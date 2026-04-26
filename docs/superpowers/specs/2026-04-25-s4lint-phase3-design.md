# s4lint Phase 3 — Severity Split & New Rules

## Goal

Restructure s4lint diagnostics into three severity tiers (error / warning / suggestion) so that judgment-call diagnostics stop masking actionable warnings, and add one new rule (W020 tail call optimization).

## Architecture

All changes are in `tools/s4lint.py` and `tools/test_s4lint.py`. No build pipeline changes — `build.sh` already calls s4lint and the exit code semantics are compatible.

### Three-Tier Severity Model

| Tier | Blocks build? | Meaning |
|---|---|---|
| Error (E001–E011) | Always (exit 1) | Incorrect code — crashes, corruption, silent misbehavior |
| Warning (W001–W004, W007–W008, W011–W017, W020) | Only with `--warnings-as-errors` | Unambiguously suboptimal — always a valid fix |
| Suggestion (W005, W006, W010, W018) | Never | Requires human judgment — may be intentional |

Suggestions keep their existing W-codes. No renaming to S-codes. This avoids churn in inline `; lint: disable=W005` comments.

### Classification Mechanism

A module-level dict overrides the default prefix-based severity:

```python
DIAGNOSTIC_SEVERITY: Dict[str, str] = {
    "W005": "suggestion",
    "W006": "suggestion",
    "W010": "suggestion",
    "W018": "suggestion",
}
```

Codes not in this dict use the existing convention: `E*` → `"error"`, `W*` → `"warning"`. The severity is resolved when a `Diagnostic` is created — the `emit()` path looks up the code in `DIAGNOSTIC_SEVERITY`, falling back to the prefix letter.

The `ctx.error()` and `ctx.warning()` helper methods remain unchanged. Check functions don't need to know whether a given W-code is a warning or suggestion — that's determined by the classification dict.

### Output Format

Diagnostic lines include the resolved severity:

```
file:line: error: message [E001]
file:line: warning: message [W001]
file:line: suggestion: message [W005]
```

Summary line shows all three counts (omitting zero counts):

```
s4lint: 0 warnings, 87 suggestions
```

Per-code breakdown table follows the summary, same format as today.

### CLI Flags

| Flag | Effect |
|---|---|
| `--no-suggestions` | Hide suggestions, show warnings + errors |
| `--no-warnings` | Hide warnings AND suggestions, only errors |
| `--warnings-as-errors` | Promote warnings → errors. Suggestions unchanged |

`--no-warnings` implies `--no-suggestions` — the filtering logic treats `--no-warnings` as suppressing both severity levels. Users don't need to pass both. These flags are not mutually exclusive with each other — `--warnings-as-errors --no-suggestions` is a valid combination (promote warnings to errors, hide suggestions).

### Exit Code

- Exit 1 if any errors emitted (after filtering)
- Exit 1 if any warnings AND `--warnings-as-errors`
- Exit 0 otherwise — suggestions never affect exit code

---

## W020: Tail Call Optimization

**Pattern:** `bsr`/`jsr` immediately followed by `rts`.

**Fix:** Replace `bsr label` with `bra.w label`, or `jsr label` with `jmp label`.

**Savings:** 4 bytes (no return address pushed/popped), ~16 cycles.

**Severity:** Warning (always a valid optimization).

**Detection:** Uses existing `prev_token` tracking. When current instruction is `rts`, check if `prev_token` was `bsr` or `jsr`. Emit W020 if so.

**Edge case — intervening labels:** If a global or local label appears between the `bsr`/`jsr` and the `rts`, the `rts` may be a separate entry point. Add a `label_since_last_instr` flag to `LintContext` — set it when a label is encountered, clear it when an instruction is processed. W020 only fires if this flag is false.

**Message format:**
```
'bsr Label' immediately followed by rts — use 'bra.w Label' for tail call (saves 4 bytes, ~16 cycles)
```

The replacement preserves the original operand and suggests `bra.w` for `bsr` or `jmp` for `jsr`.

---

## Dropped: tst on address register

`tst.w aN` / `tst.l aN` is illegal on 68000 (only 68020+). However, AS already rejects this with a hard assembler error (`addressing mode not allowed here`). A linter rule would be redundant. Dropped from scope.

---

## Scope Summary

1. **DIAGNOSTIC_SEVERITY dict** — classify W005/W006/W010/W018 as suggestions
2. **Resolve severity in emit path** — Diagnostic gets effective severity from dict, not call site
3. **Output format** — print `suggestion:` for suggestion-tier diagnostics
4. **Summary line** — three-count format (errors, warnings, suggestions), omit zeroes
5. **`--no-suggestions` flag** — suppress suggestions only
6. **`--no-warnings` update** — also suppresses suggestions
7. **W020 tail call rule** — bsr/jsr + rts detection with label-intervening guard
8. **Tests** — update existing tests for new severity strings, add W020 tests, add CLI flag tests
