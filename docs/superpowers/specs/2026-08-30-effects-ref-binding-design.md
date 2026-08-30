# EFFECTS-W1 item 1 — the `effectsRef` binding, and the retirement of `authored_probe`

*Status: **DESIGN ONLY**, 2026-08-30. Nothing in this document is implemented and nothing in
the parcel that produced it moved a ROM byte. It is the plan the implementing parcel executes
and the evidence base the empyrean CR (`docs/2026-08-30-effectsref-contract-change.md`) rests
on.*

*Every number here was measured on this tree at aeon `e07adb07`, against `s4.lst` (release
shape, built 2026-08-30 03:10) and the sources named at each claim. Cross-repo claims are
verified at committed revisions: empyrean `eff1a9a8` (`origin/main`), sigil `ad0a8243`
(`origin/master`).*

---

## 0. The one-paragraph summary

A section gets an authored raster band by naming a preset document in its
`section_N.meta.json` sidecar. `tools/effects_gen.py` resolves that name to the raster program
it already lowers, and emits **one more zero-byte `pub comptime fn`** — the same
always-emitted chooser the scene arm shipped under ruling Q-c — which the section's `preset()`
call threads into its `raster:` argument. A section with no ref hits the `hand:` fallback and
the generated module's text is byte-identical to what it emits today, so the common case costs
nothing and that fact is CRC-checkable rather than argued. `authored_probe` is deleted in the
same parcel and replaced by a real authored band, because the closure condition already
recorded in `docs/DEFERRED_WORK.md` requires it and because
`tools/test_effects_gen.py::TestPresetConverseControl::test_the_real_repo_SHIPS_preset_documents`
goes red if the presets directory empties.

---

## 1. What is actually in the tree today — re-derived, not transcribed

### 1.1 `effectsRef` is unbuilt

`effectsRef` appears in **four** files in the working tree, all prose, zero code, zero schema
(`.claude/worktrees/*` excluded — peer copies):

| file | what it says |
|---|---|
| `docs/EDITOR_RASTER_PRESETS.md:101` | "not implemented in either repo" |
| `docs/research/2026-08-22-aurora-effects-authoring-assessment.md:583` | names it as the per-section scalar ref |
| `docs/DEFERRED_WORK.md` (three hits) | the booking, the restatement, and the DoD pricing row |
| `docs/superpowers/2026-08-22-aeon-overseer-handoff.md:297,308` | the handoff note |

The controller's four-files claim is **correct**. Command:
`grep -rn "effectsRef" --include="*.md" --include="*.py" --include="*.emp" --include="*.json" --include="*.toml" --include="*.rs" . | grep -v '^\./\.claude/worktrees'`
(the `--include` patterns are quoted — unquoted ones fail silently under zsh and read like a
clean empty result).

On the empyrean side, `effectsRef` is reserved in `docs/AURORA_EFFECTS_SCHEMA.md` §7 and
re-affirmed as reserved in §7.1. It is not in any schema file. **There is no JSON schema for
`section_N.meta.json` at all** — the sidecar is specified in §3 prose;
`contract/schema/` holds exactly three schemas (`aurora-effects-preset`,
`aurora-effects-scene`, `bus-protocol`) and none of them is the sidecar. That is a load-bearing
fact for the CR: the sidecar change is a **prose amendment**, not a schema-file amendment.

### 1.2 The sidecar today

`git ls-files` finds **two** sidecars in the whole tree, for a nine-section act:

```
games/sonic4/data/editor/ojz/act1/section_0.meta.json   {"bgLayoutRef": "...", "paletteRef": null, "sceneRef": "ojz_act1_start"}
games/sonic4/data/editor/ojz/act1/section_4.meta.json   {"bgLayoutRef": null,  "paletteRef": null, "sceneRef": "ojz_act1_depth"}
```

Sections 1, 2, 3, 5, 6, 7, 8 have **no sidecar file**. That is not a gap — it is the specified
state (`load_section_scene_refs`: *"absent = all refs null. NOT an error."*). **The sparse
sidecar is the reason the no-`effectsRef` case can cost nothing: it is already the majority
case, already exercised, and already has a code path.**

`effects_gen.py` reads exactly one key out of a sidecar (`sceneRef`, via `ACT_SCENE_REF_KEY`)
and applies **no unknown-key check to the sidecar** — verified by reading
`load_section_scene_refs` (`tools/effects_gen.py:1123-1148`); the `_check_keys` machinery is
applied to scene and preset *documents*, never to the sidecar. This is the mechanism behind the
older-consumer answer in §6.

### 1.3 The preset arm

- One document ships: `games/sonic4/data/editor/effects/presets/authored_probe.json`, two
  bands.
- `effects_gen.py` lowers it to `EditorRasterSrc_…` + `pub data EditorRaster_OJZ_Act1_authored_probe`
  in `games/sonic4/data/generated/ojz/act1/effects_scenes.emp:136-140`.
- **Nothing binds it.** Its only installer is `Debug_BandDemoHotkey`'s hand-typed `dc.l` table
  (`games/sonic4/test/ojz_scroll_test.emp:1733`), a DEBUG chord.

### 1.4 The binding the section arm already has — and it is the template

`effects_gen.py`'s `render_module` tail emits two `pub comptime fn`s **for every act, always**
(ruling Q-c, design §9):

```
pub comptime fn ojz_act1_sec_scene(sec: int, hand: Label = 0) -> Label {
    ensure(sec >= 0 && sec < 9, "…")
    comptime var out = hand
    if sec == 0 { out = EditorSceneBinding_OJZ_Act1_Sec0 }
    if sec == 4 { out = EditorSceneBinding_OJZ_Act1_Sec4 }
    return out
}
```

called from `games/sonic4/data/levels/ojz/act1/act_descriptor.emp:205` as
`sec_parallax_config: ojz_act1_sec_scene(sec: sec)`. With no editor content the body is
`return hand` and the module's text is unchanged from before the arm existed. **Item 1 is this
pattern, once more, on the raster channel.**

### 1.5 The preset binding today

`Sec.sec_effects` (`$34`) names one `EffectsPreset`. The nine sections bind six instances
(`act_descriptor.emp:224-315`): Sec0/1/2/3 have their own, section 4 has `OJZ_Preset_Depth`,
and **sections 5-8 share `OJZ_Preset_Plain`**. That sharing is the single most consequential
fact in this design and §3.3 is about it.

---

## 2. THE CONTRACT AMBIGUITY — stated before the design, because the design turns on it

**empyrean §7 reserves `effectsRef` as *"a per-section sidecar key alongside `sceneRef` for
total-binding preset assignment"*.**

**A preset document cannot express a total binding.** The preset schema's closed key set is
`{schema, id, name, bands}` (`aurora-effects-preset.schema.json`, empyrean `eff1a9a8`; mirrored
in `tools/effects_gen.py` `PRESET_KEYS`). `EffectsPreset` needs six more channels, and one of
them is not optional:

```
ep_pal            REQUIRED, non-defaulted — preset() takes `pal: Label` with no default
ep_parallax       0 = defer
ep_raster         the one channel a preset document CAN supply
ep_patched        mutually exclusive with ep_raster
ep_cycle          0 illegal in the shipped instances; Pal_Cycle_None is the "off" sentinel
ep_variants[2]    every shipped preset carries Variant_Water_Deep
ep_patch_world_ys [u16; 4]
ep_transition     u16
```

A preset document carries a raster program **and nothing else**. So the reserved name promises
a total binding that its referent structurally cannot deliver. The suite must choose:

- **Narrow the semantics** — `effectsRef` binds the raster channel only, and §7's
  "total-binding" wording is amended; or
- **Grow the document** — the preset document gains `palRef` / `cycles` / `variants` /
  `parallaxRef` / `patchWorldYs` / `transition`, at which point `effectsRef` genuinely replaces
  `sec_effects`. Two of those keys (`variants`, `cycles`) are §7-reserved wave-2 names that
  **DoD item 5 builds** — so this option makes item 1 depend on item 5 and inverts the ratified
  sequence; or
- **Rename** — a new key (`rasterRef`) carries the narrow semantics now, and `effectsRef` stays
  reserved for the total binding it was named for.

**This lane's recommendation: the third.** `rasterRef` is what the mechanism does, the name
does not have to be corrected later, and §7's reservation survives intact for the day the
document is total. **This is a suite naming decision, not aeon's** — it is the CR's one
adjudication question and it is filed as such. See §9 BLOCKED-1.

**Everything below is written against the narrow semantics and is name-agnostic.** The key is
written `<REF>` where the name is the open question; substitute whichever empyrean rules.

---

## 3. The design

### 3.1 The key's shape and where it lives

`<REF>` is a **top-level key in `games/sonic4/data/editor/ojz/act1/section_N.meta.json`**,
alongside `bgLayoutRef` / `paletteRef` / `sceneRef`. Its shape is `sceneRef`'s, deliberately
and in every particular:

| property | rule | why it is this and not something else |
|---|---|---|
| type | string, or JSON `null`, or **absent** | absent == null == "this section keeps its hand-authored raster channel" |
| value space | a preset-document **id**, matching `^[a-z][a-z0-9_]{0,31}$` (`SCENE_ID_RE`) | the id becomes an `.emp` label component |
| numeric index | **REFUSED**, loudly, by the generator | Aurora's parser nulls a non-string value silently (`section-meta.ts:29-30`), so `<REF>: 3` would present to the author as an assignment that did not stick. `_scene_ref` already refuses this for `sceneRef`; `<REF>` reuses that function verbatim |
| unknown id | **REFUSED** at bake, naming the known ids | mirrors `render_module`'s `sceneRef` resolution error |
| written when | Aurora writes the sidecar when **at least one** ref is non-null (empyrean §3, `serializeSectionMeta` returns null when all refs are null) | adding a fourth ref widens "at least one" — a producer rule the CR must state |

**Serialization is `json.dumps(obj, sort_keys=True, indent=2)` plus exactly one trailing `\n`**
— the empyrean §8 canonical-file rule, generalised on 2026-08-26 to *every* JSON file Aurora
writes into aeon's tree, sidecars named explicitly.

### 3.2 How it resolves at build time

Three steps, all inside `tools/effects_gen.py`, mirroring the `sceneRef` path one function at a
time:

1. **`load_section_raster_refs(repo, zone, act) -> {section_index: preset_id}`** — a near-copy
   of `load_section_scene_refs`, reading `<REF>` instead of `sceneRef` through the same
   `_scene_ref` validator, with the **missing / unreadable split intact**: an absent sidecar is
   all-refs-null and is not an error; a sidecar that exists and does not parse **fails the
   bake**. That split is contract §2.2/§3 and it exists because "treat unreadable as all-null"
   is exactly the state that triggers Aurora's destructive cleared-overwrite.

2. **Resolution against the preset library**, in `render_module`, beside the existing scene
   resolution: a `<REF>` naming no document in `presets/` raises `SceneShapeError` listing the
   known ids. Symmetric with the `sceneRef` message, same class, same shape.

3. **Emission of the chooser** — one more always-emitted `pub comptime fn`, appended after
   `sec_scene`:

```
pub comptime fn ojz_act1_sec_raster(sec: int, hand: Label = 0) -> Label {
    ensure(sec >= 0 && sec < 9, "ojz_act1_sec_raster(sec: {sec}): this act has 9 sections, …")
    comptime var out = hand
    if sec == 5 { out = EditorRaster_OJZ_Act1_<id> }
    return out
}
```

with **no bound section at all** the body is `comptime var out = hand; return out` — zero
bytes, zero rows, and the module's byte-image unchanged.

The call site is the section's `preset()` call in `games/sonic4/data/effects/ojz_effects.emp`:

```
pub data OJZ_Preset_Sec5: EffectsPreset = preset(pal: OJZ_Palette,
    raster: ojz_act1_sec_raster(sec: 5, hand: Raster_Program_None),
    cycle: Pal_Cycle_None, variants: [Variant_Water_Deep, 0])
```

**Precedent that this composes**: `ojz_sec()` in `act_descriptor.emp:205` already calls a
generated `pub comptime fn` from inside a struct literal inside a `pub data`
(`sec_parallax_config: ojz_act1_sec_scene(sec: sec)`). This is that shape with a different
callee. It is *precedent*, not a proof for this specific callee — §9 BLOCKED-3 records what
would make it a proof.

**`hand:` must be `Raster_Program_None`, not `0`.** `ep_raster`'s "off" is the parked 3-word
program, never NULL (`preset.emp:61`, ARCH §7.12 — a NULL cannot mean "off" while it also means
"keep"). A chooser defaulting to `0` would reintroduce the exact bug total binding was built to
kill.

### 3.3 Two structural properties this shape gets for free, both worth naming

**(a) A `<REF>` on a patched section is refused at build time, by `preset()`'s own sentence.**
`preset()` asserts `raster == 0 || patched == 0`. Section 0 binds `patched: OJZ_TwoChannel`, so
threading a non-zero chooser result into its `raster:` fires the existing exclusivity ensure
with its existing measured explanation. **No new guard is needed and none should be written** —
duplicating it in the generator would be the contract's own anti-pattern (the generator holds
no bound from the raster tier).

**(b) The chooser is keyed on a section index, and a shared preset has no section index.**
Sections 5-8 share `OJZ_Preset_Plain`. Threading `ojz_act1_sec_raster(sec: 5, …)` into a record
that four sections point at would give all four the band. **So binding a `<REF>` to a section
whose preset is shared requires splitting that preset first** — a one-time 38-byte content edit
(§7), after which every future band on that section is a JSON-only change. This friction is
**not an artifact of this design**: it is `sec_effects` being a per-section pointer to a shared
record, and any binding mechanism inherits it. Stated here rather than discovered later.

### 3.4 The section with no `<REF>` — the common case, and it must cost nothing

Seven of nine sections have no sidecar at all today. For every one of them:

- `load_section_raster_refs` returns no entry (absent file, `continue`);
- `render_module` emits **no `if sec == N` row** in the chooser;
- no `EditorRaster_*` is emitted unless a document exists independently;
- the chooser body is `return hand`, i.e. the section's own `preset()` argument;
- **the generated module's text is byte-identical** to what it emits today for that section.

The converse control that proves this is already built and already inverted once:
`tools/test_effects_gen.py::TestPresetConverseControl` asserts a tree with no preset document
lowers to *nothing at all* — "not an empty program, not a banner, not a blank line". The new
arm extends it: **a tree with no `<REF>` must emit a chooser whose body is exactly
`comptime var out = hand` / `return out`, and no other text change.** That is a text assertion,
checkable without a build, and it is what makes "the common case costs nothing" a measurement
rather than a claim.

### 3.5 What `effects_gen.py` must grow — the full list

| # | change | moves ROM bytes? |
|---|---|---|
| 1 | `ACT_RASTER_REF_KEY = "<REF>"` constant beside `ACT_SCENE_REF_KEY` | no |
| 2 | `load_section_raster_refs()` — the sidecar reader, `_scene_ref` reused | no |
| 3 | `render_module(..., sec_raster_refs=…)` — resolution + the unknown-id refusal | no |
| 4 | the chooser emission (`fn_sec_raster` on `ActNames`) | no, while unbound |
| 5 | a third witness equate, `EditorRaster_<CAP>_Bindings`, for `tools/effects_seam_gate.py` | no — `equ` is zero bytes and link-visible |
| 6 | `tools/test_raster_cycle_table_lint.py` relaxation — see §4 | no |
| 7 | the docs the key list is machine-checked out of (§5) | no |

Note what is **not** on this list: no new bound in the generator, no clamp, no numeric
validation of band values. The generator holds no bound from the raster tier and this arm does
not change that.

---

## 4. THE LINT THAT WOULD DEFEAT THE FEATURE — found, and it must be fixed in the same parcel

`tools/test_raster_cycle_table_lint.py::test_the_editor_rows_are_exactly_the_presets` asserts
that the DEBUG hotkey's `.raster_table` editor rows are **exactly** the set of preset documents
in `presets/`. It is a hard equality in both directions and all four of its arms are proven
red.

It was correct when the DEBUG chord was the *only* installer: a document with no row was ROM
nobody could reach. **Once `<REF>` exists it is a bug**, because it means authoring a preset
still requires a hand-typed `dc.l` in `games/sonic4/test/ojz_scroll_test.emp` plus a
`RASTER_CYCLE_COUNT` bump — i.e. a programmer's edit, which is the exact thing item 1 exists to
remove. Leaving it as-is would ship a feature whose headline claim its own build lane
falsifies.

**The relaxation, and it must stay a real gate:** every preset document must be **reachable by
at least one of** (a) a `.raster_table` row, or (b) a `<REF>` binding in some section sidecar.
Neither alone. A document reachable by neither is still ROM nobody can install, which is the
failure the lint was built for and it must keep failing. The `RASTER_CYCLE_COUNT`-vs-row-count
arm and the every-row-is-imported arm are unaffected and stay exactly as they are.

**This is why item 1 is M and not S.**

---

## 5. Deleting `authored_probe` — every site

The controller's brief named five sites. **The count is right for what it enumerated and short
for the parcel**: there are five *primary* sites and four more that go red or go stale if only
those five are touched. The full list, all verified in this tree at `e07adb07`:

### 5.1 Primary — the five

| # | site | action | bytes |
|---|---|---|---|
| 1 | `games/sonic4/data/editor/effects/presets/authored_probe.json` | delete the file | — |
| 2 | `games/sonic4/data/generated/ojz/act1/effects_scenes.emp:136-140` | re-baked; the two `Src`/`data` lines and (if no document replaces it) the `RASTER_BANNER` vanish | **−78** |
| 3 | `games/sonic4/test/ojz_scroll_test.emp` | four edits: the `use` import (`:116`), the `dc.l` row (`:1733`), `RASTER_CYCLE_COUNT` 2→1 (`:1641`), and the two comment blocks (`:112`, `:1517-1521`) | −4 in DEBUG (one `dc.l`) |
| 4 | `tools/EFFECTS_CONSUMER_CONTRACT.md:272` | the corrected-in-place paragraph and its anti-vacuity note | 0 |
| 5 | `docs/EDITOR_RASTER_PRESETS.md` §D | the entire worked example is `authored_probe` | 0 |

### 5.2 The four the brief did not enumerate, and one of them is a red test

| # | site | why it matters |
|---|---|---|
| 6 | `tools/test_effects_gen.py::TestPresetConverseControl::test_the_real_repo_SHIPS_preset_documents` | **goes RED** if `presets/` empties. It is the anti-vacuity declaration and it has already inverted once. **Consequence: the probe cannot be deleted without a replacement document.** That is not a nuisance — it is the closure condition doing its job |
| 7 | `tools/test_raster_cycle_table_lint.py` | its editor-rows-equal-presets arm goes red the moment the two sides diverge; §4 already rewrites it |
| 8 | `docs/OVERSEER.md:620` | historical record of the chain-182 red run — **prose about a past event; do not rewrite it** |
| 9 | `docs/DEFERRED_WORK.md` (three sites) | the booking, the closure condition, and the DoD row — updated, not deleted |

### 5.3 The sigil side — the DoD's claim, checked

The DoD says *"Deleting the probe REMOVES the cross-seam symbol chain 182 added, so sigil drops
a composition row rather than adding one."* Verified at sigil `ad0a8243` (`origin/master`,
`ls-remote`-confirmed tip). Four sites, and they are not one row:

| sigil file | what is there | action |
|---|---|---|
| `crates/sigil-harness/repin.toml:1058-1067` | the `[[symbol]] name = "EditorRaster_OJZ_Act1_authored_probe"` block, `tests = ["act_descriptor_port"]` | **drop** |
| `crates/sigil-harness/src/pins.rs:362` | the `EDITOR_RASTER_OJZ_ACT1_AUTHORED_PROBE` constant | **drop** |
| `crates/sigil-cli/tests/act_descriptor_port.rs:157` | the symbol's row in the port test's list | **drop** |
| `crates/sigil-harness/golden/provenance.toml:9795` | entry 182's abandonment record | **DO NOT TOUCH — an entry is frozen once it records one** |

**⚠ THE DoD'S CLAIM IS TRUE OF THE DELETION AND FALSE OF THE PARCEL.** The probe's pin is
dropped, yes — but the *replacement* document, once bound through a `preset()` call in
`ojz_effects.emp`, introduces its own cross-seam ref. By exact analogy with
`EditorSceneBinding_OJZ_Act1_Sec4` (pinned as a `[[symbol]]` for precisely this reason,
repin.toml:1044-1055), the new `EditorRaster_OJZ_Act1_<id>` will need a pin of its own — plus
`ojz_effects`'s `[[region]]` byte-gate (`start = "OJZ_TestRaster"`, `end = "section:ojz_effects"`,
repin.toml:656-658) moves when a section's preset is split. **So sigil drops one row and gains
at least one, and re-pins a region.** Pricing item 1 as "sigil drops a row" under-prices the
pairing. Whoever dispatches the sigil half should expect a repin, not a deletion.

*Caveat held at arm's length: which `[[symbol]]`/`[[region]]` rows are needed is a property of
sigil's port scopes, which this lane read at `ad0a8243` but did not run. The port-flip rule is
that cross-seam refs break `*_port` **silently**; sigil's own lane adjudicates the exact row
set.*

### 5.4 What replaces it

The closure condition (`docs/DEFERRED_WORK.md`, "RASTER BANDS — the DEBUG half of the seam
closed") is explicit: *"when the section-binding half lands and a real authored band exists,
`authored_probe.json` is deleted **or replaced** in that same parcel."* Combined with §5.2 item
6, replacement is the only route: **a real authored band, bound to a real section, authored by
Aurora and not by this lane.**

**That band's art direction and its section are OWNER CONTENT DECISIONS, not this design's.**
What this design fixes is the *shape* of the choice:

- **Section 4** already has a sole-owner preset (`OJZ_Preset_Depth`) and needs no split — but
  its raster channel carries the d-15 showcase (`OJZ_DepthVSplit`), which a `<REF>` would
  **evict**, and `preset()`'s exclusivity ensure makes that a hard either/or.
- **Section 5** is the first `OJZ_Preset_Plain` section whose raster channel is
  `Raster_Program_None` — it takes a band without taking one from anything. Cost: the 38-byte
  split (§3.3b, §7).

**Recommendation: section 5.** It evicts nothing, it is one section past the showcase so the
two are comparable by scrolling, and its 38-byte split is the cheapest form the split can take.
Reason recorded so the owner can overturn it on one sentence.

---

## 6. WHAT AN OLDER CONSUMER DOES WHEN IT MEETS THE NEW KEY

Named, not left to be discovered. **There are two older consumers and they behave differently,
and one of them destroys data.**

### 6.1 An older `effects_gen.py` (an aeon revision before this lands)

**It silently ignores the key. No error, no warning, no band.** Mechanism, verified by reading
the function: `load_section_scene_refs` (`tools/effects_gen.py:1123-1148`) reads
`meta.get(ACT_SCENE_REF_KEY)` and applies **no unknown-key check to the sidecar** — `_check_keys`
is applied to scene and preset documents only. The single sidecar-shape assertion is that the
top level is a JSON object.

**Consequence for a bisect or a revert:** a tree that carries a `<REF>` in a sidecar and an
older generator builds **green**, ships, and shows no band. It presents to an author as
"my assignment did nothing", which is the same failure mode §3.1's numeric-index refusal exists
to prevent — arriving here through the version axis instead of the type axis. It is
**acceptable and it must be stated** rather than hardened against: adding an unknown-key
refusal to the sidecar reader would make *every future* Aurora key a build break, which is the
opposite of what a sidecar is for.

### 6.2 An older Aurora (a revision before the `SectionMeta` extension)

**It ERASES the key on the next save.** This is not new behaviour and it is already documented:
`SectionMeta` is a closed interface, its serializer writes what it enumerates
(`section-meta.ts:22`), and empyrean §6 item 1 records that *"a `sceneRef` written by anything
other than a sceneRef-aware Aurora is silently erased on Aurora's next save round-trip"* — the
thirteen-site hazard. `<REF>` inherits it exactly.

**Therefore `<REF>` inherits `sceneRef`'s SEQUENCING PRECONDITION (empyrean §3, ERRATUM 2):
`<REF>` does not land in any sidecar until the `SectionMeta` extension carrying it is on
aurora's master.** `sceneRef` needed aurora `a88db05` for this; `<REF>` needs its successor.
Landing a `<REF>` into a sidecar before then means the author's first save deletes their own
assignment.

### 6.3 A newer consumer meeting an older sidecar

Trivially fine and worth one line so the silence is not read as coverage: absent `<REF>` is
absent, which is `null`, which is "keep the hand-authored channel" — §3.4's common case.

---

## 7. THE BYTE COST OF ONE BOUND PRESET — derived, with the derivation

**All figures measured from `s4.lst` (release shape, 2026-08-30 03:10, this tree at
`e07adb07`). Label spans, not name counts.**

### 7.1 The raster program

```
EditorRaster_OJZ_Act1_authored_probe : $1324C
OJZ_TestRaster                       : $1329A     (the next label)
span = $1329A − $1324C = $4E = 78 bytes = 39 words
```

39 words is exactly `raster_words` for this two-band document: **7 fixed + 2 × 16**. The
per-band 16 comes from `op_size` — 2+6 for the ON record and 2+6 for the derived restore
(`raster_dsl.emp:2898`, the band-cap fixture's own arithmetic).

**Independent corroboration**: sigil's `act_descriptor_port.rs:155` comment, written by the
sigil lane on the landing parcel, records *"the new program is emitted immediately ahead of it
and pushed that whole region **+0x4E**"*. Two sources, different repos, same 78.

**The general form, for N one-colour CRAM bands:** `2 × (7 + 16N)` bytes.

| bands | words | bytes |
|---|---|---|
| 1 | 23 | 46 |
| 2 | 39 | **78** (measured) |
| 3 | 55 | 110 (the cap — 4 bands is 71 words and exceeds `RASTER_BUF_WORDS`) |

*Wider `colours` arrays and `pal_region` arms cost more per band; the table is the one-word-CRAM
case, which is what the shipped documents use.*

### 7.2 The preset split, when the target section shares one

```
OJZ_Preset_Sec0 : $1363A
OJZ_Preset_Sec1 : $13660
span = $26 = 38 bytes
```

38 matches `struct EffectsPreset (size: 38)` (`engine/effects/preset.emp:56`) exactly.

### 7.3 The chooser

**0 bytes.** A `pub comptime fn` emits nothing; the scene arm's `ojz_act1_sec_scene` is the
shipped proof. The witness `equ` is also 0 (`equ` mints a link symbol, not a byte —
`effects_scenes.emp:142-147`).

### 7.4 The item-1 total

| line | bytes |
|---|---|
| delete `authored_probe`'s program | **−78** |
| the replacement authored band, 2 bands | **+78** |
| the `OJZ_Preset_Plain` → `OJZ_Preset_Sec5` split (§5.4 recommendation) | **+38** |
| the chooser + its witness equate | 0 |
| **net, release shape** | **+38** |

A 3-band replacement instead: −78 + 110 + 38 = **+70**. Binding to section 4 instead (no split,
evicts the showcase): −78 + 78 + 0 = **0**.

### 7.5 One published number is wrong, and it is ours

`docs/DEFERRED_WORK.md` states the probe *"costs 30 release bytes that nothing can install"*.
**It costs 78.** Two independent measurements say so (§7.1). Corrected in the booking this
parcel lands; recorded here because 30 is the number a reader would otherwise carry into the
deletion parcel's evidence, and it is exactly the size at which nobody argues.

---

## 8. Divergence from `docs/ENGINE_ARCHITECTURE.md` — and which of us is wrong

**The design does not diverge from ARCH §7.12.** It is §7.12's mechanism used unchanged: one
pointer per section, every channel written on the crossing, the chooser feeding one argument of
the `preset()` call that builds that pointer's target.

**But ARCH §7.12 is stale about `EffectsPreset`, and the doc is wrong, not the code.** §7.12
says the struct is **32 bytes** and lays it out as `$1C ep_patch_world_y` (singular) /
`$1E ep_transition`. Three measurements say otherwise:

1. `engine/effects/preset.emp:56` declares `struct EffectsPreset (size: 38)` with
   `ep_patch_world_ys: [u16; RASTER_MAX_PATCH] @ $1C` and `ep_transition: u16 @ $24`;
2. arithmetic: 4+4+4+4+4+8+8+2 = 38;
3. the listing: `OJZ_Preset_Sec0` → `OJZ_Preset_Sec1` = $26 = 38 (§7.2).

Per this repo's own rule — *"if code diverges from it, one of them is wrong"* — **the code is
right and §7.12's byte table is out of date**, most likely left behind by the Parcel W0 change
that made `ep_patch_world_ys` an inline four-entry array (a ruling §7.12's own prose elsewhere
describes). **This design does not fix it: it is outside item 1's scope and fixing an
architecture doc inside a binding parcel is how a diff stops being reviewable.** Booked as a
rider in `docs/DEFERRED_WORK.md` in this same change.

---

## 9. BLOCKED — the ambiguities this design could not resolve, and what would resolve them

*Recorded as items rather than papered over. A design parcel's blocked items are its output.*

### BLOCKED-1 — the key's name and semantics. **Empyrean's call, and it is the CR.**

§7 reserves `effectsRef` for *total-binding* preset assignment; the preset document can only
express a raster program (§2). One of three must happen and aeon cannot choose unilaterally,
because the name is reserved in the suite contract:

- amend §7 to narrow `effectsRef` to the raster channel; or
- adopt `rasterRef` for the narrow binding and keep `effectsRef` reserved (**this lane's
  recommendation**); or
- grow the preset document to total, which makes item 1 depend on item 5 and inverts the
  ratified DoD sequence.

**What resolves it:** the empyrean CR in `docs/2026-08-30-effectsref-contract-change.md`, filed
and adjudicated. **The implementation parcel cannot start until it is** — the key's name is in
the sidecar, the generator, the tests and Aurora's writer.

### BLOCKED-2 — which section, and what the replacement band looks like. **Owner's call.**

§5.4 frames the choice (section 4 = no split, evicts the d-15 showcase; section 5 = 38-byte
split, evicts nothing) and recommends section 5. The *band itself* is authored content —
"a content decision with a picture attached", the `BAND-FIRST-CONSUMER` class the earlier lane
already reserved for the owner. This lane does not pick colours.

**What resolves it:** one sentence from the owner, or an Aurora-authored document arriving with
its section named.

### BLOCKED-3 — one `.emp` composition step is precedent-backed but unproven

`raster: ojz_act1_sec_raster(sec: 5, hand: Raster_Program_None)` as an argument to `preset()`
inside a `pub data` initialiser is the same shape as the shipped
`sec_parallax_config: ojz_act1_sec_scene(sec: sec)` inside `ojz_sec()`'s `Sec{}` literal — but
that is a *struct field*, and this is a *comptime fn argument that a subsequent `ensure` reads*
(`preset()`'s `raster == 0 || patched == 0`). Whether sigil's comptime evaluator admits a
chooser's `Label` result on the left of that comparison at that point is **not established by
the precedent**, and this parcel wrote no `.emp` to find out.

**What resolves it:** ten minutes in the implementation parcel — a throwaway `preset()` call
taking a chooser result, built with `FAST=1 DEBUG=1 ./build.sh`. **It is Step 2's first act**
(§10) precisely so it fails before anything is built on it. If it does fail, the fallback is
that the generator emits a whole `EffectsPreset` record and the descriptor's `sec_effects`
takes a chooser — which costs 38 bytes per bound section unconditionally and needs the base
preset's channels named in the sidecar, i.e. a materially larger CR. **Flagged now so the CR's
author knows a fallback exists that would change it.**

### NOT BLOCKED, recorded so it is not re-litigated

- **Runtime confirmation that a bound band renders.** Requires the emulator; no MCP call was
  made or may be made from this lane. **TAGGED for the controller's foreground follow-up**, and
  it is DoD item 2's job anyway (`tools/band_witness.py`, sequenced *ahead* of item 1 as a
  spike for exactly this reason).

---

## 10. The implementation plan — each step independently landable

**Bytes and sigil pairing are stated per step. Steps 1-3 move no ROM bytes and pair with
nothing; the pairing and the bytes all arrive in steps 4-6.**

| # | step | ROM bytes | pairs with sigil | blocked by |
|---|---|---|---|---|
| **0** | *(this parcel)* design + CR + booking | **none** | no | — |
| **1** | **File the CR; get BLOCKED-1 adjudicated.** empyrean amends §3 (the sidecar key) and §7 (the reservation). No aeon code. | **none** | no | — |
| **2** | **Prove BLOCKED-3.** A throwaway `preset()` taking a chooser-shaped `pub comptime fn` result, built and then reverted. Reports pass/fail; lands nothing. | **none** | no | — |
| **3** | **Generator + tests, arm only, no content.** `ACT_RASTER_REF_KEY`, `load_section_raster_refs`, resolution, chooser emission, the third witness equate, the `TestPresetConverseControl` extension asserting the unbound text is unchanged. **No sidecar carries the key yet**, so the generated module is byte-identical and the four-CRC check proves it. | **none** — and it is *checkable*, exactly as the preset arm's own zero-byte landing was | no | 1, 2 |
| **4** | **Relax `test_raster_cycle_table_lint.py`** to "reachable by a cycle row OR a `<REF>`", keeping the other arms and re-proving all of them red. | **none** | no | 3 |
| **5** | **Split `OJZ_Preset_Plain` → `OJZ_Preset_Sec5`** and thread the chooser into its `raster:`. Still no `<REF>` in any sidecar, so the chooser still returns `hand` and the *only* delta is the split. | **+38** | **YES** — new symbol, and `ojz_effects`'s `[[region]]` byte-gate moves | 3, BLOCKED-2 |
| **6** | **Land the authored band + its `<REF>`, delete `authored_probe`** — all nine sites of §5, both repos. | **−78 +78** (2-band replacement); **net 0** for this step, **+38** cumulative | **YES** — drops the probe's `[[symbol]]`, adds the replacement's, repins the region | 4, 5, aurora's `SectionMeta` extension on their master (§6.2) |
| **7** | **Docs**: `EDITOR_RASTER_PRESETS.md` §C's "honest limit" is *no longer true* for a bound section — rewrite §C and §D against the replacement document. `EFFECTS_CONSUMER_CONTRACT.md` grows a §2.2 row for `<REF>`. | **none** | no | 6 |

**Step 5 is the byte-moving step that can land alone**, which is why it is separated from 6: it
proves the split and the region repin in isolation, so if step 6's content decision slips, the
mechanism is already in and gated.

**Step 3's zero-byte claim is the one to verify rather than assert**, and the arm it copies
already showed how: the preset arm's own landing was proven zero-byte by CRC because
`render_module` appends *nothing at all* — not a banner, not a blank line — when there is no
content. The chooser must hold to the same standard: with no `<REF>` anywhere, the emitted text
gains the chooser and **nothing else**, and `s4.bin`/`s4.debug.bin` are byte-identical before
and after.

---

## 11. Where this is booked

`docs/DEFERRED_WORK.md`, EFFECTS-W1 item 1's row and the "RASTER BANDS ARE AUTHORABLE AND
UNBINDABLE" follow-up. The CR text is `docs/2026-08-30-effectsref-contract-change.md`.
