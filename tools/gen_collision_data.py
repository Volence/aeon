#!/usr/bin/env python3
"""Emit the §4.7 ROM collision tables from the §5 collision attr-set.

Thin CLI wrapper around the attr-set pipeline: loads the sonic_hack
collision sources, walks every OJZ section layout × chunk through
ojz_strip_gen.build_section_collision (the ONE walk implementation, shared
with the strip generator), and writes the four ROM tables.

build.sh runs this BEFORE `ojz_strip_gen.py generate`; the strip generator
then re-emits the tables from its own walk so they always match the strip
collision bytes it wrote. This script's output is the guaranteed baseline —
in particular it provides matching stub tables (type 1 = flat full block,
all-solid) when the sonic_hack sources are missing, which pairs with the
strip generator's priority-bit placeholder bytes (0 = air, 1 = solid).

Usage: python3 tools/gen_collision_data.py [output_dir]
Default output_dir: data/collision
"""

import glob
import os
import sys

# Allow running from the s4_engine root (where build.sh lives).
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import collision_pipeline
import ojz_strip_gen


def stub_tables() -> dict[str, bytes]:
    """Legacy flat-solid stubs: type 0 = air, type 1 = full block."""
    heightmaps = bytearray(256 * 16)
    for i in range(16):
        heightmaps[1 * 16 + i] = 0x10
    solidity = bytearray(256)
    solidity[1] = collision_pipeline.SOL_ALL
    return {
        "heightmaps.bin": bytes(heightmaps),
        # A full 16-high block rotates to itself (all-16 widths)
        "heightmaps_rot.bin": bytes(heightmaps),
        "angles.bin": bytes(256),
        "solidity.bin": bytes(solidity),
    }


def real_tables() -> tuple[dict[str, bytes], int]:
    """Bake every OJZ layout placement into one attr-set; emit the tables."""
    index_a, index_b, profiles, angles = \
        collision_pipeline.load_collision_sources(ojz_strip_gen.SONIC_HACK)
    chunks = ojz_strip_gen.load_chunk_map(ojz_strip_gen.CHUNK_MAP_PATH)

    pattern = os.path.join(ojz_strip_gen.LAYOUT_DIR, "OJZ_1_sec*.bin")
    layout_files = sorted(glob.glob(pattern), key=ojz_strip_gen.extract_sec_id)
    if not layout_files:
        raise FileNotFoundError(f"no OJZ section layouts matching {pattern}")

    attrset = collision_pipeline.AttrSet()
    for path in layout_files:
        layout = ojz_strip_gen.load_layout(path)
        if not layout:
            continue
        # Grids discarded — only the shared attr-set matters here.
        ojz_strip_gen.build_section_collision(
            layout, chunks, index_a, index_b, profiles, angles, attrset
        )
    return collision_pipeline.emit_tables(attrset), len(attrset.entries)


def main():
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "data/collision"
    os.makedirs(out_dir, exist_ok=True)
    try:
        tables, n_entries = real_tables()
        desc = f"attr-set baked, {n_entries} entries"
    except (OSError, ValueError) as exc:
        print("!" * 72)
        print(f"WARNING: sonic_hack collision sources unavailable: {exc}")
        print("WARNING: emitting flat-solid STUB tables (type 1 = full block).")
        print("!" * 72)
        tables = stub_tables()
        desc = "stub fallback"
    for name in sorted(tables):
        with open(os.path.join(out_dir, name), "wb") as f:
            f.write(tables[name])
    print(f"Generated collision tables in {out_dir} ({desc})")


if __name__ == "__main__":
    main()
