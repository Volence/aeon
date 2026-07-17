# s4lint W021 — write-set vs declared `; Clobbers:` header

**Status:** implemented 2026-07-17 (Sigil diagnostics-tier prework, deliverable 3).

## Summary

W021 is the `.asm` interim tier's approximation of the `.emp`
`[proc.clobber-undeclared]` compiler lint (review D1 / "s4lint growth list").
It warns when a routine writes a register that its header does not account for.
Per the 2026-07-16 review adjudication, the `.asm` tier is **best-effort,
warning-level, and NEVER blocks the build** (W021 returns exit 0; only
`--warnings-as-errors` promotes it). The strict Clobbers-set check lives in the
`.emp` compiler; W021 catches the same bug class in the still-`.asm` engine the
compiler tier cannot see (e.g. `Vscroll_Write`, `camera.asm`, `bg.asm`).

## Rule

- **Activation:** only for a routine whose header comment block contains a
  `; Clobbers:` line (mirrors the `.emp` lint running only when `clobbers()` is
  declared). A routine with no `Clobbers:` header is not checked.
- **Allowed set:** the `Clobbers:` reglist PLUS every register named ANYWHERE in
  the header comments (the `In:`/`Out:` prose, which is free-form and spans
  continuation lines). W021 therefore fires only on a register the header is
  **completely silent about** — the high-confidence, low-noise signal a
  warning tier wants. (A stricter "not in the Clobbers set specifically" check
  drowns in `In:`/`Out:`-documented registers and header-prose noise.)
- **Write detection** (`_written_regs`, mirrors the `.emp` `instr_written_regs`
  after the 2026-07-17 auto-inc/dec fix): the write-form destination (last
  operand, when a plain register) plus any `(An)+`/`-(An)` base in any operand
  position and any mnemonic (`tst.w (a0)+` writes a0). `a7`/`sp` is dropped
  (stack discipline, never a Clobbers convention). Only RECOGNIZED 68k mnemonics
  are scanned — macro invocations are skipped, never guessed.
- **Dedup:** one warning per (routine, register), not per write site (a
  human-facing `.asm` warning, unlike the per-instruction `.emp` compiler lint).

## Best-effort limitations (deliberate; documented not fixed)

- **Local, not transitive** — callee register effects are not tracked (same as
  the `.emp` lint; D1a transitivity is compiler-tier future work).
- **Individual/movem-push preservation false positives** — a register written
  then preserved via `movem.l rN,-(sp)` … restore (e.g. `BG_Init` a3,
  `AllocDynamic` a0) fires, because pairing the save/restore is the S2-D6
  dataflow work. This is the SAME false-positive class the `.emp` lint carries
  (census A1 / gap-ledger row 1030) — kept for consistency, not a W021 defect.
- **Unicode dashes** — headers use en-dash/em-dash in ranges (`; Clobbers:
  d0–d4`); the range regex accepts `-`/`–`/`—` (an ASCII-only regex false-fires
  on the range interior — the bug this rule was validated against).

## Corpus findings at implementation (8 deduped, engine + games)

Cross-validated against the `.emp` contract census (sigil
`2026-07-17-diagnostics-contract-census.md`):

| Reg | Routine | File | Class |
|---|---|---|---|
| d0, a0 | `Vscroll_Write` | parallax.asm | **real** — review-named ("prerequisite for the ISR movem trim"); `.asm`-only, invisible to the `.emp` tier |
| d7 | `RunObjects_Frozen` | core.asm | **real** — matches `.emp` census (core #11) |
| d1 | `DeleteObject` | core.asm | **real** — matches `.emp` census |
| d2 | `Collected_ParkSlot` | entity_window.asm | **real** — d2 scratched, header omits it |
| d4 | `GameState_ObjectTest_Init` | object_test_state.asm | **real** — test/debug state |
| a0 | `AllocDynamic` | core.asm | FALSE POSITIVE — individual-push preservation |
| a3 | `BG_Init` | bg.asm | FALSE POSITIVE — movem-push preservation |

The 5 real findings are retrofit demand data (add the register to the header's
`Clobbers:`/`In:`/`Out:`, or suppress with `; lint: disable=W021`). The 2 FPs
are the known preservation-pattern class.

## Implementation

`tools/s4lint.py`: `_parse_clobbers_header`, `_written_regs`,
`_expand_reglist`, `_is_recognized_mnemonic`, the `LintContext.declared_writeset`
/ `w021_seen` per-routine state, and the W021 block in `check_warnings`. Tests:
`tools/test_s4lint.py::TestW021_WriteSetVsHeader` (10 cases: undeclared write,
declared silent, no-header-disables, reglist range, post-inc, pre-dec, stack
push/pop exempt, In/Out allowed, macro skipped, suppression).
