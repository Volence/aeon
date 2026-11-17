"""Tests for tools/stress_objects_overlay.py (v2 step 0, C2: the STRESS_OBJECTS=1 shape).

Pure lane: synthetic paths, the committed path fixture and the committed overlay. No build
artifact is read (the equates the committed overlay was generated with are the ones it
records; the in-build `check` re-reads them from the shape's OWN listing)."""
import json
import math

import pytest

import stress_objects_overlay as so

#: The equates as the canonical listing publishes them (s4.lst / s4.debug.lst at d60c5ee6,
#: MEASURED in the C1 note). Synthetic tests use them; the committed-overlay tests use the
#: overlay's own recorded block instead.
EQ = {"NUM_DYNAMIC": 0x28, "CULL_DISTANCE_X": 0x300, "CULL_DISTANCE_Y": 0x200,
      "ENTITY_LOAD_BUFFER": 0x180, "ENTITY_DESPAWN_BUFFER": 0x200,
      "ENTITY_LOAD_BUFFER_Y": 0x100, "ENTITY_DESPAWN_BUFFER_Y": 0x180,
      "SCREEN_WIDTH": 0x140, "SCREEN_HEIGHT": 0xE0, "SECTION_SIZE": 0x800}


def cheb(a, b):
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def wiggle_path(n=1200):
    """A path with slopes, a hump and a vertical drop: every normal direction occurs."""
    pts = []
    for t in range(n):
        x = 200 + 4 * t
        y = 1500 + int(180 * math.sin(t / 40.0)) + (300 if t > 700 else 0)
        pts.append((x, y))
    return pts


# ---- the three brief tests ----------------------------------------------------------------

def test_no_object_within_clearance_of_path():
    """Every placed object is at least `clearance_px` (Chebyshev) from EVERY path point,
    on a synthetic path and on the committed overlay against the committed fixture's
    union of paths (all shapes and phases the fixture carries)."""
    path = wiggle_path()
    objs = so.place(path, 3 * EQ["SECTION_SIZE"], 3 * EQ["SECTION_SIZE"])
    assert objs, "positive control: the wiggle path must place something"
    worst = min(cheb((o["x"], o["y"]), p) for o in objs for p in path)
    assert worst >= so.CLEARANCE_PX, f"an object sits {worst} px from the path"

    fx = so.load_path_fixture()
    union = so.union_points(fx)
    ov = so.load_overlay()
    assert ov["objects"], "the committed overlay places nothing"
    # A 2-D grid makes the all-pairs check cheap; it is exact (cell = clearance).
    c = so.CLEARANCE_PX
    grid = {}
    for p in union:
        grid.setdefault((p[0] // c, p[1] // c), []).append(p)
    bad = []
    for o in ov["objects"]:
        gx, gy = o["x"] // c, o["y"] // c
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for p in grid.get((gx + dx, gy + dy), ()):
                    if cheb((o["x"], o["y"]), p) < c:
                        bad.append((o, p))
    assert not bad, f"{len(bad)} overlay object(s) within {c} px of a path point: {bad[:3]}"


def test_count_matches_density():
    """Density is the C1 note's: one candidate pair (±OFFSET along the normal) per SPACING
    px of path arc length. A straight 2000 px path at 2 px/tick places exactly
    2 * floor(1000 / (SPACING / 2)) candidates, all clear of the path; thinning then holds
    the modelled live count to NUM_DYNAMIC - LIVE_CAP_MARGIN with no alloc failure."""
    path = [(100 + 2 * t, 1000) for t in range(1001)]
    objs = so.place(path, 6144, 6144)
    steps = 1000 // (so.SPACING // 2)
    assert len(objs) == 2 * steps, (len(objs), 2 * steps)
    assert {o["y"] for o in objs} == {1000 - so.OFFSET, 1000 + so.OFFSET}
    assert [o["typeId"] for o in objs[:4]] == ["solid", "static", "solid", "static"]
    assert all(o["subtype"] == 0 for o in objs)

    cam = [(x - 160, 1000 - 112) for (x, _y) in path]
    cap = EQ["NUM_DYNAMIC"] - so.LIVE_CAP_MARGIN
    kept = so.thin(objs, canon=[], cams=[cam], equ=EQ, cap=cap)
    res, fails = so.simulate([(o["x"], o["y"]) for o in kept], cam, EQ)
    assert max(lv for lv, _d in res) <= cap and fails == 0
    assert max(lv for lv, _d in so.simulate([(o["x"], o["y"]) for o in objs], cam, EQ)[0]) > cap, \
        "positive control: unthinned, this density over-fills the window"

    # The committed overlay's own count is the one its header records and its model gives.
    ov = so.load_overlay()
    assert ov["count"] == len(ov["objects"])
    for name, m in ov["model"].items():
        assert m["live_max"] <= ov["equates"]["NUM_DYNAMIC"] - so.LIVE_CAP_MARGIN, name
        assert m["alloc_fails"] == 0, name


def test_overlay_is_deterministic():
    """Same inputs give byte-identical JSON: twice in-process, and the committed overlay
    regenerated from the committed fixture with its own recorded equates."""
    path = wiggle_path(600)
    fx = {"paths": {"release/0": {"t0": 0, "cx": [x - 160 for x, _ in path],
                                  "cy": [y - 112 for _, y in path],
                                  "px": [x for x, _ in path], "py": [y for _, y in path]}},
          "sha256": "0" * 64}
    a = so.dumps(so.build_overlay(fx, canon=[], act_w=6144, act_h=6144, equ=EQ))
    b = so.dumps(so.build_overlay(fx, canon=[], act_w=6144, act_h=6144, equ=EQ))
    assert a == b

    ov_text = so.OVERLAY.read_text()
    ov = json.loads(ov_text)
    again = so.dumps(so.build_overlay(so.load_path_fixture(), canon=so.canon_objects(),
                                      act_w=ov["act"]["w"], act_h=ov["act"]["h"],
                                      equ=ov["equates"]))
    assert again == ov_text, "the committed overlay is not what its inputs generate"


# ---- the in-build self-check (a gate: its red proofs are in the task-8 report) -----------

def test_check_refuses_over_cap_and_under_dispatch():
    path = [(100 + 2 * t, 1000) for t in range(1001)]
    cam = [(x - 160, 1000 - 112) for (x, _y) in path]
    objs = [(o["x"], o["y"]) for o in so.place(path, 6144, 6144)]
    v = so.verdict(objs, {"release/0": cam}, EQ)
    assert not v["ok"] and "live" in v["why"], v          # unthinned: over the cap
    v = so.verdict([], {"release/0": cam}, EQ)
    assert not v["ok"] and "dispatched" in v["why"], v    # nothing placed: no load


def test_unmeasurable_without_equates(tmp_path):
    lst = tmp_path / "x.lst"
    lst.write_text("EQU NUM_DYNAMIC = $00000028\n")
    with pytest.raises(so.OverlayError, match="CULL_DISTANCE_X"):
        so.equates_from_listing(lst)


def test_types_are_registered_and_never_spring_or_enemy():
    lib = so.object_library_ids()
    assert set(so.TYPES) <= lib
    assert not {"spring", "enemy"} & set(so.TYPES)
    assert {o["typeId"] for o in so.load_overlay()["objects"]} <= set(so.TYPES)


# ---- the re-bake: ojz_entity_gen generate --overlay ----------------------------------------

def test_entity_gen_without_overlay_reproduces_the_committed_bake(tmp_path):
    import ojz_entity_gen as eg
    out = tmp_path / "entity_data.emp"
    eg.main(["generate", "--out", str(out)])
    assert out.read_text() == open(eg.OUTPUT_PATH).read()


def test_entity_gen_overlay_merges_every_object(tmp_path):
    import ojz_entity_gen as eg
    out = tmp_path / "entity_data.emp"
    eg.main(["generate", "--overlay", str(so.OVERLAY), "--out", str(out)])
    ov = so.load_overlay()
    gw, _gh = so.act_grid()
    got = so.parse_entity_data(out.read_text(), gw, eg.SECTION_SIZE)
    assert len(got) == ov["canon_count"] + ov["count"]
    assert sorted(got) == sorted(so.canon_objects() + [(o["x"], o["y"]) for o in ov["objects"]])
    assert "STRESS_OBJECTS OVERLAY" in out.read_text()


def test_entity_gen_refuses_an_overlay_object_outside_the_act(tmp_path):
    import ojz_entity_gen as eg
    bad = tmp_path / "ov.json"
    bad.write_text(json.dumps({"objects": [{"x": 99999, "y": 10, "typeId": "solid",
                                            "subtype": 0}]}))
    with pytest.raises(SystemExit, match="outside"):
        eg.main(["generate", "--overlay", str(bad), "--out", str(tmp_path / "o.emp")])


# ---- build.sh's STRESS_OBJECTS shape refusals (a gate: red proofs in the task-8 report) ----

import os  # noqa: E402
import subprocess  # noqa: E402

AEON_DIR = so.AEON


def _build_sh(**env_over):
    """build.sh with SIGIL_BUILD pointed at nothing: every refusal under test sits ABOVE the
    sigil-binary check, so a refused combination stops at its refusal and an accepted one
    stops at the sigil check, both before any work (no re-bake, no artifact)."""
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("STRESS_", "S2CLIP", "FAST", "DEBUG"))}
    env.update(SIGIL_BUILD="/nonexistent/sigil", **env_over)
    p = subprocess.run(["bash", "build.sh"], cwd=AEON_DIR, env=env, capture_output=True,
                       text=True, timeout=120)
    return p.returncode, p.stdout + p.stderr


@pytest.mark.parametrize("other", [{"S2CLIP": "s2_ehz_cpz"}, {"STRESS_ART": "1"},
                                   {"STRESS_EVICT": "1"}, {"STRESS_SIDEKICK": "1"}])
def test_stress_objects_refuses_another_offcanonical_shape(other):
    rc, out = _build_sh(STRESS_OBJECTS="1", **other)
    assert rc == 1 and "mutually exclusive" in out, out[-2000:]
    assert "needs the sigil build binary" not in out


def test_stress_objects_refuses_fast():
    rc, out = _build_sh(STRESS_OBJECTS="1", FAST="1")
    assert rc == 1 and "FAST=1 is refused on the STRESS_* fixture shapes" in out, out[-2000:]


def test_stress_objects_alone_passes_the_refusals():
    """Positive control: alone it reaches the sigil-binary check (nothing refused it)."""
    rc, out = _build_sh(STRESS_OBJECTS="1")
    assert rc == 1 and "needs the sigil build binary" in out, out[-2000:]
    assert "mutually exclusive" not in out and "FAST=1 is refused" not in out


def test_stress_objects_rom_names_are_standalone_literals():
    import gate_cut_shape as gcs
    assert {"s4.stressobj.lst", "s4.stressobj.debug.lst"} <= gcs.off_canonical_listings()
