"""A multi-shape runner must build every artifact the `needs_build` markers declare.

WHY THIS FILE EXISTS (LS-1c, 2026-09-10), and it is a scar rather than a precaution.

`tools/needs_build_lane.py` grades the marked lane and calls a DEFERRAL "could not run":
in a caller that builds every shape the marked tests declare, a deferral means a build did
not write what it was supposed to. That doctrine is correct and it silently assumed
something nobody checked — that the caller's shape list actually covers the markers.

It stopped being true. `tools/nightly_effects_gates.sh` builds three shapes, a list chosen
on 2026-09-06 when four tests carried the marker. On 2026-09-07 `tools/test_deb2_appendix.py`
parametrized `@pytest.mark.needs_build` over all four build shapes, adding `demo.bin` and
`demo.lst` — the PLAIN demo pair, which no nightly shape builds. Measured from the
nightly's own state log, not inferred:

    2026-09-08T04:29:29  COULD NOT RUN: needs_build lane (exit 2) at 4557b939
    2026-09-09T04:30:11  COULD NOT RUN: needs_build lane (exit 2) at 37e543c2
    2026-09-10T04:31:39  COULD NOT RUN: needs_build lane (exit 2) at d3b01f07

    tools/test_deb2_appendix.py::...[demo.bin]  (demo.bin (absent), demo.lst (absent))
    1 deferred.  ->  COULD NOT RUN: 1 marked test(s) DEFERRED.

while the nightly's own header still asserted "every artifact the marked tests declare is
built by this script". The marker population grew from 4 decorators to 10 underneath a
hand-written shape list, and nothing in the tree could see it. The lane went red for a
reason that had nothing to do with the code under test, which is how a gate gets ignored.

SO THE COVERAGE CLAIM IS DERIVED AND CHECKED, NEVER PINNED. This file reads the markers
that are in the tree right now, reads the `build.sh` invocations each multi-shape runner
actually contains, maps shape -> artifacts by build.sh's own rule, and asserts the second
covers the first. There is no expected count anywhere in it: a number copied from a
neighbouring pin is exactly what went stale.

IT RUNS IN build.sh's PRE-BUILD LANE — `python3 -m pytest tools -q -m "not needs_build"`,
build-fatal, in every shape of every parcel's build. It reads no build artifact and must
never carry the marker itself; it asks a source question and answers it from source.

LOUD ON UNMEASURABLE. A runner script that is missing, or that this file cannot find a
single `build.sh` invocation in, is a FAILURE naming the file and the pattern — never a
skip and never a pass. A parse that quietly finds nothing would report full coverage of
the empty set, which is the vacuous shape this whole lane exists to refuse.
"""

import ast
import os
import re

import pytest

AEON = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(AEON, "tools")
MARKER = "needs_build"

#: The multi-shape runners: scripts that build more than one shape back to back and then
#: grade the marked lane over the result. Each must cover every declared artifact.
RUNNERS = ("merge_lane.sh", "nightly_effects_gates.sh")

#: A `[DEBUG=1 ]./build.sh[ <game>]` invocation. Anchored at the start of a statement so a
#: mention inside a longer command is not mistaken for one, and applied only to lines that
#: are not comments.
_INVOKE = re.compile(
    r"(?:^|[;&|]\s*|\bif\s+!\s+|\bif\s+|\bthen\s+|\belse\s+)"
    r"(?P<env>(?:[A-Za-z_][A-Za-z0-9_]*=\S*\s+)*)"
    r"\./build\.sh"
    r"(?P<args>(?:\s+[A-Za-z0-9_.-]+)*)"
)


def _artifacts_for(game, debug):
    """The .bin/.lst pair a shape writes, by build.sh's own rule.

    build.sh:130  if [[ "$GAME" == "sonic4" ]]; then ROM_NAME="s4"; else ROM_NAME="$GAME"; fi
    build.sh:133  if [[ "${DEBUG:-0}" == "1" ]]; then ROM_NAME="${ROM_NAME}.debug"; fi
    and the artifacts are "${ROM_NAME}.bin" / "${ROM_NAME}.lst".
    """
    rom = "s4" if game == "sonic4" else game
    if debug:
        rom += ".debug"
    return {rom + ".bin", rom + ".lst"}


def shapes_built_by(script_text):
    """Every (game, debug) shape a runner script invokes build.sh for.

    Comment lines are stripped FIRST. Both runners discuss build.sh at length in their
    headers — the nightly's says "Do NOT 'fix' this by adding a second game's build to
    build.sh" — and counting prose as an invocation would let a script claim coverage it
    does not have, which is the failure direction that matters.
    """
    shapes = set()
    for raw in script_text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        # Trim a trailing comment, but only one introduced by whitespace-# outside quotes;
        # the runners have none inside quotes, and a false trim can only LOSE an
        # invocation, i.e. fail closed.
        line = re.split(r"\s#", line, maxsplit=1)[0]
        for m in _INVOKE.finditer(line):
            debug = bool(re.search(r"\bDEBUG=1\b", m.group("env")))
            args = [a for a in m.group("args").split() if not a.startswith("-")]
            shapes.add((args[0] if args else "sonic4", debug))
    return shapes


def declared_artifacts():
    """The union of every artifact named by every `@pytest.mark.needs_build` in tools/.

    Parsed with `ast`, not grepped, for the reason `needs_build_lane.decorator_count` is:
    `tools/test_needs_build_lane.py` builds synthetic fixtures out of triple-quoted strings
    whose lines begin with the decorator at column 0, and a grep counts those. Here a grep
    would be worse than a miscount — it would import the fixtures' fake artifact names into
    the coverage requirement and demand runners build files that do not exist.

    Only literal string arguments are collected. A marker whose artifact is computed (the
    deb2 one is: `pytest.mark.needs_build(s[0], s[1])` over a module-level SHAPES list) is
    resolved by evaluating the enclosing module far enough to read that list — see
    `_literal_args`.
    """
    out = set()
    for name in sorted(os.listdir(TOOLS)):
        if not name.startswith("test_") or not name.endswith(".py"):
            continue
        path = os.path.join(TOOLS, name)
        with open(path, encoding="utf-8") as fh:
            src = fh.read()
        try:
            tree = ast.parse(src)
        except SyntaxError:
            # A broken module is pytest's own collection error to report, not this file's.
            continue
        consts = _module_constants(tree)
        for node in ast.walk(tree):
            for dec in getattr(node, "decorator_list", []):
                out |= _literal_args(dec, consts)
    return out


def _module_constants(tree):
    """Module-level names bound to a literal, for markers built out of a table.

    `ast.literal_eval` on the assignment's value covers the one shape in the tree that
    matters — `SHAPES = [("s4.bin", "s4.lst", "sonic4"), ...]` — without executing
    anything. A name that is not a literal is simply absent, and a marker referring to it
    contributes nothing rather than a wrong guess.
    """
    consts = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if not isinstance(target, ast.Name):
                continue
            try:
                consts[target.id] = ast.literal_eval(node.value)
            except (ValueError, SyntaxError):
                pass
    return consts


def _literal_args(dec, consts):
    """The artifact names a single decorator expression declares.

    Handles the two forms in the tree: a direct `@pytest.mark.needs_build("a", "b")`, and
    `pytest.param(*s, marks=pytest.mark.needs_build(s[0], s[1])) for s in SHAPES` inside a
    `@pytest.mark.parametrize`. For the second the comprehension's iterable is resolved
    through `consts` and every row's referenced elements are taken.
    """
    names = set()
    for call in [n for n in ast.walk(dec) if isinstance(n, ast.Call)]:
        target = call.func
        if not (isinstance(target, ast.Attribute) and target.attr == MARKER):
            continue
        for arg in call.args:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                names.add(arg.value)
                continue
            # `s[0]` where `s` is the comprehension variable over a literal table.
            if isinstance(arg, ast.Subscript) and isinstance(arg.value, ast.Name):
                rows = _comprehension_rows(dec, arg.value.id, consts)
                idx = arg.slice
                if rows is None or not isinstance(idx, ast.Constant):
                    continue
                for row in rows:
                    try:
                        val = row[idx.value]
                    except (IndexError, KeyError, TypeError):
                        continue
                    if isinstance(val, str):
                        names.add(val)
    return names


def _comprehension_rows(dec, var, consts):
    """The rows a comprehension variable `var` iterates, if they are a module literal."""
    for comp in [n for n in ast.walk(dec) if isinstance(n, (ast.ListComp, ast.GeneratorExp))]:
        for gen in comp.generators:
            if isinstance(gen.target, ast.Name) and gen.target.id == var:
                if isinstance(gen.iter, ast.Name) and gen.iter.id in consts:
                    return consts[gen.iter.id]
                try:
                    return ast.literal_eval(gen.iter)
                except (ValueError, SyntaxError):
                    return None
    return None


# --------------------------------------------------------------------------- the guard

def test_the_marker_set_is_readable_at_all():
    """The population this file grades must be non-empty, or every claim below is vacuous.

    An empty declared set makes every runner trivially "cover" it. That is the exact
    failure mode this file exists to refuse, so it is asserted first and separately: a
    parse that silently returns nothing must be a red test and not a green one.
    """
    declared = declared_artifacts()
    assert declared, (
        "no @pytest.mark.%s artifact names could be parsed out of %s. Either every marker "
        "was deleted — which silently restores the pre-LS-1 state — or the parse in this "
        "file no longer matches how the markers are written. Both are failures: an empty "
        "declared set makes the coverage assertions below true of everything." % (MARKER, TOOLS))


@pytest.mark.parametrize("runner", RUNNERS)
def test_a_multi_shape_runner_builds_every_declared_artifact(runner):
    """The coverage claim each multi-shape runner makes about itself, checked.

    This is the assertion that would have caught the 2026-09-07 drift on the day it landed
    instead of three nights later, and it is the reason the shape list in a runner is no
    longer a comment anyone has to remember to update.
    """
    path = os.path.join(TOOLS, runner)
    assert os.path.isfile(path), (
        "%s is named in RUNNERS but is not on disk. This file cannot check the coverage of "
        "a runner it cannot read, and reporting that as a pass is the unmeasurable-rendered-"
        "green shape. If the runner was deliberately removed, remove it from RUNNERS in the "
        "same change." % path)
    with open(path, encoding="utf-8") as fh:
        text = fh.read()

    shapes = shapes_built_by(text)
    assert shapes, (
        "%s contains no parseable `./build.sh` invocation outside its comments. Either it "
        "stopped being a multi-shape runner, or it invokes build.sh in a form this file's "
        "pattern does not match (%s). A parse that finds nothing would report full coverage "
        "of the empty set, so it is a FAILURE here and never a skip." % (path, _INVOKE.pattern))

    built = set()
    for game, debug in shapes:
        built |= _artifacts_for(game, debug)
    declared = declared_artifacts()
    missing = sorted(declared - built)
    assert not missing, (
        "%s builds %s, writing %s — but the @pytest.mark.%s markers in %s declare %s, so "
        "tools/needs_build_lane.py run by this script will DEFER on %s and report COULD NOT "
        "RUN.\n"
        "  A deferral in a multi-shape runner is not an expected skip: that runner's whole "
        "claim is that it builds every artifact the marked lane declares.\n"
        "  This is the 2026-09-07 drift repeating — the marker population grew under a "
        "hand-written shape list and the nightly went red for three nights for a reason "
        "unrelated to the code under test.\n"
        "  Fix it in the RUNNER (build the missing shape), not by narrowing a marker."
        % (path, sorted(shapes), sorted(built), MARKER, TOOLS, sorted(declared), missing))


def test_declared_artifacts_are_all_known_build_artifacts():
    """Every declared name must be one of conftest's BUILD_ARTIFACTS.

    The two lists are maintained independently — conftest's drives the DEFERRED/FAILURE
    axis and the unmarked-skip heuristic, the markers drive what a runner must build — and
    a name in one and not the other means a marker nothing can ever satisfy, or an
    artifact the axis cannot reason about. Either way the lane's verdict stops meaning
    what it says.
    """
    import conftest  # the sibling in tools/, already on pytest's path for this directory

    unknown = sorted(declared_artifacts() - set(conftest.BUILD_ARTIFACTS))
    assert not unknown, (
        "these artifacts are declared by a @pytest.mark.%s marker but are not in "
        "tools/conftest.py's BUILD_ARTIFACTS %s: %s. No build.sh shape writes them, so the "
        "marked test can only ever DEFER — and conftest's unmarked-skip heuristic cannot "
        "see them either. Add them to BUILD_ARTIFACTS, or fix the marker."
        % (MARKER, list(conftest.BUILD_ARTIFACTS), unknown))
