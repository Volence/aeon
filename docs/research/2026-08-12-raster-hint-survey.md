# Raster / HInt survey — effects suite Phase 1

**Date:** 2026-08-12
**For:** `docs/superpowers/plans/2026-08-11-effects-p1-raster-core.md` Task 0
**Why:** the sparse raster dispatcher reprograms VDP reg `$0A` per event. Everything
about whether that is even possible lives in this register's reload timing.

---

## Q1. VDP reg `$0A` (HInt line counter) semantics

**Reload points.** Reg `$0A` is a *reload source*, not the live counter. The internal
counter reloads from it (a) on every line during VBlank, and (b) **at the instant of
underflow — simultaneously with HINT-pending being set**, i.e. before the 68000
executes one instruction of the handler. It decrements once per line for lines
`0..=224` inclusive. HINT-pending sets at H=`$A6` (H40); the V-counter has already
incremented, so **V reads L+1 while the handler for line L runs**.

Sources: Eke, SpritesMind t=787 (hardware-verified); local pinned recon
`oracle-next/docs/2026-07-16-vdp-recon.md:240-264` (R7); implementations agree —
`oracle-next/crates/oracle-core/src/vdp.rs:1341-1357`, Genesis Plus GX
`core/system.c`, BlastEm `vdp.c:1877-1885`.

**Spacing = value + 1.** From the official Sega *Genesis Technical Overview* v1.00:
`$0A`=0 → every line, 1 → every other line, 2 → every third. Corroborated in-tree:
`s2disasm/s2.asm:1253` (`#$8A00|223` commented "every 224th line"),
`skdisasm/s3.asm:5798` (`#$8A6B` = 107, "every 108th").

**Fire line vs affected line.** Register writes in the handler for fire-line `L`
affect line `L+1` at the earliest — the manual: *"the CPU can control the display of
the next line but not the line on which the interrupt occurs."* So to make an effect
begin at screen line `M`, the fire must be at `M-1`.

**Ruling 1a — the delta formula.** For fire lines `L` → `M`:
`reg$0A = M - L - 1`, i.e. **BIAS = 1**. Confirmed by the only site in seven local
disassemblies that does true counter arithmetic — Batman & Robin
`disasm/code/engine/level_engine.asm:3148-3159`, which computes `screenY - 1`.
(Sonic 1/2/3K/S.C.E./Ristar write `screenY` raw and therefore land one line late —
the classic water-boundary slop. B&R is the correct one.)

**Ruling 1b — THE ONE-INTERRUPT PIPELINE LAG (load-bearing).** Because the reload
happens *at* the fire, a write to `$8Axx` from inside the handler does **not** govern
the current gap. The value written during handler `i` is consumed by the reload at
fire `i+1`, and therefore governs **gap(i+1 → i+2)**.

> TmEE, SpritesMind t=1511: *"The counter gets reloaded with value in the VDP register
> when interrupt happens, not when you write the value in. You write 20 now, and it
> takes effect starting from the next int."*

Empirical repro in that thread: a (20, 40, rest) gradient rendered as 20 / **20** / 40 —
every skip applied exactly one interrupt late; the reporter's fix was "look ahead one
entry." All three hardware-informed emulators read reg `$0A` at the fire instant, so
this reproduces on our verification path regardless of the silicon nuance below.

*Known unknown:* nothing documents a sub-line reload position, so no emulator can
distinguish "reload at H=`$A6`" from "reload at H=`$00` of the next line". Ristar's
chained script (`ristar_disasm/code/disasm.asm:14561`, `:14626`) reads as if the
effect were immediate. Treat as suggestive only; code against the lag.
**Falsifier:** set reg `$0A`=20 in VBlank and make the handler's first instruction
`move.w #$8A00,$C00004` — fires on 21,22,23… means no lag; 41,42,43… means real.

**Ruling 1c — never write reg `$0A` from the main thread during active display.** The
per-line evaluation happens at a fixed H position, so an unsynchronised write races it
(±1 line jitter). VBlank or the HInt handler only.

**Ruling 1d — Aeon-specific.** Mid-frame arming must write `$C00004` **directly**.
`HBlank_Install` programs reg `$0A` through the deferred VDP shadow + dirty mask
(`engine/system/hblank.emp:57-59`), which cannot land mid-frame. (This is also why
`Raster_VBlank` must run *before* `Flush_VDP_Shadow` — see the plan's correction.)

## Q2. CRAM writes during HBlank

**Budget.** H40 line = 3420 mclk; HINT sets at H=`$A6`; `$A6 → $00` ≈ 90 px ≈ 733 mclk
≈ **105 68k cycles**, less ~44 cycles of autovector exception entry ⇒ **≈60 cycles**
before the next line's active display. That is the binding limit — **not** the FIFO
(4 entries deep; CRAM/VSRAM cost 1 slot per word, VRAM 2).

Shipping confirmation: S3K's `HInt3` writes exactly **three colours per scanline**
(`skdisasm/sonic3k.asm:1027-1040`), and its own table comment says why
(`skdisasm/s3.asm:7109-7111`): *"to space out the CRAM writes to push the VDP dots
offscreen."*

**Ruling 2a — 3 CRAM words per HBlank** from a 68000 handler. `RASTER_CRAM_MAX = 3`
stands, and it is a *cycle* budget, not a FIFO one.

**Ruling 2b — CRAM dots are a single-port artifact, not a FIFO artifact.** CRAM is
single-ported and the pixel pipeline reads it every dot, so a write during active
display shows *the value being written* at the pixel being drawn (Nemesis t=291;
Mask of Destiny t=1510; md.railgun.works). The only mitigation is positional: keep
writes outside the visible 320 px, via `$C00004` bit 2 polling or cycle-counted
delays (S3K burns `dbf` loops, retuned per region — `sonic3k.asm:1018`, `:1038-1039`,
selected at runtime by measured VBlank length at `:9791-9793`).

**Ruling 2c — the S.C.E. `$700` premise in the plan was WRONG.** That delay is not an
HBlank loop and has nothing to do with HInt: it is a PAL-only wait in the **VBlank**
handler ahead of the CRAM DMA (`S.C.E./Engine/Core/Interrupt Handler.asm:24-31`), and
`$700` is an iteration count (~1793 × 10 cyc ≈ 36 scanlines) spending PAL's extra
blanking. There is no PAL/NTSC difference in the HBlank window itself (3420 mclk H40
on both). Nothing PAL-specific belongs in our HInt path.

## Q3. Shadow/Highlight (reg `$0C` bit 3) mid-frame

**It works and it shipped.** Mega Turrican 2-1 water is the canonical raster use: S/H
disabled at frame top, enabled partway down at the water line (rasterscroll.com,
*Shadow and Highlight*). Both BG planes and the player are low-priority so the shadow
applies; the seam is covered with flashing wave sprites.

**Ruling 3a — effect lands on the next scanline**, same 36-clock latch as any mode
register ⇒ fire at `screenY - 1`, consistent with Ruling 1a.

**Ruling 3b — never combine the S/H toggle with a V28/V30 change.** The one documented
mid-frame S/H quirk (Nemesis, VDP Internals p.2): with S/H on, toggling resolution
during active display leaves the bottom/top border at half brightness. Write the whole
register from a shadow copy with the resolution/interlace bits unchanged. Our
`$8C81` (H40, S/H off) → `$8C89` (H40, S/H on) satisfies this — bit 7 and bit 0
unchanged, only bit 3 moves.

**Corpus note:** across all seven local disassemblies there is **not one** `$8Cxx`
write from inside an HInt handler — every S/H toggle is frame-level (B&R
`main_loop.asm:4846`/`:4863`, Ristar, Vectorman). Mega Turrican's mid-frame toggle is
real but unprecedented locally, so we are implementing from the documented description,
not copying a local precedent. Verify on oracle accordingly.

---

## Format deltas — what this research CHANGED in the plan

1. **The dispatcher is re-architected around Ruling 1b.** The plan's design (walk to
   the next entry, write `next_line - cur_line - BIAS`) is **off by one event**: the
   value written during handler `i` is consumed at fire `i+1`. The shipped design
   instead makes each fire record carry a **build-time-precomputed arm word** equal to
   `L[i+2] - L[i+1] - 1`, and the program opens with **two priming records** (reg `$0A`
   = 0 in VBlank ⇒ cheap no-op fires at lines 0 and 1) so every subsequent fire lands
   exactly. Consequences: line comparisons and `Raster_Line` disappear from the runtime
   entirely (the schedule *is* the program order — build-time computation over runtime,
   per the project's stated principle), and the first real event must be at line ≥ 2
   (lines 0-1 belong to the VBlank init words anyway).
2. `RASTER_ARM_BIAS`/`RASTER_FIRST_BIAS` are retired as runtime constants — the bias
   now lives in the comptime arm-word constructor.
3. **Cycle budget is tighter than the plan assumed** (~60 cycles after exception entry
   before active display). A 4-register `movem` round trip alone is 40 cycles, so the
   handler's save set is minimised and CRAM entries stay ≤ 3 colours. Batman & Robin's
   every-line handler is ~26 cycles *because it saves nothing* (self-modifying RAM code,
   no registers touched) — noted as the Phase-2 lever if the dense tier needs it.
4. **Fire-every-line was considered and rejected** for the sparse tier: ~224 interrupts
   × ~84 cycles ≈ 11% of an NTSC frame, a constant cost even for a single event. Sparse
   dispatch costs `2 + events` interrupts. (Today HInt is genuinely dormant — the
   profiler's "HInt ~10.8%" bucket in DEFERRED_WORK is mislabelled VBlank/HScroll-DMA
   work; `HBlank_Install` has zero callers.)

---

## Q4. Reference-corpus HInt survey (TF4 / Vectorman / Gunstar / Alien Soldier)

ROM-verified (the linear-sweep `disasm.asm` files are desynced over several of these
handlers and render them as `ori.b #$0,d0` filler, so payload citations are ROM
offsets confirmed with Capstone).

| | Thunder Force IV | Vectorman | Gunstar Heroes | Alien Soldier |
|---|---|---|---|---|
| Vector `$70` | `$00C000` ROM trampoline -> RAM slot `$FFFFF0F8` | `$FFFF9D2E` (RAM code) | `$FFFFEE00` (RAM code) | `$FFFFEE00` (RAM code) |
| Idle state | stale pointer, IE1 off | `rte` stub copied from ROM | `rte` (`#$4E73`) | `rte` (`#$4E73`) |
| Handlers | 2 | 1 (2 configs) | 5 | 11+ |
| Registers saved | 1 | 1 (`a0`) | 0, or 2 | **0** |
| R10 reprogrammed *inside* a handler? | No | No | **Yes** | **Yes** |
| HInt used for parallax? | **No** | No (vscroll only) | Yes | Yes (heavily) |

**Ruling 4a — sparse counter reprogramming from inside the handler IS shipped
practice.** This refines Q1's "only Batman does counter arithmetic": Treasure does it
in both engines. Alien Soldier writes `#$8AFF` at ROM `$00169A` immediately after its
VSRAM write to park the counter so the interrupt fires **exactly once per frame** —
precisely our `.park` behaviour. Gunstar runs a mid-frame state machine (`#$8A80` at
`$001744`; `#$8A1F`/`#$8A8F` at `$00182C`/`$00183E`). So the sparse tier is not novel
and not risky; it is the Treasure idiom.

**Ruling 4b — RAISE TO IPL 7 AT HANDLER ENTRY (bug fix, applied).** The 68000 enters
IRQ4 at IPL 4, so IRQ6 (VBlank) can nest. Between an `OP_CRAM` command longword and
its following colour words, a nested VBlank would retarget the VDP address latch and
the colours would land wherever VBlank left it. Every long payload in the corpus opens
with `move.w #$2700,sr` (TF4 `$00C000`, Vectorman `$06D96A`, Gunstar `$001698`/
`$001704`/`$001782`, Alien Soldier `$0017D8`/`$001DF4`); the 3-instruction VSRAM-only
payloads omit it because they are atomic in practice. `rte` restores SR from the
stack, so the guard costs 4 cycles and nothing to undo.

**Ruling 4c — a reserved stream register is how the corpus affords a ~26-cycle
handler.** Alien Soldier saves ZERO registers and Gunstar often zero, because `a6` is
globally reserved as the per-line stream cursor and the foreground cooperates. Our
handler reloads its cursor from RAM and saves four registers (a 40-cycle `movem` round
trip inside a ~60-cycle budget). Parked as the Phase-2 lever if the dense tier needs
the cycles — it trades a global register reservation against the contract system, so
it is a deliberate design decision, not a micro-optimisation.

**Ruling 4d — per-line H-scroll belongs in the VBlank-DMA'd HSCROLL table, not HInt.**
TF4's famous 8-layer parallax is R11=`$8B03` per-line mode fed from a 192-entry RAM
table at `$FFFFE800`, DMA'd to VRAM `$F000+$80` each VBlank; its two HInt handlers
touch VSRAM word 0 only, and IE1 is off for 100% of gameplay. This is exactly what
Aeon already does in §4.6, and it confirms the split of duties: bulk per-line scroll
via the table, HInt reserved for what the table cannot express (mid-frame register /
CRAM / nametable changes).
