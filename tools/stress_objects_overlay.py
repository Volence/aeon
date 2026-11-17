#!/usr/bin/env python3
"""stress_objects_overlay — the object overlay of the STRESS_OBJECTS=1 shape (v2 step 0, C2).

WHAT. The object-heavy leg needs OJZ act 1 packed with dynamic objects that sit OFF the
player's path, so the run policy's route is unchanged while the object pool runs near full.
This module places them, models the engine's entity window over the recorded camera paths,
and thins the placement until the modelled live count never exceeds NUM_DYNAMIC - 2. The
design is the C1 sizing note's (`docs/superpowers/notes/2026-11-16-stress-content-sizing.md`
§1.2-1.4), ported from its reference model `.scratch-c1/sim/objsim{,2}.py`:

  * candidates: at every SPACING px of path arc length, one object OFFSET px each side along
    the path normal; dropped if outside the act or within CLEARANCE_PX (Chebyshev) of ANY
    recorded path point (the union over every shape and phase the fixture carries);
  * types alternate `solid` / `static` at subtype 0 (both in objects.json, both in release
    and DEBUG; never `spring`, which launches the player, never `enemy`, DEBUG-only);
  * thinning: replay the entity window (load / despawn rule of engine/objects/entity_window.emp)
    over every recorded camera path; at the worst tick over the cap, drop the overlay objects
    farthest from the camera; repeat until no tick is over the cap.

Every engine number is a LISTING EQUATE (`equates_from_listing`), never a literal here. The
committed overlay records the equates it was generated with; the in-build `check` re-reads
them from the shape's OWN listing.

    python3 tools/stress_objects_overlay.py fixture RESULT.json... [--out PATH]
        the path fixture from canonical `leg_run --leg run` results (one per shape x phase)
    python3 tools/stress_objects_overlay.py generate --lst s4.lst [--path F] [--out O]
        the overlay (deterministic: same inputs, byte-identical JSON)
    python3 tools/stress_objects_overlay.py check --lst SHAPE.lst --entity-data E [--path F]
        the shape's self-check on the BAKED entity data (build.sh runs it after sigil):
        exit 0 ok, 1 over the live cap / under-dispatched / overlay not baked, 2 unmeasurable

The re-bake itself is `ojz_entity_gen.py generate --overlay <overlay>` (build.sh's
STRESS_OBJECTS block, under an EXIT trap that restores the generated tree from git).
"""
from __future__ import annotations

import argparse
import bisect
import hashlib
import json
import math
import re
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
AEON = TOOLS.parent
sys.path.insert(0, str(TOOLS))
import leg_drive as ld  # noqa: E402
import ojz_entity_gen as eg  # noqa: E402

FIXTURES = AEON / "games" / "sonic4" / "test" / "fixtures"
#: NOT under games/sonic4/data/editor/: tools/level_staleness.py hashes every file there, so
#: an overlay at the plan's path turns the canonical build's staleness gate STALE (C1 §1.3.3).
PATH_FIXTURE = FIXTURES / "stress_objects.path.json"
OVERLAY = FIXTURES / "stress_objects.overlay.json"

# Placement parameters (the C1 note's design row: perpendicular ±96 px, 24 px spacing).
SPACING = 24
OFFSET = 96
CLEARANCE_PX = 64
LIVE_CAP_MARGIN = 2          # the model's cap is NUM_DYNAMIC - 2: headroom for the canonical
                             # act's own objects and one-tick model error (C1 §1.3.1)
TYPES = ("solid", "static")
PRIMARY = "release/0"        # the path candidates are sampled along

EQU_NEEDED = ("NUM_DYNAMIC", "CULL_DISTANCE_X", "CULL_DISTANCE_Y", "ENTITY_LOAD_BUFFER",
              "ENTITY_DESPAWN_BUFFER", "ENTITY_LOAD_BUFFER_Y", "ENTITY_DESPAWN_BUFFER_Y",
              "SCREEN_WIDTH", "SCREEN_HEIGHT", "SECTION_SIZE")


class OverlayError(RuntimeError):
    """An input is missing or does not say what it must. Never a result."""


# ---- inputs -------------------------------------------------------------------------------

def equates_from_listing(lst) -> dict:
    _addr, equ, _debug = ld.parse_listing(Path(lst))
    miss = [n for n in EQU_NEEDED if n not in equ]
    if miss:
        raise OverlayError(f"{lst}: the listing publishes no EQU {', '.join(miss)}")
    return {n: equ[n] for n in EQU_NEEDED}


def object_library_ids() -> set:
    return set(eg.load_object_library())


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def load_path_fixture(path=PATH_FIXTURE) -> dict:
    raw = Path(path).read_bytes()
    fx = json.loads(raw)
    if not isinstance(fx.get("paths"), dict) or not fx["paths"]:
        raise OverlayError(f"{path}: no `paths`")
    fx["sha256"] = sha256_bytes(raw)
    return fx


def load_overlay(path=OVERLAY) -> dict:
    return json.loads(Path(path).read_text())


def fixture_points(entry: dict) -> list:
    return list(zip(entry["px"], entry["py"]))


def fixture_cams(entry: dict) -> list:
    return list(zip(entry["cx"], entry["cy"]))


def union_points(fx: dict) -> list:
    pts = set()
    for e in fx["paths"].values():
        pts.update(fixture_points(e))
    return sorted(pts)


def act_grid() -> tuple[int, int]:
    cfg = eg.load_act_config()
    return cfg["grid_w"], cfg["grid_h"]


def canon_objects() -> list:
    """The shipped act's objects in world pixels, from the editor JSONs (the source of truth
    the canonical entity_data.emp is generated from)."""
    cfg = eg.load_act_config()
    out = []
    for n in range(cfg["grid_w"] * cfg["grid_h"]):
        sx, sy = n % cfg["grid_w"], n // cfg["grid_w"]
        for o in eg.load_section_json(cfg["data_path"], n, "objects"):
            out.append((sx * eg.SECTION_SIZE + o["x"], sy * eg.SECTION_SIZE + o["y"]))
    return out


_OBJ_TABLE = re.compile(r"OJZ_Sec(\d+)_Objects:\s*\[u16;\s*\d+\]\s*=\s*\[([^\]]*)\]")


def parse_entity_data(text: str, grid_w: int, section_size: int) -> list:
    """World (x, y) of every object entry in a generated entity_data.emp."""
    out = []
    for m in _OBJ_TABLE.finditer(text):
        sec = int(m.group(1))
        vals = [int(v.strip().replace("$", "0x"), 16) for v in m.group(2).split(",") if v.strip()]
        sx, sy = sec % grid_w, sec // grid_w
        i = 0
        while i + 2 < len(vals) and vals[i] != 0xFFFF:
            out.append((sx * section_size + vals[i], sy * section_size + vals[i + 1]))
            i += 3
    return out


# ---- placement ----------------------------------------------------------------------------

def place(path, act_w: int, act_h: int, spacing: int = SPACING, offset: int = OFFSET,
          clearance_px: int = CLEARANCE_PX, clear_of=None, types=TYPES) -> list:
    """Candidates along `path` (list of (x, y)): one pair per `spacing` px of arc length, at
    ±`offset` along the path normal; none outside [0, act_w) x [0, act_h) or within
    `clearance_px` (Chebyshev) of any point of `clear_of` (default: `path`). Types alternate
    in placement order. Port of objsim2.place_perp, with the clearance grid sized to the
    clearance instead of a fixed 64 px."""
    pts = list(clear_of if clear_of is not None else path)
    c = max(1, int(clearance_px))
    grid = {}
    for (x, y) in pts:
        grid.setdefault((x // c, y // c), []).append((x, y))

    def clear(x, y):
        gx, gy = x // c, y // c
        for ax in (gx - 1, gx, gx + 1):
            for ay in (gy - 1, gy, gy + 1):
                for (px, py) in grid.get((ax, ay), ()):
                    if abs(px - x) < c and abs(py - y) < c:
                        return False
        return True

    out, seen, acc = [], set(), 0.0
    for i in range(1, len(path)):
        (x0, y0), (x1, y1) = path[i - 1], path[i]
        d = math.hypot(x1 - x0, y1 - y0)
        if d == 0:
            continue
        acc += d
        if acc < spacing:
            continue
        acc = 0.0
        nx, ny = -(y1 - y0) / d, (x1 - x0) / d
        for s in (1, -1):
            x, y = int(round(x1 + s * offset * nx)), int(round(y1 + s * offset * ny))
            if not (0 <= x < act_w and 0 <= y < act_h):
                continue
            k = (x // 16, y // 16)
            if k in seen or not clear(x, y):
                continue
            seen.add(k)
            out.append({"x": x, "y": y, "typeId": types[len(out) % len(types)], "subtype": 0})
    return out


# ---- the entity-window model ---------------------------------------------------------------

class _Window:
    """engine/objects/entity_window.emp's load/despawn rule and RunObjects' cull, as the C1
    model (objsim.simulate) states them, over a fixed object list. Objects are bucketed per
    section and x-sorted so a tick only looks at the load band."""

    def __init__(self, objs, equ):
        self.objs = list(objs)
        self.e = equ
        self.shift = int(equ["SECTION_SIZE"]).bit_length() - 1
        if 1 << self.shift != equ["SECTION_SIZE"]:
            raise OverlayError(f"SECTION_SIZE {equ['SECTION_SIZE']} is not a power of two")
        self.buckets = {}
        for i, (x, y) in enumerate(self.objs):
            self.buckets.setdefault((x >> self.shift, y >> self.shift), []).append((x, i))
        for b in self.buckets.values():
            b.sort()
        self.keys = {k: [x for x, _ in b] for k, b in self.buckets.items()}

    def run(self, cam, cap=None):
        """Yield (live: dict idx -> True, fails_this_tick) per camera tick. `cap` None is the
        thinning pass's uncapped load; an int is Load_Object's pool limit."""
        e, sh = self.e, self.shift
        ELB, EDB, ELBY, EDBY = (e["ENTITY_LOAD_BUFFER"], e["ENTITY_DESPAWN_BUFFER"],
                                e["ENTITY_LOAD_BUFFER_Y"], e["ENTITY_DESPAWN_BUFFER_Y"])
        SW, SH = e["SCREEN_WIDTH"], e["SCREEN_HEIGHT"]
        live = {}
        for (cx, cy) in cam:
            sx0, sy0 = max(0, (cx - EDB) >> sh), max(0, (cy - EDBY) >> sh)
            tracked = {(sx0 + a, sy0 + b) for a in (0, 1) for b in (0, 1)}
            for i in list(live):
                x, y = self.objs[i]
                if (x >> sh, y >> sh) not in tracked or not (cy - EDBY <= y <= cy + SH + EDBY):
                    del live[i]
            elig = []
            for k in tracked:
                b = self.buckets.get(k)
                if not b:
                    continue
                xs = self.keys[k]
                lo, hi = bisect.bisect_left(xs, cx - ELB), bisect.bisect_right(xs, cx + SW + ELB)
                for _x, i in b[lo:hi]:
                    if i not in live and cy - ELBY <= self.objs[i][1] <= cy + SH + ELBY:
                        elig.append(i)
            fails = 0
            for i in sorted(elig):
                if cap is not None and len(live) >= cap:
                    fails += 1
                    continue
                live[i] = True
            yield live, fails, cx, cy


def simulate(objs, cam, equ) -> tuple[list, int]:
    """[(live, dispatched)] per tick and the alloc-failure count, under the NUM_DYNAMIC pool."""
    w = _Window(objs, equ)
    cx_d, cy_d = equ["CULL_DISTANCE_X"], equ["CULL_DISTANCE_Y"]
    res, fails = [], 0
    for live, f, cx, cy in w.run(cam, cap=equ["NUM_DYNAMIC"]):
        fails += f
        disp = sum(1 for i in live if abs(w.objs[i][0] - cx) <= cx_d
                   and abs(w.objs[i][1] - cy) <= cy_d)
        res.append((len(live), disp))
    return res, fails


def _dedupe(cam):
    """Consecutive repeats of one camera position leave the window state unchanged, so the
    thinning pass skips them (the capped `simulate` keeps every tick)."""
    out = []
    for c in cam:
        if not out or out[-1] != c:
            out.append(c)
    return out


def thin(over, canon, cams, equ, cap) -> list:
    """objsim2.thin over several camera paths: while some tick of some path holds more than
    `cap` live objects (uncapped load), drop the overlay objects live at the globally worst
    tick that are farthest (Manhattan) from that camera, `worst - cap` of them."""
    over = list(over)
    canon = list(canon)
    paths = []
    for c in cams:
        d = _dedupe(c)
        if d not in paths:
            paths.append(d)
    while True:
        objs = canon + [(o["x"], o["y"]) for o in over]
        w = _Window(objs, equ)
        worst, at = cap, None
        for cam in paths:
            for live, _f, cx, cy in w.run(cam):
                if len(live) > worst:
                    worst, at = len(live), (list(live), cx, cy)
        if at is None:
            return over
        lv, cx, cy = at
        cand = sorted(i for i in lv if i >= len(canon))
        cand.sort(key=lambda i: -(abs(objs[i][0] - cx) + abs(objs[i][1] - cy)))
        drop = set(cand[:worst - cap])
        if not drop:
            raise OverlayError(f"the canonical objects alone hold {worst} > {cap} live")
        over = [o for j, o in enumerate(over) if (j + len(canon)) not in drop]


def dispatch_min(equ) -> int:
    return ld.obj_dispatch_min(equ)


def model_of(objs, cam, equ) -> dict:
    res, fails = simulate(objs, cam, equ)
    dmin = dispatch_min(equ)
    return {"ticks": len(res), "live_max": max((lv for lv, _ in res), default=0),
            "alloc_fails": fails, "dispatch_min": dmin,
            "ticks_dispatched_ge_min": sum(1 for _, d in res if d >= dmin)}


def verdict(objs, cams: dict, equ) -> dict:
    """The shape's self-check: on every recorded camera path, modelled live <= NUM_DYNAMIC -
    LIVE_CAP_MARGIN with no alloc failure, and >= OBJ_COVER_TICKS ticks with >= dispatch_min
    dispatched. `why` names every path that fails, with its counts."""
    cap = equ["NUM_DYNAMIC"] - LIVE_CAP_MARGIN
    per, why = {}, []
    for name in sorted(cams):
        m = model_of(objs, cams[name], equ)
        per[name] = m
        if m["live_max"] > cap or m["alloc_fails"]:
            why.append(f"{name}: modelled live max {m['live_max']} > cap {cap} or "
                       f"{m['alloc_fails']} alloc failure(s)")
        if m["ticks_dispatched_ge_min"] < ld.OBJ_COVER_TICKS:
            why.append(f"{name}: {m['ticks_dispatched_ge_min']} tick(s) with >= "
                       f"{m['dispatch_min']} dispatched, need {ld.OBJ_COVER_TICKS}")
    return {"ok": not why, "why": "; ".join(why), "per": per, "cap": cap}


# ---- the overlay --------------------------------------------------------------------------

def build_overlay(fx: dict, canon, act_w: int, act_h: int, equ: dict) -> dict:
    equ = {n: int(equ[n]) for n in EQU_NEEDED}
    names = sorted(fx["paths"])
    primary = PRIMARY if PRIMARY in fx["paths"] else names[0]
    path = fixture_points(fx["paths"][primary])
    union = union_points(fx)
    cand = place(path, act_w, act_h, clear_of=union)
    cams = {n: fixture_cams(fx["paths"][n]) for n in names}
    cap = equ["NUM_DYNAMIC"] - LIVE_CAP_MARGIN
    kept = thin(cand, canon, [cams[n] for n in names], equ, cap)
    objs = list(canon) + [(o["x"], o["y"]) for o in kept]
    return {
        "schema": 1,
        "generator": "tools/stress_objects_overlay.py",
        "what": "STRESS_OBJECTS=1 overlay: world-pixel objects merged into OJZ act 1 by "
                "ojz_entity_gen.py generate --overlay (v2 step 0, C2)",
        "params": {"spacing": SPACING, "offset": OFFSET, "clearance_px": CLEARANCE_PX,
                   "live_cap": cap, "live_cap_margin": LIVE_CAP_MARGIN, "types": list(TYPES),
                   "primary_path": primary},
        "equates": equ,
        "act": {"w": act_w, "h": act_h},
        "path_fixture": {"file": "games/sonic4/test/fixtures/stress_objects.path.json",
                         "sha256": fx.get("sha256"), "paths": names},
        "candidates": len(cand),
        "canon_count": len(canon),
        "count": len(kept),
        "model": {n: model_of(objs, cams[n], equ) for n in names},
        "objects": kept,
    }


def dumps(ov: dict) -> str:
    return json.dumps(ov, sort_keys=True, indent=1) + "\n"


def per_section(objects, grid_w, section_size) -> dict:
    out = {}
    for o in objects:
        n = o["x"] // section_size + grid_w * (o["y"] // section_size)
        out[n] = out.get(n, 0) + 1
    return dict(sorted(out.items()))


# ---- the path fixture ---------------------------------------------------------------------

def fixture_from_results(paths) -> dict:
    out = {}
    for p in paths:
        r = json.loads(Path(p).read_text())
        pv = r["provenance"]
        if r.get("leg") != "run" or r.get("status") != "FINISHED":
            raise OverlayError(f"{p}: leg {r.get('leg')!r} status {r.get('status')!r}; the path "
                               "fixture is the canonical FINISHED `run` leg")
        if pv["rom"]["rom"] not in ("s4.bin", "s4.debug.bin"):
            raise OverlayError(f"{p}: ROM {pv['rom']['rom']} is not a canonical shape")
        rows = r["rows"]
        ts = [x["t"] for x in rows]
        if ts != list(range(ts[0], ts[0] + len(ts))):
            raise OverlayError(f"{p}: rows are not one per consecutive tick")
        key = f"{'debug' if pv['rom']['debug'] else 'release'}/{r['phase']}"
        out[key] = {
            "t0": ts[0], "cx": [x["cx"] for x in rows], "cy": [x["cy"] for x in rows],
            "px": [x["px"] for x in rows], "py": [x["py"] for x in rows],
            "source": {"result": Path(p).name, "rom": pv["rom"]["rom"],
                       "crc32": pv["rom"]["crc32"], "aeon_commit": pv["aeon"]["commit"],
                       "aeon_dirty_paths": pv["aeon"].get("dirty_paths"),
                       "oracle": pv["oracle"]["commit"], "status": r["status"],
                       "ticks": len(rows)},
        }
    return {"schema": 1,
            "what": "per-tick (Camera_X, Camera_Y, P1 x, P1 y) of the canonical `run` leg "
                    "(tools/leg_run.py --leg run), per shape/phase: the path the STRESS_OBJECTS "
                    "overlay keeps clear and the objheavy leg's path witness compares against",
            "paths": dict(sorted(out.items()))}


# ---- CLI ----------------------------------------------------------------------------------

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fixture")
    f.add_argument("results", nargs="+")
    f.add_argument("--out", default=str(PATH_FIXTURE))
    g = sub.add_parser("generate")
    g.add_argument("--lst", required=True)
    g.add_argument("--path", default=str(PATH_FIXTURE))
    g.add_argument("--out", default=str(OVERLAY))
    c = sub.add_parser("check")
    c.add_argument("--lst", required=True)
    c.add_argument("--entity-data", required=True)
    c.add_argument("--path", default=str(PATH_FIXTURE))
    c.add_argument("--overlay", default=str(OVERLAY))
    a = ap.parse_args(argv)
    try:
        if a.cmd == "fixture":
            fx = fixture_from_results(a.results)
            Path(a.out).write_text(json.dumps(fx, sort_keys=True, separators=(",", ":")) + "\n")
            print(f"stress_objects_overlay: fixture {sorted(fx['paths'])} -> {a.out}")
            return 0
        if a.cmd == "generate":
            equ = equates_from_listing(a.lst)
            gw, gh = act_grid()
            ov = build_overlay(load_path_fixture(a.path), canon_objects(),
                               gw * equ["SECTION_SIZE"], gh * equ["SECTION_SIZE"], equ)
            Path(a.out).write_text(dumps(ov))
            print(f"stress_objects_overlay: {ov['candidates']} candidates -> {ov['count']} kept "
                  f"(per section {per_section(ov['objects'], gw, equ['SECTION_SIZE'])}); "
                  + "; ".join(f"{n}: live max {m['live_max']}, fails {m['alloc_fails']}, "
                              f"{m['ticks_dispatched_ge_min']} ticks >= {m['dispatch_min']} "
                              "dispatched" for n, m in ov["model"].items()) + f" -> {a.out}")
            return 0
        # check
        equ = equates_from_listing(a.lst)
        ov = load_overlay(a.overlay)
        fx = load_path_fixture(a.path)
        gw, _gh = act_grid()
        objs = parse_entity_data(Path(a.entity_data).read_text(), gw, equ["SECTION_SIZE"])
    except (OverlayError, OSError, ValueError, KeyError) as e:
        print(f"stress_objects_overlay: UNMEASURABLE — {type(e).__name__}: {e}", file=sys.stderr)
        return 2
    want = ov["canon_count"] + ov["count"]
    if len(objs) != want:
        print(f"stress_objects_overlay: FAIL — {a.entity_data} holds {len(objs)} objects, the "
              f"overlay says {ov['canon_count']} canonical + {ov['count']} overlay = {want}: "
              "the re-bake did not apply the overlay", file=sys.stderr)
        return 1
    if ov.get("path_fixture", {}).get("sha256") != fx["sha256"]:
        print("stress_objects_overlay: FAIL — the overlay was generated from another path "
              f"fixture (sha256 {ov.get('path_fixture', {}).get('sha256')} != {fx['sha256']}); "
              "regenerate it", file=sys.stderr)
        return 1
    v = verdict(objs, {n: fixture_cams(e) for n, e in fx["paths"].items()}, equ)
    for n, m in v["per"].items():
        print(f"stress_objects_overlay: {n}: modelled live max {m['live_max']} (cap {v['cap']}), "
              f"alloc fails {m['alloc_fails']}, {m['ticks_dispatched_ge_min']} ticks >= "
              f"{m['dispatch_min']} dispatched (need {ld.OBJ_COVER_TICKS}) [ESTIMATED: model]")
    if not v["ok"]:
        print(f"stress_objects_overlay: FAIL — {v['why']}", file=sys.stderr)
        return 1
    print(f"stress_objects_overlay: OK — {len(objs)} objects baked, model within the cap")
    return 0


if __name__ == "__main__":
    sys.exit(main())
