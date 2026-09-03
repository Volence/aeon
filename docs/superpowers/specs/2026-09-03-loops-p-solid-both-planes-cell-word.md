# Solid-in-both-planes — where it lives, costed (LOOPS-P decision 4)

*Status: **DOCUMENTS ONLY, 2026-09-03**. Nothing here is implemented and no ROM byte moves.
Written because the editor lane's census of the collision cell word found no room for a
fifth solidity value and is blocked on aeon saying where "solid in both planes" belongs.
The short answer, ahead of the derivation: **it already lives nowhere new, on both sides of
the wall, and has since 2026-08-29.** This document exists to re-derive that from source
rather than take the existing docs' word for it, cost the two alternatives nobody had
priced, and give the editor lane a citable answer.*

*Every aeon claim below is transcribed from source in this tree at aeon
`7cd6353e594ff607b7dccdd3311c27aed9c7f4f5` — the tip of `origin/master` at the moment this
branch (`design/loops-p-cell-word`) was cut, confirmed by `git rev-parse HEAD` in this
worktree. Every aurora claim is transcribed from `git -C /home/volence/sonic_hacks/aurora
show <sha>:<path>` at aurora `06f1ecd5f6ed88b68cabc5fd929cf2bbab9ed441` (their tree was
verified clean — `git status --short` empty — so line numbers read off the working copy
match that commit exactly). `file:line` cites name a symbol beside the line number so a
later move does not silently invalidate the citation. No emulator was used; nothing here
needed one.*

---

## 0. The question, restated precisely

`docs/research/loops-and-sprite-rotation.md` §7 "decision 4" (line 1184) bundled this
alongside the painted-crossover-marker decision:

> *"I would add a third option, 'solid in both', so ordinary ground is drawn once and only
> the genuinely loop-specific parts get drawn twice. It costs nothing extra to build
> alongside the rest…"*

The premise — that this rides free in the *same spare bits* as the crossover marker — is
false, and it was caught twice, independently, before this document existed:

1. **On the aeon side**, `docs/decisions.jsonl` `d-39-corrected` (2026-08-29T00:11:51Z)
   flagged that the "two spare bits" it had been about to spend on the crossover marker were
   not spare at all — they are the donor word's path-B solidity — and, in withdrawing,
   floated the real answer as a hypothesis: *"the cell word may ALREADY express the state I
   was about to add… since solidity is two bits per path and 'solid on both paths' may just
   be painting both."* `docs/LOOP_CROSSOVER_ENCODING.md` §2.1 (built `8a4313b5`) later
   confirmed that hypothesis with a source-level demonstration and a measurement, and its
   §10 explicitly retracts decision 4's framing: *"Route P should be amended to drop 'the
   same spare bits can carry a solid on both planes state'. They cannot and need not."*
2. **On the aurora side**, independently and earlier by four days
   (`d1ac8c76`, 2026-08-29, merged `bbc86d1c`), the editor lane built the answer as running
   code before aeon's document existed: `src/core/collision/both-planes-paint.ts` opens with
   *"Aeon's Route P proposes 'solid on both planes' as a THIRD CELL STATE… It does not need
   to be a state, and reading it as one would have blocked half this parcel behind an
   encoding it never required."*

So the "editor lane measured why" the brief describes is this file's own header comment,
not a new finding this document produces. **What had not been done, on either side, is
costing the two alternatives against real numbers and writing the comparison down where the
next reader does not have to reconstruct it from two repos' git log.** That is this
document's job, plus re-deriving the bit census from scratch rather than trusting either
side's prose.

---

## 1. Re-deriving the bit census — independently, from our own source

**Method:** not a grep for the word "solidity". Every bit range below was found by reading
the two encoder/decoder functions that actually shift bits into and out of the word
(`bake_plane_cell` in aeon, `packCollisionCell`/`unpackCollisionCell` plus
`layer-transition.ts` in aurora) and cross-checking their named shift/mask constants against
real authored data. A name-grep would have missed the crossover field exactly the way
`d-39`'s first pass did (`decisions.jsonl` `d-39-corrected`: *"my confirming grep searched
for the LITERAL VALUE… and returned zero… because the pipeline never spells the mask — the
range lives only in a comment and every use goes through the named constant"*) — the same
trap this document's own numbers are checked against below.

**aeon, `tools/collision_pipeline.py` (`bake_plane_cell`'s word — this is the word Aurora's
`.collattr.bin`/`.collattrb.bin` files carry, NOT the donor `bake_cell` word; the two share a
file and must never be confused, §3 below):**

| bits | field | constant | values | file:line |
|---|---|---|---|---|
| 0-9 | shape index | `BLOCK_ID_MASK = 0x03FF` | 0-1023 (base bank uses 0-255 only, §4.1) | `tools/collision_pipeline.py:50` |
| 10 | X-flip | `CHUNK_XFLIP_BIT = 0x0400` | bool | `tools/collision_pipeline.py:51` |
| 11 | Y-flip | `CHUNK_YFLIP_BIT = 0x0800` | bool | `tools/collision_pipeline.py:52` |
| 12-13 | this plane's solidity | `PLANE_SOL_SHIFT = 12` | `SOL_NONE`=0, `SOL_TOP`=1, `SOL_LRB`=2, `SOL_ALL`=3 — **all four live** | `tools/collision_pipeline.py:61`, read at `:305` |
| 14-15 | crossover (`XOVER`) | `XOVER_SHIFT = 14`, `XOVER_MASK = 3` | `NONE`=0, `TO_A`=1, `TO_B`=2, `RESERVED`=3 (bake **raises**, does not clamp — `:294-303`) | `tools/collision_pipeline.py:95-100` |

Sixteen of sixteen bits accounted for, none free. Confirmed by exercising the raise path
directly: `bake_plane_cell` (`:267`) reads `xover` at `:294` and raises at `:295-303` for
value 3; there is no path that reaches a return with `xover == 3`.

**aurora — the SAME word, split across two files that between them are the authority (their
own `collision-cell-word.ts` docblock has drifted, see §1.1):**

- `src/core/collision/collision-cell-word.ts:1-19` (`06f1ecd5`) — shape/xFlip/yFlip/solidity,
  bits 0-13, matching aeon's `BLOCK_ID_MASK`/`CHUNK_XFLIP_BIT`/`CHUNK_YFLIP_BIT`/
  `PLANE_SOL_SHIFT` bit-for-bit.
- `src/core/collision/layer-transition.ts:93-105` (`06f1ecd5`) — `CROSSOVER_SHIFT = 14`,
  `CROSSOVER_VALUE_MASK = 0x3`, `CROSSOVER_RESERVED = 3`, matching aeon's `XOVER_SHIFT`/
  `XOVER_MASK`/`XOVER_RESERVED` bit-for-bit, and citing the anchor doc by commit
  (`layer-transition.ts:8`: `git -C ../aeon show aa2a9f29:docs/LOOP_CROSSOVER_ENCODING.md`).

**Verdict: our tree agrees with the editor's census exactly.** Sixteen of sixteen bits used,
solidity's four legal values all live, crossover's three legal values live and the fourth
hard-errors. **No fifth solidity value has anywhere to go, and this document does not
propose finding it one** — §2 explains why it does not need to.

### 1.1 One thing that does NOT agree, and does not matter to the answer

`collision-cell-word.ts:10` (`06f1ecd5`) still comments bits 14-15 as *"spare"* — stale
since `layer-transition.ts` claimed them on 2026-08-29, four days before this doc's cut. This
is an aurora-internal documentation drift (their own crossover authority module is a
different file, and neither file's comment references the other), not a disagreement between
the two repos' actual bit assignments — `layer-transition.ts` is unambiguous about owning
14-15, and nothing in `collision-cell-word.ts`'s code (`packCollisionCell`/
`unpackCollisionCell`, `:28-52`) touches those bits either way, so the stale comment cannot
cause a silent bit collision. Flagged because the brief's hazard warning applies to
comments as much as code; not flagged as a blocker, since it is aurora's file and this
document changes no code in either repo.

---

## 2. Why "solid on both planes" needs no bit at all

Aeon's runtime and bake keep the two collision planes as **structurally independent data**
end to end, not as two sub-fields of one shared record:

- Aurora authors two files per section: `section_N.collattr.bin` (plane A) and
  `section_N.collattrb.bin` (plane B), each 256×256 cells of one 16-bit big-endian word,
  same format, independent content.
- The bake reads them independently: `apply_editor_collision_overlay`
  (`tools/ojz_strip_gen.py:1570`) opens `path_a` (`:1601`) and `path_b` (`:1611`)
  separately and interns each cell's word through the **same function, called twice**:
  `ea[cr] = cp.bake_plane_cell(wa, …)` and `eb[cr] = cp.bake_plane_cell(wb, …)`
  (`:1655-1656`). Nothing here reads plane A's word to decide plane B's attr, or vice versa.
- The runtime keeps two collision arrays and never reads both for one query:
  `Collision_GetType` (`engine/level/collision_lookup.emp:27`) takes `d3.b` = plane select
  and fetches exactly one byte — `tst.b d3 / beq .plane_selected / addi.w
  #TILE_CACHE_COLL_SIZE, d1` (`:65-67`) — from `Tile_Cache_Collision`. It is called from
  exactly two files, `player_sensors.emp` and `player_common.emp` (confirmed by an
  engine-wide grep for the symbol, not for "layer" or "solidity" — see §3's method), and
  every call site sets `d3` to a single plane before calling. **No call site queries both
  planes for one position.**

Given that, "solid on both planes" is not a state a cell can be IN — it is a predicate over
**two independent facts that already exist**: plane A's solidity is non-zero, and plane B's
solidity is non-zero, at the same cell index. Painting a cell "solid on both" is exactly
painting ordinary solid ground into plane A's word and ordinary solid ground into plane B's
word at the same index — the same operation an author already performs for a cell that is
solid on ONE plane, done twice. No new value, no new bit, no new baked table, because the
bake already produces two attr bytes per cell and always has.

**This is measured, not assumed.** Re-deriving `docs/LOOP_CROSSOVER_ENCODING.md` §2.1's
table directly from the authored files at our SHA (decoding both plane words' bits 12-13,
independent of any doc's prior claim):

```
section_0.collattr.bin / section_0.collattrb.bin, 65536 cells each:
  solid on plane A:      1792
  solid on plane B:      1100
  solid on BOTH:         1056
  solid on A only:        736
  solid on B only:         44
  any cell with XOVER != 0 in either plane's bits 15:14:  0
  any cell with XOVER == 3 (reserved) in either plane:    0
```

This reproduces the anchor doc's numbers exactly (it measured at `fde35b2f`; this
re-derivation is at `7cd6353e`, and the OJZ act-1 collision data has not changed between
those commits — `git log --oneline fde35b2f..7cd6353e -- games/sonic4/data/editor/ojz/`
returns nothing touching the section-0 plane files). **1056 cells are already solid on both
planes, painted by hand into two files, today, in the shipped act.** Sections 1-8 are
confirmed entirely zero on both planes (`nonzero-A=0 nonzero-B=0` for all of section 1
through section 8, decoded directly from their `.collattr[b].bin` files) — matching the
anchor's claim that only section 0 has any authored collision at all.

**What was actually missing was the gesture, not the encoding**, and aurora had already
built it four days before the anchor doc: `both-planes-paint.ts` (`06f1ecd5`) implements
"paint solid-on-both" as one user stroke that computes **two independent merges**, one per
destination plane (`buildBothPlanesEntries`, `:120`), and exposes the fact as a **derived
query** rather than a stored flag — `solidOnBothPlanes(wordA, wordB)` (`:258`) is
`isSolidCell(wordA) && isSolidCell(wordB)` (`:265-268`), nothing more. Their own reasoning
for deriving rather than storing (`:55-59`) is exactly the argument this section makes from
the aeon side: *"That is strictly better than a stored flag: a flag could disagree with the
data, and this cannot."* Wired into the live UI, not just a library function —
`MapViewport.tsx:2653` calls `buildBothPlanesEntries` from the actual paint-stroke handler,
`editorStore.ts:235` and `both-planes-lens.ts:16,42,92` reference the same module for the
visualization lens that draws the derived fact.

---

## 3. Consumer enumeration — method and result

**Method, stated because the brief's hazard is real: enumerating by field name would have
missed the crossover field entirely** (its own home, `layer-transition.ts`, does not use the
word "solidity" anywhere near its bit constants, and `d-39-corrected`'s postmortem records
exactly this failure mode on the aeon side, `tools/collision_pipeline.py:54`'s
`PATH_B_SOL_SHIFT` missed by a value-grep). Instead: start from the two files that are the
word's only origin (`section_N.collattr.bin` / `.collattrb.bin`), and trace forward through
every function that opens those files or is called with a value derived from them, using the
named shift/mask constants (`BLOCK_ID_MASK`, `CHUNK_XFLIP_BIT`, `CHUNK_YFLIP_BIT`,
`PLANE_SOL_SHIFT`, `XOVER_SHIFT`/`CROSSOVER_SHIFT`) as the search key, not the English word
for what they mean. Cross-checked in the reverse direction from the runtime: start at
`Tile_Cache_Collision` (the one runtime array the word's information ends up in) and walk
every caller of `Collision_GetType`, the only reader.

**Every touch point found, aeon side:**

| stage | symbol | file:line | touches |
|---|---|---|---|
| bake (donor, off-limits) | `bake_cell` | `tools/collision_pipeline.py:228` | the OTHER word; reads bits 15:14 as path-B solidity, not crossover — the trap `d-39-corrected` found |
| bake (Aurora's word) | `bake_plane_cell` | `tools/collision_pipeline.py:267` | reads all 16 bits: shape/flip/solidity/xover |
| overlay | `apply_editor_collision_overlay` | `tools/ojz_strip_gen.py:1570` | opens both plane files, calls `bake_plane_cell` per plane per cell (`:1655-1656`) |
| donor overlay | `build_section_collision` | `tools/ojz_strip_gen.py` (donor path) | calls `bake_cell`, not `bake_plane_cell` — a different pipeline for sonic_hack-imported content |
| strip write | `write_strips_to_file` | `tools/ojz_strip_gen.py` | writes the baked attr BYTE (post-intern), never the raw word |
| block embed | `tools/ojz_block_gen.py:65-74` | `BLOCK_COLL_PLANE_SIZE`/`STRIP_COLL_OFFSET_A/B` | embeds attr bytes into 16×16 blocks, 128 B/plane/block, never the raw word |
| repaint (rewriter) | `repaint_word` | `tools/repaint_ojz_collision.py` | rewrites a per-plane word; must preserve bits 15:14 (fixed, R4) — this is the only tool on the aeon side that WRITES a word after authoring |
| table emit | `emit_tables` / `emit_stub_tables` | `tools/collision_pipeline.py` | writes `heightmaps.bin`, `heightmaps_rot.bin`, `angles.bin`, `solidity.bin`, `crossover.bin` from the interned `AttrSet` |
| data dir | `tools/gen_collision_data.py` | — | copies `emit_tables`' output into `games/sonic4/data/collision/` |
| ROM embed | `collision_data.emp:13-17,125-129` | — | `embed()`s the five `.bin` files as ROM data, ties `CrossoverTable`'s length to `SolidityTable`'s (`:122-123`) |
| runtime read | `Collision_GetType` | `engine/level/collision_lookup.emp:27` | the ONLY runtime reader of the baked attr byte; single-plane per call, by contract |
| runtime callers | `player_sensors.emp`, `player_common.emp` | (2 files, confirmed exhaustive by grep across `engine/` and `games/sonic4/`) | every call sets `d3` before calling; none queries both planes for one position |
| layer write | `path_swap.emp` `PathSwap_Main` | — | writes `Sst.layer` directly from an OBJECT, never reads the cell word |
| layer write (painted) | `Player_LoopCrossover` | `games/sonic4/player/player_common.emp:735`, called `:853` | reads `CrossoverTable[attr]`, writes `Sst.layer`; does not touch solidity bits at all |
| build-time assertions | `tools/collision_consistency.py` + `tools/test_collision_consistency.py` | — | R1-R6 (crossover legality, preservation, table-length parity); none of the six assertions is about "solid on both" — there is no rule to write because there is no state |

**Every touch point found, aurora side** (read-only, at `06f1ecd5`, not modified by this
document): `collision-cell-word.ts` (pack/unpack, bits 0-13), `layer-transition.ts`
(bits 14-15, the crossover authority), `both-planes-paint.ts` (the gesture and the derived
predicate), `editing/collision-word.ts` (`collisionPaintWord` — the per-destination merge
that both single-plane and both-planes strokes go through), `s4-collision-adapter.ts` (the
file I/O that produces the `.bin` files aeon's bake reads), `crossover-audit.ts`
(detects but does not block a reserved value — booked separately in
`docs/DEFERRED_WORK.md`'s "R1 has a detector and no defence" entry, unrelated to solidity),
`CollisionPalette.tsx`, `MapViewport.tsx`, `ClassicCollisionPanel.tsx`, `both-planes-lens.ts`
(UI), and the corresponding `test/collision/*.test.ts` files.

**Nothing found, either side:** no function anywhere reads plane A's word to decide plane
B's attr or vice versa; no runtime call site fetches both planes for one world position; no
existing assertion or table depends on a combined value. This is the basis for §2's claim
that a combined state has no consumer to serve.

---

## 4. Option A — a format change

**What would have to move.** Every bit is spoken for (§1): solidity's 2 bits carry all four
legal values, crossover's 2 bits carry all three legal values plus a hard-errored fourth.
The **only** bits in the whole word that have never taken a non-zero value in real content
are bits 8-9 of the shape field: `BLOCK_ID_MASK` is 10 bits wide (0-1023), but the imported
S&K base bank has exactly 256 shapes — confirmed directly, `games/sonic4/data/collision/
base/heightmaps.bin` is 4096 bytes = 256 × 16 (`stat` at our SHA) — and the max shape index
actually painted in the only authored section is 255 (decoded directly from
`section_0.collattr.bin`/`.collattrb.bin`, both planes). So a format change adding a
"SOLID_BOTH" flag can only take those two bits; there is nowhere else to put it.

**What it would cost:**

- **ROM: $0$.** Whatever a flag at bits 8-9 triggered, the five baked tables
  (`HeightMaps`/`HeightMapsRot`/`AngleTable`/`SolidityTable`/`CrossoverTable`) and the
  per-block embed format are unchanged — the flag would only change what the BAKE does with
  a word, not what it emits. Same as Option C, below.
- **The last free bits, spent for nothing more than Option C already gives for free.**
  Whatever headroom bits 8-9 represent for a future shape-bank expansion past 256 (the S&K
  base bank's current ceiling) is gone the moment they carry unrelated meaning. Option C
  spends none of it.
- **A correctness hazard Option C does not have.** For the flag to save an author from
  writing plane B's word, the bake would have to read ONE plane's word and either (a)
  synthesize plane B's attr from it, ignoring whatever `.collattrb.bin` actually holds at
  that index, or (b) require the SAME flag painted symmetrically on both planes — which is
  exactly as much authoring effort as painting the solidity twice, and buys nothing. Path
  (a) is the hazard: at any cell where an author had painted plane B to genuinely diverge
  (all 44 "solid on B only" cells in section 0 alone, measured in §2), a flag set on plane A
  would silently overwrite intent the author never touched. This is the same class of defect
  `docs/LOOP_CROSSOVER_ENCODING.md` §3.4 records against `repaint_word`'s old behavior and
  aurora's own `both-planes-paint.ts:22-41` names as *"the trap this module exists to
  close"* for the crossover field — a single value computed from one plane's data and
  broadcast onto the other's. Nothing in this repo asserts against it today because there is
  no such flag to test.

**Verdict: strictly worse than Option C for identical ROM/RAM cost.** It spends the word's
last headroom, adds bake complexity, and introduces exactly the kind of silent-overwrite
hazard this codebase has already had to fix once for the crossover field.

---

## 5. Option B — a second word

**What it would look like, and the two places it could live.**

*(a) Authoring-side third plane file.* Add a third per-section file the same shape as
`.collattr.bin` — 256×256 cells, 2 bytes/cell. Measured directly: `section_0.collattr.bin`
is 131072 bytes (`stat`, our SHA); a third file of the same shape costs exactly that, per
section, **whether or not the section has a single authored cell** — the file format is
fixed-resolution, not sparse. Across OJZ act 1's 9 sections (`section_0` through
`section_8`, confirmed by listing `*.collattr*.bin`), that is `9 × 131072 = 1179648` bytes
(1.125 MiB) of new authoring-side data added to the repo for a fact that is already fully
determined by the two files that exist. Eight of those nine sections are entirely
unauthored today (§2) — this cost is paid by every section whether or not it ever uses the
feature, which is exactly the objection `d-39`'s own `parallel_plane` option was rejected
for (*"real memory… paid by levels that never use the feature"*, `decisions.jsonl:56`),
applied here to a fact that costs nothing when derived instead.

*(b) A genuinely new baked table*, sized like `CrossoverTable` (256 bytes, one byte per
interned attr index — confirmed by direct file size: `crossover.bin` and `solidity.bin` are
both exactly 256 bytes at our SHA) would cost +256 B ROM if it existed, PLUS it would widen
the `AttrSet` intern key to a 5-tuple, further fragmenting the shared 256-slot attr budget.
Measured directly at our SHA (decoding `heightmaps.bin`/`angles.bin`/`solidity.bin`/
`crossover.bin` together for used vs. unused indices): **31 of 256 slots used, 225 free**
(this supersedes the anchor doc's "20 of 256" figure, which was measured at `fde35b2f`,
before `8a4313b5`'s key-widening for the crossover field split some previously-shared
entries — the anchor's own §5 row 6 predicted exactly this kind of growth). A sixth
dimension in the key would cost nothing here (225 slots of headroom is ample for a loop's
handful of marked cells), but it would still be **pure duplication**: the fact this table
would hold — "is this attr's cell also solid on the other plane" — is not new information;
it is computable from the SAME two plane files' existing solidity fields at bake time, with
zero storage.

**Verdict: real, measured, and avoidable.** Whether scoped as an authoring file (1.125 MiB
across the current act, for content that is 8/9ths unauthored) or a ROM table (+256 B and a
wider intern key), Option B buys a fact Option A and Option C already have for nothing.

---

## 6. Option C — outside the cell word (recommended, and already shipped on both sides)

**Cost, measured:**

- **ROM: $0$ bytes.** The five collision tables are unchanged in format and size
  (`heightmaps.bin` 4096 B, `heightmaps_rot.bin` 4096 B, `angles.bin` 256 B, `solidity.bin`
  256 B, `crossover.bin` 256 B — all measured at our SHA). A cell painted "solid on both" is,
  to `bake_plane_cell`, two ordinary non-zero-solidity words at the same index across two
  files — indistinguishable from two cells an author happened to paint solid by hand in both
  files separately. No new code path in `apply_editor_collision_overlay` is needed; it
  already interns each plane independently (§2).
- **RAM: $0$ bytes.** `Tile_Cache_Collision` stays `TILE_CACHE_COLL_SIZE × TILE_CACHE_COLL_PLANES`
  = 2400 × 2 = 4800 bytes (`engine/system/constants.emp:744-746`), and the per-block ROM
  embed stays `BLOCK_COLL_SIZE` = 256 B/block (`:875,890`) — neither constant nor its
  consumers change.
- **Authoring cost: paid once, in aurora, already spent.** `both-planes-paint.ts`
  (`d1ac8c76`, 2026-08-29) turns "paint solid on both" into one gesture instead of two,
  wired into the real paint-stroke handler (`MapViewport.tsx:2653`) and a visualization lens
  (`both-planes-lens.ts`) that draws the DERIVED fact rather than trusting a stored one.
- **Bake/engine cost: $0$ new code.** Nothing in `tools/collision_pipeline.py`,
  `tools/ojz_strip_gen.py`, or `engine/level/collision_lookup.emp` needs to change. The
  representation this option describes is not a future state to build toward; it is what
  the two-plane architecture has done since before this document, and the 1056 cells
  measured in §2 are it in production today.

---

## 7. Recommendation

**Option C.** Not as a preference among three untried designs, but as a report that it is
already built, on both sides of the wall, and has been for the four days between aurora's
`both-planes-paint.ts` (2026-08-29) and this document's cut. Option A would spend the word's
only remaining headroom for a correctness hazard and no ROM saving over Option C. Option B
would cost real, measured bytes — 1.125 MiB of authoring-side duplication or a widened,
256-byte ROM table — for a fact that is already free.

**What would change my mind:** a runtime consumer that needs "is this cell solid on both
planes" as a single fact at a position where only one plane's tile cache is resident, without
being willing to pay for a second `Collision_GetType` call. Today no such consumer exists —
every call site queries one plane by design (§2, §3), and the query is cheap enough
(`Collision_GetType` is one bounds-checked table fetch) that even a hypothetical future need
could likely be answered by calling it twice — with `d3 = 0` then `d3 = 1` — rather than by
storing a combined value that could disagree with the two independent facts it summarizes.
If a future feature genuinely could not afford two calls (a per-frame budget tighter than
`Player_LoopCrossover`'s own measured 106-538 cycle range, `docs/LOOP_CROSSOVER_ENCODING.md`
§5 row 13), that would be the moment to revisit — and even then, Option B's 256-byte table
is cheaper than Option A's flag, since it would not need to touch the word at all.

---

## 8. What could NOT be established in this pass

- **Whether aurora's `both-planes-paint.ts` gesture has been used to author any REAL content
  yet**, as opposed to being wired into the UI and covered by synthetic tests
  (`test/collision/both-planes-paint.test.ts`, not read in this pass). Section 0's measured
  1056 both-solid cells could predate the gesture (painted by hand into two files before
  2026-08-29) or postdate it; this document did not determine which, and it does not change
  any number above either way — the representation's cost is the same regardless of how the
  1056 cells were produced.
- **The exact number of unique 16×16 blocks in OJZ act 1's deduplicated block pool.**
  Section 6's Option B(a) cost is exact (file-format-driven, resolution-fixed); a
  hypothetical Option B(b)-style per-block ROM cost (were "solid on both" ever pushed down
  to the block-embed format rather than staying at the 256-slot attr-table level) would be
  `128 B × (number of unique blocks)`, and that block count was not measured — it would
  require running the bake pipeline, which this documents-only pass did not do. Not needed
  for the recommendation, since Option C requires no new block-format bytes at all.
- **Whether there is a formal `decisions.jsonl` entry closing decision 4 specifically.**
  `d-39`/`d-39-corrected` cover the CROSSOVER field's encoding (a real, ruled decision); the
  "solid on both" half of decision 4 was folded into `d-39-corrected`'s withdrawal text as a
  hypothesis and then confirmed by `LOOP_CROSSOVER_ENCODING.md` §2.1/§10 without ever
  becoming its own numbered decision — because, per this document, it turned out to need no
  ruling at all. Whether the hub considers decision 4 formally closed, or wants a
  `decisions.jsonl` entry recording that closure explicitly, is outside this document's
  scope to decide.
- **Whether any tool outside `tools/collision_pipeline.py`/`ojz_strip_gen.py`/
  `ojz_block_gen.py`/`repaint_ojz_collision.py` touches the raw per-plane word.** The
  enumeration in §3 covers the full aeon collision pipeline and both engine call sites; a
  handful of adjacent tools (`tools/verify_level_bin.py`, `tools/collision_consistency.py`)
  reference "solidity" but were confirmed to operate on the BAKED attr byte or the emitted
  tables, not the raw 16-bit word — read closely enough to be confident of that, not
  exhaustively line-by-line.
- **No build was run and no emulator was used**, per the brief's bar (documents only; this
  parcel touches nothing the build reads).

---

## 9. Doc sync

`docs/DEFERRED_WORK.md` gets a short pointer paragraph appended to the existing "AN AUTHORED
LOOP CROSSOVER REACHES THE FILE AND NEVER THE ROM" entry (the block covering the crossover
field's history), naming this document as the closed-out answer to decision 4's "solid in
both planes" half specifically — that entry is the closest existing home for this topic and
already tracks the sibling crossover-field history in detail. No other line in
`docs/DEFERRED_WORK.md` is touched.
