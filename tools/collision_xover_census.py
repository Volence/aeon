#!/usr/bin/env python3
"""Count crossover marks in the shipped per-plane collision attribute data.

WHY THIS EXISTS. `tools/collision_pipeline.py` carried the comment "no crossover;
the value every shipped cell holds" beside XOVER_NONE. It was false: act 1 ships
sixteen marked cells. The comment was source somebody reads while implementing;
the marks are data somebody reads while operating, and the two were never met in
the same sitting. Rather than replace one stale count with a fresher one that
goes stale on the identical clock, the comment now points here.

This is a CENSUS, not a gate. It reports what the data holds and asserts only
that it could read it. The reserved value 3 needs no gate here because
`bake_plane_cell` refuses it at bake time, which is build-fatal.

The field position is read out of collision_pipeline.py rather than repeated, so
this cannot disagree with the encoding it is describing.
"""
from __future__ import annotations

import argparse
import collections
import glob
import json
import os
import re
import struct
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PIPELINE = os.path.join(REPO, "tools", "collision_pipeline.py")
DEFAULT_GLOB = os.path.join(
    REPO, "games", "sonic4", "data", "editor", "*", "*", "section_*.collattr*.bin"
)


def field_encoding(path: str = PIPELINE) -> tuple[int, int, dict[int, str]]:
    """Read XOVER_SHIFT/MASK and the named values out of the pipeline module.

    Derived, never copied: if the encoding moves, this moves with it, and if it
    cannot be found we say so instead of falling back to a plausible guess.
    """
    try:
        src = open(path, encoding="utf-8").read()
    except OSError as exc:
        sys.exit(f"cannot read {path}: {exc}")

    def const(name: str) -> int:
        m = re.search(rf"^{name}\s*=\s*(\d+)", src, re.M)
        if not m:
            sys.exit(
                f"{name} not found in {path} -- the encoding this census describes has "
                f"moved or been renamed. Refusing to guess."
            )
        return int(m.group(1))

    names = {
        const("XOVER_NONE"): "none",
        const("XOVER_TO_A"): "to path A",
        const("XOVER_TO_B"): "to path B",
        const("XOVER_RESERVED"): "RESERVED (illegal)",
    }
    return const("XOVER_SHIFT"), const("XOVER_MASK"), names


def plane_of(path: str) -> str:
    # section_N.collattr.bin is plane A; section_N.collattrb.bin is plane B.
    return "B" if os.path.basename(path).endswith("collattrb.bin") else "A"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--glob", default=DEFAULT_GLOB,
                    help="which attribute blobs to read (default: every shipped act)")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args()

    paths = sorted(glob.glob(args.glob))
    if not paths:
        # An empty result and a broken glob look identical; say which this is.
        sys.exit(f"no files matched {args.glob!r} -- that is a bad pattern or a moved "
                 f"tree, NOT a finding that no collision data ships.")

    shift, mask, names = field_encoding()
    hist: collections.Counter[int] = collections.Counter()
    marks: list[dict] = []
    words = 0

    for path in paths:
        blob = open(path, "rb").read()
        if len(blob) % 2:
            sys.exit(f"{path}: odd byte count {len(blob)}, not a u16 image")
        # Big-endian: these blobs are 68000 words. The little-endian decode of the
        # same bytes yields marks at non-coincident indices, which is how the
        # endianness was controlled rather than assumed.
        cells = struct.unpack(f">{len(blob) // 2}H", blob)
        words += len(cells)
        rel = os.path.relpath(path, REPO)
        for index, cell in enumerate(cells):
            value = (cell >> shift) & mask
            hist[value] += 1
            if value:
                marks.append({"file": rel, "plane": plane_of(path),
                              "index": index, "cell": f"0x{cell:04x}",
                              "xover": value, "meaning": names.get(value, "UNKNOWN")})

    if sum(hist.values()) != words:
        sys.exit("histogram does not sum to the word count -- a mis-parse is hiding in it")

    if args.json:
        json.dump({"files": len(paths), "words": words,
                   "histogram": {str(k): v for k, v in sorted(hist.items())},
                   "marks": marks}, sys.stdout, indent=2)
        print()
        return 0

    print(f"{len(paths)} file(s), {words} cell words")
    for value, count in sorted(hist.items()):
        print(f"  xover {value} ({names.get(value, 'UNKNOWN')}): {count}")
    if not marks:
        print("\nno crossover marks in this corpus")
        return 0
    print(f"\n{len(marks)} marked cell(s):")
    for m in marks:
        print(f"  {m['file']} plane {m['plane']} index {m['index']} "
              f"cell {m['cell']} -> {m['meaning']}")

    # A crossover is two-way by construction; report whether the marks pair up,
    # because an unpaired mark is a data defect this census can see and the bake
    # (which is handed one plane at a time) structurally cannot.
    by_index: dict[int, set[str]] = collections.defaultdict(set)
    for m in marks:
        by_index[m["index"]].add(m["plane"])
    lonely = sorted(i for i, planes in by_index.items() if planes != {"A", "B"})
    print(f"\npaired indices: {len(by_index) - len(lonely)} of {len(by_index)}")
    if lonely:
        print(f"  UNPAIRED (one plane marks, the other does not): {lonely}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
