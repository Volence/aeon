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

## Runner

`build.sh` sweeps `tools/test_*.py` with `python3 -m pytest "${TOOLS}" -q` build-fatally; this
file is collected by that sweep like every other `tools/test_*.py`.
"""
from __future__ import annotations

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


def test_the_walk_records_its_step(clean_env):
    root = suite_paths.suite_root()
    src = suite_paths.suite_root_source()
    assert str(root) in src or str(Path(suite_paths.__file__).resolve()) in src, src
    assert not any(name in src for name in ALL_SPELLINGS), (
        f"no variable was set, yet the record credits one: {src}")


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
