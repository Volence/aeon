#!/usr/bin/env python3
"""Staleness gate: is the COMMITTED generated level tree older than its editor sources?

WHY THIS EXISTS. `games/<game>/prebuild.sh` is a documented no-op and the generated
level tree is a COMMITTED artifact, because its generators read two out-of-repo donor
projects a fresh checkout does not have. That is the right call for reproducibility and
it opens a silent trap: you save in the editor, run `./build.sh`, load the ROM, and get
the PREVIOUS level data with no warning anywhere. The only note about it lived in
`tools/regenerate-level.sh`'s docstring, which is not where anyone reading a green build
is looking. An Aurora editing session lost an hour to exactly this on 2026-08-19.

So: the build asks the question now, every time.

  canonical build -> STALE is a HARD FAILURE naming tools/regenerate-level.sh
  FAST=1 build    -> STALE auto-runs the re-bake (that is the edit/look/edit loop's
                     whole point) and reports how long it took

WHAT IS COMPARED (and why it is a tree compare, not a file-pair map). The re-bake is
`tools/regenerate-level.sh`: preflight -> import_sk_collision -> ojz_strip_gen generate
-> inject_editor_bg -> per-page ZX0/raw election -> ojz_block_gen generate ->
verify_level_bin. ojz_strip_gen alone reads essentially the whole editor tree
(`section_N.{tiles,coll,collattr,collattrb,meta,rings,objects}` for every section, plus
`ojz/chunks.json`, `objects.json`, the tileset blob named by project.json) and rewrites
essentially the whole generated tree in one pass. There is no stable per-file pairing to
derive: one editor byte can move every page in the pool, because the pool is globally
deduped across all sections. A hand-maintained pair list would be a second source of
truth that drifts away from the generator on the first schema change — the exact failure
class this tree keeps rediscovering. So the compare is CONSERVATIVE and whole-tree:

    newest mtime(editor sources)  >  newest mtime(generated tree)   ==>  STALE

Conservative in the safe direction: it can ask for a re-bake that would have been a
no-op (a touched-but-unchanged editor file), it cannot miss a real edit.

EDITOR SOURCES (the "newer" side):
  games/<game>/data/editor/**            the editor's own tree
  games/<game>/data/editor_bg_override.json   read by tools/inject_editor_bg.py
  project.json                           read by ojz_strip_gen._project_tileset_path
                                         (zones[0].tileset); the editor rewrites this
                                         file wholesale on save, so it is a real input

GENERATED TREE (the "older" side):
  games/<game>/data/generated/**         every re-bake rewrites this whole tree

data/collision/ is written by the re-bake too, but it is NOT on either side: its content
comes from the skdisasm donor plus the per-section bake, not from editor edits, and
including it would only add noise. The generated tree moves on every re-bake, so it is a
sufficient and simpler witness of "when was the last bake".

EXCLUSIONS (enumerated on purpose — an unexplained exclusion is a hole):
  any directory whose name starts with "."   the editor's and the repo's manual backup
                                             snapshots of PREVIOUS editor state:
                                             .pre-sk-import-backup, .empty-collattr-backup,
                                             .reset-backup-2026-06-20,
                                             .pre-wysiwyg-backup-2026-06-20. They are
                                             copies of inputs, read by no generator, and
                                             restoring one would otherwise read as an edit.
  any file whose name starts with "."        dotfiles/editor scratch (.DS_Store, swap
                                             files); no generator reads one.
  the directory named "export"               the editor's export dump
                                             (data/editor/ojz/act1/export/) — an editor
                                             OUTPUT, not a generator input.
  files ending "~" or ".tmp"                 save-in-progress scratch from atomic writes.

TIMESTAMP GRANULARITY. mtimes are compared truncated to WHOLE SECONDS, strictly greater.
A fresh `git clone`/`git worktree add` writes every file within the same second or two in
arbitrary order, so a sub-second compare fires spuriously on a pristine checkout — the
one case that absolutely must stay quiet. The cost is that an editor save landing in the
same second as the end of a re-bake reads as fresh until the NEXT save. The incremental
re-bake (2026-08-19) shrank that blind window rather than widening it: the whole hole is
"saved while the bake was running", and the bake went from ~10 s to ~1 s, so the window
narrowed by an order of magnitude. Hitting what is left needs a save inside the same
whole second the bake finishes in — and the next save re-opens the gate.

USAGE
    python3 tools/level_staleness.py [game]        # default sonic4
exit 0  fresh (or not applicable — no editor tree for this game)
exit 2  STALE — the generated tree is older than an editor source
exit 1  usage/internal error
"""

import os
import sys

EXIT_FRESH = 0
EXIT_ERROR = 1
EXIT_STALE = 2

SKIP_DIR_NAMES = {"export"}
SKIP_FILE_SUFFIXES = ("~", ".tmp")

REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


def _skip_dir(name: str) -> bool:
    return name.startswith(".") or name in SKIP_DIR_NAMES


def _skip_file(name: str) -> bool:
    return name.startswith(".") or name.endswith(SKIP_FILE_SUFFIXES)


def newest(paths):
    """(mtime_seconds, path) of the newest non-excluded file under `paths`.

    `paths` may mix files and directories; missing entries are skipped. Returns
    (None, None) when nothing was found.
    """
    best_t, best_p = None, None
    for root in paths:
        if os.path.isfile(root):
            candidates = [root]
        elif os.path.isdir(root):
            candidates = []
            for dirpath, dirnames, filenames in os.walk(root):
                dirnames[:] = [d for d in dirnames if not _skip_dir(d)]
                candidates.extend(
                    os.path.join(dirpath, f) for f in filenames if not _skip_file(f)
                )
        else:
            continue
        for p in candidates:
            try:
                t = int(os.stat(p).st_mtime)
            except OSError:
                continue
            if best_t is None or t > best_t:
                best_t, best_p = t, p
    return best_t, best_p


def editor_sources(game: str, repo: str = REPO):
    return [
        os.path.join(repo, "games", game, "data", "editor"),
        os.path.join(repo, "games", game, "data", "editor_bg_override.json"),
        os.path.join(repo, "project.json"),
    ]


def generated_outputs(game: str, repo: str = REPO):
    return [os.path.join(repo, "games", game, "data", "generated")]


def check(game: str, repo: str = REPO):
    """-> (stale: bool, message: str). Not stale when there is no editor tree."""
    editor_root = os.path.join(repo, "games", game, "data", "editor")
    if not os.path.isdir(editor_root):
        return False, f"level staleness: n/a ({game} has no data/editor tree)"

    e_t, e_p = newest(editor_sources(game, repo))
    g_t, g_p = newest(generated_outputs(game, repo))

    if e_t is None:
        return False, f"level staleness: n/a ({game} editor tree has no files)"
    if g_t is None:
        return True, (
            f"level staleness: STALE — {game} has editor sources but NO generated tree "
            f"(games/{game}/data/generated/ is empty or missing)."
        )
    if e_t > g_t:
        return True, (
            f"level staleness: STALE — editor source is newer than the generated tree.\n"
            f"    newest editor source : {os.path.relpath(e_p, repo)}  ({_fmt(e_t)})\n"
            f"    newest generated file: {os.path.relpath(g_p, repo)}  ({_fmt(g_t)})"
        )
    return False, (
        f"level staleness: ok (generated {_fmt(g_t)} >= editor {_fmt(e_t)})"
    )


def _fmt(t: int) -> str:
    import datetime

    return datetime.datetime.fromtimestamp(t).strftime("%Y-%m-%d %H:%M:%S")


def main(argv):
    game = argv[1] if len(argv) > 1 else "sonic4"
    stale, msg = check(game)
    print(msg)
    return EXIT_STALE if stale else EXIT_FRESH


if __name__ == "__main__":
    sys.exit(main(sys.argv))
