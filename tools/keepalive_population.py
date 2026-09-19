#!/usr/bin/env python3
"""keepalive_population — who the instrument keepalive lane is responsible for.

THE DEFECT THIS SERVES. A channel that cannot report is indistinguishable from a
channel reporting nothing wrong. `tools/parallax_hscroll_probe.py` crashed on startup
from 2026-08-26 until it was found on 2026-09-18, and the crash was hiding 35 findings.
`tools/parallax_hscroll_identity.py` had not run since 2026-08-29. Nothing noticed,
because nothing ran them.

WHY THE POPULATION IS DERIVED HERE RATHER THAN LISTED. A keepalive lane whose population
is a hand-typed list rots the same way the instruments did: a tool added to the tree and
not added to the list is invisible, and the lane goes on reporting green over a shrinking
fraction of the thing it claims to cover. So the lane asks the tree, every run, and
`keepalive_lane.py` refuses to grade unless the manifest accounts for every name this
module returns.

THE TWO DEFINITIONS, AND WHY ONLY THE FIRST IS LOAD-BEARING.

  POPULATION  — every `tools/*.py` that is not a `test_*`, and is not this lane's own
                machinery, that names `BusClient`. These are the "bus instruments": tools
                that drive a headless emulator and measure the engine through it.
                **85 of them on 2026-09-18**, and the criterion is deliberately the
                superset: 84 literally CONSTRUCT a `BusClient`, and the 85th,
                `transition_window_probe.py`, shims `aether.BusClient.call` to instrument
                another tool instead of constructing one. Both relayed counts of this
                population (84 and 85) are therefore correct about different criteria.
                A superset cannot miss an instrument, which is the property that matters;
                a tighter criterion buys nothing and can only drop somebody.

  UNREACHABLE — the subset that NOTHING EXECUTES. Not "referenced by nothing": a tool
                referenced only by another tool that nothing runs is just as dead, and a
                mention in prose is not an execution at all. So this is transitive
                reachability from the entry points that actually execute on this machine
                — `build.sh`, `tools/landing_build.sh`, `tools/nightly_effects_gates.sh`,
                and every `tools/test_*.py` (`pytest tools` runs them on every build) —
                over references that appear in CODE, with comments and docstrings
                stripped first.

⚠ THE UNREACHABLE COUNT IS DEFINITION-DEPENDENT AND THE SPREAD IS LARGE. Measured on this
  tree, 2026-09-18, over the same 85:

      any mention in any tracked file                            0 unreachable
      mention in a runner file (.sh/.py/.toml/...)              18
      same, excluding test_*.py                                 21
      transitive reachability, references matched in RAW text   25
      transitive reachability, references matched in CODE ONLY  50   <- what this returns

  The first four all over-credit, and the fourth was checked rather than assumed: of the
  tools it called reachable, `dplc_coherence_witness` was reached through a sentence in
  `test_tool_selftests.py`'s docstring, `floor_capture` and `floor_hscroll_dump` through a
  paragraph in `perspective_floor_witness.py`'s prose, and `sec5_band_witness` and
  `lens_residue_raster_witness` through a comment in `effects_gen.py`. A tool named in a
  comment is not a tool anybody runs. Stripping comments and docstrings — but KEEPING short
  string literals, because an invocation lives in `"tools/foo.py"` and prose does not —
  removes that credit, and the count roughly doubles.

  A figure of "29 unreachable" has been relayed for this tree. It does not reproduce under
  any of the five definitions above. So the count is ADVISORY: it says which instruments
  most need wiring, and it is not what the lane's coverage rests on. The ACCOUNTING is the
  real invariant — `keepalive_lane.py` requires a manifest disposition for every one of the
  85 — and that does not depend on this heuristic being exactly right.
"""
import io
import os
import re
import subprocess
import sys
import tokenize

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(TOOLS_DIR)

# This lane's own two files. They name `BusClient` in their prose and are not instruments.
LANE_OWN_FILES = frozenset({"keepalive_population.py", "keepalive_lane.py"})

# The entry points that actually run on this machine. build.sh is every developer's
# build; landing_build.sh is the pre-merge check; nightly_effects_gates.sh is the
# backstop timer. Anything reachable from one of these is exercised by somebody.
SCRIPT_ENTRY_POINTS = (
    "build.sh",
    "tools/landing_build.sh",
    "tools/nightly_effects_gates.sh",
)


def _tracked_files(repo=REPO):
    out = subprocess.run(
        ["git", "-C", repo, "ls-files"],
        capture_output=True, text=True, check=True,
    ).stdout.split("\n")
    return [f for f in out if f]


def _read(repo, rel, cap=4_000_000):
    path = os.path.join(repo, rel)
    try:
        if os.path.getsize(path) > cap:
            return None
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return None


def population(repo=REPO):
    """Every bus instrument: tools/*.py, not test_*, not this lane's own machinery."""
    names = []
    tools = os.path.join(repo, "tools")
    for fname in sorted(os.listdir(tools)):
        if not fname.endswith(".py") or fname.startswith("test_"):
            continue
        # The keepalive lane's own machinery is not an instrument. Without this the
        # population module counts itself, because it spells `BusClient` in its prose.
        #
        # ⚠ AN EXPLICIT SET, NOT THE `keepalive_` PREFIX, and that is not a style choice.
        # This started as a prefix test, and the drift fixture that was supposed to prove
        # the UNDECLARED arm fires was itself named `keepalive_drift_fixture_probe.py` --
        # so the exclusion ate the fixture and the lane reported a clean accounting over a
        # tree that had just grown an undeclared instrument. A prefix exclusion is an
        # open-ended hole: anything anyone names `keepalive_*` later escapes the census
        # silently, which is the exact defect this lane exists to close, reintroduced by
        # its own bookkeeping. The set below can only ever excuse these two files.
        if fname in LANE_OWN_FILES:
            continue
        text = _read(repo, os.path.join("tools", fname))
        if text is not None and "BusClient" in text:
            names.append(fname)
    return names


def strip_prose(src):
    """Drop comments and triple-quoted (doc)strings; keep code and SHORT string literals.

    The asymmetry is the point. An invocation lives in a short literal --
    `subprocess.run(["python3", "tools/foo.py"])` -- and prose does not. Keeping short
    strings keeps every real invocation; dropping triple-quoted ones drops the docstring
    paragraphs that were crediting dead tools as live.
    """
    try:
        toks = list(tokenize.generate_tokens(io.StringIO(src).readline))
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return src  # unparseable: keep raw text rather than silently dropping the file
    triple = ('"' * 3, "'" * 3)
    kept = []
    for tok in toks:
        if tok.type == tokenize.COMMENT:
            continue
        if tok.type == tokenize.STRING and tok.string.lstrip("rbfuRBFU")[:3] in triple:
            continue
        kept.append(tok.string)
    return "\n".join(kept)


# The keepalive lane's own files, which must not act as reachability SOURCES.
#
# ⚠ MEASURED, NOT ANTICIPATED. Without this the advisory count moved 50 -> 47 the moment
# the lane's own tests were written, because `tools/test_keepalive_lane.py` carries an
# argparse fixture whose text is the short string "usage: sec5_band_witness.py [-h] ..." --
# and a short string literal is exactly what this module deliberately KEEPS, since that is
# where a real invocation lives. So the lane's own bookkeeping was crediting instruments as
# live, which is the over-crediting flaw documented at the top of this file, reintroduced
# from inside. It is also wrong on the merits: "the keepalive lane mentions this tool" can
# never be evidence that something ELSE runs it.
# ⚠ AND IT ROTTED ON THE NEXT LANE FILE ADDED, because nothing enforced that a new one
# joined the list. MEASURED 2026-09-19: committing `tools/test_keepalive_surface.py` --
# whose control names two instruments by filename, in exactly the short literals this
# module deliberately keeps -- moved the same count 50 -> 43 and flipped
# `floor_hscroll_dump.py` from dead to live. Seven instruments credited as executed by a
# file that only measures them. The list stays EXPLICIT for the reason above, and
# `test_keepalive_surface.test_every_keepalive_file_is_excluded_as_a_reachability_source`
# is what now makes it keep up.
LANE_BOOKKEEPING = frozenset({
    "tools/keepalive_population.py",
    "tools/keepalive_lane.py",
    "tools/test_keepalive_lane.py",
    "tools/nightly_instrument_keepalive.sh",
    "tools/keepalive_surface.py",
    "tools/test_keepalive_surface.py",
})


def _code_corpus(repo):
    corpus = {}
    for rel in _tracked_files(repo):
        if not (rel.endswith(".py") or rel.endswith(".sh")):
            continue
        if rel in LANE_BOOKKEEPING:
            continue
        text = _read(repo, rel)
        if text is None:
            continue
        corpus[rel] = strip_prose(text) if rel.endswith(".py") else text
    return corpus


def _reach(repo):
    """Returns {rel: parent_rel_or_None} for everything reachable from an entry point."""
    corpus = _code_corpus(repo)
    entries = [e for e in SCRIPT_ENTRY_POINTS if e in corpus]
    entries += [
        rel for rel in corpus
        if rel.startswith("tools/") and os.path.basename(rel).startswith("test_")
    ]

    # One word-boundary pattern per file, so `floor_capture` does not match
    # `floor_capture_extra`. Both the bare filename (how a script spells it) and the
    # module stem (how an import spells it) count as a reference.
    patterns = {}
    for rel in corpus:
        base = os.path.basename(rel)
        stem = base[:-3] if base.endswith((".py", ".sh")) else base
        patterns[rel] = re.compile(r"(?<![\w.-])" + re.escape(stem) + r"(?![\w-])")

    parent = {e: None for e in entries}
    stack = list(entries)
    while stack:
        cur = stack.pop()
        text = corpus[cur]
        for other, pat in patterns.items():
            if other in parent or other == cur:
                continue
            if pat.search(text):
                parent[other] = cur
                stack.append(other)
    return parent


def unreachable(repo=REPO):
    """(population, unreachable) as two sorted lists of bare filenames."""
    pop = population(repo)
    parent = _reach(repo)
    dead = sorted(t for t in pop if "tools/" + t not in parent)
    return sorted(pop), dead


def main(argv=None):
    pop, dead = unreachable()
    print(f"bus instruments (tools/*.py, not test_*, names BusClient): {len(pop)}")
    print(f"reachable in CODE from a real entry point:                 {len(pop) - len(dead)}")
    print(f"UNREACHABLE -- nothing executes these:                     {len(dead)}")
    for name in dead:
        print("   ", name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
