# Aurora Effects Authoring — Wave 1 Design (BgAnim bands + scene editing + section assignment)

*Status: **draft for design review**, 2026-08-22. Docs-only parcel — no engine code, no
builds. Design inputs: the six ADJUDICATED answers in
`docs/research/2026-08-22-aurora-effects-authoring-assessment.md` §(f), owner-confirmed at
`08f01b73` — transcribed here, not re-litigated (each ruling is cited where it lands).
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
   (the neutral contract and consumer ALREADY EXIST); band preview on the shared
   play-clock; the first authored act.
2. **Scene parameter editing** — Aurora authors scene definition JSON under
   `games/sonic4/data/editor/effects/` (NEW schema; consumed by the booked-unbuilt
   `tools/effects_gen.py`, scanline P5).
3. **Section assignment** — `sceneRef` in the `section_N.meta.json` sidecars + the
   act-level default in `project.json` (ruling Q2/Q4).

**Wave 2 (sequenced, not deferred):** raster preset composition (tint bands, vscroll
splits, patchable channels, variants, cycling) — cut immediately after wave 1's contract
golden is green. Wave 2, not wave 1, is the recorded revival trigger for the banked
effects-tail overlap parcel (`docs/DEFERRED_WORK.md:5461-5468` — "a real program that
needs overlapping patchable bands"; that revival is an aeon parcel against the r3.1
design). Nothing in wave 1 authors an overlapping program, so the trigger stays untripped.

Out of scope for both waves: anything that makes Aurora emit `.asm`/`.emp` (format
boundary), anything requiring the deferred real aeon ProjectAdapter loader (§7), the full
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
  `scene_registry.emp:405` — editor scenes get the same budget gate as hand scenes, in
  their own module.
- **The import seam:** `act_descriptor.emp` imports the per-section Labels **by name
  list** and passes them where it passes hand bindings today
  (`sec_parallax_config` / `act_parallax_config`). **The label-vs-const trap is the
  load-bearing detail** (`ojz_scenes.emp:70-74`; `docs/EMP_PITFALLS.md` §2/§8): these
  MUST be `pub data` **Labels** — label imports travel as symbol references; a **const**
  import re-evaluates its initializer in the consumer's scope (the Task-5 clone-injection
  trap) and would silently duplicate every table and record into the descriptor's
  section. The generator emits Labels; the descriptor's `use` line is a name list, never
  a glob (`docs/DEFERRED_WORK.md:6847`'s glob re-evaluation note).
- **Reachability is solved by the seam itself, then pinned:** an unreached `.emp` module
  gets ZERO body elaboration — `ensure(1 == 0)` builds green
  (`scene_registry.emp:28-34`). The descriptor's name-list import IS the whole-path `use`
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
- **Editor-library ids only** in wave 1: `sceneRef` cannot name a hand-authored `.emp`
  scene (that would put symbol strings in editor JSON, coupling the editor tree to
  `.emp` internals). The twenty shipped hand scenes keep their hand bindings; open
  question §9 Q-a covers a future manifest if assignment-to-hand-scenes is wanted.
- **Aurora-side hazard (ERRATUM 1 of the assessment + addendum, verified at aurora
  `e731214`; specified in full in `tools/EFFECTS_CONSUMER_CONTRACT.md` §2.2 and the
  empyrean doc §3/§6):** Aurora's sidecar codec hardcodes the two-ref set at six sites —
  parse silently drops unknown keys AND nulls non-string values in known keys, serialize
  and the cleared-overwrite body re-emit only the enumerated fields — so a `sceneRef`
  from any non-sceneRef-aware writer is silently erased on Aurora's next save. Hence:
  the `SectionMeta` extension (all six sites) lands in the same Aurora parcel as the
  first writer; the golden pins the parse→serialize round-trip; `sceneRef` is ruled a
  string id, never a numeric index (silent-null failure mode); malformed sidecars throw,
  so non-Aurora writers write atomically; and a MISSING sidecar is all-refs-null for
  every consumer, never an error.

## 5. BgAnim authoring (the wave-1 opener)

The neutral contract and consumer already exist (`tools/inject_editor_bg.py`; field list
= `tools/EFFECTS_CONSUMER_CONTRACT.md` §1). Aurora's work is UI + preview + the first
authored act:

- **Authoring:** band editor over the existing BG override document — mark a `cols×rows`
  tile region as a band, author/import its 8 phase banks, pick driver
  (`camera_x`/`camera_y`/`timer`) and `rate_shift`. Constraints surfaced in-UI (≤ 4
  bands, contiguous packing from slot 0, `pattern_px = cols*8`, `rows*32` power of two,
  shared 448-tile capacity) but ENFORCED by the consumer's asserts — Aurora pre-checks
  are advisory UX.
- **Preview:** drives fine phase (bank select) and coarse rotation (column reindex)
  straight from the source `phases` array on the shared rAF play-clock — no baked banks
  needed (assessment §(e)). Labeled-approximate per ruling Q6.
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

**The named ProjectAdapter gap (load-bearing, not assumed away):** aurora's
`AeonProjectAdapter` is a ROUTING MARKER — `open()` returns a capability-marker handle
and the renderer still runs the legacy `useProject.loadFromPath`; the real core-callable
aeon loader is deferred (aurora ROADMAP §2.5 "Deferrals", restated in the §5.2 lane
note). **Wave 1 is deliberately shaped to fit the legacy file-level path** — every
surface is a JSON document or sidecar under the editor tree, exactly what today's facets
already read/write. What wave 1 therefore CANNOT do, by design: enumerate hand-authored
`.emp` scenes, read budget ledgers (the `<game>_scene_budgets.txt` artifact is itself
unbuilt — scanline P2's symbol-readback spike), or resolve scene→section bindings from
the built ROM. If the design review wants any of those in wave 1, that is NEW adapter
work and must be named as such, not absorbed silently.

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
- **Q-c:** The zero-editor-content descriptor seam (§3 last bullet): how the descriptor
  imports the act-default binding without a dormant scaffold when no editor content
  exists — resolve inside the P5 spike, options: always-emitted default label vs
  descriptor-side conditional. (Flagged, not decided here.)
- **Q-d:** Scene-id pattern is `^[a-z][a-z0-9_]{0,31}$` (symbol-safe); Aurora's existing
  BG-library ids use hyphens+timestamps — confirm Aurora is fine generating distinct id
  styles per document type.
- **Q-e:** Does wave 1's scene JSON need `SceneDeform.Shared` at scene level AND `Own`
  at layer level from day one (this design says yes — both are in the shipped scene
  vocabulary), or should wave-1 UI expose fewer and the schema stay full-width?
