#!/usr/bin/env python3
"""Generate Plane B multi-band nametable layouts (§4.6 T10).

A Plane B nametable is 64 cells wide × 32 cells tall = 4096 bytes (one
2-byte word per cell). For zones with horizontal parallax bands, each band
covers a contiguous range of cell rows; the visible band stack should
align with the zone's parallax_config band TOP_CELL values so that visual
art transitions and parallax-rate transitions coincide.

Genesis nametable cell word layout (big-endian):
  bit 15:    priority (0 = behind, 1 = above sprites of same priority)
  bits 14:13: palette line (0..3)
  bit 12:    v-flip
  bit 11:    h-flip
  bits 10:0: tile index (0..2047 — referencing the tile pool loaded into VRAM)

Usage (in a Python build helper or run directly):

    from gen_multi_band_bg import cell, gen_band_stack

    bands = [
        # rows:     count of cell rows this band occupies
        # cells:    EITHER a list of cell words (length 64, one per column)
        #           OR a callable (col_idx, row_in_band) -> cell_word
        {'rows':  4, 'cells': [cell(SKY_TILE, palette=0)] * 64},
        {'rows':  6, 'cells': [cell(MOUNTAIN_FAR, palette=1)] * 64},
        ...
    ]
    gen_band_stack(bands, 'art/myzone/bg_layout.bin')

Bands' total rows must sum to 32. Each row emits 64 cells × 2 bytes. The
output file is a flat 4096-byte binary suitable for BINCLUDE.

Authoring discipline (§4.6 spec):
- Place band boundaries at the same TOP_CELL values as the zone's
  ParallaxConfig_<Zone>'s `band TOP=` declarations. The build-tool wrap
  analysis (in spec section "Build-time validation") will warn if a band
  with factor >= 1/2 has a non-seamless tile-edge wrap, since fast-scrolling
  bands repeat horizontally as the camera moves.
- Authors typically use a different palette line per band (0..3) so each
  band has a visually distinct color set even with the same tile shapes.
- For seamless horizontal repetition (factor 1/2 bands), choose tile patterns
  whose left-most column matches the right-most column.
"""

import struct
import sys


PLANE_W = 64
PLANE_H = 32
TOTAL_BYTES = PLANE_W * PLANE_H * 2


def cell(tile, palette=0, hflip=0, vflip=0, priority=0):
    """Pack a Genesis nametable cell word (big-endian 16 bits)."""
    if not (0 <= tile <= 0x7FF):
        raise ValueError(f"tile index {tile} out of range 0..2047")
    if not (0 <= palette <= 3):
        raise ValueError(f"palette line {palette} out of range 0..3")
    return (
        ((priority & 1) << 15)
        | ((palette & 3) << 13)
        | ((vflip & 1) << 12)
        | ((hflip & 1) << 11)
        | (tile & 0x7FF)
    )


def gen_band_stack(bands, out_path):
    """Emit a 64x32 nametable to out_path from a list of band specs.

    Each band dict has:
      rows:  int — number of cell rows this band occupies (must sum to 32)
      cells: list[int] of length 64 OR callable(col, row_in_band) -> word
    """
    total_rows = sum(b["rows"] for b in bands)
    if total_rows != PLANE_H:
        raise ValueError(
            f"bands sum to {total_rows} rows, expected {PLANE_H}"
        )

    out = bytearray()
    for b_idx, band in enumerate(bands):
        cells = band["cells"]
        is_callable = callable(cells)
        if not is_callable and len(cells) != PLANE_W:
            raise ValueError(
                f"band {b_idx}: cells list has {len(cells)} entries, expected {PLANE_W}"
            )
        for r in range(band["rows"]):
            for c in range(PLANE_W):
                w = cells(c, r) if is_callable else cells[c]
                out.extend(struct.pack(">H", w))

    if len(out) != TOTAL_BYTES:
        raise RuntimeError(
            f"emitted {len(out)} bytes, expected {TOTAL_BYTES}"
        )

    with open(out_path, "wb") as f:
        f.write(out)
    print(
        f"gen_multi_band_bg: wrote {out_path}: {len(out)} bytes "
        f"({len(bands)} bands, rows={[b['rows'] for b in bands]})"
    )


# ---------------------------------------------------------------------------
# Self-test / example usage
# ---------------------------------------------------------------------------

def _selftest(out_path):
    """5-band stack matching ParallaxConfig_OJZ_Default's band layout.

    Each band uses one tile index + one palette line — adjust to real tile
    indices from the zone's BG tile pool when authoring.
    """
    bands = [
        {"rows":  4, "cells": [cell(0x001, palette=0)] * PLANE_W},
        {"rows":  6, "cells": [cell(0x002, palette=1)] * PLANE_W},
        {"rows":  4, "cells": [cell(0x003, palette=2)] * PLANE_W},
        {"rows":  6, "cells": [cell(0x004, palette=3)] * PLANE_W},
        {"rows": 12, "cells": [cell(0x005, palette=0)] * PLANE_W},
    ]
    gen_band_stack(bands, out_path)


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "/tmp/test_bg.bin"
    _selftest(out)
