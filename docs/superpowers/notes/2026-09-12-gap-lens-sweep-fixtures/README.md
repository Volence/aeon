# T1 seat fixtures, 2026-09-12 gap lens sweep — a RECORD of what ran, not a runnable suite

These are the scripts the T1 seat (OJZ bakers) ran to demonstrate findings F1-F6 in
`../2026-09-12-aeon-gap-lens-sweep.md`, committed as they were, so the evidence outlives the session.

**Do not run them as they stand.** Every script hard-codes that session's scratch directory:
`t1_setup.sh` copies a worktree that no longer exists, and the others read their working directory `S`
from a `t1_S_path` file that exists only in that session. If that file is missing, `S` is empty, and
lines such as `rm -rf "$F"` with `F="$S/fx_..."` would target a path off the filesystem root.

To reproduce a finding: make a fresh `S=$(mktemp -d)`, then `cp -a` a clean checkout of `9fe9ee91` into
`$S/pristine` and delete its `.git` pointer. Replace each script's `S=$(cat …)` line with your `S`, and
patch the copy's `regenerate-level.sh` repo-root `cd` the way `t1_setup.sh`'s header describes. Every
mutation happens inside `$S`; nothing here touches a real tree.

| script | finding |
|---|---|
| `t1_fx_coll.sh` | F1 (D1: short `collattr.bin`), F5 (D2: short `collattrb.bin`) |
| `t1_fx_tail.sh` | F2 (missing `section_8.tiles.bin`) |
| `t1_fx_trunc.sh` | F3 (tileset truncated 919 → 700 tiles) |
| `t1_fx_blk.sh` | F6 (`sec5_blocks.bin` over `sec0_blocks.bin`) |
| `t1_build.sh` | F2's control-then-fixture link under `FAST=1 DEBUG=1 ./build.sh` |
| `t1_measure.py`, `t1_cmp.py`, `t1_run.sh` | the measurement and comparison helpers |
| `deps_t1.py` | the AST import walker that derived the corpus |
