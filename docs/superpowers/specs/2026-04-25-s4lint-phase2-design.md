# s4lint Phase 2 — Convention Enforcement

## Overview

Phase 2 adds warning-level checks for naming conventions, file structure, and routine length to the existing s4lint linter. Also adds a diagnostic summary footer. All new checks are warnings (W015-W019) — they do not block the build.

Phase 1 (E001-E011, W001-W014) is already implemented and merged.

## New Warning Checks

### W015: Global Label Not PascalCase

Global labels (any label not starting with `.`) must match PascalCase with underscores between words: `[A-Z][A-Za-z0-9]+(_[A-Za-z0-9]+)*`.

Valid examples: `VDP_Init`, `Camera_X`, `EntryPoint`, `DMA_Queue_Process`, `RAM_Start`

Invalid examples: `vdp_init` (lowercase start), `DMA_QUEUE_ADD` (all caps — that's a constant, use `=` or `equ`), `myRoutine` (camelCase)

**Skip conditions:**
- Labels defined with `=` or `equ` (those are constants — checked by W016 instead)
- Labels where the instruction is `struct`, `macro`, or `function` (those have their own naming conventions not enforced in Phase 2)
- Labels that are exactly one uppercase letter (loop counters like `i` aren't used, but single-char labels in macros shouldn't fire)

```
engine/objects/core.asm:42: warning: global label 'run_objects' is not PascalCase (expected 'Run_Objects' or similar) [W015]
```

### W016: Constant Not ALL_CAPS

Labels defined via `=` or `equ` must match `[A-Z][A-Z0-9]+(_[A-Z0-9]+)*`.

Valid examples: `MAX_OBJECTS`, `VRAM_POOL_SIZE`, `VDP_DATA`, `BUTTON_A`

Invalid examples: `maxObjects`, `Vram_Pool`, `vdp_data`

**Tokenizer note:** The tokenizer parses `LABEL = value` with `=` as the instruction and `value` as an operand. `LABEL equ value` has `equ` as the instruction. Both patterns identify a constant definition.

```
constants.asm:15: warning: constant 'vdp_Data' should be ALL_CAPS (expected 'VDP_DATA' or similar) [W016]
```

### W017: Local Label Not .lowercase

Local labels (starting with `.`) must match `\.[a-z][a-z0-9_]*`.

Valid examples: `.loop`, `.done`, `.not_found`, `.skip_pal`

Invalid examples: `.Loop`, `.DONE`, `.notFound`, `.Skip`

```
engine/boot.asm:55: warning: local label '.Loop' should be .lowercase (expected '.loop') [W017]
```

### W018: Routine Too Long

A routine (global label to `rts`/`rte`) that exceeds 100 instructions. The instruction count is `ctx.routine_lines` which already tracks this in Phase 1.

Only fires at routine terminators (`rts`/`rte`). Does not fire for routines that end with `bra`/`jmp` (tail calls — the routine boundary is less clear).

```
engine/objects/sprites.asm:395: warning: routine 'Render_Sprites' is 142 instructions (threshold: 100) — consider splitting [W018]
```

### W019: File Missing Header Comment

The first non-blank line of a file must be a comment (starts with `;` after optional whitespace). Checked once per file before the line-by-line loop.

```
engine/new_file.asm:1: warning: file has no header comment (first line should be '; description') [W019]
```

## Diagnostic Summary Footer

After all diagnostics are printed, output a summary to stderr:

```
s4lint: 2 errors, 47 warnings
  E005  1  missing alignment after byte data
  E006  1  VDP write without Z80 stopped
  W001  7  clr on memory (read-modify-write)
  W005  28 branch should use .s
  W010  12 indexed addressing in loop
```

Format:
- First line: `s4lint: N errors, M warnings` (or `s4lint: no issues found` when clean)
- One line per code that fired, sorted by code, with count and a short human-readable label
- Grouped by severity (errors first, then warnings)
- Only codes that actually fired are shown
- Suppressed via `--no-warnings` when applicable (warning lines hidden, but error lines still shown)

The short labels are a static dict mapping code to description, e.g.:
```python
DIAGNOSTIC_LABELS = {
    "E001": "unsized branch",
    "E002": "multiply/divide in hot path",
    ...
    "W015": "global label not PascalCase",
    ...
}
```

## Implementation

### Where Each Check Lives

| Check | Location in s4lint.py | Trigger |
|-------|----------------------|---------|
| W015 | `run_checks`, label-tracking section | Global label encountered |
| W016 | `run_checks`, label-tracking section | Label with `=` or `equ` instruction |
| W017 | `run_checks`, label-tracking section | Local label encountered |
| W018 | `run_checks`, routine termination section | `rts` or `rte` encountered |
| W019 | `lint_file`, before line loop | First non-blank line check |
| Summary | `main()`, after diagnostic loop | Always (end of run) |

### No New State

All new checks are stateless inspections or use existing `LintContext` fields:
- W015/W016/W017: inspect `token.label` and `token.instruction`
- W018: reads `ctx.routine_lines` (already tracked) and `ctx.current_routine`
- W019: reads raw file lines (already loaded)

### Regex Patterns

```python
_PASCAL_CASE_RE = re.compile(r'^[A-Z][A-Za-z0-9]*(_[A-Za-z0-9]+)*$')
_ALL_CAPS_RE = re.compile(r'^[A-Z][A-Z0-9]*(_[A-Z0-9]+)*$')
_LOCAL_LABEL_RE = re.compile(r'^\.[a-z][a-z0-9_]*$')
```

Note: PascalCase regex also matches ALL_CAPS (e.g., `RAM_START` matches both). This is intentional — W015 only runs on labels that are NOT constant definitions, and W016 only runs on constant definitions. The two checks are mutually exclusive by context.

### Inline Suppression

Same mechanism as Phase 1: `; lint: disable=W015` on the line.

### CLI Interaction

All existing CLI flags apply to the new checks:
- `--skip=W015,W016` suppresses naming checks
- `--only=W018` runs only the routine length check
- `--no-warnings` suppresses all new checks (they're all warnings)
- `--warnings-as-errors` promotes them to errors

## What Phase 2 Does NOT Check

- **Struct field naming** — would require parsing inside struct blocks (deferred)
- **AS function/macro naming** — would require parsing function/macro definitions (deferred)
- **SST custom overlay naming** — `_lowercase_underscored` convention (deferred)
- **Compile-time `function` usage** — detecting "this runtime math could be a function" requires deeper analysis (deferred to Phase 3)
- **File organization** — "one logical unit per file" is a judgment call, not automatable
