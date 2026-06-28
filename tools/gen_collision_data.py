#!/usr/bin/env python3
"""Emit the §4.7 ROM collision tables from the §5 collision attr-set.

Thin CLI wrapper around the attr-set pipeline: loads the sonic_hack
collision sources, walks every OJZ section layout × chunk through
ojz_strip_gen.build_section_collision (the ONE walk implementation, shared
with the strip generator), and writes the four ROM tables. The section list
comes from ojz_strip_gen.enumerate_collision_layouts() — the SAME
enumeration generate() Pass 1b bakes — so a standalone run of this script
always reproduces the tables the strips' collision bytes index into
(verified by ojz_strip_gen's test_collision_emit_identity).

build.sh runs this BEFORE `ojz_strip_gen.py generate`; the strip generator
then re-emits the tables from its own walk so they always match the strip
collision bytes it wrote. This script's output is the guaranteed baseline —
in particular it provides matching stub tables (type 1 = flat full block,
all-solid) when the sonic_hack sources are missing, which pairs with the
strip generator's priority-bit placeholder bytes (0 = air, 1 = solid).

Usage: python3 tools/gen_collision_data.py [output_dir]
Default output_dir: data/collision
"""

import os
import sys

# Allow running from the aeon root (where build.sh lives).
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import collision_pipeline
import ojz_strip_gen


def real_tables() -> tuple[dict[str, bytes], int]:
    """Bake every OJZ layout placement into one attr-set; emit the tables."""
    index_a, index_b, profiles, angles = \
        collision_pipeline.load_collision_sources(ojz_strip_gen.SONIC_HACK)
    chunks = ojz_strip_gen.load_chunk_map(ojz_strip_gen.CHUNK_MAP_PATH)

    layout_pairs = ojz_strip_gen.enumerate_collision_layouts()
    if not layout_pairs:
        raise FileNotFoundError(
            f"no OJZ section layouts found (LAYOUT_DIR={ojz_strip_gen.LAYOUT_DIR})"
        )

    attrset = collision_pipeline.AttrSet()
    for _sec_id, path in layout_pairs:
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
        tables = collision_pipeline.emit_stub_tables()
        desc = "stub fallback"
    for name in sorted(tables):
        with open(os.path.join(out_dir, name), "wb") as f:
            f.write(tables[name])
    print(f"Generated collision tables in {out_dir} ({desc})")


if __name__ == "__main__":
    main()
