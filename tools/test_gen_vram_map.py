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

MB = "// >>> GENERATED: vram map (tools/gen_vram_map.py) — DO NOT HAND-EDIT <<<"
ME = "// <<< GENERATED: vram map END >>>"

EMP_WITH_MARKERS = textwrap.dedent("""\
    // hand content above
    // >>> GENERATED: vram map (tools/gen_vram_map.py) — DO NOT HAND-EDIT <<<
    stale old content
    // <<< GENERATED: vram map END >>>
    // hand content below
    """)

# a map containing the two magic regions the --py mirror exports budgets from
PY_GOOD = """
[[region]]
name = "fg_art_pool"
owner = "engine.pool"
kind = "arena"
base = 0
tiles = 960
quantum = 64
lifetime = "act"

[[region]]
name = "win"
owner = "game.win"
kind = "window"
base = 960
tiles = 64
lifetime = "act"
const = "VRAM_WIN"

[[region]]
name = "bg_region"
owner = "engine.bg"
kind = "arena"
base = 1024
tiles = 448
lifetime = "act"

[[free]]
base = 1472
tiles = 576
"""


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
    # R2/I5: the mirror requires the magic budget regions, so this map has them
    r = run(tmp_path, PY_GOOD, extra=["--py", str(tmp_path / "vram_map.py")])
    assert r.returncode == 0, r.stderr
    ns = {}
    exec((tmp_path / "vram_map.py").read_text(), ns)
    assert ns["GAME"] == "testgame"   # sonic4-only consumers assert this stamp
    assert ns["REGIONS"]["win"]["base"] == 960
    assert ns["VRAM_WIN"] == 960
    assert ns["POOL_TILE_CEILING"] == 960
    assert ns["BG_TILE_CAPACITY"] == 448


def test_py_missing_magic_regions_is_an_error(tmp_path):
    # R2/I5: --py without fg_art_pool/bg_region must fail loudly, not emit a
    # wrong mirror for the build tools to import
    r = run(tmp_path, GOOD, extra=["--py", str(tmp_path / "vram_map.py")])
    assert r.returncode != 0
    assert "fg_art_pool" in r.stderr


def test_end_before_begin_marker_is_an_error(tmp_path):
    # R2/C1: reversed markers must not splice
    r = run(tmp_path, GOOD, emp_text=ME + "\n// middle\n" + MB + "\n")
    assert r.returncode != 0
    assert "before" in r.stderr.lower()


def test_duplicated_begin_marker_is_an_error(tmp_path):
    # R2/C1: a duplicated marker must not silently duplicate content
    r = run(tmp_path, GOOD, emp_text=MB + "\n" + MB + "\nold\n" + ME + "\n")
    assert r.returncode != 0
    assert "2" in r.stderr and "marker" in r.stderr.lower()


def test_free_run_past_end_is_an_error(tmp_path):
    # R2/C2: an overflowing free run is a guided error, not an IndexError
    bad = GOOD.replace('base = 2016\ntiles = 32', 'base = 2016\ntiles = 40')
    r = run(tmp_path, bad)
    assert r.returncode != 0
    assert "free" in r.stderr.lower() and "2016" in r.stderr
    assert "Traceback" not in r.stderr


def test_free_negative_base_is_an_error(tmp_path):
    # R2/C2: a negative base must not wrap via Python negative indexing —
    # this variant WOULD silently satisfy coverage through the wraparound
    bad = GOOD.replace('base = 2016\ntiles = 32', 'base = -32\ntiles = 32')
    r = run(tmp_path, bad)
    assert r.returncode != 0
    assert "free" in r.stderr.lower() and "-32" in r.stderr


def test_unsafe_region_text_is_an_error(tmp_path):
    # R2/I3: strings interpolated into emitted source must be charset-safe
    bad = GOOD.replace('name = "win"', 'name = "win\\" // evil"')
    r = run(tmp_path, bad)
    assert r.returncode != 0
    assert "name" in r.stderr and "win" in r.stderr


def test_missing_toml_is_a_guided_error(tmp_path):
    # R2/I4: I/O errors follow the gen_vram_map: convention, no traceback
    emp = tmp_path / "constants.emp"; emp.write_text(EMP_WITH_MARKERS)
    r = subprocess.run([sys.executable, GEN, "--toml", str(tmp_path / "nope.toml"),
                        "--emp", str(emp), "--map-doc", str(tmp_path / "map.md"),
                        "--game", "testgame"], capture_output=True, text=True)
    assert r.returncode != 0
    assert "gen_vram_map:" in r.stderr and "nope.toml" in r.stderr
    assert "Traceback" not in r.stderr


def test_splice_preserves_hand_content_byte_for_byte(tmp_path):
    # R2/M9a: everything outside the markers survives EXACTLY
    prefix = "// alpha\n//   beta with trailing spaces   \n\n"
    suffix = "// gamma\n\n\n// delta, no trailing newline"
    emp_text = prefix + MB + "\nold stuff\n" + ME + "\n" + suffix
    r = run(tmp_path, GOOD, emp_text=emp_text)
    assert r.returncode == 0, r.stderr
    out = (tmp_path / "constants.emp").read_text()
    begin = out.index(MB)
    assert out[:begin] == prefix
    end_line = out.index("\n", out.index(ME)) + 1
    assert out[end_line:] == suffix


def test_resplice_is_idempotent(tmp_path):
    # R2/M9b: regenerating over an already-spliced file changes nothing
    r = run(tmp_path, GOOD)
    assert r.returncode == 0, r.stderr
    first = (tmp_path / "constants.emp").read_text()
    args = [sys.executable, GEN, "--toml", str(tmp_path / "vram.toml"),
            "--emp", str(tmp_path / "constants.emp"),
            "--map-doc", str(tmp_path / "map.md"), "--game", "testgame"]
    r2 = subprocess.run(args, capture_output=True, text=True)
    assert r2.returncode == 0, r2.stderr
    assert (tmp_path / "constants.emp").read_text() == first


def test_authority_crosscheck_emits_ensure(tmp_path):
    # R1: typed authority forms emit comptime ensures with the right relation
    # and the region name in the message; a list declares several checks.
    withauth = GOOD.replace(
        'quantum = 64\nlifetime = "act"',
        'quantum = 64\nlifetime = "act"\n'
        'authority = ["engine-endtiles:POOL_TILE_CEILING", "engine-tiles:POOL_TILE_COUNT"]')
    withauth = withauth.replace(
        'const = "VRAM_WIN"',
        'const = "VRAM_WIN"\nauthority = "engine-bytebase:VRAM_WIN_BYTES"')
    r = run(tmp_path, withauth)
    assert r.returncode == 0, r.stderr
    emp = (tmp_path / "constants.emp").read_text()
    assert "ensure(POOL_TILE_CEILING == 1984," in emp      # endtiles: base+tiles
    assert "ensure(POOL_TILE_COUNT == 1984," in emp        # tiles
    assert "ensure(VRAM_WIN_BYTES == $F800," in emp        # bytebase: 1984*32
    assert "pool drifted" in emp and "win drifted" in emp


def test_unknown_authority_form_is_an_error(tmp_path):
    bad = GOOD.replace('quantum = 64\nlifetime = "act"',
                       'quantum = 64\nlifetime = "act"\nauthority = "bogus:X"')
    r = run(tmp_path, bad)
    assert r.returncode != 0
    assert "bogus" in r.stderr and "pool" in r.stderr


def test_const_with_space_is_an_error(tmp_path):
    # R3: const is emitted as a bare .emp identifier — the shared loose
    # charset (spaces, dots, hyphens) would emit broken syntax
    bad = GOOD.replace('const = "VRAM_WIN"', 'const = "VRAM WIN"')
    r = run(tmp_path, bad)
    assert r.returncode != 0
    assert "const" in r.stderr and "win" in r.stderr


def test_authority_target_with_space_is_an_error(tmp_path):
    # R3: authority TARGET names are emitted as bare identifiers in ensures
    bad = GOOD.replace(
        'quantum = 64\nlifetime = "act"',
        'quantum = 64\nlifetime = "act"\nauthority = "engine-tiles:POOL TILES"')
    r = run(tmp_path, bad)
    assert r.returncode != 0
    assert "authority" in r.stderr and "pool" in r.stderr


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


# ---------------------------------------------------------------------------
# band_reserve — the BG animation tile reserve (docs/BUGS.md TOOL-01).
#
# The reserve withholds tiles at the top of bg_region from the STATIC BG
# importer so a BgAnim band can be inserted afterwards. It lives in vram.toml
# rather than in a --max-tiles flag because a flag is forgotten on the next
# import, which is exactly how the reserve reached zero.
# ---------------------------------------------------------------------------

def _py_ns(tmp_path, toml_text):
    """Generate the --py mirror from toml_text and return its namespace."""
    r = run(tmp_path, toml_text, extra=["--py", str(tmp_path / "vram_map.py")])
    assert r.returncode == 0, r.stderr
    ns = {}
    exec((tmp_path / "vram_map.py").read_text(), ns)
    return ns


def test_reserve_absent_defaults_to_zero_and_full_budget(tmp_path):
    # PY_GOOD declares no band_reserve: absent must mean "as before the field
    # existed", so the budget is the whole region.
    ns = _py_ns(tmp_path, PY_GOOD)
    assert ns["BG_BAND_RESERVE"] == 0
    assert ns["BG_STATIC_TILE_BUDGET"] == ns["BG_TILE_CAPACITY"]


def test_reserve_subtracts_from_the_static_budget(tmp_path):
    reserved = PY_GOOD.replace('name = "bg_region"',
                               'name = "bg_region"\nband_reserve = 192')
    ns = _py_ns(tmp_path, reserved)
    assert ns["BG_BAND_RESERVE"] == 192
    # derived from the emitted capacity, not from a literal 448 or 256
    assert ns["BG_STATIC_TILE_BUDGET"] == ns["BG_TILE_CAPACITY"] - 192
    # the capacity itself must NOT move: it is the hard VRAM boundary, and
    # inject_editor_bg.py still gates the FINAL blob (bands included) on it
    assert ns["BG_TILE_CAPACITY"] == ns["REGIONS"]["bg_region"]["tiles"]


def test_reserve_equal_to_the_region_is_allowed(tmp_path):
    reserved = PY_GOOD.replace('name = "bg_region"',
                               'name = "bg_region"\nband_reserve = 448')
    ns = _py_ns(tmp_path, reserved)
    assert ns["BG_STATIC_TILE_BUDGET"] == 0


def test_reserve_larger_than_the_region_is_an_error(tmp_path):
    bad = PY_GOOD.replace('name = "bg_region"',
                          'name = "bg_region"\nband_reserve = 449')
    r = run(tmp_path, bad, extra=["--py", str(tmp_path / "vram_map.py")])
    assert r.returncode != 0
    assert "band_reserve" in r.stderr and "449" in r.stderr
    assert "Traceback" not in r.stderr


def test_negative_reserve_is_an_error(tmp_path):
    bad = PY_GOOD.replace('name = "bg_region"',
                          'name = "bg_region"\nband_reserve = -1')
    r = run(tmp_path, bad, extra=["--py", str(tmp_path / "vram_map.py")])
    assert r.returncode != 0
    assert "band_reserve" in r.stderr


def test_boolean_reserve_is_an_error(tmp_path):
    # bool is an int subclass in Python: `band_reserve = true` must not read
    # as a 1-tile reserve
    bad = PY_GOOD.replace('name = "bg_region"',
                          'name = "bg_region"\nband_reserve = true')
    r = run(tmp_path, bad, extra=["--py", str(tmp_path / "vram_map.py")])
    assert r.returncode != 0
    assert "band_reserve" in r.stderr and "integer" in r.stderr


def test_reserve_on_another_region_is_a_loud_error(tmp_path):
    # only bg_region's reserve is honoured; anywhere else it would be silently
    # ignored, which is the same defect class the registry exists to prevent
    bad = PY_GOOD.replace('name = "fg_art_pool"',
                          'name = "fg_art_pool"\nband_reserve = 64')
    r = run(tmp_path, bad, extra=["--py", str(tmp_path / "vram_map.py")])
    assert r.returncode != 0
    assert "band_reserve" in r.stderr and "fg_art_pool" in r.stderr
    assert "bg_region" in r.stderr          # names where it DOES belong


def test_reserve_appears_in_the_occupancy_map(tmp_path):
    # a reserve invisible in the map doc is a reserve that gets forgotten
    reserved = PY_GOOD.replace('name = "bg_region"',
                               'name = "bg_region"\nband_reserve = 192')
    r = run(tmp_path, reserved, extra=["--py", str(tmp_path / "vram_map.py")])
    assert r.returncode == 0, r.stderr
    doc = (tmp_path / "map.md").read_text()
    assert "band_reserve: 192" in doc
    assert "static budget 256" in doc       # 448 - 192, from the same row


def test_zero_reserve_adds_no_map_doc_noise(tmp_path):
    r = run(tmp_path, PY_GOOD, extra=["--py", str(tmp_path / "vram_map.py")])
    assert r.returncode == 0, r.stderr
    assert "band_reserve" not in (tmp_path / "map.md").read_text()


def test_reserve_does_not_change_the_emp_block(tmp_path):
    """The reserve is a build-tool budget; no engine constant mirrors it.

    Nothing in .emp reads it, so an engine constant would be unread AND its
    authority cross-check would be circular (checking a value against itself).
    This pins that decision: changing the reserve must not move ROM bytes.
    """
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir(); b.mkdir()
    assert run(a, PY_GOOD).returncode == 0
    reserved = PY_GOOD.replace('name = "bg_region"',
                               'name = "bg_region"\nband_reserve = 192')
    assert run(b, reserved).returncode == 0
    assert (a / "constants.emp").read_text() == (b / "constants.emp").read_text()


# ---------------------------------------------------------------------------
# Staleness: gen_vram_map.py has NO automated caller — its outputs are
# committed artifacts regenerated by hand. So editing vram.toml and forgetting
# to regenerate went completely unnoticed: the `ensure`s live INSIDE the
# generated block, so a stale block cross-checks a stale value and passes.
# This makes "setting the reserve is a one-line data edit" actually true, by
# failing the build (pytest runs in build.sh) when the edit is not regenerated.
# ---------------------------------------------------------------------------

GAMES = ["sonic4", "demo"]


def _regen(tmp_path, game, with_py):
    import shutil
    emp_rel = f"games/{game}/config/constants.emp"
    doc_rel = f"docs/generated/vram-map-{game}.md"
    shutil.copy(os.path.join(REPO, emp_rel), tmp_path / "constants.emp")
    args = [sys.executable, GEN, "--game", game,
            "--toml", os.path.join(REPO, f"games/{game}/vram.toml"),
            "--emp", str(tmp_path / "constants.emp"),
            "--map-doc", str(tmp_path / "map.md")]
    if with_py:
        args += ["--py", str(tmp_path / "vram_map.py")]
    r = subprocess.run(args, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    out = {emp_rel: (tmp_path / "constants.emp"), doc_rel: (tmp_path / "map.md")}
    if with_py:
        out["tools/vram_map.py"] = tmp_path / "vram_map.py"
    return out


def test_generated_artifacts_are_in_sync(tmp_path):
    """Every committed gen_vram_map.py output must match a fresh regeneration.

    Nothing else checks this: the generator has no caller in build.sh, and the
    authority `ensure`s are emitted INTO the block they would have to guard.
    """
    stale = []
    for game in GAMES:
        d = tmp_path / game
        d.mkdir()
        # --py is the sonic4 mirror only (the build tools import from it)
        for rel, fresh in _regen(d, game, with_py=(game == "sonic4")).items():
            committed = os.path.join(REPO, rel)
            assert os.path.exists(committed), f"{rel} is missing from the repo"
            if open(committed).read() != fresh.read_text():
                stale.append(rel)
    assert not stale, (
        "these committed artifacts do not match games/<game>/vram.toml:\n  "
        + "\n  ".join(stale)
        + "\nRegenerate them:\n"
        "  python3 tools/gen_vram_map.py --game sonic4 "
        "--toml games/sonic4/vram.toml --py tools/vram_map.py "
        "--emp games/sonic4/config/constants.emp "
        "--map-doc docs/generated/vram-map-sonic4.md\n"
        "  python3 tools/gen_vram_map.py --game demo "
        "--toml games/demo/vram.toml "
        "--emp games/demo/config/constants.emp "
        "--map-doc docs/generated/vram-map-demo.md")


def test_the_sync_gate_covers_the_mirror_the_tools_import(tmp_path):
    """Guard the guard above: it must compare the file consumers actually use.

    A sync test pointed at a path nothing imports would be vacuous, and this
    repo has shipped exactly that (a lint over one no-op file).
    """
    sys.path.insert(0, os.path.join(REPO, "tools"))
    import vram_map
    assert os.path.normpath(vram_map.__file__) == \
        os.path.normpath(os.path.join(REPO, "tools/vram_map.py")), \
        "the importable vram_map is not the committed one the sync gate checks"
    assert "tools/vram_map.py" in _regen(tmp_path, "sonic4", with_py=True)
