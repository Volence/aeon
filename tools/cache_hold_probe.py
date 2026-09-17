#!/usr/bin/env python3
"""cache_hold_probe.py — runtime camera-art-hold count and art-page decode timing, headless.

Report 11 (docs/research/megaact-bg-streaming/11-cache-window-runtime-holds.md) is the first
user. It answers two runtime questions report 10 left DERIVED: how often the camera is held
because foreground art is not resident (`Camera_Art_Hold`, set by `art_hold_edge_check` in
engine/level/tile_cache.emp, consumed by Camera_Update in engine/level/camera.emp), and how
long one art page takes from decode start to publish.

INSTRUMENT. The Rust core through `aether_instance.AetherInstance` (the owner-ruled default
emulator; its spawn asserts the server identity and reads the whole cart back against the
file). Nothing here uses MCP. The machine is driven one video frame at a time:

  DRIVER    the camera leader's SST x_pos/y_pos are poked to (target + screen half) at the
            start of each leg, then Camera_Update steps the camera at its own per-tick cap
            (CAM_MAX_X_STEP / CAM_MAX_Y_STEP = 16 px) until it arrives. On a DEBUG build the
            leader is in free flight, so the poke holds; that is deliberate here: the hold
            path reads only the camera and the art cache, and the cap-speed camera in any
            direction is exactly the stress under test (player physics cannot sustain 16 px
            per tick vertically). What free flight cannot say anything about: the collision
            range a smaller window gives the player and objects.

  HOLDS     counted three independent ways, all printed:
              clamp_ticks   DEBUG `Dbg_Cam_Clamp_Frames` delta (Camera_Update increments it on
                            every tick it sees a hold bit) — absent on a release build;
              hold_writes   a bus WRITE watch on `Camera_Art_Hold`: nonzero values written
                            (the fill re-derives the byte every pass), from the hit log;
              hold_sampled  the byte read after every video frame (can miss a hold the next
                            fill pass already cleared; the weakest of the three).
            The watch hit log carries seq numbers; the run records `matched` and checks the
            captured hits are contiguous, so an incomplete log is visible, not silent.

  DECODE    write watches on PageIn_InFlight, PageIn_Suspended, PageIn_Saved_PC,
            PageIn_Cur_Page and Page_Table give, per page-in: decode start (InFlight set),
            each VBlank preempt (Saved_PC written by VBlank_Handler's bookmark hook), each
            resume (Suspended cleared by PageIn_Resume), completion (InFlight cleared at
            PageIn_Process.after) and publish (Page_Table[page] written with a frame id).
            Decode CPU = sum of the in-decoder spans in master-clock units / 7, with two
            DERIVED per-event corrections from the 68000 timing tables (IRQ entry to the
            Saved_PC write; Suspended clear to the rte back into the decoder). Any HBlank
            handler that fires inside a span is INCLUDED; the init bulk load (display off)
            is reported separately as the uncontaminated reference.

  FAULTS    status pc >= ErrorHandlerBlob (the fault island is the last emission) stops
            the run and is recorded; a fault is never read as a pass.

ROUTES are in camera pixels, clamped to the act by the engine. `all` sweeps the whole act
(5 horizontal rows both ways, 4 vertical columns both ways, 4 diagonals); `hot` crosses the
region around --hot-x/--hot-y repeatedly (defaults: OJZ act 1's densest windows). Legs whose
name ends in `goto` only reposition and are excluded from the totals.

Usage:
    python3 tools/cache_hold_probe.py run --rom R --lst L --out RUN.json [--route all|hot|short]
                                          [--settle N] [--pages N] [--hot-x X] [--hot-y Y]
    python3 tools/cache_hold_probe.py analyze RUN.json [RUN.json ...] [--out SUMMARY.json]
"""
import json
import os
import statistics
import sys
import time
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

SST_X_POS = 0x02
SST_Y_POS = 0x06
SCREEN_HALF_W = 160
SCREEN_HALF_H = 112
MCLK_PER_CPU_CLOCK = 7          # 68000 clock = MCLK / 7 (NTSC: 896,081 mclk = 128,012 clocks/frame)
PREEMPT_CORR_CLOCKS = 262       # DERIVED: IRQ exception 44 + movem 15 regs 128 + 5 instrs to the Saved_PC write
RESUME_CORR_CLOCKS = 170        # DERIVED: 7 move.l abs,Rn + 2 pushes + rte after the Suspended clear
STILL_QUIET_FRAMES = 20         # leg ends: camera unmoved this long with no hold/stall/queue/decode
STILL_STUCK_FRAMES = 900        # leg ends anyway: a hold lasting this long is recorded as stuck
WATCHES = ("PageIn_InFlight", "PageIn_Suspended", "PageIn_Saved_PC", "Page_Table",
           "PageIn_Cur_Page", "Camera_Art_Hold")

USAGE = """Usage:
    python3 tools/cache_hold_probe.py run --rom R --lst L --out RUN.json [--route all|hot|short] [--settle N] [--pages N] [--hot-x X] [--hot-y Y]
    python3 tools/cache_hold_probe.py analyze RUN.json [RUN.json ...] [--out SUMMARY.json]"""


def routes(name, max_x, max_y, hot_x, hot_y):
    """(leg name, (camera x, camera y), measured) in drive order."""
    H, V, D, HOT = [], [], [], []
    for i in range(5):
        y = max_y * i // 4
        H += [(f"H y={y} goto", (0, y), False), (f"H y={y} right", (max_x, y), True),
              (f"H y={y} left", (0, y), True)]
    for i in range(4):
        x = max_x * i // 3
        V += [(f"V x={x} goto", (x, 0), False), (f"V x={x} down", (x, max_y), True),
              (f"V x={x} up", (x, 0), True)]
    m = min(max_x, max_y)
    D = [("D goto", (0, 0), False), ("D down-right", (m, m), True), ("D up-left", (0, 0), True),
         ("D goto2", (max_x, 0), False), ("D down-left", (max(0, max_x - m), m), True),
         ("D up-right", (max_x, 0), True)]
    span = 1600
    for dy in (32, 80, 128, 176):
        y = min(max_y, hot_y + dy)
        HOT += [(f"HOT-H y={y} goto", (0, y), False),
                (f"HOT-H y={y} right", (min(max_x, hot_x + span), y), True),
                (f"HOT-H y={y} left", (0, y), True)]
    for dx in (-200, -40, 120):
        x = max(0, min(max_x, hot_x + dx))
        HOT += [(f"HOT-V x={x} goto", (x, hot_y + 32), False),
                (f"HOT-V x={x} down", (x, min(max_y, hot_y + span)), True),
                (f"HOT-V x={x} up", (x, hot_y + 32), True)]
    far = min(max_x, max_y, span)
    HOT += [("HOT-D goto", (0, hot_y + 32), False), ("HOT-D down-right", (far, far), True),
            ("HOT-D up-left", (0, hot_y + 32), True), ("HOT-D goto2", (far, hot_y + 32), False),
            ("HOT-D down-left", (0, far), True), ("HOT-D up-right", (far, hot_y + 32), True)]
    table = {"all": H + V + D, "hot": HOT, "short": H[:3]}
    if name not in table:
        raise SystemExit(f"unknown route {name!r}; one of {sorted(table)}")
    return table[name]


def _flag(args, name, default=None, cast=str):
    if name in args:
        i = args.index(name)
        if i + 1 >= len(args):
            print(USAGE)
            sys.exit(1)
        v = args[i + 1]
        del args[i:i + 2]
        return cast(v)
    return default


def _u(bs, o, n):
    return int.from_bytes(bs[o:o + n], "big")


async def _probe(sock, inst, opt, sym):
    from aether import BusClient
    A = {k: v & 0xFFFFFF for k, v in sym.items()}
    need = ["Camera_X", "Camera_Y", "Camera_Target", "Camera_Art_Hold", "Camera_X_Max", "Camera_Y_Max",
            "Logic_Tick", "Cache_Art_Stall", "PageIn_Queue_Count", "PageIn_Fully_Resident",
            "ErrorHandlerBlob"] + list(WATCHES)
    missing = [n for n in need if n not in A]
    if missing:
        raise SystemExit(f"UNMEASURABLE: symbols missing from {opt['lst']}: {missing}")
    raw = open(opt["rom"], "rb").read()
    out = {"tool": "cache_hold_probe", "rom": opt["rom"], "rom_crc32": f"{zlib.crc32(raw):08x}",
           "rom_bytes": len(raw), "cart_note": inst.cart_note,
           "implementation": inst.handshake.get("implementation"), "route": opt["route"],
           "settle": opt["settle"], "loadavg_start": open("/proc/loadavg").read().strip(),
           "debug_counters": "Dbg_Cam_Clamp_Frames" in A, "legs": []}
    b = BusClient(socket_path=sock, client_id="cachehold", client_name="cache_hold_probe")
    await b.connect()

    async def rd(addr, n):
        r = await b.call("emulator/read_memory", {"addr": hex(addr), "len": n})
        return bytes.fromhex(str(r["bytes"]).replace("0x", "")[:2 * n])

    async def rsym(name, n):
        return _u(await rd(A[name], n), 0, n) if name in A else None

    for name in WATCHES:
        n = opt["pages"] if name == "Page_Table" else (2 if name == "PageIn_Cur_Page" else 1)
        await b.call("emulator/watchpoint_add", {"addr": hex(A[name]), "len": n, "write": True,
                                                 "read": False, "mode": "record", "label": name,
                                                 "space": "bus"})
    hits, cursor, wstat = [], [None], {}

    async def drain():
        while True:
            p = {"limit": 500}
            if cursor[0] is not None:
                p["cursor"] = str(cursor[0])
            r = await b.call("emulator/watchpoint_hits", p)
            got = r.get("hits", [])
            for h in got:
                cursor[0] = h["seq"]
                hits.append([h["seq"], h["mclk"], h["frame"], int(str(h["addr"]).replace("0x", ""), 16),
                             int(str(h["value"]).replace("0x", ""), 16), int(str(h["pc"]).replace("0x", ""), 16)])
            wstat.update({k: r.get(k) for k in ("seen", "matched", "dropped")})
            if not r.get("truncated") and len(got) < 500:
                return

    await b.call("emulator/run_frames", {"frames": opt["settle"]})
    for _ in range(30):
        if (await rsym("Logic_Tick", 4)) >= 30:
            break
        await b.call("emulator/run_frames", {"frames": 120})
    max_x = await rsym("Camera_X_Max", 2)
    max_y = await rsym("Camera_Y_Max", 2)
    out["camera_max"] = [max_x, max_y]

    async def sample():
        s = {"cx": (await rsym("Camera_X", 4)) >> 16, "cy": (await rsym("Camera_Y", 4)) >> 16,
             "hold": await rsym("Camera_Art_Hold", 1), "stall": await rsym("Cache_Art_Stall", 2),
             "qn": await rsym("PageIn_Queue_Count", 1), "tick": await rsym("Logic_Tick", 4),
             "inflight": await rsym("PageIn_InFlight", 1), "susp": await rsym("PageIn_Suspended", 1),
             "fr": await rsym("PageIn_Fully_Resident", 1)}
        for k, n in (("clamp", "Dbg_Cam_Clamp_Frames"), ("dem", "Dbg_PageCache_Demands"),
                     ("pfx", "Dbg_PageCache_Prefetches")):
            s[k] = await rsym(n, 2)
        return s

    s0 = await sample()
    out["fully_resident"] = s0["fr"]
    await drain()
    out["hits_before_first_leg"] = len(hits)
    err = A["ErrorHandlerBlob"]
    fault, trace = None, []
    for name, (wx, wy), measured in routes(opt["route"], max_x, max_y, opt["hot_x"], opt["hot_y"]):
        tgt = await rsym("Camera_Target", 2)
        leader = (0xFF0000 | tgt) if tgt & 0x8000 else tgt
        await b.call("emulator/write_memory", {"addr": hex(leader + SST_X_POS), "value": (wx + SCREEN_HALF_W) << 16, "width": 4})
        await b.call("emulator/write_memory", {"addr": hex(leader + SST_Y_POS), "value": (wy + SCREEN_HALF_H) << 16, "width": 4})
        first = await sample()
        st = await b.call("emulator/status", {})
        leg = {"name": name, "measured": measured, "target": [wx, wy], "start": [first["cx"], first["cy"]],
               "frame0": st.get("frame"), "frames": 0, "hold_sampled": 0, "hold_where": []}
        prev, still = first, 0
        for i in range(opt["max_frames"]):
            await b.call("emulator/run_frames", {"frames": 1})
            s = await sample()
            leg["frames"] += 1
            if s["hold"]:
                leg["hold_sampled"] += 1
                leg["hold_where"].append([s["cx"], s["cy"], s["hold"], s["tick"]])
            trace.append([len(out["legs"]), s["tick"], s["cx"], s["cy"], s["hold"], s["stall"], s["inflight"], s["susp"], s["qn"]])
            still = still + 1 if (s["cx"], s["cy"]) == (prev["cx"], prev["cy"]) else 0
            prev = s
            if i % 120 == 0:
                st = await b.call("emulator/status", {})
                if int(str(st["pc"]), 16) >= err:
                    fault = {"leg": name, "pc": st["pc"], "symbol": st.get("symbolAtPc"), "camera": [s["cx"], s["cy"]]}
                    break
                await drain()
            quiet = not s["hold"] and not s["stall"] and not s["qn"] and not s["inflight"] and not s["susp"]
            if (still >= STILL_QUIET_FRAMES and quiet) or still > STILL_STUCK_FRAMES:
                break
        st = await b.call("emulator/status", {})
        if not fault and int(str(st["pc"]), 16) >= err:
            fault = {"leg": name, "pc": st["pc"], "symbol": st.get("symbolAtPc"), "camera": [prev["cx"], prev["cy"]]}
        await drain()
        leg.update({"frame1": st.get("frame"), "end": [prev["cx"], prev["cy"]], "ticks": prev["tick"] - first["tick"],
                    "stuck": still > STILL_STUCK_FRAMES})
        for k in ("clamp", "dem", "pfx"):
            leg[{"clamp": "clamp_ticks", "dem": "demands", "pfx": "prefetches"}[k]] = (
                (prev[k] - first[k]) & 0xFFFF if first[k] is not None else None)
        out["legs"].append(leg)
        print(f"  {name:22} frames {leg['frames']:5} ticks {leg['ticks']:4} clamp_ticks {leg['clamp_ticks']} "
              f"sampled {leg['hold_sampled']} demands {leg['demands']} prefetches {leg['prefetches']}", flush=True)
        if fault:
            break
    out["fault"] = fault
    out["watch"] = wstat
    out["hits_contiguous"] = all(b2[0] == a2[0] + 1 for a2, b2 in zip(hits, hits[1:])) and (not hits or hits[0][0] == 0)
    out["hits_cols"] = ["seq", "mclk", "frame", "addr", "value", "pc"]
    out["hits"] = hits
    out["trace_cols"] = ["leg", "tick", "cx", "cy", "hold", "stall", "inflight", "susp", "qn"]
    out["trace"] = trace
    out["symbols"] = {n: A[n] for n in WATCHES}
    out["loadavg_end"] = open("/proc/loadavg").read().strip()
    await b.close()
    return out


def run_probe(args):
    import asyncio
    from aether_instance import AetherInstance
    from raster_cost_probe import parse_lst
    opt = {"rom": _flag(args, "--rom"), "lst": _flag(args, "--lst"), "out": _flag(args, "--out"),
           "route": _flag(args, "--route", "all"), "settle": _flag(args, "--settle", 240, int),
           "pages": _flag(args, "--pages", 16, int), "max_frames": _flag(args, "--max-frames", 3000, int),
           "hot_x": _flag(args, "--hot-x", 760, int), "hot_y": _flag(args, "--hot-y", 0, int)}
    if args or not (opt["rom"] and opt["lst"] and opt["out"]):
        print(USAGE)
        sys.exit(1)
    opt["rom"], opt["lst"] = os.path.abspath(opt["rom"]), os.path.abspath(opt["lst"])
    sym = parse_lst(opt["lst"])
    t0 = time.time()
    inst = AetherInstance(opt["rom"], symbols=opt["lst"])
    try:
        sock = inst.start()
        res = asyncio.run(_probe(sock, inst, opt, sym))
    finally:
        inst.reap()
    res["wall_s"] = round(time.time() - t0, 1)
    with open(opt["out"], "w") as f:
        json.dump(res, f)
    s = summarize(res)
    print(f"{os.path.basename(opt['out'])}: frames {s['frames']} ticks {s['ticks']} clamp_ticks {s['clamp_ticks']} "
          f"hold_writes {s['hold_writes']} hold_sampled {s['hold_sampled']} demands {s['demands']} "
          f"fault {s['fault']} fully_resident {s['fully_resident']} hits_contiguous {s['hits_contiguous']} "
          f"wall {res['wall_s']}s finished=ok")
    return 2 if res["fault"] or not res["hits_contiguous"] else 0


def _stats(v):
    if not v:
        return None
    return {"n": len(v), "min": min(v), "median": statistics.median(v), "mean": round(statistics.mean(v), 1), "max": max(v)}


def summarize(d):
    S = d["symbols"]
    measured = [l for l in d["legs"] if l["measured"]]
    tot = lambda k: (None if any(l.get(k) is None for l in measured) else sum(l[k] for l in measured))
    legs_by_frame = [(l["frame0"], l["frame1"], l) for l in d["legs"]]

    def leg_of(frame):
        for f0, f1, l in legs_by_frame:
            if f0 is not None and f1 is not None and f0 <= frame <= f1:
                return l
        return None

    hold_w = {}
    for seq, mclk, frame, addr, val, pc in d["hits"]:
        if addr == S["Camera_Art_Hold"] and val:
            l = leg_of(frame)
            if l is not None:
                hold_w[l["name"]] = hold_w.get(l["name"], 0) + 1
    res = {"rom_crc32": d["rom_crc32"], "route": d["route"], "settle": d["settle"], "fault": d["fault"],
           "fully_resident": d["fully_resident"], "hits_contiguous": d["hits_contiguous"],
           "watch": d.get("watch"), "legs": len(d["legs"]), "legs_measured": len(measured),
           "frames": tot("frames"), "ticks": tot("ticks"), "clamp_ticks": tot("clamp_ticks"),
           "hold_sampled": tot("hold_sampled"),
           "hold_writes": sum(v for k, v in hold_w.items() if any(l["name"] == k and l["measured"] for l in d["legs"])),
           "demands": tot("demands"), "prefetches": tot("prefetches"),
           "stuck_legs": [l["name"] for l in d["legs"] if l.get("stuck")],
           "holds_by_leg": [{"leg": l["name"], "clamp_ticks": l.get("clamp_ticks"), "hold_writes": hold_w.get(l["name"], 0),
                             "where_sampled": l["hold_where"][:8]}
                            for l in d["legs"] if l.get("clamp_ticks") or hold_w.get(l["name"]) or l["hold_sampled"]]}
    # decode timing from the watch log
    first_leg = d["legs"][0]["frame0"] if d["legs"] else None
    dec, cur, op = [], None, None
    for seq, mclk, frame, addr, val, pc in d["hits"]:
        if addr == S["PageIn_Cur_Page"]:
            cur = val
        elif addr == S["PageIn_InFlight"] and val:
            op = {"page": cur, "start_frame": frame, "seg": mclk, "clocks": 0.0, "preempts": 0,
                  "phase": "init" if first_leg is None or frame < first_leg else "motion"}
        elif addr == S["PageIn_Saved_PC"] and op and op["seg"] is not None:
            op["clocks"] += (mclk - op["seg"]) / MCLK_PER_CPU_CLOCK - PREEMPT_CORR_CLOCKS
            op["seg"] = None
            op["preempts"] += 1
        elif addr == S["PageIn_Suspended"] and not val and op and op["seg"] is None:
            op["seg"] = mclk + RESUME_CORR_CLOCKS * MCLK_PER_CPU_CLOCK
        elif addr == S["PageIn_InFlight"] and not val and op:
            if op["seg"] is not None:
                op["clocks"] += (mclk - op["seg"]) / MCLK_PER_CPU_CLOCK
                op["end_frame"] = frame
                dec.append(op)
            op = None
        elif S["Page_Table"] <= addr < S["Page_Table"] + 256 and val != 0xFF:
            for x in reversed(dec):
                if x["page"] == addr - S["Page_Table"] and "publish_frame" not in x:
                    x["publish_frame"] = frame
                    break
    for x in dec:
        x.pop("seg")
        x["clocks"] = round(x["clocks"])
        if "publish_frame" in x:
            x["start_to_publish_frames"] = x["publish_frame"] - x["start_frame"]
    for ph in ("init", "motion"):
        rows = [x for x in dec if x["phase"] == ph]
        res[f"decode_{ph}"] = {"count": len(rows), "clocks": _stats([x["clocks"] for x in rows]),
                               "preempts": _stats([x["preempts"] for x in rows]),
                               "start_to_publish_frames": _stats([x["start_to_publish_frames"] for x in rows if "start_to_publish_frames" in x]),
                               "unpublished": sum(1 for x in rows if "publish_frame" not in x)}
    res["decodes"] = dec
    return res


def analyze_runs(args):
    out = _flag(args, "--out")
    if not args:
        print(USAGE)
        sys.exit(1)
    rows = []
    for p in args:
        with open(p) as f:
            s = summarize(json.load(f))
        s["run"] = os.path.basename(p)
        rows.append(s)
        print(f"{s['run']}: route {s['route']} settle {s['settle']} frames {s['frames']} ticks {s['ticks']} "
              f"clamp_ticks {s['clamp_ticks']} hold_writes {s['hold_writes']} demands {s['demands']} fault {s['fault']} "
              f"decode_motion n={s['decode_motion']['count']} clocks {s['decode_motion']['clocks']} "
              f"publish {s['decode_motion']['start_to_publish_frames']}")
    if out:
        with open(out, "w") as f:
            json.dump(rows, f, indent=1)
    return 0


MODES = {
    "run": run_probe,
    "analyze": analyze_runs,
}


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    handler = MODES.get(args[0] if args else None)
    if handler is None:
        print(USAGE)
        sys.exit(1)
    return handler(args[1:])


if __name__ == "__main__":
    sys.exit(main())
