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
| `tools/effects_gen.py` | **booked-unbuilt** (scanline-services P5, `docs/superpowers/specs/2026-08-17-scanline-services-design.md` §7) | §2 — NORMATIVE build-to list; P5 implements exactly this and nothing more |

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
  `v_deform`, `anchor`, `left_column_mask`, `precision`, `transition`, `budget_class`
  (passthrough, unvalidated — sigil is the validator).
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
  the golden pins:** aurora's codec hardcodes the two-ref set at **THIRTEEN sites, not the six
  this contract originally listed** (corrected 2026-08-22 after Aurora's first wave-1 parcel
  enumerated it against the real type: `save.ts` carries a SECOND independent hardcoded
  enumeration at `:130` beside the cleared-overwrite literal, `Section` itself gains the field,
  and `cloneSection` hand-enumerates every ref in a bare literal — that last one was UNGUARDED,
  and dropping a ref from it survived Aurora's entire 3,909-test suite). The six below are the
  CODEC frame only; enumerate by what TOUCHES the record — constructors and copiers included —
  not by what defines it. Original six — four
  executable (`section-meta.ts:21`, `:22`, `:29-30` — unknown keys silently DROPPED,
  non-string known keys nulled — and the cleared-overwrite body at `save.ts:118-126`)
  plus the header-comment enumeration (`:5-9`) and the `SectionMeta` interface
  (`:11-14`) — so a `sceneRef` written by anything other than a sceneRef-aware Aurora is
  silently erased on Aurora's next save round-trip. The `SectionMeta` extension edits
  all six in the same Aurora parcel as the first writer, and parse→serialize
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
