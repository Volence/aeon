#!/usr/bin/env python3
"""Boot headless, take screenshots at stages to see what state the game reaches."""
import asyncio
import base64
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
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/tmp/peek")

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


async def shot(b, name):
    r = await b.call("emulator/screenshot", {})
    OUT.mkdir(parents=True, exist_ok=True)
    p = r.get("path")
    if p:
        import shutil
        shutil.copy(p, OUT / f"{name}.png")
        print(f"wrote {OUT}/{name}.png", flush=True)
    else:
        print(f"screenshot keys: {list(r.keys())}", flush=True)


async def main():
    tmp = Path(tempfile.mkdtemp(prefix="oracle-peek-"))
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
    for _ in range(120):
        if sock.exists():
            break
        time.sleep(0.5)
    time.sleep(5)
    b = BusClient(socket_path=str(sock), client_id="peek", client_name="peek")
    await b.connect()
    await b.call("emulator/reset", {"wait": True, "run": False})
    await b.call("emulator/run_frames", {"frames": 300})
    await shot(b, "f300")
    await b.call("emulator/press", {"buttons": ["start"], "frames": 4})
    await b.call("emulator/run_frames", {"frames": 180})
    await shot(b, "f484_after_start")
    await b.call("emulator/press", {"buttons": ["start"], "frames": 4})
    await b.call("emulator/run_frames", {"frames": 300})
    await shot(b, "f788")
    # check z80 pc moving (sound driver alive?)
    r1 = await b.call("emulator/z80_registers", {})
    await b.call("emulator/run_frames", {"frames": 10})
    r2 = await b.call("emulator/z80_registers", {})
    print("z80 r1:", {k: r1.get(k) for k in ("pc", "PC")}, flush=True)
    print("z80 r2:", {k: r2.get(k) for k in ("pc", "PC")}, flush=True)
    proc.terminate()


if __name__ == "__main__":
    asyncio.run(main())
