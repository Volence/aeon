#!/usr/bin/env python3
"""PNG -> editor_bg_override.json (MVP of the never-built genesis_ingest path).

Converts an indexed-friendly PNG into the OJZ Plane B background override that
inject_editor_bg.py consumes: a 64x64 nametable (flip-canonical deduped,
blob-local tile indices, PER-TILE palette line) + the unique tile blob.

PALETTE MODES:
  lock (default)  quantise each 8x8 tile to the nearest EXISTING CRAM line
                  (candidates default 2,3). Shared FG art on those lines is
                  never recoloured. Multi-line: trunks land on line 2, pink
                  flowers on line 3, etc. Nothing is stamped.
  --new-palette   EXTRACT + stamp one fresh palette (UNSAFE: recolours any FG
                  art sharing that CRAM line). Single line.

Hard gates: image tile-aligned (8x8); width divides the 512px plane;
<= 448 unique flip-canonical tiles. BG is opaque (index 0 excluded).

FILE OWNERSHIP: this tool rewrites editor_bg_override.json wholesale, so it
reads the file first. Its own keys (OWNED_KEYS) are carried across a run that
does not stamp them; any OTHER key -- `anims` above all -- is a loud refusal,
because the tool would destroy hand-authored content it does not understand.
`--out <path>` writes elsewhere, so a refusal never forces anyone to delete
content to get past it. See tools/bg_override_io.py for the full rationale.

Usage:
  python3 tools/png_to_bg_override.py <image.png> [--voffset N] [--lines 2,3]
                                      [--out other.json]
"""
import argparse
import os
import struct
import sys

import numpy as np
from PIL import Image

PLANE_W = 64          # cells; 512 px, the horizontal wrap period
PLANE_H = 64          # cells; VDP Plane B is 64x64 for OJZ
# BG_TILE_CAPACITY is imported from the generated registry mirror — one
# authority (tools/vram_map.py <- games/sonic4/vram.toml), not a restated literal.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vram_map import GAME as _VRAM_MAP_GAME, BG_TILE_CAPACITY
assert _VRAM_MAP_GAME == 'sonic4', (
    f"tools/vram_map.py was generated for {_VRAM_MAP_GAME!r}, not sonic4 — "
    "regenerate: python3 tools/gen_vram_map.py --game sonic4 "
    "--toml games/sonic4/vram.toml --py tools/vram_map.py")
DEFAULT_PAL_LINE = 2  # OJZ BG owns CRAM line 2 (decoded from ojz_palette.bin)

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OVERRIDE = os.path.join(REPO, "games/sonic4/data/editor_bg_override.json")
GEN_PALETTE = os.path.join(REPO, "games/sonic4/data/generated/ojz/act1/ojz_palette.bin")

# The keys in editor_bg_override.json that THIS tool authors: layout/tiles
# always, palette/palette_line only in EXTRACT+stamp mode.
# tools/test_bg_override_no_clobber.py pins this set against the keys the tool
# actually emits across both modes, so it cannot drift into a stale literal.
#
# Anything else -- notably `anims`, which tools/forest_bg_gen.py authors and
# inject_editor_bg.py consumes -- is a LOUD REFUSAL. See tools/bg_override_io.py
# for why refusal, and not a merge-preserve, is the terminal correct answer here.
OWNED_KEYS = frozenset(("layout", "tiles", "palette", "palette_line"))

from bg_override_io import atomic_write_json, read_existing_override


def gen_palette_line_words(cram_line):
    """The 16 CRAM words GEN_PALETTE currently holds for `cram_line`.

    Same mapping load_lock_palettes uses: the file's source lines load starting
    at CRAM line 1, so source line = cram_line - 1.
    """
    fl = cram_line - 1
    if fl < 0:
        sys.exit(f"ERROR: palette_line {cram_line} maps below CRAM line 1.")
    with open(GEN_PALETTE, "rb") as f:
        pal = f.read()
    return list(struct.unpack(">16H", pal[fl * 32:fl * 32 + 32]))


def snap9(v):
    return int(round(v / 255 * 7))


def cram_word(rgb):
    r, g, b = (snap9(c) for c in rgb)
    return (b << 9) | (g << 5) | (r << 1)


def build_palette(img):
    """EXTRACT mode: return (index_of[rgb], 16 cram words). Index 0 = darkest."""
    colours = [tuple(int(x) for x in c) for c in np.unique(img.reshape(-1, 3), axis=0)]
    if len(colours) > 16:
        sys.exit(f"ERROR: {len(colours)} colours > 16. Extract mode needs a single "
                 "16-colour image; use lock mode (default) for multi-line art.")
    colours.sort(key=lambda c: sum(c))
    idx = {c: i for i, c in enumerate(colours)}
    line = [cram_word(c) for c in colours] + [0] * (16 - len(colours))
    return idx, line


def load_lock_palettes(cram_lines):
    """{cram_line: [16 (r,g,b) in 0..7]} read from ojz_palette.bin.

    The file's 3 source lines load starting at CRAM line 1, so the slice for
    CRAM line N is source line N-1.
    """
    pal = open(GEN_PALETTE, "rb").read()
    out = {}
    for cl in cram_lines:
        fl = cl - 1
        w = struct.unpack(">16H", pal[fl * 32:fl * 32 + 32])
        out[cl] = np.array([((x >> 1) & 7, (x >> 5) & 7, (x >> 9) & 7) for x in w], float)
    return out


def quantise_tile(rgb8, palettes, opaque=True):
    """rgb8: 8x8x3. Pick the CRAM line that fits best; return (idx 8x8, line)."""
    flat = np.round(rgb8.astype(float) / 255 * 7).reshape(-1, 3)   # 64,3
    best = None
    for cl, lut in palettes.items():
        d = ((flat[:, None, :] - lut[None, :, :]) ** 2).sum(2)     # 64,16
        if opaque:
            d[:, 0] = np.inf                                       # never transparent
        idx = np.argmin(d, axis=1)
        err = d[np.arange(len(idx)), idx].sum()
        if best is None or err < best[0]:
            best = (err, cl, idx)
    _, line, idx = best
    return idx.reshape(8, 8).astype(np.uint8), line


def flip_variants(t):
    return {"": t, "H": t[:, ::-1], "V": t[::-1, :], "HV": t[::-1, ::-1]}


def canonical(t):
    return min(v.tobytes() for v in flip_variants(t).values())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("--voffset", type=int, default=0)
    ap.add_argument("--lines", default="2,3",
                    help="candidate CRAM lines for lock mode (default 2,3; 1=sky)")
    ap.add_argument("--pal-line", type=int, default=DEFAULT_PAL_LINE,
                    help="CRAM line for --new-palette (extract) mode")
    ap.add_argument("--new-palette", action="store_true",
                    help="EXTRACT+stamp one palette (UNSAFE: recolours shared FG art)")
    ap.add_argument("--out", default=None,
                    help="write elsewhere instead of the live override file — the "
                         "escape hatch when this tool refuses to clobber a key it "
                         "does not author (merge by hand afterwards)")
    args = ap.parse_args()

    out_path = args.out or OVERRIDE
    # Read (and vet) the file we are about to rewrite, before any heavy work.
    existing = read_existing_override(out_path, OWNED_KEYS, "png_to_bg_override")

    img = np.array(Image.open(args.image).convert("RGB"))
    h, w, _ = img.shape
    if w % 8 or h % 8:
        sys.exit(f"ERROR: {w}x{h} not tile-aligned (8x8).")
    tw, th = w // 8, h // 8
    if (PLANE_W * 8) % w:
        sys.exit(f"ERROR: width {w} does not divide the {PLANE_W*8}px plane -> seam.")

    stamp_palette = None
    art = [[None] * tw for _ in range(th)]      # [r][c] = (idx 8x8, cram_line)
    if args.new_palette:
        idx_of, stamp_palette = build_palette(img)
        ip = np.zeros((h, w), np.uint8)
        for c, i in idx_of.items():
            ip[(img[:, :, 0] == c[0]) & (img[:, :, 1] == c[1]) & (img[:, :, 2] == c[2])] = i
        for r in range(th):
            for c in range(tw):
                art[r][c] = (ip[r*8:r*8+8, c*8:c*8+8], args.pal_line & 3)
    else:
        lines = [int(x) for x in args.lines.split(",")]
        palettes = load_lock_palettes(lines)
        for r in range(th):
            for c in range(tw):
                art[r][c] = quantise_tile(img[r*8:r*8+8, c*8:c*8+8], palettes)

    # flip-canonical dedup on PIXEL data (palette line lives in the nametable word)
    blob, key_to_local = [], {}
    def tile_word(idx, line):
        key = canonical(idx)
        if key not in key_to_local:
            key_to_local[key] = len(blob)
            blob.append(np.frombuffer(key, np.uint8).reshape(8, 8))
        local = key_to_local[key]
        canon = blob[local]
        for flag, var in flip_variants(canon).items():
            if var.tobytes() == idx.tobytes():
                break
        return (line & 3) << 13 | (1 if "V" in flag else 0) << 12 | \
               (1 if "H" in flag else 0) << 11 | (local & 0x7FF)

    layout, line_hist = [], {}
    full_height = (th == PLANE_H)
    for r in range(PLANE_H):
        # full-height art wraps vertically (the plane loops); shorter art clamps
        # (extend top/bottom edge) to avoid a canopy-meets-roots seam.
        ar = (r - args.voffset) % th if full_height else min(max(r - args.voffset, 0), th - 1)
        for c in range(PLANE_W):
            idx, line = art[ar][c % tw]
            line_hist[line] = line_hist.get(line, 0) + 1
            layout.append(int(tile_word(idx, line)))

    if len(blob) > BG_TILE_CAPACITY:
        sys.exit(f"ERROR: {len(blob)} tiles > {BG_TILE_CAPACITY} budget. Make the art "
                 "flatter / more repetitive.")

    out = {"layout": layout, "tiles": [t.reshape(-1).astype(int).tolist() for t in blob]}
    if stamp_palette:
        # This run IS stamping, so the fresh values win -- that is its job.
        out["palette"] = stamp_palette
        out["palette_line"] = args.pal_line & 3
    else:
        # Lock mode stamps nothing, so a palette an earlier EXTRACT run wrote
        # must survive: inject_editor_bg.py stamps it into ojz_palette.bin every
        # build, and dropping it here silently reverts the BG colours.
        #
        # But retaining it is only SAFE if it still matches what this run
        # quantised against. Lock mode quantises to GEN_PALETTE, which
        # ojz_strip_gen.py re-copies from sonic_hack on every build. Carrying a
        # palette that disagrees with GEN_PALETTE would restamp colours the new
        # art was never quantised against -- the same silent-wrongness class as
        # the loss, just pointing the other way. So verify, and refuse on drift.
        if "palette_line" in existing:
            out["palette_line"] = existing["palette_line"]   # safe on its own
        if "palette" in existing:
            line = int(existing.get("palette_line", DEFAULT_PAL_LINE)) & 3
            current = gen_palette_line_words(line)
            retained = [int(w) & 0xFFFF for w in existing["palette"]]
            if retained != current:
                sys.exit(
                    f"ERROR: the existing `palette` does not match {GEN_PALETTE}\n"
                    f"  CRAM line {line} (file source line {line - 1}).\n"
                    "  Lock mode quantised this art against GEN_PALETTE, so carrying the\n"
                    "  stored palette would stamp colours the art was never fitted to.\n"
                    f"  stored : {[hex(w) for w in retained]}\n"
                    f"  current: {[hex(w) for w in current]}\n"
                    "  Re-run with --new-palette to restamp, or drop the stale `palette`\n"
                    "  key deliberately (keeping a copy), or use --out to write elsewhere.")
            out["palette"] = existing["palette"]
    atomic_write_json(out_path, out)
    carried = [k for k in ("palette", "palette_line")
               if k in out and not stamp_palette]
    mode = "EXTRACT+stamp" if stamp_palette else f"lock (lines {args.lines})"
    print(f"[png_to_bg_override] {args.image} {w}x{h} ({tw}x{th}) — {mode}")
    print(f"  unique tiles: {len(blob)}/{BG_TILE_CAPACITY}")
    print(f"  cells per CRAM line: " +
          ", ".join(f"line{k}={v}" for k, v in sorted(line_hist.items())))
    if carried:
        print(f"  carried through from the existing file: {', '.join(carried)}")


if __name__ == "__main__":
    main()
