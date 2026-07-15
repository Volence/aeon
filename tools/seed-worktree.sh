#!/usr/bin/env bash
#
# seed-worktree.sh — populate a fresh aeon git worktree with the git-IGNORED
# generated artifacts a build/test run needs but `git worktree add` does NOT
# check out, then build the reference ROMs.
#
# WHY: the editor's per-section working data, the generated OJZ level data
# (entity_data.asm etc.), the collision/sprite binaries, and engine/debug's
# generated blobs are all gitignored. A fresh worktree lacks them, so build.sh
# fails ("cannot include .../entity_data.asm") or — worse, historically —
# silently falls back to air-baseline collision and builds a ROM that diverges
# ~130KB with no error. This script copies the whole gitignored artifact set
# from a known-good tree (default: this repo's main worktree) and builds the
# ROMs, so the fresh worktree is byte-for-byte buildable/testable.
#
# USAGE:
#   tools/seed-worktree.sh <worktree-path> [<source-tree>]
#     <worktree-path>  the fresh worktree to seed
#     <source-tree>    tree to copy gitignored artifacts from
#                      (default: the main worktree containing this script)
#
# Run ONCE, right after `git worktree add <worktree-path> <branch>`.
#
set -euo pipefail

WT="${1:?usage: tools/seed-worktree.sh <worktree-path> [<source-tree>]}"
SRC_DEFAULT="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel)"
SRC="${2:-$SRC_DEFAULT}"
WT="$(cd "$WT" && pwd)"
SRC="$(cd "$SRC" && pwd)"

if [ "$WT" = "$SRC" ]; then
  echo "error: worktree and source tree are the same ($WT)" >&2
  exit 1
fi
if [ ! -x "$WT/build.sh" ]; then
  echo "error: $WT does not look like an aeon worktree (no build.sh)" >&2
  exit 1
fi

echo "seeding worktree: $WT"
echo "  from source:    $SRC"

# Copy every gitignored file from SRC (the generated artifact set), preserving
# paths. This is the whole set — editor data, generated OJZ, collision/sprite
# binaries, engine/debug blobs, and any stray ROMs (rebuilt below). Using the
# ignore list means the script stays correct as new generated artifacts appear.
count=0
while IFS= read -r -d '' f; do
  # Skip sibling git worktrees (`.worktrees/` is itself ignored and lists as a
  # directory entry) and anything that isn't a plain file to copy.
  case "$f" in .worktrees/*) continue ;; esac
  [ -f "$SRC/$f" ] || continue
  mkdir -p "$WT/$(dirname "$f")"
  cp -p "$SRC/$f" "$WT/$f"
  count=$((count + 1))
done < <(git -C "$SRC" ls-files --others --ignored --exclude-standard -z)
echo "  copied $count gitignored artifact(s)"

# Build the reference ROMs. DEBUG first → s4.debug.* (build.sh writes s4.bin
# regardless of DEBUG — the repin trap), then the plain build last.
echo "building reference ROMs (DEBUG then plain)..."
cd "$WT"
DEBUG=1 ./build.sh
cp -f s4.bin s4.debug.bin
cp -f s4.lst s4.debug.lst
./build.sh

echo "done: $WT is seeded and built (s4.bin + s4.debug.bin present)."
