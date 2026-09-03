"""The canopy record reader's arithmetic, and the geometry it reads it with.

This does NOT run the instrument -- that needs a DEBUG machine and a sighting, which is
the whole reason the instrument exists. What it gates is the half that CAN be wrong
silently: the decoder that turns a captured record into the three facts a reader will act
on, and the constant parse those facts are measured against.

Every expectation below is DERIVED -- from the predicate definitions in
`engine/level/section.emp`, or from `engine/system/constants.emp` re-evaluated here from
its own inputs -- never copied off a nearby comment. That matters more than usual here:
`SCREEN_LAST_ROW_MAX`'s source comment says 27 and the expression evaluates to 28, and a
test that copied the comment would have pinned the wrong rectangle.

Runner: `build.sh`'s tool-suite lane (`python3 -m pytest "${TOOLS}" -q`), build-fatal.

RED-FIRST, MEASURED 2026-09-02 against the committed baseline. Ten mutations, each
applied TO DISK, each run alone, each restored with `git checkout --`; both controls (the
unapplied mutation and the restored baseline) green at 14 passed.

    M1  FACT 1's disagreement filter inverted                        1 failed
    M2  FACT 2's over-claim threshold raised past reach              1 failed
    M3  the impossible-offset warning silenced                       1 failed
    M4  FACT 3's row-ownership filter inverted                       1 failed
    M5  the empty-record arm made unreachable                        1 failed
    M6  C4's shortfall arithmetic sign-flipped                       1 failed
    M7  geometry()'s tokeniser loses `>>`                            1 failed
    M8  Canopy_Probe walks one column short (engine source)          1 failed
    M9  a canopy call site put outside its DEBUG gate (engine)       1 failed
    M10 the halt-arm report inverted                                 2 failed

⚠ M10 FIRST CAME BACK GREEN, AND IT WAS A FALSE GREEN — worth recording because the
mechanism is not the one the pitfall note describes. The sweep cleared `__pycache__` under
the repo and set `PYTHONPYCACHEPREFIX` to a scratch directory, then REUSED that directory
across all ten runs, so the repo sweep never touched the cache that was actually being
read. Setting the prefix is not the protection; clearing it is. With a per-mutation prefix
directory M10 fails both of its parametrised cases. A stale cache can only manufacture a
false GREEN, so the nine reds above were never in doubt — but a tenth mutation that
"passed" would have been read as a vacuous test and the test rewritten for no reason.
"""
import pathlib
import re
import sys

import pytest

TOOLS = pathlib.Path(__file__).resolve().parent
AEON = TOOLS.parent
sys.path.insert(0, str(TOOLS))

import canopy_record as cr  # noqa: E402

CONSTS = AEON / "engine" / "system" / "constants.emp"
SECTION = AEON / "engine" / "level" / "section.emp"
PLANE = AEON / "engine" / "level" / "plane_buffer.emp"


def _const(name: str) -> str:
    m = re.search(rf"^\s*pub\s+const\s+{re.escape(name)}\s*=\s*([^/\n]+)",
                  CONSTS.read_text(), re.M)
    assert m, f"pub const {name} is gone from {CONSTS}"
    return m.group(1).strip()


# ---- the geometry parse ------------------------------------------------------

def test_geometry_matches_an_independent_evaluation():
    """cr.geometry() must agree with the constants re-derived from their own inputs.

    The two derivations are independent: cr.geometry() tokenises and folds the whole
    expression chain, this one substitutes the leaf constants by hand. If the tool ever
    starts folding `>>` or `-` wrongly, only one of the two moves.
    """
    g = cr.geometry()
    screen_w = int(_const("SCREEN_WIDTH"))
    screen_h = int(_const("SCREEN_HEIGHT"))
    assert g["SCREEN_LAST_COL_MAX"] == (7 + screen_w - 1) >> 3
    assert g["SCREEN_LAST_ROW_MAX"] == (7 + screen_h - 1) >> 3
    assert g["PLANE_H_CELLS"] == int(_const("PLANE_H_CELLS"))
    assert g["PLANE_V_CELLS"] == int(_const("PLANE_V_CELLS"))
    assert g["CANOPY_PERSIST_FRAMES"] == int(_const("CANOPY_PERSIST_FRAMES"))


def test_the_sweep_walks_the_visible_rectangle_the_reader_assumes():
    """The engine's loop counts and the reader's rectangle are one fact written twice.

    `Canopy_Probe` spells `moveq #SCREEN_LAST_COL_MAX, d6` / `moveq #SCREEN_LAST_ROW_MAX,
    d6`, so the swept rectangle IS the reader's `cam..cam+LAST`. If someone rewrites the
    sweep to walk a different span, the reader's FACT 1 and FACT 3 start counting a
    rectangle the machine never looked at -- silently, because both halves still run.
    """
    src = SECTION.read_text()
    assert "moveq   #SCREEN_LAST_COL_MAX, d6" in src, \
        "Canopy_Probe's column pass no longer walks SCREEN_LAST_COL_MAX+1 columns"
    assert "moveq   #SCREEN_LAST_ROW_MAX, d6" in src, \
        "Canopy_Probe's row pass no longer walks SCREEN_LAST_ROW_MAX+1 rows"


def test_both_fire_sites_are_debug_gated():
    """Zero bytes in release is the parcel's hard constraint, and it is checkable here
    without a build: every canopy call site sits inside an `if DEBUG == 1` block."""
    for path in (SECTION, PLANE):
        txt = path.read_text()
        for m in re.finditer(r"jbsr\s+(Canopy_\w+)", txt):
            before = txt[:m.start()]
            opens = before.count("if DEBUG == 1 {")
            assert opens > 0, f"{path.name}: `{m.group(1)}` call is not under any DEBUG gate"


# ---- the decoder ------------------------------------------------------------

G = dict(plane_h=64, plane_v=64, last_col=40, last_row=28, persist_frames=8)


def _rec(**over):
    """A well-formed, NEVER-FIRED record. Every test overrides only what it is about."""
    h, v = G["plane_h"], G["plane_v"]
    cam_col, cam_row = 100, 20
    base = {n: 0 for n in cr.SCALARS}
    base.update({n: 0 for n in cr.LONGS})
    base["Canopy_Rec_CamX"] = (cam_col * 8) << 16
    base["Canopy_Rec_CamY"] = (cam_row * 8) << 16
    base["Canopy_Hits"] = [0, 0, 0, 0]
    base["Canopy_First_Fr"] = [0, 0, 0, 0]
    base["Canopy_Rec_ResumeCol"] = cr.NEVER
    base["Canopy_Rec_ResumeRow"] = cr.NEVER
    # a healthy shadow: plane column P holds the one world column congruent to P that is
    # inside [camCol, camCol+63]; no plane row is row-owned.
    base["Canopy_Snap_ColW"] = [cam_col + ((p - cam_col) % h) for p in range(h)]
    base["Canopy_Snap_ColTop"] = [cam_row - 16] * h
    base["Canopy_Snap_ColFrame"] = [500] * h
    base["Canopy_Snap_RowR"] = [cr.NEVER] * v
    base["Canopy_Snap_RowFrame"] = [0] * v
    for n in cr.LIVE:
        base[n] = base["Canopy_Snap_" + n.split("Canopy_")[1]]
    base["Canopy_Rec_SecR"] = cam_col + G["last_col"]
    base.update(over)
    return base


def _run(rec):
    return "\n".join(cr.decode(rec, G["plane_h"], G["plane_v"],
                               G["last_col"], G["last_row"], G["persist_frames"]))


def test_empty_record_refuses_to_read_as_a_clean_bill():
    out = _run(_rec())
    assert "NOTHING IS LATCHED" in out
    assert "It is NOT evidence that the canopy gap is fixed" in out


def test_c1_reports_the_offset_in_whole_wrap_twins():
    """A column write puts world column W at plane column W & 63, so a C1 disagreement is
    always a whole multiple of PLANE_H_CELLS. One twin back is 64 cells = 512 px."""
    h = G["plane_h"]
    cam_col = 100
    p = (cam_col + 5) % h
    colw = _rec()["Canopy_Snap_ColW"][:]
    colw[p] -= h                                   # the wrap twin, one ring behind
    out = _run(_rec(Canopy_Rec_Code=1, Canopy_Rec_Idx=p,
                    Canopy_Rec_Want=cam_col + 5, Canopy_Rec_Got=cam_col + 5 - h,
                    Canopy_Hits=[3, 0, 0, 0], Canopy_Snap_ColW=colw))
    assert f"difference +{h} = +1 wrap twins" in out
    assert f"({h * 8} px)" in out
    assert "NOT a whole multiple" not in out


def test_c1_flags_an_offset_no_column_write_could_have_produced():
    h = G["plane_h"]
    out = _run(_rec(Canopy_Rec_Code=1, Canopy_Rec_Idx=5,
                    Canopy_Rec_Want=105, Canopy_Rec_Got=105 - h + 1,
                    Canopy_Hits=[1, 0, 0, 0]))
    assert "NOT a whole multiple of the ring width" in out


def test_fact_1_finds_the_run_of_disagreeing_columns():
    h, cam_col = G["plane_h"], 100
    colw = _rec()["Canopy_Snap_ColW"][:]
    bad = [cam_col + 12, cam_col + 13, cam_col + 14]
    for w in bad:
        colw[w % h] -= h
    out = _run(_rec(Canopy_Rec_Code=1, Canopy_Rec_Idx=bad[0] % h,
                    Canopy_Rec_Want=bad[0], Canopy_Rec_Got=bad[0] - h,
                    Canopy_Hits=[9, 0, 0, 0], Canopy_Snap_ColW=colw))
    assert f"disagrees: {len(bad)} of {G['last_col'] + 1}" in out
    assert f"world-column runs: {bad[0]}..{bad[-1]}" in out


def test_fact_2_sizes_a_tracker_over_claim_against_what_writers_reached():
    """The (b) candidate's shape: Section_Right_Col_Written naming columns beyond the
    largest world column any column writer ever stamped."""
    h, cam_col = G["plane_h"], 100
    colw = _rec()["Canopy_Snap_ColW"][:]
    reached = max(colw)
    over = 5
    out = _run(_rec(Canopy_Rec_Code=1, Canopy_Rec_Idx=0, Canopy_Rec_Want=0,
                    Canopy_Rec_Got=cr.NEVER, Canopy_Hits=[8, 0, 0, 0],
                    Canopy_Rec_SecR=reached + over, Canopy_Snap_ColW=colw))
    assert f"OVER-CLAIMS BY {over} column(s)" in out


def test_fact_2_says_within_it_when_the_tracker_is_honest():
    colw = _rec()["Canopy_Snap_ColW"]
    out = _run(_rec(Canopy_Rec_Code=1, Canopy_Rec_Idx=0, Canopy_Rec_Want=0,
                    Canopy_Rec_Got=cr.NEVER, Canopy_Hits=[8, 0, 0, 0],
                    Canopy_Rec_SecR=max(colw)))
    assert "within it" in out
    assert "OVER-CLAIMS" not in out


def test_c4_says_which_side_the_anchor_missed_on():
    """A row write's anchor R must satisfy camCol+SCREEN_LAST_COL_MAX <= R <= camCol+63.
    Short of the left bound, the screen's leading columns get the twin 64 back."""
    cam_col, last = 100, G["last_col"]
    short_by = 3
    out = _run(_rec(Canopy_Rec_Code=4, Canopy_Rec_Idx=7, Canopy_Rec_Want=27,
                    Canopy_Rec_Got=cam_col + last - short_by, Canopy_Hits=[0, 0, 0, 1]))
    assert f"SHORT of the screen right edge by {short_by}" in out


def test_fact_3_counts_only_the_rows_a_row_write_owns():
    v, cam_row = G["plane_v"], 20
    rowr = [cr.NEVER] * v
    owned = [cam_row + 2, cam_row + 3]
    for q in owned:
        rowr[q % v] = 163
    out = _run(_rec(Canopy_Rec_Code=1, Canopy_Rec_Idx=0, Canopy_Rec_Want=0,
                    Canopy_Rec_Got=cr.NEVER, Canopy_Hits=[8, 0, 0, 0],
                    Canopy_Snap_RowR=rowr))
    assert f"rows a row write owns: {len(owned)} of {G['last_row'] + 1}" in out
    assert "distinct anchors in play: [163]" in out


def test_pending_episode_is_reported_with_its_age():
    out = _run(_rec(Canopy_Pend_Code=1, Canopy_Pend_Idx=33, Canopy_Pend_Age=4))
    assert f"plane column 33, age 4/{G['persist_frames']} sweeps" in out


@pytest.mark.parametrize("halt,expect", [(0, "off (latch silently)"), (1, "ARMED")])
def test_halt_arm_is_reported(halt, expect):
    assert expect in _run(_rec(Canopy_Halt=halt))
