#!/usr/bin/env python3
"""Post-fix smoke: gameplay frames + held-right scroll, then dump debug_arbiter
(clamp counters + pending buffers)."""
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
FRAMES = int(sys.argv[1]) if len(sys.argv) > 1 else 2000

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
    tmp = Path(tempfile.mkdtemp(prefix="oracle-smoke-"))
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
    time.sleep(5.0)

    b = BusClient(socket_path=str(sock), client_id="smoke", client_name="smoke")
    await b.connect()
    await b.call("emulator/reset", {"wait": True, "run": False})
    await asyncio.wait_for(b.call("emulator/run_frames", {"frames": 120}), 30)
    await asyncio.wait_for(b.call("emulator/hold", {"buttons": ["right"], "down": True}), 20)
    done = 120
    while done < FRAMES:
        try:
            await asyncio.wait_for(b.call("emulator/run_frames", {"frames": 20}), 30)
        except asyncio.TimeoutError:
            print(f"WEDGED at frame ~{done}", flush=True)
            st = await asyncio.wait_for(b.call("emulator/debug_arbiter", {}), 10)
            print(jsonlib.dumps(st, indent=1), flush=True)
            return 1
        done += 20
        if done % 500 == 0:
            print(f"frame {done} ok", flush=True)
    st = await asyncio.wait_for(b.call("emulator/debug_arbiter", {}), 10)
    vdp = st.get("vdp", {})
    arb = st.get("arbiter", {})
    m68 = st.get("m68000", {})
    print("SMOKE PASS", flush=True)
    print("vdp:", {k: vdp.get(k) for k in ("dma_transfer_active", "bus_granted",
          "execute_timeslice_count", "det_heal_block_runs", "det_clamped_br_releases")}, flush=True)
    print("arbiter:", {k: arb.get(k) for k in ("m68k_bus_request_line_state",
          "m68k_bus_grant_line_state", "det_clamped_handshake_times",
          "pending_line_count")}, flush=True)
    print("m68000:", {k: m68.get(k) for k in ("br_line_state", "bg_line_state",
          "pending_line_count")}, flush=True)
    proc.terminate()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
