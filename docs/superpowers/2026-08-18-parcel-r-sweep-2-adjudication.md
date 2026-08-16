# PARCEL R — sweep 2 adjudication. v2 stopped. What survives, and what does not.

**Date:** 2026-08-18
**Draft reviewed:** `specs/2026-08-18-parcel-r-bands-design-v2.md` @ `fb42e0f6`
**Seats:** correctness/state (Opus), hardware/timing (Fable), plus a Fable adviser on the composition
ruling. Sweep 1's adjudication (`2026-08-18-parcel-r-sweep-adjudication.md`) stopped v1.

---

## The one-line state

**The palette half is verified sound. The scroll half is wrong as designed. The register half is
dead by three independent arguments.** v2 as a whole does not proceed.

---

## What is now VERIFIED, not merely argued

The correctness seat traced the palette snapshot end-to-end rather than accepting it:

- `Palette_Compose` is main-loop-only; **nothing in VBlank writes `Palette_Buffer`**. Within one
  VBlank, `Enqueue_Dirty_Buffers` enqueues and `Process_DMA_Critical` drains with no writer between,
  so a snapshot at the `bclr` and the DMA that ships it read the **same buffer generation**. v1's
  skew is genuinely killed.
- The per-line drop-safety works mechanically: `bcs .skip_pal0` branches *before* `bclr #0`
  (`buffers.emp:242-243`), so a snapshot spliced at the `bclr` is skipped on a drop and retains the
  previous frame's value — which is what CRAM retains. Correct by construction, as claimed.
- Static records genuinely cannot be suppressed (`.suppress` is reachable only from the patchable
  `line_src` test), and a program overflowing the buffer is now a build error rather than a silent
  truncation.

That is the core mechanism, and it holds.

---

## What is WRONG, and the pattern behind it

### 1. The VSRAM source is not the frame-top source for any shipped config

`Vscroll_Write` reads `Parallax_Vscroll_Column_Buf` **only** when `pcfg_v_deform_table_bg != 0`. In
the whole-plane branch it writes ONE longword from `Vscroll_Factor` into entries 0-1 and never
touches entries 2..39. **Every shipped OJZ config is whole-plane** — `v_deform_bg` is set on exactly
two configs, none of them OJZ's. And `fx_vscroll_split` targets VSRAM byte 2 = entry 1 = plane B,
which in whole-plane mode is committed from `Vscroll_Factor`'s low word.

So a `vscroll_band` built to v2's table would restore garbage on every shipped section, on the exact
op named as the parcel's second half. The mode is not even static — `Parallax_Active_Config` returns
`Target` during a transition, so a band can straddle both modes in one crossing.

**Fix (known):** snapshot what `Vscroll_Write` EMITTED, mirroring its own mode branch — not a source
buffer it may not have read.

### 2. The off-screen ship invalidates both snapshots, on exactly the frames a band would matter

The ship queues `Static_Pal_Ship` **after** the four base-line DMAs, deliberately, so it wins over
the same entries. On a shipping frame CRAM holds VARIANT colours while a snapshot taken at the
`bclr` holds `Palette_Buffer`'s BASE. A band restoring at its bottom edge would paint the dry palette
back over a submerged screen — the artifact the ship exists to remove.

Sharper on the register side: the ship replays the fire's `set_reg` words straight to `VDP_CTRL`
**after** `Flush_VDP_Shadow`, and says so in its own comment. v2 places the register snapshot
"immediately after `Flush_VDP_Shadow`" — provably before the replay. That recreates, from the other
end, the defect commit `c5cac3a2` shipped to fix.

**Fix (ruled):** refuse a band on a channel that declares `offscreen_ship`. Cheap comptime guard, no
content needs the combination.

### 3. `OP_RESTORE_REG` is dead — three independent kills

- **Adviser:** for registers, overlap is the NORM. The blanket frame-top flush exists precisely so
  effects can touch one register without knowing about each other; refusing rejects legitimate
  composition, allowing silently kills another preset's excursion. The mechanism is wrong for the
  class. And a register band **already works today**: `fire(100,[sh_on()])` + `fire(140,[set_reg($8C81)])`,
  zero new opcodes.
- **Correctness:** a new opcode does not inherit `set_reg`'s `$8A` ban, and reg `$0A`'s shadow byte is
  the schedule's own scratch (`HBlank_Install` writes it every `Raster_VBlank`, left at 0 for
  priming). `restore_reg($0A)` assembles `$8A00` = fire-every-line and detonates the relative-arm
  chain from the band's bottom edge down.
- **Hardware:** ~210-240 cycles charged as ZERO by the density model, plus the measured ~45%
  mid-line mode-register seam on the band's bottom row.

**Ruled: dropped from v1.** §6's guard also could not see the register collision the sweep-1
adjudication called the worse half — dropping the opcode collapses that gap too.

### 4. "Every existing path stays byte-identical" is false

Any new opcode adds a rung to the compare chain, taxing the `OP_SET_REG` fall-through ~16-40 cycles.
That would be inert, except `check_mixed_fire` forces SetRegs BEFORE CRAM ops and the shipped OJZ
water fire is `sh_on() + pal_region` — so the tax lands upstream of the CRAM command write,
displacing the oracle-calibrated landing by ~28-35 px against a ~40-cycle `EFX_BLANK_DELAY` margin.

There is no placement that avoids it: the fall-through IS an existing op. **The honest fix is to stop
claiming byte-identity and book the oracle recalibration**, which the delay constant's own comment
instructs when the prologue changes.

### 5. The pattern worth naming

Both sweeps killed the draft the same way: **I verified a result for the palette and generalised it
to sources I did not re-verify.** v1 generalised "the buffer is maintained" without checking its
phase; v2 generalised "snapshot at the commit point" without checking that the named buffer IS what
the commit reads. The discipline this needs is per-source derivation, not a table.

---

## Smaller findings worth keeping

- **The drop path is not reachable today.** `DMA_CRITICAL_SLOTS = 8`; steady-state Critical use is 7
  (4 palette + ship + sprite + HScroll), and art staging rides Important. So §2.2's justification was
  overstated — the per-line splice is still right (it is free and correct if the path ever opens) but
  should be grounded on "the enqueue and the bit-clear are the same event". **And §8's drop gate
  cannot be built** without adding a synthetic 8th Critical enqueuer that exists only for the gate.
  `buffers.emp:233-235`'s own "reachable during a fade" comment is stale for the same reason.
- **Nothing in the format knows the two fires are a pair.** A band is the first construct where two
  records must live or die together, and v2 encodes that nowhere. At minimum it should be checkable
  at comptime (a restore must have a matching effect op on a strictly-earlier line naming the same
  target and count).
- **The overlap guard's real false-positive is CRAM vs VSRAM**, because "CRAM-class" in this codebase
  INCLUDES `Vsram`. The guard must key on target, and run on the COMPOSED program.
- **The guard as written refuses every band** — the own-pair exemption must be stated — and must
  measure overlap worst-case over patchable fires' reachable bands, or it goes vacuous the moment an
  anchor moves.
- **The banded palette line is dirty every frame by construction** (`prog_mask` ORs `op_mask`;
  `Raster_VBlank` re-asserts), which answers the first-frame/never-dirty question — pin it as an
  invariant rather than leaving it a happy accident.
- **Two more bandable sources exist**: the dense tier (a ramp is a band with no bottom edge —
  `Raster_Dense_Lines` counts down and simply resumes, leaving the last value), and reg `$0B` MODE3.
- **Budgets bands halve:** the ~64-word program ceiling gives roughly **4 colour bands per program**,
  on top of the `RASTER_MAX_PATCH` band budget.
- Minimum band heights fall out of the density model: 3 screen lines for a 3-colour band, 2 for a
  1-word one. The constructors should refuse the degenerate cases by name.

---

## Where this leaves the parcel

**Palette-only is buildable now.** Its mechanism is verified, its guard is computable, its gate is
the committed scene harness plus a handler-observing breakpoint, and its remaining costs are known
(oracle recalibration for the mixed-fire shift; a density re-measurement).

**Colour + scroll needs one more design pass** — not a big one, and the fix is named: derive the
VSRAM snapshot from what `Vscroll_Write` emitted, mode-aware, rather than from a source buffer.

**Registers are out**, and a register band is already expressible today without this parcel.

The owner chose colour + scroll over colour-only on the reasoning that "if the format is going to
move, it should move once". That reasoning still holds — the wire format question is settled either
way (one new opcode, no existing op touched). What changed is that the scroll half needs its own
derivation rather than inheriting the palette's, which is a design cost, not a format cost.
