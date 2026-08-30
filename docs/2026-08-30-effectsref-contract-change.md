# CR to empyrean — the per-section raster binding key (`effectsRef` / `rasterRef`)

*Filed by the aeon lane, 2026-08-30. **This file is the CR text, ready to file**; the design it
rests on is `docs/superpowers/specs/2026-08-30-effects-ref-binding-design.md` in this repo.
Nothing is implemented on either side.*

**Verified at committed revisions, not through sibling working trees:**
empyrean `origin/main` = `eff1a9a8`; aeon (this tree) = `e07adb07`; sigil `origin/master` =
`ad0a8243`.

---

## 1. What this CR is for

EFFECTS-W1 item 1 binds an Aurora-authored raster preset to a level section, so an authored
band reaches the screen through the normal content path instead of a DEBUG chord. That needs
one new key in `section_N.meta.json`. §7 of `docs/AURORA_EFFECTS_SCHEMA.md` already reserves a
name for it — and **the reserved name's stated semantics and the only thing its referent can
express do not match.** That mismatch is the adjudication this CR asks for; everything else
here is the mechanical amendment that follows from whichever way it is settled.

---

## 2. THE ADJUDICATION QUESTION — and it is the whole CR

§7 reserves:

> `effectsRef` — a per-section sidecar key alongside `sceneRef` for **total-binding preset
> assignment**

**A preset document cannot express a total binding.** The preset schema's closed key set is
`{schema, id, name, bands}` (`contract/schema/aurora-effects-preset.schema.json`,
`eff1a9a8`). aeon's `EffectsPreset` — the record `Sec.sec_effects` points at — has eight
channels, and one of them has no default:

| channel | supplied by a preset document? |
|---|---|
| `ep_pal` (palette) | **no — and it is REQUIRED, non-defaulted** |
| `ep_parallax` | no (0 = defer to act default) |
| `ep_raster` | **yes — this is what `bands` lowers to** |
| `ep_patched` | no; mutually exclusive with `ep_raster` |
| `ep_cycle` | no (`cycles` is §7-reserved, unbuilt) |
| `ep_variants[2]` | no (`variants` is §7-reserved, unbuilt) |
| `ep_patch_world_ys[4]` | no |
| `ep_transition` | no |

So `effectsRef`, read literally, names a total binding that its referent structurally cannot
deliver. Three ways out, and **aeon cannot choose unilaterally because the name is reserved in
the suite contract**:

| option | what it means | cost |
|---|---|---|
| **A. Narrow `effectsRef`** | amend §7 so `effectsRef` binds the **raster channel only** | the name outlives its meaning; a future total binding needs a second key or a semantics change |
| **B. Adopt `rasterRef`** *(aeon's recommendation)* | a new key carries the narrow binding now; `effectsRef` stays reserved, unspent, for the total binding it was named for | one more reserved name in §7 |
| **C. Grow the preset document to total** | add `palRef`, `cycles`, `variants`, `parallaxRef`, `patchWorldYs`, `transition`; `effectsRef` then genuinely replaces `sec_effects` | **inverts the ratified DoD sequence** — two of those keys are what DoD **item 5** builds, so item 1 would depend on item 5 |

**aeon recommends B.** `rasterRef` says what the mechanism does; the name never has to be
corrected; §7's reservation survives intact for the day the document is total; and it does not
reorder the owner-ratified wave sequence. **A is acceptable to aeon.** C is not rejected on
merit — it is the right end state — but adopting it *now* reorders the DoD, which is the
owner's sequence and not this CR's to change.

Everything below is written with the key spelled `<REF>`. Substitute the adjudicated name.

---

## 3. What changes in the schema

### 3.1 `docs/AURORA_EFFECTS_SCHEMA.md` §3 — the sidecar gains one key

§3 currently specifies `sceneRef` in `section_N.meta.json`. It gains a sibling with **the
identical shape**:

- **`<REF>`: string (a preset-document id from §7.1) or `null` — never a numeric index.**
- **`null` / absent = "this section keeps its hand-authored raster channel."** Absent and
  explicit-null are the same state, exactly as for `sceneRef`.
- The id space is the preset-document id space: `^[a-z][a-z0-9_]{0,31}$`, matching the
  document's own `id` and its filename stem.
- **Numeric index is refused by the consumer**, for the reason §3 already gives for `sceneRef`:
  Aurora's parser nulls a non-string value silently (`section-meta.ts:29-30`), so `<REF>: 3`
  would present to the author as an assignment that did not stick. The one writer that can
  still see the mistake is the build, so the build is where it is refused.
- **The sidecar write condition widens.** §3 records that Aurora writes a sidecar only when at
  least one ref is non-null (`serializeSectionMeta` returns null when ALL refs are null).
  `<REF>` joins that set: a section whose only non-null ref is `<REF>` **must** get a file.
- **Canonical form** is unchanged and applies: `sort_keys=True, indent=2`, exactly one trailing
  `\n` (§8, generalised 2026-08-26 to every JSON file Aurora writes into aeon's tree).

**There is no schema *file* to amend for the sidecar.** `contract/schema/` holds
`aurora-effects-preset.schema.json`, `aurora-effects-scene.schema.json` and
`bus-protocol.schema.json`; the sidecar is specified in §3 prose only. This CR is therefore a
**prose amendment to §3 and §7**, and touches no `.json` schema — unless option C is adopted,
in which case `aurora-effects-preset.schema.json` changes substantially.

### 3.2 §7 — the reservation

Under option B: add `rasterRef` to §7's reserved-name list as **now specified** (pointing at
§3), and leave `effectsRef` reserved and unspent with one added sentence recording *why* it was
not spent — that a preset document cannot express a total binding until `variants` / `cycles` /
a palette reference exist.

Under option A: amend the `effectsRef` bullet's words "total-binding preset assignment" to
"raster-channel assignment", with the same explanatory sentence.

### 3.3 What does NOT change

- `aurora-effects-preset.schema.json` — untouched under A and B. The document's key set is
  unchanged; this CR binds documents, it does not grow them.
- `fires`, `variants`, `cycles` stay reserved and stay refused by name.
- No numeric bound moves in either direction. The engine's `ensure`s in
  `engine/effects/raster_dsl.emp` remain the only authority on values; the schema stays
  normative for shape only; **clamping stays rejected on both sides.**

---

## 4. What a conformant PRODUCER must do

*(Aurora, or any writer of `section_N.meta.json`.)*

1. **Extend `SectionMeta` in the same parcel as the first `<REF>` writer.** `SectionMeta` is a
   closed interface whose serializer writes what it enumerates (`section-meta.ts:22`), so the
   interface, the header-comment field enumeration (`:5-9`), the parser and every other site
   the §6-item-1 thirteen-site audit named move **together**. A partial extension does not
   half-work; it erases.
2. **`parse → serialize` must preserve `<REF>`**, as a named contract requirement — the same
   requirement §3/§6/§8 already impose on `sceneRef`, for the same reason.
3. **Write a string id or `null`. Never a number, never an object.**
4. **Write the sidecar whenever any ref including `<REF>` is non-null**, per §3.1 above.
5. **Canonical serialization**: `sort_keys=True, indent=2`, exactly one trailing newline.
6. **Do not validate the band values and do not clamp them** — that rule already governs the
   preset document and it governs the reference too. A producer that refuses a legal-shaped id
   because it dislikes the document's contents is authoring something the author did not write.
7. **Honour the sequencing precondition in §6 below.**

---

## 5. What a conformant CONSUMER must do

*(aeon's `tools/effects_gen.py`.)*

1. **Read `<REF>` out of `section_N.meta.json` with the missing/unreadable split intact.** An
   **absent** sidecar is all-refs-null and is **not an error**. A sidecar that exists and does
   not parse **fails the bake loudly**. "Degrade gracefully" must not collapse those two,
   because all-null is precisely the state that triggers Aurora's destructive cleared-overwrite.
2. **Refuse a non-string, non-null value**, naming the reason (§3.1).
3. **Refuse an id that names no preset document**, listing the known ids — symmetric with the
   existing `sceneRef` resolution error.
4. **Emit the binding as an always-emitted zero-byte chooser**, per ruling Q-c: with no `<REF>`
   anywhere, the generated module's text gains the chooser and **nothing else**, and the ROM is
   byte-identical. The unbound case must cost nothing and that must be *checkable*, not argued.
5. **Restate no numeric bound from the raster tier.** Out-of-range values continue to be
   forwarded verbatim so the author reads the engine's own sentence, which carries the
   measurement behind the rule.
6. **Do not add an unknown-key refusal to the sidecar.** The sidecar reader deliberately ignores
   keys it does not know; making unknown keys fatal would turn every future Aurora key into a
   build break. (This is the mechanism behind §6.1's answer, and it is a choice, not an
   oversight.)

---

## 6. WHAT AN OLDER CONSUMER DOES WHEN IT MEETS THE NEW KEY

**Named, because this is the half that gets discovered instead of decided.** There are two
older parties and they behave differently. One of them destroys data.

### 6.1 An older `effects_gen.py` — **silently ignores it**

An aeon revision from before this lands reads only `sceneRef` from a sidecar and applies **no
unknown-key check** to it (verified in `tools/effects_gen.py`'s `load_section_scene_refs`; the
`_check_keys` machinery is applied to scene and preset *documents*, never to the sidecar). Its
only sidecar-shape assertion is that the top level is a JSON object.

**So: no error, no warning, no band.** A tree carrying `<REF>` and an older generator builds
green, ships, and shows nothing. To an author that reads as "my assignment did nothing".

**This is accepted, not fixed.** Hardening it would mean making unknown sidecar keys fatal,
which breaks every future key. The behaviour is *named here* so that a bisect, a revert, or a
mixed-SHA pairing produces a known outcome rather than a mystery.

### 6.2 An older Aurora — **ERASES it on the next save**

`SectionMeta`'s serializer writes what it enumerates, so a `<REF>` written by anything other
than a `<REF>`-aware Aurora is **silently erased on Aurora's next save round-trip**. This is
the thirteen-site hazard §6 item 1 already documents for `sceneRef`, inherited unchanged.

**Therefore `<REF>` inherits `sceneRef`'s SEQUENCING PRECONDITION (§3, ERRATUM 2), and this CR
restates it as binding:**

> **`<REF>` does not land in any sidecar in aeon's tree until the `SectionMeta` extension
> carrying it is on aurora's master.**

`sceneRef` needed aurora `a88db05` for this. `<REF>` needs its successor, and the aeon parcel
that writes the first `<REF>` cites that SHA in its evidence. Landing earlier means the
author's first save deletes their own assignment.

### 6.3 A newer consumer, an older sidecar

Absent `<REF>` is absent, which is `null`, which is "keep the hand-authored channel". Stated so
the silence is not read as coverage.

---

## 7. Golden and pinning

Per §8's change protocol: **this document + `AURORA_EFFECTS_SCHEMA.md` §3/§7 + aeon's
`tools/EFFECTS_CONSUMER_CONTRACT.md` §2.2 amend together**, and Aurora re-pins its writer-side
golden against both repo SHAs.

The golden gains, at minimum:

- a sidecar carrying `<REF>` validating and round-tripping unchanged;
- **the round-trip preserving `<REF>` alongside `sceneRef`, `bgLayoutRef` and `paletteRef`** —
  the §6.2 hazard, asserted rather than trusted;
- the write condition with `<REF>` as the only non-null ref (a file must be written);
- the explicit-null clear.

**One known limit, carried forward from §7.1 so a silence is not read as coverage, and it is
the one this CR *removes*:** §7.1 records that *"nothing checks a preset is bound (an authored,
unbound preset costs ROM and shows nothing)"*. Once `<REF>` exists, aeon's build gains exactly
that check — a preset document must be reachable by **either** a `<REF>` binding **or** the
DEBUG lab's cycle table, and one reachable by neither fails the build. That is an aeon-internal
gate and needs no schema text, but it closes a limit this document currently declares open, so
§7.1's sentence should be amended when the aeon half lands.

---

## 8. What aeon commits to, on adjudication

The implementation plan is §10 of
`docs/superpowers/specs/2026-08-30-effects-ref-binding-design.md`. In one line each:

1. the generator arm, **zero ROM bytes**, CRC-checkable, no sidecar carries the key yet;
2. the reachability-lint relaxation (a preset is reachable by a `<REF>` **or** a lab row);
3. the section's preset split (**+38 bytes**, pairs with sigil);
4. the authored band, its `<REF>`, and the deletion of the `authored_probe` scaffold (net **0**
   for that step, **+38** cumulative), gated on §6.2's precondition;
5. docs — including deleting the "authoring effects still needs a programmer" sentence from
   `docs/EDITOR_RASTER_PRESETS.md` §C, which this change is what makes false.

**Byte figures are measured, not estimated**: 78 bytes for a two-band program (label span in
`s4.lst`, corroborated independently by sigil's own `+0x4E` pin note), 38 bytes for one
`EffectsPreset` record (label span, matching `struct EffectsPreset (size: 38)`). Derivations
are in §7 of the design doc.

---

## 9. The ask, in one paragraph

**Adjudicate §2.** Pick A, B or C. If B, add `rasterRef` to §7 as specified and amend §3 with
the key's shape in §3.1. If A, amend §7's `effectsRef` wording instead — the §3 text is
identical either way. Then confirm §6.2's sequencing precondition applies to the new key, and
aurora schedules its `SectionMeta` extension. **aeon's step 1 is blocked on this and on nothing
else**, and item 1 is the first aeon row every remaining aurora feature row waits on.
