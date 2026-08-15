# Effects P3 Parcel P — the patch generalisation

**Date:** 2026-08-15 · **Status:** reviewed, awaiting owner sign-off
**Base:** aeon `9dcfa8b3` / sigil `ccfc6226`, chain 118, four shapes rebuilt to the handoff CRCs
(`0fcdcbaa` / `50f6ae69` / `6af0112d` / `fdc82cc0`) at the top of this session.

Roadmap: `docs/superpowers/2026-08-14-effects-crown-roadmap.md` ("P — the patch generalisation
(the crown unlock; do this before D)").

**Split into two parcels** (§4, §7). P-a is the encoder and is byte-moving but runtime-free; P-b is
the runtime. The seam is load-bearing, not cosmetic: P-b's entire risk is that it trusts the
`arm_off` values in P-a's table, and P-a proves them byte-exactly at build time first.

**Review provenance.** This spec's first draft was reviewed by three adversarial lenses on
2026-08-15 (two Opus, one Fable) covering encoder/runtime correctness, authoring surface + guard
liveness, and blast radius + gate honesty. They returned 34 findings, nine design-changing. Every
design-changing finding is folded in below and attributed at §11. Three claims of the draft were
**false** and are corrected in place: the deletion/pin claim (§8), the gate instrument (§7.2), and
the gate's own success predicate (§7.1).

---

## 0. What P is actually for, after re-deriving against the tree

The roadmap bills P as deleting four things in one move. **Two are already dead** and the spec must
not claim credit for them:

| Billed | Actual state on `master` |
|---|---|
| the `init_count == 1` trap | **already gone** — blanket restore killed the init header; `WATER_TEMPLATE_ARM0_OFF = 2` is structural (`raster.emp:751`) |
| the `sh: 1` hack | **already gone** — `raster_dsl.emp:289-296` records `sh` stays required as documentation, not safety |
| the magic offset | **OPEN** — `Raster_PatchWaterLine` writes `Raster_Buf_B + 2` on all three exits (`raster.emp:856/866/869`); only a hand-written `ensure` (`ojz_effects.emp:238`) says that word is an arm word |
| one moving boundary per section | **OPEN** — `Raster_Buf_B` and `Raster_Water_World_Y` are both single; P3 spec §9 parked "two independently patched effects in one section" as out of scope |

P's real content: **the offset stops being magic, and the one-boundary limit dies.**

### 0.1 The patched path is DEAD on master, and P-b must revive it

**CONFIRMED by tracing, and independently by review lens C.** Since C2 merged, no patched program
renders anything:

1. `ojz_scroll_test.emp:286-288` installs `OJZ_WaterRaster` in Init → `Active_Buf = Buf_B`.
2. `Parallax_Init` seeds `Parallax_Prev_Sec_X/Y = $FF` (`parallax.emp:126-128`), so
   `Parallax_CheckBoundary` (`ojz_scroll_test.emp:378`, **before** the patch call at `:384`) reports
   a crossing on Update frame 1.
3. `Effects_InstallPreset` reads `OJZ_Preset_Sec0`, whose `ep_patched` is 0 (`ojz_effects.emp:540`),
   and stages the static `OJZ_TestRamp` (`preset.emp:212-224`).
4. `Raster_VBlank .copy_program` re-points `Active_Buf` at `Raster_Buf_A` (`raster.emp:491-494`).
5. From that frame on, `Raster_PatchWaterWorldY`'s liveness test (`raster.emp:892-894`) takes
   `.not_patched` **forever**.

This is a **regression introduced by C2's total binding**, not by P: EFX-1 recorded water surviving
exactly one crossing; total binding made it survive **zero**. C2's gate evidence could not catch it
because nothing was measuring Buf_B. It is booked separately in `docs/BUGS.md` as the EFX-1
successor and is **not** P's to fix incidentally — but it has two consequences P owns:

- any P gate phrased around "the water boundary" measures nothing until the path is live again;
- **P-b must convert an OJZ section's preset to `patched:`**, which by `preset.emp:115`'s
  exclusivity ensure means that section gives up its static raster program. That is scope, and §7
  books it.

---

## 1. The authoring surface

### 1.1 `patchable` takes and returns a fire LIST

```
pub comptime fn patchable(fires: array, ch: int, lo: int, hi: int) -> array
```

Two corrections against the draft, both from review:

- **It is list-level, not fire-level.** Every `fx_` preset returns a fire *list*
  (`raster_dsl.emp:382-422`), so a fire-level `patchable(f, …)` would be a type error at exactly the
  call an author reaches for first — `patchable(fx_tint_band(…), …)`. List-level composes with the
  preset library and with `compose` directly. `ensure(fires.len == 1)`: marking a multi-fire preset
  would clamp all of its fires onto one line.
- **It carries an explicit channel `ch`.** The draft let indices be encoder-assigned ordinals, which
  gave an author no way to know which RAM slot drives their fire except by counting patchable fires
  in program order — fragile under `compose` merging, and it silently dropped the handoff's actual
  ask ("emit its offset as a **named constant**"). `ch` makes the identity authored, and makes §5's
  guard 3 check real facts.

```
compose([
    patchable(fx_tint_band(line: 120, slot: 0, pal_line: 2, entry: 4, count: 3, sh: 1),
              ch: 0, lo: 40,  hi: 180),
    patchable(fx_vscroll_split(line: 190, offset: $0043),
              ch: 1, lo: 181, hi: 223),
])
```

`RasterFire` gains a second variant, `Patch(line, ch, lo, hi, ops)`. Every `match` on `RasterFire`
becomes two-armed. Sigil **does** enforce exhaustive comptime enum matches — CONFIRMED at
`sigil-frontend-emp/tests/eval_match.rs:101-121`, which emits `[match.non-exhaustive]` naming every
missing variant — but see §1.2 for what that guarantee does *not* cover.

### 1.2 `compose` must be rewritten, and exhaustiveness will not tell you

The draft claimed compose was unchanged and leaned on exhaustive matching to catch any path that
dropped the mark. **That argument is wrong.** `compose` destructures via `fire_screen_line` /
`fire_ops` (`raster_dsl.emp:428-433`) and **reconstructs** every merged fire through
`fire(line, ops)` (`:365`), which returns a `Fire`. Adding `Patch` arms to the two accessors
satisfies exhaustiveness *completely* — and compose then compiles clean while stripping
patchability from every composed program. Exhaustiveness polices destructuring; the loss happens in
reconstruction, which no `match` ever sees.

So compose's per-line walk carries band state explicitly:

- patchable + static on one line → **patchable**, band and channel inherited;
- patchable + patchable on one line → legal **only** when `ch`, `lo` and `hi` all match, and they
  then move together (this is "layer S/H onto the moving water"); any disagreement is a build error
  (§5 guard 8). This is why §2's disjointness is not violated by same-line merges: compose folds
  them into **one** record before the interval walk ever runs.

### 1.3 The interval invariant, stated once, in fire lines

The draft stated this across two coordinate systems and the inconsistency was load-bearing. Stated
**once, in fire-line space**, matching `fire_lines` (`raster_dsl.emp:601-612`):

Each record has a possible **fire-line** interval — `[L, L]` for a static fire (`L = screen − 1`),
`[lo − 1, hi − 1]` for a patchable one. Priming records are `[0,0]` and `[1,1]`. The invariant:

```
hi_fl[k-1] < lo_fl[k]     for every adjacent pair, priming records included
lo >= 3, hi <= 223        (screen lines, per fire's existing bounds)
```

**Why this is the parcel's most dangerous predicate.** `gap = L[k] − L[k−1] − 1` is stored as a
byte. A violated invariant yields `gap = −1`, whose byte is `$FF` — and `$8AFF` is
`RASTER_ARM_PARK` (`raster.emp:181`). A one-line interval overlap therefore **parks the counter and
kills every fire after it**, silently, with no other symptom. The concrete break: static fire line
100 followed by a patchable band whose `lo` is screen 101 → fire line 100 → identical lines →
`gap = −1`. Guard 2 (§5) is what stands between the author and a black chain, and its message must
name that consequence.

Reaching `$FF` from *above* is impossible: max gap is 219, held by `raster_dsl.emp:50`. CONFIRMED.

---

## 2. The emitted image

```
pub comptime fn patched_program(fires: array) -> array
pub comptime fn patched_words(fires: array) -> int
```

`patched_program(P)` emits the ordinary program **padded to exactly `RASTER_BUF_SIZE` (128) bytes**,
followed by the patch table:

```
byte 0..127   program  [mask][arm0][opc0][arm1][opc1] … [$8AFF][$FFFF][pad $0000 …]
byte 128      count            — WORD; number of authored fires (records 2 .. n-1)
byte 130+     entry × count, 4 words each:
                 [arm_off][line_src][band_lo_fl][band_hi_fl]
```

- `arm_off` — byte offset **into Buf_B** of the arm word this entry rewrites: the arm of record
  `k−2`, pre-resolved by the encoder so the runtime keeps no offset history.
- `line_src` — a literal **fire line** (0..222, high bit clear) for a static record, or
  `$8000 | ch` for a patchable one.
- `band_lo_fl` / `band_hi_fl` — the band in **fire lines**, read only for a patchable entry. A
  static entry writes its own fire line into both, so **every field of every entry is in fire-line
  space** (the draft mixed screen and fire lines inside one record).

`count` is a **word**, read with `move.w`. `patched_program` routes through `raster_program`, which
already refuses an empty fire list (`raster_dsl.emp:684`), so `count >= 1` and the runtime's
`subq #1 / dbf` do-while cannot execute a bogus iteration.

**The table's address is `ep_patched + 128`** — constant, so no preset field is needed to find it.
Padding is not waste: `Raster_CopyPatchedTemplate` copies exactly `RASTER_BUF_SIZE / 2` words
(`raster.emp:779-782`), so the copy stops **precisely** at the table boundary — the table is never
partially copied, CONFIRMED. Cost: a patched template goes from ~24 bytes to `128 + 2 + 8·count`
(154 bytes for the two-channel fixture).

### 2.1 The arm identity

`arm_at(L, i) = $8A00 | (L[i+2] − L[i+1] − 1)`, park past the end (`raster_dsl.emp:625-628`).
Writing record `k−2`'s arm needs exactly `L[k−1]` and `L[k]`, which is why the runtime walk carries
one previous line and nothing else.

Review lens A verified this numerically for n=3 (reducing to `$8A00|(M−3)`, matching the shipped
`$8A75` at `ojz_effects.emp:248`), n=4, n=5, patchable-first, patchable-last, and two adjacent
patchables: **every arm that can change is written, and no park arm is.** The walk covers
`k = 2..n−1` → arms `0..n−3`, exactly the non-park set.

---

## 3. Density — the guard three lenses found missing

`check_density` (`raster_dsl.emp:583-595`) computes the gap from **authored** lines. A patchable
fire's authored line is a placeholder for an interval it will not stay in, so the existing guard
goes **vacuous** for every patchable record. Concrete: channels banded `40..120` and `121..200`
pass disjointness, and `check_density` sees the authored gap (160 lines) and passes trivially — while
at runtime they clamp to 120 and 121, putting two 3-word CRAM fires **one scanline** apart at a
measured 526 cycles against a 488-cycle line. That is exactly the overrun `check_density` exists to
refuse, and it renders as a visible mid-line colour change.

**Guard 8:** for every adjacent pair where either side is patchable, check the cost against the
**minimum possible** separation `lo_fl[k] − hi_fl[k−1]`, not the authored difference. The bands make
this computable, which is the strongest argument for the band ruling and the draft omitted it.

This also answers the `RASTER_MAX_PATCH` sizing question correctly: the binding constraint is the
**band budget under density**, not RAM. Disjoint bands over `3..223` means
`Σ(hi_i − lo_i + 1) + (N−1) <= 221`, so four channels each free to traverse the screen is not
expressible — a single water line with 200px of travel consumes the budget alone. `RASTER_MAX_PATCH
= 4` stands, with that stated.

---

## 4. P-a — the encoder parcel

**Scope.** `RasterFire::Patch`; `patchable`; the `compose` rewrite (§1.2); `patched_program` /
`patched_words`; guards 1-9 (§5); a new `OJZ_TwoChannel` patched fixture emitted as `pub data`.
**No RAM change, no struct change, no deletions, no runtime code.**

**Gate.** A hand-word comptime twin of the *complete* patched image — program, padding **and**
table — compared with `first_mismatch` **plus a separate `.len` ensure** (the prefix trap,
`raster_dsl.emp:721-728`: `first_mismatch` returns −1 whenever `a` is a prefix of `b`). Every one of
the nine guards proved **by inversion** — flip the predicate false, confirm the build FAILS, flip
back — which is the only proof this codebase accepts, per the handoff's vacuous-guard ledger.

Plus: `SIGIL_WARNINGS=full DEBUG=1 ./build.sh 2>&1 | grep module.unreachable` diffed before and
after (empty diff required); `tools/emp_helper_closure.py` run, because `raster_dsl` is a
COMPTIME_HELPERS member and every public name in it is glob-injected tree-wide; four-shape boot;
sigil suite; goldens; repin → refreeze `--ab`.

---

## 5. Guards, and the spelling each must take

All nine live in modules inside sonic4's use closure and are proved by inversion.

1. band within `3..223`, `lo <= hi`;
2. **intervals strictly ascending and disjoint in fire-line space** (§1.3) — message must name the
   silent-park consequence;
3. `ch` valid: `< RASTER_MAX_PATCH`, unique across the program, dense from 0;
4. the authored nominal line lies **inside** its own band (`lo <= line <= hi`) — otherwise a
   template ships with a default schedule violating its own invariant;
5. `patched_program` asserts `out.len == patched_words(fires)` **inside the emitter**, where
   `patched_words` computes independently through the `op_size` path — not the draft's
   `patched_words == 64 + 1 + 4*count`, which is a tautology when `patched_words` *is* that formula;
6. `arm_off[k] == 2 * arm_word_index(k−2)` **per entry** — an equality against a re-derived layout,
   not the draft's set-membership ("points at *some* word the encoder emitted as an arm word"),
   which admits pointing at the wrong record's arm and corrupting the schedule at runtime. The
   layout is re-derivable from `op_size` (`raster_dsl.emp:467-474`): word 1, word 3, then
   `5 + Σ_earlier(2 + Σ op_size(o))`;
7. `RASTER_MAX_PATCH` is a power of two (the runtime masks with `RASTER_MAX_PATCH − 1`);
8. **density under bands** (§3);
9. compose's same-line merge agrees on `ch`, `lo`, `hi` (§1.2).

**Two spelling rules the plan must follow, both recorded traps:**

- **Constant names in a comptime fn body resolve at the CALL site.** Imported names do not travel —
  `compose`'s bounds collapsed to an empty range at every call site and silently returned zero fires
  (`raster_dsl.emp:334-342`). So `RASTER_MAX_PATCH` is **defined in `raster_dsl`** (a
  COMPTIME_HELPERS member, glob-injected everywhere including `raster.emp` and `ram.emp`), and
  guard bodies spell literals held by module-level pins, exactly as `raster_dsl.emp:34-59` does.
- **`{}` in an `ensure` message is an interpolation.** Interpolate parameters and locals only;
  spell constant names out in prose. `RASTER_{MIN,MAX}_FIRE_LINE` emits `unknown name MIN` instead
  of the diagnostic — latent until the guard fires (`raster_dsl.emp:40-44`).

---

## 6. P-b — the runtime parcel

### 6.1 `Raster_PatchAll` runs at VBlank, not from the main loop

The draft put it in the engine loop. **That tears the schedule**, and the reason the current design
gets away with it does not generalise:

Today exactly one word is patched — the *priming* arm at `Buf_B + 2`, consumed at the frame-top
rewind (`raster.emp:510-514`) — so the main-loop write always lands after this frame's rewind and
takes effect next frame: a clean, uniform one-frame lag. `Raster_PatchAll` writes one byte per
record **scattered across the whole buffer**, while `Raster_HInt` is concurrently walking that same
buffer during active display. Records the cursor has passed keep this frame's gaps; records ahead of
it get next frame's. Because every arm is a **relative** gap, a mixed set does not land "some fires
early" — it desynchronises the entire tail of the chain, on **every frame the camera moves**.

So `Raster_PatchAll` is called from `Raster_VBlank`, in the window the rewind already owns, before
`HBlank_Install`. Latency is unchanged, because today's write is already effectively next-frame.

### 6.2 The routine

```
Raster_PatchAll () clobbers(d0-d4/a0-a2)
    move.l  Raster_Patch_Tab, d0            ; liveness: the TABLE, not Active_Buf (§6.3)
    beq     .none
    movea.l d0, a0
    lea     Raster_Buf_B, a1
    lea     Effects_World_Y, a2             ; indexed access needs its own An (§6.4)
    move.w  (a0)+, d4                       ; count (word)
    subq.w  #1, d4
    moveq   #1, d0                          ; prev fire line = L[1] = 1
    move.w  Camera_Y, d3                    ; integer word of the 16.16 camera
.entry:
    move.w  (a0)+, d1                       ; arm_off
    move.w  (a0)+, d2                       ; line_src
    bpl     .static
    and.w   #RASTER_MAX_PATCH-1, d2
    add.w   d2, d2
    move.w  (a2, d2.w), d2                  ; authored world Y
    sub.w   d3, d2                          ; screen line; may go negative
    subq.w  #1, d2                          ; -> fire line, ONE conversion, here
    cmp.w   (a0), d2
    bge     .lo_ok
    move.w  (a0), d2                        ; clamp to band_lo_fl
.lo_ok:
    cmp.w   2(a0), d2
    ble     .hi_ok
    move.w  2(a0), d2                       ; clamp to band_hi_fl
.hi_ok:
.static:
    addq.l  #4, a0
    move.w  d2, d1                          ; (see plan: d1 holds arm_off; use a scratch)
    sub.w   d0, d2
    subq.w  #1, d2                          ; gap = L[k] - L[k-1] - 1
    move.b  d2, 1(a1, d1.w)                 ; THE S3K STEAL — low byte IS the counter
    ...
    dbf     d4, .entry
.none:
    rts
```

Corrections against the draft, from review: `move.w (Raster_Patch_World_Y, d2.w), d2` **is not a
68000 addressing mode** — indexed access to an absolute array is `lea` + `(An, Dn.w)`, per
`raster.emp:654-655` — and the draft had no free address register for it; the clobber list was
undeclared (contract closure requires it); and `d6`/`d7` were gratuitous. The register assignment
above is indicative and the plan must settle it against a real assembly of the routine.

**The S3K steal, better than the roadmap states.** Every arm word is `$8Axx` **including the park
word `$8AFF`**, so the counter is the low byte and park is just `$FF` in the same byte: a single
`move.b`, no `ori.w`, no masking, and no separate parking path.

**Debug guard.** Under `DEBUG`, a negative `gap` raises an error rather than writing `$FF`. §1.3's
failure mode is a silent whole-chain park; it should not be silent in a debug shape.

### 6.3 Liveness is the table pointer, not `Active_Buf`

`Raster_VBlank`'s explicit-clear path (`raster.emp:483-490`) runs `HBlank_Uninstall` and zeroes
`Raster_Program` but **never touches `Raster_Active_Buf`** — so after a `Raster_Install(0)`
following a patched section, `Active_Buf` still equals `Buf_B` forever and an `Active_Buf`-gated
patcher would keep writing a dead buffer. Latent today only because the preset path always installs
`Raster_Program_None` rather than 0 (`preset.emp:222`).

So: gate on `Raster_Patch_Tab != 0`; `clr.l Raster_Patch_Tab` in **both** `Raster_VBlank`
teardown paths; and in the install, set `Raster_Patch_Tab` **before** `Active_Buf`, closing the
window where a live-looking state points at the previous template — or, on the first install after
boot, at 0 (`movea.l 0,a0` then reading the vector table as a count).

### 6.4 Install, RAM, and world-anchor ownership

```
Raster_InstallPatched (a0 = patched template, a2 = *u16 authored world Ys)
```

`a1` is **not** available for the anchor pointer: `Raster_CopyPatchedTemplate` declares
`clobbers(d1/a0-a1)` and uses `a1` as the Buf_B write pointer (`raster.emp:774-782`). Install also
does `clr.w Raster_Dense_Lines` — neither `Raster_VBlank` nor `Raster_CopyPatchedTemplate` clears
it today, so crossing from the dense gradient section into a patched one mid-run leaves the handler
in `.dense_body` streaming a stale cursor (pre-existing; P-b is where it becomes reachable).

RAM:

```
Effects_World_Y:   [u16; RASTER_MAX_PATCH]   ; owner-neutral name, NOT Raster_Patch_World_Y
Raster_Patch_Tab:  u32                       ; -> ROM table (template + 128)
```

**On the name and the copy.** Review proposed reading the preset's anchors in place so that W
(world-anchor ownership) later adds a *reader* rather than relocating storage. Half right: the
preset's array is in **ROM**, so reading in place makes anchors immutable and forecloses rising lava
— P's own motivating case. The synthesis: keep the RAM array (mutability is the point), name it
**owner-neutrally** so W adds a reader instead of moving storage, and ship the setter the draft
forgot:

```
Effects_SetWorldY (d0 = channel, d1 = world Y)
```

Without it, "lava that rises" is only expressible by poking raw RAM at a guessed index — and the
handoff's ask was a *named* handle.

**Declared delta:** re-entering a section **resets** an animated anchor to its authored value.

`Raster_State` net change: `+4 (Patch_Tab) +8 (Effects_World_Y) −2 (Water_Line) −2
(Water_World_Y) = +8`; all offsets stay even. `RASTER_STATE_SIZE` moves 288 → 296, which the budget
model reads via `tools/effects_budget_model.toml:138` (`raster_state_bytes`) — EFX-5's subject.

### 6.5 Preset

The anchors go **inline**, not behind a pointer:

```
ep_patch_world_ys: [u16; RASTER_MAX_PATCH] @ $1C     ; 8 bytes
ep_transition:     u16                     @ $24
struct EffectsPreset (size: 38)
```

A pointer would have introduced two couplings nothing can check: a `Label` carries no length, so the
template's channel count versus the array's length is invisible; and `preset.emp:91-96` records, in
that very file, that an `ensure` comparing an imported data symbol to an integer is **unevaluable
and silently always-passes** — a vacuous-guard generator. The draft's "the `patched != 0 ||
patch_world_y == 0` ensure follows the rename" was therefore false: the guard would die on contact.
An inline array has no null value, and `preset()` validates the literal's length at comptime.

Note the draft also placed the pointer at `$1C`, which **overlaps `ep_transition`**. The plan spells
the full field table, not a delta — this struct's declared size has already gone stale once
(`preset.emp:80-84`).

**Verify by inversion while there:** `preset.emp:115`'s existing exclusivity ensure
(`raster == 0 || patched == 0`) compares two `Label`s to 0 and may already be in the vacuous class
for the only case it exists to catch. Prove it with real Labels, not literal-0 defaults.

### 6.6 Deletions

`WATER_TEMPLATE_ARM0_OFF`, `Raster_PatchWaterLine`, `Raster_PatchWaterWorldY`,
`Raster_InstallWater`, `Raster_InstallPatchedWorldY`, `Raster_Water_Line`, `Raster_Water_World_Y`,
and the co-located arm0 `ensure` (`ojz_effects.emp:238`), superseded by guard 6. No wrappers, no
dormant compatibility path.

Two of these are named inside **`ensure` message text** — `raster_dsl.emp:709` and
`preset.emp:116` — which will not fail the build when the symbol goes. The full site inventory is in
the plan; `ojz_effects.emp:22` is a `use` import and **is** a hard compile break.

---

## 7. P-b's gate

### 7.1 The claim, corrected

The draft's predicate was **backwards**. With `screen_i = worldY_i − Camera_Y`, two world-anchored
channels hold a **constant** separation across camera motion — that is the *success* signature, not
the failure one. As drafted, a correct implementation fails the gate and a broken single-anchor one
passes. Worse, the relative predicate is not falsifying at all: an off-by-one-entry table walk, an
inverted clamp, and "channel 1 is actually a static fire" all satisfy "the separation changes".

**The gate asserts absolute, predicted rows:** at a stated `Camera_Y = C`, channel *i* renders its
transition at screen row `wy_i − C`, measured for **three** camera positions including one where each
channel clamps to `lo` and one where it clamps to `hi`. Both channels write **distinguishable**
colours, so a single-channel implementation cannot fake two boundaries.

Negative controls, two of them:
- a deliberately overlapping band pair must fail the **build** (guard 2), not render;
- one channel's anchor replaced by a fixed screen row must make the separation **drift by exactly
  the camera delta**.

### 7.2 The instrument

The draft named the replay net and the framebuffer in one sentence. **`replay_runner` has no
framebuffer, screenshot or image output of any kind** — CONFIRMED against
`oracle-next/crates/oracle-replay/src/cli.rs`, whose entire surface is
`--rom/--lst/--fixture/--negative-control/--max-frames/--stall-frames` plus exit codes 0-6. Its
`--negative-control` corrupts a checkpoint payload to `$DEADBEEF` and requires the desync trap to
fire: a control **for the harness**, not for the effect. And `ojz_fixture` is currently **red** on
master (open re-stamp, desync at tick 735, `docs/BUGS.md:328-360`).

**Ruling (owner, 2026-08-15): manual Oracle capture with the camera pinned.** Three stated camera
positions, absolute row assertions per §7.1, framebuffer as the instrument — `emulator_read_cram`
cannot see a mid-scanline CRAM write during active display. Pinning the camera rather than pressing
avoids the non-deterministic press-frame capture problem. Teaching `replay_runner` to dump
framebuffer rows is the better long-term answer and is booked as its own oracle-next parcel, not
smuggled into P.

### 7.3 Scope P-b owns because of §0.1

Converting an OJZ section's preset to `patched:` (surrendering that section's static program, per
the exclusivity ensure), rewriting `ojz_scroll_test`'s install and its per-frame call, and the
ledger surgery in §9.

---

## 8. Harness and ritual — the draft's claim here was false

**There are ZERO sites in the sigil repo for all seven deleted symbols.** Verified independently by
`rg` over the whole tree: none is a `[[symbol]]`, a `[[region]]` anchor, an `[[offset]]`, a golden
name, or a `pins.rs` constant. The `raster` region's anchors (`repin.toml:359-363`) are
`Raster_Install` … `Palette_LoadPal`, and `Raster_Install` survives. The deletions therefore cost
exactly one thing on the sigil side: the `RASTER` region **length** slides — a routine repin.

Two corrections in the other direction:

- **The real port-flip exposure is the LINK direction, and the draft missed it.** Moving the
  per-frame call from game code (`ojz_scroll_test.emp:384`) into `Raster_VBlank` keeps it inside the
  raster module, but if any part lands in `engine/system/game_loop.emp` it creates a **new outbound
  cross-seam call** from `game_loop`'s standalone re-lower — the case `repin.toml`'s
  `Palette_Compose` row exists for. If the plan puts anything there, it needs a
  `[[symbol]] name = "Raster_PatchAll" tests = ["game_loop_port"]` row.
- **The region-span rule does not apply.** P carves **no new section**; every change lands in
  existing modules. That sentence was inherited ritual boilerplate and hid the fact that P's repin
  surface is a plain length slide.

**Booked separately (vacuous gate):** the pins tagged `tests = ["raster_port"]` — `RASTER` region,
`RASTER_PROGRAM`, `RASTER_CURSOR`, `RASTER_PENDING`, `RASTER_BUF_A`, `RASTER_ACTIVE_BUF`,
`HBLANK_UNINSTALL_OFF` — are consumed by **no test**; there is no `raster_port` binary in `crates/`.
The raster module has no standalone port oracle, so P-b's runtime rewrite gets no isolated re-lower
coverage. P-b either fills that hole or declares it.

Also moving, each with a live consumer: `RASTER_STATE_SIZE` → the budget model; `EffectsPreset`
32 → 38, which moves the five pinned `OJZ_PRESET_SEC0..3`/`_PLAIN` symbols
(`act_descriptor_port.rs:146-150`) — routine repin. EFX-6's `act_sec_field_equs()` is **not**
affected; P touches no `Act`/`Sec` field.

---

## 9. Ledger surgery

- **EFX-4 CLOSES, it does not narrow.** The entry (`docs/BUGS.md:275-288`) is titled and scoped
  entirely to the patched/water template, and §2's padding closes exactly that. What remains open is
  a **different, unnamed** site: `Raster_VBlank .copy_program`'s fixed 128-byte read of short static
  ROM programs into Buf_A (`raster.emp:495-498`). Open a successor entry against that, with current
  line numbers — EFX-4's existing citations are stale and its named subject `Raster_InstallWater`
  ceases to exist under §6.6.
- **EFX-1 successor** — §0.1's regression, booked immediately and independently of P.
- **EFX-5** — `raster_state_bytes` 288 → 296.

---

## 10. Out of scope

- **Channels crossing each other, and a channel vanishing cleanly.** Both need the schedule-recompute
  variant. The clamp is a runtime policy and is replaceable; what makes recompute a **new table
  version** is that `arm_off` is pre-resolved per entry (§2) — exactly the assumption a sort-and-
  re-link breaks. Priced honestly here rather than implied to be free.
- **W (world-anchor ownership).** §6.4's owner-neutral naming is the only concession; the parallax
  seam is untouched.
- **R (mid-screen restore)** and the band compiler. Note R will want to write the buffer mid-frame,
  which §6.1's VBlank ruling deliberately forbids for the patcher — R must settle that on its own
  terms.
- **Splitting the VSRAM op class** off `RASTER_CRAM_MAX`.
- **A framebuffer dump for `replay_runner`** (§7.2) — its own oracle-next parcel.
- **EFX-2** stays open by prior ruling.
- **`lo == hi`** is **allowed**, not rejected: it is the only way to express a world-anchored fire
  pinned to a screen row, and it is trivially disjoint.

---

## 11. Attribution of review findings

Design-changing, folded in: compose reconstruction strips the mark (§1.2); no channel identity and
no setter (§1.1, §6.4); density vacuous under bands (§3, found independently by all three lenses);
main-loop patching tears the schedule (§6.1); the interval invariant's split coordinate space and
its silent-park failure (§1.3); the gate predicate inverted and non-falsifying (§7.1); the gate's
instrument does not exist and its fixture is red (§7.2); the patched path is dead on master (§0.1);
the parcel is two parcels (§4, §6).

Plan-level, folded in: the invalid addressing mode and register pressure (§6.2); the pointer's
unevaluable length/null couplings and the `$1C` overlap (§6.5); `Active_Buf` insufficient for
liveness and the install ordering window (§6.3); dense-run residue (§6.4); guards 5 and 6 vacuous or
weak as worded (§5); the constant-resolution and interpolation spelling rules (§5); EFX-4 closes
rather than narrows (§9); zero sigil sites and the real `game_loop` pin exposure (§8); `lo == hi`
should be allowed (§10).
