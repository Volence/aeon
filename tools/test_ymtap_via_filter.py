"""YmTap's Z80-WATCH-TAP contract, proven hermetically (no emulator, no build).

WHAT THIS PINS. `tools/song_load_mid_drum_witness.py`'s `YmTap` (and, by import,
`tools/fm6_foreign_sample_witness.py`) records the Z80 sound driver's YM2612 writes off
a `bus` write watch. Oracle's Z80-WATCH-TAP change (hub ruling §11.52 option C; oracle
CR `94665a6:docs/2026-09-25-z80-watch-cr.md` §5.1, the normative "The Z80 and the watch
surface" paragraph) moves those hits:

  * a Z80 YM write is reported at the register's 68000-MAP address, `$A04000-$A04003`
    (`$A00000 | a` for the Z80-side `a` = `$4000-$4003`), with `via: "z80"`, the Z80's
    `pc`, and NO `fc` and NO `symbol`;
  * the 68000's own writes to `$A04000-$A04003` arrive in the SAME stream, `via: "bus"`,
    fc 5, and are not the driver's traffic;
  * the old Z80-side address `$4000` stops being a Z80 hit (it names cartridge ROM).

The hit records below are typed from that CR text, NOT from the witness's constants, so
moving `YM_A0..A3` back or dropping the `via` filter turns this file red. The fake bus
answers only the two methods `YmTap` calls; it is not an emulator.

Red-first evidence (2026-09-25, recorded in this file's commit body): with the
`via` filter deleted from `YmTap.poll` the bus-hit and old-address tests fail; with
`YM_A0..A3` put back at `$4000-$4003` the part/latch test fails.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import song_load_mid_drum_witness as W  # noqa: E402

# From the CR (§5.1): the 68000-map base of the Z80 window, and the Z80-side YM ports.
Z80_WINDOW_68K = 0xA00000
YM_PART1_ADDR = Z80_WINDOW_68K | 0x4000   # $A04000, part-I address port
YM_PART1_DATA = Z80_WINDOW_68K | 0x4001   # $A04001, part-I data port
YM_PART2_ADDR = Z80_WINDOW_68K | 0x4002   # $A04002, part-II address port
OLD_Z80_SIDE = 0x4000                     # the pre-change hit address (cartridge ROM here)


def _z80_hit(seq, addr, value, mclk):
    # CR §5.1: via "z80", Z80 pc, fc and symbol ABSENT.
    return {"seq": seq, "addr": f"0x{addr:08X}", "value": f"0x{value:08X}",
            "size": 1, "op": "write", "via": "z80", "pc": "0x00000123", "mclk": mclk,
            "frame": 1}


def _m68k_hit(seq, addr, value, mclk):
    # CR §4/§5.1: the 68000's own write, via "bus", fc 5, with a 68k pc and symbol.
    return {"seq": seq, "addr": f"0x{addr:08X}", "value": f"0x{value:08X}",
            "size": 1, "op": "write", "via": "bus", "fc": 5, "pc": "0x0000B740",
            "symbol": "Sound_PlayMusic", "mclk": mclk, "frame": 1}


def _old_tap_hit(seq, addr, value, mclk):
    # The shape today's oracle emits for a Z80 YM write (CR l.102): raw Z80-side
    # address, fc 0, via "bus".
    return {"seq": seq, "addr": f"0x{addr:08X}", "value": f"0x{value:08X}",
            "size": 1, "op": "write", "fc": 0, "via": "bus", "pc": "0x0000020E",
            "mclk": mclk, "frame": 1}


class FakeBus:
    """Answers `watchpoint_add` and one page of `watchpoint_hits`; nothing else."""

    def __init__(self, hits):
        self.hits = hits
        self.calls = []

    async def call(self, method, params):
        self.calls.append((method, params))
        if method == "emulator/watchpoint_add":
            return {"watch": "w0"}
        if method == "emulator/watchpoint_hits":
            return {"hits": self.hits, "seen": 1000, "matched": len(self.hits),
                    "dropped": 0, "truncated": False}
        raise AssertionError(f"YmTap called an unexpected method: {method}")


def _drain(hits):
    tap = W.YmTap(FakeBus(hits))

    async def go():
        await tap.arm("t")
        await tap.poll()
    asyncio.run(go())
    return tap


def test_default_watch_is_armed_on_the_68000_map_ym_ports():
    bus = FakeBus([])
    tap = W.YmTap(bus)
    asyncio.run(tap.arm("t"))
    (_, p), = bus.calls
    assert int(p["addr"], 16) == YM_PART1_ADDR and p["len"] == 4 and p["space"] == "bus"


def test_z80_hits_at_a04000_are_counted_and_decoded():
    # select $2B on part I, then its data $80; select $2A on part II, no data.
    tap = _drain([_z80_hit(1, YM_PART1_ADDR, 0x2B, 100),
                  _z80_hit(2, YM_PART1_DATA, 0x80, 110),
                  _z80_hit(3, YM_PART2_ADDR, 0x2A, 120)])
    assert tap.z80 == 3 and tap.foreign == 0
    assert tap.events == [(1, 100, 0, 0x2B, None), (2, 110, 0, 0x2B, 0x80),
                          (3, 120, 1, 0x2A, None)]
    assert tap.data(0x2B, part=0) == [(2, 110, 0x80)]
    assert tap.liveness_fault() is None


def test_68000_bus_hit_at_a04000_is_not_counted():
    tap = _drain([_m68k_hit(1, YM_PART1_ADDR, 0x2B, 100),
                  _m68k_hit(2, YM_PART1_DATA, 0x00, 110)])
    assert tap.z80 == 0 and tap.foreign == 2
    assert tap.events == []
    # matched > 0 from the 68000 alone must NOT read as a live driver tap.
    assert tap.matched == 2
    fault = tap.liveness_fault()
    assert fault is not None and "NONE via" in fault


def test_old_z80_side_4000_hit_is_not_counted():
    tap = _drain([_old_tap_hit(1, OLD_Z80_SIDE, 0x2B, 100),
                  _old_tap_hit(2, OLD_Z80_SIDE + 1, 0x80, 110)])
    assert tap.z80 == 0 and tap.events == []
    assert tap.liveness_fault() is not None


def test_mixed_stream_keeps_only_the_driver_and_every_seq():
    tap = _drain([_z80_hit(1, YM_PART1_ADDR, 0x2A, 100),
                  _m68k_hit(2, YM_PART1_ADDR, 0x28, 105),
                  _z80_hit(3, YM_PART1_DATA, 0x7F, 110)])
    assert tap.z80 == 2 and tap.foreign == 1
    # The filter decodes the DRIVER'S stream alone: its data lands on its own select
    # ($2A). Scope, stated so it is not over-read: on the real chip the address latch is
    # shared by both masters, so an interleaved 68000 select WOULD redirect that data.
    # This asserts what YmTap reconstructs, not what the chip did; `foreign` is printed
    # on L0/L1 so a nonzero 68000 share is visible (aeon's 68k never writes the YM).
    assert tap.data(0x2A, part=0) == [(3, 110, 0x7F)]
    assert tap.data(0x28, part=0) == []
    # skipped hits still advance the seq record: no false hole
    assert tap.seqs == [1, 2, 3] and tap.holes() == 0


def test_poison_shape_goes_loud():
    # --poison aims at $A00000 (Z80 RAM): no Z80 access there is offered, so at most a
    # 68000 write can land. L0/L1 must fail either way.
    empty = _drain([])
    assert empty.liveness_fault() is not None and "matched NOTHING" in empty.liveness_fault()
    only_68k = _drain([_m68k_hit(1, Z80_WINDOW_68K, 0x00, 100)])
    assert only_68k.liveness_fault() is not None


def test_unattached_watch_goes_loud():
    tap = W.YmTap(FakeBus([]))
    assert tap.seen == 0 and "seen == 0" in tap.liveness_fault()
