# Deferred Work

Tracks work that was identified during design/implementation but deferred because dependencies don't exist yet. Check this document at the start of each new system's planning phase — items here may now be unblocked.

> **Open defects** (not deferred features) live in **`docs/BUGS.md`**.
> ~~See BUG-001: intermittent section-streaming rendering corruption (garbage tiles + red field) —
> captured live-emulator evidence.~~ **CORRECTED 2026-08-05:** BUG-001 was **RECLASSIFIED
> UNREPRODUCIBLE on the current engine (2026-08-02)** — see `docs/BUGS.md:206`. The banner is kept
> struck-through rather than deleted because the pre-July entries below were written while that
> corruption was believed live, and several of them cite it as motivation.

---

## ⚠ RECONCILIATION BANNER — verified against HEAD `0e1f32c` on 2026-08-05

**This file was re-derived against the tree on 2026-08-05 (parcel `parcel/backlog-reconcile`).
Roughly 20-25% of the entries that read as OPEN were wrong.** The corrections are annotated in
place — every corrected entry keeps its original text beneath a marked correction, because knowing
*why* something was believed is load-bearing in this repo.

**Where the rot is concentrated:**

| stratum | trust |
|---|---|
| pre-July §1 / §2 / §4 entries (Apr-Jun 2026) | **LOW** — many describe deleted subsystems |
| §4 teleport / leapfrog cluster specifically | **DEAD** — 11 entries, subsystem deleted by `eddbbf7` |
| §3 / §4.6 parallax / §4.9 entity entries | mixed — anchors drift, substance mostly holds |
| sound sections (all) | **GOOD** — self-annotating, mostly current |
| 2026-07 and 2026-08 strata | **GOOD** — written under the current conventions |

**Anchor warning — do not chase file:line citations blind.** Pre-July entries were written
against the AS-era tree and cite `.asm` paths and line numbers into files that **no longer exist**:
`main.asm`, `ram.asm`, `constants.asm`, `engine/player/*.asm`, `engine/level/section.asm`,
`engine/sound_*.asm`, `data/sound/fm_patches.asm`. The `.emp` port replaced them (`build.sh:4` —
"`sigil build` IS the build"); the only surviving `.asm` files are the vendored
`engine/debug/debugger.asm` and the two 40-50 line `games/*/game_root.asm` residual roots.
**Re-derive the anchor from the symbol name before acting on any pre-July line number.**

**Three things the file previously said that were flatly inverted, all now fixed below:**
1. The **MDDBG / release-fault** entry described the *opposite* of what ships (owner ruling
   2026-08-04 superseded the 2026-08-05 strip). See the corrected entry near the bottom.
2. The **graph-coloring allocator** was listed as future work *and* as Done in the same file,
   while the allocator is dead code that no longer exists anywhere in the tree.
3. The **VDP `$0B` propagation bug** entry described a live bug that the *same file*, 60 lines
   earlier, records as a **misdiagnosis**.

---

## NOW UNBLOCKED — actionable (compiled 2026-08-05)

Every item here had a stated blocker that **no longer holds**. This is the pick-up list. Ordered
by leverage, not by section. Each links back to its full entry below; read the entry (and its
correction) before planning — several carry caveats that shrink the win.

### SIGIL'S 5-RED BAR AGAINST aeon 415e0b6a — class (A) is the HARNESS, not this tree — booked 2026-08-25

**Provenance:** sigil lane log 2026-08-24T23:57Z (sigil `docs/OVERSEER.md` "Full suite bar":
3844 passed / 5 failed / 4 ignored at sigil `e36debf8`, reproduced on unmodified `bc05f446`).
The five: `act_descriptor_region_matches_reference`, `act_descriptor_debug_region_matches_reference`,
`act_wrong_base_map_places_the_section_at_a_different_address`,
`swapped_sec_fields_produce_different_bytes`, `soundbankhead_pinned_bootstrap_lands_at_lma_not_vma`.

**Ruling from the reproduction (parcel/sigil-red-closure, both repos):** NOTHING in this tree is
wrong, and the lane's stated cause ("map.toml still carries the block as a RESERVED SLOT") is
the cause of only ONE of the five. Two failure classes, one newly unmasked:

- **(A) `unknown function ojz_act1_act_default` / `ojz_act1_sec_scene`** — the four act tests.
  Both act harness paths (`act_descriptor_port::compile_real_file`,
  `tranche4_negative_probes::parse_act_with_structs`) lower `act_descriptor.emp` single-file
  with a hand-listed ambient set that predates P5 slice 5's import of the two binding
  `pub comptime fn`s from the generated `ojz_effects_editor_act1` module. A comptime fn
  cannot ride as a link equ the way every other cross-seam name there does, so the fix is
  to ride `games/sonic4/data/generated/ojz/act1/effects_scenes.emp` ambient like the K3
  const modules. **Sigil-owned; proposed on sigil branch `parcel/sigil-red-closure`
  (75802f6a), not merged.** The `sigil build` path was never affected — the descriptor's
  whole-path `use` edge (the banner above it) carries the module into the closure, and the
  four shipped ROMs are unchanged (CRC32 c7b9d10d / f0175028 / c708b114 / dec88cc1).
- **(B) `section ojz_effects_editor_act1 has no region in the map`** — the soundbankhead
  test only, via `native::resolve_pinned_sections` → `build_native_emp` → `place_sections`
  under the PinnedBaked map minted from sigil's registry (`emp_map_toml(specs)`), which has
  no row for the zero-byte generated section. Sigil-owned, queued there as FIVE-REG. The
  map.toml `order` row is NOT the fix and is deliberately absent (map.toml:106 comment).
- **(C) unmasked by (A):** with the ambient fixed, the two `act_descriptor_port` gates reach
  the byte compare and fail `section.bytes.len() == pins::ACT_DESCRIPTOR.plain_len`:
  emitted 0x27A (= 0x28 Act header + 9 × 0x42 Sec, `OJZ_Act1_Sections` sits at +0x28 in
  `s4.lst`), pinned 0x27C. The pin was 0x27A through sigil `85a5b879`; the `805370b1`
  refreeze (ojz-section0-paint) moved the base to $159E4, and `OJZ_Sec0_Blocks` now lands
  on an alignment boundary two bytes past the descriptor's end — `repin` measures
  start..next-label, so the successor's fill entered the pin. The first 0x27A bytes match
  the reference in both shapes (probed with the length assert relaxed, probe discarded).
  Sigil-owned (pin measurement or the exactness assert); nothing in aeon moves for it.

**Remaining:** (B) and (C) stay red until the sigil lane lands them; expect 3 red on their
bar after (A) merges (the two port gates on (C), soundbankhead on (B)).
### PARALLAX CONFIG PRECEDENCE — section > preset > act, ONE resolver — CLOSED 2026-08-26

**Found 2026-08-26 by aurora's first authored scene** (measured live: `Parallax_Current_Config`
read `ParallaxConfig_OJZ_Underwater` after the first crossing while section 0 carried the editor
binding `EditorSceneBinding_OJZ_Act1_Sec0`). Provenance: the two resolution sites each read a
different PAIR of the three bindings — `engine/effects/preset.emp:299` (the crossing, via
`Effects_InstallPreset`'s tail) resolved `ep_parallax`-else-act and never read
`Sec.sec_parallax_config`; `games/sonic4/test/ojz_scroll_test.emp:505` (the boot select) resolved
`sec_parallax_config`-else-act and never read the preset. So the per-section binding could only
ever win for the first painted frame, and the preset took it back on the first crossing.

**Closure:** `Effects_ResolveParallax` (`engine/effects/preset.emp`) is the one resolver —
precedence `Sec.sec_parallax_config` > `EffectsPreset.ep_parallax` > `Act.act_parallax_config`,
a 0 at either upper rung meaning "defer", never "keep". `Effects_InstallPreset` spills the Sec*
to the stack at entry and tail-jumps into it (no address register survives its six callees and
widening to a4 would propagate up `Parallax_CheckBoundary`'s declared contract); the boot select
calls it directly. Both `map.toml`s declare the new emitter. Shipped content at closure: no
section binds `sec_parallax_config` (ROM-read, 9/9 zero) and only `OJZ_Preset_Sec0` binds
`ep_parallax`, so the crossing path resolves exactly as before — the boot select now seeds
section 0's Underwater config directly instead of the act default, which removes the
Default→Underwater lerp the sentinel-forced first crossing used to run at boot (the invariant
`Parallax_Init`'s own comment promises: the first `Parallax_CheckBoundary` is a no-op against
the seeded config).

**Left open (controller-tagged):** (a) runtime confirmation that `Parallax_Current_Config`
equals the editor record after a crossing once the aurora binding lands; (b)
`tools/boot_override_gate.py`'s premise tripwire counts `sec_parallax_config` only — with the
boot select now reading the preset rung, an override into section 0 seeds a different config
than one into section 1 TODAY, so the gate's blind spot is observable and the tripwire does not
fire on it. Extend the tripwire to count `ep_parallax` bindings too (or witness the select as
the gate's own instruction says) before trusting its green for that consumer.

### CONTRACT MEMBERS ARE INVISIBLE TO STRUCT LAYOUT — the half of Scanline P3 Task 8 that could not land — booked 2026-08-20

**Blocked on: sigil.** Aeon-side work is done and shipped byte-identically; this is the one
edit that turns a pinned mirror back into a derivation.

> **ACCEPTED + LEDGERED sigil-side 2026-08-20** (their campaign-gap-ledger.md, sigil master
> `d3a8c91d`; sized small-medium, queued behind their in-flight m68k round-trip parcel).
> Their kill condition includes an AEON-side confirmation step this entry now owes: when the
> defines parcel lands, re-run T8's three measured contexts (data-binding layout, struct
> harvest, RAM harvest) with a capability-derived define and confirm all three see it — the
> spike harness in EXTENDED-RECORD.md re-pointed, cheap. The larger Game.*-in-layout fix is
> ledgered separately on their side, demand-gated; retiring our EMP_PITFALLS §9 is written
> into it.

**The ask, in one line:** expose each game's declared `SCANLINE_CAPS` as an `emp_defines`
row (`crates/sigil-harness/src/native.rs`, beside `MAX_RING_BUFFER` / `HAS_ACT_ART_POOL`),
so it is visible where contract members are not.

**Why.** Design §3.1 makes record shapes capability-dependent: `band_record` carries a
per-layer deform extension only in a game whose mask includes `CAP_MULTI_DEFORM_TABLE`. The
natural spelling is

```emp
pub const BAND_EXT_N = if (Game.SCANLINE_CAPS & CAP_MULTI_DEFORM_TABLE) != 0 { 1 } else { 0 }
```

and it does not compile. **Three separate contexts refuse it, each measured 2026-08-20:**

| context | what happens |
|---|---|
| the layout of an emitted `data` binding's record type | `unknown name Game.SCANLINE_CAPS`, **once per emitted record** (20, one per shipped config) |
| `harvest_engine_struct_offsets` (the ambient STRUCT_OFFSET_TWINS layout: one file + `types.emp`, no profile, no defines, no contract) | `harvest_engine_struct_offsets: layout band_entry: unknown name Game.SCANLINE_CAPS` — the build dies before a byte is emitted |
| `harvest_engine_ram_addresses` (the focused `use engine.ram`-only build) | `ram harvest build_program: unknown name Game.SCANLINE_CAPS` — so `engine/ram.emp` cannot size a reservation by capability either |

A **build define is visible in all three.** Driving `BAND_EXT_N` off `DEBUG` sized
`band_record` correctly and built `s4.debug.bin` **byte-identically** (`d7b36f90`), which is
what makes this ask concrete rather than speculative: the mechanism is finished and proven,
only its input is out of reach.

**What shipped instead, and its exact ceiling.** `BAND_EXT_N` is a literal in
`engine/level/parallax.emp`, pinned two-directionally against `Game.SCANLINE_CAPS` in
`games/sonic4/data/effects/scene_registry.emp` (where both names ARE visible), with the
shadow-RAM reservation and `PARALLAX_STATE_LONGS` pinned to the record's own size. Both pin
directions are proven red. So a capability flip is a loud, one-constant edit rather than a
silent wrong lowering — **but one engine constant cannot be 0 for one game and 1 for
another, so this tree cannot carry two games that disagree about the bit.** That is the
whole of what the define buys, and it is why this is booked rather than closed.

**Secondary, same seam, optional:** `band_entry`'s membership in `STRUCT_OFFSET_TWINS` is
what forces the legacy/extension split into two structs. It is harvested for exactly one
consumer — `engine/ram.emp`'s `ensure(extern("band_entry_len") == BAND_ENTRY_LEN)`. If the
define lands, that harvest row could be retired and the extension folded back onto
`band_entry`. Not required; noted so the next reader does not re-derive the split.

**Evidence:** `docs/benchmarks/scanline-p3/EXTENDED-RECORD.md`. **Landed:** `a1d66b51`,
`cb49a3ab`, `6c434695` on `p3/t8-extended-record`.

### AURORA SPRITE-EXPORT CONSUMER — booked 2026-08-20 (Aurora asks, owner-ratified their side; format ruling made here)

Aurora's sprite export spine (June) ends at our doorstep: a real export sits in
`games/sonic4/data/sprites/` (`index.json` + `object-bindings.json` at the root;
per-sprite dirs with `art.bin` + `mappings.bin` + `sprite.json` — see `pitcher_plant/`)
and **nothing in the build reads it**. Aurora audit `2588171`,
`aurora docs/reviews/2026-08-20-p3-plan-audit.md`. Two asks, one ruling:

1. **Build an aeon-side consumer** — a bake step mirroring the level pipeline
   (`data/sprites/` → generated `.emp`/embeds at build time), NOT a hand-maintained
   twin. First step of the parcel: enumerate exactly which fields the consumer reads,
   against the real `pitcher_plant/` export, and hand Aurora that list — they freeze
   exactly those fields with a writer-vs-reader golden on their side. Until that list
   exists the format is NOT a contract; do not let a consumer grow ad-hoc readers.
2. **Format-boundary RULING (engine call, 2026-08-20): Aurora emits neutral data, aeon
   generates the code.** Their question "should our exporter emit `.emp` `offsets`
   instead of `.asm`?" — answer: NEITHER. Their June `.asm` route is dead (asl left the
   pipeline; its `align 2` per body contradicts `sonic_anims.emp`'s deliberate no-align
   packing). But Aurora emitting `.emp` would push sigil-language churn across the tool
   wall — every `.emp` syntax/idiom change would become an Aurora-coordinated change.
   The contract stays the NEUTRAL export (json + bin); the `.emp`/binary generation is
   an aeon bake-step and ours to evolve freely. Same boundary the level pipeline
   already draws (editor stamps → our flatten/dedup/generate).

Not urgent; unblocks Aurora's P3 remainder (animation authoring UI reaching the ROM).
NOTE: `object-bindings.json` is currently UNTRACKED in this repo — the consumer parcel
decides tracked-vs-generated as part of the contract, don't let it linger untracked.
NOTE 2026-08-22: the ruling's field-list precedent now has a landed sibling —
`tools/EFFECTS_CONSUMER_CONTRACT.md` (the effects consumer contract) followed this
ruling's text and placed the list beside the generators in `tools/`; the sprite consumer
contract should mirror that placement when this parcel is cut.

### AURORA EFFECTS-AUTHORING WAVE 1 — contract docs landed, implementation open (booked 2026-08-22)

The Parcel D Aurora half's contract + design docs are landed (this branch): consumer
field list `tools/EFFECTS_CONSUMER_CONTRACT.md`, wave-1 design
`docs/superpowers/specs/2026-08-22-aurora-effects-wave1-design.md`, writer-side schema in
empyrean (`docs/AURORA_EFFECTS_SCHEMA.md` + `contract/schema/aurora-effects-scene.schema.json`,
branch `docs/aurora-effects-schema`). Design inputs = the six owner-confirmed rulings
(`08f01b73`, assessment §(f)). What the docs OPEN, all still unbuilt:

1. **`tools/effects_gen.py`** (scanline P5, already booked in that design's phase table)
   now has its contract inputs: the P5 build implements EXACTLY the §2 read set of
   `tools/EFFECTS_CONSUMER_CONTRACT.md` — the constructor-call spike + ruled fallback,
   the per-act binding module + `act_descriptor.emp` name-list label import seam (design
   §3, incl. the zero-editor-content seam question Q-c), reachability poison + drift
   gates. ~~and the `project.json` `parallax` → `sceneRef` re-point in the same parcel~~
   — **the Q4 re-point is DONE and is no longer part of this item: aeon `7bff8488`
   (branch `parcel/project-json-scene-ref`), 2026-08-22.** It was split out and landed
   ahead of P5 because the corrected ordering makes it a PREREQUISITE for Aurora's
   reader parcel (design §4's ordering note), not because P5 was ready. `project.json`'s
   act entry now carries `"sceneRef": null`; the dangling `parallax` key is gone. P5
   consumes that key, it no longer creates it.

   The parcel verified — rather than inherited — the contract's "nothing reads through
   it" claim. aeon has exactly four readers of `project.json`, all read-only Python with
   named-key access and no generic iteration over the act entry: `ojz_strip_gen.py` and
   `ojz_entity_gen.py` (`zones[0].tileset`, `acts[0].{gridWidth,gridHeight,dataPath}`),
   `test_editor_inputs.py` (`zones[0].tileset`), and `level_staleness.py`, which reads the
   file's **mtime only**. `build.sh` and the sigil tree never reference it; there is no
   aeon writer and no `*.schema.json`. A full `regenerate-level.sh` after the edit re-baked
   every generated level byte identical, and all four canonical shapes are byte-unchanged.
   **No gate was added, deliberately** — the key is unread, so a "no `parallax` key" check
   would assert the edit rather than any behaviour.

   **Trap this leaves for the next hand:** `project.json` is an mtime input to
   `tools/level_staleness.py:136`, so *any* edit to it fails the canonical build's staleness
   gate even with zero editor-content change. Remedy: one `tools/regenerate-level.sh`. That
   re-bake rewrites only `DONOR_PROVENANCE.json`'s SHA stamp, which was deliberately NOT
   committed here (level bytes unchanged ⇒ the existing stamp still describes the bake that
   produced them; the re-run's names a dirty, non-identifying donor). Stamp disposition is
   an open overseer call.
   **P5 IMPLEMENTATION STATUS (2026-08-22).** `tools/effects_gen.py` exists and is
   built in slices; three have landed, none is wired to the build:
   - **Slice 1** (`ce10277e`) — scene discovery + load posture + SHAPE validation.
     Absent directory = no editor scenes; unreadable file fails loud.
   - **Slice 2** (`5f18b5a8`) — renders the `scene()`/`layer()` call TEXT (factors in
     both spellings, eight-slot padding, count, scene scalars).
   - **Slice 3** (`251a94ec`) — the real attachment spellings, and **two defects
     slices 1-2 shipped**: the absent spelling is the string `"none"` and not JSON
     null (so slice 2 would have refused every real Aurora scene), and
     `precision`/`transition`/`left_column_mask` are lowercase enum strings needing
     `.emp` constants (slice 2 emitted `precision: line`). Both had one cause: the
     slices were written from THIS contract, which enumerates field NAMES, with their
     VALUES inferred. The empyrean schema owns the values. Read the sibling repo.
   - **Slice 4** (`9b3f11f6`) — `tableRef` realization, deduped by content.
   - **Slice 5** (this parcel, branch `parcel/p5-binding-seam`) — the assignment
     readers, the generated per-act binding module, the `act_descriptor.emp` seam,
     the reachability gate, and the build wiring. **P5 IS NOW WIRED TO THE BUILD.**
   - ~~41 tests, each derived from the contract or the constructors, each proven
     non-vacuous by poison. **Nothing runs them automatically** — no `conftest.py`,
     no `pytest.ini`, `build.sh` invokes no pytest.~~ **THAT CLAIM WAS FALSE WHEN
     WRITTEN and is corrected here (slice 5, 2026-08-22).** `build.sh:414` has run
     `python3 -m pytest "${TOOLS}" -q --no-header -p no:cacheprovider` on every
     canonical (non-FAST) build since 2026-08-16, and `tools/` is exactly the path it
     collects — so `test_effects_gen.py` was already gated from the commit that
     created it. No `pytest.ini`/`conftest.py` is needed for that invocation, which
     is presumably where the belief came from. Verified by inversion: with one
     expected value perturbed, `./build.sh` reported `1 failed, 1290 passed,
     3 skipped`, printed "Tool-suite tests failed", and stopped before any ROM.

   **Q-c IS RULED AND IMPLEMENTED (owner, 2026-08-22): the always-emitted default.**
   The generator emits the act-default binding for every act, content or not — with no
   editor scenes it resolves to the hand-authored default, with editor scenes to the
   editor-authored one — so the descriptor has exactly ONE path, always live. The
   reachability poison landed WITH the seam, as the same ruling required: always-
   emitting makes the generated module load-bearing for every act even at zero editor
   content, so a generator bug can break a working act, and the gate is what makes
   that safe.

   **THE §3 TEXT IS SUPERSEDED IN TWO PLACES — read the ruling, not the design.**
   (a) §3's last bullet says the stub "exports the act-default label aliased to
   nothing only when `project.json`/sidecars are silent". Under the ruling it aliases
   to the HAND-AUTHORED DEFAULT, which is what keeps the descriptor's single path
   live; "aliased to nothing" would put the conditional back.
   (b) §3 mandates `pub data` **Labels** for the bindings. That mandate HOLDS for
   everything with bytes — the deform tables and the lowered records are `pub data`
   Labels under stable names — but it cannot express the zero-content arm, where the
   binding must resolve to a label in ANOTHER module. All three label-carrying
   spellings were tried against sigil and all three fail:
   `pub equ X = <label>` is not importable at all (sigil's `item_pub_name()`,
   `crates/sigil-frontend-emp/src/resolve/imports.rs:128-160`, has no `Item::Equ`
   arm — which contradicts `empyrean/docs/SIGIL_SPEC2_LANGUAGE.md` §7.5's "`pub equ`
   adds module visibility like every other `pub` item"; **spec/impl divergence, open
   on the sigil lane**); `pub const X = <label>` fails `unknown name` reported at the
   DEFINING file's span, because an imported const's initializer is folded to an i64
   at the definition site (`resolve/mod.rs:204-224`) and a Label does not fold, so the
   clone re-evaluates in the consumer — the design's own clone-injection trap, firing
   on exactly the shape it warned about; and no zero-byte label-alias form exists,
   since only `data` mints a ROM label and `data` always emits bytes.
   **The shipped mechanism is a `pub comptime fn` returning a Label**, with the hand
   fallback carried as a `hand:` PARAMETER. It keeps the property the Label mandate
   protected (a fn body has no image, so nothing can be cloned into the descriptor's
   section) while giving the hand-authored `use` line a content-independent name.
   MEASURED: the fn-body reference to the module's own `pub data` resolves at the
   descriptor call site and links; and the name-list import of a `pub comptime fn` IS
   a real lowering edge — `ensure(1 == 0)` in the generated module fails the build
   with the seam in place and builds GREEN with an unchanged CRC without it.

   **NO `map.toml` ORDER ROW WAS AUTHORED, deliberately.** The `order` check keys on
   a section's HEAD LABEL (`native.rs:3194-3203`, lowest-offset label) and this
   block's head is CONTENT-DERIVED — in the slice-5 fixture build it was
   `EditorDeform_sine_8_32`, a deduped table name that changes with whichever scenes
   exist. Until Aurora authors the first scene the section emits ZERO bytes, so a row
   would be inert AND unverifiable (this tree's vacuous-gate defect in a new costume).
   The day it emits, sigil stops the build and names the label:
   `[map.order-undeclared] byte-emitting section '<head>' is not in the declared
   'order'`. `map.toml` carries a reserved-slot COMMENT at the intended position
   (immediately after `DeformTable_Zero`, so the object-bank budget cursor keeps its
   meaning) instead of a guess. **The first parcel that lands an editor scene adds the
   row there** — and that is also the parcel that first verifies the placement.

   **Slice-5 shipped surface:** `tools/effects_gen.py` gains `load_act_scene_ref` /
   `load_section_scene_refs` (contract §2.2, missing-vs-unreadable split intact,
   numeric `sceneRef` REFUSED rather than coerced), `render_module`, `emit`, and a
   `check` drift gate run on every canonical build;
   `games/sonic4/data/generated/ojz/act1/effects_scenes.emp` is the committed
   artifact; `tools/effects_seam_gate.py` reads the build's own `.lst` for the
   module's `pub equ` witnesses (presence ⇒ lowered ⇒ reached) and is wired into
   `build.sh` beside `s4budget`; `regenerate-level.sh` bakes the module
   unconditionally. `scene_registry.emp`'s `SceneCfg{1,2,4,5}` + `lower{1,2,4,5}` are
   now `pub` so the generated module lowers through the ONE authority rather than a
   second copy — a band count with no shape there is a generator refusal naming that
   file. **Byte-neutral in the shipping state** (all four canonical shapes unchanged);
   the content path is proven by a temporary fixture, green at crc `1499f79c`.

   **CLOSED 2026-08-22, `parcel/band-count-range` — the shape set was a CEILING read as
   a LIST.** `SceneCfg{1,2,4,5}` was not a decision; it is exactly what the twenty
   hand-authored scenes happened to need. The engine's declared maximum is
   `MAX_PARALLAX_BANDS = 8` (`engine/system/constants.emp`, pinned at
   `engine/level/scene_dsl.emp:54`, enforced by `scene()`), the writer schema mirrors it
   as `layers minItems 1 / maxItems 8`, and Aurora computes its Add-layer cap from that
   schema at load — so 3, 6, 7 and 8 were *exactly as reachable* as 4 and 5. Aurora's
   first writer-originated scene has eight layers and was refused. `SceneCfg{3,6,7,8}` +
   `lower{3,6,7,8}` now ship (all four, so no arbitrary remainder re-arms the defect with
   the discovering artifact spent), and coverage stopped being a list:
   `tools/test_scene_band_shape_coverage.py` derives the required set from
   `MAX_PARALLAX_BANDS` on every run and names any count whose pair is missing — move the
   constant to 10 and it reports 9 and 10 rather than going stale (measured red-first).
   It runs in `build.sh`'s build-fatal `pytest tools` lane. Byte-identical across all four
   canonical shapes (crc32 `060401E4` / `0DBAA80F` / `C708B114` / `DEC88CC1`).

   Two things found on the way, both booked here rather than left implicit: (a)
   `tools/effects_gen.py` carried an **unpinned** `MAX_PARALLAX_BANDS = 8` mirror that
   nothing compared to the engine — now pinned by the same gate, and
   `LOWERABLE_BAND_COUNTS` is `range(1, MAX+1)` not a literal. (b) An **anchored** 8-band
   scene is still correctly refused (`scene_dsl.emp:1062` — an anchor splits a layer at
   runtime, needing `count+1` shadow entries, and `Parallax_Shadow_Bands` is sized for
   eight). That is a real shadow-view capacity limit, NOT a missing `SceneCfg9`; the gate
   asserts no declared shape exceeds the ceiling so it cannot be "fixed" that way. If a
   scene genuinely needs eight bands *plus* an anchor, the parcel is widening
   `Parallax_Shadow_Bands`, and that is a RAM decision — not a registry one.

   **PARTLY CLOSED 2026-08-24 — READ THIS BEFORE THE PARAGRAPH BELOW, WHICH IS PRESERVED AS
   WRITTEN AND IS NOW STALE IN ITS FIRST SENTENCE.** The `v_factor` half is CLOSED on both
   sides and the cross-repo decision it asked for was taken: **the schema moved, the engine did
   not.** empyrean `a32bcb0` (2026-08-23, "apply CR-1") retyped `v_factor` and `v_factor_fg`
   from `$ref: #/$defs/factor` to `{"type": "integer", "minimum": 0, "maximum": 15}` — verified
   firsthand at empyrean `origin/main` on 2026-08-24, reading the committed revision, not the
   sibling path. aeon `da43a036` then added the matching engine guard. Two derivations, two
   enumeration parameters (their schema declaration; our read of the sole consumer's `asr.w`),
   same span.

   **FAIRNESS NOTE, recorded because the tempting version of this story is wrong and this lane
   nearly told it to a peer:** the schema's current prose ("do not spell this field with a
   `FACTOR_*` name") was added BY `a32bcb0`, i.e. as part of the fix. It did not predate the
   defect. At `0ea8734`, when Aurora's writer default was authored, `v_factor` was `$ref:
   factor` and **`"FACTOR_0"` was schema-LEGAL**. Aurora was not ignoring a warning; the
   contract was wrong and its owner corrected it. Any retelling that makes the writer the
   careless party is a `git log -S` away from being refuted.

   **STILL OPEN — the SAME defect on the neighbouring fields, and the parcel that closed
   `v_factor` closed exactly one of the two.** `v_center` and `v_offset` are STILL plain
   `{"type": "integer"}` in the schema (verified at `origin/main`, same read) while
   `sc_v_center` / `sc_v_offset` are `u16`, and **there is no `ensure` on either** — grep
   `scene_dsl.emp` for an `ensure` naming them and you get nothing. So `v_offset: -8` remains
   schema-valid, passes the new `_render_int` shape check (it IS an integer), and dies at
   `[emit.out-of-range] -8 does not fit u16`. **A partial closure that reads as a total one is
   the hazard here:** the booking below says "`v_factor`/`v_offset` range check" as one unit,
   and only the first word of that pair is done. Same shape as the negative generator parameter
   booked at the end of this file — negatives pass shape everywhere and are bounded nowhere.

   > **CLOSED 2026-08-25 — the VOFFSET half, both fields, both halves, on
   > `parcel/voffset-bounds`.** Zero-byte in all four shapes (every shipped scene authors
   > `v_center` 0 or 512 and `v_offset` 0, and a passing `ensure` emits nothing).
   >
   > - **THE BOUND IS A PROPERTY OF THE ENGINE MATH, and the two fields are NOT the same
   >   kind of number.** `v_offset` is **SIGNED**: its only consumers are `add.w
   >   pcfg_v_offset(a0), d0` (unlocked arm) and `move.w pcfg_v_offset(a0), d2` (`.v_locked`),
   >   both landing in `Parallax_Current_Vscroll_BG`, which the transition lerp treats with
   >   `sub.w`/`asr.w` — signed-word arithmetic end to end, so `-8` was a legal value refused
   >   by the EMITTER for a field that was typed wrong. Bound **-32768 .. 32767**.
   >   `Scene.sc_v_offset` is now an `i16` (the file's existing signed-bridge type) and
   >   `scene_hdr()` two's-complement encodes it into the still-`u16` `pcfg_v_offset`
   >   (`-8` -> `$FFF8`, measured). `v_center` is a **WORLD Y**: `sub.w` from a camera Y that
   >   `clamp_camera_axis_reg` pins to `max(0, min(y, extent - screen))` with every act
   >   descriptor asserting `extent <= $8000` — the same derivation `layer()` applies to
   >   `world_y`. Bound **0 .. $7FFF**; $8000..$FFFF would fit the `u16` and read as a
   >   negative Y through the `sub.w`. Deliberately NOT tightened to `SCENE_ACT_SPAN_Y`.
   > - **ENGINE** — two `ensure`s on `scene()` (`engine/level/scene_dsl.emp`), literals
   >   inlined per the file's pin convention. Red-first: with both stashed out
   >   `poison_scene_vbounds_range.emp` builds rc 0 / zero `[Error]`; with them in, exactly 4
   >   (`games/sonic4/test/poison/poison_scene_vbounds_range.emp`, four rows in
   >   `tools/emp_expect_fail.py`, run build-fatally by `build.sh`'s expect-fail lane).
   > - **GENERATOR** — `tools/effects_gen.py` forwards the signed literal verbatim (that IS
   >   the correct encoding now that `scene()` takes the signed int); it grew NO range check,
   >   per the SHAPE/VALUE line the VFACTOR parcel drew one paragraph up and
   >   `test_real_integers_pass_INCLUDING_ones_the_constructor_will_reject` codifies.
   >   `tools/test_effects_gen.py::TestSignedVerticalScalarsAreForwardedVerbatim` pins the
   >   sign path, both word ends, one-past-each-end and the shipped values (build.sh's pytest
   >   lane, build-fatal).
   > - **SCHEMA (empyrean, NOT edited here — the hub moves it, as it did for `v_factor` at
   >   `a32bcb0`):** at `origin/main` `52d5bc52` (read 2026-08-25) `v_center`/`v_offset` are
   >   still `{"type": "integer", "default": 0}`. Recommended: `v_offset` -> `"minimum":
   >   -32768, "maximum": 32767`; `v_center` -> `"minimum": 0, "maximum": 32767`, each with a
   >   one-line description naming the engine math above.

   **ORIGINAL BOOKING, PRESERVED — its first sentence describes empyrean at `0ea8734` and was
   true when written:** `v_factor` is typed differently in
   the two repos. The empyrean schema declares `"v_factor": {"$ref": "#/$defs/factor"}`,
   i.e. the same type as a layer's horizontal `fa`/`fb`. The engine's `sc_v_factor` is a
   `u8` **vertical shift**, `0..15`, `15` = lock
   (`Vscroll_BG = ((camY - v_center) >> v_factor) + v_offset`); every shipped scene spells
   it `3` or `15`. Aurora's fixture authored `"FACTOR_3_4"`, which folds to `288`, and sigil
   reports `shift amount out of range: 288` once per layer plus
   `[emit.out-of-range] 288 does not fit u8`. `effects_gen.py` passes it through because it
   validates SHAPE and the shape is schema-legal. Alongside it: `v_offset: -8` fails
   `[emit.out-of-range] -8 does not fit u16` while the schema says plain `"integer"`.
   **A scene can therefore be schema-valid, pass every generator check, and be
   unbuildable** — which is a wave-1 contract-golden gap, not a band-count one. Both repos
   are internally consistent, so this needs a cross-repo decision about which side moves
   before an aeon-side `v_factor`/`v_offset` range check is written (writing one first
   would harden the wrong side if the schema is what is wrong). Detail and the third,
   genuinely-authored-value diagnostic are in
   `docs/superpowers/2026-08-22-aeon-overseer-handoff-2.md`, WRITER-VALUE MISMATCH.

   **Also re-confirmed, not changed:** the `map.toml` RESERVED SLOT comment (lines 106-117)
   is exactly right. The moment a real editor scene emits, sigil fails with
   `[map.order-undeclared] byte-emitting section EditorSceneBinding_OJZ_Act1_Default is not
   in the declared order`, naming the head label to write. Measured in the fixture build;
   the row is still deliberately absent because the section still emits zero bytes.
2. **First authored animated act** — discharges `inject_editor_bg.py`'s FORMAT-FAITHFUL
   BUT NOT BYTE-PROVEN animated arm (`inject_editor_bg.py:121-124`); that parcel runs
   `tools/effects_gates.py` and pastes totals into merge evidence even though it touches
   only generated data (design §8).
3. **Aurora parcels** are Aurora's lane (their ROADMAP §5.2), cut against BOTH repo SHAs
   once the doc branches land; not tracked here beyond the contract.
4. **Wave 2 (raster preset composition)** is sequenced after wave 1's contract golden is
   green (ruling Q1); its writer surface is reserved-by-name-only in the empyrean doc §7.
   Wave 2 — not wave 1 — is the recorded revival trigger for the banked EFFECTS-TAIL
   overlap parcel below (`docs/superpowers/specs/2026-08-17-effects-tail-design-v3.md`
   r3.1; see its own entry, which this booking references and does not disturb).

### TWO RESERVATION CEILINGS LEFT STANDING BY THE P3 TASK 13 RE-TAKE — booked 2026-08-22

Task 13 re-took every row measured against the pre-P3 walker (fixture model promoted,
`[engine_reservation]` refreshed on both camera states, axis 1 re-derived 23894 → 24257).
Two rows were verified and deliberately NOT re-derived; both err in the SAFE
(over-reserved) direction and each names its unlock condition:

1. **Axis-2 reservation (2160 B) — a ceiling, not a derivation.** The tip re-take
   reproduced every input (whole-region 3056 B incl. drain residue; live idle queue
   984 B, of which 896 B is the scene's own forcer, leaving 88 B non-scene live). 88 B
   would under-reserve for art streaming, whose 1152 B page transfer the scanline-220
   scan only ever sees as residue — page DMAs are enqueued and drained inside VBlank,
   invisible to any active-display scan instant. **Unlock: an instrument that takes the
   per-frame UNION of LIVE enqueues across a streaming-active window** (e.g. a
   cursor-delta hook at drain time, or a queue-write watchpoint sweep), then
   reservation = max over states of (live union − the scene's 896 B). Consumers:
   `SB_AXIS2_RESERVATION` (scene_dsl.emp), `[scene_budget].axis2_reservation_bytes`.
2. **Axis-4b reservation (43405) — derived from the SUPERSEDED 2026-08-19 idle rows**
   (35125 + 8280); the 2026-08-22 components give 29472 + 8277 = 37749. Not re-derived
   in T13 because the constant lives in `raster_dsl.emp` (`RASTER_HINT_RESERVATION_CYC`)
   with its own guard set and the plan scoped T13's derivation step to axis 1; the stale
   value over-reserves by 5656 on an axis the 4a density guard already bounds below
   budget (T11's finding: the hint-total ensure is vacuous against any accepted
   program). **Unlock: trivial — any parcel touching raster_dsl's budget constants
   re-derives it from the current `[engine_reservation]` idle rows** and re-checks the
   4a-bounds argument still holds at the looser budget.

### 0. STREAMING ROOT-CAUSE ARC — **OPEN (owner-ruled 2026-08-19, diagnosis DONE)**
The next major engine arc. Sustained max-diagonal runs the logic at 30 Hz, not 60: a tick costs
**190,931 cycles of work against a 128,000-cycle frame**, so `frames_per_tick = ceil(1.49) = 2`.
`Tile_Cache_Fill` is 106,138 of it.

**The diagnosis parcel is complete and changed no engine code** —
`docs/benchmarks/streaming/CHOKE-DIAGNOSIS.md` (branch `diag/streaming-choke`,
`tools/streaming_choke_probe.py`). **Read it before planning any fix.** Headlines:
- **NOT a page-tier famine.** OJZ act 1's pool is 10 pages against `PAGE_FRAMES` = 15, so
  `PageIn_Fully_Resident` is true and the whole §9.7 residency tier — eviction, demand
  requests, the ZX0R bookmark — is **inert** (every counter reads 0). The known `STRESS_EVICT`
  famine is fixture-only and is not this. The choke is **entirely block-tier**.
- Two mechanisms account for it: the **per-word residency patch** (46,234 cyc/tick, 24% of the
  whole tick, doing dormant work) and the **block prefetch's 3.06 dead speculations per tick**
  (staged, then round-robin-evicted before use — proved by removing the prefetch: decompresses
  4.53 → 1.47/tick with **no** rise in demand).
- A throwaway build neutralising both runs max-diagonal at **1.107 frames/tick**. Neither lever
  alone crosses the line.
- **Raising `BLOCK_STAGE_SLOTS` is a measured null** (16 → 20 moves work/tick by +0.05%; 24 does
  not fit in RAM). Do not re-derive it. The lever is policy, not capacity. **Caveat added by F4
  (2026-08-20):** that null was measured against the LINEAR probe, whose cost grew with the slot
  count and ate the saving. F4 removed that term, so the capacity arithmetic is different now —
  if anyone wants to revisit it, RE-DERIVE rather than inherit. The RAM ceiling (24 slots do not
  fit) is unaffected and still binds.
- Ranked fixes F1–F6 with measured savings are in §8 of the packet. **F1, F2, F4 and F5 are
  CLOSED (below); F6 remains PARKED for an owner ruling** and must not be started before one.
- **The arc's remaining distance, 2026-08-20: 6,521 cycles.** Sustained max-diagonal now runs
  at **1.240 frames/tick** on `work/tick` 134,521 against the 128,000-cycle frame. The four
  fixes took it from 190,931 / 2.067. What is left is F6 (margins, estimated ~13,000 cyc/tick,
  and the only ranked streaming item still open) plus, off the streaming path, the raster
  arm-rewrite rider (1,152 cyc/frame, §5 of this file). **A NEW row is now the biggest single
  non-fill cost at max-diagonal: `Parallax_Update` at 26,159 cyc/tick**, against
  `Tile_Cache_Fill`'s 64,991 — and §3 of this file already carries two untaken parallax
  levers whose blockers are discharged.
- **Instrument defect found:** old oracle's per-routine rows lose 20.6% of the frame when a
  logic tick spans a VBlank (they close to 1–2% when it does not). Packet §7. The instrument
  asks for oracle-next are packet §9, sorted into (a) satisfied by their in-flight profiler v1,
  (b) composable today via mclk-stamped watch hits, (c) three genuinely new asks.
- **The arc CLOSED 2026-08-20** — F2 + the parallax-unroll coda took it to **1.192 frames/tick
  / work/tick 123,016** (`docs/benchmarks/streaming/ARC-CLOSEOUT.md`), superseding the
  1.240/134,521 remaining-distance bullet above. **And the corpus A/B (same day, oracle
  `docs/2026-08-20-profiler-corpus-ab.md`) then downgraded the absolute margin to a
  hypothesis**: the old instrument's five top rows account for only 78.45% of a maxdiag
  frame, so every `work/tick` figure in this block is instrument-relative; the f/t figures
  (direct tick counts) stand. See the PROBE-MIGRATION entry below.
- **The retake RAN the same day and the hypothesis SURVIVES**
  (`docs/benchmarks/streaming/TICK-VARIANCE.md`): honest work/tick **112,897 — 15,103 UNDER
  the 128,000 line**, three times the claimed margin, spread 0 over 3 boots. The
  attribution hole never entered that figure (the close-out's formula built on the frame
  TOTAL, not on a sum of rows). **The variance question is answered too:** 3 of 26 whole
  ticks miss the frame, all three carrying an `S4LZ_DecompressDict` burst (25.7-48.9k cyc)
  on the block-COLUMN crossing — one per 128 px, every 8 ticks; the row crossings are free
  ~~because their blocks are already staged~~ **because their blocks decode as the EMPTY
  form — the settling experiment (2026-08-21, `STAGING-LIFETIME.md`,
  `tools/staging_lifetime_timeline.py` rewritten onto the new profiler ritual) REFUTED
  the staged-carryover hypothesis: no crossing block is ever pre-staged at maxdiag, and
  the column side pays because its blocks are COMPRESSED while the F2a latch suppresses
  the one mechanism (`cs` col-scan) that measurably covers column crossings at `right`.
  The smoothing parcel's design inputs (mechanism, residency and cycle budgets) are in
  that doc's §5.** The f/t figures are the one thing that did NOT
  reproduce: 1.069 here vs 1.192 there, on byte-identical ROM bytes.
- **The smoothing parcel RAN 2026-08-22 and is BLOCKED at whole-call granularity**
  (`docs/benchmarks/streaming/BURST-SMOOTHING.md`, branch `feat/burst-smoothing`): five
  measured whole-call schedules (k=1 spread / drift-ordered walk / compressed-only
  claims / recovery-tick batches of 3 and 2) all produced 5-8 spike ticks against the
  baseline's 3 — §5's residency (~0.4 tick margin) and cycle (+15.3k crosses 128,000)
  budgets are a JOINT exclusion for whole calls. Permanent yields: a covered column
  crossing is PROVEN not to lag (live, v4 crossing 221); `right`/`down` ledgers stay
  byte-identical under the classifier family; the correct claim set is "imminent head
  column's COMPRESSED blocks, arriving-rows first" (substrate committed in that
  branch's history, `66cc7635` + `096d934d`).
  **NEXT LEVER — the booked escalation: a resumable (bookmarked) `S4LZ_DecompressDict`
  for the lookahead path, ZX0R/§9.7 style** — one claim whose 10-15k decode spreads at
  ~4-6k/tick over the cadence's six quiet ticks, satisfying both budgets at once.
  engine/compression parcel; the tile-cache side plugs into the committed substrate.

**PROBE MIGRATION to the validated oracle profiler — booked 2026-08-20, condition MET.**
The corpus A/B passed (oracle main `8d10cc5`, evidence doc with CRC per row; reference row
exact to the cycle, spread 0 whole-reply). The standing "profiler consumers stay on
oracle-old" condition is DISCHARGED — new cycle work should use the new oracle's profiler
(`cyclesSelf`/`stallCycles`, honest under preemption, hint/vint split). What that costs us:
every profiler-consuming probe hardcodes `oracle-old/linux-port/harness` and the old row
shape (`parallax_cost_probe.py`, `engine_baseline_probe.py`, `raster_cost_probe.py`,
`streaming_choke_probe.py`, + kin) — port them harness+row-shape+caveats (the per-frame
30/31 division and hint-conflation caveats DISSOLVE on the new instrument; delete, don't
carry).

- **FIRST LEG LANDED 2026-08-20 (`measure/tick-variance`).** `tools/tick_variance_probe.py`
  is the first probe on the new profiler and took the first workload — **the tick-variance
  spike hunt + the honest work/tick retake, one run, both answered**
  (`docs/benchmarks/streaming/TICK-VARIANCE.md`). Its control re-measures the A/B's pinned
  reference row **on the A/B's own ROM** (crc `d22dda85`, recovered byte-identically from
  sigil `7b46f075`'s golden — **no rebuild needed, and that recipe is reusable**) and
  refuses to measure if it misses. **Reusable pieces for the remaining ports:** the
  `Server` class (fresh `oracle-aether` per boot, `--symbols`, per-PID socket), the
  `identity()` completeness check derived from the reply's own keys, the `sample()` note
  that `run_frames(N)` yields `frameCount == N−1`, and the **prefix-differencing ladder**
  that recovers per-frame per-routine rows (`perFrame[]` carries whole-frame totals only).
- **Two instrument findings the next port MUST carry.** (1) `vintCycles` does NOT partition
  tick-frames from lag-frames in general — it did at the corpus state and does NOT at
  current master's maxdiag; read `Logic_Tick` at every frame boundary instead. (2)
  Differencing INCLUSIVE `cyclesTotal` is not a per-frame quantity (a straddling
  invocation's cost arrives in a lump: `GameState_OJZScroll_Update` reads 3,836 in one
  frame and 149,104 — more than a whole frame — in the next). Per-frame work must be built
  from `cyclesSelf`.
  **(2) IS ROOT-CAUSED, GENERALISES TO INTERRUPT BUCKETS, AND ITS REMEDY HAS NO FIELD ON THE
  RING — 2026-08-23.** Cross-checked with the oracle lane (their `Q-PROF-STRADDLE`, reasoned
  from source; our 149,104 lump, measured on a streaming workload — different enumeration
  parameters, so corroboration rather than echo, protocol bar 19). **Verified firsthand at
  oracle `origin/main` `4f0bedd5`**, by symbol not coordinate:
  - **One mechanism, and it is kind-agnostic.** `Profiler::checkpoint` in
    `crates/oracle-core/src/profiler.rs` picks the row (`FrameKind::Routine` → `pending`,
    `FrameKind::Interrupt` → `pending_buckets`) and then runs the *same* three accumulates
    for both. A parent's inclusive only acquires a callee's time when the callee pops
    (`parent.child_cycles += frame.inclusive()`), so any boundary checkpoint taken with a
    callee in flight gives that frame nothing and lands the whole lifetime in the frame of
    return. The module doc says so outright: inclusive *"distribution across frames lags
    where a callee straddles a boundary; `self_cycles` has no such lag"*.
  - ~~**So `cyclesSelf` really is sound for both kinds** — the fix above is right in principle.~~
    **HALF-REFUTED AND THE ASK IS WITHDRAWN — 2026-08-24. It is sound for ROUTINES and FALSE
    FOR INTERRUPT BUCKETS.** Found by the oracle lane against our own registered ask, and
    verified firsthand here at oracle `origin/main` before agreeing. **The acknowledge arms a
    routine frame for the handler's own entry address, so a bucket's `self_cycles` is the
    EXCEPTION ENTRY ALONE** and every cycle its handler retires is already child time. It is
    not "the bucket's cost with callees subtracted" — it is a different quantity, and a
    `vintSelfCycles` column would have shipped us an exact, cheap, useless number.
    Pinned by a test that **predates the finding by five days**, so it is not reasoning built
    to fit a conclusion — `a_nested_hint_inside_a_vint_charges_the_inner_bucket_alone`, first
    appearing in oracle `d1a2137` (2026-08-19, profiler slice 3), body read here at
    `origin/main`: `hint.self_cycles == STEP_CYCLES` against `hint.cycles == 3 * STEP_CYCLES`.
    **Our finding (2) itself STANDS** — the 149,104 lump is a *routine*
    (`GameState_OJZScroll_Update`), and for a routine `self_cycles` really is cost-minus-callees.
    Only the generalisation *to buckets* was wrong.
    **Our error class, and it is the reusable part: we adopted a peer's documented rule across a
    boundary it never crossed.** Their §3 says "read `cyclesSelf` for a lag-free figure"; that
    advice is about the AGGREGATE and does not transfer to a bucket. Nothing in the sentence
    marks its own scope, we carried it into a cross-repo ask, and **the premise arrived from the
    same lane that later refuted it** — a relayed premise inherits no more scrutiny than the
    claim it supports. Same family as protocol bar 16: the rule's *name* was right and its
    *reach* was never checked.
    **FIXED AT SOURCE, and the description above is therefore DATED — oracle `566413a`,
    verified here as reachable at their `origin/main` and read firsthand.** Their module doc now
    marks the scope at the sentence itself: routine rows keep the advice, buckets are flagged as
    the entry alone. **So do not go looking for the unscoped sentence — it no longer exists**, and
    finding the scoped one is not evidence this booking was wrong.
    *One correction to our own wording while dating it, because this whole exchange was about
    precision: we wrote that the rule "is about the AGGREGATE". It is not — it is scoped by ROW
    KIND (routine vs interrupt bucket), and both kinds appear in the aggregate. Our axis was
    wrong even though our conclusion was right, which is the cheaper half of the same mistake.*
  - **⚠ BUT THE RING CANNOT EXPRESS IT.** The `perFrame[]` wire row is exactly five keys —
    `frame`, `cycles`, `stallCycles`, `hintCycles`, `vintCycles` (`oracle-aether`'s
    `engine.rs`, the `per_frame_armed()` block). There is **no `vintSelfCycles`, no
    `hintSelfCycles`, and no per-routine breakdown on the ring at all.** Both bucket figures
    are inclusive-only. A porter who reads "use `cyclesSelf`", goes to `perFrame[]`, and
    finds no such field will either fall back to the inclusive figure or invent a workaround
    — **the permissive-stale failure this repo keeps rediscovering, one layer down.**
  - ~~**Sorted per the protocol's gap rule:** aggregate bucket self is *composable today*
    (`interrupts[].cyclesSelfTotal`); **per-frame bucket self is genuinely-new and is a NAMED
    ASK to the oracle lane**, not something a port works around. Do not port an
    interrupt-bucket per-frame consumer until the field exists or the ask is refused.~~
    **`PROF-RING-SELF` IS WITHDRAWN BY THIS LANE, 2026-08-24** — as the consumer that filed it,
    on the refutation above. No field is owed. **What we actually wanted was delivered instead**,
    by oracle's straddle fix: `perFrame[].hintCycles`/`vintCycles` are now cut from a per-frame
    accumulator charged as the cycles retire, so a straddling handler's span is charged to the
    frames it RAN in rather than the frame it returned in. The two properties that make it the
    quantity we asked for, read firsthand off the fix's own source at oracle `51143a5` (merge)
    / `4111c88` (code): **`hint_cycles + vint_cycles <= cycles` always**, and **the rows still
    sum to the undivided bucket totals exactly** — so the ring carries the WHOLE handler cost,
    distributed, not the entry. It needed no wire change and no new field, which is why the ask
    was not merely unnecessary but pointed away from the fix.
    **Note the shape of this outcome for the next gap we sort:** we classified it
    *genuinely-new* when it was really *satisfied-by-their-in-flight-work* — and genuinely-new is
    the one bucket of the protocol's sort that generates work across the fence. **A gap sorted
    from the WIRE SCHEMA (is there a field?) rather than from the QUANTITY (what do we need
    measured?) lands in that bucket by construction**, because a schema can only ever answer
    whether a name is present.
  - **Displacement is CONDITIONAL, which is what a witness test must exercise.** Boundary
    checkpoints run for every live frame including interrupt frames, so an in-flight handler
    flushes its own cycles on time; what a frame misses is only time held inside a callee
    open across the boundary. **A handler whose `jsr`s all return before the boundary shows
    no displacement at all** — so the obvious test passes for the wrong reason. The witness
    must be: `iack` opens the bucket → **the handler calls a routine** → the boundary lands
    with that callee still open → the callee returns and the `RTE` arrives next frame. Step 2
    is load-bearing and was absent from the first draft of the test (oracle's own correction
    against themselves).
    **DISCHARGED 2026-08-24 — the witness exists and the defect is FIXED.** Oracle landed two
    red-first boundary-straddling tests (`68461a7`) and the fix (`4111c88`), merged at
    `51143a5`; the red output is the arithmetic proof, a frame reporting `vint_cycles: 40`
    against its own `cycles: 30` — **an interrupt costing more than the frame containing it.**
    **So the hold on our three cost probes has its condition met** —
    `tools/raster_cost_probe.py`, `tools/engine_baseline_probe.py`,
    `tools/streaming_choke_probe.py` may now migrate off the legacy harness when a parcel wants
    them to. That is a permission, not a queue item; nothing on this lane waits on it, and the
    scope note in `OVERSEER.md` (this held THREE NAMED PROBES, never "aeon's profiler
    migration") still governs how it is relayed.
  - Oracle's write-up: `docs/2026-08-23-prof-straddle-mechanism.md` in their repo. Their
    analysis is a **source read — no cargo run, no machine** — and they say so; the only
    measured half of this is ours.
  - **The `suppressed` sibling caveat, RAISED BY ORACLE AND ALREADY CHECKED NEGATIVE HERE.**
    A bucket already open when the sample opened is `suppressed`, and its self cycles go to
    `unattributedCycles` rather than to the bucket row — so a sample armed mid-handler
    under-reports its first frames, on a future `vintSelfCycles` exactly as on `vintCycles`.
    **`tools/tick_variance_probe.py` already carries the discriminator as a hard identity
    gate** (`sampleCycles - (self + unattributedCycles)` must close at every prefix rung),
    and it measures **`unattributedCycles == 0` at every rung** at the states it samples —
    so the case is detected, not merely absent. Two consequences: the caveat does not bite
    the one probe we have on the new profiler, and **every remaining port MUST carry the
    `unattributedCycles == 0` ASSERTION — not merely "the identity check".** Zero at the
    states measured is not a proof for arbitrary arming.
    **⚠ THE DISTINCTION IS THE WHOLE GUARD, and an earlier draft of this booking got it
    wrong (corrected 2026-08-23, caught by the oracle lane).** A suppressed bucket
    **conserves** cycles: `checkpoint` does `pending_unattributed += d_self; return`, so the
    time lands in `unattributedCycles` and **the identity still closes with that term
    arbitrarily large.** Closure alone is satisfied by precisely the case being guarded
    against. A porter who copies "carries the identity check" and keeps only the closure has
    kept the gate's shape and discarded the half that fires — the vacuous-gate failure this
    repo has the most scar tissue about, arriving through a correctly-described gate.
    **The identity is a LOSS detector, not a correctness proof:** it catches loss-shaped
    defects and would not catch a mis-keying one where cycles are conserved but land on the
    wrong row, and the suppressed case is conserved-but-diverted.
- **STILL ON `oracle-old`, in rough order of next use:** `streaming_choke_probe.py`
  (the fill's callee decomposition — the biggest consumer), `engine_baseline_probe.py`
  (the §1 baselines every budget denominator cites), `parallax_cost_probe.py` (needs the
  17-fixture installer, which is a second harness — see rider (a)),
  `raster_cost_probe.py` (F0-F8 fixture encoder, same shape of problem). Porting the two
  fixture-installing probes is strictly larger than porting the two reading probes.
- **An unresolved cross-instrument delta, booked by the first leg:** on byte-identical ROM
  bytes (crc `5be03175`) the old emulator runs **26** logic ticks per 31 frames at maxdiag
  where the new one runs **29** (1.192 vs 1.069 f/t; idle 30 vs 31); the two agree exactly
  at the corpus-era state (15 ticks). The divergence appears only where the tick sits close
  to the frame boundary. Not resolved, not smoothed — TICK-VARIANCE §1.2.

Riders from the A/B, THEIRS+OURS: (a) the 17
walker fixtures were NOT re-driven — the two-regime curve is neither confirmed nor refuted
(measurable leg agrees to 0.17%/invocation; out-of-sample gap +4.7% on a per-invocation
denominator, vs WALKER-MODEL §6's +1.1% per-frame figure); (b) five ungated short routines
disagree 11–40%, UNEXPLAINED, settling experiment = paired event-level trace on both
instruments (their §11.5); (c) already booked into rows: dense −242 anomaly RESOLVED
(instrument defect, measured == model), DMA-stall row now measurable (~2,200 cyc/frame all
VBlank drain vs 2,745.5 derived ceiling), ENGINE-BASELINE §1's byte-identical claim
corrected (priming arm words track camera).

**Fix F1 — collapse the per-word residency patch — ✅ CLOSED 2026-08-19**
(`perf/resident-patch-collapse`). The arc's biggest single win. The copy-site patch runs
translated every nametable word global→physical through `Page_Table` and maintained a
ref/unref pair, servicing an eviction that cannot occur while `PageIn_Fully_Resident` holds.
- **The ruled shape hit a contradiction and it is worth knowing.** The ruling was "RAM-rewrite
  at act load: compose global→PHYSICAL into the section local maps in RAM". **The section
  local maps are ROM** — `embed()`ed blobs reached through `Act.act_sec_local_maps`, read
  straight by the patch runs. A RAM copy was priced and rejected: OJZ act 1's nine maps are
  3,230 B against 3,622 B free in `lower_ram`, i.e. it fits this act and silently ceilings
  the next one.
- **What shipped is the same collapsed loop with the composition pass deleted.** Under the
  latch, `PageCache_Init`'s free list (`0→1→…`) + `Level_LoadArt`'s in-order bulk enqueue +
  page-in's single-slot in-order completion make `Page_Table` the IDENTITY, so
  `frame<<6 | (global&63) == global` and the map's global value already IS the physical index.
  `Level_LoadArt` **verifies** the identity after the pool lands (never assumes it) and
  latches `PageCache_Direct_Map`; the runs dispatch per RUN, and the fallback arm is the
  pre-F1 loop byte-for-byte over the pristine ROM maps. Zero ROM format change, zero RAM
  layout change (the latch consumes an existing pad byte at `$FFB833`).
- **Measured** (probe `--repeat 3`, spread 0.000, 3 boots): `right` fill 43,395 → **33,646**
  cyc/tick (−22.5%), `_Col` 183.1 → **103.3** cyc per patched word; `down` fill
  41,067 → **34,218** (−16.7%), `_Seq` 136.2 → **88.5** cyc/word; `maxdiag` work/tick
  190,941 → **174,437** (−16,504). ~84%/78% of throwaway C's floor, the residual being the
  pool-bounds assert the shipped loop KEEPS (in a stricter, cheaper form) and C dropped.
- **The RELEASE shape's saving is smaller and it is the one to quote for shipping.** The
  DEBUG numbers overstate it: the pre-F1 general loop carried two DEBUG asserts release never
  paid, which the collapsed loop deletes along with the block they sat in. Measured on
  `s4.bin` at `down`: `_Seq` 112.7 → **86.6** cyc/word (−23.2%, vs −35.0% in DEBUG), fill
  36,880 → **32,707** (−11.3%), work/tick 92,937 → **88,762**. The two shapes' F1 costs agree
  (88.5 vs 86.6); it is the BASELINES that differ. **`right` is NOT reproducible in release on
  this probe** — the leader falls (dx 320 dy 124 vs dx 496 dy 0), so it is a diagonal state
  there; calibrating one is an instrument job.
- **`maxdiag` frames/tick stays 2.067, as §5 predicted.** F2 is the other half; 46,437 cycles
  remain to the 128,000 line. Read F1 off `right`/`down`, where the instrument closes (§7):
  F1's own per-word deltas predict 17,208 cyc/tick and `work/tick` fell 16,504, closing to 4%.
- **Value identity is the gate and it held:** full byte compare of `Tile_Cache_Nametable` AND
  `Tile_Cache_Collision` against the pre-parcel ROM at all four pinned camera states, camera
  position verified equal at the sample point. Exact decompress counts unchanged everywhere.
- **`PageCache_Audit` was made regime-aware rather than disabled** (throwaway C had to disable
  it). Under the latch the refcount comparison is replaced by: all refcounts zero (the
  variants-got-mixed detector), no nametable word referencing an unassigned frame (the
  no-dangling-index property the refcounts protected), and `Page_Table` still the identity
  (the collapsed loop's premise). Bijectivity / candidate-flag / orphan checks untouched.
- **Trap the whole arc inherits — the four AB raster scenes cannot return ALL EQUAL against a
  tick-rate change.** `ab_runner` reports DIFFERENCES on 3 of 4, and running the BASELINE ROM
  against ITSELF at settle 180 vs 181 reproduces the SAME difference set scene for scene
  (`vram` + `active_buf`, or `vram` + `dense_state`, or `active_buf` alone), with `active_buf`
  returning to EQUAL at 182 — a double-buffer parity alternation. Under both F1 and the pure
  phase shift, `Raster_Buf_A`/`_B`, CRAM, VSRAM and regs are EQUAL. The discriminating content
  check is `effects_gates`' own four `scene:*` determinism + shape gates, which PASS on the F1
  ROM with the exact pinned words. **F2 will hit this same wall; run the ±1-frame control.**
- **Trap for the next parcel:** at the canonical `idle` settle 180 the DEBUG audit fires and
  F1 reads 1.069 frames/tick against 1.033 — NOT a regression. Every row is equal or lower and
  `PageCache_Audit` is 3,688 cyc/frame in both; F1 has simply completed one more logic tick by
  frame 180, so the ~114,000-cycle one-shot lands at a different phase. At settles where the
  audit does not fire (120/150/210/240) base and F1 are identical to ≤11 cycles. **Read the
  `idle` null off a non-firing settle.**

**Fix F2 — the block prefetch's speculation lands instead of dying — ✅ CLOSED 2026-08-20**
(`perf/prefetch-lands`). **The arc's line-crossing lever: max-diagonal 2.067 → 1.240
frames/tick, work/tick 170,723 → 134,521.** F2a (the residency guard) + the memo re-key
shipped; **F2b and F2c were not needed** — the ruling made F2c conditional on a+re-key
missing the −21,580-class saving or regressing the right axis, and they did neither.
- **The guard.** `Cache_Spec_Gen_Ring`, eight words of `Block_Stage_Gen` history indexed
  `Logic_Tick & 7`, makes "claims over the prefetch lead" a subtraction. Above
  `BLOCK_STAGE_SLOTS` the whole speculation tail is skipped; it re-arms only below
  `BLOCK_SPEC_REARM` = 8. **The asymmetry is not taste — it is measured:** the demand-only
  window at max-diagonal settles at **11**, between the two thresholds, so a single-threshold
  gate would have oscillated at roughly 50% duty. Guard state is now printed by
  `streaming_choke_probe`: suppressed **25 of 25** ticks at `maxdiag`, **0 of 31** at `right`,
  **0 of 31** at `down`, **0 of 29** at `idle`.
- **Why a guard and not a deletion, settled by measurement rather than by the packet's
  inference.** The new `tools/staging_lifetime_timeline.py` (built BEFORE the fix, per the
  arc's standing rule and the packet's own §9(b)6 ask) grades each speculation. At `right`
  and `down` **100% of staging claims are speculative and ZERO are demand** — on a single
  axis the prefetch IS the fill and every claim lands, which is exactly why the packet's
  throwaway B regressed `right` to 1.069. Those states sit at 4-5 claims per 8 ticks against
  a 16-slot budget, so the guard never trips there and both are byte-for-byte unchanged in
  claim count and frames/tick.
- **It also corrected the packet.** §3's "speculation is 100% dead" is really 59% dead
  (9 of 22 evicted speculations LANDED), and the larger cost was never the dead claims: it is
  the DEMAND work the churn creates. Demand-block residency at max-diagonal was **3.25 ticks**
  against a strip the fill needs for eight, so the fill was re-decompressing its own blocks —
  2.20 demand claims/tick where the single-axis states pay ZERO. After the guard, demand
  residency is **11.24 ticks** and total claims are 1.27/tick, all demand, zero dead.
- **The memo re-key** fixed both halves of the self-defeat: block-aligned bounds (the raw
  bounds moved 8× more often than the SET they named) and an eviction-derived key
  (round-robin makes the claims-since-record an exact evicted-slot window; the scan records
  the slots its result rests on in a word mask, and a survivor rolls its delta base forward).
  `TileCache_FindStagedBlock` publishes the hit slot at zero instructions (`d4` was already
  holding it; it moved from `clobbers` to an unconditional `out` with a `$FF` miss sentinel).
  **Isolated by throwaway: worth 709 cyc/tick at `right`, 511 at `down`, ZERO at `maxdiag`,
  against the OLD key's 707 and 482 — i.e. the re-key itself is worth +2 and +29, nothing
  measurable.** That is a derivable result, not a disappointment: at `right` only the col
  scan runs and its bounds are static, at `down` only the row scan runs and its bounds are
  static, so the old key already hit at both. The re-key pays in MIXED-axis motion, which is
  where the guard now turns the scans off. It ships as a correctness fix and is counted as a
  lever nowhere.
- **Two caveats on the 36,202, in opposite directions, both stated:** `PageCache_Audit` fired
  in the BEFORE window and not the AFTER one (1,633 cyc/tick of it), so the attributable
  saving is ≥ 34,569; and §7's attribution defect understates the 2.067-frames/tick baseline,
  so the true saving is larger than either figure. **Quote `frames/tick` 2.067 → 1.240** — a
  frame and tick count, not an attribution. `idle`'s work/tick is not quotable (F1's booked
  trap fired again: VSync_Wait moved 3,734 cyc/frame with `total_cycles` unchanged); the
  guard's fixed idle cost read off the fill's own row is **+121 cyc/frame**.
- **Value identity held**, and the compare had to be rebuilt for a schedule-changing fix: the
  fixed ROM travels further in the same 31 frames, so the states are matched on SETTLED
  CAMERA POSITION, with camera, all four cache bounds, both origins, budget, both resume slots
  and the stall flag asserted equal before any content hash is compared. Nametable and
  collision hash equal at all four states.
- **Lanes:** `effects_gates` 24/24 exit 0, `./test.sh` 19/19 (the headless replay net's two
  fixtures still replay desync-free, plus its negative control), pytest 1143 passed /
  3 skipped, `emp_expect_fail` 20/20, `s4lint` clean, `effects_budget_check` 31 rows,
  `verify_level_bin` OK, sigil warnings unchanged (9 / 123), F4's
  `tools/staging_index_poison.py` and `tools/pagecache_audit_poison.py` both LIVE.
- **RAM +30 B in `lower_ram`**, placed beside F4's Bucket/Chain: four lower_ram symbols move
  and NOTHING game-side does. Deliberately not at the `upper_ram` tail where the rest of the
  memo lives — that costs a full game-side repin to buy 4 cycles a tick on once-per-tick state.
- **Trap for the next parcel:** sigil's `[call.live-clobbered]` (D1c) fires on ANY read of a
  register declared `out(... if eq)` when that register is may-defined before the call, which
  a loop always makes true. The fire decision consults `callee_uncond_out`, so a CONDITIONAL
  out is treated as destroyed. Reading a probe's conditional result in a loop therefore needs
  either an unconditional `out` (which sigil then refuses to also list in `clobbers`) or an
  adjudicated baseline row in the sigil repo. This parcel took the first route because `d4`
  is genuinely total; a parcel barred from the sigil tree and holding a value that is NOT
  total has no third option worth its cycles.

**Fix F5 — `PageCache_Audit` off the fill path — ✅ CLOSED 2026-08-19**
(`perf/audit-off-fill-path`). The DEBUG periodic residency audit's interval gate no longer sits
inside `Tile_Cache_Fill`; the level state's tick runs it, once per tick, immediately after the
fill returns. Cadence is unchanged — the fill's own once-per-physical-frame gate already made
the counter advance once per LOGIC TICK (measured at idle: `Page_Audit_Ticks` 109 → 11 over
30 ticks / 31 frames), so the audit still fires every `PAGECACHE_AUDIT_INTERVAL` = 128 ticks and
its blind window is still one interval (~2.1 s at 60 Hz, ~4.3 s while the streaming path lags).
The corruption class it witnesses is monotone — nothing re-derives `pf_refcount` from the
nametable, so a drift is never MISSED by a periodic audit, only reported late.
- **De-noise, measured where the instrument closes.** `idle` (the audit fires inside the window):
  `Tile_Cache_Fill` 4,780 → **926** cyc/tick, −3,854 = 100.4% of the audit's own row
  (3,837 cyc/tick), which survives intact at 3,811. The fill's row is now its true no-work cost.
- **The null.** At `right`, `down` and at non-firing `maxdiag` phases (settle 160 / 186) NOTHING
  else moves: the fill loses only the removed gate (−42 cyc/frame at `right`/`down`, −14 at
  `maxdiag`/160) and every leaf, every bracket, `work/tick`, `frames/tick` and the exact
  decompress counts are unchanged. **This is the parcel's real product: the probe's other rows
  are proven audit-free**, so F1/F2/F4's numbers were never audit-contaminated.
- **`maxdiag` at the canonical settle 180 is not a usable de-noise measure**, and this parcel is
  a second, independent demonstration of §7: the fill row moves 106,138 → 105,231 cyc/tick while
  the audit row collapses 7,333 → 872, i.e. old oracle stops attributing the pass to any row
  rather than moving it. In that state its rows already fail to close — the
  `GameState_OJZScroll_Update` bracket (55,145 cyc/frame) is SMALLER than the sum of the children
  the probe measures under it (56,219), before and after. `idle`, `right` and `down` close.
- Release shapes byte-identical (`s4.bin` e111dff7 / `demo.bin` aae04929). **Trap for the next
  parcel:** the first cut added a zero-byte DEBUG-only engine proc for the gate; that label alone
  moved `demo.bin` (aae04929 → 6710c1ac, everything before `EndOfRom` identical — it is the deb2
  appendix). The gate is spelled INLINE in the level state for that reason. `s4.bin` did not
  move, so **a release CRC check on sonic4 alone would have missed it** — check both.
- `tools/streaming_choke_probe.py` updated: `PageCache_Audit` is out of `Tile_Cache_Fill`'s
  child map and prints as a sibling with no "%fill" (it read 411.6% of the fill at idle while
  still tabled as a child).

**Fix F4 — direct-map the staging probe — ✅ CLOSED 2026-08-20** (`perf/staging-direct-map`).
`TileCache_FindStagedBlock` probed the 16-slot block-staging cache with a LINEAR SCAN
(`cmp.l (a1)+ / dbeq`), 416 cycles a probe. It is now an O(1) hashed lookup.
- **The design choice that mattered.** A true direct-mapped CACHE (slot = hash(key)) would have
  changed EVICTION — F2's subject, and the baseline F2 is measured against. What shipped is a
  **side index over the existing round-robin slots**: `Block_Stage_Bucket` (256 entries, one per
  block index) + a stride-4 `Block_Stage_Chain`. `Block_Stage_Next`, the round-robin policy and
  `BLOCK_STAGE_SLOTS` are untouched. Separate chaining is exact for ANY hash, so the probe
  returns the slot the scan returned for every key and the HIT/MISS sequence is unchanged **by
  construction**, not by measurement. **F2's baseline is intact** — `Block_Stage_Gen` (exact
  decompress count) and `Block_Stage_Next` (the cursor) are equal at all four states.
- **The hash costs zero instructions:** the bucket IS the block index, already in `d2`. Two
  staged blocks collide only across sections exactly 256 tiles apart, against an 80×60 cache.
  Measured: **0 of 16 chain links in use — max chain length 1.** The chain exists so exactness
  does not rest on that argument.
- **Predicted then measured.** Hit ≈ 210 cyc (was ≈ 427), miss ≈ 116 (was ≈ 582) predicted
  −1,911 / −2,795 / −5,918 cyc/tick at `right`/`down`/`maxdiag`; **measured −1,714 / −2,708 /
  −5,394**, within 5–12%, with per-probe cost landing at 196–214 against 210 predicted.
- **Measured** (`--repeat 3`, spread 0.000, 3 boots): `FindStagedBlock` `right`
  3,614 → **1,900** (−47.4%), `down` 5,281 → **2,573** (−51.3%), `maxdiag` 10,265 → **4,871**
  (−52.5%). `work/tick` `right` 82,577 → **80,979**, `down` 83,614 → **81,660**, `maxdiag`
  174,447 → **170,723**. **`idle` calls it ZERO times** — verified from the counters (the probe
  prints `ABSENT (0 calls)`), not assumed.
- **RELEASE, the shipping number** (`s4.bin`, `down`): 4,703 → **2,451 cyc/tick (−47.9%)**,
  392 → **204 cyc/probe**, fill 32,707 → **30,583 (−6.5%)**, work/tick 88,762 → **86,638**.
  `right` stays non-reproducible in release for F1's reason (the leader falls).
- **`maxdiag` frames/tick stays 2.067, as intended.** F4 was never a line-crossing lever;
  170,723 is still above 128,000. **F2's remaining distance is 42,723 cycles.**
- **Value identity held:** full byte compare of `Tile_Cache_Nametable` AND
  `Tile_Cache_Collision` at all four pinned states (two settles), camera + cache bounds +
  `Block_Stage_Gen` + `Block_Stage_Next` all equal.
- **The AB scenes did NOT hit F1's wall** — all four returned `ALL EQUAL (gated)` after
  `--selfcheck`, because they poke `Debug_Scene_Freeze` and the fill does nothing there. F1's
  booked warning that "F2 will hit the same wall" still stands for F2; it just did not apply here.
- **New machine checks are poison-tested** — `tools/staging_index_poison.py`, three arms HALT
  (two of them leave 255 buckets correct) and the control keeps running. The claim's
  duplicate-key arm has no RAM poison (any poke creating a duplicate also makes the probe hit
  it) and was shown live by a throwaway source mutation instead; both throwaways reverted.
- **Lanes:** `effects_gates` **24/24 exit 0**, pytest **1143 passed / 3 skipped**,
  `emp_expect_fail` 20/20, `s4lint` clean, `effects_budget_check` 31 rows, `verify_level_bin` OK,
  sigil warning counts unchanged (9 / 123).
- **Cost:** `TileCache_DecompressBlock` +384 B, `TileCache_InvalidateStaging` +36,
  `TileCache_FindStagedBlock` +16 (+12 inter-module pad). ROM: `s4.bin` +243, `s4.debug.bin`
  +329, `demo.bin` +229, `demo.debug.bin` +331. **RAM +320 B in `lower_ram`** — only the four
  `lower_ram` symbols after it move; **no `upper_ram` address and not `Engine_RAM_End`, so
  there is NO game-side repin.** `lower_ram` free 3,622 → 3,302 B.
- **Trap for the next parcel, worth knowing:** the `.lst` interleaves Z80-space blob labels
  (`SfxBlobWinTab`, `DacSampleTable`, `MovingTrucks_PitchTable`, …) with 68k symbols at
  overlapping numeric addresses. They do NOT move when 68k code shifts, so a naive
  "span = next symbol's address" per-proc diff splits unrelated procs at random and invents
  changes — it reported `Level_LoadArt` −89 and `Sound_GetComm` −448 here, both fictional.
  Filter boundary candidates to symbols that actually shifted.

### 1. §9.7 idle-time deferred work / resumable decode — **✅ RESOLVED — EXECUTED as art-streaming Phase 2 (2026-08-09)**
**Done (`feat/art-streaming-p2`, chains 55→78; merged to master `2f047e3`).** §9.7
shipped as the pre-chunked-pages + VBlank-supervisor-bookmark idle-time path (the user-mode variant
was rejected). The resumable `ZX0R_Decompress` decoder is sliced across idle by a VBlank
register-bank/resume, feeding a VRAM page residency cache. All three items this gated are
discharged: **Art-streaming Phase 2** (the driving consumer) is live; **ZX0 mid-gameplay decode**
now rides the bookmark, never synchronous; **S4LZ Streaming Mode (§2.1)** inherits the identical
pipeline (rescoped in its own entry below). ARCH §9.7 + §2 rewritten in place; see the resolved
full entry below and `plans/2026-08-08-art-streaming-phase2-v2.md`.

### 2. The whole "Engine substrate gaps" gate is satisfied
The stocktake's gate was "execute AFTER the Sigil port". **The port is done** — `build.sh:4`,
no `.asm` code twins remain. Per-item status is annotated on the stocktake itself; summary:
- **SRAM save (item 2)** — mechanically ready, but retains a genuinely unverified dependency
  (oracle SRAM persistence) *and* `3c96265` has since ruled SRAM **is** the persistence
  mechanism (CrossResetRAM ruled out), which raises its priority.
- **Water (item 3)** — unblocked but still wants its own design pass. Not a pick-up-and-go.
- **Engine-default sound bank (item 4)** — mechanically ready, but **must be re-targeted**: the
  contract file it names was deleted. See the corrected item.
- **RNG (item 5)** — folds into design #9, as stated. Not standalone.

### 3. Cheap, self-contained, verification-bounded
- **`yflip`/`xyflip` size+link word merge** (`engine/objects/sprites.emp` `size_link`) — the
  constraint that forced the byte-wise form is recorded as dead. Needs only SAT byte-identity
  verification for the two flipped variants. ~8 cycles/piece.
- ~~**Parallax computed-jump-table unroll**~~ — **✅ CLOSED 2026-08-20 (`perf/parallax-unroll`).**
  This row was stale twice over and contradicted the file's own closed entry below; both are
  now settled there. The lever was taken in the SAMPLING loops (not the flat one, which has
  been unrolled for a year) and it took the streaming arc under its line: max-diagonal
  work/tick **134,521 → 123,016**, against a 128,000-cycle frame. Full verdict in the closed
  entry below and in `benchmarks/streaming/CHOKE-DIAGNOSIS.md` §8 F7.
- **Variable HScroll DMA — variable-length transfer** — its blocker ("await a confirmed
  performance need") is **DISCHARGED by this file's own measurement**: per-line HScroll is
  896 B/frame, ~20% of the frame, and this file names it "the single biggest lever". Caveat: the
  `Hscroll_Dirty_Start/End` infrastructure it assumed **was deleted** and must be rebuilt.
- **`VInt_Level` header comment** — one-line comment fix, zero byte change (entry at the bottom).

### 4. Object-system items whose §3 blocker is long satisfied
`engine/objects/` is fully built (`load_object.emp`, `animate.emp`, `dplc.emp`, `collision.emp`,
`children.emp`, `sprites.emp`), so these are unblocked *mechanically* — but read the caveats:
- **DPLC Lookahead** (§1.6) — `animate.emp` + `dplc.emp` exist. Clean pick-up.
- **Dynamic VRAM Allocator** + **Refcount-based Art Caching** (§2.2) — `load_object.emp` exists,
  **but the fully-resident deduped art pool may have made the premise moot.** Re-read the design
  before planning; do not assume the 2026-04 framing still applies.
- **Section-aware Streaming / Predictive Preloading** (§2.1/§4.8) — blockers exist, and the
  block-stream half **effectively shipped** (`tile_cache.emp:1001` row scan, `:1093` col scan with
  H3 hysteresis). What remains is the *art* half, which is item 1 above.

### 5. Diagnostics / instrumentation
- **Contract-enforcement trap handler** (68K half, idea-capture section) — its expensive
  prerequisite, the In:/Out: contract grammar, **has landed and is still growing** (HEAD `fa0ae0b`
  made the Z80 bus and the interrupt mask declared contexts). The cheap half of a
  design-for-it-now item is now the only half left.
- **SIGIL ASK (not aeon work) — promote declared-`preserves()` violations to a build-fatal
  dataflow check.** From the T6 art-streaming review. Today `[call.live-clobbered]` is a
  *non-fatal* diagnostic, and that leniency is exactly how the chain-63 `CopyBlockColumn` `a1`
  regression shipped: a coherent-but-wrong render that a fatal check would have caught at build
  time. Ask: sigil should verify, per proc, that the value of each declared-preserved register at
  every `rts` equals its value at entry (dataflow equality across the whole body incl. call
  clobbers), and make a violation **build-fatal** — not a warning. This lives in the sigil repo
  (`/home/volence/sonic_hacks/sigil`), not here; recorded so the ask isn't lost.

- **The replay net had NO automated runner — ✅ candidate fix (a) DONE 2026-08-14; (b) still open.**
  Discovered 2026-08-13 while re-stamping it (`docs/superpowers/plans/2026-08-13-replay-net-restamp.md`).
  Verified at the time: it was not a pytest, not a cargo test in sigil, not in `test.sh`, and there
  is no CI. The aeon suite's "2 skipped" are `test_s4lint.py` looking for a deleted `main.asm` —
  **not** the replay net. The net failed only when a human ran a manual oracle procedure, which is
  precisely how master stayed red from the Knuckles C4 merge until 2026-08-13 with nothing
  reporting it. `tools/test_replay_fixture.py` gates fixture *structure* (length, tick
  count, checkpoint ring alignment, and the BUTTON_C spindash runs that prove a re-stamp
  rather than a re-record), but it cannot detect a desync — that needs the emulator.
  Two candidate fixes were named: (a) a headless oracle runner invoked from `test.sh`,
  (b) a committed re-stamp tool that makes the manual loop cheap enough to run routinely.

  **(a) SHIPPED 2026-08-14 — `test.sh` section 8 "Replay Net (headless oracle)".** The runner is
  a headless binary in the sibling oracle-next repo that boots the DEBUG ROM, arms the embedded
  stream, replays it to completion and reports PASS / DESYNC / FAULT / TIMEOUT by exit code
  (design + contract: `/home/volence/sonic_hacks/oracle-next/docs/2026-08-14-replay-runner-design.md`).
  To run it:

  ```bash
  cd /home/volence/sonic_hacks/oracle-next && cargo build --release -p oracle-replay
  cd /home/volence/sonic_hacks/aeon
  export SIGIL_BUILD=/home/volence/sonic_hacks/sigil/target/release/sigil
  export SIGIL_EMIT=/home/volence/sonic_hacks/sigil/target/release/emit_sound_blob
  ./test.sh                       # section 8 runs the net; ORACLE_NEXT=/path overrides the repo
  ```

  The section **builds the DEBUG shape itself** (`DEBUG=1 ./build.sh sonic4`, measured ~1.4 s) —
  the checkpoint compare is `if DEBUG == 1` only and symbols bind per-shape, so grading a stale
  or release ROM would be a false green (the runner refuses a release ROM outright). It runs
  **both** committed fixtures *and* `--negative-control`, which plants `$DEADBEEF` over the first
  checkpoint and requires the desync trap to fire — a gate never seen failing is not a gate.
  Absent inputs (runner, ROM, `.lst`) are RED, never skipped. Cost: ~12 s on top of the ~1 s suite.

  **What this does NOT cover.** It replays the two committed OJZ fixtures on the sonic4 DEBUG
  shape only — no demo game, no other shapes, no new coverage of code the fixtures never touch.
  `tools/test_replay_fixture.py` still does its own separate structural job and is not replaced.
  **(b) is still open**: the manual re-stamp loop still costs ~7 full playbacks (each replays
  from tick 0, and the post-spindash section runs well under realtime under host CPU contention).
  The oracle-next design scopes (b) as a future `--restamp` flag on the same runner rather than a
  second tool, so a desync that is a *legitimate* engine change still needs the manual loop today.

### 6. Sound package 4 — ✅ EXECUTED 2026-08-10 (historical text below)
**D1, D4, D5, D6, D7** and **E5's 7th RegDelta group** are open, verified against the tree, and do
**not** depend on the unexecuted packages 1/3/5/6. (**D2 is DONE** — corrected below.) This is the
largest cluster of small, well-specified, independent sound work in the file.

### 7. Mega-act ROM layout — OJZ's pre-DAC hole caps in-order act data at ~21 KB slack — 2026-08-09
**Discovered building the P2c Task 11 stress-art fixture.** OJZ's map order places ALL act data
(art pool, block blobs, local maps, the 116 KB `collision_data`/heightmaps) BEFORE the HARD DAC
sample-bank anchor at `$48000` (a Z80 `SetBank` latch — cannot move). `collision_data` alone ends
at `$42D90` canonically, so the in-order act data has only **~21 KB of slack** before the anchor.
A real act whose art/block data exceeds that overruns the anchor and will not link in order.

The stress fixture works around this with **fixture-only relocation** (the growable OJZ sections
move past the sound banks, extending the ROM tail — see `native.rs::relocate_fixture_pool`, gated
by `fixture_placement`). That is fine for an unfrozen throwaway, but the **mega-act's real acts
WILL exceed the hole** and need a real answer, one of:
- **post-sound act-data placement** (make the fixture's relocation a first-class layout for real
  acts — the act data region lives after the sound banks, before the fault island); or
- **a ROM layout rethink** (move the sound/DAC banks higher, or bank the act data) so the pre-DAC
  hole stops being the ceiling.
This is a genuine mega-act blocker, not a fixture quirk — record it now so it is not rediscovered
under the mega-act itself.

---

## From §4.12 — External Warp Mailbox (shipped 2026-08-19, `feat/debug-warp-mailbox`)

The DEBUG warp mailbox is live and gated (`tools/warp_mailbox_gate.py`, 10/10). Full protocol +
ladder in **ARCH §4.12** — Aurora consumes that section. These are the riders it deliberately
left open, each recorded with what it would take to close.

- **The warp is a ~21-frame hitch, not a seamless jump.** Measured (gate: ack after 21 frames).
  The consumer re-runs `TileCache_FillAll` over the whole 80×60 window and forces
  `Section_RedrawPlanes` (itself documented as a ~3-frame poke storm), all inside one game-state
  call, so the frame overruns and the display holds the pre-warp picture until it finishes.
  Correct for an editor jump and deliberately off every gameplay path. **To close** (only if a
  gameplay-facing teleport is ever wanted): slice the refill across frames behind a "warp
  pending" state, or blank the display for the duration. Do not do it speculatively — the
  seamless version is the floating-origin rebase (§4.11), which is a *different* mechanism.

- **Objects spawned before the warp are not despawned.** The ladder calls `EntityWindow_Init`,
  which clears the loaded masks, the collected window and the scan state, and re-centres on the
  destination — but it does not walk Object RAM, and boot only gets away with that because
  `InitObjectRAM` runs *before* the player is placed. So an object that was live at the origin
  stays allocated at its old world position after the warp. Harmless today (test-scene objects,
  and the slot pool is far from full) but it is a slot leak across repeated warps. **To close:**
  a "despawn every dynamic object except the leader" walk, which does not exist yet and which
  `InitObjectRAM` cannot be reused for (it would wipe `Player_1`).

- **Streaming acts (pool > `PAGE_FRAMES_CLAMP`) are untested through a warp.** OJZ act 1 is 10
  pages against 15 frames, i.e. permanently fully resident, so `TileCache_FillAll` after a warp
  never misses. On a streaming act the refill would take demand misses, set `Cache_Art_Stall`,
  and `FillAll` has no resume path (it is an init-only routine). `PageCache_ResetRefcounts`
  deliberately does *not* flush the page-in FIFO (a flush would strand a mid-decode frame,
  detached and invisible to `PageCache_Audit`), so an in-flight page-in completes normally. **To
  close:** the first streaming act, plus a decision on whether the warp should spin frames until
  the demand set lands (the `Level_LoadArt` shape) or accept a few frames of blank art.

- **The consumer lives game-side, and that is a constraint, not a preference.** `Debug_Warp_Consume`
  is called from `GameState_OJZScroll_Update`, not `engine/system/game_loop.emp`, because `demo`
  links every `engine.*` module: an ungated frame-top consumer would compile into a game with no
  act, and gating it needs a new **required** `Game` contract const — which both games must bind
  and which breaks the 11 sigil port tests that lower `game_loop.emp` standalone against a
  synthetic contract env. `Game.debug_tick`, the existing frame-top hook, is claimed by the
  off-canonical Config-A profile, so binding it there would move that profile's frozen bytes.
  **To close** (if a second level state ever wants the warp): add the contract member and the
  sigil-side `test_support` + `repin.toml` entries as one aeon+sigil pair — the blast radius is
  known and small, it was simply out of this parcel's scope.

- **Two DEBUG-only labels ride in the RELEASE deb2 appendix.** `Debug_Warp_Consume` and
  `PageCache_ResetRefcounts` emit zero release bytes, but a zero-byte label still lands in the
  convsym symbol table both canonical shapes carry — which moves the ROM CRC. Both are therefore
  parked immediately against an existing zero-byte label so the appendix dedupes them away, and
  release stays byte-identical (verified: `s4.bin cdabf8a3`, `demo.bin f7806241`). **This is
  fragile and load-bearing**: moving either proc changes the release ROM. The language offers no
  module-level `if DEBUG == 1 { proc … }` (measured: `expected a declaration, found Ident("if")`),
  and registry-side module gating — the `CompressionSelfTest` idiom — is the only clean fix, at
  the cost of a sigil registry edit. **To close:** either a `.emp` module-level conditional, or
  move both procs into a DEBUG-only module with a `native.rs` registry row.

- **`Plane_Buffer_Reset` now has a caller, and it is DEBUG-only.** Its `@scaffolding("…unwired:
  single-level harness")` annotation is still true of release, which is why it stayed. If a real
  act transition ever wires it, drop the annotation then.

---

## CANNOT BE SETTLED STATICALLY — needs an emulator run or an owner ruling

Recorded so nobody burns another pass trying to re-verify these by reading code. Each is
genuinely open; none of them can be closed from the tree alone.

**Needs a live emulator run (oracle):**
- **A2 — two SFX in one 68k frame.** The 8-deep ring shipped; the *runtime* check (jump+ring,
  skid+ring, death+ring-loss in one frame, both SFX reaching the chip) has never been run. Partly
  discharged by the Stage-A fix-3 live debugging, but not formally.
- **FM env attack seam (T8 residual)** — explicitly "awaiting the user's by-ear pass". Not
  visible in rendered A/B at capture scale.
- **Bank-latch desync corrupter** — captured exactly once, did not reproduce deterministically.
  Needs a live watchpoint session on `$6000`-latch writes around a mid-sample DAC retrigger. May
  be an emulator artifact.
- **DAC worst-tick profiling round** — the honest lever for the remaining hold tail; requires
  profiling what dominates the 5-10 ms ticks, not code reading.
- **§2 A.5 T1 — FG tile-flip A/B vs sonic_hack** — requires two emulators paused at the same
  screen comparing VRAM bytes. Build-tool math already verifies correct.
- **oracle SRAM persistence** (substrate item 2's hidden dependency) — likely an oracle-side task,
  not an Aeon one.

**Needs an owner ruling (product decision, not an engineering answer):**
- The **diagonal streaming budget** tradeoff (A: accept the dip / B: cap combined diagonal step /
  C: cut BgAnim bands during fast scroll). Recommendation on file is (A).
- **`test_player` as a unit** — whether the test object set should ship in release at all.
- **Authoring the debug-fly cheat code** — mechanism is shipped and waiting on content.
- **The OJZ BG `band_reserve` number** (NEW 2026-08-22, `parcel/bg-band-reserve`). The mechanism
  shipped at **0**, which is bit-for-bit today's behaviour; the number itself is the
  animation-vs-detail dial and is deliberately not an engineering call. Setting it is a one-line
  edit to `bg_region` in `games/sonic4/vram.toml` followed by
  `python3 tools/gen_vram_map.py --game sonic4 --toml games/sonic4/vram.toml --py tools/vram_map.py --emp games/sonic4/config/constants.emp --map-doc docs/generated/vram-map-sonic4.md`
  (skipping the regenerate now fails `pytest tools`, so it cannot go unnoticed).
  **Coupled to an art re-import**: the reserve constrains the *next* `png_to_bg_override.py` run,
  and the shipped 448/448 blob does not shrink on its own. Sizing context, measured rather than
  inferred: the destroyed configuration was 340 tiles = 192 animated + 148 static + 108 unused,
  **not** "192 reserved of 448" (full derivation in `docs/BUGS.md` TOOL-01).
  **UPDATE 2026-08-26 (`content/ojz-bg-roomy`)**: the re-import happened. The shipped BG was
  regenerated from the auto-simplified source under owner ruling aurora d-10 (answered at
  aurora master 259c5cb): static budget now **320/320** with the full **128-tile band_reserve
  free** for bands. Aurora remains the sole writer of `anims`.

---

## PARKED FOR REVISIT — mid-line CRAM writes: a VERTICAL (left/right) palette boundary — 2026-08-15

**Owner asked for this to be parked and retrievable, not dropped.** Raised while testing Parcel W's
water line: *"can I do 389 cycles of nothing, then 100 cycles of a different palette for one line —
does the right side of the screen become that palette?"*

**The premise is correct.** The VDP reads CRAM as it draws each pixel, so a CRAM write part-way
through a scanline changes the colours for the remainder of that line. We are already producing
this effect BY ACCIDENT: channel 0's 3-word CRAM fire measures **518 cycles against a 488-cycle
line** (`docs/benchmarks/effects-p3/DENSITY-EVIDENCE.md`, re-measured 2026-08-16; the 526 it
replaces was an `interrupts.hint` figure, i.e. HBlank plus VBlank), so it spills past the line edge
and repaints mid-line. That is the "cuts off halfway" the owner observed at the water boundary on
2026-08-15 — the horizontal-boundary mechanism demonstrating itself unintentionally.

**Three obstacles, in order of how much they hurt:**

1. **The CRAM dot is not tunable away.** A CRAM write during active display corrupts the pixel
   being output at that instant — the colour bus is hijacked. `EFX_BLANK_DELAY` exists precisely to
   push our writes into HBlank so nobody sees it (`engine/effects/raster.emp`, the row-119 fix).
   Titan's demos do not avoid the dot; they choreograph it. **Choosing a vertical boundary is
   choosing to put a dot on it.**
2. **Bus slots, not cycles, are the currency.** During active display the 68000 gets VDP access
   only at scarce fixed slots, so a cycle-counted delay does not land where the arithmetic says —
   it lands at the next slot. Horizontal positioning is therefore quantised much coarser than a
   pixel, and the quantisation is not a round number.
3. **No budget left.** 526 > 489 already. A second timed write per line means fewer colours per
   fire, not extra work for free. Realistic ceiling: about ONE mid-line write per line.

**Do not reach for this first — three cheaper mechanisms cover most vertical-boundary wants:**
- **Per-tile palette lines** (four lines, free) — the right answer whenever the boundary follows
  tile geometry.
- **The window plane** (free rectangular region with its own tiles) — the right answer for a
  status-bar-shaped split.
- **Per-column VSRAM, which Aeon ALREADY SHIPS** — `pcfg_v_deform_table_bg`, 20 column-pairs
  sampled per frame (ARCH §4.6). Vertical-boundary *scroll* effects are already free; it is only
  *palette* on the vertical axis that is unsolved.

**If it is built anyway**, the hook is the DENSE tier: `OP_RUN_GRADIENT` is the only mechanism with
per-line control (it fires every line with reg `$0A`=0 and runs a minimal body), so a mid-line
write would be a second timed store inside a dense-run body. It is a **set-piece effect, not a
vocabulary op** — expensive, artifact-bearing, spectacular. Cost it as a demo, gate it on a pinned
camera, and expect the dot to be part of the art direction rather than a defect to fix.

**Unblocked already** — nothing is missing. This is parked on cost and taste, not dependencies.

---

## MAINTENANCE PROTOCOL — in-place annotation is the convention (settled 2026-08-05)

The "How to Use This Document" section at the bottom says to *move* completed items to the Done
section. **That protocol lapsed:** the Done section stops at 2026-06-11, while roughly a dozen
later closures were annotated in place instead (`~~struck~~` headings, `✅ RESOLVED` prefixes,
`DONE <date>` suffixes, inline `**CORRECTION**` blocks).

**Ruling: in-place annotation IS the convention now. Do not move entries to Done.** It preserves
the reasoning chain next to the claim it corrects, which is the property this repo actually wants.
The Done section below is frozen as a historical tail (Apr-Jun 2026); nothing new goes into it.

When you close or correct an entry:
1. Leave the heading where it is; prefix it with `✅ RESOLVED —`, `~~strike~~`, or
   `**CORRECTED <date>**`.
2. State the evidence — commit hash, `file:line`, or the ruling that superseded it.
3. **Keep the original text beneath.** Never silently delete a wrong claim; a wrong statement
   reading as current is the only unacceptable outcome.

---

## Engine substrate gaps — stocktake 2026-07-07 (~~execute AFTER the Sigil port~~ — **GATE SATISFIED 2026-08-05**)

> **✅ GATE SATISFIED (verified 2026-08-05).** The whole section was gated on "execute AFTER the
> Sigil port". **The port is done.** `build.sh:4` reads "THE FLIP (Spec-5 Stage 2, the point of no
> return): `sigil build` IS the build" — asl/p2bin/fixheader have left the pipeline and the `.asm`
> CODE twins are deleted. The only `.asm` survivors are the vendored `engine/debug/debugger.asm`
> and the two ~40-50 line `games/*/game_root.asm` residual roots, neither of which is a twin.
> **The pin-target argument that justified deferring no longer applies.** Per-item status is
> annotated on each item below — three of the five are ready, one needs a design pass, one is not
> standalone.

Gaps with no owning design anywhere (not in the nine design-week specs, not in the sound
packages, not in the engine/game split plan). Deliberately deferred until Sigil finishes
and the code is ported — Sigil verifies by byte-exact pinning against AS output, so new
engine code before then moves the pin target and grows the port surface for no de-risk
(the pin is a stronger port-verification net than any of these features would be).

**Recommended pickup order after the port:**

1. ✅ **RESOLVED 2026-08-02** — **Input layer maturity + demo recording/replay** — SHIPPED
   as the input/replay phase (spec/plan `docs/superpowers/{specs,plans}/2026-08-02-input-replay*`,
   parcels I1-I4, chains 25-30): full 6-button layer (SGDK low-first cadence, two-signature
   per-frame detect, Ext/Pad_Type cells), `Logic_Tick` timebase, the `Input_Tick` replay seam
   (`engine/system/replay.emp`), the committed OJZ fixture + proven checkpoint net
   (evidence: `docs/superpowers/2026-08-02-engine-debts-opener-evidence.md`). Pad-2 was
   already read; a human P2 + the determinism audit shipped with the harness. ORIGINAL
   ENTRY (historical): do FIRST: 6-button read (TH-toggle
   protocol), pad-2 support (a human second player; design #3's Tails AI is input-filter
   based and doesn't need it, a player does), and an input abstraction a record/replay
   harness hooks. Replay's real cost is the determinism audit (RNG seeding,
   frame-count/window-scan-dependent logic must be replay-stable); its payoff is a
   deterministic regression net under every later engine execution (#1/#2/#7-#9).
   `engine/system/controllers.emp` is 62 lines today — 3-button, pad 1.
2. **SRAM save system** — **PORT GATE CLEARED (2026-08-05); hidden dependency still live.**
   68k side is simple; the design is slot format + checksums +
   wear pattern. HIDDEN DEPENDENCY: oracle must emulate SRAM persistence first (verify;
   likely an oracle-side task) — **this one is NOT satisfied and cannot be settled by reading
   the tree.** UI home = design #7's menu screens. The `gameHeader`
   SRAM field (engine/game split plan) already parameterizes the header declaration.
   **PRIORITY RAISED (2026-08-05):** `3c96265` ("CrossResetRAM persistence RULED OUT — design
   deleted, SRAM is the mechanism") makes SRAM the *only* persistence mechanism the engine has.
   It is no longer an optional convenience feature.
3. **Water/underwater engine hooks** — **PALETTE HALF SHIPPED (effects P2, 2026-08-12);
   physics half still deferred.** Two halves: (a) mid-frame underwater palette via HInt —
   **DONE.** The water cluster is a composed preset (a `Variant_Water_Deep` boundary +
   S/H + the `Water_Level` patch slot: `Raster_Buf_B` rebuild + runtime arm recompute via
   `Raster_PatchWaterLine`), built on the raster script engine exactly as this entry
   predicted ("extend it, don't build parallel machinery"). The host now exists and is
   used (`Raster_InstallWater` / `OJZ_WaterRaster`). Two open riders on this half:
   (i) **S/H is visually UNPROVEN** — it dims only low-priority pixels and OJZ art is
   high-priority (baked into generated block data, no engine hook to clear); proving it
   needs low-priority water content, which is out of the effects-P2 parcel's scope. (ii)
   The oracle gate (variant boundary + moving line) is the controller's, not yet run.
   **UPDATE 2026-08-14 (Effects P3 Parcel C2).** The water cluster is now bound through
   an `EffectsPreset` rather than an imperative init call, and the patched channel got a
   world-Y entry point (`Raster_InstallPatchedWorldY`) so a boundary can be authored as a
   WORLD y instead of a screen line — the old path derived world Y from the camera, so
   feeding it an authored value stored `world_y + Camera_Y` and re-anchored differently on
   every re-entry. Also fixed here: EFX-1, water surviving exactly one crossing, which
   total binding removes by writing every channel. Rider (i) — S/H visually UNPROVEN — is
   unchanged and still needs low-priority water content.
   (b) per-section physics-modifier plumbing (engine hooks, game values) — **still
   deferred**, its own design pass when a level needs it.
4. **Engine-default sound bank** — lift the split plan's v1 limitation that `games/demo/`
   can't build with `SOUND_DRIVER_ENABLED` (ship a minimal engine-side bank satisfying
   the soundBankHead contract). **LIVE as of 2026-07-08:** the engine/game split executed
   and `games/demo/` exists — its `build.conf` defaults `SOUND_DRIVER_ENABLED=0` precisely
   because no demo sound bank exists yet (see `docs/ENGINE_ARCHITECTURE.md`, "Engine/game
   contract" section, and `games/demo/build.conf`). Lifting this limitation is now simply:
   author a minimal engine-side (or demo-side) bank that satisfies the `soundBankHead`
   contract (`engine/sound/sound_bank.inc`) — pitch table + SFX window table + song/SFX
   data — and flip the default on.

   > **⚠ CORRECTED 2026-08-05 — THE CONTRACT FILE THIS ITEM NAMES NO LONGER EXISTS.**
   > `engine/sound/sound_bank.inc` was **DELETED** by `1afa9aa` (2026-08-01, "K4 inc-5 Stage 4b —
   > P2 soundBankHead probe: the head is native; sound_bank.inc DELETED"). The `soundBankHead`
   > macro is gone; the head is now emitted natively.
   > **The live contract to satisfy is instead:**
   > - the `sound_bank` anchor declared in **`games/sonic4/map.toml`**, the entry whose
   >   `name = "sound_bank"` (`# SoundTablesZ80_Head — the MT/SFX phase bank (vma $8000)`), and
   > - the worked reference implementation at
   >   **`games/sonic4/data/sound/soundbankhead.emp`**.
   >
   > Three places still cite the dead path and will mislead the next reader — **all three are
   > out of scope for this doc-only parcel, listed so they get fixed together:**
   > `games/demo/build.conf:2`, `engine/sound/dac_sample_tab.emp:21`, and
   > `games/sonic4/data/sound/soundbankhead.emp:5` (the last is past-tense and least harmful).
   >
   > The item's *substance* is unchanged and the port gate is cleared: author a minimal
   > engine-side or demo-side bank, then flip `games/demo/build.conf`'s
   > `SOUND_DRIVER_ENABLED` default on. Only the target has moved.
5. **RNG** — trivial; fold into design #9 execution (the behavior sequencer is its first
   real consumer), not a standalone task. **(2026-08-05: port gate cleared, but this remains
   NOT standalone — it lands with design #9, not on its own.)**
6. **Dense-tier reserved stream register — FLAGGED, needs user sign-off (effects P2,
   2026-08-12).** `OP_RUN_GRADIENT`'s `.dense_body` ships the CONSERVATIVE model: the
   stream cursor is reloaded from `Raster_Dense_Cursor` (RAM) every line and only
   d0-d1/a1-a2 are saved. The corpus affords a ~26-cycle every-line handler by reserving
   a global stream register and saving zero (Gunstar `a6` / Alien Soldier, survey Ruling
   4c); for a 224-line gradient that difference is ~thousands of cycles/frame. Reserving
   a register engine-wide trades against the contract system and changes register
   conventions across the engine — an irreversible bet, so it is NOT taken without a
   user ruling (`memory/leapfrog_provenance_audit`). Revisit if a dense-tier workload
   measures over budget on oracle. Cycle arithmetic + the two mode-switch transitions are
   documented at `Raster_HInt`'s dense-body comment and `tools/effects_budget_model.toml`.

### ✅ RESOLVED — PAL fixed-timestep — deleted, NTSC-only (ruling B) — 2026-08-02
**Resolution (Volence, 2026-08-02, ruling B):** commit to NTSC-only. The dead PAL
timestep machinery is deleted — `boot.emp` drops the two `Timing_Step` writes and the
`Frame_Accumulator` clear, `ram.emp` drops both fields, `constants.emp` drops
`NTSC_TIMING_STEP`/`PAL_TIMING_STEP`. The region-adaptive DMA budget stays (the drain
reads it). Historical context of the decision follows.
**Surfaced during:** the silent-drop-class doc-reconciliation audit (2026-07-16 review
cross-check). Recorded as an UNFINISHED FEATURE awaiting a product decision, NOT a bug.
**Status (pre-deletion):** `boot.asm:167-174` performed region detection and wrote a
per-region timing step + accumulator, but nothing consumed them:
- `Timing_Step` (ram.asm:79) ← `NTSC_TIMING_STEP=$0100` / `PAL_TIMING_STEP=$0133` (the 6/5
  ratio, constants.asm:83-84). **Zero readers** (grep-verified: only the two boot writes).
- `Frame_Accumulator` (ram.asm:80) ← `0` at boot. **Zero readers.**
- `GameLoop` (game_loop.asm:10-18) runs exactly ONE state tick per `VSync_Wait`,
  unconditionally — no accumulator step, no catch-up ticks. So on PAL hardware the whole
  game (physics, camera, animation) runs at 50 Hz uncompensated (~5/6 speed), and the
  timestep machinery that would drive a fixed-timestep accumulator is dead scaffolding.
  (The region DMA budget `DMA_Budget_Default`, written on the same lines, IS live — the
  drain reads it — so only the *timestep* half is unconsumed.)
**The product decision (either direction is fine; this entry just forces the choice):**
- **(A) Implement PAL support** — consume `Timing_Step` into `Frame_Accumulator` in the
  main loop to run 0/1/2 catch-up ticks per VSync (fixed-timestep), so PAL plays at NTSC
  wall-clock speed. Couples to every frame-rate-sensitive system (physics caps, streaming
  budget, sound tempo — see item 6 above).
- **(B) Commit to NTSC-only** — then `Timing_Step`/`Frame_Accumulator`/`PAL_TIMING_STEP`
  and the PAL boot branch are dead and should be removed for honesty. **← chosen
  (Volence, 2026-08-02); the timestep machinery is deleted.**
**See:** item 6 above (PAL music tempo, the sound half of the same decision).

6. **PAL music tempo** — ✅ DECIDED (Volence, 2026-08-02, by the same NTSC-only ruling B
   that deleted the PAL fixed-timestep): frame-based PAL music slow is accepted as the
   product goes NTSC-only (emulator-only project; classic games shipped frame-based PAL
   music slow). Boot still region-adapts the DMA budget (that IS wired, read by the
   drain); the region timing STEP it used to write is deleted — see the dated
   **"✅ RESOLVED — PAL fixed-timestep — deleted, NTSC-only (ruling B)"** entry below.

---

## ✅ RESOLVED — OJZ section-0 tile-budget overflow — 2026-06-22

**RESOLVED 2026-06-22** via the globally-deduped paged act art pool (OJZ_ACT_POOL_TILES,
page loader), merged to master. The build succeeds and boots — every continuous-scroll
phase since (including Phase 2's on-device oracle verification) has run a bootable ROM.
Historical record retained below.

**Original report — The build failed** (`SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh`) at the art-budget
check: `sec0_tiles.bin is 19296 bytes — exceeds Decomp_Buffer capacity (9600)`.
This blocked **all** runtime work — no bootable ROM. Surfaced as "OJZ layout edits
weren't showing in game."

**Root cause is engine-side, not bad level data.** Whole level = 612 distinct tiles
in a 1,536-tile FG VRAM pool (60% empty); user's "shouldn't need so many tiles"
intuition was correct. The per-section streaming + DSATUR color-grouping pipeline
duplicates tiles across two VRAM regions and forces section 0's 603-tile blob
through a 300-tile (`9,600 B`) RAM staging buffer (`Decomp_Buffer`).

**Recommended fix (engine + build tool):** whole-level shared tileset loaded once
(the Sonic 2 model) when total distinct tiles ≤ VRAM capacity — skip color-grouping,
emit one shared tileset, decompress in N≤300-tile passes at level init. Full analysis
+ numbers + the alternative (multi-pass per-section decompress) in
**`docs/research/2026-06-22-tile-budget-deep-dive.md`**.

**⚠ Touches `tools/ojz_strip_gen.py`** — which the auto-commit daemon watches (commits
edits as the user ~60s after change). Coordinate with the user before editing it;
don't edit it autonomously. Needs the user's go-ahead on approach (shared-tileset vs
multi-pass) before implementation.

---

## ✅ RESOLVED — Engine Phase 3 cleanup — 2026-06-23

Behavior-preserving cleanup (branch `cleanup/engine-phase3`). A 114-agent
verified-clean audit confirmed the leapfrog teardown left no dead code paths;
the engine's "orphan" constants are intentional design surface (hardware-register
sets, flag/enum layouts, DEFERRED_WORK-tracked scaffolding), not cruft. Shipped:
- Removed the `SOUND_LOADTEST` debug scaffold (asm block + `build.sh` flag).
- `BG_TILE_CAPACITY` 512→448 reconciled (see the entry below).
- Removed two true vestiges: the `ANIM_BALL` alias and the dead `Sprite_Link_Next`
  write + RAM field.
- Whole-engine comment hygiene (non-sound): stripped historical/lying/task-tag
  comments, kept load-bearing rationale; binary-neutral (ROM byte-identical).
- `ENGINE_ARCHITECTURE.md` reconciled to the shipped paged-dedup pipeline
  (no graph-coloring/DSATUR/`LoadSectionTiles`/per-section art swap; ZX0 act pool;
  §4.2 `Sec` struct corrected to the real 66-byte / `$42` layout); §7 marked PLANNED.
- `CLAUDE.md` pipeline description corrected (graph-color → dedup + spatial paging).

### DEFERRED — Phase 3 follow-ups (not done this pass)
- **Sound-subsystem comment lineage (~151 tags).** `sound_*.asm`,
  `z80_sound_driver.asm`, `sound_constants.asm`, `main.asm`, `game_loop.asm` carry
  dense `(Task N)`/`(Phase N)`/`(Sound 1X)` build-lineage in comments. Deferred to a
  dedicated pass — large, judgment-heavy, on a subsystem not otherwise being
  modified, and many tags sit on otherwise-good descriptions.
- **`CLAUDE.md` "What This Engine Is" residual staleness.** L105 still says
  single-tier "S4LZ compression (level/bulk art)" — it is two-tier now (ZX0 act-pool
  pages + S4LZ runtime block stream). L106 says "Flamedriver sound driver" — the
  shipped driver is the custom sequencer (`engine/sound_*.asm` + the Z80 driver),
  not Flamedriver. **RESOLVED 2026-06-23** — both fixed (L105 → two-tier ZX0 + S4LZ;
  L106 → from-scratch custom Z80-autonomous driver).
- **`ENGINE_ARCHITECTURE.md` §8.1b "Level Editor Tile Budget UI."** Its per-corner /
  4-way-corner-adjacency budget model is the old graph-coloring premise; under the
  global-dedup resident pool the relevant metric is a single global tile cap, not
  per-corner adjacency. Rewrite when the editor budget UI is revisited.

---

## From §5 — Player System

### No bottom death plane — falling past the level bottom leaves the player skimming, not dying — 2026-08-12
**Surfaced during:** Knuckles C4 (glide/slide/climb) oracle verification — the controller
observed a fallen player skimming at y≈5920 (near the OJZ act-1 bottom, world height 6144)
in a **perpetual airborne state** rather than dying/respawning.
**Status (pre-existing engine gap, NOT a C4 defect):** there is no death/respawn system yet.
`Player_LevelBound` (`games/sonic4/player/player_common.emp`) already routes the bottom trip
on `EDGE_KILL` — it sets `Player_Death_Pending` (`st`) — but with the shipped `EDGE_CLAMP`
edge mode it just clamps `y` to the playable bottom and zeros `y_vel`, so the player sits at
the bottom edge airborne. The trigger point exists; the consumer (death → respawn → ring
loss) does not.
**When to revisit:** when the death/respawn system lands — it consumes `Player_Death_Pending`
and this becomes the single trigger. Until then the clamp is the intended placeholder.
**See:** `Player_LevelBound` (`.edge_kill` / `.edge_clamp`), `Player_Death_Pending`
(`games/sonic4/config/ram.emp`), spec §10 edge modes.

### Knuckles' `Disable_wall_grab` (non-grabbable walls) has no counterpart — 2026-08-12
**Surfaced during:** Knuckles C4 Task 11 (climb) research.
**Status:** S3K's `Disable_wall_grab` (`sonic3k.asm:30777`, `:31039`) lets an object mark a
wall non-grabbable so the glide catch / climb refuse it; our engine has no equivalent, so
**every** LRB terrain wall is grabbable. The climb otherwise works; this is only the
object-side opt-out.
**When to revisit:** when an object needs a non-grabbable wall (e.g. a moving platform face,
a scripted no-climb zone). It is an object flag consulted at the wall-catch (`player_climb.emp`
`Knuckles_Gliding_WallCatch`) and the two climb detach points.

### Climb tolerates a 1..3 px wall recess — DELIBERATE S3K divergence — 2026-08-12
**Surfaced during:** Knuckles C4 climb verification (user playtest, reproduced live).
**Status:** SHIPPED as a user-ruled deviation, recorded here so it is never "corrected" back.
S3K freezes the climb on any non-flush, non-ledge wall reading ("If Knuckles has encountered
a small dip in the wall, then make him stop" — `Knuckles_Wall_Climb`, `tst.w d1; bne
.notMoving`). That is safe on S3K's terrain because its climbable walls have FLAT tops, so
the wall distance jumps 0 → ≥4 in one step and the freeze band is never entered en route to
a ledge. **Our terrain has SLOPED grass tops** (ubiquitous), so the face recedes gradually
and the probe walks 0 → 1 → 2 → 3 before reaching the ledge threshold — S3K's rule then
wedges the ascent permanently, ~7 px short of the top, with no eject and no ledge.
Reproduced at the user's ledge: left face x464, frozen at y=561; the platform's top tile is
shape 29 (heights `[9,9,10,10,…,16,16]`, a slope). **The divergence:** a distance of 1..3
means "still on the wall" and the climb continues (normal ceiling gate + 1 px ascent);
freeze is reserved for EMBEDDED (dist < 0), a genuine intrusion. The ledge threshold
(`CLIMB_LEDGE_DIST` = 4) is UNCHANGED, so the ledge still fires by S3K's own test — at
y=560 the gap reads exactly 4. `x_pos` is deliberately NOT hugged toward the wall (that
would drift off `knux_latch_x` and trip the latch-drift detach). The same tolerance is
mirrored in the climb-DOWN path, where S3K's `bne` ejected on a 1..3 recess mid-descent (a
spurious fall rather than a wedge, same cause); a real wall end (≥4 / the +32 sentinel) and
EMBEDDED still detach there exactly as S3K does.
**When to revisit:** only if terrain authoring moves to flat-topped climbable walls, which
would make the divergence inert rather than wrong. See `games/sonic4/player/player_climb.emp`
header and ARCH §5.4.

### Solid object tops are floors for every player state — user principle + S3K divergence — 2026-08-12
**Surfaced during:** Knuckles C4, glide landing on the `TestSolid` platform.
**The ruling (user):** "a solid object's top is a floor and should behave like one" — for
EVERY player state, not just the standing ones. A glide landing on a platform must slide
exactly as it does on flat terrain.
**Status:** HOLDS TODAY across the glide family; recorded so a new airborne state does not
silently break it. Our solid handler (`engine/objects/collision.emp` `.solid_top`) clears
ST_IN_AIR and sets ST_ON_OBJECT **without touching the player state**, so each AIRBORNE
state must observe the bit itself or it keeps running its airborne body while parked on a
platform. The grounded half is enforced in one chokepoint instead: `Player_SensorFloor`'s
ST_ON_OBJECT early-out (`player_sensors.emp`) reports dist 0 / angle 0 / solid.

| State | On a solid-object top | Correct per the principle |
|---|---|---|
| GLIDE | `.on_object` → angle 0 → flat → PSTATE_SLIDE, x_vel preserved | yes — same as its flat-terrain landing |
| GLIDEFALL | `.dead_stop` → GROUND, velocities zeroed | yes — dead-stop IS its terrain landing |
| SLIDE | floor-follow + ledge-drop via `Player_SensorFloor` early-out; drop fires at the platform edge when the bit clears | yes |
| AIR / FLY | `Air_LandOnObject` (shared conversion, gsp = x_vel) | yes |
| CLIMB | ST_ON_OBJECT = DETACH (S3K `:31052`) | yes — deliberate, S3K-faithful |
| LEDGE | no test — mid-clamber is a scripted animation | acceptable; S3K has no test either |

**DELIBERATE S3K DIVERGENCE.** Stock S3K does NOT slide on a platform. Every solid object
routes the landing through `RideObject_SetRide` (`:42047`), which does `bclr
#Status_InAir` and calls `Player_TouchFloor` → `Knux_TouchFloor` (`:32833`), zeroing
`double_jump_flag`. The glide family runs only under mode 2 (Freespace) of `Knux_Modes`
(`:30473`, mode = `status & 6`), so clearing Status_InAir + zeroing double_jump_flag drops
Knuckles out of the glide state machine entirely — he stands up. S3K's glide never tests
Status_OnObj at all (the only two tests in the player region are the climb's detach
`:31052` and the standing/push code `:31805`); the object acts on the player from outside.
Worth noting S3K does not dead-stop him either — `RideObject_SetRide` preserves speed via
`move.w x_vel(a1),ground_vel(a1)`, landing him RUNNING at glide speed.
**When to revisit:** when a new airborne state is added — it must test ST_ON_OBJECT and
route to its own terrain-landing outcome, or it will glide-on-platform.

### Ability agency — cancels and re-entry (the C4 follow-up parcel) — 2026-08-12
**Surfaced during:** Knuckles C4 playtest; the user endorsed prototyping these.
**Status:** DESIGN + PROTOTYPE, not started. Today an ability is committal: once in
flight or a glide there is no voluntary exit but the terminal one. The parcel:
- **Tails: flight cancel** — proposed input down+jump, dropping to a normal fall.
- **Knuckles: re-glide from `PSTATE_GLIDEFALL`** on a fresh jump press, so a bailed
  glide is recoverable instead of a committed drop (S3K does not allow this).
- **Ball-cancel variant behind a DEBUG flag** for feel-testing only, so the two
  candidate feels can be A/B'd on hardware-accurate playback before either ships.
**USER RULING already given:** a cancel lands the player in the **vulnerable fall**
by default (not a curled/invulnerable ball) — the cancel buys agency, not safety.
**When to revisit:** next player-feel parcel. All three are gated on nothing.

### Slope standstill: mirror-symmetry option (abs-before-shift) — 2026-08-12
**Surfaced during:** the "Knuckles drifts off a ledge at rest" investigation, which
closed as AUTHENTIC — our `Player_SlopeResist` matches S3K clause for clause
(standing gate `|factor| >= $D`, `PHYS_SLOPE_WALK $20`, byte-identical sine table).
**Status:** OPTION, needs the user's call. `asr` floors toward −∞, so at 22.5° the
factor is −13 one way and +12 the other: the same slope drifts in one orientation
and holds in its mirror. Exactly **four angles** in the table are decided by this
rounding asymmetry — `$90`, `$91`, `$EF`, `$F0`. The minimal fix is to take the
absolute value BEFORE the shift (`(|sin|)>>3` instead of `|sin>>3|`), which leaves
every symmetric case bit-identical and only affects those four.
**Cost:** it is an S3K divergence and touches shared ground physics, so it needs a
**replay-fixture re-record** (the Sonic fixtures hash the player window).
**When to revisit:** only on a user ruling that mirrored slopes must behave alike.

### Glide / slide / climb SFX are unwired placeholders — 2026-08-12
**Surfaced during:** Knuckles C4.
**Status:** TODO markers at the code. S3K plays `sfx_Grab` ($4A) at the wall catch,
`sfx_GlideLand` ($4C) on the fall landing, and `sfx_GroundSlide` ($7E) every 8
frames while sliding. None exist in our SFX bank yet, so all three sites are
silent with a `TODO(user)` note. Sourcing audio is the **user's** decision.
**When to revisit:** when the user sources the audio; the call sites are already
in place and each is a one-line add.

> **Correction (2026-08-13, character lens sweep, seat A2).** This entry used to
> close with "(the same reason Tails' flight SFX `$BA`/`$BB` are unwired)". That
> was FALSE and has been removed: Tails' flight SFX **are** wired.
> `Fly_TickSfx` (`games/sonic4/player/player_fly.emp:368-381`) plays
> `SFXID_FLYING` / `SFXID_FLY_TIRED` on S3K's 16-frame cadence behind an
> on-screen gate and tail-jumps `Sound_PlaySFX`; `PState_Fly` step 1b calls it.
> `player_fly.emp:16` carried the same false claim ("the three deliberate
> deviations ... and the unwired SFX" — there are two) and is corrected in the
> same pass. A stale "unwired" entry in the doc every planning phase reads first
> is how finished work gets redone.

### REMOVABLE SCAFFOLDS currently in the tree — 2026-08-12
**Status:** live, deliberately. Remove before ship.
- ~~**DEBUG glide test platform** (`4ea60239`)~~ **REVERTED at the merge ritual
  (2026-08-12).** It was 8 `ObjDef_Solid` blocks in OJZ sec0 at x960-1088, top
  y=208, 48 px above the y=256 surface, added because the shipped sec0 solid is
  untestable by construction (16×16, top only 8 px above the surface, crossed in
  ONE frame by a 16 px/frame glide). It did its job — the ruled glide→SLIDE
  behaviour was verified on it and BUG 10 withdrawn — and then the strict suite
  caught why it cannot stay: DEBUG-gating made `entity_data` 48 bytes longer in
  the debug shape, and the harness enforces `debug_len == plain_len` for every
  ported section (`sigil crates/sigil-cli/tests/ojz_run_a_port.rs`). Level DATA is
  expected to be shape-identical, so a **DEBUG-only ENTITY is not expressible**;
  the ungated alternative would have changed release bytes. The invariant was kept
  and the scaffold reverted. TO RE-ADD TEMPORARILY: put the 8 records in
  `data/editor/ojz/act1/section_0.objects.json` so they land in BOTH shapes, run
  `tools/regenerate-level.sh`, and revert before merging — geometry and the
  approach recipe are preserved in the note block in `tools/ojz_entity_gen.py`.
- The replay fixtures and the DEBUG-only object-test scene are permanent test
  infrastructure, NOT scaffolds — do not remove those.

### Min-penetration-axis may misclassify fast-horizontal contacts — 2026-08-12
**Surfaced during:** BUG 10 (withdrawn — the reported case was three measurement
errors, not engine behaviour).
**Status:** DOCUMENTED, not observed in practice. `Touch_Solid` picks the contact
face by minimum penetration axis (`pen_x` vs `pen_y`). A player moving fast
horizontally and slowly vertically — a glide is 16 px/frame against 0.5 px/frame —
can first overlap a narrow platform at its leading EDGE with a tiny `pen_x`, which
classifies as a SIDE hit (push + `clr.w x_vel`, a stall) rather than a top landing.
Whether it bites depends on sub-pixel phase and platform width; on the 128 px test
platform the top landing is reliable, and the ruled glide→slide behaviour was
**verified working on an object top**. A narrow platform plus a fast approach is
the risk case.
**When to revisit:** if a stall-on-edge is ever seen in real level geometry. The
fix direction would be a swept/previous-position test rather than a static AABB —
a shared-collision change needing the user's ruling, not a local patch.

### Cycle Profiler (§8.5) Not Wired — Frame-Budget Measured via Lag Counter — 2026-06-14
**Surfaced during:** §5 Task 10.4 frame-budget pass.
**Status:** The §8.5 raster-bar / lagometer cycle profiler is NOT built.
> **⚠ PARTIALLY CORRECTED 2026-08-05 — the "written NOWHERE" claim is a FALSE NEGATIVE.**
> The `Prof_*` block **IS** written, in `games/sonic4/test/object_test_state.emp:158-195`
> (`Prof_RunObjects`, `Prof_Peak_RunObjects`, `Prof_TouchResponse`, `Prof_Peak_Touch`,
> `Prof_RenderSprites`, …) — landed all the way back in `739143f` (2026-04-25, "combined
> integration + stress test scene with profiling"), i.e. it was already wired when this entry
> was written. What is true is narrower: **the counters are unwired in OJZ gameplay**, which is
> the state the original live read at `0xFF89FC` was measuring. The headline claim ("declared but
> written NOWHERE") is wrong; the conclusion (no profiler on the gameplay path) survives.
> The §8.5 raster-bar/lagometer presentation layer is genuinely not built.

Original text: The
`Prof_*` RAM block (`ram.asm`: `Prof_RunObjects`/`Prof_TouchResponse`/
`Prof_RenderSprites`/`Prof_FrameTotal` + their `Prof_Peak_*`, DEBUG only) is
declared but written NOWHERE — confirmed live: all sixteen bytes at
`Prof_RunObjects` (0xFF89FC) read zero during active gameplay. This matches
spec §9 item 10's own note ("the §8.5 profiler is not built yet").
**Measured instead** via the wired `Lag_Frame_Count` (0xFF89F8, incremented in
`VInt_Lag` whenever the main loop misses VBlank): with the player active on OJZ,
**steady-state gameplay = 0 lag frames over 120 frames** (full game loop —
player physics + camera + render — completes within the ~224-line NTSC
active-display window before VBlank). Spindash launches at $7FA gsp added zero
lag. The only lag observed (+13 frames over a 250-frame run that crossed
terrain) was section-streaming art DMA during teleport/preload — amortized
deferrable DMA by design, not the per-frame player cost. The Task 10 camera
additions (landing lock + spindash freeze) are a few byte-tests + branches,
~10-20 cycles/frame, negligible.
**When to revisit:** Build the real cycle profiler if a future workload (dense
badnik + multi-part boss + heavy parallax) starts producing steady-state lag
frames; until then the lag counter is a sufficient pass/fail budget gate.
**See:** `docs/superpowers/specs/2026-06-12-player-system-design.md` §9 item 10.

### Removed Up-Velocity Cap — Launch-Cap Coupling (§2.1 FEEL DEVIATION) — 2026-06-12
**Surfaced during:** §5 Task 6/7 (commit 04b492b region).
**Status (intentional, shipped):** the classic non-jump airborne up-cap (`y_vel`
clamped to `-$FC0`) is **removed**. Launches are instead bounded by
`PHYS_GSP_CAP = $1000` (the SPG-placement ground-speed tunneling guard). The
`; FEEL DEVIATION` comment lives at the clamp site in
`engine/player/player_air.asm` (`PState_AirShared`, after the fall-cap).
**Coupling — do NOT change in isolation:** if launches ever feel truncated, the
knob is `PHYS_GSP_CAP`, and raising it is a **coupled** change. These must rise
together or the player will outrun streaming / tunnel through geometry:
- `CAM_MAX_Y_STEP` (16 px/frame, the camera-follow clamp the fill relies on),
- `VFILL_ROWS_PER_FRAME` (2 rows/frame — the VBlank-bound streaming contract;
  >2 overflows VBlank into active display, see §4.7),
- the 32px sensor reach (swept collision must cover one frame's travel).
Do not re-add the `-$FC0` cap silently. The separate `$FC0` cap in the
steep-landing conversion is a different, retained mechanism.

### Fall cap `PHYS_FALL_CAP = $1000` — S3K deviation, PARKED with a known 1px hole (§2.1 FEEL DEVIATION) — 2026-08-03
**Surfaced by:** Volence noticed falls feel slower than S3K. Researched + parked
the same day ("doesn't seem like something I want to get into right now") — this
entry exists so the analysis is not re-derived. Sibling of the up-velocity-cap
entry above; the two share the same coupling set.

**Provenance (settled — do not re-litigate from precedent):**
- **S3K has NO fall cap.** `MoveSprite` adds `#$38` to `y_vel` and returns, no
  clamp on the path (`skdisasm/sonic3k.asm:36041`). **S2: none** either.
- **S.C.E. DOES cap at `$1000`** (`Objects/Players/Sonic/Sonic.asm:435-437` air,
  `:508-510` jump) — and our line is a clone of S.C.E.'s, NOT a Sonic-CD import.
- **S.C.E.'s cap has no documented rationale.** Git-archaeology (2026-08-03): it
  was added in `8c6e438` "Big March update" (2024-03-09), a 92-file /
  4,535-insertion omnibus whose message says only "Objects optimization and
  fixes / New level loading header / Other fixes". The lines carry NO comment,
  though every neighbouring velocity clamp in the same routine is commented
  (`; limit upward y velocity exiting the water`, `; reduce gravity by $28`).
  No README/changelog mentions it. The one plausible motive — that it
  accompanied that commit's level-loading/size rework — was checked and does NOT
  hold (those diffs are whitespace-only). **Conclusion: S.C.E. is not evidence of
  an engineering rationale; any future argument for capping must stand on our own
  measured constraints below.**

**Our constraints (these ARE real, and they are ours, not inherited):**
- *Axis A — thin-floor tunneling (camera-irrelevant).* The probe examines two
  16px cells, so max safe per-frame Y step = `min_floor_thickness − 1`. OJZ act 1's
  thinnest floor is 16px → **safe step = 15px**, and 224 pixel-columns are that
  thin. **The shipped `$1000` (16px) is therefore ONE PIXEL HOT**: a frame ending
  with feet exactly on a 16px slab's surface (dist 0 → `bpl .no_land`) plus a full
  16px step skips the slab. Needs 577px of prior fall + exact alignment, so it is
  narrow but real, and it is in the shipped build today.
- *Axis B — collision residency (camera-coupled).* Collision reads
  `Tile_Cache_Collision`, an 80×30-cell RAM ring bounded by `Cache_Top_Row`/
  `Cache_Bottom_Row` which follow the camera; outside it every probe returns air
  (`engine/level/collision_lookup.emp:47-56`). Cells arrive only by decompressing
  block streams (`tile_cache.emp:365-375`) — there is NO directly-indexable
  collision map in ROM. **This is why S3K gets uncapped falls for free and we do
  not: S3K's layout is fully RAM-resident, so its collision is camera-independent.**

**Why a taller collision band is NOT the answer** (asked + answered 2026-08-03):
the band buys a fixed reach, but under gravity the player↔window gap grows
quadratically, so safe fall distance grows only as ~√(band size):

| slack below player | total fall before collision blackout |
|---|---|
| ~188px (today) | ~1,450px |
| ~700px (2× band) | ~2,560px |
| ~1,400px (4× band) | ~3,790px |

Quadrupling RAM buys 2.6× the fall. Fine as margin, cannot be load-bearing —
and it gets weaker exactly as levels get taller (cf. the mega-act goal).

**If it is ever picked up, the real shape is:**
1. **Swept / sub-stepped vertical movement** in `PState_AirShared` (move
   `min(STEP, remaining)` with `STEP <= min_floor_thickness − 1`, probe, repeat).
   Unavoidable for Axis A; cycles are affordable (~8 probes/frame at 48px/f vs 2
   today) — the cost is semantic: class dispatch, wall probes, `jump_headroom`
   consumption and quadrant forcing all currently assume one move per tick.
2. **Speed-scaled vertical fill** for Axis B — raise fill rate with fall speed
   rather than raising the fixed budget. Attractive because a vertical plunge is
   when horizontal streaming is otherwise idle, so the block-decompression budget
   is mostly unspent — **premise unverified, check it before betting on it.**
   Alternative (more expensive): raise `CAM_MAX_Y_STEP` + `VFILL_ROWS_PER_FRAME`
   together, which is the §4 streaming budget.
3. Housekeeping: `player_common.emp:662`'s `ensure(PBOUND_BOTTOM_MARGIN > ...)`
   references the constant and must be re-expressed if it is removed; import
   lists in `player_air.emp:12` / `player_common.emp:25`.

**Cheap option available anytime (NOT taken — user parked the topic):** set
`PHYS_FALL_CAP = $0F00` (15px/f). One-constant change, closes the Axis-A hole,
imperceptible in feel (only reached after ~540px of fall; the act's deepest
floor-terminated drop is 592px). Strictly safer than today.

**Micro-optimisation dead end (checked, do not retry):** the clamp cannot be
replaced by a bitwise op. `ori`/`andi`/`bclr` give WRAP, not saturation —
`andi.b #$0F` on the high byte turns `$1000` into `$0000`, producing a mid-air
sawtooth. Saturation needs a comparison. Branchless forms lose on 68000 (no
conditional move; shifts cost 2 cycles/bit): sign-mask ~68 cyc, `Scc`+merge
~30 cyc, vs 18 for the current `cmpi.w`+`ble`. We already clamp in a register
(S.C.E. clamps in memory, twice — we have ONE site because `PState_AirShared`
is shared). Best remaining win is 2 cycles by inverting the branch; not worth it.

### §5 Deferred Items — Player/Character Follow-Up Work — 2026-06-14 (updated 2026-06-15)
**Status:** §5 (player-system branch) shipped Sonic-only, physics-first, on OJZ
with real collision, the full sensor layer, ground/air/roll/spindash, the loop,
and camera landing lock + spindash freeze. feat/sonic-animations added the full
animation set, speed-scaled timing, and shared spindash. Per spec §1, the
following are deliberately **deferred to follow-up plans** (not bugs):
- ~~**Sonic art / animation / DPLC** — a real sprite set + animation driver beyond
  the placeholder test art.~~ **DONE (feat/sonic-animations):** full ANIM_* contract
  (11 ids, build-time assert), `Player_Animate` read-only classifier, `DUR_DYNAMIC`
  speed-scaled timing in `AnimateSprite`, shared spindash in `player_spindash.asm`,
  `Player_AtLedgeEdge` balance probe, DEBUG anim viewer. Sonic's sprite art DATA is
  the real CUSTOM Sonic set migrated from sonic_hack (`art/optimized/characters/sonic.bin`,
  mappings + DPLC; frame-index layout follows the S2 convention, but the pixels are
  our custom design — NOT stock S2). Still provisional is the VRAM SLOT —
  `VRAM_TEST_SONIC` is a hand-placed test slot, not yet allocated via the build-time
  ~~graph-color allocator~~ (separate art-pipeline task).
  **⚠ CORRECTED 2026-08-05: there is no graph-color allocator.** DSATUR/`color_sections`/
  `compute_adjacency` have zero hits tree-wide; the allocator was superseded by the
  globally-deduped paged act pool (2026-06-22) and removed in the Phase-3 cleanup. The slot is
  still hand-placed and still provisional — but whatever allocates it later, it will not be a
  graph colorer. See the corrected "Build-time Graph Coloring (§2.3)" entry.
- ~~**Spindash shared across all 3 characters** — `PState_Spindash` was in
  `sonic.asm`, blocking Tails/Knuckles.~~ **DONE (feat/sonic-animations):** relocated
  to `engine/player/player_spindash.asm`; resolves `ANIM_SPINDASH` per-character via
  the `ANIM_*` contract. `sonic.asm` now holds only `Sonic_InitAssets`, `Sonic_LoadArt`,
  `PhysTable_Sonic`.
- **In-game get-up trigger** — `ANIM_GETUP` (id 10) is defined and viewer-visible
  but nothing arms it in gameplay. A future pass needs the "just landed after a hurt"
  state to write `ANIM_GETUP` into the classifier path (or a dedicated PSTATE).
  **⚠ NARROWED 2026-08-05 — most of this shipped; only the ARMING is missing.** The classifier
  path the entry asks for **exists**: `PlayerV.getup_timer` is a real field
  (`games/sonic4/player/player_common.emp:84`), it is cleared at init (`:209`), and `:488-492`
  already runs the one-shot — `tst.b getup_timer` / `subq.b #1` / `move.b #ANIM_GETUP, anim(a0)`.
  What is missing is **the writer**: nothing sets `getup_timer` non-zero, because no hurt/landing
  state exists to set it. So this is not "build the get-up trigger" any more, it is "when damage
  ships, poke one byte". Fold it into the shields/damage work rather than planning it separately.
  **⚠ 2026-08-26 — that damage/shields parcel now carries a second passenger.** The
  insta-shield shipped with its hitbox expansion BLOCKED on exactly the same missing piece
  (see the instashield entry below for the arithmetic and the two reasons), and the
  suppression predicate it ships — `PlayerV.status_secondary & INSTASHIELD_SUPPRESS_MASK`,
  the `$73` set S3K's own `TouchResponse` spells — is a live instruction with **no writer**:
  the shield work adds writers to `status_secondary` and changes no reader. Both are named
  here so the damage parcel is planned with all three in view, not one.
- **Duck / look-up camera pan** — duck and look-up are display conditions computed
  each frame (no new PSTATE); the camera-pan half is NOT implemented. The field
  ~~`_pl_look_offset`~~ is reserved as a zero-valued seam in the `PlayerV` SST overlay
  for the future pass that wires this up.
  **⚠ ANCHOR CORRECTED 2026-08-05:** the field is `PlayerV.look_offset`
  (`games/sonic4/player/player_common.emp:86`, `// camera look/duck pan seam — stays 0 this
  pass`), cleared at `:210`. `_pl_look_offset` has **zero hits** tree-wide — that name never
  survived the port. The substance is unchanged: the seam exists, still zero, still unwired.
- **Balance threshold tuning** — `LEDGE_NO_GROUND` in `player_sensors.asm` is
  flagged as tunable; the current value is a first estimate.
- ~~**Dropdash, instashield** — Sonic move-kit extensions.~~ **INSTASHIELD DONE
  (parcel/instashield, 2026-08-26); DROPDASH still open.**
  `games/sonic4/player/player_instashield.emp` — `Ability_InstaShield` bound through
  `CharDef_Sonic.cd_ability`, the three-value `PlayerV.instashield` one-shot (S3K's
  `double_jump_flag`, reset on landing in `PHook_GroundEnter`/`PHook_RollEnter`), S3K's
  14-frame attack window, the roll-jump air-control cancel, and the flash object with
  the sonic_hack donor's 52-tile art streamed through a 29-tile DPLC window
  (`VRAM_INSTA_SHIELD`). Design + every derivation:
  `docs/superpowers/notes/2026-08-26-instashield-design.md`. Four riders below.
  - **THE HITBOX EXPANSION IS NOT BUILT — blocked on the damage system.** S3K's
    attacking box is a 48x48 REPLACEMENT of the player's touch box (`x - $18`, width
    `$30`; `y - $18`, height `$30`; `sonic3k.asm:20626-20646`), against a jumping
    Sonic's 16x22 (`x - 8`, width `$10`; `y - (y_radius-3)`, height `2*(y_radius-3)`,
    with the ball's `y_radius = $E`). The half-extent `$18` is not a magic number: it
    is `Obj_InstaShield`'s own declared `width_pixels`/`height_pixels` (`:34576`), and
    our converted mapping blob independently agrees — every visible frame's bbox is
    `(-24,+24)` on both axes. S3K also `bset`s `Status_Invincible` for the duration of
    that one sweep and restores it after, so contact resolves as a kill rather than as
    damage. **Two reasons it is not built:** (a) every handler it exists to reach is an
    `rts` stub (`Touch_Enemy`/`Boss`/`Hurt`/`Projectile`/`SolidBreak`/`SolidHurt`,
    `engine/objects/collision.emp:200-227`), so it would be unobservable — the emulator
    check "see the expanded hitbox connect" cannot be run today; (b) a blanket
    expansion would be WRONG here, because Aeon's `TouchResponse` dispatches solids,
    springs and monitors through the same AABB that S3K reserves for the damage family
    (S3K resolves solids in `SolidObject`, outside `TouchResponse`), so a 48x48 player
    box would let solid objects push Sonic from 24 px away. Doing it right means a
    PER-TYPE box, i.e. hoisting the type dispatch above the AABB in the engine's
    hottest per-object loop. **NOT via `cd_ability_wh`**: that writes
    `size_wh_off()` = `Sst.width_pixels`/`height_pixels`, which `player_sensors`
    halves into the TERRAIN sensor radii (`:343-346`, `:547`) — Knuckles' 10x10 is a
    physics box, and a 48x48 there would give Sonic a 48x48 terrain footprint. The
    state the expansion needs already ships: `PlayerV.instashield` with S3K's exact
    14-frame window, and the attacking predicate is the single comparison
    `cmpi.b #INSTASHIELD_ATTACKING, PlayerV.instashield(<player>)`.
  - **The SFX is not wired — blocked on a sound-lane import.** S3K plays
    `sfx_InstaAttack` = SFX `$42` (`sonic3k.constants.asm:1193`). Aeon's transcoded
    bank (`games/sonic4/data/sound/sfx/sfx_bank.emp`) holds 11 effects
    (`$33 $34 $35 $36 $3C $62 $AB $B6 $B9`, plus `$BA $BB` in DEBUG) and `$42` is not
    one. Adding it: run `tools/sfx_transcode.py` over the S3K source, add the
    `SfxTable` row, a `SFXID_INSTA_ATTACK` in `config/sound_ids.emp` and a
    priority-ladder tier, then re-pin the sound blob's frozen goldens. A wrong id was
    deliberately NOT substituted.
  - **The roll-jump cancel lands one frame late.** S3K's `bclr #Status_RollJump` takes
    effect the same frame (`Sonic_ChgJumpDir` re-tests the bit after
    `Sonic_JumpHeight` returns). Here the lockout is `AIRF_INPUT_LOCK`, already latched
    in the CALLER's `d6` when the hook runs, and the `AbilityHook` contract
    (`clobbers(d0-d2/a1-a2)`) forbids touching it — so `Ability_InstaShield` changes
    `PSTATE_ROLLJUMP` -> `PSTATE_JUMP` and air control returns on the NEXT frame.
    Closing it means widening the hook contract to let an ability write `d6`, which is
    a seam change under the replay gate. Not worth one frame of a lockout today.
  - **`AF_CALLBACK` is still unexercised.** `engine/objects/animate.emp`'s `$FA`
    opcode has an empty installable-target set, and the flash's end-of-attack write is
    exactly the shape it was built for. It is done in the object body instead (S3K's
    own structure, and simpler); converting it would retire the forward machinery.
- **Dropdash** — the other half of the move-kit line above, untouched.
- **Super Sonic** — transformation, palette cycle, physics row.
- **Tails** — CPU AI (4-state machine) + position-history-buffer following (the
  `Player_Pos_Ring`/`Player_Stat_Ring` are already recorded for this) + the
  twin-tail appendage child object. **Flight physics are DONE** —
  `games/sonic4/player/player_fly.emp` (`PSTATE_FLY` + `Ability_TailsFlight`,
  S3K-exact bar three flagged deviations); until the appendage object lands, the
  flight pose draws the body without its spinning tails, and the flight SFX are
  unwired because S3K's `$BA`/`$BB` are outside the imported SFX id range.
- ~~**Knuckles** — gliding, climbing, wall detection.~~ **DONE (feat/knuckles-c4,
  2026-08-12):** all five states ship — `PSTATE_GLIDE` / `GLIDEFALL` / `SLIDE`
  (`player_glide.emp`) and `CLIMB` / `LEDGE` (`player_climb.emp`), entered through
  the single `CharDef_Knuckles.cd_ability` → `Ability_KnuxGlide` pointer, plus the
  glide wall-catch. Structure and numbers are S3K's, with two user-ruled
  divergences recorded separately below (the 1..3 px climb recess tolerance; solid
  object tops as floors). Oracle-verified: wall-catch → climb → ledge top-out →
  stand, climb-down landing, glide-land → slide (~440 px travel, dust trailing),
  and slide-off-a-solid → ledge-drop → GLIDEFALL. Remaining Knuckles gaps are the
  SFX placeholders and `Disable_wall_grab` (both tracked separately).
- ~~**Per-character dispatch-table indirection** — the prerequisite refactor for
  Tails/Knuckles.~~ **DONE (character-dispatch C1, merged 2026-08-12):**
  `CharacterDef` (`engine/structs.emp`) is the ROM record and `Player_Chardef` the
  resolved cache; `Player_Init` does the ONE roster resolve. The proof it worked is
  that C4 added a whole third character — five states — with **zero** engine
  changes and no `Character_ID` test anywhere in the frame: one record field and
  two modules. See `ENGINE_ARCHITECTURE.md` §5.4.
- **Shields + damage + loss-rings** — shield objects, hit/invuln response, ring
  scatter (loss-rings is also tracked under §4.9).
- **Water** — and with it the **per-section physics modifier / Lerp system** (the
  RefreshPhysics plumbing shipped with an identity modifier; the modifier tables,
  section references, and boundary Lerp are the deferred half — see
  `ENGINE_ARCHITECTURE.md` §5.2).
- **6-button mappings** — X/Y/Z/Mode gameplay actions (detection exists, §5.1).
- **Forced-roll objects (S-tunnels)** — bypass the roll-start gate, use
  `PHYS_ROLL_FORCE_MIN` at rest; the `stick_convex` full-adherence flag and the
  roll-start gate already have the hook comments.
- **The §8.5 cycle profiler** — unwired (see the Cycle Profiler entry above).

---

## From §1 — Core VDP Pipeline

These subsystems are fully designed in ENGINE_ARCHITECTURE.md §1 but require other systems to exist first.

### Plane_Buffer "complete" guard — TRIED + REJECTED (not viable) — 2026-06-23
**Surfaced during:** continuous-scroll Phase 2 Task 6 gate (the diagonal-corruption fix, commit `b96c861`).
**Status: REJECTED.** Built + oracle-tested on branch `feat/plane-buffer-complete-guard` (commit `fb81809`, left UNMERGED for inspection). The idea was: add a `Plane_Buffer_Complete` flag set after the fill phase, gate `VInt_DrawLevel` on it, and re-add the drain to `VInt_Lag` so lag frames drain a *completed* buffer (killing the sustained-lag stutter) without the mid-fill tear. It IS corruption-safe (diagonal stayed clean across the corner), **but it is a net regression, not an improvement, for two reasons:**
1. **Plane/sprite desync.** The plane buffer completes at `Section_UpdateColumns` (ojz_scroll_test.asm:179) but the sprite table completes later at `Render_Sprites` (:188). A lag-frame drain firing in the window [179,188] commits NEW planes while the sprite table in VRAM is still LAST frame's → the world scrolls one frame ahead of the player sprite. The only desync-free drain point is "whole visual frame complete" = `VBlank_Ready` = exactly `VInt_Level` — i.e. there is NO safe lag-frame drain that also keeps sprites in sync, so the guard cannot deliver its benefit.
2. **+~10% lag.** Re-adding the drain to `VInt_Lag` extends the VBlank handler, stealing main-loop time and pushing borderline frames over: sustained-max-diagonal went 76% → 86% lag (measured).
**Conclusion:** `b96c861`'s whole-frame-defer is the CORRECT design — on a lag frame the screen shows the last *coherent* complete frame (planes+sprites together), which is the classic behavior; the "stutter" is just the framerate drop, not a fixable drain-timing artifact. The real lever for the sustained-diagonal lag is the **diagonal streaming budget** (below), not drain timing. Delete the branch if not inspecting.

### Diagonal streaming budget — ~76% lag at sustained MAX diagonal (§4.7 / §1.1) — 2026-06-23
**Surfaced during:** continuous-scroll Phase 2 Task 6 diagonal stress (PRE-EXISTING — master shows the same lag).
**Status (UPDATED 2026-08-09 — patch-run batching shipped, `perf/patchrun-batch`):** The
per-word `PageCache_PatchWord` primitive (movem-bank + jsr/rts per WORD, ~166 cycles of
bracket overhead before any work — 160 words/frame ≈ 19% of frame at terminal fall) was
replaced by `PageCache_PatchRun_Seq`/`_Col`: one register bank per RUN, map/Page_Table/
Page_Frames hoisted per run, the (only-caller) Ref/Unref bodies inlined per word. Identical
per-word semantics (capture-old-before-write, ref-new-then-unref-old, miss = Request +
stall + skip + continue); DEBUG per-frame refcount audit green through full-map churn.
Measured A/B (oracle, deterministic input replay, OJZ act1):
- **VERTICAL max fall (user-reported "BG slows where FG chunks draw"): FIXED.** Baseline
  had clustered bursts on dense strips — worst 5 lag/30 frames (17%, camera dropped 80px of
  travel that half-second). New: the same strip runs 0 lag at full 480px/chunk; whole-map
  fall 7 scattered lag frames (~1.9%), worst chunk 2/30.
- **Dense-region MAX diagonal (from spawn): improved, still saturating.** Position-matched
  traverse to camera ~1100: 54 lag/120 frames (45%) → 29 lag/90 frames, traverse 25%
  faster wall-clock. Worst dense strips still hit ~40-47% during their crossing.
**The remaining diagonal residual is unchanged in kind** — `TileCache_FillColumn`'s
per-cell copy + `Draw_TileColumn`'s nametable draw at 16px/f (2 cols/frame), plus the
per-line HScroll + BgAnim flat taxes. That is the "horizontal Wave-1 that never happened"
(the FillColumn/Draw_TileColumn hoist+SR, domain-split in campaign-gap-ledger) — now the
top lever on this line item.
**Measured 2026-08-09 (post-batching, oracle profiler, 60-frame average at max
diagonal from spawn, canonical DEBUG):** total frame 127,962/128,000 cycles —
**~100% budget, zero headroom** (lag 0 only because the window preceded the dense
strips; they tip it over). Decomposition of the fill half:
`Tile_Cache_Fill` 72.8k incl (56.9%) = `FillRow` 35.9k + `FillColumn` 28.9k, inside
which `CopyBlockColumn` 20.9k (8 calls, ~2.6k/call — the per-cell copy),
`PatchRun_Seq` 18.6k (11 calls) + `PatchRun_Col` 13.7k (10 calls) (the already-
batched patch cost, M-1-endorsed), `FindStagedBlock` 9.3k (24 calls, ~387/call),
`DecompressBlock` 3.4k (prefetch doing its job). Draw side: `Draw_TileColumn` 5.1k
+ `Draw_TileRow_FromCache` 3.3k. Flat taxes unchanged (HInt 10.8k = 8.5%,
`Parallax_Update` 6.8k, `Section_UpdateColumns` 9.6k).
**Hoist parcel scope (queued):** the copy chain (`FillColumn`/`FillRow` →
`CopyBlockColumn` → per-cell) carries ~50k/frame against the batching precedent —
same shape as patch-run: bank once per column/run, hoist the stage-slot resolve
out of the per-cell path (`FindStagedBlock`'s 24 calls/frame include repeat hits
on the same staged block), and fold the draw's nametable recompute. The P2-merge
revisit condition of the 2026-08-05 owner ruling is now met.
> **BUILT AND MEASURED 2026-08-10 — the premise above is WRONG.**
> `perf/fillcol-hoist` (T1-T5) shipped every lever in that scope and produced
> **NO measurable lag win** (3×90-frame diagonal: baseline 209 ticks/61 lag →
> candidate 207 ticks/63 lag, same 15.9 px/tick) for **+430 B ROM / +138 B RAM**.
> Correctness was clean (both replay fixtures hold with all checkpoint hashes
> matching, refcount audit green, patch runs unchanged within noise), and two
> attributable wins are real but ~1k/frame combined: `Draw_TileColumn` −14%
> (T1's gather unroll) and `FindStagedBlock` 13→11 calls (T5's memo).
> **So the copy chain's call/hoist overhead is NOT the top lever on this line
> item** — the residual is the flat decompress + patch-run + HInt taxes the
> parcel deliberately did not touch.
> **OWNER RULING 2026-08-10: take the clean win, park the rest.** T1 (the
> `Draw_TileColumn` gather unroll — the one unambiguous measured win, -14% on
> that routine, +42 B, no RAM) is cherry-picked to master as `e1367aee`
> (sigil chain 87), gated with both replay fixtures holding. T2-T5 stay on
> branch `perf/fillcol-hoist` (tip `118c184a`) as parked research: built,
> green and correctness-gated, but not worth +388 B / +138 B RAM for no
> measurable lag movement. **Do not delete that branch.** Pick-up notes +
> the re-measure prerequisite:
> `docs/research/2026-08-10-diagonal-scroll-research-parked.md`. Full evidence:
> `docs/superpowers/notes/2026-08-10-fillcol-hoist-ab.md` (+ `-baseline.md`).
> Method caveat for any re-measure: fixed-FRAME windows drift in content
> (the candidate hit ~+3.1k more cold decompress), so drive to a fixed
> camera-X and count frames instead.
**Status (UPDATED 2026-07-16 — unified prefetch shipped):** Sustained MAX diagonal now runs **~42% lag** (oracle, 8/19 frames), down from the ~76% below. The unified direction-aware prefetch (H1 column scan + H2 corner + H3 hysteresis + H4 trailing-lag gate + H5 16 slots + H6 base-lea hoist, `feat/unified-prefetch`) removed the cold-crossing DECOMPRESS spike (A/B: sustained-max-horizontal 44→27 lag, ~40% cut). **The residual is now COPY/DRAW-bound, not decompress** — `TileCache_FillColumn`'s per-cell copy + `Draw_TileColumn`'s nametable draw at 16px/f (2 cols/frame) exceed budget regardless of decompress. That is the "horizontal Wave-1 that never happened" (the FillColumn/Draw_TileColumn hoist+SR, domain-split in campaign-gap-ledger). The pre-prefetch analysis below stands as the decomposition of the remaining fill cost.

**Ruling (owner, 2026-08-05): MARK AND REVISIT — stays OPEN.** Neither accept the dip (A) nor spend on it yet; do **not** silently take (A) despite the recommendation below. Revisit alongside art-streaming Phase 2 (whose budget model touches the same frame window) or when a level actually plays at sustained max diagonal. Full ruling text: "Owner rulings, 2026-08-05" near the bottom of this file.

**Original (pre-prefetch) status:** Sustained MAX diagonal scroll (both axes at CAM_MAX=16px/frame) runs ~76% lag frames (genuine fill cost, not corruption — that's fixed). Profiler: Tile_Cache_Fill ~25% (FillRow+FillColumn+Decompress) + HInt ~24% + Process_DMA_Deferrable ~18% + parallax ~14%. The zero-slack contract `CAM_MAX_Y_STEP == VFILL_ROWS_PER_FRAME*8` was sized for SINGLE-axis motion; diagonal runs BOTH column-fill and row-fill against the shared `BLOCK_DECOMP_BUDGET=6`, roughly halving the effective per-axis budget.
**What:** Investigated 2026-06-23 (read-only profiler + code analysis). The cost is dominated by ESSENTIAL work with no significant redundancy — there is NO clean safe fix:
- `Tile_Cache_Fill` ~25% — column-fill (X) + row-fill (Y) both run, sharing `BLOCK_DECOMP_BUDGET=6`. Corner cells are NOT double-decompressed (`TileCache_FindStagedBlock` hits the staging slot). Clean.
- VBlank/"HInt" ~24% (vs ~4.6% stationary) — the **per-line HScroll DMA**: 896 B/frame (vs 112 B per-cell) queued by `Enqueue_Dirty_Buffers`, drained by `Process_DMA_Critical`. NOT for a shimmer (OJZ's `deformBg=DeformTable_Zero` is all-zeros — no deform); it carries the 4-band BG parallax AND deliberately works around a **live VDP `$0B` shadow→register propagation bug** (see the per-cell entry below). This ~20%/frame is a FLAT tax (same stationary or scrolling), so it's the single biggest lever — but NOT capturable by a config flip (proven below).
- `Process_DMA_Deferrable` ~17.5% — `BgAnim` animated-tile-band DMAs (+ any DPLC); already step-gated, all essential.
- `Parallax_Update` ~7.4% — per-line deform fill; essential.
Safe wins are small AND mostly DON'T help diagonal: an HScroll-DMA dirty-gate is near-useless here (the deform phase animates EVERY frame → buffer always dirty); skipping parallax Step-4a when vscroll is unchanged (~2%) only helps horizontal-only. So a real reduction needs a FEEL/VISUAL tradeoff — the user's call: **(A) accept the dip** (it's gameplay-rare — sustained MAX diagonal across corners; brief diagonals recover instantly; classic Sonic also slows under extreme load); **(B) lower `CAM_MAX` on diagonal** (detect dual-axis motion, cap the combined step — camera follows slightly slower); or **(C) cut non-essential BgAnim bands / parallax deform during fast scroll** (lose some visual flourish). Do NOT raise `CAM_MAX_Y_STEP` 16→24 (diagonal already saturates). Recommendation: (A) accept for now; revisit with (B)/(C) only if aggressive diagonal traversal becomes a design requirement.

### Per-cell HScroll (~20%/frame) — NOT ACHIEVABLE (per-cell can't do pixel-precise band boundaries) — 2026-06-23
**Surfaced during:** diagonal-budget investigation (the per-line HScroll DMA is the biggest single flat cost).
**Status: CLOSED — not achievable for OJZ's parallax.** Root-caused on hardware (VDP-register read, 2026-06-23). The chain:
- **`$0B` is NOT the problem.** With `deformBg` dropped, the VDP register `$0B` reads `$02` (`hscroll_mode: cell`) correctly — per-cell IS active and the shadow→register propagation works fine. The original `DeformTable_Zero` comment's "intermittent `$0B` stuck at `$03`" explanation was a **MISDIAGNOSIS**; a flush-side latch-reset "fix" (`Flush_VDP_Shadow`) was tried and changed nothing (branch `fix/vdp-mode3-propagation`, deleted).
- **The real cause is band-boundary precision.** A BG parallax band's on-screen boundary = `band_top_plane_row*8 − BG_vertical_scroll`. With smooth per-pixel vertical parallax (`vFactorBg`), those boundaries land at ARBITRARY screen lines (measured the per-line table putting one at **line 22**). Per-cell mode can only change scroll at 8-px cell-rows (lines 0,8,16,24…), so it rounds line 22 → 16/24, misaligning each band by up to 7 px → the FG/BG **tears at every band boundary during scroll** (user-confirmed at Cam `$02D0,$019D`; reproduced in free-fly).
**What:** Nothing — per-line (`DeformTable_Zero`) is mandatory for smooth banded vertical parallax and stays. The only way to use per-cell would be to give up smooth vertical scroll (chunky 8-px-stepped vscroll), which is not worth ~20%. Do NOT re-attempt the per-cell switch. Lesson: a settled/at-rest frame HIDES scroll-time tearing — verify under continuous motion ([[feedback_verify_during_motion]]), and read the actual VDP register before theorizing about propagation.

### ✅ CLOSED — Parallax fill — the unroll lever (§4.6 perf) — 2026-07-14 — **taken 2026-08-20 in the SAMPLING loops; the 08-09 "already shipped" closure was half right and half wrong**

> **2026-08-20 VERDICT (`perf/parallax-unroll`, the streaming arc's coda parcel).** Both
> earlier rows are now superseded. What each got right:
>
> * **The 08-09 closure was right about the flat path.** `.lp_flat` is 8x unrolled, the
>   "224-iteration `move.l/dbf`" this entry originally targeted does not exist, and at the
>   shipped shape the flat path covers only ~80 of 224 lines and is worth ~240 cycles. Do not
>   re-take it.
> * **The 08-09 closure was WRONG to dismiss the sampling paths.** It parked them with
>   "(which OJZ does not currently hit)". **Parcel W's world-anchored overlay made that false**
>   — the shipped `ParallaxConfig_OJZ_Underwater` samples BG for 144 of 224 lines at the idle
>   camera and ~176 under sustained max diagonal, because `pcfg_anchor_dsb` switches sampling
>   on below the split. That is where the walker's time was: `Parallax_Fill_PerLine` measured
>   **17,310 cyc/frame at max diagonal, 13.6% of the whole frame**, at 90 cycles per sampled
>   line. The lesson is the general one: a closure that rests on "current content does not hit
>   this" expires the moment content changes, and nothing re-checks it.
>
> **What shipped.** `.band_fg_only` and `.lp_bg` rewritten: pointer-walk the deform curve
> instead of recomputing `(phase + line) & $FF` and indexing (with the run split at the
> 256-byte wrap — at most one split per band, since 224 lines run against a 256-byte curve);
> the sampled channel's base scroll unpacked into its own word register once per band; 8x
> unroll plus remainder tail. **90 → 43.25 cycles per sampled line.** `.lp_both` was left
> alone — two sampled channels need two walk pointers and there is no second free address
> register — which also leaves the walker model's `line_both` term as an unchanged control.
>
> **Measured** (`tools/streaming_choke_probe.py`, 3 boots, spread 0.000 on `frames/tick` at
> every state): max-diagonal **work/tick 134,521 → 123,016 (−11,505)**, against a success
> criterion of −6,521 — the arc is **4,984 cycles under the 128,000-cycle frame**.
> `frames/tick` 1.240 → **1.192**; `right` and `down` hold 1.000 and both got cheaper. The
> tick did NOT reach 1.000 and CHOKE-DIAGNOSIS §8 F7 explains why that is a finding about the
> arc's criterion (the `ceil` model is a floor on `frames/tick`, not a value) rather than a
> shortfall.
>
> **Value identity** was proved by a gate that did not previously exist —
> `tools/parallax_hscroll_identity.py`, all 896 bytes of `Hscroll_Buffer` over 24 frames on a
> 10-fixture matrix, all byte-identical. Nothing in the tree had ever observed that buffer.
>
> **Micro-levers still NOT taken, and still not worth it:** the `movem.l` broadcast fill for
> flat bands (~2 cycles/long, ~160 cyc/frame at the shipped shape) and a computed-jump
> (Duff) entry in place of the remainder tail (~60 cycles per band). Both were designed and
> declined during this parcel; the unroll's win came from the pointer walk and the register
> unpack, not from the jump table the original entry named.
>
> **A newly named model parameter** came out of it: a ~149-cycle fixed cost per sampled band
> (the hoisted setup). See `benchmarks/scanline-p2/WALKER-MODEL.md` §9 — it carries an ASK to
> add the column to `tools/parallax_cost_probe.py`.

> **2026-08-09 reconciliation (historical):** the premise is stale — `Parallax_Fill_PerLine`'s flat
> (constant-span) path is ALREADY 8×-unrolled (`.lp_flat`: span is always a multiple of 8
> because band tops are cell rows ×8, so eight `move.l d0,(a4)+` per `dbf`). Measured
> (oracle profiler, max fall): the whole per-line fill runs ~3.9k cycles ≈ 3.1% of frame —
> which is exactly the all-flat cost, i.e. OJZ's zero-deform bands already take the cheap
> path and the "224-iteration move.l/dbf with ~2,200 cycles of dbf overhead" this entry
> targeted no longer exists. Remaining micro-levers, noted for completeness and NOT worth
> their complexity today (~0.5% of frame): movem.l 8-register broadcast fill for flat bands
> (Gunstar Heroes precedent, `disasm.asm:4268` — 32 bytes/instruction, ~9.3 c/long vs 12)
> and Batman-style computed-entry unrolled deform bodies for the sampling paths (which OJZ
> does not currently hit). Reference survey: 2026-08-09 fast-copy/fill research pass
> (Batman/Gunstar/Alien Soldier/Ristar findings recorded in the git history of this entry's
> closing commit).
**Surfaced during:** TheBlad768 survey (S.C.E. updated `DeformScroll`, unreleased) — see `docs/research/2026-07-14-theblad768-survey.md`.
**Original text (historical):** `Parallax_Update`'s per-line fill (~7.4% of frame under max diagonal, per the diagonal-budget profile above) runs a 224-iteration `move.l/dbf` loop; the `dbf` alone is ~10 cycles/line ≈ ~2,200 cycles/frame of pure loop overhead. Replace the constant-span inner loop with a computed jump into an unrolled `move.l d1,(a2)+` run (`jmp table(pc,d0.w)`, entry offset `(224-N)*2`) — Duff's-device style, ~448 bytes ROM per body.

### ✅ RESOLVED — BG_TILE_CAPACITY reconciliation (512 → 448) + BG_Init guard (§2 A.5) — 2026-06-23
**Surfaced during:** continuous-scroll Phase 2 Task 5 doc-sync (PRE-EXISTING cross-tool inconsistency the SAT relocation left behind).
**Status:** The SAT was relocated to $B800, making it the BG region's hard ceiling — usable BG space is $8000-$B7FF = **448 tiles**, not the nominal 512 ($8000-$BFFF, which now overlaps the SAT). The value is inconsistent across the pipeline: `tools/inject_editor_bg.py` already uses 448 (correct), but `constants.asm BG_TILE_CAPACITY` and `tools/ojz_strip_gen.py BG_TILE_CAPACITY_PY` still say 512. **PARTIALLY ADDRESSED 2026-06-23 (commit 0aab611):** `engine/level/bg.asm` `BG_Init` now CLAMPS the blob copy to `BG_TILE_REGION_BYTES` ($8000-$B7FF), so it can no longer spray into the SAT (the runtime last-line guard). OJZ is safe today (340 tiles ≤ 448). **RESOLVED 2026-06-23 (Engine Phase 3 Task 2):** both `constants.asm BG_TILE_CAPACITY` and `tools/ojz_strip_gen.py BG_TILE_CAPACITY_PY` now gate at 448; the full build passes at the tightened gate. A too-large BG blob now fails at generation (the `ojz_strip_gen.py` assert) instead of being silently runtime-clamped.
**What:** Reconcile the gate to 448 in `constants.asm` AND `tools/ojz_strip_gen.py` (the latter is auto-commit-daemon-watched — coordinate with the user, do NOT hand-edit autonomously). Add a runtime/build guard in `BG_Init` (or an AS assert) that the BG blob ≤ `VRAM_SPRITE_TABLE - BG_TILE_BASE_VRAM`, so a future >448-tile blob fails loudly instead of silently spraying into the SAT.

### ~~Editor-export Act descriptor format drift (§8 tooling)~~ — **VOID 2026-08-05 (the artifact was deleted)** — 2026-06-23
> **⚠ VOID — the file this entry is about no longer exists.** `46c2e0f` (2026-08-01, "Parcel J:
> delete the parked ojz editor exports (#25/#26/#27)") deleted the parked export directory, so
> `data/editor/ojz/act1/export/act_descriptor.asm` is gone and there is no stale descriptor left
> to drift. The entry additionally cites `main.asm:198` — **`main.asm` itself is deleted** (the
> ROM layout is now the declared sigil map, `games/sonic4/map.toml`).
>
> **What survives as real work:** the *belt-and-suspenders* half at the end of the entry — an
> assert that an emitted descriptor's size equals `Act_len`, so any future hand-written or
> re-exported descriptor fails the build instead of silently mis-parsing. That is still worth
> having and is now the only actionable content here. The exporter-rewrite half is moot until
> an exporter is rebuilt, and the direction of travel recorded elsewhere in this file
> ("editor authors JSON, BUILD generates engine format") says it should not be rebuilt in place.
>
> Historical text below.

**Surfaced during:** continuous-scroll Phase 2 final review.
**Status:** `data/editor/ojz/act1/export/act_descriptor.asm` is git-tracked but NOT in the build include graph (`main.asm:198` includes only `data/levels/ojz/act1/act_descriptor.asm`, which IS correct), and it would not even assemble as-is (e.g. a path where a symbol is expected). So it is no build/runtime risk. But it still emits the OLD Act layout: the removed `cam_min_x/max_x/min_y/max_y` 4-word camera block, no `edge_mode` byte/pad, and pre-paging art fields — mismatched to the current `Act_len=$22`. This dir is auto-commit-daemon-watched (do NOT hand-edit autonomously).
**What:** Update the editor EXPORTER tool to emit the current Act format (no cam bounds, `edge_mode` + pad, `act_art_pool_table`/`pages`) so a future regeneration can never reintroduce the obsolete layout into the build. Coordinate with the user (daemon-watched path). Optional belt-and-suspenders: add an AS assert at the `OJZ_Act1_Descriptor` site that the emitted descriptor size equals `Act_len`, so ANY drifting descriptor (hand-written or exported) fails the build instead of silently mis-parsing.

### yflip/xyflip size+link word merge in the sprite emit loop (§1.2 perf) — 2026-08-03 — **UNBLOCKED, verification-bounded**
> **2026-08-05 reconciliation:** confirmed accurate and confirmed unblocked. `size_link` is live at
> `engine/objects/sprites.emp:568`, called at `:668`; the dead-constraint note is at `:539`.
> Nothing gates the change — the entire remaining cost is **SAT byte-identity verification for the
> yflip/xyflip variants**, which is emulator work. Piggyback it on any session already doing
> SAT-level oracle checking, exactly as the entry says.
**Surfaced during:** sprites H2 quality review (parcel/bug005-sprites-player).
**Status:** H2 merged the size+link SAT write into one word write for unflipped/xflip
(~12 cycles/piece). yflip/xyflip kept the byte-wise form, but the constraint that
forced it (the front-loaded size read) died with the stream-order restructure —
`y_term(1)`'s size peek is now NON-consuming, so the merged form applies to those
variants too (~8 cycles/piece on yflip pieces).
**What:** Switch `size_link(1)` to the merged word form; verify SAT byte-identity for
yflip/xyflip (piggyback on any session that already does SAT-level oracle checking).
**See:** `engine/objects/sprites.emp` `size_link` header comment.

### Static Sub-Sprite Array — Render-Path Optimization (§1.2 / §3.5)
**Surfaced during:** §1.2 multi-sprite implementation Task 8 research (2026-04-27).
**Status:** Implementation shipped with sibling-chain walk per spec; the static-array
optimization is logged here as a real follow-up, not just research backlog.
**What:** Sonic 3K (`s3.asm:29940-30024`) and S.C.E. (`Render Sprites.asm:259-292`)
both use a **static sub-sprite array** (count + per-child X/Y/frame triplets) embedded
in parent's object data, not a sibling-pointer chain. ~10 cycles/child saved (no
null-check, tighter loop) plus simpler render-time logic. Our `sibling_ptr` chain is
already wired to `CreateChild_*` / `DeleteChildren` lifecycle, so the trade-off is:
(a) keep chain for lifecycle + duplicate to a render array (data-sync risk), or
(b) replace chain with array and refactor all `CreateChild_*` / `DeleteChildren`.
**When to revisit:** When we have a real workload showing the per-child cycle cost
matters — multi-part bosses with 6+ children, Tails-tail-style trails, formation
enemies, etc. Premature without that signal.
**See:** `docs/research/sprite-system-§1.2.md` Task 8 for the cross-engine evidence.

### ~~Sprite Rendering Pipeline (§1.2)~~ — DONE 2026-04-27
**Completed in:** §1.2 sprite-system multisprite + piece-overflow plan
**What:** Most §1.2 features (two-phase render, priority bands, overflow cascade, scanline budget, sprite mask, link-order cycling, dirty-flag DMA) shipped during §3 Object System work. Remaining bullets closed in this plan: (a) multi-sprite batching via Approach 1 + semantic C — Draw_Sprite child-skip guard for parents with `RF_MULTISPRITE`; Render_Sprites walks `sibling_ptr` chain after parent emission, indexing parent's `mapping_frame` against each child's own `mappings`; mid-chain overflow skips just the offending child. (b) `sprite_piece_count` byte at SST_$2D for predictive total-piece overflow skip; populated by Load_Object (initial frame) + AnimateSprite (per frame change via new `RefreshSpritePieceCount` helper). (c) `Render_Sprites` factored emission into reusable `Emit_ObjectPieces` subroutine. (d) ENGINE_ARCHITECTURE.md §1.2/§3.5 link-chain doc corrected — "never rebuilt" was a wash on 68000.
**Test:** TestParent + 3 children renders identically with `RF_MULTISPRITE` on (Task 8) vs off (Task 7 baseline). Sprites_Rendered observed at 49 in stress scene; pre-check + per-piece dbeq layered defenses in place.
**See:** `docs/superpowers/specs/2026-04-27-sprite-system-design.md`, `docs/superpowers/plans/2026-04-27-sprite-system-multisprite-and-piece-overflow.md`, `docs/research/sprite-system-§1.2.md`.

### ~~Scroll / Plane Drawing — Core (§1.3)~~ — DONE 2026-04-25
**Completed in:** §4 Phase 1 Level/World System
**What:** Deferred Plane_Buffer (1536 bytes), Draw_TileColumn/Row, VInt_DrawLevel with autoincrement $80 column mode, overflow protection, pre-computed nametable strips.

### ~~Scroll / Plane Drawing — Dual Plane / Row Updates (§1.3)~~ — **DONE / RESCOPE-OR-DELETE 2026-08-05**
> **⚠ CORRECTED 2026-08-05 — every component this entry lists now exists.**
> - `Draw_TileRow` shipped as **`Draw_TileRow_FromCache`** (`engine/level/plane_buffer.emp:219`),
>   called twice from `engine/level/section.emp:628,667`.
> - **Plane B scroll support** shipped — Plane B is owned by `engine/level/bg.emp`.
> - The stated blocker ("vertical section support / §4.2 vertical section teleport") is doubly
>   void: vertical streaming shipped, and **section teleport itself was deleted** (see the
>   teleport-cluster correction under §4).
>
> The only bullet with any life left is "double-update mechanism for fast travel", and that is now
> just a restatement of the streaming budget work tracked under the diagonal-budget entry.
> **Recommendation: delete or rescope this entry the next time §1 is touched — do not plan from it.**
> Original text below.

**Blocked by:** Vertical section support (§4.2)
**What:** Plane B scroll support, Draw_TileRow for vertical section transitions, double-update mechanism for fast travel.
**When ready:** After §4.2 adds vertical section teleport.

### DPLC Lookahead (§1.6) — **✅ UNBLOCKED 2026-08-05**
> **Blocker discharged.** The §3 object system is fully built: `engine/objects/animate.emp` and
> `engine/objects/dplc.emp` both exist and ship, so "AnimateSprite and DPLC tables" — the stated
> dependency — is satisfied. Clean pick-up; the design below still reads correctly against the
> current code. Listed in the NOW UNBLOCKED section.
**Blocked by:** Object System (§3) — specifically AnimateSprite and DPLC tables
**What:** Predictive art loading by peeking at next animation frame's DPLC requirements one frame early. Queue as Important-priority DMA.
**When ready:** After §3 defines animation system with frame scripts and DPLC mappings.

### Adaptive DMA Byte Budget (§1.1)
**Blocked by:** Real workloads from gameplay systems
**What:** Per-frame DMA byte tracking, lag-frame budget reduction, lag recovery 1.5x burst. Self-tuning throughput based on scene complexity.
**When ready:** After enough consumers exist to generate meaningful DMA load (character art streaming, level tile loading, animated tiles).

### ~~Variable HScroll DMA — Infrastructure (§1.1)~~ — DONE 2026-04-25
**Completed in:** §4 Phase 1 Level/World System
**What:** Hscroll_Dirty_Start/End tracking, Hscroll_Update fills 28 per-8-row bands from Camera_X.

### Variable HScroll DMA — Variable-Length Transfer (§1.1) — **BLOCKER DISCHARGED, INFRASTRUCTURE GONE**
> **⚠ TWO CORRECTIONS 2026-08-05, pulling in opposite directions.**
> 1. **The blocker is discharged.** "Confirmed performance need" is exactly what this file's own
>    diagonal-budget entry supplies: the per-line HScroll DMA is **896 B/frame**, measured at
>    **~20% of the frame**, and the file names it "the single biggest lever" and "a FLAT tax (same
>    stationary or scrolling)". It is no longer waiting on evidence.
> 2. **The infrastructure it assumes was DELETED.** The entry (and the `~~DONE 2026-04-25~~`
>    infrastructure entry above it) both key on `Hscroll_Dirty_Start`/`Hscroll_Dirty_End` —
>    **zero hits tree-wide.** Only `Hscroll_Buffer` survives (`engine/ram.emp:195`). The
>    dirty-range tracking has to be **rebuilt**, not merely consumed.
>
> Net: unblocked, but it is a build-it-then-use-it, not a wire-up. **Also read the caveat that
> already killed the neighbouring idea:** the diagonal-budget entry measured an HScroll-DMA
> dirty-gate as "near-useless" under deform, because the deform phase animates every frame so the
> buffer is always dirty. A dirty-*range* transfer is a different mechanism from a dirty-*gate*
> and is not obviously subject to the same objection — but establish that before committing.
**Blocked by:** Confirmed performance need (currently always DMAs full 224-line table)
**What:** Use Hscroll_Dirty_Start/End to DMA only the dirty scanline range instead of all 896 bytes.
**When ready:** When HScroll partial updates become a measurable DMA budget issue.

### Background Work / Cooperative Multitasking (§1.5 → §9.7) — **✅ RESOLVED — EXECUTED as art-streaming Phase 2 (2026-08-09)**
> **RESOLVED 2026-08-09 (`feat/art-streaming-p2`, chains 55→78; merged to master `2f047e3`).**
> §9.7 was designed AND SHIPPED — not as the user-mode cooperative-multitasking split this entry
> named, but as its ratified replacement: the **pre-chunked pages + VBlank supervisor bookmark**
> idle-time path (ARCH §9.7 rewritten in place, D4=A). A resumable stack-flat ZX0 decoder
> (`ZX0R_Decompress`) is sliced across `VSync_Wait` idle by a VBlank register-bank/resume, feeding a
> VRAM page residency cache. All three downstream items this entry gated are discharged: the
> art-page consumer is live; ZX0 mid-gameplay decode rides the bookmark (never synchronous); S4LZ
> streaming (§2.1) inherits the same pipeline (that entry rescoped below). The user-mode variant is
> recorded as **rejected** in ARCH §9.7. Plan: `plans/2026-08-08-art-streaming-phase2-v2.md`.
> **Original entry retained below for provenance.**
>
> **Blocker discharged 2026-08-05.** "When §9.7 is designed and the S4LZ decompressor exists" —
> **both decompressors exist and ship** (`engine/compression/`, S4LZ + ZX0).
>
> **This is the single highest-leverage unlock in the document** because it is the *sole* remaining
> gate on three independent downstream items, each of which names it explicitly:
> - **S4LZ Streaming Mode (§2.1)** — "Blocked by: §9.7 Cooperative Multitasking".
> - **ZX0 needs budgeted decode before any mid-gameplay use** — ~76 KB/s, ~5 frames synchronous
>   for a 6.3 KB blob; the entry's stated resolution is "route them through §9.7".
> - **Art-streaming Phase 2** — binding amendment #1 promotes resumable decode from tunable to
>   *requirement*, and `2026-07-02-art-streaming-phase2-design.md` §3 names the
>   supervisor-bookmark pattern as the vehicle.
>
> Nothing else here unlocks three items at once. Note the design has moved on since this entry was
> written: amendment #1 was superseded on format (ZX0 + raw-direct hybrid, not S4LZ pages), but
> **the resumable-decode requirement survived that supersession and is now format-independent** —
> so read the Phase-2 spec, not this stub, for the shape.
**Blocked by:** Full design of §9.7
**What:** Supervisor/user mode context switching for background S4LZ decompression in leftover CPU time.
**When ready:** When §9.7 is designed and the S4LZ decompressor exists.

### HUD Dirty Flags (§1.4)
**Blocked by:** HUD system (part of §9.13 screen/menu system)
**What:** Per-element dirty flags (score, rings, timer, lives) to skip HUD VDP writes on frames where nothing changed.
**When ready:** After HUD rendering exists.

---

## From §2 — Art & Compression Pipeline

### Art-streaming Phase 2 — binding amendments from the 2026-07-01 loading audit — **✅ RESOLVED (EXECUTED 2026-08-09)**
> **RESOLVED 2026-08-09 (`feat/art-streaming-p2`, chains 55→78; merged to master `2f047e3`).**
> Phase 2 shipped and every binding amendment below is discharged or superseded, as executed:
> (1) resumable decode is a requirement and shipped format-independent as `ZX0R_Decompress` — pages
> are ZX0 + raw-direct hybrid, 64 tiles; the S4LZ-page format half was already superseded 2026-07-02.
> (2) the pool is now a VRAM residency cache capped by ROM not VRAM (`ART_POOL_PAGE_TILES = 64`,
> manifest v2, per-section local→global indices) — the ~700-850-tile ceiling no longer bounds an act.
> (3) stress-validated under sustained max-diagonal on the `--stress-uniquify` 2600-tile / 41-page
> fixture (window ≪ pool): `Lag_Frame_Count = 0` across every leg, zero wrong-tile frames,
> `Dbg_Cam_Clamp_Frames = 10` total; honorable degradation is the camera soft-clamp (Task 10).
> (4) adopted verbatim — B&R per-act art budget word (Task 9), Vectorman dual cap entries+bytes
> (Task 8). (5) the mega-act showcase depends on this plus floating-origin; its remaining blocker is
> the pre-DAC ROM-layout hole (see the NOW-UNBLOCKED item 7 mega-act ROM-layout entry) — not a
> streaming gap. Plan: `plans/2026-08-08-art-streaming-phase2-v2.md`; ARCH §9.7 + §2 rewritten.
> **Original amendments retained below for provenance.**

**Surfaced during:** the 3-agent post-leapfrog loading audit (2026-07-01; best-in-class comparison vs S2/S3K/S.C.E./B&R/Vectorman/Gunstar/Alien Soldier/TF4/Ristar + SGDK/Tanglewood/homebrew). The shipped Phase 1 (fully-resident deduped pool) was ratified correct and best-in-class; these bind the NOT-yet-built Phase 2 (residency cache / streams-past-VRAM) of `docs/superpowers/specs/2026-06-22-act-art-streaming-design.md`:
1. **Mid-game page streaming MUST use small (~64-tile) S4LZ pages + resumable decode; ZX0 stays init-only.** → **FORMAT HALF SUPERSEDED 2026-07-02** by `docs/superpowers/specs/2026-07-02-art-streaming-phase2-design.md` §4: measured on the real deduped OJZ pool, S4LZ pages reach only 86% ratio (vs ZX0 57.8% — global dedup removes the redundancy S4LZ needs), and the supervisor-bookmark resumable decode (spec §3) removes the fits-per-frame premise this amendment was built on. Phase-2 pages are **ZX0 + raw-direct hybrid, small (~64-tile)**; the *resumable decode* requirement stands, now format-independent. Original rationale (for the record) — CPU is the binding constraint, not DMA: one 8KB ZX0 page ≈ ~620K cycles (~5 frames of total CPU) vs ~1 VBlank of DMA — physically impossible at 16px/frame scroll. S4LZ at the measured 510-640 KB/s closes the worst-case envelope at ~17-22% of a frame. Promote from spec-§8 tunable to requirement. Resumable = the S3K V-int bookmark pattern (ARCH §9.7 coop multitasking is the designed vehicle — make it the page-loader contract). Precedent: S2/Sonic 3D stored streamed art uncompressed; S3K time-sliced Kosinski.
2. **Effective FG pool budget is ~700-850 tiles** after BG (448) + character DPLC + HUD/ring/monitor permanents — S3K-maximalist acts (1000-1500 tiles) will NOT fit fully resident. Phase 2 is core roadmap, not an "unlimited levels" garnish.
3. **Stress-validate Phase 2 under sustained MAX DIAGONAL scroll** — parallax (~20%) + dual-axis block fill + art decode contend for the same idle pool (~76% lag already at max diagonal, see §1 diagonal-budget entry). Honorable degradation: S3K-style gate (brief camera soft-clamp at a worst-case seam).
4. **Adopt from the corpus:** B&R's per-act art/DMA byte budget (a descriptor word reloaded per frame, not a global constant); Vectorman's dual cap (entries AND bytes per frame) on the DMA queue.
5. **Motivating showcase (user goal, 2026-07-10): the multi-zone "mega-act" tech demo** — several classic zones (or a whole game's worth) as one seamless act, no score-tally/camera-lock transitions. Zone themes live in separate pool pages; seams are transition corridors built from shared/neutral tiles where page swaps stream behind the player (the S3K PLC-during-transition pattern, corridor-loading style). Depends on: Phase 2 page streaming (this entry) + floating-origin rebase (§4.11) for the coordinate span. Per-section palettes/parallax/entities already scale. Constraint to author around: zones hand off through corridors, never interleave at fine grain.
**All 7 audit bugs were fixed + merged same day** (blank-slot-0 pin, 960 ceiling assert x2, numeric page enumeration, column-guard off-by-4, marker relocation + PIO int-mask, grid $8000 assert). Remaining small backlog: orphaned teleport-era RAM (`Section_Fwd/Bwd_Neighbor_Data`, `Tile_Override_Table`, `Pos_table`, `H_scroll_frame_offset`, `Camera_Lookahead`), dead `Plane_Buffer_Reset`, ~~`Section_RedrawPlanes` PIO without stopZ80 (convention deviation, currently safe)~~, stale comment at `plane_buffer.asm` "Called with Z80 already stopped by VInt_Level / VInt_Lag", Aurora still exporting the dead parity-model `vram_bases.asm` (ROM ignores it; editor schema drift — see the §8 editor-export entry).

> **⚠ BACKLOG LINE CORRECTED 2026-08-05 — one of these six is DONE.**
> **`Section_RedrawPlanes` PIO without stopZ80 is RESOLVED.** The routine now owns its own Z80
> posture in *both* build shapes — flag bracket with sound on, whole-storm bus hold with sound off
> — documented at the call site (`games/sonic4/test/ojz_scroll_test.emp:171`), which explains that
> the call is deliberately BARE because a caller-side hold would be a FALSE lock. Not a convention
> deviation any more.
>
> The other five **remain genuinely open and were re-verified**: `Tile_Override_Table` still exists
> with no writer (`engine/ram.emp:398`, 96 B), the orphan teleport-era RAM is still orphaned, dead
> `Plane_Buffer_Reset` and the stale `plane_buffer.emp` comment both survive, and the Aurora
> `vram_bases.asm` export is still dead. Note the last one's cross-reference now dangles — the §8
> editor-export entry it points at is itself VOID (its artifact was deleted by `46c2e0f`).

### ~~§2 A.5 T2/T3 — Per-Section BG~~ — VERIFIED 2026-04-27
**Engine paths proven end-to-end** via temporary fixtures in OJZ Act 1, then reverted. Production ships pure T1.
**T2 verified:** `sec_bg_layout` ≠ NULL → `BG_RedrawForSection` blits the section's authored layout to Plane B on teleport. Tested with sec1 = byte-identical zone copy (proved redraw doesn't corrupt content) and sec3 = palette-tinted variant (proved swap visually).
**T3 verified:** sec5's BG layout referenced an in-section VRAM slot (color base 0, tile 5) tiled across all 64×32 cells. After A.4 streaming loaded sec5's tile pool, the BG correctly rendered tile 5 from sec5's region — not the shared 1024+ region. Proves `BG_RedrawForSection` works for any tile_index, regardless of source.
**T1 fallback fix:** `BG_RedrawForSection` originally skipped when `sec_bg_layout` was NULL, which meant T2→T1 transitions kept the prior section's BG. Now falls back to `Act.act_bg_layout` so every transition writes the correct content.
**For real T2/T3 use:** author per-section BG layout files, BINCLUDE them, set `sec_bg_layout` in the section descriptor. The build tool's `emit_bg_tile_blob` already accepts a list of nametables and unions their referenced tiles — no CLI flags or stubs needed.
**Plan:** `docs/superpowers/plans/2026-04-26-art-pipeline-phase2-A5-per-section-background.md` (Tasks 7-10 superseded by inline verification).

### §2 A.5 — Section_Check d0-Clobber Bug — FIXED 2026-04-27
**Status:** `preload_fwd` / `preload_bwd` in `engine/level/section.asm` clobber d0 to build a section offset, but `.threshold_check` assumed d0 = Camera_X high word. After preload fired, the threshold check read garbage d0, frequently spurious-triggering BWD teleport (`d0 ≤ $200` accidentally true). Fixed by reloading Camera_X at the top of `.threshold_check`. Was masking BG verification work.

### §2 A.5 T1 — FG Plane A Tile-Flip Mismatch vs sonic_hack — **EMULATOR-GATED (cannot be settled statically)**
> **2026-08-05:** left open deliberately. This entry's own "Needs:" line already says what it
> needs — a live A/B with two emulators paused at the same screen comparing VRAM bytes. It is on
> the CANNOT-BE-SETTLED-STATICALLY list at the top so nobody re-derives the build-tool math a
> fourth time; that half is already verified correct. It blocks nothing.
**Status:** Architectural milestone shipped, but Exodus's Plane A nametable viewer shows tile-orientation differences between our build and sonic_hack's running OJZ. Build-tool math verifies correct (chunk-level X/Y flip per sonic_hack ProcessAndWriteBlock + dedupe canonicalization + strip remap), so the residual gap is likely in Exodus viewer rendering details (CRAM shadow mode, palette auto-selection) rather than build-tool output — but that's not confirmed.
**Needs:** Live A/B diagnostic with sonic_hack paused at OJZ Act 1 + our build paused at the same screen, comparing specific VRAM tile bytes.
**Doesn't block:** anything; T1 architecture is solid and BG renders correctly.

### ~~§2 A.x — FG Strips Have Wrong Content in Upper Rows~~ — RESOLVED 2026-06-11 (re-test)
**Resolution:** Does not reproduce on current master. Live Exodus verification: at camY=0 over sec0/sec1's
empty top chunks, Plane A row 0 is fully transparent across all 64 cells (blank tile $C6, no priority);
where dirt IS rendered (camX=$EB0/camY=$290 → sec1 chunk rows 1-2, cols 9-11), the on-screen content
matches the source layout cell-for-cell (empty sky chunk over 28/$1D ground chunks). Two findings:
(1) hypothesis (b) was half-right — sec1's layout genuinely has dirt chunk $1D across chunk-row 0
cols 7-15 (editor data AND sonic_hack OJZ_1_sec1.bin agree), so "brown in the sky" at world Y<128
in sec1's right half is faithful level data, not a bug; (2) the "all 64 cells filled" misplacement
was a strip-era streaming artifact — the strip pipeline was deleted and replaced by the 2D block
tile cache (2026-06-10 rewrite), which renders correctly.
Original entry (for reference): As Camera_X scrolled into sec1+, Plane A's upper rows rendered
dirt/rock chunk content with priority set (0xC846, 0xC04C — pal 2), filling the sky region; row 0
had all 64 cells filled, not just slot 0's half.

### ~~§2 A.x — BG Tiles Render Black via Palette Index 0~~ — CLOSED 2026-06-11
**Resolution:** Was contingent on the FG-rows bug above ("resolves automatically once the FG-rows bug
is fixed"). With FG rendering verified faithful to source data, remaining black pixel-0 outlines on BG
tiles only appear where the FG is *supposed* to be transparent — that's the authored art, same as
sonic_hack. No engine work to do.



### ~~Generic Perform_DPLC Routine (§2.1 / §3.9)~~ — DONE 2026-04-25
**Completed in:** §3 Object System audit cleanup
**What:** Perform_DPLC with internalized change detection (SST_prev_frame), Important and Deferrable variants. Objects pass a2=DPLC table, a3=art base, d1=VRAM dest.

### Dynamic VRAM Allocator (§2.2) — **UNBLOCKED, BUT THE PREMISE MAY BE MOOT**
> **⚠ 2026-08-05 — blocker discharged, premise questioned.** The stated blocker (§3 Object System,
> `Load_Object` lifecycle) is satisfied: `engine/objects/load_object.emp` exists and ships, as does
> the rest of `engine/objects/`.
> **But do not plan straight from the 2026-04 text.** It was written when art was expected to swap
> per section. The engine now ships a **fully-resident globally-deduped paged act pool** loaded
> once at init, which is exactly the model that made the graph-color allocator (below) dead. Much
> of "section compaction" and the swap-driven pressure this allocator was designed to relieve may
> no longer exist. **Re-read the current art-pipeline design before planning; the honest first
> question is whether this item should be rescoped to object/sprite VRAM only.**
**Blocked by:** §3 Object System (`Load_Object` spawn/destroy lifecycle drives `AllocVRAM`/`FreeVRAM` calls)
**What:** Bump allocator for unified VRAM pool, loaded table tracking, refcount per type_id, lazy reclaim, section compaction.
**When ready:** After §3 defines object RAM layout and the object loop exists.

### Refcount-based Art Caching / Lazy Reclaim (§2.2) — **UNBLOCKED, SAME MOOTNESS CAVEAT**
> **⚠ 2026-08-05:** §3 exists (`load_object.emp`), so the blocker is discharged — but this entry
> is downstream of the Dynamic VRAM Allocator above and inherits its caveat verbatim: under a
> fully-resident deduped pool there may be nothing to refcount. Evaluate the two together, and
> evaluate the premise before the implementation.
**Blocked by:** §3 Object System (refcount increments/decrements tied to object spawn/destroy)
**What:** Freed art stays in VRAM until pool needs space. Re-spawn of same type is free (refcount bump, no decompression).
**When ready:** After §3 and the dynamic VRAM allocator exist.

### ~~Build-time Graph Coloring (§2.3)~~ — **DEAD 2026-08-05: the allocator does not exist and is not coming back**
> **⚠ VOID — this is not deferred work, it is a deleted design.** Verified 2026-08-05: `DSATUR`,
> `color_sections` and `compute_adjacency` have **zero hits** anywhere in the tree.
>
> The approach was **superseded** by the globally-deduped, spatially-ordered, paged act art pool
> (2026-06-22, the OJZ tile-budget resolution) and the machinery was then removed — this file's own
> Phase-3 cleanup entry records `ENGINE_ARCHITECTURE.md` being reconciled to "no
> graph-coloring/DSATUR/`LoadSectionTiles`/per-section art swap", and `CLAUDE.md` being corrected
> from "graph-color" to "dedup + spatial paging".
>
> **The file was contradicting itself:** this entry listed graph coloring as future work while the
> Done section below carries "§2 Phase 2 Layer A.3 — Build-time Graph Coloring — 2026-04-26" as
> shipped. It was both done and not-done and is in fact neither: it shipped, then was deleted.
> Two other entries referenced the allocator as a live dependency (§5's Sonic VRAM slot, and the
> A.5 T1 Done entry's architectural note) — both corrected in place.
>
> **Do not resurrect this without a fresh design.** Historical text below.
**Blocked by:** §4 Level/World (section adjacency graph) + §8 Build Tools (tile deduplication pipeline)
**What:** Non-adjacent sections share VRAM tile indices. Build tool computes coloring from section adjacency graph.
**When ready:** After §4 defines section grid and §8 has flatten/deduplicate pipeline.

### Section-aware Streaming / Predictive Preloading (§2.1/§4.8) — **UNBLOCKED; the block-stream half already shipped**
> **⚠ 2026-08-05 — half of this is already done, and the blocker text is stale.**
> **Blocker discharged, but not as written:** it names "leapfrog loading" and "section transition
> triggers", and **the leapfrog/teleport subsystem was deleted** (`eddbbf7`). What replaced it —
> continuous scroll with a camera-driven streamer — supplies the same dependency better.
> **The block-stream half effectively SHIPPED** as the unified direction-aware prefetch:
> `engine/level/tile_cache.emp:1001` (row scan, vertical, no hysteresis — "gravity is decisive")
> and `:1093` (column scan with H3 direction hysteresis). That is precisely "predictive preloading
> based on camera velocity and direction", for blocks.
> **What genuinely remains is the ART half** — deferrable-DMA streaming of *tile art* — and that is
> art-streaming Phase 2, which gates on §9.7 (item 1 of the NOW UNBLOCKED list). Rescope this entry
> to the art half or fold it into Phase 2; do not plan it as written.
**Blocked by:** §4 Level/World (section transition triggers, camera position, leapfrog loading)
**What:** Deferrable-priority DMA streaming of next section's art based on camera velocity and direction.
**When ready:** After §4 implements section transitions and camera system.

### S4LZ Streaming Mode (§2.1) — **UNBLOCKED — the §9.7 mechanism now ships; adopt the shipped pipeline**
> **RESCOPED 2026-08-09.** The gate (§9.7) is discharged — the pages+bookmark idle-time path shipped
> with art-streaming Phase 2. S4LZ streaming is no longer *blocked*; it is now a straight adoption of
> the shipped `ZX0R_Decompress`-style contract: make the S4LZ decompressor a `@resumable` stack-flat
> proc in the same `[start, __end)` range shape, enqueue it through the same demand/prefetch FIFO,
> and let the VBlank bookmark slice it. The pipeline (private staging buffer → dispatcher DMA enqueue
> → VBlank transfer) is built and proven; only the S4LZ-specific resumable decoder body remains.
> Do this when a payload larger than one block dictionary actually needs mid-gameplay streaming.
**Was blocked by:** §9.7 (now shipped — pages + supervisor bookmark, ARCH §9.7).
**What:** A `@resumable` S4LZ decoder body adopting the shipped bookmark contract + demand/prefetch FIFO.
**When ready:** Now — do it when a larger-than-block payload needs mid-gameplay streaming. Blocking mode handles all current use cases.

---

## From §3 — Object System (Research Phase)

These items were identified during §3 Phase 0 research but require a full SST field audit before committing.

### Boss-system design reference — multi-phase choreography via chained routine pointers (§3) — 2026-07-14
**Surfaced during:** TheBlad768 survey — S3K Epilogue boss objects. Full write-up: `docs/research/2026-07-14-theblad768-survey.md` (KEEP #2).
**Status:** Reference only — no boss system is designed yet. Epilogue runs multi-stage fights inside ONE object: HP-threshold swaps the active attack-pattern table (8→4 HP = different 4-pattern set), each pattern a coroutine-style subroutine whose successor address lives in a free object-RAM field and is chained at runtime (mid-attack transitions = pointer swap, no routine-counter ladder, no per-phase object IDs), position-gated pattern entry, child-object attack spawns, HP-keyed palette hit-flash tables.
**What:** When the boss-system design phase opens, cite this as the worked "one object, N phases" example. Maps directly onto objects-v2: chained next-routine pointer in `sst_custom`, pattern-table swap on HP threshold, children system for spawns, palette-line flash via per-line dirty DMA. Related: the same survey doc's KEEP #3 (Sonic Spinball script-VM cutscene/animation architecture, added 2026-07-14) is the companion reference for any cutscene/scripted-sequence system — both replace routine-counter ladders with data-driven control flow.

### SST Field Audit & Size Re-evaluation (§3)
**Note (2026-06-10):** objects-formats-v2 resolved the dead-field/metadata half of this audit — `respawn_index`, `wait_timer`, and the separate priority word are gone; entity-window metadata (`slot_tag`/`entity_section_id`/`entity_list_index`/`layer`) packed at $2A-$2D; `sst_custom` grew to 34 bytes at $2E.
**CLOSED (2026-06-14, §5 player work):** the player overlay fits 34 bytes with room to spare — **`PlayerV_len` = $D (13 bytes)** of the 34 available (`engine/player/player_common.asm`: ground_speed, player_state, status_secondary, move_lock, spindash_charge, flip_angle, air_left, invuln_time, stick_convex, debug_flag; the last five are reserved/debug). The DPLC table and art base are **per-character code immediates** (`lea` in `sonic.asm`), NOT SST fields, so the 9-byte test_player DPLC-in-SST pattern is not carried over. No per-pool stride, no variable SST sizing, no SST growth needed for the player. The general SST-shrink question (below) stays open but is decoupled from the player.
**Blocked by:** Implementation of player subsystem (need real player field pressure)
**What:** Audit every SST field across all object types (player, badnik, platform, effect, boss, system) once subsystems are implemented. Determine actual field usage per type. Evaluate whether the SST can shrink from $50 to $4C or $48.
**When ready:** After §3 Phase 3 (animation) and Phase 4 (collision) are implemented — enough subsystems exist to see real field pressure.

### ~~Word code_addr at $00 (§3)~~ — DONE (superseded by objects-v2, 2026-06-10)
Shipped: SST $00 is a word offset from `ObjCodeBase`, `objroutine()` computes it at build time, and the object bank has a build-time 64KB overflow guard.
**What:** Use a word offset at $00 instead of longword function pointer (sonic_hack pattern). `objroutine function x,(x)-ObjCodeBase` computes offset from a $10000-aligned code bank. Dispatch: `moveq #BANK, d0; swap d0; move.w (a0), d0; movea.l d0, a1; jsr (a1)`. Saves 2 bytes per SST, 20 cycles per dispatch (~1,320 cycles/frame across 66 slots). Constraint: all object code must fit in one 64KB bank.

### Word Mappings Offset (§3)
**Blocked by:** SST field audit
**What:** Use a word offset for `mappings` instead of a longword ROM pointer. All sprite mappings would live within 64KB of a base address. Saves 2 bytes per SST. Combined with word code_addr, that's 4 bytes freed — may enable SST shrink.
**When ready:** During SST field audit. Requires organizing mapping data contiguously.

### Variable SST Sizing — Effect Pool (§3)
**Blocked by:** SST field audit (need to know actual effect field usage)
**What:** Thunder Force IV uses $20/$40/$60 per-type pools. A $20 effect SST (explosions, dust, score popups, debris) shares the $00-$19 prefix with the full SST, enabling shared routines (ObjectMove, Draw_Sprite). Saves ~768 bytes at 16 effect slots. Trade-off: separate RunEffects loop, effects can't use routines that access fields past $19 (e.g., AnimateSprite needs anim_table at $28).
**When ready:** After SST field audit determines which fields effects actually need. May be unnecessary if SST shrinks enough overall.

### ~~Pack collision_resp + width + height for Single-Longword Init (§3)~~ — SUPERSEDED by objects-v2 (2026-06-10)
The burst-copy spawn (`movem.l` of the whole $0A-$21 template block) makes per-field init moot — collision_resp/width/height arrive with everything else in one copy.
**Blocked by:** SST field audit + Load_Object init path performance pressure
**Source:** TheBlad768's S.C.E. and S1-in-S3 collision refactors (`d1e24ee` / `05512e4`) put `collision_type`, `collision_height`, `collision_width` adjacent so spawn init can do `move.b d0,collision_type(a0); swap d0; move.w d0,collision_height(a0)` — three bytes initialized from one ROM longword. Currently `collision_resp` is at $0F and `width_pixels`/`height_pixels` at $18-$19, so they need separate fetches.
**What:** Reorder SST so the type byte is adjacent to the width/height pair (or move both into the $0E neighborhood). Lets objdef tables emit `dc.b coltype, colh, colw, pad` and Load_Object init reads them in one `move.l`. Rough estimate: ~10-20 cycles saved per spawn × spawn frequency. Not free — reorder breaks the current $00-$19 "shared-prefix" boundary that we may want for a future $20 effect SST, so these two items must be evaluated together.
**When ready:** During SST field audit, alongside the effect-pool decision.

### ~~Object Data Macros (`subObjData` family) (§3)~~ — DONE (superseded by objects-v2, 2026-06-10)
Shipped as the `objdef` named-parameter macro (26-byte archetype image) plus `objentry`/`objend` for placement lists — semantic args, build-time validation.
**Blocked by:** Objdef format finalization (currently still raw `dc.b`/`dc.l` in `data/objdefs/test_objects.asm`)
**Source:** S.C.E.'s `subObjData frame,coltype,(colh/2),(colw/2)` macro hides the field layout behind a named-parameter call so reordering SST fields doesn't ripple through every object table. Same idea for child priority data, animation script entries, etc.
**What:** Once the objdef format is stable, wrap the byte/word emission in `function`-and-macro pairs that take semantic args (`coltype`, `colh`, `colw`, `frame`, `priority`, ...) rather than positional bytes. Uses our `function` for any /2 or shift conversion, `struct`/`endstruct` patterns where appropriate. Pure ergonomics — zero runtime cost, but it's the difference between objdef tables that read like data and ones that read like a binary blob.
**When ready:** When more than 2-3 objects exist and the objdef format stops churning.

### Multisprite children vs parent bbox culling (§3.5)
**Surfaced during:** objects-formats-v2 final review (2026-06-10).
**What:** Exact parent-bbox culling governs whole multisprite batches (children
skip independent registration), so a child extending beyond its parent's own
frame bbox can pop at the screen edge earlier than under the old ±32 margin.
No multisprite content exists yet.
**When to revisit:** first boss/multi-part object — either author parent frames
whose bbox covers the chain's extent, or have the generator union child extents.

### SST frame-pointer cache (§3.5)
**Surfaced during:** objects-formats-v2 T8 review (2026-06-10).
**What:** Draw_Sprite and Render_Sprites each resolve mapping_frame → frame data
per object per frame (~46 cycles each). RefreshSpritePieceCount/
PopulateSpawnedPieceCount already run at every mapping_frame write, so caching
the resolved frame POINTER in the SST (one long from sst_custom) has a ready
invalidation contract and saves ~90 cycles per rendered object per frame.
Caveat: the multisprite sibling walk indexes child mappings with the parent's
frame and must keep its inline resolve.
**When to revisit:** when profiling shows object-loop pressure (~20+ on-screen
objects), alongside the §3 SST field audit.

---

## From s4lint — Static Analysis (Phase 1)

### Fall-Through State Carry-Forward
**Blocked by:** Real codebase patterns that use fall-through across global labels during VDP access
**What:** When a routine doesn't end with `rts`/`rte`/`bra`/`jmp`, carry Z80/interrupt state forward to the next global label instead of resetting. Currently all state resets at every global label boundary.
**When ready:** When fall-through patterns appear in engine code that cause false positives on E006/E007/E008.

### Sprite Multiplexing for Particle/Weather Systems (§3.5)
**Blocked by:** HBlank handler infrastructure, weather/particle system design
**What:** Rewrite SAT entries mid-frame via HBlank to display 80+ visual sprites from 3-5 physical SAT entries. Each HBlank updates Y/X/tile for a small set of sprites, scanning them down the screen. 18 bytes/scanline VRAM bandwidth, ~92 68k cycles per HBlank handler. Best for simple, repetitive effects (rain, snow, starfields) where sprites are small and never share scanlines. Too constrained for general Sonic gameplay (diverse objects at varying positions).
**When ready:** When a weather or particle system needs more than 80 simultaneous sprites. Stone Protectors (falling snow, 3 sprites × 8 scanlines) is the reference pattern.

### Object-vs-Object Collision (§3)
**Blocked by:** Real gameplay objects that need it (boulders, boss parts, projectiles)
**What:** Current TouchResponse is player-vs-object only. For object-vs-object cases (two boulders bouncing, boss parts checking each other, shields vs projectiles), add a `CheckObjectPair` helper that takes two SSTs, does the same AABB test, and returns overlap data. Objects call it from their own per-frame routine against specific targets. A full O(n²) object-vs-object pass is overkill — object-side polling is the Sonic-era pattern.
**When ready:** When a gameplay object needs to react to another non-player object.

### W010 Loop Detection Refinement
**Blocked by:** When suggestion-tier noise becomes annoying even with `--no-suggestions`
**What:** W010 (indexed addressing in loops) currently triggers after ANY local label, not just actual `dbf`/`dbra` loop bodies. Should only flag indexed addressing between a local label and the `dbf` that references it. Phase 3 reclassified W010 as a suggestion (not warning), so the noise is lower-priority now.
**When ready:** When the false positive rate is still disruptive even as a suggestion.

---

## From §4 Phase 1 — Level/World System

### ~~Path-B collision content — wire the secondary index through the strip generator (§4.7)~~ — **✅ FULLY CLOSED — design #6 closeout, verified 2026-08-08**
> **⚠ CORRECTED 2026-08-08 — path B is editor-authorable now, and "remaining = path-swapper
> objects" (the assumption the 2026-07-02 editor-collision-authoring-design spec carried into
> this entry) was already stale when that spec was written: `path_swap.emp` shipped
> 2026-06-12, three weeks before the spec's 2026-07-02 date.**
>
> **Production collision has moved off the sonic_hack-donor secondary index entirely.** The
> 2026-08-05 correction below (kept for provenance) describes wiring the real `"OJZ secondary
> 16x16 collision index.bin"` through `bake_cell`/`PATH_A_SOL_SHIFT`/`PATH_B_SOL_SHIFT` — that
> path (`ojz_strip_gen.build_section_collision`) still exists in the tree but is now
> legacy/test-fallback only (see `test_section_collision_sec0`, explicitly commented
> "fallback-mode data"). The LIVE production path (`ojz_strip_gen.generate()`, the "FRESH
> START + flag-based authoring" block) is: **all-air baseline** (`per_section_coll` seeded
> from `air_col`) **+ Aurora's editor overlay** (`apply_editor_collision_overlay`, reading
> `games/sonic4/data/editor/ojz/act1/section_N.collattr.bin` / `.collattrb.bin` — 16-bit
> big-endian cell words, one plane per file) **baked via `collision_pipeline.bake_plane_cell`
> against the imported S&K shape/height/angle bank** (`data/collision/base/`, written by
> `import_sk_collision.py`) **into a shared, sparse interned attr-set** (13/255 combos used
> today, ~242 slots headroom) — only combos actually painted reach the ROM tables.
>
> aeon's half of this (consumption) has needed **zero code changes** since 2026-07-02 (per
> `docs/superpowers/specs/2026-07-02-editor-collision-authoring-design.md` §3). Today's
> design #6 (Aurora, `aurora/docs/plans/2026-08-08-chunk-collision-and-map-clipboard.md`)
> closes the AUTHORING half instead: `ChunkDef.collisionA`/`collisionB` (16-bit cell words,
> same encoding as the section edit planes) now travel with stamps atomically, a map clipboard
> copies/pastes regions with both collision planes, paint defaults to "just here" instead of
> art-identity propagation, and the legacy per-tile nibble plane + `.coll.bin` export + 2-bit
> `ChunkDef.collision` are all deleted. Path B is no longer "copy of A until real secondary
> data is authored" — Aurora authors it directly now (`docs/LEVEL_EDITOR_SPEC.md` corrected
> alongside this entry).
>
> **Path-swapper objects were never the actual gap.** `games/sonic4/objects/path_swap.emp`
> (`PathSwap_Init`/`PathSwap_Main`, writes `Sst.layer` on line-crossing — the collision-layer
> select `engine/level/collision_lookup.emp` reads into `d3.b`) shipped 2026-06-12 ("path-swap
> line object — OJZ loop wired for two-path traversal") and was ported to `.emp` 2026-07-29; a
> real two-path loop is placed in level data (`OJZ_Sec1_Objects`, `entity_data.emp:41`, type 1
> = `ObjDef_PathSwap`, two instances). **No collision-content work remains deferred here** —
> author → bake → consume → runtime swap is closed end-to-end.
>
> Older correction, kept for provenance:
> **⚠ CORRECTED 2026-08-05 — this entry asked for two things and BOTH shipped.**
> 1. **The real secondary index is loaded and baked.** `tools/collision_pipeline.py:301` loads
>    `"OJZ secondary 16x16 collision index.bin"` alongside the primary, and `:172-189`
>    (`bake_cell`) bakes *both* layers per placement, driving path selection off
>    `PATH_A_SOL_SHIFT` / `PATH_B_SOL_SHIFT` (bits 13:12 and 15:14 of the chunk-entry word) with
>    per-path flip handling. The VDP-priority-bit placeholder this entry complains about is gone —
>    and note the pipeline moved: it is `tools/collision_pipeline.py` now, not
>    `tools/ojz_strip_gen.py`.
> 2. **The path-swapper objects exist.** `games/sonic4/objects/path_swap.emp` is implemented and
>    actually placed in level data — `ObjDef_PathSwap` appears as type 1 in
>    `games/sonic4/data/generated/ojz/act1/entity_data.emp:41`
>    (`OJZ_Sec1_TypeTable ... t1: ObjDef_PathSwap`).
>
> Layer B is no longer a byte-copy of layer A. **The RAM-slack note in the entry (910 bytes lower
> RAM, one more `BLOCK_STAGE_SLOTS` fits) is from 2026-06-10 and has NOT been re-measured — do not
> trust that number.** Historical text below.

**Surfaced during:** objects-formats-v2 T7 (2026-06-10).
**What:** Dual-layer collision SHIPPED format-wise (768-byte blocks, two cache planes,
SST_layer select) but layer B is a byte-copy of layer A. The real data exists:
`sonic_hack/collision/OJZ secondary 16x16 collision index.bin` (138 bytes, 122 differ
from primary) — but `tools/ojz_strip_gen.py` derives collision from a VDP-priority-bit
placeholder, not the index files, so wiring block-ID → secondary index → real path-B
bytes is level-pipeline work. Also needed then: path-swapper objects that write SST_layer.
**RAM note:** lower RAM slack is now 910 bytes ($FFFF7C72 → $FFFF8000). One more
BLOCK_STAGE_SLOTS (+768) fits; nothing ≥1KB does without evicting something.
**When to revisit:** when the level pipeline replaces the priority-bit collision
placeholder with real collision data, or when the first loop is authored.



### ~~Tile cache vertical slide is a memmove — circular row origin (§4.7)~~ — DONE 2026-06-10
**Completed:** `Cache_Origin_Row` circular index shipped same day the lag was
observed live (debug-fly turbo descent = up to 3 memmoves/frame ≈ 260k cycles).
VSlide/VSlideUp are now O(1); row-walking consumers use an end-of-buffer
sentinel (~16 cycles/row); single-row consumers remap the index. Origin kept
even so collision stays cell-aligned. Verified in Exodus: 252-row descent →
origin 12 (252 mod 60), 216-row ascent → origin 36 ((12−216) mod 60), terrain
renders clean through 4+ ring wraps in both directions.
Original entry:
**Surfaced during:** tile cache fill rewrite 2026-06-10.
**What:** Columns evict via circular origin (`Cache_Origin_Col`, free), but rows evict by
shifting the whole buffer: `TileCache_VSlide`/`VSlideUp` move ~9.4 KB nametable + ~2.3 KB
collision per 2-row evict ≈ **~47k cycles (a third of a frame) every 16 px of sustained
vertical scroll**. Fine in the light test state; will cause lag frames under real object
load. Fix: add a `Cache_Origin_Row` circular index. Touches every row-indexed consumer —
`Tile_Cache_GetTile`/`GetCollision`, `TileCache_CopyBlockColumn`, `Draw_TileColumn`
(column walks would split into two runs at the wrap, mirroring the existing NT 63/0
split), `Draw_TileRow_FromCache`, `Section_RedrawPlanes`.
**When to revisit:** once gameplay objects + parallax + DMA load share the frame and
vertical traversal shows lag, or §4 vertical work touches these routines anyway.

### FG H-deform vs streaming seam (left-edge draw lookahead)
**Surfaced during:** plane-A scroll lock fix 2026-06-10.
**What:** Plane A is now hard-locked to the camera, but configs that apply an
**H-deform wave to plane A** (e.g. SkyHaze's bottom-band FG haze on Sec2) still
displace FG lines by up to the wave amplitude. A leftward wobble pulls plane
columns left of the camera window into view — those sit at the plane-wrap seam
and may hold ahead-content, exposing up to wave-amplitude pixels of seam at the
screen edge. Mitigation: stream a few extra columns of edge lookahead in
`Section_UpdateColumns` (≥ max FG deform amplitude in tiles) so the seam sits
beyond any FG wobble.
**When to revisit:** before shipping any production config with FG H-deform, or
if Sec2's haze shows edge artifacts during testing.

### ~~§4.9 entity window is X-only — no vertical dimension~~ — DONE 2026-06-11 (vertical entity window)
**Surfaced during:** vertical-axis audit 2026-06-10 (EntityWindow_TeleportShiftY added
for teleport consistency, but the underlying system is 1D).
**What it was:** `EntityScanState` had `ess_origin_x` but no Y origin; ring/object
populate used ROM Y verbatim; only the slot-mapped (upper) sections of each vertical
pair were scanned; `EntityWindow_Scan` advanced on camera X only.
**Fix shipped:** exactly the proposed shape — 2×2 quadrant scan state (4 entries: slot
L/R × row r/r+1, derived from `Slot_Section_Map` by `EntityWindow_BuildEntries`),
per-entry `ess_origin_y` + `ess_entry_idx`, `Entity_Window_Active` validity mask with
SEC_VOID stamping for out-of-grid entries, S3K-style camera-Y spawn band
(ENTITY_LOAD_BUFFER_Y $100) with despawn hysteresis (ENTITY_DESPAWN_BUFFER_Y $180),
128px-coarse vertical re-scan (ENTITY_RESCAN_COARSE_MASK), per-entry loaded bitmasks
making all spawn paths idempotent, ring-buffer high-water + DEBUG-fatal drop diagnostics,
and build-time guards on the band invariants. Teleport mask migration proven a no-op
(disjoint 2-section block moves, table in entity_window.asm). **OEF_ANY_Y is now
honored:** ANY_Y objects spawn on X coverage regardless of camera Y and are exempt
from Y despawn, with the flag mirrored to `SST_slot_tag` bit 7 at spawn. Full 7-check
verification matrix passed in Exodus 2026-06-11. See ENGINE_ARCHITECTURE.md §4.9.3/§4.9.6.

---

## ☠ DEAD CLUSTER — the §4 teleport / leapfrog entries (11 entries, VOID 2026-08-05)

**Every entry marked `[DEAD CLUSTER]` below describes a subsystem that no longer exists.**
`eddbbf7` (2026-06-22, "refactor(level): delete the dead leapfrog subsystem — continuous-scroll
Task 10") removed it wholesale, and the continuous-scroll engine that replaced it does not
teleport at all: it scrolls continuously and rebases the floating origin.

**Grep evidence (2026-08-05, whole tree, source only — every one returns ZERO hits):**
`Section_Check`, `Section_TeleportFwd`, `Section_TeleportBwd`, `Section_TeleportUp`,
`Section_TeleportDown`, `Section_QueueNewSlot`, `Section_Preload`, `SECTION_SHIFT`,
`Slot_Section_Map`, `SyncSlide`, `TeleportShift`.
(`Slot_Section_Map` appears exactly once, in a comment at `engine/system/replay.emp:255`
explicitly noting the name does **not** exist.)

**What `engine/level/section.emp` actually exports today** — the complete list:
`Section_Init`, `Section_FillInitial`, `Section_FlatIDXY`, `Section_GetSecPtrXY`,
`Section_RedrawPlanes`, `Section_UpdateColumns`. No teleport, no preload, no slot map, no
threshold check.

**How to read these entries:** as **historical record only**. They are retained (not deleted)
because they document real reasoning about plane wrap, streaming budgets, landing suppression and
register-clobber contracts, and because the continuous-scroll design was chosen *against* them —
knowing what was rejected is worth keeping. **Do not plan from any of them. Do not "fix" the
defects they describe.** A few contain observations that outlived the subsystem; those are called
out individually.

**The eleven:** Plane A wrap-cycle · Section Preload with S4LZ Deferrable DMA · Section Preload
Velocity-Based Timing · Vertical Section Teleport · Section Null-Neighbor Camera Clamp · Section
rotation cascading work · Plane A fill-in after teleport · Section teleport landing-flag mechanism
· X-BWD clamp-to-zero degenerate slot pair · `Section_TeleportBwd` `.at_start` guard ·
`Section_Check` clobber header understates.

---

### [DEAD CLUSTER] ~~Plane A wrap-cycle visible during scroll (§4.2 streaming polish)~~
> **VOID — see the DEAD CLUSTER banner above.** The whole entry is framed on `SECTION_SHIFT`
> (deleted) and `Section_UpdateColumns`' teleport-era ring math. Its recommended fix — "camera
> teleport per plane-width" — is the opposite of the direction the engine actually took
> (continuous scroll + floating-origin rebase, shipped 2026-06-22/23). Historical text below.
**Surfaced during:** §4.6 polish session 2026-04-28 (after bhi→bhs core fix + Section_Teleport_Guard increase shipped).

**Symptom:** When scrolling right through a single section, foreground (Plane A) terrain appears to "draw from left to right" — chunks of FG content materialize at screen LEFT and seem to fill toward screen RIGHT as the user scrolls. When scrolling left (back), the LEFT chunk disappears first while the RIGHT chunk persists. User confirmed via experiment: stub'ing `Section_UpdateColumns` to `rts` immediately makes all FG content disappear, proving the streaming engine *is* producing the visible artifacts.

**Root cause analysis:**
- Plane A is 64 cells = 512 px wide; screen is 320 px wide
- Section is 4096 px (`SECTION_SHIFT = $1000`); user scrolls through a section across 8 plane-widths
- `Section_UpdateColumns` writes each new section col to plane col `(global_col mod 64)`
- The streaming target is mathematically *correct* — it writes off-screen-right (1 col past visible right edge)
- BUT plane col 0 has a visibility cycle as Camera_X grows: visible at screen LEFT briefly when `Cam_mod_512 ∈ [0,7]`, off-screen for ~190 px, then reappears at screen RIGHT and drifts left
- During this cycle, each plane col gets *overwritten* every 512 px of camera travel with new section data — but the overwrite happens off-screen-right, so the new content enters from screen-right correctly
- **The "drawing from left" perception** is the plane-wrap natural behavior: every 512 px of scroll, the pattern repeats. Content at screen LEFT after each wrap is the LATEST streamed content — user sees it as "appearing on the left."

**Verified facts:**
- HScroll values are correct (uniform `-Camera_X` across all 28 cell rows for Sec0)
- Section_FillInitial fills cols 0..63 correctly at boot
- Section_UpdateColumns advances Right_Col_Written / Left_Col_Written correctly
- Streaming writes target plane col is always off-screen-right at the moment of write
- Plane wrap is mathematically inevitable when plane width (512px) < section width (4096px)

**Possible fixes (all §4.2 architecture work, not §4.6):**
1. **Camera teleport per plane-width**: instead of `SECTION_SHIFT = $1000`, teleport every 512 px so plane wraps land at teleport boundaries (= invisible). Requires reworking section coordinate system, object spawning, collision lookups.
2. **Wider effective plane via VRAM trickery**: not feasible — VDP is hard-limited to 64×64.
3. **Section_UpdateColumns rewrite**: stream content N plane-widths AHEAD so each plane col is written 64+ cols before reaching visibility. Requires more aggressive write-ahead and careful Plane_Buffer budgeting.
4. **Live with it**: accept that plane-wrap pattern is visible. Real Sonic games (S1/S2/S3K) use camera teleport to mask it; we currently don't.

**When to revisit:** Dedicated §4.2 polish session. Don't try to band-aid this in §4.6 territory — it's a section-streaming engine architecture issue. Recommend Option 1 (camera teleport per plane-width) as the proper fix; it matches the technique used in real Sega Genesis Sonic games.

**Additional finding:** `SECTION_SHIFT = $1000` ≠ `SECTION_SIZE = $0800`. Comment claims "uniform shift applied on teleport (pixels)" but the value is 2× SECTION_SIZE. With current values, post-FWD Camera_X = $200 (= cam_min_x = BWD_THRESHOLD), which is what causes the section oscillation that the 30-frame Section_Teleport_Guard patches. The "natural" fix would be `SECTION_SHIFT = SECTION_SIZE = $0800` (so FWD/BWD both land Cam mid-window at $0A00, no oscillation), but this requires recalibrating Right_Col_Written / Left_Col_Written math in Section_UpdateColumns and the Section_FillInitial init values. Worth investigating as part of §4.2 polish — may also resolve the plane-wrap perception issue if the ring rotation is "shorter" per teleport.

### [DEAD CLUSTER] ~~Section Preload with S4LZ Deferrable DMA (§4.2)~~
> **VOID — see the DEAD CLUSTER banner.** `Section_Preload` and `Section_QueueNewSlot*` do not
> exist. **One idea outlived the subsystem:** deferrable-DMA streaming of upcoming *art* is real
> work — it lives on as **art-streaming Phase 2**, gated on §9.7. Plan it from the Phase-2 spec,
> not from this entry.
**Blocked by:** S4LZ art streaming pipeline (§2.1) and section adjacency graph
**What:** When camera crosses Section_FWD/BWD_PRELOAD threshold, queue Deferrable-priority DMA to load next section's tile art into the VRAM pool. Currently Section_QueueNewSlot1/0Cols just writes nametable strips; the art must already be in VRAM.
**When ready:** After §2 art streaming and §4.2 section preload are designed.

### [DEAD CLUSTER] ~~Section Preload — Velocity-Based Timing (§4.2)~~
> **VOID — see the DEAD CLUSTER banner.** No preload threshold exists to make velocity-adaptive.
> **The idea outlived it in shipped form:** direction/velocity-aware prefetch is live in
> `engine/level/tile_cache.emp` (`:1001` row scan, `:1093` column scan with H3 hysteresis) for the
> block stream. What that does not cover is art — again art-streaming Phase 2.
**Blocked by:** Player physics providing ground_speed
**What:** Preload threshold adapts to player ground_speed — trigger earlier at high speed to ensure art arrives before new columns are visible. Currently fires at fixed SECTION_FWD/BWD_PRELOAD constants.
**When ready:** After §3 player physics provides ground_speed to the section system.

### [DEAD CLUSTER] ~~Vertical Section Teleport (§4.2)~~
> **VOID — see the DEAD CLUSTER banner.** `Section_TeleportUp`/`Down` never existed beyond a stub
> and the `Section_Check` that would have hosted them is deleted. **The capability shipped by
> other means:** continuous vertical scrolling + the vertical entity window + vertical tile-cache
> fill, all merged 2026-06-11/23. Multi-row section grids work today without any teleport.
**Blocked by:** Vertical level design and camera Y handling
**What:** Section_TeleportUp / Section_TeleportDown paths (stub exists in Section_Check). Camera Y threshold mirrors the X system. Required for multi-row section grids.
**When ready:** After a level with vertical transitions is designed.

### [DEAD CLUSTER] ~~Section Null-Neighbor Camera Clamp (§4.2)~~
> **VOID — see the DEAD CLUSTER banner.** There is no `Section_TeleportBwd` to add a null check
> to. Note the underlying concern *was* separately addressed in the teleport era via the
> `SEC_VOID` sentinel + camera max-x void clamp (see the grid-edge entry), and the concept
> survives as ordinary act-boundary camera clamping in the continuous-scroll engine.
**Blocked by:** Act descriptor null-section encoding
**What:** When camera approaches a section slot with no neighbour (edge of the level), Camera_X should clamp to the act boundary instead of teleporting. Currently Section_TeleportBwd has a note for zero-clamp but no null check.
**When ready:** After act descriptors encode level boundaries.

### Dynamic Tile Override Table (§4.3)
**Blocked by:** Gameplay objects that need runtime tile patching
**What:** Tile_Override_Table (16 entries × 6 bytes) is allocated in RAM. Needs a writer (object sets col/row/new_tile) and a drain routine (VInt_DrawLevel emits row updates). Used for breakable tiles, activated switches, destroyed terrain.
**When ready:** When a gameplay object needs to modify level geometry at runtime.

### ~~§4.6 lerp accumulator never converges to per-band targets~~ — RESOLVED 2026-06-11 (re-test)
**Resolution:** Root cause was the TestPlayer d7 clobber (fixed 2026-06-10) — garbage object dispatch
was stomping the accumulators between frames, which is why every single-stepped iteration computed
correctly while stored values were wrong. Re-test on current master: Camera_X=608 stable, active config
resolves to ParallaxConfig_OJZ_Caves (factors 1/16,1/16,1/8,1/4,1 — NOT the April-era Default config the
original expectations were computed from), and `Parallax_Current_Scroll_B` reads exactly
[-38,-38,-76,-152,-608] = 608×factors, pixel-perfect. Entries 5-7 stay 0. Mid-pan spot-check at
Camera_X=624 under the same config was also exact ([-39,-78,-156,-624]). Note for future debugging:
the April "expected" values were computed against the wrong config — always derive targets from
`Parallax_Current_Config`'s actual band table, not from the act's default.

Original investigation notes kept for reference:

**Surfaced during:** §4.6 polish session 2026-04-28 (after MCP debug session).

After ~thousands of frames with Camera_X stable at 608, Plane A
entries 0-4 of `Parallax_Current_Scroll_A` converge to -608 (the
FACTOR_1 target — correct). But Plane B entries don't converge to
their per-band targets:

  Expected (steady state with camX=608):
    B[0] cloud (FACTOR_1_8) → -76
    B[1] far_mtns (FACTOR_1_4) → -152
    B[2] mid_mtns (FACTOR_3_8) → -228
    B[3] hills (FACTOR_1_2) → -304
    B[4] ground (FACTOR_1) → -608

  Observed: -542, -551, -608, -608, -608

Entries 5-7 (which the 5-band loop shouldn't touch) read as -608 even
though `Parallax_Init`'s zero loop correctly sets them to 0.

Verified via single-step:
- `Decode_Factor_A` returns -608 for FACTOR_1 ✓
- `Decode_Factor_B` reads correct s1=3 for cloud band's first call ✓
- Band loop iterates 5 times, exits with d5=5 ✓
- `a2`/`a3` advance by 2 per iter, end at entry 5 ✓
- `Parallax_Current_Config = $000104C2` (OJZ_Default) stable ✓
- Camera_X stable at 608 ✓
- `Parallax_Init` runs once at boot, never again ✓

So the lerp's *individual iterations* compute correctly per-band, yet
the steady-state values are wrong. This suggests entries are getting
overwritten BETWEEN frames by something that doesn't appear in the
band loop or Parallax_Update flow. Watchpoints don't fire.

Live MCP debugging hit a wall — the inconsistency between "every
instruction does the right thing" and "the stored values are wrong"
needs **instrumented offline debugging**: dump
`Parallax_Current_Scroll_A/B` to a debug VRAM region every frame, then
inspect the trace to find when/which write produces the wrong value.

**When to revisit:** Dedicated session with code instrumentation. Don't
try live-stepping — too much state, too much MCP-level uncertainty.

---

### ~~§4.6 visual artifacts blocked on root-cause of state clobber~~ — RE-TESTED 2026-06-11, ALL THREE RESOLVED

**Re-test 2026-06-11 (current master, live Exodus):**
1. **3-line race on load / wrong lerp targets** — RESOLVED. Accumulators converge pixel-exact to the
   active config's per-band targets (see the lerp entry below for full numbers). The April "wrong
   targets" were measured against the wrong config (Default instead of the per-section Caves).
2. **FG H-deformed during section transitions** — RESOLVED. FG HScroll words verified uniform at
   -Camera_X across all 224 lines through: a FWD teleport into Sec2, a BWD teleport back, and two
   live config switches (Windy↔Caves). The only per-line FG variation found was SkyHaze's *intentional*
   bottom-band haze on Sec2 (`parallax_combine_split` demo) — by design, not the artifact.
3. **BG warps while stationary** — RESOLVED. Two screenshots ~20s apart with camera idle at
   Camera_X=608 are byte-identical PNGs.

All three derived from the TestPlayer d7 stomp (fixed 2026-06-10). No further §4.6 debugging needed.

**Surfaced during:** §4.6 T12 testing, expanded in T12 polish session 2026-04-27.

Three known visual artifacts in the OJZ scroll test that all derive from
the same upstream state-corruption issue tracked below:

1. **3-line race on load.** Top scanlines lerp from VSRAM=0 to their
   converged target over the first half-second. Snap-on-init
   (32-iter convergence loop in `Parallax_Init`) was added but didn't
   eliminate the visible race. MCP runtime read of
   `Parallax_Current_Scroll_B` after Init shows entries [0]=-542, [1]=-551,
   [2..7]=-608 instead of the expected per-band targets (-76, -152, -228,
   -304, -608). The lerp accumulators are converging toward a *different*
   target than the math would predict — points to either a register
   clobber inside `Parallax_Update` or stale state from a stalled iter.

2. **FG appears H-deformed during section transitions.** When entering
   Sec2 (or otherwise crossing a section boundary), Plane A tiles show
   sine-wave horizontal offsets, even though `pcfg_deform_table_fg=NULL`
   for every shipped config. Possibly a section-streaming race where
   Plane A nametable updates land mid-deform-frame, or a residual
   per-line FG entry left in `Hscroll_Buffer` from a previous config.

3. **BG warps on its own when stationary.** With camera stopped, the
   BG plane keeps animating despite `Parallax_Deform_Phase_FG/BG`
   *never being incremented* by any code path (verified via grep of
   `s4.lst`). The animation source is unidentified — possibly the
   per-line H-deform sample reading garbage past the buffer when
   per-cell DMA mode is active but per-line fill ran.

**Current state:** Workarounds in place make the system not crash and
mostly render correctly. Multi-band horizontal parallax works, sine
deform on clouds is visible, per-section configs resolve. The artifacts
above are polish issues that compound on top of the upstream clobber
documented below; trying to patch them individually keeps producing
new failure modes.

**When to revisit:** When the upstream `Parallax_Current_Config` /
`Camera_Y` clobber (below) is root-caused and fixed, re-test all three
artifacts. If they persist, debug separately with the upstream noise gone.

---

### Parallax effects library — expansion backlog (§4.6)
**Surfaced during:** §4.6 polish session 2026-04-28.
**Where:** `data/parallax/effects/` — each effect is a self-contained file (deform table + parameterised macro + named variants). Two entries shipped so far: `heat_shimmer.asm`, `wave_rocking.asm`.

**Pattern to follow when adding effects:**
1. One file per effect under `data/parallax/effects/`.
2. Header comment: visual description, mechanism, tuning knobs, dependencies.
3. Shared deform table (one in ROM) + a `<effect>_config` macro that takes camelCase params (AS limitation — no underscores in macro args).
4. A few pre-named variants (`_Slow`, default, `_Fast`) for casual use.
5. Add an `include` line to `main.asm` after `ojz_default.asm` (some effects depend on `DeformTable_Zero`).

**Effects to add (ranked by ease/impact):**
- **screen_shake.asm** — short-duration triangle table at high speed. Per-column V or per-line H. Triggered by gameplay events; needs a "fade out over N frames" wrapper. Earthquake / explosion impact.
- **water_surface.asm** — combined per-line H sine + per-column V sine (90° offset). Hydrocity-style ambient water surface. Complex — verify VBlank budget.
- **mirage.asm** — extreme low-amplitude (1 px) high-frequency H-deform on a single mid band. Distant heat haze without affecting near terrain.
- **vortex.asm** — sawtooth H-deform + sawtooth V-column with reversing phase. Boss room / portal swirl.
- **earthquake.asm** — random/noise table V-column at high speed for ~30 frames, then quiesces. Procedural noise table generator helps here (a `deform_table_noise` macro, peer of sine/triangle).
- **banking.asm** — linear V-column ramp whose slope tracks Camera_X velocity. "Tilts into turns." Needs runtime parameter feed (Camera_X velocity → vDeformShiftBg adjustment).
- **falling.asm** — accelerating linear V-column ramp during fall sequences. Pairs with vertical scroll mechanics (§4.2 deferred).

**Deeper effects (need new mechanisms):**
- **raster_perspective.asm** — true 3D pseudo-perspective floor via per-LINE H-scroll programmed by HBlank IRQ. Sonic 2 special stage / S3K bonus stage feel. Different feature, not just a new table — needs HInt handler + per-line H-scroll arithmetic. Tracks as §4.7 task.
- **palette_cycle_band.asm** — recolour a band as the deform phase advances. Combines with existing effects. Needs palette-cycling pipeline.

**When to revisit:** When level design surfaces a specific need ("this zone wants underwater wobble", "the boss room needs a vortex"). Build effects on demand rather than speculatively.

### OJZ scroll-test sky-tint section marker (T15 diagnostic — remove later)
**Surfaced during:** §4.6 T15 testing 2026-04-28.

The `OJZScroll_Update` per-frame logic writes a section-id-keyed color into `Palette_Buffer[0]` (CRAM[0] = backdrop) so the sky tints differently per section: Sec0 black, Sec1 red, Sec2 green, Sec3 blue, Sec4 yellow, Sec5 magenta, Sec6 cyan, Sec7 gray, Sec8 white. The color table is `OJZ_SectionMarkerColors` at the bottom of `test/ojz_scroll_test.asm`. Useful for diagnosing slot rotation and section streaming visually.

**Why deferred:** this is a debug/development aid, not a shipping feature. Remove or gate behind a debug flag once OJZ has real visual content per section (e.g., distinct palettes, tile art, props) that makes the section identity obvious without a marker.

**When to revisit:** once §3 player physics is in and we're playtesting actual gameplay, the diagnostic tint will be confusing. Strip the marker code (~25 lines + the table) and let the per-section palette do the storytelling.

### ~~Section rotation should be block-style, not rolling~~ — DONE 2026-04-28
**Completed in:** §4.6 T15 commit. `Section_TeleportFwd`/`Bwd` now advance both slots by 2 sections per teleport (block-style), matching `SECTION_SHIFT = $1000` and the user's "infinite forward walking" intent. Architecture doc §4.1 still describes the older rolling-leapfrog model and needs updating in T17.

### [DEAD CLUSTER] ~~Section rotation cascading work (§4.2 architectural fix)~~
> **VOID — see the DEAD CLUSTER banner.** Slot rotation, `SECTION_SHIFT`, the RC/LC trackers and
> the preload bandwidth model all went with the subsystem. `Section_UpdateColumns` survives by
> name only — it is now a continuous-scroll column streamer, not a slot-pair ring walker, so its
> "ring-buffer math" bullet does not describe today's routine.
**Surfaced during:** §4.6 T15 testing 2026-04-28.

**State:** The rotation logic itself is now block-style (shipped 2026-04-28). The cascade work below remains.

1. **`Section_UpdateColumns` ring-buffer math.** Currently assumes the rolling model — RC/LC trackers reset to fresh-streaming state and assume slot 1 = next section, slot 0 = continuation. With block-style, both slots are new at teleport, both need cold-fill streaming. Requires `FG_RedrawForSection` sibling to `BG_RedrawForSection` (already a separate deferred entry) so the visible content doesn't streak in over multiple frames after teleport.

2. **Preload bandwidth double-up.** Currently preload only loads slot 1's next section. Block-style needs both slot 0's *and* slot 1's next sections pre-fetched (= up to 2 sections of art queued during the slot 1 traversal). Doubles preload DMA bandwidth requirement; may need bigger preload window or velocity-based timing tightening to avoid mid-teleport stalls.

3. **Landing flag (separately deferred).** With block, post-teleport camera lands at `$200` (start of new slot 0), and walking left immediately fires BWD threshold. The `$0FFF` SHIFT nudge fixes that; the proper fix is sonic_hack's landing flag.

**When to revisit:** §4.2 polish session. Pair with FG_RedrawForSection and landing flag — they're all the same teleport pipeline.

**When to revisit:** §4.2 polish session. Pair with the FG-redraw work and the landing-flag mechanism; they're all the same teleport pipeline. Recommend reading `sonic_hack/code/engines/section_streaming.asm:Section_ForwardTeleport` end-to-end as the reference implementation.

### [DEAD CLUSTER] ~~Plane A "fill-in" after teleport (§4.2 streaming polish)~~
> **VOID — see the DEAD CLUSTER banner.** There is no teleport, so there is no post-teleport
> fill-in. `Section_RedrawPlanes` does survive (it is one of the six real exports) but as the
> synchronous initial plane fill at level start, not as a teleport repair path.
**Surfaced during:** §4.6 T14 testing 2026-04-28.

**Symptom:** Crossing a section teleport boundary (`$1200` FWD or `$200` BWD), Plane A foreground content visibly "runs in" over ~2-3 frames as `Section_UpdateColumns` re-streams the visible 40 columns into the plane. User wants the teleport to be imperceptible — same content visible before and after.

**Why it happens:**
- After `Section_TeleportFwd`/`Bwd`, slot rotation relabels plane cols (slot 0 ↔ slot 1) but does not move data — plane content still has the OLD slot mapping's tiles.
- `Section_Right_Col_Written` / `Left_Col_Written` reset to fresh-streaming state. `Section_UpdateColumns` then gradually re-fills columns from the new slot map.
- `PLANE_BUFFER_SIZE = 1536` bytes only holds ~15 columns of strip data per frame; the visible 40-column window takes 2-3 frames to fully refresh.

**`BG_RedrawForSection` already handles plane B at teleport** (full-section rewrite via dedicated batch path, drains in 1-2 VBlanks). Plane A doesn't have an equivalent — it relies on the per-frame streaming machinery.

**Fix paths (ranked by complexity):**
1. **`FG_RedrawForSection` sibling.** Mirror BG's batch redraw, queueing 64 plane cols of new slot 0 + slot 1 content into `Plane_Buffer` at teleport. Requires `PLANE_BUFFER_SIZE` increase to ~6400 bytes (= ~5KB extra RAM) so the burst fits in one frame. Drains in 1-2 VBlanks via existing `VInt_DrawLevel`. Cleanest but eats RAM budget.
2. **VRAM DMA from staged source.** Pre-build a 4096-byte plane-half template during preload phase, then DMA-fill into VRAM at teleport. Faster than direct writes, doesn't need bigger Plane_Buffer. New infrastructure required.
3. **Brief display-off during teleport.** Disable display, blast plane via direct VDP writes (huge VRAM bandwidth available with display off), re-enable. 1-2 frames of black. Simplest but ugly.
4. **Live with the streaming fill-in.** Current state. ~33-50ms of "running in" content. Tolerable for early demos; not shippable.

**When to revisit:** §4.2 polish session. Path 1 is the most aligned with the current architecture; path 2 is where to head once we're tightening the engine. Reference `BG_RedrawForSection` as the model — Plane A version follows the same structure but writes 32 nametable cols × ~30 rows per slot.

### [DEAD CLUSTER] ~~Section teleport landing-flag mechanism (player-physics polish)~~
> **VOID — see the DEAD CLUSTER banner.** The `SECTION_SHIFT = $0FFF` stopgap it describes, the
> `$200`/`$1200` thresholds, and `Section_Check` are all deleted. The physics concern that
> motivated it (a player flung past a boundary by a spring or terminal fall) is real and
> permanent, but under continuous scroll there is no boundary to be flung past — it degenerates to
> ordinary camera clamping.
**Surfaced during:** §4.6 T14 testing 2026-04-28.

**Current state:** `SECTION_SHIFT = $0FFF` (= FWD - BWD - 1) so post-teleport camera lands 1 px inside the safe zone, preventing idle oscillation between `$200` and `$1200`. Works for the OJZ camera-driven scroll test where camera is bounded directly by `cam_min_x` and user input is at fixed pixel-step.

**Why it's a stopgap:** when player physics arrive, the camera will follow a player position that can be flung past thresholds by springs, knockback, terminal-velocity falls, or other physics impulses. A 1-pixel margin is too narrow for momentum-based crossings — the player may overshoot and re-trigger the opposite teleport before they can move into a safe zone.

**The proper fix (sonic_hack pattern):** state-based suppression rather than geometric margin.
- Add a `Section_Teleport_Landing_Flag` byte to RAM (or reuse a bit in `Section_Preload_Flags`).
- On FWD teleport: set the landing flag.
- On BWD teleport: set the landing flag.
- In `Section_Check`: if the landing flag is set, suppress whichever teleport check is opposite to the most-recent direction. (Or: always suppress until the flag clears, which is symmetric.)
- Clear the flag when camera enters the central safe zone (e.g., `$0400 < camX < $09FF`). User must move into the safe zone before any further teleport can fire.

**Reference implementation:** `sonic_hack/code/engines/section_streaming.asm:Section_Check` lines 1100-1150. They use `ss_flags` bit 4 + `ss_landing_timer` for the same purpose; their thresholds are also asymmetric (FWD inclusive at `$1200`, BWD strict-less-than at `$200`) which complements the flag.

**When to revisit:** when integrating player physics (§3 spec). Restore `SECTION_SHIFT = $1000` at the same time so post-teleport camera lands exactly at the boundary, and the landing flag handles the rest. Until then, the `$0FFF` nudge is a clean equivalent for the camera-driven test setup.

### ~~VDP register $0B (mode_set_3) propagation bug — workaround in place (§4.6)~~ — **MISDIAGNOSIS, CLOSED (corrected 2026-08-05)**
> **⚠ THERE IS NO `$0B` PROPAGATION BUG. This entry asserts a live hardware defect that the same
> file already retracts.** The retraction is ~60 lines earlier, in the per-cell HScroll entry
> (2026-06-23), and is unambiguous:
> > "**`$0B` is NOT the problem.** With `deformBg` dropped, the VDP register `$0B` reads `$02`
> > (`hscroll_mode: cell`) correctly — per-cell IS active and the shadow→register propagation
> > works fine. The original `DeformTable_Zero` comment's 'intermittent `$0B` stuck at `$03`'
> > explanation was a **MISDIAGNOSIS**"
> — and the attempted flush-side fix (`Flush_VDP_Shadow`, branch `fix/vdp-mode3-propagation`)
> changed nothing and was deleted.
>
> **The real cause was band-boundary precision:** smooth per-pixel vertical parallax puts band
> boundaries on arbitrary scanlines (one measured at line 22), and per-cell mode can only change
> scroll at 8-px cell rows, so it tears at every band boundary during scroll. Per-line is therefore
> **mandatory and permanent**, not a workaround.
>
> **The per-frame `$0B` force described here is also gone.** `games/sonic4/test/ojz_scroll_test.emp:70`
> writes the shadow byte and dirty mask **once, at init** — it is not re-forced per frame.
>
> **Do NOT action the four "when to revisit" investigation leads below** (interrupt-time VDP_CTRL
> writes, Z80 bus interaction during shadow flush, boot register ordering, clean-place `$8B02`
> write). They chase a bug that does not exist. The whole entry stands as historical record of a
> misdiagnosis — and, per its own retraction's lesson, as the reason this repo now insists on
> reading the actual VDP register before theorizing, and on verifying under continuous motion.
**Surfaced during:** §4.6 polish session 2026-04-28.

**Symptom:** When `pcfg_deform_table_fg` and `pcfg_deform_table_bg` are both NULL (e.g. ParallaxConfig_OJZ_Default), the parallax pipeline auto-selects per-cell HScroll mode: `Parallax_Fill_PerCell` writes 28 longwords, the per-cell static DMA enqueues 112 bytes, `setVDPReg vdp_mode3 = $02` marks shadow dirty, and Flush_VDP_Shadow writes $8B02 to VDP_CTRL on every VBlank. Visually we expected per-cell HScroll: all 28 cell rows scroll uniformly with the same `-Camera_X`. We observed instead per-line behavior: only scanlines 0-27 (the top 28 px = 3.5 cell rows) scrolled correctly, lines 28-223 stayed pinned to plane col 0.

**Empirical proof of per-line state:** Patching VRAM HSCROLL_TABLE entries 28-223 directly with proper PA values via `mcp__exodus__emulator_write_vram` made the entire screen scroll correctly. This is only possible if VDP register $0B has bits 1:0 = %11 (per-line). VDP shadow byte at offset 11 reads $02 and dirty bit 11 stays set, but the visual proves register $0B is $03.

**What we tried (all failed):**
- `setVDPReg vdp_mode3, #$02` every frame in OJZScroll_Update (shadow + dirty path).
- Direct `move.w #$8B02, (VDP_CTRL).l` with stopZ80 wrap.
- Adding a state-machine reset (`move.w (VDP_CTRL).l, d1`) before the direct write to clear any half-finished 32-bit address command.
- None changed the register's per-line behavior.

**Workaround in place (2026-04-28):**
- `data/parallax/ojz_default.asm` defines `DeformTable_Zero` (256 zero bytes) and adds `deformBg=DeformTable_Zero` to both `ParallaxConfig_OJZ_Default` and `ParallaxConfig_OJZ_Floor`. This forces the entire pipeline (Parallax_Update auto-select, Enqueue_Dirty_Buffers DMA selector, OJZScroll_Update mode_set_3 force) into per-line mode for these no-/V-only-deform configs.
- Cost: ~1500-2000 extra cycles per frame (224-line fill vs 28), 8× HScroll DMA bandwidth (896 vs 112 bytes), 256 bytes ROM for the zero table. With sample = 0 the deform sampling adds 0 to each line — no visual change.
- ParallaxConfig_OJZ_Windy was unaffected (it has a real BG H-deform table and was already per-line).

**When to revisit:** When the per-cell mode is needed for performance budget. Investigation should focus on:
1. Possible interrupt-time VDP_CTRL write that lands between Flush_VDP_Shadow and the next render.
2. Possible Z80 bus interaction during the shadow flush — the Z80 isn't stopped during Flush_VDP_Shadow's individual `move.w` writes.
3. Re-examine whether Boot's initial VDP register write loop properly writes $0B = $00 then OJZScroll_Init's setVDPReg path correctly upgrades it to $02 on first VBlank.
4. Try writing $8B02 to VDP_CTRL in a known-clean place (e.g. immediately after `Flush_VDP_Shadow` returns, with explicit Z80 stop) and observe if behavior changes.

**Bare-minimum reproduction:** Remove `deformBg=DeformTable_Zero` from `ParallaxConfig_OJZ_Default`, build, load OJZ scroll test, scroll right. FG bricks scroll correctly only on top 28 scanlines; rest of the screen shows plane A column 0 stuck.

### ~~Parallax_Current_Config / Camera_Y intermittent clobber (§4.6)~~ — ROOT-CAUSED + FIXED 2026-06-10
**Root cause:** `TestPlayer_Main` read `Ctrl_1_Press` into **d7 — the RunObjects
loop counter** (object routines must preserve a0/d7). Every press edge extended
the player slot loop by the press bitmask value: the dispatcher marched up to
255 slots past `Player_1`, re-running live objects, then executing free-stack
words and arbitrary RAM as `code_addr` offsets into `ObjCodeBase`. Real object
routines invoked on garbage "slots" wrote SST fields through a0 at arbitrary
RAM (the zeroing symptom); level data executing as code produced stray writes
like `$FF71FF71` (the garbage symptom) or ILLEGAL INSTRUCTION (live crash
captured in Exodus 2026-06-10: a0=$FFFF9E14 = Dynamic_Free_Stack, d7=1,
caller RunObjects.always_next, jump target OJZ_SEC2_BLOCKS+$1640).
**Fix:** press bits moved to d4 (`objects/test_player.asm`); debug builds now
assert the a0/d7 loop contract after every dispatch (`Debug_AssertObjLoop`,
`engine/objects/core.asm`). Pointer-validation band-aids removed from
`Enqueue_Dirty_Buffers`, `Parallax_Update`, `Vscroll_Write`, and the OJZ test
mode-set-3 force. Re-test of the three §4.6 visual artifacts done 2026-06-11 —
all three resolved (see the artifacts entry above).

Original investigation notes kept for reference:
**Surfaced during:** §4.6 T12 testing (2026-04-27).
**Symptom:** During §4.6 T12 v2 debugging, multiple MCP reads showed
`Parallax_Current_Config = $00000000` and `Camera_Y = 0` even though
`Parallax_Init` and `Camera_Init` had set them correctly at boot. The
zeroing wasn't caught by Exodus MCP watchpoints, didn't fire the
breakpoint at the only `move.l #0, (Camera_Y).w` instruction
(`object_test_state.asm:34`, never on the OJZ scroll test path), and
no code path in the OJZ scroll test Update flow writes either field.
The corruption is intermittent — repeated single-step sessions sometimes
showed the values intact and Vscroll_Factor lerping correctly.
**Practical workaround in place:** OJZ parallax configs use
`vCenter=0, vOffset=0` so even when `Parallax_Current_Vscroll_BG` ends
up at a wrong negative steady-state value (we observed -59 instead of
the expected 62), the BG plane stays anchored at the top where the
nametable is fully populated. With OJZ being X-only-scroll in §4
Phase 1, this is functionally invisible.
**When to revisit:** When adding vertical camera scroll (§4 Phase 2+),
the parallax math depends on Camera_Y being accurate frame-to-frame.
Suspect candidates to investigate: (a) interrupt-time write through a
stale or corrupt pointer, (b) movem-out-of-bounds on the supervisor
stack at $FFFFFEF8 (lots of save/restore traffic in band loop +
VBlank handler), (c) Exodus MCP watchpoint not actually catching
writes in this build.
**Bare-minimum reproduction:** Build current `master`, load in Exodus,
let it run a few seconds at the OJZ scroll test, MCP-read
`Parallax_Current_Config` and `Camera_Y` repeatedly. Both should be
non-zero; intermittently they read zero.

### ~~OJZ Tile Art Loading — Full Terrain Visibility~~ — DONE 2026-04-26
**Completed in:** §2 Phase 2 Layer A.1 (tile dedupe + nametable remap)
**What:** ojz_strip_gen.py now globally dedupes tile data with hflip/vflip canonicalization across all 16 sections and rewrites strip files to reference the new compact index space. The deduped pool (10 tiles for OJZ act 1's current visible 48-row strip band) loads via Level_LoadArt → S4LZ_Decompress → DMA. Strip tile-index ceiling collapsed from 1856 → 9; nametable at VRAM $C000 is no longer at risk of being clobbered.
**Caveat:** Visible band still capped at strip rows 0-47 (sprite attribute table at VRAM $D800 = nametable row 48). Showing the *full* layout (chunk rows 2-12 of the 16-row OJZ layouts, the actual ground terrain) requires vertical-axis section transitions (still §4 deferred) or relocating the sprite table out of the Plane A nametable region (not currently planned). The pipeline is correct end-to-end; only the camera/strip envelope limits how much of OJZ becomes visible at once.
**Measurements:** see `docs/research/tile-pipeline-measurements.md`.

---

### ~~Chunk/block parsing produces mostly-empty tiles~~ — DONE 2026-04-26
**Completed in:** kos_decompress rewrite
**What:** Root cause was the homegrown Kosinski decoder in `tools/ojz_strip_gen.py` — subtle bit-order / displacement bugs that produced ~5× too much output and ~50% of blocks parsing as all-zero. Hypothesis 1 (multi-stream Kosinski) was wrong; hypothesis 2 (block-ID mask) was wrong. Real bug was the decoder itself. Fixed by porting `sonic_hack/code/engines/kosinski.asm` KosDec literally to Python: LUT bit-reversal of each descriptor byte + `add.b`-style MSB-first reads, exact stream-copy semantics matching the asm.
**Post-fix verification:** chunk 0x3f now references blocks 272-302 (all 4/4 non-zero, real ground data). Block count: 374 (was 2002 garbage). Tile art: 919 tiles (was 322 truncated). 141 unique source tile indices in OJZ act 1 sec0 strips (was 14). With this fix + a related palette-line-1 offset fix in the test state (sonic_hack's `palptr Pal_OJZ, 1` means OJZ palette occupies CRAM lines 1-3, not 0-2), the OJZ scroll test now renders actual OJZ art with correct green palette. Verified via Exodus Plane A viewer.
**Bonus learning:** Investigation revealed I had been over-confidently calling sparse-pixel screenshots "clean rendering" through A.1-A.3 verification. Honest visual ground truth (level editor screenshots from the user) was what surfaced the bug. Process lesson saved as a memory.

## From §7 — Visual Effects (design-stage)

### Palette transition on section crossing (§4.8 / §7.1) — NOT IMPLEMENTED — recorded 2026-08-08
**Surfaced during:** 2026-07-15 alignment audit (ENGINE_ARCHITECTURE.md presented palette-transition-on-crossing as if shipped; zero implementation existed). The doc claims were re-marked honestly (§7 banner, §7.1 shipped-vs-planned split, §4.2 `sec_pal` "descriptor field only", §4.8 blend-sections status) — this entry is the backlog row those pointers land on.
**What:** No section-crossing palette code exists in `engine/level/` (verified 2026-08-08: no palette/CRAM/fade references there at all). `sec_pal` and `sec_pal_cycle` are reserved descriptor fields with no runtime consumer. The shipped palette path is game-poked only: game code writes `Palette_Buffer` + `Palette_Dirty` bits and `Enqueue_Dirty_Buffers` DMAs dirty lines to CRAM (§7.1). The planned design — descriptor-driven palette load on crossing, instant or ~16-frame RGB-lerp cross-fade, per-section cycling, blend cells (§4.8) — is future §7 work.
**Blocked by:** §7 Visual Effects execution (palette-system design phase); nothing technical. The Deep-Forest-BG entry's "per-section palette variants" (below) is the cheap first step and depends on the same mechanism.

### An import prune into a pointer-typed struct field is caught late and positionally — recorded 2026-08-13
**Surfaced during:** effects P3 Parcel A, Task 9 (the import prune on `games/sonic4/data/parallax/configs.emp`).
**What:** A comptime fn's free names resolve at the EMISSION site, so a constructor's returned struct literal needs its constant names imported into whatever module emits the `pub data`. A missing import does not error there — the bare name degrades to a label reference, and *which* error you get depends on the destination field's type. Measured: dropping `RASTER_ARM_PARK` + `RASTER_OPS_END` failed as `[emit.type] expected an integer for u16, got label` — named, and phase-early, because those fields are `u16`. Into a pointer-typed field a label reference is well-typed, so emit accepts it and the reference becomes a data fixup; the catch defers to link and arrives positionally instead: `unresolved symbol … for fixup in section … at offset …` (`sigil-link/src/lib.rs:432`). Comptime constants lower to zero link symbols, so a degraded constant name has no definition to find. `resolve::report_unresolved` would name it, but is gated on `closed` and does not run for aeon's mixed AS + `.emp` build (`build_program_open_embed`). **Not silent — deferred and de-named.** The genuinely silent case is narrow: a degraded name that collides with an actually-defined label or `equ`. No pointer-field instance exists in the tree today (`RasterGradientProgram.rgp_stream`'s value comes from `raster_gradient_program`'s `stream: Label` parameter, supplied at the call site, so no free name reaches it). Documented in place at `configs.emp`'s dense-tier import comment.

### The raster DSL covers the SPARSE tier only — recorded 2026-08-13
**Surfaced during:** effects P3 Parcel A (`engine/effects/raster_dsl.emp`).
**What:** `raster_program` authors sparse-tier programs only. The dense tier keeps its own constructor `raster_gradient_program` (`engine/effects/raster.emp`), because a `[u16; N]` array cannot hold a link-time symbol and a dense program carries a ROM stream pointer — so the two tiers cannot share one constructor without a wire-format redesign. Separately, the wire format *permits* sparse events before and after a dense run (`Raster_HInt`'s `.op_run_gradient` falls through to `.advance`), but **neither constructor can author that combination**, and a section must take one tier or the other. No Phase-3 content requires the mix. Unifying the tiers is out of scope for Phase 3 by design, not by omission.
**Blocked by:** nothing technical; it is a wire-format redesign nobody has needed yet.

### `region_boundary`'s signature is Parcel-A-shaped — recorded 2026-08-13
**Surfaced during:** effects P3 Parcel A, Task 6.
**What:** The design spec sketched `region_boundary(line:, variant:, sh:)`. The shipped constructor takes `(line, addr, slot, pal_line, entry, count, sh)` — the parameters `OJZ_WaterRaster` actually needs — because the sketch's `variant:` handle presumes the `EffectsPreset` binding that does not exist until Parcel C. Parcel D re-shapes the signature once the starter pack's needs are known. Note `sh` deliberately has **no default**: `sh: 0` yields a program with zero init words, which moves the priming arm word off word 3 while `Raster_PatchWaterLine` patches byte offset 6 unconditionally. A default would have made that corrupt case reachable by omission.
**Blocked by:** Parcel C (the preset binding), then Parcel D (the pack's real authoring needs).

### Which screen line a raster VSRAM write lands on — MEASURED N+1 (2026-08-14)
**Surfaced during:** effects P3, the five-lens review fixes (`vsram()` added to `engine/effects/raster_dsl.emp`).
**What:** `vsram(addr, values)` reuses `Raster_HInt`'s target-agnostic `.op_cram` path (the handler issues whatever command longword the program carries and never inspects its target bits), so it needed zero runtime change. What it did NOT come with is a measurement. The VDP latches the next line's render state ~36 cycles after HInt asserts while the 68000 needs ~44 cycles to reach the handler; CRAM and reg `$07` are unlatched and apply to line N+1, which is what the DSL's screen-line = fire-line + 1 rule encodes — **but VSRAM may be latched, in which case a write issued from the handler first takes effect on line N+2.** Sources conflict and emulators differ. The constructor therefore ships with the same screen-line semantics as `cram` and a prominent comment saying so.
**What is owed:** an oracle measurement — author a `vsram` fire at a known line, screenshot, and read where the scroll discontinuity actually falls. **No content may rely on the exact landing line until that runs.** If it measures as N+2 the fix belongs in the *constructor's* line arithmetic (schedule the fire a line earlier, or carry a per-op line bias into `fire_lines`), never in the handler: target-agnosticism is the property that made the op free, and it must stay.
**Blocked by:** nothing — it is one oracle session, and it wants doing before the first banded-vertical-scroll section is authored.

---

## From §4.6 — Parallax (post-T17 backlog)
**RESOLVED 2026-08-14 on oracle.** `OJZ_TestVsram` (section 0) authored at screen line 112; against a control build differing only in the offset, the first differing pixel row is exactly **y=112** and rows 108-111 are pixel-identical. A VSRAM write from HInt therefore lands on **N+1**, and the DSL's existing `-1` fire-line arithmetic is correct for VSRAM with no separate rule. Caveat kept open: emulators disagree on mid-frame VSRAM (GensKMod latches at HBlank start, Exodus/BizHawk consult continuously); oracle is Exodus-derived, and this project has no real hardware, so N+1 is the best available evidence rather than a hardware fact.


### Per-block linear interpolation deformation format
**Blocked by:** N/A — deliberately not in v1.
**What:** S.C.E.'s block-based deformation table format with high-bit linear-interp flag. Variable-height blocks save ROM (~32 bytes vs ~256 bytes per table). v1 uses full 256-byte time-varying tables — block format is a ROM-saving optimization we don't currently need.
**When ready:** if a section's deformation table waste becomes a real ROM problem (currently affordable — 256 B per shape, shared across sections that use the same shape).

### Per-band deformation table pointers
**Blocked by:** visual demand for different wave shapes per band.
**What:** Each band points at its own 256-byte deform table. Currently single shared table per section (`pcfg_deform_table_fg` / `_bg`) + per-band amplitude/phase via `BAND_DSA/B` and `BAND_PHASE`. Adds 4 bytes per band (table pointer field) + multiple tables per section.
**When ready:** when a section visually requires different shapes per band — e.g., square wave for one band, sine for another.

### Per-band frequency variation
**Blocked by:** visual demand.
**What:** Per-band `phase_increment` byte. Currently only phase OFFSET varies per band (frequency is section-wide via `pcfg_deform_speed_fg/bg`).
**When ready:** when "different speeds per band" surfaces as a clear visual need.

### Plane A per-column V-scroll
**Blocked by:** use case (ground-plane warping is rare in Sonic-style platformers).
**What:** `pcfg_v_deform_table_fg` field is reserved but not wired in v1. Currently the FG plane always uses whole-plane V-scroll; `Vscroll_Write`'s per-column branch only writes the BG word per column-pair from `Parallax_Vscroll_Column_Buf`. Implementation is symmetric to the BG path — ~30 cycles + 80 bytes RAM for an FG column buffer + the fill code in `Parallax_Update`.
**When ready:** when a section needs ground-plane vertical warping (special-stage 3D floors, post-explosion ground sink, banking-platform foreground variants).

### Sprite mask for per-column V-scroll leftmost-partial-column garbage — RESTATED by P3 Task 12, 2026-08-21 (policy layer LANDED, emission still open)
**What (unchanged):** Genesis VDP per-column V-scroll grain is 16 px. With non-zero plane B HScroll, the leftmost screen sliver renders at V-scroll = 0 regardless of VSRAM[0] — silicon-level, no register fix. Real games drop a sprite strip over the left edge to hide it (Battle Mania 2, Sonic 3 Hydrocity boss arena) or ship it (Gynoug).

**What P3 Task 12 CLOSED (branch `p3/t12-left-column-mask`):**
- The policy is now MANDATORY and authored, not implied: any scene attaching `SceneVDeform.Columns` must declare `left_column_mask: SceneLeftColMask.{SpriteMask|Factor0Lock|Accept}` or the build fails carrying the scene's authored signature (`scene()` in `engine/level/scene_dsl.emp`; a declaration on a non-per-column scene is refused as noise).
- `factor0_lock` is a VERIFIED claim, both halves: every real layer `fb == FACTOR_0` AND no live plane-B deform amplitude with a table that can reach the plane — the second half because deform re-adds per-line HScroll on top of a locked factor (this booking's original "locking plane B HScroll to 0 eliminates the partial column" was only true table-free; Perspective's shimmer floor is the shipped counterexample).
- `accept` is spellable and is what both shipped per-column families now declare — Rocking because its factor0 truth (all-zero table) is comptime-invisible, Perspective because its artifact is genuinely reachable on the dsb-live rows.
- The axis-5 price is measured, ruled and gated: **7 SAT table slots** full-height at the shipped 8×32 mask geometry (not the 1 design §2 priced), 1 sprite + 8 px on any line where the axis actually binds (per-line count) — accepted per `axis5_task12_resolution` in `tools/effects_budget_model.toml`, enforced every canonical build by `check_axis5_mask_pricing()` in `tools/effects_budget_check.py` (red-first both arms).
- The claims are ROM-verified: `tools/left_col_mask_probe.py --claims` (static, .lst + ROM, offsets derived from the struct declarations).

**What is STILL OPEN — the `sprite_mask` ENGINE EMISSION. `scene()` refuses the SpriteMask variant, loudly and by name, until this lands.** Blocked by, precisely:
1. **The cross-seam pair.** The per-frame strip emission belongs in `Render_Sprites` (`engine/objects/sprites.emp`), must be capability-gated to stay zero-byte in games that don't raise it — and sprites.emp has ZERO `Game.*`/`CAP_*` references today, so the gate is the module's FIRST cross-seam reference: a sigil isolation-port flip requiring an aeon+sigil pair landing (the P3 plan's trap ledger predicted exactly this for Task 12). A build-define gate has the same shape (the port env must learn the define). Overseer-gated.
2. **The opaque tile is a game hook** (this booking's original "zone level data hooks" half): the strip needs a game-owned fully-opaque tile + palette line; the engine cannot know a game's VRAM layout. Natural shape: the SpriteMask variant grows an `art_tile`-word payload when the emission lands.
3. **Mechanism ruling (RECORDED — the emission parcel must honour it):** the strip is OPAQUE sprites at screen X 0 (SAT X = 128), priority set, FIRST in the link chain (priority + exemption from per-line-limit drops). The VDP's X=0 sprite-MASKING feature CANNOT serve: it suppresses later sprites on covered lines and never repaints a plane pixel, and its first-sprite-on-line exemption makes it fail closed on top. The MD1-vs-MD2 partial-column fill value stays UNPINNED and is irrelevant to an opaque cover — it covers whatever was fetched. Capability: a NEW bit arriving WITH its gated block (per the promotion rule); `CAP_FG_SPRITE_STRIPS` is a different mechanism and stays reserved.
4. **Runtime verification is staged:** `tools/left_col_mask_probe.py --mask` exits 2 (no subject) today and carries the full oracle-bus check list for the emission parcel's instrument build, including the per-line engagement check. Foreground/controller only.

**When ready:** when a section uses per-column V-scroll *and* wants non-zero plane B HScroll (today NO installable config enters per-column mode — Rocking/Perspective are registry-only, probe-verified), or when Perspective's shimmer-floor sliver starts to matter visually. Cost when adopted: 7/77 table slots, 1/18 per-line sprites, 8/288 per-line pixels against the measured idle reservation. Side note for the same day: re-authoring Rocking's `dsb: 4` to 15 would unlock the verified `Factor0Lock` spelling at the cost of one shipped record byte per Rocking config (image-identity churn — owner call).

## From §4.9 — Section-Local Entity Management

### ~~§4.9.4 Rolling 4-Slot State Tracking (Respawn Memory)~~ — SHIPPED 2026-06-12
**Resolution:** `Ring_Collected_Park` (4 × 33 B rolling park, 134 B total) parks a section's
collected/killed bitmasks when `Collected_UpdateCenter` evicts it from the 3×3 window
(pristine sections skipped) and restores them in `Collected_ClaimSlot` on re-entry.
3×3 window + 4 park = 13 remembered sections — covers OJZ's whole act (zero resurrection);
larger acts degrade classically at long range. Spec: `docs/superpowers/specs/2026-06-12-respawn-memory-design.md`,
commit 235e200. Follow-ups from review (minor): (1) restore-leg verification read only the
collected mask — re-verify the killed mask round-trip plus a live no-respawn census when a
killable object path exists; (2) freed park entries aren't preferentially reused — rolling
overwrite can evict a live entry while a freed slot idles (effective capacity dips under
mixed traffic; spec-compliant, revisit if park pressure appears); (3) natural-eviction
retest needs an act larger than 3×3 — re-run when one exists.

### ~~§4.9.5 Warp-Based Teleport Preview (Entities in Preview Zone)~~ — SHIPPED 2026-06-12
**Resolution:** Visibility-derived window makes preview intrinsic. The despawn envelope overlaps sections ahead of the camera before any teleport fires — those sections are tracked, their entities are in the buffer. No warp coordinates, no coordinate shift, no integration work. Closed by the visibility-window plan (branch `vertical-entity-window`); see ENGINE_ARCHITECTURE.md §4.9.3.

### Bouncing "Loss Rings" (Ring Scatter on Damage)
**Blocked by:** §4.9 ring system + player damage system
**Surfaced during:** §4.9 design session 2026-04-29.
**What:** When the player takes damage, scatter N rings as temporary SST objects (not buffer entries). Each has physics (gravity, bounce), a lifetime timer, and can be re-collected. Uses AllocEffect slots (lightweight). These are separate from level-placed buffer rings — buffer rings are static positions with bitmask state, loss rings are short-lived physics objects.
**When ready:** After player damage/hurt system exists (§3 player physics) and ring collection works.
**Re-checked 2026-08-26 (ring-sparkle parcel):** still ABSENT — `grep scatter/lost_ring/LostRing` over `engine`/`games` is empty. Ring collection now works and the collect sparkle shipped (see the 2026-08-26 stratum at the end of this file), so the only remaining blocker is the damage system. The S3K reference is `Obj_LostRings`; the sparkle parcel's effect-pool shape (`RingSparkle_Spawn`) is the template for the scattered ring objects.

### Ring Attraction (Magnet Shield)
**Blocked by:** §4.9 ring system + shield system
**Surfaced during:** §4.9 design session 2026-04-29.
**What:** When player has magnet shield, uncollected rings within attraction radius accelerate toward the player. Modifies the per-frame ring collision check to also compute distance and apply pull velocity. Only affects buffer rings within range — loss rings (SST objects) would have their own attraction in their object code.
**When ready:** After shield system exists (§3 player abilities).

## From Teleport-Rebase (2026-06-10)

### ~~CRITICAL: FWD teleport advances slot pair out of a narrow grid~~ — DONE 2026-06-11
**Surfaced during:** teleport-rebase verification 2026-06-10 (pre-existing). **Fixed in:** grid-edge branch.
**What it was:** `Section_TeleportFwd` advanced the pair `(0,1) → (2,3)` but OJZ act1 is a 3×3 grid — sec_x=3 doesn't exist; the entity window built scan state from a garbage Sec pointer → DEBUG assert in `Collected_CheckRing` (release: undefined ring spawns) on walking right past `x=$1200`.
**Fix shipped:** `SEC_VOID` ($FF) sentinel in slot-1 sec_x past the grid; guards in `Section_Check .fwd_check` (sentinel check before the wrapping addq), TeleportFwd's SS_RESIDENT mark, EntityWindow Init/Rebuild slot-1 blocks (skipped; `Entity_Window_Active`=1; the stale entry's section_id stamped SEC_VOID for the despawn exemption), camera max-x void clamp ($8C0 = slot-0 right edge), `TileCache_DecompressBlock` world-edge guard (out-of-grid blocks decompress blank — also fixed the latent bottom-edge Sec-table overread that vertical fills have had since shipping), prefetch sec_x guard. BWD heals the pair (new slot 1 = old slot 0 − 1). Exodus-verified end to end (warp right → pair (2,$FF), objects spawn, camera pins $8C0, BWD returns (0,1)).
**Still open (minor, from review):** `Section_Check` clobber header understates; classic-style player X clamp at camera bounds (player can currently walk past the camera into the void region — level data should wall it, but a bounds clamp matching the classics is worth considering with §3 player physics).

### ~~Per-section BG layout swap at the seam (T2/T3 zones)~~ — SUPERSEDED 2026-06-12
Superseded by the full BG seam-streaming spec ("From Deep Forest BG Work
(2026-06-12)" below). The original observation stands: teleports no longer
run `Section_RedrawPlanes`, all production data is T1, and any per-section
BG needs a non-blocking streaming mechanism, not a synchronous blit.

## From Deep Forest BG Work (2026-06-12)

### SPEC: Per-section background grid with seam streaming
> **Update (2026-08-08):** a full research pass
> (`docs/research/2026-08-08-bg-seam-streaming.md`) corrected four of this
> sketch's assumptions before design: layouts are **64×64/8192 B** (not 64×32 —
> re-derive all byte math); the transport should be the **`Plane_Buffer`** path
> (the purpose-built zero-caller `Draw_BG_TileColumn` already exists there —
> not `QueueDMA_Deferrable` as written below); horizontally there is **no single
> BG camera** (per-band `Parallax_Current_Scroll_B` — the uniform "camX/8 margin"
> math below only holds vertically, which locks in the vertical-first order); and
> the tile ceiling is 448 (the two-half-pool idea stands). That doc carries the
> revised build order + the open user rulings; this sketch remains the component
> inventory.
**Goal:** each section (or section row/column) gets its own background from
the editor's per-section BG assignment, and the engine stitches them into
one continuous world as the player travels — no visible swap, both axes.
User intent: "section below the forest has the darker firefly one, and the
tree one above connects to it."

**Why it works (the headroom argument):** Plane B is 64×64 cells (512×512px)
but the screen shows only 320×224. At the BG's parallax factors the hidden
margin is enormous in camera terms: vertically, 288 hidden px at camY/8 =
2304 camera px (more than one 2048px section row) before an off-screen row
wraps back into view; horizontally, 192 hidden px at camX/8 = 1536 camera px.
Rows/columns that scroll off one edge are rewritten with the NEXT section's
BG via QueueDMA_Deferrable long before they re-enter from the other edge —
the same trick as FG column streaming, applied to Plane B on both axes.
Bandwidth is trivial: one plane row or column = 128 bytes; a few per frame.

**Components:**
1. **BG grid data.** Zone data gains a BG-grid table: section (or section
   row/col band) → {nametable region ptr, tile blob ptr, anim band table
   ptr, palette line variant}. Editor already has per-section BG assignment
   (UI exists, engine unwired); injector emits the grid instead of the
   single zone-wide override.
2. **Seam tracker + row/col streamer.** Engine-side state: which BG region
   each plane row/column currently holds, and a per-frame budgeted streamer
   that rewrites rows/cols in the hidden margin toward the target (derived
   from camera section position + scroll direction). Mirrors the FG
   preview-column scheduler. Teleport rebases are coordinate-invariant on
   the plane (mod 512), same as FG — the streamer keys on world-derived BG
   scroll, not raw camY.
3. **Tile budget across the seam.** Both themes' tiles coexist in VRAM while
   a seam is in transit. Strategy: split the 448-tile BG pool into two
   half-pools (~224 each, minus shared animated slots); the streamer loads
   the incoming theme's blob into the inactive half (deferrable DMA, chunked)
   before its nametable rows reference it. Editor enforces per-theme budget
   (set_bg validator) and a shared-atlas option for themes that intentionally
   share tiles (forest ↔ darker forest).
4. **Animated bands per theme.** BgAnim_Table is per-act today; becomes
   per-theme, swapped when the seam fully clears the screen (bands reference
   fixed VRAM slot ranges, so the safe-swap moment = no on-screen rows from
   the outgoing theme). The table-driven design (driver/rate/dest per band)
   already supports this — needs a "active table ptr" indirection + handoff.
5. **Seam contract in the editor.** Two modes per adjacent BG pair:
   - **connects-to:** the arts' meeting edges are authored to blend (e.g.
     forest bottom rows = firefly zone top rows). Editor feature: edge
     preview of A-bottom against B-top (and A-right against B-left), plus
     a palette-compatibility check.
   - **disconnected:** transition must be masked. Two sanctioned tricks:
     (a) FG occlusion — level geometry covers the full screen height while
     the seam crosses (cave mouth, tunnel, waterfall; classic S3K), with an
     instant region swap while occluded; (b) palette blackout — fade the BG
     CRAM line to black over ~16 frames, swap/stream while black, fade up
     (thematically free for caves; needs the per-section palette mechanism).
6. **Per-section palette variants** (cheap multiplier, can ship first):
   same art, darker/tinted CRAM line per section row, lerped at the seam.
   The harness's per-section sky-tint table is the prototype.

**Constraints / open questions:**
- Vertical wrap vs themes: the current 512px art wraps seamlessly (camY/8 ×
  $1000 rebase = exactly one plane height). With per-row themes, the wrap
  must land on the THEME boundary — keep vFactorBg=3 and make each theme's
  vertical slice 512px (one full plane per section row) or 256px (two rows
  per plane); pick during design.
- Diagonal travel: two seams (X and Y) can be in transit at once; streamer
  must handle a 2D dirty region, or sequence one axis at a time with the
  hidden margin as slack.
- Parallax config per theme: band factors may differ per BG (the Sec3
  LockedClouds incident shows per-section configs + plane-space bands must
  agree); fold parallax config into the theme record so it swaps with the
  art under the same safe-swap rule.
- Budget the streamer against the existing deferrable consumers (BgAnim
  banks, DPLC, section streaming) — the queue is shared.

**Suggested build order:** (a) per-section palette variants (standalone
win), (b) vertical-axis streaming with connects-to seams only (forest →
firefly section: the motivating case), (c) horizontal axis + disconnected
transitions (palette blackout first, FG occlusion as level-design tooling),
(d) per-theme anim-table + parallax-config handoff, (e) editor seam
contracts + budget validation.
**When ready:** next major BG work block; (a) any time.

## From Vertical Entity Window — Task 6 (2026-06-11)

### ~~Teleport keep-range tests pre-shift coords against the post-rebase camera~~ — DISSOLVED 2026-06-12
**Resolution:** The keep-window no longer exists. The visibility-derived window retains all entities across a teleport (shift, no despawn); there is no keep-range test to get wrong. This defect was only relevant under the old TeleportShift keep-window/despawn design, which was deleted in the visibility-window plan.

### ~~No survivor continuity across teleports (per-entry loaded masks can't cover off-window sections)~~ — DISSOLVED 2026-06-12
**Resolution:** The keep-window no longer exists. The visibility-derived anchor is invariant across rebases — the same sections are tracked before and after — so there are no "just-left-the-window survivors" to worry about. The duplicate-spawn risk that blocked the keep-range fix is also gone: teleports never populate, so no re-add can occur. Closed by the same design deletion.

## From Vertical Entity Window — Task 8 closeout (2026-06-11)

### [DEAD CLUSTER] ~~X-BWD clamp-to-zero degenerate slot pair~~
> **VOID — see the DEAD CLUSTER banner under §4.** `Section_TeleportBwd` and its clamp-to-zero
> path are deleted, and there is no slot pair to be degenerate. The `section.asm ~:481` anchor is
> doubly dead (the file is `.emp` now, and the routine is gone). The "revisit if any act starts at
> an odd `sec_x`" trigger can never fire.
**Surfaced during:** Task 8 teleport-table review 2026-06-11.
**What:** From an odd start `sec_x`, `Section_TeleportBwd`'s clamp-to-zero (section.asm
~:481) can produce BOTH slots tracking section 0 — a two-entries-same-section window
state that nothing else can create. The teleport disjointness/no-op argument is
unaffected (the moved block is still disjoint from the old one), but the duplicate-entry
state itself is untested: two scan states + two loaded-mask slots for one section.
**When to revisit:** if any act ever starts at an odd `sec_x`. All current acts start
at `sec_x = 0`.

### SEC_VOID vs flat-id 255 alias
**Surfaced during:** Task 8 closeout review 2026-06-11.
**What:** `SEC_VOID = $FF` lives in the same byte namespace as flat section ids, and on
a 16×16 grid the real bottom-right section has flat id 255 = $FF — a void-sentinel
alias. Separately, `EntityWindow_BuildEntries`' void path stamps the sentinel but does
NOT clear the entry's loaded-mask slot (safe today only because `InitSection`'s
compare-clear wipes it whenever a real section later claims the entry).
**When to revisit:** if act grids ever approach 16×16 (current max is 3×3), or if any
new consumer reads `Entity_Loaded_Masks` for void entries.

### RescanY burst is unbudgeted
**Surfaced during:** Task 8 closeout review 2026-06-11.
**What:** A 128px coarse-row crossing re-walks all 4 entries' ROM lists from index 0 up
to each X ratchet in a single frame. Trivial on test fixtures (≤16 entities), but on
dense production levels (40-50 rings/section × 4 entries, ratchet fully advanced) the
burst could reach tens of K cycles in one frame — same shape as the tile-cache fill
bursts that needed N-way staging + a frame budget (2026-06-10).
**When to revisit:** when real level data lands — watch `Lag_Frame_Count` during fast
vertical traversal (the profiler misses single-frame bursts). Tile-cache N-way staging
is the precedent if budgeting is needed.

### Entity despawner micro-opts — **dead-field half DONE, but the refund is SPENT (corrected 2026-08-05)**
> **⚠ THE PROMISE IN THIS ENTRY IS NO LONGER DELIVERABLE — the struct will NOT shrink.**
> The dead fields `ess_ring_left_idx`/`ess_obj_left_idx` are **gone** (zero hits), so that half is
> done. But `EntityScanState` did **not** shrink to `$16`: it is still declared
> `struct EntityScanState (size: $1A)` at `engine/objects/entity_window.emp:45`, because the four
> reclaimed bytes were **immediately reused** by the trigger caches
> `ess_ring_next_x: u16 @ $16` and `ess_obj_next_x: u16 @ $18` (":engine-X of next ring/object
> entering right; $FFFF = none"). Those are live fields serving the X ratchet.
> **Anyone planning a `$1A → $16` shrink from this entry will find nothing to remove.** Also note
> the module moved: `engine/objects/entity_window.emp`, not `engine/level/`.
>
> **The other two halves are still genuinely open** and were re-verified: the loop-invariant Y
> band-bound hoist in `DespawnRings`/`DespawnObjects` (~3.5k cycles/frame at a full 128-ring
> buffer), and trimming `RescanY`'s defensive d7 save. Those remain the actionable content.
> Original text below.
**Surfaced during:** Task 8 closeout review 2026-06-11.
**What:** `DespawnRings`/`DespawnObjects` recompute the loop-invariant Y band bounds
per entity (~3.5k cycles/frame at a full 128-ring buffer — hoist to registers before
the loop). `RescanY`'s defensive d7 save around the scan calls can likely be trimmed
once the RunObjects d7 contract is re-audited. Also: `ess_ring_left_idx`/
`ess_obj_left_idx` are dead struct fields (cleared at init, never read — the X scan
is a right-edge ratchet; no left scan exists). Removing them shrinks EntityScanState
$1A → $16 and stops tempting docs into describing phantom left scanners.
**When to revisit:** alongside any other §4.9 perf work (e.g. the RescanY budget entry
above) — not worth a dedicated session.

## From Visibility-Window Plan (2026-06-12)

### Slide populate is X-unfiltered
**Surfaced during:** visibility-window plan implementation 2026-06-12.
**What:** `EntityWindow_PopulateSectionRings` (and the object equivalent) offers every entry in the section's ROM list to `TrySpawnRing`/`TrySpawnObject` without an X edge filter. On a rightward slide the newly tracked section can be up to ~$500px beyond the right load edge, so all its in-band rings are added immediately rather than waiting for the ratchet to reach them. Fine at current entity counts; could front-load spawns noticeably on dense production sections.
**When to revisit:** when production entity density lands — watch `Ring_HighWater` after a slide vs a normal X ratchet advance. Perf backlog family (tile-cache N-way staging is the precedent for budgeted populate).

### [DEAD CLUSTER] ~~Section_TeleportBwd .at_start clamp path lacks a SyncSlide-style guard~~
> **VOID — see the DEAD CLUSTER banner under §4.** `Section_TeleportBwd`, `EntityWindow_SyncSlide`,
> `EntityWindow_TeleportShift` and `Slot_Section_Map` are all deleted (zero hits each). There is no
> path to guard and the "add the defense when `Section_TeleportBwd` is next modified" trigger can
> never fire.
**Surfaced during:** visibility-window plan review 2026-06-12.
**What:** `Section_TeleportBwd` calls `EntityWindow_SyncSlide` unconditionally before the camera rebase, then may fall through `.at_start` with the slot map left as-is and still call `EntityWindow_TeleportShift`. Today `.at_start` is only reachable when `sec_x == 0` (already at the left edge of the grid — slot map parity guarantee holds). If that invariant ever breaks, the invariance assert would fire: a second SyncSlide call after an unchanged slot map with an already-shifted camera would re-derive the correct anchor, but the assert would see a mismatch. Add an Up-style guard (`cmpi.b #0, (Slot_Section_Map).w / blo.s .at_start_nop` pattern) when this path is next touched.
**When to revisit:** add the defense when `Section_TeleportBwd` is modified for any reason.

### [DEAD CLUSTER] ~~Section_Check clobber header understates~~
> **VOID — see the DEAD CLUSTER banner under §4.** `Section_Check` does not exist, nor do the
> `Section_TeleportFwd` / `SyncSlide` / `TeleportShift` handlers whose clobbers it understated.
> **Worth noting the concern was structural, not incidental**, and the engine has since gone much
> further in that direction: clobber/preserve sets are now *declared* on every proc
> (`clobbers(...)` / `preserves(...)`) and machine-checked, with declared contexts added as
> recently as HEAD `fa0ae0b`. The class of bug this entry describes is now caught by the language.
**Surfaced during:** grid-edge branch review 2026-06-11 (pre-existing).
**What:** The `Section_Check` routine header documents a narrow clobber set, but its tail-branches (`bra.w Section_TeleportFwd` etc.) enter handler routines that clobber d0–d7/a0–a4 (`SyncSlide` + `TeleportShift` rebuild paths). Any caller that saves only the documented set around `Section_Check` will see unexpected register corruption. Fix the header when opportunistically passing through.
**When to revisit:** opportunistically when touching `Section_Check` or any teleport handler.

### Row-2 seam fixtures — DOWN-direction preview only structurally tested
**Surfaced during:** visibility-window verification 2026-06-12.
**What:** Vertical slide and DOWN teleport paths are structurally exercised (window derives rows correctly, vertical streaming works), but sections 6–8 (row 2 of the OJZ 3×3 grid) have no ring or object content, so the row-2 seam has no visible entities to confirm preview behavior end to end. The structural path is proven; the content test is deferred.
**When to revisit:** when row-2 section content is authored for production OJZ or any zone with ≥3 row sections.

## From Compression Two-Tier (2026-06-11)

### S4LZ DP literal-extension undercharge
**Surfaced during:** compression-two-tier review 2026-06-11.
**What:** The DP cost model doesn't charge the 2-byte lit-count extension word for literal runs ≥ 15 words. Fixing this requires run-length-aware DP state (~16× build time) for a measured ceiling well under 0.5% of the block corpus. Not worth it; recorded so it isn't re-litigated.
**Status:** Won't fix — cost model undercharge is negligible in practice.

### S4LZ decompressor micro-optimizations (audit F4 speed wins)
**Surfaced during:** compression audit 2026-06-11 (cycle analysis in docs/research/compression-audit-2026-06-11.md).
**What:** The decoder runs ~510-640 KB/s realistic mix. Three ranked wins were measured but NOT implemented because current budgets fit (6 blocks/frame ≈ half a frame; vertical scroll protocol +4/512px unchanged with dictionaries on): (1) `move.l` in the unrolled copy tables (guard match path for offset ≥ 4) — pure literals 10.2 → 9.2 c/byte; (2) unroll the extended-count `dbf` loops (currently the SLOWEST path per byte despite being the bulk-copy case) — 22 → ~12.5 c/word; (3) 256-entry token jump table (~1.5 KB ROM) — mixed ~13.7 → ~10 c/byte ≈ 770 KB/s.
**When ready:** when block budgets grow (BLOCK_DECOMP_BUDGET > 6, bigger blocks, or new per-frame consumers) or profiling shows decode pressure.

### ZX0 needs budgeted decode before any mid-gameplay use
**Surfaced during:** compression-two-tier T6 measurement 2026-06-11.
**What:** ZX0 measured ~76 KB/s (5 frames synchronous for a 6.3 KB section blob). Today it runs only at level init (invisible). The §4.2 deferred cold-load design (mid-traversal FWD/BWD section art loads — currently stubbed) would freeze ~5-7 frames if it called `Art_Decompress` on a ZX0 blob synchronously. Before implementing deferred loads: either route them through the §9.7 pages+bookmark idle-time path (now SHIPPED — the resumable `ZX0R_Decompress` sliced across idle, never a synchronous blocking decode), or keep gameplay-streamed art on the S4LZ tier (wrapper version byte already dispatches per blob — the pipeline can mix tiers freely).
**When ready:** with §4.2 deferred cold-load implementation.

### Level editor exporter template is stale (dict fields, .zx0, blob aliases)
**Surfaced during:** compression-two-tier T2/T3 2026-06-11. Editor repo (sonic-level-editor, user-triaged commits only).
**What:** The editor's act-descriptor exporter (`src/core/export/act-descriptor.ts`) still emits the pre-compression-branch shape: `sec_reserved_2C`/pad instead of `sec_block_dict` ($2C) + `sec_block_dict_len` ($46); `OJZ_SecN_Tiles_S4LZ` labels + `.s4lz` BINCLUDEs instead of `OJZ_SecN_Tiles` + `.zx0`; 18 per-section BINCLUDE lines instead of the two generated blob-alias includes (`sec_tile_blobs.asm`/`sec_block_blobs.asm`). Nothing breaks today (the export dir isn't in the ROM build), but the NEXT editor export would hand the engine a NULL dict pointer for dict-compressed blocks. Also: `tools/ojz_strip_gen.py editor_data_available()` hardcodes `ojz/act1/section_0.tiles.bin` instead of deriving from project.json `dataPath` (same config-derivation treatment as the 2026-06-11 chunk-library move).
**When ready:** before the next editor level export; engine-side spec is all on master (structs.asm Sec fields, act_descriptor.asm as reference).
**Update 2026-06-11 (entity exporter):** entities now follow the build-step model —
`tools/ojz_entity_gen.py` generates entity_data.asm from the editor JSONs (X-sort,
validation, per-section minimized type tables, ring-buffer pressure analysis).
Direction decision: editor authors JSON, BUILD generates engine format — the
act-descriptor exporter above should eventually shrink into the same model rather
than be fixed in place. Editor-repo follow-up: placement UI checkboxes for the new
`anyY`/`xflip`/`yflip` object fields (generator already accepts them). Generator
polish backlog (review minors): friendly errors for malformed JSON/float coords,
warn on whole-act-empty dataPath misconfig, duplicate library-id check.

### Streaming polish backlog (consolidated pointers)
**Surfaced during:** vertical-streaming 2026-06-10 (full analysis in that plan's RESULTS + follow-ups).
**What:** (1) Prefetch column cursor — residual +4 vertical / +6 horizontal lag per 512px is block-row/col crossing decompresses; prefetch re-probes only the view-center column, walking the ~6 visible block columns between crossings should reach ~+1. (2) Per-VBlank plane-buffer drain budget — the deeper fix if row payloads ever grow past 2 rows/frame again. (3) DEBUG_FLY_SPEED_FAST is pinned to base speed by the 16px/f camera clamp (turbo is a no-op).
**When ready:** any perf-focused session; all measured groundwork is in docs/superpowers/plans/2026-06-10-vertical-streaming-budget.md.

### Real ring/object art at safe VRAM slots
**Surfaced during:** objects-v2 play-testing 2026-06-10.
**What:** Test objects render placeholder squares; VRAM_TEST_SONIC-era test art sat inside the FG pool (caused the debug-exit tile corruption, since fixed by relocation). Production ring/monitor/object art needs proper slots in the unified pool via the build-time allocator, replacing the placeholders so play-testing reads like a game.
**When ready:** prerequisite satisfied — §4.9 phase 2 (vertical entity window) shipped 2026-06-11; entities now spawn everywhere on both axes. Ready to pick up in any art-focused session.

---

## From Sound Driver Work (Future)

> **STATE-OF-TRUTH (2026-07-03 — supersedes the 2026-07-01 banner):** EVERY open sound entry
> below is now OWNED by a banked package of the 2026-07-03 design-banking session
> (`docs/superpowers/2026-07-03-sound-banking-queue.md`, six packages 0-6, all specs+plans on
> master). Do NOT execute any sound entry from this file directly — execute its owning package
> plan, which embeds the entry's current verified state (several entries below are stale;
> the plans record what was ALREADY fixed). Ownership map:
> - SFX Stage B/C + continuous SFX → **package 2** (`plans/2026-07-03-sfx-fidelity-stage-bc.md`)
> - deep-audit survivors D1/D4/D6/D7/B3/B5/E5-runtime → **package 4** (`plans/2026-07-03-sound-correctness-batch.md`)
> - DAC descriptor insurance + Bank-D hook + drum authoring → **package 3** (`plans/2026-07-03-dac-drum-library-readiness.md`)
> - game-feel gaps (pause/jingle/song-finished/API v2) → **package 1** (`plans/2026-07-03-sound-game-feel-moments.md`) — **EXECUTED 2026-08-09** (`sound-pkg1`; see the closing entry at the end of this file)
> - detune-unison + production features → **package 5** (`plans/2026-07-03-sound-production-suite.md`)
> - GATE articulation, opbias test, $28 guard, cold-boot pan seed, FM env seam, HCZ2 loop
>   residual, bank-latch hunt, boundary-tick check, comment rot, + ALL formal closures
>   (§6.4, Phase-4, defensive-upload, H3, worst-tick) → **package 6** (`plans/2026-07-03-sound-closeout-sweep.md`)
> After packages 5+6 execute, this file's sound sections should contain ONLY closed/annotated
> entries; anything still open then is a process bug. (The 2026-07-01 review pair remains the
> analytical record behind the packages.)
>
> **EXECUTION STATUS as of 2026-08-05 (reconciliation pass):**
> - **Package 2** (SFX Stage B/C) — **EXECUTED + merged 2026-07-07**, annotated on its own entry.
> - **CORRECTED 2026-08-10:** packages **1 (2026-08-09), 3 and 4 (both 2026-08-10)** have
>   all EXECUTED and merged. Only **5 and 6** remain of the banked set. The package-4
>   paragraph below is historical — every item it lists as open has shipped. Note also
>   that packages 5+6 no longer close the sound backlog: the 2026-08-08 triage adopted
>   nine riders (R2, R3, R5-R11) and two ruled-in streams that postdate this banner and
>   have no plans. See `docs/superpowers/2026-08-10-open-work-inventory.md`.
> - **Package 4 has open work that does not need the others.** Verified against the tree:
>   **D2 is DONE** (corrected on its own line below — do not re-plan it), while **D1, D4, D5, D6,
>   D7 and E5's 7th RegDelta group are genuinely open** and are independent of packages 1/3/5/6.
>   If sound work is picked up piecemeal, that cluster is the cleanest entry point.
> - Three sound items **cannot be closed statically at all** and are listed in the
>   CANNOT-BE-SETTLED-STATICALLY section at the top of this file: the A2 two-SFX-in-one-frame
>   runtime check, the FM env attack seam by-ear pass, and the bank-latch desync hunt (plus the
>   DAC worst-tick profiling round).

### Music-expression Task 0 (Z80 code recovery) — follow-ups — 2026-06-24
Task 0 recovered Z80 code headroom (2 → ~1016 B) by **co-locating** the engine lookup tables
at the start of Moving Trucks' streamed ROM bank (window `$8000`), read with the song bank
already in the window — no swap. SFX is covered (its blobs share MT's bank). Verified: MT
renders == pre-banking baseline. Merged on `feat/sound-task0-recovery`. Two follow-ups:
- **Bank-D (DAC) co-location hook — for the first real COPY / FM6=DAC-drum song.** COPY songs
  run with the **DAC sample bank** in the window during their frame, which lacks the tables.
  When a real drum song is authored, emit a **label-free data-only copy** of the engine tables
  at the DAC sample bank start (`main.asm`, after `dac_samples.asm`'s `align $8000`) — needs a
  small generator tweak (`gen_sound_tables.py` + `zyrinx_player.py` to emit a data-only twin,
  since the labels are defined once in MT's bank). The Phase-3 scratch COPY test songs (id 1–5)
  were dropped, so nothing needs this today. The banking model (tables at bank-start in whatever
  bank the window holds) is the general rule; this is just the COPY instance.
  *(Generator twin LANDED `874b260` (package 3, 2026-08-10) — `gen_sound_tables.py::
  emit_emp_z80_data_only()`, byte-equality tested (`TestEmpDataOnlyTwin`); written against the
  CURRENT build-consumed `emit_emp_z80()` emitter, activation path re-anchored to seam-2/embed
  mechanics (the `main.asm` phase-include named above is deleted — see the twin's docstring +
  the DAC spec's authoring runbook step 6). ROM activation still rides the first COPY song.)*
- ~~**Dead 68k table copies.**~~ **✅ DONE — deleted by `a3f2332`** (2026-07-01, "chore: tier-2
  mess cleanup — orphans deleted, references protected, handoff neutralized). Verified 2026-08-05:
  `data/sound/fm_patches.asm` and `data/sound/sound_tables.asm` are gone from
  `games/sonic4/data/sound/`, and **`FmPatchTable` has zero hits tree-wide**. (Original text:
  with the scratch COPY songs gone, `data/sound/fm_patches.asm`
  (`FmPatchTable`) and `data/sound/sound_tables.asm` (the 68k duplicate of the Z80 tables) are
  now **wholly unreferenced** (the runtime uses the Z80 copies). Candidate for removal — left in
  this pass to keep Task 0 scoped to recovery.) **See also the "Dead-but-drift-guarded 68k ROM
  table/patch copies (Plan 1C)" entry further down — same two files, also closed by this commit.**

> **Driver note:** the engine ships a **from-scratch custom Z80-autonomous sound driver**
> (2026-06-16 master sound spec), NOT an imported Flamedriver. Plans **1A** (foundations),
> **1B** (DMA-survival DAC), **1C** (FM+PSG sequencer), **1D** (Moving Trucks FM infra), and
> **Phase 3a** (FM depth — per-frame modulation engine + native Moving Trucks port) are SHIPPED
> (merged to master `c89bea3`, 2026-06-19). The remaining Phase 2 / 3b / 4 / 5 / 6 backlog
> (N-channel DAC mixer, FM extras, adaptive FM6, section-aware banking/fades + SFX, MegaDAW export)
> is tracked at the bottom of this section. References to "Flamedriver upload" below are historical.

### SFX Fidelity Stage B/C (deferred from Stage A, 2026-07-03)
> **EXECUTED 2026-07-07** (`feat/sfx-fidelity-stage-bc`, plan `plans/2026-07-03-sfx-fidelity-stage-bc.md`).
> Shipped + oracle-verified: `sfh_gain` fold (FM TL + PSG atten), per-SFX `sfh_duck` (deepest-active
> wins; global `SFX_DUCK_THRESHOLD`/`SFX_DUCK_DEPTH` retired), non-latching priority (bit 7), authored
> instance caps (oldest-slot kill), continuous-SFX class (tri-state `sx_extend`). `SfxChannel` 64→68.
> Two plan defects fixed in review: (1) `sx_gain` moved off +58 (aliases `sc_detune`, read on SFX ix);
> (2) **bit-7 non-latching flag collided with the 8-bit priority scale → `SFXPRI_*` rescaled to 7-bit
> ($10/$20/$30/$40/$60), bit 7 reserved as the flag, build-fatal + pytest guard added.** Oracle proof:
> spindash stores `sx_priority=$40` (was $00); 4-FM-SFX contention steals lowest (roll $30), death $60
> + spindash $40 survive; cap=1; no duck at defaults. Blobs no longer byte-identical to Stage A (byte[0]
> priority intentionally rescaled; ordering/behavior preserved). **STILL DEFERRED:** H3 (music-relative
> level) + full rendered S3K A/B (below, by-ear-gated); cap>1 on multi-channel SFX (generation tag);
> jingle cross-rule → package 1 (introduces the jingle class); by-ear taste values (gain/duck all 0).

**Surfaced during:** the SFX fidelity phase (spec `2026-07-02-sfx-fidelity-and-mixing-design.md`,
plan `2026-07-03-sfx-fidelity-stage-a.md`, branch `feat/sfx-fidelity`). Stage A SHIPPED: PSG +24
octave fixup removed (jump/skid S3K-exact), retrigger replace-in-place cap 1 (rev escalation kept),
PSG sweep floor clamp, TL-clamp audit + bake test, `SfxHeader` 8 bytes with inert Stage-B fields,
and THREE field-found fixes from the user's by-ear pass (all live-debugged in oracle):
1. **Stopped-sequencer drone** — `Sfx_Restore` gates on `SND_SEQ_ACTIVE` (an SFX ending over
   stopped music re-keyed the dead song's stale-KEYED note into an unkillable tone).
2. **S3K modSet load-point semantics** — S3K's `cfModulation` only retargets the data pointer;
   params load at the next ATTACKED note (`zPrepareModulation` early-outs on no-attack) and
   speed/steps reload THROUGH the pointer. So roll's fade RISES to the end and spindash's holds
   the sweep-top. Our engine's base-pitch snap in `Seq_Op_ModSet` (built on the wrong immediate-
   cancel reading) is DELETED; the transcoder's `_apply_s3k_modset_load_points` pass drops/freezes
   unloaded modSets. Registered-verified: roll sweeps to `$6D9` (S3K-computed exact) through the
   fade; spindash holds `$4F4` after the climb.
3. **SFX-ring byte-cursor-as-word-index** — `Sound_PlaySFX`/`Sound_DrainSfxRing` loaded ring
   cursors with `move.b` but indexed `(a0,dN.w)`; a dirty caller upper byte (spindash release
   leaves `$09xx` in d1) sent the ring write up to `$FF00` bytes astray — the dash SFX vanished
   AND a stray byte hit unrelated RAM. Fixed with `moveq #0` sanitization. A repo-wide audit of
   the same pattern (70+ `(aN,dM.w)` sites) ran 2026-07-03 — see the audit report for verdicts.
The retrigger POLICY DECISION from the 2026-07-01 review findings is CLOSED (replace-in-place, cap 1).
The A2 runtime-verification item (below) is effectively DISCHARGED by fix 3's live debugging —
the ring delivers correctly once the index bug is fixed; jump+ring same-frame pairing was
exercised throughout the phase's captures.

- **Stage B — per-SFX mixing surface (engine wiring for the reserved header fields):**
  `sfh_gain` (authored master attenuation, FM carrier-TL 0.75 dB steps / PSG atten 2 dB steps,
  applied at init), `sfh_duck` (per-SFX duck depth replacing global `SFX_DUCK_DEPTH`; 0 for
  bread-and-butter SFX, deep only for death/ring-loss class), `sfh_cap` (authored instance caps),
  non-latching priority via bit 7 of `sfh_priority` (S2's trick — plays but never raises the floor).
  Spec §5 has the full design. **Roll taste**: S3K's roll is authentically a ~2.2 kHz C#7 with a
  1.4 s authored fade (`smpsFMAlterVol` ×42, register-verified at parity) — if it reads as "too
  high/long" by ear, tame it via `sfh_gain`/the FM taste knob as a DELIBERATE divergence, not a fix.
- **Instance discriminator for cap > 1 on multi-channel SFX** (quality-review note, Task 2): the
  per-slot id table alone can't tell which slots form the OLDEST instance of a multi-channel SFX
  (Dash = FM5+PSG3). cap=1 and cap-N-single-channel work as-is; cap>1 multi-channel needs a
  generation tag or per-instance grouping.
- **Stage C — continuous-SFX class** (S3K extend semantics; header flag `SHF_CONTINUOUS` + engine
  re-ping/loop-counter). None of the current 9 SFX need it; ~30 S3K sounds (wind/fans/rumbles) are
  unportable without it. Existing ARCH §6.7 entry stands.
- **H3 (music-relative SFX level) — deferred pending by-ear:** SFX play at raw authored TL
  (chip-exact). If SFX still feel hot vs music after Stage A, A/B the full music+SFX mix RMS/spectrum
  against real S3K (HCZ2 bed) and fix the MUSIC converter's volume round-trip — do NOT tune SFX.
- **Rendered S3K A/B per SFX — deferred:** Stage A verified register-exact divisors/F-nums/durations
  against skdisasm sources on the same YM core (+ the S3K-source-exact roll fade), which pins pitch
  and duration. A full vgm2wav energy/spectrum A/B vs `skdisasm/sonic3k.bin` sound-test captures
  remains available if by-ear ever disputes timbre/level.
- **Debug-harness START edge**: MCP-driven 3-frame START presses intermittently miss the
  `Ctrl_1_Press` edge (one observed miss, 2026-07-03) — benign for gameplay, noise for scripted
  emulator tests; suspect press/frame alignment in the harness, not the engine.

### Sound Engine Deep Audit (2026-06-21) — Full Bug Backlog + Best-in-Class Roadmap
**Surfaced during:** a 73-agent adversarially-verified correctness audit + a fact-checked frontier
gap analysis (Zyrinx, XGM/XGM2, Echo, MDSDRV, GEMS, Flamedriver, demoscene/MegaPCM). Branch
`feat/sound-phase5a-sfx`. Memory: [[project_sound_audit_2026_06_21]], [[project_sfx_pitch_open]].
**Verdict:** structurally sound — **0 crashes, 0 register/bus-corruption, 0 IRQ bugs**. 40 confirmed
issues, clustered in SFX + DAC + the build pipeline. We are already best-in-class on DMA-survival
DAC cadence, the SFX steal/priority/ducking engine, and the static key-on FM-expression layer.
**Status of Item 1 (IN PROGRESS, branch off this one):** bug B1 (transcoder operator swap) + bug
A1 (SFX steal silence-gap). Everything else below is the durable backlog so nothing is lost.

#### A. Bugs reachable in normal gameplay (fix soon)
- **A1 — SFX steal silences the music voice it stole** (`engine/sound_sfx.asm` ~447/895/920/947).
  Steal's key-off clears `SCF_KEYED` on the music channel; `Sfx_Restore` tests that *same* now-cleared
  bit to decide whether to re-key the held note, so it never re-keys → music voice dropout on every
  steal of a sounding FM/PSG note. **Fix:** stash the music channel's KEYED state at steal, branch
  Restore on the saved bit. (Violates the spec's "no silence gap" criterion.) **→ Item 1.**
- **A2 — two SFX in one 68k frame → only the last survives** (`engine/sound_api.asm` 130; single-byte
  `SND_REQ_SFX`, latest-wins; consumed once/VBlank at `z80_sound_driver.asm` 522). Jump+ring, skid+ring,
  death+ring-loss all drop one SFX, *priority-blind*. The Z80 3-deep queue sits downstream and can't help.
  **Fix:** Flamedriver two-slot post (`zSFXNumber0/1`) or a small 68k-side pending ring. Audio-only (high/med).
  **IMPLEMENTED (af09e83, 8-deep 68k-side ring):** `Sound_PlaySFX` enqueues; `Sound_DrainSfxRing`
  (GameLoop, post-VSync) posts ONE id/frame into the mailbox once the Z80 has cleared it. Lint clean,
  full ROM assembles. The code has long since shipped to master (the OJZ tile-budget build blocker that
  gated boot testing was resolved 2026-06-22). **The dedicated runtime verification item still stands
  (2026-07-01):** exercise jump+ring / skid+ring / death+ring-loss in one frame and confirm both SFX
  reach the chip. Logic hand-traced (enqueue/drain/dedup edge cases) in the interim.

#### B. Build-pipeline / fidelity bugs (the "SFX sounds wrong" root cause)
- **B1 — transcoder swaps physical operators S2↔S3** (`tools/sfx_transcode.py` ~388). Emits S3K op
  order straight through, but our engine maps byte-index k→reg base+k*4 = physical `[S1,S3,S2,S4]`;
  S3K uploads `[S1,S2,S3,S4]`. Every transcoded FM SFX plays with OP2/OP3 transposed → wrong timbre
  (spindash alg-4 swaps the *modulators* = large). **Likely root of [[project_sfx_pitch_open]].**
  **Fix:** emit `[src[3],src[1],src[2],src[0]]` (OP_REORDER=[0,2,1,3]) for the S3K-SFX path only. **→ Item 1.**
- **B2 — by-ear FM octave / spindash-sweep "taste knobs" baked into committed SFX data** (`sfx_transcode.py`
  151-176; `_FM_SFX_OCTAVE`, `_SPINDASH_MOD_SCALE`). Unconverged WIP; likely *compensating* for B1.
  **After B1 lands + regen, re-evaluate — they may collapse toward 0/S3K-faithful.** (Paused 2026-06-21.)
- ~~**B3 — AM-enable bit dropped vs S3K byte** (`sfx_transcode.py` 330-336/390; `_am<<5 & 0x80` always 0).
  Harmless on YM2612 (bit 5 of $60 is a don't-care) but a byte-fidelity divergence + a trap if a real
  AM voice is ever transcoded. Doc or preserve the junk bits.~~
  **DONE 2026-08-10 (package 4, `sound-pkg4`) — but NOT as "preserve the junk bits".** The entry's own
  observation is the reason: bits 6-5 of `$60` are DON'T-CARES, so reproducing the `SourceSMPS2ASM==0` byte
  buys nothing while losing the flag the voice author meant. `smpsVcAmpMod`'s operand is now treated as a
  per-operator AM-ENABLE FLAG and lands on YM2612 **bit 7** — the placement `_smps2asm_inc.asm`'s own comment
  records as correct ("According to several docs, however, it's actually the high bit"). Implemented as a
  NONZERO TEST rather than a shift, so it is right under either SMPS2ASM encoding and under the 2-bit values
  the erroneous assumption could produce. **Zero shipped-content movement:** all nine core SFX `.bin` payloads
  regenerate byte-identical (of all S3K SFX only `9B - Thump Boss` authors AM, and it is not in
  `_CORE_SFX_IDS`), and all four ROM CRCs were unchanged across the commit.
- **B4 — looped-SFX fade tail (`smpsFMAlterVol`) + bare-duration replay — FIXED 2026-06-21** (see
  `docs/BUGS.md` BUG-002 items 1 & 3). The transcoder collapsed S&K's per-pass `smpsFMAlterVol` fade to one
  constant `MEV_VOL` (roll tail held flat then hard-cut) and dropped the SMPS bare-duration "replay previous
  note" idiom (spindash rev-tail collapsed to zero ticks). Fixed transcoder-side (no Z80 growth — driver has
  4 bytes free): AlterVol-bearing `smpsLoop`s are now UNROLLED with a dB-faithful per-pass fade (invert
  `LogVolumeLutZ`), and a standalone duration byte re-articulates the previous note. Packer backstop added.
  **`smpsNoAttack` (the per-pass FM re-key) — DONE 2026-06-21** (was the deferred half). VGM capture proved
  the unrolled tails re-keyed the FM envelope 43×(roll)/26×(spindash) at 30 Hz — the "jingle/higher-pitch"
  the user heard. Fixed in EXACTLY the 4 free Z80 bytes: bit 7 of a NoteDur's pitch operand is a no-attack
  flag; `Seq_Op_NoteDur` does `ld d,a / bit 7,d / ret nz` to skip the note-on hook (no `$28` re-attack AND no
  freq re-write) for a held continuation. The transcoder sets bit 7 on tail passes via `mod_dirty`: the FIRST
  note after a modSet still re-keys (resets the swept pitch to base), the rest hold. Verified on hardware:
  KEY-ON 43→2 / 26→2, tail holds at base fnum, TL fade intact. **Transition re-key (the last residual) —
  FIXED 2026-06-22** (see `docs/BUGS.md` Items 1+3 follow-up #3): `Seq_Op_ModSet` now re-writes `sc_base_freq`
  via `Fm_WriteFreq` (held-note pitch change, no `$28`) for SFX FM channels, so the modSet-off snaps the tail
  to base with no re-key; the transcoder holds ALL tail passes. +18 Z80 bytes reclaimed by folding 6 more
  channel-class tests into `Snd_ChanClass` (`Z80_SOUND_SIZE` `$16EE`, 2 free). Verified: roll/spindash
  KEY-ON 2→1, fades intact, skid/ring/jump/dash no regression. The looped FM SFX tails are now S&K-faithful
  (one key-on, smooth fade to silence). `Snd_ChanClass` has converted 11 of 12 inline channel-class sites;
  the 1 remaining + future reclaim is there if needed. (Historical: that fix left $16EE / 2 free; Task 0
  banking then recovered to $1618 / 216 free, and later phases spent it back to 10 free (2026-07-01);
  the 2026-07-02 budget phase recovered ~790 B and ended at **$175A / $18F0 → $196 (406) free,
  DEBUG=1** after spending on fidelity + portamento — see F1/F5.)
- **B5 — `smpsPSGform $E7` tone-FREQUENCY-TRACKED noise sweep** (refinement; the fixed-rate fix is done — see
  `docs/BUGS.md` BUG-003). The dash `$B6` (and any `smpsPSGform $E7` SFX) is now correctly rerouted to the
  NOISE channel, but plays a FIXED white-noise rate (`$E6`, clk/2048). S&K's `$E7` is white noise whose shift
  rate TRACKS PSG3's tone frequency — so as the channel's tone sweeps (its `smpsModSet`), the noise pitch
  descends (a "pshhew"). Reproducing it needs the engine to drive PSG3's frequency register as the noise clock
  + apply the modulation to it, with the audio on the noise channel — either (a) a `Psg_Noise` `$E7` path that
  writes PSG3's freq from the note+mod, or (b) the transcoder splitting the source channel into a silenced
  tone-clock (PSG3) + a noise channel (the engine + hardware then sync via the `$E7` track bit). Option (b) is
  engine-change-free but adds a 3rd SFX channel + needs the clock pinned to PSG3 (no voice substitution). The
  fixed-rate noise is the right character; the descending sweep is the nuance. Re-evaluate by ear.
  *(Status check 2026-07-01: STILL OPEN for SFX — `tools/sfx_transcode.py` still emits the fixed `$E6`
  approximation. Note the MUSIC path has since shipped tone-tracked noise — `MEV_PSGNOISE` clocks rate-3
  noise from tone-2, S3K-faithful, HCZ2 hi-hats — so the engine mechanism for option (a) now part-exists.)*

  > **STILL OPEN after package 4 (2026-08-10) — the plan's own Step-2B fallback was taken, deliberately.**
  > Package 4's Task 6 required answering, first, whether the shipped music mechanism REACHES SFX. It does
  > not: `Psg_Noise` branches on `Snd_ChanClass` and the rate-3 tone-2 clock (`Psg_EmitNoiseClock`) lives
  > ONLY on the MUSIC arm; the SFX arm is the legacy `$E0 | (note & 7)` path with no `$C0` write. The plan
  > sanctioned the fallback if un-gating cost more than ~12 B. Costed, it is far more than that — THREE
  > coupled changes, not one:
  >
  > 1. **The SFX channel cannot carry a noise-mode byte.** S3K's `$E7` semantics need the note to be a
  >    PITCH plus a cached mode/rate, but `sc_noise_mode` (+57) ALIASES `SfxChannel.sx_priority`, and
  >    `_validate_no_aliasing_ops` rejects `MEV_PSGNOISE` on SFX for exactly that reason. The shared prefix
  >    may not grow (standing sound-banking invariant), so the carrier would have to be a new `sx_kind`
  >    value (+63, SFX-private) plus a tone-clock branch in `Psg_Noise`'s SFX arm — ~18 B before sharing,
  >    ~11 B net if the `SCF_KEYED`/`Psg_EnvCursorReset` prologue is hoisted out of both arms first.
  > 2. **The sweep itself is broken on the noise route.** The dash's descent is a `smpsModSet`, and
  >    `Psg_ApplyMod` re-latches through `Psg_EmitDivisor` -> `Psg_ChBase`, which for `CHROUTE_PSGN`
  >    computes latch `$80|$60` = `$E0` — the NOISE CONTROL register. That is precisely the **D1**
  >    corruption this same package just closed producer-side. A tone-clocked noise SFX therefore ALSO
  >    needs a noise-route special case in `Psg_ApplyMod` that writes tone-3's frequency latch (`$C0`),
  >    plus a carve-out in the brand-new D1 rule so the sweep is legal on exactly that channel shape.
  > 3. Only then does the transcoder change (drop the `$E6` approximation, emit pitch notes + the `$E7`
  >    kind) become meaningful.
  >
  > Estimated ≳ 40 B resident plus a re-plumb of the D1 rule — well past the ceiling, and it re-opens a
  > corruption path the same session closed. **Recommendation: give B5 its own scoped parcel** (it is a
  > `Psg_Noise` + `Psg_ApplyMod` route-shape change, not a transcoder tweak), and sequence it AFTER any
  > log-domain pitch work (triage R3), which changes how modulation reaches the divisor anyway. The
  > fixed-rate `$E6` character remains correct; only the descending nuance is missing.

#### C. DAC sample path — ✅ largely RESOLVED by the DAC-format revision (2026-06-25)
*(The "ONE format revision" this block asked for SHIPPED as the DAC drum phase — see
`docs/superpowers/specs/2026-06-24-dac-drum-format-revision-design.md` + its raw-8-bit amendment.
The multi-sample descriptor table, per-sample banking, and the one-shot state machine replaced the
1C blip path wholesale.)*
- ~~**C1 — one-shot samples never stop**~~ **RESOLVED (DAC drum phase, 2026-06-25):** the shipped
  one-shot state machine (IDLE → PLAYING → DRAINING_TAIL → STOPPING) plays a sample once and cleanly
  stops to DC center — nothing re-loops. (Historical text: `DAC_ACTIVE` only ever set, never cleared
  on exhaustion; FILL-exhaust unconditionally re-looped the blip.)
- ~~**C2 — `Snd_StartSample` ignores `ds_loop_ofs` + `ds_rate`**~~ **SUPERSEDED (DAC drum phase):** in the
  shipped 9-byte descriptor both fields are *deliberately* RESERVED forward-compat (`sound_constants.asm`,
  `DacSample`) — one-shots don't loop and v1 has one rate; multi-sample DAC is live via the descriptor table.
- ~~**C3 — odd `ds_length` runs away ~64KB**~~ **RESOLVED by construction:** the shipped register-resident
  1:1 loop consumes ONE byte per pass (no `-=2` FILL), so odd lengths terminate exactly
  (`tools/dac_encode.py` header notes there is no even-length requirement).
- **C4 — no consumer underrun guard** (old lines 353-363) — **mostly superseded:** the shipped
  DRAINING_TAIL path stops exactly at `lead==0` and DC-centers (no stale-ring replay at exhaust). The
  residual corner is a 68k DMA outlasting the ~200-sample ring lead mid-sample — re-evaluate against the
  shipped loop if a marathon DMA burst is ever added.

#### D. Latent correctness (trust-the-packer / new-content surfaces)
- ~~**D1** PSG pitch-mod has no noise-route gate (`sound_sequencer.asm` 162; `sound_psg.asm` 239) — a noise
  channel carrying `sc_mod_ctrl!=0` corrupts the noise control register. Gate on tone route + reject in transcoder.~~
  **DONE 2026-08-10 (package 4, `sound-pkg4`) — PRODUCER-SIDE, zero Z80 bytes.** The runtime gate stays
  reverted (the note at the `Psg_ApplyMod` call site in `sound_sequencer.emp` now points here instead of
  claiming a convention). Both producers enforce it: `song_packer.py` `ModSet.validate` refuses
  `CHROUTE_PSGN` outright, and `sfx_transcode.py` `_validate_no_modset_on_noise` backstops every SFX
  channel from `pack_sfx`. Rule is absolute, including the all-zero `smpsModSet 0,0,0,0` "mod off" idiom.
  Spec: music-expr format-validity §(d)4. **Deliberately a BACKSTOP, not a re-shape, on the SFX side:** the
  parser already DROPS `smpsModSet` when it reroutes a channel to noise and a shipped test pins that drop, so
  erroring at the emission point would reject real S3K sources we do not control.
- ~~**D2** note before any set-duration reloads from a zeroed `sc_dur_default` → 255-tick stuck note
  (`sound_sequencer.asm` 536; init `sc_dur_default` to 1).~~ **✅ DONE — verified 2026-08-05.**
  The seed-to-1 the entry prescribes is in place at **both** init sites:
  `engine/sound/z80_sound_driver.emp:1276` (`ld (ix+sc_dur_default), 1`, with the rationale
  spelled out in the comment at `:1273` — "seeds to 1 (not 0): a channel that issues a note BEFORE
  any set-duration…") and `engine/sound/sound_sfx.emp:1034`. **Package 4 must not re-plan this
  item;** D1/D4/D5/D6/D7 in the same block are still open.
- ~~**D3** `sc_mod_wait` never restored on note re-arm — 2nd+ modulated note gets zero delay vs S3K
  `zPrepareModulation` (`sound_sequencer.asm` 381; add `sc_mod_wait_raw`).~~ **DONE 2026-07-02
  (budget phase T6):** `sc_mod_wait_raw` + `sc_mod_delta_raw` latched at MODSET, reloaded every
  note-on — capture-verified at ref parity (`docs/research/phase_harness/t6_verification.md`).
- ~~**D4** `Psg_NoteOn` ignores `sc_transpose` (S3K applies it to PSG too) (`sound_psg.asm` 154).~~
  **DONE 2026-08-10 (package 4, `sound-pkg4`, commit `27b3b6a8`) — BYTE-NEUTRAL.** `Psg_NoteOn` now calls
  the new `Fm_TransposeClampChrom` (seeds `FMPITCH_MAX_IDX`, falls into `Fm_TransposeClamp`), which also
  replaced `Fm_NoteOn`'s own 2 B seed — so the 3 B `call` exactly funds itself against the `ld l,a / ld h,0`
  widen it replaces. `FMPITCH_MAX_IDX` legitimately bounds BOTH tables: `FmPitchTableZ` and
  `PsgDivisorTableZ` are one 95-entry note list and `sound_tables_z80.emp` already asserts both emitted
  extents at 190 B. **The bound had to live on the FM side**: seam-1 resolves each resident module's
  constants from a per-module name list baked into the sigil harness (`seam1.rs` `psg_const_names`), and no
  pitch-domain constant is on `sound_psg.emp`'s list. The SFX PSG-tone RESTORE path now folds the MUSIC
  channel's transpose on re-key, matching what the FM restore already did. **Oracle gate owed** (controller):
  spindash-rev PSG pitch-tracking.
- ~~**D5** PSG envelope attack uses a stale `sc_psgenv_out` / lands one frame late vs S3K (`sound_psg.asm`
  106/184; zero `sc_psgenv_out` at cursor-reset).~~ **✅ ALREADY DONE — re-verified 2026-08-10 (package 4).**
  `Psg_EnvCursorReset` (`engine/sound/sound_psg.emp`) zeroes BOTH `sc_psgenv_cur` and `sc_psgenv_out`, with
  the rationale in the comment ("drop the previous note's env tail so the attack's volume emit … starts
  clean, not one frame of the old note's stale attenuation delta"). **Package 4 planned no work here.**
- ~~**D6 (uncertain)** single-level repeat state may carry a stale `sc_repeat_count` across a song loop /
  mid-flight jump (`sound_sequencer.asm` 1042). Watch; add a packer guard if it bites.~~
  **DONE 2026-08-10 (package 4, `sound-pkg4`) — CONFIRMED REAL, then closed from both ends.** The mechanism:
  the song-loop `Jump` target IS the `LoopPoint`, so a `LoopPoint` inside a `RepeatStart..RepeatEnd` span makes
  the loop re-enter the body mid-span; `Seq_Op_RepeatStart` never runs again, and `Seq_Op_RepeatEnd` seeds from
  the operand ONLY when it reads 0, so a stale nonzero count is CONSUMED. Packer: a `LoopPoint` while a span is
  open is a `PackError` (the COMPLETE rule — the `Jump` can target nothing else). Engine: `Seq_Op_RepeatStart`
  re-seeds `sc_repeat_count` to 0 (**4 B**, not the plan's 2 — `ld (ix+d),n` is 4 B on Z80), byte-inert on
  valid content. Spec: music-expr §(c)4.
- ~~**D7** `MEV_REPEAT_END` operand 0 → 255-pass repeat, no runtime clamp (`sound_sequencer.asm` 1022; trust-packer).~~
  **DONE 2026-08-10 (package 4, `sound-pkg4`) — 0 RELEASE BYTES (plain blob + plain ROM CRC unchanged across
  the commit).** `Seq_Op_RepeatEnd` tests `a` at `.have_count` — where it is either an in-progress count
  (nonzero by the preceding test) or the FRESH operand — so `a == 0` there is exactly "the stream authored 0",
  trapped to `Seq_BadOpcode` under `DEBUG == 1` before the wrapping `dec`. **Found while pinning the producer
  side: the rule did not cover SFX at all.** `pack_sfx` encodes events directly and never calls
  `Event.validate`, so `song_packer`'s 1..255 range never reached an SFX stream; the count check now lives in
  `_validate_sfx_repeat`, which `pack_sfx` does call. Spec: music-expr §(c)5.
- ~~**D8** `song_packer.py` accepts expression opcodes the engine silently DROPS on a music route — add a build-time music-legal opcode gate~~ **DONE 2026-06-27 (music-expr merge)** — the packer now enforces a music-legal opcode gate (commits `60524f9` + `da9bb93`, "D8 review"): it errors at build time on any opcode the music route would silently drop, relaxed per-opcode as each un-gates. `MEV_MODSET` vibrato is now music-legal (Phase-1 un-gate); `MEV_PSGENV` since feat/hcz2-import. **STILL OPEN (separate, not the gate):** route PSG note-on through the multipoint `sc_points` arp path (today under `.is_fm` only) for single-channel PSG chords — pairs with D4 (PSG `sc_transpose`).

#### E. Best-in-class — the honest gaps (cross-driver consensus)
**DO NOW (high payoff, seam already exists, ~no pigeonhole):**
- **E-now-1 — continuous/fine pitch + portamento ON MUSIC channels.** Every frontier driver converged
  on this (Zyrinx fine ladder + restoring-division glide `batman_driver_analysis.md`:186-219; MDSDRV 256
  steps/semitone; XGM2 freq-delta; Flamedriver pitch-slide w/ octave-rollover). Our `FmPitchTableZ` is
  strictly chromatic and our continuous-vibrato core (`Mod_Advance`/`sc_base_freq`/`sc_porta_*`) renders
  **SFX channels only** — music gets none. Promote that machinery into the music `SeqChannel` path + add a
  fine-pitch representation. Fields `sc_porta_accum/incr` reserved (`sound_constants.asm` 793). *(This is
  the same as the long-deferred Phase 3a Task 7 portamento + Zyrinx "take-next".)* *(**2026-07-01:** the
  fine-pitch half SHIPPED — `MEV_DETUNE` + music vibrato/`MEV_MODSET` are live on music channels.)*
  *(**DONE 2026-07-02 (budget phase T10):** the PORTAMENTO half SHIPPED — `MEV_PORTA` ($F5) +
  `Porta_Apply` fully RESIDENT, packer event + tests, soak/glide capture-verified
  (`docs/research/phase_harness/t10_verification.md`). This entry is closed.)*
- ~~**E-now-2 — per-frame FM TL volume envelope on music channels**~~ **DONE 2026-06-27 (music-expr merge)** —
  shipped as `MEV_FMENV` ($F7) + `FmEnvUpdate` (per-frame FM-TL carrier volume envelope), reusing the existing
  `Fm_PatchTlGroup` TL-write plumbing; no format change. Supersedes the static `OPBIAS`-only state. (Flamedriver `zDoFMVolEnv`.)
- ~~**E-now-3 — master fade-in/out + global tempo-speedup.**~~ **DONE (music-expr Phase 2):** shipped as
  `Sound_FadeOut`/`Sound_FadeIn` (`SND_REQ_FADE` master TL ramp) + the `MEV_TEMPO` ($F3) global tempo
  scalar with a per-channel accumulator (the 2026-07-01 fix pass repaired the speed-up borrow math).
  `zFadeToPrev`-style fade-to-previous/saved-song-state remains unspec'd — part of the game-feel gap
  (see the 2026-07-01 spec review §3).
- ~~**E-now-4 — sequencer-driven hardware LFO ($22 rate opcode).**~~ **DONE (music-expr Phase 2):**
  shipped as `MEV_LFO` ($F4). ~~**Also fix latent doc
  bug:** comment at `z80_sound_driver.asm` says 3.98 Hz but `$08` = 3.82 Hz.~~ **Doc bug FIXED 2026-06-27**
  (comments at lines 158 & 167 now read 3.82 Hz).

**DESIGN-FOR-IT-NOW, build later (the ONE true pigeonhole + its companions):**
- **E2 — multi-voice PCM mixing on FM6 DAC** — the single architectural decision that forecloses the
  frontier. XGM(4ch)/XGM2(3ch)/MDSDRV(2-3ch)/DualPCM(2ch) sum samples in Z80 RAM; our consumer copies one
  byte, no summing stage, no per-voice volume field (`z80_sound_driver.asm` 353-363; `sound_constants.asm`
  228-234). **Don't build the mixer now — shape the ring consumer + `DacSample` descriptor for N voices now**
  (per-voice volume byte + 16.16 mix cursor so per-sample pitch is free later), ship 1 voice, keep the
  RAM-only equal-cost invariant. This is the "[[feedback_best_of_class_north_star]] design-for-C, build-for-A"
  call — do it **before authoring real DAC content.**
  *(**2026-07-01 update:** the DAC format revision decided AGAINST this — the approved spec
  (`2026-06-24-dac-drum-format-revision-design.md` §2.2) rejects runtime mixing in favor of a single voice
  + pre-mixed composites, and the shipped descriptor has NO per-voice volume/mix-cursor fields. That
  rejection is the one irreversible format bet and was **RATIFIED by the user 2026-07-03** (sound
  design-banking session). The ratification-time ask — the cheap insurance this entry wanted (add
  `ds_vol` + reserved mix-cursor bytes, ~3 B/descriptor, zero code) — is a build item in the banked
  DAC drum-library-readiness package. See the 2026-07-01 spec review §4.)*
  *(Descriptor insurance LANDED `a34c0e1` (package 3, 2026-08-10) — `ds_vol` + `ds_mix_rsvd`
  shipped, 12-byte descriptor, appended so no existing offset moves; v1 engine reads none of the
  new bytes and the resident Z80 blob is byte-count identical (the ×12 stride kept the 8-bit
  Snd_DacLookup form's exact instruction count/length).)*
- **E3 — round out the DAC format in that SAME revision:** loop point (= C2), priority, pan (via $B6),
  auto-bankswitch, `ds_rate` pitch, **+ 4-bit DPCM** (re-adopt our own S3K JMan2050 DPCM, `Flamedriver.asm`
  4321-4442 — halves ROM, producer-side so the 8948 Hz cadence is untouched), and route **sampled SFX** as
  mixer-voice-2 with ducking. (Skip PCM-on-PSG.) Fold the C1-C4 bug fixes in here.
  *(**2026-07-01 update:** the shipped revision landed the C-block fixes, per-sample banking (`ds_bank`),
  and the `$B6` pan door, and RESERVED `ds_codec`/`ds_rate` at zero cost — but chose raw 8-bit over DPCM
  (compression bought ~nothing for once-stored drums and the decode capped the rate; see the spec's
  2026-06-25 amendment) and forecloses sampled-SFX-over-drums with the single-voice bet above.)*
- ~~**E4 — independent per-channel modulation/control stream (dual-stream channels)**~~ **DONE 2026-06-27 (music-expr merge)** —
  the committed seam (`sc_mod_ptr` slot[1], stream-agnostic `ModUpdate`) is now LIVE: slot[1] drives a `MacroTick`
  register-automation stream via `MEV_MACRO` ($F9) — tag grammar `TAG_MAC_*` ($E0–$E3), 2-byte BE loop, `Snd_SongBase`
  rebase. Zyrinx's "feels alive" secret + MDSDRV macro-tracks. *(was Phase 3b "dual per-channel data streams".)*
- **E5 — SSG-EG per-operator looping ($90-$9E)** — cheap buzzy/metallic/AY timbre family. **Load-time half
  DONE 2026-06-27 (music-expr merge):** SSG-EG is now a real per-op patch field — `FmPatch` grew 26→32 bytes
  (`fp_ssg_eg ds.b 4`), loaded at note-on via `SND_REG_OP_SSG_EG` ($90) in `Fm_PatchLoad`; `$00` default = off, so
  existing patches are byte-identical. ~~**STILL OPEN — the runtime 7th-RegDelta-group half:** `MEV_REGDELTA` does
  **not** reach $90 (`RegDeltaGroupBase` is groups 0..5 = $30-$80, `REGDELTA_GROUP_COUNT` = 6, `sound_fm.asm`). Add a
  7th group to sweep SSG-EG per-frame (one reg write/op).~~ **DONE 2026-08-10 (package 4, `sound-pkg4`) —
  E5 FULLY CLOSED, +1 B.** `RegDeltaGroupBase` gained `SND_REG_OP_SSG_EG` as group 6 and
  `REGDELTA_GROUP_COUNT` went to 7; `Fm_RegDelta`'s range check and the RHS-only length ensure both read the
  constant, so no handler changed. Producer: `song_packer`'s mirror -> 7 (build-checked by the existing
  constant-parity test) + `RD_GROUP_SSG_EG = 6`; group 7 still rejected. Spec: music-expr §(d)1.
  **Oracle showcase owed** (controller, optional): a scratch song sweeping group 6 — confirm the
  `$90+op*4+ch` writes land and the timbre audibly buzzes in a rendered capture.

**SKIP / DEFER (and why):**
- **68k-resident sequencer (MDSDRV model)** — explicitly **skip**; our full-Z80 autonomy is the right call
  for a 60fps section-streaming platformer with a busy 68k. Borrow MDSDRV's *techniques* onto the Z80, not
  its CPU placement.
- **CSM mode** — skip; contends with Timer-A (our ~59 Hz sequencer clock).
- **CH3 special mode** (someday; niche, complicates FM3 SFX voice arbitration in `sound_sfx.asm`) and
  **Echo-style adaptive live-inject** (someday; mailbox could grow a direct-event slot — protocol is already
  reentrant/extensible). Build only when a concrete song/boss needs them.

#### F. Hygiene — doc drift, dead code, RAM budget (recovers ~750 B ROM)
- ~~**F1** Z80 RAM-map spec (`docs/superpowers/specs/2026-06-16-sound-z80-ram-map.md`) is STALE~~
  **DONE (budget A.3 repack, 2026-07-02):** the spec was REWRITTEN in full as the live design record —
  new map table (state `$18F0` / ring `$1900` / seq `$1A00` / derived tail / page-aligned derived
  `SND_SFX_BASE` / frozen `$1F00+` mailbox), layout invariants (incl. the `Snd_ChanClass` page-compare
  contract), headroom history, and the complete assert inventory. `sound_constants.asm` stays the
  authoritative values; the spec documents the design + which assert guards which seam.
  ~~**Phase-final headroom (2026-07-02, end of the budget phase): `Z80_SOUND_SIZE` = $175A, ceiling
  `SND_STATE_BASE` = $18F0 → $196 (406) bytes free**~~ — DEBUG=1 figures; plain builds are 126 B
  leaner.
  > **⚠ HEADROOM FIGURE SUPERSEDED TWICE — corrected 2026-08-05.** The `$175A` / 406-free number
  > is from 2026-07-02 and was **spent back down to 86 B DEBUG** by the phases that followed, then
  > **recovered by the wave-4 Z80 reclaim (2026-08-03)** to roughly **317 B DEBUG** (plain
  > 212 B → ~443 B). Source: `docs/superpowers/plans/2026-08-03-wave4-z80-sound-reclaim.md`
  > (header + closing ledger) and this file's own "Sound — deferred follow-ups from the wave-4
  > Z80 reclaim (2026-08-03)" section near the bottom.
  > **Treat the wave-4 section as the current record, not F1/F5.** The *design* content of F1 (the
  > RAM map, layout invariants, assert inventory) is unaffected and still stands; only the
  > headroom arithmetic drifted. Item 25 in the wave-4 section notes a further −71..−94 B is
  > available in the sequencer if more is ever wanted. (A.1 song-buffer delete + A.2 table banking + A.3's +512 ceiling raise recovered ~790 B
  to a peak of 802 free; the phase then spent it on fidelity — rekey −10, mod re-arm +18, porta
  +386, tempo model −8. Full ledger: `docs/research/phase_harness/t12_matrix.md`.) The
  resident-code budget remains the binding sound constraint; data-banking remains the recovery lever
  (code may NOT be banked).
- **F2** `ENGINE_ARCHITECTURE.md §6` still lists SFX deferred + AF_SOUND a stub (update on merge to master).
- **F3** Dead ROM: `dc.l SfxTable` 540 B unused (engine uses its own Z80 `dw` window table); duplicate
  `sfx_NN_patches` banks ~208 B; ~~dead `Snd_TimerA_Program` (`z80_sound_driver.asm` 715)~~. Purge.
  > **⚠ ONE THIRD OF THIS IS WRONG — corrected 2026-08-05.** There is no dead
  > `Snd_TimerA_Program`. The only symbol of that name in the tree is
  > **`Snd_TimerA_ProgramFixed`**, and it is **LIVE — called twice**, at
  > `engine/sound/z80_sound_driver.emp:277` and `:1331` (defined `:1018`, documented `:1013`,
  > cross-referenced from `sound_fm.emp:1134` and `sound_constants.emp:151`).
  > Whatever unfixed-rate twin existed in 2026-06 is gone; **do not purge the survivor.**
  > The other two thirds (`dc.l SfxTable`, duplicate `sfx_NN_patches` banks) were not re-verified
  > in this pass — treat them as unconfirmed rather than established.
  > **2026-08-10 (package 4):** package 4's plan header listed F3 as "verified already fixed — SfxTable is
  > LIVE". That is consistent with the 2026-08-05 correction only for the `Snd_TimerA_Program` third; the
  > `dc.l SfxTable` / duplicate-patch-bank thirds remain UNCONFIRMED and package 4 did **no** work on them.
  > Do not treat F3 as closed.
- **F4** Stale/load-bearing-wrong comments: ISR "ix NOT touched" (it IS, via SfxDispatch — safe by
  construction, but the *reasoning* would license a future bug); `Sfx_Restore` "ret stub" (it's implemented);
  PSG header "never clobbers de" (it does; caller restores it); a0-clobber contracts on Sound_StopMusic/
  PlaySample/Ping/PlayRing (same class just fixed in Sound_PlaySFX — unify to all-preserve-a0).
  > **RE-VERIFIED 2026-08-10 (package 4).** The plan carried F4 as "already fixed"; that is **three
  > quarters true**, and the remaining quarter is not the bug this entry describes.
  > * ISR — **FIXED.** `SndDrv_ISR`'s header now states the opposite of the stale claim ("It does NOT save
  >   ix/iy, and PollMailbox DOES clobber them — SAFE for two reasons…") and the proc's machine-checked
  >   contract is `clobbers(ix, iy)`.
  > * `Sfx_Restore` "ret stub" — **FIXED**; the phrase no longer exists anywhere in `engine/sound/`.
  > * PSG header — **FIXED**; `sound_psg.emp`'s header now reads "They DO clobber `de`, however … the
  >   de=$4001 invariant is re-established by the Timer-A tick CALLER, NOT by PSG code preserving de."
  > * **a0 unification — NOT done, and re-classified.** `Sound_Ping` / `Sound_PlaySample` /
  >   `Sound_StopMusic` still declare `clobbers(a0)` while `Sound_PlayRing` declares `preserves(a0)`. But
  >   these are no longer COMMENTS — they are machine-checked `.emp` contracts, and each is TRUE (every one
  >   of the three does `lea <SLOT>, a0`). So there is nothing load-bearing-wrong left here: what remains is
  >   an **API-ergonomics** choice (uniform preserve-a0 costs a push/pop or a scratch register per call
  >   site), which belongs with the command-API work, not in a stale-comment sweep. **Reduce F4 to that one
  >   ergonomics item.**
- ~~**F5** Z80 blob space TIGHT: ~118 B code headroom… Plan a space recovery (bank FmPitchTableZ/LogVolumeLut/
  MovingTrucks_PitchTable into a $8000-window read)~~ **DONE (music-expr Task 0 banking, 2026-06-24):** the engine
  lookup tables were co-located at the start of Moving Trucks' streamed ROM bank (read with the song bank already
  in the `$8000` window — no swap), recovering Z80 code headroom from ~2 B → ~1016 B. The Phase 1/3
  music-expression features consumed most of that back; music-expr Phase 2 (detune/LFO/tempo/fade) and the
  2026-07-01 review fix pass took the rest. ~~**Phase-final as of 2026-07-02 (budget phase complete):
  `Z80_SOUND_SIZE` = $175A, ceiling `SND_STATE_BASE` = $18F0 → $196 (406) bytes free, DEBUG=1**~~
  **⚠ SUPERSEDED — see the correction under F1 above; the live figure is ~317 B DEBUG after the
  2026-08-03 wave-4 reclaim, having dipped to 86 B in between.**
  (build message / `s4.lst`; plain builds 126 B leaner — the A.1/A.2/A.3 recovery peaked at 802
  free, then portamento + the fidelity fixes spent it back). See F1 above (now DONE — the rewritten
  z80-ram-map spec carries the full headroom history), and the "Music-expression Task 0 (Z80 code
  recovery)" entry above.

### Per-frame pitch / volume envelopes (Phase 3a #2/#3) — DEFERRED, build-on-demand
**Surfaced during:** Moving Trucks missing-effects investigation (2026-06-19).
**Decision: do NOT build for MT; build only when a song's data actually uses them.**
**What:** A `ModUpdate` per-frame pitch-envelope processor (continuous intra-note pitch shape on
plain count==1 notes) and a per-frame volume-envelope/TL processor. A VGM census first *looked*
like MT needed these (oracle wrote freq ~16×/note, TL ~33×/note). **Re-measurement proved that was
an artifact:** the Zyrinx driver re-asserts every register every frame (60Hz full-state refresh) —
**97% of its freq writes and 99% of its TL writes are redundant re-writes of UNCHANGED values.**
Normalized to actual value *changes* per note, ours ≈ oracle (freq 0.92 vs 0.93/note; TL 0.43 vs
0.50/note). Our write-on-change engine already produces the same chip state. Building these now and
applying them to MT would ADD modulation MT doesn't have = over-modulation = WORSE. They remain
legitimate **general** capabilities (many FM tunes use real sweeps/swells) and the modulation layer
(`ModUpdate`, the design-for-C seam) is already architected to host them — so adding them later is a
clean drop-in. **When to build:** when a ported/authored song's command data actually requests
intra-note pitch/volume movement. Tool: `tools/vgm_intranote.py` (intra-note change census) +
`tools/vgm_modulation_diff.py`. LESSON: register write-COUNT is a misleading proxy; measure value
CHANGES. See memory [[project_mt_correct_source]].

### GATE articulation ($1A) — transcoder drops it (Phase 3a #4)
**Surfaced during:** same investigation. **Status:** deferred; only worth doing if percussion
phrasing audibly differs from B&R. **What:** MT uses 340 GATE commands (note-shortening, mostly
ch5/ch3/ch4 percussion). `tools/zyrinx_player.py` currently drops them (the gate-as-note-off model
b4137be/63bfd62 was REVERTED by 78fdfaf), and the engine has no sub-duration note-length field to
receive one. **When to build:** if the user reports percussion still lacks staccato/punch vs the
oracle. Needs BOTH a transcoder re-emit and an engine note-fill/gate-time field — and coordinate
with the reverted commits to avoid repeating whatever broke them.

### opbias-on-carriers fix (commit 05eca4a) — KEPT, carrier path not yet song-verified
**Status:** shipped + kept (correct latent-bug fix). `Fm_SetVolume` now writes carrier
TL = clamp(base + sc_opbias[op] + log), consistent with `Fm_PatchTlGroup`. **Caveat:** MT does not
exercise carrier opbias (FM2 carrier opbias=0), so it's verified by code audit + "doesn't break MT",
not by a song that uses it. **TODO when convenient:** add a synthetic alg5–7 test voice with a
carrier bias and capture-verify the $4x output, to bulletproof the untested path.

### ✅ RESOLVED — Multi-sample DAC loop-restart hardcodes the blip descriptor — by the DAC drum phase (2026-06-25)
**Surfaced during:** Sound 1C pre-merge audit (2026-06-17).
**Status:** **RESOLVED** — the DAC-format revision replaced the 1C looping-blip path wholesale: samples
are one-shots driven by the 9-byte `DacSample` descriptor table + the IDLE→PLAYING→DRAINING_TAIL→STOPPING
state machine; the FILL-exhaust restart branch is gone (`SND_BLIP_*` constants now only populate the
blip's own descriptor-table entry, like any other sample). Historical text below retained for lineage.
**Original status:** Benign in 1C (single DAC sample); **must fix before adding a 2nd DAC sample.**
**What:** The FILL-exhaust restart in `engine/z80_sound_driver.asm` (the rare "sample
exhausted → loop the blip" branch, ~line 399) hardcodes `SND_BLIP_PTR` / `SND_BLIP_LEN`:
```z80
        ld      hl, SND_BLIP_PTR
        ld      (SND_ROM_PTR), hl
        ld      hl, SND_BLIP_LEN
        ld      (SND_ROM_LEN), hl
```
instead of re-reading the **active `DacSample` descriptor's** loop fields (loop ptr / loop
len). In 1C there is exactly one DAC sample (the blip), so the constants and the active
sample agree and the restart is correct. The moment a second DAC sample (e.g. a real drum)
is added, an exhausted non-blip sample would incorrectly restart into the blip's bytes.
**When to fix:** when the DAC gains a 2nd sample (Phase 2 N-channel mixer, or any new drum):
have the exhaust branch reload `SND_ROM_PTR`/`SND_ROM_LEN` from the currently-playing
descriptor's loop fields (the `SND_LOOP_OFS` / per-sample loop machinery already exists in
`SND_STATE_BASE`), not from the fixed `SND_BLIP_*` constants.

### ~~Dead-but-drift-guarded 68k ROM table/patch copies (Plan 1C)~~ — **✅ DONE — resolved as option (b), `a3f2332`**
> **⚠ CLOSED — verified 2026-08-05.** The entry offered two exits: (a) adopt a banked-ROM loader
> so the 68k copies become live, or (b) decide inline-only is permanent and drop them.
> **(b) happened.** `a3f2332` (2026-07-01) deleted `data/sound/fm_patches.asm` and
> `data/sound/sound_tables.asm`; `FmPatchTable` has zero hits tree-wide and the files are absent
> from `games/sonic4/data/sound/`. The `main.asm` includes they rode on are moot — `main.asm`
> itself is deleted. Same closure as the "Dead 68k table copies" bullet in the Task-0 follow-ups
> above; the two entries were tracking the same two files.
**Surfaced during:** Sound 1C pre-merge audit (2026-06-17).
**Status:** Harmless in 1C; candidate for trimming in a later phase.
**What:** The FM writer / sequencer read **inline Z80 copies** of the sound tables and FM
patches (`engine/sound_tables_z80.asm` and `data/sound/fm_patches.inc`, both included into
the `phase 0` Z80 blob). The **68k ROM copies** — `data/sound/sound_tables.asm` and
`data/sound/fm_patches.asm` (the latter `include`s the same `fm_patches.inc`) — are emitted
into ROM (via `main.asm`) but **not read by any 1C code path** (decision: inline for 1C, not
banked). They exist for a future banked-ROM loader. They are **drift-guarded**: the patch
bytes are single-sourced through `data/sound/fm_patches.inc` (a `pbyte` macro picks `dc.b`/`db`
per CPU), and `gen_sound_tables.py`'s generator + its pytest keep the table copies in sync, so
the dead copies cannot silently diverge.
**When to fix:** a later phase that either (a) adopts a banked-ROM song/patch loader (then the
68k copies become live), or (b) decides inline-only is permanent (then drop the unread 68k
`.asm` copies + their `main.asm` includes to reclaim ROM). No urgency — drift-guarded, small.

### Phase 2–6 sound backlog (master sound spec §12)
**Surfaced during:** Sound 1C pre-merge audit (2026-06-17), per the 1C design §2 "explicitly deferred."
**What (each its own plan, per master spec §12):**
- ~~**Phase 2 — DAC powerhouse:** N-channel DAC mixer (quality-adaptive single↔mix), stereo/pseudo-
  stereo PCM, pitch-shifted SFX, half-rate samples, BRR codec (after spike), bank-switch optimization.~~
  **SUPERSEDED (2026-06-24/25 DAC format revision + 2026-07-01 amendment header on the master spec):**
  single voice, raw 8-bit, pre-mixed composites; mixer/BRR/pitch-shifted-PCM/half-rate cut (doors kept
  via `ds_codec`/`ds_rate`); bank-switch optimization SHIPPED (cached `SndDrv_SetBank`). Mixer rejection
  pending user ratification — see ARCH §6.2.
- **Phase 3a — FM depth (SHIPPED, merged `c89bea3` 2026-06-19):** per-frame modulation engine,
  per-song pitch table + pitch envelopes (trills/arps), pan, signed per-op TL bias, voice-stepping
  via build-time register deltas, hardware LFO ($22=$08), note-fill gate articulation, native Moving
  Trucks port. **Deferred build-on-demand within 3a:** **Task 7 portamento** (MEV_PORTA — `sc_porta_*`
  struct fields reserved, not rendered) and the **formal Task 9 verification-harness file**
  (`tools/phase3_verify.py` was never written; MT fidelity was instead verified ad-hoc by rendered-audio
  comparison vs the GD3 rip — see memory [[project_mt_resolved]]).
- **Phase 3b — FM extras (PARTLY SHIPPED 2026-06-27, music-expr merge):**
  ~~dual per-channel data streams~~ DONE (`sc_mod_ptr` slot[1] + `MacroTick` + `MEV_MACRO`, see E4 above);
  ~~SSG-EG~~ load-time DONE (`FmPatch` $90 group — runtime 7th-RegDelta-group still open, see E5);
  ~~full PSG envelopes~~ DONE (`Seq_Op_PsgEnv`/`MEV_PSGENV`, music-legal);
  ~~raw-register escape hatch~~ DONE (`MEV_REGWRITE` $F8, $2A/$2B-guarded).
  ~~true (division-based) portamento~~ DONE (per-note `MEV_PORTA` shipped resident 2026-07-02, budget
  phase T10); ~~broader sequencer-driven LFO use~~ DONE (`MEV_LFO`, music-expr Phase 2).
  **STILL DEFERRED:** Ch3 special/CSM, detune-unison.
- **Phase 4 — Adaptive FM6/DAC slot:** the three content-adaptive modes (full 6th FM voice /
  Batman time-share / permanent N-channel DAC mixer). 1C keeps FM6 permanently the DAC (simple model).
- **Phase 5 — Engine integration & game-feel:** section-aware sound banking, music fade state machine,
  distance attenuation + priority SFX mixing, procedural ambient soundscape, continuous SFX. (These are
  ENGINE_ARCHITECTURE §6.4–6.7, all DEFERRED.)
- **Phase 6 — MegaDAW compiler:** event-list format finalization, MegaDAW export retarget,
  sample/DC-offset encoders. (1C hand-authors the test song; MegaDAW integration + real song-sourcing
  are downstream/user-driven — the engine defines the format contract first.)
**Blocked by:** 1C, Phase 3a, the **SFX engine**, and the **music-expression spine** (Phase 1 + Phase 3) have
all merged to master. SFX now exists (`Sound_PlaySFX`, steal/priority/ducking) — the "no SFX path" gap is
**CLOSED**. The current sound priority is **music-expression Phase 2** (per-note portamento/detune + global
fade/tempo/hardware-LFO). Remaining after that: the DAC format revision (Phase 2 powerhouse — needs user
sign-off, irreversible), Phase 4 content-adaptive FM6, Phase 5 game-feel integration (section-aware banking,
fade state machine, distance attenuation, ambient, continuous SFX), Phase 6 MegaDAW. Each phase is audible +
Exodus-verifiable.
**See:** `docs/superpowers/specs/2026-06-16-sound-driver-design.md` §12; `docs/superpowers/specs/2026-06-17-sound-1c-design.md` §2.

### Defensive Z80 RAM Upload — Verify-and-Retry
**Surfaced during:** Ristar disassembly deep-dive (2026-04-27). Source:
`ristar_disasm/code/disasm.asm` lines 8330–8350 (`$641A` upload routine);
analysis in `ristar_disasm/ANALYSIS.md` § "Sound architecture (CONFIRMED)".
**Blocked by:** N/A for 1C — the from-scratch driver is **assembled inline into the ROM**
(`engine/z80_sound_driver.asm`, `phase 0` blob), so there is no runtime 68k→Z80 byte-by-byte
*driver upload* to wrap. This pattern applies only if a future phase streams driver/data bytes
into Z80 RAM at runtime (it does not today).
**What:** Ristar's Z80 RAM upload routine writes each byte, **reads it
back to verify**, retries up to 16 times on mismatch before giving up.
Most Genesis games trust the write; Ristar's team apparently saw
intermittent bus-contention failures and added the retry loop. The
relevant pattern (paraphrased):

```asm
; In: a0 = src, a1 = z80_dst, d0 = byte count - 1
upload_loop:
    move.b  (a0)+, d1               ; load src byte
    moveq   #15, d3                 ; retry counter
.retry:
    move.b  d1, (a1)                ; write to z80 ram
    cmp.b   (a1), d1                ; verify
    beq.s   .ok                     ; matches → next byte
    dbra    d3, .retry              ; mismatch → retry
    bra.s   .abort                  ; give up after 16 tries
.ok:
    addq.w  #1, a1
    dbra    d0, upload_loop
```

**When ready:** Only if a future phase adds a **runtime** 68k→Z80 RAM byte-copy
(e.g. streaming song/sample data into Z80 RAM, rather than the current inline-in-ROM
driver). Wrap each Z80 byte write with the read-back-verify retry loop. ~30 extra lines
of asm. Not applicable to the inline-assembled 1A/1B/1C driver.
**Why bother:** Cheap insurance against a real-but-rare bug class. Most
runs will hit `.ok` on the first try; the retry only fires when the bus
is contended (probably never on most hardware revisions, but the cost is
~zero when it doesn't fire). Catches write-loss before it manifests as
silent driver failure or audio glitches that are nearly impossible to
debug after the fact.
**See:** `ristar_disasm/ANALYSIS.md`, `ristar_disasm/code/disasm.asm`
lines ~8330–8350.

### Bank-latch desync corrupter — unidentified (2026-07-02)
Captured ONCE on HCZ2 (~44 s in): the Z80's physical $6000 bank latch and the driver's
`SND_CUR_BANK` cache desynced during a mid-sample DAC retrigger window; every $8000-window
read then returned $FF forever, so every music channel read $FF = `MEV_END` and ended
silently — and every subsequent song load stayed SILENT permanently, because
`SndDrv_SetBank`'s cache short-circuit (`SND_CUR_BANK` == requested → `ret z`) meant the
load never reprogrammed the physical latch. The PERSISTENCE half is fixed (Snd_LoadSong now
poisons `SND_CUR_BANK` with the $FF sentinel before its first SetBank, forcing a full
physical latch program on every load); the CORRUPTER itself is still unidentified — it may
even be an emulator artifact rather than real driver state loss. Evidence is preserved in-repo at
`docs/research/wedge_evidence/` (the capture + README with the full analysis; also covers the
related deterministic StopMusic cross-wait wedge found the same day). The
race did NOT reproduce on a deterministic re-run past the loop point — it is
alignment-dependent. **Hunt plan:** live watchpoint session on $6000-latch writes plus
`SND_SONG_BANK`/`SND_ROM_BANK`/`SND_CUR_BANK` around a mid-sample DAC retrigger, to catch
the latch and cache diverging in the act. **Optional second hardening** (deliberately
deferred pending the Task-9 cycle budget): a per-frame uncached re-latch at
`Run_SeqFrame_OnSongBank`'s head, ~8-12 B + ~100-130 cyc/frame, which would bound any
future desync to a single frame instead of one song.

## From Build Pipeline — Future Optimizations

### ✅ CLOSED 2026-08-19 — silent stale level data + the ~38 s content loop (`FAST=1`)
**Booking source:** the Aurora editor session's report of 2026-08-19, relayed with
measurements — its Build & Run loop was ~38 s (an ~8 s re-bake plus `./build.sh`), and the
session lost an hour to *save → build → reload shipping the PREVIOUS level data, silently*.
**Two defects, one parcel** (`feat/fast-content-build`, build orchestration only — zero ROM
bytes; all four canonical shapes stayed at their master CRCs).

**1. The silent-stale-data trap is closed structurally.** `games/<game>/prebuild.sh` is a
documented no-op and the generated level tree is a COMMITTED artifact (its generators read
out-of-repo donors), so nothing in `build.sh` ever noticed that the editor had saved since
the last re-bake. The only warning in the entire tree lived in `tools/regenerate-level.sh`'s
docstring — which is not where anyone reading a *green* build is looking. That is the same
shape as every other gate-nobody-runs defect this repo keeps rediscovering, except here the
gate did not exist at all. Now `tools/level_staleness.py` runs on **every** build:
canonical **fails loud** naming the remedy; `FAST=1` **auto-runs the re-bake** and reports
its time. The compare is deliberately a conservative whole-tree newest-mtime one rather than
a per-file pair map — one editor byte can move every page in the pool (it is globally
deduped across sections), so there is no stable pairing to derive, and a hand-maintained
second list would drift from the generator on the first schema change. Exclusions are
enumerated with a reason each in the tool's docstring; whole-second granularity is what keeps
a pristine `git clone`/`git worktree add` quiet. 12 unit tests in
`tools/test_level_staleness.py` (on `build.sh`'s pytest lane, so it is a gate and not a
convention).

**2. `FAST=1 ./build.sh` — and the answer to "is the assemble the ceiling": NO.** Measured
per-stage on the canonical `DEBUG=1` build (38.14 s total): `emp_expect_fail` 22.69 s +
`pytest tools` 12.40 s = **92% of the wall clock**, both verification; the sigil assemble is
**1.15 s (3%)** and `emit_sound_blob` 0.20 s. So the loop was never waiting on the ROM. FAST
keeps only the byte-producing steps (`emit_sound_blob`, `gen_compression_vectors`, the sigil
build with its checksum + deb2 appendix, plus the re-bake if stale) and lands at **1.3 s**
for `s4.debug.bin`, **1.7 s** release, **~0.6-1.0 s** for demo — verified byte-identical to
the canonical ROM on the same tree for all four shapes. It is a DEV shape: loud banner at
both ends, refused on the `STRESS_*` fixture shapes (those exist to produce evidence) and on
`CONTRACTS=0`.

**3. The re-bake's cold path — CLOSED 2026-08-19 by the incremental re-bake below.** This
entry originally booked "~9.8 s on its first invocation, cold donor page cache, nobody has
profiled it". Profiling found a different and worse story: the cost was not a cold page
cache and not a first invocation, it was **every re-bake that follows a real edit**. See
the entry immediately below.

### ✅ CLOSED 2026-08-19 — the re-bake after a REAL edit (14.7 s -> 1.0 s, incremental)

**The case nobody had profiled.** The `FAST=1` parcel measured a warm NO-CHANGE re-bake
(0.85-1.5 s) and booked the rest as a cold-cache mystery. The editor's actual loop is a
re-bake after a genuine chunk edit, and that case was **14.66 s** (measured here on a real
16x16 chunk stamp into `section_0.tiles.bin`, 16 cores, load ~35; the Aurora session
reported 7-12 s on a quieter machine). At 80%+ of the edit-look-edit loop it was the loop.

**The culprit, named.** Not compression of the act art pool, and not the dedupe /
spatial-order / paging pass — both hypotheses were wrong. Per-stage on the real-edit
re-bake:

| stage | no-change | one-chunk edit |
|---|---|---|
| `ojz_block_gen generate` | 0.16 s | **13.00 s** |
| `ojz_strip_gen generate` | 0.63 s | 0.87 s |
| 10x `salvador` (ZX0 pool pages) | 0.26 s | 0.35 s |
| `verify_level_bin` | 0.20 s | 0.19 s |
| everything else | ~0.2 s | ~0.2 s |

`ojz_block_gen` already had a per-SECTION content-hash cache, which is why the no-change
case looked cheap and why the real case looked like a cliff: one edited byte invalidates a
whole section, and rebuilding a section means the **S4LZ K-sweep** — `s4lz.compress` once
per (non-empty block, dictionary) pair, `K=0..3` dictionaries x ~72 blocks = 282 calls at
~47 ms each. Isolated: **13.152 s of a 13.19 s section**, against 0.033 s for
parse + extract + rank. 99.7%.

**The fix — one more caching tier, at the granularity the edit actually has.** A one-chunk
edit dirties exactly ONE 16x16 block, so `ojz_block_gen` now memoizes `s4lz.compress` per
`(block bytes, dictionary bytes)`. The edit recompresses 4 streams (one block x the 4
dictionary shapes) instead of 282. Free side effect: the memo also collapses duplicate
blocks WITHIN a run, so even a cold-cache full bake drops 12.1 s -> 2.0 s (1538 of 1870
compressions are repeats).

**Byte identity is the contract and it holds.** The caches are pure memoization of a pure
function. Full `--no-cache` regenerate vs cached re-bake after an edit: the whole
`data/generated/` + `data/collision/` tree byte-identical (`diff -r` clean bar
`DONOR_PROVENANCE.json`, which records the aeon repo's own git status and is not
ROM-embedded), and `s4.debug.bin` md5 `7003bece05d449a20d1bc0f860948a3c` from both paths.
Edit -> re-bake -> revert -> re-bake reproduces the original tree with zero differing files.

**Why a hit is trustworthy** (`tools/ojz_block_gen.py` carries the full argument):
- KEY COMPLETENESS. `s4lz.compress` is pure — `s4lz.py` imports only argparse/struct/sys
  and the function reads no file, environment, clock or randomness. Its output is a
  function of exactly `(data, tile_delta, dictionary, the s4lz.py source)`, and the key
  hashes all four, both byte strings length-prefixed. There is no fifth input to forget.
- INTEGRITY, two independent guards: a stored sha256 of each cache file's payload (catches
  truncation and bit rot; writes are `os.replace`, so an interrupted run cannot leave a
  torn entry), AND **output verification** — every accepted hit is decoded and compared
  against the source bytes it claims to encode. That is affordable only because
  decompression is ~780x cheaper than compression here (0.02 ms vs 19.1 ms per 768-byte
  block, measured): ~2 ms per section against a 13 s sweep. So even an entry forged with a
  valid file digest cannot put wrong data in the ROM.
- The division of labour is exact: the KEY gives byte-identity with `--no-cache` (a
  different-but-valid encoding would pass verification yet occupy different bytes); the
  digest + decode check give data correctness even if a key were ever wrong.

**Escape hatches.** `tools/regenerate-level.sh --no-cache` (and
`ojz_block_gen.py generate --no-cache`) read and write no cache at all. `rm -rf
tools/.cache` is always safe. Every run prints a `Cache:` line with sections served whole,
sections rebuilt, block compressions hit/recomputed, and any entries rejected by the decode
check. Cache lives in `tools/.cache/` (already gitignored) and deliberately NOT in
`data/generated/`, which is a committed artifact with an orphan check in
`verify_level_bin.py`.

**Timing table** (16 cores; load quoted because the machine was shared):

| case | before | after |
|---|---|---|
| no-change re-bake | 1.47 s (load 27) | **0.83 s** (load 6.7) |
| **one-chunk edit re-bake** | **14.66 s** (load 35) | **0.99 s** (load 6.6) |
| cold cache, full bake | — | 2.82 s (load 6.4) |
| `--no-cache` full regenerate | 13.26 s (load 25) | 10.06 s (load 5.6) |

The loop's real case is now under 1 s, so the residual-miss parallelism the parcel
authorised was measured as unnecessary and not built. `ojz_strip_gen generate` (0.37 s) is
now the largest single stage and the next lever if one is ever wanted.

**The honest limit.** The dictionary is a whole-section property: if an edit changes which
blocks `select_dict_blocks` ranks highest, every key in that section moves and the section
resweeps (only the `K=0` shape, whose dictionary is empty, survives). Editing a dictionary
block does the same. That is inherent — pinning the ranking to keep the cache warm would
change ROM bytes, which the byte-identity contract forbids. Asserted rather than hoped for
in `test_a_dictionary_shift_costs_a_full_section_resweep`.

**Coverage.** 25 tests in `tools/test_ojz_block_gen_cache.py` (key completeness incl. the
data/dictionary boundary ambiguity and the compressor-source dependency; both integrity
guards incl. forged-with-valid-digest at both tiers; cached vs `--no-cache` equivalence;
the edit/revert round trip; the one-block-edit miss count). Suite: **1143 passed, 3
skipped** via `python3 -m pytest tools -q` (baseline 1118/3 + 25).

**Still open (small):** `ojz_block_gen.py test` — the five original self-tests, including a
full decode round-trip of section 0 — is run by nothing. `tools/test_ojz_block_gen_cache.py`
does not wire them in, because `test_generate_roundtrip` on a cold cache would add ~13 s to
a 17 s suite. Worth wiring behind a marker or against a synthetic section.

### ⚠ PRE-EXISTING BREAKAGE — `STRESS_ART=1` fails to place (found 2026-08-19)
Found incidentally while regression-checking the off-canonical shapes against the `FAST=1`
parcel. `STRESS_ART=1 ./build.sh` re-bakes the uniquified 41-page pool fine (`verify_level_bin`
green, the EXIT trap restores the committed tree correctly) and then **fails in sigil's span
pass**: `sections 'section\036' [0x6B8C, 0x7016) and 'player_sensors\050' [0x66B0, 0x6BA4)
overlap in the image (colliding pins)`. **Confirmed pre-existing** — reproduced identically by
running master's own `build.sh` (`git show HEAD:build.sh`) on the same tree, so it predates
this parcel. The fixture's `--stress-art` derived placement (greedy pack from measured sizes,
org anchors held) no longer fits the current section sizes. `STRESS_EVICT=1` still builds
clean (`crc=cd17460e`). Not fixed here: this parcel is build orchestration and touches no
placement.

### Pre-Baked Path Tables for Loops / Special Geometry
**Surfaced during:** §4.7 world-space strip cache brainstorm (2026-04-30).
**What:** Define loops, S-tubes, and corkscrews as parametric curves in the editor. Build tool samples the curve and emits a path table: sequence of (x, y, angle) waypoints. At runtime, player snaps to path and interpolates between waypoints — no per-frame collision queries during traversal. Eliminates the most complex and error-prone collision scenarios. Classic Sonic's loops use path-swapping between collision layers with hand-tuned height maps; this approach makes loops reliable by construction.
**Blocked by:** Level editor integration, §3 player physics (need movement system to consume path data).

### Build-Time Collision Validation
**Surfaced during:** §4.7 world-space strip cache brainstorm (2026-04-30).
**What:** Use modern CPU power to simulate player traversal at build time. Verify slopes are traversable (not too steep for physics constants), detect collision gaps, flag unreachable areas, check height profile transitions between adjacent cells for smoothness. Catches level design errors before they hit hardware.
**Blocked by:** §3 player physics (need physics constants and movement model to simulate), §4.7 collision system (need collision data format finalized).

### Animated Tile DMA Scripts
**Surfaced during:** §4.7 world-space strip cache brainstorm (2026-04-30).
**What:** Pre-compute animated tile sequences (waterfalls, conveyors, flickering lights) as table-driven DMA scripts at build time. Each frame entry is a pre-built DMA command (source ROM addr, VRAM dest, length). Runtime just steps through the table — zero computation, zero logic. Build tool handles figuring out VRAM addresses after ~~graph coloring~~ and structuring DMA entries.
**Blocked by:** Animated tile system design (Phase 4), ~~VRAM graph coloring integration~~.
> **⚠ BLOCKER CORRECTED 2026-08-05 — the second blocker cannot ever be satisfied.** There is no
> VRAM graph coloring to integrate with; the allocator is dead (see the §2.3 correction). Read
> both mentions as "after the build tool assigns VRAM addresses", which the **deduped paged act
> pool already does** — so that half of the blocker is effectively discharged, not pending.
> **What genuinely blocks this is the first item only: the animated-tile system design.**
> Note also that a table-driven animated-band mechanism already ships in some form (`BgAnim`
> bands, referenced by the diagonal-budget and Deep-Forest-BG entries); check against it before
> designing from scratch.

---

## How to Use This Document

When starting a new planning phase:
1. Read the **RECONCILIATION BANNER** at the top first — it tells you which strata to trust.
2. Read the **NOW UNBLOCKED — actionable** section. That is the pick-up list.
3. Read through the remaining deferred items; check whether any blockers are now resolved.
4. **Re-derive any pre-July `file:line` anchor before chasing it** — those citations point into
   `.asm` files that no longer exist.
5. If an item is live, include it in the new plan.
6. ~~Move completed items to a "Done" section at the bottom (with the date and the system that
   unblocked them)~~ — **superseded 2026-08-05: annotate closures IN PLACE.** See the
   MAINTENANCE PROTOCOL section at the top. The Done section below is a frozen historical tail
   (Apr-Jun 2026); nothing new goes into it.

---

## Done (FROZEN — historical tail, Apr-Jun 2026)

> **Frozen 2026-08-05.** This section stops at 2026-06-11 and is not being extended. Roughly a
> dozen later closures were annotated in place instead of being moved here, and in-place
> annotation is now the convention (see MAINTENANCE PROTOCOL at the top). Entries below are kept
> verbatim as the record of the Apr-Jun era.
>
> **⚠ One entry in this section is actively misleading:** "§2 Phase 2 Layer A.3 — Build-time Graph
> Coloring — 2026-04-26" records a shipped feature that was **later deleted** (superseded by the
> globally-deduped paged act pool, 2026-06-22). Reading it alongside the §2.3 entry above produced
> the contradiction — the same feature listed as both future work and done — that this pass
> resolved. It shipped, then it was removed. Its sibling A.4 entry already carries a
> DELETED-2026-06-11 note of the same kind; A.3 did not, and now does.

### Strip data emission + streaming decompressor removed (dead format) — 2026-06-11
**Completed in:** compression-two-tier Task 5 (dead-code sweep).
**What:** The 2D block cache replaced column strips entirely; the remaining strip
artifacts are gone. Deleted: `engine/s4lz_stream.asm` (zero callers) + `StreamState`
struct + `S4LZ_Stream_States` RAM; `tools/ojz_strip_gen.py` Pass 5b (wide-strip
`.s4lz` + checkpoint emission); the legacy `OJZ_Sec*_Strips_S4LZ` /
`OJZ_Sec*_Strip_Checkpoints` BINCLUDEs in the act descriptor (~50 KB ROM); orphan
generated files (`sec*_collision.s4lz` — no generator, no references;
`sec*_tiles.s4lz` — replaced by `.zx0`; stale sec9-D leftovers from the 16-section
era). Raw `sec*_strips_a.bin` emission STAYS — it feeds `ojz_block_gen.py` and the
editor (`sec*_strips_source.bin`). Also deleted `Section_StreamArtGroup` +
`STREAMING_BUFFER_A/B` + `Streaming_Active_Buffer` + `SS_STREAMING` (see the A.4
entry note below). The Sec struct never carried strip pointers by this point — no
layout change.

### §2 Phase 2 Layer A.5 T1 — Per-Section Background (Zone-Shared Tier) — 2026-04-26
**Completed in:** §2 Phase 2 Layer A.5 (T1 only — T2/T3 fixtures deferred, see new entry below)
**What:** Plane B per-zone background art end-to-end. New shared-region VRAM block at slots 1280-1535 ($A000-$BFFF, 8 KB) reserved for BG tiles permanently — never overwritten by section transitions. Build tool extended: `load_bg_layout` parses OJZ_1.bin's BG section (16 chunk-rows × 128 cols), `build_bg_nametable_words` samples a 64×32 region, `emit_bg_tile_blob` dedupes + emits `bg_tiles.bin` with a 2-byte length header, `emit_zone_bg_layout` rewrites tile-index fields into the shared region (BG_TILE_BASE_SLOT + canon_idx). `chunk_get_tile_word` now honours chunk-entry X/Y flip flags (bits 10/11 per sonic_hack ProcessAndWriteBlock) — a latent bug uncovered during BG visual diff. Engine: new `engine/level/bg.asm` with `BG_Init` (loads BG tile blob to $A000 + blits zone nametable to Plane B at $E000, both blocking VDP DATA-port writes wrapped in stopZ80/startZ80) and `BG_RedrawForSection` (T2/T3-ready, called from teleport handlers; T1 sections with NULL `sec_bg_layout` skip). New struct fields: Sec.sec_bg_layout (replaces dead sec_strips_b placeholder, $1C, longword), Act.act_bg_layout ($16, longword), Act.act_bg_tiles ($1A, longword), Act struct $1A → $1E. Test scaffold loads dual palette: Pal_BGND (SonicAndTails, CRAM line 0) + Pal_OJZ (CRAM lines 1-3) matching sonic_hack's runtime layout.
**OJZ measurement:** 218 unique BG tiles (well within 256-slot capacity), bg_tiles.bin = 6978 bytes, zone_bg.bin = 4096 bytes, ROM cost ~11 KB. Engine cost: ~1.5 ms blocking at level init (display off), zero per-frame. Drop of 212 KB ROM elsewhere from removing the placeholder strips_b BINCLUDEs.
**Verified visually in Exodus:** Plane B renders OJZ's authentic cloud band (top) + sky transition + grass band (bottom) with magenta/pink/green palette colors, matching sonic_hack's Level_OJZ1_BG reference structure (image-9-style).
**Architectural fix vs spec:** §2.4's "T1 shares FG tiles, zero VRAM cost" claim was unworkable with A.3's per-section graph-colored FG pool — slots 0-1279 swap on every section transition, so BG nametable references can't reliably use them. The shared 256-slot region is the correct architectural fit. See `docs/research/per-section-background.md` Q5.
**See:** `docs/research/per-section-background.md`, `docs/research/tile-pipeline-measurements.md`.

### §2 Phase 2 Layer A.4 — Per-Section Deferrable Streaming — 2026-04-26
**DELETED 2026-06-11 (compression-two-tier Task 5):** `Section_StreamArtGroup` ended up
with zero callers — the union-blob model (color-class sections share one tile blob, so a
neighbor's art is already in VRAM; teleports mark sections `SS_RESIDENT` directly) made
runtime art streaming unnecessary, and the 2D tile cache (§4.7) superseded the preload
design it served. Removed with it: `STREAMING_BUFFER_A/B` (8 KB RAM),
`Streaming_Active_Buffer`, `STREAMING_BUFFER_SIZE`, and the `SS_STREAMING` state (value 1
retired; `SS_IDLE`/`SS_RESIDENT` keep their values). Entry below kept as history.
**Completed in:** §2 Phase 2 Layer A.4 (structural — visual verification blocked on upstream bug below)
**What:** `Section_StreamArtGroup` (engine/level/load_art.asm) decompresses + queues Deferrable DMA for an upcoming section. `Section_Check` extended to fire the preload trigger ~1024 px before the FWD teleport threshold (and ~512 px before BWD). Per-section state machine in `Section_Stream_State` (16 bytes RAM): `SS_IDLE` → `SS_STREAMING` → `SS_RESIDENT`. Two streaming buffers (`STREAMING_BUFFER_A`/`B`, 4 KB each, carved from existing `Decomp_Buffer`) handle fast direction reversals via round-robin. `Section_TeleportFwd`/`Bwd` retain blocking `Section_LoadArt` as a fallback for IDLE-state sections. `Level_LoadArt` reads section IDs from the act descriptor (not `Slot_Section_Map`) so it can be called before `Section_Init`.
**Verified structurally in Exodus:** `Section_Stream_State[0]=[1]=SS_RESIDENT` after Level_LoadArt; forward teleport advanced slot map 0/1 → 1/2 and Section_LoadArt fallback path fired correctly; backward teleport reversed cleanly.
**Visual verification blocked:** the test viewport renders mostly black due to a pre-existing upstream chunk/block parsing bug — see "Chunk/block parsing produces mostly-empty tiles" below.
**Closes the §4 Phase 1 deferred item:** "Section Preload with S4LZ Deferrable DMA" (the engine plumbing).
**See:** `docs/research/section-streaming.md`, `docs/research/tile-pipeline-measurements.md`.

### §2 Phase 2 Layer A.3 — Build-time Graph Coloring — 2026-04-26 — **DELETED SINCE (see note)**
> **⚠ SHIPPED, THEN DELETED.** Annotated 2026-08-05, matching the note its sibling A.4 entry has
> carried since 2026-06-11. The DSATUR coloring, `compute_adjacency`/`color_sections`,
> `assign_section_slots`, per-section tile blobs and `sec_vram_bases.asm` described below were
> **superseded by the globally-deduped, spatially-ordered paged act art pool** (2026-06-22, the
> OJZ tile-budget resolution) and then removed. Zero hits tree-wide for `DSATUR`,
> `color_sections`, `compute_adjacency` as of 2026-08-05; `ENGINE_ARCHITECTURE.md` and `CLAUDE.md`
> were both reconciled away from graph coloring in the Phase-3 cleanup. Kept verbatim as the
> record of what was built and why it was replaced.
**Completed in:** §2 Phase 2 Layer A.3
**What:** Section adjacency graph + DSATUR greedy coloring + per-section VRAM-slot assignment, all at build time. `tile_dedupe.py` gained `compute_adjacency`, `color_sections`, `assign_section_slots`. `tools/ojz_strip_gen.py` emits per-section tile blobs (one per OJZ section) and an auto-generated `sec_vram_bases.asm` constants file. `Sec` struct gained `tile_art_s4lz` longword + `tile_art_vram` word (struct $40 → $48; `Section_GetSlotDef` updated to multiply by $48 = 72 instead of 64). New `Section_LoadArt` decompresses + DMAs one section's blob; `Level_LoadArt` walks the slot map and calls it for both initial slots; `Section_TeleportFwd`/`Bwd` call it for the new section after each teleport. The leapfrog system's adjacency invariant guarantees that the two visible slots always hold sections in DIFFERENT colors → DIFFERENT VRAM ranges → both render correctly simultaneously. A.2's region-1/region-2 fields removed from `Act_Desc` (multi-region packing remains in `tile_dedupe` for future use; A.3's per-section model is the active path; Act struct shrunk back to $16).
**OJZ measurement:** 16 sections in a horizontal chain → 15 adjacency edges → chromatic number 2 (path graph is bipartite; DSATUR optimal). Color bases: [0, 10]. Max simultaneously-resident: 20 tiles (10 per color × 2 colors; per-section blobs include shared tile 0 separately, so total > A.1's 10. Structural regression for OJZ-scale data; structural enabler for any zone that exceeds A.1's 1536-tile ceiling).
**Verified in Exodus:** Default rendering matches A.2 byte-for-byte. Forward teleport updates slot map 0/1 → 1/2 and runs Section_LoadArt for section 2 (Decomp_Buffer confirms section 2's tile data was decompressed and DMA'd). Backward teleport reverses. No nametable corruption, no flicker, rendering correct in both directions.
**See:** `docs/research/section-graph-coloring.md`, `docs/research/tile-pipeline-measurements.md`.

### §2 Phase 2 Layer A.2 — Multi-region VRAM Packing — 2026-04-26
**Completed in:** §2 Phase 2 Layer A.2
**What:** `tile_dedupe.pack_regions` partitions canonical tiles across multiple VRAM regions; `tools/ojz_strip_gen.py` emits per-region pools (`ojz_tiles_r1.bin` / `ojz_tiles_r2.bin`) and supports `--force-region1-cap` for stress testing the spill path. Engine: `Level_LoadArt` calls `LoadArt_S4LZ` once per non-empty region. `Act_Desc` grew with `tile_art_r2_s4lz` longword (struct size $1C → $22). New constants `REGION1_TILE_CAPACITY=1536`, `REGION2_VRAM_BASE=$F800`, `REGION2_TILE_CAPACITY=64` define the layout. Region 2 lives in Plane B's off-screen rows ($F800-$FFFF, 16 rows × 128 bytes, 64 tiles), safe because OJZ's `cam_max_y=128px` keeps the visible bottom at nametable row 44 with a 3-row safety margin.
**Default-OJZ measurement:** 10 tiles fit in region 1; region 2 empty (placeholder S4LZ blob). Verified visually no regression vs A.1.
**Forced-spill (--force-region1-cap=5):** 5 tiles in region 1 (slots 0-4) + 5 in region 2 (slots 1984-1988); rendering matches default Exodus screenshot byte-for-byte. Confirms multi-region remap + dual LoadArt_S4LZ path works end-to-end.
**See:** `docs/research/multi-region-packing.md`, `docs/research/tile-pipeline-measurements.md`.

### §2 Phase 2 Layer A.1 — Tile Dedupe + Nametable Remap — 2026-04-26
**Completed in:** §2 Phase 2 Layer A.1
**What:** Global flip-aware tile dedupe across all 16 OJZ sections, with build-tool nametable strip remap. New `tools/tile_dedupe.py` module (canonical_form + dedupe_tiles + remap_nametable_word, 12 unit tests, lex-smallest of 4 orientations as canonicalization rule per `docs/research/tile-dedupe-canonicalization.md`). `tools/ojz_strip_gen.py` extended with `decompress_full_ojz_art` + `collect_referenced_tiles` and a 3-pass generate flow (build strips → dedupe globally → remap + emit). Engine: new `engine/level/load_art.asm` exposes `LoadArt_S4LZ` (decompress to `Decomp_Buffer`, queue Critical DMA) and `Level_LoadArt` (act-descriptor-driven orchestrator). `Act_Desc` struct gained `tile_art_s4lz` longword + `tile_art_vram` word. `STRIP_TILE_HEIGHT` bumped 32 → 48 to sample first ground band. Build.sh now invokes ojz_strip_gen + s4lz compress. Test state replaces two manual `QueueDMA_Critical` calls with one `Level_LoadArt`. Closes the deferred "OJZ Tile Art Loading — Full Terrain Visibility" item. **Headline:** strip tile-index ceiling 1856 → 9, nametable collisions 2 → 0, VRAM bytes 10,304 → 320 (32× less). Full per-layer metrics in `docs/research/tile-pipeline-measurements.md`.

### VInt_DrawLevel CD-bit Corruption + Section_UpdateColumns Ring-Buffer Tracking (§4.1) — 2026-04-26
**Completed in:** §4 Phase 1 polish
**What:** Two integration bugs uncovered by the synthetic scroll test (`tools/synth_scroll_test_gen.py`).
1. VInt_DrawLevel's `lsl.l #2, d0` encoding leaked d0[31:16] garbage into VDP CD bits, randomly redirecting ~70% of column writes to VSRAM instead of Plane A. Fix: `moveq #0, d0` before reading the VRAM addr each iteration of `.next`.
2. Section_UpdateColumns tracked left/right boundaries independently, ignoring that the 64-col nametable wraps. Fix: clamp the opposite side after each loop so `Right - Left ≤ 63` always represents what's actually correct in VRAM.

### 128KB DMA Boundary Splitting (§1.1 / §2.1) — 2026-04-24
**Completed in:** §2 Art & Compression Pipeline
**What:** `QueueDMATransfer` checks if `source + length` crosses a 128KB boundary and splits into two queue entries. Sub+sub carry-flag approach (~16 cycles common case).

### Build-Time DPLC Tools (§2.1 / §2.6) — 2026-04-24
**Completed in:** §2 Art & Compression Pipeline
**What:** `tools/dplc_layout.py` — contiguous art rearrangement (1 DMA entry per frame change) + DPLC entry merging (3.1 → 1.2 entries average). Sprite art extracted to `art/uncompressed/`, optimized art in `art/optimized/`, DPLC tables in `data/dplc/`.

## Sound — small deferred items from the 2026-07-01 review follow-up

### Cold-boot DAC pan seed (init $B6)
A `SND_REQ_SAMPLE` posted before the FIRST song load plays silent/one-sided (YM
powers on with $B6 L/R=0; the per-sample-start $C0 force was correctly moved to
the song loader so authored DAC pans survive, but `SndDrv_Init` doesn't seed
$B6). Debug-mailbox-only today (every shipped DAC trigger rides a song). Fix =
~10 B part-II seed in init — schedule with the Z80 RAM/ceiling rework.

### Boundary-tick patch pre-loading (generator)
Body-prefix thinning (b48b35e) cut the measure-5 burst 236->86 writes and fixed
the audible stutter, but boundaries with GENUINE multi-channel instrument
changes still cost ~25-35 ms ticks (per-load cost through the banked window).
If one ever turns audible: pre-load the new patch during the preceding gate gap
(the channel is keyed-off there — no audible timbre switch).

### ~~Frame-clock effective-rate tuning~~ — DONE 2026-07-02 (budget phase T11)
~~Timer-A N=136 (nominal ~59.99 Hz) measures ~59.63 Hz effective in Exodus (idle
poll latency). If a finer match to reference cadence is ever wanted, retune N
against MEASURED cadence (and re-pin the build assert) rather than nominal math
— but real hardware latency may differ from Exodus; don't tune to the emulator.~~
**Retuned exactly as this entry prescribed:** measured 59.873 Hz effective under
HCZ2 load at N=136 (deterministic from-start window), re-pinned to the compensated
N=137 (`SND_FRAME_MILLIHZ` 60053) → **59.9227 Hz exactly** over 10,800 frames, dead
center in the ±0.02 gate. `docs/research/phase_harness/t11_verification.md`.

## Sound — deferred follow-ups from the Sound Performance & Budget phase (2026-07-02)

Phase record: `docs/superpowers/specs/2026-07-01-sound-performance-budget-design.md` +
`docs/research/phase_harness/t*_verification.md` + `t12_matrix.md` (final numbers) +
`phase_notes.md` (the accumulated minors).

### Worst-tick shortening — the honest lever for the remaining DAC-hold tail (T9 outcome)
Drum airtime lost to holds sits at 24.1% vs ref's own 21.4%; the gap is a handful of
5-10 ms ticks (~4.6/s vs ref ~1.0/s). In-tick draining (D.2) was measured net-negative
twice and reverted — the remaining lever is SHORTENING THE WORST TICKS themselves:
profile what dominates them (patch-load YM busy-waits, bulk-refill length, event
clusters) in its own profiling round. `docs/research/phase_harness/t9_verification.md`.

### HCZ2 import loop-length residual (~−0.52% tempo vs S3K) — tools-side
The engine tempo model is now S3K-exact (`b342889`); the residual −0.52% drift is an
IMPORT defect: our packed HCZ2 loop runs ~14 event-ticks SHORT per loop vs the SMPS
source — same family as the fixed drum standalone-duration bug. Audit per-channel
packed loop tick counts vs the SMPS source (`tools/smps_import.py`). Related: MT's
tempo is −0.196% by construction (zyrinx rate 2/7 unrepresentable in the 8-bit mod
model; 73/256 is the nearest). `docs/research/phase_harness/t12_matrix.md` H.4.

### Held-envelope resolve cost (T8 review info item — perf backlog)
Sustained/parked env channels still pay id-resolve + cursor walk per frame
(~90-180T FM, up to ~540T PSG worst case `PsgVolEnv_1D`) just to rediscover $81/$83;
a held-sentinel (cursor bit 7) would cut that to ~30T. Needs bytes; the chip-write
elimination (T8) already removed the dominant cost. Revisit with any tick-cost round.

### Small correctness minors swept during the phase (from `phase_notes.md`)
- **$28 REGWRITE guard gap:** `Seq_Op_RegWrite` guards $2A/$2B/$24-$27 but NOT $28 —
  an authored REGWRITE to $28 can desync chip key state from `SCF_KEYED` (which the
  T5 chokepoint's bit-test relies on). ~4-6 B to extend the guard.
- **sc_base_freq steal-latch:** under SFX override, bare-note/NOTE_DUR paths skip the
  `sc_base_freq` latch (`Seq_HookNoteOn` ret nz), so a note change DURING a steal
  restores the pre-steal pitch; NOTE_RAW's pre-gate latch is the model fix. The
  comment at `sound_sfx.asm:1013-1017` oversells the current behavior.
- **Stale comment:** `z80_sound_driver.asm:1290-1292` "once the gates are removed
  (later task)" — the gates were removed in music-expr Phase 1.

### FM env attack seam (T8 residual — by-ear pending)
FM key-on resets the `sc_env_out` shadow to 0 without a TL emit; an FM env body with
leading zeros rides the PREVIOUS note's latched TL for 1-2 frames — after a
rest-silenced note the next attack could open TL-silenced. Not visible in rendered
A/B at capture scale; awaiting the user's by-ear pass. Candidate 0-2 byte fix if
audible: key-on primes the shadow with a never-matches sentinel.
`docs/research/phase_harness/t8_verification.md`.

---

## Sound — deferred follow-ups from the wave-4 Z80 reclaim (2026-08-03)

Parcel record: `docs/superpowers/plans/2026-08-03-wave4-z80-sound-reclaim.md` +
`docs/superpowers/notes/2026-08-03-wave4-sound-ab.md` (A/B evidence) +
`docs/reviews/2026-07-16-emp-port-optimization-review.md` STATUS UPDATE (drops/rejections).
Defect write-ups in `docs/BUGS.md`. The parcel executed review items **23 + 24**; item 25
and the two coverage gaps below are what it deliberately left on the table.

### Review item 25 — sequencer H1-H3 + M-items (≈ −71..−94 B still available)
**Surfaced during:** wave-4 scoping — item 25 was ruled OUT of the parcel by Volence as a
separate follow-on.
**Status:** unstarted. Roughly **−71..−94 B of pure-size, chip-stream-identical work**
remains in `sound_sequencer.emp`; `Porta_Apply`'s ladder factor alone is **−40..55 B**.
Everything in the parcel's ledger was measured, so these estimates are the last unmeasured
ones in the sound tree.
**CORRECTION that must not be inherited (do NOT re-plan on the review's premise):** the
review calls H1's per-channel tempo gate "provably redundant." **It is not.**
`Seq_Op_Tempo` (`$F3`) broadcasts **mid-frame**, from inside channel N's tick, so channels
0..N run that frame's gate with the old modulus and N+1.. with the new — a **permanent
accumulator phase offset**. Hoisting to a global accumulator is *more* S3K-exact but IS a
chip-stream change on that frame, so it cannot ride a PS (pure-size) bar. Dormant only
because no shipped song contains a tempo event. Its advertised "**−2 B/channel RAM**" is
also **not collectable**: `sc_tempo_mod`/`sc_tempo_accum` live in the SeqChannel↔SfxChannel
shared prefix that the `sx_pad+58 == sc_detune` invariant depends on.

### PSG vol-env fold clamp is a SINGLE-BIT test — wrong-channel write hazard
**Surfaced during:** wave-4 Task 9 (comptime hardening), while proving out the
`Psg_SetVolume` `Snd_ChanClass` collapse.
**Status:** contained by a build-time assert, NOT repaired. High-value to record because
the containment is data-side, not code-side.
**What:** the PSG **class** fold clamps with `cp $0F+1` — a real magnitude test. The PSG
**vol-env** fold clamps with `bit 4,a` — a **SINGLE-BIT** test. A fold sum in `$20..$2F`
therefore passes **UNCLAMPED**, and `$20` OR'd into the `$90|(ch<<5)` volume latch corrupts
the **CHANNEL-SELECT bits** — i.e. the attenuation is written to the WRONG PSG CHANNEL.
**Why it is unreachable today:** every authored PSG env body byte is `<= $10`, so the worst
fold is `$10 + $0F = $1F` — exactly one below the cliff. That margin is now **enforced by a
generator assert added in this parcel** (poison-tested: a `$11` byte fails the build).
**Consequences worth keeping together:**
- This asymmetry is also what makes the `Psg_SetVolume` fold-collapse UNSAFE — the
  full-domain enumeration returns **517,440 divergent cases out of 1,048,576**, which is why
  that optimization was rejected while its FM twin (7.6) shipped.
- **Restricted to env `<= $10`, the same reorder enumerates CLEAN (0 / 69,632 divergent).**
  So the −5..7 B optimization becomes available the moment the vol-env fold is made a real
  magnitude clamp (matching the class fold) instead of a bit test. That is the fix to reach
  for if the bytes are ever wanted — it buys the optimization AND removes the hazard.

### YM data→next-address spacing has NO structural coverage
**Surfaced during:** wave-4 Task 9 — the task set out to make the review's hand YM-spacing
audit structural, and got **half** of it.
**Status:** address→data IS covered, at all **9** write sites, by `ensure(cycles(...))`
guards that all pass (`Fm_YmWrite` ×2 = 21 T each, matching the review's hand figure
exactly; the seven DIRECT sites that bypass `Fm_YmWrite` measure 17-24 T). The
**data→next-address floor could not be expressed at any site.**
**Why (two independent blockers, both established by probe, not assumed):**
1. `cycles()` takes **proc-local labels** and carves ONE proc's code buffer. Every
   data→next-address gap starts inside `Fm_YmWrite`, exits through `ret` into the caller,
   and re-enters `Fm_YmWrite` — three procs of straight line.
2. Even the caller-local remainder contains `call nn` / `ret` / `pop af` / `bit n,r` /
   `add a,n`, none of which are in `z80_cycles::instr_cost`'s demand subset, so the span
   bails `[cycles.unknown-op]`.
Splitting the requirement across hand-derived prologue/tail constants was rejected — that is
exactly the hand audit the task existed to retire. A coverage ledger comment above
`Fm_WriteFreq` records the gap instead, and `YM_DATA_TO_ADDR_MIN_T` was deliberately NOT
declared: a constant nothing consumes would advertise coverage that does not exist.
**What would unblock it:** widening the cycle model's demand subset to the caller-local
opcodes above, plus a `cycles()` form that can span a call boundary.
**Unresolved question flagged as a CANDIDATE, not a defect:** several direct-write paths
measure **~20 T** data→next-address by hand, against the **~39 T** figure the review used as
the floor. This is NOT confirmed as a defect — the exact per-register hardware rule was not
verified, and there is no real hardware available here to settle it. Worth resolving before
any future change narrows those gaps further.

---

## On-target diagnostic instrumentation — idea capture 2026-07-20

**Framing (shared across three repos):** we use vladikcomper's Error Handler/Debugger
(and `convsym` from the same suite) as our one significant not-from-scratch tool. It's
excellent, but it's designed as a *drop-in library* for someone with an arbitrary
emulator and no control over their assembler — so it renders crashes to the Genesis
screen, symbolizes PC → nearest label, is post-mortem-only, and is 68K-only. **We are not
in that position: we own the whole stack (sigil assembler + Oracle emulator + MCP + build),
and we have no real hardware, so emulator-substitutes-for-hardware is a first-class goal.**
That changes what "better" means — the leverage is tight integration, not out-engineering
his handler. Emulator-side ideas live in `oracle-next/docs/2026-07-20-diagnostic-tooling-ideas.md`;
assembler-side in `sigil/docs/2026-07-20-diagnostic-instrumentation-ideas.md`. This section
holds the pieces that run **on the 68K/Z80 target itself** (the drop-in-library tier).

These are unbuilt ideas, not committed work. Pick up opportunistically.

- **Structured crash-frame mailbox (highest value; pairs with the Oracle reader).**
  Instead of rendering registers to VDP, a thin exception handler writes a fixed
  crash-frame struct (regs, PC, SR, USP/SSP, fault addr, a few RAM breadcrumbs) to a
  known RAM address and halts. Oracle reads it straight off the MCP socket as structured
  data — no rendering path, works even when the VDP is the wedged thing. ~100-200 B of
  68K + a `struct` def. This is the one piece worth building first because it turns crash
  debugging from "OCR the screen" into "query the crash." Reader half is an Oracle task.
- **RAM poisoning for uninitialized-read detection.** Fill all RAM with a poison pattern
  at cold boot; any value read back as poison = read-before-write. Catches the
  "works after soft reset, not cold boot" class. Debug-build only.
- **Stack high-water canary.** Sentinel pattern below the stack; check how deep it was
  ever eaten. 68K has no frame convention, so silent stack overflow into RAM is a common
  nasty failure — this makes it visible. Cheap.
- **Object-slot leak / use-after-free tracker.** Instrument the 64-byte SST slot allocator
  to flag leaks and reuse of freed slots. Debug-build only.
- **Z80 heartbeat / watchdog.** A counter the Z80 bumps that the 68K samples each frame;
  a stalled counter = silent sound-driver hang, which currently nothing catches (the
  drop-in handler is 68K-only). Small; closes a real blind spot.
- **Contract-enforcement trap handler (the 68K half). — ✅ PREREQUISITE HAS LANDED (2026-08-05).**
  Depends on sigil emitting the
  shadow-check instrumentation (see the sigil note). This repo's In:/Out: contract grammar
  (recent `contract-grammar` commits) is the vocabulary; a DEBUG build traps the exact
  instant a routine clobbers a register it swore to preserve or returns garbage in a
  promised `Out:`. High value because the expensive prerequisite (the contract grammar)
  is already being paid for.
  > **2026-08-05:** "already being paid for" has become "already paid, and still growing".
  > `clobbers(...)`/`preserves(...)` are declared and machine-checked across the tree, and HEAD
  > `fa0ae0b` extended the grammar to **declared contexts** (the Z80 bus and the interrupt mask).
  > The vocabulary this item needs exists and is richer than when the idea was captured. What
  > remains genuinely blocked is the **sigil half** — emitting the shadow-check instrumentation —
  > which is a Sigil-repo task, not an Aeon one. Listed in NOW UNBLOCKED with that caveat.

---

## Synced sprite-art streaming — idea capture 2026-07-29

**Framing:** the engine already streams level art aggressively; sprite art is the last
fully-resident holdout. Devon's SCHG guide ("Dynamically Loading Ring Animation Frames
into VRAM", info.sonicretro.org) shows the trick the classics never used: when every
instance of an object class shows the SAME animation frame (one global clock), keep only
the current frame's tiles in VRAM and DMA the next frame in when the clock ticks. This is
NOT per-object DPLC (which would be redundant per-instance loads) — it's one shared slot
+ one compare + one small DMA per frame *change*, serving every instance on screen. The
headline win isn't the VRAM refund; it's that animation frame count decouples from VRAM
entirely (frames live in ROM, uncompressed, DMA'd on demand).

These are unbuilt ideas, not committed work. Pick up opportunistically.

- **Ring frame swap (the concrete, do-first one).** Today: 16 tiles resident at
  `VRAM_RING_PLACEHOLDER` (4 frames × 2×2), `DrawRings` computes attr = base + frame×4
  (engine/objects/rings.emp:141-149) off global `Ring_Anim_Frame`. Change: shrink the
  slot to 4 tiles, freeze the attr at base (per-ring hot loop gets CHEAPER — attr becomes
  a constant), and in the existing `Ring_Anim_Timer` tick queue a $80-byte DMA of the new
  frame from ROM when the frame byte changes (every 8 frames ≈ 16 B/frame amortized,
  ~0.2% of a VBlank on change frames). Refund: 12 tiles. Unlock: the S1-2013 8-frame
  smooth spin (halve tick period, mask 7) at zero VRAM — the real reason to do it.
  Triggers to pick it up: we want the smooth spin, or the tile-1000 gap comes under
  pressure. Engine-contract note: `VRAM_RING_PLACEHOLDER` shrinks from ">=16 tiles" to
  ">=4 tiles" and the game must provide uncompressed frame-sequential ring art + a frame
  count; update engine.inc contract comment + demo game stub when done.
- **Generalize to "synced art channels" if a second consumer appears.** A small table of
  {clock RAM addr, ROM art base, bytes/frame, VRAM dest, frame mask} walked once per
  frame: compare clock vs shadow, queue DMA on change. Rings become channel 0. Candidate
  future channels: checkpoint orb spin, any globally-clocked hazard loop, animated
  goal-post spin. Don't build the table for one consumer — hardcode rings first
  (clean-not-bolted-on cuts both ways: no speculative scaffolding).
- **Single-instance effect streaming (shields, invincibility, signpost).** Different
  sync story, same economics: objects that exist at most once (per player) with many
  frames need only the current frame resident — a per-object stream, and redundant-load
  objections don't apply at instance count 1. The same SCHG family has a
  "Shield/Invincibility Art" guide in this vein. Evaluate when shields/invincibility get
  built (design queue), not before.
- **Badnik archetype animation lockstep (NOVEL BET — needs user sign-off).** Force each
  badnik archetype's loop animation (wing flap, tread roll) onto a per-archetype global
  clock; all instances of a type then share one streamed slot. Payoff scales with the
  mega-act tech demo (many archetypes resident at once is exactly its VRAM pressure);
  costs: lockstep look (subtle for loops), and state-dependent frames (attack poses)
  break sync so only the common loop streams. Genuinely novel — no classic or reference
  disasm does this; flag before designing (leapfrog-provenance rule).

## Release-shape error handler / MDDBG strip — EXECUTED 2026-08-05, then **SUPERSEDED BY OWNER RULING** (corrected 2026-08-05)

> # ⚠ THIS ENTRY DESCRIBED THE OPPOSITE OF WHAT SHIPS
>
> **The strip executed, and was then reversed. Release ships the FULL 4.2 KB MDDBG island.**
> `ReleaseFault` is **not** the release path — it is the **opt-in `lean`-profile-only** path.
> Anyone reading the text below as current would conclude that release has no crash handler and
> that all 60 fault vectors point at a red-screen freeze. Both are false.
>
> ### What actually ships (verified against HEAD, 2026-08-05)
>
> The deciding axis is **`CRASH_REPORT`**, an ordinary comptime define carried by every profile
> (`1` everywhere except the opt-in `lean` profile). `CODING_CONVENTIONS.md` §1.7 tabulates the
> three shapes:
>
> | shape | flags | debug equipment | crash handler | fault vectors point at |
> |---|---|---|---|---|
> | **debug** | `DEBUG=1`, `CRASH_REPORT=1` | yes | yes | `error_handler` per-class stubs |
> | **release** (default) | `DEBUG=0`, `CRASH_REPORT=1` | **no** | **yes** | `error_handler` per-class stubs |
> | **lean** (opt-in) | `DEBUG=0`, `CRASH_REPORT=0` | no | no | `ReleaseFault` |
>
> The gate predicate everywhere on this axis is **`DEBUG == 1 || CRASH_REPORT == 1`** — never bare
> `DEBUG == 1`, "or the debugger vanishes from release" (§1.7).
>
> ### The superseding ruling, in the code's own words
>
> `engine/system/vectors.emp:16-19`:
> > `── CRASH-REPORT POLICY — OWNER-RULED 2026-08-04, SUPERSEDES THE 2026-08-05`
> > `── RELEASE STRIP (review item 29 part 4)`
>
> …continuing: the release ROM is ~9% of a 4 MB cart, so space is not a 68k-side constraint, and
> **a player's crash must be REPORTABLE**. The MDDBG island and its deb2 symbol appendix are
> **DIAGNOSTICS, not debug EQUIPMENT, and diagnostics SHIP.** The shape-split gates are at
> `vectors.emp:79` and `:123`, both reading `if DEBUG == 1 || CRASH_REPORT == 1`.
> `engine/debug/error_handler.emp:12-17` states the same: the island ships in the DEBUG **and**
> RELEASE shapes; "the only shape without it is the opt-in LEAN profile
> (`sigil build --native --lean`, `CRASH_REPORT=0`), which routes every fault at `ReleaseFault`".
> `build.sh:10-19` says it a third time, and enumerates what release still does *not* carry —
> **equipment**: asserts, `SOUND_DEBUG_HOTKEYS`, `SOUND_DBG_MIRROR`, boot autoplay,
> `CompressionSelfTest`, the sound-debug mirror.
>
> ### Why the ordering looks wrong (it isn't)
>
> The ruling is dated **2026-08-04** and the parcel **2026-08-05**. The ruling is nonetheless the
> later authority: it explicitly names and supersedes the strip. The equipment-vs-diagnostics
> distinction is the whole point — the strip conflated the two, the ruling separated them.
>
> ### What survived the reversal
>
> The parcel's work was not wasted; it was **re-gated**, not reverted:
> - `engine/system/release_fault.emp` / `ReleaseFault` **still exists** and is still the described
>   red-screen freeze — it just serves the `lean` profile instead of release.
> - The vectors shape-split still exists — the predicate widened from `debug` to
>   `debug || crash_report`.
> - `null_interrupt.emp` deletion stands.
> - What reverted is the **placement**: `error_handler.emp` is NOT `debug_only`; it is placed
>   under `debug || crash_report`, so plain does **not** shrink by 4.2 KB.
>
> ### Consequences for anything downstream
>
> The "What ships in release today" table below (`plain_len == debug_len == 0x10B0`, 4,272 B) is
> **once again accurate for the release shape** — it was briefly wrong between the parcel and the
> ruling. Its framing as *a leak to be fixed* is what is wrong now: those bytes ship **by design**.
> Likewise the "Why this is blocked" section's central question ("what should a release build do
> on a bus error?") **has been answered**: release runs the real handler. The `lean` profile is
> where the `bra.s *` freeze answer applies.
>
> **Historical record of the strip parcel follows, retained unaltered.**

Part 4 of review item 29 ("build hygiene / release leaks"). Parts 1-3 landed on
`parcel/item29-build-hygiene`; this half stopped at the design gate — now RULED and
EXECUTED. The owner ruling: RELEASE ships ZERO debug equipment but still HALTS
LOUDLY. Implementation:

- `engine/debug/error_handler.emp` (the 12 exception stubs + the vendored MDDBG v2.6
  blob, ~4.2 KB) is now DEBUG-ONLY — registry `if debug` (native.rs), repin.toml
  `debug_only`, and `debugger.asm` gated behind `__DEBUG__` in both `game_root.asm`s.
- NEW `engine/system/release_fault.emp` — `ReleaseFault`: mask IRQs (`move.w #$2700,sr`),
  reset the VDP command state, set the backdrop red (`CRAM[0]=$000E`), `bra.s *` freeze.
  No stack, no `rte`, no `rts`, no `stop_z80`. RELEASE-ONLY (registry `if !debug`,
  repin.toml `plain_only`).
- `engine/system/vectors.emp` fault cells shape-split: DEBUG → per-class stubs, RELEASE
  → ReleaseFault (all 60). `null_interrupt.emp` DELETED (no referencer since item 27).

Verified: plain vector cells all point at ReleaseFault, MDDBG blob absent in plain /
present in debug, plain shrinks ~4.2 KB. Historical design record below.

### What ships in release today

`ERROR_HANDLER` is resident in **both** shapes — `plain_len == debug_len == 0x10B0`
(4,272 B) — and nothing in `engine/debug/error_handler.emp` is shape-conditional.
The registry places it unconditionally (`sigil/crates/sigil-harness/src/native.rs`,
the `engine.` prefix filter), so `demo.bin` carries it too.

| component | bytes |
|---|---|
| 12 exception-vector stubs | 346 (0x15A) |
| vendored MDDBG v2.6 blob (`ErrorHandlerBlob`) | 3,926 (0xF56) |
| `MDDBG__*` equ table | 0 (link-folded) |

The `MDDBG_ERROR_HANDLER` pin is tagged "debug-shape consumer only", which is
about the *symbol reference*, not the bytes. The bytes ship in release.

`Replay_OJZ_Fixture` is NOT in this region — it is its own 320-byte region
immediately after it. It is referenced by nothing in either shape (playback is
armed by an external poke) and is deliberately last before `EndOfRom` so
re-recording shifts no gameplay address. It is not part of this strip; it only
moves as a downstream address.

### Why this is blocked, not merely unstarted

**The two pre-run rulings pull opposite ways.** Ruling 1 says strip the MDDBG
blob *and the exception stubs* from release. Ruling 2 (item 27) says a spurious
or unexpected interrupt must **halt loudly in BOTH shapes**, because it means a
state the engine does not model and should surface rather than corrupt silently.
A release build with the stubs stripped cannot halt loudly unless something
replaces them.

The likely resolution is "strip the 3,926-byte vendored *debugger*, keep a
minimal loud halt for the fault vectors" — but that leaves a real product
question the code cannot answer: **what should a release build actually do on a
bus error?** `NullInterrupt` (`rte`) is the wrong answer for the fault classes —
an `rte` from a bus or address error re-executes the faulting instruction and
hard-loops. Candidate answers, all defensible: a 2-byte `bra.s *` freeze; a jump
to `EntryPoint` (soft reset); a coloured-border-then-hang so the failure is
visible on a TV. Whatever is chosen becomes the target of 55 vector cells.

### What it costs once ruled

Not mechanical. Following the `compression_selftest` pattern (source-gate every
call site, `if debug` in the registry, `plain_len: 0x0` in `pins.rs`, keep the
name in `map.toml`'s union order) covers the placement, but four things sit on
top:

1. **60 dangling `dc.l` cells.** `engine/system/vectors.emp` currently points 60
   of 64 vectors at handler labels, identically in both shapes; it would need a
   shape split. (Was 55. The item-27 parcel, 2026-08-04, executed ruling 2 and
   repointed IRQ1/2/3/5/7 — $64/$68/$6C/$74/$7C — from `NullInterrupt` to
   `ErrorExcept`, so five more cells now depend on the handler surviving. Those
   five are the NON-fault levels; for them an `rte` replacement is at least
   *safe*, unlike the fault classes. `NullInterrupt` itself is now referenced by
   nothing and is kept deliberately — see the note at the top of
   `engine/system/null_interrupt.emp` — precisely so this parcel has a tolerant
   primitive available if the ruling wants one for those five.)
2. **Four ungated file-scope `equ`s in the vendored `engine/debug/debugger.asm`**
   resolve to `pub equ`s living *inside* `error_handler.emp`. Unplacing the
   module removes them from the plain link. Whether the AS residual prunes them
   (it emits no bytes) or errors on the unresolved extern could not be
   determined statically — it must be settled by building. If it errors,
   `debugger.asm` also has to leave `game_root.asm` in the plain shape, which is
   harmless since it is inert without `__DEBUG__`.
3. **Large pin/golden churn**, in release AND in Config-B (silent, plain shape):
   `ERROR_HANDLER.plain_len` 0x10B0 -> 0, `REPLAY_FIXTURE.plain_base`,
   `EPILOGUE`/`EndOfRom`, `pins::ASSEMBLED_LEN`. `error_handler_port.rs` must
   drop its plain arm. Full byte-changing ritual.
4. **`demo` is in scope** on the same registry filter and carries the same 4,272
   bytes and the same 60 vectors.

### Recommendation

Take the ruling on release-fault behaviour first, then run it as its own parcel.
Sequenced after the ruling it is a day of work with a large, well-understood
blast radius; sequenced before, it is a coin flip on a product decision.

---

## Boot YM2612 key-off race — SPEC'd, deliberately NOT fixed (2026-08-04)

Review item 27, finding 3. The boot key-off block (`engine/system/boot.emp:200-230`)
has two real hardware defects: its six data writes are not busy-paced (most are
dropped on real silicon), and in a **sound build** `stop_z80()` can halt the
running driver between its own YM address and data writes, so the 68k's `$28`
latch steals the Z80's resumed data write (a dual-owner address-latch race).

**Owner ruling (2026-08-04): leave the code byte-for-byte untouched, write the
spec instead** — there is no real hardware here to verify timing against, and a
wrong fix is worse than the documented status quo because it would look
addressed. Done: `docs/specs/boot-ym-keyoff-race.md` carries the mechanism, the
two candidate fixes (key off before the bus release; or drop the block in sound
builds), the moot-today reasoning, and the revisit triggers.

**The dangerous revisit trigger:** the block is redundant only because the
`/IC` reset pulse at `engine/system/boot.emp:143-148` already keys every channel
off. Shorten or remove that pulse and these six unpaced writes become
load-bearing. Anyone touching the pulse must read the spec first.

**Unblocks on:** real hardware, or an emulator that models the YM2612 busy flag
and address-latch contention.

## BG blit posture + column-major transpose — EXECUTED 2026-08-05 (parcel/item28-bg-transpose)

> **EXECUTED.** Owner ruling 2026-08-04: take the transpose, take Tier-1
> `move.l`, **no DMA anywhere** (load_art keeps the queue). Deciding the CPU
> posture first dissolved the coupling below — "column-major forces 64 small
> DMAs" only bites if the init blits become DMA, and they did not.
> Landed as provenance chain entry 40; evidence in
> `docs/superpowers/notes/2026-08-05-item28-bg-transpose-ab.md`. The layout blob
> is column-major (pure permutation, 4,096/4,096 cells exact) transposed at the
> single editor->engine boundary (`tools/inject_editor_bg.py`), so editor-space
> artifacts stay row-major and no dual format exists. Framebuffers byte-identical
> over a 900-frame run including 600 frames of max-speed diagonal; zero
> scroll-lag frames on either build; +1 one-time init lag frame (the 64
> per-column VDP command setups), which is the cost the review itself priced as
> init-only noise.
>
> The analysis below is retained as the historical record of the fork.

The part of review item 28 the item is actually named for. The safe half (the
length-1 VRAM-spray guard, the dispatch inversion, the contract and comment
corrections) landed on `parcel/item28-bg-blit`; this half stopped at the time,
per the overnight run's standing instruction to stop on a design fork rather
than pick.

### Why it is one decision, not three

The review says so itself, three separate times: "decide together with bg.asm's
posture", "decide with load_art", and "column-major forces 64 small DMAs if the
init blits become DMA (decide together)".

1. **bg init blits** — both are CPU word pokes today: nametable 4,096 words
   (~90k cycles), tiles up to 7,168 words (~158k) — about **2 frames with SR
   masked and the Z80 stopped**. The ROM sources make this the conventions §7.2
   zero-copy case. Tier 1 `move.l` + halved `dbf` is a ~3-line change for ~80k;
   Tier 2 is a 4x unroll; Tier 3 is real DMA (~0.3-0.4 frame for all 22 KB) but
   needs 128KB-straddle handling.
2. **load_art posture** — queue+VSync vs direct blocking `stopZ80`/DMA/`startZ80`
   at display-off init. Each page currently pays up to a full frame parked in
   `VSync_Wait`; direct DMA saves an estimated **3-8 frames per act load**.
3. **the BG transpose** — column-major takes `Draw_BG_TileColumn` from ~34 to
   ~22 cyc/word (~380 per strip, and this is a **per-frame** cost at scroll
   speed), plus it unlocks `move.l` pairing. The review's consumer census says
   it needs NO dual format: the two linear consumers adapt via autoinc `$80`
   (row stride 128 fits the 8-bit autoinc register exactly) at ~2-3k cycles per
   blob, init-only noise, and their inner loops stay sequential-source.

The coupling is real: choosing DMA for (1) forces column-major into 64 small
DMAs, which changes the arithmetic on (3); and (2) shares the straddle handling
with (1).

### What the transpose costs beyond the engine

- **The ACT blob must be transposed too.** Production sections ship
  `sec_bg_layout = NULL`, so the act fallback is the common per-frame path — a
  transpose that only covers per-section blobs would miss the case that matters.
- `.emp` twins, `tools/ojz_strip_gen.py` and the editor-library blobs all flip
  **in one commit**, or the format is inconsistent between producer and consumer.
- Verification has to be mid-scroll, not at rest.

### One finding from the safe half, for whoever takes this

**The length-1 guard just added is NOT made redundant by a `move.l` conversion.**
A halved long count underflows identically on a 2-byte blob, so the guard would
be re-derived rather than deleted. The guard and the posture are less coupled
than they look, which is why the guard was safe to land alone.

### Recommendation

Take it as one parcel with a posture ruling in front of it, after measuring the
act-load time that (1)+(2) actually cost today — the review's cycle figures are
estimates and no profiling was run. The per-frame win in (3) is the one with
ongoing value; (1) and (2) are load-time only.

---

## RESOLVED — debug-fly is a CHEAT, gated at runtime (ruled 2026-08-05)

Raised as "debug-fly mode is REACHABLE in the shipped release ROM", found by
re-auditing the `crash-report` parcel's no-debug-equipment claim: `Player_Main` and
`TestPlayer_Main` toggled free-flight on a B press with no gate of any kind, so a
player holding B in the shipped build flew.

**Owner ruling: debug-fly is a CHEAT, not debug equipment.** It is therefore not a
§1.7 violation at all once it is gated the way a cheat is gated. Equipment is gated
at BUILD time and absent from release; a cheat is gated at RUNTIME and present but
unreachable. The payload SHIPS in release deliberately.

**What shipped (parcel `cheat-flag`).** A runtime gate, no build-shape gate:

- `Cheat_Flags` — a `u8` bitfield in game RAM (`games/sonic4/config/ram.emp`; cheats
  are game content, not engine).
- `CHEAT_DEBUG_FLY = 1 << 0` — bit 0 (`games/sonic4/config/constants.emp`).
- Both toggle sites test the bit before doing anything and fall straight through
  when it is clear: `Player_Main` (`games/sonic4/player/player_common.emp:249-270`)
  and `TestPlayer_Main` (`games/sonic4/objects/test_player.emp:76-119`).
- Boot-entry tests the same bit: `Player_Init`
  (`games/sonic4/player/player_common.emp:205-209`) — see below.
- The debug shape arms the bit at the game's one-shot boot init
  (`GameState_OJZScroll_Init`, `games/sonic4/test/ojz_scroll_test.emp`) inside an
  `if DEBUG == 1`. Release/lean write nothing: boot clears all Work-RAM, so the
  default of 0 costs **zero release bytes**.

So `Player_DebugEnter` / `DebugExit` / `DebugMove` / `TestPlayer_Debug` still emit
their bytes in release — that is now intended cheat payload, and all three gate sites
say so in comments for the next auditor.

**Boot-entry rides the same bit (done in this parcel).** `Player_Init` used to end
with an unconditional `jbra Player_DebugEnter` — the player *booted* into free-flight
so the streaming-test workflow started in the yellow square. Gating only the B toggle
would have stranded a release player in free-flight forever, since B is now inert:
strictly worse than the ungated state we started from. No separate ruling was needed,
because "default off, a cheat code turns it on" already means a release player starts
as a normal player. `Player_Init` now tests the same bit and tail-calls
`Player_DebugEnter` only when it is armed; with the bit clear it returns normally
with the slot in `PSTATE_AIR`, which lands on frame 1 — nothing else in the init
sequence was conditional on debug-fly. **The DEBUG shape is unaffected**:
`GameState_OJZScroll_Init` arms the bit before it calls `Player_Init`, so a debug
build still boots into the yellow square exactly as it did, and the dev convenience
survives for free. Only release behaviour changed, which was the intent.

**What remains.** (Item 2 was the follow-on question about the B button; it has since
been ruled and executed, and is kept in place below so the ruling sits next to the
gate it depends on. Items 1 and 3 are the genuinely open ones.)

1. **Author the cheat code that sets the bit.** Nothing else has to change when it
   lands: a button sequence or a menu unlock writes `CHEAT_DEBUG_FLY` into
   `Cheat_Flags` and debug-fly becomes reachable in a release ROM. That is the whole
   point of the runtime-gate shape.
2. **Should B join `BUTTON_JUMP_MASK`? — RESOLVED, and EXECUTED as parcel
   `b-jumps` (ruled 2026-08-05).** Jump was `A|C` only precisely because B was the
   debug-fly toggle; once the toggle went behind `CHEAT_DEBUG_FLY`, B did nothing at
   all in release, which is the classic-wrong behaviour — S3K jumps on all three face
   buttons.

   **Owner ruling: B jumps when `CHEAT_DEBUG_FLY` is CLEAR; B does not jump when the
   bit is ARMED.** Default players get the correct three-button jump; anyone who has
   deliberately enabled the cheat accepts that B is the free-flight toggle instead.
   The gate is a conditional mask, not a static one, because the cheat bit is
   runtime-settable — a future cheat code can arm it on any frame, so anything
   precomputed at init would go stale. Both sites read the bit where they use it.

   **The exit path is what forced the exclusion.** The conflict is not on ENTERING
   free-flight — that returns early through `Player_DebugMove` and never reaches the
   jump code. It is on EXITING: `Player_DebugExit` clears `debug_flag` and falls
   straight through into normal physics, so the very same B press that left
   free-flight would be seen by the jump latch and buffer a jump on that tick.
   Excluding B from the mask exactly while the bit is armed is the whole mechanism;
   a mask that always included B would give every debug-fly exit a spurious jump.

   **Both consumers had to agree, so the mask stopped being duplicated.** The press
   latch (`Player_Main`) and the variable-jump-height HELD check
   (`PState_AirShared`) each carried their own file-local `BUTTON_JUMP_MASK`. If B
   latched a jump but did not sustain it, B jumps would come out with a clipped arc —
   a feel bug that would be miserable to trace. The pair now lives once, in
   `games/sonic4/player/player_common.emp` as `pub const BUTTON_JUMP_MASK`
   (`A|B|C`) and `pub const BUTTON_JUMP_MASK_NO_B` (`A|C`), and `player_air` imports
   both. Both sites run the identical shape: mask `A|B|C` and short-circuit,
   `moveq #CHEAT_DEBUG_FLY, d0` / `and.b Cheat_Flags, d0`, re-mask `A|C` only when
   armed. Cost lands on the cold side — the frames with no face-button press (in the
   latch) or no face button held (in the release-cap check) exit on the first `beq`
   and never probe the cheat byte, so the per-frame cost is unchanged from before.

   **Why the gate is `moveq`/`and` and not `btst`, at all four cheat sites.** A
   `btst #CHEAT_DEBUG_FLY_BIT, Cheat_Flags` shape was written first and assembled
   fine in the full build, but it is unlowerable in a standalone port-test compile:
   `games/sonic4/config/constants.emp` `pub const`s harvest into link EquSyms
   (`harvest_game_constants`), and `Cheat_Flags` is a link symbol too, so both
   operands are symbolic — `[lower.imm-link]`, "a link-time immediate combined with
   another symbolic operand is not yet supported". `andi.b #BUTTON_JUMP_MASK, d1` is
   unaffected because only one operand is symbolic. The `moveq`/`and` pair keeps one
   symbolic operand per instruction, costs the same 6 bytes and the same 16 cycles,
   and is the shape the `cheat-flag` parcel already used at `Player_Init` /
   `TestPlayer_Main`. Caught by `test_p2_player_states_port` under the strict suite,
   not by `build.sh`. **There is deliberately no `CHEAT_DEBUG_FLY_BIT` twin**: a bit
   number and a mask that can disagree is precisely the drift class this run has been
   paying for, and with the mask as the sole representation there is nothing to
   guard.

   **Not in scope: `test_player`.** `TestPlayer_Main` jumps on C only and uses A as
   its free-flight turbo modifier; it is scaffolding with its own input map, not the
   player, and item 3 below already asks the larger question about it.
3. **`test_player` as a unit.** The whole object is scaffolding that ships in release
   regardless of this ruling; whether it should is a separate question about the test
   object set, not about debug-fly.

### Correction: the `Debug_AssertObjLoop` entry that used to be here was WRONG

An earlier version of this entry claimed `Debug_AssertObjLoop`
(`engine/objects/core.emp:564`) shipped its bytes in release. **It does not.** Its body
is already `if DEBUG == 1`-wrapped, so it emits ZERO bytes in the plain shape — the
symbol and `RunObjects_Frozen` share address `$2BEE`, i.e. span 0, and `core_port`'s
`debug_shape_length_diverges` already pins plain = zero bytes. The source comment says
so explicitly.

The claim came from a subagent that read the symbol's ADDRESS out of `s4.lst` and
concluded bytes ship, and it was propagated into this document and into
`docs/superpowers/notes/2026-08-05-crash-report-ab.md` without being checked. **A
symbol in the listing is not emitted bytes** — zero-length labels appear at the address
of whatever follows them. The right measurement is the span to the next symbol, which
is what found the real leak above. Fourth instance of this repo paying for an unverified
claim; the first three were `[closed by <pending mechanism>]` markers.

---

## `VInt_Level` header comment states a stale execution order (found 2026-08-05)

`engine/system/vblank.emp:61-63` documents `VInt_Level` as running "Critical drain ->
VSRAM -> budget -> Important drain". The body (`vblank.emp:91-138`) seeds the frame
budget at the top and charges it **before** the Critical drain. `ENGINE_ARCHITECTURE.md`
§0.10 describes the body correctly, so the doc is right and the **code comment** is the
thing that drifted — the inverse of the usual direction, which is why the §0
reconciliation pass surfaced it.

One-line comment fix, zero byte change. Left out of the §0 doc parcel because that
parcel was deliberately doc-only (no `.emp` touched, so it needed no repin/refreeze).

---

## Owner rulings, 2026-08-05 (backlog reconciliation follow-up)

Four decisions taken after the reconciliation. Recorded here so they stop resurfacing as
open questions.

### Diagonal streaming budget — MARK AND REVISIT (not accepted, not fixed)

**Ruling (Volence):** neither accept the dip nor spend on it yet — mark it and revisit.

So this stays OPEN and is deliberately *not* closed with the on-file "accept the dip"
recommendation. The three shapes remain: (A) accept the dip, (B) cap the combined diagonal
step, (C) cut BgAnim bands during fast scroll. Revisit when there is a reason to — most
likely alongside art-streaming Phase 2, whose budget model touches the same frame window,
or when a level actually plays at sustained max diagonal. Do not re-ask it before then, and
do not silently take (A).

### `children` C1c — band inheritance: IMPLEMENT clear-then-set

**Ruling (Volence):** implement proper inheritance rather than ratifying the refusal.

The existing refusal is sound *for the current idiom* (`CHILD_INHERITED_FLAGS` composes with
`or.b`, and the priority band is a 3-bit VALUE, so `or`-ing 5 and 6 yields 7). The fix is
therefore not "add the band to the inherit mask" — it is a **clear-then-set** idiom: mask
the band bits out of the child's render flags, then OR the parent's band in. This is a
convention change affecting every child-creation site, so it lands as a single templated
change rather than nine hand-edits. **EXECUTED 2026-08-05** (`parcel/defect-batch-8`):
`set_priority_band` comptime template in sst.emp + CHILD_INHERITED_FLAGS gains the band.

### Object-test scene — GATE DEBUG-ONLY

**Ruling (Volence):** the whole scene stops shipping in release.

`GameState_ObjectTest_Init` and its test objects (TestPlayer, TestStatic, TestAnimated,
TestEnemy, TestSolid, TestParticle, TestEmitter, TestChildPart, TestStressEmitter,
TestChurnObj) are pushed unconditionally today (`native.rs` registry, no `if debug`) and are
**unreachable from the game entry point** (`games/sonic4/config/game.emp:23-24` →
`GameState_OJZScroll_Init`). By the `CODING_CONVENTIONS.md` §1.7 rule — a harness you drive
is equipment, and equipment does not ship — they belong in the debug shape only. Same
registry idiom as `CompressionSelfTest`. The OJZ level is unaffected: it spawns the real
Sonic player (`ojz_scroll_test.emp:134 jbsr Player_Init`), not `TestPlayer`.

**Correction worth keeping:** an earlier framing of this decision claimed `test_player` was
"the object driving the test scene". It is not. The yellow square in the OJZ level is
`Player_DebugMove` — the real player's debug-fly. `TestPlayer` is a separate object used
only by the object-test scene (`object_test_state.emp:88, :271`). The two were conflated.

### Debug-fly cheat code — DEFER to design #7

**Ruling (Volence):** defer until the screens/HUD design lands.

The runtime gate (`Cheat_Flags` bit 0, `CHEAT_DEBUG_FLY`) shipped with chain 43 and is
covered by the replay net, so the payload is ready and tested. What is missing is somewhere
to *enter* a code: classic codes live on a title or level-select screen, and screens are
design #7 (banked, unexecuted). Inventing an in-gameplay button sequence now would be
throwaway work replaced when #7 lands. Pick this up as part of #7.

---

## Ledgered by the 2026-08-05 defect batch (`parcel/defect-batch-8`)

### `vdp_stride80` declared context — DEFERRED, with the dead ends pinned

Defect NEW-1 (VInt_Lag trusting the unasserted "autoinc = $02 on exit" ambient) was closed
with the unconditional runtime re-assert (`move.w #$8F02, VDP_CTRL` at the Critical drain
head — 8 bytes, 20 cycles, lag frames only). The STRUCTURAL close — a declared context whose
release half restores `$8F02` — was evaluated and rejected as disproportionate. Pin the
reasons so the next session does not re-walk them:

- Contexts prove bracket PAIRING, not register VALUES. VDP control-port write-sequence
  tracking is an explicit spec exclusion (sigil contract-unification spec §3/§9, the S2-D7
  exclusion). Nothing forces a raw `#$8F80` write into a bracket — there is no inferred VDP
  net analogous to the Z80 `[bus.*]` tier.
- An IRQ is not a CFG edge: a correctly bracketed writer running UNMASKED in the main loop
  when VInt_Lag fires is the real residual failure mode, and `requires(...)` (proc-level,
  conjunctive) cannot spell "only under ints_off OR vblank" at bracket granularity.
- Full closure needs two sigil checker extensions (context-level any-of requires; an
  immediate-$8F-outside-bracket lint) — both emission-neutral, but two new checker semantics
  plus a byte-changing hot-loop adoption to protect one 8-byte invariant.

REVISIT only if a second stride-switching writer ever appears outside the current three
files (plane_buffer / bg / section — full 9-site inventory in the defect-batch scoping
notes).

**SUPERSEDED 2026-08-14 — the runtime re-assert is gone, and NEW-1 is closed by a stronger
mechanism.** `Flush_VDP_Shadow` now re-blits every shadowed register including `$0F`
unconditionally at the top of both VBlank paths (§0.4 blanket restore), and reg `$0F`'s shadow
byte is `$02` from `BootData_VDPRegs` with no writer anywhere. On the `VInt_Lag` path nothing
between the flush and the Critical drain touches the VDP at all — `Enqueue_Dirty_Buffers` is
RAM-only — so the 8-byte `move.w #$8F02, VDP_CTRL` was provably dead and was deleted rather
than kept as a dormant scaffold. The ambient invariant NEW-1 distrusted is no longer what the
lag path rests on. `VInt_DrawLevel`'s own `.done` restore is a different case and stays: it
sits *between* the flush and the drain on the `VInt_Level` path, downstream of a real `$8F80`
excursion, so it is load-bearing. The structural-close reasoning above still stands as the
verdict on declared contexts for stride switching.

### `Palette_Dirty` drop-retained analog — RECORDED, not fixed

The NEW-3 class (a Critical-queue drop retains a dirty flag; IRQ6 then ships a stale
snapshot against a mid-write buffer) exists in principle for `Palette_Dirty` + the palette
buffer: a drop-retained line bit + IRQ6 landing mid-palette-buffer-write ships a torn line.
Narrower than the sprite case (per-line bits, 32-byte lines, no length field to skew, and
palette writers are fade steps — not a per-frame emit loop), so it was left out of the
sprite fix deliberately. If palette corruption during a fade under heavy Critical-queue
pressure is ever reported, this is the mechanism; the fix shape is the same emit bracket.

---

## Ledgered by the 2026-08-08 art-streaming Phase 2 Task 2 review (`feat/art-streaming-p2`)

### `compression_selftest` engine-agnosticism smell — RECORDED, not fixed

The DEBUG boot equivalence walk (`engine/debug/compression_selftest.emp`) proves
`ZX0R_Decompress` byte-identical to `ZX0_Decompress` over every act-pool page. To reach the
pool it hardcodes the game-specific symbol `OJZ_Act1_Descriptor`, behind a
`HAS_ACT_ART_POOL` comptime define (sonic4 family = 1, demo = 0) so the block is discarded
in the game-agnostic demo build. It works and keeps demo green, but it plants a
`games.sonic4.*` reference inside a shared `engine.*` module — the exact engine/game-wall
crossing the restructure exists to prevent. It also forces the engine module's isolation
port test (`compression_selftest_port.rs`) to inject a game symbol as a cross-seam carrier.

**Cleaner shapes when revisited:** (a) bind the current act descriptor through the Game
contract (an engine-visible hook the game supplies), so the self-test walks "the game's act
pool" without naming a sonic4 symbol; or (b) move the act-pool equivalence walk into
`games/sonic4` test scaffolding, leaving `compression_selftest.emp` testing only the engine
golden vectors (fully game-agnostic). Either removes the `HAS_ACT_ART_POOL` define and the
port-test carrier injection. Low urgency — the current form is correct and cheaply
reversible.

### Equivalence walk does not assert `form == ZX0` — RESOLVED by Task 5

The self-test fed each act-pool page to both decoders assuming the page is a ZX0 (version
2) stream past the 4-byte wrapper. **FIXED in Task 5 (P2b format cutover, 2026-08-08):** the
`.eq_page` walk now strides the manifest v2 `PageManifest` records (stride 8), reads the
source from `pm_source` and length from `pm_tiles`, SKIPS `pm_tiles==0` pages, and
equivalence-tests ONLY `pm_form == ART_PAGE_FORM_ZX0` pages — a raw-direct page is skipped
(ZX0-vs-ZX0R equivalence is meaningless there). This was also the crash fix: the old
stride-4 longword walk dereferenced garbage once the table became stride-8 v2 records
(ADDRESS ERROR at `CompressionSelfTest.eq_page`).

## Ledgered by the 2026-08-08 art-streaming Phase 2 Task 3 review (`feat/art-streaming-p2`)

### Bookmark straddle → rare benign single lag frame — KNOWN RESIDUAL, corrected lemma

The sketch §2 lag-impossibility lemma ("the lag path can never bank") is OVER-STATED. The
VBlank hook runs BEFORE the Ready/dispatch split, so it banks the decode on WHICHEVER path
dispatches. Counterexample (reviewer-proven): after `VBlank_Ready := 1`, if the first VBlank
lands during the pre-decoder setup window — the ~150-cycle `PageIn_Resume` restore/push, or
the DEBUG scaffold's page scan — it correctly does NOT bank (PC outside `[ZX0R_Decompress,
.__end)`), runs `VInt_Level`, and clears `Ready`. The decode then runs to the NEXT VBlank
with `Ready = 0`, which dispatches `VInt_Lag` and banks the decode there. This is SAFE (the
main loop is parked in the decoder, so `Plane_Buffer` is already drained and `VInt_Lag`'s
skipped plane drain is a no-op; the banked context survives either path via the movem
round-trip), but it costs one benign lag frame at roughly per-resume probability. The true
invariant is "the bank is safe on whichever path dispatches," not "the lag path can never
bank." The `vblank.emp` hook comment now states the corrected form.

**Task-12 action — ✅ DONE (2026-08-09).** The ARCH §9.7 rewrite landed the CORRECTED lemma, NOT
the draft's "lag path can never bank" phrasing. The draft (invariant 3) was swept and its stale
"the lag path can never bookmark — a mid-decode VBlank always dispatches `VInt_Level`, structurally"
claim was replaced verbatim by "the bank is safe on whichever path dispatches" + the benign single
lag frame. Execution record won over the pre-execution draft, as flagged.

## Ledgered by the 2026-08-09 art-streaming Phase 2 Task 12 closeout (`feat/art-streaming-p2`)

### Sigil isolation-port systemic-inject — the `DMA_Enq_Bytes_Frame` class remains — SIGIL ASK, RECORDED
The Sigil isolation port tests lower ONE engine module standalone against an EMPTY symbol table, so
any cross-seam reference (an `engine.constants` immediate, or now a cross-module RAM word) must be
either kept module-local or injected as a port-test carrier. Two instances of this pattern are now
on the books and it is systemic, not one-off: (a) `bg_anim.emp` keeps a module-local
`BGANIM_MAX_BANDS` mirror with a drift comment because re-homing it to `engine.constants` breaks
`bg_anim_port`'s standalone link (item 30/F, reverted; `bg_anim.emp:40-47`); (b) the T2
`compression_selftest_port.rs` injects a game symbol (`OJZ_Act1_Descriptor`) as a cross-seam carrier
(T2 wall-smell entry above). The T8 dual-cap added `DMA_Enq_Bytes_Frame` (a RAM word charged from
`dma_queue.emp`'s shared enqueue path and reset in `vblank.emp`) — the SAME class of cross-module
reference that a `dma_queue`/`vblank` port test must carry. **Follow-through:** the real single-
authority fix is a comptime path from `ram.emp`/`constants.emp` into a CODE module's consts that
survives standalone lowering (does not exist today, per `bg_anim.emp:45-47`). Until it does, each new
cross-seam RAM/const reference costs a port-test carrier injection or a module-local mirror. This is
sigil-repo work (`/home/volence/sonic_hacks/sigil`), recorded here so the accumulating injections
are seen as one systemic item, not filed one at a time.

### Oracle MCP wedge on repeated long `press` — EMULATOR-SIDE, for the oracle backlog
During the T11 acceptance-matrix bonus sweep (after the matrix itself completed clean), the oracle
MCP wedged: **two consecutive `press` calls each timed out at 1800 s on fresh oracle instances**,
hanging the controller's confidence sweep (abandoned; the matrix evidence was already complete).
This is an emulator-side/MCP-arbiter fault, NOT an Aeon-engine issue — the ROM was fine and the
matrix passed. Pattern to watch: long-duration `press` on a freshly-launched instance can wedge the
arbiter; the workaround was to abandon and rely on the completed evidence. Recorded for the **oracle
backlog** (oracle-repo work, not Aeon). Consequence for Aeon: none remaining — the final oracle
spot-check passed and the T12 merge landed on master (`2f047e3`).

## Ledgered by the 2026-08-09 sound game-feel package 1 execution (`sound-pkg1`)

Package 1 (`plans/2026-07-03-sound-game-feel-moments.md`) EXECUTED: pause/unpause
(music + all scopes, freeze-in-place, pop-free $B4 mute + resume voice re-upload),
jingle push/pop (frozen mid-song resume under a fade-in), the song-finished/comm
status contract (`SND_STAT_SEQ_ACTIVE/COMM/JINGLE/FADE_BUSY`; natural song end now
drops `SND_SEQ_ACTIVE`), composed fade terminals (out+stop / out+pause), the R4
spread-bit fade-rate table (8 speeds from the command byte's rate nibble), the
TimerA-DMA refill guard (user-ruled), and the 68k API v2 wrappers/readers.
`zFadeToPrev`-style fade-to-previous is COVERED by the jingle push/pop model.

Open items this execution creates or leaves:

- **Game-side game-feel flows (spec §7 cookbook)** — act-clear sequencing,
  drowning panic tempo, 1-up jingle wiring, Start-menu pause-all: documented API
  flows consumed by game features (the screens/HUD package, design-week #7).
  Engine work is DONE; these are game-side callers. Owner: the screens/HUD
  package when it executes. Reference: the game-feel spec §7 + `sound_api.emp`'s
  transport/reader block.
- **Spec §6.4 DEBUG transport-exclusivity assert OMITTED (resident ceiling).**
  The both-slots-nonzero (`SND_REQ_MUSIC` + `SND_REQ_JINGLE` in one poll) DEBUG
  assert costs ~20 resident bytes; the debug blob ended 3 B under the `$18F0`
  ceiling. The 68k-side contract ("one transport op per frame") is documented at
  the wrappers. Revisit if a Z80 reclaim opens headroom.
- **Z80 resident headroom is nearly EXHAUSTED** — debug blob 6381/6384 after this
  package (plain 6255/6384). The next resident addition needs its own reclaim
  first (candidates: further init rolling, shared scan helpers). The R9 30 T-state
  bank is a TIME budget, untouched (banked for polyphonic PCM).
- **Fade default duration changed** (R4): the fastest rate is ±1 TL/frame → a
  full $7F fade is ~2.1 s (was ~1.07 s at the old STEP=2). All 8 authored speeds
  are slower-or-equal; if a sub-2s fade is ever needed the step magnitude (not
  the pattern) is the knob.

## Ledgered by the 2026-08-10 DAC drum-library-readiness package 3 execution (`sound-pkg3`)

- **`tools/test_import_sk_collision.py` regenerates committed collision bins
  IN-PLACE with bytes that differ from what is committed** (porter observation,
  reproduced across runs; the porter restored the committed bytes each time and
  committed nothing). Either the committed bake or the tool's default params
  drifted. Until reconciled, running the tools suite dirties the tree — a
  parallel-session hazard (auto-commit daemon could sweep the regenerated bins
  onto a branch). Owner: a small tools session — diff regenerated-vs-committed,
  decide which is truth, and make the test write to a temp path instead of the
  committed location.
- **Sigil table-fold vs placement divergence at unaligned bank-section base** —
  exposed by sound-pkg3's head growth (DacSampleTable 9→12 B/descriptor shifted the
  sound-bank tail parity): the placement chainer **8-aligns** the SFX block's
  section base, but seam-2's sound_layout fold (which bakes the absolute
  `SfxTable` pointer cells into `sfx_bank{,_debug}.bin` and the SfxBlobWinTab
  window pointers) packs contiguously WITHOUT that align — every pointer came out
  **-2** in the plain shape and SFX went totally silent (debug's base happened to
  stay ≡ 0 mod 8, so only plain broke, and no build gate fired). The quantum was
  pinned empirically: a mod-4-only pad still placed **-4** ($5BB0C fold vs $5BB10
  placed), and the old working bases $5BAE8/$5D558 are ≡ 0 mod 8 but ≢ 0 mod 16.
  Worked around by STRUCTURAL 8-alignment of the sfx_bank base via two
  comptime-sized pads inside the seam-2-lowered artifacts (so the fold and the
  chainer both count the bytes): the engine-table head is rounded to ≡ 0 mod 8 at
  its tail (`engine/sound/dac_sample_tab.emp` `DacHeadPad_*`, sized off the
  seeded DAC consts + the four fixed head sizes, walled in `soundbankhead.emp`
  incl. a head-total `% 8 == 0` tripwire), and the MT bank tail is rounded to
  ≡ 0 mod 8 (`games/sonic4/data/sound/mt_bank.emp` `_sfx_align_*`, sized off its
  own blob lengths, before SongTable so the pad lands in the body split-bin) —
  self-adjusting under head growth, song regen, and shape. Plus a link-time base
  wall in `games/sonic4/data/sound/sfx_bank_blob.emp`
  (`ensure((winptr(Sfx_33) & 7) == 0, …)` — placement-side only; the fold's base
  is not expressible repo-side).
  **Second finding, same session**: a source `align` CANNOT express this fix —
  seam-2 lowers these modules at baseline-0/vma positions that differ from final
  placement, so `align` computes the wrong pad count; its D2.29 link-time
  congruence assert catches it loudly ("padding was computed against the
  lowering-baseline address ... final address ..."), which is correct-and-loud
  but means `align` is unusable in any seam-2-lowered module whose placed base
  parity differs from its lowering baseline.
  **Needs a sigil-side fix**: either the fold must model the same alignment the
  chainer applies (and/or lower seam-2 modules at their true placed bases so
  `align` works), or a fold-vs-placement base mismatch must be a BUILD ERROR —
  never silent short pointers. The chainer's 8-quantum should also be stated
  somewhere authoritative instead of reverse-engineered. (Class risk: any OTHER
  seam-2 fold that bakes absolute addresses against a contiguous-pack model
  diverges the same way if its section gains chainer alignment.)

---

## Ledgered by the 2026-08-10 sound correctness-batch package 4 execution (`sound-pkg4`)

Package 4 (`plans/2026-07-03-sound-correctness-batch.md`) EXECUTED. Closed:
**D4** (PSG folds `sc_transpose` — the one live audible defect, byte-neutral),
**D1** (ModSet-on-noise refused in both producers, zero Z80 bytes),
**D6** (LoopPoint-in-repeat-span refused + a 4 B RepeatStart re-seed),
**D7** (DEBUG operand-0 trap, 0 release bytes, plus the missing SFX half of the
producer rule), **B3** (AM-enable bit lands on YM bit 7), **E5-runtime**
(RegDelta group 6 = `$90` SSG-EG, +1 B). Ride-along: **triage R1**, the DAC DRAIN
underrun guard (24 T / 6 B, zero net cycles). **B5 took the plan's own Step-2B
fallback** — see the costed finding on the B5 entry itself. Verification pass on
the plan's "already fixed" list: D2/D3/D5 confirmed done, F4 three-quarters done
and re-classified, F3 NOT closed (two thirds still unconfirmed).

Resident cost: plain 6157 -> 6164, debug 6283 -> 6294 of 6384 (headroom 101 ->
90 B), funded by the Task-0 item-25 reclaim. pytest 897 -> 912 passed / 2 skipped.

Open items this execution creates or leaves:

- **Blob length re-pin owed (controller).** Every package-4 build ran with
  `SIGIL_BLOB_LEN_DRIFT=warn`; `BLOB_LEN_PLAIN` / `BLOB_LEN_DEBUG` and the
  `Z80_SOUND_SIZE` mirrors still expect the pre-Task-0 6255/6381.
- **Oracle gates owed (controller, foreground).** (a) **D4** — force the
  spindash-rev SFX after several rev pings and confirm the PSG component's divisor
  writes now RISE with rev, as the FM component already did. (b) **R1** — if the
  underrun is reproducible (a long 68k DMA burst against a streaming sample),
  capture before/after: the ~72 Hz full-amplitude buzz should become a held level.
  (c) **Rendered A/B on BOTH the plain and debug shapes** — plain-shape SFX
  regressions have bitten this lane before, and D4 changes every PSG note-on.
  (d) Optional: the E5 group-6 SSG-EG showcase sweep.
- **`sfx_transcode._process_lines` is DEAD CODE.** Only `_process_lines_v2` is
  ever called (`_process_lines`'s single call site at its own `smpsJump` handling
  is a self-recursion). The two scans have already DIVERGED — v2 carries the
  `noise_form is not None` ModSet drop and v1 does not — which is exactly the
  hazard a dead twin creates. Package 4 did not delete it (out of scope) and
  closed the risk with a pack-time backstop instead. **Delete the v1 scan** in the
  next transcoder parcel; the divergence is evidence, not speculation.
- **`pack_sfx` does not validate events.** D7 surfaced this: `pack_sfx` calls
  `e.encode()` directly and never `e.validate(route)`, so EVERY `song_packer`
  range/route rule is silently inapplicable to SFX streams. Package 4 patched the
  two rules it owned (`_validate_sfx_repeat` count, `_validate_no_modset_on_noise`)
  but the general hole stands. **Audit which other `Event.validate` rules SFX
  streams need** and either route SFX through a validation pass or mirror the
  needed rules into the `_validate_*` backstops. Class risk: any future packer
  rule is assumed to cover both producers and does not.
- **`Fm_TransposeClampChrom` exists partly to route around a sigil limitation.**
  seam-1 resolves each resident module's constants from a per-module name list
  baked into the harness (`seam1.rs` `psg_const_names` / `fm_const_names` / …), so
  a `.emp` module cannot reference a `sound_constants.emp` constant that is not on
  ITS list, even though every constant is `pub` and evaluated. The D4 fix turned
  out better for it (byte-neutral, one shared clamp entry), but the constraint is
  undocumented and will surprise the next author. **Either document the per-module
  const seam in the engine/game contract reference, or make the lists derive from
  the modules' actual references.**

---

## Ledgered by the 2026-08-10 `characters.emp` module registration (`feat/character-dispatch`)

### Adding a module should not require editing the toolchain — SIGIL ASK, RECORDED (owner-raised)

**Raised by Volence 2026-08-10**, on discovering that moving the character roster into a new
`.emp` module required a commit to the *sigil* repo. The observation, in his framing: adding a
character "should really be as simple as making the new file and calling it where needed in the
actual game code."

**What it costs today.** Adding one module is three edits in two repos:

| edit | repo | correct? |
|---|---|---|
| the `.emp` file itself | game | yes |
| a row in `games/<game>/map.toml` `order` | game | **no** — ceremony |
| a `ModuleSpec` in `crates/sigil-harness/src/native.rs` `registry()` | **assembler** | **no** — wrong repo |

Pins and port tests are **not** in this path — verified this session: `characters` registered with
`DUMMY_REGION` and both shapes built green, because every shipped profile is `SizeSource::Frozen`
and `ModuleSpec.region` is read only from `emp_map_toml`, reachable only from `PinnedBaked`. So the
friction is the registry + the order list, not the pin table.

For a **brand-new game** it is worse: three *sigil* edits (a `GameProfile` literal, a registry
function, and a frozen size table under `crates/sigil-harness/golden/offcanonical_sizes/`). A third
party cannot build their own game on Aeon without committing to the assembler. That is backwards
and it undercuts the engine/game wall the 2026-07-07 split exists to enforce.

**The principle to design to: declare a placement REQUIREMENT, never a placement POSITION.**

Auditing `map.toml`'s ~60-entry `order`, the genuine requirements are about eight facts — object
code bank at `$10000`; the hard-org'd sound banks at `$8000`/`$58000` (the Z80 holds pointers in, so
they never pack); DAC banks at `$48000`/`$50000`; `error_handler` must be the final byte-emitting
section (MDDBG blob-end contract, `check_error_handler_is_last`); the OJZ act island runs stay
contiguous; `Vectors` at 0 and the header at `$100`. Everything else is arbitrary-but-deterministic.
Nothing breaks if `tails` lands before `sonic`; it only has to land *somewhere in the object bank*,
reproducibly.

**Sketch of the end state** — the file declares its own bucket:

```
module games.sonic4.tails in tails @ object_bank
```

sigil auto-places within the bucket in a stable order (sort by module id — stable across machines,
unlike a filesystem walk). `map.toml` shrinks to the memory map: regions, anchors, and the few hard
ordering contracts. You edit it when the *architecture* changes, not when content is added. Adding
a character becomes: write the `.emp`, add the roster row, build.

**Two dependencies that must land with it:**

1. **Inclusion must follow from use.** It cannot today, and this is the hidden reason the registry
   exists at all: cross-module calls resolve as **bare link refs**, so `player_common` calling
   `Player_LoadArt` creates no module-graph edge to `characters`. With no dependency graph to walk,
   `synthetic_entry_src` fabricates reachability by `use`-ing every registry row. Two ways out —
   make bare cross-module refs create real edges (proper dead-code elimination, larger job), or
   scope by directory (`engine/` + `games/<this game>/` are the link set), which is already the
   de-facto rule, just expressed in Rust (`demo_registry`'s `module_id.starts_with("engine.")`).
2. **Shape gating must move into the file.** Debug-only modules are excluded in Rust today, and
   `CODING_CONVENTIONS.md` §"Whole-file gating" is explicit that this is a workaround, not a
   preference: "a module-level comptime `if` wrapping items is not expressible in `.emp`, so the
   file is the gated unit and the exclusion happens in the build registry." Fix the expressiveness
   (`module … requires DEBUG`) and the last reason to open the Rust disappears.

**Known costs, to be priced in the spec, not discovered later:**

- Auto-placement can separate two hot mutually-calling modules far enough to widen branches. `jbsr`
  handles it correctly but spends bytes and cycles. Bucket granularity bounds it; a `near:` hint
  covers the rare case that matters.
- The frozen size tables are a *this-repo* byte-exactness gate, not something a third-party game
  wants. They should degrade gracefully: no frozen table means pure packed layout from the declared
  buckets, and freezing becomes opt-in. Today they are mandatory because sizes are sourced from them.
- One goldens refreeze when the placement algorithm lands. Not per content change — that is already
  true today.

**Treat as ONE design, not three.** The registry, the `order` list, and the frozen size tables are
the same mistake wearing three hats: the toolchain storing positions that should be derived from
declared requirements. K5 already did half of it (the map took `order` authority from the frozen
table, which was explicitly demoted to a "measurement cache"); this is the other half of that
migration, which was never finished.

**Status: NOT STARTED.** Novel, cross-repo, hard to reverse — wants an explicit owner go-ahead and a
written spec before any code. Parked 2026-08-10 at Volence's direction to keep C2/C4 moving.

---

## Ledgered by the 2026-08-10 per-slot player-state split (`feat/character-dispatch`)

### Hoist `Player_Quadrant` out of the sensor stack into a parameter — RECORDED, not fixed

**What:** `Player_SensorFloor` / `Player_SensorCeiling` / `Player_SensorSurface`
(`games/sonic4/player/player_sensors.emp`) read the probe quadrant out of ambient state rather than
taking it as an argument. Before C1 that was a global (`Player_Quadrant`); after C1 it is
`PBLK_QUADRANT(a4)`, the calling slot's PlayerBlock. Either way the dependency is **hidden**: the
wrapper's signature says `a0 = player SST` and nothing in the call expression says the caller must
also have established a4. The fix is to pass the quadrant explicitly (a register argument, or the
block pointer as a declared param) so the contract is on the signature where the compiler and the
reader can both see it.

**Why it is worth doing, beyond tidiness — the latent coupling it closes.** `TestPlayer`
(`games/sonic4/objects/test_player.emp`, DEBUG shape only) borrows `Player_SensorFloor` for its
floor probe. It is not a player, has its own overlay (`TPlayerV`), and wants plain quadrant-0
downward probing — but it has no way to *say* so. Pre-C1 it silently inherited whatever the real
player last wrote to the global, and got away with it only because the object-test scene never runs
the real player, so the boot-zero global happened to mean "quadrant 0". Had the two ever run in the
same scene, TestPlayer's floor probe would have rotated with the real player's terrain angle and
nobody would have suspected the sensor call. With an explicit parameter, TestPlayer states
quadrant 0 honestly and the coupling cannot exist.

**Why it was deferred.** The hoist changes the register contract of three procs that every player
frame runs through, at ~10 call sites in the hot path (`player_ground` ×3, `player_air` ×4,
`player_spindash` ×1, `test_player` ×1, plus the `Player_SensorSurface` fall-through). C1 Task 4
gates this refactor on the **real player being byte-identical under a recorded-input replay**, and a
contract change across the shared sensor stack underneath that gate would make a byte diff
impossible to attribute. Right idea, wrong moment — owner ruling, 2026-08-10.

**What was done instead (option 1 of the two considered):** `TestPlayer_Main` loads slot 0's block
into a4 before its `Player_SensorFloor` call, and says why at the `lea`. That is coherent rather
than a patch — `object_test_state.emp` installs TestPlayer in the `Player_1` slot, so slot 0's block
genuinely is its block. The alternative considered and **rejected** was having TestPlayer call
`Collision_ProbeDown` directly (as `Player_AtLedgeEdge` does): that is *not* behavior-preserving,
because `Player_SensorSurface` runs an **A/B sensor pair** at x±x_rad and keeps the closer hit,
while the bare core is a single centre point — collapsing a 32px-wide box's two foot probes to one
would change how it behaves straddling a ledge edge.

**Pick this up when:** Task 4's replay gate has passed and the byte-identity requirement is
discharged. It closes the last hidden dependency in the player sensor path — post-C1 the quadrant is
not a global any more, it is an *ambient register parameter*, which is why the compiler still cannot
see it. **Do not size this from this paragraph** — it is mechanical but it is not small; the
`MEASURED SCOPE` block immediately below is the estimate, and it concludes ~19 procs plus the
dispatch type, i.e. its own parcel with its own gate.

**MEASURED SCOPE (attempted and reverted 2026-08-10 — read this before estimating).** The obvious
first move is to declare the dependency on the four procs that actually read the quadrant
(`Player_SensorFloor`/`Ceiling`/`Surface` + `Player_SnapToSurface`), the way
`Player_RefreshPhysics (a2: *u8)` does. That was tried. It does **not** build, and the reason is
structural, not cosmetic: `[call.input-undefined]` fires **13 times**. a4 reaches the state machine
*implicitly* — `Player_Main` establishes it, then dispatches through
`jsr (a1,d1.w) as PlayerState`, and `type PlayerState` declares `clobbers(d0-d7, a1-a4)`. The
closure therefore treats a4 as destroyed at the dispatch boundary and cannot carry the definition
into any handler. The 13 firings:

```
Air_CeilingBump, Air_LandState, PState_AirShared,
PState_Ground, PState_Roll (x2)          -> Player_SensorCeiling
Air_FloorLandBanded, Air_FloorLandFlat,
Ground_PostMove, PState_Spindash         -> Player_SensorFloor
Air_TouchFloor, Ground_PostMove,
PState_Spindash                          -> Player_SnapToSurface
```

So the real change is not four signatures — it is an `a4` in-param on roughly **nineteen** procs
spanning `player_ground` / `player_air` / `player_spindash` **plus the `PlayerState` dispatch type
itself**, whose clobber list `Player_Main` brackets. That is the whole player frame's register
contract, which is exactly why it must not ride along underneath the Task 4 byte-identity gate: a
change that broad makes any byte diff impossible to attribute. Budget it as its own parcel with its
own gate. The partial form is not a valid halfway house — it does not compile, so there is no
smaller increment to land first.

---

## Ledgered by the 2026-08-10 Tails palette re-index (`feat/character-dispatch`)

### Knuckles is NOT solvable by index permutation — he needs a real palette swap — RECORDED, not fixed

**Read this before designing Knuckles' art path.** Tails' wrong colours were fixed by re-indexing
his S3K art into our CRAM line 0 ordering at build time
(`games/sonic4/data/characters_staging/gen_characters.py`, `remap_art_indices`). **That fix does not
generalise to Knuckles, and reaching for it will silently corrupt his colours.**

**The measurement.** Our player line is `art/palettes/SonicAndTails.bin`; S3K's is
`skdisasm/General/Sprites/Sonic/Palettes/SonicAndTails.bin` line 0. The two hold the *same colour
set in a different order* — 15 of 16 S3K indices match one of ours exactly. The exception is S3K
index **5 = `$0080`** (dark green), which our line does not carry at any index.

| art | S3K index-5 pixels | permutation lossless? |
|---|---|---|
| Tails body (`Tails.bin`) | **0** | yes — shipped |
| Tails appendage (`Tails tails.bin`) | **0** | yes — shipped |
| Knuckles (`Knuckles.bin`, contiguous `_opt`) | **3,450** | **no** |

3,450 pixels have nowhere to go. Any permutation either drops them onto a wrong colour or needs a
colour our line does not have — so the whole approach is off the table for him, whatever ordering is
chosen. This is not a tuning problem; it is a set-membership one.

**What Knuckles actually needs.** A genuine palette swap: S3K itself swaps `Pal_Knuckles` into
CRAM line 0 when Knuckles is the active character. Both his lines are already staged —
`games/sonic4/data/characters_staging/palettes/knuckles_main.bin` (gameplay) and
`knuckles_ssz_end.bin` (ending) — so the asset side is done; the missing piece is the runtime
decision about **who owns CRAM line 0** and when it is rewritten.

**The consequence that must be designed for, not discovered.** Line 0 is a *shared* resource. Today
it holds the Sonic+Tails colours and both characters render off it simultaneously, which is exactly
what a follower / 2P mode will need. Swapping `Pal_Knuckles` in makes line 0 Knuckles-only: **Sonic
and Knuckles cannot be on screen together on one line.** So the Knuckles design has to answer one of:
- **swap on character select** (simplest; forecloses Sonic-and-Knuckles co-presence), or
- **give Knuckles a second CRAM line** (costs a line the level art currently uses — measured: the
  OJZ act draws its FG on lines 2/3 and its Plane B on lines 2/3, with line 1 the OJZ page-0 line, so
  a fourth character line means taking one back from the level), or
- **re-author Knuckles' art** against a line that unions with Sonic's (an art decision, not an
  engineering one — it changes how he looks).

Pick before writing code; all three are cheap up front and expensive to retrofit.

**How to re-run the measurement.** The generator prints the derived permutation and per-set index
histograms on every run (`./gen_characters.py` from `games/sonic4/data/characters_staging/`), and
hard-asserts that no art it re-indexes uses an unmappable index. It deliberately does **not**
re-index Knuckles — see the comment at his `process_set` call.

---

## Ledgered by the 2026-08-11 Tails appendage object (`feat/character-dispatch`)

### ✅ RESOLVED 2026-08-11 — The appendage's angle-banked roll frames stay at bank 0 — BLOCKED on an engine arctan

**RESOLVED 2026-08-11 (`feat/character-dispatch`).** `GetArcTan` + `ArcTan_Table` shipped in
`engine/system/math.emp` (a faithful port of S3K `s3.asm:3174`, `preserves(d3-d4)`), and
`TailsAppendage_Main` now banks `mapping_frame` and re-derives the flip pair between the
`AnimateSprite` call and the DPLC. The four banks were confirmed present and distinct in the
converted data before the code was written — mapping frames 5-8 / 9-$C / $D-$10 / $11-$14, all 16
DPLC frames distinct, and the VDP size code changes $09 -> $06 between the horizontal and vertical
pairs, so they are genuinely different orientations and not a duplicated cycle.

**TWO CORRECTIONS TO THE ORIGINAL TEXT BELOW — it was wrong on the mechanism, and the error was
load-bearing enough to send a reader down a dead end:**

1. **"S3K's `GetArcTan` is a `$100`-byte table lookup" is FALSE.** It is a **257-entry ratio
   table plus TWO `divu.w`s** (`s3.asm:3193` and `:3202`). `ArcTanTable` is not indexed by x and
   y — it is indexed by the *quotient* `floor(min·256/max)`, so the table converts a ratio to an
   angle and the divide is what produces the ratio. A table lookup therefore does NOT make the
   routine division-free. The blob is 258 bytes: 257 entries (the index is an inclusive quotient —
   equal magnitudes divide to exactly `$100`) plus one even-pad byte.
2. **The rejection of the octant approximation was RIGHT, and now has a number behind it.** The
   ledger rejected a `tan(22.5°) ≈ 7/16` threshold as "not S3K's rounding". Correct:
   `tan(22.5°)·256 = 106.04`, but the table's own crossings are at **q = 103** (entry 15 -> 16) and
   **q = 110** (16 -> 17). A trig-derived threshold of 106 sits between them and disagrees with S3K
   on real inputs.

**A PROVEN-EXACT SHORTCUT EXISTS AND WAS DELIBERATELY NOT TAKEN — do not "discover" it again
without reading this.** The appendage keeps only bits 5-7 of the biased angle (`(a>>3)&$C` is bits
5-6, and the `bpl` flip test is bit 7), i.e. a 45°-sector classifier with a 22.5° offset. Because
`ArcTanTable` is monotonic, each sector boundary is exactly a threshold on the quotient, and
`floor(min·256/max) >= k` is exactly `min·256 >= k·max` — a multiply, not a divide. Deriving the
two `k` from the TABLE rather than from trigonometry makes the result bit-identical by
construction. This was verified, not assumed: **3.77M inputs (all of `|x|,|y| <= 600`, 600K random
full-int16 pairs, every quotient 0-256 at 14 scales, and the exact crossing rows ±1 at ~3000
scales) produced ZERO disagreements** with the full S3K pipeline, filling all 32 classifier
entries. The both-zero case does *not* fold in (it collides with the near-45° key and needs its own
test, exactly as S3K's `GetArcTan_Zero` does).

It was rejected on **measured cost**, not correctness. From the 68000 manual, over the code each
form actually emits: faithful `GetArcTan` + transform = **498 cycles**; the classifier =
**327** multiply-free, **291** with `mulu.w #k`. That is 1.5x, not the ~3x a bare `divu`-vs-`mulu`
comparison suggests, because the classifier must reconstruct by hand all the sign and octant
bookkeeping the fold does implicitly — a saving of **171-207 cycles, ~0.13-0.16% of one NTSC
frame**, on a path that runs once per frame and only while Tails is rolling. Against that it costs
two magic constants that encode the table's ROUNDING (silently wrong if the table is ever
regenerated), a 32-entry classifier table of its own, and it still needs a `mulu` exception unless
you pay 88 cycles for a shift/add chain — so it does not escape the convention question either.
The full derivation, the 32-entry table, and the verifier are recoverable from this entry's
description if the tradeoff is ever re-opened.

**Original entry, preserved:**

`games/sonic4/objects/tails_appendage.emp` ships S3K's tail behaviour with one frame-selection
detail missing, and it is missing because a primitive does not exist yet — not because it was
skipped.

**What S3K does.** When Tails is in ball form his tails render from one of FOUR angle-banked mapping
banks (`AniTails_Tail03`/`04`/`05`/`06` — the same 4-frame cycle drawn at four orientations). The
selection is `sonic3k.asm:29556` (`loc_15A3C`): take the PARENT's `x_vel`/`y_vel`, run them through
`GetArcTan`, mirror the result on the facing bit (`not.b d0` facing right, `+$80` facing left), bias
by `+$10`, then `lsr.b #3` / `andi.b #$C` to get 0/4/8/$C and ADD that to `mapping_frame` after the
script step. The same angle also drives a two-bit render_flags flip.

**What we ship.** `Ani_TailsAppendage.Roll` carries bank 0 (tails_anims.emp deviation 3 says so
explicitly and assigns the offset to the appendage object), and the object does not add anything, so
a rolling Tails' tails spin at the horizontal orientation regardless of travel direction.

**The blocking dependency.** `engine/system/math.emp` is sine/cosine only — there is no arctan
anywhere in the engine (`GetSineCosine` + `Sine_Table` are the whole module). S3K's `GetArcTan` is a
$100-byte table lookup. An APPROXIMATION is available (classify the octant from `|dx|` vs `|dy|`
against a `tan(22.5°) ≈ 7/16` threshold, which is all `>>3 & $C` actually extracts) but it is NOT
S3K's rounding, so it would ship a visible-frame difference against the reference we are measuring
against, and it cannot be A/B'd against S3K without the real table.

**What closing it looks like.** Add `GetArcTan` (table + lookup) to `engine/system/math.emp` as its
own parcel — it is a general primitive several systems will want (projectile aiming, slope-facing
objects, the classic `CalcAngle` the air-state quadrant comment already name-checks) — then the
appendage change is ~10 instructions in `TailsAppendage_Main` between the `AnimateSprite` call and
the DPLC: bank the mapping_frame and re-derive the flip pair. The flight ascend/descend hold, the
OTHER thing tails_anims.emp assigned to this object, is already shipped (DUR_DYNAMIC + the parent's
`y_vel` sign).

### The `mulu`/`divu` convention text and the shipped code disagree — needs a ruling

`CODING_CONVENTIONS.md:247` states the rule absolutely:

> **Rule:** No `mulu`/`muls`/`divu`/`divs` in any code that runs per-frame. Use shifts, adds, or
> lookup tables. The ONLY exception is code that runs once (level load, init).

Two shipped sites are per-frame divides, and neither is "code that runs once":

| Site | Instruction | Why it is there |
|---|---|---|
| `engine/level/parallax.emp:548` | `divs.w d4, d2` | ramp step = `(target − current) / frames_remaining`, so a band transition converges exactly on its last frame. Runs every frame a transition is active. |
| `engine/system/math.emp` `GetArcTan` | `divu.w` ×2 | the arctan table is indexed by the RATIO, so the divide is what produces the index. Runs once per frame while Tails is rolling. |

Both carry a block comment proving the divisor is never zero and the quotient cannot overflow, so
the *practice* looks like **"not casually, and prove the invariants at the site"** rather than the
blanket prohibition the text states. That is a real gap between the law and the code, and the two
are not reconcilable by reading.

**This is a decision for the user, and is deliberately NOT resolved here** — amending
`CODING_CONVENTIONS.md` as a side effect of a feature parcel is exactly the kind of quiet
law-change that should not happen. The options are:

1. **Amend the text** to match practice: divides are permitted where an exact result requires one,
   provided the site documents divisor-non-zero and no-overflow. Both sites already comply.
2. **Keep the text absolute** and mark these two as named, listed exceptions (the text would need
   an exceptions register, since "the ONLY exception is code that runs once" currently excludes
   them).
3. **Remove the divides.** Costed for `GetArcTan` in the entry above and rejected: the divide-free
   form is provably exact but buys only ~0.13% of a frame while adding two rounding-derived magic
   constants — and it needs a `mulu`, which the same rule forbids, so it does not even resolve the
   discrepancy. Not costed for `parallax.emp`.

Note that option 3 does not generally escape the rule: for both sites the divide-free alternative
is a *multiply*, which sits under the same sentence.


### VRAM linker T1 — the packer in sigil's chainer (spec §6)
**Blocked by:** nothing technical; queued behind the T1 plan being written.
**What:** the six sigil asks from `docs/superpowers/specs/2026-08-11-vram-linker-design.md` §6: S-1 vram.toml parser in the harness, S-2 the solver (FFD + lifetime stub + exact fallback, with the fixpoint acceptance test: given the pinned map, reproduce it), S-3 define emission — VRAM names join `emp_defines`, replacing the hand ring-placeholder values across the native.rs profiles (MUST land value-neutral, byte-identical goldens as its gate), S-4 the no-raw-literal lint, S-5 map/budget/diff artifacts + refreeze integration, S-6 (T2) per-act solve outputs.
**Also ledgered with it:** the art_tile hash normalization rider (spec §12 — one re-stamp, unpins the character window for T1 floating); the possible vram.toml/map.toml merge when the user's broader TOML review happens (their stated intent, 2026-08-11).
**When ready:** after the T0 execution note and the T1 plan (task queued).

### Dust plan Task 2 — SUPERSEDED by the VRAM registry carve
`docs/superpowers/plans/2026-08-11-dust-effect.md` Task 2 (the hand
POOL_TILE_CEILING carve) is superseded by the registry
(`games/sonic4/vram.toml`, commit c51a4ff9): VRAM_DUST_PUFF/VRAM_DUST_SPINDASH
now exist from the generated block. Dust Tasks 3-6 resume unchanged otherwise.


### Dust riders (plan Task 6, 2026-08-12)
1. **Knuckles dust art variant** — a second, RAW (unpermuted) 2816 B blob
   selected at Player_RefreshPhysics alongside his palette swap, which must
   also re-DMA the resident puff block (it is palette-specific). Measured: no
   single variant serves both CRAM lines — the three colours the art needs sit
   at disjoint indices, and the lines agree only at 0/10/11, none used by dust
   (dust spec §5.4).
2. **Water splash / water-run dust** — a design task gated on a water system
   existing at all (dust spec §1; no ST_UNDERWATER implementation today).
3. **TF4 round-robin misattribution** — docs/ENGINE_ARCHITECTURE.md (~1118,
   1165, 1955, §3.5) and docs/research/children-particles.md:166 credit
   Thunder Force IV with "round-robin sprite flicker" at $F29A. Verified from
   its disassembly: that address is a global Y-drift accumulator; TF4 has no
   such mechanism, and the doc's claimed TF4 RAM pools are palette/tilemap
   staging. Our per-frame intra-band link-order cycling (sprites.emp:242) is
   real — only the provenance is wrong. Correct in one docs pass.
4. **particle_anims.emp:17 duration comment** — says "duration 4 frames/frame";
   under animate.emp's N+1 rule a duration byte of 4 holds for 5 frames.
5. **Hoist the shared S3K sprite conversion** out of gen_characters.py /
   gen_dust.py into tools/s3k_sprites.py — deferred while gen_characters.py is
   load-bearing on two branches (dust plan, File Structure note).


## Ledgered by the 2026-08-12 Knuckles C4 task 9 + research (`feat/knuckles`)

### The ability collision box does not compose with the enter hooks — BLOCKING Task 10, not yet fixed
Glide, slide and climb all run at 10x10 radii (S3K `sonic3k.asm:32566-32569`) — a
THIRD collision box beside standing and ball, and our box machinery only knows
two. `PHook_EnsureStanding` (`player_common.emp:1014`) keys on `cd_roll_wh`, so
coming from a 21x21 ability box it takes `.keep` and **never restores the
standing box**; `PHook_EnsureBall` (`:1027`) applies the full stand-to-ball
`curl_y_shift` that S3K's wall jump-off does not have (`:31430-31431`). So a
glide or climb detach would leave Knuckles with a 21x21 hitbox for the rest of
the act, and every wall jump-off would drop him 5 px.

Fix (designed, not built): a third registered box `cd_ability_wh` in
`CharacterDef` at `$24`, a `set_ability_size` splice, a `PHook_EnsureAbility`,
and generalising EnsureStanding's guard to "am I not the standing box" with the
y shift derived from the CURRENT height. That closed form is literally S3K's
`y_radius - default_y_radius` and reproduces today's numbers exactly (ball 5,
ability 9 — and 9 is what S3K's slide get-up applies). Sonic and Tails come out
behaviour-identical; ROM changes, RAM does not.
→ §0 of `docs/superpowers/2026-08-12-knuckles-c4-research.md`

### The plan's Task 10/11 text has ~12 substantive errors — CORRECTED IN PLACE
The plan now carries a banner at each task pointing at the research. The ones
that change what gets built: the slide dust cadence is 4, not 8 (8 is the SFX
cadence); the fall-from-glide needs its own PSTATE rather than being a
sub-state; glide needs its OWN terrain pass because `Air_Collide` tail-jumps
into `Player_SetState`; there are three climb detach conditions, not two.

### Task 11 Step 1 is DONE, and the answer is "no sensor work needed"
`player_sensors.emp` already takes fully arbitrary probe points, so the
S3K-to-ours wall-detection mapping the plan calls "the hard part" needs no
extension. The full equivalence table is banked. One genuine gap remains
recorded: the glide wall-catch needs "both sensors flush" and
`Player_SensorPair` returns the NEARER hit — answer is to call the probe cores
twice, the idiom `Player_AtLedgeEdge` already documents.
→ §2 of the research doc

### Glide/slide/climb SFX do not exist in our bank — SCOPE DECISION OWED
S3K uses `sfx_GlideLand $4C`, `sfx_GroundSlide $7E`, `sfx_Grab $4A`. Our SFX
bank has none of them, so Task 10/11 either opens a sound-side parcel (bank
entry + priority-ladder row each) or ships the abilities silent. The plan is
silent about being silent. Same class as, and can ride with, the flight-SFX
range work if that is still open.

### S3K's `Disable_wall_grab` has no counterpart — object-side hook, RECORDED
Two S3K gates (`:30777-30778`, `:31039-31040`) let specific walls refuse a
grab. We have no equivalent, so every wall will be climbable. Register the
object-side hook when the climb lands rather than losing the capability.

### `knux_latch_x` will need the floating-origin shift-list — NOTE AT THE FIELD
The climb latches a WORLD X to detect being pushed off the wall. When the
floating-origin rebase lands, that cell must join the rebase shift-list or every
rebase mid-climb trips the drift guard and drops Knuckles off the wall. Same
class as the `Player_Pos_Ring` note in plan Task 8. Put the note at the field,
not only here.

### `PlayerV` header comment says "22 of 30" and is stale — it is 20 of 30
`player_common.emp:78`. (Plan Task 12 Step 1 already lists a DIFFERENT stale
figure, "18 of 34", whose text no longer exists at the cited line.) Fix in
whichever task gets there first.

### The `.emp` language cannot express the ability-scratch UNION — SIGIL ASK, RECORDED
`player_common.emp:104-110` states the design intent that Knuckles' ability
bytes re-use Tails' `fly_fuel`/`fly_thrust`, since exactly one character is
resident per slot. The language has no way to say it: every
`vars X: Sst.sst_custom` overlay in the tree starts at `$30`, none uses
offset-anchored placement, and both characters share the single `PlayerV`
overlay. Costs 2 bytes of a 30-byte window today (26 of 30 after climb), so it
is not urgent — but the comment should be amended to read as a BUDGET principle
rather than a byte-sharing one until the language grows an offset-anchored view.

### The ROM-tail character-art exile has now happened TWICE — relayout pressure
Knuckles' 0x226C8 of art took the same exile Tails' 132 KB took, for the same
reason (Art_Sonic ends at $4277E, the `dac_banks` org anchor is at $48000). The
plain ROM is 676 KB against 414 KB before Tails, and each exile costs a
frozen-table hand ruling in five shapes. The parked "banks late, data unbounded"
relayout retires the whole friction class; a fourth character, or any further
character-scale art, pays the tax again.

### Palette variant DEBUG guard — CONSIDERED AND BANKED, not an oversight (2026-08-13)
`fix/palette-variant-derive` gated the variant derive on `PAL_ACT_VARIANT_STALE`,
which makes "the palette engine is the sole runtime writer of `Palette_Buffer`
lines 1-3" a CORRECTNESS dependency rather than a tidiness one: an outside
runtime writer of those lines would leave `Pal_Variant_Stage` stale with nothing
to notice. A DEBUG-only guard was designed (checksum the `v_lines` bytes at
derive time, re-check on a skipped frame) and deliberately NOT built.

The audit that made it optional — every writer of `Palette_Buffer` in the tree:

| Writer | Lines | When |
|---|---|---|
| `player_common.emp:517` character resolve | **line 0** | **every frame** |
| `ojz_scroll_test.emp:112` BGND | line 0 | init |
| `ojz_scroll_test.emp:119` OJZ_Palette | **lines 1-3** | init, before first compose |
| `ojz_scroll_test.emp:390` backdrop tint | line 0 | runtime |
| `object_test_state` / `demo_state` | line 0 | init |
| `palette.emp` compose layers | lines 1-3 | per frame |

So today the invariant holds: the only non-engine writers of lines 1-3 are
init-time (and covered anyway, since binding sets the stale bit), and every
runtime outside writer touches line 0, which no variant can cover (`v_lines` is
bits 1-3 by construction).

**If the guard is ever built, it must cover ONLY the `v_lines` lines.** A
whole-buffer checksum fires on every character resolve — a guard that cries wolf
each frame gets deleted, and takes the real invariant with it. Cost if built: one
debug-only RAM cell (moves debug pins) plus ~400 cyc/frame in the debug shape.

### Palette variant LUT (design lever C) — deferred until real content exists
Lever A took the STATIC-frame derive to zero, but a frame whose source actually
moved still pays the full **19332 cyc** (48 entries at ~403, measured) — 3 lines
x 16 entries, each doing three variable-shift + branch-clamped channel rebuilds
with six loop-invariant descriptor bytes re-read from memory per entry.

The fix is not another gate, it is the arithmetic: each channel is 3 bits, so
build three 8-entry word tables at BIND time, pre-shifted into channel position
(`clamp((c >> shift) + bias, 0, 7) << {1,5,9}`). 48 bytes per slot. The inner
loop becomes three extract-and-index sequences plus two `or`s — est. 3-4x. This
is the house idiom (CODING_CONVENTIONS: tables over runtime arithmetic), and
`variant_word(c, v)` already exists as a `comptime fn` computing exactly this
mapping, so the builder can be gated at build time against its `ensure` vectors
rather than tested by hand.

Deferred because the only scene that exercises it has no continuous cycling, so
any measurement today would be on a garish test fixture rather than real content
— the same caveat that already qualifies the dense-tier reserved-register ruling.
Revisit when a section runs cycling or a fade continuously.

### ~~The DRY direction of a patch channel — blocked on Ristar's linked-list schedule~~ — CLOSED 2026-08-16

**Closed by:** the HInt schedule local-removal parcel. `Raster_PatchAll` (in-place, one arm BYTE
patched per record per VBlank) is replaced by `Raster_BuildSchedule`, which RE-RECORDS the whole
schedule each VBlank from the ROM template into the INACTIVE raster buffer — copying only the
records that are live this frame — then swaps `Raster_Active_Buf`. A record is removed by simply
not copying it, which is the local edit the array-of-relative-gaps encoding could never express
through an in-place byte patch: an arm word can MOVE a boundary but a record is only left behind
by having been walked, and the old patcher never controlled the walk. `Raster_HInt` itself is
byte-for-byte unchanged, so this costs zero added HBlank cycles — the reason this shape was chosen
over porting Ristar's per-record linked-list schedule (`ristar_disasm/code/disasm.asm:14556-14595`),
which would have cost roughly 12 cycles of a ~60-cycle HBlank budget on every fire, forever, not
only the ones that get suppressed.

**The suppression rule:** `L > band_hi` (screen space) — past the record's authored band, the
record is not emitted at all this frame. Applied identically by `Raster_BuildSchedule` and by the
parallax overlay (`engine/level/parallax.emp`), both reading the same two band words through
`Raster_GetChannelBand`, so the palette boundary and the scroll boundary agree in every anchor
state rather than merely clamping the same way. Below `band_lo` the record still CLAMPS UP —
that direction stays a clamp, not a removal, because the frame-top ship (the previous parcel,
2026-08-15) already covers the rows above with the fire's own colours when the anchor reads
`L <= 0`; clamping up hides nothing there, where clamping down used to paint a lie.

**RESIDUAL:** for `band_hi < L < 224` the boundary now renders NOWHERE rather than pinned near the
screen bottom — the record is suppressed, so the affected rows show whatever the underlying art
already draws (dry), when the world says the boundary should still be visible there. This is
inert rather than wrong-in-the-visible-sense (a row that should be wet renders dry, never the
reverse), but it is not a true fix — it is the residual DEFERRED_WORK originally described,
narrowed by re-banding the OJZ fixture from `3..120`/`130..200` to `3..220`/`222..223`. Worst-case
dry-side error fell from ~10 rows to ~3 (`games/sonic4/data/effects/ojz_effects.emp`, search
`OJZ_TwoChannel`). Fully removing the residual still needs a record whose band reaches all the way
to the screen bottom with no channel sharing the tail of the screen — a content/authoring question
now, not an encoding one.

---

**Original entry, kept for provenance:**

**Surfaced during:** the off-screen frame-top ship parcel (2026-08-15). That parcel fixed the
direction where a patch channel's anchor leaves the TOP of the screen; this is the other one.

**What is wrong:** `Raster_PatchAll` CLAMPS a patchable fire's line into the record's authored
band rather than suppressing it, so when the anchor falls BELOW the screen bottom the fire pins
at `hi` and paints up to ~10 rows that the world says should be dry. Measured on OJZ after the
re-band; it was 72 rows before it.

**Why the clamp cannot simply go:** a sub-band fire line yields a negative inter-record gap,
which stores as `$FF` — and `$8AFF` is the park word, so it would kill every remaining fire in
the frame. The clamp is load-bearing.

**Why the top-of-screen fix does not mirror.** Above the screen, the answer was to ADD a
frame-top DMA covering the whole screen — the fire keeps running and simply writes what is
already there. Below the screen there is nothing to add: the fire has to STOP, and Aeon cannot
park one record without killing the tail, because arm gaps are RELATIVE.

**The unblock is Ristar's encoding**, and it is recorded as the bigger prize in the same work
order: each node writes its own gap AND its own successor
(`ristar_disasm/code/disasm.asm:14556-14595`), so removing a node is a LOCAL edit. Ristar runs
two independently armed effects off one chain with separate thresholds, a disarmed one costing
interrupt entry + `tst`/`beq`/`rte` (~40 cycles) instead of its payload. Sonic 2 clamps exactly
as Aeon does (`s2.asm:5280-5292`); S3K and S.C.E. deliberately changed it to disarm.

**Until then the parallax side clamps the SAME way on purpose** (`parallax.emp`, the
`cmpi.w #224` branch). Fixing only the scroll boundary would trade a consistent 10-row error
for a 9-row DISAGREEMENT between the palette and scroll boundaries — which is the exact defect
Parcel W exists to remove. Do not "fix" one side alone.

---

## Ledgered by the 2026-08-17 Parcel R1 Task 8 review batch (`feature/parcel-r1-palette-bands`)

### R1 follow-up: RasterOp.Cram/PalRestore direct construction bypasses C-D's wrap/line-0 refusals — RECORDED, not fixed

RasterOp.Cram/PalRestore direct construction bypasses C-D's wrap/line-0 refusals (constructor-only
refusals are not refusals — the $8F/$8A precedent); needs an op-level span scan in
`raster_program`; found by the Task 8 review, booked not built.

## R1 §7.3 measurement 2 — the +16 mixed-fire landing (booked 2026-08-17, Fable-ruled)

The RUNGS 4→5 dispatch tax is hardware-confirmed exactly +16 (F5 = 628.0, spread 0); its
PIXEL-LANDING consequence on the shipped water fire is UNMEASURED — four capture protocols
have now failed their own controls (the record: docs/benchmarks/effects-r1/GATE-EVIDENCE.md
§7.3-2). Re-measure ONLY with the render-anchoring parcel's framediff instrument
(docs/superpowers/2026-08-18-oracle-render-anchoring-brief.md), with ALL of:
- pinned camera AND Logic_Tick controlled (or anchored out by the instrument);
- the boundary row re-derived at the capture camera (`Effects_Screen_L` ch 0) — the P2
  baseline rows 118-120 are camera-stale, do NOT reuse them;
- expected-harmless: seam drift ~14-15 px right; failure: tint spill into the visible row.
On a measured failure: the §3.3 fallback slot is VACANT and the OWNER re-rules (per-fire
delay word / stream-count narrowing / accept-if-sub-pixel). Never retune EFX_BLANK_DELAY.

## CLAIM 7-N1 — a comptime-enforcing committer contract IS implementable in sigil (booked 2026-08-17, R1 Task 14)

The two halves exist: z80_bus.rs keys diagnostics on resolved destination-operand symbols
(is_vdp_write), and the context system propagates requires()/grants() per proc. A
[palette.unregistered-committer] contract is the same machinery with a symbol allowlist.
THE TRAP that makes this a claim, not a task: is_vdp_port punts on register-indirect
operands, and every real Palette_Buffer writer goes lea+(a1)+ — a store-keyed contract
catches ONE writer of ten (textbook vacuous gate). The non-vacuous form flags SYMBOL
REFERENCES (lea/abs/extern), which also flags readers and needs an allowlist — that trade
needs a sweep. Until then: the advisory census (buffers.emp) + the reference-count lint
(tools/test_palette_census_lint.py) are the floor, and both are red-first-verified.

## R1 booking: N bands (more than one restore per program)

Parcel R1 shipped exactly one band per program (`docs/superpowers/specs/
2026-08-16-parcel-r1-palette-bands-v6.md` §1, §9) — `raster_program` refuses a second
`OP_PAL_RESTORE` outright. The blocker is representational, not a guard tweak: the
composition guard (C-A, §4.2) and the single-op-restore-fire guard (D-B, §4.2a) both reason
in the singular — "the restore," "its partner," "the restore's line" — because with one
restore, ownership of a CRAM span between an ON fire and its OFF fire is unambiguous. With
two+ restores in one program, a second band's ON op and OFF edge cannot be checked against
each other by span alone once two restores compete for the same partner candidates (the
equal-span-partner guard as written cannot disambiguate which restore owns which ON op).
N bands need an **entry-ownership representation** — each restore record naming which ON
record it closes, rather than the guard inferring it from span equality and fire order —
before the guard set generalizes past `restore_n == 1`. Until that representation exists,
the equal-span-partner guard is single-restore by construction, and adding a second band is
a refusal, not a silent bug.

## R1 booking: moving bands (patchable ON and/or OFF edges)

Both directions are explicitly refused by rule 6 (CLAIM E-A, spec §4.2): a band's ON fire
and its restore (OFF) fire must BOTH be static (`fire_is_patch == 0`). Sweep 5 found the
open door by splicing `band()`'s restore fire into `patchable(...)` — every existing guard
passed, and above `band_hi` the record hit `raster.emp:1083`'s `.suppress` path and was
silently dropped: the tint ran to the bottom of the screen rather than turning off where
authored. Rule 6 closes both spellings that reach `.suppress` — compose-merging `band()`'s
fires onto a patchable line, and list-indexing a band fire into `patchable(...)` directly
(via `band()` the partner is always its own ON op, so there is no third spelling) — and both
are now guard-refused at build time, not merely undocumented.

**The blocker is the same representation question as N-bands, not a separate one.** A moving
band needs the restore to track its partner's *current* line every frame (the ON fire may be
patchable, the OFF fire may be patchable, or both), which is exactly the entry-ownership link
N-bands need to disambiguate "which restore closes which ON" — a moving single band is the
N=1 case of the same missing mechanism. When this is designed, **rule 6/E-A is the seam to
reopen**, and sweep 5's `.suppress` trace (`engine/effects/raster.emp:~1083`, the schedule-
recording path that drops a record outside its authored band each VBlank) is the hazard
analysis record the design inherits — any relaxation of rule 6 must re-derive why a suppressed
partner or a suppressed restore can no longer desync silently, not merely re-permit the
spelling.

## Effects tail Part A — runtime patchable-overlap resolution (BANKED 2026-08-17, owner ruling: demand-pull)

**What it is**: two patchable raster channels may overlap bands / traverse the whole screen;
collisions resolved at runtime by a main-loop resolver (authored-order priority, push ≤
spacing on near-collision, suppress on genuine inversion) publishing into a double-buffered
per-channel bank. Deletes `check_intervals`' disjointness wall for patchable-vs-patchable
pairs ONLY — statics stay sacrosanct via a symmetric comptime scan (G-A3).

**State: design COMPLETE and three-times-swept** — r1 → sweep 1 (26 findings) → r2 → delta
sweep (20 findings, incl. two latent regressions and a value-proposition inversion) → r3 →
mini-sweep (12 findings, incl. the `resolved_rec[]` stale-slot divergence) → **r3.1, fully
adjudicated, zero open mechanisms**:
- design: `docs/superpowers/specs/2026-08-17-effects-tail-design-v3.md` (r3.1)
- adjudications: `docs/superpowers/2026-08-17-effects-tail-sweep-adjudication.md`,
  `…-delta-adjudication.md`, `…-mini-adjudication.md`
- the D1-1 install window is MEASURED on the shipped build (3/3 crossings, no VBlank —
  latent, phase-deterministic; the atomic-publish fix is in r3.1 regardless)

**Why banked, not shipped** (owner sign-off 2026-08-17): for shipped OJZ content the parcel
only swaps which effect is absent in screen rows 221-223 (tint vs vscroll split — a one-line
content edit either way); its real payload — general two-channel freedom — had no authored
consumer yet, and unshipped collision arms would be gate-exercised only (dormant-scaffold
rule). **Revival condition: a real program that needs overlapping patchable bands** — the
expected one is the Parcel D OJZ showcase (Aurora-authored multi-band). Revival cost is one
plan+execute session against r3.1; the plan-facing surface (atomic landing cluster, +2 table
readers, sigil cross-seam hand-edits, 18-byte RAM, poison list) is already enumerated in
r3.1 §A5/§A7.

**Breadcrumb placed at the failure site**: `check_intervals`' ensure message and comment
block (engine/effects/raster_dsl.emp, GUARD 2) now point here and at r3.1 — a future author
hitting the overlap build error lands on this trail. DO NOT relax the guard ad hoc; three
adjudications exist because every naive relaxation was proven unsound.

**Part B (VSRAM op-class split) is separately banked inside r3.1** — net +26 cyc/op loss
today, payoff gated on an instrument that can bind mid-frame VSRAM visibility to hardware
(none exists; the emulator-model known-unknown is recorded in
`2026-08-14-vsram-planeb-handoff.md`). Its revival conditions live in r3.1 §B.

---

## ojz_run_b port tests — CLOSED 2026-08-19 (owner-ruled, fixed harness-side)

**CLOSED same day it was triaged.** Owner ruling (morning 2026-08-19): fix harness-side —
`BG_LAYOUT_SIZE` already lives engine-side (`engine/level/bg.emp:51`) and is engine-fixed
geometry (the full 64×64 Plane B nametable), not per-game, so nothing relocates. Sigil
`ae7212a6` (merge `4af3f7d6`) extends the `cd5cb646` synthesized-dep idiom: a new
`emp_const_rhs` helper copies the RHS **text** (`64*64*2`) verbatim into a synthesized
`engine.bg_layout` module, so sigil's comptime folder does the arithmetic and no value is
written down in Rust (poison: forcing 4096 fails both tests at lower, named). Both tests
green with ZERO re-baselining — their region assertions passed against the current goldens
on first compile. Full sigil suite: **3733 passed / 0 failed** — fully green for the first
time since the booking. Note the two tests skip unless `SIGIL_STRICT_GATE=1` and the aeon
ROMs exist; the targeted verification ran strict.

The original booking follows for the record:

## (record) ojz_run_b port tests were RED on master — pre-existing, unowned (found 2026-08-19)

`ojz_run_b_regions_match_reference` and `ojz_run_b_debug_regions_match_reference` in
sigil (`crates/sigil-cli/tests/ojz_run_b_port.rs`) fail with
**`unknown name BG_LAYOUT_SIZE`**.

**Cause, and it is not the test's fault.** `games/sonic4/data/levels/ojz/act1/act_assets.emp`
gained `use engine.bg.{BG_LAYOUT_SIZE}` in **5519ea54** ("guard the two silent cliffs — DPLC
tile_start and the BG blob size"). `ojz_run_b_port` lowers a **single module in isolation**
(`lower_module`, no dep list — by design, so the region comparison is not polluted by other
modules' bytes), so a cross-seam import in the module under test has nothing to resolve
against and the test cannot even compile its subject.

**Verified pre-existing**, not caused by the raster-substrate parcel: `act_assets.emp` at
`4452284b` (the pre-merge master) already carries the import.

**This is the `reference_sigil_port_flip_ritual` trap for the third time** — a new
cross-seam ref breaks `*_port` tests silently, `build.sh` stays green, and only
`cargo test --workspace --no-fail-fast` sees it. The substrate parcel hit the same trap
itself (five failures from importing `VDP_REG_0C_BOOT` out of `boot_data`) and fixed it by
moving the constant into `engine.constants`, which every port harness already depends on.
**That is likely the fix here too** — but `BG_LAYOUT_SIZE` is a genuine `engine.level.bg`
concept, not a stray constant, so the call is whether to relocate it, teach the harness a
companion module, or supply it through `LowerOptions.defines`. Not ruled; left for whoever
owns 5519ea54.

**Do not re-baseline around it.** The test is failing because it cannot build, not because
a number moved.

## Raster substrate lens sweep — 7 confirmed defects awaiting a parcel (booked 2026-08-18)

**Packet:** `docs/superpowers/2026-08-18-raster-substrate-sweep-adjudication.md`
(+ `…-packet.jsonl`, 16 seats raw). Review SHA `48ca8b5d`. 15 seats, 117 raw findings
(31 major / 51 minor / 35 note), overseer-verified; **one major REFUTED** (see below).

**Charter:** sweep the substrate scanline-services P1 freezes as its byte-identity baseline.
**Parallax walker + fill internals were EXPLICITLY OUT OF SCOPE** (P3 rewrites them); `bg_anim`
was in scope. So this sweep says nothing about the parallax config records P1 re-authors —
neither clean nor dirty, just unexamined.

**None of it is in P1's removal set.** P1 deletes only `games/sonic4/data/parallax/`; every
subject here (`raster.emp`, `raster_dsl.emp`, `palette.emp`, `buffers.emp`, `bg_anim`, `tools/`)
survives untouched, so no finding expires.

### LANDED 2026-08-18 — the zero-byte subset (branch `feature/raster-substrate-fixes`)

**Item 6 — CLOSED 2026-08-18, and the constant it left unverified turns out to be CORRECT.**
`effects_gates.py`'s cost gate now names **F4** in its `--only` list, with the expectation
computed from the shipped constants like every other row (never typed in):
`fire_region = base + fetch + rung + hit + REGION + 3*word + tail`, `expect_f4 = f0 + 6*fire_region`.

The **first ever hardware measurement** of that fixture (s4.debug.bin `ab1055d4`):
**F4 = 3968 cyc/frame, 566/fire** — matching the computed expectation exactly. So
`RASTER_WORK_REGION_CYC = 122` was right for the entire time nothing was checking it. The gap
the sweep found was real; the drift it feared never happened.

**The 16 cycles that make it look broken.** The model puts region 32 cycles over cram (122 vs
90) while hardware measures a 48-cycle per-fire gap. The difference is ONE failed dispatch rung
(`RASTER_DISPATCH_RUNG_CYC = 16`): `OP_PAL_REGION` sits at **depth 1**, not depth 0 like
`OP_CRAM` — `raster.emp:711` orders the chain OP_CRAM, then OP_PAL_REGION, with OP_SET_REG as
the fall-through. Anyone re-deriving this and getting 32 has forgotten the rung, not found a bug.

**Poison-proved, so the new row is not inert:** perturbing `RASTER_WORK_REGION_CYC` 122→123
moves the expectation to 3974 against an unchanged measured 3968 and the gate FAILS. Restored.

**Item 5 — CLOSED 2026-08-18 by owner ruling: ritual + nightly backstop.** The gap was a
PROCESS gap, not hidden rot: the full lane was run by hand 2026-08-18 and passed **10/10
gates, exit 0**, but the script's own docstring argues these gates *cannot* live in
`build.sh` (each boots a headless emulator), so "unwired" was a manual ritual nothing
enforced. The owner chose both enforcement points:
- **Ritual** (primary): any parcel touching `engine/effects/*`, `engine/level/bg_anim.emp`,
  or `engine/system/buffers.emp` runs the lane pre-merge and pastes totals + exit code into
  the merge evidence. Recorded in CLAUDE.md's Testing section, where every session reads it.
- **Nightly backstop**: `tools/nightly_effects_gates.sh`, driven by the
  `aeon-effects-gates.timer` systemd user timer (04:17, `Persistent=true`), builds current
  master DEBUG in a detached checkout at `~/sonic_hacks/.aeon-nightly` (outside the repo
  root — a worktree inside it double-counts modules in `emp_helper_closure`'s tree scan)
  and runs the lane. A FAILED lane and a COULD-NOT-RUN lane are both loud
  (desktop notification + `~/.local/state/aeon-nightly/nightly.log`) — a backstop that
  silently can't run is the vacuous-gate pattern this item exists to kill. The failure path
  was selftest-proven and a full real run executed at wiring time.

Six commits, each gated on all four ROM shapes staying **bit-for-bit identical** to master
(`s4.debug` crc=ab1055d4 len=712752 · `s4` crc=7e4dc5de len=697868 · `demo.debug`
crc=10aad76c len=100805 · `demo` crc=2ecd1031 len=96451). Every claim was re-verified against
the code before being acted on.

**CLOSED:**
- **Item 3** — MITIGATED here, **STRUCTURALLY CLOSED 2026-08-19** (branch
  `fix/raster-frame-epoch`; see the block at the end of this section). Both dense constructors
  `ensure(top + lines <= 223)`, and the bound stays — but the measurement that closed the item
  also showed this bound was never what protected the engine. The MITIGATED wording below is
  kept as the record of what was believed at the time.
  ~~The last-line-223 hazard is no longer authorable through them. Swept every caller: only
  `OJZ_TestGradient` (96+96 = 192) and `OJZ_TestRamp` (112+96 = 208), so it was never live.
  Poison-proved (a 224 run fails the build). Interrupt-priority reasoning is still
  source-confirmed, not emulator-confirmed.~~
- **Item 7** — budget-model rows corrected (`sparse_fire_reg1` 396→412,
  `sparse_fire_water` 660→676), values re-derived from the live model rather than copied, and
  the file's `_SUPERSEDED` convention applied. Also corrected `movem_roundtrip_cycles` 40→84
  (the row named a round trip and carried the push only). These rows remain **UNGATED** — they
  are measured/modelled, so they do not fit the `[symbols]` resolver, which cannot evaluate a
  comptime call.
- **Tier 4 / A2 comment truth** — all 10 corrected across `raster.emp`, `raster_dsl.emp`,
  `palette.emp`, `ojz_effects.emp`. Note `raster_dsl.emp`'s row-119 guard text was corrected
  into an explicit **warning** about item 1's single-op hazard, pointing here; it must not be
  read as though item 1 were handled.
- **Tier 4 / B2 `BGANIM_MAX_BANDS`** — guard added
  (`tools/test_bg_emit.py::TestBgAnimBandCeiling`, on build.sh's pytest lane), comparing the
  three real authorities (`constants.emp`, `bg_anim.emp`'s deliberate module-local mirror, the
  emitter's cap, now a named constant). All three agreed at 4, so there was no live drift.
  Four poisons proved it non-vacuous. The span-`ensure` shape of `RASTER_MAX_PATCH` was
  deliberately NOT copied: `ram.emp` *names* `BGANIM_MAX_BANDS`, so a span guard would have
  measured itself. The three mirrors are still not collapsible to one authority.

### LANDED 2026-08-18 — the byte-moving parcel (branch `parcel/raster-substrate-byte-moving`)

Baseline for attribution (all four shapes, verified equal to master before the first edit):
`s4.debug ab1055d4/712752 · s4 7e4dc5de/697868 · demo.debug 10aad76c/100805 · demo 2ecd1031/96451`.

- **Item 2 — CLOSED, and it was THREE sites, not one.** The sweep booked `.cycling`; the
  identical shape is in `.fade` (odd-frame parity `rts`) and `.operators` (NEG_FLASH
  every-4, `.fade_dir` every-2). All three announced `PAL_ACT_VARIANT_STALE` on the layer
  being INSTALLED rather than having CHANGED. Fixed uniformly: `publish_compose_lines()`
  is emitted at the paths that actually wrote colours and `Palette_Compose` announces
  nothing; `DoCycle` keeps its per-line `d7` mask over the helper's blanket `%1110` and
  gates both publishes on `d7 != 0`. **Checked before changing the dirty half:** suppressing
  a redundant `Palette_Dirty` is safe against mid-frame CRAM writes because `Raster_VBlank`
  re-asserts the program's own `pal_dirty_mask` every frame (`raster.emp:636`) — a band's
  tint never depended on a compose layer's incidental re-ship. Code delta +40 bytes,
  reconciled PER PROC against the `.lst`; the ROM length grew only 20, the other 20 went
  into placer fill (do not read length as code delta here).
- **Item 4 — CLOSED.** The dropped-base guard derives its palette line from the trailer's
  CRAM destination (`addr >> 5`) instead of hardcoding `btst #2`. Exact, not approximate:
  every constructor that can produce the address (`stream_cram`, `stream_pal_region`,
  `pal_restore`) already ensures the span cannot run past the end of its CRAM line. Fits
  `clobbers(d0/a1-a2)` unchanged. Byte-verified in the ROM.
- **Item 1 — 1a LANDED; 1b and 1c CLOSED 2026-08-19 (see below).** The blanking spin is now
  per-op PROGRAM DATA read with `move.w (a1)+, d1`; `EFX_BLANK_DELAY` and `EFX_RESTORE_DELAY`
  are deleted. Wire: `[op][cmd hi][cmd lo][SPIN][count-1][payload]`. **At 1a the emitted
  values were still the hand-calibrated 4/4/13**, so timing was unchanged and the wire change
  was measurable in isolation — a LEADING stream op was still mis-timed and `fire()`'s guard
  still said so. (Item 1c replaced those values with a solver; the paragraph below is 1a's
  own record and its 4/4/13 are history, not the shipped numbers.)
  Every stream op is +2 bytes and +4 cycles and nothing else moved: predicted as a pure
  count of stream ops, then **confirmed on hardware, all eight fixtures to the cycle**
  (F1 412 unmoved — the control; F2/F7 462, F3 522, F4 570, F5 632, F6 622, F8 708).
  Work constants split into spinless bases + `spin_cyc(n) = n*10 + 14`.
  **A real cost, not a probe artifact:** programs lost buffer headroom (a 3-word cram fire
  is 10 words, was 9), which forced probe fixtures F3 6→5 and F5 5→4 fires against
  `RASTER_BUF_SIZE`. Shipped programs still fit, but P3 authors denser ones.
- **Tier 4 riders — three CLOSED.** `raster_cost_probe.py`'s wire transcription is now
  PINNED (`tools/test_raster_wire_pin.py`, on build.sh's pytest lane): spin constants,
  per-class arity, opcodes, and the spin word's POSITION (arity alone cannot see a
  transposition). Item 1a is the proof it was needed — the probe's encoder had to be
  hand-edited, and a wrong edit would have measured garbage while `calls` looked healthy.
  `RASTER_SH_BASE` has a real pin against boot's newly-named `VDP_REG_0C_BOOT` instead of a
  comment claiming parity, plus a second ensure that boot's byte does not already have S/H
  set (which would make every band's OFF edge a no-op). `RASTER_BUF_WORDS` replaces the
  bare `64` at four encoder sites. All three byte-neutral; all poison-proved by perturbing
  the SUBJECT, not by asserting "something raised".

**Effects gate lane (mandatory ritual):** 10 gates PASS, exit 0, on `s4.debug.bin`
post-1a — including the cost gate, whose expectations are computed from the shipped
constants and matched hardware exactly.

- **Item 1b — CLOSED 2026-08-19.** The window is MEASURED. Driver
  `tools/hblank_window_sweep.py` against oracle-next's `emulator/scanlines`; full results in
  `docs/benchmarks/scanline-p2/HBLANK-WINDOW-SWEEP-RESULTS.md`. For a LEADING single-op
  3-word CRAM the three burst words cross the line-start sampling instant at N = 22/25/28
  (repeated at four consecutive line boundaries): **upper edge N = 21.5 MEASURED, lower edge
  N = 15.21 DERIVED from the 122.9-cycle H40 blanking width, clean integers 16..21,
  CENTRE 18.** Two by-products: `RASTER_STREAM_WORD_CYC = 30` is confirmed against hardware
  for the first time (8 independent intervals) — **superseded 2026-08-19 by Tier-3 item 1,
  which made the CRAM word 26 and re-ran this sweep: N = 23/26/28, upper edge 22.5,
  CENTRE 19; the numbers in this bullet are the pre-item-1 handler's and stay as the record
  of what was measured then** — and the spec's own §4 fixture was measured
  VACUOUS for two independent reasons, both fixed before any sweep number was recorded. The
  instrument's own limit is booked there too — `emulator/scanlines` renders a row atomically
  at line start, so a landing resolves to +/-1 scanline and the early edge is not observable.
- **Item 1c — CLOSED 2026-08-19** (branch `fix/raster-spin-solver-1c`). The three hand-fitted
  per-class anchors (`RASTER_SPIN_CRAM/REGION/RESTORE` = 4/4/13) are deleted. One measured
  constant — `RASTER_HBLANK_END_CYC = 351`, the modelled cycles from a fire record's op-walk
  origin to the sampling instant — plus a comptime solver that centres each op's burst in the
  window **from the op's position in its fire**. Emitted spins old -> new: leading cram 1w
  4 -> 21, leading cram 3w 4 -> 18, leading region 3w 4 -> 15, leading vsram 1w 4 -> 21,
  leading restore 3w 13 -> 10, reg+cram 1w 4 -> 10, reg+cram 3w 4 -> 7, reg+region 3w 4 -> 4
  (the one shipped shape that does not move — it is the shape the old constant was fitted to).
  `check_landings` refuses any burst that misses the window with margin (EARLY 20 / LATE 10,
  asymmetric because the early edge is derived rather than measured), naming the op, the fire
  line, the landing and both edges. **Do not adopt the numbers this file used to carry** — the
  packet's ~21 and the earlier ~15 were both anchored on inherited points and neither survived
  the measurement; the §2 term that broke them was "3-word CRAM burst ~= 84 cycles", where what
  must fit inside blanking is first-write-to-last-write, measured at 60.
  Three independent corroborations are pinned beside the constant, and they are the reason to
  trust it: the RESULTS doc's own "235 cycles before the instant" for the retired spin 4; the
  retired restore 13 reproduced as the window's far edge; and the retired cram 4 reproduced as
  2.1 cycles (1.8 px) short of the early edge — which is the "1px -> 0px" the P2 gate measured
  on that exact fixture. F-series pins re-derived at 10 cyc/iteration (F1 412 unmoved, the
  control). Ripple landed in the same parcel: `ojz_effects.emp`'s four hand pins, both band
  twins, `raster_cost_probe.py`'s mirrored solver, the wire pin (expectations derived from the
  .emp constants, not copied), and the cost gate.
  **VERIFICATION.** Four shapes build. Tool suite 1044 passed / 2 skipped (baseline
  1025/2; +19 wire-pin cases). Expect-fail lane 17/17 (was 15/15 — a poison per window
  edge, one exactly-1-diagnostic and one exactly-2, the count being half the assertion).
  Effects gate lane **10 PASS, exit 0**, and the load-bearing one is the cost gate: its
  expectations are re-derived from the shipped constants including the solved spins, and
  hardware measured F0 572 / F1 3044 / F3 3882 / F4 4652 / F5 3220 / F8 4640 — every one
  exact, so the new iteration counts were verified on an emulator, not just in comptime.
  The 1b driver re-run against the new ROM reproduces the boundary structure unchanged
  ([22, 25, 28], window [15.21, 21.5], centre 18), which is the check that 1c touched no
  handler code. **Byte accounting against the `.lst`: length delta 0, FOUR differing bytes
  total** — the header checksum, `OJZ_TestRaster+0x19` (04 -> 0A), `OJZ_TestVsram+0x15`
  (04 -> 15) and `OJZ_TwoChannel+0x29` (04 -> 15). Zero code bytes; no placer fill involved.
  **A/B (controller, 2026-08-19, pre-refreeze).** `ab_runner` OLD (`8f629a69`, s4.debug
  `c97cc7b9`, rebuilt and CRC-confirmed) vs NEW (`4143b58c` merge, `8610557b`) on all three
  committed effects scenes, `--selfcheck` deterministic on each: whole-VDP `state_hash`
  EQUAL, visible plane EQUAL, `active_buf` EQUAL; the ONLY gated diffs are the parcel's own
  payload — spin words `04 -> 15` at `raster_buf` offsets +015/+029 (the OJZ_TestVsram /
  OJZ_TwoChannel authored words; 0x15 = the solved vsram-1w spin 21), with the
  reg+region record's spin correctly UNMOVED at 4 (the shape the old constant was fitted
  to). BA-class bar: state-identity everywhere but the designed bytes, and the named
  positive observation is the 1b driver re-run above (solved leading spin 18 inside the
  measured clean integers [16, 21]).
  **CLOSED (same night): the sigil-side repin/refreeze** — s4.debug `c97cc7b9 -> 8610557b`,
  s4 `eab1f9a0 -> d6bc3057`, both at UNCHANGED length (demo byte-identical); frozen as
  `raster-spin-solver-1c`, paired merge recorded in the sigil provenance chain.

**STILL OPEN:**
- Everything else: the rest of Tier 3 perf (the `palette.emp` shift-to-add item, the
  `palette.emp` tail calls, the `-4(a2)` burst word, the OP_SET_REG dispatch chain and the
  dense-kind retest all CLOSED 2026-08-19 — see the Tier 3 block below; the raster.emp
  tail calls CLOSED 2026-08-19 too, so item #5 is fully closed, and only the SR push/pop
  remains of that list, needing owner sign-off, and the dense tier
  gained two NEW riders on the way out — the `-4(a2)` extension into `.dense_body`, which
  is now **CLOSED 2026-08-19** (branch `perf/dense-body-addressing`, measured 12 cyc/line;
  see the closure block below), and the two trailing fires, booked at ~600 cyc/frame and now
  **CLOSED 2026-08-19** (branch `perf/dense-trailing-fires`) at **232 cyc/frame** — ONE fire
  suppressed, not two, and the second is a slope cost rather than an intercept one; see that
  closure block for the Ruling-1b re-derivation; Tier 4 / B2's
  self-test-only variant mirror also CLOSED 2026-08-19, see below), plus C5 footprint, the
  EFX-4b angle, and the zero-`assert.*` observation. Item 3's structural fix CLOSED 2026-08-19
  — not as the booked frame-epoch flag, which the measurement ruled out; see the block below.

**CLOSED 2026-08-19 — Tier 4 / B2, `palette_dsl`'s self-test-only variant mirror.** The
booking was right and the fix went the PREFERRED way rather than the retract-the-claim way:
the mirror now checks the asm. `tools/palette_variant_gate.py` (wired into
`tools/effects_gates.py` as gate `palette_variant`) parses the three
`ensure(variant_word($C, variant(..)) == $W)` vectors straight out of `palette_dsl.emp`, pokes
each vector's `pal_variant` and its colour into live RAM, lets `Palette_Compose` ->
`Palette_DoVariants` -> `Palette_DeriveVariant` run for real, and asserts the word the asm
wrote into `Pal_Variant_Stage`. On top of the pinned vectors it sweeps all 48 entries of CRAM
lines 1-3 against the model and asserts `v_lines` coverage — a fact the mirror's ensures never
modelled at all (the constructor validates the mask; nothing checked the asm obeys it). Zero
ROM bytes: all four CRCs unchanged. Two rebuild poisons recorded in the gate's docstring, both
of which BUILD GREEN — that is the point of the booking, restated as evidence.

  **One finding worth keeping.** Under the G-shift poison the three pinned vectors caught only
  ONE of three failures: two of them use `$000E`, whose G is 0, so they are G-blind by
  construction. The mirror's vectors alone would have been a weak asm check even once wired
  up; the 48-entry sweep is what makes the gate non-vacuous. If those vectors are ever
  rewritten, keep them literal and keep the sweep — the gate reads source TEXT, and a vector
  moved into a named constant or a computed expression leaves it with nothing to parse (it
  exits 2 rather than passing vacuously, but it stops testing its subject either way).

### Sequencing — the deadline is Task 9 of scanline P1, not "before P1"

Byte-moving fixes are FREE before P1's Task 9 (they just become part of the baseline) and cost a
deliberate repin + `refreeze --freeze --ab` with emulator evidence afterwards. That is a real but
modest cost — **do not let it become a reason to leave a defect in place.** The gate is
differential (did the migration change anything), not a claim that these bytes are good.

**Do NOT land these inside the scanline-P1 branch.** Two byte-moving changes in one branch make a
crc diff unattributable — the confounding that voided the prebatch A/B measurement. Land as its
own parcel off master, then merge master into the P1 branch before Task 9.

| # | Site | Bytes | Notes |
|---|---|---|---|
> **RE-DERIVE ITEM 1's DEFICIT — the packet's "~21" does not reconcile (found in review
> 2026-08-18).** Each `dbf` spin iteration is 10 cycles (the shipped spin is 4 taken x 10 +
> 14 not-taken = 54). Covering the 110-cycle single-op-vs-two-op gap needs about +11
> iterations, i.e. `EFX_BLANK_DELAY` ~= **15**; against the stale 94-cycle gap it would be
> ~14. Neither reaches the packet's ~21. The landed comment corrections deliberately restate
> NO number, saying only that the gap is bigger — so nothing in the tree inherited this.
> Whoever lands item 1 must re-derive from the shipped constants and pin the result, not
> adopt ~21.

| 1 | `engine/effects/raster.emp:232` | moves | **top finding.** `EFX_BLANK_DELAY=4` was fitted to the 152-cyc two-op (SetReg-prefixed) shape; a SINGLE-op CRAM/region fire carries 58 cyc and lands at x~170 of 320 — mid-active-display. The DSL freely admits that shape (`band(sh: 0)`, `region_boundary(sh: 0)`, `fx_tint_band`). Deficit ~4 → ~21. Latent (all shipped OJZ fires are two-op). **Also: the author-facing guard text at `raster_dsl.emp:340` asserts the OPPOSITE of the measurement recorded at `raster.emp:797-804`** — the row-119 fixture has the stream op second. Fix: split the constant by op position (`_FIRST` / `_AFTER_REG`) + re-pin the F-series, or refuse single-stream-op CRAM fires without a measured opt-out. Correct :340 either way. |
| 2 | `engine/effects/palette.emp:356` | moves | **costs cycles today.** `.cycling` sets `PAL_ACT_VARIANT_STALE` before `Palette_DoCycle` decides whether anything rotated (rotation is timer-gated at `:419`), so any section binding a cycle script AND a variant pays the full ~19,332-cyc re-derive every frame — the exact regression the stale bit exists to kill ("the 15.1%-of-frame gate"). `OJZ_Preset_Sec3` is that combination. `.fade` same shape, smaller scale. Fix: move the stale-set into DoCycle's rotation branch gated on `d7 != 0` — one instruction (DoCycle already accumulates the touched-line mask in d7). |
| 3 | `engine/effects/raster.emp:609` | **zero** | ~~No interlock between a deferred IRQ4 and `Raster_VBlank`'s unconditional frame rewind. A dense run ending at line 223 is authorable (both constructors `ensure(top + lines <= 224)`), HINT raises on the same line as VINT, IRQ6 masks level 4, so the pending IRQ4 runs after the rewind, consumes priming record 0, overwrites the flushed `$0A=0` and shifts the whole next frame by one record — a stuck state, not a blip. Source-confirmed, NOT emulator-confirmed. Cheap fix: tighten to `<= 223` (shipped gradient top=96/96 lines passes). Structural: a one-byte frame-epoch flag.~~ **CLOSED 2026-08-19 — the hazard is real, the LINE-223 diagnosis was not, and the frame-epoch flag is impossible. See the block at the end of this section.** |
| 4 | `engine/system/buffers.emp:402` | moves | Off-screen ship's dropped-base guard hardcodes `btst #2, Palette_Dirty` (CRAM line 2) but the ship's palette line is authored data in the trailer — for a ship on line 1 or 3 the guard tests a bit nothing sets and is fully vacuous. Latent (shipped content is line 2). |
| 5 | `tools/effects_gates.py:11` | zero ROM | **`effects_gates.py` is UNWIRED** — no build, no test runner, no CI, no hook; the only mention in build.sh is inside a comment. It is the SOLE invoker of `raster_off_gate`, `raster_source_gate`, `snapshot_poison_gate`, `effects_scene_assert` (3 scenes) and every cost fixture. That entire emulator-backed lane has only ever run when a human typed the command. build.sh *does* wire the source-level lane (`effects_budget_check.py`, pytest suite, 11-poison expect-fail) — the gap is precisely the emulator-backed half. Expect it to FAIL on first wiring. Same species as `reference_verified_vacuous_gates`. |
| 6 | `tools/effects_gates.py:214` | zero ROM | Cost gate hardcodes `--only F0,F1,F3,F5,F8`, omitting **F4** — the sole `stream_pal_region` fixture — so `RASTER_WORK_REGION_CYC = 122` (`raster_dsl.emp:1008`), the constant gating the shipped OJZ water band, never reaches hardware. The list grew `F0,F1,F3` → `+F5,F8` with F4 simply never added. |
| 7 | `tools/effects_budget_model.toml:55` | zero | Per-fire rows contradict a live `ensure`: `sparse_fire_reg1_cycles = 396` vs `raster_dsl.emp:1124` pinning F1 at **412**; water fire 660 vs 676. `effects_budget_check.py` gates only the `[symbols]` table and `sparse_fire_*` is read by NOTHING. The file has a `_SUPERSEDED` convention it failed to apply. Three seats found this independently. |

**Tier 3 perf — deliberately AFTER the freeze, as byte-moving parcels** (ranked by leverage):
~~`raster.emp:736` 30 cyc/streamed word vs 16 via `-4(a2)`~~ **CLOSED 2026-08-19** (see
"Tier-3 item 1 CLOSED" below — landed at 26, not 16; the 16 was the instruction alone and
omitted the loop's `dbf`) · ~~`raster.emp:714` OP_SET_REG pays all 5 compare rungs (80 of
110 cyc; a leading `tst.w d1 / beq` decimates it)~~ **CLOSED 2026-08-19** (see "Tier-3 item 2
CLOSED" below — landed WITHOUT the `tst.w`: the op fetch's own `move.w` already sets Z, so the
whole pre-test is one `beq`) · ~~`raster.emp:834` dense kind re-tested per
scanline, ~2,300 cyc/frame, run-invariant~~ **CLOSED 2026-08-19** (see "Tier-3 item 3 CLOSED"
below — the hoist landed and is worth **4 cyc/line, not 24**; the booking priced instructions
nominally in a body the VDP's bus holds. The parcel's durable half is the dense tier's first
scene, gate and cost row) · ~~`raster.emp:656` redundant SR push/pop ~30 cyc/fire
(`rte` already restores SR) — needs a sigil-side context flavour, so it is a paired aeon+sigil
change AND a novel mechanism: owner sign-off required, do not assume~~ **CLOSED 2026-08-19,
owner-approved — see "Tier-3 item 6 CLOSED" below. The sigil flavour was genuinely required
(the booking was NOT over-scoped), the saving measured **22 cyc/fire not 30**, and the booking
missed where the cycles actually are: the DENSE tier, at 96 fires a frame** · ~~`palette.emp` ×6
`lsl.w #1` → `add.w dN,dN` ~768 cyc/derive~~ **CLOSED 2026-08-19** · ~~4 missed mandatory tail calls
(`raster.emp:560,622`; `palette.emp:386,666`)~~ — **FULLY CLOSED 2026-08-19**, palette half first,
raster half second (see the two blocks below).

> **CLOSED 2026-08-19 — the palette half of both items** (branch `perf/palette-shift-to-add`,
> commit `bfccde10`). All six `lsl.w #1` doublings are `add.w dN,dN` (8 cyc → 4), and both
> palette tail calls (`Palette_Compose`.variants → `Palette_DoVariants`, `Palette_DoVariants`
> `.slot1` → `Palette_DeriveVariant`) are `jbra`. Line numbers had drifted post-1c: the six
> shifts landed at `:567,590,653,669,760,786` and the tail calls at `:421,718`.
>
> *Flag safety:* every one of the six is immediately followed by `or.w dN, dM`, which
> recomputes the whole CCR — no consumer of the shifted-out flags exists at any site. Even
> if one did, the two encodings agree here: each operand is a 0..7 channel already masked
> (max `$0700` after the paired `lsl.w #8`), so nothing crosses bit 15 and C=X=V=0 under
> either; N/Z are result-derived and identical by construction.
>
> *Size:* ZERO byte movement. The symbol maps of all four shapes are byte-identical to base
> — 16 bytes change per ROM (six opcode words `E34B`→`D643` / `E349`→`D241`, two opcode bytes
> `61`→`60` where sigil had already relaxed both `jbsr` to `bsr.b`, and the header checksum).
> No pins move, so no repin/refreeze was needed.
>
> *Realized cycles.* The `~768 cyc/derive` booking assumed BOTH variant slots bound. Every
> shipped OJZ preset carries `variants: [Variant_Water_Deep, 0]` — slot 1 is NULL — so the
> derive covers one slot: `v_lines` defaults to `%1110`, 3 lines × 16 entries = 48 entries,
> 2 sites × 4 cyc = **384 cyc per derive** today (768 the moment a second slot is bound).
> Add 24 cyc for the Compose tail call (`bsr.b` 18 + returning `rts` 16 + Compose's own `rts`
> 16 = 50 → `bra.b` 10 + callee `rts` 16 = 26) for **408 cyc per derive**. The `DoVariants`
> `.slot1` tail call is LATENT — with slot 1 NULL the `beq .ret` above it always takes.
> Cadence under shipped content: sections 0/1/2/Plain install the count-0 cycle sentinel, so
> the only stale-setter is the base copy and the derive runs once per section ENTRY; section 3's
> `OJZ_ShimmerCycle` (`period: 8` → 9-frame cadence) derives every 9th frame, i.e. ~45 cyc/frame
> averaged, 408 of the derive's ~19,332 cyc (~2.1%) on the frame it fires. `Palette_DoFade`'s
> `.word` and `Palette_DoOperator`'s `.fw_word` each save 8 cyc × 48 words = **384 cyc per step
> frame**, but the shipped scroll test runs neither a fade nor an operator, so those two are
> exercised only by their gates.
>
> *Evidence:* four shapes green; pytest 1066 passed / 2 skipped (baseline); effects gate lane
> 18/18 PASS, exit 0, cost model unmoved (F0 572, F1 3044, F3 3882, F4 4652, F5 3220, F8 4640
> — the model does not price the palette derive); `ab_runner --selfcheck` OLD-vs-NEW on all
> three raster scenes (`mid_band`, `suppressed`, `above_screen`) = **ALL EQUAL (gated)**
> including `state_hash`, as a value-identical parcel must be.

> **CLOSED 2026-08-19 — the RASTER half of the tail-call item, which closes item #5 entirely**
> (branch `perf/raster-tail-calls`, commits `74043ec9` + this one). Line numbers had drifted a
> fourth time: the two sites landed at `raster.emp:625` and `:692` post-item-3. Both are in
> `Raster_VBlank clobbers(d0-d4/a0-a2)`, and structurally they are the two shapes the palette
> parcel already met — one foldable pair, one whose `rts` is a branch target.
>
> *Site A — `HBlank_Uninstall`, the empty-program uninstall arm.* Genuine tail: no `link`, no
> `movem`, no stack frame anywhere in the proc, and nothing at all between the call and the
> `rts`. That `rts` carries NO label (the proc's four locals are `.copy_program`, `.copy`,
> `.no_install`, `.done`; the listing agrees), so it is reachable by fall-through only and
> folding it orphans nothing. `HBlank_Uninstall clobbers(d0)` ⊂ the caller's set. → `jbra`,
> and the `rts` is deleted rather than left as dead code.
>
> *Site B — `HBlank_Install`, the per-frame re-arm.* Same tail proof; `clobbers(d1)` ⊂ the
> caller's set. But its `rts` **IS** `.done`, the target of the `beq.s` that the no-program
> arm takes further up the proc, so it is KEPT exactly as the palette parcel kept its
> equivalent. Only the `bsr` becomes a `bra`.
>
> *Bytes, checked at the encodings and not assumed.* **Neither `jbsr` had relaxed short** —
> both were `bsr.w` (`6100`) at 4 bytes and both become `bra.w` (`6000`) at 4 bytes, same
> displacement word at site A. So the branch conversions save ZERO bytes and the entire
> movement is site A's deleted `rts`: `Raster_VBlank` **38 → 36 (-2)**, the only proc in any
> shape whose span changes. 128 downstream effects symbols shift -2, from
> `Raster_VBlank$copy_program` through `Effects_InstallPreset$have_config`, and the section's
> placer fill absorbs it before `Level_LoadArt`'s pinned base at `$008260`, which is unmoved.
> **All four ROM lengths unchanged** (698393 / 713279 / 95713 / 100070). Two other apparent
> span changes in a naive listing scan are artifacts of separately-pinned symbols interleaved
> by address (`SoundTablesZ80_Head` at `$008000`, `Level_LoadArt` at `$008260`), not code.
>
> *Cycles.* 24 each, nominal and real: `bsr.w` 18 + callee `rts` 16 + caller `rts` 16 = 50 →
> `bra.w` 10 + callee `rts` 16 = 26. Site A fires once per raster-OFF transition. **Site B is
> the recurring one: `HBlank_Install` is deliberately re-run every frame a program is armed**
> ("idempotent, and it heals the counter"), so it is 24 cyc/frame — 0.019% of an NTSC frame.
>
> *VDP-window statement, per the carried item-3 finding.* **Neither site is inside a VDP-held
> window, so nominal timings are not over-predicting here.** `HBlank_Install` and
> `HBlank_Uninstall` write only `HBlank_Vector_Slot` and `VDP_Shadow_Table`, both RAM; the
> arms of `Raster_VBlank` around both sites are `clr.l`/`lea`/`move.l` against RAM. There is
> no VDP-port access anywhere on either path, so nothing is absorbed into a bus wait the CPU
> was already serving. *Cost model:* neither site is on a path the F-series prices — the
> F-series and `RASTER_DENSE_LINE_GRAD_CYC` price ops inside `Raster_HInt`, and no `[symbols]`
> row maps to `Raster_VBlank`, `HBlank_Install` or `HBlank_Uninstall`. So **no constant moves
> and the landing solver does not re-derive**, confirmed empirically: the cost row is
> byte-for-byte the same as master's on the same hour (below).
>
> **THE FINDING — the 1b sweep boundaries MOVED, and the cause is not what a byte-moving
> parcel would assume.** Run on master and on this branch the same hour, the sweep read
> `[22, 25, 28]` vs `[23, 24, 27]`. Two single-site control builds attribute it exactly:
>
> | build | bytes moved | VBlank tail | sweep boundaries | window |
> |---|---|---|---|---|
> | master `26f965c4` (`54f4b253`) | — | — | `[22, 25, 28]` | `[15.21, 21.5]`, centre 18 |
> | **C1** site B only (`0dfded5e`) | **none** (opcode `61`→`60`, same width) | -24 cyc/frame | `[23, 24, 27]` | `[14.21, 22.5]`, centre 18 |
> | **C2** site A only (`8063a0ad`) | -2, 128 symbols | unchanged on the armed path | `[22, 25, 28]` | `[15.21, 21.5]`, centre 18 |
> | parcel (`896a35c8`) | -2, 128 symbols | -24 cyc/frame | `[23, 24, 27]` | `[14.21, 22.5]`, centre 18 |
>
> C2 reproduces master EXACTLY while moving 128 symbols, and C1 reproduces the new reading
> while moving zero bytes. **The byte shift is invisible to this instrument; the 24-cycle
> VBlank tail is the whole cause** — and each control was reproducible (master and the parcel
> were each swept twice, identical both times), so this is a deterministic effect, not drift.
>
> *Why a VBlank-tail saving can move a raster boundary at all, which is the durable half.*
> The priming IRQ4s on lines 0 and 1 are raised while IRQ6 still masks level 4, so they are
> taken the instant `VInt` returns — their phase within a line is set by **when VBlank
> finishes**, not by the VDP. `Raster_VBlank` is the last raster work in that handler, so its
> tail is literally part of the raster schedule's phase reference. Shortening it by 24 cycles
> moves every fire's landing that much earlier, which is why the MEASURED half of the window
> (the group's first boundary, ±0.5) moved **21.5 → 22.5**: an earlier landing needs one more
> spin step to cross the same boundary. That is the predicted direction, so this is
> *predicted*, not merely *unchanged*. Anyone editing `Raster_VBlank`, `VInt_Level` or
> `VInt_Lag` should expect the same and re-run the sweep.
>
> *And why it needs no action.* The window WIDENED to a strict superset — integers `16..21`
> became `15..22` — with **centre N = 18 in every one of the four builds**. The shipped solved
> leading spin is 18, still dead centre and still inside the clean integers, so no spin
> re-derives and the change relaxes the constraint rather than tightening it. **Do not read
> the `30.0 → 20.0 cycles per burst word` step as physical**: it is two intervals between
> three points at a 10-cycle quantum, and the true CRAM stream-word cost is the 26 that
> Tier-3 item 1 landed — both readings bracket it, neither measures it.
>
> *Evidence.* Four shapes green — `cf54b017` / `896a35c8` / `f16d1a50` / `31a87100`, every
> length unchanged. pytest **1074 passed / 2 skipped** (baseline). expect-fail **17/17**.
> Effects gate lane **22/22 PASS, exit 0**. Cost row **UNMOVED**, and re-measured on master's
> own ROM in the same session to say so rather than comparing against a stale booking: master
> F0 572 F1 2624 F3 3862 F4 4640 F5 3204 F8 4628 and dense FD1 4362/13 fires, FD2 15562/45
> fires → 350.0 cyc/line; branch identical in all eight. (The palette parcel's row above reads
> F1 3044 etc. — that is pre-item-2 and pre-item-3, not a discrepancy.) `ab_runner`
> `--selfcheck` OLD-vs-NEW on **all four** scenes (`mid_band`, `suppressed`, `above_screen`,
> `dense`) = **ALL EQUAL (gated)** including `state_hash`, both raster buffers, `active_buf`
> and the dense runtime state — value-identical, as the 1b phase shift does not reach any
> committed state. Not done here, deliberately: **no repin/refreeze and no sigil-side pairing**
> — the -2 moves pins and that ritual belongs to whoever merges this.

> **CLOSED 2026-08-19 — Tier-3 item 3, the dense-kind retest** (branch
> `perf/raster-dense-kind`). Line numbers had drifted again: the retest was at
> `raster.emp:970` post-item-2.
>
> **Read the instrument half first — it is the larger deliverable.** Three prior sessions
> established the same gap and none could close it: the dense tier had NO cost model, NO gate
> observing its timing, and NO committed `ab_runner` scene (all three were sparse-tier). So a
> "~2,300 cyc/frame" claim about the tier that costs ~27% of a frame had nothing in the tree
> able to confirm or refute it. This parcel shipped the instrument BEFORE the optimization:
>
> - **`tools/scenes/effects_raster_dense.json`** — the fourth scene. Reaches `OJZ_TestGradient`
>   by poking `Camera_X` past the section-2 boundary and letting `Parallax_CheckBoundary`
>   install `OJZ_Preset_Sec2`, then asserts `Raster_Dense_Cursor == stream + lines *
>   RASTER_CRAM_MAX * 2` — an equality that holds only if `.dense_body` ran exactly `lines`
>   times from the right base. Nothing else a scene can read sees that: CRAM is re-asserted at
>   frame top and the program words are ROM.
> - **`raster_cost_probe` FD1/FD2** — a dense fixture pair, read only as a SLOPE so every shared
>   overhead cancels. `dense_program_words` is pinned against `RasterGradientProgram`'s own
>   fields and `raster_arm`'s own formula (`test_raster_wire_pin.py`, +5 tests).
> - **`RASTER_DENSE_LINE_GRAD_CYC`** — the dense tier's first cost term, measured (350), with an
>   invariant nothing checked before: a dense line must fit inside a scanline, because the tier
>   fires on every one. 350 of 488.
>
> *What the instrument then said about the item.* **BEFORE 354.0 cyc/line, AFTER 350.0** — the
> whole hoist is **4 cycles per line**, 384 cyc/frame on the shipped 96-line gradient, 0.30% of
> an NTSC frame. The booking's ~2,300 assumed 24 cyc/line (a `tst.w` at 16 plus a branch). Two
> independent measurements say otherwise: removing the pair measured -4, and inserting a
> behaviour-neutral `tst.w` in the same position (the cost gate's poison) measured +4. **The
> missing cycles are the VDP holding the bus.** The test sat directly after
> `move.l Raster_Dense_Cmd, (a2)`, a control-port write, and during active display the EA read
> is absorbed into a wait the CPU was already serving. *Nominal 68000 timings over-predict any
> edit inside `.dense_body`, and the FD pair is now the only thing that can say by how much.*
> That generalises past this item — it is the reason to distrust the remaining Tier-3 raster
> bookings' cycle figures until they are measured too.
>
> *What shipped.* `Raster_Dense_Kind` (0/1) became `Raster_Dense_Mode`, TRI-STATE: 0 no run,
> +1 gradient, -1 ramp. It is now both the run-active flag and the body selector, so the
> top-of-handler `tst.w` answers both questions — `bne` takes the dense side, and its N flag
> feeds one `bmi.s` there. `Raster_Dense_Lines` is demoted to a pure countdown whose expiry
> clears the mode. Same RAM slot, same width: **not one RAM address moves**, which is what lets
> a single symbol table serve both sides of the A/B (`ab_runner` loads one).
>
> *The floor, and why the item's own proposal was worse.* A RAM-held body pointer costs MORE:
> sigil places this RAM in the absolute-SHORT window, so `movea.l (xxx).W, a1` (16) + `jmp (a1)`
> (8) = 24 against the 20 the two-instruction test cost — before considering that a computed
> `jmp` defeats contract-closure dataflow. And a three-way branch at the TOP would put a second
> not-taken branch on the SPARSE path, moving `RASTER_FIRE_BASE_CYC` and re-basing every solved
> blanking spin and every fixture pin. One conditional branch on the dense side is the floor.
>
> *Honest cost.* +34 cycles per RUN per frame (the ENTER's `move.w #1` over `clr.w`, and the
> `.dense_end` retire), measured as the FD1/FD2 intercept. **Crossover ~9 lines**: a dense run
> shorter than that is very slightly slower than before. Both shipped runs are 96 lines and an
> 8-line dense run is a sparse-tier job, but it is a real property.
>
> *One correction to the source, found by the fixtures.* The LEAVE schedule said ONE trailing
> fire after a run; hardware said `lines + 5` fires where `lines + 4` was predicted, at both
> line counts. There are **TWO** — Ruling 1b keeps the last two dense fires' every-line arms in
> flight past the end of the run. `raster.emp`'s own authoring rule ("the first post-gradient
> sparse event must be >= 2 lines below the run's last line") was already right; only the
> runtime comment was wrong. The derivation was corrected rather than relaxed to the measurement.
>
> *Evidence.* Four shapes green (`2da6bcc7` / `54f4b253` / `f38eee3d` / `a931ad3e`). pytest
> **1074 passed / 2 skipped** (+5, the new wire pins). expect-fail **17/17**. effects gate lane
> **22/22 PASS exit 0** (19 on master; the three additions are `scene:dense` determinism,
> `scene:dense` dense tier, and the dense cost row). `ab_runner` OLD-vs-NEW on **all four**
> scenes = ALL EQUAL (gated) including `state_hash` and the dense runtime state. The item-1b
> sweep driver, run on OLD and NEW the same hour: **every field identical** — boundaries
> `[22,25,28,71,74,76]`, window centre 18, 27.5 cyc/burst-word, 490.0 cyc/sampling-period, and
> every per-N landing and verdict. The sparse tier did not move, as a dense-path-only change
> must not. Byte accounting: `Raster_HInt` 318 → **332 (+14)**, the only symbol that moved.
>
> *Solver:* `RASTER_DENSE_LINE_GRAD_CYC` is the only cost constant this parcel touched, and
> **the landing solver does not read it** — `fire_spins` / `solve_spin` price ops within a
> sparse fire and the dense tier has no ops. So no spin re-derives, and the sweep confirms it
> empirically rather than only by argument.
>
> **UNBLOCKED, NOT TAKEN — the `-4(a2)` rider.** Tier-3 item 1 landed `-4(a2)` in `.cram_loop`
> only and left `.dense_body`'s three `move.w (a1)+, VDP_DATA` (20 cyc each) alone because
> nothing could measure the dense tier. FD1/FD2 can now. **Do not assume it is worth 4×3=12
> cyc/line**: those three writes sit in the same VDP-held window that ate this parcel's 8
> cycles, so the fixture pair must rule, not the instruction table. Same rider, same caveat,
> for `.dense_body`'s cursor reload.
>
> **CLOSED 2026-08-19 — and the caveat above was WRONG, which is the finding.** Branch
> `perf/dense-body-addressing`. It is worth exactly 4×3 = 12 cyc/line, and the cursor-reload
> half of the rider is untouched (a2 is the VDP port, not the cursor; there is no `-4(a2)`
> spelling for a RAM long). See the closure block at the end of this section.
>
> **A SECOND RIDER, worth more than either — the two trailing fires.** Each is a full sparse
> fire (~300 cyc) doing nothing but walking the terminator, twice per frame per dense run:
> ~600 cyc/frame, larger than this whole parcel. Falling `.dense_end` into `.park` would write
> `$8AFF` over the run's last `$8A00` and suppress both. It is NOT a value-identical change —
> it alters the LEAVE schedule that a post-dense sparse record depends on — so it needs its own
> parcel, its own authoring rule, and the dense scene to gate it. Booked, not taken.

> **CLOSED 2026-08-19 — and the booking was HALF right, which is the finding** (branch
> `perf/dense-trailing-fires`). `.dense_end` now falls into `.park`, and it suppresses **ONE**
> trailing fire, not two: **232 cyc/frame per dense run**, measured, against the booked ~600.
>
> *The re-derivation, from the tree's own Ruling 1b.* An arm word written at fire i governs
> `gap(i+1 -> i+2)`, so when a run ends the last TWO dense fires each have an every-line
> `$8A00` in flight — the second-to-last line's schedules the fire at `last+1`, the last
> line's the fire at `last+2`. The LEAVE edge runs INSIDE the last dense fire, so the only arm
> it can still overwrite is that fire's own. The first trailing fire was already armed one line
> earlier and is unreachable from there. `raster_cost_probe.py`'s own schedule note said
> exactly this ("the first trailing fire consumes the second-to-last dense fire's arm, the
> second consumes the LAST one's") and the booking read past it.
>
> *Why the other one is not worth buying.* Suppressing the first as well needs the
> SECOND-TO-LAST line to park, i.e. a "one line remaining" test inside `.dense_body` — the
> per-line path. The cheapest spelling costs ~4 cyc/line (the countdown's own flags answer
> "zero", not "one", and the count lives in RAM), so it pays for itself only below ~60 lines
> and both shipped runs are 96. The parcel's rule was intercept, never slope, and this is the
> case where the two are in opposition. NOT TAKEN, deliberately.
>
> *A third framing, which is the one to remember.* These fires were never dense-tier overhead
> — they are the SPARSE walk resuming, and they walk the terminator only because a dense
> program has nothing after its run. The sparse tier never pays them: `raster_dsl` authors
> `$8AFF` into its last TWO records from DATA, so a sparse schedule ends with zero wasted
> fires and its terminator is pure defense. The dense tier could not do that because the arm
> is written by the BODY at runtime. This parcel gives the dense tier half of what the sparse
> tier has from data; the other half is not free, per the paragraph above.
>
> *What it costs the format, stated rather than rounded away.* The schedule now ENDS with a
> dense run, bar the one fire already in flight. Nothing representable loses anything — the
> dense tier is authorable only through `raster_gradient_program` / `raster_ramp_program`,
> both fixed structs whose terminator follows the setup record immediately, and `raster_dsl`
> has no dense-op constructor at all, so a post-dense record cannot be written today. A future
> dense-then-sparse composition wants an authored LEAVE arm word in the op body (the sparse
> tier's answer), not this pipeline leak. **Booked as such, above.** It also PULLS THE LAST
> FIRE BACK INSIDE ACTIVE DISPLAY: a legal run ending at 222 used to fire on 223 and 224, the
> second past `RASTER_VBLANK_V`; now no representable program fires in VBlank at all.
>
> *Predicted, then measured.* Prediction written before the build: `calls` 12/44, slope
> UNCHANGED at 316.0, intercept `1512 -> ~1276` (one park fire nominally ~238, plus +2 at the
> LEAVE edge where a 10-cycle `bra.s` is traded for a 12-cycle `move.w #imm,(a2)`).
> Measured on `tools/raster_cost_probe.py`, same session, s4.debug `06af0010 -> 234ac35d`:
>
> | | before | after | delta |
> |---|---|---|---|
> | FD1 (8 lines) | 4040 / 13 fires | **3808 / 12 fires** | -232 |
> | FD2 (40 lines) | 14152 / 45 fires | **13920 / 44 fires** | -232 |
> | slope (FD2-FD1)/32 | 316.0 | **316.0** | 0 |
> | intercept | 1512 | **1280** | -232 |
> | F0 (sparse floor) | 588 | **588** | 0 |
>
> The delta is the SAME at both legs and the slope is bit-identical, which is the signature of
> a cost charged once per run and to nothing else. 232 against the predicted 236 — four
> cycles, the same direction the tables have missed by all week inside this handler.
>
> *And the full five-count sweep was re-run rather than re-scaled from the pair*, the way the
> `-4(a2)` rider's was, so "once per run" is five points and not two:
>
> | lines | fires | `lines + 4` | cyc/frame | `1280 + 316 x lines` | delta vs pre-parcel |
> |---|---|---|---|---|---|
> | 8 | 12 | 12 | 3808 | 3808 | -232, -1 fire |
> | 40 | 44 | 44 | 13920 | 13920 | -232, -1 fire |
> | 80 | 84 | 84 | 26560 | 26560 | -232, -1 fire |
> | 96 | 100 | 100 | 31616 | 31616 | -232, -1 fire |
> | 120 | 124 | 124 | 39200 | 39200 | -232, -1 fire |
>
> Exact at every count. The two dense riders are mirror images in this table and that is worth
> keeping: `-4(a2)` moved every leg by exactly `12 x lines` with the intercept frozen, this one
> moves every leg by exactly 232 with the slope frozen.
>
> *Schedule walk, before and after* (`tools/raster_frame_epoch_probe.py`, ordered event walk
> with cursor readback — the instrument that SEES schedule corruption). Cursor 26 is the
> terminator record, which `.park` reads without advancing:
>
> | fixture | before | after |
> |---|---|---|
> | `dense 220+3->222` | `HHHHHHHHV` `[2,6,10,26,26,26,26,26]` | `HHHHHHHV` `[2,6,10,26,26,26,26]` |
> | `dense 100+4->103` | `HHHHHHHHHV` `[2,6,10,26 x6]` | `HHHHHHHHV` `[2,6,10,26 x5]` |
> | `sparse@222` (control) | `HHHV` `[2,6,10]` | `HHHV` `[2,6,10]` |
> | `stall 222(spin 400)+224` | `HHHHV` `[2,2,6,10]` | `HHHHV` `[2,2,6,10]` |
>
> UNIFORM on every row, both sides. Exactly one `26` leaves each dense walk and nothing else
> moves — including the stall fixture, i.e. the frame-rewind interlock still retires its stale
> fire on cursor 2 without advancing and the frame's own walk still completes.
>
> *The derivation was updated, not patched.* `dense_fire_count` is `lines + 4` again — the
> value it was FIRST derived as, when only one trailing fire was assumed, then corrected to
> `lines + 5` by hardware. The same number for a different mechanism is exactly the trap this
> lane exists to catch, so the pin no longer restates it: `tools/test_raster_wire_pin.py`
> reads `raster.emp` and asserts `.dense_end` falls STRAIGHT into `.park`, with a poison that
> puts the `jbra .out` back. `tools/effects_gates.py` now IMPORTS `dense_fire_count` instead
> of spelling `+ 5` beside a paragraph explaining why — the two could not fail each other
> before.
>
> *Bytes.* `Raster_HInt` **340 -> 338**, the only proc whose length changed (the removed
> `bra.s`); 78 of 1024 symbols shifted and the placer's fill re-flowed, so s4.debug is 20
> bytes shorter while the other three shapes are unchanged in length. Byte-moving, no
> refreeze in this branch.
>
> *Lanes.* Four shapes green — s4 `e111dff7 -> d00dd11d`, s4.debug `06af0010 -> 234ac35d`,
> demo `aae04929 -> 7db47b7b`, demo.debug `82884c07 -> 4c0a432d` (demo links the engine's
> raster module, so it moves too). pytest **1107 passed / 2 skipped** (+1, the LEAVE-edge
> poison). expect-fail **20/20**. Effects gate lane **23/23 PASS, exit 0**, with the dense
> cost row now reading `lines + 4` and the sparse cost row unmoved (F0 588, F1 2508, F3 3818,
> F4 4584, F5 3172, F8 4632 — every one exact against the shipped constants, which is the
> control that says the sparse tier did not move). `ab_runner` OLD-vs-NEW on **all four**
> effects scenes: **ALL EQUAL (gated)** — `state_hash`, both raster buffers, `active_buf`, and
> the dense scene's `dense_state`. That was the ENUMERATED prediction and not a hope: the
> suppressed fire wrote `$8AFF` over an `$8AFF` that was going to be there anyway, so no cell
> ab_runner captures can see it, and the observable delta lives only in the fire count (epoch
> probe) and the intercept (cost probe). The 1b sweep driver, run on OLD and NEW the same
> hour with identical arguments: **byte-identical output** — 19 distinct `flipX` values,
> CLEAN 8 / TOO EARLY 16 / TOO LATE 7, contiguous clean run `[(16, 23)]`, centre 19.5,
> blanking plateau row 101 N 16..23. The sparse tier's blanking boundaries did not move, as a
> dense-path-only change must not.
>
> *Two instrument traps, both hit here.* `ab_runner`'s `--new` takes the same ABSOLUTE-path
> rule the cost probe documents for `--rom`: a relative path resolves against the EMULATOR's
> cwd, and the first run of the dense scene reported a loud `DIFF` whose NEW side was
> uninitialised RAM (`A0A0…`) rather than a schedule difference. And the committed effects
> scenes hard-code `"symbols": "/home/volence/sonic_hacks/aeon/s4.debug.lst"`, the SHARED
> checkout — which another agent was rebuilding mid-run. Only RAM symbols are read so it
> survives, but a worktree parcel should point the scenes at its own `.lst` (copy them; do not
> edit the committed ones).
>
> **A RIDER THIS PARCEL FOUND AND DID NOT TAKE — the per-line arm write may be redundant,
> and it is a SLOPE item.** Both dense bodies open with
> `move.w #RASTER_ARM_EVERY_LINE, (a2)`, i.e. they re-write reg $0A = 0 on EVERY scanline of
> the run. reg $0A is a latched VDP register, not a counter: the HInt counter reloads FROM it
> and the register keeps its value until something writes it. Entering a run, reg $0A is
> already 0 — the setup record's own arm word (`rgp_arm2 = RASTER_ARM_EVERY_LINE`) was written
> by the sparse walk at the setup fire — and nothing on the dense path touches reg $0A except
> these writes and, now, the LEAVE park. If that reading is right the write is pure redundancy
> from the second dense line onward and removing it is **12 cyc/line** — 1,152 cyc/frame on a
> 96-line run, five times this parcel and on the SLOPE rather than the intercept.
>
> **UNVERIFIED, deliberately.** It was found while re-deriving the LEAVE schedule, it is a
> different change (per-line, not per-run), and this handler has over-predicted and
> under-predicted four edits this week — so it is booked rather than smuggled in. The
> experiment is cheap and already built: delete the two writes, run
> `tools/raster_cost_probe.py --only F0,FD1,FD2` (the slope must drop by 12 and the intercept
> must NOT move) and `tools/effects_gates.py`'s `scene:dense` row (the dense cursor must still
> end at `stream + lines * 3` words, which is only true if the body ran exactly `lines`
> times). Two failure modes to look for and neither is visible in the cycle figure: a run
> whose first line does NOT inherit reg $0A = 0 from the setup record (any future program
> shape where the setup fire is not the one immediately before the run), and any path that
> writes reg $0A between two dense lines.

> **CLOSED 2026-08-19 — Tier-3 item 2, the dispatch chain** (branch
> `perf/raster-dispatch-chain`, commit `0b1ad989`). Line numbers had drifted: the chain is at
> `raster.emp:769` post-1c.
>
> *What shipped, and why it is not what the item proposed.* The item asked for a leading
> `tst.w d1 / beq`. The `tst.w` is unnecessary: OP_SET_REG is opcode **0**, and `.op_loop`'s
> own op fetch `move.w (a1)+, d1` sets Z from the word it moved. The pre-test is therefore a
> single `beq .op_reg` in front of the chain and nothing else — one instruction, +2 bytes,
> and 4 cycles cheaper than the proposal for every op in the vocabulary.
>
> | class | dispatch before | after | delta |
> |---|---|---|---|
> | OP_SET_REG | 80 (five failed rungs — it was the fall-through) | **10** (one taken `beq.s`) | **-70** |
> | OP_CRAM / VSRAM | 18 | 26 | +8 |
> | OP_PAL_REGION | 34 | 42 | +8 |
> | OP_PAL_RESTORE | 82 | 90 | +8 |
>
> *Why `beq` forward and not `bne` around an inlined body.* The two spellings trade the taken
> branch for the not-taken one — `beq` costs OP_SET_REG 10 and everyone else 8; `bne` with the
> body hoisted costs OP_SET_REG 8 and everyone else 10 — so shipped frequency decides. Decoded
> out of the ROM, the three OJZ raster programs carry **2 reg_set against 3 stream ops**
> (`OJZ_TestRaster` reg+cram, `OJZ_WaterRaster` reg+region, `OJZ_TestVsram` vsram), so the +8
> side is the one worth making cheap. The `beq` form also keeps two properties the `bne` form
> loses: OP_SET_REG stays the chain's FALL-THROUGH, so an unrecognised opcode still lands on
> the harmless one-word register write instead of on whichever body got promoted; and it is
> ONE INSERTED INSTRUCTION with no code motion, so all five rung displacements are byte-
> identical to master (`6720 6732 6752 675E 6774`) and every rung keeps its `.s` encoding and
> its 16/18-cycle price. The chain order is otherwise unchanged and the depth auto-derivation
> (`depth = (opcode - OP_CRAM) / 2`) survives intact.
>
> Making OP_PAL_RESTORE the fall-through instead (saving it 18 more) was weighed and refused:
> it costs +2 on every op the tree actually ships, it kills the depth derivation, and the
> decoded programs fire **zero** restores.
>
> *Size:* +2 bytes of handler code, absorbed by the fill before the next section anchor, so
> **no downstream symbol moves** (`SoundTablesZ80_Head` sits at `$8000` in both). All four ROMs
> grow by exactly **+16 bytes**, which is the deb2 entry for the one new local label
> `$engine.effects.raster$Raster_HInt$op_reg` (2575 -> 2576 symbols). No pins move.
>
> *The model re-priced itself.* Two new constants (`RASTER_DISPATCH_ZERO_HIT_CYC` 10,
> `_MISS_CYC` 8) feed `op_dispatch_cyc`; the solver re-derived every spin and the cost gate
> re-derived every expectation. Nothing was hand-adjusted. Fixture moves, measured on hardware:
> **F1 3044 -> 2624** (six reg fires, -420 = 6 x 70 — the parcel), F3 3882 -> 3862, F4 4652 ->
> 4640, F5 3220 -> 3204, F8 4640 -> 4628, F0 572 unmoved. Shipped program spins re-solved:
> `OJZ_TestRaster` 10 -> 17, `OJZ_WaterRaster` 4 -> 10, `OJZ_TestVsram` 21 -> 21 (0.8 of an
> iteration does not reach the next integer).
>
> *Realized cycles on shipped OJZ content.* Every sparse raster record fires once per frame.
> Section 0 (`OJZ_TwoChannel`) fires `[reg_sh_on, pal_region]` + `[vsram]` = one reg_set and
> two stream ops per frame: **-70 + 2 x 8 = -54 cyc/frame**. The single-program fixtures
> `OJZ_TestRaster` / `OJZ_WaterRaster` are `[reg, stream]`: **-62 cyc/frame** each.
> `OJZ_TestVsram` alone is **+8**. Against a 19,332-cycle NTSC frame the section-0 saving is
> ~0.28%, which is small because the shipped vocabulary is small — the parcel's real size is
> per-op, and it grows with the register writes a program carries. An S/H band fires two of
> them (`reg_sh_on` at the top, `reg_sh_off` at the de-mix line): those two alone go from 160
> cycles of dispatch to 20, and the band nets **-124 cyc/frame** after its ON op and its
> restore each pay the +8.
>
> *Two guards changed REACHABILITY, and both are recorded rather than patched.* (a) A
> four-reg_set fire now costs 462 against a 488-cycle line, so it FITS; five would overrun but
> five is past the per-fire op ceiling of 4, so the overrun side is stated as arithmetic on the
> model rather than as an unconstructible `fire()`. Consequence worth knowing: **no legal
> reg-only fire overruns a scanline any more.** (b) `check_landings`' LATE edge is no longer
> reachable through any legal fire — the deepest non-restore op behind the most register writes
> the ceiling allows lands at 320 against the 341 edge, two-stream-op fires always trip the
> EARLY edge first, and a restore with anything else in its fire is refused by D-B. Its poison
> now dodges the ceiling with a direct `RasterFire.Fire` construction, the way
> `poison_direct_8a` dodges `reg_set`'s own ensure.
>
> *Pins 3 and 4 were re-spelled, not re-based.* Both reproduce hardware calibrations taken on
> the OLD chain (the restore's 13, the P2 gate's measured 1-pixel spill). Rewriting their
> targets to the new arithmetic would have made them check this parcel against itself, so a
> `op_dispatch_cyc_preitem2` twin was added for them alone, pinned to the shipped function by
> the exact item-2 delta. PIN 4 gained a margin clause so the re-spelling could not be wrong
> quietly.
>
> *Evidence:* four shapes green (s4 698376 / s4.debug 713261 / demo 95696 / demo.debug 100053,
> all base+16); pytest **1069 passed / 2 skipped** (1067 baseline + the two new mirrored
> constants); expect-fail lane **17/17**; effects gate lane **18/18 PASS, exit 0**, cost row
> `F0 572, F1 2624, F3 3862, F4 4640, F5 3204, F8 4628` all matching the re-derived model;
> sweep re-run predicted -0.8 N on every boundary and measured **-0.833** (ten of twelve moved
> exactly -1, two held), with the driver printing `CENTRE N = 18` unprompted against the
> solver's independently derived 18 — see
> `docs/benchmarks/scanline-p2/HBLANK-WINDOW-SWEEP-RESULTS.md`, "Re-run — item 2".

**Tier 4 — drift the baseline would enshrine as documentation** (zero-byte, land with the parcel):
10 major comment-truth defects incl. `raster_dsl.emp:1630` trailer offset documented `8n` where
the runtime steps `10n` · `raster.emp:934` trailer described as a built 14-byte DMAEntry when it
holds parameters · `palette.emp:323` header describes a d7 dirty accumulator that does not exist ·
`raster.emp:803` EFX_RESTORE_DELAY arithmetic uses the pre-R1 SetReg cost (94, now 110) ·
`raster.emp:82` movem round trip priced at 40, actually 84 · four stale `ojz_effects.emp` fixture
notes. Plus hand-synced duplication with no gate: `BGANIM_MAX_BANDS` in four places with **no span
guard** (unlike `RASTER_MAX_PATCH`), so raising it in the generator alone lets `BgAnim_Update` walk
past the array · `RASTER_SH_BASE` a hand copy of boot's reg `$0C` byte held only by a comment
claiming pin parity it does not have · `RASTER_BUF_SIZE/2` as a bare `64` in four encoder sites ·
`raster_cost_probe.py` re-implements the wire format unpinned — and it is the instrument that
calibrates the constants `band()` enforces. Also: the effects corpus uses **zero** `assert.*`
though the engine ships that zero-byte-in-release construct at 47 sites, leaving
`Raster_BuildSchedule`'s record walk unbounded where `bg_anim` asserts the identical shape.

### Tier-3 item 6 CLOSED 2026-08-19 — the redundant SR save, and the flavour it needed

**Shipped** on `perf/raster-sr-flavour` (aeon) paired with `feat/handler-sr-flavour` (sigil).
`Raster_HInt` brackets with the new `engine.irq.ints_off_until_rte` instead of `ints_off`: the
acquire raises to IPL 7 and there is no release, because the handler's own `rte` reloads SR from
the exception frame the CPU pushed at entry. Two instructions gone, 4 bytes, 348 bytes where the
proc was 352, no branch relaxed (all 20 internal labels moved by exactly -2, every inter-label
gap identical).

**THE SIGIL HALF WAS REQUIRED, AND THE BOOKING WAS RIGHT TO FLAG IT.** Confirmed from source,
not assumed. A bare `move.w #$2700, sr` in the handler body is `User`-authored, so
`[proc.sr-undeclared]` (`lower/proc.rs`) charges it, and no honest clause absorbs it:
`clobbers(sr)` is false of a handler declared interrupt-transparent, and `preserves(sr)` cannot
be verified because nothing models `rte` restoring SR — declaring it collapses the whole
preserves clause and every movem-saved register then reports undeclared. The context bracket was
the only sanctioned spelling, and `lower_with`'s definition-site check
(`lower::sr_writes_round_trip`) hard-requires the `move.w sr,-(sp)` … `move.w (sp)+, sr` round
trip. So the pair could not simply be deleted.

**THE FLAVOUR VERIFIES RATHER THAN WAIVES**, which is the bar the parcel was given. A
`released_by_rte` context splices no release and earns two proofs instead:
`[context.rte-undischarged]` (every path out of the region must be, or fall straight onto, an
`rte` — `rts`/`rtr`/tail-out/an instruction wedged before the return all fire; an in-body `rte`
is the release taken early and is legal) and `[context.rte-acquire-pushes]` at the declaration
(an rte-released acquire may not push, because `rte` reads its frame off the stack top). Both
rules were poison-checked in the sigil suite: relaxing either arm fails exactly the tests that
cover it and no others.

**MEASURED 22 CYCLES PER FIRE, NOT THE BOOKED 30.** `move.w sr,-(sp)` is 14 nominal and
`move.w (sp)+, sr` is 16; hardware says 22 for the pair. `tools/raster_cost_probe.py`, baseline
ROM and item-6 ROM in one session:

| fixture | before | after | fires | per fire |
|---|---|---|---|---|
| F0 | 632 | 588 | 2 | -22 |
| F1 | 2684 | 2508 | 8 | -22 |
| F3 | 3922 | 3768 | 7 | -22 |
| F4 | 4700 | 4524 | 8 | -22 |
| F5 | 3264 | 3132 | 6 | -22 |
| F8 | 4688 | 4512 | 8 | -22 |
| FD1/FD2 slope | 350.0 | 328.0 | per line | -22 |

Every marginal moved by the same 22 (F1 342→320, F3 658→636, F4 678→656, F5 658→636,
F8 676→654). Zero residual, so there is nowhere a second effect could hide. This is the **third**
time this week the 68000 tables have mispriced an edit to this handler (dense-body hoist booked
24, measured 4; priming guard modelled 28, measured 30). The fixture pair is the authority.

**AND THE BOOKING LOOKED AT THE WRONG TIER.** "~30 cyc/fire" was priced against the sparse tier,
where OJZ fires a handful of times a frame. A dense line **is** a fire, so a 96-line gradient run
takes the same 22 ninety-six times: **2,112 cycles/frame**, an order of magnitude more than the
sparse side and absent from the booking.

**THE SECOND-ORDER COST, WHICH IS THE REAL WORK IN THIS PARCEL.** The prologue half moves the
op-walk origin, so `RASTER_HBLANK_END_CYC` — the distance from that origin to the line-start
sampling instant — moves with it. `tools/hblank_window_sweep.py`, same driver and fixture, both
ROMs, twice each (spread 0 across repeats):

```
baseline  boundaries N = [22, 25, 27 | 70, 73, 76]   clean 15..21   CENTRE 18
item 6    boundaries N = [24, 26, 29 | 72, 75, 78]   clean 17..23   CENTRE 20
delta                    +2  +1  +2 | +2  +2  +2                        +2
```

All four EDGE boundaries moved +2 in both groups in both repeats, so `RASTER_HBLANK_END_CYC`
goes 351 → 371 — the only value that makes the solver reproduce the driver's own printed centre
of 20 (PIN 2's standing invariant; 351 gives 18, 365 gives 19). **Twenty, where the removed
instruction costs fourteen**: the rest is the fire's earlier RETURN moving the interrupt-entry
phase, since every fire now retires 22 cycles sooner and the next IRQ4 is taken at a different
instruction boundary. Under-stating it would have aimed every burst early, which the asymmetric
margins (early 20, late 10) forgive — but the sweep is the instrument of record for this number
and it answered twice on two independent statistics.

Consequences, all re-derived rather than re-fitted: every solved spin +2 (so the eight fixture
pins move by -22 + 20 = -2, except F1 which has no spin and keeps the whole -22, 342 → 320);
`RASTER_FIRE_BASE_CYC` 302 → 280; `RASTER_DENSE_LINE_GRAD_CYC` 350 → 328; the four shipped OJZ
program spins (17→19, 10→12, 21→23 ×2) and both `band()` hand twins re-derived by hand from the
solver's arithmetic; PINs 1, 3 and 4 spelled through a new `RASTER_ORIGIN_SHIFT_ITEM6 = 20` so
each historical calibration stays pinned in the geometry it was captured in (the same device
`op_dispatch_cyc_preitem2` is for), while PIN 2 — the one that was re-measured — moves.

**A GUARD WIDENED AND WAS TIGHTENED BACK.** The reg-op density bracket used to straddle the
overrun at the FIFTH register write (302 + 5×40 = 502 > 488); with the base at 280 five now fit
(480) and the overrun arrives at the sixth (520). Restated as the pair of arithmetic bounds that
straddle it, the model's register op is pinned into **35..41** cycles against a 488-cycle line,
where the single old bound pinned it into 38..46.

**VERIFICATION.** Four build shapes green (s4 `209b5db4` / s4.debug `b7960905` / demo `f7806241` /
demo.debug `f9f8d0e5`; every ROM length unchanged, and the demo shapes move too — the demo game
links the engine handler, so the parcel is exercised in both games). pytest **1074 passed /
2 skipped** (baseline), expect-fail **17/17**, `s4lint` clean, `effects_budget_check` 21 rows
agree, warning census unchanged at 104. **`effects_gates`: OK — 22 gates, exit 0**, with the cost
gate re-deriving F0 588 / F1 2508 / F3 3868 / F4 4644 / F5 3212 / F8 4632 from the shipped
constants and measuring exactly those, and the dense row measuring 328.0 against
`RASTER_DENSE_LINE_GRAD_CYC = 328`. Zero residual on all seven.

**`ab_runner` ×4 IS NOT "ALL EQUAL", AND IT MUST NOT BE.** This is a byte-changing parcel whose
whole second half is re-solving the spins, so a value-identical A/B would mean the re-derivation
had not reached the shipped programs. Baseline ROM vs item-6 ROM over the four committed scenes:
`state_hash`, `read:active_buf` and `read:screen_l` are **EQUAL in all four**, and the only
differences anywhere are the raster program buffers' spin words —

```
above_screen / dense / mid_band   raster_buf_a,b  +019 $0A->$0C   +029 $15->$17
suppressed                        raster_buf_a,b  +015 $15->$17   +029 $15->$17
```

— i.e. the region spin 10 → 12 and the VSRAM spin 21 → 23, the two re-derivations this parcel
makes, and nothing else. Every non-program capture is identical.

**NOT DONE HERE, BY INSTRUCTION:** no refreeze. The sigil suite's six golden/pin failures
(`native_full_sonic4_debug`, `a_passing_extra_entry_moves_no_bytes`, the two `game_loop_port`
region pins, `parallax_debug_region_matches_reference`, `raster_debug_region_matches_reference`)
are all frozen-byte failures against the pre-parcel tree — a `bsr.w` displacement four bytes
shorter, and `pins::RASTER.debug_len` 882 where the proc is now 878. Nothing else in either suite
is red.

### Tier-3 item 1 CLOSED 2026-08-19 — and what it left behind

**Shipped** on `perf/raster-stream-word`. `.cram_loop`'s write is now `move.w (a1)+, -4(a2)`
instead of `move.w (a1)+, VDP_DATA`: a2 has held VDP_CTRL (`$C00004`) across that whole arm
and VDP_DATA is `$C00000`, so the port is a `d16(An)` displacement off a register already in
hand. **The item's "16" was wrong and the shipped number is 26.** 16 is the MOVE.W alone
(source `(An)+`, destination `d16(An)`); the loop's taken `dbf` is another 10, exactly as the
20 + 10 that made the old figure 30. The correct claim is **30 -> 26, and 6 -> 4 bytes**.

`RASTER_STREAM_WORD_CYC` is gone, replaced by `RASTER_STREAM_WORD_CRAM_CYC = 26` /
`_DEEP_CYC = 30` and `op_stream_word_cyc(o)`. **Region and restore cannot have the cheap
word and this is not an oversight**: both have repurposed a2 as their SOURCE cursor
(`Pal_Variant_Stage` / `Palette_Ship_Snap`), so their write has no base register left and
stays the 20-cycle absolute. Freeing one LOSES — an a1 save/restore round trip is 8 + 12 =
20 cycles against 4 saved on at most 3 words.

Measured: the 1b sweep re-run put the swept shape's clean window at N in [15.21, 22.5],
centre **19** (was [15.21, 21.5], centre 18) with the first word's crossing unmoved in all
four groups — see `docs/benchmarks/scanline-p2/HBLANK-WINDOW-SWEEP-RESULTS.md`, "Re-run
2026-08-19". The effects cost gate re-derives its expectations from the shipped constants
and the emulator agreed to the cycle: **F3 3872** and **F5 3212** (3882 / 3220 under the old
constants), with the three controls **F1 3044 · F4 4652 · F8 4640** unmoved — F4 and F8
being precisely the region and restore fixtures whose word did NOT get cheaper.

**Two riders, both booked here rather than taken:**

**(a) `RASTER_CRAM_MAX = 3 -> 4` — RESOLVED 2026-08-19 on `feat/raster-cram-max-4`. See the
closure block below this one; the proposal is kept verbatim because the measurement's whole
value is that it can be checked against what was predicted before it ran.**

**(a) `RASTER_CRAM_MAX = 3 -> 4` — a proposal, with its arithmetic.** The item claimed the
word cost is "what sets RASTER_CRAM_MAX = 3". It is not, quite: what set 3 was Ruling 2a's
pre-sweep estimate of "~60 usable cycles" (`raster.emp:80`), and the 1b sweep MEASURED the
window at 122.9 cycles, which supersedes it. Against the guard that actually binds today
(`raster_dsl.emp`: widest single burst + both margins <= the window),

| ceiling | CRAM class (26) | deep class (30) |
|---|---|---|
| 3 (today) | 2x26 + 30 = 82 vs 122.9, slack **40.9** | 2x30 + 30 = 90 vs 122.9, slack **32.9** |
| 4 | 3x26 + 30 = 108 vs 122.9, slack **14.9** | 3x30 + 30 = 120 vs 122.9, slack **2.9** |
| 5 | 4x26 + 30 = 134 vs 122.9, **REFUSED** | 4x30 + 30 = 150 vs 122.9, **REFUSED** |

So **4 is placeable for the CRAM class with 1.5 iterations of slack, and only barely for the
deep class** — 2.9 cycles is under the instrument's own +-5-cycle boundary resolution, i.e.
indistinguishable from zero. A ceiling raise is therefore not one decision but two: raise it
for cram/vsram and leave region/restore at 3, or raise both and accept a deep 4-word burst
whose margin the sweep cannot confirm. The payoff is real — a full 16-colour line goes from
`ceil(16/3) = 6` fires to `ceil(16/4) = 4` — but it needs its own parcel: `RASTER_CRAM_MAX`
is a single constant today with a hard `ensure(== 3)` pin, four constructor guards, a
`RASTER_BUF_SIZE` interaction (a wider op is a longer program), and it would want the sweep
re-run against a 4-word fixture rather than argued from the table above. **Do not raise it
inside another parcel.**

### Rider (a) CLOSED 2026-08-19 — measured, and the answer is NO (with a constant re-derived on the way)

Branch `feat/raster-cram-max-4`. The proposal asked for a fixture before a raise. It got one,
the fixture said no, and getting there turned up a wrong constant.

**The fixture.** `tools/hblank_window_sweep.py` grew a `--words` input: it authors the burst
directly in wire, so the constructors' `ensure` is not consulted. Three widths, four sampling
periods each, pooled least squares.

**THE ANCHOR WAS WRONG, and this parcel's own instrument bug is why.** The sweep's fold used to
estimate the sampling period from the group FIRST boundaries and subtract it from the group LAST
boundaries — two different statistics, disagreeing by up to 0.33 N, accumulating a full N of
error by the fourth group. Item 6 validated `RASTER_HBLANK_END_CYC = 371` partly against that
fold's printed centre, and PIN 2 then locked it in because both sides shared the error. Re-fitted
as a least-squares line through (group index, crossing) over **12 independent groups**:

```
crossing 28.200 N   period 48.867 N (H40 arithmetic 48.857)   s.e. 2.0 cyc
RASTER_HBLANK_END_CYC = 70 + 14 + 10 * 28.200 = 366
```

The delta agrees independently: pre-SR the same fold gives 26.50 N = END 349, so item 6 really
costs +1.70 N = 17 cycles, and 349 + 17 = 366. Item 6's "+2 everywhere" is that same 1.7 read
through a method that can only report integers. Provenance: 351 -> 371 -> **366**.

**THE 4-WORD ANSWER, at the re-derived anchor.** The binding edge flipped from late to early:

| width | solved spin | early slack | late slack |
|---|---|---|---|
| 3 | 19 | **+10.9 cyc** | +30.0 cyc |
| 4 | 18 | **+0.9 cyc** | +14.0 cyc |
| 5 | 17 | -9.1 cyc | -2.0 cyc |

Decision rule, fixed before the number was known: the raise stands only if the binding margin
clears both 2 s.e. (4.0 cyc) and the 2.9-cyc threshold the DEEP class was refused on. **0.9
clears neither. `RASTER_BURST_MAX_CRAM` stays at 3.** The arithmetic still admits 4 with 14.9
cycles to spare, and that is the trap this closes: a fit check asks whether the span FITS, not
where the solver's rounding PUTS it. Necessary, not sufficient.

**What shipped anyway** — a SPLIT, because one constant was carrying three unrelated facts:

- `RASTER_BURST_MAX_CRAM = 3` — cram/vsram, the 26-cycle `.cram_loop` word. The class with
  headroom (14.9 cyc of arithmetic slack); a raise is one token whenever the evidence arrives.
- `RASTER_BURST_MAX_DEEP = 3` — region/restore, the 30-cycle word. 2.9 cyc of slack, no headroom.
- `RASTER_DENSE_WORDS_PER_LINE = 3` — `.dense_body`'s three inlined `move.w`. Never a ceiling;
  under the old name a ceiling move would have silently resized `OJZ_GradientStream`.

Two constants at the same value are still two constants: different word costs, separate
placeability ensures, different futures. `fire()`'s ceiling is the dearest class present
(`op_burst_max`, folded with a minimum). `RASTER_STREAM_WORD_MAX_CYC` is DELETED — it existed
only so ONE guard could reason about ONE ceiling with TWO word costs.

**NOT ZERO-BYTE — the anchor moved, so five shipped spin words moved.** The byte diff against
the pre-change ROM is exactly six words: the five solved spins, each -1, plus the header
checksum. No code, no lengths, no relocation.

| offset | old -> new | shape |
|---|---|---|
| `0x00018E` | `2E20` -> `2E1B` | header checksum |
| `0x012CAE` | 19 -> 18 | OJZ_TestRaster |
| `0x012D38` | 12 -> 11 | OJZ_WaterRaster |
| `0x012FB4` | 23 -> 22 | OJZ_TestVsram |
| `0x0130DE` | 12 -> 11 | OJZ_TwoChannel region |
| `0x0130EE` | 23 -> 22 | OJZ_TwoChannel vsram |

Of the seven cost-model fixtures, **five re-rounded and two did not** (F6 and F8 held) — a
5-cycle shift is half an iteration, so whether a shape re-rounds depends where its ideal spin
sat inside its iteration. Anyone reading "the anchor moved 5, so everything moves" off the
arithmetic would have got two wrong; the pins are what make that visible.

**CRCs.** s4.debug `b7960905` -> **`d22dda85`**, s4 `209b5db4` -> **`cdabf8a3`** (both lengths
unchanged). demo.debug `f9f8d0e5` and demo `f7806241` **unchanged** — demo authors no raster
programs. **A refreeze is required at landing.**

**Verification.** pytest 1074 passed / 2 skipped; expect-fail **19/19**; `effects_budget_check`
22 rows; effects gates **22/22**, cost row `F0 588 F1 2508 F3 3818 F4 4584 F5 3172 F8 4632`
model == hardware to the cycle (F3 -50, F4 -60, F5 -40 = one spin iteration x each fixture's
fire count; F0/F1/F8 unmoved), dense 328.0 cyc/line. `ab_runner` on all four committed scenes,
pre vs post: `state_hash` **EQUAL** on every scene, `screen_l` and `active_buf` EQUAL, and the
only differing capture is the program image at the two spin offsets — the intended change and
nothing else.

**Two things this did NOT do, deliberately.**
1. Neither class was raised — see the decision rule above. The cram class keeps its headroom
   and its own constant; only the evidence is missing.
2. `band()` cannot carry an ON op wider than the DEEP class — the restore is derived from the ON op's span, so a
   4-word `stream_cram` reaches `pal_restore` with count 4 and is refused there. Restoring
   three of four entries would leave the fourth tinted for the frame, which is worse than not
   building the band. A 4-word cram is authorable as a plain fire, not as a band. **If the
   deep class ever gains a word, this restriction lifts with it and not before.**

**(b) `.dense_body` / `.ramp_body` get the same treatment — and this is where the SHIPPED
cycles actually are. CLOSED 2026-08-19 on `perf/dense-body-addressing`; the closure block
follows the proposal, which is kept verbatim because its explicit "do not book 12" caveat is
the thing the measurement overturned.** Item 1 as scoped touches only the sparse `.cram_loop`, and the
measured saving on today's OJZ content is **4 cycles a frame** (section 0's one `stream_vsram`
word, section 1's one `stream_cram` word; the tint band and the water boundary are region ops
and save nothing). The dense tier is the opposite: `.dense_body` writes three
`move.w (a1)+, VDP_DATA` and `.ramp_body` one `move.w d1, VDP_DATA` **every line of a run**,
a2 is VDP_CTRL at both sites, and `-4(a2)` takes them 20 -> 16 and 16 -> 12. That is
**12 cyc/line** for a gradient run and 4 for a ramp — for `OJZ_TestGradient` at 96 lines,
~1,150 cyc/frame, three orders of magnitude more than item 1 bought on live content.

Why it was NOT taken here: the dense burst carries **no spin and no cost model**, so nothing
build-time prices it and nothing in `tools/effects_gates.py` observes its timing (the three
committed scenes are sparse-tier). The safety argument is good — the FIRST write does not
move, and words 2 and 3 move EARLIER, so they stay strictly inside `[word 1, word 3 old]` and
cannot leave the window on either side — but "good argument, no instrument" is exactly the
shape this tree has been burned by. It needs a dense-tier gate (or a sweep fixture that
drives `OP_RUN_GRADIENT`) first, and then it is a three-token change.

### Rider (b) CLOSED 2026-08-19 — the change was three tokens, the caveat was the interesting part

Branch `perf/dense-body-addressing`, cut from master `6c341697`. The rider had been passed over
twice: once for want of an instrument, and once — by Tier-3 item 3, which built the instrument —
with an explicit instruction not to book 12 cyc/line, because that parcel had watched a
nominally-12-cycle removal measure 4. **The instrument was built, the edit was made, and it
measured the full 12.** Both facts are true and they are not in conflict; naming why is worth
more than the cycles.

**THE SAFETY ARGUMENT, RESTATED AGAINST TODAY'S CODE.** `Raster_HInt` does `lea VDP_CTRL, a2`
in its prologue (`raster.emp`, immediately after the `movem`) and nothing on the dense path
reassigns it: `.dense_body` and `.ramp_body` both open by writing the arm word and the command
longword THROUGH `(a2)`, and the only `lea` that repurposes a2 is `.op_pal_restore`'s, on a
different arm, restored before that arm exits. So `-4(a2)` is `$C00000` = VDP_DATA at both
sites, verified in the emitted listing and not merely in the source. The timing argument is
about WHEN each write lands: a destination extension word is prefetched ahead of the write it
belongs to, so the cycles the short form stops paying fall AFTER that write. The first stream
write does not move; writes 2 and 3 move earlier by 4 and 8; all three stay strictly inside
`[first write, old third write]`, so the burst contracts from its own tail and cannot leave the
blanking window on either side. `.ramp_body` has a single write, which therefore does not move
at all. **And the argument was not trusted on its own** — the dense scene gate re-ran green and
the sparse 1b sweep came back bit-identical (below).

**PREDICTED vs MEASURED.** Nominal: 3 × (20 − 16) = 12 cyc/line gradient, 1 × (16 − 12) = 4
cyc/line ramp. Predicted after applying item 3's absorption ratio (nominal 12 → measured 4,
confirmed in the other direction by that parcel's cost-gate poison): **~4**. Measured on the
FD1/FD2 pair: **12**, exactly.

| | FD1 (8 lines) | FD2 (40 lines) | slope | intercept |
|---|---|---|---|---|
| before | 4136 | 14632 | 328.0 | 1512 |
| after | **4040** | **14152** | **316.0** | **1512** |

The intercept is the control: unchanged, so the whole delta is per-LINE and the per-RUN fixed
cost did not move. The full five-count sweep was re-run rather than re-scaled — 8/40/80/96/120
gave `4040 / 14152 / 26792 / 31848 / 39432`, i.e. `1512 + 316 × lines` to the cycle at every
count, with fires = lines + 5 at every count, and every leg down by exactly `12 × lines`.

**WHY THE ABSORPTION DID NOT APPLY, which is the durable half.** Item 3 removed a
`tst.w (xxx).W` sitting directly behind `move.l Raster_Dense_Cmd, (a2)` — an OPERAND access
issued while the CPU was already stalled on a control-port write, so it rode a wait the CPU was
serving anyway. This parcel removes one INSTRUCTION-STREAM word per write. The 68000 fetches
those on its own account and no VDP wait pays for them. So the standing warning — "nominal
over-predicts any edit in `.dense_body`" — survives but with a narrower scope: **the bus
absorbs adjacent data accesses, not code size.** Neither result was derivable from the other,
and the FD pair is still the only thing that can settle a third case.

**On shipped content**, at the dense scene's camera state: the HBlank row for the live
`OJZ_TestGradient` reads **31665 cyc/frame (24.7%)** where the same script reads **32812** on
the pre-parcel ROM (the row previously recorded 32758 — that state carries ~50 cyc of
boot-to-boot spread, unlike the poked fixtures, which are exact). −1147 against 96 × 12 = 1152
predicted. The row's long-standing model gap is **unchanged**: −183 now, −188 same-instrument
before, so this parcel neither caused nor cured it.

**Constants moved:** `RASTER_DENSE_LINE_GRAD_CYC` 328 → **316**; `effects_budget_model.toml`'s
`[raster.dense]` `per_line_body_cycles`, `dense_run_cycles_per_frame`, `dense_run_frame_pct`,
`dense_line_sweep`, `full_frame_fraction_ntsc`, and `[raster.sparse]`'s
`hint_total_dense_*` rows, all with the superseded values kept beside them.
**The solver does not read any of them** — re-verified, not assumed: the only in-tree
references to `RASTER_DENSE_LINE_GRAD_CYC` are its own `< RASTER_SCANLINE_CYC` `ensure`, the
effects-gate cost row, and one comment. The dense tier has no ops, so no blanking spin is
solved against it and not one solved spin re-derives. There is no ramp cost constant to
update — the dense tier's only cost term is the gradient one.

**Per-proc bytes — `Raster_HInt` 348 → 340 (−8) in ALL FOUR shapes**, which is exactly the four
instructions' 2 bytes each. Nothing ahead of `.dense_body` moved by a single byte, so no
dispatch rung's displacement changed and none relaxed (the trap `RASTER_DISPATCH_RUNG_CYC`'s
note warns about). `.dense_body` 44 → 38, `.ramp_body` 34 → 32. Downstream the shift is
absorbed by placement fill and **every ROM length is unchanged**: s4.debug 107 symbols at −8,
absorbed at `Level_LoadArt`; s4 the same −8 to `Level_LoadArt`, then −16 to the hard `$8000`
`SoundTablesZ80_Head` anchor (an alignment pad released a further 8); demo.debug −8 then −16 to
`ObjCodeBase` at `$10000`; demo −8, absorbed at `Level_LoadArt`.

**CRCs (all four lengths UNCHANGED).** s4 `cdabf8a3` → **`e111dff7`** (698411) · s4.debug
`2d365501` → **`06af0010`** (713863) · demo `f7806241` → **`aae04929`** (95733) · demo.debug
`183587b5` → **`82884c07`** (100152). The demo shapes move because the demo game links the
engine handler; **demo has no dense content** — `games/demo` contains zero references to
`gradient` / `OP_RUN_*` / any raster-program constructor, so `Raster_Program` is never given a
dense program and `.dense_body` is dead code there. That is the check, and it is why no demo
boot witness was taken. **A refreeze is required at landing.**

**Verification.** pytest **1092 passed / 2 skipped** (baseline) · `emp_expect_fail` **20/20**
(baseline) · `effects_budget_check` **31 code-derived rows agree** · warning census
**unchanged** in both sonic4 shapes (release 112, debug 107, each re-measured against a
reverted-source build in the same tree) · **`effects_gates`: OK — 23 gates, exit 0**, with the
sparse cost row re-derived and measured at `F0 588 F1 2508 F3 3818 F4 4584 F5 3172 F8 4632`
(unmoved, as a dense-path-only edit requires) and the dense row at `FD1 4040/13 FD2 14152/45 ->
316.0` against the new constant. `scene:dense` stayed green without re-derivation, as predicted:
its assertion is `Raster_Dense_Cursor == stream + lines * 3 words`, a WORDS-CONSUMED equality,
and the addressing mode does not change how many words `(a1)+` consumes.

**`ab_runner` ×4 IS "ALL EQUAL", and here it must be** — this is a value-identical parcel, the
opposite of item 6. OLD (`2d365501`) vs NEW (`06af0010`) over all four committed scenes,
`--selfcheck` clean on each: `state_hash`, both raster buffers, `active_buf`, and `screen_l` /
`dense_state` **EQUAL on every scene**, dense included. The **1b sweep** was re-run on both ROMs
at the default range and at `--hi 200 --rows 12`, and the raw JSON records are **identical
apart from the file paths and the wall clock** — sparse boundaries did not move by one N, which
is what a dense-path-only edit is supposed to look like. *(Instrument note, NOT this parcel:
both sweep runs fold to a single boundary group and print `=> NO-GO` for the solver fit. That
output is byte-identical on master, so it is a pre-existing property of the tool's default
invocation, not a regression here — but it does not reproduce the item-1 closure's four-group
fold, and somebody should find out why before the sweep is cited again.)*

**Still open, unchanged:** the two-trailing-fires rider above (~600 cyc/frame, NOT
value-identical, needs its own parcel) and the cursor-reload half of the item-1 rider, which
`-4(a2)` cannot serve — a2 holds the VDP port, and `Raster_Dense_Cursor` is a RAM long with no
base register in hand.

**DO NOT RE-LITIGATE (refuted):** "`RASTER_FIRE_BASE_CYC` omits the 44-cyc IRQ4 entry, so
check_density is unsound" (`raster_dsl.emp:991`, filed major) is **REFUTED** — 302 is not a
post-entry figure; it derives from fixture F0's *absolute measured* 572 cyc for two priming
records (`docs/benchmarks/effects-p3/DENSITY-EVIDENCE.md:73`). An HInt invocation inherently
includes its own exception entry; the model is entry-inclusive.

**New angle on booked EFX-4b:** static programs may need no RAM copy at all — walk the ROM
template directly, dissolving the over-read rather than patching it.

### Substrate item 3 CLOSED 2026-08-19 — the hazard is real, the diagnosis was wrong, and the booked fix was impossible

Branch `fix/raster-frame-epoch`. The booking asked for a reproduction FIRST and for the fix to
be abandoned if the instrument contradicted the source argument. The instrument contradicted
*half* of it, which is why this block is longer than a closure note.

**The instrument.** `tools/raster_frame_epoch_probe.py`. Two execution breakpoints —
`Raster_HInt` and `Raster_VBlank` — turn a frame into an ordered event list, and every stop
carries `Raster_Cursor` read BEFORE that fire consumes its record, so a healthy frame reads
`[2,6,10]` (priming 0, priming 1, the event) and a schedule that has slipped reads something
else. Fixtures are poked straight into `Raster_Buf_A` (the cost probe's discipline) because
the constructors exist to make the hazardous program unauthorable. Two instrument facts cost
real time and are written into the tool's header: `frame_token` does not advance in a headless
instance (frames are grouped by the game's own `Frame_Counter`), and **resuming from a
breakpoint's own address re-breaks without executing** — 24 rising `hits` with the machine
frozen, which would have produced a confident "no hazard" on a CPU that never ran an
instruction.

**WHAT THE MEASUREMENT REFUTED — line 223 was never the hazard.** Sparse fires authored at
222, at 223 and at **224**, and the dense run `220..223` (i.e. exactly the `top + lines == 224`
case both constructors were tightened to forbid), all retire BEFORE the rewind, every frame,
with an identical `[2,6,10]` cursor walk. The VDP raises the last active line's HINT far enough
ahead of VINT that the 68000 takes IRQ4 first. The `<= 223` bound was not standing between the
engine and this defect.

**WHAT IT CONFIRMED — the mechanism, once the real precondition is supplied.** The precondition
is a MASK WINDOW straddling the VINT instant with an IRQ4 already raised, not a line number.
The probe's `stall` fixture forces it with no engine change: fire 1 at line 222 carries a poked
blanking spin (~4,000 cycles at spin 400), so `Raster_HInt` holds IPL 7 across VINT while fire
2 at line 224 is raised inside that window; at fire 1's `rte` both are pending, IRQ6 wins, and
the IRQ4 is serviced after `Raster_VBlank`. Measured, pre-fix:

| fixture | cursor walks per frame |
|---|---|
| stall 222(spin 2)+224 — control | `[2,6,10,26] x4` uniform |
| stall 222(spin 400)+224 | `[2,6] x3` and `[2,6,10] x2` — **alternating, a fire lost every other frame** |
| stall 222(spin 1000)+224 | `[2,6] x3` and `[2,6,10] x2` |

Real code reaches the same state through any `ints_off` bracket straddling the end of active
display — the VDP-access invariant at the top of `raster.emp` mandates such brackets around
every main-loop command pair.

**WHY THE BOOKED ONE-BYTE FRAME-EPOCH FLAG CANNOT BE BUILT.** A stale fire and the legitimate
line-0 fire see BYTE-IDENTICAL engine state: same cursor, same counter, same everything the
rewind just wrote. Any flag that self-clears on the first fire consumes the line-0 fire in the
healthy case and shifts the whole schedule down a line; a flag cleared by the main loop is not
reached before line 0 on a lag frame, turning the guard into a whole frame of lost effect. The
only thing that separates the two fires is WHERE THE BEAM IS, so the discriminator has to be
the beam. Two other candidates were built and rejected with evidence rather than argued away:
deasserting IE1 in `Raster_VBlank` to cancel the pending HInt (built, shipped to the emulator,
**did not work** — oracle's VDP recomputes the IPL line state only on interrupt acknowledge,
not on an IE1 change, `S315-5313_Ports.cpp:1931`), and idling the RAM trampoline slot (correct
but needs a release point after VInt's `rte`, which only the main loop offers, i.e. the lag
hole again).

**WHAT SHIPPED.** `Raster_HInt`'s no-op-record arm becomes `.priming` and reads the HV counter
at `$C00008` (a displacement off the `VDP_CTRL` already in a2, the same trick `.cram_loop` uses
for `VDP_DATA`). `V >= RASTER_VBLANK_V` means outside active display, so the fire is stale:
restore the every-line arm word this record just clobbered and return WITHOUT advancing the
cursor. Not `RASTER_ARM_PARK` — that leaves reg `$0A` at 255 and kills the next frame, the
opposite of a fix. The HV counter and not the status register's VBlank bit: reading `VDP_CTRL`
resets the command-latch write-pending state and clears the status F flag, and status bit 3
also reads set whenever the display is off, which would retire every fire during a fade.

**THE COST, MEASURED, AND THE SOLVER DOES NOT RE-DERIVE.** The guard sits on the arm a record
WITH ops never reaches, which is the whole point. `tools/raster_cost_probe.py` on the same
scene either side: F0 572→632, F1 2624→2684, F3 3862→3922, F4 4640→4700, F5 3204→3264,
F8 4628→4688, FD1 4362→4422, FD2 15562→15622 — **every fixture +60, i.e. two priming fires at
30**, while every marginal per-fire figure came out byte-identical (F1 342.0, F3 658.0,
F4 678.0, F5 658.0, F8 676.0, dense slope 350.0). So `RASTER_FIRE_BASE_CYC` stays 302, the
op-walk origin does not move, `RASTER_HBLANK_END_CYC` stays 351, **not one solved blanking spin
changes**, and the 1b sweep boundaries are predicted UNCHANGED. The 30 is now
`RASTER_PRIMING_GUARD_CYC` in `raster_dsl.emp`, read separately from the base by
`effects_gates.py` so a guard that migrated into the prologue would leave F0 right and every
other fixture 30 cycles light. Nominal predicted 28; hardware said 30, the same direction as
the dense-body hoist's missing eight.

**THE `<= 223` BOUND STAYS, for a NEW reason.** Not defence in depth against the original
(refuted) derivation: the interlock's discriminator IS the line, so a run authored to put a
fire at 224 would be authoring real work into the region the interlock reads as stale. The
bound and `RASTER_VBLANK_V` are one fact and are pinned together by an `ensure` beside
`RASTER_MAX_FIRE_LINE`, verified red-first (at 225 the build fails with the named message and
the expect-fail lane reports the extra diagnostic). **Relaxing the bound to 224 is therefore
NOT open as a follow-up** — it would have to move the threshold too, and the threshold has
nowhere to go: 224 is where active display ends. Booked here so it does not read as slack.

**Residual, deliberately not fixed:** the retired fire's ops do not run. They cannot — its line
has already gone by, and discarding it is the same outcome the booked park design wanted. What
the interlock protects is the SCHEDULE, and it does: post-fix, the stall fixtures read
`[2,2,6,10]` uniformly (the stale fire retiring on cursor 2 without advancing, then the frame's
own `2 -> 6 -> 10` walk completing) on every frame instead of alternating.

**VERIFICATION.** Four shapes, all building — `s4.debug` 896a35c8/713279 -> 72ab53aa/713295 ·
`s4` cf54b017/698393 -> 1e230133/698411 · `demo.debug` 31a87100/100070 -> 25eaed93/100086 ·
`demo` f16d1a50/95713 -> deacc756/95733. Per-proc: `Raster_HInt` +20 bytes, everything after it
in the section +20 and the rest of the image +16 (placer fill absorbed 4); of 900 common
symbols, 72 moved and **zero RAM symbols moved**. pytest **1074 passed / 2 skipped**.
expect-fail **17/17**, plus the new `RASTER_VBLANK_V` pin verified red-first (at 225 the build
fails with the named message and the lane reports the extra diagnostic). Effects gate lane
**22/22 PASS, every segment exit 0**, cost row `F0 632 F1 2684 F3 3922 F4 4700 F5 3264 F8 4688`
measured == expected and the dense row 350.0 cyc/line. `ab_runner` on all four committed
scenes, pre-fix ROM vs post-fix: **ALL EQUAL (gated)**, `state_hash` included. The 1b blanking
sweep's anchor captures are **byte-identical** pre vs post (39 comparable lines, 0 differing),
which is the boundaries measured unchanged rather than merely predicted.

**INSTRUMENT NOTE for whoever runs the gate lane next.** ~~Two full-lane `effects_gates.py`
invocations WEDGED — one inside `snapshot_poison`, one inside `raster_source` — while both of
those gates pass in seconds run standalone on the same ROM, and `raster_source` then passed in
the segmented re-run. That is the known intermittent oracle stop-race, not a gate failure, and
a single 22-gate invocation loses every result to it. Running the lane as `--only` segments
with a per-segment timeout and one retry recovers all 22; consider making that the lane's own
shape rather than a thing each session rediscovers.~~

**CLOSED 2026-08-19** (`fix/gate-lane-segments`, tools-only, zero ROM bytes). The suggested
shape IS the lane's shape now: a plain `effects_gates.py` invocation partitions the gates into
**10 segments** — every emulator-backed gate on its own, the two listing-only gates sharing
one — re-invokes ITSELF once per segment with `--only`, and aggregates into the identical
`effects_gates: OK — 22 gates` line and exit code the single-run shape produced. Per segment:
a timeout (~8-35x measured runtime), **ONE** retry, and a segment that wedges twice becomes its
own named `WEDGED after retry` FAILURE row — loud on unmeasurable, never silence, never a pass.
`--only` is untouched: it still runs in-process, and it is what the segments themselves use.

Three details worth keeping:
- **The partition is DERIVED** from `gate_registry()`, the same registration `--only` validates
  against, and `wanted()` records every name the body asks about so any run fails on registry
  drift. A hand-kept second list of gate names would have been the copied-expectation defect,
  and its failure mode is the quiet one — an unscheduled gate looks exactly like a passing one.
- **The pre-retry reap matches by argv TOKEN**, never `pkill oracle_gui` (that mistake was made
  twice on 2026-08-19). Several worktrees run this lane at once; a bare pkill kills another
  session's emulator mid-measurement, which looks exactly like the wedge it was cleaning up
  after. Verified live against three concurrent foreign instances.
- **The wedge reproduced during this parcel — twice, unprompted.** First while runtimes were
  being measured: `snapshot_poison` hung for 642 s with its oracle_gui alive, then ran clean in
  10 s minutes later. Then, better, DURING the verification run itself:

      [ 6/10] raster_source   WEDGED at 240s — retrying once (reaped oracle_gui [3323042] for this ROM)
      [ 6/10] raster_source   PASS   13.5s  1 gate(s)
      ...
      effects_gates: OK — 22 gates          (exit 0)

  That is the fix working on the real disease rather than on the poison: the same invocation
  that would have printed nothing and lost all 22 results under the old shape absorbed the
  wedge, reaped the orphan, and reported a complete green lane.

---

## `.emp` has no spelling for a CLOSURE EDGE — the bare `use` idiom collides with a lint (booked 2026-08-18, scanline-P1 Task 10)

**The idiom.** A zero-emitting module (a guard module, a witness, an equivalence proof) can
never take a row in sigil's ModuleSpec registry — that list carries byte-EMITTING modules
only, and it is what seeds the synthesized entry closure. So the ONLY way to pull such a
module into a profile's `use` closure is a **bare whole-path `use <module>`** from a module
already in the closure. `--extra-entry` does not do it: that adds an edge to one invocation
(the expect-fail lane's per-poison build), leaving the module dark on a normal build.

Two ship today, both deliberate, both irreplaceable:
- `games/sonic4/data/effects/ojz_effects.emp` → `use games.sonic4.scene_registry`
- `games/sonic4/test/ojz_scroll_test.emp` → `use games.sonic4.scene_equiv_proof`

**Why neither can be spelled another way** (both measured, not assumed):
- A **name list** does not create the edge. Without the bare `use`, the registry's
  capability-subset ensure and everything in `scene_dsl.emp` behind it go dark.
- A **glob** on the witness would re-evaluate its twenty `EQ_*` consts in the CONSUMER's
  scope — the const-clone behaviour Task 5 measured (a selective/glob import of a const
  injects a clone whose initializer re-runs at the consumer, producing diagnostics at a span
  inside a module that never elaborated).

**The gap.** sigil's `[import.no-names]` lint reads a bare whole-path `use` as "you probably
meant to import names" — reasonable for the accidental case, wrong for this one. It is now
**baselined for all five sonic4 shapes** (sigil `crates/sigil-cli/tests/warn_tier_corpus.rs`,
`WARN_ID_BASELINE`), which means **a genuinely accidental bare `use` in sonic4 now hides
behind these two.** Demo authors no scenes, so its rows stay empty and remain a live control
on the id.

**The fix is a SPELLING FOR THE IDIOM, not a wider baseline.** Options, unranked:
1. A distinct syntax (`use <module> for closure` / an attribute) the lint recognises and the
   resolver treats as an edge-only import — most honest, sigil-side parser work.
2. Let the registry carry zero-emitting modules with a null section, so a witness takes a row
   like any other module and needs no edge at all. Removes the idiom rather than naming it.
3. A per-site suppression comment. Cheapest, weakest — it makes each site auditable without
   making the intent expressible.

Until one lands, **treat a new `import.no-names` firing in sonic4 as unreviewed**: the id-set
gate can no longer tell you about it. The bidirectional gate still catches a shape that STOPS
firing, so a removed closure edge is still loud.

**Related, same session:** `[layout.odd-field]` fired on `Scene`'s two `i16` bridges once the
module reached the closure. Padded rather than baselined (`engine/level/scene_dsl.emp`) — the
struct is comptime-only so it cannot fault today, but a baselined warning would not be there
on the day something emits a `Scene`.

---

## Scanline Services P1 tail — three items booked at the merge (2026-08-18)

P1 shipped byte-identical (`docs/benchmarks/scanline-p1/GATE-EVIDENCE.md`). These are the
follow-ups it deliberately declined mid-parcel.

### 1. The two byte-identity BRIDGES — hygiene, normalize only with a deliberate refreeze

`Scene` carries `layer_mask_raw` and `v_deform_shift_raw` (both `-1` = derive). They are
**not features**. They exist because three shipped configs hand-wrote a value the model
would otherwise derive differently, and P1's gate was byte identity:

- `layer_mask_raw: $1F` on **`OJZ_Default` and `OJZ_Underwater`** — both `band_count: 4`
  with a mask whose bit 4 is set for a layer that does not exist. Exactly two users.
- `v_deform_shift_raw: 0` on **`SkyHaze`** — the shipped header sets `v_deform_shift_bg: 0`
  with no V-table, while `SceneVDeform.None` lowers to the runtime default shift 4.

**`OJZ_LockedClouds` deliberately does NOT use the mask bridge** — its `$1E` DERIVES from
`enabled: 0` on layer 0, verified. The migration plan prescribed a bridge there and was
wrong; a bridge used where derivation works is a guard surrendered for nothing.

Normalizing any of the three is a **byte-moving change**: it needs its own parcel, a repin,
and a `refreeze --freeze --ab` with emulator evidence. Cheap, but not free, and not to be
done incidentally. Guarded meanwhile: the mask bridge may only ADD bits the model cannot
derive (superset ensure), and both are range-fenced (`-1..$FF`, `-1..15`) because a wider
value wraps the i16 field and silently reads back as "derive".

### 2. Move `engine.level.scene_dsl` into sigil's `COMPTIME_HELPERS` — PAIRED aeon+sigil

`scene_dsl` is the only authoring DSL in its family NOT in the helper set
(`sigil crates/sigil-harness/src/native.rs` — `parallax_dsl`, `palette_dsl`, `raster_dsl`
all are). Joining it would: delete the glob-import requirement on every scene module, let
the ten `pub` accessors go private, and return the inlined literals to names.

**The real argument is gating, not ergonomics.** Membership subjects the set to
`tools/emp_helper_closure.py`, which exists to prove helper names are disjoint. Nothing
currently gates a hand-written glob against collisions — and this DSL injects names as
generic as `layer`, `scene`, `no_layer` into game modules. **The collision is not
hypothetical: `band` had to be renamed `cfg_band` across 44 sites** during P1 because it
collided with `raster_dsl.band`, a helper already glob-injected everywhere, and `.emp` has
no `as` alias. Staying out is the UNGATED option; joining is the gated one.

Correctly declined mid-parcel (a paired change during a byte-identity migration); correctly
owed now.

### 3. sigil language defect — an `if` in BLOCK-TAIL position evaluates to UNIT

`if a { 1 } else { if b { 1 } else { 0 } }` silently yields `()` whenever only the inner
test is true. **No diagnostic.** Measured twice. It mis-folded a capability mask to `0`
during P1 Task 3 and was caught ONLY because the expected value had been derived
independently rather than read off a neighbour.

This is a general trap for every `comptime fn` in the tree, not a scene_dsl issue. Workaround
in use: a flat accumulator over statement `if`s. A single-level if-expression is fine; a call
in tail position is fine.

**Sibling traps found the same parcel, same species (silent, wrong-value-not-error):**
`d0`-`d7` / `a0`-`a7` are register tokens even in comptime code, so `let d0 = ...` binds a
register and the error points at the CALL SITE, not the binding · an unknown name in a Label
position does not error, it becomes a link extern and compares unequal (a typo surfaces as a
field mismatch, never as "unknown name") · Label equality at comptime is SYMBOL IDENTITY, not
content, so two byte-identical tables under different names compare unequal.

---

## THREE 2026-08-13 LENS PACKETS — landed 2026-08-18, findings UNADJUDICATED

Merged from `review/{sound,system,tools}-lens-sweep`, where they had been invisible for five
days. **Landing them made them discoverable; NOTHING in them is fixed.** Review SHA
`ffe05158`, 15 seats each, overseer-verified.

- `docs/superpowers/notes/2026-08-13-sound-lens-sweep.md`
- `docs/superpowers/notes/2026-08-13-system-lens-sweep.md`
- `docs/superpowers/notes/2026-08-13-tools-lens-sweep.md`

### ⚠ THREE CRITICALs in the tools packet, and they threaten the LEVEL DATA

**tools D1 — `regenerate-level.sh` is a DESTRUCTIVE NO-OP. Do not run it.** It runs
`import_sk_collision.py` FIRST, which unconditionally overwrites the ROM-consumed
`data/collision/{heightmaps,angles,solidity}.bin` with the base S&K bank, and only THEN hits
`ojz_strip_gen.py generate` → `require_donor()` → `SystemExit`. `set -euo pipefail` with **no
trap**, so it aborts having already clobbered the tables. Verified: `data/collision/` DIFFERS
from `collision/base/` today, i.e. the tree is in the interned state and one invocation of
the documented re-bake destroys the pairing. Player result: every solid surface resolves to a
different height profile, angle and solidity class. `grep -c collision tools/verify_level_bin.py`
= **0** — the gate never looks. The in-file safety story ("only DEFAULTS —
`gen_collision_data.generate()` overwrites them") is wrong twice: that function does not
exist, and the tool that would overwrite them cannot run.

**tools D2 — the re-bake cannot run at all, and the PROVENANCE is the finding.**
`project.json`'s tileset points at `ojz_tiles.bin`, which is missing and `.gitignore`d. A
deliberate fix (`f2371ca0`, 2026-06-11) was reverted the NEXT DAY by an editor state save
(`586cd3fa`) that the **auto-commit daemon landed unreviewed**. The editor rewrites
`project.json` wholesale on save, so **any repo-side correction to an editor-owned field has
a shelf life of one editing session.** That is an active drift vector, not a stale file — two
months of a dead re-bake path followed from it. `build.sh`'s `STRESS_ART=1` shape is dead too.

**tools D3 — the obvious repair of D2 detonates a silent blank-level bake that every gate
passes.** So the naive fix is worse than the bug. Read D3 before touching D2.

**tools D4/D5:** the "ROM Build" gate has never built the ROM it asserts about; the
build-fatal lint gate lints one file that emits no bytes (path bug).

### System packet — S2 is the SAME defect Parcel R independently found

**S2 — `Pal_Variant_Stage` is streamed to CRAM by IRQ4 while the main loop rewrites it.**
This is the one-compose-generation skew that `2026-08-18-parcel-r-sweep-adjudication.md`
found from the other direction and that killed the mid-screen-restore design. **Two
independent sweeps, five days apart, converging on it** raises its priority above its tier.
Also: S1 (DMA jump-table stride guard measures a struct, not the emitted slot), S3 (the
"dirty flag set only after a complete write" lemma is FALSE — the palette path lacks the
bracket the sprite path has), S4 (the replay net records inputs but not the scenario, so
Tails and Knuckles are structurally unreachable — corroborates the character-lens finding),
S5 (a second Critical-enqueue path bypasses the byte cap and both drop counters).

### Sound packet

D1 (SFX instance cap kills one slot of a multi-slot SFX, substitution then stacks the rest —
**LIVE TODAY**), D2 (the DAC/DMA guard pair leaves the ring with no producer for the whole
VDP window), D3 (`RegDeltaGroupBase` length guard verifies nothing), D4 ("BUILD-ENFORCED" PSG
env ceiling is not in the build), D5 (adaptive songs leave FM6's output gate closed until the
first FM6 patch event).

### Sequencing

The tools CRITICALs are first and are **not** blocked on anything — they are the only findings
here that can destroy authored data. Everything else is ordinary parcel work. None of it is
blocked by scanline P1.

---

## Tools lens CRITICALs — D1/D3 FIXED, D2 CURED, the DRIFT VECTOR still open (2026-08-18)

Landed today, each verified rather than assumed:

- **D1 CLOSED.** `tools/regenerate-level.sh` now runs a write-free
  `ojz_strip_gen.py preflight` FIRST. Poison-verified both destructive paths: missing
  `sonic_hack` and missing `skdisasm` each exit 1 with the collision tables' md5
  **unchanged**. Keep every new precondition in the preflight rather than at its point of
  use, or the defect returns.
- **D3 CLOSED at the root.** `editor_data_available()` required only `isfile`; a ZERO-BYTE
  tileset passed and baked a blank level every gate accepted. Now requires non-empty, and
  the refusal distinguishes ABSENT from PRESENT-BUT-EMPTY because they send an author to
  different places. Verified both directions (0-byte refused, 32-byte accepted — not
  over-broad).
- **D2 CURED.** `games/sonic4/data/editor/ojz_tiles.bin` is now tracked (explicit
  `.gitignore` negation, not a silent force-add). Verified in a FRESH worktree: the file is
  present and preflight passes end-to-end with the documented donor env vars. `STRESS_ART=1`
  should be alive again with it.

### ⚠ STILL OPEN — the drift vector, which is the real finding behind D2

**The editor rewrites `project.json` wholesale on save, so any repo-side correction to an
editor-owned field has a shelf life of ONE editing session.** That is what reverted the
2026-06-11 fix the very next day (`f2371ca0` → `586cd3fa`), via an editor state save the
auto-commit daemon landed unreviewed. Tracking the tileset removes the CONSEQUENCE that
made it fatal, not the mechanism.

It will bite again on the next editor-owned field that needs a repo-side value. Options,
unranked: keep editor-owned fields and build-consumed fields in SEPARATE files so the editor
never rewrites the latter; have the daemon refuse (or flag) a commit that changes a
build-consumed field; or add a gate asserting `project.json`'s resolved tileset is tracked
AND non-empty, so a revert fails the build rather than the next re-bake two months later.
**The third is the cheapest and is a real gate, not a convention.**

**CLOSED 2026-08-18 — the third option shipped.** `tools/test_editor_inputs.py`, on
build.sh's pytest lane (992 -> 996 passed). It asserts a PROPERTY rather than a filename —
whatever `zones[0].tileset` names must be TRACKED and NON-EMPTY (plus a whole number of
32-byte tiles) — so it covers both ways this one field has already broken, and it resolves
the path exactly as `ojz_strip_gen._project_tileset_path` does so it cannot pass for a file
the consumer never reads. Poison-verified against all three: the 0-byte `chunks_tiles.bin`
(D3's exact detonation), a tracked non-tileset, and an untracked blob (D2's original state).

The drift MECHANISM is still there — the editor will still rewrite the field on any save —
but it is now loud at the next build instead of silent for two months. The other two options
(separating editor-owned from build-consumed fields; making the daemon flag such a change)
remain open and would address the mechanism itself rather than alarming on it.

### Also from the same packet — ALL THREE CLOSED 2026-08-18

- **D4 CLOSED.** Its first half had already been fixed (test.sh names the game explicitly).
  The second half had not: the ROM sanity checks were gated on `[ -f "s4.bin" ]` alone, so a
  failed build left six confident PASS lines grading whatever ROM a previous manual build had
  left on disk. The prior ROM is now REMOVED before building and the checks require THIS run
  to have produced one. Verified by simulating a failing build: two FAILs, no stale PASSes.
- **D5 CLOSED, with a correction to the packet.** The real defect was that
  `discover_files` had **no else branch** — main() passed `base_dir = dirname(entry)`, so for
  a top-level entry both include candidates collapsed to the same wrong directory and the
  include vanished silently. base_dir is now the PROJECT ROOT (what AS uses, and what the
  code's own comment always claimed), an unresolvable include now RAISES, and `_SKIP_FILES`
  paths were corrected — they were dead code exactly as the packet said, and fixing
  resolution immediately produced 44 style warnings against the vendored MD Debugger, which
  is what those entries always existed to prevent.
  **The correction:** the packet says this leaves "142 `.emp` files unlinted". It does not.
  `s4lint` is an AS assembler linter (`discover_files` returns `.asm` files) and the tree now
  has 165 `.emp` files against essentially one meaningful `.asm`. The `.emp` corpus is covered
  by sigil's own warning tiers. This gate's honest scope is small BY CONSTRUCTION, not
  because of the bug; what the bug did was hide that smallness behind a confident green line.
- **The collision gate gap CLOSED.** `verify_level_bin.py` now asserts the ROM-consumed
  tables are NOT byte-identical to `collision/base/`. Property, not checksum pin: the tables
  legitimately change on every re-bake, so a pin would be silenced rather than obeyed.
  Poison-verified with D1's exact clobber. This is the detector for every route to that state
  OTHER than the one the preflight now blocks — a hand-run of `import_sk_collision.py`, a bad
  merge, a partial revert, a restored backup.

**THE TOOLS PACKET IS NOW FULLY WORKED — D1 through D10 all closed 2026-08-18.**

- **D6** — `zone_bg.bin`'s two producers. Fixed by TYPING the embed
  (`[u8; BG_LAYOUT_SIZE]`) so the length IS the guard and cannot drift from the
  declaration; `BG_LAYOUT_SIZE` is now `pub` because it is an engine↔data contract.
  Poison-verified with producer 1's exact geometry: `[emit.size-mismatch] declared type is
  8192 byte(s), initializer produced 4096`.
- **D7** — `s4budget` gated nothing, four ways: no threshold (main returned 0 on every path,
  the limits only formatted percentages), the exit code discarded by `|| true` anyway,
  UNMEASURED printed as `0KB/64KB (0%)`, and retired VRAM fallbacks 0x2000 off. All fixed;
  a real ROM/object-bank breach now fails the build. **STILL OPEN: the listing parser
  itself** — `_PAGE_BREAK_RE` keys on the AS page header, which a sigil `.lst` does not
  emit, so RAM and the section rows are genuinely unmeasurable until it is rewritten. It now
  says so loudly instead of printing 0. Its 40-test suite cannot catch this: every fixture
  is hand-authored WITH `AS V1.42` headers, so fixture and parser were co-designed and the
  suite is green forever.
- **D8** — `./test.sh` wrote committed ROM data, and it was ARMED by the D2 fix exactly as
  the packet predicted. `ojz_entity_gen.generate()` now takes `out_path`. Proven by MTIME,
  because the generator is deterministic and `git status` stayed clean throughout — a
  content check would have been green for the whole life of the bug. Regression gate:
  `tools/test_generator_sandbox.py`.
- **D9** — DPLC `tile_start` silently masked to 12 bits while `tile_count` on the SAME LINE
  had a loud assert. Now asserted. `knuckles_data.emp` records 25 entries that already
  wrapped silently in an earlier layout — the wrap is how that was discovered, not how it
  was caught.
- **D10** — 18 orphans (240 KB) deleted and the missing direction added to
  `verify_level_bin`: it checked embed→file and never file→embed. **NOT deleted and not to
  be: `knuckles.bin`** has no producer AND no input (`art/uncompressed/characters/knuckles.bin`
  does not exist), so it is irreplaceable.

### What remains open across the tools surface

All three remainders worked 2026-08-18 (the same day they were recorded). Two closed, one
STOPPED on an owner ruling with a concrete proposal below.

- **✅ CLOSED — the `s4budget` listing parser.** Rewritten for the sigil format. The old
  parser modelled an AS listing (page headers, include-depth nesting, per-file byte
  contributions, `__BUDGET_*` sentinels, `FFFFFFFFFFFF` sign-extended RAM equates, a
  `-`-typed constant bucket). A sigil `.lst` has NONE of that: it is one flat symbol table,
  every symbol type `C`, rendered twice (source rows above the header, symbol rows below,
  same set in the same order, with a `N symbols` trailer).

  What is measurable now, and from where — ROM total against `[[region]] rom` with
  `EndOfRom` as a cross-check; the object-bank budget from `map.toml`'s `[[budget]]`
  (region + ceiling + a cursor SYMBOL resolved against the listing — the map-owned
  successor to the retired `__BUDGET_DATA` marker); RAM from the `$FFFF0000+` symbols,
  which is the axis the dead parser lost entirely; VRAM from `games/<game>/vram.toml`,
  because the listing carries no constants at all. Real figures on today's build:
  `ROM: 696.0 KB/4.0 MB (17.0%) | object_bank: 6.4 KB/64.0 KB (10.0%) | RAM: 47.0 KB/64.0 KB
  (73.4%) | Free: 16.7KB before stack`.

  **Per-file ROM contributions are gone and are not coming back** — a sigil listing carries
  no file attribution whatsoever. Nothing is reported in their place.

  Three structural defences against a repeat, because the D7 failure was silence:
  `parse_listing` RAISES on a format it cannot read (no path from "format changed" to
  "zero"), and validates by making THREE numbers the listing supplies itself agree — the
  trailer count, the symbol rows, and the source rows, which must also match
  symbol-for-symbol; UNMEASURED is never rendered as a number, including the small-but-real
  case (demo's 6-byte object bank prints `6 B/64.0 KB`, not `0KB/64KB`); and the tests are
  **cut from real builds** (`tools/fixtures/*.lst` via `make_listing_excerpt.py`) with
  poisons that are MUTATIONS of that real fixture. 39 tests, 9 of them poisons, verified to
  bite by weakening the parser and watching them go red.

  Two things noticed on the way, neither acted on: sigil already enforces the map's
  `[[budget]]` ceilings at pack time, so that gate here is a dashboard and a second pair of
  eyes rather than the enforcer — but **RAM growing into the stack has no other enforcer**,
  and s4budget now fails the build on it. And a naive sum of `vram.toml` region tiles reports
  104% of VRAM for a correct map, because `window_plane` declares an overlay on `plane_b`;
  occupancy is the union, cross-checked against the map's own `[[free]]` blocks (47 == 47).

- **⛔ STOPPED, needs an owner ruling — the drift MECHANISM behind D2.** Investigated in
  Aurora; the premise in the packet turns out to be **wrong in an important way**, and the
  cure is a design decision, not a contained fix. Proposal below.

- **✅ CLOSED — donor revisions.** `tools/donor_provenance.py` stamps both donors' HEAD SHAs
  and dirty flags into `games/sonic4/data/generated/ojz/act1/DONOR_PROVENANCE.json` as
  `generate()`'s last pass. Backfilled today and **labelled `mode: "backfill"`**, which the
  file itself defines as "recorded by inspection AFTER the bake, NOT proof this tree
  reproduces". `sonic_hack` records DIRTY (11 modified tracked files) — that is the finding,
  not a formatting detail: its SHA does not identify what was read, and the first real
  re-bake will say so again unless the donor is committed first. The destination derives
  from `generate()`'s `out_dir` rather than a module constant, because a constant would
  write the committed file straight through `test_full_pipeline_runs`' redirect (D8's exact
  shape). `ojz_common.skdisasm_root()` is now the one authority for the second donor.
  16 tests against throwaway git repos, including an mtime gate proving inspection writes
  nothing into a donor's `.git`.

### D2's drift mechanism — the ruling that is actually needed (2026-08-18)

**The packet's premise was wrong.** Aurora does NOT serialize only its in-memory model.
`src/core/config/s4-config.ts` retains the parsed `project.json` verbatim as `config.raw`,
and `buildAeonSavePlan` writes `JSON.stringify(config.raw, null, 2)`. Unknown and unmodelled
keys at every nesting depth already round-trip. Verified against the 2026-06-12 revert
commit itself (`586cd3fa`): **no key was lost** — `stripPath`, `stripPrefix`, `parallax`,
`palette`, `objectLibrary`, `chunkLibrary` all survived; only formatting changed.

So "preserve unknown fields on save" is already implemented and is not the fix.

**What actually happened** is narrower and deliberate: `buildAeonSavePlan`
(`src/core/project/aeon/save.ts:140-207`) unconditionally RETARGETS exactly three fields to
editor-owned paths on every save — `zones[].tileset`, `acts[].bgLayout`, `acts[].bgTiles`.
For the tileset it computes `` `${dataRoot}editor/${zone.id}_tiles.bin` `` from the zone id
alone; the loaded value is an input to nothing, only compared to decide whether a rewrite is
needed. No user action changes it. It changes because the REPO changed it to something else.
Today the computed value already equals what is on disk, so a save writes no `project.json`
at all — the mechanism is quiescent, not absent.

The retarget is load-bearing and its rationale is documented in place: Aurora writes the tile
bytes to the editor path unconditionally, so without the pointer rewrite, MCP `write_tiles`,
imported art and merged art **silently vanish on reload**. Suppressing the retarget alone
makes saves strictly worse — bytes to one path, pointer to another, no diagnostic.

**Why this is a ruling and not a fix:** two parties both need authority over one field.
Aurora needs `project.json` to point where it writes; `ojz_strip_gen` needs
`zones[0].tileset` to name the blob the bake consumes (and hard-errors on a missing or
zero-byte target — tools D3). Whoever wins, the byte-destination and the pointer must stay
consistent by construction.

Three coherent options, recommended order:

1. **Repo-owned destination (recommended).** Add optional `editorTilesetPath` (and
   `editorBgLayout` / `editorBgTiles`) to `S4ZoneConfig` / `S4ActConfig`. When present,
   Aurora writes the bytes THERE and never rewrites `tileset`; when absent, today's
   behaviour. Gives the repo the authority it wants, keeps pointer and bytes consistent by
   construction, is fully testable at `buildAeonSavePlan`, and only widens the config type —
   the raw-preservation machinery carries the new key through untouched.
2. **Honour the loaded path as the write destination**, retargeting only when it is absent
   or unwritable. One source of truth, but it needs a "is this path safe to write" rule, and
   the current code's whole premise is that `data/generated/` is not.
3. **Keep the retarget, kill the collateral churn** (cheap, orthogonal, worth doing under any
   option): the rewrite drops the trailing newline and reindents the whole file, which is
   noise that makes these rewrites hard to spot in review.

**Trap for whoever implements it:** the legacy-atlas truncation guard at `save.ts:225-231`
reads `raw.zones[].tileset` to decide whether zeroing `chunks_tiles.bin` would destroy live
zone art. Re-derive that guard's meaning under whichever option wins.

Also worth doing regardless, and independent of the ruling: the raw-verbatim preservation
contract — the one mechanism that does work — is only ever asserted against a hand-written
`JSON.stringify` standing in for the save (`test/config/s4-config.test.ts` exists; it never
calls `buildAeonSavePlan`), so it could not catch the save itself dropping a key. A real
`load → buildAeonSavePlan → parse` round-trip asserting an unknown key survives at top, zone
and act level would pin it.

Aeon-side, the D2 gate (`tools/test_editor_inputs.py`) still alarms on the specific field,
so a recurrence fails the next build rather than hiding for two months.

#### RULED 2026-08-18 — option 1 + all three riders, implemented in Aurora

Owner ruled **option 1 (repo-owned destination)** plus riders 2 (churn), the guard
re-derivation, and the missing round-trip test. Implemented on the Aurora branch
`feature/editor-dest-fields` (cut from Aurora master `bd7700b`), four commits:

- `3830129f` — `S4ZoneConfig.editorTilesetPath`, `S4ActConfig.editorBgLayout` /
  `editorBgTiles`, and `LoadedS4Config.rawTrailingNewline`.
- `ae9b652f` — `buildAeonSavePlan` resolves each blob's destination from the raw config
  first; a declared field is where the bytes go AND suppresses that pointer's rewrite. The
  BG rewrite becomes per-field. project.json keeps the source file's trailing-newline state
  (the loader carries the fact across the parse) at the same 2-space indent.
- `dfb3267a` — the truncation guard re-derived: a path holds live zone art if it is the
  pointer a reader follows **or** the destination this plan writes to, for any zone; the
  guard tests both fields.
- `bb3b61e0` — the round-trip test file (13 tests, each proven red-first). The
  fields-absent case is pinned byte-for-byte against a plan captured *before* the mechanism
  existed: 12 writes, same order, same lengths, same project.json text.

Aurora suite after: 3138 passed / 3 skipped, `tsc --noEmit` clean, `npm run build` clean
(3125 passed before).

**The mechanism ships dormant.** No project.json in this repo declares any of the three
fields, so Aurora's behaviour is unchanged until one does. Claiming the authority — setting
`editorTilesetPath` on `zones[0]` so the bake owns `tileset` — is a separate data change,
deliberately not made here.

Remaining before close-out:

1. Merging `feature/editor-dest-fields` into Aurora master — the controller's call, not
   done by the implementing session.
2. The aeon-side alarm gate `tools/test_editor_inputs.py` **stays in place regardless of
   the ruling**. Option 1 removes the drift's cause only for fields a project actually
   declares; the gate is what makes any recurrence fail the next build.

## Sweep-driver sub-line mode — CLOSED 2026-08-19 evening (`bench/sweep-subline-mode`)

> **SHIPPED.** The mode is in `tools/hblank_window_sweep.py`; `summarize` detects the row
> convention from the data (`subline_detect`: does the landing pixel move with the spin?) and
> dispatches. The line-atomic path is **kept whole** — oracle classic is still pointed at this
> tool — and is simply no longer reached on oracle-next. Evidence, with every control, is a
> dated appended section of `docs/benchmarks/scanline-p2/HBLANK-WINDOW-SWEEP-RESULTS.md`
> ("THE SUB-LINE ERA"); no historical figure in that document was edited.
>
> **BOTH EDGES ARE NOW MEASURED**, which is the thing this booking existed for:
>
> | | measured | against | |
> |---|---|---|---|
> | early edge (window opens) | **N = 16.028 ± 0.070** (0.70 cyc) | — | never observable before |
> | late edge (window closes) | **N = 28.267 ± 0.076** (0.76 cyc) | — | |
> | blanking width | **122.39 ± 1.07 cyc** | arithmetic 122.86 | **AGREES**, 0.44 s.e. |
> | `RASTER_HBLANK_END_CYC` | **366.67 ± 0.76** | shipped **366** | **CONFIRMED**, 0.88 s.e. |
> | pixel clock | 0.8740 ± 0.0027 px/cyc | 0.8750 | 0.4 s.e. |
> | sampling period | 488.51 ± 0.25 cyc | 488.57 | 0.2 s.e. |
>
> **No stop-and-report.** The stop condition was the anchor landing outside a guard margin
> (which would mean shipped spins are mis-centred against the better instrument). The tighter
> margin is the late one at 10 cycles; the anchor is off by 0.67. **Nothing shipped is
> mis-placed and this parcel changed no constant.** The 351 → 371 → 366 provenance chain
> closes at 366.7 measured; 371 is settled as ~4.3 cycles high.
>
> Controls: A1 PASS (3 fresh processes, byte-identical); A1-style determinism across the whole
> 201-capture sweep PASS (two processes, 0 differing N, every derived quantity identical to 6
> d.p.); A2 literal now PASSES (106 differing columns on the split row, where it read 0 before
> the amendment); A2 restated 19 distinct pictures vs 4; `source == "raster"` asserted on every
> capture and never fired; self-diff control 0 vs itself and 57 vs the subject; **all five
> anchors reproduce their atomic-era verdicts exactly**, first-new-pixel columns included, so
> the edge-row calibration (authored+1) survives the instrument change. Zero ROM bytes
> (`s4.debug.bin` crc32 `06af0010` unchanged); wire pins 39/39; pytest 1106 passed / 2 skipped
> against a 1092/2 baseline, the 14 new tests in `tools/test_hblank_subline.py` being the
> difference. `--replay` re-derives every number with no emulator and no ROM.
>
> **Two riders that came out of the run and are NOT closed:**
>
> 1. **`--words 1` is the window fixture, and the wider ones cannot be.** Every sensitive
>    column samples exactly one written entry, so on a multi-word burst `flipX` reports the
>    FIRST entry's landing and its bracket cannot be taken over the whole sensitive set. Width
>    and period are immune (a constant offset cancels); the absolute edges drift ~1.6 cycles
>    across widths 1→5. Measured, not assumed.
> 2. **The plateau control goes VACUOUS above three words on this art**, and the tool now says
>    so instead of letting a reader misread it. A fourth and fifth burst entry add only ~2
>    observable columns each to the edge row, so a trailing word landing just inside active
>    changes nothing any column can report and the plateau stops shrinking — §4's content trap,
>    one entry further along than §4 looks. Nothing downstream consumes a plateau. A fixture
>    that could watch a wide burst's TAIL directly would need an address whose whole span is
>    well sampled at these rows; the content map probes 3-entry windows and would have to be
>    widened to pick one.

## RECOMMENDATION for the controller — `RASTER_BURST_MAX_CRAM`: **HOLD AT 3** (booked 2026-08-19)

The parked 4-word raise, re-asked against a **directly measured** early edge instead of one
derived from the arithmetic width. **No constant, ceiling or margin was changed by the parcel
that produced these numbers** — this is the booking the controller rules on.

Decision rule, fixed before the numbers were known and restated without softening: the binding
margin must clear **both** two standard errors **and** the 2.9-cycle threshold the DEEP class
was refused on.

| words | solved spin | early slack | late slack | **binding** | 2 s.e. | verdict |
|---|---|---|---|---|---|---|
| 3 (shipped) | 19 | +9.72 | +30.67 | **+9.72** | 1.41 | GO |
| **4** | 18 | **−0.28** | +14.67 | **−0.28** | 1.41 | **NO-GO** |
| 5 | 17 | −10.28 | −1.33 | −10.28 | 1.41 | NO-GO |

**The verdict is unchanged from the atomic era and the evidence for it is now first-class.**
That refusal read +0.9 cycles against a 2-s.e. bar of 4.0 — a positive margin too small to
trust, on a derived edge with an error bar borrowed from the *other* edge's quantization. The
direct measurement reads **−0.28 against a bar of 1.41**: the error bar shrank 2.8× and the
margin turned out not to be positive at all. Repeated across four independent 201-capture
sweeps the 4-word binding margin reads **−0.28 / +0.51 / +1.03 / +1.31** cycles against 2-s.e.
bars of 1.41 / 1.76 / 1.64 / 1.60 and the fixed 2.9 threshold: **it fails both bars in every
run, on both signs of the estimate.**

The arithmetic still nominally admits four words (78 of burst + 30 of margins against a window
now measured at 122.4, 14.4 to spare). That gap between "the span fits" and "the solver's
rounding puts it there" is the trap the atomic-era section named, and the measurement lands on
the same side of it: `solve_spin` quantizes to whole `dbf` iterations and the nearest one puts
the first write a quarter-cycle inside the early margin.

**Two things WOULD change the answer, and neither is proposed here:**

1. A pre-burst path ~3 cycles cheaper moves the solved spin off its unlucky rounding.
2. **`RASTER_HBLANK_MARGIN_EARLY_CYC` = 20 is now arguably over-bought.** It is two iterations
   of slop, and its own comment ties the asymmetry to the early edge being *derived* where the
   late one was measured. That asymmetry of evidence is gone: the early edge is now the
   better-measured of the two (0.70 cyc s.e. against 0.76). Re-deriving it is a real parcel
   with a real safety argument to make — it is the guard against painting a visible mid-row
   dot — and it is emphatically **not** a knob to turn in order to fit a fourth word. If it is
   ever opened, the 4-word question should be re-asked *after* it settles, never as its
   justification.

Also worth carrying: `RASTER_BURST_MAX_DEEP` stays at 3 for an unchanged reason. Its word is
30 cycles, so four span 90 against the measured 122.4, leaving 32.4 for margins wanting 30 —
a 2.4-cycle slack, now *below* the 2.9 threshold rather than marginally above it (the measured
window is 0.5 cyc narrower than the arithmetic one that gave it 2.9). The DEEP refusal is
firmer than it was, not weaker.

## Sweep-driver sub-line mode — the original booking, 2026-08-19 morning (superseded above)

oracle-next shipped mid-line CRAM resolution (their 87c8e99/ff9e784; empyrean §11.15) and the
acceptance re-run PASSED (flipX 219 in the predicted [205,225]; literal spec-A2 passes with 102
differing columns; 19/20 distinct pictures; px/cyc 0.849 measured vs 0.875 arithmetic).
`tools/hblank_window_sweep.py`'s flip-x columns are now REAL — but its boundary-crossing
analysis and solver-fit sections are ATOMIC-ERA logic: on the new instrument they misread
split rows as ~23 "boundaries", derive a nonsense 290-cyc span, and print a spurious NO-GO.
Ignore those sections on sub-line servers until this lands.

**The mode to build:** classify directly from flip-x (the landing pixel IS the measurement);
the blanking window's EARLY edge becomes directly measurable for the FIRST time (always
derived until now, and the asymmetric ensure margins — early 20 / late 10 — exist precisely
because of that). Re-derive `RASTER_HBLANK_END_CYC` with both edges measured and a tighter
s.e., then REVISIT the parked 4-word burst raise (it failed at +0.9 cyc early slack against
a 2-s.e. bar of 4.0 — a direct early-edge measurement changes both numbers). Registered
refinements on their side that bound precision: F-SUBLINE-ACCESSMCLK / F-SUBLINE-DMASPREAD
(a burst shares one landing x — no smear).

## Scanline P2 Phase 2 (Tasks 10-13) — BLOCKED at Task 10's spike and Task 12's join (booked 2026-08-19, `feat/scanline-p2-budgets`)

> **UPDATE 2026-08-19, same day — BLOCKER 1 IS CLOSED; BLOCKER 2 STANDS.**
>
> The unblock landed as a sigil parcel: **sigil master `0df77f83`** (merge of `feat/equ-listing`)
> routes equates into the listing as a third section, framed by an "Equate Table" header with an
> "N equates" trailer, one `EQU <name> = $XXXXXXXX` row each. The spike was re-run on this branch
> and **round-trips**: `SPIKE_LEDGER_EQU = $000000DC` (= 220, exactly the computed
> `SceneRegistry_CapsFolded * 7 + 3`) and `SPIKE_LEDGER_NEG = $FFFFFFFB` (= -5, confirming values
> render unsigned 32-bit and a negative row is two's complement). CRC unchanged, so ledger rows
> remain zero-ROM. `pub equ` is the reliable spelling; `pub const` still mints no symbol.
>
> **Tasks 10, 11 and 13 shipped on that path** — see the branch commits. Four axes are enforced
> comptime (1 main-loop, 2 VBlank DMA bytes, 3 VBlank CPU, 4b HInt total), the ledger publishes
> twelve equate rows, and `tools/scene_budget_report.py` renders them from the artifact.
>
> **Three findings from the shipping pass, all booked in `tools/effects_budget_model.toml`
> `[scene_budget]` rather than left in a report:**
> 1. **The aggregation must be `max`, not the `sum` design §5 and the plan specify.** Only one
>    scene is live at a time; a SUM over the shipped twenty is ~500k cycles against a 128k frame
>    and would refuse a registry that demonstrably runs. The pairwise sum is exactly what
>    Task 12's transition frame would add — which is the second reason Blocker 2 matters.
> 2. **Only axis 1 is falsifiable**, and it is measured: 115 bands passes, 116 fails by 82.01 cyc.
>    Axes 2 and 3 charge a two-valued cost that always fits; axis 4b is bounded above by the 4a
>    density guard. Three poisons were booked WITH THEIR UNLOCK CONDITIONS instead of faked.
> 3. The axis-6 RAM row and the axis-2 per-line figure were both wrong in the tree and are
>    corrected in the same commit (see the two corrections below, now applied rather than pending).
>
> **What still needs a ruling: Blocker 2 (Task 12) is untouched and was not attempted**, per the
> resume scope. Its two unblock conditions below are unchanged.

Phase 2 was dispatched off master `bc048e2a` (the Phase-0 merge — every budget denominator
measured). It stopped at the first gate the plan itself put there. Two independent blockers,
both structural, neither a matter of effort.

### BLOCKER 1 — the ledger readback does not exist (Task 10, the spike the plan named)

Design §5 has the lowering publish per-scene ledger rows as **named exported comptime consts
(zero ROM bytes)**, with a formatter reading them **from the build's symbol table**. Task 10
Step 1 required round-tripping ONE const end to end before authoring twenty. It does not
round-trip, in any spelling available today.

**The spike, run on `s4.debug.bin`.** Two candidate declarations were added to
`games/sonic4/data/effects/scene_registry.emp` (a REACHED, section-carrying module) with a
value that is genuinely COMPUTED rather than literal — `SceneRegistry_CapsFolded * 7 + 3`,
which folds to 220:

```emp
pub equ   SPIKE_LEDGER_EQU   = SceneRegistry_CapsFolded * 7 + 3
pub const SPIKE_LEDGER_CONST = SceneRegistry_CapsFolded * 7 + 3
```

Result: build GREEN, `crc=d22dda85 len=713295` — **identical to baseline**, so both spellings
are genuinely zero-ROM and that half of the design holds. But neither name appears in
`s4.debug.lst`, and the symbol count is **unchanged at 2578**. Positive control on the same
module in the same build: `DeformTable_Zero : 121C8 C |` and
`ParallaxConfig_OJZ_Default : 122C8 C |` are both present, so the search method is sound and
the negative is real. The spike was reverted; the tree is unmodified.

**Why, from the sigil source rather than from the symptom.** The `.lst` is built by walking
`sec.labels` ONLY — `crates/sigil-harness/src/native.rs:3341-3352` (the chained driver, the
path a Frozen shape actually takes) and `:3593-3604` (the PinnedBaked driver), both:

```rust
for sec in &resolved { let origin = sec.vma_origin();
    for label in &sec.labels { listing.push(ListingSymbol { name: …, value: origin + label.offset, … }) } }
```

- `pub const` is, in the lowerer's own words (`sigil-frontend-emp/src/lower/mod.rs:596-598`),
  "a name-resolution-only item (**no bytes, no label, no deferred symbol**)". Invisible by
  construction.
- `pub equ` DOES mint a link-level `EquSym` (`lower_equ_item`, same file :568/:794) — zero
  bytes, and explicitly **no label**. So it never enters either listing loop. The AST comment
  that defines the item says the quiet part outright (`sigil-frontend-emp/src/ast.rs:82-86`):
  an equ's "whole purpose is to become a link-level symbol (**that emission is a later
  task**)".
- deb2 is `convsym` over that same `.lst` (`native.rs:4002-4015`), so it is blind for the same
  reason, not an independent surface. Confirmed live: the tree's 147 existing `equ`
  declarations (`SFX_WIN_33`, `SND_BLIP_LEN`, `SND_KICK_BANK`, …) are absent from
  `s4.debug.lst` too.
- `ListingSymbol` carries an `is_equate` flag rendering a `-` marker, and **nothing in the
  tree ever sets it true** (only unit tests do). The `.lst` currently holds `0` equate rows.

**The other candidate surface is blind for an unrelated reason.** `tools/effects_budget_check.py`
— the `[symbols]` provenance gate Task 11 Step 3 would extend — resolves a constant by
REGEX over `.emp` source text (`CONST_RE`, `^\s*(?:pub\s+)?const\s+NAME…=\s*(.+?)$`) plus a
Python evaluation of const-to-const references in the same file. It can evaluate
`RASTER_FIRE_BASE_CYC = 280`; it cannot evaluate `fold_caps(SCENES)` or any per-scene ledger
value, which is a comptime function call over an array of structs. So provenance rows cannot
substitute for the readback either.

**Plan Task 10 Step 2 governs and was followed:** "If the readback does not work, STOP and
report. Do not invent a second emission path — registry-emission exclusivity is a carried
trap." No second path was built.

**What unblocks it (a sigil-side parcel, aeon+sigil pair).** Route `EquSym`s into the
listing: they are already resolved into the symbol table (`sigil-link`'s
`resolved_symbols`/`build_symbol_table` return them — that is how the pins path reads them),
so the change is to emit them as `is_equate: true` rows in `emit_listing`'s input alongside
the label rows. Two cautions for whoever takes it: (a) `convsym`'s `as_lst` reader takes only
`C` symbols (`native.rs:3559-3561` states this), so equate rows would land in the `.lst` for
tool consumption but NOT in deb2 — which is fine for a formatter and should be stated rather
than discovered; (b) a non-`pub` equ is owner-mangled to `$module$NAME`, and `$` names are
dropped by the demangler, so ledger consts must be `pub`.

### BLOCKER 2 — Task 12's transition-frame check has no derivable subject AND no denominator

Two independent failures, either one sufficient. **(b) the denominator was MEASURED 2026-08-20
(P3 Phase 0 Task 3). (a) the Label-typed join is UNTOUCHED and still blocks Task 12 on its own.**

**(a) The section→scene join column is a `Label`.** The plan's Step 1 requires adjacency
DERIVED from section descriptors ("a hand-maintained adjacency list is a copied expectation").
Adjacency itself is fine — it is grid order, and `GRID_W = 3` / `GRID_H = 3` with
`flat = sec_y*grid_w + sec_x` are plain comptime ints in
`games/sonic4/data/levels/ojz/act1/act_descriptor.emp:75-76` and `engine/level/section.emp:92`.
What is missing is the join from a section to its SCENE VALUE. Every binding in the chain is a
link-time Label, never a value:
`Sec.sec_parallax_config: *u8` (`engine/structs.emp:116`) →
`EffectsPreset.ep_parallax: *u8 @ $04` (`engine/effects/preset.emp:58`) →
`preset(…, parallax: Label = 0, …)` (`:119`). There is no comptime path from
`ParallaxConfig_OJZ_Underwater` (a Label) back to `Scene_OJZ_Underwater` (a value in
`SCENES[1]`), and this tree has ruled on exactly that shape repeatedly — an `ensure` comparing
a Label to an int is silently unevaluable and always passes (`scene_dsl.emp:243`,
`preset.emp:52`, `EMP_PITFALLS.md` §3). `OJZ_Act1_Sections` is a `pub data`, not a `pub const`,
so importing it yields the symbol and not nine `Sec` structs; `ojz_sec` is private; and the
`use` edge already runs act_descriptor → scene_registry, so the reverse import is a cycle.

The tree ALREADY declined this check for this reason, at `scene_registry.emp:280-282`: "a
transition-compatibility check between adjacent scenes: P1 does not know which sections are
adjacent." Task 12 as written would have to re-open that ruling, not implement around it.

**(b) There is no measured transition-frame reservation.** ~~Phase 0's own flags record that
neither measured camera state crosses a section boundary~~ — **MEASURED 2026-08-20 by P3 Phase 0
Task 3. THIS HALF OF BLOCKER 2 IS CLOSED.** See below.

> **BLOCKER 2(b) — CLOSED 2026-08-20, `p3/t3-reglue-instrument`.**
> `tools/parallax_cost_probe.py --transition N` synthesizes the frame instead of driving the
> camera to a crossing: freeze the camera, then write `Parallax_Current_Config = A`,
> `Parallax_Target_Config = B`, `Parallax_Transition_Frames = N` straight into RAM. That is a
> live transition frame with both configs routed — `Parallax_Active_Config` routing, the
> per-band scroll lerp and the reg `$0B` mode state all real — and it is measurable
> per-routine without a real crossing. Rows are in `tools/effects_budget_model.toml`
> `[parallax.cost_model]` (`transition_*`), marked SYNTHESIZED; evidence and every control in
> `docs/benchmarks/scanline-p3/REGLUE-INSTRUMENT.md`.
>
> Pair: `ParallaxConfig_OJZ_Underwater` (mode `%011`) → `ParallaxConfig_Perspective_Dramatic`
> (mode `%111`), the **maximal shipped mode difference**. 5 boots, sample 31, spread 0 on
> every row, every window preemption-free.
>
> | axis | measured |
> |---|---|
> | 1 main-loop | surcharge **+1074 cyc** (active B, 5 bands) / **+894 cyc** (active A, 4 bands), against the stable frame on the same active config |
> | 2 VBlank DMA bytes | **+0 B** — the scanline-220 queue is byte-for-byte identical, 3056 B total / 1152 B largest, transition or not |
> | 3 VBlank CPU | `Enqueue_Dirty_Buffers` **+2 cyc** (1374 → 1376) |
>
> **Three boundaries on the row, so it is not over-read.** (i) `Parallax_StartTransition` and
> `Parallax_CheckBoundary` do not run — a frozen camera suppresses them by construction, so the
> staging cost is in no row here. (ii) The reg `$0B` write is paid ONCE, four frames before the
> profiled window; the shadow byte is read back and checked against the ACTIVE config's derived
> mode, so the change is witnessed but its cost is not measured. (iii) **The plan's "one
> per-cell, one per-line" pair does not exist in this tree** — all 20 shipped scenes attach an
> H-deform table, so reg `$0B`'s H bits are `%11` for every installable config and a
> mode-differing HScroll length is unmeasurable here. Axis 2's `+0` is structural, not lucky.
>
> Reproduced en route: correction **C1's queue discrepancy** — one declared
> `Static_Hscroll_Line` at `dma_length(896)`, but **two** 448-word entries live with the same
> command word `7C000082`. P3 Task 6 Step 1 owns reconciling it; this is fresh evidence for it,
> not a ruling.
>
> **AND A SECOND FINDING THE AXIS-1 ROW BELOW DIVIDES BY: `[parallax.cost_model]` IS STALE
> AGAINST MASTER.** The same parcel re-ran the fit sweep as a tool regression (26 fixtures,
> spread 0, zero failed checks, exit 0) and the rows do not reproduce, because the walker
> changed: `loop_shape` declares the rows a property of the PRE-UNROLL per-line filler at
> master `08e87cbc`, and **`afccb141 perf(parallax): pointer-walk + unroll the single-channel
> sampling loops` has since landed on master**. The model's STRUCTURE survives intact — the
> un-anchored residual is still exactly **0.00** over the same 18 fixtures and 7 of 11
> un-anchored columns are unmoved — but `line_fg_only` 72.75 → **26.00**, `line_bg_only`
> 72.81 → **26.90**, `band_sampling` 0.00 → **154.00** (the ~149 class `WALKER-MODEL.md` §5(d)
> predicted for the unrolled shape), and the shipped config's out-of-sample cost
> **20162 → 13798, 31.6% cheaper**. Post-unroll values are booked as `postunroll_*` in
> `tools/effects_budget_model.toml` beside a block naming the staleness; **Task 1's rows are
> deliberately left intact** (they are the pre-unroll record `loop_shape` exists to name) and
> **P3 Task 7's standing-rule re-fit / Task 13's re-take own promoting them**. Until then
> nothing may divide by the pre-unroll per-line columns — they over-charge a sampled line by
> ~2.8x and would refuse a scene that demonstrably runs.

**(a) STILL OPEN, AND UNCHANGED BY P3.** The section→scene join is a `Label` end to end
(`Sec.sec_parallax_config` → `EffectsPreset.ep_parallax` → `preset(parallax: Label = 0)`) and
nothing in P3 touches it. **Task 12 is NOT unblocked** — a synthesized transition measures the
frame's cost; it does not give the lowering a comptime-visible, value-typed map from a section
to its scene, which is what Task 12's derived adjacency check needs.

**What unblocks the remaining half:** a comptime-visible, value-typed section→scene map — and
the honest shape is to INVERT authorship so `act_descriptor.emp`/`ojz_effects.emp` derive their
`parallax:` Label FROM a shared scene-index table, rather than adding a parallel hand-written
array beside the Labels (which would be exactly the unfalsifiable guard
`scene_registry.emp:268-283` rejects). ~~and (ii) a Phase-0-style baseline probe run at a
boundary-crossing camera state~~ — superseded: the synthesized frame above is that measurement,
and it does not need a crossing. A probe run at a real crossing would additionally price
`Parallax_StartTransition` + `Parallax_CheckBoundary`, which remains open work but blocks
nothing in Task 12.

### Axis audit for Task 11, done while blocked (so the re-dispatch does not re-derive it)

Per-axis, against the MEASURED rows, using the IDLE-state reservations as the gate divisor
(controller ruling: sustained max-diagonal runs 15 logic ticks per 31 video frames and is
streaming-bound — `Tile_Cache_Fill` 40.1%/tick — so it is informative context with BOTH
denominators, never a gate divisor).

| # | Axis | Pool | Reservation (idle, measured) | Verdict |
|---|---|---|---|---|
| 1 | main-loop cycles | 128000 cyc/frame | `idle_main_loop_cycles` 35125; real headroom `idle_vsync_wait_cycles` 79595 | **GATEABLE** — cost from `[parallax.cost_model]`. **AND SUPERSEDED A SECOND TIME 2026-08-20 by P3 Task 3's regression run: the P3 Task 1 rows below are PRE-UNROLL and `afccb141` has landed on master — see the post-unroll block in Blocker 2(b) above and `postunroll_*` in the toml.** **The figures in this row were superseded 2026-08-20 by P3 Task 1** (every P2 row was diluted 30/31; `anchor` is now FITTED, not two labelled regimes): residual **0.00** un-anchored / 13.3 all-fixtures, out-of-sample gap **+1.22% (+246.7)**, `anchor = 982.2 + 59.27 x overlay_loop_trips` at ±27.6. **SUSPECT THE RESERVATION FIGURES TOO**: P2's idle `Parallax_Update` row was 19511 and the preemption-free value is 20162 = `19511 x 31/30` to half a cycle, so the idle profile that `idle_main_loop_cycles` 35125 came from was diluted by the same factor. NOT re-measured here (it is a different probe's row) — re-take it before dividing by it. |
| 2 | VBlank DMA bytes | 7524 B (H40 NTSC) | live queue `dma_queue_words_idle` 1528 w = **3056 B** | **GATEABLE** — see the correction below |
| 3 | VBlank CPU | ~18200 cyc VBlank window | `idle_vblank_cycles` 8280 (`VInt_Level` bracket) | **GATEABLE** — budget 9920 cyc |
| 4a | HInt per-fire spacing | — | — | already owned by `check_density`; no new work |
| 4b | HInt per-frame total | 128000 cyc/frame | sparse 1878 (1.5%); dense **31665 (24.7%)** is the shipped worst case (was 32758/25.7% before the `-4(a2)` dense-stream rider) | **GATEABLE** — and the dense row's open −183 cyc / 1 fire model gap (−188 pre-rider on the same instrument, i.e. unmoved) belongs in the derivation note, not absorbed |
| 5 | sprite slots | — | **NOTHING MEASURED** | **NOT GATEABLE.** No Phase-0 row exists, and no shipped scene has the subject: FG sprite strips are `CAP_FG_SPRITE_STRIPS = $0080`, in `scene_dsl.emp`'s RESERVED (P3+) block with no lowering |
| 6 | RAM | free-before-stack | `[ram]` sizes are code-derived and `[symbols]`-gated | **GATEABLE, but the pool row is STALE** — see below |
| 7 | computed-handler pins | — | — | **NO SUBJECT IN P2.** `CAP_COMPUTED = $0400` is in the same RESERVED (P3+) comment block, no lowering; design §472 records the computed-range infra as deleted and deliberately not rebuilt |

So **four axes of the plan's seven are actually gateable in P2** (1, 2, 3, 4b), 4a already has
an owner, and axes 5 and 7 have no shipped subject at all. A re-dispatch should say so rather
than let "seven axes" imply seven gates — and Task 13's "one poison per axis" should be scoped
to the four, or it will demand poisons for capabilities that cannot be authored.

**Two corrections to carry into the re-dispatch, both found by deriving instead of copying:**

1. **Axis 2's per-line forcer is 1792 B, not 896.** The plan (and design §5) price a per-line
   forcer at 896 B. The live queue scan shows **TWO** 448-word entries — `dma_hscroll_perline_entries = 2`,
   `dma_hscroll_perline_bytes_each = 896` — i.e. 1792 B against a 7524 B pool (23.8%), not
   12%. This is precisely the case Task 11 Step 2 exists to prevent ("so '12%' never reads as
   the whole tax") and the understatement is in the plan's own figure, before the drain CPU
   is even added.
2. **Axis 6's pool row is stale by ~2x and in the unsafe direction.**
   `effects_budget_model.toml:540` carries `free_before_stack_kb = 31.8   # measured — build.sh
   reports it each build`. Measured this session on `bc048e2a`: **16.7 KB** free (release) and
   **6.5 KB** free (DEBUG — the tight shape, and the one a budget must clear). A RAM gate
   written against 31.8 would pass while enforcing a number nobody took, which is the exact
   defect this plan's own preamble cites (`EFX_BLANK_DELAY = 4`). Re-take the row, and gate
   the DEBUG shape.

### State of the branch

`feat/scanline-p2-budgets` off `bc048e2a`. No engine or tool source was modified — the spike
was reverted and verified clean. All four shapes build at baseline:
sonic4 DEBUG `d22dda85`/713295 · sonic4 release `cdabf8a3`/698411 ·
demo DEBUG `f9f8d0e5`/100086 · demo release `f7806241`/95733.
Tasks 11 and 13 were NOT started: Task 11's ledger-const shape is downstream of the Task-10
ruling (how a ledger row gets published decides what the consts are), and Task 13 poisons one
per axis, which is downstream of which axes Task 11 gates.

## Scanline P3 (walker mechanisms) — PLANNED 2026-08-20, and what it does and does not unblock above

The P3 implementation plan is written and committed:
**`docs/superpowers/plans/2026-08-20-scanline-p3-walker-mechanisms.md`**
(branch `plan/scanline-p3-walker`, off master `0cf5a053`). Sixteen tasks in three phases —
instruments first, then the six mechanisms design §10 assigns to P3 (world-Y re-glue, curves,
per-layer deform refs + extended record, the single-source per-line forcer derivation,
vscroll-split lowering, left-column mask), then the model re-fit, gates and poisons.

**Read the plan's "Spec-vs-tree corrections" table before touching any of this.** The design
spec predates P2's landings and is stale in eight places, including two numbers a task would
otherwise copy: the per-line forcer is **1792 B, not the spec's 896**, and `.lp_both` has
**14 registers live, not "all 16"** (`a0` is spilled at proc entry and dormant), which is the
stated justification for the curve∧deform prohibition.

### P3 Task 2 — the HScroll ramp reader — ✅ CLOSED 2026-08-20 (`measure/p3-t2-hscroll-probe`)

`tools/parallax_hscroll_probe.py` + 34 unit tests + `docs/benchmarks/scanline-p3/CURVE-INSTRUMENT.md`.
Zero engine bytes on all four shapes. **§8.3's curve instrument now exists, and it went red
before any curve did** — the arm hand-installs a quadratic HScroll bow (BG excursion +388 px,
an order of magnitude outside the +-255 any signed-byte deform table can reach) and runs the
same checker twice over the same RAM: RED against the shipped-derived expectation naming
`line 2 FG: expected $FFA0 (-96) got $FF9F (-97)` of 434 mismatching words, then GREEN against
the ramp's own. T10 inherits a detector with a fired-poison record instead of one written to
agree with the mechanism it witnesses.

Three facts a later task will otherwise rediscover:

1. **The shadow band COUNT exists only in `d7`.** Step 4b makes the view one entry longer than
   `pcfg_band_count` says and the entries below it are last frame's, so the fill's band
   partition is underivable from RAM alone. The probe derives Step 4a + Step 4b in Python and
   proves the derivation against `Parallax_Shadow_Bands` before it checks a single line. That
   stage has already fired on its own account.
2. **`run_frames` is not a sample point for anything the walker writes.** It returns on a video
   frame boundary the main-loop tick is not aligned to, and a camera write lags the loop through
   a full tile-cache re-stream. The first draft read the buffer MID-FILL and reported 90
   mismatching BG words from line 70 — lines 0..69 on the new deform phase, 70..223 on the old.
   Every sample is now taken stopped at `Parallax_Update`'s entry.
3. **Two breakpoint traps sit behind that.** A breakpoint at the PC you are already stopped at
   re-triggers instantly (24 sweep iterations ran against one frozen tick), and
   `wait_for_break` can return on a stop that is not yours (6 of 24 samples landed mid-tick).
   Step off the PC before arming, and verify the stop PC.

Baseline the curve task moves off, from the shipped `ParallaxConfig_OJZ_Underwater`: FG interior
first differences identically 0; BG max |d1| = 1, max |d2| = 2, entirely the shimmer table at
shift 2 below the anchored split.

**What P3 does to the two BLOCKED items above:**

- **Task 12's blocker (b) — no measured transition-frame reservation — is CLOSED BY P3 Task 3.**
  The cost probe's own fixture trick supplies it without a real crossing: freeze the camera,
  then install `Parallax_Current_Config = A`, `Parallax_Target_Config = B`,
  `Parallax_Transition_Frames = N` in RAM. That routes both configs, changes reg `$0B` and runs
  the per-band scroll lerp — the three things `WALKER-MODEL.md` §8 lists as unmeasured. Stated
  limit, carried into the row: a frozen camera suppresses `Parallax_StartTransition` and
  `Parallax_CheckBoundary`, so it is a **synthesized** transition frame, not a real crossing.
- **Task 12's blocker (a) — the Label-typed section→scene join — is UNTOUCHED by P3 and still
  blocks.** Nothing in the P3 mechanism set inverts that authorship. Task 12 stays blocked; do
  not read the P3 landing as unblocking it.
- **Axis 5 (sprite slots) gets its first subject in P3 — from the LEFT-COLUMN MASK, not from
  sprite strips.** `CAP_FG_SPRITE_STRIPS` stays RESERVED past P3; §10's P3 list does not
  include strips. The plan's Task 4 measures the missing object-system SAT reservation and
  Task 14 gates the axis.
- **Axis 7 (computed-handler pins) gets NO subject in P3.** §10's P3 list contains no computed
  handlers and §9 records the computed-range infra as deliberately not rebuilt. The toml row
  currently reads "NO SUBJECT UNTIL P3", which will be false the moment P3 lands; the plan's
  Task 13 rewrites it.
- **`Sprite mask for per-column V-scroll leftmost-partial-column garbage` (the booking above at
  "Sprite mask for per-column V-scroll…") is P3 Task 12's subject — RESTATED 2026-08-21, not
  closed.** Task 12 landed the POLICY LAYER (mandatory `left_column_mask` declaration, verified
  `factor0_lock`, `Accept` on both shipped per-column families, the 7-slot axis-5 pricing gated
  in `effects_budget_check.py`, the static claims probe) as a zero-byte parcel; the
  `sprite_mask` ENGINE EMISSION stays open, `scene()` refuses the variant until it lands, and
  the booking now enumerates its exact blockers (the sprites.emp first-`Game.*`-reference sigil
  port flip → aeon+sigil pair; the game-owned opaque tile) plus the recorded mechanism ruling
  (opaque strip at screen X 0 — the VDP X=0 masking feature cannot repaint plane pixels).
- **The P1 gate evidence's deferred runtime differential is now DUE.** `docs/benchmarks/
  scanline-p1/GATE-EVIDENCE.md` §8 ruled its motion spot-check tautological because all four
  images were byte-identical, and named the unlock: "if the images ever diverge (a future parcel
  that moves bytes deliberately) this test becomes a real differential and should be run then."
  P3 moves bytes deliberately.

### ~~P3 Phase 0 Task 1 — the anchored overlay's two regimes~~ — CLOSED 2026-08-20 (`measure/p3-t1-anchor-regimes`)

**The parameter is `anchor_ops` = 59.27 cycles per Step-4b overlay loop iteration, on top of a
fixed `anchor` = 982.2.** Eight anchored fixtures across three overlay-trip counts, max
|residual| **27.6 cycles**. `anchor_status` in `[parallax.cost_model]` changes from
"NOT CONSTANT — two regimes measured … deliberately not fitted" to **FITTED**, and P2's
`anchor_cycles_reglue_only` / `anchor_cycles_shipped_shape` rows are deleted.

**The 749-cycle "second regime" did not exist.** It decomposes, exactly, into two instrument
defects plus a real and much smaller effect:

1. **Frame dilution.** The per-routine row is a per-VIDEO-FRAME average and the P2 sweep never
   checked frames-per-tick. The idle baseline lags ~1 window in 4 (and always on the window
   right after a fixture install), so W10/W12 were measured `x 29/31` while the un-anchored model
   they were scored against was fitted on `x 30/31` rows — worth ~790 cycles of apparent overlay.
   Every P2 coefficient is `30/31` of its clean value to 4 decimal places, and `line_both` — the
   one column excited by a single fixture, whose window caught two lag frames — is `29/31`.
2. **A missing per-line term.** The sampled loops end in `asr.w d3, d1`, a register-count shift
   (`6 + 2n`), so the per-line cost depends on the deform SHIFT VALUE. Measured **exactly 2.00**
   cyc/line/shift-unit on two independent steps. The shipped config samples at shift 2 while
   P2's coefficients were shift-3 values, over-charging W16 by ~280.

Reconstructing P2's published numbers from the clean model through both distortions reproduces
W16's +1204.7 as **+1205.1**.

**§5(c)'s named parameter (`band_sampling`) is REFUTED for this loop shape, and MEASURED at
exactly 0.00** — the plan's premise that it is "collinear in every un-anchored fixture" is false
(W14/W15 are mixed-type), and W25 confirms it directly: turning a second band's sampling on costs
`112 x 78.75` and not one cycle more. **It is not zero forever**: the parallax fill-unroll parcel
measures the same column at a ~149-cycle class once the sampled loops are unrolled. Two parcels
triangulated one physical cost from opposite directions. Every row in `[parallax.cost_model]` now
carries a `loop_shape` field naming the code it was measured against.

**What actually drives the anchor** (2×2, overlay cost over the un-anchored model): band count
2→4 is **+222** (flat overlay) to **+240** (turn-on); the loop-type change P2 named as the regime
is **+27** (2 bands) / **+45** (4 bands); channel is +25; split POSITION is **+1**.

**Also landed, and load-bearing beyond this task:**
- The un-anchored fit is now **max |residual| 0.00 over 18 fixtures** (was 0.27 over 14), with
  `shift_lines` at a derived-and-confirmed 2.0000.
- The probe's derived checks went 3 → 5 and now **fail the run (exit 5)** instead of printing.
  New: a two-sided `$FF` poison of shadow slot `band_count` (the overlay is its only writer);
  the frames-per-tick preemption check; and a world-anchor readback for the split-position
  fixture. Poisoned red-first — and the instructive result is that the slot witness does NOT
  catch an `anchor_ch = $FF` poison (the fixture is then legitimately un-anchored); only the
  neighbour differential does. Neither witness is sufficient alone.
- The out-of-sample row is measured **by the probe**, from the shadow view rather than the ROM
  band entries — the shipped config does not pin `v_factor_bg`, so Step 4a rotates and clamps its
  tops and the ROM-entry derivation put the split at 48 when the machine says 80. Gap
  **+246.7 (1.22%)**, essentially P2's +1.1%: this task fixed the in-sample residual, not the
  out-of-sample one.

**Two riders, booked not closed:**
- **The idle reservations are probably diluted too.** P2's idle `Parallax_Update` was 19511 and
  the preemption-free value is 20162 = `19511 x 31/30` to half a cycle, so
  `idle_main_loop_cycles` 35125 and its neighbours in `[scene_budget]` came off the same diluted
  profile. NOT re-measured here — it is `engine_baseline_probe.py`'s row, not this probe's.
- **`multiband` = 24.00 is due for re-measurement, not carrying**: P3 Task 7 rewrites the
  `.find_k` loop that produces it.

## ~~Warp mailbox: two measured behaviours to explain~~ — CLOSED 2026-08-19 (`fix/warp-semantics-doc`)

Booked from a raw-`Sst.y_pos` probe (oracle-aether headless, no-input boot + 600f, x=1536):
ask y=128 → rest 117 (−11); ask y=320 → rest 320 verbatim; both frozen for 240f after ack.
Both riders are answered, one of them was a defect, and it is fixed. Full prose: §4.12,
"Placement semantics".

1. **The −11 was NOT destination-dependent — the terrain reading was an artefact of the
   probe's own shape, and the writer is `PHook_EnsureStanding`** (`player_common.emp`),
   reached from the consumer's `Player_SetState(PSTATE_AIR)` via `PHook_AirEnter`. It
   normalises the collision box to the character's standing box and applies the feet-planted
   lift `y_pos -= (cd_stand_h − current_h) >> 1`. The DEBUG shape boots into debug-fly, whose
   marker box is 16×16 (`Player_DebugEnter`), so the FIRST warp of a boot lifted Sonic
   `(39 − 16) >> 1 = 11` px and every later warp found the box already standing and took the
   hook's `.keep`. The booking's two asks were two warps in ONE boot — hence "128 → 117, then
   320 → 320", read as destination-dependence when it was first-warp-dependence. Decided by
   two fresh-boot controls: a single warp straight to y=320 rested at **309**, and two
   successive warps to y=128 rested at **117 then 128**, with the box observed going 16×16 →
   19×39 across warp 1. No collision probe runs in the ack window at all.
   **Verdict: defect, and FIXED** — the lift is correct for a state change in place and wrong
   for a teleport, and it made the same request land at different heights (11 px out of
   debug-fly, 5 px out of a curl, 0 px otherwise) depending on session history, which a
   placement tool cannot reason about. `Debug_Warp_Consume` step 2 now writes the position
   AFTER `Player_SetState` (`d3`/`d4` carry the clamped pair across it — its contract clobbers
   only `d1-d2`/`a1-a2`), so the hook's lift lands on the pre-warp position and is overwritten.
   Re-measured after the fix: fresh-boot single warp to y=320 rests at **320**; two warps to
   y=128 rest at **128 and 128**; the physics-regime warp is unchanged at verbatim. The edit is
   byte-count neutral (`s4.debug.bin` len 713863 either side, crc `06af0010` → `203a3bac`) and
   wholly inside `if DEBUG == 1`, so `s4.bin` stays `e111dff7`.
2. **The leader IS ticked — it just cannot move.** `RunObjects` calls `Player_Main` every
   frame, but the DEBUG shape arms `CHEAT_DEBUG_FLY` and `Player_Init` tail-calls
   `Player_DebugEnter`, so the scene boots in free flight and `Player_Main`'s escape hatch
   (`tst.b PlayerV.debug_flag(a0); bne Player_DebugMove`) routes past physics, state dispatch
   and rings into `Player_DebugMove`, which reads the D-pad and nothing else. No input, no
   motion — indistinguishable from "never ticked" from outside. There is no simulation mode
   flag: a harness sends **one B press** through the emulator's controller surface
   (`emulator/press`, not a memory write — the pad cells are rewritten every VBlank), which is
   `Player_Main`'s cheat-gated toggle → `Player_DebugExit` → standing box, `debug_flag` cleared,
   `PSTATE_AIR`. Measured from a no-input boot at x=256: y holds 256 for 60 idle frames, then
   after the press runs 256 → 260 → 332 → 573 with `player_state` `PSTATE_AIR` → `PSTATE_GROUND`
   and `ST_IN_AIR` clearing on touchdown.

## Seraph coupling anchor — the S0-unpark ruling's aeon-side facts (2026-08-19)

Anchor for seraph's Log (their f8b0f0c records the ruling as transcription pending this
commit). The three caveats attached to "the sound pipeline is stable, unpark S0":
1. **Open aeon sound work that could touch driver internals:** packages 5 and 6 (of the
   2026-07-03 six-package banking) remain OPEN, and the 2026-08-13 sound lens sweep's
   packet is UNMERGED with two live findings (multi-slot SFX cap; a DAC/DMA wedge
   class). None scheduled. **Standing contract: any MEV format or sound_constants.emp
   change lands only after explicit pre-landing notice to the seraph session.**
2. **MEV_EXT registry slots 0/1/2 are load-bearing invariants** — extensions are a
   cross-repo ask through the demand-doc flow, never a unilateral read/extend.
3. **The streaming arc couples to the sound driver's DMA-survival design** via the
   max-contiguous-DMA-stall question (P2 Phase 0 Task 5's row is instrument-blind until
   oracle-next's stallCycles; a future streaming fix touching DMA cadence coordinates
   with seraph before landing).
Last engine/sound commit at ruling time: 8b39969d (2026-08-11, Tails-flight SFX import
— content, not format), reconciled by seraph's firsthand check.

## Boot-position override (§4.12b) — what the shipped parcel deliberately left (2026-08-19, `feat/debug-boot-override`)

### 1. The parallax half of the hook is UNWITNESSED, and it is unwitnessable in OJZ act 1

The override has two consumers in `GameState_OJZScroll_Init`: the placement block after
`Player_Init` (camera + leader), and the parallax config select further down, which reads
`Act.start_sec_x/y` and under an override must read the section containing the destination
instead. The first is witnessed hard — poisoning either half of it fails
`tools/boot_override_gate.py` loudly (measured: removing the camera aim gives 1027/1189
differing visible plane words and 8/8 differing rendered scanlines; removing the leader's X
placement gives 617/1189 and 8/8).

The second is **not** witnessed, and the reason is data, not instrumentation: every OJZ act 1
section binds `sec_parallax_config: default` (NULL = inherit the act default), so
`Section_GetSecPtrXY` returns the same config pointer whatever section index it is handed.
Poisoning that half to always read section 0 leaves the gate fully green (verified —
poison `p2`, exit 0, every metric identical to a clean run). It is kept because it is
correct for the general case and costs seven DEBUG-only instructions; it is *booked* because
a green gate must not be read as coverage it does not have.

**The tripwire is already installed rather than deferred:** the gate walks the section grid
out of the ROM image and hard-fails (setup error, exit 2) with an instruction the day any
section binds its own `sec_parallax_config`. **The work at that point** is to give the gate a
reference the warp cannot supply: the warp sets `Parallax_Snap_Pending` and therefore snaps,
so it cannot distinguish "the init picked the right config" from "the first
`Parallax_CheckBoundary` corrected it". The reference has to be a *walked* arrival into the
destination section (which lerps the same way a boot does not) or a direct readback of the
installed config pointer.

### 2. Cross-act boot is NOT this mailbox — named so it is not re-proposed

There is deliberately no zone/act field. Booting a different act is `Game_Entry`
parameterisation (design #5), not a position override, and the two want different lifetimes:
this mailbox is consumed by one act's init and cleared, while an act selector has to survive
into whatever chooses the act. Within-act only, and §4.12b says so.

### 3. Aurora's client contract moved, and the client has not been written against it yet

Aurora's analysis assumed the cells could be written at the reset-paused machine before
`resume`. They cannot: boot clears all 64 KB of Work RAM. The supported sequence is
`reload_rom` → `run_to GameState_OJZScroll_Init` → write X/Y/FLAG → continue, and the gate's
`pre` run proves the pre-resume write is silently eaten. **If Aurora's Build & Run was built
against the earlier assumption it will silently boot at the authored start** — the failure is
a no-op, not an error, which is exactly the shape that goes unnoticed. Worth an explicit
handshake with the aurora session rather than a doc update alone.

## Axis 4b (`check_hint_total`) has no reachable subject in the sparse tier (found 2026-08-20, P3 Task 11)

`raster_program()` sums `fire_cost_cycles` over a program's fires and refuses a total above
`RASTER_HINT_FRAME_CYC - RASTER_HINT_RESERVATION_CYC` = 84,595 cycles. **No program it accepts
can reach that number**, so the ensure has never been able to fire and is not the protection a
reader takes it for. Two guards dominate it, both measured while proving Task 11's lowered fire
is counted there:

* **`check_density`** requires `cost_i <= gap_i * RASTER_SCANLINE_CYC` (488). The cheapest fire
  class measures ~320 model cycles at one line of gap and the dearest classes cost more per line
  they occupy, so the most an all-sparse program can spend across screen lines 3..223 is about
  `320 x 221 = 70,720` — 84% of the budget, and that is the ceiling, not a typical figure.
* **`RASTER_BUF_SIZE`** (128 bytes = 64 words) refuses the LENGTH long before the cost. Measured:
  a 205-fire pad failed with `raster_program: 827 words = 1654 bytes exceeds RASTER_BUF_SIZE
  (128)` while `check_hint_total` passed on the same program.

What IS true, and was the thing Task 11 owed: a lowered `fx_vscroll_split` fire is summed there
like any other (with the reservation temporarily shrunk so the ensure fires: 2 fires / 640 cyc
without it, 3 fires / 1264 with it — delta 624, the same total the tree reports for
`OJZ_TestVsram` itself). The model is right; only its ceiling is unreachable.

**Not fixed here, deliberately.** The options are a budget-model decision rather than a parcel's
— price the DENSE tier through the same total (a gradient run is many fires inside one
interrupt and is where a per-frame HInt budget would actually bind), or re-derive the
reservation against what the sparse tier can physically spend, or state in the guard that it is
a model kept for the dense tier and let the two structural guards own the sparse one. Whoever
takes it should read `docs/benchmarks/scanline-p3/VSPLIT.md` §7 for the measurements.

## `scene_budget_report.py --check` still has no artifact-lane runner (found 2026-08-22, P3 Task 14)

The ledger's readback gate (`--check`: fail when a published `SceneBudget_*` row is missing
from the listing's equate table) needs a built DEBUG listing, so it cannot sit in the
canonical build's source-gate block, and today nothing automated invokes it. Task 14 closed
the larger half at the SOURCE level: `tools/test_scene_budget_ledger.py` (pytest lane, both
canonical shapes) gates `LEDGER_ROWS` against the registry's `pub equ` rows in both
directions, plus the pub-equ-not-pub-const spelling — so a renamed, dropped or mis-spelled
row now fails the build. What remains uncovered is the one failure the source cannot see:
**sigil ceasing to route equates into the listing at all** (the `0df77f83` equate-table
contract regressing). Unlock/fix options: run `--check` inside a lane that already owns a
DEBUG artifact (`tools/effects_gates.py` boots one per gate; the nightly
`aeon-effects-gates.timer` is the backstop candidate), or fold an equate-table presence
probe into a listing-consuming test the sweep already runs (`test_s4budget.py` reads real
listing fixtures — but fixtures freeze, so a fixture-based probe would NOT catch a live
regression; it needs the fresh artifact). Until then: run
`python3 tools/scene_budget_report.py --check` by hand after any sigil listing-format
change.

## The extended-record size pins cannot be driven red from the poison lane (found 2026-08-22, P3 Task 15)

Plan Task 15's list owes "the extended-record size pin (Task 8)" an `emp_expect_fail`
CASES row, and no honest one exists today. **Booked with its unlock conditions rather than
faked** — the Task 14 axis-5 precedent, applied after measuring, not assuming.

**Why no input can reach any of the pins.** Every pin site compares TREE CONSTANTS that a
`--extra-entry` poison module cannot perturb:

- the two-directional `Game.SCANLINE_CAPS & CAP_MULTI_DEFORM_TABLE` <-> `BAND_EXT_N` pair
  (and its CAP_FACTOR_CURVE <-> `BAND_CURVE_N` twin) in
  `games/sonic4/data/effects/scene_registry.emp` — both sides are fixed by the shipped
  game + engine; both directions were red-proven at Task 8 **by edits** (the registry
  banner records the two arms), which is exactly the evidence class a lane row cannot
  reproduce;
- the capability-off identity ensure and the `Parallax_Shadow_Bands` extern-span pin in
  `engine/level/parallax.emp` — `sizeof(band_record)` and the RAM span are decided by the
  same constants.

**The one input-shaped route is unenforced where the lane could use it.** A wrong-SHAPE
record VALUE would be the one-unit poison (`br_ext` one element long against
`BAND_EXT_N = 0`), and it has nowhere to fire:

- on a **comptime `const` binding** sigil does NOT check the array length — measured
  2026-08-22 in this worktree: a `const P: band_record = band_record{ .., br_ext:
  [ band_ext{ .. } ], br_curve: [] }` literal ELABORATED (proven via a field-read hook
  ensure) and built green with the canonical CRC. This is consistent with the Task-1
  probe-B record ("a comptime fn's return annotation is documentation; the typed `data`
  binding is what raises `array length mismatch`") — the registry's typed `data`
  bindings, not const bindings, are the enforcement;
- a **`data` binding** is the enforcement site, but a poison module may not contribute
  bytes (the lane refuses it loudly), and the two-fixture rule makes it structurally
  unusable anyway: the defect-REMOVED control would still be a byte-contributing module
  and could never pass.

**Unlock conditions, either suffices:**

1. **sigil enforces array lengths on typed comptime `const` literals.** The day that
   lands, the one-element-`br_ext` const above IS the one-unit poison — the fixture is
   already written out in this entry.
   > **SATISFIED IN SIGIL SOURCE 2026-08-22 — sigil master `e08f5bdc`**, reported by
   > sigil-83: `const_record_wrong_tail_arity_refuses ... ok` under `SIGIL_STRICT_GATE=1`
   > against aeon `1a794ace` (their run: 3762 passed / 0 failed / 4 ignored, `^skip:` count
   > zero). Root cause of the old gap was theirs: the length check lived in the
   > byte-EMISSION path (`sigil-frontend-emp/src/eval/emit.rs:214,236`), which a comptime
   > `const` binding never reaches.
   >
   > **DO NOT CUT THE LANE-ROW PARCEL ON THIS ALONE — one thing is unverified and it is the
   > thing that decides whether the parcel can work.** aeon builds against the SHARED binary
   > at `/home/volence/sonic_hacks/sigil/target/release/sigil`, NOT against sigil's source
   > tree, and that binary was last built 2026-08-20 09:54 — *before* `e08f5bdc`. sigil-83 is
   > additionally bound this session not to rebuild it.
   >
   > **CONFIRMED ABSENT BY MEASUREMENT, not by inference (sigil-83, 2026-08-22).** The
   > suspicion above was upgraded to a fact: the enforcement lives in `const_arity.rs`, added
   > by sigil `5700b656` and on master at `e08f5bdc` — but run through **the exact binary aeon
   > invokes**, the minimal fixture
   >
   > ```
   > const N_EXT = 0
   > struct ext { ex_a: u16, }
   > struct rec { r_base: u16, r_ext: [ext; N_EXT], }
   > const P: rec = rec{ r_base: 1, r_ext: [ ext{ ex_a: 2 } ] }
   > ```
   >
   > builds **GREEN** (`built: 0 bytes`, `exit=0`) — a one-element array against a zero-length
   > declared type, accepted silently. **Cutting the lane row against this binary would have
   > enshrined the exact vacuous gate this entry exists to prevent.**
   >
   > **SEQUENCE BEFORE CUTTING** (agreed with sigil-83): shared binary rebuilt from master →
   > aeon re-runs the fixture against it and observes a REFUSAL → *then* the row is cut, citing
   > the shared artifact rather than a transient worktree build. Do not accept a refusal
   > obtained from a worktree binary as the artifact the row cites — that is evidence for the
   > LANGUAGE claim, not for the assembler this repo runs.
   >
   > **SEQUENCE NOW SATISFIED — THE ROW IS CUTTABLE (2026-08-22).** All three steps done:
   > 1. Shared binary rebuilt: `/home/volence/sonic_hacks/sigil/target/release/sigil`,
   >    mtime **2026-08-22 13:58:30** (was 2026-08-20 09:54:11).
   > 2. Verified against THAT artifact by sigil-83 — poison: `array length mismatch:
   >    expected 0 element(s), got 1`, exit 1. Control (`r_ext: []`): `built: 0 bytes`,
   >    exit 0. **The control is the load-bearing arm** — a reject-everything compiler
   >    satisfies the poison alone.
   > 3. Committed fixture to cite instead of a scratchpad file:
   >    `crates/sigil-cli/tests/const_arity_cli.rs` + `vectors/const_arity_{poison,control}.emp`,
   >    runner `const_arity_cli`, driving the built binary via `CARGO_BIN_EXE_sigil` and
   >    taking **no `AEON_DIR`** (deliberately — that coupling is what it exists to avoid).
   >
   > **⚠ EVERY SIGIL SHA BELOW IS LOCAL-ONLY — VERIFIED, NOT ASSUMED.** sigil
   > `origin/master` is `40f862e2` (2026-08-21, the T10 refreeze); local master is
   > `538e5a3c`, **38 commits ahead and unpushed** (the owner's gate, not an oversight).
   > So the fixture commit `a24a1b4f` / merge `34d887c4`, and `e08f5bdc` / `e8f325b3`,
   > exist **only on this machine**. Cite them as local-only or wait for a push; a row
   > citing an unfetchable fixture is an anchor nobody else can reach.
   >
   > **AEON RE-VERIFIED UNDER THE NEW ASSEMBLER (this overseer, firsthand).** aeon
   > `551d1841` in a clean paired worktree, ROMs deleted first so existence proves
   > freshness: all four shapes green, CRCs **unmoved** — `060401e4` / `0dbaa80f` /
   > `c708b114` / `dec88cc1`; suite `1211 passed, 4 skipped` (the 4th skip is the known
   > benign DEBUG-artifact-presence one, present because the ROMs were deleted; it is
   > `1212/3` once `s4.debug.bin` exists — not a regression). This matters because the
   > rebuilt binary also carries an **encoder tightening**: `TST` takes DATA ALTERABLE on
   > the MC68000, not DATA, removing nine encodable words the 68000 traps as illegal.
   > Independently confirmed here: **zero `tst` with a `pc` or `#` operand** across aeon's
   > `.emp`/`.asm`/`.inc`. Their sweep covered aeon at `b1f8a230`/`1a794ace` and worried
   > about the delta to `419194bb` — **that delta is docs-only** (`git diff --name-only`
   > excluding `docs/` is empty), so their coverage transfers.
   >
   > Standing hazard this exposed, wider than the parcel: **the shared
   > `sigil/target/release/sigil` had been three days behind master and nobody noticed until
   > this entry forced the question.** Every aeon build in that window used it. A stale shared
   > assembler is invisible to CRC identity by construction — it reproduces the same bytes it
   > always did.
2. **The `SCANLINE_CAPS` `emp_defines` parcel** (accepted sigil-side 2026-08-20, booked
   above in this file) makes `BAND_EXT_N` capability-DERIVED instead of a pinned mirror.
   The pin pair then stops being the guard surface (a derivation cannot disagree with its
   own input) and the falsifiability question must be re-measured over whatever replaces it.

Until one lands, the pins' liveness evidence remains Task 8's recorded edit-red arms, and
the record-shape family's lane coverage is the arity guards' natural-red probe (Task 5's
rotation, recorded at the `lowerN` banner) — also not a CASES row, for the same
constants-not-inputs reason.

---

## ✅ RESOLVED — `Scene`'s hand-computed pad went stale; the guard is now an invariant assertion (2026-08-22)

**Severity: LATENT, not live.** `Scene` (`engine/level/scene_dsl.emp`) is comptime-only and
emits no ROM bytes, so no shipped ROM ever performed an odd-address word access. All four
CRCs are byte-identical across the fix (`060401e4` / `0dbaa80f` / `c708b114` / `dec88cc1`).
What was broken is the **guard**, in precisely the scenario it was installed to cover.

**What happened.** `120180ac` (2026-08-18) added `sc_pad_5D` specifically to silence sigil's
`[layout.odd-field]` lint, landing the two `i16` bridges (`sc_mask_raw`,
`sc_v_deform_shift_raw`) on even offsets 94/96. It worked — that day. At least fifteen commits
then touched the file, four of them adding fields *above* the pad (`sc_left_col_mask` in
`ba335e08`, `SceneDeform.Own()` in `022b961f`, capability-shaped band records in `a1d66b51`,
per-layer vertical depth in `59e29b68`). The bridges drifted to **119/121 — odd**, the lint
fired twice on every build for four days, and it fired into a `SIGIL_WARNINGS=full` baseline
nobody re-read. The comment above the pad went on asserting `(94, 96)` the entire time.

**The fix** (`9a718f74`): pad widened `u8` → `u16` — derived from the compiler's own
measurement (pad at 118, bridges reported at 119/121), *not* from the stale 94/96 — plus two
`ensure`s immediately after the struct asserting the **property**:

```
ensure(offsetof(Scene, sc_mask_raw) % 2 == 0, "…")
ensure(offsetof(Scene, sc_v_deform_shift_raw) % 2 == 0, "…")
```

`@offset 94` was available and was **deliberately rejected**. It makes the failure loud, but a
pinned offset must be hand-updated on every legitimate field insertion — it re-arms the exact
staling-constant trap this entry exists to record. Parity survives every insertion; a number
does not.

**Red-first evidence.** Reverting the pad to `u8` fails the real sonic4 DEBUG closure with
exactly 2 errors, both messages verbatim — *not* merely under `sigil build --extra-entry`,
where a guard in an unreachable module would also appear to fire (EMP_PITFALLS §3). Warning
tally 134 → 132; `layout.odd-field` 2 → 0. Note the first perturbation tried (inserting a
temporary `u8` field) is **confounded** — it buries the guard under ~700
`[struct.missing-field]` errors, because `scene()` and the three poison fixtures spell every
field. Perturbing the pad *width* is the isolated probe.

### THE CLASS — a hand-computed pad is a silently-staling constant

This generalises past `Scene`. **Any struct with alignment intent wants an assertion, not
arithmetic.** A pad width is a function of every field above it, so it is invalidated by edits
that are individually correct, made by people who never read the pad. The failure is silent by
construction: the field that goes odd still compiles, still type-checks, and (for a
comptime-only struct) still produces an identical ROM.

Two compounding factors made this survive four days, and both are reusable warnings:

1. **A lint that lands in an accepted baseline stops being a signal.** The original comment
   predicted this in its own words — *"a warning that has been explained away in a baseline is
   not there to catch it"* — and was then defeated by exactly that. A tally line moving
   134 → 132 is not something anyone reads; an `ensure` that fails the build is.
2. **A comment is not a check.** The comment stated `(94, 96)` as fact for four days while the
   compiler measured 119/121. Prose asserting a computed value is a claim with no verifier
   attached.

**Standing guidance:** when adding or adjusting a pad, express the intent as
`ensure(offsetof(T, f) % 2 == 0, …)` (or `% 4` for long-span bases) rather than writing the
resulting offset in a comment or an `@offset`. `engine/system/replay.emp:96-102` is the house
pattern and the message idiom — **name the instruction that would fault** ("move.w would
address-error"), never the offset that moved, because the offset is the part that rots.

**Not swept.** This parcel fixed the one struct it was scoped to. Whether other structs in the
tree carry hand-computed pads with the same exposure was **not** audited — `[layout.odd-field]`
is currently at 0 for both games, which bounds the *odd-field* instance of the class but says
nothing about pads holding a `% 4` or a declared-size intent. A sweep is cheap (grep for `pad`
in struct bodies, check each for an accompanying `ensure`) and is offered as follow-up work.

**Residual nit, deliberately not fixed:** the field is still named `sc_pad_5D`, and `$5D` = 93
is itself a stale offset (it now sits at 118). Renaming it would touch the three
`games/sonic4/test/poison/` fixtures that spell it, and a poison fixture whose failure mode
shifts can go vacuously green — not worth the risk inside this parcel. The name is decoration;
the `ensure`s are the authority.

#### ALIGN — the `(align: N)` migration this booking is owed (CLOSED 2026-08-25, branch parcel/field-align)

**Closed in place.** `sc_mask_raw: i16 (align: 2)` and `sc_v_deform_shift_raw: i16 (align: 2)` in
`engine/level/scene_dsl.emp`; both trailing `offsetof(…) % 2 == 0` ensures deleted. Zero-byte:
all four ROM CRCs identical before/after (s4 875d591f, s4.debug a02d36db, demo bf2cdb42,
demo.debug 62a0019e); `SIGIL_WARNINGS=full` sonic4-debug warning set diff 0 (150 lines both
sides); pytest 1371/1372 passed + emp_expect_fail 35/35 on every shape. Gate settled positively:
`$SIGIL_BUILD --version` reports revision bbcc0cb0 and `merge-base --is-ancestor 6fae4d6a
bbcc0cb0` holds. Both relayed cautions verified against sigil itself: the field form is the
one in `crates/sigil-frontend-emp/tests/eval_layout.rs:376-444` (satisfied-silent control arm +
violation-is-error poison arm); the `@align(N)`-on-a-struct-field refusal is
`crates/sigil-frontend-emp/src/parser.rs:1155` and was re-proven red-first here (sigil has no
test of its own for that refusal — offered to the sigil lane as a proposal). Red-first B:
widening `sc_transition` to u16 fails the build with the attribute's own diagnostic naming the
field, the claim and the live offset (121/123), where the deleted ensures used to fire.

**What THE CLASS still leaves open:** `sc_pad_5D`'s width is STILL a hand-computed constant —
now guarded structurally rather than by an asserted `ensure`, but not derived. `pad_to(N)` is
not shipped; nothing here reaches for it. The residual `sc_pad_5D` naming nit stays residual.
Original booking text kept below for the record.

Sigil shipped a field-level alignment attribute, which is the derived replacement for the
`ensure`-guarded hand pad above. Scope when it is picked up: `sc_mask_raw` and
`sc_v_deform_shift_raw` take the attribute, and the two `offsetof(…) % 2 == 0` ensures come
out (the attribute makes the property structural rather than asserted).

**Gate — verify, do not infer.** `6fae4d6a` ("Merge branch 'feat/field-align'") is an ancestor
of sigil master, verified firsthand 2026-08-24. A rebuilt `SIGIL_BUILD` binary's **mtime is not
evidence it carries that merge** (protocol bar 16 — presence is not behaviour). Sigil's lane
states that `sigil --version` reports the revision, branch and tree state it was built from;
**that is their claim, unverified here** — settle it with that command at dispatch, and if it
does not report a revision, find another positive check rather than falling back to mtime.

**Two cautions from the sigil lane, relayed 2026-08-24, both unverified here:**
1. **The spelling is `(align: N)`, NOT `@align(N)`.** `@align(N)` is the `vars`-region
   cursor-mover; on a struct field it is refused by name with a teaching diagnostic. Cheap to
   get wrong, loud when you do.
2. **The migration does NOT derive `sc_pad_5D`'s width — it stays hand-computed.** The
   attribute guards the stale constant; it does not compute it. So THE CLASS above is only
   half-discharged by this parcel, and the residual nit stays residual. The deriving construct
   is `pad_to(N)`, which sigil describes as **drafted-but-unlanded and now needing the owner's
   agreement before it ships** — so do not plan this migration around `pad_to` existing, and do
   not let an agent reach for it.

**Provenance note, recorded because it matters for how much the agreement is worth:** the
handback state (both repos' HEADs equal to their pushed remotes) was checked by this lane and by
the sigil lane minutes apart using effectively the same two commands on the same trees. Sigil
said so unprompted. That is a repeated check, **not an independent second derivation**
(protocol bar 19) — the enumeration parameter did not differ.

### EFFECTS-W1 — the TRUE aeon blocker, restated 2026-08-24 (the old one was refuted)

**The declared blocker was stale and both of its stated reasons are refuted.** It read
"`tools/effects_gen.py` is SLICE 1 only" and "the `act_descriptor.emp` import seam waits on
design Q-c, an open decision". Verified firsthand at aeon `ea8a820e` (== `origin/master`),
and independently re-verified by the empyrean hub against the same remote before they moved
their board:

- **Q-c was RULED AND IMPLEMENTED by the owner on 2026-08-22** (the always-emitted default).
  Design §9 records it; `effects_gen.py` implements it under a header naming the ruling.
- **Slices 1-5 are all on master and P5 IS WIRED** — `build.sh` runs `effects_gen.py check`
  on every canonical build, `effects_seam_gate.py` runs beside `s4budget`, and
  `regenerate-level.sh` bakes the module unconditionally.

**Root cause of the stale blocker, and it is the reusable part:** master's `effects_gen.py`
still opens with a module docstring reading *"SLICE 1 (this commit) … the seam in particular
waits on design Q-c … which is an open decision."* It has been false since slice 5 and it sits
at the top of the 1,059-line file that implements the ruling. **A perishable claim in a code
comment outlived every doc that recorded the ruling** — the design doc, this file, and the
implementing header all say "ruled", and the one artifact nobody re-reads propagated the
opposite into a cross-lane contract. Same family as the `sc_pad_5D` comment asserting `(94, 96)`
for four days.

> **CLOSED by the VFACTOR parcel (part C).** Both stale claims are gone; the docstring now
> describes what the code IS, with no new date-stamped "as of" sentence to rot the same way.
> **A SECOND COPY WAS FOUND IN THE SAME FILE WHILE FIXING THE FIRST, AND IT WAS WORSE.**
> `render_scene()`'s own docstring claimed *"the generated module is not wired into the build
> until the descriptor import seam exists (open question Q-c)"* — i.e. the sentence a reader
> would use to conclude that the `scene()` / `layer()` guards on its output DO NOT RUN, in the
> docstring of the function that produces the text they guard. It is fixed, and it sharpens the
> lesson: the stale header was not one bad paragraph, it was a claim that had been COPIED, and
> the grep that finds the copies (`Q-c`, `slice 1`, `not wired`) is what the next such fix
> should start with rather than end with. (`tools/test_effects_gen.py` carried the "slice 1"
> staling too and is fixed with them.)

**What is ACTUALLY left, and it is one thing:** *no real Aurora-authored scene has ever been
through the path end to end.* P5 is byte-neutral in its shipping state precisely because zero
editor scenes exist; the content path is proven only by a **temporary fixture** (green at crc
`1499f79c`), which is a fixture this lane wrote, not an artifact an author produced. Three
named things stood between here and that; **item 1 is CLOSED (VFACTOR, 2026-08-24) and 2-3
remain** — and note what that re-ranks: the two survivors are both blocked on an ARTIFACT
existing (a placement row that only a real scene can verify, and an editor that cannot yet
make one), not on engine or generator work. Neither is ours to unblock alone.

1. **The `v_factor` default defect (VFACTOR) — this would break the FIRST real scene.**
   Aurora's new-scene default is `v_factor: 'FACTOR_0'`. `FACTOR_*` is the **packed**
   horizontal encoding (`parallax_dsl.emp`: `FACTOR_LOCKED = $0FF`, `FACTOR_0` an alias), so
   the name folds to **255**; `sc_v_factor` is a **raw shift** (`(camY - v_center) >> v_factor`)
   whose lock sentinel is **15**. Two namespaces, one field. `effects_gen.py` treats `v_factor`
   as a `SCENE_SCALARS` member and interpolates it **verbatim with no type check**, so the
   string reaches the generated `.emp` and — wherever `parallax_dsl` is imported, i.e. any
   scene with a named layer factor — **resolves to 255 and compiles silently.** Nothing
   downstream catches it: the only two `ensure`s naming `v_factor` in `scene_dsl.emp` are both
   `== 15` *conditions*, and **there is no range guard on `v_factor` anywhere.**
   **Both halves are ours and they are separable:** refusing a string where an integer belongs
   is a **SHAPE** error and is squarely inside `effects_gen.py`'s charter (it duplicates no
   constructor guard); the **range** check is NOT — that belongs on the `scene()` constructor,
   which currently has no owner for "255 is an absurd shift".
   *Empyrean has separately ruled the schema `$ref` half (the schema moves, the engine does
   not) and holds that CR; it is coordinated because aurora vendors the file by blob hash.*

   > **CLOSED 2026-08-24 — both halves, on `parcel/vfactor-shape-range`.** Byte-neutral in
   > all four shapes (zero editor scenes exist; a passing `ensure` emits nothing).
   >
   > - **SHAPE** — `tools/effects_gen.py` grew one `_render_int` helper and every slot that
   >   is emitted as a bare `.emp` integer now routes through it. **Scoped to the class, not
   >   the instance:** all four `SCENE_SCALARS` (the other three had the identical exposure),
   >   the non-bool `LAYER_SCALARS`, `world_y` beside them, the composed-factor `{s1,s2,op}`
   >   terms, the anchor's `channel/dsa/dsb`, the attachment payloads past a `tableRef`, and
   >   the `tableRef` generator parameters. `render_vsplit`'s inline check was this rule
   >   written once for one slot and now defers to the shared one.
   > - **RANGE** — `scene()` gained `0 .. 15` on `v_factor` and on `v_factor_fg`. **Derived
   >   from the consumer, not from the sentinel:** `Parallax_Step5_Vscroll` compares the byte
   >   against 15 and otherwise uses it as an `asr.w d2, d0` count; `asr.w` takes its register
   >   count mod 64 and every count from 15 up fills the word with its sign, which is why 15
   >   was free to BE the sentinel. So 0..14 are the shifts, 15 is the lock, and **16..255
   >   neither lock nor shift** — `.v_locked` is not taken and the plane silently pins to
   >   0/-1. The lower bound is live too: `scene()` takes an `int` into a `u8`, so `-1` wraps
   >   to 255. Corroborated independently (a check, not the source) by empyrean's writer
   >   schema, which declares both fields `{"type":"integer","minimum":0,"maximum":15}`.
   > - **`v_factor_fg` is the SAME NUMBERS BY A DIFFERENT DERIVATION, and the distinction is
   >   worth keeping.** `pcfg_v_factor_fg` is RESERVED and **nothing reads it** (Step 5 sets
   >   the FG vscroll to camY unconditionally), so no bound is derivable from a consumer and
   >   no authored value can bend a picture today. The bound comes from the field's declared
   >   identity as `v_factor`'s twin, which it inherits when the reservation lifts. It is a
   >   RESERVATION bound, and deliberately not `== 0`: that would pin the v1 runtime's
   >   silence as if it were the field's meaning and re-arm the `sc_pad_5D` staling trap.
   > - **Shipped corpus enumerated before the guard landed:** every `scene()` call site in
   >   the tree authors `v_factor` in {3, 4, 15}, and **no call site anywhere passes
   >   `v_factor_fg`** (all take the `= 0` default). Nothing shipped fails.
   > - Tests: `tools/test_effects_gen.py` (build.sh's `pytest tools` lane) with coverage
   >   derived by iterating the scalar tuples rather than listing them, plus
   >   `games/sonic4/test/poison/poison_scene_vfactor_range.emp` and two `CASES` rows in the
   >   expect-fail lane. **Red-first measured, including the matcher:** with the message
   >   reworded into the neighbouring refusals' vocabulary the guard still fired and the
   >   tests still went red, and with the two `ensure`s stashed out the poison module builds
   >   **clean, rc 0, zero `[Error]`** — the silence this closes.
   >
   > **AN ADJACENT DEFECT FOUND BY READING THE WRITER'S SCHEMA RATHER THAN OUR FIELD LIST,
   > and it would have bitten the same first scene:** `enabled` is a **JSON boolean**
   > (`$defs.layer.enabled`), while `layer()` takes `enabled: int = 1`. Master emitted the
   > bare word `True` / `False` into generated `.emp` for a legal Aurora scene. Translated
   > now (`_render_bool_int`); an integer stays accepted, as `ATTACH_NONE` accepts JSON null.
   > This is the third time this contract has been bitten by reading our own field NAMES and
   > assuming the writer's VALUE spellings (slices 1-2 assumed JSON null for `"none"`, then
   > `precision: cell`, now this) — **the enumeration to run on the next field is the
   > schema's `type`/`enum`/`const` per field, not our key list.**
2. **The `map.toml` order row**, deliberately unauthored — **STILL PENDING as of 2026-08-24;
   it has NOT fired, and a cross-lane reading that it had was retracted the same hour. Read the
   correction below before reasoning about this item.**

   > **⚠ THIS ITEM IS ABOUT `ojz_effects_editor_act1` (generated by `tools/effects_gen.py`) AND
   > NOTHING ELSE.** On 2026-08-24 aurora built the first real editor-authored band against
   > `origin/master` `5349bea4` and the ROM failed to assemble; the hub relayed the second
   > failure as *"your blocker (2) fired exactly where you said it would"*. **It did not.** The
   > section that collided is **`ojz_bg_anim`** — a different section, emitted by a different
   > tool (`tools/inject_editor_bg.py`), and **declared in `order` all along**: `BgAnim_Table`
   > sits at `map.toml:120`, and `bg_anim.emp:7` is the only module declaring `in ojz_bg_anim`,
   > so that label is the section's offset-0 head label. Verified firsthand here at
   > `5349bea4` before the correction was sent; the hub re-verified it independently before
   > retracting (empyrean `06438a8`, ledger `ad9bf1d`, both stated pushed and
   > ancestor-verified — **their claim, not re-checked here**).
   >
   > **Three consequences, all durable:**
   > - `[map.order-undeclared]` did not fire because there was **nothing to fire on**. The
   >   companion hypothesis — that the overlap check masks the better diagnostic — has **no
   >   mechanism behind it and generated no sigil-side ask.** Do not revive it from the
   >   retracted prose.
   > - **The fix for that collision is not an order row.** The label is already declared, so a
   >   row would be a no-op *that looks like a fix* — booked separately as BGANIM-PLACE: a
   >   declared section grew from 4 bytes (the disabled stub) to 8192+ and ran through
   >   `test_mappings`'s pin. That is a placement/size question against the FROZEN TABLES.
   > - This item's own trigger is unchanged and still ahead of us: the first authored
   >   **effects scene**, which emits zero bytes today.
   >
   > **THE PREMISE THAT FAILED, recorded because it is the reusable part and it was THIS
   > LANE'S TOO.** Both lanes reasoned from an uncited joint premise — *"BgAnim is the
   > deferred section"* — and neither ever stated it, so neither ever checked it. It broke on
   > `grep BgAnim games/sonic4/map.toml`, one command nobody ran because nobody thought it was
   > a question. **This booking is part of why**: it sits four lines above the `map.toml`
   > quote and reads as though the two are one thing. Protocol bar 8's shared frame, arriving
   > on a *premise* rather than on an enumeration — and the frame-changer was only that this
   > lane read its own placement file instead of the story about it. **Cite the joint, or
   > nothing will ever check it.**
   >
   > *Both lanes also mis-scoped the same passage by opening the file AT the cited line and
   > reading downward: the reserved-slot comment names its subject in its FIRST line
   > (`map.toml:106-107`), above where either of us started reading. The hub ledgered this as
   > a repeat costume of the same defect class from earlier the same day.*

   The `order` check keys on a section's
   HEAD LABEL and this block's head is **content-derived**, so a row today would be inert and
   unverifiable — the vacuous-gate defect in a new costume. `map.toml` carries a reserved-slot
   comment at the intended position. **The first parcel that lands a real editor scene adds the
   row, and is also the first that can verify the placement.**
3. **Aurora needs to be able to MAKE one.** Their band editor is stranded at 448/448 tiles.
   **UNSTRANDED 2026-08-26 (`content/ojz-bg-roomy`)**: the shipped BG was regenerated from the
   auto-simplified source under owner ruling aurora d-10 — static 320/320, 128 tiles reserved
   for bands. This supersedes the test-only scope of the 2026-08-24 grant below for the BG
   art itself: the owner ruled the simplified picture ships.

**OWNER GRANT, 2026-08-24, verbatim: _"Yeah I've said a few times we can edit it howevver for
testing"_.** Relayed by the hub (banked empyrean `ff909fe`, reachability-verified at
`origin/main`). This authorizes editing the background art to free tiles so aurora's band
editor can be exercised end to end. **It reaches this lane because
`games/sonic4/data/editor_bg_override.json` is a blob WE ship**, and freeing tiles means art
changing on our side.

**SCOPE — TEST ONLY, and this is recorded as a boundary, not a footnote.** He ruled that the
art may be edited *for testing*. He did **NOT** rule on what the shipped background art
becomes; that remains the open art call behind the 448/448 ceiling. **Do not restate this grant
wider than "for testing"** — a test-scope grant quietly becoming a shipping-scope one is a
failure this suite has already recorded once, and the hub flagged it with the grant rather than
after it.

### CLOSED 2026-08-25 (`parcel/neg-label`) — a negative generator parameter emits a label that is not symbol-safe

> **CLOSED IN PLACE.** The enumeration the booking asked for was done FIRST, on the engine
> side, by measurement rather than by reading: a scratch `--extra-entry` module handed every
> `TABLE_GENERATORS` parameter a negative in turn. **None of the five generators carries a
> sign `ensure`** — `deform_sine` and `deform_triangle` guard only `256 % period == 0`,
> `v_column_perspective` / `v_column_floor` / `deform_zero` guard nothing — and every
> negative elaborated green (`deform_sine(amplitude: -8, period: 32)` samples `-8` at line 8:
> a legitimately inverted wave; `v_column_perspective(.., max_offset: -24)` an opposite tilt).
> So this was a **LIVE emission bug**, not a diagnostic-quality one, and the generator's job
> was to EMIT the negative, not refuse it. The old label was measured as a sigil parse error
> (`expected \`=\`, found Minus`) at the generated line.
>
> **Fix — the pattern:** `tools/effects_gen.py` `symbol_token()` renders any integer that
> becomes a SYMBOL component (`-8` -> `m8`; non-negatives byte-identical to before, so no
> committed label moves; injective over sign because `-0` is `0` and a digit-only token can
> never start with `m`; `_` is the joiner, hence not the marker). Used by BOTH the dedup key
> and the label; the CALL still spells the true signed literal so the engine's guard is the
> error surface. Labels are the generator's own domain — not a value rule, the da43a036
> one-owner ruling is untouched.
>
> **Same-class audit of the file (every JSON value that becomes an `.emp` token):** scene ids
> (`SCENE_ID_RE`) safe; generator names (table lookup) safe; `precision`/`transition`/
> `left_column_mask` (`_render_enum`) safe; `enabled` (`_render_bool_int`) safe; factor names
> (`FACTOR_NAMES`) safe; every integer VALUE slot safe (a negative literal is legal inside a
> call — the VOFFSET parcel relies on it); `budget_class` never emitted. Two more sites were
> NOT safe and were closed with siblings: the `bin` label fold `[^a-z0-9]+ -> _` is lossy, so
> `a-b.bin` and `a_b.bin` interned as two declarations under ONE label (now refused at
> `TableRegistry.intern`, naming both); and project.json zone/act ids reached `EditorScenes_*`
> labels and the module name unchecked (now refused in `ActNames`).
>
> **No poison added, by the rule the parcel set:** the engine refuses no negative, so there is
> no constructor message to prove. Tests are `TestJsonValuesBecomeSymbolSafeTokens` in
> `tools/test_effects_gen.py` (16 red against the pre-fix code; runner = build.sh's pytest
> lane, build-fatal). Zero-byte: all four ROM CRCs unchanged, `--no-cache` re-bake
> byte-identical.
>
> **Found beside it, booked below, NOT fixed here:** `deform_triangle` folds to `()` for
> EVERY input, positive included.


**Found beside the VFACTOR parcel (aeon `da43a036`), deliberately NOT fixed there** — it is a
VALUE question in a parcel whose whole point was drawing the SHAPE/VALUE line, and fixing it
inside the generator would have been the second source for a rule that this parcel had just
finished arguing belongs to one owner.

`tools/effects_gen.py`'s `render_table_ref` builds both its dedup key and its emitted label
with `str(v)` over the generator's parameter values:

```python
key   = f"{gen}:" + ",".join(str(v) for v in values)
label = "EditorDeform_" + gen + ("_" + "_".join(str(v) for v in values) if values else "")
```

Verified firsthand at `da43a036`. Since the VFACTOR parcel every `v` is guaranteed to be an
**integer** — but a NEGATIVE integer still passes shape, and `str(-8)` is `-8`, so a legal
authored scene yields `EditorDeform_sine_-8_32`. A `-` is not legal in an `.emp` label.

**Why it is worth booking rather than shrugging at:** the failure lands as a sigil parse or
unknown-symbol error **pointing at generated code**, for a scene the author spelled exactly
right — which is the identical failure shape `PRECISION_NAMES` already carries a comment about
(slices 1-2 emitting `precision: cell`). That is the third instance of the same class in this
one file, so the pattern, not the instance, is the thing to fix.

**Not yet established, and whoever takes this should establish it FIRST rather than assuming
it, because it decides whether this is reachable or merely latent:** whether any
`TABLE_GENERATORS` signature legitimately accepts a negative parameter. If none does, the
constructor refuses it anyway and this is a diagnostic-quality bug (a confusing error instead
of a clear one); if one does, it is a live emission bug. The two deserve different priorities
and the enumeration is cheap — read the generator signatures in `scene_dsl.emp`, do not infer
the answer from the Python side, which is the side that already lost this argument twice.

**Related, same file, already fixed at `da43a036` and recorded here as the pattern's second
instance:** `enabled` is a JSON **boolean** in the writer's schema while `layer()` takes an
`int`, so master emitted the bare word `False` into generated `.emp` for a legal Aurora scene.
Found by reading the WRITER's schema rather than our own field list. **The reusable enumeration
is the schema's per-field `type`/`enum`/`const`, not our field names** — our names tell us
which fields exist and say nothing about how the writer spells their values, and that
distinction has now bitten this contract three times.

### CLOSED 2026-08-26 (`parcel/triangle-fold`) — `deform_triangle` folds to `()` for every input (found 2026-08-25, `parcel/neg-label`)

> **CLOSED IN PLACE.** Reproduced first, verbatim shape (scratch `--extra-entry` probe):
> `deform_triangle(amplitude: 16, period: 64)` printed `T[0]=() T[16]=() T[32]=() T[48]=()`
> while `deform_sine(16, 64)[16]` printed `16` beside it. The "not established which"
> question below IS now established, by planting the effects_gen two-step emission form
> (`pub const SceneSrc_… = deform_triangle(…)` / `pub data …: [i8; 256] = SceneSrc_…`) in a
> REACHABLE module: the build dies **LOUDLY** with 256 x
> `[emit.type] expected an integer for i8, got unit` pointing at the generated `pub data`
> span — so a `"generator": "triangle"` Aurora scene was live-LOUD (a confusing 256-error
> wall at generated code), never silent zeros. `--extra-entry` itself refuses any `data`
> declaration (byte-neutral contract), which is why the lowering half needed the reachable
> plant.
>
> **Fix (engine/level/parallax_dsl.emp):** the element's block-tail `if` is hoisted into
> `tri_sample()`, a helper `comptime fn` whose single-level `return if` folds to a value
> (`iabs` in the same file is the standing precedent; a CALL in block-tail position is fine
> per §1) — waveform derivation written in the guard comment BEFORE coding. Post-fix, all
> 256 samples match an independently-spelled oracle (mismatches=0 probe).
>
> **Guards:** module-level `TriPin` ensures in parallax_dsl.emp pin T[0]=-16, T[16]=0,
> T[32]=16, T[48]=0, T[8]=-8 for (16, 64) — red-first against the pre-fix generator (all 5
> fired with `got ()`, which also proves `() == int` compares FALSE rather than erroring —
> the catch mechanism), and module reachability itself proven red-first with a deliberate
> failing ensure (parallax_dsl is in every profile's use closure; runner = every sigil
> build, both sonic4 shapes and demo). Plus
> `games/sonic4/test/poison/poison_tail_if_unit_fold.emp` (+ its emp_expect_fail row,
> 37/37): a verbatim copy of the PRE-FIX body, pinned differentially against the shipped
> generator — it documents that a value ensure is the engine's ONLY catch surface for §1's
> unit fold, and it flips to a lane failure (the retirement signal) if sigil ever fixes
> block-tail-if folding (inversion measured: the fixed-shape variant builds clean).
>
> **Sigil half (proposed in the parcel report, not edited here):** sigil silently folds a
> block-tail `if` to `()` in a value context with NO diagnostic even when non-nested; a
> warning/error at the fold site would catch the whole class at the source instead of
> per-value ensures. `TABLE_GENERATORS["triangle"]` confirmed mapped to this function, so
> the Aurora path is the fixed one. Zero-byte: all four ROM CRCs unchanged.

**Measured, not inferred** (scratch `--extra-entry` witness, sonic4 plain profile): with
`T = deform_triangle(amplitude: 8, period: 32)`, interpolating `T[0]`, `T[8]`, `T[16]` into an
`ensure` message prints `()` for all three — and identically for `amplitude: -8` — while
`deform_sine(amplitude: 8, period: 32)[8]` beside it prints `8`. The generator's body is a
`comptime for` whose element expression is an `if { .. } else { .. }` in block-tail position,
which is EMP_PITFALLS §1's shape (a block-tail `if` silently yielding unit) even though it is
not nested. Nothing shipped attaches a triangle table (the shipped scenes use `DeformTable_*`
sine tables and `deform_zero`; `grep deform_triangle` finds only the generator, the
`TABLE_GENERATORS` row, and docs), so this is LATENT today and reachable by the first
authored scene that picks `"generator": "triangle"` — which would presumably die at
`[i8; 256]` typing of a unit element, or worse, emit zeros. Not established which.

**Not fixed here** because it is an engine-side comptime defect (parallax_dsl.emp) in a
zero-byte tools parcel, and the fix wants its own red-first: a poison-style witness that
pins `deform_triangle(8, 32)[8] == 0` and `[0] == -8` (a linear ramp -A -> +A over half a
period: `((i % 32) * 8 * 4) / 32 - 8`), then the flat-accumulator rewrite EMP_PITFALLS §1
prescribes (or a sigil-side fix if the single-level tail `if` is itself the bug — that half
belongs to sigil and should be reported there with this witness).

### PARTLY CLOSED — the first real authored band does not assemble: two defects (found 2026-08-24)

> **DEFECT 1 IS FIXED AND REPRODUCED FIRST (2026-08-24, `parcel/bganim-extern-spelling`).
> DEFECT 2's ceiling and refusal ARE BUILT (2026-08-24, `parcel/bganim-slot-ceiling`) but the
> ruled option is BLOCKED ON SIGIL at any useful size — see "DEFECT 2 — DISPOSITION" at the end
> of this section, and read it BEFORE trusting any space figure in the older text, several of
> which are refuted in place.** See "DEFECT 1 — CLOSED" for what was measured in THIS tree.

**Provenance and its limits.** Aurora built the first genuinely editor-authored BG band against
this repo at `origin/master` `5349bea4`, in an isolated `git worktree` of their own — **this
tree was never touched**. Everything upstream of assembly worked: promotion on the real 448/448
document with `tiles.length` unchanged, `regenerate-level.sh` re-baked and self-verified
(`verify_level_bin: OK`), and `inject_editor_bg.py` wrote `BgAnim_Table: u16 = 1` with an
8192-byte bank blob (`cols*rows*BANKS*32`, derived). **Both failures are downstream of a correct
band.** ~~⚠ **Neither failure has been reproduced HERE** — they are aurora's observations, relayed
by the hub. Reproduce before fixing (protocol bar 6); the ROM has not been built in this tree.~~
**SUPERSEDED 2026-08-24: BOTH failures are now reproduced in this tree** (see DEFECT 1 — CLOSED,
and the confirmation block under DEFECT 2). The reproduce-before-fixing bar was met and it paid:
it turned up a stage-attribution trap (`./build.sh` dies in the expect-fail lane, not the sigil
build) and a per-entry error count that aurora's single band could not have shown.

**DEFECT 1 — CLOSED 2026-08-24 (`parcel/bganim-extern-spelling`). Reproduced here first, then
fixed, then gated.** Kept in full below because the reasoning is the record; what follows is
what was measured in THIS tree rather than relayed.

- **Reproduced.** The fixture is `tools/test_bg_emit.py`'s historical blob
  `33892d82c95d61a9214cb449fa7c67f683247ad3` (the real two-band override at `b0e5a661`: 128 +
  64 tiles, 8 phases each, 340-tile static blob), installed as
  `games/sonic4/data/editor_bg_override.json`, re-baked with `tools/regenerate-level.sh`
  (`REGEN_EXIT=0`), then built. `sigil build --aeon . --native`:
  `error: native build (sonic4 plain): build_program: 16 error(s);` — **sixteen**
  `[Error] unknown name \`BgAnim_Banks\``, one per pointer entry (2 bands × 8 phases). Aurora's
  eight was one band's worth; the defect is per-entry, exactly as stated.
- **A note on where the build stops.** With a band present the canonical `./build.sh` does NOT
  reach the sigil build at all — it dies earlier in the **expect-fail lane**, whose `sentinel`
  case counts diagnostics and reported `got 17 [Error] diagnostic(s), expected 1` (16 + its own
  sentinel), printing `emp_expect_fail: FAIL — the sentinel did not fire`. That message names
  `--extra-entry` and reads like a lane defect, not a band defect. **Attribute by stage:** it is
  the band's errors leaking into a whole-program diagnostic count. Worth knowing before the next
  lane loses an hour to it.
- **`extern("BgAnim_Banks") + <off>` WORKS HERE — measured, not inherited.** With the array
  respelled, the 16 errors vanish and the build advances to layout. `docs/EMP_PITFALLS.md` §5's
  "extern() poisons comptime-ness" does **not** bite: §5's second failure mode is an emitted
  image that a **comptime pin then compares**, and nothing pins this one. No `here.provisional`
  error appeared in any file.
- **The fix** is one expression, `tools/inject_editor_bg.py`'s `banks_list` join, plus a comment
  block at the emission site recording why the `extern` is load-bearing.
- **The gate that was missing.** Every pre-existing test in `tools/test_bg_emit.py` called
  `validate_band_coherence` and stopped there — **nothing ran the emitter**, so the only covered
  path was the stub, which emits no pointer array at all. New
  `tools/test_bg_emit.py::TestBgAnimEmission` (8 tests) drives the real `main()` over the
  two-band fixture into a temp dir and gates the RULE — *no bare link-time symbol inside an
  emitted array initializer* — not the substring `extern`. The matcher
  (`bare_symbol_refs_in_emitted_emp`) is itself unit-tested against the historical bad spelling,
  the accepted one, `embed(...)`/`Data.empty` initializers, and the all-literal header row, so a
  green cannot mean the matcher stopped looking. Red-first against the unfixed generator: 2
  failed / 6 passed, the two failures being exactly the two spelling assertions. It runs under
  `build.sh`'s `python3 -m pytest tools` lane. A missing fixture blob **fails loudly** there
  rather than skipping (the sibling coherence class skips; that is defensible for an invariant
  check and is not defensible for a gate whose entire purpose is that this arm has never run).
- **Byte-neutral on master, proven not assumed:** with no `anims` the stub branch is taken and
  the changed line is unreachable; `test_the_stub_arm_emits_no_pointer_array_at_all` asserts
  that, and all four ROM shapes were rebuilt from `rm -f` with unchanged CRCs.
- **Still true and still the shape of the thing:**

**DEFECT 1 (original text) — `inject_editor_bg.py` emits a symbol form the language does not accept.**
`tools/inject_editor_bg.py:178` builds the per-band pointer array as
`', '.join(f'BgAnim_Banks + {off}' ...)`, and the generated
`games/sonic4/data/generated/ojz/act1/bg_anim.emp` therefore writes
`[BgAnim_Banks + 0, BgAnim_Banks + 1024, …]` → **8× `[Error] unknown name 'BgAnim_Banks'`**.
- **Not a forward reference** — aurora tested that hypothesis by moving the declaration above
  its use and got the identical eight errors. They reported the tested answer, not the
  plausible one.
- **The accepted spelling is already in the same directory**: `sec_local_maps.emp:20`, the same
  generated family and the same `[*u8; N]` pointer-table shape, uses
  `extern("OJZ_SecN_LocalMap")` for every entry. Aurora verified `extern("BgAnim_Banks") + <off>`
  resolves completely.
- **This is a booking discharging exactly as written, not a surprise.** The injector's own
  comment at `:152-159` says the array is "link-relative, resolved at link" and then, in
  capitals, **"FORMAT-FAITHFUL BUT NOT BYTE-PROVEN: no act in the tree authors BG animation, so
  the six-target gate exercises only the stub — the first animated act proves this arm."** The
  intent was right and only the spelling was wrong; this run is that arm's first execution.
  Byte-neutral on the stub (which emits no pointer array at all), byte-moving on any tree
  carrying a real band.

**DEFECT 2 (BGANIM-PLACE) — a declared section outgrew its pin.** *(CLOSED 2026-08-26 — the
placement half by sigil b0363140's derived layout; see the closure note on the DISPOSITION
block below. The size ceiling that landed under it stays.)* With defect 1 patched the
build reached layout and stopped:

```
sections `test_mappings` [0x3B672, 0x3B6A2) and `ojz_bg_anim` [0x3B270, 0x3D29E) overlap (colliding pins)
```

> **CONFIRMED INDEPENDENTLY HERE 2026-08-24** (`parcel/bganim-extern-spelling`; defect 2's text
> above is unchanged, this is an addition). With defect 1 fixed and the two-band `b0e5a661`
> fixture installed, `sigil build --aeon . --native` stops at exactly this diagnostic:
> ```
> error: native build (sonic4 plain): span pass (spread round, post-growth): span pass:
>   resolve_layout: 1 diag(s); first Some(Diagnostic { level: Error, message: "sections
>   `test_mappings\070` [0x38A40, 0x38A70) and `ojz_bg_anim\082` [0x38632, 0x4468C)
>   overlap in the image (colliding pins)" })
> ```
> **The addresses differ from aurora's and that is expected, not a discrepancy** — mine is the
> PLAIN shape with a TWO-band 49,152-byte blob, theirs the shape they built with one 8,192-byte
> band. **Do not treat either address set as the number to fit a pin to**; a band's size is
> `cols*rows*BANKS*32` and two runs of the same defect already disagree by 48 KB, which is the
> concrete form of "a hand-fitted pin fits exactly one geometry" below. Note also the `\070` /
> `\082` suffixes sigil now prints on section names; aurora's quote has none.

**This is NOT the deferred `map.toml` order row** — see the retraction banked under
"EFFECTS-W1 … item 2" above; `ojz_bg_anim`'s head label `BgAnim_Table` has been declared at
`map.toml:120` all along, and adding a row would be a no-op that looks like a fix. What changed
is SIZE: the disabled stub is 4 bytes (`BgAnim_Table: u16 = 0` plus `BgAnim_Banks = Data.empty`),
a real single band is 8192+. ~~**Open and deliberately not pre-judged: whether `ojz_bg_anim` or
`test_mappings` is the section that should move.**~~ **← RULED. Owner decision `d-9`
(`docs/decisions.jsonl`): `fitinplace` — keep BG animation where it is and accept a small
ceiling; relocation stays available and is explicitly not foreclosed.** The stub is **2** bytes,
not 4 (`u16 = 0` is 2, `Data.empty` is 0). That is a
FROZEN-TABLES placement decision rather than a `map.toml` one, and it wants the byte-moving
parcel ritual (repin → refreeze `--ab`, full sigil suite) since a real band moves bytes.
**⚠ That ritual CANNOT RUN for this growth — see the DISPOSITION block at the end of this
section; the re-derivation goes through the pass that is failing.**

**Aurora deliberately did not author an order row**, which was right for a better reason than
either lane first gave: a guessed pin yields a ROM that boots and is *subtly corrupt*, which is
worse than no ROM for a visual test.

**~~THE FIX IS A RE-DERIVATION, NOT A RELOCATION~~ — measured 2026-08-24, and one supporting
number that arrived with it is REFUTED.** *(The headline itself is now REFUTED too: a
re-derivation is not available. `derive_offcanon` fails on the same tree with the same
diagnostic — measured, see the DISPOSITION block at the end of this section. The measurement
of the allotment below is correct and stands.)* The frozen boundary table allots `ojz_bg_anim`
**exactly two bytes**: at sigil `origin/master` `805370b1`,
`crates/sigil-harness/golden/offcanonical_sizes/s4_debug.txt` reads `BgAnim_Table 0x27e70`
then `Map_TestObj 0x27e72`. Two bytes is exactly the disabled stub (`u16 = 0` is 2,
`Data.empty` is 0), so **the cache is measuring a layout in which the band system emits
nothing** — `test_mappings` is not misplaced and `ojz_bg_anim` is not greedy. A real single
band needs ~8,250. Read out of sigil's committed table, independent of aurora's build, and
confirmable here without building anything.

**Do not hand-move a section.** A band's size is `cols*rows*BANKS*32` and changes with every
scene an author makes, so a hand-fitted pin fits exactly one geometry and breaks on the next
scene (aurora's argument, and it is the load-bearing one). The mechanism is
`derive_offcanonical_sizes.sh` — **it lives in SIGIL's tree**, takes `AEON_DIR` plus a sigil
binary, and its header calls the addresses it writes golden provenance re-derived on a
**RULED** post-flip re-baseline. Two consequences: it cannot run until this tree carries a real
band, and a golden re-baseline is a ruled act in sigil's repo rather than a script we run at
them. **That plausibly makes wave 1 a three-lane project** — flagged by the hub, not yet put to
sigil, and correctly not put to them until this parcel lands.

> **⚠ REFUTED, and it was the number carrying the "not a ROM-space problem" conclusion.** The
> claim relayed with the above was that `OJZ_Palette` carries **22,664 bytes of headroom**
> (`0x27e70 - 0x225e8`) so an 8 KB band "fits comfortably in that neighbourhood". **It has 6
> bytes free.** That gap is the SIZE of a four-blob section, not slack: `act_assets.emp:12-30`
> makes `OJZ_Palette` the first of four `pub data` blobs in `ojz_act_assets`, and they measure
> 96 + 32 + 8,192 + 14,338 = **22,658** against a 22,664 gap. **14,338 of it is `bg_tiles.bin`
> — the 448/448 ceiling aurora is blocked by is sitting inside the space offered as free.**
>
> **The general rule, because it applies to every row in that file: the golden table records
> BASES ONLY, no sizes — a gap is an ALLOTMENT, never proven free space.** These bases are
> tightly packed, proven twice over: `OJZ_Palette`'s allotment matches its content to 6 bytes,
> and `BgAnim_Table`'s allotment is exactly 2 for an exactly-2-byte stub. **There is no slack
> anywhere in this table by construction.** Any "N bytes of headroom" read off it is a
> section's size (the companion `Map_TestObj 3,082` is the same class).
>
> **⚠ MY OWN "NO SLACK ANYWHERE" CLAIM IS REFUTED — by this repo's own `map.toml`, and the
> cascade below is BOUNDED, not open-ended (measured 2026-08-24, same session).** I proved
> tight packing at two points and wrote *"no slack anywhere in this table by construction"*.
> That is the completeness over-claim protocol bar 17 exists for: two points are not a
> distribution, and **bases-without-sizes cannot establish density anywhere** — which is the
> exact categorical finding that killed the headroom claim, pointing the other way. The hub and
> aurora spotted the symmetry; neither of us had noticed the weapon cuts both ways.
>
> **What the table actually looks like downstream of the growth site.** `BgAnim_Table` has
> **15** labels after it by address (verified numerically; a string sort of varying-length hex
> gives 40-of-93 and is wrong — the trap caught two lanes today, this one included on a first
> attempt). But those 15 are not a packed run:
> ```
> 0x28ee0 HeightMaps
> 0x48000 Dac_Temp_Blip     ← 127,264 bytes later
> ```
> ~~`HeightMaps` + `HeightMapsRot` are 4,096 + 4,096, so **~119 KB of that span is genuine
> slack**~~ **← REFUTED (d-8); the corrected figure is 11,424 B, derived below.** The span
> holds `AngleTable`, `SolidityTable`, `Map_Sonic`, `DPLC_Sonic` and `Art_Sonic`
> (`s4.debug.lst` lines 2225-2229), which is invisible in the frozen table *by construction*
> — it lists a SUBSET of labels. This paragraph is the repo bar's founding instance: **a gap
> between two rows of that table is an ALLOTMENT, never proven free space** (`docs/OVERSEER.md`).
> The rest of the paragraph stands: `0x48000` is not a packed base at all. **`map.toml:167-176`
> declares it as an `[[anchor]]`** (`dac_banks`, matched by ADDRESS because the Z80's `SetBank`
> latches the LMA), as is `0x58000` (`sound_bank`). Those are **hardware-pinned and cannot move.**
>
> **THE FIFTEEN IS NOT WRONG — it answers a different question, and this line is here because
> the phrasing below invites the misread.** Fifteen labels DO follow `BgAnim_Table` by address.
> Only five can SHIFT, because the sixth is anchored. Two true answers to two questions, the
> same distinction that separated "no local slack" from "abundant total space" an hour earlier
> in this booking. Do not read what follows as a retraction of the count.
>
> **So the blast radius is FIVE labels of the fifteen:** `Map_TestObj`, `Ani_Sonic`, `Ani_Tails`,
> `Ani_Particle`, `HeightMaps` shift; everything from `Dac_Temp_Blip` onward is anchored. ~~An
> ~8,248-byte band is **~7% of the slack** sitting before that anchor, so the growth is absorbed
> inside one region and **this is a bounded shift, NOT a full golden re-baseline.** That
> LOWERS the three-lane likelihood this file raised a few paragraphs above — treat that
> escalation as superseded.~~ **← the percentage is REFUTED with the 119 KB it was computed
> from; an 8,238 B band is ~72% of the real 11,424 B, not 7%. The "bounded shift" conclusion
> survives (the five-label list is correct and was read off `map.toml`'s anchors), but the
> three-lane escalation does NOT: see the 2026-08-24 disposition block at the end of this
> section — the re-baseline this depends on cannot be produced at all today.**
>
> **Scoreboard, stated plainly because both halves matter:** aurora's *conclusion* ("local, not
> cascading") was closer to right than mine, though the query they reached it with could not
> support it — they took a span from build output and grepped a table whose addresses do not
> overlap it. My *cascade* argument was better-supported and still wrong, because it
> generalised density from two measurements. **A correct conclusion from an unsupported query
> and a wrong conclusion from a sound-looking one landed in the same hour.** The thing that
> settled it was neither: it was reading the placement file that declares the anchors.
>
> **~~Knock-on, and it is the more load-bearing half.~~ SUPERSEDED by the anchor measurement
> above — kept because the reasoning is instructive and was the best-supported read available
> before anyone looked at `map.toml`'s anchors:** Aurora predicted every base after
> `ojz_bg_anim` would be invalidated, then withdrew it on measuring the two labels adjacent
> ("damage local to that seam, not cascading"). **With zero slack an ~8,248-byte growth
> necessarily shifts every base after it.** Adjacency does not establish locality — sigil
> reports the FIRST overlap, and no further reported collisions is not evidence of none. The
> withdrawn prediction looks correct; the measurement did not bear on it. **So expect a full
> re-baseline, not a seam repair**, which raises rather than lowers the three-lane question.
>
> **None of this changes the fix — it strengthens it.** Re-derivation recomputes every base, so
> a cascade is expected and harmless, and with 6 bytes free next door **a hand-fitting was
> never even available.**
>
> **~~Still open~~ CLOSED 2026-08-24, same session: ~8 KB fits the ROM with room to spare.**
> `EndOfRom` is `0xA3290` = 668,304 bytes in the s4_debug frozen table, and the built ROMs on
> disk are 699,106 (`s4.bin`) / 715,010 (`s4.debug.bin`). Against a 1 MB power-of-two pad that
> leaves ~350 KB unused; an ~8,248-byte band is about **2%** of it, and this is nowhere near
> any cartridge limit. **So "not a ROM-space problem" is TRUE — it was only the reason offered
> for it that was false.** The distinction is the whole point of the refutation above: there is
> no LOCAL slack (6 bytes), and total space is abundant. Those are different questions and only
> the second one licenses the conclusion.
> *(Caveat, honest rather than material: the two ROMs are whatever the last build left on disk
> and their freshness was not established — see the landing lane's `rm -f`-before-rebuild rule.
> An order-of-magnitude answer survives that; do not quote the byte counts as current.)*
> **Freshness now established (`parcel/bganim-slot-ceiling`, 2026-08-24): both figures are
> current — all four shapes rebuilt from `rm -f`, `s4.bin` 699,106 / crc `c7b9d10d`,
> `s4.debug.bin` 715,010 / crc `f0175028`.**

**DEFECT 2 (BGANIM-PLACE) — DISPOSITION 2026-08-24, `parcel/bganim-slot-ceiling`. The
ceiling is built and gated; the ruling itself is BLOCKED ON SIGIL at any useful size.**

> **CLOSURE 2026-08-25/26 (`parcel/bganim-room-retire`) — the layout blocker is CLOSED by
> sigil's derived layout; the placer arm is RETIRED here.** sigil master `b0363140` (merge of
> `feat/derived-layout`; release binary `a4eac185`, source read at `a0fbee24`) changed what
> §2/§3 below measured: a pure-data section that collides at its frozen pin is now re-measured
> at a disjoint scratch slot (`crates/sigil-harness/src/native.rs:2315-2348` `measure_or_spread`
> → `:2353` `image_lens_pinned(.., scratch_data=true)`, `:2372-2394`), its neighbours pack
> downstream from real sizes (`:2549` `packed_true_bases`), and a base drifting past the stale
> frozen table is the `[layout.provisional-drift]` WARNING (`:2605-2616` `GROWTH_DRIFT_TOLERANCE
> = 0x1000`, `:2687-2697`), never a stop. The `0x400` spread survives only as the fallback for
> relaxable CODE growth (`:2327-2343`) — it bounds no data section. What still fails, loud, is a
> run overrunning a declared HARDWARE anchor: `:2670-2676` holds the anchor absolute and the
> final `resolve_layout` overlap check (`crates/sigil-link/src/relax.rs:273-286`, the
> `colliding pins` diagnostic) refuses it. That is exactly the §1 ROM-room limit and nothing
> else. The `GROWTH_DRIFT_TOLERANCE` vs spread asymmetry flagged below is therefore moot.
>
> **Retired in aeon:** `tools/bganim_room.py`'s "placer room" (its `_SPREAD` regex over
> `native.rs`, `sigil_spread_step()`, `placer_room()`, the `SIGIL_BUILD` dependency and the
> `BINDING` verdict), and `BGANIM_PLACER_CEILING` + the two-limit chooser in
> `tools/inject_editor_bg.py` — deleted, not disabled, as sigil's design note asked
> (`docs/superpowers/notes/2026-08-26-derived-layout-design.md` §4: "a stale-but-green tool is
> the worse failure"). The tool now prints the ROM room, `BGANIM_SECTION_CEILING`, and a
> `binding limit:` line naming which of those binds. Gated by
> `tools/test_bg_emit.py::TestBgAnimPlacerArmRetired` (red-first: 3 of 4 failed against the
> old tool). Zero-byte: all four shape CRCs unchanged. §3's "cannot be built AND cannot be
> re-frozen" is no longer true — a grown band builds with one warning and the refreeze
> runs the same walk.
>
> **What REMAINS open:** (1) the first real band has still not landed — aurora's 8,238 B
> band is now an ACCEPTANCE at the 9,394 B ceiling (`test_auroras_authored_band_is_refused_
> with_its_own_numbers` flips to its acceptance arm), but the animate-vs-static question at
> the end of this block is unchanged and still an emulator check; (2) the PHYSICAL ceiling —
> ~11.4 KB before the `0x48000` `dac_banks` anchor is ONE 8 KB band per act. A second band
> needs the "banks late, data unbounded" re-layout ("The ROM-tail character-art exile has now
> happened TWICE — relayout pressure", above), not a bigger `BGANIM_SECTION_CEILING`.

Owner decision `d-9` ruled `fitinplace` — keep BG animation where it is, accept a small
ceiling, keep relocation open. That was ruled against the ROM-room number. **The ROM is not
the binding limit.** Both limits are stated here because conflating them is what produced
every retracted figure above.

**1. ROM room — 11,424 B. Derived, per shape, from the LISTING and the image; never from a
boundary-table gap.**

| shape | `Art_Sonic` LMA | + blob on disk | packed end | `dac_banks` anchor | room |
|---|---|---|---|---|---|
| `s4` | `0x2CE60` | 97,472 | `0x44B20` | `0x48000` | **13,536** |
| `s4.debug` | `0x2D6A0` | 97,472 | `0x45360` | `0x48000` | **11,424** |
| `demo`, `demo.debug` | — | — | — | — | **n/a — no `ojz_bg_anim` section** |

Instruments: label LMAs from `s4.lst` / `s4.debug.lst`; `art/optimized/characters/sonic.bin`
on disk (the blob `collision_data.emp`'s `const _art_sonic = embed(...)` names); the anchor
from `map.toml`'s `[[anchor]] dac_banks`. Cross-checked against the ROM image: both spans are
**pure `$00` fill**, exactly 13,536 and 11,424 bytes — so spending them does not grow the ROM
file, it spends what `Art_Sonic` may grow into. **Minimum 11,424 B**, + the 2 B the stub holds
= 11,426 B reachable. *(This supersedes d-9's 11,427: that came from a constant-byte run scan
starting at `0x4535D`, three bytes inside `Art_Sonic`'s own trailing zeros. The owned-span end
is `0x45360`. The difference is immaterial; the instrument matters.)*

**`demo` does not carry this section at all** — and note *how* that was established, because
the frozen table gets it wrong in the safe direction: `demo.txt` / `demo_debug.txt` have no
`BgAnim_Table` row, but the listing shows `BgAnim_Table` at `0x100FE` in `demo.lst`. It is
`games/demo/data/demo_data.emp`'s own stub inside the `demo_data` section, not `ojz_bg_anim`;
`tools/inject_editor_bg.py` is hardcoded to sonic4 and `regenerate-level.sh` only calls it for
sonic4. The ceiling is a sonic4 fact. **A missing row in the frozen table was not the evidence
— the listing was.**

**2. PLACER room — 1,026 B, and IT IS THE BINDING LIMIT. This is the finding that changes the
ruling's cost.** *(HISTORICAL as of sigil b0363140 — see the closure note at the head of this
disposition; the numbers below describe the pre-derived-layout chainer.)* sigil's chainer measures every section's image length at its frozen
provisional base; when a grown section collides there it retries **once**, with a cumulative
`0x400`-per-rank spread (`measure_or_spread`, sigil `crates/sigil-harness/src/native.rs`).
`ojz_bg_anim` and `test_mappings` are ADJACENT in the declared order, so the retry buys
exactly ONE step:

| shape | frozen allotment | + one spread step | placer room |
|---|---|---|---|
| `s4` | 14 | 1,024 | **1,038** |
| `s4.debug` | 2 | 1,024 | **1,026** |

**Measured, both directions, both shapes** (`sigil build --aeon . --native`, real bands baked
through `tools/regenerate-level.sh`): a **814 B** section (3 slots) BUILDS in both shapes; a
**1,070 B** one (4 slots) FAILS in both, and sigil's own diagnostic reports the available spans
as `0x40E` / `0x402` — exactly `allotment + 0x400`. The derivation reproduces the measurement
in both shapes.

**3. THE ESCAPE HATCH DOES NOT EXIST — verified, not reasoned.** The obvious answer is "grow
it, then refreeze". `derive_frozen_table` → `resolve_frozen_sections` → `true_bases_by_index`
→ **the same `measure_or_spread`**. Run against this tree carrying the 1,070 B band,
`target/release/derive_offcanon` fails with the identical diagnostic:

```
ERROR: derive s4: span pass (spread round, post-growth): span pass: resolve_layout: 1 diag(s);
  first Some(Diagnostic { level: Error, message: "sections `test_mappings\070` [0x38A40, 0x38A70)
  and `ojz_bg_anim\082` [0x38632, 0x38A60) overlap in the image (colliding pins)" })
```

`repin` resolves against the aeon listings, which need a successful build. **So a tree whose
band exceeds ~1 KB can be neither BUILT nor RE-FROZEN.** There is no `SIGIL_*` env knob for
the table path (`load_frozen_table` uses a compile-time `CARGO_MANIFEST_DIR`) and no flag that
relaxes the spread on a canonical profile; the machinery that *would* work exists but is bound
to the `--stress-art` fixture (`image_lens_pinned(.., fixture=true)` measures
position-independent DATA at disjoint scratch slots — and `ojz_bg_anim` IS pure data).

Note also that sigil's own `GROWTH_DRIFT_TOLERANCE` is `0x1000` while the measuring spread is
`0x400`: the tolerance that decides whether a drift is acceptable is four times looser than the
pass that has to measure it first. That asymmetry looks unintentional and is worth putting to
the sigil lane along with the rest.

**⇒ BLOCKED, and this is a constraint conflict, not a design choice.** The ruled option
`fitinplace` is available today only at **1,026 B ≈ 3 animated tiles**, against aurora's 8,238 B
band. Nothing in aeon can raise it. **This is the item to put to sigil**, and it makes wave 1
the three-lane project this file raised and then withdrew — withdrawn for the right reason at
the time (the blast radius IS five labels), reinstated for a different one (the re-baseline
that would absorb those five labels cannot be produced).

**WHAT LANDED ANYWAY, because it is right regardless of which way the block is resolved:**

- **The cryptic collision is replaced by a sentence.** `tools/inject_editor_bg.py` now refuses
  an over-ceiling act *before it writes any artifact*, naming the band count, the per-band
  geometry, the section's size with its arithmetic shown, the ceiling, how far over it is,
  **which of the two limits bound it** (they have completely different remedies), and how many
  slots would fit. Precedent and quality bar: the `BGANIM_MAX_BANDS` assert in the same file.
- **The check totals ALL bands, never each band.** `BgAnim_Banks` is one blob for the whole
  act. Decision `d-6` proposed a per-band cap and this project's own deleted content refuted
  it — 32x4 + 16x4 each pass a generous per-band limit while their sum is 49,242 B. Kept
  executable as `test_bands_each_under_the_ceiling_but_over_in_total`.
- **Both ceilings are re-derived on every sonic4 build** *(now ONE — the placer arm is retired,
  closure note above)* by `tools/bganim_room.py --gate`
  (wired into `build.sh` beside `effects_seam_gate`), from the listing + the image + the map,
  and **it fails loudly when it cannot measure** rather than reporting zero. It is the standing
  guard for the revisit `d-9` named: the day `Art_Sonic` grows into the reservation, the build
  says so and names the two options.
- **14 new tests** in `tools/test_bg_emit.py::TestBgAnimSectionCeiling`, run by `build.sh`'s
  `python3 -m pytest tools` lane (total 1,347 → 1,361). The refusal *matcher* is itself under
  test against the collision diagnostic being replaced — a matcher that accepted that message
  would accept exactly the failure this work removes.
- **Byte-neutral on master, proven not assumed:** all four shapes rebuilt from `rm -f` with
  unchanged CRCs (`c7b9d10d` / `f0175028` / `c708b114` / `dec88cc1`).

**NOT DONE, deliberately: the reservation itself.** The mechanism that would make the
allotment content-independent — pad the section to the ceiling in both arms, so any band up to
the ceiling needs no golden re-derivation — is implementable in one place
(`inject_editor_bg.py`, a padded `bg_anim_banks.bin`; `map.toml` has no declared-reservation
form, only `order` / `region` / `anchor` / `hole` / `budget`, so this is the only mechanism
available without a sigil feature). It was NOT landed because at any useful ceiling it breaks
the build on the very first commit, for the reason in §3 above, and at a ceiling that builds it
would permanently spend 1 KB to buy an unusable band size. **Its cost, for the ruling record:
at a 9,394 B ceiling the stub grows 2 → 9,394 B, i.e. +9,392 B in each sonic4 shape and 0 in
demo, with the ROM FILE SIZE UNCHANGED** (the growth lands in the `$00` fill measured above) —
what is spent is `Art_Sonic`'s growing room, leaving 2,032 B (63 tiles) in the debug shape.

**PROPOSED CEILING, FLAGGED FOR THE OWNER — not decided here.** Section size is
`2 + 44 x bands + slots x 256`; the worst case is all 4 band records plus all 448 slots =
114,866 B. Against the 11,426 B reachable:

| total slots | ceiling (worst case at 4 bands) | `Art_Sonic` room left, debug | in tiles |
|---|---|---|---|
| 32 — aurora's band exactly | 8,370 | 3,056 | 95 |
| **36 — proposed** | **9,394** | **2,032** | **63** |
| 40 | 10,418 | 1,008 | 31 |
| 43 — the most that fits | 11,186 | 240 | 7 |
| 44 | 11,442 | *does not fit* | — |

Reasoning for 36: a ceiling equal to today's band (32) gives an author **zero** room to grow
one, which is the workflow tax the ruling exists to avoid — the next column added breaks the
build. 36 buys one more 4-row column (or a second small band) for 1,024 B, ~1% of `Art_Sonic`,
while being +12.5% of the band budget. It is a judgement call between two thin margins and the
owner should pick the row. `BGANIM_SECTION_CEILING` in `tools/inject_editor_bg.py` carries 36
today with the whole derivation beside it; changing the row is a one-line edit that the room
gate then re-checks against the live layout.

**Still untested at the end of all this — and the boundary matters.** This parcel can
establish that a band **assembles and is placed**, and that its bytes are in the image. It
**cannot** establish that the band ANIMATES: nothing in a build watches a frame, and a band
that assembles, places correctly and renders as a static or garbled strip would satisfy every
check here and every check a build lane can add. Do not read a green build as a working effect.

- **The driver IS reached — that half is closed** (verified in
  `games/sonic4/test/ojz_scroll_test.emp`): `GameState_OJZScroll_Update` is declared at `:556`,
  the unconditional `jbsr BgAnim_Update` is at `:821`, and there is **zero `rts`** between them,
  so it ticks every frame on a plain boot.
- **What remains untested is everything downstream of that call**: whether the bank pointers
  select the right art, whether phase stepping produces visible motion, whether promoted tiles
  land where the layout says. That is a **foreground emulator check owned by the aurora lane's
  rerun**, not something a build lane or a background agent can reach.

Aurora reruns this exact pipeline once the placement block clears, so **tell them directly**
rather than leaving it to the board — and tell them the block, not just the ceiling.


## From the ring-sparkle parcel (2026-08-26)

Design note: `docs/superpowers/notes/2026-08-26-ring-sparkle-design.md`. Branch `parcel/ring-sparkle`.

### ~~Ring collect sparkle~~ — SHIPPED 2026-08-26
**What:** collected rings vanished in the overlap frame (rings are buffer entries, not objects). Now `RingCollision` invokes `Game.ring_collected` (a3 = the entry) before `RingBuffer_Remove`; sonic4 binds `RingSparkle_Spawn`, a fire-and-forget effect on the ring's spot: S3K's `Ani_RingSparkle` transcribed (duration byte 5, four flip-variant frames on ONE 2x2 piece, 4 x (5+1) = 24 display frames), band = player + 1 (S3K's $100 -> $80), resident 4-tile art from the sonic_hack `Ring.bin` donor (tiles 10-13, identity palette, CRAM line 1) at `VRAM_RING_SPARKLE` = 924. Pool exhaustion skips the sparkle, never the collect. Comptime gates: display frames derived from the script bytes, palette census, size; `poison_ring_sparkle_frames` proves the frame gate red. The demo binds nothing and is byte-identical.
**Still open (emulator, controller-owned):** (1) a frame-by-frame capture of one collect — position, band, the 24-frame life, the 4 orientations; (2) the replay fixtures: `Replay_Hash` folds Effect free-stack OCCUPANCY (`engine/system/replay.emp:274`) and `Replay_OJZ_Slide_Fixture` collects rings, so checkpoints landing within 24 ticks of a collect now differ by design — re-verify or re-stamp both fixtures.

### Ring draw order vs. other objects (report from the S3K comparison)
**What:** `DrawRings` runs after the band loop (`engine/objects/sprites.emp:449`), so rings are appended LAST to the SAT — behind every object sprite in every band. S3K draws rings at priority $100 (the player's bucket; the player wins by slot order) which is IN FRONT of the $180+ objects (most badniks, monitors). Relative to the player Aeon matches S3K; relative to other objects it does not (a badnik overlapping a ring hides it here, shows it there).
**Why not now:** cosmetic, rarely visible, and moving `DrawRings` into a band is a `Render_Sprites` change with the sprite-cap shortcut caveat at `sprites.emp:517-521` (the shortcut is only equivalent because DrawRings emits nothing at the cap).
**When ready:** with the next `Render_Sprites` parcel; decide the ring band against the object bands then.

### BGANIM authoring ceiling raised 9,394 -> 12,288 B — OWNER RULED 2026-08-26 (d-9), APPLIED

The ceiling was derived on 2026-08-24 against a room of 11,424 B (debug shape). The roomy-BG
regeneration (aeon 94b384a2) dropped the static background from 448 to 320 unique tiles, freeing
128 x 32 = 4,096 B in exactly the run that ends at `Art_Sonic`, so the room grew to **15,152 B
debug / 17,264 B plain** — re-measured from the build's own `bganim_room` block, not assumed.
That left the ruled ceiling stale-low by ~5.7 KB, and the BINDING limit stopped being the
hardware and became a number we chose. Put to the owner; he ruled raise-with-margin rather than
to the physical edge. 12,288 B (12 KiB) leaves **2,866 B** under the debug room for other content
in that run to grow into without forcing a re-layout, and is still short of two 8 KB bands
(16,384 > 15,152) — that remains the "banks late, data unbounded" re-layout's job, booked in §7.
Byte-neutral to apply (no shipped act carries a band yet): all four shapes identical at
b96319e3 / 7be32302 / bf2cdb42 / 62a0019e. `tools/bganim_room.py` re-derives the room every build
and fails if the ceiling ever stops fitting, so a future shrink of that run cannot pass silently.

### Sigil placer: a measuring round can alias to zero and mis-measure a section — MECHANISM CORRECTED 2026-08-26, ACCEPTED BY SIGIL (BGROOM-3)

> **The mechanism below is REFUTED; the symptom and measurement are sound.** An unresolved
> operand is a hard error in sigil, not a width guess, so "encodes abs.w because the address is
> unknown" cannot be the cause. Sigil reproduced our symptom exactly (7 nops in RingCollision;
> `player_sensors` 0x4DC measured vs 0x4F4 packed; the same twelve `lea` sites) and found the
> real cause: the collision-fallback SCRATCH SLOT wraps the 24-bit bus — `collision_data` at
> scratch slot 41 = 0x300_0000 masks to 0x0, where `abs.w` IS legitimate, so the section was
> measured at an address that aliases zero. Their fix (`fix/measure-at-packed-base`) makes every
> measuring round exact at its own bases, deletes the scratch/spread fallbacks (which also
> removes the ~0x400 growth cap: 5000 B of growth now builds with drift warnings), and adds a
> non-convergence diagnostic naming width-flipping sites with both encodings. CONSEQUENCE FOR
> US: our explicit `lea (X).l` / `movea.l #ptable` pins in player_sensors are a superseded
> workaround, not a style rule — see EMP_PITFALLS §11's correction; keep them only if a cycle
> shape wants them. What survives: when the placer names a pair nothing touched, suspect how one
> of them was MEASURED, not the map.

*Original proposal text, superseded:*
**Surfaced during:** ring-sparkle, 2026-08-26. **Measured on bare master:** seven `nop`s added to `RingCollision` fail the build with `packed layout overlaps at its real bases — a run grew into a declared anchor ... sections section [..] and player_sensors [..] overlap` — the named pair is innocent.
**Mechanism:** `packed_true_bases` (`sigil-harness/src/native.rs`) measures sections in a provisional round; an UNSIZED `lea ROMTable, aN` whose target's provisional address is not yet known encodes abs.w (4 B) there and abs.l (6 B) at the real base. `player_sensors`' `probe_core` has 12 such sites, so it measured 24 B short and the walk placed `section` 24 B into it; the remeasure then reports a "real" overlap and the walk gives up instead of iterating. Any upstream growth past the slack exposes it; +2/+6 B did not, +14 B did.
**Aeon-side fix shipped:** the three `probe_core` pointers pinned (`lea (X).l`; `movea.l #{ptable}` for the template arg — `({ptable}).l` does not parse) — same 6-byte encodings, same cycles, measurement now base-invariant. Grep candidates for the same shape before the next byte-moving parcel: `grep -rn "lea     [A-Z][A-Za-z_]*, a" games engine --include=*.emp` and check each target lives above $8000.
**Proposal for sigil:** (a) treat a provisional-round measurement that resolved any absolute-width choice against an UNKNOWN address as distorted (feed the next round, never the fixpoint) — the spread fallback already exists for the length case; (b) name the section whose length changed between rounds in the diagnostic instead of the first overlapping pair. Not a repin matter: no frozen row moved.
**Also measured, same parcel:** a NEW `.emp` module is discovered without a `native.rs` registry row — it needs only a `map.toml` `order` row (`[map.order-undeclared]` otherwise). Worth a line in ENGINE_ARCHITECTURE's engine/game contract section when it is next touched.
