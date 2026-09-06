# EFFECTS-W1 — the closing inventory, aeon's half

**Anchor: aeon `de559a91`.** Surveyed 2026-09-06 against this tree, with both authorities read at
committed revisions rather than through the sibling path — the DoD spec
(`empyrean:docs/superpowers/specs/2026-08-29-effects-definition-of-done.md`) and
`empyrean:contract/projects.json`, both at `origin/main` after a fetch. Four parcels were in
flight at survey time, so this is a snapshot with a named anchor, not a standing claim.

**What the buckets mean.** LANDED cites the commit that carries the **code**, `--stat`-checked;
OPEN names where it is tracked here; OWNER states the sentence he would have to say; OUT is
descoped.

## Spec items 0-11

| # | Bucket | Evidence |
|---|---|---|
| 0 | LANDED `296feb7e` | `spare_nametable`, 128 tiles at `$6000`; `games/sonic4/vram.toml`, `tools/vram_map.py` |
| 1 | **OPEN** | binding half landed (`ACT_RASTER_REF_KEY`, sections 5/6 sidecars carry live `rasterRef`); the spec's second clause is not done — see contradiction 7 |
| 2 | LANDED `fa99b257` | `tools/sec5_band_witness.py` + the BAND SEEN measurement; the owner has since seen bands himself |
| 3 | LANDED `b81e5daa` + `ce4dbb7c` | chains 201 and 205 |
| 4 | ~~**OPEN**~~ **LANDED** — corrected 2026-09-06, see contradiction 8 | engine half `094496ca` (chain 215); **the authoring half needs NEITHER key: both are at empyrean `origin/main` since `d36d704` (2026-09-03) and both readers land here** (`grep -c` over `tools/effects_gen.py`: `patch_world_ys` 29, `patch_motion` 35, `anchor_sweep` 10, against the 0/0/0 the booking measured at `e190297c`). A document authoring both SHIPS: `games/sonic4/data/editor/effects/presets/ojz_sec5_showcase.json` |
| 5 | LANDED `445a5856` | the generator learns cycles and variants |
| 6 | LANDED `cf3dfb1a` | `RASTER_DENSE_LINE_RAMP_CYC = 304` with its `ensure`; certified on an authored ramp |
| 7 | LANDED `8c75722b` | **booked "unlanded" for five days; it is an ancestor** |
| 8 | LANDED `f0aebbd3` | a vertical band in a ROM, witnessed moving; debug-tier probe content, not the authored act — scope flag below |
| 9 | **OPEN on 9c, but it is CONTENT** — corrected 2026-09-06, see contradiction 8 | 9a `3d00e2c6`, 9b `6381a736`, 9d `957b380f` + on screen `722d1cf2`; **9c's scene key is NOT missing** — `layer.rowRemap` is at empyrean `origin/main` since `3992d16` (2026-09-04 00:24:54 -0400) and its reader landed here in `d593070a` **ten minutes later**. What is left is an authored scene with a `plane_y` that has a visual basis — the 9c block's own last words, *"Ask aurora to author"* |
| 10 | 10a `cb088530`, 10b `577cefd2` LANDED; **10c OUT** | both gates wired in `build.sh` |
| 11 | 11a LANDED **`3d5e0764`**; **11b OUT** | see contradiction 1 — the booked SHA is docs-only |

## `completionRequires`

| key | Bucket | Evidence |
|---|---|---|
| scroll clamp | LANDED `d3b3ab5a` / merge `2718cf0a` | capture `46acfdd0` |
| d-34 | LANDED `55cab5a8` | owner chose `fix`; `cmpi.b #$C1` at two sites |
| d-35 | **OUT** | `d-35-closed`, "no action, will not be fixed" |
| d-32 re-measure | LANDED `2596187e` | verdict "d-32 absent" |
| DMA split-reject reserve | LANDED **`30c0eabc`** | gate wired at `build.sh:1056`; booked closure SHA is docs-only — contradiction 2 |
| base-residue ensures | LANDED `c5129b65` | all four shapes byte-identical |
| `dplc-budget-breach` | LANDED `e15b872d` | peak slots 13 → 10; `tools/test_dplc_recut.py` build-fatal |
| `canopy-gap` | **OWNER** | a cause was found, fires 2,080× over 21,439 driven frames, and is **proven structurally invisible** — so it is not his symptom. Needs: *"here is where and when I see the canopy strip go blank, and whether it fills back in"* |
| `side-items-first` | **OPEN** | `B7-TERMINUS`, `F-CLASS`, `S1S3S9`, `CURVE-DESC`, `FLOOR-FAN`, plus lab rows F4 and F5 |
| `sigil-decouple` | **cannot classify from this tree** | sigil's project; the cut-the-ceremony amendment says it gates nothing here. Reported unknown rather than assumed finished |

## Counts, members named in the same sentence so they cannot drift

- **LANDED (16 rows):** items 0, 2, 3, 5, 6, 7, 8, 10a, 10b, 11a; scroll clamp, d-34, d-32
  re-measure, DMA split-reject reserve, base-residue ensures, `dplc-budget-breach`.
- **OPEN (4):** item 1, item 4, item 9c, `side-items-first`. **⚠ CORRECTED 2026-09-06 to OPEN (3):
  item 1, item 9c (as CONTENT), `side-items-first`. Item 4 moves to LANDED (17 rows).**
- **OWNER (2):** `canopy-gap`, `FLOOR-FAN`.
- **OUT (3):** item 10c, item 11b, d-35.
- **Unclassifiable (1):** `sigil-decouple`.

## Where this tree contradicts a booking — the valuable half

**1. Item 11a's booked SHA is a docs-only commit.** `DEFERRED_WORK` and the lane log both say
LANDED `eb87d2ba`; that commit is **one file**, `docs/DEFERRED_WORK.md`, +29/-6. The code is
`3d5e0764` (`ojz_effects.emp` +104, `tools/plane_base_swap_gate.py` +344). **The mechanism is
real; the SHA on the row does not carry it.** This is the shared protocol's SHA-class bar
landing on our own records rather than on a peer's citation.

**2. The same shape on the DMA split-reject closure.** Booked as closed on `f3e001f6`, which is
`DEFERRED_WORK` alone. The gate's code is `30c0eabc`, invoked at `build.sh:1056` — checked, not
assumed.

**3. A `DATA_GROWTH_RESERVE` figure stale a SECOND time, in a different entry.**
`DEFERRED_WORK:2300-2307` computes a room/spendable table against "16,384 B" citing
`bganim_room.py:398`; the tool reads `DATA_GROWTH_RESERVE = 0xC000` (49,152) at line 169 with
`DATA_GROWTH_GRACE = 0x8000`, and line 398 holds no literal at all. **Every "spendable after"
cell in that table is wrong**, derived from a floor three times too small against a room five
times too large. The DPLC verdict does not rest on it; the table is quoted elsewhere as headroom,
which is how a wrong number travels.

**4. `bg_region` 448 with 128 tiles of headroom is stale, and this one is expensive.**
`BG_TILE_CAPACITY = 400` (`engine/system/constants.emp:607`), and `vram.toml` records
`448 → 400` with `band_reserve 128 → 80`, the 48 having become the `waterline_strips` region.
**So 9d's tiles are SPENT, not available.** Anything pricing against "128 unresident" is pricing
against 80.

**5. A remainder list was stale the day it was written.** `DEFERRED_WORK:18907` (2026-09-03) names
the live remainder as d-34, d-35, d-32 re-measure and the DMA reserve. At that moment **all four
were already dead** in this tree's own ledger and history. The list was carried forward rather
than checked, which is the exact failure the same entry names two paragraphs earlier.

**6. A ruling attributed to the owner is partly ours, and it names the wrong sub-item.** The
10c/11b descoping at empyrean `OVERSEER-LOG.md` 2026-09-04T19:05:26Z reads "the window plane and
**mid-frame base swap** (10c/11b)". The mid-frame base swap is **11a**, which landed 2026-09-03;
11b is Plane Z. The bucket is right and the label is not. **And the "do not spend VRAM on
10c/11b" sentence is aeon's own recommendation (`2b57c48a`) that the hub adopted — not something
he said.** His verbatim words are about dynamic VRAM as a future direction. Read a relay as two
separable things: the quoted ruling, which is his, and the scaffolding around it, which has an
author and is checkable like any other peer claim.

**7. Item 1 reads as substantially landed while its spec clause is unmet.** `authored_probe` is
still emitted (`effects_scenes.emp:241,245`), still bound as row 3 of the effects lab's raster
table (`ojz_scroll_test.emp:2372`), and still stamped. The spec's own cost argument for item 1 —
that deleting the probe removes the cross-seam symbol chain 182 added — has not been collected.

**8. THE THREE "MISSING AUTHORING KEYS" (items 4 and 9c) ARE ALL PRESENT AT CONTRACT TIP, AND
THE REAL CONTRACT GAP IS SOMEWHERE ELSE.** Measured 2026-09-06 against empyrean `origin/main`
`b6913fae`, read with `git -C ../empyrean show "<rev>:<path>"`. This inventory booked 3 keys as
absent; **the count is 0**. Item 4's `patch_world_ys` and `patch_motion` landed empyrean
`d36d704` on 2026-09-03 — the same day the merge message that booked them as blocked was
written, hours later; 9c's `layer.rowRemap` landed `3992d16` on 2026-09-04, ten minutes before
its reader. Neither booking could be contradicted from inside this tree, which is why both
survived: **a green build says nothing about a schema in another repo.**

**What IS a live contract defect, and nobody booked it because it is not a missing key:**
`rowRemap.height_shift` is encoded `3..7` in the scene schema and **only 4 can build** —
`row_remap_ladder16()` (`engine/level/parallax_dsl.emp:396`) is the one ladder that exists, and
the refusal of the other four lives only in `tools/effects_gen.py:152`. The refusal's own
escape hatch is stale too: it names 9b as the fix, and 9b landed a generator that
**deliberately does not write into the tree.** Full derivation, the three closing options, and
the two stale sentences inside the contract itself:
**`docs/2026-09-06-w1-authoring-keys-note.md`.**

**⚠ ALSO CORRECTED THERE: the schema path in every dispatch and doc that names it.** It is
`contract/schema/aurora-effects-preset.schema.json`, not `contract/aurora-…`. A `git show` at
the wrong path fails with "does not exist", **which reads as "the key is absent"** — the exact
misreading this contradiction is about.

## Flagged rather than decided

- **Item 8's scope is a call, not a measurement.** Bucketed LANDED because a vertical band is in
  a ROM and witnessed moving. If item 8 means *a vertical band in the authored act*, it is OPEN
  and waits on the raised `BGANIM_SECTION_CEILING_RULED = 20480` being spent.
- **`side-items-first` is not enumerable to a fixed set** from this tree: whether the lab rows
  F4/F5/F6 sit inside the frozen tier or queue behind it could not be determined here.
