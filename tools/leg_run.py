#!/usr/bin/env python3
"""leg_run — one leg, one shape, one phase, one JSON result (Empyrean v2 step 0, B2).

    python3 tools/leg_run.py --rom s4.bin --lst s4.lst --leg run --phase 0 --out DIR \\
        [--profile] [--dma-probe] [--cap N]

Writes DIR/<rom-stem>_<leg>_p<phase>.json with keys
    provenance, leg, phase, status, coverage{rule, got, need, met}, lag{frames, ticks},
    rows, input_log, profile, dma
(plus reason, notes, end, run{wall_s, ...}). The emulator is the pinned oracle
(`leg_provenance.spawn_pinned`, the only spawn the harness uses), and the result is refused
(`require_provenance`) before it is written if any provenance leaf is missing.

A section that was not asked for is recorded as {"status": "DID NOT RUN", "reason": ...},
never as null or zero. `--dma-probe` arms tools/vblank_dma_probe.py (B3) over the drive window
(from t0) on the same client: `dma = {sites, events, worst_end, overruns, unmeasurable, ...}`.

Exit: 0 written and coverage met (and, with --dma-probe, the probe measured and no DMA ended
past DMA_END_LIMIT_LINE + 0); 1 written but not met (STUCK / CAP / FAILED / a rule unmet / the
probe unmeasurable / an overrun); 2 could not run (nothing written).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import leg_drive as ld  # noqa: E402
import leg_provenance as lp  # noqa: E402
import vblank_dma_probe as vdp  # noqa: E402
from suite_paths import add_client_path  # noqa: E402

add_client_path()
from aether import BusError  # noqa: E402

#: A drive that dies on any of these produced no measurement: COULD NOT RUN (exit 2), and no
#: result file. DriveError = the driver refused (missed tick, no Input_Tick hit, ...); the rest
#: are the bus: a server error reply, or the connection dropping/timing out.
DRIVE_FAILURES = (ld.DriveError, BusError, ConnectionError, EOFError,
                  asyncio.IncompleteReadError, TimeoutError, OSError)

DEFAULT_CAP = {"idle": ld.IDLE_NEED_TICKS, "run": 3000, "topspeed": 3000, "diagfall": 3000,
               "spindash": 3000}


def _lfc_note(syms, tr) -> str:
    """DEBUG's second lag witness, LOUD when it disagrees with sum(dFC) - sum(dTick)."""
    if not syms.debug:
        return ""
    d = tr.lag_frame_count_delta
    if d == tr.lag_frames:
        return f"; LFC delta {d} (agrees)"
    return f"; LAG WITNESSES DISAGREE: Lag_Frame_Count delta {d} != {tr.lag_frames}"


def _did_not_run(reason: str) -> dict:
    return {"status": "DID NOT RUN", "reason": reason}


async def _profile_read(c, ticks: int, top: int = 512) -> dict:
    """leg_probe.py's read and identity check (sampleCycles = sum(self) + interrupts' self +
    unattributed). A non-zero remainder is RECORDED, never dropped."""
    pf = await c.call("emulator/get_profiler_frames", {"top": top, "topCallers": 4})
    await c.call("emulator/set_profiler", {"enabled": False})
    items = pf["routines"]["items"]
    selfsum = sum(r["cyclesSelfTotal"] for r in items) + sum(
        pf["interrupts"][k]["cyclesSelfTotal"] for k in ("hint", "vint"))
    return dict(status="MEASURED", ticks=ticks, sampleCycles=pf["sampleCycles"],
                frameCount=pf["frameCount"], unattributed=pf["unattributedCycles"],
                identity_remainder=pf["sampleCycles"] - selfsum - pf["unattributedCycles"],
                truncated=pf["routines"]["truncated"], abandoned=pf.get("abandonedFrames"),
                depthExceeded=pf.get("depthExceeded"), interrupts=pf["interrupts"], items=items)


async def run_leg(a, inst, syms, probe=None) -> dict:
    from aether import BusClient
    c = BusClient(socket_path=inst.socket_path, client_id=f"leg-run-{os.getpid()}",
                  client_name="leg_run")
    await c.connect()
    # A whole-leg profile reply with callers exceeds asyncio's 64 KiB line limit and the client
    # drops the connection (measured 2026-09-25 by leg_probe). Raise it.
    c._reader._limit = 64 * 1024 * 1024
    try:
        await c.call("emulator/reset", {})
        t0 = ld.T0 + ld.PHASE_OFFSETS[a.phase]
        policy = ld.POLICIES[a.leg](syms.buttons, syms.equ)
        armed = {"at": None}

        async def on_tick(s, row):
            if probe is not None:
                probe.tick = s.tick
            if armed["at"] is None:                     # arm over the drive window (from t0)
                if a.profile:
                    await c.call("emulator/set_profiler", {"enabled": True, "callers": True})
                if probe is not None:
                    await probe.arm(c)
                armed["at"] = s.tick

        tr = await ld.drive_leg(c, syms, policy, t0=t0, cap_ticks=a.cap, on_tick=on_tick,
                                on_break=None if probe is None else probe.on_break)
        if probe is not None:
            await probe.disarm(c)
        prof = (await _profile_read(c, tr.rows[-1]["t"] - armed["at"]) if a.profile
                else _did_not_run("--profile not given"))
    finally:
        await c.close()
    return dict(trace=tr, t0=t0, profile=prof)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--rom", required=True)
    ap.add_argument("--lst", required=True)
    ap.add_argument("--leg", required=True, choices=sorted(ld.POLICIES))
    ap.add_argument("--phase", required=True, type=int, choices=range(len(ld.PHASE_OFFSETS)))
    ap.add_argument("--out", required=True)
    ap.add_argument("--profile", action="store_true")
    ap.add_argument("--dma-probe", action="store_true")
    ap.add_argument("--cap", type=int, default=None)
    a = ap.parse_args(argv)
    if a.cap is None:
        a.cap = DEFAULT_CAP[a.leg]
    rom, lst = Path(a.rom).resolve(), Path(a.lst).resolve()
    try:
        syms = ld.resolve_syms(lst)
    except ld.DriveError as e:
        print(f"leg_run: COULD NOT RUN — {e}", file=sys.stderr)
        return 2
    probe = None
    if a.dma_probe:
        try:
            lst_text, rom_bytes = lst.read_text(errors="replace"), rom.read_bytes()
        except OSError as e:
            print(f"leg_run: COULD NOT RUN — {e}", file=sys.stderr)
            return 2
        probe = vdp.probe_for(lst_text, syms.addr, syms.equ, rom_bytes)
    wall0 = time.monotonic()
    load0 = open("/proc/loadavg").read().split()[:3]
    try:
        inst = lp.spawn_pinned(rom, lst)
    except lp.PinMismatch as e:
        print(f"leg_run: COULD NOT RUN — {e}", file=sys.stderr)
        return 2
    try:
        try:
            prov = lp.provenance(lp.load_pin(), inst.handshake, rom, lst)
        except (lp.StalePair, lp.PinMismatch) as e:
            print(f"leg_run: COULD NOT RUN — {e}", file=sys.stderr)
            return 2
        prov["harness"]["leg_drive_sha256"] = lp.sha256_file(TOOLS / "leg_drive.py")
        prov["harness"]["leg_run_sha256"] = lp.sha256_file(Path(__file__).resolve())
        if probe is not None:
            prov["harness"]["vblank_dma_probe_sha256"] = lp.sha256_file(TOOLS /
                                                                        "vblank_dma_probe.py")
            prov["harness"]["leg_correction_sha256"] = lp.sha256_file(TOOLS / "leg_correction.py")
        try:
            got = asyncio.run(run_leg(a, inst, syms, probe))
        except DRIVE_FAILURES as e:
            print(f"leg_run: COULD NOT RUN {type(e).__name__}: {e} (nothing written)",
                  file=sys.stderr)
            return 2
    finally:
        inst.reap()
    wall = time.monotonic() - wall0
    tr = got["trace"]
    cov = ld.coverage(a.leg, tr.status, tr.rows, syms.equ)
    lag = {"frames": tr.lag_frames, "ticks": tr.lag_ticks}
    if syms.debug:
        lag["lag_frame_count_delta"] = tr.lag_frame_count_delta
        lag["witnesses_agree"] = tr.lag_frame_count_delta == tr.lag_frames
    last = tr.rows[-1] if tr.rows else {}
    result = {
        "provenance": prov, "leg": a.leg, "phase": a.phase, "status": tr.status,
        "coverage": cov, "lag": lag, "rows": tr.rows, "input_log": tr.input_log,
        "profile": got["profile"],
        "dma": probe.result() if probe is not None else _did_not_run("--dma-probe not given"),
        "reason": tr.reason, "notes": tr.notes,
        "end": {k: last.get(k) for k in ("t", "px", "py", "cx", "cy", "cxm")},
        "run": {"t0": got["t0"], "cap_ticks": a.cap, "policy_from": tr.policy_from,
                "hits": tr.hits, "run_frames_misses": tr.misses, "probe_breaks": tr.breaks,
                "wall_s": round(wall, 2),
                "loadavg_start": load0, "loadavg_end": open("/proc/loadavg").read().split()[:3],
                "date_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())},
    }
    lp.require_provenance(result["provenance"])
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{rom.stem}_{a.leg}_p{a.phase}.json"
    path.write_text(json.dumps(result))
    lagpct = 100.0 * tr.lag_frames / max(1, tr.lag_frames + tr.lag_ticks)
    print(f"{rom.name} {a.leg} p{a.phase}: {tr.status} ({tr.reason}); coverage "
          f"{'MET' if cov['met'] else 'NOT MET'} got={cov['got']} need={cov['need']}; "
          f"end cx={last.get('cx')} cx_max={last.get('cxm')} (px,py)=({last.get('px')},"
          f"{last.get('py')}); lag {tr.lag_frames} frames / {tr.lag_ticks} ticks "
          f"({lagpct:.2f}%){_lfc_note(syms, tr)}"
          f"; wall {wall:.1f}s -> {path}")
    for n in tr.notes:
        print(f"  note: {n}")
    dma_ok = True
    if probe is not None:
        d = result["dma"]
        if d["unmeasurable"]:
            dma_ok = False
            print(f"  dma: UNMEASURABLE — {d['unmeasurable']}")
        else:
            w = d["worst_end"]
            where = ("no DMA in the window" if w["status"] == "NO DMA" else
                     f"worst last-DMA end line {w['line']} + {w['off']} mclk (tick {w['tick']})")
            dma_ok = not d["overruns"]
            print(f"  dma: {len(d['vblanks'])} VBlanks, {len(d['events'])} DMAs, {where}; "
                  f"{len(d['overruns'])} past line {d['limit']['line']} + 0"
                  + ("" if dma_ok else " — OVERRUN"))
    return 0 if cov["met"] and dma_ok else 1


if __name__ == "__main__":
    sys.exit(main())
