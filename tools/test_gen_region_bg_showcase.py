"""tools/gen_region_bg_showcase.py — the DEBUG region background the region bg switch is
gated against (plan docs/superpowers/plans/2026-09-16-region-bg-switch.md, task 2; source
replaced by parcel/showcase-classic-bg: Sonic 2 Oil Ocean Zone's background, own palette).

What is held here:
  * the emitted layout is the Plane B blob shape, rebased, references ONLY the blob's own
    tiles, paints every cell (the donor is one plane tall) and lays every cell on the
    generator's SHOWCASE_LINE;
  * the tile blob fits the static budget, is NOT the act default's, and is OPAQUE (the donor's
    sky is its backdrop colour, resolved into art: a colour-0 pixel on Plane B would show
    Aeon's backdrop instead);
  * the palette changes SHOWCASE_LINE and nothing else, and NO foreground tile in any section
    of the act is on SHOWCASE_LINE (so the swap recolours no level art) — measured from the
    shipped section blobs, not from the generator's docstring;
  * the committed outputs are what the generator emits (the drift check);
  * the emp mirror of the tile count equals the blob's (act_assets.emp types the embed by it);
  * the library-entry source still lowers, with the act palette unchanged;
  * the rebase rule factored out of inject_editor_bg.main() still reproduces the committed act
    default blob, so the refactor changed no output.
"""
import collections
import json
import os
import pathlib
import re
import struct
import subprocess
import sys

import gen_region_bg_showcase as g
import inject_editor_bg
from vram_map import BG_TILE_BASE_SLOT, BG_STATIC_TILE_BUDGET

REPO = pathlib.Path(__file__).resolve().parent.parent
COLONNADE = "deep-forest-v15-marching-colonnade-1781232423352"


def test_showcase_layout_is_row_major_rebased_and_references_only_its_own_tiles():
    layout, tiles, count, _pal, _info = g.build()
    assert len(layout) == 64 * 64 * 2
    words = struct.unpack(">4096H", layout)
    assert all(words), "a showcase cell is word 0: the donor is one plane tall and paints all 64 rows"
    used = {w & 0x7FF for w in words}
    assert min(used) >= BG_TILE_BASE_SLOT and max(used) < BG_TILE_BASE_SLOT + count, (
        f"layout tile indices span {min(used)}..{max(used)}; they must lie in "
        f"[{BG_TILE_BASE_SLOT}, {BG_TILE_BASE_SLOT + count}) — the tiles the overwrite uploads")
    lines = collections.Counter((w >> 13) & 3 for w in words)
    assert set(lines) == {g.SHOWCASE_LINE}, f"layout palette lines {dict(lines)}"
    assert not any(w & 0x8000 for w in words), "a showcase cell carries the priority bit"
    assert struct.unpack(">H", tiles[:2])[0] == count * 32 == len(tiles) - 2
    assert count <= BG_STATIC_TILE_BUDGET
    act = (REPO / "games/sonic4/data/generated/ojz/act1/bg_tiles.bin").read_bytes()
    assert tiles != act, "the showcase tiles equal the act default's: a switch would show nothing"


def test_showcase_tiles_are_opaque():
    _layout, tiles, count, _pal, _info = g.build()
    body = tiles[2:]
    clear = [t for t in range(count)
             if any((b >> 4) == 0 or (b & 15) == 0 for b in body[t * 32:(t + 1) * 32])]
    assert not clear, (
        f"{len(clear)} showcase tile(s) hold colour-0 pixels (first: tile {clear[0]}). The donor's "
        "sky is its backdrop colour and must be resolved into art, or Plane B shows Aeon's "
        "backdrop through it")


def test_showcase_palette_changes_its_line_and_nothing_else():
    _layout, _tiles, _count, pal, _info = g.build()
    act = (REPO / "games/sonic4/data/generated/ojz/act1/ojz_palette.bin").read_bytes()
    assert len(pal) == len(act) == 96
    lo, hi = (g.SHOWCASE_LINE - 1) * 32, g.SHOWCASE_LINE * 32
    assert pal[:lo] == act[:lo] and pal[hi:] == act[hi:], (
        "the showcase palette changes a CRAM line other than SHOWCASE_LINE")
    assert pal[lo:lo + 2] == act[lo:lo + 2], "entry 0 of the showcase line must keep the act's value"
    new = struct.unpack(">15H", pal[lo + 2:hi])
    assert len(set(new)) == 15, f"the showcase line holds {len(set(new))} distinct colours, not 15"
    assert pal[lo + 2:hi] != act[lo + 2:hi]


def test_no_foreground_tile_in_the_act_uses_the_showcase_line():
    """The FG recolour measurement. Decodes the SHIPPED sec*_blocks.bin (what the ROM carries)."""
    import fg_working_set as f
    import ojz_block_gen as blockgen
    model = f.Model()
    bpa = model.c["BLOCKS_PER_SECTION_AXIS"]
    wpb = model.c["BLOCK_NT_SIZE"] // 2
    lens = f.load_dict_lens()
    lines = collections.Counter()
    for sec in range(model.grid_w * model.grid_h):
        blob = (pathlib.Path(f.GEN_DIR) / f"sec{sec}_blocks.bin").read_bytes()
        for bi in range(bpa * bpa):
            d = blockgen.decode_block(blob, lens[sec], bi)
            if d is None:
                continue
            for w in struct.unpack(f">{wpb}H", d[:wpb * 2]):
                if w & model.nt_tile_mask:
                    lines[(w >> 13) & 3] += 1
    assert sum(lines.values()) > 0, "decoded no foreground word at all: the measurement is vacuous"
    assert lines[g.SHOWCASE_LINE] == 0, (
        f"{lines[g.SHOWCASE_LINE]} foreground cells are on CRAM line {g.SHOWCASE_LINE}, which the "
        f"showcase preset recolours (all FG lines: {dict(lines)})")


def test_committed_showcase_outputs_match_the_generator():
    r = subprocess.run([sys.executable, str(REPO / "tools/gen_region_bg_showcase.py"), "--check"],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_act_assets_tile_count_mirror_matches_the_blob():
    _layout, _tiles, count, _pal, _info = g.build()
    text = (REPO / "games/sonic4/data/levels/ojz/act1/act_assets.emp").read_text()
    m = re.search(r"^pub const BG_SHOWCASE_TILE_COUNT\s*=\s*(\d+)", text, re.M)
    assert m, "act_assets.emp no longer declares `pub const BG_SHOWCASE_TILE_COUNT = <int>`"
    assert int(m.group(1)) == count, (
        f"act_assets.emp says the showcase blob holds {m.group(1)} tiles; the blob holds {count}")
    m = re.search(r"^pub const BG_REGION_STATIC_TILE_BUDGET\s*=\s*(\d+)", text, re.M)
    assert m and int(m.group(1)) == BG_STATIC_TILE_BUDGET, (
        "act_assets.emp's BG_REGION_STATIC_TILE_BUDGET must equal vram.toml's static budget "
        f"({BG_STATIC_TILE_BUDGET}, tools/vram_map.py)")


def test_an_unknown_library_id_is_refused():
    try:
        g.build(entry="no-such-entry")
    except g.Refused as e:
        assert "not an id" in str(e)
    else:
        raise AssertionError("an unknown id was accepted")


def test_an_unknown_donor_is_refused():
    try:
        g.build(donor="s2-nope")
    except g.Refused as e:
        assert "not a known donor" in str(e)
    else:
        raise AssertionError("an unknown donor was accepted")


def test_the_library_source_still_lowers_with_the_act_palette():
    layout, tiles, count, pal, _info = g.build(entry=COLONNADE)
    assert len(layout) == 8192 and count == (len(tiles) - 2) // 32
    assert pal == (REPO / "games/sonic4/data/generated/ojz/act1/ojz_palette.bin").read_bytes()


def test_inject_editor_bg_rebase_still_reproduces_the_committed_act_layout():
    override = REPO / "games/sonic4/data/editor_bg_override.json"
    layout = json.loads(override.read_text())["layout"]
    if len(layout) == 2048:
        layout = layout + [0] * 2048
    committed = (REPO / "games/sonic4/data/generated/ojz/act1/zone_bg.bin").read_bytes()
    assert inject_editor_bg.rebase_layout(layout) == committed
