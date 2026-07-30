#!/usr/bin/env python3
"""tools/verify_emit_bin.py — byte-equality verifier for --emit-bin outputs.

Sound-migration prep (design ruling DSM.4): song_packer.py, zyrinx_player.py,
smps_import.py and sfx_transcode.py each grew a --emit-bin mode that writes the
EXACT payload bytes their generated .asm files' dc.b/db (or pbyte) lines encode,
to a sibling .bin path (same stem, .bin extension — see song_packer.bin_path_for).
This script is the independent check that the two stay byte-identical: it parses
each target .asm back into bytes from its data lines ALONE (no label/align/equ/
assert scaffolding) and compares against the corresponding .bin file.

It does NOT regenerate anything itself — run each tool's --emit-bin (or
generate --emit-bin for sfx_transcode) first, THEN run this script to verify:

    python3 tools/zyrinx_player.py --emit-pitchtable --emit-bin
    python3 tools/zyrinx_player.py --emit-native-song --emit-bin
    python3 games/sonic4/data/sound/song_drumtest.py --emit-bin
    python3 games/sonic4/data/sound/song_hcz2.py --emit-bin
    python3 tools/sfx_transcode.py generate --emit-bin
    python3 tools/verify_emit_bin.py

Parsing rule: within a target .asm, find the FIRST top-level `Label:` line (a
bare identifier followed by ':' at column 0) and its matching `Label_End:`
line; every `dc.b`/`db`/`pbyte` directive STRICTLY BETWEEN those two lines
contributes its operand bytes, in file order. Comment-only lines (starting
with ';') and non-data lines (align, equ, if/endif, macro bodies, error, ...)
are skipped. Operand bytes are decoded as either `$XX` (hex) or bare decimal
(0-255) tokens, comma-separated, trailing comment (";...") stripped first.

This covers every target's actual format:
  - song_*.asm / *_pitchtable*.asm / sfx_NN.asm       -> dc.b $XX hex rows
  - movingtrucks_patches.asm / sfx_NN_patches.asm     -> pbyte NNN decimal rows
  - hcz2_patches.asm                                  -> dc.b $XX hex rows

sfx_table.asm is EXCLUDED on purpose: it is a dc.l POINTER table (linker-
resolved label addresses), not a static byte payload — it has no byte-equal
.bin twin (see sfx_transcode.generate_all's emit_bin docstring).

Dependency-free: stdlib only (os, re, sys, argparse).
"""

import argparse
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.normpath(os.path.join(_HERE, ".."))
_SOUND_DIR = os.path.join(_ROOT, "games", "sonic4", "data", "sound")
_SFX_DIR = os.path.join(_SOUND_DIR, "sfx")

# Target .asm files, relative to _SOUND_DIR (plus every sfx/*.asm blob+patches
# pair; sfx_table.asm is deliberately excluded — see the module docstring).
# The six Moving-Trucks .asm (song_movingtrucks/drumtest/hcz2, movingtrucks_
# pitchtable_stream/patches, hcz2_patches) RETIRED at seam-2 stage-2c: the .asm
# are deleted (mt_bank.emp BINCLUDE'd), so there is no .asm to verify against
# their .bin twins. The .bin (mt_bank.emp's `embed()` source) is now covered by
# the mt_port region gate + the seam2_mt_rom whole-ROM byte gate instead.
_FIXED_TARGETS = []

_LABEL_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*):\s*$")
_DATA_DIRECTIVE_RE = re.compile(r"^\s*(dc\.b|db|pbyte)\b\s*(.*)$", re.IGNORECASE)


class ParseError(Exception):
    pass


def _strip_comment(operand_text: str) -> str:
    """Strip a trailing ';...' end-of-line comment (the operand text never
    legitimately contains ';', so the first one found is always the comment)."""
    idx = operand_text.find(";")
    if idx >= 0:
        operand_text = operand_text[:idx]
    return operand_text.strip()


def _parse_operand_bytes(operand_text: str, lineno: int, path: str) -> list:
    """Parse a comma-separated operand list into a list of 0..255 ints.
    Accepts '$XX' hex tokens and bare decimal tokens (the two conventions the
    four emitters use); rejects anything else (e.g. ALLARGS in the pbyte macro
    body, which must never be reached because we only scan Label:..Label_End:)."""
    text = _strip_comment(operand_text)
    if not text:
        return []
    out = []
    for tok in text.split(","):
        tok = tok.strip()
        if not tok:
            continue
        if tok.startswith("$"):
            val = int(tok[1:], 16)
        elif re.fullmatch(r"[0-9]+", tok):
            val = int(tok, 10)
        elif re.fullmatch(r"[0-9A-Fa-f]+h", tok):
            val = int(tok[:-1], 16)
        else:
            raise ParseError(
                f"{path}:{lineno}: un-parseable data operand token {tok!r} "
                f"(expected $XX hex or decimal 0-255)")
        if not (0 <= val <= 0xFF):
            raise ParseError(
                f"{path}:{lineno}: operand {val} out of byte range 0..255")
        out.append(val)
    return out


def parse_asm_payload(path: str) -> bytes:
    """Parse the payload bytes of the FIRST Label:..Label_End: data block in an
    .asm file. Raises ParseError if no such block is found."""
    with open(path) as f:
        lines = f.readlines()

    start_i = None
    label = None
    for i, raw in enumerate(lines):
        line = raw.rstrip("\n")
        m = _LABEL_RE.match(line)
        if m:
            start_i = i
            label = m.group(1)
            break
    if start_i is None:
        raise ParseError(f"{path}: no top-level 'Label:' line found")

    end_label = label + "_End:"
    end_i = None
    for i in range(start_i + 1, len(lines)):
        if lines[i].rstrip("\n").strip() == end_label:
            end_i = i
            break
    if end_i is None:
        raise ParseError(f"{path}: no matching '{end_label}' line found after "
                         f"line {start_i + 1}")

    out = bytearray()
    for i in range(start_i + 1, end_i):
        line = lines[i].rstrip("\n")
        stripped = line.strip()
        if not stripped or stripped.startswith(";"):
            continue
        m = _DATA_DIRECTIVE_RE.match(line)
        if not m:
            # Non-data line inside the block (shouldn't normally occur between
            # Label: and Label_End: for these generators, but skip defensively
            # rather than fail — e.g. a stray blank/comment variant).
            continue
        out.extend(_parse_operand_bytes(m.group(2), i + 1, path))
    return bytes(out)


def bin_path_for(asm_path: str) -> str:
    root, _ext = os.path.splitext(asm_path)
    return root + ".bin"


def discover_targets():
    """Return the full list of .asm paths to verify: the fixed task list plus
    every games/sonic4/data/sound/sfx/*.asm EXCEPT sfx_table.asm."""
    targets = [os.path.join(_SOUND_DIR, name) for name in _FIXED_TARGETS]
    if os.path.isdir(_SFX_DIR):
        for name in sorted(os.listdir(_SFX_DIR)):
            if not name.endswith(".asm"):
                continue
            if name == "sfx_table.asm":
                continue  # pointer table, no byte-equal .bin twin (see docstring)
            targets.append(os.path.join(_SFX_DIR, name))
    return targets


def verify_one(asm_path: str):
    """Returns (status, detail) where status in {"PASS", "FAIL", "MISSING_BIN",
    "MISSING_ASM", "PARSE_ERROR"}."""
    if not os.path.exists(asm_path):
        return "MISSING_ASM", f"{asm_path} does not exist"
    bin_path = bin_path_for(asm_path)
    if not os.path.exists(bin_path):
        return "MISSING_BIN", f"{bin_path} does not exist (run the emitter with --emit-bin first)"
    try:
        asm_bytes = parse_asm_payload(asm_path)
    except ParseError as e:
        return "PARSE_ERROR", str(e)
    with open(bin_path, "rb") as f:
        bin_bytes = f.read()
    if asm_bytes == bin_bytes:
        return "PASS", f"{len(asm_bytes)} bytes"
    if len(asm_bytes) != len(bin_bytes):
        return "FAIL", (f"length mismatch: asm={len(asm_bytes)} bytes, "
                        f"bin={len(bin_bytes)} bytes")
    for i, (a, b) in enumerate(zip(asm_bytes, bin_bytes)):
        if a != b:
            return "FAIL", (f"{len(asm_bytes)} bytes, first diff at offset "
                            f"{i}: asm=${a:02X} bin=${b:02X}")
    return "FAIL", f"{len(asm_bytes)} bytes, differ (unreachable diff search)"


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    ap = argparse.ArgumentParser(
        description="Byte-compare each generated .asm's dc.b/db/pbyte payload "
                    "against its --emit-bin .bin sibling.")
    ap.add_argument("paths", nargs="*",
                    help="Specific .asm file(s) to verify (default: the full "
                         "sound-migration target set under games/sonic4/data/sound/).")
    args = ap.parse_args(argv)

    targets = [os.path.abspath(p) for p in args.paths] if args.paths else discover_targets()

    results = []
    n_pass = 0
    n_fail = 0
    for asm_path in targets:
        status, detail = verify_one(asm_path)
        rel = os.path.relpath(asm_path, _ROOT)
        results.append((rel, status, detail))
        if status == "PASS":
            n_pass += 1
            print(f"PASS  {rel}  ({detail})")
        else:
            n_fail += 1
            print(f"FAIL  {rel}  [{status}] {detail}")

    print()
    print(f"{n_pass} passed, {n_fail} failed, {len(targets)} total")
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
