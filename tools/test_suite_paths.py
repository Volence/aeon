#!/usr/bin/env python3
"""The suite-root resolver honours the hub's spelling, its transitional alias, and nothing else.

## What this pins (empyrean `contract/SUITE_PATHS.md`, ruled 2026-09-02, commit 4e8e865b)

The suite-root variable is `EMPYREAN_SUITE_ROOT`. aeon's own pre-contract spelling
(`AEON_SUITE_ROOT`) is a transitional alias: *"a resolver may accept them during the transition
but must document [the ratified name] as the name."* A variable that is **set but wrong** is a
hard error at that step, never a null that lets the walk run. Refusals name the variable(s)
consulted and the path(s) tried.

Contract step 1 (R9, 2026-09-02): the explicit checkout variable `EMPYREAN_DIR` is consulted
BEFORE the suite root when the empyrean checkout is wanted (`client_path()`). Set and right, it
answers and the provenance says so; set and wrong, the refusal names `EMPYREAN_DIR` and the
path and the suite root is NOT consulted behind it; unset, the suite root answers and the
provenance says which of ITS steps did.

Every expectation below is derived from `suite_paths`'s own constants (`SUITE_ROOT_ENV`,
`SUITE_ROOT_ENV_ALIASES`, `_SUITE_MARKERS`, `EMPYREAN_DIR_ENV`, `_EMPYREAN_MARKERS`,
`_EMPYREAN_DIRNAME`), so a rename in the module reddens exactly the row that pins the
contract, not a row that copied a string. The two literals are the ratified names themselves,
because those ARE the contract and drifting from them is the defect.

## The walk's beds (empyrean `contract/SUITE_PATHS.md` at `7d0a279a`, the step-3 observability bar)

The contract's step-3 clause is explicit that a bed which merely *exists* proves nothing: *"the
test executes the worktree's copy of the resolver and proves it did"*, *"the bed must not be the
ONLY case: the step-3 row proves the derivation in BOTH configurations"*, *"the bed FAILS LOUDLY
when it cannot demonstrate the disagreement"*, and — the discriminator — *"only the returned
step-source naming the worktree path proves the resolver was there... a bed whose returned source
names the main checkout fails regardless of its pair."*

Python is a language WITH runtime module loading, so this file takes the contract's first arm
(*"loading the worktree's copy is one way and parameterising the anchor is another"*): `_plant_resolver()`
copies `suite_paths.py` into the bed and **imports that copy**, so the walk's anchor —
`Path(__file__)`, which is what the resolver actually derives from — is the bed's own path and not
this checkout's. A bed that only changed directory would be provably inert here, because the walk
never reads the cwd. Each planted copy is a fresh module object with its own memos, so the
per-process caching in `_suite_root` cannot leak one bed's answer into another's.

The contract's *"the other route, and where its reason stops"* names the exact gap these rows close:
aeon's walk *"works from a worktree because aeon nests worktrees under `.claude/worktrees/<name>/`,
three levels deeper and still inside the suite root, so the walk lands on the same directory from
both depths... That reason generalises exactly as far as the nesting does. A worktree outside the
suite tree... gives a marker walk nothing to find."* So there are three beds: the two nested depths
(`_LAYOUTS`, which must AGREE) and the outside-the-suite bed (which must REFUSE by name).

The "wrong method" this walk exists instead of is a **fixed parent count** — the module docstring's
own reason for the walk (*"It must be a walk and not a fixed parent count because this repo is
routinely checked out as a git worktree under `.claude/worktrees/<name>/`"*). `_FIXED_PARENT_COUNT`
is derived from the main-checkout layout, so the disagreement the rows assert is the module's own
stated reason, measured.

## Runner

`build.sh` sweeps `tools/test_*.py` with `python3 -m pytest "${TOOLS}" -q` build-fatally; this
file is collected by that sweep like every other `tools/test_*.py`.
"""
from __future__ import annotations

import importlib.util
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))  # tools/, for suite_paths
import suite_paths  # noqa: E402
from suite_paths import (  # noqa: E402
    EMPYREAN_DIR_ENV, SUITE_ROOT_ENV, SUITE_ROOT_ENV_ALIASES,
    CheckoutNotFound, MissingSuitePath, SuiteRootNotFound,
)

#: The contract's rulings. The only literals in this file, on purpose: the module must agree
#: with the hub, and the way it stops agreeing is a rename here that nothing else would notice.
RATIFIED_NAME = "EMPYREAN_SUITE_ROOT"
RATIFIED_CHECKOUT_NAME = "EMPYREAN_DIR"

ALL_SPELLINGS = (SUITE_ROOT_ENV, *SUITE_ROOT_ENV_ALIASES)


@pytest.fixture
def clean_env(monkeypatch):
    """No suite-root or checkout spelling set, and the module's memos forgotten, before and after."""
    for name in (*ALL_SPELLINGS, EMPYREAN_DIR_ENV):
        monkeypatch.delenv(name, raising=False)
    suite_paths._forget()
    yield monkeypatch
    suite_paths._forget()


def _make_suite(tmp_path: Path, name: str) -> Path:
    """A directory that IS a suite root by the module's own definition: every marker present."""
    root = tmp_path / name
    for marker in suite_paths._SUITE_MARKERS:
        (root / marker).mkdir(parents=True)
    return root


#: The two layouts this repo's checkout ACTUALLY has, written once as data so the bed builder and
#: the in-place production row read the same definition. `<repo>` is the checkout directory (which
#: is also a suite marker, so a bed's suite root holds it by construction); `<wt>` is a worktree's
#: own name. Straight from `suite_paths`'s own docstring: a worktree lives under
#: `.claude/worktrees/<name>/`, "three levels deeper than the main checkout".
_LAYOUTS: dict[str, tuple[str, ...]] = {
    "main-checkout": ("<repo>", "tools", "suite_paths.py"),
    "nested-worktree": ("<repo>", ".claude", "worktrees", "<wt>", "tools", "suite_paths.py"),
}

#: What the wildcards become when a bed is BUILT. `<repo>` must be a suite marker or the bed would
#: not be a suite root at all; taking it from the module's own tuple keeps that true after a rename.
_WILDCARDS = {"<repo>": suite_paths._SUITE_MARKERS[0], "<wt>": "wt"}

#: The WRONG method, derived: the fixed parent count that is correct for the main checkout. From
#: `<root>/<repo>/tools/suite_paths.py` the suite root is `parents[2]`; the module's docstring says
#: in so many words that a fixed count is what the walk exists instead of.
_FIXED_PARENT_COUNT = len(_LAYOUTS["main-checkout"]) - 1

#: The real resolver, whose bytes every bed is a copy of.
_RESOLVER_SOURCE = Path(suite_paths.__file__).resolve()

assert len({len(shape) for shape in _LAYOUTS.values()}) == len(_LAYOUTS), (
    "the layouts must be genuinely different depths or the parameterisation proves nothing")


def _bed_relpath(layout: str) -> tuple[str, ...]:
    """A layout with its wildcards resolved — where the resolver copy goes under a bed's root."""
    return tuple(_WILDCARDS.get(part, part) for part in _LAYOUTS[layout])


def _match_layout(rel_parts: tuple[str, ...]) -> str | None:
    """Which layout a resolver path (relative to its suite root) has, or None for an unknown one."""
    for name, shape in _LAYOUTS.items():
        if len(shape) == len(rel_parts) and all(
                s.startswith("<") or s == r for s, r in zip(shape, rel_parts)):
            return name
    return None


_planted = 0


def _plant_resolver(at: Path):
    """Copy the resolver to `at` and IMPORT THAT COPY, so the walk's anchor is the bed's path.

    The contract's step-3 bar in one function: the resolver derives from `Path(__file__)`, so a
    bed that only set a cwd would be inert. Loading the copy is the arm the contract names for a
    language with runtime module loading. Each copy is a fresh module object, so its `_suite_root`
    memo is its own and no bed can be answered by another's cached value.
    """
    global _planted
    _planted += 1
    at.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(_RESOLVER_SOURCE, at)
    spec = importlib.util.spec_from_file_location(f"suite_paths_bed_{_planted}", at)
    assert spec is not None and spec.loader is not None, at
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    # The bed is the subject or the row means nothing: the loaded copy must be the planted file.
    assert Path(mod.__file__).resolve() == at.resolve(), (
        f"the bed loaded {mod.__file__} and not the planted copy at {at}")
    assert mod is not suite_paths, "the bed re-used this checkout's module object"
    return mod


def _make_empyrean(where: Path) -> Path:
    """Make `where` an empyrean checkout by the module's own definition, with the client inside."""
    for marker in suite_paths._EMPYREAN_MARKERS:
        (where / marker).mkdir(parents=True, exist_ok=True)
    (where / "clients" / "python").mkdir(parents=True, exist_ok=True)
    return where


def test_the_ratified_name_is_the_documented_one():
    """The primary spelling is the hub's, not tool-branded, and the alias list does not
    re-list it (an alias equal to the name would make the both-set check compare a value
    with itself)."""
    assert SUITE_ROOT_ENV == RATIFIED_NAME
    assert not SUITE_ROOT_ENV.startswith("AEON_"), "a suite-level fact must not carry one tool's brand"
    assert SUITE_ROOT_ENV not in SUITE_ROOT_ENV_ALIASES
    assert SUITE_ROOT_ENV_ALIASES, "the transition keeps aeon's old spelling accepted"
    # Documented as the name: the module's own prose names the ratified spelling.
    assert RATIFIED_NAME in (suite_paths.__doc__ or "")


def test_the_ratified_spelling_is_honoured(clean_env, tmp_path):
    root = _make_suite(tmp_path, "suite")
    clean_env.setenv(SUITE_ROOT_ENV, str(root))
    assert suite_paths.suite_root() == root.resolve()
    src = suite_paths.suite_root_source()
    assert SUITE_ROOT_ENV in src and str(root) in src, src


@pytest.mark.parametrize("alias", SUITE_ROOT_ENV_ALIASES)
def test_an_alias_spelling_is_honoured_and_the_ratified_name_is_announced(clean_env, tmp_path, alias, capsys):
    root = _make_suite(tmp_path, "suite")
    clean_env.setenv(alias, str(root))
    assert suite_paths.suite_root() == root.resolve()
    src = suite_paths.suite_root_source()
    # "must document <the ratified name> as the name": the record says which spelling
    # answered AND which spelling it should have been.
    assert alias in src and str(root) in src and SUITE_ROOT_ENV in src, src
    err = capsys.readouterr().err
    assert alias in err and SUITE_ROOT_ENV in err, (
        f"the alias was used silently; stderr carried: {err!r}")


@pytest.mark.parametrize("alias", SUITE_ROOT_ENV_ALIASES)
def test_both_set_and_disagreeing_is_refused_naming_both(clean_env, tmp_path, alias):
    a = _make_suite(tmp_path, "suite_a")
    b = _make_suite(tmp_path, "suite_b")
    clean_env.setenv(SUITE_ROOT_ENV, str(a))
    clean_env.setenv(alias, str(b))
    with pytest.raises(SuiteRootNotFound) as ei:
        suite_paths.suite_root()
    msg = str(ei.value)
    for needle in (SUITE_ROOT_ENV, alias, str(a), str(b)):
        assert needle in msg, f"refusal does not name {needle!r}: {msg}"


@pytest.mark.parametrize("alias", SUITE_ROOT_ENV_ALIASES)
def test_both_set_and_equal_resolves_under_the_ratified_name(clean_env, tmp_path, alias, capsys):
    root = _make_suite(tmp_path, "suite")
    clean_env.setenv(SUITE_ROOT_ENV, str(root))
    clean_env.setenv(alias, str(root))
    assert suite_paths.suite_root() == root.resolve()
    src = suite_paths.suite_root_source()
    assert src.startswith(SUITE_ROOT_ENV), f"the ratified spelling should have answered: {src}"
    assert capsys.readouterr().err == "", "nothing to announce when the ratified name answered"


@pytest.mark.parametrize("name", ALL_SPELLINGS)
def test_set_but_wrong_is_a_hard_error_at_that_step_not_a_fallthrough(clean_env, tmp_path, name):
    """Control first: with nothing set, the walk from this file DOES find a suite root, so a
    fall-through would have succeeded. Then the same walk must NOT be reached when the
    variable is set to a directory that is not a suite root."""
    walked = suite_paths.suite_root()
    assert suite_paths._is_suite_root(walked)
    suite_paths._forget()

    not_a_suite = tmp_path / "empty"
    not_a_suite.mkdir()
    clean_env.setenv(name, str(not_a_suite))
    with pytest.raises(SuiteRootNotFound) as ei:
        suite_paths.suite_root()
    msg = str(ei.value)
    assert name in msg and str(not_a_suite) in msg, msg
    for marker in suite_paths._SUITE_MARKERS:
        assert f"{marker}/" in msg, f"refusal does not say what was looked for: {msg}"

    suite_paths._forget()
    absent = tmp_path / "does-not-exist"
    clean_env.setenv(name, str(absent))
    with pytest.raises(SuiteRootNotFound) as ei:
        suite_paths.suite_root()
    assert name in str(ei.value) and str(absent) in str(ei.value), str(ei.value)


def test_the_walk_refusal_names_the_variable_and_where_it_looked(clean_env):
    clean_env.setattr(suite_paths, "_is_suite_root", lambda p: False)
    with pytest.raises(SuiteRootNotFound) as ei:
        suite_paths.suite_root()
    msg = str(ei.value)
    assert SUITE_ROOT_ENV in msg, f"the fix is not readable from the message: {msg}"
    assert str(Path(suite_paths.__file__).resolve()) in msg, msg
    for marker in suite_paths._SUITE_MARKERS:
        assert f"{marker}/" in msg, msg


def test_a_missing_target_refusal_says_which_step_answered(clean_env, tmp_path):
    root = _make_suite(tmp_path, "suite")
    clean_env.setenv(SUITE_ROOT_ENV, str(root))
    with pytest.raises(MissingSuitePath) as ei:
        suite_paths.require_suite_path("nothing-here", what="a probe's donor")
    msg = str(ei.value)
    assert str(root / "nothing-here") in msg and "a probe's donor" in msg, msg
    assert suite_paths.suite_root_source() in msg, (
        f"the refusal does not say which step produced the root: {msg}")


def test_the_walk_records_its_step_in_the_layout_this_run_actually_has(clean_env):
    """The production arm of the two-configuration rule — and it must NOT be a tautology.

    Contract: *"the row exercises the constructed bed for the disagreement AND the real main
    checkout for the shape production actually uses"*. This is that second half: the real
    resolver, in place, un-parameterised. The row that used to sit here asserted only that the
    walk succeeded, which it is DEFINED to do from anywhere inside the suite root, so it could
    not fail and did not choose its depth. What is checkable in place is the thing that is not
    guaranteed: the answer's position relative to this file must be one of the layouts this
    repo actually has (`_LAYOUTS`), and the run must SAY which one it ran from. An unrecognised
    layout is a loud failure naming what was seen, not a pass — a walk that landed somewhere
    else entirely would otherwise read exactly like a walk that worked.
    """
    here = Path(suite_paths.__file__).resolve()
    root = suite_paths.suite_root()
    src = suite_paths.suite_root_source()

    assert not any(name in src for name in ALL_SPELLINGS), (
        f"no variable was set, yet the record credits one: {src}")
    assert str(here) in src, (
        f"the record does not name the file the walk started from: {src}")

    rel = here.relative_to(root).parts
    layout = _match_layout(rel)
    assert layout is not None, (
        f"UNMEASURABLE: the walk answered {root}, putting this resolver at {'/'.join(rel)}, which "
        f"matches none of the layouts this repo has ({dict(_LAYOUTS)}). Either the walk climbed "
        f"past the suite root or the checkout was relocated; both are the defect, not the bed.")
    # Say which configuration this run was: a green log and an absent run must not look alike.
    print(f"suite_root walk ran from the {layout} layout: {here} -> {root} ({src})")
    assert suite_paths._is_suite_root(root)


# --- step 3: the marker walk, from beds the TEST chooses -------------------------------------

@pytest.mark.parametrize("layout", sorted(_LAYOUTS))
def test_the_walk_answers_the_bed_it_stands_in_at_every_depth(clean_env, tmp_path, layout):
    """The walk is exercised from a depth the test picked, against a suite root the test built.

    Three things are asserted and none of them is the walk merely succeeding:

      1. the answer is the BED's suite root, not this checkout's;
      2. the returned step-source names the BED's copy of the resolver and NOT this checkout's —
         the contract's only discriminator against an inert bed (*"a bed whose returned source
         names the main checkout fails regardless of its pair"*);
      3. the wrong method (a fixed parent count) is measured on this bed and the pair is asserted
         in whichever direction the bed's geometry makes true, loudly, rather than assumed.
    """
    root = _make_suite(tmp_path, "suite")
    planted_at = root.joinpath(*_bed_relpath(layout))
    bed = _plant_resolver(planted_at)

    assert bed.suite_root() == root.resolve(), (
        f"the walk from {planted_at} answered {bed.suite_root()}, not the bed's root {root}")

    src = bed.suite_root_source()
    assert str(planted_at.resolve()) in src, (
        f"the returned source does not name the bed's resolver — the row measured nothing: {src}")
    assert str(_RESOLVER_SOURCE) not in src, (
        f"the bed's answer credits THIS checkout's resolver, so the bed was inert: {src}")
    assert not any(name in src for name in ALL_SPELLINGS), (
        f"no variable was set, yet the record credits one: {src}")

    # The depth is the test's, not the runner's: the planted copy sits exactly where asked.
    assert planted_at.resolve().relative_to(root.resolve()).parts == _bed_relpath(layout)

    wrong = planted_at.resolve().parents[_FIXED_PARENT_COUNT]
    if len(_LAYOUTS[layout]) == len(_LAYOUTS["main-checkout"]):
        # The shallow bed is the configuration the fixed count was calibrated for; it CANNOT
        # discriminate, and saying so out loud is the point of running it (contract: the row
        # proves the derivation in both configurations, and the second one is production's).
        assert wrong == root.resolve(), (
            f"UNMEASURABLE: the fixed-parent-count method was expected to be right by accident "
            f"on the {layout} bed and instead gave {wrong} for a root of {root} — the bed's "
            f"geometry is not what _LAYOUTS says, so neither arm of this row means anything.")
    else:
        assert wrong != root.resolve(), (
            f"UNMEASURABLE: the {layout} bed was built so the fixed-parent-count method would be "
            f"WRONG there, and it landed on the right answer ({wrong}) anyway. The bed has stopped "
            f"discriminating; fix the bed rather than trusting this row.")
        print(f"disagreement at the {layout} bed: fixed-count={wrong}  walk={bed.suite_root()}")


def test_the_walk_outside_the_suite_tree_refuses_by_its_own_name(clean_env, tmp_path):
    """The case the nesting argument does not cover, and no row reached before.

    `suite_paths`'s docstring declines `git rev-parse` on the grounds that the walk is pure and
    finds the root from either nested depth. The contract's *"the other route, and where its
    reason stops"* names the limit: *"A worktree outside the suite tree... gives a marker walk
    nothing to find"*. So this bed is a fresh temp directory holding ONLY the worktree, with no
    suite markers in any ancestor, and the walk must refuse — by the resolver's own named
    refusal, not by an incidental exception from somewhere else.
    """
    bed_root = tmp_path / "isolated"
    planted_at = bed_root.joinpath(*_bed_relpath("nested-worktree"))
    bed = _plant_resolver(planted_at)
    here = planted_at.resolve()

    # Loud precondition: if any ancestor happened to be a suite root, this bed is the vacuous
    # case wearing the right name, and it must fail rather than pass.
    offenders = [str(p) for p in here.parents if bed._is_suite_root(p)]
    assert not offenders, (
        f"UNMEASURABLE: the outside-the-suite bed has a suite root above it ({offenders}), so the "
        f"walk has something to find and the refusal this row asserts would not be reachable.")

    # On THIS bed the refusal is the whole assertion, and two opposite outcomes both look like
    # "it raised": the walk reaching the end of the parents having found nothing, and the test
    # dying before the walk ran at all (a vanished directory, an OSError, an ImportError). So the
    # type is pinned exactly — to the BED's class object, which a copy of the module defines
    # afresh, so even this checkout's `SuiteRootNotFound` would not satisfy it.
    with pytest.raises(bed.SuiteRootNotFound) as ei:
        bed.suite_root()
    assert type(ei.value) is bed.SuiteRootNotFound, (
        f"a {type(ei.value).__name__} is not the resolver's named refusal: {ei.value}")
    assert type(ei.value) is not SuiteRootNotFound, (
        "the bed raised THIS checkout's exception class, so the bed was not the subject")
    msg = str(ei.value)

    # ...and on wording unique to the WALK's refusal. The module raises `SuiteRootNotFound` from
    # four places; the other three are the override arm ("...disagree", "is not a directory",
    # "is not a suite root: missing"), each of which leads with a `<VAR>=<value>` and none of
    # which can produce "no suite root above". Asserting the leading phrase AND the absence of
    # the override arms' phrases means a message that could be either one fails this row.
    assert "no suite root above" in msg, f"not the walk's own refusal: {msg}"
    assert str(here) in msg, f"the refusal does not say where it looked: {msg}"
    assert SUITE_ROOT_ENV in msg, f"the fix is not readable from the message: {msg}"
    for marker in bed._SUITE_MARKERS:
        assert f"{marker}/" in msg, f"the refusal does not say what it looked for: {msg}"
    for override_arm in ("is not a directory", "is not a suite root", "disagree"):
        assert override_arm not in msg, (
            f"the walk's refusal reads like the set-but-wrong arm's ({override_arm!r}): {msg}")

    # And the consumers refuse behind it rather than reaching a guess.
    with pytest.raises(bed.SuiteRootNotFound):
        bed.suite_path("anything")
    with pytest.raises(bed.SuiteRootNotFound):
        bed.suite_root_source()

    # POSITIVE CONTROL, in the same bed and the same process: the refusal above must mean "the
    # walk climbed to the end and found no markers", not "the walk never ran". Complete the
    # marker set at `bed_root` — which already holds `<repo>/` — and the SAME call must now
    # succeed and answer `bed_root`. A walk that had died early could not start passing because
    # a directory appeared four levels above it.
    bed._forget()
    for marker in bed._SUITE_MARKERS:
        (bed_root / marker).mkdir(parents=True, exist_ok=True)
    assert bed.suite_root() == bed_root.resolve(), (
        "the walk did not find a suite root that was placed on the path it claimed to climb, so "
        "the refusal above is not evidence the walk reached the end of the parents")
    assert str(here) in bed.suite_root_source(), bed.suite_root_source()


def test_the_step_source_is_a_returned_value_naming_the_bed_not_a_printed_line(clean_env, tmp_path, capsys):
    """Two beds in one run: each source names its OWN resolver, and nothing was printed.

    The contract distinguishes a returned step-source from a memoised stderr announce and rules
    that only the returned value can prove where the resolver stood. `suite_root_source()` is
    already a returned value, so aeon owes the other half: proving it is bed-specific rather
    than a per-process constant. Two beds at different depths, resolved in one process, whose
    sources name different files is that proof; a memoised or module-global source would make
    the two identical.
    """
    shallow_root = _make_suite(tmp_path / "a", "suite")
    deep_root = _make_suite(tmp_path / "b", "suite")
    shallow_at = shallow_root.joinpath(*_bed_relpath("main-checkout"))
    deep_at = deep_root.joinpath(*_bed_relpath("nested-worktree"))
    shallow = _plant_resolver(shallow_at)
    deep = _plant_resolver(deep_at)
    capsys.readouterr()  # discard anything the plants emitted; the assertion is about resolving

    shallow_src = shallow.suite_root_source()
    deep_src = deep.suite_root_source()

    assert shallow_src != deep_src, (
        f"both beds report the same step source, so it is not the bed's: {shallow_src!r}")
    assert str(shallow_at.resolve()) in shallow_src and str(deep_at.resolve()) not in shallow_src, shallow_src
    assert str(deep_at.resolve()) in deep_src and str(shallow_at.resolve()) not in deep_src, deep_src
    assert str(_RESOLVER_SOURCE) not in shallow_src + deep_src, (
        "a bed's source names this checkout's resolver: the beds were inert")
    assert shallow.suite_root() == shallow_root.resolve()
    assert deep.suite_root() == deep_root.resolve()

    out, err = capsys.readouterr()
    assert (out, err) == ("", ""), (
        f"the step source must be a returned value, not a printed line: stdout={out!r} stderr={err!r}")


# --- contract step 1: the explicit checkout variable, for the empyrean checkout ---------------

def test_the_checkout_name_is_the_contracts():
    """`<TOOL>_DIR` from the contract's table, documented as the name, and the step-2 join
    uses the same directory name the suite-root walk requires (so step 2 can never answer
    with a directory the walk would not have accepted as evidence of a suite root)."""
    assert EMPYREAN_DIR_ENV == RATIFIED_CHECKOUT_NAME
    assert EMPYREAN_DIR_ENV in (suite_paths.__doc__ or "")
    assert suite_paths._EMPYREAN_MARKERS, "a checkout check with no markers accepts any directory"
    assert suite_paths._EMPYREAN_DIRNAME in suite_paths._SUITE_MARKERS


def test_checkout_var_set_and_right_answers_before_the_suite_root(clean_env, tmp_path):
    """Step 1 outranks step 2: with a suite root ALSO set and holding its own empyrean
    checkout, the explicit variable is the one that answers, and the provenance says so."""
    suite = _make_suite(tmp_path, "suite")
    _make_empyrean(suite / suite_paths._EMPYREAN_DIRNAME)
    explicit = _make_empyrean(tmp_path / "elsewhere" / "empyrean-checkout")
    clean_env.setenv(SUITE_ROOT_ENV, str(suite))
    clean_env.setenv(EMPYREAN_DIR_ENV, str(explicit))

    assert suite_paths.empyrean_dir() == explicit.resolve()
    src = suite_paths.empyrean_dir_source()
    assert EMPYREAN_DIR_ENV in src and str(explicit) in src, src
    assert str(suite) not in src, f"step 1 answered, yet the record credits the suite root: {src}"
    assert suite_paths.client_path() == explicit.resolve() / "clients" / "python"


@pytest.mark.parametrize("shape", ("empty-directory", "absent"))
def test_checkout_var_set_but_wrong_is_refused_at_that_step_not_a_fallthrough(clean_env, tmp_path, shape):
    """Control first: with the variable unset, the suite root DOES hold an empyrean checkout,
    so a fall-through would have succeeded. Then, with the variable set to something that is
    not an empyrean checkout, the refusal must name the variable and the path — and the suite
    root must not have been consulted at all (sabotaged to fail the test if it is)."""
    suite = _make_suite(tmp_path, "suite")
    _make_empyrean(suite / suite_paths._EMPYREAN_DIRNAME)
    clean_env.setenv(SUITE_ROOT_ENV, str(suite))
    assert suite_paths.empyrean_dir() == (suite / suite_paths._EMPYREAN_DIRNAME).resolve()
    suite_paths._forget()

    wrong = tmp_path / shape
    if shape == "empty-directory":
        wrong.mkdir()
    clean_env.setenv(EMPYREAN_DIR_ENV, str(wrong))
    clean_env.setattr(suite_paths, "suite_root",
                      lambda: pytest.fail(f"{EMPYREAN_DIR_ENV} was set and wrong, yet the "
                                          "resolver fell through to the suite root"))
    with pytest.raises(CheckoutNotFound) as ei:
        suite_paths.empyrean_dir()
    msg = str(ei.value)
    assert EMPYREAN_DIR_ENV in msg and str(wrong) in msg, msg
    for marker in suite_paths._EMPYREAN_MARKERS:
        assert f"{marker}/" in msg, f"refusal does not say what was looked for: {msg}"
    # And the consumer sees the same refusal, not something that walked past it.
    with pytest.raises(CheckoutNotFound):
        suite_paths.client_path()


def test_checkout_var_unset_the_suite_root_answers_and_says_which_step(clean_env, tmp_path):
    suite = _make_suite(tmp_path, "suite")
    _make_empyrean(suite / suite_paths._EMPYREAN_DIRNAME)
    clean_env.setenv(SUITE_ROOT_ENV, str(suite))

    assert suite_paths.empyrean_dir() == (suite / suite_paths._EMPYREAN_DIRNAME).resolve()
    src = suite_paths.empyrean_dir_source()
    assert f"{EMPYREAN_DIR_ENV}=" not in src, f"nothing was set, yet the record credits it: {src}"
    assert EMPYREAN_DIR_ENV in src, f"the record should say the step-1 variable was unset: {src}"
    assert suite_paths.suite_root_source() in src, (
        f"the record does not say which suite-root step answered: {src}")
    assert suite_paths.client_path() == (suite / suite_paths._EMPYREAN_DIRNAME / "clients" / "python").resolve()


def test_checkout_var_unset_and_the_suite_root_holds_no_checkout_is_refused_by_name(clean_env, tmp_path):
    """The "present but empty" poison: `<suite>/empyrean/` exists (so the suite root resolves)
    but is not an empyrean checkout. The refusal names the path tried, the variable that would
    have answered first, and the suite-root step that produced the path."""
    suite = _make_suite(tmp_path, "suite")  # empyrean/ present, empty
    clean_env.setenv(SUITE_ROOT_ENV, str(suite))
    with pytest.raises(CheckoutNotFound) as ei:
        suite_paths.empyrean_dir()
    msg = str(ei.value)
    assert str(suite / suite_paths._EMPYREAN_DIRNAME) in msg, msg
    assert EMPYREAN_DIR_ENV in msg and suite_paths.suite_root_source() in msg, msg
    for marker in suite_paths._EMPYREAN_MARKERS:
        assert f"{marker}/" in msg, msg


def test_a_checkout_without_the_client_is_refused_naming_the_checkout_step(clean_env, tmp_path):
    explicit = tmp_path / "empyrean-no-client"
    for marker in suite_paths._EMPYREAN_MARKERS:
        (explicit / marker).mkdir(parents=True)
    clean_env.setenv(EMPYREAN_DIR_ENV, str(explicit))
    with pytest.raises(MissingSuitePath) as ei:
        suite_paths.client_path()
    msg = str(ei.value)
    assert str(explicit / "clients" / "python") in msg, msg
    assert suite_paths.empyrean_dir_source() in msg, (
        f"the refusal does not say which step produced the checkout: {msg}")


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
