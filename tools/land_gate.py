#!/usr/bin/env python3
"""land_gate: the landing gate (CTRL-3). Code reaches master only if a completed
`tools/landing_build.sh` run proved that exact content green.

WHY THIS EXISTS. The landing check was a habit: `tools/landing_build.sh` builds and
grades the shapes in its LANDING_SHAPES list (three since CTRL-3b, 2026-09-14: the hub's
A plus D; a stamp therefore means "the TRIMMED check finished 0 over this code"), and
nothing stopped a push to master that skipped
it. Its own closure row (LS-1c) said so: "a ritual like the effects gate, not a hook
-- nothing in this tree mechanically blocks a merge". The owner chose `gate` on
2026-09-13T22:06:54Z (docs/decisions.jsonl, CTRL-3), bounded by "as long as it doesn't
hamper too much". This file is that gate. It has three halves:

  1. `landing_build.sh` calls `begin` before it builds and `finish` after. `finish`
     writes a STAMP for the content it proved, and only when the run completed
     (finished=0), HEAD did not move, and no code path was dirty at either end.
  2. `tools/hooks/pre-push` (installed by hand, see that file) calls `pre-push` for
     any push to refs/heads/master. It refuses unless the pushed code carries a stamp
     or is identical to the code the remote's master already has, and it runs the
     tests that read any docs file the push changes. Every other ref is untouched.
  3. The classifier below decides which paths are code. It is guarded on every build
     by tools/land_gate_audit.py (a pytest plugin that watches which docs files the
     tests actually open) and tools/test_land_gate_classifier.py (a static scan).

THE STAMP IS KEYED BY CONTENT. The key is a sha256 over the (mode, object, path) of
every CODE-class path in a commit's tree. Not a timestamp, not a branch name, not a
log's mtime: two commits with the same code have the same key wherever they sit, and
a commit that changes one code byte has a different one. So the ledger commit the
landing lane writes after a verified merge (docs/lens-findings.jsonl,
docs/lane-log.jsonl) keeps the key and needs no rebuild. This file is itself a CODE
path, so changing the classifier changes every key and old stamps stop matching:
the safe direction.

THREE CLASSES OF PATH (see `classify`):

  code     anything outside docs/, and any docs/ path the BUILD reads (build.sh, its
           generators and gates, a needs_build test). A push changing one needs a stamp.
  checked  a docs/ path read only by SOURCE-ONLY tests (build.sh's pre-build pytest
           lane, which needs no ROM). A push changing one runs the tests its rules name,
           in a temporary checkout of the pushed commit: seconds, not the build. That is
           oracle's rule for its own fast path ("it must VALIDATE, not merely skip"),
           generalised from three lane files to every file a test reads.
  docs     a docs/ path no rule names: read by nothing that runs in a build. A push
           that changes only these runs nothing. (Today there are none; see RULES.)

Nothing outside docs/ is ever anything but code.

Usage:
  land_gate.py key [REV]                 content key of REV (default HEAD)
  land_gate.py classify PATH...          code | checked | docs, one per line
  land_gate.py begin                     for landing_build.sh (prints LAND_GATE_START ...)
  land_gate.py finish --head H --key K --clean C --rc RC [--sigil PATH]
                                         for landing_build.sh: write the stamp or say why not
  land_gate.py pre-push REMOTE URL       the hook body (reads git's pre-push stdin)
  land_gate.py stamps                    list the stamps on this machine

Stamps live in "$(git rev-parse --git-common-dir)/aeon-land-gate/", shared by every
worktree of the repository and by no commit. AEON_LAND_GATE_DIR overrides it (tests).
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import time

TOOLS = os.path.dirname(os.path.abspath(__file__))
AEON = os.path.dirname(TOOLS)

CODE, CHECKED, DOCS = "code", "checked", "docs"
MASTER = "refs/heads/master"
ZERO = "0" * 40
KEY_VERSION = "aeon-land-key-v1"

# ------------------------------------------------------------------------------------
# THE RULES. Rules ACCUMULATE: a docs/ path takes every rule that matches it (a key
# ending in "/" matches everything under it). Its class is CODE if any match is CODE,
# else CHECKED if any is, else DOCS; a CHECKED path's readers are the union over its
# matches. A path outside docs/ never reaches this table.
#
# Each rule is (path-or-prefix, class, readers, why). Readers are the test FILES a push
# runs when a CHECKED path changes. They must be source-only: they run in a fresh
# checkout of the pushed commit, with `-m "not needs_build"`, and no ROM.
#
# DERIVED 2026-09-13, NOT GUESSED (docs/superpowers/notes/2026-09-13-ctrl3-land-gate.md):
#   * an inotify trace of this repository's docs/ tree across a full
#     tools/landing_build.sh run (every process: build.sh, sigil, gates, both lanes);
#   * tools/land_gate_audit.py's record mode over both pytest lanes, which attributes
#     each open()/listdir() to the test file that made it;
#   * the static scan in tools/test_land_gate_classifier.py.
# The brief this was built from assumed only docs/OVERSEER.md was read. The trace said
# otherwise: 830 of the 832 tracked docs files were opened, 4 times each per landing.
# ------------------------------------------------------------------------------------
# >>> RULES (tools/test_land_gate.py replaces this block in its scratch copy)
RULES: tuple = (
    ("*.emp", CODE, (),
     "sigil's module walk (crates/sigil-frontend-emp/src/resolve/manifest.rs, collect_emp; "
     "reproduced by tools/artifact_provenance.py scan_members) takes EVERY *.emp under the "
     "root into the build, docs/ included. None exist there today (0 on 2026-09-13), and "
     "the three listings' Source Digests name no docs/ file, so this is the build's only "
     "way into docs/"),
    ("docs/", CHECKED, ("tools/test_citation_form.py",),
     "test_citation_form's anchor row opens EVERY tracked docs file looking for a "
     "CITATIONS-ANCHORED-AT declaration (830 of 832 on 2026-09-13; the other two have "
     "non-ASCII names) and its live row opens the LIVE ones"),
    ("docs/decisions.jsonl", CHECKED, ("tools/test_decisions_ledger.py",),
     "the owner's decision ledger: every line after the ruled set must parse"),
    ("docs/lane-log.jsonl", CHECKED, ("tools/test_lane_log_shape.py",),
     "the lane log's line shape and `at` rule"),
    ("docs/OVERSEER.md", CHECKED, ("tools/test_overseer_bound.py",),
     "the boot file's ruled read bound"),
    ("docs/ENGINE_ARCHITECTURE.md", CHECKED, ("tools/test_object_mailbox_contract.py",),
     "the object mailbox op codes must match the doc"),
    ("docs/EDITOR_RASTER_PRESETS.md", CHECKED, ("tools/test_effects_gen.py",),
     "TestEditorRasterPresetsDoc: the preset block covers every row"),
    ("docs/EFFECTS_LAB.md", CHECKED, ("tools/test_lab_index_lint.py",),
     "the effects lab page lists the same words as the lab index"),
    ("docs/ART_PIPELINE_CONTRACT.md", CHECKED, ("tools/test_art_pipeline_contract.py",),
     "the hand-copied VRAM table and the budget constants it restates must equal the "
     "generated vram_map mirror; it went stale on BG_TILE_CAPACITY in the same week "
     "EFFECTS_CONSUMER_CONTRACT.md did, from the same carve, ungated"),
    ("docs/generated/", CHECKED, ("tools/test_gen_vram_map.py", "tools/test_fg_working_set.py"),
     "the generated VRAM maps must equal their generator's output and agree with the "
     "pool ceiling; a prefix because the generator writes one file per game"),
)
# <<< RULES

# Tests that LIST docs directories but keep only one kind of file from the listing. A
# listing is a read of a directory's membership, so a lister is covered only if every
# docs file of the kind it keeps is CODE (tools/land_gate_audit.py checks exactly that).
# Each entry was read at its source, 2026-09-13: (suffix kept, where the filter is).
LISTERS = {
    "tools/test_emp_helper_closure.py":
        (".emp", "emp_helper_closure.py's module index: os.walk(aeon), `if not fn.endswith('.emp')`"),
    "tools/test_artifact_provenance.py":
        (".emp", "artifact_provenance.scan_members: sigil's *.emp module walk, reproduced"),
    "tools/test_bg_emit.py":
        (".emp", "bganim_room's provenance check calls the same scan_members"),
    "tools/conftest.py":
        (".emp", "_pair_problems -> artifact_provenance.check_pair -> the same scan_members"),
}


def _norm(path: str) -> str:
    path = path.replace(os.sep, "/")
    return path[2:] if path.startswith("./") else path


def _matches(key: str, path: str) -> bool:
    if key.startswith("*"):                 # a suffix: any docs FILE ending in it
        return path.startswith("docs/") and not path.endswith("/") and path.endswith(key[1:])
    if key.endswith("/"):
        return path.startswith(key)
    return path == key


def rules_for(path: str) -> list:
    """Every rule matching a docs/ path (or directory, spelled with a trailing /)."""
    path = _norm(path)
    return [r for r in RULES if _matches(r[0], path)]


def lister_covered(who: str) -> bool:
    """A declared lister is covered when every docs file of the kind it keeps is CODE."""
    entry = LISTERS.get(who)
    return bool(entry) and classify("docs/any/probe" + entry[0]) == CODE


def classify(path: str) -> str:
    path = _norm(path)
    if not path.startswith("docs/"):
        return CODE
    classes = {r[1] for r in rules_for(path)}
    return CODE if CODE in classes else CHECKED if CHECKED in classes else DOCS


def readers_for(paths) -> list:
    out = []
    for p in paths:
        if classify(p) != CHECKED:
            continue
        for rule in rules_for(p):
            for r in rule[2]:
                if r not in out:
                    out.append(r)
    return out


# ------------------------------------------------------------------------------------
# git
# ------------------------------------------------------------------------------------
class GitError(Exception):
    pass


def git(*args, cwd=None, check=True) -> str:
    p = subprocess.run(["git", *args], cwd=cwd, capture_output=True)
    if check and p.returncode != 0:
        raise GitError("git %s: %s" % (" ".join(args), p.stderr.decode(errors="replace").strip()))
    return p.stdout.decode(errors="surrogateescape")


def toplevel(cwd=None) -> str:
    return git("rev-parse", "--show-toplevel", cwd=cwd).strip()


def rev_parse(rev, cwd=None) -> str:
    return git("rev-parse", "--verify", "--quiet", rev + "^{commit}", cwd=cwd).strip()


def has_commit(sha, cwd=None) -> bool:
    return subprocess.run(["git", "cat-file", "-e", sha + "^{commit}"], cwd=cwd,
                          capture_output=True).returncode == 0


def content_key(rev="HEAD", cwd=None) -> str:
    """sha256 over every CODE-class (mode, type, object, path) in REV's tree."""
    raw = git("ls-tree", "-r", "-z", "--full-tree", rev, cwd=cwd)
    h = hashlib.sha256((KEY_VERSION + "\0").encode())
    n = 0
    for entry in raw.split("\0"):
        if not entry:
            continue
        meta, path = entry.split("\t", 1)
        if classify(path) != CODE:
            continue
        h.update(meta.encode() + b"\t" + path.encode(errors="surrogateescape") + b"\0")
        n += 1
    if n == 0:
        raise GitError("%s has no code paths at all; refusing to key an empty tree" % rev)
    return h.hexdigest()


def dirty_paths(cwd=None) -> list:
    """(status, path) for every modified, staged or untracked (not ignored) path."""
    raw = git("status", "--porcelain=v1", "-z", "--untracked-files=all", cwd=cwd)
    out, parts, i = [], raw.split("\0"), 0
    while i < len(parts):
        e = parts[i]
        i += 1
        if not e:
            continue
        st, path = e[:2], e[3:]
        out.append((st, path))
        if st[0] in "RC":          # rename/copy: the source path follows
            out.append((st, parts[i]))
            i += 1
    return out


def blocking_dirt(cwd=None) -> list:
    """Dirty paths that could make a build grade something other than the commit: CODE.
    A dirty CHECKED or DOCS path cannot: the key excludes them, and a push re-runs the
    tests that read a CHECKED path against the pushed commit itself."""
    return [(s, p) for s, p in dirty_paths(cwd) if classify(p) == CODE]


# ------------------------------------------------------------------------------------
# stamps
# ------------------------------------------------------------------------------------
def stamp_dir(cwd=None) -> str:
    d = os.environ.get("AEON_LAND_GATE_DIR")
    if d:
        return d
    common = git("rev-parse", "--path-format=absolute", "--git-common-dir", cwd=cwd).strip()
    return os.path.join(common, "aeon-land-gate")


def read_stamp(key, cwd=None):
    """(stamp, "") if KEY has a complete green stamp, else (None, why)."""
    p = os.path.join(stamp_dir(cwd), key + ".json")
    try:
        with open(p) as f:
            s = json.load(f)
    except FileNotFoundError:
        return None, "no stamp for this content"
    except (OSError, ValueError) as e:
        return None, "unreadable stamp %s (%s)" % (p, e)
    if not isinstance(s, dict) or s.get("key") != key:
        return None, "stamp %s does not name this content's key" % p
    if s.get("finished") != 0:
        return None, "stamp %s records finished=%r, not 0" % (p, s.get("finished"))
    return s, ""


def _md5(path):
    try:
        with open(path, "rb") as f:
            return hashlib.md5(f.read()).hexdigest()
    except OSError:
        return None


# ------------------------------------------------------------------------------------
# begin / finish (landing_build.sh)
# ------------------------------------------------------------------------------------
def cmd_begin(argv) -> int:
    """Print the evidence, then one machine line: LAND_GATE_START HEAD KEY CLEAN."""
    try:
        head = rev_parse("HEAD")
        key = content_key(head)
        dirt = blocking_dirt()
    except GitError as e:
        print("land-gate: UNMEASURABLE at start (%s): this run will write no stamp" % e)
        print("LAND_GATE_START unmeasurable unmeasurable 0")
        return 0
    print("land-gate: start HEAD=%s key=%s" % (head, key[:16]))
    if dirt:
        print("land-gate: %d code path(s) dirty at start, so this run CANNOT stamp:" % len(dirt))
        for st, p in dirt[:20]:
            print("land-gate:     %s %s" % (st, p))
        if len(dirt) > 20:
            print("land-gate:     ... and %d more" % (len(dirt) - 20))
    print("LAND_GATE_START %s %s %d" % (head, key, 0 if dirt else 1))
    return 0


def cmd_finish(argv) -> int:
    """Exit 0: stamp written. 1: no stamp, as expected (a run that was not green, a dirty
    start, an unmeasurable start). 3: no stamp because HEAD or the tree MOVED under the
    run, which makes everything the run printed unattributable."""
    import argparse
    ap = argparse.ArgumentParser(prog="land_gate.py finish")
    for flag in ("--head", "--key", "--clean", "--rc"):
        ap.add_argument(flag, required=True)
    ap.add_argument("--sigil", default=None)
    a = ap.parse_args(argv)

    def say(m):
        print("land-gate: " + m)

    if a.head == "unmeasurable":
        say("NO STAMP: the start could not be measured (see the start line)")
        return 1
    try:
        now = rev_parse("HEAD")
        dirt = blocking_dirt()
    except GitError as e:
        say("NO STAMP: the end could not be measured (%s)" % e)
        return 1
    if now != a.head:
        say("NO STAMP: HEAD MOVED during the run (%s -> %s). The run graded a tree that"
            " is no longer HEAD; nothing it printed is evidence for either commit." % (a.head, now))
        return 3
    if a.clean == "1" and dirt:
        say("NO STAMP: the tree CHANGED during the run (%d code path(s) dirty now, clean"
            " at start). What was built is not what is committed:" % len(dirt))
        for st, p in dirt[:20]:
            say("    %s %s" % (st, p))
        return 3
    if a.rc != "0":
        say("NO STAMP: finished=%s. A stamp records a completed GREEN run only." % a.rc)
        return 1
    if a.clean != "1":
        say("NO STAMP: code paths were dirty at start (listed there). Commit, then re-run.")
        return 1
    key = content_key(a.head)
    if key != a.key:
        say("NO STAMP: the key of %s is now %s, not %s" % (a.head, key[:16], a.key[:16]))
        return 3
    d = stamp_dir()
    os.makedirs(d, exist_ok=True)
    stamp = {
        "key": key,
        "head": a.head,
        "tree": git("rev-parse", a.head + "^{tree}").strip(),
        "finished": 0,
        "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "worktree": toplevel(),
        "sigil_md5": _md5(a.sigil) if a.sigil else None,
    }
    final = os.path.join(d, key + ".json")
    tmp = "%s.tmp.%d" % (final, os.getpid())
    with open(tmp, "w") as f:
        json.dump(stamp, f, indent=1, sort_keys=True)
        f.write("\n")
    os.replace(tmp, final)
    say("STAMP WRITTEN key=%s head=%s -> %s" % (key[:16], a.head[:12], final))
    return 0


# ------------------------------------------------------------------------------------
# pre-push
# ------------------------------------------------------------------------------------
_CHILD_ENV_DROP = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_PREFIX",
                   "GIT_COMMON_DIR", "GIT_OBJECT_DIRECTORY",
                   "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_QUARANTINE_PATH",
                   "PYTEST_ADDOPTS", "FAST", "NO_LINT", "DEBUG")


def _validate_checked(paths, lsha, top, say) -> bool:
    """Run the source-only tests that read the CHECKED paths this push changes, in a
    temporary detached worktree of the PUSHED commit, so the answer is about what is
    being published whatever the pushing checkout holds (a dirty lane-status.json, a
    different HEAD). The worktree is a SIBLING of the pushing checkout because the
    suite's tests locate their paired repositories (sigil) beside the aeon root."""
    readers = readers_for(paths)
    if not readers:
        say("REFUSED: %d checked path(s) changed but no rule names a reader" % len(paths))
        return False
    wt = os.path.join(os.path.dirname(top), ".aeon-land-gate-%d-%d" % (os.getpid(), int(time.time())))
    say("validating %d checked path(s) with %s, in a temporary checkout of %s (%s)"
        % (len(paths), " ".join(readers), lsha[:12], wt))
    t0 = time.monotonic()
    try:
        git("worktree", "add", "-q", "--detach", wt, lsha, cwd=top)
    except GitError as e:
        say("REFUSED: could not make a checkout of the pushed commit to validate in (%s)" % e)
        return False
    try:
        missing = [r for r in readers if not os.path.isfile(os.path.join(wt, r))]
        if missing:
            say("REFUSED: reader test(s) named by a rule are absent from %s: %s"
                % (lsha[:12], ", ".join(missing)))
            return False
        env = {k: v for k, v in os.environ.items() if k not in _CHILD_ENV_DROP}
        cmd = [sys.executable, "-m", "pytest", "-q", "--no-header", "-p", "no:cacheprovider",
               "-m", "not needs_build", *readers]
        p = subprocess.run(cmd, cwd=wt, env=env, capture_output=True, text=True)
    finally:
        subprocess.run(["git", "worktree", "remove", "--force", wt], cwd=top, capture_output=True)
        shutil.rmtree(wt, ignore_errors=True)
    dt = time.monotonic() - t0
    if p.returncode == 0:
        last = [l for l in p.stdout.splitlines() if l.strip()]
        say("validated in %.1f s: %s" % (dt, last[-1] if last else "(no summary line)"))
        return True
    sys.stderr.write(p.stdout[-6000:])
    sys.stderr.write(p.stderr[-2000:])
    why = "collected NO tests (exit 5): unmeasurable, never a pass" if p.returncode == 5 \
        else "exit %d" % p.returncode
    say("REFUSED: the checked-path tests FAILED (%s) after %.1f s: %s" % (why, dt, " ".join(cmd[2:])))
    return False


def _one_master_update(lsha, rsha, top, say) -> bool:
    if lsha == ZERO:
        say("REFUSED: this push DELETES master.")
        return False
    base = rsha if rsha != ZERO and has_commit(rsha, cwd=top) else None
    if base is None:
        say("cannot diff against the remote (%s): requiring a stamp, and validating every"
            " checked rule." % ("it has no master" if rsha == ZERO else
                                "its master %s is not in this repository; git fetch first" % rsha[:12]))
        code_paths, checked_paths = None, [r[0] for r in RULES if r[1] == CHECKED]
    else:
        changed = [p for p in git("diff", "--name-only", "-z", "--no-renames", base, lsha,
                                  cwd=top).split("\0") if p]
        code_paths = [p for p in changed if classify(p) == CODE]
        checked_paths = [p for p in changed if classify(p) == CHECKED]
        say("master %s..%s: %d path(s) change: %d code, %d checked, %d docs"
            % (base[:12], lsha[:12], len(changed), len(code_paths), len(checked_paths),
               len(changed) - len(code_paths) - len(checked_paths)))
    if code_paths == []:
        say("no code path differs from the remote's master: no build is needed.")
    else:
        key = content_key(lsha, cwd=top)
        stamp, why = read_stamp(key, cwd=top)
        if stamp is None:
            say("REFUSED: %s (key %s)." % (why, key[:16]))
            for p in (code_paths or [])[:15]:
                say("    code: %s" % p)
            if code_paths and len(code_paths) > 15:
                say("    ... and %d more code path(s)" % (len(code_paths) - 15))
            say("  Prove it: from a clean checkout of %s run tools/landing_build.sh, read its"
                " 'STAMP WRITTEN' and finished=0 lines, then push again." % lsha[:12])
            return False
        say("code proven green: stamp %s, written %s in %s for head %s (land_gate.py finish,"
            " which only landing_build.sh calls)"
            % (key[:16], stamp.get("at"), stamp.get("worktree"), str(stamp.get("head"))[:12]))
    if checked_paths:
        return _validate_checked(checked_paths, lsha, top, say)
    return True


def cmd_pre_push(argv) -> int:
    remote = argv[0] if argv else "?"

    def say(m):
        print("land-gate: " + m, file=sys.stderr)

    lines = [l.split() for l in sys.stdin.read().splitlines() if l.strip()]
    master = [l for l in lines if len(l) == 4 and l[2] == MASTER]
    if not master:
        return 0
    if os.environ.get("AEON_LAND_GATE") == "skip":
        say("=" * 72)
        say("GATE SKIPPED (AEON_LAND_GATE=skip). This push to %s master is UNVERIFIED:" % remote)
        for l in master:
            say("    %s -> %s" % (l[1][:12], MASTER))
        say("Say so in the lane log. `git push --no-verify` skips it too, and SILENTLY.")
        say("=" * 72)
        return 0
    t0 = time.monotonic()
    try:
        top = toplevel()
        ok = all(_one_master_update(l[1], l[3], top, say) for l in master)
    except GitError as e:
        say("REFUSED: could not measure (%s). Unmeasurable is never green." % e)
        ok = False
    if ok:
        say("ALLOWED: the push to %s master (gate took %.2f s)." % (remote, time.monotonic() - t0))
        return 0
    say("Nothing was pushed. The deliberate, printed bypass: AEON_LAND_GATE=skip git push ...")
    return 1


def cmd_stamps(argv) -> int:
    d = stamp_dir()
    try:
        names = sorted(n for n in os.listdir(d) if n.endswith(".json"))
    except FileNotFoundError:
        names = []
    print("%d stamp(s) in %s" % (len(names), d))
    for n in names:
        try:
            with open(os.path.join(d, n)) as f:
                s = json.load(f)
            print("  %s  head=%s  at=%s  finished=%s" % (n[:16], str(s.get("head"))[:12],
                                                          s.get("at"), s.get("finished")))
        except (OSError, ValueError) as e:
            print("  %s  UNREADABLE (%s)" % (n, e))
    return 0


def cmd_key(argv) -> int:
    print(content_key(argv[0] if argv else "HEAD"))
    return 0


def cmd_classify(argv) -> int:
    for p in argv:
        print("%s\t%s" % (classify(p), p))
    return 0


#: The ONE list of legal modes, and it is the dispatcher (LS-15d's rule, held by
#: tools/test_cli_dispatch_refuses.py): an unknown or missing mode prints usage and
#: exits 1 before any handler runs. The lambdas look the handler up at call time so
#: that test's tripwires replace the real thing. `finish` is the one that writes.
MODES = {
    "key": lambda a: cmd_key(a),
    "classify": lambda a: cmd_classify(a),
    "begin": lambda a: cmd_begin(a),
    "finish": lambda a: cmd_finish(a),
    "pre-push": lambda a: cmd_pre_push(a),
    "stamps": lambda a: cmd_stamps(a),
}


def main(argv) -> int:
    handler = MODES.get(argv[0]) if argv else None
    if handler is None:
        print("Usage: tools/land_gate.py {%s} ...  (see the module docstring)" % "|".join(MODES))
        sys.exit(1)
    return handler(argv[1:])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
