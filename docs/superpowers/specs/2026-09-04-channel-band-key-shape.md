# The channel-to-band link's key shape — the moving band a document cannot declare

*Status: **ANSWER ARTIFACT, documents only.** Nothing here is implemented; this parcel moves
no ROM byte and runs no build. Written because aurora's timeline strip is blocked on a
question aeon owns, and because "not without engine work" is a real answer that needs the
work named rather than gestured at.*

*Authored against `origin/master` `d8baf84f`. Every `file:line` was opened in that tree in
this pass.*

**The short version, before the evidence, because two of the three answers are surprising:**

1. **For `$defs.band` as it exists — NO, not without engine work**, and the arity is not an
   accident: a `band` is an ON fire *plus a derived restore*, `patchable()` takes exactly
   one fire, and `band()`'s own banner says so as a ruling. §3.
2. **For a NEW sibling key — YES, today, with zero engine work.** The shipped moving water
   boundary is not a `band()` at all; it is `patchable(fx_tint_band(...), ch, lo, hi)`,
   which is ONE fire. A `boundary` key lowering to exactly that call needs nothing from the
   engine. §4. **This is the one the hub should file.**
3. **And for aurora's *drawing* problem specifically there is something cheaper than
   either** — the generator already walks the `.emp` library collecting channels and simply
   does not publish the bands it walks past. §5.

---

## 1. The hub's claims, checked

| claim | verdict |
|---|---|
| a preset band declares `top/bot/sh/on` and no channel index | **CORRECT.** `contract/schema/aurora-effects-preset.schema.json` `$defs.band`: `required: [top, bot, sh, on]`, no other property, and the lowering forwards exactly those four (`tools/effects_gen.py:1849-1863`) |
| `$defs.band` is closed | **CORRECT** — `"unevaluatedProperties": false` |
| the only link between a patch channel and its screen band lives in hand-authored `patchable(fires, ch, lo, hi)` | **CORRECT** — `engine/effects/raster_dsl.emp:460`. The only two live calls in the whole game are `games/sonic4/data/effects/ojz_effects.emp:1502` and `:1504` |
| `tools/effects_gen.py:1276` greps the `.emp` library for it | **CORRECT, exact line** — `for m in re.finditer(r"patchable\s*\(", src):` inside `_collect_live_channels` (`:1267-1283`), which also collects `SceneAnchor.At(ch)` at `:1280-1281` |
| a document cannot declare one | **CORRECT** — `PRESET_KEYS` (`:306-307`) has no channel key on any band, and `_check_keys` (`:715`) refuses unknown keys |
| a sweep whose travel leaves the band is **not clamped**; `Raster_BuildSchedule` drops the record and the band vanishes | **CORRECT AT THE `hi` EDGE, WRONG AT THE `lo` EDGE, AND THE ASYMMETRY IS DELIBERATE.** `engine/effects/raster.emp:1979-1980`: `cmp.w 2(a0), d2 / bgt .suppress` — **past `hi` the record is removed.** `:1981-1983`: below `lo` it is **clamped UP** and still emitted, *"because the frame-top ship covers what is above."* The one-sentence statement of the rule is in the shipped source at `ojz_effects.emp:1494-1499`: *"clamping UP is covered, clamping DOWN was not"* |
| …until the next zero crossing | **NEARLY.** The record returns on the first frame the latched line comes back inside the band — for a sine sweep that IS once per half-cycle, so the observed symptom (a band flickering out once per cycle) is right; the mechanism is "L re-enters `[lo, hi]`", not "the sweep crosses zero" |
| the key an editor can act on is `ch -> (lo, hi)` | **AGREED, and I would go further:** it is the only pair from which the warning can be derived, because the other half of the comparison (`amp_shift` → peak = `256 >> amp_shift` px) is already a document key (`patch_motion`, landed 2026-09-03) |

**One stale cite found in passing, worth a line because it will mislead the next reader.**
`engine/effects/raster.emp:2036` says *"Raster_BuildSchedule clamps it (:895-901)"* and
`:2045` says the channel *"clamps at BOTH edges."* Both are stale: the clamp is at
`:1979-1983`, not `:895-901` (which is `raster_ramp_program`'s sign pin), and at the `hi`
edge it is a **drop**, not a clamp. The *behaviour* is correct everywhere it matters — the
parallax consumer at `engine/level/parallax.emp:2124-2143` handles the drop explicitly and
says so — it is only this one banner that describes the old shape. **Not fixed here** (no
engine writes in this parcel); named so the CR does not inherit it.

---

## 2. The distinction everything turns on: a BAND is two fires, a BOUNDARY is one

This is not terminology. It is why the answer to "can a document declare a moving band"
is two different answers depending on which thing is meant.

| | **boundary** | **band** |
|---|---|---|
| constructor | `fx_tint_band(line, slot, pal_line, entry, count, sh)` → `region_boundary(...)` | `band(top, bot, on, sh)` |
| cite | `raster_dsl.emp:654-663` → `:436-443` | `raster_dsl.emp:689-760` |
| fires emitted | **1**, always — `sh: 1` adds a second *op* to the same fire, not a second fire | **2** (`sh: 0`) or **3** (`sh: 1`) |
| what it does | switches the palette at a line and **never switches back** | turns on at `top`, and a **derived** `pal_restore` puts the base payload back at `bot` |
| patchable? | **YES** — this is what the shipped water uses | **NO**, by ruling: *"Static by construction — BOTH fires (spec §4.2 rule 6); not handable to `patchable`"* (`raster_dsl.emp:678`) |
| reachable from a document? | **NO** — no key lowers to it | **YES** — `$defs.band`, and it is the only raster shape a document can author besides `ramp` and `base_swap` |

**The two columns are exactly inverted.** The shape a document can author cannot move; the
shape that moves cannot be authored. That is the whole blocker, stated as one table.

---

## 3. Can `$defs.band` carry a channel? — **NOT WITHOUT ENGINE WORK.** Worked out, not asserted.

The hub's framing was right to be suspicious: *"a band is an ON fire plus a derived restore,
so 'make this band patchable on channel ch within [lo,hi]' is not obviously one fire."* It
is not one fire, and three separate things stop it:

1. **The arity guard.** `patchable()` opens with `ensure(fires.len == 1, ...)`
   (`raster_dsl.emp:461-462`), and its message gives the reason rather than the rule:
   *"Marking a multi-fire preset would clamp all of its fires onto one line, because they
   would share a single world anchor."* `band()` hands it 2 or 3.

2. **The patch record has room for ONE line.** The table entry is
   `[line_src][band_lo_fl][band_hi_fl][rec_off][rec_len]`
   (`raster.emp:1941-1943`) — one `line_src` per record, and `Raster_BuildSchedule` derives
   exactly one fire line from it (`:1972-1978`). There is nowhere to put the second edge.
   Guard 11 closes the obvious workaround: **two patchable records may not share a channel**
   (`raster_dsl.emp:3144-3166`) — *"Raster_GetChannelBand returns the first match, so the
   parallax overlay would follow one record while the palette follows the other."*

3. **Moving one edge is not a degraded version of moving two — it is a frame-killer.** The
   schedule's arm word is a *relative* gap, `L[k] - L[k-1] - 1`, written as a byte
   (`raster.emp:1987-1989`). If the ON edge moved below its own restore, that gap goes
   negative and stores `$FF`, **which is the park word**, killing every remaining fire in
   the frame — stated at `raster.emp:2038-2040` and again in `Effects_LatchWorldLines`'
   banner. So "move the top only" is not a cheap first version; it is a version that has to
   grow a clamp and a degenerate-height case before it can ship at all.

**So the engine work, named:** a `patchable_band()` constructor that marks a 2/3-fire list;
a patch record widened by one word (a height, or a second `line_src` derived from it) — the
band-ownership design's own price, *"+2 B/patch record and ~+8 NOMINAL cycles per patchable
record per VBlank (unmeasured)"*; and a `Raster_BuildSchedule` that emits both edges from
one latched L. **That is `2026-09-02-moving-bands-anchor-mover-design.md`'s Q5 verbatim**
("P3 — both edges moving"), deferred there to *"only if the owner asks."* Booked below.

**⚠ Q4 is NOT this question**, and the brief's guess should be corrected rather than
accepted. Q4 asks whether a free-running `Rate` that wraps its band is wanted at all — a
taste question about a *motion law*, not about how many edges a motion applies to. It is
untouched by anything here and stays open on its own terms.

---

## 4. THE KEY THAT IS POSSIBLE TODAY — `boundary`, a fourth exclusive arm

The shipped moving water is this, and it has been in the ROM since Parcel P
(`games/sonic4/data/effects/ojz_effects.emp:1501-1505`):

```
patchable(fx_tint_band(line: 100, slot: 0, pal_line: 2, entry: 4, count: 3, sh: 1),
          ch: 0, lo: 3, hi: 220, offscreen_ship: 1)
```

One fire. Every argument a plain integer or an existing `$defs` shape. **A document key
lowering to exactly this call requires no engine change of any kind.**

```json
"boundary": {
  "line": 100,
  "channel": 0,
  "lo": 3,
  "hi": 220,
  "offscreen_ship": true,
  "on": { "pal_region": { "slot": 0, "pal_line": 2, "entry": 4, "count": 3 } },
  "sh": true
}
```

| key | type / range | who enforces | note |
|---|---|---|---|
| `line` | integer 3..223 | **engine** — `fire()` (`raster_dsl.emp:360-361`) | the template's DEFAULT schedule, i.e. where the boundary sits before any patch. `patchable` additionally refuses a `line` outside its own `[lo, hi]` (`:475-476`) |
| `channel` | integer 0..3 | **engine** — `ch >= 0 && ch < RASTER_MAX_PATCH` (`:463-464`) | the SAME index space as `patch_world_ys` / `patch_motion` / the scene's `anchor.at.channel`. Authored, never an encoder-assigned ordinal (`:452-455`) |
| `lo`, `hi` | integers, `3 <= lo <= hi <= 223` | **engine** — `:465-467` | **SCREEN lines, not fire lines.** The engine converts once, `subq.w #1` at `raster.emp:1977`. An editor that subtracted 1 would be the exact class of bug §4b of the item-4 note forbids |
| `offscreen_ship` | boolean | **engine** — `:477-478`, plus `:486-487` requiring exactly one `stream_pal_region` op to re-ship | true is what makes the band survive the camera leaving `[lo, hi]` at the `lo` end |
| `on` | `{pal_region: …}` | reuse `$defs.pal_region` unchanged | `fx_tint_band` derives `addr` from `pal_line`/`entry` (`:657`), so the document must NOT carry `addr` — one fact computed twice |
| `sh` | boolean / 0-1 | **engine** — `region_boundary` (`:438`) | same shape as `$defs.band.sh` |

**Every value forwarded VERBATIM, 1:1.** No unit conversion on any field, the standing rule
this seam already states for `patch_world_ys` (`tools/effects_gen.py:3008-3013`: *"there is
no `* 256` anywhere on this path and there must never be one"*).

**Three states**, the house rule: **absent** = the section keeps whatever raster/patched
program it had; **`null`** = explicitly off (`Raster_Program_None`); **object** = authored.

**⚠ IT IS A FOURTH EXCLUSIVE ARM, AND IT LANDS IN A DIFFERENT ENGINE CHANNEL THAN THE OTHER
THREE.** `bands`/`ramp`/`base_swap` all lower into `EffectsPreset.ep_raster`
(`tools/effects_gen.py:721-725`). A `patchable` fire list lowers into **`ep_patched`**, via
`patched_program()` / `patched_words()` (`raster_dsl.emp:3564`, `:3576`), and `preset()`
refuses a preset carrying both — `ensure(raster == 0 || patched == 0, ...)`
(`engine/effects/preset.emp:153-154`), destructively-install-order being the reason. So
`boundary` joins the `oneOf` group as a fourth arm, and the CR must say **why** it is
exclusive with the other three for a *different* reason than they are with each other: they
compete for one field; this one competes for a mutually-exclusive sibling field.

**What refuses, and who owns it:**

| refusal | owner | why there |
|---|---|---|
| `line`, `channel`, `lo`, `hi`, `sh`, `offscreen_ship` ranges | **engine `ensure`s**, restated in the schema as plain per-field bounds | every one is a single-field range; the schema restating them lets the editor's controls refuse before export, and the engine message carries the measurement |
| `line` outside `[lo, hi]` | **engine** (`raster_dsl.emp:475-476`); schema **cannot** express it | a cross-field conditional inside one object is writable in JSON Schema and unreadable; the generator can and should also check it, since all three numbers are in the document |
| `addr` present on `on` | **generator**, by name | `fx_tint_band` derives it; a document carrying it is two sources for one byte |
| `boundary` alongside `bands`/`ramp`/`base_swap` | **generator** (`effects_gen.py:726-750`, widened) | this file *is* the build gate; no schema validator runs against these documents in this repo (its own words at `:724-725`) |
| **travel leaves `[lo, hi]`** | see §6 | |

---

## 5. The cheaper thing, for aurora's DRAWING problem only

Aurora's stated blocker is that its timeline strip *"structurally cannot draw a band that
moves"* — it has no way to know which channel a band belongs to or what band it is confined
to. **Drawing needs only to READ the pairs; authoring needs the key.**

`_collect_live_channels` (`tools/effects_gen.py:1267-1283`) already opens every `.emp` in
`games/<game>/data/effects`, regex-matches every `patchable(` and reads its `ch:` — and
throws the `lo:`/`hi:` on the floor. Extending that walk to capture the two bounds and
emitting a generated read-only sidecar (`ch -> {lo, hi, source}`) is a `tools/` change of
perhaps twenty lines, no schema, no engine, no contract amendment — and it would let the
strip draw the shipped water band and warn about a too-wide sweep **before** any of §3 or
§4 lands.

Stated as an option rather than proposed as a parcel: it is aurora's call whether a
published-derived-fact sidecar is worth having when the authoring key is the real goal. It
is named here because it is strictly cheaper than both other answers and nobody had costed
it.

---

## 6. (b) What does the anchor move — **BOTH EDGES, RIGIDLY. This is aeon's call and it is Q5.**

**The decision: when a band becomes patchable, the anchor translates the WHOLE band — both
edges move by the same delta, the height is a constant of the record.**

Four reasons, in the order that decides it:

1. **It is what every effect in the corpus that wants this actually is.** A water surface
   band, a light shaft, a shadow conveyor, a heat band: all rigid. Nothing in the S3K / SCE
   / Ristar / Gunstar survey behind item 4 moves one edge of a palette band while pinning
   the other. A shape-changing band is a different effect and should be asked for by name.
2. **Rigid motion makes the ordering invariant STRUCTURAL rather than checked.** §3's third
   point is the failure: if ON can pass OFF, a negative inter-record gap stores `$FF`, the
   park word, and the rest of the frame's fires die. Under rigid motion `top' < bot'` for
   every delta because `bot' - top' = bot - top` by construction. **The alternative buys a
   runtime clamp, a degenerate-height case, and a class of bug that presents as "the screen
   below the band went blank."**
3. **Top-only needs MORE record space than rigid, not less.** Rigid needs one height word
   (+2 B). Top-only needs the restore's line *and* a clamp against it, and then has to
   decide what a zero-height band means.
4. **It costs the number the design already priced.** +2 B per patch record, ~+8 nominal
   cycles per patchable record per VBlank (unmeasured, and the "unmeasured" is the design's
   own word — not re-derived here).

**Is this Q4/Q5? — Q5 YES, verbatim. Q4 NO.** `2026-09-02-moving-bands-anchor-mover-design.md`
§11 Q5 is *"OWNER CALL: P3 (both edges moving)… Nothing in this design forecloses it."*
That is exactly this question and this section answers it: **when it is built, it is built
rigid.** Q4 — whether a free-running `Rate` that wraps its band is wanted — is a separate
taste question about the motion law and is **not** answered here, and the brief's guess that
the two are the same question should be corrected in the hub's record.

---

## 7. (c) Who owns the travel-leaves-band case — **neither the engine nor the editor. It is
already owned, by a build-fatal pytest lane, and the key MOVES it.**

**The finding first: the check exists.** `tools/test_anchor_sweep_band.py` is in the tree at
`d8baf84f`, runs in build.sh's `pytest tools` lane (build-fatal on the canonical path,
skipped under `FAST=1`), and its red-first mutation is recorded in its own docstring:
raising `ojz_effects.emp`'s `anchor_sweep(amp_shift: 4, …)` to `amp_shift: 1` fails with
*"channel 0: peak-to-peak 512 px does not fit band 3..220 (218 lines)"*. It already grew a
second arm for the generated chooser shape. **Nobody needs to invent this check; the
question is only where it should live once a document owns both numbers.**

**Why it is NOT an engine `ensure` today, and this is a structural reason not a preference:**
`lo`/`hi` live in the raster program's `patchable(…)` call, `amp_shift` lives in the
preset's `patch_motion`, and the two are associated **by a pointer at runtime**. There is no
comptime scope in which both numbers exist — `tools/effects_gen.py:3026-3033` states exactly
this and names the pytest file as that scope. `anchor_sweep()` enforces the strongest
condition available to it alone (an amplitude wider than the screen), which is necessary and
not sufficient.

**What the `boundary` key changes:** both numbers become keys of documents the generator
reads — `boundary.lo`/`boundary.hi` and `patch_motion[ch]`, in the same document, bound to
the same section by the same `rasterRef`. **The check should then move into
`tools/effects_gen.py`**, beside `_check_patch_context`'s two existing refusals
(`:1300-1315` and `:1316-1333`), because that file is the actual build gate for documents
and its message can name the JSON path the author typed. The pytest lane stays as the
backstop for hand-authored `.emp`, which the generator never reads.

**And the editor's check is a WARNING, not a refusal, and it is worth having anyway.** The
argument for it is not redundancy, it is *when*: a build error arrives twenty seconds after
the author committed to an amplitude, and the aurora control can grey the rungs that do not
fit while the author is choosing. But it must never be the only check — a document can reach
the tree without passing through aurora, which is the same reasoning
`EFFECTS_CONSUMER_CONTRACT.md` uses for every other document field.

**Three owners, three jobs, none of them optional:**

| | owner | verdict shape |
|---|---|---|
| while authoring | aurora | warn, and show the rungs that fit |
| at bake | `tools/effects_gen.py` (once the key lands) | refuse, naming the JSON path |
| for hand-authored `.emp` | `tools/test_anchor_sweep_band.py` | fail the build, naming the module |

---

## 8. The booking, for aurora to name

`docs/DEFERRED_WORK.md` — **row `RASTER-CHBAND-1`**: *"A DOCUMENT CANNOT DECLARE A BAND'S
PATCH CHANNEL — `$defs.band` IS TWO FIRES AND `patchable()` TAKES ONE."* It carries §3's
three blockers, §4's zero-engine-work alternative, §5's cheaper drawing-only option and §6's
rigid-motion ruling. **Aurora's blocker should cite `RASTER-CHBAND-1`, not a rumour**, and
should say which of the three it is actually blocked on — because if the strip needs to
*draw* the shipped band, §5 unblocks it this week and neither of the other two is on the
critical path.

## 9. What this note did NOT settle

1. **Nothing here was built or measured on hardware.** Every claim is a source read at
   `d8baf84f`. The `+2 B / ~+8 cycles` price in §6 is quoted from the band-ownership design
   and carries that design's own "unmeasured".
2. **Whether `boundary` should carry a `vsplit` arm on `on`.** The shipped program's second
   patchable record is `fx_vscroll_split` (`ojz_effects.emp:1504`), one fire, equally
   authorable — but `patchable`'s `offscreen_ship` requires a `stream_pal_region` op
   (`raster_dsl.emp:486-487`), so a vsplit arm has a hole in it. Left for the CR.
3. **The stale banner at `raster.emp:2036`/`:2045`.** Named in §1, not fixed — no engine
   writes in this parcel.
