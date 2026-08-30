#!/usr/bin/env python3
"""Deterministic S3K Tails + Knuckles asset extractor/converter for Aeon.

Design #3 (character-dispatch) asset PREP. Reads stock Sonic 3 & Knuckles
character assets out of the read-only skdisasm tree and emits them in Aeon's
sprite formats (mirroring our custom-Sonic pipeline, with the ONE documented
divergence below), plus intermediate JSON for the animation scripts (whose
11-universal-id .emp table authoring is a character-plan decision, deferred
here). See README.md for provenance and the full list of decisions made vs
deferred.

BALL SEATING IS THE ONE GEOMETRIC TRANSFORM (2026-08-29, owner ruling d-36).
Every mapping frame is converted verbatim EXCEPT the rolling-ball frames, whose
piece `y_off` is moved by a shift DERIVED from BALL_Y_RADIUS so the ball seats on
the collision floor. See the "Ball seating" section below; asserted by
tools/test_ball_seating.py. Sonic's ball is not produced here and already seats
flush (verified, not assumed).

Source of truth for the Aeon formats this mirrors:
  tools/convert_s2_mappings.py  -> mapping VDP-order binary + flip-invariant bbox
  tools/dplc_layout.py          -> contiguous art rearrange + <=16-tile DPLC split
  tools/verify_sprites.py       -> art/DPLC structural checks

Canonical S3K sources (verified against s3.asm: Obj_Tails / Obj_Tails_Tail /
Obj_Knuckles load exactly these — NOT the *_S3 / *2P / SStage variants):
  Tails body      : Map_Tails_ / PLC_Tails_ / AniTails_ / ArtUnc_Tails
  Tails appendage : Map_Tails_Tail_ / PLC_Tails_Tail_ / AniTails_Tail_ / ArtUnc_Tails_Tail
  Knuckles        : Map_Knuckles_ / DPLC(Knuckles) / AniKnuckles_ / ArtUnc_Knuckles

Deterministic: no timestamps, no RNG; JSON is sorted & fixed-indent. Running
twice produces byte-identical output.

TAILS ART IS RE-INDEXED, NOT COPIED (2026-08-10). S3K's art indexes S3K's
character palette; Aeon loads a *different ordering of the same colours* into
CRAM line 0 (art/palettes/SonicAndTails.bin, the sonic_hack/S2-era order). Tails
therefore rendered with a grey head and an orange body. The fix is a colour-
lossless index permutation applied at build time — see `derive_palette_remap`
and `remap_art_indices` below. Sonic's art is already in our order and is not
produced here.

KNUCKLES CANNOT BE BRIDGED ONTO SONICTAILS' LINE (he uses an S3K colour that line
lacks), so he keeps his own CRAM line 0. But he IS permuted WITHIN that line
(2026-08-12): KNUCKLES_LINE_PERMUTE swaps his grays into the shared effect-dust
slots 4/6/7 so the shared skid/spindash/slide dust — which draws on line 0 at
those indices — stays gray on him instead of inheriting his reds. It is applied
identically to his art and his palette (a lossless relabel). See README.md.

Usage:
  ./gen_characters.py [skdisasm_root]
  (default skdisasm_root = <suite>/skdisasm, beside this aeon checkout)
"""

import hashlib
import json
import re
import struct
import sys
from pathlib import Path

TILE_SIZE = 32               # one 8x8 4bpp tile = 32 bytes
MAX_TILES_PER_ENTRY = 16     # DPLC tile-count is a 4-bit field (bits 15-12 = count-1)
S3K_MAP_PIECE = 6            # S3K 1P mapping piece: Y.b size.b tile.w X.w
AF_CTRL_THRESHOLD = 0xF7     # anim bytes >= this are control codes (engine constants.emp)

# Anim control-code operand counts, per engine/system/constants.emp ($F7-$FF).
# Used only to lay out the intermediate JSON readably; the raw bytes are always
# preserved so nothing here is load-bearing for the (deferred) .emp authoring.
AF_OPERANDS = {
    0xFF: 0,  # AF_END      loop/restart
    0xFE: 1,  # AF_BACK     rewind count
    0xFD: 1,  # AF_CHANGE   new anim id
    0xFC: 0,  # AF_ROUTINE  increment routine counter
    0xFB: 0,  # AF_DELETE   despawn
    0xFA: 3,  # AF_CALLBACK hi,lo,0
    0xF9: 1,  # AF_SOUND    sound id
    0xF8: 1,  # AF_COLLISION collision type
    0xF7: 2,  # AF_SET_FIELD (best-effort; unused by player scripts)
}
AF_NAME = {
    0xFF: "AF_END", 0xFE: "AF_BACK", 0xFD: "AF_CHANGE", 0xFC: "AF_ROUTINE",
    0xFB: "AF_DELETE", 0xFA: "AF_CALLBACK", 0xF9: "AF_SOUND",
    0xF8: "AF_COLLISION", 0xF7: "AF_SET_FIELD",
}

# aeon repo root — this file is at <root>/games/sonic4/data/characters_staging/.
AEON_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(AEON_ROOT / "tools"))
from suite_paths import suite_path                           # noqa: E402

DEFAULT_SK = suite_path("skdisasm")

# tools/measure_character_boxes.py owns the .emp const reader and the .emp animation
# table parser. Import them rather than re-implementing: the ball seating below is
# derived from the SAME BALL_Y_RADIUS and the SAME `Roll` frame list that the report
# tool and tools/test_ball_seating.py measure against, and two parsers that can drift
# apart would let the generator seat the ball against a frame set nothing else agrees
# with. Import is side-effect free (its os.chdir is under __main__).
sys.path.insert(0, str(AEON_ROOT / "tools"))
import measure_character_boxes as mcb                       # noqa: E402

# The two 16-colour CRAM lines the remap bridges (32 bytes = 16 big-endian words).
AEON_PLAYER_PAL = "art/palettes/SonicAndTails.bin"          # relative to AEON_ROOT
S3K_PLAYER_PAL = "General/Sprites/Sonic/Palettes/SonicAndTails.bin"  # rel. to skdisasm

# Pinned expectation for the S3K -> Aeon index permutation. NOT the input: the
# permutation is re-derived from the two palette files on every run and this
# table is asserted against it, so a palette edit on either side fails the build
# loudly instead of silently shifting Tails' colours.
PALETTE_REMAP_EXPECTED = {
    0: 0,  1: 6,  2: 5,  3: 3,
    4: 2,  6: 12, 7: 13, 8: 14,
    9: 15, 10: 10, 11: 11, 12: 4,
    13: 7, 14: 8, 15: 1,
}
# S3K index 5 ($0080, dark green) has no counterpart in our line 0. Tails uses it
# ZERO times, so the permutation is lossless for him; Knuckles uses it ~3,450
# times, which is why he cannot be bridged onto SonicTails' line this way
# (docs/DEFERRED_WORK.md).
S3K_UNMAPPABLE_INDEX = 5

# --- Knuckles' OWN-line permutation — the effect-dust fix ---------------------
# Knuckles keeps his own CRAM line 0 (he cannot be re-indexed onto SonicTails' —
# see above). But the shared effect-dust art (skid / spindash / belly-slide) draws
# on line 0 at indices 4/6/7 as grays, and line 0 is the PER-CHARACTER line, so
# those three slots must hold the SAME grays in the Knuckles palette as in
# SonicTails or the dust recolours to his reds (user screenshot). His grays sat at
# 12/1/13; this INVOLUTION swaps them into 4/6/7 (and the displaced colours back
# out), applied IDENTICALLY to his art and his palette so the swap is a pure
# relabel — lossless, nothing lost, no ROM-size delta. Identity elsewhere.
# games/sonic4/data/characters/knuckles_data.emp re-checks the invariant at build.
KNUCKLES_LINE_PERMUTE = {i: i for i in range(16)}
KNUCKLES_LINE_PERMUTE.update({4: 12, 12: 4, 6: 1, 1: 6, 7: 13, 13: 7})
# The line-0 slots the shared dust art draws through (index 0 = transparent).
DUST_SHARED_SLOTS = (4, 6, 7)


def permute_cram_line(data, table):
    """Relabel the first 16-entry CRAM line of `data` by `table`.

    Pairs with remap_art_indices, which sends pixel value i -> table[i]: for the
    displaced palette to still show the right colour, slot i must inherit the
    colour that used to live at table[i], i.e. new[i] = old[table[i]]. `table`
    must be a permutation of 0..15 (asserted); an involution round-trips cleanly.
    Only the first 32 bytes (line 0) are touched; any trailing lines pass through.
    """
    if len(data) < 32:
        raise AssertionError(f"palette too short to permute ({len(data)} bytes)")
    if sorted(table.keys()) != list(range(16)) or sorted(table.values()) != list(range(16)):
        raise AssertionError("permute_cram_line: table is not a permutation of 0..15")
    words = [struct.unpack_from('>H', data, i * 2)[0] for i in range(16)]
    out = bytearray(data)
    for i in range(16):
        struct.pack_into('>H', out, i * 2, words[table[i]])
    return bytes(out)


# ---------------------------------------------------------------------------
# Palette re-indexing  (S3K character-palette order -> Aeon CRAM line 0 order)
# ---------------------------------------------------------------------------

def _read_cram_line(path, line=0):
    """Read one 16-entry CRAM line (32 bytes) as big-endian words."""
    data = path.read_bytes()
    off = line * 32
    if len(data) < off + 32:
        raise AssertionError(f"{path}: too short for CRAM line {line} "
                             f"({len(data)} bytes)")
    return [struct.unpack_from('>H', data, off + i * 2)[0] for i in range(16)]


def derive_palette_remap(sk):
    """Derive S3K-index -> Aeon-index by matching CRAM words, and verify the pin.

    Returns (table, ours, s3k) where `table` maps every S3K index that HAS a
    counterpart in our line 0; indices with no match are absent from the dict.
    """
    ours = _read_cram_line(AEON_ROOT / AEON_PLAYER_PAL)
    s3k = _read_cram_line(sk / S3K_PLAYER_PAL)

    # Our line must be unambiguous, or "the matching index" is not well defined.
    dupes = {w for w in ours if ours.count(w) > 1}
    if dupes:
        raise AssertionError(
            f"{AEON_PLAYER_PAL} has duplicate CRAM words {sorted(dupes)} — the "
            "S3K->Aeon index match is ambiguous; the permutation cannot be derived")

    table = {}
    for si, word in enumerate(s3k):
        if word in ours:
            table[si] = ours.index(word)

    if table != PALETTE_REMAP_EXPECTED:
        raise AssertionError(
            "Derived S3K->Aeon palette permutation does not match the pinned "
            f"table.\n  derived : {dict(sorted(table.items()))}\n"
            f"  pinned  : {dict(sorted(PALETTE_REMAP_EXPECTED.items()))}\n"
            "One of the two palette files changed. Re-rule the mapping before "
            "regenerating — do NOT just repin.")
    if S3K_UNMAPPABLE_INDEX in table:
        raise AssertionError(
            f"S3K index {S3K_UNMAPPABLE_INDEX} now HAS a counterpart in our line 0 "
            "— the Knuckles caveat in docs/DEFERRED_WORK.md is stale and this "
            "generator's unmappable-index assert is meaningless. Re-rule.")
    return table, ours, s3k


def index_histogram(art):
    """Count occurrences of each 4bpp index. Genesis packs 2 px/byte, high first."""
    hist = [0] * 16
    for b in art:
        hist[b >> 4] += 1
        hist[b & 0x0F] += 1
    return hist


def remap_art_indices(art, table, tag):
    """Permute every 4bpp pixel index of `art` through `table`.

    Genesis 4bpp art is 2 pixels per byte, HIGH NIBBLE FIRST, so both nibbles of
    every byte are remapped independently. Pure permutation: output length ==
    input length, so no ROM-size or placement delta.

    HARD ASSERT: an index with no entry in `table` (i.e. a colour our CRAM line
    does not carry) is a LOSSY remap. Refuse rather than silently paint it wrong.
    """
    before = index_histogram(art)
    missing = [i for i, n in enumerate(before) if n and i not in table]
    if missing:
        raise AssertionError(
            f"{tag}: art uses S3K palette index/indices {missing} which have no "
            f"counterpart in {AEON_PLAYER_PAL} "
            f"(counts: {{{', '.join(f'{i}: {before[i]}' for i in missing)}}}). "
            "The permutation would be LOSSY — this art cannot be re-indexed and "
            "needs a real palette swap instead.")

    if len(set(table.values())) != len(table):
        raise AssertionError(f"{tag}: remap table is not injective — two S3K "
                             "colours would collapse onto one of ours")

    # Index 0 is TRANSPARENT on the VDP, so a remap that moved it would change
    # which pixels are drawn at all — silently, and it would take the ball-seating
    # derivation (which reads opacity out of this art) with it.
    if table.get(0) != 0:
        raise AssertionError(
            f"{tag}: remap sends index 0 -> {table.get(0)}. Index 0 is the VDP's "
            "transparent slot; permuting it changes the sprite's silhouette, not "
            "just its colours.")

    # 256-entry byte LUT indexed by the packed pixel pair. Unmapped indices only
    # ever reach here in byte positions the assert above proved do not occur.
    nib = [table.get(i, 0) for i in range(16)]
    out = art.translate(bytes((nib[hi] << 4) | nib[lo]
                              for hi in range(16) for lo in range(16)))

    after = index_histogram(out)
    for si, ai in table.items():
        if after[ai] != before[si]:
            raise AssertionError(f"{tag}: remap lost pixels at index {si}->{ai} "
                                 f"({before[si]} in, {after[ai]} out)")
    if sum(after) != sum(before) or len(out) != len(art):
        raise AssertionError(f"{tag}: remap changed the pixel/byte count")
    return out, before, after


# ---------------------------------------------------------------------------
# skdisasm .asm parsing  (dc.b / dc.w with pointer tables)
# ---------------------------------------------------------------------------

def _eval_num(tok):
    tok = tok.strip()
    if tok.startswith('$'):
        return int(tok[1:], 16)
    if tok.startswith('-'):
        return int(tok, 10) & 0xFF
    return int(tok, 10)


_LABEL_RE = re.compile(r'^(\w+):')
_DC_RE = re.compile(r'\bdc\.([bw])\s+(.*?)\s*(?:;.*)?$')
_PTR_RE = re.compile(r'\bdc\.w\s+(\w+)\s*-\s*\w+')


def parse_sprite_asm(path):
    """Parse an S3K sprite .asm (mappings / DPLC / anim).

    Returns (frame_order, label_bytes):
      frame_order  : list of label names in pointer-table order (== frame count)
      label_bytes  : {label_name: bytes}  fully-assembled big-endian body bytes
    """
    text = path.read_text(errors='replace')
    lines = text.splitlines()

    # Pointer table: the only `dc.w LABEL-BASE` lines in the file.
    frame_order = []
    for ln in lines:
        m = _PTR_RE.search(ln)
        if m:
            frame_order.append(m.group(1))

    # Label bodies: accumulate dc.b/.w bytes from a label's own line and the
    # following continuation lines until the next label. Pointer-table lines
    # (LABEL-BASE) are excluded so the base label's body stays empty.
    label_bytes = {}
    current = None
    buf = bytearray()

    def flush():
        nonlocal current, buf
        if current is not None:
            label_bytes[current] = bytes(buf)
        buf = bytearray()

    for ln in lines:
        stripped = ln.strip()
        lab = _LABEL_RE.match(ln)
        if lab:
            flush()
            current = lab.group(1)
            rest = ln[lab.end():]
        else:
            rest = ln
        if current is None:
            continue
        if _PTR_RE.search(rest):
            continue  # pointer-table entry, not body data
        dm = _DC_RE.search(rest)
        if dm:
            width = 1 if dm.group(1) == 'b' else 2
            for tok in dm.group(2).split(','):
                tok = tok.strip()
                if not tok:
                    continue
                val = _eval_num(tok)
                buf.extend(val.to_bytes(width, 'big', signed=False))
    flush()
    return frame_order, label_bytes


def frames_from_asm(path, kind):
    """Return per-frame structured data following the pointer table.

    kind 'map' : list of frames; frame = list of (y, size, tile, x)  (signed y/x)
    kind 'dplc': list of frames; frame = list of (tile_start, tile_count)
    kind 'anim': list of raw-byte scripts (bytes)
    """
    order, bodies = parse_sprite_asm(path)
    frames = []
    for lab in order:
        body = bodies.get(lab, b'')
        if kind == 'anim':
            frames.append(body)
            continue
        if len(body) < 2:
            frames.append([])
            continue
        count = struct.unpack_from('>H', body, 0)[0]
        pos = 2
        items = []
        if kind == 'map':
            for _ in range(count):
                y = struct.unpack_from('>b', body, pos)[0]
                size = body[pos + 1] & 0x0F
                tile = struct.unpack_from('>H', body, pos + 2)[0]
                x = struct.unpack_from('>h', body, pos + 4)[0]
                items.append((y, size, tile, x))
                pos += S3K_MAP_PIECE
        elif kind == 'dplc':
            for _ in range(count):
                word = struct.unpack_from('>H', body, pos)[0]
                tile_count = ((word >> 12) & 0xF) + 1
                tile_start = word & 0xFFF
                items.append((tile_start, tile_count))
                pos += 2
        frames.append(items)
    return frames


# ---------------------------------------------------------------------------
# Ball seating  —  owner ruling d-36 (2026-08-28): "they should all be flush"
# ---------------------------------------------------------------------------
#
# Stock S3K does NOT seat its three rolling balls consistently: measured against
# the shared 14 px ball radius, its Tails floats 1 px, its Sonic overlaps 1 and
# its Knuckles overlaps 1 (docs/CHARACTER_BOX_AUDIT.md §5 — the "+2" in the
# original audit was one stray pixel, see the body statistic below). Our Sonic's ball is
# S2 art and lands flush, which made the two S3K-sourced characters read as bugs
# beside him. The owner ruled that all three seat flush, so this generator moves
# the S3K balls onto the floor as it converts them.
#
# THE SHIFT IS DERIVED, NEVER TYPED. For each character:
#
#     shift = BALL_Y_RADIUS - max(lowest opaque art row, over the ball frames)
#
# Both inputs are read from source on every run: BALL_Y_RADIUS from
# engine/system/constants.emp, the ball frame list from the character's `Roll`
# animation row, and the pixels from the art + DPLC blobs this same run produces.
# So a radius change, an animation-table edit or a re-export of the art all
# re-derive the shift instead of silently invalidating a pinned number.
#
# WHY `max` AND NOT A PER-FRAME SHIFT. The ball frames of a character do NOT all
# have the same lowest opaque row — Knuckles' $96 reaches 1 px lower than his
# other four, and our (already-accepted, untouched) Sonic's $9A stops 1 px short
# of his other four. That variation is inside the drawn art; no rigid vertical
# shift of a whole frame can remove it, and shifting frames INDIVIDUALLY would
# change the ball's silhouette from frame to frame rather than seat it. `max` is
# the statistic our reference character already satisfies (Sonic: max lowest row
# 14 == BALL_Y_RADIUS 14, verified, not assumed), so adopting it makes the two
# S3K characters match the roster's own reference rather than a new invention.
# It means: the ball's deepest pixel rests exactly on the collision floor and no
# ball frame ever sinks into it.
#
# tools/test_ball_seating.py asserts the result on the SHIPPED blobs, measuring
# them with tools/measure_character_boxes.py's independent decoder.

# Where the ball frame list is read from, per generated set. A set absent from
# this table is not a playable character and is not seated (the Tails appendage:
# its roll frames are drawn at one of four runtime orientations selected from the
# parent's velocity angle, half of them with BOTH axes flipped, so a uniform
# mapping-space shift would move half of them the WRONG WAY on screen. Its
# seating is not a static property and is deliberately out of scope here).
BALL_ANIM_SOURCE = {
    "tails":    ("games/sonic4/data/animations/tails_anims.emp", "Ani_Tails"),
    "knuckles": ("games/sonic4/data/animations/knuckles_anims.emp", "Ani_Knuckles"),
}
# The animation row whose frames ARE the ball. Same name the engine's ANIM_ROLL
# ordinal binds and the same row measure_character_boxes.py maps to the roll box.
BALL_ANIM_STATE = "Roll"
BALL_RADIUS_SOURCE = ("engine/system/constants.emp", "BALL_Y_RADIUS")


def _frame_tiles(dplc_frame):
    """The frame's DPLC tile list — what a mapping piece's tile field indexes."""
    tiles = []
    for start, count in dplc_frame:
        tiles.extend(range(start, start + count))
    return tiles


def _row_profile(art, tiles, pieces, tag):
    """{row relative to y_pos: longest contiguous opaque run} for one frame.

    `pieces` are S3K-parsed (y, size, tile, x) with `size` the 4-bit VDP code and
    `tile` the raw attribute word (bit 11 xflip, bit 12 yflip). Index 0 is
    transparent. Raises if the frame draws nothing — a ball frame with no pixels
    is a broken conversion, not a zero.

    This is a SECOND decoder of the same pixels that
    measure_character_boxes.Character.row_profile decodes off the emitted blob.
    Keeping both is deliberate: the shift is derived here and re-measured there by
    tools/test_ball_seating.py, so the two must agree or the gate goes red.
    """
    cols = {}
    for y, size, attr, x in pieces:
        w = ((size >> 2) & 3) + 1
        h = (size & 3) + 1
        ti = attr & 0x7FF
        xflip = (attr >> 11) & 1
        yflip = (attr >> 12) & 1
        k = 0
        for cx in range(w):
            for cy in range(h):
                idx = ti + k
                k += 1
                if idx >= len(tiles):
                    raise AssertionError(
                        f"{tag}: mapping piece indexes DPLC entry {idx} but the "
                        f"frame's tile list holds {len(tiles)} — mappings and DPLC "
                        "are out of sync")
                base = tiles[idx] * TILE_SIZE
                t = art[base:base + TILE_SIZE]
                if len(t) < TILE_SIZE:
                    raise AssertionError(
                        f"{tag}: DPLC references tile {tiles[idx]} past the end of "
                        f"the art ({len(art) // TILE_SIZE} tiles)")
                for ry in range(8):
                    sy = cy * 8 + ry
                    if yflip:
                        sy = h * 8 - 1 - sy
                    for rx in range(8):
                        byte = t[ry * 4 + (rx >> 1)]
                        if not ((byte >> 4) if rx % 2 == 0 else (byte & 0x0F)):
                            continue
                        sx = cx * 8 + rx
                        if xflip:
                            sx = w * 8 - 1 - sx
                        cols.setdefault(y + sy, set()).add(x + sx)
    if not cols:
        raise AssertionError(f"{tag}: frame has no opaque pixels — cannot be seated")
    return {row: mcb.longest_run(c) for row, c in cols.items()}


def _body_bottom(art, tiles, pieces, tag):
    """(body row, its run, [(skipped spur row, its run), ...]) for one frame.

    The rule and the reason it is not `max(lowest opaque row)` live in
    measure_character_boxes.body_bottom_from_profile — shared, so the generator
    and the gate cannot drift onto two different definitions of "the ball body".
    """
    profile = _row_profile(art, tiles, pieces, tag)
    found = mcb.body_bottom_from_profile(profile)
    if found is None:
        raise AssertionError(
            f"{tag}: EVERY row of this frame is a spur under the body rule "
            f"(row profile {dict(sorted(profile.items()))}) — its geometry is not "
            "understood and it cannot be seated. Do not paper over this with a "
            "fallback to the lowest opaque row; that is the statistic the body "
            "rule exists to replace.")
    return found


def derive_ball_shift(name, map_frames, dplc_frames, art):
    """Derive the vertical shift that seats `name`'s ball on the collision floor.

    Returns (frames, shift, per_frame_body) or None if the set has no ball, where
    per_frame_body maps frame -> (body row, its run, skipped spurs). Every input
    is read from source; nothing here is a tuned constant.
    """
    src = BALL_ANIM_SOURCE.get(name)
    if src is None:
        return None
    anim_path, anim_table = src
    ball_y = mcb.read_const(*BALL_RADIUS_SOURCE)
    anims = mcb.read_anim_frames(anim_path, anim_table)
    if BALL_ANIM_STATE not in anims:
        raise AssertionError(
            f"{name}: `{anim_table}` in {anim_path} has no `{BALL_ANIM_STATE}` row "
            "with frame bytes — the ball frame list cannot be derived. Do NOT "
            "hardcode it; fix the table or the parser.")
    frames = sorted(set(anims[BALL_ANIM_STATE]))
    for f in frames:
        if f >= len(map_frames):
            raise AssertionError(
                f"{name}: `{BALL_ANIM_STATE}` names frame ${f:02X} but the converted "
                f"mapping set has only {len(map_frames)} frames — the .emp animation "
                "table and the S3K mapping source disagree on frame indexing")
    bodies = {f: _body_bottom(art, _frame_tiles(dplc_frames[f]),
                              map_frames[f], f"{name} ball frame ${f:02X}")
              for f in frames}
    # `max` over the cycle, of each frame's BODY bottom (spurs already removed).
    # max and not min: a frame whose ball is genuinely drawn a pixel shorter must
    # not lift the whole cycle off the floor — see Sonic's $9A in
    # docs/DEFERRED_WORK.md. It is only strays that max must not see, and the body
    # rule is what removes those before max ever runs.
    shift = ball_y - max(row for row, _run, _skipped in bodies.values())
    return frames, shift, bodies


def apply_ball_shift(map_frames, frames, shift):
    """Move each named frame's pieces by `shift` rows. In place."""
    for f in frames:
        map_frames[f] = [(y + shift, size, tile, x)
                         for (y, size, tile, x) in map_frames[f]]


# ---------------------------------------------------------------------------
# Aeon mapping emit  (mirror of tools/convert_s2_mappings.py)
# ---------------------------------------------------------------------------

def _cell_px(size_byte):
    w = (((size_byte >> 2) & 3) + 1) * 8
    h = ((size_byte & 3) + 1) * 8
    return w, h


def _compute_bbox(pieces, frame_index):
    if not pieces:
        return 0, 0, 0, 0
    x_min, x_max, y_min, y_max = 127, -128, 127, -128
    for y, size, _tile, x in pieces:
        w, h = _cell_px(size)
        x_min = min(x_min, x)
        x_max = max(x_max, x + w)
        y_min = min(y_min, y)
        y_max = max(y_max, y + h)
    # flip-invariant symmetrization (union of flipped/unflipped extents)
    x_min, x_max = min(x_min, -x_max), max(x_max, -x_min)
    y_min, y_max = min(y_min, -y_max), max(y_max, -y_min)
    for name, val in (('x_min', x_min), ('x_max', x_max),
                      ('y_min', y_min), ('y_max', y_max)):
        if val < -128 or val > 127:
            raise ValueError(f"Bbox {name}={val} (frame {frame_index}) exceeds "
                             "signed byte range [-128,127]")
    return x_min, x_max, y_min, y_max


def emit_mappings(map_frames):
    """map_frames -> Aeon VDP-order mapping binary (bbox header + 8-byte pieces)."""
    frame_count = len(map_frames)
    pointer_table_size = frame_count * 2
    parts = []
    offsets = []
    data_off = pointer_table_size
    for fi, pieces in enumerate(map_frames):
        offsets.append(data_off)
        x_min, x_max, y_min, y_max = _compute_bbox(pieces, fi)
        fb = struct.pack('bbbb', x_min, x_max, y_min, y_max)
        fb += struct.pack('>H', len(pieces))
        for y, size, tile, x in pieces:
            fb += struct.pack('>h', y)
            fb += struct.pack('BB', size, 0)
            fb += struct.pack('>H', tile)
            fb += struct.pack('>h', x)
        parts.append(fb)
        data_off += len(fb)
    out = bytearray()
    for off in offsets:
        out.extend(struct.pack('>H', off))
    for p in parts:
        out.extend(p)
    return bytes(out)


# ---------------------------------------------------------------------------
# DPLC / art emit  (mirror of tools/dplc_layout.py)
# ---------------------------------------------------------------------------

def split_contiguous_entries(start, count):
    entries = []
    while count > 0:
        chunk = min(count, MAX_TILES_PER_ENTRY)
        entries.append((start, chunk))
        start += chunk
        count -= chunk
    return entries


def build_contiguous_art(art_data, dplc_frames):
    """Rearrange art so each frame's tiles are contiguous; one entry per frame."""
    art_tiles = len(art_data) // TILE_SIZE
    new_art = bytearray()
    new_frames = []
    cursor = 0
    for entries in dplc_frames:
        total = sum(c for _, c in entries)
        if total == 0:
            new_frames.append((cursor, 0))
            continue
        frame_start = cursor
        for tstart, tcount in entries:
            for t in range(tcount):
                src = tstart + t
                if src < art_tiles:
                    tile = art_data[src * TILE_SIZE:(src + 1) * TILE_SIZE]
                else:
                    tile = b'\x00' * TILE_SIZE
                new_art.extend(tile)
                cursor += 1
        new_frames.append((frame_start, total))
    return bytes(new_art), new_frames


def write_dplc(frames):
    """Write DPLC in S2/S3K pointer-table format; assert <=16 tiles per entry."""
    frame_count = len(frames)
    parts = []
    offsets = []
    data_off = frame_count * 2
    for entries in frames:
        offsets.append(data_off)
        fb = struct.pack('>H', len(entries))
        for tstart, tcount in entries:
            assert 1 <= tcount <= MAX_TILES_PER_ENTRY, (
                f"DPLC tile_count={tcount} out of range 1..{MAX_TILES_PER_ENTRY} "
                f"(4-bit field wraps) at tile_start={tstart}")
            # tile_start is a TWELVE-bit field. The `& 0xFFF` below is a mask, not
            # a range check, so without this assert an art set larger than 4096
            # tiles wraps SILENTLY and those frames DMA early-frame art instead.
            # Knuckles is the first set to reach it: his contiguous ("_opt") art is
            # 4383 tiles, and 25 entries across frames 234-250 wrapped — a defect
            # invisible in the emitted file, since the wrap has already happened by
            # the time anyone parses it. Caught 2026-08-11 by reconstructing each
            # frame from both the raw and _opt pairs and diffing the results.
            assert 0 <= tstart <= 0xFFF, (
                f"DPLC tile_start={tstart} exceeds the 12-bit field (max 4095) — "
                f"the art set is larger than a DPLC entry can address, so this "
                f"entry would wrap to {tstart & 0xFFF} and load the wrong tiles")
            fb += struct.pack('>H', ((tcount - 1) & 0xF) << 12 | (tstart & 0xFFF))
        parts.append(fb)
        data_off += len(fb)
    out = bytearray()
    for off in offsets:
        out.extend(struct.pack('>H', off))
    for p in parts:
        out.extend(p)
    return bytes(out)


def assert_dplc_le16(frames, tag):
    for fi, entries in enumerate(frames):
        for tstart, tcount in entries:
            if not (1 <= tcount <= MAX_TILES_PER_ENTRY):
                raise AssertionError(
                    f"{tag} frame {fi}: DPLC entry tile_count={tcount} exceeds "
                    f"{MAX_TILES_PER_ENTRY}-tile hardware limit (start={tstart})")


# ---------------------------------------------------------------------------
# Animation intermediate JSON  (DEFERRED: .emp 11-id authoring = character plan)
# ---------------------------------------------------------------------------

def decode_anim(script):
    """Decode one S3K anim script to a structured, readable dict.

    Raw bytes are always preserved (raw_hex); the decode is a convenience view
    for the character plan and is NOT authoritative.
    """
    if not script:
        return {"empty": True, "raw_hex": ""}
    duration = script[0]
    frames = []
    terminator = None
    i = 1
    while i < len(script):
        b = script[i]
        if b >= AF_CTRL_THRESHOLD:
            nops = AF_OPERANDS.get(b, 0)
            ops = list(script[i + 1:i + 1 + nops])
            terminator = {
                "code": f"0x{b:02X}",
                "name": AF_NAME.get(b, f"0x{b:02X}"),
                "operands": ops,
            }
            i += 1 + nops
            # player scripts terminate at the first control code
            break
        frames.append(b)
        i += 1
    trailing = list(script[i:])
    out = {
        "duration": duration,
        "duration_note": ("DUR_DYNAMIC (speed-scaled)" if duration == 0xFF else None),
        "frames": frames,
        "frame_count": len(frames),
        "terminator": terminator,
        "raw_hex": script.hex(),
    }
    if trailing:
        out["trailing_bytes"] = trailing  # extra data after first terminator (rare)
    return out


def emit_anim_json(path, name, source_rel):
    order, _ = parse_sprite_asm(path)
    scripts = frames_from_asm(path, 'anim')
    anims = []
    for idx, (lab, script) in enumerate(zip(order, scripts)):
        entry = {"index": idx, "s3k_label": lab}
        entry.update(decode_anim(script))
        anims.append(entry)
    return {
        "character": name,
        "source": source_rel,
        "format": "s3k-raw",
        "note": ("Raw S3K animation scripts. Mapping to Aeon's 11 universal "
                 "ANIM_* ids + new ability anims (FLY/GLIDE/etc.) is a "
                 "character-plan authoring decision — DEFERRED. See README."),
        "anim_control_codes": {AF_NAME[k]: f"0x{k:02X}" for k in sorted(AF_NAME)},
        "anim_count": len(anims),
        "animations": anims,
    }


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def sha(b):
    return hashlib.sha256(b).hexdigest()[:16]


def process_set(sk, name, art_rel, map_rel, dplc_rel, anim_rel, out_dir, report,
                remap=None, optimize=True):
    art_path = sk / art_rel
    art = art_path.read_bytes()
    art_tiles = len(art) // TILE_SIZE
    src_art_sha = sha(art)

    # Palette re-index (Tails only — see module docstring). Applied to the RAW
    # art before the DPLC rearrange, so the staged raw and _opt blobs live in the
    # same colour space and either one can be re-optimised later.
    hist_before = hist_after = None
    if remap is not None:
        art, hist_before, hist_after = remap_art_indices(art, remap, name)

    map_frames = frames_from_asm(sk / map_rel, 'map')
    dplc_frames = frames_from_asm(sk / dplc_rel, 'dplc')

    if len(map_frames) != len(dplc_frames):
        raise AssertionError(
            f"{name}: mapping frame count {len(map_frames)} != "
            f"DPLC frame count {len(dplc_frames)} — sources out of sync")

    # Ball seating (owner ruling d-36) — derived from BALL_Y_RADIUS, the `Roll`
    # animation row and THIS art, then applied to the mapping frames before they
    # are emitted. See the "Ball seating" section above. Sets with no ball row in
    # BALL_ANIM_SOURCE pass through untouched.
    ball = derive_ball_shift(name, map_frames, dplc_frames, art)
    if ball is not None:
        ball_frames, ball_shift, ball_bodies = ball
        apply_ball_shift(map_frames, ball_frames, ball_shift)

    # Raw source DPLC (S3K pointer format) — provenance / re-optimizable.
    raw_dplc = write_dplc(dplc_frames)

    # Contiguous art + one-entry-per-frame DPLC (split to <=16). Build-consumed.
    #
    # `optimize=False` is for a set whose contiguous form does not FIT the format:
    # the rearrange makes the art strictly larger (every frame's tiles are copied
    # in full, duplicates and all), and once it passes 4096 tiles the 12-bit
    # tile_start can no longer address it. That is not a tuning knob — write_dplc
    # would refuse to emit it. Such a set ships its RAW pair, which is both correct
    # and smaller; the only cost is more DPLC entries per frame. Knuckles is the
    # first character to hit this (4383 contiguous tiles vs Tails' 3635).
    opt_art = opt_dplc = None
    opt_frames = []
    if optimize:
        opt_art, opt_single = build_contiguous_art(art, dplc_frames)
        opt_frames = [split_contiguous_entries(s, c) if c else [] for s, c in opt_single]
        assert_dplc_le16(opt_frames, name)
        opt_dplc = write_dplc(opt_frames)

    # Aeon VDP-order mappings.
    map_bin = emit_mappings(map_frames)

    (out_dir / "art").mkdir(parents=True, exist_ok=True)
    (out_dir / "mappings").mkdir(parents=True, exist_ok=True)
    (out_dir / "dplc").mkdir(parents=True, exist_ok=True)

    (out_dir / "art" / f"{name}.bin").write_bytes(art)                 # raw source art
    if opt_art is not None:
        (out_dir / "art" / f"{name}_opt.bin").write_bytes(opt_art)     # contiguous
    (out_dir / "mappings" / f"{name}.bin").write_bytes(map_bin)        # Aeon VDP-order
    (out_dir / "dplc" / f"{name}.bin").write_bytes(raw_dplc)           # S3K-format
    if opt_dplc is not None:
        (out_dir / "dplc" / f"{name}_opt.bin").write_bytes(opt_dplc)   # optimized <=16

    tiles_per_frame = [sum(c for _, c in f) for f in dplc_frames]
    max_entry_opt = max((c for f in opt_frames for _, c in f), default=0)
    report.append({
        "set": name,
        "frames": len(map_frames),
        "src_art_tiles": art_tiles,
        "src_art_bytes": len(art),
        "opt_art_tiles": (len(opt_art) // TILE_SIZE) if opt_art is not None else None,
        "opt_art_bytes": len(opt_art) if opt_art is not None else None,
        "max_tiles_per_frame": max(tiles_per_frame) if tiles_per_frame else 0,
        "max_opt_dplc_entry_tiles": max_entry_opt,
        "map_bin_bytes": len(map_bin),
        "src_art_sha": src_art_sha,
        "art_sha": sha(art),
        "opt_art_sha": sha(opt_art) if opt_art is not None else None,
        "map_sha": sha(map_bin),
        "opt_dplc_sha": sha(opt_dplc) if opt_dplc is not None else None,
        "optimized": opt_art is not None,
        "remapped": remap is not None,
        "hist_before": hist_before,
        "hist_after": hist_after,
        "ball_frames": [f"${f:02X}" for f in ball[0]] if ball else None,
        "ball_shift": ball[1] if ball else None,
        "ball_bodies": ({f"${f:02X}": {"body_row": row, "run": run,
                                       "spurs_skipped": skipped}
                         for f, (row, run, skipped) in ball[2].items()}
                        if ball else None),
        "ball_radius": mcb.read_const(*BALL_RADIUS_SOURCE) if ball else None,
    })


def main():
    sk = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SK
    out = Path(__file__).parent
    S = "General/Sprites"
    report = []

    # ---- Palette permutation (derived + pin-asserted, see module docstring) ----
    remap, ours_pal, s3k_pal = derive_palette_remap(sk)

    # ---- Tails body — RE-INDEXED into our CRAM line 0 order ----
    process_set(
        sk, "tails",
        f"{S}/Tails/Art/Tails.bin",
        f"{S}/Tails/Map - Tails.asm",
        f"{S}/Tails/DPLC - Tails.asm",
        f"{S}/Tails/Anim - Tails.asm",
        out / "tails", report, remap=remap)
    # ---- Tails appendage (the separate tail sprites, own object/art) ----
    #      Same palette line as the body, so the same re-index.
    process_set(
        sk, "tails_tail",
        f"{S}/Tails/Art/Tails tails.bin",
        f"{S}/Tails/Map - Tails tails.asm",
        f"{S}/Tails/DPLC - Tails tails.asm",
        f"{S}/Tails/Anim - Tails Tail.asm",
        out / "tails", report, remap=remap)
    # ---- Knuckles — NOT bridged onto SonicTails' line (he uses S3K index 5
    #      $0080, a colour that line does not carry), so he keeps his OWN CRAM
    #      line 0 and S3K swaps Pal_Knuckles in for him. He IS permuted within
    #      that line, though: KNUCKLES_LINE_PERMUTE swaps his grays into the
    #      shared effect-dust slots 4/6/7 (see the constant) — a lossless relabel
    #      of art + palette so the shared dust stays gray on him. optimize=False
    #      because his contiguous art overruns the DPLC's 12-bit tile_start (see
    #      below). See docs/DEFERRED_WORK.md. ----
    process_set(
        sk, "knuckles",
        f"{S}/Knuckles/Art/Knuckles.bin",
        f"{S}/Knuckles/Map - Knuckles.asm",
        f"{S}/Knuckles/DPLC - Knuckles.asm",
        f"{S}/Knuckles/Anim - Knuckles.asm",
        out / "knuckles", report, remap=KNUCKLES_LINE_PERMUTE, optimize=False)

    # ---- Animation intermediate JSON (deferred format decision) ----
    anim_specs = [
        ("tails",      out / "tails" / "anim" / "tails_anims.json",
         f"{S}/Tails/Anim - Tails.asm"),
        ("tails_tail", out / "tails" / "anim" / "tails_tail_anims.json",
         f"{S}/Tails/Anim - Tails Tail.asm"),
        ("knuckles",   out / "knuckles" / "anim" / "knuckles_anims.json",
         f"{S}/Knuckles/Anim - Knuckles.asm"),
    ]
    for name, jpath, rel in anim_specs:
        jpath.parent.mkdir(parents=True, exist_ok=True)
        obj = emit_anim_json(sk / rel, name, rel)
        jpath.write_text(json.dumps(obj, indent=2, sort_keys=False) + "\n")

    # ---- Palettes (copy; document sharing in README) ----
    # Main.bin is line-permuted the SAME way as his art (KNUCKLES_LINE_PERMUTE),
    # so his grays land in the shared effect-dust slots 4/6/7 and the shared dust
    # stays gray on him. Then assert those slots now equal SonicTails' — the exact
    # invariant knuckles_data.emp re-checks against the shipped blobs, caught here
    # first with the clearer message. SSZ End.bin is a cutscene palette, not
    # build-consumed, and is copied raw.
    pal_out = out / "palettes"
    pal_out.mkdir(parents=True, exist_ok=True)
    _knux_main = permute_cram_line(
        (sk / f"{S}/Knuckles/Palettes/Main.bin").read_bytes(), KNUCKLES_LINE_PERMUTE)
    _knux_words = [struct.unpack_from('>H', _knux_main, i * 2)[0] for i in range(16)]
    for _s in DUST_SHARED_SLOTS:
        if _knux_words[_s] != ours_pal[_s]:
            raise AssertionError(
                f"Knuckles line-0 slot {_s} = ${_knux_words[_s]:04X} after "
                f"KNUCKLES_LINE_PERMUTE, but SonicTails carries ${ours_pal[_s]:04X} "
                "there — the shared effect-dust slots no longer agree. The permute "
                "or one of the two source palettes changed; re-rule before shipping.")
    (pal_out / "knuckles_main.bin").write_bytes(_knux_main)
    (pal_out / "knuckles_ssz_end.bin").write_bytes(
        (sk / f"{S}/Knuckles/Palettes/SSZ End.bin").read_bytes())

    # ---- Ship the build-consumed trio into the real data dirs ----
    # These are the exact paths games/sonic4/data/characters/tails_data.emp
    # embeds. Shipping from here (rather than a hand `cp` after the fact) is what
    # makes this generator the single source of truth end to end: a regenerate
    # that changes a staged blob can no longer leave the ROM's copy stale.
    # Knuckles ships the RAW pair, NOT the `_opt` pair — the one place the two
    # characters deliberately differ. His contiguous art is 4383 tiles, past what
    # the DPLC's 12-bit tile_start can address, so `_opt` wrapped 25 entries across
    # frames 234-250 (see write_dplc's assert, which now refuses to emit it). The
    # raw pair addresses a max tile_start of 4070, is 8,702 bytes SMALLER, and its
    # only cost is up to 5 DMA entries per frame instead of 2 — well inside
    # DMA_IMPORTANT_SLOTS (12) and the same total 29 tiles either way.
    ship = []
    for src_rel, dst_rel in (
            ("tails/mappings/tails.bin",      "games/sonic4/data/mappings/tails.bin"),
            ("tails/dplc/tails_opt.bin",      "games/sonic4/data/dplc/optimized/tails.bin"),
            ("tails/art/tails_opt.bin",       "art/optimized/characters/tails.bin"),
            ("knuckles/mappings/knuckles.bin", "games/sonic4/data/mappings/knuckles.bin"),
            ("knuckles/dplc/knuckles.bin",     "games/sonic4/data/dplc/knuckles.bin"),
            ("knuckles/art/knuckles.bin",      "art/optimized/characters/knuckles.bin"),
            ("palettes/knuckles_main.bin",     "art/palettes/knuckles.bin"),
            ("tails/mappings/tails_tail.bin", "games/sonic4/data/mappings/tails_tail.bin"),
            ("tails/dplc/tails_tail_opt.bin", "games/sonic4/data/dplc/optimized/tails_tail.bin"),
            ("tails/art/tails_tail_opt.bin",  "art/optimized/characters/tails_tail.bin")):
        src = out / src_rel
        dst = AEON_ROOT / dst_rel
        data = src.read_bytes()
        changed = (not dst.exists()) or dst.read_bytes() != data
        if changed:
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(data)
        ship.append((dst_rel, len(data), changed))

    # ---- Summary report ----
    print("=" * 74)
    print("S3K Tails + Knuckles asset staging — summary")
    print("=" * 74)

    print("\n[palette re-index]  S3K character line 0 -> Aeon CRAM line 0")
    print(f"  ours: {AEON_PLAYER_PAL}")
    print(f"  s3k : {S3K_PLAYER_PAL}")
    print("  s3k  ->  aeon   (matched by CRAM word)")
    for si in range(16):
        tgt = f"{remap[si]:2d}  ${ours_pal[remap[si]]:04X}" if si in remap else \
              "--  UNMAPPABLE (colour absent from our line)"
        print(f"   {si:2d}  ${s3k_pal[si]:04X}  ->  {tgt}")

    for r in report:
        print(f"\n[{r['set']}]")
        print(f"  frames                 : {r['frames']}")
        print(f"  source art             : {r['src_art_tiles']} tiles "
              f"({r['src_art_bytes']:,} bytes)  sha={r['src_art_sha']}")
        if r['remapped']:
            print(f"  re-indexed art         : sha={r['art_sha']} "
                  f"(size unchanged — pure nibble permutation)")
            print(f"    index hist before    : "
                  f"{ {i: n for i, n in enumerate(r['hist_before']) if n} }")
            print(f"    index hist after     : "
                  f"{ {i: n for i, n in enumerate(r['hist_after']) if n} }")
        else:
            print(f"  art                    : raw S3K copy (NOT re-indexed)  "
                  f"sha={r['art_sha']}")
        if r.get("optimized", True):
            print(f"  contiguous (opt) art   : {r['opt_art_tiles']} tiles "
                  f"({r['opt_art_bytes']:,} bytes)  sha={r['opt_art_sha']}")
            print(f"  max opt DPLC entry     : {r['max_opt_dplc_entry_tiles']} tiles "
                  f"(<= {MAX_TILES_PER_ENTRY} asserted)")
        else:
            print(f"  contiguous (opt) art   : NOT BUILT — the contiguous form "
                  f"exceeds the DPLC's 12-bit tile_start; ships the RAW pair")
        print(f"  max tiles / frame      : {r['max_tiles_per_frame']} "
              f"(pre-split)")
        print(f"  Aeon mappings          : {r['map_bin_bytes']:,} bytes  "
              f"sha={r['map_sha']}")
        if r['ball_shift'] is not None:
            b = r['ball_bodies']
            print(f"  ball seating           : frames {' '.join(r['ball_frames'])}  "
                  f"shift {r['ball_shift']:+d} px")
            print(f"    derived as           : BALL_Y_RADIUS {r['ball_radius']} - "
                  f"max(BODY bottom row) = {r['ball_shift']:+d}")
            for fk, v in b.items():
                spur = ("  SPURS SKIPPED: "
                        + ", ".join(f"row {sr:+d} (run {srun} px)"
                                    for sr, srun in v['spurs_skipped'])
                        ) if v['spurs_skipped'] else ""
                print(f"      {fk}  body row {v['body_row']:+d}  "
                      f"run {v['run']:2d} px{spur}")
    for name, jpath, _ in anim_specs:
        obj = json.loads(jpath.read_text())
        print(f"\n[{name} anims]  {obj['anim_count']} scripts -> "
              f"{jpath.relative_to(out)}")
    print("\n[shipped — build-consumed copies]")
    for dst_rel, size, changed in ship:
        print(f"  {'UPDATED' if changed else 'same   '}  {dst_rel}  ({size:,} B)")

    print("\nDPLC <=16-tile invariant   : PASS (asserted per set above)")
    print(f"Palette permutation pin    : PASS (derived == pinned, {len(remap)} indices)")
    print(f"S3K index {S3K_UNMAPPABLE_INDEX} in Tails' art : 0 occurrences "
          "(asserted — remap is lossless)")
    print("=" * 74)


if __name__ == '__main__':
    main()
