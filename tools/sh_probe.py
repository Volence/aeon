#!/usr/bin/env python3
"""Probe oracle-next's pixel_attribution for the OJZ S/H question.

Question: with `fire(120, [reg_sh_on()])`, is "shadow band on BG but not FG"
correct hardware behaviour (FG plane pixels carry priority=1, so S/H leaves them
at full intensity) or an emulator defect?

Decisive datum: the per-candidate `priority` flag above vs below line 120.
"""
import asyncio, json, os, subprocess, sys, time

sys.path.insert(0, "/home/volence/sonic_hacks/empyrean/clients/python")
from aether import BusClient, BusError

ROM = "/home/volence/sonic_hacks/aeon/s4.debug.bin"
BIN = "/home/volence/sonic_hacks/oracle-next/target/release/oracle-aether"
SOCK = "/tmp/aeon_shprobe.sock"  # AF_UNIX paths cap at 108 bytes; scratchpad path is longer

ROWS = [40, 80, 110, 118, 119, 120, 121, 125, 150, 190, 215]
COLS = [40, 96, 160, 224, 288]


async def main(frames):
    if os.path.exists(SOCK):
        os.unlink(SOCK)
    proc = subprocess.Popen([BIN, ROM, "--socket", SOCK, "--no-pace"],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        for _ in range(100):
            if os.path.exists(SOCK):
                break
            time.sleep(0.05)
        c = BusClient(SOCK)
        await c.connect()
        await c.call("emulator/run_frames", {"frames": frames})
        st = await c.call("emulator/status", {})
        print("frameToken:", st.get("frameToken"), " pc:", st.get("symbolAtPc") or st.get("pc"))

        print("\nrow  col  winner      state     cram  | candidates (layer opaque prio)")
        rows_summary = {}
        for y in ROWS:
            prio_true = prio_false = 0
            for x in COLS:
                try:
                    a = await c.call("emulator/pixel_attribution", {"x": x, "y": y})
                except BusError as e:
                    print(f"{y:4d} {x:4d}  ERROR {e}")
                    continue
                cands = a.get("candidates", [])
                cs = " ".join(
                    "%s/%s/%s" % (cd.get("layer"), "op" if cd.get("opaque") else "--",
                                  "P1" if cd.get("priority") else "P0")
                    for cd in cands)
                for cd in cands:
                    if cd.get("layer") in ("planeA", "planeB", "PlaneA", "PlaneB"):
                        if cd.get("priority"):
                            prio_true += 1
                        else:
                            prio_false += 1
                print(f"{y:4d} {x:4d}  {str(a.get('winner')):11s} {a.get('state'):9s} "
                      f"{a.get('cramIndex')!s:5s} | {cs}")
            rows_summary[y] = (prio_true, prio_false)

        print("\nplane-candidate priority tally per row (P1, P0):")
        for y, (t, f) in rows_summary.items():
            print(f"  y={y:4d}  P1={t}  P0={f}")
        await c.close()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()


asyncio.run(main(int(sys.argv[1]) if len(sys.argv) > 1 else 600))
