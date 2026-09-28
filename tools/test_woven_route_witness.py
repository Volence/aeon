#!/usr/bin/env python3
"""tools/woven_route_witness.py: P2's no-music zone is a connector's RECTANGLE.

WOVEN-ROUTE-WITNESS-P2-XSPAN (2026-09-28). P2 used to take a corridor's no-music zone as its
x span alone, so on s2_woven the correct song-4 request made in Metropolis west at camera
centre (4583, 2859) was flagged as inside hpz_to_ooz, a tunnel about 1,800 px lower. These
rows feed connectors_holding() the act's real geometry (games/sonic4/data/clips/s2_woven,
dst_rect values copied as literals so no donor tree is needed) and the two camera centres the
witness recorded: the Metropolis request (outside every connector) and the one a ROM mutant
made inside hpz_to_ooz (inside it). No emulator boots and no build artifact is read.
"""

import woven_route_witness as W


class _K:
    def __init__(self, cid, dst, axis="x"):
        self.id, self.dst, self.axis = cid, dst, axis


EHZ_TO_MTZ = _K("ehz_to_mtz", (2560, 2240, 608, 512))
HPZ_TO_OOZ = _K("hpz_to_ooz", (4544, 4624, 560, 512))
MTZ_TO_CPZ = _K("mtz_to_cpz", (4688, 2624, 416, 512))
WFZ_TO_MTZ = _K("wfz_to_mtz", (3968, 1408, 192, 832), axis="y")
LEGS = [(k, None, None) for k in (EHZ_TO_MTZ, HPZ_TO_OOZ, MTZ_TO_CPZ, WFZ_TO_MTZ)]


def _ids(c, cy):
    return [k.id for k in W.connectors_holding(LEGS, c, cy)]


def test_a_request_above_a_stacked_corridor_is_not_inside_it():
    # x 4583 is inside hpz_to_ooz's x span (4544..5103) but y 2859 is 1,765 px above its
    # top (4624): the MEASURED Metropolis-west request the x-only rule flagged
    assert HPZ_TO_OOZ.dst[0] <= 4583 < HPZ_TO_OOZ.dst[0] + HPZ_TO_OOZ.dst[2]
    assert _ids(4583, 2859) == []


def test_a_request_inside_the_corridor_rectangle_is_still_caught():
    # the red-first mutant's request (hpz_to_ooz's far half naming OOZ): centre (4850, 4863)
    assert _ids(4850, 4863) == ["hpz_to_ooz"]
    # and a 1-D corridor on the same act, on its floor line
    assert _ids(4700, 2859) == ["mtz_to_cpz"]


def test_the_rectangle_is_half_open_on_both_axes():
    x, y, w, h = HPZ_TO_OOZ.dst
    assert _ids(x, y) == ["hpz_to_ooz"]
    assert _ids(x + w - 1, y + h - 1) == ["hpz_to_ooz"]
    assert _ids(x + w, y) == [] and _ids(x, y + h) == [] and _ids(x, y - 1) == []


def test_a_shaft_is_its_rectangle_as_before():
    assert _ids(4000, 2000) == ["wfz_to_mtz"]
    assert _ids(4000, 2240) == []
