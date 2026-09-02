#!/usr/bin/env python3
"""The suite-root resolver honours the hub's spelling, its transitional alias, and nothing else.

## What this pins (empyrean `contract/SUITE_PATHS.md`, ruled 2026-09-02, commit 4e8e865b)

The suite-root variable is `EMPYREAN_SUITE_ROOT`. aeon's own pre-contract spelling
(`AEON_SUITE_ROOT`) is a transitional alias: *"a resolver may accept them during the transition
but must document [the ratified name] as the name."* A variable that is **set but wrong** is a
hard error at that step, never a null that lets the walk run. Refusals name the variable(s)
consulted and the path(s) tried.

Every expectation below is derived from `suite_paths`'s own constants (`SUITE_ROOT_ENV`,
`SUITE_ROOT_ENV_ALIASES`, `_SUITE_MARKERS`), so a rename in the module reddens exactly the row
that pins the contract, not a row that copied a string. The one literal is the ratified name
itself, because that IS the contract and drifting from it is the defect.

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
    SUITE_ROOT_ENV, SUITE_ROOT_ENV_ALIASES, MissingSuitePath, SuiteRootNotFound,
)

#: The contract's ruling. The single literal in this file, on purpose: the module must agree
#: with the hub, and the way it stops agreeing is a rename here that nothing else would notice.
RATIFIED_NAME = "EMPYREAN_SUITE_ROOT"

ALL_SPELLINGS = (SUITE_ROOT_ENV, *SUITE_ROOT_ENV_ALIASES)


@pytest.fixture
def clean_env(monkeypatch):
    """No suite-root spelling set, and the module's memo forgotten, before and after."""
    for name in ALL_SPELLINGS:
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


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
