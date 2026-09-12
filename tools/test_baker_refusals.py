"""Refusals and gate checks for the OJZ bakers' silent failure paths.

WHY THIS EXISTS. The 2026-09-12 gap lens sweep (T1 seat,
docs/superpowers/notes/2026-09-12-aeon-gap-lens-sweep.md on the review branch) showed
the OJZ bakers turning a malformed editor input into a green re-bake, a green
tools/verify_level_bin.py, and wrong level data. Each test here drives the REAL
function against a one-defect fixture and pairs it with a converse control, so a
refusal that fires on everything cannot pass.

Two halves, deliberately:
  * the GENERATOR must refuse the bad input (tools/ojz_strip_gen.py), and
  * the GATE must fail a tree that was baked from it anyway (tools/verify_level_bin.py),
because a fix to only the generator leaves the gate blind -- the 09-06 tools packet's
T1-2 shape, where the proof reproduced the generator's own fallback.

Runner: build.sh's pre-build pytest lane collects tools/test_*.py. The gate half is
donor-free. The generator half imports ojz_strip_gen, which resolves the sonic_hack
donor at import, so it SKIPS by name without the donor (tools/test_tool_selftests.py's
convention); on the owner's machine and the nightly it runs.
"""

import json
import os
import shutil
import struct
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)

import verify_level_bin as vlb  # noqa: E402  (donor-free by contract)
from suite_paths import suite_path  # noqa: E402

SONIC_HACK = os.environ.get("AEON_SONIC_HACK_DIR") or str(suite_path("sonic_hack"))

W = 256                      # editor grid: 256x256 tiles per section
CELL_FILE_BYTES = W * W * 2  # one 16-bit word per tile
SOL_ALL = 3
SHAPE_WITH_GEOMETRY = 114    # a real base-bank shape (tools/test_collision_consistency.py uses it too)


def _strip_gen():
    """Import the real baker, or skip when the donor it resolves at import is absent."""
    if not os.path.isdir(SONIC_HACK):
        pytest.skip(f"donor tree absent (AEON_SONIC_HACK_DIR={SONIC_HACK}): "
                    f"ojz_strip_gen resolves the sonic_hack donor at import")
    import ojz_strip_gen
    return ojz_strip_gen


def _plane(cells):
    """A full-size collision plane with `cells` = {(tile_row, tile_col): word}."""
    buf = bytearray(CELL_FILE_BYTES)
    for (r, c), w in cells.items():
        struct.pack_into(">H", buf, (r * W + c) * 2, w)
    return bytes(buf)


def _one_section_editor(tmp_path, collattr, collattrb=None):
    act = tmp_path / "editor" / "ojz" / "act1"
    act.mkdir(parents=True, exist_ok=True)
    (act / "section_0.collattr.bin").write_bytes(collattr)
    if collattrb is not None:
        (act / "section_0.collattrb.bin").write_bytes(collattrb)
    return tmp_path / "editor"


def _overlay(osg, monkeypatch, editor_dir):
    import collision_pipeline as cp
    monkeypatch.setattr(osg, "EDITOR_DIR", str(editor_dir))
    profiles, angles = osg.load_base_bank()
    air = bytes(osg.COLLISION_ROWS_PER_STRIP)
    grids = ([air] * osg.STRIP_TILE_HEIGHT, [air] * osg.STRIP_TILE_HEIGHT)
    return osg.apply_editor_collision_overlay(grids, "0", profiles, angles, cp.AttrSet())


# ---------------------------------------------------------------------------
# F1 -- a wrong-sized collattr.bin used to bake the section as ALL AIR
# ---------------------------------------------------------------------------

def test_f1_a_wrong_sized_collattr_is_refused_by_name(tmp_path, monkeypatch):
    osg = _strip_gen()
    painted = _plane({(20, 10): (SOL_ALL << 12) | SHAPE_WITH_GEOMETRY})
    ed = _one_section_editor(tmp_path, painted[:-2])
    with pytest.raises(ValueError) as exc:
        _overlay(osg, monkeypatch, ed)
    msg = str(exc.value)
    assert "section_0.collattr.bin" in msg, msg
    assert str(CELL_FILE_BYTES - 2) in msg and str(CELL_FILE_BYTES) in msg, (
        "the refusal must name the file's size AND the expected size: " + msg)


def test_f1_converse_control_a_full_size_collattr_still_bakes(tmp_path, monkeypatch):
    """Without this, an overlay that raised on every file would pass the test above."""
    osg = _strip_gen()
    painted = _plane({(20, 10): (SOL_ALL << 12) | SHAPE_WITH_GEOMETRY})
    out_a, _out_b = _overlay(osg, monkeypatch, _one_section_editor(tmp_path, painted))
    assert out_a[10][10] != 0, "row 20 is collision row 10; the painted cell must be solid"


# The gate half. A scratch tree holding exactly what verify_editor_collision_fidelity
# reads, copied from the COMMITTED tree, so the control is today's real bake.

#: The real tree's layout, taken BEFORE any test patches the module's paths.
REAL_GEN, REAL_COLLISION = vlb.GEN, vlb.COLLISION_DIR
REL_GEN = os.path.relpath(vlb.GEN, vlb.ROOT)
REL_COLLISION = os.path.relpath(vlb.COLLISION_DIR, vlb.ROOT)


def _act():
    with open(os.path.join(REPO, "project.json")) as f:
        return json.load(f)["zones"][0]["acts"][0]


def _gate_tree(tmp_path):
    act = _act()
    root = tmp_path / "tree"
    root.mkdir()
    shutil.copy(os.path.join(REPO, "project.json"), root / "project.json")
    src_ed = os.path.join(REPO, act["dataPath"])
    dst_ed = root / act["dataPath"]
    dst_ed.mkdir(parents=True)
    for fn in os.listdir(src_ed):
        if fn.endswith((".collattr.bin", ".collattrb.bin")):
            shutil.copy(os.path.join(src_ed, fn), dst_ed / fn)
    gen = root / REL_GEN
    gen.mkdir(parents=True)
    for n in range(act["gridWidth"] * act["gridHeight"]):
        shutil.copy(os.path.join(REAL_GEN, f"sec{n}_strips_a.bin"), gen / f"sec{n}_strips_a.bin")
    shutil.copytree(REAL_COLLISION, root / REL_COLLISION)
    return root, dst_ed, gen


def _run_collision_gate(monkeypatch, root):
    monkeypatch.setattr(vlb, "ROOT", str(root))
    monkeypatch.setattr(vlb, "GEN", str(root / REL_GEN))
    monkeypatch.setattr(vlb, "PROJECT_JSON", str(root / "project.json"))
    monkeypatch.setattr(vlb, "COLLISION_DIR", str(root / REL_COLLISION))
    monkeypatch.setattr(vlb, "_fail", [])
    vlb.verify_editor_collision_fidelity()
    return list(vlb._fail)


def _authored_nonair(collattr_path):
    """Non-air cells the editor authored on plane A of one section, counted from the
    file itself: a cell is its top tile row's word, non-air when it has a shape AND a
    solidity (or a crossover mark). The expectation is derived, never a pinned count."""
    words = struct.unpack(f">{W * W}H", open(collattr_path, "rb").read())
    n = 0
    for cr in range(W // 2):
        for c in range(W):
            w = words[(2 * cr) * W + c]
            if ((w & 0x3FF) and (w >> 12) & 3) or (w >> 14) & 3:
                n += 1
    return n


def test_f1_gate_passes_the_committed_bake(tmp_path, monkeypatch):
    root, _ed, _gen = _gate_tree(tmp_path)
    fails = _run_collision_gate(monkeypatch, root)
    assert fails == [], fails


def test_f1_gate_fails_an_all_air_bake_of_an_authored_section(tmp_path, monkeypatch):
    """The sweep's D1 outcome, reproduced at the artifact: section 0's baked collision
    zeroed while its editor file still carries the authored cells."""
    root, ed, gen = _gate_tree(tmp_path)
    act = _act()
    authored = [n for n in range(act["gridWidth"] * act["gridHeight"])
                if os.path.isfile(ed / f"section_{n}.collattr.bin")
                and _authored_nonair(ed / f"section_{n}.collattr.bin") > 0]
    assert authored, (
        "the fixture needs a section with authored collision, or 'all air' proves nothing")
    sec = authored[0]
    strip_rows = vlb._strip_gen_int("STRIP_TILE_HEIGHT")
    pad = vlb._strip_gen_int("STRIP_COLLISION_PAD")
    stride = strip_rows * 2 + 2 * (strip_rows // 2) + pad
    p = gen / f"sec{sec}_strips_a.bin"
    blob = bytearray(p.read_bytes())
    for c in range(strip_rows):
        o = c * stride + strip_rows * 2
        blob[o:o + strip_rows] = bytes(strip_rows)   # both planes: 2 x (strip_rows // 2)
    p.write_bytes(bytes(blob))
    fails = _run_collision_gate(monkeypatch, root)
    assert any(f"sec{sec} plane A" in f for f in fails), fails
    assert any(f"sec{sec} plane B" in f for f in fails), fails


def test_f1_gate_fails_a_wrong_sized_collattr(tmp_path, monkeypatch):
    root, ed, _gen = _gate_tree(tmp_path)
    p = ed / "section_0.collattr.bin"
    p.write_bytes(p.read_bytes()[:-2])
    fails = _run_collision_gate(monkeypatch, root)
    assert any("section_0.collattr.bin" in f and str(CELL_FILE_BYTES - 2) in f for f in fails), fails
