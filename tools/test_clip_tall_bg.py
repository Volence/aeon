"""WINDOWED-BG-VERTICAL-CLAMP (2026-09-27): a clip zone's whole background height, streamed.

tools/clip_rom_bake.py lowers a zone whose clips reach screen tops its one 512-line window
cannot hold (Hidden Palace, Wing Fortress) as a TALL map named by rg_bg_layout + rg_bg_span,
and scrolls it with a CHAIN of band layouts (tools/clip_bg_scroll.py derive_tall) switched on
split region rows. These rows hold that to SONIC 2, not to the engine model: over every camera
top each committed clip act can hold, the screen-top BG row the engine shows and the band kind
every visible non-transparent line takes must be Sonic 2's (`vertical_coverage`). The engine
side (the ROM against the model, and the nametable against the blob) is
tools/clip_bg_scroll_witness.py's, which boots the ROM.

The clip acts are read straight from their committed clips.json (no converted donor tree:
tall_plans reads the donor disassembly itself), so no row reads the gitignored working tree.
"""

import json
import os
import sys
from types import SimpleNamespace

import pytest

TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS)

import clip_bg_lower as CBL                 # noqa: E402
import clip_bg_scroll as CBS                # noqa: E402
import clip_rom_bake as CRB                 # noqa: E402
import s2_donor as S                        # noqa: E402
from suite_paths import SuitePathError      # noqa: E402

REPO = os.path.dirname(TOOLS)
TALL_CLIPS = ["s2_hpz_solo", "s2_wfz_solo", "s2_woven"]


def _need(donor):
    try:
        S.donor_root(donor)
    except (SystemExit, SuitePathError) as e:
        pytest.skip(f"the {donor} donor could not be resolved, so NOTHING in this row is "
                    f"checked: {e}")


def _act(clip):
    """The clip act's clips as tall_plans reads them (zone keys by first (donor, zone))."""
    with open(os.path.join(REPO, "games", "sonic4", "data", "clips", clip, "clips.json")) as fh:
        doc = json.load(fh)
    keys, clips = {}, []
    for c in doc["clips"]:
        tk = (c["donor"], c["zone"])
        keys.setdefault(tk, len(keys))
        r, d = c["src_rect"], c["dst_rect"]
        clips.append(SimpleNamespace(donor=tk[0], zone=tk[1], tree_key=tk, zone_key=keys[tk],
                                     src=(r["x"], r["y"], r["w"], r["h"]),
                                     dst=(d["x"], d["y"], d["w"], d["h"])))
    for tk in keys:
        _need(tk[0])
    return SimpleNamespace(id=clip, clips=clips)


def _cams(act, key):
    cl = [c for c in act.clips if c.zone_key == key]
    return sorted({y for c in cl
                   for y in range(c.dst[1], max(c.dst[1], c.dst[1] + c.dst[3] - 224) + 1)})


def _wild(ext, words):
    return {ext["r0"] + 8 * t + i for t in range(ext["rows"])
            if not any(words[t * 64:(t + 1) * 64]) for i in range(8)}


@pytest.mark.parametrize("clip", TALL_CLIPS)
def test_every_camera_top_shows_sonic2s_row_and_band(clip):
    """AFTER: every camera top of every tall zone is exact against Sonic 2. BEFORE (the one
    window, the booking's measurement): not, which is what makes this row say something."""
    act = _act(clip)
    tall = CRB.tall_plans(act)
    chains = CRB.tall_chains(act)
    assert tall, f"{clip} has no tall zone: nothing below is checked"
    tree = {c.zone_key: c.tree_key for c in act.clips}
    for key, ext in tall.items():
        donor, zone = tree[key]
        words = CRB.lower_zone(donor, zone, ext)[0]
        wild = _wild(ext, words)
        cams = _cams(act, key)
        ch = chains[key]

        def pick(y, ch=ch):
            return ch["specs"][sum(1 for c in ch["cuts"] if c <= y + CBS.CAM_HALF_H)]
        exact, n, first = CBS.vertical_coverage(donor, zone, ext["paste_dy"], cams, pick, wild,
                                                ext["donor_cam_x_max"])
        assert (exact, first) == (n, None), (clip, zone, exact, n, first)
        old = CBS.derive(donor, zone, ext["paste_dy"])
        b_exact, b_n, _ = CBS.vertical_coverage(donor, zone, ext["paste_dy"], cams,
                                                lambda y: old, wild, ext["donor_cam_x_max"])
        assert b_exact < b_n, f"{clip} {zone}: the one window was already exact everywhere"


@pytest.mark.parametrize("clip", TALL_CLIPS)
def test_each_switch_lies_where_both_layouts_are_exact(clip):
    """A switch row sits inside the overlap of the two layouts it joins, and the overlap is at
    least SWITCH_MARGIN wide, so a scroll trailing its camera still meets an exact layout."""
    act = _act(clip)
    for key, ch in CRB.tall_chains(act).items():
        for i, v in enumerate(ch["switch_rows"]):
            a0, a1 = ch["specs"][i]["tall"]["valid"]
            b0, b1 = ch["specs"][i + 1]["tall"]["valid"]
            assert b0 <= v <= a1, (clip, key, i, v)
            assert a1 - b0 >= CBS.SWITCH_MARGIN, (clip, key, i, (b0, a1))
        if len(ch["specs"]) > 1:
            assert all(sp["transition"] == 1 for sp in ch["specs"])
            for k in range(max(len(sp["bands"]) for sp in ch["specs"])):
                assert len({(sp["bands"][k].get("drift") or 0) if k < len(sp["bands"]) else 0
                            for sp in ch["specs"]}) == 1


def test_only_the_zones_the_window_cannot_hold_go_tall():
    """OOZ's clips reach screen tops 80..288, inside its window: it stays windowed, and so does
    every EHZ / CPZ / MTZ zone of the woven act (their transcriptions have no tall path)."""
    act = _act("s2_woven")
    tall = CRB.tall_plans(act)
    zone_of = {c.zone_key: c.zone for c in act.clips}
    assert sorted(zone_of[k] for k in tall) == ["HPZ", "WFZ"]
    assert CRB.tall_plans(_act("s2_ooz_solo")) == {}


def test_the_window_path_is_byte_identical_and_the_tall_blob_starts_with_it():
    _need("s2disasm")
    for donor, zone in (("s2disasm", "EHZ"), ("s2disasm", "OOZ"), ("s2disasm", "WFZ")):
        w0, t0, _ = CBL.lower(donor, zone)
        w1, t1, _ = CBL.lower(donor, zone, rows=CBL.PLANE_ROWS)
        assert (w0, t0) == (w1, t1)
        from inject_editor_bg import rebase_layout
        assert CBL.layout_blob(w0) == rebase_layout(list(w0))
    words, _t, _i = CBL.lower("s2disasm", "WFZ", r0=384, rows=176, x_reach=8192)
    blob = CBL.layout_blob(words)
    assert len(blob) == 176 * 128
    assert blob[:8192] == CBL.layout_blob(words[:4096])
    assert blob[8192:] == CBL.layout_blob(words[4096:])
