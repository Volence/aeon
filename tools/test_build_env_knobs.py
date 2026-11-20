#!/usr/bin/env python3
"""build.sh's environment knobs, graded by EXECUTING the blocks build.sh runs.

  EMITTER   build.sh named the assembler's revision and recorded nothing about SIGIL_EMIT, so a
            split pair (sigil and emit_sound_blob from different revisions) was found by a peer
            rather than by any build's own output (docs/DEFERRED_WORK.md, the shared-emitter
            row, 2026-09-12). emit_sound_blob takes `--aeon` and `--out-dir` and nothing else
            (no `--version`), so its md5 is its identity; build.sh now prints it beside the
            `Assembler:` line.

  NO_LINT   An exported `NO_LINT=1` was IGNORED until 2026-09-12: build.sh set `NO_LINT=0`
            unconditionally before parsing flags, so only `-nl`/`--no-lint` (and FAST) skipped
            the lint lanes, while tools/landing_build.sh already refused an EXPORTED NO_LINT and
            CLAUDE.md, docs/OVERSEER-REFERENCE.md and several test docstrings named `NO_LINT=1`
            as an environment knob. Ruling (aeon overseer, 2026-09-12): honour the env var,
            default 0 when unset, and make the skip LOUD. The `-nl` path used to print nothing,
            so both routes now print a banner at the top AND a closing one at the bottom of the
            build. A value other than 0 or 1 is refused rather than guessed at.

HOW. Each block sits between `# >>> NAME` / `# <<< NAME` markers in build.sh, which say the
markers are load-bearing. The block is lifted and run under `bash -euo pipefail` (build.sh's
own `set` line) with a controlled environment. build.sh itself is NEVER invoked: a test in
build.sh's own pytest lane that calls build.sh against the real repo recurses (DEFERRED_WORK,
side findings of the 2026-09-11 lens-tools parcel, item (c)). Expected md5s are computed here
with hashlib from a file this test writes, never copied from a pin.

WHAT IT DOES NOT COVER: that the lanes build.sh guards with `NO_LINT` are the ones the banner
names. The banner lists them by hand; this file checks that the knob reaches NO_LINT and that
the skip is announced, not which `if` blocks read it.

  PROJECT   (G0b Task 8 cut demo over, Task 10 sonic4) every game is built from its
            description: the row is `release`/`debug` by DEBUG, `stress-evict`/`stress-art`
            under STRESS_EVICT/STRESS_ART, or SHAPE=<row> (a non-fixture row with an
            `[outputs]` stem, whose stem becomes ROM_NAME); DEBUG, CRASH_REPORT,
            SOUND_DRIVER_ENABLED, SOUND_DEBUG_HOTKEYS and SOUND_DBG_MIRROR come from the row
            (tools/game_shape_feature.py --shell), and an environment value that disagrees
            with the description is refused.

RUNNER: build.sh's pre-build tool-suite lane (`pytest tools -m "not needs_build"`), build-fatal.
Source only, no marker. A NO_LINT=1 build skips that lane and so skips this file too;
tools/landing_build.sh refuses NO_LINT, so a landing run always reaches it.
"""
import hashlib
import os
import subprocess
import tempfile

TOOLS = os.path.dirname(os.path.abspath(__file__))
BUILD_SH = os.path.join(os.path.dirname(TOOLS), "build.sh")


def _block(name):
    with open(BUILD_SH, "r", encoding="utf-8") as f:
        src = f.read()
    begin, end = "# >>> " + name, "# <<< " + name
    assert src.count(begin) == 1 and src.count(end) == 1, (
        "build.sh must carry exactly one %r / %r marker pair; this test lifts and runs the "
        "block between them" % (begin, end))
    i = src.index(begin) + len(begin)
    return src[i:src.index(end, i)]


def _run(script, args=(), **env_over):
    # Every knob a test controls is dropped from the inherited environment, so a test that
    # passes `DEBUG=None` means "unset" even inside a DEBUG=1 build (landing_build.sh runs
    # this suite inside each shape's build.sh: its s4.debug lane inherited DEBUG=1 and the
    # demo-shape rows read `debug` where they asked for `release`, G0b Task 9a).
    env = {k: v for k, v in os.environ.items()
           if k not in ("NO_LINT", "FAST", "SIGIL_EMIT", "SOUND_DRIVER_ENABLED", "DEBUG", "GAME",
                        "SHAPE", "ROM_NAME", "CRASH_REPORT", "SOUND_DEBUG_HOTKEYS",
                        "SOUND_DBG_MIRROR", "STRESS_EVICT", "STRESS_ART", "S2CLIP",
                        "STRESS_OBJECTS", "STRESS_SIDEKICK")}
    env.update({k: v for k, v in env_over.items() if v is not None})
    p = subprocess.run(["bash", "-c", "set -euo pipefail\n" + script, "build.sh", *args],
                       env=env, capture_output=True, text=True, timeout=30)
    return p.returncode, p.stdout, p.stderr


# ------------------------------------------------------------------------ NO_LINT
def _no_lint(args=(), **env):
    return _run(_block("NO_LINT_KNOB") + '\necho "RESULT NO_LINT=${NO_LINT}"\n', args, **env)


def _result(out):
    lines = [l for l in out.splitlines() if l.startswith("RESULT NO_LINT=")]
    assert len(lines) == 1, out
    return lines[0].split("=", 1)[1]


def test_unset_means_the_lanes_run_and_nothing_is_announced():
    rc, out, err = _no_lint()
    assert rc == 0, (out, err)
    assert _result(out) == "0"
    assert "LINT LANES SKIPPED" not in out, out


def test_an_exported_NO_LINT_1_is_honoured_and_announced():
    rc, out, err = _no_lint(NO_LINT="1")
    assert rc == 0, (out, err)
    assert _result(out) == "1", "an exported NO_LINT=1 did not reach NO_LINT:\n" + out
    assert "LINT LANES SKIPPED" in out, out
    assert "NO_LINT=1 in the environment" in out, out
    for lane in ("pytest", "effects_budget_check", "emp_expect_fail"):
        assert lane in out, "the banner does not name the %s lane:\n%s" % (lane, out)


def test_the_flag_still_works_and_is_now_announced_too():
    for flag in ("-nl", "--no-lint"):
        rc, out, err = _no_lint(["sonic4", flag])
        assert rc == 0, (flag, out, err)
        assert _result(out) == "1", (flag, out)
        assert "LINT LANES SKIPPED" in out and flag in out, (flag, out)


def test_an_exported_NO_LINT_0_or_empty_runs_the_lanes():
    for v in ("0", ""):
        rc, out, err = _no_lint(NO_LINT=v)
        assert rc == 0, (v, out, err)
        assert _result(out) == "0", (v, out)
        assert "LINT LANES SKIPPED" not in out, (v, out)


def test_an_unrecognised_value_is_refused_not_guessed():
    for v in ("yes", "true", "2"):
        rc, out, err = _no_lint(NO_LINT=v)
        assert rc != 0, "NO_LINT=%s was accepted:\n%s" % (v, out)
        assert "RESULT" not in out, out
        assert "NO_LINT=%s" % v in out, out


def test_the_closing_banner_follows_the_request_and_nothing_else():
    """The closing banner reads NO_LINT_FROM, which only the knob block sets: FAST sets
    NO_LINT=1 on its own later and prints its own two banners."""
    tail = _block("NO_LINT_CLOSING")
    for env, args, want in (({"NO_LINT": "1"}, (), 2), ({}, ("sonic4", "-nl"), 2),
                            ({}, (), 0)):
        rc, out, err = _run(_block("NO_LINT_KNOB") + "\n" + tail, args, **env)
        assert rc == 0, (env, args, out, err)
        got = out.count("LINT LANES SKIPPED")
        assert got == want, (env, args, got, out)
    rc, out, err = _run('NO_LINT=1; NO_LINT_FROM=""\n' + tail)
    assert rc == 0 and "LINT LANES SKIPPED" not in out, (
        "the closing banner fired on NO_LINT alone (FAST's route), not on the request:\n" + out)


# ------------------------------------------------------------------------ EMITTER
def test_the_emitter_md5_is_printed_when_sound_is_on():
    with tempfile.TemporaryDirectory() as d:
        emit = os.path.join(d, "emit_sound_blob")
        with open(emit, "wb") as f:
            f.write(b"not a real emitter, only bytes to hash\n")
        with open(emit, "rb") as f:
            want = hashlib.md5(f.read()).hexdigest()
        rc, out, err = _run(_block("EMITTER_IDENTITY"), SIGIL_EMIT=emit)
        assert rc == 0, (out, err)
        line = [l for l in out.splitlines() if l.startswith("Emitter:")]
        assert len(line) == 1, out
        assert want in line[0] and emit in line[0], (want, line[0])


def test_a_missing_emitter_is_named_not_hashed():
    for emit in (None, "", "/nonexistent/emit_sound_blob"):
        rc, out, err = _run(_block("EMITTER_IDENTITY"), SIGIL_EMIT=emit)
        assert rc == 0, (emit, out, err)
        assert "Emitter:" in out and "NOT FOUND" in out, (emit, out)


def test_a_silent_shape_says_the_emitter_is_not_used():
    rc, out, err = _run(_block("EMITTER_IDENTITY"), SOUND_DRIVER_ENABLED="0",
                        SIGIL_EMIT="/nonexistent/emit_sound_blob")
    assert rc == 0, (out, err)
    assert "Emitter:" in out and "not used" in out and "NOT FOUND" not in out, out


# ------------------------------------------------------------------------ LANDING RECEIPT
# CTRL-3b (2026-09-14): the one switch that skips the shared lanes, and it is landing_build.sh's
# alone. Every refusal row asserts exit != 0, NO result line (the block stopped the build), the
# name landing_build.sh in the message, and the specific reason.
def _receipt_block():
    return _block("LANDING_LANES_RECEIPT") + '\necho "RESULT SKIP=${LANDING_LANES_SKIP}"\n'


def _write_receipt(d, pid, lanes="passed", carrier="s4"):
    p = os.path.join(d, "receipt")
    with open(p, "w") as f:
        f.write("landing_pid=%s\ncarrier=%s\nlanes=%s\n" % (pid, carrier, lanes))
    return p


def _refused(out, why):
    assert "RESULT" not in out, "the block let the build continue:\n" + out
    assert "only tools/landing_build.sh may set it" in out, out
    assert why in out, (why, out)


def test_no_receipt_means_every_lane_runs_and_nothing_is_said():
    rc, out, err = _run(_receipt_block())
    assert rc == 0, (out, err)
    assert "RESULT SKIP=0" in out and "SHARED LANES" not in out, out


def test_a_hand_set_receipt_is_refused_naming_landing_build():
    with tempfile.TemporaryDirectory() as d:
        # a path to nothing
        rc, out, err = _run(_receipt_block(), AEON_LANDING_LANES_RECEIPT=os.path.join(d, "no"))
        assert rc != 0
        _refused(out, "there is no readable receipt")
        # a receipt naming THIS pytest process: a real, live ancestor of the block's shell,
        # and exactly what a hand run under any other runner looks like
        rc, out, err = _run(_receipt_block(),
                            AEON_LANDING_LANES_RECEIPT=_write_receipt(d, os.getpid()))
        assert rc != 0
        _refused(out, "not tools/landing_build.sh")
        # a receipt naming a live process that is NOT an ancestor
        sleeper = subprocess.Popen(["sleep", "30"])
        try:
            rc, out, err = _run(_receipt_block(),
                                AEON_LANDING_LANES_RECEIPT=_write_receipt(d, sleeper.pid))
        finally:
            sleeper.kill()
            sleeper.wait()
        assert rc != 0
        _refused(out, "is not an ancestor of this build.sh")
        # a receipt that does not say the lanes passed
        rc, out, err = _run(_receipt_block(),
                            AEON_LANDING_LANES_RECEIPT=_write_receipt(d, os.getpid(), "failed"))
        assert rc != 0
        _refused(out, "does not record the lanes passing")
        # a receipt with no pid at all, and pid 1 (every process's ancestor)
        for pid in ("", "1"):
            rc, out, err = _run(_receipt_block(),
                                AEON_LANDING_LANES_RECEIPT=_write_receipt(d, pid))
            assert rc != 0, pid
            _refused(out, "names no landing_build.sh process")


def _fake_landing(root, name, child_dir=None):
    """A real ancestor: <root>/tools/<name> cd's to <root> (as landing_build.sh does), writes
    a receipt naming its own pid, then runs the lifted block as its CHILD. `child_dir`
    makes the child run from another directory while the ancestor stays at <root>."""
    tools = os.path.join(root, "tools")
    os.makedirs(tools, exist_ok=True)
    os.makedirs(os.path.join(root, "sub"), exist_ok=True)
    script = os.path.join(tools, name)
    run = 'bash -c "$BLOCK" build.sh'
    if child_dir:
        run = '( cd %s && exec %s )' % (child_dir, run)
    with open(script, "w") as f:
        f.write('cd "$(dirname "$0")/.." || exit 9\n'
                "printf 'landing_pid=%s\\ncarrier=s4\\nlanes=passed\\n' \"$$\" > \"$PWD/receipt\"\n"
                'export AEON_LANDING_LANES_RECEIPT="$PWD/receipt"\n' + run + "\n")
    env = {k: v for k, v in os.environ.items() if k != "AEON_LANDING_LANES_RECEIPT"}
    env["BLOCK"] = "set -euo pipefail\n" + _receipt_block()
    p = subprocess.run(["bash", script], env=env, capture_output=True, text=True, timeout=30)
    return p.returncode, p.stdout, p.stderr


def test_a_receipt_from_a_real_landing_build_ancestor_is_honoured_and_announced():
    with tempfile.TemporaryDirectory() as d:
        rc, out, err = _fake_landing(d, "landing_build.sh")
        assert rc == 0, (out, err)
        assert "RESULT SKIP=1" in out, out
        assert "SHARED LANES NOT RE-RUN IN THIS SHAPE" in out, out
        assert "ran them green in its s4 build of this run" in out, out


def test_the_ancestor_must_be_named_landing_build_and_work_in_this_directory():
    """The two controls for the honoured row: the SAME script under another name, and the
    same script whose build runs from another directory, are both refused."""
    with tempfile.TemporaryDirectory() as d:
        rc, out, err = _fake_landing(d, "landing_check.sh")
        assert rc != 0
        _refused(out, "not tools/landing_build.sh")
    with tempfile.TemporaryDirectory() as d:
        rc, out, err = _fake_landing(d, "landing_build.sh", child_dir="sub")
        assert rc != 0
        _refused(out, "not in this build's")


# ------------------------------------------------------------------------ SHARED LANES
# The two call sites the receipt guards, lifted and run with python3 and gate() stubbed, so
# what is asserted is which commands the real block reaches.
def _lanes(skip):
    stub = ('TOOLS=/stub/tools\n'
            'python3() { echo "CALLED python3 $*"; return 0; }\n'
            'gate() { shift 2; "$@"; }\n'
            'LANDING_LANES_SKIP=%s\nLANDING_LANES_FROM="stub receipt"\n' % skip)
    return _run(stub + _block("SHARED_LANES"))


def test_without_a_receipt_both_shared_lanes_run():
    rc, out, err = _lanes(0)
    assert rc == 0, (out, err)
    assert "CALLED python3 -m pytest /stub/tools" in out and "-m not needs_build" in out, out
    assert "CALLED python3 /stub/tools/emp_expect_fail.py" in out, out
    assert "NOT RUN in this shape" not in out, out


def test_with_a_receipt_neither_shared_lane_runs_and_both_say_so():
    rc, out, err = _lanes(1)
    assert rc == 0, (out, err)
    assert "CALLED" not in out, "a shared lane ran although the receipt was honoured:\n" + out
    assert out.count("NOT RUN in this shape") == 2, out
    assert "stub receipt" in out, out


# ------------------------------------------------------------------------ PROJECT
def _project(**env):
    # ROM_NAME is what build.sh's earlier blocks computed (s4 / s4.debug / demo / ...).
    script = (_block("PROJECT_GAME_SHAPE")
              + '\necho "RESULT shape=${SIGIL_PROJECT_SHAPE} sound=${SOUND_DRIVER_ENABLED:-unset}"\n'
              + 'echo "AXES rom=${ROM_NAME} debug=${DEBUG} crash=${CRASH_REPORT}'
              + ' hotkeys=${SOUND_DEBUG_HOTKEYS} mirror=${SOUND_DBG_MIRROR}"\n')
    env.setdefault("TOOLS", TOOLS)
    if "ROM_NAME" not in env:
        stem = "s4" if env.get("GAME", "sonic4") == "sonic4" else env.get("GAME")
        env["ROM_NAME"] = stem + (".debug" if env.get("DEBUG") == "1" else "")
    return _run(script, **env)


def _axes(out):
    lines = [l for l in out.splitlines() if l.startswith("AXES ")]
    assert len(lines) == 1, out
    return lines[0][len("AXES "):]


def _project_result(out):
    lines = [l for l in out.splitlines() if l.startswith("RESULT ")]
    assert len(lines) == 1, out
    return lines[0][len("RESULT "):]


def test_demo_takes_its_shape_row_and_sound_axis_from_its_description():
    for debug, row in ((None, "release"), ("0", "release"), ("1", "debug")):
        rc, out, err = _project(GAME="demo", DEBUG=debug)
        assert rc == 0, (out, err)
        # games/demo/game.toml [shapes.release|debug] features.sound = false
        assert _project_result(out) == "shape=%s sound=0" % row, out


def test_an_environment_sound_axis_that_disagrees_with_the_description_is_refused():
    rc, out, err = _project(GAME="demo", SOUND_DRIVER_ENABLED="1")
    assert rc == 1, (out, err)
    assert "SOUND_DRIVER_ENABLED=1 is set, but games/demo/game.toml" in out, out
    assert "RESULT" not in out, out
    rc, out, err = _project(GAME="demo", SOUND_DRIVER_ENABLED="0")
    assert rc == 0 and _project_result(out) == "shape=release sound=0", (out, err)


# Expectations below are games/sonic4/game.toml's rows, read through the same reader
# build.sh uses (so a description edit moves the test with it, not a typed copy).
def _desc(shape):
    import game_shape_feature as gsf
    return dict(gsf.shell_facts("sonic4", shape))


def test_sonic4_takes_its_shape_row_and_axes_from_its_description():
    for debug, row in ((None, "release"), ("0", "release"), ("1", "debug")):
        rc, out, err = _project(GAME="sonic4", DEBUG=debug)
        assert rc == 0, (out, err)
        d = _desc(row)
        assert _project_result(out) == "shape=%s sound=%d" % (row, d["DESC_SOUND"]), out
        assert _axes(out) == "rom=%s debug=%d crash=%d hotkeys=%d mirror=%d" % (
            d["DESC_STEM"], d["DESC_DEBUG"], d["DESC_CRASH_REPORT"],
            d["DESC_SOUND_DEBUG_HOTKEYS"], d["DESC_SOUND_DBG_MIRROR"]), out


def test_a_shape_row_by_name_takes_its_stem_and_axes():
    """SHAPE=config-a / config-b: the sound shapes build.sh used to refuse are description
    rows now, each written under its `[outputs]` stem."""
    for row in ("config-a", "config-b"):
        d = _desc(row)
        assert d["DESC_STEM"] and not d["DESC_FIXTURE"], d      # positive control
        rc, out, err = _project(GAME="sonic4", SHAPE=row)
        assert rc == 0, (out, err)
        assert _project_result(out) == "shape=%s sound=%d" % (row, d["DESC_SOUND"]), out
        assert _axes(out) == "rom=%s debug=%d crash=%d hotkeys=%d mirror=%d" % (
            d["DESC_STEM"], d["DESC_DEBUG"], d["DESC_CRASH_REPORT"],
            d["DESC_SOUND_DEBUG_HOTKEYS"], d["DESC_SOUND_DBG_MIRROR"]), out


def test_the_stress_fixtures_take_their_rows():
    for knob, row in (("STRESS_EVICT", "stress-evict"), ("STRESS_ART", "stress-art")):
        # build.sh's stress blocks set DEBUG=1 and the literal ROM_NAME before this block.
        rc, out, err = _project(GAME="sonic4", DEBUG="1", ROM_NAME=_desc(row)["DESC_STEM"], **{knob: "1"})
        assert rc == 0, (out, err)
        assert _project_result(out).startswith("shape=%s " % row), out


def test_a_row_build_sh_does_not_write_is_refused():
    """lean has no `[outputs]` stem; the stress rows and the keystones alias are fixtures."""
    rc, out, err = _project(GAME="sonic4", SHAPE="lean")
    assert rc == 1 and "no [outputs] stem" in out and "RESULT" not in out, (out, err)
    for row in ("stress-evict", "stress-art", "config-a-keystones-flipped"):
        rc, out, err = _project(GAME="sonic4", SHAPE=row)
        assert rc == 1 and "is a fixture row" in out and "RESULT" not in out, (row, out, err)
    rc, out, err = _project(GAME="sonic4", SHAPE="nope")
    assert rc == 1 and "no [shapes.nope]" in (out + err) and "RESULT" not in out, (out, err)


def test_shape_does_not_combine_with_the_stress_or_clip_shapes():
    for knob in ("STRESS_EVICT", "STRESS_ART", "STRESS_OBJECTS", "STRESS_SIDEKICK"):
        rc, out, err = _project(GAME="sonic4", SHAPE="config-a", **{knob: "1"})
        assert rc == 1 and "mutually exclusive" in out, (knob, out, err)
    rc, out, err = _project(GAME="sonic4", SHAPE="config-a", S2CLIP="x")
    assert rc == 1 and "mutually exclusive" in out, (out, err)


def test_an_environment_axis_that_disagrees_with_the_row_is_refused():
    """The old by-hand refusals (silent sonic4, hotkeys, mirror, CRASH_REPORT=0) are now
    disagreements with the row; DEBUG under SHAPE likewise."""
    for env, needle in ((dict(SOUND_DRIVER_ENABLED="0"), "SOUND_DRIVER_ENABLED=0 is set"),
                        (dict(SOUND_DEBUG_HOTKEYS="1"), "SOUND_DEBUG_HOTKEYS=1 is set"),
                        (dict(SOUND_DBG_MIRROR="1"), "SOUND_DBG_MIRROR=1 is set"),
                        (dict(CRASH_REPORT="0"), "CRASH_REPORT=0 is set"),
                        (dict(SHAPE="config-b", DEBUG="1"), "DEBUG=1 is set"),
                        (dict(SHAPE="config-a", DEBUG="0"), "DEBUG=0 is set"),
                        (dict(SHAPE="config-a", SOUND_DRIVER_ENABLED="0"), "SOUND_DRIVER_ENABLED=0 is set")):
        rc, out, err = _project(GAME="sonic4", **env)
        assert rc == 1 and needle in out and "RESULT" not in out, (env, out, err)
    # Agreeing values are accepted (config-b IS silent).
    rc, out, err = _project(GAME="sonic4", SHAPE="config-b", SOUND_DRIVER_ENABLED="0", DEBUG="0")
    assert rc == 0 and _project_result(out) == "shape=config-b sound=0", (out, err)


def test_a_stem_build_sh_spells_that_disagrees_with_the_description_is_refused():
    rc, out, err = _project(GAME="sonic4", ROM_NAME="s4.renamed")
    assert rc == 1 and "[outputs] says 's4'" in out and "RESULT" not in out, (out, err)
    # The clip and stress-objects shapes build release/debug under their own names.
    rc, out, err = _project(GAME="sonic4", ROM_NAME="s4.stressobj", STRESS_OBJECTS="1")
    assert rc == 0 and _project_result(out).startswith("shape=release "), (out, err)


def test_a_per_game_build_conf_is_refused():
    """build.conf is gone for every game; one that reappears is a second authority."""
    with tempfile.TemporaryDirectory() as td:
        rc, out, err = _run('cd "%s"; mkdir -p games/sonic4; touch games/sonic4/build.conf\n' % td
                            + _BUILD_CONF_BLOCK() + '\necho NOT_REFUSED\n', GAME="sonic4")
    assert rc == 1 and "reads no per-game build config" in out and "NOT_REFUSED" not in out, (out, err)


def _BUILD_CONF_BLOCK():
    with open(BUILD_SH, "r", encoding="utf-8") as f:
        src = f.read()
    a = src.index("# No per-game build config.")
    return src[a:src.index("# EVERY GAME IS A GAME-AS-DATA GAME", a)]

