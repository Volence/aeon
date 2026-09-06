#!/usr/bin/env python3
"""tilt_frame_static_audit.py — audit and RENDER every tilted walk/run frame of a
character sheet straight out of the shipped ROM data, with no emulator anywhere.

WHY THIS EXISTS (F7, the player sprite jumble). The owner's own description of the
bug is "while playing, it happens when on a slope and sonic/character is rotated, a
specific sprite during the animation of walking". That is a claim about ONE frame of
the tilted walk cycle, and a frame is a purely static object: a mapping frame, the
DPLC frame that loads its tiles, and the art those tiles name. Every one of those
three lives in a committed .bin. So the whole hypothesis is checkable offline, and
this tool checks it two ways:

  1. COHERENCE. For each frame, the DPLC entries enqueue T tiles into the character
     VRAM window in entry order, filling relative tile indices 0..T-1. Every mapping
     piece names a relative tile index and a VDP size, so it consumes w*h tiles
     starting there. The frame is coherent iff
         max(referenced relative tile) == T - 1
     Greater is an OVERRUN: the piece draws VRAM the frame never loaded, i.e. the
     previous frame's leftovers — exactly the reported symptom, and exactly what an
     off-by-one in a producer looks like. Less is DEAD LOAD: harmless to the picture
     but it burns VRAM and DMA, so it is reported too. Each DPLC entry is separately
     checked to lie inside the art sheet.

  2. RENDERING. Coherence is necessary and not sufficient: a frame whose tables are
     internally consistent can still name the WRONG tiles (a mis-deduped run, a
     producer that appended a fresh run and left one piece pointing at the old one).
     Nothing but looking at the picture finds that, so this renders every frame from
     art + DPLC + mapping into one contact sheet, laid out block-by-block so a bad
     frame stands out against its three siblings.

WHAT THE HYPOTHESIS FORBIDS. "The reported jumble is a static table defect in one
tilted walk frame" forbids all 48 frames being coherent AND all 48 rendering as a
clean Sonic. If this tool comes back green on both arms, that hypothesis is refuted
for the shipped tables and the defect has to be produced at RUNTIME (transfer,
ordering, or a frame the tables never see) — say so, do not soften it.

FORMATS, all read from this tree rather than assumed:
  mappings  offset table of words; frame = 4 signed bbox bytes, piece-count word at
            FRAME_PIECE_COUNT (+4), pieces from FRAME_PIECES (+6), 8 bytes each:
            +0 word Y, +2 byte VDP size code, +3 pad, +4 word tile attrs, +6 word X
            (engine/objects/sprites.emp, engine/objects/frames.emp)
  DPLC      offset table of words; frame = entry-count word then that many words,
            each [count-1 : 4][tile_start : 12] (engine/objects/dplc.emp)
  art       raw 4bpp tiles, 32 B each

The tilt geometry (TILT_WALK_BASE/LEN/SHIFT, TILT_RUN_*, TILT_SETS) and the walk/run
script frame lists are PARSED from player_common.emp and sonic_anims.emp. They are
not typed here: a re-paged sheet moves the constants, and a tool holding its own copy
would keep auditing the frames the sheet no longer uses.

Usage:
    python3 tools/tilt_frame_static_audit.py [--png OUT.png] [--no-render]
Exit status: 0 clean, 1 a coherence defect, 2 could not measure.
"""

import argparse
import re
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

MAP_BIN = ROOT / "games/sonic4/data/mappings/sonic.bin"
DPLC_BIN = ROOT / "games/sonic4/data/dplc/optimized/sonic.bin"
ART_BIN = ROOT / "art/optimized/characters/sonic.bin"
PAL_BIN = ROOT / "games/sonic4/test/sonic_palette.bin"

PLAYER_EMP = ROOT / "games/sonic4/player/player_common.emp"
ANIMS_EMP = ROOT / "games/sonic4/data/animations/sonic_anims.emp"
CONSTS_EMP = ROOT / "engine/system/constants.emp"

TILE_SIZE = 32


class Unmeasurable(Exception):
    """A precondition this tool cannot check around. LOUD, never a soft skip."""


# ---------------------------------------------------------------- source parsing


def emp_const(path, name):
    """One `const NAME = <int>` from a .emp file. $hex and decimal."""
    if not path.is_file():
        raise Unmeasurable(f"{path} is missing; cannot derive {name}")
    m = re.search(
        r"^\s*(?:pub\s+)?const\s+%s\s*=\s*(\$[0-9A-Fa-f]+|\d+)\b" % re.escape(name),
        path.read_text(),
        re.M,
    )
    if not m:
        raise Unmeasurable(f"const {name} not found in {path} — re-derive it")
    t = m.group(1)
    return int(t[1:], 16) if t.startswith("$") else int(t)


def script_frames(path, anim):
    """The frame bytes of one `offsets Ani_Sonic` row, control codes dropped.

    `Walk: [u8; 10] = [DUR_DYNAMIC, 7, 8, 1, 2, 3, 4, 5, 6, AF_END],` -> the eight
    numbers. The leading duration byte and the trailing AF_* command are named, not
    numeric, which is what makes the filter safe: every FRAME in these rows is a
    literal and every non-frame is a symbol.
    """
    if not path.is_file():
        raise Unmeasurable(f"{path} is missing; cannot derive the {anim} script")
    m = re.search(r"^\s*%s:\s*\[u8;\s*\d+\]\s*=\s*\[([^\]]*)\]" % anim,
                  path.read_text(), re.M)
    if not m:
        raise Unmeasurable(f"the {anim} row is not in {path} — re-derive it")
    out = []
    for tok in m.group(1).split(","):
        tok = tok.split("//")[0].strip()
        if not tok:
            continue
        if tok.startswith("$"):
            out.append(int(tok[1:], 16))
        elif tok.isdigit():
            out.append(int(tok))
    if not out:
        raise Unmeasurable(f"the {anim} row parsed to zero frames")
    return out


# ------------------------------------------------------------------ blob parsing


class Sheet:
    def __init__(self, mapping, dplc, art):
        self.M = mapping
        self.D = dplc
        self.A = art
        self.art_tiles = len(art) // TILE_SIZE
        self.map_frames = struct.unpack_from(">H", self.M, 0)[0] // 2
        self.dplc_frames = struct.unpack_from(">H", self.D, 0)[0] // 2
        self.piece_count_off = emp_const(CONSTS_EMP, "FRAME_PIECE_COUNT")
        self.pieces_off = emp_const(CONSTS_EMP, "FRAME_PIECES")

    def dplc(self, frame):
        """[(count, tile_start)] in ENQUEUE ORDER — the order that assigns the
        relative tile indices the mapping pieces name."""
        off = struct.unpack_from(">H", self.D, frame * 2)[0]
        n = struct.unpack_from(">H", self.D, off)[0]
        out = []
        for i in range(n):
            w = struct.unpack_from(">H", self.D, off + 2 + 2 * i)[0]
            out.append((((w >> 12) & 0xF) + 1, w & 0x0FFF))
        return out

    def pieces(self, frame):
        """[(y, size_code, attrs, x)] for one mapping frame."""
        off = struct.unpack_from(">H", self.M, frame * 2)[0]
        n = struct.unpack_from(">H", self.M, off + self.piece_count_off)[0]
        out = []
        for i in range(n):
            b = off + self.pieces_off + 8 * i
            y, size, _pad, attr, x = struct.unpack_from(">hBBHh", self.M, b)
            out.append((y, size, attr, x))
        return out

    def vram_window(self, frame):
        """The frame's relative tile window: index i holds art tile window[i]."""
        win = []
        for count, start in self.dplc(frame):
            win.extend(range(start, start + count))
        return win


def size_wh(code):
    """VDP sprite size code -> (cells wide, cells tall)."""
    return ((code >> 2) & 3) + 1, (code & 3) + 1


# ------------------------------------------------------------------- the coherence arm


def audit_frame(sheet, frame):
    """(list of defect strings, list of note strings) for one mapping frame."""
    defects, notes = [], []
    entries = sheet.dplc(frame)
    total = sum(c for c, _ in entries)

    for i, (count, start) in enumerate(entries):
        if start + count > sheet.art_tiles:
            defects.append(
                "DPLC entry %d loads tiles %d..%d, past the %d-tile art sheet"
                % (i, start, start + count - 1, sheet.art_tiles))

    hi = -1
    for pi, (y, size, attr, x) in enumerate(sheet.pieces(frame)):
        w, h = size_wh(size)
        base = attr & 0x07FF
        span = w * h
        if base + span - 1 >= total:
            defects.append(
                "piece %d (%dx%d cells at x=%d y=%d) names relative tiles %d..%d, "
                "but the DPLC only loaded %d — it draws %d tile(s) of whatever the "
                "PREVIOUS frame left in VRAM"
                % (pi, w, h, x, y, base, base + span - 1, total,
                   base + span - total))
        hi = max(hi, base + span - 1)

    if hi < total - 1:
        notes.append("DPLC loads %d tile(s) no piece draws (dead DMA)"
                     % (total - 1 - hi))
    return defects, notes


# --------------------------------------------------------------------- rendering


def load_palette(path):
    if not path.is_file():
        raise Unmeasurable(f"{path} is missing; cannot render")
    raw = path.read_bytes()
    pal = []
    for i in range(16):
        w = struct.unpack_from(">H", raw, i * 2)[0] if (i * 2 + 2) <= len(raw) else 0
        b = ((w >> 8) & 0xE) * 255 // 14
        g = ((w >> 4) & 0xE) * 255 // 14
        r = (w & 0xE) * 255 // 14
        pal.append((r, g, b))
    return pal


def tile_pixels(art, tile_index):
    """8x8 list of rows of palette indices."""
    off = tile_index * TILE_SIZE
    rows = []
    for r in range(8):
        row = []
        for c in range(4):
            byte = art[off + r * 4 + c]
            row.append(byte >> 4)
            row.append(byte & 0xF)
        rows.append(row)
    return rows


def render_frame(sheet, frame, pal, canvas, ox, oy, draw_flips=True):
    """Draw one mapping frame into `canvas` (a PIL Image) with (ox, oy) as the
    object's origin pixel. Returns (out_of_window_cells, clipped_pixels): the first
    are drawn as a red block so a defect is VISIBLE rather than silently skipped, and
    the second is counted rather than swallowed — a cell too small to hold a frame
    would otherwise hide the very jumble this is looking for."""
    win = sheet.vram_window(frame)
    bad = 0
    clipped = 0
    for (y, size, attr, x) in sheet.pieces(frame):
        w, h = size_wh(size)
        base = attr & 0x07FF
        xflip = bool(attr & 0x0800) and draw_flips
        yflip = bool(attr & 0x1000) and draw_flips
        for col in range(w):
            for row in range(h):
                rel = base + col * h + row          # VDP order: column-major
                sc = (w - 1 - col) if xflip else col
                sr = (h - 1 - row) if yflip else row
                px0 = ox + x + sc * 8
                py0 = oy + y + sr * 8
                cw, ch = canvas.size
                oob = rel >= len(win)
                if oob:
                    bad += 1
                tp = None if oob else tile_pixels(sheet.A, win[rel])
                for dy in range(8):
                    for dx in range(8):
                        if oob:
                            v, colour = 1, (200, 0, 0)
                        else:
                            v = tp[7 - dy if yflip else dy][7 - dx if xflip else dx]
                            colour = pal[v] if v else None
                        if not v:
                            continue
                        px, py = px0 + dx, py0 + dy
                        if not (0 <= px < cw and 0 <= py < ch):
                            clipped += 1
                            continue
                        canvas.putpixel((px, py), colour)
    return bad, clipped


def contact_sheet(sheet, rows, out_path, pal, title_rows):
    from PIL import Image, ImageDraw

    # Cell size is DERIVED, not guessed: the widest/tallest piece extent measured
    # over the audited frames, padded, so nothing can clip. render_frame counts
    # clipped pixels anyway and the caller fails on a non-zero count.
    xmin = ymin = 1 << 30
    xmax = ymax = -(1 << 30)
    for row in rows:
        for frame in row:
            for (y, size, _a, x) in sheet.pieces(frame):
                w, h = size_wh(size)
                xmin, xmax = min(xmin, x), max(xmax, x + w * 8)
                ymin, ymax = min(ymin, y), max(ymax, y + h * 8)
    pad, hdr = 4, 12
    cell_w = (xmax - xmin) + 2 * pad
    cell_h = (ymax - ymin) + 2 * pad + hdr
    org_x, org_y = pad - xmin, pad + hdr - ymin
    label_w = 74
    ncol = max(len(r) for r in rows)
    W = label_w + ncol * cell_w
    H = 16 + len(rows) * cell_h
    img = Image.new("RGB", (W, H), (24, 24, 30))
    d = ImageDraw.Draw(img)

    for ci in range(ncol):
        d.text((label_w + ci * cell_w + 4, 3), "block %d" % ci, fill=(200, 200, 210))

    bad_total = 0
    clip_total = 0
    for ri, row in enumerate(rows):
        y0 = 16 + ri * cell_h
        d.text((4, y0 + cell_h // 2 - 4), title_rows[ri], fill=(200, 200, 210))
        for ci, frame in enumerate(row):
            x0 = label_w + ci * cell_w
            d.rectangle([x0, y0, x0 + cell_w - 2, y0 + cell_h - 2], outline=(60, 60, 70))
            b, c = render_frame(sheet, frame, pal, img, x0 + org_x, y0 + org_y)
            bad_total += b
            clip_total += c
            d.text((x0 + 3, y0 + 2), "$%02X" % frame, fill=(140, 200, 140))
    img.save(out_path)
    return bad_total, clip_total, (W, H)


# -------------------------------------------------------------------------- main


def focus_sheet(sheet, frames, out_path, pal, captions, scale=5):
    """One row of named frames blown up — the close-up evidence image. Same
    renderer as the contact sheet, so it cannot disagree with it."""
    from PIL import Image, ImageDraw

    xmin = ymin = 1 << 30
    xmax = ymax = -(1 << 30)
    for frame in frames:
        for (y, size, _a, x) in sheet.pieces(frame):
            w, h = size_wh(size)
            xmin, xmax = min(xmin, x), max(xmax, x + w * 8)
            ymin, ymax = min(ymin, y), max(ymax, y + h * 8)
    pad = 3
    cw, ch = (xmax - xmin) + 2 * pad, (ymax - ymin) + 2 * pad
    strip = Image.new("RGB", (cw * len(frames), ch), (24, 24, 30))
    clipped = 0
    for i, frame in enumerate(frames):
        _b, c = render_frame(sheet, frame, pal, strip,
                             i * cw + pad - xmin, pad - ymin)
        clipped += c
    strip = strip.resize((strip.width * scale, strip.height * scale),
                         __import__("PIL.Image", fromlist=["Image"]).NEAREST)
    img = Image.new("RGB", (strip.width, strip.height + 30), (24, 24, 30))
    img.paste(strip, (0, 0))
    d = ImageDraw.Draw(img)
    for i, cap in enumerate(captions):
        for li, line in enumerate(cap.split("\n")):
            d.text((i * cw * scale + 6, strip.height + 4 + li * 11), line,
                   fill=(210, 210, 220))
    img.save(out_path)
    return clipped


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--png", default=str(ROOT / "docs/witness/f7-tilt-frames.png"))
    ap.add_argument("--focus-png",
                    default=str(ROOT / "docs/witness/f7-frame-09-defect.png"))
    ap.add_argument("--focus", default="09,01,11,19,C9",
                    help="comma-separated hex frames for the close-up strip")
    ap.add_argument("--no-render", action="store_true")
    args = ap.parse_args()

    for p in (MAP_BIN, DPLC_BIN, ART_BIN):
        if not p.is_file():
            print("UNMEASURABLE: %s is missing" % p)
            return 2

    try:
        sets = emp_const(PLAYER_EMP, "TILT_SETS")
        wbase = emp_const(PLAYER_EMP, "TILT_WALK_BASE")
        wlen = emp_const(PLAYER_EMP, "TILT_WALK_LEN")
        wshift = emp_const(PLAYER_EMP, "TILT_WALK_SHIFT")
        rbase = emp_const(PLAYER_EMP, "TILT_RUN_BASE")
        rlen = emp_const(PLAYER_EMP, "TILT_RUN_LEN")
        rshift = emp_const(PLAYER_EMP, "TILT_RUN_SHIFT")
        walk = script_frames(ANIMS_EMP, "Walk")
        run = script_frames(ANIMS_EMP, "Run")
        sheet = Sheet(MAP_BIN.read_bytes(), DPLC_BIN.read_bytes(), ART_BIN.read_bytes())
    except Unmeasurable as e:
        print("UNMEASURABLE: %s" % e)
        return 2

    # The two shifts ARE the block lengths (player_common.emp ensures this); if the
    # source ever disagrees with itself the audit would sweep the wrong frames.
    if (1 << wshift) != wlen or (1 << rshift) != rlen:
        print("UNMEASURABLE: TILT shifts do not encode the block lengths "
              "(walk 1<<%d vs %d, run 1<<%d vs %d)" % (wshift, wlen, rshift, rlen))
        return 2
    if wbase + sets * wlen != rbase:
        print("UNMEASURABLE: the walk blocks do not end where the run blocks begin "
              "(%d + %d*%d != %d)" % (wbase, sets, wlen, rbase))
        return 2

    print("tilt geometry from source: TILT_SETS=%d  WALK base $%02X len %d shift %d  "
          "RUN base $%02X len %d shift %d" % (sets, wbase, wlen, wshift, rbase, rlen, rshift))
    print("walk script frames: %s" % " ".join("$%02X" % f for f in walk))
    print("run  script frames: %s" % " ".join("$%02X" % f for f in run))
    print("art %d tiles, %d mapping frames, %d DPLC frames"
          % (sheet.art_tiles, sheet.map_frames, sheet.dplc_frames))
    print()

    # Player_ApplyTilt: mapping_frame = script_frame + (block << shift).
    walk_rows = [[f + (b << wshift) for b in range(sets)] for f in walk]
    run_rows = [[f + (b << rshift) for b in range(sets)] for f in run]

    defect_count = 0
    audited = 0
    print("%-8s %-6s %-6s %-8s %s" % ("frame", "dplc", "pieces", "maxtile", "status"))
    for rows, kind in ((walk_rows, "walk"), (run_rows, "run")):
        for row in rows:
            for frame in row:
                if frame >= min(sheet.map_frames, sheet.dplc_frames):
                    print("UNMEASURABLE: %s frame $%02X is past the tables "
                          "(%d map / %d dplc frames)"
                          % (kind, frame, sheet.map_frames, sheet.dplc_frames))
                    return 2
                audited += 1
                d, n = audit_frame(sheet, frame)
                total = sum(c for c, _ in sheet.dplc(frame))
                pieces = sheet.pieces(frame)
                hi = max((a & 0x7FF) + size_wh(s)[0] * size_wh(s)[1] - 1
                         for _y, s, a, _x in pieces) if pieces else -1
                status = "ok" if not d and not n else "; ".join(d + n)
                if d:
                    defect_count += 1
                    status = "DEFECT: " + status
                print("$%02X %-4s %-6d %-6d %-8d %s"
                      % (frame, kind, total, len(pieces), hi, status))

    print()
    print("audited %d frames (%d walk + %d run) across %d tilt blocks"
          % (audited, len(walk) * sets, len(run) * sets, sets))
    print("coherence defects: %d" % defect_count)

    if not args.no_render:
        try:
            pal = load_palette(PAL_BIN)
        except Unmeasurable as e:
            print("UNMEASURABLE: %s" % e)
            return 2
        out = Path(args.png)
        out.parent.mkdir(parents=True, exist_ok=True)
        rows = walk_rows + run_rows
        titles = (["walk %d" % i for i in range(len(walk_rows))]
                  + ["run %d" % i for i in range(len(run_rows))])
        red, clipped, dims = contact_sheet(sheet, rows, out, pal, titles)
        print("rendered %d frames -> %s (%dx%d), %d out-of-window cells drawn red"
              % (audited, out, dims[0], dims[1], red))
        if clipped:
            print("UNMEASURABLE: %d pixels fell outside their cell — the contact "
                  "sheet is hiding art and cannot be read as evidence" % clipped)
            return 2
        if red:
            defect_count += 1

        focus = [int(t, 16) for t in args.focus.split(",") if t.strip()]
        caps = ["$%02X" % f for f in focus]
        fc = focus_sheet(sheet, focus, Path(args.focus_png), pal, caps)
        print("close-up strip (%s) -> %s"
              % (" ".join(caps), args.focus_png))
        if fc:
            print("UNMEASURABLE: %d pixels clipped out of the close-up strip" % fc)
            return 2

    return 1 if defect_count else 0


if __name__ == "__main__":
    sys.exit(main())
