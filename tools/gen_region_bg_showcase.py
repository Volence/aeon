#!/usr/bin/env python3
"""gen_region_bg_showcase — lower the DEBUG-only region background the region bg switch is
tested against, and the palette it is shown in.

REGION BG SWITCH, TASK 2 (docs/superpowers/plans/2026-09-16-region-bg-switch.md, call C11);
SOURCE REPLACED BY parcel/showcase-classic-bg (2026-09-16).

WHAT IT IS, AND WHAT IT IS NOT. An INSTRUMENT: a second background with visibly different
ART and COLOURS, so a crossing that overwrites the BG tile arena and repaints Plane B can be
observed and gated. It exists as a DEBUG-shape delta because a regions document cannot name a
per-region background today: `bg.layoutRef` has no lowering (tools/effects_gen.py
`_check_region_bg`) and the contract schema has no tiles key at all (booked
REGION-BG-TILES-AUTHORING).

WHY THE DEFAULT SOURCE IS A CLASSIC ZONE AND NOT THE EDITOR LIBRARY. The owner flew the first
showcase (library entry `deep-forest-v15-marching-colonnade`) and reported that every library
background is a forest variant, so the switch read as the same forest scrolling. He asked for
an unmistakably different place, preferably a classic Sonic background. The default is now

  --donor s2-ooz   Sonic 2 OIL OCEAN ZONE's background plane: an orange sunset sky over
                   refinery silhouettes. Chosen over the other candidates measured on
                   2026-09-16 (every S2 and S3K background the megaact loaders reach) because it
                   is the furthest from a green forest in hue, is exactly one Aeon plane tall
                   (4 chunk rows = 64 tile rows, so rg_bg_span stays 0 = PLANE_B_SPAN), fits
                   the static tile budget with room to spare, and its art sits on ONE donor
                   palette line apart from a few oil/light accents.

The editor-library source is kept as `--entry ID` (the act palette is then emitted unchanged).

DONOR PIPELINE (`--donor s2-ooz`), every input read out of s2disasm, nothing typed:
  1. DECODE through tools/s2_donor.py, THE Sonic 2 donor reader (ojz_common's
     Kosinski + block/chunk maps, ojz_strip_gen.chunk_get_tile_word through megaact's
     _chunk_tiles). S2's layout is 16 rows of (128 FG + 128 BG) chunk ids; the BG row is the
     odd one. The zone's registry row is s2_donor's.
  2. VERTICAL. The painted rows must be exactly the first 64 tile rows (every chunk row past 3
     is chunk 0 and chunk 0 is all tile 0); refused otherwise.
  3. HORIZONTAL. Aeon's Plane B is 64 columns and wraps. The donor repeats with a period of P
     chunk columns (derived, the smallest P under which rows 0-3 repeat over the painted width);
     OOZ's P is 6 = 96 tiles, which does not divide 64. The crop is 4 CONSECUTIVE chunk columns
     of one period (3 real donor joins), and the start is the one whose single invented join,
     the wrap, costs least: cost = pixels of colour that differ between the tile column the
     donor really places after the crop and the crop's own first tile column, over all 64
     rows. Ties take the lowest start. The seam cost is printed.
  4. TRANSPARENCY. S2 sets the backdrop to `$87xx` in `Level:` (read out of s2.asm) and OOZ's
     whole sky is transparent pixels over that backdrop colour. Aeon's backdrop is not the
     donor's, so every colour-0 pixel is resolved to the backdrop colour and becomes OPAQUE
     art. (Transparent Plane B would show Aeon's backdrop instead of the sky.)
  5. COLOUR. The resolved image's distinct colours are counted by pixel weight. While more than
     15 remain, the pair with the least weighted cost min(wa, wb) * dist2(a, b) (dist2 over
     the 3-bit channels) is merged into the heavier colour; ties by the pair's colour values.
     Every merge is printed and returned. The 15 survivors, by descending weight (ties by
     value), are CRAM line SHOWCASE_LINE entries 1..15; entry 0 keeps the act palette's value.
  6. LINE. SHOWCASE_LINE = 3, measured rather than chosen: every foreground word in all nine
     OJZ act 1 sections is on line 2, and line 3 is used only by 156 cells of the ACT DEFAULT
     background (which the showcase region replaces). Line 2 also carries OJZ_ShimmerCycle
     (entries 8-11) and line 1 the rings' gold. So line 3 recolours no foreground tile.
     tools/test_gen_region_bg_showcase.py re-measures the foreground half from the shipped
     section blobs.
  7. TILES. Each cell's donor tile is re-indexed through its donor line's colour map; identical
     32-byte results are one tile, numbered by first occurrence row-major. Flip bits are kept,
     the donor priority bit is CLEARED (printed if any was set), palette bits = SHOWCASE_LINE.
  8. WHAT IS LOST, stated: OOZ's oil palette cycle (S2 PalCycle_OOZ rotates line-2 entries
     10-13) ships STATIC at the values in OOZ.bin; S2's per-line BG deformation is not
     reproduced (the region uses OJZ's scene, whose four bands all move together); the donor's
     96-tile period is cut to 64 with one invented join.

OUTPUT (DEBUG-only embeds, games/sonic4/data/levels/ojz/act1/act_assets.emp):
  zone_bg_showcase_debug.bin     the Plane B blob: 64x64 ROW-MAJOR, 8192 B, indices rebased by
                                 BG_TILE_BASE_SLOT through tools/inject_editor_bg.py's own
                                 rebase_layout (the SAME rule the act default goes through).
  bg_tiles_showcase_debug.bin    BE u16 byte length + raw 4bpp tiles (BG_Init's blob shape).
  ojz_palette_showcase_debug.bin the act palette (96 B = CRAM lines 1-3) with SHOWCASE_LINE's
                                 entries 1..15 replaced by the donor's colours. The DEBUG
                                 preset OJZ_Preset_Showcase (ojz_effects.emp) binds it.

REFUSED: an unknown donor or library id; a tile blob whose header disagrees with its body,
whose body is not 32-byte granular, or whose tile count exceeds the static budget
(BG_STATIC_TILE_BUDGET, vram.toml `tiles - band_reserve`); a layout word naming a tile past
the blob; a tile blob byte-identical to the act default's (the instrument would then show
nothing); a donor whose painted height is not one plane.

Usage:  python3 tools/gen_region_bg_showcase.py [--donor NAME | --entry ID] [--check]
        python3 tools/gen_region_bg_showcase.py --png PATH
            render the COMMITTED blobs (layout + tiles + palette) to a PNG, 512x512 px.
"""
import argparse
import hashlib
import json
import os
import pathlib
import re
import struct
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))

from vram_map import BG_TILE_BASE_SLOT, BG_STATIC_TILE_BUDGET   # noqa: E402
from inject_editor_bg import rebase_layout                       # noqa: E402

EDITOR = REPO / "games/sonic4/data/editor"
LIBRARY = EDITOR / "ojz_bglib.json"
OUT = REPO / "games/sonic4/data/generated/ojz/act1"
LAYOUT_OUT = OUT / "zone_bg_showcase_debug.bin"
TILES_OUT = OUT / "bg_tiles_showcase_debug.bin"
PALETTE_OUT = OUT / "ojz_palette_showcase_debug.bin"
ACT_TILES = OUT / "bg_tiles.bin"
ACT_PALETTE = OUT / "ojz_palette.bin"
DEFAULT_DONOR = "s2-ooz"

TILE_BYTES = 32
COLS = 64
ROWS = 64
SHOWCASE_LINE = 3            # CRAM line; see the docstring's step 6 for the measurement
LINE_COLOURS = 15            # entries 1..15; entry 0 is transparent and never drawn

# donor name -> (s2_donor donor tree, zone key in its registry)
DONORS = {"s2-ooz": ("s2disasm", "OOZ")}


class Refused(SystemExit):
    pass


def refuse(msg: str):
    raise Refused(f"gen_region_bg_showcase: REFUSED — {msg}")


# ---------------------------------------------------------------------------
# shared validation
# ---------------------------------------------------------------------------
def _validate(words, tiles, what):
    if len(tiles) < 2:
        refuse(f"the tile blob for {what} is {len(tiles)} B, shorter than its header")
    (declared,) = struct.unpack(">H", tiles[:2])
    body = len(tiles) - 2
    if declared != body:
        refuse(f"the tile blob's header says {declared} B and its body is {body} B")
    if body % TILE_BYTES:
        refuse(f"the tile body is {body} B, not a multiple of {TILE_BYTES}")
    count = body // TILE_BYTES
    if count == 0:
        refuse("the tile blob holds no tiles")
    if count > BG_STATIC_TILE_BUDGET:
        refuse(f"{what} holds {count} tiles and the static BG budget is "
               f"{BG_STATIC_TILE_BUDGET} (vram.toml bg_region tiles - band_reserve)")
    if tiles == ACT_TILES.read_bytes():
        refuse(f"{what}'s tiles are byte-identical to the act default's, so a switch to it "
               "changes nothing on screen and every gate built on it would be vacuous")
    if len(words) != COLS * ROWS:
        refuse(f"the layout is {len(words)} words; expected {COLS}x{ROWS}")
    over = [i for i, w in enumerate(words) if w and (w & 0x7FF) >= count]
    if over:
        refuse(f"{len(over)} layout word(s) name a tile past the {count} tiles "
               f"(first at word {over[0]}: ${words[over[0]]:04X})")
    return count


# ---------------------------------------------------------------------------
# --entry: an editor library entry (the first showcase's source)
# ---------------------------------------------------------------------------
def build_entry(entry: str):
    ids = [e["id"] for e in json.loads(LIBRARY.read_text())]
    if entry not in ids:
        refuse(f"{entry!r} is not an id in {LIBRARY.relative_to(REPO)} ({len(ids)} entries)")
    layout_src = (EDITOR / f"ojz_bg_{entry}.bin").read_bytes()
    tiles = (EDITOR / f"ojz_bg_{entry}_tiles.bin").read_bytes()
    if len(layout_src) % 2:
        refuse(f"the layout is {len(layout_src)} B, not whole words")
    words = list(struct.unpack(f">{len(layout_src) // 2}H", layout_src))
    if len(words) == COLS * 32:
        words += [0] * (COLS * 32)             # the injector's legacy 32-row padding
    count = _validate(words, tiles, repr(entry))
    return rebase_layout(words), tiles, count, ACT_PALETTE.read_bytes(), {"source": entry}


# ---------------------------------------------------------------------------
# --donor: a classic zone's background plane
# ---------------------------------------------------------------------------
def _md_rgb(c):
    return ((c >> 1) & 7, (c >> 5) & 7, (c >> 9) & 7)


def _s2_backdrop(s2asm, pal48):
    """The backdrop colour S2's `Level:` routine selects (`move.w #$87LC,(a6)`)."""
    start = s2asm.index("\nLevel:")
    end = s2asm.index("\nLevel_LoadPal:", start)
    m = re.findall(r"move\.w\s+#\$87([0-9A-Fa-f])([0-9A-Fa-f]),\(a6\)", s2asm[start:end])
    if len(m) != 1:
        refuse(f"s2.asm `Level:` sets the backdrop register {len(m)} times; expected exactly one")
    line, idx = int(m[0][0], 16), int(m[0][1], 16)
    if line == 0:
        refuse("s2.asm's level backdrop is on line 0, which a zone palette file does not carry")
    return pal48[(line - 1) * 16 + idx]


def _load_s2_bg(donor, zone):
    """Everything this generator needs from one Sonic 2 zone, through `s2_donor`.

    `s2_donor` is THE Sonic 2 donor reader (S2-COMPRESSED-ACT parcel 1); this file
    used to reach into `megaact_window_pageset`'s private `_load_s2` helpers, which
    was the third private copy of the same file registry.
    """
    import s2_donor as sd
    root = sd.donor_root(donor)
    s2asm = open(os.path.join(root, "s2.asm"), "r", errors="replace").read()
    pal = sd.read_bytes(sd.palette_path(zone, donor))
    if len(pal) != 96:
        refuse(f"{sd.palette_path(zone, donor)} is {len(pal)} B; a zone palette is 96 "
               f"(lines 1-3)")
    pal48 = struct.unpack(">48H", pal)
    art = sd.load_art(zone, donor)
    blocks = sd.load_blocks(zone, donor)
    chunks = sd.load_chunks(zone, donor)
    bg = sd.load_bg_grid(zone, donor).astype("int64")
    ct = sd.chunk_tiles(chunks, blocks)                     # (n_chunks, 16, 16)
    return bg, ct, bytes(art), pal48, _s2_backdrop(s2asm, pal48)


def build_donor(name: str):
    import numpy as np
    if name not in DONORS:
        refuse(f"{name!r} is not a known donor ({sorted(DONORS)})")
    donor, zone = DONORS[name]
    bg, ct, art, pal48, backdrop = _load_s2_bg(donor, zone)
    tpc = ct.shape[1]

    # 2. vertical: exactly one plane of painted rows
    painted = [r for r in range(bg.shape[0])
               if any((ct[c] & 0x7FF).any() for c in set(bg[r].tolist()))]
    rows_c = ROWS // tpc
    if not painted or max(painted) >= rows_c:
        refuse(f"{zone}'s background paints chunk rows {painted}; this lowering needs them all "
               f"inside the first {rows_c} (one {ROWS}-row plane)")

    # 3. horizontal period and crop
    # over the PAINTED width: the layout's trailing chunk-0 columns are not part of the picture
    nz = [c for c in range(bg.shape[1]) if bg[:rows_c, c].any()]
    width = max(nz) + 1
    period = next((p for p in range(1, width)
                   if all((bg[r, :width - p] == bg[r, p:width]).all() for r in range(rows_c))), None)
    if period is None:
        refuse(f"{zone}'s background does not repeat horizontally")
    crop_c = COLS // tpc
    if period < crop_c:
        refuse(f"{zone}'s period is {period} chunks, narrower than the {crop_c}-chunk plane")
    full = ct[bg[:rows_c, :period * 2 + crop_c + 1]].transpose(0, 2, 1, 3).reshape(
        rows_c * tpc, (period * 2 + crop_c + 1) * tpc)

    def colour(word, v):
        if v == 0:
            return backdrop
        return pal48[(((word >> 13) & 3) - 1) * 16 + v] if (word >> 13) & 3 else None

    def pixels(word):
        t = word & 0x7FF
        raw = art[t * TILE_BYTES:(t + 1) * TILE_BYTES]
        if len(raw) != TILE_BYTES:
            refuse(f"{zone}: a background word names tile {t}, past the art blob")
        px = [[(raw[r * 4 + c // 2] >> (4 if c % 2 == 0 else 0)) & 15 for c in range(8)]
              for r in range(8)]
        if word & 0x800:
            px = [row[::-1] for row in px]
        if word & 0x1000:
            px = px[::-1]
        return px

    for w in set(int(x) for x in np.unique(full)):
        if (w >> 13) & 3 == 0 and any(v for row in pixels(w) for v in row):
            refuse(f"{zone}: background word ${w:04X} draws on line 0, which the zone palette "
                   "does not carry")

    def col_colours(tc):
        out = []
        for r in range(ROWS):
            w = int(full[r, tc])
            px = pixels(w)
            out.extend(colour(w, px[pr][c]) for pr in range(8) for c in range(8))
        return out

    seams = []
    for s in range(period):
        a = col_colours((s + crop_c) * tpc)
        b = col_colours(s * tpc)
        seams.append((sum(1 for x, y in zip(a, b) if x != y), s))
    seam_cost, start = min(seams)
    crop = full[:, start * tpc:start * tpc + COLS]

    # 4 + 5: resolve and count colours
    weight = {}
    for r in range(ROWS):
        for c in range(COLS):
            w = int(crop[r, c])
            for row in pixels(w):
                for v in row:
                    k = colour(w, v)
                    weight[k] = weight.get(k, 0) + 1
    distinct_before = len(weight)
    alias = {k: k for k in weight}
    merges = []
    live = dict(weight)

    def d2(a, b):
        return sum((x - y) ** 2 for x, y in zip(_md_rgb(a), _md_rgb(b)))

    while len(live) > LINE_COLOURS:
        best = None
        keys = sorted(live)
        for i, a in enumerate(keys):
            for b in keys[i + 1:]:
                cost = min(live[a], live[b]) * d2(a, b)
                cand = (cost, a, b)
                if best is None or cand < best:
                    best = cand
        cost, a, b = best
        keep, drop = (a, b) if (live[a], -a) >= (live[b], -b) else (b, a)
        merges.append({"merged": f"{drop:03X}", "into": f"{keep:03X}",
                       "pixels": live[drop], "dist2": d2(a, b)})
        live[keep] += live.pop(drop)
        for k, v in alias.items():
            if v == drop:
                alias[k] = keep
    ordered = sorted(live, key=lambda k: (-live[k], k))
    entry = {k: ordered.index(alias[k]) + 1 for k in alias}

    # 7: tiles
    tile_index = {}
    tile_bytes = []
    words = []
    prio_set = 0
    for r in range(ROWS):
        for c in range(COLS):
            w = int(crop[r, c])
            prio_set += 1 if w & 0x8000 else 0
            t = w & 0x7FF
            raw = art[t * TILE_BYTES:(t + 1) * TILE_BYTES]
            line_w = w & 0x6000
            out = bytearray(TILE_BYTES)
            for i, byte in enumerate(raw):
                hi, lo = byte >> 4, byte & 15
                out[i] = (entry[colour(line_w, hi)] << 4) | entry[colour(line_w, lo)]
            key = bytes(out)
            if key not in tile_index:
                tile_index[key] = len(tile_bytes)
                tile_bytes.append(key)
            words.append((w & 0x1800) | (SHOWCASE_LINE << 13) | tile_index[key])
    body = b"".join(tile_bytes)
    tiles = struct.pack(">H", len(body)) + body
    count = _validate(words, tiles, f"donor {name}")

    act_pal = bytearray(ACT_PALETTE.read_bytes())
    if len(act_pal) != 96:
        refuse(f"{ACT_PALETTE.name} is {len(act_pal)} B; expected 96 (CRAM lines 1-3)")
    base = (SHOWCASE_LINE - 1) * 16
    for i, k in enumerate(ordered):
        struct.pack_into(">H", act_pal, (base + 1 + i) * 2, k)
    info = {"source": f"{name} (Sonic 2 {zone} background)", "period_chunks": period,
            "crop_start_chunk": start, "seam_cost_pixels": seam_cost,
            "distinct_colours_before": distinct_before, "merges": merges,
            "backdrop": f"{backdrop:03X}", "priority_bits_cleared": prio_set,
            "line": SHOWCASE_LINE, "colours": [f"{k:03X}" for k in ordered]}
    return rebase_layout(words), tiles, count, bytes(act_pal), info


def build(entry: str = None, donor: str = None):
    """(layout blob, tile blob, tile count, palette blob, info). Pure: no writes."""
    if entry is not None:
        return build_entry(entry)
    return build_donor(donor or DEFAULT_DONOR)


# ---------------------------------------------------------------------------
# --png: render the committed blobs
# ---------------------------------------------------------------------------
def render_png(path, layout, tiles, palette, scale=1):
    from PIL import Image
    words = struct.unpack(f">{COLS * ROWS}H", layout)
    body = tiles[2:]
    pal = [0] * 16 + list(struct.unpack(">48H", palette))
    img = Image.new("RGB", (COLS * 8, ROWS * 8))
    put = img.load()
    for i, w in enumerate(words):
        r0, c0 = divmod(i, COLS)
        if w == 0:
            continue
        t = ((w & 0x7FF) - BG_TILE_BASE_SLOT) & 0x7FF
        raw = body[t * TILE_BYTES:(t + 1) * TILE_BYTES]
        line = (w >> 13) & 3
        for y in range(8):
            for x in range(8):
                sx = 7 - x if w & 0x800 else x
                sy = 7 - y if w & 0x1000 else y
                v = (raw[sy * 4 + sx // 2] >> (4 if sx % 2 == 0 else 0)) & 15
                r, g, b = _md_rgb(pal[line * 16 + v])
                put[c0 * 8 + x, r0 * 8 + y] = (r * 36, g * 36, b * 36)
    if scale != 1:
        img = img.resize((img.width * scale, img.height * scale), Image.NEAREST)
    img.save(path)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    src = ap.add_mutually_exclusive_group()
    src.add_argument("--entry", help="an editor background-library id")
    src.add_argument("--donor", choices=sorted(DONORS),
                     help=f"a classic zone background (default {DEFAULT_DONOR})")
    ap.add_argument("--check", action="store_true",
                    help="verify the committed outputs match; write nothing")
    ap.add_argument("--png", metavar="PATH",
                    help="render the committed blobs to PATH; build nothing")
    args = ap.parse_args(argv)
    outs = (LAYOUT_OUT, TILES_OUT, PALETTE_OUT)
    if args.png:
        missing = [p for p in outs if not p.is_file()]
        if missing:
            print(f"MISSING: {missing[0]}", file=sys.stderr)
            return 2
        render_png(args.png, *(p.read_bytes() for p in outs))
        print(f"gen_region_bg_showcase: rendered the committed blobs to {args.png}")
        return 0
    layout, tiles, count, palette, info = build(entry=args.entry, donor=args.donor)
    digest = hashlib.md5(layout + tiles + palette).hexdigest()
    if args.check:
        for path, want in zip(outs, (layout, tiles, palette)):
            if not path.is_file():
                print(f"MISSING: {path}", file=sys.stderr)
                return 2
            if path.read_bytes() != want:
                print(f"STALE: {path} differs from what this generator emits. "
                      f"Re-run: python3 tools/gen_region_bg_showcase.py", file=sys.stderr)
                return 2
        print(f"gen_region_bg_showcase --check: OK — {count} tiles, md5 {digest}")
        return 0
    OUT.mkdir(parents=True, exist_ok=True)
    for path, data in zip(outs, (layout, tiles, palette)):
        path.write_bytes(data)
    print(f"gen_region_bg_showcase: wrote {LAYOUT_OUT.name} ({len(layout)} B) + "
          f"{TILES_OUT.name} ({count} tiles) + {PALETTE_OUT.name} ({len(palette)} B), md5 {digest}")
    print(json.dumps(info, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
