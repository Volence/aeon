# Regions v1: identity by rectangle

**Parcel 1 of the painted-regions project. Design spec and implementation plan.**
**Date:** 2026-09-09. **Status:** design only — this document changes no engine code.

> **⚠ §3.1 CARRIED A WRONG ROW AND IT IS NOW CORRECTED (2026-09-09,
> `parcel/section-effects-record-fix`).** The table headed "What act 1 looks like today,
> **verified**" said section 7's `ojz_act1_sec_scene(sec: 7)` **"returns 0, act default
> stands"**. It does not — section 7 has bound an editor scene since `c1d0a6be`, 2026-09-05,
> four days before this document was written and already present at `944c5cc0`, the SHA §0
> names as its verification point. **§4 step 1 transcribes that table 1:1 into the regions
> table**, so the row would have become a wrong region inside a migration whose entire proof
> is byte-identical behaviour. The row is fixed in place with the old text struck through,
> the other eight rows now state their derived verdict instead of leaving it implicit, and
> §3.1 also now carries the **frozen-name coupling** (`OJZ_Preset_*` /
> `EditorSceneBinding_OJZ_Act1_*`: reorder free, rename coordinated with sigil) that step 1
> must read before renaming anything. **If you are working from a copy of §3.1 taken before
> 2026-09-09, re-read it.** Nothing else in this document was re-verified by that parcel.
**Closure pass, 2026-09-09 evening — §10.** Q1, Q4, Q5, Q6 and Q7 are RESOLVED from source and
from builds in a clean worktree; the T1 baseline gate is GREEN on master; two findings §4 did not
have are booked there (the T1 gate itself reads the symbols step 3 deletes; the T2 gate's
expectation is derived from the wrong reference point). Net cost revises to **+152 emitted,
+12 RAM**. Open to the owner: Q2 only.

**Scope, stated before anything else.** This is parcel 1 and only parcel 1: *identity by
rectangle, no new rendering.* Parcel 2 ("the background belongs to the region") is **out of
scope and is not planned here** — it is blocked on an owner decision about VRAM budget that
this document does not attempt to pre-empt or route around. Where parcel 1 leaves a seam that
parcel 2 would use, the seam is named in one sentence and the sentence stops. Parcel 0
(cleanup) is substantially done; see `docs/research/2026-09-09-regions-study-reground.md` §2.

---

## 0. How this document was grounded, and what that is worth

**Every number below is re-derived from source in this worktree at
`944c5cc0`, not copied from the study or the re-ground document.** That rule is not ceremony:
the eleven-day-old study's coordinates rotted (the re-ground doc found 12 of 37 claims MOVED),
and this document's will rot too. So each figure carries the file and the arithmetic that
produced it, and where my reading disagrees with an inherited number the disagreement is
reported as a finding (§7).

**No emulator was used.** Every item wanting a running ROM is TAGGED in §8 for the
controller's foreground follow-up. No ROM was built in this worktree, so **no byte figure here
is a measurement** — they are emitted-byte derivations from instruction encodings, and §6.0
says exactly what that does and does not license.

**Reference-engine findings are inherited, deliberately.** The four-lens study of 2026-08-29
(plus a fifth report, `E-effects-feature-audit.md`, which the brief did not name — §7.6) swept
S3K, S2 and the aeon corpus for how other engines scope per-area identity. Redoing that sweep
would vary nothing, so §1.4 cites it rather than re-running it, and says plainly where the
sweep did *not* look.

---

## 1. What a region is

### 1.1 The one-sentence definition

**A region is a world-pixel rectangle that names an identity record.** The identity record is
the `EffectsPreset` the engine already has; the rectangle replaces the section grid as the
*scope* at which that record is bound. Storage — tiles, blocks, collision, objects, rings,
type tables — stays per section and is not touched.

### 1.2 What identity is today, verified

Identity is *not* the `Sec` record. It is `EffectsPreset`, reached through one pointer.

```
engine/structs.emp          pub struct Sec  — 34 bytes ($22), 8 fields
                              sec_effects:         *u8  @ $1C   ← the identity pointer
                              sec_parallax_config: *u8  @ $0C   ← rung 1 of the parallax resolve
engine/effects/preset.emp   pub struct EffectsPreset (size: 46)
                              ep_pal $00, ep_parallax $04, ep_raster $08, ep_patched $0C,
                              ep_cycle $10, ep_variants[2] $14, ep_patch_world_ys[4] $1C,
                              ep_transition $24, ep_patch_motion[4] $26
```

Both sizes read out of the declarations, not from prose. `sizeof(Sec) == 34` is `ensure`-pinned
in `engine/level/section.emp` and `engine/level/tile_cache.emp`; `EffectsPreset`'s `(size: 46)`
is checked by sigil's layout checker the moment the module is in a target's `use` closure,
which it is (`engine/level/parallax.emp:17`).

The crossing installs it: `Parallax_CheckBoundary` → `Effects_InstallPreset` →
`Effects_ResolveParallax`. That is **TOTAL BINDING** — every channel is written on every
install, and `_None` sentinels express "off", so nothing a previous scope set survives into a
scope that did not ask for it. Regions inherit that property unchanged; it is the reason this
parcel is a re-scoping and not a rewrite.

### 1.3 The record

```emp
// engine/structs.emp — proposed
pub struct Region (size: 16) {
    rg_x0:       u16,      // $00 — inclusive left,   world px
    rg_x1:       u16,      // $02 — inclusive right
    rg_y0:       u16,      // $04 — inclusive top
    rg_y1:       u16,      // $06 — inclusive bottom
    rg_effects:  *u8,      // $08 — EffectsPreset*; REQUIRED, no `= 0` default
    rg_parallax: *u8 = 0,  // $0C — outranks ep_parallax; 0 = defer (Effects_ResolveParallax rung 1)
}
```

**Sixteen bytes. Four decisions in it, each with its reason.**

**(a) The rectangle is stored span-major per axis (`x0, x1, y0, y1`), not corner-major
(`x0, y0, x1, y1`).** This is the only field-order decision that costs bytes, and it is worth
12 of them. The crossing caches the live rectangle in RAM (§2.3); with the span-major order
that cache is two `move.l`s (6 bytes each) instead of four `move.w`s (6 bytes each, because a
`move.w d16(An),(xxx).W` is opcode + source displacement + destination extension = 6):
`24 → 12`. It is also §7.5 of `CODING_CONVENTIONS.md` doing its job — group by what is
consumed together, not by what reads nicely.

**(b) Bounds are INCLUSIVE on both ends, not half-open.** C's editor schema uses `{x, y, w, h}`
and A's `Rect` used half-open `x0,y0,x1,y1`; the *runtime* record uses inclusive because the
test is then four compares with no adjustment (`blo` on the low edge, `bhi` on the high edge),
and because a half-open `x1` for an act that fills its axis would be `grid_w << 11` = up to
`$8000`, which is where a signed word compare changes meaning. Inclusive `x1` is at most
`$7FFF`. The generator converts `{x,y,w,h}` → `(x, x+w-1, y, y+h-1)` at bake; that conversion
is the *only* place the two conventions meet, which is the point.

**(c) `rg_effects` has no `= 0` default, and the omission is the guard.** This is the
`sec_effects` precedent, verbatim: `Effects_InstallPreset` dereferences the pointer untested,
the only null test on the path is inside `if DEBUG == 1`, and a null in release would read the
68000 vector table as an `EffectsPreset`. `Sec.sec_effects` and `ojz_sec()`'s `effects:`
argument both dropped their defaults on 2026-09-04 for exactly this reason, making an omitted
binding a compile error in every shape at zero ROM bytes. `rg_effects` starts there.

**(d) The record carries NOTHING else.** No `rg_music`, `rg_sound_bank`, `rg_plc`,
`rg_lookahead`, `rg_flags` — the five fields A's 36-byte proposal carried. B's objection (d) is
correct and the tree has since proved it: **all five of those are `Sec` fields that were
deleted on 2026-09-04 for having zero readers.** Re-creating them one scope up would be
recreating dead weight, and this repo's standing ruling is that a field is added the day a
consumer wants it, not reserved against one. The re-ground doc §4.3(d) says the same about
`sec_plc` specifically: the region record is where a per-region art PLC belongs, *the day
something reads it*. Nothing reads one today.

Nor does it carry `rg_bg_layout` / `rg_bg_anchor_*` / `rg_bg_rows` / `rg_bg_tiles`.
**Seam, named and stopped:** the background triple would land on this record, and that is
parcel 2.

### 1.4 What the reference engines actually do — and why they do not settle this

The 2026-08-29 sweep (report D) found the mechanisms below. **The sweep covered S3K and S2
only**; it did not examine Vectorman, Gunstar Heroes, Alien Soldier, Thunder Force IV, S.C.E.
or homebrew for per-area identity, so the corpus is narrower than `CLAUDE.md`'s research
checklist asks for. That is stated as a limit, not glossed.

| game / place | how "you are in a new place" is decided | cite (D §1.2) |
|---|---|---|
| S3K FBZ1 in/out | **player X/Y thresholds with hysteresis**, indexed by a state byte `Events_bg+$00` | `sonic3k.asm:108925-108990` |
| S3K ICZ1 | camera thresholds `$3700`/`$68C`, then `$3940` | `:39430-39444` |
| S3K ICZ2 | **a literal camera X/Y box, hand-written in the zone's event routine** | `:110728-110743` |
| S3K HCZ2 | `cmpi.w #$C00,(Camera_X_pos)` | `:39320-39323` |
| S2 WFZ | one compare, `cmpi.w #$2700,(Camera_X_pos)`, selecting a scroll array | `s2.asm:15641-15645` |
| S2 CPZ | **`CPZ_CameraSections`, a `$40`-entry byte table** indexing `BGCameraLookup` per 16-px row | `s2.asm:19078-19084` |

**Three things follow, and the third is the one that matters.**

1. **The classics have no region table.** Every one of these is either a hand-written compare
   in per-zone code or, in CPZ's single case, a per-row byte table. The rectangle table is not
   a technique aeon is adopting from anywhere; it is a generalisation of ICZ2's hand-written
   box into data.
2. **ICZ2's mechanism *is* a rectangle test** — a camera X/Y box — which is direct precedent
   that the shape is right and that a camera-referenced box is what a designer reaches for.
   What ICZ2 lacks is a *table*: one box, in code, per zone.
3. **CPZ's byte table is B's alternative, shipped, and it shipped a bug.** D found that
   `CPZ_CameraSections` splits at row 20 while the hscroll side splits at row 18
   (`s2.asm:17340-17348`) — "the two tables disagree by two rows." That is what a
   per-storage-cell identity table costs when the storage grid and the identity boundary are
   not the same thing. It is the strongest argument in the corpus *for* separating identity
   geometry from storage geometry, and it comes from the precedent for the alternative.

**On palettes**, D's finding is a correction worth carrying into this design: the classics
**snap** mid-level. S3K AIZ1 replaces all 48 level entries in one frame at a camera threshold
with no cover (`sonic3k.asm:38882-38893`); S2 swaps whole palette lines uncovered at three boss
triggers. Neither game fades mid-level — `Pal_FadeFromBlack` is a *blocking* 22-frame loop that
cannot run inside `ScreenEvents`. So a region edge that changes the palette is free of cover
requirements, and the existing `ep_transition`/`Palette_ArmFade` path stays an author's opt-in
rather than the default.

### 1.5 Where it lives in ROM

The `Act` descriptor gains two fields, appended (so no existing offset moves):

```emp
// engine/structs.emp — Act, today 40 bytes ($28), ends at act_art_budget: u16 @ $26
    act_regions:       *u8,   // $28 — [Region; act_region_count]
    act_region_count:  u16,   // $2C — REQUIRED, no default
                              //       Act is now 46 bytes ($2E)
```

The table itself is a `pub data <Act>_Regions: [Region; N]` beside the act's section table, in
the same ROM neighbourhood, placed by `games/sonic4/map.toml` exactly as `OJZ_Act1_Sections`
is. Nothing about placement is novel.

**A region identity may own more than one rectangle**, and that is why there is no separate
`Region` / `Rect` split of the kind A proposed (36 B + 10 B per rect). Two rows carrying the
same `rg_effects` pointer *are* the same region for every purpose the engine has, because
nothing downstream reads a region id. The cost comparison, derived:

| shape | 9 rects / 9 identities | 24 rects / 12 identities |
|---|---:|---:|
| A's split (`36R + 10N`) | 324 + 90 = **414 B** | 432 + 240 = **672 B** |
| this design (`16N`) | **144 B** | **384 B** |

The flat table is smaller at both sizes and removes an indirection from the hot path. What it
loses is a place to hang per-identity data that is not per-rectangle — which is exactly the
data §1.3(d) refuses to carry. If parcel 2 or a later parcel needs per-identity fields that a
rectangle should not duplicate, the split can be reintroduced then; **that is a seam, and this
sentence is the whole of what parcel 1 says about it.**

### 1.6 What binds to what

```
Act.act_regions ──▶ [Region; N]
                      Region.rg_effects  ──▶ EffectsPreset   (unchanged, 46 B, shared many-to-one)
                      Region.rg_parallax ──▶ parallax_config (0 = defer)

Act.sec_grid_ptr ──▶ [Sec; grid_w*grid_h]
                      storage only: blocks, objects, rings, type table, dict, bg_layout
```

**The precedence ladder stays three rungs.** This is B's objection (f) — "a fourth rung in two
repos, days after a three-rung resolve shipped a bug" — and the answer is that the region
scope **replaces** the section scope rather than sitting beside it:

| rung | today | under regions |
|---|---|---|
| 1 | `Sec.sec_parallax_config` | `Region.rg_parallax` |
| 2 | `EffectsPreset.ep_parallax` (via `Sec.sec_effects`) | `EffectsPreset.ep_parallax` (via `Region.rg_effects`) |
| 3 | `Act.act_parallax_config` | `Act.act_parallax_config` |

Three before, three after. `Effects_ResolveParallax` keeps its shape and its docstring's rung
numbering; only the type of its `a0` argument changes. This is C's "mode by file presence,
never both" applied at the engine level: a `Sec` does not get to keep an identity field that a
`Region` also carries, because two sources for one rule is the defect that produced the
2026-08-26 bug the resolver exists to prevent.

---

## 2. Crossing detection

### 2.1 What the crossing does today, read out of source

`engine/level/parallax.emp`, `Parallax_CheckBoundary`, called per frame from the OJZ game
state (`games/sonic4/test/ojz_scroll_test.emp:1229`) and again on the DEBUG warp (`:1816`) —
those two are the complete caller set (`grep -rn "jbsr *Parallax_CheckBoundary\|jbra *Parallax_CheckBoundary" engine/ games/`
returns exactly those two lines; `games/demo` never reaches it).

```
1. cur = ((Camera_X + SCREEN_WIDTH/2) >> 11, (Camera_Y + SCREEN_HEIGHT/2) >> 11)
2. compare against Parallax_Prev_Sec_X/Y; equal → rts
3. Section_GetSecPtrXY; out of grid → keep current, rts
4. commit Prev_Sec_X/Y
5. [DEBUG] tst.l Sec.sec_effects(a0); 0 → raise_error
6. jbsr Effects_InstallPreset          (a0 = Sec* in, resolved parallax config out)
7. jbra Parallax_StartTransition
```

The reference point is the **camera centre**, and it stays the camera centre. `Camera_X` is the
high word of a long, read as `move.w Camera_X, d2` — world pixels.

### 2.2 What changes

**Step 1 loses the two shifts. Steps 2 and 3 fuse into a rectangle test.** Everything from
step 5 down is unchanged in mechanism; only the pointer's type changes.

```
1. cx = Camera_X + CAM_SCREEN_HALF_W ; cy = Camera_Y + CAM_SCREEN_HALF_H
2. is (cx,cy) still inside the cached live rectangle?  yes → rts          [the fast path]
3. Region_Resolve(cx,cy) → a0 = Region*, or 0 if none contains the point
4. a0 == 0 → keep current, rts                                            [the out-of-grid twin]
5. cache the new rectangle; Region_Current = a0
6. [DEBUG] tst.l Region.rg_effects(a0); 0 → raise_error
7. jbsr Effects_InstallPreset          (a0 = Region* in, resolved parallax config out)
8. jbra Parallax_StartTransition
```

Two small cleanups ride along, both of them corrections rather than taste:

- The crossing spells `#SCREEN_WIDTH/2` and `#SCREEN_HEIGHT/2` inline while
  `engine/system/constants.emp:502-503` already declares `CAM_SCREEN_HALF_W = 160` and
  `CAM_SCREEN_HALF_H = 112`. C's report asks that the editor read the reference point "from one
  shared constant, never restate it" — the *engine* is currently restating it. Use the named
  constants.
- `moveq #SECTION_SIZE_SHIFT, d0` goes away with the shifts, freeing d0 for the scan counter.

### 2.3 The fast path, and why the rectangle is cached in RAM

The live rectangle is **copied into RAM on each crossing** rather than reached through a
pointer each frame. This is not denormalisation for its own sake: `Parallax_Prev_Sec_X/Y` is
already exactly this — a two-byte RAM cache of a value derived from the camera — and the
region cache is the same pattern widened from 2 bytes to 8. There is no coherence hazard
because the source is ROM.

```emp
// engine/level/parallax.emp — Parallax_CheckBoundary, the fast path
        move.w  Camera_X, d2                    // (Camera_X).w — world X px (high word)
        addi.w  #CAM_SCREEN_HALF_W, d2
        move.w  Camera_Y, d3                    // (Camera_Y).w
        addi.w  #CAM_SCREEN_HALF_H, d3
        cmp.w   Region_Cur_X0, d2               // (Region_Cur_X0).w
        blo     .rescan
        cmp.w   Region_Cur_X1, d2
        bhi     .rescan
        cmp.w   Region_Cur_Y0, d3
        blo     .rescan
        cmp.w   Region_Cur_Y1, d3
        bls     .no_crossing
    .rescan:
```

Unsigned compares throughout (`blo`/`bhi`/`bls`), because a world coordinate can legally reach
`$7FFF` and the act ceiling `ensure((GRID_W << SECTION_SIZE_SHIFT) <= $8000)` in
`games/sonic4/data/levels/ojz/act1/act_descriptor.emp:137` is the exclusive extent — a signed
compare would be one authored act away from meaning something else.

**Cycle derivation, no-crossing frame** (68000 nominal, `cmp.w (xxx).W,Dn` = 4 + 8 = 12, branch
not-taken 8 / taken 10, `move.w (xxx).W,Dn` = 12, `addi.w #imm,Dn` = 8, `asr.w Dx,Dy` = 6 + 2n,
`rts` = 16, entering `bsr.w` = 18):

| | today | regions |
|---|---:|---:|
| `bsr.w` in | 18 | 18 |
| 2 × (`move.w` + `addi.w`) | 40 | 40 |
| `moveq` + 2 × `asr.w` #11 | 4 + 56 = 60 | — |
| 2 × `cmp.b` (xxx).W + 2 branches | 24 + 18 = 42 | — |
| 4 × `cmp.w` (xxx).W + 4 branches | — | 48 + 34 = 82 |
| `rts` | 16 | 16 |
| **total** | **176** | **156** |

**The rectangle test is 20 cycles CHEAPER per frame than the section shift-and-compare**, and
176 is what report A derived independently for today's path (A §2.2), which is a control on the
method: two derivations, same number, and I did not read A's until after computing mine.
Against a ~128,000-cycle NTSC frame that is 0.016% recovered — i.e. nothing. **The correct
statement is that the per-frame cost is a wash, and nobody should decide anything on it.**

### 2.4 The scan

```emp
// engine/level/parallax.emp — proposed
// Region_Resolve — THE point-in-region query. Both the crossing (above) and the
// level init's boot select call it, for Effects_ResolveParallax's reason: two sites
// resolving the same thing privately is how the 2026-08-26 precedence bug shipped.
//   d2 = world X, d3 = world Y (the camera centre at both call sites)
//   Out: a0 = Region*, or 0 when no rectangle contains the point
pub proc Region_Resolve (d2: u16, d3: u16) clobbers(d0/a2) out(a0) {
        movea.l Current_Act_Ptr, a2             // (Current_Act_Ptr).w
        movea.l Act.act_regions(a2), a0
        move.w  Act.act_region_count(a2), d0
        subq.w  #1, d0                          // count >= 1 is a build-time ensure
    .scan:
        cmp.w   Region.rg_x0(a0), d2
        blo     .next
        cmp.w   Region.rg_x1(a0), d2
        bhi     .next
        cmp.w   Region.rg_y0(a0), d3
        blo     .next
        cmp.w   Region.rg_y1(a0), d3
        bls     .found
    .next:
        lea     sizeof(Region)(a0), a0
        dbf     d0, .scan
        suba.l  a0, a0                          // 0 = no region contains the point
    .found:
        rts
}
```

**Linear, and that is a decision, not a default.** Costs, derived: setup ≈ 56 cycles;
a rejected rectangle costs 40 cycles (rejected on the first compare) to 100 (all four compares
run, then `lea` + `dbf`). A nine-rectangle act therefore costs **≤ 956 cycles once, on a
crossing frame** — 0.75% of a frame. On that same frame `Effects_InstallPreset` runs
unconditionally: it copies a 96-byte palette, seeds two 4-word banks, and can reach a measured
**~19,332 cycles (15.1% of a frame)** when a palette variant actually rebinds (B §2c, citing
`preset.emp`'s own note). **The scan is 5% of the cheapest thing that happens on the same
frame.** Indexing it would be optimising the wrong term.

Three named optimisations, all deliberately NOT taken in v1, each with its trigger:
- **`(a0)+` compares** (A's form): `cmp.w (An)+,Dn` is 8 cycles / 2 bytes against 12 / 4, so
  the scan body drops 32 cycles and 8 bytes per candidate — at the cost of an `a0` fixup on
  every reject arm. Take it if a crossing-frame profile ever shows the scan.
- **Scan the current region's neighbours first.** Needs an authored adjacency, i.e. data.
- **A per-section bucket** (`>> SECTION_SIZE_SHIFT` into a candidate list) restores O(1) at the
  cost of the byte table B's alternative B proposed. Take it if `act_region_count` ever
  approaches the point where 956 cycles is not noise; at `MAX_ACT_SECTIONS = 48` and one
  rectangle per section the worst case is ~4,856 cycles, 3.8% of a frame, still on crossing
  frames only.

### 2.5 The sentinel, the warp, and the boot

Today `Parallax_Init` writes `$FF`/`$FF` into `Parallax_Prev_Sec_X/Y` so the first
`Parallax_CheckBoundary` always reads as a crossing, and `Debug_Warp_Consume`
(`games/sonic4/test/ojz_scroll_test.emp:1813-1814`) writes the same pair to force a crossing at
the destination. B calls that sentinel "the load-bearing trick", correctly.

**The region sentinel is a rectangle that cannot contain anything:** `Region_Cur_X0 = $FFFF`,
`Region_Cur_X1 = $0000`. One instruction sets both, because they are adjacent and span-major:

```emp
        move.l  #$FFFF0000, Region_Cur_X0       // sentinel: no point is inside
        clr.l   Region_Current
```

Any centre value is `< $FFFF`, so the first `cmp.w`/`blo` always takes `.rescan`. This costs
**zero cycles on the fast path** — no null test, no extra branch — which the alternative
designs do not:

| sentinel design | fast-path cycles | RAM | dead ROM |
|---|---:|---:|---:|
| cached rect, `$FFFF/$0000` (chosen) | **156** | 12 B | 0 |
| pointer + a `Region_None` record in ROM | 172 | 4 B | 8 B never read |
| pointer + `cmpa.w #0,a0` null test | 188 | 4 B | 0 |

The pointer-only forms are *slower than today*. The ROM-sentinel form also parks eight bytes
(`rg_effects`, `rg_parallax`) that nothing ever reads, which this repo rules against.

**RAM**, in `engine/ram.emp`:

```emp
    // Inside Parallax_State/_End, where Parallax_Prev_Sec_X/Y were:
    pad(2),                     // was Prev_Sec_X/Y; keeps PARALLAX_STATE_LONGS unchanged

    // OUTSIDE Parallax_State/_End, beside Parallax_Roles_Swapped and for its reason:
    // this is the identity scope, read by the effects path, not parallax-internal
    // state, and it must NOT be zeroed by Parallax_Init's longword clear loop — its
    // reset is an explicit named write (the $FFFF/$0000 sentinel above).
    Region_Cur_X0:  u16,
    Region_Cur_X1:  u16,
    Region_Cur_Y0:  u16,
    Region_Cur_Y1:  u16,
    Region_Current: u32,        // the Region* the cache came from; 0 = none resolved yet
```

The `pad(2)` is deliberate and cheap: `Parallax_State`'s span is a longword-counted clear whose
size is `ensure`-pinned against `PARALLAX_STATE_LONGS` in `engine/level/parallax.emp`.
Removing two bytes and padding the hole leaves that pin untouched, which keeps a parcel about
identity out of a parcel about parallax RAM arithmetic. **Net RAM: +12 bytes.** (A estimated
~24 B for a richer record; the difference is the five fields §1.3(d) refuses.)

`Region_Current` earns its four bytes as the observable that replaces `Parallax_Prev_Sec_X/Y`
for three witness tools (§4.3). It is not read by engine logic.

**The boot select must change, and B's objection (g) is why.** `games/sonic4/test/ojz_scroll_test.emp:904-910`
today does `Section_GetSecPtrXY` on the start section (or, in DEBUG, on the clamped
`Boot_At_X/Y` override) and hands the `Sec*` to `Effects_ResolveParallax`. Under regions it
calls `Region_Resolve` on the camera centre instead. Two consequences:

- The DEBUG `Boot_At_X/Y` → grid-coordinate block (`:893-901`, two `lsr.w` pairs) becomes
  **unnecessary**, because `Camera_Init` has already clamped `Camera_X/Y` to the boot position
  before this point and the region query wants world pixels, not grid coords. That is a
  deletion, not an addition. *(Ordering claim — see §8 T4: I read the init ladder and believe
  `Camera_Init` precedes this block, but I did not build or trace it.)*
- B's stronger claim — "the boot-position override does not set `Parallax_Snap_Pending` and
  does not touch palette / cycle / variants / raster, so under regions booting into a non-default
  region would come up with the wrong palette" — is **half right and does not block this
  parcel.** The re-ground doc's §1 row for it is the correct reading: `Parallax_Init` writes the
  sentinel and sets `Snap_Pending` on *every* boot branch, so the first `Parallax_CheckBoundary`
  of the update loop installs the full identity. The residue is **one frame** of the act
  default's palette, and it is one frame today too. Regions do not make it worse; they make it
  *visible* (today all nine presets bind the same `pal: OJZ_Palette`, so the wrong palette is
  the right palette). Fixing it properly means installing the whole preset at boot, not just
  the parallax config — booked in §5 as open question Q3, not folded in here.

---

## 3. The migration

### 3.1 What act 1 looks like today, verified

`games/sonic4/data/levels/ojz/act1/act_descriptor.emp`: `GRID_W = 3`, `GRID_H = 3`,
`ensure(GRID_W * GRID_H == 9)`. Section side is `SECTION_SIZE = $0800` (2048 px), so the act is
**6144 × 6144 world pixels**. Nine sections, and — the fact that decides the shape of the
migration — **nine distinct presets**:

| flat id | sec (x,y) | rect (x0,x1,y0,y1) | `effects:` | `sec_parallax_config` |
|---|---|---|---|---|
| 0 | (0,0) | 0,2047, 0,2047 | `OJZ_Preset_Sec0` | **BOUND** — `EditorSceneBinding_OJZ_Act1_Sec0` (`ojz_act1_start`) |
| 1 | (1,0) | 2048,4095, 0,2047 | `OJZ_Preset_Sec1` | 0 — no chooser arm; act default stands |
| 2 | (2,0) | 4096,6143, 0,2047 | `OJZ_Preset_Sec2` | 0 — no chooser arm; act default stands |
| 3 | (0,1) | 0,2047, 2048,4095 | `OJZ_Preset_Sec3` | 0 — no chooser arm; act default stands |
| 4 | (1,1) | 2048,4095, 2048,4095 | `OJZ_Preset_Depth` | **BOUND** — `EditorSceneBinding_OJZ_Act1_Sec4` (`ojz_act1_depth`) |
| 5 | (2,1) | 4096,6143, 2048,4095 | `OJZ_Preset_Sec5` | 0 — no chooser arm; **resolves at RUNG 2** to `ParallaxConfig_OJZ_Underwater` |
| 6 | (0,2) | 0,2047, 4096,6143 | `OJZ_Preset_Sec6` | 0 — no chooser arm; act default stands |
| 7 | (1,2) | 2048,4095, 4096,6143 | `OJZ_Preset_Sec7` | **BOUND** — `EditorSceneBinding_OJZ_Act1_Sec7` (`ojz_act1_sec7_worldwater`) ⚠ *~~returns 0, act default stands~~ — corrected, see below* |
| 8 | (2,2) | 4096,6143, 4096,6143 | `OJZ_Preset_Plain` | **BOUND** — `EditorSceneBinding_OJZ_Act1_Sec8` (`ojz_act1_floor`) |

(Rectangles derived as `sec_x * 2048 .. sec_x * 2048 + 2047`, flat id = `sec_y * 3 + sec_x`.
The `effects:` column is read out of the nine `ojz_sec(...)` calls at `:239-361`.)

**⚠ CORRECTION, 2026-09-09 — row 7 was wrong, and the whole column was under-specified
(`parcel/section-effects-record-fix`).**

**What this table said, quoted so a reader who remembers it meets the correction rather than
quietly inheriting a new value.** Row 7's `sec_parallax_config` cell read
**`ojz_act1_sec_scene(sec: 7)` — returns 0, act default stands**, and rows 1, 2, 3, 5 and 6
carried the bare call with no verdict at all, which reads as "bound" beside row 0's explicit
"bound".

**It does not return 0.** Derived from source, not from any report:

- `games/sonic4/data/editor/ojz/act1/section_7.meta.json` exists and reads
  `"sceneRef": "ojz_act1_sec7_worldwater"`. It landed at **`c1d0a6be`, 2026-09-05**.
- The generated chooser therefore carries an arm for it —
  `games/sonic4/data/generated/ojz/act1/effects_scenes.emp:346`:
  `if sec == 7 { out = EditorSceneBinding_OJZ_Act1_Sec7 }`.
- That binding is a real emitted record, `effects_scenes.emp:168`:
  `pub data EditorSceneBinding_OJZ_Act1_Sec7: SceneCfg3 = lower3(EditorScenes_OJZ_Act1[2])`,
  and `EditorScenes_OJZ_Act1[2]` is `Scene_Editor_ojz_act1_sec7_worldwater` (`:140`) —
  3 layers, `v_factor: 15`, `v_offset: 288`, no anchor (`:92-111`).

So **section 7 resolves at rung 1 to an editor scene, and the act default does NOT stand.**

**The full column, derived once so nobody has to re-derive it.** The chooser
(`effects_scenes.emp:341-349`) has exactly four arms — `{0, 4, 7, 8}` — and
`act_descriptor.emp:229` calls it as `ojz_act1_sec_scene(sec: sec)` with **no `hand:`
argument**, so the five sections without an arm get the parameter default `0`. That is what
the rewritten rows above now state per row.

**Section 5 is the one row where 0 does not mean "act default"**, and the migration must not
read it that way: with rung 1 at 0, `Effects_ResolveParallax` (`engine/effects/preset.emp:228-245`)
falls to rung 2 and finds `OJZ_Preset_Sec5`'s own
`parallax: ParallaxConfig_OJZ_Underwater` (`ojz_effects.emp` at `OJZ_Preset_Sec5`, the d-53
loan). Section 5
is the act's **only live install** of that record — section 0 names it too (`:1517`) but its
rung 1 overrides it. A transcription that copies `sec_parallax_config` alone would give
section 5 the act default and change what is on screen.

**Why this matters more than a typo.** This document is the source for a **1:1 transcription**
(§4 step 1: "the nine rectangles of §3.1, each naming the preset and scene binding its section
names today"). A wrong row here becomes a wrong region, and the error would land inside a
migration whose whole proof is byte-identical behaviour. The row was already **four days stale
when it was written**: the sidecar's `c1d0a6be` is an ancestor of `944c5cc0`, the SHA §0 names
as this document's verification point, so it was present in the tree the table claims to have
been verified against.

**The upstream copies were corrected in the same parcel**, so the tree no longer contains the
sentence this row was transcribed from: `act_descriptor.emp:347-350` (the original), the
`OJZ_Preset_Sec7` banner in `ojz_effects.emp`, and `ojz_scroll_test.emp`'s parallax-readout
rationale (which justified a technique with "section 8 carries it and section 7 does not").

**⚠ FROZEN NAMES — read before §4 step 1 renames anything.** `OJZ_Preset_*` and
`EditorSceneBinding_OJZ_Act1_*`: **reorder free, rename coupled.** Reorder is absorbed because
`sigil/crates/sigil-harness/src/pins.rs` is generated and `repin_pins::pins_rs_is_current`
fails loudly if it is not regenerated. Rename breaks by-name resolution in `repin.toml`, a
generated identifier in `pins.rs` (a compile error, not a test failure), and a string literal
in `act_descriptor_port.rs`. **Four shapes and four md5s cannot see either hazard** — a
`pub data` rename moves no ROM byte, so a byte-neutrality proof is structurally blind to it.
Verified firsthand at sigil `master` `5498bdfb`, 2026-09-09. Expires if `pins.rs` stops being
generated or the manifest stops resolving by name. A rename is not forbidden, it is
**coordinated**: three mechanical edits on sigil's side, cheap when expected. Route it rather
than dropping it. **Basis and expiry, stated because the bare fact is what rotted last time:**
the consumer sites below were enumerated from two greps of one repo; nobody has swept the
family exhaustively, so **treat the list as a floor, not a total.**

| sigil site (at `5498bdfb`) | what it does | breaks on |
|---|---|---|
| `crates/sigil-cli/tests/act_descriptor_port.rs:117-146` | asserts 7 `OJZ_Preset_*` + `EditorSceneBinding_..._Sec0` + `_Sec4` by **string literal**, each against its own pinned address | rename |
| `act_descriptor_port.rs:132-136` | `EditorSceneBinding_OJZ_Act1_Sec0` is the **END label of the pinned `SCENE_REGISTRY` region** — asserted as `plain_base + plain_len`, i.e. **arithmetic**, not a lookup | rename |
| `act_descriptor_port.rs:268` | prefix sweep `["EditorRaster_", "EditorCycle_", "EditorSceneBinding_", "EditorReel", "OJZ_Preset_Sec"]` — membership is decided by the **name's prefix** | rename that changes prefix membership (e.g. `OJZ_Preset_Depth` -> `OJZ_Preset_Sec4` would move it from the pinned list into the swept set **and orphan its `[[symbol]]` pin**) |
| `crates/sigil-harness/repin.toml:978-1017` | `[[symbol]]` manifest entries resolved **by name** | rename |
| `crates/sigil-harness/src/pins.rs:341-362` | generated Rust identifiers derived from those manifest names | rename (compile error) |
| `crates/sigil-harness/src/section_align.rs:228` | `d("EditorSceneBinding_OJZ_Act1_Sec0", 2, WORD)` alignment row | rename |
| `crates/sigil-harness/src/map_placement.rs:217` | `assert_eq!(section_row("EditorSceneBinding_OJZ_Act1_Sec0"), None)` | rename |

**How three lanes got this wrong, recorded because it transfers.** The premise everyone
reasoned from was *"nothing derives from their ORDER or ADDRESS"* — a claim about
**derivation**, which says nothing about **by-name pinning**. Three separate lanes turned it
into "free to rename". If a premise names properties and a conclusion names operations, check
each operation against a named property before relying on it. The second half of the same
lesson: everyone enumerated by the symbol's **declaration** site and found one hit, because
every consumer lives in another repo. **Enumerate by what touches the data, not by what
defines it.**

**C's migration rule — "merging adjacent cells with identical tuples, never one region per
section" — produces nine regions here, because there is nothing to merge.** All nine bindings
are distinct. That is a change since the study, which recorded six presets over nine sections
with `OJZ_Preset_Plain` covering four; sections 5, 6 and 7 acquired their own records during
EFFECTS-W1 (first at `99d70db4`, 2026-08-30). So the migration is a **1:1 transcription**, which
is the best possible starting state for a proof: nine rectangles equal to nine sections must
produce byte-identical *behaviour*.

### 3.2 What happens to `Sec.sec_effects`

**It is deleted, along with `Sec.sec_parallax_config`.** Not kept as a fallback, not left
behind for a later parcel. Three reasons, in order of weight:

1. **Two sources for one rule is the defect the resolver exists to prevent.** The
   `Effects_ResolveParallax` header records the 2026-08-26 bug in as many words: "the two sites
   each read a different pair of the three and the preset won on the first crossing." Keeping a
   section rung alive beside a region rung recreates that class at a higher scope, and it is
   B's objection (f) landing for real.
2. **The precedence ladder must stay three rungs**, and it can only do that if the region
   scope *replaces* the section scope (§1.6).
3. **A field with no reader is what parcel 0 just spent a commit deleting.** Leaving
   `sec_effects` bound but unread would be nine dead pointers, the exact shape of the nine
   fields removed on 2026-09-04.

`Sec` goes **34 → 26 bytes** (`sec_block_index` 4 + `sec_objects` 4 + `sec_rings` 4 +
`sec_bg_layout` 4 + `sec_type_table` 4 + `sec_block_dict` 4 + `sec_block_dict_len` 2 = 26).
Nine sections × 8 bytes = **72 ROM bytes recovered on act 1**.

**`Sec.sec_bg_layout` stays exactly where it is.** It is read (`Section_RedrawPlanes`), all
nine sections pass `default` (NULL → the act-wide layout), and moving it is parcel 2's
business. **That is the seam, and this sentence is the end of what parcel 1 says about it.**

### 3.3 What the tools side has to become

Not planned in detail here — it is a tools parcel with its own lane and its own repo
boundaries — but the shape is settled by C's report and by what `effects_gen.py` does today:

- `tools/effects_gen.py` emits `pub comptime fn ojz_act1_sec_scene(sec: int, hand: Label = 0)`
  as a comptime `if sec == N` chain over a flat int, with
  `ensure(sec >= 0 && sec < 9)` (`:4275-4280`) and `ensure(9 <= MAX_ACT_SECTIONS)` (`:4479`).
  B's objection (i) is right that this is flat-int-indexed end to end and that a point-in-rect
  query is not expressible as a `Label`-returning comptime fn. It does not have to be: the
  generator emits a **table**, and the query is the runtime `Region_Resolve`.
- **Mode by file presence** (C §2.2): no `regions.json` → legacy sidecar mode, unchanged;
  `regions.json` present → region mode, and a sidecar carrying a non-null `sceneRef` is
  **refused, never merged**.
- Until that lands, act 1's region table is **hand-written**, exactly as `OJZ_Act1_Sections` is
  hand-written today through `ojz_sec()`. There is no generator emitting `Sec` rows either.

### 3.4 Build-time invariants

Per-row, expressible in a `region()` comptime constructor (the `ojz_sec()` / `preset()`
precedent — a comptime fn's `ensure`s evaluate at the **call site**, which is what makes them
live):

| invariant | why | derivation |
|---|---|---|
| `x0 <= x1`, `y0 <= y1` | a degenerate rect silently contains nothing | — |
| `x1 < grid_w << 11`, `y1 < grid_h << 11` | a rect past the act is unreachable | act extent |
| `x1 - x0 + 1 >= 32`, same on y | the camera steps at most 16 px/frame, so a rect could otherwise be stepped over | `CAM_MAX_X_STEP = 16` (`engine/level/camera.emp:26`), `CAM_MAX_Y_STEP = 16` (`constants.emp:1049`). Strict bound is 17; 32 is one doubling of margin. **This is authoring hygiene, not safety** — a skipped rect costs a missed identity change, never corruption, because the fast path then rescans. |
| edges lie in the reachable band | `Camera_X_Max = (grid_w << 11) - SCREEN_WIDTH` (`camera.emp:192-197`), so the centre spans `[160, (grid_w << 11) - 160]`; an interior edge outside that never fires | derived from the clamp, not asserted |
| `rg_effects != 0` | §1.3(c) | the missing default is the guard |

Whole-table, in the generator plus a pytest, **not** in `.emp`:

| invariant | why not comptime |
|---|---|
| rectangles do not overlap | needs a pairwise fold over the authored table; whether `comptime for` can produce a value an `ensure` can read is **open** (Q1) |
| rectangles cover the act | same |
| `act_region_count >= 1` | expressible; put it beside the table |

**Overlap is forbidden in v1**, following A: with overlap, identity stops being a pure function
of position, and warp/respawn/replay would have to re-run or invert a history. A's hysteresis
argument (dwell in the current rect until the point leaves it) is real and gives an authored
dead band for free — but it buys a dead band at the cost of path-dependence, and this parcel
takes the position that **identity is a function of `(x, y)` and nothing else.** Note what that
costs, honestly: a camera oscillating one pixel across an edge re-fires `Effects_InstallPreset`
every frame. It does that today at `x = 2048` too, and the variant guard is why it is
survivable.

**The replay hash needs nothing.** A §3.8 suggested `Region_Cur` must join it. Read out of
`engine/system/replay.emp:372-376`, the ledger is `Camera_X`+`Camera_Y`,
`Section_Top/Bottom_Row_Written`, `Section_Right/Left_Col_Written`,
`Section_Fwd/Bwd_Neighbor_Data` — and `Parallax_Prev_Sec_X/Y` **is not in it today**. With
non-overlapping rectangles the region is a pure function of `Camera_X/Y`, which the hash
already covers. Adding it would be adding a derived value. Do not.

---

## 4. Implementation plan

### 4.0 What a byte figure in this section is worth — read this before quoting one

Every byte cost below is an **emitted-byte derivation from 68000 instruction encodings**, done
by hand against the source in this worktree. No ROM was built. Three specific things they do
not account for, each of which has bitten this tree:

1. **The deb2 symbol appendix.** `build.sh` appends a `convsym` symbol table into the image in
   **every shape, release included**. Its Huffman code table is built over the *characters* of
   every symbol name, so adding names like `Region_Cur_X0` re-encodes the appendix
   unpredictably — a measured precedent (LS-22a, 2026-09-07) moved 953 appendix bytes with the
   appendix's length unchanged, from one added `mark`. **The ROM length delta will not equal
   the emitted delta and cannot be predicted.** Quote `EndOfRom` from a real build, or say
   "emitted bytes" and mean it.
2. **`bsr.w` vs `bsr.s`.** I priced every `jbsr`/`jbra` at 4 bytes (the `.w` rung). Sigil
   relaxes by reach, so an in-range call is 2. Cross-module calls are `.w`; the intra-file ones
   in `Parallax_CheckBoundary` may relax.
3. **Zero-displacement folding.** `Region.rg_x0` is at offset `$00`. Whether sigil emits
   `cmp.w (a0),d2` (2 bytes) or `cmp.w 0(a0),d2` (4) is unknown to me and changes the scan by
   2 bytes. Priced at 4, i.e. pessimistically. (Q4.)

Cycle figures are 68000 nominal from the instruction tables; they exclude prefetch and bus
contention, which is the same basis `CODING_CONVENTIONS.md` §2.1 and report A use.

**No step below adds a gate.** Where a step needs one that does not exist, it is written as
part of that step's work under the implementing lane's own red-first discipline — this parcel
does not build test infrastructure.

---

### Step 1 — the Region record and act 1's table, read by nothing

**What changes**
- `engine/structs.emp`: add `pub struct Region (size: 16)` (§1.3) and append
  `act_regions: *u8` / `act_region_count: u16` to `Act`.
- `games/sonic4/data/levels/ojz/act1/act_descriptor.emp`: a `region()` comptime constructor
  carrying the per-row `ensure`s of §3.4, and `pub data OJZ_Act1_Regions: [Region; 9]` — the
  nine rectangles of §3.1, each naming the preset and scene binding its section names today.
  Wire `act_regions: OJZ_Act1_Regions` / `act_region_count: 9` into `OJZ_Act1_Descriptor`.
- `games/sonic4/map.toml`: place the new data beside `OJZ_Act1_Sections`.

Nothing reads any of it. `Sec` is untouched. The crossing is untouched.

**How it is verified**
- `./build.sh` and `DEBUG=1 ./build.sh` for both games green — the real check here is that
  `Region`'s declared `(size: 16)` matches its fields, and sigil's layout checker validates
  that **only when the module is in the target's `use` closure** (`docs/EMP_PITFALLS.md` §3,
  and `EffectsPreset`'s own two-task history of a wrong declared size in an unreachable
  module). `engine/structs.emp` is reached by `section.emp`, so it is live — but confirm with
  `SIGIL_WARNINGS=full` that `structs` is not on the unreachable list before trusting the
  check.
- **Inversion, mandatory** (`EMP_PITFALLS.md` §10): declare `(size: 15)` and watch the build go
  red; violate each per-row `ensure` from the real call site in `act_descriptor.emp` and watch
  each fail with its own message. A guard nobody has seen fail is not a guard.
- A pytest asserting the nine rectangles tile 6144×6144 exactly, parsed from the `.emp` the way
  `tools/parallax_crossing_gate.py`'s `struct_offsets()` parses `structs.emp`.

**Expected byte cost: +150 emitted.**
`9 × sizeof(Region)` = 9 × 16 = **144** (table) + `4 + 2` = **6** (`Act`'s two fields, one act
descriptor in the tree) = **+150**. The struct declaration itself emits nothing —
`engine/structs.emp` is a type-only module.

**Independently landable:** yes. Adds data and names, changes no behaviour. Note it *does* add
cross-seam names (`Region`, `act_regions`, `act_region_count`), so per `CODING_CONVENTIONS.md`'s
name-move checklist it **pairs with sigil regardless of byte count**, and the standalone
`*_port` scopes that lower `engine/structs.emp` need checking with `--no-fail-fast`.

---

### Step 2 — the resolvers take a `Region*`

**What changes**
- `engine/effects/preset.emp`: `Effects_InstallPreset` reads `Region.rg_effects(a0)` instead of
  `Sec.sec_effects(a0)`; `Effects_ResolveParallax` reads `Region.rg_parallax(a0)` instead of
  `Sec.sec_parallax_config(a0)`. Both keep their shape, their register discipline (the `a3`
  hazard, the stack spill) and their docstrings' rung numbering; the `use engine.structs.{Sec, Act}`
  import becomes `{Region, Act}`.
- `games/sonic4/test/ojz_scroll_test.emp:3003` (the effects lab's parallax readout) follows.

**How it is verified**
- Both procs must remain **byte-identical in length**: `movea.l d16(An),An` is 4 bytes at any
  non-zero displacement, and `$08`/`$0C` replace `$1C`/`$0C`. A length change means something
  else moved.
- TAGGED T1: `tools/parallax_crossing_gate.py` — it asserts the three-rung resolve end to end
  and its `struct_offsets()` will re-derive from the edited declaration.

**Expected byte cost: 0 emitted, in the procs themselves.** Displacement values change; encoding
widths do not. Caveat 4.0(1) still applies to the ROM as a whole.

**Independently landable:** **no** — this step and step 3 must land together, because the
callers hand these procs a `Sec*` today. They are written separately because they are
separately *reviewable*: this one is a pure retype, step 3 is where the mechanism changes.

---

### Step 3 — the crossing becomes a rectangle test

**What changes**
- `engine/ram.emp`: `Parallax_Prev_Sec_X/Y` → `pad(2)` inside `Parallax_State`; the five
  `Region_*` vars added outside it (§2.5).
- `engine/level/parallax.emp`: `Region_Resolve` (new, §2.4); `Parallax_CheckBoundary` rewritten
  to §2.2; `Parallax_Init`'s two `move.b #$FF` replaced by the `move.l` sentinel + `clr.l`.
- `games/sonic4/test/ojz_scroll_test.emp`: the boot select calls `Region_Resolve` on the camera
  centre (§2.5); `Debug_Warp_Consume`'s two `move.b #$FF` become the same sentinel pair; the
  effects lab's PRESET chord (`:2211-2262`) takes a **region index** instead of a section index
  — its `mul_bounded` against `grid_w * grid_h` becomes a bounds check against
  `act_region_count` and a `mul_const.w d0, #sizeof(Region)`.

**How it is verified**
- **TAGGED T1, and it is the whole point of the parcel's proof strategy:** run
  `tools/parallax_crossing_gate.py` unchanged, with the nine rectangles equal to the nine
  sections, and require the same verdict. It walks the pad across the OJZ `(0,0)|(1,0)` edge
  and back and asserts crossing A resolves to `Act.act_parallax_config` (rung 3, staged) and
  crossing B to the section's own binding (rung 1, snapped). Under regions those become the
  *region's* bindings and must resolve identically. **This gate is the single strongest
  instrument this parcel has, and it exists.**
- TAGGED T2: `tools/boot_override_gate.py` — the other half of the same resolver, sampling at
  the init's exit *before* any crossing.
- TAGGED T3: `tools/sec5_band_witness.py` and `tools/row_remap_witness.py` — both read
  `Parallax_Prev_Sec_X/Y` and must be repointed at `Region_Current`.
- Inversion on the sentinel: boot with the sentinel write removed and confirm the first frame
  fails to install (i.e. that the sentinel is load-bearing, which B says it is).

**Expected byte cost: +76 emitted (release).** Derivation, instruction by instruction:

| site | today | regions | delta |
|---|---:|---:|---:|
| `Region_Resolve` (new) | 0 | `4+4+4+2` setup + `(4+2)×4` scan + `4+4` next/dbf + `2+2` tail = **50** | +50 |
| `Parallax_CheckBoundary` | centre `4+4+2+2+4+4+2` = 22 · compare `4+2+4+2` = 12 · lookup `4+4+2` = 10 · commit `4+4` = 8 · tail `4+4+2` = 10 → **62** | 4 moves **16** + 4 cmp/branch **24** + `jbsr` 4 + `cmpa.w` 4 + `beq` 2 + 2×`move.l` **12** + `move.l a0` 4 + `jbsr` 4 + `jbra` 4 + `rts` 2 = **76** | +14 |
| `Parallax_Init` | 2 × `move.b #imm,(xxx).W` = **12** | `move.l #imm,(xxx).W` 8 + `clr.l (xxx).W` 4 = **12** | 0 |
| boot select | 2 × `move.b d16(An),Dn` 8 + `jbsr` 4 + `beq` 2 = **14** | 2 × (`move.w`+`addi.w`) 16 + `jbsr` 4 + `cmpa.w` 4 + `beq` 2 = **26** | +12 |
| | | | **+76** |

DEBUG shapes additionally lose the boot override's `Boot_At_X/Y` → grid-coord block
(~20 bytes) and gain a slightly different `raise_error` string; both unpriced.

**Independently landable:** as a pair with step 2, yes.

---

### Step 4 — delete the section identity fields

**What changes**
- `engine/structs.emp`: delete `Sec.sec_parallax_config` and `Sec.sec_effects`; renumber the
  trailing `// $HH` comments (**they are a gate, not decoration** — `parallax_crossing_gate.py`
  cross-checks every one).
- `engine/level/section.emp` and `engine/level/tile_cache.emp`: re-pin
  `ensure(sizeof(Sec) == 34)` → `== 26`, and rewrite the message, which currently explains that
  the pin exists because three Python tools carry their own copy of the layout. It still does.
- `games/sonic4/data/levels/ojz/act1/act_descriptor.emp`: `ojz_sec()` loses its `effects:` and
  `sec_parallax_config:` arguments; nine call sites shrink.
- `tools/boot_override_gate.py` (`SEC_SIZE = 34`, `SEC_PARALLAX_CONFIG = 0x0C`,
  `SEC_EFFECTS = 0x1C`) and `tools/preset_lab_witness.py` (`SEC_SIZE = 34`,
  `SEC_EFFECTS = 0x1C`) hardcode the layout and owe edits.
  `tools/parallax_crossing_gate.py` parses it and owes only the field names it looks up.
- `docs/ENGINE_ARCHITECTURE.md` §4.2 and §7.12 describe a section-scoped binding that no longer
  exists. **Not edited in this parcel** (§7.4 records what is already wrong there); the
  implementing parcel owes the rewrite.

**How it is verified**
- The `sizeof(Sec)` inversion: leave the pin at 34 and confirm the build goes red.
- All three Python tools re-run. **TAGGED** — `boot_override_gate` and `parallax_crossing_gate`
  need a running ROM; `preset_lab_witness` likewise.
- `grep -rn "sec_effects\|sec_parallax_config" engine/ games/ tools/ docs/` must return prose
  only, the way the nine-field deletion of 2026-09-04 was checked.

**Expected byte cost: −72 emitted.** `8 bytes × 9 sections`. The `Sec` fields are 4 + 4 = 8;
the section table is `[Sec; 9]`.

**Independently landable:** yes, once steps 2+3 have landed.

---

### Step 5 — author one sub-section edge

**What changes**
- One region rectangle in act 1 that does **not** align to a section boundary — the smallest
  honest proof, e.g. splitting section 4 so that a 600 × 300 interior rectangle binds a
  different `EffectsPreset` (a different palette is the cheapest visible difference, and D's
  precedent says snap it).
- Nothing in the engine.

**How it is verified**
- **TAGGED T5:** this is the first thing in the parcel that cannot be verified without a
  screen. The rectangle must be crossed, the palette must change at the authored edge and not
  at `x = 4096`, and the crossing must not stutter.
- The per-row `ensure`s of §3.4 (width ≥ 32, edges reachable) become live for the first time
  against a hand-authored value rather than a generated one.

**Expected byte cost: +16 emitted** per added rectangle (one `Region` row), plus 46 if the edge
needs a new `EffectsPreset` and 0 if it reuses one.

**Independently landable:** yes. It is content, and it is the step that proves the parcel
bought anything. **Until step 5 lands, parcel 1 has delivered a re-scoping that costs 154 bytes
and changes no pixel** — which is the honest description of steps 1-4 and should be said out
loud in their commit messages.

---

### Step 6 (optional, gated) — skip the install when the identity is unchanged

**What changes**
- Cache `Region_Cur_Effects: u32` beside the rectangle; on a crossing, if the new
  `rg_effects` equals the cached one, skip `Effects_InstallPreset` and go straight to
  `Effects_ResolveParallax` + `Parallax_StartTransition`.

**Why it might be wanted**, and why it is not in v1: it answers B's objection (c) — "if region
edges are added *inside* sections, crossings get more frequent and this becomes the new hot
cost. The proposal does not say which." It also removes the redundant install when two
rectangles of one L-shaped region share an internal seam. The idiom is already in the tree
twice (`Raster_InstallSection`'s `cmp.l/beq .keep`, and `Effects_InstallPreset`'s own variant
guard, which exists because a rebind costs a measured ~19,332 cycles).

**Why it is gated, not folded in:** it is an idempotence guard, and idempotence is only true if
nothing else can have changed the channels in between. The DEBUG effects-lab chords *do* change
them (`Debug_BandDemoHotkey` installs a raster program live). So the guard could hide a
re-install an author wants, in the shape authors develop in. Take it only with a measurement
showing crossings are hot.

**Expected byte cost: +4 RAM, +10 emitted** (`move.l d16(An),Dn` 4 + `cmp.l (xxx).W,Dn` 4 +
`beq` 2).

---

### 4.1 Net

| step | emitted bytes | RAM |
|---|---:|---:|
| 1 — record + table | +150 | 0 |
| 2 — resolvers retyped | 0 | 0 |
| 3 — rectangle crossing | +76 | +12 |
| 4 — delete `Sec` identity | −72 | 0 |
| **parcel 1 total (steps 1-4)** | **+154** | **+12** |
| 5 — one authored edge | +16 (+46 if a new preset) | 0 |

**Parcel 1 is a ROM loss of about 154 bytes, and it should be argued for on nothing else.**
That is worse than the study's estimate of +116 B, and the reason is a finding: **parcel 0
already spent regions' ROM case.** B's arithmetic credited regions with recovering the 44
identity bytes of a 66-byte `Sec` — 396 bytes on act 1, up to 2,112 in a 48-section act. Those
fields were deleted on 2026-09-04 for having no readers, recovering 288 bytes with no region
mechanism at all. What is left for regions to recover is `sec_parallax_config` +
`sec_effects` = **8 bytes a section**: 72 on act 1, **384 in the largest legal act**. B's "best
possible saving 1.6 KB" is now 384 bytes. The ROM argument is not merely a wash; it is a small
loss, and §7.2 restates it as a finding.

---

## 5. Open questions

**Q1 — Can a whole-table invariant be expressed as a live `ensure` in `.emp`?**
Per-row invariants go in a `region()` comptime constructor and evaluate at the call site.
Non-overlap and coverage need a pairwise fold over the authored table. `comptime for i in 0..N
{ ... }` exists and produces arrays (`games/sonic4/data/effects/ojz_effects.emp:807, 1002,
2016`), but I did not establish whether it can produce a scalar an `ensure` can read.
**What would settle it:** write the fold, invert it (overlap two rectangles on purpose) and
watch the build go red. If it cannot, the checks live in the generator and a pytest, which is
weaker — a hand-written table then has no comptime overlap check at all, and that matters
because act 1's table *is* hand-written until step 3.3's generator lands.

**Q2 — Does the owner want sub-section edges?** This is the whole discriminator and it is not
a technical question. B's alternative B (a 1-byte-per-section region id) and alternative E
(regions as an editor-only grouping, zero engine bytes) both deliver "a set of places sharing a
binding" for free. **The only thing rectangles buy over them is an edge that does not lie on a
2048-pixel grid line.** The re-ground doc adds that act 1 now binds one preset per section with
no sharing at all, so the grouping B and E offer buys nothing *new* either — but "buys nothing
new" is not an argument for spending 154 bytes and a struct change. **What would settle it:**
the owner naming one edge he wants that is not on a section boundary. The study's framing of
his ask ("a 600×300 cave, a zone edge at `$1400`, a hatch") is sub-section by definition, but
that is the study reading him, not him.

**Q3 — Should the boot select install the whole preset, not just the parallax config?**
§2.5 establishes the residue is one frame and that regions do not worsen it. But regions do
make it *reachable*: today all nine presets bind the same palette, so no boot can show a wrong
one. **What would settle it:** author a boot into a region whose preset differs in `ep_pal`
(step 5 creates exactly that fixture) and look at frame 1. If the flash is visible, the fix is
to call `Effects_InstallPreset` at boot instead of `Effects_ResolveParallax` alone — a small
change this parcel deliberately does not make blind.

**Q4 — Does sigil fold a zero displacement?** `cmp.w Region.rg_x0(a0), d2` at offset `$00`:
2 bytes or 4? Changes `Region_Resolve` by 2 and every byte figure that includes it.
**What would settle it:** read the `.lst` from any build containing an offset-0 struct field
access. I did not build.

**Q5 — Is the effects lab's PRESET chord present in the release shape?**
`games/sonic4/test/ojz_scroll_test.emp` ships in both shapes, and a comment at `:2271` says a
nearby table is "Absent in the release shape", but I did not establish which side of the
`if DEBUG == 1` boundary the chord's dispatch sits on. It determines whether step 3's rework of
that chord costs release bytes. **What would settle it:** `grep` the enclosing conditional, or
a symbol-span read off both `.lst`s.

**Q6 — Is `Camera_Init` guaranteed to run before the boot select?** §2.5's deletion of the
`Boot_At_X/Y` grid-coordinate block depends on `Camera_X/Y` already holding the clamped boot
position at `ojz_scroll_test.emp:904`. I read the ladder and believe it does. **What would
settle it:** trace the init order, or keep the block and convert its output to world pixels
instead (costlier, always correct).

**Q7 — Is the REGIONS project actually unpaused?** The `REGIONS` record at empyrean
`origin/main:contract/projects.json` read `"state": "paused"` as of `f6ad6f5`, and report E
records the owner's pause verbatim: *"finish the parallax/raster stuff totally first"*
(2026-08-29T22:26). EFFECTS-W1 and W2 both read `done`, so the stated precondition is
discharged. Recorded as an observation about the record, not as a challenge to the brief.

**Q8 — Where does `effectsRef` live?** Report E §7 proposes implementing `effectsRef` **in the
per-section sidecar**; report C §2.1 puts it inside `regions.json`'s `bindings`. If both land
there are two homes for one binding and C's mixed-mode refusal becomes load-bearing
immediately. **What would settle it:** whoever sequences the effects and regions tool parcels
picking one. Not this parcel's call, but this parcel's problem if it is not made.

---

## 6. What I did NOT verify

Aim here first.

1. **I built nothing.** No `./build.sh`, no `sigil build`, no `.lst`. Every byte figure in §4 is
   a hand derivation from instruction encodings and **none of them is a measurement**. The
   first implementing step should replace the whole of §4's arithmetic with an `EndOfRom` delta
   and treat any disagreement as a defect in this document.
2. **I ran no emulator, by standing invariant.** Nothing here has been on a screen. Every gate
   named in §4 is TAGGED, not run. In particular `tools/parallax_crossing_gate.py` — the
   instrument the whole proof strategy rests on — I read but did not execute, and I do not know
   that it is currently green on master.
3. **I did not verify the ojz init ladder's ordering** (Q6), only read it.
4. **I did not verify which shape the effects lab's PRESET chord is in** (Q5).
5. **I did not check sigil's encoder** for zero-displacement folding, `bsr` relaxation, or
   whether `comptime for` can feed an `ensure` (Q1, Q4, and §4.0's caveat 2).
6. **I did not re-derive the VRAM figures** (376 tiles / 320 spent) the scope boundary rests on.
   The brief said they come from this lane's own card and invited disagreement; I read the
   re-ground doc's §4.2b independent verification of them and did not re-run it. **Nothing in
   this parcel depends on them** — parcel 1 allocates no VRAM — so a correction there does not
   reach this design.
7. **I did not re-run the reference-engine sweep.** §1.4 is report D's work, cited. I did not
   open `sonic3k.asm` or `s2.asm` to check a single line number in that table. The sweep's own
   gap — no Vectorman / Gunstar / Alien Soldier / Thunder Force IV / S.C.E. / homebrew — is
   reported but not filled.
8. **I did not verify aurora's half of anything.** C's editor design, the `regions.json`
   schema, `AURORA_REGIONS_SCHEMA.md`, the MCP surface: all cited from a peer repo at
   `origin/main`, none checked against aurora's tree. §3.3 is deliberately thin for that reason.
9. **I did not check the `*_port` standalone scopes.** Step 1 adds cross-seam names, which
   `CODING_CONVENTIONS.md`'s checklist says every byte instrument is blind to. I did not
   enumerate which ports lower `engine/structs.emp`.
10. **I did not price the DEBUG shapes.** Every byte figure is release. The DEBUG deltas
    (a changed `raise_error` string, the deleted `Boot_At` block, the lab chord) are named and
    unpriced.
11. **The cycle counts exclude prefetch and bus contention**, as does every other cycle figure
    in this repo's docs. They are comparative, not absolute.
12. **`pad(2)` is verified, not assumed** — `engine/ram.emp:211` and `:419` both use it. Listed
    here because it started as an assumption and was checked before this document was
    committed; the general point stands that everything else in this list was not.

---

## 7. Where the brief, the study, or the tree turned out to be wrong

**7.1 — The study's "~176 vs ~154 cycles" is right, and my independent derivation confirms it.**
Not a correction; a control. I derived today's no-crossing path at 176 cycles including the
entering `bsr.w`, and report A derived 176 by a different route. The rectangle form comes out
at 156 against A's 154; the two-cycle gap is a branch-taken assumption. **Both derivations
agree the change is a wash and nobody should decide on it.**

**7.2 — The study's ROM case has gotten four times worse, and parcel 0 is why.** B priced the
prize as "44 identity bytes of a 66-byte `Sec`" — 396 B on act 1, 2,112 B at
`MAX_ACT_SECTIONS`. Today `Sec` is 34 bytes and only 8 of them are identity, so the prize is
**72 B on act 1 and 384 B at 48 sections**, against a table costing 144 B on act 1. Regions are
now a **larger** net ROM loss than when the study called them one. This is not an argument
against the parcel, but it removes ROM from the argument entirely, and the re-ground doc did
not carry it because it was re-grounding claims rather than re-deriving the case.

**7.3 — A's 36-byte `Region` and its five extra fields should not be built.** `rg_music`,
`rg_sound_bank`, `rg_plc`, `rg_lookahead`, `rg_flags` are five `Sec` fields that were **deleted
on 2026-09-04 for having zero readers**. B's objection (d) predicted exactly this and the tree
has since proved it. The 16-byte record in §1.3 is the correction.

**7.4 — `docs/ENGINE_ARCHITECTURE.md` §7.12 is stale and self-contradicting, today, before
this parcel touches anything.** Its opening sentence reads:

> A section binds every visual effect through ONE pointer: `Sec.sec_effects` (offset `$34`)
> names an `EffectsPreset` (`engine/effects/preset.emp`, **38 bytes**)

Both figures are wrong — `sec_effects` is at `$1C` and `EffectsPreset` is 46 bytes — and the
*same section*, four paragraphs down, says so: "`sizeof(Sec)` went 66 → 34 and `sec_effects`
moved to `$1C`." Its field table also stops at `$24 ep_transition` and is missing
`ep_patch_motion` at `$26`. **Not fixed here** — the brief says do not edit that file in this
parcel — and booked for the implementing parcel, which owes §4.2 and §7.12 a rewrite anyway.

**7.5 — The engine restates a constant it already has a name for.** `Parallax_CheckBoundary`
spells `#SCREEN_WIDTH/2` and `#SCREEN_HEIGHT/2` while `engine/system/constants.emp:502-503`
declares `CAM_SCREEN_HALF_W = 160` / `CAM_SCREEN_HALF_H = 112`. Report C asked the *editor* to
read the reference point from one shared constant and never restate it; the engine is the one
restating it. Folded into step 3 as a one-line cleanup.

**7.6 — There are five lens reports, not four.** The brief and the study synthesis both name
four (A-D). `empyrean origin/main:docs/research/2026-08-29-painted-regions-study/` also contains
`E-effects-feature-audit.md` (33 KB) and a `PINS` file. E is a planned-vs-done audit of the
effects feature set, not of regions, and the synthesis does not cite it. Three things in it
bear on this parcel and are carried above: the owner's pause (Q7), the `effectsRef` two-homes
collision (Q8), and a contradiction — E20 records "palette cross-fade on crossing NOT
IMPLEMENTED" where A and B describe `ep_transition` → `Palette_ArmFade` as shipping.
**Source wins: it ships.** `Effects_InstallPreset` calls `Palette_ArmFade` on a non-zero
`ep_transition` (`engine/effects/preset.emp`), and D's reading — "ships, unused by every OJZ
fixture" — is the accurate one.

**7.7 — A's "`Region_Cur` must join the replay hash" is not needed.** Read out of
`engine/system/replay.emp:372-376`, the hash ledger covers `Camera_X`/`Camera_Y`, the four
section stream trackers and the two neighbour longs — and **`Parallax_Prev_Sec_X/Y` is not in
it today.** With non-overlapping rectangles the region is a pure function of `Camera_X/Y`,
which the hash already covers, so adding `Region_Current` would be hashing a derived value.

**7.8 — The brief's "four underlying lens reports" and "37 claims" framings both held up
otherwise.** The re-ground doc's §2 verdicts on parcel 1 (right shape, unbuilt, unblocked,
under-priced on tools) match everything I found in source, including the three Python tools
that carry their own copy of the `Sec` layout. Its correction that act 1 now runs nine presets
over nine sections is the single most useful fact in it for this design, because it turns the
migration into a 1:1 transcription and therefore into a clean byte-identical-behaviour proof.

---

## 8. TAGGED for the controller — needs a running ROM, not attempted

| # | what | when |
|---|---|---|
| T1 | `tools/parallax_crossing_gate.py` with rectangles equal to today's sections, requiring the same verdict. **The parcel's central proof.** Also: confirm it is green on master *before* the parcel starts, so a red is attributable. | step 3 |
| T2 | `tools/boot_override_gate.py` — the boot-select half of the same resolver | step 3 |
| T3 | `tools/sec5_band_witness.py` and `tools/row_remap_witness.py` repointed from `Parallax_Prev_Sec_X/Y` to `Region_Current` | step 3 |
| T4 | `tools/preset_lab_witness.py` — carries `SEC_SIZE = 34` / `SEC_EFFECTS = 0x1C` | step 4 |
| T5 | The first authored sub-section edge, on a screen, crossed at speed. Nothing before this proves the parcel bought anything. | step 5 |
| T6 | Q3's fixture: boot directly into a region whose preset differs in `ep_pal`, look at frame 1 | after step 5 |
| T7 | The measurement that would justify step 6: crossing-frame cost with sub-section edges authored | after step 5 |

---

## 9. Summary

A region is a 16-byte ROM record: an inclusive world-pixel rectangle stored span-major, an
`EffectsPreset` pointer with no default, and a parallax config that defers on zero. The act
carries a flat array of them; a region identity may own several rectangles by naming the same
preset twice. `Parallax_CheckBoundary` stops shifting the camera centre into grid coordinates
and instead tests it against the live rectangle cached in RAM — 20 cycles a frame cheaper, with
a linear rescan on the rare frame the test fails that is 5% of the cost of the install it
triggers. `Sec.sec_effects` and `Sec.sec_parallax_config` are deleted rather than kept as a
fallback, so the precedence ladder stays three rungs and the region scope *replaces* the
section scope instead of sitting beside it. Act 1's nine sections migrate 1:1 to nine
rectangles, which makes the existing `parallax_crossing_gate` a byte-identical-behaviour proof
before any content moves. The whole thing costs about 154 emitted bytes and 12 bytes of RAM,
which is a ROM loss — regions must be argued for on the sub-section edge they buy, and on
nothing else.

---

## 10. Closure pass — 2026-09-09 evening

**What this section is.** The controller's follow-up on §5 (open questions), §6 (not verified)
and §8 (TAGGED). Everything here was done against aeon `11647b64` in a clean detached worktree
(`git status` empty), with the sigil release binary of 2026-09-07 19:47, using
`FAST=1 DEBUG=1 ./build.sh` (the artifact-only lane; each probe build finished in about 3.6 s).
Line numbers below are at `11647b64`. Where a figure in §2–§4 is superseded, this section says
so and §2–§4 are left as written, so the record of what was derived blind stays legible.

### 10.1 Q4 — RESOLVED: sigil folds a zero displacement

`s4.bin` on master (built 05:07 today), `Effects_InstallPreset` at `$777E`: the instruction
for `movea.l EffectsPreset.ep_pal(a3), a1` (`preset.emp:396`, field at `$00`) sits at `$77C8`
and reads `2253` — `movea.l (a3),a1`, 2 bytes, 8 cycles. Not `226B 0000`.

Consequences for §4, which priced it pessimistically at 4: `Region_Resolve`'s first compare
`cmp.w Region.rg_x0(a0), d2` is 2 bytes and 8 cycles, so

| figure | §4 said | now |
|---|---:|---:|
| `Region_Resolve` emitted | 50 | **48** |
| step 3 emitted | +76 | **+74** |
| parcel 1 total (steps 1–4) | +154 | **+152** |
| scan: candidate rejected on the first compare | 40 cyc | **36 cyc** |

Nothing else moves: every other struct offset the parcel touches is non-zero, and the fast path
reads RAM through `(xxx).W`, not `(An)`.

### 10.2 Q5 — RESOLVED: the PRESET chord is DEBUG-only

`Debug_LabCycleHotkey` (`ojz_scroll_test.emp:2082`) opens `if DEBUG == 1 {` at `:2083` and
that block closes at `:2402`, the proc at `:2403`. The PRESET chord (`:2211–2262`) is inside
it. Step 3's rework of the chord costs **zero release bytes**; it is a DEBUG-shape delta only.

### 10.3 Q6 — RESOLVED: `Camera_Init` precedes the boot select — and T2 is a rewrite, not a re-run

All in `GameState_OJZScroll_Init` (`:585`): `Camera_Init` at `:677`; the DEBUG boot override's
`center_camera_on(Boot_At_X, Boot_At_Y)` at `:802` writes the clamped `Camera_X/Y`
(`center_camera_on`, `:315–335`, clamps against `Camera_X_Max` and writes `Camera_X` as 16.16);
the boot select at `:904`. So at `:904` `Camera_X/Y` hold the clamped boot position on every
branch, and §2.5's deletion of the `Boot_At → grid` block (`:893–901`) is safe.

**New finding, not in §2.5.** Selecting by the camera centre instead of by `Boot_At_X/Y`'s
section changes WHICH scope is selected whenever the boot position lies within 160 px (X) or
112 px (Y) of an act edge, because the camera clamps and `Boot_At` does not. That is the
*correct* answer — it is what the first `Parallax_CheckBoundary` will select one frame later,
and agreeing with it is the resolver's whole purpose — but `tools/boot_override_gate.py`
derives its expectation from the **`Boot_At` section**: `RomAct.sec_ptr(gx, gy)` /
`resolve_parallax(gx, gy)` (`:443–475`) restate `Section_GetSecPtrXY` over grid coordinates.
It already has `camera_expect()` (`:432`) for the clamp. Under regions the expectation is "the
region containing `camera_expect(px, py) + (CAM_SCREEN_HALF_W, CAM_SCREEN_HALF_H)`". **T2 is a
rewrite of the gate's expectation derivation, not a re-run**, and the rewrite must be inverted
(boot within 160 px of the right edge into a region that differs from the `Boot_At` section's
old answer, and confirm the gate would have been RED under the old derivation).

### 10.4 Q7 — RESOLVED: REGIONS is active

empyrean `origin/main` at `2dbbbc4`, `contract/projects.json`, record `REGIONS`:
`"state": "active"`, with the goal text recording *"PAUSE LIFTED 2026-09-09T07:08Z by the
owner"* and naming the 2026-08-29 pause as history. §5's reading of `paused` was of `f6ad6f5`
and was superseded the same day this document was written.

### 10.5 Q1 — RESOLVED by inversion: whole-table invariants live in `.emp`

Four builds in the clean worktree, a probe block appended to
`games/sonic4/data/levels/ojz/act1/act_descriptor.emp` (discarded afterwards; the worktree was
restored to `11647b64` and rebuilt to the same CRC):

| build | change | result |
|---|---|---|
| 1 | local `struct RegionProbeRect {x0,x1,y0,y1: u16}`; `probe_rect()` ctor with the §3.4 per-row `ensure`s; `const PROBE_ROWS: [RegionProbeRect; 9]` = the nine §3.1 rectangles; `comptime fn probe_first_overlap(r: array) -> int` (nested `for i in 0..r.len { for j in (i + 1)..r.len { … r[i].x0 … return i*16+j } }`, `-1` if none); `comptime fn probe_area_sum(r: array) -> int` with a `comptime var s: int = 0` accumulator; two `ensure`s over them | **GREEN**, `crc=db5aeb9f len=847277` — byte-identical to the baseline: consts and guards emit nothing |
| 2 | row 4 widened `x1: 4095 → 4200` (overlaps row 5) | **RED**: `[Error] Q1 PROBE: rectangles overlap (pair code 69)` (4·16+5) and `… do not tile the act (area 37963776)` — both from disk, both carrying the value |
| 3 | row 4 restored; row 8 shrunk `x1: 6143 → 6000` | **RED** on the tiling ensure alone: `area 37455872` |
| 4 | rows restored; `pub data OJZ_Probe_Regions: [RegionProbeRect; 9] = PROBE_ROWS` added | **GREEN**, 72 bytes emitted at `$185A2` (read back: `0000 07ff 0000 07ff 0800 0fff …`, nine correct rows), placed in the module's own section beside `OJZ_Act1_Sections` (`$18470`) with **no `map.toml` edit** |

So: the §3.4 table that said "whole-table, in the generator plus a pytest, not in `.emp`" is
**wrong**, and the two rows move to the comptime column. The shape for step 1 is a
**single-source table**: `const OJZ_ACT1_REGION_ROWS: [Region; 9] = [region(...), …]`, the
non-overlap and tiling `ensure`s over that const, and
`pub data OJZ_Act1_Regions: [Region; 9] = OJZ_ACT1_REGION_ROWS` — so the guards check the very
rows that are emitted, and a hand-written table has the same protection a generated one would.
Three `.emp` facts this settled are recorded for reuse in the controller's memory
(`emp-comptime-fold-and-zero-disp`). The real `Region` struct still goes in
`engine/structs.emp`, because `parallax_crossing_gate.py`'s `struct_offsets()` parses that file.

Step 1's "`games/sonic4/map.toml`: place the new data beside `OJZ_Act1_Sections`" is, on this
measurement, a no-op for a table declared in `act_descriptor.emp` — sigil placed the probe there
unaided. Keep the line as "confirm placement in the `.lst`", not as an edit.

### 10.6 T1 — baseline GREEN on master, and the gate cannot run "unchanged"

```
parallax_crossing_gate: OJZ act 1, 2048px sections, boot (1792,1024) in (0, 0)
  crossing A -> (1, 0) after 18 walked frames: staged 0x1347a (ParallaxConfig_OJZ_Default) (pcfg_transition=0, 15 frames left)
  crossing B -> (0, 0) after 5 walked frames: snapped 0x14800 (EditorSceneBinding_OJZ_Act1_Sec0) (pcfg_transition=1)
parallax_crossing_gate: PASS          exit 0 · 0.41 s · 17:29:30 local, uptime 2d 21:42
```

Run against a copy of the worktree's `s4.debug.bin` whose CRC32 was checked against the build
line before the run (`db5aeb9f`, 847,277 B). A future red is therefore attributable.

**New finding, not in §4.** The gate **reads `Parallax_Prev_Sec_X/Y` itself**: they are in its
required-symbol list (`:640–648`, `SetupError` if absent), `walk_to_section()` polls them every
frame to know a crossing has happened (`:464–488`), and the baseline sample reads them (`:413`).
Step 3 deletes both symbols, so the gate as written exits 2 on a step-3 ROM — "run it unchanged"
(§4 step 3, §8 T1) is not possible. What preserves the proof: the gate's crossing **detector**
is repointed at `Region_Current` (a pointer change is a crossing) and its **verdict** logic
(`Parallax_Current/Target_Config`, `Transition_Frames`, reg `$0B`, band count) is left untouched.
The repoint lands in step 3's commit and is inverted there (poll a symbol that never changes and
require the walk to FAIL at `WALK_MAX_FRAMES`, proving the detector is live). The proof
statement becomes "same walk, same verdict, detector repointed" — weaker than "unchanged", and
said so. T3's list gains this file.

The gate's coincidence refusal still holds under regions: region (0,0)'s three rungs are
`rg_parallax` = the editor binding, `ep_parallax` = Underwater, act default — distinct.

### 10.7 §6.9 — the `*_port` scopes that lower `engine/structs.emp`, enumerated

In sigil at `b64a8af8`, `crates/sigil-cli/tests/`: `structs_module.rs` (the shared harvest of
`engine/structs.emp`) and nineteen tests that parse it directly or ride the harvest —
`bg_anim_port`, `bg_port`, `buffers_port`, `camera_port`, `dma_queue_port`, `dplc_port`,
`entity_window_port`, `game_loop_port`, `load_art_port`, `ojz_run_a_port`, `parallax_port`,
`plane_buffer_port`, `section_port`, `sprites_port`, `test_p1_player_port`,
`test_p2_player_states_port`, `tile_cache_port`, `vblank_port`, `tranche4_negative_probes`.
Two carry an explicit **drift wall over `Act_*`/`Sec_*` names** (`parallax_port.rs:179`,
`plane_buffer_port.rs:132`), so step 1 (two `Act` fields) and step 4 (two `Sec` fields deleted)
each trip a sigil test by construction. The pairing §4 inferred from the name-move checklist is
therefore measured, not inferred: both steps run sigil's suite with `--no-fail-fast` and land as
a pair.

### 10.8 §7.4 — superseded on master

`docs/ENGINE_ARCHITECTURE.md` §7.12 was corrected on master on 2026-09-09 (the paragraph now
opens with `$1C`, carries a dated correction note, and its table includes `$26 ep_patch_motion`).
The stale-numbers finding is closed. What the implementing parcel still owes is the *regions*
rewrite of §4.2 and §7.12 ("one preset per section" becomes "one preset per region").

### 10.9 §1.4 — the reference sweep the study skipped, done

**S.C.E.** (`Sonic-Clean-Engine-S.C.E.-`, read against stock `skdisasm/sonic3k.asm`):

- Per-act dispatch is data (`Level_data_addr_RAM`, `Engine/Variables.asm:263–314`, populated by
  `levartptrs`), per-AREA logic is hand-written code reached through one RAM function pointer
  (`Engine/Core/Level Events.asm:10–13`). The shipped act's resize pointer is `dc.l 0`.
- **It has a 16-byte camera rectangle record.** `Check_CameraInRange`
  (`Engine/Objects/Check Range.asm:29–56`): `+0 min Y, +2 max Y, +4 min X, +6 max X`, then two
  side-bit thresholds, tested against `Camera_Y_pos`/`Camera_X_pos` with four compares. Same
  size, same reference point, same test as §1.3/§2.4. It is object-side, not a level table.
- **It scans a threshold table on the camera path every frame.** `Resize_MaxYFromX`
  (`:529–542`): linear over `{max-Y, camera-X}` longwords, `-1` terminated, sign bit = snap vs
  glide; `WaterResize_MaxYFromX` (`:562`) is the same for water. Inherited from Sonic 3
  (`s3.asm:32687–32701`). 1-D on X only.
- Palette, deformation routine, HInt and music are NOT area-tabled anywhere in S.C.E.: palette
  changes are `LoadPalette` (target, faded) or `LoadPalette_Immediate` (snap), none
  camera-triggered; deformation is the per-act `BackgroundEvent` pointer plus one boss flag;
  HInt is the single water-palette swap. Stock S3K does snap palette entries on camera
  thresholds inside its resize state machine (`sonic3k.asm:38978–38981`).
- Against: this lineage's area transitions carry side effects (PLC queueing, star-post save,
  Tails' CPU routine, tile-anim counters — `sonic3k.asm:38893–38921`) that a pure
  rectangle-to-preset table cannot express. Aeon's answer is the synthesis spec's own: *a region
  says what a place is; a trigger says when it changes* — side effects stay a trigger mechanism.

**Vectorman, Gunstar Heroes, Alien Soldier, Thunder Force IV, Ristar** (§10.9b; read from the
full listings `<game>_disasm/code/disasm.asm` — the `labels.txt` dumps carry no names):

- **None of the five stores area geometry as data.** Every spatial test found is a hardcoded
  `cmpi.w` in per-stage code, or a threshold ladder on a 1-D progress scalar.
- **Ristar** (VERIFIED): camera-X band gates as compare pairs (`disasm.asm:21143–21148`,
  `$011FB4`); one hand-written player AABB latched into a flag bit (`:21134–21141`, `$011F8E`);
  camera X and player X tested in adjacent instructions (`$010C7A`). Its per-stage identity
  record IS data — 2 bytes `{hint_idx, vblank_idx}` at `$05612C`, each pre-scaled ×4 into a
  pointer table — keyed by stage, not position. **And it latches on identity, not geometry:**
  `$010958` caches the requested ID in `$E673`, compares against the loaded ID in `$E671`
  (bit 7 = loaded), and skips the 32-byte palette record reload when equal. No dead-band
  anywhere. Presentation switching is a scripted sub-mode sequencer (`$01163A`), not spatial.
- **Gunstar Heroes** (VERIFIED): a descending compare ladder on an *accumulated scroll
  distance* `$CA04` (`:56923–56929`, `$5FC28`), plus a 15-rung routine-counter event list.
- **Thunder Force IV** (VERIFIED): a per-stage frame tick `$8C80` gates tile/palette loads;
  position equals time only because the game auto-scrolls. One HInt install per stage.
- **Alien Soldier, Vectorman**: NOT RECOVERABLE — the compare ladders present are boss HP,
  velocity clamps and object hitboxes (Vectorman's 4-word `{x_max,y_max,x_min,y_min}` walked
  with `cmp.w (a1)+,d0` at `$0085EE`/`$065418` is collision, not area).
- **A correction to our own research file:** `ristar_disasm/ANALYSIS.md:152` calls `$C01E` a
  "stage script interpreter"; the listing (`:14690–14742`) shows a demo-input recorder/player
  (button, duration pairs replayed from `$C0C4`/`$C0D4`). `docs/research/ristar-techniques.md`
  should be checked for the same claim — booked, not fixed here.

Two of the sweep's recommendations were weighed against §1: **(i)** carry an identity *index*
rather than a pointer (Ristar's shape) — not adopted, for §1.5's reason (nothing downstream
reads a region id, and the pointer removes an indirection from the hot path; the split can be
reintroduced if per-identity fields ever appear); **(ii)** make the reference point selectable
(Ristar tests camera and player) — not adopted; the camera centre is deliberate (§2.1) and a
player-referenced region is a *trigger* in the synthesis spec's vocabulary. **(iii)** Ristar's
latch-on-identity is the strongest precedent in the corpus for **step 6** (skip the install when
`rg_effects` is unchanged); it does not change step 6's gating, which rests on the DEBUG lab
chords mutating channels behind the guard's back, but it says the guard is the norm, not an
optimisation.

**What the sweep changes in §1.4.** Nothing in the shape; one thing in the argument. The
rectangle-with-four-compares is no longer "a generalisation of ICZ2's hand-written box" alone —
it is a record S.C.E. ships and scans against the camera, so the *form* has a second shipped
precedent. What remains without precedent in the corpus is the *table*: no reference engine
holds per-area identity as an array of rectangles. That is still the novel bet, and it is still
the owner's Q2.

### 10.10 What remains open, and who closes it

| item | status | who |
|---|---|---|
| Q2 — sub-section edges wanted? | card `REGIONS-V1-WORTH-IT` on the owner's console since 09:30Z | owner |
| Q3 — boot installs whole preset? | needs the step 5 fixture on a screen (T6) | implementing parcel |
| Q8 — where `effectsRef` lives | tools sequencing across aurora/empyrean | whoever sequences the tools parcels |
| T1 | baseline green; gate needs the §10.6 detector repoint at step 3 | step 3 |
| T2 | expectation rewrite per §10.3, inverted | step 3 |
| T3 | `sec5_band_witness`, `row_remap_witness` **and `parallax_crossing_gate`** repointed | step 3 |
| T4–T7 | unchanged from §8 | steps 4–5 |

### 10.11 Revised net

| step | emitted bytes | RAM |
|---|---:|---:|
| 1 — record + table | +150 | 0 |
| 2 — resolvers retyped | 0 | 0 |
| 3 — rectangle crossing | **+74** | +12 |
| 4 — delete `Sec` identity | −72 | 0 |
| **parcel 1 (steps 1–4)** | **+152** | **+12** |

Still a ROM loss; still to be argued for on the sub-section edge and nothing else. Every figure
above remains an emitted-byte derivation (§4.0 caveat 1 stands: the deb2 appendix makes the ROM
length delta unpredictable); the first implementing step replaces them with an `EndOfRom` delta.

### 10.12 §3.1 row 7 — WRONG, corrected 2026-09-09 by a later parcel

Filed by `parcel/section-effects-record-fix`, which was not this design's lane. Recorded here
because §10 is where a returning reader looks for what moved after the closure pass, and
because the correction lands in the one table §4 step 1 transcribes verbatim.

**The claim.** §3.1's row 7 read `ojz_act1_sec_scene(sec: 7)` **— returns 0, act default
stands**, under a heading that says **verified**.

**It is false, and the derivation is in §3.1 in full.** `section_7.meta.json` (landed
`c1d0a6be`, 2026-09-05) binds `"sceneRef": "ojz_act1_sec7_worldwater"`; the generated chooser
carries `if sec == 7` (`effects_scenes.emp:346`) yielding the emitted record at `:168`.
Section 7 resolves at rung 1.

**Three things worth carrying past the fix itself.**

1. **"Verified" did not fail on staleness — it failed on the ORIGINAL.** `c1d0a6be` is an
   ancestor of `944c5cc0`, the SHA §0 pins as the grounding point, so the tree in front of
   this document already contradicted the row. The row was inherited from
   `act_descriptor.emp:347-350`'s comment, which is where it had gone stale on 2026-09-05,
   and re-derivation stopped at a comment rather than reaching the chooser. **§0's rule
   ("re-derived from source, not copied") held for the numbers and failed for exactly the one
   cell whose source is a generated file.**
2. **The whole column was under-specified, which is how one wrong cell survived review.**
   Only rows 0 and 7 carried a verdict; the other seven carried the bare call. A reader
   scanning for disagreement sees seven cells that assert nothing and two that disagree with
   each other. All nine now state their derived verdict.
3. **Row 5 is a trap the corrected table now names.** Its `sec_parallax_config` really is 0,
   but 0 there does **not** mean "act default": rung 2 finds `ParallaxConfig_OJZ_Underwater`
   on `OJZ_Preset_Sec5`. A migration that transcribes rung 1 alone changes what section 5
   looks like.

**Scope.** That parcel corrected this row, the eight rows around it, and the upstream
`.emp` comments the row was copied from. It re-verified **nothing else** in this document.
