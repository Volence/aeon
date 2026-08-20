#!/usr/bin/env python3
"""parallax_hscroll_probe — read the per-line HScroll buffer and check it against a DERIVED ramp.

WHY THIS EXISTS BEFORE ANY CURVE DOES. Scanline design §8.3 names the curve instrument as:
"after `Parallax_Update` on a pinned camera state, read the HScroll buffer RAM and compare
every line word in the curve span against the comptime-expected ramp (derived, not copied);
repeat across a camera sweep". Nothing in this tree reads that buffer as a derived expectation.
Building the reader AFTER the curve mechanism would make the mechanism's only witness a tool
written to agree with it — the vacuous-gate pattern this tree has a postmortem for. So the
reader lands first, and it is proven RED against a hand-installed curve-shaped ramp while no
mechanism in the ROM can produce one (`--arm redfirst`). T10 inherits a detector that has
already fired.

DERIVED, NOT SNAPSHOT — and the line between "input" and "expectation" is the whole design.
The tool reads the walker's INPUTS (the parallax config bytes, the live per-band scroll words,
the live BG vscroll, the two deform phases, Camera_Y, the latched anchor line, and the deform
TABLES the config points at) and recomputes what the fill must have written, by the same
arithmetic the fill uses. It never reads a line's expectation off a neighbouring line, off the
buffer, or off a nearby pin. Reading a deform table is reading an operand of the arithmetic,
exactly as parallax_cost_probe reads the shipped config header; it is not reading the answer.

WHY EVERY INPUT IS READABLE AT THE SAMPLE POINT. `Parallax_Update`'s tail order is Step 3
(band scroll lerp) -> Step 5 (vscroll) -> Step 4a (shadow rotate) -> Step 4b (anchor overlay)
-> Step 4 (fill), with the deform phase advance immediately before the fill call
(`engine/level/parallax.emp:1030-1040`). The fill is the LAST thing the routine does, so one
completed call leaves every input and the whole buffer mutually consistent.

AND THAT IS WHY THE SAMPLE POINT IS A BREAKPOINT, NOT `run_frames`. `run_frames` returns on a
VIDEO frame boundary, which the main-loop tick is not aligned to — and after a camera write the
loop lags through a full tile-cache re-stream. Sampling there caught the machine MID-FILL: the
first draft of this probe reported 90 mismatching BG words starting at line 70, with lines
0..69 carrying the new deform phase and 70..223 the previous frame's. That is a torn read
reported as a defect, which is worse than no instrument. So every sample is taken with the
machine STOPPED at `Parallax_Update`'s entry: the previous call has fully completed, nothing is
half-written, and the next has not started. The one value that belongs to the tick about to run
rather than the one just finished is the anchor latch (`Effects_LatchWorldLines` runs earlier in
the loop), so the probe cross-checks it against `Effects_World_Y - Camera_Y` and refuses if the
two disagree — under `Debug_Scene_Freeze` with a written camera they cannot, and a disagreement
means the freeze is not holding rather than that the walker is wrong.

TWO STAGES, AND STAGE A IS WHAT MAKES STAGE B EXACT.
  Stage A  derive the per-frame SHADOW VIEW (Step 4a's vscroll rotation + Step 4b's anchored
           split) from the config + live vscroll + live scroll words + the latched anchor line,
           and check it against `Parallax_Shadow_Bands` / `Parallax_Shadow_Scroll_A/B`. This is
           not decoration: the shadow band COUNT is held only in d7 and exists nowhere in RAM,
           and the fill's band partition is undefined without it. Deriving the count and then
           proving the derivation against the machine's own shadow view is how the probe knows
           the partition it is about to check lines against.
  Stage B  derive all 224 (or 28) longwords from the DERIVED shadow view and check them against
           `Hscroll_Buffer`, reporting the FIRST mismatching line with expected and got.

THE THREE ARMS ARE SEPARATE RUNS ON PURPOSE (§8.3's camera-sweep requirement vs. the walker's
frozen-camera requirement).
  --arm frozen    value checking at N pinned camera positions. `Debug_Scene_Freeze = 1` and
                  Camera_X/Camera_Y are WRITTEN between frames; the camera is never stepped by
                  holding a direction, because under sustained motion one logic tick spans two
                  video frames and a frame's buffer stops being one call's output.
  --arm sweep     free-running camera (input held), asserting only CONTINUITY and the FG
                  camera-tracking identity. It never asserts an exact word and never a cycle
                  count. At-rest captures hide scroll artifacts; this arm is the one that runs
                  under motion, and it is deliberately weaker.
  --arm redfirst  the red-first proof. Hand-install a curve-shaped ramp into the buffer with
                  the machine paused, run the SAME checker against the shipped-derived
                  expectation (must go RED, naming the first mismatching line), then against
                  the ramp's own derived expectation (must go GREEN), then restore and let the
                  walker refill (must go GREEN again).

SMOOTHNESS SCAFFOLDING FOR T10. Every arm prints per-line FIRST DIFFERENCES of both channels,
split into BAND-INTERIOR steps and BAND-EDGE steps — a band boundary is a legitimate
discontinuity, a curve's interior is not. Interior max |d1| (step) and max |d2| (jerk) are the
quantitative readout a curve task needs; today they are 0 in flat bands and 1 in the shipped
shimmer span, which is the baseline T10 moves off.

Usage:
    python3 tools/parallax_hscroll_probe.py --rom s4.debug.bin --lst s4.debug.lst
    python3 tools/parallax_hscroll_probe.py --arm redfirst --rom ... --lst ...
    python3 tools/parallax_hscroll_probe.py --arm sweep --rom ... --lst ...
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path

HARNESS = "/home/volence/sonic_hacks/oracle-old/linux-port/harness"
sys.path.insert(0, "/home/volence/sonic_hacks/empyrean/clients/python")
sys.path.insert(0, HARNESS)
sys.path.insert(0, str(Path(__file__).resolve().parent))


# ======================================================================
# LAYOUT — transcribed from the engine source, each with its cite. Nothing below is
# inferred from a memory dump; every offset names the line that declares it.
# ======================================================================

# `Hscroll_Buffer: [u8; 896],  // 224 lines x 4 bytes (FG + BG)` — engine/ram.emp:270.
# The per-LINE fill writes one longword per screen line, FG word first then BG word:
#   .lb_line (both sampled)  engine/level/parallax.emp:1305-1322  `move.w d1,(a4)+` FG,
#                                                                 then `move.w d1,(a4)+` BG
#   .lf_line (FG sampled)    engine/level/parallax.emp:1327-1341  FG sampled, BG constant
#   .lg_line (BG sampled)    engine/level/parallax.emp:1350-1371  FG constant, BG sampled
#   .fl_line (flat)          engine/level/parallax.emp:1444-1470  `move.l d0,(a4)+` with
#                            d0 = FG<<16 | BG packed at :1284-1287
# The per-CELL fill writes 28 longwords of the same shape — engine/level/parallax.emp:1495-1541
# (`Out: Hscroll_Buffer filled (28 longwords)`), leaving lines 28..223 stale.
HSCROLL_LINES = 224
HSCROLL_ENTRY = 4                    # bytes: FG word, then BG word
HSCROLL_BYTES = HSCROLL_LINES * HSCROLL_ENTRY      # 896 — matches ram.emp:270
PERCELL_CELLS = 28

# `pub struct band_entry` — engine/level/parallax.emp. 10 bytes, RESHAPED (not resized) by
# P3 Task 7: the top is a u16 and the two 1-bit factor-op flags share one packed byte.
# `band_top_line` is THE SAME WORD as `band_top_plane`: ROM entries measure the top in
# Plane-B LINES (0..511), the per-frame shadow view measures it in SCREEN LINES (0..224).
BE_TOP          = 0    # band_top_plane / band_top_line   u16
BE_A_S1         = 2    # band_factor_a_s1
BE_A_S2         = 3
BE_B_S1         = 4
BE_B_S2         = 5
BE_OPS          = 6    # band_factor_ops — bit 0 = plane A op, bit 1 = plane B op
BE_DSHIFT_A     = 7    # band_deform_shift_a (15 = no FG deform)
BE_DSHIFT_B     = 8    # band_deform_shift_b
BE_PHASE        = 9    # band_phase_offset
BE_SIZE         = 10   # sizeof(band_entry); mirrored as BAND_ENTRY_LEN at engine/ram.emp:38
PLANE_B_SPAN    = 512  # engine/level/parallax.emp PLANE_B_SPAN — Step 4a's rotation modulus


def be_top(entry: bytes) -> int:
    """The band top, u16 big-endian. One reader, so the width lives in one place."""
    return int.from_bytes(entry[BE_TOP:BE_TOP + 2], "big")

# `pub struct parallax_config` — engine/structs.emp:161-190. 28 bytes.
CFG_BAND_COUNT      = 0     # pcfg_band_count            u8
CFG_V_FACTOR_BG     = 1     # pcfg_v_factor_bg           u8
CFG_V_FACTOR_FG     = 2
CFG_LAYER_MASK      = 3     # pcfg_layer_mask            u8
CFG_V_CENTER_Y      = 4     # pcfg_v_center_y            u16
CFG_V_OFFSET        = 6     # pcfg_v_offset              u16
CFG_TRANSITION      = 8     # pcfg_transition            u8
CFG_DEFORM_SPEED_FG = 9     # pcfg_deform_speed_fg       u8
CFG_DEFORM_SPEED_BG = 10    # pcfg_deform_speed_bg       u8
CFG_ANCHOR_CH       = 11    # pcfg_anchor_ch             u8   ($FF = PARALLAX_ANCHOR_NONE)
CFG_DEFORM_TAB_FG   = 12    # pcfg_deform_table_fg       *u8
CFG_DEFORM_TAB_BG   = 16    # pcfg_deform_table_bg       *u8
CFG_V_DEFORM_TAB_BG = 20    # pcfg_v_deform_table_bg     *u8
CFG_V_DEFORM_SPEED  = 24
CFG_V_DEFORM_SHIFT  = 25
CFG_ANCHOR_DSA      = 26    # pcfg_anchor_dsa            u8
CFG_ANCHOR_DSB      = 27    # pcfg_anchor_dsb            u8
CFG_SIZE            = 28    # sizeof(parallax_config)

# engine/system/constants.emp:602,606
MAX_PARALLAX_BANDS = 8
ANCHOR_NONE        = 0xFF
NO_DEFORM          = 15     # the shift sentinel: this plane takes no deform on this band

# The patch table `Raster_Patch_Tab` points at, walked by Raster_GetChannelBand
# (engine/effects/raster.emp:1783-1812): a WORD record count, then 10-byte entries of
# line_src / band_lo_fl / band_hi_fl / rec_off / rec_len. A patchable line_src is
# $8000 | channel (raster.emp:1786-1787). RASTER_MAX_PATCH = 4 (raster_dsl.emp:1989).
PATCH_ENTRY_SIZE = 10
RASTER_MAX_PATCH = 4

SYMS = ("Hscroll_Buffer", "Parallax_Update", "Parallax_Current_Config",
        "Parallax_Current_Scroll_A",
        "Parallax_Current_Scroll_B", "Parallax_Current_Vscroll_BG",
        "Parallax_Deform_Phase_FG", "Parallax_Deform_Phase_BG",
        "Parallax_Shadow_Bands", "Parallax_Shadow_Scroll_A", "Parallax_Shadow_Scroll_B",
        "Parallax_Transition_Frames", "Camera_X", "Camera_Y",
        "Debug_Scene_Freeze", "Effects_Screen_L", "Effects_World_Y", "Raster_Patch_Tab")


def s8(v: int) -> int:
    return v - 256 if v > 127 else v


def s16(v: int) -> int:
    v &= 0xFFFF
    return v - 0x10000 if v > 0x7FFF else v


def u16(v: int) -> int:
    return v & 0xFFFF


# ======================================================================
# THE DERIVATION — Step 4a, Step 4b and the fill, recomputed in Python.
# ======================================================================

class Shadow:
    """The per-frame screen-space band view the fillers consume.

    `tops` are SCREEN LINES (parallax.emp:82-101). `n` is the band count the filler walks,
    which lives only in d7 on the machine — deriving it is half the reason Stage A exists.
    """

    def __init__(self, tops, dsa, dsb, phase, scroll_a, scroll_b, split_line=None):
        self.n = len(tops)
        self.tops = tops
        self.dsa = dsa
        self.dsb = dsb
        self.phase = phase
        self.scroll_a = scroll_a
        self.scroll_b = scroll_b
        self.split_line = split_line

    def spans(self, total=HSCROLL_LINES):
        """The filler's band partition: band i covers [tops[i], tops[i+1]), last ends at total.

        Transcribed from Parallax_Fill_PerLine's `.next_band` (parallax.emp:1274-1283):
        `move.w #224, d5` then, unless this is the last band, `move.b band_top_line_next(a1), d5`.
        """
        out = []
        for i in range(self.n):
            lo = self.tops[i]
            hi = self.tops[i + 1] if i + 1 < self.n else total
            out.append((lo, hi))
        return out


def resolve_anchor_line(cfg, screen_l, patch_tab_bytes):
    """Step 4b's L, resolved exactly as engine/level/parallax.emp:802-885 resolves it.

    Returns (L, reason) with L = None meaning "no split this frame".

    `screen_l` is the LATCHED Effects_Screen_L[ch] read off the machine — a camera-dependent
    quantity, measured per frame and never assumed (Effects_LatchWorldLines runs between
    Camera_Update and Parallax_Update, parallax.emp:809-812). `patch_tab_bytes` is the record
    block Raster_Patch_Tab points at, or None when the table pointer is null.
    """
    ch = cfg[CFG_ANCHOR_CH]
    if ch == ANCHOR_NONE:
        return None, "no anchor (pcfg_anchor_ch = PARALLAX_ANCHOR_NONE)"
    L = s16(screen_l[ch])
    if L <= 0:
        # `.anchor_top`: off the top of the screen -> split at line 0, DO NOT clamp to the
        # band (parallax.emp:817-830).
        return 0, "L <= 0 -> whole-screen split at line 0"
    found, lo, hi = _patch_band(patch_tab_bytes, ch)
    if found:
        lo += 1                                  # fire line -> screen line (parallax.emp:850-851)
        hi += 1
        if L > hi:
            return None, f"L {L} past band_hi {hi} — record not emitted, no split"
        if L < lo:
            L = lo                               # clamp UP to the band floor
    if L < 0:
        L = 0
    if L >= HSCROLL_LINES:
        return None, f"L {L} entirely below the screen"
    return L, ("clamped to band floor" if found and L != s16(screen_l[ch]) else "unclamped")


def _patch_band(tab: bytes | None, ch: int):
    """Raster_GetChannelBand's table walk — engine/effects/raster.emp:1783-1812."""
    if not tab or len(tab) < 2:
        return False, 0, 0
    count = int.from_bytes(tab[0:2], "big")
    if count == 0:
        return False, 0, 0
    want = 0x8000 | (ch & (RASTER_MAX_PATCH - 1))
    for i in range(count):
        off = 2 + i * PATCH_ENTRY_SIZE
        if off + PATCH_ENTRY_SIZE > len(tab):
            break
        if int.from_bytes(tab[off:off + 2], "big") == want:
            return (True,
                    s16(int.from_bytes(tab[off + 2:off + 4], "big")),
                    s16(int.from_bytes(tab[off + 4:off + 6], "big")))
    return False, 0, 0


def derive_shadow(cfg: bytes, vscroll_bg: int, cur_a, cur_b, anchor_L):
    """Steps 4a + 4b, recomputed. `cfg` is the whole config (header + band entries).

    Step 4a, AS REWRITTEN BY P3 TASK 7 (world-Y re-glue): the rotation works in PLANE
    LINES, not cells. vs = Vscroll_BG mod 512 — the sub-cell part is KEPT, which is the
    whole mechanism (it used to be `>> 3`'d away, quantising every top to an 8-px edge).
    k = the last band whose plane-line top <= vs; bands are copied from k wrapping, band k
    retopped to the screen top, every other top rebased by `top - vs` (+512 when it wrapped
    past the plane bottom) and clamped to 224 SCREEN LINES. No unit conversion survives.

    Step 4b (parallax.emp:887-993): the band holding L is split, entries below shift down one
    slot, the split entry inherits band k's factors and scroll words and is retopped to L, and
    every band from the split down takes pcfg_anchor_dsa/dsb.
    """
    n = cfg[CFG_BAND_COUNT]
    ent = [cfg[CFG_SIZE + i * BE_SIZE: CFG_SIZE + (i + 1) * BE_SIZE] for i in range(n)]

    vs = u16(vscroll_bg) & (PLANE_B_SPAN - 1)    # plane LINE at the screen top
    k = 0
    for probe in range(1, n):
        if be_top(ent[probe]) > vs:
            break
        k = probe

    tops, dsa, dsb, phase, sa, sb = [], [], [], [], [], []
    src = k
    for i in range(n):
        e = ent[src]
        if i == 0:
            t = 0                                # band k starts at the screen top
        else:
            t = be_top(e) - vs
            if t <= 0:
                t += PLANE_B_SPAN                # wrapped past the plane bottom
            if t > HSCROLL_LINES:
                t = HSCROLL_LINES                # off-screen -> zero-length fill
        tops.append(t)                           # already SCREEN LINES
        dsa.append(e[BE_DSHIFT_A])
        dsb.append(e[BE_DSHIFT_B])
        phase.append(e[BE_PHASE])
        sa.append(u16(cur_a[src]))
        sb.append(u16(cur_b[src]))
        src = src + 1 if src + 1 < n else 0

    if anchor_L is None:
        return Shadow(tops, dsa, dsb, phase, sa, sb, None)

    # --- Step 4b: find the band holding L, split it, override the shifts below ---
    kk = 0
    for probe in range(1, len(tops)):
        if tops[probe] > anchor_L:
            break
        kk = probe
    ins = kk + 1
    for lst in (tops, dsa, dsb, phase, sa, sb):
        lst.insert(ins, lst[kk])                 # the split entry inherits band k wholesale
    tops[ins] = anchor_L                         # ... retopped to L
    for i in range(ins, len(tops)):
        dsa[i] = cfg[CFG_ANCHOR_DSA]
        dsb[i] = cfg[CFG_ANCHOR_DSB]
    return Shadow(tops, dsa, dsb, phase, sa, sb, anchor_L)


def per_line_mode(cfg: bytes) -> bool:
    """The mode key — engine/level/parallax.emp:1012-1024, and its twin in engine.buffers.

    per-line iff either H-deform table is non-NULL, OR the config carries an anchor.
    """
    tf = int.from_bytes(cfg[CFG_DEFORM_TAB_FG:CFG_DEFORM_TAB_FG + 4], "big")
    tb = int.from_bytes(cfg[CFG_DEFORM_TAB_BG:CFG_DEFORM_TAB_BG + 4], "big")
    return bool(tf or tb) or cfg[CFG_ANCHOR_CH] != ANCHOR_NONE


def derive_hscroll(cfg, shadow, tab_fg, tab_bg, phase_fg, phase_bg, cam_y_hi, vscroll_bg):
    """The expected (FG, BG) word pair for every written entry. THE EXPECTATION.

    Per-line (Parallax_Fill_PerLine, parallax.emp:1250-1470):
        FG word = scroll_a[band]  when the band is flat on FG
                = scroll_a[band] + (sext8(tab_fg[(phase_fg + band_phase + camY + line) & $FF])
                                    >> shift_a)   when it samples
        BG word = the same with tab_bg, Parallax_Deform_Phase_BG, Vscroll_BG and shift_b.
    A channel samples iff its table pointer is non-NULL AND the band's shift != 15
    (parallax.emp:1289-1303, 1344-1348).

    The two phase folds are the layer anchor (Harmony study defect #2, parallax.emp:1298-1302
    and :1317-1320): the FG index folds Camera_Y's pixel high word, the BG index folds
    Parallax_Current_Vscroll_BG, so the wave rides the ART rather than the screen.

    Per-cell (Parallax_Fill_PerCell, parallax.emp:1495-1541) writes one longword per CELL,
    28 of them, taken straight from the band scroll words: no sampling, no phase.
    """
    per_line = per_line_mode(cfg)
    total = HSCROLL_LINES if per_line else PERCELL_CELLS
    out = [None] * total
    # THE PER-CELL FILLER COUNTS CELLS, and it converts the shadow view's LINE-unit tops on the
    # way in: `move.b band_top_line_next(a1), d4 / lsr.w #3, d4` (parallax.emp:1516-1518), with
    # the last band's end already in cells (28) because 224 >> 3 == 28. Walking the line-unit
    # tops here instead put a 2-band per-cell config's whole 28 cells in band 0 — caught by
    # test_per_cell_mode_writes_only_28_entries, not by any emulator run, because the shipped
    # OJZ configs are all per-line.
    unit = 1 if per_line else 8
    for i, (lo, hi) in enumerate(shadow.spans(HSCROLL_LINES)):
        lo, hi = lo // unit, hi // unit
        lo, hi = max(0, min(lo, total)), max(0, min(hi, total))
        base_fg, base_bg = shadow.scroll_a[i], shadow.scroll_b[i]
        f_on = bool(tab_fg) and shadow.dsa[i] != NO_DEFORM and per_line
        b_on = bool(tab_bg) and shadow.dsb[i] != NO_DEFORM and per_line
        pf = u16(phase_fg + shadow.phase[i] + cam_y_hi)
        pb = u16(phase_bg + shadow.phase[i] + vscroll_bg)
        for line in range(lo, hi):
            fg, bg = base_fg, base_bg
            if f_on:
                fg = u16(base_fg + (s8(tab_fg[u16(pf + line) & 0xFF]) >> shadow.dsa[i]))
            if b_on:
                bg = u16(base_bg + (s8(tab_bg[u16(pb + line) & 0xFF]) >> shadow.dsb[i]))
            out[line] = (fg, bg)
    return out


# ======================================================================
# THE CHECKER — one code path, used by every arm and by the red-first proof.
# ======================================================================

def buffer_pairs(raw: bytes, count: int):
    return [(int.from_bytes(raw[i * 4:i * 4 + 2], "big"),
             int.from_bytes(raw[i * 4 + 2:i * 4 + 4], "big")) for i in range(count)]


def pack_pairs(pairs) -> bytes:
    b = bytearray()
    for fg, bg in pairs:
        b += u16(fg).to_bytes(2, "big") + u16(bg).to_bytes(2, "big")
    return bytes(b)


def check(actual, expected, label=""):
    """Compare two (FG, BG) sequences. Returns (ok, mismatches) with mismatches NAMED.

    A mismatch names the LINE, the CHANNEL, the expected word and the got word — a gate that
    only reports "something differed" is the failure mode design §8.5 forbids.
    """
    bad = []
    for line, (a, e) in enumerate(zip(actual, expected)):
        if e is None:
            continue
        for chan, (av, ev) in enumerate(zip(a, e)):
            if u16(av) != u16(ev):
                bad.append({"line": line, "chan": "FG" if chan == 0 else "BG",
                            "expected": u16(ev), "got": u16(av),
                            "expected_s": s16(ev), "got_s": s16(av), "label": label})
    return (not bad), bad


def report_mismatch(bad, limit=6):
    lines = [f"  {len(bad)} mismatching words; first {min(limit, len(bad))}:"]
    for m in bad[:limit]:
        lines.append(f"    line {m['line']:3} {m['chan']}: expected ${m['expected']:04X}"
                     f" ({m['expected_s']:+d})  got ${m['got']:04X} ({m['got_s']:+d})")
    return "\n".join(lines)


# ======================================================================
# SMOOTHNESS METRIC — the quantitative readout T10 inherits.
# ======================================================================

def smoothness(pairs, tops):
    """Per-line first (and second) differences, split BAND-INTERIOR vs BAND-EDGE.

    A band boundary is a legitimate discontinuity — the two bands carry different scroll
    factors — so folding edge steps into the same statistic as interior steps would make any
    multi-band config look rough and hide a genuinely jagged curve inside one band. Interior
    max |d1| is the step metric and interior max |d2| the jerk metric; a smooth curve keeps
    both small and, more importantly, keeps d2 near-constant-signed across the span.
    """
    edges = set(t for t in tops if 0 < t < len(pairs))
    res = {}
    for ci, name in ((0, "FG"), (1, "BG")):
        w = [s16(p[ci]) for p in pairs]
        d1_int, d1_edge = [], []
        for i in range(1, len(w)):
            (d1_edge if i in edges else d1_int).append(w[i] - w[i - 1])
        d2_int = [d1_int[i] - d1_int[i - 1] for i in range(1, len(d1_int))]
        hist = {}
        for d in d1_int:
            hist[d] = hist.get(d, 0) + 1
        res[name] = {
            "interior_steps": len(d1_int),
            "interior_nonzero": sum(1 for d in d1_int if d),
            "interior_max_abs_d1": max((abs(d) for d in d1_int), default=0),
            "interior_max_abs_d2": max((abs(d) for d in d2_int), default=0),
            "interior_d1_min": min(d1_int, default=0),
            "interior_d1_max": max(d1_int, default=0),
            "interior_d1_hist": dict(sorted(hist.items())),
            "edge_steps": [{"line": t, "d1": None} for t in sorted(edges)],
            "edge_max_abs_d1": max((abs(d) for d in d1_edge), default=0),
        }
        for e, d in zip(res[name]["edge_steps"], d1_edge):
            e["d1"] = d
    return res


def print_smoothness(sm, indent="  "):
    for name, m in sm.items():
        print(f"{indent}{name}: interior steps {m['interior_steps']:3}"
              f"  nonzero {m['interior_nonzero']:3}"
              f"  max|d1| {m['interior_max_abs_d1']}  max|d2| {m['interior_max_abs_d2']}"
              f"  d1 range [{m['interior_d1_min']:+d}, {m['interior_d1_max']:+d}]")
        print(f"{indent}    d1 histogram {m['interior_d1_hist']}")
        if m["edge_steps"]:
            print(f"{indent}    band edges "
                  + ", ".join(f"line {e['line']}: {e['d1']:+d}" for e in m["edge_steps"]))


# ======================================================================
# THE RED-FIRST RAMP — a curve-shaped gradient no shipped mechanism produces.
# ======================================================================

def curve_ramp(base_fg: int, base_bg: int, lines=HSCROLL_LINES):
    """A QUADRATIC bow: BG(L) = base + (L*L >> 7), FG(L) = base - (L >> 1).

    Curve-shaped on purpose, and unreachable by anything in the ROM today. Every shipped band
    is either flat (first differences identically 0) or sampled from a 256-byte signed deform
    table at shift >= 2, whose amplitude is +-8 and whose first differences live in {-1,0,+1}.
    This ramp's BG first difference RISES from 0 to +3 monotonically over the screen and its
    total excursion is +392 — an order of magnitude outside any table's reach, with a
    non-constant second difference no flat path can emit. If the checker cannot tell this from
    the shipped state, it cannot tell a curve from a flat band either, and T10 would inherit a
    tool that agrees with whatever it is shown.
    """
    return [(u16(base_fg - (L >> 1)), u16(base_bg + ((L * L) >> 7))) for L in range(lines)]


# ======================================================================
# MACHINE PLUMBING
# ======================================================================

async def _read(b, addr, n):
    r = await b.call("emulator/read_memory", {"addr": hex(addr), "len": n})
    return bytes.fromhex(r["bytes"])


async def _words(b, addr, n):
    raw = await _read(b, addr, n * 2)
    return [int.from_bytes(raw[i * 2:i * 2 + 2], "big") for i in range(n)]


async def _boot(b, sym, lst, settle, freeze=True):
    for attempt in range(4):
        try:
            await b.call("emulator/reset", {"wait": True, "run": False})
            break
        except Exception:
            if attempt == 3:
                raise
            await asyncio.sleep(1.5)
    await b.call("emulator/run_frames", {"frames": settle})
    if freeze:
        await b.call("emulator/write_memory",
                     {"addr": hex(sym["Debug_Scene_Freeze"]), "value": 1, "width": 1})
        await b.call("emulator/run_frames", {"frames": 2})


class Torn(Exception):
    """The sample point could not be reached, or the freeze is not holding. Never a verdict."""


async def stop_at_tick(b, sym, timeout_ms=120000):
    """Stop the machine at `Parallax_Update`'s entry — the probe's ONLY sample point.

    At that PC the previous call has fully completed (its fill wrote all 224 longwords with the
    phase it had just advanced) and the next has not started, so the buffer and every input to
    it are one consistent tick. 120 s and not 20: this is a wedge detector, not a performance
    assertion, and parallel lanes on a loaded box produced four load-induced false failures on
    a 20 s budget in this tree on 2026-08-19 alone.
    """
    await b.call("emulator/breakpoint_clear", {"all": True})
    # STEP OFF THE CURRENT PC FIRST. A breakpoint at the PC the machine is already stopped at
    # re-triggers the moment it resumes, so a stop-sample-resume loop returns instantly at the
    # same instruction and the machine never advances. Measured: the sweep arm ran 24
    # iterations against ONE frozen tick, reporting 24 identical "does not track" lines against
    # a walker that was simply never called again. One instruction of progress is enough, and
    # it costs nothing on the paths that were already elsewhere.
    await b.call("emulator/step", {})
    target = sym["Parallax_Update"] & 0xFFFFFF
    await b.call("emulator/breakpoint_add", {"addr": hex(target)})
    # AND THE STOP PC IS VERIFIED, not assumed. `wait_for_break` can return on a stop that is
    # not this breakpoint (the `step` above emits one of its own), and a sample taken at an
    # arbitrary mid-tick PC is a TORN read that looks like a walker defect: it made the buffer
    # read one tick older than the camera on 6 of 24 sweep frames. So the loop re-resumes until
    # the PC really is the routine's entry, and gives up loudly rather than sampling elsewhere.
    for _ in range(8):
        await b.call("emulator/resume", {})
        r = await b.call("emulator/wait_for_break", {"timeout_ms": timeout_ms})
        if r.get("running", False) is not False:
            await b.call("emulator/breakpoint_clear", {"all": True})
            raise Torn("never reached Parallax_Update within the wedge timeout")
        regs = await b.call("emulator/registers", {})
        if (int(str(regs["pc"]).lstrip("$"), 16) & 0xFFFFFF) == target:
            await b.call("emulator/breakpoint_clear", {"all": True})
            return
    await b.call("emulator/breakpoint_clear", {"all": True})
    raise Torn(f"stopped 8 times without landing on Parallax_Update (${target:06X})")


async def sample_state(b, sym, rom: bytes, frozen=True):
    """Read every INPUT to the fill, plus the fill's OUTPUT, at a completed-tick sample point."""
    cfg_ptr = int.from_bytes(await _read(b, sym["Parallax_Current_Config"], 4), "big") & 0xFFFFFF
    if cfg_ptr == 0:
        return None
    head = await _read(b, cfg_ptr, CFG_SIZE)
    n = head[CFG_BAND_COUNT]
    cfg = head + await _read(b, cfg_ptr + CFG_SIZE, n * BE_SIZE)

    cur_a = await _words(b, sym["Parallax_Current_Scroll_A"], MAX_PARALLAX_BANDS)
    cur_b = await _words(b, sym["Parallax_Current_Scroll_B"], MAX_PARALLAX_BANDS)
    vscroll_bg = (await _words(b, sym["Parallax_Current_Vscroll_BG"], 1))[0]
    phase_fg = (await _words(b, sym["Parallax_Deform_Phase_FG"], 1))[0]
    phase_bg = (await _words(b, sym["Parallax_Deform_Phase_BG"], 1))[0]
    cam = await _read(b, sym["Camera_X"], 8)
    cam_x_hi = int.from_bytes(cam[0:2], "big")
    cam_y_hi = int.from_bytes(cam[4:6], "big")
    screen_l = await _words(b, sym["Effects_Screen_L"], RASTER_MAX_PATCH)
    world_y = await _words(b, sym["Effects_World_Y"], RASTER_MAX_PATCH)
    # The latch belongs to the tick ABOUT to run; every other value belongs to the one just
    # finished. Under a frozen, written camera the latch is constant across ticks
    # (Effects_Screen_L[ch] = Effects_World_Y[ch] - Camera_Y, engine/effects/raster.emp:1826),
    # so the two coincide. A disagreement means the camera moved between them — the freeze is
    # not holding — and this is reported as a SETUP failure, never as a walker defect.
    ch = cfg[CFG_ANCHOR_CH] if len(cfg) > CFG_ANCHOR_CH else ANCHOR_NONE
    if frozen and ch != ANCHOR_NONE:
        want = s16(world_y[ch] - cam_y_hi)
        if s16(screen_l[ch]) != want:
            raise Torn(f"anchor latch skew: Effects_Screen_L[{ch}] = {s16(screen_l[ch])} but "
                       f"Effects_World_Y[{ch}] - Camera_Y = {want} — the camera moved between "
                       f"the latch and this sample, so the freeze is not holding")

    patch_ptr = int.from_bytes(await _read(b, sym["Raster_Patch_Tab"], 4), "big") & 0xFFFFFF
    patch = None
    if patch_ptr:
        cnt = int.from_bytes(await _read(b, patch_ptr, 2), "big")
        if 0 < cnt <= 64:
            patch = await _read(b, patch_ptr, 2 + cnt * PATCH_ENTRY_SIZE)

    tab_fg = tab_bg = None
    for off, name in ((CFG_DEFORM_TAB_FG, "fg"), (CFG_DEFORM_TAB_BG, "bg")):
        p = int.from_bytes(cfg[off:off + 4], "big") & 0xFFFFFF
        if p:
            t = await _read(b, p, 256)
            if name == "fg":
                tab_fg = t
            else:
                tab_bg = t

    shadow_raw = await _read(b, sym["Parallax_Shadow_Bands"], BE_SIZE * MAX_PARALLAX_BANDS)
    shadow_a = await _words(b, sym["Parallax_Shadow_Scroll_A"], MAX_PARALLAX_BANDS)
    shadow_b = await _words(b, sym["Parallax_Shadow_Scroll_B"], MAX_PARALLAX_BANDS)
    hs = await _read(b, sym["Hscroll_Buffer"], HSCROLL_BYTES)

    return {"cfg_ptr": cfg_ptr, "cfg": cfg, "cur_a": cur_a, "cur_b": cur_b,
            "vscroll_bg": vscroll_bg, "phase_fg": phase_fg, "phase_bg": phase_bg,
            "cam_x_hi": cam_x_hi, "cam_y_hi": cam_y_hi, "screen_l": screen_l,
            "patch": patch, "tab_fg": tab_fg, "tab_bg": tab_bg,
            "shadow_raw": shadow_raw, "shadow_a": shadow_a, "shadow_b": shadow_b,
            "hscroll": hs}


def stage_a(st):
    """Derive the shadow view and check it against the machine's. Returns (shadow, ok, msgs)."""
    L, why = resolve_anchor_line(st["cfg"], st["screen_l"], st["patch"])
    sh = derive_shadow(st["cfg"], st["vscroll_bg"], st["cur_a"], st["cur_b"], L)
    msgs = [f"anchor: {why}" + (f" -> L = {L}" if L is not None else "")]
    bad = []
    raw = st["shadow_raw"]
    for i in range(sh.n):
        got = raw[i * BE_SIZE:(i + 1) * BE_SIZE]
        for field, off, want in ((("top"), BE_TOP, sh.tops[i]),
                                 ("dsa", BE_DSHIFT_A, sh.dsa[i]),
                                 ("dsb", BE_DSHIFT_B, sh.dsb[i]),
                                 ("phase", BE_PHASE, sh.phase[i])):
            if got[off] != (want & 0xFF):
                bad.append(f"shadow band {i} {field}: derived {want}, machine {got[off]}")
        if u16(sh.scroll_a[i]) != u16(st["shadow_a"][i]):
            bad.append(f"shadow scroll_a[{i}]: derived ${u16(sh.scroll_a[i]):04X},"
                       f" machine ${u16(st['shadow_a'][i]):04X}")
        if u16(sh.scroll_b[i]) != u16(st["shadow_b"][i]):
            bad.append(f"shadow scroll_b[{i}]: derived ${u16(sh.scroll_b[i]):04X},"
                       f" machine ${u16(st['shadow_b'][i]):04X}")
    msgs.append(f"shadow view: {sh.n} bands, tops {sh.tops} (screen lines)")
    return sh, (not bad), msgs + bad


def edge_tops(cfg, sh):
    """Band tops in the unit the BUFFER is indexed in — lines per-line, cells per-cell.

    The shadow view always measures in screen lines; the per-cell buffer is indexed in cells.
    Handing line-unit tops to `smoothness` against a 28-entry buffer would mark no edges at all
    and quietly fold every band boundary into the interior statistic.
    """
    return sh.tops if per_line_mode(cfg) else [t // 8 for t in sh.tops]


def stage_b(st, sh):
    """Derive the buffer and check it. Returns (expected, actual, ok, bad, n_lines)."""
    per_line = per_line_mode(st["cfg"])
    total = HSCROLL_LINES if per_line else PERCELL_CELLS
    exp = derive_hscroll(st["cfg"], sh, st["tab_fg"], st["tab_bg"],
                         st["phase_fg"], st["phase_bg"], st["cam_y_hi"], st["vscroll_bg"])
    act = buffer_pairs(st["hscroll"], total)
    ok, bad = check(act, exp, "derived")
    return exp, act, ok, bad, total


# ======================================================================
# ARMS
# ======================================================================

async def arm_frozen(b, sym, rom, positions, out, settle_frames=30):
    """Value checking at N pinned camera positions. The camera is WRITTEN, never held."""
    fails = 0
    for cx, cy in positions:
        if cx is not None:
            await b.call("emulator/write_memory",
                         {"addr": hex(sym["Camera_X"]), "value": cx << 16, "width": 4})
        if cy is not None:
            await b.call("emulator/write_memory",
                         {"addr": hex(sym["Camera_Y"]), "value": cy << 16, "width": 4})
        # Settle BEFORE sampling: a camera write is a teleport, and the tile-cache re-stream
        # it triggers lags the main loop for many video frames. The sample point below is
        # tick-exact regardless, but a lagging loop is not the state a value check should
        # describe. This budget is a settle, never an assertion.
        await b.call("emulator/run_frames", {"frames": settle_frames})
        tag = f"camera ({cx}, {cy})"
        try:
            await stop_at_tick(b, sym)
            st = await sample_state(b, sym, rom)
        except Torn as e:
            print(f"\n{tag}: SETUP FAILURE — {e}")
            fails += 1
            continue
        if st is None:
            print(f"{tag}: NO ACTIVE PARALLAX CONFIG — nothing to check")
            fails += 1
            continue
        sh, a_ok, a_msgs = stage_a(st)
        exp, act, b_ok, bad, total = stage_b(st, sh)
        mode = "per-line" if per_line_mode(st["cfg"]) else "per-cell"
        print(f"\n{tag}  config ${st['cfg_ptr']:06X}  {mode}  {total} entries checked")
        for m in a_msgs:
            print(f"  {m}")
        if not a_ok:
            print("  STAGE A FAIL — the derived shadow view disagrees with the machine's")
            fails += 1
        if b_ok:
            print(f"  STAGE B ok — all {total} derived entries match Hscroll_Buffer")
        else:
            print("  STAGE B FAIL")
            print(report_mismatch(bad))
            fails += 1
        sm = smoothness(act, edge_tops(st["cfg"], sh))
        print("  smoothness (first differences of the buffer):")
        print_smoothness(sm, indent="    ")
        out.append({"camera": [cx, cy], "mode": mode, "entries": total,
                    "stage_a_ok": a_ok, "stage_b_ok": b_ok, "shadow_tops": sh.tops,
                    "split_line": sh.split_line, "mismatches": bad[:16],
                    "smoothness": sm})
    return fails


async def arm_redfirst(b, sym, rom, out):
    """The red-first proof — the exact inversion of normal red-first.

    The instrument must detect curve-shaped output BEFORE any curve mechanism exists, so the
    curve is hand-installed in RAM and the SAME checker is run against two expectations.
    """
    await b.call("emulator/run_frames", {"frames": 6})
    try:
        await stop_at_tick(b, sym)
        st = await sample_state(b, sym, rom)
    except Torn as e:
        print(f"SETUP FAILURE — {e}")
        return 1
    if st is None:
        print("no active parallax config — cannot run the red-first proof")
        return 1
    sh, a_ok, a_msgs = stage_a(st)
    exp, act, b_ok, bad, total = stage_b(st, sh)
    fails = 0
    print(f"config ${st['cfg_ptr']:06X}  {'per-line' if per_line_mode(st['cfg']) else 'per-cell'}"
          f"  {total} entries")
    for m in a_msgs:
        print(f"  {m}")

    print("\n[0] CONTROL — the shipped state against its derived expectation")
    if b_ok and a_ok:
        print(f"    GREEN as required: all {total} entries match")
    else:
        print("    FAIL: the control is not green, so nothing below means anything")
        print(report_mismatch(bad))
        return 1

    # --- install the curve-shaped ramp. The machine is ALREADY stopped at the sample point
    # (stop_at_tick above), which is what makes the poison observable at all: resume it and the
    # very next Parallax_Update overwrites all 224 longwords before anything could read them.
    base_fg, base_bg = act[0]
    ramp = curve_ramp(base_fg, base_bg, total)
    await b.call("emulator/write_memory",
                 {"addr": hex(sym["Hscroll_Buffer"]), "bytes": pack_pairs(ramp).hex().upper()})
    installed = buffer_pairs(await _read(b, sym["Hscroll_Buffer"], total * 4), total)
    if installed != [(u16(f), u16(g)) for f, g in ramp]:
        print("\n[1] FAIL: the ramp did not land in RAM — the proof cannot proceed")
        return 1
    print(f"\n[1] RAMP INSTALLED — quadratic bow, {total} entries, "
          f"BG ${u16(ramp[0][1]):04X} -> ${u16(ramp[-1][1]):04X}"
          f" (excursion {s16(ramp[-1][1]) - s16(ramp[0][1]):+d} px)")
    print("    ramp smoothness (what a curve mechanism would look like):")
    print_smoothness(smoothness(installed, edge_tops(st["cfg"], sh)), indent="      ")

    print("\n[2] RED — the same checker, ramp in RAM, shipped-derived expectation")
    ok2, bad2 = check(installed, exp, "derived")
    if ok2:
        print("    FAIL: the checker accepted a curve-shaped buffer against a flat expectation."
              "\n    An instrument that cannot go red here cannot witness T10's curves.")
        fails += 1
    else:
        print("    RED as required.")
        print(report_mismatch(bad2))

    print("\n[3] GREEN — the same checker, same RAM, the RAMP's own expectation")
    ok3, bad3 = check(installed, ramp, "ramp")
    if ok3:
        print(f"    GREEN as required: all {total} entries match the ramp expectation")
    else:
        print("    FAIL: the checker rejected the buffer against its own expectation")
        print(report_mismatch(bad3))
        fails += 1

    print("\n[4] RESTORE — write the derived words back, re-check")
    await b.call("emulator/write_memory",
                 {"addr": hex(sym["Hscroll_Buffer"]), "bytes": pack_pairs(exp).hex().upper()})
    back = buffer_pairs(await _read(b, sym["Hscroll_Buffer"], total * 4), total)
    ok4, bad4 = check(back, exp, "restored")
    print("    GREEN as required" if ok4 else "    FAIL after restore\n" + report_mismatch(bad4))
    fails += 0 if ok4 else 1

    print("\n[5] RESTORE BY THE WALKER — let it refill, re-derive from scratch")
    await stop_at_tick(b, sym)
    st5 = await sample_state(b, sym, rom)
    sh5, a5_ok, a5_msgs = stage_a(st5)
    exp5, act5, b5_ok, bad5, total5 = stage_b(st5, sh5)
    if a5_ok and b5_ok:
        print(f"    GREEN as required: all {total5} entries match after the walker refilled")
    else:
        print("    FAIL: the shipped state does not re-derive after the poison was removed")
        print(report_mismatch(bad5))
        fails += 1

    out.append({"control_ok": b_ok and a_ok, "red_fired": not ok2,
                "red_first_mismatch": bad2[0] if bad2 else None,
                "red_mismatch_count": len(bad2),
                "ramp_expectation_ok": ok3, "restore_ok": ok4,
                "walker_refill_ok": a5_ok and b5_ok,
                "ramp_smoothness": smoothness(installed, edge_tops(st["cfg"], sh))})
    return fails


async def arm_sweep(b, sym, rom, frames, out):
    """Free-running camera. Continuity and camera-tracking ONLY — never an exact word.

    The frozen arm owns value checking, because under sustained motion one logic tick spans two
    video frames and a frame's buffer stops being one call's output. What survives motion is
    STRUCTURE: inside a band the buffer must stay continuous (no step larger than the deform
    amplitude the tables can reach), and the FG word must keep tracking -Camera_X, which is the
    identity a scroll artifact breaks first.
    """
    await b.call("emulator/write_memory",
                 {"addr": hex(sym["Debug_Scene_Freeze"]), "value": 0, "width": 1})
    # HELD, NOT PRESSED PER FRAME — and that is what makes consecutive samples consecutive
    # WALKER CALLS. `emulator/press` runs a fixed number of VIDEO frames, so a press-then-break
    # loop can pass through a Parallax_Update inside the press and another on the way to the
    # breakpoint: two calls between samples, and the one-tick-lagged identity below then holds
    # on some frames and not others (measured: 4 of 24). A persistent held set lets the
    # breakpoint alone advance the machine, exactly one call per sample.
    await b.call("emulator/hold", {"buttons": ["right"], "down": True})
    fails, samples = 0, []
    prev_cam = prev_fg = None
    for f in range(frames):
        try:
            await stop_at_tick(b, sym)
            st = await sample_state(b, sym, rom, frozen=False)
        except Torn as e:
            print(f"  frame {f}: SETUP FAILURE — {e}")
            fails += 1
            break
        if st is None:
            continue
        sh, a_ok, _ = stage_a(st)
        total = HSCROLL_LINES if per_line_mode(st["cfg"]) else PERCELL_CELLS
        act = buffer_pairs(st["hscroll"], total)
        sm = smoothness(act, edge_tops(st["cfg"], sh))
        # Continuity: the interior step bound is the widest excursion a deform sample can
        # contribute between adjacent lines, derived from the tables actually attached —
        # max|table| >> min(live shift) on each channel, doubled (the sample may swing from
        # one extreme to the other), never a hand-typed number.
        bound = {}
        for name, tab, shifts in (("FG", st["tab_fg"], sh.dsa), ("BG", st["tab_bg"], sh.dsb)):
            live = [s for s in shifts if s != NO_DEFORM]
            bound[name] = 0 if (not tab or not live) else \
                2 * (max(abs(s8(v)) for v in tab) >> min(live))
            if sm[name]["interior_max_abs_d1"] > bound[name]:
                print(f"  frame {f}: {name} interior step {sm[name]['interior_max_abs_d1']}"
                      f" exceeds the derived bound {bound[name]} — discontinuity under motion")
                fails += 1
        cam_x = s16(st["cam_x_hi"])
        fg0 = s16(act[0][0])
        # THE ONE-TICK-LAGGED TRACKING IDENTITY. Plane A is hard-locked to the camera and never
        # lerped (parallax.emp:606-614), so band 0's FG word is exactly -camX whenever that band
        # is flat on FG. But the sample point is Parallax_Update's ENTRY, so the buffer in hand
        # was filled by the PREVIOUS call, against the PREVIOUS camera — under motion that is 16
        # px away, and asserting against the camera read in the same breath reports a 16-px
        # "failure" on every frame of a correct walker (measured: it did, on 19 of 24 frames).
        # Consecutive samples are always consecutive CALLS, because the breakpoint fires per
        # call and not per video frame, so the previous sample's camera is exactly the right
        # comparand and lag cannot desynchronise it.
        if sh.dsa[0] == NO_DEFORM and prev_cam is not None and fg0 != -prev_cam:
            print(f"  frame {f}: FG word ${u16(act[0][0]):04X} ({fg0}) does not track the"
                  f" PREVIOUS tick's -Camera_X ({-prev_cam})")
            fails += 1
        # Monotonicity: holding right, the FG word must never move backwards.
        if prev_fg is not None and fg0 > prev_fg:
            print(f"  frame {f}: FG word went BACKWARDS, {prev_fg} -> {fg0}, while"
                  f" scrolling right")
            fails += 1
        samples.append({"frame": f, "cam_x": cam_x, "fg0": fg0, "tops": sh.tops,
                        "fg_max_d1": sm["FG"]["interior_max_abs_d1"],
                        "bg_max_d1": sm["BG"]["interior_max_abs_d1"], "bound": bound})
        prev_cam = cam_x
        prev_fg = fg0
    await b.call("emulator/release_all", {})
    # THE ANTI-VACUITY CHECK FOR THIS ARM. Every assertion above is conditional on motion; if
    # the camera never moved, this arm ran and tested nothing, which is the exact shape of a
    # gate that asserts only "something happened".
    moved = bool(samples) and (samples[-1]["cam_x"] != samples[0]["cam_x"])
    print(f"  {len(samples)} moving-camera frames, Camera_X "
          f"{samples[0]['cam_x'] if samples else '?'} -> {prev_cam}"
          + ("" if moved else "  !! THE CAMERA NEVER MOVED — this arm asserted nothing"))
    if not moved:
        fails += 1
    if samples:
        print(f"  interior max|d1| over the sweep: FG {max(s['fg_max_d1'] for s in samples)},"
              f" BG {max(s['bg_max_d1'] for s in samples)}"
              f"  (derived bounds {samples[-1]['bound']})")
    out.append({"frames": len(samples), "moved": bool(moved), "samples": samples})
    return fails


# ======================================================================

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--rom", default="s4.debug.bin")
    ap.add_argument("--lst", default="s4.debug.lst")
    ap.add_argument("--arm", default="frozen", choices=("frozen", "redfirst", "sweep", "all"))
    ap.add_argument("--settle", type=int, default=180)
    ap.add_argument("--sweep-frames", type=int, default=24)
    ap.add_argument("--repeat", type=int, default=1)
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    args.rom = str(Path(args.rom).resolve())
    args.lst = str(Path(args.lst).resolve())
    if not Path(args.rom).is_file():
        print(f"ROM not found: {args.rom}", file=sys.stderr)
        return 3
    from raster_cost_probe import parse_lst          # noqa: E402 — needs the sys.path above
    from aether import BusClient                     # noqa: E402
    from launcher import headless_emulator           # noqa: E402
    sym = parse_lst(args.lst)
    missing = [s for s in SYMS if s not in sym]
    if missing:
        print(f"symbols missing: {', '.join(missing)}", file=sys.stderr)
        return 3
    rom = Path(args.rom).read_bytes()

    # Pinned camera positions. Written, not held — see arm_frozen. The first entry is
    # (None, None): the boot camera, untouched, so one position is always the state the ROM
    # actually reaches rather than one this tool invented.
    positions = [(None, None), (96, 144), (256, 144), (96, 320), (512, 96)]

    results = {"arms": {}, "rom": args.rom}
    rc = 0

    async def _run(sock, arm):
        b = BusClient(socket_path=sock, client_id="hsprobe",
                      client_name="parallax_hscroll_probe")
        await b.connect()
        await b.call("emulator/load_symbols", {"path": args.lst})
        await _boot(b, sym, args.lst, args.settle, freeze=(arm != "sweep"))
        out = results["arms"].setdefault(arm, [])
        if arm == "frozen":
            n = await arm_frozen(b, sym, rom, positions, out)
        elif arm == "redfirst":
            n = await arm_redfirst(b, sym, rom, out)
        else:
            n = await arm_sweep(b, sym, rom, args.sweep_frames, out)
        await b.close()
        return n

    arms = ("frozen", "redfirst", "sweep") if args.arm == "all" else (args.arm,)
    for rep in range(args.repeat):
        for arm in arms:
            print("=" * 72)
            print(f"ARM {arm}" + (f"  (repeat {rep + 1}/{args.repeat})"
                                  if args.repeat > 1 else ""))
            print("=" * 72)
            with headless_emulator(args.rom) as sock:
                rc += asyncio.run(_run(sock, arm))

    print("\n" + "=" * 72)
    print("PASS" if rc == 0 else f"FAIL — {rc} failing check(s)")
    if args.out:
        Path(args.out).write_text(json.dumps(results, indent=2) + "\n")
        print(f"raw: {args.out}")
    return 0 if rc == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
