#!/usr/bin/env python3
"""aether_instance — the ONE way an aeon gate spawns its own headless emulator.

WHY THIS EXISTS. Every emulator-backed gate in this tree used to spawn its own server, and
they did it two different ways: five went through `launcher.headless_emulator` in
`oracle-old/linux-port/harness` (which boots the legacy C++ `oracle_gui` under `xvfb-run`),
and three (`vsplit_landing_gate`, `warp_mailbox_gate`, `boot_override_gate`) each carried
their OWN hand-copied `Server` class for the Rust `oracle-aether`. Three copies of a spawn
loop is three places for a leak to hide, and the legacy half carried a measured defect: the
C++ server free-runs after boot and is stopped by a race, which WEDGED the `raster_source`
segment twice at 240 s each on 2026-08-25 and only passed on a hand `--only` retry.

The Rust server removes that race BY CONSTRUCTION, and this module is the seam that makes it
the default: it boots PAUSED at frame 0, and `run_frames` / `run_to` are synchronous and
bounded — they RETURN when the condition is met. There is nothing to race with.

Owner ruling 2026-08-26 (empyrean 3c21183): the Rust core is the default instrument;
`oracle_gui` is FALLBACK ONLY.

THE ASSERTION IS THE POINT. `assert_rust_server()` runs on every spawn, so a gate cannot
silently end up on the legacy server — which is the exact failure this module exists to make
impossible, and the failure that would make every timing and stop-PC claim downstream of it
wrong without anything going red.

    MEASURED HANDSHAKES, 2026-08-26, both binaries AS SHIPPED on this machine:

      field                     oracle-aether (Rust)      oracle_gui (legacy C++)
      implementation            ABSENT                    ABSENT
      serverBuild               ABSENT                    ABSENT
      serverName                "oracle-next"             "oracle"
      serverVersion             "0.0.0"                   "2.1-linux"
      capabilities.breakpoints  false (present)           ABSENT
      len(methods)              41                        53

    ⚠ `implementation` / `serverBuild` are NOT YET on the wire. Oracle committed them
    (`bc2cddd`, "the handshake says which implementation answered", merged 2026-08-26) but
    the RELEASE BINARIES here predate it — both were built 2026-08-25 21:03. So an assertion
    written only against `implementation == "oracle-rs"` would refuse the correct server
    today and block the whole lane. Hence TWO RUNGS, in this order:

      1. `implementation` present  -> it MUST equal "oracle-rs". Nothing else passes.
         (Forward-compatible: the day oracle's binaries are rebuilt, this is the live rung
         and rung 2 stops being consulted.)
      2. `implementation` absent   -> `serverName` MUST equal "oracle-next", the measured
         structural discriminator above. The legacy server answers "oracle" and is refused.

    Rung 2 is a fallback for a STALE BINARY, not a permanent second answer. When oracle's
    release binaries carry `implementation`, delete rung 2 and its test — and until then, do
    not weaken rung 1 to match it.

    Proof it fires: `tools/test_aether_instance.py` drives both rungs off the recorded
    handshakes above, and `python3 tools/aether_instance.py --poison-legacy` spawns a REAL
    legacy `oracle_gui`, hands its handshake to this module, and fails if it is accepted.

WHAT DIFFERS FROM THE LEGACY SEAM — every one of these is measured, not read:

  * `emulator/reset` takes NO PARAMS. The legacy `{"wait": True, "run": False}` is refused
    with -32602 (protocol §2.5 rejects undeclared keys). It is also unnecessary: the Rust
    server resets to a STOPPED machine, which is what those two params were asking for.
  * The bus is 24 BITS. `0xFFFF0000` is refused with -32004; `0xFF0000` is the same byte.
    `parse_lst` already yields 24-bit addresses, so converted gates needed no change.
  * `capabilities.breakpoints` is FALSE — `breakpoint_add` / `wait_for_break` do not exist.
    Use `emulator/run_to {"addr"|"symbol", "maxFrames"}`, which is synchronous and reports
    `reached` (see `run_to_addr` below).
  * `limits.maxRunFrames` is 3600 here, so a 180-frame settle is one call.
  * There is no `deterministic=` knob and none is needed: the Rust core has no threaded
    device schedule to opt out of, and `run_to` stops on the exact instruction — which is
    precisely what `deterministic=False` was bought for on the legacy server.

Usage (drop-in for `with headless_emulator(rom) as sock:`):

    from aether_instance import aether_emulator
    with aether_emulator(rom, symbols=lst) as sock:
        ...BusClient(socket_path=sock)...

Self-test / poison:
    python3 tools/aether_instance.py --smoke [--rom R] [--lst L]
    python3 tools/aether_instance.py --poison-legacy [--rom R]
"""
from __future__ import annotations

import argparse
import asyncio
import contextlib
import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, "/home/volence/sonic_hacks/empyrean/clients/python")
from aether import BusClient  # noqa: E402

# `oracle-next` is a SYMLINK to `oracle` on this machine, so the three already-aether gates
# that spell the path the other way run the same binary. Spelled the owner-ruled way here.
SERVER = Path("/home/volence/sonic_hacks/oracle/target/release/oracle-aether")

READY_TIMEOUT_S = 15.0    # generous: measured ready time is ~0.06 s
READY_POLL_S = 0.05
REAP_TERM_TIMEOUT_S = 3.0

# The two rungs of the identity assertion. See the module docstring for how they were measured.
WANT_IMPLEMENTATION = "oracle-rs"
WANT_SERVER_NAME = "oracle-next"


class WrongServerError(RuntimeError):
    """The handshake did not come from the Rust core. Never caught to continue anyway."""


class SpawnError(RuntimeError):
    """The server could not be started; the message names why and quotes its output."""


def assert_rust_server(info: dict) -> None:
    """Raise WrongServerError unless `info` is an `initialize` reply from oracle-aether.

    PURE — takes the handshake dict, touches nothing else. That is what lets both rungs be
    tested against recorded handshakes from both real servers without booting either.
    """
    impl = info.get("implementation")
    if impl is not None:
        if impl != WANT_IMPLEMENTATION:
            raise WrongServerError(
                f"this gate requires the Rust core, but the server answered "
                f"implementation={impl!r} (want {WANT_IMPLEMENTATION!r}). "
                f"serverName={info.get('serverName')!r} "
                f"serverBuild={info.get('serverBuild')!r}"
            )
        return
    # Rung 2 — stale-binary fallback, see the docstring. Delete when oracle's release
    # binaries carry `implementation`.
    name = info.get("serverName")
    if name != WANT_SERVER_NAME:
        raise WrongServerError(
            f"this gate requires the Rust core. The handshake carries no `implementation` "
            f"field (server predates oracle bc2cddd), and its serverName is {name!r}, not "
            f"{WANT_SERVER_NAME!r} — this is the legacy C++ oracle_gui, or an unknown "
            f"server. serverVersion={info.get('serverVersion')!r}, "
            f"{len(info.get('methods', []))} methods."
        )


def _set_pdeathsig() -> None:
    # If this process dies without reaping (SIGKILL, OOM), the kernel SIGTERMs the child.
    # Best effort; never fatal. Lifted from oracle-old/linux-port/mcp/oracle_mcp.py.
    try:
        import ctypes
        ctypes.CDLL("libc.so.6", use_errno=True).prctl(1, signal.SIGTERM)  # PR_SET_PDEATHSIG
    except Exception:
        pass


class AetherInstance:
    """One spawned `oracle-aether`, its private socket, and the dir that holds both.

    The socket dir is a `mkdtemp` under $TMPDIR and NOT the session scratchpad: AF_UNIX paths
    cap near 100 bytes and the scratchpad path alone is longer than that.

    Never touches the owner's live socket. Reaping is idempotent and runs from the context
    manager's `finally`, so a raising gate still cleans up.
    """

    def __init__(self, rom: str, symbols: str | None = None, no_pace: bool = True,
                 binary: str | os.PathLike = SERVER):
        self.rom = str(Path(rom).resolve())
        self.symbols = str(Path(symbols).resolve()) if symbols else None
        self.no_pace = no_pace
        self.binary = str(binary)
        self.dir = tempfile.mkdtemp(prefix="aeon-gate-")
        self.socket_path = os.path.join(self.dir, "oracle.sock")
        self.log_path = os.path.join(self.dir, "server.log")
        self.proc: subprocess.Popen | None = None
        self.handshake: dict = {}

    @property
    def pid(self) -> int | None:
        return self.proc.pid if self.proc is not None else None

    def argv(self) -> list[str]:
        cmd = [self.binary, self.rom, "--socket", self.socket_path]
        if self.symbols:
            cmd += ["--symbols", self.symbols]
        if self.no_pace:
            cmd.append("--no-pace")
        return cmd

    def _log_tail(self, lines: int = 12) -> str:
        try:
            text = Path(self.log_path).read_text(errors="replace")
        except OSError:
            return "(no server output captured)"
        tail = text.strip().splitlines()[-lines:]
        return "\n".join(tail) if tail else "(server printed nothing)"

    def _socket_accepts(self) -> bool:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            s.settimeout(0.2)
            s.connect(self.socket_path)
            return True
        except OSError:
            return False
        finally:
            s.close()

    def start(self) -> str:
        """Launch, wait for the socket to ACCEPT, handshake, assert identity. Returns the socket."""
        for label, path in (("server binary", self.binary), ("ROM", self.rom)):
            if not Path(path).is_file():
                self.reap()
                raise SpawnError(f"cannot spawn oracle-aether: {label} does not exist: {path}")
        cmd = self.argv()
        with open(self.log_path, "wb") as log:
            try:
                self.proc = subprocess.Popen(
                    cmd, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                    start_new_session=True, preexec_fn=_set_pdeathsig)
            except OSError as e:
                self.reap()
                raise SpawnError(f"cannot spawn oracle-aether ({' '.join(cmd)}): {e}") from e
        deadline = time.monotonic() + READY_TIMEOUT_S
        while True:
            rc = self.proc.poll()
            if rc is not None:
                tail = self._log_tail()
                self.reap()
                # The server REFUSES a .bin/.lst pair that do not match, by design. That
                # lands here, and the tail says so in words.
                raise SpawnError(f"oracle-aether exited with status {rc} before its socket was "
                                 f"ready ({' '.join(cmd)}). Server output:\n{tail}")
            if self._socket_accepts():
                break
            if time.monotonic() >= deadline:
                tail = self._log_tail()
                self.reap()
                raise SpawnError(f"oracle-aether did not open {self.socket_path} within "
                                 f"{READY_TIMEOUT_S:.0f}s. Server output:\n{tail}")
            time.sleep(READY_POLL_S)
        self.handshake = asyncio.run(self._handshake())
        assert_rust_server(self.handshake)       # <- the anti-vacuity check
        return self.socket_path

    async def _handshake(self) -> dict:
        b = BusClient(socket_path=self.socket_path, client_id="aeon-gate-probe",
                      client_name="aether_instance")
        try:
            return await b.connect()
        finally:
            await b.close()

    def reap(self) -> None:
        """SIGTERM, bounded wait, SIGKILL, then remove the dir. Idempotent.

        The server leaves its socket FILE behind on SIGTERM; the rmtree is what removes it,
        so this is not optional tidiness.
        """
        proc, self.proc = self.proc, None
        if proc is not None and proc.poll() is None:
            try:
                proc.terminate()
                try:
                    proc.wait(timeout=REAP_TERM_TIMEOUT_S)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=REAP_TERM_TIMEOUT_S)
            except (ProcessLookupError, subprocess.TimeoutExpired):
                pass
        shutil.rmtree(self.dir, ignore_errors=True)


@contextlib.contextmanager
def aether_emulator(rom: str, symbols: str | None = None, no_pace: bool = True):
    """Yield the bus socket of a freshly-booted, PAUSED oracle-aether. Reaps on the way out.

    Drop-in for `launcher.headless_emulator(rom)` with two differences a caller must know:
    the machine is STOPPED at frame 0 (no boot_wait, nothing to pause), and `emulator/reset`
    takes no params.
    """
    inst = AetherInstance(rom, symbols=symbols, no_pace=no_pace)
    try:
        yield inst.start()
    finally:
        inst.reap()


def unprefix(hexstr: str) -> str:
    """Strip the `0x` / `$` the Rust core puts on every hex byte string it returns.

    ⚠ THE QUIET TRAP OF THIS WHOLE CUTOVER. The legacy server answered `read_memory` with
    BARE hex ("0100000700000000"); the Rust core answers "0x0100000700000000". Callers that
    do `int(bytes, 16)` are unaffected — but callers that SLICE the string positionally
    (`raw[i*4:i*4+4]`, and several gates here do) read two characters off and get a
    plausible, entirely wrong answer with nothing raised. Measured 2026-08-26.

    In the other direction the core is strict rather than quiet: a `bytes` param WITHOUT the
    prefix is refused with -32602 (`bytes` must start with "0x" or "$"), which is how the
    palette_variant conversion announced itself.
    """
    s = hexstr[2:] if hexstr[:2].lower() == "0x" else (hexstr[1:] if hexstr[:1] == "$" else hexstr)
    return s


async def read_bytes(b: BusClient, addr: int, length: int) -> str:
    """`read_memory` returning BARE hex — the shape the legacy-era gate bodies expect.

    Use this instead of indexing the raw reply whenever the result is sliced.
    """
    return unprefix((await b.call("emulator/read_memory",
                                  {"addr": hex(addr), "len": length}))["bytes"])


async def write_bytes(b: BusClient, addr: int, hexstr: str) -> dict:
    """`write_memory` from a bare-or-prefixed hex string; the prefix is added if missing."""
    return await b.call("emulator/write_memory",
                        {"addr": hex(addr), "bytes": "0x" + unprefix(hexstr)})


async def run_to_addr(b: BusClient, addr: int, what: str, max_frames: int = 600) -> dict:
    """`run_to` an ADDRESS and insist it was REACHED. The breakpoint replacement.

    `run_to` returns whether the ceiling ended the run instead of the target — a caller that
    ignores `reached` reads registers from wherever the machine happened to stop, which is a
    convincing wrong answer rather than an error.
    """
    r = await b.call("emulator/run_to", {"addr": hex(addr), "maxFrames": max_frames})
    if not r.get("reached"):
        raise RuntimeError(f"run_to {what} (${addr:06X}) never reached it within {max_frames} "
                           f"frames; stopped at pc={r.get('pc')}")
    return r


# --------------------------------------------------------------------------- self-test / poison

def _smoke(rom: str, lst: str) -> int:
    t0 = time.monotonic()
    with aether_emulator(rom, symbols=lst) as sock:
        ready = time.monotonic() - t0
        print(f"  socket ready + handshake in {ready:.3f}s at {sock}")

        async def go():
            b = BusClient(socket_path=sock, client_id="smoke", client_name="smoke")
            info = await b.connect()
            print(f"  serverName={info.get('serverName')!r} "
                  f"implementation={info.get('implementation')!r} "
                  f"breakpoints={info.get('capabilities', {}).get('breakpoints')!r}")
            st = await b.call("emulator/status", {})
            print(f"  boots paused: running={st['running']} frame={st['frame']} pc={st['pc']}")
            r = await b.call("emulator/run_frames", {"frames": 180})
            print(f"  run_frames(180) -> frame={r['frame']} mclk={r['mclk']} running={r['running']}")
            await b.close()
            return st

        st = asyncio.run(go())
    if st["running"] or st["frame"] != 0:
        print("  FAIL: the server did not boot paused at frame 0")
        return 1
    print("  OK")
    return 0


def _poison_legacy(rom: str) -> int:
    """Spawn a REAL legacy oracle_gui and require assert_rust_server to REFUSE its handshake.

    This is the live half of the anti-vacuity proof. `tools/test_aether_instance.py` covers
    the same ground from recorded handshakes in a second and without xvfb; this one proves
    the recording is not a fiction. Kept out of pytest deliberately: it boots the legacy
    server under xvfb-run and takes ~15 s.
    """
    sys.path.insert(0, "/home/volence/sonic_hacks/oracle-old/linux-port/harness")
    from launcher import headless_emulator  # noqa: E402

    async def shake(sock):
        b = BusClient(socket_path=sock, client_id="poison", client_name="poison")
        try:
            return await b.connect()
        finally:
            await b.close()

    with headless_emulator(rom) as sock:
        info = asyncio.run(shake(sock))
    print(f"  legacy handshake: serverName={info.get('serverName')!r} "
          f"serverVersion={info.get('serverVersion')!r} "
          f"implementation={info.get('implementation')!r} "
          f"methods={len(info.get('methods', []))}")
    try:
        assert_rust_server(info)
    except WrongServerError as e:
        print(f"  OK — assertion FIRED, as it must:\n    {e}")
        return 0
    print("  FAIL: a REAL legacy oracle_gui handshake was ACCEPTED as the Rust core. "
          "The assertion is vacuous; every gate on this seam could be running on the wrong "
          "server and nothing would say so.")
    return 1


def main() -> int:
    ap = argparse.ArgumentParser()
    aeon = Path(__file__).resolve().parent.parent
    ap.add_argument("--rom", default=str(aeon / "s4.debug.bin"))
    ap.add_argument("--lst", default=str(aeon / "s4.debug.lst"))
    ap.add_argument("--smoke", action="store_true", help="spawn, handshake, assert, run 180 frames")
    ap.add_argument("--poison-legacy", action="store_true",
                    help="spawn a real legacy oracle_gui; FAIL if the assertion accepts it")
    args = ap.parse_args()
    if not args.smoke and not args.poison_legacy:
        ap.error("pass --smoke and/or --poison-legacy")
    rc = 0
    if args.smoke:
        print(f"aether_instance --smoke  ROM {args.rom}")
        rc |= _smoke(args.rom, args.lst)
    if args.poison_legacy:
        print(f"aether_instance --poison-legacy  ROM {args.rom}")
        rc |= _poison_legacy(args.rom)
    return rc


if __name__ == "__main__":
    sys.exit(main())
