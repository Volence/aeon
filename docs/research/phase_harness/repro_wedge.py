#!/usr/bin/env python3
"""Reproduce the deterministic BR wedge headless, then freeze for gdb attach.

Launches an isolated headless oracle_gui (ORACLE_DETERMINISTIC=1), resets to the
deterministic anchor, then advances 1 frame at a time. If a run_frames call takes
longer than TIMEOUT seconds, we declare the wedge reproduced, print the PID, and
leave the process alive for gdb.
"""
import asyncio
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, "/home/volence/sonic_hacks/empyrean/clients/python")
from aether import BusClient  # noqa: E402

REPO = Path("/home/volence/sonic_hacks/oracle")
GUI = REPO / "linux-port" / "build" / "oracle_gui"
ROM = sys.argv[1] if len(sys.argv) > 1 else "/home/volence/sonic_hacks/aeon/s4.bin"
MAX_FRAMES = int(sys.argv[2]) if len(sys.argv) > 2 else 6000
TIMEOUT = 20.0

_SETTINGS = """<Settings>
<ModulesPath>{repo}/Data/Modules</ModulesPath>
<SavestatesPath>{tmp}/s</SavestatesPath>
<PersistentStatePath>{tmp}/p</PersistentStatePath>
<WorkspacesPath>{repo}/Data/Workspaces</WorkspacesPath>
<CapturesPath>{tmp}/c</CapturesPath>
<AssembliesPath>{repo}/Assemblies</AssembliesPath>
<DefaultSystem>MegaDriveTestSystemNoBios.xml</DefaultSystem>
<DefaultWorkspace>Mega Drive Clean.xml</DefaultWorkspace>
<EnableThrottling>1</EnableThrottling>
<RunWhenProgramModuleLoaded>1</RunWhenProgramModuleLoaded>
<EnablePersistentState>0</EnablePersistentState>
<LoadWorkspaceWithDebugState>0</LoadWorkspaceWithDebugState>
<ShowDebugConsole>0</ShowDebugConsole>
</Settings>
"""


async def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="oracle-wedge-"))
    for sub in ("s", "p", "c"):
        (tmp / sub).mkdir()
    (tmp / "settings.xml").write_text(_SETTINGS.format(repo=REPO, tmp=tmp))
    proc = subprocess.Popen(
        ["xvfb-run", "-a", "env", "-C", str(REPO),
         f"HOME={tmp}", f"XDG_RUNTIME_DIR={tmp}",
         "SDL_AUDIODRIVER=dummy", "LIBGL_ALWAYS_SOFTWARE=1",
         "ORACLE_DETERMINISTIC=1",
         str(GUI), str(tmp / "settings.xml"), ROM],
        stdout=open(tmp / "gui.log", "w"), stderr=subprocess.STDOUT)
    sock = tmp / "oracle.sock"
    print(f"tmp={tmp} launcher_pid={proc.pid}", flush=True)
    for _ in range(120):
        if sock.exists():
            break
        time.sleep(0.5)
    if not sock.exists():
        print("FAIL: socket never appeared", flush=True)
        return 2
    time.sleep(5.0)

    b = BusClient(socket_path=str(sock), client_id="wedge", client_name="wedge")
    await b.connect()
    await b.call("emulator/reset", {"wait": True, "run": False})
    frame = 0
    while frame < MAX_FRAMES:
        try:
            await asyncio.wait_for(b.call("emulator/run_frames", {"frames": 10}), TIMEOUT)
        except asyncio.TimeoutError:
            print(f"WEDGED at frame ~{frame} (run_frames timed out after {TIMEOUT}s)", flush=True)
            # find the real gui pid (xvfb-run wraps it)
            out = subprocess.run(["pgrep", "-f", str(GUI)], capture_output=True, text=True)
            print(f"gui_pids={out.stdout.strip()}", flush=True)
            print("Process left alive for gdb. tmp dir NOT cleaned.", flush=True)
            # try grabbing arbiter state via a second connection (socket thread should live)
            try:
                b2 = BusClient(socket_path=str(sock), client_id="dbg", client_name="dbg")
                await b2.connect()
                st = await asyncio.wait_for(b2.call("emulator/debug_arbiter", {}), 10)
                import json
                print(json.dumps(st, indent=1), flush=True)
                await b2.close()
            except Exception as e:
                print(f"debug_arbiter failed: {e}", flush=True)
            return 1
        frame += 10
        if frame % 500 == 0:
            print(f"frame {frame} ok", flush=True)
    print(f"NO WEDGE in {MAX_FRAMES} frames", flush=True)
    proc.terminate()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
