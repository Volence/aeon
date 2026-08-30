#!/usr/bin/env python3
"""curve_probe — the ramping BG scroll factor, seen and priced (P3 Task 10).

Two arms over one non-canonical instrument build.

  --arm ramp   THE VALUE CHECK. Install a curve fixture, read Hscroll_Buffer, and compare
               every line word against a ramp this tool DERIVES from the fixture's own
               authored factors — the layer's `fb` at the top, its `curve: To(..)` factor at
               the bottom, Bresenham between them. Repeated ACROSS A CAMERA SWEEP, because a
               curve is camera-proportional: its whole spread is `camX>>to - camX>>from`, so
               one frozen camera position tests almost nothing (at camX 0 the ramp is flat,
               and it would pass against a walker that had no curve mechanism at all).
               Carries its own red-first control and the anchored-split continuation check.

  --arm cost   THE MODEL COLUMN. Five fixtures, each one thing apart, fitting two
               parameters: the per-curve-LINE cost and the per-curve-BAND cost. The pairs are
               curve-vs-flat on the SAME ROM, so the capability's record stride, Step 4a's
               wider copy and the hoist loop's per-band `btst` are held fixed and cancel.

WHY A SEPARATE TOOL, AND WHY IT REFUSES A CANONICAL ROM
------------------------------------------------------
No canonical image contains the mechanism: sonic4 declares SCANLINE_CAPS $001F, no shipped
scene authors a curve, BAND_CURVE_N is 0 and all three gated blocks are elided. Everything
here runs against a LOCAL instrument build (recipe: docs/benchmarks/scanline-p3/CURVES.md),
and the stride check below refuses a legacy-record ROM rather than measuring the flat path
and reporting a number for it.

WHAT IS DERIVED AND WHAT IS READ
--------------------------------
Read (INPUTS): Camera_X, and the buffer itself. Derived (the EXPECTATION): the base scroll
words, the far-end scroll words, the spread, the Bresenham pair, and every line of the ramp
— all from the fixture's own factor bytes, which this tool authored. Nothing is read back
off the band records the walker computed into: reading `bc_step` and re-multiplying by it
would be checking the walker against itself, which is the vacuous shape
docs/benchmarks/scanline-p3/CURVE-INSTRUMENT.md was written to avoid.

Usage:
    python3 tools/curve_probe.py --rom s4.i1.bin --lst s4.i1.lst --arm ramp
    python3 tools/curve_probe.py --rom s4.i1.bin --lst s4.i1.lst --arm cost --repeat 3
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # tools/, for suite_paths
from suite_paths import add_client_path, harness_path  # noqa: E402
add_client_path()  # the Aether client, resolved from the suite root; loud if absent
HARNESS = str(harness_path())  # legacy oracle_gui launcher; loud if absent
sys.path.insert(0, HARNESS)
sys.path.insert(0, str(Path(__file__).resolve().parent))
from aether import BusClient            # noqa: E402
from launcher import headless_emulator  # noqa: E402
import parallax_cost_probe as pcp       # noqa: E402
import parallax_hscroll_probe as php    # noqa: E402
from raster_cost_probe import parse_lst  # noqa: E402

LEGACY_BE_SIZE = 10    # sizeof(band_entry) — the prefix, which never grows (design §3.1)

# `pub struct band_curve` — engine/level/parallax.emp. Offsets FROM THE TAIL; the tail sits
# immediately after the legacy prefix when BAND_EXT_N is 0, which is the instrument build's
# shape and is asserted against the DERIVED stride in main().
BC_TO_S1 = 0
BC_TO_S2 = 1
BC_FLAGS = 2
BC_PAD   = 3
BC_STEP  = 4    # i16, DERIVED per frame by the walker — authored as 0
BC_REM   = 6    # i16, likewise
BC_SPAN  = 8    # u16, likewise
BC_SIZE  = 10

CURVE_FLAG_OP     = 1 << 0
CURVE_FLAG_ACTIVE = 1 << 1
CURVE_FLAG_CONT   = 1 << 2   # runtime-only: Step 4b sets it on a split entry

# The packed factor encoding — engine/level/parallax_dsl.emp `packed()`:
# bits 0-3 shift1 (15 = whole-factor zero), 4-7 shift2 (15 = single term), bit 8 op (1 = SUB).
def packed(s1: int, s2: int, op: int) -> int:
    return ((op & 1) << 8) | ((s2 & 15) << 4) | (s1 & 15)


FACTOR_1    = packed(0, 15, 0)   # $0F0 — camX
FACTOR_1_2  = packed(1, 15, 0)   # $0F1
FACTOR_1_4  = packed(2, 15, 0)   # $0F2
FACTOR_1_8  = packed(3, 15, 0)   # $0F3
FACTOR_1_16 = packed(4, 15, 0)   # $0F4
FACTOR_1_32 = packed(5, 15, 0)   # $0F5
FACTOR_3_4  = packed(0, 2, 1)    # $120 — camX - camX>>2
# THE NIBBLES ARE s2:s1, NOT s1:s2, and getting that backwards is a silent wrong answer, not
# an error: the first spelling of this block wrote FACTOR_1 as $000, which is s1 0 / s2 0 —
# a legal factor meaning camX+camX. It measured -2*camX on both sides and PASSED, because the
# tool and the walker agreed on the wrong factor. Caught only because one swept position
# disagreed. Hence `packed()`, transcribed from engine/level/parallax_dsl.emp, rather than
# hand-written hex.
assert (FACTOR_1, FACTOR_1_2, FACTOR_1_8) == (0x0F0, 0x0F1, 0x0F3)


def decode_factor(cam_x: int, packed: int) -> int:
    """The scroll WORD a factor produces: -(camX>>s1 op camX>>s2), truncated to a word.

    Transcribed from Decode_Factor_A/B (engine/level/parallax.emp) — the negation included,
    because HScroll words are negated camera offsets and the whole derivation below works in
    that space. Python's `>>` floors on negatives, which is what `asr.w` does.
    """
    s1 = packed & 15
    if s1 == 15:
        return 0
    v = php.s16(cam_x) >> s1
    s2 = (packed >> 4) & 15
    if s2 != 15:
        t2 = php.s16(cam_x) >> s2
        v = v - t2 if (packed >> 8) & 1 else v + t2
    return php.s16(-php.s16(v))


def bresenham(spread: int, span: int) -> tuple[int, int]:
    """(whole, rem) with rem normalised into [0, span) — the FLOOR division pair.

    The walker computes this with one `divs.w` and a conditional fixup; this is the same
    quantity spelled as arithmetic, which is what makes it an independent expectation rather
    than a transcription of the instruction sequence.
    """
    assert span >= 1, "span must be >= 1 — the walker's `ble` skips the divide otherwise"
    whole = spread // span          # Python // floors, which IS the normalised quotient
    rem = spread - whole * span
    assert 0 <= rem < span
    return whole, rem


# ======================================================================
# THE FIXTURE — a config plus 20-byte band records, authored here.
# ======================================================================

def curve_band(top: int, fa: int, fb: int, to: int | None, stride: int) -> bytes:
    """One band record: the legacy prefix built by hand, then the curve tail.

    The prefix is NOT `pcp.band()`'s, because that helper hard-codes the shipped fixtures'
    factors (FACTOR_1 / FACTOR_1_2) and a curve fixture has to vary the BG factor to have a
    ramp at all. The two op bits and the 15-sentinels are the same encoding, transcribed
    beside the field names so the divergence is visible rather than buried.
    """
    b = bytearray(LEGACY_BE_SIZE)
    b[0:2] = (top & 0xFFFF).to_bytes(2, "big")
    b[2] = fa & 15
    b[3] = (fa >> 4) & 15
    b[4] = fb & 15
    b[5] = (fb >> 4) & 15
    b[6] = ((fa >> 8) & 1) | (((fb >> 8) & 1) << 1)
    b[7] = pcp.NO_DEFORM      # dsa — a curve band never samples (layer() refuses the pair)
    b[8] = pcp.NO_DEFORM      # dsb
    b[9] = 0                  # phase
    t = bytearray(BC_SIZE)
    if to is not None:
        t[BC_TO_S1] = to & 15
        t[BC_TO_S2] = (to >> 4) & 15
        t[BC_FLAGS] = CURVE_FLAG_ACTIVE | (CURVE_FLAG_OP if (to >> 8) & 1 else 0)
    out = bytes(b) + bytes(t)
    assert len(out) == stride, f"record is {len(out)}, but the build's stride is {stride}"
    return out


def build_curve_cfg(base: bytes, *, layers, stride: int, head_tab_fg: int,
                    anchor_ch: int = pcp.ANCHOR_NONE) -> bytes:
    """The shipped header with the fixture's fields, plus one record per layer.

    `layers` is a list of (top, fa, fb, to_or_None).

    THE HEADER TABLE WORD IS NO LONGER A MODE KEY. Until 2026-08-26 `parallax_mode_key`
    decided per-line vs per-cell at RUNTIME by ORing the config's two HEADER table words,
    and this docstring claimed the desync "cannot happen" in the authored model because
    `scene_forces_per_line()` arm 3 raised per-line off the curve. That claim was WRONG:
    arm 3 raised the CAPABILITY BIT (which compiled the per-line code in); it never
    changed the runtime key's answer for a config with null header words, so a real curve
    scene with no table and no anchor ran the per-cell filler and drew no curve — the
    d-29 showcase defect. The key and the per-cell filler are deleted (d-29-corrected);
    every config runs Parallax_Fill_PerLine. The flat zero-amplitude table is still put in
    the header here only so the fixture's shape matches the shipped one it copies.

    V_FACTOR_BG IS THE LOCK SENTINEL (15) AND V_OFFSET IS 0, which pins Vscroll_BG at 0 and
    makes Step 4a's rotation an identity copy — so the shadow tops ARE the authored tops and
    the derivation below does not have to re-derive the rotation. Every W fixture in
    parallax_cost_probe does the same, for the same reason.
    """
    h = bytearray(base[:pcp.CFG_SIZE])
    h[pcp.CFG_BAND_COUNT] = len(layers)
    h[pcp.CFG_V_FACTOR_BG] = pcp.NO_DEFORM
    h[pcp.CFG_LAYER_MASK] = 0xFF
    h[pcp.CFG_TRANSITION] = 0
    h[pcp.CFG_DEFORM_SPEED_FG] = 0
    h[pcp.CFG_DEFORM_SPEED_BG] = 0
    h[pcp.CFG_ANCHOR_CH] = anchor_ch
    h[pcp.CFG_ANCHOR_DSA] = pcp.NO_DEFORM
    h[pcp.CFG_ANCHOR_DSB] = pcp.NO_DEFORM
    h[pcp.CFG_V_DEFORM_SHIFT] = 3
    h[pcp.CFG_V_CENTER_Y:pcp.CFG_V_CENTER_Y + 2] = (0).to_bytes(2, "big")
    h[pcp.CFG_V_OFFSET:pcp.CFG_V_OFFSET + 2] = (0).to_bytes(2, "big")
    for off, val in ((pcp.CFG_DEFORM_TAB_FG, head_tab_fg),
                     (pcp.CFG_DEFORM_TAB_BG, 0),
                     (pcp.CFG_V_DEFORM_TAB_BG, 0)):
        h[off:off + 4] = val.to_bytes(4, "big")
    body = b"".join(curve_band(t, fa, fb, to, stride) for (t, fa, fb, to) in layers)
    return bytes(h) + body


# ======================================================================
# THE DERIVATION — what the buffer must contain, from the fixture's own factors.
# ======================================================================

def derive_curve_buffer(layers, cam_x: int, split_line: int | None = None,
                        continue_at_split: bool = True):
    """The expected (FG, BG) pair per screen line, 224 of them.

    `layers` is the AUTHORED list. `split_line`, when given, is where the anchored overlay
    splits the layer containing it — the split entry inherits its parent's factors and, with
    `continue_at_split`, its parent's accumulator.

    `continue_at_split=False` is not a mode the engine has; it is the ALTERNATIVE HYPOTHESIS
    the ramp arm derives alongside the real one so that "the split continues the curve" is a
    discriminating claim rather than a restatement. If the two expectations agreed, the check
    would pass whatever the walker did with the split.
    """
    tops = [t for (t, _fa, _fb, _to) in layers]
    ends = [tops[i + 1] if i + 1 < len(tops) else php.HSCROLL_LINES for i in range(len(tops))]
    out = [None] * php.HSCROLL_LINES
    carry = None            # (acc, err) parked by the previous entry, as the walker does
    for i, (top, fa, fb, to) in enumerate(layers):
        fg = decode_factor(cam_x, fa)
        base = decode_factor(cam_x, fb)
        # The layer's own span — the divisor, taken BEFORE any split, which is exactly why
        # the walker hoists it in Step 4a's neighbourhood and not in the fill's band hoist.
        span = ends[i] - top
        segs = [(top, ends[i], False)]
        if split_line is not None and top < split_line < ends[i]:
            segs = [(top, split_line, False), (split_line, ends[i], True)]
        for (lo, hi, is_split) in segs:
            if to is None:
                for line in range(lo, hi):
                    out[line] = (php.u16(fg), php.u16(base))
                continue
            end_word = decode_factor(cam_x, to)
            whole, rem = bresenham(php.s16(end_word - base), span)
            if is_split and continue_at_split and carry is not None:
                acc, err = carry
            else:
                acc, err = base, 0
            for line in range(lo, hi):
                out[line] = (php.u16(fg), php.u16(acc))
                acc += whole
                err += rem
                if err >= span:
                    err -= span
                    acc += 1
            carry = (php.s16(acc), err)
    return out


# ======================================================================
# THE RAMP ARM
# ======================================================================

async def install(b, sym, cfg: bytes, settle: int, cam_x: int | None):
    """Freeze the scene, install the fixture in the replay scratch, aim the config at it."""
    for attempt in range(4):
        try:
            await b.call("emulator/reset", {"wait": True, "run": False})
            break
        except Exception:
            if attempt == 3:
                raise
            await asyncio.sleep(1.5)
    await b.call("emulator/run_frames", {"frames": settle})
    await b.call("emulator/write_memory",
                 {"addr": hex(sym["Debug_Scene_Freeze"]), "value": 1, "width": 1})
    await b.call("emulator/run_frames", {"frames": 2})
    # THE CAMERA MOVES FIRST AND THE FIXTURE GOES IN AFTER IT — the order is load-bearing and
    # was MEASURED, not reasoned. Written the other way round, camX 3072 read back a buffer
    # that was flat at -147 while every derived check passed: moving the camera crosses a
    # SECTION boundary, `Parallax_CheckBoundary` fires, and `Parallax_StartTransition` stages
    # the section's own config as the TARGET — which leaves `Parallax_Current_Config` still
    # aimed at the fixture (so the pointer check is green) while `Parallax_Update` builds the
    # buffer from the target instead. Installing after the crossing has settled, and then
    # asserting the transition state is idle at the sample, closes both halves.
    #
    # A held direction is not an option either: it moves the camera between the tick that
    # built the buffer and the read, which is the torn read
    # docs/benchmarks/scanline-p3/CURVE-INSTRUMENT.md §3 is a postmortem for. Camera_X is a
    # 16.16 subpixel long, so the pixel value goes in the HIGH word.
    if cam_x is not None:
        await b.call("emulator/write_memory",
                     {"addr": hex(sym["Camera_X"]), "value": (cam_x & 0xFFFF) << 16,
                      "width": 4})
        await b.call("emulator/run_frames", {"frames": 6})
    scratch = sym["Replay_Record_Buf"]
    await b.call("emulator/write_memory", {"addr": hex(scratch), "bytes": cfg.hex().upper()})
    await b.call("emulator/write_memory",
                 {"addr": hex(sym["Parallax_Transition_Frames"]), "value": 0, "width": 1})
    await b.call("emulator/write_memory",
                 {"addr": hex(sym["Parallax_Target_Config"]), "value": 0, "width": 4})
    await b.call("emulator/write_memory",
                 {"addr": hex(sym["Parallax_Current_Config"]), "value": scratch, "width": 4})
    await b.call("emulator/run_frames", {"frames": 4})
    return scratch


async def ramp_at(b, sym, cfg, layers, settle, cam_x, split_line=None):
    """One camera position: install, sample at a completed tick, derive, check."""
    scratch = await install(b, sym, cfg, settle, cam_x)
    await php.stop_at_tick(b, sym)
    ptr = int.from_bytes(await php._read(b, sym["Parallax_Current_Config"], 4), "big") & 0xFFFFFF
    back = await php._read(b, scratch, len(cfg))
    cam = await php._read(b, sym["Camera_X"], 4)
    got_cam_x = int.from_bytes(cam[0:2], "big")
    hs = await php._read(b, sym["Hscroll_Buffer"], php.HSCROLL_BYTES)
    tops = await php._read(b, sym["Parallax_Shadow_Bands"], 20 * 8)
    # THE TRANSITION STATE IS A DERIVED CHECK, not decoration: a staged TARGET config wins
    # over Current_Config inside Parallax_Update's Step 1, so the pointer check alone reads
    # green while the walker builds from somebody else's config entirely. That is exactly
    # what a camera write across a section boundary produced here.
    tframes = (await php._read(b, sym["Parallax_Transition_Frames"], 1))[0]
    target = int.from_bytes(await php._read(b, sym["Parallax_Target_Config"], 4), "big")
    setup = []
    if tframes or target:
        setup.append(f"a transition is live (frames {tframes}, target ${target:08X}) — the "
                     f"walker built from the TARGET config, not the fixture")
    if ptr != (scratch & 0xFFFFFF):
        setup.append(f"config pointer moved off the fixture (${ptr:06X})")
    if back != cfg:
        setup.append("fixture bytes were overwritten between install and sample")
    if cam_x is not None and got_cam_x != (cam_x & 0xFFFF):
        setup.append(f"Camera_X reads ${got_cam_x:04X}, not the written ${cam_x & 0xFFFF:04X}")
    act = php.buffer_pairs(hs, php.HSCROLL_LINES)
    exp = derive_curve_buffer(layers, php.s16(got_cam_x), split_line, True)
    ok, bad = php.check(act, exp, label=f"camX {php.s16(got_cam_x)}")
    return {"cam_x": php.s16(got_cam_x), "ok": ok, "bad": bad, "act": act, "exp": exp,
            "setup": setup, "shadow_tops": [int.from_bytes(tops[i * 20:i * 20 + 2], "big")
                                            for i in range(8)]}


def spread_of(layers, cam_x, i=0) -> int:
    _t, _fa, fb, to = layers[i]
    return php.s16(decode_factor(cam_x, to) - decode_factor(cam_x, fb))


def run_ramp(args, sym, base, stride, zero_tab) -> int:
    # ONE curve layer over the whole screen, ramping BG from 1/2 to 1/8. FG is FACTOR_1 (the
    # hard camera lock every shipped config uses), so the FG half of every line is a constant
    # and a curve that leaked into it would be caught by the same compare.
    layers = [(0, FACTOR_1, FACTOR_1_2, FACTOR_1_8)]
    cfg = build_curve_cfg(base, layers=layers, stride=stride, head_tab_fg=zero_tab)

    # TWO LAYERS WITH AN ANCHOR, for the split-continuation check. The anchor channel is 0
    # and the split line comes from Effects_Screen_L[0], which the fixture cannot choose
    # directly — so it is READ BACK and the expectation is derived against what the machine
    # actually split at, never against what this tool hoped for.
    a_layers = [(0, FACTOR_1, FACTOR_1_2, FACTOR_1_8), (160, FACTOR_1, FACTOR_1_4, None)]
    a_cfg = build_curve_cfg(base, layers=a_layers, stride=stride, head_tab_fg=zero_tab,
                            anchor_ch=0)

    sweep = [int(x) for x in args.sweep.split(",")]
    results = []
    split_res = {}

    async def _go(sock):
        b = BusClient(socket_path=sock, client_id="curveprobe", client_name="curve_probe")
        await b.connect()
        await b.call("emulator/load_symbols", {"path": args.lst})
        for cx in sweep:
            results.append(await ramp_at(b, sym, cfg, layers, args.settle, cx))
        # the split arm, at one camera position with a large spread
        r = await ramp_at(b, sym, a_cfg, a_layers, args.settle, sweep[-1])
        sl = await php._words(b, sym["Effects_Screen_L"], 4)
        split_res.update({"r": r, "screen_l": php.s16(sl[0])})
        await b.close()

    with headless_emulator(args.rom) as sock:
        asyncio.run(_go(sock))

    print(f"ROM {args.rom}   arm ramp   stride {stride} B (DERIVED)")
    print("fixture: 1 layer, BG factor ramps FACTOR_1_2 -> FACTOR_1_8 over all 224 lines;")
    print("         FG FACTOR_1 (constant). Expectation DERIVED from those factors + camX.\n")
    hdr = f"{'camX':>6} {'spread':>7} {'BG[0]':>7} {'BG[223]':>8} {'verdict':>9}  notes"
    print(hdr)
    print("-" * len(hdr))
    failures = []
    for r in results:
        if r["setup"]:
            failures += [f"camX {r['cam_x']}: {m}" for m in r["setup"]]
        sp = spread_of(layers, r["cam_x"])
        note = "" if r["ok"] else "MISMATCH"
        print(f"{r['cam_x']:>6} {sp:>7} {php.s16(r['act'][0][1]):>7} "
              f"{php.s16(r['act'][223][1]):>8} {'PASS' if r['ok'] else 'FAIL':>9}  {note}")
        if not r["ok"]:
            print(php.report_mismatch(r["bad"]))
            failures.append(f"camX {r['cam_x']}: {len(r['bad'])} mismatching words")

    # ---- ANTI-VACUITY: the sweep must contain a position whose ramp is REAL ----
    # At camX 0 every factor decodes to 0 and the whole screen is flat, so a green there is
    # compatible with a walker that has no curve at all. The sweep is only evidence if at
    # least one position moves the BG word by more than a couple of pixels.
    spreads = [abs(spread_of(layers, r["cam_x"])) for r in results]
    if max(spreads, default=0) < 16:
        failures.append(f"every swept position has |spread| < 16 px (max {max(spreads, default=0)})"
                        f" — the ramp is invisible at this camera range and the sweep asserts"
                        f" nothing. Widen --sweep.")
    print(f"\nspread range over the sweep: {min(spreads)} .. {max(spreads)} px "
          f"[anti-vacuity floor is 16]")

    # ---- THE RED-FIRST CONTROL, on the same bytes ----
    # Same buffer, same checker, a DIFFERENT expectation: the flat band the layer would be
    # without its curve. It must FAIL, naming a line. Steps 2 and 3 of the Task-2 red-first
    # proof in one: if this passes, the buffer is flat and the mechanism did not run.
    last = results[-1]
    flat = derive_curve_buffer([(0, FACTOR_1, FACTOR_1_2, None)], last["cam_x"])
    ok_flat, bad_flat = php.check(last["act"], flat, label="flat control")
    print(f"\nRED-FIRST CONTROL at camX {last['cam_x']} — the same words against the FLAT"
          f" expectation:")
    if ok_flat:
        print("  GREEN, which is a FAILURE of the control: the buffer is flat, so the curve"
              " loop did not run.")
        failures.append("red-first control passed — the buffer holds no ramp")
    else:
        print(f"  RED as required. {len(bad_flat)} words differ from flat; first:")
        print(php.report_mismatch(bad_flat, limit=3))

    # ---- THE SPLIT CONTINUATION (design §2's interaction) ----
    r, L = split_res["r"], split_res["screen_l"]
    print(f"\nANCHORED SPLIT — Effects_Screen_L[0] = {L}; shadow tops {r['shadow_tops'][:4]}")
    if r["setup"]:
        failures += [f"split fixture: {m}" for m in r["setup"]]
    if not (0 < L < 160):
        print(f"  SKIPPED: the latched anchor line {L} is not inside the curve layer"
              f" [0,160), so no split lands in it and this arm asserts nothing.")
        failures.append(f"split arm could not run: anchor line {L} outside the curve layer")
    else:
        cont = derive_curve_buffer(a_layers, r["cam_x"], split_line=L, continue_at_split=True)
        rest = derive_curve_buffer(a_layers, r["cam_x"], split_line=L, continue_at_split=False)
        ok_c, bad_c = php.check(r["act"], cont, "continues")
        ok_r, bad_r = php.check(r["act"], rest, "restarts")
        # THE TWO HYPOTHESES MUST DIFFER, or the check is vacuous: if the ramp is shallow
        # enough that continuing and restarting produce the same words, a pass proves nothing.
        _, disc = php.check(cont, rest, "discriminating")
        print(f"  the two hypotheses differ on {len(disc)} words"
              f" [0 would make this check vacuous]")
        print(f"  CONTINUES the ramp through the split: {'PASS' if ok_c else 'FAIL'}")
        print(f"  RESTARTS  the ramp at the split:      {'PASS' if ok_r else 'FAIL'}"
              f"   [must FAIL — it is the alternative hypothesis]")
        if not disc:
            failures.append("the continue/restart expectations are identical — vacuous")
        if not ok_c:
            print(php.report_mismatch(bad_c, limit=4))
            failures.append(f"split does not continue the curve: {len(bad_c)} words")
        if ok_r and disc:
            failures.append("the split RESTARTED the ramp — CURVE_FLAG_CONT is not working")

    print()
    php.print_smoothness(php.smoothness(last["act"], [0]))
    if failures:
        print("\nFAILURES:")
        for f in failures:
            print(f"  {f}")
        return 5
    print("\nramp arm: PASS")
    return 0


# ======================================================================
# THE COST ARM
# ======================================================================

def cost_fixtures(base: bytes, stride: int, zero_tab: int) -> dict:
    """Five fixtures, three pairs, two parameters. Each pair is ONE thing apart.

    F1/K1  1 band, 224 lines            flat / curve      -> 224 L + 1 B
    F2/K2  2 bands, 112+112, both       flat / curve      -> 224 L + 2 B
    H2     2 bands, only the LOWER a curve                -> 112 L + 1 B   (paired with F2)

    L is the per-curve-LINE cost, B the per-curve-BAND cost (the frame hoist's decode and
    divide, plus the fill's per-band seed). Three equations, two unknowns: the third is the
    residual, which is the deliverable.
    """
    F, C = FACTOR_1_2, FACTOR_1_8
    def mk(layers):
        return build_curve_cfg(base, layers=layers, stride=stride, head_tab_fg=zero_tab)
    return {
        "F1": {"what": "1 band, flat BG factor", "lines": 0, "bands": 0,
               "cfg": mk([(0, FACTOR_1, F, None)])},
        "K1": {"what": "1 band, BG factor RAMPS (F1 + a curve, nothing else)",
               "lines": 224, "bands": 1, "cfg": mk([(0, FACTOR_1, F, C)])},
        "F2": {"what": "2 bands, both flat", "lines": 0, "bands": 0,
               "cfg": mk([(0, FACTOR_1, F, None), (112, FACTOR_1, F, None)])},
        "K2": {"what": "2 bands, BOTH ramp (F2 + two curves)", "lines": 224, "bands": 2,
               "cfg": mk([(0, FACTOR_1, F, C), (112, FACTOR_1, F, C)])},
        "H2": {"what": "2 bands, only the LOWER ramps (F2 + one curve)", "lines": 112,
               "bands": 1,
               "cfg": mk([(0, FACTOR_1, F, None), (112, FACTOR_1, F, C)])},
        # ---- THE DATA-DEPENDENCE ARM. K1 with ONE thing changed: the far-end factor. ----
        # Same band, same 224 lines, same everything else — only the SPREAD differs, and with
        # it two data-dependent quantities the fit above cannot see:
        #   * the Bresenham correction fires `rem/span` of the time, and when it does it costs
        #     a `sub.w` + `addq.w` and turns a not-taken branch into a taken one;
        #   * `divs.w` on the 68000 is operand-timed, so a different dividend is a different
        #     number of cycles, once per curve band per frame.
        # Reported as a RANGE rather than folded into the fit: a per-line "constant" that
        # moves with the data is not a constant, and §5(b) of WALKER-MODEL.md is a postmortem
        # for exactly the shape of claim that hides this.
        "D4": {"what": "K1 with the ramp ending at FACTOR_1_4 (smaller spread)",
               "lines": 224, "bands": 1,
               "cfg": mk([(0, FACTOR_1, F, FACTOR_1_4)])},
        "D32": {"what": "K1 with the ramp ending at FACTOR_1_32 (larger spread)",
                "lines": 224, "bands": 1,
                "cfg": mk([(0, FACTOR_1, F, FACTOR_1_32)])},
    }


def run_cost(args, sym, base, stride, zero_tab) -> int:
    FX = cost_fixtures(base, stride, zero_tab)
    results: dict[str, list[dict]] = {k: [] for k in FX}

    async def _sweep(sock):
        b = BusClient(socket_path=sock, client_id="curveprobe", client_name="curve_probe")
        await b.connect()
        await b.call("emulator/load_symbols", {"path": args.lst})
        for k, fx in FX.items():
            results[k].append(await pcp._one(b, sym, fx["cfg"], args.settle, args.sample))
        await b.close()

    for _ in range(args.repeat):
        with headless_emulator(args.rom) as sock:
            asyncio.run(_sweep(sock))

    print(f"ROM {args.rom}   arm cost   stride {stride} B (DERIVED)   sample {args.sample}"
          f"   repeats {args.repeat}")
    print("response = Parallax_Update's per-routine row, INCLUSIVE of its callees.")
    print("Every pair is curve-vs-flat on the SAME ROM, so the capability's record stride,")
    print("Step 4a's wider copy and the hoist loop's per-band btst cancel.\n")
    hdr = (f"{'FIX':4} {'bands':>5} {'crvln':>6} {'crvbd':>6} {'Px_Update':>10} {'spread':>7}"
           f" {'Fill_PerLine':>12}  checks")
    print(hdr)
    print("-" * len(hdr))
    table, failures = {}, []
    for k, fx in FX.items():
        runs = results[k]
        rows = [pcp.row(r["prof"], sym["Parallax_Update"]) for r in runs]
        if any(x is None for x in rows):
            failures.append(f"{k}: no Parallax_Update row")
            print(f"{k:4} -- NO Parallax_Update ROW")
            continue
        checks = []
        for reason, key in (("config pointer moved off the fixture", "ptr_ok"),
                            ("fixture bytes were overwritten", "bytes_ok"),
                            ("the replay recorder woke up", "replay_idle"),
                            ("the window was not preemption-free", "preempt_free")):
            if not all(r[key] for r in runs):
                checks.append(key)
                failures.append(f"{k}: {reason}")
        cyc = [int(x["cycles"]) for x in rows]
        pl = pcp.row(runs[0]["prof"], sym["Parallax_Fill_PerLine"])
        n = fx["cfg"][pcp.CFG_BAND_COUNT]
        print(f"{k:4} {n:>5} {fx['lines']:>6} {fx['bands']:>6} {cyc[0]:>10} "
              f"{max(cyc) - min(cyc):>7} {(pl['cycles'] if pl else 0):>12}  "
              f"{'ok' if not checks else '!! ' + ','.join(checks)}")
        table[k] = {"cycles": cyc, "bands": n, "curve_lines": fx["lines"],
                    "curve_bands": fx["bands"], "what": fx["what"],
                    "fill_per_line": pl["cycles"] if pl else 0}

    if {"F1", "K1", "D4", "D32"} <= set(table):
        print("\nDATA DEPENDENCE — K1 with ONE thing changed, the far-end factor. Same band,")
        print("same 224 lines; only the spread, and with it the Bresenham fraction and the")
        print("divs operands, differ. A per-line cost that moves here is not a constant.")
        f1 = table["F1"]["cycles"][0]
        for k, lbl in (("K1", "-> FACTOR_1_8 "), ("D4", "-> FACTOR_1_4 "),
                       ("D32", "-> FACTOR_1_32")):
            d = table[k]["cycles"][0] - f1
            print(f"  {k:4} {lbl}  delta {d:+6d}   per line (band cost NOT removed)"
                  f" {d / 224.0:7.3f}")

    if {"F1", "K1", "F2", "K2", "H2"} <= set(table):
        d1 = table["K1"]["cycles"][0] - table["F1"]["cycles"][0]
        d2 = table["K2"]["cycles"][0] - table["F2"]["cycles"][0]
        dh = table["H2"]["cycles"][0] - table["F2"]["cycles"][0]
        print(f"\nPAIRED DELTAS (curve minus its flat twin):")
        print(f"  K1-F1 = {d1:+6d}   224 curve lines, 1 curve band")
        print(f"  K2-F2 = {d2:+6d}   224 curve lines, 2 curve bands")
        print(f"  H2-F2 = {dh:+6d}   112 curve lines, 1 curve band")
        B = d2 - d1                      # one more curve band, same line count
        L = (d1 - dh) / 112.0            # 112 more curve lines, same band count
        pred = {"K1-F1": 224 * L + B, "K2-F2": 224 * L + 2 * B, "H2-F2": 112 * L + B}
        print(f"\nFIT: line_curve = {L:.2f} cyc/line   band_curve = {B:.2f} cyc/band")
        resid = []
        for name, got in (("K1-F1", d1), ("K2-F2", d2), ("H2-F2", dh)):
            r = got - pred[name]
            resid.append(abs(r))
            print(f"  {name}: measured {got:+6d}  predicted {pred[name]:+8.2f}"
                  f"  residual {r:+6.2f}")
        print(f"  max |residual| = {max(resid):.2f}")
        table["_fit"] = {"line_curve": L, "band_curve": B, "max_resid": max(resid)}

    if args.out:
        Path(args.out).write_text(json.dumps(
            {"rom": args.rom, "stride": stride, "table": table, "failures": failures},
            indent=1))
        print(f"\nraw: {args.out}")
    if failures:
        print("\nDERIVED CHECKS FAILED — the rows above are NOT evidence:")
        for f in failures:
            print(f"  {f}")
        return 5
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", required=True)
    ap.add_argument("--lst", required=True)
    ap.add_argument("--arm", choices=("ramp", "cost"), default="ramp")
    ap.add_argument("--sweep", default="0,96,320,1024,3072,6144",
                    help="Camera_X pixel positions for the ramp arm")
    ap.add_argument("--settle", type=int, default=180)
    ap.add_argument("--sample", type=int, default=31)
    ap.add_argument("--repeat", type=int, default=1)
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    if not Path(args.rom).exists():
        sys.exit(f"ROM not found: {args.rom}")
    sym = parse_lst(Path(args.lst))
    span = sym["Parallax_Shadow_Scroll_A"] - sym["Parallax_Shadow_Bands"]
    if span % pcp.MAX_SHADOW:
        sys.exit(f"shadow span {span} is not a multiple of MAX_PARALLAX_BANDS — the symbols "
                 f"moved, or this .lst is not this ROM's")
    stride = span // pcp.MAX_SHADOW
    if stride != LEGACY_BE_SIZE + BC_SIZE:
        sys.exit(f"REFUSED: this build's band record is {stride} bytes, not the "
                 f"{LEGACY_BE_SIZE + BC_SIZE} a curve build has (legacy prefix + one "
                 f"band_curve). No canonical image carries the curve tail — sonic4 declares "
                 f"SCANLINE_CAPS $001F and BAND_CURVE_N is 0. See "
                 f"docs/benchmarks/scanline-p3/CURVES.md for the instrument-build recipe. "
                 f"Refusing rather than measuring the flat path and calling it a curve.")
    pcp.BE_SIZE = stride
    php.BE_SIZE = stride

    rom = Path(args.rom).read_bytes()
    base = rom[sym["ParallaxConfig_OJZ_Default"]:
               sym["ParallaxConfig_OJZ_Default"] + pcp.CFG_SIZE]
    zero_tab = sym["DeformTable_Zero"]
    if args.arm == "ramp":
        return run_ramp(args, sym, base, stride, zero_tab)
    return run_cost(args, sym, base, stride, zero_tab)


if __name__ == "__main__":
    raise SystemExit(main())
