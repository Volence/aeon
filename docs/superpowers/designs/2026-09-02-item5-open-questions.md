# Item 5 open questions — grounded recommendations (2026-09-02)

*Branch `design/item5-open-questions`, worktree base aeon master `3967db33`. Documents
only: no code was written, no build was run, no emulator was touched. Cross-repo reads
are at empyrean `origin/main` = **`d8768c07`**, via `git show`, never through the sibling
working tree.*

*Every engine claim below is transcribed from source in THIS tree with `file:line`. Where
the spec (`docs/superpowers/specs/2026-08-30-item5-variants-cycles-key-shapes.md`, written
against aeon `82fb65a8` and empyrean `5a894756`) disagrees with what is in source or in the
hub today, the disagreement is named — §12 collects them. Anything derived rather than read
is labelled DERIVED; anything unverified is labelled so.*

---

## 0. HEADLINE — the hub has already ruled all ten, and the spec does not know it

The brief, and the spec's own §4 heading (*"Open questions for the owner or hub (listed,
not answered)"*), both treat Q1–Q10 as open. **They are not.** At empyrean `origin/main`
`d8768c07`:

- `docs/AURORA_EFFECTS_SCHEMA.md` **§7.2** — *"`cycles` and `variants` in preset documents
  (2026-08-30, DoD item 5, aeon demand artifact `8ec2b05d`)"* — is 100+ lines long, carries
  a subsection headed **"The ten rulings"**, and answers Q1 through Q10 by number, each with
  its reason, *"ruled by the hub in the owner's place, 2026-08-30, `docs/OVERSEER.md`, under
  the standing delegation"*. It also adds a **Q1a** the spec never asked.
- `contract/schema/aurora-effects-preset.schema.json` **already carries both keys as
  properties**, with the three-state semantics in their `description` strings, and its
  title now reads *"Aurora Effects Raster Preset Document (wave 2: bands, cycles,
  variants)"*. The reserved-and-refused line is down to `fires` alone.
- §7 was amended in place: *"`variants` and `cycles` are no longer reserved: both are
  specified in §7.2."*
- §3.1 was amended too: **`rasterRef` binds the WHOLE preset document, every channel the
  document carries** — that is the Q1 answer, written into the `rasterRef` section itself.

So this document is not "ten recommendations to send upward". It is **an audit of ten
committed rulings against aeon's source**, plus the two questions the rulings leave for us
(Q9's measurement, Q11's language call) and the ORDER the hazards impose. Where I agree
with the hub I say so in one line and spend the space on what it costs the implementing
parcel; where the ruling collides with source I say that loudly, because a parcel written
from the spec alone would contradict a committed schema.

**The single most important consequence: the implementing parcel's authority is the hub's
§7.2 and the committed JSON schema, NOT the spec's §2.** The spec's §2 is a proposal the
hub overrode in three places (Q2, Q5, Q7). Its §2.3 worked example is now WRONG (§12, F3).

---

## 1. Summary table

| Q | One-line recommendation | Decision owner | Preference or hazard |
|---|---|---|---|
| **Q1** one ref or three | **Ruled: one ref, `rasterRef`, binds the whole document.** Concur — the alternative expresses what the engine cannot bind. Aeon should carry the "historical spelling" sentence, not re-open the name. | Hub (**already ruled**, §3.1 + §7.2 Q1) | Preference, correctly resolved |
| **Q1a** must a document carry `bands`? | **Ruled: `bands` stays required.** Concur *for this CR* — but this is the blocker for Q8 and Q6 and nobody has written that down. | Hub (**already ruled**) | **HAZARD by omission** — it silently blocks two riders |
| **Q2** empty `cycles: []` | **Ruled: absent = keep hand, `null` = OFF, `[]` = refused.** Concur on shape. But absent-vs-null is only safe if aurora's writer can omit a key, and its sibling writer demonstrably does not. Make that a sequencing precondition. | Hub ruled shape; **aurora owns the precondition** | **HAZARD** — order-constraining |
| **Q3** 3/4-channel scripts | **Ruled: no number in the schema; generator refuses >2; `cycle_script3/4` is a rider.** Concur. Note that landing the rider removes the accidental margin over an unguarded runtime walk. | Aeon lane (rider scoping) | Preference, with a hazard rider attached |
| **Q4** `lines` spelling | **Ruled: integer bitmask, 1:1 with `v_lines`.** Concur on the wire. The residual cost is git-diff legibility for hand-edited documents, and that judgement is aurora's. | Aurora (ergonomics); hub ruled the wire | Preference |
| **Q5** short `variants` array | **Ruled: positional; absent keeps `hand:`, `null` clears, object authors.** Concur — the opposite reading drops the act-wide water tint. Inherits Q2's absent-vs-null precondition. | Hub ruled; **aurora owns the precondition** | **HAZARD** (shared with Q2) |
| **Q6** slot-binding assertion | **Ruled: not in this CR, booked as a rider.** Concur, and the reason is stronger than stated: it is blocked on Q8, which is blocked on Q1a. | Aeon lane (rider), gated by hub's Q1a | Preference |
| **Q7** `period + 1` cadence | **Ruled: document `period` is FRAMES; the generator absorbs the quirk (`period - 1`).** Order constraint accepted by the controller. Two things must follow or it breaks silently. | Hub (**ruled**); order is the aeon lane's to enforce | **HAZARD** — order-constraining |
| **Q8** retire the hand twins | **Ruled: rider, after byte-golden + attested chain + reader re-verification.** Concur, and add: it is blocked on Q1a, and its byte-golden must be Python, not comptime (see Q11). | Aeon lane (rider), gated by hub's Q1a | Preference, gated |
| **Q9** cycling cost row | **Ruled: rider, no number.** Concur, and **no recommendation on the number** — nothing measures it. §9 names the exact capture that would settle it, TAGGED for the controller. | Aeon lane; measurement TAGGED | Preference; honest gap |
| **Q10** naming hazard | **Ruled: say it once.** Done, in the hub's `cycles` section. Aeon's `EFFECTS_CONSUMER_CONTRACT.md` §2.4 should carry the same sentence once. | Aeon lane (docs) | Preference |
| **Q11** label-vs-struct comparison (controller's, not in the spec) | Two halves. **Ours:** write the byte-golden in Python, never as comptime equality against a hand `pub data` twin. **Owner's:** whether array-literal position should resolve a `pub data` name as its value. Sigil's premise is enumerated below and **it holds in aeon's tree**. | Split: aeon lane (guard shape) / **owner** (language rule) | Hazard for the guard; owner call for the rule |

**LOOK / TASTE items — named, not recommended past** (§11): (T1) whether the shimmer runs
at 8 or 9 frames on screen; (T2) whether the water tint should be section-scoped at all.

---

## 2. Q1 — one ref or three

*Written to be sendable as-is to a contract owner who has not read our spec. It is
addressed to a question the hub has since answered; it is kept in full because the hub's
answer arrived with a reason, and this is the file where the reason is checkable.*

### The options, as the spec states them (§4 Q1)

1. **Grow `rasterRef`** to bind every channel the named document carries — *"then its name
   is wrong the moment a document has no `bands`"*.
2. **Sibling keys**, `cycleRef` / `variantsRef`, each mirroring `rasterRef`'s shape.
3. **Spend `effectsRef`** — the key the hub reserved for the TOTAL binding.

### Evidence a schema author needs

- **The engine binds ONE preset record per section, and all three channels are fields of
  that one record.** `engine/effects/preset.emp:56-67` declares
  `struct EffectsPreset (size: 38)` with `ep_raster: *u8 @ $08`, `ep_cycle: *u8 @ $10` and
  `ep_variants: [*u8; 2] @ $14`. A section reaches it through a single pointer,
  `Sec.sec_effects` (read at `preset.emp:184`, `:252`). **Three sidecar refs could name
  three documents; the engine has one slot to put them in.** That is the whole of option
  2's problem, and it is the spec's own §2.1 principle turned on the sidecar: a shape must
  not be able to express what the engine cannot bind.
- **Why `effectsRef` cannot be spent yet.** `ep_pal` is the one required, non-defaulted
  field: `preset.emp:57` (`// required; the preset CARRIES the palette`) and the
  constructor signature `preset(pal: Label, parallax: Label = 0, ...)` at
  `preset.emp:121-126` — every other parameter has a default, `pal` has none. A document
  with `bands` + `cycles` + `variants` still cannot construct a preset, because it cannot
  name a palette. **`effectsRef` means "this document IS the preset", and until a palette
  reference exists, no document is.** This is the fact that decides Q1, and it is one line
  of source.
- **Does `rasterRef`'s name survive a document with no `bands`?** Today the question is
  moot in two directions. (a) The hub ruled `bands` REQUIRED (§7.2 Q1a), and the committed
  schema enforces it: `"required": ["schema","id","bands"]` with `"bands"` carrying
  `"minItems": 1`. (b) Aeon's generator refuses a missing or empty `bands` independently —
  `tools/effects_gen.py:495-503`, with the message *"if the intent is 'no raster here',
  delete the file"*. So a bands-less document cannot exist on either side. The name only
  becomes wrong the day Q1a is relaxed, and §7 of the hub doc has `effectsRef` waiting for
  exactly that day.
- **The precedent, and what it cost.** `rasterRef` was itself adjudicated on 2026-08-30
  (hub §3.1, against aeon CR `2cf29126`) precisely to avoid spending `effectsRef` early;
  option C ("grow the preset document to total") was refused there because it *"makes item
  1 depend on item 5 and inverts the ratified DoD order"*. Aeon's generator carries the
  same record at `tools/effects_gen.py:1106-1118`. §3.1 also records the price of a key
  addition: **thirteen code sites in five files plus six prose sites**, two populations
  found by two different methods. Adding two more sidecar keys pays that twice more.

### Recommendation

**Option 1, and the hub has ruled it** (§3.1: *"`rasterRef` binds the WHOLE preset
document, every channel the document carries … `rasterRef` is a historical spelling from
the day a preset document had only `bands`, kept deliberately"*). I concur, on the
one-record argument alone; the naming awkwardness is real and is the cheaper of the two
costs.

**What aeon must do about it:** carry the historical-spelling sentence in
`tools/EFFECTS_CONSUMER_CONTRACT.md` §2.2 in the same parcel, so a reader of the consumer
half does not conclude from the name that `cycles` and `variants` need their own refs. One
sentence, and it is the whole aeon-side obligation for Q1.

**Cost if wrong:** if `rasterRef`'s name is later judged intolerable, the fix is a rename
CR — one constant in aeon (`ACT_RASTER_REF_KEY`, `effects_gen.py:1118`, and
`effects_gen.py:1113-1117` states *"NOTHING ELSE IN THE TREE HARDCODES IT"*), plus aurora's
thirteen sites and six prose sites. Recoverable, and the aeon half is genuinely one line.
The unrecoverable direction is option 3: spending `effectsRef` on a partial binding retires
the name reserved for the total one, and no rename brings it back.

**Owner:** hub. Already ruled, correctly, with the reason carried.

---

## 3. Q1a — must a document carry `bands`? (the hub's addition)

Not in the spec's §4. The hub added it and ruled *"`bands` stays REQUIRED in this CR …
A document that carries `cycles` or `variants` without `bands` is a future CR"* (§7.2).

**Concur for this CR** — every shipped document has bands (`ojz_sec5_showcase.json`,
`authored_probe.json`), and requiring it costs nothing today.

**But it is a hazard by omission, and this is a finding.** The hub's Q6 and Q8 rulings do
not name Q1a as their blocker, and it is:

- Every one of the nine OJZ sections binds the water tint by hand:
  `games/sonic4/data/effects/ojz_effects.emp:1030` (Sec0), `:1033` (Sec1), `:1034` (Sec2),
  `:1035` (Sec3), `:1078` (Sec5) and the shared `OJZ_Preset_Plain` for 6-8 — every one
  spelling `variants: [Variant_Water_Deep, 0]`.
- Q8 retires `Variant_Water_Deep`. Under Q5's ruling, a slot the document does not reach
  keeps its `hand:` value — so retiring the hand twin requires **every** section that wants
  the tint to author it in a document.
- Most of those sections have no bands. `OJZ_Preset_Sec3` carries
  `raster: Raster_Program_None` (`:1035`); the 6-8 group carries no raster at all.
- **Therefore Q8 needs variant-only documents, which Q1a forbids.** The chain is
  **Q1a → Q8 → Q6** (the hub itself gates Q6 on Q8: *"becomes checkable when the hand twins
  retire (Q8)"*).

**Recommendation:** aeon should write this chain into `docs/DEFERRED_WORK.md` beside riders
2 and 3 when it books them, so the first parcel to pick up Q8 discovers the blocker from
the ledger rather than from a refused document. **No CR is needed now** — the relaxation is
cheap the day it is wanted (`required` loses `"bands"`; `load_preset` grows an
at-least-one-channel check). Naming the dependency is the whole deliverable.

**Owner:** hub ruled the requiredness; the aeon lane owns writing the dependency down.

---

## 4. Q2 — `cycles: []`, and the absent/null/value split

### The options, as the spec states them (§4 Q2)

Lower `[]` to `Pal_Cycle_None` ("cycling OFF here"), or refuse it on the empty-`bands`
precedent. The spec notes the precedent does not settle it, *"Unlike bands, OFF is a value
the engine can bind"*.

### The hub's ruling — a third answer

Three states, one spelling each: **absent** = keep the hand cycle; **`null`** = OFF,
lowering to `Pal_Cycle_None`; **`[]`** = refused by the generator naming the two legal
spellings. The committed schema types `cycles` as `["array","null"]` and carries no
`minItems`, deliberately: the refusal is the generator's.

### Evidence

- **OFF really is a bindable value, and the sentinel really is non-NULL.**
  `engine/effects/palette.emp:834` — `pub data Pal_Cycle_None: [u16; 1] = [ 0 ]`, a
  non-NULL script whose channel count is zero. Its 20-line header (`:815-833`) says why
  NULL cannot serve. `Palette_LoadCycle` handles both: `a0 == 0` falls to `.done` with
  `PAL_ACT_CYCLE` already cleared (`palette.emp:324-329`), and a count-0 script exits at
  `bmi .done` **before** the `ori.b #PAL_ACT_CYCLE` at `:334` — so cycling ends up OFF
  either way. The sentinel earns its place by convention, not by necessity, and every
  shipped preset follows it (`ojz_effects.emp:1030, 1033, 1034, 1078`).
- **Absent-means-keep has a working precedent in this generator.**
  `tools/effects_gen.py:1204-1211` (`load_section_raster_refs`): *"Absent / null =
  'this section keeps its hand-authored raster channel', which is the majority case and
  the reason this arm can cost nothing."*
- **And here is the collision.** That precedent treats absent and null as the SAME state.
  Hub §3.1 says so explicitly for `rasterRef`: *"`null` / absent = 'this section keeps its
  hand-authored raster channel.' Absent and explicit-null are the same state, exactly as
  for `sceneRef`."* **Q2 makes them DIFFERENT states**, in the same document family, one
  layer down. Two adjacent conventions, opposite.

### The hazard, and why it constrains order

Aurora's sibling writer demonstrably serialises unset refs as explicit `null`. The live
sidecar in this tree, `games/sonic4/data/editor/ojz/act1/section_5.meta.json`, reads:

```json
{ "bgLayoutRef": null, "paletteRef": null, "rasterRef": "ojz_sec5_showcase", "sceneRef": null }
```

Every unset ref is present-and-null. That is harmless there, because §3.1 makes the two
states identical. **If aurora's preset-document codec inherits the same habit, every saved
document carries `"cycles": null`, and under Q2 that turns palette cycling OFF for the
bound section — silently, on a save that changed nothing.** Section 3's shimmer would
simply stop the first time anyone opened and saved its document.

The hub saw the shape of this: site population 2 says the panel *"must be able to author
'absent' distinctly from 'null', since they are different states."* But it did not make it
a **sequencing precondition**, the way §3.1 did for `rasterRef` (*"does not land in any
sidecar in aeon's tree until the `SectionMeta` extension carrying it is on aurora's
master"*).

### Recommendation

**Concur with the three-state ruling** — it is the right shape, and OFF genuinely deserves
a spelling the engine can bind.

**Add the precondition, and this is the aeon lane's ask of aurora:** no `cycles: null`
document lands in aeon's tree until aurora's writer-side golden proves **absent survives a
parse→serialize round-trip as absent**, not as null. That golden already exists in form
(hub §8: *"the sidecar round-trip — parse→serialize preserves `sceneRef`"*); it needs one
new row.

**Belt-and-braces on our side, and I recommend it:** `load_preset` should refuse a
`variants: null` at key level by name (the hub ruled there is no key-level null for
`variants`, §7.2 Q5), rather than letting it fall through to "absent". A writer that nulls
every known key will produce it, and an unnamed fall-through is exactly the silent state.

**Cost if wrong:** if the precondition is skipped and aurora does null-fill, the failure is
invisible on the build (schema-green, generator-green) and shows only as an effect that
stopped. That is the most expensive failure mode in this whole item — no gate sees it, and
the effects gate ritual would not either, because the ROM is internally consistent.

**Owner:** hub ruled the shape; the **precondition is aurora's to satisfy and ours to
require**. Preference in its shape; **hazard in its ordering.**

---

## 5. Q3 — 3- and 4-channel scripts

### The options (spec §4 Q3)

Add `PalCycleScript3/4` + `cycle_script3/4` on the engine side before or with the lowering,
or cap the document at 2 and say so in the schema.

### The hub's ruling

Neither, exactly: **no number in the schema**; the generator refuses more than two today,
naming the engine limit; `cycle_script3/4` is **a rider aeon books**, not part of item 5.

### Evidence

- `engine/effects/palette.emp:77` — `pub const PAL_CYCLE_MAX_CHANNELS = 4`.
- Wrappers stop at 2: `engine/effects/palette_dsl.emp:112-123` (`cycle_script1`,
  `cycle_script2`), with a module ensure at `:124-125` whose message is *"add cycle_script4
  if a script needs it"*. Struct shapes at `palette.emp:162-163`.
- **The runtime has no bound at all, and I re-verified this against source.**
  `Palette_LoadCycle` (`palette.emp:330-339`) reads `channel_count` off the script and
  zeroes that many bytes from `Pal_Cycle_Timers` with a bare `dbf` — no comparison against
  4 anywhere in the proc. `Pal_Cycle_Timers` is `[u8; 4]` (`engine/ram.emp:548`) and is
  immediately followed by `Pal_Fade_Frames` (`:549`). `Palette_DoCycle` walks the same
  unbounded count and indexes timers as `(a3, d5.w)` (`palette.emp:447-461`) with the same
  absence of a check. **A 5-channel script corrupts the fade state.** The only guard in the
  system is the comptime `chs.len == 1` / `== 2` in the wrappers.

### Recommendation

**Concur with the ruling.** The generator's >2 refusal is a SHAPE fact (an array length),
squarely inside the tool's own posture at `tools/effects_gen.py:30-40`, and identical in
kind to the empty-`bands` refusal at `:497-503`. No number belongs in the schema.

**One addition to rider 1, and it is the reason to state Q3 at all.** Today the distance
between the widest legal script and the unguarded overflow is **two** (wrappers stop at 2,
the array is 4). Landing `cycle_script3/4` narrows it to **zero** — the widest wrapper sits
exactly on the bound, and the only thing standing between a hand-written `PalCycleScript5`
and `Pal_Fade_Frames` is that nobody wrote one. **Rider 1 should therefore land a pin in
the same parcel:** an `ensure` tying every `PalCycleScriptN` wrapper's `chs.len` to
`PAL_CYCLE_MAX_CHANNELS`, so that raising the constant without widening the RAM array fails
the build. `palette_dsl.emp:124-125` is the existing pin of that exact shape and the place
to extend.

**Cost if wrong:** capping the document at 2 in the schema instead would need a schema CR
the day the wrappers land — the hub's own reason, and a good one. Under-scoping rider 1
(shipping `cycle_script3/4` without the pin) leaves a silent RAM-corruption path one
hand-written struct away; it is not reachable from an authored document, which is why this
is a rider note and not a blocker.

**Owner:** aeon lane. Rider scoping is a defensible expert call, and the hub has already
handed it to us by name.

---

## 6. Q4 — the `lines` spelling *(for aurora's eyes)*

### The options (spec §4 Q4)

Integer bitmask (1:1 with `v_lines`), or an array of line numbers translated by the
generator.

### The hub's ruling

**Integer bitmask**, *"1:1 with `v_lines` … authoring ergonomics belong to aurora's panel,
not the wire"*. Carried in the committed schema.

### What the two spellings cost the PERSON authoring a document

- **The field is a mask over CRAM lines 1-3, and bit 0 is forbidden.**
  `engine/effects/palette.emp:134` — `v_lines: u8, // bitmask bits 1-3 … (bit 0 ignored —
  character's)`. Two `ensure`s enforce it: `palette_dsl.emp:43` (*"lines mask {lines}
  selects line 0 (the character's) — use bits 1-3"*) and `:44` (at least one of bits 1-3).
  The constructor default is `lines: int = %1110` (`palette_dsl.emp:35`) — decimal **14**.
- **Inside the editor, the spelling costs the author nothing either way.** Aurora's panel
  can present three checkboxes over any wire form; that is the hub's argument and it is
  correct.
- **Outside the editor, it costs one specific thing: git-diff legibility.** These documents
  are committed files in aeon's tree (`games/sonic4/data/editor/effects/presets/`, which
  today holds `ojz_sec5_showcase.json` and `authored_probe.json`). A reviewer reading
  `- "lines": 14` / `+ "lines": 6` cannot see what changed without decoding two bitmasks;
  `- "lines": [1,2,3]` / `+ "lines": [2,3]` says it. Anyone hand-editing a document —
  which is how both shipped documents got there — pays the same cost, twice: writing 14 and
  trusting it, then reading it back a month later.
- **The wire cost of the list form is one translation in the generator, and that
  translation is already this tool's declared job.** `tools/effects_gen.py:41-46`: *"A
  SPELLING translation is shape too (TRANSITION_NAMES, `_render_bool_int`, `symbol_token`):
  the writer's vocabulary is not the `.emp` vocabulary, and mapping between them is this
  tool's job."* The hub cites the same lines. So the list form would not violate the
  generator's posture; it is a legitimate option that was weighed and lost.

### Recommendation

**The wire call is settled and I concur: keep the integer bitmask.** The generator can
validate it with zero translation and zero second source, and it is the one spelling that
cannot drift from `v_lines`.

**But the ergonomic judgement is genuinely aurora's, and my recommendation does not cover
it.** What I can say is only this: *if* aurora finds the bitmask hostile in hand-edited
documents, the list form is implementable inside the generator's own rules and costs a
schema CR — it is not blocked, it was ranked second. What I cannot say is whether the
diff-legibility cost is worth that CR, because I do not author these files and have never
had to read one back.

**One thing I do recommend regardless, and it is small:** whatever the wire, the
generator's refusal message for a bad mask should let the engine speak. `variant()`'s
own `ensure` text names line 0 and bits 1-3 in a sentence an author can act on
(`palette_dsl.emp:43-44`), and the generator forwards values verbatim, so this happens for
free — as long as nobody adds a range check in Python that pre-empts it.

**Cost if wrong:** low and recoverable in one direction (bitmask → list is a generator
translation plus a schema CR), and free in the other (aurora's panel absorbs either).

**Owner:** **aurora**, for the ergonomics. The hub ruled the wire and the aeon lane has no
standing to re-open it.

---

## 7. Q5 — a short `variants` array

### The options (spec §4 Q5)

Does a length-1 array leave slot 1 at `hand:` (keeps today's water tint) or at 0 (clears
it)?

### The hub's ruling

Positional, index = slot. **Absent (including an index the array does not reach) keeps
`hand:`; `null` at an index CLEARS; an object authors.** No key-level `variants: null` —
clearing both is `[null, null]`.

### Evidence

- **The positional identity is real, three deep.** `preset.emp:64` —
  `ep_variants: [*u8; 2] @ $14, // PAL_MAX_VARIANTS; unused slots 0 = clear`. Those slots
  are handed to `Palette_SetVariant` by index at `preset.emp:319-333` (via
  `EP_VARIANT_0`/`EP_VARIANT_1`, `:149-150`), and `Palette_SetVariant`'s `d0` **is** the
  slot (`palette.emp:298-319`). The same integer is what a `pal_region` band names —
  `on.pal_region.slot` in the same document.
- **"Silence clears" would be a real regression, and it is documented as one.**
  `ojz_effects.emp:974-985`: *"A preset with an empty variants array would CLEAR the slot
  under total binding, silently dropping the water tint act-wide the moment a section
  crossing installs it — a real regression dressed up as 'the preset said nothing'."* All
  nine sections carry `[Variant_Water_Deep, 0]` (`:1030, 1033, 1034, 1035, 1078`).
- **The engine's own words describe the RECORD, not the document.** *"unused slots 0 =
  clear"* is a statement about `ep_variants`, which is filled by `preset()`. What the
  document's silence maps to is a generator decision, and the hub's is the safe one.
- **`hand:` is not always a harmless default, and this matters for the chooser's design.**
  `tools/effects_gen.py:1618-1637` (`RASTER_BINDING_BANNER`) records that on the raster
  channel `hand:` **must** be `0` for a patched section, because `preset()`'s exclusivity
  `ensure` (`preset.emp:131-132`) reads the chooser's result and `Raster_Program_None` is a
  real non-zero label. The variants channel has no such exclusivity rule — nothing in
  `preset.emp` constrains `ep_variants` against another field — so the analogous trap does
  not exist here. Worth stating, because the raster chooser is the template and its `hand:`
  contract is *not* transferable.

### Recommendation

**Concur, unreservedly.** Silence-keeps is the only reading that does not regress shipped
content, and the hub's reason is the one aeon's own source argues for.

**Two implementation notes for the parcel:**
1. Emit **per-slot** choosers (`ojz_act1_sec_variant(sec:, slot:, hand:)`), or a single
   `[Label; 2]`-returning chooser — **both are now proven to reach the ROM**. The probe
   (`docs/superpowers/probes/2026-09-02-item5-comptime-probe.md`, verdicts Q1/Q1-L) built
   both spellings four-shape byte-identical and read `ep_variants` back out of
   `s4.debug.bin` in slot order. Prefer the `[Label; 2]` form: it matches `preset()`'s own
   parameter spelling (`preset.emp:123`) and needs one chooser instead of two. **Caveat
   from the probe: a `[Label; 2]` annotation is NOT length-checked on the fn** — a wrong
   length is caught only at record emission, blamed on the `pub data` line.
2. `load_preset` must refuse a key-level `variants: null` **by name** rather than treating
   it as absent — see Q2's belt-and-braces note. The hub says the state does not exist; the
   generator has to be the one that says so out loud.

**Cost if wrong:** the "silence clears" reading loses the act-wide water tint at the first
crossing, on every section whose document omits the key. It is visible on screen, so it
would be caught — but only by someone looking, and the effects gates do not test tint
presence (`ojz_effects.emp:975-985` describes it as the thing a mechanism conversion would
break, not as something gated).

**Owner:** hub ruled; the absent-vs-null precondition (Q2) is aurora's.

---

## 8. Q6 — the slot-binding assertion

### The options (spec §4 Q6)

With `bands[i].on.pal_region.slot` and `variants[slot]` in one document, should the
generator (or an engine `ensure`) refuse a band that streams from a slot the document
leaves `null`/absent?

### The hub's ruling

**Not in this CR.** Booked as rider 2. Reason: *"absent means 'the hand value is still
there', and the document is not the whole truth while `hand:` fallbacks exist."*

### Evidence

- The limit is real and already declared: the committed schema's own `description` lists
  *"the runtime variant-to-pal_line binding behind a pal_region band cannot be checked at
  build time"* among the known unenforced limits, and hub §7.1 carries the same sentence.
- The band side does pin the slot count independently — `stream_pal_region` in
  `engine/effects/raster_dsl.emp` and `pal_stage_off` in `raster.emp` both bound the slot
  to `PAL_MAX_VARIANTS` — so an out-of-range slot is already refused. What is unchecked is
  the *pairing*: slot 1 named by a band while slot 1 is idle.
- **`null` at an index is checkable today; absent is not.** The hub's own three states make
  this precise: `null` means CLEARED, so a band naming a `null` slot is unambiguously a
  defect, whereas an absent index means "whatever the hand `preset()` call passes", which
  the generator cannot see.

### Recommendation

**Concur with deferral, and sharpen the gating.** The hub gates rider 2 on Q8 (*"once
absent no longer means 'a hand value is there'"*), and Q8 is itself gated on Q1a (§3 above).
So rider 2 sits **two** gates back, not one, and that should be written into
`DEFERRED_WORK.md` when it is booked.

**One piece of it is available NOW and I recommend taking it in the item-5 parcel:** refuse
a band whose `pal_region.slot` the document sets to **explicit `null`**. That case has no
`hand:` ambiguity — the document is saying "clear this slot" and "stream from this slot" in
the same breath, which is never right whatever the hand call does. It is a handful of lines
in `load_preset`, it is a SHAPE-level cross-field consistency check (the same class as the
exactly-one-`on`-arm rule at `render_band_on`), and it retires the easy half of the limit
without waiting on two gates.

**Cost if wrong:** the narrow check refuses nothing legitimate — I can construct no document
where "clear slot N" plus "stream from slot N" is intended. If I am wrong about that, the
cost is one refused document and a one-line revert. The broad check, landed early, would
refuse the *majority* case (absent + hand value present), which is why the hub deferred it.

**Owner:** aeon lane, gated by the hub's Q1a. The narrow half is ours to take now.

---

## 9. Q7 — the `period + 1` cadence *(short entry: RULED)*

**Ruled**, twice over: hub §7.2 Q7 (document `period` is FRAMES; the generator emits
`period - 1` today and `period` unchanged after the booked fix, *"so that no authored
document ever moves"*), and the controller's message this session (the hub accepts the
order constraint in advance; the schema will document which cadence it describes, and the
two changes land in whichever order never shifts an authored cycle by a frame). **Not
re-analysed.**

### The true cadence, transcribed from the engine, not the spec

`Palette_DoCycle`, `engine/effects/palette.emp:454-461`: `tst.b (a3, d5.w)` on the
channel's timer; if **non-zero** it falls to `.wait` and `subq.b #1`; if **zero** it
reloads `move.b d3, (a3, d5.w)` (d3 = the period byte, read at `:451`) and rotates.
`Palette_LoadCycle` seeds every timer to **0** — `moveq #0, d1` then `move.b d1, (a1)+`
(`palette.emp:336-339`), commented *"0 = rotate on the first compose"*.

So: rotate at frame 0, timer = P; frames 1..P decrement it to 0; next rotation at frame
P+1. **Cadence = `period + 1` frames.** The engine agrees with the spec and with
`ojz_effects.emp:493-501` (*"`period: 8` yields 9 frames, not 8"*).

**One source disagreement found, and it is the comment a reader would trust.**
`palette.emp:329` reads *"reset each channel's frame timer to its period so cycling starts
in phase"* — sitting immediately above code that writes **zero**, with the correct inline
comment nine lines below it at `:338`. The header comment describes a different algorithm
than the one under it, and it is the one that reads like an explanation of the cadence.
Recommend correcting it in the item-5 parcel (comment-only, zero bytes).

### What the generator must emit or refuse so the constraint cannot break silently

1. **Emit `pc_period = period - 1`** while the runtime is `period + 1`. The committed
   schema pins this: `contract/schema/aurora-effects-preset.schema.json`, `$defs.cycle_channel.period.description` — *"THE GENERATOR ABSORBS IT (it emits period - 1
   today, period unchanged after the fix lands)"*.
2. **Refuse `period < 2` in the generator, with a message naming the AUTHOR's number.**
   `cycle_channel`'s `ensure` is `period >= 1 && period <= 255`
   (`palette_dsl.emp:96`). With the `-1`, an authored `period: 1` emits `0` and fires an
   engine message about **0**, a number the author never wrote. That is the one place the
   forward-verbatim posture breaks, and the hub anticipated it (*"the legal document range
   today is the engine's range shifted by one, and … the generator reports it"*). This is a
   **unit translation**, which `effects_gen.py:41-46` classifies as SHAPE, so it is inside
   the tool's rules — but it must be written deliberately, not discovered.
3. **The `-1` and the runtime fix must land in ONE parcel.** Rider 5 changes
   `Palette_DoCycle`'s timer logic; the moment it does, a generator still emitting
   `period - 1` shifts every authored cycle one frame **faster**, silently. Nothing gates
   this: no test compares an authored period against an observed cadence, and no budget or
   effects gate measures cycling at all (§10). **Recommend a `# RIDER 5 PAIRING` comment at
   the emission site in `effects_gen.py` naming `palette.emp:454-461`, so the engine-side
   parcel is told by the code it is about to break.**

**Preference or hazard:** hazard, order-constraining. The hazard is not the choice — that
is settled — it is that the pairing in (3) has no enforcement other than a comment.

**Owner:** hub ruled; the aeon lane owns enforcing the order.

---

## 10. Q9 — a cycling cost row

### The options (spec §4 Q9)

Is a `[palette.cycle_cost]` budget-model row part of item 5, or a rider?

### The hub's ruling

**Rider** (rider 4), from a real capture, cross-pinned like the bob's. The cost paragraph
says *"per-frame cost unmeasured"* rather than a number, because *"a placeholder number in
a budget model is worse than an absent row, since the model is read as measured."*

### Evidence

- No measurement exists. `ojz_effects.emp:498-499`: *"there is no cycling row in the budget
  model and no GATE-EVIDENCE cycling capture."* The spec's §5 lists the same as NOT FOUND.
  I did not re-grep `tools/effects_budget_model.toml`; **that half is the spec's claim, not
  my finding.**
- The one measured number in the neighbourhood is the variant re-derive: **19,332
  cycles/frame = 15.1% of every frame**, `palette.emp:107-111`, measured on OJZ_ScrollTest
  2026-08-13.

### The finding that matters more than the row: the cost is a COUPLING, not a number

- `Palette_DoCycle` sets `PAL_ACT_VARIANT_STALE` **only on frames where a channel actually
  rotated** (`palette.emp:462-476`, the `tst.b d7 / beq .ret_quiet` guard). The stale bit is
  what gates the re-derive (`palette.emp:415-421`, *"This is the 15.1%-of-frame gate"*).
- So for a section binding **both** a cycle and a variant — which is exactly what
  `OJZ_Preset_Sec3` does (`ojz_effects.emp:1035`) and exactly what a document carrying both
  keys produces — the dominant per-frame cost of `cycles` is not `Palette_DoCycle` at all.
  It is the re-derive that cycling re-arms.
- **DERIVED, not measured:** at cadence `period + 1`, the amortised re-derive is
  `19332 / (P+1)` cycles/frame. For `OJZ_ShimmerCycle` (P=8, cadence 9) that is **≈2,148
  cycles/frame ≈ 1.7% of a frame** (taking 19,332 = 15.1% ⇒ frame ≈ 128,000 cycles), paid
  as a ~15% spike on one frame in nine rather than smoothly. I have not measured this and
  it excludes `Palette_DoCycle`/`Palette_RotateSpan` themselves.
- **A second DERIVED caveat the hub's cost paragraph does not carry: 19,332 is a ONE-SLOT
  number.** `palette.emp:110-111` records that the measured scene bound only
  `Variant_Water_Deep`, *"so Pal_Active read $10 — variant-only — in every section."*
  `Palette_DoVariants` (`palette.emp:705-721`) calls `Palette_DeriveVariant` **once per
  bound slot**, independently, each over a full 128-byte image. **A document that authors
  both slots therefore costs roughly twice the measured figure** — DERIVED from the call
  structure, and `variants` is the first mechanism that makes binding two slots easy.

### Recommendation

**Concur that the row is a rider — and I have NO recommendation on its value, because
nothing has measured it.** Manufacturing one would be exactly the placeholder the hub
refused.

**Here is the measurement that would settle it, TAGGED FOR THE CONTROLLER** (I may not run
an emulator; agents deadlock on the Oracle MCP):

> Boot OJZ act 1 to **section 3** — the only section binding a cycle
> (`ojz_effects.emp:1035`, `cycle: OJZ_ShimmerCycle`) — on a `DEBUG=1` build with the
> profiler armed. Capture **at least 18 consecutive frames** (two full cadences at P=8) and
> report per-frame work for `Palette_DoCycle`, `Palette_RotateSpan` and
> `Palette_DoVariants` **separately**, so the rotation frame and the eight quiet frames are
> distinguishable rather than averaged. The row wants two numbers, not one: the per-rotation
> cost, and the amortised cost at a stated period. **Control:** the same capture on section
> 2 (`OJZ_Preset_Sec2`, `cycle: Pal_Cycle_None`, same variant bound) isolates the cycling
> delta from the standing variant cost. **Second control, worth taking in the same run:**
> a scene with **both** variant slots bound, to test the "19,332 is a one-slot number"
> derivation above.

**Cost if wrong:** none from deferring. The cost of guessing a number is that the budget
model is read as measured, which is the hub's reason and it is correct.

**Owner:** aeon lane owns the rider; the measurement is TAGGED.

---

## 11. Q10, and the look/taste items

### Q10 — the naming hazard

**Ruled: say it once.** The hub does, at the top of its `cycles` section: `cycles` is
PALETTE cycling (`Palette_DoCycle`, `palette.emp:439`), unrelated to the DEBUG hotkey's
**raster cycle table** (`RASTER_CYCLE_COUNT`, `tools/test_raster_cycle_table_lint.py:6-16`),
which cycles through raster PROGRAMS for a human at a controller. Concur; the aeon-side
obligation is one sentence in `EFFECTS_CONSUMER_CONTRACT.md` §2.4, and it should be the
same sentence, not a paraphrase. **Aeon lane, preference.**

### T1 — LOOK: is the shimmer 8 frames or 9? *(NOT recommended past)*

`ojz_effects.emp:489-501` presents the `period + 1` cadence as a documentation error and
books *"making `period: N` mean N frames"* as a runtime change. **It is not only a
correctness fix.** OJZ section 3's water shimmer has run at a **nine**-frame cadence for as
long as it has existed; rider 5 changes it to eight and the difference is on screen. The
question "should the shimmer speed up by one frame in nine" is a look call about shipped
content, and neither the engine's timer logic nor the schema's unit convention answers it.

**This is a decision card for the owner.** If the answer is "keep what it looks like", rider
5 lands with `OJZ_ShimmerCycle`'s authored period going 8 → 9 in the same parcel, which
costs one byte and no visual change. If the answer is "eight is what was meant", the
shimmer changes and that is fine — but somebody should have said so.

### T2 — LOOK: should the water tint be section-scoped? *(NOT recommended past)*

`ojz_effects.emp:986-988` (within the block at `:974-990`): *"Whether the variant should be
section-scoped is a content question for a later parcel, not something to change while
converting the binding mechanism."* `variants` is the mechanism that makes per-section
tinting authorable for the first time. Whether OJZ's water should tint uniformly across all
nine sections or vary is a look call, it becomes answerable the moment item 5 lands, and it
belongs to the owner. **Naming it is the whole recommendation.**

---

## 12. Q11 — label-vs-struct comparison *(controller's, not in the spec)*

### 12a. Does §3.4's proof fall into the trap? — **No for its proof; yes for its escape hatch**

The controller asked two reads of the spec's §3.4 (*"Byte-compatibility with the hand-written
data, and how it is proven (red-first)"*, spec lines 477-504).

**(a) Does the proof lean on comptime equality against a hand `pub data` twin? NO.** Both
named layers are outside `.emp` entirely:

- **Layer 1**, spec:486-489 — a **text golden in `tools/test_effects_gen.py`**: render the
  document, assert the emitted `cycle_channel(...)` / `variant(...)` argument lists equal
  the hand call text. Python string comparison.
- **Layer 2**, spec:491-498 — a **byte golden on the built ROM**: read the spans at the two
  symbols out of `s4.debug.bin` at the listing's own addresses and assert equality. Python,
  reading a file.

Neither touches comptime equality. The spec's proof is clean.

**(b) Does its text anticipate a red and tell the reader to weaken it? NO — the opposite.**
Both layers carry a *red-first* instruction: *"Red first: mutate `period` to 7 in the
fixture and watch it fail by name before the real document passes"* (spec:488-489) and
*"Red first: the same period-7 mutation, rebuilt, differs at byte 5"* (spec:494-495). Those
are TDD "break it deliberately, then unbreak it" instructions — the opposite of a
pre-authored workaround. **There is no "if this guard fires, relax it to X" text anywhere
in §3.4.** The suspicion does not land, and I say so plainly.

**The residual risk is one sentence, and it is real.** §3.4 closes (spec:499-501):

> *"A comptime `first_mismatch(a, b) == -1` ensure (`raster_dsl.emp:3402`; the idiom at
> `ojz_effects.emp:213-216, 1273-1276`) is the in-`.emp` alternative for arrays; whether two
> `pal_variant` STRUCT values can be compared that way is **NOT VERIFIED**."*

That sentence points at exactly the trap, as an *alternative* to the two safe layers. When
the probe landed, §5 was amended with a "Verified 2026-09-02" bullet carrying the caveat
(spec:591-600) — **but §3.4's sentence was not touched.** A reader who opens §3.4 to
implement the proof now reads "the in-`.emp` alternative" as available-and-verified, 100
lines from the caveat. **Recommend: amend or delete that sentence in the item-5 parcel.**
Neither named layer needs comptime equality, and the case item 5 actually requires —
comparing a value in the **generated** module against one in the **hand** module — was
explicitly left unprobed (probe, "Left open" item 1: the working `const` shape was proven
**same-module only**, and cross-module `pub const` visibility *"was not probed"*).

**The escalation the controller described is right, and worth writing down:** an always-red
guard fires on correct code, which is loud and by itself safe. The damage is the second
step — the probe measured that with the EQUAL twin and `== -1` it fires, *and with the EQUAL
twin and `== 0` it passes*. So the natural "debugging" move on an always-red
`first_mismatch([Variant_Water_Deep], [variant(...)]) == -1` is to flip the expectation to
`== 0` and watch it go green. That is a **permanently vacuous guard produced by fixing a
red**, and it looks like debugging the whole way.

**Does anything else I recommend lean on comptime equality against hand data?** One: **Q8's
byte-golden precondition.** The hub gates retiring the twins on *"documents reproduce them
byte-golden"*, and that is the natural place to reach for `first_mismatch`. **It must be
§3.4's layer 1 + layer 2 (Python), not a comptime ensure** — the cross-module case is
unprobed and the same-module `const` workaround would require moving `Variant_Water_Deep`'s
definition into the generated module, which inverts the ownership the whole arm rests on.
Noted in Q8's entry as well as here.

### 12b. Sigil's premise, enumerated — **it holds in aeon's tree**

Sigil's argument (relayed by the controller) is that making label-vs-struct comparison a
comptime TYPE ERROR is correct under either resolution rule, because a `Label` is an ADDRESS
and a struct is a VALUE. I was asked not to evaluate the conclusion but to test the
**premise**: *is there any position in `.emp` where a `pub data` symbol already flows as a
VALUE rather than as an address?*

**Method** (bounded, and its limits stated): extracted every `pub data` / `data` declaration
name across `engine/` and `games/` — **248 symbols** — then searched the same trees for any
of those names appearing in a dotted position (`.len`, `.field`), which is the only syntax
in which a struct VALUE is distinguishable from an address.

**Result: three candidate hits, all false.** `CharDef_Sonic`, `CharDef_Tails`,
`CharDef_Knuckles` matched — and every occurrence is inside a **comment**
(`games/sonic4/player/player_instashield.emp:14` and `:171`, prose naming
`CharDef_Sonic.cd_ability`). The declaration is a plain `pub data` at
`games/sonic4/player/sonic.emp:40`. **No `pub data` symbol appears in a value position in
executable or comptime `.emp` anywhere in aeon.**

**Two corroborating positives:**

1. **The existing whole-image pin uses `const` on BOTH sides, not `pub data`.**
   `engine/effects/raster_dsl.emp:3483` — `ensure(first_mismatch(raster_program(RASTER_BAND_TWIN), RASTER_BAND_TWIN_HAND) == -1, ...)`.
   `RASTER_BAND_TWIN` is `const` (`:3459`) and `RASTER_BAND_TWIN_HAND` is `const`
   (`:3461`). The idiom the spec cites as precedent **never names a data symbol**, which is
   why it works.
2. **Sigil today cannot even resolve one to a value.** The probe measured `Variant_Water_Deep`
   bare in an `ensure` → `unknown name`, and `OJZ_ShimmerCycle.pcs_ch` → `unknown name`
   (probe, RED-4). That is stronger than "aeon never does it": the value reading is not
   merely unused, it is unavailable.

**So the premise holds, and by the argument as relayed, the two halves separate: sigil's
type error can land now without waiting on the resolution rule.**

**Scope of that claim, stated so it is not over-read:** I searched **aeon's** `engine/` and
`games/` trees only. I did not read sigil's own crate, its test corpus, or any other repo,
and a `pub data` value position appearing in sigil's tests would be a counterexample I
cannot see. The claim is *"no such position is exercised in aeon"*, not *"the language has
none"*. Verifying the latter is sigil's read of its own resolver.

**The cross-type half is independent, and I agree.** `variant(...) == cycle_channel(...)`
evaluating false rather than being refused (probe, RED-4: *"cross-type `==` is NOT refused;
it evaluates false and the ensure fires"*) touches no label resolution and no `pub data`
symbol — both operands are comptime struct values from constructors. It can be tightened on
its own schedule. Worth noting the failure mode it produces is the same family: a typo'd
constructor on one side of an equality ensure reads as a **mismatch**, not as a type error.

### 12c. The split, explicitly

- **OURS (aeon lane), and I recommend it:** the item-5 byte-golden is Python — §3.4's layers
  1 and 2 — and no `.emp` guard in this item compares a generated value to a hand `pub data`
  twin. Amend or delete §3.4's closing sentence so the next reader is not sent to the trap.
  This needs nothing from sigil and nothing from the owner.
- **OWNER's, and I do not recommend past it:** whether array-literal position *should*
  resolve a `pub data` name as its VALUE rather than its ADDRESS is a language-design call
  in `.emp`.
  - *Keep today's rule (name = address everywhere):* consistent with every other position;
    `preset(variants: [Variant_Water_Deep, 0])` keeps working unchanged (it is how the whole
    tree spells a pointer table, `ojz_effects.emp:1030-1080`); the cost is that
    `first_mismatch([<data>], [<value>])` remains expressible-and-meaningless, which sigil's
    type error would then catch.
  - *Change it (name in a value context = the value):* makes the comparison people reach for
    work directly and removes the `const` indirection; the cost is that array-literal
    position becomes context-sensitive, and every existing pointer-table literal depends on
    the address reading — **a 248-symbol blast radius in aeon alone, unmeasured.**
  - **Either way sigil's type error is safe to land**, on the premise verified above.

---

## 13. Ordering — what must happen before what

Driven by the hazards, not by preference.

1. **BEFORE the generator accepts `cycles: null` as OFF** — aurora's writer-side golden must
   prove **absent survives a parse→serialize round-trip as absent**, not as null (Q2/Q5
   hazard; the sibling writer null-fills today, `section_5.meta.json`). This mirrors §3.1's
   own sequencing precondition for `rasterRef` and should be written the same way. *Nothing
   else in item 5 is blocked on it* — the generator can land `cycles` as an array and
   `variants` positionally while `null` handling waits.
2. **IN THE SAME PARCEL as the first `cycles` emission** — the `period - 1` absorption, the
   `period >= 2` refusal naming the author's number, and the `RIDER 5 PAIRING` comment at
   the emission site (Q7). All three, or the fourth is discovered later by a frame.
3. **IN ONE PARCEL, WHENEVER IT LANDS** — rider 5's runtime `period` fix **and** the
   generator's `-1` → passthrough. Split across two parcels, every authored cycle shifts a
   frame silently and nothing gates it. Precede it with the T1 look call.
4. **BEFORE rider 1 (`cycle_script3/4`) ships** — the `PalCycleScriptN` ↔
   `PAL_CYCLE_MAX_CHANNELS` pin, in the same parcel (Q3): the wrappers stop being the margin
   the moment the widest one sits on the bound.
5. **Q1a → Q8 → Q6, in that order.** Relaxing "bands required" is a hub CR and is the
   precondition for retiring `Variant_Water_Deep`, which is the precondition for the broad
   slot-binding assertion. The **narrow** half of Q6 (refuse a band naming an
   explicitly-`null` slot) is not gated and can ship with item 5.
6. **Anything in item 5 touching `engine/effects/*`** — the effects gate ritual
   (`CLAUDE.md`) applies: `tools/effects_gates.py --rom s4.debug.bin --lst s4.debug.lst`,
   totals and exit code in the merge evidence. Item 5 as scoped is generator + schema +
   docs, so it may not trip this; riders 1 and 5 both do.
7. **Independent of all of the above:** sigil's label-vs-struct type error (§12b). It waits
   on nothing here.

---

## 14. What the spec gets WRONG about current source or the current hub

| # | The spec says | Source / hub says | Severity |
|---|---|---|---|
| **F1** | §4 heading: the ten questions are *"for the owner or hub (listed, not answered)"* | **All ten are ANSWERED** at empyrean `origin/main` `d8768c07`, `AURORA_EFFECTS_SCHEMA.md` §7.2 ("The ten rulings"), dated 2026-08-30 — plus a Q1a the spec never asked; and `contract/schema/aurora-effects-preset.schema.json` already carries both keys as properties. §7 was amended to drop them from "reserved". | **HIGH** — a parcel planned from the spec alone contradicts a committed schema |
| **F2** | §2 proposes JSON shapes as the spec's own | The hub **overrode §2 in three places**: Q2 (adds `null` = OFF; §2.1 offered only "lower `[]`" or "refuse"), Q5 (adds `null`-at-index = clear), Q7 (the `period - 1` absorption; §2.1 says *"`period` … cadence = period+1 frames"* on the wire). Hub §7.2: *"Aeon's artifact §2 is a PROPOSAL, and the hub's ruling wins where they differ."* | **HIGH** |
| **F3** | §2.3's worked example writes `"period": 8`; §3.4 asserts its `cycles` entry is *"byte-for-byte `OJZ_ShimmerCycle`"* | **False under the Q7 ruling.** `period: 8` now emits `pc_period = 7`; `OJZ_ShimmerCycle` is `period: 8` by hand (`ojz_effects.emp:502-503`) so its byte is 8. The document must say **`"period": 9`** to reproduce the twin. §3.4's "differs at byte 5" red-first arithmetic needs re-deriving with it. | **HIGH** — it is the parcel's own golden fixture |
| **F4** | §3.4 offers a comptime `first_mismatch` ensure as *"the in-`.emp` alternative"*, marked NOT VERIFIED | §5 was amended on 2026-09-02 with the probe's verdict **and its caveats**; **§3.4's sentence was not**. It now reads as available-and-verified 100 lines from the caveat, and points at the always-red trap. The cross-module case item 5 needs was left explicitly unprobed. | **MEDIUM** (§12a) |
| **F5** | §5 NOT FOUND: *"`Palette_RunCycles` — named at `ojz_effects.emp:494`; no such proc exists"* | **Still true and still unfixed.** `ojz_effects.emp:494` names `Palette_RunCycles`; the proc is `Palette_DoCycle` (`palette.emp:439`). Confirmed, not a spec error — recorded so the item-5 parcel fixes it while it is in the file. | LOW |
| **F6** | *(not in the spec)* | **New source disagreement:** `palette.emp:329` — *"reset each channel's frame timer to its period so cycling starts in phase"* — sits above code that writes **zero** (`:336-339`, correctly commented at `:338`). The wrong comment is the one a reader consults about cadence. | LOW, but it is the Q7 comment |
| **F7** | §1.1 / §1.3 cite the hub at empyrean `5a894756` | Hub `origin/main` is now **`d8768c07`**. Every §7/§3.1 line number the spec quotes has moved, and §7.1/§7.2 are new. Re-read before citing. | MEDIUM (citation rot) |
| **F8** | *(not in the spec)* — `tools/effects_gen.py:437-442` (`discover_preset_files` docstring): *"Today this directory does not exist in the tree at all, which is why adding this arm moves no bytes."* | **Stale.** `games/sonic4/data/editor/effects/presets/` exists and holds **two** documents: `ojz_sec5_showcase.json` and `authored_probe.json`. (The latter's retirement is referenced in spec §3.5 as already-done precedent; it is still present.) | LOW |
| **F9** | §1.3 / hub §7.2 both quote **19,332 cycles = 15.1%** as the variant re-derive cost, unqualified | It is a **ONE-SLOT** figure — `palette.emp:110-111` records that the measured scene bound only slot 0. `Palette_DoVariants` (`:705-721`) derives each bound slot independently, so two authored slots cost roughly double. **DERIVED** from the call structure, not measured. `variants` is the first mechanism that makes two-slot binding easy. | MEDIUM — it is a budget number about to be quoted at a new feature |

---

## 15. What I could NOT answer

- **Q9's number.** No measurement of `Palette_DoCycle` / `Palette_RotateSpan` exists
  anywhere. §10 states the exact capture that would produce one, with its two controls, and
  **TAGS it for the controller** (agents may not drive the emulator). The derived
  amortisation in §10 is arithmetic on a measured number, not a measurement, and is labelled
  so.
- **Whether the language rule in Q11b should change.** Owner's, by construction. I verified
  the premise and stated both consequences; I did not pick.
- **Q4's ergonomic half.** Aurora's. I costed both spellings for a hand-editing reader and
  said what the generator can validate; I have no standing on whether the diff-legibility
  cost is worth a schema CR.
- **T1 and T2.** Look calls on shipped content. Named as decision cards, not answered.
- **Cross-module `pub const` visibility** (generated `effects_scenes.emp` ↔ hand
  `ojz_effects.emp`) — the probe left it open and I ran no build. It only matters if
  someone insists on a comptime byte-golden; my recommendation routes around it.
- **`tools/effects_budget_model.toml` having no cycling row** — I did not re-grep it. That
  claim is the spec's (§1.4, §5) and the hub's, repeated here as theirs, **not verified by
  me.**
