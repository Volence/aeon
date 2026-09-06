# Effects Authoring — Consumer Field Contract

*Status: contract, 2026-08-22 (draft for design review). This is the aeon half of the
Aurora effects-authoring contract: **exactly which fields the consumers read**. Per the
sprite-export ruling (`docs/DEFERRED_WORK.md:120-125`), a neutral-data format is NOT a
contract until the consumer's exact field list is enumerated and handed over for a
writer-side golden — this document is that enumeration for the effects surfaces. The
writer-side half (what Aurora writes: shapes, ranges, defaults) is
`empyrean/docs/AURORA_EFFECTS_SCHEMA.md` + `empyrean/contract/schema/aurora-effects-scene.schema.json`;
**Aurora pins its writer-side golden against BOTH repo SHAs at landing** (this repo's and
empyrean's — SHAs to be pinned by Aurora when it cuts its parcels, aurora ROADMAP §5.2).*

*Placement note: the sprite-export ruling's own consumer contract is booked but not yet
landed (verified 2026-08-22 — no field-list artifact exists in the tree; the booking at
`docs/DEFERRED_WORK.md:112-136` is the ruling). This file therefore follows the ruling's
TEXT — the field list lands beside the generators, in `tools/` — and is the first of its
kind; the sprite consumer contract should mirror this placement when it lands.*

Two consumers, two maturity levels:

| Consumer | Status | Read set |
|---|---|---|
| `tools/inject_editor_bg.py` | **EXISTS, shipped** | §1 — OBSERVED, with code citations |
| `tools/effects_gen.py` | **BUILT AND WIRED** 2026-08-22 (scanline-services P5, slices 1-5; the module it emits is `games/sonic4/data/generated/ojz/act1/effects_scenes.emp` and `act_descriptor.emp` imports its two bindings) | §2 — NORMATIVE; the implementation reads exactly this and nothing more |

**⚠ THIS DOCUMENT ENUMERATES FIELD *NAMES*. THE EMPYREAN SCHEMA OWNS THEIR *VALUES*.**
Adopted as a standing rule in both directions, 2026-08-22, jointly with the Aurora lane —
and it is here because reading this file as if it settled values has **already shipped two
defects**. P5 slices 1-2 were written from this document with their values inferred, and
both inferences were wrong: the absent spelling is the string `"none"`, **not JSON null**
(so slice 2 would have refused every real Aurora scene), and `precision` / `transition` /
`left_column_mask` are **lowercase enum strings** needing `.emp` constants (slice 2 emitted
`precision: line`). One cause, not two.

What makes this trap sharp rather than careless: a name enumeration is *exactly* the shape
that makes inferring the value feel legitimate — the field is right there, named, in a
document titled "contract", and nothing about reading a type off it announces itself as a
guess. **If you are about to write a literal value while holding only this file, stop and
read the sibling repo**: `empyrean/docs/AURORA_EFFECTS_SCHEMA.md` and
`empyrean/contract/schema/aurora-effects-scene.schema.json`. Read them at a **committed
revision** (`git -C ../empyrean show origin/main:<path>`), never through the working-tree
path — that directory is another session's live tree and may be mid-edit.

**The drift rule (both directions):** the consumer may read exactly the fields listed
here. Adding a read of a new field, changing a default, or tightening a constraint is a
CONTRACT change: it amends this file + the empyrean schema pair in the same change series,
and Aurora re-pins its golden. A change to what the generator *emits* (`.emp` shape,
generated symbol names, `data/generated/**`) that does not alter what it *reads* is
aeon-internal and touches nothing here (format-boundary ruling, 2026-08-20).

---

## 1. `tools/inject_editor_bg.py` — read set (OBSERVED at `08f01b73`)

Input file: `games/sonic4/data/editor_bg_override.json` (path fixed at
`inject_editor_bg.py:56`).

### 1.1 Top-level keys read

| Key | Line(s) | Required | Read as |
|---|---|---|---|
| `layout` | `:61`, `:162-181` | yes | 2048 (legacy, zero-padded to 64 rows) or 4096 nametable words |
| `tiles` | `:61`, `:165`, `:185-199` | yes | list of 64-px tiles; `len(tiles) <= BG_TILE_CAPACITY` (448, imported from the vram_map mirror `:24`) |
| `anims` | `:70` | no | list of band objects (§1.2); absent/empty → the disabled stub (`band_count = 0`) |
| `anim` | `:71-72` | no | LEGACY single-band form, wrapped to `[anim]` only when `anims` is absent. **Writers must not emit it** (read-side compatibility only) |
| `palette` | `:206-221` | no | exactly 16 CRAM words, stamped into `ojz_palette.bin` |
| `palette_line` | `:207` | no (default 2) | CRAM line 1..3 (`file_line = cram_line - 1` must be ≥ 0, `:213-214`) |

No other top-level key is read. (Aurora already owns `layout`/`tiles` via the BG override
path; wave 1 adds `anims` authoring — see the wave-1 design doc.)

### 1.2 Per-band keys read (each element of `anims`)

Band ceiling: `len(anims) <= BGANIM_MAX_BANDS` (= 4, `:53`, `:74` — one of THREE
deliberate authorities drift-gated by `tools/test_bg_emit.py::TestBgAnimBandCeiling`;
raising it is a three-file engine change, never a writer decision).

| Key | Line(s) | Required | Read as / constraint |
|---|---|---|---|
| `cols` | `:85` | yes | band width in tiles; on a **vertical** band `cols * 32` is the rotation unit and must be a power of two |
| `rows` | `:85` | yes | band height in tiles; on a **horizontal** band `rows * 32` is the rotation unit and must be a power of two |
| `axis` | `band_axis_geometry` | no (default `"horizontal"`) | `"horizontal"` or `"vertical"` — which way the band's pattern translates. Any other value is refused by name. **NOT the same thing as `driver`**, which names the SCALAR the step is read from and never an axis |
| `pattern_px` | `:87`, `:91` | yes | the pattern period **along the axis**: `cols * 8` horizontal, `rows * 8` vertical |
| `driver` | `:105-106` | no (default `"camera_x"`) | one of `camera_x` / `camera_y` / `timer` (`DRIVERS`, `:69`) |
| `rate_shift` | `:107` | no (default 2) | 1 px of pattern motion per `1 << rate_shift` driver units |
| `slot_base` | `:92-93` | no (default = running cursor) | if present MUST equal the running cursor — bands pack contiguously from slot 0 in list order |
| `phases` | `:96-97`, `:127-128` | yes | exactly **8** banks; each bank exactly `cols*rows` tiles; each tile 64 pixel values (low nibble kept, `:101-103`) |
| `default_off` | `views_emitted`, `:339-358` | no (default absent = false) | **NOT a view toggle — it silences the band in the RELEASE ROM.** A band carrying it is not counted into `BgAnim_Table`, so a single-band act emits `count = 0` and the system is off at boot in EVERY shape. Two hard refusals plus a release-shape consequence: see the `default_off` subsection below |

Derived, not read: `step_mask` (= `pattern_px - 1`), `col_shift`, `tile_count`,
`bank_offsets`. Writers must not emit them; the consumer ignores unknown keys today, but
the drift rule above governs — do not rely on ignored keys staying ignored.

#### `default_off` — a SHIPPED-BEHAVIOUR switch that reads like a preview setting (added 2026-09-06T11:51:06Z)

**Supplied because the aurora lane found this key in our shipped document, could find no rule
describing it, and correctly declined to model it from its name and its round-trip behaviour.**
The rule existed and was enforced — as an `AssertionError` in `tools/inject_editor_bg.py` — but
it lived only there, which is to say **nowhere a consumer can read**. That is the class: not a
stale value in a vendored copy, but a constraint that was never in the copy at all, and it is
invisible to a per-line check of the consumer's file (which cannot find what is absent) and to a
currency gate over values (because it is not a value).

**⚠ THE ASK WAS SUPERSEDED A DAY LATER AND THE MECHANISM ALREADY IMPLEMENTS THE NEWER SHAPE —
`default_off` IS NOT MOOT IN IT, IT IS THE OFF HALF OF IT** (recorded 2026-09-06T11:56:47Z; the owner's later words
read firsthand out of empyrean `origin/main:docs/OVERSEER-LOG.md` at 2026-09-04T19:14:26Z, not
from a relay).

His correction of his own request, verbatim: *"I just ddidn't want the experimental animation
bands right now for this, they showed we can do horizontal and vertical movement on a timer, but
it was on for every test and distracting. It should be its own scene with start + button and
should be tested for perspective vs timer, that's all"*.

**That shape is BUILT** (`games/sonic4/test/ojz_scroll_test.emp:2379`, `Debug_BgAnimViewHotkey`):
**START held + C pressed**, no direction held, steps OFF -> horizontal (Camera_X) -> vertical
(Camera_Y) -> TIMER -> the vertical-axis probe -> its control -> OFF. The chord moved from C+A to
START+C *because he asked for START+button*, and the timer arm was restored because *"tested for
perspective vs timer"* is a COMPARISON that the previous parcel had left only one arm of.

**AND THE PART A READER MUST NOT GET WRONG: the hub's relay of that ruling reads "the
`default_off` flag question is moot in that shape" — marked as the hub's reading, not his words —
and acting on it would break the shipped behaviour.** In the built shape `default_off` is what
makes the bands OFF in every other scene, at zero cost: the act boots silent in every shape
INCLUDING RELEASE because the emitter writes `BgAnim_Table: u16 = 0`, so `BgAnim_Update` walks a
zero-count table and returns — no code, no flag, no chord. The chord supplies the *"its own scene
with start + button"* and *"perspective vs timer"* halves; **`default_off` supplies the *"not on
for every test"* half, and nothing else does.** Drop it and the distracting bands return to the
release ROM, which is the request that started this.

**READ THIS FIRST, ahead of either obligation, and put it in author-facing copy before either:
`default_off` changes what SHIPS.** Its origin is an owner ask of 2026-09-03 — *"can we please
just get rid of the animated tiles for now, they're so distracting? Maybe have one view for
horizontal and one for vertical?"* — and that second sentence is exactly the phrasing an editor
would render as a preview control. It is not one. A band marked `default_off` is not counted into
the act's own `BgAnim_Table`, so a single-band act emits `count = 0` and the whole system is off
at boot **in every shape, release included** (`games/sonic4/config/ram.emp:357` states it in those
words), with no runtime flag, no engine gate and no cost. **An author flipping this in an editor
is changing shipped behaviour while believing they are changing what they see.**

**AND THE TWINS CANNOT SUBSTITUTE FOR IT — a correction to a reading that nearly reached the owner
(2026-09-06).** The ask had three parts and each mechanism serves a different one: `default_off`
is the *"get rid of them"* half, the H and V twins are the *"one view for horizontal and one for
vertical"* half, and the T twin is *"perspective related instead of just timer"*. **The twins
cannot cover the first, as a matter of EMISSION rather than of policy:** every twin is
`if DEBUG == 1 { … } else { [] }` (`games/sonic4/data/generated/ojz/act1/bg_anim.emp:19-23`) and
`BgAnim_SetTable` is DEBUG-only, so the plain shape has no selector and permanently walks
`BgAnim_Table`. In the shipped ROM there is no twin and exactly one table. **`default_off` is
currently the only mechanism that stops these tiles animating in the game as played.** Read the
other way — *"the twins already do that, so drop `default_off`"* — the conclusion puts the
distracting tiles back in the release ROM, which is the reverse of the request that created it.

What it buys in exchange, and why it is not simply a delete: the emitter writes three DEBUG-only
view twins over the same bank blob — `BgAnim_View_H` (the authored band, driven off `Camera_X`),
`BgAnim_View_V` (re-driven off `Camera_Y`), and `BgAnim_View_T` (off `Logic_Tick`) — so
"perspective versus timer" is a comparison a reviewer can actually make.

**THE TWO WRITER OBLIGATIONS. Both are `AssertionError`, not warnings, and both fire at BUILD
time with no editor-side signal.**

1. **The ACT must have exactly ONE band — not "all bands agree".** If any band carries
   `default_off` and `len(anims) != 1`, the emitter refuses: the view twins exist for the effects
   lab, which drives one band, and a multi-band act would need a view table per band plus a
   selector naming both. **⚠ THE QUANTIFIER IS THE TRAP, and it was the aurora lane who named it:
   the constraint is on the ACT'S BAND COUNT, not on how many bands carry the key.** A per-key
   validator naturally checks *"is `default_off` consistent across the bands"* and **passes a
   two-band act that this build refuses.** Model it against `len(anims)`, or not at all.
2. **`pattern_px` must equal `BGANIM_VIEW_DERIVED_PERIOD_PX` (= 64).** `BGANIM_VIEW_V_RATE_SHIFT`
   (= 2) was derived against a 64 px period — one full cycle being roughly one screen height of
   vertical camera travel. Any other period **refuses rather than silently giving a different
   cadence**, deliberately, so the derivation comment cannot go on claiming a number it no longer
   earned. Re-deriving the rung for another period means moving `BGANIM_VIEW_DERIVED_PERIOD_PX`
   with it, which is an engine-side decision and not a writer's.

**Measured on the shipped document (2026-09-06):** 1 band, `default_off` true, `pattern_px` 64,
`views_emitted()` returns 3. Both obligations satisfied — **which is exactly why neither refusal
has ever fired, and why nothing surfaced this key until a consumer went looking.**

**A NOTE ON WHAT A CLEAN ROUND-TRIP DOES NOT PROVE.** Aurora reported that they parse this key
with zero notices, validate clean, and write it back unchanged. That is true and it is not
safety: it holds only because an author cannot currently CREATE or CHANGE the key, so the
consumer is PRESERVING rather than VALIDATING. The day a writer exposes it, that writer can emit
a document this build refuses — **the permissive-guard direction, failing by blaming the build.**

#### `axis` — three writer obligations the consumer CANNOT check (added 2026-09-02)

The engine was always axis-agnostic (`bg_anim.emp`'s header block is the authority):
`col_shift` is log2 of the rotation UNIT in bytes and `step_mask` is the period in px
minus 1, and the vertical arm reuses the same whole-unit DMA rotate with no engine byte
changed. That makes `axis` cheap to add and it also means **the axis is a declaration
about art, and three of the four things that have to be true for it are the writer's.**

1. **Slot order inside the band.** Horizontal wants column-major (slot `base + c*rows + r`
   at band cell `(c, r)`); vertical wants **row-major** (`base + r*cols + c`). It lives in
   `layout`, and the same slots read as a scroll under one order and as a shimmer under
   the other. The consumer cannot tell them apart — a band's slots are deduped against the
   static blob and appear at many cells — so nothing checks this.
   **⚠ AND A TEST OVER THE SET OF SLOTS CANNOT DISCHARGE THIS OBLIGATION** (the aurora lane's
   formulation, 2026-09-03, written while briefing an agent against this section — theirs is
   sharper than the paragraph above, which says the obligation exists without saying which
   shape of test fails to meet it). Column-major and row-major emission produce **the same
   slots**; they differ only in ORDER. So an assertion over the set, the count, a sorted list,
   or a checksum **passes under both orderings and reads as coverage while asserting nothing
   about the obligation.** Discharge it by asserting the ORDER at named positions, derived from
   `base + r*cols + c` (vertical) and `base + c*rows + r` (horizontal) — for example the slots
   at band cells `(1,0)` and `(0,1)`, **which are the two the orderings first disagree about**.
   That last clause is the operative one: naming which cells disagree first turns "assert the
   order" into something a writer can act on without re-deriving the formula.
2. **The eight phases must be translations along the declared axis.** One narrow case IS
   refused: a vertical band whose phases are exact HORIZONTAL translations of phase 0 and
   are not also vertical ones. That is the reachable accident — a horizontal-only
   shift-fill (aurora ROADMAP row 55: the column-wise twin is costed, **not built**) run
   over a band someone declared vertical, which bakes clean and ships a shimmer. Anything
   else is admitted, deliberately: the shipped horizontal bands are composites rather than
   pure rolls, and demanding rolls would outlaw the same technique on the new axis before
   anyone has used it.
   **⚠ THE CHECK WAS NARROWER THAN THIS SENTENCE PROMISED, AND THE GAP WAS MEASURED — CLOSED
   2026-09-03.** The measurement and the lesson are kept because both stay useful; only the
   verdict table has moved. Found by the aurora lane against a materialised copy of this tree
   with a control, and closed the same day. `validate_band_phase_axis` **additionally required
   column-major slots**, because `_band_pixels` decoded every bank column-major unconditionally.
   On a **row-major** band — which is what `axis: "vertical"` requires, obligation 1 above — it
   therefore assembled a permutation of the real picture, a true x-roll was no longer an x-roll
   in the decoded grid, and the guard **stopped firing on exactly the case it exists to refuse**.
   One band, `cols=2 rows=2`, base picture `(x*7 + y*13) % 15 + 1`, eight phases that are exact
   x-rolls of phase 0, the two arms differing **only in slot order**:
   ```
                                          BEFORE      AFTER (today)
   column-major slots + x-rolled phases   REFUSED     ADMITTED
   row-major    slots + x-rolled phases   ADMITTED    REFUSED     <- the case the guard is for
   ```
   **The sentence above is conditioned on the PHASES alone; the code used to be conditioned on
   phases AND slot order, and now is not.** `_band_pixels` takes the band's declared `axis` and
   decodes row-major for vertical, column-major for horizontal, so the guard sees the real
   picture. A writer may now rely on the sentence as written.
   **The verdicts SWAPPED rather than both becoming refusals, and that is deliberate.** A band
   that declares `vertical` and emits column-major slots is broken in **obligation 1**, which is
   explicitly not checkable here; the guard reads the picture the declaration says is there, and
   on such a band that picture is scrambled, so any refusal it drew would be incidental rather
   than earned. Refusing it anyway would widen the guard past obligation 2 and start outlawing
   composites, which is the thing this obligation deliberately does not do.
   **And note WHY the docstring's own argument did not protect it**, because the shape recurs:
   it said *"a consistent relabelling of the slots cannot turn a non-translation into one"* —
   which is TRUE, and rules out FALSE POSITIVES. The exposure was a FALSE NEGATIVE: a relabelling
   turns a translation INTO a non-translation. A correct sentence certifying the half nobody was
   worried about. *The population was empty at the time, so nothing ever shipped broken — the
   first vertical band anyone authors is what would have landed on it.*
   The pair above is kept permanently as two rows in `tools/test_bg_emit.py`
   (`TestBgAnimMotionAxis.test_the_guard_reads_a_vertical_band_in_ITS_OWN_slot_order` and
   `..._the_column_major_control_is_what_makes_that_row_mean_anything`); neither means anything
   alone.
3. **`axis` must survive a round trip.** A writer that loads a document, edits something
   else and saves it back must preserve the key. Dropping it silently reverts the band to
   horizontal, and the guard in (2) cannot see a band that no longer claims to be vertical.

**Direction is fixed and is not a key.** Bank `k` is phase 0 moved `k` px toward
decreasing coordinate and the coarse rotate carries the same sign, so an increasing
driver scrolls a horizontal band LEFT and a vertical band UP. A `direction` key would be
an engine change (reverse the step on its ring) and is booked in `docs/DEFERRED_WORK.md`,
not built.

Output contract (aeon-internal, cited for orientation only): 44-byte records LOCKSTEP
with `engine/level/bg_anim.emp` `struct bganim_band` (**`bg_anim.emp:66`**, its width held
by `ensure(sizeof(bganim_band) == 44, …)` at `bg_anim.emp:75` — that ensure, not this
sentence, is the authority); the animated arm is
FORMAT-FAITHFUL BUT NOT BYTE-PROVEN until the first authored act (`:121-124`) — that
discharge is a wave-1 aeon lane item.

## 2. `tools/effects_gen.py` — normative read set (build-to; P5)

This section is the NORMATIVE read set `effects_gen.py` is built to. It was enumerated
BEFORE the generator existed, so that Aurora's writer golden and the generator would be
written against the same list rather than the consumer growing ad-hoc readers (the exact
failure the sprite-export ruling names). The status table at the top of this file is the
authority on whether the generator exists; do not restate it here.

*⚠ A sentence stood here from before the generator landed — "`effects_gen.py` does not
exist yet" — while the table at the top of this same file said BUILT AND WIRED. **One
document asserted both, and the Aurora lane quoted the wrong half for eight days**, which
is where a false claim in their manual came from. Deleted rather than re-stated: a fresh
"it exists now" would go stale on the identical clock, and a status that lives in two places
will disagree again. Found by the Aurora lane, 2026-08-30.*

### 2.1 Scene definition files

`games/sonic4/data/editor/effects/<scene_id>.json` — one scene per file; an absent
directory means "no editor scenes" (not an error). The generator reads exactly the wave-1
normative surface of `empyrean/docs/AURORA_EFFECTS_SCHEMA.md` §2, which mirrors the scene
DSL constructor arguments 1:1 (`engine/level/scene_dsl.emp` `scene()`/`layer()`):

- Top level: `schema` (refuse ≠ 1), `id` (refuse ≠ filename stem or bad pattern),
  `layers`, `v_factor`, `v_center`, `v_offset`, `v_factor_fg`, `deform_fg`, `deform_bg`,
  `v_deform`, `reels`, `anchor`, `left_column_mask`, `transition`, `budget_class`
  (passthrough, unvalidated — sigil is the validator).
- **`left_column_mask` gained a fifth value, `decline_borrow` (owner ruling `d-50`,
  2026-09-02).** It is the only value of this key that changes emitted bytes: it ORs $80
  into `pcfg_v_deform_shift_bg` and makes the engine skip the column-19 borrow on that
  scene, trading the foreground's leading sliver back for the background's two edges.
  `tools/effects_gen.py` accepts it today. **The editor half is Aurora's + empyrean's and
  is NOT built**: the schema's enum, the `scene-ui` control, and whatever the editor shows
  an author so the trade is legible rather than a fifth word in a dropdown. Until that
  lands the value is only reachable from hand-authored `.emp`, which is where the two
  shipped adopters (`Scene_Perspective_Subtle`, `Scene_Perspective`) spell it.
- **`precision` — ACCEPTED AND IGNORED (engine-side RETIRED 2026-08-26, owner ruling
  `d-29-corrected`).** The per-cell HScroll path the field chose between was deleted; the
  fill is per-line for every scene and `scene()` no longer takes the argument. The
  empyrean schema (wave 1, `cell` only) still spells it, so the generator does not refuse
  a file that carries it — it drops the key, whatever the value. Removing the field from
  the schema and from Aurora's `scene-ui` is **Aurora's + empyrean's**, booked in
  `docs/DEFERRED_WORK.md` ("Per-cell HScroll fill — DELETED"); when it lands, the key
  moves from the generator's ignored set to its refused set.
- Per layer: `world_y`, `fa`, `fb`, `dsa`, `dsb`, `phase`, `enabled`, `deform`, `curve`,
  `vsplit`, `drift`, `rowRemap`.
- **`drift` — READ SINCE 2026-09-02 (this amendment; contract change per the drift rule
  above).** Wire form `"none"` / absent / `{"rate": <signed int>}`; lowers to
  `layer(drift: SceneDrift.Rate(<rate>))`, and absent lowers to the argument being
  omitted (`SceneDrift.None` is `layer()`'s default). **`rate` IS IN THE ENGINE'S UNIT ON
  THE WIRE: 1/256 px per FRAME, signed** — 1 px/frame is `256`, S3K AIZ1's clouds are
  `32`, the shipped OJZ canopy is `-32`. The px/frame presentation the design asks for
  (`docs/superpowers/specs/2026-08-29-band-drift-design.md` §7.1 mitigation 2) is
  **Aurora's UI, multiplied by 256 on export**; the generator applies no conversion, so a
  writer that exports px/frame unscaled is 256x slow and one that scales twice is 256x
  fast. Bounds `-4096 … +4096` and the refusal of `0` are `layer()`'s two `ensure`s in
  `engine/level/scene_dsl.emp` and are NOT re-checked here, per design §7 row 10 — the
  generator's shape check only requires an integer. This key is only authorable in a game
  whose `SCANLINE_CAPS` raise `CAP_BAND_DRIFT` (`$0080`); in one that does not, the
  scene-registry gate in `games/sonic4/data/effects/scene_registry.emp` refuses the fold
  at build time with its own message. Writer half: empyrean
  `contract/schema/aurora-effects-scene.schema.json` `$defs.layer.drift`, already landed
  at empyrean `041e5e8` — **its description's closing clause ("until then
  `effects_gen.py` refuses the key") is stale as of this amendment and is empyrean's to
  cut.**
- **`rowRemap` — READ SINCE 2026-09-04 (this amendment; contract change per the drift rule
  above).** EFFECTS-W1 item 9's row remap: this layer's plane-B scroll words are re-fetched
  through a perspective-selected index ladder. Wire form `"none"` / absent /
  `{"plane_y": <int>, "height_shift": <int>}` — the payload is **FLAT and spells no variant
  tag**, exactly as `drift`/`vsplit`/`curve` spell no `SceneDrift.Rate`/`SceneVSplit.At`/
  `SceneCurve.To`. Lowers to
  `layer(rowRemap: SceneRemap.Ladder(RowRemapLadder_Waterline16, <plane_y>, <height_shift>))`;
  absent **and** `"none"` both lower to the argument being omitted (`SceneRemap.None` is
  `layer()`'s default, and a NULL `brm_ladder` is the per-band gate, so the two are the same
  eight bytes).
  - **BOTH NUMBERS ARE 1:1, VERBATIM, WITH NO UNIT CONVERSION**, the standing rule on this
    seam. `plane_y` is a **PLANE-B LINE, 0..511** — not a world Y and not a screen line; the
    runtime's only use of it is `plane_y - Vscroll_BG`, a subtraction whose second term is a
    per-frame runtime quantity, so no editor arithmetic can improve it.
  - **`height_shift` IS A SHIFT, NOT A LINE COUNT: `H = 1 << height_shift`.** This is where a
    helpful editor does the most damage — presenting "band height = 16 lines" and exporting
    `16` asks for H = 65536. **The editor may DISPLAY `1 << height_shift`; it must EXPORT the
    shift.** Every value 3..7 is legal to `layer()`, so a conversion bug inside that window
    lands as a band four times too tall rather than as a refusal.
  - **THE LADDER IS DERIVED FROM `height_shift`, NEVER NAMED.** `ladder` and `table` are
    **reserved names, refused BY NAME** (`LAYER_REFUSED_KEYS`): exactly one ladder exists,
    `row_remap_ladder16()` (`engine/level/parallax_dsl.emp:220`), whose H is the module const
    `ROW_REMAP_H16 = 16` rather than a parameter, so naming it would be one number spelled
    twice. A named ladder is the **second-variant** extension when a non-perspective ladder
    is wanted (heat haze, a mirror); a `oneOf` can widen where a required field cannot be
    taken back.
  - **⚠ TODAY ONLY `height_shift: 4` BUILDS.** `layer()` accepts 3..7
    (`engine/level/scene_dsl.emp:1006`), but 3/5/6/7 have no generated ladder, so the
    generator refuses them **by name** — the alternative is an emission that fails on an
    undefined Label and names a missing symbol instead of the thing the author wrote. The
    generated ladder for the other four shifts is EFFECTS-W1 item **9b**.
  - `plane_y`'s bounds are `layer()`'s two `ensure`s (`scene_dsl.emp:1008` for `>= 0`,
    `:1017` for the `< 512` ceiling added 2026-09-04 — before that the upper bound was PROSE
    and `brm_plane_y` is a `u16`, so 512..65535 was silently a wrong window). Not re-checked
    here, per the same rule as `drift`. This key is only authorable in a game whose
    `SCANLINE_CAPS` raise `CAP_ROW_REMAP` (`$0800`). **AT MOST ONE LAYER PER SCENE** may
    carry it, and `scene()` additionally requires the scene to have an `anchor:` and
    something to vary — all three are `scene()` refusals, not schema ones. Writer half:
    empyrean `contract/schema/aurora-effects-scene.schema.json` `$defs.layer.rowRemap`, key
    shape filed by `docs/superpowers/specs/2026-09-04-item9-row-remap-key-shape.md`.
- **`reels` — READ SINCE 2026-09-04 (this amendment; contract change per the drift rule
  above). DEBUG TIER: it moves DEBUG-shape ROM bytes and ZERO release bytes.** EFFECTS-W1
  item 10's authoring half; the ratified writer half is empyrean
  `docs/AURORA_EFFECTS_SCHEMA.md` §2.7 at `ff3f43f2e9c2b0b98e6c283f5cb87eb106f0fe5c`. Wire
  form `{"rates": [<int> x REEL_BAND_COUNT]}`, a CLOSED object, absent = no reels; there is
  **no `"none"` spelling** (CR ruling 2 — the binding table is generated whole, so "keep"
  and "off" are one state). It is a SCENE key and not a layer key: a reel band is one of
  five vertical COLUMN strips while `band_record` partitions the screen into horizontal ROW
  bands, and the two share a noun and nothing else.
  - **A RATE IS SIGNED WHOLE PIXELS PER FRAME, 1:1, AND THE x256 CONVERSION MUST NOT
    HAPPEN.** `add.b (a2)+, d0` puts the authored byte straight into the strip's phase;
    there is no fixed point on this path. `drift.rate` two bullets up is 1/256 px per frame
    with the editor multiplying by 256 on export — **a reels panel built by copying the
    drift panel's export path emits 768 for an intended 3.** The engine's guard is
    `reel_rates_ok`'s magnitude `ensure` (`games/sonic4/config/constants.emp`), added by the
    same parcel as this amendment because before it NOTHING bounded a single rate.
    **The CR's ruling (6) says the schema bound is "the only artifact in the chain that
    catches it today"; that is REFUTED by measurement** (2026-09-04, sigil `0a58f2ec`): a
    768 authored here also draws `[emit.out-of-range] 768 does not fit i8 (-128..=127)`,
    so sigil refuses rather than silently narrowing — which is the same question the CR
    lists as still open two paragraphs later. What sigil's diagnostic does not carry is
    the CAUSE: it names a slot, not a unit. `reel_rates_ok`'s ensure fires first and says
    which.
  - **DOCUMENT ORDER IS SCREEN ORDER.** Index *i* owns column-pairs 4*i*..4*i*+3, screen X
    64*i*..64*i*+63; the map is a hardcoded `lsr.b #2` in `OJZ_Reels_Fill` that no JSON can
    see. The generator emits the array verbatim; an editor that sorts, reverses, or
    round-trips it through a dict keyed by band name silently relocates every strip.
  - **THE LENGTH IS `REEL_BAND_COUNT`, RE-DERIVED, NOT 5.** The schema's `minItems`/
    `maxItems` is a copy of `games/sonic4/config/constants.emp`'s constant in another repo;
    the generator parses that declaration and refuses a disagreeing length naming both
    numbers. `cols_per_band` is **refused by closure**: the geometry is fixed at
    REEL_BAND_COUNT x REEL_COLS_PER_BAND because the column->band map is a compiled shift,
    not a value read at runtime (CR ruling 5). It is recoverable additively later.
  - **THE KEY IS LEGAL ONLY ON A SECTION BOUND AT RUNG 1** — `Sec.sec_parallax_config`, i.e.
    a `sceneRef` sidecar. The generated binding is keyed on `Parallax_Current_Config`, and
    that pointer is unique only at rung 1; a section resolving through a preset
    (`EffectsPreset.ep_parallax`, rung 2, shared by every section naming that preset) or the
    act default (rung 3) holds a SHARED pointer, so the table would hand it **another
    section's motion** rather than none. The generator REFUSES all three cases by name — the
    scene is the act default, no section binds it at rung 1, or a hand `preset(.. parallax:
    ..)` also names its lowered record. Values (magnitude, pairwise distinctness) are
    `reel_rates_ok`'s ensures and are NOT re-checked here, the same rule as `drift`.
  - **Not expressible in the schema, so said here:** the effect reaches only the DEBUG
    build shape (nothing in a release ROM can set `OJZ_Reel_Active`), the FOREGROUND is
    untouched by construction, and the excursion is 0..255 px BELOW the camera's BG base —
    always downward, with a negative rate reversing travel rather than lifting the strip.
- Inside attachments: the factor spelling (named `FACTOR_*` or `{s1,s2,op}`) and the
  `tableRef` forms (`generator`: `sine`/`triangle`/`zero`/`v_column_perspective`/
  `v_column_floor` with their parameters, or `bin`).
- **NOT read** (excluded from the JSON surface, empyrean schema §2.1): `layer_mask_raw`,
  `v_deform_shift_raw` (byte-identity bridges for hand-migrated scenes; editor scenes
  derive), `name` (writer-owned display label — the generator ignores it and MUST keep
  ignoring it; it is the one deliberate writer-only field).

Validation posture (scanline design §7, restated): the generator validates SHAPE
(schema/id/unknown keys — refuse, don't guess); authored VALUES are validated by sigil
when the generated `.emp` calls the constructors — raw ensure text is the v1 error
surface.

### 2.1b THE RIGHT-EDGE RULE — a scene using per-column mode owes its background's rightmost 16 px (owner ruling 2026-08-29, d-41)

**Read this before authoring a per-column scene. It is a constraint on ART, not on the file
format, so nothing in this contract can assert it and no build gate will catch you.**

The engine repairs the leftmost partial column — the sliver the V-scroll grain leaves at
x 0..15 — by **borrowing column-pair 19**, the rightmost one, and writing the FOREGROUND's
V-scroll into it. On a per-column scene plane B is vertically locked, so after the borrow
those rightmost 16 pixels show **the background at the camera's height instead of its own**.
That is the price, it is permanent while the borrow is on, and the owner has seen it running
and accepted it.

**THE RULE: any scene that uses per-column mode must make the background's rightmost 16 px
tolerate carrying the foreground's scroll.** Two ways, both with precedent:

- **Make the borrowed slot correct by construction.** *Cutie Suzuki no Ringside Angel* lays its
  VSRAM out so the borrowed column is the one that should carry that value anyway — the seam
  costs nothing because the art was designed around it (SpritesMind thread t=737).
- **Cover it.** *Battle Mania 2* hides the equivalent strip behind foreground art. If the
  rightmost 16 px are never background-critical in your scene, the seam is invisible.

The cheap general form: **a neutral strip at the right edge** — sky, a flat gradient, anything
whose vertical position is not readable — costs nothing and makes the scene immune.

**A per-scene switch to disable the borrow is NOT built and is deliberately not built.** It is
booked in `docs/DEFERRED_WORK.md` as **revival on the first real instance**: the first scene
whose art genuinely cannot satisfy this rule is the evidence that earns the switch. Do not
build it speculatively — the owner's words were *"revisit if it actually comes into play"*.

**What the build DOES still tell you:** `scene()`'s `Factor0Lock` guards now say in their own
message that the engine repairs the sliver either way, so `Factor0Lock` asserts only that a
scene never HAD one — **it does not exempt a scene from the borrow's right-edge cost.** That is
a note in an error you may never see, which is exactly why the rule is written here as well.

### 2.2 Assignments

- `games/sonic4/data/editor/ojz/act1/section_N.meta.json` (per act's `dataPath`): the
  generator reads **two keys**: `sceneRef` — string scene id or `null`/absent (= act
  default) — and `rasterRef` (below). It does not read `bgLayoutRef`/`paletteRef` (those
  belong to the BG/palette pipeline). **Write condition and round-trip (contract-level; ERRATUM 1 of
  `docs/research/2026-08-22-aurora-effects-authoring-assessment.md`, verified firsthand
  in aurora source at master `e731214` and independently re-verified):** the sidecar is
  written only when at least one ref is non-null — the all-default case legitimately has
  **no sidecar file on disk**, and the generator MUST treat a missing sidecar as
  all-refs-null, never as an error; when all refs are cleared but a file exists, Aurora
  overwrites it with an explicit all-nulls body (aurora
  `src/core/project/aeon/save.ts:118-126`). **`sceneRef` is a string id or null, NEVER a
  numeric index** — stated in exactly these words because the parser's failure mode for
  a non-string value is a **silent null, not a loud reject**
  (`src/core/formats/section-meta.ts:29-30` guards with `typeof x === 'string'`): a
  numeric scene index like `sceneRef: 3` is read as null by a fully sceneRef-aware
  Aurora and then erased on the next save, presenting as "the assignment didn't stick" —
  do not later "helpfully" switch this field to an integer index. **Round-trip hazard
  the golden pins — READ THE METHOD, NOT THE NUMBER.** Empyrean's schema doc defers to this
  paragraph as the governing enumeration, so it states how to re-derive the list rather than
  freezing a count: **counts in prose rot** (empyrean's own doc had drifted to "four" in one
  section and "six" in another within five days, and this contract said six when the answer was
  thirteen).

  **Definition of a "site":** a place that hardcodes the ref SET — i.e. that must be edited when a
  ref is added — not every mention of a ref name. **Re-derivation (protocol review bar 8,
  empyrean `dc629a5`): enumerate by what TOUCHES the record, not by what defines it** — grep the
  TYPE and every constructor/copier of `Section`/`SectionMeta`, not the field names in their
  owning module. `grep -rn "bgLayoutRef\|paletteRef\|sceneRef" src` in aurora is the start, but
  the codec frame is the trap: two overseers independently enumerated it, cross-verified
  firsthand, and both got the same wrong answer.

  **Dated evidence, not a standing fact:** the authoritative enumeration is Aurora's first wave-1
  parcel (aurora `61d4b80`), which found **13** by editing against the real type with tests —
  supersede this number by re-deriving, never by copying it forward. Of those, the three the
  codec frame MISSED — **line numbers verified firsthand at aurora `fb8f8f0` and re-confirmed at
  `70ed4c2`** (their tip moved twice during this write; if these cites miss, re-derive by the
  method above rather than trusting them, and note that this doc is the GOVERNING cite — a doc
  that merely restates these line numbers is the count-in-prose failure in different clothes):
  `src/core/editing/section-ops.ts:30` (`cloneSection` hand-enumerating every ref in a bare
  literal — **it was UNGUARDED; dropping a ref survived a 3,909-test suite**), a SECOND
  independent ref literal in the save path at `save.ts:131` distinct from the cleared-overwrite
  body (now at `:144`, and note it already carries `sceneRef: null`), and the `Section` type
  itself. The six below are the CODEC FRAME ONLY — historically what this contract listed, kept
  because the round-trip hazard is explained there. Codec frame — four
  executable (`section-meta.ts:21`, `:22`, `:29-30` — unknown keys silently DROPPED,
  non-string known keys nulled — and the cleared-overwrite body at `save.ts:118-126`)
  plus the header-comment enumeration (`:5-9`) and the `SectionMeta` interface
  (`:11-14`) — so a `sceneRef` written by anything other than a sceneRef-aware Aurora is
  silently erased on Aurora's next save round-trip. The `SectionMeta` extension edits
  every site — re-derived, not the six — in the same Aurora parcel as the first writer, and parse→serialize
  preservation of `sceneRef` is a **named contract requirement** (empyrean schema doc
  §3/§6/§8), not an implementation detail. **Unreadable sidecars — the obligation is
  SHARED** (ERRATUM 2, `5be97277`, superseding an earlier consumer-side-only framing):
  Aurora's meta path is silently destructive TODAY (bare catch at `load.ts:322-329` +
  the cleared-overwrite at `save.ts:123` turn a malformed sidecar into a well-formed
  empty one — a live data-loss defect); Aurora's half of the fix is `markUnreadable` +
  `understood('meta.json')` gating including the cleared-overwrite literal. The
  generator's half: (a) WRITE atomically (reuse `_atomic_write`,
  `tools/ojz_block_gen.py:201-206` — §3) so a partial sidecar is never observable;
  (b) READ with the missing/unreadable split intact — a MISSING
  sidecar is all-refs-null, an UNREADABLE one **fails the bake loudly**; "degrade
  gracefully" must NOT mean "treat as all-null", because all-null is exactly the state
  that triggers Aurora's destructive overwrite. **And stated plainly because the
  opposite expectation is the natural one:** once Aurora refuses to overwrite an
  unreadable sidecar, a generator that writes a sidecar Aurora cannot parse finds its
  file **preserved rather than repaired** — a generator bug is sticky, not
  self-healing; a human fixes the file by hand. **Sequencing precondition:** `sceneRef`
  does not land in sidecars until Aurora's meta-gating fix is on their master (fix SHA:
  **`a88db05`**, aurora master — merged, re-verified on the merged tree, pushed;
  see the wave-1 design doc §4).
- **`rasterRef` — the per-section RASTER binding (NEW, EFFECTS-W1 item 1; amends
  together with empyrean `docs/AURORA_EFFECTS_SCHEMA.md` §3.1, and per §8 the two are a
  matched set Aurora re-pins against both SHAs).** A **string preset-document id, or
  `null`, or absent — NEVER a numeric index.** The id space is the preset document's own
  (`^[a-z][a-z0-9_]{0,31}$`, matching the document's `id` and its filename stem). Absent
  == `null` == "this section keeps its hand-authored raster channel", which is the
  majority case and is why the arm costs nothing until a section uses it.

  **The shape is `sceneRef`'s in every particular, deliberately**, including the numeric
  ban and its reason: Aurora's parser nulls a non-string value **silently**
  (`section-meta.ts:29-30`), so `rasterRef: 3` presents to the author as an assignment
  that did not stick — the build is the one reader that can still see the mistake, and it
  refuses, naming the key.

  **What the generator does, normatively:** reads the key with the **missing/unreadable
  split intact** (an absent sidecar is all-refs-null and is NOT an error; a sidecar that
  exists and does not parse **fails the bake** and must never collapse to all-null);
  **refuses a non-string, non-null value by name**; **refuses an id naming no preset
  document, listing the known ids** (symmetric with the `sceneRef` resolution error);
  emits the binding as an **always-present, zero-byte `pub comptime fn` chooser**, so
  that with no `rasterRef` anywhere the generated module gains the chooser and nothing
  else and the ROM is byte-identical — checkable by CRC rather than argued. It restates
  **no numeric bound from the raster tier** (the band constructors hold those, and
  duplicating one here would be §2.1's anti-pattern), and it applies **no unknown-key
  refusal to the sidecar**, so a future Aurora key is not a build break.

  **The write condition widens.** `rasterRef` joins the ref set whose any-non-null
  triggers a sidecar write: a section whose ONLY non-null ref is `rasterRef` **must** get
  a file. All-null still writes no file, and the cleared-overwrite body carries the key.

  **Older consumers — named, and ACCEPTED rather than guarded against (ruled).** An older
  `effects_gen.py` **silently ignores** the key: green build, no band, and it presents as
  "my assignment did nothing". An older Aurora **erases** the key on its next save, by the
  same closed-`SectionMeta` mechanism as `sceneRef`'s thirteen-site hazard above. Neither
  is defended against here: an unknown-key refusal on the sidecar would make every future
  Aurora key a build break, which is the opposite of what a sidecar is for.

  **Sequencing precondition — DISCHARGED 2026-08-30.** `rasterRef` could not land in any
  sidecar until the `SectionMeta` extension carrying it was on aurora's master, because
  an older Aurora erases the key on its next save and the author's first save would
  delete their own assignment. `sceneRef` needed aurora **`a88db05`**; `rasterRef`'s
  extension is aurora master **`7b1d15a0`**, merged and verified. The ban is lifted.

  **Its site enumeration was re-derived, and MIND THE UNIT:** **thirteen SITES across five
  files**, by this section's own definition of a site (a place that hardcodes the ref
  SET), against **sixteen FILES that merely mention `sceneRef`**. Both numbers are right
  and they count different things; neither is the other.

  ⚠ **AND THE RE-DERIVATION METHOD ABOVE HAS A KNOWN HOLE — do not read it as complete.**
  Following the sibling key finds the code that HANDLES the ref set and misses the prose
  that DESCRIBES it: six further prose sites hardcode the set, and one of them
  (`PRESET_LIMITS.unbound`) is **author-facing and mentions `sceneRef` zero times**, so no
  `sceneRef`-shaped search could ever surface it. An amendment to the enumeration rule is
  booked with the hub. Until it lands, enumerate prose separately from code rather than
  trusting a search keyed on the sibling name.

  ~~**The channel it binds is `ep_raster` only** — a preset document carries a raster
  program and nothing else, so `rasterRef` is a NARROW binding.~~ **CORRECTED IN PLACE
  2026-09-02 (EFFECTS-W1 item 5, hub ruling Q1).** A preset document now carries `cycles`
  and `variants` beside `bands`, and **`rasterRef` binds the WHOLE document — every channel
  it carries.** The reason it is one key and not three: the engine binds ONE preset record
  per section, and `ep_cycle` and `ep_variants` are fields of that same record
  (`engine/effects/preset.emp`), so sibling `cycleRef` / `variantsRef` keys would let a
  section name three documents the engine has one slot to put. **`rasterRef` is therefore a
  deliberate HISTORICAL SPELLING**, from the day a preset document had only `bands`; do not
  conclude from the name that the other two channels need refs of their own. Renaming it is
  a separate CR nobody has asked for (empyrean §3.1 records the price of a key addition:
  thirteen code sites in five files plus six prose sites). empyrean §7's `effectsRef`
  stays reserved and unspent for the TOTAL binding it was named for (CR adjudication
  2026-08-30, option B) — total still needs a palette reference, and `ep_pal` is the one
  preset field with no default.
- `project.json` (repo root): per act entry, the generator reads **one key**: `sceneRef`
  — string scene id or `null`/absent (= the hand-authored engine default in
  `act_descriptor.emp` stands). The dangling `parallax` key is deleted in the same parcel
  that lands this contract's implementation (ruling Q4: one change, no interim fossil).

### 2.3 Referenced binaries

- `tableRef.bin` paths resolve relative to `games/sonic4/data/editor/effects/`, refuse
  `..` segments, and must be exactly 256 bytes (signed i8 table), baked via `embed()`
  (the `inject_editor_bg.py` precedent).

### 2.4 Preset documents — the RASTER BAND field contract (NEW, this series)

`games/sonic4/data/editor/effects/presets/<preset_id>.json` — one preset document per
file. An absent directory means "no presets" and is **not** an error.

**~~the directory does not exist in the tree today, which is why adding this read set moved
zero ROM bytes~~ — CORRECTED IN PLACE 2026-08-29, one day later.** The directory exists and
holds `authored_probe.json`, the first editor-authored raster program, and it moved all four
sonic4 ROM bytes as a preset document is designed to. The zero-byte claim was true of the
arm *without content* and is preserved above as the converse control
(`tools/test_effects_gen.py::TestPresetConverseControl`); what is no longer true is the
statement about the tree. The anti-vacuity test that guarded this sentence
(`test_the_real_repo_ships_no_preset_documents`) went red the moment content arrived,
exactly as its author intended, and is now inverted
(`test_the_real_repo_SHIPS_preset_documents`). A worked example of a real document, and the
Aurora lane's page, is `docs/EDITOR_RASTER_PRESETS.md`.

**⚠ A BAND IS NOT A SCENE FIELD, AND THIS IS THE PART TO READ BEFORE THE TABLE.** The
parcel that built this arm was dispatched to put the band on the *scene* file. It is not
there, and both reasons were already committed before the parcel started:

1. `docs/superpowers/specs/2026-08-28-raster-band-ownership-design.md` **§16.1** — "A
   scene IS a `parallax_config`. It is not an effects bundle. The palette, the palette
   cycle, the variants and *the raster program* are channels of an `EffectsPreset`, and an
   `EffectsPreset` is bound **per SECTION**, never per scene." Its closing sentence is
   addressed to exactly this reader: *"'put a band in a scene' is not a thing you can
   do."*
2. `empyrean` origin/main `docs/AURORA_EFFECTS_SCHEMA.md` **§7** already RESERVES the right
   place — `games/sonic4/data/editor/effects/presets/` ("preset composition documents"),
   for "raster preset composition (tint bands, vscroll splits, patchable world-anchor
   channels, palette variants, cycling)". Putting `bands` on the scene object would have
   contradicted a reservation the suite had already agreed.

So the editor's band panel edits a **preset document**, not a scene. A `bands` key on a
scene file is refused by the scene loader's ordinary unknown-key path (asserted:
`tools/test_effects_gen.py::TestPresetConverseControl::test_a_scene_file_carrying_a_band_key_is_REFUSED`).

**Wave-2 status.** `bands` is a NEW key, not one of §7's reserved three. Its relation to
the reserved `fires`: a band lowers to the two (or three, with `sh`) fires `band()`
derives, so `bands` is the safe, closed subset and `fires` remains the open general form.
**`variants` and `cycles` were refused by name until 2026-09-02 and are now BUILT**
(EFFECTS-W1 DoD item 5; the hub specified them in `empyrean`
`docs/AURORA_EFFECTS_SCHEMA.md` §7.2 on 2026-08-30 and ruled all ten of aeon's open
questions there). `fires` is the last reserved name and is still refused **by name** here
rather than as an unknown key.

**⚠ WHICH "CYCLE" `cycles` MEANS, SAID ONCE (hub ruling Q10).** `cycles` is **PALETTE
cycling** — the rotation of a span of CRAM entries performed by `Palette_DoCycle` and
`Palette_RotateSpan` in `engine/effects/palette.emp`. It is unrelated to the DEBUG hotkey's
**raster cycle table** (`RASTER_CYCLE_COUNT`, `tools/test_raster_cycle_table_lint.py`),
which steps a human at a controller through raster PROGRAMS. A reader of that lint must not
read this key as the same thing.

**The other two channels are `EffectsPreset` channels for the same reason `bands` is.** A
scene IS a `parallax_config`; the palette, the palette cycle, the variants and the raster
program are channels of an `EffectsPreset`, bound per SECTION (§16.1, quoted above). So all
three live in `presets/<id>.json` together, and **one `rasterRef` binds the whole document**
(ruling Q1 — see §2.2's corrected note on that key's historical spelling).

#### What one band becomes, end to end

```
{"top": 120, "bot": 148, "sh": false,
 "on": {"cram": {"addr": 74, "colours": [548]}}}
        |
        |  tools/effects_gen.py  render_band / render_band_on / render_preset
        v
band(top: 120, bot: 148, on: stream_cram(addr: 74, colours: [548]), sh: 0)
        |
        |  wrapped, per document, into one program
        v
const EditorRasterSrc_OJZ_Act1_<id> = compose([ <band>, ... ])
pub data EditorRaster_OJZ_Act1_<id>: [u16; raster_words(EditorRasterSrc_OJZ_Act1_<id>)]
                                   = raster_program(EditorRasterSrc_OJZ_Act1_<id>)
        |
        v
words in `games/sonic4/data/generated/ojz/act1/effects_scenes.emp`, section
`ojz_effects_editor_act1`, placed by the `"section:ojz_effects_editor_act1"` row in
`games/sonic4/map.toml` (a NAME row precisely because the head label is content-derived —
so a program appearing here needs no map.toml edit).
```

MEASURED, not asserted (2026-08-29, real `sigil build --native --game sonic4`, the three
bands above): `EditorRaster_OJZ_Act1_ojz_ground_wash` lands at ROM `$1323C`, and the next
label sits at `$132AA` — a span of `$6E` = **110 bytes = 55 words**, which is exactly
`raster_words` for three one-colour bands (7 fixed + 3 × 16).

#### Field table

Every row names **where the rule is enforced**, file + symbol. Where a rule has **no**
enforcing assertion, the row says so in those words rather than implying one exists.

**Legend for the enforcement column.** `effects_gen.py` symbols are the SHAPE layer (is
this a number, is this key known, is this arm spelled right); `raster_dsl.emp` symbols are
the VALUE layer (is this number legal), and they fire at build time on the generated
`.emp` because a `pub data` in a lowered module is elaborated unconditionally.

| Field | Type / range | Meaning, incl. absent / zero | Lowers to | Enforced at (file + symbol) |
|---|---|---|---|---|
| `schema` | integer, `== 1` | Document format version. **Absent: refused.** | nothing | `tools/effects_gen.py` `load_preset` |
| `id` | string, `^[a-z][a-z0-9_]{0,31}$`, `== ` filename stem | Becomes the `.emp` label component `EditorRaster_<ACT>_<id>`. **Absent: refused.** | the emitted label's name | `tools/effects_gen.py` `load_preset` (pattern `SCENE_ID_RE`) |
| `name` | any | Writer-owned display label. **Read by nothing; whatever the value, it is dropped.** | nothing | not validated anywhere — deliberately, `PRESET_IGNORED_KEYS` |
| `bands` | array, length ≥ 1 | The bands in this program. **Empty: refused** (an empty program is not a program). **Absent is refused only when no OTHER raster arm is present** — `bands`, `ramp`, `base_swap` and `boundary` are an exactly-one-of group, so a document carries exactly one of the four and a `bands`-less document is legal if it carries one of the other three. | one `compose([...])` | `tools/effects_gen.py` `load_preset`; backstop `engine/effects/raster_dsl.emp` `compose` ("compose: nothing to compose") |
| `base_swap` | array, length >= 1, of closed objects; three required members and one optional each | **READ SINCE 2026-09-03; NOT IN THE EMPYREAN SCHEMA — this generator IS the shape until that CR lands** (the item-11a booking called this half strictly smaller than a full demand artifact warrants, so the key shipped ahead of the ruling — the reverse of `ramp`'s sequence). **A LIST SINCE 2026-09-04 (EFFECTS-W1 T3; contract change per the drift rule at the top of this file) — it was a single object, and the refusal guarding that shape said "never an array of them", which was wrong about the mechanism it defended: a document carries one raster PROGRAM, and a program is a sequence of fires.** The section's mid-frame nametable-base bands: partway down the frame, re-point a scroll plane's base register at an address that already holds a valid nametable, so a band of the screen draws the other plane's map in that layer. Bands flatten into fires in document order; ordering ACROSS bands is `fire_lines`' strict-ascent ensure, not this file's. Third arm of the exactly-one-of group, exclusive for the SAME reason as `bands`/`ramp` (all three lower into `EffectsPreset.ep_raster`), NOT for `boundary`'s destructive-install reason. **Absent: no swap.** No capability bit gates it — `OP_SET_REG` dispatches unconditionally in every game — so no `ensure(Game.SCANLINE_CAPS & …)` is re-emitted at the call site, unlike `ramp`'s. The emitted program is real section content and reaches `s4.bin` as well as `s4.debug.bin`. | one or two `fire(line, [reg_set(vdp_reg(VDP_PLANE_x_OFF, vdp_base_reg(VdpBase.Planex, …)))])` PER BAND under `raster_program()`, as `pub data EditorRaster_<ACT>_<id>` | `tools/effects_gen.py` `_check_base_swap` (shape, closed keys) · `load_preset`'s exactly-one-of group · `render_base_swap_preset` (the lowering) |
| `base_swap[i].plane` | string, one of `"PlaneA"` / `"PlaneB"` | **READ SINCE 2026-09-04 (EFFECTS-W1 T3).** Which scroll plane's base register this band writes — `PlaneA` is the FOREGROUND layer (reg $02), `PlaneB` the BACKGROUND layer (reg $04). **No default — required**, because the register IS the content of the effect (it says which layer borrows) and a default would let a band that means one direction lower silently into the other. ⚠ **THE ONE FIELD ON THIS ARM THAT IS NOT FORWARDED VERBATIM.** `VdpBase` has five variants and three of them are not scroll planes, so `"SpriteTable"` would emit a legal call that re-points the SPRITE TABLE mid-frame and assembles without complaint — nothing downstream can refuse a legal call, so the set is closed in the generator. The REGISTER is derived from it and can never be authored: the two must agree, since `vdp_base_reg` shifts by the variant's own shift (10 / 13). | `vdp_reg(VDP_PLANE_x_OFF, vdp_base_reg(VdpBase.Planex, …))` | `tools/effects_gen.py` `_check_base_swap` (the closed set — this one IS this file's refusal) |
| `base_swap[i].line` | integer | The screen line this band's swap fires ON. **No default — required.** | `fire(line: …)` | shape: `_render_int` · value: `engine/effects/raster_dsl.emp` `fire` (screen-line range 3..223) |
| `base_swap[i].target` | integer, multiple of `$2000` | The raw VRAM byte address the register named by `plane` is re-pointed at — **spelled as an address, not a `VdpBase` name**, the `pal_region.addr` / `ramp.target.vsram.addr` precedent. ⚠ both scroll-plane base registers encode only the bits above the `$2000` granule and drop the rest SILENTLY, so a misaligned target would point the VDP somewhere no other `VRAM_*` consumer looks with nothing visible anywhere else. **No default — required.** | `vdp_base_reg(VdpBase.Planex, target)` | shape: `_render_int` · value: `engine/vdp.emp` `vdp_base_reg` (the granule ensure, which names the granule in its refusal) |
| `base_swap[i].restore_line` | integer | **READ SINCE 2026-09-04 (EFFECTS-W1 F2; contract change per the drift rule at the top of this file).** The screen line the band CLOSES on. **OPTIONAL — and it is what makes the effect a BAND.** With `line`/`target` alone the document lowers to ONE `OP_SET_REG` and there is no OFF edge: nothing restores that band's register until `Flush_VDP_Shadow` at the next frame top, so the swap runs **to the bottom of the display**. At `line: 160` that read as a band because 64 lines remained under it; at `line: 3` it covered the whole screen and read as no effect at all, which is the defect this key fixes. ⚠ **ITS TARGET IS DERIVED, NEVER AUTHORED** — the generator emits the engine's own name for THAT PLANE's home base (`VRAM_PLANE_A` for a `PlaneA` band, `VRAM_PLANE_B` for a `PlaneB` one), the base the register already owns and the word the flush itself would write, so a document cannot disagree with the flush. That asymmetry is the design: an author CHOOSES which map to borrow and does not choose what to give back. A `swaps: [{line, target}, …]` list was rejected for that reason. **Absent: omitted from the emitted program**, i.e. the single-edge shape — absence is how this schema already spells "off" (§7.6 ruling M1's reasoning, one key over), and there is no `null` spelling. Whether it EXCEEDS `line` is `fire_lines`' strict-ascent ensure, not this file's. | a SECOND `fire(restore_line, [reg_set(vdp_reg(VDP_PLANE_x_OFF, vdp_base_reg(VdpBase.Planex, VRAM_PLANE_x)))])` for that band in the same `raster_program()` | shape: `_check_base_swap` · value: `engine/effects/raster_dsl.emp` `fire` (screen-line range) and `fire_lines` (strict ascent) |
| `boundary` | object, closed; six required members and one optional | **READ SINCE 2026-09-04 (this amendment; contract change per the drift rule at the top of this file).** The section's movable single-fire tint boundary — the shipped moving water, made authorable. It is the **fourth arm of the exactly-one-of group** and **it is exclusive for a DIFFERENT REASON than the other three**: `bands`/`ramp`/`base_swap` compete for one field, `EffectsPreset.ep_raster`, and could widen the day a combinator exists; `boundary` lowers into the SIBLING field `ep_patched`, and `preset()` refuses a record carrying both because the install order is **destructive** — `Raster_InstallPatched` clears `Raster_Pending`, so whichever installs last silently kills the other. No combinator unlocks a destructive install order, and the generator's refusal says which reason applies. **There is NO `boundary: null`** (schema §7.6 ruling M1): a top-level arm has no index to leave unreached, so "explicitly off" is spelled by ABSENCE exactly as `ramp` and `base_swap` spell it, and a `null` is refused BY NAME rather than read as absent. Bound through the same `rasterRef` (ruling Q1: one ref binds the whole document); the generator routes it into the generated `<act>_sec_patched(sec:)` chooser instead of `<act>_sec_raster(sec:)`, and **a section binding `patched:` OMITS `raster:` from its `preset()` call**, because `Raster_Program_None` is a real non-zero label and would fire `preset()`'s exclusivity ensure. ⚠ **CORRECTED 2026-09-04, and the empyrean §7.6 sentence this row mirrors still carries the wrong spelling:** this row said "owes `hand: 0` on the raster side" until that spelling was assembled for the first time and refused — `[Error] expected a label (a `Label` argument), got int`, because a bare `0` is not a `Value::Label` and a `Label` parameter's declared DEFAULT is the one place sigil does not class-check. Omitting `hand:` fails identically on a patched-bound section (it has no raster arm to retype the result). Omitting the whole `raster:` argument is buildable and lands the identical 0 in `ep_raster`. | `patchable(fx_tint_band(line, slot, pal_line, entry, count, sh), ch: channel, lo, hi, offscreen_ship)` under `pub data EditorPatched_<ACT>_<id>`, through `patched_program()` | `tools/effects_gen.py` `_check_boundary` (shape, the null-by-name refusal, both cross-field refusals) · `load_preset`'s exactly-one-of group (the four-arm exclusivity, with the different reason) · `render_boundary_preset` (the lowering) |
| `boundary.line` | integer | The **template's DEFAULT schedule** — the screen line the boundary sits on before any runtime patch. **No default — required.** | `fx_tint_band(line: …)` | shape: `_render_int` · value: `engine/effects/raster_dsl.emp` `fire` (screen-line range) · **cross-field**: `_check_boundary` (`line` within `[lo, hi]`) |
| `boundary.channel` | integer | The patch channel this boundary rides. **The SAME index space as `patch_world_ys`, `patch_motion` and a scene's `anchor.at.channel`** — authored, never an encoder-assigned ordinal. **No default — required.** ⚠ A boundary whose channel no document seeds sits at `line` forever, and a seed with no boundary on its channel moves nothing visible: the whole moving water is `boundary` plus both positional keys at that index, in ONE document, bound to ONE section by ONE `rasterRef`. | `patchable(ch: …)` | shape: `_render_int` · value: `raster_dsl.emp` `patchable` (`RASTER_MAX_PATCH`) |
| `boundary.lo` / `boundary.hi` | integers | The inclusive band the patched boundary may travel between. **No default — required.** **⚠ SCREEN lines, NOT fire lines, and NEITHER SIDE CONVERTS — 1:1.** The engine subtracts 1 once, in `Raster_BuildSchedule`; an editor that pre-subtracted would be off by one everywhere, which is the unit trap `patch_world_ys` describes one key over. ⚠ Travel that leaves the band is handled **asymmetrically**: past `hi` the record is DROPPED for the frame and the tint vanishes; below `lo` it is CLAMPED UP and still emitted, because the frame-top ship covers what is above. | `patchable(lo: …, hi: …)` | shape: `_render_int` · value: `raster_dsl.emp` `patchable` (screen-line range) · **cross-field**: `_check_boundary` (`lo <= hi`, checked BEFORE the line rule) |
| `boundary.sh` | boolean, or integer `0`/`1` | Shadow/Highlight on for the boundary. **No default — required**, `bands[i].sh`'s reason exactly. | `fx_tint_band(sh: …)` | shape (bool→int): `_render_bool_int` · value: `raster_dsl.emp` `region_boundary` |
| `boundary.offscreen_ship` | boolean, or integer `0`/`1` | Re-ship this fire's colours as a frame-top DMA when the camera leaves the band at the `lo` end. **OPTIONAL — the only optional member**, because it is the only one `patchable()` itself defaults (`offscreen_ship: int = 0`); absent means omitted from the emitted call so the constructor's default stands. Its engine precondition — exactly one `stream_pal_region` op on the fire — is satisfied by `fx_tint_band` **by construction**, so a document cannot get it wrong. | `patchable(offscreen_ship: …)` | shape: `_render_bool_int` · value: `raster_dsl.emp` `patchable` |
| `boundary.on` | object, **exactly one** arm, `pal_region` | The ON op. **No default — required.** **A `cram` arm and a `vsplit` key are RULED ABSENT, not reserved** (schema §7.6, per §7.3's `approach` precedent that a reserved arm is a key with nothing behind it): `fx_tint_band` takes a staged region only, and a vscroll split has no `stream_pal_region` op for `offscreen_ship` to re-ship, so a reserved arm would carry a hole. Adding either is its own contract change. | `fx_tint_band(slot:, pal_line:, entry:, count:)` | `tools/effects_gen.py` `_check_boundary` (`_single_arm`, which names the one legal arm) |
| `boundary.on.pal_region.slot` / `.pal_line` / `.entry` / `.count` | integers | The staged variant region the boundary switches to. **This is `$defs.tint_region`, NOT `$defs.pal_region` — the same four members WITHOUT `addr`.** `fx_tint_band` DERIVES the CRAM address from `pal_line` and `entry` (`0 * 128 + pal_line * 32 + entry * 2`), so a document carrying `addr` would be one fact computed twice: **`addr` here is refused BY NAME with the derivation**, not accepted and cross-checked. (A `bands[i].on.pal_region` DOES require `addr`, because there `stream_pal_region` cross-checks it against the line and entry — two facts checking each other. Here there is only one.) | forwarded verbatim into `fx_tint_band` | shape + the `addr` refusal: `tools/effects_gen.py` `_check_boundary` · value: `raster_dsl.emp` `stream_pal_region` |
| *(cross-field)* a `boundary` streaming from a slot the same document **nulls** | — | **Refused**, ruling Q6's narrow half applied to this arm: saying "clear this slot" and "stream from this slot" in one file is never what anyone meant, and `offscreen_ship` would re-ship the stale colours at frame top as well. A slot the `variants` array does not **reach** is NOT refused — that slot still holds the section's hand-authored value, which the generator cannot see. | nothing | `tools/effects_gen.py` `_check_cleared_slot_is_not_streamed` |
| `cycles` | array of channel objects, **or `null`**, or absent | This section's ONE palette cycle script — the array IS the script, because `ep_cycle` is one pointer. **Three states, one spelling each** (ruling Q2): **absent** = keep the section's hand-authored cycle (the no-cost majority case); **`null`** = cycling OFF, lowering to the `Pal_Cycle_None` sentinel and never to 0; a **non-empty array** = the authored script. **Empty array: refused**, naming the two legal spellings. More channels than `engine/effects/palette_dsl.emp` has wrappers for (1 and 2 today): refused naming the wrappers, not `PAL_CYCLE_MAX_CHANNELS`. | `cycle_scriptN([cycle_channel(...), ...])` under `pub data EditorCycle_<ACT>_<id>` | `tools/effects_gen.py` `_check_cycles` (shape, the empty-array and channel-count refusals) · `render_preset_cycle` (wrapper choice) |
| `variants` | array whose INDEX is the slot; each entry an object or `null` | The palette variant descriptors this section binds. **Positional: index *i* is `ep_variants[i]`, the slot `Palette_SetVariant` takes and the slot an `on.pal_region.slot` in this same document names.** **Three states per INDEX** (ruling Q5): an index the array does not reach (**including an absent `variants` key**) KEEPS that slot's hand-authored value — load-bearing, because every shipped OJZ preset carries the act's water tint and a silent clear would drop it act-wide at the first crossing; **`null`** at an index CLEARS it (lowers to 0); an **object** authors it. **There is no key-level `variants: null`** — clearing both is `[null, null]`, and a key-level null is refused BY NAME rather than read as absent. More entries than the engine has slots: refused naming `PAL_MAX_VARIANTS`. | one `variant(...)` per authored slot under `pub data EditorVariant_<ACT>_<id>_<slot>` | `tools/effects_gen.py` `_check_variants` (shape, the key-level-null and slot-count refusals) |
| `patch_world_ys` | array whose INDEX is the patch channel; each entry an integer `0 … 65535` or `null` | The world anchor each patch channel rides — the place in the LEVEL that `Effects_LatchWorldLines` turns into a screen line once per frame for all three consumers (the raster fire of a `patchable()` record, a scene's `SceneAnchor.At` band split, the off-screen ship). **Positional: index *i* is patch channel *i*.** **Three states per INDEX**, the same three `variants` has: an index the array does not reach (**including an absent key**) KEEPS the section's hand-authored anchor; **`null`** is the engine sentinel `PATCH_ANCHOR_NONE` (`$7FFF`), "this channel is unused"; an **integer** authors it. No key-level `patch_world_ys: null`. More entries than `RASTER_MAX_PATCH`: refused — and nothing downstream would have caught it, since `preset()`'s length ensure fires on the CALL SITE's four literal positions. **⚠ THE UNIT IS WHOLE PIXELS, absolute level space, and NEITHER SIDE CONVERTS — 1:1.** Not the scene document's `drift.rate` (1/256 px/frame, editor multiplies by 256); that habit here lands the anchor 256× down the level and the band silently never appears. **⚠ `0` is a real world Y and the worst one** — `anchor - Camera_Y` at 0 reads as above the screen top. **`32767` is REFUSED**: it is the sentinel, so it reads as authored to a human and as unused to the runtime. Both bounds are owned HERE (and by the writer schema) because **nothing else enforces them** — `preset()` checks the array's length, never its values. | `ojz_act1_sec_patch_world_y(sec: N, ch: i, hand: …)` → `ep_patch_world_ys[i]` | shape + both value bounds: `tools/effects_gen.py` `_check_patch_world_ys` (mirrors `RASTER_MAX_PATCH` / `PATCH_ANCHOR_NONE`, and the empyrean schema encodes the same two) |
| `patch_motion` | array whose INDEX is the patch channel; each entry `{"sweep": {…}}` or `null` | The motion of each patch channel. Same positional shape and same three states; **`null`** is `ANCHOR_MOTION_NONE` (`0`), a static channel. **`sweep` is the only arm.** No `approach` arm exists and none is reserved: APPROACH has no preset seed field (`engine/effects/preset.emp`), its runtime handle is the call `Effects_SetTargetY`, and a reserved arm would be a key with nothing behind it — adding one is its own contract change. | `ojz_act1_sec_patch_motion(sec: N, ch: i, hand: …)` → `ep_patch_motion[i]` | `tools/effects_gen.py` `_check_patch_motion` (shape, arm arity) |
| `patch_motion[i].sweep.amp_shift` | integer | **A BASE-2 LOGARITHM, not pixels.** Peak excursion = `256 >> amp_shift` px, so the ladder is 64 px down to 1 px in **7 rungs** and adjacent rungs differ by a **factor of two**. **No default — required.** A UI control must SNAP to a rung; the generator forwards the value untouched and never rounds, because rounding halves or doubles the author's travel in silence where the engine's refusal prints the whole derived ladder. | `anchor_sweep(amp_shift: …)` | shape: `_render_int` · value: `engine/effects/raster_dsl.emp` `anchor_sweep` (`ANCHOR_SWEEP_SHIFT_MIN..MAX`, both **derived** from `ANCHOR_SINE_AMP` and `ANCHOR_SCREEN_LINES`, never picked) |
| `patch_motion[i].sweep.period_shift` | integer | Also a base-2 logarithm: one cycle = `256 << period_shift` ticks (4.27 s at 0, 8.53 s at 1, on a 60 Hz frame), **9 rungs**. **No default — required.** Forwarded verbatim, same reason. | `anchor_sweep(period_shift: …)` | shape: `_render_int` · value: `raster_dsl.emp` `anchor_sweep` (`0..ANCHOR_SWEEP_PERIOD_SHIFT_MAX`, derived from `ANCHOR_SINE_ENTRIES` and `ANCHOR_TICK_BITS`) |
| `patch_motion[i].sweep.phase` | integer | Phase offset in **sine-table entries**; `0 … 255` is one full cycle whatever the period is, because the phase is added AFTER the shift. **OPTIONAL — the only optional sweep field**, because it is the only one `anchor_sweep()` defaults; absent means omitted from the emitted call so the constructor's default stands. The only continuous field. It exists so two channels at one period do not move in lockstep and read as one boundary (Ristar's correction). | `anchor_sweep(phase: …)` | shape: `_render_int` · value: `raster_dsl.emp` `anchor_sweep` (`0..ANCHOR_SWEEP_PHASE_MAX`) |
| *(cross-field)* a sweep on a channel the same document **nulls** | — | A `patch_motion[i]` beside an explicit `patch_world_ys[i] = null` is **refused**: a sweep displaces an anchor, and a channel the document declares unused has none. A sweep on an index the document does not **reach** is **NOT** refused — the section's hand-authored anchor is still there, which the generator cannot see (`_check_cleared_slot_is_not_streamed`'s reason, one key over). | nothing | `tools/effects_gen.py` `_check_motion_has_an_anchor` |
| *(cross-file)* a motion in a game without `CAP_ANCHOR_MOTION` | — | **Refused.** The two halves of the mover are gated differently: `Effects_InstallPreset` seeds `Effects_Motion[]` from every preset unconditionally, while the latch loop that READS it is inside `if (Game.SCANLINE_CAPS & CAP_ANCHOR_MOTION) != 0`. So in a game that does not raise the bit the sweep is installed, folded into `Effects_Motion_Any`, and never read — a silent no-op with data behind it. The mask is **parsed from the game's own `config/game.emp`**, not mirrored: sonic4 is `$01DE` and demo is `0`, so there is no single value to carry, and a config with no `SCANLINE_CAPS` at all is refused rather than read as 0. | nothing | `tools/effects_gen.py` `game_scanline_caps` + `_check_patch_context` |
| *(cross-file)* a motion on a channel nothing consumes | — | **Refused**, naming the channels that do have a consumer. Liveness is collected from the game's own effects library — every `patchable(ch: i, …)` record **and** every `SceneAnchor.At(i, …)` scene, because three consumers read the latched line and a check that looked only at `patchable()` would refuse a sweep a band split legitimately consumes. **Since 2026-09-04 the DOCUMENT'S OWN `boundary` counts as a consumer too**, and it is the only one with no superset caveat: the library walk greps hand-authored `.emp`, which by construction cannot contain a channel a document declares, so without this the intended shape (boundary + seed + sweep at one index in ONE document) would be refused for having no consumer while carrying its consumer. **It is a SUPERSET check and says so in its own message:** whether the SECTION binding this document is one of the places the channel is consumed depends on which program and which parallax config that section's `preset()` binds, which lives in the hand-authored library and the act descriptor. A green is not a promise the effect is visible; a red is a promise it is not. A **seed** on a dead channel is deliberately NOT refused — an inert anchor costs one word and is what a channel becomes live around, where an inert sweep costs cycles every frame. | nothing | `tools/effects_gen.py` `declared_patch_channels` + `_check_patch_context` |
| `fires` | — | The last empyrean §7 reserved wave-2 key. **Refused by name**, with the reason, not as an unknown key. | nothing | `tools/effects_gen.py` `_check_keys` via `PRESET_REFUSED_KEYS` |
| any other key | — | **Refused.** Adding one is a CONTRACT change (see the drift rule at the top of this file). | nothing | `tools/effects_gen.py` `_check_keys` |
| `bands[i].top` | integer | Screen line the effect turns **ON**. Its writes land on this line. **No default — required.** **0 is not "off"; it is line 0, which the engine refuses** (lines 0–2 belong to the priming records). | `band(top: …)` | shape: `tools/effects_gen.py` `_render_int` · value: `engine/effects/raster_dsl.emp` `fire` (screen-line range), `band` (`top < bot`), `band` (height vs `fire_cost_cycles`) |
| `bands[i].bot` | integer | Screen line the effect turns **OFF** — the restore's line. The band covers `top .. bot-1` inclusive; `bot - top` is the height the engine charges. **No default — required.** | the derived `pal_restore` fire's line | shape: `_render_int` · value: `raster_dsl.emp` `fire`, `band` (`top < bot`), `band` (height, and the S/H height rule when `sh` is set) |
| `bands[i].sh` | boolean, or integer `0`/`1` | Shadow/Highlight on for the band. **No default — required**, deliberately: `raster_dsl.emp`'s `region_boundary` note is that "whether an effect changes a mode register is worth stating at the call site". `false`/`0` = a two-fire band; `true`/`1` = the three-fire S/H shape. | `band(sh: 0\|1)` | shape (bool→int translation): `tools/effects_gen.py` `_render_bool_int` · value: `raster_dsl.emp` `band` ("band: sh must be 0 or 1") |
| `bands[i].on` | object, **exactly one** of `cram` / `pal_region` | The ON op — the write the band turns on and the restore is derived from. **No default — required.** Zero arms, two arms, or an unknown arm: refused. `vsram` is deliberately not an arm: `band()` refuses a VSRAM ON op because a band's restore is derived from the ON op's CRAM span and VSRAM has none. | `stream_cram(…)` or `stream_pal_region(…)` | `tools/effects_gen.py` `render_band_on` (arm spelling, arity) |
| `on.cram.addr` | integer | CRAM **byte** address the colours are written to. **`0` is a real address, not "absent" — and it is on palette line 0, the character's line, which both `stream_cram` and the derived `pal_restore` refuse.** | `stream_cram(addr: …)`, and the derived `pal_restore(addr, …)` | shape: `_render_int` · value: `raster_dsl.emp` `stream_cram` (range, even, line ≠ 0, span within the line) **and** `pal_restore` (the same four, on the restore `band()` derives) |
| `on.cram.colours` | array of integers | The CRAM colour words, in order, starting at `addr`. Its **length** is also the restore's word count (`band()` derives `pal_restore(sa, sb / 2)` from this op's own span). **Empty: refused by the engine, not here.** | `stream_cram(colours: [ … ])` | shape (list, and each element an integer): `tools/effects_gen.py` `render_band_on` + `_render_int` · value: `raster_dsl.emp` `stream_cram` (burst ceiling), `pal_restore` (the DEEP-class ceiling the derived restore hits), `fire` (per-fire stream words) |
| `on.pal_region.addr` | integer | CRAM byte address the staged variant colours land at. | `stream_pal_region(addr: …)` | shape: `_render_int` · value: `raster_dsl.emp` `stream_pal_region` (range, even, and the two agreement ensures against `pal_line`/`entry`), plus `pal_restore` on the derived restore |
| `on.pal_region.slot` | integer | Which `Pal_Variant_Stage` slot the colours are streamed FROM. **Not the CRAM destination** — that is `addr`. | `stream_pal_region(slot: …)` | shape: `_render_int` · value: `raster_dsl.emp` `stream_pal_region` (slot range) |
| `on.pal_region.pal_line` | integer | The staging source's palette line. Must agree with `addr`'s line. | `stream_pal_region(pal_line: …)` | shape: `_render_int` · value: `raster_dsl.emp` `stream_pal_region` (range, and the `addr >> 5 == pal_line` agreement) |
| `on.pal_region.entry` | integer | The staging source's first entry. Must agree with `addr`'s entry. | `stream_pal_region(entry: …)` | shape: `_render_int` · value: `raster_dsl.emp` `stream_pal_region` (range, and the `(addr >> 1) & 15 == entry` agreement) |
| `on.pal_region.count` | integer | How many colours are swapped. Also the derived restore's word count. | `stream_pal_region(count: …)` | shape: `_render_int` · value: `raster_dsl.emp` `stream_pal_region` (burst ceiling, `entry + count` within the line), `pal_restore`, `fire` |
| `cycles[i].line` | integer | CRAM line the rotation runs on. **No default — required.** Never 0: line 0 is the character's, which the constructor refuses. | `cycle_channel(line: …)` → `pc_line` | shape: `_render_int` · value: `engine/effects/palette_dsl.emp` `cycle_channel` (1..3) |
| `cycles[i].first` | integer | First entry index within the line. **No default — required.** | `cycle_channel(first: …)` → `pc_first` | shape: `_render_int` · value: `palette_dsl.emp` `cycle_channel` (0..15) |
| `cycles[i].count` | integer | How many consecutive entries rotate. **No default — required.** The runtime treats a too-small count as a no-op. | `cycle_channel(count: …)` → `pc_count` | shape: `_render_int` · value: `palette_dsl.emp` `cycle_channel` (a minimum, and `first + count` within the line's 16 entries) |
| `cycles[i].period` | integer ≥ 2 | **FRAMES BETWEEN ROTATIONS, IN THE AUTHOR'S UNIT** — `period: 9` means a rotation every 9 frames. **No default — required.** The engine's timer reloads the byte and rotates when it hits 0, so its runtime cadence is `period + 1`; **the generator absorbs that** and emits `pc_period = period - 1` (ruling Q7), so no authored document moves when the booked runtime fix lands. **The one consequence, and the ONE value bound this generator owns:** the legal document floor is the engine's floor shifted by the same translation, so `0` and `1` are refused HERE, with a message naming the author's number — one layer down the engine would complain about a number the author never wrote. | `cycle_channel(period: <period - 1>)` → `pc_period` | shape + the unit floor: `tools/effects_gen.py` `render_cycle_channel` (`CYCLE_PERIOD_DOC_MIN`, pinned against the engine's own floor by `test_effects_gen.py::TestTheEngineMirrorsArePinned`) · value: `palette_dsl.emp` `cycle_channel` (1..255, on the EMITTED byte) |
| `cycles[i].dir` | integer | Rotation direction, forward or reverse. **OPTIONAL — the only optional channel field**, because it is the only one `cycle_channel()` defaults. Absent: omitted from the emitted call so the constructor's default stands. | `cycle_channel(dir: …)` → `pc_dir` | shape: `_render_int` · value: `palette_dsl.emp` `cycle_channel` (0 or 1) |
| `variants[i].shift_r` / `shift_g` / `shift_b` | integer | Right-shift of that colour channel before the bias. **OPTIONAL** (constructor default). | `variant(shift_r: …)` → `v_shift_r` etc. | shape: `_render_int` · value: `palette_dsl.emp` `variant` (0..3 — a 3-bit channel) |
| `variants[i].bias_r` / `bias_g` / `bias_b` | integer, may be negative | Signed bias added to that channel after the shift; the transform is `clamp((c >> shift) + bias, 0, 7)`. **OPTIONAL** (constructor default). | `variant(bias_r: …)` → `v_bias_r` etc. | shape: `_render_int` · value: `palette_dsl.emp` `variant` (-7..+7) |
| `variants[i].lines` | integer **bitmask** | Which CRAM lines the derive covers. **The INTEGER BITMASK the engine field is** (ruling Q4) — checkboxes or a line list are the editor panel's job, not the wire's, and **the generator will not grow a second spelling.** **OPTIONAL** (constructor default `%1110`). Uncovered lines are left as they are. | `variant(lines: …)` → `v_lines` | shape: `_render_int` · value: `palette_dsl.emp` `variant` (bit 0 — the character's line — must be clear; at least one of bits 1-3 set) |
| *(cross-field)* a band streaming from a **cleared** slot | — | A band whose `on.pal_region.slot` names an index this same document sets to **`null`** is **refused**: "clear this slot" and "stream from this slot" in one file is never what anyone meant, and the band would stream whatever the staging buffer last held. A band naming a slot the document simply does **not reach** is **NOT** refused — that slot still holds the section's hand-authored value, which the generator cannot see (ruling Q6 defers the broad check). | nothing | `tools/effects_gen.py` `_check_cleared_slot_is_not_streamed` |

**Whole-program rules — no field carries them, and they are all the engine's.** Emitted by
`raster_program()` over the composed fire list: band pairing and ownership
(`check_band_pairing`, `check_band_ownership` — including "two bands may share colours only
if they do not overlap vertically"), the blanking-window landing solve (`check_landings` —
this is what refuses two contiguous bands, because band N's restore and band N+1's ON op
would share a fire line), fire spacing and cost (`check_intervals`, `check_density`), the
per-frame HInt total (`check_hint_total`), and the program-buffer ceiling inside
`raster_program` itself (which is what makes three bands the cap). **All in
`engine/effects/raster_dsl.emp`.**

#### Not restated, not clamped — and what that buys the writer

The generator holds **no** numeric bound from the raster tier: not the screen-line range,
not the CRAM address range, not a burst ceiling, not the band count, not a height minimum,
not the palette-line-0 rule. An out-of-range value is **forwarded verbatim** so the author
reads `raster_dsl.emp`'s own sentence — which carries the measurement behind the rule,
something a copy in a Python file could never carry. Clamping was explicitly rejected: a
producer that clamps authors something the author did not write.

Measured, on the real build (2026-08-29, `sigil build --native --game sonic4`, generated
text only):

| authored | the message the author gets |
|---|---|
| 4 colours in one band | `stream_cram: 4 colours exceeds RASTER_BURST_MAX_CRAM (3) — the per-fire CYCLE budget for the CHEAP burst class, not a FIFO limit. …` (+ `pal_restore`'s DEEP-class refusal on the derived restore, + `fire`'s per-fire ceiling) |
| `addr: 4` (palette line 0) | `stream_cram: address 4 is on CRAM line 0, the character's line (CharacterDef.cd_palette) — a raster write there repaints the active character` |
| `top: 999` | `fire: screen line 999 outside 3..223 (lines 0-2 belong to the priming records)` |
| `top: 120, bot: 121` | `band: height 1 is below this ON op's minimum — the ON fire costs 624 cyc against 488 available` |

The generator's own structural gate for this claim is
`tools/test_effects_gen.py::TestBandValuesAreNotValidatedHere::test_the_generator_source_carries_NO_raster_bound_literal`,
which reads `effects_gen.py`'s raster arm and fails if it spells one of those numbers.

#### RULES WITH NO ENFORCING ASSERTION — stated because a silence is a claim

- **Nothing checks that a preset document is BOUND.** The generator emits the program's
  words; which section installs it is an `ep_raster` argument in a hand-authored `preset()`
  call (`games/sonic4/data/effects/ojz_effects.emp`), and choosing that is a content
  decision with a picture attached (§16.1: a preset is section-scoped). An authored but
  unbound preset therefore costs ROM and shows nothing, and **no assertion anywhere says
  so**. This is the open seam of this arm; see the DEFERRED_WORK entry.

  **HALF OF IT IS NOW CHECKED, and stating which half is the point** (2026-08-29).
  `tools/test_raster_cycle_table_lint.py` holds the DEBUG effects-lab's `.raster_table`
  (`games/sonic4/test/ojz_scroll_test.emp`, `Debug_LabCycleHotkey`) to the preset documents
  on disk in both directions, so a preset with no row — i.e. a program *nothing in either
  shape can install* — fails the build's pytest lane. What is still unchecked, and is the
  larger half: **binding to a SECTION**. A preset reachable only from a debug chord is not
  content, and a preset named in a `preset()` call has no assertion at all. Do not read the
  lint as closing this bullet.
- **Nothing checks the total ROM cost of the preset set.** Each program is bounded by the
  64-word program buffer; the number of programs is not bounded by anything.
- **A SWEEP'S FIT INSIDE ITS CHANNEL'S BAND IS NOT AN ASSERTION IN THIS PIPELINE, AND IT IS
  THE OBLIGATION MOST LIKELY TO GO WRONG FIRST** (item 4, §4a of
  `docs/superpowers/specs/2026-09-03-anchor-authoring-key-shape.md`). A sweep's peak-to-peak
  travel must stay inside its channel's `patchable(lo, hi)`. Leaving that band upward does
  **not** clamp: `Raster_BuildSchedule` REMOVES the record for the frame, so the band does
  not move — it VANISHES, and returns at the next zero crossing. A sweep one rung too wide
  reads as a band flickering out once per cycle, i.e. as a rendering bug rather than as an
  amplitude anyone chose. `anchor_sweep()` refuses an amplitude wider than the SCREEN, which
  is necessary and not sufficient; `lo`/`hi` live in the raster program and `amp_shift` in
  the preset, associated by a POINTER at runtime, so no comptime scope holds both.
  **`tools/test_anchor_sweep_band.py` is that scope**, it covers the hand-authored and the
  generated modules by glob through one `scan_module()`, and it accounts for every
  `anchor_sweep(` occurrence rather than counting the ones a pattern matched. Two limits it
  states on every run rather than leaving to be inferred from a green: on **channel 0** the
  band bound is currently unfalsifiable (a 218-line band against a 128 px widest legal rung),
  so only channel 1 can be failed by amplitude alone; and the **seeded-headroom** bound is
  evaluated only for a sweep on the **spawn section**, because `SPAWN_CAMERA_Y` is the camera
  at the act spawn and anchors are act-relative — a section a grid row down legitimately
  seeds an anchor a section-height further down, and judging it against the spawn camera
  would report a violation that is an artifact of the wrong camera.
- **Nothing checks that a SECTION binding a document actually consumes the patch channels it
  authors.** The generator's liveness check is a superset (see the row above): it can see
  that a channel has a consumer somewhere in the game, not that this section is one of them.
  **This bites today.** The only section in the tree with live patch channels is section 0
  (`OJZ_TwoChannel`'s two `patchable()` records plus `ParallaxConfig_OJZ_Underwater`'s
  anchor), and **section 0 cannot bind an editor preset document at all**: a document must
  carry `bands` (ruling Q1a), `bands` lowers to a raster program, `tools/effects_seam_gate.py`
  requires every sidecar `rasterRef` to be threaded through `ojz_act1_sec_raster(sec: N)`,
  and `preset()` makes `ep_raster` and `ep_patched` mutually exclusive. Those three rules
  close the door together. So the authoring path is proved end to end on **section 5**, whose
  preset binds a static editor program and defers its parallax to an unanchored act default
  — the seed and the packed word reach the ROM and are seeded on the crossing, and nothing
  reads them. Giving section 5 a consumer, or opening the contract so a `patched:` section
  can bind a bands-less document, is the open half; see `docs/DEFERRED_WORK.md`.
- **The runtime palette binding behind a `pal_region` band is unchecked, and cannot be
  checked at build time.** The variant bound to `slot` must cover `pal_line` in its `lines`
  mask or the band streams whatever the staging buffer holds. Binding is a runtime call
  (`Palette_SetVariant`), so no comptime guard can see it — `raster_dsl.emp`'s
  `fx_tint_band` header states this as a standing, booked limitation.
- **Nothing checks that a band is VISIBLE** — that the CRAM entry it repaints is used by
  pixels on those rows, or that the colour differs from the base. Design §3.4.
- **The per-frame CPU cost of palette CYCLING is UNMEASURED, and there is deliberately no
  number** (ruling Q9). `tools/effects_budget_model.toml` has no cycling row, and a
  placeholder there would be worse than an absent one because a budget model is read as
  measured. What IS measured, and what matters more than the rotation itself: a cycling
  channel sets `PAL_ACT_VARIANT_STALE` on the frames it actually rotates, and that bit is
  what gates the full variant re-derive — **19,332 cycles/frame, 15.1% of a frame**
  (`engine/effects/palette.emp`, measured on OJZ_ScrollTest 2026-08-13). So a document
  carrying BOTH keys is not two independent costs: the cycle is what makes the variant
  re-derive fire. **⚠ And that figure is a ONE-SLOT number** — the measured scene bound one
  variant — while `variants` is the first mechanism that makes binding BOTH slots easy, and
  `Palette_DoVariants` derives each bound slot independently. The two-slot cost is
  unmeasured; the capture is booked in `docs/DEFERRED_WORK.md` under item 5.
- **Nothing compares an authored `period` against an observed CADENCE.** The generator's
  `period - 1` and the engine's `period + 1` timer are a matched pair held together by a
  comment (`# RIDER 5 PAIRING` in `tools/effects_gen.py`'s `render_cycle_channel`) and
  nothing else. If the booked runtime fix lands without the generator changing in the same
  parcel, every authored cycle runs one frame faster, silently. What IS checked, by
  `tools/editor_palette_golden.py` on every canonical sonic4 build, is that the byte in the
  ROM equals `authored period - 1` — i.e. that the generator's half of the pair is intact.
- **The runtime variant-to-`pal_line` binding is still unchecked, but HALF of the slot half
  is now checkable and is checked.** A document carrying both `bands` and `variants` puts
  the band's `slot` and the descriptor in one file, so the generator refuses a band that
  streams from a slot the document explicitly clears (the row above). The BROAD check — a
  band naming a slot the document leaves absent — is deferred (ruling Q6) because absent
  means "the section's hand `preset()` value is still there", which is the majority case.
  Whether the bound variant's `lines` mask covers the band's `pal_line` remains a runtime
  fact no comptime guard can see.
- ~~**No writer-side schema exists yet.**~~ **IT EXISTS NOW — corrected 2026-08-29, hours after
  this bullet was written, which is why it is corrected in place rather than left to be
  discovered.** The writer-side half is `contract/schema/aurora-effects-preset.schema.json`
  in `empyrean`, added at `6664b61` (verified reachable at their `origin/main` here; blob
  `29c1c5ee6197`, read firsthand rather than taken from the message announcing it).
  It is a **new** document rather than a `bands` key added to the scene schema — the original
  bullet's own check, run against `aurora-effects-scene.schema.json`, would therefore still
  come back empty today and still be reporting the truth about the wrong file. **A staleness
  check that names a specific artifact goes stale when the answer moves to a different
  artifact**, and it fails silently in the reassuring direction: the grep stays empty, so
  nothing prompts a re-read.
  It transcribes §2.4 at `c03b9812`, restates **no** numeric bound (each row's description
  points at its `raster_dsl.emp` symbol instead), is closed everywhere, refuses `fires` /
  `variants` / `cycles` by name, and carries the four no-assertion limits above in its own
  description — so a reader of either half meets them. Aurora pins its golden against both.

## 3. Error-handling posture — normative for BOTH halves

Written because of the asymmetry, which is the reason the section exists at all (ERRATUM 2
+ its `c88ab125` mirror-audit appendix, both verified firsthand): **the load path is safe
on the aeon side today and unsafe on the Aurora side today.**

- **aeon consumers fail loud, and must keep doing so.** `inject_editor_bg.py:58-61` is
  the reference posture: bare `json.load` + direct subscripting — malformed input raises,
  the build STOPS, and nothing is written back over the input. `effects_gen.py` adopts
  the same posture for every §2 input (including an unreadable sidecar — §2.2's
  missing/unreadable split). No consumer grows a tolerate-garbage or repair path.
- **Deliberate non-example:** the broad `except Exception` handlers in
  `tools/ojz_block_gen.py` (`:222`, `:248`, `:288`, `:308`) are confined to the
  content-addressed cache/memo layer, where degrading means a cache MISS and a recompute
  — not data loss. A different defect class from Aurora's silent catch; correct as
  written; do not file them as the same hazard.
- **Generator writes reuse the in-tree atomic idiom by NAME:**
  `tools/ojz_block_gen.py:201-206` `_atomic_write` (pid-suffixed temp file, then
  `os.replace`). New generators reuse it rather than re-deriving the principle.
- **Aurora's half** (their lane, restated from ERRATUM 2): route the meta catch through
  `markUnreadable`, gate the meta write — including the cleared-overwrite literal —
  behind `understood('meta.json')`; loud and non-destructive, never quiet-and-lossy.

## 4. Provenance and companions

- Six adjudicated rulings, owner-confirmed: aeon `08f01b73`,
  `docs/research/2026-08-22-aurora-effects-authoring-assessment.md` §(f).
- Wave-1 design (generated binding module, act_descriptor import seam, preview posture,
  Aurora-vs-aeon split): `docs/superpowers/specs/2026-08-22-aurora-effects-wave1-design.md`.
- Writer-side: `empyrean/docs/AURORA_EFFECTS_SCHEMA.md` +
  `empyrean/contract/schema/aurora-effects-scene.schema.json` (empyrean branch
  `docs/aurora-effects-schema`; SHA at landing to be pinned by Aurora).
- Wave 2 (raster preset composition) will add its own consumer rows here when its schema
  is cut; its writer surface is reserved-by-name-only in the empyrean doc §7.
- **PUBLISHED THE OTHER WAY (aeon → the writer), new 2026-09-04:**
  `games/sonic4/data/generated/effects_channel_bands.json` — a GENERATED, READ-ONLY sidecar
  giving each patch channel the screen band its `patchable(fires, ch, lo, hi)` record
  declares, as `ch -> {lo, hi, lines, source}` with `source` a `file:line` into the
  hand-authored `.emp`. It exists because those bounds live nowhere a writer can read them,
  so a panel could author a sweep whose travel leaves its channel's band and say nothing:
  a sweep is a CERTAIN REFUSAL when its PEAK-TO-PEAK TRAVEL (`2 * (256 >> amp_shift)`, whole
  pixels, and `amp_shift` is already a document key) EXCEEDS `channels[c].lines`. Travel
  within `lines` is NOT a clearance — the latched line is (anchor - Camera_Y), so whether it
  fits is camera-dependent and unknowable at author time. **This line carried BOTH of the
  errors the sidecar's own `how_to_use` exists to prevent, until 2026-09-05: it said
  "fits when" (a clearance the test cannot give) AND it used PEAK EXCURSION rather than
  peak-to-peak travel — the 2x permissive error whose fix in the sidecar was never
  back-applied here.** Found by grepping this tree for the old phrasing after aurora asked
  me to confirm nothing else keyed on it; the phrasing search found the stale QUANTITY too. **⚠ THE TWO EDGES ARE NOT SYMMETRIC and
  a warning that treats them alike is wrong** — past `hi` the record is DROPPED (no boundary
  anywhere; the band vanishes until the latched line re-enters the band), while below `lo` it
  is CLAMPED UP and still drawn. The file's own `edges` block carries both behaviours and the
  engine line implementing each, located at generation time rather than written down.
  Regenerated by `effects_gen.py emit` and drift-checked by `effects_gen.py check`, which
  `build.sh` runs build-fatally. Booked `RASTER-CHBAND-1`; the authoring key that would let a
  document declare a band is a separate, larger question answered in
  `docs/superpowers/specs/2026-09-04-channel-band-key-shape.md`.


## 5. Canonical serialization — normative for every writer of these files

*(Agreed with the Aurora lane 2026-08-22, after they measured 282,867 B vs 407,055 B
for one semantically identical document.)*

**The clause has two halves with different scopes, and the split is deliberate**
*(ruled 2026-08-22 after the Aurora lane found the original text's letter and its
rationale disagreeing — the letter reached scene files, every line of the reasoning was
about tile-array documents)*:

- **DETERMINISM binds universally. No exceptions, no document classes.** Keys sorted
  alphabetically, **recursively** (Python's `sort_keys=True` is recursive; nested band
  and layer objects sort too). Every writer of every shared JSON document in this
  contract.
- **COMPACTNESS is per document class.** Tile-array documents (`editor_bg_override.json`
  and kin) are minified, separators `(",", ":")`. Scalar documents — the effects scene
  files, which are a handful of fields — are **pretty-printed**, indent 2.

So aeon's chokepoint is `json.dumps(obj, sort_keys=True, separators=(",", ":"))` for the
tile-array class (`bg_override_io.atomic_write_json`, which all three aeon writers —
`forest_bg_gen.py`, `png_to_bg_override.py`, and the shared path itself — already funnel
through), and `json.dumps(obj, sort_keys=True, indent=2)` for scene files.

**Why compactness splits and determinism does not.** The rejection of pretty-printing
below is an argument *from scale*: a document dominated by tile arrays yields a diff that
is attributable and enormous. Remove the scale and that argument inverts — for a scene
file a pretty diff is genuinely more reviewable. But the property the clause exists for,
*a diff appears only when something semantic changed*, is scale-independent, so
determinism cannot split.

**Why ALPHABETICAL rather than contract order**, since the alternative is tempting and
worse: alphabetical is a total order derivable by both repos from the data alone.
Contract order needs a key list maintained identically in two repos, and has no answer at
all for the unknown keys Aurora round-trips untouched (insertion order is not
reproducible across writers). **The cost is real and accepted:** in a pretty-printed
scene file, alphabetical puts `schema` and `id` in the middle rather than at the top,
which reads worse than contract order. A self-describing order that cannot drift is worth
more than a familiar one that can.

**Vendored provenance fixtures are NOT canonicalized, and this overrides the above**
*(Aurora's call, adopted — they raised it unprompted while adopting the clause)*. A
fixture whose value IS byte-identity with the artifact it was captured from
(`test/fixtures/bg-override/editor_bg_override.b0e5a661.json` is the live example) must
keep the bytes it was captured with; re-pinning it to canonical form destroys the exact
provenance that makes it worth having. **Canonicalization governs what a tool WRITES as
output, never what it VENDORS as evidence.** A parcel that finds it needs to reserialize
such a fixture should stop and report rather than decide.

**The property is DETERMINED serialization, not compactness.** Matching separators
alone would fix the churn that happened to get measured and leave key order waiting to
produce the identical surprise later. What is being bought is: *a diff appears only
when something semantic changed.*

**Why not pretty-print.** It was considered and rejected. The instinct is sound — these
documents are single-line, so `git --stat` reports "1 line changed" regardless of what
happened inside, which is exactly how a two-band `anims` deletion survived a month
unnoticed. But pretty-printing a document dominated by tile arrays yields a diff that is
attributable and enormous, which is the same unreviewability in a different costume.
Canonical-and-minified delivers the property that actually defends against the silent
deletion.

**Adopting it churns the file once per side, and that one-time churn has the exact shape
of the hazard this clause exists to prevent** — a total rewrite showing as one line. So:
**land a reserialization as its own commit that changes nothing else**, stating in the
message that the diff is format-only. If it rides along inside a content change, the
first thing this clause does is hide a real edit. This applies to every tool that adopts
it later, which is why it is written here rather than in a commit message.
