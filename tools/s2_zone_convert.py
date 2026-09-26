#!/usr/bin/env python3
"""One whole Sonic 2 zone -> one aeon editor tree. ART, LAYOUT AND COLLISION.

S2-COMPRESSED-ACT staged plan rows 2 (art + layout) and 5 (collision)
(`docs/research/2026-09-17-s2-compressed-act-design.md` §10).

WHAT THIS PRODUCES, and why in this shape
-----------------------------------------
A converted zone lands as a tree aurora and `ojz_strip_gen` can already read,
so nothing downstream needs a new loader:

    games/sonic4/data/donors/<donor>/<ZONE>/
        tileset.bin            the donor's decompressed level art, 32 B/tile,
                               tile 0 at offset 0 (BOTH donors load level art to
                               VRAM tile 0, so a nametable word's index is an
                               index into this blob directly)
        palette.bin            the donor's 96-byte zone palette, VERBATIM
        section_<N>.tiles.bin  256x256 big-endian VDP nametable words
        section_<N>.collattr.bin   256x256 big-endian PLANE-A cell words   [row 5]
        section_<N>.collattrb.bin  256x256 big-endian PLANE-B cell words   [row 5]
        zone.json              the manifest: grid, extents, provenance, counts

`section_<N>` is flat row-major over the section grid, N = sy * grid_w + sx —
the same indexing `games/sonic4/data/editor/ojz/act1/regions.json` shows for the
shipped act (sec0 at x=0, sec1 at x=2048, sec3 at x=0 y=2048 on a 3-wide grid).

THE FILE SET IS TRANSCRIBED FROM THE TREE, NOT FROM THE DESIGN DOC. Two things
the design's §8 sketch gets slightly wrong about aeon's own act tree, worth
knowing before wiring this into a project:

  * there is no `tileset.bin` inside a real act directory. The zone tile blob is
    named by `project.json`'s `zones[].tileset` and today lives OUTSIDE the act
    dir (`games/sonic4/data/editor/ojz_tiles.bin`). `tileset.bin` here is a name
    this converter chooses for a self-contained donor tree; a project that wants
    to point at one points `zones[].tileset` at it.
  * `palette.bin` IS in the act dir, but it is `project.json`'s `zones[].palette`
    that names it, not a convention.

`ojz_strip_gen.validate_editor_inputs(data_path, tileset_path, num_sections)`
takes all three paths explicitly, so a converted tree is validated without
touching `project.json` or the committed OJZ act.

WHAT IS NOT HERE
----------------
No objects, no rings, no `regions.json`, no clip manifest (row 3), no background.

~~No collision.~~ **ROW 5, 2026-09-17.** Both plane files are written, and
`zone.json` now carries the attr-set cost per section that the design's §8 sketch
listed and row 2 could not compute. See rule 6.

THE RULES THIS CONVERTER DECIDES
--------------------------------
1. EXTENT. The converted grid is anchored at donor world tile (0, 0) and covers
   ceil(crop_x1 / 256) x ceil(crop_y1 / 256) sections, where (crop_x1, crop_y1)
   is the upper bound of `s2_donor.load_zone`'s camera-box crop. A zone whose
   size does not divide evenly into 2048-px sections is PADDED with zero words,
   never cropped and never refused. Padding is the only lossless choice: cropping
   would silently drop camera-reachable cells, and refusing would make 8 of the 19
   zone/donor pairs unconvertible (measured — not one zone's crop is a multiple of
   256 tiles on its long axis).
   Cells inside the grid but outside the crop rectangle are zero. That includes
   the rows ABOVE the crop for the four zones whose `LevelSize` ystart is not 0
   (ARZ y0=64, MCZ/DHZ y0=120, NGHZ y0=64 in tiles): anchoring at world (0, 0)
   rather than at the crop origin costs those zones nothing (every crop ends at
   or before tile row 256, so the grid is one section tall either way) and means
   a donor world pixel and a converted tree pixel are THE SAME NUMBER. Row 3's
   `clips.json` names `src_rect` in donor coordinates; an origin shift here would
   put a silent offset under every clip.
   The camera box is used even for the five zones whose `LevelSize` xend is the
   `$3FFF` placeholder (WFZ final; CNZ/HPZ/MTZ/WZ prototype). Those convert to a
   full 8-section-wide grid of mostly-blank cells. That is deliberate: it is the
   lossless choice, and the prototype-formats report's rule ("do not clip a
   placeholder-box zone from its camera box") is a rule about CLIPPING, which is
   row 3's job. `zone.json` carries `painted_bbox` so row 3 can obey it.

2. PALETTE. The donor's 96 bytes are copied VERBATIM, and the converter DERIVES
   from the donor's own palette-pointer table that those 96 bytes are three
   consecutive CRAM lines starting at line 1 — which is exactly the three lines
   aeon writes (line 0 is the character's and the engine never writes it). Any
   zone whose palette does not land at line 1, or is not 96 bytes, is REFUSED by
   name rather than copied and hoped for.

3. CRAM LINE 0 CELLS. Some zones paint a few cells on palette line 0, which aeon
   never writes, so they would render in the character's colours: measured here,
   CPZ 698 cells (0.62%) in the final donor and 680 (0.61%) in the prototype, WFZ
   104 (0.10%); every other zone/donor pair is zero. The converter does NOT
   rewrite them. It counts them, per zone and per section, into `zone.json` and
   prints a warning.
   WHY NOT REWRITE: rewriting a nametable word's palette bits is precisely the
   thing `tools/verify_level_bin.py`'s bake-fidelity lane asserts the bake never
   does, and it would break this parcel's own identity bar. It is also not this
   parcel's decision to take — the design's §9.1 prices three whole-act answers
   to the palette problem and the owner has not ruled. Faithful conversion plus a
   counted, surfaced defect leaves every one of those answers open; a quiet remap
   closes them.

4. TILE INDICES ARE NOT REMAPPED. A converted word's 11-bit index means the same
   tile in `tileset.bin` that it meant in the donor. Dedupe, page election and the
   per-cell tileset key all happen later in the real bake; doing any of it here
   would make the round trip non-identity for no gain.

5. COLLISION IS THE INTERMEDIATE WORD, NOT THE BAKED BYTE (row 5). A converted
   tree carries `section_N.collattr.bin` / `.collattrb.bin` in AURORA's per-plane
   cell-word format — the format `collision_pipeline.bake_plane_cell` consumes and
   `ojz_strip_gen.apply_editor_collision_overlay` reads — never the attr-set byte
   the ROM holds. Two reasons, and the first is the load-bearing one:
     * an attr byte is an index into an act-wide 255-entry set. A DONOR ZONE IS
       NOT AN ACT. Baking here would mint a per-zone set that the clip act then
       has to re-intern anyway, and the number that actually decides the act
       (§3.5's 255 cap) is a property of the CLIPS, not of any one zone.
     * the cell word is what an author edits. A converted tree opened in aurora is
       paintable, marqueeable and re-bakeable exactly like an authored act; a tree
       of baked bytes is a read-only artifact.
   The transcode is `collision_pipeline.chunk_entry_to_plane_words`, and it is
   exactly equivalent to `bake_cell` (asserted over every distinct chunk-entry word
   of the six showcase zones by `tools/test_s2_clip_collision.py`).

6. THE SHAPE INDEX NAMES THE S2 BANK, AND THE TREE SAYS SO. A plane word's low 10
   bits index a base collision bank, and a converted S2 tree's indices are S2's own
   — `games/sonic4/data/collision/base_s2/` (row 4,
   `tools/import_s2_collision.py`), NOT the S&K bank under `base/` that the shipped
   OJZ act uses. The same integer means a different shape in the two banks, so
   `zone.json` names the bank and pins its `heightmaps.bin` sha256. Anything that
   bakes one of these trees must select that bank; `ojz_strip_gen.load_base_bank`
   takes the directory for exactly this reason.
   BOTH DONORS SHARE ONE BANK, which is a measured fact and not an assumption:
   the prototype's `Collision array 1.bin` is byte-identical to the final game's
   `- Vertical.bin` (parcel 4, pinned by `tools/test_s2_donor.py::
   test_the_two_donors_share_one_collision_shape_vocabulary`).

7. COLLISION IS CROP-MASKED EXACTLY LIKE ART. A cell outside the camera-box crop
   holds word 0 on both planes — air — for the same reason its nametable word is
   0. Anything else would put invisible solid ground under a blank region, and the
   converter's own pad check (verify_tree B) would stop meaning anything.
   WHAT THIS COSTS, MEASURED rather than assumed, because the obvious worry is that
   it makes the design's §3.5 numbers unreachable: NOTHING at whole-zone scope. Two
   of the six zones have layout grids that reach below their crop — EHZ's
   below-crop chunks are all chunk 0 (air), OOZ's are real chunks (180-186 among
   them) — and the cropped and uncropped attr-set counts are IDENTICAL for both
   (EHZ 105/105, OOZ 67/67): the below-crop chunks reuse shapes the crop already
   needs. All six zones match `s2_clip_budget.py collision <ZONE>` exactly.
   It can still differ for a CLIP, because that tool's `ZONE:s0,n` spec has no
   vertical extent at all — it counts every chunk the COLUMN range references, over
   every row — so a narrow clip of a zone whose only use of some shape is below the
   crop would be predicted high. `tools/clip_act_bake.py` reports the clip's real
   number off the emitted bytes and cross-checks it against that prediction.

USAGE
-----
    python3 tools/s2_zone_convert.py convert s2disasm@EHZ
    python3 tools/s2_zone_convert.py convert s2-simonwai-disasm@HPZ --out /tmp/x
    python3 tools/s2_zone_convert.py convert --all-six
    python3 tools/s2_zone_convert.py verify games/sonic4/data/donors/s2disasm/EHZ

`convert` always verifies what it wrote; there is no --no-verify, because a skip
flag is how a converter ends up green over a tree nothing checked.
"""

import argparse
import hashlib
import json
import os
import re
import struct
import sys

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))

import s2_donor                                    # noqa: E402
import ojz_strip_gen                                # noqa: E402
import collision_pipeline                           # noqa: E402
import import_s2_collision                          # noqa: E402

# ---------------------------------------------------------------------------
# Geometry — every number READ from the module that owns it, never restated.
# ---------------------------------------------------------------------------
#: Nametable rows/columns per section. ojz_strip_gen owns it (256 -> 2048 px).
SECTION_TILES = ojz_strip_gen.STRIP_TILE_HEIGHT
#: Bytes in one section_N.tiles.bin. The same constant validate_editor_inputs
#: checks against, imported rather than recomputed.
SECTION_FILE_BYTES = ojz_strip_gen.EDITOR_CELL_FILE_BYTES
#: 16x16 tiles per 128-px chunk.
TILES_PER_CHUNK = ojz_strip_gen.TILES_PER_CHUNK_ROW
#: 8x8 16-px blocks per 128-px chunk — the chunk-entry grid both games store.
BLOCKS_PER_CHUNK = ojz_strip_gen.BLOCKS_PER_CHUNK_ROW
#: 11-bit tile index field of a VDP nametable word.
TILE_INDEX_MASK = ojz_strip_gen.TILE_INDEX_MASK
#: Bytes of art per tile.
TILE_BYTES = ojz_strip_gen.tile_dedupe.TILE_SIZE

#: Genesis CRAM line size in bytes (16 colours x 2). Hardware, not a donor fact.
PALETTE_LINE_BYTES = 32
#: A zone palette is three lines: CRAM 1, 2, 3. Aeon writes exactly those.
ZONE_PALETTE_BYTES = 3 * PALETTE_LINE_BYTES
#: The CRAM line a zone palette must start at for aeon to be able to install it.
ZONE_PALETTE_FIRST_LINE = 1

DEFAULT_OUT_ROOT = os.path.join(REPO, "games", "sonic4", "data", "donors")

#: The owner's six showcase zones (design §4 / the prototype-formats report §4).
THE_SIX = [
    (s2_donor.S2_FINAL, "EHZ"),
    (s2_donor.S2_FINAL, "CPZ"),
    (s2_donor.S2_PROTOTYPE, "HPZ"),
    (s2_donor.S2_FINAL, "WFZ"),
    (s2_donor.S2_FINAL, "OOZ"),
    (s2_donor.S2_FINAL, "MTZ"),
]


# ---------------------------------------------------------------------------
# Palette: derive the CRAM line from the donor, do not assume it
# ---------------------------------------------------------------------------

def palette_cram_line(zone: str, donor: str) -> tuple[int, int]:
    """(first CRAM line, payload bytes) for this zone's palette, READ from the donor.

    FINAL: `PalPtr_EHZ: palptr Pal_EHZ, 1`, and the macro two dozen lines above it
    is `dc.w (Normal_palette+lineno*palette_line_size)&$FFFF` — so the macro's
    second argument IS the CRAM line, and `dc.w bytesToLcnt(ptr_End-ptr)` makes
    the payload the palette file's own length. Only the line has to be parsed.

    PROTOTYPE: the table is open-coded, `dc.l Pal_HPZ` / `dc.w $FB20,$17` — a RAM
    destination and a `dbf` count of LONGS MINUS ONE. The RAM base is not a
    constant this file can resolve (`Normal_palette` is a `ds.b` inside a struct
    in constants.asm), so the line is derived from the TABLE instead: the entry
    with a four-line (128-byte) payload can only be a whole-CRAM load, so its
    destination pins line 0, and every other entry's line is the offset from it.
    A four-line entry with any other destination would break the derivation
    LOUDLY rather than shift every zone's palette by a line.
    """
    name = s2_donor.zone_row(zone, donor)["palette"]
    text = s2_donor._main_asm(donor)
    size = os.path.getsize(s2_donor.palette_path(zone, donor))

    if donor == s2_donor.S2_FINAL:
        lines = set(re.findall(
            rf"^\S*:?\s*palptr\s+Pal_{re.escape(name)}\s*,\s*(\d+)\s*$", text, re.M))
        if not lines:
            raise SystemExit(
                f"{donor}/{zone}: s2.asm has no `palptr Pal_{name}, <line>` row — the "
                f"palette-pointer table moved. Re-derive the CRAM line rather than "
                f"assuming line 1.")
        if len(lines) != 1:
            raise SystemExit(
                f"{donor}/{zone}: Pal_{name} is loaded to more than one CRAM line "
                f"{sorted(lines)} — which one a converted zone means is not this "
                f"converter's call.")
        return int(lines.pop()), size

    rows = [(int(d, 16), int(c, 16)) for d, c in re.findall(
        r"dc\.l\s+Pal_\w+[^\n]*\n\s*dc\.w\s+\$([0-9A-Fa-f]+)\s*,\s*\$?([0-9A-Fa-f]+)",
        text)]
    if not rows:
        raise SystemExit(f"{donor}: PalPointers is no longer `dc.l Pal_x` / `dc.w dest,count`")
    four_line = {d for d, c in rows if (c + 1) * 4 == 4 * PALETTE_LINE_BYTES}
    if len(four_line) != 1:
        raise SystemExit(
            f"{donor}: expected exactly one whole-CRAM (4-line) palette destination to "
            f"pin CRAM line 0; found {sorted(hex(d) for d in four_line)}. The prototype's "
            f"palette-line derivation rests on that row — re-derive it.")
    base = four_line.pop()

    mine = {(d, c) for d, c in re.findall(
        rf"dc\.l\s+Pal_{re.escape(name)}\b[^\n]*\n\s*dc\.w\s+\$([0-9A-Fa-f]+)\s*,\s*\$?([0-9A-Fa-f]+)",
        text)}
    dests = {int(d, 16) for d, _ in mine}
    if not dests:
        raise SystemExit(f"{donor}/{zone}: PalPointers has no row for Pal_{name}")
    if len(dests) != 1:
        raise SystemExit(
            f"{donor}/{zone}: Pal_{name} is loaded to more than one destination "
            f"{sorted(hex(d) for d in dests)}")
    dest = dests.pop()
    if (dest - base) % PALETTE_LINE_BYTES:
        raise SystemExit(
            f"{donor}/{zone}: Pal_{name} loads to ${dest:X}, which is not a whole CRAM "
            f"line from the line-0 base ${base:X}")
    return (dest - base) // PALETTE_LINE_BYTES, size


def check_palette(zone: str, donor: str) -> dict:
    """Refuse a zone whose palette is not aeon's three writable CRAM lines."""
    line, size = palette_cram_line(zone, donor)
    if line != ZONE_PALETTE_FIRST_LINE or size != ZONE_PALETTE_BYTES:
        raise SystemExit(
            f"{donor}/{zone}: palette is {size} bytes starting at CRAM line {line}; aeon "
            f"installs a zone palette as {ZONE_PALETTE_BYTES} bytes over lines "
            f"{ZONE_PALETTE_FIRST_LINE}..{ZONE_PALETTE_FIRST_LINE + 2} (line 0 is the "
            f"character's and the engine never writes it, engine/effects/palette.emp). "
            f"Converting this zone needs a ruling, not a copy.")
    return {"cram_first_line": line, "bytes": size,
            "cram_lines": [line, line + 1, line + 2]}


# ---------------------------------------------------------------------------
# The independent chunk-word re-derivation (the round trip's other side)
# ---------------------------------------------------------------------------

def expand_chunk_words(chunks: list[list[int]], blocks: list[list[int]]) -> np.ndarray:
    """(n_chunks, 16, 16) nametable words — a SECOND implementation, on purpose.

    `s2_donor.load_zone` builds its grid through `ojz_strip_gen.chunk_get_tile_word`.
    Checking the converted tree against that same function would only prove the
    converter copied an array. This re-derives the same words straight from the
    two file formats:

      chunk entry word : bits 9:0 block id, 10 X-flip, 11 Y-flip
                         (bits 15:12 are the path-A/path-B solidity nibbles,
                         which are collision and belong to staged-plan row 5)
      block            : 4 nametable words, [top-left, top-right, bottom-left,
                         bottom-right]
      a chunk-level flip both SWAPS the sub-tile within the block and TOGGLES
      that tile word's own H/V bit.

    Vectorised because it runs over every cell of every converted zone.
    """
    n = len(chunks)
    entries = np.zeros((n, 8, 8), dtype=np.uint16)
    for i, ch in enumerate(chunks):
        entries[i] = np.asarray(ch[:64], dtype=np.uint16).reshape(8, 8)

    block_words = np.zeros((len(blocks) + 1, 4), dtype=np.uint16)
    if blocks:
        block_words[:len(blocks)] = np.asarray(blocks, dtype=np.uint16)
    OOR = len(blocks)                       # out-of-range block id -> word 0
    block_words[OOR] = 0

    bid = (entries & 0x03FF).astype(np.int64)
    xf = (entries & 0x0400) != 0
    yf = (entries & 0x0800) != 0
    bid = np.where(bid >= len(blocks), OOR, bid)

    out = np.zeros((n, TILES_PER_CHUNK, TILES_PER_CHUNK), dtype=np.uint16)
    H_BIT = ojz_strip_gen.tile_dedupe.NAMETABLE_H_BIT
    V_BIT = ojz_strip_gen.tile_dedupe.NAMETABLE_V_BIT
    for tr in range(TILES_PER_CHUNK):
        for tc in range(TILES_PER_CHUNK):
            e_bid = bid[:, tr // 2, tc // 2]
            e_xf = xf[:, tr // 2, tc // 2]
            e_yf = yf[:, tr // 2, tc // 2]
            sub_col = np.where(e_xf, (tc & 1) ^ 1, tc & 1)
            sub_row = np.where(e_yf, (tr & 1) ^ 1, tr & 1)
            w = block_words[e_bid, sub_row * 2 + sub_col]
            w = np.where(e_bid == OOR, np.uint16(0), w)
            w = np.where(e_xf & (e_bid != OOR), w ^ np.uint16(H_BIT), w)
            w = np.where(e_yf & (e_bid != OOR), w ^ np.uint16(V_BIT), w)
            out[:, tr, tc] = w
    return out


def expand_collision_words(chunks: list[list[int]], index_a: bytes,
                           index_b: bytes) -> tuple[np.ndarray, np.ndarray]:
    """(n_chunks, 16, 16) plane-A and plane-B cell words — rule 5's transcode.

    Vectorised twin of `collision_pipeline.chunk_entry_to_plane_words`, which is
    the scalar DEFINITION. This runs over every chunk of every zone, so it is a
    numpy expression; `tools/test_s2_clip_collision.py` asserts the two agree cell
    for cell rather than trusting that they were written from the same paragraph.

    An entry covers a 16x16-px block = 2x2 nametable cells, and BOTH cells of a
    block carry the block's word: aeon's collision cell is 8 px wide
    (`COLL_CELL_W`) against Sonic 2's 16, so the X resolution doubles and the pair
    shares one shape. In Y the editor file's odd rows are never read (a 16-px
    collision row samples the even tile row,
    `ojz_strip_gen.apply_editor_collision_overlay`); they are filled anyway so the
    file is WYSIWYG in an editor that draws every cell.
    """
    n = len(chunks)
    entries = np.zeros((n, BLOCKS_PER_CHUNK, BLOCKS_PER_CHUNK), dtype=np.uint16)
    for i, ch in enumerate(chunks):
        entries[i] = np.asarray(ch[:BLOCKS_PER_CHUNK * BLOCKS_PER_CHUNK],
                                dtype=np.uint16).reshape(BLOCKS_PER_CHUNK, BLOCKS_PER_CHUNK)

    cp = collision_pipeline
    bid = (entries & cp.BLOCK_ID_MASK).astype(np.int64)
    flips = entries & np.uint16(cp.CHUNK_XFLIP_BIT | cp.CHUNK_YFLIP_BIT)

    out = []
    for shift, index in ((cp.PATH_A_SOL_SHIFT, index_a),
                         (cp.PATH_B_SOL_SHIFT, index_b)):
        # a block id past the index reads as shape 0 = air, matching bake_cell
        table = np.zeros(max(len(index), int(cp.BLOCK_ID_MASK) + 1), dtype=np.uint16)
        table[:len(index)] = np.frombuffer(index, dtype=np.uint8)
        shape = table[bid]
        solidity = (entries >> shift) & np.uint16(3)
        word = shape | flips | (solidity << np.uint16(cp.PLANE_SOL_SHIFT))
        # one entry -> the block's 2x2 nametable cells
        out.append(np.repeat(np.repeat(word, 2, axis=1), 2, axis=2))
    return out[0], out[1]


def rederive_zone_collision(zone: str, donor: str) -> tuple[np.ndarray, np.ndarray]:
    """The zone's FULL (uncropped) per-plane cell-word grids, via the chunk grid."""
    chunks, grid, index_a, index_b = s2_donor.collision_inputs(zone, donor)
    grid = grid.astype(np.int64)
    planes = expand_collision_words(chunks, index_a, index_b)
    # A layout byte naming a chunk the zone does not define reads as AIR, which is
    # `s2_clip_budget.collision_entries`'s `if ci < len(chunks)` guard and
    # `ojz_strip_gen.build_collision_grids`'s "out-of-range chunk -> air". Not
    # hypothetical: OOZ's below-crop rows name chunks past its own table.
    oor = len(chunks)
    grid = np.where(grid >= oor, oor, grid)
    out = []
    for per_chunk in planes:
        per_chunk = np.concatenate(
            [per_chunk, np.zeros((1,) + per_chunk.shape[1:], dtype=per_chunk.dtype)])
        full = per_chunk[grid]                                # (rows, cols, 16, 16)
        out.append(full.transpose(0, 2, 1, 3).reshape(
            grid.shape[0] * TILES_PER_CHUNK, grid.shape[1] * TILES_PER_CHUNK))
    return out[0], out[1]


def rederive_zone_words(zone: str, donor: str) -> np.ndarray:
    """The zone's FULL (uncropped) word grid, via `expand_chunk_words`.

    Uses the donor loader only for the three FILE readers (chunks, blocks,
    layout). The word arithmetic is this module's own.
    """
    chunks = s2_donor.load_chunks(zone, donor)
    blocks = s2_donor.load_blocks(zone, donor)
    grid = s2_donor.load_fg_grid(zone, donor).astype(np.int64)
    per_chunk = expand_chunk_words(chunks, blocks)
    full = per_chunk[grid]                                    # (rows, cols, 16, 16)
    return full.transpose(0, 2, 1, 3).reshape(
        grid.shape[0] * TILES_PER_CHUNK, grid.shape[1] * TILES_PER_CHUNK)


# ---------------------------------------------------------------------------
# Conversion
# ---------------------------------------------------------------------------

def section_grid(crop_x1: int, crop_y1: int) -> tuple[int, int]:
    """(grid_w, grid_h) in sections covering donor world tiles [0, crop) — rule 1."""
    gw = max(1, -(-crop_x1 // SECTION_TILES))
    gh = max(1, -(-crop_y1 // SECTION_TILES))
    return gw, gh


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def convert_zone(zone: str, donor: str, out_dir: str, quiet: bool = False) -> dict:
    """Write one zone's editor tree. Returns the manifest it wrote."""
    z = s2_donor.load_zone(zone, donor)
    x0, x1, y0, y1 = z.box["crop_tiles"]
    if x0 != 0:
        raise SystemExit(
            f"{donor}/{zone}: the camera-box crop starts at tile column {x0}, not 0. "
            f"Rule 1 anchors the converted grid at donor world (0, 0) so donor and tree "
            f"coordinates are the same number; a non-zero x0 would silently break that. "
            f"No zone in either donor does this today — re-derive the rule before "
            f"converting this one.")

    art = z.art
    if not art or len(art) % TILE_BYTES:
        raise SystemExit(
            f"{donor}/{zone}: the art blob is {len(art)} bytes — not a non-empty whole "
            f"number of {TILE_BYTES}-byte tiles. `validate_editor_inputs` refuses that, "
            f"and a partial trailing tile is not addressable by any nametable word.")
    n_tiles = len(art) // TILE_BYTES

    pal_info = check_palette(zone, donor)
    pal = s2_donor.read_bytes(s2_donor.palette_path(zone, donor))

    gw, gh = section_grid(x1, y1)
    words = z.words                                  # (crop_h, crop_w)
    os.makedirs(out_dir, exist_ok=True)

    idx_all = words & TILE_INDEX_MASK
    painted = idx_all != 0
    pal_line = (words >> 13) & 3
    line0 = painted & (pal_line == 0)

    # Rule 5: both collision planes, in aurora's per-plane cell-word format.
    # Uncropped and in DONOR WORLD coordinates, like the words above, so the same
    # (sx0..sx1, sy0..sy1) crop window slices all three.
    coll_full = rederive_zone_collision(zone, donor)
    bank_dir = import_s2_collision.default_out()
    bank_profiles, bank_angles = ojz_strip_gen.load_base_bank(bank_dir)
    # UNCAPPED on purpose (rule 5): a donor zone is not an act, so the 255 cap is
    # not its refusal to make. The number is reported; the clip act enforces it.
    zone_attrs = collision_pipeline.AttrSet(cap=None)

    sections = []
    for sy in range(gh):
        for sx in range(gw):
            n = sy * gw + sx
            buf = np.zeros((SECTION_TILES, SECTION_TILES), dtype=">u2")
            coll = [np.zeros((SECTION_TILES, SECTION_TILES), dtype=">u2")
                    for _ in range(2)]
            wx0, wy0 = sx * SECTION_TILES, sy * SECTION_TILES
            # The crop occupies donor world rows y0..y1, columns 0..x1.
            sx0, sx1 = max(wx0, 0), min(wx0 + SECTION_TILES, x1)
            sy0, sy1 = max(wy0, y0), min(wy0 + SECTION_TILES, y1)
            n_cells = 0
            if sx1 > sx0 and sy1 > sy0:
                buf[sy0 - wy0:sy1 - wy0, sx0 - wx0:sx1 - wx0] = \
                    words[sy0 - y0:sy1 - y0, sx0:sx1]
                n_cells = (sx1 - sx0) * (sy1 - sy0)
                for p in range(2):
                    # rule 7: the SAME crop window as the art, in donor world
                    # coordinates (coll_full is uncropped, words is not)
                    coll[p][sy0 - wy0:sy1 - wy0, sx0 - wx0:sx1 - wx0] = \
                        coll_full[p][sy0:sy1, sx0:sx1]
            path = os.path.join(out_dir, f"section_{n}.tiles.bin")
            data = buf.tobytes()
            assert len(data) == SECTION_FILE_BYTES, len(data)
            with open(path, "wb") as fh:
                fh.write(data)
            coll_meta = {}
            for p, suffix in enumerate(("collattr", "collattrb")):
                cdata = coll[p].tobytes()
                assert len(cdata) == SECTION_FILE_BYTES, len(cdata)
                with open(os.path.join(out_dir, f"section_{n}.{suffix}.bin"), "wb") as fh:
                    fh.write(cdata)
                coll_meta[f"{suffix}_sha256"] = _sha256(cdata)
            coll_meta["collision_cells_solid"] = int(sum(
                np.count_nonzero((np.asarray(coll[p], dtype=np.uint16)
                                  >> collision_pipeline.PLANE_SOL_SHIFT) & 3)
                for p in range(2)))
            before = len(zone_attrs.entries)
            for p in range(2):
                for w in np.unique(np.asarray(coll[p], dtype=np.uint16)).tolist():
                    collision_pipeline.bake_plane_cell(
                        int(w), bank_profiles, bank_angles, zone_attrs)
            coll_meta["attr_entries_added"] = len(zone_attrs.entries) - before
            sec_idx = np.asarray(buf, dtype=np.uint16) & TILE_INDEX_MASK
            sec_painted = sec_idx != 0
            sec_line0 = sec_painted & (((np.asarray(buf, dtype=np.uint16) >> 13) & 3) == 0)
            sections.append({
                "n": n, "sx": sx, "sy": sy,
                "world_rect_px": [wx0 * 8, wy0 * 8, SECTION_TILES * 8, SECTION_TILES * 8],
                "donor_cells": int(n_cells),
                "painted_cells": int(sec_painted.sum()),
                "cram_line0_cells": int(sec_line0.sum()),
                "distinct_tiles": int(np.unique(sec_idx[sec_painted]).size)
                                  if sec_painted.any() else 0,
                "sha256": _sha256(data),
                **coll_meta,
            })

    with open(os.path.join(out_dir, "tileset.bin"), "wb") as fh:
        fh.write(art)
    with open(os.path.join(out_dir, "palette.bin"), "wb") as fh:
        fh.write(pal)

    manifest = {
        "schema": 1,
        "produced_by": "tools/s2_zone_convert.py",
        "content": "foreground art + layout + both collision planes (no objects, "
                   "rings, regions, background — staged plan rows 2 and 5)",
        "zone": zone,
        "donor": donor,
        "donor_env_var": s2_donor.donor_env_var(donor),
        "donor_role": s2_donor.donor_role(donor),
        "game": z.box.get("game"),
        "layout": z.box.get("layout"),
        "grid": {"w": gw, "h": gh, "sections": gw * gh,
                 "section_px": SECTION_TILES * 8,
                 "index": "flat row-major, N = sy * grid_w + sx"},
        "extent": {
            "anchored_at": "donor world tile (0, 0)",
            "camera_box_px": z.box["level_size_px"],
            "camera_box_is_placeholder": bool(z.box.get("camera_box_is_placeholder", False)),
            "crop_tiles": [int(v) for v in z.box["crop_tiles"]],
            "ystart_clamped": bool(z.box.get("ystart_clamped", False)),
            "painted_bbox_tiles": ([int(v) for v in s2_donor.painted_bbox(z)]
                                   if s2_donor.painted_bbox(z) else None),
            "pad_rule": "zero words; the grid is padded up to whole sections and "
                        "NEVER cropped",
        },
        "tileset": {"file": "tileset.bin", "bytes": len(art), "tiles": n_tiles,
                    "tile_bytes": TILE_BYTES, "vram_base_tile": 0,
                    "sha256": _sha256(art),
                    "sources": [[os.path.relpath(p, s2_donor.donor_root(donor)), off]
                                for p, off in s2_donor.art_sources(zone, donor)]},
        "palette": dict(pal_info, file="palette.bin", sha256=_sha256(pal),
                        source=os.path.relpath(s2_donor.palette_path(zone, donor),
                                               s2_donor.donor_root(donor))),
        "collision": {
            "files": ["section_N.collattr.bin (plane A)",
                      "section_N.collattrb.bin (plane B)"],
            "format": "aurora per-plane cell word, big-endian u16: 9:0 base-bank "
                      "shape, 10 X-flip, 11 Y-flip, 13:12 this plane's solidity, "
                      "15:14 reserved, always 0 (the donor's bits 15:14 are path-B "
                      "solidity, which is plane B's own word). See "
                      "collision_pipeline.chunk_entry_to_plane_words.",
            "cell_px": [8, 16],
            "cell_px_note": "the file is one word per 8-px NAMETABLE cell so it "
                            "overlays the tiles grid exactly; a 16-px collision "
                            "row samples the EVEN tile row "
                            "(ojz_strip_gen.apply_editor_collision_overlay), and "
                            "both 8-px columns of a donor 16-px block carry that "
                            "block's word",
            "base_bank": os.path.relpath(bank_dir, REPO),
            "base_bank_heightmaps_sha256": _sha256(bank_profiles),
            "base_bank_angles_sha256": _sha256(bank_angles),
            "base_bank_note": "a shape index means a DIFFERENT shape in the S&K "
                              "bank under data/collision/base/; anything that "
                              "bakes this tree must select this one "
                              "(ojz_strip_gen.load_base_bank takes the directory)",
            "index_primary": s2_donor.zone_row(zone, donor)["coll_p"],
            "index_secondary": s2_donor.zone_row(zone, donor)["coll_s"],
            "index_note": "the donor's own per-zone block-id -> shape-index tables "
                          "(Off_ColP / Off_ColS). A zone with no second path names "
                          "no secondary and both planes share the primary.",
            "attr_entries": len(zone_attrs.entries) - 1,
            "attr_entries_note": "distinct (heights, angle, solidity) this "
                                 "WHOLE zone needs, against the act-wide cap of "
                                 f"{collision_pipeline.AttrSet.CAP} "
                                 "(collision_pipeline.AttrSet.CAP). A donor zone "
                                 "is not an act: a clip needs a subset, and an act "
                                 "needs the union of its clips'. Counted with the "
                                 "cap lifted so the REQUIRED size is reported.",
            "distinct_shapes": sorted({int(w) & collision_pipeline.BLOCK_ID_MASK
                                       for p in coll_full
                                       for w in np.unique(p).tolist()
                                       if (int(w) >> collision_pipeline.PLANE_SOL_SHIFT) & 3}),
        },
        "counts": {
            "crop_cells": int(words.size),
            "painted_cells": int(painted.sum()),
            "distinct_tiles_referenced": int(np.unique(idx_all[painted]).size),
            "max_tile_index": int(idx_all.max()),
            "cram_line0_painted_cells": int(line0.sum()),
            "cram_line0_note": ("these cells name CRAM line 0, which aeon never writes "
                                "(engine/effects/palette.emp). Converted faithfully and "
                                "counted; NOT remapped — see rule 3 in "
                                "tools/s2_zone_convert.py"),
        },
        "sections": sections,
    }
    with open(os.path.join(out_dir, "zone.json"), "w") as fh:
        json.dump(manifest, fh, indent=2, sort_keys=True)
        fh.write("\n")

    if not quiet:
        print(f"  {donor}@{zone}: {gw}x{gh} = {gw * gh} sections, "
              f"{n_tiles} tiles, {manifest['counts']['painted_cells']} painted cells "
              f"-> {os.path.relpath(out_dir, REPO)}")
        if manifest["counts"]["cram_line0_painted_cells"]:
            print(f"    WARNING: {manifest['counts']['cram_line0_painted_cells']} painted "
                  f"cells name CRAM line 0, which aeon never writes — they will render in "
                  f"the character's colours. Counted, not remapped (rule 3).")
    return manifest


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------

def reference_collision_cell(zone: str, donor: str, row: int, col: int) -> tuple[int, int]:
    """(plane A word, plane B word) for ONE donor world tile cell — scalar, slow.

    The SECOND implementation of rule 5, written from the geometry rather than
    from `expand_collision_words`'s numpy: resolve the cell's chunk, then its block
    inside that chunk, then hand the chunk-entry word to the scalar definition in
    `collision_pipeline`. `verify_tree` E samples this against the vectorised grid
    on disk, so a transposition or an off-by-one in the repeat/reshape chain has
    something to disagree with.
    """
    chunks, grid, index_a, index_b = s2_donor.collision_inputs(zone, donor)
    chunk_row, chunk_col = row // TILES_PER_CHUNK, col // TILES_PER_CHUNK
    if chunk_row >= grid.shape[0] or chunk_col >= grid.shape[1]:
        return (0, 0)
    chunk_id = int(grid[chunk_row, chunk_col])
    if chunk_id >= len(chunks):
        return (0, 0)
    block_row = (row % TILES_PER_CHUNK) // 2
    block_col = (col % TILES_PER_CHUNK) // 2
    word = chunks[chunk_id][block_row * BLOCKS_PER_CHUNK + block_col]
    return collision_pipeline.chunk_entry_to_plane_words(word, index_a, index_b)


def read_tree_planes(out_dir: str, manifest: dict) -> tuple[np.ndarray, np.ndarray]:
    """Both collision planes reassembled from disk, same shape as read_tree_words."""
    gw, gh = manifest["grid"]["w"], manifest["grid"]["h"]
    out = []
    for suffix in ("collattr", "collattrb"):
        buf = np.zeros((gh * SECTION_TILES, gw * SECTION_TILES), dtype=np.uint16)
        for sy in range(gh):
            for sx in range(gw):
                n = sy * gw + sx
                p = os.path.join(out_dir, f"section_{n}.{suffix}.bin")
                with open(p, "rb") as fh:
                    data = fh.read()
                if len(data) != SECTION_FILE_BYTES:
                    raise SystemExit(f"{p}: {len(data)} bytes, expected {SECTION_FILE_BYTES}")
                buf[sy * SECTION_TILES:(sy + 1) * SECTION_TILES,
                    sx * SECTION_TILES:(sx + 1) * SECTION_TILES] = \
                    np.frombuffer(data, dtype=">u2").reshape(SECTION_TILES, SECTION_TILES)
        out.append(buf)
    return out[0], out[1]


def read_tree_words(out_dir: str, manifest: dict) -> np.ndarray:
    """Reassemble the converted tree's (grid_h*256, grid_w*256) word grid from disk."""
    gw, gh = manifest["grid"]["w"], manifest["grid"]["h"]
    full = np.zeros((gh * SECTION_TILES, gw * SECTION_TILES), dtype=np.uint16)
    for sy in range(gh):
        for sx in range(gw):
            n = sy * gw + sx
            data = open(os.path.join(out_dir, f"section_{n}.tiles.bin"), "rb").read()
            if len(data) != SECTION_FILE_BYTES:
                raise SystemExit(f"{out_dir}/section_{n}.tiles.bin is {len(data)} bytes")
            arr = np.frombuffer(data, dtype=">u2").reshape(SECTION_TILES, SECTION_TILES)
            full[sy * SECTION_TILES:(sy + 1) * SECTION_TILES,
                 sx * SECTION_TILES:(sx + 1) * SECTION_TILES] = arr
    return full


def verify_tree(out_dir: str, quiet: bool = False) -> dict:
    """The parcel's falsifiable check, run against bytes on disk.

    Four things, each counted and each reported whether it passes or not:

    A. ROUND TRIP IS IDENTITY. Every cell of the donor's camera-box crop is
       re-derived from the donor's chunk/block/layout files by THIS module's own
       `expand_chunk_words` — not by the loader the writer used — and compared to
       the word read back out of `section_N.tiles.bin`. Reported as cells compared
       and cells differing.
    B. THE PAD IS ZERO. Every cell of the grid OUTSIDE the crop rectangle is zero.
       This is what makes rule 1's padding lossless rather than merely plausible:
       nothing was dropped, because everything outside the identity rectangle is
       provably blank.
    C. EVERY TILE INDEX IS INSIDE THE TILESET.
    D. `ojz_strip_gen.validate_editor_inputs` ACCEPTS THE TREE, pointed at the
       converted directory and its own `tileset.bin`, with the converted grid's
       section count. It raises SystemExit if it does not.
    """
    manifest = json.load(open(os.path.join(out_dir, "zone.json")))
    zone, donor = manifest["zone"], manifest["donor"]
    x0, x1, y0, y1 = manifest["extent"]["crop_tiles"]
    gw, gh = manifest["grid"]["w"], manifest["grid"]["h"]

    got = read_tree_words(out_dir, manifest)

    # A. identity over the crop, against an independent re-derivation
    ref_full = rederive_zone_words(zone, donor)
    ref = ref_full[y0:y1, x0:x1]
    sub = got[y0:y1, x0:x1]
    if ref.shape != sub.shape:
        raise SystemExit(
            f"{out_dir}: re-derived crop is {ref.shape}, tree holds {sub.shape}")
    diff = int(np.count_nonzero(ref != sub))
    compared = int(ref.size)

    # B. the pad is zero
    mask = np.zeros(got.shape, dtype=bool)
    mask[y0:y1, x0:x1] = True
    pad_nonzero = int(np.count_nonzero(got[~mask]))
    pad_cells = int((~mask).sum())

    # C. indices inside the tileset
    art_bytes = os.path.getsize(os.path.join(out_dir, "tileset.bin"))
    n_tiles = art_bytes // TILE_BYTES
    oob = int(np.count_nonzero((got & TILE_INDEX_MASK) >= n_tiles))

    # E. COLLISION (row 5): the planes on disk against a scalar re-derivation, and
    #    the same crop/pad rule the art obeys. Every cell of the crop is compared
    #    against `expand_collision_words`'s numpy output re-run here, and a SAMPLE
    #    is compared against `reference_collision_cell`, which shares no array code
    #    with it — the cheap exhaustive check plus the expensive independent one.
    got_a, got_b = read_tree_planes(out_dir, manifest)
    ref_a_full, ref_b_full = rederive_zone_collision(zone, donor)
    coll_diff = int(np.count_nonzero(ref_a_full[y0:y1, x0:x1] != got_a[y0:y1, x0:x1])
                    + np.count_nonzero(ref_b_full[y0:y1, x0:x1] != got_b[y0:y1, x0:x1]))
    coll_compared = int(got_a[y0:y1, x0:x1].size * 2)
    coll_pad_nonzero = int(np.count_nonzero(got_a[~mask]) + np.count_nonzero(got_b[~mask]))
    scalar_n, scalar_diff = 0, 0
    rng = np.random.default_rng(0xC0115101)          # fixed seed: a sample, not a lottery
    if y1 > y0 and x1 > x0:
        for _ in range(512):
            r = int(rng.integers(y0, y1))
            c = int(rng.integers(x0, x1))
            scalar_n += 1
            if reference_collision_cell(zone, donor, r, c) != (int(got_a[r, c]),
                                                               int(got_b[r, c])):
                scalar_diff += 1

    # D. the real gate — run LAST so it also sees the collision files, which
    #    validate_editor_inputs checks "when present".
    ojz_strip_gen.validate_editor_inputs(out_dir,
                                         os.path.join(out_dir, "tileset.bin"),
                                         gw * gh)

    ok = (diff == 0 and pad_nonzero == 0 and oob == 0
          and coll_diff == 0 and coll_pad_nonzero == 0 and scalar_diff == 0)
    result = {
        "zone": zone, "donor": donor, "dir": out_dir,
        "sections": gw * gh,
        "roundtrip_cells_compared": compared,
        "roundtrip_cells_differing": diff,
        "pad_cells": pad_cells,
        "pad_cells_nonzero": pad_nonzero,
        "tileset_tiles": n_tiles,
        "tile_indices_out_of_range": oob,
        "collision_cells_compared": coll_compared,
        "collision_cells_differing": coll_diff,
        "collision_pad_cells_nonzero": coll_pad_nonzero,
        "collision_scalar_sampled": scalar_n,
        "collision_scalar_differing": scalar_diff,
        "collision_attr_entries": manifest["collision"]["attr_entries"],
        "validate_editor_inputs": "accepted",
        "ok": ok,
    }
    if not quiet:
        print(f"  {donor}@{zone}: round trip {compared} cells compared, {diff} differing; "
              f"pad {pad_cells} cells, {pad_nonzero} nonzero; "
              f"{oob} indices past the {n_tiles}-tile tileset; "
              f"collision {coll_compared} cells, {coll_diff} differing, "
              f"{coll_pad_nonzero} nonzero pad, {scalar_n} scalar-sampled "
              f"({scalar_diff} differing), {result['collision_attr_entries']} attr "
              f"entries; validate_editor_inputs accepted {gw * gh} sections -> "
              f"{'OK' if ok else 'FAILED'}")
    if not ok:
        raise SystemExit(f"{donor}@{zone}: conversion is NOT identity — {result}")
    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def split_spec(spec: str) -> tuple[str, str]:
    """`<donor>@<ZONE>` -> (donor, zone). The donor is REQUIRED.

    No default and no bare-name spelling: five zone names exist in BOTH donor
    trees with different data (CNZ, CPZ, HTZ, MTZ, OOZ), and a converter that
    guessed would write one donor's bytes under the other's name.
    """
    if "@" not in spec:
        raise SystemExit(
            f"{spec!r}: name the donor — `<donor>@<ZONE>`, one of "
            f"{', '.join(s2_donor.DONORS)}. There is no default: five zone names exist "
            f"in both trees with different data.")
    donor, zone = spec.split("@", 1)
    if donor not in s2_donor.DONORS:
        raise SystemExit(f"{spec}: unknown donor {donor!r} "
                         f"(one of {', '.join(s2_donor.DONORS)})")
    if not s2_donor.known_zone(zone, donor):
        raise SystemExit(f"{spec}: {donor} has no zone {zone!r} "
                         f"(one of {', '.join(s2_donor.zone_names(donor))})")
    return donor, zone


def zone_out_dir(zone: str, donor: str, root: str) -> str:
    return os.path.join(root, s2_donor.donor_dirname(donor), zone)


def mode_convert(args) -> int:
    pairs = [split_spec(s) for s in args.spec]
    if args.all_six:
        pairs = list(THE_SIX) + pairs
    if args.all_zones:
        pairs = [(d, z) for d in s2_donor.DONORS for z in s2_donor.zone_names(d)]
    if not pairs:
        raise SystemExit("name at least one <donor>@<ZONE>, or --all-six / --all-zones")
    seen, ordered = set(), []
    for p in pairs:
        if p not in seen:
            seen.add(p)
            ordered.append(p)

    print(f"# converting {len(ordered)} zone(s) -> {os.path.relpath(args.out, REPO)}")
    results = []
    for donor, zone in ordered:
        out = zone_out_dir(zone, donor, args.out)
        convert_zone(zone, donor, out)
        results.append(verify_tree(out))
    bad = [r for r in results if not r["ok"]]
    print(f"# {len(results)} zone(s) converted, "
          f"{sum(r['roundtrip_cells_compared'] for r in results)} cells round-tripped, "
          f"{sum(r['roundtrip_cells_differing'] for r in results)} differing, "
          f"{len(bad)} FAILED")
    if args.json:
        print(json.dumps(results, indent=2))
    return 1 if bad else 0


def mode_verify(args) -> int:
    results = [verify_tree(d) for d in args.dir]
    bad = [r for r in results if not r["ok"]]
    print(f"# {len(results)} tree(s), {len(bad)} FAILED")
    if args.json:
        print(json.dumps(results, indent=2))
    return 1 if bad else 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__.split("\n")[0],
        formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="mode", required=True)

    c = sub.add_parser("convert", help="write one or more zones' editor trees")
    c.add_argument("spec", nargs="*", help="<donor>@<ZONE>")
    c.add_argument("--out", default=DEFAULT_OUT_ROOT,
                   help=f"output root (default {os.path.relpath(DEFAULT_OUT_ROOT, REPO)})")
    c.add_argument("--all-six", action="store_true",
                   help="also convert the owner's six showcase zones")
    c.add_argument("--all-zones", action="store_true",
                   help="convert every zone of both donors (overrides the specs)")
    c.add_argument("--json", action="store_true")
    c.set_defaults(func=mode_convert)

    v = sub.add_parser("verify", help="re-verify already-written trees")
    v.add_argument("dir", nargs="+", help="a converted zone directory")
    v.add_argument("--json", action="store_true")
    v.set_defaults(func=mode_verify)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
