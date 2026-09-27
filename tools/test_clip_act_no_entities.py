"""A clip act emits NO inherited OJZ entities (the woven report's §C item 8, 2026-09-27).

RUNNER: build.sh's PRE-build tool-suite lane (`pytest tools -m "not needs_build"`), which
`tools/landing_build.sh` runs once per landing. Nothing here reads a build artifact or a
donor tree.

WHAT CHANGED. Pass 8 (`ojz_entity_gen.generate`, called by `ojz_strip_gen.generate`) read the
SHIPPED act's editor objects and rings for every bake, clip acts included, so a clip act
carried Oracle Jungle's entities at Oracle Jungle's world positions over Sonic 2 geometry.
Keeping those inherited section ids lined up is what forced two refusals on every clip grid:
at least the shipped act's nine sections, and whole rows of its width 3 (a 5 x 4 woven act
had to be measured as 6 x 4). A clip act's staged project now says `entities: none`
(`clip_rom_bake.stage_project`), and Pass 8 then emits every section's three tables EMPTY at
the clip act's own grid, reading no editor JSON.

WHAT IS PINNED:
  * `entities: none` at a 5 x 4 grid (20 sections, neither >= 9-in-rows-of-3 rule holds)
    emits 20 empty table sets, and reads no editor JSON (its dataPath does not exist);
  * THE CONTROL: the same project WITHOUT the key still takes the inherit path, and that
    path still refuses 20 sections (not whole rows of the shipped width), so nothing was
    loosened for the shipped act;
  * the SHIPPED project (no key) regenerates the committed entity_data.emp byte for byte,
    so every canonical shape's Pass 8 output is unchanged;
  * `stage_project` writes the key.
"""

import json
import os
import re
import sys
import types

import pytest

TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS)

import ojz_entity_gen as GEN               # noqa: E402

REPO = os.path.dirname(TOOLS)
COMMITTED = os.path.join(REPO, "games", "sonic4", "data", "generated", "ojz", "act1",
                         "entity_data.emp")


def _project(tmp_path, grid, entities=None):
    with open(os.path.join(REPO, "project.json")) as fh:
        proj = json.load(fh)
    act = proj["zones"][0]["acts"][0]
    act["gridWidth"], act["gridHeight"] = grid
    act["dataPath"] = "this-editor-dir-does-not-exist"
    if entities is not None:
        act[GEN.ENTITIES_KEY] = entities
    p = tmp_path / "project.json"
    p.write_text(json.dumps(proj))
    return str(p)


def _tables(text, kind):
    return re.findall(rf"pub data OJZ_Sec(\d+)_{kind}: (.*)", text)


def test_no_entities_emits_empty_tables_at_the_clip_grid(tmp_path):
    proj = _project(tmp_path, (5, 4), entities="none")
    out = tmp_path / "entity_data.emp"
    GEN.generate(out_path=str(out), sections=20, project_json=proj)
    text = out.read_text()
    for kind, empty in (("TypeTable", "[u8; 2] = [0, 0]"),
                        ("Objects", "[u16; 1] = [$FFFF]"),
                        ("Rings", "[u16; 2] = [$000, $000]")):
        rows = _tables(text, kind)
        assert [int(n) for n, _ in rows] == list(range(20)), (kind, rows)
        assert all(body == empty for _n, body in rows), (kind, rows)
    assert "ENTITIES: NONE" in text


def test_no_entities_refuses_a_count_that_is_not_its_own_grid(tmp_path):
    proj = _project(tmp_path, (5, 4), entities="none")
    with pytest.raises(SystemExit, match="20"):
        GEN.generate(out_path=str(tmp_path / "x.emp"), sections=21, project_json=proj)


def test_control_without_the_key_still_inherits_and_still_refuses(tmp_path):
    """The inherit path is the shipped act's, unchanged: 20 sections are not whole rows of
    its width, and it says so. If this passed, the key would not be what gates the change."""
    proj = _project(tmp_path, (5, 4))
    with pytest.raises(SystemExit, match="whole number of rows"):
        GEN.generate(out_path=str(tmp_path / "x.emp"), sections=20, project_json=proj)


def test_unknown_policy_is_refused(tmp_path):
    proj = _project(tmp_path, (5, 4), entities="some")
    with pytest.raises(SystemExit, match="may be one of"):
        GEN.generate(out_path=str(tmp_path / "x.emp"), sections=20, project_json=proj)


def test_shipped_project_regenerates_the_committed_file(tmp_path):
    out = tmp_path / "entity_data.emp"
    GEN.generate(out_path=str(out), project_json=GEN.PROJECT_JSON)
    with open(COMMITTED) as fh:
        assert out.read_text() == fh.read()


def test_stage_project_says_none(tmp_path):
    import clip_rom_bake as B
    clip = types.SimpleNamespace(donor="s2disasm", zone="EHZ")
    act = types.SimpleNamespace(clips=[clip], zone_table=[("s2disasm", "EHZ")],
                                sheet_table=[("s2disasm", "EHZ")], id="t",
                                grid_w=5, grid_h=4)
    path, _tree = B.stage_project(act, str(tmp_path), str(tmp_path / "donors"),
                                  gen_dir=str(tmp_path / "gen"),
                                  sheet_files=[str(tmp_path / "tileset.bin")])
    with open(path) as fh:
        assert json.load(fh)["zones"][0]["acts"][0][GEN.ENTITIES_KEY] == "none"
