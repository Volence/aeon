#!/usr/bin/env python3
"""s2_donor.py — the Sonic 2 donor loaders, for BOTH Sonic 2 donor trees.

WHAT THIS IS. One place that turns a Sonic 2 zone, in EITHER donor checkout,
into the things aeon's build-time pipeline eats: a foreground nametable-word
grid, the art blob those words index, the 16x16 / 128x128 mapping tables, the
per-path collision indices, and the palette. The donor is named explicitly on
every call — there is no default and no "current" donor, because the two trees
disagree about nearly every file format and a silent fall-back between them
would read one game's bytes and label them the other's.

THE TWO DONORS

  s2disasm            the FINAL Sonic 2 (REV01) disassembly. Nine zones are
                      registered. This is the tree every number in
                      `docs/research/2026-09-17-s2-compressed-act-design.md`
                      was measured through.

  s2-simonwai-disasm  the SIMON WAI PROTOTYPE disassembly. Ten zones. It is the
                      ONLY source of Hidden Palace Zone level data — the final
                      game ships HPZ's palette and music and NO layout, no
                      mappings, no art and no collision (design doc §6). Cloned
                      read-only on the owner's ruling, 2026-09-17.

WHERE THIS CAME FROM. `megaact_window_pageset._load_s2` was the working S2
loader (8 zones) and `docs/research/s2-compressed-act/s2_clip_budget.py` carried
a monkey-patched WFZ row on top of it. Both are gone: this module is the one
loader, and the WFZ row is a registry entry rather than a patch. The promotion is
row 1 of the design's §10 staged plan, and its falsifiable check is that the nine
final-game grids come out byte for byte identical to what the measurement tool
produced before the move.

HOW THE PROTOTYPE'S FORMATS DIFFER FROM THE FINAL GAME'S — every line of this
was re-derived from the prototype's own `main.asm`, not assumed:

  layout       .bin, UNCOMPRESSED, and a DIFFERENT SHAPE. Two header bytes
               (width-1, height-1 in 128px chunks) then width*height chunk ids,
               row major. `Interleave_Level_Layout` (main.asm:7930) tiles each
               row ($80 div width) times across the 128-byte RAM row, so a
               narrow layout REPEATS horizontally — it is not zero-padded.
               Foreground and background are SEPARATE FILES (`GHZ_1.bin` /
               `GHZ_BG.bin`), where the final game interleaves them in one
               $1000-byte Kosinski blob. Every foreground layout here is
               128x16, i.e. the same grid the final game's FG rows form.
  16x16 maps   .bin, UNCOMPRESSED (the final game Kosinski-compresses them).
               Same 4-words-per-block content; copied straight to Block_Table
               by main.asm:7816.
  128x128 maps .kos, Kosinski — SAME as the final game. `GHZ and HTZ.kos` is
               shared by two zones, the way `EHZ_HTZ.kos` is in the final game.
  art          .nem, NEMESIS — the final game uses Kosinski. There is no
               `art/kosinski/` directory in the prototype at all. Hence
               `nem_decompress()` below.
  collision    indices are .bin, UNCOMPRESSED, 768 bytes, one byte per block
               (the final game Kosinski-compresses the same shape). The shape
               banks are named `Collision array 1.bin` / `Collision array 2.bin`
               and the angle table `Curve and resistance mappings.bin` (plural).
               MEASURED: `Collision array 1.bin` is BYTE-IDENTICAL to the final
               game's `Collision array - Vertical.bin`, `Collision array 2.bin`
               to `Collision array - Horizontal.bin`, and the angle table to
               `Curve and resistance mapping.bin`. The two games share one
               collision-shape vocabulary.
  chunk word   IDENTICAL to the final game: bits 9:0 block id (main.asm:7304
               `andi.w #$3FF`), bit 10 X-flip and bit 11 Y-flip (main.asm:7534
               `btst #3`/`btst #2` on the high byte), bits 13:12 path-A
               solidity and 15:14 path-B (constants.asm:70-71, "either $C or $E"
               / "$D or $F"). `collision_pipeline.bake_cell` applies unchanged.
  LevelSize    a DIFFERENT TABLE SHAPE: 4 longs per zone, two per act, each long
               packing (min,max) as two words -> (xstart, xend, ystart, yend),
               the same four numbers the final game's `zoneTableEntry.w` row
               carries. HPZ's row is the placeholder $3FFF/$0720, exactly as
               WFZ's is in the final game, so an HPZ clip must be taken from the
               PAINTED bounding box and not the camera box.

Donor roots resolve through `suite_paths` (or the per-donor environment
variable), never a literal path.

Usage:
    python3 tools/s2_donor.py zones --donor s2disasm
    python3 tools/s2_donor.py zones --donor s2-simonwai-disasm
    python3 tools/s2_donor.py selfcheck        # both donors, every zone
"""

from __future__ import annotations

import argparse
import os
import re
import struct
import sys

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))

import ojz_common                                   # noqa: E402
import ojz_strip_gen                                # noqa: E402
from suite_paths import require_suite_path          # noqa: E402

__all__ = [
    "S2_FINAL", "S2_PROTOTYPE", "DONORS",
    "donor_root", "donor_env_var", "donor_role", "donor_dirname",
    "zone_names", "zone_row", "known_zone",
    "Zone", "chunk_tiles", "crop_to_box",
    "load_zone", "load_art", "load_blocks", "load_chunks", "load_fg_grid",
    "level_size", "palette_path", "art_sources",
    "collision_inputs", "collision_arrays",
    "nem_decompress", "read_bytes",
    "parse_level_sizes", "parse_s2_constant",
]

# ---------------------------------------------------------------------------
# Donors
# ---------------------------------------------------------------------------

#: The final Sonic 2 (REV01) disassembly.
S2_FINAL = "s2disasm"
#: The Simon Wai prototype disassembly — the only source of Hidden Palace Zone.
S2_PROTOTYPE = "s2-simonwai-disasm"

DONORS = (S2_FINAL, S2_PROTOTYPE)

#: Per-donor: the directory under the suite root, the `<TOOL>_DIR`-style escape
#: hatch, the file that proves the directory IS that donor, and the role string
#: `donor_provenance` stamps. Two donors, two variables: one variable naming
#: "the S2 donor" would let a prototype checkout answer for the final game.
_DONOR = {
    S2_FINAL: {
        "dirname": "s2disasm",
        "env": "AEON_S2DISASM_DIR",
        "marker": "s2.asm",
        "what": "Sonic 2 donor disassembly",
        "role": "Sonic 2 final-game level layouts, Kosinski art, chunk+block "
                "maps, collision indices, palettes",
    },
    S2_PROTOTYPE: {
        "dirname": "s2-simonwai-disasm",
        "env": "AEON_S2PROTO_DIR",
        "marker": "main.asm",
        "what": "Sonic 2 Simon Wai prototype disassembly (Hidden Palace donor)",
        "role": "Sonic 2 Simon Wai prototype level layouts, Nemesis art, "
                "chunk+block maps, collision indices, palettes — the only "
                "source of Hidden Palace Zone",
    },
}


def _donor(donor: str) -> dict:
    try:
        return _DONOR[donor]
    except KeyError:
        raise SystemExit(
            f"unknown S2 donor {donor!r} — name one of {', '.join(DONORS)} "
            f"explicitly (there is no default donor: the two trees disagree "
            f"about every file format)") from None


def donor_dirname(donor: str) -> str:
    """The donor's directory name under the suite root."""
    return _donor(donor)["dirname"]


def donor_env_var(donor: str) -> str:
    """The environment variable that relocates this donor's checkout."""
    return _donor(donor)["env"]


def donor_role(donor: str) -> str:
    """What this donor contributes, for `donor_provenance`'s record."""
    return _donor(donor)["role"]


def donor_root(donor: str) -> str:
    """Resolve a donor checkout, REFUSING by name rather than guessing.

    `<VAR>` first (the contract's step 1 shape, as `suite_paths` documents it):
    set-but-not-a-directory, and set-but-not-that-donor, are hard errors here
    and never fall through to the suite root — a fall-through would let the
    wrong tree answer during exactly the runs the variable exists to redirect.
    """
    d = _donor(donor)
    env = os.environ.get(d["env"])
    if env:
        if not os.path.isdir(env):
            raise SystemExit(f"{d['env']}={env} is not a directory")
        if not os.path.isfile(os.path.join(env, d["marker"])):
            raise SystemExit(
                f"{d['env']}={env} is not the {donor} checkout: no {d['marker']}")
        return env
    root = str(require_suite_path(d["dirname"], what=d["what"]))
    if not os.path.isfile(os.path.join(root, d["marker"])):
        raise SystemExit(
            f"{root} is not the {donor} checkout: no {d['marker']} "
            f"(set {d['env']} to the real one)")
    return root


def read_bytes(path: str) -> bytes:
    with open(path, "rb") as fh:
        return fh.read()


_asm_cache: dict[tuple[str, str], str] = {}


def _asm(donor: str, name: str) -> str:
    """The donor's assembly source, memoised. Read-only; never written."""
    key = (donor, name)
    if key not in _asm_cache:
        with open(os.path.join(donor_root(donor), name), "r", errors="replace") as fh:
            _asm_cache[key] = fh.read()
    return _asm_cache[key]


def _main_asm(donor: str) -> str:
    return _asm(donor, _donor(donor)["marker"])


# ---------------------------------------------------------------------------
# Zone registry
# ---------------------------------------------------------------------------
#
# FINAL. Cross-read from `s2.asm` `LevelArtPointers` (levartptrs rows) and the
# `BM16_*:/ArtKos_*:/BM128_*: BINCLUDE` block; the collision columns from
# `Off_ColP`/`Off_ColS` (s2.asm:5915-5960). Every BINCLUDE spelling is re-checked
# against s2.asm at load time, so a renamed donor file fails loudly instead of
# silently loading the wrong zone.
#
#   art       art/kosinski/<art>.kos
#   blocks    mappings/16x16/<blocks>.kos
#   chunks    mappings/128x128/<chunks>.kos
#   layout    level/layout/<layout>.kos
#   size_key  the zone name `LevelSize:`'s comment rows use
#   coll_p/s  collision/<name>.kos; coll_s None => the zone has no real second
#             path and Off_ColS points at the primary
#   art_supp  (file, constant) — a supplementary art blob overlaid at
#             `constant` tiles into the base blob, the way s2.asm's KosDec to
#             `Chunk_Table+tiles_to_bytes(...)` does it
#   block_patch  the BM16 blob patched into Block_Table at a fixed offset
#
_FINAL_ZONES = {
    "EHZ": dict(art="EHZ_HTZ", blocks="EHZ", chunks="EHZ_HTZ", layout="EHZ_1",
                size_key="EHZ", palette="EHZ",
                coll_p="EHZ and HTZ primary 16x16 collision index.kos",
                coll_s="EHZ and HTZ secondary 16x16 collision index.kos"),
    "HTZ": dict(art="EHZ_HTZ", blocks="EHZ", chunks="EHZ_HTZ", layout="HTZ_1",
                size_key="HTZ", palette="HTZ",
                coll_p="EHZ and HTZ primary 16x16 collision index.kos",
                coll_s="EHZ and HTZ secondary 16x16 collision index.kos",
                art_supp=("HTZ_Supp", "ArtTile_ArtKos_NumTiles_HTZ_Main"),
                block_patch="HTZ"),
    "CPZ": dict(art="CPZ_DEZ", blocks="CPZ_DEZ", chunks="CPZ_DEZ", layout="CPZ_1",
                size_key="CPZ", palette="CPZ",
                coll_p="CPZ and DEZ primary 16x16 collision index.kos",
                coll_s="CPZ and DEZ secondary 16x16 collision index.kos"),
    "ARZ": dict(art="ARZ", blocks="ARZ", chunks="ARZ", layout="ARZ_1",
                size_key="ARZ", palette="ARZ",
                coll_p="ARZ primary 16x16 collision index.kos",
                coll_s="ARZ secondary 16x16 collision index.kos"),
    "CNZ": dict(art="CNZ", blocks="CNZ", chunks="CNZ", layout="CNZ_1",
                size_key="CNZ", palette="CNZ",
                coll_p="CNZ primary 16x16 collision index.kos",
                coll_s="CNZ secondary 16x16 collision index.kos"),
    "MCZ": dict(art="MCZ", blocks="MCZ", chunks="MCZ", layout="MCZ_1",
                size_key="MCZ", palette="MCZ",
                coll_p="MCZ primary 16x16 collision index.kos", coll_s=None),
    "OOZ": dict(art="OOZ", blocks="OOZ", chunks="OOZ", layout="OOZ_1",
                size_key="OOZ", palette="OOZ",
                coll_p="OOZ primary 16x16 collision index.kos", coll_s=None),
    "MTZ": dict(art="MTZ", blocks="MTZ", chunks="MTZ", layout="MTZ_1",
                size_key="MTZ", palette="MTZ",
                coll_p="MTZ primary 16x16 collision index.kos", coll_s=None),
    # WFZ — the row `megaact_window_pageset.S2_ZONES` never had, and the reason
    # `s2_clip_budget.py` carried a monkey patch. Art is SCZ's blob with
    # WFZ_Supp overlaid at ArtTile_ArtKos_NumTiles_WFZ_Main (s2.asm:6492-6495,
    # s2.constants.asm:2305), and the layout file is `WFZ.kos`, not `WFZ_1.kos`.
    # Its `LevelSize` row is the placeholder $3FFF (s2.asm:14718): the camera box
    # is the full 16,384 px and a WFZ clip must come from the PAINTED bounding
    # box instead (design doc §3.1).
    "WFZ": dict(art="WFZ_SCZ", blocks="WFZ_SCZ", chunks="WFZ_SCZ", layout="WFZ",
                size_key="WFZ", palette="WFZ",
                coll_p="WFZ and SCZ primary 16x16 collision index.kos",
                coll_s="WFZ and SCZ secondary 16x16 collision index.kos",
                art_supp=("WFZ_Supp", "ArtTile_ArtKos_NumTiles_WFZ_Main")),
}

#
# PROTOTYPE. Cross-read from the prototype's `LevelArtPointers`
# (main.asm:34667-34683), its layout label block (:35614-35726), `Off_ColP` /
# `Off_ColS` (:4189-4237) and the `Pal_<ZONE>:` bincludes (:2377-2401).
#
#   art       art/nemesis/<art>.nem          (NEMESIS, not Kosinski)
#   blocks    mappings/16x16/<blocks>.bin    (UNCOMPRESSED, not Kosinski)
#   chunks    mappings/128x128/<chunks>.kos  (Kosinski, as in the final game)
#   layout    level/layout/<layout>.bin      (UNCOMPRESSED, 2-byte header)
#   zone_id   the row index in LevelSize / LevelArtPointers
#   coll_p/s  collision/<name>.bin           (UNCOMPRESSED, 768 bytes)
#
_PROTO_ZONES = {
    "GHZ": dict(art="GHZ and HTZ primary", blocks="GHZ", chunks="GHZ and HTZ",
                layout="GHZ_1", zone_id=0x00, palette="GHZ",
                coll_p="GHZ primary 16x16 collision index.bin",
                coll_s="GHZ secondary 16x16 collision index.bin"),
    "WZ":  dict(art="WZ primary", blocks="WZ", chunks="WZ",
                layout="WZ_1", zone_id=0x02, palette="WZ",
                coll_p="WZ 16x16 collision index.bin", coll_s=None),
    "MTZ": dict(art="MTZ primary", blocks="MTZ", chunks="MTZ",
                layout="MTZ_1", zone_id=0x04, palette="MTZ",
                coll_p="MTZ 16x16 collision index.bin", coll_s=None),
    # HTZ reuses GHZ's art and blocks and patches both, exactly as the final
    # game's HTZ does — a supplementary Nemesis blob at the VRAM address its
    # PLC list names, and BM16_HTZ over Block_Table+$980.
    "HTZ": dict(art="GHZ and HTZ primary", blocks="GHZ", chunks="GHZ and HTZ",
                layout="HTZ_1", zone_id=0x07, palette="HTZ",
                coll_p="GHZ primary 16x16 collision index.bin",
                coll_s="GHZ secondary 16x16 collision index.bin",
                art_supp=("HTZ secondary", "Hill_Top_Sprites_1", "ArtNem_HTZ"),
                block_patch="HTZ"),
    # The whole reason this donor exists.
    "HPZ": dict(art="HPZ primary", blocks="HPZ", chunks="HPZ",
                layout="HPZ_1", zone_id=0x08, palette="HPZ",
                coll_p="HPZ primary 16x16 collision index.bin",
                coll_s="HPZ secondary 16x16 collision index.bin"),
    "OOZ": dict(art="OOZ primary", blocks="OOZ", chunks="OOZ",
                layout="OOZ_1", zone_id=0x0A, palette="OOZ",
                coll_p="OOZ 16x16 collision index.bin", coll_s=None),
    "DHZ": dict(art="DHZ primary", blocks="DHZ", chunks="DHZ",
                layout="DHZ_1", zone_id=0x0B, palette="DHZ",
                coll_p="DHZ 16x16 collision index.bin", coll_s=None),
    "CNZ": dict(art="CNZ primary", blocks="CNZ", chunks="CNZ",
                layout="CNZ_1", zone_id=0x0C, palette="CNZ",
                coll_p="CNZ primary 16x16 collision index.bin",
                coll_s="CNZ secondary 16x16 collision index.bin"),
    "CPZ": dict(art="CPZ primary", blocks="CPZ", chunks="CPZ",
                layout="CPZ_1", zone_id=0x0D, palette="CPZ",
                coll_p="CPZ primary 16x16 collision index.bin",
                coll_s="CPZ secondary 16x16 collision index.bin"),
    "NGHZ": dict(art="NGHZ primary", blocks="NGHZ", chunks="NGHZ",
                 layout="NGHZ_1", zone_id=0x0F, palette="NGHZ",
                 coll_p="NGHZ primary 16x16 collision index.bin",
                 coll_s="NGHZ secondary 16x16 collision index.bin"),
}

_REGISTRY = {S2_FINAL: _FINAL_ZONES, S2_PROTOTYPE: _PROTO_ZONES}


def zone_names(donor: str) -> list[str]:
    """Every zone this donor can load, sorted."""
    return sorted(_REGISTRY[_donor(donor) and donor])


def known_zone(zone: str, donor: str) -> bool:
    return zone in _REGISTRY[_donor(donor) and donor]


def zone_row(zone: str, donor: str) -> dict:
    """The registry row, refusing by name for an unregistered zone."""
    reg = _REGISTRY[_donor(donor) and donor]
    if zone not in reg:
        raise SystemExit(
            f"{donor} has no registry row for zone {zone!r} — known: "
            f"{', '.join(sorted(reg))}")
    return reg[zone]


# ---------------------------------------------------------------------------
# Nemesis — the prototype's level-art codec
# ---------------------------------------------------------------------------

def nem_decompress(data: bytes) -> bytes:
    """Decompress a Nemesis stream (the prototype donor's level art).

    Header word: bit 15 = XOR (delta) mode, bits 14:0 = TILE count; each tile is
    8 rows of 8 nibbles, so the output is `tiles * 32` bytes. Then a code table
    of (palette-index marker | length+repeat descriptor, code) entries ending at
    $FF, then the bit stream. The 6-bit code $3F is the inline escape: 3 repeat
    bits then a 4-bit nibble.

    Aeon's engine has no Nemesis decoder and will never gain one (the ARCH ruling
    removed Enigma/Nemesis/Kosinski/UFTC from the runtime). This is a BUILD-TIME
    donor reader and nothing else.

    VERIFIED against clownnemesis v1.1.1 (`sonic_hack/tools/nemdec -d`) over all
    283 `.nem` files in the two donors — 79 in the prototype, 204 in s2disasm —
    byte for byte, 0 mismatches (2026-09-17). The check lives in
    `tools/test_s2_donor.py::test_nemesis_matches_the_reference_decoder`, which
    runs it over the committed fixtures when the reference binary is present and
    is LOUD (not skipped-green) when it is not.
    """
    if len(data) < 3:
        raise ValueError("nemesis: stream shorter than its header")
    hdr = struct.unpack_from(">H", data, 0)[0]
    xor = bool(hdr & 0x8000)
    rows = (hdr & 0x7FFF) * 8          # 8 pixel rows per tile
    pos = 2

    table: dict[tuple[int, int], tuple[int, int]] = {}
    pal = 0
    b = data[pos]
    pos += 1
    while b != 0xFF:
        if b & 0x80:
            pal = b & 0x0F
            b = data[pos]
            pos += 1
        table[(b & 0x0F, data[pos])] = (pal, (b >> 4) & 7)
        pos += 1
        b = data[pos]
        pos += 1

    stream = data[pos:]
    bitpos = 0

    def getbit() -> int:
        nonlocal bitpos
        if (bitpos >> 3) >= len(stream):
            raise ValueError("nemesis: bit stream exhausted before the tile count")
        v = (stream[bitpos >> 3] >> (7 - (bitpos & 7))) & 1
        bitpos += 1
        return v

    def getbits(n: int) -> int:
        v = 0
        for _ in range(n):
            v = (v << 1) | getbit()
        return v

    out = bytearray()
    prev = row = nib = written = code = clen = 0
    while written < rows:
        code = (code << 1) | getbit()
        clen += 1
        if clen == 6 and code == 0x3F:
            rep, val = getbits(3), getbits(4)
            code = clen = 0
        elif (clen, code) in table:
            val, rep = table[(clen, code)]
            code = clen = 0
        elif clen > 8:
            raise ValueError("nemesis: no code matched within 8 bits")
        else:
            continue
        for _ in range(rep + 1):
            row = ((row << 4) | val) & 0xFFFFFFFF
            nib += 1
            if nib == 8:
                if xor:
                    row ^= prev
                out += struct.pack(">I", row)
                prev, row, nib = row, 0, 0
                written += 1
                if written >= rows:
                    break
    return bytes(out)


# ---------------------------------------------------------------------------
# Source-derived facts: LevelSize tables, constants, palette filenames
# ---------------------------------------------------------------------------

def parse_level_sizes(s2asm_text: str) -> dict:
    """{(zone, act): (xstart, xend, ystart, yend)} from s2.asm `LevelSize:`.

    FINAL DONOR ONLY — the prototype's table is a different shape (see
    `_parse_proto_level_sizes`).
    """
    start = s2asm_text.index("\nLevelSize:")
    end = s2asm_text.index("zoneTableEnd", start)
    zone = None
    acts = {}
    for line in s2asm_text[start:end].splitlines()[1:]:
        m = re.match(r"^\s*;\s*([A-Za-z0-9 ]+?)\s*$", line)
        if m:
            zone = m.group(1).strip()
            continue
        m = re.match(r"^\s*zoneTableEntry\.w\s+(.+?);\s*Act\s+(\d+)", line)
        if m:
            vals = [int(v.strip().replace("$", "0x").replace("-0x", "-0x"), 0)
                    for v in m.group(1).split(",")]
            acts[(zone, int(m.group(2)))] = tuple(vals)
    if ("EHZ", 1) not in acts:
        raise SystemExit("could not parse s2.asm LevelSize table")
    return acts


def _parse_proto_level_sizes(main_text: str) -> dict:
    """{(zone_id, act): (xstart, xend, ystart, yend)} from the prototype's
    `LevelSize:` (main.asm:4919).

    Shape, read off `LevelSizeLoad` (main.asm:4897-4906): the index is
    `(zone << 4) | (act ? 8 : 0)`, so 16 bytes per zone and 8 per act, and each
    act's 8 bytes are two longs each packing a (min, max) word pair —
    `move.l (a0)+,d0 / move.l d0,(Camera_Min_X_pos)` writes Camera_Min_X_pos AND
    Camera_Max_X_pos in one move. That unpacks to the same four numbers the
    final game's `zoneTableEntry.w xstart, xend, ystart, yend` row carries.
    """
    start = main_text.index("\nLevelSize:")
    end = main_text.index("zoneTableEnd", start)
    out = {}
    for line in main_text[start:end].splitlines()[1:]:
        m = re.match(r"^\s*zoneTableEntry\.l\s+(.+?);\s*\$([0-9A-Fa-f]{2})", line)
        if not m:
            continue
        longs = [int(v.strip().replace("$", "0x"), 0) for v in m.group(1).split(",")]
        if len(longs) != 4:
            raise SystemExit(
                f"prototype LevelSize row for zone ${m.group(2)} has "
                f"{len(longs)} longs, expected 4")
        zid = int(m.group(2), 16)
        for act in (1, 2):
            xx, yy = longs[(act - 1) * 2], longs[(act - 1) * 2 + 1]
            out[(zid, act)] = (xx >> 16, xx & 0xFFFF, yy >> 16, yy & 0xFFFF)
    if (0x00, 1) not in out:
        raise SystemExit("could not parse the prototype's LevelSize table")
    return out


def parse_s2_constant(text: str, name: str) -> int:
    m = re.search(rf"^{name}\s*=\s*\$([0-9A-Fa-f]+)", text, re.M)
    if not m:
        raise SystemExit(f"s2.constants.asm no longer defines {name}")
    return int(m.group(1), 16)


def level_size(zone: str, donor: str, act: int = 1) -> tuple[int, int, int, int]:
    """(xstart, xend, ystart, yend) — the act's camera box, in pixels."""
    row = zone_row(zone, donor)
    if donor == S2_FINAL:
        return parse_level_sizes(_main_asm(donor))[(row["size_key"], act)]
    return _parse_proto_level_sizes(_main_asm(donor))[(row["zone_id"], act)]


#: A `LevelSize` row of $3FFF (final) / $3FFF (prototype) is a placeholder the
#: game never uses as a camera bound; a clip of such a zone MUST come from the
#: painted bounding box. WFZ (final) and HPZ, WZ, MTZ, CNZ, DEZ... (prototype)
#: carry it.
CAMERA_BOX_PLACEHOLDER_XEND = 0x3FFF


def palette_path(zone: str, donor: str) -> str:
    """The zone's 96-byte (3 CRAM lines) palette file.

    Derived from the donor's own `Pal_<ZONE>:` line rather than typed in: the
    final game spells it `Pal_EHZ:   palette EHZ.bin` (a macro that prepends the
    directory) and the prototype `Pal_GHZ:  binclude "palettes/GHZ.bin"`.
    """
    name = zone_row(zone, donor)["palette"]
    text = _main_asm(donor)
    if donor == S2_FINAL:
        m = re.search(rf'^Pal_{name}:\s*palette\s+(\S+\.bin)', text, re.M)
        if not m:
            raise SystemExit(f"s2.asm no longer defines Pal_{name}")
        rel = os.path.join("art", "palettes", m.group(1))
    else:
        m = re.search(rf'^Pal_{name}:\s*binclude\s+"([^"]+)"', text, re.M)
        if not m:
            raise SystemExit(f"the prototype's main.asm no longer defines Pal_{name}")
        rel = m.group(1)
    p = os.path.join(donor_root(donor), rel)
    if not os.path.isfile(p):
        raise SystemExit(f"{donor}: palette {p} is absent")
    return p


def art_sources(zone: str, donor: str) -> list[tuple[str, int]]:
    """[(path, tile offset into the zone's art blob)] — the blobs `load_art`
    composes, in the order it lays them down. For provenance and for a later
    parcel that wants to name what a clip's tiles came from."""
    row = zone_row(zone, donor)
    root = donor_root(donor)
    if donor == S2_FINAL:
        out = [(os.path.join(root, "art/kosinski", row["art"] + ".kos"), 0)]
        if "art_supp" in row:
            fn, const = row["art_supp"]
            off = parse_s2_constant(_asm(donor, "s2.constants.asm"), const)
            out.append((os.path.join(root, "art/kosinski", fn + ".kos"), off))
        return out
    out = [(os.path.join(root, "art/nemesis", row["art"] + ".nem"), 0)]
    if "art_supp" in row:
        fn, plc_label, art_label = row["art_supp"]
        out.append((os.path.join(root, "art/nemesis", fn + ".nem"),
                    _proto_plc_vram_tile(_main_asm(donor), plc_label, art_label)))
    return out


def _proto_plc_vram_tile(text: str, plc_label: str, art_label: str) -> int:
    """The VRAM tile index a prototype PLC list loads `art_label` to.

    `Hill_Top_Sprites_1:` ... `dc.l ArtNem_HTZ` / `dc.w $3F80` — the word after
    the pointer is the VRAM BYTE address, so the tile index is that over 32 and
    the byte offset into the zone's art blob is the address itself.
    """
    start = text.index("\n" + plc_label + ":")
    m = re.search(rf"dc\.l\s+{art_label}\b[^\n]*\n\s*dc\.w\s+\$([0-9A-Fa-f]+)",
                  text[start:start + 4000])
    if not m:
        raise SystemExit(
            f"the prototype's {plc_label} no longer loads {art_label} "
            f"(the supplementary-art VRAM address is unreadable)")
    addr = int(m.group(1), 16)
    if addr % 32:
        raise SystemExit(
            f"{plc_label}/{art_label} VRAM address ${addr:X} is not tile-aligned")
    return addr // 32


# ---------------------------------------------------------------------------
# Art / blocks / chunks / layout
# ---------------------------------------------------------------------------

def load_art(zone: str, donor: str) -> bytes:
    """The zone's foreground art blob: 32 bytes per tile, tile 0 at offset 0.

    Both donors load the level art to VRAM tile 0, so a nametable word's tile
    index is an index into this blob directly.
    """
    row = zone_row(zone, donor)
    root = donor_root(donor)

    if donor == S2_FINAL:
        s2asm = _main_asm(donor)
        for spelled in (f'"art/kosinski/{row["art"]}.kos"',
                        f'"mappings/16x16/{row["blocks"]}.kos"',
                        f'"mappings/128x128/{row["chunks"]}.kos"'):
            if spelled not in s2asm:
                raise SystemExit(
                    f"s2.asm no longer BINCLUDEs {spelled} — donor registry is stale")
        art, _ = ojz_common.kos_decompress(
            read_bytes(os.path.join(root, "art/kosinski", row["art"] + ".kos")))
        art = bytearray(art)
        if "art_supp" in row:
            fn, const = row["art_supp"]
            off = parse_s2_constant(_asm(donor, "s2.constants.asm"), const) * 32
            supp, _ = ojz_common.kos_decompress(
                read_bytes(os.path.join(root, "art/kosinski", fn + ".kos")))
            if len(art) < off + len(supp):
                art.extend(bytes(off + len(supp) - len(art)))
            art[off:off + len(supp)] = supp
        return bytes(art)

    main = _main_asm(donor)
    for spelled in (f'"art/nemesis/{row["art"]}.nem"',
                    f'"mappings/16x16/{row["blocks"]}.bin"',
                    f'"mappings/128x128/{row["chunks"]}.kos"'):
        if spelled not in main:
            raise SystemExit(
                f"the prototype's main.asm no longer bincludes {spelled} — "
                f"donor registry is stale")
    art = bytearray(nem_decompress(
        read_bytes(os.path.join(root, "art/nemesis", row["art"] + ".nem"))))
    if "art_supp" in row:
        fn, plc_label, art_label = row["art_supp"]
        off = _proto_plc_vram_tile(main, plc_label, art_label) * 32
        supp = nem_decompress(read_bytes(os.path.join(root, "art/nemesis", fn + ".nem")))
        if len(art) < off + len(supp):
            art.extend(bytes(off + len(supp) - len(art)))
        art[off:off + len(supp)] = supp
    return bytes(art)


def load_blocks(zone: str, donor: str) -> list[list[int]]:
    """The zone's 16x16 block table: 4 nametable words per block.

    FINAL: `mappings/16x16/<set>.kos`, Kosinski.
    PROTOTYPE: `mappings/16x16/<set>.bin`, UNCOMPRESSED — main.asm:7816 copies
    it word for word into Block_Table with no decompression step.
    """
    row = zone_row(zone, donor)
    root = donor_root(donor)
    if donor == S2_FINAL:
        blocks = ojz_common.load_block_map(
            os.path.join(root, "mappings/16x16", row["blocks"] + ".kos"))
    else:
        raw = read_bytes(os.path.join(root, "mappings/16x16", row["blocks"] + ".bin"))
        blocks = [list(struct.unpack_from(">4H", raw, i))
                  for i in range(0, len(raw) // 8 * 8, 8)]

    if "block_patch" in row:
        patch = row["block_patch"]
        main = _main_asm(donor)
        # Both donors spell the patch the same way:
        #   lea (Block_Table+$980).w,a1 / lea (BM16_HTZ).l,a0
        m = re.search(
            r"lea\s+\(Block_Table\+\$([0-9A-Fa-f]+)\)\.w,a1\s*\n\s*lea\s+"
            r"\(BM16_" + re.escape(patch) + r"\)", main)
        if not m:
            raise SystemExit(
                f"{donor}: the {patch} block-map patch offset is no longer readable")
        boff = int(m.group(1), 16) // 8
        ext = ".kos" if donor == S2_FINAL else ".bin"
        if donor == S2_FINAL:
            extra = ojz_common.load_block_map(
                os.path.join(root, "mappings/16x16", patch + ext))
        else:
            raw = read_bytes(os.path.join(root, "mappings/16x16", patch + ext))
            extra = [list(struct.unpack_from(">4H", raw, i))
                     for i in range(0, len(raw) // 8 * 8, 8)]
        while len(blocks) < boff + len(extra):
            blocks.append([0, 0, 0, 0])
        blocks[boff:boff + len(extra)] = extra
    return blocks


def load_chunks(zone: str, donor: str) -> list[list[int]]:
    """The zone's 128x128 chunk table: 64 chunk-entry words per chunk.

    Kosinski `.kos` in BOTH donors — the one level format they agree on.
    """
    row = zone_row(zone, donor)
    return ojz_common.load_chunk_map(
        os.path.join(donor_root(donor), "mappings/128x128", row["chunks"] + ".kos"))


def load_fg_grid(zone: str, donor: str) -> np.ndarray:
    """The zone's FOREGROUND chunk-id grid, (rows, cols) of uint8.

    FINAL: `level/layout/<name>.kos` decodes to exactly $1000 bytes — 32 rows of
    128, even rows foreground, odd rows background.
    PROTOTYPE: `level/layout/<name>.bin` is uncompressed, foreground only (the
    background is a separate `_BG.bin`), with a two-byte (width-1, height-1)
    header; `Interleave_Level_Layout` (main.asm:7930) then TILES each row
    ($80 div width) times across the 128-byte RAM row. Every foreground layout
    in the prototype is 128x16, so the tiling is a single copy — but it is
    implemented rather than asserted, because the background layouts are not.
    """
    row = zone_row(zone, donor)
    root = donor_root(donor)
    if donor == S2_FINAL:
        layout, _ = ojz_common.kos_decompress(
            read_bytes(os.path.join(root, "level/layout", row["layout"] + ".kos")))
        if len(layout) != 0x1000:
            raise SystemExit(
                f"{row['layout']}: layout decoded to {len(layout)} bytes, expected $1000")
        return np.frombuffer(bytes(layout), dtype=np.uint8).reshape(32, 128)[0::2]

    data = read_bytes(os.path.join(root, "level/layout", row["layout"] + ".bin"))
    return expand_proto_layout(data, row["layout"])


def load_bg_grid(zone: str, donor: str) -> np.ndarray:
    """The zone's BACKGROUND chunk-id grid, (rows, cols) of uint8. FINAL DONOR ONLY.

    The final game interleaves the two planes in one $1000-byte blob, so the
    background is simply the odd rows — one file, no extra registry.

    The PROTOTYPE keeps its background in a SEPARATE file per zone AND act
    (`GHZ_BG.bin`, but `HTZ_1_BG.bin` / `HTZ_2_BG.bin`, and `CNZ_2_BG.bin` is
    8 bytes where `CNZ_1_BG.bin` is 2048), and the mapping from zone+act to file
    is `Off_Level`'s `zoneOffsetTableEntry` rows rather than a naming rule. That is
    a registry this parcel has no consumer for, so it is REFUSED by name rather
    than guessed at: `<zone>_BG.bin` is right for five of the ten zones and wrong
    for the rest, which is exactly the shape of silent-wrong-data this module
    exists to prevent.
    """
    if donor != S2_FINAL:
        raise SystemExit(
            f"load_bg_grid: the {donor} donor keeps its background layouts in "
            f"separate per-zone-AND-act files named by Off_Level, not by a rule. "
            f"Add that registry (main.asm:35551-35612) before asking for a "
            f"prototype background — do not guess `<zone>_BG.bin`.")
    row = zone_row(zone, donor)
    layout, _ = ojz_common.kos_decompress(
        read_bytes(os.path.join(donor_root(donor), "level/layout", row["layout"] + ".kos")))
    if len(layout) != 0x1000:
        raise SystemExit(
            f"{row['layout']}: layout decoded to {len(layout)} bytes, expected $1000")
    return np.frombuffer(bytes(layout), dtype=np.uint8).reshape(32, 128)[1::2]


def expand_proto_layout(data: bytes, name: str = "?") -> np.ndarray:
    """One prototype layout file -> its (height, 128) chunk-id grid.

    Exposed separately from `load_fg_grid` because the background layouts use the
    same format and a later parcel will want them.
    """
    if len(data) < 2:
        raise SystemExit(f"{name}: prototype layout shorter than its header")
    w, h = data[0] + 1, data[1] + 1
    body = data[2:]
    if len(body) != w * h:
        raise SystemExit(
            f"{name}: prototype layout header says {w}x{h} = {w * h} bytes, "
            f"the file carries {len(body)}")
    if w > 0x80:
        raise SystemExit(f"{name}: prototype layout is {w} chunks wide, over the 128 the "
                         f"RAM row holds")
    reps = 0x80 // w
    grid = np.zeros((h, 128), dtype=np.uint8)
    src = np.frombuffer(body, dtype=np.uint8).reshape(h, w)
    for r in range(reps):
        grid[:, r * w:(r + 1) * w] = src
    return grid


# ---------------------------------------------------------------------------
# Zone assembly — the grid the page pipeline eats
# ---------------------------------------------------------------------------

class Zone:
    """One S2 zone act, cropped to its camera-reachable box.

    words: (box_h, box_w) uint16 nametable words; void: same shape, bool.
    """

    def __init__(self, name, words, void, box, art_tiles, n_art_tiles):
        self.name = name
        self.words = words
        self.void = void
        self.box = box
        self.art = art_tiles          # bytes, 32 per tile
        self.n_art_tiles = n_art_tiles


def chunk_tiles(chunks, blocks) -> np.ndarray:
    """chunk id -> 16x16 tile words, through the REAL chunk_get_tile_word."""
    tpc = ojz_strip_gen.TILES_PER_CHUNK_ROW
    out = np.zeros((len(chunks), tpc, tpc), dtype=np.uint16)
    for ci, ch in enumerate(chunks):
        for tr in range(tpc):
            for tc in range(tpc):
                out[ci, tr, tc] = ojz_strip_gen.chunk_get_tile_word(ch, blocks, tc, tr)
    return out


def crop_to_box(name, full, art, xs, xe, ys, ye, extra=None) -> Zone:
    """Crop a zone's full FG nametable to its camera-reachable LevelSize box."""
    tile = 8
    x0 = max(0, xs) // tile
    x1 = min(full.shape[1], -(-(xe + 320) // tile))
    y0 = max(0, ys) // tile
    y1 = min(full.shape[0], -(-(ye + 224) // tile))
    words = full[y0:y1, x0:x1].copy()
    n_art = len(art) // 32
    oob = int(np.count_nonzero((words & 0x7FF) >= n_art))
    if oob:
        raise SystemExit(f"{name}: {oob} words reference tiles past the {n_art}-tile art blob")
    box = {"level_size_px": [xs, xe, ys, ye], "crop_tiles": [x0, x1, y0, y1],
           "ystart_clamped": ys < 0}
    if extra:
        box.update(extra)
    return Zone(name, words, np.zeros(words.shape, dtype=bool), box, bytes(art), n_art)


_zone_cache: dict[tuple[str, str, int], Zone] = {}


def load_zone(zone: str, donor: str, act: int = 1) -> Zone:
    """A whole zone act, cropped to its camera box. Memoised per (zone, donor, act)."""
    key = (donor, zone, act)
    if key in _zone_cache:
        return _zone_cache[key]

    row = zone_row(zone, donor)
    art = load_art(zone, donor)
    blocks = load_blocks(zone, donor)
    chunks = load_chunks(zone, donor)
    grid = load_fg_grid(zone, donor).astype(np.int64)
    if grid.max() >= len(chunks):
        raise SystemExit(
            f"{donor}/{zone}: layout names chunk {int(grid.max())} of {len(chunks)}")

    tpc = ojz_strip_gen.TILES_PER_CHUNK_ROW
    full = chunk_tiles(chunks, blocks)[grid]
    full = full.transpose(0, 2, 1, 3).reshape(grid.shape[0] * tpc, grid.shape[1] * tpc)

    xs, xe, ys, ye = level_size(zone, donor, act)
    extra = {
        "game": "Sonic 2" if donor == S2_FINAL else "Sonic 2 (Simon Wai prototype)",
        "layout": row["layout"],
        "donor": donor,
    }
    if xe >= CAMERA_BOX_PLACEHOLDER_XEND:
        # The camera box is a placeholder, not a bound. Recorded, never silently
        # trimmed: trimming here would move every figure measured off this box.
        extra["camera_box_is_placeholder"] = True
    z = crop_to_box(zone, full, art, xs, xe, ys, ye, extra)
    _zone_cache[key] = z
    return z


def painted_bbox(zone_obj: Zone):
    """(x0, x1, y0, y1) in tiles of the cells whose tile field is non-zero, or None.

    The bound a clip of a placeholder-camera-box zone (WFZ in the final game, HPZ
    in the prototype) must be taken from.
    """
    nz = (zone_obj.words & 0x7FF) != 0
    if not nz.any():
        return None
    rows = np.nonzero(nz.any(axis=1))[0]
    cols = np.nonzero(nz.any(axis=0))[0]
    return int(cols[0]), int(cols[-1]) + 1, int(rows[0]), int(rows[-1]) + 1


# ---------------------------------------------------------------------------
# Collision
# ---------------------------------------------------------------------------
#: The two shape banks, per donor. Both are 256 shapes x 16 bytes.
#: VERTICAL is the per-column HEIGHT array `collision_pipeline.bake_cell` wants
#: as its `profiles`; HORIZONTAL is the rotated (per-row WIDTH) array, which
#: aeon REGENERATES rather than imports (design doc §1.3 item 3).
_COLL_ARRAYS = {
    S2_FINAL: {"vertical": "Collision array - Vertical.bin",
               "horizontal": "Collision array - Horizontal.bin",
               "angles": "Curve and resistance mapping.bin"},
    S2_PROTOTYPE: {"vertical": "Collision array 1.bin",
                   "horizontal": "Collision array 2.bin",
                   "angles": "Curve and resistance mappings.bin"},
}


def collision_arrays(donor: str, which: str = "vertical") -> tuple[bytes, bytes]:
    """(profiles, angles) — the shape bank and its 256 angle bytes.

    `which` names WHICH bank: "vertical" is the per-column height array and the
    one `bake_cell` means by `profiles`; "horizontal" is the rotated array and is
    offered only so a measurement can be reproduced against it.

    MEASURED 2026-09-17: the prototype's `Collision array 1.bin` is byte-identical
    to the final game's `Collision array - Vertical.bin`, `Collision array 2.bin`
    to `- Horizontal.bin`, and the angle tables are identical too. The two games
    share one collision-shape vocabulary, so a prototype zone's geometry needs no
    second bank.
    """
    names = _COLL_ARRAYS[_donor(donor) and donor]
    if which not in ("vertical", "horizontal"):
        raise SystemExit(f"collision_arrays: which must be vertical|horizontal, got {which!r}")
    root = donor_root(donor)
    profiles = read_bytes(os.path.join(root, "collision", names[which]))
    angles = read_bytes(os.path.join(root, "collision", names["angles"]))
    if len(profiles) != 4096:
        raise SystemExit(f"{donor}: {names[which]} is {len(profiles)} bytes, expected 4096")
    if len(angles) != 256:
        raise SystemExit(f"{donor}: {names['angles']} is {len(angles)} bytes, expected 256")
    return profiles, angles


_coll_cache: dict[tuple[str, str], tuple] = {}


def collision_inputs(zone: str, donor: str):
    """(chunks, fg_grid, index_a, index_b) for one zone.

    index_a/index_b are 768-byte arrays, ONE BYTE PER BLOCK naming a collision
    shape — Kosinski-compressed in the final donor, raw in the prototype (which
    expands each byte to a word in RAM at load time, main.asm:4174, a RAM detail
    with no bearing on the file's content). A zone with no second path has
    index_b == index_a, matching the donor's own Off_ColS row.
    """
    key = (donor, zone)
    if key in _coll_cache:
        return _coll_cache[key]
    row = zone_row(zone, donor)
    root = donor_root(donor)
    chunks = load_chunks(zone, donor)
    grid = load_fg_grid(zone, donor)

    def _index(name):
        raw = read_bytes(os.path.join(root, "collision", name))
        if donor == S2_FINAL:
            raw, _ = ojz_common.kos_decompress(raw)
        if len(raw) != 768:
            raise SystemExit(
                f"{donor}: collision index {name} is {len(raw)} bytes, expected 768")
        return bytes(raw)

    a = _index(row["coll_p"])
    b = a if row["coll_s"] is None else _index(row["coll_s"])
    _coll_cache[key] = (chunks, grid, a, b)
    return _coll_cache[key]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _mode_zones(args):
    donor = args.donor
    print(f"# donor {donor} at {donor_root(donor)}")
    for zn in (args.zones or zone_names(donor)):
        z = load_zone(zn, donor)
        pb = painted_bbox(z)
        h, w = z.words.shape
        print(f"{zn:5s} box={w}x{h} tiles ({w*8}x{h*8} px)  art_tiles={z.n_art_tiles:5d}  "
              f"painted={pb}  placeholder_box={z.box.get('camera_box_is_placeholder', False)}")


def _mode_selfcheck(args):
    rc = 0
    for donor in DONORS:
        try:
            root = donor_root(donor)
        except SystemExit as e:
            print(f"{donor}: UNRESOLVED — {e}")
            rc = 1
            continue
        print(f"# {donor} at {root}")
        for zn in zone_names(donor):
            try:
                z = load_zone(zn, donor)
                ch, gr, a, b = collision_inputs(zn, donor)
                pal = palette_path(zn, donor)
                srcs = art_sources(zn, donor)
                print(f"  {zn:5s} OK words={z.words.shape} art={z.n_art_tiles} "
                      f"chunks={len(ch)} idxA/B={'same' if a == b else 'differ'} "
                      f"pal={os.path.basename(pal)} art_sources={len(srcs)}")
            except SystemExit as e:
                print(f"  {zn:5s} FAILED — {e}")
                rc = 1
        for which in ("vertical", "horizontal"):
            p, ang = collision_arrays(donor, which)
            print(f"  bank[{which}] {len(p)}B angles {len(ang)}B")
    return rc


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="mode", required=True)
    p = sub.add_parser("zones")
    p.add_argument("zones", nargs="*")
    p.add_argument("--donor", required=True, choices=DONORS)
    p.set_defaults(fn=_mode_zones)
    p = sub.add_parser("selfcheck")
    p.set_defaults(fn=_mode_selfcheck)
    a = ap.parse_args()
    sys.exit(a.fn(a) or 0)


if __name__ == "__main__":
    main()
