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
preset:          bands, id, schema
preset-ignored:  name
preset-refused:  cycles, fires, variants
band:            bot, on, sh, top
on-arms:         cram, pal_region
on.cram:         addr, colours
on.pal_region:   addr, count, entry, pal_line, slot
```
<!-- /KEYS-CHECKED-AGAINST-effects_gen.py -->

Reading the seven rows:

- **`preset`** — all three required. `schema` must be `1`. `id` must match the filename stem
  and `^[a-z][a-z0-9_]{0,31}$`, because it becomes an `.emp` label component. `bands` is a
  list with at least one element; empty is refused, because a document that emits a zero-band
  program is a document that should not exist.
- **`preset-ignored`** — `name` is the writer's display label. Any value; read by nothing;
  dropped on lowering. It is the one deliberate writer-only field.
- **`preset-refused`** — `fires` / `variants` / `cycles` are refused **by name**, with the
  reason. They are `empyrean` `docs/AURORA_EFFECTS_SCHEMA.md` §7's reserved wave-2 vocabulary,
  not unknown keys: the suite has agreed on them and this generator has not built them.
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
   next program, `START` + `DOWN` removes it. Row 0 is the hand-authored `OJZ_BandDemo`;
   the editor-authored rows follow. **That table is a hand-typed `dc.l` list** — a new preset
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
  hand-authored control in row 0 and an editor-authored program in row 1.
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
