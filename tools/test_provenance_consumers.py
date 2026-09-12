"""Every migrated `--built-after` gate asks tools/artifact_provenance.py, and they agree
(LS-1a step 3, 2026-09-12).

RUNNER: build.sh's PRE-build tool-suite lane, build-fatal, every shape. Nothing here reads
a working-tree artifact: each gate is driven as a SUBPROCESS, exactly as build.sh calls
it, over a real plain-demo pair the installed assembler builds into a directory this file
owns (tools/provenance_fixtures.py).

WHAT IS ASSERTED, per gate:
  * FRESH control: over a fresh pair the gate prints the primitive's `provenance FRESH`
    line, i.e. it reached the primitive with the right two paths and got a yes. What the
    gate then says about a DEMO ROM is its own business and is not asserted.
  * MISPAIRED: the listing with another build's byte-identical ROM -> exit 2, the shared
    `provenance NOT FRESH` wording, and the `DIGEST-ROM names` row. Only the primitive's
    path rule can see this (the CRCs are equal), so a gate that kept a private mtime
    check, or skipped the call, stays green here.
  * NO SECTION: the real ROM with a copy of its listing stripped of `DIGEST-` lines ->
    exit 2, whatever the mtime.
  * THE VERDICT DOES NOT DEPEND ON --gate: every gate that takes --gate is run with and
    without it, and a stale pair is 2 both ways. Before this parcel instashield_gate,
    loop_crossover_gate and bganim_room exited 1 on a stale pair, and sprite_tilt_gate
    exited 0 without --gate; a missing artifact there was 0 without --gate too.

The consumer classes a mutation must break are covered here (the ten gates that print
through `gate_check`, and bganim_room, which raises through `check_provenance`); the
conftest lane is covered by tools/test_needs_build_lane.py, which drives a COPY of the
shipping conftest and primitive.
"""

import os
import subprocess
import sys
import time

import pytest

TOOLS = os.path.dirname(os.path.abspath(__file__))
AEON = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)

import provenance_fixtures as pf  # noqa: E402

#: gate -> (the arguments build.sh passes beyond --lst/--rom/--built-after, adjusted to a
#: demo pair, whether the gate takes --gate). The eleven are build.sh's `--built-after
#: "${SIGIL_T0}"` call sites; tools/test_provenance_consumers.py::
#: test_the_population_is_build_sh_s asserts the set against build.sh itself.
GATES = {
    "row_remap_gate": (["--game", "demo"], False),
    "anim_frame_bound": (["--game", "demo"], True),
    "editor_palette_golden": ([], False),
    "band_drift_golden": ([], False),
    "plane_base_swap_gate": (["--shape", "release"], False),
    "reels_gate": (["--shape", "release"], False),
    "plane_role_swap_gate": (["--shape", "release"], False),
    "bganim_room": ([], True),
    "sprite_tilt_gate": ([], True),
    "instashield_gate": ([], True),
    "loop_crossover_gate": ([], True),
}


@pytest.fixture(scope="module")
def pairs(tmp_path_factory):
    d = tmp_path_factory.mktemp("consumers")
    t0 = int(time.time())
    try:
        rom, lst = pf.build_demo(str(d / "real"))
        other_rom, _ = pf.build_demo(str(d / "other"))
    except pf.NoAssembler as e:
        pytest.fail(str(e))
    bare = pf.rewrite(lst, str(d / "bare.lst"), lambda t: "".join(
        ln for ln in t.splitlines(keepends=True) if not ln.startswith("DIGEST-")))
    return {"t0": t0, "rom": rom, "lst": lst, "other_rom": other_rom, "bare": bare}


def run_gate(gate, lst, rom, t0, extra):
    p = subprocess.run([sys.executable, os.path.join(TOOLS, gate + ".py"),
                        "--lst", lst, "--rom", rom, "--built-after", str(t0), *extra],
                       cwd=AEON, capture_output=True, text=True, timeout=600)
    return p.returncode, p.stdout + p.stderr


def _gate_variants(gate):
    extra, takes_gate = GATES[gate]
    if not takes_gate:
        return [extra]
    return [extra, extra + ["--gate"]]


@pytest.mark.parametrize("gate", sorted(GATES))
def test_a_fresh_pair_reaches_the_primitive_and_reads_fresh(gate, pairs):
    rc, out = run_gate(gate, pairs["lst"], pairs["rom"], pairs["t0"], GATES[gate][0])
    assert "provenance FRESH" in out, out[-3000:]
    assert "provenance NOT FRESH" not in out, out[-3000:]


@pytest.mark.parametrize("gate", sorted(GATES))
def test_a_mispaired_rom_is_exit_2_with_and_without_gate(gate, pairs):
    for extra in _gate_variants(gate):
        rc, out = run_gate(gate, pairs["lst"], pairs["other_rom"], pairs["t0"], extra)
        assert rc == 2, (extra, out[-3000:])
        assert "provenance NOT FRESH" in out and "DIGEST-ROM names" in out, (extra, out[-3000:])


@pytest.mark.parametrize("gate", sorted(GATES))
def test_a_listing_with_no_section_is_exit_2(gate, pairs):
    for extra in _gate_variants(gate):
        rc, out = run_gate(gate, pairs["bare"], pairs["rom"], pairs["t0"], extra)
        assert rc == 2, (extra, out[-3000:])
        assert "NO `DIGEST-` section" in out, (extra, out[-3000:])


def test_sprite_tilt_gate_is_not_green_on_a_missing_artifact_without_gate(pairs, tmp_path):
    """The footgun the booking named, closed at both of its sites: without --gate a
    missing artifact used to return 0."""
    p = subprocess.run([sys.executable, os.path.join(TOOLS, "sprite_tilt_gate.py"),
                        "--lst", str(tmp_path / "absent.lst"), "--rom", pairs["rom"]],
                       cwd=AEON, capture_output=True, text=True)
    assert p.returncode == 2, p.stdout + p.stderr


def test_the_population_is_build_sh_s():
    """The GATES table is derived from build.sh, not remembered: every script build.sh
    hands `--built-after "${SIGIL_T0}"` is here, and nothing else is. A new consumer
    that is not added here goes red, and so does one build.sh stops calling."""
    import re
    with open(os.path.join(AEON, "build.sh"), encoding="utf-8") as f:
        text = f.read()
    calls = set()
    # each gate invocation is one `gate strict "<name>.py" python3 ...` command that may
    # continue over backslash-newlines
    for m in re.finditer(r'python3 "\$\{TOOLS\}/(\w+)\.py"((?:[^\n]*\\\n)*[^\n]*)', text):
        if "--built-after" in m.group(2):
            calls.add(m.group(1))
    assert calls, "found no --built-after call in build.sh; the parse drifted"
    assert calls == set(GATES), ("build.sh's --built-after gates %s != this table %s"
                                 % (sorted(calls), sorted(GATES)))
