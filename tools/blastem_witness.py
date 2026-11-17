#!/usr/bin/env python3
"""blastem_witness — BlastEm as the second witness for a close Oracle call (Empyrean v2, B4).

    python3 tools/blastem_witness.py --rom s4.bin --lst s4.lst --result OUT/s4_run_p0.json \\
        [--ticks N] [--deadline 540]

WHY. Oracle omits the 68000 refresh and the Z80 bank stalls (tools/leg_correction.py), so a
"fits" with a corrected margin under 3 % of its budget is not a verdict on Oracle alone
(`leg_correction.classify` -> NEEDS-WITNESS). This tool replays a leg_run result's `input_log`
OPEN-LOOP on BlastEm 0.6.2, keyed to `Logic_Tick` at the same `Input_Tick` seam leg_drive uses,
and compares lag and path tick by tick. BlastEm is a second MODEL, not hardware: agreement
raises confidence, it does not prove the cart fits on a console.

HOW (the Oracle-fitness audit's proven drive, audit-builds/oracle/blastem/drive_blastem.py):
BlastEm runs as a GDB-RSP stub (`blastem ROM -D -g` under xvfb-run), spoken to through
oracle/tools/blastem-differential/rsp.py and never by opening BlastEm's source. One `Z0`
breakpoint at `Input_Tick` (a breakpoint, not a pc write: `P` for pc is unsupported); on each
hit the tool reads Frame_Counter/Logic_Tick, and from t0 writes `held` from the log and
`press = held & ~prev` to Ctrl_1_Held / Ctrl_1_Press, then continues. Before t0 nothing is
written, exactly as on Oracle. A lag frame has no hit. Every address is resolved by symbol from
the build's listing (leg_drive.resolve_syms).

LIMITS. The stub has no cycle counter: the witness is lag-level and path-level only. PAL
(`blastem -r E`) is not built here.

Writes `<result>.blastem.json`. Exit 0 the witness agrees; 1 it ran and disagrees (or did not
cover the leg); 2 COULD NOT RUN (the file is still written, status COULD NOT RUN, with the
stderr tail).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import NamedTuple

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import leg_drive as ld  # noqa: E402
import leg_provenance as lp  # noqa: E402
from suite_paths import require_suite_path  # noqa: E402

BLASTEM_VERSION = "0.6.2"
#: Seconds one wait for an Input_Tick hit may take before the stub is called wedged.
HIT_TIMEOUT_S = 10.0
#: The whole replay's own deadline (the run is capped at 600 s; this leaves room to write).
DEFAULT_DEADLINE_S = 540


class WitnessError(RuntimeError):
    """The witness cannot answer (missed tick, stub wedged, no overlap). Never a verdict."""


class WitnessRow(NamedTuple):
    tick: int
    frame_counter: int
    cx: int
    cy: int
    px: int
    py: int


@dataclass(frozen=True)
class WitnessResult:
    path_agree_ticks: int            # leading common ticks whose (cx, cy, px, py) agree
    first_divergent_tick: int | None
    lag_oracle: int                  # lag frames over the common ticks, each side's own count
    lag_blastem: int
    extra_lag_ticks: tuple           # ticks whose lag (dFC - dTick) differs between the two
    common_ticks: int = 0
    oracle_ticks: int = 0

    def agrees(self) -> bool:
        """Same lag, same path, over every tick the Oracle leg drove."""
        return (self.first_divergent_tick is None and self.lag_oracle == self.lag_blastem
                and not self.extra_lag_ticks and self.common_ticks > 0
                and self.common_ticks >= self.oracle_ticks
                and self.path_agree_ticks == self.common_ticks)


# ---- compare ------------------------------------------------------------------------------

def _norm(rows):
    """-> ({tick: (cx, cy, px, py)}, {tick: lag contribution}, row count)."""
    pos, lag, fc = {}, {}, {}
    for r in rows:
        if isinstance(r, dict):
            t = r["t"]
            pos[t] = (r["cx"], r["cy"], r["px"], r["py"])
            fc[t] = r["fc"]
            if "dfc" in r:
                lag[t] = r["dfc"] - r.get("dlt", 1)
        else:
            t = r.tick
            pos[t] = (r.cx, r.cy, r.px, r.py)
            fc[t] = r.frame_counter
    for t in fc:
        if t not in lag and t - 1 in fc:
            lag[t] = ((fc[t] - fc[t - 1]) & 0xFFFF) - 1
    return pos, lag, len(rows)


def compare(oracle_rows, blastem_rows) -> WitnessResult:
    """Tick-keyed comparison. Oracle rows may be leg_run row dicts or WitnessRows."""
    po, lo, n_o = _norm(oracle_rows)
    pb, lb, _ = _norm(blastem_rows)
    common = sorted(set(po) & set(pb))
    if not common:
        raise WitnessError("the two traces share no tick: nothing to compare")
    first, agree = None, 0
    for t in common:
        if po[t] != pb[t]:
            first = t
            break
        agree += 1
    lag_ticks = sorted(set(lo) & set(lb) & set(common))
    return WitnessResult(
        path_agree_ticks=agree, first_divergent_tick=first,
        lag_oracle=sum(lo[t] for t in lag_ticks), lag_blastem=sum(lb[t] for t in lag_ticks),
        extra_lag_ticks=tuple(t for t in lag_ticks if lo[t] != lb[t]),
        common_ticks=len(common), oracle_ticks=n_o)


# ---- the open-loop replay -----------------------------------------------------------------

def _be(b: bytes, n: int = None) -> int:
    return int.from_bytes(b if n is None else b[:n], "big")


def _rd(stub, addr: int, n: int) -> bytes:
    b = stub.read_mem(addr & 0xFFFFFF, n)
    if b is None or len(b) < n:
        raise WitnessError(f"read ${addr:06X},{n}: no reply from the stub")
    return b


def _fc_lt(stub, a) -> tuple[int, int]:
    if a["Logic_Tick"] == a["Frame_Counter"] + 2:
        m = _rd(stub, a["Frame_Counter"], 6)
        return _be(m[0:2]), _be(m[2:6])
    return _be(_rd(stub, a["Frame_Counter"], 2)), _be(_rd(stub, a["Logic_Tick"], 4))


def _state(stub, syms, tick: int, fc: int) -> WitnessRow:
    a, o = syms.addr, syms.off
    cx = _be(_rd(stub, a["Camera_X"], 2))
    cy = _be(_rd(stub, a["Camera_Y"], 2))
    tgt = _be(_rd(stub, a["Camera_Target"], 2))
    leader = (0xFF0000 | tgt) if tgt & 0x8000 else tgt
    px = py = 0
    if leader:
        p = _rd(stub, leader, max(o["x_pos"], o["y_pos"]) + 2)
        px, py = _be(p[o["x_pos"]:o["x_pos"] + 2]), _be(p[o["y_pos"]:o["y_pos"] + 2])
    return WitnessRow(tick, fc, cx, cy, px, py)


def _write_pad(stub, a, held: int, press: int):
    if a["Ctrl_1_Press"] == a["Ctrl_1_Held"] + 1:
        ok = stub.write_mem(a["Ctrl_1_Held"], bytes([held, press]))
    else:
        ok = stub.write_mem(a["Ctrl_1_Held"], bytes([held])) and \
            stub.write_mem(a["Ctrl_1_Press"], bytes([press]))
    if not ok:
        raise WitnessError("pad write: no reply from the stub")


def replay(stub, syms, input_log: dict, n_ticks: int, deadline: float | None = None,
           hit_timeout: float = HIT_TIMEOUT_S) -> list[WitnessRow]:
    """Drive a ready stub from power-on. Returns the t0-1 baseline row plus one row per tick
    t0 .. t0+n_ticks-1, each read at the Input_Tick hit BEFORE that tick's pad write."""
    t0, held_log = int(input_log["t0"]), list(input_log["held"])
    if n_ticks < 1 or n_ticks > len(held_log):
        raise WitnessError(f"n_ticks {n_ticks}: the input log holds {len(held_log)} ticks")
    if t0 < 2:
        raise WitnessError(f"t0 {t0}: no t0-1 baseline hit to key lag against")
    a = syms.addr
    stub.bp(a["Input_Tick"])
    rows, prev_tick, prev_held, last = [], None, 0, t0 + n_ticks - 1
    while True:
        if deadline is not None and time.monotonic() > deadline:
            raise WitnessError(f"deadline passed at tick {prev_tick} ({len(rows)} rows)")
        rep, timed_out = stub.cont_or_interrupt(hit_timeout)
        if timed_out or not rep:
            raise WitnessError(f"no Input_Tick hit within {hit_timeout}s after tick "
                               f"{prev_tick} (reply {rep!r})")
        fc, tick = _fc_lt(stub, a)
        if prev_tick is not None and tick != prev_tick + 1:
            raise WitnessError(f"tick {prev_tick} -> {tick}: an Input_Tick hit was missed or "
                               "repeated (ticks are the only index)")
        if prev_tick is None and tick > t0 - 1:
            raise WitnessError(f"first hit at tick {tick}, past the t0-1={t0 - 1} baseline")
        prev_tick = tick
        if tick < t0 - 1:
            continue
        rows.append(_state(stub, syms, tick, fc))
        if tick < t0:
            continue
        held = held_log[tick - t0] & 0xFF
        press = held & ~prev_held & 0xFF
        prev_held = held
        _write_pad(stub, a, held, press)
        if tick >= last:
            return rows


def blastem_binary() -> Path:
    return require_suite_path("emulators", "blastem64-0.6.2", "blastem")


def _rsp_module():
    d = require_suite_path("oracle", "tools", "blastem-differential")
    if str(d) not in sys.path:
        sys.path.insert(0, str(d))
    import rsp
    return rsp


def run_blastem(rom: Path, lst: Path, input_log: dict, n_ticks: int,
                deadline_s: float = DEFAULT_DEADLINE_S, stderr_path: Path | None = None,
                syms=None) -> list[WitnessRow]:
    """Boot `rom` on BlastEm from power-on and replay `input_log` open-loop, keyed to tick.
    BlastEm's stderr goes to `stderr_path` (rsp.py discards it; the launch itself is rsp.py's
    own command line, untouched)."""
    syms = syms or ld.resolve_syms(Path(lst))
    rsp = _rsp_module()
    os.environ["BLASTEM"] = str(blastem_binary())
    rsp.BLASTEM = os.environ["BLASTEM"]
    rsp.watchdog(int(deadline_s) + 30)             # backstop if the stub wedges in a read
    real_popen = rsp.subprocess.Popen
    err = open(stderr_path, "wb") if stderr_path else subprocess.DEVNULL

    def popen(*a, **kw):
        kw["stderr"] = err
        return real_popen(*a, **kw)

    rsp.subprocess.Popen = popen
    try:
        stub = rsp.RSP(str(rom))
    finally:
        rsp.subprocess.Popen = real_popen
    try:
        stub.wait_ready()
        return replay(stub, syms, input_log, n_ticks,
                      deadline=time.monotonic() + deadline_s)
    finally:
        stub.close()
        if stderr_path:
            err.close()
        import signal
        signal.alarm(0)


# ---- CLI ----------------------------------------------------------------------------------

def _tail(p: Path, n: int = 20) -> list[str]:
    try:
        return p.read_text(errors="replace").splitlines()[-n:]
    except OSError:
        return []


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--rom", required=True)
    ap.add_argument("--lst", required=True)
    ap.add_argument("--result", required=True, help="a leg_run result JSON")
    ap.add_argument("--ticks", type=int, default=None, help="default: the whole input log")
    ap.add_argument("--deadline", type=float, default=DEFAULT_DEADLINE_S)
    a = ap.parse_args(argv)
    rom, lst, res_path = Path(a.rom).resolve(), Path(a.lst).resolve(), Path(a.result).resolve()
    out = res_path.with_name(res_path.name + ".blastem.json")
    try:
        result = json.loads(res_path.read_text())
        log, oracle_rows = result["input_log"], result["rows"]
        rom_prov = lp.rom_provenance(rom, lst)
        want = result["provenance"]["rom"]
        if (rom_prov["crc32"], rom_prov["size"]) != (want["crc32"], want["size"]):
            raise WitnessError(f"{rom.name} crc32 {rom_prov['crc32']} size {rom_prov['size']} "
                               f"!= the result's ROM {want['crc32']} / {want['size']}")
        syms = ld.resolve_syms(lst)
        bin_ = blastem_binary()
    except (OSError, KeyError, ValueError, WitnessError, ld.DriveError, lp.StalePair) as e:
        print(f"blastem_witness: COULD NOT RUN — {type(e).__name__}: {e} (nothing written)",
              file=sys.stderr)
        return 2
    n = a.ticks or len(log["held"])
    prov = {"oracle_result": {"path": str(res_path), "provenance": result["provenance"]},
            "aeon": lp.aeon_provenance(), "rom": rom_prov,
            "blastem": {"binary": str(bin_), "sha256": lp.sha256_file(bin_),
                        "version": BLASTEM_VERSION, "rsp": "oracle/tools/blastem-differential"
                                                          "/rsp.py"},
            "harness": {"tool_sha256": lp.sha256_file(Path(__file__).resolve()),
                        "leg_correction_sha256": lp.sha256_file(TOOLS / "leg_correction.py")}}
    rec = {"provenance": prov, "leg": result.get("leg"), "phase": result.get("phase"),
           "t0": log["t0"], "n_ticks": n, "mode": "open-loop replay keyed to Logic_Tick"}
    wall0 = time.monotonic()
    with tempfile.NamedTemporaryFile(prefix="blastem-stderr-", suffix=".log",
                                     dir=str(out.parent), delete=False) as f:
        errp = Path(f.name)
    try:
        rows = run_blastem(rom, lst, log, n, deadline_s=a.deadline, stderr_path=errp, syms=syms)
    except (WitnessError, RuntimeError, OSError, AssertionError, SystemExit) as e:
        rec.update(status="COULD NOT RUN", reason=f"{type(e).__name__}: {e}",
                   stderr_tail=_tail(errp), wall_s=round(time.monotonic() - wall0, 2))
        out.write_text(json.dumps(rec, indent=1))
        errp.unlink(missing_ok=True)
        print(f"blastem_witness: COULD NOT RUN — {rec['reason']}; stderr tail: "
              f"{rec['stderr_tail'][-5:]} -> {out}", file=sys.stderr)
        return 2
    wall = time.monotonic() - wall0
    tail = _tail(errp)
    errp.unlink(missing_ok=True)
    # Compare only the ticks the witness was asked to replay.
    o_rows = [r for r in oracle_rows if r["t"] < log["t0"] + n]
    w = compare(o_rows, rows)
    rec.update(status="MEASURED", wall_s=round(wall, 2), stderr_tail=tail,
               comparison=asdict(w) | {"agrees": w.agrees()},
               oracle_lag_result=result.get("lag"),
               rows=[list(r) for r in rows])
    out.write_text(json.dumps(rec))
    print(f"blastem_witness {rom.name} {rec['leg']} p{rec['phase']}: "
          f"{'AGREES' if w.agrees() else 'DISAGREES'}; path_agree_ticks {w.path_agree_ticks}"
          f"/{w.common_ticks} common (oracle {w.oracle_ticks} rows); first_divergent_tick "
          f"{w.first_divergent_tick}; lag oracle {w.lag_oracle} blastem {w.lag_blastem}; "
          f"extra_lag_ticks {list(w.extra_lag_ticks)[:20]}; wall {wall:.1f}s -> {out}")
    return 0 if w.agrees() else 1


if __name__ == "__main__":
    sys.exit(main())
