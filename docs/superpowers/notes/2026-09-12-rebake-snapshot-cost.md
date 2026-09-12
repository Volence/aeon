# 2026-09-12 — what F5's re-bake snapshot costs the FAST loop

Question: fix F5 (`8802e581`) made `tools/regenerate-level.sh` copy
`games/sonic4/data/collision` and `games/sonic4/data/generated` into a `mktemp -d` on EVERY
re-bake, so a failed bake can restore what it wrote. `FAST=1 DEBUG=1 ./build.sh` runs that
script whenever `tools/level_staleness.py` says the editor tree is stale, i.e. after every
editor save. Nobody had measured what the copy costs.

Verdict: **measured and harmless, no code change.** The snapshot-and-cleanup step costs
~4.3 ms (0.08% of a ~5.5 s FAST edit build on this box, and far under the 50 ms bar), and
in both whole-pipeline series it is well below the run-to-run noise.

## The mechanism, read from source (tree `f512e228`)

- The snapshot is unconditional: it runs after `ojz_strip_gen.py preflight` and before
  `import_sk_collision.py`, on every invocation, cached no-op included. On success the
  EXIT trap only `rm -rf`s the snapshot; on failure it `rm -rf`s each output dir and
  `cp -a`s the snapshot back.
- FAST calls the script only on a STALE verdict (build.sh's `FAST_REBAKE_BLOCK`). A FAST
  build on a fresh tree never reaches the snapshot at all.
- Copied: `data/collision` 11 files, 34,527 B; `data/generated` 77 files in 5 dirs,
  3,749,886 B (apparent size; 68 K + 3,868 K on disk). Source ext4, destination `/tmp`
  = tmpfs (`TMPDIR` unset), so it is a real copy, not a reflink.

## Arms

- **before** = `4afb4ad7` (`8802e581^`; `git show 4afb4ad7:tools/regenerate-level.sh | grep -c REBAKE_SNAP` = 0).
- **after** = `f512e228` (origin/master at dispatch).
- **nosnap** = `f512e228` with ONLY the snapshot block and trap deleted (a scratch worktree,
  never committed). This is the attribution control. `before` and `after` also differ by
  F5's `validate_editor_inputs` preflight and F6's full block decode in
  `verify_level_bin` (0.095 s by its own commit message), so before-vs-after alone would
  charge those to the snapshot.
- The editor, generated and collision trees are identical at `4afb4ad7` and `f512e228`
  (`git diff --stat` empty), and `section_0.tiles.bin` has the same md5 (`59cfc7c4...`) in all three.
- Each worktree got one discarded warm-up re-bake (a cold cache) and one discarded
  warm-up round per series. 16 cores, other lanes building throughout.

## (a) the snapshot-and-cleanup step alone, n=20 interleaved pairs

The exact commands the script runs on a successful bake (mktemp, `mkdir -p` + `cp -a` per
output dir, then `rm -rf`), timed with `date +%s%N` in one bash process, against an empty
block (BEFORE: the step does not exist, which leaves only the harness).
2026-09-12T18:07:19Z, `load average: 9.16, 10.17, 6.71` at both start and end.

| arm | median | min-max | raw (µs) |
|---|---|---|---|
| empty (harness) | 0.31 ms | 0.27-0.45 | 365 449 293 366 316 350 345 278 402 342 335 390 291 303 306 272 275 310 307 306 |
| snapshot step | 4.31 ms | 4.09-10.48 | 10475 4734 4303 4158 4426 4085 4330 4277 4262 4412 4173 4473 4307 4270 4457 4281 4242 4721 4203 5398 |

## (b) `tools/regenerate-level.sh`, nothing to do (cached no-op), n=7 rounds

Rounds ran the three arms in order (before, after, nosnap).
Start 2026-09-12T18:08:33Z `load average: 10.64, 10.23, 6.99`; end 18:09:17Z `14.75, 11.38, 7.54`. All rc=0.

| arm | median | min-max | raw (ms) |
|---|---|---|---|
| before | 1679 | 1550-2848 | 1596 2848 1692 1592 1679 1742 1550 |
| after | 1730 | 1659-2047 | 1659 1837 1785 1730 2047 1676 1712 |
| nosnap | 1884 | 1696-2452 | 2452 1884 1778 1893 2032 1696 1799 |

after minus nosnap = -154 ms: the arm WITH the snapshot is faster, so noise is
everything here and the ~4 ms step is invisible. after minus before = +51 ms, which the
nosnap control (also above before) puts on the F5/F6 preflight and gate work, not on the copy.

## (c) `FAST=1 DEBUG=1 ./build.sh` after a real one-cell editor edit, n=6 rounds

Each round, before each arm's build, the harness wrote the pristine `section_0.tiles.bin`
with one cell (row 100, col 40) set to a DIFFERENT
existing nametable word (k=2..7: `$1800 $4000 $4006 $4007 $4008 $4009`). Every edit was
therefore new to every cache (a real incremental recompress), and each arm got the same
edit. Every run: rc=0, the staleness gate fired (4 STALE lines), `FAST: re-bake done in 1-4s`.
Start 2026-09-12T18:09:30Z `load average: 13.99, 11.38, 7.60`; end 18:11:28Z `13.61, 12.28, 8.39`.

| arm | median | min-max | raw (ms) |
|---|---|---|---|
| before | 5414 | 5054-6247 | 5622 5054 6247 5350 5262 5477 |
| after | 5526 | 5156-7271 | 7271 5271 6499 5506 5156 5546 |
| nosnap | 5576 | 5181-6660 | 5651 5181 6660 5669 5500 5284 |

after minus nosnap = -50 ms (again the snapshot arm is the faster one; noise spans
~1-2 s per arm). after minus before = +112 ms (+2.1%), and nosnap minus before = +162 ms,
so that gap is not the snapshot either.

## What this does NOT say

- The whole-loop numbers are under load 10-15 with other lanes building. Treat them as
  a comparison between arms, not as the loop's speed (the repo's "~1.3 s" FAST and "~0.8 s"
  no-op re-bake figures were taken on a quieter box and are not re-measured here). The
  snapshot's cost rests on (a), a direct measurement of the step. (b) and (c) only show it
  is lost in the noise.
- The step scales with the size of `data/generated` (3.75 MB today). It runs per re-bake,
  not per section, so a larger act grows it linearly: at the measured ~1.1 ms/MB, even a
  tree ten times larger stays under the 50 ms bar.
- The failure path (restore = `rm -rf` + `cp -a` back) was not timed. It runs only on a
  refused bake, where correctness is the point.

## Why no cheaper form was needed (candidates weighed anyway)

- `cp -al` (hard links) would be UNSAFE here as well as unnecessary. Some writers do
  write in place (they truncate the existing inode): `ojz_strip_gen.py` opens its outputs
  directly with `open(out_path, "wb")` (4 sites), `ojz_block_gen.py` does the same for its
  output blobs, and `regenerate-level.sh` itself writes `} > "$POOL_EMP"`. Only the block
  cache, the editor stamp and `effects_gen.py` go through `os.replace`. An in-place write
  would reach the snapshot through the link, and the "restore" would then put the damage back.
- Snapshotting only the files the bake is about to write needs a write-set the script
  does not have, and it is exactly the kind of list that goes stale.
- Skipping the snapshot on a cached no-op would save ~4 ms on a path that FAST never
  takes (FAST re-bakes only when stale, and a stale tree is never a no-op).
