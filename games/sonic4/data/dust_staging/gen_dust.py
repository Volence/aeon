#!/usr/bin/env python3
"""Deterministic S3K dust (Obj_DashDust) asset extractor for Aeon.

Ships two of the donor's four frame groups — the spindash charge dust (mapping
frames $0A-$10) and the 16-tile skid/slide puff block (loaded by frame $15).
The splash/drown set ($16-$1D) indexes a DIFFERENT art base and is out of scope
(no water system — see the design spec §1).

THE ART IS RE-INDEXED, NOT COPIED. The dust draws on CRAM line 0, the character
palette. Measured over the 88 shipped tiles, the art touches only palette
indices 0, 1, 12 and 13, and under Aeon's art/palettes/SonicAndTails.bin all
three non-transparent ones are WRONG (index 1 is $0EEE white in S3K but $0222
near-black here; 12 is $0ECC vs $000E red; 13 is $0CAA vs $0008 dark red). The
colour-lossless permutation is 1->6, 12->4, 13->7, a strict subset of the remap
table already pinned for Tails. See README.md.

REMAP below is the DECLARED intent, but it is not trusted blind: `verify_remap`
re-derives the S3K->Aeon permutation the same way gen_characters.py does (from
the two palette files, via its `derive_palette_remap`) and asserts our three
entries agree with it, so an edit to either palette file fails the build
loudly instead of silently baking wrong-coloured dust.

Deterministic: no timestamps, no RNG. Running twice is byte-identical.

Usage:
  ./gen_dust.py --out <dir> [--skdisasm <suite>/skdisasm]
"""

import argparse
import importlib.util
import struct
import sys
from pathlib import Path

# aeon repo root — this file is at <root>/games/sonic4/data/dust_staging/.
sys.path.insert(0, str(Path(__file__).resolve().parents[4] / 'tools'))
from suite_paths import suite_path                            # noqa: E402

TILE_SIZE = 32
ART_FIRST, ART_LAST = 0x062, 0x0B9          # donor tile span we ship (inclusive)
CHARGE_FRAMES = range(0x0A, 0x11)           # $0A..$10, the charge cycle
PUFF_FRAMES = range(0x11, 0x15)             # $11..$14, the puff cycle
PUFF_LOADER_FRAME = 0x15                    # the frame whose DPLC loads the puff block

# The measured colour-lossless permutation into Aeon's SonicAndTails line 0.
# Identity for every index the art does not touch.
REMAP = {1: 6, 12: 4, 13: 7}
ART_ALLOWED_SRC = {0, 1, 12, 13}


def load_donor_parser():
    """Borrow gen_characters.py's donor .asm parser — READ-ONLY reuse.

    The donor pointer tables are SYMBOLIC (`dc.w word_18F1E-DPLC_DashSplashDrown_`,
    not hex) and the bodies mix dc.b with dc.w, so a naive word scanner does not
    work. gen_characters.py already parses exactly this shape against exactly this
    donor tree, so we import its `frames_from_asm` rather than reimplement it.

    Imported, not refactored into a shared module, deliberately: gen_characters.py
    is load-bearing for Tails art on this branch and Knuckles art on
    wip/knuckles-task9, and a read-only import cannot perturb either. The hoist
    into a shared tools/s3k_sprites.py is ledgered as a rider. gen_characters.py
    guards its entry point with `if __name__ == '__main__'`, so importing it runs
    no work.
    """
    path = Path(__file__).resolve().parent.parent / 'characters_staging' / 'gen_characters.py'
    spec = importlib.util.spec_from_file_location('gen_characters', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def verify_remap(gc, skdisasm_root):
    """Cross-check the hardcoded REMAP against the DERIVED S3K->Aeon permutation.

    gc.derive_palette_remap() re-derives the permutation from the two real
    palette files (art/palettes/SonicAndTails.bin and skdisasm's own
    SonicAndTails.bin) on every run — it is the source of truth, not the pin
    table it also happens to assert against. We check our three dust entries
    against THAT derived table, so a palette edit that changes what 1/12/13 map
    to is caught here even if gen_characters.py's own pin were ever loosened.
    """
    derived, _ours, _s3k = gc.derive_palette_remap(Path(skdisasm_root))
    for src, dst in REMAP.items():
        if derived.get(src) != dst:
            raise ValueError(
                f"REMAP[{src}] = {dst} disagrees with the derived S3K->Aeon "
                f"palette permutation, which maps {src} -> {derived.get(src)!r}. "
                "One of art/palettes/SonicAndTails.bin or skdisasm's own copy "
                "changed — re-measure REMAP before shipping, do not just repin.")


def build_dplc(dplc_frames):
    """Rebase the charge frames' DPLC into our 88-tile blob.

    dplc_frames comes from frames_from_asm(..., 'dplc'): a list of frames, each a
    list of (tile_start, tile_count) with tile_start absolute into Dash Dust.bin.
    We re-encode as (count-1) << 12 | (tile_start - ART_FIRST).
    """
    bodies = []
    for fi in CHARGE_FRAMES:
        entries = []
        for (start, count) in dplc_frames[fi]:
            if not (ART_FIRST <= start and start + count - 1 <= ART_LAST):
                raise ValueError(f"frame ${fi:02X} entry ({start:#x},{count}) leaves the shipped span")
            if count > 16:
                raise ValueError(f"frame ${fi:02X} entry count {count} exceeds the 4-bit field")
            entries.append(((count - 1) << 12) | (start - ART_FIRST))
        bodies.append(entries)

    out = bytearray()
    cursor = 2 * len(bodies)
    for entries in bodies:
        out += struct.pack('>H', cursor)
        cursor += 2 + 2 * len(entries)
    for entries in bodies:
        out += struct.pack('>H', len(entries))
        for e in entries:
            out += struct.pack('>H', e)
    return bytes(out)


def _cell_px(size_byte):
    return (((size_byte >> 2) & 3) + 1) * 8, ((size_byte & 3) + 1) * 8


def build_mappings(map_frames, frame_ids):
    """Convert donor frames to the S4 VDP-order mapping format.

    map_frames comes from frames_from_asm(..., 'map'): a list of frames, each a
    list of (y, size, tile, x) with y/x already signed. Tile fields are kept
    as-is — they are relative to the frame's art_tile base in both formats (the
    charge frames load at window+0 and the puff frames address 0/4/8/$C of their
    resident window), and the tests assert exactly that.

    Bboxes are flip-invariant (symmetrized), matching tools/convert_s2_mappings.py.
    """
    bodies = []
    for fi in frame_ids:
        pieces = [(y, size, tile, x) for (y, size, tile, x) in map_frames[fi]]
        if not pieces:
            raise ValueError(f"frame ${fi:02X} has no pieces — wrong frame id?")

        x_min = min(p[3] for p in pieces)
        x_max = max(p[3] + _cell_px(p[1])[0] for p in pieces)
        y_min = min(p[0] for p in pieces)
        y_max = max(p[0] + _cell_px(p[1])[1] for p in pieces)
        x_min, x_max = min(x_min, -x_max), max(x_max, -x_min)
        y_min, y_max = min(y_min, -y_max), max(y_max, -y_min)
        for v in (x_min, x_max, y_min, y_max):
            if not (-128 <= v <= 127):
                raise ValueError(f"frame ${fi:02X}: bbox extent {v} leaves signed byte range")

        body = struct.pack('>bbbb', x_min, x_max, y_min, y_max)
        body += struct.pack('>H', len(pieces))
        for (y, size, attrs, x) in pieces:
            body += struct.pack('>hBBHh', y, size, 0, attrs, x)
        bodies.append(body)

    header = 2 * len(bodies)
    out = bytearray()
    cursor = header
    for b in bodies:
        out += struct.pack('>H', cursor)
        cursor += len(b)
    for b in bodies:
        out += b
    return bytes(out)


def remap_art(raw):
    """Apply the palette permutation to every nibble, asserting the source set."""
    out = bytearray(len(raw))
    for i, b in enumerate(raw):
        hi, lo = b >> 4, b & 0xF
        for nib in (hi, lo):
            if nib not in ART_ALLOWED_SRC:
                raise ValueError(
                    f"byte {i}: source index {nib} outside the measured set "
                    f"{sorted(ART_ALLOWED_SRC)} — the donor art changed, re-measure")
        out[i] = (REMAP.get(hi, hi) << 4) | REMAP.get(lo, lo)
    return bytes(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--skdisasm', default=str(suite_path('skdisasm')))
    args = ap.parse_args()

    src = Path(args.skdisasm) / 'General' / 'Sprites' / 'Dash Dust'
    # Check EVERY donor file we will read, not just the art: verify_remap below
    # reaches into the Sonic palette directory through derive_palette_remap, so a
    # partial checkout (art present, palettes missing) would otherwise surface as
    # a bare traceback from inside the borrowed parser rather than as this message.
    required = [
        src / 'Dash Dust.bin',
        src / 'DPLC - Dash Dust.asm',
        src / 'Map - Dash Dust.asm',
        Path(args.skdisasm) / 'General' / 'Sprites' / 'Sonic' / 'Palettes' / 'SonicAndTails.bin',
    ]
    missing = [p for p in required if not p.is_file()]
    if missing:
        raise SystemExit(
            "gen_dust: donor file(s) not found:\n  "
            + "\n  ".join(str(p) for p in missing)
            + "\nPass --skdisasm pointing at your skdisasm checkout root "
              "(tools/test_gen_dust.py honors AEON_SKDISASM_DIR for the same purpose).")

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    gc = load_donor_parser()
    verify_remap(gc, args.skdisasm)

    art = (src / 'Dash Dust.bin').read_bytes()
    expect = 186 * TILE_SIZE
    if len(art) != expect:
        raise ValueError(f"Dash Dust.bin is {len(art)} B, expected {expect}")

    shipped = art[ART_FIRST * TILE_SIZE:(ART_LAST + 1) * TILE_SIZE]
    (out / 'art_dust.bin').write_bytes(remap_art(shipped))

    dplc_frames = gc.frames_from_asm(src / 'DPLC - Dash Dust.asm', 'dplc')
    (out / 'dplc_dust.bin').write_bytes(build_dplc(dplc_frames))

    # The four puff frames must carry NO DPLC of their own — that is what lets
    # concurrent puffs sit on different frames out of one resident block.
    for fi in PUFF_FRAMES:
        if dplc_frames[fi]:
            raise ValueError(f"puff frame ${fi:02X} has a non-empty DPLC list; "
                             f"the resident-block assumption is broken")

    # And the loader frame must be exactly the 16 tiles we ship as that block.
    loader = dplc_frames[PUFF_LOADER_FRAME]
    if loader != [(ART_LAST - 15, 16)]:
        raise ValueError(f"frame ${PUFF_LOADER_FRAME:02X} DPLC is {loader}, "
                         f"expected [({ART_LAST - 15:#x}, 16)] — the puff block moved")

    map_frames = gc.frames_from_asm(src / 'Map - Dash Dust.asm', 'map')
    (out / 'map_dust_spindash.bin').write_bytes(build_mappings(map_frames, CHARGE_FRAMES))
    (out / 'map_dust_puff.bin').write_bytes(build_mappings(map_frames, PUFF_FRAMES))


if __name__ == '__main__':
    main()
