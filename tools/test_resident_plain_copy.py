"""Resident plain copy (2026-09-26): the physical-form bake and the gate that holds it.

The engine copies a physical-form act's block words verbatim (PAGECACHE_DIRECT_PLAIN, no
map read, no per-word check), so the facts that make that copy exact live at build time:
tools/verify_level_bin.py verify_nt_form. These tests drive the REAL gate over a copy of
the committed tree and show that it refuses each way the copy could go wrong on screen.
Design: docs/research/2026-09-26-resident-plain-copy.md.
"""
import os
import shutil
import struct
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ojz_strip_gen as osg  # noqa: E402
import verify_level_bin as vlb  # noqa: E402

REAL_GEN = vlb.GEN
REL_GEN = os.path.relpath(vlb.GEN, vlb.ROOT)


def test_identity_map_is_identity_on_slots_and_zero_in_gaps():
    # two pages of 64: page 0 full up to slot 2, page 1 starts at 64 (a short page 0)
    m = osg.build_pool_slot_identity_map({1, 2, 64, 65})
    assert len(m) == 66
    assert m[:3] == [0, 1, 2]
    assert m[3:64] == [0] * 61                  # the gap a short page leaves maps to blank
    assert m[64:] == [64, 65]


def test_identity_map_refuses_a_slot_past_the_index_field():
    with pytest.raises(ValueError):
        osg.build_pool_slot_identity_map({osg.SECTION_LOCAL_INDEX_MAX + 1})


def _tree(tmp_path, monkeypatch):
    gen = tmp_path / REL_GEN
    gen.mkdir(parents=True)
    for fn in os.listdir(REAL_GEN):
        if fn in ("sec_local_maps.emp", "ojz_act_pool.emp") or fn.endswith(
                ("_local_map.bin", "_strips_a.bin")):
            shutil.copy(os.path.join(REAL_GEN, fn), gen / fn)
    monkeypatch.setattr(vlb, "GEN", str(gen))
    monkeypatch.setattr(vlb, "_fail", [])
    return gen


def _run(monkeypatch):
    monkeypatch.setattr(vlb, "_fail", [])
    vlb.verify_nt_form()
    return list(vlb._fail)


def test_committed_tree_is_physical_and_passes(tmp_path, monkeypatch):
    _tree(tmp_path, monkeypatch)
    assert vlb._nt_form_flag() == 1, "OJZ act 1 fits PAGE_FRAMES; the bake rule makes it PHYSICAL"
    assert _run(monkeypatch) == []


def test_a_local_flag_on_a_resident_act_is_refused(tmp_path, monkeypatch):
    gen = _tree(tmp_path, monkeypatch)
    p = gen / "sec_local_maps.emp"
    p.write_text(p.read_text().replace("OJZ_ACT_NT_PHYSICAL = 1", "OJZ_ACT_NT_PHYSICAL = 0"))
    fails = _run(monkeypatch)
    assert any("bake rule gives 1" in f for f in fails), fails


def test_a_non_identity_map_is_refused(tmp_path, monkeypatch):
    gen = _tree(tmp_path, monkeypatch)
    p = gen / "sec3_local_map.bin"
    b = bytearray(p.read_bytes())
    b[2 * 5:2 * 5 + 2] = struct.pack(">H", 6)       # map[5] = 6: a translating loop now disagrees
    p.write_bytes(bytes(b))
    fails = _run(monkeypatch)
    assert any("sec3_local_map.bin is not the pool-slot identity" in f for f in fails), fails


def _first_word(blob, pred):
    for off in range(0, len(blob), 2):
        w = struct.unpack(">H", blob[off:off + 2])[0]
        if pred(off, w):
            return off
    raise AssertionError("no such word")


def test_a_blank_word_with_attribute_bits_is_refused(tmp_path, monkeypatch):
    gen = _tree(tmp_path, monkeypatch)
    p = gen / "sec0_strips_a.bin"
    b = bytearray(p.read_bytes())
    off = _first_word(b[:512], lambda o, w: w == 0)  # a blank word in column 0's nametable
    b[off:off + 2] = struct.pack(">H", 0x8000)        # priority bit on a blank
    p.write_bytes(bytes(b))
    fails = _run(monkeypatch)
    assert any("1 blank word(s) carrying attribute bits" in f for f in fails), fails


def test_a_word_naming_no_pool_slot_is_refused(tmp_path, monkeypatch):
    gen = _tree(tmp_path, monkeypatch)
    p = gen / "sec0_strips_a.bin"
    b = bytearray(p.read_bytes())
    off = _first_word(b[:512], lambda o, w: (w & 0x7FF) != 0)
    w = struct.unpack(">H", b[off:off + 2])[0]
    b[off:off + 2] = struct.pack(">H", (w & 0xF800) | 0x7FF)   # slot 2047: past the pool
    p.write_bytes(bytes(b))
    fails = _run(monkeypatch)
    assert any("1 word(s) naming no pool slot" in f for f in fails), fails


def test_a_tree_without_the_flag_is_refused(tmp_path, monkeypatch):
    gen = _tree(tmp_path, monkeypatch)
    p = gen / "sec_local_maps.emp"
    p.write_text("\n".join(l for l in p.read_text().splitlines()
                           if "OJZ_ACT_NT_PHYSICAL" not in l) + "\n")
    fails = _run(monkeypatch)
    assert any("declares no `pub const OJZ_ACT_NT_PHYSICAL" in f for f in fails), fails
