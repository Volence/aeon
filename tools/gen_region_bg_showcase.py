#!/usr/bin/env python3
"""gen_region_bg_showcase — lower one editor background LIBRARY entry into the DEBUG-only
region background the region bg switch is tested against.

REGION BG SWITCH, TASK 2 (docs/superpowers/plans/2026-09-16-region-bg-switch.md, call C11).

WHAT IT IS, AND WHAT IT IS NOT. An INSTRUMENT: a second background with visibly different
ART, so a crossing that overwrites the BG tile arena and repaints Plane B can be observed and
gated. It is not content and it is not a look decision; which picture a region shows is the
owner's call. It exists as a DEBUG-shape delta because a regions document cannot name a
per-region background today: `bg.layoutRef` has no lowering (tools/effects_gen.py
`_check_region_bg`) and the contract schema has no tiles key at all (booked
REGION-BG-TILES-AUTHORING).

INPUT (both tracked, both written by Aurora's background library):
  games/sonic4/data/editor/ojz_bg_<id>.bin        64x32 editor layout, ROW-MAJOR BE words,
                                                   tile indices LOCAL to the entry (0-based)
  games/sonic4/data/editor/ojz_bg_<id>_tiles.bin  BE u16 byte length + raw 4bpp tiles, which
                                                   is already the engine's blob shape (BG_Init)

OUTPUT (DEBUG-only embeds in games/sonic4/data/levels/ojz/act1/act_assets.emp):
  zone_bg_showcase_debug.bin     the Plane B blob: 64x64 ROW-MAJOR, 8192 B, indices rebased by
                                 BG_TILE_BASE_SLOT through tools/inject_editor_bg.py's own
                                 rebase_layout (the SAME rule the act default goes through).
                                 A 32-row editor layout is zero-padded to 64 rows, the
                                 injector's legacy convention; word 0 is the transparent tile.
  bg_tiles_showcase_debug.bin    the tile blob, copied after validation.

REFUSED: an id not in ojz_bglib.json; a tile blob whose header disagrees with its body, whose
body is not 32-byte granular, or whose tile count exceeds the static budget
(BG_STATIC_TILE_BUDGET, vram.toml `tiles - band_reserve`); a layout word naming a tile past the
entry's own tile count; a tile blob byte-identical to the act default's (the instrument would
then show nothing).

Usage:  python3 tools/gen_region_bg_showcase.py [--entry ID] [--check]
"""
import argparse
import hashlib
import json
import pathlib
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
ACT_TILES = OUT / "bg_tiles.bin"
DEFAULT_ENTRY = "deep-forest-v15-marching-colonnade-1781232423352"

TILE_BYTES = 32
COLS = 64
ROWS = 64


class Refused(SystemExit):
    pass


def refuse(msg: str):
    raise Refused(f"gen_region_bg_showcase: REFUSED — {msg}")


def build(entry: str = DEFAULT_ENTRY) -> tuple[bytes, bytes, int]:
    """(layout blob, tile blob, tile count) for one library entry. Pure: no writes."""
    ids = [e["id"] for e in json.loads(LIBRARY.read_text())]
    if entry not in ids:
        refuse(f"{entry!r} is not an id in {LIBRARY.relative_to(REPO)} ({len(ids)} entries)")
    layout_src = (EDITOR / f"ojz_bg_{entry}.bin").read_bytes()
    tiles = (EDITOR / f"ojz_bg_{entry}_tiles.bin").read_bytes()

    if len(tiles) < 2:
        refuse(f"the tile blob for {entry!r} is {len(tiles)} B, shorter than its header")
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
        refuse(f"{entry!r} holds {count} tiles and the static BG budget is "
               f"{BG_STATIC_TILE_BUDGET} (vram.toml bg_region tiles - band_reserve)")
    if tiles == ACT_TILES.read_bytes():
        refuse(f"{entry!r}'s tiles are byte-identical to the act default's, so a switch to it "
               "changes nothing on screen and every gate built on it would be vacuous")

    if len(layout_src) % 2:
        refuse(f"the layout is {len(layout_src)} B, not whole words")
    words = list(struct.unpack(f">{len(layout_src) // 2}H", layout_src))
    if len(words) == COLS * 32:
        words += [0] * (COLS * 32)             # the injector's legacy 32-row padding
    if len(words) != COLS * ROWS:
        refuse(f"the layout is {len(words)} words; expected {COLS}x32 or {COLS}x{ROWS}")
    over = [i for i, w in enumerate(words) if w and (w & 0x7FF) >= count]
    if over:
        refuse(f"{len(over)} layout word(s) name a tile past the entry's {count} tiles "
               f"(first at word {over[0]}: ${words[over[0]]:04X})")
    layout = rebase_layout(words)
    assert len(layout) == COLS * ROWS * 2
    return layout, tiles, count


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--entry", default=DEFAULT_ENTRY)
    ap.add_argument("--check", action="store_true",
                    help="verify the committed outputs match; write nothing")
    args = ap.parse_args()
    layout, tiles, count = build(args.entry)
    digest = hashlib.md5(layout + tiles).hexdigest()
    if args.check:
        for path, want in ((LAYOUT_OUT, layout), (TILES_OUT, tiles)):
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
    LAYOUT_OUT.write_bytes(layout)
    TILES_OUT.write_bytes(tiles)
    print(f"gen_region_bg_showcase: wrote {LAYOUT_OUT.name} ({len(layout)} B) + "
          f"{TILES_OUT.name} ({count} tiles) from {args.entry}, md5 {digest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
