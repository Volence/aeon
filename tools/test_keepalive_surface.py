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


# ======================================================================================
# THE UNWIRED HALF (KEEPALIVE-UNWIRED-SURFACE, 2026-09-19)
#
# `measure()` reads the manifest's [wired] table only, so everything above is about the 35
# tools the lane runs. The other 50 rows in that manifest are the tools it does NOT run,
# each carrying a written reason -- and a reason is a MEASURED ABSENCE, the claim most
# likely to rot, because nothing that would falsify it ever visits it.
#
# WHAT `measure_unwired()` MEANS, AND WHAT IT DOES NOT. For an unwired tool NOTHING is set,
# so classifying its options "unreached" is true by construction and says nothing. The
# informative quantity is the one a reader needs in order to PRICE a wiring:
#
#   * `required` -- what argparse would refuse without. This is the `args = [...]` any
#     manifest row would have to spell, and it is what mechanises the A/B reason class:
#     "requires --before-rom/--after-rom from two different builds" is a sentence, and
#     `required_args()` is the same claim read off the parser.
#   * the option classes UNDER AN EMPTY ARGV -- what a bare wiring would still leave dead
#     even after it went green.
#   * `bare_exit_is_free` -- the trap the manifest itself names for display_ab_gate: a row
#     that exits 0 without measuring anything. A tool whose parser demands nothing cannot
#     be told apart, from the outside, from one that measured and passed.
#
# THE CONTROLS BELOW ARE MEASURED, NOT ASSUMED. Both were run off this tree on 2026-09-19
# against s4.debug.bin crc32 62238a15 / 848,075 B:
#   `python3 tools/sec5_band_witness.py --rom ... --lst ...` -> exit 2,
#     "error: the following arguments are required: --label, --out-dir"
#   `python3 tools/bg_nt_gate.py` is declared A/B in the manifest, and its parser carries
#     required=True on exactly the four before/after paths.
# A derivation that cannot reproduce an exit status already observed is not evidence about
# the other 48 rows.
# ======================================================================================


@pytest.fixture(scope="module")
def unwired():
    return ks.measure_unwired(REPO)


def _tool(rows, name):
    return [r for r in rows if r["tool"] == name]


def test_every_not_wired_row_is_scanned(unwired):
    """The unwired scan must cover the manifest's [not_wired] table exactly -- a subset
    would be this lane's own defect (a census that quietly covers 49 of 50)."""
    import tomllib
    nw = set(tomllib.load(
        open(os.path.join(REPO, "tools", "keepalive_manifest.toml"), "rb"))["not_wired"])
    assert {r["tool"] for r in unwired} == nw


def test_the_measured_required_set_is_reproduced_from_the_parser(unwired):
    """CONTROL. argparse itself printed this set; the derivation must agree with it."""
    r = _tool(unwired, "sec5_band_witness.py")[0]
    assert set(r["required"]) == {"--label", "--out-dir"}, (
        "derived required set disagrees with the exit-2 argparse message measured off "
        f"this tree: {r['required']}"
    )
    assert r["needs_args"] is True


def test_the_ab_reason_class_is_read_off_the_parser_not_the_prose(unwired):
    """The three A/B rows say they need a second ROM. That is checkable, so it is checked."""
    for name, want in (
            ("bg_nt_gate.py", {"--before-rom", "--before-lst", "--after-rom", "--after-lst"}),
            ("display_ab_gate.py", {"--before-rom", "--before-lst", "--after-rom", "--after-lst"}),
            ("sec7_waterline_probe.py", {"--old-rom", "--old-lst", "--new-rom", "--new-lst"})):
        r = _tool(unwired, name)[0]
        assert set(r["required"]) == want, f"{name}: {r['required']}"
        assert r["needs_args"] is True


def test_a_tool_whose_parser_demands_nothing_is_flagged_as_a_free_green(unwired):
    """The display_ab_gate trap, generalised: a row that can exit 0 having measured
    nothing looks identical from the outside to one that measured and passed. The flag
    is not a verdict -- it marks the rows where an exit status is not evidence."""
    r = _tool(unwired, "fade_busy_stale_witness.py")[0]
    assert r["needs_args"] is False and r["bare_exit_is_free"] is True
    # And it must be able to say NO: a parser with four required paths is not free.
    assert _tool(unwired, "bg_nt_gate.py")[0]["bare_exit_is_free"] is False


def test_a_file_that_is_not_a_program_is_reported_as_one(unwired):
    """`aether_bytes.py` is excluded as "not an instrument". It has no argparse AND no
    __main__ block, so it cannot be invoked at all -- which is the reason, derived."""
    r = _tool(unwired, "aether_bytes.py")[0]
    assert r["flag"] == "(no argparse)"
    assert r["runnable"] is False
    # The harness beside it IS runnable, so this is not a blanket answer for the pair.
    assert _tool(unwired, "aether_instance.py")[0]["runnable"] is True


def test_choices_domains_are_reported_wholly_unreached(unwired):
    """A wired tool's selector reports the ONE choice the lane reaches. An unwired tool
    reaches none, and the whole domain is the unmeasured surface."""
    rows = [r for r in _tool(unwired, "lens_residue_object_witness.py")
            if r["class"] == ks.SELECTOR]
    assert rows, "the selector this tool refuses without is no longer a choices option"
    r = rows[0]
    assert r["reached_choices"] == []
    assert "c2a6" in r["unreached_choices"]


def test_a_hand_rolled_argv_dispatcher_is_undetermined_not_free(unwired):
    """LOUD ON UNMEASURABLE. `bare_exit_is_free` is read off argparse, so for a tool that
    parses `sys.argv` by hand it is not a measurement at all and must not be reported as
    one. Both no-argparse programs in the [not_wired] table dispatch by hand, and
    cache_hold_probe is the case that proves the difference is real: another lane already
    records that an unknown/missing mode gives it usage + exit 1, i.e. the OPPOSITE of the
    free green a truthiness answer here would assert.

    Contrast with aether_bytes.py, which has no argparse AND no __main__: not runnable at
    all, which IS determinable, and False rather than None."""
    for name in ("cache_hold_probe.py", "reels_witness.py"):
        r = _tool(unwired, name)[0]
        assert r["flag"] == "(no argparse)", name
        assert r["bare_exit_is_free"] is None, (
            f"{name} parses sys.argv by hand; argparse says nothing about its bare argv, "
            f"and reporting {r['bare_exit_is_free']!r} would be an unmeasured claim"
        )
        assert r["needs_args"] is None, name
    assert _tool(unwired, "aether_bytes.py")[0]["bare_exit_is_free"] is False


def test_a_built_choices_domain_is_resolved_and_matches_argparse(unwired):
    """MEASURED CONTROL. `choices=WITNESSES + ("c4a2t","all") + tuple(AB)` is not a
    literal. Running the tool on this tree, 2026-09-19, argparse printed its own domain:

        usage: lens_residue_object_witness.py ...
               {c2a6,multisprite,nullmap,c4a2,c4a3,c4a2t,all,c4a3ab,c4a2ab}

    The evaluator must reproduce that exactly -- and the failure it replaces is worse than
    no answer: the unresolved marker "<expr>" is a STRING, and iterating it reported the
    domain as ['<','e','x','p','r','>'], which looks like a result."""
    r = [x for x in _tool(unwired, "lens_residue_object_witness.py")
         if x["flag"] == "witness"][0]
    assert r["choices"] == ["c2a6", "multisprite", "nullmap", "c4a2", "c4a3",
                            "c4a2t", "all", "c4a3ab", "c4a2ab"]
    assert r["unreached_choices"] == r["choices"]


def test_no_manifest_tool_has_an_unresolvable_choices_domain(unwired):
    """If one appears, it must show as the marker -- never as a character list."""
    bad = [(r["tool"], r["flag"]) for r in unwired
           if r["choices"] == ks.CHOICES_UNRESOLVED]
    assert not bad, f"unresolvable choices domains in the manifest population: {bad}"
