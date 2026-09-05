#!/usr/bin/env python3
"""waterline_art_gate — the row remap's ART half, checked IN THE BUILT ROM.

EFFECTS-W1 item 9d. `tools/row_remap_gate.py` gates the half that permutes plane-B SCROLL
words; this gates the half that permutes PIXEL ROWS. Same discipline: it reads bytes out of
the linked image at the addresses the listing gives, and re-derives everything it asserts.

FIVE ARMS, AND THE THIRD IS THE ONE THAT COULD NOT BE WRITTEN ANY OTHER WAY:

  1. THE IMAGE IS THE MODEL. The emitted `WaterlineStripArt` bytes are recomputed from
     `tools/waterline_art_gen.py` — a separate spelling of the model that
     `engine/level/parallax_dsl.emp`'s `waterline_strip_art16()` is one instantiation of —
     and compared. Not a byte pin: nothing checked in is being matched.

  2. THE IMAGE CAN BE SEEN. No two source rows inside the ladder's own reach are identical,
     and no nibble is 0. A row-uniform image makes the gather byte-for-byte INVISIBLE, and
     index 0 is the plane's backdrop. Run against the ROM rather than the model, so it is
     not reachable from arm 1 alone — arm 1 says the bytes are the model's, arm 2 says what
     is in the image can show, and a model that lost its variation passes arm 1 by agreeing
     about a blank.

  3. THE CODE AND THE DATA AGREE ON THE GEOMETRY. Six immediates are decoded out of
     `Waterline_Art_Update`'s own instruction bytes — the dest column stride, the source
     strip stride, the line count, the strip count, the VRAM destination and the DMA length
     — and each is checked against the value DERIVED from H. This is the arm that catches
     the whole failure family the other four cannot: an image and a loop that were changed
     apart. A gather with a stale stride reads plausible pixels from the wrong rows and
     every byte-level check upstream of it stays green.

  4. THE DMA LANDS WHERE THE MAP SAYS. The destination immediate equals `waterline_strips`'
     declared base from games/<game>/vram.toml (base * 32), and base + length stays under
     `sprite_table`. Read from the map, never typed here.

  5. THE TWO HALVES ARE WIRED TOGETHER IN THE IMAGE. `Parallax_Fill_PerLine`'s row-remap
     pass must contain a `move.l a3, Waterline_Art_Row` — the publication S3K spells
     `move.w d2,(Events_bg+$10).w`. Without it the art half reads a cell nobody writes,
     which is a strip that never updates: no fault, no wrong pixel, just a still picture.

⚠ A GAME WITH NO WATERLINE IS A PASS, AND IT IS DERIVED. `demo` declares no CAP_ROW_REMAP.
Its image must therefore carry NO `WaterlineStripArt` symbol AND a `Waterline_Art_Update`
that is exactly `rts` — both directions, because that is the shape this capability threatens
demo in: the proc is ENGINE code and ships in every game, so a gate that only looked at
sonic4 would be blind to a 512-byte image or an ungated gather leaking into a game that can
never show one. "No symbol, nothing to do" would pass hardest exactly when the emission had
been lost.

WHAT THIS GATE DELIBERATELY DOES NOT DO. It does not run an emulator. Whether the gather
actually RAN this frame, on the ladder row the perspective quantity selected, and whether
those bytes reached VRAM, is tools/waterline_art_witness.py's question and it needs a
machine. Keeping them apart is what lets this one be build-fatal in every canonical shape.
"""
from __future__ import annotations

import argparse
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import waterline_art_gen as model                                   # noqa: E402
from row_remap_gate import (Unmeasurable, cap_bit, game_caps,       # noqa: E402
                            parse_lst, EXIT_OK, EXIT_FAIL, EXIT_UNMEASURABLE)

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# --------------------------------------------------------------- the declared geometry


def geometry(repo: str) -> dict:
    """H and the strip shape, read off engine/level/parallax_dsl.emp — never typed here.

    `WATERLINE_H` is spelled there as an alias of the ladder's own `ROW_REMAP_H16`, so this
    resolves the alias rather than accepting a name it cannot value. A gate that typed 16
    would keep passing after the ladder was retuned, which is the exact drift arm 3 exists
    to catch, one level up."""
    p = os.path.join(repo, "engine/level/parallax_dsl.emp")
    text = open(p, encoding="utf-8").read()

    def const(name: str) -> int:
        m = re.search(r"^pub const " + name + r"\s*=\s*([A-Za-z0-9_]+)", text, re.M)
        if not m:
            raise Unmeasurable(f"{name} is not declared in {p}")
        tok = m.group(1)
        if tok.isdigit():
            return int(tok)
        m2 = re.search(r"^pub const " + tok + r"\s*=\s*(\d+)", text, re.M)
        if not m2:
            raise Unmeasurable(f"{name} = {tok}, which is not a literal const in {p}")
        return int(m2.group(1))

    H = const("WATERLINE_H")
    strips = const("WATERLINE_STRIPS")
    row_bytes = const("WATERLINE_ROW_BYTES")
    if strips != model.STRIPS or row_bytes != model.ROW_BYTES:
        raise Unmeasurable(
            f"the engine declares {strips} strips of {row_bytes}-byte rows; "
            f"tools/waterline_art_gen.py models {model.STRIPS} of {model.ROW_BYTES}. "
            f"The two spellings of the geometry have diverged")
    return {"H": H, "src": model.src_bytes(H), "dst": model.dst_bytes(H),
            "tiles": model.tiles_for_height(H),
            "col_stride": H * model.BYTES_PER_COLUMN_ROW,
            "strip_src_stride": 2 * H * model.ROW_BYTES}


def region_from_map(repo: str, game: str, name: str) -> dict:
    """One region's declared base/tiles, out of the game's own vram.toml."""
    import tomllib
    p = os.path.join(repo, "games", game, "vram.toml")
    with open(p, "rb") as fh:
        doc = tomllib.load(fh)
    for r in doc.get("region", []):
        if r.get("name") == name:
            return r
    raise Unmeasurable(f"games/{game}/vram.toml declares no region {name!r}")


# --------------------------------------------------------------- arm 3: decode the loop


def decode_immediates(code: bytes) -> dict:
    """Pull the six geometry immediates out of Waterline_Art_Update's instruction bytes.

    Matched by OPCODE WORD, not by position: `lea d16(a2),a4` is $49EA, `lea d16(a0),a0` is
    $41E8, `move.w #imm,d3` is $363C, `move.w #imm,d2` is $343C, `moveq #imm,d4` is $78xx.
    Positional decoding would survive an instruction being inserted or reordered and would
    then read a displacement out of the middle of something else. Each is required to occur
    exactly once — a second `lea d16(a2),a4` means the loop grew a shape this cannot read,
    and the honest answer to that is UNMEASURABLE, not a guess."""
    want = {
        "col_stride":       (0x49EA, 2),   # lea d16(a2),a4  — dest column 1's cursor
        "strip_src_stride": (0x41E8, 2),   # lea d16(a0),a0  — next strip's source
        "vram_dest":        (0x343C, 2),   # move.w #imm,d2  — QueueDMA destination
    }
    out, counts = {}, {}
    i = 0
    # move.w #imm,d3 appears TWICE with different meanings (the line count and the DMA
    # length), so it is collected as a list and disambiguated by the caller.
    d3_imms = []
    moveq_d4 = []
    while i + 1 < len(code):
        op = struct.unpack_from(">H", code, i)[0]
        if op == 0x363C and i + 3 < len(code):
            d3_imms.append(struct.unpack_from(">H", code, i + 2)[0])
            i += 4
            continue
        if (op & 0xFF00) == 0x7800:                     # moveq #imm,d4
            moveq_d4.append(op & 0xFF)
            i += 2
            continue
        hit = [(k, v) for k, v in want.items() if v[0] == op]
        if hit and i + 3 < len(code):
            k, (_, width) = hit[0]
            counts[k] = counts.get(k, 0) + 1
            out[k] = struct.unpack_from(">H", code, i + 2)[0]
            i += 2 + width
            continue
        i += 2
    for k in want:
        if counts.get(k, 0) != 1:
            raise Unmeasurable(
                f"Waterline_Art_Update carries {counts.get(k, 0)} instance(s) of the "
                f"instruction that should hold {k}, expected exactly 1 — the loop's shape "
                f"has changed and this decoder can no longer say what it reads")
    if len(d3_imms) != 2:
        raise Unmeasurable(
            f"Waterline_Art_Update carries {len(d3_imms)} `move.w #imm,d3`, expected 2 (the "
            f"per-strip line count and the DMA length)")
    if len(moveq_d4) != 1:
        raise Unmeasurable(
            f"Waterline_Art_Update carries {len(moveq_d4)} `moveq #imm,d4`, expected 1 (the "
            f"strip count)")
    out["line_count"], out["dma_length"] = d3_imms[0], d3_imms[1]
    out["strip_count"] = moveq_d4[0]
    return out


def proc_span(syms: dict, name: str) -> tuple[int, int]:
    """[start, end) of a proc, ended by the next symbol that is not one of ITS OWN locals.

    Two traps, both hit while writing this. Sigil emits a proc's local labels as
    `$<module>$<Proc>$<label>` symbols in the same listing, so "the next symbol at a higher
    address" ends the proc at its first internal label — here 22 bytes in, which made arm 3
    report zero instances of instructions that are plainly there. And RAM symbols share the
    map, so an unfiltered scan ends a ROM proc at $FFxxxx."""
    if name not in syms:
        raise Unmeasurable(f"{name} is not in the listing")
    start = syms[name]
    own = f"${name}$"
    rom = sorted({v for k, v in syms.items()
                  if v > start and v < 0x400000 and own not in k})
    if not rom:
        raise Unmeasurable(f"{name} is the last ROM symbol — cannot bound it")
    return start, rom[0]


# --------------------------------------------------------------- the gate


def run(a) -> int:
    geo = geometry(REPO)
    H = geo["H"]
    caps = game_caps(REPO, a.game)
    bit = cap_bit(REPO, "CAP_ROW_REMAP")
    declared = bool(caps & bit)
    syms = parse_lst(a.lst)
    rom = open(a.rom, "rb").read()
    problems: list[str] = []

    print(f"waterline_art_gate: {a.game} SCANLINE_CAPS ${caps:04X}, CAP_ROW_REMAP ${bit:04X} "
          f"-> {'DECLARED' if declared else 'not declared'}")
    print(f"  geometry from engine/level/parallax_dsl.emp: H = {H}, source {geo['src']} B, "
          f"DMA {geo['dst']} B, {geo['tiles']} VRAM tiles")

    if not declared:
        # THE UNDECLARED PATH IS NOT A SKIP. Both directions, and both are real leaks.
        if "WaterlineStripArt" in syms:
            problems.append(
                f"{a.game} does not declare CAP_ROW_REMAP but its image carries "
                f"WaterlineStripArt at ${syms['WaterlineStripArt']:X} — "
                f"{geo['src']} bytes of art for a waterline it can never draw")
        if "Waterline_Art_Update" in syms:
            start, end = proc_span(syms, "Waterline_Art_Update")
            body = rom[start:end]
            if body[:2] != b"\x4e\x75":
                problems.append(
                    f"{a.game} does not declare CAP_ROW_REMAP but Waterline_Art_Update at "
                    f"${start:X} is {end - start} bytes beginning {body[:2].hex()}, not the "
                    f"bare `4e75` the capability gate should leave — the gather is emitted "
                    f"and would run against a Waterline_Art_Row nothing publishes")
            else:
                print(f"  Waterline_Art_Update ${start:X}: `rts` only — the gate holds")
        for p in problems:
            print("  FAIL " + p)
        print(f"  {'OK' if not problems else 'FAILED'} — undeclared path, "
              f"{len(problems)} problem(s)")
        return EXIT_OK if not problems else EXIT_FAIL

    # ---- arm 1: the emitted image IS the model ----
    if "WaterlineStripArt" not in syms:
        raise Unmeasurable(
            f"{a.game} DECLARES CAP_ROW_REMAP but no WaterlineStripArt symbol is in "
            f"{a.lst} — the art half's source image was not emitted, and every arm below "
            f"has no subject")
    at = syms["WaterlineStripArt"]
    blob = rom[at:at + geo["src"]]
    want = model.image(H)
    if blob != want:
        first = next(i for i in range(len(want)) if blob[i:i + 1] != want[i:i + 1])
        problems.append(
            f"WaterlineStripArt at ${at:X} is not the model: first difference at byte "
            f"{first} (source row {first // model.ROW_BYTES % (2 * H)} of strip "
            f"{first // (2 * H * model.ROW_BYTES)}), ROM ${blob[first]:02X} vs model "
            f"${want[first]:02X}")
    else:
        print(f"  arm 1  WaterlineStripArt ${at:X}, {geo['src']} B — byte-identical to "
              f"tools/waterline_art_gen.py at H = {H}")

    # ---- arm 2: the image can be SEEN ----
    # ON THE ROM BYTES, NOT ON THE MODEL, and the difference is the whole reason this arm
    # exists separately from arm 1. Asking the model would make this arm unreachable by any
    # ROM mutation — arm 1 would always fail first — and it would answer the wrong question:
    # arm 1 says the ROM is the model, arm 2 says what is IN THE ROM can be seen. Run
    # against the image the 68000 gathers from, it catches both an image that lost its
    # variation and a MODEL that never had any (in which case arm 1 passes, agreeing about
    # a blank).
    # The rule is model.local_duplicates — no two source rows identical INSIDE the ladder's
    # own reach — and it is shared rather than restated so the ROM and the model are judged
    # by one predicate. It is deliberately LOCAL, not global: global distinctness is
    # unreachable above H = 16 with 16 ripple phases, and asserting it here would refuse
    # every raised H (tools/test_waterline_art_gen.py P4 measures both boundaries).
    seen_bad = ["the ROM image is partly invisible: " + b
                for b in model.local_duplicates(H, blob)]
    for o, byte in enumerate(blob):
        if (byte >> 4) == 0 or (byte & 15) == 0:
            seen_bad.append(
                f"byte {o} of the ROM image carries palette index 0, the plane's backdrop "
                f"— that pixel punches a hole through the band")
            break
    problems.extend(seen_bad)
    if not seen_bad:
        rows = sum(len({bytes(r) for r in model.source_rows(H, blob, st)})
                   for st in range(model.STRIPS))
        print(f"  arm 2  no duplicate source row inside the ladder's {model.RIPPLE_PERIOD}-row "
              f"reach and no nibble 0; {rows} of {model.STRIPS * 2 * H} rows globally "
              f"distinct (reported, not required)")

    # ---- arm 3: the loop's own immediates against the derived geometry ----
    start, end = proc_span(syms, "Waterline_Art_Update")
    imm = decode_immediates(rom[start:end])
    checks = [
        ("dest column stride", imm["col_stride"], geo["col_stride"],
         "the gather's second write cursor would land on top of column 0's rows"),
        ("source strip stride", imm["strip_src_stride"], geo["strip_src_stride"],
         "the second strip would be gathered out of the first strip's rows"),
        ("per-strip line count", imm["line_count"], H - 1,
         "the gather writes a different number of lines than the strip holds"),
        ("strip count", imm["strip_count"], model.STRIPS - 1,
         "one of the two strips is never gathered, or the loop runs past the buffer"),
        ("DMA length", imm["dma_length"], geo["dst"],
         "the transfer is not the size of the gathered image"),
    ]
    for label, got, expect, why in checks:
        if got != expect:
            problems.append(
                f"Waterline_Art_Update's {label} immediate is {got}, derived {expect} "
                f"(H = {H}) — {why}")
    if all(g == e for _l, g, e, _w in checks):
        print(f"  arm 3  Waterline_Art_Update ${start:X}-${end:X} ({end - start} B): all 5 "
              f"geometry immediates match the derivation "
              f"(col {imm['col_stride']}, strip {imm['strip_src_stride']}, "
              f"lines {imm['line_count'] + 1}, strips {imm['strip_count'] + 1}, "
              f"dma {imm['dma_length']})")

    # ---- arm 4: the DMA lands inside the declared region ----
    reg = region_from_map(REPO, a.game, "waterline_strips")
    sat = region_from_map(REPO, a.game, "sprite_table")
    base_bytes = reg["base"] * 32
    if imm["vram_dest"] != base_bytes:
        problems.append(
            f"the DMA destination immediate is ${imm['vram_dest']:04X} but "
            f"games/{a.game}/vram.toml declares waterline_strips at slot {reg['base']} = "
            f"${base_bytes:04X} — the strips are being written outside their own region")
    if base_bytes + geo["dst"] > sat["base"] * 32:
        problems.append(
            f"the strips ({geo['dst']} B at ${base_bytes:04X}) run into sprite_table at "
            f"${sat['base'] * 32:04X}")
    if reg["tiles"] < geo["tiles"]:
        problems.append(
            f"waterline_strips declares {reg['tiles']} tiles and the geometry needs "
            f"{geo['tiles']} at H = {H}")
    if not problems:
        print(f"  arm 4  DMA ${imm['vram_dest']:04X} + {geo['dst']} B inside "
              f"waterline_strips (slot {reg['base']}, {reg['tiles']} tiles; "
              f"{geo['tiles']} used, {reg['tiles'] - geo['tiles']} spare) and clear of "
              f"sprite_table at ${sat['base'] * 32:04X}")

    # ---- arm 5: the two halves are wired together in the image ----
    pub = publication(syms, rom)
    if pub is None:
        problems.append(
            "the row-remap pass in Parallax_Fill_PerLine contains no "
            "`move.l a3,Waterline_Art_Row` — nothing publishes the ladder row, so the "
            "art half reads a cell nobody writes and the strips never update. That is a "
            "still picture, not a fault: no wrong pixel is ever drawn")
    else:
        print(f"  arm 5  the pass publishes the ladder row at ${pub:X} "
              f"(move.l a3,${syms['Waterline_Art_Row'] & 0xFFFF:04X}.w)")

    for p in problems:
        print("  FAIL " + p)
    print(f"  {'OK' if not problems else 'FAILED'} — {len(problems)} problem(s)")
    return EXIT_OK if not problems else EXIT_FAIL


def publication(syms: dict, rom: bytes) -> int | None:
    """Find `move.l a3,<Waterline_Art_Row>.w` ($21CB, then the short address) inside the
    row-remap pass's own bracketed span. Bounded by the brackets rather than searched
    ROM-wide so a coincidental byte pair elsewhere cannot answer for the pass."""
    begin = next((v for k, v in syms.items() if k.endswith("$cap_row_remap_pass_begin")), None)
    end = next((v for k, v in syms.items() if k.endswith("$cap_row_remap_pass_end")), None)
    if begin is None or end is None or "Waterline_Art_Row" not in syms:
        raise Unmeasurable(
            "the row-remap pass's cap_row_remap_pass brackets or Waterline_Art_Row are not "
            "in the listing — arm 5 has no span to search")
    addr = syms["Waterline_Art_Row"] & 0xFFFF
    for i in range(begin, min(end, len(rom) - 3)):
        if rom[i] == 0x21 and rom[i + 1] == 0xCB and \
                struct.unpack_from(">H", rom, i + 2)[0] == addr:
            return i
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--lst", required=True)
    ap.add_argument("--rom", required=True)
    ap.add_argument("--game", required=True)
    a = ap.parse_args()
    try:
        return run(a)
    except Unmeasurable as e:
        print(f"waterline_art_gate: UNMEASURABLE — {e}")
        return EXIT_UNMEASURABLE


if __name__ == "__main__":
    sys.exit(main())
