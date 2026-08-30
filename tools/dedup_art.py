#!/usr/bin/env python3
"""Dedup sprite art into a unique-tile pool, preserving per-frame load order.

The contiguous layout (dplc_layout.py) DUPLICATES tiles so each frame is one
ROM run. That inflates ROM (+11.6% over the source, +25% over a deduped pool).
Since the >16-tile fix already forces multi-entry frames, contiguity's payoff is
mostly gone — so dedup to a unique-tile pool instead.

Each frame still LOADS the same tiles in the same order (so the existing
mappings, which index VRAM tiles in load order, are unchanged and rendering is
byte-identical) — the tiles just come from shared pool locations, and the
per-frame DPLC entries are re-grouped into <=16-tile contiguous runs.

Usage: dedup_art.py <art.bin> <dplc.bin> --out-art A --out-dplc D [--verify-against <art> <dplc>]
"""
import struct, sys, argparse
from pathlib import Path
import importlib.util

TILE = 32

def _load_dl():
    s = importlib.util.spec_from_file_location('dl', str(Path(__file__).parent / 'dplc_layout.py'))
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
dl = _load_dl()

def frame_tile_indices(entries):
    """Expand a frame's DPLC entries to the ordered list of source tile indices it loads."""
    out = []
    for start, count in entries:
        out.extend(range(start, start + count))
    return out

def dedup(art, frames):
    pool = []                 # list of 32-byte unique tiles, in first-seen order
    seen = {}                 # tile bytes -> pool index
    new_frames = []
    for entries in frames:
        loaded = frame_tile_indices(entries)
        pool_idx = []
        for src in loaded:
            tb = art[src*TILE:(src+1)*TILE]
            if len(tb) < TILE:
                tb = tb + b'\x00'*(TILE-len(tb))
            if tb not in seen:
                seen[tb] = len(pool); pool.append(tb)
            pool_idx.append(seen[tb])
        # re-group into contiguous <=16-tile runs (DPLC entry = contiguous run)
        new_entries = []
        i = 0
        while i < len(pool_idx):
            run_start = pool_idx[i]; run_len = 1; i += 1
            while i < len(pool_idx) and pool_idx[i] == pool_idx[i-1] + 1 and run_len < 16:
                run_len += 1; i += 1
            new_entries.append((run_start, run_len))
        new_frames.append(new_entries)
    return b''.join(pool), new_frames

def loaded_bytes(art, entries):
    """The exact tile bytes a frame loads into VRAM, in order."""
    return b''.join(art[i*TILE:(i+1)*TILE].ljust(TILE, b'\x00') for i in frame_tile_indices(entries))

def entry_cap(art, frames, cap):
    """RE-CUT: bring every frame's ENTRY count down to `cap` by un-deduping it.

    WHY THIS EXISTS (d-47 `targeted`, owner-ruled). Dedup trades ENTRIES for
    BYTES: a frame whose tiles come from many scattered pool runs is cheap in
    ROM and expensive in the DMA queue, because each contiguous run is one
    QueueDMA_Important enqueue. `engine/objects/dplc.emp` states the budget —
    a frame costs `entry_count` of DMA_IMPORTANT_SLOTS, and DPLC_ENTRY_RESERVE
    slots must stay free for PageIn_EnqueueLanding — and Sonic's deduped sheet
    blows it (13 entries against 12 slots).

    The remedy is per-frame, not global: only the frames OVER the cap give back
    their dedup. Each such frame's tiles are APPENDED to the pool as one fresh
    contiguous run, so the frame becomes `ceil(tiles/16)` entries — the 4-bit
    count field's cap being the only reason it is not always 1. Every other
    frame keeps its deduped, shared runs untouched.

    Appending is what makes this safe to do late: existing pool indices do not
    move, so no frame this pass does not rewrite can change. The tiles appended
    are byte-copies of tiles already in the pool, so the equivalence proof in
    main() still holds by construction.

    Returns (art, frames, rewritten_frame_indices).
    """
    pool = bytearray(art)
    out = [list(e) for e in frames]
    cursor = len(pool) // TILE          # first appended tile index
    rewritten = []
    for fi, ents in enumerate(out):
        if len(ents) <= cap:
            continue
        tiles = frame_tile_indices(ents)
        for src in tiles:
            pool.extend(art[src*TILE:(src+1)*TILE].ljust(TILE, b'\x00'))
        out[fi] = dl.split_contiguous_entries(cursor, len(tiles))
        cursor += len(tiles)
        rewritten.append(fi)
    return bytes(pool), out, rewritten

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('art'); ap.add_argument('dplc')
    ap.add_argument('--out-art', required=True); ap.add_argument('--out-dplc', required=True)
    ap.add_argument('--entry-cap', type=int, default=None,
                    help='re-cut frames over this many DPLC entries by un-deduping '
                         'them (d-47 targeted; the Important-queue slot budget)')
    a = ap.parse_args()
    art = Path(a.art).read_bytes()
    frames = dl.parse_dplc(Path(a.dplc).read_bytes())
    new_art, new_frames = dedup(art, frames)
    if a.entry_cap is not None:
        deduped_peak = max(len(f) for f in new_frames)
        new_art, new_frames, recut = entry_cap(new_art, new_frames, a.entry_cap)
        print(f"entry cap {a.entry_cap}: peak entries {deduped_peak} -> "
              f"{max(len(f) for f in new_frames)}, "
              f"{len(recut)} frame(s) re-cut: "
              f"{', '.join(f'${i:02X}' for i in recut) or 'none'}")

    # EQUIVALENCE PROOF: every frame must load byte-identical tiles
    mism = 0
    for fi, (oe, ne) in enumerate(zip(frames, new_frames)):
        if loaded_bytes(art, oe) != loaded_bytes(new_art, ne):
            mism += 1
            if mism <= 3: print(f"  MISMATCH frame {fi}")
    new_dplc = dl.write_dplc(new_frames)
    print(f"frames: {len(frames)}")
    print(f"art: {len(art):,} -> {len(new_art):,} bytes ({len(art)//TILE} -> {len(new_art)//TILE} tiles)")
    print(f"dplc: {len(Path(a.dplc).read_bytes()):,} -> {len(new_dplc):,} bytes")
    ents = [len(f) for f in new_frames]
    print(f"DPLC entries/frame: avg {sum(ents)/len(ents):.2f}, max {max(ents)}")
    print(f"EQUIVALENCE: {'OK — all frames load byte-identical tiles' if mism==0 else f'FAILED ({mism} mismatches)'}")
    if mism == 0:
        Path(a.out_art).write_bytes(new_art)
        Path(a.out_dplc).write_bytes(new_dplc)
        print(f"written: {a.out_art}, {a.out_dplc}")
    else:
        sys.exit(1)

if __name__ == '__main__':
    main()
