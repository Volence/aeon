#!/usr/bin/env python3
"""REGIONS-P2-STEP8 measurement: what the Plane B height buys the BACKGROUND.

1. Re-derives the BG row streamer's containment budget (engine/level/bg.emp's own formula)
   at PLANE_V_CELLS = 64 (today) and 32 (step 8), plus the per-column VSRAM offset envelope
   a streamed map can show without a garbage row, and the wrap budget of a one-plane map.
2. Occupancy of OJZ act 1's shipped act-default background (zone_bg.bin, row-major 64x64).
3. Painted height of every Sonic 2 final background (tools/clip_bg_lower.py's own rule),
   i.e. whether a clip zone's BG is one plane tall at 64 rows and at 32.
Writes nothing.
    python3 docs/research/2026-09-27-regions-p2-step8/bg_plane_budget.py [--root R] [--no-s2]
"""
import argparse, pathlib, re, sys

ap = argparse.ArgumentParser()
ap.add_argument("--root", default=str(pathlib.Path(__file__).resolve().parents[3]))
ap.add_argument("--no-s2", action="store_true")
a = ap.parse_args()
root = pathlib.Path(a.root)

def grab(path, name):
    t = (root / path).read_text()
    m = re.search(rf"(?:pub )?const {name}\s*=\s*([^\n/]+)", t)
    return m.group(1).strip()

SCREEN_HEIGHT = int(grab("engine/system/constants.emp", "SCREEN_HEIGHT"))
STEP_ROWS = int(grab("engine/level/parallax.emp", "BG_VSCROLL_MAX_STEP_ROWS"))
WIPE_RPF = int(grab("engine/level/bg.emp", "BG_WIPE_ROWS_PER_FRAME"))
print(f"read: SCREEN_HEIGHT {SCREEN_HEIGHT}, BG_VSCROLL_MAX_STEP_ROWS {STEP_ROWS}, "
      f"BG_WIPE_ROWS_PER_FRAME {WIPE_RPF}")
print("formulas (engine/level/bg.emp): BG_SCREEN_ROWS = SCREEN_HEIGHT/8 + 1; "
      "SPARE = PLANE_V_CELLS - BG_SCREEN_ROWS; LEAD = SPARE/2; "
      "want_top = (vscroll>>3) - LEAD\n")

print(f"{'P':>3} {'span':>5} {'spare':>5} {'lead':>4} {'below':>5} "
      f"{'omin':>5} {'omax':>5} {'1-plane wrap':>12} {'wipe frames':>11} {'FG col B':>8}")
for P in (64, 32):
    rows = SCREEN_HEIGHT // 8 + 1
    spare = P - rows
    lead = spare // 2
    below = spare - lead
    # per-column VSRAM offset o added to vscroll v; the column shows lines [v+o, v+o+223].
    # Held rows [top, top+P-1], top = floor(v/8) - LEAD (mid-map). Worst case over v mod 8:
    #   top edge:    floor((v+o)/8) >= floor(v/8) - LEAD   for all v  <=>  o >= -8*LEAD
    #   bottom edge: floor((v+o+223)/8) <= floor(v/8) - LEAD + P - 1, worst v%8 = 7
    #                <=> 7+o+223 <= 8*(P-LEAD) - 1  <=>  o <= 8*(P-LEAD) - 231
    omin = -8 * lead
    omax = 8 * (P - lead) - (SCREEN_HEIGHT + 7)
    wrap = P * 8 - SCREEN_HEIGHT
    wipe = -(-P // WIPE_RPF)
    print(f"{P:>3} {P*8:>5} {spare:>5} {lead:>4} {below:>5} {omin:>5} {omax:>5} "
          f"{wrap:>12} {wipe:>11} {8 + P*2:>8}")
print("  omin/omax: the per-column VSRAM offset range a STREAMED (taller-than-plane) map can show\n"
      "  with no garbage row, tracker exactly on target. '1-plane wrap': the spread budget of a map\n"
      "  exactly one plane tall (plane_span - SCREEN_HEIGHT). FG col B: Draw_TileColumn entry bytes.")
print(f"  a scroll JUMP the held rows absorb before a garbage row shows = min(lead, below) rows:"
      f" 64 -> {min((64-29)//2, 64-29-(64-29)//2)} rows, 32 -> {min((32-29)//2, 32-29-(32-29)//2)} rows\n")

# ---- shipped deform tables (the two the plane-size doc measured at 31 px spread) ----
import math
rock = [int(20 * math.sin(2 * math.pi * i / 64)) for i in range(256)]
print(f"Rocking table deform_sine(20, 64): offsets {min(rock)}..{max(rock)} px "
      "(as.int truncation modelled with int(); range is what matters)")

# ---- OJZ act-default background ----
p = root / "games/sonic4/data/generated/ojz/act1/zone_bg.bin"
b = p.read_bytes()
print(f"\n{p.relative_to(root)}: {len(b)} B")
if len(b) == 8192:
    words = [int.from_bytes(b[i:i+2], "big") for i in range(0, 8192, 2)]  # ROW-MAJOR 64x64
    for r0, r1 in ((0, 32), (32, 64)):
        cells = words[r0*64:r1*64]
        nz = sum(1 for w in cells if w & 0x7FF)
        uniq = len({w & 0x7FF for w in cells})
        print(f"  rows {r0:>2}-{r1-1:<2}: {len(cells)} cells, {nz} with a non-zero tile index, "
              f"{uniq} distinct tile indices (mask $7FF)")
    same = words[:32*64] == words[32*64:]
    print(f"  rows 32-63 identical to rows 0-31? {same}")

if a.no_s2:
    sys.exit(0)
sys.path.insert(0, str(root / "tools"))
try:
    import s2_donor as sd, clip_bg_lower as cbl
except Exception as e:  # loud, not green
    print(f"\nS2 donor census COULD NOT RUN: {e!r}")
    sys.exit(2)
print("\nSonic 2 (s2disasm) backgrounds. content = rows above the uniform tail, at CHUNK level\n"
      "(clip_bg_lower's own 'painted' rule counts the tail's non-blank chunk as paint and reads\n"
      "2048 px for EHZ, contradicting its docstring's 256; the chunk-level rule reproduces 256\n"
      "for EHZ and 896 for CPZ, the two figures that docstring states). vperiod = smallest\n"
      "vertical repeat of the content rows, if any:")
for z in sd.zone_names("s2disasm"):
    try:
        bg, ct, art = cbl._load("s2disasm", z)
        cpx = ct.shape[1] * 8
        k = bg.shape[0] - 1
        while k > 0 and (bg[k] == bg[-1]).all():
            k -= 1
        n = k + 1
        per = next((q for q in range(1, n) if all((bg[r] == bg[r + q]).all() for r in range(n - q))), None)
        px = n * cpx
        print(f"  {z}: content {px:>5} px, vperiod {str(per * cpx) + ' px' if per else 'none':>8}; "
              f"one 64-row plane (512)? {px <= 512!s:<5} one 32-row plane (256)? {px <= 256}")
    except Exception as e:
        print(f"  {z}: COULD NOT MEASURE ({type(e).__name__}: {e})")
