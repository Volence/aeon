#!/usr/bin/env python3
"""Collision attr-set pipeline (§5 Task 1).

Bakes sonic_hack per-placement collision (profile, xflip, yflip, solidity)
into one-byte attr-set indices + ROM tables. See
docs/superpowers/specs/2026-06-12-player-system-design.md §4 and
docs/research/player-sensors-sce.md §3.3.

Usage:
    python3 tools/collision_pipeline.py test    # run self-tests
    python3 tools/collision_pipeline.py --probe SEC_ID X Y [SEC_ID X Y ...]
        # print baked attr byte, solidity, height/rotated-height column
        # bytes and angle for BOTH paths at section-local pixel (X, Y).
        # Attr indices come from the canonical build walk
        # (enumerate_collision_layouts × build_section_collision), so they
        # match the bytes the strips carry and data/collision/*.bin.

Height semantics (per-column profile byte h):
    0          empty column
    1..16      solid height in pixels measured UP from the block bottom
    0x80..0xFF two's-complement negative: solid hangs DOWN from the block
               top with depth 256-h

Angles are 256-unit bytes, 0 = flat. Odd values flag "no usable angle"
and stay odd through flips (negation preserves oddness).
"""

import glob
import os
import sys

# Allow running from the aeon root (where build.sh lives).
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# Shared paths + loaders come from ojz_common (NOT ojz_strip_gen — that would
# recreate the old collision_pipeline <-> ojz_strip_gen import cycle).
from ojz_common import (
    SONIC_HACK,
    CHUNK_MAP_PATH,
    LAYOUT_DIR,
    kos_decompress,
    load_chunk_map,
    load_layout,
)

# ---------------------------------------------------------------------------
# Solidity values (per path, 2 bits in the chunk entry word)
# ---------------------------------------------------------------------------
SOL_NONE, SOL_TOP, SOL_LRB, SOL_ALL = 0, 1, 2, 3

BLOCK_ID_MASK = 0x03FF      # bits 9:0 of a chunk entry word
CHUNK_XFLIP_BIT = 0x0400    # bit 10
CHUNK_YFLIP_BIT = 0x0800    # bit 11
PATH_A_SOL_SHIFT = 12       # bits 13:12 (bit12=top, bit13=lrb)
PATH_B_SOL_SHIFT = 14       # bits 15:14

PROFILE_LEN = 16            # one height byte per 16x16-block column
MAX_PROFILES = 256          # one byte indexes the attr-set


# ---------------------------------------------------------------------------
# Pure flip / coverage primitives
# ---------------------------------------------------------------------------

def flip_profile_x(heights: bytes) -> bytes:
    """xflip: reverse the 16 per-column heights."""
    return bytes(reversed(heights))


def flip_profile_y(heights: bytes) -> bytes:
    """yflip: solid now hangs from the top edge. 0→0, 16→16 (full stays
    full), else h → 256-h (two's-complement negative byte = hanging depth)."""
    return bytes(h if h in (0, 16) else (256 - h) & 0xFF for h in heights)


def flip_angle_x(angle: int) -> int:
    """Negate angle; odd-flag values stay odd (e.g. $FF → $01)."""
    return (-angle) & 0xFF


def flip_angle_y(angle: int) -> int:
    """Reflect: -(angle+$40)-$40 == -angle-$80."""
    return (-angle - 0x80) & 0xFF


def covers(h: int, row: int) -> bool:
    """Does signed height byte h cover block row `row` (0 = top)?"""
    if h == 0:
        return False
    if h == 16:
        return True
    if h < 0x80:
        return row >= 16 - h                    # bottom-anchored
    return row < (256 - h)                      # hanging, depth 256-h


def rotate_profile(heights: bytes) -> bytes:
    """Regenerate the rotated (wall) profile from a vertical profile.

    rotated[row] = solid width at block row `row` (0 = TOP row), measured
    from the LEFT edge when the row's solid run touches the left edge
    (positive width = contiguous run length from left); when the run is
    anchored at the RIGHT edge instead, emit negative width (256-w), per
    the S2 'Collision array 2' convention. Row all-solid → 16; none → 0.
    A row whose solid span touches NEITHER edge (floating middle) →
    raise ValueError (doesn't occur in OJZ data; the real-data self-test
    proves it).
    """
    rotated = bytearray(PROFILE_LEN)
    for row in range(PROFILE_LEN):
        solid = [covers(heights[col], row) for col in range(PROFILE_LEN)]
        if not any(solid):
            rotated[row] = 0
            continue
        if all(solid):
            rotated[row] = 16
            continue
        if solid[0]:
            # Left-anchored: contiguous run length from the left edge
            w = 0
            while w < PROFILE_LEN and solid[w]:
                w += 1
            if any(solid[w:]):
                raise ValueError(
                    f"rotate_profile: row {row} has multiple solid runs "
                    f"(heights={list(heights)})"
                )
            rotated[row] = w
        elif solid[PROFILE_LEN - 1]:
            # Right-anchored: contiguous run length from the right edge,
            # emitted as a negative byte (256-w)
            w = 0
            while w < PROFILE_LEN and solid[PROFILE_LEN - 1 - w]:
                w += 1
            rotated[row] = (256 - w) & 0xFF
        else:
            raise ValueError(
                f"rotate_profile: row {row} solid span touches neither edge "
                f"(heights={list(heights)})"
            )
    return bytes(rotated)


# ---------------------------------------------------------------------------
# Attr-set: deduplicated (heights, angle, solidity) → one-byte index
# ---------------------------------------------------------------------------

class AttrSet:
    """Deduplicated (heights, angle, solidity) → byte index. Index 0
    reserved for air."""

    def __init__(self):
        self.entries = [(bytes(PROFILE_LEN), 0x00, SOL_NONE)]   # 0 = air
        self.lookup: dict[tuple[bytes, int, int], int] = {}
        self.lookup[self.entries[0]] = 0

    def intern(self, heights: bytes, angle: int, solidity: int) -> int:
        key = (heights, angle, solidity)
        idx = self.lookup.get(key)
        if idx is not None:
            return idx
        idx = len(self.entries)
        if idx > 255:
            raise ValueError(
                f"AttrSet overflow: more than 255 unique solid combos "
                f"(interning entry {idx})"
            )
        self.entries.append(key)
        self.lookup[key] = idx
        return idx


def bake_cell(block_word: int, index_a: bytes, index_b: bytes,
              profiles: bytes, angles: bytes,
              attrset: AttrSet) -> tuple[int, int]:
    """One 16×16 placement → (path_a_byte, path_b_byte).

    block_word: chunk-entry word (bits 9:0 block id, bit 10 xflip, bit 11
    yflip, bits 13:12 path-A solidity [bit12=top, bit13=lrb], bits 15:14
    path-B solidity). Per path: solidity=(word>>shift)&3 with shift 12 (A)
    or 14 (B); profile_id=index[block_id]; if solidity==0 or profile_id==0
    → byte 0; else apply xflip then yflip to (heights, angle), intern.
    """
    block_id = block_word & BLOCK_ID_MASK
    xflip = bool(block_word & CHUNK_XFLIP_BIT)
    yflip = bool(block_word & CHUNK_YFLIP_BIT)

    result = []
    for shift, index in ((PATH_A_SOL_SHIFT, index_a),
                         (PATH_B_SOL_SHIFT, index_b)):
        solidity = (block_word >> shift) & 3
        profile_id = index[block_id] if block_id < len(index) else 0
        if solidity == SOL_NONE or profile_id == 0:
            result.append(0)
            continue
        heights = profiles[profile_id * PROFILE_LEN:
                           (profile_id + 1) * PROFILE_LEN]
        angle = angles[profile_id]
        if xflip:
            heights = flip_profile_x(heights)
            angle = flip_angle_x(angle)
        if yflip:
            heights = flip_profile_y(heights)
            angle = flip_angle_y(angle)
        result.append(attrset.intern(heights, angle, solidity))
    return (result[0], result[1])


def bake_plane_cell(cell_word: int, profiles: bytes, angles: bytes,
                    attrset: AttrSet) -> int:
    """One Aurora plane's 16-bit cell word -> interned attr-set byte.

    Aurora paints each of the engine's TWO collision planes independently, so
    each cell carries its OWN word (vs bake_cell's single word driving both
    paths). cell_word bits: 9:0 base-bank shape index, bit10 xflip, bit11 yflip,
    13:12 THIS plane's solidity (bit12=top, bit13=lrb). Air (shape 0) or
    solidity NONE -> byte 0. Applies xflip then yflip (same order as bake_cell),
    then interns (heights, angle, solidity) into the shared attr-set."""
    shape = cell_word & BLOCK_ID_MASK
    solidity = (cell_word >> PATH_A_SOL_SHIFT) & 3
    if solidity == SOL_NONE or shape == 0:
        return 0
    heights = profiles[shape * PROFILE_LEN:(shape + 1) * PROFILE_LEN]
    angle = angles[shape] if shape < len(angles) else 0
    if cell_word & CHUNK_XFLIP_BIT:
        heights = flip_profile_x(heights)
        angle = flip_angle_x(angle)
    if cell_word & CHUNK_YFLIP_BIT:
        heights = flip_profile_y(heights)
        angle = flip_angle_y(angle)
    return attrset.intern(heights, angle, solidity)


def emit_tables(attrset: AttrSet) -> dict[str, bytes]:
    """ROM tables: {'heightmaps.bin': 4096B (256×16), 'heightmaps_rot.bin':
    4096B (rotate_profile per entry), 'angles.bin': 256B, 'solidity.bin':
    256B}. Unused slots zero."""
    heightmaps = bytearray(MAX_PROFILES * PROFILE_LEN)
    heightmaps_rot = bytearray(MAX_PROFILES * PROFILE_LEN)
    angles = bytearray(MAX_PROFILES)
    solidity = bytearray(MAX_PROFILES)
    for i, (heights, angle, sol) in enumerate(attrset.entries):
        heightmaps[i * PROFILE_LEN:(i + 1) * PROFILE_LEN] = heights
        heightmaps_rot[i * PROFILE_LEN:(i + 1) * PROFILE_LEN] = \
            rotate_profile(heights)
        angles[i] = angle
        solidity[i] = sol
    return {
        "heightmaps.bin": bytes(heightmaps),
        "heightmaps_rot.bin": bytes(heightmaps_rot),
        "angles.bin": bytes(angles),
        "solidity.bin": bytes(solidity),
    }


def emit_stub_tables() -> dict[str, bytes]:
    """Legacy flat-solid stub tables: type 0 = air, type 1 = full block.

    Emitted when the sonic_hack collision sources are missing — pairs with
    the strip generator's priority-bit placeholder collision bytes (0 = air,
    1 = solid). Used by both gen_collision_data.py (baseline emit) and
    ojz_strip_gen.generate() (fallback branch).
    """
    heightmaps = bytearray(MAX_PROFILES * PROFILE_LEN)
    for i in range(PROFILE_LEN):
        heightmaps[1 * PROFILE_LEN + i] = 0x10
    solidity = bytearray(MAX_PROFILES)
    solidity[1] = SOL_ALL
    return {
        "heightmaps.bin": bytes(heightmaps),
        # A full 16-high block rotates to itself (all-16 widths)
        "heightmaps_rot.bin": bytes(heightmaps),
        "angles.bin": bytes(MAX_PROFILES),
        "solidity.bin": bytes(solidity),
    }


# ---------------------------------------------------------------------------
# Loader helper (file I/O kept separate from the pure functions)
# ---------------------------------------------------------------------------

def load_collision_sources(sonic_hack_dir: str):
    """Returns (index_a, index_b, profiles, angles).

    index_a/b: Kosinski-decompressed from
      '<dir>/collision/OJZ primary 16x16 collision index.bin' and
      '<dir>/collision/OJZ secondary 16x16 collision index.bin'
      (both decode to 374 bytes).
    profiles: raw 4096 bytes from '<dir>/collision/Collision array 1.bin'.
    angles: raw 256 bytes from
      '<dir>/collision/Curve and resistance mapping.bin'.
    """
    coll_dir = os.path.join(sonic_hack_dir, "collision")

    def _kos_load(name: str) -> bytes:
        with open(os.path.join(coll_dir, name), "rb") as f:
            data = f.read()
        decoded, _ = kos_decompress(data, 0)
        return decoded

    index_a = _kos_load("OJZ primary 16x16 collision index.bin")
    index_b = _kos_load("OJZ secondary 16x16 collision index.bin")
    with open(os.path.join(coll_dir, "Collision array 1.bin"), "rb") as f:
        profiles = f.read()
    with open(os.path.join(coll_dir, "Curve and resistance mapping.bin"),
              "rb") as f:
        angles = f.read()

    # Validate profile bytes: 0..16 (bottom-anchored height) or
    # 0xF0..0xFF (hanging depth 1..16). Anything else (0x11-0xEF) is
    # undefined and would silently read as fully solid — fail loudly.
    for off, h in enumerate(profiles):
        if not (h <= 16 or h >= 0xF0):
            raise ValueError(
                f"load_collision_sources: profile {off // PROFILE_LEN} "
                f"column {off % PROFILE_LEN} has undefined height byte "
                f"0x{h:02X}"
            )
    return index_a, index_b, profiles, angles


# ---------------------------------------------------------------------------
# Probe mode (§5 Task 4) — query one cell the way the runtime sees it
# ---------------------------------------------------------------------------

def resolve_cell(layout: list[list[int]], chunks: list[list[int]],
                 x: int, y: int) -> int | None:
    """Chunk-entry word covering section-local pixel (x, y), or None when
    the position falls outside the layout / references an out-of-range
    chunk (both bake to air). Mirrors build_section_collision's walk:
    128px chunks, 8×8 blocks of 16px per chunk."""
    if x < 0 or y < 0:
        return None
    chunk_row, chunk_col = y // 128, x // 128
    if chunk_row >= len(layout) or chunk_col >= len(layout[chunk_row]):
        return None
    chunk_id = layout[chunk_row][chunk_col]
    if chunk_id >= len(chunks):
        return None
    block_row, block_col = (y % 128) // 16, (x % 128) // 16
    return chunks[chunk_id][block_row * 8 + block_col]


def build_canonical_attrset():
    """Replicate the build's attr-set intern order exactly: walk
    enumerate_collision_layouts() through build_section_collision (the ONE
    walk implementation, same as generate() Pass 1b / gen_collision_data).
    Returns (attrset, index_a, index_b, profiles, angles, layouts) where
    layouts maps sec_id (str) → layout."""
    # Lazy import: ojz_strip_gen imports this module at top level — a
    # module-level import here would recreate the old import cycle.
    import ojz_strip_gen

    index_a, index_b, profiles, angles = load_collision_sources(SONIC_HACK)
    chunks = load_chunk_map(CHUNK_MAP_PATH)
    attrset = AttrSet()
    layouts: dict[str, list[list[int]]] = {}
    for sec_id, path in ojz_strip_gen.enumerate_collision_layouts():
        layout = load_layout(path)
        layouts[sec_id] = layout
        if layout:
            ojz_strip_gen.build_section_collision(
                layout, chunks, index_a, index_b, profiles, angles, attrset
            )
    return attrset, index_a, index_b, profiles, angles, layouts, chunks


def run_probe(triples: list[tuple[str, int, int]]):
    """--probe driver: print both paths' attr data for each (sec, x, y)."""
    (attrset, index_a, index_b, profiles, angles,
     layouts, chunks) = build_canonical_attrset()

    # Consistency proof: the rebuilt walk must reproduce the on-disk tables,
    # otherwise the printed attr indices don't match the built ROM.
    coll_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "..", "games", "sonic4", "data", "collision")
    tables = emit_tables(attrset)
    stale = []
    for name, blob in sorted(tables.items()):
        path = os.path.join(coll_dir, name)
        if not os.path.isfile(path):
            stale.append(f"{name} (missing)")
            continue
        with open(path, "rb") as f:
            if f.read() != blob:
                stale.append(name)
    if stale:
        print(f"WARNING: data/collision out of date vs this walk: "
              f"{', '.join(stale)} — attr indices below may not match the "
              f"built ROM. Re-run build.sh.")
    else:
        print("data/collision/*.bin match this walk (attr indices valid)")

    for sec_id, x, y in triples:
        layout = layouts.get(sec_id)
        if layout is None:
            print(f"sec {sec_id} ({x},{y}): NO LAYOUT (not in canonical "
                  f"enumeration)")
            continue
        word = resolve_cell(layout, chunks, x, y)
        sub_x, sub_y = x & 0xF, y & 0xF
        print(f"sec {sec_id} local ({x},{y})  sub_x={sub_x} sub_y={sub_y}  "
              f"word={'None' if word is None else f'${word:04X}'}")
        a, b = (0, 0) if word is None else bake_cell(
            word, index_a, index_b, profiles, angles, attrset)
        for path_name, attr in (("A", a), ("B", b)):
            heights, angle, sol = attrset.entries[attr]
            rot = rotate_profile(heights)
            h = heights[sub_x]
            w = rot[sub_y]
            hs = h - 256 if h >= 0x80 else h
            ws = w - 256 if w >= 0x80 else w
            print(f"  path {path_name}: attr=${attr:02X} sol={sol} "
                  f"angle=${angle:02X} h[{sub_x}]=${h:02X}({hs:+d}) "
                  f"rot[{sub_y}]=${w:02X}({ws:+d})")


# ---------------------------------------------------------------------------
# Self-tests
# ---------------------------------------------------------------------------

def test_flip_x_reverses():
    """Synthetic ramp 1..16 reversed by flip_profile_x."""
    ramp = bytes(range(1, 17))
    assert flip_profile_x(ramp) == bytes(range(16, 0, -1))
    # Double flip is identity
    assert flip_profile_x(flip_profile_x(ramp)) == ramp
    print("  [OK] test_flip_x_reverses")


def test_flip_y_negates():
    """h=4 → 0xFC; 0 and 16 unchanged."""
    src = bytes([4, 0, 16, 8])
    out = flip_profile_y(src + bytes(12))
    assert out[0] == 0xFC, f"h=4 should yflip to 0xFC, got 0x{out[0]:02X}"
    assert out[1] == 0, "h=0 must stay 0"
    assert out[2] == 16, "h=16 must stay 16"
    assert out[3] == 0xF8, f"h=8 should yflip to 0xF8, got 0x{out[3]:02X}"
    print("  [OK] test_flip_y_negates")


def test_angle_flips():
    """flip_angle_x(0x20)==0xE0; odd flags stay odd; flip_angle_y(0x20)==0x60."""
    assert flip_angle_x(0x20) == 0xE0
    assert flip_angle_x(0xFF) == 0x01, "odd-flag must stay odd through xflip"
    assert flip_angle_y(0xFF) % 2 == 1, "odd-flag must stay odd through yflip"
    assert flip_angle_y(0x20) == 0x60
    assert flip_angle_x(0x00) == 0x00, "flat stays flat through xflip"
    print("  [OK] test_angle_flips")


def test_covers_semantics():
    """h=4 covers rows 12-15 only; h=0xFC (hanging depth 4) covers rows 0-3."""
    for row in range(16):
        assert covers(4, row) == (row >= 12), f"h=4 row {row}"
        assert covers(0xFC, row) == (row < 4), f"h=0xFC row {row}"
        assert covers(0, row) is False, f"h=0 row {row}"
        assert covers(16, row) is True, f"h=16 row {row}"
    print("  [OK] test_covers_semantics")


def test_rotate_flat_full():
    """All-16 profile → rotated all-16; all-0 → all-0."""
    assert rotate_profile(bytes([16] * 16)) == bytes([16] * 16)
    assert rotate_profile(bytes(16)) == bytes(16)
    print("  [OK] test_rotate_flat_full")


def test_rotate_ramp():
    """Hand-computed asymmetric cases."""
    # Left half empty, right half full: every row's solid span is
    # columns 8-15 = right-anchored width 8 → 256-8 = 0xF8.
    step = bytes([0] * 8 + [16] * 8)
    assert rotate_profile(step) == bytes([0xF8] * 16)

    # Sloped profile: heights 1..16 left-to-right. Row r is covered by
    # column c iff c >= 15-r (right-anchored run of width r+1).
    # Rows 0-14 → 256-(r+1) = 255-r; row 15 all-solid → 16.
    ramp = bytes(range(1, 17))
    expected = bytes([255 - r for r in range(15)] + [16])
    assert rotate_profile(ramp) == expected

    # Mirrored slope (16..1): left-anchored, row r width r+1; row 15 → 16.
    ramp_l = flip_profile_x(ramp)
    expected_l = bytes([r + 1 for r in range(15)] + [16])
    assert rotate_profile(ramp_l) == expected_l

    # Floating middle span must raise
    floating = bytes([0] * 6 + [4] * 4 + [0] * 6)
    try:
        rotate_profile(floating)
        assert False, "floating middle span must raise ValueError"
    except ValueError:
        pass

    # Two solid runs in one row (solid at BOTH edges, gap in the middle)
    # must raise instead of silently truncating to the left run width.
    two_runs = bytes([16, 16] + [0] * 12 + [16, 16])
    try:
        rotate_profile(two_runs)
        assert False, "two-run row must raise ValueError"
    except ValueError:
        pass
    print("  [OK] test_rotate_ramp")


def test_attrset_dedup_and_air():
    """Same combo interned once; index 0 is air."""
    s = AttrSet()
    assert s.entries[0] == (bytes(16), 0, 0), "index 0 must be air"
    assert s.intern(bytes(16), 0, SOL_NONE) == 0, \
        "interning the air combo must return index 0, not a duplicate"
    h = bytes([16] * 16)
    i1 = s.intern(h, 0x00, SOL_ALL)
    i2 = s.intern(h, 0x00, SOL_ALL)
    assert i1 == i2 == 1, "duplicate combo must dedup to the same index"
    i3 = s.intern(h, 0x00, SOL_TOP)
    assert i3 == 2, "different solidity is a distinct entry"
    i4 = s.intern(h, 0x20, SOL_ALL)
    assert i4 == 3, "different angle is a distinct entry"
    assert len(s.entries) == 4
    print("  [OK] test_attrset_dedup_and_air")


def test_bake_cell_solidity_gate():
    """Solidity 0 → byte 0 even with nonzero profile; paths independent."""
    # Synthetic sources: block 1 → profile 1 (full block, angle 0)
    index = bytes([0, 1])
    profiles = bytes(16) + bytes([16] * 16) + bytes(4096 - 32)
    angles = bytes(256)

    s = AttrSet()
    # Both paths solidity 0 → both bytes 0 despite the solid profile
    a, b = bake_cell(0x0001, index, index, profiles, angles, s)
    assert (a, b) == (0, 0), f"solidity 0 must gate to air, got ({a},{b})"
    assert len(s.entries) == 1, "nothing interned for solidity-0 placement"

    # Path A top-solid (bit 12), path B empty
    a, b = bake_cell(0x0001 | (SOL_TOP << PATH_A_SOL_SHIFT),
                     index, index, profiles, angles, s)
    assert a != 0 and b == 0, f"A solid + B empty expected, got ({a},{b})"

    # Path B all-solid (bits 15:14), path A empty
    a, b = bake_cell(0x0001 | (SOL_ALL << PATH_B_SOL_SHIFT),
                     index, index, profiles, angles, s)
    assert a == 0 and b != 0, f"A empty + B solid expected, got ({a},{b})"

    # Profile 0 (air block) gates to 0 even with solidity set
    a, b = bake_cell(0x0000 | (SOL_ALL << PATH_A_SOL_SHIFT),
                     index, index, profiles, angles, s)
    assert (a, b) == (0, 0), "profile 0 must gate to air"

    # block_id beyond the index table must not crash → profile 0 → air
    a, b = bake_cell(0x03FF | (SOL_ALL << PATH_A_SOL_SHIFT),
                     index, index, profiles, angles, s)
    assert (a, b) == (0, 0), "out-of-range block_id must gate to air"
    print("  [OK] test_bake_cell_solidity_gate")


def test_bake_plane_cell():
    """One Aurora 16-bit plane word -> interned attr byte. Per-plane solidity at
    bits 13:12; X/Y flip applied; air (shape 0 / solidity NONE) -> 0."""
    # block 1 = a right-ascending ramp (heights 1..16), angle 0x20
    profiles = bytes(16) + bytes(range(1, 17)) + bytes(4096 - 32)
    angles = bytes([0, 0x20]) + bytes(254)
    s = AttrSet()

    # air / no-solidity gate (nothing interned)
    assert bake_plane_cell(0x0000, profiles, angles, s) == 0
    assert bake_plane_cell(0x0001, profiles, angles, s) == 0, "solidity NONE -> air"
    assert len(s.entries) == 1

    # plain solid shape 1
    i_plain = bake_plane_cell(0x0001 | (SOL_ALL << PATH_A_SOL_SHIFT), profiles, angles, s)
    assert i_plain == 1
    assert s.entries[1] == (bytes(range(1, 17)), 0x20, SOL_ALL)

    # x-flip → reversed columns + negated angle, a DISTINCT entry
    i_xf = bake_plane_cell(0x0001 | CHUNK_XFLIP_BIT | (SOL_ALL << PATH_A_SOL_SHIFT),
                           profiles, angles, s)
    assert s.entries[i_xf] == (bytes(reversed(range(1, 17))), flip_angle_x(0x20), SOL_ALL)
    assert i_xf != i_plain

    # jump-through (top-only) of the same shape: distinct solidity entry
    i_jt = bake_plane_cell(0x0001 | (SOL_TOP << PATH_A_SOL_SHIFT), profiles, angles, s)
    assert s.entries[i_jt] == (bytes(range(1, 17)), 0x20, SOL_TOP)
    assert i_jt not in (i_plain, i_xf)
    print("  [OK] test_bake_plane_cell")


def test_resolve_cell():
    """--probe's cell resolution: chunk/block decomposition + air guards."""
    # 2×2 chunk layout; chunk 0 = all words 0, chunk 1 = word index baked
    # into the value so the picked entry is self-identifying.
    chunk0 = [0] * 64
    chunk1 = [0x1000 + i for i in range(64)]
    layout = [[0, 1], [1, 0]]
    chunks = [chunk0, chunk1]

    # (0,0) → chunk 0, block (0,0)
    assert resolve_cell(layout, chunks, 0, 0) == 0
    # (128+35, 17) → chunk 1 (layout[0][1]), block_row 1, block_col 2 → idx 10
    assert resolve_cell(layout, chunks, 128 + 35, 17) == 0x100A
    # (15, 128+127) → chunk 1 (layout[1][0]), block_row 7, block_col 0 → idx 56
    assert resolve_cell(layout, chunks, 15, 128 + 127) == 0x1038
    # Out of layout bounds / negative → None
    assert resolve_cell(layout, chunks, 256, 0) is None
    assert resolve_cell(layout, chunks, 0, 256) is None
    assert resolve_cell(layout, chunks, -1, 0) is None
    # Out-of-range chunk id → None
    assert resolve_cell([[7]], chunks, 0, 0) is None
    print("  [OK] test_resolve_cell")


def test_real_data_measurement():
    """Bake every OJZ placement; measure attr-set size; emit_tables runs."""
    index_a, index_b, profiles, angles = load_collision_sources(SONIC_HACK)
    assert len(index_a) == 374, f"index_a: expected 374 bytes, got {len(index_a)}"
    assert len(index_b) == 374, f"index_b: expected 374 bytes, got {len(index_b)}"
    assert len(profiles) == 4096, f"profiles: expected 4096, got {len(profiles)}"
    assert len(angles) == 256, f"angles: expected 256, got {len(angles)}"

    chunks = load_chunk_map(CHUNK_MAP_PATH)
    layout_files = sorted(glob.glob(os.path.join(LAYOUT_DIR, "OJZ_1_sec*.bin")))
    assert layout_files, f"no OJZ section layouts under {LAYOUT_DIR}"

    attrset = AttrSet()
    placements = 0
    for path in layout_files:
        layout = load_layout(path)
        for row in layout:
            for chunk_id in row:
                if chunk_id >= len(chunks):
                    continue  # out-of-range → empty
                for word in chunks[chunk_id]:
                    bake_cell(word, index_a, index_b, profiles, angles, attrset)
                    placements += 1

    count = len(attrset.entries)
    assert count <= 255, f"attr-set overflow: {count} entries"
    assert count > 1, "real OJZ data produced no solid combos at all"

    # emit_tables must not raise — proves rotate_profile handles every
    # real synthesized profile (no floating middle spans in OJZ data).
    tables = emit_tables(attrset)
    assert len(tables["heightmaps.bin"]) == 4096
    assert len(tables["heightmaps_rot.bin"]) == 4096
    assert len(tables["angles.bin"]) == 256
    assert len(tables["solidity.bin"]) == 256
    # Index 0 is air in every table
    assert tables["heightmaps.bin"][:16] == bytes(16)
    assert tables["solidity.bin"][0] == 0

    print(f"  [OK] test_real_data_measurement: {len(layout_files)} sections, "
          f"{placements} placements → {count} attr-set entries "
          f"(incl. air at index 0)")


def run_tests():
    """Run all self-tests."""
    print("Running collision_pipeline tests...")
    test_flip_x_reverses()
    test_flip_y_negates()
    test_angle_flips()
    test_covers_semantics()
    test_rotate_flat_full()
    test_rotate_ramp()
    test_attrset_dedup_and_air()
    test_bake_cell_solidity_gate()
    test_bake_plane_cell()
    test_resolve_cell()
    test_real_data_measurement()
    print("All tests passed")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) == 2 and sys.argv[1] == "test":
        run_tests()
        return
    if len(sys.argv) >= 5 and sys.argv[1] == "--probe" \
            and (len(sys.argv) - 2) % 3 == 0:
        args = sys.argv[2:]
        triples = [(args[i], int(args[i + 1], 0), int(args[i + 2], 0))
                   for i in range(0, len(args), 3)]
        run_probe(triples)
        return
    print(f"Usage: {sys.argv[0]} test")
    print(f"       {sys.argv[0]} --probe SEC_ID X Y [SEC_ID X Y ...]")
    sys.exit(1)


if __name__ == "__main__":
    main()
