# Sound subsystem — lens-panel adjudication packet

**Review SHA:** `ffe05158` (pinned; worktree `.worktrees/sound-lens`, branch `review/sound-lens-sweep`)
**Corpus:** `engine/sound/*.emp` (9,630 lines), `engine/debug/sound_debug.emp`,
`games/sonic4/config/sound_ids.emp`, `games/sonic4/data/sound/**`, and the producers
`tools/{gen_sound_tables,sfx_transcode,song_packer,smps_import,dac_encode,dac_verify}.py`.
**Panel:** the ratified roster — A · A2 · B1 · B2x2 · C1x2 · C2x2 · C3x2 · C4x2 · C5 · V.
15 read-only seats. Doubled seats diverged on two axes: opposed walk orders (one from the
Z80 driver inward, its pair from the Python producers inward) and different models.
**Adjudication:** every load-bearing citation below was re-verified by the overseer against
the pinned tree. Verification status is marked per finding. No seat reported BLOCKED.

---

## 1. Why this sweep, and what it changes

The 2026-07-16 engine-wide review covered sound completely — but it read the `.asm` twins
that no longer exist, so every anchor in it is stale. Since then ~3,165 lines have landed
across four landings (wave-4 Z80 reclaim 08-03, sound-pkg1 08-09, pkg3 + pkg4 08-10, Tails
flight SFX 08-11) with **zero adversarial review**: 52% of `z80_sound_driver.emp` and 28%
of `sound_sequencer.emp` are post-baseline.

**The subsystem is well built.** Seat B1 found construct discipline essentially clean (zero
explicitly-sized branches corpus-wide, real structs with `offsetof` derivations,
`dac_samples.emp` cited as a model file). Seat A2 checked ~130 factual claims and found
~85 true, with **zero comments whose falsity changes emitted bytes** — every number that
could rot is spelled as a derived expression with a re-measuring `ensure`. Seat A walked
every registration surface and found no missing row reachable by a live path. Seats C3a/C3b
between them re-verified the boot YM key-off race, every `z80_stopped` bracket, the
`z80_bus.emp` BUSREQ/BUSACK spin, FM key-on ordering, `$28` part-I routing, the `.stop`
epilogue ordering, and the PSG two-byte protocol — all correct.

What the sweep found instead is concentrated in three places: **one live player-reachable
defect**, **a coupled pair of DAC changes that were never reasoned about together**, and a
**guard layer with specific, identifiable holes** — including three separate cases of a
safety mechanism being named in a document or commit message and never built.

---

## 2. Confirmed defects, ranked

### D1 — SFX instance cap kills ONE slot of a multi-slot SFX; substitution then stacks the rest · HIGH · LIVE TODAY
**Seat:** C2a · **Overseer-verified: YES, end to end**

`sound_sfx.emp:953-962` counts every ACTIVE slot matching the incoming id and, when
`count >= sfh_cap`, kills exactly one — `d`, the lowest matching slot. A single
`Sfx_Restore` call, not a loop. `pack_sfx` forces `cap == 1` for every multi-channel SFX
(`tools/sfx_transcode.py:1561-1563`), so a 2-channel SFX always trips `count(2) >= cap(1)`
and still retires only half of itself.

Then `Sfx_SelectVoice` tier (b) — "any FREE same-kind slot" — runs **before** tier (c), the
equal-priority steal that would have reused the surviving slot. So the new instance's second
channel substitutes into a fresh voice instead of displacing the stale half.

**All three shipped 2-channel SFX are live gameplay sounds** (verified: header byte +2):

| id | SFX | chcount | call site |
|---|---|---|---|
| `$36` | SKID | 2 | `games/sonic4/player/player_common.emp:903` |
| `$B6` | DASH | 2 | `games/sonic4/player/player_spindash.emp:148` |
| `$B9` | RINGLOSS | 2 | live |

**Player-visible:** re-trigger skid (tap-turn), dash (repeated spindash) or ring-loss (two
hits in quick succession) while the previous instance runs, and you get a phased, doubled
sound roughly +6 dB, with each re-trigger consuming another voice until the stale halves
hold every PSG voice and the music's PSG parts go silent for the duration.

**Why every gate misses it:** ROM byte-identity is unaffected; the A/B renders fire each SFX
once, never re-triggered-while-running; boot smoke never skids.

**Fix direction:** make the cap kill *all* matching slots, or make tier (b) skip slots owned
by the id being replaced. Not applied — this is the find phase.

### D2 — The DAC/DMA guard pair leaves the ring with no producer for the whole VDP window · HIGH
**Seats:** C3a and C3b, INDEPENDENTLY, from opposed walks and different models ·
**Overseer-verified: YES (all premises)**

`SND_CTRL_DMA_ACTIVE` is not "a 68k DMA burst is in flight". It is raised at the very top of
`VInt_Level`, before any VDP work, and lowered only after `Process_DMA_Deferrable`
(`vblank.emp:114-124`, `:226`; `VInt_Lag` the same at `:279`) — i.e. it is up for the
*entire* per-frame VDP pipeline. `section.emp:219-231` raises it directly for what its own
comment calls a "~3-frame VDP poke storm", under `move.w #$2700, sr`.

Inside that window both producers are off:
- every streaming pass takes `.drain` (`z80_sound_driver.emp:414`) — no ROM read, lead burns
  at 1 sample/pass;
- and since `dcc74329`, if the Timer-A tick fires in the window, the **entire** bulk refill
  is skipped (`:1252-1254`).

There is no third producer. `SND_RING_LEAD_TARGET = 200` samples = **10.9 ms** of lead
against a ~50 ms storm. The lead exhausts and `a5fd3cf8`'s DC-hold engages for the remainder.

**The beat is deterministic, not random.** Timer A's period (`SND_TIMERA_N = 137` →
16.652 ms, 60.055 Hz) and NTSC frame (16.688 ms, 59.922 Hz) share the master crystal, so the
phase slip is a fixed ~36.7 us/frame and the tick walks the whole frame in ~455 frames
(~7.6 s). For a VDP window `W`, the tick lands inside it for `W/36.7us` **consecutive**
frames — 27 frames at W=1 ms, 65 at W=2.4 ms, 136 at W=5 ms. C3a's table puts lead
exhaustion at 2-11 frames into each run.

**Player-visible:** a drum or SFX one-shot streaming when a full-plane redraw fires plays
~11 ms then clamps to a held DC level for ~35-40 ms — a sample cutting off mid-hit. Music
(FM/PSG) is unaffected; only the DAC's ROM refill is starved.

**C3a's degenerate case, and why this is a regression not just a limitation:**
`docs/superpowers/notes/2026-08-04-item26-game-shell-ab.md:97` records `$1F04` sampling as
`1` *persistently* in the OJZ scroll state. If `W` approaches the frame period, post-`dcc74329`
nothing ever writes the ring: `SND_ROM_LEN` never decrements, `SND_DAC_PHASE` never reaches 2,
`.stop` is never reached, `SND_STAT_DAC_ACTIVE` never clears, FM6 is never handed back. The
sample plays its lead and **wedges forever**. Pre-`dcc74329` the same state still produced
200 bytes/frame — glitchy and under-fed, but it progressed and terminated. **The reversal
converted a degrading-but-terminating failure into a non-terminating one.**

**Status of the two commits:** each is individually correct and honours the cartridge-bus
hazard. Neither was reasoned about against the flag's real duty cycle, and their joint
before/after oracle gate is recorded as **OWED** in `a5fd3cf8`'s own trailer with no evidence
anywhere in `docs/` that it was ever run. This finding is what that gate would have caught.

**Direction (not a prescription):** narrow the flag to actual DMA bursts; or give the tick a
producer that is safe under it (RAM staging); or, as the motivating study actually
recommended (`docs/research/2026-08-07-mdsdrv/z80-dma.md`), poll *inside* `.refill` so a tick
starting outside the window recovers what lead it can, rather than the shipped once-before-
the-loop check which is the weakest of the two placements offered.

### D3 — `RegDeltaGroupBase` length guard verifies nothing; the constant is the sole runtime bound · HIGH
**Seats:** V (engine side) + B2b (producer side) · **Overseer-verified: YES**

```
sound_fm.emp:781   ensure(7 == REGDELTA_GROUP_COUNT,
                          "RegDeltaGroupBase length must be REGDELTA_GROUP_COUNT")
```
The message names the table's length; the condition compares a constant to a literal.
`RegDeltaGroupBase` — a `pub proc` emitting 7 `dc.b` at `:765-778` — is never measured.
`sound_fm.emp:738` (`cp REGDELTA_GROUP_COUNT`) is the only runtime bound on the
`RegDeltaGroupBase + group_code` read whose result becomes a YM register number.

Delete the SSG-EG row at `:777` (a natural "revert the E5 runtime half" edit — the row is
self-documented as an independently-added feature): table becomes 6, constant stays 7, guard
passes, `group_code == 6` reads the byte after the table and writes an authored data byte to
whatever register that byte names.

**Both guards on this constant are hollow.** B2b found the producer mirror
(`song_packer.py:725`) has no parity check either, and commit `f4b270f8` claims in its
message that "the mirror is build-checked against sound_constants.emp by the existing
constant-parity test". Verified false: `TestConstantsSync._parse_asm_equates`
(`test_song_packer.py:818-820`) matches exactly three prefixes — `MEV_`, `CHROUTE_`,
`TAG_MAC_`. A landing author believed the mirror was guarded; it was not.

**Fix:** one token — `span(RegDeltaGroupBase) == REGDELTA_GROUP_COUNT`. `span()` on a proc is
already used six times in sibling modules.

**Seat conflict resolved:** Seat A graded this registry CLEAN, citing this same `ensure` as
the table-length guard and noting the `xor a` clamp at `:740`. The clamp is real but bounds
the input *against the constant*, not against the table — it cannot see a shortened table.
Seat A's verdict is downgraded. That a careful reviewer on this very panel read the guard and
concluded the table was protected is the strongest available evidence of the harm.

### D4 — "BUILD-ENFORCED" PSG env ceiling is not in the build · HIGH
**Seat:** V · **Overseer-verified: YES**

`sound_psg.emp:594` states the PSG vol-env level ceiling "is now BUILD-ENFORCED:
tools/gen_sound_tables.py rejects...". `gen_sound_tables.py` appears in neither `build.sh`
nor `test.sh`. It is generator-enforced, the generator runs only when someone runs it, and
its output `sound_tables_z80.emp` is committed source the build consumes directly.

The hazard it contains is the known-open single-bit fold at `sound_psg.emp:604` (`bit 4, a`),
whose margin is exactly one ($10 body + $0F prior atten = $1F, one below the cliff). Hand-edit
one env body byte from `$10` to `$11` — the file's DO-NOT-EDIT banner is enforced by nothing —
and PSG attenuation is OR'd into the channel-select bits and lands on the wrong channel, with
a green build.

### D5 — Adaptive songs leave FM6's output gate closed until the first FM6 patch event · HIGH (content-reachable)
**Seat:** C2a · **Overseer-verified: partial (mechanism read, not audio-confirmed)**

`Snd_LoadSong` calls `Sequencer_StopAll` first, which closes `$B6 = $00`
(`sound_sequencer.emp:2016-2036` sweeps both parts). For a *dedicate* song it re-seeds `$C0`;
for an *adaptive* song it deliberately does not (`z80_sound_driver.emp:1448-1461`), on the
theory that `Fm_PatchLoad` will set the real `$B6`. But `.chan_init` loads no patches — the
first `Fm_PatchLoad` happens when FM6's *stream* executes its first `MEV_PATCH`. With `$2B`
armed the DAC inherits FM6's L/R (the driver's own comment, `:1453`).

So any adaptive song whose DAC channel issues `$E2` before FM6 executes its first `$E1` has
silent drums until then. Two purely authorial routes: channel declaration order (channels run
in header order; `song_drumtest.py:77` happens to declare FM6 before DAC — reorder them, a
legal unvalidated edit, and the first hit is silent), or FM6 simply resting at the top of the
song (entering at bar 5 means four bars of inaudible drums).

Two unwired variants of the same root: `Sound_StopMusic` closes `$B6` and nothing reopens it,
so a later `Sound_PlaySample` is silent; and `SndDrv_Init` never writes `$B4-$B6` at all, so a
pre-music sample depends on YM power-up state (0 on silicon; emulator-dependent otherwise).

### D6 — `Seq_SilenceMusicVoices` is below the driver's own data-to-next-address floor at three sites · HIGH
**Seat:** C3a · **Overseer-verified: NO — arithmetic not independently re-derived**

`sound_fm.emp:107-118` states the model: ~8 T after an address-port write, **~39 T after a
data-port write**, measured start-to-start, with no busy poll anywhere. C3a counts
`sound_sequencer.emp:2027-2039` at 17 T, 34 T and 32 T against that 39 T floor. The `nop`s at
`:2024`/`:2031` pad the address-to-data gap (which *is* ensured at `:2050-2055`), not the
data-to-next-address gap, which is the short one — so the three `ensure`s pass over the wrong
axis. `sound_fm.emp:1163-1191` already admits the ~39 T half is never machine-checked.

Consequence if the model holds: a dropped `$B4` part-II write leaves FM4/5/6's L/R gate open,
so release tails bleed across a song stop — the exact pop the block exists to suppress. A
dropped `$2A` re-park leaves the address latch on `$B6` and the streaming loop writes DAC
bytes into FM6's pan/AMS register at 18 kHz until the next tick's `.reparkDac`.

**Owner ruling wanted:** the tree contains two incompatible YM busy models —
`docs/specs/boot-ym-keyoff-race.md` §2 argues from ~25 us (~90 T), `sound_fm.emp` from
~10.8 us (39 T). Both cannot be right, and they justify opposite conclusions about the `$28`
key-off loop at `:2006-2015`. Resolve the model before acting on this finding.

### D7 — Unvalidated SFX streams reach two memory-corrupting interpreter paths · MEDIUM-HIGH (content-reachable)
**Seat:** C2a · **Overseer-verified: NO — read but not traced to a built blob**

Specific consequences of the known-open `pack_sfx`-never-calls-`Event.validate` gap, neither
of which is in the existing record:

- **`Seq_Op_PitchEnv`** (`sound_sequencer.emp:1420-1442`) trusts the point count from the
  stream ("packer guarantees 1..5" — that guarantee is `Event.validate`, which SFX never
  reach). `count == 0` makes `djnz` run **256** times, copying 256 stream bytes from
  `&sc_points[0]`. `SfxChannel_len` is 68, so it writes ~200 bytes past the slot: through the
  remaining SfxChannels, `SND_SFX_ID_TAB`, the dispatch scratch, and toward `SND_REQ_BASE`.
  `Seq_Op_RegDelta`'s `.fm` path (`:1531`) has the same `ld b,a`/`djnz` shape.
- **`MEV_JUMP` with `sc_loop_ptr == 0`** (`sound_sequencer.emp:1687-1689`). `Sfx_BeginSound`'s
  `.wipe` zeroes the slot, so a `Jump` with no preceding `LoopPoint` sets `hl = $0000` and the
  channel interprets the driver's own code as an event stream. `song_packer.py:954` raises on
  this; `pack_sfx` does not.

Also unvalidated: an SFX stream may legally contain `MEV_TEMPO` (writes global music tempo and
broadcasts to every music channel) and `MEV_EXT` (writes the 68k-visible `SND_STAT_COMM`).

### D8 — `sc_macro_active` aliases `sx_patch_base`, and it is the one overlap with neither guard · MEDIUM (latent)
**Seat:** C4a · **Overseer-verified: YES**

```
SeqChannel:  sc_noise_mode +57 · sc_detune +58 · sc_pad        +59
SfxChannel:  sx_priority   +57 · sx_pad     +58 · sx_patch_base +59..+60 (u16)
```
`sc_macro_active = offsetof(SeqChannel, sc_pad)` = +59 (`sound_constants.emp:866`), and
`Seq_Op_Macro` writes it (`sound_sequencer.emp:1169`) through the *shared* interpreter that
also walks `SfxChannel`s. The +57 and +58 overlaps each carry a layout `ensure`
(`sound_constants.emp:792-795`) **and** a producer blacklist entry. For +59:
`grep 'ensure.*sc_pad|ensure.*sx_patch_base'` returns nothing, and `_validate_no_aliasing_ops`
names only `MEV_PSGNOISE` and `MEV_DETUNE` — grepping `sfx_transcode.py` for Macro/`$F9`
returns nothing at all.

Unreachable today only because the SFX transcoder has no Macro event class; nothing in the
build says so. If an SFX stream ever carries `$F9` it rewrites the low byte of the running
SFX's own patch-window pointer and `Fm_PatchLoad` uploads garbage as a voice. **Zero Z80 bytes
to close.**

### D9 — CTRL-slot unpause defeats an in-flight jingle freeze · HIGH defect / LOW reachability
**Seat:** C2b · **Overseer-verified: YES**

`Snd_CtrlCommand`'s `.unpause` is a bare `jp Snd_ResumeMusic` (`z80_sound_driver.emp:946`)
with no `SND_JINGLE_ACTIVE` read — the only readers of that cell are `Sfx_JinglePopCheck` and
the sequencer's own gate. An unpause posted while a jingle holds the pause state resumes every
music channel under the still-sounding jingle, and the later pop-check then fires its own
resume on top, audibly dipping and re-fading the music a second time.

Unreachable today: **zero callers** of `Sound_PlayJingle`/`Pause`/`Unpause`/`PauseAll`/
`UnpauseAll` outside `engine/sound` (verified). Goes live the moment the Start-menu pause or
the 1-up jingle is wired — which the design doc names as the first two consumers.

### D10 — `Fm_TransposeClamp`'s high-clamp path leaves `h` non-zero · MEDIUM-LOW (latent, one instruction)
**Seat:** C2a · **Overseer-verified: NO**

`sound_fm.emp:834-843`: the contract at `:811-815` promises `h = 0`; the negative-clamp path
honours it (`ld hl,0`), the high path does `ld l,c` and returns with `h` still 1. Callers then
`add hl,hl` + `add hl,table_base`, reading **512 bytes past** the entry — off the end of the
190-byte `FmPitchTableZ` entirely. Unreachable today ($83 max note + $10 rev cap = $93), live
the moment a `MEV_TRANSPOSE`-style opcode lands or the rev escapes its cap (C2a's F10: the cap
is an equality test `cp $10 / jr z` on a value that grows quadratically if `MEV_SPINREV` ever
executes twice per instance, which nothing rejects). Worth fixing now because it is one
instruction.

---

## 3. The process finding — three mechanisms named and never built

This is the pattern I would fix structurally rather than case by case. Three different
authors, three landings, each recording a guarantee that was never implemented — and in each
case the *code* shipped while the *check* existed only in prose.

| Named mechanism | Where claimed | Reality |
|---|---|---|
| D8 linker asserts | 2026-07-16 review, `[closed by D8 linker asserts]` | never shipped; fired as a boot ADDRESS ERROR 2026-08-03 |
| constant-parity test covering `REGDELTA_GROUP_COUNT` | commit `f4b270f8` message | test matches only `MEV_`/`CHROUTE_`/`TAG_MAC_` (D3) |
| DEBUG exclusivity assert for CTRL/JINGLE/MUSIC/FADE | pkg1 design doc §6.4 (`:213`) + §10 (`:301`) | absent; `z80_sound_driver.emp:15` states the driver has ZERO `__DEBUG__` content, so no shape could host it |

The standing bar from the 2026-08-01 sweep already covers "a claimed guard that does not
exist". What it does not cover is a guard claimed in a *commit message* or a *design doc*
rather than in code. Recommend: a merge-ritual step that greps the landing's own prose for
mechanism claims and requires each to resolve to a file:line.

---

## 4. Coverage verdict — what actually guards this subsystem

**Genuinely gated** (comptime, falsifiable, in the build path): Z80 blob size and evenness
(`engine/system/boot_data.emp:64,71` — the remediated 2026-08-07 finding, and the one cited
wall that stands); the Z80 RAM-map seams; ring/SFX base page alignment; vol-env id/ptr parity
and LUT extents (`span()`-measured); `DacSampleTable`'s emitted span; the banked head sizes
and 8-alignment (`soundbankhead.emp:67-82`); the 13 YM address-to-data floors; the DAC loop's
195 T balance; the 41 `SeqChannel`/`SfxChannel` prefix offsets; `CHROUTE` table length.

**Gated only by a producer that nothing runs** — every one of these is single-point
containment behind `python3 tools/<x>.py`, invoked by no script and no CI, whose output is
committed source: the PSG env level ceiling (D4, margin 1); the "vol-env body must not start
with `$80`" rule (hangs the driver inside the Timer-A tick with interrupts off, and the file
concedes it is "the only place it can be caught"); non-empty vol-env body;
`FMPITCH_MAX_IDX` vs table geometry (the only bound on the `FmPitchTableZ` index clamp); the
SFX aliasing-opcode blacklist; SFX `RepeatEnd` operand range.

**Gated by nothing:** `SND_RING_LEAD_PRIME <= SND_RING_LEAD_TARGET < 256` (prose at
`sound_constants.emp:207`, no mechanism); `RegDeltaGroupBase` row count (D3); the
`sound_ids.emp` ↔ `sfx_transcode.py` priority mirror, and four more producer mirrors
(`SH_F_*`, `SFXEL_*`, `SHF_*`, `FMPATCH_LEN`) — all currently identical, all hand-diffed, none
checked; a tenth `SFXPRI_*` constant's bit-7 property (the fold is a fixed 9-name list); SFX
blobs 2..11 co-residency (only `Sfx_33` is checked); `YM_ADDR_TO_DATA_MIN_T`'s three
independent declarations.

**All 374 sound test functions across six modules are invoked by nothing** — no CI, no
`pytest.ini`/`conftest.py`, absent from `test.sh`. Includes ~20 tests in
`test_gen_sound_tables.py` that drive emitters the file itself declares dead, and
`test_ids_ptrs_count_match`, which does not compare ids to ptrs. `dac_verify.py` prints
"NOT the sample (garbage/silent)" and **exits 0**.

---

## 5. Convergent findings (independent seats, same target)

Convergence across opposed walks and different models is the panel's strongest signal.

- **Vol-env resolver is a per-frame linear scan** — C4a, C1a, C1b (three seats, three lenses).
  `sound_psg.emp:192-253` walks a sparse 11-entry id list, up to 10 misses, every frame per
  keyed channel. The replacement direct-index table lands in the **banked** window, not
  against the `$18F0` resident ceiling. Est. -100..-450 T per resolve.
- **`YM_ADDR_TO_DATA_MIN_T` declared three times, cross-checked zero times** — A2, B2a.
  `sound_fm.emp:135`, `sound_sequencer.emp:82`, `z80_sound_driver.emp:113`; RHS of 13
  `ensure`s whose sets are disjoint per module. Zero-byte fix.
- **fnum block-renormalize: one shared helper and one hand-inlined twin** — B2a, C4b.
  `Fm_FnumApplyDelta` vs `Mod_Advance`'s `.fm_pack`; the sequencer already calls the helper
  twice for portamento and inlines it for vibrato. Both carry the same accepted-edge-case
  essay; nothing binds them.
- **The YM spacing coverage ledger under-enumerates** — A2, B2a, C3a. `sound_fm.emp:1161`
  claims 9 checked sites and lists 10; the real count is 13, and 6 structural twins are
  ungated (incl. `Snd_LoadSong`'s `$B6` seed, byte-identical to a gated site).
- **`soundbankhead.emp` carrier VMAs are pre-flight-SFX** — A2, A. Header says
  `$856D/$85AD`; the file's own size walls re-derive `$8571/$85B1`, and `:59`/`:61` in the
  same file are correct.

---

## 6. Open questions requiring something outside this tree

1. **Does sigil's seam-1 `banked_carriers` list PIN or DERIVE the head VMAs?** Two seats
   independently flagged this and neither could answer it from the aeon tree — no
   `banked_carriers`/`$856D`/`$85AD` string exists in any `.toml`/`.py`/`.sh`/`.emp` here.
   If it pins, the `$856D -> $8571` shift is a live cross-seam desync rather than doc drift.
   **Resolve this first.**
2. **Which YM busy model is correct** — ~39 T (`sound_fm.emp`) or ~90 T
   (`boot-ym-keyoff-race.md`)? D6 depends on it, and both live in-tree justifying opposite
   conclusions.
3. **Was the pkg1/pkg4 DAC before/after oracle gate ever run?** `a5fd3cf8` records it as
   OWED; no record exists in `docs/`. D2 is what it would have caught.
4. **E5 SSG-EG mid-note behaviour.** Both C3 seats raised the SSG-EG invert-latch quirk
   (reset only on key-on) as a risk for `$90` RegDelta sweeps, both labelled it community
   lore rather than datasheet text, and the feature's own owed verification
   (`2026-07-03-sound-correctness-batch.md` Step 3, E5) is still unchecked.

---

## 7. Reclaim opportunities (C5, C1a/C1b — estimates, not link-measured)

- **~32 KB of dead ROM**: `dac_blip_bank` pins a 2,880-byte retired bring-up placeholder alone
  at `$48000`, then `align $8000` pads 29,888 bytes to `$50000`. Every reader audited: the id
  is marked "DEAD — no reader anywhere", the debug hotkey is self-documented as "Superseded",
  no song references DAC id 1. Directly relieves the `map.toml:41-49` pressure that exiled
  `Map_Tails` to the ROM tail.
- **-94 B resident, cycle-neutral or better**: collapse `Sfx_Steal`'s three byte-identical
  kind arms (-37 B, also saves cycles); occupy the dead 53-byte IM1 vector gap with driver
  leaf procs (-41 B, zero instructions changed); `Fm_YmWriteCh` fall-through prefix (-16 B,
  exactly cycle-neutral, does not narrow any YM gap).
- **-548 B**: `SfxTable`'s 137 cells x 4 B, of which 126 are holes — no reader in `engine/`,
  `games/`, or the resident Z80 (sigil's own `seam2.rs:983` comment concurs).
- **Explicitly recommended AGAINST**: re-encoding `SfxBlobWinTab` sparsity (-115 B net) and
  reverting the DAC descriptor to 6 bytes (-64 B banked). Both spend risk on the exact
  alignment mechanism that made the plain ROM go silent in `46ea51f1`, to buy back an
  uncontested resource.
- **BLOCKED on toolchain**: ~-116 B via Z80 `rst` vectors in the dead gap. `rst` is not
  encodable — it exists only in sigil's contract analyzers, with no IR opcode, no AS mapping
  and no backend emission. A sigil feature request, not a sound-lane change.

---

## 8. Seat conflicts

- **RegDelta registry (A vs V)** — resolved in V's favour; see D3. A's CLEAN verdict is
  downgraded and is itself evidence for the finding.
- **Vol-env resolvers (C4b vs C4a/C1a/C1b)** — not a conflict. C4b praised them as *unified*
  (one shared scan rather than duplicated), which is true; the other three fault the *scan*
  as the wrong data structure, which is also true. Both stand.

---

## 9. What was NOT covered

- C3a did not reach `sound_sfx.emp` in depth (walk-order tail); C3b's reverse walk covers it.
- B2a did not line-diff `mt_bank*.emp`/`movingtrucks_pitchtable.emp` against their
  `zyrinx_port.py` producer — flagged as its own coverage gap.
- Seat V did not enumerate `Event.validate`'s full rule set to determine exactly what
  `pack_sfx` loses beyond the three `_validate_*` backstops. That diff is the obvious next step.
- No emulator was run by any seat (deliberate — oracle MCP deadlocks from subagents). Every
  runtime consequence above is static reasoning. D1, D2 and D5 each want a live confirmation.
