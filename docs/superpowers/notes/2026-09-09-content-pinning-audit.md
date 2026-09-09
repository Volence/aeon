# Content-pinning checks — an audit (2026-09-09)

**Read-and-report parcel. No test was changed and nothing was fixed.** Branch
`audit/content-pinning-checks`, worktree
`/home/volence/sonic_hacks/aeon/.claude/worktrees/agent-aa099f8aae1f97060`, base
`11647b64`. **No build was run** — every claim below is derived from source, and the
places where that matters are marked.

---

## THE CRITERION, AS THE OWNER STATED IT

> **a check may require that authored content is CORRECT; it may not require that
> particular content EXISTS, unless something real breaks without it.**

He reached it tonight after trying to turn off a decorative moving waterline in one level
section — an ordinary content decision — and having the build refuse:

> "This is actually silly how tough we make the tests that turning off this makes the whole
> build fail. I feel like we need to start having a 'once this project is considered
> complete, ease up on the tests' or something for things that were specifically created
> just to test"

> "so much of our dev time goes into working around tests I feel"

**The discriminator that fell out of the sweep, and it is worth stating before the table,
because it sorts almost the whole population mechanically:**

| implication direction | what it does when content is REMOVED | verdict |
|---|---|---|
| **authored ⇒ declared** ("you authored a curve, so declare the capability") | nothing — the antecedent is gone | **safe** |
| **declared ⇒ authored** ("you declare the capability, so some scene must author it") | **fires** | **content-pinning** |

Every comptime hit in this audit is the second direction. Every safe sibling is the first.
The repo already writes the safe direction deliberately and says so — `scene_registry.emp`'s
subset arm is one-sided **on purpose** and its banner explains why. The defect is that three
separate arms were later added that reinstate the other side.

---

## WHAT WAS SWEPT, AND WHAT THE SWEEP CANNOT SEE

**Populations, with units:**

| surface | population |
|---|---|
| `.emp` comptime `ensure(...)` | **1,398 sites** in **134 files** (of 201 `.emp` files); 684 sites engine-side, 628 game-side non-poison, 81 in `games/sonic4/test/poison/` |
| pytest suite | **2,217 test functions** in **103 `tools/test_*.py` files** — build-fatal, pre-sigil lane |
| non-test tool scripts | **157 `tools/*.py`**; `build.sh` invokes **24** of them build-fatally, of which **21 are checking tools** (the other three are `suite_paths.py`, `gen_compression_vectors.py`, `level_staleness.py`) |

**Method:** enumerate by what the assertion *does*, never by name. Three mechanism shapes —
(a) existence of a named symbol/scene/fixture, (b) a population guard asserting a count > 0
of authored things, (c) a specific authored value that is a design choice rather than a
structural fact — plus the `.emp` comptime equivalent of each. Candidates were then **read in
context**; this repo comments heavily and the comment usually states the intent, which is what
separates a healthy vacuity guard from an over-reach.

**A population guard is not automatically a defect, and several here are fine.** "If I cannot
see my subject at all, fail" is healthy — this repo has spent real effort on gates that passed
vacuously. The defect is **over-reach: hard-coding WHERE or WHICH content must exist.**

**What this enumeration cannot see:**

- **Whether any given hit actually fires.** Nothing here was built. The blast-radius chain
  below is a *derivation from source*, not a measured build failure.
- **`ensure`s produced by a comptime `fn` from data** rather than written literally — a
  generator that emits an `ensure` per document (`tools/effects_gen.py` does exactly this) is
  visible only through the generator, not through a grep of the checked-in `.emp`.
- **Checks that live in prose obligations** — a ritual a merge is supposed to run
  (`tools/effects_gates.py`) is not build-fatal and was not swept as one.
- **Aurora-side and sigil-side checks.** Cross-repo; out of scope and unmeasurable from here.
- **Anything abandoned before a commit** — an author who gave up rather than fight a gate
  leaves no artifact at all.

---

## THE FLAGSHIP: WHAT ACTUALLY REFUSES "TURN OFF THE WATERLINE"

The change is deleting one argument in one file:
`games/sonic4/data/effects/ojz_scenes.emp:327`, the
`rowRemap: SceneRemap.Ladder(RowRemapLadder_Waterline16, 101, 4)` on `Scene_OJZ_Underwater`'s
layer 1.

**Derived, not measured** — **five** independent build-fatal refusals, in three different
enforcement mechanisms. Four of the five fire **before the ROM is even linked**:

| # | where | mechanism | what it says |
|---|---|---|---|
| 1 | `games/sonic4/data/effects/scene_registry.emp:488` | comptime `ensure` | `(SceneRegistry_CapsFolded & CAP_ROW_REMAP) != 0` — "NO shipped scene folds CAP_ROW_REMAP any more … this is a **THREE-file retreat** and not a scene-local edit" |
| 2 | `games/sonic4/data/effects/scene_registry.emp:567` | comptime `ensure` | `SceneRegistry_CapsFolded == SceneRegistry_CapsExpected` ($08DE) — the two-sided equality pin catches the same removal a second time |
| 3 | `tools/test_lab_index_lint.py:502` | pytest, **pre-build lane** | `assert len(live) == 1` — "expected exactly ONE authored scene carrying a live `rowRemap:`" |
| 4 | `tools/test_lab_index_lint.py:530` | pytest, **pre-build lane** | `assert len(rows) == 1` — "`.lab_index` holds N `LAB_KIND_WLINE` row(s), expected exactly one" |
| 5 | `tools/row_remap_gate.py:621` | post-sigil gate, `exit 1` | `if not tails:` — "DECLARES CAP_ROW_REMAP but NO emitted band carries a non-NULL ladder pointer" |

And the retreat the first message *prescribes* spans **seven source files**: `ojz_scenes.emp`
(the key), `games/sonic4/config/game.emp` (clear $0800), `engine/level/parallax.emp`
(`BAND_REMAP_N` → 0), `engine/ram.emp` (`BAND_REMAP_BYTES` → 0), `scene_registry.emp` (two arms
plus re-deriving `SceneRegistry_CapsExpected`, plus dropping the 272-byte ladder emission),
`games/sonic4/test/ojz_scroll_test.emp` (the `.lab_index` WLINE row and its `.scene_table`
join), and `tools/test_lab_index_lint.py` (the two `== 1` pins).

**Item 4 is the sharpest instance of the owner's sentence.** `LAB_KIND_WLINE` is a **debug lab
row** — a fixture built so a human could see the effect, which the row's own comment says
outright ("WHY THIS ROW EXISTS AT ALL … This row is the picture"). A pytest that runs
build-fatally asserts that this debug fixture must remain authored, forever. That is literally
"a demo feature must remain authored, in a specific section, forever."

---

## THE HIT TABLE

### A. Comptime `ensure` — the `declared ⇒ authored` family

| # | site | condition | class | note |
|---|---|---|---|---|
| A1 | `games/sonic4/data/effects/scene_registry.emp:488` | `(SceneRegistry_CapsFolded & CAP_ROW_REMAP) != 0` | **PINS-CONTENT** | Nothing breaks. The cost it names is *waste* — 272 ROM bytes, 128 B of `Parallax_State`, 26 cycles/band/frame — not a fault. Waste is a good thing to warn about and a bad thing to refuse on. |
| A2 | `games/sonic4/data/effects/scene_registry.emp:595` | `(SceneRegistry_CapsFolded & CAP_FACTOR_CURVE) != 0` | **PINS-CONTENT** | Same shape, same file, for the perspective floor's curve. Its own banner already admits the "THREE-file retreat" text is **stale** — `BAND_CURVE_N` and `BAND_CURVE_BYTES` are already 1 and 10 on master, so the retreat it prescribes is partly a no-op. |
| A3 | `games/sonic4/data/effects/scene_registry.emp:610` | `(SceneRegistry_CapsFolded & CAP_BAND_DRIFT) != 0` | **PINS-CONTENT** | Same shape, for `Scene_OJZ_Default`'s `drift: SceneDrift.Rate(-32)`. |
| A4 | `games/sonic4/data/effects/scene_registry.emp:567` | `SceneRegistry_CapsFolded == SceneRegistry_CapsExpected` | **PINS-CONTENT** (stronger) | An equality pin over the whole fold. It re-fires on *every* A1-A3 case and on any capability a scene stops raising. Its banner defends itself well — "a pin nobody has to touch is a pin nobody is checking" — and that argument is about a capability *landing*, which is the safe direction. It is doing double duty as a content-existence pin in the unsafe one. |
| A5 | `games/sonic4/data/effects/scene_registry.emp:578` | `(SceneRegistry_CapsFolded & CAP_MULTI_DEFORM_TABLE) == 0` | **PINS-CONTENT BY DESIGN — out of scope** | This forbids *adopting* `deform: Own(..)` until the owner approves. It refuses a content decision on purpose and says so ("PARK-1, owner-gated"). Listed so it is not mistaken for a defect; it is a policy the owner set. |

### B. Comptime `ensure` — the safe siblings, listed so the contrast is on the record

| site | condition | class |
|---|---|---|
| `scene_registry.emp:613` | `(SceneRegistry_CapsFolded & ~Game.SCANLINE_CAPS) == 0` — *folded ⊆ declared* | **REAL-INVARIANT.** A declared **subset** would omit machinery a scene still demands — the P2 lowering drops the tail and the runtime reads a record shape that is not there. Deliberately one-sided; its banner explains the direction as the safety property. |
| `games/sonic4/data/generated/ojz/act1/effects_scenes.emp:162` | same subset test, generated | **REAL-INVARIANT**, same reason. |
| `scene_registry.emp:459/461, 468/470, 476/478, 482/484` (4 pairs) | `(caps & CAP_X) == 0 \|\| BAND_X_N == 1` and its converse | **REAL-INVARIANT.** These pin the *declaration against the engine record shape*, not against content. The message for the row-remap pair states the fault precisely: "the gated per-band mark would read the record base as a ROM pointer and index the HScroll buffer through it." That is memory corruption, not waste. |
| `ojz_effects.emp:1252`, `effects_scenes.emp:232/265` and the generator at `tools/effects_gen.py:2991` | `(Game.SCANLINE_CAPS & CAP_DENSE_TIER) != 0` beside each authored ramp | **REAL-INVARIANT / safe direction.** *authored ⇒ declared*. Removing the content removes the `ensure` with it. This is the shape A1-A4 should have. |
| `scene_registry.emp:660` | `SceneRegistry_RebaseTagged > 0` | **HEALTHY POPULATION GUARD.** "the §6 declarative gate is vacuous" if it classified nothing across all 20 scenes. This is the "cannot see the subject at all" shape the criterion permits. Its only weakness is that comptime has no *unmeasurable* channel — see §Exit codes. |

**Why the `.emp` population is so small, stated so the smallness is a result and not a gap.**
Of 1,398 `ensure` sites, the operator census is 921 `==`, 204 `<=`, 145 `>=`, 131 `<`, 101 `>`,
79 `!=`. The `==` mass is overwhelmingly **drift tripwires** — 69 engine-side sites of the form
`ensure(SOME_CONST == <literal>)` guarding a value inlined in two places (`scene_dsl.emp:77-126`
is a block of them). The `<=`/`>=`/`<` mass is **range checks** bounding an authored value into
what the hardware or the format allows, which is the correctness direction and cannot refuse a
removal. **Content-existence pinning in `.emp` is confined to the four `SceneRegistry_CapsFolded`
arms above.** That is a genuinely good result for the comptime layer, and it makes the Python
layer, not the language, where this problem lives.

**AND THE DSL CONSTRUCTORS ARE ALREADY WRITTEN THE RIGHT WAY — this is the model to copy.**
Every guard in `layer()` / `scene()` / `band()` is variant-gated:
`ensure(is_curve == 0 || …)`, `ensure(remap_none == 1 || …)`, `ensure(drift_none == 1 || …)`,
`ensure(is_own == 0 || …)`. Each reads *"if you authored this, it must be valid"* — the
`authored ⇒ correct` direction, which **cannot fire on a removal**. `scene_dsl.emp:2009`, the
"a `rowRemap:` layer needs something to vary" guard, is one of these: **it plays no part in
tonight's refusal**, because deleting the `rowRemap:` deletes its antecedent. Worth saying
plainly, since `row_remap_gate.py` cited that guard as its authority for a stricter rule it does
not support — the defect ruled on 2026-09-05 in
`docs/witness/rowremap-gate-vs-guard-2026-09-05.md`, whose lesson was **"a gate that quotes an
authority should be tested against that authority."**

**The engine/game wall holds.** Exactly one `ensure` in all of `engine/` names anything
waterline-shaped — `engine/level/bg_anim.emp:407`, and it is a RAM-region size pin
(`Waterline_Art_State_End - Waterline_Art_Buffer == WATERLINE_DST_BYTES`), a real invariant.
**No engine-side `ensure` names a Sonic 4 scene, and no `games/demo/` `ensure` names Sonic 4
content at all.** That is a clean result and worth keeping clean.

### C. Python — pytest, build-fatal pre-build lane

**Funnel:** ~1,353 raw candidate assertion sites (`assertIn` 797, `assertNotIn` 131, bare
`assertTrue` 131, `assertEqual(len(` 103, `raise AssertionError` 97, `pytest.fail` 36,
`assertIsNotNone` 31, `assertGreater(len` 12, `len(...) >/>=` 15 — heavily overlapping), all
103 files read in context → **10 PINS-CONTENT and 12 AMBIGUOUS, in 9 files. About 94 of 103
files are clean.** Nearly every raw candidate was an `assertIn` against a *derived* allow-set,
not a literal-name pin — reading eliminated them.

| # | site | assertion | class | note |
|---|---|---|---|---|
| C1 | `tools/test_lab_index_lint.py:530` | `assert len(rows) == 1` (`LAB_KIND_WLINE`) | **PINS-CONTENT** | Requires a debug-lab fixture row to exist forever. The `> 1` half is a real invariant (two rows drive one System slot); the `< 1` half is the over-reach. |
| C2 | `tools/test_lab_index_lint.py:502` | `assert len(live) == 1` (scenes with a live `rowRemap:`) | **PINS-CONTENT** | Same split: `> 1` is real ("this arm cannot say which scene the row should name"); `== 0` is a content decision being refused. |
| C3 | `tools/test_effects_seam_gate.py:783` | `self.assertEqual(sorted(bound), [5, 6])` | **PINS-CONTENT** | **Self-labelled.** The test's own docstring opens "*The content assertion*, kept separate from the invariant above so a content change cannot look like a mechanism failure." It knows it is a content pin and is build-fatal anyway. Sections 5 **and** 6 must each carry a bound editor raster, forever. |
| C4 | `tools/test_map_dplc_binding.py:303,307` | `assert len(maps) == 7` / `assert len(dplcs) == 6` | **PINS-CONTENT** | **The single best illustration in the audit**, because the healthy and the over-reaching guard sit in one function four lines apart: `assert len(emp_sources()) > 100` ("the enumeration is broken") is exactly right; `== 7` refuses adding or retiring any mapped object. |
| C5 | `tools/test_anchor_sweep_band.py:993` | `assertTrue(authored_sweeps(), "no anchor_sweep(...) is authored anywhere …")` | **PINS-CONTENT** | n=1 population held build-fatally. Message: "if it was deliberately removed, the capability bit … should come out in the same commit." |
| C6 | `tools/test_anchor_sweep_band.py:1095` | `assertGreater(judged, 0, …)` | **PINS-CONTENT** | Requires an authored sweep specifically on the act's **spawn section** — relocating it elsewhere fails the build. This is the "in a *specific section*" half of the owner's sentence. |
| C7 | `tools/test_anchor_sweep_band.py:1278` | `assertTrue(gen, "the generated arm's live population is EMPTY again …")` | **PINS-CONTENT** | Pins one editor document (`ojz_sec5_showcase.json`) and its sidecar binding. |
| C8 | `tools/test_effects_gen.py:3355-3413` | `self.fail(f"{path} does not exist")` for `ojz_sec3_shimmer.json`; likewise for `OJZ_ShimmerCycle` / `Variant_Water_Deep` | **PINS-CONTENT** | One named decorative effect and its hand twin must exist permanently so a parity test has a subject. |
| C9 | `tools/test_perspective_floor.py:229, 621` | `assert fn, "perspective_floor_layers() is gone …"`; `assert scene, "Scene_Perspective_Floor is gone …"` | **PINS-CONTENT** | Two hard existence pins on a named decorative feature and its scene. |
| C10 | `tools/test_lab_index_lint.py:538-578` | the WLINE row's sub-index equals the remapping scene's registry index, and `.scene_table[want]` is that scene's config | **REAL-INVARIANT** | The correctness half, and it is excellent — a drifted sub-index silently installs a scene with no ladder and the reviewer sees nothing with every gate green. **It should survive any fix to C1/C2 untouched.** |

**Twelve AMBIGUOUS**, not tabled individually. The recurring pattern, worth more than the list:
`tools/test_vsplit_consumer_lint.py:406-422`, `test_effects_seam_gate.py:726/758/835/927`,
`test_reels_gate.py:63` (`REEL_BAND_COUNT == 5`), `test_sfx_transcode.py:561` (9 hard-coded SFX
ids), `test_demo_specialization_witness.py:151`, `test_anim_frame_bound.py:96` (4 hard-coded
object aliases), `test_effects_budget_check.py:217`. **What would settle most of them is one
question:** does the mechanism under test have a *synthetic fixture* that proves it, or is real
shipped content its only subject? Where a fixture exists (`test_anchor_sweep_band.py` has four),
the live-population guard is redundant and can become a warning; where it does not, the guard is
load-bearing and should stay.

### D. Python — non-test gates

**Scope:** 153 scripts (155 minus the two already classified). **23 build-fatal scripts read**
(9 cover-to-cover, 14 at depth); the other 130 pattern-swept only. Raw candidates: ~40
population-guard sites, 3 content-name lookups, 1 authored-value check. **Almost every
population guard read as healthy** — a glob- or walk-derived set with a "if I see nothing, my
subject is gone" refusal.

| # | site | condition | class | build-fatal | note |
|---|---|---|---|---|---|
| D1 | `tools/row_remap_gate.py:621` | `if not tails:` → "the capability has no subject" | **PINS-CONTENT** | **yes** | The `declared ⇒ authored` direction again, one layer out. |
| D2 | `tools/row_remap_gate.py:727` (via `REMAP_VISIBLE_MIN_PX = 8`) | `px < floor_px` → `problems` → `exit 1` | **PINS-CONTENT** | **yes** | **A build-fatal aesthetic threshold.** The constant's own comment says its provenance is "an OBSERVATION … a perceptual bar can only be calibrated against someone looking at the screen." A deliberately subtle 6-px shimmer is refused. The perceptual judgement belongs to the person looking at the screen — who is the person the build is refusing. |
| D3 | `tools/band_drift_golden.py:72` + `:169` | `SCENE_NAME = "Scene_OJZ_Default"` hard-coded, then `if not any(r is not None for r in rates)` | **PINS-CONTENT** | **yes** | Stronger than a population guard: it names **one specific scene** and requires it to author a non-`None` drift rate. Turning off decorative band drift on that background — the same category of decision as tonight's — fails the canonical build. Its own message concedes the remedy is "this file and its build.sh call go with it." |
| D4 | `tools/editor_palette_golden.py:262` | `if not authored: return 2` — "no preset document … carries an authored `cycles` or `variants`" | **AMBIGUOUS → PINS-CONTENT** | **yes** | The guard's *shape* is the healthy generic kind — it walks every preset document. But the population in this tree is **n=1** (`ojz_sec3_shimmer.json`, confirmed by grep). So turning off that one section's palette shimmer empties the set and fails the build. **The healthy-in-theory / pinning-in-practice trap.** Settled by: whether a second `cycles`/`variants` document is expected, or whether the contract is "prove the pipeline only once something uses it" — in which case zero should not be fatal. |
| D5 | `tools/row_remap_gate.py:498` | `visibility_arm_self_test` raises `Unmeasurable` — "no remapped band to mutate" | **PINS-CONTENT (via exit collapse)** | **yes** | Correct as a *refusal*; fatal only because of §Exit codes. |
| D6 | `tools/effects_seam_gate.py:506` | `if not raster_calls:` — "**Bind one section's preset through it**" | **AMBIGUOUS** | **yes** | Intent is reachability; wording is an instruction to author content. **What would settle it:** whether the `--lst` arm's `pub equ` witnesses already prove the seam is reached — a different and stronger fact than "some section binds a raster." If they do, this is over-reach. |
| D7 | `tools/base_swap_witness.py:153` | `AUTHORED_SYM = "EditorRaster_OJZ_Act1_ojz_sec6_baseswap"` | **PINS-CONTENT (in shape)** | **no** | Hard-codes that section 6 carries one specific authored raster. Not called from `build.sh` or `effects_gates.py`, so it cannot block a build today — only its own manual run. Low severity, listed for completeness. |

**Judged and found healthy** (so the contrast is on the record): `art_rom_report.py` ("no act
art pools found" — generic glob, not a named act), `verify_level_bin.py` (orphans WARN, not
FAIL), `collision_consistency.py` ("REFUSES to pass on an empty population" — its build.sh
comment names this as the healthy shape), `s4budget.py` ("no `[[region]]`" — a malformed
placement contract, not content), `effects_budget_check.py` (`adopters > 0` **skips** pricing
rather than failing), `effects_gen.py check` (a re-bake drift gate — remove content, re-bake,
it passes), `gen_compression_vectors.py` and `emp_expect_fail.py` (synthetic/poison fixtures
only).

### E. Friction that is not over-reach, recorded so it is not confused with it

| site | what | why it is not the defect |
|---|---|---|
| `games/sonic4/test/scene_equiv_proof.emp` (~50 `ensure`s) | names every scene and band index literally (`EQ_OJZ_Windy_b0`, …) | The *assertion* is a correctness claim (two lowering spellings agree). Deleting a scene produces an **unresolved-name compile error**, not a false assertion. Real maintenance tax; not a check asserting the wrong thing. |
| `act_descriptor.emp:363` | `ensure(GRID_W * GRID_H == 9)` | Pins a literal `[Sec; 9]` array length. Real invariant *as written*; the better shape is `[Sec; GRID_W*GRID_H]`, which would delete the pin. |
| `act_descriptor.emp:132` ↔ `scene_registry.emp:658` | `SCENE_ACT_SPAN_Y == (GRID_H << SECTION_SIZE_SHIFT)` | A two-species mirror pin — a number written twice must agree. Resizing the act touches two files; that is the documented cost of the mirror, taken to avoid an import cycle. |
| `ojz_effects.emp:2232` | `ensure(REEL_COLS_PER_BAND == 4, …)` | **The contrast case, and worth reading beside D2 and A1.** It has the exact shape of a content pin — a literal equality on an authored-looking design number — and it is a **REAL-INVARIANT**, because `OJZ_Reels_Fill`'s column→band map is a hard-coded `lsr.b #2`. Change the constant without the shift and the loop addresses the wrong band. **This is what "say what breaks" looks like when there is an answer**; A1-A4 and D2 are the same shape with no such answer. |
| `games/sonic4/test/scene_equiv_proof.emp:749-769`, `ojz_effects.emp:392/2017` | `.len == 256`, `.len == 6`, `.len == 25` | Internal consistency of **hand-written twin fixtures** against the generator they check (a padding run is computed against a 25-word body). Gate fixtures, not shipped content. |

---

## THE COUNT, WITH ITS UNIT

| classification | count | unit |
|---|---|---|
| **PINS-CONTENT** | **19** | **check sites** — 4 comptime `ensure` (A1-A4) + 10 pytest assertion sites (C1-C9; C9 is two sites in one file) + 5 gate sites (D1, D2, D3, D5, D7) |
| **AMBIGUOUS** | **14** | check sites — 12 in the pytest suite, 2 in the gates (D4, D6) |
| **REAL-INVARIANT** (in the swept candidate set — checks that *look* like content pins and are not) | **~20** | check sites, incl. the 4 `BAND_*_N` pairs, the two subset arms, the `CAP_DENSE_TIER` family, C10, and `REEL_COLS_PER_BAND` |
| **PINS-CONTENT BY DESIGN** (owner-set park, out of scope) | **1** | check site (A5) |

**No site is counted twice: D4 is AMBIGUOUS only, and is not in the 19.**

**Files affected: 9 pytest files, 3 gate scripts, 1 `.emp` file.** Of the **19** PINS-CONTENT
sites, **18 are build-fatal today**; the single exception is **D7**, a standalone witness that
`build.sh` does not call. **Against populations of 1,398 `ensure` sites, 2,217 test functions and
157 tool scripts, this is a small and highly concentrated defect** — which is the good news, and
the reason a fix is tractable rather than a rewrite.

---

## THE EXIT-CODE COLLAPSE — one line that promotes refusals into failures

**Eleven of the twenty-one build-fatal gates carry a substantive `UNMEASURABLE` / exit-2
concept** (`dplc_straddle` 72 sites, `bganim_room` 49, `row_remap_gate` 36, `reels_gate` 36,
`dma_defer_headroom` 32, `editor_palette_golden` 28, `plane_base_swap_gate` 26,
`band_drift_golden` 21, `waterline_art_gate` 15, `anim_frame_bound` 14,
`plane_role_swap_gate` 12 — count is *sites per file*, files are the unit of the eleven).

They draw the distinction carefully: **exit 1 = the bytes are wrong; exit 2 = I cannot measure
this.** `build.sh` erases it. Every one is invoked as:

```sh
if ! python3 "${TOOLS}/<gate>.py" …; then
    echo "…"
    exit 1
fi
```

Only `tools/level_staleness.py` (`case "$STALE_RC"`) and the pytest lane (`pytest_rc`)
distinguish exit codes at all. **So a gate saying "you removed the content, so there is nothing
here for me to measure" fails the build identically to "the emitted bytes disagree with the
model."** That is a single-point cause behind D3 and D4, and it converts every future honest
refusal into a content pin for free.

---

## QUESTION 2 — "so much of our dev time goes into working around tests"

**Verdict: partly supported, and the honest version is more useful to him than the flattering
one.** The frustration is real and measurable as *time cost per content change*. The evidence
does **not** support "we game the tests to get things through."

### The number, with its method

**Instrument:** commits since 2026-09-01 (9 days, **1,233 commits** — this repo runs 500-1,700
commits/week across parallel lanes), from
`git log --since=2026-09-01 --format='COMMIT %H' --name-only`, partitioned by path:

- *check* = `^tools/test_.*\.py$` ∪ `^tools/.*_gate\.py$` ∪ `^tools/.*_witness\.py$`
- *subject* = non-test `engine/**/*.emp` ∪ `games/*/**.emp` ∪ `games/*/data/**`

**Result: 64 of 1,233 commits (5.2%) edit a check and its subject in the same commit.**

**Classified sample: 12 read in full → 4 CHECK WAS WRONG (33%), 8 CONTRACT MOVED (67%), 0
WORKED AROUND.**

**What the 5.2% cannot see, and every one of these pushes the true figure UP or sideways, none
down:**

- It **undercounts the dominant pattern**: a check is found wrong in a *later, separate*
  session — often by a different lane, days after the content change that exposed it. Those
  never co-appear in one commit.
- `ensure(...)` edits inside `.emp` were **not** included — that needs per-commit content
  diffing, not path matching. A real gap in the figure, not a zero.
- A check corrected in **prose only** (no gate bytes changed) is invisible: `b2acceca` is
  exactly that, "No gate behaviour changed — messages only."
- Work **abandoned before a commit** leaves no trace anywhere.
- Merges here are real merges, not squashes, and their constituents walk individually — so
  squashing is *not* hiding rework. That one checks out in his favour.

### The finding that matters most: this exact defect already happened, three days ago

**`a621a69f` (2026-09-06)** — title, verbatim from `git log`:

> `fix(bganim): the gate I added pinned the shipped document, plus the docs the fix owes`

and from its body:

> "MY NEW GATE'S LAST ROW ASSERTED `live_section_bytes() == 8376`, which reads THIS TREE'S
> override. So the moment an author removed `default_off` — **the exact correct run this parcel
> exists to keep building** — the build failed on a TOOL TEST instead of a link error. **A gate
> pinning the shipped document's CONTENT is the failure being fixed wearing a different hat.**"

That was itself the tail of **BGANIM-DECOUPLE** (`docs/DEFERRED_WORK.md:29335`), which is the
closest analogue in the repo to tonight: an author turning off a **decorative moving background
animation** hit **three** separate build walls on one content edit —

1. `views_emitted` raising on `default_off` + >1 band — "an author does the one thing the
   editor invites them to do and gets a build failure about DEBUG view twins they have never
   heard of and did not touch";
2. an ordering assertion (`default_off` bands must be the TAIL) that fired the instant the
   first was patched — "fixing only `views_emitted` would have moved the author's build failure
   one line down and **looked like a fix**";
3. the PLAIN build dying on missing `pub` names once the refusal stopped firing first — "ONE
   shape of eight linked."

≈8 commits (`37cab840`→`a621a69f`), an owner-analog ruling, and a same-day self-correction of
the fix's own gate. **One content decision, about a day of work.**

Its generalisation is already written down and is the sentence tonight needed:

> **"a refusal removed under a ruling is not the same thing as the author's path being open."**

### The other three CHECK-WAS-WRONG cases

- **`072adc8b` (2026-09-05)** — `row_remap_gate.py` refused a NULL deform table on a **curve**
  layer while *citing a comptime guard that accepts exactly that case*, and its stated reason
  ("every line gets the same scroll word") was independently measured **false** for a curve.
  Ruled in `docs/witness/rowremap-gate-vs-guard-2026-09-05.md`; the lesson banked there —
  **"a gate that quotes an authority should be tested against that authority"** — is the same
  gate that carries D1 and D2 above.
- **`6145ea7a`** — the level-staleness gate's own docstring claimed it "cannot miss a real
  edit"; it missed a **deletion** (mtime is monotonic) and re-ran the same wrong build three
  times naming a deleted file. Same commit: the FAST wrapper piped the generator's only
  actionable line to `/dev/null` and printed a fixed wrong guess in its place.
- **`b2acceca`** — six comments/docs prescribed `hand: 0` as the way to get a `Label` default;
  measured not to compile.

### The counter-reading, stated because it is strong

**Zero WORKED AROUND instances in the sample.** The one candidate — `SIGIL_BLOB_LEN_DRIFT=warn`
— is explicitly documented as "relax[ing] no contract check and … explicitly not a landing
state." Checks in this repo are not quietly loosened to get things through; they are either
shown genuinely wrong and repaired, or the contract really moved and they were updated to
match, usually with a red-first re-proof. Recurring gate names across the 64
(`test_effects_gen.py` 7×, `spring_launch_witness.py` 6×, `demo_specialization_witness.py` 4×,
`row_remap_gate.py`/`row_remap_witness.py` 4×) cluster inside **EFFECTS-W1**, one large
in-flight feature landing content and its gate together — normal TDD-shaped iteration on new
work, not a check fighting existing content.

**So the accurate sentence is not "we work around tests." It is: the check suite is dense
enough, and its content-shape assumptions narrow enough, that an ordinary content edit
routinely surfaces two or three previously-unmodelled cases before it can land — and that costs
real hours even when every individual fix is legitimate.** That is a different problem from the
one he named, and it is a more tractable one.

### The repo already holds the bar it is breaking

`docs/OVERSEER-LOG.md:1131-1136`, written before tonight:

> "**the cost is not the false stop, it is what the operator does next.** A refusal that fires
> on correct work trains a route-around — an env var someone always sets, a flag someone always
> passes, a step someone always skips — and **the route-around is permanent while the memory of
> why is not.** … So a gate that over-refuses does not merely annoy; it **converts itself into a
> disabled gate** by a path nobody records."

and, a few lines on:

> "the vacuous-pass family is better represented here only because a false green leaves no one
> arguing with it, while **a false red gets routed around within the hour and looks like it was
> fixed**."

**This is the mechanism by which "ease up on the tests" becomes the rational response.** The
owner's instinct is the bar the repo already wrote.

---

## RANKED SHORTLIST — worth fixing first, and why each earns its place

**1. The `build.sh` exit-code collapse.** *(§Exit codes)*
Ranked first because it is **one change that de-fangs a whole class, including cases not yet
written.** A `case` per gate instead of `if !`, so exit 2 reports **UNMEASURABLE** and does not
fail the build. Eleven gates already implement the distinction carefully and are being ignored
at the call site — **the work is already paid for and is being thrown away by one shell idiom.**
It resolves D3, D4 and D5 outright. **Highest leverage per line changed, and the only item that
also protects the future.**

**2. `tools/test_lab_index_lint.py:502` and `:530` — the two `== 1` pins.** *(C1, C2)*
The purest instance of the owner's sentence: a **debug-lab fixture** held build-fatally in place
forever by the pre-build pytest lane. The fix is a change of *shape*, not a deletion — make the
pins **conditional**: *if* a scene carries a live `rowRemap:`, exactly one WLINE row must name
it (C10, the good part, unchanged); if none does, require **zero** WLINE rows. Keeps every
failure C10 catches; refuses nothing the owner is entitled to decide. **Cheapest fix, largest
share of tonight's blast radius.**

**3. `scene_registry.emp` A1/A2/A3/A4 — the "THREE-file retreat" family and the equality pin.**
The comptime half of tonight's refusal. They refuse over **waste, not breakage** — 272 ROM bytes
and 26 cycles/band/frame is a thing to *warn* about, loudly, not to refuse on. The repo already
has the right pattern and used it three days ago: **decline and announce**, in two places, the
way `inject_editor_bg.py` now handles `default_off` ("the twins' condition SURVIVES UNCHANGED …
and stops being able to veto what the act ships"). **Fix all four together or not at all** — A4
fires on the same edit, so repairing A1-A3 alone moves the wall one line down, which is exactly
the BGANIM lesson. A2's prescribed retreat is additionally **stale** by its own banner's
admission, which is a second reason to touch it.

**4. `tools/row_remap_gate.py:727` — the 8-px visibility floor.** *(D2)*
The clearest *principled* case in the audit: a **perceptual threshold enforced build-fatally**.
Its own constant's comment says such a bar "can only be calibrated against someone looking at
the screen" — and the person looking at the screen is the one the build is refusing. Should be a
loud report, never `exit 1`. Ranked fourth only because it bites less often than 1-3.

**5. `tools/test_anchor_sweep_band.py` C5/C6/C7 and `tools/band_drift_golden.py:72` D3.**
Grouped because they share one fix and one reason: each holds an **n=1 population** build-fatally,
and each already **names the remedy in its own failure message** ("should come out in the same
commit", "this file and its build.sh call go with it"). **A check that can already describe the
legitimate reason it is firing should not be failing the build for it.** C6 is the "in a
*specific section*" case — it requires the sweep to be on the act's spawn section, so *moving*
it fails. D3 hard-codes `Scene_OJZ_Default` by name.

**6. `tools/test_effects_seam_gate.py:783` (C3) and `tools/test_map_dplc_binding.py:303/307`
(C4).** Two self-aware pins worth fixing for what they teach as much as what they cost. C3's
docstring calls itself "*the content assertion*" and is build-fatal anyway. C4 puts the healthy
guard (`len(emp_sources()) > 100`) and the over-reaching one (`len(maps) == 7`) four lines apart
in one function — **the single clearest before/after example in the repo for anyone writing the
next guard.**

**7. Settle, do not fix: `tools/editor_palette_golden.py:262` (D4) and
`tools/effects_seam_gate.py:506` (D6).** Both are AMBIGUOUS and may be correct. D4's guard is
generically shaped but has an n=1 population *in this tree*, which is the healthy-in-theory /
pinning-in-practice trap — settle by deciding whether a second `cycles`/`variants` document is
expected. D6 asks for reachability but words it as an instruction to author content — settle by
checking whether the `--lst` arm's `pub equ` witnesses already prove the seam is reached.

**Not on the list, deliberately:** A5 (`CAP_MULTI_DEFORM_TABLE == 0`) is an **owner-set park**,
not a defect — it refuses a content decision on purpose and says so. D7 is not build-fatal.

### The one-line rule worth adopting over all of it

**A check may say "if this content exists, it must be correct." It may not say "this content
must exist" unless it can name, at the assertion, what breaks — and "we would waste bytes" is
not a break.** Mechanically: **write the implication as `authored ⇒ declared`, never
`declared ⇒ authored`.** Every defect in this audit is the second direction; every safe sibling
is the first.

---

## WHAT THIS AUDIT DID NOT ESTABLISH

- **That any hit actually fires.** No build was run. The five-refusal chain is derived from
  source; a build with the `rowRemap:` removed would confirm the set and, more usefully, might
  reveal a **sixth** wall behind them — which is exactly what BGANIM-DECOUPLE teaches to expect.
  **The single highest-value follow-up is that one-key control run**, not more reading.
- **Whether `tools/waterline_art_gate.py` is in that chain.** Its `demo`/undeclared arms are
  clear, but whether `WaterlineStripArt` and the `Waterline_Art_Update` gather survive a
  scene-level `rowRemap:` removal was not traced to a conclusion.
- **130 of the 157 non-test tool scripts were pattern-swept, not read.** Only the 23 build-fatal
  ones (plus the two read directly) got a full reading. A defect phrased outside the three
  mechanism shapes — a bare numeric comparison with no `len()`/`not` idiom, or a hard-coded
  object/monitor/ring name rather than a scene name — could sit in those 130 unseen.
- **Helper-function assertions in the pytest suite were not exhaustively traced to callers.**
  A content-shaped assertion living in a shared helper, in a file otherwise judged clean, could
  be under-counted.
- **`ensure`s emitted by a generator** rather than written literally are visible only through
  the generator (`tools/effects_gen.py:2991` emits one per document); a grep of the checked-in
  `.emp` sees the output, not the rule.
- **`tools/effects_gates.py`** — the merge-ritual lane, ~1,300 lines — was not swept. It is not
  build-fatal, but it is **merge-fatal by owner ruling**, so it can block work the same way.
  **This is the largest named gap.**
- **The `ensure`-diff half of the Question-2 number.** Path matching cannot see a check that
  lives inside a `.emp` file that also carries content, so 5.2% is a floor, not a measurement.
- **Any cross-repo checks** — Aurora's editor-side and sigil's own gates were out of scope.
- **A count of how often each hit has actually blocked someone.** The Question-2 classified
  sample is 12 commits read out of 64 co-edits, not a census. **No claim here is a frequency
  claim.**
- **Whether "ease up on the tests once the project is complete" is the right remedy.** This audit
  deliberately did not evaluate that idea. Its finding is narrower and, I think, better news:
  **the problem is 19 sites, not the test culture** — the culture is what produced the
  `authored ⇒ declared` pattern correctly everywhere else.
