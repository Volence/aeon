#!/usr/bin/env python3
"""tick_variance_probe — the per-TICK cost distribution at sustained max-diagonal,
measured on the NEW oracle's exact per-invocation profiler.

WHY THIS EXISTS, and why it is not a flag on the old probe.
`tools/streaming_choke_probe.py` and its kin drive `oracle-old/linux-port/harness`
(the C++ Exodus port) and consume rows with three defects the corpus A/B measured on
this very ROM family (oracle `docs/2026-08-20-profiler-corpus-ab.md`):

  * cycles LOST to preemption and to the per-frame shadow-stack reset — the old
    instrument's five published top-level rows tile only **78.45%** of a max-diagonal
    frame (A/B §9.2). Any "work per tick" built on them is a floor of unknown depth.
  * every figure divided in-server by the REQUESTED window with `calls` floored up to
    1, so a once-per-tick routine's count carries no information (A/B §5.2).
  * a cycle base that excludes bus/DMA stall by construction, with no stall row at all.

None of those caveats survive here, so none of them is carried:
  * rows are exact per invocation: `cycles` inclusive, `cyclesSelf` additive, and the
    server closes the identity
        Sum(routines[].cyclesSelfTotal) + Sum(interrupts[].cyclesSelfTotal)
            + unattributedCycles == sampleCycles
    which this probe CHECKS on every sample rather than trusting (see `identity`).
  * `callsTotal` is a real count. Nothing is floored, nothing is fabricated.
  * `stallCycles` is reported SEPARATELY and never absorbed into a cycle figure. Where
    a stall-free comparison is wanted the probe prints `cycles - stallCycles` beside
    the raw figure and labels which is which.
  * the hint/vint split is real (the old `interrupts.hint` was HBlank PLUS VBlank on
    this ROM); both buckets are printed.

ROW BASIS, stated once and repeated per figure in the output:
  * `cyclesSelf`  — the row's OWN cycles, callees excluded. ADDITIVE: the per-frame
    self columns of all rows plus both interrupt buckets sum to the frame, exactly.
    This is the basis for every "share of the frame" figure here.
  * `cycles`      — inclusive of callees, EXCLUDING preemption (a routine's row does
    not grow because a VBlank interrupted it). Used only for the named brackets, and
    labelled `incl` wherever it appears.
  * `stallCycles` — the subset of `cycles` the CPU spent held off the bus. Printed in
    its own column, always.

THE MEASUREMENT the probe was built for (two questions, one run):

  1. THE HONEST WORK/TICK RETAKE. `docs/benchmarks/streaming/ARC-CLOSEOUT.md` closed the
     streaming arc with "work/tick 123,016, mean 4,984 UNDER the 128,000 line" — an
     OLD-INSTRUMENT number, downgraded to a hypothesis by its own 2026-08-20 addendum.
     Here work is defined with no attribution gap to hide in:
         work over the window = sampleCycles - (VSync_Wait inclusive cycles)
         work per tick        = that / (Logic_Tick delta over the same window)
     `sampleCycles` is the machine's own undivided cycle count for the window, so the
     only modelling in that expression is "the vsync spin is not work". Interrupt time
     is work and is inside it, which is the same convention the 128,000 line uses.

  2. THE SPIKE HUNT. A mean under the line is necessary, not sufficient: frames_per_tick
     is ceil()-shaped, so a tick that spikes past 128,000 costs a whole extra frame. The
     per-frame series is recovered by PREFIX DIFFERENCING (see `per_frame_series`) and
     grouped into ticks by the engine's own `Logic_Tick`, read at every frame boundary —
     not inferred. The A/B's `vintCycles` partition (§12) is CHECKED against that
     ground truth rather than used in place of it.

HOW PER-FRAME PER-ROUTINE ROWS ARE RECOVERED. `perFrame[]` carries whole-frame totals
only (cycles / stallCycles / hintCycles / vintCycles) — there is no per-routine
breakdown in it, by spec. So the probe takes N samples of length 1..N from the SAME
start state (fresh reset + settle + lead each time, so nothing is carried) and
differences the cumulative `*Total` columns. Two properties make that exact rather than
approximate: the machine is deterministic (the A/B's spread gate: byte-identical
replies across boots), and the server attributes an OPEN invocation's partial time as
it goes (the identity closes with `unattributedCycles == 0` at every prefix length, so
no cycle is waiting to be booked at the cut). The ladder is CONTROLLED, not assumed:
prefix N must reproduce the direct N-frame sample cell for cell, or the run is BLOCKED.

THE CONTROL, and the arc stops without it. Before any new number is taken, the probe
re-measures the corpus A/B's own designated PHASE-0 REFERENCE ROW on the corpus's own
ROM — `s4.debug.bin` crc `d22dda85`, recovered byte-identically from sigil's committed
golden at `7b46f075` (no rebuild) — and compares against values pinned from that
document, at BOTH camera states:
    $FFB452 (HBlank_Vector_Slot): 1878.0 cyc/video-frame, 4.000 calls/frame, stall 0
    sampleCycles 3968178, identity remainder 0, idle 30 ticks / maxdiag 15 ticks,
    idle camera (96,144) stationary, maxdiag camera (320,368) -> (560,608),
    and §12's whole 31-row `vintCycles` series at both states.
The corpus ROM ships no listing, so the symbol addresses come from the CURRENT build's
listing and are VALIDATED on the corpus ROM by three witnesses the A/B publishes
independently (Camera_X 96, Camera_Y 144, Camera_Target -> leader $FF8DB0). If any of
that misses, the probe exits 1 and takes no measurement: a harness that cannot
reproduce a pinned row is not an instrument.

RED-FIRST. Every check here was made to fail before it was allowed to pass; `--poison`
reproduces that on demand:
    --poison control-rom  runs the corpus expectations against the CURRENT ROM
    --poison identity     adds one cycle to the identity's remainder
    --poison prefix       drops a rung from the prefix ladder
Each MUST exit 1. A check that cannot be poisoned is not tested.

Usage:
    python3 tools/tick_variance_probe.py --rom s4.debug.bin --lst s4.debug.lst --boots 3
    python3 tools/tick_variance_probe.py --no-control --boots 1      # iteration only
    python3 tools/tick_variance_probe.py --poison identity           # must exit 1
Exit: 0 measured · 1 a control/assertion failed (BLOCKED) · 3 setup problem
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
from aether import BusClient  # noqa: E402

# The NEW oracle (Rust). `oracle-next` is a symlink to `oracle`; the OLD C++ harness at
# oracle-old/linux-port/harness is deliberately NOT importable from here — this probe's
# whole point is that it does not consume those rows.
SERVER = "/home/volence/sonic_hacks/oracle/target/release/oracle-aether"
# The corpus A/B's ROM, recovered from sigil's committed golden rather than rebuilt.
CORPUS_GOLDEN = ("/home/volence/sonic_hacks/sigil", "7b46f075",
                 "crates/sigil-harness/golden/s4.debug.bin")
CORPUS_CRC, CORPUS_LEN = 0xD22DDA85, 713295

# AF_UNIX caps at 108 bytes and scratchpad paths are longer; per-process so parallel
# lanes in parallel worktrees never unlink each other's socket.
SOCK = f"/tmp/aeon_tickvar_{os.getpid()}.sock"

SETTLE = 180        # engine_baseline_probe's settle, unchanged so states compare
LEAD = 24           # frames after the poke, to reach the steady follow ceiling
WINDOW = 31         # the corpus's window length; run_frames(WINDOW+1) measures exactly this

SST_X_POS, SST_Y_POS = 0x02, 0x06
DIAG_AHEAD_X, DIAG_AHEAD_Y = 2000, 1400
CAM_MAX_STEP = 16
STATES = {"idle": (0, 0), "maxdiag": (DIAG_AHEAD_X, DIAG_AHEAD_Y)}

# Engine counters read at EVERY frame boundary of the ladder. These are the spike
# hunt's candidate causes: a fill burst on a row/column crossing shows up as a step in
# Cache_Left_Col / Cache_Top_Row and as decompresses in Block_Stage_Gen.
LONG_SYMS = ("Logic_Tick", "Lag_Frame_Count", "Camera_X", "Camera_Y")
WORD_SYMS = ("Frame_Counter", "Block_Stage_Gen", "Cache_Left_Col", "Cache_Head_Col",
             "Cache_Top_Row", "Cache_Bottom_Row", "Cache_Fill_Budget",
             "Cache_Fill_Rows_Left", "Cache_Art_Stall", "Cache_Spec_Skips",
             "Dbg_Cam_Clamp_Frames")
BYTE_SYMS = ("PageIn_Fully_Resident", "Camera_Art_Hold", "PageCache_Direct_Map")
SETUP_SYMS = ("Camera_Target",)
# Named brackets whose per-frame series the deliverable asks for by name.
FEATURED = ("Tile_Cache_Fill", "GameState_OJZScroll_Update", "Parallax_Update",
            "VSync_Wait", "VInt_Level", "Section_UpdateColumns",
            "TileCache_FillRow", "TileCache_FillColumn", "TileCache_DecompressBlock")

# ---- values PINNED from oracle/docs/2026-08-20-profiler-corpus-ab.md -----------------
# §5.1 (the reference row), §2.5 (state witnesses), §3 (sampleCycles), §12 (the ring).
AB = {
    "sampleCycles": 3968178,
    "hb_addr": 0xFFB452,
    "hb_cycles_per_frame": 1878.0,
    "hb_calls_per_frame": 4.0,
    "hb_stall": 0,
    "leader": 0xFF8DB0,
    "idle": {"ticks": 30, "cam0": (96, 144), "cam1": (96, 144),
             "vint": [9230, 9242, 9230, 9242, 9230, 9242, 9230, 9242, 9230, 9242,
                      9230, 9242, 9230, 9242, 9230, 9242, 9230, 7534, 8310, 8342,
                      9230, 9242, 9230, 9242, 9230, 9242, 9230, 9242, 9230, 9242, 9230],
             "stall": [2270] * 17 + [2174, 2270, 2174] + [2270] * 11},
    "maxdiag": {"ticks": 15, "cam0": (320, 368), "cam1": (560, 608),
                "vint": [13908, 7852, 13908, 7852, 13908, 7852, 7840, 7852, 13908, 7852,
                         13908, 7852, 13908, 7852, 13908, 7852, 13908, 7852, 13908, 7852,
                         13908, 7852, 13908, 7852, 13908, 7852, 13908, 7852, 13908, 7852,
                         13908],
                "stall": [2220, 2182, 2220, 2182, 2220, 2182, 2182, 2182, 2220, 2182,
                          2220, 2182, 2220, 2182, 2220, 2182, 2220, 2182, 2220, 2182,
                          2220, 2182, 2220, 2182, 2220, 2182, 2220, 2182, 2220, 2182,
                          2220]},
}


class Blocked(Exception):
    """A condition under which no number may be recorded. Carries its own evidence."""


class Setup(Exception):
    """The lane could not be brought up at all — exit 3, distinct from a red check."""


# ---- the bus session ----------------------------------------------------------------

class Server:
    """One oracle-aether process, one ROM. A fresh one per boot: an independent boot is
    a new machine, not a `reset` on an old one (the A/B's spread-gate discipline)."""

    def __init__(self, rom: str, lst: str | None, sock: str = SOCK):
        self.rom, self.lst, self.sock = rom, lst, sock
        self.proc = self.client = None

    async def __aenter__(self) -> BusClient:
        if os.path.exists(self.sock):
            os.unlink(self.sock)
        argv = [SERVER, self.rom, "--socket", self.sock, "--no-pace"]
        if self.lst:
            argv += ["--symbols", self.lst]
        self.proc = subprocess.Popen(argv, stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL)
        for _ in range(400):
            if os.path.exists(self.sock):
                break
            time.sleep(0.05)
        else:
            raise Setup(f"oracle-aether never created {self.sock} (binary {SERVER})")
        self.client = BusClient(self.sock, client_id="tickvar",
                                client_name="tick_variance_probe")
        await self.client.connect()
        for m in ("emulator/set_profiler", "emulator/get_profiler_frames"):
            if not self.client.supports(m):
                raise Setup(f"the server does not advertise `{m}` — rebuild "
                            "`cargo build --release -p oracle-aether` in the oracle repo")
        if not self.client.capabilities.get("profiler"):
            raise Setup("server advertises no `profiler` capability")
        return self.client

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


async def rd(c, addr, n):
    r = await c.call("emulator/read_memory", {"addr": hex(addr & 0xFFFFFF), "len": n})
    b = r["bytes"]
    b = b[2:] if b.lower().startswith("0x") else b
    return int(b[:n * 2], 16)


async def counters(c, sym):
    out = {}
    for n in LONG_SYMS:
        out[n] = await rd(c, sym[n], 4)
    for n in WORD_SYMS:
        if n in sym:
            out[n] = await rd(c, sym[n], 2)
    for n in BYTE_SYMS:
        if n in sym:
            out[n] = await rd(c, sym[n], 1)
    out["cam"] = (out["Camera_X"] >> 16, out["Camera_Y"] >> 16)
    return out


async def reach(c, sym, state):
    """Reset, settle, poke the leader, lead. Identical in setup to engine_baseline_probe
    and streaming_choke_probe, so the states are the same states."""
    ax, ay = STATES[state]
    await c.call("emulator/reset", {})
    await c.call("emulator/run_frames", {"frames": SETTLE})
    if ax or ay:
        tgt = await rd(c, sym["Camera_Target"], 2)
        leader = 0xFF0000 | tgt if tgt & 0x8000 else tgt
        cx = (await rd(c, sym["Camera_X"], 4)) >> 16
        cy = (await rd(c, sym["Camera_Y"], 4)) >> 16
        await c.call("emulator/write_memory",
                     {"addr": hex((leader + SST_X_POS) & 0xFFFFFF),
                      "value": (cx + ax) << 16, "width": 4})
        await c.call("emulator/write_memory",
                     {"addr": hex((leader + SST_Y_POS) & 0xFFFFFF),
                      "value": (cy + ay) << 16, "width": 4})
        await c.call("emulator/run_frames", {"frames": LEAD})
        return leader
    return None


async def sample(c, frames):
    """One profiler sample of exactly `frames` complete video frames.

    run_frames(N) yields frameCount == N-1: the sample is delimited by frame boundaries
    at BOTH ends, so the frame the arm lands in is inexpressible and is not counted.
    We run one frame MORE rather than asking for one fewer (the legacy `frames: sample-1`
    folklore did the opposite and silently measured a 30/31 window)."""
    await c.call("emulator/set_profiler", {"enabled": True, "perFrame": True})
    await c.call("emulator/run_frames", {"frames": frames + 1})
    pf = await c.call("emulator/get_profiler_frames", {"frames": frames + 8, "top": 512})
    await c.call("emulator/set_profiler", {"enabled": False})
    return pf


def identity(pf, poison=False):
    """The completeness identity the SERVER itself defines (CR-26 §11.16), checked, not
    trusted. Expectation DERIVED from the reply's own keys — no literal anywhere."""
    rows = pf["routines"]["items"]
    s = sum(r["cyclesSelfTotal"] for r in rows)
    s += sum(pf["interrupts"][k]["cyclesSelfTotal"] for k in ("hint", "vint"))
    rem = pf["sampleCycles"] - (s + pf["unattributedCycles"]) + (1 if poison else 0)
    if rem != 0:
        raise Blocked(f"completeness identity does not close: sampleCycles "
                      f"{pf['sampleCycles']} - (self {s} + unattributed "
                      f"{pf['unattributedCycles']}) = {rem}")
    if pf["routines"]["truncated"]:
        raise Blocked(f"routine rows TRUNCATED ({pf['routines']['returned']} of "
                      f"{pf['routines']['total']}) — the sum above is not the whole frame")
    for k in ("abandonedFrames", "depthExceeded"):
        if pf[k]:
            raise Blocked(f"{k} = {pf[k]}: the instrument dropped attribution in this sample")
    if pf["frameCount"] != pf["perFrame"]["returned"]:
        raise Blocked(f"perFrame ring has {pf['perFrame']['returned']} rows for "
                      f"frameCount {pf['frameCount']}")
    return s


def by_name(pf):
    return {r["name"]: r for r in pf["routines"]["items"] if r.get("name")}


def by_addr(pf):
    return {int(r["addr"], 16) & 0xFFFFFF: r for r in pf["routines"]["items"]}


# ---- the control --------------------------------------------------------------------

def recover_corpus_rom(dest: Path) -> Path:
    """The A/B's ROM, byte-identical, from sigil's committed golden. No rebuild: the
    golden blob at 7b46f075 IS the image the corpus measured (A/B §1.3 step 4)."""
    import zlib
    repo, rev, path = CORPUS_GOLDEN
    if not dest.exists():
        out = subprocess.run(["git", "-C", repo, "show", f"{rev}:{path}"],
                             stdout=subprocess.PIPE)
        if out.returncode != 0 or not out.stdout:
            raise Setup(f"could not read {path} at {rev} from {repo}")
        dest.write_bytes(out.stdout)
    d = dest.read_bytes()
    crc = zlib.crc32(d) & 0xFFFFFFFF
    if (crc, len(d)) != (CORPUS_CRC, CORPUS_LEN):
        raise Setup(f"corpus ROM identity wrong: crc {crc:08x} len {len(d)} "
                    f"(want {CORPUS_CRC:08x} / {CORPUS_LEN})")
    return dest


async def control(rom: Path, sym: dict, poison_rom: str | None = None) -> list[str]:
    """Re-measure the A/B's pinned rows on the A/B's own ROM. Returns the transcript;
    raises Blocked on the first cell that misses."""
    log = []
    target = poison_rom or str(rom)
    async with Server(target, None) as c:
        st = await c.call("emulator/status", {})
        log.append(f"   control ROM {Path(target).name}  romBytes {st['romBytes']}")
        for state in ("idle", "maxdiag"):
            exp = AB[state]
            await c.call("emulator/reset", {})
            await c.call("emulator/run_frames", {"frames": SETTLE})
            # The three witnesses that validate borrowing the CURRENT build's symbol
            # addresses for a ROM that ships no listing. All three are published
            # independently by the A/B (§2.3, §2.5).
            cx = (await rd(c, sym["Camera_X"], 4)) >> 16
            cy = (await rd(c, sym["Camera_Y"], 4)) >> 16
            tgt = await rd(c, sym["Camera_Target"], 2)
            leader = 0xFF0000 | tgt if tgt & 0x8000 else tgt
            if (cx, cy) != (96, 144) or leader != AB["leader"]:
                raise Blocked(
                    f"[{state}] the borrowed symbol addresses do not describe this ROM: "
                    f"Camera_X {cx} Camera_Y {cy} leader ${leader:06X} "
                    f"(A/B: 96 / 144 / ${AB['leader']:06X})")
            if state == "maxdiag":
                await c.call("emulator/write_memory",
                             {"addr": hex((leader + SST_X_POS) & 0xFFFFFF),
                              "value": (cx + DIAG_AHEAD_X) << 16, "width": 4})
                await c.call("emulator/write_memory",
                             {"addr": hex((leader + SST_Y_POS) & 0xFFFFFF),
                              "value": (cy + DIAG_AHEAD_Y) << 16, "width": 4})
                await c.call("emulator/run_frames", {"frames": LEAD})
            c0 = await counters(c, sym)
            pf = await sample(c, WINDOW)
            c1 = await counters(c, sym)
            identity(pf)
            n = pf["frameCount"]
            fails = []
            if n != WINDOW:
                fails.append(f"frameCount {n} != {WINDOW}")
            if pf["sampleCycles"] != AB["sampleCycles"]:
                fails.append(f"sampleCycles {pf['sampleCycles']} != {AB['sampleCycles']}")
            row = by_addr(pf).get(AB["hb_addr"])
            if row is None:
                fails.append(f"no row at ${AB['hb_addr']:06X}")
            else:
                cyc, cal = row["cyclesTotal"] / n, row["callsTotal"] / n
                if cyc != AB["hb_cycles_per_frame"]:
                    fails.append(f"$FFB452 {cyc} cyc/frame != {AB['hb_cycles_per_frame']}")
                if cal != AB["hb_calls_per_frame"]:
                    fails.append(f"$FFB452 {cal} calls/frame != {AB['hb_calls_per_frame']}")
                if row["stallCyclesTotal"] != AB["hb_stall"]:
                    fails.append(f"$FFB452 stall {row['stallCyclesTotal']} != 0")
            ticks = c1["Logic_Tick"] - c0["Logic_Tick"]
            if ticks != exp["ticks"]:
                fails.append(f"ticks {ticks} != {exp['ticks']}")
            if c0["cam"] != exp["cam0"] or c1["cam"] != exp["cam1"]:
                fails.append(f"camera {c0['cam']}->{c1['cam']} != "
                             f"{exp['cam0']}->{exp['cam1']}")
            vint = [x["vintCycles"] for x in pf["perFrame"]["items"]]
            stall = [x["stallCycles"] for x in pf["perFrame"]["items"]]
            if vint != exp["vint"]:
                fails.append(f"perFrame vintCycles series differs from A/B §12\n"
                             f"        ours {vint}\n        A/B  {exp['vint']}")
            if stall != exp["stall"]:
                fails.append(f"perFrame stallCycles series differs from A/B §12\n"
                             f"        ours {stall}\n        A/B  {exp['stall']}")
            if fails:
                raise Blocked(f"[control {state}] " + "; ".join(fails))
            log.append(f"   PASS control {state:8}: $FFB452 {row['cyclesTotal']/n:.1f} "
                       f"cyc/frame, {row['callsTotal']/n:.3f} calls/frame, stall "
                       f"{row['stallCyclesTotal']}; sampleCycles {pf['sampleCycles']}; "
                       f"{ticks} ticks; camera {c0['cam']}->{c1['cam']}; "
                       f"31-row vintCycles + stallCycles series EXACT vs A/B §12")
    return log


# ---- the measurement ----------------------------------------------------------------

async def per_frame_series(c, sym, state, window, poison=False):
    """Prefix differencing: N samples of length 1..N from the SAME start state.

    Returns (cums, counters_at_each_boundary, direct) where cums[k] is the reply for a
    k-frame sample. Differencing the `*Total` columns gives per-FRAME figures; the
    identity closing with unattributedCycles == 0 at every rung is what makes the cut
    exact (no cycle is waiting to be booked at the boundary)."""
    cums, cnts = [], []
    ladder = list(range(1, window + 1))
    if poison:
        ladder.remove(window // 2)      # --poison prefix: a missing rung
    for k in ladder:
        await reach(c, sym, state)
        c0 = await counters(c, sym)
        pf = await sample(c, k)
        c1 = await counters(c, sym)
        identity(pf)
        if pf["frameCount"] != k:
            raise Blocked(f"prefix {k}: frameCount {pf['frameCount']}")
        cums.append((k, pf, c0, c1))
        cnts.append((k, c1))
    return cums, cnts


def diff_series(cums, keys=("cyclesTotal", "cyclesSelfTotal", "stallCyclesTotal",
                            "callsTotal")):
    """Per-frame figures from the cumulative ladder. cums must be contiguous 1..N."""
    out = []
    prev = {}
    for k, pf, _c0, _c1 in cums:
        cur = {}
        for r in pf["routines"]["items"]:
            cur[(int(r["addr"], 16) & 0xFFFFFF, r.get("name"))] = {q: r[q] for q in keys}
        for b in ("hint", "vint"):
            cur[(None, b)] = {q: pf["interrupts"][b][q] for q in keys}
        frame = {}
        for key, v in cur.items():
            p = prev.get(key, {q: 0 for q in keys})
            frame[key] = {q: v[q] - p[q] for q in keys}
        out.append(frame)
        prev = cur
    return out


def check_ladder(cums, direct, window):
    """The ladder's own control, in two parts.

    (a) CONTIGUITY. Differencing rung k against rung k-1 is only a per-frame figure if
    the ladder really is 1,2,...,N with nothing missing; a gap silently turns one
    "frame" into two frames' work and nothing downstream can tell. Checked first,
    because it is the failure that would otherwise read as a spike.
    (b) The top rung must reproduce the DIRECT N-frame sample cell for cell. If prefix
    differencing were lossy — an open invocation's partial time held back until its
    return, say — this is where it shows."""
    got = [k for k, _pf, _c0, _c1 in cums]
    if got != list(range(1, window + 1)):
        missing = sorted(set(range(1, window + 1)) - set(got))
        raise Blocked(f"prefix ladder is not contiguous 1..{window}: "
                      f"{len(got)} rungs, missing {missing} — every difference across a "
                      f"gap would be booked as one frame's work and read as a spike")
    k, pf, _, _ = cums[-1]
    if k != direct["frameCount"]:
        raise Blocked(f"ladder top rung {k} != direct frameCount {direct['frameCount']}")
    a = {(r["addr"], r.get("name")): (r["cyclesTotal"], r["cyclesSelfTotal"],
                                      r["stallCyclesTotal"], r["callsTotal"])
         for r in pf["routines"]["items"]}
    b = {(r["addr"], r.get("name")): (r["cyclesTotal"], r["cyclesSelfTotal"],
                                      r["stallCyclesTotal"], r["callsTotal"])
         for r in direct["routines"]["items"]}
    if a != b:
        d = [f"{k2}: ladder {a.get(k2)} direct {b.get(k2)}"
             for k2 in set(a) | set(b) if a.get(k2) != b.get(k2)]
        raise Blocked("ladder top rung != direct sample:\n      " + "\n      ".join(d[:8]))
    if pf["sampleCycles"] != direct["sampleCycles"]:
        raise Blocked("ladder/direct sampleCycles differ")
    return True


async def measure_boot(c, sym, state, window, poison_prefix=False):
    """One boot: the direct window sample, then the prefix ladder, then the checks."""
    await reach(c, sym, state)
    c0 = await counters(c, sym)
    direct = await sample(c, window)
    c1 = await counters(c, sym)
    identity(direct)
    if direct["frameCount"] != window:
        raise Blocked(f"direct sample frameCount {direct['frameCount']} != {window}")
    cums, cnts = await per_frame_series(c, sym, state, window, poison=poison_prefix)
    check_ladder(cums, direct, window)
    return {"direct": direct, "c0": c0, "c1": c1, "cums": cums, "cnts": cnts,
            "frames": window, "ticks": c1["Logic_Tick"] - c0["Logic_Tick"]}


# ---- reporting ----------------------------------------------------------------------
#
# THE PER-FRAME BASIS IS `cyclesSelf`, AND THAT IS NOT A PREFERENCE — IT IS THE ONLY
# ONE THE LADDER CAN CARRY. Measured here on 2026-08-20 and worth stating because it is
# the first thing a re-runner will get wrong: differencing a row's INCLUSIVE
# `cyclesTotal` across the ladder does NOT give "that routine's cycles in that frame".
# An invocation that straddles a frame boundary shows up with its inclusive cost
# credited in a lump — e.g. `GameState_OJZScroll_Update` reads 3,836 in the frame where
# a burst ran and 149,104 (more than a whole 128,000-cycle frame) in the next, while its
# child `Tile_Cache_Fill` reads 97,878 in the first. Self cycles have no such problem:
# they are additive by construction and the server's own identity closes on them, which
# the probe checks at every rung. So subtree costs here are built by SUMMING SELF over a
# declared subtree, and the sum is CHECKED against the parent's inclusive window total.

# The fill's subtree, from the call tree verified in tools/streaming_choke_probe.py's
# header (every `jbsr` in engine/ + games/, 2026-08-19) — PageCache_Audit deliberately
# absent since fix F5 moved it out to the level state's tick.
FILL_SUBTREE = ("Tile_Cache_Fill", "TileCache_FillRow", "TileCache_FillColumn",
                "TileCache_CopyBlockColumn", "PageCache_PatchRun_Seq",
                "PageCache_PatchRun_Col", "TileCache_DecompressBlock",
                "S4LZ_DecompressDict", "S4LZ_Decompress", "TileCache_FindStagedBlock",
                "TileCache_HSlide", "TileCache_VSlide", "TileCache_VSlideUp",
                "PageCache_Request", "PageCache_Prefetch")


def block_tile_size(root=Path(__file__).resolve().parent.parent):
    """BLOCK_TILE_SIZE read from the engine's own constants, not pinned here. The block
    grid is the spike hunt's candidate cause, so its geometry must come from the source
    that defines it or the correlation is fitted."""
    src = root / "engine" / "system" / "constants.emp"
    for line in src.read_text().splitlines():
        if line.strip().startswith("pub const BLOCK_TILE_SIZE"):
            return int(line.split("=")[1].split("//")[0].strip())
    raise Setup(f"BLOCK_TILE_SIZE not found in {src}")


def spin_cycles(pf):
    """VSync_Wait's INCLUSIVE cycles — the idle spin. Inclusive rather than self so a
    callee reached from inside the spin counts as spin too; both are printed so the
    choice is auditable. This is a WINDOW total (no straddle problem: the window's ends
    are the only straddles and the identity says nothing is lost at them)."""
    r = by_name(pf).get("VSync_Wait")
    if r is None:
        raise Blocked("no VSync_Wait row — the idle spin cannot be separated from work")
    return r["cyclesTotal"], r["cyclesSelfTotal"]


def report(state, boots, out=sys.stdout):
    p = lambda *a: print(*a, file=out)                             # noqa: E731
    b0 = boots[0]
    pf = b0["direct"]
    n, ticks = pf["frameCount"], b0["ticks"]
    ring = pf["perFrame"]["items"]
    BTS = block_tile_size()
    dx = b0["c1"]["cam"][0] - b0["c0"]["cam"][0]
    dy = b0["c1"]["cam"][1] - b0["c0"]["cam"][1]
    # The follow-ceiling witness is only meaningful where the camera moves: dx == ticks *
    # CAM_MAX_STEP is what says "sustained at the cap" rather than "somewhere below it".
    cap = ""
    if dx or dy:
        cap = (f" (= {ticks} x {CAM_MAX_STEP} px: sustained AT the follow ceiling)"
               if dx == ticks * CAM_MAX_STEP and dy == ticks * CAM_MAX_STEP else
               f" (NOT the {ticks} x {CAM_MAX_STEP} = {ticks * CAM_MAX_STEP} px ceiling —"
               f" this state is BELOW the cap and is not the sustained max-diagonal)")
    p(f"== state {state}   {n} video frames / {ticks} logic ticks = "
      f"{n / ticks:.3f} frames/tick   camera {b0['c0']['cam']} -> {b0['c1']['cam']}"
      f"   dx {dx} dy {dy} px{cap}")
    p(f"   witnesses: PageIn_Fully_Resident {b0['c1'].get('PageIn_Fully_Resident')}"
      f"  Camera_Art_Hold {b0['c1'].get('Camera_Art_Hold')}"
      f"  PageCache_Direct_Map {b0['c1'].get('PageCache_Direct_Map')}"
      f"  Dbg_Cam_Clamp_Frames {b0['c1'].get('Dbg_Cam_Clamp_Frames')}"
      f"  BLOCK_TILE_SIZE {BTS} (from engine/system/constants.emp)")
    tk = [x["ticks"] for x in boots]
    sc = [x["direct"]["sampleCycles"] for x in boots]
    p(f"   across {len(boots)} boots: ticks {tk} (spread {max(tk) - min(tk)})   "
      f"sampleCycles {sc} (spread {max(sc) - min(sc)})")

    # ---- 1. the honest work/tick retake ---------------------------------------------
    spin_incl, spin_self = spin_cycles(pf)
    work = pf["sampleCycles"] - spin_incl
    p("\n   -- 1. WORK PER TICK, honest basis (sampleCycles is the machine's own"
      " undivided count for the window; nothing is divided by a requested window and"
      " nothing is floored) --")
    p(f"   sampleCycles {pf['sampleCycles']}  - VSync_Wait incl {spin_incl}"
      f"  = work {work}   over {ticks} ticks")
    p(f"   WORK/TICK = {work / ticks:,.0f} cyc   vs the 128,000 line: "
      f"{'UNDER by' if work / ticks < 128000 else 'OVER by'} "
      f"{abs(128000 - work / ticks):,.0f}   ({work / ticks / 128000 * 100:.1f}% of a frame)")
    p(f"   (VSync_Wait self {spin_self}; the {spin_incl - spin_self} difference is a"
      f" callee reached from inside the wait and is counted as spin here)")
    works = []
    for x in boots:
        si, _ = spin_cycles(x["direct"])
        works.append((x["direct"]["sampleCycles"] - si) / x["ticks"])
    p(f"   across boots: {[f'{w:,.0f}' for w in works]}   spread "
      f"{max(works) - min(works):,.1f}")

    # ---- per-frame series ------------------------------------------------------------
    frames = diff_series(b0["cums"])
    cnts = [c for _k, c in b0["cnts"]]
    idx = {}
    for f in frames:
        for key in f:
            idx.setdefault(key[1], key)

    def series(name, q):
        key = idx.get(name)
        return [f.get(key, {}).get(q, 0) if key else 0 for f in frames]

    spin_f = series("VSync_Wait", "cyclesTotal")
    work_f = [x["cycles"] - s for x, s in zip(ring, spin_f)]
    fill_f = [sum(series(nme, "cyclesSelfTotal")[i] for nme in FILL_SUBTREE)
              for i in range(n)]
    s4lz_f = series("S4LZ_DecompressDict", "cyclesSelfTotal")
    s4lz_c = series("S4LZ_DecompressDict", "callsTotal")

    # the subtree's closure, checked not assumed: summing SELF over the declared subtree
    # must land on the parent's own INCLUSIVE window total.
    fill_row = by_name(pf).get("Tile_Cache_Fill")
    if fill_row:
        gap = fill_row["cyclesTotal"] - sum(fill_f)
        p(f"\n   fill-subtree closure: sum(self over {len(FILL_SUBTREE)} declared rows) "
          f"{sum(fill_f)} vs Tile_Cache_Fill inclusive {fill_row['cyclesTotal']} "
          f"-> residual {gap} ({100.0 * gap / fill_row['cyclesTotal']:+.2f}%)"
          f"{'  [the window ends straddle; rows outside the declared subtree would add here]' if gap else ''}")

    # ---- 2. the tick partition -------------------------------------------------------
    lt0 = b0["c0"]["Logic_Tick"]
    lt = [c["Logic_Tick"] for c in cnts]
    ticked = [lt[0] > lt0] + [lt[i] > lt[i - 1] for i in range(1, len(lt))]
    vint = [x["vintCycles"] for x in ring]
    hi = [v for v, t in zip(vint, ticked) if t]
    lo = [v for v, t in zip(vint, ticked) if not t]
    sep = (min(hi) > max(lo)) if hi and lo else None
    p("\n   -- 2. the tick partition: the A/B §12 `vintCycles` method CHECKED against the"
      " engine's own Logic_Tick, read at every frame boundary --")
    p(f"   ground truth: {sum(ticked)} of {n} frames carried a logic tick "
      f"({n - sum(ticked)} lag frames)")
    p(f"   vintCycles on tick frames: min {min(hi) if hi else '-'} max "
      f"{max(hi) if hi else '-'}   on lag frames: {sorted(lo)}")
    if sep is True:
        p("   VERDICT: a single vintCycles threshold DOES separate them at this state "
          "(the A/B's method reproduces)")
    elif sep is False:
        p("   VERDICT: NO vintCycles threshold separates tick frames from lag frames at"
          " this state — the A/B's §12 partition is a property of ITS state, not a"
          " general method. Logic_Tick is the ground truth and is what is used below.")
    else:
        p("   VERDICT: not separable — one of the two classes is empty in this window")

    # ---- 3. the per-frame table ------------------------------------------------------
    p("\n   -- 3. per-FRAME work. work = frame cycles - that frame's VSync_Wait span."
      "  fill/S4LZ columns are SUMS OF SELF (see the module note: inclusive diffs are"
      " not per-frame quantities) --")
    p(f"   {'frame':>6} {'tick':>4} {'work':>8} {'%128k':>6} {'spin':>7} {'stall':>6}"
      f" {'vint':>6} {'fillsub':>8} {'S4LZ':>7} {'n':>2} {'dec':>4}"
      f" {'headcol':>8} {'botrow':>7} {'blk c/r':>8}")
    prev_c, spikes = b0["c0"], []
    blk_cross = []
    for i, f in enumerate(ring):
        c = cnts[i]
        dec = c.get("Block_Stage_Gen", 0) - prev_c.get("Block_Stage_Gen", 0)
        bc = c.get("Cache_Head_Col", 0) // BTS
        br = c.get("Cache_Bottom_Row", 0) // BTS
        pbc = prev_c.get("Cache_Head_Col", 0) // BTS
        pbr = prev_c.get("Cache_Bottom_Row", 0) // BTS
        mark = ("C" if bc != pbc else "") + ("R" if br != pbr else "")
        if mark:
            blk_cross.append((f["frame"], mark))
        if s4lz_c[i]:
            spikes.append(i)
        p(f"   {f['frame']:>6} {('T' if ticked[i] else '.'):>4} {work_f[i]:>8} "
          f"{100.0 * work_f[i] / 128000:>5.1f}% {spin_f[i]:>7} {f['stallCycles']:>6} "
          f"{f['vintCycles']:>6} {fill_f[i]:>8} {s4lz_f[i]:>7} {s4lz_c[i]:>2} {dec:>4}"
          f" {c.get('Cache_Head_Col'):>8} {c.get('Cache_Bottom_Row'):>7} "
          f"{str(bc) + '/' + str(br) + ' ' + mark:>8}")
        prev_c = c
    p(f"   per-frame work: min {min(work_f):,}  mean {sum(work_f) / n:,.0f}  "
      f"max {max(work_f):,}   frames above 99% of 128,000: "
      f"{[ring[i]['frame'] for i in range(n) if work_f[i] > 0.99 * 128000]}")

    # ---- 4. per-TICK, with the frame-granularity bound stated -----------------------
    groups, cur = [], []
    for i in range(n):
        if ticked[i] and cur:
            groups.append(cur)
            cur = []
        cur.append(i)
    if cur:
        groups.append(cur)
    p("\n   -- 4. per-TICK cost. A tick begins PART WAY INTO the frame its Logic_Tick"
      " lands in, and the ladder can only cut at frame boundaries, so each tick is"
      " reported as a RANGE: lower = the frames strictly after its start frame, upper ="
      " every frame in its group. Both bounds are exact measurements; the tick's true"
      " cost is between them. --")
    p(f"   {'tick':>5} {'frames':>18} {'lower':>9} {'upper':>9} {'fillsub':>8}"
      f" {'S4LZ':>7} {'dec':>4}")
    over = []
    for j, g in enumerate(groups):
        up = sum(work_f[i] for i in g)
        low = sum(work_f[i] for i in g[1:]) if len(g) > 1 else up
        fl = sum(fill_f[i] for i in g)
        sz = sum(s4lz_f[i] for i in g)
        d = (cnts[g[-1]].get("Block_Stage_Gen", 0)
             - (cnts[g[0] - 1].get("Block_Stage_Gen", 0) if g[0]
                else b0["c0"].get("Block_Stage_Gen", 0)))
        # THE CRITERION IS THE OBSERVABLE, NOT A THRESHOLD. A tick "spiked" when it did
        # not fit in one video frame — measured directly as its group spanning more than
        # one frame (which is what frames_per_tick counts), not by comparing a derived
        # figure against 128,000. The bounds are printed beside it so the reader can see
        # how far past the line it is, but no number is being thresholded into a verdict.
        spiked = len(g) > 1
        flag = "  SPIKE (this tick did not fit in one frame)" if spiked else ""
        if spiked:
            over.append((j, low, up, [ring[i]["frame"] for i in g]))
        p(f"   {j:>5} {str([ring[i]['frame'] for i in g]):>18} {low:>9,} {up:>9,} "
          f"{fl:>8} {sz:>7} {d:>4}{flag}")
    inner = [sum(work_f[i] for i in g) for g in groups][1:-1] or \
            [sum(work_f[i] for i in g) for g in groups]
    p(f"   whole ticks (window's two partial ends dropped): n={len(inner)}  "
      f"min {min(inner):,}  mean {sum(inner) / len(inner):,.0f}  max {max(inner):,}")

    # ---- 5. the spike hunt's verdict -------------------------------------------------
    p("\n   -- 5. THE SPIKE TICKS (ticks that did not fit in one video frame), and what"
      " they have in common --")
    if not over:
        p("   no tick in this window spent more than one video frame.")
    for j, low, up, gf in over:
        i = gf.index(max(gf, key=lambda fr: s4lz_f[[x['frame'] for x in ring].index(fr)]))
        k = [x["frame"] for x in ring].index(gf[i])
        p(f"   tick {j:>3}  frames {gf}  work {low:,}..{up:,}  "
          f"S4LZ_DecompressDict {s4lz_f[k]:,} cyc in {s4lz_c[k]} calls "
          f"({s4lz_f[k] // max(1, s4lz_c[k]):,}/call)")
    s4lz_frames = [ring[i]["frame"] for i in spikes]
    p(f"   frames in which S4LZ_DecompressDict ran at all: {s4lz_frames}"
      f"   (of {n})")
    p(f"   block-grid crossings (C = Cache_Head_Col crossed a {BTS}-tile block edge,"
      f" R = Cache_Bottom_Row did): {blk_cross}")
    covered = [fr for fr in s4lz_frames
               if any(abs(fr - cf) <= 1 and "C" in m for cf, m in blk_cross)]
    p(f"   of those, within one frame of a COLUMN-edge crossing: {covered}"
      f"  -> {len(covered)}/{len(s4lz_frames)}")
    rowonly = [(fr, m) for fr, m in blk_cross if m == "R"]
    p(f"   ROW-edge crossings with no S4LZ run at all: "
      f"{[fr for fr, _m in rowonly if fr not in s4lz_frames]}"
      f"   (their blocks were already staged — the demand was served without a"
      f" dictionary decompress)")

    # ---- 6. stall --------------------------------------------------------------------
    p("\n   -- 6. stallCycles at this state, never absorbed into a cycle figure --")
    rows = sorted(pf["routines"]["items"], key=lambda r: -r["stallCyclesTotal"])
    tot_stall = sum(x["stallCycles"] for x in ring)
    p(f"   ring total {tot_stall} cyc over {n} frames = {tot_stall / n:.1f} cyc/frame"
      f"   per-frame min/max {min(x['stallCycles'] for x in ring)}/"
      f"{max(x['stallCycles'] for x in ring)}   (rows nest, so the row list below"
      f" double-counts by depth and is a LOCATION, not a second total)")
    for r in rows[:6]:
        if r["stallCyclesTotal"]:
            p(f"      {str(r.get('name', r['addr']))[:40]:40} {r['stallCyclesTotal']:>8} "
              f"({r['stallCyclesTotal'] / n:>7.1f}/frame)  of cycles "
              f"{r['cyclesTotal']}  -> stall-free {r['cyclesTotal'] - r['stallCyclesTotal']}")
    for b in ("hint", "vint"):
        i2 = pf["interrupts"][b]
        if i2["stallCyclesTotal"]:
            p(f"      {'interrupts.' + b:40} {i2['stallCyclesTotal']:>8} "
              f"({i2['stallCyclesTotal'] / n:>7.1f}/frame)")

    # ---- 7. the window's top rows ----------------------------------------------------
    p("\n   -- 7. top rows by cyclesSelf (ADDITIVE basis: these plus the interrupt"
      " buckets sum to the window, remainder 0) --")
    p(f"   {'ROUTINE':46} {'callsTot':>8} {'self/frame':>11} {'self/tick':>10}"
      f" {'incl/call':>11} {'stall':>7}")
    for r in sorted(pf["routines"]["items"], key=lambda r: -r["cyclesSelfTotal"])[:16]:
        pc = r["cyclesTotal"] / r["callsTotal"] if r["callsTotal"] else float("nan")
        p(f"   {str(r.get('name', r['addr']))[:46]:46} {r['callsTotal']:>8} "
          f"{r['cyclesSelfTotal'] / n:>11.1f} {r['cyclesSelfTotal'] / ticks:>10.1f} "
          f"{pc:>11.1f} {r['stallCyclesTotal']:>7}")
    for b in ("hint", "vint"):
        i2 = pf["interrupts"][b]
        p(f"   {'interrupts.' + b:46} {i2['callsTotal']:>8} "
          f"{i2['cyclesSelfTotal'] / n:>11.1f} {i2['cyclesSelfTotal'] / ticks:>10.1f} "
          f"{i2['cyclesTotal'] / i2['callsTotal'] if i2['callsTotal'] else 0:>11.1f} "
          f"{i2['stallCyclesTotal']:>7}")
    p("")
    return {"state": state, "frames": n, "ticks": ticks, "frames_per_tick": n / ticks,
            "work": work, "work_per_tick": work / ticks, "work_per_tick_boots": works,
            "work_frames": work_f, "fill_frames": fill_f, "s4lz_frames": s4lz_f,
            "s4lz_calls": s4lz_c, "spin_frames": spin_f, "ticked": ticked,
            "vint_separable": sep,
            "groups": [[ring[i]["frame"] for i in g] for g in groups],
            "group_work_upper": [sum(work_f[i] for i in g) for g in groups],
            "group_work_lower": [sum(work_f[i] for i in g[1:]) if len(g) > 1
                                 else sum(work_f[i] for i in g) for g in groups],
            "over_128k": over, "block_crossings": blk_cross,
            "ring": ring, "stall_per_frame": tot_stall / n,
            "rows": {r.get("name", r["addr"]): {q: r[q] for q in
                     ("cyclesTotal", "cyclesSelfTotal", "stallCyclesTotal", "callsTotal")}
                     for r in pf["routines"]["items"]},
            "interrupts": pf["interrupts"],
            "per_frame": [{str(k[1] or hex(k[0])): v for k, v in f.items()}
                          for f in frames],
            "counters": cnts}

async def resolve_syms(rom, lst):
    """Symbol addresses from the CURRENT build's listing, via the server's own resolver."""
    need = list(LONG_SYMS) + list(WORD_SYMS) + list(BYTE_SYMS) + list(SETUP_SYMS)
    out, missing = {}, []
    async with Server(rom, lst) as c:
        for nme in need:
            try:
                r = await c.call("emulator/lookup_symbol", {"name": nme})
                out[nme] = int(r["addr"], 16) & 0xFFFFFF
            except Exception:
                missing.append(nme)
    hard = [m for m in missing if m in LONG_SYMS or m in SETUP_SYMS]
    if hard:
        raise Setup(f"symbols missing from {lst}: {', '.join(hard)}")
    if missing:
        print(f"   note: optional counters absent from the listing: {', '.join(missing)}")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--rom", default="s4.debug.bin")
    ap.add_argument("--lst", default="s4.debug.lst")
    ap.add_argument("--state", default="maxdiag")
    ap.add_argument("--window", type=int, default=WINDOW)
    ap.add_argument("--boots", type=int, default=3)
    ap.add_argument("--no-control", action="store_true")
    ap.add_argument("--poison", choices=("control-rom", "identity", "prefix"), default=None)
    ap.add_argument("--json", default="")
    args = ap.parse_args()

    rom, lst = str(Path(args.rom).resolve()), str(Path(args.lst).resolve())
    if not Path(rom).exists() or not Path(lst).exists():
        print(f"missing {rom} or {lst}", file=sys.stderr)
        return 3
    import zlib
    d = Path(rom).read_bytes()
    t0 = time.time()
    print(f"ROM {rom}\n    crc32 {zlib.crc32(d) & 0xFFFFFFFF:08x}  len {len(d)}")
    print(f"instrument: {SERVER}")
    print(f"basis: cyclesSelf ADDITIVE (callees excluded) · cycles INCLUSIVE, preemption"
          f" excluded · stallCycles reported SEPARATELY, never absorbed\n")
    if args.poison:
        print(f"!! POISONED RUN (--poison {args.poison}) — this MUST exit 1\n")

    try:
        sym = asyncio.run(resolve_syms(rom, lst))
        if not args.no_control:
            scratch = Path(os.environ.get("TMPDIR", "/tmp")) / "s4.corpus.d22dda85.bin"
            corpus = recover_corpus_rom(scratch)
            print(f"-- CONTROL: the A/B's pinned rows on the A/B's own ROM "
                  f"(crc {CORPUS_CRC:08x}, from sigil {CORPUS_GOLDEN[1]}'s golden) --")
            log = asyncio.run(control(corpus, sym,
                                      poison_rom=rom if args.poison == "control-rom" else None))
            print("\n".join(log))
            print(f"   control took {time.time() - t0:.1f}s\n")
        elif args.poison == "control-rom":
            raise Blocked("--poison control-rom cannot fire with --no-control")

        boots = []
        for i in range(args.boots):
            tb = time.time()
            async def one():
                async with Server(rom, lst) as c:
                    return await measure_boot(c, sym, args.state, args.window,
                                              poison_prefix=(args.poison == "prefix"))
            b = asyncio.run(one())
            if args.poison == "identity":
                identity(b["direct"], poison=True)
            boots.append(b)
            print(f"   boot {i + 1}/{args.boots}: {args.window}-frame direct sample + "
                  f"{args.window}-rung prefix ladder in {time.time() - tb:.1f}s")
        print()
        res = report(args.state, boots)
        if args.json:
            Path(args.json).write_text(json.dumps(res, indent=1, default=str) + "\n")
            print(f"raw: {args.json}")
    except Blocked as e:
        print(f"\nBLOCKED: {e}", file=sys.stderr)
        return 1
    except Setup as e:
        print(f"\nSETUP: {e}", file=sys.stderr)
        return 3
    print(f"total wall {time.time() - t0:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
