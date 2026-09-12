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


# ---------------------------------------------------------------------------
# F2 -- a missing LAST section file used to ship a short local-map table
# ---------------------------------------------------------------------------

def test_f2_the_grid_has_one_source_and_the_engine_must_agree(tmp_path):
    import act_grid
    w, h = act_grid.section_grid()
    assert (w, h) == act_grid.descriptor_grid()
    proj = json.load(open(os.path.join(REPO, "project.json")))
    proj["zones"][0]["acts"][0]["gridHeight"] = h + 1
    p = tmp_path / "project.json"
    p.write_text(json.dumps(proj))
    with pytest.raises(act_grid.ActGridError) as exc:
        act_grid.section_grid(str(p))
    assert "act descriptor" in str(exc.value), str(exc.value)


def test_f2_a_descriptor_that_stops_declaring_the_grid_is_refused(tmp_path):
    import act_grid
    d = tmp_path / "act_descriptor.emp"
    d.write_text("module games.sonic4.ojz_act1_descriptor\n")
    with pytest.raises(act_grid.ActGridError):
        act_grid.descriptor_grid(str(d))


def test_f2_a_missing_last_section_file_is_refused(tmp_path):
    import act_grid
    osg = _strip_gen()
    n = act_grid.section_count()
    for i in range(n - 1):
        (tmp_path / f"section_{i}.tiles.bin").write_bytes(bytes(CELL_FILE_BYTES))
    with pytest.raises(SystemExit) as exc:
        osg.require_editor_sections(str(tmp_path), n)
    assert f"section_{n - 1}.tiles.bin" in str(exc.value), str(exc.value)
    # converse control: the full set passes, in flat-id order
    (tmp_path / f"section_{n - 1}.tiles.bin").write_bytes(bytes(CELL_FILE_BYTES))
    got = osg.require_editor_sections(str(tmp_path), n)
    assert [os.path.basename(p) for p in got] == [f"section_{i}.tiles.bin" for i in range(n)]


def test_f2_the_local_map_table_must_cover_the_whole_grid(tmp_path):
    import act_grid
    osg = _strip_gen()
    n = act_grid.section_count()
    maps = [(str(i), [0, i + 1]) for i in range(n - 1)]
    with pytest.raises(RuntimeError) as exc:
        osg.emit_section_local_maps(maps, str(tmp_path), n)
    assert f"missing [{n - 1}]" in str(exc.value), str(exc.value)
    maps.append((str(n - 1), [0, n]))
    osg.emit_section_local_maps(maps, str(tmp_path), n)
    assert f"[*u8; {n}]" in (tmp_path / "sec_local_maps.emp").read_text()


def _run_gate(monkeypatch, root, fn, *args):
    monkeypatch.setattr(vlb, "ROOT", str(root))
    monkeypatch.setattr(vlb, "GEN", str(root / REL_GEN))
    monkeypatch.setattr(vlb, "PROJECT_JSON", str(root / "project.json"))
    monkeypatch.setattr(vlb, "COLLISION_DIR", str(root / REL_COLLISION))
    monkeypatch.setattr(vlb, "_fail", [])
    fn(*args)
    return list(vlb._fail)


def _gen_tree(tmp_path, files):
    root = tmp_path / "tree"
    (root / REL_GEN).mkdir(parents=True)
    shutil.copy(os.path.join(REPO, "project.json"), root / "project.json")
    for fn in files:
        shutil.copy(os.path.join(REAL_GEN, fn), root / REL_GEN / fn)
    return root


def test_f2_gate_fails_a_local_map_table_short_of_the_grid(tmp_path, monkeypatch):
    import act_grid
    n = act_grid.section_count()
    root = _gen_tree(tmp_path, ["sec_local_maps.emp"])
    assert _run_gate(monkeypatch, root, vlb.verify_local_map_table, n) == []
    p = root / REL_GEN / "sec_local_maps.emp"
    txt = p.read_text()
    last = f', extern("OJZ_Sec{n - 1}_LocalMap")'
    assert f"[*u8; {n}]" in txt and last in txt, "the emitter's table shape moved"
    p.write_text(txt.replace(f"[*u8; {n}]", f"[*u8; {n - 1}]").replace(last, ""))
    fails = _run_gate(monkeypatch, root, vlb.verify_local_map_table, n)
    assert any(f"[*u8; {n - 1}]" in f for f in fails), fails


def test_f2_gate_fails_a_leftover_section_outside_the_grid(tmp_path, monkeypatch):
    import act_grid
    n = act_grid.section_count()
    root = _gen_tree(tmp_path, ["sec0_local_map.bin"])
    assert _run_gate(monkeypatch, root, vlb.verify_section_set) == []
    shutil.copy(os.path.join(REAL_GEN, "sec0_local_map.bin"),
                root / REL_GEN / f"sec{n}_local_map.bin")
    fails = _run_gate(monkeypatch, root, vlb.verify_section_set)
    assert any(f"sec{n}_local_map.bin" in f for f in fails), fails


class _PastTheRefusal(Exception):
    pass


def test_f2_block_gen_refuses_a_grid_section_without_strips(tmp_path, monkeypatch):
    """The block baker used to iterate a literal 9 and bake whatever strips were on
    disk. Converse control: with every strip present it gets past the refusal to the
    pool -- stubbed with a sentinel, so no compression runs and nothing is written."""
    import act_grid
    import ojz_block_gen as bg

    def boom(*_a, **_k):
        raise _PastTheRefusal()

    monkeypatch.setattr(bg, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(bg.multiprocessing, "Pool", boom)
    n = act_grid.section_count()
    for i in range(n - 1):
        (tmp_path / f"sec{i}_strips_a.bin").write_bytes(b"")
    with pytest.raises(SystemExit) as exc:
        bg.generate_all(use_cache=False)
    assert f"[{n - 1}]" in str(exc.value), str(exc.value)
    (tmp_path / f"sec{n - 1}_strips_a.bin").write_bytes(b"")
    with pytest.raises(_PastTheRefusal):
        bg.generate_all(use_cache=False)


# ---------------------------------------------------------------------------
# F3 -- an index past the tileset baked a blank tile, and the gate zero-filled too
# ---------------------------------------------------------------------------

def test_f3_an_index_past_the_tileset_is_refused():
    osg = _strip_gen()
    blob = bytes(range(32)) + bytes(range(32, 64))        # exactly two tiles
    with pytest.raises(ValueError) as exc:
        osg.collect_referenced_tiles({"0": [[0x0000, 0x0001, 0x0002]]}, blob,
                                     source="fixture blob")
    msg = str(exc.value)
    assert "fixture blob" in msg and "highest index 2" in msg, msg
    # converse control: in-range references return the real bytes, not padding
    idx, raw = osg.collect_referenced_tiles({"0": [[0x0000, 0x0001]]}, blob)
    assert idx == [0, 1] and raw == [blob[:32], blob[32:]]


def test_f3_the_bg_blob_refuses_an_index_past_its_art(tmp_path):
    osg = _strip_gen()
    blob = bytes(32) + bytes([0x11] * 32)                 # blank + a solid tile
    with pytest.raises(ValueError) as exc:
        osg.emit_bg_tile_blob([0x0000, 0x0001, 0x0003], blob, str(tmp_path / "bg.bin"))
    assert "highest 3" in str(exc.value), str(exc.value)
    _map, count = osg.emit_bg_tile_blob([0x0000, 0x0001], blob, str(tmp_path / "bg.bin"))
    assert count == 2


def test_f3_the_gate_does_not_invent_a_blank_tile():
    assert vlb._tile_pixels(bytes(64), 2, 0, 0) is None, (
        "a tile past the blob must be reported, not resolved to blank")
    assert vlb._tile_pixels(bytes(64), 1, 0, 0) == bytes(32)


def _bake_tree(tmp_path):
    """A scratch tree holding what verify_editor_bake_fidelity reads, copied from the
    committed tree: project.json, the editor tileset and section nametables, and the
    generated strips, local maps and pool pages."""
    with open(os.path.join(REPO, "project.json")) as f:
        zone = json.load(f)["zones"][0]
    act = zone["acts"][0]
    n = act["gridWidth"] * act["gridHeight"]
    root = tmp_path / "tree"
    root.mkdir()
    shutil.copy(os.path.join(REPO, "project.json"), root / "project.json")
    ts = root / zone["tileset"]
    ts.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(os.path.join(REPO, zone["tileset"]), ts)
    ed = root / act["dataPath"]
    ed.mkdir(parents=True, exist_ok=True)
    gen = root / REL_GEN
    gen.mkdir(parents=True)
    for i in range(n):
        shutil.copy(os.path.join(REPO, act["dataPath"], f"section_{i}.tiles.bin"), ed)
        for stem in ("strips_source", "strips_a"):
            shutil.copy(os.path.join(REAL_GEN, f"sec{i}_{stem}.bin"), gen)
        shutil.copy(os.path.join(REAL_GEN, f"sec{i}_local_map.bin"), gen)
    for fn in os.listdir(REAL_GEN):
        if fn.startswith("act_pool_page") and fn.endswith(".bin"):
            shutil.copy(os.path.join(REAL_GEN, fn), gen)
    return root, ts, ed, n


def test_f3_gate_fails_a_tileset_shorter_than_the_editor_references(tmp_path, monkeypatch):
    """The sweep's fixture A at the artifact: the tileset loses tiles the editor still
    names. The cut point is DERIVED from the editor files (the highest index they
    reference), never a pinned count."""
    root, ts, ed, n = _bake_tree(tmp_path)
    assert _run_gate(monkeypatch, root, vlb.verify_editor_bake_fidelity) == []
    highest = max(max(w & 0x07FF for w in struct.unpack(
        f">{W * W}H", (ed / f"section_{i}.tiles.bin").read_bytes())) for i in range(n))
    assert highest > 0, "the fixture needs a referenced tile to cut away"
    ts.write_bytes(ts.read_bytes()[:highest * 32])        # tiles 0..highest-1 survive
    fails = _run_gate(monkeypatch, root, vlb.verify_editor_bake_fidelity)
    assert any("past the end of the" in f and f"highest index {highest}" in f
               for f in fails), fails


# ---------------------------------------------------------------------------
# F5 -- refusals must come before the first write, or the write must be undone
# ---------------------------------------------------------------------------

def test_f5_a_wrong_sized_collattrb_is_refused_not_mirrored(tmp_path, monkeypatch):
    osg = _strip_gen()
    painted = _plane({(20, 10): (SOL_ALL << 12) | SHAPE_WITH_GEOMETRY})
    ed = _one_section_editor(tmp_path, painted, collattrb=bytes(CELL_FILE_BYTES - 2))
    with pytest.raises(ValueError) as exc:
        _overlay(osg, monkeypatch, ed)
    msg = str(exc.value)
    assert "section_0.collattrb.bin" in msg and str(CELL_FILE_BYTES - 2) in msg, msg


def test_f5_converse_an_absent_collattrb_still_mirrors_plane_a(tmp_path, monkeypatch):
    osg = _strip_gen()
    painted = _plane({(20, 10): (SOL_ALL << 12) | SHAPE_WITH_GEOMETRY})
    out_a, out_b = _overlay(osg, monkeypatch, _one_section_editor(tmp_path, painted))
    assert out_a[10][10] != 0 and out_b[10][10] == out_a[10][10]


def _editor_inputs(tmp_path, n, tiles=4):
    ed = tmp_path / "ed"
    ed.mkdir()
    for i in range(n):
        (ed / f"section_{i}.tiles.bin").write_bytes(bytes(CELL_FILE_BYTES))
        (ed / f"section_{i}.collattr.bin").write_bytes(bytes(CELL_FILE_BYTES))
        (ed / f"section_{i}.collattrb.bin").write_bytes(bytes(CELL_FILE_BYTES))
    ts = tmp_path / "tiles.bin"
    ts.write_bytes(bytes(32 * tiles))
    return ed, ts


@pytest.mark.parametrize("defect", [
    "collattr_short", "collattrb_short", "tiles_short", "missing_last_section",
    "index_past_tileset", "partial_tile",
])
def test_f5_every_editor_input_refusal_is_decided_before_the_first_write(tmp_path, defect):
    """validate_editor_inputs is what preflight() runs before regenerate-level.sh's
    first write. Each row is one defect the bake used to meet only after that write."""
    import act_grid
    osg = _strip_gen()
    n = act_grid.section_count()
    ed, ts = _editor_inputs(tmp_path, n)
    osg.validate_editor_inputs(str(ed), str(ts), n)      # converse control: valid inputs pass
    if defect == "collattr_short":
        (ed / "section_0.collattr.bin").write_bytes(bytes(CELL_FILE_BYTES - 2))
        want = "section_0.collattr.bin is"
    elif defect == "collattrb_short":
        (ed / "section_1.collattrb.bin").write_bytes(bytes(CELL_FILE_BYTES - 2))
        want = "section_1.collattrb.bin is"
    elif defect == "tiles_short":
        (ed / "section_0.tiles.bin").write_bytes(bytes(CELL_FILE_BYTES - 2))
        want = "section_0.tiles.bin is"
    elif defect == "missing_last_section":
        (ed / f"section_{n - 1}.tiles.bin").unlink()
        want = f"section_{n - 1}.tiles.bin is MISSING"
    elif defect == "index_past_tileset":
        buf = bytearray(CELL_FILE_BYTES)
        struct.pack_into(">H", buf, 0, 0x0004)            # tile 4 of a 4-tile set
        (ed / "section_2.tiles.bin").write_bytes(bytes(buf))
        want = "highest index 4"
    else:
        ts.write_bytes(bytes(32 * 4 + 2))
        want = "not a non-empty whole number"
    with pytest.raises(SystemExit) as exc:
        osg.validate_editor_inputs(str(ed), str(ts), n)
    assert want in str(exc.value), str(exc.value)


# The restore half, run for real: tools/regenerate-level.sh copied into a scratch git
# repository and driven with STUB tools (TOOLS=stubs), so no donor and no real bake are
# needed and nothing outside tmp_path can be touched.

_STUB_WRITER = r'''
import os, sys
os.makedirs("games/sonic4/data/generated/ojz/act1", exist_ok=True)
FAIL_AT = os.environ.get("STUB_FAIL_AT", "")
def fail_here(step):
    if FAIL_AT == step:
        print(f"stub {step}: refusing on purpose", file=sys.stderr)
        sys.exit(1)
'''


def _stub_repo(tmp_path):
    import subprocess
    repo = tmp_path / "repo"
    (repo / "tools").mkdir(parents=True)
    shutil.copy(os.path.join(HERE, "regenerate-level.sh"), repo / "tools" / "regenerate-level.sh")
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    stubs = repo / "stubs"
    (stubs / "bin").mkdir(parents=True)
    salv = stubs / "bin" / "salvador"
    salv.write_text("#!/bin/sh\ncp \"$1\" \"$2\"\n")
    salv.chmod(0o755)
    bodies = {
        "ojz_strip_gen.py": _STUB_WRITER + r'''
if sys.argv[1] == "preflight":
    sys.exit(0)
open("games/sonic4/data/collision/heightmaps.bin", "wb").write(b"BAKED")
open("games/sonic4/data/generated/ojz/act1/keep.bin", "wb").write(b"BAKED")
open("games/sonic4/data/generated/ojz/act1/new.bin", "wb").write(b"NEW")
open("games/sonic4/data/generated/ojz/act1/ojz_act_pool_manifest.emp", "w").write(
    "pub const OJZ_ACT_POOL_PAGES = 0\n")
open("games/sonic4/data/generated/ojz/act1/ojz_act_pool_manifest.json", "w").write(
    '{"pages": []}\n')
fail_here("generate")
''',
        "import_sk_collision.py": _STUB_WRITER + r'''
open("games/sonic4/data/collision/angles.bin", "wb").write(b"RAW BASE BANK")
''',
        "effects_gen.py": _STUB_WRITER,
        "ojz_block_gen.py": _STUB_WRITER,
        "verify_level_bin.py": _STUB_WRITER + 'fail_here("verify")\n',
        "level_staleness.py": _STUB_WRITER,
    }
    for name, body in bodies.items():
        (stubs / name).write_text(body)
    coll = repo / "games" / "sonic4" / "data" / "collision"
    gen = repo / "games" / "sonic4" / "data" / "generated" / "ojz" / "act1"
    coll.mkdir(parents=True)
    gen.mkdir(parents=True)
    (coll / "heightmaps.bin").write_bytes(b"INTERNED heightmaps")
    (coll / "angles.bin").write_bytes(b"INTERNED angles")
    (gen / "keep.bin").write_bytes(b"COMMITTED")
    return repo


def _tree_bytes(repo):
    out = {}
    for sub in ("collision", "generated"):
        base = repo / "games" / "sonic4" / "data" / sub
        for dp, _d, fns in os.walk(base):
            for fn in fns:
                p = os.path.join(dp, fn)
                out[os.path.relpath(p, repo)] = open(p, "rb").read()
    return out


def _run_rebake(repo, tmp_path, fail_at):
    import subprocess
    snap_root = tmp_path / "tmpdir"
    snap_root.mkdir(exist_ok=True)
    env = dict(os.environ, TOOLS="stubs", STUB_FAIL_AT=fail_at, TMPDIR=str(snap_root))
    p = subprocess.run(["bash", "tools/regenerate-level.sh"], cwd=repo, env=env,
                       capture_output=True, text=True)
    return p, snap_root


@pytest.mark.parametrize("fail_at", ["generate", "verify"])
def test_f5_a_refusal_after_the_first_write_leaves_the_tree_as_it_was(tmp_path, fail_at):
    """`generate`: a refusal inside the bake (e.g. an R2 self-mark) after
    import_sk_collision.py has rewritten the tables. `verify`: the drift gate failing
    at the very end, after every output was rewritten."""
    repo = _stub_repo(tmp_path)
    before = _tree_bytes(repo)
    p, snaps = _run_rebake(repo, tmp_path, fail_at)
    assert p.returncode != 0, p.stdout + p.stderr
    assert "restored" in p.stderr, p.stderr
    assert _tree_bytes(repo) == before, (
        "a failed re-bake must leave collision/ and generated/ byte-identical to "
        "before it ran -- incl. deleting what it added")
    assert list(snaps.iterdir()) == [], "the snapshot must be removed afterwards"


def test_f5_converse_a_successful_rebake_keeps_its_outputs(tmp_path):
    """Without this, a trap that restored unconditionally would pass the test above."""
    repo = _stub_repo(tmp_path)
    p, snaps = _run_rebake(repo, tmp_path, "")
    assert p.returncode == 0, p.stdout + p.stderr
    after = _tree_bytes(repo)
    assert after["games/sonic4/data/collision/heightmaps.bin"] == b"BAKED"
    assert after["games/sonic4/data/generated/ojz/act1/new.bin"] == b"NEW"
    assert "restored" not in p.stderr, p.stderr
    assert list(snaps.iterdir()) == []
