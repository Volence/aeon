#!/usr/bin/env python3
"""instashield_gate.py — prove Ability_InstaShield refuses every air state that did
NOT come from a jump, by EXECUTING the built ROM's own bytes.

WHY THIS SHAPE. The claim this parcel makes is a REFUSAL — "pressing jump in mid-air
after walking off a ledge must not fire the insta-shield" — and a refusal is the one
thing shipped content cannot demonstrate. The recorded replay net is proof of that: it
stays byte-identical across this change (measured), because every airborne press in the
two fixtures was already made from a real jump. A gate over recorded play therefore
cannot see the half of the behaviour that moved, so the subject here is the ROUTINE,
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

ONE S3K GATE IS DELIBERATELY NOT MODELLED, because it is not built: `Sonic_JumpHeight`
also requires `cmp.w y_vel(a0),d1 / ble.w` with d1 = -$400, i.e. no insta-shield while
still rising faster than the release cap. That is booked in docs/DEFERRED_WORK.md. If
it is ever built, MODEL_RISING_GATE below has to grow with it — the assertion that no
y_vel byte is read (see `test_reads_no_velocity`) is what makes that a loud change
rather than a silent divergence between this model and the routine.

The executor is deliberately NOT a 68000 emulator. It implements one instruction form
per line the routine actually contains and raises UnsupportedInstruction on anything
else, so a future edit reaching for a new addressing mode fails LOUDLY here instead of
being silently skipped. It also refuses to read a register a stubbed callee's declared
contract says was clobbered. That refusal is the whole reason its green is worth
anything.

Usage (the post-sigil gate; see build.sh):

    instashield_gate.py --lst s4.debug.lst --rom s4.debug.bin \
                        --built-after <unix-ts> \
                        --fixture tools/fixtures/instashield_cut.json --gate

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
from sprite_tilt_gate import (  # noqa: E402
    Micro, UnsupportedInstruction, _split_ops, parse_operand,
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


def routine_extent(syms, name=ROUTINE):
    """[start, end) — end is the next symbol strictly above start. The routine's own
    hygienic local labels sit inside it and are skipped."""
    start = syms.get(name)
    if start is None:
        raise SystemExit("instashield_gate: %s is not in the listing. Either the "
                         "ability was renamed or removed, or Sonic's cd_ability no "
                         "longer reaches it." % name)
    above = [a for n, a in syms.items()
             if a > start and not n.startswith(LOCAL_PREFIX)]
    if not above:
        raise SystemExit("instashield_gate: nothing follows %s in the listing" % name)
    return start, min(above)


def playerv_offsets(sst_custom, src_root=ROOT):
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
    for need in ("player_state", "status_secondary", "instashield"):
        if need not in offs:
            raise SystemExit("instashield_gate: PlayerV has no `%s` field — this gate "
                             "probes it by name; a rename must move the gate too"
                             % need)
    return offs, cur


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


class Refusal(Exception):
    """The executor read something a callee's contract says is undefined."""


def run_case(rom, prog, start, end, stubs, offs, state, insta, status2):
    """Execute the routine once. Returns a dict of everything observable."""
    cpu = Micro(rom, RAM_BASE)
    cpu.a[0] = RAM_BASE
    cpu.wb(RAM_BASE + offs["player_state"], state)
    cpu.wb(RAM_BASE + offs["instashield"], insta)
    cpu.wb(RAM_BASE + offs["status_secondary"], status2)

    undef = set()
    events = []
    reads = set()
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
                reads.add(cpu.a[op[2]] + op[1] - RAM_BASE if op[2] == 0 else None)

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
        "sst_reads": {r for r in reads if r is not None},
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


# --------------------------------------------------------------------------
# The committed cut — so the pytest lane can run the same sweep without a fresh ROM
# --------------------------------------------------------------------------

CUT_NOTE = ("Ability_InstaShield's bytes, per BUILD SHAPE, and the constants each was "
            "built with. The two canonical shapes place the routine at different "
            "addresses, so one cut cannot serve both. Regenerate with "
            "tools/instashield_gate.py --write-fixture (it preserves the other shape).")

CUT_KEYS = ("start", "end", "bytes", "stubs", "sst_custom", "offsets", "constants")


def shape_key(lst_path):
    return pathlib.Path(lst_path).name


def build_cut(rom, start, end, stubs, offs, k, sst_custom, lst_path, existing=None):
    doc = existing or {"_note": CUT_NOTE, "shapes": {}}
    doc["_note"] = CUT_NOTE
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


def check_cut(rom, start, end, path, lst_path):
    """THIS SHAPE's committed cut must still be what the fresh ROM holds."""
    doc = _read_cut_doc(path)
    shape = shape_key(lst_path)
    if shape not in doc["shapes"]:
        raise SystemExit(
            "instashield_gate: %s carries no cut for shape %r (have: %s) — the pytest "
            "lane covers the other shape(s) only. Regenerate with --write-fixture."
            % (path, shape, ", ".join(sorted(doc["shapes"]))))
    cut = doc["shapes"][shape]
    if cut["start"] != start or cut["end"] != end or \
            cut["bytes"] != rom[start:end].hex():
        raise SystemExit(
            "instashield_gate: %s shape %r is STALE — it holds $%06X..$%06X (%d bytes) "
            "but this build has $%06X..$%06X (%d bytes). The pytest lane is grading a "
            "routine that no longer exists; regenerate with --write-fixture."
            % (path, shape, cut["start"], cut["end"], cut["end"] - cut["start"],
               start, end, end - start))


# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lst", required=True)
    ap.add_argument("--rom", required=True)
    ap.add_argument("--fixture", default=str(TOOLS / "fixtures" / "instashield_cut.json"))
    ap.add_argument("--write-fixture", action="store_true")
    ap.add_argument("--built-after", type=int, default=None,
                    help="unix ts; both artifacts must be newer (staleness guard)")
    ap.add_argument("--gate", action="store_true", help="exit 1 on any failure")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    if args.built_after is not None:
        for p in (pathlib.Path(args.rom), pathlib.Path(args.lst)):
            age = int(p.stat().st_mtime) - args.built_after
            if age < 0:
                print("instashield_gate: %s is OLDER than this build started (%ds) — "
                      "refusing to grade a stale artifact" % (p, -age))
                return 1

    rom = pathlib.Path(args.rom).read_bytes()
    syms, equs = parse_lst(args.lst)
    k = constants(equs)
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

    start, end = routine_extent(syms)
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
                        args.lst, existing)
        p.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n")
        print("instashield_gate: wrote %s (shapes: %s)"
              % (p, ", ".join(sorted(doc["shapes"]))))
        return 0

    total, fails, fired = sweep(rom, prog, start, end, stubs, offs, k,
                                verbose=args.verbose)

    print("instashield_gate [%s]:" % args.lst)
    print("  %s $%06X-$%06X (%d bytes, %d instructions), PlayerV overlay %d B"
          % (ROUTINE, start, end - 1, end - start, len(prog), overlay_len))
    print("  %d executions compared against the S3K model "
          "(Sonic_JumpHeight :23369 -> Sonic_ShieldMoves :23401)" % total)
    named = {v: n for n, v in equs.items() if n.startswith("PSTATE_")
             and n != "PSTATE_COUNT"}
    legal = sorted(n for v, n in named.items() if v in fired)
    stray = sorted(s for s in fired if s not in named)
    print("  states that fired: %s%s"
          % (", ".join(legal) or "(none)",
             "" if not stray else
             "  + %d value(s) that are not a declared state ($%02X..)"
             % (len(stray), stray[0])))
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

    if pathlib.Path(args.fixture).exists():
        try:
            check_cut(rom, start, end, args.fixture, args.lst)
        except SystemExit as e:
            print("  %s" % e)
            return 1 if args.gate else 0
        print("  fixture: %s [%s] — the committed cut is this build's routine, "
              "byte-identical"
              % (pathlib.Path(args.fixture).name, shape_key(args.lst)))
    else:
        print("  fixture: %s MISSING — the pytest lane has nothing to grade "
              "(--write-fixture)" % args.fixture)
        if args.gate:
            return 1

    if fails:
        return 1 if args.gate else 0

    print("  OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
