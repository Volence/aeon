#!/usr/bin/env python3
"""Tests for the instrument keepalive lane.

These run in `pytest tools` on every build and boot NO emulator. They grade the two
things that can rot without anybody noticing:

  1. THE CLASSIFIER. That COULD NOT RUN stays distinct from FAILED and from PASSED is
     the lane's entire claim, and it is one function.
  2. THE ACCOUNTING. That the manifest still covers every bus instrument in the tree.
     Without this, the coverage check only happens on nights the lane runs, and a tool
     added today would go undeclared until then.

⚠ THE FIXTURES SPELL THE TRACEBACK TEXT AND THE VERDICT NAMES OUT IN FULL rather than
  importing `keepalive_lane.TRACEBACK_MARK`, `PASSED`, `FAILED` or `CNR`. That is the
  rule the DEAD-INSTRUMENT-PAIR parcel paid for and wrote down: a fixture builder and the
  code under test must not read the same symbol for the quantity being tested. When they
  do, the fixture moves with the code and the test measures self-consistency. Measured
  there: parallax_hscroll_probe had 34 unit tests pinning its arithmetic, `mkcfg` laid its
  fixtures out at `BE_SIZE` and `derive_shadow` parsed them at `BE_SIZE`, and with the
  stride mutated 32 of 34 still passed. If someone edits TRACEBACK_MARK to something a
  Python traceback never prints, these tests must go red, and they can only do that by
  not sharing the constant.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import keepalive_lane as lane  # noqa: E402
import keepalive_population as kpop  # noqa: E402

# Spelled out, deliberately. See the module docstring.
REAL_TRACEBACK = (
    "Traceback (most recent call last):\n"
    '  File "tools/parallax_hscroll_identity.py", line 391, in main\n'
    "    bad.append(_keepalive_break_shape_3)\n"
    "NameError: name '_keepalive_break_shape_3' is not defined\n"
)


def test_a_crash_is_could_not_run_not_failed():
    verdict, _ = lane.classify(rc=1, output=REAL_TRACEBACK, expect=0, timed_out=False)
    assert verdict == "COULD NOT RUN"


def test_a_crash_that_exits_the_declared_baseline_is_still_could_not_run():
    """The decisive case, and the one a naive exit-code lane gets wrong.

    parallax_hscroll_identity's declared baseline IS exit 1 (three deliberate stale-fixture
    reds). An uncaught exception also exits 1. A lane comparing only exit statuses would
    call a crashed instrument PASSED -- a dead channel wearing a healthy channel's badge,
    which is the exact defect this lane exists to close.
    """
    verdict, why = lane.classify(rc=1, output=REAL_TRACEBACK, expect=1, timed_out=False)
    assert verdict == "COULD NOT RUN", (
        "a crash that happens to exit the declared baseline status must NOT read as PASSED"
    )
    assert "NameError" in why


def test_a_measured_negative_with_no_traceback_is_failed():
    """The real parallax_hscroll_identity output shape: exits 1, prints FAIL, no traceback."""
    out = (
        "\nCOVERAGE WITNESSES - ragged spans 0   wrapping frames 240\n"
        "\nFAIL\n"
        "  - ID7: sampled buffer is identical to the flat fixture ID1\n"
    )
    assert lane.classify(rc=1, output=out, expect=0, timed_out=False)[0] == "FAILED"


def test_the_declared_baseline_is_what_passes():
    out = "FAIL\n  - ID7: ...\n"  # red output, but red IS this tool's declared baseline
    assert lane.classify(rc=1, output=out, expect=1, timed_out=False)[0] == "PASSED"


def test_a_known_red_going_green_is_failed_not_passed():
    """Otherwise the cheapest way to green this lane is to weaken an instrument."""
    assert lane.classify(rc=0, output="OK\n", expect=1, timed_out=False)[0] == "FAILED"


def test_a_timeout_is_could_not_run():
    assert lane.classify(rc=-1, output="", expect=0, timed_out=True)[0] == "COULD NOT RUN"


def test_a_timeout_is_could_not_run_even_when_the_partial_output_looks_fine():
    assert lane.classify(rc=-1, output="OK\n", expect=0, timed_out=True)[0] == "COULD NOT RUN"


def test_an_argparse_rejection_is_could_not_run_because_the_LANE_is_wrong():
    out = ("usage: sec5_band_witness.py [-h] [--rom ROM] --label LABEL\n"
           "sec5_band_witness.py: error: the following arguments are required: --label\n")
    verdict, why = lane.classify(rc=2, output=out, expect=0, timed_out=False)
    assert verdict == "COULD NOT RUN"
    assert "invocation" in why


def test_a_plain_exit_2_without_a_usage_error_is_failed():
    """Exit 2 is a real verdict for some tools; only an ARGPARSE exit 2 is a lane problem."""
    out = "three arms are vacuous; exiting 2\n"
    assert lane.classify(rc=2, output=out, expect=0, timed_out=False)[0] == "FAILED"


def test_the_clean_pass():
    assert lane.classify(rc=0, output="OK\n", expect=0, timed_out=False)[0] == "PASSED"


def test_no_declared_baseline_can_make_a_crash_green():
    """There must be no manifest setting that accepts a crash as an instrument's normal state.

    A measured negative is a legitimate thing to baseline -- parallax_hscroll_identity's
    three stale-fixture reds are declared. A CRASH never is: baselining one would mean the
    lane agreeing to stop noticing that a channel cannot report, which is the defect.
    """
    tb = "Traceback (most recent call last):\nNameError: boom\n"
    for expect in range(-2, 5):
        assert lane.classify(rc=1, output=tb, expect=expect, timed_out=False)[0] == "COULD NOT RUN"


# ---------------------------------------------------------------------------------
#  The instrument's own refusal word
# ---------------------------------------------------------------------------------
# All five strings below are VERBATIM from the lane's first real run, 2026-09-18, against
# s4.debug.bin crc32 62238a15. They are not invented shapes.

@pytest.mark.parametrize("line", [
    "blank_priority_probe: COULD NOT RUN - ROM crc32 62238a15 is not the measured 9ce1c2ff; pass --any-rom",
    "COULD NOT RUN (setup): ROM s4.debug.bin is crc32 62238a15, not the 9ce1c2ff this run expects.",
    "REFUSED: band record is 32 bytes, expected 20 (legacy prefix + one band_ext).",
    "UNMEASURABLE: Sound_DebugMirror is not a label in s4.debug.lst",
    "BLOCKED: [idle] the borrowed symbol addresses do not describe this ROM",
])
def test_an_instrument_that_refuses_is_could_not_run_not_failed(line):
    out = "some preamble\n" + line + "\nmore output\n"
    verdict, why = lane.classify(rc=1, output=out, expect=0, timed_out=False)
    assert verdict == "COULD NOT RUN", (
        "an instrument saying in its own words that it cannot measure this ROM is a "
        "channel that cannot report, not an engine defect"
    )
    assert "itself refused" in why


def test_a_refusal_word_inside_a_sentence_does_not_trigger():
    """The marker must BEGIN a line. Otherwise ordinary prose reclassifies a real failure."""
    out = "VERDICT FAIL\n  the engine REFUSED the write, which is the behaviour under test\n"
    assert lane.classify(rc=1, output=out, expect=0, timed_out=False)[0] == "FAILED"


def test_a_tool_that_exited_zero_is_never_reclassified_by_its_prose():
    out = "note: an earlier arm was UNMEASURABLE, the rest ran\nOK\n"
    assert lane.classify(rc=0, output=out, expect=0, timed_out=False)[0] == "PASSED"


def test_refusal_is_expected_opts_a_tool_out():
    """tools/curve_probe.py refuses every canonical image BY DESIGN."""
    out = "REFUSED: this image is canonical, which is what this probe asserts\n"
    assert lane.classify(rc=1, output=out, expect=1, timed_out=False,
                         refusal_is_expected=True)[0] == "PASSED"


def test_a_real_measured_failure_is_still_failed():
    """waterline_art_witness's actual first-run output shape: a verdict, not a refusal."""
    out = ("  POSITIVE  12/12 frames: VRAM equals the gather predicted from the ladder row\n"
           "  VERDICT FAIL\n")
    assert lane.classify(rc=1, output=out, expect=0, timed_out=False)[0] == "FAILED"


# ---------------------------------------------------------------------------------
#  The accounting
# ---------------------------------------------------------------------------------

def _manifest():
    return lane.load_manifest(lane.DEFAULT_MANIFEST)


def test_every_bus_instrument_in_the_tree_is_declared():
    """A keepalive lane quietly covering 84 of 85 is the artifact it was built to prevent."""
    pop = kpop.population(lane.REPO)
    _, undeclared, missing, dupes = lane.account(_manifest(), pop)
    assert undeclared == [], f"bus instruments in the tree with no manifest disposition: {undeclared}"
    assert missing == [], f"manifest names tools that are no longer in the tree: {missing}"
    assert dupes == [], f"declared both wired and not_wired: {dupes}"


def test_the_population_is_not_empty():
    """A census that returned nothing would make every accounting assertion above vacuous."""
    assert len(kpop.population(lane.REPO)) > 50


def test_every_not_wired_entry_carries_a_reason():
    for name, reason in _manifest()["not_wired"].items():
        assert isinstance(reason, str) and len(reason.strip()) >= 20, (
            f"{name} is declared not-wired without a usable reason"
        )


def test_every_wired_entry_names_a_file_that_exists_and_a_baseline():
    for name, spec in _manifest()["wired"].items():
        assert os.path.isfile(os.path.join(lane.REPO, "tools", name)), name
        assert isinstance(spec.get("expect"), int), f"{name} has no declared baseline"
        assert isinstance(spec.get("timeout"), int) and spec["timeout"] > 0, name


def test_the_lane_excuses_only_its_own_two_files_from_the_census():
    """A PREFIX exclusion here once ate the fixture written to test the UNDECLARED arm.

    population() has to skip the lane's own machinery, which names BusClient in prose.
    While that skip was `fname.startswith("keepalive_")`, anything named keepalive_* was
    invisible to the census -- an open-ended hole in the exact check the lane exists for.
    """
    assert kpop.LANE_OWN_FILES == {"keepalive_population.py", "keepalive_lane.py"}


@pytest.mark.parametrize("name", ["parallax_hscroll_identity.py", "parallax_hscroll_probe.py"])
def test_the_two_instruments_that_motivated_this_lane_are_accounted_for(name):
    m = _manifest()
    assert name in m["wired"] or name in m["not_wired"], (
        f"{name} is one of the two instruments found dead on 2026-09-18; "
        "it must not fall out of this lane's accounting"
    )
