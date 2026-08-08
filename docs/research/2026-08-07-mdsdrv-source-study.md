# MDSDRV source study (2026-08-07)

Source-level read of **MDSDRV** (superctr) — `github.com/superctr/MDSDRV`, cloned to
`docs/research/external/mdsdrv/` (gitignored; upstream, not vendored).

**Why this was worth doing.** Every prior MDSDRV reference in our docs
(`2026-06-23-genesis-technique-survey.md:26,44`, `ENGINE_ARCHITECTURE.md:3085`,
`DEFERRED_WORK.md:2047`, the sound design specs) came secondhand from the GDRI wiki
and MDSDRV's own `doc/`. Nobody had read the code. Three agents read all 9.4k lines
of it against our shipped driver.

Evidence files: [`core.md`](2026-08-07-mdsdrv/core.md) ·
[`z80-dma.md`](2026-08-07-mdsdrv/z80-dma.md) ·
[`format-toolchain.md`](2026-08-07-mdsdrv/format-toolchain.md) ·
[`sfx-and-gaps.md`](2026-08-07-mdsdrv/sfx-and-gaps.md)

---

## The result in one line

The headline yield is **not** a feature to copy. It is a **defect list against our own
driver**, plus one architectural correction to how we represent pitch.

---

## 1. Architectural correction: pitch belongs in the log domain

**Confidence: verified in both codebases.**

MDSDRV builds a single 8.8 fixed-point *semitone* value per track and moves everything
on it — detune is literally 1/256 semitone (`t_dtn`), transpose is its integer part,
portamento and the pitch envelope both step that number. F-num is derived exactly once,
at the end, by linear interpolation between adjacent table entries
(`mds_pitch_update` mdsdrv.68k:1988-1996; `mds_get_fm_pitch` :1887-1907, with a
`beq.s` fast path that skips the multiply when the fraction is zero).

We add `sc_detune` straight to the 11-bit f-num (`sound_fm.emp:971-987`) and step
portamento in f-num units (`sound_sequencer.emp:276-436`). F-num is linear in
*frequency*, so:

- the same authored depth is worth ~2x more cents at the bottom of an octave block
  than at the top;
- modulation changes discontinuously across a block boundary.

This is a fidelity flaw in our expression engine, not a stylistic difference. It is the
likely explanation for any "vibrato feels uneven in the high register" symptom.

Adopting the log domain also lets us **delete** `Fm_FnumApplyDelta`
(`sound_fm.emp:883-938`, ~55 resident Z80 bytes plus a documented block-7 bit-bleed
edge case) — which matters against our ~316 B headroom. Cost: an 8x8 shift-add
multiply, ~2.5% of a frame for 6 FM channels, un-modulated case stays free.

**Verdict: take it.** Biggest single idea in either path. Needs a scoped plan, not a patch.

## 2. Two latent bugs in our Z80 driver

Found by reading MDSDRV's `doc/dma.md` and comparing, not by testing.

**2a. `SndDrv_TimerATick` bulk-refills from banked ROM during an active DMA**
(`z80_sound_driver.emp:976-999` — its own comment says so). Timer A is 60.05 Hz against
VBlank's 59.92 Hz, so the tick's phase walks continuously through the DMA window. This
is not a rare race; it fires regularly. It is exactly the hazard `doc/dma.md:18-26`
describes: address-line glitch at DMA start corrupting VRAM or 68k RAM.
Fix: poll the flag inside `.refill`, ~6 B.

> ⚠️ **This is a hardware-only hazard. Our emulator cannot reproduce it, and we have no
> real hardware** (see memory: no-real-hardware). Taking this fix means accepting it on
> reasoning + MDSDRV's documentation rather than on verification — a different confidence
> class than our normal practice. **Flagged for user ruling, not assistant discretion.**

**2b. `.drain` has no underrun guard.** RD laps WR and replays the ring as a ~72 Hz buzz;
worse, the tick's `cp LEAD_TARGET / jr nc` then reads the lapped ring as *full*, so it
never recovers. MDSDRV holds the last sample instead (`mdssub.z80:299-310`).
Fix: 34 T branchless "don't advance RD at lead 0", fits inside the existing 76 T DRAIN
pad. ~9 B, **0 added cycles**. Confidence: verified by code read; reproducible in
emulator, so this one we can prove before and after.

**2c. Possible re-key flam (inferred, unconfirmed).** `Seq_RekeySingle` may leave
`SCF_REKEY` pending during a steal (`sound_sequencer.emp:612-613`) while `Sfx_Restore`
separately re-keys from `sc_base_freq`; both could fire around a restore. MDSDRV's rule
(mask a pending key-on if <5 ticks remain, always in drum mode, `:915-924`) is an ~8 B
fix either way. **Needs an emulator trace before it is treated as real.**

## 3. On DMA survival specifically: we are fine

**Confidence: high, verified both sides.** The prior claim at
`2026-06-23-genesis-technique-survey.md:42` **holds**.

MDSDRV's DMA approach is near-identical in *mechanism* to our flag-bracket: keep the Z80
running, feed the DAC from a RAM ring through the window, cycle-match in-window output.

| | MDSDRV | Ours |
|---|---|---|
| Fail mode | fail-**closed** (missed ack = silence) | ✗ we can read ROM mid-DMA (§2a) |
| No-68k-bus rule in window | absolute | ✗ violated by §2a |
| Window tightness | all of vblank | ✓ the DMA pipeline only |
| Bus holds/frame | dozens (68k sequencer) | ✓ 2 |
| Cycle balance rigour | hand-counted comments | ✓ `ensure(cycles())`-checked |
| Sample placement | runtime bank-crossing + align table | ✓ build-time no-straddle |
| DAC rate | 17809 Hz (2 streams) | ✓ 18356 Hz (1 stream) |

Their two wins are exactly the two bugs in §2. Fix those and we dominate the comparison.

## 4. Feature gaps confirmed (not inferred)

- **No pause/resume at all.** `grep -rn "PAUSE|Pause|SUSPEND" engine/sound/*.emp` → one
  unrelated comment. MDSDRV's `set_pause` (:315-339) suspends/resumes with a single
  `ori.b #nm_init|nm_restore` re-arm. We own every piece already (`Sfx_Restore` *is* the
  restore body). Low effort.
- **Tempo is hard-capped at one tick per frame** (`sound_sequencer.emp:149` says so
  explicitly). MDSDRV runs N ticks/frame (:504-513, `dbra d5` :546). Blocks sub-frame
  groove and fine tempo.
- **Fade has exactly one hardcoded rate** (`SND_FADE_STEP=2`, `SND_FADE_DELAY=1`).
  MDSDRV gets eight evenly-spread fractional rates from one byte and three instructions
  via a rotating bit pattern (`dc.b $01,$11,$49,$55,$57,$77,$7f,$ff` + `ror.b`/`bpl`,
  :309-310, :939-942). Cheap and charming.
- **No call stack.** Ours is single-level `sc_repeat_ptr`. This blocks §5 and §6 below.

## 5. Drum mode

A note byte in a drum-mode track is not a pitch: it indexes the song table and is
**called as a subroutine on the track's own stack** (:1112-1119), terminated by
`dmfinish nn` which pops and supplies the actual note (:1553-1557). One sequence byte
expands to a whole FM percussion program. No equivalent on our side. Requires the call
stack (§4).

## 6. Data density: we are 3-5x fatter than we should be

**Confidence: measured, with a stated caveat.** The agent decoded MDSDRV's five real
songs and both our shipped blobs with matching decoders and simulated loop expansion.

| | bytes/sec of music | structural compression (executed:stored) |
|---|---|---|
| MDSDRV (5 songs) | **15-27** | 2.8-6.1x |
| Moving Trucks | 79 | 1.8x |
| HCZ2 | 124 | **1.0x** |

Caveat: different music, and both our songs are machine ports — `smps_import.py`
flattens every S3K loop, and HCZ2 contains zero repeats to begin with. So this
overstates the gap. But the mechanisms behind it are real and individually measured:

1. **Two running-duration registers + bare-length-byte-as-rest** (`mdsdrv.inc:139-140`,
   `doc/mdsseq.md:301`). We have one `sc_dur_default` (`sound_constants.emp:622`).
   Re-encoding HCZ2 under their semantics: **5576 → 3871 B, −26.2% of the whole blob.**
2. **Nested counted loops + `lpb` loop-break** (mdsdrv.68k:1480-1537, 8-word stack/track).
   Ours is single-level and non-nested (`sound_sequencer.emp:1501-1548`). This is where
   the density gap actually lives. Costs 88-132 B of Z80 channel RAM.
3. **Our Note opcode spans 95 pitches; MT's table needs 132.** The shortfall forces 1824
   single notes to encode as `$E8 01 idx` — **3648 B, 29% of Moving Trucks**, purely from
   an opcode-range shortfall. Root-cause fix is `trs`/`trsm` transpose opcodes
   (near-free: `sc_transpose` already exists and is already applied in
   `sound_fm.emp:778-950`; only `Seq_Op_SpinRev` writes it) and/or a per-instrument
   transpose byte (`FmPatch` has `fp_reserved[2]` waiting).
4. **Reference repeated payloads by 1-byte id** — MT has 1824 `PitchEnv` events with only
   **29 distinct payloads**; by-id saves 1766 B (14% of MT).

## 7. Smaller takes

- **`slr` slur/legato** — closes the exact "accepted v1 fidelity gap" recorded at
  `smps_import.py:670-676` for different-pitch `smpsNoAttack`.
- **Macro table writes channel *state*, not just YM registers** — mtab `$00-$3f` = set
  struct byte at offset, `$40-$7f` = add, saturating clamp on TL, auto-dirty past `t_vol`
  (:1618-1647). `(ix+d)` makes this cheap for us, **but** the offset must be build-gated:
  our shared interpreter walks both `SeqChannel` and `SfxChannel` with load-bearing
  aliases past +56.
- **`comm` song→game cue byte** (already noted in our game-feel spec as an "MDSDRV steal").
- **2-byte macro register writes** (`cmd<<2`); ours is 4.
- **Ring-lead telemetry byte** (their `z_load`) — we currently have **no way to measure
  DMA-survival margin at all**. 5 B. Their `sample/dma/` is a tuning instrument with an
  adjustable simulated-DMA burn; worth building the equivalent.
- **`volm` relative volume** (45-69 uses/song), **`pat` subroutines**, data version byte,
  link-time global patch dedup.

## 8. Rejected, with reasons

| Candidate | Why not |
|---|---|
| Position-independent code | Z80 has no PC-relative addressing; the table-of-`bra.w` sub-idea is strictly worse for us — `SeqOpcodeTable` is already banked |
| Opcode-patch trick for hot-loop flags | **RESOLVED — rejected, superseded by a non-SMC fix. See §10.** |
| 16×256 B volume-LUT mixing | Needs 4 KB of Z80 RAM we do not have. Reduced forms noted in `z80-dma.md` |
| Z80-self-opens-the-window | Incompatible: our loop is `di` end-to-end by design; theirs runs `ei` and pays with a shadow-register-detection hack |
| Their batch producer | 16 T/sample for enormous hand-interleaving; our single stream already beats their two |
| FM3 special mode | Four op-tracks share one patch **and** one algorithm → 3 timbre-locked voices, not 3 instruments. Collides with SFX stealing FM3. Banked, not near-term |
| 68k-resident sequencer / 4-slot BGM+SFX unification | A rewrite, not a technique. Our Z80-autonomy ruling stands (and unlike them, we ship ducking) |
| Pointer-byte scavenging, type union, command-length table | 68k-specific or measured at ~18 B total saving |
| PAL tempo compensation | Prior ruling |

## 8b. SFX arbitration — added 2026-08-07 after a second pass

Prompted by a Discord post from an MDSDRV integrator (MDTravis): *"ive implemented a
list-based priority system due to how sfx work in this driver"*, showing tiered
null-terminated ID lists (`.hiPri`/`.midPri`/`.loPri`, `dc.w` … `-1`).

**Initial reading (mine) was wrong and is corrected here.** I read it as evidence MDSDRV
lacks priority. It does not.

- MDSDRV **has** real arbitration: `mds_update_priority` (mdsdrv.68k:878-932) — 4 request
  slots, channel-granular; the loser gets `cf_background`, keeps running muted, and
  restores via `nm_restore`.
- What it lacks is **sound-intrinsic** priority. No priority byte exists in the song
  header, the sequence stream, or the driver. `mds_request` is five instructions with
  **zero comparison against what is playing** (:140-145) — unconditional overwrite, stated
  outright at `doc/api.md:39-41`.
- Therefore the tier lists are **the ID→slot mapping every integrator is structurally
  required to write**. Three tiers because exactly three SFX slots exist
  (`MDS_SE3=0/SE2=1/SE1=2`). A delegated job, not a missing feature.

**Architectural note worth keeping:** MDSDRV keeps *mechanism* in the driver and delegates
*policy* to the game. That is the same split independently recommended for our own SFX
work — frame-level policy (instance limiting, game-context arbitration) belongs on the 68k
where it is free and informed; live-channel-state mechanism (steal, save/restore, duck)
belongs on the Z80 where the state lives. See §8c.

**Head-to-head: MDSDRV has nothing here we lack.** Verified from code:

| | MDSDRV | Ours |
|---|---|---|
| Priority source | caller-declared slot only | ✓ sound-intrinsic, 7-bit + bit7 non-latching (`sound_sfx.emp:810-813`) |
| Build-time guard | none (lists keyed on ID *values*, stored away from the definitions — renumber and it rots silently) | ✓ `SFXPRI_*` beside the ID, build-fatal `ensure` (`sound_ids.emp:98-99`) |
| Concurrent SFX voices | 3 | ✓ 7 |
| Steal gate | unconditional overwrite | ✓ 3-tier ladder with `>=` gate (`sound_sfx.emp:1609-1750`) |
| Instance caps | none | ✓ per-SFX (`sfh_cap`) |
| Request buffering | single word — **a same-frame double request silently loses the first sound** | ✓ 68k ring w/ dedup + Z80 priority queue |
| Ducking | **none** | ✓ duck ramp |
| Request cost | hard stop + one frame of silence (2-frame `rf_stop`→`rf_active`) | ✓ no forced silence |
| Voice allocation | none — physical channels baked into song data | ✓ allocated |

Honest steelman for tiered lists: sparse tier lists cost less ROM than a dense byte table.
Killer flaw: second source of truth, keyed on ID values, no build-time guard.

**Sweep result on "what else did we miss": not much.** Two items, both observability, and
they rhyme with the missing DMA-margin telemetry in §7:

1. **Live per-track state table rendered every frame** in their test ROM
   (`main.68k:241-290`). Our mirror covers 3 music channels and **zero SFX channels** —
   steals, drops, and queue depth are currently unobservable. Concrete Oracle requirement.
2. **Driver cost meter** read straight from the H/V counter after the update
   (`main.68k:330-335`), ~3 instructions.

Cross-cutting theme: **our sound system is under-instrumented.** No DMA-survival margin,
no SFX channel visibility, no cost meter.

## 8c. Should SFX priority live on the 68k instead of the Z80?

Question raised 2026-08-07. Short answer: **the MDSDRV comparison does not support it, but
there is an independent case — for quality, not for space.**

- **MDSDRV is not evidence either way.** Its sequencer is *already* 68k-resident (16 tracks
  on the 68k; Z80 does PCM only). Putting priority on the 68k costs it nothing and saves it
  nothing, because none of its sound logic was ever on the Z80. Apples to oranges.
- **Our SFX *data* is already off-Z80** — blobs and `SfxHeader` priority bytes live in
  banked 68k ROM (`sound_sfx.emp:38-44`). What is Z80-resident is mechanism, not table.
- **Movable:** the queue + best-of-N scan (`Sfx_DrainQueue`, `sound_sfx.emp:117-180`).
  It exists to pick a winner when several SFX are requested in one frame — but the 68k
  *is* the requester and inherently holds all of them before writing the mailbox.
- **Not movable without cost:** the steal compare and instance cap need live channel state
  (`sx_priority`, `sfh_cap`); moving them means publishing a Z80 occupancy mirror, costing
  a bus hold and making the state a frame stale.
- **Must stay Z80:** save/restore and the duck ramp.

**Recommendation: do not do this for space.** Headroom is ~316 B after the wave-4 reclaim
(was 86 B), the log-domain change in §1 frees ~55 B more, and the net saving is smaller
than the raw queue size because the Z80 still receives and acts.

**Do consider it for context.** The Z80 arbitrates blind on priority numbers; the 68k knows
this explosion is the boss dying and that ring was the eleventh this second. That is exactly
the "instance limiting and per-sound depths" gap our own SFX spec
(`2026-07-02-sfx-fidelity-and-mixing-design.md:72`) already identified against modern
practice. Frame-level policy → 68k; live-state mechanism → Z80.

## 9. Corrections to the record

- **RAM claim verified by computation**: TSIZE=58, WSIZE=1004 B, 92.4% of it the 16 track
  structs. Ours is 1136 B for 18 slots — same order, we are not overweight.
- Two errors in MDSDRV's own docs: `PCM_MIN_BUFFER` is 35 in source, 40 in `dma.md`;
  volume range is `$0F`-`$1E`, not the `10-1f` its comment claims.
- **Seraph has no Aeon/MEMRA exporter** — zero `memra|aeon` hits in its Rust/TS source.
  S0/S1 are banked and unstarted; it emits SMPS `.asm` + VGM only. Our real authoring path
  is the `song_packer.py` Python DSL. (Corrects any assumption that the Seraph→Aeon path
  exists today.)
- MDSDRV's MML front end (ctrmml) is **not in-repo**. Two constructs worth stealing as
  notation: `{a/b/c}` chord fan-out across a track group, and `/` inside `[...]n` as
  loop-break.

---

## 10. RESOLVED: the opcode-patch trick — rejected, non-SMC fix wins

Second-pass analysis 2026-08-07, prompted by "is there a middle ground?". Answer: no middle
ground is needed, because a **structural fix beats SMC on cycles at zero SMC risk.**

**The originally-quoted "+23% / −9 B" was wrong on both halves.**

- **The naive PHASE patch is buggy as specified.** `.afterPoll` (the Timer-A tick rejoin,
  `z80_sound_driver.emp:1012`) enters the PHASE site with flags from `or l` in
  `.refillDone` — **NZ whenever len≠0** — so a patched `$C2` is taken and truncates every
  *healthy* sample. Needs a 1-byte `xor a`, so −9 B was never the true cost.
- **Second footgun:** the "inactive" opcode **inverts** between "patch DMA only" (flags NZ
  from `cp 2`) and "patch both" (flags Z). A later edit to the PHASE site would silently
  flip the DMA bracket into filling *through* an active DMA.
- **The split is 20/17, not even.** PHASE `ld a,(nn)`+`cp 2`+`jp z` = 30 T → 10 T
  (−20 T, −5 B). DMA `ld a,(nn)`+`or a`+`jp nz` = 27 T → 10 T (−17 T, −4 B).

**Risk asymmetry confirmed.** `SND_DAC_PHASE`: six refs, all in `z80_sound_driver.emp`,
**zero 68k writers or readers** — safe site. `SND_CTRL_DMA_ACTIVE`: written by the 68k at
four bracket sites — unsafe, and needs a cross-address-space symbol export
(`:128-133` documents that collision class), the largest integration cost and not a byte cost.
Blast radius differs by class: bad flag = one wrong branch; bad opcode = arbitrary Z80
execution at 18 kHz.

**No spare register — verified, not assumed.** `a`/`l` scratch (consumed every pass),
`b`/`c` ring, `d`/`e` `$4001` invariant, `h` ring page, `ix` ROM ptr, `h'`/`l'` len.
Shadow `c'` costs an `exx` pair (26 T vs 27 T — saves 1 T); `iyl` = 22 T (saves 5 T,
undocumented opcode + per-frame reload). No free 16-bit pair. All dead ends.

**THE FIX: split the loop. −30 T, zero SMC, ~+15 B.** PHASE is not a flag, it is a *mode*
that changes once per sample — testing it 18356x/sec is waste. Give DRAINING_TAIL its own
loop; `.exhaust` jumps there, the tick picks its rejoin label. FILL = 165 T / 21694 Hz,
DRAIN pad unchanged at 76, DRAINING at 164 (same 1-T tail gap already accepted).

| # | option | period | rate | bytes | SMC | verdict |
|---|---|---|---|---|---|---|
| 1 | **Loop-split PHASE** | 165 T | 21694 Hz (+18.2%) | ~+15 B | **0** | **RECOMMENDED** |
| 2 | #1 + SMC on DMA | 148 T | 24186 Hz (+31.8%) | ~+11 B | 1 cross-CPU | only behind a Sigil `patch_site` construct |
| 3 | SMC PHASE only | 175 T | 20454 Hz | −4 B | 1 local | dominated by #1 |
| 4 | SMC both | 158 T | 22655 Hz | −8 B | 2 | dominated by #2 on cycles, #1 on risk |
| 5 | carry-flag protocol | 176 T | 20338 Hz | ~−4 B | 0 | reject — invisible invariant, worse than SMC |
| 6 | build-gate | — | — | — | — | reject, see below |

**Build-gating is the worst option, decisively.** The loop period *is* the sample clock, so
DEBUG and release would sit **364 cents (~3.6 semitones) apart** — and we verify sound
exclusively in the DEBUG shape. It also makes `pad_to_cycles` output shape-dependent, which
feeds `Z80_SOUND_SIZE` and the "odd blob = boot address error" trap that crashed both shapes
in wave-4. **DEBUG-gate the assert, never the mechanism.**

**BANK the 30 T; do not spend it on rate.** Raising the rate **re-pitches the whole drum
kit** (`ds_rate` is a reserved zero; the loop period *is* the playback rate), and the HCZ2
kit was fidelity-matched to S3K by ear and by VGM. A second mixed PCM stream costs ~57-70 T
— our known polyphonic-PCM gap — so 30 T pre-paid is worth more than 2.9 semitones of drum
pitch. If the rate is wanted, spend it and re-render the kit in the tools; still zero SMC.

**Hazards checked and cleared** (would have mattered had SMC won): blob is copied once per
boot, warm reset falls through the same path, nothing re-uploads mid-run; Z80 code is
RAM-resident so banking cannot reach it; the patch address is shape-invariant.
**Still real:** the DEBUG state mirror (`sound_debug.emp:47,64`) slurps `SND_STATE_BASE`, so
deleting PHASE's RAM writes would leave a permanently stale byte — misleading, worse than
absent.

**On "checked SMC"** (the mirror-byte + Sigil-construct middle ground): the mirror restores
*state* visibility and catches the corruption class but **not the logic class** — it would
not have caught the `.afterPoll` bug. The Sigil construct's real prize is
`ensure(all variants equal T-states)`, which `cycles()` structurally cannot see today, and
it would have to be built **first**, not promised as a follow-up. Moot now that #1 wins.
