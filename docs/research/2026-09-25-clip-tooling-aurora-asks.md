# Clip tooling: aurora's two asks (row-8 work, 2026-09-25)

Source of the asks: `docs/research/2026-09-17-s2-compressed-act-design.md` §8, the
"RULED 2026-09-25" block. Aurora's Sonic 2 donor page calls these tools. Both shapes below are
meant to be vendored, so every field is listed with its meaning.

Branch `parcel/clip-tooling-aurora-asks`. Files: `tools/clip_act_bake.py`,
`tools/clip_manifest.py`, `tools/test_clip_pool_per_clip.py` (new),
`tools/test_clip_manifest_json.py` (new), and the §8 note in the design doc.

## What was already there, and a correction

The bake's JSON file is `clipact.json`, confirmed at `tools/clip_act_bake.py` `emit()`. It is
written to `bake --out DIR`, or to `<manifest dir>/baked/` by default.

**Correction to design §8.** The paragraph "ALL FOUR SHIP 2026-09-17" said parcel 3 put
"tiles, pages and worst window" per clip in `clipact.json`. It did not. Those were ACT-level
only (`pool.tiles`, `pool.pages`, `verdict_at_placement`). The only per-clip data was the
collision readout (`collision.per_clip`). The §8 text is corrected in place. The worst camera
window is still act-level only. Nothing reports it per clip, and this parcel did not add it:
it was not asked for, and it needs a definition of "the clip's neighbourhood" that nobody
has written yet.

## Ask 1: per-clip unique tiles and pages in `clipact.json`

### Shape

The new keys sit inside the existing `pool` object, next to `tiles`, `pages`, `page_tiles`,
`page_lengths` and `pool_bin`, which are all unchanged:

```jsonc
"pool": {
  "tiles": 872, "pages": 14, ...,                      // unchanged, act-level
  "per_clip": [                                        // index-aligned with top-level "clips"
    { "id": "ehz_act1", "index": 0,
      "tiles": 479, "tiles_added": 479,
      "pages_touched": 8, "pages_exclusive": 7 }, ... ],
  "per_corridor": [ /* same row shape */ ],            // index-aligned with "corridors"
  "per_clip_fields": { "<field>": "<meaning>", ... }   // the table below, verbatim
}
```

| field | meaning |
|---|---|
| `id` | the clip's (or corridor's) id from `clips.json` |
| `index` | its position in `clips.json`'s `clips` list (for `per_clip`) or `corridors` list (for `per_corridor`) |
| `tiles` | distinct pool tiles (post-dedupe canonical tiles, with flips folded) that this rectangle's cells reference, **excluding the blank tile at pool slot 0**, which the act always carries whatever is pasted |
| `tiles_added` | of `tiles`, the ones no EARLIER row references. Rows run through the clips in manifest order, then the corridors. `sum(tiles_added over every row) + 1 == pool.tiles`, where the 1 is the blank |
| `pages_touched` | pool pages holding at least one of this rectangle's `tiles`, meaning the pages that must be resident to draw ALL of it. A shared page counts for every row that touches it, so the sum over rows can exceed `pool.pages` |
| `pages_exclusive` | the pages in `pages_touched` that NO other clip or corridor touches, meaning the pages that are in this pool only because of this rectangle. The sum over rows is never more than `pool.pages`. It does not predict what removing the clip would save, because a re-bake re-places the whole pool |

### What a clip's pages means, and why

A page holds 64 tiles and belongs to ONE placement of the WHOLE act. Clips of one zone can share
a page. At a spatial seam, one page can hold the tail of one zone and the head of the next. So
when a page is shared, no single clip owns it, and any one number called "pages" would be read
one way by one author and the other way by the next. That is why there is **no field called
`pages`**. There are two instead, one for each question an author choosing what to paste
actually asks:

- **"How heavy is this clip to stream?"** → `pages_touched`. This is the clip's own footprint,
  and the camera-window budget is built out of it.
- **"How much pool exists only because of this clip?"** → `pages_exclusive`, which never
  double-counts.

Measured on `s2_ehz_cpz`, page 7 is touched by `ehz_act1`, `cpz_act1` AND the corridor. The
touched counts sum to 8 + 7 + 1 = 16 against a 14-page pool. The exclusive counts are 7 + 6 + 0
= 13, and 13 plus the shared page 7 makes 14. A single "pages" field would have given this act
16 pages or 13, depending on who wrote the tool.

For tiles, `tiles` is the placement-independent size of the clip, and `tiles_added` follows the
same manifest-order convention as `collision.per_clip.attr_entries_added`. A tile that two
clips share is credited to the first one.

### Same code path as the act figures

`pool.tiles` is `len(placement["unique"])` and `pool.pages` is `len(placement["pages"])`.
`pool_contributions()` reads the same placement dict: `canon`, the post-split canonical id of
every cell, and `page_grid`, the per-cell page index that `fg_page_order._evaluate` builds and
the window budget counts. It slices both by each rectangle's `dst_rect`. The blank is identified
by its SLOT, 0, which is the same rule the page grid uses to give the blank no page. Nothing is
deduplicated or placed a second time.

### Before and after on `s2_ehz_cpz`

Before (the tip of master at `78f51b0d`), `pool` in `clipact.json`:

```json
{"page_lengths": [64,64,64,64,64,64,64,64,64,64,64,64,64,40], "page_tiles": 64,
 "pages": 14, "pool_bin": "pool.bin (pages padded to page_tiles; slot = page*page_tiles + i)",
 "tiles": 872}
```

After, the same five keys with the same values, plus:

```json
"per_clip": [
  {"id": "ehz_act1", "index": 0, "pages_exclusive": 7, "pages_touched": 8, "tiles": 479, "tiles_added": 479},
  {"id": "cpz_act1", "index": 1, "pages_exclusive": 6, "pages_touched": 7, "tiles": 390, "tiles_added": 390}],
"per_corridor": [
  {"id": "ehz_to_cpz", "index": 0, "pages_exclusive": 0, "pages_touched": 1, "tiles": 2, "tiles_added": 2}],
"per_clip_fields": { ...the table above... }
```

The tiles add up: 479 + 390 + 2 + 1 (the blank) = 872, which is `pool.tiles`. The corridor's
third tile is its blank tile, which deduplicates into the act's blank. On the other fixtures:
`s2_two_clip` (placed by the searched rung, so its canonicals are split by zone) gives 469 + 565
+ 1 = 1035 tiles, with pages 8 + 9 all exclusive (17 pages). `s2_two_clip_pins` gives 797 tiles
in 13 pages. `s2_ehz_boot` gives 480 tiles in 8 pages.

`tools/clip_rom_bake.py` copies `summary["pool"]` into `clip_rom_bake.json`, so that report now
carries the rows as well. This is a JSON report and not a ROM input.

### Proof that nothing the ROM reads moved

- All four committed fixtures (`s2_two_clip`, `s2_two_clip_pins`, `s2_ehz_cpz`, `s2_ehz_boot`)
  were baked before and after the change into scratch directories. Every non-JSON output file
  is byte-identical: 14, 14, 129 and 92 files. `clipact.json` is identical once the three new
  keys are removed. Wall-clock `seconds` fields and the out-dir-relative `tileset_file` path
  were ignored, because they differ between any two bakes.
- `S2CLIP=s2_ehz_cpz ./build.sh` produced `s4.s2clip.bin` with crc `9a3533f1` at 822,334 B,
  both before the change and after it.

### Gate

`tools/test_clip_pool_per_clip.py`, 12 rows, run by the pre-build tool lane. It bakes all four
committed fixtures. Between them they reach both placement rungs, a corridor row and a
single-clip act, and a row asserts each fixture still does. The gate then:

- re-derives every row OFF DISK. It decodes `section_N.local.bin` through
  `secN_local_map.bin` to get a global slot per cell, which is the decode
  `page_grid_from_tree` does for the window recount, and requires equality with the row;
- requires that the union of the rows' tile sets, plus slot 0, EQUALS the set of occupied
  pool slots (from `page_lengths`), and that its size is `pool.tiles`;
- requires `sum(tiles_added) + 1 == pool.tiles`;
- requires that the union of the rows' pages is `range(pool.pages)`;
- requires `pages_exclusive <= pages_touched` for every row, and
  `sum(pages_exclusive) <= pool.pages`.

Red-first, with the mutations on disk and restored from the committed baseline
(`git checkout HEAD --`):

- keep the blank in `tiles` → 8 failed, 4 passed;
- count a page as exclusive when `touch >= 1` instead of `== 1` → 4 failed, 8 passed, on the
  two fixtures where a page is actually shared. This also shows that the other two fixtures
  share no page.

## Ask 2: `tools/clip_manifest.py validate --json`

### Shape

This is one JSON document on stdout, with `indent=2, sort_keys=True` and ASCII-escaped:

```jsonc
{ "schema": 1,                 // VALIDATE_JSON_SCHEMA; bumped on any change a reader could see
  "ok": false,                 // true iff the exit code is 0
  "refusals": [                // [] when ok. At most ONE entry today (load() stops at the first
    {                          //   refusal); it is a list so that can never change the shape
      "rule": "R7",            // the message's leading tag: R1-R12 or K1-K3; null for an untagged
                               //   refusal (a top level that is not an object, or an engine
                               //   constant the loader cannot read)
      "subjects": [            // WHICH clip(s)/corridor(s); [] = an act-level refusal (R1, R2,
        { "kind": "clip",      //   the act id under R3, an empty clips list, corridors not a list)
          "index": 1,          // position in clips.json's `clips` (kind clip) or `corridors`
          "id": "cpz_s2" }     // the entry's id, or null when it has none (not an object, no id)
      ],                       // TWO subjects for a pair rule, first claimant first: R10 overlap
                               //   (clip/clip or clip/corridor), duplicate id (R3, K1 vs a clip),
                               //   duplicate region_id (R3)
      "message": "R7 clip 'cpz_s2': src 2048x2048 != dst 1024x2048. ..." }
                               // the human sentence, EXACTLY what human mode prints after
                               //   "clips.json REFUSED — "
  ],
  "warnings": [                // W2 / W3, each {rule, subjects, message}, in the order raised;
    ... ]                      //   kept when a later rule refuses. W3 names every clip in the
}                              //   mixed section
```

On success the document has the same shape: `{"ok": true, "refusals": [], "schema": 1,
"warnings": [...]}`.

**Exit codes are unchanged:** 0 when accepted, 1 when refused. **Invocation:** `validate
<clips.json> [--donor-root DIR] --json`, where the flag goes after the path, like
`--donor-root`.

### Deliberate limits that aurora should know about

- **Only a `ClipManifestError` is a refusal, in either mode.** Two inputs fail differently.
  If the manifest is not JSON at all, or the path does not exist, the loader raises the way
  it always has: a traceback, exit code 1, and **nothing on stdout**. The human mode behaves
  exactly the same way. A caller has to treat "exit 1 with stdout that is not JSON" as a
  crash, not as a refusal. I did not wrap these errors as refusals, because they are not
  rule violations and reporting them with `rule: null` would disguise a bug as a verdict.
  This is aurora's call to raise if it wants them wrapped.
- **`USAGE` is unchanged, byte for byte.** It is human output, and the brief said the human
  mode must not move. So `--json` is documented in the module header and not in the one-line
  usage string. A usage error under `--json` still prints the human usage text and exits 1.
- **The rule tag is read back from the message**, which is the header's existing contract
  ("each is named in the message it raises or warns with"). The tag is therefore spelled in
  one place only. The subjects are attached at each raise site through
  `ClipManifestError(message, subjects)`, and the message text did not change.

### Examples

A refusal (`s2_two_clip` with `clips[1].dst_rect.w = 1024`):

```json
{
  "ok": false,
  "refusals": [
    {
      "message": "R7 clip 'cpz_s2': src 2048x2048 != dst 1024x2048. A clip is a paste; nothing in this pipeline rescales nametable cells.",
      "rule": "R7",
      "subjects": [{"id": "cpz_s2", "index": 1, "kind": "clip"}]
    }
  ],
  "schema": 1,
  "warnings": []
}
```

Success on `s2_ehz_cpz`: `{"ok": true, "refusals": [], "schema": 1, "warnings": []}`, exit 0.
The human mode for the same file prints the same lines it printed before this parcel.

### Proof that the human mode did not move

The pre-change `clip_manifest.py` (`git show HEAD:` at the item-1 commit) was staged beside the
new one and both were run over 35 invocations: the 4 fixtures, 22 refusals, W2, W2 followed by
R12, W3, a top-level list, a file that is not JSON, and 4 usage errors (no args, unknown arg,
no mode, bad mode). **35 of 35 had identical stdout and exit code**, and the same last stderr
line. As a control, the same comparison on `--json` does differ: the old tool says "unknown
argument '--json'" and exits 1. The staged copy was deleted afterwards.

### Gate

`tools/test_clip_manifest_json.py`, 31 rows, run by the pre-build tool lane. Each row runs
`main()` in BOTH modes on one mutation of a committed fixture:

- one refusal per reachable rule family: R1, R2, R3 (act id, clip id, duplicate id, duplicate
  region_id, a non-object clip, a missing key), R4, R5, R6, R7, R8, R9, R10 (clip/clip and
  clip/corridor), R11, R12, K1 (pattern, and a clash with a clip id), K2 and K3, plus the
  untagged refusal (`rule: null`, no subjects);
- the warnings W2 and W3, and a W2 that has to survive a later R12;
- success on all four fixtures;
- a real subprocess pair per outcome, to prove the shell sees the same exit codes.

Each refusal row expects the tag its mutation was built to trip, and expects the subjects the
mutation touched, with each id READ from the mutated document. It also requires the human
stdout to equal the warnings rendered as `"  WARNING: …"` lines, followed by `"clips.json
REFUSED — " + message`, and the two exit codes to be equal.

Red-first, with the mutations on disk and restored from the committed baseline:

- drop K from the tag regex → 4 failed (the K1, K1, K2 and K3 rows);
- drop the subjects on the R7 raise → 1 failed (the R7 row);
- make the JSON message diverge from the human sentence (`rstrip(".")`) → 12 failed.

## Totals, landing and CRC

These figures are filled in from the runs in the final report of this parcel (see the commit
that adds them).
