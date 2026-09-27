#!/usr/bin/env python3
"""REGIONS-P2-STEP8 measurement: today's VRAM map and what a 64x32 plane frees.

Reads games/sonic4/vram.toml (the declared placement contract that gen_vram_map.py
checks and the build consumes) and engine constants. Writes nothing.

    python3 docs/research/2026-09-27-regions-p2-step8/vram_step8.py [--root <aeon tree>]

Base-register granules are the H40 values from plutiedev (Plane A/B $2000, Window $1000 in
H40, SAT $400 in H40, HScroll $400); the engine encodes the same table in engine/vdp.emp
(VdpBase), which this script reads to cross-check.
"""
import argparse, pathlib, re, sys, tomllib

ap = argparse.ArgumentParser()
ap.add_argument("--root", default=str(pathlib.Path(__file__).resolve().parents[3]))
a = ap.parse_args()
root = pathlib.Path(a.root)
toml = tomllib.loads((root / "games/sonic4/vram.toml").read_text())

CAT = {
    "fg_art_pool": "FG art cache", "bg_region": "BG arena", "waterline_strips": "BG effect art",
    "plane_a": "nametable", "plane_b": "nametable", "window_plane": "nametable (overlay)",
    "spare_nametable": "reserved nametable", "sprite_table": "VDP table", "hscroll_table": "VDP table",
}
rows = []
for r in toml.get("region", []):
    name = r["name"]
    cat = CAT.get(name) or ("debug tag" if name.startswith("debug_") else
                            "test art" if name.startswith("test_") else "object/character art")
    rows.append((r["base"], r["tiles"], name, cat, r.get("overlay_with"), r.get("lifetime")))
for f in toml.get("free", []):
    rows.append((f["base"], f["tiles"], "[free]", "free", None, None))
rows.sort()

print("== TODAY'S MAP (games/sonic4/vram.toml) ==")
print(f"{'tiles':>11} {'bytes':>13} {'n':>4}  {'region':<22} category")
for base, n, name, cat, ov, life in rows:
    b0, b1 = base * 32, (base + n) * 32 - 1
    tag = f"  (overlays {','.join(ov)})" if ov else ""
    print(f"{base:>5}-{base+n-1:<5} ${b0:04X}-${b1:04X} {n:>4}  {name:<22} {cat}{tag}")

# coverage (non-overlay)
cover = [0] * 2048
for base, n, name, cat, ov, life in rows:
    if ov:
        continue
    for t in range(base, base + n):
        cover[t] += 1
print(f"\ncoverage: {sum(1 for c in cover if c == 1)} tiles covered once, "
      f"{sum(1 for c in cover if c == 0)} uncovered, {sum(1 for c in cover if c > 1)} double")

tot = {}
for base, n, name, cat, ov, life in rows:
    if ov:
        continue
    tot[cat] = tot.get(cat, 0) + n
print("\nby category (overlays excluded; sums to 2048):")
for k, v in sorted(tot.items(), key=lambda kv: -kv[1]):
    print(f"  {v:>5}  {k}")
print(f"  {sum(tot.values()):>5}  TOTAL")

objs = [(n, name) for base, n, name, cat, ov, life in rows if cat == "object/character art"]
print(f"\nobject+character art: {sum(n for n, _ in objs)} tiles = " +
      " + ".join(f"{name} {n}" for n, name in objs))
test = sum(n for base, n, name, cat, ov, life in rows if cat == "test art")
dbg = sum(n for base, n, name, cat, ov, life in rows if cat == "debug tag")
print(f"test art {test}, debug tags {dbg}")

# ---- engine constants (read, not assumed) ----
c = (root / "engine/system/constants.emp").read_text()
def const(name, text=c):
    m = re.search(rf"pub const {name}\s*=\s*(\$?[0-9A-Fa-f]+)", text)
    v = m.group(1)
    return int(v[1:], 16) if v.startswith("$") else int(v)
H, V = const("PLANE_H_CELLS"), const("PLANE_V_CELLS")
PA, PB, WIN = const("VRAM_PLANE_A"), const("VRAM_PLANE_B"), const("VRAM_WINDOW")
print(f"\n== ENGINE CONSTANTS == PLANE_H_CELLS {H}, PLANE_V_CELLS {V}, "
      f"VRAM_PLANE_A ${PA:04X}, VRAM_PLANE_B ${PB:04X}, VRAM_WINDOW ${WIN:04X}")
vdp = (root / "engine/vdp.emp").read_text()
gran = dict(re.findall(r"(\w+)\s*=>\s*\$([0-9A-Fa-f]+)", vdp))
print("VdpBase granules (engine/vdp.emp):", {k: '$' + v for k, v in gran.items()})
boot = (root / "engine/system/boot_data.emp").read_text()
w11 = re.search(r"dc\.b\s+(\$[0-9A-Fa-f]+)\s*//\s*\$11", boot).group(1)
w12 = re.search(r"dc\.b\s+(\$[0-9A-Fa-f]+)\s*//\s*\$12", boot).group(1)
print(f"boot reg $11 = {w11}, reg $12 = {w12}  (both 0 => window displays no cell)")

def plane_bytes(h, v):
    return h * v * 2
print(f"\nplane bytes at {H}x{V}: {plane_bytes(H, V)} = {plane_bytes(H, V)//32} tiles each")

# ---- step 8: 64x32 ----
H2, V2 = 64, 32
pb = plane_bytes(H2, V2)
a_end, b_end = PA + pb, PB + pb
freed = [(a_end, PA + plane_bytes(H, V)), (b_end, PB + plane_bytes(H, V))]
print(f"\n== STEP 8 (64x32, bases held at ${PA:04X}/${PB:04X}) ==")
print(f"each plane {pb} B = {pb//32} tiles; freed runs:")
total = 0
for lo, hi in freed:
    n = (hi - lo) // 32
    total += n
    legal = [k for k, g in gran.items() if lo % int(g, 16) == 0]
    print(f"  ${lo:04X}-${hi-1:04X}  tiles {lo//32}-{hi//32-1}  {n} tiles  legal base for: {legal}")
print(f"  total freed by the planes: {total} tiles")
wlo = WIN
inside_b = PB <= wlo < b_end
print(f"window base ${wlo:04X}: inside the 64x32 Plane B? {inside_b}. "
      f"inside a freed run? {any(lo <= wlo < hi for lo, hi in freed)}")
print("window VRAM actually READ by the VDP = rows_enabled x (H40 row stride 128 B = 4 tiles); "
      "at regs $11/$12 = 0 that is 0 tiles.")
for rows_on in (0, 4, 8, 16, 28, 32):
    print(f"  window rows enabled {rows_on:>2}: reads {rows_on*128:>5} B = {rows_on*4:>3} tiles from its base")

# ---- what objects can be promised ----
obj_today = sum(n for n, _ in objs)
print("\n== OBJECT ROOM ==")
print(f"objects+characters today: {obj_today}")
for label, add in (("step 8, window disabled or parked on a freed run it never reads", total),
                   ("step 8, window enabled full-screen inside a freed run (28 rows)", total - 28 * 4),
                   ("step 8, window gets its own full 128-tile run", total - 128)):
    print(f"  {label}: +{add} -> {obj_today + add}")
