# Scanline Services — Unified Parallax + Raster Effects Design (C+)

**Status:** r2 — swept (7-seat adversarial panel, 66 findings adjudicated, 0 rejected;
r1 → r2 fold 2026-08-17 late)
**Owner ruling trail:** ratified Step-2 "full parallax engine phase"; approach C+ selected
by owner 2026-08-17 (one authored scene model, comptime lowering with per-game runtime
specialization, over the two proven runtimes).
**Research base:** docs/research/2026-08-17-parallax-phase-research-synthesis.md (34865383).
Supersedes the parallax/raster halves of 2026-07-02-raster-parallax-authoring-design.md
(its Aurora viewport guidance still stands). Composes with 2026-08-11-effects-suite-design
with TWO stated divergences: (a) the live in-editor cost meter is superseded for this phase
by the post-bake ledger (§5) — cost-as-you-compose defers to the Aurora lab phase alongside
live preview; (b) TS-simulator golden fixtures defer to the Aurora lab phase because no
simulator exists yet — this narrows that doc's acceptance bar for this phase only.
Does not reopen the banked effects-tail r3.1 (revival conditions restated in §4.2).

## 0. Requirements → design map

| Req | Where satisfied |
|---|---|
| R1 many H bands, distinct speeds | §2 layers (cap ruling), §4.1 curves |
| R2 deeper-reading BG | §2 vertical (vscroll splits at layer boundaries + v-factors) |
| R3 foreground parallax | §2 FG tier 1 = priority plane-B layers + sprite strips; plane-A strips = §9 non-goal |
| R4 BG tile animation interplay | §2 attachments, §4.3 (base-scroll binding rule) |
| R5 unified raster vocabulary | §1 one contract, §2 raster attachments |
| R6 corridors / floating origin | §6 (corridor machinery deferred to mega-act; rebase = structural contract until §4.11 exists) |
| R7 budgeted authoring | §5 |
| R8 pay-for-what-you-use | §3.2–3.3 (scene registry + capability mask) |
| R9 Aurora authorability | §7 |
| R10 feature-complete | §2 + §9 (every known gap explicitly in-vocabulary or non-goal) |

## 1. Architecture

```
SCENE MODEL (authored)      one document per section-config: world-Y layers + anchors +
                            attachments. Hand path = comptime .emp constructors; Aurora
                            path = JSON → effects_gen.py → .emp calling the SAME
                            constructors (§7; spiked in P5 before relied on).
      │ comptime
SCENE REGISTRY (per game)   the single emission path: one explicit module listing every
                            scene VALUE the game links (§3.2). A comptime fold over it
                            derives the capability mask and cross-scene checks. An
                            emitted-but-unregistered scene is impossible by construction
                            (scenes only emit via the registry).
      │ comptime
LOWERING (build time)       emits runtime-native records; owns ALL derived keys (mode,
                            DMA length, forcer set §4.1); computes the cost ledger and
                            ensure-fails over budget (§5); publishes the capability mask
                            via Game interface const (§3.3).
      │
RUNTIMES (proven engines)   parallax walker → HScroll/VSRAM tables (VBlank-DMA'd, never
                            HInt); sparse raster dispatcher (counter-fired HInt); VBlank
                            services (palette compose, DMA queue); HBlank_Install escape
                            hatch (runtime-resolved refs only, §7).
```

**The inversion:** geometry is declared once (world-Y layers + anchors); scroll factors,
deform, palette regions, vscroll splits, BgAnim strips, raster patches are attachments.
The lowering derives per-runtime representations and guarantees agreement at compile time.

**Deliberately unchanged:** the runtime execution split; reg $0B protocol;
`Parallax_Active_Config` routing; VBlank emit order (HScroll DMA → VSRAM → rest);
flat-fill remainder-tail guard; trampoline HInt dispatch; 16-frame plane-B-only lerp;
`Effects_LatchWorldLines` ordering; VSRAM N+1 landing model. §8.5 carries the trap ledger.

**Why not a unified kernel (rejected approach B):** buys no new effects (hardware-bounded
vocabulary), costs threaded dispatch in a 224-line hot path, hides mandated seams. B&R —
the best bytecode precedent — itself kept specialized writers for hot fills. B's best ideas
are absorbed: resumable budget → §4.4; combinatorial palette-DMA → palette compose lineage.

**Terminology/naming:** the scene-level constructor is **`layer()`**, not `band()` —
`band()` already exists twice with incompatible signatures (parallax `configs.emp:42`,
raster `raster_dsl.emp:612`, the latter helper-glob-visible). Prose may say "band"; code
says layer. All scene constructors live in a new `engine/level/scene_dsl.emp` namespace.

## 2. The scene model (authored vocabulary)

A **scene** = one section-config's visual behavior. Sections reference scenes;
`0 = inherit` semantics kept.

**Layers** — declared by `world_y` top (act space). Per layer:
- FG + BG scroll factors (existing shift-add encoding). A BG factor may be a
  **curve(from, to)**: the effective scroll ramps per line across the layer. Semantics
  (ruled): an **additive per-line delta over the layer's camera-tracked base scroll** —
  the base term `camX >> factor` is preserved; the spread `(camX>>to − camX>>from)` is
  computed once per frame per curve layer in the band hoist with a bounded `divs.w` by
  layer height (precedented: the transition ramp at parallax.emp:593), never in the line
  loop, never a multiply. Curves are camera-proportional; deform tables are fixed-profile
  — different semantics, both kept. **A layer may have a curve OR a deform ref, not both**
  (`ensure`) — the fill loop's register file is exhausted (verified: .lp_both uses all 16);
  the combination is a §9 future.
- Optional **deform ref** — ruled spelling (three variants, comptime enum — see §3.1):
  - `deform: none`
  - `deform: shared(phase)` — samples the scene's plane-shared table at a per-layer phase
    (this is what WindyHaze/SkyHaze/haze_fg actually are; does NOT trip MULTI_DEFORM_TABLE)
  - `deform: own(table, amplitude_shift_a/b, phase, speed)` — per-layer table+speed
    (trips MULTI_DEFORM_TABLE, extended record)
- Optional **attachments**: `palette_region` (lowers to raster PAL_REGION/ramp at the
  layer's boundary), `vscroll_split` (below), `bganim` (§4.3), `sprite_strip` (below).

**Scene-level scroll precision** — `precision: cell | line` is an EXPLICIT field,
independent of deform authoring. Rationale (closed-bug guard): OJZ's shipped configs
attach a zero-amplitude table (`DeformTable_Zero`) purely to force per-line mode because
per-cell tears smooth vertical parallax at band boundaries (permanently CLOSED per-cell
ruling). An author must be able to demand line precision with zero visible deform.
For byte-identity, `precision: line` on migrated scenes lowers to exactly today's
DeformTable_Zero attachment (same record bytes).

**The per-line forcer set** (ruled, exhaustive; the lowering owns it and feeds BOTH mode
twins — the fill-side key and the `engine.buffers` DMA-length key — from one derivation):
{ any H-deform table incl. shared, anchor_ch != NONE, any curve layer, `precision: line`,
any layer boundary not on the 8-px cell grid }. Each forcer prices the 896-byte line item
in the ledger (§5). "Twin-key desync impossible by construction" holds because this set is
the single source both twins consume.

**Anchors** — the existing patch channels, unchanged in mechanism, promoted in the model:
an anchor is a dynamic layer boundary ("boundary = channel N"). Parcel W's runtime split
stays. Interaction rules (ruled): the world-Y re-glue (§4.1) computes static layer tops
first, then the anchor split applies (the existing Step 4a → 4b order); an anchor split
inside a curve layer **continues** the curve (the per-line delta is indexed by absolute
screen line, so the split changes deform shifts below the boundary without
re-parametrizing the curve).

**Foreground parallax (R3), tier 1 — two mechanisms, both proven-shape:**
1. **Priority plane-B layers** — a plane-B layer whose BG art uses priority tiles renders
   in front of low-priority sprites and plane A: a foreground canopy/pillar layer with its
   own scroll factor, expressible TODAY with zero new runtime mechanism (per-layer plane-B
   factors already ship). The scene marks it `foreground: true` for documentation and so
   the ledger/gates know the priority-bit expectation (§8.3 instrument). Cost: those
   scanlines' plane B is spent on the FG layer (can't also show far background there) —
   an authoring tradeoff, stated.
2. **Sprite strips** — a `sprite_strip` attachment: a repeating sprite row at the layer's
   factor for sparse accents (vines, pillars — Shinobi-III-style). SAT-budgeted (§5 axis
   5: N sprites/line within the scanline sprite limit), engine-owned slots, priced.
**Plane-A strips are a §9 non-goal** (swept finding: plane A is the runtime-streamed
playfield with camera-locked vscroll — the World-of-Illusion static-layer premise does not
hold on this engine). Preconditions for ever revisiting are ledgered in §9.

**Raster programs** — existing sparse vocabulary authored as scene attachments bound to
layers/anchors. Dense tier remains a distinct program kind (existing constructors,
retained); sparse/dense exclusivity now enforced by the scene (`ensure`). Screen-level
(non-scene) raster programs — title cards etc. — remain hand-authored `.emp` calling the
DSL directly against the generic `Raster_Install`; stated so the scene model doesn't
appear to be the only path (it's the only *section* path).

**Computed effects** — a scene names an HBlank_Install handler by **registry index →
runtime-resolved pointer table** — never a comptime-folded symbol in an emitted image
(extern()-poisons-comptime trap, now in §8.5 by name). Cost: a **measured oracle pin**
per handler (NEEDS-MEASUREMENT row → measured before ship; the raster F1–F8 fixture
precedent). An unmeasured handler is a build error unless the game sets
`ALLOW_UNMEASURED_COMPUTED=1` (dev-only flag; ledger marks the row UNBOUNDED). This
replaces r1's author-declared cost rows (ruled: budgeting theater — an unverifiable
number must not flow into ledger sums, and its poison was unsatisfiable).

**Vertical (R2 "deeper-reading BG")** — ruled mechanism set (r1's per-band→per-column
lowering was wrong — columns are vertical, layers are horizontal; orthogonal axes):
- Scene-level `v_factor_bg`/center/offset — unchanged (15 = lock).
- **Per-layer vertical depth** = mid-frame whole-plane VSRAM changes at layer boundaries,
  lowered to the existing vscroll-split raster op (`fx_vscroll_split` family). Each
  boundary with a distinct v-factor = one raster fire, priced in axis 4. This is the
  banded near/far depth stack.
- **Per-column VSRAM** stays what it is: horizontal skew/wobble (AIZ-flame class),
  authored as a scene-level `v_deform` (table, shift, speed). Any scene using it MUST
  declare `left_column_mask: sprite_mask | factor0_lock | accept`; the sprite_mask
  mechanism is bound to the DEFERRED_WORK §"leftmost column" analysis: one engine-reserved
  SAT slot, 8-px masking column strip, emitted at scene install, priced in axis 5.
  FG per-column VSRAM stays unwired (§9).

## 3. Comptime lowering, registry & specialization

### 3.1 Lowering
Comptime functions consume scenes and emit runtime-native records. Rules (all swept):
- **Optional attachments are comptime ENUM VARIANTS with exhaustive match** (the
  RasterOp/RasterFire precedent) — never `Label = 0` defaults, which make "is X attached?"
  silently unanswerable (the documented vacuous-guard generator). Scene constructors are
  forbidden from reading the capability set (caps are folded FROM scene values —
  a constructor reading caps is an elaboration cycle).
- Record shapes are capability-dependent: no-new-capability scenes lower to the EXISTING
  28-byte header + 10-byte entries **byte-identically** (§8.1). Extended records (per-layer
  deform refs) exist only in games whose mask includes MULTI_DEFORM_TABLE. The walker's
  field displacements/strides become capability-selected comptime constants — a pervasive
  addressing rewrite carried explicitly in P3 (typed conditional-data spike included; the
  proven untyped `if CAP {..} else {Data.empty}` form forfeits size-annotation pins).
- Byte-identity preconditions (stated): intra-module data order preserved by hand through
  the migration; "byte-identical" means **image-identical after the routine repin ritual**
  (section labels move); migrated scenes' `world_y` values carry an
  `ensure(world_y % cell_quantum == 0)` so lowering hits today's `band_top_cell` exactly.
- The two shipped `hdr()` safety ensures (anchored split capacity ≤ MAX_PARALLAX_BANDS;
  anchor_ch < RASTER_MAX_PATCH) are ported by name into the scene constructors — which are
  always in the use closure (dead-guard trap).

**Migration scope (enumerated — r1's blanket DELETE was wrong):**
- SUPERSEDED & DELETED: parallax `hdr()`/`band()` authoring entry points in configs.emp;
  the sparse-raster *section*-authoring path in ojz_effects.emp; `games/sonic4/data/parallax/`
  as a directory (contents move under `data/effects/` scene modules).
- RETAINED UNTOUCHED: dense-tier constructors (`raster_gradient_program`/
  `raster_ramp_program`); `preset()`/`EffectsPreset` and palette variant/cycle
  constructors (they become what scenes lower INTO, not parallel authoring);
  `raster_dsl`/`parallax_dsl` internals (the lowering's implementation); the hand-authored
  PIN consts (`OJZ_TEST_HAND`, `OJZ_WATER_HAND`, `OJZ_TC_HAND`, `OJZ_VSRAM_HAND`) — their
  retirement belongs to the banked effects-tail parcel, not this one; the
  `games/sonic4/test/poison/` fixtures (they call raster_dsl directly and are unaffected —
  stated, with the poison_sentinel reachability edge re-verified in P1).

### 3.2 Scene registry & capability derivation
There is no comptime cross-module scan in sigil (swept: linkage is link-time; Labels are
opaque; the -D route is per-profile Rust-side and cannot carry derived values). Ruled
construction:
- Each game has ONE **scene registry module** listing every scene value:
  `pub const SCENES = [scene_ojz_caves, scene_ojz_underwater, ...]`. Scenes emit records
  ONLY via the registry's emission fold — an unregistered scene emits nothing and its
  section reference fails the existing missing-symbol path. The registry is also where
  cross-scene checks live (they need values, not Labels).
- A comptime fold over SCENES derives one **packed capability mask**.
- The mask reaches the engine as a **Game interface const** (`Game.SCANLINE_CAPS`) — the
  proven engine-side gating surface (camera.emp precedent). One packed const, not ~13
  (interface consts are per-game mandatory; demo binds one word). P1 spikes whether an
  `implement Game` const can be the computed fold result; fallback (still sound): the game
  hand-writes the mask word and a registry-side `ensure(mask == folded)` makes it
  derive-and-verify rather than hand-maintained.
- Force-enable for runtime-installed scenes: a game may OR extra bits into its mask
  declaration; the ensure then checks `folded ⊆ declared`.

### 3.3 Specialization
`if Game.SCANLINE_CAPS & CAP_X` bodies + use-closure elision. Depths (measured differently
— §8.2): module-level (zero scenes ⇒ zero parallax/raster/palette-compose bytes; demo is
the permanent witness), path-level (no-deform ⇒ no sampling loop; never-per-line ⇒ no
224-fill and no 896-B DMA entry; no-anchor ⇒ no Step-4b), data-level (§3.1 record shapes).
**Every comptime-gated block the lowering emits gets bracketing local labels** — required
for path-level span gates (§8.2), stated here as an emission convention, not an
afterthought.

## 4. Runtime changes

### 4.1 Parallax walker
- **World-Y re-glue:** layer tops recomputed from world space each frame (S3K
  seed-and-search adapted to the shadow-layer layout). **Capacity ruling:** the shadow
  contract stays `MAX_PARALLAX_BANDS = 8` (≤7 authored when anchored), Step-4a stays
  copy-all; world-Y buys ANCHORING and vertical gluing, not layer count. Sub-layer
  granularity is what curves are for; windowed re-glue over >8 declared layers is a §9
  future with its own re-derivation. This answers R1 explicitly: OJZ ships 5 layers today,
  has headroom to 7 anchored + curves inside each.
- **Curves** per §2 semantics: per-frame hoist (bounded divs by height), per-line additive
  delta; separate specialized loop variant; curve∧deform per layer forbidden.
- **Per-layer deform refs** (extended record, MULTI_DEFORM_TABLE).
- **Parcel W copy hardening (carried trap):** the two hand-unrolled 10-byte entry moves
  (parallax.emp:862-864, :891-893) are pinned by `ensure(sizeof(band_entry)==10)` today
  and rebuilt as sizeof-derived generated copies when the extended record lands.
- Non-strip FG lines unchanged: `-Camera_X` hard lock, plane A never lerps.

### 4.2 Raster dispatcher
Mechanism unchanged; lowering emits its programs, and the scene attachment for `patchable`
carries the full existing parameter surface (per-channel lo/hi clamp, offscreen_ship
trailer). **`OJZ_TwoChannel` is the named P1 migration acceptance fixture** (two channels,
three pinned word blocks — the hardest shipped case). Banked-work revival unchanged:
overlapping patchable layers ⇒ revive Part A against r3.1; VSRAM-op ceiling ⇒ evaluate
Part B. Neither scheduled.

### 4.3 BgAnim band binding
A `bganim` attachment derives its driver phase from the owning layer's **base scroll**
(`Parallax_Current_Scroll_B[layer]`) — ruled: for curve layers this is the defined
binding (the curve spread is per-line and has no single speed; binding to base is stated
authoring semantics, not an approximation bug). Ordering pinned as a contract: the new
driver kind requires `Parallax_Update` strictly before `BgAnim_Update` (already true;
now an ensure-documented invariant, not prose). Standalone strips unchanged.
`inject_editor_bg.py` LOCKSTEP gains the driver kind.

### 4.4 Degradation valve — designed, demand-pulled
Kept in the spec (design is sound — swept and verified pop-free for paused accumulators)
but **implementation is demand-pulled**: P4 builds it only if the OJZ showcase scenes'
ledgers demand it (owner's standing lag disposition is "accept"). Invariants (ruled):
- deferrable work PAUSES and resumes at identical phase — **catch-up stepping is
  forbidden** (a 2× resync step is the pop);
- the valve is **excluded from determinism surfaces**: DEGRADE is forced OFF in replay and
  gate lanes (deferrable mutations are lag-dependent and would poison Replay_Hash and
  pinned captures);
- scroll-critical work (camera, layer scroll, HScroll buffer, anchor latch) is never
  deferrable. Note: "lag-immune" BgAnim (Logic_Tick) means deterministic, not free — the
  valve addresses cost, not correctness.

### 4.5 Untouched inventory
As §1 "deliberately unchanged," plus: sparse arm-word precompute + priming records;
≤3-CRAM-words rule; EFX_BLANK_DELAY semantics; Raster_Install genericity.

## 5. Budget model (budgeted authoring)

**Denominators (swept — F1):** every axis budget is `pool − engine_reservation`, where the
engine reservation covers standing engine cost at a **defined worst-case camera state**.
Engine baselines (idle + max-diagonal) enter `tools/effects_budget_model.toml` as
NEEDS-MEASUREMENT rows measured on oracle-next profiler (wall-clock beside every figure).
The unanswered "who budgets the standing part" is answered: the ENGINE declares
reservations; scenes budget the remainder.

**The ledger's evaluation frame (swept — F3):** the **transition frame** — outgoing +
incoming configs partially live under Active_Config routing, the reg $0B mode-change
overhead, and the larger of the two HScroll DMA lengths. Steady-state is also reported,
but the pass/fail check runs against the transition frame of the worst adjacent-scene
pair (registry-derived — the registry knows all scenes; adjacency from section
descriptors).

**Axes (seven — RAM added):**
1. **Main-loop cycles** — walker cost from a **fitted additive model** (raster F1–F8
   precedent: small parameter set — per-layer, per-line-mode, per-curve, per-deform-ref,
   re-glue — pinned to oracle fixture measurements, 0-residual target), NOT per-variant
   re-measurement. Plus BgAnim, anchor latch, curve hoists.
2. **VBlank DMA bytes** vs `pool − reservation` (pool 7524 B NTSC H40; reservation = the
   buffers.emp fixed floor: palette lines, SAT, the HScroll entry itself + a declared
   streamer allowance). Per-line forcers price 896 B; the ledger shows the COMBINED
   per-line cost (DMA bytes + axis-3 drain CPU) so "12%" never reads as the whole tax.
3. **VBlank CPU cycles** — compose, enqueue, drain.
4. **HInt** — split per the swept finding: (4a) per-fire spacing = the existing G-A6 /
   `check_density` machinery, and the ledger's fire costs ARE `fire_cost_cycles` summed
   over the lowered program (never a parallel estimate — the drift the DSL pins exist to
   kill); (4b) per-frame HInt TOTAL — a genuinely new budget, NEEDS-MEASUREMENT (the
   toml's absolute HInt rows have never been measured; `interrupts.hint` conflates VBlank).
5. **Sprite slots** — sprite strips (per-line count vs scanline limit) + mask policy slots,
   against a declared object-system reservation.
6. **RAM** — scene record footprint incl. extended records × layer count, against the
   existing `[ram]` provenance gate.
7. **Computed-handler pins** — measured rows only (§2); UNBOUNDED rows fail outside the
   dev flag.
Also noted (unbudgeted, documented): ROM bytes per scene; max-contiguous-DMA-stall vs
Z80/DAC headroom (couples to the sound driver's DMA-survival design; a stall-length row is
carried NEEDS-MEASUREMENT for awareness, not gating, this phase).

**Ownership (swept — F5):** enforcement constants live in the comptime DSL (raster_dsl
precedent) as the single authority; the toml `[symbols]` gate pins PROVENANCE (drift
detection), never enforcement. Per axis, the ~~SUM~~ **MAX is enforced comptime** in the
lowering (it alone sees all scenes via the registry); the Python checker remains
constants-only. *(AMENDED 2026-08-19, P2 Phase 2 implementation finding, controller-
ratified: only ONE scene is live at a time, so a sum over the shipped registry (~500k
cyc against a 128k frame) would refuse a configuration that demonstrably runs. The
worst-PAIR sum is exactly the transition frame — §5's own evaluation-frame rule — and
belongs to Task 12, which remains blocked on a boundary-crossing measurement state.)*

**Ledger artifact (swept — producer named):** the lowering publishes per-scene ledger rows
as **named exported comptime consts** (zero ROM bytes); a formatter tool reads them from
the build's symbol table (.lst/deb2) and renders `<game>_scene_budgets.txt`. Derivation
stays single-sourced in .emp; Aurora later renders this artifact (post-bake — the live
pre-bake meter is deferred to the Aurora lab phase, superseding 2026-08-11's live-meter
sketch for this phase). P2 includes the symbol-readback spike.

**`budget_class`** — per-scene override for deliberate hero scenes, values resolved at
lowering against the game's declared class table in `game.emp`; the generator schema
passes it through without validating (sigil is the validator).

## 6. Transitions, corridors, floating origin

- Per-section transitions: existing machinery is the contract (unchanged).
- **Corridor machinery moved OUT** (swept YAGNI + untracked-warning findings): no
  `corridor_pair`, no advisory warning. The mega-act program owns corridor authoring;
  when it lands, skeleton compatibility becomes a hard registry `ensure` (the registry
  makes cross-scene checks possible — that hook is this design's contribution).
- **Floating origin:** world-Y layer tops and the anchor bank join the §4.11 rebase
  checklist. Until §4.11 exists (it is FUTURE/Phase-4), the "contract test" is
  **structural/declarative only** — an act-relative tagging check — stated plainly so it
  cannot be mistaken for runtime rebase verification, which is deferred to when the rebase
  mechanism ships.

## 7. Authoring pipeline (Aurora contract)

- Hand path: scene constructors in `.emp` under `games/<game>/data/effects/` — reference
  surface, always available. (`data/parallax/` is retired — stated.)
- Aurora path: JSON under `games/<game>/data/editor/effects/` → `tools/effects_gen.py` →
  `.emp` **calling the same constructors**. Swept caveats, all binding:
  - This generator shape has NO precedent in the tree (every existing generator emits
    data literals/embed). **P5 opens with a spike** proving nested constructor-call
    emission; the stated fallback if the spike fails: the generator emits data literals
    and a comptime verifier module re-derives every scene ensure over the emitted records
    (second-best; keeps sigil the sole rulebook at the cost of one derived checker).
  - The generator emits a FIXED generator-owned `use` preamble, checked against the
    helper-closure collision gate — the free-name trap bit this DSL twice, once silently.
  - Error surface policy (stated, deliberate): P5 ships RAW sigil ensure text as the
    Aurora-user error surface; message wrapping is the Aurora lab phase's problem.
  - `"schema": 1` from day one; the generator REFUSES `schema != 1`; migration machinery
    is explicitly out of scope until the Aurora lab phase (Aurora has no migration
    precedent — deferral is to a gap, so don't imply a compat story exists).
  - Computed-handler refs in JSON are registry indices (runtime-resolved; §2) — never
    symbol strings folded into comptime images.
- Deform `points[256]`/bulk data: `.bin` + `embed()` (the inject_editor_bg precedent).
- Golden/drift: generator output committed + drift-gated (regenerate + verify pattern).
  TS-simulator fixtures deferred (header divergence note).
- Live preview: deferred to Aurora lab (Aether, symbol-resolved, loopback); interim loop
  is save→build→reload_rom.

## 8. Verification

### 8.1 Migration gate
Migrating existing configs to scene constructors (no new capabilities) must produce
**image-identical ROMs across all four shapes** — s4.bin, s4.debug.bin, demo.bin,
demo.debug.bin — after the routine repin ritual, verified with `--freeze NAME --ab REF`
(**never `--check`** — recorded lesson). Localization: each migrated fixture ALSO gets a
**word-equivalence proof** against its hand-authored predecessor (the in-tree
"COMPOSITION EQUIVALENCE PROOF" pattern at ojz_effects.emp:443-456) so a mismatch names
the fixture, not just a global crc. `OJZ_TwoChannel` is the named acceptance case.
**Lifetime (swept):** the gate is not a one-time P1 tick — a minimal capability-off
fixture scene stays in the sonic4 test lane permanently, word-equality-pinned, as the
standing witness that the zero-capability lowering path still emits legacy bytes after
P2/P3 interleave their conditionals.

### 8.2 Build-time gates
- **Demo witness**: demo.bin span-absence AND **whole-image comparison across each parcel
  landing** (spans alone can be satisfied by an inlined leak with no boundary symbol —
  recorded lesson; the image delta is the backstop).
- **Span gates scoped by specialization depth** (swept): module-level = manifest absence
  (SOUND_DRIVER_ENABLED shape); path-level = REQUIRES the §3.3 bracketing labels (the
  flat .lst drops `$`-mangled locals — raster_source_gate had to hand-roll a resolver);
  data-level = record-size symbols. Expectations derived from the capability mask, never
  copied (point implementers at effects_gates.py's `derive_arms` pattern).
- **Poisons**: every budget axis, the tiling/curve/attachment ensures, and the
  capability-mask ensure each get a poison fixture — wired under
  `games/sonic4/test/poison/` as `emp_expect_fail` CASES rows with red-first sentinel
  discipline (the one anti-"built carefully, run by nothing" harness; EFX-9 is the
  postmortem). **Two-fixture differential form required** for span/budget gates (a single
  poison can pass on layout accident — raster_source_gate's own rule).
- Rebase structural check per §6.

### 8.3 Runtime verification (oracle-next; oracle = absolute-measure reference)
Named instruments per new runtime claim (swept — "motion-verified" is scheduling, not
method):
- **Curve smoothness:** after `Parallax_Update` on a pinned camera state, read the HScroll
  buffer RAM and compare every line word in the curve span against the comptime-expected
  ramp (derived, not copied); repeat across a camera sweep (moving-camera requirement).
- **Priority plane-B FG layers:** `read_vram` the layer's nametable words asserting
  priority bits + pinned-camera capture during motion for the "in front" reading.
- **Valve (if built):** memory-read the deform/BgAnim phase accumulators across a
  lag-triggered defer→resume; assert exact-phase resume (no catch-up delta).
- **Vscroll splits:** existing raster gate machinery (arm words + memory_hash; VSRAM N+1
  model; emulator-disagreement caveat carried).
- Standing constraints: replay net is pixel-blind; screenshots non-deterministic; CRAM
  frame-latched (arm words/memory_hash, never CRAM reads); press-wedge avoidance (hold +
  resume + wait_for_break); every timing figure ships with wall-clock uptime.

### 8.4 Measurement program
New NEEDS-MEASUREMENT rows this design creates: engine baselines (idle/max-diagonal),
per-frame HInt total (4b), walker fitted-model parameters, computed-handler pins,
max-contiguous-DMA-stall. Each names oracle-next profiler methodology; none block P1.

### 8.5 Trap ledger carry-forward
Everything from r1 §8.4 PLUS (swept additions): Parcel W fixed-10-byte entry copies
(§4.1); extern()-poisons-comptime for handler refs (§2/§7); the `Label = 0`
vacuous-attachment idiom (§3.1); refreeze `--check` is not the goldens (§8.1); warning
tallies are untracked — never gate on a warning (§6/§8.2); registry-emission exclusivity
(§3.2). Implementation plan enumerates per-parcel which traps it touches.

## 9. Non-goals (explicit)

**Owner revisit notes (2026-08-17) — deferred effects we KNOW can be done, in plain
terms, with caveats:**
- **Sprites reflecting/cutting off at a waterline** (Castlevania Bloodlines dual-SAT
  trick): doable on this hardware, visually striking for water scenes. Caveats: blocked on
  VRAM headroom + SAT-binning work (visual-techniques backlog §20), timing-critical
  mid-frame SAT-base swaps, and it is all-or-nothing per scanline. Nothing in this design
  obstructs it; it would be its own parcel.
- **See-through foreground over full parallax background in the same scanlines**: only
  sprites can do this (plane B is busy being the foreground there). Caveat: sprite-strip
  coverage is SAT-budgeted; dense full-width see-through FG is effectively out of reach —
  design content so dense FG bands are opaque.
- **Perspective floor + ripple on one layer**: formally disallowed (curve∧deform), but
  achievable by baking ramp+wave into one custom `points[256]` deform table. Caveat: the
  baked ramp's amplitude is fixed (camera-independent) — fine for water floors, wrong for
  speed-proportional perspective.
- **Plane-A foreground strips**: only if a static plane-A sub-window with its own vertical
  handling is ever carved out, or in acts/regions where plane A is not streamed — both are
  real engine work, not config.

- **Plane-A FG strips** — unbuildable on this engine as-is (plane A = streamed playfield,
  camera-locked vscroll). Preconditions if ever revisited: a reserved static plane-A
  sub-window with its own vertical handling, or restriction to non-streamed regions.
  Tier-1 FG is §2's priority plane-B layers + sprite strips.
- **Tier-2 streaming FG bands** — precondition ledgered (streamer lookahead ≥ max offset).
- **Curve + deform on one layer** — register-file-bounded; revisit only with a measured
  register-allocation design.
- **Windowed world-Y re-glue / >8 declared layers** — needs Step-4a re-derivation.
- **FG per-column VSRAM** — reserved fields stay; nothing demands it.
- **Variable-length HScroll DMA** — the two fixed static entries stay the model; the
  deleted computed-range infra is not rebuilt (was an R10 audit gap — now explicit).
- **Effect backlog classification** (was implicit): mirage/vortex/banking = deform tables
  or computed handlers (in-vocabulary, content work); water_surface = anchors + palette
  regions (in-vocabulary); earthquake/screen-shake = camera-offset mechanism, OUTSIDE the
  scene model (camera system's, as S2/S3K do it).
- **Corridor authoring machinery** — mega-act program's (§6).
- **Debug-register tricks, interlace, border opening** — catalogue-only.
- **Sprite multiplexing / dual-SAT swap service** — backlog (VRAM + SAT-binning blocked).
- **Window-plane masking service** — quirks unverified; needs oracle/primary-source check.
- **Aurora UI, live preview, live cost meter, TS-simulator fixtures, JSON migration** —
  Aurora lab phase.
- **Effects-tail Parts A/B revival** — condition-gated (§4.2), not scheduled.

## 10. Implementation phasing (input to writing-plans)

- **P1 — Scene model + registry + lowering + migration.** scene_dsl constructors (enum
  attachments), registry + capability fold + Game-const spike (fallback ruled), lowering
  to existing records, ALL existing configs/effects migrated per §3.1 scope, map.toml
  symbol audit, poison_sentinel reachability re-check, §8.1 gates green (image-identity
  ×4 shapes + per-fixture word proofs + standing capability-off witness). One atomic
  landing cluster.
- **P2 — Specialization + budget.** CAP-mask gating, bracketing-label convention, demo
  witness + depth-scoped span gates, ledger consts + formatter spike, budget model rows +
  reservations + transition-frame check, all §8.2 poisons (two-fixture form).
- **P3 — Walker mechanisms.** World-Y re-glue (copy-all, ≤8), curves (hoist divs +
  specialized loop variant), per-layer deform refs (extended record + Parcel-W copy
  hardening + walker addressing rewrite + typed-data spike), per-line forcer derivation
  feeding both twins, vscroll-split lowering, left-column mask emission. Each mechanism
  lands with its §8.3 instrument.
- **P4 — BgAnim binding; valve only if ledgers demand it.**
- **P5 — effects_gen.py**: constructor-call spike (fallback ruled), fixed use-preamble +
  collision gate, schema v1 + refusal, one migrated reference scene as fixture, drift
  gate. Aurora handoff point.

Each parcel: atomic landing, gates + poisons in the same cluster, trap-ledger enumeration
in the plan, master never half-migrated.
