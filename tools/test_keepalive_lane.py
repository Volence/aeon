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

    A declared baseline of exit 1 is real -- three rows carry one on 2026-09-19, and
    parallax_hscroll_identity carried one until IDENTITY-FIXTURE-RULING settled its three
    stale-fixture reds that day. An uncaught exception also exits 1, so a lane comparing
    only exit statuses would
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

    A measured negative is a legitimate thing to baseline -- loop_step_over_witness's
    setup refusal is declared. A CRASH never is: baselining one would mean the
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
    for row, spec in _manifest()["wired"].items():
        # A row key is an INVOCATION; only the part before the `#` is a filename.
        assert os.path.isfile(os.path.join(lane.REPO, "tools", row.split("#")[0])), row
        assert isinstance(spec.get("expect"), int), f"{row} has no declared baseline"
        assert isinstance(spec.get("timeout"), int) and spec["timeout"] > 0, row


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


# ---------------------------------------------------------------------------------
#  A BASELINE DESCRIBES AN INVOCATION, NOT A TOOL
# ---------------------------------------------------------------------------------
# Measured 2026-09-19 (`KEEPALIVE-DEFAULT-ARGS`): `loop_step_over_witness --phase-sweep`
# enters its arm, hits the same tool-wide SETUP red the default arm hits, and exits 1.
# Graded against a TOOL-keyed `expect = 1` it reports PASSED -- a row that reports PASSED
# whatever it does. These pin the rule that stops a red baseline travelling onto an arm
# nobody measured.
#
# ⚠ THE FIXTURES SPELL "COULD NOT RUN" AND THE ARGV OUT IN FULL, for the module
#   docstring's reason: a fixture that imported `lane.ARM_SEP` or `lane.CNR` would move
#   with the code and measure self-consistency.

DEFAULT_ARGV = ["--rom", "{rom}", "--lst", "{lst}"]
SWEEP_ARGV = ["--rom", "{rom}", "--lst", "{lst}", "--phase-sweep"]


def test_a_row_key_names_the_tool_before_the_separator():
    assert lane.tool_of("loop_step_over_witness.py#phase-sweep") == "loop_step_over_witness.py"
    assert lane.arm_of("loop_step_over_witness.py#phase-sweep") == "phase-sweep"
    assert lane.tool_of("loop_step_over_witness.py") == "loop_step_over_witness.py"
    assert lane.arm_of("loop_step_over_witness.py") == ""


def test_a_zero_baseline_needs_no_argv_because_zero_cannot_travel():
    assert lane.baseline_drift("x.py", {"args": DEFAULT_ARGV, "expect": 0}) is None
    assert lane.baseline_drift("x.py", {"args": DEFAULT_ARGV}) is None


def test_a_non_zero_baseline_with_no_declared_argv_is_refused():
    why = lane.baseline_drift("loop_step_over_witness.py",
                              {"args": DEFAULT_ARGV, "expect": 1})
    assert why is not None
    assert "baseline_args" in why


def test_a_baseline_measured_on_a_different_arm_cannot_grade_this_row():
    """THE MEASURED CASE. The `--phase-sweep` arm carrying the default arm's baseline."""
    why = lane.baseline_drift("loop_step_over_witness.py#phase-sweep",
                              {"args": SWEEP_ARGV, "expect": 1,
                               "baseline_args": DEFAULT_ARGV})
    assert why is not None
    assert "DIFFERENT invocation" in why


def test_a_baseline_that_names_its_own_argv_grades_normally():
    assert lane.baseline_drift("loop_step_over_witness.py#phase-sweep",
                               {"args": SWEEP_ARGV, "expect": 1,
                                "baseline_args": SWEEP_ARGV}) is None


def test_a_stale_declared_argv_is_caught_even_on_a_zero_baseline():
    """Zero is exempt from NEEDING the field, not from meaning it once it is there."""
    assert lane.baseline_drift("x.py", {"args": SWEEP_ARGV, "expect": 0,
                                        "baseline_args": DEFAULT_ARGV}) is not None


def test_a_drifting_row_is_could_not_run_and_is_never_spawned(tmp_path):
    """Both halves matter: the verdict is the third outcome, and no emulator is booted.

    PASSED and FAILED are both wrong answers for a run the declared baseline is not
    entitled to grade, and a headless boot spent for no verdict is the cost this refuses.
    """
    res = lane.run_one("loop_step_over_witness.py#phase-sweep",
                       {"args": SWEEP_ARGV, "expect": 1, "baseline_args": DEFAULT_ARGV,
                        "timeout": 5},
                       str(tmp_path / "rom.bin"), str(tmp_path / "x.lst"),
                       lane.REPO, False)
    assert res["verdict"] == "COULD NOT RUN"
    assert res["cmd"] == "(not run)"
    assert res["rc"] is None


def test_a_new_arm_that_declares_nothing_reports_failed_on_a_known_red_tool():
    """The default is the third guard, and it is the one that needs no author at all.

    `expect` absent means 0. An arm added to a tool whose red is understood therefore
    reports FAILED on its first run rather than inheriting the tool's declared red -- the
    lane says "this invocation exits 1 and nobody has declared that", which is true.
    """
    spec = {"args": SWEEP_ARGV}
    assert lane.baseline_drift("loop_step_over_witness.py#phase-sweep", spec) is None
    verdict, _ = lane.classify(rc=1, output="THE PLAYER NEVER LANDED\n",
                               expect=int(spec.get("expect", 0)), timed_out=False)
    assert verdict == "FAILED"


def test_two_rows_of_one_tool_running_the_same_argv_are_ambiguous():
    twins = lane.twin_rows({"a.py": {"args": DEFAULT_ARGV},
                            "a.py#copy": {"args": DEFAULT_ARGV},
                            "a.py#sweep": {"args": SWEEP_ARGV},
                            "b.py": {"args": DEFAULT_ARGV}})
    assert twins == [("a.py", "a.py#copy")]


def test_an_arm_row_is_one_disposition_not_two_in_the_accounting():
    """Adding an arm must not make the tree look like it grew an instrument."""
    manifest = {"wired": {"alpha.py": {"args": []}, "alpha.py#second": {"args": ["--x"]}},
                "not_wired": {"beta.py": "a reason long enough to pass the other test"}}
    declared, undeclared, missing, dupes = lane.account(manifest, ["alpha.py", "beta.py"])
    assert declared == {"alpha.py", "beta.py"}
    assert (undeclared, missing, dupes) == ([], [], [])


def test_an_arm_wired_while_the_tool_is_not_wired_is_still_ambiguous():
    manifest = {"wired": {"alpha.py#second": {"args": ["--x"]}},
                "not_wired": {"alpha.py": "a reason long enough to pass the other test"}}
    assert lane.account(manifest, ["alpha.py"])[3] == ["alpha.py"]


def test_the_shipped_manifest_has_no_row_whose_baseline_describes_another_invocation():
    wired = _manifest()["wired"]
    bad = {row: lane.baseline_drift(row, spec) for row, spec in wired.items()
           if lane.baseline_drift(row, spec)}
    assert bad == {}, f"rows whose declared baseline does not describe their own argv: {bad}"
    assert lane.twin_rows(wired) == []


def test_every_non_zero_baseline_in_the_shipped_manifest_spells_its_argv():
    """The population this rule exists for, held to a count rather than a spot check."""
    wired = _manifest()["wired"]
    reds = {r for r, s in wired.items() if int(s.get("expect", 0)) != 0}
    assert reds, "no row declares a non-zero baseline any more -- this rule now guards nothing"
    for row in reds:
        assert [str(a) for a in wired[row]["baseline_args"]] == \
               [str(a) for a in wired[row]["args"]], row


# ---------------------------------------------------------------------------------
#  CENSUS-CRITERION-TOO-NARROW (2026-09-25): the population is what the code DOES,
#  and "reachable" is what something EXECUTES
# ---------------------------------------------------------------------------------
# The fixtures are tiny synthetic trees, spelled out in full, so each arm is graded by a
# file whose ONLY route in is that arm. On the real tree most drivers carry three arms at
# once, so a broken arm cannot drop them and the accounting test above cannot see it.

def _tree(tmp_path, files):
    for rel, text in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    return str(tmp_path)


LENDER = (
    "from aether import BusClient\n"
    "class Server:\n"
    "    def open(self):\n"
    "        return BusClient()\n"
    "def parse(text):\n"
    "    return text.split()\n"
)


@pytest.mark.parametrize("name,text,arm", [
    ("imp.py", "from aether_instance import aether_emulator\n", "import"),
    ("legacy.py", "from launcher import headless_emulator\n", "import"),
    ("proto.py", "def peek(c):\n    return c.call('emulator/read_memory', {})\n", "protocol"),
    ("sock.py", "import socket\ns = socket.socket(socket.AF_UNIX)\n", "socket"),
    ("borrower.py", "from lender import Server\nServer().open()\n", "borrow"),
    ("modborrower.py", "import lender\nlender.Server().open()\n", "borrow"),
    ("parent.py", "import subprocess\nsubprocess.run(['python3', 'tools/lender.py'])\n", "child"),
    ("scenes.py", "import subprocess, sys\nsubprocess.run([sys.executable, 'x/ab_runner.py'])\n",
     "child"),
])
def test_each_arm_admits_a_file_that_only_it_reaches(tmp_path, name, text, arm):
    repo = _tree(tmp_path, {"tools/lender.py": LENDER, f"tools/{name}": text})
    arms = kpop.drives(repo)
    assert name in arms, f"{name} drives an emulator by the {arm!r} arm and was not counted"
    assert arm in arms[name], (name, arms[name])


@pytest.mark.parametrize("name,text", [
    # the cart_coverage_census shape: names the class, drives nothing
    ("census.py", 'CANARY = {"sfx.py": "reached solely by `from aether import BusClient`"}\n'),
    ("prose.py", '"""Talks to emulator/read_memory through BusClient."""\nX = 1\n'),
    # borrowing a member's ARITHMETIC is not driving an emulator
    ("arith.py", "from lender import parse\nparse('a b')\n"),
    # a table of scripts is not a child process
    ("table.py", "RUNNERS = ('lender.py', 'other.sh')\n"),
])
def test_a_file_that_only_names_the_bus_is_not_a_driver(tmp_path, name, text):
    repo = _tree(tmp_path, {"tools/lender.py": LENDER, f"tools/{name}": text})
    assert name not in kpop.drives(repo)


def test_the_real_population_contains_the_drivers_the_old_criterion_missed():
    """The four booked 2026-09-19 plus the two this change found; and not the census.

    Each is here for a reason read off its source, not copied from a count:
    effects_gates runs ab_runner.py and sixteen member gates as children;
    cart_identity speaks `emulator/read_memory` on a client it is handed;
    depth_onset_probe imports `aether_instance.assert_rust_server` and borrows
    `curve_desc_probe.Server`; cart_verify_spawn_proof constructs `AetherInstance`;
    base_swap_witness calls `ramp_authored_witness.run`, which spawns; and
    staging_lifetime_timeline borrows `tick_variance_probe.Server`.
    cart_coverage_census names BusClient in strings and drives nothing.
    """
    pop = set(kpop.population(lane.REPO))
    for name in ("effects_gates.py", "cart_identity.py", "depth_onset_probe.py",
                 "cart_verify_spawn_proof.py", "base_swap_witness.py",
                 "staging_lifetime_timeline.py"):
        assert name in pop, name
    assert "cart_coverage_census.py" not in pop


RUNNER_TEST = (
    "import subprocess, sys\n"
    "import c_lib, e_main\n"
    "TOOLS = ['a_table.py']\n"
    "PATTERN = r'python3 tools/b_regex\\.py'\n"
    "PROBE = 'tools/f_bound.py'\n"
    "def test_x():\n"
    "    c_lib.helper()\n"
    "    subprocess.run([sys.executable, 'tools/d_argv.py'])\n"
    "    e_main.main([])\n"
    "    subprocess.run([sys.executable, str(PROBE)])\n"
)
RUNNER_SH = (
    "#!/bin/bash\n"
    "# python3 tools/g_comment.py\n"
    "echo \"then run python3 tools/g_echo.py by hand\"\n"
    "python3 tools/h_sh.py --rom x.bin\n"
)
TARGETS = ("a_table", "b_regex", "c_lib", "d_argv", "e_main", "f_bound",
           "g_comment", "g_echo", "h_sh")


def test_only_an_executing_reference_makes_a_tool_reachable(tmp_path):
    files = {"tools/test_runner.py": RUNNER_TEST, "tools/landing_build.sh": RUNNER_SH}
    files.update({f"tools/{t}.py": "def helper():\n    pass\ndef main(a):\n    pass\n"
                  for t in TARGETS})
    repo = _tree(tmp_path, files)
    parent = kpop.reach(repo, files=sorted(files))
    got = {t for t in TARGETS if f"tools/{t}.py" in parent}
    assert got == {"d_argv", "e_main", "f_bound", "h_sh"}, (
        "credited as executed: " + ", ".join(sorted(got)))


def test_a_reachable_reason_is_true():
    """A `[not_wired]` reason that says "reachable" is a claim this census can check.

    It rotted twice before anything checked it: evict_witness was "reachable" through a
    string in cart_coverage_census's classification table while it was dead, and when
    that string moved, sfx_audition inherited the same false credit.
    """
    parent = kpop.reach(lane.REPO)
    false = sorted(name for name, reason in _manifest()["not_wired"].items()
                   if reason.lower().startswith("reachable")
                   and "tools/" + name not in parent)
    assert false == [], (
        "[not_wired] reasons claim 'reachable' for tools nothing executes: " + ", ".join(false))
