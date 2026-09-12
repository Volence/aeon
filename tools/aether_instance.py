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

SO IS THE SECOND ONE, ADDED 2026-09-12 (CART-VERIFY-COVERAGE). Right server, WRONG CART is
the same shape of failure and was undefended: of the 67 bus-reaching tools in `tools/`, 3
asked what cart they were measuring. Now `assert_cart_matches_disk` runs on every spawn too,
between the handshake and the caller's first call, so the 46 that construct this class inherit
it instead of hand-rolling it. It compares `emulator/status`'s `romBytes` against the file AND
reads the whole cart back off the bus, because these four ROM shapes hold their sizes across
landings and a length match is therefore not an identity. Measured cost of the readback on
`s4.debug.bin`: see `cart_identity`'s docstring — it is small enough that `cart_check="length"`
exists only for a caller that can argue it cannot afford even that, and says LENGTH ONLY,
WEAKER on stderr when used. `tools/cart_coverage_census.py` re-derives the coverage.

    MEASURED HANDSHAKES, 2026-08-26, both binaries AS SHIPPED on this machine:

      field                     oracle-aether (Rust)      oracle_gui (legacy C++)
      implementation            ABSENT                    ABSENT
      serverBuild               ABSENT                    ABSENT
      serverName                "oracle-next"             "oracle"
      serverVersion             "0.0.0"                   "2.1-linux"
      capabilities.breakpoints  false (present)           ABSENT
      len(methods)              41                        53

    ⚠⚠ RE-MEASURED 2026-09-12 AGAINST THE SHIPPED `oracle-aether` (built that day 14:46),
    AND THE RUST COLUMN ABOVE IS NOW WRONG IN FOUR PLACES. The table is left standing as
    the record of what rung 2 was built for; this block is what is TRUE today:

      field                     2026-08-26 (above)        2026-09-12 (measured)
      implementation            ABSENT                    "oracle-rs"
      serverBuild               ABSENT                    {source: "vcs",
                                                           id: "781e9e08...+profile=release",
                                                           dirty: false}
      len(methods)              41                        61
      capabilities.breakpoints  false                     TRUE
      capabilities.watchpoints  not present               {supported: true, maxWatches: 32,
                                                           ringCap: 4096,
                                                           spaces: [bus, vram, cram, vsram]}
      capabilities.vgm          not present               false  (and `vgm_start` /
                                                           `audio_spectrum` are genuinely
                                                           NOT among the 61 — there is no
                                                           audio instrument on this bus)

    SO THE "DO NOT EXIST" PARAGRAPH BELOW IS OUT OF DATE, and that matters more than the
    numbers: `breakpoint_add`, `wait_for_break` AND the whole watchpoint surface are served
    now. Three witnesses in this tree depend on them — `tools/song_load_mid_drum_witness.py`
    reads the Z80's own YM writes through a `bus`-space write watch over $4000-$4003, and
    `tools/poke_storm_sound_cost_witness.py` times the sound driver's DMA-window bracket the
    same way. A reader who took that paragraph at its word would not try a watchpoint at all.

    ⚠ `implementation` / `serverBuild` WERE NOT on the wire in August. Oracle committed them
    (`bc2cddd`, "the handshake says which implementation answered", merged 2026-08-26) but
    the RELEASE BINARIES then predated it — both were built 2026-08-25 21:03. So an assertion
    written only against `implementation == "oracle-rs"` would have refused the correct server
    and blocked the whole lane. Hence TWO RUNGS, in this order:

      1. `implementation` present  -> it MUST equal "oracle-rs". Nothing else passes.
         (As of 2026-09-12 this is the LIVE rung: the shipped binary answers "oracle-rs",
         so rung 2 is no longer consulted on this machine.)
      2. `implementation` absent   -> `serverName` MUST equal "oracle-next", the measured
         structural discriminator above. The legacy server answers "oracle" and is refused.

    Rung 2 is a fallback for a STALE BINARY, not a permanent second answer. Its stated
    retirement condition — "when oracle's release binaries carry `implementation`" — IS NOW
    MET (measured 2026-09-12). Deleting it is a code change with its own test
    (`tools/test_aether_instance.py` drives both rungs off recorded handshakes) and belongs
    to a parcel that owns that test; it is recorded here rather than done in passing. Until
    then, do not weaken rung 1 to match rung 2.

    Proof it fires: `tools/test_aether_instance.py` drives both rungs off the recorded
    handshakes above, and `python3 tools/aether_instance.py --poison-legacy` spawns a REAL
    legacy `oracle_gui`, hands its handshake to this module, and fails if it is accepted.

WHAT DIFFERS FROM THE LEGACY SEAM — every one of these is measured, not read:

  * `emulator/reset` takes NO PARAMS. The legacy `{"wait": True, "run": False}` is refused
    with -32602 (protocol §2.5 rejects undeclared keys). It is also unnecessary: the Rust
    server resets to a STOPPED machine, which is what those two params were asking for.
  * The bus is 24 BITS. `0xFFFF0000` is refused with -32004; `0xFF0000` is the same byte.
    `parse_lst` already yields 24-bit addresses, so converted gates needed no change.
  * `capabilities.breakpoints` WAS false on 2026-08-26 — `breakpoint_add` / `wait_for_break`
    did not exist, and `emulator/run_to {"addr"|"symbol", "maxFrames"}` was the replacement
    (synchronous, reports `reached`; see `run_to_addr` below). **That is no longer true: as of
    2026-09-12 the shipped binary answers `breakpoints: true`, serves both methods, and serves
    the four-space watchpoint surface as well — see the RE-MEASURED block above.** `run_to`
    remains the right tool for "run until this PC" because it is bounded and synchronous;
    reach for a breakpoint only when you need halt-on-an-unscheduled-hit, which `run_to`
    cannot express, and for a watchpoint when the question is "who wrote this, and when".
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

sys.path.insert(0, str(Path(__file__).resolve().parent))  # tools/, for suite_paths
from suite_paths import add_client_path, harness_path, suite_path  # noqa: E402
add_client_path()  # the Aether client, resolved from the suite root; loud if absent
from aether import BusClient  # noqa: E402

# The layering that makes the cart check inheritable: aether_bytes (leaf, no suite imports)
# <- cart_identity <- this module. `unprefix` / `read_bytes` / `write_bytes` used to live
# HERE and are re-exported below, unchanged, so the ~30 tools that import them from
# `aether_instance` need no edit. See aether_bytes.py for why they moved.
from aether_bytes import read_bytes, unprefix, write_bytes  # noqa: E402,F401
from cart_identity import CartMismatch, assert_cart_matches_disk  # noqa: E402,F401

# `oracle-next` is a SYMLINK to `oracle` on this machine, so the three already-aether gates
# that spell the path the other way run the same binary. Spelled the owner-ruled way here.
SERVER = suite_path("oracle", "target", "release", "oracle-aether")

READY_TIMEOUT_S = 15.0    # generous: measured ready time is ~0.06 s
READY_POLL_S = 0.05
REAP_TERM_TIMEOUT_S = 3.0

# The two rungs of the identity assertion. See the module docstring for how they were measured.
WANT_IMPLEMENTATION = "oracle-rs"
WANT_SERVER_NAME = "oracle-next"

# --- the cart check's strength knob -----------------------------------------------------
# FULL reads the whole cart back off the bus and compares bytes. LENGTH compares only
# `romBytes` against the file's size, which CANNOT see a stale cart of the right length —
# and for this tree that is the common case, because the four canonical ROM shapes have held
# their sizes across many landings. So FULL is the default and LENGTH is an argued-for
# opt-down that ANNOUNCES ITSELF ON stderr every time, never a silent setting.
#
# THERE IS DELIBERATELY NO "off" AND NO ENVIRONMENT VARIABLE. An env knob would let a whole
# run be weakened from outside the source, invisibly, by something that is not the tool's
# author — which is the same class of failure as the stale preload this check exists to
# catch. A caller that genuinely cannot afford the readback says so in its own source, in
# its own diff, where a reviewer sees it.
CART_CHECK_FULL = "full"
CART_CHECK_LENGTH = "length"
CART_CHECKS = {CART_CHECK_FULL, CART_CHECK_LENGTH}


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
                 binary: str | os.PathLike = SERVER, cart_check: str = CART_CHECK_FULL):
        self.rom = str(Path(rom).resolve())
        self.symbols = str(Path(symbols).resolve()) if symbols else None
        self.no_pace = no_pace
        self.binary = str(binary)
        if cart_check not in CART_CHECKS:
            raise ValueError(f"cart_check must be one of {sorted(CART_CHECKS)}, "
                             f"not {cart_check!r}")
        self.cart_check = cart_check
        self.dir = tempfile.mkdtemp(prefix="aeon-gate-")
        self.socket_path = os.path.join(self.dir, "oracle.sock")
        self.log_path = os.path.join(self.dir, "server.log")
        self.proc: subprocess.Popen | None = None
        self.handshake: dict = {}
        # What the cart check found, as one line, for a caller that wants to print its
        # provenance. Stays None until `start()` runs it.
        self.cart_note: str | None = None
        self.cart_crc: int | None = None

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
        self.handshake = asyncio.run(self._probe())
        return self.socket_path

    async def _probe(self) -> dict:
        """Connect once, then ask BOTH identity questions on that one connection.

        WHY HERE AND NOT IN A SECOND PASS. The cart check needs a live bus, and this is
        the only point in the lifecycle where this class holds one: after `start()` returns,
        the socket belongs to the caller and a check bolted on afterwards would be a
        check the caller could forget. Firing here also means the cart is compared while
        the machine is still STOPPED AT FRAME 0 and no caller code has run, so nothing
        the caller did can be blamed for a mismatch and nothing the caller measures
        precedes the check.

        ORDER IS LOAD-BEARING: `assert_rust_server` FIRST. It is the cheap, pure question,
        and if the answer is the legacy server then `emulator/status`'s `romBytes` and the
        `read_memory` reply shape are both a different server's vocabulary — reading a cart
        back through it would fail confusingly, or worse, not fail. Refuse the wrong server
        before asking it anything about carts.

        `_handshake` was this method's name while it only did the first half. It was
        renamed rather than extended silently so that a reader who greps for the handshake
        does not find a method that also reads 847 KB off the bus.
        """
        b = BusClient(socket_path=self.socket_path, client_id="aeon-gate-probe",
                      client_name="aether_instance")
        try:
            info = await b.connect()
            assert_rust_server(info)             # <- the anti-vacuity check
            await self._verify_cart(b)           # <- right server, right CART
            return info
        finally:
            await b.close()

    async def _verify_cart(self, b) -> None:
        """Prove the loaded cart IS `self.rom`. Raises `CartMismatch`; never returns false.

        `CartMismatch` is not caught here and must not be caught to continue anyway. It is
        an UNMEASURABLE verdict — not a pass, and not a failure of whatever the caller came
        to measure — and converting it to a zero or a green is the precise thing this check
        exists to prevent.
        """
        note: list[str] = []
        full = self.cart_check == CART_CHECK_FULL
        if not full:
            # Loud, every time, on the stream a gate's own output does not own. A weaker
            # check that does not say it is weaker is worse than no check: it produces the
            # same reassuring line as the strong one.
            print(f"aether_instance: CART CHECK IS LENGTH ONLY, WEAKER — a stale cart of "
                  f"the right size passes. {self.rom}", file=sys.stderr)
        self.cart_crc = await assert_cart_matches_disk(b, self.rom, note, full=full)
        self.cart_note = note[0] if note else None

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
def aether_emulator(rom: str, symbols: str | None = None, no_pace: bool = True,
                    cart_check: str = CART_CHECK_FULL):
    """Yield the bus socket of a freshly-booted, PAUSED oracle-aether. Reaps on the way out.

    Drop-in for `launcher.headless_emulator(rom)` with two differences a caller must know:
    the machine is STOPPED at frame 0 (no boot_wait, nothing to pause), and `emulator/reset`
    takes no params.

    Raises `CartMismatch` before yielding if the server's cart is not `rom` — see
    `AetherInstance._verify_cart`. `cart_check="length"` opts down to the weaker comparison
    and says so on stderr; there is no way to opt out.
    """
    inst = AetherInstance(rom, symbols=symbols, no_pace=no_pace, cart_check=cart_check)
    try:
        yield inst.start()
    finally:
        inst.reap()


# `unprefix`, `read_bytes` and `write_bytes` are re-exported from `aether_bytes` at the top
# of this module. They are still `from aether_instance import ...`-able and always will be;
# `tools/test_aether_instance.py` pins that, because a re-export that quietly stopped being
# one would break ~30 tools at IMPORT time in a lane nobody runs first.


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
    # Spawn TWICE and subtract, so the readback's cost is a measurement and not a guess:
    # the length-only spawn pays everything except the readback, so full-minus-length IS
    # the readback. Both numbers are printed, because a difference without its two
    # operands is not a measurement.
    t0 = time.monotonic()
    lean = AetherInstance(rom, symbols=lst, cart_check=CART_CHECK_LENGTH)
    try:
        lean.start()
        t_len = time.monotonic() - t0
    finally:
        lean.reap()
    t0 = time.monotonic()
    inst = AetherInstance(rom, symbols=lst)
    try:
        inst.start()
        t_full = time.monotonic() - t0
        n = Path(rom).stat().st_size
        print(f"  spawn+handshake+cart(length) {t_len:.3f}s · +cart(full) {t_full:.3f}s "
              f"-> readback of {n} bytes costs {t_full - t_len:+.3f}s")
        print(f"  {inst.cart_note}")
    finally:
        inst.reap()

    t0 = time.monotonic()
    with aether_emulator(rom, symbols=lst) as sock:
        ready = time.monotonic() - t0
        print(f"  socket ready + handshake + cart check in {ready:.3f}s at {sock}")

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
    sys.path.insert(0, str(harness_path()))
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
