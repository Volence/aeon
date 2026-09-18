#!/usr/bin/env python3
"""The clip-reachability gate's own rows — DONOR-FREE, BUILD-FREE.

These drive `tools/clip_reachability.py` over synthetic generated trees built in
tmp_path. They deliberately do NOT need a converted donor tree, a baked act or a ROM:
the subject is the gate's DECISION LOGIC, and a row that needed a donor would be a row
that silently stops running on a fresh checkout.

`clip_manifest.load` is stubbed for the same reason — it validates against a converted
donor tree and has its own rows in tools/test_clip_manifest.py. What is NOT stubbed is
anything the gate derives: the strip layout comes from ojz_strip_gen's source, SOLID_TOP
and the collision cell geometry from engine/system/constants.emp, and plane B's
reachability from the crossover table on disk.

THE ROW THAT MATTERS MOST is test_an_undeclared_void_fails: that is the state
s2_ehz_boot shipped in on 2026-09-17, where ten green lanes and a green `ground` check
sat on top of an act whose painted world stopped at x=4096 with 2,048 px of walk-in void
behind it.
"""

import json
import os
import struct
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import clip_reachability as CR          # noqa: E402
import clip_rom_bake                    # noqa: E402

SECTION_PX = 2048
SECTION_TILES = SECTION_PX // 8
STRIDE = 776                            # re-derived below; this is only the fixture size


class _Clip:
    def __init__(self, cid, dst):
        self.id = cid
        self.dst = dst


class _Act:
    def __init__(self, aid, clips, raw):
        self.id = aid
        self.clips = clips
        self.raw = raw
        self.section_px = SECTION_PX


def _geometry():
    rows = CR.strip_gen_int("STRIP_TILE_HEIGHT")
    pad = CR.strip_gen_int("STRIP_COLLISION_PAD")
    coll_rows = rows // 2
    return rows, coll_rows, rows * 2 + 2 * coll_rows + pad


def _write_tree(tmp_path, grid_w, grid_h, painted_to_x, *, floor_attr=1,
                plane_b_holes=(), art_holes=(), floor_holes=()):
    """A generated tree: `painted_to_x` px of art + floor, the rest air.

    `plane_b_holes` / `art_holes` / `floor_holes` are world-x values (8-px columns) to
    punch out of an otherwise complete act — the mutations the rows below are about.
    """
    rows, coll_rows, stride = _geometry()
    gen = tmp_path / "gen"
    coll = tmp_path / "coll"
    gen.mkdir(exist_ok=True)
    coll.mkdir(exist_ok=True)

    solidity = bytearray(256)
    solidity[floor_attr] = CR.engine_const("SOLID_TOP")
    (coll / "solidity.bin").write_bytes(bytes(solidity))
    heights = bytearray(256 * 16)
    for i in range(16):
        heights[floor_attr * 16 + i] = 16
    (coll / "heightmaps.bin").write_bytes(bytes(heights))
    (coll / "crossover.bin").write_bytes(bytes(256))

    floor_row = 40                      # 16-px collision row -> world y 640
    tile_row = 80                       # 8-px tile row       -> world y 640
    for n in range(grid_w * grid_h):
        sx, sy = n % grid_w, n // grid_w
        buf = bytearray(rows * stride)
        if sy == 0:                     # only the top section row carries anything
            for lx in range(SECTION_TILES):
                wx = sx * SECTION_PX + lx * 8
                if wx >= painted_to_x:
                    continue
                base = lx * stride
                if wx not in art_holes:
                    struct.pack_into(">H", buf, base + tile_row * 2, 0x4000 | 7)
                if wx not in floor_holes:
                    buf[base + rows * 2 + floor_row] = floor_attr
                if wx not in plane_b_holes and wx not in floor_holes:
                    buf[base + rows * 2 + coll_rows + floor_row] = floor_attr
        (gen / f"sec{n}_strips_a.bin").write_bytes(bytes(buf))
    return gen, coll


def _install(monkeypatch, gen, grid, act_id="fixture_act", clips=None, declared=None):
    import act_grid
    import clip_manifest
    raw = {}
    if declared is not None:
        raw["unpainted_remainder"] = declared
    act = _Act(act_id, clips or [_Clip("c0", [0, 0, 2048, 1024])], raw)
    monkeypatch.setattr(clip_manifest, "load", lambda *a, **k: act)
    monkeypatch.setattr(act_grid, "descriptor_grid", lambda *a, **k: grid)
    clip_rom_bake.write_stamp(act, str(gen), "fixture/clips.json")
    return act


def _run(gen, coll, capsys=None):
    return CR.check("fixture/clips.json", gen_dir=str(gen), coll_dir=str(coll), log=None)


# ---------------------------------------------------------------------------
# The act-wide question
# ---------------------------------------------------------------------------

def test_a_complete_act_with_a_matching_declaration_passes(tmp_path, monkeypatch):
    gen, coll = _write_tree(tmp_path, 2, 1, painted_to_x=4096)
    _install(monkeypatch, gen, (2, 1),
             declared={"x_from": 4096, "why": "the act is fully painted"})
    assert _run(gen, coll) == 0


def test_an_undeclared_void_fails(tmp_path, monkeypatch, capsys):
    """THE INCIDENT. A clip that paints 2,048 px of a 4,096 px act, declaring nothing."""
    gen, coll = _write_tree(tmp_path, 2, 1, painted_to_x=2048)
    _install(monkeypatch, gen, (2, 1))
    assert _run(gen, coll) == 1
    err = capsys.readouterr().err
    assert "declares no `unpainted_remainder`" in err
    assert "ends at x=2048" in err
    assert "act runs to x=4096" in err


def test_a_declaration_that_reserves_less_than_the_bytes_do_names_missing_content(
        tmp_path, monkeypatch, capsys):
    gen, coll = _write_tree(tmp_path, 2, 1, painted_to_x=2048)
    _install(monkeypatch, gen, (2, 1),
             declared={"x_from": 3072, "why": "declared edge"})
    assert _run(gen, coll) == 1
    err = capsys.readouterr().err
    assert "CONTENT IS MISSING" in err
    assert "1024 px" in err


def test_a_stale_declaration_fails(tmp_path, monkeypatch, capsys):
    """The other side of the two-sided check: the act grew and the gate stopped asking."""
    gen, coll = _write_tree(tmp_path, 2, 1, painted_to_x=4096)
    _install(monkeypatch, gen, (2, 1),
             declared={"x_from": 2048, "why": "written when the clip was half this wide"})
    assert _run(gen, coll) == 1
    assert "THE DECLARATION IS STALE" in capsys.readouterr().err


def test_a_declaration_without_a_why_fails(tmp_path, monkeypatch, capsys):
    gen, coll = _write_tree(tmp_path, 2, 1, painted_to_x=2048)
    _install(monkeypatch, gen, (2, 1), declared={"x_from": 2048, "why": "   "})
    assert _run(gen, coll) == 1
    assert 'no "why"' in capsys.readouterr().err


def test_a_column_with_no_floor_on_the_reachable_plane_fails(tmp_path, monkeypatch,
                                                             capsys):
    gen, coll = _write_tree(tmp_path, 2, 1, painted_to_x=4096, floor_holes=(1600,))
    _install(monkeypatch, gen, (2, 1),
             declared={"x_from": 4096, "why": "fully painted"})
    assert _run(gen, coll) == 1
    err = capsys.readouterr().err
    assert "plane A has NO landing surface in 1 column" in err
    assert "(1600, 1608)" in err


def test_a_hole_inside_the_painted_world_is_not_read_as_an_edge(tmp_path, monkeypatch,
                                                                capsys):
    gen, coll = _write_tree(tmp_path, 2, 1, painted_to_x=4096, art_holes=(1600,))
    _install(monkeypatch, gen, (2, 1),
             declared={"x_from": 4096, "why": "fully painted"})
    assert _run(gen, coll) == 1
    assert "That is a hole, not an edge" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# Plane B: informational until the crossover table makes it reachable
# ---------------------------------------------------------------------------

def test_plane_b_holes_are_informational_until_a_crossover_is_marked(
        tmp_path, monkeypatch, capsys):
    """The latent defect this parcel found, and the condition that would expose it.

    Every act before the first Sonic 2 clip had plane B as a byte-for-byte copy of
    plane A (ojz_block_gen.test_extract_block asserts it), so a plane-B hole could not
    exist. It can now — and it is harmless exactly while nothing writes the player's
    layer byte.
    """
    gen, coll = _write_tree(tmp_path, 2, 1, painted_to_x=4096,
                            plane_b_holes=(1600, 1608))
    _install(monkeypatch, gen, (2, 1),
             declared={"x_from": 4096, "why": "fully painted"})
    assert _run(gen, coll) == 0, "plane B is unreachable, so its holes cannot be fallen into"

    table = bytearray((coll / "crossover.bin").read_bytes())
    table[9] = 1                                   # one marked attr byte is enough
    (coll / "crossover.bin").write_bytes(bytes(table))
    assert _run(gen, coll) == 1
    err = capsys.readouterr().err
    assert "plane B has NO landing surface in 2 column" in err
    assert "(1600, 1616)" in err


def test_reachable_planes_reads_the_table_rather_than_assuming(tmp_path):
    coll = tmp_path / "coll"
    coll.mkdir()
    (coll / "crossover.bin").write_bytes(bytes(256))
    planes, why = CR.reachable_planes(str(coll))
    assert planes == (0,) and "unreachable" in why

    (coll / "crossover.bin").write_bytes(bytes(200) + b"\x03" + bytes(55))
    planes, why = CR.reachable_planes(str(coll))
    assert planes == (0, 1) and "first: 200" in why


@pytest.mark.parametrize("payload", [None, b""])
def test_an_unreadable_crossover_table_is_unmeasurable(tmp_path, payload):
    coll = tmp_path / "coll"
    coll.mkdir()
    if payload is not None:
        (coll / "crossover.bin").write_bytes(payload)
    with pytest.raises(CR.Unmeasurable):
        CR.reachable_planes(str(coll))


# ---------------------------------------------------------------------------
# Loud when it cannot measure — exit 2, never a pass
# ---------------------------------------------------------------------------

def test_a_missing_strip_is_unmeasurable(tmp_path, monkeypatch):
    gen, coll = _write_tree(tmp_path, 2, 1, painted_to_x=4096)
    _install(monkeypatch, gen, (2, 1),
             declared={"x_from": 4096, "why": "fully painted"})
    os.remove(gen / "sec1_strips_a.bin")
    with pytest.raises(CR.Unmeasurable) as e:
        _run(gen, coll)
    assert "sec1_strips_a.bin is missing" in str(e.value)


def test_a_short_strip_is_unmeasurable(tmp_path, monkeypatch):
    gen, coll = _write_tree(tmp_path, 2, 1, painted_to_x=4096)
    _install(monkeypatch, gen, (2, 1),
             declared={"x_from": 4096, "why": "fully painted"})
    p = gen / "sec0_strips_a.bin"
    p.write_bytes(p.read_bytes()[:-1])
    with pytest.raises(CR.Unmeasurable) as e:
        _run(gen, coll)
    assert "B per column is" in str(e.value)


def test_the_cli_exits_2_on_unmeasurable(tmp_path, monkeypatch):
    """The exit CODE, not just the exception — `gate strict` grades the number."""
    gen, coll = _write_tree(tmp_path, 2, 1, painted_to_x=4096)
    _install(monkeypatch, gen, (2, 1),
             declared={"x_from": 4096, "why": "fully painted"})
    os.remove(gen / "sec0_strips_a.bin")
    with pytest.raises(SystemExit) as e:
        CR.main(["check", "fixture/clips.json", "--gen-dir", str(gen),
                 "--coll-dir", str(coll)])
    assert e.value.code == 2


def test_strip_gen_int_is_loud_when_the_constant_moved(tmp_path):
    src = tmp_path / "ojz_strip_gen.py"
    src.write_text("STRIP_TILE_HEIGHT = something_else\n")
    with pytest.raises(CR.Unmeasurable) as e:
        CR.strip_gen_int("STRIP_TILE_HEIGHT", src=str(src))
    assert "no longer defines" in str(e.value)


def test_a_declared_bound_must_be_an_integer_in_range(tmp_path):
    with pytest.raises(CR.Unmeasurable) as e:
        CR._declared_bound({}, "x_from", 4096, "x")
    assert 'has no "x_from"' in str(e.value)
    for bad in ("4096", 4097, -1, True):
        with pytest.raises(CR.Unmeasurable):
            CR._declared_bound({"x_from": bad}, "x_from", 4096, "x")


# ---------------------------------------------------------------------------
# The stamp — a tree that is not this act's cannot be measured as if it were
# ---------------------------------------------------------------------------

def test_an_unstamped_tree_is_unmeasurable(tmp_path, monkeypatch):
    gen, coll = _write_tree(tmp_path, 2, 1, painted_to_x=4096)
    _install(monkeypatch, gen, (2, 1),
             declared={"x_from": 4096, "why": "fully painted"})
    os.remove(gen / clip_rom_bake.STAMP_NAME)
    with pytest.raises(CR.Unmeasurable) as e:
        _run(gen, coll)
    assert "carries no clip_bake_stamp.json" in str(e.value)


def test_a_stamp_from_a_different_clip_act_is_named_as_stale_not_as_geometry(
        tmp_path, monkeypatch):
    """The trap this closes: a stale tree used to answer as `donor_corroboration`'s
    "a difference that is a multiple of 8 or 16 is a PASTE SHIFT"."""
    gen, coll = _write_tree(tmp_path, 2, 1, painted_to_x=4096)
    _install(monkeypatch, gen, (2, 1),
             declared={"x_from": 4096, "why": "fully painted"})
    stamp = gen / clip_rom_bake.STAMP_NAME
    d = json.loads(stamp.read_text())
    d["act"] = "some_other_clip"
    stamp.write_text(json.dumps(d))
    with pytest.raises(CR.Unmeasurable) as e:
        _run(gen, coll)
    msg = str(e.value)
    assert "STALE TREE, not a geometry problem" in msg
    assert "some_other_clip" in msg


def test_a_bare_bake_leaves_no_stamp_so_the_readers_refuse(tmp_path):
    """The bare-bake default and the stamp are ONE mechanism, not two.

    A bare `bake` restores the tree, so the tree it leaves has no stamp, so `ground` and
    clip_reachability refuse it by name instead of measuring the shipped act.
    """
    gen = tmp_path / "gen"
    gen.mkdir()
    with pytest.raises(clip_rom_bake.ClipRomError) as e:
        clip_rom_bake.require_stamp("anything", str(gen), "ground")
    assert "--keep" in str(e.value)
