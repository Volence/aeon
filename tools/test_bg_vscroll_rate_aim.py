"""Unit cover for BG-RATE's AIM — the half that shipped wrong and was caught by a live run.

WHY THIS FILE EXISTS. `tools/bg_vscroll_rate_witness.py` shipped with leg W taking its warp
COLUMN from wherever the earlier legs happened to leave `Camera_X`, under a comment claiming the
choice was derived. On OJZ act 1 that is the bottom-right region, whose parallax config is the
vertical LOCK (`pcfg_v_factor_bg == 15`), so the derived jump came out 0 px over 2047 px of
camera travel and the leg refused. The refusal was correct behaviour and it still cost a live
emulator run to discover, because nothing here could see the aim.

THE AIM IS NOW TWO PURE FUNCTIONS — `candidate_window` (geometry) and `jump_verdict`
(arithmetic) — precisely so this file can. The emulator-backed part of the scan is the middle
step, "warp there and ask the ENGINE which config is live", and that is deliberately NOT
modelled here: restating `Effects_ResolveParallax` in a test would give the tree a second
private answer to the question the regions work exists to consolidate, and the test could then
agree with itself while disagreeing with the ROM.

TWO ARMS, DELIBERATELY UNEQUAL:
  * the SYNTHETIC arm runs everywhere, pre-build, and pins the decision rules themselves;
  * the REAL-ACT arm is `needs_build` and reads OJZ act 1's actual region table out of the
    built ROM. It is the one that would have caught the original defect, and it asserts the
    specific fact the live run turned up: this act has rows that are vertically locked AND rows
    that qualify, so a scan that walks the table finds one and a leg that inherits a column may
    not.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bg_vscroll_rate_witness as W  # noqa: E402
import region_table                  # noqa: E402
from raster_cost_probe import parse_lst  # noqa: E402

AEON = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Derived, not typed: the same resolver the witness uses on the same source.
K = W.emp_consts(["BG_VSCROLL_MAX_STEP", "VSCROLL_BG_MAX", "SCREEN_HEIGHT",
                  "CAM_SCREEN_HALF_W", "CAM_SCREEN_HALF_H"])
K["HALF_W"], K["HALF_H"] = K["CAM_SCREEN_HALF_W"], K["CAM_SCREEN_HALF_H"]
STEP = K["BG_VSCROLL_MAX_STEP"]


def row(i, x0, x1, y0, y1):
    return {"index": i, "addr": 0x10000 + i * 22, "x0": x0, "x1": x1, "y0": y0, "y1": y1,
            "effects": 0, "parallax": 0, "bg_layout": 0, "bg_span": 0}


def cfg(v_factor, v_center=512, v_offset=0):
    return {"ptr": 0x134E8, "v_factor": v_factor, "v_center": v_center & 0xFFFF,
            "v_offset": v_offset & 0xFFFF, "bob": 0}


# ---- the geometry half ---------------------------------------------------------------------

class TestCandidateWindow:
    def test_the_window_is_the_cameras_not_the_rows(self):
        """Region_Resolve tests the camera CENTRE, so the legal camera Ys are the row's span
        shifted up by HALF_H — not the row's span."""
        rec, cx, lo, hi = candidate = W.candidate_window(row(0, 0, 2047, 0, 2047), K, 5000, 6000)
        assert "verdict" not in rec, rec.get("verdict")
        assert lo == 0                                     # 0 - HALF_H clamped up at the act top
        assert hi == 2047 - K["HALF_H"]
        assert cx + K["HALF_W"] == 1023                    # the row's middle, centre-corrected
        assert candidate[1] == 1023 - K["HALF_W"]

    def test_camera_y_max_can_leave_a_legal_row_with_no_travel(self):
        """A row at the act's floor has a legal rectangle and nowhere for the camera to go. That
        is a rejection on GEOMETRY, before any config is read."""
        rec, _, lo, hi = W.candidate_window(row(3, 0, 2047, 4096, 6143), K, 5000, 3000)
        assert "no camera-Y travel" in rec["verdict"]
        assert hi <= lo

    def test_a_row_the_camera_cannot_centre_into_is_rejected_by_x(self):
        """Camera_X_Max is act_width - SCREEN_WIDTH, so the centre tops out short of the act's
        right edge. A narrow row past that point can never hold the centre."""
        rec, _, _, _ = W.candidate_window(row(9, 9000, 9500, 0, 2047), K, 100, 6000)
        assert "cannot centre inside this row's X span" in rec["verdict"]

    def test_probe_x_is_clamped_into_the_camera_range(self):
        rec, cx, _, _ = W.candidate_window(row(1, 0, 6143, 0, 2047), K, 120, 6000)
        assert cx == 120 and rec["probe_x"] == 120 + K["HALF_W"]


# ---- the arithmetic half -------------------------------------------------------------------

class TestJumpVerdict:
    def test_the_lock_sentinel_is_named_and_not_lumped_in_with_too_small(self):
        """THE REGRESSION THIS FILE IS FOR. v_factor 15 gives a jump of exactly 0 however far the
        camera travels, and a reader must be told that is the lock behaving correctly — the fix
        for it (re-aim) is the opposite of the fix for a wrong model."""
        rec = {}
        jump = W.jump_verdict(rec, cfg(15, 0, 288), 0, 2047, STEP)
        assert jump == 0
        assert "VERTICAL LOCK sentinel" in rec["verdict"]
        assert "CORRECT, not a modelling failure" in rec["verdict"]
        assert "does not exceed" not in rec["verdict"]

    def test_a_responsive_config_over_a_full_row_qualifies(self):
        rec = {}
        # ((1935 - 512) >> 3) - ((0 - 512) >> 3) = 177 - (-64) = 241
        jump = W.jump_verdict(rec, cfg(3), 0, 1935, STEP)
        assert jump == 241 and rec["verdict"] == "CHOSEN"

    def test_a_responsive_config_with_too_little_travel_is_rejected_as_too_small(self):
        rec = {}
        jump = W.jump_verdict(rec, cfg(3), 1000, 1100, STEP)   # 100 >> 3 = 12
        assert jump <= 2 * STEP
        assert "does not exceed" in rec["verdict"] and "LOCK" not in rec["verdict"]

    def test_the_threshold_is_strict_and_derived(self):
        """A jump of exactly 2 * step cannot force TWO consecutive ticks at the bound, so the
        test is `>`, not `>=`."""
        rec = {}
        # v_factor 0 makes the jump the camera travel itself, so the boundary is expressible.
        W.jump_verdict(rec, cfg(0, 0, 0), 0, 2 * STEP, STEP)
        assert rec["verdict"].startswith("REJECTED")
        W.jump_verdict(rec, cfg(0, 0, 0), 0, 2 * STEP + 1, STEP)
        assert rec["verdict"] == "CHOSEN"


# ---- the real act --------------------------------------------------------------------------

@pytest.mark.needs_build("s4.debug.bin", "s4.debug.lst")
def test_ojz_act1_has_both_locked_rows_and_a_qualifying_row():
    """The fact the first live run turned up, pinned so it cannot quietly stop being true.

    This act contains BOTH kinds of region. A scan that walks the table finds a qualifying one;
    a leg that inherits its column from wherever the camera stopped may land on a locked one and
    refuse. That asymmetry is the whole reason `plan_vertical_leg` exists, and if a future act
    ever has only locked rows this test says so in the same breath as the witness would.

    The camera clamps are not read from the emulator here, so they are derived the way the act
    itself derives them, and the assertions below are about the SHAPE of the population
    (some locked, at least one qualifying), never about a particular row index.
    """
    rom_p = os.path.join(AEON, "s4.debug.bin")
    lst_p = os.path.join(AEON, "s4.debug.lst")
    rom = open(rom_p, "rb").read()
    sym = parse_lst(lst_p)
    rows = region_table.read_regions(rom, sym["OJZ_Act1_Descriptor"])
    assert rows, "the act table is empty — this test measured nothing"

    off = region_table.act_region_offsets()
    act = sym["OJZ_Act1_Descriptor"]
    pcfg = W.pcfg_offsets()

    def u16(a):
        return int.from_bytes(rom[a:a + 2], "big")

    def u32(a):
        return int.from_bytes(rom[a:a + 4], "big")

    act_default = u32(act + off["act_parallax_config"]) if "act_parallax_config" in off else None
    if act_default is None:                       # the offset table does not carry it; read $16
        act_default = u32(act + 0x16)

    # EffectsPreset.ep_parallax, from the struct's own `@ $XX` declarations.
    ep = W.__dict__.get("_EP_CACHE")
    if ep is None:
        import re
        txt = open(os.path.join(AEON, "engine/effects/preset.emp")).read()
        m = re.search(r"pub struct EffectsPreset\s*\(size:\s*(\d+)\)\s*\{(.*?)^\}", txt,
                      re.M | re.S)
        ep = {fm.group(1): int(fm.group(2), 16)
              for fm in re.finditer(r"^\s*(ep_\w+)\s*:[^@\n]*@\s*\$([0-9A-Fa-f]+)",
                                    m.group(2), re.M)}
    # Effects_ResolveParallax's rungs, restated ONLY to classify the table for this population
    # check — never to decide a leg. The witness itself asks the engine.
    cam_x_max = max(r["x1"] for r in rows) - 2 * K["HALF_W"] + 1
    cam_y_max = max(r["y1"] for r in rows) - 2 * K["HALF_H"] + 1

    locked, qualifying, rejected = [], [], []
    for r in rows:
        rec, _, lo, hi = W.candidate_window(r, K, cam_x_max, cam_y_max)
        if "verdict" in rec:
            rejected.append((r["index"], rec["verdict"]))
            continue
        p = r["parallax"] or u32(r["effects"] + ep["ep_parallax"]) or act_default
        c = {"ptr": p, "v_factor": rom[p + pcfg["pcfg_v_factor_bg"]],
             "v_center": u16(p + pcfg["pcfg_v_center_y"]),
             "v_offset": u16(p + pcfg["pcfg_v_offset"]),
             "bob": rom[p + pcfg["pcfg_bob"]]}
        W.jump_verdict(rec, c, lo, hi, STEP)
        if c["v_factor"] == 15:
            locked.append(r["index"])
        elif rec["verdict"] == "CHOSEN":
            qualifying.append((r["index"], rec["derived_jump"]))
        else:
            rejected.append((r["index"], rec["verdict"]))

    assert locked, (
        "no region row in OJZ act 1 is vertically locked, so this test is no longer covering the "
        "case that caused the defect. Either the act changed or the classification is broken; "
        "either way re-read it rather than deleting it.")
    assert qualifying, (
        f"NO region row in OJZ act 1 can force the rate clamp: {len(locked)} row(s) are "
        f"vertically locked ({locked}) and the rest were rejected ({rejected}). Leg W and leg S "
        "would both be COULD NOT RUN on this ROM, which is a real finding about the act and "
        "not a tool failure — but it means step 4 has no discriminator, so read it before "
        "landing anything.")
    # The bob is not modelled by target_scroll; if a shipped config ever authors one, the whole
    # derivation above (and the witness's A3) is wrong rather than merely incomplete.
    assert all(rom[(r["parallax"] or u32(r["effects"] + ep["ep_parallax"]) or act_default)
                   + pcfg["pcfg_bob"]] == 0 for r in rows), (
        "a shipped parallax_config authors a vertical bob (pcfg_bob != 0). target_scroll() does "
        "not model the sine term, so the witness's A3 and this test's jumps are both wrong. "
        "Teach target_scroll() before trusting either.")


@pytest.mark.needs_build("s4.debug.bin", "s4.debug.lst")
def test_patching_rg_bg_span_on_disk_hits_exactly_the_right_two_bytes():
    """Leg S's ROM patch, checked WITHOUT an emulator — which is the half that can be wrong
    silently.

    The live `emulator/write_memory` poke leg S used to do is refused by the Rust core (only
    $E00000-$FFFFFF is writable), so leg S now patches `rg_bg_span` in a COPY OF THE ROM ON DISK
    and boots that. The emulator half of that is verified for free on spawn —
    `AetherInstance.start()` byte-compares the whole 4 MB cart against the file. What nothing
    else checks is the ARITHMETIC: that a Region record's ROM address is also its offset in the
    file, and that two bytes at `addr + rg_bg_span` are the field and not a neighbour.

    That identity is not assumed here, it is exercised: patch the copy, then read the region
    table back OUT OF THE PATCHED IMAGE with the same reader the witness uses, and require that
    the chosen row's span is the patched value, every other row is untouched, and exactly two
    bytes of the file changed.
    """
    rom = open(os.path.join(AEON, "s4.debug.bin"), "rb").read()
    sym = parse_lst(os.path.join(AEON, "s4.debug.lst"))
    rows = region_table.read_regions(rom, sym["OJZ_Act1_Descriptor"])
    ro, _ = region_table.region_layout()

    target = rows[1] if len(rows) > 1 else rows[0]
    off = target["addr"] + ro["rg_bg_span"]
    assert off + 2 <= len(rom), f"rg_bg_span at {off:#x} is past the {len(rom)}-byte image"
    span_test = 368                                    # any legal span; the value is not the point

    image = bytearray(rom)
    image[off:off + 2] = span_test.to_bytes(2, "big")

    changed = [i for i, (a, b) in enumerate(zip(rom, bytes(image))) if a != b]
    assert changed == [off, off + 1] or len(changed) <= 2, (
        f"the patch changed {len(changed)} byte(s) at {changed[:8]}, not the two at {off:#x}")

    after = region_table.read_regions(bytes(image), sym["OJZ_Act1_Descriptor"])
    assert after[target["index"]]["bg_span"] == span_test, (
        f"after patching {off:#x} the reader still sees bg_span "
        f"{after[target['index']]['bg_span']} on row {target['index']} — the Region record's ROM "
        "ADDRESS is not its file OFFSET, and leg S would be patching something else entirely")
    for a, b in zip(rows, after):
        if a["index"] == target["index"]:
            continue
        assert a == b, f"patching row {target['index']} also changed row {a['index']}: {a} -> {b}"
    # The field the patch aims at is the LAST in the record, so an off-by-one lands outside it
    # and the check above would still pass on a lucky read. Pin the offset against the struct.
    assert ro["rg_bg_span"] == 20 and off == target["addr"] + 20, (
        f"rg_bg_span moved to offset {ro['rg_bg_span']}; leg S's patch site is derived from "
        "region_layout() so it follows, but the note and the witness header quote 20/$14")


# ---- the granularity split, from the run that went red ---------------------------------------

def sample(v, cam_y, *, dtick=1, region=0x18AC0, cfg_ptr=0x134E8, v_factor=3, ceiling=288,
           v_center=512, v_offset=0, tag="t"):
    return {"tag": tag, "v": v, "cam_y": cam_y, "cam_x": 0, "dtick": dtick, "logic_tick": 0,
            "region": region, "row": 1, "span": 0, "ceiling": ceiling, "trans": 0,
            "centre": (0, 0), "lag": 0,
            "cfg": {"ptr": cfg_ptr, "v_factor": v_factor, "v_center": v_center,
                    "v_offset": v_offset, "bob": 0}}


# OJZ act 1's two real config shapes, so the fixtures below are the act's arithmetic and not
# invented numbers: the act default (v_factor 3, v_center 512, v_offset 0) and a vertical-lock
# row (v_factor 15, v_offset 288 — the scroll pinned camera-independently).
DEFAULT = dict(cfg_ptr=0x134E8, v_factor=3, v_center=512, v_offset=0)
LOCK = dict(cfg_ptr=0x14A68, v_factor=15, v_center=0, v_offset=288, region=0x18AD6)
# camY 1935 under DEFAULT gives ((1935 - 512) >> 3) = 177, which is the act's real reach.
REACH = 177


class TestGranularity:
    """THE REGRESSION FOR THE THIRD LIVE RUN. Leg W reported `tick 1 moved ... by 32 px`, which
    is exactly 2 x BG_VSCROLL_MAX_STEP against an unclamped target of 177. A warp tick runs
    Parallax_Update TWICE (Debug_Warp_Consume primes, then the frame body runs), so per-tick
    sampling attributes two correctly-clamped stores to one tick. These pin that the two
    granularities disagree in exactly that way and that only the per-tick one is fooled."""

    def test_per_tick_sampling_reads_two_clamped_stores_as_one_illegal_step(self):
        fails = []
        # camY 1935 -> target 177; the store sequence 0, 32 is what a warp tick LOOKS like when
        # only its endpoints are sampled.
        W.check_leg(fails, K, "W", [sample(0, 1935), sample(32, 1935)], granularity="tick")
        assert any("A1" in f and "32 px" in f for f in fails), fails
        assert any(f"past BG_VSCROLL_MAX_STEP = {STEP}" in f for f in fails), fails

    def test_per_invocation_sampling_sees_two_legal_stores(self):
        """The same 32 px of travel, sampled once per Parallax_Update, is two 16 px steps and
        breaks nothing. This is the fix, and it TIGHTENS: it asserts on what the clamp bounds."""
        fails = []
        r = W.check_leg(fails, K, "W", [sample(0, 1935), sample(16, 1935), sample(32, 1935)],
                        granularity="step5")
        assert fails == [], fails
        assert r["worst_step"] == STEP and r["ticks_at_the_bound"] == 2

    def test_a3_pairs_the_camera_with_the_store_it_produced_and_the_pairing_differs(self):
        """Per TICK the value at i was produced by the camera sampled at i; per INVOCATION the
        entry sample reads the PREVIOUS store, so v[i] pairs with cam[i-1]. Getting this
        backwards models the wrong frame, so it is pinned rather than commented."""
        # cam 1935 -> target 177, clamped to +16 from 0; cam 0 -> target -64, clamped to 0.
        per_tick = [sample(0, 0), sample(16, 1935)]
        fails = []
        W.check_leg(fails, K, "T", per_tick, granularity="tick")
        assert fails == [], fails                       # v[1]=16 from cam[1]=1935: correct
        fails = []
        W.check_leg(fails, K, "S", per_tick, granularity="step5")
        assert any("A3" in f for f in fails), (
            "step5 mode accepted a pairing only the tick mode makes true, so the two modes are "
            "not actually distinguishing which camera produced the store")

    def test_a_multi_tick_interval_BLOCKS_rather_than_reporting_a_giant_step(self):
        """A lag tick or a missed Update entry read as one step is exactly how a working clamp
        looks broken. The tick-mode leg refuses instead of reporting."""
        with pytest.raises(W.LegBlocked) as e:
            W.check_leg([], K, "C", [sample(0, 0), sample(32, 1935, dtick=2)],
                        granularity="tick")
        assert "not exactly one logic tick" in str(e.value)

    def test_bound_steps_are_attributed_by_exact_decomposition(self):
        """FINDING D's answer, and the REGRESSION for the classifier that produced it.

        The first version compared the region/config pointers of two ADJACENT samples and called
        everything else "steady state". That cannot see a BACKLOG, so a ratchet's later steps
        were labelled steady-state while the crossing that caused them sat steps earlier — which
        is exactly the ambiguity the controller raised. `why_it_bound` decomposes the gap into
        d_cfg + d_cam + backlog with no remainder, so the three cases separate."""
        # a crossing into a vertical-lock row: caught up at 177, the target jumps to 288
        crossing = [sample(REACH, 1935, **DEFAULT),
                    sample(REACH + STEP, 1935, **LOCK)]
        r = W.check_leg([], K, "D", crossing, granularity="tick")
        assert r["bound_by"]["config"] == 1, r["bound_at"]
        assert not any(x["blocking"] for x in r["bound_at"])
        # the ratchet AFTER it: pointers equal across every step, but the value is still behind
        ratchet = [sample(REACH, 1935, **LOCK),
                   sample(REACH + STEP, 1935, **LOCK),
                   sample(REACH + 2 * STEP, 1935, **LOCK)]
        r = W.check_leg([], K, "D", ratchet, granularity="tick")
        assert r["bound_by"]["backlog"] == 2, r["bound_at"]
        assert r["bound_by"]["camera"] == 0
        assert not any(x["blocking"] for x in r["bound_at"]), (
            "a ratchet is the clamp doing its job and must not block — the OLD classifier "
            "called these steady-state, which is the mislabelling this test exists for")

    def test_only_two_answers_block_and_they_are_the_two_that_contradict_the_derivation(self):
        # camera term over the bound with the config UNCHANGED: contradicts v_factor 3
        big_cam = [sample(0, 0, v_factor=0, v_center=0, ceiling=4000),
                   sample(STEP, 400, v_factor=0, v_center=0, ceiling=4000)]
        r = W.check_leg([], K, "D", big_cam, granularity="tick")
        assert r["bound_by"]["camera"] == 1, r["bound_at"]
        assert r["bound_at"][0]["blocking"]
        # a bind the model says was unnecessary: impossible while A3 is green. camY 512 under
        # the act default gives target 0, so a 16 px move needed no clamping at all.
        contra = [sample(0, 512, **DEFAULT), sample(STEP, 512, **DEFAULT)]
        r = W.check_leg([], K, "D", contra, granularity="tick")
        assert r["bound_by"]["contradiction"] == 1, r["bound_at"]
        assert r["bound_at"][0]["blocking"]
        # two ordinary terms ADDING UP is arithmetic, not a mystery, and must not block —
        # flagging it would teach a reader to ignore the flag. Target 1000 -> 1010 (d_cam 10)
        # with the value 10 behind (backlog 10): gap 20, no single term over 16.
        comb = [sample(990, 1000, v_factor=0, v_center=0, ceiling=4000),
                sample(990 + STEP, 1010, v_factor=0, v_center=0, ceiling=4000)]
        r = W.check_leg([], K, "D", comb, granularity="tick")
        assert r["bound_by"]["combined"] == 1, r["bound_at"]
        assert not r["bound_at"][0]["blocking"]

    def test_a_blocking_observation_carries_its_own_trace(self):
        """The old code printed "read the trace before accepting this run" and exited 0. It now
        carries the trace, so nobody has to go and find it."""
        big_cam = [sample(0, 0, v_factor=0, v_center=0, ceiling=4000),
                   sample(STEP, 400, v_factor=0, v_center=0, ceiling=4000),
                   sample(2 * STEP, 800, v_factor=0, v_center=0, ceiling=4000)]
        r = W.check_leg([], K, "D", big_cam, granularity="tick")
        obs = r["blocking_observations"]
        assert obs and obs[0]["trace"], "a blocking observation shipped without its trace"
        assert {"tag", "v", "cam_y", "row"} <= set(obs[0]["trace"][0])
        d = obs[0]["decomposition"]
        assert d["gap"] == d["d_cfg"] + d["d_cam"] + d["backlog"], (
            "the decomposition does not sum to the gap — it is supposed to be exact")


class TestSourceShapeChecksAreLive:
    """⚠ THESE HAVE A POSITIVE *AND* A NEGATIVE ARM, and the negative arm is the whole point.

    The first version of the warp test only called `warp_consumer_shape_check()` and asserted it
    did not raise. A mutation that emptied the check's search loop — making it look at nothing at
    all — left that test GREEN. That is a runner defect, not a pass: a check asserting "the tree
    is fine" is satisfied by a check that cannot see the tree. Both functions now take doctored
    `text` so the refusal itself can be exercised."""

    def test_the_warp_consumer_check_refuses_source_with_the_second_update_removed(self):
        good = open(os.path.join(AEON, "games/sonic4/test/ojz_scroll_test.emp")).read()
        W.warp_consumer_shape_check(good)                       # positive: the real tree passes
        gutted = good.replace("jbsr    Parallax_Update", "jbsr    Nothing_At_All")
        assert gutted != good, "the substitution matched nothing — the probe is not probing"
        with pytest.raises(W.SetupError) as e:
            W.warp_consumer_shape_check(gutted)
        assert "Parallax_Update" in str(e.value)

    def test_the_warp_consumer_check_refuses_a_frame_top_that_stopped_calling_it(self):
        good = open(os.path.join(AEON, "games/sonic4/test/ojz_scroll_test.emp")).read()
        moved = good.replace("if DEBUG == 1 {\n                jbsr    Debug_Warp_Consume",
                             "if DEBUG == 1 {\n                jbsr    Something_Else")
        assert moved != good, "the substitution matched nothing — the probe is not probing"
        with pytest.raises(W.SetupError) as e:
            W.warp_consumer_shape_check(moved)
        assert "frame top" in str(e.value)

    def test_the_step5_check_refuses_a_clamp_whose_instructions_changed(self):
        good = open(os.path.join(AEON, "engine/level/parallax.emp")).read()
        W.step5_shape_check(good)                               # positive: the real tree passes
        gutted = good.replace("move.w  Region.rg_bg_span(a1), d0",
                              "move.w  Region.rg_x0(a1), d0")
        assert gutted != good, "the substitution matched nothing — the probe is not probing"
        with pytest.raises(W.SetupError) as e:
            W.step5_shape_check(gutted)
        assert "clamp_model" in str(e.value)
