#!/usr/bin/env python3
"""instashield_gate.py — prove the ABILITY HOOKS refuse every air state that did NOT
come from a jump, by EXECUTING the built ROM's own bytes.

TWO SUBJECTS, one method (the second added 2026-09-02, parcel/tails-jump-gate):

  * Ability_InstaShield  (games/sonic4/player/player_instashield.emp) — Sonic's.
  * Ability_TailsFlight  (games/sonic4/player/player_fly.emp)         — Tails'.

Ability_KnuxGlide is DELIBERATELY NOT a subject: the ruling that tightened Tails left
Knuckles' glide on the broad "any air state" rule, because gliding off a ledge walk-off
reads as a coyote-time affordance rather than a bug. Adding it here would assert a rule
the engine is not supposed to have. See docs/DEFERRED_WORK.md.

WHY THIS SHAPE. The claim each of these parcels makes is a REFUSAL — "pressing jump in
mid-air after walking off a ledge must not fire the ability" — and a refusal is the one
thing shipped content cannot demonstrate. The recorded replay net is proof of that: it
stays byte-identical across the insta-shield change (measured), because every airborne
press in the two fixtures was already made from a real jump; and it cannot reach
Ability_TailsFlight AT ALL, because Character_ID is boot-zero (CHAR_SONIC) and its only
writer, Debug_CharacterHotkey, stands down for INPUT_PLAYBACK and INPUT_RECORD alike
(ojz_scroll_test.emp:1057-1058). A gate over recorded play therefore cannot see the half
of the behaviour that moved, so the subject here is the ROUTINE,
taken from the ROM as bytes:

    s4[.debug].lst  ->  Ability_InstaShield's address and extent, and the EQU block
                        that carries PSTATE_* / INSTASHIELD_* out of
                        games/sonic4/config/constants.emp
    player_common.emp -> the PlayerV overlay's field offsets, from the layout's owner
    s4[.debug].bin  ->  the routine's bytes
    capstone        ->  an INDEPENDENT decoder (not our assembler's own opinion)
    this file       ->  a strict micro-executor for exactly the forms that decode to
    the model       ->  S3K's Sonic_JumpHeight -> Sonic_ShieldMoves rule, re-derived

and the two are compared over the full cross product of player_state (all 256 byte
values, not just the 13 legal ones), PlayerV.instashield (all three values) and
PlayerV.status_secondary (empty, each single suppression bit, the whole mask, and a
non-suppressing bit).

THE MODEL, and where every clause of it was read (skdisasm/sonic3k.asm, first-hand):

  * `Sonic_ShieldMoves` (:23401) has exactly ONE caller, `Sonic_JumpHeight` (:23368),
    whose first two instructions are `tst.b jumping(a0) / beq.s Sonic_UpVelCap`
    (:23369-23370) and whose `Sonic_UpVelCap` arm (:23393) rts's without ever reaching
    the shield moves. So `jumping != 0` is a HARD PRECONDITION.
  * Aeon has no `jumping` byte; `PlayerV.player_state` already discriminates.
    PSTATE_JUMP is "airborne curled FROM A JUMP" and PSTATE_ROLLJUMP is the same with
    the air-control lockout; PSTATE_AIR (ledge walk-off, debug-fly exit, init) and
    PSTATE_AIRBALL (rolled off a ledge, spindash floor-vanish) are the not-from-a-jump
    air states. The equivalence was established by enumerating every WRITER of
    player_state — `Player_SetState` is the sole transition writer — see the derivation
    in games/sonic4/player/player_instashield.emp's module header.
  * `tst.b double_jump_flag / bne` (:23402) is the one-shot, and it sits AFTER the
    `jumping` test and BEFORE the roll-jump cancel.
  * `bclr #Status_RollJump,status(a0)` (:23408) is the cancel: it runs past the
    one-shot but ahead of the suppression tests, so a SUPPRESSED insta-shield still
    lifts the lockout.
  * The suppression set is `Status_Invincible` + the four barrier bits, S3K's own
    `andi.b #$73` (:20621); config/constants.emp owns it as INSTASHIELD_SUPPRESS_MASK
    and pins it against that line.

ONE S3K GATE IS DELIBERATELY NOT MODELLED FOR THE INSTA-SHIELD, because it is not
built: `Sonic_JumpHeight` also requires `cmp.w y_vel(a0),d1 / ble.w` with d1 = -$400,
i.e. no insta-shield while still rising faster than the release cap. That is booked in
docs/DEFERRED_WORK.md. If it is ever built, MODEL_RISING_GATE below has to grow with it
— the assertion that no y_vel byte is read (see `test_reads_no_velocity`) is what makes
that a loud change rather than a silent divergence between this model and the routine.

THE TAILS MODEL (`Tails_JumpHeight` :28596 -> `Tails_Test_For_Flight` :28627), read the
same way:

  * `tst.b jumping(a0) / beq.s loc_15106` (:28597-28598); the `loc_15106` arm (:28615)
    rts's without ever reaching Tails_Test_For_Flight. Same hard precondition, same
    {PSTATE_JUMP, PSTATE_ROLLJUMP} equivalence.
  * `cmp.w y_vel(a0),d1 / ble.s Tails_Test_For_Flight` (:28605-28606) with d1 = -$400
    ($-200 underwater). Unlike Sonic's, THIS ONE IS BUILT — as `cmp.w
    PBLK_RELEASE_CAP(a4),d1 / blt`, reading the cap out of the slot's physics row — so
    it IS modelled, and the cap is swept as an INPUT rather than pinned to one row's
    value. That is what keeps this gate independent of the physics tables.
  * On engagement the routine seeds PlayerV.fly_fuel = FLY_FUEL_TICKS and
    PlayerV.fly_thrust = FLY_COAST and tail-calls Player_SetState(PSTATE_FLY). A
    REFUSAL must write none of the three — a half-seeded PSTATE_FLY scratch is the
    failure this observes.
  * Not modelled, because Aeon does not have them: S3K's Super-Tails transformation
    branch (:28636-28645) and its `Tails_CPU_idle_timer` gate (:28647). Both are
    guarded by systems that do not exist here yet; when they land, this model grows.

The executor is deliberately NOT a 68000 emulator. It implements one instruction form
per line the routine actually contains and raises UnsupportedInstruction on anything
else, so a future edit reaching for a new addressing mode fails LOUDLY here instead of
being silently skipped. It also refuses to read a register a stubbed callee's declared
contract says was clobbered. That refusal is the whole reason its green is worth
anything.

Usage (the post-sigil gate; see build.sh):

    instashield_gate.py --lst s4.debug.lst --rom s4.debug.bin \
                        --built-after <unix-ts> \
                        --fixture tools/fixtures/instashield_cut.json \
                        --tails-fixture tools/fixtures/tailsflight_cut.json --gate

BOTH abilities are graded on every run; `--ability instashield|tailsflight` narrows it
for debugging only. Two fixture FILES rather than one two-ability document, so that a
re-stamp of one subject cannot quietly re-stamp the other.

Exit 0 = every comparison matched. Exit 1 with --gate = a mismatch, a stale artifact,
or an instruction the executor does not model.
"""

import argparse
import json
import pathlib
import re
import sys

TOOLS = pathlib.Path(__file__).resolve().parent
ROOT = TOOLS.parent
sys.path.insert(0, str(TOOLS))

# The micro-CPU primitives are shared with the sprite-tilt gate rather than
# re-implemented: same memory model, same flag arithmetic, same operand grammar, same
# "raise on anything not modelled" contract. Only the executor LOOP differs, because
# this routine's callees are events to observe rather than side-effect-free stubs.
# normalize_stream/stream_diff/unresolved_note come from the same place for the same
# reason: the relocation-invariant fixture comparison was designed, argued and proved on
# the tilt gate (parcel/gate-fixtures-address-pinned, 9332587b) and this is its
# APPLICATION, not a second implementation of it. See the long WHY note above
# `normalize_stream` in sprite_tilt_gate.py — every word of it holds here.
from sprite_tilt_gate import (  # noqa: E402
    Micro, UnsupportedInstruction, _split_ops, parse_operand,
    normalize_stream, stream_diff, unresolved_note,
)

# --------------------------------------------------------------------------
# Inputs derived from the build, never restated here
# --------------------------------------------------------------------------

_SYM = re.compile(r"^ ([A-Za-z_$][\w$.]*) : ([0-9A-Fa-f]+) [A-Z] \|")
_EQU = re.compile(r"^EQU ([A-Za-z_][\w]*) = \$([0-9A-Fa-f]+)\s*$")

# The `vars` field grammar of player_common.emp's PlayerV block. Sizes are the .emp
# scalar widths; the region packs sequentially with no implicit alignment (which the
# block's own hand-written `climb_pad` proves, and which the _pl_state cross-check
# below re-proves against the build every run).
_FIELD = re.compile(r"^\s*([a-z_][\w]*)\s*:\s*([iu](?:8|16|32))\s*,")
_WIDTH = {"u8": 1, "i8": 1, "u16": 2, "i16": 2, "u32": 4, "i32": 4}

ROUTINE = "Ability_InstaShield"
LOCAL_PREFIX = "$games.sonic4.player_instashield$%s$" % ROUTINE

TAILS_ROUTINE = "Ability_TailsFlight"
TAILS_LOCAL_PREFIX = "$games.sonic4.player_fly$%s$" % TAILS_ROUTINE
TAILS_SRC = ("games", "sonic4", "player", "player_fly.emp")

# NOT a free parameter: the local-label prefix is the routine's name UNDER ITS OWN
# MODULE PATH, so a second subject needs its own string even though the ROUTINE name
# is "just a parameter". Getting this wrong is silent and severe — routine_extent
# would stop at the routine's first local label, cutting the tail off the extent, and
# the executor would then report "execution left the extent" (measured on the first
# run against Ability_TailsFlight: 28 bytes instead of 30, the trailing `rts` gone).


def parse_lst(path):
    """(symbols, equates) — both out of the sigil listing this ROM was built with."""
    syms, equs = {}, {}
    for line in pathlib.Path(path).read_text(errors="replace").splitlines():
        m = _SYM.match(line)
        if m:
            syms.setdefault(m.group(1), int(m.group(2), 16))
            continue
        m = _EQU.match(line)
        if m:
            equs.setdefault(m.group(1), int(m.group(2), 16))
    if not syms:
        raise SystemExit("instashield_gate: no symbols parsed from %s — the listing "
                         "format changed; this gate reads the ' NAME : ADDR C |' block"
                         % path)
    if not equs:
        raise SystemExit("instashield_gate: no EQU lines parsed from %s — this gate "
                         "takes PSTATE_*/INSTASHIELD_* from the build's own equates, "
                         "not from literals in this file" % path)
    return syms, equs


def routine_extent(syms, name=ROUTINE, prefix=None):
    """[start, end) — end is the next symbol strictly above start. The routine's own
    hygienic local labels sit inside it and are skipped, which is what `prefix` is
    for; see the note beside TAILS_LOCAL_PREFIX for why it cannot default."""
    if prefix is None:
        prefix = LOCAL_PREFIX if name == ROUTINE else None
    if prefix is None:
        raise SystemExit("instashield_gate: routine_extent(%r) needs its module's "
                         "local-label prefix — an extent that stops at the routine's "
                         "own first local label is silently truncated" % name)
    start = syms.get(name)
    if start is None:
        raise SystemExit("instashield_gate: %s is not in the listing. Either the "
                         "ability was renamed or removed, or the character's "
                         "cd_ability no longer reaches it." % name)
    above = [a for n, a in syms.items()
             if a > start and not n.startswith(prefix)]
    if not above:
        raise SystemExit("instashield_gate: nothing follows %s in the listing" % name)
    return start, min(above)


PLAYERV_REQUIRED = ("player_state", "status_secondary", "instashield",
                    "fly_fuel", "fly_thrust")


def playerv_offsets(sst_custom, src_root=ROOT, require=PLAYERV_REQUIRED):
    """PlayerV field -> SST byte offset, parsed from the block that DECLARES the
    layout (games/sonic4/player/player_common.emp) and rebased onto the overlay's own
    window start (`SST_sst_custom`, from the build's equates). Read from source rather
    than hard-coded so a reordered overlay moves this gate's probes with it;
    cross-checked against the build's own `_pl_state` equate by the caller."""
    path = src_root / "games" / "sonic4" / "player" / "player_common.emp"
    text = path.read_text(errors="replace")
    m = re.search(r"^pub vars PlayerV\s*:\s*Sst\.sst_custom\s*\{\s*$", text, re.M)
    if not m:
        raise SystemExit("instashield_gate: could not find `pub vars PlayerV: "
                         "Sst.sst_custom {` in %s — the overlay moved or was renamed"
                         % path)
    offs, cur = {}, 0
    for line in text[m.end():].splitlines():
        code = line.split("//", 1)[0]
        if code.strip() == "}":
            break
        f = _FIELD.match(code)
        if f:
            offs[f.group(1)] = sst_custom + cur
            cur += _WIDTH[f.group(2)]
    for need in require:
        if need not in offs:
            raise SystemExit("instashield_gate: PlayerV has no `%s` field — this gate "
                             "probes it by name; a rename must move the gate too"
                             % need)
    return offs, cur


# --------------------------------------------------------------------------
# Module-private `const`s, read from the source that declares them
# --------------------------------------------------------------------------
#
# FLY_FUEL_TICKS / FLY_COAST / PBLK_RELEASE_CAP are plain `const`, not `pub const`, so
# unlike PSTATE_* they never reach the listing's EQU block. This gate will not
# substitute a literal for them (the whole discipline is "derive from the build's own
# constants"), so it parses them out of the file that DECLARES them and evaluates the
# expression — `(8 * 60) / 2` is a real declaration, not a hypothetical. `/` is .emp's
# integer divide; `//` starts a comment and never an operator, which is what makes
# stripping at `//` safe.

_CONST_DECL = re.compile(r"^\s*(?:pub\s+)?const\s+([A-Za-z_]\w*)\s*=\s*(.+)$", re.M)


def _eval_emp_int(expr, name, path):
    import ast
    expr = expr.split("//", 1)[0].strip()
    expr = re.sub(r"\$([0-9A-Fa-f]+)", lambda m: str(int(m.group(1), 16)), expr)

    def ev(n):
        if isinstance(n, ast.Expression):
            return ev(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, int):
            return n.value
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, (ast.USub, ast.UAdd)):
            v = ev(n.operand)
            return -v if isinstance(n.op, ast.USub) else v
        if isinstance(n, ast.BinOp):
            l, r = ev(n.left), ev(n.right)
            for op, f in ((ast.Add, lambda: l + r), (ast.Sub, lambda: l - r),
                          (ast.Mult, lambda: l * r), (ast.Div, lambda: l // r),
                          (ast.FloorDiv, lambda: l // r),
                          (ast.LShift, lambda: l << r), (ast.RShift, lambda: l >> r)):
                if isinstance(n.op, op):
                    return f()
        raise SystemExit(
            "instashield_gate: `const %s` in %s is not an integer expression this gate "
            "can evaluate (%r). It refuses to guess — either simplify the declaration "
            "or teach _eval_emp_int the form." % (name, path, expr))

    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError:
        raise SystemExit("instashield_gate: cannot parse `const %s = %s` in %s"
                         % (name, expr, path))
    return ev(tree)


def source_consts(rel_parts, names, src_root=ROOT):
    """{name: value} for module-private `const`s, from the .emp that declares them."""
    path = src_root.joinpath(*rel_parts)
    text = path.read_text(errors="replace")
    found = {n: e for n, e in _CONST_DECL.findall(text)}
    out = {}
    for n in names:
        if n not in found:
            raise SystemExit(
                "instashield_gate: %s declares no `const %s` — this gate reads it from "
                "source because it is not a `pub const` and so never reaches the "
                "listing's EQU block. A rename must move the gate too." % (path, n))
        out[n] = _eval_emp_int(found[n], n, path)
    return out


# --------------------------------------------------------------------------
# The model — S3K's rule, re-derived (see the header for every line reference)
# --------------------------------------------------------------------------

MODEL_RISING_GATE = False   # S3K's `cmp.w y_vel,#-$400 / ble` — NOT built here; booked
                            # in docs/DEFERRED_WORK.md. See the header.


def model(state, insta, status2, k):
    """What S3K's Sonic_JumpHeight -> Sonic_ShieldMoves does, expressed over this
    engine's state byte. `k` carries the constants taken from the build's equates.

    Returns (fires, cancels, final_state, final_insta).
    """
    from_a_jump = state in (k["PSTATE_JUMP"], k["PSTATE_ROLLJUMP"])
    if not from_a_jump:
        return (False, False, state, insta)                 # tst.b jumping / beq
    if insta != k["INSTASHIELD_READY"]:
        return (False, False, state, insta)                 # tst.b double_jump_flag / bne
    cancels = state == k["PSTATE_ROLLJUMP"]                 # bclr #Status_RollJump
    final_state = k["PSTATE_JUMP"] if cancels else state
    if status2 & k["INSTASHIELD_SUPPRESS_MASK"]:
        return (False, cancels, final_state, insta)         # a barrier takes the press
    return (True, cancels, final_state, k["INSTASHIELD_ATTACKING"])


def model_flight(state, y_vel, cap, k):
    """What S3K's Tails_JumpHeight -> Tails_Test_For_Flight does, over this engine's
    state byte and the slot's own release cap.

    Returns (engages, final_state, fuel, thrust) — fuel/thrust are None when the press
    is refused, which is the assertion that a refusal writes NOTHING.
    """
    if state not in (k["PSTATE_JUMP"], k["PSTATE_ROLLJUMP"]):
        return (False, state, None, None)       # tst.b jumping / beq  (:28597-28598)
    if y_vel < cap:
        return (False, state, None, None)       # cmp.w y_vel,d1 / ble (:28605-28606)
    return (True, k["PSTATE_FLY"], k["FLY_FUEL_TICKS"], k["FLY_COAST"])


# --------------------------------------------------------------------------
# The strict micro-executor
# --------------------------------------------------------------------------

BRANCHES = {"bra", "bhi", "bls", "bcc", "bhs", "bcs", "blo", "bne", "beq",
            "bvc", "bvs", "bpl", "bmi", "bge", "blt", "bgt", "ble"}

# Which operands each modelled mnemonic READS and which it WRITES, by index. Declared
# rather than inferred so the clobber discipline below cannot quietly let a poisoned
# register through a form nobody thought about.
RW = {
    "move":  ((0,), 1),
    "moveq": ((), 1),
    "tst":   ((0,), None),
    "cmpi":  ((0, 1), None),
    "cmp":   ((0, 1), None),
    "andi":  ((0, 1), 1),
    "ori":   ((0, 1), 1),
    "eori":  ((0, 1), 1),
}

# The declared clobber contracts of the routine's callees, from their own `proc`
# headers. A register listed here is UNDEFINED after the call and reading it raises.
CALLEE_CLOBBERS = {
    "Player_SetState":   ("d1", "d2", "a1", "a2"),
    "InstaShield_Spawn": ("d0", "d1", "d2", "a1"),
}
# a0 is `preserves(a0)` on every one of them, so it is deliberately absent.

RAM_BASE = 0xFF9000     # where the synthetic player SST is planted
BLK_BASE = RAM_BASE + 0x80   # and the synthetic PlayerBlock a4 points at. Inside the
                             # same 0x100 window Micro.rb() treats as "unwritten reads
                             # 0", and clear of the 0x40-byte SST above it.


class Refusal(Exception):
    """The executor read something a callee's contract says is undefined."""


def run_case(rom, prog, start, end, stubs, offs, state, insta=None, status2=None,
             sst_words=None, blk_words=None):
    """Execute the routine once. Returns a dict of everything observable.

    `state` always seeds PlayerV.player_state. `insta`/`status2` seed the insta-shield's
    two other inputs and are skipped when None (Ability_TailsFlight reads neither).
    `sst_words` seeds {SST byte offset: signed word} — y_vel for the flight gate.
    `blk_words` seeds {PlayerBlock byte offset: signed word} at BLK_BASE and points a4
    at it; when it is None a4 is left at 0, so a routine that reaches through a4
    unexpectedly faults loudly instead of reading zeros.
    """
    cpu = Micro(rom, RAM_BASE)
    cpu.a[0] = RAM_BASE
    cpu.wb(RAM_BASE + offs["player_state"], state)
    if insta is not None:
        cpu.wb(RAM_BASE + offs["instashield"], insta)
    if status2 is not None:
        cpu.wb(RAM_BASE + offs["status_secondary"], status2)
    for off, val in (sst_words or {}).items():
        cpu.write(RAM_BASE + off, val & 0xFFFF, "w")
    if blk_words is not None:
        cpu.a[4] = BLK_BASE
        for off, val in blk_words.items():
            cpu.write(BLK_BASE + off, val & 0xFFFF, "w")

    undef = set()
    events = []
    reads = set()
    blk_reads = set()
    pc, steps = start, 0

    def reg_name(op):
        return ("d%d" if op[0] == "d" else "a%d") % op[1]

    while True:
        steps += 1
        if steps > 200:
            raise UnsupportedInstruction(
                "instruction limit reached — %s did not return" % ROUTINE)
        if pc not in prog:
            raise UnsupportedInstruction("execution left the extent at $%06X" % pc)
        mnem_full, ops, nxt = prog[pc]
        parts = mnem_full.split(".")
        base, size = parts[0], (parts[1] if len(parts) > 1 else None)

        if base == "rts":
            events.append(("rts", None))
            break

        if base in BRANCHES or base in ("bsr", "jsr", "jmp"):
            tgt = ops[0][1] if ops and ops[0][0] in ("tgt", "absl", "absw") else None
            if base in BRANCHES and tgt is not None and start <= tgt < end:
                cc = "ra" if base == "bra" else base[1:]
                pc = tgt if cpu.cond(cc) else nxt
                continue
            # Anything leaving the extent is a call or a tail call to a named callee.
            if tgt is None:
                raise UnsupportedInstruction(
                    "%s with an operand form this gate does not model: %s"
                    % (mnem_full, ", ".join(map(str, ops))))
            name = stubs.get(tgt)
            if name is None:
                raise UnsupportedInstruction(
                    "transfer to $%06X, which is not a modelled callee. A new callee "
                    "has to be understood before its effect on player_state / "
                    "instashield can be assumed to be none." % tgt)
            events.append((name, cpu.d[0] & 0xFF))
            if name == "Player_SetState":
                # Its whole contract: writes the state byte, then runs the enter hook.
                # PHook_AirBallEnter (both JUMP and ROLLJUMP) touches size/status only —
                # it does NOT re-arm instashield, which is what makes landing the sole
                # re-arm (player_common.emp:1338/1371 are the two that do).
                cpu.wb(RAM_BASE + offs["player_state"], cpu.d[0] & 0xFF)
            undef |= set(CALLEE_CLOBBERS.get(name, ()))
            if base in ("bra", "jmp"):       # tail call — the routine ends here
                break
            pc = nxt
            continue

        if base not in RW:
            raise UnsupportedInstruction("instruction not modelled: %s %s"
                                         % (mnem_full, ", ".join(map(str, ops))))

        read_idx, write_idx = RW[base]
        for i in read_idx:
            op = ops[i]
            if op[0] in ("d", "a") and reg_name(op) in undef:
                raise Refusal(
                    "$%06X %s reads %s, which the preceding call's declared clobber "
                    "list leaves UNDEFINED" % (pc, mnem_full, reg_name(op)))
            if op[0] == "disp":
                if op[2] == 0:
                    reads.add(cpu.a[0] + op[1] - RAM_BASE)
                elif op[2] == 4:
                    blk_reads.add(op[1])
                else:
                    raise UnsupportedInstruction(
                        "$%06X %s reads through a%d, which this gate plants no "
                        "synthetic block behind" % (pc, mnem_full, op[2]))

        if base == "moveq":
            v = ops[0][1] & 0xFF
            if v & 0x80:
                v -= 0x100
            cpu.d[ops[1][1]] = v & 0xFFFFFFFF
            cpu.logic_flags(v & 0xFFFFFFFF, "l")
        elif base == "move":
            v = cpu.src(ops[0], size)
            cpu.logic_flags(v, size)
            cpu.dst_write(ops[1], v, size)
        elif base == "tst":
            cpu.logic_flags(cpu.src(ops[0], size), size)
        elif base in ("cmpi", "cmp"):
            cpu.sub_flags(cpu.src(ops[1], size), cpu.src(ops[0], size), size)
        elif base in ("andi", "ori", "eori"):
            a, b = cpu.src(ops[1], size), cpu.src(ops[0], size)
            r = {"andi": a & b, "ori": a | b, "eori": a ^ b}[base]
            cpu.logic_flags(r, size)
            cpu.dst_write(ops[1], r, size)

        if write_idx is not None and ops[write_idx][0] in ("d", "a"):
            undef.discard(reg_name(ops[write_idx]))
        pc = nxt

    names = [e[0] for e in events]
    return {
        "spawned": "InstaShield_Spawn" in names,
        "sfx": next((v for n, v in events if n == "Sound_PlaySFX"), None),
        "set_state": [v for n, v in events if n == "Player_SetState"],
        "state": cpu.rb(RAM_BASE + offs["player_state"]),
        "insta": cpu.rb(RAM_BASE + offs["instashield"]),
        "fly_fuel": cpu.rb(RAM_BASE + offs["fly_fuel"]),
        "fly_thrust": cpu.rb(RAM_BASE + offs["fly_thrust"]),
        "sst_reads": {r for r in reads if r is not None},
        "blk_reads": blk_reads,
        "events": events,
    }


def decode(rom, start, end):
    import capstone
    md = capstone.Cs(capstone.CS_ARCH_M68K,
                     capstone.CS_MODE_BIG_ENDIAN | capstone.CS_MODE_M68K_000)
    prog, listing = {}, []
    for insn in md.disasm(rom[start:end], start):
        ops = [parse_operand(t) for t in _split_ops(insn.op_str)] if insn.op_str else []
        prog[insn.address] = (insn.mnemonic, ops, insn.address + insn.size)
        listing.append((insn.address, insn.bytes.hex(), insn.mnemonic, insn.op_str))
    covered = sum(prog[a][2] - a for a in prog)
    if covered != end - start:
        raise SystemExit("instashield_gate: capstone decoded %d of %d bytes in "
                         "[$%06X,$%06X) — the extent is not a clean instruction run"
                         % (covered, end - start, start, end))
    return prog, listing


# --------------------------------------------------------------------------
# The sweep
# --------------------------------------------------------------------------

def constants(equs):
    need = ["PSTATE_JUMP", "PSTATE_ROLLJUMP", "PSTATE_AIR", "PSTATE_AIRBALL",
            "PSTATE_COUNT", "INSTASHIELD_READY", "INSTASHIELD_ATTACKING",
            "INSTASHIELD_SPENT", "INSTASHIELD_SUPPRESS_MASK"]
    missing = [n for n in need if n not in equs]
    if missing:
        raise SystemExit("instashield_gate: the listing carries no equate for %s — "
                         "this gate derives its expectations from the build's own "
                         "constants and will not substitute a literal"
                         % ", ".join(missing))
    return {n: equs[n] for n in need}


def status2_probes(mask):
    """The empty set, every single bit of the suppression mask on its own, the whole
    mask, and one bit OUTSIDE it (which must NOT suppress)."""
    out = [0, mask]
    for b in range(8):
        if mask & (1 << b):
            out.append(1 << b)
    outside = [1 << b for b in range(8) if not (mask & (1 << b))]
    out.extend(outside[:2])
    return sorted(set(out))


def sweep(rom, prog, start, end, stubs, offs, k, verbose=False):
    insta_vals = [k["INSTASHIELD_READY"], k["INSTASHIELD_ATTACKING"],
                  k["INSTASHIELD_SPENT"]]
    probes = status2_probes(k["INSTASHIELD_SUPPRESS_MASK"])
    fails, total = [], 0
    fired_states = set()
    for state in range(256):
        for insta in insta_vals:
            for s2 in probes:
                total += 1
                got = run_case(rom, prog, start, end, stubs, offs, state, insta, s2)
                want_fires, want_cancel, want_state, want_insta = \
                    model(state, insta, s2, k)
                if got["spawned"]:
                    fired_states.add(state)
                bad = []
                if got["spawned"] != want_fires:
                    bad.append("fires=%s want %s" % (got["spawned"], want_fires))
                if got["insta"] != want_insta:
                    bad.append("instashield=%d want %d" % (got["insta"], want_insta))
                if got["state"] != want_state:
                    bad.append("player_state=$%02X want $%02X"
                               % (got["state"], want_state))
                did_cancel = bool(got["set_state"])
                if did_cancel != want_cancel:
                    bad.append("rolljump-cancel=%s want %s" % (did_cancel, want_cancel))
                if want_cancel and got["set_state"] != [k["PSTATE_JUMP"]]:
                    bad.append("cancel target %s want [%d]"
                               % (got["set_state"], k["PSTATE_JUMP"]))
                if got["spawned"] and got["sfx"] is None and "Sound_PlaySFX" in \
                        set(stubs.values()):
                    bad.append("spawned but posted no SFX")
                if bad:
                    fails.append((state, insta, s2, "; ".join(bad)))
    return total, fails, fired_states


def yvel_probes(cap):
    """DERIVED from the cap, not copied from a physics row: the two values either side
    of the boundary and the boundary itself (which must PASS — the compare is `blt`, so
    y_vel == cap engages), plus the extremes of the signed word and a value a whole
    jump-force away in each direction."""
    out = {cap - 1, cap, cap + 1, 0, -0x8000, 0x7FFF, cap - 0x100, cap + 0x100}
    return sorted(v for v in out if -0x8000 <= v <= 0x7FFF)


def cap_probes():
    """The release cap is an INPUT here — the routine reads it out of the slot's
    physics row through a4 — so it is swept rather than pinned. -$400 and -$200 are
    S3K's surface/underwater pair; 0 is the degenerate row that would let any
    non-rising frame through and must still obey the state gate."""
    return (-0x400, -0x200, 0)


def sweep_flight(rom, prog, start, end, stubs, offs, k, cap_off, y_vel_off):
    fails, total = [], 0
    engaged_states = set()
    for state in range(256):
        for cap in cap_probes():
            for y in yvel_probes(cap):
                total += 1
                got = run_case(rom, prog, start, end, stubs, offs, state,
                               sst_words={y_vel_off: y},
                               blk_words={cap_off: cap})
                want_eng, want_state, want_fuel, want_thrust = \
                    model_flight(state, y, cap, k)
                engaged = got["set_state"] == [k["PSTATE_FLY"]]
                if engaged:
                    engaged_states.add(state)
                bad = []
                if engaged != want_eng:
                    bad.append("engages=%s want %s" % (engaged, want_eng))
                if got["state"] != want_state:
                    bad.append("player_state=$%02X want $%02X"
                               % (got["state"], want_state))
                # A REFUSAL MUST WRITE NOTHING. The synthetic SST reads 0 where nothing
                # was written, so 0 is the "untouched" witness for both scratch bytes —
                # and FLY_COAST is 1 and FLY_FUEL_TICKS is 240, so neither seed can be
                # confused with it.
                exp_fuel = want_fuel if want_fuel is not None else 0
                exp_thrust = want_thrust if want_thrust is not None else 0
                if got["fly_fuel"] != exp_fuel:
                    bad.append("fly_fuel=%d want %d" % (got["fly_fuel"], exp_fuel))
                if got["fly_thrust"] != exp_thrust:
                    bad.append("fly_thrust=%d want %d"
                               % (got["fly_thrust"], exp_thrust))
                if bad:
                    fails.append((state, y, cap, "; ".join(bad)))
    return total, fails, engaged_states


# --------------------------------------------------------------------------
# The committed cut — so the pytest lane can run the same sweep without a fresh ROM
# --------------------------------------------------------------------------

def cut_note(routine):
    return ("%s's bytes, per BUILD SHAPE, and the constants each was "
            "built with. The two canonical shapes place the routine at different "
            "addresses, so one cut cannot serve both. Regenerate with "
            "tools/instashield_gate.py --write-fixture (it preserves the other shape)."
            % routine)


CUT_NOTE = cut_note(ROUTINE)

CUT_KEYS = ("start", "end", "bytes", "stubs", "sst_custom", "offsets", "constants")


def shape_key(lst_path):
    return pathlib.Path(lst_path).name


def build_cut(rom, start, end, stubs, offs, k, sst_custom, lst_path, existing=None,
              note=CUT_NOTE):
    doc = existing or {"_note": note, "shapes": {}}
    doc["_note"] = note
    doc.setdefault("shapes", {})[shape_key(lst_path)] = {
        "start": start,
        "end": end,
        "bytes": rom[start:end].hex(),
        "stubs": {"%06X" % a: n for a, n in stubs.items()},
        "sst_custom": sst_custom,
        "offsets": offs,
        "constants": k,
    }
    return doc


def _read_cut_doc(path):
    doc = json.loads(pathlib.Path(path).read_text())
    if "shapes" not in doc:
        raise SystemExit("instashield_gate: %s predates the shape-keyed format; "
                         "regenerate it with --write-fixture" % path)
    return doc


def cut_shapes(path):
    return sorted(_read_cut_doc(path)["shapes"])


def load_cut(path, shape=None):
    """Rebuild a sparse ROM + the gate's inputs from one shape's committed cut."""
    doc = _read_cut_doc(path)
    if shape is None:
        shape = sorted(doc["shapes"])[0]
    cut = doc["shapes"][shape]
    missing = [k for k in CUT_KEYS if k not in cut]
    if missing:
        raise SystemExit(
            "instashield_gate: %s shape %r is missing %s — it was stamped by an older "
            "version of this gate and cannot be graded. Regenerate with "
            "tools/instashield_gate.py --write-fixture."
            % (path, shape, ", ".join(missing)))
    rom = bytearray(cut["end"])
    rom[cut["start"]:cut["end"]] = bytes.fromhex(cut["bytes"])
    stubs = {int(a, 16): n for a, n in cut["stubs"].items()}
    return (bytes(rom), cut["start"], cut["end"], stubs, cut["offsets"],
            cut["constants"], cut["sst_custom"])


# --------------------------------------------------------------------------
# Relocation-invariant fixture comparison  (ported from sprite_tilt_gate.py)
#
# WHAT WAS WRONG. `check_cut` used to require `cut["start"] == start and cut["end"] ==
# end`, and then raw byte equality of the routine. Both of those go red for something
# that is NOT a defect. These two routines each end in a transfer to a symbol outside
# themselves — Ability_InstaShield tails into `Sound_PlaySFX` and calls
# `Player_SetState`/`InstaShield_Spawn`; Ability_TailsFlight tails into
# `Player_SetState` — so ANY parcel that shifts player code moves the routine (red #1)
# AND rewrites the displacement bytes baked into the routine's own body (red #2).
# Re-keying the fixture on symbol-relative offsets alone would only relocate the same
# false red one level down into the byte comparison; that was measured on the tilt/loop
# pair and it applies here unchanged.
#
# A canonical-base relocation is NOT available as a fix: the two build shapes' symbols
# move by DIFFERENT deltas (here, Sound_PlaySFX sits at $0081A8 in the release shape and
# $00B4EA in DEBUG while the routine itself moves by only $10C), so no single base
# exists. That was measured on the first pair too, and is why the answer is a
# normalisation rather than a rebasing.
#
# WHAT IT DOES NOW. The comparison is over the DECODED INSTRUCTION STREAM with every
# operand that names a *place* rewritten to what it means (see the long note over
# `normalize_stream` in sprite_tilt_gate.py):
#
#   a target inside the routine  ->  <self+0xNN>
#   an address naming a symbol   ->  <SymbolName>     (the cut's OWN stub names, and the
#                                                      SAME name set on both sides)
#   anything else                ->  compared verbatim, and REPORTED as unresolved
#
# Opcodes, sizes, registers, immediates and (a0)/(a4) displacements are all still
# compared exactly, so every logic change the raw-byte check caught is still caught.
# --------------------------------------------------------------------------

# Transfer-of-control mnemonics whose ENCODING the assembler picks by reach, not by
# meaning. `bra`/`jmp` are one transfer at two reaches and so are `bsr`/`jsr`; a
# conditional branch relaxes between `.b` and `.w` with its base mnemonic unchanged.
# A difference confined to these, with the resolved TARGET identical, was caused by
# relocation and must not be described as an edit.
_XFER_ALIAS = {"bra": "goto", "jmp": "goto", "bsr": "call", "jsr": "call"}


def xfer_class(mnem):
    """The relaxation class of a mnemonic, or None if it has none.

    None is the safe answer: an instruction with no class can never be excused as a
    relaxation, so a mnemonic this does not recognise is reported as an EDIT.
    """
    base = mnem.split(".", 1)[0].lower()
    if base in _XFER_ALIAS:
        return _XFER_ALIAS[base]
    # bcc/bne/beq/bge/... — exactly three letters, and `bra`/`bsr` are already taken
    # above. `bclr`/`bchg`/`bset`/`btst` are four and correctly fall through to None.
    if len(base) == 3 and base.startswith("b"):
        return "b" + base[1:]
    return None


_SELF_TOK = re.compile(r"<self\+0x([0-9A-F]+)>")


def _by_instruction(op_str, rows):
    """Rewrite `<self+0xNN>` to `<self#i>`, naming the INSTRUCTION it targets rather than
    the byte offset it happens to sit at.

    An internal branch's byte offset is not stable under a relaxation EARLIER in the same
    routine: widen one transfer and every offset behind it slides, so three untouched
    `bne` instructions in Ability_InstaShield read as `<self+0x3E>` in one shape and
    `<self+0x3C>` in the other while pointing at the same `rts`. Measured on the two
    committed cuts — it is why this pass exists at all. An offset that is not the start
    of any instruction is left alone, so a branch into the middle of one (which would be
    a real finding) can never be smoothed away.
    """
    at = {r[0]: i for i, r in enumerate(rows)}
    return _SELF_TOK.sub(
        lambda m: ("<self#%d>" % at[int(m.group(1), 16)]
                   if int(m.group(1), 16) in at else m.group(0)),
        op_str)


def classify_stream(cut_rows, live_rows, name):
    """Split the differences between two normalised streams by CAUSE.

    Returns (edits, relaxations). BOTH ARE FATAL — a relaxed routine is genuinely not the
    bytes the pytest lane grades, and re-stamping is still required — so nothing is
    forgiven here and no detection is lost. What differs is the SENTENCE, and the
    sentence is what a reader carries forward. Calling a reach-driven `bra.w` -> `jmp.l`
    "the routine was edited" is the fabricated-reason failure this parcel exists to
    remove, one level in from the address check.

    Three classes:
      RELAXED  the same transfer to the same named target at a different reach
      SLID     an untouched instruction whose internal target moved because something
               ahead of it relaxed — only ever attributed once a relaxation is present
      differs  everything else: a real edit
    """
    edits, relax = [], []
    if len(cut_rows) != len(live_rows):
        edits.append("%s: the instruction COUNT changed (cut %d, live %d) — the routine "
                     "was edited, not moved" % (name, len(cut_rows), len(live_rows)))
        return edits, relax

    # Pass 1: name every difference, and note which ones are pure internal slides.
    findings, relaxed_any = [], False
    for i, (c, l) in enumerate(zip(cut_rows, live_rows)):
        if c[1:] == l[1:]:
            continue
        cc, lc = xfer_class(c[1]), xfer_class(l[1])
        if c[2] == l[2] and cc is not None and cc == lc:
            relaxed_any = True
            findings.append(("relax", i, c, l))
        elif c[1] == l[1] and (_by_instruction(c[2], cut_rows)
                               == _by_instruction(l[2], live_rows)):
            findings.append(("slide", i, c, l))
        else:
            findings.append(("edit", i, c, l))

    # Pass 2: a slide is only explainable once a relaxation is on record. With no
    # relaxation, an instruction that moved inside its own routine means the routine's
    # geometry changed for some other reason, and that is an EDIT — the excuse must not
    # be available for free.
    for kind, i, c, l in findings:
        if kind == "relax":
            relax.append("%s: instruction %d (cut offset +0x%X) RELAXED — `%s` became "
                         "`%s`, same target `%s`. The assembler picked a different reach "
                         "because the code MOVED; the routine was not edited"
                         % (name, i, c[0], c[1], l[1], c[2]))
        elif kind == "slide" and relaxed_any:
            relax.append("%s: instruction %d (cut +0x%X, live +0x%X) still reaches the "
                         "SAME instruction of this routine, which SLID — `%s %s` now "
                         "reads `%s`. Something between them relaxed; this instruction "
                         "was not edited"
                         % (name, i, c[0], l[0], c[1], c[2], l[2]))
        else:
            edits.append("%s: instruction %d (cut offset +0x%X) differs — cut `%s %s`, "
                         "live `%s %s`" % (name, i, c[0], c[1], c[2], l[1], l[2]))
        if len(edits) + len(relax) >= 8:
            edits.append("%s: ... further differences suppressed" % name)
            break
    return edits, relax


def placement_notes(cut, start, end, syms):
    """What MOVED, said out loud on the success path.

    A relocation is not a failure any more, but it is also not nothing: it is the
    explanation a reader needs for why the fixture's numbers no longer match the build's.
    Printing it is what keeps 'the gate is green' and 'the addresses differ' from looking
    like a contradiction the next time someone diffs the fixture by hand.
    """
    notes = []
    if (start, end) != (cut["start"], cut["end"]):
        notes.append("the routine MOVED (not edited): cut $%06X..$%06X, this build "
                     "$%06X..$%06X (%+d bytes, length %d -> %d)"
                     % (cut["start"], cut["end"], start, end,
                        start - cut["start"], cut["end"] - cut["start"], end - start))
    moved = ["%s $%06X -> $%06X" % (n, a, syms[n])
             for a, n in sorted(((int(a, 16), n) for a, n in cut["stubs"].items()))
             if n in syms and syms[n] != a]
    if moved:
        notes.append("symbol(s) it references MOVED (not renamed, not edited): %s"
                     % "; ".join(moved))
    return notes


def check_cut(rom, start, end, syms, path, lst_path, routine=ROUTINE):
    """THIS SHAPE's committed cut must still be the same ROUTINE the fresh ROM holds —
    up to relocation, and nothing more than relocation.

    Still proved: the decoded instruction stream (so every opcode, size, register,
    immediate and SST/PlayerBlock displacement), that each transfer still reaches the
    SAME NAMED symbol, and that every symbol the cut anchors still exists.
    No longer required: that any of it sits at the address it did when stamped.

    Raises SystemExit on a real difference; returns the informational placement notes
    otherwise.
    """
    doc = _read_cut_doc(path)
    shape = shape_key(lst_path)
    if shape not in doc["shapes"]:
        raise SystemExit(
            "instashield_gate: %s carries no cut for shape %r (have: %s) — the pytest "
            "lane covers the other shape(s) only. Regenerate with --write-fixture."
            % (path, shape, ", ".join(sorted(doc["shapes"]))))
    cut = doc["shapes"][shape]
    problems = []

    # The cut's own stub names, and nothing more, resolved on BOTH sides. An asymmetric
    # resolver — the fixture's three names against the listing's thousands — would invent
    # differences of its own.
    cut_names = {int(a, 16): n for a, n in cut["stubs"].items()}
    names = sorted(set(cut_names.values()))

    # Existence first, because a symbol that VANISHED is a different failure from one
    # that moved, and the old address check conflated them.
    gone = [n for n in names if n not in syms]
    if gone:
        problems.append("symbol(s) the cut anchors are GONE from the listing: %s — "
                        "renamed or removed, not moved" % ", ".join(gone))
    live_names = {syms[n]: n for n in names if n in syms}

    cb = bytes.fromhex(cut["bytes"])
    if len(cb) != cut["end"] - cut["start"]:
        raise SystemExit(
            "instashield_gate: %s shape %r is INTERNALLY INCONSISTENT — it holds %d "
            "bytes for the span $%06X..$%06X (%d bytes). This is a broken fixture, not "
            "a finding about the build. Regenerate with --write-fixture."
            % (path, shape, len(cb), cut["start"], cut["end"],
               cut["end"] - cut["start"]))

    img = bytearray(cut["end"])
    img[cut["start"]:cut["end"]] = cb
    cut_rows, cut_unres = normalize_stream(bytes(img), cut["start"], cut["end"],
                                           cut_names, "instashield_gate")
    live_rows, live_unres = normalize_stream(rom, start, end, live_names,
                                             "instashield_gate")
    edits, relax = classify_stream(cut_rows, live_rows, routine)
    problems += edits + relax
    notes = placement_notes(cut, start, end, syms)

    if problems:
        if edits or relax:
            problems += unresolved_note(routine, cut_unres + live_unres)
        headline = ("the ROUTINE CHANGED" if edits else
                    "the routine RELAXED under a relocation" if relax else
                    "a symbol it anchors is gone")
        raise SystemExit(
            "instashield_gate: %s shape %r is STALE — %s. The pytest lane is grading a "
            "routine this build does not have:\n  %s%s\n  If every line above says "
            "RELAXED or MOVED, no logic changed and the fixture is simply re-stamped; an "
            "instruction that `differs` is a real edit and needs explaining first. "
            "Regenerate with tools/instashield_gate.py --write-fixture."
            % (path, shape, headline, "\n  ".join(problems),
               ("\n  " + "\n  ".join(notes)) if notes else ""))
    return notes


# --------------------------------------------------------------------------
# The Tails subject's inputs, derived the same way
# --------------------------------------------------------------------------

TAILS_CONSTS = ("FLY_FUEL_TICKS", "FLY_COAST", "PBLK_RELEASE_CAP")


def tails_inputs(equs, src_root=ROOT):
    """(constants, cap_off, y_vel_off) for Ability_TailsFlight.

    PSTATE_* come from the build's equates; FLY_FUEL_TICKS / FLY_COAST /
    PBLK_RELEASE_CAP are module-private `const`s and come from player_fly.emp itself
    (see source_consts). SST_y_vel is the build's own struct export.
    """
    for need in ("PSTATE_JUMP", "PSTATE_ROLLJUMP", "PSTATE_FLY", "SST_y_vel"):
        if need not in equs:
            raise SystemExit(
                "instashield_gate: the listing carries no equate for %s — the flight "
                "gate derives its expectations from the build's own constants and "
                "will not substitute a literal" % need)
    src = source_consts(TAILS_SRC, TAILS_CONSTS, src_root)
    k = {n: equs[n] for n in ("PSTATE_JUMP", "PSTATE_ROLLJUMP", "PSTATE_FLY")}
    k["FLY_FUEL_TICKS"] = src["FLY_FUEL_TICKS"]
    k["FLY_COAST"] = src["FLY_COAST"]
    return k, src["PBLK_RELEASE_CAP"], equs["SST_y_vel"]


def check_cap_displacement(prog, cap_off):
    """The a4 displacement the ROUTINE actually encodes, against PBLK_RELEASE_CAP as
    player_fly.emp declares it. This is the flight gate's peer of the `_pl_state`
    cross-check: the source value is what the model seeds, so if the routine reaches a
    DIFFERENT field of the physics row the model would be grading the wrong input."""
    seen = {op[1] for _, ops, _ in prog.values() for op in ops
            if op[0] == "disp" and op[2] == 4}
    if seen != {cap_off}:
        raise SystemExit(
            "instashield_gate: %s reaches a4 displacement(s) %s, but player_fly.emp "
            "declares PBLK_RELEASE_CAP = %d. Either the routine now reads another "
            "PlayerBlock field (the model has to grow) or the const drifted."
            % (TAILS_ROUTINE, sorted("+%d" % d for d in seen) or "(none)", cap_off))


# --------------------------------------------------------------------------

def _staleness_ok(args):
    if args.built_after is None:
        return True
    for p in (pathlib.Path(args.rom), pathlib.Path(args.lst)):
        age = int(p.stat().st_mtime) - args.built_after
        if age < 0:
            print("instashield_gate: %s is OLDER than this build started (%ds) — "
                  "refusing to grade a stale artifact" % (p, -age))
            return False
    return True


def _fixture_verdict(rom, start, end, syms, fixture, lst, gate, routine=ROUTINE):
    """(ok, hard_fail). Shared by both passes."""
    if pathlib.Path(fixture).exists():
        try:
            notes = check_cut(rom, start, end, syms, fixture, lst, routine)
        except SystemExit as e:
            print("  %s" % e)
            return False, gate
        print("  fixture: %s [%s] — the committed cut is this build's %s: decoded "
              "instruction stream identical, every transfer reaching the same named "
              "symbol (relocation normalised)"
              % (pathlib.Path(fixture).name, shape_key(lst), routine))
        for n in notes:
            print("    note: %s" % n)
        return True, False
    print("  fixture: %s MISSING — the pytest lane has nothing to grade "
          "(--write-fixture)" % fixture)
    return False, gate


def pass_instashield(args, rom, syms, equs, offs, overlay_len):
    k = constants(equs)
    start, end = routine_extent(syms, ROUTINE, LOCAL_PREFIX)
    prog, listing = decode(rom, start, end)

    stubs = {}
    for name in ("Player_SetState", "InstaShield_Spawn", "Sound_PlaySFX"):
        if name in syms:
            stubs[syms[name]] = name

    if args.verbose:
        print("  %s $%06X..$%06X (%d bytes, %d instructions)"
              % (ROUTINE, start, end, end - start, len(prog)))
        for a, b, m, o in listing:
            print("    %06X  %-14s %s %s" % (a, b, m, o))

    if args.write_fixture:
        p = pathlib.Path(args.fixture)
        p.parent.mkdir(parents=True, exist_ok=True)
        existing = _read_cut_doc(p) if p.exists() else None
        doc = build_cut(rom, start, end, stubs, offs, k, equs["SST_sst_custom"],
                        args.lst, existing, note=cut_note(ROUTINE))
        p.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n")
        print("instashield_gate: wrote %s (shapes: %s)"
              % (p, ", ".join(sorted(doc["shapes"]))))
        return 0

    total, fails, fired = sweep(rom, prog, start, end, stubs, offs, k,
                                verbose=args.verbose)

    print("  %s $%06X-$%06X (%d bytes, %d instructions), PlayerV overlay %d B"
          % (ROUTINE, start, end - 1, end - start, len(prog), overlay_len))
    print("  %d executions compared against the S3K model "
          "(Sonic_JumpHeight :23369 -> Sonic_ShieldMoves :23401)" % total)
    print("  states that fired: %s" % _named_states(equs, fired))
    print("  the model's allowed set is S3K's `jumping`: PSTATE_JUMP $%02X, "
          "PSTATE_ROLLJUMP $%02X" % (k["PSTATE_JUMP"], k["PSTATE_ROLLJUMP"]))

    # The SUBJECT's own verdict first: a mismatch is the finding, and a stale cut must
    # not be able to mask it behind an unrelated failure message.
    if fails:
        print("  FAIL — %d of %d executions disagree with the model:" % (len(fails), total))
        for state, insta, s2, why in fails[:20]:
            print("    player_state=$%02X instashield=%d status_secondary=$%02X: %s"
                  % (state, insta, s2, why))
        if len(fails) > 20:
            print("    ... and %d more" % (len(fails) - 20))

    _, hard = _fixture_verdict(rom, start, end, syms, args.fixture, args.lst,
                               args.gate, ROUTINE)
    if hard:
        return 1
    if fails:
        return 1 if args.gate else 0
    print("  OK")
    return 0


def pass_tailsflight(args, rom, syms, equs, offs, overlay_len):
    k, cap_off, y_vel_off = tails_inputs(equs)
    start, end = routine_extent(syms, TAILS_ROUTINE, TAILS_LOCAL_PREFIX)
    prog, listing = decode(rom, start, end)
    check_cap_displacement(prog, cap_off)

    stubs = {}
    for name in ("Player_SetState",):
        if name in syms:
            stubs[syms[name]] = name

    if args.verbose:
        print("  %s $%06X..$%06X (%d bytes, %d instructions)"
              % (TAILS_ROUTINE, start, end, end - start, len(prog)))
        for a, b, m, o in listing:
            print("    %06X  %-14s %s %s" % (a, b, m, o))

    # The cut carries everything the pytest lane needs to re-run this sweep with no
    # ROM: the two derived offsets ride in `constants` beside the values, because
    # CUT_KEYS is the format contract and a new top-level key would fail older cuts.
    ck = dict(k, PBLK_RELEASE_CAP=cap_off, SST_y_vel=y_vel_off)

    if args.write_fixture:
        p = pathlib.Path(args.tails_fixture)
        p.parent.mkdir(parents=True, exist_ok=True)
        existing = _read_cut_doc(p) if p.exists() else None
        doc = build_cut(rom, start, end, stubs, offs, ck, equs["SST_sst_custom"],
                        args.lst, existing, note=cut_note(TAILS_ROUTINE))
        p.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n")
        print("instashield_gate: wrote %s (shapes: %s)"
              % (p, ", ".join(sorted(doc["shapes"]))))
        return 0

    total, fails, engaged = sweep_flight(rom, prog, start, end, stubs, offs, k,
                                         cap_off, y_vel_off)

    print("  %s $%06X-$%06X (%d bytes, %d instructions)"
          % (TAILS_ROUTINE, start, end - 1, end - start, len(prog)))
    print("  %d executions compared against the S3K model "
          "(Tails_JumpHeight :28596 -> Tails_Test_For_Flight :28627)" % total)
    print("  states that engaged flight: %s" % _named_states(equs, engaged))
    print("  the model's allowed set is S3K's `jumping`: PSTATE_JUMP $%02X, "
          "PSTATE_ROLLJUMP $%02X; release cap swept over %s"
          % (k["PSTATE_JUMP"], k["PSTATE_ROLLJUMP"],
             ", ".join("%d" % c for c in cap_probes())))

    if fails:
        print("  FAIL — %d of %d executions disagree with the model:" % (len(fails), total))
        for state, y, cap, why in fails[:20]:
            print("    player_state=$%02X y_vel=%d release_cap=%d: %s"
                  % (state, y, cap, why))
        if len(fails) > 20:
            print("    ... and %d more" % (len(fails) - 20))

    _, hard = _fixture_verdict(rom, start, end, syms, args.tails_fixture, args.lst,
                               args.gate, TAILS_ROUTINE)
    if hard:
        return 1
    if fails:
        return 1 if args.gate else 0
    print("  OK")
    return 0


def _named_states(equs, hit):
    named = {v: n for n, v in equs.items() if n.startswith("PSTATE_")
             and n != "PSTATE_COUNT"}
    legal = sorted(n for v, n in named.items() if v in hit)
    stray = sorted(s for s in hit if s not in named)
    return ("%s%s" % (", ".join(legal) or "(none)",
                      "" if not stray else
                      "  + %d value(s) that are not a declared state ($%02X..)"
                      % (len(stray), stray[0])))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lst", required=True)
    ap.add_argument("--rom", required=True)
    ap.add_argument("--fixture", default=str(TOOLS / "fixtures" / "instashield_cut.json"))
    ap.add_argument("--tails-fixture",
                    default=str(TOOLS / "fixtures" / "tailsflight_cut.json"))
    ap.add_argument("--ability", choices=("instashield", "tailsflight", "both"),
                    default="both")
    ap.add_argument("--write-fixture", action="store_true")
    ap.add_argument("--built-after", type=int, default=None,
                    help="unix ts; both artifacts must be newer (staleness guard)")
    ap.add_argument("--gate", action="store_true", help="exit 1 on any failure")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    if not _staleness_ok(args):
        return 1

    rom = pathlib.Path(args.rom).read_bytes()
    syms, equs = parse_lst(args.lst)
    for need in ("SST_sst_custom", "_pl_state"):
        if need not in equs:
            print("instashield_gate: the listing carries no `%s` equate — this gate "
                  "cannot place its synthetic SST without it" % need)
            return 1
    offs, overlay_len = playerv_offsets(equs["SST_sst_custom"])

    # The build's own link-exported offset, against the one parsed from the source
    # block. If the language ever starts aligning `vars` fields, or the overlay is
    # reordered without this gate noticing, this is what fires.
    if offs["player_state"] != equs["_pl_state"]:
        print("instashield_gate: PlayerV.player_state parses to $%02X, but the build "
              "exports _pl_state = $%02X. The overlay parser in this gate has diverged "
              "from the language's layout rule."
              % (offs["player_state"], equs["_pl_state"]))
        return 1

    print("instashield_gate [%s]:" % args.lst)
    rc = 0
    if args.ability in ("instashield", "both"):
        rc |= pass_instashield(args, rom, syms, equs, offs, overlay_len)
    if args.ability in ("tailsflight", "both"):
        rc |= pass_tailsflight(args, rom, syms, equs, offs, overlay_len)
    return rc


if __name__ == "__main__":
    sys.exit(main())
