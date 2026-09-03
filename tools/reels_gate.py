#!/usr/bin/env python3
"""ITEM 10a's BYTE GOLDEN — is the "reels" per-strip vertical scroll source in the ROM?

EFFECTS-W1 DoD item 10a (`parcel/item10a-reels`, 2026-09-03). One question:

    `OJZ_Reel_Speed`, read out of THIS ROM at THIS listing's address, holds
    REEL_BAND_COUNT independently-authored, pairwise-DISTINCT per-frame phase
    increments — the "reel source" `OJZ_Reels_Fill` (games/sonic4/data/effects/
    ojz_effects.emp) advances every frame and composes onto the per-column VSRAM
    buffer's BG words. And `OJZ_Reels_Fill` itself, the routine that does that
    composing, actually reaches the ROM.

WHY A SOURCE-LEVEL CHECK CANNOT ANSWER IT, plane_base_swap_gate.py's reason, restated
for this fixture:

  * The `.emp` `ensure`s (distinctness, the REEL_BAND_COUNT * REEL_COLS_PER_BAND
    identity) are comptime-vs-comptime. They prove the AUTHORED numbers have the
    property; they say nothing about whether the `pub data`/`pub proc` carrying them
    actually emitted a byte, or emitted it DEBUG-gated the wrong way round.
  * `tools/effects_gates.py` boots an emulator per gate and is the pixel half. It did
    not run here (no emulator in a subagent) — see the TAGGED section below.

So: a fixture that agrees with itself is "green and possibly absent from the ROM
entirely", and this file is the half that reads the actual bytes.

THE EXPECTATION IS DERIVED FROM FILES THE FIXTURE DOES NOT AUTHOR-TWICE:

  * `REEL_BAND_COUNT`      games/sonic4/config/constants.emp
  * `OJZ_REEL_SPEEDS`      games/sonic4/data/effects/ojz_effects.emp (the array literal
                           itself — re-parsed, not re-typed, so a hand edit to either
                           the source array or the emitted bytes is caught independently)

Change the array's values without moving REEL_BAND_COUNT and this gate's byte compare
goes red naming the mismatched index. Change any value so two entries collide and the
gate's own distinctness check goes red BEFORE the ROM is even opened — the same
property games/sonic4/data/effects/ojz_effects.emp's `distinct5()` ensure already
proves at compile time, measured here a second, independent way, against the actual
image.

THREE SYMBOLS, TWO GAPS. `OJZ_Reel_Speed` (data) is declared immediately before
`OJZ_Reels_Fill` (code), which is declared immediately before `OJZ_TestPal` (the next
real content in games/sonic4/data/effects/ojz_effects.emp) — so the label arithmetic
plane_base_swap_gate.py uses (gap between two ADJACENT declared symbols is the actual
byte size of the first) applies twice: once for the table, once for the whole proc.

BOTH SHAPES ARE ASSERTED, IN OPPOSITE DIRECTIONS, for OJZ_BaseSwap's reason: nothing in
the release shape can ever set `OJZ_Reel_Active` (`tools/reels_witness.py` is the only
writer, and it pokes a DEBUG-only RAM cell), so an unconditionally-emitted table or
proc would be a dormant scaffold in the ROM the owner ships.

    --shape debug     OJZ_Reel_Speed is exactly REEL_BAND_COUNT bytes and its content
                      is the derived image; OJZ_Reels_Fill is non-empty (code exists —
                      this gate does NOT decode its instruction bytes; see below)
    --shape release   BOTH symbols emit ZERO bytes (their labels collapse onto
                      OJZ_TestPal's address, exactly as OJZ_BaseSwap's does)

WHAT IT CANNOT SAY, AND WHY OJZ_Reels_Fill's BYTES ARE NOT DECODED. Unlike OJZ_BaseSwap
— an 11-word DATA program with a fixed, DSL-derived shape — OJZ_Reels_Fill is CODE: a
loop with a `dbf` and a shift. Pinning a compiler's exact encoding of a loop is
precisely the coupling this tree spends real effort avoiding elsewhere (a sigil
codegen change unrelated to this parcel would false-red a byte-for-byte pin on
`move.b`/`dbf` encodings). So this gate proves the routine's BYTES REACH THE ROM WITH
THE RIGHT SHAPE (present in DEBUG with a real, nonzero size; absent in release) and
proves the DATA it reads is exactly what the source declares; it does NOT prove the
loop composes those bytes onto VSRAM correctly at runtime, and it does NOT prove
anything reaches the screen. That is TAGGED for the controller's emulator pass
(tools/reels_witness.py), exactly as item 11a's gate tags its own on-screen half.

REFUSES TO BE VACUOUS. A missing symbol, a missing neighbour, a gap that is neither the
full image nor zero (nor a plausible nonzero code size, for the proc), or a constant
this file cannot parse out of its source is reported as UNMEASURABLE (exit 2), never as
a pass.

Usage:
    tools/reels_gate.py --shape debug|release [--lst s4.lst] [--rom s4.bin]
                        [--built-after <epoch s>]

Exit 0 = the mechanism is in the ROM (or correctly absent). 1 = a real failure.
2 = UNMEASURABLE.
"""

import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

GAME_CONSTANTS = os.path.join(REPO, "games", "sonic4", "config", "constants.emp")
FIXTURE = os.path.join(REPO, "games", "sonic4", "data", "effects", "ojz_effects.emp")

SPEED_SYM = "OJZ_Reel_Speed"
FILL_SYM = "OJZ_Reels_Fill"
# The symbol immediately after OJZ_Reels_Fill in emission order. NOT OJZ_TestPal — the
# OJZ_Reels block sits at the END of games/sonic4/data/effects/ojz_effects.emp (moved
# there deliberately so inserting it does not fall BETWEEN OJZ_BaseSwap and OJZ_TestPal,
# which would break tools/plane_base_swap_gate.py's own adjacency assumption for item
# 11a — measured red the first time this file was drafted). The module's last content
# is followed by whatever games/sonic4/map.toml's `order` list names next after the
# "OJZ_TestRaster" section head this whole module IS (map.toml: `"OJZ_TestRaster",
# "ObjDef_Static",`), which is `ObjDef_Static` (games/sonic4/data/effects/ojz_effects.emp
# ends and the object-index data begins).
NEXT_SYM = "ObjDef_Static"

_LST_LABEL = re.compile(r"^\(0\)\s+\d+/([0-9A-Fa-f]+)\s+:\s+([A-Za-z_$][\w$.]*):")


class Unmeasurable(Exception):
    pass


def _read(path):
    if not os.path.isfile(path):
        raise Unmeasurable(f"{path} does not exist")
    with open(path, "r", errors="replace") as f:
        return f.read()


def _int(raw):
    return int(raw[1:], 16) if raw.startswith("$") else int(raw)


def emp_const(path, name):
    """A `const NAME = <int literal>` out of an `.emp`, or UNMEASURABLE naming both."""
    m = re.search(rf"^\s*(?:pub\s+)?const\s+{re.escape(name)}\s*=\s*(\$[0-9A-Fa-f]+|-?\d+)\s*(?://.*)?$",
                  _read(path), re.M)
    if not m:
        raise Unmeasurable(
            f"cannot find `const {name} = <literal>` in {os.path.relpath(path, REPO)} — "
            f"this gate DERIVES its expectation from that declaration, and guessing would "
            f"produce a byte mismatch that is really a parse failure")
    return _int(m.group(1))


def emp_int_array(path, name):
    """The literal ints inside `const NAME: [T; N] = [a, b, c, ...]`, in source order.

    Pure text parse, deliberately: re-typing the values as a second Python list would
    make this a restatement rather than a re-derivation, exactly the gap OJZ_BaseSwap's
    header explains for its own five-source expectation.
    """
    m = re.search(rf"^\s*const\s+{re.escape(name)}\s*:\s*\[[^\]]*\]\s*=\s*\[([^\]]*)\]",
                  _read(path), re.M)
    if not m:
        raise Unmeasurable(
            f"cannot find `const {name}: [...] = [...]` in {os.path.relpath(path, REPO)}")
    items = [x.strip() for x in m.group(1).split(",") if x.strip() != ""]
    if not items:
        raise Unmeasurable(f"`{name}` in {os.path.relpath(path, REPO)} parsed to an empty array")
    return [_int(x) for x in items]


def to_bytes_i8(values):
    """Signed byte values -> their two's-complement unsigned byte encoding."""
    out = []
    for v in values:
        if not -128 <= v <= 127:
            raise Unmeasurable(f"{v} does not fit in a signed byte (i8)")
        out.append(v & 0xFF)
    return out


def all_distinct(values):
    return len(set(values)) == len(values)


def lst_labels(path):
    out = {}
    for line in _read(path).splitlines():
        m = _LST_LABEL.match(line)
        if m:
            out.setdefault(m.group(2), int(m.group(1), 16))
    if not out:
        raise Unmeasurable(
            f"{os.path.relpath(path, REPO)} yielded no `(0) n/ADDR : Name:` label lines — "
            f"the listing format changed and this gate cannot locate anything in it")
    return out


def at(labels, name, path):
    if name not in labels:
        raise Unmeasurable(
            f"`{name}` is not in {os.path.relpath(path, REPO)}. This gate reads its bytes "
            f"at that label; a missing symbol is not a pass — the content may simply not "
            f"have been emitted at all")
    return labels[name]


def main():
    args = sys.argv[1:]

    def opt(flag, default=None):
        return args[args.index(flag) + 1] if flag in args else default

    lst = opt("--lst", "s4.lst")
    rom_name = opt("--rom", "s4.bin")
    shape = opt("--shape")
    built_after = opt("--built-after")
    lst_path = lst if os.path.isabs(lst) else os.path.join(REPO, lst)
    rom_path = rom_name if os.path.isabs(rom_name) else os.path.join(REPO, rom_name)

    try:
        if shape not in ("debug", "release"):
            raise Unmeasurable(
                f"--shape must be `debug` or `release` (got {shape!r}). This gate asserts "
                f"OPPOSITE things in the two shapes — the table+proc present in DEBUG, both "
                f"empty in release — so it cannot guess, and guessing from the artifact's "
                f"NAME would be a name standing in for a behaviour")
        for p in (lst_path, rom_path):
            if not os.path.isfile(p):
                raise Unmeasurable(f"{p} does not exist")
        if built_after is not None:
            try:
                t0 = float(built_after)
            except ValueError:
                raise Unmeasurable(f"--built-after {built_after!r} is not a number of seconds")
            for p in (lst_path, rom_path):
                if os.path.getmtime(p) < t0:
                    raise Unmeasurable(
                        f"{os.path.basename(p)} predates this invocation's sigil run; it is "
                        f"a PREVIOUS build's artifact and reading it would measure the past")

        # ---- the expectation, out of the two sources the fixture does not author twice ----
        band_count = emp_const(GAME_CONSTANTS, "REEL_BAND_COUNT")
        speeds = emp_int_array(FIXTURE, "OJZ_REEL_SPEEDS")

        if len(speeds) != band_count:
            raise Unmeasurable(
                f"OJZ_REEL_SPEEDS has {len(speeds)} entries but REEL_BAND_COUNT is "
                f"{band_count} — the source's own `.len == REEL_BAND_COUNT` ensure should "
                f"have refused this build before this gate ever ran")
        if not all_distinct(speeds):
            raise Unmeasurable(
                f"OJZ_REEL_SPEEDS = {speeds} are not pairwise distinct — the whole 'reels' "
                f"claim is that every strip has its OWN rate; two bands sharing one would "
                f"read as a single wide strip. The source's own distinct5() ensure should "
                f"have refused this build before this gate ever ran")

        want_bytes = to_bytes_i8(speeds)

        labels = lst_labels(lst_path)
        speed_addr = at(labels, SPEED_SYM, lst_path)
        fill_addr = at(labels, FILL_SYM, lst_path)
        next_addr = at(labels, NEXT_SYM, lst_path)
        table_gap = fill_addr - speed_addr
        proc_gap = next_addr - fill_addr

        print(f"reels_gate [{os.path.basename(lst_path)}, shape={shape}]")
        print(f"  derived: REEL_BAND_COUNT {band_count}, OJZ_REEL_SPEEDS {speeds}")
        print(f"  {SPEED_SYM} at ${speed_addr:06X}, {FILL_SYM} at ${fill_addr:06X} — "
              f"{table_gap} byte(s) between (the table)")
        print(f"  {FILL_SYM} at ${fill_addr:06X}, {NEXT_SYM} at ${next_addr:06X} — "
              f"{proc_gap} byte(s) between (the proc)")

        if shape == "release":
            bad = []
            if table_gap != 0:
                bad.append(f"`{SPEED_SYM}` emits {table_gap} bytes in the RELEASE shape")
            if proc_gap != 0:
                bad.append(f"`{FILL_SYM}` emits {proc_gap} bytes in the RELEASE shape")
            if bad:
                print("reels_gate: FAIL — " + "; ".join(bad) + ". Nothing in the release "
                      "shape can ever set OJZ_Reel_Active (its only writer is "
                      "tools/reels_witness.py poking a DEBUG-only RAM cell), so this is a "
                      "dormant scaffold in the shipped ROM. Restore the `if DEBUG == 1` / "
                      "else-empty gate on the `pub data` and the `if DEBUG == 1 {}` wrap on "
                      "the `pub proc` in games/sonic4/data/effects/ojz_effects.emp.")
                return 1
            print(f"reels_gate: OK — `{SPEED_SYM}` and `{FILL_SYM}` emit no bytes in the "
                  f"release shape, as their DEBUG-only reason requires")
            return 0

        # shape == "debug"
        # REEL_BAND_COUNT (5) is odd, so games/sonic4/data/effects/ojz_effects.emp
        # carries an explicit `align 2` between the table and OJZ_Reels_Fill (CODE
        # landing at an odd address is a hard 68k address-error crash, [layout.odd-item]
        # is a build error for a proc). An even band_count would need no pad; this gate
        # derives the expected gap the same way the source's own comment does, rather
        # than hardcoding "+1".
        expected_table_gap = band_count + (band_count % 2)
        if table_gap != expected_table_gap:
            raise Unmeasurable(
                f"`{SPEED_SYM}` occupies {table_gap} bytes, not the {expected_table_gap} "
                f"(REEL_BAND_COUNT {band_count}, plus one alignment byte if odd) this gate "
                f"derived. Either the two symbols are no longer adjacent in emission order "
                f"(they are declared adjacently in games/sonic4/data/effects/ojz_effects.emp), "
                f"or the table's declared length or the `align 2` pad moved — do NOT read "
                f"this as a byte mismatch")
        if proc_gap <= 0:
            print(f"reels_gate: FAIL — `{FILL_SYM}` emits NO bytes in the DEBUG shape, so "
                  f"item 10a's reel source is not in this ROM at all. The `if DEBUG == 1` "
                  f"wrap on the `pub proc` is inverted, or the proc stopped being emitted.")
            return 1

        with open(rom_path, "rb") as f:
            rom = f.read()
        if speed_addr + band_count > len(rom):
            raise Unmeasurable(
                f"`{SPEED_SYM}` at ${speed_addr:06X} + {band_count} bytes runs past the "
                f"end of the {len(rom)}-byte ROM")
        got_bytes = list(rom[speed_addr:speed_addr + band_count])

        bad = 0
        for i, (g, w) in enumerate(zip(got_bytes, want_bytes)):
            ok = g == w
            bad += 0 if ok else 1
            signed = g - 256 if g >= 128 else g
            print(f"  band {i}  ${speed_addr + i:06X}  {g:02X} ({signed:+d})  "
                  f"want {w:02X} ({speeds[i]:+d})  {'OK' if ok else 'MISMATCH'}")

        if bad:
            print(f"reels_gate: FAIL — {bad} of {band_count} speed byte(s) differ")
            return 1

        print(f"reels_gate: OK — the reel source is in this ROM: {band_count} pairwise-"
              f"distinct per-band rates {speeds} at ${speed_addr:06X}, and "
              f"`{FILL_SYM}` ({proc_gap} bytes of code) reaches the ROM to advance and "
              f"compose them")
        return 0

    except Unmeasurable as e:
        print(f"reels_gate: UNMEASURABLE — {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
