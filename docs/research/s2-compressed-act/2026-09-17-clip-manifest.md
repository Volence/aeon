# S2-COMPRESSED-ACT parcel 3 — `clips.json`, the per-cell tileset key, and the bake that reads it

**Date:** 2026-09-17 · **Branch:** `parcel/s2-clip-manifest` (worktree `aeon-wt-s2clip`, base
`75008de6`) · **Staged plan:** `docs/research/2026-09-17-s2-compressed-act-design.md` §10 row 3.
**Scope:** art and layout only. No collision, objects, engine code, `.emp` or ROM change, and the
committed `games/sonic4/data/editor/ojz/act1` tree is untouched.

## What shipped

| File | What it is |
|---|---|
| `tools/clip_manifest.py` | `clips.json` schema 1: load, validate (R1-R11 refusals, W1-W3 warnings), and the per-cell zone-key grid |
| `tools/clip_act_bake.py` | compose an act from a manifest → real `fg_page_order.place_pool` with a real zone grid → emit the tree, the per-section local maps and the pool → re-count the verdict off disk |
| `tools/test_clip_manifest.py` | 39 rows in the pre-build `pytest tools -m "not needs_build"` lane |
| `games/sonic4/data/clips/s2_two_clip/clips.json` | the row-3 fixture: one Emerald Hill section beside one Chemical Plant section |
| `games/sonic4/data/clips/s2_two_clip_pins/clips.json` | the fixture that can tell a wrong answer from a right one (below) |

The bake output (`<fixture>/baked/`) is gitignored, like the converted donor trees, and for the
same reason and with the same expiry: the moment a clip's bytes reach the ROM (row 6) both have
to be tracked.

## The row-3 check, and why it was restated

The design's check was: *"a two-clip act bakes; `fg_page_order.check` reports the same
worst-window count as `s2_clip_budget.py place` on the same two clips."*

**`fg_page_order.check` cannot be pointed at a second act, and that is deliberate on its part.**
`_known_acts` RAISES on any act whose generated directory is not `fg_working_set.GEN_DIR`, and
`fg_working_set.Model` takes `GRID_W`/`GRID_H` from OJZ act 1's `act_descriptor.emp`. Teaching it
a second act means a `project.json` entry plus a matching `.emp` descriptor — a ROM change, which
is rows 4-6. So the count runs inside `clip_act_bake`, importing the two functions `check` itself
calls (`window_needed`, `budget_verdict`). The arithmetic is shared; only the decoding differs
(`check` S4LZ-decodes `sec{N}_blocks.bin`, the bake reads `section_N.local.bin`) — and the
decoding differs because a block file carries the collision planes, and inventing collision bytes
to reach a number is row 5's work, not filler for row 3.

**Three numbers, not two.** N1 the placement verdict, N2 the recount decoded back off disk, N3
`s2_clip_budget.py place` reaching the same `place_pool` from the donor side without clips.json or
a converted tree.

| fixture | N1 placement | N2 recount off disk | N3 `s2_clip_budget place` | pool / pages / rung |
|---|---|---|---|---|
| `s2_two_clip` (`EHZ:2,0,1,1` + `CPZ:2,0,1,1`) | **12** of 12, 0 of 48,471 over, 682 at the peak (tile left 215 top 10) | **12**, identical in all four figures | **12**, identical in all four figures | 1,035 / 17 / searched |
| `s2_two_clip_pins` (`EHZ:1,0,1,1` + `CPZ:1,0,1,1`) | **10** of 12, 0 of 48,471 over, 1,771 at the peak (tile left 417 top 62) | **10**, identical | **10**, identical | 797 / 13 / shipped |

Plus 1,182 (zone, tile) pairs on the first fixture and 900 on the second verified to resolve to
their own zone's 32 bytes of art.

## The numbers DID disagree, and the design's tool was the one that was wrong

On the tree as committed, `s2_clip_budget.py place EHZ:1,0,1,1 CPZ:1,0,1,1` printed **11** where
the bake printed **10**. Cause, found by reading the pins it reported (`pins [0, True]`):

`place_pool` calls `rule_pins_fn(pages, sets)` and then does `sorted(set(candidates) - {0})`, so
the callable must return **page indices**. `ojz_strip_gen.mark_pinned_pages` returns a
`list[bool]` parallel to `pages`, and `generate()` wraps it at its Pass 4 call. The design's
measurement tool passed the raw function, so the candidate set became `{False, True} - {0}` =
`{True}` = page 1: **every act with any pinned page pinned page 1, and could pin nothing else.**

I believe the bake's 10, because its wiring is `generate()`'s wiring — the thing the ROM is
actually built with. Fixed in `s2_clip_budget.py` with `--pins raw` preserving the old behaviour,
the same shape parcel 1 used for `--profiles horizontal`.

**§3.3's published table does not move, and that was measured rather than assumed.** No page on
those four acts reaches the pin rule's 75%-of-sections threshold, so the candidate set is empty
either way. Re-measured both ways: 5 whole zones, pins `[0]`, worst 12, 707 positions of 870,231
windows, identical. The defect only bites on a SMALL act, where two sections make the 75% rule
easy to satisfy.

## Section alignment buys less than §2.2 said — with the control that shows it

`python3 tools/clip_act_bake.py measure-alignment`. Two 1024×1024 clips, EHZ and CPZ, in a
2×1-section act; same cells, same tilesets, three placements:

| placement | sections used | local maps | pool | pages | worst window |
|---|---|---|---|---|---|
| separated, one zone per section | 2 | 394 / 224 | 617 | 10 | 7 of 12 |
| adjacent, one zone per section | 2 | 394 / 224 | 617 | 10 | **9 of 12** |
| adjacent, both inside section 0 | 1 | 617 / 1 | 617 | 10 | **9 of 12** |

Row 2 is the control for row 3: the clips touch in both, so "a camera window can hold two zones"
is held fixed and the only thing that varies is whether the section boundary falls between them.
**The page budget is the same either way.** The first cut of this measurement had only rows 1 and
3 and showed 7 → 9, which reads as evidence for alignment and is not: that difference is
adjacency, which is §9.1's corridor argument.

So §2.2's claim that a straddling clip "defeats" per-zone pages is struck — `perzone_pages` groups
by the per-CELL zone key, not by section. What alignment does buy is the local-map column: a
section carries ONE 11-bit local tile map capped at 2047 entries and a mixed section needs the sum
of both zones. The recommendation therefore survives as R11, a refusal with an **in-file** opt-out
(`unaligned_dst_reason`, so the argument is where the next reader will see it), while "two zones
in one section" became W3, a warning — the exact limit is downstream and precise
(`build_section_local_map` raises past 2047) and this one is a cost, not an error.

The 128-px chunk rule is W1, a warning: on the art path a nametable word is per cell and nothing
cares. Its evidence is collision-side, so promoting it is row 5's call. **The hard alignment rule
§2.2 never stated is 8 px** (R6): a section file is a grid of 8-px cells with no sub-tile
addressing at all.

## The manifest, as settled

Rectangles are integer world pixels on both sides, and `units: "world_px"` is a required field so
the unit is part of the interface rather than a convention two tools each remember.

```jsonc
{ "schema": 1, "units": "world_px", "id": "s2_two_clip", "name": "...",
  "act": { "grid_w": 2, "grid_h": 1 },
  "clips": [
    { "id": "ehz_s2", "donor": "s2disasm", "zone": "EHZ",
      "src_rect": { "x": 4096, "y": 0, "w": 2048, "h": 1024 },
      "dst_rect": { "x": 0,    "y": 0, "w": 2048, "h": 1024 },
      "region_id": "ehz_s2",            // optional: aurora's write-back
      "unaligned_dst_reason": null } ]} // optional: the R11 opt-out
```

Changes from the design's §8 sketch, each with its reason, all patched into §8 in place:

- **donor and zone are separate fields** (`"s2/EHZ"` is gone). Two donor trees are registered and
  five zone names exist in **both**, meaning different levels.
- **the act's section grid is declared, not inferred.** An act with a trailing empty section is a
  different act: the camera-window sweep the budget is counted over is a function of the grid.
- **`dst_rect` keeps `w`/`h` and they must equal `src_rect`'s.** A clip is a paste, never a scale.
- **there is no `palette` field, and a manifest carrying one is refused** — see the contract
  section below.
- **the zone key is derived, not authored:** distinct `(donor, zone)` pairs in first-appearance
  order. Two clips of the same zone share a key, or the pool would carry that zone's art twice.

Rules: R1 schema + units · R2 act grid within `MAX_ACT_SECTIONS` · R3 ids · R4 donor/zone
registered and converted · R5 rect shape · R6 multiple of 8 px · R7 dst size == src size · R8
inside the act · R9 inside the donor's **crop** (not its zero padding) · R10 no dst overlap · R11
section-aligned origin, in-file opt-out. Warnings: W1 128-px src · W2 blank clip · W3 a section
holding two zones.

R9 is worth calling out on its own: the converted tree is PADDED up to whole sections, so a rect
can be inside the files and outside the level. `s2_clip_budget.clip` truncates such a rect
silently (it slices a numpy array), which is how a clip can measure smaller than it reads.

## The multiple-tileset finding

The per-cell key is **forced by the format, not chosen**. An editor word's tile index is 11 bits
into one act-wide tileset, so a single tileset tops out at 2048 tiles — against the design's own
2,965 canonical tiles for six clipped zones (§0 item 2). There is no version of this act that
concatenates the zones into one blob. That is worth knowing before row 6 designs the runtime side.

## Answering the aurora regions contract

Four constraints came from the aurora lane mid-parcel; all four verified here firsthand by reading
`empyrean:contract/schema/aurora-regions.schema.json` at `0742b5ed`, not taken on report. `$defs/
region` is `required: [id, rect, preset]` with `unevaluatedProperties: false`. All four accepted;
two made the design better.

1. **`preset` is required and a donor zone cannot supply it.** So there is no preset or palette
   field here, and a manifest carrying `palette` is REFUSED rather than ignored — a
   silently-dropped field is how two tools end up disagreeing about which was supposed to decide.
   What a clip supplies is the donor's 96 bytes (`donors/<donor>/<zone>/palette.bin`, sha256 in
   `zone.json`, carried into the bake's `clipact.json`); the preset that installs them is named by
   aurora at paste time.
2. **rect is integer world pixels and its edges need not fall on the section grid.** Agreed, and
   `units` is now declared in the file so nothing rounds at the boundary. A `dst_rect` is a legal
   region rect; the converse does not hold, because R6 and R11 are stricter. Stricter is the safe
   direction, and a gate row pins that it never becomes looser.
3. **Region ids are `^[a-z][a-z0-9_]{0,31}$`.** Act ids, clip ids and any `region_id` are now held
   to exactly that pattern (they were `[A-Za-z0-9_-]+`), so a clip id is one aurora can use
   verbatim and one rectangle keeps one name across both documents. Donor and zone names, where
   upper case belongs, stay in their own fields. `region_id` is documented as aurora's write-back
   of an id **it** derived, validated against the pattern, and refused if two clips claim one
   region.
4. **No extension point, so provenance is decided here rather than discovered later:** it lives in
   `clips.json` and in the `clipact.json` the bake writes. The region's `name` (free text, ≤64
   chars, never read by the engine or the generator) may carry a human-readable echo such as
   `EHZ (s2disasm) clip ehz_s2` — but it is an echo, never the record.

A gate row re-derives `REGION_ID_PATTERN` from the schema file when the suite contract is checked
out beside this repo, and SKIPS SAYING SO when it is not, rather than passing on a hard-coded copy
that could drift from the schema it claims to mirror.

## The gate, and what stops it being vacuous

39 rows, all in the pre-build lane. Three traps and what is done about each:

- **A worst-window agreement is cheap.** `PAGE_FRAMES` is 12 and every S2 act the design measured
  lands at exactly 12, so "both tools said 12" can be true of two tools that agree about nothing —
  and indeed `s2_two_clip` answers 12 with the pin rule wired correctly OR wrongly.
  `s2_two_clip_pins` answers 10 vs 11, and `test_the_pin_wiring_moves_this_fixture` asserts the
  two wirings still differ, so the discriminating fixture cannot quietly stop discriminating.
- **The zone key can be vacuous too** if the two zones never share a tile index.
  `test_the_two_clips_actually_collide` counts the shared indices, and
  `test_a_uniform_zone_key_breaks_the_art` is the converse control.
- **A refusal row can pass by raising for the wrong reason,** so each asserts its own rule tag
  starts the message. That caught the R10 row: its mutation was being refused by R11 first, and
  the row was green without ever reaching R10.

**Eight mutations, each applied on disk, each restored from a committed baseline.**

| # | mutation | result |
|---|---|---|
| M1 | `cell_grids` writes a uniform zone key | 9 failed / 21 passed |
| M2 | `rule_pins` returns the raw `list[bool]` | 3 failed / 27 passed — and only on the discriminating fixture |
| M3 | one emitted local-map entry corrupted | the bake itself refuses; 10 errors / 20 passed |
| M4 | R9 checks the padded grid instead of the crop | 2 failed / 28 passed |
| M5 | local maps built act-wide instead of per section | 1 failed / 29 passed |
| M6 | the id pattern loosened back to `[A-Za-z0-9_-]+` | 4 failed / 35 passed |
| M7 | the `units` check removed | 1 failed / 38 passed |
| M8 | a `palette` field accepted and ignored | 2 failed / 37 passed |

## Two other gates caught this parcel, and both were right

Neither fires when the new gate is run alone — only in the full lane, which is the argument for
running the full lane rather than the file you just wrote.

- `test_cli_dispatch_refuses::test_the_ladder_population_is_still_the_roster`: both new tools
  joined the argv-dispatch population unrostered. Both are MODES-table tools born in the fixed
  form — the dispatch runs before any handler, so an unrecognised mode reaches no writing branch,
  which matters for `clip_act_bake bake`, which writes. Measured rather than claimed: `not-a-mode`
  on each printed usage, exited 1 and left the tree byte-identical. Population 18 → 20, plus two
  subprocess rows.
- `test_land_gate_classifier::test_every_docs_path_named_in_code_is_covered`: the gate named a
  bare `docs/research/s2-compressed-act` string to put it on `sys.path`. Fixed at the source — the
  module names the file it depends on and takes the `sys.path` entry from its dirname — and
  `land_gate.py` gained a CHECKED rule for that directory, as a PREFIX rather than the one `.py`,
  because importing it makes the audit record a directory listing and a bytecode-cache read too
  (verified: the leaf rule left 2 of 3 findings standing).

## Evidence

Pre-build tool lane, `__pycache__` cleared, `python3 -m pytest tools -m "not needs_build" -q`:
**4 failed, 2965 passed, 2 skipped, 28 deselected, 55 errors, 143 subtests passed in 64.32 s.**

The 4-failed/55-error family is the pre-existing artifact-freshness one and it was **established
by a control taken BEFORE this parcel touched anything**: the same worktree at base `75008de6`,
with the converted donor trees already present, gives **4 failed, 2924 passed, 2 skipped, 28
deselected, 55 errors in 63.80 s** and a FAILED/ERROR node-id set that is byte-identical to the
one above. The only difference between the two runs is this parcel, and the delta is +41 passed =
39 gate rows + 2 subprocess rows. (Taking the control first is a stronger form of the
move-the-files-aside control, not a weaker one: nothing had to be reconstructed.)

`tools/landing_build.sh` **exit 0, `finished=0`**, three shapes built: `s4.bin` 821,479 B
(md5 `ae62156a66c9c3f13e93940e938c340e`), `s4.debug.bin` 848,075 B
(md5 `b15ef259523f67ac963ef0cf4df003dc`), `demo.debug.bin` 104,707 B
(md5 `f740c22498f6ad132ac9f8bd978c9350`) — the same sizes parcel 2 booked, as expected from a
parcel that changes no ROM byte. Its in-build pre-build lane on the freshly built tree is
**3024 passed / 2 skipped / 0 failed / 0 errors** (= parcel 2's 2983 plus exactly this parcel's
41 rows), and the needs_build lane is **27 ran / 0 deferred / 0 failed / 1 exempted**.

Wall clock at measurement: 2026-09-17, dev box up 1 day 20 h, load average 1.7-9.5 across the
runs. No emulator was used.

## What row 4 inherits

- **`clips.json` is the interface and it validates today.** `clip_manifest.load(path,
  donor_root=...)` returns a `ClipAct` whose `cell_grids()` gives `(words, zone_id)` for the whole
  act. Row 5 needs the same rectangles for the collision planes and should take them from here
  rather than re-deriving them.
- **W1 is row 5's to rule on.** 128-px chunk alignment of `src_rect` is a warning because nothing
  on the art path cares. Collision is authored per chunk, so row 5 has the evidence to promote it
  — and should, or state why not.
- **The crossover-cut refusal §2.3 promises is not built.** Nothing in this parcel scans the
  source rectangle for a severed loop pair; `apply_editor_collision_overlay` refuses a self-mark
  today, which means a bad clip fails at the bake rather than at the marquee. §8's per-clip
  readout wants it earlier than that.
- **The per-clip readout of §8 is one call away for three of its four items** (tiles, pages, worst
  window — all in the bake's `clipact.json`). The fourth, attr-set entries, needs row 4.
- **`clip_act_bake` does not emit `sec{N}_blocks.bin`,** so nothing here exercises the block baker
  or S4LZ. Row 6 is where the clip act meets `ojz_block_gen`, and it will also be where the
  `fg_page_order.check` restatement above is either resolved (by teaching the committed-tree
  decoder a second act) or permanently accepted.

---

*No `.emp` touched, no ROM byte changed, the committed `games/sonic4/data/editor/ojz/act1` tree
untouched, both donor trees read-only, no emulator used.*
