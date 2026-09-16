# Regions seam, part one: the loader, the flattener and the shared golden

Parcel `parcel/regions-loader-golden`, aeon, 2026-09-16. Step 2 of the **AURORA REGIONS EDITOR**
spec (`empyrean docs/superpowers/specs/2026-09-14-aurora-regions-editor-design.md`). ⚠ Not part
2's step 2 and not part 2's step 10 — the two specs number independently and the collision is
live; always name the spec.

No emulator, no running app. One build-artifact gate is written and marked; everything else reads
source and fixtures.

## 1. The finding that reshaped the parcel

**§5.2 of the spec describes an algorithm the owner overturned in §8 of the same document, and
the landed contract implements the overturned-to version.** §5.2 writes out a painter's-order
flatten: an act-wide bottom layer, later regions subtracted out of earlier ones, then an adjacency
merge to keep a cut from multiplying rows. §8 records the owner ruling **A, cut right away** on
2026-09-14T14:54:34Z — the editor trims rectangles at the moment of the draw, so `regions.json`
holds each region's own already-disjoint area, and, in the ruling's own words, *"flattening becomes
a check that the rows are disjoint and cover the act, not a subtraction."*

I did not have to infer the supersession: **§8 states it about itself**, naming §2.3, §2.5, §3.2
and §5.2 explicitly. What made it a trap is that §5.2's prose was never rewritten, so a reader who
stops there implements the superseded model — which is what my own brief did.

The landed schema (`contract/schema/aurora-regions.schema.json`, empyrean `c3f892f`/`ad03bd7`)
settles it independently: `{schema, act, regions[]}` with **one `rect` per region**, a **required
non-null `preset`**, no `defaults`, no `bindings` wrapper, no `rects` array. §2.3's document cannot
be written against it at all, and a subtraction flatten has no bottom layer to subtract from.

**One region is one rectangle is one row.** So §5.2's steps 1-3 are gone with the bottom layer;
step 4, the per-row rules, survives whole. What replaces them is the pair the ruling names.

They are not the weaker check. Subtraction made coverage true **by construction** and therefore
unfalsifiable. Under the ruling a hole is a thing an author can actually have, so `uncovered()` has
to be able to find one and name it — `tools/test_regions_doc.py` punches a hole on purpose and
requires the rectangle back, because `[]` is what a correct document produces *and* what a broken
instrument produces.

## 2. Act 1's ten rows came back exactly

The acceptance test, and it passed first run. The golden document flattens to act 1's ten release
rows — `index`, `id`, `x0`, `x1`, `y0`, `y1`, `preset`, `sceneRef`, `rasterRef`, row for row.

**It is not circular.** `tools/fixtures/regions/ojz_act1.rows.json` was typed by hand from
`act_descriptor.emp`'s `OJZ_ACT1_REGION_ROWS` and the constants it names, not produced by the
flattener it tests. Area 37 748 736 = 6144 × 6144, `first_overlap` None, `uncovered` empty.

A second, independent check is written and marked `needs_build`: `GATE ROWS-IDENTICAL` reads the
table out of the assembled `s4.bin` through `tools/region_table.py` (whose struct layout is parsed
from `engine/structs.emp`, not typed) and compares geometry per row **per axis**, `rg_effects`
resolved through the listing to the record the document binds, and `rg_parallax`
presence-for-presence against the document's own `sceneRef`.

**What the golden covers that a naive one would not.** The night region, `x 3400..4799`, straddles
the section line at 4096 and neither edge lands on a multiple of the 2048 section size. Without it
a document sits entirely on the section grid, and then nothing distinguishes a correct flattener
from one that quietly snaps to sections — and `sec1`/`sec2`, whose spans are the night region's
complement (1352 and 1344 px) rather than a section's width, never get exercised. There is a test
asserting the fixture still has that property, so a later tidy-up onto the grid fails loudly
instead of silently hollowing the fixture out.

## 3. The chooser question, priced

§5.2's last paragraph hands aeon a design item and does not settle it. **This section prices; it
does not decide.** Nothing here is implemented.

### 3.1 The measured ground

| fact | value | where |
|---|---|---|
| `struct EffectsPreset` | **46 bytes** | `engine/effects/preset.emp:57` |
| `struct Region` | **22 bytes** | `engine/structs.emp:121` |
| act 1 release rows | 10 | `act_descriptor.emp`, `OJZ_ACT1_REGION_ROWS` |
| distinct records those rows bind | **10 — bijective today** | same, `effects:` arguments |
| rows binding a preset DOCUMENT | 2 (`sec5`, `sec6`) | `section_{5,6}.meta.json` `rasterRef` |
| a `pub comptime fn` chooser's ROM cost | **0 bytes** | the generated module's own banners |
| generated module | 541 lines / 33 691 bytes | `games/sonic4/data/generated/ojz/act1/effects_scenes.emp` |
| chooser call sites inside hand records | 19 | `ojz_effects.emp` |

**⚠ `struct Region` is 22 bytes, not 16.** The spec's §2.1 read it at aeon `0dc0ff11`, before
regions part 2 step 1 added `rg_bg_layout` and `rg_bg_span`; §6's budget row ("16 per row") is
stale with it. Act 1's table is 10 × 22 = **220 bytes** release, 242 in DEBUG.

**The tree has already run this experiment by hand, twice.** `OJZ_Preset_Sec5` and
`OJZ_Preset_Sec6` exist only because the chooser is keyed on a section index and sections 5, 6 and
8 all pointed at the shared `OJZ_Preset_Plain`: *"threading `ojz_act1_sec_raster(sec: 5, ...)` into
the shared record would have given sections 6, 7 and 8 the same band."* Two records were split off
at 46 bytes each — **92 bytes of deliberate duplication, with the reasoning written at the site.**
That is the same problem this design item asks about, and the answer the tree reached under time
pressure was "duplicate the record per binding site".

### 3.2 A distinction §5.2 blurs, and it matters more than either option

§5.2 says "the choosers", as if they were one population called from one place. **They are two
populations called from two places**, and only one of them is the problem:

* **The scene chooser is ALREADY called from the region row.** `act_descriptor.emp` writes
  `parallax: ojz_act1_sec_scene(sec: N)` *inside* `ojz_region(...)`. Re-keying it from `sec:` to
  `row:` is the whole of its fix, it is mechanical, and it is independent of everything below.
* **The five preset-channel choosers** (`raster`, `patched`, `cycle`, `variant`, the two `patch_*`)
  are called from inside the hand-written `preset()` records in `ojz_effects.emp` — 19 call sites.
  A record does not know which row binds it. **This is the only part of the question that is hard.**

Fixing them with one mechanism, as "move the choosers to the row" suggests, is what makes the
problem look bigger than it is.

### 3.3 Shape A — the generator emits a per-row wrapper record

The generator emits, per region that binds a document, a new `EffectsPreset` copying the hand one
with the document's channels substituted; the row's `effects:` points at the wrapper.

* **ROM: a relocation, not an addition.** 46 bytes per document-bound region — **2 regions, 92
  bytes on act 1 today**; worst case, every region binds a document, 10 × 46 = 460. But the
  wrapper makes the hand splits unnecessary, so with `Sec5`/`Sec6` retired into `Plain` the steady
  state is 8 authored + 2 generated = 10 records = 460 bytes, **exactly what act 1 ships today.
  Zero delta.** (Under the ruled model the count is bounded by a number the author typed — one per
  region — not by a derived fragment count; that bound only existed under the superseded
  subtraction model.)
* **Generated file:** +1 `pub data` per wrapper. `OJZ_Preset_Sec5`'s argument list is 21 lines
  including two four-element arrays, so act 1's worst case is roughly +50..210 lines on a
  541-line module.
* **What it does to the hand-authored records — and this is the cost only the engine side can
  see.** To wrap a record the generator must **read a hand-written `preset()` call out of
  `ojz_effects.emp` and re-emit it with substitutions.** `effects_gen.py` today only *extracts*
  from that file — `section_preset_symbols`, `preset_parallax_bindings`, via `_enclosing_call_span`
  / `_arg_expr` / `classify_parallax_expr` — and has never re-emitted a line of it. This makes the
  generator a partial `.emp` parser and pretty-printer for a hand-authored file, and **its failure
  mode is silent**: a mis-copied argument still assembles. Those three extraction helpers exist
  precisely because parsing those call sites is delicate; this asks for strictly more.
* **Aurora:** a second class of record in the emitted library. **If this shape is chosen, the
  wrapper's name is DERIVED FROM THE REGION ID** (hub ruling on the option, banked at aeon
  `origin/master` `01ae4ed3`) — not from a prefix convention. A prefix answers the symptom: an
  author can name a record the same way and the filter stops working. `id` is `required` in
  `$defs/region` and unique within the act, so a name derived from it **cannot** be collided with,
  and aurora's read-back becomes a check rather than a filter: a wrapper whose id resolves to no
  region is a finding, where a pattern match would tolerate a stranger. It costs nothing — the
  wrapper needs a name either way — and it is only available because of the Q1 ruling: under the
  superseded subtraction model one region could become several rows, so no per-row name could have
  been the region id.
* **Contract:** unaffected. The program is still a channel of the record `preset` names.

### 3.4 Shape B — the choosers move to the row

**⚠ This phrase has two readings with very different costs, and §5.2 does not say which.**

**B1, the cheap reading: re-key the existing choosers from `sec:` to `row:`, call site unchanged.**
* ROM: **0 bytes.** No record changes; a `pub comptime fn` emits nothing.
* Generated file: unchanged size; six signatures rename a parameter and their `ensure` bound moves
  from the section count to the region count.
* Hand records: 19 mechanical call-site edits.
* **But a record baked with its own row number cannot be bound by two rows**, so it needs a new
  gate: *no `EffectsPreset` may be named by two region rows*. That gate forbids the normal way to
  express a non-rectangular area under the ruled model — an L-shape is two regions with one look —
  so an author hits it on an ordinary edit and pays a hand duplicate. **That is B1's real cost and
  it is not small.**
* Contract: unaffected — the program is still a channel of the record.

**B2, the expensive reading: the ROW carries the channel** (`rg_raster`, `rg_cycle`, … on
`struct Region`).
* ROM: +4 bytes per added pointer per row, on a 22-byte record — one pointer is 10 × 4 = 40 bytes
  on act 1 and the table grows 18%. Plus `Effects_InstallPreset` must merge record and row.
* Collides head-on with `struct Region`'s own standing comment: *"NOTHING ELSE … a field is added
  the day a consumer wants it."*
* **This is the reading that falsifies the landed schema's line 43 and §3** (`rasterRef` names a
  document whose program is a channel of the record `preset` names) — under B2 the channel belongs
  to the row. The document validates identically and every vector stays green while the sentence
  becomes false, so it needs a deliberate hub amendment, not a discovery. **That cost attaches to
  B2 only, not to B1.**

### 3.5 What I recommend — and it is neither, quite

**RECOMMENDATION: B1's mechanism with B1's gate replaced — re-key the five preset-channel choosers
from the SECTION INDEX to the PRESET RECORD they are already called from, and gate on agreement
rather than on uniqueness.** Call it **B′**. Separately and independently, re-key the scene chooser
from `sec:` to `row:`, which is §3.2's easy half.

How it works: the generator groups `regions[]` by `preset` and emits each record's arms from the
regions that name it. Two regions naming one record and one document: fine, one set of channels,
correct by construction — the L-shape case B1 forbids. Two regions naming one record and
*different* documents: **refused, naming both regions**, because that is a genuine ambiguity and
the author's own fix is to split the record, which is what they meant.

The arithmetic:

| | ROM delta (act 1) | generated file | hand records | aurora read-back | contract |
|---|---|---|---|---|---|
| A, wrapper | **0** (relocation) | +50..210 lines worst case | generator must re-emit them | second record class, needs a naming rule | unaffected |
| B1, re-key to row | **0** | unchanged | 19 mechanical edits | unchanged | unaffected |
| B2, row carries channel | **+40** per pointer | unchanged | unchanged | unchanged | **falsifies line 43 / §3** |
| **B′, re-key to record** | **0** | unchanged | 19 mechanical edits | unchanged | unaffected |

**Bytes do not decide this. Three of the four shapes are a zero-byte delta on act 1**, because the
92 bytes the wrapper "saves" are the 92 bytes it then spends. So the decision is about what new
capability the generator acquires and what an author hits on an ordinary edit, and on both counts
B′ wins:

1. **A asks the generator to become a source-to-source transformer of a hand-authored `.emp` file,
   with a failure mode that still assembles.** That is the single largest new capability in the
   whole comparison and it is the one nobody outside this tree can see. B′ asks for a parameter
   rename and a grouping.
2. **B′ keeps the emitted library equal to the authored one**, which is what lets
   `section_preset_symbols`, `test_lab_index_lint`, `preset_lab_witness` and aurora's
   `section-wiring.ts` go on reading one population of records. A is the only shape that splits it.
3. **B′ refuses only genuine ambiguity.** B1 refuses the L-shape, which the ruled model makes the
   normal way to draw a non-rectangle. A refuses nothing, at the price of point 1.
4. The case the hub flagged as still live — *two regions naming the same `preset` carry one
   region's channels* — is the case B′ is built around: agreement passes, disagreement is a
   refusal that names both regions.

**What I am accepting, stated rather than buried:** under B′ two regions that want the same record
with *different* raster documents must split the record, which is the 46-byte hand duplication the
tree already chose twice. I am not claiming that away; I am claiming it costs the same bytes under
every shape, and that B′ makes it an explicit refusal with both region ids in the message rather
than a silent wrong band.

**Nothing above is implemented.** B′ is a third shape, mine, not the spec's — flagged as such. If
the ruling is A, the wrapper's name is derived from the region id (§3.3), not from a prefix.

**A generalisation worth carrying past this ledger, and B′ is an instance of it:** prefer a key
**derived from a required unique field** over one that follows a convention. A convention is a
filter and can be collided with; a derivation is a check and its failures are findings. B′ groups
by the `preset` record name — a required field, and the same name the engine binds — rather than
by a positional index the generator assigns, which is why its refusal can name both offending
regions instead of reporting a mismatched count. Same family as deriving a gate's expectation from
source rather than copying it from a nearby pin.

## 4. What else this parcel measured

**A migrated act 1 does not bake, and it has nothing to do with regions.** Found in the sandbox,
not predicted. Null every sidecar `sceneRef` — which is exactly what `Migrate sections` does — and
`render_module` refuses: `ojz_act1_depth.json` carries a `reels` key, and the rung-1 rule requires
some SECTION to bind that scene through a `sceneRef` sidecar, because the reels table is keyed on
the pointer identity of `EditorSceneBinding_OJZ_Act1_Sec4`. With identity on regions there is no
such sidecar. **This blocks flipping act 1 into region mode** and it is asserted as a test so that
the day it is fixed, the test fails and tells its author to delete it.

> ⚠ **AMENDED 2026-09-16 by `parcel/regions-emit-bindings`: there are TWO extra DEBUG rows, not
> one, and they shorten THREE release rows between them.** `OJZ_TALL_BG_ROWS` (regions part 2
> step 5) is the twelfth, and it carves the right end off rows 5 and 8 the way the snap row
> carves row 2. Measured off the built images: release 10 × 22 = 220 B, DEBUG 12 × 22 = **264**
> B — this note's "11 × 22 = 242" is wrong on both factors. The ruling's named-row condition is
> unchanged and is owed three times. Left in place below rather than rewritten, because a reader
> coming from the ruling needs to find the sentence they remember before they find its
> correction.

**The DEBUG shape has an eleventh row a closed document cannot express.** `OJZ_E2_SNAP_ROWS` adds
a look fixture at `x 5600..6143` under `DEBUG` and shortens `sec2` to `x1 = 5599` to make room. A
`regions.json` has no shape key. So a generated table is release-shaped by construction, and the
emitter parcel must pick one of: retire the E2 fixture, amend the schema, or let the descriptor
apply the DEBUG delta on top of a generated release table. **An owner/hub call with byte
consequences; not made here.**

**The `bg.span` derived check is unreachable today.** `bg.layoutRef` is refused for every value but
`"@act"`/null while the engine has no consumer, so "a span must equal its referenced layout's
height" — the check only this generator can make, because the schema never sees the layout — has
nothing to check. The refusal for a typed `span` IS in and tested, on `ojz_region()`'s own third bg
ensure (`bg_layout != 0 || bg_span == 0`). The equality check is what the parcel that opens
`layoutRef` owes.

## 5. What reads this, and what state that reader is in

Named deliberately, because this parcel exists *because* an artifact was built and nothing consumed
it.

* **`tools/test_regions_doc.py` reads the rows today, and nothing else does.** `generate()` calls
  `check_mode_conflict` and stops; act 1's table is still hand-written in `act_descriptor.emp`.
  That is by design and it is what keeps the change reversible.
* **The first thing that will read them is the emitter**, in the second parcel, blocked on §4's
  first two items and on the chooser ruling above.
* **`check_mode_conflict` IS wired into the build path** and is inert on every act in this repo,
  because none has a `regions.json`. It is there so the first tree that grows one meets the
  refusal rather than a silently ignored sidecar.
* **Aurora's codec is not blocked on this** (corrected by the hub mid-parcel): their parcel is
  scoped to the schema, the read/write half, contract vectors and a drift gate, and will add a
  conformance leg against this golden when it lands. The golden is in the document's own
  vocabulary — `preset`, `sceneRef`, `rasterRef`, never `.emp` symbol names — so their side can
  check every field of it.

## 6. Red-first evidence

Three mutations, each applied to `tools/region_flatten.py` on disk, each diff shown before the run,
each restored with `git checkout HEAD --` from the committed baseline and the tree verified clean:

| mutation | result |
|---|---|
| `to_inclusive` off by one (`x + w` for `x + w - 1`) | **10 failed**, 46 passed |
| right-edge rule written as the left rule "mirrored" | the endpoint test fails at **x1 = 160 = `CENTRE_X_MIN`** — the exact edge the naive reading gets wrong |
| `uncovered()` short-circuited to `[]` | **2 failed**, including the instrument check |

The second is the one worth keeping: aurora measured that the naive transcription disagrees with
the engine on exactly two of this act's 6144 vertical edges, the band endpoints, so a test sampling
*near* the boundary cannot tell the readings apart. The test derives the disagreement set over the
whole axis and requires it to be exactly `{CENTRE_X_MIN, CENTRE_X_MAX}`, rather than copying either
number.
