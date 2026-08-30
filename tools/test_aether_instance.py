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
