#!/usr/bin/env python3
"""The OJZ act's section grid: ONE source, cross-checked against the engine.

WHY THIS MODULE EXISTS (2026-09-12 gap lens sweep, F2). The act's section count was
stated four times: project.json's gridWidth x gridHeight (what tools/ojz_strip_gen.py
bakes from), the engine's `GRID_W` / `GRID_H` in the act descriptor, and two literal
`NUM_SECTIONS = 9`s, in tools/ojz_block_gen.py and tools/verify_level_bin.py. A
missing section file slipped between them: the strip baker skipped it with a warning,
the local-map table came out one entry short, the block baker re-baked the missing
section from the previous bake's strips at its literal 9, and the gate checked its
own literal 9 against files that were all still on disk. Exit 0 everywhere, and the
engine read the next table's first long as section 8's local map.

THE ONE SOURCE is project.json's `gridWidth` x `gridHeight` for zones[0].acts[0] —
the file Aurora writes and the strip baker already read. Every tool that needs the
count calls `section_grid()`, and that call also REQUIRES the engine's act descriptor
to agree (`const GRID_W` / `const GRID_H` in
games/sonic4/data/levels/ojz/act1/act_descriptor.emp). The engine indexes the baked
`OJZ_Sec_LocalMaps` table by flat id over ITS grid, so a project.json that disagreed
would bake a table the engine over- or under-reads — the same NULL-map read, reached
from the other file.

Stdlib only and donor-free: tools/verify_level_bin.py runs on every canonical build,
on machines that have no donor checkout, and imports this.
"""

import json
import os
import re

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
PROJECT_JSON = os.path.join(ROOT, "project.json")
ACT_DESCRIPTOR = os.path.join(
    ROOT, "games", "sonic4", "data", "levels", "ojz", "act1", "act_descriptor.emp")


class ActGridError(ValueError):
    """The act grid cannot be read, or its two statements disagree."""


def project_act(project_json: str = PROJECT_JSON) -> tuple[dict, dict]:
    """(zone, act) for zones[0].acts[0] of project.json — the OJZ act the bakers bake."""
    with open(project_json, "r") as f:
        proj = json.load(f)
    zone = proj["zones"][0]
    return zone, zone["acts"][0]


def descriptor_grid(descriptor: str = ACT_DESCRIPTOR) -> tuple[int, int]:
    """(GRID_W, GRID_H) as the engine's act descriptor declares them.

    Parsed, not assembled: a literal `const GRID_W = <int>` line. A descriptor
    that stops declaring them that way RAISES rather than falling back to
    project.json, because a fallback here is the one-sided agreement this module
    exists to replace.
    """
    if not os.path.isfile(descriptor):
        raise ActGridError(f"act descriptor {descriptor} missing — cannot read the "
                           f"engine's GRID_W/GRID_H to check project.json against")
    text = open(descriptor, "r").read()
    got = {}
    for name in ("GRID_W", "GRID_H"):
        m = re.search(rf"^const {name} = (\d+)\s*$", text, re.M)
        if not m:
            raise ActGridError(
                f"{descriptor} no longer declares `const {name} = <int>` — the act grid "
                f"moved; re-derive tools/act_grid.py's reader rather than guessing")
        got[name] = int(m.group(1))
    return got["GRID_W"], got["GRID_H"]


def section_grid(project_json: str = PROJECT_JSON,
                 descriptor: str = ACT_DESCRIPTOR) -> tuple[int, int]:
    """(grid_w, grid_h) from project.json, refused unless the engine agrees."""
    _zone, act = project_act(project_json)
    w, h = int(act["gridWidth"]), int(act["gridHeight"])
    if w < 1 or h < 1:
        raise ActGridError(f"project.json act grid {w}x{h} has a zero axis")
    dw, dh = descriptor_grid(descriptor)
    if (w, h) != (dw, dh):
        raise ActGridError(
            f"project.json declares the act grid {w}x{h} but the engine's act "
            f"descriptor ({descriptor}) declares GRID_W x GRID_H = {dw}x{dh}. The "
            f"engine indexes OJZ_Sec_LocalMaps by flat id over ITS grid, so baking "
            f"{w * h} sections against a {dw * dh}-section engine ships a table it "
            f"over- or under-reads. Change both, together.")
    return w, h


def section_count(project_json: str = PROJECT_JSON,
                  descriptor: str = ACT_DESCRIPTOR) -> int:
    """GRID_W * GRID_H — the number of sections every per-section artifact covers."""
    w, h = section_grid(project_json, descriptor)
    return w * h


if __name__ == "__main__":
    w, h = section_grid()
    print(f"act grid {w}x{h} = {w * h} sections (project.json == act descriptor)")
