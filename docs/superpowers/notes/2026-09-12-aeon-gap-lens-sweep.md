# Aeon gap lens sweep, 2026-09-12: the two holes the 2026-09-06 panels left

**Review pin: aeon `9fe9ee91`** (origin/master at dispatch). Each seat ran read-only in its own worktree, detached at the
pin, and was clean at the start. No fixes were made during the sweep. The aeon overseer adjudicated after the seats returned.

## Why this sweep, and what it is NOT

The queue row `LENS-SWEEP-COVERAGE` said "the sound driver, the build tools and the engine's system layer were never
swept". **That was stale.** `docs/superpowers/notes/2026-09-06-aeon-lens-sweep.md` ran the full Roster A panel with the ×2
doubling over `engine/**/*.emp` + `games/**/*.emp` (76,111 lines, sound and system included), and
`2026-09-06-aeon-tools-lens-sweep.md` gave `tools/` its first review (Roster B seats T1/T2/T3). The row came from a
2026-08-13 coverage map that predates both. Those two packets name exactly two holes themselves, and this sweep charters
only those:

1. **The Z80 comment surface** — "The Z80 comment surface was not swept at all" (engine packet, "Sampled, not swept").
   Seat **A2 (comment TRUTH)**. *Section below, pending the seat's return.*
2. **The OJZ level bakers** — T1's parent seat "was killed by the account session limit", recorded as
   "UNEXAMINED, NOT CLEARED" and "the single largest gap" (tools packet). Seat **T1 (generator correctness)**.

**Still UNEXAMINED, NOT CLEARED after this sweep:** the engine packet's wider comment population (1,846
`always`/`never`/`cannot`/`guaranteed` universals, sampled ~35 of 217 `the only`-class), the tools packet's 11 of 18
no-assertion test functions and its 14 unexecuted listing gates, `effects_gen.py`'s `render_module`/`generate` (~1,500
of 4,910 lines, see T1's "not covered"), and everything else not named above. **This sweep is not a blessing of any of it.**

Step 0 (standing findings): the 2026-09-06 packets' own rows are tracked in `docs/DEFERRED_WORK.md` and the
LENS-FIX-RESIDUE row; neither seat here re-litigates them. T1 was told to honour the 09-06 T1 "checked and found
CORRECT" results and the collision/art half's scope.

---

## T1 — the OJZ bakers (generator correctness)

**Corpus, derived by the seat from the invocation chain** (an AST walk of local imports from each tool
`tools/regenerate-level.sh` runs, plus a `subprocess` grep; the walker is `deps_t1.py` in the fixtures directory):
`regenerate-level.sh` 245, `ojz_strip_gen.py` 2296, `ojz_common.py` 421, `tile_dedupe.py` 197, `ojz_block_gen.py` 840,
`ojz_entity_gen.py` 610, `inject_editor_bg.py` 1431, `verify_level_bin.py` 658 (all read in full); `s4lz.py` 924,
`effects_gen.py` 4910, `donor_provenance.py` 222, `suite_paths.py` 387, `level_staleness.py` 414 (partial, stated per
file in the seat's report).

**Headline: no convention mismatch between what the bakers write and what the engine reads, in today's shipped bytes.
Three SILENT failure paths, each demonstrated on a one-file fixture, where a bad editor input produces a green re-bake,
a green `verify_level_bin`, and wrong level data.** All three are latent: they need a malformed input that today's tree
does not hold.

Every fixture ran in a `cp -a` copy of the pinned tree; the only edit to a copy was `regenerate-level.sh`'s `cd` line so a
`.git`-less copy resolves its root. The scripts, as the seat ran them, are in
`2026-09-12-gap-lens-sweep-fixtures/` beside this file (`t1_fx_coll.sh` D1/D2, `t1_fx_tail.sh` C, `t1_fx_trunc.sh` A,
`t1_fx_blk.sh` B, `t1_build.sh`, `t1_measure.py`, `t1_cmp.py`).

**Citation check by the controller:** every line cited under F1, F2, F3, F4 (engine half) and F5 below was re-read at
`9fe9ee91` and says what the finding says. F6's `verify_local_maps` range and every measured count (1038/1042 cells,
12,164 words, 116 blank-priority words, 67/256 blocks) are the SEAT's measurements and were not re-run.

### F1 — HIGH, latent: a wrong-sized collision file silently deletes the act's floor
`tools/ojz_strip_gen.py`, `apply_editor_collision_overlay`: `if len(a) != expect:` prints a `WARNING … ignoring editor
collision for sec N` and `return grids`, i.e. the all-air baseline. Fixture D1 (`section_0.collattr.bin` cut by 2 bytes):
re-bake exit 0 with `interned 0/255`, `verify_level_bin: OK`, section 0 plane A 1038 → 0 non-air cells and plane B
1042 → 0, all five ROM collision tables changed. Section 0 is the only section with authored collision, so the act ships
with no solid ground. **Why every gate passes:** `verify_level_bin` has no collision-fidelity check, and an all-air table
still differs from `base/`, so `verify_collision_is_interned` is satisfied.
Proposed: refuse a wrong size instead of warning; add a collision-fidelity check to `verify_level_bin`.

### F2 — HIGH, latent: a missing section file ships a short local-map table and the engine reads a NULL map
`ojz_strip_gen.py`, `generate()`: a missing `section_N.tiles.bin` is `WARNING … not found, skipping` then `continue`.
`emit_section_local_maps` refuses only a NON-CONTIGUOUS id set (`missing = [i for i in range(n) …]` with
`n = max(by_id)+1`), so a missing LAST section passes. `ojz_block_gen.py` hardcodes `NUM_SECTIONS = 9` and re-bakes
section 8 from the previous bake's strips left on disk. Fixture C (delete `section_8.tiles.bin`): exit 0,
`sec_local_maps.emp` emitted as `[*u8; 8]`, `sec8_blocks.bin` rewritten from stale `sec8_strips_a.bin`,
`verify_level_bin: OK (8 section(s))`; control then fixture both linked under `FAST=1 DEBUG=1 ./build.sh`. In the ROM,
`OJZ_Sec_LocalMaps` entry 8 reads the first long of the next table (`OJZ_Palette`), `0x0` only because palette colour 0
is black. `TileCache_DecompressBlock` publishes that as section 8's map: the NULL-map hazard `tile_cache.emp`'s own comment
describes. **RUNTIME-TAG** for the in-game consequence.
Proposed: require every `section_N.tiles.bin` in editor mode; emit the table length as a constant pinned against
`GRID_W*GRID_H`; delete leftover per-section outputs.

### F3 — HIGH, latent: a short tileset bakes blank tiles, and the gate is blind by the same zero-fill (T1-2's shape)
`ojz_strip_gen.py`, `collect_referenced_tiles`: an index past the blob appends `bytes(TILE_SIZE)  # missing → zero tile`
(also `emit_bg_tile_blob`). `verify_level_bin._tile_pixels` returns `bytes(TILE_SIZE)` past the end, "matching what the
generator's collect_referenced_tiles substitutes", so the fidelity proof compares padding to padding.
`editor_data_available` rejects only a zero-byte tileset. Fixture A (tileset 919 → 700 tiles, editor references up to
732): exit 0, `editor bake fidelity OK (9 section(s), 589824 nametable words)`, 12,164 words (30 distinct tiles) baked
blank with no diagnostic. **This is the 09-06 T1-2 defect (`dedup_art.py`) recurring in a second generator**, the proof
reproducing the generator's fallback instead of checking against the source.
Proposed: refuse any index ≥ the tileset's tile count, in the generator and in the gate.

### F4 — MEDIUM, LIVE bytes, consequence needs the emulator: blank cells lose attribute bits the baker preserves
`engine/level/page_cache.emp`, `.pw_new_blank`: `clr.w (a1)` writes `$0000` for any word whose tile index is 0, while
`verify_level_bin` asserts `strips_a` keeps priority and palette bits. The seat counted 116 blank words carrying the
priority bit (20/19/10/15/10/11/14/7/10 across sections 0-8). Shadow/highlight is active in section 1 below line 120 and
in section 7's water band, where the plane priority of a cell decides shadowing. **The claim that a blank cell's priority
still affects shadowing is the seat's reading of the hardware, not a measurement.** **RUNTIME-TAG:** set priority on a
blank cell in section 1 below line 120 and compare pixels against the cleared case. If it matters, the fix is either the
engine keeping attributes on blank or the baker stripping them, and which is an authoring question.

### F5 — MEDIUM, loud: the preflight's "nothing is written before it can fail" does not hold for generate()'s refusals
`regenerate-level.sh` runs `ojz_strip_gen.py preflight`, then `import_sk_collision.py` (which overwrites the ROM-consumed
collision tables), and only then `generate()`, whose refusals all fire after that write. Fixture D2
(`section_0.collattrb.bin` cut by 2 bytes): the bad plane-B file is silently replaced by a mirror of plane A
(`# malformed path B → mirror A`); here it was refused only because section 0 has crossover marks that trip R2. The
re-bake exited 1 leaving the four tables byte-identical to raw `base/` and the stamp unrewritten, which the next build
catches loudly (`verify_collision_is_interned` + staleness). On a section without marks the mirror would be silent: a
code read, not a measurement.
Proposed: run `import_sk_collision` after `generate()` or restore on failure; refuse a bad `collattrb` instead of mirroring.

### F6 — LOW, latent (T2's lane): the gate checks intermediate files, not the ROM-consumed blocks
Nothing in the ROM embeds `strips_a`, and `verify_local_maps` checks only the dictionary region of `secN_blocks.bin`.
Fixture B (`sec5_blocks.bin` copied over `sec0_blocks.bin`, both 768-byte dictionaries): `verify_level_bin` exit 0 with
67 of 256 section-0 blocks decoding wrong; reachable only through a partial commit. **For the pin itself the seat closed
it:** decoding all 2,304 blocks gives 0 mismatches against `strips_a`.

### Minor (seat's, unverified here)
`inject_editor_bg.py` keeps a layout word of exactly 0 as VRAM tile 0 though BG slot 0 holds a band tile (no such words
today). The collision overlay samples only each 16-px cell's top tile row (0 cells differ today; whether Aurora can write
the two rows differently is a question for Aurora). The pool summary prints the retired `(ceiling 768)`.

### Checked and found CORRECT (re-derived by the seat)
Reproducibility: `--no-cache`, cold and warm re-bakes byte-identical to each other and to the committed tree across 203
files (bar `DONOR_PROVENANCE.json`'s aeon record, from the `.git`-less copy). Nametable word layout, flip
canonicalisation, the local map format, the block blob index and inner layout, S4LZ v3 tokens and end marker, the ZX0
page wrapper, `PageManifest`, entity/ring data bits and terminators, the injected BG layout, determinism (sorted
`listdir`, sets for membership only, no RNG), and a grid change failing loudly.

### Not covered by T1
`effects_gen.py` `render_module`/`generate`; engine-vs-Python decoder agreement (RUNTIME-TAG, `compression_selftest.emp`);
F2/F4 runtime consequences; fixture C in the canonical and release shapes; the STRESS path; the salvador C source;
generator source as a staleness input (declared by design in `level_staleness.py`).

### Triage (owner-gated per the protocol; nothing here is fixed)
- **Byte-neutral tool parcels** (refusals change no baked bytes on today's inputs): F1, F2, F3, F5, F6. They can land
  as their own parcels, each with a red-first proof on the seat's fixture. F3 should be fixed in the generator and the gate
  together, or the gate stays blind.
- **Measure-first:** F4, in the emulator, before choosing which side changes.
- **Open question for Aurora:** whether a collision cell's two tile rows can differ.

---

## A2 — the Z80 comment surface (comment TRUTH)

*Pending: the seat is still running. This section is filled when it returns, and the packet merges only with both halves.*
