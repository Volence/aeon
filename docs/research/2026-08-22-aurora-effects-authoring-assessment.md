# Aurora Effects-Authoring Assessment — design input for the Parcel D / OJZ BG showcase arc

**Date:** 2026-08-22 · **Status:** ASSESSMENT (pre-design; no implementation, no plan) ·
**Update 2026-08-22:** §(f)'s six questions are now ADJUDICATED under owner delegation — see the
provenance note there; the rulings are design inputs, overturnable at the design review.
**Aeon surveyed at:** `77cbf7c0` (master, via worktree branch `research/aurora-effects-assessment`)
**Aurora surveyed at:** `4cffe45619192285290aa6d8be33512543ef767c` (branch `master`, **tree clean** —
`git status --short` empty at survey time; the 2026-08-21 landed line `5b58f68..4cffe45` is fully
committed, nothing in flight)

Every claim is tagged **OBSERVED** (file:line, read on this tree) or **INFERRED** (reasoned from
observed facts). Aurora was read-only throughout.

---

## ERRATUM 1 — the sidecar write condition (verified 2026-08-22, aurora `e731214`)

Raised by the aurora-86 overseer's firsthand-verification pass and **re-verified independently by
the aeon overseer** before acceptance (peer claims are checked, not trusted). This does NOT
overturn ruling Q2 — the `section_N.meta.json` sidecar is still the right venue for the per-section
`sceneRef` — but the assessment's citation of `save.ts:112-115` summarises the mechanism as "scalar
refs with explicit-null semantics", and a contract needs the actual write condition.

**The two-ref set is hardcoded in FOUR places** (all OBSERVED at aurora `e731214`):

1. `src/core/formats/section-meta.ts:21` — `serializeSectionMeta` returns `null` when BOTH refs are
   null, so the all-default case writes no sidecar at all.
2. `section-meta.ts:22` — the emitted body is a two-field literal.
3. `section-meta.ts:29-30` — `parseSectionMeta` enumerates the two fields explicitly; **unknown keys
   are silently dropped** ("missing or non-string fields read as null").
4. `save.ts:118-126` — when the serializer returns null but a sidecar exists, save overwrites it
   with a hardcoded all-nulls body, an exists-probe-gated path whose purpose is stopping a cleared
   ref from resurrecting on the next load.

**The consequence, and it is load-bearing:** parse drops unknown keys and serialize re-emits only
what it enumerates, so a `sceneRef` written by anything that is not a sceneRef-aware Aurora — an
aeon generator, a hand edit, version skew in either direction — is **silently erased on the next
Aurora save round-trip**. The cleared-overwrite literal has the same shape and would wipe a third
ref even once Aurora knows about it.

**What this obligates in the contract docs:** (a) the aeon consumer field list documents the write
CONDITION and the parse→serialize round-trip requirement, not merely field presence and type;
(b) the empyrean schema states that the all-refs-null case may legitimately leave NO sidecar on
disk, so consumers treat a missing sidecar as all-null and never as an error; (c) both halves name
the unknown-key-drop as the round-trip hazard so Aurora's writer-side golden can pin against it;
(d) adding `sceneRef` requires coordinated edits at all four sites above.

### Addendum (same night, aurora-86's second pass — CONFIRMED independently at `e731214`)

**The drop is not only for UNKNOWN keys.** The guard is
`typeof raw?.bgLayoutRef === 'string' ? raw.bgLayoutRef : null`, so a **known, schema-blessed key
carrying a non-string value also reads as null**, with no error path and no warning — a malformed
ref is indistinguishable from an absent one. The realistic form of the mistake is `sceneRef: 3`, a
numeric scene index, which a generator or a hand edit would very naturally emit; a fully
sceneRef-aware Aurora reads it as null and erases it on the next save. The symptom presented to a
user is "the assignment didn't stick".

> **RULING (assistant-authored under the owner's overnight delegation, 2026-08-22 — reasoning
> recorded so it is cheap to overturn at the design review):** the section-meta ref type is
> **normatively a string id** — `sceneRef: string | null`, never a numeric index — matching
> `bgLayoutRef`/`paletteRef` (`section-meta.ts:12-13`, `S4Project.bgLibrary` ids). A numeric index
> is FORBIDDEN by the schema *because* the parser's failure mode for it is a silent null rather
> than a loud reject. The aeon consumer field list states that failure mode in those words, so the
> integer-index shape is not later adopted as an optimisation.

Two further facts from the same file, both contract-relevant:

- **`parseSectionMeta:27` does a bare `JSON.parse`** — a malformed sidecar THROWS rather than
  degrading to defaults. Ownership of that error is assigned consumer-side: generators write
  sidecars **atomically** (temp file then rename) so a partially-written sidecar is never
  observable. (Offered to aurora-86 as a shared obligation instead, if they prefer Aurora also
  degrade gracefully — their side of that fence, their call.)
- **The site count is SIX, not four.** Beyond the four executable sites: the header comment's prose
  enumeration (`:5-9`) and the `SectionMeta` TS interface (`:11-14`), the latter being what makes
  the compiler agree a third ref exists. All six go stale when `sceneRef` lands.

---

## ERRATUM 2 — the meta sidecar is silently destructive TODAY (verified 2026-08-22, aurora `e731214`)

Raised by aurora-86 when they took the atomic-write question to their loader; **independently
verified by the aeon overseer** at the same SHA before acceptance. This is a **live data-loss
defect in Aurora**, not a hardening nicety, and it changes this arc's sequencing.

**The mechanism** (all OBSERVED at aurora `e731214`):

1. `src/core/project/aeon/load.ts:322-329` — the meta sidecar's load path has a **bare, silent
   catch**: `catch { // no meta sidecar — defaults from createSection stand }`. A malformed sidecar
   is therefore indistinguishable from an absent one; both yield default (null) refs.
2. Save then completes the destruction: refs are null → `serializeSectionMeta` returns null → the
   exists-probe at `save.ts:123` finds the file → it is **overwritten with
   `{bgLayoutRef: null, paletteRef: null}`**. A corrupt sidecar is silently consumed and replaced
   with a well-formed empty one. Every assignment in it is gone, with no notice anywhere.

**The repo already has the correct idiom seven lines above.** The rings loader (`load.ts:311-318`)
routes its catch through `markUnreadable`, which probes `exists` to separate present-but-unreadable
from simply-absent (`:173-175` — exactly the distinction the meta catch collapses), records the
suffix on `section.unreadable`, and emits "…exists but could not be read… Aurora is showing empty
data for it and will NOT overwrite the file — fix it by hand and reopen" (`:178-181`). That promise
is enforced at save by `understood()` (`save.ts:78`), which gates `tiles.bin` (`:81`),
`objects.json` (`:99`) and `rings.json` (`:106`). **The meta sidecar is gated by neither.** The
save-path comment at `save.ts:74-77` states the rule in its own words — "a load-time parse failure
must not lead to destroying data" — and names the exact scenarios (a truncated hand-edit, a
merge-conflict marker). Three of four section artifacts honour it; the fourth is the one this arc
wants to hang `sceneRef` on.

**RULING — the atomic-write obligation becomes SHARED, not consumer-side-only** (assistant-authored
under owner delegation; aurora-86 concurs and is dispatching their half). Atomic temp-file-then-
rename stops *partial* writes and is still required of generators. It does nothing about the hand
edits this contract explicitly blesses as a legitimate writer, a merge-conflict marker, or any
other unreadable-for-any-reason case — each of which hits the silent-destroy path above. Aurora's
half: route the meta catch through `markUnreadable` as rings does, and gate the meta write
(**including the cleared-overwrite literal**) behind `understood('meta.json')`. Recorded emphatically
because it is the subtle part: **"degrade gracefully" must NOT mean "treat as all-null"** — all-null
is precisely the state that triggers the destructive overwrite, so quiet-and-lossy would be worse
than the status quo. Loud and non-destructive.

**Consequence for the aeon consumer field list, stated because the opposite expectation is the
natural one:** once Aurora refuses to overwrite an unreadable sidecar, a generator that writes a
sidecar Aurora cannot parse will find its file **preserved rather than repaired**, and the section
shows empty refs until a human fixes it. That is intended behaviour, but it means a generator bug
is **sticky rather than self-healing**. Say so plainly in the field list.

**SEQUENCING CONSEQUENCE (mine, delegated):** wave 1 must not land `sceneRef` into the sidecar until
Aurora's meta-gating fix is on their master. Until then the third ref inherits a known silent-
destroy path, and the arc's first authored act would be the thing that discovers it. The fix SHA is
therefore a **named precondition** on wave 1's sceneRef work — aurora-86 sends it when reviewed and
landed; the aeon and empyrean contract docs pin it alongside the other anchors.

### The mirror question, answered on OUR side (aeon `5be97277`, aeon overseer, firsthand)

Aurora's defect prompts the obvious reciprocal audit: do aeon's editor-data consumers collapse
*unreadable* into *absent* the same way? **They do not — aeon's posture is already the correct one**,
and the contract should state the asymmetry rather than leave it assumed.

- `tools/inject_editor_bg.py:58-61` — `json.load` with **no try/except**, then `data['layout']`,
  `data['tiles']` by direct subscript. A malformed or truncated override JSON raises and the build
  STOPS. Loud, non-destructive, and it never writes anything back over the input.
- The broad `except Exception` handlers in `tools/ojz_block_gen.py` (`:222`, `:248`, `:288`, `:308`)
  are confined to the **content-addressed cache/memo layer**, where degrading to a miss means
  recompute, never data loss — a different defect class from Aurora's, and correct as written.
- **The atomic-write idiom the generator obligation calls for already exists in-tree**:
  `tools/ojz_block_gen.py:201-206` (`_atomic_write` — pid-suffixed temp then `os.replace`). New
  generators reuse it rather than reinventing it; name it in the consumer field list so the
  obligation points at an implementation instead of a principle.

Net: the contract's error-handling section is **normative for both halves** rather than a courtesy
note aimed at one.

**AMENDED same night** (aurora-86; their meta fix landed as aurora `a88db05`, and their enumeration
found more). The asymmetry is narrower than first written — state it as: **safe on the aeon side;
FIXED for the sidecar on Aurora; STILL OPEN for collision planes.** Do not freeze a settled-Aurora
claim.

- **Their meta fix is landed and merged-tree-verified** (`a88db05`): `markUnreadable` on the load
  catch with the same argument shape as the rings call, and BOTH meta write branches — content and
  cleared-overwrite — behind `understood('meta.json')`. `tsc --noEmit` clean; `vitest` 3856 passed
  / 3 skipped across 323 files, delta exactly the 7 new tests; red-first proof shows the
  destruction as **bytes on disk**, with three planted mutations including one that breaks only
  the save half.
- **The legacy-atlas guard resolved as NEITHER predicted outcome.** It is at `save.ts:270-279` and
  reaches the right result **through data flow, not through `unreadable`/`understood()`**:
  `legacyAtlasMerged` is set only inside the success block at `load.ts:494-506`, so a malformed
  chunks.json leaves the library empty, migration is skipped, and the flag stays false. Therefore
  the contract's claim must be **outcome-uniform per artifact, NOT mechanism-uniform** — four
  sites use the explicit guard, one gets there another way. The mechanism claim would be
  load-bearing in the wrong direction.
- **A live defect one artifact over, still open:** `.collattr.bin`/`.collattrb.bin`
  (`load.ts:276-287`) parse inside bare catches that substitute a strip-derived baseline, and
  `save.ts:89-96` gates the writes only on `if (section.collisionEdit)` — which the fallback makes
  always truthy. An unreadable authored collision plane is silently overwritten with the baked
  baseline. **Mechanism correction from their own second pass:** `parseCollAttr`
  (`s4-collattr.ts:6-11`) is `n = data.length >> 1` plus a loop with no length validation and no
  throw, so a **truncated** file never enters the catch at all — it parses short, and
  `serializeCollAttr` writes back `words.length * 2` bytes, persisting the truncation **at the
  short length** (odd-length files silently drop the trailing byte). It is parse-level loss that
  **no `understood()` gate can see**, which is why it needs its own answer. Their fix is on
  `fix/collattr-unreadable-guard`; SHA to follow. Not this arc's blocker — `sceneRef` rides the
  sidecar, not the collision planes — but the error-handling section must not imply it is closed.

---

## (a) Inventory — the three effects vocabularies and their data paths to the ROM

### A1. Scenes (multi-band parallax: layers, deform, curves, vsplit, anchors)

**Authored today:** by hand, in `.emp`, in `games/sonic4/data/effects/ojz_scenes.emp` — the twenty
shipped parallax configurations re-authored in the scene model (OBSERVED `ojz_scenes.emp:1-12`;
the old `games/sonic4/data/parallax/configs.emp` is DELETED, `ojz_scenes.emp:8`). Scenes are values
built from constructors in `engine/level/scene_dsl.emp`:

- `layer(world_y, fa, fb, dsa, dsb, phase, enabled, deform, curve, vsplit)` — OBSERVED
  `engine/level/scene_dsl.emp:521-635`; heavy `ensure` guard load (own-table sampling, curve∧deform
  refusal, vsplit 0..511, world-Y act span).
- `scene(layers, count, v_factor, v_center, v_offset, deform_fg/bg, v_deform, anchor,
  left_column_mask, precision, transition, layer_mask_raw, v_deform_shift_raw)` — OBSERVED
  `scene_dsl.emp:1020-1078` (pad guard, mask bridge, anchor channel < 4).
- Factors and deform-table generators in `engine/level/parallax_dsl.emp` — packed shift-add
  `FACTOR_*` encoding (OBSERVED `parallax_dsl.emp:21-40`), `deform_sine` / `deform_zero` /
  `deform_triangle` / `v_column_perspective` / `v_column_floor` each emitting 256 signed bytes
  (OBSERVED `parallax_dsl.emp:51-99`). Pure integer/comptime math — `as.sin`/`as.int` reproduce
  asl float routines bit-for-bit (comment at `parallax_dsl.emp:44-46`).

**Data path to ROM:** `ojz_scenes.emp` (pure comptime, zero bytes) → the SOLE emission module
`games/sonic4/data/effects/scene_registry.emp` ("THE ONLY module that lowers scenes to ROM
records", OBSERVED `scene_registry.emp:1-3`), which lowers each scene to a
`parallax_config` header + `band_record[]` via per-arity `lowerN` folds (OBSERVED
`scene_registry.emp:80-99`) → sections reference the lowered records: the act default at
`games/sonic4/data/levels/ojz/act1/act_descriptor.emp:130`
(`act_parallax_config: ParallaxConfig_OJZ_Default`), per-section via `Sec.sec_parallax_config`
(default = act fallback, OBSERVED `act_descriptor.emp:172`) or through a preset's `ep_parallax`
(first live binding noted at `games/sonic4/data/effects/ojz_effects.emp:55-60`) → walked at runtime
by `engine/level/parallax.emp` (2,359 lines).

**Budget/gate machinery a new authoring path must respect (OBSERVED):**

- `scene_budget_enforce(scenes)` — comptime, runs on every build over the whole registry:
  `pub const SceneRegistry_BudgetChecked = scene_budget_enforce(SCENES)`
  (`scene_registry.emp:405`); axes 1 (main-loop cycles), 2 (DMA bytes), 3 (VBlank cycles),
  5 (per-line sprites — the BINDING ceiling) with fitted cost models transcribed from
  `tools/effects_budget_model.toml` (OBSERVED `scene_dsl.emp:2333-2360`, `:1969-1973`).
- `tools/effects_budget_check.py` — gates the toml's code-derived rows against the `.emp`
  constants that are their authority (OBSERVED header, `effects_budget_check.py:1-14`).
- `tools/effects_gates.py` — the aggregated emulator-backed gate lane (scene determinism via
  `ab_runner --selfcheck`, program-shape asserts with DERIVED arm words, `raster_off_gate`,
  `raster_source_gate`, `vsplit_landing_gate`, `palette_variant_gate`), with a deliberate
  poison-wedge self-test (`EFFECTS_GATES_POISON_WEDGE`, OBSERVED `effects_gates.py:1-45,310-315`).
  Cannot live in build.sh (each gate boots a headless emulator); it is the pre-merge ritual for
  anything touching `engine/effects/*`, `engine/level/bg_anim.emp`, `engine/system/buffers.emp`
  (aeon `CLAUDE.md`, effects gate ritual, owner ruling 2026-08-18).
- Reachability trap any generated module inherits: an unreached `.emp` module gets ZERO body
  elaboration — `ensure(1 == 0)` builds green (OBSERVED `scene_registry.emp:28-34`). A generated
  scenes module must be reached (whole-path `use` edge + `map.toml` order entry) or its guards are
  vacuous.

### A2. Raster / palette effects (sparse fires, patchable channels, variants, cycling, presets)

**Authored today:** by hand, in `.emp`, in `games/sonic4/data/effects/ojz_effects.emp` (fixtures +
presets; OBSERVED header `ojz_effects.emp:1-9`) through the vocabulary in
`engine/effects/raster_dsl.emp` / `palette_dsl.emp` (ambient via sigil's COMPTIME_HELPERS). The
standing authoring reference is `docs/EFFECTS_AUTHORING.md` (1,063 lines — descriptor set,
presets/`compose`, `patchable` world-anchor channels, wire format, guard table). Representative
surface (all OBSERVED in `EFFECTS_AUTHORING.md` with their raster_dsl.emp citations):
`fire(line, ops)`, `stream_cram/stream_pal_region/stream_vsram`, `reg_set/reg_sh_on`,
`region_boundary`, presets `fx_sh_below/fx_vscroll_split/fx_tint_band`, `compose`,
`patchable(fires, ch, lo, hi, offscreen_ship)`, `variant(shift/bias)`, `cycle_channel`.

**Data path to ROM:** `pub data X: [u16; raster_words(P)] = raster_program(P)` (or
`patched_program`) in game data modules → bound to sections three ways (OBSERVED
`act_descriptor.emp:159-194`): `ojz_sec(raster:)` → `Sec.sec_raster_table`; `ojz_sec(cycle:)` →
`Sec.sec_pal_cycle`; `ojz_sec(effects:)` → `Sec.sec_effects`, the total-binding `EffectsPreset`
(e.g. `OJZ_Preset_Sec0..Sec3/Plain`, OBSERVED `ojz_effects.emp:693-699`) → consumed on boundary
crossings (`Raster_InstallSection` / `Effects_InstallPreset`), patched templates re-recorded every
VBlank by `Raster_BuildSchedule`.

**Hard ceilings an authoring UI must encode (OBSERVED in `docs/EFFECTS_AUTHORING.md`):** 64-word
program buffer (≈6-8 colour events per program); ≤4 ops / ≤2 stream ops / ≤3 stream words per
fire; density guard (measured cycle model, band-edge-to-band-edge for patchable); strictly
ascending disjoint fire intervals (overlap parks the schedule — silent kill); `RASTER_MAX_PATCH`
= 4 channels with a shared 221-line band budget; `PAL_MAX_VARIANTS` = 2 slots; palette line 0
forbidden; sparse and dense tiers cannot mix in one program.

### A3. BgAnim tile bands (the "animated third parallax")

**Authored today: NOBODY authors it.** The engine and bake path exist end-to-end, but the current
editor source has no `anims` key — OBSERVED: `games/sonic4/data/editor_bg_override.json` contains
only `layout` + `tiles` (448 tiles), so `tools/inject_editor_bg.py` emits the disabled stub and
`games/sonic4/data/generated/ojz/act1/bg_anim.emp` is `band_count = 0`.

**Data path (when authored):** `editor_bg_override.json` `anims: [{cols, rows, pattern_px,
driver, rate_shift, phases[8][tiles]}]` → `tools/inject_editor_bg.py:69-147` emits
`bg_anim_banks.bin` (8 pre-shifted 1px banks per band, concatenated) + generated
`bg_anim.emp` (`BgAnim_Table` count + per-band 44-byte records + `embed()` of the banks) →
natively placed section `ojz_bg_anim` → runtime `BgAnim_Update`
(`engine/level/bg_anim.emp:122-217`): driver = Camera_X / Camera_Y / Logic_Tick, fine phase picks
a bank, coarse phase rotates whole columns via two wrapped deferrable DMAs.

**Contracts (OBSERVED):** the 44-byte record is a LOCKSTEP twin (`bg_anim.emp:61-76` `struct
bganim_band` + ensure 44 vs `inject_editor_bg.py:14-17`); `BGANIM_MAX_BANDS = 4` held by THREE
deliberate authorities (constants.emp, bg_anim.emp module-local, the emitter) drift-gated by
`tools/test_bg_emit.py::TestBgAnimBandCeiling` (`inject_editor_bg.py:29-53`); emitter invariants
`pattern_px == cols*8`, power-of-two column bytes, bands pack contiguously from slot 0
(`inject_editor_bg.py:89-93`). **Caveat to carry into planning:** the animated arm is
"FORMAT-FAITHFUL BUT NOT BYTE-PROVEN — no act in the tree authors BG animation, so the six-target
gate exercises only the stub; the first animated act proves this arm" (OBSERVED
`inject_editor_bg.py:121-124`).

**Adjacent editor data (OBSERVED):** `games/sonic4/data/editor/ojz_bglib.json` is a BG *library
index* — 16 `{id, name}` entries; Aurora reads/writes it (`aurora
src/core/formats/bg-library.ts:16` builds `<dataRoot>editor/<zone>_bglib.json`; the loader
accumulates entries at `src/core/project/aeon/load.ts:385-399`). `tools/png_to_bg_override.py` is
the PNG→override MVP feeding the same file `inject_editor_bg.py` consumes.

### A4. The parallax config reference today — a dangling string

OBSERVED: `project.json:22` still declares `"parallax":
"games/sonic4/data/parallax/ojz_default.asm"`. That directory no longer exists (`data/parallax/`
deleted with configs.emp). Aurora carries the value opaquely — `actConfig.parallax` →
`parallaxRef` (`aurora src/core/project/aeon/load.ts:370`, model at `src/core/model/s4-types.ts:121`)
— and nothing on either side reads through it. INFERRED: the field is a fossil of the pre-scene
era and is dead weight until the new contract re-points it (or deletes it).

### A5. The banked design context (what was already ruled)

- **The 2026-08-11 effects suite design** — `docs/superpowers/2026-08-11-effects-suite-design.md`
  (committed `3da87fe6`). §7 sketches the **Aurora Effects Lab** (parallax band editor, raster
  track on a scanline ruler, variant designer, cycle editor), a TS scanline simulator with golden
  fixtures, Map-mode preset assignment, and a Verify button; §8 fixes the data flow: *"Aurora
  preset JSON + assignments → tools/effects_gen.py → generated .emp → sigil → ROM"* with a shared
  machine-readable budget model enforced as a hard build gate. Phases 4-5 (simulator, Lab,
  effects_gen.py, Map assignment) are exactly this arc's territory; phases 1-3 shipped as the
  raster/palette/preset vocabulary above.
- **The scanline-services design (2026-08-17)** — `docs/superpowers/specs/2026-08-17-scanline-services-design.md`
  §7 "Authoring pipeline (Aurora contract)" REFINES the same ruling with binding caveats
  (OBSERVED `:355-383`): JSON under `games/<game>/data/editor/effects/` → `tools/effects_gen.py`
  → `.emp` **calling the same constructors**; P5 opens with a spike (nested constructor-call
  emission has NO precedent in the tree; ruled fallback = data literals + a comptime verifier
  module); fixed generator-owned `use` preamble checked by the helper-closure gate; RAW sigil
  ensure text as the v1 error surface; `"schema": 1` refused-if-not; bulk data as `.bin` +
  `embed()` (the inject_editor_bg precedent); generator output committed + drift-gated; live
  preview deferred to the Aurora lab phase, interim loop = save→build→reload_rom. Per its phase
  table, **P4 = BgAnim binding into the scene model, P5 = effects_gen.py** (`:506-507`) — booked,
  **not built**: OBSERVED `tools/effects_gen.py` and `games/sonic4/data/editor/effects/` do not
  exist at `77cbf7c0`.
- **Format-boundary RULING (2026-08-20)** — `docs/DEFERRED_WORK.md:112-136` (sprite-export
  consumer booking): *"Aurora emits neutral data, aeon generates the code"* — Aurora emits neither
  `.asm` nor `.emp`; neutral json+bin is the contract; the `.emp` generation is an aeon bake step;
  and a contract only exists once the consumer's exact field list is enumerated and handed over
  for a writer-side golden.
- **Banked adjacent parcel:** the effects-tail r3.1 design (overlapping patchable bands) is banked
  with its revival condition literally this arc — *"a real program that needs overlapping
  patchable bands — the expected one is the Parcel D OJZ showcase (Aurora-authored multi-band)"*
  (OBSERVED `docs/DEFERRED_WORK.md:5461-5468`).
- **ENGINE_ARCHITECTURE anchors:** §4.6 (shipped parallax, `:2393`), §7 Visual Effects System
  (`:3575`, with §7.12 preset total-binding `:3994`, §7.13 patchable wire format `:4053`, §7.14
  palette bands `:4217`).
- **DEFERRED_WORK Aurora bookings found:** the sprite-export consumer (`:112-136`, above) and the
  ARCH §4.12 ladder consumption note (`:636`). No existing booking for effects authoring itself —
  this assessment precedes it.

### A6. Adjacent overlap: the ComfyUI art pipeline

OBSERVED: spec at `docs/superpowers/specs/2026-07-12-comfyui-art-pipeline-design.md` (M1 = BG
pipeline end-to-end with a human preview gate); its M1 output shipped to master
(`dd93a840`/`2d8b0670`, the ChatGPT Deep Forest OJZ BG); the working branch no longer exists in
this repo. Its ingest tool survives as `tools/png_to_bg_override.py` writing the SAME
`editor_bg_override.json` that BgAnim authoring would extend. **Synergy, not conflict**
(INFERRED): AI-generated BG art arrives through the same neutral file the effects view's BgAnim
band authoring reads/writes; no design coupling needed beyond not double-owning that file's schema.

---

## (b) Aurora architecture map (what a new view/worker rides on)

Surveyed at `4cffe456...` (master, clean). Required-reading set honored: `docs/OVERSEER.md`,
`docs/ROADMAP.md` §2.5/§2.6/§5.1/§5.2, `docs/reviews/2026-08-21-s1-viewport-lenses-audit.md`.

- **Stack (OBSERVED `package.json`):** Electron + electron-vite, React 19, zustand, vitest; MCP
  SDK + express (the agent/Aether surface). `src/core` = pure-TS domain (node-tested),
  `src/renderer` = React app, `src/main`/`preload` = Electron shells.
- **The view system is the facet registry** (OBSERVED `src/renderer/workspace/facet-registry.ts:1-60`):
  modules keyed by `(engine, facetId)`, registered in `register-facets.ts` for `'aeon'` and
  `'s1'`; a `FacetModule` supplies `Canvas / ToolDock / ToolOptions / RightPanel / BottomExtra /
  StatusBar` slots plus a `mapOverlays` flag; no fallback — an unregistered pair renders null
  loudly. Both engines render through one `LevelWorkspace` (ROADMAP §2.6 A). **Adding an effects
  view = one more facet module per engine, plus overlay lenses on the shared viewport** (INFERRED
  from the registry shape).
- **The overlay/lens pattern (the 2026-08-21 line — the surfaces this arc rides):**
  `viewStore.overlays` + `ViewMenu` (OBSERVED `src/renderer/state/viewStore.ts:37-133`,
  `src/renderer/shell/ViewMenu.tsx`); `ClassicLevelViewport.tsx` + `classic-overlays.ts` composite
  overlay passes on canvas 2D (`getContext('2d')`, OBSERVED `ClassicLevelViewport.tsx:496,629`).
  The `5b58f68..4cffe45` parcels landed: a **shared rAF play-clock** driving animated level art
  and object previews **overlay-only** (document untouched), and a **per-pixel priority-occlusion
  pass** (map wins iff hi tile ∧ opaque ∧ low sprite piece) at 0.18 ms avg, harness 30/30
  (OBSERVED git log `5b58f68..4cffe45`; ROADMAP §5.1 item 7). The lenses audit
  (`docs/reviews/2026-08-21-s1-viewport-lenses-audit.md`) is the measurement-first template for
  such a lens. **No Web Workers found** in `src/renderer`/`src/core` (grep for `new Worker`) —
  per-frame overlay work runs on the renderer thread inside measured sub-millisecond budgets
  (OBSERVED harness numbers 0.18-0.49 ms). "View/worker" in practice = facet + play-clock overlay
  passes, not thread workers.
- **The aeon project adapter (OBSERVED `src/core/project/aeon/`):** `load.ts` reads
  `project.json` (`s4-config.ts` — zones/acts, `dataPath` per-section tiles/objects/rings/
  collision, `bgLayout`/`bgTiles`, the BG library, `parallax` carried opaquely); `save.ts` writes
  `.tiles.bin` + `.meta.json` sidecars and the editor-owned art blobs under the dest-field
  ownership invariant (field absent → Aurora owns path+pointer; present → repo owns, OBSERVED
  `s4-config.ts:1-16`) — the 2026-08-18 `feature/editor-dest-fields` ruling.
  **Load-bearing caveat (named, not assumed away):** `AeonProjectAdapter` is still a ROUTING
  MARKER — `open()` returns a capability-marker handle and the renderer still runs the legacy
  `useProject.loadFromPath`; the real core-callable aeon loader is deferred (OBSERVED ROADMAP §2.5
  "Deferrals", restated in the §5.2 incoming-arc note). If the effects view needs deeper
  aeon-project understanding than today's facets use (e.g. scene-registry introspection, budget
  ledgers), that is NEW adapter work and sits in the gap list below.
- **Live-preview plumbing already exists:** P2 (the playtest loop) is DONE 2026-08-19 — Aether
  outbound client, `push_palette` (palette→CRAM live), `warp`, `build_and_run`, with agent-surface
  parity (ROADMAP §5.1 item 1, §2.7). P5 "Raster mode + live preview (design #8 Aurora half)"
  is open, engine-gated on aeon (§5.2 phase table).
- **Precedent end-to-end flow (tiles):** UI edit → store command → `save.ts` writes
  `section_N.tiles.bin` + meta into `games/sonic4/data/editor/ojz/act1/` → aeon
  `tools/regenerate-level.sh` bake (staleness-gated by `tools/level_staleness.py`; FAST=1
  auto-re-bakes) → generated strips/blocks → sigil → ROM. The effects view should be the same
  shape with `editor/effects/` JSON and `effects_gen.py` in the bake seat (INFERRED; this is also
  what both standing designs say).
- **Process/lane fact (from the coordinating sessions, recorded in aurora ROADMAP §5.2
  "Incoming arc", agreed 2026-08-22):** Aurora parcels are dispatched and landed by the Aurora
  session **against committed aeon briefs/contracts with SHAs**; cross-tool contract material goes
  to empyrean. Any data contract this arc defines must therefore land as a committed artifact, not
  a transcript.

---

## (c) The gap list — what does not exist today

1. **UI:** No effects authoring or preview surface of any kind in Aurora (the 2026-08-11 design's
   baseline "Aurora: Map/Art/Sprite modes; zero effects authoring/preview" is still true at
   `4cffe456`; nothing under `src/` mentions scenes, rasters, variants or BgAnim bands).
2. **Data contract:** `games/sonic4/data/editor/effects/` does not exist; no schema for scene /
   preset / assignment JSON exists anywhere; `project.json`'s `parallax` field dangles at a
   deleted `.asm` path (A4).
3. **Bake hook:** `tools/effects_gen.py` does not exist (scanline-services P5, booked not built).
   The constructor-call-emission spike it must open with is unproven; the fallback is ruled but
   also unbuilt. No bake step regenerates section→effect bindings — `ojz_sec(raster:/cycle:/
   effects:)` arguments are hand-typed in `act_descriptor.emp`.
4. **BgAnim content + proof:** zero authored bands (`band_count = 0`); the emitter's animated arm
   is format-faithful but byte-unproven (A3); no Aurora UI reads or writes the `anims` key even
   though that half of the neutral contract already exists.
5. **Preview:** Aurora's renderers draw planes flat (canvas 2D, `SectionRenderer.ts`); there is no
   per-line HScroll / VSRAM / vsplit simulation, no palette-variant or cycling preview, no BgAnim
   band playback. The play-clock + overlay-pass machinery to hang these on now exists (b), but
   every effects-specific pass is unwritten. The TS-simulator golden fixtures are explicitly
   deferred to this arc by the scanline design (§5/§7).
6. **Aeon adapter depth:** the routing-marker gap (b) — if the view needs to enumerate scenes,
   read budget ledgers, or resolve scene names to sections, none of that is loadable through the
   current adapter; today's facets only touch tiles/objects/rings/collision/BG blobs.
7. **Budget visibility in-tool:** `scene_budget_enforce` errors surface only as sigil build
   failures (raw ensure text is the RULED v1 surface; wrapping is "the Aurora lab phase's
   problem", scanline design `:373-374`). The post-bake ledger artifact
   (`<game>_scene_budgets.txt` from exported comptime consts) is designed with the symbol-readback
   spike booked in scanline P2 — not yet built, so Aurora has nothing to render a meter from.
8. **Assignment model:** no editor-owned representation of "section N uses preset/scene X" —
   today that fact lives only in hand-authored `.emp` (`act_descriptor.emp` and preset tables in
   `ojz_effects.emp`).

---

## (d) Design options for the authoring surface and data contract

The option space is heavily pre-constrained by three standing rulings (A5): the 2026-08-11 suite
design §8's one-direction data flow, the scanline-services §7 Aurora contract, and the 2026-08-20
neutral-data format boundary. Reported per the brief's compare-then-recommend ask; nothing below
contradicts a ruling silently.

### Option A — Aurora edits the `.emp` directly (structured editing of `ojz_scenes.emp` / `ojz_effects.emp`)

Aurora parses and rewrites the hand-authored scene/preset modules in place.

- **Bake path:** none needed (the `.emp` IS the source) — superficially attractive.
- **Why it loses:** contradicts the 2026-08-20 format-boundary ruling head-on (Aurora emitting
  `.emp` "pushes sigil-language churn across the tool wall"); `.emp` comptime semantics are
  actively hostile to machine round-tripping (call-site name resolution, mandatory glob imports,
  helper-closure collisions, load-bearing emission order in `scene_registry.emp:36-39`); and every
  hand-authored comment/citation in those files (which are dense with load-bearing prose) would be
  churned by a serializer. Gate implications are neutral (sigil still validates) but the authoring
  files stop being human artifacts. **Rejected.**

### Option B — Neutral JSON in the editor tree; an aeon bake step emits `.emp` (the ruled shape)

Aurora authors `games/sonic4/data/editor/effects/*.json` (scene definitions, preset compositions,
BgAnim bands, section assignments) exactly as it authors tiles today; `tools/effects_gen.py`
(new) emits a generated `.emp` module **calling the same scene/preset constructors**, so every
`ensure` and `scene_budget_enforce` still fires on authored content; BgAnim bands ride the
EXISTING `editor_bg_override.json` `anims` contract and `inject_editor_bg.py` unchanged.

- **Bake path:** joins the level re-bake lane (staleness via `tools/level_staleness.py` pattern;
  generated output committed + drift-gated per scanline §7; deform curves / bulk data as `.bin` +
  `embed()`). The generated module must be REACHED (map.toml order entry + use edge) or its guards
  are vacuous (A1's reachability trap) — a gate must pin that.
- **Gate/budget implications:** sigil remains the sole rulebook; `effects_gates.py` stays the
  pre-merge emulator lane untouched; Aurora reads `tools/effects_budget_model.toml` (and later the
  ledger artifact) for an advisory meter, while the hard gate stays in the build — the exact
  two-enforcement-point shape §8 of the 2026-08-11 design specifies.
- **Risk:** the P5 constructor-call-emission spike has no precedent; the ruled fallback (emit data
  literals + a derived comptime verifier) keeps the option alive at the cost of one extra checker
  module.

### Option C — Aurora (or the bake) emits lowered binary records directly (`parallax_config`/`band_record` blobs via `embed()`)

- **Why it loses:** bypasses every scene_dsl/raster_dsl guard — the ensures never evaluate over
  hand-lowered bytes, re-creating the hand-word era the DSLs were built to kill (the `%0001` mask
  bug class, `EFFECTS_AUTHORING.md:43-49`); double-authors the lowering so the TS writer and the
  `.emp` lowering can drift silently; and budget enforcement would have to be reimplemented in
  Python/TS against a model the `.emp` already owns. **Rejected.**

### RECOMMENDATION — Option B, phased, with the contract landing as a committed artifact

Option B is not just the best option; it is the already-ruled architecture (2026-08-11 §8,
scanline-services §7, format boundary 2026-08-20) and it is the same boundary the
tiles/objects/BG pipeline already draws. Concretely:

1. **Phase the surface by contract maturity:** start with **BgAnim bands** (the neutral contract
   and bake step ALREADY EXIST — only Aurora UI + preview + the first authored act are missing,
   and that first act simultaneously discharges the emitter's unproven animated arm); then
   **scene parameter editing + section assignment** (needs the new `editor/effects/` schema +
   `effects_gen.py`, i.e. aeon's P5); then **raster preset composition** (tint bands, vscroll
   splits, patchable channels — the richest UI, and the piece whose overlap ambitions may trigger
   the banked effects-tail revival, an aeon parcel).
2. **The contract is a committed artifact with a SHA**, mirroring the sprite-consumer ruling: aeon
   commits the schema + the exact field list its generator reads (venue: aeon docs, or empyrean if
   ruled cross-tool); Aurora pins a writer-side golden against it and its parcels are cut against
   that SHA (the lane split recorded in aurora ROADMAP §5.2).
3. **Assignments live in the editor tree, bindings are baked:** the editor owns "section N →
   scene/preset id" (sidecar or effects JSON — open question 2), and the bake emits the binding
   table the `.emp` consumes, ending the hand-edited `act_descriptor.emp` binding path for
   editor-authored content. How far `act_descriptor.emp` itself becomes generated is open
   question 3.

## (e) Preview feasibility verdict

**Verdict: BOTH, in order — the oracle loop is nearly free and is the truth; an in-Aurora
approximate preview is the actual value of the view and is feasible in the current renderer.
Bit-exact TS goldens stay deferred per the standing spec until the preview exists to pin.**

- **Launch-in-oracle loop — effort S (mostly wiring).** The plumbing shipped with Aurora P2:
  `build_and_run` + `warp` + a live Aether client (ROADMAP §2.7). The loop is save →
  `FAST=1 DEBUG=1 ./build.sh` (auto re-bakes a stale editor tree, ~1 s incremental) →
  `reload_rom` → warp to the section — exactly the interim loop the scanline design names
  (`:383`). Caveats: FAST skips all verification lanes (fine for an authoring loop, never for
  landing), and `effects_gates.py` is tens of seconds per gate, so it stays a pre-merge ritual,
  not an inner loop.
- **In-Aurora static/scrubbed preview — effort M.** All the math is comptime-simple integer work
  that ports 1:1 to TS: packed shift-add factors (`parallax_dsl.emp:21-40`), deform-table
  sampling (`(frame*speed + line + phase) & $FF`), vsplit row snapping, variant transforms
  (`clamp((c >> shift) + bias)`), tint-band per-row palette swaps. Rendering per-line HScroll in
  canvas 2D means blitting the composed BG in 1-px-tall rows with per-row offsets (224 draw calls
  or ImageData row shifts per pass) — INFERRED affordable: the shipped per-pixel occlusion pass
  measures 0.18 ms and the animated-preview passes 0.2-0.7 ms on the same canvases, and a preview
  lens can render at play-clock rate, not per-edit. Honesty rule from the 2026-08-11 design
  carries over: label what is approximated (CRAM dots, DMA timing, the N+1 landing line) instead
  of pretending.
- **BgAnim band preview — effort S-M, and YES it can preview from source.** The 8 pre-shifted
  banks are generated at bake from the band's `phases` array, but the phases themselves live in
  the editor JSON — Aurora can drive fine phase (bank select) and coarse rotation (column
  reindexing) directly from the source strip on the existing shared play-clock, no baked banks
  needed. The driver model (Camera_X/Y/Logic_Tick + rate_shift) is three integers.
- **Full TS scanline simulator with golden fixtures — effort L, defer.** This is the "bit-exact
  where it counts" lab tier (2026-08-11 §7); the scanline design already defers its goldens to
  this arc's later phase. Do not gate the first preview on it.

## (f) Open questions — ADJUDICATED under owner delegation, 2026-08-22

> **Provenance (flagged per the decision-audit rule):** after the assessment landed, the owner
> delegated all six answers — "whatever you think is best … do what's best for our best-in-class
> tools + engine" — with one stated lean: Q2, "probably the section one". The rulings below are
> therefore **assistant-authored under owner delegation**, not owner-dictated; each carries its
> reasoning so the design review can overturn any of them cheaply. The questions as originally
> posed are kept verbatim in the next subsection.
>
> **OWNER CONFIRMED 2026-08-22** in the main conversation: all six stand as ruled. The
> pending-eyeball-confirmation gate from the 08-22 handoff is CLOSED; Aurora-arc doc work
> (schema/contract halves + wave-1 design) is cleared to cut.

1. **v1 scope → two waves, both inside this arc.** Wave 1 = BgAnim bands + scene parameter
   editing + section assignment (the contract-mature pieces); wave 2 = raster preset composition
   (tint bands / vscroll splits / patchable channels), cut immediately after wave 1's contract
   golden is green — sequenced, not deferred, because the showcase goal needs it. The banked
   effects-tail overlap parcel revives exactly when wave 2 authors the first genuinely
   overlapping program (its recorded revival condition, `docs/DEFERRED_WORK.md:5461-5468`); that
   revival is an aeon parcel.
2. **Assignments → the section sidecar** (the owner's lean, and it survives scrutiny): the
   per-section assignment is one scalar ref (`effectsRef` / `sceneRef`) in `section_N.meta.json`,
   which already carries exactly this shape — scalar refs with explicit-null semantics (OBSERVED
   aurora `src/core/project/aeon/save.ts:112-115`). Scene/preset/band **definitions** stay in
   `games/sonic4/data/editor/effects/*.json` (the act-scoped library): sidecars hold pointers,
   never bodies, so a scene shared by five sections has one definition.
3. **Bake reach → a generated binding module, NOT a generated `act_descriptor.emp`.** The
   descriptor is dense, hand-authored, contract-bearing prose; half-generating it violates
   clean-not-bolted-on. `effects_gen.py` emits a per-act generated `.emp` binding module (the
   `bg_anim.emp` / sec-local-maps precedent) whose per-section Labels `act_descriptor.emp`
   imports by name list. Design-phase check flagged: the label-vs-const import axis — label
   imports are symbol references and travel safely; const imports re-evaluate in the consumer's
   scope (`ojz_scenes.emp:70-74`).
4. **`project.json` `parallax` → re-point, one change, no interim fossil:** the dangling `.asm`
   path is replaced by a scene-id string into the new contract in the same parcel that lands the
   schema; nothing keeps or deprecates the dead path.
5. **Contract venue → both, split by role:** the cross-tool schema (what Aurora writes) goes to
   **empyrean** per the lane note in aurora's ROADMAP §5.2; the consumer field list (exactly which
   fields `effects_gen.py` and `inject_editor_bg.py` read — the thing that makes it a contract per
   the sprite-export ruling, `docs/DEFERRED_WORK.md:120-125`) lands in **aeon** beside the
   generators. Aurora pins its writer-side golden against both SHAs.
6. **Preview honesty bar → labeled-approximate is the v1 bar** (the standing spec's position);
   the oracle loop remains the truth channel from day one, and TS golden fixtures land with the
   simulator phase — i.e. when the preview first claims exactness anywhere, goldens gate that
   claim, not before.

### The questions as originally posed (kept for the design review)

1. **v1 scope:** Is the first Aurora parcel wave BgAnim bands + scene editing + section
   assignment, with raster preset composition (tint bands / vscroll splits / patchable channels)
   as a second wave — or must raster composition be in v1? (Second wave keeps the banked
   effects-tail overlap parcel un-revived until a real overlapping program is authored.)
2. **Where do section→effect assignments live:** extend the existing `section_N.meta.json`
   sidecars (the save path already owns them), or a single `editor/effects/assignments.json`
   beside the scene/preset JSON (the scanline design's sketch)?
3. **How far does baking reach into `act_descriptor.emp`:** does the bake emit a parallel
   generated binding table the descriptor references, or does the section table itself become
   generated? (Today every `ojz_sec(raster:/cycle:/effects:)` argument is hand-typed.)
4. **`project.json` `parallax` field:** re-point it at the new contract (scene ids), or delete it
   as part of the schema change? (It currently dangles at a deleted `.asm` path.)
5. **Contract venue:** aeon `docs/` or empyrean for the effects-authoring schema? (The aurora
   ROADMAP lane note says cross-tool contract material goes to empyrean; the sprite-consumer
   field-list precedent landed in aeon.)
6. **Preview honesty bar for v1:** is a labeled-approximate in-Aurora preview acceptable with TS
   golden fixtures deferred (the standing spec's position), or must goldens land with the first
   preview lens?

---

## Appendix — survey provenance

- Aeon read at `77cbf7c0` on branch `research/aurora-effects-assessment`
  (worktree `/home/volence/sonic_hacks/aeon-wt-assess`). Files read are cited inline; none
  modified except this document.
- Aurora read-only at `4cffe4561919...` (master, clean tree). Nothing committed or changed there.
- Blocked items: none. The one near-conflict — the brief's invitation to weigh "edit `.emp`
  directly" against the standing rulings — is resolved in the open (option A, rejected with the
  rulings named), not silently.
