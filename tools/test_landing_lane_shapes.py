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

THE RUNNERS IT GRADES are `tools/landing_build.sh` (the pre-merge check every parcel runs
before it merges, and the merge-time home of the needs_build lane) and
`tools/nightly_effects_gates.sh` (the once-a-day backstop). The nightly must build every
shape the markers declare, and builds all four -- every shape build.sh can produce. The
landing check builds its one declared list, LANDING_SHAPES (three since CTRL-3b,
2026-09-14: demo normal left it under the hub's option A), so for it the rule is narrower
and still checked: whatever it leaves uncovered must be exactly inside the exemption its
needs_build lane derives from that same list, never an artifact of a shape it builds.

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
RUNNERS = ("landing_build.sh", "nightly_effects_gates.sh")

#: A `./build.sh` invocation. Deliberately NOT anchored to the start of a statement: the two
#: runners wrap it differently and an anchored pattern silently matched neither wrapper.
#: `tools/landing_build.sh` writes `run_shape s4.debug  env DEBUG=1 ./build.sh` and
#: `tools/nightly_effects_gates.sh` writes `if ! DEBUG=1 ./build.sh demo >> "$LOG" 2>&1; then`.
#: So: find `./build.sh` on a non-comment line, read DEBUG out of the text BEFORE it, and read
#: the game out of the first plain word AFTER it. Redirections and `;`/`then` terminate the
#: argument scan, which is why `>> "$LOG"` does not become a game name.
_INVOKE = re.compile(r"\./build\.sh(?P<rest>.*)$")
_WORD = re.compile(r"^[A-Za-z0-9_.-]+$")
#: A STRESS_* fixture prefix (`STRESS_EVICT=1 ./build.sh`): tools/nightly_effects_gates.sh
#: builds both fixture shapes after its canonical lanes. See `shapes_built_by`.
_STRESS_PREFIX = re.compile(r"\bSTRESS_[A-Z_]+=1\b")

#: tools/landing_build.sh's ONE declared shape list (CTRL-3b, 2026-09-14): its markers. The
#: A->B swap is the one line between them; tools/test_landing_build_trim.py makes it.
LANDING_BLOCK = ("# >>> LANDING_SHAPES", "# <<< LANDING_SHAPES")


def landing_shapes(script_text):
    """The shapes tools/landing_build.sh builds, read out of its LANDING_SHAPES block.

    A missing or doubled block, or anything but ONE non-empty `LANDING_SHAPES="..."` line in
    it, raises: a parse that quietly found nothing would grade the empty list, which covers
    nothing and would read as a green."""
    begin, end = LANDING_BLOCK
    if script_text.count(begin) != 1 or script_text.count(end) != 1:
        raise ValueError("expected exactly one %r / %r pair" % LANDING_BLOCK)
    body = script_text.split(begin, 1)[1].split(end, 1)[0]
    rows = [l.strip() for l in body.splitlines() if l.strip() and not l.strip().startswith("#")]
    m = re.fullmatch(r'LANDING_SHAPES="([A-Za-z0-9_. ]*)"', rows[0]) if len(rows) == 1 else None
    if not m or not m.group(1).split():
        raise ValueError('the LANDING_SHAPES block must hold exactly one non-empty '
                         'LANDING_SHAPES="..." line; it holds %r' % rows)
    return m.group(1).split()


def shape_game_debug(shape):
    """A landing shape (a ROM name) back to build.sh's (game, DEBUG): the inverse of
    `_artifacts_for`, and the rule tools/landing_build.sh's loop applies (`${shape%.debug}`,
    then s4 -> sonic4)."""
    debug = shape.endswith(".debug")
    base = shape[:-len(".debug")] if debug else shape
    return ("sonic4" if base == "s4" else base), debug


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
        m = _INVOKE.search(line)
        if not m:
            continue
        before = line[:m.start()]
        if _STRESS_PREFIX.search(before):
            # An off-canonical fixture shape (build.sh's STRESS_EVICT / STRESS_ART blocks
            # set ROM_NAME to s4.stress / s4.stressart and ignore DEBUG and the game). It
            # writes no canonical artifact, so it covers nothing; read as a plain build it
            # would claim s4.bin/s4.lst, which is the failure direction that matters.
            continue
        debug = bool(re.search(r"\bDEBUG=1\b", before))
        game = "sonic4"
        for tok in m.group("rest").split():
            if not _WORD.match(tok):
                break          # a redirection, a `;`, a quote: the argument list ended
            if tok.startswith("-"):
                continue       # an option, not the game selector
            game = tok
            break
        shapes.add((game, debug))
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

    if runner == "landing_build.sh":
        # CTRL-3b: the landing check builds its one declared list, LANDING_SHAPES, through a
        # loop, so its shapes are read from the list (landing_shapes raises on an unreadable
        # or empty one) rather than from `./build.sh` spellings in the text.
        listed = landing_shapes(text)
        shapes = {shape_game_debug(s) for s in listed}
    else:
        listed = None
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
    if listed is not None:
        # The landing check does not build every shape (option A), and its needs_build lane
        # is handed the list and EXEMPTS exactly the artifacts of the unbuilt shapes. So what
        # it leaves uncovered must be inside that derived exemption, and the exemption must
        # never include something the check builds. Anything else missing is still the
        # 2026-09-07 drift and still fails below.
        import conftest
        import needs_build_lane
        exempt = set(needs_build_lane.exempt_artifacts(listed, conftest.BUILD_ARTIFACTS))
        assert not exempt & built, (
            "the lane would exempt %s, which %s builds" % (sorted(exempt & built), path))
        missing = sorted(set(missing) - exempt)
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


def test_a_stress_fixture_invocation_claims_no_canonical_shape():
    """`STRESS_EVICT=1 ./build.sh` writes s4.stress.*, not s4.bin/s4.lst (build.sh's STRESS
    blocks fix ROM_NAME and ignore DEBUG and the game). The nightly spells both stress legs
    this way; read as a plain sonic4 build they would claim coverage of the release pair
    they do not write. The control line proves the parse still sees a real invocation."""
    text = (
        'STRESS_EVICT=1 ./build.sh >> "$STATE/stress_evict.log" 2>&1\n'
        'STRESS_ART=1 ./build.sh >> "$STATE/stress_art.log" 2>&1\n'
    )
    assert shapes_built_by(text) == set()
    control = text + 'if ! DEBUG=1 ./build.sh demo >> "$STATE/build.log" 2>&1; then\n'
    assert shapes_built_by(control) == {("demo", True)}


#: The one instrument the STRESS_EVICT fixture exists for, and the argv the nightly must run it
#: on (EVICT-WITNESS-WIRING, 2026-09-25). Spelled as the nightly spells it: a literal
#: invocation, like the build lines, so a reader and this parse see the same thing.
_EVICT_WITNESS = re.compile(
    r"^python3 tools/evict_witness\.py --rom s4\.stress\.bin --lst s4\.stress\.lst\b")
_EVICT_BUILD = re.compile(r"^STRESS_EVICT=1 \./build\.sh\b")
_ART_BUILD = re.compile(r"^STRESS_ART=1 \./build\.sh\b")


def _script_statements(script_text):
    """Non-comment statements, trailing ` # comment` stripped (see `shapes_built_by`)."""
    lines = []
    for raw in script_text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        lines.append(re.split(r"\s#", line, maxsplit=1)[0].strip())
    return lines


def _graded_leg(script_text, *, witness, build, gate_var, rc_var, before, before_what, what):
    """The six wiring checks shared by the two STRESS_* witness legs: [] means wired.

      1. exactly one witness invocation and exactly one build line for its shape;
      2. the invocation comes AFTER that build and BEFORE `before` (the witness belongs to
         the leg that wrote its artifact);
      3. it sits in the THEN branch of the innermost `if` around it, and that `if` tests the
         build's rc for 0 (`"$<gate_var>" = 0`), so a failed build never grades a stale
         artifact left from the night before;
      4. its exit is captured (`<rc_var>=$?` on one of the two statements after it);
      5. `<rc_var>` is in the worst-wins `for r in ...` fold;
      6. no branch assigns `<rc_var>=0` by hand, which would be a leg that reports green
         without having run.
    """
    lines = _script_statements(script_text)
    wit = [i for i, l in enumerate(lines) if witness.search(l)]
    bld = [i for i, l in enumerate(lines) if build.search(l)]
    if len(wit) != 1 or len(bld) != 1:
        return ["expected exactly one %s build and one witness invocation; found %d build(s), "
                "%d invocation(s)" % (what, len(bld), len(wit))]
    problems = []
    w, b = wit[0], bld[0]
    if not b < w:
        problems.append("the witness runs BEFORE the %s build that writes its artifact" % what)
    nxt = [i for i, l in enumerate(lines) if before.search(l)]
    if len(nxt) != 1 or not w < nxt[0]:
        problems.append("the witness is not before %s, i.e. it is outside its own leg"
                        % before_what)
    depth, enclosing, in_else = 0, None, False
    for i in range(w - 1, -1, -1):
        l = lines[i]
        if l == "fi" or l.endswith("; fi"):
            depth += 1
        elif re.match(r"^if\b", l):
            if depth == 0:
                enclosing = l
                break
            depth -= 1
        elif depth == 0 and (l == "else" or l.startswith("elif")):
            in_else = True
    if enclosing is None or in_else or not re.search(
            r'"\$%s"\s*=\s*0\b' % re.escape(gate_var), enclosing):
        problems.append("the witness is not in the THEN branch of `if [ \"$%s\" = 0 ]` "
                        "(innermost enclosing if: %r, in an else branch: %s)"
                        % (gate_var, enclosing, in_else))
    after = lines[w + 1:w + 3]
    if not any(re.fullmatch(r"%s=\$\?" % re.escape(rc_var), l) for l in after):
        problems.append("the witness's exit is not captured as `%s=$?` right after it "
                        "(next statements: %r)" % (rc_var, after))
    folds = [l for l in lines if re.match(r'^for r in .*"\$rc"', l)]
    if len(folds) != 1 or '"$%s"' % rc_var not in folds[0]:
        problems.append("%s is not in the (one) worst-wins fold: %r" % (rc_var, folds))
    if any(re.search(r"\b%s=0\b" % re.escape(rc_var), l) for l in lines):
        problems.append("a branch sets %s=0 by hand: a leg that can report green without "
                        "running" % rc_var)
    return problems


def stress_evict_witness_leg(script_text):
    """What is wrong with how a script grades the STRESS_EVICT artifact: [] means wired.

    Comment lines are stripped first, for the reason `shapes_built_by` strips them: the
    stress block's header DESCRIBES the witness leg at length, and prose that names it must
    not count as running it. The six checks are `_graded_leg`'s; this leg's witness must sit
    between the STRESS_EVICT build and the STRESS_ART build, gated on `rc_se`, captured and
    folded as `rc_ew`.
    """
    return _graded_leg(script_text, witness=_EVICT_WITNESS, build=_EVICT_BUILD,
                       gate_var="rc_se", rc_var="rc_ew", before=_ART_BUILD,
                       before_what="the (one) STRESS_ART build", what="STRESS_EVICT")


#: The STRESS_ART fixture's instrument (STRESSART-HALTS, 2026-09-26): its two DEBUG flight
#: legs, which halted on master for as long as the shape had built and nothing booted it.
_ART_WITNESS = re.compile(
    r"^python3 tools/stressart_legs_witness\.py --rom s4\.stressart\.bin "
    r"--lst s4\.stressart\.lst\b")
_TREE_AFTER = re.compile(r"^tree_after=")


def stress_art_witness_leg(script_text):
    """What is wrong with how a script grades the STRESS_ART artifact: [] means wired.

    `_graded_leg`'s six checks: the witness sits between the STRESS_ART build and the tree
    check that closes the stress block (`tree_after=`), gated on `rc_sa`, captured and folded
    as `rc_sw`.
    """
    return _graded_leg(script_text, witness=_ART_WITNESS, build=_ART_BUILD,
                       gate_var="rc_sa", rc_var="rc_sw", before=_TREE_AFTER,
                       before_what="the stress block's tree check (`tree_after=`)",
                       what="STRESS_ART")


def test_the_nightly_grades_the_stress_evict_artifact():
    """The STRESS_EVICT leg builds s4.stress.{bin,lst} AND runs the eviction witness on it.

    Until 2026-09-25 the nightly built that fixture and nothing read it (EVICT-WITNESS-WIRING
    in docs/DEFERRED_WORK.md): a green line about a ROM nobody booted. The leg's shape is
    checked here, in build.sh's pre-build lane, against the real script."""
    path = os.path.join(TOOLS, "nightly_effects_gates.sh")
    with open(path, encoding="utf-8") as fh:
        problems = stress_evict_witness_leg(fh.read())
    assert not problems, (
        "%s does not grade the STRESS_EVICT artifact:\n  - %s"
        % (path, "\n  - ".join(problems)))


_GOOD_LEG = (
    'STRESS_EVICT=1 ./build.sh >> "$STATE/stress_evict.log" 2>&1\n'
    'rc_se=$?\n'
    'if [ "$rc_se" = 0 ]; then\n'
    '    echo ok\n'
    'fi\n'
    'if [ "$rc_se" = 0 ]; then\n'
    '    python3 tools/evict_witness.py --rom s4.stress.bin --lst s4.stress.lst \\\n'
    '        >> "$STATE/stress_evict_witness.log" 2>&1\n'
    '    rc_ew=$?\n'
    'else\n'
    '    rc_ew=1\n'
    'fi\n'
    'STRESS_ART=1 ./build.sh >> "$STATE/stress_art.log" 2>&1\n'
    'for r in "$rc" "$rc_se" "$rc_ew" "$rc_sa"; do\n'
    'done\n'
)
_W = '    python3 tools/evict_witness.py --rom s4.stress.bin --lst s4.stress.lst \\\n'
_ART = 'STRESS_ART=1 ./build.sh >> "$STATE/stress_art.log" 2>&1\n'
_BROKEN_LEGS = {
    "absent": _GOOD_LEG.replace(_W, "    # " + _W.lstrip()),
    "ungated": _GOOD_LEG.replace('if [ "$rc_se" = 0 ]; then\n    python3',
                                 'if true; then\n    python3'),
    "else-branch": _GOOD_LEG.replace('if [ "$rc_se" = 0 ]; then\n    python3',
                                     'if [ "$rc_se" = 0 ]; then\n    true\nelse\n    python3'),
    "uncaptured": _GOOD_LEG.replace("    rc_ew=$?\n", "    true\n"),
    "unfolded": _GOOD_LEG.replace(' "$rc_ew"', ""),
    "hand-green": _GOOD_LEG.replace("    rc_ew=1\n", "    rc_ew=0\n"),
    "after-art": _GOOD_LEG.replace(_ART, "").replace("rc_se=$?\n", "rc_se=$?\n" + _ART),
}


def test_the_stress_evict_leg_parse_accepts_the_good_shape():
    assert stress_evict_witness_leg(_GOOD_LEG) == []


@pytest.mark.parametrize("name", sorted(_BROKEN_LEGS))
def test_the_stress_evict_leg_parse_reports_each_broken_shape(name):
    """Each control differs from the accepted shape by ONE clause, so a green on the real
    script is a statement about that script and not about a parse that always passes."""
    assert stress_evict_witness_leg(_BROKEN_LEGS[name]), (
        "the %r control was not reported" % name)


def test_the_nightly_grades_the_stress_art_artifact():
    """The STRESS_ART leg builds s4.stressart.{bin,lst} AND flies its two legs on it.

    From 2026-09-17 to 2026-09-26 the nightly built that fixture and nothing booted it, and
    both legs halted on master throughout (GPL-1, GPL-2 in docs/DEFERRED_WORK.md)."""
    path = os.path.join(TOOLS, "nightly_effects_gates.sh")
    with open(path, encoding="utf-8") as fh:
        problems = stress_art_witness_leg(fh.read())
    assert not problems, (
        "%s does not grade the STRESS_ART artifact:\n  - %s"
        % (path, "\n  - ".join(problems)))


_ART_BUILD_LINE = 'STRESS_ART=1 ./build.sh >> "$STATE/stress_art.log" 2>&1\n'
_AW = ('    python3 tools/stressart_legs_witness.py --rom s4.stressart.bin '
       '--lst s4.stressart.lst \\\n')
_TA = 'tree_after=$(git -C "$NIGHTLY" status --porcelain 2>&1)\n'
_GOOD_ART_LEG = (
    _ART_BUILD_LINE
    + 'rc_sa=$?\n'
    'if [ "$rc_sa" = 0 ]; then\n'
    + _AW
    + '        >> "$STATE/stress_art_legs.log" 2>&1\n'
    '    rc_sw=$?\n'
    'else\n'
    '    rc_sw=1\n'
    'fi\n'
    + _TA
    + 'for r in "$rc" "$rc_sa" "$rc_sw" "$rc_tree"; do\n'
    'done\n'
)
_BROKEN_ART_LEGS = {
    "absent": _GOOD_ART_LEG.replace(_AW, "    # " + _AW.lstrip()),
    "ungated": _GOOD_ART_LEG.replace('if [ "$rc_sa" = 0 ]; then\n    python3',
                                     'if true; then\n    python3'),
    "else-branch": _GOOD_ART_LEG.replace('if [ "$rc_sa" = 0 ]; then\n    python3',
                                         'if [ "$rc_sa" = 0 ]; then\n    true\nelse\n    python3'),
    "uncaptured": _GOOD_ART_LEG.replace("    rc_sw=$?\n", "    true\n"),
    "unfolded": _GOOD_ART_LEG.replace(' "$rc_sw"', ""),
    "hand-green": _GOOD_ART_LEG.replace("    rc_sw=1\n", "    rc_sw=0\n"),
    "after-tree-check": _GOOD_ART_LEG.replace(_TA, "").replace("rc_sa=$?\n", "rc_sa=$?\n" + _TA),
    "before-build": _GOOD_ART_LEG.replace(_ART_BUILD_LINE, "").replace(_TA, _ART_BUILD_LINE + _TA),
}


def test_the_stress_art_leg_parse_accepts_the_good_shape():
    assert stress_art_witness_leg(_GOOD_ART_LEG) == []


@pytest.mark.parametrize("name", sorted(_BROKEN_ART_LEGS))
def test_the_stress_art_leg_parse_reports_each_broken_shape(name):
    """One clause off the accepted shape each, as for the STRESS_EVICT leg."""
    assert _BROKEN_ART_LEGS[name] != _GOOD_ART_LEG, "the %r control mutated nothing" % name
    assert stress_art_witness_leg(_BROKEN_ART_LEGS[name]), (
        "the %r control was not reported" % name)
