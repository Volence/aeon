# s4lint — Static Analysis for 68000 Assembly

## Overview

A Python-based linter (`tools/s4lint.py`) that catches correctness bugs at build time before the assembler runs. Designed for the aeon codebase conventions — not a generic 68000 tool.

Phase 1 focuses on correctness checks (things that crash or corrupt). Convention enforcement (naming, style) is deferred to Phase 2.

## Architecture

### Tokenizer

Each `.asm` line is split into a structured tuple:

```
(line_number, label, instruction, size_suffix, operands[], comment)
```

- `label`: global (`PascalCase`) or local (`.dotted`), or None
- `instruction`: mnemonic lowercased (`move`, `bra`, `lea`, etc.) or macro name
- `size_suffix`: `.b`, `.w`, `.l`, or None
- `operands`: list of operand strings, whitespace-trimmed
- `comment`: everything after `;`, or None

Lines that are pure comments, blank, or assembler directives (`if`, `endif`, `rept`, `endr`, `include`, `phase`, `dephase`) are recognized as their own types rather than instructions.

### State Tracker

Per-file state, reset at each global label (routine boundary):

| State | Values | Default at routine entry |
|---|---|---|
| Z80 bus | `running`, `stopped`, `unknown` | `unknown` |
| Interrupts | `enabled`, `disabled`, `unknown` | `unknown` |
| Byte alignment | count of `dc.b`/`ds.b` bytes since last `even` | 0 (aligned) |
| SR saved | boolean — whether `move.w sr,-(sp)` seen without restore | false |
| Inside dbf loop | boolean + label of loop top | false |

State resets to `unknown` at each global label unless the previous routine ended without `rts`/`rte`/`bra` (fall-through detected), in which case state carries forward.

### File Discovery

When given `main.asm` as the entry point, the linter follows `include` directives to build the file list (same order the assembler processes them). Alternatively accepts explicit file paths as CLI arguments.

Files under `debug/` that are part of the MD Debugger (not our code) can be excluded via a skip-list.

## Error Checks (Block Build)

All errors use codes E001-E011.

### E001: Unsized Branch or Jump

Any `bra`, `bne`, `beq`, `bhi`, `blo`, `bhs`, `bls`, `bge`, `bgt`, `ble`, `blt`, `bpl`, `bmi`, `bcc`, `bcs`, `bvc`, `bvs`, `bsr` without `.s` or `.w` suffix.

```
engine/objects.asm:42: error: unsized branch 'bra .loop' — add .s or .w [E001]
```

### E002: Multiply/Divide in Hot Path

`mulu`, `muls`, `divu`, `divs` in files under `engine/` or `objects/`. Warning-level (W014) in other directories.

```
engine/sprites.asm:87: error: mulu in hot path — use shifts/adds/lookup [E002]
```

### E003: Odd Immediate Address

An immediate value used as an address operand (in `movea`, `lea`, `jmp`, `jsr`, or any `(xxx).w`/`(xxx).l` effective address) where the value is odd.

```
engine/vdp_init.asm:15: error: odd address $FF0001 will cause address error [E003]
```

### E004: Word/Long Access to Odd Literal

`move.w`, `move.l`, or any word/long-sized instruction with an absolute address operand that resolves to an odd number.

```
engine/boot.asm:30: error: word-size access to odd address $C00005 [E004]
```

### E005: Missing Alignment After Byte Data

A `dc.w`, `dc.l`, `ds.w`, `ds.l`, or an instruction appears after one or more `dc.b`/`ds.b` directives without an intervening `even` or `align 2`. Only triggers when the accumulated byte count is odd.

```
data/mappings/test_mappings.asm:20: error: word data after odd byte count without 'even' [E005]
```

### E006: VDP Access Without Z80 Stopped

Any write to `VDP_CTRL` (`$C00004`) or `VDP_DATA` (`$C00000`) — either direct address or through known macros (`setVDPReg`) — when Z80 bus state is `running` or `unknown`.

```
engine/vblank.asm:55: error: VDP write without stopZ80 [E006]
```

### E007: Unpaired stopZ80/startZ80

A routine (global label to `rts`/`rte`) contains `stopZ80` without a matching `startZ80`, or vice versa.

```
engine/vblank.asm:90: error: stopZ80 at line 62 has no matching startZ80 before rts [E007]
```

### E008: Macro Contract Violation

A macro is invoked but its preconditions (from the contract registry) are not met.

```
engine/game_loop.asm:33: error: setVDPReg requires z80=stopped [E008]
```

### E009: SST Access Past Bounds

An operand containing an `SST_*` offset where the offset value >= `SST_len` ($50). Catches custom field overlays that exceed the struct.

```
objects/test_enemy.asm:8: error: SST field offset $52 exceeds SST_len ($50) [E009]
```

The linter resolves `SST_sst_custom + N` patterns by knowing `SST_sst_custom = $32` and `SST_len = $50`, so any `N >= 30` ($1E) triggers this.

### E010: SR Save/Restore Mismatch

`move.w sr,-(sp)` without a matching `move.w (sp)+,sr` before every `rts`/`rte` in the routine.

```
engine/dma_queue.asm:58: error: sr saved at line 58 but not restored before rts at line 97 [E010]
```

### E011: Double stopZ80

`stopZ80` invoked when Z80 bus state is already `stopped`.

```
engine/vblank.asm:70: error: stopZ80 but Z80 already stopped (stopped at line 62) [E011]
```

## Warning Checks (Don't Block Build)

All warnings use codes W001-W013.

### W001: `clr` on Memory

`clr.w (addr)` or `clr.l (addr)` — 68000 does a read-modify-write. Suggest `moveq #0,dn; move.X dn,(addr)`.

### W002: `cmp #0` Instead of `tst`

`cmp.X #0, dn` or `cmpi.X #0, dn` — `tst.X dn` is shorter and faster.

### W003: `move.w #0` Instead of `moveq`

`move.w #0, dn` — should be `moveq #0, dn`.

### W004: `add/sub #1-8` Instead of `addq/subq`

`add.w #N, X` or `sub.w #N, X` where N is 1-8. Should be `addq`/`subq`.

### W005: Long Branch Where Short Likely Reaches

`bXX.w .local_label` where the target is a local label within the same routine. The `.s` form is likely sufficient. (Approximate — based on line distance, not byte distance.)

### W006: Routine Missing Header Comment

A global label followed by code with no register contract comment block (the `; In: / Out: / Clobbers:` pattern) within the 10 lines preceding it.

### W007: `lsl.w #1` Instead of `add`

`lsl.w #1, dn` — `add.w dn, dn` is 2 cycles faster.

### W008: `sub.w dn,dn` to Zero

`sub.X dn, dn` — should be `moveq #0, dn` or `clr`.

### W009: `swap; clr.w` Pattern

`swap dn` followed immediately by `clr.w dn` — should be `clr.l dn` if the upper word isn't needed.

### W010: Indexed Addressing in dbf Loop

`(an,dn.w)` or `(an,dn.l)` effective address inside a `dbf` loop body. Suggest pre-computing with `lea` outside the loop.

### W011: `movem` for Single Register

`movem.l dn,-(sp)` or `movem.l (sp)+,dn` with only one register. A plain `move.l` or the `swap` trick is cheaper.

### W012: `move.l an,an` Instead of `movea.l`

`move.l aX, aY` — should be `movea.l` for clarity. Same encoding but conventions require `movea`.

### W013: `move.w #N` in moveq Range

`move.w #N, dn` where -128 <= N <= 127. Should be `moveq #N, dn`.

## Macro Contract Registry

Defined as a Python dict at the top of the script (or in a separate `s4lint_config.py`):

```python
MACRO_CONTRACTS = {
    "stopZ80":     {"rejects": {"z80": "stopped"},  "sets": {"z80": "stopped"}},
    "startZ80":    {"requires": {"z80": "stopped"},  "sets": {"z80": "running"}},
    "disableInts": {"sets": {"ints": "disabled"}},
    "enableInts":  {"requires": {"ints": "disabled"}, "sets": {"ints": "enabled"}},
    "setVDPReg":   {"requires": {"z80": "stopped"}},
    "vdpCommReg":  {},
    "queueStaticDMA": {},
}
```

Macros with empty contracts are recognized (not flagged as unknown) but have no state requirements.

Adding a new macro: add one line to the dict. If the macro has no hardware state requirements, use `{}`.

## Inline Suppression

Single-line suppression via comment:

```asm
        mulu    d1, d0          ; lint: disable=E002
```

Only suppresses the specified check on that line. No block suppression — each exception must be individually justified.

## Build Integration

In `build.sh`, before the assembler:

```bash
echo "Linting..."
python3 tools/s4lint.py main.asm
if [[ $? -ne 0 ]]; then
    echo "Lint errors found — fix before assembling."
    exit 1
fi
```

### CLI Interface

```
Usage: python3 tools/s4lint.py [options] <file.asm ...>

Options:
  --warnings-as-errors    Treat warnings as errors (non-zero exit)
  --no-warnings           Suppress all warnings
  --only=E001,W003,...    Only run specified checks
  --skip=W005,W006,...    Skip specified checks
  --no-follow-includes    Don't follow include directives (lint only named files)
```

### Output Format

```
file.asm:LINE: error: MESSAGE [CODE]
file.asm:LINE: warning: MESSAGE [CODE]
```

Exit code 0 if no errors (warnings alone don't fail). Exit code 1 if any errors found.

## What s4lint Does NOT Do

- **Expand macros** — recognizes them by name, doesn't inline their content
- **Evaluate AS expressions** — doesn't resolve `function` results or `if` conditions
- **Cross-file analysis** — each file is analyzed independently; the assembler catches cross-file issues
- **Control flow graphs** — no branch-following or register dataflow (potential Phase 3)
- **Naming conventions** — deferred to Phase 2

## Future Phases

**Phase 2 — Convention Enforcement (warnings):**
- Naming style: PascalCase routines, ALL_CAPS constants, .lowercase locals
- File header presence
- Routine length metrics
- `function` usage for constant expressions

**Phase 3 — Deeper Analysis (optional):**
- Intra-routine control flow for register initialization tracking
- Branch target alignment checking (even-address hot labels)
- Stack depth tracking (push/pop balance across branches)
- DMA source address even-ness verification

**Organic Growth:**
- When an in-game crash is traced to a pattern the linter could have caught, add a new check. The linter grows from real bugs.
