#!/usr/bin/env python3
"""Compose aeon's insta-shield sprite tables from the sonic_hack donor.

THE ART IS NOT PRODUCED HERE. `art/uncompressed/shields/insta_shield.bin` was
imported at 2a0895aa and is byte-identical to
`sonic_hack/art/uncompressed/instashield.bin` (52 tiles, 1664 B). This script
VERIFIES that identity and produces the three things the tree is missing:

  1. mappings  -> games/sonic4/data/mappings/insta_shield.bin
     Donor `mappings/sprite/Instashield.asm` (SonMapEd S2 8-byte piece format,
     S3K's geometry verbatim) assembled here, then converted to aeon's
     VDP-order frame format by tools/convert_s2_mappings.py::convert_mappings —
     imported, never re-implemented, so a format change moves one file.

  2. DPLC      -> games/sonic4/data/dplc/insta_shield.bin
     Donor `mappings/spriteDPLC/Instashield.asm` assembled verbatim: S3K's DPLC
     format IS aeon's (offset-word table, then a count word and that many
     `(tiles-1)<<12 | start` entry words; engine/objects/dplc.emp's header is
     the spec).  ONE deviation, and it is checked in both directions by a
     comptime `ensure` in games/sonic4/objects/insta_shield.emp:
       a frame whose MAPPING has zero pieces gets a ZERO-ENTRY DPLC frame.
     S3K's two trailing frames draw nothing (its map offsets 6 and 7 both point
     at `word_1A152: dc.w 0`) but its DPLC still names 29 tiles for them, because
     S3K's own object only loads a DPLC on mapping_frame 0 and 3. Aeon's generic
     Perform_DPLC loads on every frame change, so keeping the donor entries there
     would DMA 928 dead bytes twice per insta-shield.
     NOTE the committed file this REPLACES was wrong: 24 bytes, 3 frames, both
     entries pointing at block A. It is a PENDING_PAIRS row in verify_sprites.py
     (on disk, not in the ROM), which is why nothing noticed.

  3. donor anim -> games/sonic4/data/animations/insta_shield_donor_anim.bin
     The donor's raw S3K attack script (`animations/Sprite/Instashield.asm`,
     anim 1). Embedded by the .emp as a `const` ONLY — it emits zero ROM bytes —
     so the animation gate's expected duration is COMPUTED from the reference
     instead of typed in as a literal.

Usage:
    tools/compose_instashield.py [--donor DIR] [--out-root DIR] [--check]

    --donor     sonic_hack tree (default $AEON_SONIC_HACK_DIR, else ../sonic_hack)
    --out-root  where to write (default: the aeon tree this script lives in)
    --check     write nothing; compare against what is already there

Provenance test: tools/test_instashield_art.py.
"""
import argparse
import os
import re
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
AEON = os.path.normpath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)

from convert_s2_mappings import convert_mappings  # noqa: E402

DONOR_MAP = os.path.join("mappings", "sprite", "Instashield.asm")
DONOR_DPLC = os.path.join("mappings", "spriteDPLC", "Instashield.asm")
DONOR_ANIM = os.path.join("animations", "Sprite", "Instashield.asm")
DONOR_ART = os.path.join("art", "uncompressed", "instashield.bin")

OUT_MAP = os.path.join("games", "sonic4", "data", "mappings", "insta_shield.bin")
OUT_DPLC = os.path.join("games", "sonic4", "data", "dplc", "insta_shield.bin")
OUT_ANIM = os.path.join("games", "sonic4", "data", "animations",
                        "insta_shield_donor_anim.bin")
IN_ART = os.path.join("art", "uncompressed", "shields", "insta_shield.bin")

# S3K animation control codes occupy $FC..$FF; anything below is a frame index.
S3K_CONTROL_FLOOR = 0xFC


class DonorError(RuntimeError):
    """The donor .asm did not parse the way this script's format claim says."""


# ---------------------------------------------------------------------------
# A two-pass assembler for the donor's dc.b / dc.w listings.
#
# The files are SonMapEd/disassembler output with exactly one shape: an optional
# `label:` at the start of a line, then `dc.b` or `dc.w` and a comma list of
# either integers ($hex or decimal) or `label-BaseLabel` differences. Pass 1
# sizes and records label offsets, pass 2 emits. Nothing else is supported on
# purpose — an unexpected token raises rather than being silently skipped.
# ---------------------------------------------------------------------------
_LINE = re.compile(r"^(?:(\w+)\s*:)?\s*(?:dc\.(b|w)\s+(.*?))?\s*(?:;.*)?$")


def _parse_lines(text):
    """-> [(label_or_None, width_or_None, [operand_str, ...])]"""
    out = []
    for raw in text.splitlines():
        line = raw.replace("\t", " ").rstrip()
        if not line.strip():
            continue
        m = _LINE.match(line.strip())
        if not m:
            raise DonorError(f"unparsed donor line: {raw!r}")
        label, width, operands = m.group(1), m.group(2), m.group(3)
        ops = []
        if operands:
            ops = [o.strip() for o in operands.split(",") if o.strip()]
        out.append((label, width, ops))
    return out


def _int(tok):
    tok = tok.strip()
    if tok.startswith("$"):
        return int(tok[1:], 16)
    return int(tok, 10)


def assemble(text):
    """Assemble a donor dc.b/dc.w listing to bytes. Offsets are from byte 0."""
    parsed = _parse_lines(text)

    # pass 1 — label offsets
    labels = {}
    pos = 0
    for label, width, ops in parsed:
        if label:
            if label in labels:
                raise DonorError(f"duplicate donor label {label}")
            labels[label] = pos
        if width:
            pos += len(ops) * (1 if width == "b" else 2)

    # pass 2 — emit
    out = bytearray()
    for _label, width, ops in parsed:
        if not width:
            continue
        for tok in ops:
            if "-" in tok and not tok.lstrip().startswith("-"):
                lhs, rhs = tok.split("-", 1)
                lhs, rhs = lhs.strip(), rhs.strip()
                if lhs not in labels:
                    raise DonorError(f"unknown donor label {lhs}")
                # The base label is the table head, which these files leave
                # implicit (it is the `Map_InstaShield:` in the includER). It is
                # offset 0 by construction; a named base must also resolve to 0.
                base = labels.get(rhs, 0)
                if base != 0:
                    raise DonorError(
                        f"donor base label {rhs} is not the table head")
                value = labels[lhs] - base
            else:
                value = _int(tok)
            if width == "b":
                if not 0 <= value <= 0xFF:
                    raise DonorError(f"byte operand out of range: {tok}")
                out.append(value)
            else:
                if not 0 <= value <= 0xFFFF:
                    raise DonorError(f"word operand out of range: {tok}")
                out += struct.pack(">H", value)

    # The donor's `even`. NOT cosmetic and NOT optional: every one of these
    # includes is followed by `even` in sonic_hack/code/engines/animated_tiles.asm,
    # and the mapping file RELIES on it — its final empty frame is written
    # `word_1A152: dc.b 0`, one byte, and only the pad completes the 16-bit piece
    # count word that makes it a zero-piece frame. (The sibling SonMapEd export
    # `mappings/sprite/S2 instashield.asm` spells the same frame `dc.b 0, 0`.)
    # Without this the last frame's count word reads off the end.
    if len(out) & 1:
        out.append(0)
    return bytes(out)


# ---------------------------------------------------------------------------
# DPLC surgery: zero the frames whose mapping frame draws nothing.
# ---------------------------------------------------------------------------
def frame_piece_counts(s4_map):
    """Piece count per frame of an ALREADY-CONVERTED aeon mapping blob."""
    frames = struct.unpack_from(">H", s4_map, 0)[0] // 2
    counts = []
    for f in range(frames):
        off = struct.unpack_from(">H", s4_map, f * 2)[0]
        counts.append(struct.unpack_from(">H", s4_map, off + 4)[0])
    return counts


def dplc_entry_counts(dplc):
    frames = struct.unpack_from(">H", dplc, 0)[0] // 2
    counts = []
    for f in range(frames):
        off = struct.unpack_from(">H", dplc, f * 2)[0]
        counts.append(struct.unpack_from(">H", dplc, off)[0])
    return counts


def rebuild_dplc(dplc, piece_counts):
    """Re-emit a DPLC table, replacing every frame whose mapping has zero pieces
    with a zero-entry frame. Frames that DO draw keep the donor's entries
    verbatim. Shared frame bodies are re-shared: identical bodies dedupe, exactly
    as the donor's own offset table does."""
    frames = struct.unpack_from(">H", dplc, 0)[0] // 2
    if frames != len(piece_counts):
        raise DonorError(
            f"donor DPLC has {frames} frames, mappings have {len(piece_counts)}")

    bodies = []
    for f in range(frames):
        if piece_counts[f] == 0:
            body = struct.pack(">H", 0)
        else:
            off = struct.unpack_from(">H", dplc, f * 2)[0]
            n = struct.unpack_from(">H", dplc, off)[0]
            body = dplc[off:off + 2 + n * 2]
        bodies.append(body)

    out_offsets = []
    blob = bytearray()
    seen = {}
    base = frames * 2
    for body in bodies:
        if body not in seen:
            seen[body] = base + len(blob)
            blob += body
        out_offsets.append(seen[body])

    out = bytearray()
    for off in out_offsets:
        out += struct.pack(">H", off)
    return bytes(out + blob)


# ---------------------------------------------------------------------------
def donor_attack_script(anim_text):
    """The donor's SECOND animation (the attack) as raw S3K script bytes.

    `Anim - Insta-Shield.asm` is a 2-entry offset table over two script bodies:
    anim 0 is the invisible idle, anim 1 is the attack. Returned verbatim,
    duration byte first — the .emp derives its expected duration from these
    bytes rather than restating the reference."""
    blob = assemble(anim_text)
    count = struct.unpack_from(">H", blob, 0)[0] // 2
    if count != 2:
        raise DonorError(f"donor anim table has {count} animations, expected 2")
    start = struct.unpack_from(">H", blob, 2)[0]
    script = blob[start:]
    # Terminated by a control code ($FC..$FF) plus, for $FC..$FE, one argument.
    for i in range(1, len(script)):
        if script[i] >= S3K_CONTROL_FLOOR:
            end = i + 1 if script[i] == 0xFF else i + 2
            return bytes(script[:end])
    raise DonorError("donor attack script has no terminator")


def compose(donor_root):
    """-> {relative_output_path: bytes}"""
    def read(rel):
        path = os.path.join(donor_root, rel)
        if not os.path.isfile(path):
            raise DonorError(f"donor file missing: {path}")
        with open(path, "rb") as fh:
            return fh.read()

    s2_map = assemble(read(DONOR_MAP).decode("latin-1"))
    s4_map, _frames = convert_mappings(s2_map)
    counts = frame_piece_counts(s4_map)

    donor_dplc = assemble(read(DONOR_DPLC).decode("latin-1"))
    s4_dplc = rebuild_dplc(donor_dplc, counts)

    anim = donor_attack_script(read(DONOR_ANIM).decode("latin-1"))

    return {
        OUT_MAP: s4_map,
        OUT_DPLC: s4_dplc,
        OUT_ANIM: anim,
    }, read(DONOR_ART)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--donor", default=os.environ.get(
        "AEON_SONIC_HACK_DIR", os.path.normpath(os.path.join(AEON, "..", "sonic_hack"))))
    ap.add_argument("--out-root", default=AEON)
    ap.add_argument("--check", action="store_true",
                    help="write nothing; compare against the existing files")
    args = ap.parse_args()

    outputs, donor_art = compose(args.donor)

    # The art is a VERIFICATION, not an output: it is already in the tree.
    art_path = os.path.join(args.out_root, IN_ART)
    with open(art_path, "rb") as fh:
        have_art = fh.read()
    if have_art != donor_art:
        print(f"FAIL {IN_ART}: differs from the donor "
              f"({len(have_art)} B here, {len(donor_art)} B donor)")
        return 1
    print(f"ok   {IN_ART}: {len(have_art)} B == donor (52 tiles)")

    rc = 0
    for rel, blob in outputs.items():
        path = os.path.join(args.out_root, rel)
        if args.check:
            existing = open(path, "rb").read() if os.path.isfile(path) else None
            if existing == blob:
                print(f"ok   {rel}: {len(blob)} B")
            else:
                print(f"FAIL {rel}: {len(blob)} B composed, "
                      f"{len(existing) if existing is not None else 'absent'} on disk")
                rc = 1
        else:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as fh:
                fh.write(blob)
            print(f"wrote {rel}: {len(blob)} B")
    return rc


if __name__ == "__main__":
    sys.exit(main())
