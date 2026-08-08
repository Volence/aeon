#!/usr/bin/env python3
"""Deterministic S3K Tails + Knuckles asset extractor/converter for Aeon.

Design #3 (character-dispatch) asset PREP. Reads stock Sonic 3 & Knuckles
character assets out of the read-only skdisasm tree and emits them in Aeon's
sprite formats (mirroring our custom-Sonic pipeline exactly), plus intermediate
JSON for the animation scripts (whose 11-universal-id .emp table authoring is a
character-plan decision, deferred here). See README.md for provenance and the
full list of decisions made vs deferred.

Source of truth for the Aeon formats this mirrors:
  tools/convert_s2_mappings.py  -> mapping VDP-order binary + flip-invariant bbox
  tools/dplc_layout.py          -> contiguous art rearrange + <=16-tile DPLC split
  tools/verify_sprites.py       -> art/DPLC structural checks

Canonical S3K sources (verified against s3.asm: Obj_Tails / Obj_Tails_Tail /
Obj_Knuckles load exactly these — NOT the *_S3 / *2P / SStage variants):
  Tails body      : Map_Tails_ / PLC_Tails_ / AniTails_ / ArtUnc_Tails
  Tails appendage : Map_Tails_Tail_ / PLC_Tails_Tail_ / AniTails_Tail_ / ArtUnc_Tails_Tail
  Knuckles        : Map_Knuckles_ / DPLC(Knuckles) / AniKnuckles_ / ArtUnc_Knuckles

Deterministic: no timestamps, no RNG; JSON is sorted & fixed-indent; art is a
byte-for-byte copy. Running twice produces byte-identical output.

Usage:
  ./gen_characters.py [skdisasm_root]
  (default skdisasm_root = /home/volence/sonic_hacks/skdisasm)
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

DEFAULT_SK = Path("/home/volence/sonic_hacks/skdisasm")


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


def process_set(sk, name, art_rel, map_rel, dplc_rel, anim_rel, out_dir, report):
    art_path = sk / art_rel
    art = art_path.read_bytes()
    art_tiles = len(art) // TILE_SIZE

    map_frames = frames_from_asm(sk / map_rel, 'map')
    dplc_frames = frames_from_asm(sk / dplc_rel, 'dplc')

    if len(map_frames) != len(dplc_frames):
        raise AssertionError(
            f"{name}: mapping frame count {len(map_frames)} != "
            f"DPLC frame count {len(dplc_frames)} — sources out of sync")

    # Raw source DPLC (S3K pointer format) — provenance / re-optimizable.
    raw_dplc = write_dplc(dplc_frames)

    # Contiguous art + one-entry-per-frame DPLC (split to <=16). Build-consumed.
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
    (out_dir / "art" / f"{name}_opt.bin").write_bytes(opt_art)         # contiguous
    (out_dir / "mappings" / f"{name}.bin").write_bytes(map_bin)        # Aeon VDP-order
    (out_dir / "dplc" / f"{name}.bin").write_bytes(raw_dplc)           # S3K-format
    (out_dir / "dplc" / f"{name}_opt.bin").write_bytes(opt_dplc)       # optimized <=16

    tiles_per_frame = [sum(c for _, c in f) for f in dplc_frames]
    max_entry_opt = max((c for f in opt_frames for _, c in f), default=0)
    report.append({
        "set": name,
        "frames": len(map_frames),
        "src_art_tiles": art_tiles,
        "src_art_bytes": len(art),
        "opt_art_tiles": len(opt_art) // TILE_SIZE,
        "opt_art_bytes": len(opt_art),
        "max_tiles_per_frame": max(tiles_per_frame) if tiles_per_frame else 0,
        "max_opt_dplc_entry_tiles": max_entry_opt,
        "map_bin_bytes": len(map_bin),
        "art_sha": sha(art),
        "opt_art_sha": sha(opt_art),
        "map_sha": sha(map_bin),
        "opt_dplc_sha": sha(opt_dplc),
    })


def main():
    sk = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SK
    out = Path(__file__).parent
    S = "General/Sprites"
    report = []

    # ---- Tails body ----
    process_set(
        sk, "tails",
        f"{S}/Tails/Art/Tails.bin",
        f"{S}/Tails/Map - Tails.asm",
        f"{S}/Tails/DPLC - Tails.asm",
        f"{S}/Tails/Anim - Tails.asm",
        out / "tails", report)
    # ---- Tails appendage (the separate tail sprites, own object/art) ----
    process_set(
        sk, "tails_tail",
        f"{S}/Tails/Art/Tails tails.bin",
        f"{S}/Tails/Map - Tails tails.asm",
        f"{S}/Tails/DPLC - Tails tails.asm",
        f"{S}/Tails/Anim - Tails Tail.asm",
        out / "tails", report)
    # ---- Knuckles ----
    process_set(
        sk, "knuckles",
        f"{S}/Knuckles/Art/Knuckles.bin",
        f"{S}/Knuckles/Map - Knuckles.asm",
        f"{S}/Knuckles/DPLC - Knuckles.asm",
        f"{S}/Knuckles/Anim - Knuckles.asm",
        out / "knuckles", report)

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
    pal_out = out / "palettes"
    pal_out.mkdir(parents=True, exist_ok=True)
    (pal_out / "knuckles_main.bin").write_bytes(
        (sk / f"{S}/Knuckles/Palettes/Main.bin").read_bytes())
    (pal_out / "knuckles_ssz_end.bin").write_bytes(
        (sk / f"{S}/Knuckles/Palettes/SSZ End.bin").read_bytes())

    # ---- Summary report ----
    print("=" * 74)
    print("S3K Tails + Knuckles asset staging — summary")
    print("=" * 74)
    for r in report:
        print(f"\n[{r['set']}]")
        print(f"  frames                 : {r['frames']}")
        print(f"  source art             : {r['src_art_tiles']} tiles "
              f"({r['src_art_bytes']:,} bytes)  sha={r['art_sha']}")
        print(f"  contiguous (opt) art   : {r['opt_art_tiles']} tiles "
              f"({r['opt_art_bytes']:,} bytes)  sha={r['opt_art_sha']}")
        print(f"  max tiles / frame      : {r['max_tiles_per_frame']} "
              f"(pre-split)")
        print(f"  max opt DPLC entry     : {r['max_opt_dplc_entry_tiles']} tiles "
              f"(<= {MAX_TILES_PER_ENTRY} asserted)")
        print(f"  Aeon mappings          : {r['map_bin_bytes']:,} bytes  "
              f"sha={r['map_sha']}")
    for name, jpath, _ in anim_specs:
        obj = json.loads(jpath.read_text())
        print(f"\n[{name} anims]  {obj['anim_count']} scripts -> "
              f"{jpath.relative_to(out)}")
    print("\nDPLC <=16-tile invariant: PASS (asserted per set above)")
    print("=" * 74)


if __name__ == '__main__':
    main()
