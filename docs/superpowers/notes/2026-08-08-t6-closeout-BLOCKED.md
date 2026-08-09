# T6-review closeout batch — status + blocker (2026-08-08)

Landing the six-item T6 art-streaming review closeout on `feat/art-streaming-p2`.
Three items are docs/comments (byte-neutral); three are byte-changing engine code
that require the coupled sigil golden re-freeze (chain 66). **The byte-changing
half is BLOCKED** — see the blocker section. This note is the durable record; the
byte-changing code edits are preserved verbatim in
`2026-08-08-t6-closeout-items1-3-BLOCKED.patch` (same directory).

## Landed (byte-neutral)

- **Item 4 — ram.emp staging-placement comment reword** (`engine/ram.emp`):
  restated the "sliced path can write past 2048" premise as defense-in-depth
  (chain-65 proved the real bug was Publish's stale-offset write, since fixed);
  placement stays last-in-region (review-adjudicated KEEP). Comment-only, byte-neutral.
- **Item 5 — plan Task 7 demand-page eviction-protection step**
  (`docs/superpowers/plans/2026-08-08-art-streaming-phase2-v2.md`): inserted an
  explicit "design the demand-page-not-in-LRU-until-first-Ref protection in, don't
  soak for the deadlock" step; renumbered the following Task-7 steps.
- **Item 6 — DEFERRED_WORK sigil-ask** (`docs/DEFERRED_WORK.md`): the build-fatal
  `preserves()` dataflow-check recommendation. **Already committed** — a concurrent
  session's broad `git add` absorbed this edit into commit `a1195a5` ("collision
  truth sync"). Text is present and correct; verify with
  `grep "SIGIL ASK" docs/DEFERRED_WORK.md`.

## Blocked (byte-changing — items 1-3)

The three byte-changing edits (all correct in source, they build cleanly — see
Evidence) are held back. They are, verbatim in the patch:

1. **Delete dead `TileCache_Reinit`** + `TileCache_FillAll` precondition comment
   (`engine/level/tile_cache.emp`). Grep-confirmed zero callers; the one remaining
   `Reinit` mention (the `TileCache_WarmupBelowRow` Init-only rationale at :696)
   is reworded so the deletion orphans nothing.
2. **Zero-extend hardening** in `PageCache_Publish .not_pinned` — `moveq #0,d0`
   before `move.b d1,d0` (`engine/level/page_cache.emp`).
3. **Fold `Page_Queued_Bits` clear into `PageIn_Flush`** via eight register-free
   `clr.l` (preserves the proc's `clobbers()` == none); `PageCache_Init`'s clear
   kept (idempotent) (`engine/level/page_in.emp`).

Net parcel size: **-56 bytes** (Reinit deletion dominates; +48 for the clr.l block,
+2 for the moveq), absorbed at the `org $10000` object-bank boundary — no anchor
move, no placement change.

## THE BLOCKER — chain-65 golden is not reproducible from committed HEAD

A byte-changing parcel must re-freeze the sigil goldens against the chain-65
baseline. That baseline does not reproduce:

- Frozen toolchain (chain 65): `sigil-frozen-0808` / `emit_sound_blob-frozen-0808`.
- A clean build from committed HEAD (`a1195a5`; `bb0667c..a1195a5` is **docs-only**)
  yields `s4.bin` md5 `10844c2addd7d99ce98347ac66278786`, crc32 `de51d2da`.
- The chain-65 golden (`sigil .../golden/s4.bin`) is md5
  `c1c620f0b258008e2a26855d5529de64`, crc32 `5a942cb8`.
- They differ in **6829 bytes**, first at `0x18E` (checksum) then a contiguous block
  from **`0x2624e`** onward — the `HeightMaps` / collision-data region. Header-neutral
  anchors also differ (`693c210b` built vs golden `1a9c6cf6`).
- **Proof the golden baked uncommitted data:** the committed `heightmaps.bin`
  (identical `bb0667c..HEAD`) is **not found anywhere in the golden ROM**. The
  chain-65 golden was frozen against a DIRTY working tree (uncommitted collision +
  OJZ WIP present at ~20:45 capture, since reverted). It corresponds to no committed
  aeon state.

Compounding it, a **concurrent session is live on this branch**: it committed
`a1195a5` at 21:07, absorbed item 6 into that commit, and holds uncommitted OJZ art
WIP (`bg_tiles.bin` 14338->6978, `zone_bg.bin` 8192->4096, mtime 21:04). With OJZ WIP
in place, the build fails outright — `[map.undeclared-island] 0x26192` (`BgAnim_Table`):
the halved OJZ opened a >`ANCHOR_GAP` (0x400) gap. (Confirmed this is the OJZ WIP, not
our parcel: with OJZ restored to HEAD the build is clean.)

Refreezing now would (a) bake transient uncommitted collision/OJZ data into new
goldens, and (b) attribute a multi-KB collision-data anchor move to our -56-byte code
parcel in the provenance chain — a garbage entry. So the ritual was **not run**.

## Evidence that items 1-3 are themselves sound

- Edited code + coherent (HEAD) OJZ builds clean: `s4.bin` md5
  `9619a027cbff64862b7824b69b9692da`, size 413598 (vs baseline 413654 = **-56 B**).
  No `[map.undeclared-island]`, no assembler error, s4lint clean.
- The only blocker is upstream golden/data hygiene owned by the concurrent session,
  not this parcel.

## Recommended path to land items 1-3

1. Quiesce the concurrent OJZ session; get a CLEAN committed tree (no dirty
   collision/OJZ) that reproduces a golden.
2. **First re-baseline the golden to committed HEAD** (its own chain bump — the
   collision-data drift is independent of this parcel). Then the anchors are honest.
3. `git apply docs/superpowers/notes/2026-08-08-t6-closeout-items1-3-BLOCKED.patch`.
4. Run the full parcel ritual: build both shapes (frozen toolchain) ->
   `refreeze --freeze t6-closeout-reinit-delete --ab <this-note> --note "..."` ->
   `refreeze --check` + `pins_rs_is_current` + native gates -> refresh both frozen
   binaries. Expected: the only anchor motion is the -56 B engine shrink, absorbed at
   `org $10000` (EndOfRom unchanged both shapes), mirroring the chain-65 pf_page fix.
