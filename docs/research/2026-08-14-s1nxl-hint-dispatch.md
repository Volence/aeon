# Sonic 1: The Next Level — HBlank dispatch, and what it means for our raster tier

**Date:** 2026-08-14
**Subject ROM:** `S1NXL.bin`, 3,964,388 bytes, header `SONIC 1: THE NEXT LEVEL` (MarkeyJester).
Supplied by the owner as the reference for a **giant plane-drawn boss** with heavy warping and
palette work — the ambition target for our raster vocabulary.

**Method:** static disassembly of the ROM image (capstone M68K + hand decode). **No emulator run, and
no execution traced.** Everything below is read from the reset path; nothing here is a claim about the
boss's own code, which was not located.

---

## 1. The finding: HBlank is dispatched through a RAM trampoline

The 68000 vector table has been overwritten with an author message ("Once there was a Jester, he threw
a decade of his life at hacking…"), but the two interrupt vectors survive inside it:

| Vector | Offset | Value | Effective (24-bit) |
|---|---|---|---|
| IRQ4 — HBlank | `$70` | `$20FFA7F0` | **`$FFA7F0`** (RAM) |
| IRQ6 — VBlank | `$78` | `$20FFA7F6` | **`$FFA7F6`** (RAM) |

Six bytes apart. The reset path at `$00037A` installs them:

```
$000382:  41FA 002C     lea     $3B0(pc), a0     ; source table in ROM
$000386:  43F8 A7F0     lea     $A7F0.w, a1      ; the RAM trampoline pair
$00038A:  22D8          move.l  (a0)+, (a1)+     ; 12 bytes = two 6-byte jmps
$00038C:  22D8          move.l  (a0)+, (a1)+
$00038E:  22D8          move.l  (a0)+, (a1)+
```

And the ROM table at `$0003B0`:

```
$0003B0:  4EF9 0000 14B2    jmp $0014B2      ; default HBlank handler
$0003B6:  4EF9 0000 0B62    jmp $000B62      ; default VBlank handler
```

So the interrupt vectors point at **two writable `jmp` instructions in RAM**. Any game state can
install a different HBlank handler by writing four bytes to `$FFA7F2`.

This is the same shape the project already recorded for Ristar (HBlank → `$FFEA70`,
`docs/research/ristar-techniques.md`), and it is exactly
`docs/research/visual-techniques-backlog.md` **§19 "per-section HInt handler dispatch"**.

---

## 2. Why this matters for the ambition question

**CORRECTION, and it inverts the interesting half of this note.** The first draft framed this as an
architectural difference between S1NXL and Aeon. It is not. **Aeon already ships the identical
mechanism**, and the author of this note asserted the contrast without checking our own side first.

`engine/system/hblank.emp` points IRQ4 **directly at `HBlank_Vector_Slot`, a 6-byte executable slot in
RAM**, holding either an idle `rte` (`$4E73`) or `jmp handler.l` (`$4EF9` + target). `HBlank_Install
(a0: HBlankHandler, d0: u8)` writes the opcode and the handler address, programs the line counter and
enables IE1. The module's own header states the intent plainly: *"The trampoline is dispatch MECHANISM
only. Its first consumer — the sparse raster dispatcher that installs itself here — lives in
engine/effects/raster.emp."*

`ENGINE_ARCHITECTURE.md:299` already records this, notes that Vectorman (`$FFFF9D2E`), Batman
(`$FFFFE560`) and Gunstar/Alien Soldier (`$FFFFEE00`) all do a variant, and argues ours is slightly
better — theirs read a *pointer* from RAM, ours executes an *instruction* from RAM, saving the
pointer-load and the indirect jump.

**So the difference is policy, not capability:**

| | S1NXL | Aeon |
|---|---|---|
| Dispatch mechanism | RAM trampoline, `jmp abs.l` | **RAM trampoline, `jmp abs.l` — the same** |
| What is installed today | arbitrary per-state handlers | **one** handler (`Raster_HInt`) walking per-section **data** (`Sec.sec_raster_table`) |
| Installing a bespoke handler | the norm | **supported and public** — `HBlank_Install` is a `pub proc` with no policy attached |
| Cost of a wrong handler | crash / corruption at runtime | same, if you bypass the DSL |

**The practical answer to "can we do what MarkeyJester did for that boss?" is therefore yes, and the
mechanism is already shipped.** A boss state can call `HBlank_Install` with its own handler and do
anything per line that fits the budget. What it gives up by doing so is exactly what the raster DSL
exists to provide: build-time validation, a single audited hot path, and programs that cannot be
malformed.

The honest trade is a per-state choice, not an engine limitation:

- **Use the DSL** for anything expressible in its op set — you get the guards, and the effect is data.
- **Install a bespoke handler** for a set-piece that needs computed per-line values (Thunder Force IV's
  Bresenham accumulator, Ristar's fixed-point interpolation, a boss with a per-frame-varying warp).
  The DSL cannot express computed values by design — everything it emits is comptime-constant.

The value of each additional DSL opcode is still real, because an opcode moves an effect from the
second column to the first. But it is not the difference between possible and impossible.

---

## 3. What the boss almost certainly is (corpus reasoning, NOT measured)

Stated as reasoning from the technique corpus, because it was not verified in this ROM:

- **The art is plane tiles, not sprites.** A near-fullscreen figure is far past the 80-sprite /
  20-per-line budget. Camera locked, boss drawn into a nametable, player composited over it.
- **The sweeping curves are per-line horizontal scroll.** A rectangular tilemap cannot produce them;
  giving each scanline its own HScroll value shears the image, and because a plane is 64×64 cells and
  **wraps**, one strip of art can appear at several horizontal positions on different lines — which
  reads as duplication.
- **Vertical shear, if present, is per-column VSRAM.**
- **The dithering is palette-stretching**, and per-line CRAM writes down the figure give the glow and
  banding.

**This was not confirmed against the ROM.** Confirming it means locating the boss state's installed
handler and reading what it writes — which is a much larger job than the reset path, and is better done
on the emulator with a breakpoint on `$FFA7F2` than statically.

---

## 4. Where Aeon stands on each half

| Ingredient | Aeon subsystem | Status |
|---|---|---|
| Plane art for the figure | VRAM pool / art streaming (ARCH §9.7) | **The real constraint.** A near-fullscreen unique image is ~1000+ tiles against 2048 total. A boss state can plausibly discard the act's art budget — whether the streamer supports that cleanly is an open question |
| Per-line HScroll warp | **Parallax deform (§4.6)** | **Ships.** Frame-level `Hscroll_Buffer` DMA'd at VBlank — and therefore **costs zero HBlank time**, which is better than doing it per-scanline |
| Per-column VSRAM shear | Raster DSL | **Closed 2026-08-14.** `.op_cram` writes whatever VDP command it is handed, so `vsram(addr, values)` needed no runtime change at all. Caveat: whether the write lands on line N+1 or N+2 is UNMEASURED — see `docs/DEFERRED_WORK.md` |
| Palette bands / glow | Raster DSL | **Covered** (`cram`, `pal_region`, `cycle_channel`) |
| Mid-screen plane base swap | Raster DSL | **Authorable today** — regs `$02`/`$04` are inside `set_reg`'s range |
| Per-line values that must be *computed* | A bespoke handler via `HBlank_Install` | **Supported today** (§2). The DSL cannot express computed values by design |
| Player over the boss | Sprites | Normal |

So the raster tier is **not** the binding constraint for this effect class; VRAM is. The VSRAM
constructor (added 2026-08-14) closes the vertical-shear gap inside the DSL, and anything the DSL
still cannot express can be done by installing a bespoke handler — at the cost of the DSL's guards.

---

## 5. Recorded caveats

- The vector table is vandalised with author text; the reset PC (`$6500034A` → `$00034A`) and SSP
  (`$00005468` → `$005468`, in ROM) are both odd. The ROM presumably fixes the stack early. Not
  investigated — irrelevant to the finding.
- capstone 5.0.7's M68K disassembler returned zero instructions for several ranges that decode fine by
  hand; the sequence in §1 was hand-decoded and should be re-checked by anyone building on it.
- Do not name a `.py` helper `dis.py` in this workflow — it shadows the stdlib module capstone imports
  and produces a confusing circular-import error.
