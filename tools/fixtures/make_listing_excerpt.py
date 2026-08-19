#!/usr/bin/env python3
"""Cut a s4budget test fixture out of a REAL sigil listing.

The whole reason tools/test_s4budget.py's previous 40 tests were green forever
against a parser that read nothing (tools lens sweep D7) is that their fixtures
were hand-authored to match the parser. Fixture and parser were co-designed, so
the suite could only ever confirm the parser's own assumptions.

So the fixtures are CUT, not written. Every line in the output is byte-identical
to a line a real `sigil build --emit-lst` produced — including the original
source-row sequence numbers, which stay non-contiguous exactly because the rows
are a subset. The only synthesized lines are the two trailer counts, which have
to be recomputed for the subset to keep the listing internally consistent.

Regenerate (the .lst is a build artifact and is not tracked):

    ./build.sh                      # produces s4.lst at the repo root
    python3 tools/fixtures/make_listing_excerpt.py s4.lst \
        tools/fixtures/s4_listing_excerpt.lst

Symbols are selected by NAME so the fixture keeps its meaning across rebuilds:
the ROM landmarks the budget axis needs (EndOfRom, the object-bank cursor) and a
spread of RAM buffers across both halves of work RAM.
"""

import re
import sys

# Chosen for coverage, not for size: boot/ROM landmarks, the object-bank budget
# cursor, EndOfRom, every Lower-RAM buffer, and the largest Upper-RAM ones.
WANT = {
    "Vectors", "GameHeader", "Checksum", "EntryPoint", "BootData",
    "Z80_Sound_Start", "Z80_Sound_End", "VDP_Shadow_Init",
    # Each game's own object-bank budget cursor (map.toml [[budget]].cursor):
    # sonic4 declares DeformTable_Zero, demo declares ObjDef_DemoBox. Asking for
    # both means each extraction warns about the other's, which is correct.
    "DeformTable_Zero", "ObjDef_DemoBox", "EndOfRom",
    "Tile_Cache_Nametable", "Tile_Cache_Collision", "Block_Stage_Buffers",
    "Page_Table", "Page_Frames", "Page_Queued_Bits", "Art_Staging_Buffer",
    "Lower_RAM_End",
    "Sprite_Table_Buffer", "Hscroll_Buffer", "Pal_Variant_Stage",
    "Dynamic_Slots", "Effect_Slots", "Plane_Buffer", "Ring_Buffer",
    "Cheat_Flags", "Engine_RAM_End", "Character_ID",
    "Player_Pos_Ring", "Player_Stat_Ring", "Player_Ring_Index", "Game_RAM_End",
}

_SRC = re.compile(r'^\((\d+)\) (\d+)/([0-9A-F]+) :\s+(.+):$')
_SYM = re.compile(r'^\s*(\*?)([\w.$]+) : ([0-9A-F]+) ([C-]) \|$')


def main() -> int:
    if len(sys.argv) != 3:
        print(f"usage: {sys.argv[0]} <real.lst> <out.lst>")
        return 1
    lines = open(sys.argv[1]).read().splitlines()
    hdr = next(i for i, l in enumerate(lines) if l.strip().startswith("Symbol Table"))

    src = [(m.group(4), l) for l in lines[:hdr] if (m := _SRC.match(l))]
    sym = [(m.group(2), l) for l in lines[hdr + 1:] if (m := _SYM.match(l))]
    assert [s[0] for s in src] == [s[0] for s in sym], \
        "the two halves of the real listing already disagree"

    keep = [i for i, (n, _) in enumerate(src) if n in WANT]
    missing = WANT - {src[i][0] for i in keep}
    if missing:
        print(f"WARNING: not in this build: {sorted(missing)}")

    out = [src[i][1] for i in keep]
    out += ["  Symbol Table (* = unused):", "  --------------------------", ""]
    out += [sym[i][1] for i in keep]
    out += ["", f"   {len(keep)} symbols", "    0 unused symbols"]
    with open(sys.argv[2], "w") as f:
        f.write("\n".join(out) + "\n")
    print(f"wrote {sys.argv[2]}: {len(keep)} symbols")
    return 0


if __name__ == "__main__":
    sys.exit(main())
