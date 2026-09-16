# Regions seam, part two: the emitter, and the flip that is an L

Parcel `parcel/regions-emit`, aeon, 2026-09-16. The successor to
`parcel/regions-loader-golden` (`docs/superpowers/notes/2026-09-16-regions-loader-golden.md`),
step 2 of the **AURORA REGIONS EDITOR** spec
(`empyrean docs/superpowers/specs/2026-09-14-aurora-regions-editor-design.md`).

No emulator, no running app, no `mcp__oracle__*`. Everything below reads source, fixtures and
Python; the build lanes are the ordinary four shapes.

**SCOPE NARROWED MID-PARCEL BY THE CONTROLLER, and it is recorded here rather than absorbed
silently:** the B′ chooser re-key is OUT, and `games/sonic4/data/effects/ojz_effects.emp` is not to
be touched, because a second agent is landing the night-palette fix in that file
(`OJZ_Palette_Night`, :1966) and two agents in one file is a merge nobody wants to referee. The
emitter needs to *read* that file — `effects_library_records()` already parses its
`pub data <Name>: EffectsPreset` lines to validate a region's `preset` — and reads nothing else
from it, so the narrowing is not a blocker. B′ is booked below.

---

## 1. PHASE 0 — the third blocker stands, and the brief UNDERSTATES it

The brief asked me to test its own reading rather than confirm it. The reading is right about the
mechanism and **wrong about the severity, in the direction that matters**: the reels refusal is not
the thing blocking the flip, it is the last thing *refusing* a flip that would otherwise succeed
and silently throw away every Aurora binding in the act.

### 1.1 The refusal reproduces exactly

Sandbox (`RegionSandbox`, the loader-golden parcel's pattern): act 1 in region mode, the golden
document written, every `section_*.meta.json` removed — which is the state `Migrate sections`
leaves. `effects_gen.generate()` raises `SceneShapeError`:

```
/tmp/…/games/sonic4/data/editor/effects/ojz_act1_depth.json: scene 'ojz_act1_depth' carries a
`reels` key but no section binds it with a `sceneRef` sidecar, so it is never
Effects_ResolveParallax's rung 1 and the binding table would have no config pointer to key on.
Reels bind to a SECTION's lowered record, not to a scene in the library — assign the scene to a
section, or drop the key.
```

Confirmed. `render_module`'s `bound` map is built from `load_section_scene_refs`, so in region mode
it is empty, `rung1` is empty, and the rung-1 rule refuses.

### 1.2 THE MEASUREMENT THAT CHANGES THE ANSWER: remove the blocker, and the bake goes green EMPTY

I removed the only named blocker — dropped the `reels` key from `ojz_act1_depth.json` in the
sandbox, nothing else — and re-ran `generate()`. **It succeeded.** Census of the module it produced
against the shipped one:

| emitted population | legacy (shipped) | region mode, reels key removed |
|---|---|---|
| `EditorSceneBinding_*` records | **4** (Sec0, Sec4, Sec7, Sec8) | **0** |
| chooser arms (`if sec == N`) | **14** | **0** |
| `EditorRaster_*` programs | 6 | 6 |
| `EditorCycle_*` / `EditorVariant_*` | 1 / 1 | 1 / 1 |
| reels payload + binding table | 2 | 1 (the table, empty) |
| module size | 541 lines / 33 691 B | 384 lines / 25 712 B |

Unified diff: 11 hunks, **169 lines removed**, 12 added.

**Read what the two middle rows say together.** The raster/cycle/variant *programs* are still
emitted, because they are emitted per authored DOCUMENT and the documents are still there. What
vanished is every *binding*. All six choosers degrade to `comptime var out = hand; return out`, so
`ojz_act1_sec_raster(sec: 5)` returns 0 and `OJZ_Preset_Sec5`'s raster channel becomes null — the
band showcase disappears from the ROM while six raster programs sit in it unreferenced. Same for
the four scene bindings, the shimmer cycle and its variant.

**So the narrow fix the brief floated — "let a region's `sceneRef` establish the rung-1 binding the
way a sidecar's does" — is the one change that must NOT be made alone.** Today the reels rule is a
load-bearing tripwire: it is the only refusal standing between a migrated act 1 and a green build
of a silently de-bound ROM. Relaxing it in isolation converts a loud refusal into a quiet content
loss, which is the exact failure mode this seam's whole design is organised against.

### 1.3 The real price: the binding half of `render_module` is keyed on SECTION INDEX, end to end

Not one rule. Every binding mechanism in the generated module is section-keyed:

* `ActNames.binding_sec(i)` mints `EditorSceneBinding_OJZ_Act1_Sec<i>`.
* Six `pub comptime fn <act>_sec_*(sec: int, …)` choosers, whose arms are `if sec == N`, with an
  `ensure(sec >= 0 && sec < 9)` derived from the act's section count.
* `EditorReelBindings_OJZ_Act1` keys on `extern("EditorSceneBinding_OJZ_Act1_Sec4")` — pointer
  identity of a section-keyed symbol.
* `render_module`'s `bound` / `raster_bound` / `cycle_bound` / `variant_bound` / `patch_bound` /
  `patched_bound` / `reels_bound` are all `{section index: …}`.

Reference count for `ojz_act1_sec_*` and `EditorSceneBinding_OJZ_Act1_Sec*` outside the generated
module itself: **87 sites across 14 files**, including `games/sonic4/data/effects/ojz_effects.emp`
(26), `act_descriptor.emp` (17), and seven gate/witness tools
(`effects_seam_gate`, `parallax_crossing_gate`, `depth_onset_probe`, `sec5_band_witness`,
`row_remap_witness`, `lens_residue_raster_witness`, `boot_override_gate`) plus
`games/sonic4/test/ojz_scroll_test.emp`'s `.lab_index`. There is a reader on aurora's side of the
seam too — `src/core/formats/effects/section-wiring.ts`, named in empyrean `a718ea7c`'s
`docs/AURORA_REGIONS_SCHEMA.md`, whose own amendment describes it keying on `sec_N`. That is a
citation of a ruling, not a claim about their working tree, and it is the hub's to confirm.

**A correct flip therefore needs all three of:** (1) the scene-binding half re-keyed from section
to region row, (2) the reels table re-keyed with it — same `bound` map, so it is one piece, not two
— and (3) **B′**, the five preset-channel choosers, whose 19 call sites are in the file this parcel
is forbidden to touch and whose ruling is `3fc9ffa5`. Without (3), a flip that passes (1) and (2)
still drops the raster/cycle/variant/patch bindings exactly as measured in §1.2.

**VERDICT: L, decisively not S. Stop condition taken — act 1 is NOT flipped**, the price is booked
in `docs/DEFERRED_WORK.md` under `REGIONS-EMIT-BINDINGS`, and emission is proven against a sandbox
act. Booked, not attempted.

### 1.4 What I think the brief got wrong, stated plainly

Three things, in descending order of consequence:

1. **Severity, per §1.2.** "This blocks flipping act 1 into region mode" is true and reads as an
   obstacle. It is better described as a *guard*: the blocker is the only thing currently making the
   flip fail loudly instead of quietly. A brief that sends someone to remove it gets the worst
   available outcome.
2. **"one rule in one generator plus its tests, no `.emp` engine change" would be S.** The rule is
   one `if`; the *keying it depends on* is the whole binding half of a 5 391-line generator plus
   87 downstream sites plus a cross-repo reader. Sizing the rule instead of the keying is how this
   reads as S from outside.
3. **The parcel's headline — "`generate()` emits the table from the document" — cannot be true of
   THIS tree in this parcel**, because no act in this tree is in region mode and flipping one is the
   L above. What lands is the emitter itself, wired into `generate()` behind the mode switch, inert
   on every act here, and proven end to end in a sandbox. That is the same posture
   `check_mode_conflict` shipped in deliberately one parcel ago, and it is stated rather than
   glossed.

Nothing here is a criticism of the brief's method — it explicitly asked to be tested and said it
would rather be corrected than agreed with, and the correction only exists because it named its
own reading as a reading.

---

## 2. PHASE 1 — the id edits, and the one that would have stayed green

Hub ruling 2026-09-16T10:5xZ (empyrean `a718ea7c`, `docs/AURORA_REGIONS_SCHEMA.md`, "A KEY-LESS
ROW'S ID IS ITS PRESET SYMBOL, LOWERCASED — AND AEON'S `night` MOVES"), read at that revision
through git objects, verified an ancestor of empyrean `origin/main`.

**The count of four is right, and I checked it rather than trusting it.** Exactly four sites carry
`night` as an **id**: `tools/fixtures/regions/ojz_act1.regions.json`,
`tools/fixtures/regions/ojz_act1.rows.json`, and `tools/test_regions_doc.py` lines 172 and 551. The
other nine occurrences of the word across those three files are prose — a provenance key, a method
name, docstrings — and are untouched.

**⚠ ONE OF THE FOUR WOULD HAVE SURVIVED THE RULING UN-EDITED.** Line 551 is
`self.refuses(doc, "sec1", "night", "overlap")`, and `refuses` asserts with `assertIn`. `"night"`
is a **substring** of `"ojz_preset_night"`, so that assertion goes on passing while no longer
naming the id an author has to go and find. Both lookups now route through one `NIGHT_ID` constant
and the near-miss is written at the site. This is the `assertIn`-widens-silently family, and it is
the reason a rename should be done by enumerating ids rather than by running the suite and stopping
when it is green.

**Added `test_the_key_less_rows_id_is_its_preset_symbol_lowercased`**, with the expectation
**derived from the row's own `preset` field** rather than typed beside it — typing the id on both
sides passes against a fixture whose preset was renamed and whose id was not, which is the exact
drift the ruling names as its accepted cost. It also pins `name: "Night"`, which the ruling makes a
*condition* of itself.

**Aeon does not implement the sanitisation, deliberately.** The minting is Aurora's migration's,
written once and never re-derived. A second implementation here would be a drift source wearing a
check's clothes; the golden's `_provenance` says so, and says the rule, for a reader who needs it.

**Aurora vendors this golden and their copy needs the same two id edits.** That is the hub's ruling
to relay, not this parcel's to make.

---

## 3. PHASE 2 — the emitter, and the two shape questions the assembler answered

`effects_gen.render_region_table` / `generate_region_table`, wired into this tool's `emit` and
`check` modes behind the mode switch. **Inert in this tree**: no act has a `regions.json`, so
`check` prints *"no region table owed (LEGACY mode)"* and `emit` writes nothing. That is the posture
`check_mode_conflict` shipped in one parcel ago and it is defended on the same grounds — the first
tree to grow a document meets a wired path, not a missing one.

### 3.1 A module, not a fragment — and I did not decide this

The first draft emitted a module-less **fragment**, on the theory that the descriptor would consume
it inside its own module (there is no include in `.emp`, and the constructor's free names cannot
travel — §3.2). **Sigil refused it, and not on the flip, which is what makes it worth recording:
`sigil build` parses every `.emp` in the tree, wherever it sits.** The committed test **fixture**
alone — never emitted, never placed, never imported — took the plain demo build to exit 1 with
`error: file must start with a "module" declaration` and took **50 tests** in
`test_artifact_provenance.py` / `test_provenance_consumers.py` down with it.

**I found it only because I established a control.** My tree ran 4 failed / 2777 passed / **50
errors**; a worktree at the parcel base `277ddcdd` ran 4 failed / **2822 passed / 0 errors**. The
difference is what named the fixture. Running only the regions tests — which were green throughout —
would have shipped it.

So: the emitted table is a **module**, the committed fixture is named `.emp.txt`, and
`test_the_emitted_module_declares_itself` is the gate whose red is that build. **Any future
generator in this tree inherits the constraint**, and it is booked where a generator author will
look.

### 3.2 `Region{...}` literals, not `ojz_region(...)` calls — forced, and it costs something

The descriptor's constructor is not `pub`. Even if it were, `docs/EMP_PITFALLS.md` §2 says a
`comptime fn`'s free names resolve at the **call site**, and `ojz_region`'s body reads a dozen of
that file's own consts (`ACT_W`, `CENTRE_X_MIN`, `REGION_MIN_SPAN`, …). A cross-module call would
need every one imported alongside it — and the pitfall's measured hazard is the **partial** case,
where some names are in scope and the fn neither errors nor works.

**⚠ So a generated table carries none of `ojz_region()`'s per-row ensures** — the minimum span, the
reachable-centre band, the three background rules. That is a real loss, not a technicality: a
generated table is exactly as unchecked as a hand-typed one until something re-checks it. The
consumer owes a **table walk** in the shape `region_first_overlap` / `region_area_sum` already have
in the same file. It is said in the emitted header, where the person wiring it up will be looking,
and booked under `REGIONS-EMIT-BINDINGS`.

### 3.3 What it refuses rather than degrades

* **A row carrying `sceneRef` or `rasterRef`** — six of act 1's ten. Lowering one is §1's L.
  Emitting `parallax: 0` would be the row silently losing its picture, which is the failure this
  whole seam exists to make impossible. The refusal names every offending region and the booking.
* **A row carrying a non-default `bg`** — unreachable today, because `_check_region_bg` refuses a
  named layout first. Written anyway: the day `REGIONS-BG-GOLDEN-GAP` opens, a named layout would
  otherwise be validated, flattened and **dropped at emission**, the same `bgLayoutRef` failure one
  layer further in. The existing tripwire now covers both sites and fails unless they open together.

### 3.4 What it reads rather than assumes

`struct Region`'s field names, from `engine/structs.emp` — the same declaration
`tools/region_table.py` parses for the ROM side, so a field lands in both halves or in neither. The
preset import list is derived from the rows, not from the library: importing the whole library
would work and would hide a row binding a record that vanished.

### 3.5 The ruling's two conditions, both in

The header **points at the golden fixture's `release_shape_only` note** (asserted on the fixture's
real path, so moving the golden fails here rather than leaving a dangling pointer), and every row
gets a `<ACT>_ROW_<ID>` index constant so the DEBUG delta addresses a **named** row — a renamed
region deletes the name the consumer's `ensure` reads, a moved one changes its value.

### 3.6 B′ is out, by the controller's call

Taken back from me mid-parcel, for a reason outside my view: the night-palette parcel was landing in
`ojz_effects.emp` — B′'s 19 call sites' own file — the same night. The emitter only *reads* that
file, through `effects_library_records()`, so this was not a blocker. What I learned while in the
area is banked in the booking rather than lost: the scene chooser is already called from the region
row, so its re-key is mechanical and independent; the five preset-channel choosers are the whole of
the difficulty.

---

## 4. PHASE 3 — re-answering the whole status, which is how two already-stale sentences surfaced

The banner said **NOTHING CONSUMES THE ROWS**. Replaced rather than appended to.

**Re-answering every sentence rather than only the ones I falsified is what found the other two.**

1. `_check_region_bg`'s named-layout refusal stood on **three** reasons and **two were false**.
   *"Nothing lowers this document into a region table"* — my emitter falsified it. *"`rg_bg_span`
   has no engine reader until step 4's clamp"* — **step 4 landed the same day that sentence was
   written** (`d1390f1c`; `Parallax_Step5_Vscroll` reads it through `Region_Current`), so it was
   stale within hours and nothing re-checked it. **Not mine, and a patch scoped to my own change
   would have left it standing.** What survives is the reason that was load-bearing all along and
   was never checked because two easier ones sat in front of it: `ojz_bglib.json` carries `id` and
   `name` and **no height**. The test now asserts both dead sentences absent.
2. `act_descriptor.emp:462` carried the same stale `rg_bg_span` claim, in the file where a reader
   of the ensures meets it. `engine/structs.emp` has said it correctly since step 4; the descriptor
   is where it went stale. Corrected, keeping the fact that actually matters: **both fields have
   readers and no shipped row reaches either**, which is the same shape of trap as no reader at all.

`test_a_migrated_act_does_not_bake_yet_and_the_reason_is_reels` is **unchanged**, and now says why:
the second parcel came and deliberately did not fix it.

---

## 5. Red-first evidence

Every mutation applied on disk with `git diff --stat` and the changed line quoted **before** the red
run; every restore from the **committed** baseline (`git checkout HEAD --`) with
`git status --porcelain` verified empty after. `__pycache__` cleared before every run.

| # | mutation | subject | result |
|---|---|---|---|
| A | drop the `module {module}` line from the header template | `test_the_emitted_module_declares_itself` | **2 failed**, 67 passed |
| B | `region_struct_fields` returns the hard-coded `REGION_EMITTED_FIELDS` | the struct-field read | **1 failed**, 68 passed |
| C | golden `.emp.txt` row 1 `rg_x1: 3399` → `3400` | the committed text golden | **1 failed**, 68 passed |
| D | `_refuse_unlowerable_bindings` returns early | the bindings refusal | **1 failed**, 68 passed |
| E | header's `` `release_shape_only` `` → `shape-scope` | the ruling's pointer condition | **2 failed**, 67 passed |
| F | rows fixture `id` → `ojz_preset_nite` | the derived id assertion | **4 failed**, 55 passed |
| G | document `name: "Night"` → `"Nite"` | the ruling's label condition | **1 failed**, 58 passed |

Restored baseline: **69 passed**, exit 0.

**⚠ METHOD TIGHTENED PARTWAY, AND THE EARLIER CLAIM WAS RE-ESTABLISHED UNDER IT.** Mutation F was
first run through `| tail`, which replaces pytest's exit status with `tail`'s — the thing this
lane's own rule forbids. It was re-run without a pipe, writing to a file and reading `$?`
(`PYTEST_EXIT=1`), and every run in the table above is under the tightened method. No claim rests
on the piped run.

**A gate's red is not always a mutation.** `test_the_emitted_module_declares_itself`'s red is a real
`sigil build` failure (§3.1); mutation A exists to keep it falsifiable after the fact.

---

## 6. What is left open

* **`REGIONS-EMIT-BINDINGS`** — the section→row re-key, B′, and the per-row ensure walk. The L.
* **Nothing has assembled the emitted text.** Sigil has never seen a generated region table.
  ⚠ **TAGGED FOR FOREGROUND FOLLOW-UP:** nothing here wants an emulator, but the first flip wants
  an assembler and a look at the ROM.
* **The generated module's placement.** It declares `const`s only and sits in no section, so it may
  need no `map.toml` entry. **Unverified** — it rides the flip.
* **`REGIONS-BG-GOLDEN-GAP`** — unchanged, with its refusal's reason now correct and its tripwire
  covering the emitter as well as the loader.
* **Aurora's vendored golden** needs the two id edits (§2). The hub's relay.
