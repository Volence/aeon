# Editor-authored raster presets — the Aurora lane's page

*Status: worked example + honest limit, 2026-08-29. **This page is NOT an authority on the
format.** Two documents already are, and this one exists because neither of them carries a
real document, a way to look at the result, or a plain statement of what an author still
cannot do:*

| | authority | what it owns |
|---|---|---|
| consumer side | `tools/EFFECTS_CONSUMER_CONTRACT.md` §2.4 (this repo) | exactly which fields `tools/effects_gen.py` reads, and the file+symbol enforcing each rule |
| writer side | `contract/schema/aurora-effects-preset.schema.json` (`empyrean`, reachable at `origin/main` — verified firsthand, not taken from an announcement) | the JSON types, the closed key set, the exactly-one-arm rule |

**If this page and either of those disagree, they win and this page is wrong.** The one
thing here that is machine-checked is the key list in §B, which
`tools/test_effects_gen.py::TestEditorRasterPresetsDoc` reads out of this file and compares
against `effects_gen.py`'s own constants on every build — so a field NAME here cannot rot
silently, which is the failure that costs a panel a rebuild. Everything else in this page is
prose and can.

---

## A. The shortest true description

One JSON document per raster program, at
`games/sonic4/data/editor/effects/presets/<preset_id>.json`. `tools/effects_gen.py` lowers
it to `compose([band(...)]) → raster_program(...)` and emits it as
`pub data EditorRaster_OJZ_Act1_<preset_id>` in
`games/sonic4/data/generated/ojz/act1/effects_scenes.emp`. Its ROM placement is already
declared by a section-NAME row in `games/sonic4/map.toml`, so **a new preset needs no
`map.toml` edit.**

**A band is not a scene field.** A scene IS a `parallax_config`; the raster program is a
channel of an `EffectsPreset`, and an `EffectsPreset` is bound per SECTION
(`docs/superpowers/specs/2026-08-28-raster-band-ownership-design.md` §16.1). A `bands` key on
a *scene* file is refused. The band panel edits a **preset document**, a different file.

---

## B. The key list — checked against the generator

Every name below is compared against `tools/effects_gen.py` by a test. The **values** are
not here on purpose: the generator holds no numeric bound from the raster tier, so an
out-of-range value is forwarded verbatim and the author reads
`engine/effects/raster_dsl.emp`'s own sentence, which carries the measurement behind the
rule. Do not clamp on the writer side either — a producer that clamps authors something the
author did not write.

<!-- KEYS-CHECKED-AGAINST-effects_gen.py -->
```
preset:          bands, cycles, id, patch_motion, patch_world_ys, ramp, schema, variants
preset-ignored:  name
preset-refused:  fires
band:            bot, on, sh, top
on-arms:         cram, pal_region
on.cram:         addr, colours
on.pal_region:   addr, count, entry, pal_line, slot
cycle-channel:   count, first, line, period
cycle-channel-optional: dir
variant:         bias_b, bias_g, bias_r, lines, shift_b, shift_g, shift_r
sweep:           amp_shift, period_shift
sweep-optional:  phase
```
<!-- /KEYS-CHECKED-AGAINST-effects_gen.py -->

Reading the rows:

- **`preset`** — `schema`, `id` and `bands` are required; `cycles` and `variants` are
  optional. `schema` must be `1`. `id` must match the filename stem and
  `^[a-z][a-z0-9_]{0,31}$`, because it becomes an `.emp` label component. `bands` is a
  list with at least one element; empty is refused, because a document that emits a zero-band
  program is a document that should not exist. **Exactly one of `bands` or `ramp` is
  required** (ruling Q1a for `bands` alone, widened by EFFECTS-W1 item 6's `ramp` and the
  contract's top-level `oneOf`): both channels lower into the same `EffectsPreset.ep_raster`
  slot, so a document naming neither or both is refused. A cycle-only or variant-only
  document with neither `bands` nor `ramp` is a future contract change, and it is the one
  that unblocks retiring the hand twins.
- **`preset-ignored`** — `name` is the writer's display label. Any value; read by nothing;
  dropped on lowering. It is the one deliberate writer-only field.
- **`preset-refused`** — `fires` is refused **by name**, with the reason. It is the last of
  `empyrean` `docs/AURORA_EFFECTS_SCHEMA.md` §7's reserved wave-2 vocabulary that this
  generator has not built, and it is not an unknown key: the suite has agreed on the name.
  `variants` and `cycles` were here until 2026-09-02 and are now built (DoD item 5).
  Anything else unknown is refused as an unknown key, and adding one is a contract change to
  both halves.
- **`band`** — all four required, **none with a default**, `sh` included. That is deliberate:
  `raster_dsl.emp`'s `region_boundary` note is that whether an effect changes a mode register
  is worth stating at the call site, and a JSON default would restore the silence that ruling
  removed. `sh` accepts a JSON boolean or the integers `0`/`1`.
- **`on-arms`** — exactly one. Zero arms, two arms, or an unknown arm are refused. Two arms
  would be two writes and therefore two restores, which is two bands. `vsram` is absent on
  purpose: a band's restore is derived from the ON op's CRAM span, and a VSRAM op has none.
- **`on.cram` / `on.pal_region`** — every listed field required, no extras. `colours` is a
  JSON array of integers; every other field is a bare integer.
- **`cycles`** — the section's ONE palette cycle script, spelled as its array of channels.
  **This is PALETTE cycling** (`Palette_DoCycle`), not the DEBUG hotkey's raster cycle table
  in §C, which steps through raster *programs*. Three states, one spelling each: the key
  **absent** keeps the section's hand-authored cycle; **`null`** turns cycling OFF; a
  **non-empty array** is the authored script. An **empty array is refused**, naming the two
  legal spellings. One or two channels today — `engine/effects/palette_dsl.emp` declares
  `cycle_script1` and `cycle_script2` and nothing wider, so three is refused naming the
  wrappers.
- **`cycle-channel` / `cycle-channel-optional`** — `line`, `first`, `count` and `period` are
  required; `dir` is optional, because it is the only field `cycle_channel()` itself
  defaults. **`period` is in FRAMES, the author's unit**: `period: 9` means a rotation every
  9 frames. The engine's timer rotates one frame after the byte says, so the generator emits
  `period - 1` and the author never sees the quirk (ruling Q7). The one consequence: the
  smallest period a document can carry is **2**, and the generator refuses `0` or `1` naming
  *your* number rather than letting the engine complain about a number you never wrote.
- **`variants`** — the palette variant descriptors this section binds, **positionally**:
  index *i* is the staging slot `Palette_SetVariant` takes, and it is the same integer an
  `on.pal_region.slot` in this same document names. Three states per INDEX: an index the
  array does not reach (including an absent `variants` key) **keeps** that slot's
  hand-authored value; **`null`** at an index **clears** it; an object **authors** it. There
  is deliberately no key-level `variants: null` — clearing both slots is `[null, null]`, and
  a key-level null is refused by name. Two slots; a third is refused naming
  `PAL_MAX_VARIANTS`. Every field is optional because every one has a constructor default,
  which is what lets the shipped deep-water variant be `{"shift_r": 1, "shift_g": 1}`
  verbatim. `lines` is the **integer bitmask** the engine field is (ruling Q4) — a friendlier
  spelling is the editor panel's job, not the wire's, and the generator will not grow a
  second one.
- **One cross-field rule, and it is the only one:** a band that streams from a slot the same
  document sets to explicit `null` is refused. Saying "clear this slot" and "stream from this
  slot" in one file is never what anyone meant. A band naming a slot the document simply does
  not reach is **not** refused — that slot still holds the section's hand-authored value,
  which the generator cannot see.
- **`patch_world_ys`** — the world anchor of each patch channel, **positionally**: index *i*
  is patch channel *i*, the same integer a `patchable(ch: i, ..)` record or a
  `SceneAnchor.At(i, ..)` scene names. Same three states per INDEX as `variants`: an index
  the array does not reach (or an absent key) **keeps** the section's hand-authored anchor;
  **`null`** is the engine sentinel `PATCH_ANCHOR_NONE`, i.e. *this channel is unused*; an
  integer **authors** it. Four channels; a fifth is refused naming `RASTER_MAX_PATCH`, and
  nothing downstream would have caught it. There is no key-level `patch_world_ys: null`.
  **⚠ THE UNIT IS WHOLE PIXELS, absolute, in level space, and NEITHER SIDE CONVERTS — 1:1.**
  This is *not* the scene document's `drift.rate`, which is 1/256 px per frame with the
  editor multiplying by 256 on export. A world Y carried through that habit lands 256x down
  the level and the band simply never appears; there is no error, because the engine derives
  the screen line as `anchor - Camera_Y` and a huge anchor is just off-screen-below.
  **⚠ `0` IS A REAL WORLD Y AND IT IS THE WORST ONE** — it reads as *above the screen top*,
  the most invasive state a channel nobody asked for can have. "Unused" is `null`.
  Range `0 … 65535` (the engine field is `u16`), and **`32767` is refused**: it is
  `PATCH_ANCHOR_NONE` itself, so writing it as an integer reads as an authored anchor to
  every human and as "unused" to the runtime. Both bounds are enforced here and in the writer
  schema, and both are owed that because *nothing else enforces them* — `preset()` checks the
  array's length, never its values.
- **`patch_motion`** — the motion of each patch channel, positionally and with the same three
  states. **`null`** is `ANCHOR_MOTION_NONE`, a static channel; an object is
  `{"sweep": { .. }}`. **`sweep` is the only arm.** There is no `approach` arm and none is
  reserved: APPROACH has no preset seed field at all, its runtime handle is the call
  `Effects_SetTargetY`, and a reserved arm would be a key with nothing behind it. Adding one
  is its own contract change. A sweep on a channel this same document sets to `null` is
  refused — a displacement with no anchor to displace.
- **`ramp`** — the dense-tier alternative to `bands` (EFFECTS-W1 item 6): ONE linear
  per-scanline vertical-scroll run, never an array (a preset has exactly one `raster:`
  channel, so there is one ramp per document). A single closed object with all five of
  `top` (3..222), `lines` (1..220), `target` (`{"vsram": {"addr": 0..78}}` — the only arm;
  a `cram` arm is refused, since nothing reserves one until its own contract change),
  `start` and `step` REQUIRED, none defaulted. **`start`/`step` are `fp16` OBJECTS,
  `{"whole": -512..511, "frac256": 0..255}`, and MUST be** — a raw integer is refused,
  because the generator emits `fp16(whole, frac256)` verbatim and that is the only thing
  standing between an authored value and `raster_ramp_program()`, which carries no range
  ensure of its own on either field. **Value is NOT `whole + frac256/256`** for a negative
  `whole` — that naive reading is wrong by up to a whole pixel. `fp16()`'s real rule:
  non-negative `whole` adds the fraction (`whole + frac256/256`); negative `whole`
  SUBTRACTS it, so the fraction ADDS TO THE MAGNITUDE going more negative. So `{"whole":
  -1, "frac256": 128}` is `-1.5`, not `-0.5`, and this is asserted through `fp16()` itself
  in `engine/effects/raster.emp` (a build-time witness `ensure`, not a schema-side
  restatement) so a later "simplification" of the emission cannot silently disagree with
  it. **⚠ A REAL GAP: `fp16` cannot spell any value in the open interval `(-1, 0)`** —
  `whole: 0` covers `0` to `+0.996`, `whole: -1` covers `-1.0` to `-1.996`, and nothing
  covers, e.g., `-0.5`. There is no fix in this generator or engine for that; an author
  wanting a slow upward ramp meets this gap directly, and a converter should return "not
  representable" rather than snap across it (snapping silently doubles the rate). **No
  `curve` key**: the object is closed, and a ramp authors exactly one rate and one starting
  offset — `RasterRampProgram` has no field that could receive a per-line table. **A VSRAM
  target's value `j` displays on screen line `top + j + 1`**, the N+1 VSRAM latency; the
  constructor does not compensate and NEITHER DOES THIS GENERATOR — `top`/`lines` are
  forwarded verbatim with no `+1` or other adjustment anywhere on this path; the only place
  display-lag compensation legitimately exists is an editor's own preview. Whether this
  game declares `CAP_DENSE_TIER` in its `SCANLINE_CAPS` is checked too — a game that has
  not is refused at the generated call site rather than silently building a program the
  interpreter no-ops.
- **`sweep` / `sweep-optional`** — `amp_shift` and `period_shift` are required, `phase` is
  optional (it is the only field `anchor_sweep()` itself defaults). **⚠ ALL THREE ARE
  QUANTIZED, and the first two are BASE-2 LOGARITHMS, not pixels or frames**: the peak
  excursion is `256 >> amp_shift` px and one cycle is `256 << period_shift` ticks, so there
  are **7 amplitude rungs and 9 period rungs** and adjacent rungs differ by a **factor of
  two**. A UI control must SNAP; the generator forwards the value untouched and
  `anchor_sweep()` refuses an off-ladder one with the whole derived ladder in the message,
  because rounding a rung silently doubles or halves the motion. `phase` is in sine-table
  entries, `0 … 255` is one full cycle, and it is the only continuous field — it exists so
  that two channels at the same period do not move in lockstep and read as one boundary.
- **What no one can check for you:** a sweep's peak-to-peak travel has to stay inside its
  channel's `patchable(lo, hi)` band. Leaving it upward does **not** clamp —
  `Raster_BuildSchedule` deletes the record for the frame, so the band *vanishes* and returns
  at the next zero crossing, which reads as a rendering bug rather than as an amplitude
  anyone chose. `lo`/`hi` live in the raster program and the amplitude in the preset, so no
  compiler scope holds both; `tools/test_anchor_sweep_band.py` is the check that does.

**Serialization is normative** (contract §5): a preset document is a *scalar* document, so
`json.dumps(obj, sort_keys=True, indent=2)`. Keys sort alphabetically and **recursively** —
the band objects and the arm bodies sort too. That is why the example below reads
`bot, on, sh, top` rather than in the order a human would type them.

---

## C. THE HONEST LIMIT — read this before describing the feature to anyone

**An author can write the document and the band will be in the ROM. Attaching it to
anything a player reaches still requires a programmer to edit `.emp`.**

Two separate gaps, and they are not the same size:

1. **Nothing binds a preset to a section.** A raster program is an `EffectsPreset` channel
   (`ep_raster`, `engine/effects/preset.emp`) and presets are bound per section by
   hand-authored `preset()` calls in `games/sonic4/data/effects/ojz_effects.emp`. The
   generator emits the words and binds nothing; the per-section sidecar key that would carry
   the assignment (`effectsRef`, `empyrean` §7) is **not implemented in either repo**. So an
   authored preset costs ROM whether or not anything installs it.
2. **Seeing it at all is a DEBUG chord.** `Debug_BandDemoHotkey`
   (`games/sonic4/test/ojz_scroll_test.emp`) steps a table: `START` held + `UP` installs the
   next program, `START` + `DOWN` removes it. Rows 0 and 1 are hand-authored
   (`OJZ_BandDemo`, then `OJZ_BaseSwap` — EFFECTS-W1 item 11a's mid-frame plane-base change,
   which is a raster program but not a band); the editor-authored rows follow. **That table
   is a hand-typed `dc.l` list** — a new preset
   document does not appear in it by itself. `tools/test_raster_cycle_table_lint.py` fails
   the build's pytest lane if a preset document has no row, so the omission is loud rather
   than silent, but the fix is still a programmer's edit.

So the accurate sentence is *"an author can author a raster band, and a programmer wires it
up in one line"*. **The inaccurate sentence, which this page exists to prevent, is
"authoring effects no longer needs a programmer".**

**One more limit, stated because a silence reads as coverage:** nothing checks that a band is
*visible* — that the CRAM entry it repaints is used by pixels on those rows, or that the
colour differs from the base. A perfectly legal band over an unused palette entry builds
green and shows nothing.

---

## D. The first real document, and what it becomes

`games/sonic4/data/editor/effects/presets/authored_probe.json`:

```json
{
  "bands": [
    {
      "bot": 156,
      "on": { "cram": { "addr": 74, "colours": [ 14 ] } },
      "sh": false,
      "top": 112
    },
    {
      "bot": 216,
      "on": { "cram": { "addr": 74, "colours": [ 3584 ] } },
      "sh": false,
      "top": 172
    }
  ],
  "id": "authored_probe",
  "name": "Authored probe (red / blue)",
  "schema": 1
}
```

*(the committed file is the same document with `sort_keys=True, indent=2` exactly — the
arrays are expanded one element per line; it is reproduced compactly here for reading.)*

Why these numbers, since every one of them is a choice an author has to make:

- **`addr: 74`** (`$4A`) is not invented. It is `OJZ_TEST_CRAM_ADDR` — CRAM line 2, entry 5,
  the address already measured as OJZ's single most-used ground colour (~54% of lower-screen
  pixels). A band anywhere else on that palette line is legal and would mostly repaint
  nothing. `$4A >> 5 = 2`, which is also what makes it legal at all: both `stream_cram` and
  the derived `pal_restore` refuse palette line 0, the character's line.
- **Lines 112..155 and 172..215** sit inside the region that address dominates, and inside
  `fire()`'s `3..223`. Heights are 44 rows each, an order of magnitude above the minimum a
  one-word CRAM band needs.
- **The 16-line seam** (156 → 172) is not styling. Contiguous bands put a restore and an ON
  op on the same fire line, which `check_landings` refuses; the seam also gives a reviewer
  base colour to compare against *inside* the effect.
- **`14` (`$000E`, pure red) and `3584` (`$0E00`, pure blue)** are deliberately NOT the act's
  palette. The hand-authored `OJZ_BandDemo` uses three subtle steps of OJZ's own ground ramp,
  because it is trying to look like art direction. This one is trying to be
  **unmistakable and unmistakably not that one**: two saturated bands against three muted
  ones is a difference nobody has to squint at, which is the whole point of having a
  hand-authored control in row 0 and an editor-authored program after it. (The editor rows
  moved from index 1 to index 2 when `OJZ_BaseSwap` joined the table; the comparison the
  sentence describes is unchanged — it is between the hand-authored bands and the
  editor-authored ones, and `OJZ_BaseSwap` is neither, it is a register op.)
- **`sh: false`** on both. Shadow/Highlight emits a third fire and a de-mix write; mixing it
  in would make a failure ambiguous between the band machinery and the S/H machinery.

It lowers to, in `games/sonic4/data/generated/ojz/act1/effects_scenes.emp`:

```
const EditorRasterSrc_OJZ_Act1_authored_probe = compose([
    band(top: 112, bot: 156, on: stream_cram(addr: 74, colours: [14]), sh: 0),
    band(top: 172, bot: 216, on: stream_cram(addr: 74, colours: [3584]), sh: 0),
])
pub data EditorRaster_OJZ_Act1_authored_probe: [u16; raster_words(EditorRasterSrc_OJZ_Act1_authored_probe)] = raster_program(EditorRasterSrc_OJZ_Act1_authored_probe)
```

Every `ensure` in `band()` / `stream_cram()` / `fire()` / `compose()` / `raster_program()`
and both ownership walks fires on those numbers, in **both** shapes — a `pub data` in a
lowered module is elaborated unconditionally. There is no softer class for editor content.

---

## E. What a band panel has to get right

1. **Write to `presets/<id>.json`, not to the scene file.** A `bands` key on a scene file is
   refused by the scene loader's unknown-key path, deliberately.
2. **`id` == the filename stem.** The loader refuses a mismatch, because the id becomes a
   symbol and the filename is how a human finds the file.
3. **Emit all four band fields every time**, `sh` included. There is no default to fall back
   on, in the JSON or in the engine.
4. **Do not validate ranges, and do not clamp.** Forward what the author typed. The build
   refuses it with a sentence that names the hardware budget behind the rule — for example
   `fire: screen line 999 outside 3..223 (lines 0-2 belong to the priming records)`, or
   `band: height 1 is below this ON op's minimum — the ON fire costs 624 cyc against 488
   available`. A clamp replaces that with silence.
5. **Serialize canonically** (§B): `sort_keys=True, indent=2`.
6. **Expect the honest limit** (§C). A panel that says "saved — your band is now in the game"
   is lying; "saved — a programmer has to bind it to a section" is not.

---

## F. Where this is booked

`docs/DEFERRED_WORK.md`, "RASTER BANDS ARE AUTHORABLE AND UNBINDABLE" and its 2026-08-29
follow-up. The section-binding half is flagged for the owner rather than decided: wiring it
means editing shipped `preset()` calls, which changes what boots — a content decision with a
picture attached.
