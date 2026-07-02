#!/usr/bin/env python3
"""Wedge repro v3: FREE-RUN (RunSystem path, like the live GUI) with periodic
input, polling status for a frozen frame counter. On freeze: dump debug_arbiter
and leave the process alive for gdb."""
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
MINUTES = float(sys.argv[1]) if len(sys.argv) > 1 else 10.0

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
    tmp = Path(tempfile.mkdtemp(prefix="oracle-wedge3-"))
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
    print(f"tmp={tmp}", flush=True)
    for _ in range(120):
        if sock.exists():
            break
        time.sleep(0.5)
    time.sleep(5.0)

    b = BusClient(socket_path=str(sock), client_id="w3", client_name="w3")
    await b.connect()
    # free-run (RunWhenProgramModuleLoaded already runs it; make sure)
    try:
        await asyncio.wait_for(b.call("emulator/resume", {}), 10)
    except Exception as e:
        print(f"resume: {e}", flush=True)

    async def token():
        st = await asyncio.wait_for(b.call("emulator/status", {}), 10)
        return st.get("frame_token"), st

    last = None
    stuck_count = 0
    t0 = time.time()
    i = 0
    while time.time() - t0 < MINUTES * 60:
        await asyncio.sleep(2.0)
        i += 1
        try:
            tok, st = await token()
        except asyncio.TimeoutError:
            print("status op timed out!", flush=True)
            tok, st = last, None
        if tok == last:
            stuck_count += 1
            print(f"[{int(time.time()-t0)}s] frame_token STUCK at {tok} ({stuck_count})", flush=True)
            if stuck_count >= 3:
                print("WEDGE DETECTED", flush=True)
                out = subprocess.run(["pgrep", "-f", str(GUI)], capture_output=True, text=True)
                print(f"gui_pids={out.stdout.strip()}", flush=True)
                try:
                    b2 = BusClient(socket_path=str(sock), client_id="dbg", client_name="dbg")
                    await b2.connect()
                    stt = await asyncio.wait_for(b2.call("emulator/debug_arbiter", {}), 10)
                    print(jsonlib.dumps(stt, indent=1), flush=True)
                    await b2.close()
                except Exception as e:
                    print(f"debug_arbiter failed: {e}", flush=True)
                print("left alive for gdb", flush=True)
                return 1
        else:
            stuck_count = 0
            if i % 15 == 0:
                print(f"[{int(time.time()-t0)}s] token={tok}", flush=True)
        last = tok
    print("NO WEDGE (free-run)", flush=True)
    proc.terminate()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
