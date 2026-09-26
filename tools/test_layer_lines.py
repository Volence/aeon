#!/usr/bin/env python3
"""tools/layer_lines.py: the authored layer-line source, its refusals, and the one row builder.

LINES-EVERYWHERE (2026-09-26). An act's layer lines come from one of two sources (a Sonic 2
donor's Obj03 objects, tools/s2_layer_lines.py; or an authored layer_lines.json) and go
through one row builder. These rows pin the authored half: every flag the format can say
reaches the right LL_* bit, every refusal fires with its tag, and the committed OJZ module is
what its committed source bakes to.
"""
import copy
import json
import os

import pytest

import layer_lines as LL

REPO = LL.REPO
OJZ_SRC = os.path.join(REPO, "games", "sonic4", "data", "editor", "ojz", "act1", "layer_lines.json")

LINE = {"id": "a", "orientation": "vertical", "x": 100, "y": 200, "length": 32,
        "forward": {"path": "B", "priority": "high"},
        "backward": {"path": "A", "priority": "low"}}


def _doc(*lines, **extra):
    d = {"format": LL.FORMAT, "version": LL.VERSION, "lines": list(lines)}
    d.update(extra)
    return d


def _write(tmp_path, doc):
    p = tmp_path / "layer_lines.json"
    p.write_text(json.dumps(doc))
    return str(p)


def _bits(c, *names):
    v = 0
    for n in names:
        v |= 1 << c[n]
    return v


def test_a_vertical_line_bakes_to_one_row(tmp_path):
    c = LL.engine_constants()
    p = LL.plan_authored(_write(tmp_path, _doc(LINE)), 4096, 4096)
    assert [(r["key"], r["a"], r["b"], r["flags"]) for r in p["rows"]] == \
        [(100, 200, 232, _bits(c, "LL_FWD_B", "LL_FWD_HI"))]


def test_every_flag_the_format_can_say(tmp_path):
    c = LL.engine_constants()
    ln = dict(LINE, orientation="horizontal", grounded_only=True,
              forward={"path": "keep", "priority": "low"},
              backward={"path": "keep", "priority": "high"})
    p = LL.plan_authored(_write(tmp_path, _doc(ln)), 4096, 4096)
    assert {r["flags"] for r in p["rows"]} == \
        {_bits(c, "LL_KEEP_PATH", "LL_GROUNDED", "LL_HORIZONTAL", "LL_BACK_HI")}
    ln = dict(LINE, forward={"path": "A", "priority": "low"},
              backward={"path": "B", "priority": "high"})
    p = LL.plan_authored(_write(tmp_path, _doc(ln)), 4096, 4096)
    assert p["rows"][0]["flags"] == _bits(c, "LL_BACK_B", "LL_BACK_HI")


def test_a_horizontal_line_is_cut_into_segments(tmp_path):
    c = LL.engine_constants()
    ln = dict(LINE, orientation="horizontal", x=0, y=300, length=c["LL_SEG_W"] * 2 + 1)
    p = LL.plan_authored(_write(tmp_path, _doc(ln)), 4096, 4096)
    assert [(r["key"], r["a"], r["b"]) for r in p["rows"]] == \
        [(0, 300, c["LL_SEG_W"]), (c["LL_SEG_W"], 300, 2 * c["LL_SEG_W"]),
         (2 * c["LL_SEG_W"], 300, 2 * c["LL_SEG_W"] + 1)]


def test_equal_keys_keep_file_order(tmp_path):
    a = dict(LINE, id="first", y=500)
    b = dict(LINE, id="second", y=100)
    p = LL.plan_authored(_write(tmp_path, _doc(a, b)), 4096, 4096)
    assert [r["a"] for r in p["rows"]] == [500, 100]


@pytest.mark.parametrize("mutate,tag", [
    (lambda d: d.update(version=2), "A1"),
    (lambda d: d.update(format="regions"), "A1"),
    (lambda d: d.update(colour="red"), "A1"),
    (lambda d: d["lines"][0].update(colour="red"), "A1"),
    (lambda d: d["lines"][0].pop("length"), "A2"),
    (lambda d: d["lines"][0].update(length=0), "A2"),
    (lambda d: d["lines"][0].update(x=1.5), "A2"),
    (lambda d: d["lines"][0].update(orientation="diagonal"), "A2"),
    (lambda d: d["lines"][0]["forward"].update(path="C"), "A2"),
    (lambda d: d["lines"][0]["forward"].update(priority="mid"), "A2"),
    (lambda d: d["lines"][0].update(grounded_only=1), "A2"),
    (lambda d: d["lines"][0]["forward"].update(path="keep"), "A3"),
    (lambda d: d["lines"].append(copy.deepcopy(d["lines"][0])), "A4"),
    (lambda d: d["lines"][0].update(x=5000), "L4"),
])
def test_each_refusal_fires_with_its_tag(tmp_path, mutate, tag):
    doc = _doc(copy.deepcopy(LINE))
    LL.plan_authored(_write(tmp_path, doc), 4096, 4096)           # the control: accepted
    mutate(doc)
    with pytest.raises(LL.LayerLineError, match=rf"^{tag} "):
        LL.plan_authored(_write(tmp_path, doc), 4096, 4096)


def test_the_committed_ojz_module_is_what_its_source_bakes_to():
    """The build lane's `check`, run here too: a hand edit to the generated module or an
    edited source without a re-bake is refused."""
    assert [n for _g, n in LL.emit(check=True)] == [4]


def test_the_ojz_loop_lines_are_laid_out_like_sonic_2s():
    """OJZ's loop (LOOP-EXIT, 2026-09-26). The CROWN keeps the retired marks' two lines
    (x 1144/1152: right -> B high, left -> A low), now y 384..447 and grounded-only. The FLOOR
    has no line between the arcs any more: the old floor lines at x 1144/1152 fired "right: B" on the way OUT of a
    rightward lap as well as on the way in, so the player rode the right arc again. The entry
    is a line WEST of the loop (right -> B high, left -> A low) and the exit a line EAST of it
    (A low both ways), which is Sonic 2's apex-line-plus-exit-line layout, mirrored because
    our right arc is the plane-B one. Priority follows the plane (B high, A low) on every row."""
    c = LL.engine_constants()
    w, h = LL.act_size()
    p = LL.plan_authored(OJZ_SRC, w, h)
    to_b = _bits(c, "LL_FWD_B", "LL_FWD_HI")
    crown = to_b | _bits(c, "LL_GROUNDED")          # grounded-only, like S2's apex line
    got = sorted((r["key"], r["a"], r["b"], r["flags"]) for r in p["rows"])
    assert got == [(1024, 512, 576, to_b),         # entry, west of the left arc
                   (1144, 384, 448, crown),        # crown, tall enough for a fast rider
                   (1152, 384, 448, crown),        # crown
                   (1280, 384, 576, 0)]            # exit, east of the right arc: A low
    # nothing switches on the floor band between the arcs (the old double-lap cause)
    assert not [r for r in p["rows"] if 1024 < r["key"] < 1280 and r["b"] > 448]
