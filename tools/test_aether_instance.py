#!/usr/bin/env python3
"""Tests for `aether_instance` — the shared gate spawn seam and its identity assertion.

THE POINT OF THIS FILE is that `assert_rust_server` is not vacuous. A spawn helper whose
identity check silently accepts anything is WORSE than no check: every gate on the seam would
report a verdict measured on the wrong emulator and nothing would go red. So the assertion is
driven here against handshakes RECORDED FROM BOTH REAL SERVERS, and the legacy one must be
refused.

Recorded 2026-08-26 on this machine, from the binaries as shipped that day:
  * Rust:   <suite>/oracle/target/release/oracle-aether  (built 08-25 21:03)
  * legacy: oracle-old/linux-port/build/oracle_gui, spawned by launcher.headless_emulator

These are RECORDINGS, and a recording can go stale. `python3 tools/aether_instance.py
--poison-legacy` boots the real legacy server and re-runs the refusal against a live
handshake; that is the check that proves these fixtures still describe reality. It is not in
pytest because it needs xvfb and ~15 s.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aether_instance import (WrongServerError, assert_rust_server,  # noqa: E402
                             AetherInstance, SERVER)

# --- the two recorded handshakes, trimmed to the identity-bearing fields ------------------

RUST_HANDSHAKE = {
    "serverName": "oracle-next",
    "serverVersion": "0.0.0",
    "protocolVersion": 1,
    "capabilities": {"breakpoints": False, "profiler": True, "watchpoints": {"supported": True}},
    "methods": ["emulator/run_to", "emulator/run_frames", "emulator/read_memory"],
    "running": False,
    "frame": 0,
}

LEGACY_HANDSHAKE = {
    "serverName": "oracle",
    "serverVersion": "2.1-linux",
    "protocolVersion": 1,
    "capabilities": {},
    "methods": ["emulator/breakpoint_add", "emulator/wait_for_break", "emulator/resume"],
}


def test_rust_handshake_is_accepted():
    """The correct server must pass, or the seam blocks the whole lane."""
    assert_rust_server(RUST_HANDSHAKE)


def test_legacy_handshake_is_refused():
    """THE POISON. A real legacy oracle_gui handshake must not be mistaken for the Rust core."""
    with pytest.raises(WrongServerError) as e:
        assert_rust_server(LEGACY_HANDSHAKE)
    msg = str(e.value)
    assert "oracle" in msg and "oracle-next" in msg, msg
    # It must say WHICH server it got, not just that something was wrong.
    assert "2.1-linux" in msg, msg


def test_explicit_implementation_wins_over_server_name():
    """Rung 1: once `implementation` is on the wire it is the ONLY thing consulted.

    Both halves matter. A server that says `oracle-cpp` must be refused even if it spells its
    name the Rust way (that is exactly what the C++ server will look like once oracle's
    identity commit lands on both binaries), and a server that says `oracle-rs` must be
    accepted even under a name this module has never seen.
    """
    with pytest.raises(WrongServerError) as e:
        assert_rust_server({**RUST_HANDSHAKE, "implementation": "oracle-cpp"})
    assert "oracle-cpp" in str(e.value)

    assert_rust_server({"implementation": "oracle-rs", "serverName": "something-renamed"})


def test_unknown_server_with_no_identity_fields_is_refused():
    """Neither rung may fall through to "accept". Silence is not a pass."""
    with pytest.raises(WrongServerError):
        assert_rust_server({})
    with pytest.raises(WrongServerError):
        assert_rust_server({"serverName": "blastem", "serverVersion": "0.6.2"})


def test_argv_is_the_documented_launch_line():
    """The recipe: <bin> <rom> --socket <short path> --symbols <lst> --no-pace."""
    inst = AetherInstance("/dev/null", symbols="/dev/null")
    try:
        argv = inst.argv()
        assert argv[0] == str(SERVER)
        assert argv[2] == "--socket" and argv[3] == inst.socket_path
        assert "--symbols" in argv
        assert argv[-1] == "--no-pace"
        # AF_UNIX paths cap near 108 bytes; the session scratchpad path alone exceeds that,
        # which is why the dir is a plain mkdtemp. Guard the constraint, not the prefix.
        assert len(inst.socket_path) < 100, inst.socket_path
    finally:
        inst.reap()


def test_no_symbols_omits_the_flag():
    inst = AetherInstance("/dev/null")
    try:
        assert "--symbols" not in inst.argv()
    finally:
        inst.reap()


def test_unprefix_handles_both_spellings_and_neither():
    """The quiet trap: reads come back `0x`-prefixed here and bare on the legacy server.

    A gate that slices positionally reads two characters off and reports a wrong answer with
    nothing raised, so this helper is what the converted gates route through.
    """
    from aether_instance import unprefix
    assert unprefix("0x0100000700000000") == "0100000700000000"
    assert unprefix("0X00FF") == "00FF"
    assert unprefix("$1122") == "1122"
    assert unprefix("1122") == "1122"          # legacy shape passes through untouched
    assert unprefix("") == ""


def test_reap_is_idempotent_and_removes_the_dir():
    """Reap runs from a `finally` and from error paths; a second call must not raise."""
    inst = AetherInstance("/dev/null")
    d = Path(inst.dir)
    assert d.is_dir()
    inst.reap()
    inst.reap()
    assert not d.exists()


# --- the spawn-time CART check (CART-VERIFY-COVERAGE, 2026-09-12) -------------------------
#
# Same bar as `assert_rust_server` above and for the same reason: a precondition that
# cannot fire is worse than none. These drive `AetherInstance._verify_cart` against the
# fake bus from `test_cart_identity`, so they need no emulator and run in the build's
# pytest lane. The REAL-cart proof — pointing a live server at a DIFFERENT ROM of the
# SAME SIZE and requiring a refusal — is `python3 tools/cart_verify_spawn_proof.py`,
# kept out of pytest because it boots a server, exactly as --poison-legacy is.

import asyncio  # noqa: E402
import zlib  # noqa: E402

from aether_instance import (CART_CHECK_FULL, CART_CHECK_LENGTH, CART_CHECKS,  # noqa: E402
                             CartMismatch, aether_emulator)
from test_cart_identity import CART, FakeBus  # noqa: E402


def _inst(tmp_path, data, **kw):
    """An AetherInstance that has NOT spawned, pointed at a real file on disk."""
    rom = tmp_path / "rom.bin"
    rom.write_bytes(data)
    return AetherInstance(str(rom), **kw)


def test_byte_primitives_are_still_importable_from_aether_instance():
    """The re-export pin. ~30 tools say `from aether_instance import read_bytes, ...`.

    `unprefix`/`read_bytes`/`write_bytes` MOVED to `aether_bytes` to break the import
    cycle the spawn-time cart check creates. If the re-export ever stops being one, those
    tools break at IMPORT time — in whichever lane happens to run them first, which is
    not this one. So it is pinned here, where it is cheap.
    """
    import aether_bytes
    import aether_instance
    for name in ("unprefix", "read_bytes", "write_bytes"):
        assert getattr(aether_instance, name) is getattr(aether_bytes, name), name


def test_the_two_modules_import_in_either_order():
    """The cycle is resolved, not merely dodged by one lucky import order.

    A function-local import inside `start()` would pass a test that imports
    `aether_instance` first and fail nothing when a caller imports `cart_identity`
    first. Both orders are driven in fresh interpreters.
    """
    import subprocess
    here = str(Path(__file__).resolve().parent)
    for first, second in (("aether_instance", "cart_identity"),
                          ("cart_identity", "aether_instance")):
        r = subprocess.run(
            [sys.executable, "-c",
             f"import sys; sys.path.insert(0, {here!r}); import {first}; import {second}; "
             f"print('ok')"],
            capture_output=True, text=True)
        assert r.returncode == 0, f"{first} then {second} failed:\n{r.stderr}"


def test_an_unknown_cart_check_mode_is_refused_at_construction(tmp_path):
    """Not at spawn — at construction, where the typo is still cheap to see."""
    with pytest.raises(ValueError) as e:
        _inst(tmp_path, CART, cart_check="off")
    assert "full" in str(e.value) and "length" in str(e.value)
    assert CART_CHECKS == {CART_CHECK_FULL, CART_CHECK_LENGTH}, \
        "an 'off' mode would make the whole inherited check optional and silent"


def test_verify_cart_passes_a_matching_cart_and_records_its_crc(tmp_path):
    """The negative control. Without it an unconditional refusal would look perfect."""
    inst = _inst(tmp_path, CART)
    try:
        asyncio.run(inst._verify_cart(FakeBus(CART)))
        assert inst.cart_crc == zlib.crc32(CART) & 0xFFFFFFFF
        assert inst.cart_note and "byte-identical" in inst.cart_note
    finally:
        inst.reap()


def test_verify_cart_raises_on_a_same_length_content_difference(tmp_path):
    """THE discriminating case: right size, wrong bytes — the stale cart.

    A length-only check passes this. That is why `full` is the default and why this
    test asserts on the FULL mode specifically.
    """
    bad = bytearray(CART)
    bad[len(CART) // 3] ^= 0xFF
    inst = _inst(tmp_path, bytes(bad))
    try:
        with pytest.raises(CartMismatch) as e:
            asyncio.run(inst._verify_cart(FakeBus(CART)))
        assert "CONTENT" in str(e.value)
    finally:
        inst.reap()


def test_verify_cart_raises_on_a_length_difference(tmp_path):
    """The truncated / mid-write ROM."""
    inst = _inst(tmp_path, CART + b"\x00" * 16)
    try:
        with pytest.raises(CartMismatch):
            asyncio.run(inst._verify_cart(FakeBus(CART)))
    finally:
        inst.reap()


def test_length_mode_announces_itself_as_weaker_on_stderr(tmp_path, capsys):
    """The opt-down must never be silent.

    A weaker check that prints the same reassuring line as the strong one is the exact
    artifact this parcel exists to remove, so the WORD 'WEAKER' is asserted, not just
    that something was printed.
    """
    bad = bytearray(CART)
    bad[7] ^= 0xFF                      # same length, different content
    inst = _inst(tmp_path, bytes(bad), cart_check=CART_CHECK_LENGTH)
    try:
        asyncio.run(inst._verify_cart(FakeBus(CART)))     # passes: length-only cannot see it
        err = capsys.readouterr().err
        assert "WEAKER" in err and "LENGTH ONLY" in err, err
        assert inst.cart_note and "length only" in inst.cart_note
    finally:
        inst.reap()


def test_aether_emulator_threads_cart_check_through_and_defaults_to_full():
    """The context manager is how 40+ tools spawn; the default is what they inherit."""
    import inspect
    sig = inspect.signature(aether_emulator)
    assert sig.parameters["cart_check"].default == CART_CHECK_FULL
    assert inspect.signature(AetherInstance.__init__).parameters["cart_check"].default \
        == CART_CHECK_FULL


def test_probe_asserts_the_server_before_it_reads_the_cart(tmp_path):
    """Order is load-bearing: refuse the wrong server BEFORE asking it about carts.

    On the legacy server `romBytes` and the `read_memory` reply shape are a different
    vocabulary, so a cart readback through it fails confusingly or — worse — does not
    fail. This drives `_probe` with a bus whose handshake is the LEGACY recording and a
    cart that would ALSO mismatch, and requires the SERVER error, not the cart one.
    """
    import aether_instance

    reads = []

    class RecordingBus(FakeBus):
        """Answers the handshake with the LEGACY recording and counts cart traffic."""

        def __init__(self, cart, handshake):
            FakeBus.__init__(self, cart)
            self.handshake = handshake

        def __call__(self, *a, **kw):       # stands in for the BusClient CONSTRUCTOR
            return self

        async def connect(self):
            return self.handshake

        async def close(self):
            pass

        async def call(self, method, params):
            reads.append(method)
            return await FakeBus.call(self, method, params)

    # The real `_probe`, not a re-implementation of it: the only thing swapped is the
    # BusClient class the module reaches for. A test that retyped `_probe`'s body would
    # keep passing after `_probe` reordered, which is the one thing it is checking.
    inst = _inst(tmp_path, CART + b"\x00")      # the cart would ALSO mismatch
    saved = aether_instance.BusClient
    try:
        aether_instance.BusClient = RecordingBus(CART, LEGACY_HANDSHAKE)
        with pytest.raises(WrongServerError):
            asyncio.run(inst._probe())
        assert reads == [], f"the cart was read off a REFUSED server: {reads}"
        # ...and the positive half: with the Rust handshake the same bus DOES get asked
        # about the cart, so the emptiness above is an ordering fact, not a dead path.
        reads.clear()
        aether_instance.BusClient = RecordingBus(CART, RUST_HANDSHAKE)
        with pytest.raises(CartMismatch):
            asyncio.run(inst._probe())
        assert "emulator/status" in reads, reads
    finally:
        aether_instance.BusClient = saved
        inst.reap()
