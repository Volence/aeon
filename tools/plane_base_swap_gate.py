#!/usr/bin/env python3
"""ITEM 11a's BYTE GOLDEN — is the mid-frame nametable-base change actually in the ROM?

EFFECTS-W1 DoD item 11a (`parcel/item11a-midframe-base`, 2026-09-03). One question:

    `OJZ_BaseSwap`, read out of THIS ROM at THIS listing's address, is a sparse raster
    program of TWO `OP_SET_REG` ops: the first carries the VDP word that re-points Plane
    A's nametable base at the address Plane B's nametable actually occupies, and the
    second — at a later line — puts it back to Plane A's own. The pair is a BAND; the
    first op alone is a swap that runs to the bottom of the display.

⚠ THE SECOND OP JOINED 2026-09-04 (EFFECTS-W1 F2) AND THE GATE'S SUBJECT CHANGED WITH IT.
This file used to derive an 11-word single-fire image and pass on it. That was a correct
measurement of the wrong claim: it asked "are the words right" and never "is there a band",
and the two came apart the moment the fire line moved to 3, where a single ON edge covers
the WHOLE SCREEN and there is nothing to see. Deriving both edges is what makes the shape
of the answer match the shape of the question.

WHY A SOURCE-LEVEL CHECK CANNOT ANSWER IT, stated precisely so this is not a duplicate:

  * The `.emp` fixture's own `first_mismatch` pin compares the encoder's output against a
    hand-authored word list. That is a comptime value against a comptime value: it proves
    the DSL and the hand twin agree, and it would go on passing if the `pub data` were
    DEBUG-gated the wrong way round, emitted zero words, or landed somewhere no installer
    points at. It never looks at a byte.
  * `tools/test_raster_cycle_table_lint.py` proves the lab table has a row for it and that
    the row is imported. That is the INSTALLER half; it says nothing about the program.
  * `tools/effects_gates.py` boots an emulator per gate and is the pixel half. It cannot
    live in build.sh and it did not run here.

So: a fixture that agrees with itself and a table row that names it is "green and absent",
and this file is the half that catches it.

THE EXPECTATION IS DERIVED FROM FILES THE FIXTURE DOES NOT AUTHOR, which is what makes the
register-word arm an independent measurement rather than a restatement:

  * `VRAM_PLANE_A` / `VRAM_PLANE_B`   engine/system/constants.emp
  * `vdp_base_shift(PlaneA)`          engine/vdp.emp, the `match` arm — the same fold
                                      engine/system/boot_data.emp derives reg $02 from
  * `OP_SET_REG`, `RASTER_ARM_PARK`,
    `RASTER_OPS_END`                  engine/effects/raster.emp
  * the two edge lines                games/sonic4/data/effects/ojz_effects.emp
    (`OJZ_BASE_SWAP_LINE`, `OJZ_BASE_SWAP_END_LINE`)

Change the fixture to write any other reg $02 word — including one that re-points Plane A
at its OWN base, which is a silent no-op on screen — and the register arm goes red naming
both addresses. That mutation is the gate's red-first proof (see the parcel's evidence).

BOTH SHAPES ARE ASSERTED, IN OPPOSITE DIRECTIONS, and the release arm is not decoration.
The only installer is `Debug_BandDemoHotkey`, whose body emits zero bytes in the release
shape, so an unconditionally-emitted program would be a dormant scaffold in the ROM the
owner ships — the defect `OJZ_BandDemo`'s own gate note in ojz_effects.emp records being
made the wrong way round first. So:

    --shape debug     the 15 words are present and exactly the derived image
    --shape release   the symbol emits ZERO bytes (its label collapses onto its
                      neighbour's address, exactly as OJZ_BandDemo's does)

WHAT IT CANNOT SAY. This is a ROM-image check. It proves the op and its argument reach the
ROM; it does NOT prove the VDP draws Plane B's map in the Plane-A layer between the two
edge lines.
That needs an emulator, which this lane does not have, and it is TAGGED in the parcel's
DEFERRED_WORK entry. Do not read a green here as the picture having been looked at.

REFUSES TO BE VACUOUS. A missing symbol, a missing neighbour, a gap that is neither the
full image nor zero, or a constant this file cannot parse out of its source is reported as
UNMEASURABLE (exit 2), never as a pass.

Usage:
    tools/plane_base_swap_gate.py --shape debug|release [--lst s4.lst] [--rom s4.bin]
                                 [--built-after <epoch s>]

Exit 0 = the mechanism is in the ROM (or correctly absent). 1 = a real failure.
2 = UNMEASURABLE.
"""

import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CONSTANTS = os.path.join(REPO, "engine", "system", "constants.emp")
VDP = os.path.join(REPO, "engine", "vdp.emp")
RASTER = os.path.join(REPO, "engine", "effects", "raster.emp")
FIXTURE = os.path.join(REPO, "games", "sonic4", "data", "effects", "ojz_effects.emp")

# The symbol under test and the neighbour that BOUNDS it. The neighbour is named rather
# than found, band_drift_golden's rule: "the next label in address order" would silently
# accept a zero-length symbol as a correct one whenever another label happened to share
# the address, which is exactly the release shape's own signature.
SYM = "OJZ_BaseSwap"
NEXT_SYM = "OJZ_TestPal"

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
            f"produce a word mismatch that is really a parse failure")
    return _int(m.group(1))


def vdp_base_shift(base_name):
    """`vdp_base_shift`'s match arm for one VdpBase variant, out of engine/vdp.emp.

    Read from the FUNCTION BODY rather than from a table typed here: the shift is what
    turns a VRAM address into the register byte, and boot_data.emp folds reg $02 through
    this same function. A copy would drift the day the fold does, which is the whole
    failure `vdp_base_reg` was introduced to remove.
    """
    src = _read(VDP)
    m = re.search(r"comptime fn vdp_base_shift\s*\([^)]*\)\s*->\s*int\s*\{(.*?)\n\}", src, re.S)
    if not m:
        raise Unmeasurable(
            "cannot find `comptime fn vdp_base_shift` in engine/vdp.emp — the fold this "
            "gate re-derives the reg $02 byte through has been renamed or reshaped")
    arm = re.search(rf"^\s*{re.escape(base_name)}\s*=>\s*(\d+)\s*,", m.group(1), re.M)
    if not arm:
        raise Unmeasurable(
            f"`vdp_base_shift` has no `{base_name} => <n>` arm in engine/vdp.emp; its arms "
            f"are {sorted(set(re.findall(r'^\\s*(\\w+)\\s*=>', m.group(1), re.M)))}")
    return int(arm.group(1))


def expected_words(line, end_line, plane_b, plane_a, shift, op_set_reg, park, ops_end):
    """The 15-word image `raster_program([fire(line, ...), fire(end_line, ...)])` emits.

    A PURE FUNCTION over the eight derived facts, so the derivation can be exercised
    without a ROM at all (tools/test_plane_base_swap_gate.py). The framing is the sparse
    tier's documented schedule — one header word, two priming records, ONE RECORD PER
    EDGE, the terminator — and every arm follows `arm_at(L, i)` over the fire-line list
    L = [0, 1, line - 1, end_line - 1]:

        record 0 (priming)   $8A00 | (L[2] - L[1] - 1)  = the gap to the ON edge
        record 1 (priming)   $8A00 | (L[3] - L[2] - 1)  = the gap from ON to OFF
        record 2 (the ON edge)   park — i + 2 is past the end of L
        record 3 (the OFF edge)  park

    TWO EDGES IS THE SUBJECT, NOT AN IMPLEMENTATION DETAIL (EFFECTS-W1 F2, 2026-09-04).
    Until then this derived an 11-word single-fire image, and that image was CORRECT for
    the program in the ROM and still described something invisible: one OP_SET_REG has no
    OFF edge, so at `line` 3 it re-pointed Plane A for the whole display and there was no
    band to see. The gate went green on it, because "the words are right" and "the band
    exists" are different claims and only the first one was ever being asked. The second
    edge is what makes the interval finite, so the derivation is now shaped like a band:
    an ON word, an OFF word, and an arm between them that names the distance.
    """
    word = 0x8200 | (plane_b >> shift)
    home = 0x8200 | (plane_a >> shift)
    if word == home:
        raise Unmeasurable(
            f"Plane A (${plane_a:04X}) and Plane B (${plane_b:04X}) fold to the SAME reg "
            f"$02 byte at shift {shift}, so there is no mid-frame swap to look for. The "
            f"`.emp` fixture refuses this by name too; seeing it here means that ensure is "
            f"no longer running")
    fire_line = line - 1                       # an effect on screen line M fires at M-1
    end_fire_line = end_line - 1
    if end_fire_line <= fire_line:
        raise Unmeasurable(
            f"the OFF edge (screen line {end_line}, fire line {end_fire_line}) does not "
            f"follow the ON edge (screen line {line}, fire line {fire_line}). "
            f"`fire_lines` refuses a non-ascending program by name, so this gate cannot "
            f"be looking at a built ROM with these two constants — do NOT read it as a "
            f"byte mismatch")
    arm0 = 0x8A00 | (fire_line - 1 - 1)        # raster_arm(1, fire_line)
    arm1 = 0x8A00 | (end_fire_line - fire_line - 1)
    if not 0 <= (fire_line - 2) <= 255:
        raise Unmeasurable(
            f"screen line {line} gives a priming gap of {fire_line - 2}, which is not a "
            f"legal reg $0A reload — the fixture's line is outside the schedule this gate "
            f"models")
    if not 0 <= (end_fire_line - fire_line - 1) <= 255:
        raise Unmeasurable(
            f"the ON->OFF gap is {end_fire_line - fire_line - 1} lines (screen lines "
            f"{line} -> {end_line}), which is not a legal reg $0A reload — the band is "
            f"wider than one reload of the schedule this gate models")
    return [
        0x0000,                 # pal_dirty_mask — a register op writes no CRAM
        arm0, 0x0000,           # fire 0 — priming; schedules the ON edge
        arm1, 0x0000,           # fire 1 — priming; schedules the gap ON -> OFF
        park, 0x0001,           # fire 2 — the ON edge, one op
        op_set_reg, word,       # OP_SET_REG, then reg $02 <- Plane B's nametable
        park, 0x0001,           # fire 3 — the OFF edge, one op
        op_set_reg, home,       # OP_SET_REG, then reg $02 <- Plane A's own base again
        park, ops_end,          # terminator
    ]


def classify_gap(gap, image_bytes):
    """'emitted' / 'absent' / None, from the distance between the two labels.

    Pure, and split out for the same reason `unreachable_presets` is in the raster-cycle
    lint: the two-sided shape assertion is the judgement this gate adds, so it is the part
    that gets exercised without a build. `None` means the gate cannot say, and the caller
    must report UNMEASURABLE rather than choose.
    """
    if gap == image_bytes:
        return "emitted"
    if gap == 0:
        return "absent"
    return None


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
            f"at that label; a missing symbol is not a pass — the program may simply not "
            f"have been emitted at all")
    return labels[name]


def main():
    args = sys.argv[1:]

    def opt(flag, default=None):
        return args[args.index(flag) + 1] if flag in args else default

    shape = opt("--shape")
    # THE DEFAULTS FOLLOW --shape, and before 2026-09-04 they did not. Both defaulted to
    # the RELEASE artifact whatever --shape said, so `--shape debug` with no --lst read
    # s4.lst, found OJZ_BaseSwap correctly absent (it is DEBUG-gated), and reported
    # "emits NO bytes in the DEBUG shape, so item 11a's mechanism is not in this ROM at
    # all" — a confident FAIL about an artifact it had not opened. It cost a real
    # investigation on 2026-09-04 while diagnosing why the owner could not see the band.
    # This gate asserts OPPOSITE things per shape, which is exactly why the shape must
    # pick the artifact: a fixed default guarantees one of the two runs is a lie.
    # An explicit --lst/--rom still wins, so the mismatched pairing stays expressible on
    # purpose — that is the poison this gate's own fixtures need.
    _DEFAULTS = {"debug": ("s4.debug.lst", "s4.debug.bin"),
                 "release": ("s4.lst", "s4.bin")}
    _dl, _dr = _DEFAULTS.get(shape, ("s4.lst", "s4.bin"))
    lst = opt("--lst", _dl)
    rom_name = opt("--rom", _dr)
    built_after = opt("--built-after")
    lst_path = lst if os.path.isabs(lst) else os.path.join(REPO, lst)
    rom_path = rom_name if os.path.isabs(rom_name) else os.path.join(REPO, rom_name)

    try:
        if shape not in ("debug", "release"):
            raise Unmeasurable(
                f"--shape must be `debug` or `release` (got {shape!r}). This gate asserts "
                f"OPPOSITE things in the two shapes — the words present in DEBUG, the "
                f"symbol empty in release — so it cannot guess, and guessing from the "
                f"artifact's NAME would be a name standing in for a behaviour")
        for p in (lst_path, rom_path):
            if not os.path.isfile(p):
                raise Unmeasurable(f"{p} does not exist")
        if built_after is not None:
            # Temporal provenance, band_drift_golden's rule: a sigil listing carries no ROM
            # identity of its own, so "both post-date the instant this invocation started
            # sigil" is the check it supports, and it excludes a previous build by
            # construction.
            try:
                t0 = float(built_after)
            except ValueError:
                raise Unmeasurable(f"--built-after {built_after!r} is not a number of seconds")
            for p in (lst_path, rom_path):
                if os.path.getmtime(p) < t0:
                    raise Unmeasurable(
                        f"{os.path.basename(p)} predates this invocation's sigil run; it is "
                        f"a PREVIOUS build's artifact and reading it would measure the past")

        # ---- the expectation, out of five sources the fixture does not author -----
        plane_a = emp_const(CONSTANTS, "VRAM_PLANE_A")
        plane_b = emp_const(CONSTANTS, "VRAM_PLANE_B")
        shift = vdp_base_shift("PlaneA")
        op_set_reg = emp_const(RASTER, "OP_SET_REG")
        park = emp_const(RASTER, "RASTER_ARM_PARK")
        ops_end = emp_const(RASTER, "RASTER_OPS_END")
        line = emp_const(FIXTURE, "OJZ_BASE_SWAP_LINE")
        end_line = emp_const(FIXTURE, "OJZ_BASE_SWAP_END_LINE")

        want = expected_words(line, end_line, plane_b, plane_a, shift, op_set_reg, park,
                              ops_end)
        image_bytes = 2 * len(want)

        labels = lst_labels(lst_path)
        addr = at(labels, SYM, lst_path)
        nxt = at(labels, NEXT_SYM, lst_path)
        gap = nxt - addr

        print(f"plane_base_swap_gate [{os.path.basename(lst_path)}, shape={shape}]")
        print(f"  derived: Plane A ${plane_a:04X} -> reg $02 ${0x8200 | (plane_a >> shift):04X}   "
              f"Plane B ${plane_b:04X} -> reg $02 ${0x8200 | (plane_b >> shift):04X}   "
              f"(vdp_base_shift PlaneA = {shift})")
        print(f"  derived: OP_SET_REG {op_set_reg}, arm park ${park:04X}, ops end ${ops_end:04X}")
        print(f"  derived: BAND screen lines {line}..{end_line} — ON edge at {line} "
              f"(fire line {line - 1}), OFF edge at {end_line} (fire line {end_line - 1}), "
              f"{end_line - line} line(s) wide")
        print(f"  {SYM} at ${addr:06X}, {NEXT_SYM} at ${nxt:06X} — {gap} byte(s) between")

        state = classify_gap(gap, image_bytes)
        if state is None:
            raise Unmeasurable(
                f"`{SYM}` occupies {gap} bytes, which is neither the {image_bytes}-byte "
                f"program this gate derived nor the 0 bytes a correctly DEBUG-gated symbol "
                f"emits in the release shape. Either the two symbols are no longer adjacent "
                f"in emission order (they are declared adjacently in "
                f"games/sonic4/data/effects/ojz_effects.emp), or the program's shape moved — "
                f"do NOT read this as a byte mismatch")

        if shape == "release":
            if state != "absent":
                print(f"plane_base_swap_gate: FAIL — `{SYM}` emits {gap} bytes in the "
                      f"RELEASE shape. Its only installer, Debug_BandDemoHotkey, emits zero "
                      f"bytes there, so this is a raster program in the shipped ROM that "
                      f"nothing in that shape can point the raster engine at. Restore the "
                      f"`if DEBUG == 1` / else-empty gate on the `pub data` in "
                      f"games/sonic4/data/effects/ojz_effects.emp.")
                return 1
            print(f"plane_base_swap_gate: OK — `{SYM}` emits no bytes in the release shape, "
                  f"as its DEBUG-only installer requires")
            return 0

        if state != "emitted":
            print(f"plane_base_swap_gate: FAIL — `{SYM}` emits NO bytes in the DEBUG shape, "
                  f"so item 11a's mechanism is not in this ROM at all. The `pub data`'s "
                  f"`if DEBUG == 1` gate is inverted, or the fixture stopped being emitted.")
            return 1

        with open(rom_path, "rb") as f:
            rom = f.read()
        if addr + image_bytes > len(rom):
            raise Unmeasurable(
                f"`{SYM}` at ${addr:06X} + {image_bytes} bytes runs past the end of the "
                f"{len(rom)}-byte ROM")
        got = [int.from_bytes(rom[addr + 2 * i:addr + 2 * i + 2], "big") for i in range(len(want))]

        bad = 0
        for i, (g, w) in enumerate(zip(got, want)):
            ok = g == w
            bad += 0 if ok else 1
            print(f"  word {i:2d}  ${addr + 2 * i:06X}  {g:04X}  want {w:04X}  "
                  f"{'OK' if ok else 'MISMATCH'}")

        # The item's own claim, asserted by name on top of the whole-image compare, because
        # the image compare would blame "index 8" for what is really "the op points at the
        # wrong plane" — and because these are the two words the DoD row is about.
        if got[7] != op_set_reg:
            print(f"        word 7 is the ON EDGE'S OPCODE and it is not OP_SET_REG "
                  f"({op_set_reg}). Item 11a IS the OP_SET_REG path — "
                  f"engine/effects/raster.emp's `.op_set_reg` arm, whose whole argument is "
                  f"one `$8xxx` register word.")
        if got[8] != want[8]:
            decoded = (got[8] & 0xFF) << shift
            print(f"        word 8 is the ON EDGE'S REGISTER WORD. ${got[8]:04X} re-points "
                  f"Plane A at VRAM ${decoded:04X}; item 11a needs Plane B's nametable, "
                  f"${plane_b:04X}. If it decodes to ${plane_a:04X} the op writes the base "
                  f"Plane A already has and the band is invisible on screen while every "
                  f"other check here stays green.")
        if got[11] != op_set_reg:
            print(f"        word 11 is the OFF EDGE'S OPCODE and it is not OP_SET_REG "
                  f"({op_set_reg}). Without a second OP_SET_REG there is no OFF edge, and "
                  f"the swap runs from its line to the BOTTOM OF THE DISPLAY — which is "
                  f"not a band. That is the exact program that shipped at 8bf6df74 and "
                  f"that the owner reported he could not see.")
        if got[12] != want[12]:
            decoded = (got[12] & 0xFF) << shift
            print(f"        word 12 is the OFF EDGE'S REGISTER WORD. ${got[12]:04X} "
                  f"re-points Plane A at VRAM ${decoded:04X}; closing the band needs Plane "
                  f"A's OWN nametable, ${plane_a:04X} — the word Flush_VDP_Shadow writes at "
                  f"the next frame top. If it decodes to ${plane_b:04X} instead, BOTH edges "
                  f"write the same base: the second op costs its cycles, changes nothing, "
                  f"and the band still runs to the bottom of the screen.")
        if got[8] == got[12]:
            print(f"        BOTH EDGES CARRY THE SAME WORD (${got[8]:04X}). Whatever the "
                  f"two words are, a band needs them to DIFFER — this program has an "
                  f"interval with no boundary at either end of it.")

        if bad:
            print(f"plane_base_swap_gate: FAIL — {bad} of {len(want)} word(s) differ")
            return 1
        print(f"plane_base_swap_gate: OK — the mid-frame base BAND is in this ROM: "
              f"OP_SET_REG ${got[8]:04X} at screen line {line} re-points Plane A at "
              f"${plane_b:04X} (Plane B's nametable), and OP_SET_REG ${got[12]:04X} at "
              f"screen line {end_line} puts it back to ${plane_a:04X} — a {end_line - line}"
              f"-line band, closed mid-frame rather than at the VBlank shadow flush")
        return 0

    except Unmeasurable as e:
        print(f"plane_base_swap_gate: UNMEASURABLE — {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
