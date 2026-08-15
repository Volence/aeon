# Task 1 gap closure — the four testing gaps on the blanket-restore parcel

Closes the four gaps the 2026-08-14 work order named. All emulator work in the
controlling session (oracle MCP deadlocks from subagents). Every scratch edit reverted
and the revert PROVEN BY CRC, not by eye.

---

## 1a — the dense raster fixtures RENDER (was: verified only by reading emitted bytes)

Both fixtures byte-match the shapes read out of the ROM last session, and both were
rendered and measured rather than inspected.

**`OJZ_TestRamp`** (OJZ act1 section 0 — on screen at spawn), ROM `$12F74`:
```
0000 8A6D 0000 8A00 0000 8A00 0001 0008 4002 0010 0060 00000000 00008000 8AFF FFFF
```
Runtime state read at the dense body: `Raster_Dense_Kind` = 1 (ramp), `Raster_Dense_Cmd`
= `$40020010` (VSRAM byte 2 = plane B), `Raster_Ramp_Step` = `$00008000` = 0.5 px/line.

A/B against `Raster_Program_None` installed at runtime through the engine's own
`Raster_Pending` path (no rebuild): **rows 0-112 pixel-identical, rows 113-223 all
differ** (17,420 px). Measured scroll advances **+1 px every 2 rows** — the 16.16
fractional half is doing real work. Accumulator walked line by line at a breakpoint on
`$engine.effects.raster$Raster_HInt$ramp_body`: `0.0 -> 0.5 -> ... ->` exactly
`$00300000` = **48.0** after 96 lines, zero drift, then frozen for rows 208-223.

The run starts at row 113, not 112, and that is CORRECT: the body adds *then* emits
(`move.l Acc,d1 / add.l Step,d1 / move.l d1,Acc / swap`), so line 112 emits `0.5 -> 0`,
which equals the base scroll.

**`OJZ_TestGradient`** (section 2), ROM `$12F3A`:
```
0004 8A5D 0000 8A00 0000 8A00 0001 0006 C048 0000 0060 0001 2CFA 8AFF FFFF
```
Installed via the same runtime path so the measurement did not depend on platforming to
section 2 (section CROSSING is separately proven — walking right installed section 1's
`$12C52` on the way). Control needed `Palette_Dirty |= $0F` forced once, because
`Raster_Program_None` has `pal_dirty_mask` 0 and therefore leaves the gradient's last
written colours stuck — a control that does not restore is not a control.

Recovered level per scanline from the pixels (oracle's 8-bit scale is level*34):

| rows | level | authored `grad_word` |
|---|---|---|
| 96-107 | 0 | lines 0-11 |
| 108-119 | 1 | lines 12-23 |
| 120-131 | 2 | |
| 132-143 | 3 | |
| 144-155 | 4 | |
| 156-167 | 5 | |
| 168-179 | 6 | |
| 180-191 | 7 | lines 84-95 |
| 192-223 | 7 held | post-run, until VBlank restores |

First differing row exactly 96, boundaries exactly on 96+12k, 8 distinct monotonic
levels. **All three channel mixes present on every row** — `(0,0,B)`, `(0,G,B)`,
`(R,0,B)` — so the 3-word stream is in phase; a one-word desync scrambles them, which is
the property the fixture was designed to expose. CRAM lands on line N while the VSRAM
ramp lands on N+1, matching the recorded finding.

**No dense-tier hand pin was added.** The work order said to add one "if they render
correctly". On inspection that would duplicate what `raster_gradient_program` /
`raster_ramp_program` already assert at comptime, and the pin idiom's value
(`OJZ_VSRAM_HAND`) is pinning a HAND-DERIVED twin against the encoder — which for a
288-word computed stream means re-implementing `grad_word` in the pin, i.e. pinning the
encoder against itself. The render measurement above is the stronger gate and it is now
recorded. Flagged rather than silently skipped.

---

## 1b — the three `$0F` IPL asserts are LIVE, not vacuous

Each site negative-probed individually and reverted. All three trip to the MD Debugger
naming themselves, and each names a real caller — so each site is REACHED as well as
armed. Exact text:

| site | probe | crash-screen text |
|---|---|---|
| `engine/level/section.emp` | `move.w #$2700,sr` -> `#$2300` at the excursion | `> assert.w d0,hs,#$0600` · `Got: 0300` · `Offset: 006B9E engine.section.raise` · `Caller: 006DA6 Section_UpdateColumns+E` |
| `engine/level/plane_buffer.emp` | scratch `move.w #$2300,sr` before the check | `> assert.w d0,hs,#$0600` · `Got: 0300` · `Offset: 00567A engine.plane_buffer.raise` · `Caller: 002340 VInt_Level+44` |
| `engine/level/bg.emp` | scratch `move.w #$2300,sr` before the check | `> assert.w d0,hs,#$0600` · `Got: 0300` · `Offset: 008EB2 engine.bg.raise` · `Caller: 001764 GameState_OJZScroll_Init.copy_ojz+16` |

Reverted: `s4.debug.bin` back to `crc=3cffc29b`, byte-identical to the merged build.

---

## 1c — `Set_VDP_Reg` exercised, both arms

Zero callers, so neither its indexed write nor its bound assert had ever executed.

- **Valid index.** Scratch `Set_VDP_Reg(#$0C, #$00)` from boot -> framebuffer becomes
  **256x224** (H40 -> H32). The indexed shadow write reaches hardware through the
  unconditional flush, which is the whole contract of the proc.
  Reg `$0C` was used, NOT the work order's suggested `$07` backdrop: the backdrop is
  invisible in OJZ because plane B covers the screen opaquely (measured this session
  while diagnosing the release blackout — a `$07` probe there returned no signal and was
  discarded as an instrument).
- **Out of range.** `Set_VDP_Reg(#$13, ...)` ->
  `> assert.w d0,ls,#$12` · `Got: 0013` · `Offset: 001CC8 engine.vdp_init.raise` ·
  `Caller: 000390 EntryPoint.region_done+58`.

Reverted; all four shapes rebuilt to the merged CRCs.

---

## 1d — boot `demo` and the release shape

This one did not pass. It found that the RELEASE shape of BOTH games rendered nothing at
all, a pre-existing defect; see `docs/benchmarks/boot-cursor-seam/AB-EVIDENCE.md` and the
`BUGS.md` entry. Fixed in aeon `f2adf85c` / sigil `7e1b70dd`, chain 116.

Post-fix, all four shapes boot correctly:

| shape | crc | result |
|---|---|---|
| `s4.bin` | `a6efe203` | OJZ renders — art, palette, parallax, Sonic |
| `s4.debug.bin` | `3cffc29b` | renders |
| `demo.bin` | `8c6abbfe` | white 16x16 box on dark blue (the spec) |
| `demo.debug.bin` | `fdda99a7` | white 16x16 box on dark blue |
