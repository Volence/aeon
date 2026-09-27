#!/usr/bin/env python3
"""How many BG-arena tiles each donor zone's background needs, and what a switch INTO it costs.

A MEASUREMENT for docs/research/2026-09-27-mega-act-woven.md. For the four zones
`tools/clip_bg_lower.py lower` accepts, the count IS that function's (the tile list the clip
bake ships). For Wing Fortress (refused: no horizontal repeat) and the prototype's Hidden
Palace (refused: its BG registry is not written), the count uses the same canonical-flip
dedupe (clip_bg_lower's rule: an all-transparent tile is the reserved word 0 and costs
nothing) over 64 x 64-cell windows of the donor's painted background, read directly:
  * WFZ: `s2_donor.load_bg_grid` (odd layout rows);
  * HPZ: `level/layout/HPZ_BG.bin`, the one file the prototype's `Hpz_Background:` label
    BINCLUDEs (main.asm:35668-35669), expanded by `s2_donor.expand_proto_layout`, the
    prototype format's own reader. That names ONE file; it is not the Off_Level registry the
    loader refuses to guess, so the source is labelled INFERRED-SOURCE.
The switch columns are the engine's rule as measured in
docs/research/2026-09-25-shorter-connector.md §2.3 and §8.2: an overwrite of
ceil(bytes / BG_OVERWRITE_CHUNK_BYTES) chunks, one a frame, then the DMA wipe (2 frames
measured, 3 in Z2's model, which keeps one slipped-DMA frame).

    python3 bg_tiles.py
"""
import math
import os
import pathlib
import sys

import numpy as np

REPO = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "tools"))
import clip_bg_lower as L                 # noqa: E402
import s2_donor as sd                     # noqa: E402

CHUNK_BYTES = 1824       # BG_OVERWRITE_CHUNK_BYTES, as quoted by the 09-25 report
WIPE_FRAMES = 3          # Z2's model: 2 measured + 1 slipped-DMA allowance
CAPACITY = 376           # BG_TILE_CAPACITY (engine/system/constants.emp)


def canon_set(words_grid, art):
    seen = set()
    for w in np.unique(words_grid).tolist():
        t = w & 0x7FF
        raw = art[t * 32:(t + 1) * 32]
        if len(raw) != 32:
            continue
        px = L._unpack(raw)
        if not any(v for row in px for v in row):
            continue
        forms = [L._pack(L._flip(px, g)) for g in (0, L.FLIP_H, L.FLIP_V, L.FLIP_H | L.FLIP_V)]
        seen.add(min(forms))
    return seen


def windows(bg, ct, art):
    """Tile counts of every 64-column window (16-cell steps) over the first 64 tile rows."""
    tpc = ct.shape[1]
    full = ct[bg].transpose(0, 2, 1, 3).reshape(bg.shape[0] * tpc, bg.shape[1] * tpc)
    painted = np.flatnonzero((full & 0x7FF).any(axis=0))
    rows = full[:64]
    counts = [len(canon_set(rows[:, c0:c0 + 64], art))
              for c0 in range(0, full.shape[1] - 64 + 1, 16)]
    whole = len(canon_set(full[:64, painted.min():painted.max() + 1], art))
    return min(counts), max(counts), whole


def switch_frames(tiles):
    chunks = math.ceil(tiles * 32 / CHUNK_BYTES)
    return chunks, chunks + WIPE_FRAMES


def main():
    rows = []
    for donor, zone in (("s2disasm", "EHZ"), ("s2disasm", "CPZ"), ("s2disasm", "OOZ"),
                        ("s2disasm", "MTZ")):
        _w, tiles, _info = L.lower(donor, zone)
        rows.append((zone, len(tiles), "clip_bg_lower.lower (MEASURED: the bake's own list)"))
    art = bytes(sd.load_art("WFZ", "s2disasm"))
    ct = sd.chunk_tiles(sd.load_chunks("WFZ", "s2disasm"), sd.load_blocks("WFZ", "s2disasm"))
    bg = sd.load_bg_grid("WFZ", "s2disasm").astype("int64")
    lo, hi, whole = windows(bg, ct, art)
    rows.append(("WFZ", hi, f"MEASURED, worst 64x64 window (windows {lo}..{hi}; whole painted "
                            f"width {whole}); lower() refuses WFZ"))
    donor = "s2-simonwai-disasm"
    art = bytes(sd.load_art("HPZ", donor))
    ct = sd.chunk_tiles(sd.load_chunks("HPZ", donor), sd.load_blocks("HPZ", donor))
    data = sd.read_bytes(os.path.join(sd.donor_root(donor), "level/layout/HPZ_BG.bin"))
    bg = sd.expand_proto_layout(data, "HPZ_BG").astype("int64")
    lo, hi, whole = windows(bg, ct, art)
    rows.append(("HPZ", hi, f"MEASURED count, INFERRED-SOURCE file; worst 64x64 window "
                            f"(windows {lo}..{hi}; whole {whole}); grid "
                            f"{bg.shape[1]}x{bg.shape[0]} chunks"))
    print(f"{'zone':5s} {'tiles':>5s} {'chunks':>6s} {'T_into':>6s}  source")
    for z, n, src in rows:
        ch, t = switch_frames(n)
        print(f"{z:5s} {n:5d} {ch:6d} {t:6d}  {src}")
    print(f"\nBG arena capacity {CAPACITY}; pair sums (an upper bound: shared tiles are few, "
          f"EHZ+CPZ share 2):")
    n = {r[0]: r[1] for r in rows}
    names = list(n)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            s = n[a] + n[b]
            print(f"  {a}+{b}: {s:4d} {'fits' if s <= CAPACITY else 'OVER'}")


if __name__ == "__main__":
    main()
