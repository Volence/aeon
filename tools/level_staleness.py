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
effects_gen emit -> verify_level_bin. ojz_strip_gen alone reads essentially the whole
editor tree (`section_N.{tiles,coll,collattr,collattrb,meta,rings,objects}` for every
section, plus `ojz/chunks.json`, `objects.json`, the tileset blob named by project.json)
and rewrites essentially the whole generated tree in one pass. There is no stable
per-file pairing to derive: one editor byte can move every page in the pool, because the
pool is globally deduped across all sections. A hand-maintained pair list would be a
second source of truth that drifts away from the generator on the first schema change —
the exact failure class this tree keeps rediscovering. So the compare is whole-tree, and
it has TWO INDEPENDENT ARMS:

  ARM A — MTIME.  newest mtime(editor sources) > newest mtime(generated tree) => STALE
  ARM B — CONTENT STAMP.  sha256 of every editor source, compared against the manifest
                          the last re-bake wrote (see STAMP below)      => STALE

A DELETION IS WHY ARM B EXISTS, AND ARM A'S OLD CLAIM WAS FALSE. This docstring used to
say arm A "cannot miss a real edit". It can, and the miss is the single most expensive
thing in this file's history — the owner's "it kept giving errors ... and some seem like
they're just a repeat of things", reproduced by the Aurora cold walkthrough on
2026-09-02 (aurora docs/reviews/2026-09-02-effects-cold-walkthrough.md, finding b2):

    1. author an illegal value in the editor, save, build -> the build fails
    2. revert it the way a person reverts: `rm <that preset>.json`
    3. build again -> THE SAME ERROR, byte-identical, about a file that no longer exists
    4. again -> again, forever

mtime is monotonic per file. **Deleting a file lowers no mtime**, so after step 2 the
newest editor mtime is unchanged, arm A reads "fresh", the re-bake never runs, and the
STALE generated module — still carrying the value from the deleted document — is
assembled again. The only escape was `touch` on any editor file, and nothing said so.
That is not a caveat, it is a structural blindness: mtime can only ever see the set GROW
or a member get NEWER, never the set SHRINK.

Arm B closes it by construction. It compares the SET and the CONTENT of the editor
sources against a manifest written at bake time, so an added, removed, renamed or
modified file all move the answer, whatever their mtimes say. THE ESCAPE HATCH IS NOT
`touch` and cannot be: nothing about a file's timestamps is an input to arm B.

WHAT NEITHER ARM SEES (stated so the next reader does not have to rediscover it): a
change to something the generators read that is NOT in EDITOR SOURCES below — the two
out-of-repo donor projects (sonic_hack, skdisasm) and the generator source itself. Those
are re-bake inputs and this gate is blind to them by design; `tools/regenerate-level.sh`
stamps the donor SHAs into DONOR_PROVENANCE.json for the first, and nothing covers the
second. Do not read a green line here as "the generated tree is current".

Arm A is kept although arm B subsumes its content coverage, because the two fail
independently: arm A needs no cooperation from the generator at all, so it still fires
if the stamp mechanism itself is broken or was never run. A gate whose only arm depends
on the thing being gated is the vacuous shape this tree keeps rediscovering.

THE STAMP.  games/<game>/data/editor_sources.stamp.json — a COMMITTED artifact, written
by `tools/regenerate-level.sh` (via `python3 tools/level_staleness.py --stamp <game>`)
as its last step, and committed alongside the regenerated tree exactly like
DONOR_PROVENANCE.json. It records `{relative path: sha256}` for every editor source, by
the same walk and the same exclusions used below, so the two arms can never disagree
about what the editor source set IS.

It lives beside `editor/` rather than inside it (it would then be an input to itself) and
outside `generated/` (verify_level_bin.py's orphan sweep walks that tree and would report
a file nothing embeds). A MISSING stamp reads as STALE, not as "skip the check" — on a
fresh clone the committed stamp is present and matches, so the pristine-checkout case
stays quiet, and on a tree that has never been stamped the honest answer really is "this
was not baked from what is here now".

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

TIMESTAMP GRANULARITY (arm A only — arm B reads no timestamps).
mtimes are compared truncated to WHOLE SECONDS, strictly greater.
A fresh `git clone`/`git worktree add` writes every file within the same second or two in
arbitrary order, so a sub-second compare fires spuriously on a pristine checkout — the
one case that absolutely must stay quiet. The cost is that an editor save landing in the
same second as the end of a re-bake reads as fresh until the NEXT save. The incremental
re-bake (2026-08-19) shrank that blind window rather than widening it: the whole hole is
"saved while the bake was running", and the bake went from ~10 s to ~1 s, so the window
narrowed by an order of magnitude. Hitting what is left needs a save inside the same
whole second the bake finishes in — and the next save re-opens the gate. Arm B has no
equivalent window: it hashes what is on disk when it is asked.

USAGE
    python3 tools/level_staleness.py [game]           # default sonic4 — ask the question
    python3 tools/level_staleness.py --stamp [game]   # WRITE the stamp (the re-bake does this)
exit 0  fresh (or not applicable — no editor tree for this game); --stamp wrote the file
exit 2  STALE — the generated tree was not baked from the editor sources that are here now
exit 1  usage/internal error
"""

import hashlib
import json
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


def walk_files(paths):
    """Every non-excluded file under `paths`, as absolute paths, sorted.

    `paths` may mix files and directories; missing entries are skipped. BOTH arms
    call this, so they can never disagree about what the source set is — an
    exclusion added for one arm is automatically honoured by the other.
    """
    out = []
    for root in paths:
        if os.path.isfile(root):
            out.append(root)
        elif os.path.isdir(root):
            for dirpath, dirnames, filenames in os.walk(root):
                dirnames[:] = [d for d in dirnames if not _skip_dir(d)]
                out.extend(
                    os.path.join(dirpath, f) for f in filenames if not _skip_file(f)
                )
    return sorted(out)


def newest(paths):
    """(mtime_seconds, path) of the newest non-excluded file under `paths`.

    Returns (None, None) when nothing was found.
    """
    best_t, best_p = None, None
    for p in walk_files(paths):
        try:
            t = int(os.stat(p).st_mtime)
        except OSError:
            continue
        if best_t is None or t > best_t:
            best_t, best_p = t, p
    return best_t, best_p


# ---------------------------------------------------------------------------
# ARM B — the content stamp (see "A DELETION IS WHY ARM B EXISTS" above)
# ---------------------------------------------------------------------------
# Schema is versioned so a future change to the walk, the exclusions or the digest
# reads as "re-bake to re-stamp" rather than as a silent mis-compare against a
# manifest built by different rules.
STAMP_SCHEMA = 1
STAMP_BASENAME = "editor_sources.stamp.json"
_DIFF_NAMES_SHOWN = 8


def stamp_path(game: str, repo: str = REPO) -> str:
    """Beside `editor/`, NOT inside it (it would be an input to itself) and NOT under
    `generated/` (verify_level_bin.py's orphan sweep walks that tree)."""
    return os.path.join(repo, "games", game, "data", STAMP_BASENAME)


def editor_fingerprint(game: str, repo: str = REPO) -> dict:
    """{repo-relative path: sha256 hex} over every editor source, right now.

    The whole set, hashed by content. This is the arm that sees a DELETION: a file
    that is gone is a key that is gone, which no timestamp can express.
    """
    out = {}
    for p in walk_files(editor_sources(game, repo)):
        d = hashlib.sha256()
        try:
            with open(p, "rb") as f:
                for chunk in iter(lambda: f.read(1 << 20), b""):
                    d.update(chunk)
        except OSError:
            # Unreadable is not "unchanged": record it distinguishably so it cannot
            # silently compare equal to a real hash.
            out[os.path.relpath(p, repo).replace(os.sep, "/")] = "unreadable"
            continue
        out[os.path.relpath(p, repo).replace(os.sep, "/")] = d.hexdigest()
    return out


def read_stamp(game: str, repo: str = REPO):
    """The recorded fingerprint, or None if there is no usable stamp."""
    path = stamp_path(game, repo)
    try:
        with open(path, "r", encoding="utf-8") as f:
            doc = json.load(f)
    except (OSError, ValueError):
        return None
    if not isinstance(doc, dict) or doc.get("schema") != STAMP_SCHEMA:
        return None
    files = doc.get("files")
    return files if isinstance(files, dict) else None


def write_stamp(game: str, repo: str = REPO) -> str:
    """Record the editor sources as they are NOW. Called by the re-bake, last."""
    path = stamp_path(game, repo)
    files = editor_fingerprint(game, repo)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(
            {
                "schema": STAMP_SCHEMA,
                "game": game,
                "written_by": "tools/level_staleness.py --stamp"
                              " (run by tools/regenerate-level.sh)",
                "note": "The editor sources the committed generated tree was baked "
                        "from. Commit it WITH that tree. A mismatch here is the "
                        "staleness gate's deletion-visible arm — see the module "
                        "docstring.",
                "count": len(files),
                "files": files,
            },
            f,
            indent=1,
            sort_keys=True,
        )
        f.write("\n")
    os.replace(tmp, path)
    return path


def stamp_diff(current: dict, stamped: dict):
    """(added, removed, changed) — sorted repo-relative paths."""
    cur, old = set(current), set(stamped)
    added = sorted(cur - old)
    removed = sorted(old - cur)
    changed = sorted(p for p in cur & old if current[p] != stamped[p])
    return added, removed, changed


def _diff_lines(added, removed, changed):
    lines = []
    for label, names in (("removed", removed), ("added", added), ("changed", changed)):
        if not names:
            continue
        shown = ", ".join(names[:_DIFF_NAMES_SHOWN])
        more = f" (+{len(names) - _DIFF_NAMES_SHOWN} more)" \
            if len(names) > _DIFF_NAMES_SHOWN else ""
        lines.append(f"    {label} since the bake ({len(names)}): {shown}{more}")
    return lines


def editor_sources(game: str, repo: str = REPO):
    return [
        os.path.join(repo, "games", game, "data", "editor"),
        os.path.join(repo, "games", game, "data", "editor_bg_override.json"),
        os.path.join(repo, "project.json"),
    ]


def generated_outputs(game: str, repo: str = REPO):
    return [os.path.join(repo, "games", game, "data", "generated")]


def mtime_arm(game: str, repo: str = REPO):
    """ARM A -> (stale, message). Sees files that got NEWER; structurally blind to a
    file that went AWAY, because a deletion lowers no mtime. Kept separate from arm B
    so a test can demonstrate exactly that blindness rather than assert it in prose."""
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
            f"level staleness: STALE (mtime) — editor source is newer than the "
            f"generated tree.\n"
            f"    newest editor source : {os.path.relpath(e_p, repo)}  ({_fmt(e_t)})\n"
            f"    newest generated file: {os.path.relpath(g_p, repo)}  ({_fmt(g_t)})"
        )
    return False, (
        f"level staleness: mtime ok (generated {_fmt(g_t)} >= editor {_fmt(e_t)})"
    )


def stamp_arm(game: str, repo: str = REPO):
    """ARM B -> (stale, message). Sees the editor source SET and its CONTENT, so an
    added, removed, renamed or modified file all move the answer. No timestamp is an
    input, which is why `touch` is not — and cannot become — the escape hatch."""
    rel_stamp = os.path.relpath(stamp_path(game, repo), repo)
    stamped = read_stamp(game, repo)
    if stamped is None:
        return True, (
            f"level staleness: STALE (stamp) — {rel_stamp} is missing or unreadable, so "
            f"nothing records which editor sources the committed generated tree was "
            f"baked from. A missing stamp is NOT 'skip the check': the honest answer is "
            f"that this tree was not demonstrably baked from what is here now."
        )
    current = editor_fingerprint(game, repo)
    added, removed, changed = stamp_diff(current, stamped)
    if added or removed or changed:
        return True, "\n".join(
            [
                f"level staleness: STALE (stamp) — the editor sources are not the ones "
                f"the last re-bake read ({rel_stamp}).",
            ]
            + _diff_lines(added, removed, changed)
            + [
                "    NOTE: a REMOVED file is invisible to a timestamp compare — "
                "deleting a file lowers no mtime — so `touch` is not the fix and never "
                "was. Re-bake.",
            ]
        )
    return False, f"level staleness: stamp ok ({len(current)} editor source(s) match)"


def check(game: str, repo: str = REPO):
    """-> (stale: bool, message: str). Not stale when there is no editor tree.

    STALE if EITHER arm says so. Both messages are always shown on a failure: which
    arm fired is the difference between "you saved" and "you deleted something", and
    those have different remedies in the reader's head even though the tool's remedy
    is the same.
    """
    editor_root = os.path.join(repo, "games", game, "data", "editor")
    if not os.path.isdir(editor_root):
        return False, f"level staleness: n/a ({game} has no data/editor tree)"
    if not walk_files(editor_sources(game, repo)):
        return False, f"level staleness: n/a ({game} editor tree has no files)"

    a_stale, a_msg = mtime_arm(game, repo)
    b_stale, b_msg = stamp_arm(game, repo)

    if a_stale or b_stale:
        return True, f"{a_msg}\n{b_msg}"
    return False, f"{a_msg}\n{b_msg}"


def _fmt(t: int) -> str:
    import datetime

    return datetime.datetime.fromtimestamp(t).strftime("%Y-%m-%d %H:%M:%S")


def main(argv):
    args = [a for a in argv[1:] if a != "--stamp"]
    game = args[0] if args else "sonic4"
    if "--stamp" in argv:
        editor_root = os.path.join(REPO, "games", game, "data", "editor")
        if not os.path.isdir(editor_root):
            print(f"level staleness: --stamp n/a ({game} has no data/editor tree)")
            return EXIT_FRESH
        path = write_stamp(game)
        n = len(read_stamp(game) or {})
        print(f"level staleness: stamped {n} editor source(s) -> "
              f"{os.path.relpath(path, REPO)}")
        print("  COMMIT IT WITH THE REGENERATED TREE — it is the record of which "
              "editor bytes these outputs were baked from.")
        return EXIT_FRESH
    stale, msg = check(game)
    print(msg)
    return EXIT_STALE if stale else EXIT_FRESH


if __name__ == "__main__":
    sys.exit(main(sys.argv))
