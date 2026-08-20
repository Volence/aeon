#!/usr/bin/env python3
"""staging_lifetime_timeline — DIRECT measurement of dead block-tier speculation.

WHY THIS EXISTS. `docs/benchmarks/streaming/CHOKE-DIAGNOSIS.md` §3 makes the arc's
central claim by ARITHMETIC, not by observation:

    "Eviction is strict round-robin over BLOCK_STAGE_SLOTS = 16, so a staged block
     survives exactly 16 claims, i.e. 16 / claim_rate ticks. At the measured 4.53
     claims/tick that is 3.53 ticks ... the prefetch lead is 8 ticks ... so nothing
     survives to its use."

That is slots ÷ rate — an inference. The packet says so itself and books the fix
(§9(b)6): *"watch Block_Stage_Keys slot writes (stage instant) and the
FindStagedBlock hit path (use instant). The difference IS the staged-but-evicted-
before-use waste ... worth building before the fix parcel, so F2's success criterion
is a measured lifetime rather than a proxy."*

This is that instrument. It composes a per-speculation record — staged-at,
used-at / evicted-at, by-what — from mclk-stamped watch hits on oracle-aether
(CR-12: every hit carries `{frame, mclk, seq, pc, symbol, value, old, via}`; all four
target cells are WORK RAM, i.e. `space: bus` hits off the 68000 bus event stream).

    NOT a profiler. It reads no cycle rows and cannot: oracle-aether has no
    profiler. Cycle costs stay with tools/streaming_choke_probe.py on old oracle.
    This tool answers a question that has no cycle in it — *did the speculation
    land?* — and the two are meant to be read side by side.

------------------------------------------------------------------------------
THE COMPOSITION — four watches, and why each one is exact

  W_stage   WRITE  Block_Stage_Keys  (BLOCK_STAGE_SLOTS x 4 B)
        The claim instant. `addr` gives the slot; `value` is the new key
        (sec_x<<24 | sec_y<<16 | block_index); `old` is the key this claim EVICTED.
        Written only by TileCache_DecompressBlock's slot claim and by
        TileCache_InvalidateStaging (act init, never inside a sample) — asserted
        live, per hit, from the hit's own `symbol`.

  W_use     READ   Block_Stage_Ptrs  (BLOCK_STAGE_SLOTS x 4 B)
        The use instant. This table is WRITTEN by DecompressBlock (three arms) and
        READ by exactly one instruction in the whole ROM: the `movea.l (a1,d4.w),a1`
        on TileCache_FindStagedBlock's `.hit` arm. So a READ hit here IS a staged-
        cache hit on that slot, and the slot index falls straight out of `addr`.
        Also asserted live from `symbol`.

  W_phase   WRITE  Cache_Pfx_Row_Target (2 B), value $FFFF only
        The phase marker, and the reason this tool can tell a DEMAND claim from a
        SPECULATIVE one without touching the engine. Tile_Cache_Fill stores $FFFF
        here exactly once per fill pass, at the head of the speculation tail
        (tile_cache.emp, `.v_top_done`), immediately before the row/col/corner
        scans. Everything the pass did BEFORE that store is demand fill; everything
        after it is speculation. (Tile_Cache_Init writes the same $FFFF, which is
        why the `symbol` assertion below pins the writer to Tile_Cache_Fill — init
        does not run inside a sample, and if it ever does, the tool says so.)

  W_tick    WRITE  Logic_Tick (4 B)
        The clock. `addq.l #1, Logic_Tick` is the first thing GameLoop does after
        VSync_Wait, so hits between two of these belong to one LOGIC TICK — the
        arc's unit. Lifetimes are reported in ticks (and in mclk, for burst shape).

`seq` is the global monotone order across all four watches, and it is what makes the
composition possible at all: the phase of an event is its position relative to the
marker, and the lifetime of a claim is the seq-distance to the write that evicts it.

------------------------------------------------------------------------------
WHAT A "LANDED" SPECULATION IS — the distinction that decides the number

A speculative claim is CONSUMED only when the demand fill later arrives at that block
and finds it staged. The prefetch scans themselves probe with FindStagedBlock and HIT
on blocks they staged earlier — those hits read Block_Stage_Ptrs too, and counting
them as uses would report a dead speculation as a live one. So a use only counts when
it happens in the DEMAND phase of some tick:

    SPEC claim LANDED  := evicted (or still resident) with >=1 DEMAND-phase use
    SPEC claim DEAD    := evicted with zero demand-phase uses

Demand claims are not graded this way and never can be: TileCache_FillColumn /
FillRow use DecompressBlock's returned `a1` directly and never re-probe, so a demand
claim's first (and often only) consumption leaves no read hit at all. Its
"immediately used" is true by construction. This tool grades SPECULATION.

------------------------------------------------------------------------------
CENSORING, stated rather than hidden. Claims still resident when the window closes
have not been evicted yet, so their lifetime is a lower bound. They are reported in
their own column (`open`) and are EXCLUDED from the dead/landed rates, which are
computed over evicted claims only. A window long enough that `open` is a small
fraction of claims is what makes the rate trustworthy; the default 31-frame sample
leaves `open` <= BLOCK_STAGE_SLOTS by construction.

------------------------------------------------------------------------------
SOURCE ASSERTIONS (probe convention — the tool must fail rather than mislead)

 1. Every W_use hit's `symbol` is TileCache_FindStagedBlock. If any other site ever
    reads Block_Stage_Ptrs, "read = staged hit" is false and every number here is.
 2. Every W_stage hit's `symbol` is TileCache_DecompressBlock (or
    TileCache_InvalidateStaging, which then also fails #5).
 3. Every W_phase hit's `symbol` is Tile_Cache_Fill, and exactly <=1 marker per tick.
 4. `dropped == 0` on every hits page — a dropped hit silently truncates a lifetime.
 5. The W_stage hit count equals the `Block_Stage_Gen` delta over the same window.
    That counter is the packet's own exact decompress count, so this is the timeline
    agreeing with the instrument the packet was built on.
 6. `PageIn_Fully_Resident` true and `Camera_Art_Hold` 0 — the same regime the
    choke packet measured; a false reading here means the page tier is engaged and
    the block-tier story is not the whole story.

States, settle, lead and the pokes are byte-identical to
tools/streaming_choke_probe.py's, so a row here lines up with a row there.

Usage:
    python3 tools/staging_lifetime_timeline.py --rom s4.debug.bin --lst s4.debug.lst
    python3 tools/staging_lifetime_timeline.py --state maxdiag --repeat 3 --events
"""
import argparse
import asyncio
import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, "/home/volence/sonic_hacks/empyrean/clients/python")
sys.path.insert(0, str(Path(__file__).resolve().parent))
from aether import BusClient                # noqa: E402
from raster_cost_probe import parse_lst     # noqa: E402

SERVER = "/home/volence/sonic_hacks/oracle-next/target/release/oracle-aether"

# ---- camera states: byte-identical to streaming_choke_probe's ---------------
SST_X_POS = 0x02
SST_Y_POS = 0x06
DIAG_AHEAD_X = 2000
DIAG_AHEAD_Y = 1400
STATES = {
    "idle":    (0, 0),
    "maxdiag": (DIAG_AHEAD_X, DIAG_AHEAD_Y),
    "right":   (DIAG_AHEAD_X, 0),
    "down":    (0, DIAG_AHEAD_Y),
}

PHASE_MARKER = 0xFFFF
EMPTY_KEY = 0xFFFFFFFF


class ProbeError(RuntimeError):
    pass


class Server:
    """One oracle-aether process, one ROM. Fresh per repeat — every run from reset."""

    def __init__(self, rom: str, lst: str, sock: str):
        self.rom, self.lst, self.sock = rom, lst, sock
        self.proc = None
        self.client = None

    async def __aenter__(self):
        if os.path.exists(self.sock):
            os.unlink(self.sock)
        self.proc = subprocess.Popen(
            [SERVER, self.rom, "--socket", self.sock, "--symbols", self.lst, "--no-pace"],
            stdout=open("/tmp/f2-aether.log","w"), stderr=subprocess.STDOUT)
        for _ in range(200):
            if os.path.exists(self.sock):
                break
            time.sleep(0.05)
        else:
            raise ProbeError(f"oracle-aether never created {self.sock}")
        self.client = BusClient(self.sock, client_id="stagelife",
                                client_name="staging_lifetime_timeline")
        await self.client.connect()
        for m in ("emulator/watchpoint_add", "emulator/watchpoint_hits",
                  "emulator/watchpoint_clear", "emulator/run_frames",
                  "emulator/read_memory", "emulator/write_memory", "emulator/reset"):
            if not self.client.supports(m):
                raise ProbeError(f"the server does not advertise `{m}`")
        return self

    async def __aexit__(self, *exc):
        try:
            if self.client:
                await self.client.close()
        finally:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except Exception:
                self.proc.kill()


async def _c(b, method, params=None, timeout=300.0):
    return await asyncio.wait_for(b.call(method, params or {}), timeout=timeout)


async def _read(b, addr, n):
    r = await _c(b, "emulator/read_memory", {"addr": hex(addr & 0xFFFFFF), "len": n})
    return int(r["bytes"].removeprefix("0x").removeprefix("0X")[:n * 2], 16)


# ---- hit collection ---------------------------------------------------------

async def _drain(b):
    """Every hit the ring holds, paged by cursor. Raises if the ring dropped any:
    a dropped hit is a lifetime silently truncated, not a missing row."""
    hits, cursor, total_dropped = [], None, 0
    while True:
        p = {"limit": 256}
        if cursor:
            p["cursor"] = cursor
        r = await _c(b, "emulator/watchpoint_hits", p)
        total_dropped = max(total_dropped, int(r.get("dropped", 0)))
        hits.extend(r.get("hits", []))
        cursor = r.get("cursor")
        if not cursor or not r.get("truncated"):
            break
    if total_dropped:
        raise ProbeError(
            f"the watch ring DROPPED {total_dropped} hits — the timeline is truncated "
            f"and every lifetime below it is wrong. Shorten --sample or raise the ring.")
    return hits


def _as_int(v, default=None):
    if v is None:
        return default
    if isinstance(v, int):
        return v
    s = str(v).strip()
    if s.startswith("$"):
        return int(s[1:], 16)
    if s.lower().startswith("0x"):
        return int(s, 16)
    try:
        return int(s)
    except ValueError:
        return default


# ---- the timeline itself ----------------------------------------------------

def _proc_of(symbol: str) -> str:
    """`TileCache_FindStagedBlock.hit+$E` -> `TileCache_FindStagedBlock`.

    A hit's `symbol` resolves to the NEAREST label, which in this codebase is a
    proc-local `.label`; the owning proc is the part before the first `.`/`+`.
    """
    s = symbol or ""
    for cut in (".", "+"):
        i = s.find(cut)
        if i >= 0:
            s = s[:i]
    return s


def compose(hits, sym, slots, strict=True):
    """seq-ordered walk -> one record per staging claim.

    Returns (records, meta). A record is
        {slot, key, tick, phase, mclk, evicted_tick, evicted_mclk, evicted_by,
         uses:[{tick, phase, mclk}], open:bool}

    WORD PAIRING, which is load-bearing. The 68000 has no 32-bit bus cycle: every
    `move.l`/`addq.l` against these tables emits TWO word accesses, so a single
    staging claim appears as two hits at `base+4s` and `base+4s+2` sharing one `pc`.
    Counting both would double every rate in the report. The event is taken on the
    4-ALIGNED hit and its `value`/`old` completed from the +2 sibling (matched on
    the same pc and adjacent seq), so one long access is one event and the long's
    full 32-bit key is recovered.
    """
    keys_base = sym["Block_Stage_Keys"] & 0xFFFFFF
    ptrs_base = sym["Block_Stage_Ptrs"] & 0xFFFFFF
    tick_addr = sym["Logic_Tick"] & 0xFFFFFF
    mark_addr = sym["Cache_Pfx_Row_Target"] & 0xFFFFFF

    raw = []
    for h in hits:
        addr = _as_int(h.get("addr"))
        if addr is None:
            continue
        raw.append({
            "addr": addr & 0xFFFFFF,
            "seq": _as_int(h.get("seq"), 0),
            "mclk": _as_int(h.get("mclk"), 0),
            "frame": _as_int(h.get("frame"), 0),
            "value": _as_int(h.get("value"), 0),
            "old": _as_int(h.get("old")),
            "sym": _proc_of(h.get("symbol") or ""),
            "pc": _as_int(h.get("pc")),
            "op": (h.get("op") or "").lower(),
        })
    raw.sort(key=lambda r: r["seq"])

    def sibling(i, want_addr):
        """The +2 half of the same long access: same pc, adjacent seq."""
        for j in (i + 1, i - 1):
            if 0 <= j < len(raw):
                s = raw[j]
                if s["addr"] == want_addr and s["pc"] == raw[i]["pc"]:
                    return s
        return None

    ev = []
    bad_sym = []
    pair_misses = 0
    for i, h in enumerate(raw):
        addr = h["addr"]
        if keys_base <= addr < keys_base + slots * 4:
            if (addr - keys_base) % 4:
                continue                       # the low half; the aligned hit is the event
            if strict and h["sym"] != "TileCache_DecompressBlock":
                bad_sym.append(("stage", h["sym"], hex(addr), h["pc"]))
            lo = sibling(i, addr + 2)
            if lo is None:
                pair_misses += 1
            key = ((h["value"] & 0xFFFF) << 16) | ((lo["value"] & 0xFFFF) if lo else 0)
            old = None
            if h["old"] is not None:
                old = ((h["old"] & 0xFFFF) << 16) | (
                    (lo["old"] & 0xFFFF) if (lo and lo["old"] is not None) else 0)
            ev.append(("stage", h["seq"], h["mclk"], h["frame"],
                       (addr - keys_base) // 4, key, old))
        elif ptrs_base <= addr < ptrs_base + slots * 4:
            if h["op"] and "r" not in h["op"]:
                continue                       # a WRITE to Ptrs is DecompressBlock's own
            if (addr - ptrs_base) % 4:
                continue
            if strict and h["sym"] != "TileCache_FindStagedBlock":
                bad_sym.append(("use", h["sym"], hex(addr), h["pc"]))
            ev.append(("use", h["seq"], h["mclk"], h["frame"],
                       (addr - ptrs_base) // 4, h["value"], None))
        elif addr == mark_addr:
            if (h["value"] & 0xFFFF) != PHASE_MARKER:
                continue                       # the real target store, not the marker
            if strict and h["sym"] != "Tile_Cache_Fill":
                bad_sym.append(("phase", h["sym"], hex(addr), h["pc"]))
            ev.append(("phase", h["seq"], h["mclk"], h["frame"], -1, h["value"], None))
        elif addr == tick_addr:
            if (addr - tick_addr) % 4:
                continue
            lo = sibling(i, addr + 2)
            val = ((h["value"] & 0xFFFF) << 16) | ((lo["value"] & 0xFFFF) if lo else 0)
            ev.append(("tick", h["seq"], h["mclk"], h["frame"], -1, val, None))

    if bad_sym:
        raise ProbeError(
            "SOURCE ASSERTION FAILED — a watched cell was touched by a site this tool "
            "does not model, so its meaning is not what the docstring claims:\n  "
            + "\n  ".join(f"{k}: symbol={s!r} addr={a} pc={p}" for k, s, a, p in bad_sym[:12]))
    if pair_misses:
        raise ProbeError(
            f"{pair_misses} staging-key writes had no +2 sibling hit — the word-pairing "
            f"assumption is wrong on this server and every key/rate below it is wrong")

    ev.sort(key=lambda e: e[1])

    live = {}          # slot -> record
    recs = []
    tick = None
    phase = "demand"
    markers_this_tick = 0
    marker_violations = 0
    ticks_seen = []
    for kind, seq, mclk, frame, slot, val, old in ev:
        if kind == "tick":
            tick = val
            ticks_seen.append(val)
            phase = "demand"
            markers_this_tick = 0
            continue
        if kind == "phase":
            markers_this_tick += 1
            if markers_this_tick > 1:
                marker_violations += 1
            phase = "spec"
            continue
        if kind == "stage":
            prev = live.pop(slot, None)
            if prev is not None:
                prev["evicted_tick"] = tick
                prev["evicted_mclk"] = mclk
                prev["evicted_by"] = phase
                prev["open"] = False
                # the evicted key the engine itself reported, as a cross-check
                prev["evicted_old_key"] = old
            rec = {"slot": slot, "key": val, "tick": tick, "phase": phase,
                   "mclk": mclk, "seq": seq, "uses": [], "open": True,
                   "evicted_tick": None, "evicted_mclk": None, "evicted_by": None,
                   "evicted_old_key": None}
            live[slot] = rec
            recs.append(rec)
            continue
        if kind == "use":
            rec = live.get(slot)
            if rec is not None:
                rec["uses"].append({"tick": tick, "phase": phase, "mclk": mclk})
    meta = {"marker_violations": marker_violations,
            "ticks": len(ticks_seen),
            "tick_first": ticks_seen[0] if ticks_seen else None,
            "tick_last": ticks_seen[-1] if ticks_seen else None,
            "events": len(ev)}
    return recs, meta


def grade(recs):
    """The verdict table. Speculation is graded; demand is only counted."""
    out = {
        "claims": len(recs),
        "demand": 0, "spec": 0,
        "spec_evicted": 0, "spec_landed": 0, "spec_dead": 0, "spec_open": 0,
        "demand_evicted": 0, "demand_reused": 0, "demand_open": 0,
        "life_spec": [], "life_demand": [], "ttu_spec": [],
    }
    for r in recs:
        is_spec = r["phase"] == "spec"
        out["spec" if is_spec else "demand"] += 1
        demand_uses = [u for u in r["uses"] if u["phase"] == "demand"]
        if r["open"]:
            out["spec_open" if is_spec else "demand_open"] += 1
            continue
        life = None
        if r["evicted_tick"] is not None and r["tick"] is not None:
            life = r["evicted_tick"] - r["tick"]
        if is_spec:
            out["spec_evicted"] += 1
            if demand_uses:
                out["spec_landed"] += 1
                if demand_uses[0]["tick"] is not None and r["tick"] is not None:
                    out["ttu_spec"].append(demand_uses[0]["tick"] - r["tick"])
            else:
                out["spec_dead"] += 1
            if life is not None:
                out["life_spec"].append(life)
        else:
            out["demand_evicted"] += 1
            if demand_uses:
                out["demand_reused"] += 1
            if life is not None:
                out["life_demand"].append(life)
    return out


def _mean(xs):
    return (sum(xs) / len(xs)) if xs else float("nan")


# ---- one run ----------------------------------------------------------------

async def one(b, sym, state, settle, lead, sample, slots, strict):
    ax, ay = STATES[state]
    await _c(b, "emulator/reset", {"wait": True, "run": False})
    await _c(b, "emulator/run_frames", {"frames": settle})
    if ax or ay:
        tgt = await _read(b, sym["Camera_Target"], 2)
        leader = 0xFF0000 | tgt if tgt & 0x8000 else tgt
        cam_x = (await _read(b, sym["Camera_X"], 4)) >> 16
        cam_y = (await _read(b, sym["Camera_Y"], 4)) >> 16
        if ax:
            await _c(b, "emulator/write_memory",
                     {"addr": hex((leader + SST_X_POS) & 0xFFFFFF),
                      "value": (cam_x + ax) << 16, "width": 4})
        if ay:
            await _c(b, "emulator/write_memory",
                     {"addr": hex((leader + SST_Y_POS) & 0xFFFFFF),
                      "value": (cam_y + ay) << 16, "width": 4})
        await _c(b, "emulator/run_frames", {"frames": lead})

    resident = await _read(b, sym["PageIn_Fully_Resident"], 1)
    hold = await _read(b, sym["Camera_Art_Hold"], 1)
    gen0 = await _read(b, sym["Block_Stage_Gen"], 2)
    tick0 = await _read(b, sym["Logic_Tick"], 4)
    frame0 = await _read(b, sym["Frame_Counter"], 2)
    camx0 = await _read(b, sym["Camera_X"], 4)
    camy0 = await _read(b, sym["Camera_Y"], 4)

    await _c(b, "emulator/watchpoint_clear", {"all": True})
    await _c(b, "emulator/watchpoint_add",
             {"space": "bus", "addr": hex(sym["Block_Stage_Keys"]), "len": slots * 4,
              "write": True, "read": False, "label": "stage"})
    await _c(b, "emulator/watchpoint_add",
             {"space": "bus", "addr": hex(sym["Block_Stage_Ptrs"]), "len": slots * 4,
              "write": False, "read": True, "label": "use"})
    await _c(b, "emulator/watchpoint_add",
             {"space": "bus", "addr": hex(sym["Cache_Pfx_Row_Target"]), "len": 2,
              "write": True, "read": False, "label": "phase"})
    await _c(b, "emulator/watchpoint_add",
             {"space": "bus", "addr": hex(sym["Logic_Tick"]), "len": 4,
              "write": True, "read": False, "label": "tick"})

    await _c(b, "emulator/run_frames", {"frames": sample})
    hits = await _drain(b)
    await _c(b, "emulator/watchpoint_clear", {"all": True})

    gen1 = await _read(b, sym["Block_Stage_Gen"], 2)
    tick1 = await _read(b, sym["Logic_Tick"], 4)
    frame1 = await _read(b, sym["Frame_Counter"], 2)
    camx1 = await _read(b, sym["Camera_X"], 4)
    camy1 = await _read(b, sym["Camera_Y"], 4)

    recs, meta = compose(hits, sym, slots, strict=strict)
    g = grade(recs)

    d_gen = (gen1 - gen0) & 0xFFFF
    d_tick = tick1 - tick0
    d_frame = (frame1 - frame0) & 0xFFFF
    problems = []
    if not resident:
        problems.append("PageIn_Fully_Resident is FALSE — the page tier is live; the "
                        "block-tier reading below is not the whole story")
    if hold:
        problems.append(f"Camera_Art_Hold = {hold} — the camera was soft-clamped in-window")
    if meta["marker_violations"]:
        problems.append(f"{meta['marker_violations']} ticks carried MORE THAN ONE phase "
                        f"marker — the demand/spec split is not what this tool models")
    # assertion 5: the timeline's claim count IS the packet's exact decompress count
    if g["claims"] != d_gen:
        problems.append(f"claim count {g['claims']} != Block_Stage_Gen delta {d_gen} — "
                        f"the timeline and the engine's own exact counter disagree")
    return {
        "state": state, "recs": recs, "meta": meta, "grade": g,
        "ticks": d_tick, "frames": d_frame,
        "frames_per_tick": (d_frame / d_tick) if d_tick else float("nan"),
        "dx": (camx1 - camx0) / 65536.0, "dy": (camy1 - camy0) / 65536.0,
        "gen_delta": d_gen, "resident": resident, "hold": hold,
        "hits": len(hits), "problems": problems,
    }


def report(state, runs, slots, lead_ticks):
    r0 = runs[0]
    g = r0["grade"]
    t = r0["ticks"] or 1
    print(f"== state {state}   {r0['frames']} frames / {r0['ticks']} ticks = "
          f"{r0['frames_per_tick']:.3f} frames/tick   dx {r0['dx']:.0f} dy {r0['dy']:.0f} px"
          f"   resident {r0['resident']}   hold {r0['hold']}   watch hits {r0['hits']}")
    fpts = [x["frames_per_tick"] for x in runs]
    dead = [x["grade"]["spec_dead"] / (x["ticks"] or 1) for x in runs]
    print(f"   across {len(runs)} boots: frames/tick {[round(x, 3) for x in fpts]} "
          f"spread {max(fpts) - min(fpts):.3f}   "
          f"dead-spec/tick {[round(x, 3) for x in dead]} spread {max(dead) - min(dead):.3f}")
    print(f"   claims {g['claims']} over {r0['ticks']} ticks = {g['claims'] / t:.2f}/tick"
          f"   (Block_Stage_Gen delta {r0['gen_delta']} — must match)")
    print(f"   DEMAND claims {g['demand']} = {g['demand'] / t:.2f}/tick"
          f"   SPECULATIVE claims {g['spec']} = {g['spec'] / t:.2f}/tick")
    if g["spec"]:
        ev = g["spec_evicted"] or 1
        print(f"   SPEC graded: evicted-in-window {g['spec_evicted']}  "
              f"LANDED {g['spec_landed']} ({100 * g['spec_landed'] / ev:.1f}%)  "
              f"DEAD {g['spec_dead']} ({100 * g['spec_dead'] / ev:.1f}%)  "
              f"still-resident (censored, excluded) {g['spec_open']}")
        print(f"   DEAD SPECULATIONS PER TICK: {g['spec_dead'] / t:.2f}")
        print(f"   measured SPEC residency (stage->evict): mean {_mean(g['life_spec']):.2f} ticks"
              f"   n={len(g['life_spec'])}"
              f"   vs the {lead_ticks}-tick prefetch lead"
              f"   [inference was {slots}/claim_rate]")
        if g["ttu_spec"]:
            print(f"   landed speculations' time-to-use: mean {_mean(g['ttu_spec']):.2f} ticks"
                  f"   n={len(g['ttu_spec'])}")
    else:
        print("   SPEC claims: NONE in this window (nothing to grade)")
    print(f"   DEMAND claims: evicted {g['demand_evicted']}, of which re-used before "
          f"eviction {g['demand_reused']}; still resident {g['demand_open']}"
          f"   mean residency {_mean(g['life_demand']):.2f} ticks")
    for p in r0["problems"]:
        print(f"   !! {p}")
    print()


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--rom", default="s4.debug.bin")
    ap.add_argument("--lst", default="s4.debug.lst")
    ap.add_argument("--settle", type=int, default=180)
    ap.add_argument("--lead", type=int, default=24)
    ap.add_argument("--sample", type=int, default=31)
    ap.add_argument("--repeat", type=int, default=1)
    ap.add_argument("--state", default="maxdiag,right,down")
    ap.add_argument("--slots", type=int, default=0,
                    help="BLOCK_STAGE_SLOTS; 0 = read it out of engine/system/constants.emp")
    ap.add_argument("--lead-ticks", type=int, default=8,
                    help="the prefetch lead the packet derives (block 16 tiles / 2 tiles per tick)")
    ap.add_argument("--sock", default="/tmp/aeon-staging-lifetime.sock")
    ap.add_argument("--events", action="store_true", help="dump every composed record")
    ap.add_argument("--json", default="")
    ap.add_argument("--no-strict", action="store_true",
                    help="downgrade the per-hit source assertions (diagnosis only)")
    args = ap.parse_args()

    rom = str(Path(args.rom).resolve())
    lst = str(Path(args.lst).resolve())
    sym = parse_lst(lst)
    slots = args.slots
    if not slots:
        txt = (Path(__file__).resolve().parent.parent
               / "engine/system/constants.emp").read_text()
        import re
        m = re.search(r"^\s*(?:pub\s+)?const\s+BLOCK_STAGE_SLOTS\s*=\s*(\d+)", txt, re.M)
        if not m:
            print("cannot find BLOCK_STAGE_SLOTS in engine/system/constants.emp; pass --slots",
                  file=sys.stderr)
            return 3
        slots = int(m.group(1))

    need = ["Block_Stage_Keys", "Block_Stage_Ptrs", "Block_Stage_Gen", "Logic_Tick",
            "Cache_Pfx_Row_Target", "Camera_X", "Camera_Y", "Camera_Target",
            "Frame_Counter", "PageIn_Fully_Resident", "Camera_Art_Hold"]
    missing = [n for n in need if n not in sym]
    if missing:
        print(f"symbols missing from {lst}: {', '.join(missing)}", file=sys.stderr)
        return 3
    states = [s for s in args.state.split(",") if s]
    for s in states:
        if s not in STATES:
            print(f"unknown state {s}", file=sys.stderr)
            return 3

    results = {s: [] for s in states}

    async def sweep(state):
        # ONE FRESH SERVER PER STATE, and the reason is a defect this tool's own
        # assertion 5 caught: `watchpoint_hits` is POLL-ONLY, never draining
        # (CR-12, adopted poll-only by ruling), and `watchpoint_clear` removes the
        # WATCH, not the ring. A second state read on the same process therefore
        # returns state 1's hits as well as its own — measured exactly: maxdiag 62
        # claims, then `right` reported 62+15=77 against a Block_Stage_Gen delta of
        # 15, then `down` 77+19=96 against 19. A per-state process is the honest
        # fix (it is also one reset per state, which is what the choke probe does).
        async with Server(rom, lst, args.sock) as srv:
            results[state].append(await one(srv.client, sym, state, args.settle,
                                            args.lead, args.sample, slots,
                                            not args.no_strict))

    try:
        for _ in range(args.repeat):
            for s in states:
                asyncio.run(sweep(s))
    except ProbeError as e:
        print(f"FAIL: {e}", file=sys.stderr)
        return 2

    print(f"ROM {rom}")
    print(f"BLOCK_STAGE_SLOTS {slots}   prefetch lead {args.lead_ticks} ticks   "
          f"sample {args.sample} frames   repeats {args.repeat}")
    print("mclk-stamped watch hits on oracle-aether (CR-12). NOT a cycle instrument.\n")
    for s in states:
        report(s, results[s], slots, args.lead_ticks)
        if args.events:
            for r in results[s][0]["recs"]:
                print(f"   slot {r['slot']:2d} key {r['key']:08X} {r['phase']:6s} "
                      f"tick {r['tick']} -> evict {r['evicted_tick']} "
                      f"uses {[(u['tick'], u['phase']) for u in r['uses']]}")
            print()

    if args.json:
        Path(args.json).write_text(json.dumps(
            {s: [{k: v for k, v in r.items() if k != "recs"} for r in results[s]]
             for s in states}, indent=2, default=str))

    bad = any(r["problems"] for s in states for r in results[s])
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
