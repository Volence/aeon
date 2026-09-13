"""tools/band_geometry.py — the one per-game reader of the band-record tail geometry.

RUNNER: build.sh's PRE-build tool-suite pytest lane (every shape).

WHAT IS ASSERTED.
  * Against the REAL tree, for both games: the reader's per-game counts agree with the
    game's own `Game.SCANLINE_CAPS`, read through a DIFFERENT parser (tools/scene_spans.py's
    caps_from_manifest over games/<game>/config/game.emp) and a different source of the bit
    values (scene_spans.capability_bits over engine/level/scene_dsl.emp). That is the tool-side
    view of the build's own define == contract guard, so the expectation is derived from the
    contract and never from the define this reader consumes.
  * Against a COPY of the four files the reader consumes, each refusal: no [defines] row, the
    retired engine-wide literal spelling, a ram.emp mask that disagrees with parallax.emp's, a
    ram.emp size that is not the tail struct's. The unmodified copy is the CONTROL: it must
    read exactly what the real tree reads, or the fixture itself is broken and a refusal would
    prove nothing.
"""

import os
import re
import shutil
import sys

import pytest

TOOLS = os.path.dirname(os.path.abspath(__file__))
AEON = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)

import band_geometry as bg  # noqa: E402
import scene_spans  # noqa: E402

GAMES = ("sonic4", "demo")
FILES = ("engine/level/parallax.emp", "engine/ram.emp", "engine/level/scene_dsl.emp",
         "games/sonic4/map.toml", "games/demo/map.toml")


def contract_caps(game):
    p = os.path.join(AEON, "games", game, "config", "game.emp")
    with open(p, encoding="utf-8") as f:
        return scene_spans.caps_from_manifest(f.read(), p)


@pytest.mark.parametrize("game", GAMES)
def test_counts_follow_the_contract_not_the_define(game):
    caps = contract_caps(game)
    bits = scene_spans.capability_bits()
    got = bg.tail_counts(game, AEON)
    for count, _nbytes, _struct, cap in bg.TAILS:
        assert got[count] == (1 if caps & bits[cap] else 0), (game, count, got, caps)


@pytest.mark.parametrize("game", GAMES)
def test_bytes_are_count_times_the_declared_tail_size(game):
    g = bg.geometry(game, AEON)
    for count, nbytes, struct, _cap in bg.TAILS:
        assert g["bytes"][nbytes] == g["counts"][count] * g["sizes"][struct], (game, nbytes)


def test_the_two_games_disagree_about_at_least_one_tail():
    """The parcel's whole point. With the engine-wide literals the two games could not
    disagree about a bit; if they ever agree about all four again, the per-game rows would
    be carrying nothing, so this row turns red and asks why."""
    assert bg.tail_counts("sonic4", AEON) != bg.tail_counts("demo", AEON)


@pytest.fixture
def tree(tmp_path):
    for rel in FILES:
        dst = tmp_path / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(os.path.join(AEON, rel), dst)
    return tmp_path


def _edit(tree, rel, old, new):
    p = tree / rel
    text = p.read_text(encoding="utf-8")
    assert old in text, f"fixture drift: {old!r} is not in {rel}"
    p.write_text(text.replace(old, new, 1), encoding="utf-8")


@pytest.mark.parametrize("game", GAMES)
def test_control_the_copied_tree_reads_like_the_real_one(tree, game):
    assert bg.geometry(game, str(tree)) == bg.geometry(game, AEON)


def test_refuses_a_map_with_no_defines_row(tree):
    p = tree / "games/demo/map.toml"
    p.write_text(re.sub(r"(?ms)^\[defines\].*", "", p.read_text(encoding="utf-8")),
                 encoding="utf-8")
    with pytest.raises(bg.Unreadable, match="GAME_SCANLINE_CAPS"):
        bg.geometry("demo", str(tree))


def test_refuses_the_retired_engine_wide_literal(tree):
    _edit(tree, "engine/level/parallax.emp",
          "pub const BAND_REMAP_N = if (GAME_SCANLINE_CAPS & $0800) != 0 { 1 } else { 0 }",
          "pub const BAND_REMAP_N = 1")
    with pytest.raises(bg.Unreadable, match="not the per-game fold"):
        bg.geometry("demo", str(tree))


def test_refuses_a_ram_mask_out_of_step_with_parallax(tree):
    _edit(tree, "engine/ram.emp",
          "const BAND_DRIFT_BYTES      = if (GAME_SCANLINE_CAPS & $0080)",
          "const BAND_DRIFT_BYTES      = if (GAME_SCANLINE_CAPS & $0040)")
    with pytest.raises(bg.Unreadable, match="masks disagree"):
        bg.geometry("sonic4", str(tree))


def test_refuses_a_ram_size_that_is_not_the_tail_struct(tree):
    _edit(tree, "engine/ram.emp",
          "if (GAME_SCANLINE_CAPS & $0800) != 0 { 8 } else { 0 }",
          "if (GAME_SCANLINE_CAPS & $0800) != 0 { 10 } else { 0 }")
    with pytest.raises(bg.Unreadable, match="band_remap is"):
        bg.geometry("sonic4", str(tree))
