#!/usr/bin/env python3
"""ITEM 11a's BYTE GOLDEN — is the mid-frame nametable-base change actually in the ROM?

EFFECTS-W1 DoD item 11a (`parcel/item11a-midframe-base`, 2026-09-03). One question:

    `OJZ_BaseSwap`, read out of THIS ROM at THIS listing's address, is a sparse raster
    program of FOUR `OP_SET_REG` ops forming TWO BANDS ON TWO DIFFERENT REGISTERS. The
    TOP band writes reg $04 — Plane B's nametable base — pointing the BACKGROUND layer at
    the FOREGROUND's map, and closes on Plane B's own base. The BOTTOM band writes reg
    $02 — Plane A's base — pointing the FOREGROUND layer at the BACKGROUND's map, and
    closes on Plane A's own. Each pair is a BAND; an ON op alone is a swap that runs to
    the bottom of the display.

⚠ THE SECOND OP JOINED 2026-09-04 (EFFECTS-W1 F2) AND THE GATE'S SUBJECT CHANGED WITH IT.
This file used to derive an 11-word single-fire image and pass on it. That was a correct
measurement of the wrong claim: it asked "are the words right" and never "is there a band",
and the two came apart the moment the fire line moved to 3, where a single ON edge covers
the WHOLE SCREEN and there is nothing to see. Deriving both edges is what makes the shape
of the answer match the shape of the question.

⚠ THE SECOND BAND JOINED LATER THE SAME DAY (EFFECTS-W1 T3) AND MOVED THE GATE'S SUBJECT
AGAIN — 15 words to 23, ONE register to TWO. The owner's ask names two layers, not two
lines: "the foreground in the background layer at the top and the background in the
foreground layer at the bottom of screen". Plane A's base is reg $02 and Plane B's is reg
$04, with DIFFERENT shifts (10 and 13, engine/vdp.emp's `vdp_base_shift` arms), so a gate
written around one register and one shift could not tell the inversion from two copies of
the same borrow. Both registers, both shifts and both selectors are derived below, and the
selectors are asserted DIFFERENT by name — a program whose two bands share a register is
ordered, assembles, shows two bands, and is not what was asked for.

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
  * `vdp_base_shift(PlaneA)` and
    `vdp_base_shift(PlaneB)`          engine/vdp.emp, the `match` arms — the same fold
                                      engine/system/boot_data.emp derives reg $02 and reg
                                      $04 from
  * the two REGISTER NUMBERS          engine/structs.emp, `VdpShadow`'s `vdp_plane_a` /
                                      `vdp_plane_b` field comments. Read from there rather
                                      than typed, because that struct is ALSO the fact the
                                      program depends on for its bottom: both registers are
                                      shadowed, so Flush_VDP_Shadow restores both at frame
                                      top and neither band needs a frame-top reset word. A
                                      register that stopped being shadowed would still have
                                      a number typed here and would silently leak.
  * `OP_SET_REG`, `RASTER_ARM_PARK`,
    `RASTER_OPS_END`                  engine/effects/raster.emp
  * the FOUR edge lines               games/sonic4/data/effects/ojz_effects.emp
    (`OJZ_BASE_SWAP_TOP_LINE`, `OJZ_BASE_SWAP_TOP_END_LINE`, and the two BOT_* lines,
     which the fixture DERIVES as the top band's reflected through RASTER_MAX_FIRE_LINE —
     see `emp_const_expr` below for why this gate reads the expression, not a literal)

Change the fixture to write any other register word — including one that re-points a plane
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
STRUCTS = os.path.join(REPO, "engine", "structs.emp")
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


def emp_const_expr(path, name, env):
    """A `const NAME = <sum of names and integers>` out of an `.emp`, resolved against `env`.

    ADDED FOR T3, and the reason it exists rather than a second literal reader: the bottom
    band's two lines are NOT literals in the fixture. They are DERIVED there —
    `RASTER_MAX_FIRE_LINE - OJZ_BASE_SWAP_TOP_END_LINE` — because the bottom band is the
    top band reflected through the display's horizontal midline, and freezing 159 and 220
    into the source would be two more taste numbers that a display-height change would
    strand. A gate that could only read literals would have forced the fixture to spell
    them as literals, i.e. the measurement would have dictated the design.

    THE GRAMMAR IS DELIBERATELY TINY — names and integers joined by `+`/`-`, nothing else,
    no parentheses, no calls. `eval` is not used and must not be: this reads source the
    build also reads, and a reader that could execute it would be a second, weaker
    evaluator whose disagreements with sigil would be invisible. Anything outside the
    grammar is UNMEASURABLE by name, which is the correct answer for "I cannot account for
    this expression" — never a guess.
    """
    m = re.search(rf"^\s*(?:pub\s+)?const\s+{re.escape(name)}\s*=\s*([^/\n]+?)\s*(?://.*)?$",
                  _read(path), re.M)
    if not m:
        raise Unmeasurable(
            f"cannot find `const {name} = <expression>` in {os.path.relpath(path, REPO)}")
    expr = m.group(1).strip()
    toks = re.findall(r"[A-Za-z_][\w]*|\$[0-9A-Fa-f]+|\d+|[+-]", expr)
    if "".join(toks) != expr.replace(" ", ""):
        raise Unmeasurable(
            f"`const {name}` in {os.path.relpath(path, REPO)} is `{expr}`, which is outside "
            f"the names-and-integers-joined-by-plus-or-minus grammar this gate can account "
            f"for. It refuses rather than evaluating it a second way — a reader that "
            f"disagreed with sigil about this expression would be invisible")
    total, sign, seen_term = 0, 1, False
    for t in toks:
        if t in "+-":
            if not seen_term:
                raise Unmeasurable(f"`const {name} = {expr}`: leading/duplicated operator")
            sign, seen_term = (1 if t == "+" else -1), False
            continue
        if t[0].isalpha() or t[0] == "_":
            if t not in env:
                raise Unmeasurable(
                    f"`const {name} = {expr}` names `{t}`, which this gate has not derived. "
                    f"It knows {sorted(env)}; add the derivation rather than typing a number")
            v = env[t]
        else:
            v = _int(t)
        total += sign * v
        seen_term = True
    if not seen_term:
        raise Unmeasurable(f"`const {name} = {expr}`: trailing operator")
    return total


def vdp_shadow_reg(field):
    """A VdpShadow field's VDP register number, out of engine/structs.emp's own comment.

    `vdp_plane_a: u8,   // reg $02`. The comment IS the source of truth for which register
    the byte is flushed to — engine/system/vdp_init.emp's Flush_VDP_Shadow walks the table
    by INDEX, so the struct's field order is the register order and the comment is what a
    reader (and this gate) has to go on.

    WHY THE NUMBER IS READ AND NOT TYPED, and it is not tidiness: the register selector
    ($8200 vs $8400) is half of each word this gate derives, and pairing Plane B's byte
    with Plane A's selector produces a legal-looking word pointing three bits away from
    anything. Deriving the selector from the struct that also proves the register is
    SHADOWED ties the two facts the program depends on to one file — if a register ever
    left VdpShadow, the flush would stop restoring it at frame top and the band would leak
    into the next frame, and this reader would go UNMEASURABLE instead of quietly
    continuing with a typed number.
    """
    src = _read(STRUCTS)
    m = re.search(rf"^\s*{re.escape(field)}\s*:\s*u8\s*,\s*//\s*reg\s+\$([0-9A-Fa-f]{{2}})",
                  src, re.M)
    if not m:
        raise Unmeasurable(
            f"engine/structs.emp's VdpShadow has no `{field}: u8, // reg $XX` line. This "
            f"gate derives the register SELECTOR from that comment, and the same struct is "
            f"what makes Flush_VDP_Shadow restore the register at frame top — a field that "
            f"left the struct is a band that leaks, not a formatting change")
    return int(m.group(1), 16)


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


def expected_words(top_line, top_end, bot_line, bot_end,
                   plane_a, plane_b, shift_a, shift_b, reg_a, reg_b,
                   op_set_reg, park, ops_end):
    """The 23-word image the TWO-BAND, TWO-REGISTER program emits.

    A PURE FUNCTION over the thirteen derived facts, so the derivation can be exercised
    without a ROM at all (tools/test_plane_base_swap_gate.py). The framing is the sparse
    tier's documented schedule — one header word, two priming records, ONE RECORD PER
    EDGE, the terminator — and every arm follows `arm_at(L, i)` over the fire-line list
    L = [0, 1, top_line - 1, top_end - 1, bot_line - 1, bot_end - 1]:

        record 0 (priming)        $8A00 | (L[2] - L[1] - 1)  = the gap to the TOP ON edge
        record 1 (priming)        $8A00 | (L[3] - L[2] - 1)  = the TOP band's width
        record 2 (TOP band ON)    $8A00 | (L[4] - L[3] - 1)  = the MIDDLE, between the bands
        record 3 (TOP band OFF)   $8A00 | (L[5] - L[4] - 1)  = the BOTTOM band's width
        record 4 (BOTTOM band ON)   park — i + 2 is past the end of L
        record 5 (BOTTOM band OFF)  park

    TWO EDGES WAS THE SUBJECT OF F2; TWO BANDS ON TWO REGISTERS IS THE SUBJECT OF T3
    (2026-09-04). Before F2 this derived an 11-word single-fire image that was CORRECT for
    the program in the ROM and still described something invisible — one OP_SET_REG has no
    OFF edge, so at line 3 it re-pointed Plane A for the whole display. Before T3 it derived
    15 words on ONE register, and that image would have been just as correct for a program
    with a second band on the SAME register, which is two copies of one borrow rather than
    the inversion the owner asked for. So the two selectors are separate inputs here and
    they are asserted DIFFERENT: the shape of the answer has to match the shape of the
    question, and the question is now about two layers.

    THE SELECTOR/SHIFT PAIRING IS THE SUBTLE HALF. `vdp_base_reg` returns a register BYTE;
    the caller supplies the selector. reg $02 uses shift 10 and reg $04 uses shift 13
    (engine/vdp.emp), so a word built from one register's selector and the other's shift is
    a legal $8xxx word aimed three address bits away from anything, and nothing downstream
    can see it. Each band below builds its word from ITS OWN (selector, shift) pair, once.
    """
    sel_a = 0x8000 | (reg_a << 8)          # reg $02's selector word, $8200
    sel_b = 0x8000 | (reg_b << 8)          # reg $04's selector word, $8400
    if sel_a == sel_b:
        raise Unmeasurable(
            f"both bands would write VDP register selector ${sel_a:04X}: Plane A's base "
            f"register (${reg_a:02X}) and Plane B's (${reg_b:02X}) are the same register. "
            f"T3 IS the role inversion — the top band drives the BACKGROUND layer's base "
            f"and the bottom band the FOREGROUND layer's — so two bands on one register is "
            f"not the effect this gate describes. The `.emp` fixture refuses this by name "
            f"too")

    # THE TOP BAND: the BACKGROUND layer (reg $04, Plane B's base) borrows the FOREGROUND's
    # map, then returns to its own. THE BOTTOM BAND: the FOREGROUND layer (reg $02, Plane
    # A's base) borrows the BACKGROUND's map, then returns to its own.
    top_word, top_home = sel_b | (plane_a >> shift_b), sel_b | (plane_b >> shift_b)
    bot_word, bot_home = sel_a | (plane_b >> shift_a), sel_a | (plane_a >> shift_a)
    for tag, w, h, sel, shift in (("TOP", top_word, top_home, sel_b, shift_b),
                                  ("BOTTOM", bot_word, bot_home, sel_a, shift_a)):
        if w == h:
            raise Unmeasurable(
                f"the {tag} band's borrowed base and its own base both fold to ${w:04X} "
                f"under selector ${sel:04X} at shift {shift} — Plane A is ${plane_a:04X} "
                f"and Plane B ${plane_b:04X} — so that band re-points a register at the "
                f"base it already has and there is no mid-frame swap to look for. The "
                f"`.emp` fixture refuses this by name too; seeing it here means that "
                f"ensure is no longer running")

    # An effect on screen line M fires at M-1 (raster_dsl's Ruling 1a).
    L = [0, 1, top_line - 1, top_end - 1, bot_line - 1, bot_end - 1]
    NAMES = ("priming 0", "priming 1", "the TOP band's ON edge", "the TOP band's OFF edge",
             "the BOTTOM band's ON edge", "the BOTTOM band's OFF edge")
    for i in range(1, len(L)):
        if L[i] <= L[i - 1]:
            raise Unmeasurable(
                f"{NAMES[i]} (fire line {L[i]}) does not follow {NAMES[i - 1]} (fire line "
                f"{L[i - 1]}). `fire_lines` refuses a non-ascending program by name, so this "
                f"gate cannot be looking at a built ROM with these four constants — do NOT "
                f"read it as a byte mismatch. The four screen lines are "
                f"{top_line}, {top_end}, {bot_line}, {bot_end}")

    arms = []
    for i in range(len(L)):
        if i + 2 >= len(L):
            arms.append(park)
            continue
        gap = L[i + 2] - L[i + 1] - 1
        if not 0 <= gap <= 255:
            raise Unmeasurable(
                f"the gap from {NAMES[i + 1]} to {NAMES[i + 2]} is {gap} line(s), which is "
                f"not a legal reg $0A reload — that interval is wider than one reload of "
                f"the schedule this gate models, or the lines are outside it")
        arms.append(0x8A00 | gap)

    return [
        0x0000,                     # pal_dirty_mask — register ops write no CRAM
        arms[0], 0x0000,            # record 0 — priming; schedules the TOP band's ON edge
        arms[1], 0x0000,            # record 1 — priming; the TOP band's width
        arms[2], 0x0001,            # record 2 — TOP band ON; its arm is the MIDDLE
        op_set_reg, top_word,       # reg $04 <- Plane A's nametable: fg map, bg layer
        arms[3], 0x0001,            # record 3 — TOP band OFF; its arm is the BOTTOM's width
        op_set_reg, top_home,       # reg $04 <- Plane B's own base again
        arms[4], 0x0001,            # record 4 — BOTTOM band ON; nothing left to schedule
        op_set_reg, bot_word,       # reg $02 <- Plane B's nametable: bg map, fg layer
        arms[5], 0x0001,            # record 5 — BOTTOM band OFF; past the end, so park
        op_set_reg, bot_home,       # reg $02 <- Plane A's own base again
        park, ops_end,              # terminator
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

        # ---- the expectation, out of SIX sources the fixture does not author ------
        plane_a = emp_const(CONSTANTS, "VRAM_PLANE_A")
        plane_b = emp_const(CONSTANTS, "VRAM_PLANE_B")
        shift_a = vdp_base_shift("PlaneA")
        shift_b = vdp_base_shift("PlaneB")
        reg_a = vdp_shadow_reg("vdp_plane_a")
        reg_b = vdp_shadow_reg("vdp_plane_b")
        op_set_reg = emp_const(RASTER, "OP_SET_REG")
        park = emp_const(RASTER, "RASTER_ARM_PARK")
        ops_end = emp_const(RASTER, "RASTER_OPS_END")
        max_fire = emp_const(RASTER, "RASTER_MAX_FIRE_LINE")
        top_line = emp_const(FIXTURE, "OJZ_BASE_SWAP_TOP_LINE")
        top_end = emp_const(FIXTURE, "OJZ_BASE_SWAP_TOP_END_LINE")
        # The bottom band's lines are EXPRESSIONS in the fixture, not literals — it derives
        # them as the top band's reflected through RASTER_MAX_FIRE_LINE. This gate resolves
        # that expression against the names it has already derived rather than demanding
        # literals in the source, so the fixture keeps its derivation and the gate keeps its
        # independence: it still gets its numbers from the fixture, and it can still say
        # what it read.
        env = {"RASTER_MAX_FIRE_LINE": max_fire,
               "OJZ_BASE_SWAP_TOP_LINE": top_line,
               "OJZ_BASE_SWAP_TOP_END_LINE": top_end}
        bot_line = emp_const_expr(FIXTURE, "OJZ_BASE_SWAP_BOT_LINE", env)
        bot_end = emp_const_expr(FIXTURE, "OJZ_BASE_SWAP_BOT_END_LINE", env)

        want = expected_words(top_line, top_end, bot_line, bot_end,
                              plane_a, plane_b, shift_a, shift_b, reg_a, reg_b,
                              op_set_reg, park, ops_end)
        image_bytes = 2 * len(want)

        labels = lst_labels(lst_path)
        addr = at(labels, SYM, lst_path)
        nxt = at(labels, NEXT_SYM, lst_path)
        gap = nxt - addr

        sel_a, sel_b = 0x8000 | (reg_a << 8), 0x8000 | (reg_b << 8)
        print(f"plane_base_swap_gate [{os.path.basename(lst_path)}, shape={shape}]")
        print(f"  derived: Plane A ${plane_a:04X} (FOREGROUND layer, reg ${reg_a:02X}, "
              f"shift {shift_a})   Plane B ${plane_b:04X} (BACKGROUND layer, reg "
              f"${reg_b:02X}, shift {shift_b})")
        print(f"  derived: OP_SET_REG {op_set_reg}, arm park ${park:04X}, ops end ${ops_end:04X}, "
              f"last fire line {max_fire}")
        print(f"  derived: TOP    band screen lines {top_line}..{top_end} "
              f"({top_end - top_line} wide) — reg ${reg_b:02X} <- ${sel_b | (plane_a >> shift_b):04X} "
              f"then home ${sel_b | (plane_b >> shift_b):04X}: the FOREGROUND's map in the "
              f"BACKGROUND layer")
        print(f"  derived: BOTTOM band screen lines {bot_line}..{bot_end} "
              f"({bot_end - bot_line} wide) — reg ${reg_a:02X} <- ${sel_a | (plane_b >> shift_a):04X} "
              f"then home ${sel_a | (plane_a >> shift_a):04X}: the BACKGROUND's map in the "
              f"FOREGROUND layer")
        print(f"  derived: MIDDLE (neither band) screen lines {top_end + 1}..{bot_line - 1}, "
              f"{bot_line - top_end - 1} row(s); the bottom band is the top band reflected "
              f"through line {max_fire}")
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
        # the image compare would blame "index 16" for what is really "the op points at the
        # wrong plane" — and because these are the four words the DoD row is about. The four
        # edges live at words 7/8, 11/12, 15/16 and 19/20; the table below is walked rather
        # than the four cases being written out, because T3 doubled them and a fifth band
        # would double them again.
        EDGES = (
            (7, 8, f"the TOP band's ON edge", reg_b, shift_b, plane_a,
             "the BACKGROUND layer (reg $%02X) must borrow the FOREGROUND's map" % reg_b),
            (11, 12, f"the TOP band's OFF edge", reg_b, shift_b, plane_b,
             "closing the top band needs Plane B's OWN base — the word Flush_VDP_Shadow "
             "writes at the next frame top"),
            (15, 16, f"the BOTTOM band's ON edge", reg_a, shift_a, plane_b,
             "the FOREGROUND layer (reg $%02X) must borrow the BACKGROUND's map" % reg_a),
            (19, 20, f"the BOTTOM band's OFF edge", reg_a, shift_a, plane_a,
             "closing the bottom band needs Plane A's OWN base — the word "
             "Flush_VDP_Shadow writes at the next frame top"),
        )
        for op_i, arg_i, tag, reg, shift, wanted_base, why in EDGES:
            if got[op_i] != op_set_reg:
                print(f"        word {op_i} is {tag}'S OPCODE and it is not OP_SET_REG "
                      f"({op_set_reg}). This effect IS the OP_SET_REG path — "
                      f"engine/effects/raster.emp's `.op_set_reg` arm, whose whole argument "
                      f"is one `$8xxx` register word. An edge without its opcode is an edge "
                      f"that does not happen, and a band missing an OFF edge runs to the "
                      f"BOTTOM OF THE DISPLAY — the exact program that shipped at 8bf6df74 "
                      f"and that the owner reported he could not see.")
            if got[arg_i] != want[arg_i]:
                sel_got = got[arg_i] & 0xFF00
                decoded = (got[arg_i] & 0xFF) << shift
                print(f"        word {arg_i} is {tag}'S REGISTER WORD. ${got[arg_i]:04X} "
                      f"writes selector ${sel_got:04X} and, read at shift {shift}, points at "
                      f"VRAM ${decoded:04X}; this edge needs ${wanted_base:04X} through "
                      f"selector ${0x8000 | (reg << 8):04X} — {why}. Note the two ways this "
                      f"goes wrong SILENTLY: the right selector with the OTHER plane's base "
                      f"is a no-op on screen, and the WRONG selector with a valid-looking "
                      f"byte drives the other layer's register at the wrong shift.")
        if got[8] == got[12]:
            print(f"        THE TOP BAND'S TWO EDGES CARRY THE SAME WORD (${got[8]:04X}). "
                  f"Whatever the word is, a band needs its edges to DIFFER — this is an "
                  f"interval with no boundary at either end of it.")
        if got[16] == got[20]:
            print(f"        THE BOTTOM BAND'S TWO EDGES CARRY THE SAME WORD "
                  f"(${got[16]:04X}). Same fault, other band.")
        if (got[8] & 0xFF00) == (got[16] & 0xFF00):
            print(f"        BOTH BANDS WRITE SELECTOR ${got[8] & 0xFF00:04X}. T3 is the "
                  f"ROLE INVERSION: one band re-points the BACKGROUND layer's base at the "
                  f"foreground's map and the other re-points the FOREGROUND layer's at the "
                  f"background's. Two bands on one register are two of the same effect. "
                  f"Every framing word above holds just as well for that program, which is "
                  f"why this is said separately.")

        if bad:
            print(f"plane_base_swap_gate: FAIL — {bad} of {len(want)} word(s) differ")
            return 1
        print(f"plane_base_swap_gate: OK — TWO mid-frame base bands are in this ROM, on TWO "
              f"registers. Screen lines {top_line}..{top_end}: OP_SET_REG ${got[8]:04X} "
              f"re-points reg ${reg_b:02X} (the BACKGROUND layer) at ${plane_a:04X} — the "
              f"foreground's map — and ${got[12]:04X} puts it back. Screen lines "
              f"{bot_line}..{bot_end}: OP_SET_REG ${got[16]:04X} re-points reg ${reg_a:02X} "
              f"(the FOREGROUND layer) at ${plane_b:04X} — the background's map — and "
              f"${got[20]:04X} puts it back. Both bands are {top_end - top_line} lines and "
              f"both close mid-frame rather than at the VBlank shadow flush, leaving "
              f"{bot_line - top_end - 1} unswapped rows between them.")
        return 0

    except Unmeasurable as e:
        print(f"plane_base_swap_gate: UNMEASURABLE — {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
