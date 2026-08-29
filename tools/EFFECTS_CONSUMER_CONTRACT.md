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
| `cols` | `:85` | yes | band width in tiles |
| `rows` | `:85` | yes | band height in tiles; `col_bytes = rows * 32` must be a power of two (`:88-90`) |
| `pattern_px` | `:87`, `:91` | yes | must equal `cols * 8` |
| `driver` | `:105-106` | no (default `"camera_x"`) | one of `camera_x` / `camera_y` / `timer` (`DRIVERS`, `:69`) |
| `rate_shift` | `:107` | no (default 2) | 1 px of pattern motion per `1 << rate_shift` driver units |
| `slot_base` | `:92-93` | no (default = running cursor) | if present MUST equal the running cursor — bands pack contiguously from slot 0 in list order |
| `phases` | `:96-97`, `:127-128` | yes | exactly **8** banks; each bank exactly `cols*rows` tiles; each tile 64 pixel values (low nibble kept, `:101-103`) |

Derived, not read: `step_mask` (= `pattern_px - 1`), `col_shift`, `tile_count`,
`bank_offsets`. Writers must not emit them; the consumer ignores unknown keys today, but
the drift rule above governs — do not rely on ignored keys staying ignored.

Output contract (aeon-internal, cited for orientation only): 44-byte records LOCKSTEP
with `engine/level/bg_anim.emp` `struct bganim_band` (**`bg_anim.emp:66`**, its width held
by `ensure(sizeof(bganim_band) == 44, …)` at `bg_anim.emp:75` — that ensure, not this
sentence, is the authority); the animated arm is
FORMAT-FAITHFUL BUT NOT BYTE-PROVEN until the first authored act (`:121-124`) — that
discharge is a wave-1 aeon lane item.

## 2. `tools/effects_gen.py` — normative read set (build-to; P5)

`effects_gen.py` does not exist yet (verified at `08f01b73`). This section is the
NORMATIVE read set the P5 implementation is built to; it is enumerated NOW so Aurora's
writer golden and the generator are written against the same list, rather than the
consumer growing ad-hoc readers (the exact failure the sprite-export ruling names).

### 2.1 Scene definition files

`games/sonic4/data/editor/effects/<scene_id>.json` — one scene per file; an absent
directory means "no editor scenes" (not an error). The generator reads exactly the wave-1
normative surface of `empyrean/docs/AURORA_EFFECTS_SCHEMA.md` §2, which mirrors the scene
DSL constructor arguments 1:1 (`engine/level/scene_dsl.emp` `scene()`/`layer()`):

- Top level: `schema` (refuse ≠ 1), `id` (refuse ≠ filename stem or bad pattern),
  `layers`, `v_factor`, `v_center`, `v_offset`, `v_factor_fg`, `deform_fg`, `deform_bg`,
  `v_deform`, `anchor`, `left_column_mask`, `transition`, `budget_class`
  (passthrough, unvalidated — sigil is the validator).
- **`precision` — ACCEPTED AND IGNORED (engine-side RETIRED 2026-08-26, owner ruling
  `d-29-corrected`).** The per-cell HScroll path the field chose between was deleted; the
  fill is per-line for every scene and `scene()` no longer takes the argument. The
  empyrean schema (wave 1, `cell` only) still spells it, so the generator does not refuse
  a file that carries it — it drops the key, whatever the value. Removing the field from
  the schema and from Aurora's `scene-ui` is **Aurora's + empyrean's**, booked in
  `docs/DEFERRED_WORK.md` ("Per-cell HScroll fill — DELETED"); when it lands, the key
  moves from the generator's ignored set to its refused set.
- Per layer: `world_y`, `fa`, `fb`, `dsa`, `dsb`, `phase`, `enabled`, `deform`, `curve`,
  `vsplit`.
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

### 2.2 Assignments

- `games/sonic4/data/editor/ojz/act1/section_N.meta.json` (per act's `dataPath`): the
  generator reads **one key**: `sceneRef` — string scene id or `null`/absent (= act
  default). It does not read `bgLayoutRef`/`paletteRef` (those belong to the BG/palette
  pipeline). **Write condition and round-trip (contract-level; ERRATUM 1 of
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
file. An absent directory means "no presets" and is **not** an error; the directory does
not exist in the tree today, which is why adding this read set moved zero ROM bytes.

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
The three reserved names are refused **by name** here rather than as unknown keys.

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
| `bands` | array, length ≥ 1 | The bands in this program. **Absent: refused. Empty: refused** (an empty program is not a program). | one `compose([...])` | `tools/effects_gen.py` `load_preset`; backstop `engine/effects/raster_dsl.emp` `compose` ("compose: nothing to compose") |
| `fires`, `variants`, `cycles` | — | empyrean §7 reserved wave-2 keys. **Refused by name**, with the reason, not as unknown keys. | nothing | `tools/effects_gen.py` `_check_keys` via `PRESET_REFUSED_KEYS` |
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
- **Nothing checks the total ROM cost of the preset set.** Each program is bounded by the
  64-word program buffer; the number of programs is not bounded by anything.
- **The runtime palette binding behind a `pal_region` band is unchecked, and cannot be
  checked at build time.** The variant bound to `slot` must cover `pal_line` in its `lines`
  mask or the band streams whatever the staging buffer holds. Binding is a runtime call
  (`Palette_SetVariant`), so no comptime guard can see it — `raster_dsl.emp`'s
  `fx_tint_band` header states this as a standing, booked limitation.
- **Nothing checks that a band is VISIBLE** — that the CRAM entry it repaints is used by
  pixels on those rows, or that the colour differs from the base. Design §3.4.
- **No writer-side schema exists yet.** This section is the aeon consumer half only; the
  `empyrean` schema pair does not spell `bands` at the revision this was written against
  (verified: `git -C ../empyrean show origin/main:contract/schema/aurora-effects-scene.schema.json`
  contains no band/raster/cram/tint token). Per the drift rule at the top of this file,
  amending the empyrean schema pair and re-pinning Aurora's golden is the other half of
  this change series.

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
