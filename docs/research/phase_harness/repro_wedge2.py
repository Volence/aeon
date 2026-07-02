#!/usr/bin/env python3
"""Wedge repro v2: boot, press Start into gameplay, hold Right (scroll load +
music + DAC), advance frames until a run_frames call stalls. On stall, dump
debug_arbiter and freeze for gdb."""
import asyncio
import json as jsonlib
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, "/home/volence/sonic_hacks/empyrean/clients/python")
from aether import BusClient  # noqa: E402

REPO = Path("/home/volence/sonic_hacks/oracle")
GUI = REPO / "linux-port" / "build" / "oracle_gui"
ROM = "/home/volence/sonic_hacks/aeon/s4.bin"
MAX_FRAMES = int(sys.argv[1]) if len(sys.argv) > 1 else 15000
TIMEOUT = 25.0

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


async def dump_arbiter(sock):
    try:
        b2 = BusClient(socket_path=str(sock), client_id="dbg", client_name="dbg")
        await b2.connect()
        st = await asyncio.wait_for(b2.call("emulator/debug_arbiter", {}), 10)
        print(jsonlib.dumps(st, indent=1), flush=True)
        await b2.close()
    except Exception as e:
        print(f"debug_arbiter failed: {e}", flush=True)


async def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="oracle-wedge2-"))
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

    async def run(n):
        nonlocal frame
        left = n
        while left > 0:
            chunk = min(10, left)
            try:
                await asyncio.wait_for(b.call("emulator/run_frames", {"frames": chunk}), TIMEOUT)
            except asyncio.TimeoutError:
                print(f"WEDGED at frame ~{frame} (run_frames timed out)", flush=True)
                out = subprocess.run(["pgrep", "-f", str(GUI)], capture_output=True, text=True)
                print(f"gui_pids={out.stdout.strip()}", flush=True)
                await dump_arbiter(sock)
                print("frozen for gdb; tmp NOT cleaned", flush=True)
                return False
            frame += chunk
            left -= chunk
            if frame % 1000 == 0:
                print(f"frame {frame} ok", flush=True)
        return True

    # boot/title
    if not await run(600):
        return 1
    # mash start a few times to get through title/menu
    for _ in range(4):
        try:
            await asyncio.wait_for(b.call("emulator/press", {"buttons": ["start"], "frames": 4}), 20)
        except Exception as e:
            print(f"press failed: {e}", flush=True)
        frame += 4
        if not await run(120):
            return 1
    # hold right for sustained scroll + streaming + music
    try:
        await asyncio.wait_for(b.call("emulator/hold", {"buttons": ["right"], "down": True}), 20)
    except Exception as e:
        print(f"hold failed: {e}", flush=True)
    if not await run(MAX_FRAMES - frame):
        return 1
    print(f"NO WEDGE in {frame} frames", flush=True)
    proc.terminate()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
