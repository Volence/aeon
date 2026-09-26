"""tools/region_table.py — the one out-of-assembler reader of the act's Region table.

What is held here, and why each is a property rather than a pin:

  * The Region layout parses cleanly against its OWN `// $HH` comments and its own
    `(size: N)`. No offset is typed in this file: the test is that the source's two
    statements of the layout agree, which is what every ROM reader depends on.
  * A stale offset comment is REFUSED (the parser is poisoned with a one-field slide), so the
    agreement above is a check that can fail and not a parse that always succeeds.
  * The two Act fields are the LAST two fields (appended, so no older offset moved).
  * `region_at` restates Region_Resolve's edge semantics: inclusive on both ends, unsigned,
    first match, None outside every row.
"""
import re

import pytest

import region_table as rt


def test_region_layout_agrees_with_its_own_offset_comments_and_size():
    off, size = rt.region_layout()
    assert list(off) == list(rt.REGION_FIELDS), (
        f"struct Region's field order is {list(off)}; the readers expect {list(rt.REGION_FIELDS)}")
    declared = re.search(r"struct\s+Region\s*\(\s*size\s*:\s*(\d+)\s*\)",
                         (rt.AEON / rt.STRUCTS).read_text())
    assert declared, "struct Region lost its (size: N) declaration"
    assert size == int(declared.group(1))


def test_a_stale_offset_comment_is_refused():
    text = (rt.AEON / rt.STRUCTS).read_text()
    block = re.search(r"pub struct Region.*?^\}", text, re.M | re.S).group(0)
    # Slide the rg_effects comment by two bytes: the types still say $08.
    poisoned = block.replace("// $08", "// $0A", 1)
    assert poisoned != block, "the poison did not apply — the rg_effects comment moved"
    with pytest.raises(rt.LayoutError, match="rg_effects"):
        rt.region_layout(text=text.replace(block, poisoned))


def test_a_wrong_declared_size_is_refused():
    text = (rt.AEON / rt.STRUCTS).read_text()
    poisoned = re.sub(r"(struct\s+Region\s*\(\s*size\s*:\s*)(\d+)",
                      lambda m: m.group(1) + str(int(m.group(2)) - 1), text, count=1)
    assert poisoned != text
    with pytest.raises(rt.LayoutError, match="size"):
        rt.region_layout(text=poisoned)


def test_the_act_region_fields_are_appended_last():
    off, size = rt.struct_layout("Act")
    names = list(off)
    assert names[-2:] == list(rt.ACT_REGION_FIELDS), (
        f"Act's last two fields are {names[-2:]}; the region fields were appended so that no "
        "older Act offset moved")
    ao = rt.act_region_offsets()
    assert ao["act_region_count"] == ao["act_regions"] + 4


def test_the_background_fields_are_appended_last_and_the_rectangle_is_still_two_move_l():
    """Regions part 2 step 1's whole claim: the two background fields were APPENDED, so no
    offset an existing reader depends on moved.

    Both halves are derived from the mechanism rather than copied off the declaration:

      * `Parallax_CheckBoundary` fills its RAM cache with TWO `move.l` because the record is
        span-major — so the four rectangle words must be the first four fields, contiguous,
        and the two longword reads must start long-ALIGNED. That is what makes "the fields
        were appended" load-bearing rather than tidy.
      * The background pair must be the LAST two fields. Anywhere else and every offset after
        it slides, which is the failure this test exists to name.
    """
    off, size = rt.region_layout()
    rect = ("rg_x0", "rg_x1", "rg_y0", "rg_y1")
    assert list(off)[:4] == list(rect), (
        f"struct Region no longer opens with the rectangle {rect}; it opens with "
        f"{list(off)[:4]}. The crossing's cache fill is two move.l over exactly those words")
    for n, prev in zip(rect[1:], rect):
        assert off[n] == off[prev] + 2, (
            f"`{n}` is at ${off[n]:02X}, not two bytes after `{prev}` (${off[prev]:02X}) — "
            "the rectangle is no longer four contiguous words")
    assert off["rg_x0"] % 4 == 0 and off["rg_y0"] % 4 == 0, (
        f"a move.l cache fill starts at ${off['rg_x0']:02X} / ${off['rg_y0']:02X}; an odd "
        "base would address-error on 68000")
    assert list(off)[-5:] == ["rg_bg_layout", "rg_bg_span", "rg_bg_tiles", "rg_song",
                              "rg_pad_1b"], (
        f"struct Region's last five fields are {list(off)[-5:]}; the background pair was "
        "APPENDED (regions part 2 step 1), the tile blob after it (region bg switch, "
        "2026-09-16) and the song byte + pad after that (region music, 2026-09-25) so that "
        "no older offset moved. A field inserted before them slides rg_effects and "
        "rg_parallax under every reader")
    assert off["rg_pad_1b"] + 1 == size, (
        f"rg_pad_1b at ${off['rg_pad_1b']:02X} + 1 is not the {size}-byte record size — "
        "something follows the field this test believes is last")
    assert size % 2 == 0, (
        f"sizeof(Region) is {size}, ODD: the table stride would put every second row's "
        "rectangle on an odd address and the crossing's move.l cache fill would address-error")


def test_region_record_carries_bg_tiles_at_offset_22():
    """Region bg switch, task 1: a region names its own background TILE blob.

    `rg_bg_tiles` is a pointer (the blob: 2-byte length + raw tiles; 0 = Act.act_bg_tiles),
    appended at $16 directly after `rg_bg_span` ($14, u16), which makes the record 26 bytes.
    The offsets come from the parser (the declaration checked against its own `// $HH`
    comments); this test adds that the field EXISTS, is a pointer defaulting to 0, and sits
    where appending puts it.
    """
    off, size = rt.region_layout()
    assert "rg_bg_tiles" in off, f"struct Region declares no rg_bg_tiles; fields: {list(off)}"
    assert off["rg_bg_tiles"] == off["rg_bg_span"] + 2 == 0x16, (
        f"rg_bg_tiles is at ${off.get('rg_bg_tiles', -1):02X}; appended after rg_bg_span "
        f"(${off['rg_bg_span']:02X}, u16) it must be $16")
    text = (rt.AEON / rt.STRUCTS).read_text()
    assert re.search(r"^\s*rg_bg_tiles\s*:\s*\*u8\s*=\s*0\s*,", text, re.M), (
        "rg_bg_tiles must be `*u8 = 0`: a pointer whose 0 means the act default, the same "
        "sentinel convention as rg_bg_layout")
    assert size == 28, (f"sizeof(Region) is {size}; with rg_bg_tiles appended it was 26, and "
                        "rg_song + rg_pad_1b (region music, 2026-09-25) make it 28")


def test_region_record_carries_the_song_byte_at_offset_26():
    """Region music (S2CLIP-REGION-MUSIC step 5): a region names its song by SongId.

    `rg_song` is a u8 defaulting to 0 ("no song named: leave the music alone"), appended at
    $1A after `rg_bg_tiles`, and `rg_pad_1b` keeps the record even. The design's second byte
    (`rg_music`, cut vs fade-in) was NOT added: the owner ruled a hard cut, so it would have
    no reader. This pins what the engine reads (`move.b Region.rg_song(a0)`) and what
    region_table.read_regions returns as `song`.
    """
    off, size = rt.region_layout()
    assert off["rg_song"] == off["rg_bg_tiles"] + 4 == 0x1A, (
        f"rg_song is at ${off.get('rg_song', -1):02X}; appended after rg_bg_tiles "
        f"(${off['rg_bg_tiles']:02X}, a pointer) it must be $1A")
    assert off["rg_pad_1b"] == 0x1B
    text = (rt.AEON / rt.STRUCTS).read_text()
    assert re.search(r"^\s*rg_song\s*:\s*u8\s*=\s*0\s*,", text, re.M), (
        "rg_song must be `u8 = 0`: 0 is the 'leave the music alone' sentinel every shipped "
        "row relies on")
    assert "rg_music" not in off, "rg_music has no reader; it must not exist"


def _row(i, x0, x1, y0, y1):
    # The stride is the record's own, parsed, not a literal: this fixture states the layout
    # and a hand-typed size here would go stale the next time a field is appended.
    stride = rt.region_layout()[1]
    return {"index": i, "addr": 0x1000 + stride * i, "x0": x0, "x1": x1, "y0": y0, "y1": y1,
            "effects": 0x2000 + i, "parallax": 0, "bg_layout": 0, "bg_span": 0,
            "bg_tiles": 0}


def test_region_at_restates_region_resolve():
    rows = [_row(0, 0, 99, 0, 99), _row(1, 100, 199, 0, 99)]
    assert rt.region_at(rows, 0, 0)["index"] == 0          # inclusive low corner
    assert rt.region_at(rows, 99, 99)["index"] == 0        # inclusive high corner
    assert rt.region_at(rows, 100, 0)["index"] == 1        # the shared edge belongs to ONE row
    assert rt.region_at(rows, 200, 0) is None               # past every row: a0 = 0
    assert rt.region_at(rows, 0, 100) is None
    assert rt.region_at(rows, -1, 0) is None                # unsigned: -1 is $FFFF, past all


def test_region_at_is_first_match_in_table_order():
    rows = [_row(0, 0, 99, 0, 99), _row(1, 0, 99, 0, 99)]
    assert rt.region_at(rows, 50, 50)["index"] == 0
