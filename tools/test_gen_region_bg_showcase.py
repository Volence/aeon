"""tools/gen_region_bg_showcase.py — the DEBUG region background the region bg switch is
gated against (plan docs/superpowers/plans/2026-09-16-region-bg-switch.md, task 2).

What is held here:
  * the emitted layout is the Plane B blob shape, rebased, and references ONLY the entry's own
    tiles (so every cell is a tile the overwrite actually uploads);
  * the tile blob fits the static budget and is NOT the act default's (the instrument can see
    a switch at all);
  * the committed outputs are what the generator emits (the drift check);
  * the emp mirror of the tile count equals the blob's (act_assets.emp types the embed by it);
  * the rebase rule factored out of inject_editor_bg.main() still reproduces the committed act
    default blob, so the refactor changed no output.
"""
import json
import pathlib
import re
import struct
import subprocess
import sys

import gen_region_bg_showcase as g
import inject_editor_bg
from vram_map import BG_TILE_BASE_SLOT, BG_STATIC_TILE_BUDGET

REPO = pathlib.Path(__file__).resolve().parent.parent


def test_showcase_layout_is_row_major_rebased_and_references_only_its_own_tiles():
    layout, tiles, count = g.build()
    assert len(layout) == 64 * 64 * 2
    words = struct.unpack(">4096H", layout)
    used = {w & 0x7FF for w in words if w}
    assert used, "the showcase layout references no tile at all"
    assert min(used) >= BG_TILE_BASE_SLOT and max(used) < BG_TILE_BASE_SLOT + count, (
        f"layout tile indices span {min(used)}..{max(used)}; they must lie in "
        f"[{BG_TILE_BASE_SLOT}, {BG_TILE_BASE_SLOT + count}) — the tiles the overwrite uploads")
    assert all(w == 0 for w in words[64 * 32:]), "rows 32..63 must be the injector's zero padding"
    assert struct.unpack(">H", tiles[:2])[0] == count * 32 == len(tiles) - 2
    assert count <= BG_STATIC_TILE_BUDGET
    act = (REPO / "games/sonic4/data/generated/ojz/act1/bg_tiles.bin").read_bytes()
    assert tiles != act, "the showcase tiles equal the act default's: a switch would show nothing"


def test_committed_showcase_outputs_match_the_generator():
    r = subprocess.run([sys.executable, str(REPO / "tools/gen_region_bg_showcase.py"), "--check"],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_act_assets_tile_count_mirror_matches_the_blob():
    _layout, _tiles, count = g.build()
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
        g.build("no-such-entry")
    except g.Refused as e:
        assert "not an id" in str(e)
    else:
        raise AssertionError("an unknown id was accepted")


def test_inject_editor_bg_rebase_still_reproduces_the_committed_act_layout():
    override = REPO / "games/sonic4/data/editor_bg_override.json"
    layout = json.loads(override.read_text())["layout"]
    if len(layout) == 2048:
        layout = layout + [0] * 2048
    committed = (REPO / "games/sonic4/data/generated/ojz/act1/zone_bg.bin").read_bytes()
    assert inject_editor_bg.rebase_layout(layout) == committed
