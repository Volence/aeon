# Gate evidence — HBlank schedule local removal

Parcel: `docs/superpowers/plans/2026-08-16-hint-schedule-local-removal.md`
Design: `docs/superpowers/specs/2026-08-16-hint-schedule-local-removal-design.md` (rev 2)

Every gate here is STRUCTURAL — memory reads, derived arithmetic, breakpoints. None of it is a
screenshot. Oracle pixel capture is not usable in this lane (three capture protocols were each
killed by their own determinism control, and `BgAnim_Update` rides the lag-immune `Logic_Tick`, so
cross-build pixel comparison is unsound). Where a number is DERIVED, the derivation is shown; a
gate whose expectation was copied rather than derived is how the last two parcels shipped an
off-by-one.

---

## Task 1 — the 5-word patch table (comptime)

**Guard 10 (`check_rec_layout`) is not vacuous.** Two poison runs, each reverted immediately after:

Poison A — `record_words` returns one word too many (`n = 3` instead of `2`):

```
[Error] raster program: record 2 spans words 5..15 but the next record's arm word is at 14 —
        rec_len and the emitted layout disagree, so the builder would copy a misaligned slice
[Error] raster program: record 3 spans words 14..22 but the next record's arm word is at 21 — ...
```

Poison B — `patch_table` emits `rec_off + 2` (a uniform base error, which is precisely the
counterexample a design reviewer raised against an offset-only cross-check):

```
[Error] raster program: the patch table says record 2 starts at byte 12 but the emitted body puts
        its arm word at byte 10. The builder copies from the TABLE's offset, so this is the
        difference between copying the record and copying a misaligned slice of its neighbour.
```

Poison B is what motivated hardening the guard mid-task: as first written, `check_rec_layout`
recomputed `arm_word_index`/`record_words` and compared them to the emitted image, but never read
what `patch_table` actually emitted — so a wrong table sailed through and only a hand twin could
catch it, for pinned fixtures only. The guard now closes table -> derivation -> image.

ROM CRC is unchanged across the hardening (`bb5ca5aa` before and after), confirming comptime guards
move zero bytes.

---

## Task 2 — `Raster_BuildSchedule` replaces the patcher

**Premise:** with nothing suppressed, the builder must reproduce exactly what the patcher produced.

**Pinned inputs** (not "whatever the camera was doing" — the live buffer carries RUNTIME lines, and
the authored template line 100 is NOT what a free-running camera yields):

| input | value | how |
|---|---|---|
| `Debug_Scene_Freeze` | 1 | skips `Camera_Update`, so a written camera stays put |
| `Camera_Y` | 144 | the boot value, left alone |
| `Effects_World_Y[0]` | 244 | written |
| `Effects_World_Y[1]` | 360 | written |

**Latch readback** (`Effects_Screen_L`, `$FF8AC2`): `0064 00D8` = 100 and 216. Both anchors minus a
camera of 144, confirming the freeze held and the latch ran.

**Derived expectation.** Fire line = screen line - 1, so channel 0 fires at 99 and channel 1 at 215
(216 is inside its 216..223 band, so no clamp). The arm word written at record `i` schedules the gap
that lands record `i+2`, so the SLOT is two records back while the LINE delta is one record back:

- priming record 0's arm = `$8A00 | (99 - 1 - 1)` = `$8A61`
- priming record 1's arm = `$8A00 | (215 - 99 - 1)` = `$8A73`
- records 2 and 3 park (`$8AFF`) — nothing follows them

**Read** (`Raster_Active_Buf` -> `$FF89A2` = `Raster_Buf_A`, 48 bytes):

```
0004 8A61 0000 8A73 0000 8AFF 0002 0000 8C89 0004 C048 0000 0002 0048
8AFF 0001 0002 4002 0010 0000 0043 8AFF FFFF 0000
```

mask `%0100`; priming arms `$8A61` / `$8A73` as derived; record 2 parked with `OP_SET_REG $8C89` +
`OP_PAL_REGION` (command `$C0480000`, count-1 = 2, stage offset 72); record 3 parked with `OP_CRAM`
carrying the VSRAM command `$40020010` and value `$0043`; terminator `$8AFF $FFFF`. Every op word
matches `OJZ_TC_HAND`'s bodies.

Had the design draft's original arithmetic shipped — the two-back SLOT paired with the two-back
LINE — `arm1` would read `$8AD5` here.

**Cross-ROM control.** Master (`77801f78`) built to a scratch worktree, `s4.debug.bin` CRC
`34078a94` (matching the session handoff, so it is genuinely master), same frozen camera, same two
written anchors, same latch readback (`0064 00D8`). Master's patcher writes into `Raster_Buf_B`
(`$FF8A22`) and never swaps; the builder had swapped to `Buf_A`. Contents:

```
master  Buf_B: 00048A6100008A7300008AFF000200008C890004C0480000000200488AFF0001000240020010000000438AFFFFFF0000
branch  Buf_A: 00048A6100008A7300008AFF000200008C890004C0480000000200488AFF0001000240020010000000438AFFFFFF0000
```

**Byte-identical.** This comparison is sound in a way a pixel comparison would not be: the buffer is
a pure function of (template, anchors, camera), and all three are pinned.

### Two behaviours that are NOT identical to master, by design

1. **Suppression is already reachable in play.** `Camera_Y` is clamped to `[0, Camera_Y_Max]`, so
   with OJZ's anchors channel 1 (anchor 314, `band_hi` fire 222) suppresses whenever
   `Camera_Y < 91`, and channel 0 (anchor 224, `band_hi` 213) whenever `Camera_Y < 10`. Master
   clamps DOWN to `band_hi` there. Spawn is 144, so the pinned gate above is unaffected; a
   free-roaming climb will show channel 1's vscroll split vanishing rather than pinning at 223.
   That is Task 4's semantics arriving early for part of the camera range.
2. **`Raster_Active_Buf` alternates A/B every frame** now that the builder swaps, where master held
   Buf_B for the whole lifetime of a patched program. Anything reading the buffer must go through
   `Raster_Active_Buf` rather than assuming Buf_B.

---

## Task 4 — suppression, on both boundaries

One oracle session, `s4.debug.bin`, `Debug_Scene_Freeze = 1`, `Camera_Y = 144` throughout.
`Effects_World_Y[1] = 360` throughout, so channel 1 latches to 216 — INSIDE its 216..223 band — in
every state. That is deliberate: channel 1 is the witness that removing channel 0 does not kill the
tail, which is the property the relative-gap encoding could never provide.

Channel 0's band at the time of this run is 3..214 (`band_hi_fl` 213); Task 6 re-bands it.

| state | `Effects_World_Y[0]` | latched `L` | raster buffer | parallax bands |
|---|---|---|---|---|
| above | 100 | `$FFD4` = -44 | record present, **clamped up** to fire line 2 | split inserted at line 0 |
| mid | 244 | 100 | record present at fire line 99 | split at 100 |
| below | 374 | 230 | **record ABSENT** | **no split** |

**Below-band buffer** (live buffer `$FF8A22`), the parcel's whole point:

```
0004        mask — the base palette is still re-asserted every frame, which IS "dry"
8AD5 0000   priming 0: $8A00 | (215 - 1 - 1) — schedules channel 1 DIRECTLY
8AFF 0000   priming 1: parked
8AFF 0001   channel 1's record, intact
0002 4002 0010 0000 0043      OP_CRAM with the VSRAM command
8AFF FFFF   terminator
```

No `0000 8C89` and no `0004 C048` anywhere: channel 0's record was not emitted. Channel 1 still
fires. Master clamps channel 0 to fire line 213 here and paints screen rows 214-223 wet against a
dry world.

**Above-band buffer:** `0004 | 8A00 0000 | 8AD4 0000 | 8AFF 0002 [0000 8C89][0004 C048 0000 0002
0048] | 8AFF 0001 [...] | 8AFF FFFF`. `arm0 = $8A00` is a gap of 0, landing the record on fire line
2 = its band floor; `arm1 = $8AD4` = 215 - 2 - 1. The record is CLAMPED UP, not suppressed — correct,
because the frame-top ship covers the rows above it. The asymmetry is the design's (§4.3).

**Parallax band tops**, read in the same frames (`Parallax_Shadow_Bands`, 10-byte entries):

| state | tops | anchored shift |
|---|---|---|
| above | 0, **0**, 48, 112, 224 | applied from the split down (`0F00` -> `0200`) |
| mid | 0, 48, **100**, 112, 224 | applied from 100 down |
| below | 0, 48, 112, 224 | **absent** — no anchored split at all |

**Poison control, in the same run.** From the below state, `Effects_World_Y[0]` was written back to
244 and the frame advanced: the raster buffer returned byte-for-byte to the mid-band form
(`8A61`/`8A73`, record present with both ops) and the band table regained its split at 100. Both
assertions flip; neither is vacuous.

**Payload column.** In the above and mid states the record's op words are byte-identical to
`OJZ_TC_HAND`'s bodies (`0000 8C89`, `0004 C048 0000 0002 0048`). The builder copies from
`rec_off`/`rec_len`, so this is the axis that would catch a misaligned copy landing a record on the
right line with the wrong bytes.

**Stride cross-check, free.** `Effects_Offscreen_Entry` ($013158) sits at `Raster_Patch_Tab`
($013140) + 24 = 2 + 10*2 + 2 — the count word, two FIVE-word entries, and the trailer's own count.
A stale 8-byte stride would have landed at +18 and pointed the ship at the wrong words.

---

## Task 6 — the re-band, and the threshold measured to the line

Channel 0 `3..214` -> `3..220`; channel 1 (a vscroll GATE FIXTURE whose position the file already
documented as negotiable) `216..223` -> `222..223`. Budget stays exactly full:
`(220-3+1) + (223-222+1) + 1 = 221`. `check_density` did NOT fire, so the 2-line separation between
band edges (219 and 221 in fire lines) still covers channel 0's modelled 526 cycles.

Re-derived twins: fire lines are now 99 and 221, so `arm1 = $8A00 | (221 - 99 - 1) = $8A79`
(was `$8A77` at fire 219). Read back live, mid-band: `0004 8A61 0000 8A79 0000 ...` — matches.

**The threshold is exact to the line.** Same session, `Camera_Y = 144`, moving only
`Effects_World_Y[0]`:

| `Effects_World_Y[0]` | latched `L` | result |
|---|---|---|
| 364 | **220** (= `band_hi`) | record PRESENT. `arm0 = $8AD9` (217 = 219-1-1), `arm1 = $8A01` (221-219-1) |
| 365 | **221** (one past) | record ABSENT. `arm0 = $8ADB` (219 = 221-1-1) reaches channel 1 directly, priming 1 parked |

One line of anchor movement flips the record in and out, with the surviving record's schedule
re-derived correctly on both sides. Note the 220 case also exercises the tightest legal spacing in
the program — two fires two lines apart — which is the case `check_density` adjudicates.

---

## Task 7 — what the builder costs

Oracle profiler, 100-frame average, both shapes at an identical pinned camera and identical written
anchors, nothing suppressed (the builder's worst case — a suppressed record is work it skips).

| | master | this branch | delta |
|---|---|---|---|
| the proc | `Raster_PatchAll` 372 | `Raster_BuildSchedule` 1228 | **+856** |
| `Raster_VBlank` | 634 | 1490 | +856 (consistent) |
| `VInt_Level` — THE BRACKET | 7499 | 8421 | +922 |

**The bracket is the number that matters**, not the proc: `Raster_VBlank` runs inside the sound-ON
DMA-flag / sound-OFF `z80_stopped` bracket, before `Flush_VDP_Shadow` and every DMA drain, and on
BOTH `VInt_Level` and `VInt_Lag`. +922 cycles is ~1.9 scanlines of an ~18,200-cycle NTSC VBlank
window; the bracket still sits under half of it. As a share of the whole frame, +856 is 0.67% of
128,000.

**Zero HBlank cost**, which was the entire reason this shape was chosen over a per-record NEXT link:
`Raster_HInt` is byte-for-byte unchanged. Ristar's spelling would have spent ~12 cycles of a
~60-cycle per-fire budget forever.

**A counter that must NOT be read as HBlank cost:** oracle's `interrupts.hint` moved 9446 -> 10307
between these runs. That counter INCLUDES VBlank, so it is reporting the same VBlank delta as the
rows above. The handler's code is identical, so its per-fire cost cannot have changed.

Recorded in `tools/effects_budget_model.toml` under `[raster.schedule_build]`. **Honest limitation:**
that is a MEASURED row, not a code-derived one, so `tools/effects_budget_check.py` (which does run on
every build — `build.sh:191`, and reports "8 code-derived rows agree") does not validate it. The file
has no generator by design; measured rows are documentation with provenance. If this number needs to
be enforced rather than recorded, that needs a mechanism this parcel did not build.

### Operational note

A 700-frame `emulator_press` WEDGED the oracle MCP (the documented StopSystem-race deadlock: every
subsequent call, including `emulator_status`, hangs). Recovery is `kill -9` plus relaunch —
`pkill -x` was not enough. Presses in this session were kept to <= 200 frames afterwards with no
recurrence.

---

## Task 9 — the ritual, and what the suite said

**Before the refreeze: 3634 passed / 83 failed.** Every one of the 83 is the byte-drift family a
byte-CHANGING parcel produces — `*_region_matches_reference`, `*_full_file`,
`*_anchor_matches_golden`, `pins_rs_is_current`, `native_full_sonic4_*`, `two_module_*_flip_*`.

Worth recording because it looked alarming and was not: `a_doctored_indexed_mode_changes_the_bytes`
in `raster_negative_probes.rs` failed on its **control** ("the CLEAN build must match the
reference"), not on its doctoring logic. That probe deliberately doctors a register field inside
what used to be `Raster_PatchAll`'s indexed load, so a genuine possibility was that it had been
aimed at a deleted proc and gone vacuous. It had not — its reference window simply moved with the
bytes, which is what the refreeze exists to update.

**The ritual:** `refreeze --freeze hint-schedule-local-removal --ab <this file>`, which captures the
six golden ROMs, re-derives the off-canonical size tables, repins `pins.rs`, and appends the
provenance entry. **Chain length 127.** `RASTER_V_BLANK` moved +0x4 and the engine tail +0x70;
the OJZ section pins moved +0x10 in the debug shape only.

**Four shapes built and BOOTED**, not merely built — the release-shape blackout of 2026-08-14
happened because a gate looked only at a debug build:

| shape | CRC | boot check |
|---|---|---|
| `s4.bin` | `f0e45751` | PC in `Enqueue_Dirty_Buffers`, frame counter advancing |
| `s4.debug.bin` | `3da516e4` | exercised throughout the Task 2/4/6/7 gates above |
| `demo.bin` | `dca06660` | PC in `Read_Controllers` (demo's own symbol table), advancing |
| `demo.debug.bin` | `6c5e1875` | PC in `Read_Controllers`, advancing |

The demo CRCs moved because engine bytes moved; the demo game itself was not touched, and it boots —
which is the standing proof the engine stays game-agnostic.

---

## Re-derived through `ab_runner` (2026-08-17)

The hand-run oracle matrix above was a foreground ritual that nothing would ever re-run. It is now a
committed scene set plus a gate. Harness change: `memory_read` capture in
`oracle/linux-port/harness/ab_runner.py` (oracle `9428a56`) — the runner could hash a region but not
show it, and these gates need to read an ARM WORD, not learn that a hash moved.

Scenes: `aeon/tools/scenes/effects_raster_{mid_band,suppressed,above_screen}.json`.
Gate: `aeon/tools/effects_scene_assert.py`. Derivations: `aeon/tools/scenes/README.md`.

Each scene pins `Debug_Scene_Freeze`, `Camera_Y = 144` and channel 0's anchor, so every expected word
is DERIVABLE before the run rather than read off afterwards. Channel 1 is deliberately not poked: its
preset anchor (314) latches to 170, below its band floor, so it clamps up to fire line 221 in all
three states — which keeps a second hard-coded RAM address out of the fixtures.

**`--selfcheck` passed on all three scenes** (two runs of one ROM, gated captures EQUAL), so the
scenes are deterministic and the byte captures are trustworthy. That is the control the 2026-08-16
work order specified as `--expect-identical`; it already existed under another name.

| scene | latched `L` (ch0, ch1) | live buffer, words 0-4 | derived from |
|---|---|---|---|
| mid_band | 100, 170 | `0004 8A61 0000 8A79 0000` | `$8A00\|(99-1-1)`, `$8A00\|(221-99-1)` |
| suppressed | 230, 170 | `0004 8ADB 0000 8AFF 0000` | `$8A00\|(221-1-1)`, park |
| above_screen | -44, 170 | `0004 8A00 0000 8ADA 0000` | `$8A00\|(2-1-1)`, `$8A00\|(221-2-1)` |

**Nine expectations, all computed from the arm formula BEFORE the run, all confirmed.** The
suppressed buffer carries no `$8C89` and no `$C048` — channel 0's record is absent — while channel
1's record and the terminator follow immediately; the other two carry both. The full suppressed
program:

```
0004 8ADB 0000 8AFF 0000 8AFF 0001 0002 4002 0010 0000 0043 8AFF FFFF
```

**The gate fails when it should.** Mid-band expectations asserted against the suppressed sidecar:

```
FAIL: word 1: expected 0x8a61, got 0x8adb
FAIL: 0x8c89 must be PRESENT but does not appear
```

It also exits 2 — not 0 — when asked to assert nothing, and when the scene did not capture the
regions it reads. A gate that asserted nothing must not report OK.

### What this deliberately did NOT build, and why

**Pixels are not gateable on oracle, by construction**, so no framediff instrument was written.
`ab_runner`'s own docstring root-causes it: the VDP renders on a worker thread
(`S315_5313::RenderThread`) draining an async queue, and the framebuffer the GUI copies is not
anchored to the deterministic `ExecuteSystemStep` count. Measured independently while surveying —
three identical `oracle_cli --frames-dir` runs of `s4.debug.bin` agreed on 26 of 28 frames and
differed on frames 2 and 5 by **8.9%** and **25.0%** of pixels (rows 134-154 and 98-153), with frame
tokens advancing by exactly 1 in all three runs, so the frames were correctly ALIGNED and the content
differed. The named fix is emulator-side (`OpScreenshot` waits for `_pendingRenderOperationCount == 0`,
or renders synchronously from committed VDP state); a framediff built before it would be a careful
instrument pointed at a nondeterministic source.

### A harness finding worth more than the task that produced it

`load_scene` silently accepted UNRECOGNISED capture keys. That is why `memory_read` produced no error
before it was implemented — and it means a scene with a typo'd key captures nothing while the run
still reports a confident green verdict. Exactly the failure this parcel exists to remove. Closed
with an allow-list plus a test that a typo now raises.

### A sigil finding worth booking separately

`lea -RASTER_BUF_SIZE(a2), a2` — a NEGATED NAMED CONSTANT in a displacement — is DROPPED by sigil's
contract-closure walk (reported as `Raster_BuildSchedule: 2` dropped instructions, gate-fatal).
Bisected: `-128` resolves, `-RASTER_BUF_SIZE` does not. The instruction lowers correctly; it is the
ANALYSIS that goes blind, which makes this a gate-blindness bug rather than a codegen one. Worked
around with `suba.w #RASTER_BUF_SIZE, a2`, this tree's existing idiom (`plane_buffer.emp:194`,
`section.emp:324`, `tile_cache.emp:453`).
