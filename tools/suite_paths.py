"""Where the OTHER Empyrean repos live — resolved, never baked.

## The defect this exists to remove (SUITE-HOME-PATHS)

52 files under `tools/ engine/ games/ build.sh` spelled the suite root absolutely
literally. Every single one of them named something under ONE directory — the suite root, the
parent of this checkout — so a single resolver replaces the whole class.

**The baked path is only half the defect.** A hardcoded path that makes a script *refuse* on
another machine is merely unportable; one that makes it *pass* is a gate reporting on a file it
never opened. So this module deliberately offers TWO shapes and they are not interchangeable:

  * `suite_path(...)` / `repo_path(...)` — resolution only. Returns a Path whether or not it
    exists. Use when the caller itself checks, or when the value is a fixture, an argparse
    default the user may override, or a string that is never opened.
  * `require_suite_path(...)` / `require_repo_path(...)` / `add_client_path()` — **resolution
    plus existence, raising a named error AT THE CALL SITE.** Use everywhere the value is about
    to be opened, imported from, or executed.

`os.environ.get("X") or "<default>"` is the construct this module replaces and must not come
back: a defaulting accessor is the one shape incapable of announcing its own failure.

## How the suite root is found, and how to stop it

The variable is **`EMPYREAN_SUITE_ROOT`** — the suite-level spelling the hub ratified in
empyrean `contract/SUITE_PATHS.md` (2026-09-02, commit `4e8e865b`): a suite-level fact must
not carry one tool's brand. aeon's own pre-contract spelling, `AEON_SUITE_ROOT`, is accepted
as a transitional alias (`SUITE_ROOT_ENV_ALIASES`); the contract lets a resolver accept the
old spellings during the transition *"but must document [the ratified name] as the name"*, so
when the alias is what answered, the resolver says so on stderr and names the spelling to
switch to. Set `EMPYREAN_SUITE_ROOT`; do not set the alias in anything new.

Whichever spelling is set WINS ABSOLUTELY — no walk is attempted, and a value pointing at a
directory that is not a suite root is a hard error rather than a silent fall-back to the real
tree (the contract's "set but wrong is a hard error at that step", which is this module's own
semantic). Both spellings set and disagreeing is the same defect — two answers to one question
is evidence of a wrong environment — and is refused naming both variables and both values.
That override is the mitigation for the hazard `docs/DEFERRED_WORK.md` records under
SUITE-HOME-PATHS: *"a helper that climbs parents looking for a marker LOOKS converted and still
opens the real tree, because the walk succeeds from wherever the test happens to run. An
override pointed at an absent directory does not stop it."* Here it does stop it, and that is
the only reason a walk is acceptable at all.

Without the override, the walk climbs this file's parents for the first directory holding ALL
of `_SUITE_MARKERS` (the contract's step 3, "a marker walk to the directory containing the
sibling repos"). It must be a walk and not a fixed parent count because this repo is
routinely checked out as a git worktree under `.claude/worktrees/<name>/`, which is three
levels deeper than the main checkout. `git rev-parse --git-common-dir` would also find it, but
that costs a subprocess in ~40 harness processes and fails outside a checkout; the walk is
pure and needs neither. (`--show-toplevel` is never acceptable: it answers with the worktree.)

Failure to resolve raises `SuiteRootNotFound`. It never returns a guess. `suite_root_source()`
says which step answered — the contract asks every resolver to be able to — and the refusal
messages carry it so the fix is readable from the message.

## How a sibling CHECKOUT is found (contract step 1), and which siblings get it

The contract's precedence has a step the suite root does not cover: **the explicit checkout
variable, `<TOOL>_DIR`, is consulted FIRST**, before `EMPYREAN_SUITE_ROOT` and before the walk.
The hub's note on aeon's first landing is the reason this paragraph exists: *"a resolver that
reaches a sibling checkout through the suite root alone still owes step 1."* So `empyrean_dir()`
reads **`EMPYREAN_DIR`** first; set-but-wrong (not a directory, or a directory that is not an
empyrean checkout by `_EMPYREAN_MARKERS`) is a hard error naming the variable and the path,
never a fall-through to the suite root — the same discipline as `_override()`. Unset, the
checkout is `suite_root()/empyrean`, so steps 2-4 are inherited unchanged. `empyrean_dir_source()`
says which step answered, in the same way `suite_root_source()` does, and `client_path()` is
resolved through it.

`harness_path()` — oracle-old's `linux-port/harness` — is **LIVE, not legacy**:
`effects_gates.py` (the nightly effects gate) and the probes that spawn the C++ `oracle_gui`
import it, so the contract's step 6 ("oracle-old's harness only if it is still meant to run")
applies and it is still meant to run. It does NOT yet get a step-1 variable, because the
contract's table names `ORACLE_DIR` for the Rust oracle — a different checkout — and no
spelling for `oracle-old`; a name invented here would be an eleventh spelling of the kind the
contract exists to end. Until the hub spells it, `harness_path()` resolves through the suite
root alone (steps 2-4), and that gap is booked in `docs/DEFERRED_WORK.md` under
HOME-PATHS-OUTWARD.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

__all__ = [
    "SuitePathError", "SuiteRootNotFound", "CheckoutNotFound", "MissingSuitePath",
    "SUITE_ROOT_ENV", "SUITE_ROOT_ENV_ALIASES", "EMPYREAN_DIR_ENV", "REPO_ROOT",
    "suite_root", "suite_root_source",
    "empyrean_dir", "empyrean_dir_source",
    "suite_path", "require_suite_path", "repo_path", "require_repo_path",
    "client_path", "add_client_path", "harness_path",
]

#: Explicit override. Set it to relocate the suite, or to point a poison run at an empty tree.
#: The spelling is the hub's (empyrean `contract/SUITE_PATHS.md`): THIS is the name.
SUITE_ROOT_ENV = "EMPYREAN_SUITE_ROOT"

#: Transitional aliases, accepted but announced. `AEON_SUITE_ROOT` was aeon's own spelling
#: before the contract; the contract's cost line for aeon is exactly this tuple. Retire it once
#: nothing in the suite sets it.
SUITE_ROOT_ENV_ALIASES = ("AEON_SUITE_ROOT",)

#: Every sibling that must be present for a directory to BE the suite root. `empyrean` is the
#: suite contract repo and `aeon` this engine; a directory holding both is the suite root by
#: definition (see `../CLAUDE.md`, "Projects").
_SUITE_MARKERS = ("aeon", "empyrean")

#: Contract step 1 for the empyrean checkout: the `<TOOL>_DIR` spelling from the contract's
#: own table. Consulted BEFORE the suite root; set-but-wrong is a hard error at this step.
EMPYREAN_DIR_ENV = "EMPYREAN_DIR"

#: The directory name empyrean's checkout has under the suite root (contract step 2: "the
#: suite root joined with the repo's directory name").
_EMPYREAN_DIRNAME = "empyrean"

#: What makes a directory BE the empyrean checkout: its two stable top-level trees — the
#: suite contract (`contract/SUITE_PATHS.md` lives there) and the Aether clients this module
#: hands out. A directory missing either is "not the named checkout", the contract's
#: set-but-wrong case.
_EMPYREAN_MARKERS = ("contract", "clients")


class SuitePathError(RuntimeError):
    """Base for every failure in this module."""


class SuiteRootNotFound(SuitePathError):
    """The suite root could not be resolved at all."""


class CheckoutNotFound(SuitePathError):
    """A sibling checkout (`<TOOL>_DIR` or `<suite root>/<tool>`) is absent or is not that repo."""


class MissingSuitePath(SuitePathError):
    """The suite root resolved, but the requested target under it does not exist."""


#: The checkout this file belongs to — `<checkout>/tools/suite_paths.py`, so parents[1]. Fixed
#: by this module's own location, not discovered: in a worktree this is the WORKTREE, which is
#: what a probe reading "this tree's ROM" wants.
REPO_ROOT = Path(__file__).resolve().parents[1]

_suite_root: Path | None = None
#: Which step answered, as prose: `<VAR>=<value>` (with the alias note when an alias answered)
#: or the walk's starting point. Set beside `_suite_root`, read by `suite_root_source()`.
_suite_root_source: str | None = None

_empyrean_dir: Path | None = None
#: Which step answered for the empyrean checkout: `EMPYREAN_DIR=<value>` (step 1) or the suite
#: root's own provenance (steps 2-3). Set beside `_empyrean_dir`, read by `empyrean_dir_source()`.
_empyrean_dir_source: str | None = None


def _forget() -> None:
    """Drop the memos. For tests that change the environment between resolutions."""
    global _suite_root, _suite_root_source, _empyrean_dir, _empyrean_dir_source
    _suite_root = None
    _suite_root_source = None
    _empyrean_dir = None
    _empyrean_dir_source = None


def _is_suite_root(p: Path) -> bool:
    return all((p / m).is_dir() for m in _SUITE_MARKERS)


def _override() -> tuple[str, str] | None:
    """`(variable, value)` for the spelling that answers, or None when nothing is set.

    Precedence is the ratified name, then the aliases in order. Two spellings set to
    different directories is set-but-wrong — refused naming both, because the next step
    would hide the wrong environment that produced them.
    """
    found = [(name, os.environ[name])
             for name in (SUITE_ROOT_ENV, *SUITE_ROOT_ENV_ALIASES)
             if os.environ.get(name)]
    if not found:
        return None
    first_name, first_value = found[0]
    first = Path(first_value).expanduser().resolve()
    for name, value in found[1:]:
        if Path(value).expanduser().resolve() != first:
            raise SuiteRootNotFound(
                f"{first_name}={first_value!r} and {name}={value!r} disagree — the suite root "
                f"is one directory. Unset {name} (a transitional alias) and set only "
                f"{SUITE_ROOT_ENV}.")
    return first_name, first_value


def suite_root() -> Path:
    """The directory holding aeon and its peer repos. Raises rather than guessing."""
    global _suite_root, _suite_root_source
    if _suite_root is not None:
        return _suite_root

    override = _override()
    if override:
        name, value = override
        p = Path(value).expanduser()
        # The override is absolute law: if it is wrong we stop, we do NOT fall back to the
        # walk. A fall-back here would re-open the real tree during exactly the poison runs
        # this variable exists to make possible.
        if not p.is_dir():
            raise SuiteRootNotFound(
                f"{name}={value!r} is not a directory (looked for a suite root holding "
                + ", ".join(f"{m}/" for m in _SUITE_MARKERS) + ")")
        missing = [m for m in _SUITE_MARKERS if not (p / m).is_dir()]
        if missing:
            raise SuiteRootNotFound(
                f"{name}={value!r} is not a suite root: missing "
                + ", ".join(f"{m}/" for m in missing))
        source = f"{name}={value}"
        if name != SUITE_ROOT_ENV:
            # The contract lets the alias answer during the transition but the resolver must
            # document the ratified name as THE name — so say so, once, where a human reads.
            source += f" (transitional alias; the name is {SUITE_ROOT_ENV})"
            sys.stderr.write(
                f"suite_paths: {name} is a transitional alias — set {SUITE_ROOT_ENV} "
                f"instead (empyrean contract/SUITE_PATHS.md)\n")
        _suite_root, _suite_root_source = p.resolve(), source
        return _suite_root

    here = Path(__file__).resolve()
    for cand in here.parents:
        if _is_suite_root(cand):
            _suite_root, _suite_root_source = cand, f"marker walk up from {here}"
            return _suite_root

    raise SuiteRootNotFound(
        f"no suite root above {here} — no ancestor holds all of "
        + ", ".join(f"{m}/" for m in _SUITE_MARKERS)
        + f". Set {SUITE_ROOT_ENV} to the directory containing the Empyrean repos.")


def suite_root_source() -> str:
    """Which step produced `suite_root()`, for announcements and refusal messages.

    The contract asks every resolver to say which step answered before work is done against
    the path: this is that answer. Resolves first if nothing has yet.
    """
    suite_root()
    assert _suite_root_source is not None
    return _suite_root_source


def _is_empyrean_checkout(p: Path) -> bool:
    return all((p / m).is_dir() for m in _EMPYREAN_MARKERS)


def empyrean_dir() -> Path:
    """The empyrean checkout: `EMPYREAN_DIR` first (contract step 1), else under the suite root.

    Raises `CheckoutNotFound` rather than guessing. A set `EMPYREAN_DIR` that is not an
    empyrean checkout is refused HERE, naming the variable and the path; the suite root is
    never consulted behind a set-but-wrong value, because the next step would hide the wrong
    environment that produced it.
    """
    global _empyrean_dir, _empyrean_dir_source
    if _empyrean_dir is not None:
        return _empyrean_dir

    looked_for = "an empyrean checkout holding " + ", ".join(f"{m}/" for m in _EMPYREAN_MARKERS)
    value = os.environ.get(EMPYREAN_DIR_ENV)
    if value:
        p = Path(value).expanduser()
        if not p.is_dir():
            raise CheckoutNotFound(
                f"{EMPYREAN_DIR_ENV}={value!r} is not a directory (looked for {looked_for})")
        missing = [m for m in _EMPYREAN_MARKERS if not (p / m).is_dir()]
        if missing:
            raise CheckoutNotFound(
                f"{EMPYREAN_DIR_ENV}={value!r} is not an empyrean checkout: missing "
                + ", ".join(f"{m}/" for m in missing))
        _empyrean_dir, _empyrean_dir_source = p.resolve(), f"{EMPYREAN_DIR_ENV}={value}"
        return _empyrean_dir

    # Steps 2-4 are the suite root's own precedence; this is "the suite root joined with the
    # repo's directory name". A suite root that resolved but holds no empyrean checkout is
    # refused naming both the variable that would have answered first and where it looked.
    root = suite_root()
    p = root / _EMPYREAN_DIRNAME
    if not _is_empyrean_checkout(p):
        raise CheckoutNotFound(
            f"{p} is not an empyrean checkout (looked for {looked_for}) — {EMPYREAN_DIR_ENV} "
            f"is unset, suite root is {root}, from {suite_root_source()}. Set "
            f"{EMPYREAN_DIR_ENV} to the empyrean checkout.")
    _empyrean_dir = p
    _empyrean_dir_source = f"{EMPYREAN_DIR_ENV} unset; under the suite root, from {suite_root_source()}"
    return _empyrean_dir


def empyrean_dir_source() -> str:
    """Which step produced `empyrean_dir()`. Resolves first if nothing has yet."""
    empyrean_dir()
    assert _empyrean_dir_source is not None
    return _empyrean_dir_source


def suite_path(*parts: str | os.PathLike) -> Path:
    """Resolve a path under the suite root. Does NOT check that it exists."""
    return suite_root().joinpath(*parts)


def require_suite_path(*parts: str | os.PathLike, what: str = "") -> Path:
    """Resolve a path under the suite root and REFUSE, by name, if it is absent."""
    p = suite_path(*parts)
    if not p.exists():
        raise MissingSuitePath(
            f"required suite path is absent: {p}"
            + (f" ({what})" if what else "")
            + f" — suite root is {suite_root()}, from {suite_root_source()}")
    return p


def repo_path(*parts: str | os.PathLike) -> Path:
    """Resolve a path inside THIS checkout of aeon. Does NOT check that it exists."""
    return REPO_ROOT.joinpath(*parts)


def require_repo_path(*parts: str | os.PathLike, what: str = "") -> Path:
    """Resolve a path inside this checkout and REFUSE, by name, if it is absent."""
    p = repo_path(*parts)
    if not p.exists():
        raise MissingSuitePath(
            f"required path in this checkout is absent: {p}"
            + (f" ({what})" if what else "")
            + f" — checkout root is {REPO_ROOT}")
    return p


def client_path() -> Path:
    """The Aether Python client package directory, required to exist.

    Resolved through `empyrean_dir()` — `EMPYREAN_DIR` first, then the suite root — so a
    refusal here says which step produced the checkout it looked under.
    """
    p = empyrean_dir() / "clients" / "python"
    if not p.exists():
        raise MissingSuitePath(
            f"required suite path is absent: {p} (the Aether Python client (`import aether`))"
            f" — empyrean checkout is {empyrean_dir()}, from {empyrean_dir_source()}")
    return p


def harness_path() -> Path:
    """The C++ `oracle_gui` launcher package in oracle-old, required to exist. LIVE.

    `effects_gates.py` (the nightly effects gate) and the probes that spawn `oracle_gui` put
    this on `sys.path` to `from launcher import headless_emulator`, so it is still meant to
    run. It resolves through the suite root ALONE (contract steps 2-4) and not through a
    step-1 `<TOOL>_DIR` variable, because the contract names none for oracle-old
    (`ORACLE_DIR` is the Rust oracle, a different checkout) and inventing one here would be
    the drift the contract exists to end. Open with the hub; see the module docstring.
    """
    return require_suite_path("oracle-old", "linux-port", "harness",
                              what="the oracle_gui launcher (`import launcher`)")


def add_client_path() -> Path:
    """Put the Aether Python client on `sys.path` — refusing loudly if it is not there.

    Replaces the absolute `sys.path.insert` of `empyrean/clients/python`, repeated in
    31 places and whose failure mode was an `ImportError: No module named 'aether'` several
    frames from the cause.
    """
    p = client_path()
    s = str(p)
    if s not in sys.path:
        sys.path.insert(0, s)
    return p


if __name__ == "__main__":  # the announce: "where does this think the suite is, and why?"
    # build.sh runs this ahead of its gate lanes so every build log carries the resolved
    # paths and the step that produced each (contract: "say which step answered"). A
    # refusal is one named line on stderr and exit 1, which `set -e` turns build-fatal.
    print(f"repo      {REPO_ROOT}")
    try:
        print(f"suite     {suite_root()}")
        print(f"  from    {suite_root_source()}")
        print(f"empyrean  {empyrean_dir()}")
        print(f"  from    {empyrean_dir_source()}")
    except SuitePathError as e:
        sys.stdout.flush()
        sys.stderr.write(f"suite_paths: REFUSED — {e}\n")
        sys.exit(1)
