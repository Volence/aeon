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

### A2. Comptime `ensure` — the three seams I missed, found by the dedicated sweep

**All quotations below were re-read at source by me before booking.** Population: 1,317 non-poison
`ensure` sites across 89 files (81 sites in `games/sonic4/test/poison/` are deliberate expect-fail
fixtures and are excluded).

| # | site | condition | class | note |
|---|---|---|---|---|
| A6 | `engine/level/scene_dsl.emp:2456` | `ensure(scenes.len >= 1, "fold_caps(): an empty scene registry has no capabilities to fold — a game with no scenes should not be declaring a cap mask")` | **PINS-CONTENT — and the most consequential hit in the audit** | Folding an empty array is a correct no-op returning 0. **This guard has already caused a shipped route-around, and the route-around is written into the source.** See the box below. **⚠ FIXED 2026-09-10 — see the ANNOTATION at the end of this file. The row above is left exactly as written; the guard it names no longer exists.** |
| A7 | `engine/level/scene_dsl.emp:3131` | `ensure(scenes.len >= 1, "scene_budget_enforce(): an empty scene registry has no budget to check …")` | **PINS-CONTENT** | A6's twin on the budget fold, same consequence. **⚠ FIXED 2026-09-10 in the same parcel as A6 — see the ANNOTATION at the end of this file.** |
| A8 | `games/sonic4/data/effects/ojz_scenes.emp:372` | `ensure(OJZ_UNDERWATER_REMAP_PX >= REMAP_VISIBLE_MIN_PX, "… the effect is ON but NOBODY CAN SEE IT")` | **PINS-CONTENT** | **A direct correction to my D2 entry, which said the 8-px perceptual floor was gate-only.** It is enforced *twice* — once post-sigil in `row_remap_gate.py:727`, and once at comptime here, **pinned to `Scene_OJZ_Underwater` by name**. The message concedes "the floor itself is an observation, not a derivation." Fixing D2 without this leaves the wall standing — the BGANIM lesson again. |
| A9 | `games/sonic4/data/characters/knuckles_data.emp:174` | `ensure(((_pal_sonic_tails[18]<<8)\|…) != ((_pal_knux[18]<<8)\|…), "slot 9 now AGREES … the forced $0444/$0080 hole is closed …")` | **PINS-CONTENT — the sharpest instance found** | **It requires a documented colour *bug* to remain present.** An artist who closes the hole — an unambiguous improvement — fails the build. In fairness its message is constructive ("Delete them and tighten the mismatch count to 3"), which is the tell: **this is a notification implemented as a refusal.** |
| A10 | `knuckles_data.emp:191,193,195,197,199,201` (6 sites) | `ensure((_pal_*[N]<<8 \| …) == DUST_GRAY_IDX{4,6,7}, …)` | **AMBIGUOUS** (the sweep called it PINS-CONTENT; I downgrade it) | It pins literal authored colours — but **it names what breaks and the break is real**: shared line-0 art (dust, insta-shield, spring) is drawn through a per-character palette line, so re-exporting both palettes in lockstep passes every agreement check while the dust turns the wrong colour for everyone. That is the 2026-08-12 red-dust bug. **This is the "say what breaks" test being passed.** Settled by: whether recolouring the dust is a decision the owner wants to make by editing the three adjacent `const`s (cheap) or expects to make in the art alone. |
| A11 | `games/sonic4/objects/ring_sparkle.emp:131`; `games/sonic4/player/player_instashield.emp:412`, `:414` | `script_display_frames(…) == S3K_SPARKLE_FRAMES * (…)`; the two donor-timing equalities | **PINS-CONTENT** | Donor-fidelity locks on **cosmetic** animation timing — `ring_sparkle.emp`'s own header says the effect "is purely cosmetic … its absence changes no gameplay state." Both messages read "re-derive the script, do not retune the reference", which forbids a legitimate feel decision by policy rather than by consequence. |
| A12 | `games/sonic4/player/knuckles.emp:138` | `ensure(KNUX_JUMP_FORCE < PHYS_JUMP_FORCE, "…that difference is the only reason this row exists")` | **PINS-CONTENT** | A **balance** value pinned by strict inequality. Its own remedy is "delete the row", i.e. nothing mechanically breaks — it is a tidiness rule refusing a retune. |
| A13 | `engine/effects/raster_dsl.emp:362`, `:524`; `engine/effects/palette_dsl.emp:44`, `:95` (the `count >= 2` half) | `fire: a fire with no ops`; `compose: nothing to compose`; `variant: lines mask selects no level line`; `count >= 2` | **PINS-CONTENT** | Degenerate-input guards that **duplicate safety nets the runtime already has** — `raster.emp` handles an op-count-0 fire as a documented priming record (`bmi .priming`); `palette.emp` leaves uncovered lines as-is; `Palette_RotateSpan` carries its own live `count < 2 is a no-op` branch. Each forbids an author expressing "nothing here", which is a normal thing to want while building content up. **Note the contrast with their real siblings** — `raster_dsl.emp:257/327` (`colours.len >= 1`) and `raster.emp:509/778` (`lines >= 1`) are **REAL-INVARIANT**: count 0 underflows to `$FFFF` in a `dbf` inside the HBlank handler. Same file, same shape, opposite verdict — which is exactly why this has to be judged per site. |

> **⚠ THE ROUTE-AROUND IS ALREADY SHIPPED, AND IT IS IN THE SOURCE IN PLAIN WORDS.**
> `games/demo/config/game.emp:15-20`, verbatim:
>
> > "*Nothing to derive and nothing to verify: **`fold_caps()` REFUSES an empty registry rather
> > than folding it to 0, so the demo deliberately has no scene registry to check this
> > against**, and this binding is the whole statement.*"
>
> The demo game — **the permanent proof that the engine is game-agnostic** — cannot use the
> capability-folding mechanism at all, because a guard refuses the legitimate zero case. Its
> `SCANLINE_CAPS = 0` is therefore **hand-asserted and unverified**, where every other game's is
> derived and checked.
>
> **This is not a hypothetical cost. It is `docs/OVERSEER-LOG.md:1131` happening, in the tree,
> already:** *"a refusal that fires on correct work trains a route-around … the route-around is
> permanent while the memory of why is not … a gate that over-refuses **converts itself into a
> disabled gate** by a path nobody records."* Here the path *was* recorded — which is the only
> reason this audit can see it, and a reason to think other instances were not.

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
removal. **⚠ CORRECTED — I FIRST WROTE THAT CONTENT-EXISTENCE PINNING IN `.emp` WAS CONFINED TO
THE FOUR `SceneRegistry_CapsFolded` ARMS. THAT WAS WRONG, AND WRONG IN MY FAVOUR** — it made the
comptime layer look clean and pushed the whole problem onto Python. A dedicated `ensure` sweep of
all 1,317 non-poison sites found **17**, in three seams I had not looked in: engine-side DSL
population guards, donor-fidelity animation/palette pins in character data, and degenerate-input
guards in the effects DSLs. **The operator-census reasoning below is still sound and is kept
verbatim — it correctly describes where the *mass* sits. What it could not do is find a hit,
because a census of operators cannot see what an operand MEANS.** That is the method failure
worth keeping: I generalised from a shape distribution to an absence. The original sentence
read: "Content-existence pinning in `.emp` is confined to the four `SceneRegistry_CapsFolded`
arms above. That is a genuinely good result for the comptime layer, and it makes the Python
layer, not the language, where this problem lives."* **Both sentences are false.** See section
A2 below for the thirteen sites I missed.

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
| ~~`games/sonic4/test/scene_equiv_proof.emp`~~ — **MOVED TO AMBIGUOUS, see below** | names every scene and band index literally (`EQ_OJZ_Windy_b0`, …) | I first filed this here on the ground that deleting a scene yields an unresolved-name **compile error**, not a false assertion. **That reasoning holds for DELETION and misses the larger case: TUNING.** The 93 `ensure(EQ_… == -1)` sites compare 20 live scenes against a **hand-transcribed snapshot frozen in the same file**, and the file's own banner declares itself **PERMANENT** ("deleting this module is a spec change, not a cleanup"). So changing *any* authored number on *any* of those 20 scenes — a band factor, a drift rate, a `v_center` — requires hand-updating this witness in the same commit, **forever**, for a proof whose stated job was a one-time migration. **What would settle it:** whether "permanent" was meant to outlive the DSL migration it exists to prove. If not, this is the single largest standing tax on scene tuning in the tree. |
| `act_descriptor.emp:363` | `ensure(GRID_W * GRID_H == 9)` | Pins a literal `[Sec; 9]` array length. Real invariant *as written*; the better shape is `[Sec; GRID_W*GRID_H]`, which would delete the pin. |
| `act_descriptor.emp:132` ↔ `scene_registry.emp:658` | `SCENE_ACT_SPAN_Y == (GRID_H << SECTION_SIZE_SHIFT)` | A two-species mirror pin — a number written twice must agree. Resizing the act touches two files; that is the documented cost of the mirror, taken to avoid an import cycle. |
| `ojz_effects.emp:2232` | `ensure(REEL_COLS_PER_BAND == 4, …)` | **The contrast case, and worth reading beside D2 and A1.** It has the exact shape of a content pin — a literal equality on an authored-looking design number — and it is a **REAL-INVARIANT**, because `OJZ_Reels_Fill`'s column→band map is a hard-coded `lsr.b #2`. Change the constant without the shift and the loop addresses the wrong band. **This is what "say what breaks" looks like when there is an answer**; A1-A4 and D2 are the same shape with no such answer. |
| `games/sonic4/test/scene_equiv_proof.emp:749-769`, `ojz_effects.emp:392/2017` | `.len == 256`, `.len == 6`, `.len == 25` | Internal consistency of **hand-written twin fixtures** against the generator they check (a padding run is computed against a 25-word body). Gate fixtures, not shipped content. |

---

## THE COUNT, WITH ITS UNIT

| classification | count | unit |
|---|---|---|
| **PINS-CONTENT** | **30** | **check sites** — **15 comptime `ensure`** (A1-A4, A6-A9, A11 ×3, A12, A13 ×4) + 10 pytest assertion sites (C1-C9; C9 is two sites in one file) + 5 gate sites (D1, D2, D3, D5, D7) |
| **AMBIGUOUS** | **29** | check sites — 12 pytest, 2 gates (D4, D6), **15 comptime** (A10 ×6 and 9 more the sweep raised, incl. `scene_equiv_proof.emp` counted as ONE mechanism spanning **93 sites**) |
| **REAL-INVARIANT** (in the swept candidate set — checks that *look* like content pins and are not) | **~20** | check sites, incl. the 4 `BAND_*_N` pairs, the two subset arms, the `CAP_DENSE_TIER` family, C10, and `REEL_COLS_PER_BAND` |
| **PINS-CONTENT BY DESIGN** (owner-set park, out of scope) | **1** | check site (A5) |

**No site is counted twice: D4 and A10 are AMBIGUOUS only, and are not in the 30.**

**⚠ THE FIRST VERSION OF THIS TABLE SAID 19, AND THAT NUMBER IS SUPERSEDED.** It was built before
the dedicated `ensure` sweep and undercounted the comptime layer by eleven sites (4 → 15). The
error was not arithmetic; it was **a population I declared closed on the strength of an operator
census** — see the correction in §WHAT WAS SWEPT.

**Files affected: 9 pytest files, 3 gate scripts, and 8 `.emp` files** (`scene_dsl.emp`,
`scene_registry.emp`, `ojz_scenes.emp`, `knuckles_data.emp`, `ring_sparkle.emp`,
`player_instashield.emp`, `knuckles.emp`, `raster_dsl.emp`/`palette_dsl.emp`). Of the **30**
PINS-CONTENT sites, **29 are build-fatal today** — every comptime `ensure` is, by construction —
and the single exception is **D7**, a standalone witness `build.sh` does not call.

**Against populations of 1,398 `ensure` sites, 2,217 test functions and 157 tool scripts this is
still a small and concentrated defect (~1.3% of `ensure` sites), and a fix is still tractable
rather than a rewrite.** But **two of the three worst hits are engine-side, not game-side**
(A6/A7), and one of them has **already cost the demo game its capability verification** — so the
"it is only Python, and only the effects seam" reading I reached first was comfortable and wrong
in both halves.

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

**⚠ WITH ONE EXCEPTION THAT LANDED AFTER I WROTE THE ABOVE, AND IT MOVES THE VERDICT TOWARD HIM.**
I wrote "0 WORKED AROUND" from a sample of commits, and that finding stands *for commits*. But the
`ensure` sweep found a route-around that **no commit-diff instrument could ever have seen, because
it is a permanent state rather than an edit**: `games/demo/config/game.emp` hand-asserts
`SCANLINE_CAPS = 0` and skips the capability-folding mechanism entirely, because `fold_caps()`
refuses an empty registry (A6). **A whole game's capability declaration is unverified today as a
direct result of an over-strict check.** That is a *worked-around* gate in the fullest sense —
just worked around once, structurally, rather than repeatedly in diffs. **My 5.2% instrument is
blind to this entire category**, and I do not know how many more there are; this one was findable
only because someone wrote down why. **Weigh his impression accordingly: the commit record
understates it, and I said so having first reported the opposite.**

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

**0. `engine/level/scene_dsl.emp:2456` and `:3131` — `scenes.len >= 1`.** *(A6, A7)*
**Promoted above everything else on evidence that arrived last.** It is the only hit in the audit
with a **demonstrated cost already paid**: the demo game's `SCANLINE_CAPS = 0` is hand-asserted
and unverified *because* `fold_caps()` refuses the empty registry, and the source says so in
those words. Two engine-side sites; the fix is to fold an empty array to 0, which is what it
mathematically is. **It restores a verification the project currently does not have, rather than
merely removing an annoyance** — the only item here that makes the check suite *stronger*.

> **⚠ LANDED 2026-09-10 — item 0 IS DONE, and the shortlist above is left as written.**
> Both sites are gone, and the demo's `SCANLINE_CAPS` is a folded value rather than a
> hand-assertion. **The item's promise held**: this is the entry that made the suite
> stronger, and the ANNOTATION at the end of this file carries the evidence — including
> the RED run that proves the guard really was what blocked the demo, and the two
> independent readings that the computed value equals the 0 that was asserted.
> **One claim in this section is wrong and the annotation corrects it**: the demo's mask
> was not the odd one out for being *hand-written* — `games/sonic4/config/game.emp` writes
> `SCANLINE_CAPS = $0FDE` by hand too. It was the odd one out for being **unchecked**.


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

**4. The 8-px visibility floor — `tools/row_remap_gate.py:727` AND `ojz_scenes.emp:372`.**
*(D2 + A8)* The clearest *principled* case in the audit: a **perceptual threshold enforced
build-fatally**. Its own constant's comment says such a bar "can only be calibrated against
someone looking at the screen" — and the person looking at the screen is the one the build is
refusing. Should be a loud report, never `exit 1`. **Fix both or neither:** it is enforced twice,
once post-sigil and once at comptime pinned to `Scene_OJZ_Underwater` by name, and repairing only
the gate leaves the comptime wall standing — the BGANIM lesson, for the third time in this list.

**4b. `knuckles_data.emp:174` — the pin that requires a bug to stay.** *(A9)*
Cheap and worth doing for what it signals as much as what it costs: it fails the build if an
artist *fixes* a documented palette hole. Its message already tells the reader exactly what to
delete, which means **it wants to be a notification and was written as a refusal** — the
one-line summary of this whole audit.

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

- **WHICH `ensure` SITES ARE ACTUALLY ELABORATED.** This tree's own comments record that
  `ensure(1 == 0)` inside an unreferenced module builds green — sigil does not always elaborate a
  module nothing imports (`reference_emp_guard_reachability`). This audit was textual. **Some
  fraction of the 15 comptime PINS-CONTENT sites may be unreachable and therefore inert**, and
  nothing here distinguishes them. A6/A7/A8/A9 are reachable by inspection (they sit in modules
  the build's own errors and the demo's comment prove are elaborated); the rest are not
  established either way.
- **⚠ A REPORTED TOOLING TRAP THAT I COULD NOT REPRODUCE, recorded because acting on it would
  have been wrong.** The `ensure` sweep reported that this shell's `grep` alias silently
  under-recurses, dropping `games/sonic4/test/poison/` from a whole-tree search with no error.
  **It does not reproduce here:** alias and `command grep` both return **1398** sites, and the
  alias returns the poison subtree's **81** when asked. Every count in this document was taken
  with the alias and is unaffected. **Booked as unreproduced, not as a fact** — this repo has one
  retracted grep-behaviour claim on the books already, and a confident mechanism written into
  three places before testing it.
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
  **the problem is 30 sites, not the test culture** — the culture is what produced the
  `authored ⇒ declared` pattern correctly everywhere else.

---

## ⚠ ANNOTATION 2026-09-10 — ITEM 0 (A6 + A7) IS FIXED, AND WHAT THE AUDIT GOT RIGHT AND WRONG

**Nothing above this line was rewritten.** This file annotates its own superseded findings
rather than editing them (it already does so for the 19-site count), and this section is the
same shape: the audit's reading of A6/A7 is left exactly as it was written, and what a build
subsequently said about it is recorded here.

Branch `parcel/foldcaps-empty-registry`, base `8f1f8aad`, sigil
`49ecc532e0b133ab0eab9447e071805c`. **Builds WERE run this time** — four shapes — which is
the axis on which this section can say things the audit could not.

### THE COORDINATES HELD, WHICH IS WORTH RECORDING GIVEN HOW OFTEN THEY DO NOT

`engine/level/scene_dsl.emp:2456` (A6, `fold_caps`) and `:3131` (A7,
`scene_budget_enforce`) were both exactly where the audit said, with the conditions and
messages quoted verbatim. Found by symbol first and confirmed by line, not the other way
round.

### THE COST WAS REAL, AND IT WAS MEASURED RATHER THAN INFERRED

The audit derived from source that A6 is what forced the demo's route-around. That is now a
measurement. With the demo binding applied and the fold **not yet changed**, the demo build
failed with:

```
./engine/level/scene_dsl.emp:2456:5: error: fold_caps(): an empty scene registry has no
capabilities to fold — a game with no scenes should not be declaring a cap mask
```

**That RED is the load-bearing evidence in this whole item.** It rules out the reading the
audit itself flags as its biggest blind spot — "WHICH `ensure` SITES ARE ACTUALLY
ELABORATED" — for this site specifically: `scene_dsl.emp` is inside the **demo's** `use`
closure already (`engine/level/parallax.emp` and `engine/effects/raster.emp` both import its
`CAP_*` consts), so the guard was live, not inert, in the shape it was blocking.

### THE IDENTITY, DERIVED FROM THE BODY RATHER THAN FROM THE WORD "FOLD"

`fold_caps` is a bitwise-OR accumulation and 0 is OR's identity — but that was checked
against the body rather than assumed from the name, which is what the task asked for:

- `caps` starts at `0`;
- the loop only ever ORs bits **in** (`caps = caps | scene_caps(s)`) — there is no clear, no
  mask-off, no subtraction, so no starting value other than 0 could be neutral;
- the one bit no single scene can raise, `$0010 CAP_TRANSITIONS`, is added under
  `scenes.len > 1`, which an empty list fails **for the same reason a one-scene game does** —
  a transition is a property of an edge between two scenes.

So an empty registry demands no scanline service and crosses no transition. **0 is the
answer, and it is the only answer consistent with both arms.**

A7 is a different shape and needed its own reading rather than "twin of A6": every `ensure`
in `scene_budget_enforce` is **inside** the per-scene loop, charged against one scene's own
five axes, with no cross-scene sum (the file's own banner: max, never sum, since one scene is
live at a time). A game with no scenes spends nothing on any axis and the honest count of
scenes checked is 0.

### THE VERIFICATION WAS RECLAIMED, WHICH WAS THE POINT OF THE ITEM

`games/demo/config/game.emp` now declares its registry and folds it:

```emp
pub const DEMO_SCENES: [Scene; 0] = []
pub const DemoScenes_CapsFolded = fold_caps(DEMO_SCENES)
...
    const SCANLINE_CAPS = DemoScenes_CapsFolded
```

and the comment the audit quoted — "Nothing to derive and nothing to verify: `fold_caps()`
REFUSES an empty registry…" — is gone with the refusal that caused it.

**The computed value equals the asserted one, read two independent ways:**

1. **Directly.** Asserting `DemoScenes_CapsFolded == 12345` under a throwaway probe made
   sigil print the real value in its own diagnostic: `PROBE: DemoScenes_CapsFolded is 0`.
2. **By the artifact.** `demo.bin` and `demo.debug.bin` came out **byte-identical** across
   the change (`97051 B crc f7fdf77d` / `103335 B crc ff11e22d`), as did both sonic4 shapes.

**What did NOT change is as important as what did.** The number is the same 0. What moved is
that it is now *computed*: the day the demo authors a scene, its mask follows the scene
instead of waiting for someone to remember. A zero-scene fold is trivially 0 today, and this
annotation says so plainly rather than dressing it up — **the win is the mechanism being
reachable at all, not the arithmetic.**

### ⚠ ONE THING THE AUDIT GOT WRONG, IN ITS OWN FAVOUR

The audit says the demo's `SCANLINE_CAPS` is hand-asserted "**where every other game's is
derived and checked**". The second half is right and the first is not.
`games/sonic4/config/game.emp` writes `const SCANLINE_CAPS = $0FDE` — a hand-written literal,
exactly like the demo's `0`. **No game derived its mask.** What sonic4 has and the demo did
not is the *check*: `scene_registry.emp`'s `(SceneRegistry_CapsFolded & ~Game.SCANLINE_CAPS)
== 0` subset arm, plus the two-sided `SceneRegistry_CapsExpected` equality.

This matters beyond pedantry, in two directions:

- It **strengthens** the audit's core claim. The demo was not merely unusual in *style*; it
  was the one game whose declaration **no check could see**, because the mechanism that does
  the seeing refused to run on it.
- It **narrows** what this parcel accomplished. The demo is now the only game whose mask is
  *derived*; sonic4's is still declared-and-checked. `engine/system/game_contract.emp`'s own
  banner describes the intended pattern as "Derived-and-verified, never
  hand-maintained-unchecked", and sonic4 satisfies the second half of that sentence but not
  the first. **Whether sonic4 should bind `fold_caps(SCENES)` directly is a separate
  decision and was NOT taken here** — `scene_registry.emp` argues against it in terms
  (deriving the expected word from the fold "would make the test `x == x`, which is the
  vacuity `poison_scene_mask.emp`'s header warns about"), and that argument deserves to be
  answered rather than stepped over.

**THE ALTERNATIVE WAS BUILT AND MEASURED BEFORE BEING PUT DOWN, so the choice is on the
record rather than asserted.** The declared-literal + subset-`ensure` shape — sonic4's,
and the one `game_contract.emp` prescribes — was implemented, built green, and rejected on
two grounds. It is the WEAKER of the two (a subset test passes for any declaration merely
wide enough, while a bound fold cannot be wrong), and it **moved the demo ROM**: a
module-level `ensure` in the manifest carrying `implement Game` flips a branch relaxation
two screens away. That second fact is a sigil finding and is written up below; the first is
why the derived form would have won anyway.

### WHAT THE OLD GUARD ALSO HAPPENED TO CATCH, AND WHERE THAT DUTY WENT

`scenes.len >= 1` would also have caught a caller whose registry NAME resolved to nothing —
the silent-degradation shape `docs/EMP_PITFALLS.md` §2 warns about. **It is not needed for
that, and this was measured rather than reasoned:** `fold_caps(NO_SUCH_REGISTRY)` produces
three errors, not an empty array —

```
a label is not a valid `array` argument, only a `Label` parameter accepts a label
for expects a range or array, got label
`len` is not a field or `.len` of label
```

An unresolved name in argument position becomes a **label**, and a label is refused at the
call, at the `for`, and at the `.len`. The §2 silence does not apply to an `array` parameter.
Both shipped callers additionally pin their own length: `scene_registry.emp`'s
`SCENE_CYCLE_COUNT == SCENES.len`, and the demo's declared `[Scene; 0]` type.

### THE ANTI-VACUITY READING TO BE CAREFUL WITH

A `0` out of `scene_budget_enforce` is **not** evidence that a budget was enforced. It never
was: the refusal that has been removed would not have caught a registry shrinking from 20
scenes to 1, which is the realistic silent loss. The pin that can see that is the caller's
own length pin, and it is unchanged. That sentence is now in the source at A7's site, so a
future reader meets it where the wrong inference would be made.

### TWO SHIPPED CHECKS ASSUMED A HAND-WRITTEN MASK, AND FOUND IT THE MOMENT IT WAS NOT

Worth recording because it is the audit's own thesis turning up in the parcel that fixes it.
Making the demo's mask a *name* rather than a *literal* failed the build with **2 failed,
2396 passed**:

- `tools/scene_spans.py:game_caps()` text-scrapes `const SCANLINE_CAPS = <literal>` and
  raises `SystemExit` when it cannot, because "guessing zero here would silently assert the
  maximal elision". **That refusal is correct and it stays.** What it lacked is the one
  derivation it can *prove* from source: a name bound to `fold_caps(<registry>)` whose
  registry is DECLARED `[Scene; 0]`. It now follows exactly that and nothing else — a
  registry with scenes in it still refuses, naming the count, and so does an untyped `= []`
  (`[]` is the tool reading a literal; `[Scene; 0]` is the type checker agreeing).
- `test_emp_helper_closure.py::test_real_implement_block_bindings_are_not_module_items`
  asserted `comptime_items(game.emp) == set()` — which held only while neither manifest had
  any module-level item at all. **That is a fixture-shape pin, and it was also the weaker
  assertion**: an empty result is equally consistent with a scanner that finds nothing
  anywhere. It now reads the contract members out of `game_contract.emp` and asserts none
  leaks into the exported set, which is the property the test is named for. `games/demo`,
  now carrying depth-0 items AND depth-1 members in one file, is the first fixture that can
  tell a depth-aware scanner from a blind one.

Both changes were proven red-first against the real subject: `comptime_items`'s brace-depth
line was mutated to `at_item = True` (the amended test then reported all three contract
members leaking), the live demo registry was mutated to `[Scene; 2]` (the tool refused,
naming the count), and the tool's own refusal arms were mutated away one at a time. Each
mutation was quoted from disk before its run and restored from a committed baseline.

### A THIRD PRIVATE PARSER, AND THE AUDIT'S RANKED-FIRST ITEM BITING IN PASSING

`./build.sh demo` then failed at a post-sigil gate, not in the pytest lane:

```
row_remap_gate: UNMEASURABLE — SCANLINE_CAPS is not declared in games/demo/config/game.emp
```

`tools/row_remap_gate.py` carried a **third** private three-line regex for the mask (and
`tools/waterline_art_gate.py` imports that one, so it is two consumers behind one reader).
**Its own docstring already recorded this exact failure happening once**: the regex knew only
the hex spelling, read demo's bare `0` as UNMEASURABLE, and that was "two shapes silently not
gated" — measured 2026-09-03. The derived binding is the second spelling the same private copy
could not read. Three consumers with three parsers is three chances to miss a spelling, so
there is now one (`scene_spans.caps_from_manifest`), and a new `TestDerivations` row fails if
any consumer starts answering differently from it, **for both games** — because a reader can be
right about one and wrong about the other, which is exactly how the September miss survived.

**AND NOTE HOW IT FAILED.** The gate said *"I could not measure this"* — its own carefully
drawn exit 2 — and `build.sh`'s `if ! python3 …; then exit 1; fi` turned that into a failed
build. That is **this audit's ranked-first item**, observed rather than derived, in the parcel
that fixes its ranked-zeroth. The gate was right, its exit code was right, and the call site
threw the distinction away.

### ⚠ A SIGIL FINDING THIS PARCEL TRIPPED OVER AND DID NOT CHASE — FOR THE OWNER

**A comptime-only `ensure` in `games/demo/config/game.emp` changes the demo ROM.** Measured
while evaluating the declared-and-checked alternative: adding `ensure(1 == 1, "x")` — inert,
no names, no emission — at module level in the manifest carrying `implement Game` produced
`crc e63260f9` instead of `f7fdf77d` at the **same length** (97051 B), with 20,395 bytes
differing. The listing locates it: `VSync_Wait`'s tail is **2 bytes shorter** with the
`ensure` present (`HBlank_Install` at `$BC8` vs `$BCA`) and everything after shifts with it,
which is the signature of a **branch-relaxation** flip (`VSync_Wait` ends in a relaxable
`jbsr PageIn_Process` and a relaxable `beq`).

Isolated as far as is useful without touching the sigil repo:

- the message text is irrelevant — `"probe A"` and `"X"` give the same `e63260f9`;
- a `pub const` at the same position is byte-NEUTRAL, so it is the `ensure` specifically;
- the same `ensure(1 == 1, "x")` in `games/demo/config/constants.emp` is byte-NEUTRAL, so it
  is specific to the module carrying `implement Game`;
- it is deterministic: repeated builds of each variant reproduce their own crc exactly.

**Nothing in this parcel ships that ROM** — the landed shape binds the fold and is
byte-identical on all four images. Recorded because a zero-byte comptime construct silently
changing emitted code is worth an owner's attention, and because the next person to add an
`ensure` to a game manifest will meet it.

### WHAT THIS PARCEL DID NOT TOUCH

Items 1 through 7 of the ranked shortlist are all still open. **No sigil `*_port` test moved**
and none was edited: `scene_registry_port.rs` lowers `scene_dsl.emp` through the sonic4
profile and byte-compares the `scene_registry` region against `s4.bin`/`s4.debug.bin`, and
both ROMs are byte-identical across this change, so its region expectations cannot have
moved; `parallax_port`, `raster_port`, `bg_anim_port` and `raster_negative_probes` scrape only
`scene_dsl.emp`'s `pub const CAP_*` block, which this parcel does not touch.
`warn_tier_corpus.rs` keeps `("demo plain", &[])` / `("demo debug", &[])` as a live control on
`import.no-names`; the demo's new import is a **glob** (`use engine.level.scene_dsl.*`), which
that lint names as one of its two recommended forms, and the demo's warning summary is
unchanged id-for-id and count-for-count across the change.
