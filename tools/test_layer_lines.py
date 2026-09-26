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


def test_the_ojz_lines_carry_the_retired_marks_meaning():
    """OJZ's four lines replace sixteen painted marks: XOVER_TO_B on plane A (fired moving
    right) and XOVER_TO_A on plane B (fired moving left), priority derived from the plane
    (B high, A low). Each line therefore says: right -> B high, left -> A low, and is not
    grounded-only (a mark fired airborne too)."""
    c = LL.engine_constants()
    w, h = LL.act_size()
    p = LL.plan_authored(OJZ_SRC, w, h)
    assert len(p["rows"]) == 4
    assert {r["flags"] for r in p["rows"]} == {_bits(c, "LL_FWD_B", "LL_FWD_HI")}
    # the marked column was x 1144..1151: entered rightward across 1144, leftward across 1152
    assert sorted({r["key"] for r in p["rows"]}) == [1144, 1152]
    assert sorted({(r["a"], r["b"]) for r in p["rows"]}) == [(416, 448), (544, 576)]
