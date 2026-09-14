"""tools/landing_build.sh's TRIMMED pre-merge check (CTRL-3b, 2026-09-14), graded by running it.

WHY THIS FILE EXISTS. The hub picked A plus D of the CTRL-3 shapes proposal (empyrean
cf430f7 docs/OVERSEER.md, "HUB PICK on aeon CTRL-3";
docs/superpowers/notes/2026-09-13-ctrl3-shapes-proposal.md):

  A  the pre-merge check stops building demo-normal (every Sonic 4 build still assembles it
     for placement: build.sh, "Evaluating the other game's link-time guards");
  D  the shape-independent lanes (build.sh's pre-build `pytest tools -m "not needs_build"`
     and tools/emp_expect_fail.py) run once per landing check, not once per shape.

B (drop both demo shapes) stays the OWNER'S, and one word from him switches A to B. So the
check's shapes are ONE declared list, LANDING_SHAPES, and everything else derives from it:
which shapes are built, the md5 line, the list handed to the needs_build lane (whose
exemption is computed from it), and which shape carries the shared lanes.

WHAT IS ASSERTED, each in a sandbox, for tools/test_landing_build_logfile.py's reason (a test
that runs a build from inside the lane that build runs must never be able to reach the repo):

  * the list is declared once and names only shapes build.sh can produce, i.e. shapes whose
    .bin/.lst are in tools/conftest.py's BUILD_ARTIFACTS;
  * the script builds EXACTLY the listed shapes, in order, md5s exactly their ROMs, and hands
    the lane the same list after `--shapes-built`;
  * the shared lanes run ONCE. The stub build.sh carries build.sh's REAL
    LANDING_LANES_RECEIPT block (lifted from build.sh at test time), so the receipt
    landing_build.sh writes is judged by the code that judges it in a real build, and a
    receipt that code refused would stop the stub. The first shape runs the lanes, every
    later one skips them and says so;
  * a carrier that FAILS hands the lanes to the next shape: they are never skipped on the
    strength of a build that did not pass;
  * the A->B swap is ONE changed line, and with it the script builds s4 and s4.debug only,
    and the REAL lane's exemption is exactly the artifacts of the shapes the swapped script
    did not write (observed in the sandbox, not typed here).

RUNNER: build.sh's pre-build tool-suite lane (`pytest tools -m "not needs_build"`),
build-fatal. Source only, no marker. It runs once per landing check (in the lane-carrying
shape) and once per hand-run `./build.sh`.
"""
import difflib
import json
import os
import shutil
import signal
import stat
import subprocess
import sys
import tempfile

TOOLS = os.path.dirname(os.path.abspath(__file__))
AEON = os.path.dirname(TOOLS)
SCRIPT = os.path.join(TOOLS, "landing_build.sh")
BUILD_SH = os.path.join(AEON, "build.sh")
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)
import needs_build_lane  # noqa: E402
from test_landing_lane_shapes import landing_shapes, LANDING_BLOCK  # noqa: E402

#: Option B of the proposal, as the one line it would be. Used ONLY inside a sandbox copy.
B_LINE = 'LANDING_SHAPES="s4 s4.debug"'


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def _build_block(name):
    """A `# >>> NAME` / `# <<< NAME` block of the real build.sh, exactly once."""
    src = _read(BUILD_SH)
    begin, end = "# >>> " + name, "# <<< " + name
    assert src.count(begin) == 1 and src.count(end) == 1, (
        "build.sh must carry exactly one %r / %r pair; this test lifts the block between "
        "them into a stub build.sh" % (begin, end))
    i = src.index(begin) + len(begin)
    return src[i:src.index(end, i)]


def _all_shapes():
    """Every shape build.sh can produce, by conftest's artifact list (NAME.bin + NAME.lst)."""
    import conftest
    arts = set(conftest.BUILD_ARTIFACTS)
    return sorted(a[:-4] for a in arts if a.endswith(".bin") and a[:-4] + ".lst" in arts)


def _stub_build():
    return ("#!/bin/bash\nset -euo pipefail\n"
            'g="${1:-sonic4}"\n'
            'if [ "$g" = sonic4 ]; then r=s4; else r="$g"; fi\n'
            'if [ "${DEBUG:-0}" = 1 ]; then r="$r.debug"; fi\n'
            "# ---- build.sh's real LANDING_LANES_RECEIPT block, lifted at test time ----\n"
            + _build_block("LANDING_LANES_RECEIPT") +
            "\n# ---- end of the lifted block ----\n"
            'if [ "${LANDING_LANES_SKIP}" = 1 ]; then echo "STUB $r lanes=skipped"; '
            'else echo "STUB $r lanes=ran"; fi\n'
            'if [ -n "${STUB_FAIL_SHAPE:-}" ] && [ "$STUB_FAIL_SHAPE" = "$r" ]; then exit 1; fi\n'
            'printf x > "$r.bin"\n')


STUB_LANE = """import json, sys
with open("lane-argv.json", "w") as f:
    json.dump(sys.argv[1:], f)
print("stub needs_build lane")
sys.exit(0)
"""


def _sandbox(root, script_text=None):
    os.makedirs(os.path.join(root, "tools"))
    script = os.path.join(root, "tools", "landing_build.sh")
    with open(script, "w", encoding="utf-8") as f:
        f.write(script_text if script_text is not None else _read(SCRIPT))
    build = os.path.join(root, "build.sh")
    with open(build, "w", encoding="utf-8") as f:
        f.write(_stub_build())
    os.chmod(build, os.stat(build).st_mode | stat.S_IXUSR)
    with open(os.path.join(root, "tools", "needs_build_lane.py"), "w") as f:
        f.write(STUB_LANE)
    return script


def _env(**extra):
    env = {k: v for k, v in os.environ.items()
           if k not in ("FAST", "NO_LINT", "DEBUG", "STUB_FAIL_SHAPE",
                        "AEON_LANDING_LANES_RECEIPT")}
    env.update(SIGIL_BUILD="/bin/false", SIGIL_EMIT="/bin/false")
    env.update(extra)
    return env


def _run(script, root, **extra):
    p = subprocess.Popen(["bash", script], cwd=root, env=_env(**extra), stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, text=True, start_new_session=True)
    try:
        out, _ = p.communicate(timeout=60)
    except subprocess.TimeoutExpired:
        os.killpg(p.pid, signal.SIGKILL)
        p.communicate()
        raise AssertionError("landing_build.sh did not finish in 60 s inside the sandbox")
    return p.returncode, out


def _stub_rows(out):
    """[(shape, 'ran'|'skipped'), ...] in the order the stub build.sh printed them."""
    rows = []
    for line in out.splitlines():
        if line.startswith("STUB "):
            _, shape, lanes = line.split()
            rows.append((shape, lanes.split("=", 1)[1]))
    return rows


def _md5_files(out):
    """The ROM names the script's md5 block hashed. EVERY line of the block must be an md5sum
    `<hash>  <file>` line: a typed list naming a ROM the run did not build leaves an md5sum
    error line there, and that is a failure, not a line to skip (red-first row R14 of the
    CTRL-3b record: skipping it let a typed md5 line pass under the B swap)."""
    lines = out.splitlines()
    start = next(i for i, l in enumerate(lines) if l.startswith("--- md5"))
    names = []
    for l in lines[start + 1:]:
        if l.startswith("--- assembler"):
            break
        if l.startswith("---"):
            continue                      # the block's own second header line
        parts = l.split()
        assert len(parts) == 2 and len(parts[0]) == 32, "not an md5 line: %r\n%s" % (l, out)
        names.append(parts[1])
    return names


def _lane_shapes_argv(root):
    """Everything the stub lane received after --shapes-built: it must be the list and
    nothing more (red-first row R13: a prefix check let a typed longer list pass)."""
    with open(os.path.join(root, "lane-argv.json")) as f:
        argv = json.load(f)
    assert argv.count("--shapes-built") == 1, argv
    return argv[argv.index("--shapes-built") + 1:]


def _last(out):
    return [l for l in out.splitlines() if l.strip()][-1]


# ----------------------------------------------------------------------------- the list

def test_the_shape_list_is_declared_once_and_names_only_buildable_shapes():
    shapes = landing_shapes(_read(SCRIPT))
    assert shapes, "LANDING_SHAPES is empty: the check would build nothing"
    assert len(set(shapes)) == len(shapes), "a shape is listed twice: %s" % shapes
    unknown = [s for s in shapes if s not in _all_shapes()]
    assert not unknown, (
        "LANDING_SHAPES names %s, which build.sh cannot produce (their .bin/.lst are not in "
        "tools/conftest.py BUILD_ARTIFACTS %s)" % (unknown, _all_shapes()))


# ----------------------------------------------------------------------------- the run

def test_the_check_builds_exactly_its_shapes_and_runs_the_shared_lanes_once():
    shapes = landing_shapes(_read(SCRIPT))
    with tempfile.TemporaryDirectory() as d:
        rc, out = _run(_sandbox(d), d)
        assert rc == 0 and _last(out) == "finished=0", out
        rows = _stub_rows(out)
        assert [s for s, _ in rows] == shapes, (rows, out)
        assert [l for _, l in rows] == ["ran"] + ["skipped"] * (len(shapes) - 1), (
            "the shared lanes must run in the first shape and in no other:\n%s" % out)
        # The skip is announced by build.sh's own banner, once per skipping shape.
        assert out.count("SHARED LANES NOT RE-RUN IN THIS SHAPE") == len(shapes) - 1, out
        for s in _all_shapes():
            if s in shapes:
                assert "EXIT_%s=0 " % s in out, (s, out)
            else:
                assert "EXIT_%s=" % s not in out, ("built a shape the list omits", s, out)
                assert not os.path.exists(os.path.join(d, s + ".bin")), s
        assert _md5_files(out) == [s + ".bin" for s in shapes], out
        assert _lane_shapes_argv(d) == shapes, out
        # The receipt lives outside the tree and is gone when the run is.
        assert "EXIT_needs_build=0" in out, out


def test_a_failed_carrier_hands_the_lanes_to_the_next_shape():
    shapes = landing_shapes(_read(SCRIPT))
    assert len(shapes) >= 2, "this row needs a second shape to hand the lanes to"
    with tempfile.TemporaryDirectory() as d:
        rc, out = _run(_sandbox(d), d, STUB_FAIL_SHAPE=shapes[0])
        assert rc == 1 and _last(out) == "finished=1", out
        lanes = [l for _, l in _stub_rows(out)]
        assert lanes == ["ran", "ran"] + ["skipped"] * (len(shapes) - 2), (
            "a failed first shape proves nothing about the lanes, so the second must run "
            "them:\n%s" % out)
        assert "needs_build lane SKIPPED" in out, out


def test_the_A_to_B_swap_is_one_line_and_derives_everything_else():
    text = _read(SCRIPT)
    begin, end = LANDING_BLOCK
    head, rest = text.split(begin, 1)
    body, tail = rest.split(end, 1)
    lines = body.splitlines(keepends=True)
    idx = [i for i, l in enumerate(lines) if l.strip().startswith("LANDING_SHAPES=")]
    assert len(idx) == 1, body
    lines[idx[0]] = B_LINE + "\n"
    swapped = head + begin + "".join(lines) + end + tail
    changed = [l for l in difflib.ndiff(text.splitlines(), swapped.splitlines())
               if l.startswith(("- ", "+ "))]
    assert len(changed) == 2, "the swap is not one line:\n" + "\n".join(changed)
    b_shapes = landing_shapes(swapped)
    assert b_shapes == ["s4", "s4.debug"], b_shapes

    with tempfile.TemporaryDirectory() as d:
        rc, out = _run(_sandbox(d, swapped), d)
        assert rc == 0 and _last(out) == "finished=0", out
        assert [s for s, _ in _stub_rows(out)] == b_shapes, out
        assert [l for _, l in _stub_rows(out)] == ["ran", "skipped"], out
        assert _md5_files(out) == [s + ".bin" for s in b_shapes], out
        assert _lane_shapes_argv(d) == b_shapes, out
        # What the swapped script did NOT write, observed on disk ...
        unwritten = [s for s in _all_shapes() if not os.path.exists(os.path.join(d, s + ".bin"))]

    import conftest
    want = sorted(a for a in conftest.BUILD_ARTIFACTS
                  if a.rsplit(".", 1)[0] in unwritten)
    # ... is exactly what the REAL lane exempts for the list it was handed.
    got = sorted(needs_build_lane.exempt_artifacts(b_shapes, conftest.BUILD_ARTIFACTS))
    assert want and got == want, (got, want)
    # And the lane never exempts an artifact of a shape it was told is built.
    assert not set(got) & {s + ext for s in b_shapes for ext in (".bin", ".lst")}
