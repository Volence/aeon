#!/usr/bin/env python3
"""Tests for tools/keepalive_surface.py -- the classifier that says which of the keepalive
lane's unreached option surface can rot silently.

WHY A CONTROL AND NOT A SNAPSHOT. Pinning today's 38/1/17/34 split would fail on the next
flag anyone adds and teach nothing. What is worth pinning is the ONE case whose answer is
already known from a measured defect: `--extra-right-frames` on `floor_hscroll_dump` and
`floor_capture` was sampling mid-transition while the default path measured clean. If the
classifier cannot put that flag in the rotting class, its verdicts about the other 89
options are not evidence.

That case is also the one that defeats the obvious implementation. The flag is read as
`a.extra_right_frames`, handed POSITIONALLY to `run(rom, lst, extra)`, and gated inside
that function as `if extra:`. A scan for `if args.X` finds nothing. So this file tests the
interprocedural hop by testing the case that needs it.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import keepalive_surface as ks  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope="module")
def rows():
    return ks.measure(REPO)


def _row(rows, tool, flag):
    for r in rows:
        if r["tool"] == tool and r["flag"] == flag:
            return r
    return None


# --------------------------------------------------------------------------------------
# THE CONTROL. Both tools carrying the flag with a known defect on it must classify as
# rotting surface, and must do so because a BLOCK was found -- not by accident.
# --------------------------------------------------------------------------------------
@pytest.mark.parametrize("tool", ["floor_hscroll_dump.py", "floor_capture.py"])
def test_the_flag_with_a_known_defect_classifies_as_rotting_surface(rows, tool):
    r = _row(rows, tool, "--extra-right-frames")
    assert r is not None, f"{tool} no longer exposes --extra-right-frames"
    assert r["class"] == ks.UNREACHED, (
        f"{tool} --extra-right-frames classified {r['class']}; it defaults to 0 and gates "
        f"a block, so the lane never executes that arm"
    )
    assert r["gated_blocks"] >= 1 and r["gated_lines"] >= 1, (
        "classified UNREACHED with no block found -- that is the right answer for the "
        "wrong reason, and it would also be given to a flag that gates nothing"
    )


def test_that_control_needs_the_interprocedural_hop(rows):
    """The `if args.X` implementation this replaced would score the control at zero.

    Asserted against the SOURCE rather than against a reimplementation: the flag's only
    mention outside the parser is a call argument, so any classifier that stops at
    `args.<dest>` sees no branch at all.
    """
    src = open(os.path.join(REPO, "tools", "floor_hscroll_dump.py"),
               encoding="utf-8").read()
    body = "\n".join(ln for ln in src.splitlines() if not ln.lstrip().startswith("#"))
    assert "if a.extra_right_frames" not in body
    assert "if args.extra_right_frames" not in body
    assert "if extra:" in body          # the gate, one call hop away


# --------------------------------------------------------------------------------------
# The classifier must also be able to say NO. A flag whose default RUNS the block it
# gates is not rotting surface, and pcc_identity_probe's --press-b is the case that
# separates a truthiness test from a correct one: it is store_true AND default=True.
# --------------------------------------------------------------------------------------
def test_a_store_true_with_an_explicit_true_default_is_not_unreached(rows):
    r = _row(rows, "pcc_identity_probe.py", "--press-b")
    assert r is not None
    assert r["default"] is True and r["action"] == "store_true"
    assert r["class"] == ks.RESIZED, (
        "--press-b defaults True, so `if a.press_b:` runs on every nightly; calling it "
        "unreached would put a block that executes nightly in the rotting class"
    )


def test_a_value_that_never_reaches_a_branch_is_a_pure_parameter(rows):
    r = _row(rows, "streaming_choke_probe.py", "--settle")
    assert r is not None and r["class"] == ks.PARAM and r["gated_blocks"] == 0


def test_a_set_choices_option_still_reports_its_unreached_choices(rows):
    """The manifest SETS this one, and it is still surface: choices are one-at-a-time."""
    r = _row(rows, "lens_residue_raster_witness.py", "witness")
    assert r is not None and r["class"] == ks.SELECTOR
    assert r["reached_choices"] == ["efx4b"]
    assert set(r["unreached_choices"]) == {"c1b3", "c3b2", "c3b2s7", "all"}


# --------------------------------------------------------------------------------------
# The surface the argparse route cannot see, kept from being rounded to "nothing there".
# --------------------------------------------------------------------------------------
def test_environment_input_is_reported_because_no_argparse_scan_can_see_it(rows):
    env = {r["tool"]: r["env"] for r in rows if r["env"]}
    assert "PB_ROM" in env.get("plane_buffer_headroom_probe.py", [])
    assert "PB_LST" in env.get("plane_buffer_headroom_probe.py", [])


def test_every_wired_tool_is_accounted_for(rows):
    """A tool with no unset surface produces no option row; it must still be reachable
    from the manifest, or this module is quietly measuring a subset."""
    import tomllib
    rowkeys = set(tomllib.load(
        open(os.path.join(REPO, "tools", "keepalive_manifest.toml"), "rb"))["wired"])
    # A manifest row is an INVOCATION: `tool.py` or `tool.py#arm-label`. `measure()` folds a
    # tool's rows before scanning it, so the tool set is what these rows are about. The "#"
    # is spelled out rather than imported from keepalive_lane, for this file's own reason: a
    # fixture that reads the same symbol as the code under test measures self-consistency.
    wired = {k.split("#", 1)[0] for k in rowkeys}
    seen = {r["tool"] for r in rows}
    assert seen <= wired
    # NOT an equality: a tool whose declared invocation sets everything produces no option
    # row at all (the docstring above says so), so `seen` is a subset by design. 28 of the
    # 35 wired tools carry unset surface on 2026-09-19.
    for name in wired:
        assert os.path.isfile(os.path.join(REPO, "tools", name)), name


# --------------------------------------------------------------------------------------
# THE LANE'S OWN BOOKKEEPING MUST NOT ACT AS A REACHABILITY SOURCE, AND NOTHING CHECKED IT.
#
# `keepalive_population.LANE_BOOKKEEPING` carries a measured warning: without it the
# advisory "nothing executes this" count moved 50 -> 47 the moment `test_keepalive_lane.py`
# was written, because a test's short string literal "tools/foo.py" is exactly what the
# census deliberately KEEPS (that is where a real invocation lives). The list was correct
# and hand-maintained, and NOTHING enforced that a new lane file joined it.
#
# So it rotted on the next lane file added -- this one. MEASURED 2026-09-19 on this tree:
# committing `tools/test_keepalive_surface.py`, whose control names two instruments by
# filename, moved the same count 50 -> 43 and flipped `floor_hscroll_dump.py` from dead to
# live. Seven instruments credited as executed by a file that only measures them.
#
# The list stays EXPLICIT -- `keepalive_population`'s own comment gives the reason a prefix
# rule is an open-ended hole -- and this test is what makes it keep up.
# --------------------------------------------------------------------------------------
def test_every_keepalive_file_is_excluded_as_a_reachability_source():
    import subprocess
    import keepalive_population as kpop

    tracked = subprocess.run(
        ["git", "-C", REPO, "ls-files"], capture_output=True, text=True, check=True
    ).stdout.split("\n")
    # Scoped to what `_code_corpus` actually READS -- it skips anything that is not .py
    # or .sh, so `keepalive_manifest.toml` is not a source today and flagging it would be
    # a red for a non-defect. If that filter ever widens, this widens with it.
    own = {f for f in tracked
           if "keepalive" in os.path.basename(f) and f.startswith("tools/")
           and (f.endswith(".py") or f.endswith(".sh"))}
    missing = sorted(own - set(kpop.LANE_BOOKKEEPING))
    assert not missing, (
        "these files are the keepalive lane's own bookkeeping and are being counted as "
        "evidence that something ELSE executes the instruments they name: "
        f"{missing}. Add them to keepalive_population.LANE_BOOKKEEPING."
    )
