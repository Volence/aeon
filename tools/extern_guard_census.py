#!/usr/bin/env python3
"""extern_guard_census — per-guard red-first proof for the `extern()`-bearing `ensure`
family, the cross-namespace/memory-reservation guards (LS-16, 2026-09-06).

WHY THIS EXISTS AND WHY IT IS NOT `emp_expect_fail`
---------------------------------------------------
`tools/emp_expect_fail.py` is the tree's negative-build lane, and it proves that a guard
reachable from a POISON MODULE can go red. That covers guards living in comptime
constructors (`raster_dsl`'s `band()`, `scene_dsl`'s `scene()`): a poison calls the
constructor with a bad argument and the constructor's `ensure` fires.

An `extern()`-bearing `ensure` cannot be reached that way, for two independent reasons:

  1. IT IS NOT A COMPTIME ENSURE. An `extern()` in the condition makes the expression
     link-resolved, so sigil lowers the site to a `LinkAssert` and evaluates it AFTER
     `resolve_layout`, in `check_link_asserts`. A failure is reported as
     `declared-chain drift guard FIRED: N error(s); first Some(Diagnostic { .. })`
     (sigil-harness/src/native.rs) — NOT as the `[Error]` lines `build_program` emits and
     `emp_expect_fail` counts. A row registered there fails on `got 0 [Error]
     diagnostic(s), expected 1` however correct the guard is.
  2. ITS SUBJECT IS THE LINKED IMAGE. These guards compare an engine constant against its
     `.asm`-namespace twin, or a RAM reservation's SPAN (`extern("X_End") - extern("X")`)
     against the geometry that has to fit in it. A poison module contributes ZERO BYTES
     by construction, so it cannot move a reservation or an equate; there is no argument
     a poison can pass that makes `parallax.emp:480` false.

So the only way to prove one of these individually is to make its own condition false and
watch the build. That is what this tool does, and mutating the tree is exactly why it is
NOT wired into `build.sh`: a lane that rewrites engine sources leaves them rewritten if it
is interrupted, which the expect-fail lane deliberately avoids (see that file's docstring
and games/sonic4/test/poison/README.md). Run it by hand after touching the family.

    python3 tools/extern_guard_census.py --list
    python3 tools/extern_guard_census.py --game sonic4
    python3 tools/extern_guard_census.py --game demo --file z80_init

THE MUTATION, AND WHY IT IS THIS ONE
------------------------------------
`ensure(COND, MSG)` becomes `ensure(!(COND), MSG)`. It is the only falsifier that keeps
every `extern()` in the condition, so the site stays a `LinkAssert` and the experiment
measures the guard rather than reclassifying it. On a clean tree COND is true, so `!(COND)`
is false and the guard MUST fire; a site that produces no diagnostic under negation is not
being evaluated at all, which is the finding this tool exists to surface.

It does NOT prove the guard's SUBJECT can drift — it proves the guard is live, reached, and
reported. That is the vacuity question: a guard nothing evaluates is a comment.

READING A MISS — THREE WORLDS, AND THEY ARE NOT THE SAME
--------------------------------------------------------
  (a) rc 0, no diagnostic  -> the module is outside this profile's `use` closure and its
      module-level ensures are never evaluated. sigil says so itself:
      `SIGIL_WARNINGS=full` prints `[module.unreachable]` naming the module and its guard
      count. NOT NECESSARILY A DEFECT — a game-side module is legitimately absent from the
      other game — but a guard unreachable from EVERY built shape guards nothing.
  (b) rc 101, a panic      -> the guard fired through `emit_sound_blob`'s co-residency /
      drift path, which `panic!`s instead of returning diagnostics. The guard IS live; the
      REPORTING is a panic. This tool matches the message out of the panic text and counts
      it as proved, and says so in the row.
  (c) rc 1, wrong count    -> the tree is already red for an unrelated reason. Fix that
      first; every row after it inherits the noise.

MEASURED 2026-09-06 on eafd1a5b, one build per FILE (messages are unique WITHIN a file, so
one build proves every guard in it by name), 19 builds, ~37 s wall for the sonic4 sweep:
  sonic4 : 134/135 proved (131 link-assert + 3 via the emit_sound_blob panic path)
           MISS: engine/system/z80_init.emp:50 — world (a), sound-OFF module, not in
           sonic4's closure. It fires under `--game demo`, which has sound off.
  demo   : 29/29 engine-side guards proved, z80_init:50 among them. The 106 sonic4
           game-side guards are absent from demo's closure, which is world (a) and expected.
Union over the two games: every one of the 135 is proved able to fire in some shipped shape.
"""
import argparse
import os
import re
import subprocess
import sys
import time
from collections import defaultdict

AEON = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SIGIL = os.environ.get("SIGIL_BUILD")


# ---------------------------------------------------------------- source scanning

def inert_mask(text: str) -> bytearray:
    """1 at every offset inside a `//` line comment, a `/* */` block, or a string body.

    The scan has to be string-aware in both directions: an `ensure(` inside a header
    comment is not a site (52 of them in this tree), and a `//` inside a guard's own
    message is not a comment.
    """
    n = len(text)
    mask = bytearray(n)
    in_str = in_line = in_block = False
    i = 0
    while i < n:
        c = text[i]
        if in_line:
            mask[i] = 1
            if c == "\n":
                in_line = False
            i += 1
        elif in_block:
            mask[i] = 1
            if c == "*" and i + 1 < n and text[i + 1] == "/":
                mask[i + 1] = 1
                i += 2
                in_block = False
            else:
                i += 1
        elif in_str:
            mask[i] = 1
            if c == "\\":
                if i + 1 < n:
                    mask[i + 1] = 1
                i += 2
            else:
                if c == '"':
                    in_str = False
                i += 1
        elif c == "/" and i + 1 < n and text[i + 1] == "/":
            in_line = True
            mask[i] = 1
            i += 1
        elif c == "/" and i + 1 < n and text[i + 1] == "*":
            in_block = True
            mask[i] = 1
            i += 1
        elif c == '"':
            in_str = True
            mask[i] = 1
            i += 1
        else:
            i += 1
    return mask


def sites_in(rel: str, text: str) -> list:
    """Every `ensure(` site in one module, paren-matched, with RAW offsets."""
    mask = inert_mask(text)
    n = len(text)
    out = []
    for m in re.finditer(r"\bensure\s*\(", text):
        if mask[m.start()]:
            continue
        op = m.end() - 1
        depth = 0
        comma = None
        i = op
        while i < n:
            if mask[i]:
                i += 1
                continue
            c = text[i]
            if c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
                if depth == 0:
                    break
            elif c == "," and depth == 1 and comma is None:
                comma = i
            i += 1
        cond_end = comma if comma is not None else i
        out.append({
            "file": rel,
            "line": text.count("\n", 0, m.start()) + 1,
            "cond_start": op + 1,
            "cond_end": cond_end,
            "cond": text[op + 1:cond_end],
            "msg": text[cond_end:i],
        })
    return out


def collect() -> list:
    """Every extern()-bearing `ensure` under engine/ and games/, sorted by file+offset."""
    files = []
    for root in ("engine", "games"):
        for dp, _dn, fn in os.walk(os.path.join(AEON, root)):
            for f in fn:
                if f.endswith(".emp"):
                    files.append(os.path.join(dp, f))
    files.sort()
    sites = []
    for p in files:
        rel = os.path.relpath(p, AEON)
        for s in sites_in(rel, open(p).read()):
            if re.search(r"\bextern\s*\(", s["cond"]):
                sites.append(s)
    sites.sort(key=lambda s: (s["file"], s["cond_start"]))
    return sites


def msg_literal(site: dict) -> str:
    """The guard's own message text, with the interpolation tail dropped.

    The head before the first `{` is what survives interpolation verbatim, and it is
    unique WITHIN each file (checked by `--list`), which is what lets ONE build per file
    prove every guard in that file by name. Across files it is NOT unique — the three
    anim modules share all 25 of their sentences — so this tool never matches a message
    against a build that mutated a different file.
    """
    m = site["msg"].strip()
    if m.startswith(","):
        m = m[1:].strip()
    if m.startswith('"'):
        m = m[1:]
    if m.endswith('"'):
        m = m[:-1]
    return " ".join(re.split(r"\{", m)[0].split())


# ---------------------------------------------------------------- tree handling

def git(*args) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=AEON, capture_output=True, text=True)


def require_clean() -> None:
    """A dirty tracked tree is a hard refusal: restore is `git show HEAD:<path>`, so
    uncommitted work in a touched file would be DESTROYED by the restore, not merely
    reverted. Invariant 8(b) — restore from a COMMITTED baseline — read as a precondition."""
    st = git("status", "--porcelain")
    if st.returncode != 0:
        sys.exit("extern_guard_census: `git status` failed: " + st.stderr.strip())
    dirty = [l for l in st.stdout.splitlines() if not l.startswith("??")]
    if dirty:
        print("extern_guard_census: REFUSING to run — tracked files are modified.")
        print("This tool rewrites .emp sources and restores them from `git show HEAD:<path>`,")
        print("so uncommitted edits in a touched file would be discarded, not reverted.")
        for l in dirty:
            print("  " + l)
        sys.exit(2)


def restore(rel: str) -> None:
    blob = subprocess.run(["git", "show", "HEAD:" + rel], cwd=AEON, capture_output=True)
    if blob.returncode != 0:
        sys.exit("extern_guard_census: `git show HEAD:%s` failed — the tree may be left "
                 "MUTATED; restore it by hand before doing anything else." % rel)
    with open(os.path.join(AEON, rel), "wb") as fh:
        fh.write(blob.stdout)


def negate(rel: str, sites: list) -> None:
    p = os.path.join(AEON, rel)
    t = open(p).read()
    for s in sorted(sites, key=lambda x: -x["cond_start"]):
        a, b = s["cond_start"], s["cond_end"]
        t = t[:a] + "!(" + t[a:b] + ")" + t[b:]
    open(p, "w").write(t)


# ---------------------------------------------------------------- the sweep

def build(game: str, out: str) -> tuple:
    env = dict(os.environ, NATIVE_DEBUG="1")
    t0 = time.time()
    p = subprocess.run([SIGIL, "build", "--aeon", ".", "--native", "--game", game,
                        "-o", out],
                       cwd=AEON, capture_output=True, text=True, env=env)
    return p.returncode, p.stdout + p.stderr, time.time() - t0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", default="sonic4")
    ap.add_argument("--file", action="append", default=[],
                    help="only sweep files whose path contains this substring")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()

    sites = collect()
    byfile = defaultdict(list)
    for s in sites:
        byfile[s["file"]].append(s)

    if args.list:
        for f in sorted(byfile):
            ms = [msg_literal(s) for s in byfile[f]]
            dup = len(ms) - len(set(ms))
            print("%-56s n=%-3d distinct=%-3d%s" % (f, len(ms), len(set(ms)),
                                                    "  *** DUPLICATE MESSAGES ***" if dup else ""))
            for s in byfile[f]:
                print("      %5d  %s" % (s["line"], msg_literal(s)[:100]))
        print("TOTAL extern()-bearing ensure sites: %d in %d file(s)" % (len(sites), len(byfile)))
        return 0

    if not SIGIL:
        sys.exit("SIGIL_BUILD not set (same contract as build.sh)")
    require_clean()

    files = sorted(byfile)
    if args.file:
        files = [f for f in files if any(o in f for o in args.file)]
    if not files:
        sys.exit("extern_guard_census: --file matched nothing")

    # Messages must be unique WITHIN a file or one build cannot attribute its diagnostics.
    for f in files:
        ms = [msg_literal(s) for s in byfile[f]]
        if len(ms) != len(set(ms)):
            sys.exit("extern_guard_census: %s has guards with identical message heads; one "
                     "build per file cannot attribute them. Split the sweep or make the "
                     "messages distinct." % f)

    out = os.path.join(AEON, ".extern_guard_census.bin")
    proved = missing = 0
    misses = []
    restore_failed = False
    print("game=%s  files=%d  guards=%d" % (args.game, len(files),
                                            sum(len(byfile[f]) for f in files)))
    try:
        for f in files:
            ss = byfile[f]
            restore(f)
            negate(f, ss)
            rc, txt, el = build(args.game, out)
            restore(f)

            printed = {" ".join(l[len("REAL DRIFT: "):].split())
                       for l in txt.splitlines() if l.startswith("REAL DRIFT: ")}
            panicked = rc == 101 and "panicked at" in txt
            got, miss = [], []
            for s in ss:
                lit = msg_literal(s)
                hit = any(lit in pm for pm in printed) or (panicked and lit in txt)
                (got if hit else miss).append(s)
            proved += len(got)
            missing += len(miss)
            misses.extend((f, s) for s in miss)
            world = ("panic-path" if panicked else
                     "unreachable" if rc == 0 else "link-assert")
            print("  %-56s n=%-3d rc=%-3d proved=%-3d MISS=%-3d [%s] %.1fs"
                  % (f, len(ss), rc, len(got), len(miss), world, el))
            sys.stdout.flush()
    finally:
        for f in files:
            restore(f)
        if os.path.exists(out):
            os.remove(out)
        st = git("status", "--porcelain")
        left = [l for l in st.stdout.splitlines() if not l.startswith("??")]
        if left:
            print("extern_guard_census: RESTORE INCOMPLETE — tracked files still modified:")
            for l in left:
                print("  " + l)
            restore_failed = True

    if restore_failed:
        return 3

    print()
    print("extern_guard_census(%s): %d proved red, %d NOT PROVED" % (args.game, proved, missing))
    for f, s in misses:
        print("  NOT PROVED  %s:%d  %s" % (f, s["line"], msg_literal(s)[:110]))
    if misses:
        print("A guard that does not fire under negation is NOT being evaluated for this")
        print("game. Run `SIGIL_WARNINGS=full` and look for `[module.unreachable]` naming")
        print("its module before treating it as a defect, and check the OTHER game.")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
