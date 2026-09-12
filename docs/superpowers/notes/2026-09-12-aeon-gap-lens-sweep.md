# Aeon gap lens sweep, 2026-09-12: the two holes the 2026-09-06 panels left

**Review pin: aeon `9fe9ee91`** (origin/master at dispatch). Each seat ran read-only in its own worktree, detached at the
pin, and was clean at the start. No fixes were made during the sweep. The aeon overseer adjudicated after the seats returned.

## Why this sweep, and what it is NOT

The queue row `LENS-SWEEP-COVERAGE` said "the sound driver, the build tools and the engine's system layer were never
swept". **That was stale.** `docs/superpowers/notes/2026-09-06-aeon-lens-sweep.md` ran the full Roster A panel with the ×2
doubling over `engine/**/*.emp` + `games/**/*.emp` (76,111 lines, sound and system included), and
`2026-09-06-aeon-tools-lens-sweep.md` gave `tools/` its first review (Roster B seats T1/T2/T3). The row came from a
2026-08-13 coverage map that predates both. Those two packets name exactly two holes themselves, and this sweep charters
only those:

1. **The Z80 comment surface** — "The Z80 comment surface was not swept at all" (engine packet, "Sampled, not swept").
   Seat **A2 (comment TRUTH)**. *Section below, pending the seat's return.*
2. **The OJZ level bakers** — T1's parent seat "was killed by the account session limit", recorded as
   "UNEXAMINED, NOT CLEARED" and "the single largest gap" (tools packet). Seat **T1 (generator correctness)**.

**Still UNEXAMINED, NOT CLEARED after this sweep:** the engine packet's wider comment population (1,846
`always`/`never`/`cannot`/`guaranteed` universals, sampled ~35 of 217 `the only`-class), the tools packet's 11 of 18
no-assertion test functions and its 14 unexecuted listing gates, `effects_gen.py`'s `render_module`/`generate` (~1,500
of 4,910 lines, see T1's "not covered"), and everything else not named above. **This sweep is not a blessing of any of it.**

Step 0 (standing findings): the 2026-09-06 packets' own rows are tracked in `docs/DEFERRED_WORK.md` and the
LENS-FIX-RESIDUE row; neither seat here re-litigates them. T1 was told to honour the 09-06 T1 "checked and found
CORRECT" results and the collision/art half's scope.

---

## T1 — the OJZ bakers (generator correctness)

**Corpus, derived by the seat from the invocation chain** (an AST walk of local imports from each tool
`tools/regenerate-level.sh` runs, plus a `subprocess` grep; the walker is `deps_t1.py` in the fixtures directory):
`regenerate-level.sh` 245, `ojz_strip_gen.py` 2296, `ojz_common.py` 421, `tile_dedupe.py` 197, `ojz_block_gen.py` 840,
`ojz_entity_gen.py` 610, `inject_editor_bg.py` 1431, `verify_level_bin.py` 658 (all read in full); `s4lz.py` 924,
`effects_gen.py` 4910, `donor_provenance.py` 222, `suite_paths.py` 387, `level_staleness.py` 414 (partial, stated per
file in the seat's report).

**Headline: no convention mismatch between what the bakers write and what the engine reads, in today's shipped bytes.
Three SILENT failure paths, each demonstrated on a one-file fixture, where a bad editor input produces a green re-bake,
a green `verify_level_bin`, and wrong level data.** All three are latent: they need a malformed input that today's tree
does not hold.

Every fixture ran in a `cp -a` copy of the pinned tree; the only edit to a copy was `regenerate-level.sh`'s `cd` line so a
`.git`-less copy resolves its root. The scripts, as the seat ran them, are in
`2026-09-12-gap-lens-sweep-fixtures/` beside this file (`t1_fx_coll.sh` D1/D2, `t1_fx_tail.sh` C, `t1_fx_trunc.sh` A,
`t1_fx_blk.sh` B, `t1_build.sh`, `t1_measure.py`, `t1_cmp.py`).

**Citation check by the controller:** every line cited under F1, F2, F3, F4 (engine half) and F5 below was re-read at
`9fe9ee91` and says what the finding says. F6's `verify_local_maps` range and every measured count (1038/1042 cells,
12,164 words, 116 blank-priority words, 67/256 blocks) are the SEAT's measurements and were not re-run.

### F1 — HIGH, latent: a wrong-sized collision file silently deletes the act's floor
`tools/ojz_strip_gen.py`, `apply_editor_collision_overlay`: `if len(a) != expect:` prints a `WARNING … ignoring editor
collision for sec N` and `return grids`, i.e. the all-air baseline. Fixture D1 (`section_0.collattr.bin` cut by 2 bytes):
re-bake exit 0 with `interned 0/255`, `verify_level_bin: OK`, section 0 plane A 1038 → 0 non-air cells and plane B
1042 → 0, all five ROM collision tables changed. Section 0 is the only section with authored collision, so the act ships
with no solid ground. **Why every gate passes:** `verify_level_bin` has no collision-fidelity check, and an all-air table
still differs from `base/`, so `verify_collision_is_interned` is satisfied.
Proposed: refuse a wrong size instead of warning; add a collision-fidelity check to `verify_level_bin`.

### F2 — HIGH, latent: a missing section file ships a short local-map table and the engine reads a NULL map
`ojz_strip_gen.py`, `generate()`: a missing `section_N.tiles.bin` is `WARNING … not found, skipping` then `continue`.
`emit_section_local_maps` refuses only a NON-CONTIGUOUS id set (`missing = [i for i in range(n) …]` with
`n = max(by_id)+1`), so a missing LAST section passes. `ojz_block_gen.py` hardcodes `NUM_SECTIONS = 9` and re-bakes
section 8 from the previous bake's strips left on disk. Fixture C (delete `section_8.tiles.bin`): exit 0,
`sec_local_maps.emp` emitted as `[*u8; 8]`, `sec8_blocks.bin` rewritten from stale `sec8_strips_a.bin`,
`verify_level_bin: OK (8 section(s))`; control then fixture both linked under `FAST=1 DEBUG=1 ./build.sh`. In the ROM,
`OJZ_Sec_LocalMaps` entry 8 reads the first long of the next table (`OJZ_Palette`), `0x0` only because palette colour 0
is black. `TileCache_DecompressBlock` publishes that as section 8's map: the NULL-map hazard `tile_cache.emp`'s own comment
describes. **RUNTIME-TAG** for the in-game consequence.
Proposed: require every `section_N.tiles.bin` in editor mode; emit the table length as a constant pinned against
`GRID_W*GRID_H`; delete leftover per-section outputs.

### F3 — HIGH, latent: a short tileset bakes blank tiles, and the gate is blind by the same zero-fill (T1-2's shape)
`ojz_strip_gen.py`, `collect_referenced_tiles`: an index past the blob appends `bytes(TILE_SIZE)  # missing → zero tile`
(also `emit_bg_tile_blob`). `verify_level_bin._tile_pixels` returns `bytes(TILE_SIZE)` past the end, "matching what the
generator's collect_referenced_tiles substitutes", so the fidelity proof compares padding to padding.
`editor_data_available` rejects only a zero-byte tileset. Fixture A (tileset 919 → 700 tiles, editor references up to
732): exit 0, `editor bake fidelity OK (9 section(s), 589824 nametable words)`, 12,164 words (30 distinct tiles) baked
blank with no diagnostic. **This is the 09-06 T1-2 defect (`dedup_art.py`) recurring in a second generator**, the proof
reproducing the generator's fallback instead of checking against the source.
Proposed: refuse any index ≥ the tileset's tile count, in the generator and in the gate.

### F4 — MEDIUM, LIVE bytes, consequence needs the emulator: blank cells lose attribute bits the baker preserves
`engine/level/page_cache.emp`, `.pw_new_blank`: `clr.w (a1)` writes `$0000` for any word whose tile index is 0, while
`verify_level_bin` asserts `strips_a` keeps priority and palette bits. The seat counted 116 blank words carrying the
priority bit (20/19/10/15/10/11/14/7/10 across sections 0-8). Shadow/highlight is active in section 1 below line 120 and
in section 7's water band, where the plane priority of a cell decides shadowing. **The claim that a blank cell's priority
still affects shadowing is the seat's reading of the hardware, not a measurement.** **RUNTIME-TAG:** set priority on a
blank cell in section 1 below line 120 and compare pixels against the cleared case. If it matters, the fix is either the
engine keeping attributes on blank or the baker stripping them, and which is an authoring question.

**MEASURED 2026-09-12 (branch `measure/blank-priority-0912`, `tools/blank_priority_probe.py`, note
`2026-09-12-blank-priority-measurement.md`; ROM `9ce1c2ff`, headless oracle-rs): CONSEQUENCE, in section 1 ONLY.**
The 116 re-derived independently (masks from `engine/system/constants.emp`), same 20/19/10/15/10/11/14/7/10 split.
VDP reg `$0C` read at every line in all nine sections: shadow/highlight is on in **section 1, lines 121-223, and nowhere
else**. **F4 was wrong about section 7:** its water band is a palette swap (`sh: 0` since 2026-09-05). Premise test on a
section-1 blank cell: `$0000` → `$8000` changed 25 px, every one an exact shadow-to-normal step; `$7800` (palette + flips,
no priority) changed 0 px; the same toggle above line 120 changed 0 px; two unmodified captures differed by 0 px.
In place, six authored section-1 words restored to `$C000` changed 75 px; 15 section-0/7 words restored changed 0 px.
**So 19 of the 116 words are visible, all in section 1, whose shadow/highlight comes from `OJZ_TestRaster`, the Effects P1
gate fixture, not authored content.** If the owner's `SECTION-EFFECTS-VISUAL` card goes the recommended way (test effects
out of sections 1 and 2), F4 has no visible consequence in shipped content today; it stays a latent authoring hazard
for the first authored shadow band. **Instrument limit, stated so it is not over-read:** oracle's own S/H rule
(`sh_state` in its `render.rs`) already builds in "a transparent cell keeps its tile's priority", so this measures the
engine's bytes under that rule, not the hardware. Side observation, the measuring agent's reading and not a measurement:
section 0 binds `OJZ_TwoChannel` ch0 with `sh: 1`, yet S/H never switched on there at three cameras; its latched line read
`$7FFF − Camera_Y`, which lands far below the screen. Booked as a question, not a defect.

### F5 — MEDIUM, loud: the preflight's "nothing is written before it can fail" does not hold for generate()'s refusals
`regenerate-level.sh` runs `ojz_strip_gen.py preflight`, then `import_sk_collision.py` (which overwrites the ROM-consumed
collision tables), and only then `generate()`, whose refusals all fire after that write. Fixture D2
(`section_0.collattrb.bin` cut by 2 bytes): the bad plane-B file is silently replaced by a mirror of plane A
(`# malformed path B → mirror A`); here it was refused only because section 0 has crossover marks that trip R2. The
re-bake exited 1 leaving the four tables byte-identical to raw `base/` and the stamp unrewritten, which the next build
catches loudly (`verify_collision_is_interned` + staleness). On a section without marks the mirror would be silent: a
code read, not a measurement.
Proposed: run `import_sk_collision` after `generate()` or restore on failure; refuse a bad `collattrb` instead of mirroring.

### F6 — LOW, latent (T2's lane): the gate checks intermediate files, not the ROM-consumed blocks
Nothing in the ROM embeds `strips_a`, and `verify_local_maps` checks only the dictionary region of `secN_blocks.bin`.
Fixture B (`sec5_blocks.bin` copied over `sec0_blocks.bin`, both 768-byte dictionaries): `verify_level_bin` exit 0 with
67 of 256 section-0 blocks decoding wrong; reachable only through a partial commit. **For the pin itself the seat closed
it:** decoding all 2,304 blocks gives 0 mismatches against `strips_a`.

### Minor (seat's, unverified here)
`inject_editor_bg.py` keeps a layout word of exactly 0 as VRAM tile 0 though BG slot 0 holds a band tile (no such words
today). The collision overlay samples only each 16-px cell's top tile row (0 cells differ today; whether Aurora can write
the two rows differently is a question for Aurora). The pool summary prints the retired `(ceiling 768)`.

### Checked and found CORRECT (re-derived by the seat)
Reproducibility: `--no-cache`, cold and warm re-bakes byte-identical to each other and to the committed tree across 203
files (bar `DONOR_PROVENANCE.json`'s aeon record, from the `.git`-less copy). Nametable word layout, flip
canonicalisation, the local map format, the block blob index and inner layout, S4LZ v3 tokens and end marker, the ZX0
page wrapper, `PageManifest`, entity/ring data bits and terminators, the injected BG layout, determinism (sorted
`listdir`, sets for membership only, no RNG), and a grid change failing loudly.

### Not covered by T1
`effects_gen.py` `render_module`/`generate`; engine-vs-Python decoder agreement (RUNTIME-TAG, `compression_selftest.emp`);
F2/F4 runtime consequences; fixture C in the canonical and release shapes; the STRESS path; the salvador C source;
generator source as a staleness input (declared by design in `level_staleness.py`).

### Triage (owner-gated per the protocol; nothing here is fixed)
- **Byte-neutral tool parcels** (refusals change no baked bytes on today's inputs): F1, F2, F3, F5, F6. They can land
  as their own parcels, each with a red-first proof on the seat's fixture. F3 should be fixed in the generator and the gate
  together, or the gate stays blind.
- **Measure-first:** F4, in the emulator, before choosing which side changes.
- **Open question for Aurora:** whether a collision cell's two tile rows can differ.

---

## A2 — the Z80 comment surface (comment TRUTH)

**Corpus, found by `cpu: z80` rather than by names:** `z80_sound_driver.emp` 1722, `sound_sequencer.emp` 2093,
`sound_sfx.emp` 1888, `sound_fm.emp` 1239, `sound_psg.emp` 743, `dac_sample_tab.emp` 221, `sound_tables_z80.emp` 177,
`z80_init.emp` 142, `seq_opcode_tab.emp` 85 (all `engine/sound/` bar `engine/system/z80_init.emp`, all read in full);
plus the 68k files that make claims about the Z80: `sound_api.emp`, `sound_constants.emp`, `engine/debug/sound_debug.emp`,
`engine/z80_bus.emp`, `engine/irq.emp`, `games/sonic4/debug/game_debug.emp` in full, and windows of `vblank`, `controllers`,
`section`, `parallax`, `game_loop`, `boot`. **UNEXAMINED, NOT CLEARED:** the `cpu: z80` DATA modules under
`games/sonic4/data/sound/**` (`sfx_blob_win_tab.emp`, `movingtrucks_pitchtable.emp`, `soundbankhead.emp`, `mt_bank.emp`),
`engine/ram.emp`'s sound reservations, and the parts of the windowed files outside their windows.

**Headline: six load-bearing wrong comments**, i.e. comments that would license a bug in the next change that trusts
them, and all six cited lines were re-read by the controller at `9fe9ee91` and say what the finding says. Eleven more are
wrong but inert, and a long tail of stale counts. Two need the emulator. **No finding asserts a live defect in shipped
behaviour except A2-9, whose consequence is the runtime item.** Line numbers below are at the pin and will drift; the
symbol beside each is the durable handle.

### Step 0 — the standing Z80 comment findings, re-verified
| booking | verdict | evidence (seat's) |
|---|---|---|
| F3, the `dc.l SfxTable` third | STILL OPEN, size changed | `sfx_bank.emp`'s `table SfxTable (cell: *u8, key: $33..=$BB)` in a `cpu: m68000` section: 137 cells, **548 B** (was 540 at 135). No reader in `engine/` or `games/`; the Z80 reads `SfxBlobWinTab`. That the bytes are emitted needs the listing. |
| F3, duplicate `sfx_NN_patches` banks | CONFIRMED, **smaller than booked** | by md5, $33 = $34 = $B9 and $BA = $BB, 32 B each: three redundant copies, **96 B**, not ~208. $36, $42, $62, $7E are zero-length. |
| F4, the remaining a0 quarter | STILL OPEN, **ergonomics only** | every contract is TRUE: `Sound_Ping`/`PlaySample`/`StopMusic` `lea` their slot into a0 and declare `clobbers(a0)`; `Sound_PlayRing` `preserves(a0)` via `Sound_PlaySFX`'s `movem.l d1/a0`. Eleven more `Sound_*` procs clobber a0, also truthfully. |
| "once the gates are removed" | **STALE: close it** | `git log -S` puts the phrase's last change at `85ae87cf`, which deleted the `.asm` twins; no surviving form in the corpus. |

### Load-bearing wrong (controller-verified at the pin)
- **A2-1 `Snd_LoadSong`** (`z80_sound_driver.emp`, the `call Sfx_StopAll` site): "Touches only RAM (preserves de=$4001)".
  `Sfx_StopAll` is `clobbers(af, bc, de, hl, ix)` and returns de = 68. The same file warns elsewhere that moving that call
  below `ld de` sends every DAC write to Z80 RAM $0044. Latent: aeon's build does not check a Z80 caller's reliance on a
  register across a call (the 09-06 C2b-S1 finding).
- **A2-2 the driver's import header**: "SndDrv_IdleTick relies on Sequencer_Frame preserving iy (… iy untouched)".
  `Sequencer_Frame` is `clobbers(af, bc, de, hl, ix, iy)`, and its own contract says why (the `jp Sfx_Frame` tail). The
  same file contradicts itself in two other places. Latent, same reason. The same sentence's "+$7E" is also stale (A2-15).
- **A2-3 `sound_sfx.emp`, the FM6 note**: "Opening FM6 to SFX for DAC-off songs is a one-byte table edit". `SfxRouteSlot`'s
  CHROUTE_FM6 cell is `SFX_SLOT_NONE`, and `.pref_hi_ok` sends an unmapped route straight to `.substitute`; the seat reads
  tiers (b)/(c) as scanning only the 7 slots, none owning FM6. So after the one edit an FM6-aimed SFX lands on FM3-5 or
  drops, and FM6 is never stolen. Opening FM6 needs an eighth `SfxChannel` and both route maps.
- **A2-5 `sound_constants.emp`, the PSG port note**: "PSG writes never touch $4000-$4003 or `de`". `Psg_NoteOn` does
  `ld de, PsgDivisorTableZ` and declares it. Twin of the booked F4 PSG item, fixed in `sound_psg.emp`'s header and not here.
- **A2-6 `sound_sequencer.emp`, the `MEV_EXT` const**: "authority: sound_constants.emp, where it is pinned inside the
  $E0-$FF coordination block". `grep MEV_EXT sound_constants.emp` finds three `const` lines and no `ensure`. The comment
  claims a guard that does not exist (the 09-06 B2b-4 gap is still open).
- **A2-9 `Snd_LoadSong`'s header**: "the loader does not stop the DAC, the ring keeps draining". The body writes $2B = $00
  (DAC mode OFF) and clears `SND_STAT_DAC_ACTIVE` unconditionally. The seat's reading: the stream keeps consuming but is
  silent, so an in-flight drum is cut at the song load until the new song's first $E2, and when that sample reaches `.stop`
  it tests the NEW song's `SND_FM6_ADAPTIVE` and can re-key FM6 mid-note. **RUNTIME-TAG** (listen, or capture the YM
  writes across a mid-drum `Sound_PlayMusic`).

### Wrong, latent or inert (the seat's; not re-verified by the controller)
- **A2-4** `Sound_SetTempo` documents 0 as "full speed", but a posted 0 means idle and the Z80 skips it (range 1..$FE per
  the driver). A silent no-op for a caller passing 0; no callers today.
- **A2-7** the YM-spacing coverage ledger in `sound_fm.emp` miscounts (9 vs 10 rows, 7 vs 8 direct), omits three guarded
  sites, and omits three UNGUARDED direct address-to-data pairs (`Snd_LoadSong` $2B 17 T and $B6 24 T, `Snd_TimerA_Rearm`
  $27 20 T) while presenting spacing as fully checked. All three pass the 8 T floor today.
- **A2-8** `Snd_StartSample`'s "TWO CALL CONTEXTS" (and `sound_api.emp`'s "in the VBlank ISR, DAC paused") are four: the
  Timer-A tick also services the mailbox mid-sample, and $E2 also arrives from `SndDrv_IdleTick`.
- **A2-10** `sound_fm.emp`'s "single-threaded — only Sequencer_Frame reaches the FM writer" is false (the resume path
  reaches `Fm_PatchLoad`/`Fm_SetVolume` from the mailbox); still safe, for a reason the comment does not give (the ISR can
  fire only in `SndDrv_Idle`'s `ei` window).
- **A2-11** `sound_api.emp`'s "at most one driver frame old" status mirrors: `SND_STAT_FADE_BUSY` stays 1 after a
  `Sound_StopMusic` mid-fade. `Sound_IsFading` has no callers today. **RUNTIME-TAG.**
- **A2-12** `sound_constants.emp` names two post-divergence struct aliases; there is a third (`sc_macro_active` over
  `sx_patch_base`'s low byte), and `sfx_transcode.py` refuses only PSGNOISE and DETUNE. The same comment's "no SFX stream
  contains MEV_PSGNOISE" has been untrue since B5.
- **A2-13** `sound_psg.emp` "vol > $7F -> atten 0": $80 gives $0F (silent), $FF gives 0. Volumes wrap, not clamp.
- **A2-14** `sound_sfx.emp` "MEASURED length guards. These fold span(…)": no guard follows.
- **A2-15** the debug-shape growth is 17 blocks / **$82 (130 B)**, not "+$7E / 16 blocks", derived two ways (byte count
  38+84+4+4, and LS-12's blob lengths 6293−6163 = 6306−6176 = 130). Needs the listing to confirm.
- **A2-16** `sound_psg.emp` "route 5/6/7 -> hw ch 0/1/2" is 6/7/8, the off-by-one its own header records fixing.
- **A2-17** the stale-count tail, too long for this packet: in the seat's report as returned to the controller, summarised
  in the booking row. It covers counts and names in all nine files, a `.drain_pad` cycle figure (52 T, not 44), deleted
  names (`Fm_ReparkDac`, `engine.inc`, `Snd_TimerA_Program`, `YM_DATA_TO_ADDR_MIN_T`), and `section.emp`'s "costs no
  sound" for a poke storm the seat estimates at ~50 ms against a ~10.9 ms ring lead (**RUNTIME-TAG**).
- **Uncertain, sigil's to answer:** four contracts' `carry:` labels read opposite to the documented polarity
  (`Snd_DacLookup carry: ok`, `Sfx_MusicChanPtr` / `*VolEnv_Resolve carry: found`, where carry SET means failure).

### Checked and found TRUE (re-derived by the seat)
The streaming loop's cycle balance (FILL 195 T, DRAIN 109+86, DRAINING 194; 18,356 Hz); the $2A park on every path the ISR
can reach (a suspected race refuted); `SndDrv_SetBank`, the ctrl-command decode, the fade terminal map and rate table; the
mailbox mirrors against the authority; struct offsets (SfxChannel 68, SeqChannel 60, FmPatch 32, SfxHeader 8); table sizes;
`Sound_PostByte`'s `preserves(sr)`; `Sound_PlayMusic`'s callers at IPL 3; the z80_bus census of 22 brackets + 1 hand hold;
09-06 C2b-V3 and the parallax "one hold" claim confirmed fixed.

### Triage
- **Byte-neutral comment parcel** (may land immediately per the protocol, with the four-shape evidence proving zero
  bytes): A2-1, 2, 3, 5, 8, 10, 12 (comment half), 13, 14, 15, 16, the A2-17 tail, and A2-4's doc line.
- **A zero-byte guard, with red-first proof:** A2-6 (pin `MEV_EXT` inside the $E0-$FF block with an `ensure`, or strike
  the claim). A2-7's three unguarded pairs could join the ledger's existing guard the same way.
- **Runtime first:** A2-9, A2-11, the A2-17 poke-storm item.
- **Byte-changing (own parcels):** F3's 548 B dead `SfxTable` and 96 B duplicate patch banks.
- **Sigil question:** the `carry:` label polarity.
