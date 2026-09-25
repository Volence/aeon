#!/usr/bin/env python3
"""clip_bg_lower.py — a Sonic 2 zone's own background, lowered for a clip act, in its OWN colours.

S2-COMPRESSED-ACT, the first (B) parcel of `docs/research/2026-09-25-s2clip-longer-cpz-and-
original-bgs.md` §4 (B-1: static backgrounds). The owner flew the S2 clip act and asked for
"the bgs should be from the games". Until this, a clip act showed Oracle Jungle's editor-drawn
background in Sonic 2 palettes.

WHAT IT PRODUCES, for one donor zone: one Aeon Plane B worth of that zone's background
(64 x 64 cells), as EDITOR-LOCAL nametable words plus a deduplicated tile list. The two
consumers are `tools/clip_rom_bake.py`'s:
  * ACT DEFAULT (the zone the act starts in): the words and tiles are handed to
    `tools/inject_editor_bg.py`'s own `main()` as a synthetic override, so zone_bg.bin,
    bg_tiles.bin and a zero-band bg_anim.emp are written by the SHIPPED emitter, not a copy;
  * REGION OVERRIDE (every other zone): `layout_blob` / `tiles_blob` below, embedded in the
    clip act's data block and named by that zone's region rows (rg_bg_layout / rg_bg_tiles).
Both go through `inject_editor_bg.rebase_layout`, reused read-only, so the tile-index rebase
is the one rule the shipped act uses.

HOW, every input read out of the donor through `tools/s2_donor.py` (nothing typed):
  1. DECODE. S2 keeps a zone's background as the odd rows of its level layout, in the same
     chunk/block/art tables as the foreground (`s2_donor.load_bg_grid`).
  2. VERTICAL. The first PLANE_ROWS tile rows (512 px). Emerald Hill paints 256 px and the
     rest is chunk 0 (blank tiles); Chemical Plant paints 896 px, so its rows past 512 are
     not shown. The CPZ half is an APPROXIMATION and is stated: faithful CPZ needs a
     background taller than the plane with BG-space bands, a separate engine item.
  3. HORIZONTAL. The donor repeats with a period of P chunk columns (derived, the smallest
     P under which the painted rows repeat). The crop is PLANE_COLS consecutive tile
     columns; the start is the chunk column whose ONE invented join (the plane wrap) costs
     the fewest differing pixels, ties to the lowest start (`gen_region_bg_showcase`'s
     rule). EHZ's period is exactly 64 cells, so its wrap is the donor's own join (cost 0).
     CPZ's is 96 cells: one invented seam per 512 px, TAGGED.
  4. NATIVE PALETTE. No re-quantisation: each clip region installs its donor zone's complete
     CRAM lines 1-3, so a background keeps the line bits the donor gave it. Colour 0 stays
     TRANSPARENT (the backdrop shows through, as in Sonic 2 — see `s2_backdrop_register`).
     Line-0 cells are WARNED, not refused: line 0 is the character line in both games.
  5. PRIORITY BITS ARE KEPT, which is faithful: a Sonic 2 background cell with priority
     draws over low-priority foreground exactly as it does there.
  6. TILES. A cell whose tile has no opaque pixel becomes word 0 (the transparent tile the
     shipped rebase already reserves). Every other tile is reduced to a canonical form over
     its four flips, the flip that reaches it is folded into the word's flip bits, and
     identical canonical tiles are one tile, numbered by first occurrence row-major.

REFUSED (ClipBgError): no painted background; no horizontal period; a donor narrower than
the plane; more tiles than BG_STATIC_TILE_BUDGET (vram.toml `tiles - band_reserve`); a
nonzero word that the rebase would read as the transparent word 0; a word naming a tile past
the list. WHAT IS NOT DONE HERE: parallax (EHZ's 7 bands, the ripple, CPZ's BG-row bands)
is tools/clip_bg_scroll.py's (parcel B-2); palette cycles are not done anywhere yet.
"""

import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from vram_map import BG_STATIC_TILE_BUDGET          # noqa: E402

PLANE_COLS = 64
PLANE_ROWS = 64
TILE_BYTES = 32
FLIP_H = 0x0800
FLIP_V = 0x1000
PRIO = 0x8000


class ClipBgError(Exception):
    """A named refusal."""


def _unpack(raw):
    return [[(raw[r * 4 + c // 2] >> (4 if c % 2 == 0 else 0)) & 15 for c in range(8)]
            for r in range(8)]


def _pack(px):
    out = bytearray(TILE_BYTES)
    for r in range(8):
        for c in range(0, 8, 2):
            out[r * 4 + c // 2] = (px[r][c] << 4) | px[r][c + 1]
    return bytes(out)


def _flip(px, bits):
    if bits & FLIP_H:
        px = [row[::-1] for row in px]
    if bits & FLIP_V:
        px = px[::-1]
    return px


def _load(donor, zone):
    import s2_donor as sd
    art = bytes(sd.load_art(zone, donor))
    chunks = sd.load_chunks(zone, donor)
    blocks = sd.load_blocks(zone, donor)
    bg = sd.load_bg_grid(zone, donor).astype("int64")
    return bg, sd.chunk_tiles(chunks, blocks), art


def lower(donor, zone, loader=None):
    """(words, tiles, info) for one donor zone. `words` are PLANE_COLS x PLANE_ROWS
    editor-local nametable words, ROW-MAJOR; `tiles` are 32-byte 4bpp tiles; local index i
    in a word is tiles[i]. Pure: reads the donor, writes nothing."""
    bg, ct, art = (loader or _load)(donor, zone)
    tpc = ct.shape[1]                                   # tiles per chunk side
    rows_c = PLANE_ROWS // tpc
    painted = [r for r in range(bg.shape[0])
               if any((ct[c] & 0x7FF).any() for c in set(bg[r].tolist()))]
    if not painted:
        raise ClipBgError(f"{donor}:{zone} has no painted background row")
    nz = [c for c in range(bg.shape[1]) if bg[:max(painted) + 1, c].any()]
    width = max(nz) + 1
    period = next((p for p in range(1, width)
                   if all((bg[r, :width - p] == bg[r, p:width]).all()
                          for r in range(max(painted) + 1))), None)
    if period is None:
        raise ClipBgError(f"{donor}:{zone}'s background does not repeat horizontally over "
                          f"its painted {width} chunk columns")
    crop_c = PLANE_COLS // tpc
    if period * tpc < PLANE_COLS and PLANE_COLS % (period * tpc):
        raise ClipBgError(f"{donor}:{zone}'s period is {period * tpc} cells, which neither "
                          f"covers nor divides the {PLANE_COLS}-cell plane")
    span_c = period * 2 + crop_c + 1
    grid = bg[:rows_c, [c % period for c in range(span_c)]]
    full = ct[grid].transpose(0, 2, 1, 3).reshape(rows_c * tpc, span_c * tpc)

    pix_cache = {}

    def pixels(word):
        t = word & 0x7FF
        if t not in pix_cache:
            raw = art[t * TILE_BYTES:(t + 1) * TILE_BYTES]
            if len(raw) != TILE_BYTES:
                raise ClipBgError(f"{donor}:{zone}: a background word names tile {t}, past "
                                  f"the {len(art) // TILE_BYTES}-tile art blob")
            pix_cache[t] = _unpack(raw)
        return _flip(pix_cache[t], word)

    def column(tc):
        """The resolved (line, index) of every pixel of one tile column; index 0 is
        transparent whatever the line, so it resolves to one value."""
        out = []
        for r in range(PLANE_ROWS):
            w = int(full[r, tc])
            line = (w >> 13) & 3
            out.extend((line, v) if v else (0, 0) for row in pixels(w) for v in row)
        return out

    seams = []
    for s in range(period):
        a = column(s * tpc + PLANE_COLS)                 # what the donor really puts next
        b = column(s * tpc)                              # what the plane wrap puts there
        seams.append((sum(1 for x, y in zip(a, b) if x != y), s))
    seam_cost, start = min(seams)
    crop = full[:PLANE_ROWS, start * tpc:start * tpc + PLANE_COLS]

    index = {}
    tiles = []
    words = []
    line0 = prio = 0
    for r in range(PLANE_ROWS):
        for c in range(PLANE_COLS):
            w = int(crop[r, c])
            px = pixels(w & ~(FLIP_H | FLIP_V))
            if not any(v for row in px for v in row):
                words.append(0)                          # transparent: the reserved word 0
                continue
            forms = [(_pack(_flip(px, g)), g) for g in (0, FLIP_H, FLIP_V, FLIP_H | FLIP_V)]
            key, g = min(forms)
            if key not in index:
                index[key] = len(tiles)
                tiles.append(key)
            line = (w >> 13) & 3
            line0 += 1 if line == 0 else 0
            prio += 1 if w & PRIO else 0
            word = (w & PRIO) | (line << 13) | ((w ^ g) & (FLIP_H | FLIP_V)) | index[key]
            if word == 0:
                raise ClipBgError(
                    f"{donor}:{zone}: cell ({c}, {r}) lowers to word $0000 — local tile 0, "
                    f"line 0, no flip, no priority — which inject_editor_bg.rebase_layout "
                    f"keeps as the TRANSPARENT word, so this opaque tile would vanish")
            words.append(word)
    if len(tiles) > BG_STATIC_TILE_BUDGET:
        raise ClipBgError(
            f"{donor}:{zone}'s background needs {len(tiles)} tiles and a background may use at "
            f"most BG_STATIC_TILE_BUDGET = {BG_STATIC_TILE_BUDGET} (vram.toml bg_region tiles "
            f"- band_reserve)")
    over = [i for i, w in enumerate(words) if w and (w & 0x7FF) >= len(tiles)]
    if over:
        raise ClipBgError(f"{donor}:{zone}: {len(over)} word(s) name a tile past the "
                          f"{len(tiles)}-tile list (first at cell {over[0]})")
    info = {"donor": donor, "zone": zone, "period_cells": period * tpc,
            "crop_start_chunk": start, "seam_cost_pixels": seam_cost,
            "painted_rows_px": (max(painted) + 1) * tpc * 8, "tiles": len(tiles),
            "line0_cells": line0, "priority_cells": prio,
            "transparent_cells": sum(1 for w in words if w == 0)}
    return words, tiles, info


def override_doc(words, tiles):
    """The synthetic `editor_bg_override.json` document inject_editor_bg.main() reads:
    editor-local words, and each tile as 64 row-major pixel indices. No `anims` (the
    injector then writes its zero-band stub) and no `palette` (nothing is stamped)."""
    return {"layout": list(words),
            "tiles": [[v for row in _unpack(t) for v in row] for t in tiles]}


def layout_blob(words):
    """The engine's Plane B blob, through the shipped rebase (ROW-MAJOR, 8192 B)."""
    from inject_editor_bg import rebase_layout
    return rebase_layout(list(words))


def tiles_blob(tiles):
    """BG_Init's tile blob shape: a BE u16 byte length, then the raw 4bpp tiles."""
    body = b"".join(tiles)
    return struct.pack(">H", len(body)) + body


def s2_backdrop_register(donor):
    """The low byte of the VDP register-7 write Sonic 2's `Level:` makes (`move.w #$87LC`):
    line L, entry C. A clip act installs its donor's CRAM lines 1-3 onto CRAM lines 1-3, so
    the same byte selects the same colour in Aeon. Refuses anything but exactly one write."""
    import s2_donor as sd
    text = open(os.path.join(sd.donor_root(donor), "s2.asm"), "r", errors="replace").read()
    try:
        start = text.index("\nLevel:")
        end = text.index("\nLevel_LoadPal:", start)
    except ValueError as exc:
        raise ClipBgError(f"{donor}'s s2.asm has no `Level:` .. `Level_LoadPal:` span") from exc
    m = re.findall(r"move\.w\s+#\$87([0-9A-Fa-f]{2}),\(a6\)", text[start:end])
    if len(m) != 1:
        raise ClipBgError(f"{donor}'s s2.asm `Level:` sets the backdrop register {len(m)} "
                          f"times; expected exactly one")
    reg = int(m[0], 16)
    if reg >> 4 == 0:
        raise ClipBgError(f"{donor}'s level backdrop is on CRAM line 0 (${reg:02X}); a clip "
                          f"act installs lines 1-3 only, so that colour is not the donor's")
    return reg
