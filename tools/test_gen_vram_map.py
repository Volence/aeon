import os, subprocess, sys, textwrap

HERE = os.path.dirname(__file__)
GEN = os.path.join(HERE, "gen_vram_map.py")
REPO = os.path.normpath(os.path.join(HERE, ".."))

# NOTE: every test writes to tmp_path. NEVER default generator output into the
# repo — tools/test_import_sk_collision.py:14 records the incident this rule
# comes from.

GOOD = """
[[region]]
name = "pool"
owner = "engine.pool"
kind = "arena"
base = 0
tiles = 1984
quantum = 64
lifetime = "act"

[[region]]
name = "win"
owner = "game.win"
kind = "window"
base = 1984
tiles = 32
lifetime = "act"
const = "VRAM_WIN"

[[free]]
base = 2016
tiles = 32
"""

EMP_WITH_MARKERS = textwrap.dedent("""\
    // hand content above
    // >>> GENERATED: vram map (tools/gen_vram_map.py) — DO NOT HAND-EDIT <<<
    stale old content
    // <<< GENERATED: vram map END >>>
    // hand content below
    """)


def run(tmp, toml_text, emp_text=EMP_WITH_MARKERS, extra=None):
    toml = tmp / "vram.toml"; toml.write_text(toml_text)
    emp = tmp / "constants.emp"; emp.write_text(emp_text)
    args = [sys.executable, GEN, "--toml", str(toml), "--emp", str(emp),
            "--map-doc", str(tmp / "map.md"), "--game", "testgame"]
    if extra: args += extra
    return subprocess.run(args, capture_output=True, text=True)


def test_good_map_emits_block_and_doc(tmp_path):
    r = run(tmp_path, GOOD)
    assert r.returncode == 0, r.stderr
    emp = (tmp_path / "constants.emp").read_text()
    assert "pub const VRAM_WIN" in emp and "$07C0" in emp        # 1984 = $7C0
    assert "stale old content" not in emp
    assert "hand content above" in emp and "hand content below" in emp
    doc = (tmp_path / "map.md").read_text()
    assert "pool" in doc and "FREE" in doc and "2016" in doc


def test_gap_is_an_error_naming_the_run(tmp_path):
    bad = GOOD.replace('base = 2016\ntiles = 32', 'base = 2016\ntiles = 16')
    r = run(tmp_path, bad)
    assert r.returncode != 0
    assert "2032" in r.stderr and "2047" in r.stderr   # the undeclared run


def test_overlap_is_an_error_naming_both_owners(tmp_path):
    bad = GOOD.replace('base = 1984\ntiles = 32', 'base = 1980\ntiles = 36')
    r = run(tmp_path, bad)
    assert r.returncode != 0
    assert "pool" in r.stderr and "win" in r.stderr


def test_declared_overlay_is_allowed(tmp_path):
    over = GOOD + textwrap.dedent("""
        [[region]]
        name = "shadow"
        owner = "game.shadow"
        kind = "plane"
        base = 1984
        tiles = 32
        lifetime = "boot"
        overlay_with = ["win"]
        """)
    r = run(tmp_path, over)
    assert r.returncode == 0, r.stderr


def test_quantum_violation_is_an_error(tmp_path):
    bad = GOOD.replace('tiles = 1984\nquantum = 64', 'tiles = 1985\nquantum = 64')
    # keep coverage consistent for the changed size
    bad = bad.replace('base = 1984\ntiles = 32\nlifetime = "act"\nconst = "VRAM_WIN"',
                      'base = 1985\ntiles = 31\nlifetime = "act"\nconst = "VRAM_WIN"')
    r = run(tmp_path, bad)
    assert r.returncode != 0
    assert "quantum" in r.stderr


def test_missing_markers_is_an_error(tmp_path):
    r = run(tmp_path, GOOD, emp_text="// a file with no markers\n")
    assert r.returncode != 0
    assert "marker" in r.stderr.lower()


def test_deterministic(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir(); b.mkdir()
    for d in (a, b):
        r = run(d, GOOD)
        assert r.returncode == 0, r.stderr
    assert (a / "constants.emp").read_text() == (b / "constants.emp").read_text()
    assert (a / "map.md").read_text() == (b / "map.md").read_text()


def test_py_mirror_emits_constants(tmp_path):
    r = run(tmp_path, GOOD, extra=["--py", str(tmp_path / "vram_map.py")])
    assert r.returncode == 0, r.stderr
    ns = {}
    exec((tmp_path / "vram_map.py").read_text(), ns)
    assert ns["REGIONS"]["win"]["base"] == 1984
    assert ns["VRAM_WIN"] == 1984


def test_real_sonic4_map_verifies_and_matches_reality(tmp_path):
    """The committed contract must verify AND reproduce today's constants."""
    import shutil
    emp_src = os.path.join(REPO, "games/sonic4/config/constants.emp")
    # run against a COPY so the repo is never written by tests
    shutil.copy(emp_src, tmp_path / "constants.emp")
    toml = os.path.join(REPO, "games/sonic4/vram.toml")
    r = subprocess.run([sys.executable, GEN, "--toml", toml,
                        "--emp", str(tmp_path / "constants.emp"),
                        "--map-doc", str(tmp_path / "map.md"),
                        "--game", "sonic4"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    emp = (tmp_path / "constants.emp").read_text()
    for expected in ("pub const VRAM_TEST_SONIC", "$03C0",
                     "pub const VRAM_TEST_OBJ", "$03E0",
                     "pub const VRAM_TEST_MARKER", "$03F8",
                     "pub const VRAM_TAILS_APPENDAGE", "$05D4"):
        assert expected in emp, expected
