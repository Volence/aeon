#!/usr/bin/env python3
"""test_cart_coverage_census — the census is a measurement, so its controls get tested.

RUNNER: `python3 -m pytest tools` in `build.sh` (build-fatal) and in
`tools/landing_build.sh`. Nothing else runs the census, so without this file `--check`
would be a flag nobody pulls.

WHY A TEST FOR A REPORTING TOOL. The `CART-VERIFY-COVERAGE` row published its count
wrong three times and each wrong number was caught by a HUMAN noticing, late. The
census's `--check` is the machine version of that noticing. A `--check` that cannot
exit 1 is worse than none — it converts "nobody looked" into "it passed" — so the
failing case is driven here, not just the passing one.
"""
import subprocess
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
CENSUS = TOOLS / "cart_coverage_census.py"


def _run(*args):
    return subprocess.run([sys.executable, str(CENSUS), *args],
                          capture_output=True, text=True)


def test_the_real_corpus_passes_its_own_controls():
    """The live number. If this goes red the census is not measuring anything."""
    r = _run("--check")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "controls OK" in r.stdout


def test_check_can_actually_fail(tmp_path):
    """THE NON-VACUITY LEG, and it is driven WITHOUT mutating the census itself.

    Pointed at a directory of python files that reach no bus, every canary drops out
    of the population. That is the same signal a broken matcher arm produces — it was
    verified against a real mutation of the `from aether import BusClient` arm, which
    took the population from 68 to 52 and dropped `evict_witness.py` — and it can be
    reproduced here on demand, with no file on disk edited.
    """
    (tmp_path / "a.py").write_text("import os\nimport sys\n")
    (tmp_path / "b.py").write_text("from pathlib import Path\n")
    r = _run("--check", "--dir", str(tmp_path))
    assert r.returncode == 1, (
        "the census reported controls OK over a directory containing no bus-reaching "
        "tool at all — `--check` cannot fail, so a green run means nothing\n"
        + r.stdout + r.stderr)
    assert "LOST known members" in r.stdout


def test_the_negative_control_is_a_pattern_that_could_match(tmp_path):
    """The bogus-module control must be capable of firing, or it proves nothing.

    A negative control nobody has ever seen fire is indistinguishable from a line of
    dead code. So a file that really does import the bogus module is planted, and the
    census must notice.
    """
    (tmp_path / "c.py").write_text(
        "import zz_no_such_module_zz\nfrom aether import BusClient\n")
    r = _run("--check", "--dir", str(tmp_path))
    assert "negative control matched something" in r.stdout, r.stdout + r.stderr
    assert r.returncode == 1


def test_the_spawner_verification_flag_is_read_from_the_measured_tree(tmp_path):
    """`spawner verifies the cart` must come from the tree under `--dir`, not from here.

    That is the whole basis of the BEFORE/AFTER comparison: the same instrument is
    pointed at an older checkout of `tools/` and must report that ITS spawner does not
    verify. A flag baked in from the running copy would make every historical
    measurement read as covered.
    """
    (tmp_path / "aether_instance.py").write_text("# a spawner with no cart check\n")
    (tmp_path / "d.py").write_text("from aether import BusClient\n")
    r = _run("--dir", str(tmp_path))
    assert "spawner verifies the cart: False" in r.stdout, r.stdout

    (tmp_path / "aether_instance.py").write_text("assert_cart_matches_disk\n")
    r = _run("--dir", str(tmp_path))
    assert "spawner verifies the cart: True" in r.stdout, r.stdout
