# Aurora Effects Authoring — Wave 1 Design (BgAnim bands + scene editing + section assignment)

*Status: **draft for design review**, 2026-08-22. Docs-only parcel — no engine code, no
builds. Design inputs: the six ADJUDICATED answers in
`docs/research/2026-08-22-aurora-effects-authoring-assessment.md` §(f), owner-confirmed at
`08f01b73` — transcribed here, not re-litigated (each ruling is cited where it lands) —
plus the assessment's ERRATA 1+2 (`e7546c3f` / `b64798f6` / `5be97277`: the sidecar write
condition, the silent-null coercion, and the live meta destroy path, all verified at
aurora `e731214`).
Standing rulings inherited: effects-suite design §8 (`docs/superpowers/2026-08-11-effects-suite-design.md`),
scanline-services §7 (`docs/superpowers/specs/2026-08-17-scanline-services-design.md:355-383`,
phase table `:506-507`), the 2026-08-20 format-boundary ruling
(`docs/DEFERRED_WORK.md:112-136`). Aurora surveyed read-only at master
`e7312148a1687420266e2ae62eb2a8e518a75929` (one commit past the assessment's `4cffe456` —
that commit is the ROADMAP §5.2 booking of this arc).*

*Contract companions: consumer field list `tools/EFFECTS_CONSUMER_CONTRACT.md` (this
branch); writer-side schema `empyrean/docs/AURORA_EFFECTS_SCHEMA.md` +
`empyrean/contract/schema/aurora-effects-scene.schema.json` (empyrean branch
`docs/aurora-effects-schema`). Cross-references are by path; **the SHA at landing is to be
pinned by Aurora — Aurora pins its writer-side golden against BOTH repo SHAs** (aurora
ROADMAP §5.2 lane split: Aurora's overseer dispatches and lands all Aurora parcels against
committed aeon briefs/contracts).*

## 1. Scope (ruling Q1: two waves, both inside this arc)

**Wave 1 (this design):** the contract-mature pieces —

1. **BgAnim tile bands** — Aurora authors the `anims` key of `editor_bg_override.json`
   (the neutral contract and the CONSUMER exist; the PRODUCER does not — Aurora becomes a
   new writer of that file, see §5's correction); band preview on the shared play-clock
   (§5 flags an open viewport risk); the first authored act.
2. **Scene parameter editing** — Aurora authors scene definition JSON under
   `games/sonic4/data/editor/effects/` (NEW schema; consumed by the booked-unbuilt
   `tools/effects_gen.py`, scanline P5).
3. **Section assignment** — `sceneRef` in the `section_N.meta.json` sidecars + the
   act-level default in `project.json` (ruling Q2/Q4).

**Wave 2 (sequenced, not deferred):** raster preset composition (tint bands, vscroll
splits, patchable channels, variants, cycling) — cut immediately after wave 1's contract
golden is green. Wave 2, not wave 1, is the recorded revival trigger for the banked
effects-tail overlap parcel (`docs/DEFERRED_WORK.md:5461-5468` at `08f01b73`; this arc's
own booking shifts it a few lines down — locate by its banner, "**Revival condition: a
real program that needs overlapping patchable bands**"; that revival is an aeon parcel
against the r3.1 design). Nothing in wave 1 authors an overlapping program, so the
trigger stays untripped.

Out of scope for both waves: anything that makes Aurora emit `.asm`/`.emp` (format
boundary), ROM-derived scene/budget enumeration (an `AeonProjectData`/`S4ActConfig` model
extension — NOT the "deferred loader", see §7's correction), the full
TS scanline simulator with goldens (§6).

## 2. Data flow (the ruled Option B shape, end to end)

```
Aurora (writer)                          aeon (bake + build)
---------------                          -------------------
editor/effects/<scene>.json  ──┐
section_N.meta.json sceneRef ──┤
project.json sceneRef        ──┼──→  tools/effects_gen.py (P5)
                               │       ├─ emits generated .emp calling scene()/layer()
                               │       │  (constructor-call spike; ruled fallback =
                               │       │   data literals + comptime verifier)
                               │       └─ emits per-act BINDING module (§3)
editor_bg_override.json anims ─┼──→  tools/inject_editor_bg.py (EXISTS)
                               │       └─ bg_anim_banks.bin + generated bg_anim.emp
                               └──→  (Aurora reads tools/effects_budget_model.toml
                                      for the advisory meter; the hard gate stays
                                      in the build — 2026-08-11 §8's two points)
```

Generated output is committed + drift-gated; bulk data rides `.bin` + `embed()`; the bake
joins the level re-bake lane behind `tools/level_staleness.py`-pattern staleness (all
scanline §7, restated not re-decided). One direction, no sync loops.

## 3. The generated binding module (ruling Q3)

> **IMPLEMENTED 2026-08-22 (scanline P5 slice 5, branch `parcel/p5-binding-seam`) —
> AND TWO BULLETS BELOW ARE SUPERSEDED. Read this banner before the bullets.**
>
> 1. **The zero-editor-content shape.** The last bullet's "the stub always exports the
>    act-default label aliased to nothing only when `project.json`/sidecars are silent"
>    is superseded by the owner's **Q-c ruling: the always-emitted default**. The
>    binding is emitted for EVERY act, content or not; with no editor scenes it
>    resolves to the HAND-AUTHORED default (not to nothing), which is what keeps the
>    descriptor's single path live. The reachability poison landed WITH the seam, per
>    the same ruling.
> 2. **The label-vs-const mechanism.** The `pub data` **Label** mandate HOLDS for
>    everything with bytes — the deform tables and the lowered records are `pub data`
>    Labels under stable names, and the const-axis trap this bullet names is real. It
>    cannot express the zero-content arm, where the binding must resolve to a label in
>    ANOTHER module, and all three label-carrying spellings were MEASURED to fail:
>    `pub equ` is not importable (sigil `item_pub_name()` has no `Item::Equ` arm,
>    contradicting `empyrean/docs/SIGIL_SPEC2_LANGUAGE.md` §7.5 — a spec/impl
>    divergence, open on the sigil lane); `pub const X = <label>` fails `unknown name`
>    at the DEFINING file's span, because an imported const's initializer folds to an
>    i64 at the definition site and a Label does not fold, so the clone re-evaluates in
>    the consumer — this bullet's own trap, firing on the shape it warned about; and no
>    zero-byte label-alias form exists in `.emp` at all. **The shipped mechanism is a
>    `pub comptime fn` returning a Label, with the hand fallback as a `hand:`
>    parameter** — no image to clone into the descriptor's section, and a
>    content-independent name for the hand-authored `use` line. The import is still a
>    NAME LIST, never a glob, and it is still the module's only reachability edge
>    (measured: `ensure(1 == 0)` in the generated module fails the build with the seam
>    and builds GREEN with an unchanged CRC without it).
>
> Also NOT done, deliberately: no `map.toml` `order` row. The row must name a
> CONTENT-DERIVED head label, the section emits zero bytes until the first editor
> scene, and sigil stops the build by name the day it emits. A reserved-slot comment
> marks the position. Full rationale + the shipped surface:
> `docs/DEFERRED_WORK.md`'s wave-1 booking, item 1.


**The descriptor stays hand-authored.** `act_descriptor.emp` is dense, contract-bearing
prose; half-generating it violates clean-not-bolted-on. Instead `effects_gen.py` emits,
per act, ONE generated `.emp` module — the `bg_anim.emp` / sec-local-maps precedent:

- **Placement:** `games/sonic4/data/generated/ojz/act1/effects_scenes.emp`, its own
  module (`games.sonic4.ojz_effects_editor_act1`) in its own `map.toml`-placed section —
  exact names are the implementing parcel's to pin; the design constraint is one
  generated module per act, never edits inside hand-authored files.
- **Contents:** (a) deform tables realized from `tableRef`s (generator calls or
  `embed()`); (b) each editor scene built through the real `scene()`/`layer()`
  constructors — every `ensure` fires on authored content; (c) the lowered records; (d)
  **per-section binding Labels** (e.g. `EditorScene_Act1_Sec0`) plus the act-default
  binding — resolved from the sidecars' `sceneRef` + `project.json`, so "section N uses
  scene X" stops being hand-typed in the descriptor for editor-authored content;
  (e) `scene_budget_enforce` over the editor-scene set, mirroring
  `games/sonic4/data/effects/scene_registry.emp:405` — editor scenes get the same budget gate as hand scenes, in
  their own module.
- **The import seam:** `act_descriptor.emp` imports the per-section Labels **by name
  list** and passes them where it passes hand bindings today
  (`sec_parallax_config` / `act_parallax_config`). **The label-vs-const trap is the
  load-bearing detail** (the `use games.sonic4.scene_registry.{DeformTable_*}` name-list
  import in `games/sonic4/data/effects/ojz_scenes.emp`, whose comment block states the
  const-axis trap; `docs/EMP_PITFALLS.md` §2/§8): these
  MUST be `pub data` **Labels** — label imports travel as symbol references; a **const**
  import re-evaluates its initializer in the consumer's scope (the Task-5 clone-injection
  trap) and would silently duplicate every table and record into the descriptor's
  section. The generator emits Labels; the descriptor's `use` line is a name list, never
  a glob (`docs/DEFERRED_WORK.md:6847`'s glob re-evaluation note).
- **Reachability is solved by the seam itself, then pinned:** an unreached `.emp` module
  gets ZERO body elaboration — `ensure(1 == 0)` builds green
  (`games/sonic4/data/effects/scene_registry.emp:28-34`). The descriptor's name-list import IS the whole-path `use`
  edge, and the `map.toml` order entry places the section; a gate still pins both (a
  poisoned-ensure reachability probe, the `poison_sentinel` pattern), because "the
  import exists today" is not "the import cannot be dropped tomorrow".
- **Zero-editor-content shape:** with no editor scenes and no assignments, the generator
  emits a stub module (no scenes, no labels) and the descriptor's hand bindings stand
  untouched — the descriptor must not import names that vanish, so the stub always
  exports the act-default label aliased to nothing only when `project.json`/sidecars are
  silent. How the descriptor conditions on "editor default vs hand default" without a
  dormant scaffold is an implementing-parcel decision flagged for the P5 spike (see §9
  Q-c).

## 4. Assignment semantics (rulings Q2, Q4)

- **Sidecar `sceneRef`** (`section_N.meta.json`): string scene id or null; null = act
  default; explicit-null semantics identical to `bgLayoutRef` (aurora
  `src/core/project/aeon/save.ts:112-125`). Sidecars hold pointers, never bodies — a
  scene shared by five sections has one definition in the library.
- **`project.json`**: the dangling `parallax` key (repo-root `project.json:20`, pointing
  into the deleted `data/parallax/`) is deleted and replaced by act-level `sceneRef` in
  the same parcel that implements this schema — one change, no interim fossil (Q4). Null
  = the hand-authored `act_parallax_config` default stands.
  > **ORDERING IS LOAD-BEARING — the two repos move in sequence (corrected 2026-08-22, defect
  > found by aurora-86's first wave-1 parcel).** aeon deletes/re-points `parallax` in
  > `project.json` FIRST; Aurora re-points its `Act.parallaxRef` reader in the parcel
  > **following** that landing. The empyrean schema §4 originally said Aurora does it "in its
  > first arc parcel", which outran this repo: at `00607dd5` the key is still
  > `"parallax": "games/sonic4/data/parallax/ojz_default.asm"` (`project.json:20`, verified),
  > so a reader re-pointed today would point at a key that does not exist yet. Their agent
  > left it undone and flagged it rather than implementing against a doc that outran its own
  > repo — the correct call. **The aeon `project.json` edit is therefore a wave-1 aeon lane
  > item and a PREREQUISITE for Aurora's reader parcel.**
  >
  > **DISCHARGED 2026-08-22 — aeon `7bff8488` (branch `parcel/project-json-scene-ref`).** The
  > act entry now reads `"sceneRef": null` and the `parallax` key is gone; `project.json:20`.
  > **Aurora's reader parcel is UNBLOCKED and may proceed** — re-point `Act.parallaxRef`
  > (`s4-types.ts`, populated at `load.ts:373`), NOT the section field, per the correction
  > directly below. The prerequisite half of the sequence is closed; the ordering note is kept
  > for the record of WHY it is sequenced, not as outstanding work.
  >
  > The parcel verified the "nothing reads through it" claim rather than inheriting it. Four
  > readers of `project.json` exist in aeon, all read-only Python, all named-key access with no
  > generic iteration over the act entry: `tools/ojz_strip_gen.py` (`zones[0].tileset`,
  > `acts[0].{gridWidth,gridHeight,dataPath}`), `tools/ojz_entity_gen.py` (same act keys),
  > `tools/test_editor_inputs.py` (`zones[0].tileset`), and `tools/level_staleness.py` — which
  > uses the file's **mtime only** and never parses it. `build.sh` and the sigil tree reference
  > `project.json` not at all. No aeon writer exists; no `*.schema.json` exists to reject
  > `sceneRef`. Confirmed empirically too: a full `tools/regenerate-level.sh` after the edit
  > re-baked every generated level byte IDENTICAL. All four canonical shapes are byte-unchanged
  > (`s4.bin` 060401e4, `s4.debug.bin` 0dbaa80f, `demo.bin` c708b114, `demo.debug.bin` dec88cc1).
  >
  > **No gate was added, deliberately** — a "`project.json` has no `parallax` key" check would
  > assert the edit rather than any behaviour, and the key is unread, so the correct coverage is
  > none.
  >
  > **Operational note the next hand will trip over:** `project.json` is an mtime input to
  > `tools/level_staleness.py:136`, so editing it FAILS the canonical build's staleness gate even
  > when no editor content changed. Remedy is one `tools/regenerate-level.sh` (incremental, ~1 s).
  > That re-bake rewrites only `DONOR_PROVENANCE.json`'s donor/generator SHA stamp, which this
  > parcel did NOT commit: the level bytes are unchanged, so the existing stamp still describes
  > the bake that produced them, whereas the re-run's stamp names a DIRTY donor the generator
  > itself flags as non-identifying. Disposition of that stamp is an overseer call.
  > **TARGET THE ACT FIELD, NOT THE SECTION FIELD — corrected 2026-08-22.** Raised by
  > aurora-86's verification pass, **re-verified firsthand by the aeon overseer** at aurora
  > `e731214`: there are **two** `parallaxRef` fields in `src/core/model/s4-types.ts` — `:121`
  > on **`Section`** and `:227` on **`Act`**. The loader populates only the Act one
  > (`load.ts:373`, `parallaxRef: actConfig.parallax`, inside the act literal); `save.ts` writes
  > neither, and `Section.parallaxRef` is set to null once at construction (`s4-types.ts:136`)
  > and never persisted. The assessment cited `:121`. **Implementing ruling Q4 from that citation
  > would wire the scene id into a dead per-section field and silently do nothing.** Ruling Q4
  > stands as ruled; its target is `Act.parallaxRef` (`s4-types.ts`).
  >
  > **Bonus for ruling Q2, from the same finding:** `Section.parallaxRef` is *already* an unused
  > per-section scalar ref of exactly the shape Q2 proposes, and `paletteRef` is the supporting
  > precedent — it persists through the sidecar today with no renderer, command or agent consumer
  > at all. "A ref that persists ahead of its UI" already ships in Aurora, so Q2 is better-founded
  > than either side argued it.
- **Editor-library ids only** in wave 1: `sceneRef` cannot name a hand-authored `.emp`
  scene (that would put symbol strings in editor JSON, coupling the editor tree to
  `.emp` internals). The twenty shipped hand scenes keep their hand bindings; open
  question §9 Q-a covers a future manifest if assignment-to-hand-scenes is wanted.
- **Aurora-side hazard (ERRATA 1+2 of the assessment, through `5be97277`, verified at
  aurora `e731214`; specified in full in `tools/EFFECTS_CONSUMER_CONTRACT.md` §2.2 and
  the empyrean doc §3/§6):** Aurora's sidecar codec hardcodes the two-ref set at six
  sites — parse silently drops unknown keys AND nulls non-string values in known keys,
  serialize and the cleared-overwrite body re-emit only the enumerated fields — so a
  `sceneRef` from any non-sceneRef-aware writer is silently erased on Aurora's next
  save. Worse, the meta path is **silently destructive today** (ERRATUM 2): a malformed
  sidecar is swallowed by a bare catch, read as all-null, and overwritten with a
  well-formed empty body at the next save — a live data-loss defect. Hence: the
  `SectionMeta` extension (**all THIRTEEN sites — the "six" this doc first cited was the codec
  frame only; see the assessment's ERRATUM 1 closing note**) lands in the same Aurora parcel as the first
  writer; the golden pins the parse→serialize round-trip; `sceneRef` is ruled a string
  id, never a numeric index (silent-null failure mode); the unreadable-sidecar
  obligation is SHARED — generators write atomically (reusing the in-tree
  `_atomic_write` idiom, `tools/ojz_block_gen.py:201-206`) and fail the bake loudly on
  an unreadable sidecar (missing = all-null; unreadable ≠ all-null, ever — the aeon
  load path is already loud-by-default, `inject_editor_bg.py:58-61`; the asymmetry is
  stated normatively in `tools/EFFECTS_CONSUMER_CONTRACT.md` §3), Aurora routes
  the meta catch through `markUnreadable` and gates the meta write (including the
  cleared-overwrite literal) behind `understood('meta.json')`.
- **NAMED PRECONDITION on wave 1's `sceneRef` work (ERRATUM 2 sequencing ruling):**
  `sceneRef` does NOT land in sidecars until Aurora's meta-gating fix is on aurora
  master. Pinned alongside this doc's other anchors: **aurora meta-gating fix SHA:
  `a88db05`** (aurora master, merged and re-verified on the merged tree: `tsc --noEmit`
  clean, `vitest` 3856 passed / 3 skipped across 323 files, delta exactly the 7 new tests;
  red-first proof shows the destruction as bytes on disk, and three planted mutations
  include one that breaks only the save half) — the placeholder is discharged; the
  fix is reviewed and landed, and the implementing parcel replaces this TBD before
  cutting sceneRef work. Everything else in wave 1 (scene files, BgAnim authoring,
  `project.json` re-point, effects_gen scaffolding) is NOT blocked by it.

## 5. BgAnim authoring (the wave-1 opener)

The neutral contract and the CONSUMER already exist (`tools/inject_editor_bg.py`; field
list = `tools/EFFECTS_CONSUMER_CONTRACT.md` §1).

> **CORRECTED 2026-08-22 — the PRODUCER does not. Aurora becomes a NEW writer here, not an
> extender.** `editor_bg_override.json` has **zero references anywhere in Aurora's `src/`**
> (aurora-86 grepped it; re-verified firsthand by the aeon overseer at aurora `e731214` —
> `grep -rn editor_bg_override src` returns 0 hits). The suite's only producer today is
> aeon's own `tools/png_to_bg_override.py`. Aurora's ROADMAP had listed the file under
> "editor-owned inputs the build already consumes", which is where the earlier
> "the contract already exists" framing came from; their overseer corrected that line at
> aurora `bccd875`. **Consequences to design for, not discover:** wave 1 must build a writer
> for a document Aurora has never touched, AND answer the ownership question — what happens
> when Aurora and `png_to_bg_override.py` both want to write the same file (last-writer-wins
> is not an answer; the tool bakes `layout`/`tiles` from a PNG while Aurora would own
> `anims`). Name the owning writer per key, or make the tool's output an input Aurora merges.

**Aurora prior art to build ON, not around** (committed, aurora-side): their
`docs/superpowers/specs/2026-08-13-ux-overhaul-stage4-design.md` §7 (`:302-359`) already rules
the direction ("Aurora writes the JSON override, not the binaries", `:44`), books Aurora as the
record's third author (`:358`), names the slot-renumber hazard as the main correctness risk
(`:344-345`), and carries an invariant list (`:349-357`) plus a round-trip golden (`:428`).

> **BAND DRIVERS DO NOT CHOOSE AN AXIS — every band shifts HORIZONTALLY.** The `driver` field
> selects the *scalar source* only (`Camera_X` / `Camera_Y` / `Logic_Tick`), never the direction
> of motion. Verified firsthand in our own engine: `engine/level/bg_anim.emp:5-6` — "Each band is
> a **horizontally-periodic** pattern held in a contiguous range of BG tile slots, column-major"
> — and the motion is whole-column rotation (`:163-164`, `:179-186`), with `step_mask` = pattern
> width in px − 1. So `camera_y` means "driven by vertical camera movement", producing horizontal
> pattern motion. **A band editor that presents `camera_y` as vertical motion is wrong**, and it
> is the natural misreading. (Raised by aurora-86 from their
> `docs/superpowers/plans/2026-08-14-plan6-handoff.md:172-179`.) The same handoff records that
> §7.5's "import 448 from `vram_map.py`" describes machinery that does not exist on their side —
> do not spec against that import.

Aurora's remaining work is UI + preview + the first authored act:

- **Authoring:** band editor over the existing BG override document — mark a `cols×rows`
  tile region as a band, author/import its 8 phase banks, pick driver
  (`camera_x`/`camera_y`/`timer`) and `rate_shift`. Constraints surfaced in-UI (≤ 4
  bands, contiguous packing from slot 0, `pattern_px = cols*8`, `rows*32` power of two,
  shared 448-tile capacity) but ENFORCED by the consumer's asserts — Aurora pre-checks
  are advisory UX.
- **Preview:** drives fine phase (bank select) and coarse rotation (column reindex)
  straight from the source `phases` array on the shared rAF play-clock — no baked banks
  needed (assessment §(e)). Labeled-approximate per ruling Q6.
  > **OPEN RISK, do not treat as solved (raised 2026-08-22 by aurora-86, their measurement to
  > close):** the play-clock/overlay machinery the assessment §(b) credits is
  > **`ClassicLevelViewport`-only** — their `viewStore.ts:52-56` declares those overlays `s1`-only,
  > and the OJZ showcase runs on **`MapViewport`, which has zero `requestAnimationFrame` calls**.
  > So "the machinery to hang effects passes on already exists" is true for classic and **not for
  > the viewport this arc actually targets**. There is also **no aeon-viewport performance datum at
  > all** (their ROADMAP's "0.18 ms avg" was a single observation quoted as a held property; the
  > harness only asserts `avg < 5 ms` — corrected their side at `bccd875`). aurora-86 owes a
  > foreground CDP measurement rather than an assumption. **If MapViewport needs its own animation
  > loop, that is a wave-1 prerequisite on the Aurora lane, not a detail.**
  >
  > **CORRECTED 2026-08-22 — "wave-1 prerequisite" was OVERDRAWN.** Ruled by aurora-86
  > (`3328c49`) and accepted here: nothing in the writer half reads a clock — region marking,
  > bank authoring, constraint UX, the `anims` writer, the sidecar codec, scene JSON, `sceneRef`.
  > The clock is **its own parcel with exactly one intra-wave ordering edge** (land no later than
  > the band-preview parcel) and gates nothing else. Aurora's wave-1 writer parcels proceed
  > without it. **Nothing on the aeon side depended on the prerequisite framing.**
  >
  > **AND THE FORK ITSELF WAS POSED ON A FALSE UNIFORMITY** (their ruling, derived from OUR
  > engine source; re-verified here): BgAnim bands are **not uniformly time-driven**.
  > `engine/level/bg_anim.emp:135-147` dispatches three drivers — `camera_x` (0), `camera_y` (1),
  > `timer` (2 = `Logic_Tick+2`) — and **`camera_x` is the schema §5 default**, so two of three
  > are functions of camera POSITION, not time. Ruled shape: **driver-faithful preview** — camera
  > bands ride the existing pan repaints clocklessly (`MapViewport.tsx:574` already carries
  > `vpX, vpY` in its draw-effect deps), and only `timer` bands need a clock, `rate_shift` being
  > the one parameter judgeable solely in motion. A wall-clock preview of a camera band would
  > teach the WRONG DRIVER MODEL — the same misreading the driver-axis banner above warns about.
  > **Labeled-approximate licenses an approximate phase; it does not license a wrong driver
  > model.** The owner-facing question is therefore narrower than "does MapViewport need a loop":
  > it is "when do `timer` bands get one", and it no longer gates wave 1.
- **Wave 1 discharges `inject_editor_bg.py`'s byte-unproven animated arm.** The arm is
  "FORMAT-FAITHFUL BUT NOT BYTE-PROVEN — the first animated act proves this arm"
  (`inject_editor_bg.py:121-124`). The first Aurora-authored act makes the six-target
  gate exercise the animated path for real; the byte-proof (gate evidence, oracle
  verification of `BgAnim_Update` against the authored bands) is an **aeon lane item**
  in the parcel that lands that act — TAGGED for the controller: it needs the emulator,
  which docs parcels never touch.

## 6. Preview posture (ruling Q6)

**Labeled-approximate is the v1 bar.** The in-Aurora preview (per-row HScroll blits,
deform sampling, vsplit snapping, BgAnim playback on the play-clock) labels what it
approximates — CRAM dots, DMA timing, the N+1 landing line — on-screen, never pretending
(the 2026-08-11 honesty rule). **The oracle loop is the truth channel from day one:**
save → `FAST=1 DEBUG=1 ./build.sh` (auto re-bakes stale editor tree, ~1 s) →
`reload_rom` → warp — the P2 plumbing Aurora already shipped. **TS golden fixtures land
with the simulator phase — when the preview first claims exactness anywhere, goldens gate
that claim, not before.** No wave-1 lens claims exactness.

## 7. What Aurora builds vs what aeon ships

| Side | Ships |
|---|---|
| **Aurora** (its overseer dispatches/lands, against pinned SHAs) | Effects facet (the registry pattern — one module per engine, `facet-registry.ts`); scene editor UI writing `editor/effects/*.json`; BgAnim band editor writing `anims`; Map-mode assignment panel writing `sceneRef` sidecars; `SectionMeta` extension; `project.json` reader re-point (`parallaxRef` → `sceneRef`); labeled-approximate preview lenses on the play-clock/overlay machinery (the `5b58f68..4cffe45` line); advisory budget meter reading `tools/effects_budget_model.toml`; the writer-side golden pinned against both repo SHAs |
| **aeon** | `tools/effects_gen.py` (P5: constructor-call spike + ruled fallback, fixed `use` preamble + helper-closure gate, `schema:1` refusal, drift gate); the per-act binding module + `act_descriptor.emp` import seam (§3); the `project.json` re-point edit itself (repo-owned file); reachability + drift gates; the animated-arm byte-proof; wave-2's effects-tail revival when tripped |

**The named ProjectAdapter gap — CORRECTED 2026-08-22, the original caveat was FALSE.**

> The assessment (and this doc's first draft) said `AeonProjectAdapter` is a ROUTING MARKER
> whose `open()` returns a capability-marker handle while the renderer still runs a legacy
> `useProject.loadFromPath`, with the real loader deferred per aurora ROADMAP §2.5/§5.2.
> **That is refuted.** Raised by aurora-86's verification pass, **re-verified firsthand by the
> aeon overseer** at aurora `e731214`: `src/core/project/aeon/index.ts:115` is
> `const aeon = await loadAeonProject(fa, fa.rootDir ?? '')` — a real project load returned on
> `handle.aeon`, with the file header at `:4-7` stating exactly that; and `useProject.loadFromPath`
> **does not exist in `src/`** — its only three hits are comments describing what replaced it.
> Both closed in aurora `4782e86` (2026-08-13), which `git merge-base --is-ancestor 4782e86
> 4cffe45` confirms is an **ancestor of the assessment's own survey pin** — so the caveat was
> already stale when the survey quoted it. The fault is aurora's ROADMAP, which their overseer is
> correcting in their repo; the survey quoted it faithfully.

**The CONCLUSION survives; the cause and the cost do not.** Nothing in `AeonProjectData` names a
scene, preset, band or budget, so wave 1 still cannot enumerate hand-authored `.emp` scenes, read
budget ledgers (`<game>_scene_budgets.txt` is itself unbuilt — scanline P2's symbol-readback
spike), or resolve scene→section bindings from the built ROM. But the reason is a **model that
does not carry those fields, not a loader that does not exist**: closing any of it is
**extending `AeonProjectData`/`S4ActConfig`, not building a loader**, and is therefore
substantially cheaper than the deferred-loader framing implied. **No doc may price this arc as
"needs the deferred aeon loader built first."** Wave 1 remains shaped around JSON documents and
sidecars under the editor tree regardless — that is a scoping choice, no longer a forced one. If
the design review wants ROM-derived enumeration in wave 1, name it as model-extension work.

## 8. Verification

- **Contract:** Aurora's writer-side golden (their lane) against the empyrean schema +
  this repo's consumer list, both SHAs pinned.
- **Bake:** generated module committed + drift-gated (regenerate-and-verify);
  reachability poison probe (§3); the P5 spike's own gates per scanline §7.
- **Budget:** `scene_budget_enforce` over editor scenes in the generated module (hard
  gate, build-time); Aurora's meter is advisory only.
- **Effects gate ritual:** wave-1 parcels as designed touch generated DATA modules, not
  `engine/effects/*` / `engine/level/bg_anim.emp` / `engine/system/buffers.emp`, so the
  2026-08-18 ritual is not mechanically triggered — but the parcel landing the FIRST
  ANIMATED ACT must run `tools/effects_gates.py` anyway and paste totals into merge
  evidence, because it changes what the six-target gate exercises (the animated arm).
  TAGGED for the controller: emulator-lane work, never from a docs/subagent session.
- **Nothing in this docs parcel claims runtime verification.** Every runtime claim above
  is a booked lane item for implementing parcels.

## 9. Open questions for the design review

- **Q-a:** Should a future manifest expose hand-authored scenes (the twenty shipped) to
  sidecar assignment, or do hand scenes stay hand-bound forever? (Wave 1: editor ids
  only; deliberate.)
- **Q-b:** `project.json` re-point spelling — this design renames `parallax` →
  `sceneRef` (empyrean doc §4 carries the naming note); confirm or keep the literal key
  with scene-id value.
- **Q-c: RULED AND IMPLEMENTED 2026-08-22 — the always-emitted default.** The
  generator emits the act-default binding for every act, content or not; with no
  editor scenes it resolves to the hand-authored default, with editor scenes to the
  editor-authored one, so the descriptor has exactly ONE path, always live. The
  descriptor-side conditional was the option that created the dormant scaffold. The
  ruling also fixed the reachability poison to land WITH the seam, on the stated
  trade-off that always-emitting makes the generated module load-bearing for every
  act even at zero editor content. **The ruling settled the STRUCTURE; the `.emp`
  MECHANISM was settled by measurement in the implementing parcel** — see §3's
  supersession banner (it is a `pub comptime fn`, not a label alias, because no
  zero-byte label alias exists).
- **Q-d:** Scene-id pattern is `^[a-z][a-z0-9_]{0,31}$` (symbol-safe); Aurora's existing
  BG-library ids use hyphens+timestamps — confirm Aurora is fine generating distinct id
  styles per document type.
- **Q-e:** Does wave 1's scene JSON need `SceneDeform.Shared` at scene level AND `Own`
  at layer level from day one (this design says yes — both are in the shipped scene
  vocabulary), or should wave-1 UI expose fewer and the schema stay full-width?
