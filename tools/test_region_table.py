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


def _row(i, x0, x1, y0, y1):
    return {"index": i, "addr": 0x1000 + 16 * i, "x0": x0, "x1": x1, "y0": y0, "y1": y1,
            "effects": 0x2000 + i, "parallax": 0}


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
