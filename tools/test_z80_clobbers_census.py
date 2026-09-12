#!/usr/bin/env python3
"""
Z80 clobbers() UNDER-declaration census (CTRL-1 / docs/DEFERRED_WORK.md LS-2a).

WHY THIS FILE EXISTS. `CODING_CONVENTIONS.md` §2.8 carries a four-cell table of what the
build verifies about register contracts. Exactly one cell is guarded by sigil's own build:
68000 under-declaration, by the `[proc.clobber-undeclared]` closure gate. The Z80 row had no
gate in either direction, and the LS-2 control proved it: `Seq_Op_NoteFill`'s `ld a,(hl)`
swapped for the same-size `ld b,(hl)` wrote an undeclared `b` and built green with the
warning summary unchanged. Under-declaration is the correctness class (a caller trusting the
contract keeps a value in a register the callee destroys), so it is the Z80 cell this file
guards. Over-declaration is NOT checked here, on either CPU, on purpose: LS-2's closure left
it unguarded with written reasons (it is used deliberately, and a wider declaration only
makes callers save more, never less).

THE CONTRACT THIS CHECKS, and where it is written down. A proc's `clobbers(...)` covers
"the write set INCLUDING outputs, plus callee effects" (CODING_CONVENTIONS.md §2.8). Sigil
states the same rule as `[call.clobbers-incomplete]`: the declared set must be a superset of
"local writes ∪ reachable-callee clobbers − verified preserves"
(sigil-harness/src/seam1.rs `z80_clobbers_report`, closure.rs `compute_closure`). Sigil runs
that check only in its own test suite, not in `sigil build`, and it EXCLUDES the sequencer's
opcode-dispatch sub-machine (`is_opcode_dispatch_proc`: every `Seq_Op_*` plus
`Seq_ContinueFetch`), because their tail jump back into the fetch loop enters a computed
dispatch it cannot bound. So for the `Seq_Op_*` handlers this file is the only check.

WHAT IT CHECKS. Every `proc` in a Z80 module under engine/ and games/ (a module or section
declared `cpu: z80`) that declares a contract must declare, in its `clobbers(...)`,
`preserves(...)` or `out(...)` or its module's `invariant: preserves(...)`, every register
half in:

  (1) its OWN writes, recognised from CODE only (comments and string literals are stripped
      first). Every Z80 mnemonic is modelled from the instruction set (Zilog UM0080's
      per-instruction register and flag effects), not from what the tree happens to use,
      in `z80_writes`. `f` is the flag register: an instruction that changes ANY flag
      writes it. A memory destination (`(hl)`, `(ix+d)`, `(nn)`) writes no register.

        ld   R, ...            R (a register destination); `ld a,i`/`ld a,r` also f
        pop  RR                RR, unless it is a RESTORE (below)
        add/adc/sub/sbc/and/or/xor (8-bit)                        a, f
        add/adc/sbc HL|IX|IY, rr                                  the pair, f
        cp                                                        f
        inc/dec r (8-bit)      r, f     inc/dec (mem)  f     inc/dec rr (16-bit)  rr
        daa cpl neg rlca rla rrca rra rld rrd                     a, f
        rlc rl rrc rr sla sra sll srl  r, f on a register; f on memory; r, f for the
                               undocumented `op (ix+d), r` copy form
        bit                    f          set/res  their register target (none on memory)
        scf ccf                f          djnz     b
        ldi ldd ldir lddr      bc, de, hl, f
        cpi cpd cpir cpdr      bc, hl, f  (never a: the accumulator is the search key)
        ini ind inir indr outi outd otir otdr   b, hl, f  (never c: it holds the port)
        exx                    bc, de, hl (the swap reads as a clobber of the main bank)
        ex de,hl               de, hl     ex af,af'  af     ex (sp),HL|IX|IY  the pair
        in r,(c)               r, f       in a,(n)   a      in (c) / in f,(c)  f
        out nop halt di ei im jp jr call ret reti retn rst push   nothing

      A statement the model cannot read FAILS the run instead of reading as "writes
      nothing": an unknown mnemonic, an operand shape the mnemonic does not take, a
      template or comptime call, or an instruction on the same line as an `if {` brace.
      Non-instruction lines are recognised by form: labels, `if`/`else` brace lines,
      `dc.b`/`dc.w`/`dc.l` data, and `ensure(...)`/`pad_to_cycles(...)`, including their
      continuation lines.

  (2) its CALLEES' DECLARED effects: for every `call [cc,] Target` and for the proc's own
      `falls_into Target`, the halves of Target's `clobbers(...)` plus its `out(...)`. The
      callee's declaration is TRUSTED, never inferred from its body: the caller's contract is
      a promise made against the callee's contract, and a callee's deliberate
      over-declaration (LS-2) is exactly what a caller may not assume away. Target's
      `preserves(...)` is not charged. A caller's own `push`/`pop` around a `call` earns it
      nothing unless the caller declares `preserves(...)`: sigil credits a bracket only
      through a declared preserve, and this file does the same.
      (`X.label` resolves to proc X, as sigil's `resolve_callee_key` does.)

TWO RULES, each derived from source, for writes that are not clobbers. There is no
allow-list; the census is zero-firing.

  RESTORE POP. A `pop RR` whose matching `push` (paired in text order, innermost first)
  saved the same pair RR returns RR to its value at that push, so the pop cannot be the
  write that clobbers it; any write between the two is counted by its own form. That is
  the DEBUG-only save pair around `Seq_Trace` (`push hl` / `call Seq_Trace` / `pop hl` in
  Seq_Op_RepeatStart and Seq_Op_LoopPoint, and `push hl` / `push bc` ... `pop bc` / `pop hl`
  in Seq_Op_RepeatEnd). Any other pop WRITES what it pops: the move idiom
  (`push ix` / `pop de`) and a pop with nothing left above it in text order. The second is
  how a branch-split pair reads (one `push af`, then a `pop af` on each of two exit paths,
  measured in SfxDispatch and Sfx_SelectVoice): it over-counts, which can only make the
  census fire, never hide a write. Sigil's own local-write set counts no pop at all
  (`z80_written_registers`); this file keeps the move idiom because it does write.

  NORETURN SP. In an `@noreturn` proc a write to `sp` is not a clobber. The proc never
  returns, so no caller's stack is replaced under it; it is setting up its own
  (SndDrv_Init's `ld sp, SND_STACK_TOP` at reset). Sigil's contract does not track `sp` at
  all (z80_preserves.rs UNITS: "stack discipline, never tracked"). Anywhere ELSE an `sp`
  write fires: in a returning proc it is a stack hazard, not a declaration to widen.

UNMEASURABLE CASES FAIL, they are never skipped: a call target that resolves to no Z80
proc, a callee with no `clobbers(...)` clause (its write set is undeclared, and inferring it
is exactly what this file refuses to do), a `call` operand it cannot parse, an `rst` (no
named target), and a proc name defined twice. An attribute token this file does not
recognise also fails the run, and so does a statement it cannot model (above).

THE CONVENTION FOR THE STREAM POINTER. The sequencer's opcode handlers advance `hl`, the
stream pointer, past their operands and hand it to Sequencer_NextOpcode.fetch, and they
spell that effect `clobbers(..., hl)` (Seq_Op_Macro, Seq_Op_RegDelta and every handler).
`out()` is not the spelling for it: in this driver `out()` names a value returned to a
`call` site, and no `Seq_Op_*` handler is called. Records:
docs/superpowers/notes/2026-09-11-lens-z3-parcel.md (the allow-list this file carried),
docs/superpowers/notes/2026-09-12-ctrl1-seqop-clobbers.md (its removal) and
docs/DEFERRED_WORK.md LS-2a (the call-containing procs, 2026-09-12).

WHAT IT DOES NOT COVER, each a real hole:
  * TAIL JUMPS. A `jp`/`jr` into another proc hands the caller that proc's effects too;
    nothing here follows a jump (a `falls_into` IS followed, above). Measured at 808141f7:
    following every tail jump to a proc other than the fetch loop would add ZERO registers.
    What it would add comes only from the handlers' `jp Sequencer_NextOpcode.fetch`, the
    re-entry into the computed dispatch that sigil also declines to bound. (Seq_Op_Ext is
    entered by a `jp z` from Sequencer_NextOpcode, whose own declaration covers `hl`.)
  * THE SHADOW BANK. `exx` and `ex af,af'` are charged as writes of the MAIN registers
    they swap out (conservative, so they can only make the census fire). A write made
    while the shadow bank is swapped in lands in bc'/de'/hl'/af', which no contract
    token names, so no declaration can be checked for it.
  * SHAPES. The scan reads source, not a shape: a DEBUG-only write or `call` (inside
    `if DEBUG == 1 { }`) counts in every shape. That is the right direction for one
    declaration shared by both shapes.
  * TEMPLATES. A comptime fn or `asm {}` template expanded inside a proc body writes
    registers no text scan can see. Such a line is an unmodelled statement, so it FAILS
    the run rather than passing unseen; none is in the Z80 tree today.
  * PROCS WITH NO CONTRACT ATTRIBUTE AT ALL. Nothing is declared, so nothing can be
    under-declared. They are pinned as an exact, named set instead
    (test_attribute_less_z80_procs_are_the_known_set), so a new one fails.
  * THE 68000. Sigil's closure gate owns that cell.
  * RUNTIME. Nothing here executes a ROM or reads a listing.

Runner: build.sh's PRE-BUILD tool-suite pytest lane (`python3 -m pytest "${TOOLS}"
-m "not needs_build"`, build-fatal), which collects `tools/test_*.py` by directory glob.
Also runnable standalone: `python3 tools/test_z80_clobbers_census.py`.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ROOTS = ("engine", "games")

# The module the reach control requires the sweep to find: the sequencer, home of the
# opcode handlers.
SEQ = "engine/sound/sound_sequencer.emp"

# Z80 procs that declare NO contract attribute, each with its in-source reason. Exact set,
# derived by this file's scanner at e4b4f38f.
#   Z80_IdleProgram: the Z80's own reset-time program, `@noreturn`, never called; its
#   header says omitting the clause is the honest spelling ("An empty `clobbers()` would
#   falsely claim it touches nothing; omitting the clause declares no contract").
KNOWN_ATTRIBUTE_LESS: frozenset[tuple[str, str]] = frozenset({
    ("engine/system/z80_init.emp", "Z80_IdleProgram"),
})

# FLOORS on the population. A floor catches the sweep going blind (a moved root, a changed
# `cpu:` spelling, a call parser that stopped matching); it is not a census, and deleting
# procs legitimately means lowering it. Files, procs and leaves derived at e4b4f38f (172 Z80
# procs, 97 of them leaves, in 11 files); the call-containing procs and the two edge counts
# derived at 808141f7 (75 procs, 227 `call` sites, 11 `falls_into` edges). The flag
# writers derived at d5ee8633, the base of the implicit-writer widening (LS-2a item (b)):
# 108 procs write `f`, where the explicit-form parser saw 3 (the `pop af` sites). A write
# model that stopped reading the implicit forms would fall back toward 3.
MIN_Z80_FILES = 11
MIN_Z80_PROCS = 172
MIN_LEAF_PROCS = 97
MIN_CALL_PROCS = 75
MIN_CALL_EDGES = 227
MIN_FALLS_INTO_EDGES = 11
MIN_FLAG_WRITERS = 108

# ---------------------------------------------------------------------------------------
# The scanner.
# ---------------------------------------------------------------------------------------
RE_MODULE_ATTRS = re.compile(r"^\s*module\s+[\w.]+\s*\((.*)\)\s*$")
RE_SECTION_ATTRS = re.compile(r"^\s*section\s+\w+\s*\(([^)]*)\)")
RE_CPU = re.compile(r"\bcpu\s*:\s*(\w+)")
RE_INVARIANT_PRESERVES = re.compile(r"\binvariant\s*:\s*preserves\s*\(([^)]*)\)")
RE_PROC = re.compile(r"^\s*(?:pub\s+)?proc\s+(\w+)")
RE_LABEL_PREFIX = re.compile(r"^\s*\.?\w+\s*:(?!\s*=)\s*")
RE_NORETURN = re.compile(r"^@noreturn\b")
RE_FALLS_INTO = re.compile(r"\bfalls_into\s+(\w+)")

RE_PUSH = re.compile(r"^push\s+(af|bc|de|hl|ix|iy)\s*$", re.I)
RE_POP = re.compile(r"^pop\s+(af|bc|de|hl|ix|iy)\s*$", re.I)
RE_CALL = re.compile(r"^(?:call|rst)\b", re.I)
# A line that is only block structure: `{`, `}`, `if <cond> {`, `} else {`, `} else if … {`.
# An instruction sharing a line with the brace does NOT match, so it cannot be skipped.
RE_BLOCK_LINE = re.compile(r"(?:\}\s*)?(?:else\b\s*)?(?:if\b[^{}]*)?\{?")
RE_DATA = re.compile(r"^dc\.[bwl]\b", re.I)
# Build-time statements that emit no instruction; their argument list may span lines.
RE_COMPTIME_STMT = re.compile(r"^(?:ensure|pad_to_cycles)\s*\(")
RE_EXPORT_LABEL = re.compile(r"^export\s+\.\w+\s*:\s*")
RE_CALL_TARGET = re.compile(
    r"^call\s+(?:(?:nz|z|nc|c|po|pe|p|m)\s*,\s*)?([A-Za-z_]\w*(?:\.\w+)?)\s*$", re.I)
RE_RST = re.compile(r"^rst\b", re.I)

PAIRS = {
    "af": ("a", "f"), "bc": ("b", "c"), "de": ("d", "e"), "hl": ("h", "l"),
    "ix": ("ixh", "ixl"), "iy": ("iyh", "iyl"),
}
SINGLES = {"a", "f", "b", "c", "d", "e", "h", "l", "ixh", "ixl", "iyh", "iyl", "sp", "i", "r"}


def _strip(line: str) -> str:
    """Drop string literals, then any `//` comment. Literals go first so a `//` inside
    `"…"` cannot truncate the line and a brace inside a message cannot move the depth."""
    line = re.sub(r'"(?:[^"\\]|\\.)*"', '""', line)
    idx = line.find("//")
    return line if idx < 0 else line[:idx]


def halves(reg: str) -> set[str]:
    reg = reg.strip().lower()
    if reg in PAIRS:
        return set(PAIRS[reg])
    if reg in SINGLES:
        return {reg}
    raise ValueError(f"unrecognised Z80 register token {reg!r}")


def declared_halves(attr_text: str | None, where: str) -> set[str]:
    """Expand one attribute's token list. An unknown token is an ERROR, never a skip: a
    new spelling silently read as `declares nothing` or `declares everything` would move
    this census without anyone deciding it should."""
    out: set[str] = set()
    if not attr_text:
        return out
    for tok in attr_text.split(","):
        tok = tok.strip()
        if not tok:
            continue
        if ":" in tok:
            key = tok.split(":", 1)[0].strip().lower()
            if key == "carry":
                out.add("f")
                continue
            raise ValueError(f"{where}: unrecognised contract token {tok!r}")
        try:
            out |= halves(tok)
        except ValueError as exc:
            raise ValueError(f"{where}: {exc}") from None
    return out


def attr(sig: str, keyword: str) -> str | None:
    m = re.search(r"\b" + keyword + r"\s*\(([^)]*)\)", sig)
    return None if m is None else m.group(1)


def _instr(line: str) -> str:
    s = line.strip()
    m = RE_EXPORT_LABEL.match(s)
    if m:
        return s[m.end():].strip()
    return RE_LABEL_PREFIX.sub("", s, count=1).strip() if ":" in s else s


# ---------------------------------------------------------------------------------------
# The Z80 write model: which register halves one instruction writes. Modelled from the
# instruction set (Zilog UM0080), mnemonic by mnemonic; the module doc carries the table.
# ---------------------------------------------------------------------------------------
class Unmodelled(ValueError):
    """A statement the write model cannot read. It FAILS the run: reading it as `writes
    nothing` would be the silent hole this file exists to close."""


R8 = frozenset({"a", "b", "c", "d", "e", "h", "l", "ixh", "ixl", "iyh", "iyl"})
R16 = frozenset({"bc", "de", "hl", "ix", "iy", "sp"})
FLAGS = frozenset({"f"})
ALU8 = frozenset({"add", "adc", "sub", "sbc", "and", "or", "xor"})
ACCUMULATOR_OPS = frozenset({"daa", "cpl", "neg", "rlca", "rla", "rrca", "rra", "rld", "rrd"})
CB_SHIFTS = frozenset({"rlc", "rl", "rrc", "rr", "sla", "sra", "sll", "srl"})
BLOCK_LD = frozenset({"ldi", "ldd", "ldir", "lddr"})
BLOCK_CP = frozenset({"cpi", "cpd", "cpir", "cpdr"})
BLOCK_IO = frozenset({"ini", "ind", "inir", "indr", "outi", "outd", "otir", "otdr"})
WRITES_NOTHING = frozenset({"out", "nop", "halt", "di", "ei", "im", "jp", "jr", "call", "ret",
                            "reti", "retn", "rst"})


def _operands(text: str) -> list[str]:
    """Split an operand list on its top-level commas. Register tokens are lower-cased;
    anything else (an expression, a memory operand) is kept as written."""
    out: list[str] = []
    depth, cur = 0, ""
    for ch in text:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            out.append(cur.strip())
            cur = ""
        else:
            cur += ch
    if cur.strip():
        out.append(cur.strip())
    return [re.sub(r"\s+", "", o.lower()) if re.fullmatch(r"\(?\s*[A-Za-z']+\s*\)?", o) else o
            for o in out]


def _mem(op: str) -> bool:
    return op.startswith("(") and op.endswith(")")


def _reg(op: str) -> set[str] | None:
    """The halves a register operand names, or None when it names no register."""
    return halves(op) if op in R8 or op in R16 or op in ("i", "r") else None


def z80_writes(stmt: str) -> set[str]:
    """The register halves (and `f`) one Z80 instruction writes. Raises Unmodelled for
    a mnemonic or operand shape the model does not know."""
    parts = stmt.split(None, 1)
    mn = parts[0].lower()
    ops = _operands(parts[1]) if len(parts) > 1 else []
    n = len(ops)

    def bad() -> Unmodelled:
        return Unmodelled(f"operand shape not modelled for `{mn}`")

    if mn == "ld":
        if n != 2:
            raise bad()
        dst = _reg(ops[0])
        if dst is not None:
            # `ld a,i` / `ld a,r` copy IFF2 into P/V and set S/Z: the only flag-writing ld.
            return dst | (FLAGS if ops[0] == "a" and ops[1] in ("i", "r") else set())
        if _mem(ops[0]):
            return set()
        raise bad()
    if mn in ("add", "adc", "sbc") and n == 2 and ops[0] in ("hl", "ix", "iy"):
        return halves(ops[0]) | FLAGS                    # 16-bit: the pair, H/N/C (+S/Z/V)
    if mn in ALU8 or mn == "cp":
        if not (n == 1 or (n == 2 and ops[0] == "a")):
            raise bad()
        return set(FLAGS) if mn == "cp" else {"a"} | FLAGS   # cp: flags only
    if mn in ("inc", "dec"):
        if n != 1:
            raise bad()
        if ops[0] in R16:
            return halves(ops[0])                        # 16-bit inc/dec: no flags
        if ops[0] in R8:
            return halves(ops[0]) | FLAGS
        if _mem(ops[0]):
            return set(FLAGS)
        raise bad()
    if mn in ACCUMULATOR_OPS:
        if n:
            raise bad()
        return {"a"} | FLAGS
    if mn in CB_SHIFTS:
        if n == 1 and ops[0] in R8:
            return halves(ops[0]) | FLAGS
        if n == 1 and _mem(ops[0]):
            return set(FLAGS)
        if n == 2 and _mem(ops[0]) and ops[1] in R8:     # undocumented: result copied to r
            return halves(ops[1]) | FLAGS
        raise bad()
    if mn == "bit":
        if n != 2 or not (ops[1] in R8 or _mem(ops[1])):
            raise bad()
        return set(FLAGS)
    if mn in ("set", "res"):                             # flags untouched
        if n == 2 and ops[1] in R8:
            return halves(ops[1])
        if n == 2 and _mem(ops[1]):
            return set()
        if n == 3 and _mem(ops[1]) and ops[2] in R8:     # undocumented: result copied to r
            return halves(ops[2])
        raise bad()
    if mn in ("scf", "ccf"):
        if n:
            raise bad()
        return set(FLAGS)
    if mn == "djnz":
        if n != 1:
            raise bad()
        return {"b"}                                     # b--, flags untouched
    if mn in BLOCK_LD:
        return halves("bc") | halves("de") | halves("hl") | FLAGS
    if mn in BLOCK_CP:
        return halves("bc") | halves("hl") | FLAGS
    if mn in BLOCK_IO:
        return {"b"} | halves("hl") | FLAGS
    if mn == "exx":
        if n:
            raise bad()
        return halves("bc") | halves("de") | halves("hl")
    if mn == "ex":
        if ops == ["de", "hl"]:
            return halves("de") | halves("hl")
        if ops == ["af", "af'"]:
            return halves("af")
        if n == 2 and ops[0] == "(sp)" and ops[1] in ("hl", "ix", "iy"):
            return halves(ops[1])
        raise bad()
    if mn == "in":
        if n == 1 and ops[0] == "(c)":
            return set(FLAGS)                            # undocumented `in (c)`
        if n == 2 and ops[1] == "(c)" and ops[0] == "f":
            return set(FLAGS)
        if n == 2 and ops[1] == "(c)" and ops[0] in R8:
            return halves(ops[0]) | FLAGS
        if n == 2 and ops[0] == "a" and _mem(ops[1]):
            return {"a"}                                 # `in a,(n)`: flags untouched
        raise bad()
    if mn in WRITES_NOTHING:
        return set()
    raise Unmodelled(f"unknown mnemonic `{mn}`")


def writes_in(body: list[tuple[int, str]], noreturn: bool = False
              ) -> tuple[dict[str, int], list[tuple[int, str]]]:
    """(register halves the proc's OWN code writes, each mapped to the first line writing
    it; the statements the model could not read, as (line, text)). Applies the RESTORE POP
    and NORETURN SP rules (module doc)."""
    found: dict[str, int] = {}
    unmodelled: list[tuple[int, str]] = []
    stack: list[str] = []
    cont = 0
    for n, line in body:
        if cont > 0:                          # continuation of a multi-line build statement
            cont += line.count("(") - line.count(")")
            continue
        s = _instr(line)
        if not s or RE_BLOCK_LINE.fullmatch(s) or RE_DATA.match(s):
            continue
        if RE_COMPTIME_STMT.match(s):
            cont = s.count("(") - s.count(")")
            continue
        m = RE_PUSH.match(s)
        if m:
            stack.append(m.group(1).lower())
            continue
        m = RE_POP.match(s)
        if m:
            pair = m.group(1).lower()
            saved = stack.pop() if stack else None
            if saved == pair:
                continue                      # RESTORE: back to its value at the push
            for h in halves(pair):            # move idiom, or nothing above it: a write
                found.setdefault(h, n)
            continue
        try:
            written = z80_writes(s)
        except Unmodelled as exc:
            unmodelled.append((n, f"`{s}`: {exc}"))
            continue
        for h in sorted(written):
            if h == "sp" and noreturn:
                continue                      # NORETURN SP
            found.setdefault(h, n)
    return found, unmodelled


def calls_in(body: list[tuple[int, str]]) -> tuple[list[tuple[int, str]], list[tuple[int, str]]]:
    """(resolved-shape `call` edges as (line, target), unmeasurable sites as (line, text)).
    An `rst` and a `call` whose operand is not a plain symbol are unmeasurable."""
    edges: list[tuple[int, str]] = []
    bad: list[tuple[int, str]] = []
    for n, line in body:
        s = _instr(line)
        if not RE_CALL.match(s):
            continue
        m = RE_CALL_TARGET.match(s)
        if m and not RE_RST.match(s):
            edges.append((n, m.group(1)))
        else:
            bad.append((n, s))
    return edges, bad


def file_cpus(lines: list[str]) -> tuple[set[str], str | None]:
    cpus: set[str] = set()
    invariant = None
    for line in lines:
        m = RE_MODULE_ATTRS.match(line) or RE_SECTION_ATTRS.match(line)
        if not m:
            continue
        c = RE_CPU.search(m.group(1))
        if c:
            cpus.add(c.group(1))
        inv = RE_INVARIANT_PRESERVES.search(m.group(1))
        if inv:
            invariant = inv.group(1)
    return cpus, invariant


def scan_text(text: str, rel: str) -> list[dict]:
    """Every proc in one Z80 source text: signature facts, own writes and call edges. The
    verdict needs the callees' declarations, so it is computed by `check`, over a whole
    population, not here."""
    lines = [_strip(l) for l in text.splitlines()]
    cpus, invariant = file_cpus(lines)
    module_preserves = declared_halves(invariant, f"{rel} module invariant")
    out: list[dict] = []
    i, n = 0, len(lines)
    while i < n:
        m = RE_PROC.match(lines[i])
        if not m:
            i += 1
            continue
        name, start = m.group(1), i + 1
        attrs_above: list[str] = []
        a = i - 1
        while a >= 0 and lines[a].strip().startswith("@"):
            attrs_above.append(lines[a].strip())
            a -= 1
        noreturn = any(RE_NORETURN.match(t) for t in attrs_above)
        sig_parts: list[str] = []
        j = i
        while j < n and "{" not in lines[j]:
            sig_parts.append(lines[j])
            j += 1
        if j >= n:
            raise ValueError(f"{rel}:{start}: proc {name} has no body brace")
        brace = lines[j].index("{")
        sig_parts.append(lines[j][:brace])
        sig = " ".join(sig_parts)

        body: list[tuple[int, str]] = []
        depth, k, seg = 0, j, lines[j][brace:]
        while True:
            depth += seg.count("{") - seg.count("}")
            body.append((k + 1, seg.lstrip("{").rstrip("}") if k == j else seg))
            if depth <= 0:
                break
            k += 1
            if k >= n:
                raise ValueError(f"{rel}:{start}: proc {name} body never closes")
            seg = lines[k]

        where = f"{rel}:{start} {name}"
        clob, pres, outs = attr(sig, "clobbers"), attr(sig, "preserves"), attr(sig, "out")
        has_contract = clob is not None or pres is not None or outs is not None
        declared = (declared_halves(clob, where) | declared_halves(pres, where)
                    | declared_halves(outs, where) | module_preserves)
        edges, unmeasurable = calls_in(body)
        writes, unmodelled = writes_in(body, noreturn)
        fi = RE_FALLS_INTO.search(sig)
        out.append({
            "file": rel, "proc": name, "line": start, "cpus": cpus,
            "has_contract": has_contract, "noreturn": noreturn,
            "leaf": not edges and not unmeasurable,
            "declared": declared,
            # What a CALLER is charged: this proc's declared clobbers plus its outs. None
            # when it declares no clobbers() clause: its write set is then undeclared.
            "effect": (None if clob is None
                       else declared_halves(clob, where) | declared_halves(outs, where)),
            "writes": writes,
            "calls": edges,
            "falls_into": None if fi is None else (start, fi.group(1)),
            "unmeasurable": unmeasurable,
            "unmodelled": unmodelled,
            "under": {}, "errors": [],
            "body": body,
        })
        i = k + 1
    return out


def check(procs: list[dict]) -> list[dict]:
    """Fill each proc's `under` ({half: why}) and `errors` against the population's own
    declarations. Returns `procs`."""
    index: dict[str, dict] = {}
    dupes: set[str] = set()
    for p in procs:
        if p["proc"] in index:
            dupes.add(p["proc"])
        index[p["proc"]] = p
    for p in procs:
        errors: list[str] = [f"proc name {p['proc']!r} is defined more than once, so a call "
                             f"to it is ambiguous"] if p["proc"] in dupes else []
        errors += [f":{ln} `{s}` has no named target to charge" for ln, s in p["unmeasurable"]]
        errors += [f":{ln} statement the write model cannot read: {why}"
                   for ln, why in p["unmodelled"]]
        required: dict[str, str] = {h: f"written at :{ln}" for h, ln in p["writes"].items()}
        edges = [(ln, t, "call") for ln, t in p["calls"]]
        if p["falls_into"] is not None:
            edges.append((p["falls_into"][0], p["falls_into"][1], "falls_into"))
        for ln, target, kind in edges:
            callee = index.get(target.split(".", 1)[0])
            if callee is None:
                errors.append(f":{ln} {kind} {target} resolves to no Z80 proc")
                continue
            if callee["effect"] is None:
                errors.append(f":{ln} {kind} {target}: the callee declares no clobbers(), so "
                              f"its effect is undeclared")
                continue
            for h in sorted(callee["effect"]):
                required.setdefault(h, f"via {kind} {target} at :{ln}")
        p["errors"] = errors
        p["under"] = ({h: why for h, why in required.items() if h not in p["declared"]}
                      if p["has_contract"] else {})
    return procs


def z80_files() -> list[Path]:
    found: list[Path] = []
    for root in ROOTS:
        base = REPO / root
        if not base.is_dir():
            continue
        for p in sorted(base.rglob("*.emp")):
            cpus, _ = file_cpus([_strip(l) for l in p.read_text(errors="replace").splitlines()])
            if "z80" in cpus:
                found.append(p)
    return found


def scan_tree() -> list[dict]:
    procs: list[dict] = []
    for p in z80_files():
        procs.extend(scan_text(p.read_text(errors="replace"), p.relative_to(REPO).as_posix()))
    return check(procs)


def _fmt(regs) -> str:
    return ",".join(sorted(regs))


# ---------------------------------------------------------------------------------------
# The checks.
# ---------------------------------------------------------------------------------------


def test_the_scan_reaches_the_z80_tree():
    """Positive control for REACH: an empty population would make every check below pass
    vacuously, and a directory sweep keyed on a `cpu:` spelling fails exactly that way. The
    edge floors do the same for the call model: a parser that stopped matching `call`
    would turn every caller into a leaf and drop every callee effect."""
    files = [p.relative_to(REPO).as_posix() for p in z80_files()]
    procs = scan_tree()
    leaves = [p for p in procs if p["leaf"]]
    callers = [p for p in procs if not p["leaf"]]
    n_calls = sum(len(p["calls"]) for p in procs)
    n_falls = sum(1 for p in procs if p["falls_into"] is not None)
    n_flag = sum(1 for p in procs if "f" in p["writes"])
    print(f"Z80 files: {len(files)}; procs: {len(procs)} ({len(leaves)} leaves, "
          f"{len(callers)} with a call, all checked); call edges: {n_calls}; "
          f"falls_into edges: {n_falls}; procs writing f: {n_flag}; own-write facts: "
          f"{sum(len(p['writes']) for p in procs)}")
    assert SEQ in files, (
        f"the Z80 sweep of {ROOTS} did not reach {SEQ}, the sequencer and home of the opcode "
        f"handlers. It found {len(files)} file(s): {files}. The `cpu: z80` match is broken."
    )
    assert len(files) >= MIN_Z80_FILES, f"only {len(files)} Z80 file(s), floor {MIN_Z80_FILES}"
    assert len(procs) >= MIN_Z80_PROCS, f"only {len(procs)} Z80 proc(s), floor {MIN_Z80_PROCS}"
    assert len(leaves) >= MIN_LEAF_PROCS, f"only {len(leaves)} leaf proc(s), floor {MIN_LEAF_PROCS}"
    assert len(callers) >= MIN_CALL_PROCS, (
        f"only {len(callers)} proc(s) with a call, floor {MIN_CALL_PROCS}")
    assert n_calls >= MIN_CALL_EDGES, f"only {n_calls} call edge(s), floor {MIN_CALL_EDGES}"
    assert n_falls >= MIN_FALLS_INTO_EDGES, (
        f"only {n_falls} falls_into edge(s), floor {MIN_FALLS_INTO_EDGES}")
    assert n_flag >= MIN_FLAG_WRITERS, (
        f"only {n_flag} proc(s) write f, floor {MIN_FLAG_WRITERS}: the write model has stopped "
        f"reading the implicit writers (cp, bit, the ALU, the rotates)")


def test_no_file_mixes_z80_procs_with_68k_sections():
    """Classification is per FILE. A file that declares both CPUs would put 68000 procs
    through the Z80 scan (or the reverse); refuse it loudly rather than mis-read it."""
    mixed = []
    for p in z80_files():
        cpus, _ = file_cpus([_strip(l) for l in p.read_text(errors="replace").splitlines()])
        if cpus - {"z80"}:
            mixed.append(f"{p.relative_to(REPO).as_posix()} {sorted(cpus)}")
    assert not mixed, f"file(s) declaring Z80 AND another cpu: {mixed}. Split the scan per section."


def test_attribute_less_z80_procs_are_the_known_set():
    found = {(p["file"], p["proc"]) for p in scan_tree() if not p["has_contract"]}
    print(f"Z80 procs with NO contract attribute: {sorted(found)}")
    assert found == KNOWN_ATTRIBUTE_LESS, (
        "the set of Z80 procs declaring no clobbers()/preserves()/out() changed.\n"
        f"  new (declare a contract, or argue the omission in source and add it here): "
        f"{sorted(found - KNOWN_ATTRIBUTE_LESS)}\n"
        f"  gone (delete the row): {sorted(KNOWN_ATTRIBUTE_LESS - found)}"
    )


def test_every_z80_call_edge_is_measurable():
    """An edge the census cannot charge is a FAILURE, not a skip: a skipped callee is a
    callee whose effect nobody checks, which is the hole this file used to be."""
    problems = [f"{p['file']}:{p['line']} {p['proc']} {e}" for p in scan_tree()
                for e in p["errors"]]
    assert not problems, (
        "Z80 clobbers census: call edge(s) it cannot measure:\n  " + "\n  ".join(problems)
        + "\nName a Z80 proc that declares clobbers(), or teach this file the new form with "
          "its own fixture control. Do not skip it."
    )


def test_no_z80_proc_under_declares_its_clobbers():
    """Zero-firing: no allow-list. Every problem line names the proc, each register half it
    leaves undeclared and why it is required (its own first write, or the callee that
    declares it), and what the proc does declare."""
    procs = scan_tree()
    under = [p for p in procs if p["under"]]
    print(f"Z80 procs under-declaring: {len(under)} of {sum(1 for p in procs if p['has_contract'])} "
          f"checked ({sum(1 for p in procs if not p['leaf'])} of them with a call)")
    problems = []
    for p in under:
        detail = ", ".join(f"{r} ({why})" for r, why in sorted(p["under"].items()))
        problems.append(f"{p['file']}:{p['line']} {p['proc']} leaves undeclared {detail}; "
                        f"declared {_fmt(p['declared']) or 'nothing'}")
    assert not problems, (
        "Z80 clobbers() under-declaration census (CTRL-1 / LS-2a):\n  "
        + "\n  ".join(problems)
        + "\nA Z80 proc must declare every register it writes, and every register its callees "
          "declare, in clobbers(), preserves() or out(). Fix the ATTRIBUTE: this census "
          "carries no allow-list."
    )


FIXTURE = (
    "module fake.z80 (cpu: z80)\n"
    "section fake (cpu: z80) {\n"
    "    pub proc Leaf_Under () clobbers(af) {\n"
    "        // ld b, a and inc hl in a comment\n"
    '        ensure(1 == 1, "ld c, a")\n'
    "        ld      (hl), a\n"
    "        ld      (ix+3), b\n"
    "    .label: ld      b, (hl)\n"
    "        ret\n"
    "    }\n"
    "    pub proc Leaf_Ok () clobbers(a, f, hl) preserves(de) out(carry: found) {\n"
    "        push    de\n"
    "        ex      de, hl\n"
    "        inc     hl\n"
    "        pop     de\n"
    "        ret\n"
    "    }\n"
    "    pub proc Handler_Under () clobbers(af) {\n"
    "        ld      a, (hl)\n"
    "        inc     hl\n"
    "        ld      (ix+5), a\n"
    "        jp      Loop.fetch\n"
    "    }\n"
    "    pub proc Handler_Ok () clobbers(af, hl) {\n"
    "        ld      a, (hl)\n"
    "        inc     hl\n"
    "        ld      (ix+5), a\n"
    "        jp      Loop.fetch\n"
    "    }\n"
    "    pub proc Caller () clobbers() {\n"
    "        ld      b, 1\n"
    "        call    Leaf_Ok\n"
    "        ret\n"
    "    }\n"
    "    pub proc Trace () clobbers(af) preserves(bc, de, hl) {\n"
    "        push    hl\n"
    "        push    bc\n"
    "        ld      hl, 0\n"
    "        pop     bc\n"
    "        pop     hl\n"
    "        ret\n"
    "    }\n"
    "    pub proc Hook () clobbers(af, bc, de, hl) preserves(ix) {\n"
    "    export .entry:\n"
    "        ld      bc, 0\n"
    "        ld      de, 0\n"
    "        ld      hl, 0\n"
    "        ret\n"
    "    }\n"
    "    pub proc Bracket_Ok () clobbers(af, b) {\n"
    "        ld      a, (hl)\n"
    "        ld      b, a\n"
    "        if DEBUG == 1 {\n"
    "            push    hl\n"
    "            push    bc\n"
    "            call    Trace\n"
    "            pop     bc\n"
    "            pop     hl\n"
    "        }\n"
    "        jp      Loop.fetch\n"
    "    }\n"
    "    pub proc Move_Under () clobbers(af) {\n"
    "        push    ix\n"
    "        pop     de\n"
    "        ret\n"
    "    }\n"
    "    pub proc Hook_Under () clobbers(af, hl) {\n"
    "        ld      a, (hl)\n"
    "        inc     hl\n"
    "        push    hl\n"
    "        call    nz, Hook\n"
    "        pop     hl\n"
    "        jp      Loop.fetch\n"
    "    }\n"
    "    pub proc Hook_Ok () clobbers(af, bc, de, hl) {\n"
    "        ld      a, (hl)\n"
    "        inc     hl\n"
    "        push    hl\n"
    "        call    Hook.entry\n"
    "        pop     hl\n"
    "        jp      Loop.fetch\n"
    "    }\n"
    "    pub proc Falls_Under () clobbers(af) falls_into Hook {\n"
    "        ld      a, 1\n"
    "    }\n"
    "    @noreturn\n"
    "    pub proc Entry_NoReturn () clobbers(af) {\n"
    "        ld      sp, $1FFE\n"
    "        ld      a, 0\n"
    "    .spin:\n"
    "        jr      .spin\n"
    "    }\n"
    "    pub proc Returning_Sp () clobbers(af) {\n"
    "        ld      sp, $1FFE\n"
    "        ret\n"
    "    }\n"
    "}\n"
)

FIXTURE_UNMEASURABLE = (
    "module fake2.z80 (cpu: z80)\n"
    "section fake2 (cpu: z80) {\n"
    "    pub proc NoClobbers () preserves(bc) {\n"
    "        ret\n"
    "    }\n"
    "    pub proc CallsNowhere () clobbers(af) {\n"
    "        call    Nowhere\n"
    "        ret\n"
    "    }\n"
    "    pub proc CallsUndeclared () clobbers(af) {\n"
    "        call    NoClobbers\n"
    "        ret\n"
    "    }\n"
    "    pub proc Restarts () clobbers(af) {\n"
    "        rst     $38\n"
    "        ret\n"
    "    }\n"
    "}\n"
)


def test_scanner_controls():
    """The controls this file owes, on fixtures. Own writes: a written-but-undeclared
    register fires; prose, strings and memory destinations do not; pair and half spellings
    compare correctly. Calls: a callee's declared clobbers and outs are charged to the
    caller, its preserves are not, a push/pop bracket around the call earns nothing, and the
    conditional, `X.label` and `falls_into` forms all resolve. The two rules: a restore pop
    writes nothing (the DEBUG save pair around a trace call, the shape the booking named
    as a false hit), a move-idiom pop writes, and `sp` is exempt only in an `@noreturn`
    proc. Unmeasurable edges refuse; an unknown attribute token refuses."""
    procs = {p["proc"]: p for p in check(scan_text(FIXTURE, "fake.emp"))}
    assert set(procs) == {
        "Leaf_Under", "Leaf_Ok", "Handler_Under", "Handler_Ok", "Caller", "Trace", "Hook",
        "Bracket_Ok", "Move_Under", "Hook_Under", "Hook_Ok", "Falls_Under", "Entry_NoReturn",
        "Returning_Sp"}, sorted(procs)
    assert not any(p["errors"] for p in procs.values()), (
        {k: p["errors"] for k, p in procs.items() if p["errors"]})
    # --- own writes (unchanged from the leaf census) ---
    assert set(procs["Handler_Under"]["under"]) == {"h", "l"}, (
        "the opcode-handler shape (`inc hl` advancing the stream, a tail `jp` into the loop) "
        f"must fire h,l when hl is undeclared. Got {procs['Handler_Under']['under']}"
    )
    assert procs["Handler_Ok"]["leaf"] and procs["Handler_Ok"]["under"] == {}, (
        f"`clobbers(af, hl)` must cover the handler shape: {procs['Handler_Ok']['under']}"
    )
    assert set(procs["Leaf_Under"]["under"]) == {"b"}, (
        "the label-prefixed `ld b, (hl)` must be the ONE undeclared write; prose, the string "
        f"literal and the memory destinations must not count. Got {procs['Leaf_Under']['under']}"
    )
    assert procs["Leaf_Ok"]["under"] == {}, (
        f"pair/half/preserves/out(carry) spellings mis-compared: {procs['Leaf_Ok']['under']}"
    )
    # --- calls ---
    caller = procs["Caller"]
    assert not caller["leaf"] and set(caller["under"]) == {"a", "b", "f", "h", "l"}, (
        "a proc with a `call` is CHECKED: its own `ld b` plus Leaf_Ok's declared "
        f"clobbers(a, f, hl) and out(carry) must fire, and Leaf_Ok's preserves(de) must NOT "
        f"be charged. Got {caller['under']}"
    )
    assert caller["under"]["b"].startswith("written at") and \
        caller["under"]["h"] == "via call Leaf_Ok at :32", caller["under"]
    assert set(procs["Hook_Under"]["under"]) == {"b", "c", "d", "e"}, (
        "`call nz, Hook` must resolve, and the push/pop hl around it must earn no credit for "
        f"Hook's bc/de (the Seq_Op_NoteDur shape). Got {procs['Hook_Under']['under']}"
    )
    assert procs["Hook_Ok"]["under"] == {}, (
        f"`call Hook.entry` resolves to Hook, covered by the full set: {procs['Hook_Ok']['under']}"
    )
    assert set(procs["Falls_Under"]["under"]) == {"b", "c", "d", "e", "h", "l"} and \
        procs["Falls_Under"]["under"]["b"].startswith("via falls_into Hook"), (
        f"a `falls_into` target's declared effect must be charged: {procs['Falls_Under']['under']}"
    )
    # --- the two rules ---
    assert procs["Bracket_Ok"]["under"] == {} and procs["Trace"]["under"] == {}, (
        "RESTORE POP: the DEBUG save pair (push hl / push bc / call / pop bc / pop hl) must "
        f"write nothing. Got {procs['Bracket_Ok']['under']} / {procs['Trace']['under']}"
    )
    assert set(procs["Move_Under"]["under"]) == {"d", "e"}, (
        f"the move idiom (push ix / pop de) WRITES de: {procs['Move_Under']['under']}"
    )
    assert procs["Entry_NoReturn"]["noreturn"] and procs["Entry_NoReturn"]["under"] == {}, (
        f"NORETURN SP: an @noreturn entry's `ld sp` is not a clobber: "
        f"{procs['Entry_NoReturn']['under']}"
    )
    assert not procs["Returning_Sp"]["noreturn"] and \
        set(procs["Returning_Sp"]["under"]) == {"sp"}, (
        f"an `sp` write in a RETURNING proc must fire: {procs['Returning_Sp']['under']}"
    )
    # --- unmeasurable edges refuse ---
    bad = {p["proc"]: p["errors"] for p in check(scan_text(FIXTURE_UNMEASURABLE, "fake2.emp"))}
    assert any("resolves to no Z80 proc" in e for e in bad["CallsNowhere"]), bad
    assert any("declares no clobbers()" in e for e in bad["CallsUndeclared"]), bad
    assert any("rst" in e for e in bad["Restarts"]), bad
    assert bad["NoClobbers"] == [], bad
    try:
        declared_halves("af, carry_flag", "fixture")
    except ValueError:
        pass
    else:
        raise AssertionError("an unrecognised contract token was accepted instead of refused")


# One fixture control per implicit-writer form (LS-2a item (b)): the statement, and the
# EXACT set it writes per the Z80 instruction set. Each row becomes two fixture procs: an
# under-declaring `clobbers()` twin the census must name with exactly this set, and an
# honest twin declaring exactly this set that must pass. Exact equality is the point: it
# pins what a form does NOT write as hard as what it does (cpi never writes a or de, djnz
# and the 16-bit inc never write f, set/res never write f, `in a,(n)` never writes f).
# A row whose set is empty is a write-nothing form: its one proc must pass `clobbers()`.
FORM_CASES: tuple[tuple[str, str], ...] = (
    # 8-bit ALU into the accumulator, and the flag-only compare
    ("add a, b", "a, f"), ("adc a, 1", "a, f"), ("sub 3", "a, f"), ("sbc a, a", "a, f"),
    ("and 7", "a, f"), ("or a", "a, f"), ("xor (hl)", "a, f"),
    ("cp 3", "f"), ("cp (ix+2)", "f"),
    # 16-bit arithmetic: the pair AND the flags (the explicit parser counted only the pair)
    ("add hl, bc", "hl, f"), ("adc hl, de", "hl, f"), ("sbc hl, de", "hl, f"),
    ("add ix, bc", "ix, f"), ("add iy, de", "iy, f"),
    # inc/dec: 8-bit register and memory forms write flags, the 16-bit forms do not
    ("inc b", "b, f"), ("dec a", "a, f"), ("inc ixh", "ixh, f"),
    ("inc (hl)", "f"), ("dec (ix+1)", "f"), ("inc hl", "hl"), ("dec de", "de"), ("inc ix", "ix"),
    # accumulator-only operations
    ("daa", "a, f"), ("cpl", "a, f"), ("neg", "a, f"),
    ("rlca", "a, f"), ("rla", "a, f"), ("rrca", "a, f"), ("rra", "a, f"),
    ("rld", "a, f"), ("rrd", "a, f"),
    # CB shifts and rotates: register, memory, and the undocumented copy-to-register form
    ("rlc c", "c, f"), ("rl d", "d, f"), ("rrc e", "e, f"), ("rr l", "l, f"),
    ("sla h", "h, f"), ("sra b", "b, f"), ("sll a", "a, f"), ("srl a", "a, f"),
    ("rl (hl)", "f"), ("srl (ix+3)", "f"), ("rlc (ix+3), b", "b, f"),
    # bit tests and bit writes
    ("bit 7, h", "f"), ("bit 0, (ix+1)", "f"),
    ("set 3, b", "b"), ("res 0, a", "a"), ("set 1, (hl)", ""), ("res 2, (ix+4)", ""),
    ("set 1, (ix+4), c", "c"),
    ("scf", "f"), ("ccf", "f"),
    ("djnz .x", "b"),
    # block operations
    ("ldi", "bc, de, hl, f"), ("ldir", "bc, de, hl, f"),
    ("ldd", "bc, de, hl, f"), ("lddr", "bc, de, hl, f"),
    ("cpi", "bc, hl, f"), ("cpir", "bc, hl, f"), ("cpd", "bc, hl, f"), ("cpdr", "bc, hl, f"),
    ("ini", "b, hl, f"), ("inir", "b, hl, f"), ("ind", "b, hl, f"), ("indr", "b, hl, f"),
    ("outi", "b, hl, f"), ("otir", "b, hl, f"), ("outd", "b, hl, f"), ("otdr", "b, hl, f"),
    # exchanges
    ("exx", "bc, de, hl"), ("ex af, af'", "af"), ("ex de, hl", "de, hl"),
    ("ex (sp), hl", "hl"), ("ex (sp), ix", "ix"), ("ex (sp), iy", "iy"),
    # port input
    ("in a, (c)", "a, f"), ("in b, (c)", "b, f"), ("in a, ($10)", "a"),
    ("in (c)", "f"), ("in f, (c)", "f"),
    # loads, including the two flag-writing forms
    ("ld a, i", "a, f"), ("ld a, r", "a, f"), ("ld i, a", "i"), ("ld r, a", "r"),
    ("ld b, (hl)", "b"), ("ld hl, ($1234)", "hl"), ("ld ix, 0", "ix"), ("ld ixl, a", "ixl"),
    ("ld (hl), b", ""), ("ld (ix+2), 5", ""), ("ld ($1234), hl", ""),
    # write-nothing forms
    ("out (c), a", ""), ("out ($10), a", ""), ("nop", ""), ("halt", ""), ("di", ""),
    ("ei", ""), ("im 1", ""), ("push bc", ""), ("ret nz", ""), ("reti", ""), ("retn", ""),
    ("jr .x", ""), ("jp c, .x", ""),
)


def _form_fixture() -> str:
    lines = ["module forms.z80 (cpu: z80)", "section forms (cpu: z80) {"]
    for i, (stmt, want) in enumerate(FORM_CASES):
        twins = [(f"Form{i}_Under", "")] + ([(f"Form{i}_Ok", want)] if want else [])
        for name, decl in twins:
            lines += [f"    pub proc {name} () clobbers({decl}) {{", "    .x:",
                      f"        {stmt}", "        ret", "    }"]
    lines.append("}")
    return "\n".join(lines) + "\n"


FIXTURE_STATEMENTS = (
    "module fake3.z80 (cpu: z80)\n"
    "section fake3 (cpu: z80) {\n"
    "    pub proc Statements_Ok () clobbers() {\n"
    "        ensure(cycles(.a, .b) >= 1,\n"
    '            "ld b, a")\n'
    "        pad_to_cycles(4, cycles(.a, .b),\n"
    "            dense: true)\n"
    "        dc.b    1, 2\n"
    "        dc.w    Statements_Ok\n"
    "        if DEBUG == 1 {\n"
    "            nop\n"
    "        } else {\n"
    "            nop\n"
    "        }\n"
    "    export .a:\n"
    "    .b: nop\n"
    "        ret\n"
    "    }\n"
    "    pub proc Unknown_Mnemonic () clobbers(af) {\n"
    "        frob    a\n"
    "        ret\n"
    "    }\n"
    "    pub proc Template_Call () clobbers(af) {\n"
    "        ym_write(SND_REG_KEY, 0)\n"
    "        ret\n"
    "    }\n"
    "    pub proc Brace_Line () clobbers(af) {\n"
    "        if DEBUG == 1 { ld b, 1 }\n"
    "        ret\n"
    "    }\n"
    "    pub proc Bad_Operand () clobbers(af) {\n"
    "        ld      Foo_Bar, a\n"
    "        ret\n"
    "    }\n"
    "    pub proc Bad_Alu () clobbers(af) {\n"
    "        add     b, c\n"
    "        ret\n"
    "    }\n"
    "}\n"
)


def test_write_model_controls():
    """The implicit writers, one fixture control per form (FORM_CASES), and the refusal of
    every statement the model cannot read."""
    procs = {p["proc"]: p for p in check(scan_text(_form_fixture(), "forms.emp"))}
    wrong = []
    for i, (stmt, want) in enumerate(FORM_CASES):
        want_set = declared_halves(want, stmt)
        under, ok = procs[f"Form{i}_Under"], procs.get(f"Form{i}_Ok")
        if under["errors"] or set(under["under"]) != want_set:
            wrong.append(f"`{stmt}`: named {_fmt(under['under']) or 'nothing'} under "
                         f"clobbers(), want exactly {_fmt(want_set) or 'nothing'} "
                         f"{under['errors'] or ''}")
        if ok is not None and (ok["errors"] or ok["under"]):
            wrong.append(f"`{stmt}`: the honest twin clobbers({want}) was named "
                         f"{_fmt(ok['under'])} {ok['errors'] or ''}")
    assert not wrong, "Z80 write model disagrees with the instruction set:\n  " + "\n  ".join(wrong)

    st = {p["proc"]: p for p in check(scan_text(FIXTURE_STATEMENTS, "fake3.emp"))}
    assert st["Statements_Ok"]["errors"] == [] and st["Statements_Ok"]["under"] == {}, (
        "labels, brace lines, data, and multi-line ensure/pad_to_cycles are not instructions "
        f"(the string literal's `ld b, a` included): {st['Statements_Ok']['errors']} "
        f"{st['Statements_Ok']['under']}")
    for name in ("Unknown_Mnemonic", "Template_Call", "Brace_Line", "Bad_Operand", "Bad_Alu"):
        errs = st[name]["errors"]
        assert len(errs) == 1 and "cannot read" in errs[0], (
            f"{name}: an unreadable statement must FAIL the run, not read as `writes "
            f"nothing`. Got {errs}")


if __name__ == "__main__":
    test_the_scan_reaches_the_z80_tree()
    test_no_file_mixes_z80_procs_with_68k_sections()
    test_attribute_less_z80_procs_are_the_known_set()
    test_every_z80_call_edge_is_measurable()
    test_no_z80_proc_under_declares_its_clobbers()
    test_scanner_controls()
    test_write_model_controls()
    print("OK")
