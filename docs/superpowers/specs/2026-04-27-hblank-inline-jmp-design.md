# Spec — HBlank Inline-JMP Dispatch

## Context

Reading the Ristar disassembly we found their HBlank dispatch is
notably faster than ours. Their pattern:

- HBlank IRQ vector points DIRECTLY at a fixed RAM address (`$FFEA70`).
- That RAM address contains an inline `jmp imm.l` instruction:
  ```
  RAM at $FFEA70: 4E F9 XX XX XX XX     = jmp $XXXXXXXX.l
  ```
- IRQ fires → vector → executes the JMP directly to the per-section
  handler. No ROM stub, no indirect call, no `movem` save/restore in
  the dispatcher.

Per-section installs are just:
```asm
move.w   #$4ef9, $ea70.w           ; opcode for jmp.l
move.l   #section_hint_handler, $ea72.w
```

See `ristar_disasm/code/disasm.asm` lines 257-258 for the install pattern;
`ristar_disasm/ANALYSIS.md` § "Interrupt dispatch — the smart bit"
for the full analysis.

## What we have today

`engine/hblank.asm`:
```asm
HBlank_Dispatch:                          ; lives in ROM
        movem.l d0-d1/a0, -(sp)
        movea.l (HBlank_Handler_Ptr).w, a0
        jsr     (a0)
        movem.l (sp)+, d0-d1/a0
        rte

HBlank_Null:
        rts                                ; default no-op handler
```

The HBlank vector points at `HBlank_Dispatch` (ROM). Every HBlank fire
costs:
- `movem.l 3 regs in` (~36 cycles)
- `movea.l + jsr` indirect (~22 cycles)
- the handler runs (with `rts`)
- `movem.l 3 regs out` (~36 cycles)
- `rte` (~20 cycles)

Per-fire dispatcher overhead (excluding the handler itself): **~115 cycles**.

## Ristar's overhead

- `jmp imm.l` (~12 cycles)
- handler runs (with its own minimal save/restore + `rte`)
- `rte` (~20 cycles)

Per-fire dispatcher overhead: **~12 cycles**. Handler internally saves
only the regs it actually uses, often 1 reg = ~12+12 = 24 cycles.

## Savings

~80 cycles/fire × 224 NTSC scanlines = ~17,920 cycles/frame ≈
**~22% of one CPU frame** if HBlank fires every line. In practice many
sections fire HBlank only on a subset of lines (e.g. 28 cell-band
boundaries), so the realistic gain is closer to ~2,000–5,000 cycles/frame.
Still meaningful for raster-heavy sections.

## Goal

Replace the ROM-stub dispatcher with a Ristar-style inline-JMP install
pattern. Wire it into the per-section HInt handler install path that
§4.6 parallax is establishing.

## Why now

Per-section HInt dispatch is being designed now in §4.6 (see
`docs/superpowers/specs/2026-04-27-section-46-parallax-design.md`).
Adopting the inline-JMP install at the same time costs almost nothing
extra — we're already going to write per-section install code; it's
the same code volume, just writes 6 bytes (opcode + addr) instead of
4 bytes (just addr).

If we adopt later, we'll have to:
- Refactor every existing HBlank handler to end with `rte` instead of
  `rts`
- Change the handler-authoring contract (handlers manage their own reg
  saves)
- Re-test every raster effect

Doing it now means new handlers are authored with the right contract
from the start.

## Files in scope

**Read first:**
- `engine/hblank.asm` — current dispatcher
- `engine/boot.asm:143-189` — how HBlank vector is initially installed
- `docs/superpowers/specs/2026-04-27-section-46-parallax-design.md`
- `docs/superpowers/plans/2026-04-27-section-46-parallax.md` — find the
  task that installs the per-section HInt handler

**Modify:**
- `engine/hblank.asm` — replace `HBlank_Dispatch` ROM stub with a
  named RAM symbol `HBlank_Install` (6-byte `4EF9 + addr` slot)
- Vector table install path — point HBlank vector directly at
  `HBlank_Install` RAM, not at the ROM stub
- `HBlank_Null` — must end with `rte` instead of `rts`
- Section-load HInt-install path — write `4EF9` + handler addr, not
  just a pointer
- Any other existing HBlank handler — same: end with `rte`, manage
  own regs

## Tasks

1. **Allocate RAM**: define `HBlank_Install` (or similar) at a fixed
   word-aligned RAM address, 6 bytes.
2. **Boot init**: write `move.w #$4EF9, HBlank_Install.w` once at boot
   (the destination addr at `HBlank_Install+2` will be written per
   section). Initial dest = `HBlank_Null`.
3. **Vector table**: change HBlank vector entry to point at
   `HBlank_Install` instead of `HBlank_Dispatch`.
4. **HBlank_Null**: change `rts` to `rte`.
5. **Per-section install macro/helper**: provide
   `set_hblank_handler(addr)` that writes the addr to `HBlank_Install+2`.
   Used by section streamer / parallax init.
6. **Delete `HBlank_Dispatch` ROM stub** — no longer reachable.
7. **Update existing HBlank handlers** (currently just `HBlank_Null`,
   so trivial). Each must:
   - Push any registers it uses
   - Do its work
   - Pop registers
   - End with `rte`
8. **Document the contract** in `engine/hblank.asm` header comment.
9. **Test**: build, boot, title screen renders. Then add a smoke-test
   handler that does something visible (e.g., toggle a CRAM color via
   write to `$C00000`) and verify it fires.

## Acceptance criteria

- [ ] HBlank vector points directly at RAM (`HBlank_Install`).
- [ ] `HBlank_Install` contains `4E F9 XX XX XX XX` bytes.
- [ ] `HBlank_Dispatch` ROM stub removed.
- [ ] All HBlank handlers end with `rte`, manage own regs.
- [ ] Per-section HInt install (in §4.6) uses inline-JMP pattern.
- [ ] Title screen + OJZ scroll test still render cleanly.
- [ ] Build green; ROM-equivalent visual output.

## Coordinate with §4.6

**Consult the §4.6 parallax plan owner before merging.** §4.6 is
in-flight; this change should land before §4.6 wires per-section HInt
install, OR §4.6 should adopt this dispatch pattern as part of its own
work. Either order is fine; double-installing isn't.

## Notes

- This is small. ~50-100 lines of changes across hblank.asm, vector
  table, and handler contract.
- The cycle savings only matter for raster-heavy stages. Don't oversell;
  it's a clean architectural improvement, not a transformative perf win.
- Real win is **keeping the contract clean for new handlers** — every
  per-section HInt installed from §4.6 onward gets the fast path.
