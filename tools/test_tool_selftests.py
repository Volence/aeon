#!/usr/bin/env python3
"""test_tool_selftests — give the tools' own `test` / `--selftest` entry points a RUNNER.

WHY THIS FILE EXISTS (LS-15, 2026-09-07).

Several tools in this directory carry a self-test suite behind a CLI subcommand
(`python3 tools/<tool>.py test`) or a proof flag (`--selftest`). `build.sh`'s pytest
lane collects `test_*.py` FILES, so a suite that lives behind an argv branch inside a
non-`test_` file is outside that sweep entirely, no matter how many assertions it has.
This file is the bridge: one pytest row per entry point, each running the real CLI as a
subprocess, so it is the SHIPPED entry point that is exercised and not an importable
copy of it. If the argv dispatch breaks, these rows go red; an `import` + direct call
would not have noticed.

WHAT THE SWEEP ACTUALLY FOUND, because the item this closes over-counted and the
correction is the useful part. Of the eight entry points named as unreachable:

  * FOUR were already reachable -- `s4lz`, `dplc_layout`, `ojz_strip_gen` and
    `collision_pipeline` are run by `./test.sh` sections 1, 3, 6 and 6b. The claim that
    `collision_pipeline`'s name "appears in no .sh at all" is false; it is `test.sh:229`.
    But `./test.sh` runs two full ROM builds and needs an out-of-repo `replay_runner`
    binary, and nothing schedules it, so it is a hand runner and these suites were
    reaching no automated gate. They are here as well as there.
  * ONE was reachable and automated -- `palette_variant_gate.py` is invoked by
    `tools/effects_gates.py:941`, i.e. by the effects ritual and the nightly. It is NOT
    in this file: it boots a headless emulator and belongs where the emulator lanes are.
  * ONE was reachable in substance -- `state_ram.py test` duplicates
    `tools/test_state_ram.py`, which this lane already runs. The CLI path itself was
    still unreached, which is what the row below adds.
  * TWO were genuinely unreached by anything -- `ojz_block_gen.py test` and
    `ojz_entity_gen.py test`.
  * And `ojz_entity_gen.py test` WAS RED, and had been since Parcel K3 run A converted
    its emitter from AS text to native `.emp` `pub data` items without updating the
    assertions. Nothing ran it, so nothing said so. Fixed in that file (see
    `test_emit_section_shapes`'s docstring) rather than here; this row is what would
    have caught it.

WHY THE PRE-BUILD LANE FOR ALL BUT ONE. Every row here except `dplc_straddle` is pure
Python over committed inputs, reads no build artifact, and costs well under a second
(measured 2026-09-07: s4lz 0.09, dplc_layout 0.01, ojz_block_gen 0.11, state_ram 0.07,
ojz_entity_gen 0.02, collision_pipeline 0.12, ojz_strip_gen 0.54, replay_pack 0.02,
prose_bound_sweep 0.02 -- about 1.0 s in total against a ~150 s canonical build). That
is the same argument build.sh:598 already makes for the lane, so they join it rather
than earning a new one.

WHAT IS DELIBERATELY *NOT* WIRED, and the reason belongs here where the next person
looks for it:

  * `tools/dma_defer_headroom.py --selftest` MUTATES COMMITTED SOURCE -- it rewrites
    `constants.emp`, `buffers.emp` and `dma_queue.emp` in place, one arm at a time, and
    restores them in a `finally`. It was VERIFIED still honest on 2026-09-07 (all three
    arms red, restore check green, tree clean afterwards), so `build.sh:1171`'s comment
    is accurate and not stale. It stays hand-run: a lane that edits tracked files would
    poison a concurrent build or an interrupted run, which is the incident class this
    tree already paid for once (tools lens sweep D8, a test that rewrote committed ROM
    data). Run it by hand: `python3 tools/dma_defer_headroom.py --lst s4.lst --selftest`.
  * The six emulator-backed poison arms -- `aether_instance --poison-legacy`,
    `dplc_coherence_witness --poison`, `staging_lifetime_timeline --poison`,
    `parallax_cost_probe --poison-vscroll`, `tick_variance_probe --poison`,
    `vsplit_landing_gate --poison`. Each boots a headless emulator, so by the same rule
    that keeps the effects gates out of build.sh they cannot come here. Booked in
    DEFERRED_WORK against the nightly.

THE DONOR ROWS SKIP, AND THAT IS THE TREE'S OWN CONVENTION, NOT A DODGE.
`ojz_strip_gen` and `collision_pipeline` read the out-of-repo sonic_hack donor -- MEASURED,
not inferred: with `AEON_SONIC_HACK_DIR` pointed at a nonexistent path both exit 1 while
the other four exit 0. `build.sh` deliberately depends on no donor, so hard-failing here
would make the ROM unbuildable on a donor-less checkout. They follow
`tools/test_instashield_art.py`'s tier-2 pattern: skip by name, printing the donor path
that was looked for. On any machine that has the donor -- the owner's, and the nightly's
-- they run and can fail.
"""

import os
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
AEON = os.path.normpath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)

from suite_paths import suite_path  # noqa: E402

#: Spelled through suite_paths for test_instashield_art.py's reason: a plain
#: `<checkout>/../sonic_hack` resolves to `.claude/worktrees/sonic_hack` from a
#: worktree, and the donor rows would then skip for a path bug that reads as
#: "donor not installed".
SONIC_HACK = os.environ.get("AEON_SONIC_HACK_DIR", str(suite_path("sonic_hack")))

#: The one artifact-reading row's inputs. Named here so the marker and the guard
#: cannot drift apart.
STRADDLE_LST = "s4.lst"
STRADDLE_ROM = "s4.bin"


def _run(*args):
    """Run a tool CLI from the repo root and return the completed process.

    cwd is pinned to AEON rather than inherited: several of these tools resolve
    committed data relative to the working directory, and a lane that only passes
    when pytest happens to be invoked from the root is a lane that will one day
    pass for the wrong reason.
    """
    return subprocess.run([sys.executable] + list(args), cwd=AEON,
                          capture_output=True, text=True)


def _assert_green(proc, label):
    assert proc.returncode == 0, (
        "%s exited %d.\n--- stdout ---\n%s\n--- stderr ---\n%s"
        % (label, proc.returncode, proc.stdout[-4000:], proc.stderr[-4000:]))


# ---------------------------------------------------------------------------
# `<tool>.py test` subcommands -- no donor, no build artifact.
# ---------------------------------------------------------------------------

def test_s4lz_selftests():
    """25 compression cases incl. the dictionary forms. This is the whole structural
    net for engine/compression/s4lz.emp, which carries zero `ensure` sites."""
    p = _run("tools/s4lz.py", "test")
    _assert_green(p, "tools/s4lz.py test")
    assert "0 failed" in p.stdout, p.stdout


def test_dplc_layout_selftests():
    p = _run("tools/dplc_layout.py", "test")
    _assert_green(p, "tools/dplc_layout.py test")
    assert "0 failed" in p.stdout, p.stdout


def test_ojz_block_gen_selftests():
    """32 assertions over the block packer, incl. the full round-trip through
    s4lz. Reached by NOTHING before this row."""
    p = _run("tools/ojz_block_gen.py", "test")
    _assert_green(p, "tools/ojz_block_gen.py test")
    assert "All tests passed" in p.stdout, p.stdout


def test_ojz_entity_gen_selftests():
    """23 assertions over the entity emitter. Reached by NOTHING before this row,
    and RED when first run (see that file's test_emit_section_shapes docstring)."""
    p = _run("tools/ojz_entity_gen.py", "test")
    _assert_green(p, "tools/ojz_entity_gen.py test")
    assert "All tests passed" in p.stdout, p.stdout


def test_state_ram_selftests():
    """The CLI path. Its ASSERTIONS are also covered by tools/test_state_ram.py, which
    imports the module and re-asserts the same refusals through `SR._synth` -- so what
    this row adds is the argv dispatch and `run_tests` itself, neither of which the
    pytest wrapper touches."""
    p = _run("tools/state_ram.py", "test")
    _assert_green(p, "tools/state_ram.py test")
    assert "all self-tests passed" in p.stdout, p.stdout


# ---------------------------------------------------------------------------
# Proof harnesses -- pure, and each returns nonzero when its proof fails.
# ---------------------------------------------------------------------------

def test_replay_pack_selftest():
    """Round-trip + reject: RLE splitting past 256, checkpoint interleave at ring
    boundaries, SOCD rejection, unknown-opcode rejection."""
    p = _run("tools/replay_pack.py", "--selftest")
    _assert_green(p, "tools/replay_pack.py --selftest")
    assert "PASS" in p.stdout, p.stdout


def test_prose_bound_sweep_self_test():
    """The instrument's POSITIVE CONTROL. An empty sweep and a dead predicate are the
    same artifact, so a sweep nobody has seen find anything is not evidence."""
    p = _run("tools/prose_bound_sweep.py", "--self-test")
    _assert_green(p, "tools/prose_bound_sweep.py --self-test")
    assert "INSTRUMENT WORKS" in p.stdout, p.stdout


# ---------------------------------------------------------------------------
# Donor-dependent rows (tier 2, tools/test_instashield_art.py's pattern).
# ---------------------------------------------------------------------------

def _require_donor():
    if not os.path.isdir(SONIC_HACK):
        pytest.skip("donor tree absent (AEON_SONIC_HACK_DIR=%s): this row reads the "
                    "sonic_hack collision/art donor" % SONIC_HACK)


def test_ojz_strip_gen_selftests():
    """78 assertions in the self-test region, incl. the stress-uniquify determinism
    and parent-match rows. Reads the donor (measured: exits 1 without it)."""
    _require_donor()
    p = _run("tools/ojz_strip_gen.py", "test")
    _assert_green(p, "tools/ojz_strip_gen.py test")
    assert "All tests passed" in p.stdout, p.stdout


def test_collision_pipeline_selftests():
    """73 assertions, ending in a real-data measurement over every committed section
    layout. Reads the donor (measured: exits 1 without it)."""
    _require_donor()
    p = _run("tools/collision_pipeline.py", "test")
    _assert_green(p, "tools/collision_pipeline.py test")
    assert "All tests passed" in p.stdout, p.stdout


# ---------------------------------------------------------------------------
# The one artifact-reading row -- POST-SIGIL lane.
# ---------------------------------------------------------------------------

@pytest.mark.needs_build(STRADDLE_LST, STRADDLE_ROM)
def test_dplc_straddle_selftest_proves_its_gate_red():
    """build.sh:1138 asserts that `dplc_straddle.py --selftest` "proves the gate red by
    searching for a shift that trips it". VERIFIED 2026-09-07 -- it does, seven arms
    including two independent red proofs and an explicit unmeasurable proof.

    It is here rather than beside the plain `test` subcommands because it reads the
    LISTING and the ROM, which is exactly what `@pytest.mark.needs_build` is for: the
    pre-build lane deselects it, build.sh's post-sigil lane runs it against the
    artifacts THIS invocation emitted, and the DEBUG and demo shapes defer it because
    they do not write s4.lst/s4.bin. The nightly builds the release shape, so it runs
    there with zero deferrals.

    It is safe in a lane in a way `dma_defer_headroom --selftest` is not: it has no
    file writes and no subprocess at all -- every arm shifts an art base in an
    in-memory model. Measured 2.53 s, the most expensive row in this file.
    """
    p = _run("tools/dplc_straddle.py", "--lst", STRADDLE_LST,
             "--rom", STRADDLE_ROM, "--selftest")
    _assert_green(p, "tools/dplc_straddle.py --selftest")
    # Its own verdict line, not just the exit status: `report()` returns 0 on several
    # paths and the verdict is what says the RED arms actually fired.
    assert "the gate is green here and provably red elsewhere" in p.stdout, p.stdout
