# PARCEL R1 — palette bands (mid-screen restore). Design draft v3.

**Date:** 2026-08-16
**Status:** DRAFT — for adversarial sweep. Nothing here is ruled.
**Supersedes:** `2026-08-18-parcel-r-mid-screen-restore-design.md` (v1, killed by sweep 1) and
`2026-08-18-parcel-r-bands-design-v2.md` (v2, killed by sweep 2).
**Scope authority:** the 2026-08-16 Fable ruling, which the owner pre-committed to.

> **READ THIS FIRST.** Two drafts died here, and the audit that killed the second one showed that
> **an adjudication MINTS fixes, and those fixes enter the next draft UNSWEPT** — sweep 2 minted
> four fixes and the audit holed three of them. Every numbered CLAIM in this draft is a claim to be
> swept, not a ruling to build on. Positive claims ("this is sound") need more redundancy than
> kills: a kill needs one witness, soundness has to survive all of them. Where a claim is grounded
> N independent ways, N is stated.

---

## 1. What this builds

An effect that turns ON at a scanline and OFF again at a lower one — a fog slab, a top-half glow,
a tinted band. Today every raster effect runs from its start line to the bottom of the screen,
which makes bands the single largest hole in the effects vocabulary.

The OFF edge is the whole problem. To turn an effect off mid-screen the handler must stream the
**pre-effect base colours** back into CRAM, and those colours must match what CRAM actually
received this frame — otherwise the bottom of the band is a different palette from the rest of the
screen.

### Scope, per the ruling

- **Palette only.** No register restore, no scroll restore.
- **ONE band per program** — at most one restore op in the whole composed program.
- **Static bands only.** A *moving* band stays booked (§9).
- Scroll bands are **re-homed to queue item 2** (the VSRAM op-class split), not deferred vaguely.

---

## 2. The mechanism

A new engine-owned 128-byte buffer, `Palette_Ship_Snap`, holding a per-line copy of
`Palette_Buffer` taken **at the moment each palette line's frame-top DMA is enqueued**. The restore
op streams from it.

### 2.1 The splice point

`engine/system/buffers.emp:236-262`, quoted verbatim (line 0; lines 1-3 identical):

```
237         move.b  Palette_Dirty, d0
238         beq     .no_pal
239         btst    #0, d0
240         beq     .skip_pal0
241         queue_static_dma(Static_Pal_Line0)
242         bcs     .skip_pal0                      // dropped -> leave bit 0 set
243         bclr    #0, Palette_Dirty               // enqueued -> clear bit 0
244     .skip_pal0:
```

The snapshot for line 0 goes **adjacent to the `bclr` at :243**. Both guard branches — not-dirty
(`beq`, :240) and dropped (`bcs`, :242) — are upstream of it, so the copy happens **iff the line
was dirty and its DMA entry was accepted**. On a clean or dropped line the snapshot is not written
and retains the previous frame's value, which is exactly what CRAM retains, since no DMA was
queued for that line.

That is correct **by construction**, not by argument. It is the reason the splice is per-line at
the `bclr` rather than a single 128-byte copy somewhere convenient.

### 2.2 The invariant

> **`Palette_Ship_Snap[line]` equals THIS FRAME'S base-DMA payload for that line.**

Deliberately *not* "byte-identical to what CRAM received at frame top". `VInt_DrawLevel` sits
between the enqueue and the drain (`vblank.emp:168-198`), so on a heavy frame the drain lands
after line 0 and the frame-top phrasing is false. The payload phrasing is what the `bclr` splice
actually pins, and it makes the drop-safety exact rather than incidental.

### 2.3 Why the snapshot is in phase — CLAIM 1

**Nothing in VBlank writes `Palette_Buffer`.** Grounded three independent ways:

1. Exhaustive writer census across `engine/` and `games/`. Every writer is main-loop:
   `Palette_Compose` base copy (`palette.emp:344-348`), `Palette_RotateSpan` (`:447-473`),
   `Palette_DoFade` (`:490-498`), `Palette_DoOperator` (`:574-578`, `:593-622`, `:631-635`), the
   `Player_RefreshPhysics` line-0 copy (`player_common.emp:517-524`, twice per session), and level
   /test init copies. Zero hits in `engine/system/vblank.emp`, `engine/debug/`, `engine/sound/`.
2. `Raster_VBlank` — the only palette-touching VBlank routine — writes only `Palette_Dirty`
   (`raster.emp:573-574`).
3. The HBlank handler streams from `Pal_Variant_Stage`, not `Palette_Buffer` (`raster.emp:733`).

**The lag path holds for a stronger reason than the one previously given.** Prior work argued
"`VInt_Lag` runs the same four steps in the same order". It does (`vblank.emp:291/293/294/337`),
but the paths are **not** equivalent: `VInt_Lag` omits `VInt_DrawLevel`, so its enqueue→drain gap
is *shorter*. The real argument is that the DMA source addresses are baked at boot
(`buffers.emp:13-16`: `SRC_PAL_LINE0..3 = Palette_Buffer + $00/$20/$40/$60`) and nothing in VBlank
mutates them, so a `Palette_Compose` torn mid-write by IRQ6 ships a half-composed buffer **and
snapshots that same half-composed buffer**. Snapshot == payload even on a torn frame.

*Falsifier:* any new VBlank-context writer of `Palette_Buffer`. See §8 on why nothing structurally
prevents one.

### 2.4 The drop path — CLAIM 2, and a correction to prior work

Prior work said the drop path is unreachable because `DMA_CRITICAL_SLOTS = 8` and steady-state
Critical use is 7. **The premise is wrong and the conclusion survives.** Level init can leave 2
entries queued when a VBlank lands (`ojz_scroll_test.emp:135`, `:145`, no drain between; `VInt_Lag`
also calls `Enqueue_Dirty_Buffers` at `vblank.emp:294`), so 2+7 = 9 **can** exceed 8.

What actually saves the palette lines is **enqueue order**: they go first (`buffers.emp:241, 247,
253, 259`), before ship/sprite/hscroll. With ≤2 pre-existing entries, 2+4 = 6 < 8, so the four
palette `bcs` arms are unreachable; only the sprite (`:325`) and HScroll drops can fire, and only
at init.

Consequences: the comment at `buffers.emp:232-235` claiming the drop is "reachable during a fade"
is **stale** (a fade adds no Critical entries — `Palette_DoFade` is main-loop arithmetic; art
staging rides the *Important* queue, `vblank.emp:206-215`), and **§8's drop gate cannot be built**
without a synthetic 8th Critical enqueuer existing only for the gate. The splice stays at the
`bclr` because it is free and correct if the path ever opens, grounded on "the enqueue and the
bit-clear are the same event" — **not** on the drop being reachable.

---

## 3. The opcode

`OP_PAL_RESTORE`, a **distinct `RasterOp` variant**, appended to the dispatch chain.

A distinct variant rather than a source-select flag on `PalRegion`, for two reasons: sigil's
exhaustiveness check names the missing variant on an omitted arm
(`sigil-frontend-emp/tests/eval_match.rs:101`), so all 12 match sites become build errors; whereas
a flag changes *arity* at every site, and while construction arity is checked
(`[enum.payload-arity]`), **arm-pattern arity checking is UNVERIFIED**.

Runtime body: `OP_PAL_REGION`'s, with `lea Palette_Ship_Snap, a2` in place of
`lea Pal_Variant_Stage, a2` (`raster.emp:733`). Same `EFX_BLANK_DELAY`, same word loop, same
`RASTER_CRAM_MAX` ceiling. The offset arithmetic is one term simpler: `line*32 + entry*2`, with no
variant slot.

### 3.1 THE PIN DOES NOT SELF-DETECT AN APPEND — CLAIM 3, and this one is load-bearing

The cost model pins dispatch depth at `raster_dsl.emp:843-844`:

```
ensure(RASTER_DEPTH_CRAM == (OP_CRAM - OP_CRAM) / 2
    && RASTER_DEPTH_REGION == (OP_PAL_REGION - OP_CRAM) / 2
    && RASTER_DISPATCH_RUNGS == (OP_RUN_RAMP - OP_CRAM) / 2 + 1, ...)
```

It names **`OP_RUN_RAMP` by name** as the chain's last rung. Appending `OP_PAL_RESTORE = 10` does
not move `OP_RUN_RAMP`, so the pin still evaluates to `(8-2)/2 + 1 = 4` and **passes while the real
chain is five rungs long**. The ruling's "update three literals" is therefore not enforced by
anything: forgetting it silently under-charges every `set_reg` by 16 cycles with a green build.

**R1 must re-spell this ensure against the new last opcode.** Two things catch the omission if it
re-occurs:

- `RASTER_DISPATCH_RUNGS` 4→5 re-prices only the fall-through, `SetReg`, by +16
  (`op_dispatch_cyc:849`). That breaks two *measured* equality ensures: **F1** 396→412
  (`:925-926`) and **F5** 612→628 (`:933-934`). Both must be re-measured on the new ROM.
- The **F1 hardware fixture** added to `effects_gates.py` on 2026-08-16 (`9a60fc87`) is the only
  gate in the tree that exercises the fall-through op, so it is the only one that can see this.
  F0 and F3 both dispatch at depth 0 and would recompute and pass blind.

*Falsifier:* re-derive `(OP_PAL_RESTORE - OP_CRAM)/2 + 1 = 5` and confirm F1 measures 412.

### 3.2 The +16 mixed-fire tax — CLAIM 4

`check_mixed_fire` forces SetRegs before CRAM ops (`raster_dsl.emp:1099`), and the one shipped
mixed fire is OJZ's water, `sh_on() + pal_region`. So +16 on the `set_reg` pushes the
`pal_region`'s CRAM command write 16 cycles later, against an `EFX_BLANK_DELAY` of 4 `dbf`
iterations tuned to "the ~40 cyc from mid-handler to the active-display edge on an H40 line"
(`raster.emp:214-217`).

This is **neither free-by-arithmetic nor a booked recalibration — it is one mandatory
measurement.** The delay places the colour burst ~14 cyc past the display edge, three words span
~74 more, the blanking window is ~97: +16 puts the last word at the window's edge, inside the
error bars of the "~40 cyc" and "~10/dbf" approximations. It is not decidable from constants.

**TRAP, ruled: if it fails, do NOT retune `EFX_BLANK_DELAY`.** The tax is per-op-mix; the delay is
global. Retuning fixes mixed fires by breaking unmixed ones.

Measurement protocol in §7.3.

---

## 4. Guards

### 4.1 One band per program — CLAIM 5

The ensure goes in **`raster_program` (`raster_dsl.emp:1124`)**, not `patched_program`.
`patched_program` calls `raster_program` (`:1426`), so an ensure in the former covers both entry
points; the reverse misses every static program. `raster_program` already walks
`for f in fires { ... fire_ops(f) ... }` (`:1163-1170`), so the count is free.

Ops are opaque enum values at that point — there is no field access — so this needs a new total
helper `op_is_restore`, shaped like `prog_mask` (`:737-745`).

One restore per program collapses three problems at once: the pairing predicate (one band, one
restore, no ambiguity), the cross-band overlap guard (nothing to overlap with), and the merged-fire
ordering problem. That is the whole reason the scope is what it is.

*Falsifier:* a two-band content request. The relaxation must then bring an **entry-ownership
representation**, not delete the ensure — the audit proved an existence check cannot substitute,
because two legitimate bands can share target and count (a mist band and a water band tinting the
same accent entries at different depths).

### 4.2 Program-keyed ship refusal — CLAIM 6

**The problem.** The ship queues `Static_Pal_Ship` **after** the four base-line DMAs, deliberately
(`buffers.emp:273-276`, comment quoted in the derivation: "*a ship queued BEFORE it would be undone
in the same frame*"). On a shipping frame CRAM holds VARIANT colours while the snapshot holds BASE.
A band restoring at its bottom edge would paint the dry palette back over a submerged screen — the
exact artifact the ship exists to remove.

**The refusal.** In `raster_program`: refuse a program that contains a restore op AND a fire with
`fire_offscreen_ship(f) == 1`. Both halves are in scope in one loop — `raster_program` already
reads `fire_is_patch`/`fire_channel` (`:1146-1153`), and `fire_offscreen_ship` (`:581-586`) is a
sibling accessor over the same array.

**Why program-keyed and not channel-keyed.** A static band carries no channel: `fire_channel`
returns **-1** for `RasterFire.Fire` (`:573-578`), so sweep 2's channel-keyed guard could never
fire. Verified.

**Why not entry-overlap.** The ship's destination is a raw CRAM byte address plus a count
(`raster.emp:996-998`, comptime `op_ship_cram_addr:675-682`), and the channel word is used only
for the off-screen test (`buffers.emp:287-291`), never for the destination. So a band on a
*different* channel covering those entries breaks identically. An overlap guard would have to model
CRAM ranges and would key on a quantity the DMA does not.

**A static program cannot carry a ship at all** — two independent witnesses: `RasterFire.Fire` has
no ship field (`:90`), and `Raster_VBlank`'s copy path **clears** `Effects_Offscreen_Entry` on both
branches (`raster.emp:539`, `:552`).

**Completeness, qualified.** `Effects_Offscreen_Entry` has exactly ONE nonzero publish site
(`raster.emp:952`), with clears at `:539`, `:552`, `:915`, `preset.emp:227`. Four attacks failed to
falsify: no address-taken aliasing; no neighbour-array overrun (`Effects_World_Y`/`Effects_Screen_L`
writers are all bounded by `RASTER_MAX_PATCH`); exactly one caller of `Raster_InstallPatched`
(`preset.emp:288`); the only other writers are test scaffolding writing 0.

**But `complete` must be qualified to "complete over programs actually built by
`patched_program`".** `preset(patched: Label)` is untyped (`preset.emp:119-120`) and
`Raster_InstallPatched` reads the trailer count word sight-unseen (`raster.emp:916`), so binding a
non-`patched_program` template would publish a ship no comptime guard ever saw. **That is a
pre-existing mis-authoring hazard, not one R1 introduces**, and R1 should not silently inherit the
word "complete".

**Correction to the framing carried from sweep 2.** `patchable`'s existing ship guard
(`raster_dsl.emp:355-358`) requires exactly one `stream_pal_region` op, and
`count_stream_pal_region_ops` matches only the `PalRegion` arm (`:660-671`). So a fire whose *only*
op is a restore **already fails** that ensure (count 0). The dangerous shape is a fire carrying
**both** a region and a restore — count 1, passes, and `ship_trailer` silently picks the region op
via `if op_ship_cram_addr(o) >= 0` (`:1293`). Either way the refusal is a **new** guard; the
existing one cannot be repaired into it, because the fact it needs (the op's source base) does not
exist in the op.

**Content cost of the refusal today: zero.** Exactly one fire in the tree declares
`offscreen_ship: 1` (`ojz_effects.emp:638-639`, in `OJZ_TC_PROG`), and no shipped program contains
a restore op because none exists.

### 4.3 Guards that need nothing — and the one trap in keying

Derived per-guard, not assumed:

- `check_intervals` (`:982-992`) — op-agnostic, needs no arm. It is already what forbids two
  overlapping bands.
- `check_density` (`:1014-1036`) — op-agnostic, but **inherits** the new op's cost through
  `op_cost_cycles` (`:867-869`). It is silently right only if `op_work_cyc`/`op_dispatch_cyc` are
  right, which §7.2 measures.
- `check_mixed_fire` (`:1082-1102`) — keys on `op_is_reg`; a restore returning 0 is handled
  automatically.
- `check_arm_layout` (`:1347`), `check_rec_layout` (`:1375`) — layout only, via `op_size`.

**TRAP: any overlap guard must key on `op_mask` bits, NOT on op class.** "CRAM-class" in this
codebase **includes `Vsram`** — verified three ways: `op_is_reg:727` returns 0 for it,
`op_dispatch_cyc:852-853` dispatches it at the CRAM rung ("A Vsram op EMITS OP_CRAM"), and
`op_words:603-606` emits opcode literal `2`. `op_mask` is deliberately 0 for `Vsram` (`:714-719`).
A class-keyed guard would false-positive on `OJZ_TC_PROG`, which is exactly
`fx_tint_band` + `fx_vscroll_split` (`ojz_effects.emp:637-642`).

---

## 5. The 12 match sites

All in `engine/effects/raster_dsl.emp`; `grep -rn "RasterOp\|RasterFire" --include=*.emp` outside
that file returns zero hits. Every omission is a **build error**, not a silent hole.

| site | line | the restore's arm |
|---|---|---|
| `op_words` | 589 | `[OPCODE, cmd>>16, cmd&$FFFF, n-1, <snapshot offset>]` |
| `op_size` | 620 | 5 — must agree with `op_words`; `raster_program:1181` cross-checks |
| `op_stream_words` | 634 | `n` — feeds the `RASTER_CRAM_MAX` ceiling (`:288`) |
| `count_stream_pal_region_ops` | 660 | 0 — a restore is not shippable |
| `op_ship_cram_addr` | 675 | -1 |
| `op_ship_stage_off` | 683 | -1 |
| `op_reg_word` | 692 | 0 |
| `op_ship_count` | 700 | 0 |
| `op_mask` | 709 | `1 << (a >> 5)` — it writes CRAM (`:643-647` records the P1 bug from getting this wrong) |
| `op_is_reg` | 727 | 0 — stream class |
| `op_dispatch_cyc` | 846 | new depth constant, §3.1 |
| `op_work_cyc` | 857 | `RASTER_WORK_REGION_CYC` (122) if the body is the region body — **UNVERIFIED until measured** |

Plus: the opcode const in `raster.emp` beside `:94-173`, and a new `beq` rung in the compare chain
at `:694-701`.

---

## 6. Authoring surface

### 6.1 `band(...)` — the first two-fire helper

Every existing preset returns a **one-element** list (`fx_sh_below:480`, `fx_vscroll_split:494`,
`fx_tint_band:524`); `compose` is currently the only multi-fire producer. A `band(...)` returning
`[fire(top, ...), fire(bottom, [restore])]` would be the first helper that emits two fires from one
call.

It must follow `fx_tint_band`'s two disciplines: **inline the staging arithmetic** rather than
calling `pal_stage_off` (`:503-515` records that bug shipping broken for two parcels — a comptime
fn's free names resolve at the CALL SITE), and derive the CRAM address from `pal_line`/`entry` so
the address/line agreement ensures cannot fail.

It **cannot** be handed to `patchable`, which hard-refuses a multi-fire list (`:331-332`).

### 6.2 Minimum band height

Falls out of the density model, and the constructors should refuse the degenerate cases **by
name** rather than emitting a program `check_density` rejects with a less helpful message: 3 screen
lines for a 3-colour band, 2 for a 1-word one.

### 6.3 Budget

`RASTER_BUF_SIZE = 128` ⇒ a 64-word ceiling (`ensure(out.len * 2 <= 128)`, `:1179-1180`);
`patched_program` pads to exactly 64 (`:1429-1431`). Fixed overhead is 7 words (mask, two priming
records, terminator; `raster_words:1112`), then `2 + Σ op_size` per fire.

- `sh: 0` — ON fire 7 words + restore fire 7 = **14/band** ⇒ `(64-7)/14 = 4` bands.
- `sh: 1` — ON fire gains a `SetReg` (`op_size` 2) ⇒ **16/band** ⇒ `(64-7)/16 = 3` bands.

The "~4 bands" figure carried from sweep 2 is confirmed **for the `sh:0` shape only**.

---

## 7. RAM, cost, and what must be measured

### 7.1 Placement

`Palette_Ship_Snap: [u8; 128]` at the **RAM tail, before `mark Engine_RAM_End`**
(`engine/ram.emp:972-974`), and **before** the `if DEBUG == 1 @shape_divergent` block at `:965-970`
so both shapes keep equal offsets.

This is the file's own stated idiom, written four times (`:950-952`, `:874`, `:891`, `:962`): "*the
addition ripples ZERO existing engine-RAM addresses*". The two alternatives both cost more —
adjacent to `Palette_Buffer` (`:225`) ripples every address below it into a mass repin, and inside
`Palette_State` (`:390-410`) trips the palette-side span guard `PALETTE_STATE_SIZE`
(`palette.emp:91-92`), which would have to be updated.

### 7.2 Cost — ESTIMATE, and it must be measured before merge

- **Bytes.** Worst case (4 lines dirty) 128 B/frame. Steady state on OJZ **32 B/frame**: its
  programs declare `pal_dirty_mask %0100` (`ojz_effects.emp:128`, `:251`), line 2 only, re-asserted
  every frame by `Raster_VBlank` (`raster.emp:573-574`).
- **Loop shape.** Eight unrolled `move.l (a1)+,(a2)+` per line, **not** `movem.l`. `d0` is
  contractually live across all four splices (`buffers.emp:37-38`), so no data register is free for
  a `dbf` counter, and `movem.l` would need 8 registers and widen `clobbers(d0/a1-a2)` into both
  VBlank handler unions (`vblank.emp:105`, `:269`). The unrolled form needs neither. ~20 cyc per
  `move.l` ⇒ **~176 cyc/line**, ~704 worst case, ~176 steady state. `movem.l` would save ~7% —
  not worth the contract change.
- **Position.** Inside the DMA window bracket (`vblank.emp:122-126` / `:131`), **before**
  `Process_DMA_Critical` (`:200`), so it does not contend for DMA bandwidth — but it lengthens the
  window ahead of the drain, eating blanking headroom for `Process_DMA_Important`/`_Deferrable`.
- **It is NOT charged against `DMA_Budget_Remaining`**, which counts DMA bytes only
  (`vblank.emp:168-190`). So that budget will **under-report** the VBlank window once this lands.
  Stating it here so it is not rediscovered as a defect.

**Required before merge:** oracle profiler VBlank row before/after on the same scene; sigil's
actually-emitted sequence read from the listing; and whether `Process_DMA_Deferrable` starts
dropping work on a worst-case 4-line frame.

### 7.3 The +16 landing measurement

**It cannot ride `effects_gates.py`.** Landing position is a pixel property, and gates in this tree
may select and assert on emulator REPORT fields but may never read pixels. This is a one-off
controller-run measurement, recorded in `docs/benchmarks/`.

**Method: column-bucket brightness across the S/H seam row**, the P2 protocol
(`docs/benchmarks/effects-p2/GATE-EVIDENCE.md:171-178`), with the camera pinned by
`Debug_Scene_Freeze` and a reset before capture. Recorded baseline:

```
row 118:   5.3  10.3  25.1   7.8   5.3  10.3  25.1   7.8   5.3  10.3   (all unshadowed)
row 119:  10.3  10.3  22.3   2.8   5.1   5.1  10.8   1.4   5.1   5.1   (switch ~bucket 3)
row 120:   6.6   5.5  13.1   2.5   6.6   5.5  13.1   2.5   6.6   5.5   (all shadowed)
```

**Buckets must be 8 px, not 32.** +16 cycles is ≈15 px ≈ half a 32 px bucket — unresolvable at the
recorded granularity.

**Do NOT use the vertical-boundary pixel count.** P1's `CORRECTION`
(`docs/benchmarks/effects-p1/GATE-EVIDENCE.md:124-159`) records that method as confounded: "zero
target pixels above row N" only bounds the effect if the art on those rows uses that palette entry
at all, and at OJZ's camera positions the brown ground begins right at the split. Per-scanline CRAM
probing cannot substitute — oracle's CRAM read is frame-latched.

The S/H seam is measured on a **mode register that shadows the whole row**, so it does not depend
on which entry the art uses. That is why it is the right instrument here.

**Two quantities, and only one of them is a failure:**
1. The S/H seam moving right by ~15 px is **expected** and harmless — it is a pre-existing,
   deliberately-unfixed residual (`raster.emp:207-212`).
2. The `pal_region` colour words spilling out of HBlank into the visible row is the **failure**,
   and it shows as a partial tint appearing on the row where none was.

---

## 8. The structural finding this parcel does NOT close

**The engine has no single frame-top commit seam.** Frame-top state is the emergent tail of an
ordered pipeline — flush, raster install, palette enqueue, ship register replay (deliberately
POST-flush), ship DMA (deliberately POST-base-lines), queue drain — with mode-dependent emitters.
"Snapshot at the commit point" is not one mechanism; it is N mechanisms, each re-deriving that
tail, and **any future frame-top writer silently invalidates the snapshot**.

The proposed mitigation is a comptime registry of frame-top committers, so adding one without
declaring its band interaction is a build error — the contract-closure idiom used elsewhere in this
codebase.

**CLAIM 7, flagged SOFT by the ruling seat and NOT resolved here:** the *enforcing* form is
**UNVERIFIED** — no grounded build-time mechanism is known that detects an unregistered
CRAM-reaching writer. The **advisory** form (a census plus an `ensure` pinning its length) is the
floor and is buildable. R1's design pass must attempt the enforcing form; failing that, ship
advisory and state the residual risk in the invariant's own comment.

This is deliberately not gating R1. Gating shippable, verified work behind an unproven enforcement
idiom is caution-by-precedent.

---

## 9. Ruled out, and booked with preconditions

- **`OP_RESTORE_REG` — dead**, three independent kills, the decisive one being that a register band
  is already expressible today as `fire(100,[sh_on()])` + `fire(140,[set_reg($8C81)])` with zero
  new opcodes.
- **Scroll bands — re-homed to queue item 2.** Third independent derivation of the kill:
  `Vscroll_Write` reads `Parallax_Vscroll_Column_Buf` only when `pcfg_v_deform_table_bg != 0`
  (`parallax.emp:385`); the whole-plane arm writes one longword from `Vscroll_Factor` (`:413`) and
  never touches the column buffer, and **every shipped OJZ config is whole-plane**. Deeper, and
  fatal to the v2 fix: `vsram(2, ...)` *means* "all of plane B" in whole-plane and "column 0's
  plane B only" in per-column, so the author's band is wrong before any restore exists — and
  `Parallax_Active_Config` returns `Target` during a transition, so a band can straddle both modes
  in one crossing.
- **N bands** — booked behind an entry-ownership representation (§4.1).
- **Moving bands** — booked behind the band-as-first-class-representation question, which is
  genuinely open: `patchable` hard-refuses a two-fire list (`:331-332`) and GUARD 11 refuses the
  two fires marked separately on one channel (`:1150-1151`). Do not solve this speculatively.
- **EFX-4b is adjacent and untouched.** `Raster_VBlank .copy_program` copies a fixed 128 bytes from
  any static ROM program and static programs are not padded, so ~122 bytes of adjacent ROM land in
  `Buf_A` past the terminator. Harmless because the walk stops at `RASTER_OPS_END`. R1 neither
  fixes it nor depends on it.

---

## 10. Gates

1. **`raster_source_gate` extended to the restore op** — it already breaks at `.region_loop` and
   reads the computed source pointer; the restore arm gets the same treatment against
   `Palette_Ship_Snap`. This is the only gate in the tree that observes the handler rather than the
   program's words, and a build that encodes the snapshot offset correctly and streams from
   `Pal_Variant_Stage` anyway passes every other gate.
2. **F1 and F5 re-measured** (§3.1). F1 is the only fixture that can see the dispatch tax.
3. **Snapshot == payload, asserted at runtime.** An end-of-VBlank RAM comparison of
   `Palette_Ship_Snap` against the four static DMA source spans. This asserts the actual invariant
   (§2.2) rather than a proxy.
4. **A poison for the one-band ensure** — a two-restore program must fail the build. An
   unreferenced `const` is inert in `.emp`, so the poison needs an `ensure` that reads it.
5. **Comptime hand-twin** of a band program plus `first_mismatch` **and** a separate `.len` ensure
   — `first_mismatch` is blind in both directions without the paired length check (`:1453-1460`).

**Not a gate:** the +16 landing measurement (§7.3), which is pixels and therefore evidence, not a
gate.

---

## 11. `.emp` gotchas this design must respect

- Expressions **cannot span lines**. A multi-line `&&` in an `ensure` condition is a parse error;
  breaking after the `,` between condition and message is fine.
- A comptime fn's free names resolve at the **call site** — inline constants in comptime fn bodies,
  never imported ones (`:14-25`, and `:396-404` records a spelled constant collapsing a range to
  empty and emitting zero fires with **no diagnostic**).
- `{...}` in an `ensure` message is an interpolation, so `{A,B}` breaks (`:40-42`).
- An unreferenced `const` is **inert** — a poison probe needs an `ensure` that reads it.
- `data` enforces its declared length; `const` does not (`:1110`).
- No indexed assignment — accumulate with `m = m | bit` (`:1135-1144`).

---

## 12. The claims, collected, for the sweep

| # | claim | confidence | falsifier |
|---|---|---|---|
| 1 | Nothing in VBlank writes `Palette_Buffer`; snapshot == payload even on a torn frame | high, 3 ways | a new VBlank-context writer (§8) |
| 2 | The palette drop arms are unreachable, saved by enqueue ORDER not slot count | high, 2 ways | a Critical enqueuer added ahead of the palette block |
| 3 | The dispatch pin does not self-detect an append; F1/F5 move | high, re-derived | `(8-2)/2+1 = 4` recomputed; F1 measures 412 |
| 4 | +16 is one measurement, not free and not a recalibration | medium | the measurement itself |
| 5 | One band/program collapses pairing, overlap and ordering | high | a two-band content request |
| 6 | Program-keyed ship refusal is writable and complete *over `patched_program` output* | high writable (quoted), medium-high complete | a second publish site; a non-`patched_program` template bound to `preset(patched:)` |
| 7 | The committer registry's enforcing form | **UNVERIFIED** | attempt it in the design pass |
| 8 | Snapshot cost ~176 cyc steady / ~704 worst | **ESTIMATE, unmeasured** | profiler row before/after |
| 9 | `op_work_cyc` = `RASTER_WORK_REGION_CYC` | **UNVERIFIED** | `raster_cost_probe` fixture on the new op |
