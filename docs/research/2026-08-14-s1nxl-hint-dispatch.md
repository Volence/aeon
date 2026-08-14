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

The owner's question was whether our authoring vocabulary lets us build effects of this class.

**The relevant difference is not the op set — it is what the interrupt runs.**

| | S1NXL | Aeon |
|---|---|---|
| What HBlank executes | **arbitrary per-state 68000 code**, swapped by a 4-byte RAM write | one fixed handler (`Raster_HInt`) walking **per-section data** (`Sec.sec_raster_table`) |
| Adding a new effect kind | write a new handler; no engine change | add an **opcode** to the handler and a constructor to the DSL |
| Cost of a wrong handler | crash / corruption, at runtime | build-time `ensure` failure |
| Per-line budget | whatever that handler costs | ~60 cycles, enforced by construction |

Neither is strictly better and the project already chose deliberately. The data model buys build-time
validation, a single audited hot path, and a vocabulary that can refuse bad programs — which is the
whole premise of Effects P3. It pays for that by making every *new kind* of per-line work an engine
change rather than an authoring act.

**The practical consequence:** anything MarkeyJester does per line that our four opcodes cannot express
is a runtime change for us, not an authoring one. So the value of each additional opcode is high, and
the cheapest ones should be taken early. See §4.

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
| Per-column VSRAM shear | Raster | **Runtime can already do it; constructor missing.** `.op_cram` writes whatever VDP command it is handed — only `cram()`/`pal_region()` hardcode `VdpTarget.Cram` |
| Palette bands / glow | Raster DSL | **Covered** (`cram`, `pal_region`, `cycle_channel`) |
| Mid-screen plane base swap | Raster DSL | **Authorable today** — regs `$02`/`$04` are inside `set_reg`'s range |
| Player over the boss | Sprites | Normal |

So the raster tier is **not** the binding constraint for this effect class; VRAM is. But the tier is on
the path, and the missing VSRAM constructor sits squarely in the middle of it.

---

## 5. Recorded caveats

- The vector table is vandalised with author text; the reset PC (`$6500034A` → `$00034A`) and SSP
  (`$00005468` → `$005468`, in ROM) are both odd. The ROM presumably fixes the stack early. Not
  investigated — irrelevant to the finding.
- capstone 5.0.7's M68K disassembler returned zero instructions for several ranges that decode fine by
  hand; the sequence in §1 was hand-decoded and should be re-checked by anyone building on it.
- Do not name a `.py` helper `dis.py` in this workflow — it shadows the stdlib module capstone imports
  and produces a confusing circular-import error.
