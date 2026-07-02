"""Launch an isolated, headless throwaway oracle_gui instance for the harness.

Isolated XDG_RUNTIME_DIR + HOME so the socket never collides with a user's
running instance; software GL + dummy audio + xvfb for headless determinism.
"""
import os, shutil, subprocess, tempfile, time
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]            # .../oracle
GUI  = REPO / "linux-port" / "build" / "oracle_gui"

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

@contextmanager
def headless_emulator(rom_path: str, boot_wait: float = 5.0):
    """Yield the bus socket path for a freshly-booted isolated instance."""
    tmp = Path(tempfile.mkdtemp(prefix="oracle-harness-"))
    for sub in ("s", "p", "c"):
        (tmp / sub).mkdir()
    (tmp / "settings.xml").write_text(_SETTINGS.format(repo=REPO, tmp=tmp))
    proc = subprocess.Popen(
        ["xvfb-run", "-a", "env", "-C", str(REPO),
         f"HOME={tmp}", f"XDG_RUNTIME_DIR={tmp}",
         "SDL_AUDIODRIVER=dummy", "LIBGL_ALWAYS_SOFTWARE=1",
         # Spike: force deterministic single-threaded device execution.
         "ORACLE_DETERMINISTIC=0",
         str(GUI), str(tmp / "settings.xml"), rom_path],
        stdout=open(tmp / "gui.log", "w"), stderr=subprocess.STDOUT)
    sock = tmp / "oracle.sock"
    try:
        for _ in range(120):
            if sock.exists():
                break
            time.sleep(0.5)
        if not sock.exists():
            raise RuntimeError(f"socket never appeared; see {tmp}/gui.log")
        time.sleep(boot_wait)
        yield str(sock)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        shutil.rmtree(tmp, ignore_errors=True)
