#!/usr/bin/env python3
"""extern_guard_reachability — the per-commit runner the `extern()`-guard family never had
(LS-16c, 2026-09-08).

WHAT THIS GATES, IN ONE SENTENCE: every `extern()`-bearing `ensure` in `engine/` and
`games/` lives in a module that at least one of the four shipped shapes actually reaches,
and every LinkAssert those shapes lower is actually DECIDED.

WHY IT DID NOT EXIST BEFORE, AND WHAT CHANGED
---------------------------------------------
LS-16 (2026-09-06) found 135 `extern()`-bearing `ensure` sites with no negative fixture,
and established WHY: such a site is lowered to a `LinkAssert`, decided after
`resolve_layout`, and a poison module cannot falsify one (a poison contributes zero bytes
by construction, so it cannot move a reservation or an equate). `tools/extern_guard_census.py`
answered the question ONCE, by hand, by negating each guard's own condition — a
tree-MUTATING sweep, ~37 s per game, deliberately not in `build.sh`.

That left the family with a census but no RUNNER, which is the state LS-15/LS-16 describe
as the pathology: a one-time proof decays silently. The specific decay is not hypothetical
— it is the census's own single miss. `engine/system/z80_init.emp:73` is a correct, live
guard that sonic4 stopped evaluating when its module became `when = "sound_off"`; nothing
said so, and the drift it guards was caught nightly at best (LS-16a).

`sigil build --check` (sigil d90a297c, installed 2026-09-07) is what makes a per-commit
answer affordable and non-mutating. It decides every `ensure` and every LinkAssert against
final post-relaxation placement, writes no ROM, and — the part this file is built on —
REPORTS ITS OWN COVERAGE:

    checked: demo plain: 2128 ensure verdict(s) at comptime, 274 LinkAssert(s) decided at
    link, 0 LinkAssert(s) inapplicable (extern not defined in this link, allowlisted)

and, under `SIGIL_WARNINGS=full`, names every module whose guards it did NOT evaluate:

    ./engine/debug/sound_debug.emp:46:1: warning: [module.unreachable] module
    `engine.debug.sound_debug` is outside this profile's `use` closure, so its 2 `ensure`
    guard(s) are never evaluated for this target ...

THE THREE SILENT-DEATH ROADS, AND WHICH TEST CLOSES EACH
--------------------------------------------------------
  (H1) a guard's module leaves EVERY shape's `use` closure -> the guard is a comment.
       Closed by `test_every_extern_guard_file_is_reachable_in_some_shape`. This is the
       z80_init class, and it is the one that actually happened.
  (H3) a guard is reached but its extern is not defined in this link, so sigil files it
       `inapplicable ... allowlisted` and decides nothing. Closed by
       `test_no_linkassert_is_inapplicable`.
  (H4) a shape stops being checkable at all (a bootstrap gap, a crash, a renamed flag) and
       a reader takes silence for green. Closed by `test_every_shape_reported`, which
       fails LOUD rather than skipping — "couldn't measure" is never green here.

WHAT THIS DOES **NOT** GATE, said plainly because it is easy to misread as covered:
  (H2) a guard whose condition is rewritten so that it can no longer be false. Deciding a
       LinkAssert proves it was EVALUATED, not that it is FALSIFIABLE. Only negating the
       condition answers that, which is `tools/extern_guard_census.py` and stays a
       hand-run mutating sweep. LS-16c is left open on exactly this remainder.
  Per-guard identity. sigil reports COUNTS plus unreachable MODULES, so the finest
  granularity available per-commit is the FILE. A file reachable in some shape passes here
  even if one guard inside it were somehow skipped; nothing in the toolchain today can
  distinguish that, and claiming otherwise would be the vacuity this file exists to end.

TWO AUTHORITIES, DELIBERATELY
-----------------------------
The site set comes from `tools/extern_guard_census.py`'s `collect()` — IMPORTED, not
re-implemented, so the census and this gate can never disagree about what the family is.
The reachability verdict comes from sigil. Neither side can go green alone: our scanner
cannot see a closure, and sigil's counts do not know which sites are ours.

The `decided >= reachable extern-guard count` assertion is a LOWER-BOUND check and is
labelled as one. sigil lowers more than `ensure` sites to LinkAsserts (657 decided against
~134 reachable extern guards in sonic4 plain), so equality is not available and pinning
today's 657 would be the snapshot-of-foreign-behaviour defect. The bound is still the
direction that matters: it cannot rise past a real regression, and it goes red the moment
sigil decides fewer LinkAsserts than we have guards demanding decisions.

COST, MEASURED
--------------
Four `sigil build --check` runs. See the module-level `SHAPES` note for the measurement and
the machine it was taken on. `--check` writes no ROM; for a sound-ON game it does run
sigil's own `emit_generated` into `engine/sound/generated/`, which `build.sh` has already
written identically at line 399 before this lane runs — asserted, not assumed, by
`test_check_does_not_perturb_generated_sound_artifacts`.

RUNNER: `build.sh`'s pre-build tool-suite lane (`build.sh:628`, `python3 -m pytest
"${TOOLS}" -q ... -m "not needs_build"`, build-fatal), which collects `tools/test_*.py` by
directory sweep — so this file needs no wiring edit. Also runnable standalone:

    SIGIL_BUILD=... python3 -m pytest tools/test_extern_guard_reachability.py -q
"""
import hashlib
import os
import pathlib
import re
import subprocess
import sys

import pytest

AEON = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AEON / "tools"))
import extern_guard_census as census  # noqa: E402  (path set above)

# The shapes swept, as (label, extra sigil args). The first four are build.sh's own two
# canonical shapes per game. The fifth is `--config-a`, one of the named off-canonical
# profiles build.sh prints in its own refusal message (build.sh:196-197,207-208) — it is
# here because `engine/debug/sound_debug.emp:93` is a real, live guard that ONLY that
# profile places, and its own header says so ("a canonical `./build.sh` proves nothing
# about it either way"). Sweeping it turns that guard from excused into covered, which is
# strictly better than an allowlist entry, and costs one more `--check`.
#
# COST: five `sigil build --check` runs, measured ~1.2 s each on this machine (see the
# module docstring). It sits in the same lane as `emp_expect_fail`'s 22.69 s of real
# builds and is skipped wholesale by `FAST=1` (build.sh:245), so the comparison a reader
# wants is ~6 s against that 22.69 s, not against the 1.15 s ROM assemble.
SHAPES = [
    ("sonic4 plain", ["--game", "sonic4"]),
    ("sonic4 debug", ["--game", "sonic4", "--debug"]),
    ("demo plain", ["--game", "demo"]),
    ("demo debug", ["--game", "demo", "--debug"]),
    ("config_a", ["--config-a"]),
]

# ---- THE TWO EXCUSAL CLASSES, AND WHY NEITHER IS A MUTE ----------------------
#
# CLASS 1 — POISON FIXTURES. `games/sonic4/test/poison/poison_extern_*.emp` hold
# extern()-bearing guards that no shape may reach: a poison that entered a shipping
# closure would fail the real build. They are evaluated by `sigil build --extra-entry`
# from `tools/emp_expect_fail.py`, which is a runner, so they are covered — just not by
# a closure. The excusal is DERIVED by importing that lane's own registration list rather
# than globbing the directory: a poison that stops being registered stops being excused
# and reds this gate, which a path glob could never notice.
#
# CLASS 2 — SEAM-1 SOUND MODULES. `games/sonic4/data/sound/{mt_bank,sfx_blob_win_tab}.emp`
# reach lowering through `emit_sound_blob` (seam-1), not through any `--check` closure —
# sigil's own unreachable warning says so in its parenthetical. `--check` therefore
# CANNOT see them, and `emit_sound_blob` has no reporting mode to ask (`--help` is
# rejected; its usage is `--aeon <dir> --out-dir <dir>` and nothing else). Their liveness
# is proved instead by `tools/extern_guard_census.py`, which negates them and catches the
# resulting `panic!` — and that panic-instead-of-diagnostic IS an already-booked defect,
# docs/DEFERRED_WORK.md LS-16b, whose fix is in the sigil tree. This gate cannot close
# LS-16b and does not pretend to; it names the boundary and keeps the excusal honest with
# `test_seam_excusals_are_not_stale` below.
SEAM_EXCUSED = {
    "games/sonic4/data/sound/mt_bank.emp":
        "lowered through seam-1 (emit_sound_blob), invisible to --check; guards proved "
        "live by tools/extern_guard_census.py via the panic path — see LS-16b",
    "games/sonic4/data/sound/sfx_blob_win_tab.emp":
        "lowered through seam-1 (emit_sound_blob), invisible to --check; guards proved "
        "live by tools/extern_guard_census.py via the panic path — see LS-16b",
}

CHECKED_RE = re.compile(
    r"^checked: (?P<shape>[^:]+): (?P<verdicts>\d+) ensure verdict\(s\) at comptime, "
    r"(?P<decided>\d+) LinkAssert\(s\) decided at link, "
    r"(?P<inapplicable>\d+) LinkAssert\(s\) inapplicable",
    re.M,
)

# The unreachable warning, keyed on the FILE in the diagnostic prefix rather than on the
# module name in the sentence. The two differ: this tree carries 14 `module.path-mismatch`
# warnings, so a module's dotted name is not a function of its path, and the census's site
# set is keyed by path. Using the prefix keeps one join key for both authorities.
UNREACHABLE_RE = re.compile(
    r"^\./(?P<file>\S+?\.emp):\d+:\d+: warning: \[module\.unreachable\] module "
    r"`(?P<module>[\w.]+)`",
    re.M,
)

SOUND_GENERATED = AEON / "engine" / "sound" / "generated"


def _sigil() -> str:
    """The installed assembler, or a LOUD failure.

    NOT a skip. `build.sh` hard-errors without `SIGIL_BUILD` two hundred lines above this
    lane, so inside the runner this cannot be missing; standalone it can, and a skip there
    would render "I could not measure the guard family" as a green dot. The same contract
    `tools/emp_expect_fail.py` states for the same reason.
    """
    exe = os.environ.get("SIGIL_BUILD")
    if not exe or not os.access(exe, os.X_OK):
        pytest.fail(
            "SIGIL_BUILD is unset or not executable, so no shape could be checked and "
            "this lane measured NOTHING about the extern()-guard family. That is a "
            "failure, not a skip (build.sh's own contract: the assembler is required)."
        )
    return exe


def _run_check(args: list) -> tuple[int, str]:
    p = subprocess.run(
        [_sigil(), "build", "--aeon", ".", "--native", *args, "--check"],
        cwd=AEON, capture_output=True, text=True,
        env=dict(os.environ, SIGIL_WARNINGS="full"),
    )
    return p.returncode, p.stdout + p.stderr


def poison_excused() -> dict:
    """The poison fixtures the expect-fail lane registers, read out of THAT lane.

    Imported rather than globbed. `games/sonic4/test/poison/*.emp` is a directory; the
    LINK rows of `tools/emp_expect_fail.py` are a RUNNER. Excusing by the directory would
    excuse a poison nothing runs — the exact shape of hole LS-15/LS-16 book. Excusing by
    registration means unregistering one moves this gate, not just that one.

    A failure to import is LOUD: silently falling back to a glob would restore the weaker
    rule without saying so.
    """
    try:
        import emp_expect_fail as eef
    except BaseException as exc:  # SystemExit too: it exits when SIGIL_BUILD is unset
        pytest.fail(
            "cannot import tools/emp_expect_fail.py to learn which poison fixtures are "
            f"registered in a runner ({exc!r}). Without it this gate would have to excuse "
            "the poison directory wholesale, which would excuse a fixture nothing runs."
        )
    rows = [eef.LINK_SENTINEL] + [(p, e, x, c) for p, e, x, c in eef.LINK_CASES]
    return {r[0]: "registered in tools/emp_expect_fail.py's LINK rows (--extra-entry)"
            for r in rows}


def excused() -> dict:
    out = dict(SEAM_EXCUSED)
    out.update(poison_excused())
    return out


def _digest_generated() -> dict:
    if not SOUND_GENERATED.is_dir():
        return {}
    out = {}
    for p in sorted(SOUND_GENERATED.rglob("*")):
        if p.is_file():
            out[str(p.relative_to(AEON))] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


@pytest.fixture(scope="module")
def checks():
    """One `--check` per shape, run once for the whole module.

    Also snapshots `engine/sound/generated/` on both sides of the sweep, so the
    perturbation test grades THIS run's writes rather than a claim about them.
    """
    before = _digest_generated()
    results = {}
    for label, args in SHAPES:
        rc, out = _run_check(args)
        results[label] = {"rc": rc, "out": out}
    after = _digest_generated()
    return {"shapes": results, "generated_before": before, "generated_after": after}


def _unreachable(out: str) -> set:
    return {m.group("file") for m in UNREACHABLE_RE.finditer(out)}


def _guard_files(sites) -> dict:
    files = {}
    for s in sites:
        files.setdefault(s["file"], []).append(s["line"])
    return files


def _parse(entry: dict, shape: str) -> dict:
    m = CHECKED_RE.search(entry["out"])
    if not m:
        tail = "\n    ".join(entry["out"].strip().splitlines()[-6:])
        pytest.fail(
            f"`sigil build --check` for shape `{shape}` printed no `checked:` summary "
            f"(rc={entry['rc']}), so this lane learned NOTHING about that shape's "
            f"guards. Do not read this as a pass. Last lines:\n    {tail}"
        )
    return {
        "shape": m.group("shape"),
        "verdicts": int(m.group("verdicts")),
        "decided": int(m.group("decided")),
        "inapplicable": int(m.group("inapplicable")),
    }


# ---------------------------------------------------------------- H4: measurability

def test_every_shape_reported(checks):
    """Every shape build.sh ships must produce a parseable `checked:` summary.

    This is the anti-vacuity floor for the three tests below: each of them reads
    `--check` output, and output that does not exist would make them all pass by having
    nothing to disagree with.
    """
    broken = []
    for shape, _args in SHAPES:
        entry = checks["shapes"][shape]
        if entry["rc"] != 0 or not CHECKED_RE.search(entry["out"]):
            tail = " | ".join(entry["out"].strip().splitlines()[-3:])
            broken.append(f"{shape}: rc={entry['rc']} :: {tail}")
    assert not broken, (
        "a shape could not be checked, so its extern()-bearing guards were not decided "
        "and this lane cannot speak for them:\n  " + "\n  ".join(broken)
    )


# ---------------------------------------------------------------- H3: undecided

def test_no_linkassert_is_inapplicable(checks):
    """`inapplicable` counts LinkAsserts sigil reached but could not decide, because the
    extern they name is not defined in this link. Such a guard is present, compiled,
    reported nowhere, and enforcing nothing — the family's failure mode with the fewest
    outward symptoms. The expectation is not a pin: ZERO is the only value at which every
    guard the shape lowered got an answer."""
    offenders = []
    for shape, _args in SHAPES:
        got = _parse(checks["shapes"][shape], shape)
        if got["inapplicable"] != 0:
            offenders.append(
                f"{shape}: {got['inapplicable']} LinkAssert(s) reached but NOT decided "
                f"(extern not defined in this link, allowlisted)"
            )
    assert not offenders, (
        "LinkAsserts were allowlisted rather than decided; each is a guard that cannot "
        "fail whatever it asserts:\n  " + "\n  ".join(offenders)
    )


# ---------------------------------------------------------------- H1: unreachable

def test_every_extern_guard_file_is_reachable_in_some_shape(checks):
    """THE CORE ROW. A file holding `extern()`-bearing guards must be inside the `use`
    closure of at least ONE shipped shape, or its guards are comments.

    Not per-shape: a game-side module is legitimately absent from the other game, and
    `engine/system/z80_init.emp` is legitimately absent from sound-ON sonic4. The union
    over the four shapes is the question that has an answer, and it is the same union
    `tools/extern_guard_census.py` reported as 135/135 on 2026-09-06 — recomputed here on
    every build instead of once by hand.

    The expectation is DERIVED, not pinned: the site set comes from the census's own
    `collect()`, the unreachable set from sigil, and the assertion is that their
    intersection over all four shapes is empty. No number is written down, so nothing
    here can go stale in either direction.
    """
    sites = census.collect()
    assert sites, (
        "extern_guard_census.collect() found ZERO extern()-bearing ensure sites. Either "
        "the family really was deleted (say so in docs/DEFERRED_WORK.md LS-16c) or the "
        "scanner broke — and a scanner that finds nothing makes this whole lane vacuous."
    )
    guard_files = _guard_files(sites)
    excuses = excused()

    unreachable_everywhere = None
    per_shape = {}
    for shape, _args in SHAPES:
        unreachable = _unreachable(checks["shapes"][shape]["out"])
        per_shape[shape] = unreachable
        here = set(guard_files) & unreachable
        unreachable_everywhere = here if unreachable_everywhere is None else (
            unreachable_everywhere & here)

    dead = sorted((unreachable_everywhere or set()) - set(excuses))
    detail = []
    for f in dead:
        lines = ", ".join(str(n) for n in guard_files[f])
        detail.append(f"{f} (guard line(s) {lines}) — outside the closure of every "
                      f"checked shape: {', '.join(per_shape)}")
    assert not dead, (
        f"{len(dead)} file(s) hold extern()-bearing `ensure` guards that NO checked shape "
        f"evaluates. Each is a guard that cannot fail whatever it asserts — the "
        f"engine/system/z80_init.emp class (LS-16a). Either bring the module into a "
        f"shape's `use` closure or delete the guard; do not `use` a module to silence "
        f"this, and do not add an excusal without a RUNNER behind it:\n  "
        + "\n  ".join(detail)
    )


def test_decided_count_covers_the_reachable_extern_guards(checks):
    """A LOWER BOUND, and labelled as one. sigil lowers more than `ensure` sites to
    LinkAsserts, so `decided` exceeds our count and equality is unavailable; pinning
    today's number would pin a snapshot of sigil's behaviour rather than a property.

    What the bound still catches: sigil deciding FEWER LinkAsserts than this tree has
    reachable guards demanding a decision — which cannot happen while every one of them
    is being decided.
    """
    guard_files = _guard_files(census.collect())

    short = []
    for shape, _args in SHAPES:
        entry = checks["shapes"][shape]
        got = _parse(entry, shape)
        unreachable = _unreachable(entry["out"])
        reachable_guards = sum(len(v) for f, v in guard_files.items()
                               if f not in unreachable)
        if got["decided"] < reachable_guards:
            short.append(
                f"{shape}: sigil decided {got['decided']} LinkAssert(s) but this tree has "
                f"{reachable_guards} extern()-bearing guard(s) in modules the shape "
                f"reaches — at least {reachable_guards - got['decided']} were not decided"
            )
    assert not short, (
        "fewer LinkAsserts decided than reachable extern()-bearing guards:\n  "
        + "\n  ".join(short)
    )


# ---------------------------------------------------------------- excusal hygiene

def test_excusals_are_not_stale(checks):
    """An excusal that has outlived its reason is worse than no excusal: it is a hole
    with a reassuring comment over it. Three ways one goes stale, all checked here.

      (a) The file no longer holds any `extern()`-bearing guard — the excusal now covers
          nothing and should be deleted, not carried.
      (b) The file became REACHABLE in some checked shape — `--check` can see it now, so
          it should be covered by the core row rather than excused past it. This is the
          direction that actually happened once already: `engine/debug/sound_debug.emp`
          would have been an allowlist entry had `--config-a` not been swept, and it is
          covered instead.
      (c) A poison excusal names a file that does not exist — `emp_expect_fail` checks
          this too, but a gate that reads another lane's list must not go green when that
          list has rotted.

    The excused set is PRINTED on every run, pass or fail. An excusal a reader never sees
    is one nobody ever revisits.
    """
    guard_files = _guard_files(census.collect())
    excuses = excused()

    reachable_somewhere = set()
    for shape, _args in SHAPES:
        unreachable = _unreachable(checks["shapes"][shape]["out"])
        reachable_somewhere |= (set(guard_files) - unreachable)

    print("\nextern()-guard excusals in force (each needs a RUNNER, not a directory):")
    for f in sorted(excuses):
        n = len(guard_files.get(f, []))
        print(f"  {f}: {n} guard(s) — {excuses[f]}")

    stale = []
    for f, why in sorted(excuses.items()):
        if not (AEON / f).is_file():
            stale.append(f"{f}: excused ({why}) but the file does not exist")
        elif f not in guard_files:
            stale.append(f"{f}: excused ({why}) but it holds NO extern()-bearing "
                         f"`ensure` — delete the excusal")
        elif f in reachable_somewhere:
            stale.append(f"{f}: excused ({why}) but a checked shape now REACHES it — "
                         f"delete the excusal and let the core row cover it")
    assert not stale, (
        "excusals that have outlived their reason (a hole with a comment over it):\n  "
        + "\n  ".join(stale)
    )


# ---------------------------------------------------------------- side effects

def test_check_does_not_perturb_generated_sound_artifacts(checks):
    """`--check` on a sound-ON game runs sigil's own `emit_generated` into
    `engine/sound/generated/` ("the one write this run makes", its own banner says). This
    lane runs INSIDE build.sh, ~230 lines after `emit_sound_blob` wrote those same files,
    and ~180 lines before the sigil invocation that reads them into the ROM. If the two
    writers disagreed, this gate would silently change the ROM it is riding in.

    Measured on THIS run rather than argued: the fixture digests the directory on both
    sides of the four checks.
    """
    before, after = checks["generated_before"], checks["generated_after"]
    changed = sorted(k for k in set(before) | set(after)
                     if before.get(k) != after.get(k))
    assert not changed, (
        "`sigil build --check` rewrote generated sound artifacts with different content "
        "than emit_sound_blob had written. This lane would then be changing the ROM of "
        "the build it runs inside; do not silence it by moving the lane:\n  "
        + "\n  ".join(changed)
    )
