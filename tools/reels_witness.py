#!/usr/bin/env python3
"""reels_witness — does each authored "reel" strip actually scroll at its OWN rate?

The claim is NOT "the table and the routine reach the ROM" (tools/reels_gate.py proves
that, byte for byte, without an emulator). It is that `OJZ_Reels_Fill`, once active,
genuinely writes REEL_BAND_COUNT DIFFERENT, INDEPENDENTLY-ADVANCING values into
`Parallax_Vscroll_Column_Buf`'s BG words — i.e. that two adjacent 16-px strips on
screen are showing genuinely different vertical offsets of the background, changing at
genuinely different rates, rather than the smooth ripple every OTHER per-column
mechanism in this tree already produces (SceneVDeform.Columns / Rocking / Perspective).

INSTRUMENT: `Parallax_Vscroll_Column_Buf` (80 bytes: 20 column-pairs x [FG word, BG
word]) read directly via `read_memory` on the Rust core, sampled TWICE, N frames apart,
while `OJZ_Reel_Active` is held nonzero.

THE EXPECTATION IS DERIVED FROM `Lag_Frame_Count`, NOT FROM N ITSELF (measured
2026-09-03). `OJZ_Reels_Fill` is called once from `GameState_OJZScroll_Update`'s frame
body (games/sonic4/test/ojz_scroll_test.emp) — that proc has exactly one `rts`, so it
never skips the call on its own. But the LEVEL frame body only ever runs once per
COMPLETE VBlank (`VInt_Level`, `VBlank_Ready=1`); whenever a physical VBlank fires while
the main loop is still mid-frame (`VBlank_Ready=0`), `VInt_Lag` (engine/system/vblank.emp)
runs instead — critical DMA and controller reads only, no level update, hence no
`OJZ_Reels_Fill` call — and still ticks `Frame_Counter` (so `run_frames(N)` genuinely
advances N physical VBlanks every time; nothing is wrong with the harness's frame count).
`VInt_Lag` also ticks `Lag_Frame_Count` (u32, DEBUG-only, engine/ram.emp), which is
therefore the exact count of frames in the just-elapsed window where the fill did NOT
run. Measured directly (`tools/reels_diag.py`-style single-frame stepping cross-checked
against `Lag_Frame_Count` deltas): requesting N frames yields exactly `N - lag_delta`
executions of `OJZ_Reels_Fill`, at N=30/60/90 alike, so the two "missing" executions
this witness used to assume away are two REAL lag frames early in this scene's settle
window, not a harness artifact — a hardcoded `N - 2` would happen to match today only
because those two lag frames both land inside every gap tested; a different SETTLE_
FRAMES, a slower/faster scene, or a future change to the level body's per-frame cost
would move or multiply them, and `N - 2` would go stale silently. So this witness now
brackets `Lag_Frame_Count` tightly around the same `run_frames` call it measures across,
and multiplies each band's speed by `N - lag_delta` (the MEASURED execution count), not
by N.

THERE IS NO HOTKEY. `OJZ_Reel_Speed`/`OJZ_Reels_Fill`'s own header
(games/sonic4/data/effects/ojz_effects.emp) records why: `Debug_BandDemoHotkey`'s header
enumerates every remaining pad chord against this shape and finds none free. So this
witness pokes `OJZ_Reel_Active` directly — `Debug_BandDemoHotkey`'s own header names
this as the alternative to a chord, and `band_witness.py` above uses the identical
pattern for `Raster_Pending`/OJZ_BandDemo.

VACUITY CHECK, mandatory, band_witness.py's own discipline: if every band's delta between
the two samples is the SAME value, either OJZ_Reel_Active never took effect (the whole
buffer is still Parallax_Update's shared-phase fill) or all five authored speeds
collapsed to one — either way this is UNMEASURABLE, not a pass, and the two are told
apart by which the FIRST assertion below already caught.

TWO THINGS THIS DOES NOT ESTABLISH:
  * It reads Work RAM, not the VDP's VSRAM registers. `Vscroll_Write`'s existing,
    unmodified per-frame DMA (engine/level/parallax.emp) is what actually carries this
    buffer to hardware every VBlank; that leg is already exercised by every other scene
    this engine ships (Rocking/Perspective/etc.) and is not re-proven here.
  * It samples ONE representative column per band (the band's first of four), not all
    20. A per-column bug that only hit columns 1-3 of a band would pass.

Usage: tools/reels_witness.py <rom> <lst>   (DEBUG shape only — OJZ_Reel_Active does not
exist in a release build's RAM layout)
"""
import asyncio, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))  # tools/, for suite_paths
from suite_paths import add_client_path  # noqa: E402
add_client_path()  # the Aether client, resolved from the suite root; loud if absent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from aether import BusClient
from aether_instance import aether_emulator
from raster_cost_probe import parse_lst

REEL_BAND_COUNT = 5
REEL_COLS_PER_BAND = 4
SPEEDS = [3, -5, 2, -4, 6]                  # OJZ_REEL_SPEEDS, games/sonic4/data/effects/ojz_effects.emp
COLUMN_BUF_LEN = 80                          # Parallax_Vscroll_Column_Buf: [u8; 80]
SETTLE_FRAMES = 180                          # into real gameplay before poking anything
WARMUP_FRAMES = 4                            # let OJZ_Reels_Fill run at least once before sample 1
SAMPLE_GAP_FRAMES = 30                       # frames between the two samples


def bg_word(buf, column):
    """The BG word for one 16-px column-pair. Format: 4 bytes per pair, [FG hi, FG lo,
    BG hi, BG lo] — Parallax_Vscroll_Column_Buf's own layout (parallax.emp Step 5b)."""
    off = column * 4 + 2
    return (buf[off] << 8) | buf[off + 1]


async def run(sock, lst):
    b = BusClient(socket_path=sock, client_id="reelsw", client_name="reels_witness")
    await b.connect()
    await b.call("emulator/load_symbols", {"path": lst})
    sym = parse_lst(lst)
    await b.call("emulator/reset", {})
    await b.call("emulator/run_frames", {"frames": SETTLE_FRAMES})

    await b.call("emulator/write_memory",
                 {"addr": hex(sym["OJZ_Reel_Active"]), "value": 1, "width": 1})
    await b.call("emulator/run_frames", {"frames": WARMUP_FRAMES})

    async def sample():
        r = await b.call("emulator/read_memory",
                          {"addr": hex(sym["Parallax_Vscroll_Column_Buf"]), "len": COLUMN_BUF_LEN})
        raw = bytes.fromhex(r["bytes"].replace("0x", ""))
        if len(raw) != COLUMN_BUF_LEN:
            raise RuntimeError(f"read {len(raw)} bytes, wanted {COLUMN_BUF_LEN}")
        return raw

    async def read_lag_count():
        r = await b.call("emulator/read_memory", {"addr": hex(sym["Lag_Frame_Count"]), "len": 4})
        raw = bytes.fromhex(r["bytes"].replace("0x", ""))
        if len(raw) != 4:
            raise RuntimeError(f"Lag_Frame_Count read {len(raw)} bytes, wanted 4")
        return int.from_bytes(raw, "big")

    active = await b.call("emulator/read_memory", {"addr": hex(sym["OJZ_Reel_Active"]), "len": 1})
    if bytes.fromhex(active["bytes"].replace("0x", ""))[0] == 0:
        return 1, ["OJZ_Reel_Active reads 0 after the write — the poke did not take"]

    lag1 = await read_lag_count()
    buf1 = await sample()
    await b.call("emulator/run_frames", {"frames": SAMPLE_GAP_FRAMES})
    lag2 = await read_lag_count()
    buf2 = await sample()

    lag_delta = lag2 - lag1
    if lag_delta < 0:
        return 1, [f"Lag_Frame_Count went BACKWARDS ({lag1} -> {lag2}) — u32 wrap or a "
                    "reset landed inside the sample window; the measurement is invalid"]
    fill_executions = SAMPLE_GAP_FRAMES - lag_delta
    if fill_executions <= 0:
        return 1, [f"Lag_Frame_Count says {lag_delta} lag frames out of "
                    f"{SAMPLE_GAP_FRAMES} requested — OJZ_Reels_Fill would have run "
                    f"{fill_executions} times, which cannot be measured"]

    print(f"Lag_Frame_Count: {lag1} -> {lag2} (delta {lag_delta}) over "
          f"{SAMPLE_GAP_FRAMES} requested frames -> OJZ_Reels_Fill actually ran "
          f"{fill_executions} times (this, not the requested frame count, is what "
          f"each band's expectation is multiplied by)")
    print(f"sampled {SAMPLE_GAP_FRAMES} frames apart, one representative column per band "
          f"(column = band * {REEL_COLS_PER_BAND}):")
    fails = []
    deltas = []
    for band in range(REEL_BAND_COUNT):
        col = band * REEL_COLS_PER_BAND
        v1, v2 = bg_word(buf1, col), bg_word(buf2, col)
        # the phase accumulator is a BYTE (wraps mod 256); the word delta modulo 256 is
        # the comparable quantity regardless of how many times it wrapped
        delta = (v2 - v1) % 256
        want = (SPEEDS[band] * fill_executions) % 256
        deltas.append(delta)
        ok = delta == want
        print(f"  band {band} (col {col}): BG {v1:#06x} -> {v2:#06x}, delta {delta} "
              f"(mod 256), speed {SPEEDS[band]:+d} x {fill_executions} actual runs = "
              f"{want}  {'OK' if ok else 'MISMATCH'}")
        if not ok:
            fails.append(f"band {band} delta")

    if len(set(deltas)) == 1:
        return 1, ["VACUOUS: every band's delta is identical — either OJZ_Reel_Active "
                    "never took effect (Parallax_Update's shared-phase fill is still "
                    "running unopposed) or the shipped OJZ_REEL_SPEEDS collapsed to one "
                    "rate. UNMEASURABLE, not green — this is exactly the property "
                    "tools/reels_gate.py's ROM-level distinctness check exists to rule "
                    "out before an emulator is ever involved; if THIS fires while THAT "
                    "gate is green, the divergence is between the ROM and this build's "
                    "s4.debug.lst symbol table, not the mechanism."]
    print(f"\nvacuity check: {len(set(deltas))} distinct band deltas — the instrument "
          f"sees independently-advancing strips")
    return (1, fails) if fails else (0, [])


def main():
    rom, lst = sys.argv[1], sys.argv[2]
    with aether_emulator(rom) as sock:
        rc, fails = asyncio.run(run(sock, lst))
    print("\nRESULT:", "PASS — five reel bands advance at their five authored, "
          "pairwise-distinct rates" if rc == 0 else f"FAIL — {fails}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
