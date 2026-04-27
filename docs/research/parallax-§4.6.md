# §4.6 Parallax — Research Notes (per-task appendix)

Spec: `docs/superpowers/specs/2026-04-27-section-46-parallax-design.md`
Plan: `docs/superpowers/plans/2026-04-27-section-46-parallax.md`

This document accumulates research findings during plan execution. Each task
appends a section. If research changes implementation, update the spec/plan
inline before proceeding.

---

## Pre-flight (before T1)

### #9 VDP shadow DMA-path audit

Per `docs/superpowers/specs/2026-04-27-vdp-shadow-dma-audit-design.md`. Findings (commit `675eea6`):

- **Zero defects.** No code changes required.
- Six direct VDP writes found via `grep -rEn 'move\.w\s+#\$8[0-9A-Fa-f]|#\$9[0-2][0-9A-Fa-f]' engine/`, all targeting register `$0F` (autoincrement). All transient pre-DMA setup, all legitimate bypasses of the shadow.
- DMA queue (`engine/dma_queue.asm`) does NOT touch register `$01` — DMA enable is set once at boot via `setVDPReg` and never toggled. Ristar's per-DMA-block save/restore pattern is reactive insurance we don't currently need.
- HBlank dispatcher + null handler clean; no per-section HInt handlers exist yet.
- Documented direct-write conventions in `docs/ENGINE_ARCHITECTURE.md` §0.4 and `CODING_CONVENTIONS.md` §3.1 rule 5.

### T2 macro spike — AS Macro Assembler fraction handling

Pre-execution feasibility spike (artifacts since deleted; findings preserved here and in commit `55f75b7`).

**Test results:**

1. **`dc.b 1/8` emits `00`** — AS evaluates `1/8` as integer division at expression-time. Hypothesis A confirmed.
2. **`function f(p,q, p*256/q)` with `f(1,8)` works correctly** — multiplication-first ordering preserves the fraction. Emits `20` ($20 = 32 = 256/8) and `E0` (224) for `f(1,8)` and `f(7,8)`.
3. **Macro arg `1/8` is collapsed to 0** — `test_frac 1/8` where the macro body uses `frac*256` emits `00` (because AS substitutes the literal text `1/8` and evaluates as `(1/8)*256 = 0*256 = 0`).
4. **Named-equate fractions work cleanly** — pre-defining `FACTOR_1_8 equ packed(3,15,0)` ($F3) etc., then setting `FACTOR_A := FACTOR_1` and `FACTOR_B := FACTOR_1_8` and invoking a macro that reads them via globals, emits exactly the expected encoding bytes (00 0F 00, 03 0F 00).
5. **`function`s cannot emit `fatal`** — they're pure expression evaluators. Validation must live in the consuming `band` macro's `if` checks.

**Decision (committed in `55f75b7`):**

- `packed(s1,s2,op)` function for build-time encoding
- 15 pre-defined `FACTOR_*` named equates covering the supported set (FACTOR_LOCKED, FACTOR_1, FACTOR_1_2, FACTOR_1_4, FACTOR_1_8, FACTOR_1_16, FACTOR_1_32, FACTOR_3_4, FACTOR_3_8, FACTOR_3_16, FACTOR_5_8, FACTOR_5_16, FACTOR_7_8, FACTOR_7_16, FACTOR_15_16)
- `band` macro takes positional args `(top, factor_a, factor_b)`; reads optional fields (BAND_DSA, BAND_DSB, BAND_PHASE) from globals settable via `:=`
- `parallax_section` opens a record and seeds the optional-field globals to defaults

---

## Task 1 — Struct layout cross-reference

**S.C.E.** (`Engine/Core/Deformation Script.asm:12-26`):

`HScroll_Deform` iterates over a per-block list. Each block is:
- velocity (word)
- size (word, in deformation table entries)
- buffer pointer (word — pointer to the FG/BG entry in the H_scroll buffer)

3 words = 6 bytes per block. List is preceded by a count word and terminates after `count+1` blocks. Velocity is added to a 32-bit accumulator (`add.l d2,(a3)`); the high 16 bits become the scroll value.

This is a **velocity-driven** model: each frame, velocity is added to an accumulator, and the accumulator's high word becomes the scroll value. No factor-based scaling from camera position; the deformation table itself is the camera's input transformed via velocity.

**Our band_entry (10 bytes) is more expressive** than S.C.E.'s 6-byte block:
- Per-band Plane A + Plane B factor split (3 bytes × 2 = 6 bytes) — S.C.E. doesn't have this
- Per-band amplitude shift for FG + BG deform (2 bytes) — S.C.E. ties amplitude to velocity
- Per-band phase offset (1 byte) — S.C.E. doesn't desync bands
- Top-cell index (1 byte) — S.C.E. uses block size and walks sequentially

S.C.E.'s simpler structure suffices for level-by-level fixed parallax (no transitions, no per-band tuning). Our model targets per-section variation, transition smoothing, and dual FG/BG deformation, justifying the larger per-band footprint. 8 bands × 10 bytes = 80 bytes per section's bands; S.C.E. equivalent would be ~48 bytes for 8 blocks. 32 bytes more per section is cheap.

**sonic_hack** (`code/engines/scroll_camera.asm:236+`): hardcoded per-zone routines, no struct at all. Each zone gets its own subroutine. Confirms the value of struct-based per-section approach for our engine — enables compile-time validation, runtime mode switching, and per-section ROM tables.

**TF4 / Vectorman / Batman / Gunstar / Alien Soldier**: raw disassembly only; cross-engine survey already covered in pre-spec brainstorming research (see `docs/superpowers/specs/2026-04-27-section-46-parallax-design.md` "Research summary"). No additional findings affect Task 1.

**Conclusion:** Plan struct layout is sound. Proceed to implementation.

---
