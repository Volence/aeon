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

THE TWO DEFINITIONS.

  POPULATION  — every `tools/*.py` that is not a `test_*`, and is not this lane's own
                machinery, that DRIVES A HEADLESS EMULATOR. Membership is read off what
                the code DOES, from its AST, by five arms (`drives()`):

                  import    imports anything from one of the three modules that hand out
                            an emulator connection: `aether` (the bus client),
                            `aether_instance` (the spawner), `launcher` (the legacy
                            headless launcher). Every connection in the tree comes from
                            one of these three.
                  protocol  carries an Aether method name (`"emulator/..."`) as a code
                            string, i.e. it speaks the bus protocol on a client it was
                            handed. This is what admits the byte helpers.
                  socket    opens an `AF_UNIX` socket itself (what `evict_witness` did
                            before 2026-09-19). Redundant today; see `ARMS`.
                  borrow    uses a sibling tool's DRIVER CALLABLE — a top-level def/class
                            of a member whose own body reaches a connection. Importing a
                            sibling's arithmetic does not count; importing its `Server`
                            or its `run()` that spawns does.
                  child     runs a member tool, or the harness's `ab_runner.py`, as a
                            child process, from an argv display in its own code.

  UNREACHABLE — the subset that NOTHING EXECUTES. Transitive reachability from the entry
                points that actually run on this machine — `build.sh`,
                `tools/landing_build.sh`, `tools/nightly_effects_gates.sh`, and every
                `tools/test_*.py` — over EXECUTING references only (`exec_edges()`):

                  .sh   a `python3 … x.py` command, or `x.sh` in command position, on a
                        line that is not a comment and not an `echo`/`printf`;
                  .py   an argv display (`["python3", ".../x.py", …]`), a shell string
                        passed to `subprocess`/`os.system`, a `x.main(...)` call on an
                        imported module, or `runpy` on it.

                A name in prose, in a data table, in a regex, or in an import of the
                tool's arithmetic is NOT an execution, and does not credit anything.

⚠ CORRECTED 2026-09-25 (`CENSUS-CRITERION-TOO-NARROW`). BOTH definitions used to be looser,
  and the old figures are kept here, not overwritten:

  * The population was "names `BusClient`" — 85 on 2026-09-18 (84 construct one; the
    85th, `transition_window_probe.py`, shims `aether.BusClient.call`). The old docstring
    called that "deliberately the superset", and it was a superset of BUS CLIENTS only,
    not of emulator drivers: it missed `effects_gates.py`, `cart_identity.py`,
    `depth_onset_probe.py`, `cart_verify_spawn_proof.py` (booked 2026-09-19), and — found
    by this change, not booked — `base_swap_witness.py` (drives through
    `ramp_authored_witness.run`) and `staging_lifetime_timeline.py` (drives through
    `tick_variance_probe.Server`). It also counted `cart_coverage_census.py`, a static
    AST census that names `BusClient` in strings and drives nothing.
  * Reachability matched a tool's NAME anywhere in code (short string literals kept, since
    "an invocation lives in a short literal"). So a filename in a classification table
    (`cart_coverage_census.CANARIES`), in a test's regex, or an `import` of a tool's
    arithmetic all counted as "something executes this". The advisory unreachable count
    was 50 (2026-09-18/19), 44 then 43 (2026-09-25) under that rule.

  `python3 tools/keepalive_population.py` prints the current figures; the record of the
  change is `docs/research/2026-09-25-census-criterion.md`.

⚠ THE UNREACHABLE COUNT IS STILL ADVISORY. It is the input that says which instruments
  most need wiring; the ACCOUNTING is the invariant — `keepalive_lane.py` requires a
  manifest disposition for every member of the population, and
  `test_keepalive_lane.test_a_reachable_reason_is_true` requires every `[not_wired]`
  reason that claims "reachable" to be one this module agrees with. It under-credits by
  construction where a runner spells the tool through a variable (`[sys.executable,
  tool]` with `tool` from a parametrize list); that errs toward "dead", the safe side for
  a list of things that need wiring.
"""
import ast
import os
import re
import subprocess
import sys
import warnings

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

# The three modules that hand out a connection to an emulator. Each is the whole of its
# arm: `aether` is oracle's bus client, `aether_instance` is this tree's spawner, and
# `launcher` is the oracle-old harness's `headless_emulator` (still reached by
# raster_cost_probe and its importers).
CONNECTION_MODULES = frozenset({"aether", "aether_instance", "launcher"})

# Emulator drivers that live OUTSIDE tools/, so the census cannot derive them. A tool that
# runs one of these as a child drives an emulator. `ab_runner.py` is oracle-old's scene
# runner (`from launcher import headless_emulator`), which effects_gates' scene:* segments
# spawn. Read, not assumed: `ab_runner.py:91` on 2026-09-25.
EXTERNAL_DRIVERS = frozenset({"ab_runner.py"})

AETHER_METHOD = re.compile(r"^emulator/[a-z_]+$")
SUBPROCESS_CALLS = frozenset({"run", "Popen", "call", "check_call", "check_output", "system"})
INTERPRETERS = frozenset({"python", "python3", "bash", "sh"})


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


def _parse(text):
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SyntaxWarning)   # a tool's own bad escapes
            return ast.parse(text)
    except (SyntaxError, ValueError):
        return None


def _prose_ids(tree):
    """ids of every bare string STATEMENT: docstrings and prose blocks, never code."""
    return {id(n.value) for n in ast.walk(tree)
            if isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant)
            and isinstance(n.value.value, str)}


def _code_strings(node, prose):
    return [n.value for n in ast.walk(node)
            if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in prose]


def _imports(tree):
    """[(module, name, bound_as)] for absolute imports. `import x` gives name None."""
    out = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            for a in n.names:
                out.append((a.name, None, (a.asname or a.name).split(".")[0]))
        elif isinstance(n, ast.ImportFrom) and n.level == 0:
            for a in n.names:
                out.append((n.module or "", a.name, a.asname or a.name))
    return out


def _used_names(node):
    """Bare names read, and (root, attr) pairs, anywhere under `node`."""
    names, attrs = set(), set()
    for n in ast.walk(node):
        if isinstance(n, ast.Name):
            names.add(n.id)
        elif isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name):
            attrs.add((n.value.id, n.attr))
    return names, attrs


def _is_interpreter(el):
    if isinstance(el, ast.Constant) and isinstance(el.value, str):
        return os.path.basename(el.value) in INTERPRETERS
    return (isinstance(el, ast.Attribute) and el.attr == "executable"
            and isinstance(el.value, ast.Name) and el.value.id == "sys")


def _script_names(strings):
    return {os.path.basename(s.strip()) for s in strings
            if s.strip().endswith((".py", ".sh"))}


def _assigned(tree):
    """{name: [value nodes]} for every `name = value` in the file, any scope."""
    out = {}
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign):
            for t in n.targets:
                if isinstance(t, ast.Name):
                    out.setdefault(t.id, []).append(n.value)
        elif isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name) and n.value:
            out.setdefault(n.target.id, []).append(n.value)
    return out


def _argv_strings(node, prose, assigned, depth=2):
    """Code strings under an argv element, following `NAME = ...` bindings `depth` hops.

    `PROBE = HERE / "transition_window_probe.py"` then `[sys.executable, str(PROBE)]` is
    an invocation, and the literal lives in the binding, not the display.
    """
    out = _code_strings(node, prose)
    if depth:
        for n in ast.walk(node):
            if isinstance(n, ast.Name):
                for v in assigned.get(n.id, ()):
                    out += _argv_strings(v, prose, assigned, depth - 1)
    return out


def argv_targets(tree, prose=None):
    """Scripts this code RUNS: basenames named in an argv display or a shell string.

    An argv display is a list/tuple whose elements include an interpreter (`python3`,
    `sys.executable`, `bash`); the script is any code string under it ending `.py`/`.sh`,
    following `NAME = ...` bindings. A `subprocess.*`/`os.system` call also runs the
    script its argv list STARTS with, and the shell command its string first argument
    spells. Nothing else counts — not a string in a table, not a regex, not a usage line.
    """
    prose = _prose_ids(tree) if prose is None else prose
    assigned = _assigned(tree)
    out = set()
    for n in ast.walk(tree):
        if isinstance(n, (ast.List, ast.Tuple)) and n.elts:
            if any(_is_interpreter(e) for e in n.elts):
                out |= _script_names(_argv_strings(n, prose, assigned))
        elif isinstance(n, ast.Call) and n.args:
            f = n.func
            fname = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", None)
            if fname not in SUBPROCESS_CALLS:
                continue
            a0 = n.args[0]
            if isinstance(a0, ast.Constant) and isinstance(a0.value, str):
                out |= shell_targets(a0.value)
            elif isinstance(a0, (ast.List, ast.Tuple)) and a0.elts:
                # A script executed directly, no interpreter: `subprocess.run([".../x.sh"])`.
                # Only when the display IS the call's argv -- a bare tuple of script names
                # (`RUNNERS = ("landing_build.sh", ...)`) is a table, not an invocation.
                first = _argv_strings(a0.elts[0], prose, assigned)
                if any(s.strip().endswith((".sh", ".py")) for s in first):
                    out |= _script_names(first)
    return out


def main_call_targets(tree, prose=None):
    """Module stems whose `main()` this code calls, or that it hands to `runpy`.

    Includes the DYNAMIC form: a file that calls `importlib.import_module(<non-literal>)`
    AND calls some `.main(` executes every module whose stem it names in a code string
    (`test_cli_dispatch_refuses` drives nine CLIs' `main()` off a table that way). The
    table credits only because the same file carries the mechanism that runs it; a table
    in a file with no such mechanism credits nothing.
    """
    prose = _prose_ids(tree) if prose is None else prose
    imps = _imports(tree)
    mod_alias = {bound: mod for mod, name, bound in imps if name is None}
    main_alias = {bound: mod for mod, name, bound in imps if name == "main"}
    out = set()
    for n in ast.walk(tree):
        if not isinstance(n, ast.Call):
            continue
        f = n.func
        if (isinstance(f, ast.Attribute) and f.attr == "main"
                and isinstance(f.value, ast.Name) and f.value.id in mod_alias):
            out.add(mod_alias[f.value.id].split(".")[-1])
        elif isinstance(f, ast.Name) and f.id in main_alias:
            out.add(main_alias[f.id].split(".")[-1])
        elif (isinstance(f, ast.Attribute) and f.attr in ("run_path", "run_module")
              and isinstance(f.value, ast.Name) and f.value.id == "runpy"
              and n.args and isinstance(n.args[0], ast.Constant)
              and isinstance(n.args[0].value, str)):
            s = os.path.basename(n.args[0].value)
            out.add(s[:-3] if s.endswith(".py") else s)
    dyn_import = any(
        isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
        and n.func.attr == "import_module" and n.args
        and not isinstance(n.args[0], ast.Constant) for n in ast.walk(tree))
    any_main = any(
        isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "main"
        for n in ast.walk(tree))
    if dyn_import and any_main:
        out |= {("DYN", s) for s in _code_strings(tree, prose) if re.fullmatch(r"\w+", s)}
    return out


# --- shell -----------------------------------------------------------------------------

_SH_PY = re.compile(r"\bpython3?(?:\s+-[A-Za-z]+)*\s+[\"']?([^\s\"';|&)]*?\.py)\b")
_SH_SH = re.compile(
    r"(?:^|[;&|(!]|\$\(|\b(?:then|do|else|bash|sh|exec|nohup|source|time)\b)\s*"
    r"[\"']?([^\s\"';|&()]*\.sh)\b")
_SH_ECHO = re.compile(r"\b(?:echo|printf)\b[^;&|]*")


def _sh_code_lines(text):
    """Logical lines with comments and echo/printf segments removed."""
    joined = re.sub(r"\\\n", " ", text)
    out = []
    for line in joined.split("\n"):
        s = line.lstrip()
        if s.startswith("#"):
            continue
        line = re.sub(r"(^|\s)#.*$", r"\1", line)   # trailing comment
        out.append(_SH_ECHO.sub(" ", line))
    return out


def shell_targets(text):
    out = set()
    for line in _sh_code_lines(text):
        for m in _SH_PY.finditer(line):
            out.add(os.path.basename(m.group(1)))
        for m in _SH_SH.finditer(line):
            out.add(os.path.basename(m.group(1)))
    return out


# --- the population ---------------------------------------------------------------------

def _tool_sources(repo):
    tools = os.path.join(repo, "tools")
    out = {}
    for fname in sorted(os.listdir(tools)):
        if not fname.endswith(".py") or fname.startswith("test_"):
            continue
        # ⚠ AN EXPLICIT SET, NOT THE `keepalive_` PREFIX. This started as a prefix test,
        # and the drift fixture that was supposed to prove the UNDECLARED arm fires was
        # itself named `keepalive_drift_fixture_probe.py` -- so the exclusion ate the
        # fixture and the lane reported a clean accounting over a tree that had just grown
        # an undeclared instrument. The set below can only ever excuse these two files.
        if fname in LANE_OWN_FILES:
            continue
        text = _read(repo, os.path.join("tools", fname))
        if text is not None:
            out[fname] = text
    return out


def _def_facts(tree, prose):
    """{top-level def/class name: (names read, (root, attr) pairs, touches the bus itself)}."""
    out = {}
    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names, attrs = _used_names(n)
            direct = (("socket", "AF_UNIX") in attrs
                      or any(AETHER_METHOD.match(s) for s in _code_strings(n, prose)))
            out[n.name] = (names, attrs, direct)
    return out


def _driver_callables(facts, conn_names, borrowed):
    """Top-level defs/classes of a module whose bodies reach a connection.

    `conn_names` are names the module bound by importing from a connection module;
    `borrowed` are names it bound to a sibling's driver callable, plus (alias, attr)
    pairs for `import sibling` + `sibling.attr`. Closed over calls within the module.
    """
    bare, pairs = borrowed
    reach = set()
    changed = True
    while changed:
        changed = False
        for name, (names, attrs, direct) in facts.items():
            if name in reach:
                continue
            if direct or names & (conn_names | bare | reach) or attrs & pairs:
                reach.add(name)
                changed = True
    return reach


def drives(repo=REPO):
    """{tool filename: sorted list of the arms that admit it} for every member."""
    srcs = _tool_sources(repo)
    parsed = {f: _parse(t) for f, t in srcs.items()}
    arms = {f: set() for f in srcs}
    prose = {}
    for f, tree in parsed.items():
        if tree is None:
            # A superset cannot miss: an unparseable tool is counted, loudly, and the
            # manifest has to say something about it.
            arms[f].add("UNPARSEABLE")
            continue
        prose[f] = _prose_ids(tree)
        imps = _imports(tree)
        if any(m.split(".")[0] in CONNECTION_MODULES for m, _, _ in imps):
            arms[f].add("import")
        strings = _code_strings(tree, prose[f])
        if any(AETHER_METHOD.match(s) for s in strings):
            arms[f].add("protocol")
        _, attrs = _used_names(tree)
        if ("socket", "AF_UNIX") in attrs:
            arms[f].add("socket")

    stems = {f[:-3]: f for f in srcs}
    facts = {f: (_imports(t), _used_names(t), _def_facts(t, prose[f]))
             for f, t in parsed.items() if t is not None}
    drivers = {}          # tool -> driver callables it defines
    changed = True
    while changed:
        changed = False
        for f, (imps, (names, attrs), dfacts) in facts.items():
            conn = {b for m, n, b in imps if m.split(".")[0] in CONNECTION_MODULES}
            bare, pairs = set(), set()
            for m, n, b in imps:
                lender = stems.get(m)
                if lender is None or lender == f:
                    continue
                if n is None:
                    for d in drivers.get(lender, ()):
                        pairs.add((b, d))
                elif n in drivers.get(lender, ()):
                    bare.add(b)
            used_borrow = (bare & names) | {f"{a}.{d}" for a, d in pairs & attrs}
            if used_borrow and "borrow" not in arms[f]:
                arms[f].add("borrow")
                changed = True
            new = _driver_callables(dfacts, conn, (bare, pairs))
            if new != drivers.get(f, set()):
                drivers[f] = new
                changed = True

    members = {f for f, a in arms.items() if a}
    for f, tree in parsed.items():
        if tree is None:
            continue
        runs = argv_targets(tree, prose[f])
        if any((t in members and t != f) or t in EXTERNAL_DRIVERS for t in runs):
            arms[f].add("child")
    return {f: sorted(a) for f, a in arms.items() if a}


def population(repo=REPO):
    """Every tool that drives a headless emulator (see `drives`), sorted."""
    return sorted(drives(repo))


# The keepalive lane's own files, which must not act as reachability SOURCES.
#
# ⚠ MEASURED, NOT ANTICIPATED. Without this the advisory count moved 50 -> 47 the moment
# the lane's own tests were written, and 50 -> 43 when `tools/test_keepalive_surface.py`
# was committed: files that only MEASURE instruments were being counted as evidence that
# something else RUNS them. "The keepalive lane mentions this tool" can never be evidence
# that something ELSE runs it. The list stays EXPLICIT, and
# `test_keepalive_surface.test_every_keepalive_file_is_excluded_as_a_reachability_source`
# is what makes it keep up. (Under the executing-reference rule of 2026-09-25 a bare name
# no longer credits anything, so this set now guards only against the lane's own
# INVOCATIONS -- keepalive_lane.py spawning every wired row -- which is the case that
# matters: the lane running a tool must not read as something else running it.)
LANE_BOOKKEEPING = frozenset({
    "tools/keepalive_population.py",
    "tools/keepalive_lane.py",
    "tools/test_keepalive_lane.py",
    "tools/nightly_instrument_keepalive.sh",
    "tools/keepalive_surface.py",
    "tools/test_keepalive_surface.py",
})


def _sources(repo, files=None):
    """Every tracked .py/.sh that may act as a reachability source -- PATHS only.

    Nothing is read here. A file is read only once something reachable executes it, so a
    script parked under docs/ that nothing runs is never opened (the land-gate audit sees
    every read a test makes, and an unread file is also the honest statement: nothing
    that runs has looked at it).
    """
    return [rel for rel in (files if files is not None else _tracked_files(repo))
            if rel.endswith((".py", ".sh")) and rel not in LANE_BOOKKEEPING]


def exec_edges(rel, text):
    """{(target basename or module stem, kind)} this file EXECUTES."""
    if rel.endswith(".sh"):
        return {(t, "sh") for t in shell_targets(text)}
    tree = _parse(text)
    if tree is None:
        return set()
    edges = {(t, "argv") for t in argv_targets(tree)}
    for s in main_call_targets(tree):
        if isinstance(s, tuple):
            edges.add((s[1] + ".py", "dyn-main()"))
        else:
            edges.add((s + ".py", "main()"))
    return edges


def reach(repo=REPO, files=None):
    """{rel: (parent_rel, kind) or None} for everything an entry point EXECUTES."""
    sources = _sources(repo, files)
    by_base = {}
    for rel in sources:
        by_base.setdefault(os.path.basename(rel), []).append(rel)
    entries = [e for e in SCRIPT_ENTRY_POINTS if e in sources]
    entries += [rel for rel in sources
                if rel.startswith("tools/") and os.path.basename(rel).startswith("test_")]
    parent = {e: None for e in entries}
    stack = list(entries)
    while stack:
        cur = stack.pop()
        text = _read(repo, cur)
        if text is None:
            continue
        for target, kind in sorted(exec_edges(cur, text)):
            for rel in by_base.get(target, ()):
                if rel not in parent:
                    parent[rel] = (cur, kind)
                    stack.append(rel)
    return parent


def unreachable(repo=REPO):
    """(population, unreachable) as two sorted lists of bare filenames."""
    pop = population(repo)
    parent = reach(repo)
    dead = sorted(t for t in pop if "tools/" + t not in parent)
    return pop, dead


def main(argv=None):
    arms = drives()
    pop = sorted(arms)
    parent = reach()
    dead = [t for t in pop if "tools/" + t not in parent]
    verbose = "-v" in (sys.argv[1:] if argv is None else argv)
    print(f"emulator drivers (tools/*.py, not test_*, drive a headless emulator): {len(pop)}")
    arm_counts = {}
    for a in arms.values():
        for x in a:
            arm_counts[x] = arm_counts.get(x, 0) + 1
    print("  by arm (a tool can carry several): "
          + ", ".join(f"{k} {v}" for k, v in sorted(arm_counts.items())))
    print(f"EXECUTED from a real entry point:                                       "
          f"{len(pop) - len(dead)}")
    print(f"UNREACHABLE -- nothing executes these:                                  "
          f"{len(dead)}")
    for name in dead:
        print("   ", name)
    if verbose:
        print("\nwho executes each reachable driver (parent, kind):")
        for t in pop:
            p = parent.get("tools/" + t)
            if p:
                print(f"    {t:36s} {p[1]:7s} {p[0]}")
        print("\narms per driver:")
        for t in pop:
            print(f"    {t:36s} {','.join(arms[t])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
