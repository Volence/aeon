#!/usr/bin/env python3
"""left_col_mask_probe — verify the left-column policy declarations against the ROM.

P3 Task 12 (design §2): every per-column-VSRAM scene must declare
`left_column_mask: sprite_mask | factor0_lock | accept`. The comptime guards enforce the
declaration; THIS probe verifies the declarations' REASONING against the shipped
artifact, and carries the (pending) runtime mask-engagement check for the day the
SpriteMask engine emission lands.

TWO ARMS, VERY DIFFERENT STANDINGS:

  --claims   STATIC — parses the .lst symbol table and reads the ROM bytes. No emulator,
             no oracle bus, runnable anywhere. Verifies:
               1. DeformTable_Zero is 256 zero bytes and DeformTable_Shimmer is not —
                  the two facts the comptime guards CANNOT see (a table is a Label), and
                  exactly why Rocking spells Accept instead of Factor0Lock.
               2. Every Rocking record: per-column table attached (DeformTable_Rocking),
                  BG H-table is the ZERO table, band 0's plane-B factor is FACTOR_0
                  (s1 = 15) with dsb live (4). Conclusion the probe certifies: plane-B
                  HScroll is identically zero at runtime, the leftmost-partial-column
                  artifact CANNOT occur, and Accept is the conservative spelling of a
                  true factor0 claim.
               3. Every Perspective record: per-column table attached
                  (DeformTable_Perspective), BG H-table is SHIMMER (non-zero), every
                  band's plane-B factor is FACTOR_0, dsb live on the hills/ground bands
                  ({15,15,15,4,2}). Conclusion: the artifact IS reachable on the
                  dsb-live rows — Accept is a real ship-the-artifact decision, exactly
                  as the authoring comment states.
               4. The two INSTALLABLE configs (OJZ_Default — the act descriptor's
                  fallback; OJZ_Underwater — the water preset) attach NO per-column
                  table: the shipped game never enters per-column mode, so the artifact
                  currently has no runtime subject at all.
             Field offsets are DERIVED from the shipped struct declarations
             (engine/structs.emp parallax_config, engine/level/parallax.emp band_entry),
             never typed — a struct edit moves this probe automatically or fails it
             loudly, both correct.

  --mask     RUNTIME — NO SUBJECT YET, AND IT SAYS SO (exit 2, loud). The SpriteMask
             engine emission is refused by scene() until its parcel lands (see
             docs/DEFERRED_WORK.md "Sprite mask for per-column V-scroll" — blocked on
             the sprites.emp first-Game.*-reference sigil port flip and the game-owned
             opaque tile). When that parcel exists, this arm grows the oracle-bus checks
             (pattern: tools/engine_baseline_probe.py --sat) against its
             capability-raised instrument build:
               * 7 strip entries FIRST in the SAT link chain (link order = priority, and
                 first-in-chain is also what exempts the strip from per-line sprite-limit
                 drops);
               * SAT X = 128 (screen X 0) — NOT X = 0: the mechanism ruling is an OPAQUE
                 strip, because the VDP's X=0 sprite-MASKING feature suppresses later
                 SPRITES on covered lines and cannot repaint a PLANE pixel (and carries
                 the first-sprite-on-line exemption on top — it fails this job twice);
               * a non-zero tile index whose 32 bytes are fully opaque in VRAM, priority
                 bit set;
               * Y coverage 0..223 with no gap at the 32-line seams;
               * per-line engagement: on a line where the artifact is live (per-column
                 mode + non-zero plane-B HScroll), the strip sprite is present in that
                 line's evaluation — the runtime question the Task-4 flag names.
             RUN IT FOREGROUND (controller): oracle MCP from a background agent
             deadlocks, and concurrent probe lanes wedge the emulator.

Red-first (the --claims arm, subject-poisoned): flip one byte inside DeformTable_Zero in
a COPY of the ROM and check 1 goes red naming the offset; the unmodified control stays
green. Quoted in the Task 12 landing evidence.

Usage:
    python3 tools/left_col_mask_probe.py --claims [--rom s4.debug.bin] [--lst s4.debug.lst]
    python3 tools/left_col_mask_probe.py --mask   (exits 2 until the emission lands)
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys

AEON = pathlib.Path(__file__).resolve().parent.parent

# `(0) 2006/12920 :        ParallaxConfig_Rocking_Slow:` — an .lst body symbol row.
SYM_RE = re.compile(r"^\(0\) \d+/([0-9A-F]+) :\s+([A-Za-z_][A-Za-z0-9_]*):\s*$", re.M)

# The .emp scalar sizes the two structs use. `*u8` and Label are ROM pointers.
TYPE_SIZES = {"u8": 1, "i8": 1, "u16": 2, "i16": 2, "u32": 4, "i32": 4, "*u8": 4, "Label": 4}

FACTOR_LOCKED_S1 = 15   # parallax_dsl.emp: FACTOR_0 = $0FF -> s1 = 15 ("term zero")
NO_DEFORM_SHIFT = 15    # the per-band no-deform sentinel


def emp_const(rel: str, name: str) -> int:
    """A `const NAME = <int>` out of an .emp source. Loud when absent, never defaulted."""
    txt = (AEON / rel).read_text(encoding="utf-8")
    m = re.search(rf"^\s*(?:pub\s+)?const\s+{re.escape(name)}\s*=\s*(\$[0-9A-Fa-f]+|\d+)",
                  txt, re.M)
    if not m:
        raise SystemExit(f"FAIL: cannot find `const {name}` in {rel} — the band stride is "
                         "derived from it and a guess would mis-read every band")
    v = m.group(1)
    return int(v[1:], 16) if v.startswith("$") else int(v)


def struct_offsets(path: pathlib.Path, name: str) -> dict:
    """Field -> (offset, size) for a `pub struct NAME { field: type, ... }` declaration.

    Deliberately minimal: scalar and pointer fields only, which is all the two records
    contain. An unknown type is a loud error — never a guessed offset."""
    src = path.read_text(encoding="utf-8")
    m = re.search(r"pub struct " + re.escape(name) + r"\s*(?:\(size:\s*\d+\)\s*)?\{", src)
    if not m:
        raise SystemExit(f"FAIL: struct {name} not found in {path}")
    body = src[m.end():]
    body = body[:body.index("}")]
    out, off = {}, 0
    for line in body.splitlines():
        line = line.split("//")[0].strip().rstrip(",")
        fm = re.match(r"([A-Za-z_][A-Za-z0-9_]*)\s*:\s*([*A-Za-z0-9_]+)$", line)
        if not fm:
            continue
        fname, ftype = fm.groups()
        if ftype not in TYPE_SIZES:
            raise SystemExit(f"FAIL: {name}.{fname} has type {ftype!r} this probe cannot size")
        out[fname] = (off, TYPE_SIZES[ftype])
        off += TYPE_SIZES[ftype]
    out["__sizeof__"] = off
    return out


def read_be(rom: bytes, addr: int, size: int) -> int:
    return int.from_bytes(rom[addr:addr + size], "big")


def field(rom: bytes, base: int, layout: dict, fname: str) -> int:
    off, size = layout[fname]
    return read_be(rom, base + off, size)


def claims(rom_path: pathlib.Path, lst_path: pathlib.Path) -> int:
    rom = rom_path.read_bytes()
    syms = {}
    for m in SYM_RE.finditer(lst_path.read_text(encoding="utf-8", errors="replace")):
        syms.setdefault(m.group(2), int(m.group(1), 16))

    cfg = struct_offsets(AEON / "engine" / "structs.emp", "parallax_config")
    band = struct_offsets(AEON / "engine" / "level" / "parallax.emp", "band_entry")
    # THE STRIDE IS band_record, NOT band_entry, AND THE TWO ARE NOT THE SAME NUMBER.
    # `band_entry` is the 10-byte LEGACY prefix; what the emitter actually lays out is
    # `band_record` = band_entry + the capability tails, and this game declares
    # CAP_FACTOR_CURVE, so the shipped stride is 20. Striding by 10 read every band from
    # index 1 on out of the middle of the previous record and reported the garbage as
    # claim failures (15 of them, all at band >= 1, measured 2026-08-27 -- band 0 is the
    # one index a wrong stride cannot corrupt, which is exactly why it looked plausible).
    #
    # DERIVED FROM ram.emp's THREE MIRRORS, which are the same numbers that size
    # Parallax_Shadow_Bands, rather than from `band_record` itself: band_record is
    # declared `(size: <expression>)` over capability constants this file's deliberately
    # minimal parser cannot evaluate, and a parser that guessed would be worse than one
    # that reads the mirrors parallax.emp already pins against the real struct.
    stride = (emp_const("engine/ram.emp", "BAND_ENTRY_LEN")
              + emp_const("engine/ram.emp", "BAND_EXT_BYTES")
              + emp_const("engine/ram.emp", "BAND_CURVE_BYTES"))
    if stride < band["__sizeof__"]:
        raise SystemExit(
            f"FAIL: derived band stride {stride} is smaller than sizeof(band_entry) "
            f"{band['__sizeof__']} — ram.emp's mirrors and parallax.emp's struct disagree, "
            "and every band read below would be wrong")

    need = ["DeformTable_Zero", "DeformTable_Shimmer", "DeformTable_Rocking",
            "DeformTable_Perspective", "ParallaxConfig_Rocking_Slow",
            "ParallaxConfig_Rocking", "ParallaxConfig_Rocking_Fast",
            "ParallaxConfig_Perspective_Subtle", "ParallaxConfig_Perspective",
            "ParallaxConfig_Perspective_Dramatic", "ParallaxConfig_OJZ_Default",
            "ParallaxConfig_OJZ_Underwater"]
    missing = [n for n in need if n not in syms]
    if missing:
        print(f"FAIL: symbols missing from {lst_path}: {missing}")
        return 1

    failures = []

    # (1) The two table facts the comptime guards cannot see.
    zero_at = syms["DeformTable_Zero"]
    nonzero = [i for i in range(256) if rom[zero_at + i] != 0]
    if nonzero:
        failures.append(f"DeformTable_Zero is NOT all-zero: first non-zero at +{nonzero[0]} "
                        f"(byte ${rom[zero_at + nonzero[0]]:02X}) — Rocking's Accept-not-"
                        "Factor0Lock reasoning rests on this table sampling to 0")
    shim_at = syms["DeformTable_Shimmer"]
    if all(rom[shim_at + i] == 0 for i in range(256)):
        failures.append("DeformTable_Shimmer is all-zero — Perspective's artifact-reachable "
                        "reasoning rests on this table being live")

    def check_family(names, v_table, bg_table, want_dsb, verdict):
        for n in names:
            base = syms[n]
            v = field(rom, base, cfg, "pcfg_v_deform_table_bg")
            if v != syms[v_table]:
                failures.append(f"{n}: pcfg_v_deform_table_bg ${v:X} != {v_table} "
                                f"${syms[v_table]:X} — not the per-column scene the "
                                "declaration adjudicates")
            bg = field(rom, base, cfg, "pcfg_deform_table_bg")
            if bg != syms[bg_table]:
                failures.append(f"{n}: pcfg_deform_table_bg ${bg:X} != {bg_table} "
                                f"${syms[bg_table]:X}")
            count = field(rom, base, cfg, "pcfg_band_count")
            if count != len(want_dsb):
                failures.append(f"{n}: band_count {count} != {len(want_dsb)}")
                continue
            for i, dsb_want in enumerate(want_dsb):
                b = base + cfg["__sizeof__"] + i * stride
                fb_s1 = field(rom, b, band, "band_factor_b_s1")
                if fb_s1 != FACTOR_LOCKED_S1:
                    failures.append(f"{n} band {i}: factor_b_s1 {fb_s1} != 15 — plane B is "
                                    "not FACTOR_0-locked, the family's base premise")
                dsb = field(rom, b, band, "band_deform_shift_b")
                if dsb != dsb_want:
                    failures.append(f"{n} band {i}: deform_shift_b {dsb} != authored {dsb_want}")
        print(f"  {', '.join(n.removeprefix('ParallaxConfig_') for n in names)}: {verdict}")

    # (2) Rocking: locked factor + live dsb against the ZERO table => artifact impossible.
    check_family(["ParallaxConfig_Rocking_Slow", "ParallaxConfig_Rocking",
                  "ParallaxConfig_Rocking_Fast"],
                 "DeformTable_Rocking", "DeformTable_Zero", [4],
                 "per-column ON, fb locked, dsb 4 vs ALL-ZERO table -> plane-B HScroll "
                 "identically 0, artifact impossible; Accept = conservative spelling of a "
                 "true factor0 claim (comptime cannot see table contents)")

    # (3) Perspective: locked factor + live dsb against SHIMMER => artifact reachable.
    check_family(["ParallaxConfig_Perspective_Subtle", "ParallaxConfig_Perspective",
                  "ParallaxConfig_Perspective_Dramatic"],
                 "DeformTable_Perspective", "DeformTable_Shimmer", [15, 15, 15, 4, 2],
                 "per-column ON, fb locked, dsb live on hills/ground vs a LIVE table -> "
                 "artifact reachable on those rows; Accept = a real ship-it decision")

    # (4) The installable configs never enter per-column mode.
    for n in ("ParallaxConfig_OJZ_Default", "ParallaxConfig_OJZ_Underwater"):
        v = field(rom, syms[n], cfg, "pcfg_v_deform_table_bg")
        if v != 0:
            failures.append(f"{n}: pcfg_v_deform_table_bg ${v:X} != 0 — an INSTALLABLE "
                            "config entered per-column mode; the 'no runtime subject' "
                            "claim in DEFERRED_WORK is stale")
    print("  OJZ_Default, OJZ_Underwater (the installable set): no per-column table — "
          "the shipped game never enters per-column mode; no runtime artifact subject")

    if failures:
        print(f"FAIL — {len(failures)} claim(s) do not hold against {rom_path.name}:")
        for f in failures:
            print(f"  {f}")
        return 1
    print(f"left_col_mask_probe --claims: OK against {rom_path.name} "
          f"(offsets derived: parallax_config {cfg['__sizeof__']} B, "
          f"band_entry {band['__sizeof__']} B, band_record stride {stride} B)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--claims", action="store_true")
    ap.add_argument("--mask", action="store_true")
    ap.add_argument("--rom", default=str(AEON / "s4.debug.bin"))
    ap.add_argument("--lst", default=str(AEON / "s4.debug.lst"))
    args = ap.parse_args()
    if args.mask:
        print("left_col_mask_probe --mask: NO SUBJECT — the SpriteMask engine emission has "
              "not landed (scene() refuses the variant; see docs/DEFERRED_WORK.md 'Sprite "
              "mask for per-column V-scroll'). This arm gains its oracle-bus checks with "
              "that parcel; the check list is in this file's docstring. Refusing to render "
              "an unmeasurable as green.")
        return 2
    if args.claims:
        return claims(pathlib.Path(args.rom), pathlib.Path(args.lst))
    print("nothing to do: pass --claims or --mask")
    return 2


if __name__ == "__main__":
    sys.exit(main())
