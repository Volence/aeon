"""The `tools/freeze_preflight.sh` step-1 classifier, tested on BOTH of its arms.

    python3 -m pytest tools/test_freeze_preflight.py -q

WHY THIS EXISTS. On 2026-09-09 the pre-flight stopped with *"repin_pins failed for
a reason that is NOT staleness"* while the actual panic was `src/pins.rs is STALE
against the live listings` — the exact string it greps for. Two causes, and the
second is the one this file is mostly about:

  1. Step 1 did not thread `AEON_DIR`, so sigil's reference-dependent gate resolved
     the SIBLING MAIN CHECKOUT and the script classified a result measured against a
     different tree than the one being frozen.
  2. The else-branch printed a CATEGORY and not the text it matched on, so the wrong
     reason travelled: a reader carried "investigate a cross-seam symbol break"
     forward when the truth was "your parcel moved bytes, as intended".

**A CLASSIFIER THAT HAS ONLY EVER SEEN ONE CASE IS NOT TESTED**, which is why every
test here comes in a pair: a genuine staleness failure AND a genuine non-staleness
failure, each asserted to produce its own verdict and its own evidence.

WHAT THIS DOES NOT DO, AND WHY THAT IS DELIBERATE. It never runs cargo. The header of
`freeze_preflight.sh` records that `cargo test` in the shared sigil checkout RELINKS
`target/release/sigil` — the binary other lanes pin their freezes against — so a test
that ran the real gate would be the single biggest relinker on the machine every time
anyone built this repo. A stub `cargo` on PATH is put in its place, and the script
cannot tell the difference: its whole step-1 contract is (exit status, log text) in
and (verdict, evidence, exit status) out.

CONSEQUENCE, STATED SO NOBODY READS MORE INTO A GREEN THAN IT CARRIES: these tests
pin the SCRIPT's behaviour given a log. They do not pin sigil's wording. If sigil ever
changes the staleness sentence, this file stays green while the real pre-flight
misclassifies — the fixture text below is transcribed from
`crates/sigil-harness/src/repin.rs::stale_pins_message` (read 2026-09-09), and that
transcription is the residual risk. The one thing keeping it honest is that the same
literal appears in the script's grep, so a drift breaks BOTH, loudly, on the next
real run.
"""

import os
import subprocess
import textwrap
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "tools" / "freeze_preflight.sh"

# Transcribed from sigil `crates/sigil-harness/src/repin.rs:1432` (stale_pins_message)
# plus the panic framing cargo wraps it in. This is the EXPECTED state for a byte-mover.
STALE_LOG = textwrap.dedent(
    """\
    running 2 tests
    test generated_pins_match_the_hand_typed_baseline ... ok
    test pins_rs_is_current ... FAILED

    failures:

    ---- pins_rs_is_current stdout ----

    thread 'pins_rs_is_current' panicked at crates/sigil-harness/tests/repin_pins.rs:77:9:
    src/pins.rs is STALE against the live listings.

    32 pin(s) moved, 0 added, 0 removed.

    regenerate with:
      cargo run --release -p sigil-harness --bin repin -- --aeon /some/aeon

    failures:
        pins_rs_is_current

    test result: FAILED. 1 passed; 1 failed; 0 ignored
    """
)

# A GENUINE NON-STALENESS FAILURE, and not an invented one: `repin_pins.rs` panics with
# `plain resolve: {e}` when sigil cannot resolve the sonic4 shape at all (a source error
# in the aeon tree, a missing module, a broken map). That failure reaches the same arm
# and is the case the else-branch exists to describe.
NOT_STALE_LOG = textwrap.dedent(
    """\
    running 2 tests
    test generated_pins_match_the_hand_typed_baseline ... ok
    test pins_rs_is_current ... FAILED

    failures:

    ---- pins_rs_is_current stdout ----

    thread 'pins_rs_is_current' panicked at crates/sigil-harness/tests/repin_pins.rs:40:9:
    plain resolve: [Error] games/sonic4/objects/test_solid.emp:12: unknown name Spring_Bounce

    failures:
        pins_rs_is_current

    test result: FAILED. 1 passed; 1 failed; 0 ignored
    """
)

CLEAN_PORTS_LOG = textwrap.dedent(
    """\
    running 12 tests
    test result: ok. 12 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out
    """
)


def _make_stub_cargo(state: Path) -> Path:
    """A `cargo` that replays canned (log, rc) pairs and records the env it saw.

    Recording `AEON_DIR` per invocation is the whole threading assertion: the script's
    banner is a CLAIM about which tree it will measure, and this file is the only place
    that can check the claim against what the child process actually received.
    """
    bindir = state / "bin"
    bindir.mkdir(parents=True)
    stub = bindir / "cargo"
    stub.write_text(
        textwrap.dedent(
            f"""\
            #!/usr/bin/env bash
            S={state}
            n=$(cat "$S/count" 2>/dev/null || echo 0)
            n=$((n+1))
            echo "$n" > "$S/count"
            {{
              echo "invocation=$n"
              echo "AEON_DIR=${{AEON_DIR-<UNSET>}}"
              echo "cwd=$PWD"
            }} >> "$S/env.log"
            [ -f "$S/log$n" ] && cat "$S/log$n"
            exit "$(cat "$S/rc$n" 2>/dev/null || echo 0)"
            """
        )
    )
    stub.chmod(0o755)
    return bindir


def _run(tmp_path, *, step1_log, step1_rc, step2_log=CLEAN_PORTS_LOG, step2_rc=0,
         aeon_dir=None):
    state = tmp_path / "stub"
    state.mkdir(parents=True)
    bindir = _make_stub_cargo(state)
    (state / "log1").write_text(step1_log)
    (state / "rc1").write_text(str(step1_rc))
    (state / "log2").write_text(step2_log)
    (state / "rc2").write_text(str(step2_rc))

    sigil = tmp_path / "fake-sigil"
    sigil.mkdir(exist_ok=True)

    env = dict(os.environ)
    env["PATH"] = f"{bindir}:{env['PATH']}"
    env["SIGIL_DIR"] = str(sigil)
    env.pop("AEON_DIR", None)
    if aeon_dir is not None:
        env["AEON_DIR"] = str(aeon_dir)

    proc = subprocess.run(
        ["bash", str(SCRIPT)],
        capture_output=True, text=True, env=env, cwd=str(tmp_path), timeout=120,
    )
    seen = (state / "env.log").read_text() if (state / "env.log").exists() else ""
    return proc, seen


# ── the classifier, both arms ────────────────────────────────────────────────────

def test_a_staleness_failure_is_classified_stale_and_ships_the_line_it_matched(tmp_path):
    proc, _ = _run(tmp_path, step1_log=STALE_LOG, step1_rc=101)
    out = proc.stdout
    assert "pins are STALE" in out, out
    assert "NOT staleness" not in out, out
    # The verdict is not enough: the arm must show the text it was reached from.
    assert "matched on:" in out, out
    assert "| src/pins.rs is STALE against the live listings." in out, out
    # A stale step 1 is not a stop — the run continues into step 2.
    assert "step 2/2" in out, out
    assert proc.returncode == 0, (proc.returncode, out)


def test_a_non_staleness_failure_stops_and_prints_the_failure_text_not_a_category(tmp_path):
    proc, _ = _run(tmp_path, step1_log=NOT_STALE_LOG, step1_rc=101)
    out = proc.stdout
    assert "NOT staleness" in out, out
    assert "pins are STALE" not in out, out
    # THE DEFECT THIS PINS: the category alone travelled, and it was wrong.
    assert "the text this classification was made on" in out, out
    assert "| plain resolve: [Error]" in out, out
    assert "unknown name Spring_Bounce" in out, out
    # It names the failing test too (the chain-199 rule this file inherits).
    assert "pins_rs_is_current" in out, out
    # And it stops before step 2 rather than reporting on ports it cannot classify.
    assert "step 2/2" not in out, out
    assert proc.returncode == 2, (proc.returncode, out)


def test_the_two_arms_do_not_print_each_others_evidence(tmp_path):
    """The pair, asked as one question: a classifier with one case is not tested."""
    stale, _ = _run(tmp_path / "a", step1_log=STALE_LOG, step1_rc=101)
    other, _ = _run(tmp_path / "b", step1_log=NOT_STALE_LOG, step1_rc=101)
    # Compared over the EVIDENCE lines (the `| ` prefix), not the whole stdout: the
    # non-staleness arm quotes the grep literal on purpose, in the sentence saying what
    # did NOT match. That is the arm being explicit about its own reasoning, and a test
    # that forbade the literal outright would forbid the fix.
    def evidence(p):
        return [l for l in p.stdout.splitlines() if l.strip().startswith("| ")]
    assert not any("plain resolve" in l for l in evidence(stale)), evidence(stale)
    assert not any("is STALE against the live listings" in l for l in evidence(other)), evidence(other)
    assert "matched on:" not in other.stdout, other.stdout
    assert (stale.returncode, other.returncode) == (0, 2)


def test_a_green_step_1_says_pins_are_current(tmp_path):
    proc, _ = _run(tmp_path, step1_log="test result: ok. 2 passed; 0 failed\n", step1_rc=0)
    assert "pins are CURRENT" in proc.stdout, proc.stdout
    assert proc.returncode == 0, (proc.returncode, proc.stdout)


def test_a_run_that_produced_no_output_says_so_rather_than_printing_nothing(tmp_path):
    """The empty-log case: a cargo that could not start leaves the arm with nothing to
    show, and an evidence block that renders blank reads as 'no evidence exists'."""
    proc, _ = _run(tmp_path, step1_log="", step1_rc=101)
    assert "NOT staleness" in proc.stdout
    assert "the run produced NO output at all" in proc.stdout, proc.stdout
    assert proc.returncode == 2


# ── the threading, checked at the child process and not at the banner ────────────

def test_aeon_dir_is_threaded_into_both_cargo_runs(tmp_path):
    aeon = tmp_path / "chosen-aeon"
    aeon.mkdir()
    proc, seen = _run(tmp_path, step1_log=STALE_LOG, step1_rc=101, aeon_dir=aeon)
    # BOTH invocations, because half a thread is the same defect one step later.
    assert seen.count(f"AEON_DIR={aeon}") == 2, (seen, proc.stdout)
    assert "<UNSET>" not in seen, seen
    assert f"aeon tree  {aeon}" in proc.stdout, proc.stdout


def test_an_unset_aeon_dir_falls_back_to_this_scripts_own_checkout_and_says_so(tmp_path):
    """The default is the tree the script lives in, not a sibling: you run
    `<tree>/tools/freeze_preflight.sh` from the tree you are freezing. It is still a
    guess, so it is announced as loudly as an unset SIGIL_DIR."""
    proc, seen = _run(tmp_path, step1_log=STALE_LOG, step1_rc=101, aeon_dir=None)
    assert f"AEON_DIR={REPO}" in seen, seen
    assert "AEON_DIR was UNSET" in proc.stdout, proc.stdout
    assert "<UNSET>" not in seen, seen


def test_the_banner_names_both_subject_trees(tmp_path):
    aeon = tmp_path / "chosen-aeon"
    aeon.mkdir()
    sigil_named = "fake-sigil"
    proc, _ = _run(tmp_path, step1_log=STALE_LOG, step1_rc=101, aeon_dir=aeon)
    out = proc.stdout
    assert "SUBJECTS" in out, out
    assert sigil_named in out, out
    assert str(aeon) in out, out
    # The shapes line exists so a step-2 green is readable: a port gate whose ROM is
    # absent SKIPS green, and this aeon tree has none of the four.
    assert "-s4.bin" in out and "-demo.debug.bin" in out, out


def test_a_missing_aeon_tree_is_a_could_not_run_and_names_the_variable(tmp_path):
    proc, _ = _run(tmp_path, step1_log=STALE_LOG, step1_rc=101,
                   aeon_dir=tmp_path / "does-not-exist")
    assert proc.returncode == 2, (proc.returncode, proc.stdout)
    assert "no aeon tree at" in proc.stdout, proc.stdout
    assert "set AEON_DIR" in proc.stdout, proc.stdout


# ── the failing-test list, which used to count cargo's own summary line ──────────

def test_step_1_does_not_print_cargos_summary_line_as_a_failing_test_name(tmp_path):
    """`^test .* FAILED` matches `test result: FAILED. 1 passed; 1 failed; …`.

    Measured 2026-09-09. The summary line begins `test ` and ends in FAILED, so the
    old pattern listed it as a failing test NAME — and step 2 counted it.
    """
    proc, _ = _run(tmp_path, step1_log=NOT_STALE_LOG, step1_rc=101)
    named = [l.strip() for l in proc.stdout.splitlines()
             if l.startswith("    test ")]
    assert named == ["test pins_rs_is_current ... FAILED"], named


PORTS_ONE_REAL_FAILURE = textwrap.dedent(
    """\
    running 12 tests
    test boot_port::region_bytes_match ... FAILED

    failures:
        boot_port::region_bytes_match

    test result: FAILED. 11 passed; 1 failed; 0 ignored; 0 measured; 0 filtered out
    """
)


def test_step_2_counts_one_failure_when_one_test_failed(tmp_path):
    """The chain-199 defect, still live until 2026-09-09: count and names were derived
    from one list so they AGREED — on a number inflated by one per failing binary."""
    proc, _ = _run(tmp_path, step1_log=STALE_LOG, step1_rc=101,
                   step2_log=PORTS_ONE_REAL_FAILURE, step2_rc=101)
    assert "freeze_preflight: 1 port test failure(s)" in proc.stdout, proc.stdout
    assert "test result" not in proc.stdout.split("failing test(s):")[1].split("distinct")[0], \
        proc.stdout


PORTS_DOCTEST_FAILURE = textwrap.dedent(
    """\
    running 3 tests
    test src/lib.rs - resolve::pins (line 12) ... FAILED

    failures:
        src/lib.rs - resolve::pins (line 12)

    test result: FAILED. 2 passed; 1 failed; 0 ignored; 0 measured; 0 filtered out
    """
)


def test_step_2_does_not_DROP_a_failing_test_whose_name_contains_spaces(tmp_path):
    """The correction sigil caught within an hour of the overcount fix landing.

    Excluding cargo's summary line by NARROWING the name to `[^ ]+` also excludes every
    doctest, which cargo spells `test src/lib.rs - m::f (line 12) ... FAILED` -- spaces and
    all. That trades a defect that INFLATES the count for one that HIDES failures, which is
    the worse direction. The end anchor is what excludes the summary (it continues past
    FAILED with its counts) while leaving the name free to contain spaces.

    Red-first against the narrowed pattern: it reports 0 failures on this log and names
    none, while the log carries one real failure.
    """
    proc, _ = _run(tmp_path, step1_log=STALE_LOG, step1_rc=101,
                   step2_log=PORTS_DOCTEST_FAILURE, step2_rc=101)
    assert "freeze_preflight: 1 port test failure(s)" in proc.stdout, proc.stdout
    assert "src/lib.rs - resolve::pins (line 12)" in proc.stdout, proc.stdout


@pytest.mark.parametrize("literal", [
    "is STALE against the live listings",
])
def test_the_grep_literal_is_the_one_sigil_emits(literal):
    """The single point of coupling to sigil, kept visible.

    The script's classification is a grep for this literal, and the fixture above is
    a transcription of sigil's own `stale_pins_message`. Asserting they are the same
    string here does not verify sigil — nothing in this repo can — but it makes the
    coupling one grep rather than two independent copies drifting apart.
    """
    assert literal in SCRIPT.read_text()
    assert literal in STALE_LOG
