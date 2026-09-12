#!/usr/bin/env python3
"""
Z80 clobbers() UNDER-declaration census (CTRL-1 / docs/DEFERRED_WORK.md LS-2a).

WHY THIS FILE EXISTS. `CODING_CONVENTIONS.md` §2.8 carries a four-cell table of what the
build verifies about register contracts. Exactly one cell is guarded: 68000
under-declaration, by sigil's `[proc.clobber-undeclared]` closure gate. The Z80 row is
UNCHECKED in both directions, and the LS-2 control proved it: `Seq_Op_NoteFill`'s
`ld a,(hl)` swapped for the same-size `ld b,(hl)` wrote an undeclared `b` and built green
with the warning summary unchanged. Under-declaration is the correctness class (a caller
trusting the contract keeps a value in a register the callee destroys), so it is the Z80
cell this file guards. Over-declaration is NOT checked here, on either CPU, on purpose:
LS-2's closure left it unguarded with written reasons (it is used deliberately, and a wider
declaration only makes callers save more, never less).

WHAT IT CHECKS. For every `proc` in a Z80 module under engine/ and games/ (a module or
section declared `cpu: z80`) that contains no `call` and no `rst` (a LEAF), the registers
its body writes must each be declared by the proc's `clobbers(...)`, `preserves(...)` or
`out(...)`, or by its module's `invariant: preserves(...)`. Writes are recognised from
CODE only, in these explicit forms (comments and string literals are stripped first):

    ld   R, ...        R a register (a..l, i, r, sp, bc/de/hl, ix/iy, their halves)
    inc R / dec R      R a register, not a memory operand
    pop  RR
    ex   de, hl        writes both
    add/adc/sbc HL|IX|IY, ...

Pairs are compared by HALF (`hl` is `h` + `l`), because declarations in this tree mix both
spellings (`clobbers(af, b, hl)`, `clobbers(a, b, de, f)`); `out(carry: …)` declares `f`.
An attribute token this file does not recognise FAILS the run rather than being skipped.

NO ALLOW-LIST. The census is zero-firing: any Z80 leaf that writes a register it does not
declare fails the build, and the fix is the ATTRIBUTE. The sequencer's opcode handlers that
advance the stream pointer spell that effect `clobbers(..., hl)` (Seq_Op_Macro,
Seq_Op_RegDelta and every leaf handler): `hl` leaves the handler advanced past its operands
and Sequencer_NextOpcode.fetch consumes it. `out()` is not the spelling for it: in this
driver `out()` names a value returned to a `call` site, and no `Seq_Op_*` handler is called.
Records: docs/superpowers/notes/2026-09-11-lens-z3-parcel.md (the allow-list this file
carried) and docs/superpowers/notes/2026-09-12-ctrl1-seqop-clobbers.md (its removal).

WHAT IT DOES NOT COVER, each a real hole:
  * PROCS WITH A `call` OR `rst`. Their callees' effects are not modelled, so they are
    skipped whole, including their own direct writes. The skipped count is derived and
    printed on every run. A DEBUG-only `call` (inside `if DEBUG == 1 { }`) skips the proc
    in every shape, because this file reads source, not a shape. That population holds
    live under-declarations of this exact class (a direct `inc hl` or `ld e, a` the
    proc's own attribute omits); docs/DEFERRED_WORK.md LS-2a enumerates them.
  * TAIL JUMPS. A `jp`/`jr` into another proc hands the caller that proc's writes too;
    nothing here follows a jump. (Seq_Op_Ext is entered by a `jp z` from
    Sequencer_NextOpcode, whose own declaration already covers `hl`.)
  * IMPLICIT WRITERS. ALU results into `a` (add/sub/and/or/xor/neg/cpl/daa and the
    accumulator rotates), flag-only writes (cp, bit, scf/ccf), `djnz` (b), the block ops
    (ldi/ldir/ldd/lddr/cpi/cpir: bc/de/hl), `exx`, `ex af,af'`, `ex (sp),hl`, `in r,(c)`,
    and shifts, rotates or set/res on a register. Not widened yet: each new form owes its
    own fixture control. The lens-z3 note measured a wider parser adding ZERO hits over
    the leaves, so widening costs no allow-list; docs/DEFERRED_WORK.md LS-2a books it.
  * TEMPLATES. A comptime fn or `asm {}` template expanded inside a proc body writes
    registers no text scan can see.
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

# FLOORS on the population, derived at e4b4f38f (172 Z80 procs, 97 of them leaves, in 11
# files). A floor catches the sweep going blind (a moved root, a changed `cpu:` spelling);
# it is not a census, and deleting procs legitimately means lowering it.
MIN_Z80_FILES = 11
MIN_Z80_PROCS = 172
MIN_LEAF_PROCS = 97

# ---------------------------------------------------------------------------------------
# The scanner.
# ---------------------------------------------------------------------------------------
RE_MODULE_ATTRS = re.compile(r"^\s*module\s+[\w.]+\s*\((.*)\)\s*$")
RE_SECTION_ATTRS = re.compile(r"^\s*section\s+\w+\s*\(([^)]*)\)")
RE_CPU = re.compile(r"\bcpu\s*:\s*(\w+)")
RE_INVARIANT_PRESERVES = re.compile(r"\binvariant\s*:\s*preserves\s*\(([^)]*)\)")
RE_PROC = re.compile(r"^\s*(?:pub\s+)?proc\s+(\w+)")
RE_LABEL_PREFIX = re.compile(r"^\s*\.?\w+\s*:(?!\s*=)\s*")

_REG = r"(ixh|ixl|iyh|iyl|ix|iy|af|bc|de|hl|sp|a|b|c|d|e|h|l|i|r)"
RE_LD = re.compile(r"^ld\s+" + _REG + r"\s*,", re.I)
RE_INCDEC = re.compile(r"^(?:inc|dec)\s+" + _REG + r"\s*$", re.I)
RE_POP = re.compile(r"^pop\s+(af|bc|de|hl|ix|iy)\s*$", re.I)
RE_EX_DE_HL = re.compile(r"^ex\s+de\s*,\s*hl\s*$", re.I)
RE_ADD16 = re.compile(r"^(?:add|adc|sbc)\s+(hl|ix|iy)\s*,", re.I)
RE_CALL = re.compile(r"^(?:call|rst)\b", re.I)

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


def writes_in(body: list[tuple[int, str]]) -> dict[str, int]:
    """Register halves written by the explicit forms, each mapped to its first line."""
    found: dict[str, int] = {}
    for n, line in body:
        s = RE_LABEL_PREFIX.sub("", line, count=1).strip() if ":" in line else line.strip()
        regs: list[str] = []
        for rx in (RE_LD, RE_INCDEC, RE_POP, RE_ADD16):
            m = rx.match(s)
            if m:
                regs.append(m.group(1))
        if RE_EX_DE_HL.match(s):
            regs += ["de", "hl"]
        for r in regs:
            for h in halves(r):
                found.setdefault(h, n)
    return found


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
    """Every proc in one Z80 source text, with its signature, body and census verdict."""
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
        is_leaf = not any(RE_CALL.match(l.strip()) for _, l in body)
        w = writes_in(body) if is_leaf else {}
        out.append({
            "file": rel, "proc": name, "line": start, "cpus": cpus,
            "has_contract": has_contract, "leaf": is_leaf,
            "declared": declared, "writes": w,
            "under": {r: ln for r, ln in w.items() if r not in declared} if has_contract else {},
            "body": body,
        })
        i = k + 1
    return out


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
    return procs


def _fmt(regs) -> str:
    return ",".join(sorted(regs))


# ---------------------------------------------------------------------------------------
# The checks.
# ---------------------------------------------------------------------------------------


def test_the_scan_reaches_the_z80_tree():
    """Positive control for REACH: an empty population would make every check below pass
    vacuously, and a directory sweep keyed on a `cpu:` spelling fails exactly that way."""
    files = [p.relative_to(REPO).as_posix() for p in z80_files()]
    procs = scan_tree()
    leaves = [p for p in procs if p["leaf"]]
    print(f"Z80 files: {len(files)}; procs: {len(procs)}; leaves checked: {len(leaves)}; "
          f"skipped for a call/rst: {len(procs) - len(leaves)}")
    assert SEQ in files, (
        f"the Z80 sweep of {ROOTS} did not reach {SEQ}, the sequencer and home of the opcode "
        f"handlers. It found {len(files)} file(s): {files}. The `cpu: z80` match is broken."
    )
    assert len(files) >= MIN_Z80_FILES, f"only {len(files)} Z80 file(s), floor {MIN_Z80_FILES}"
    assert len(procs) >= MIN_Z80_PROCS, f"only {len(procs)} Z80 proc(s), floor {MIN_Z80_PROCS}"
    assert len(leaves) >= MIN_LEAF_PROCS, f"only {len(leaves)} leaf proc(s), floor {MIN_LEAF_PROCS}"


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


def test_no_z80_leaf_under_declares_its_clobbers():
    """Zero-firing: no allow-list. Every problem line names the proc, the register halves
    it writes undeclared with the first line writing each, and what it does declare."""
    procs = scan_tree()
    under = [p for p in procs if p["under"]]
    print(f"Z80 leaves under-declaring: {len(under)} of {sum(1 for p in procs if p['leaf'])} "
          f"checked")
    problems = []
    for p in under:
        detail = ", ".join(f"{r} (first written at :{ln})" for r, ln in sorted(p["under"].items()))
        problems.append(f"{p['file']}:{p['line']} {p['proc']} writes {detail}, declared "
                        f"{_fmt(p['declared']) or 'nothing'}")
    assert not problems, (
        "Z80 clobbers() under-declaration census (CTRL-1 / LS-2a):\n  "
        + "\n  ".join(problems)
        + "\nA Z80 proc must declare every register it writes in clobbers(), preserves() or "
          "out(). Fix the ATTRIBUTE: this census carries no allow-list."
    )


def test_scanner_controls():
    """The controls this file owes, on fixtures: a written-but-undeclared register fires;
    prose, strings and memory destinations do not; a proc with a call is skipped; pair and
    half spellings compare correctly; an unknown attribute token refuses."""
    src = (
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
        "}\n"
    )
    procs = {p["proc"]: p for p in scan_text(src, "fake.emp")}
    assert set(procs) == {"Leaf_Under", "Leaf_Ok", "Handler_Under", "Handler_Ok", "Caller"}, (
        sorted(procs))
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
    assert not procs["Caller"]["leaf"] and procs["Caller"]["under"] == {}, (
        "a proc containing `call` must be skipped whole"
    )
    try:
        declared_halves("af, carry_flag", "fixture")
    except ValueError:
        pass
    else:
        raise AssertionError("an unrecognised contract token was accepted instead of refused")


if __name__ == "__main__":
    test_the_scan_reaches_the_z80_tree()
    test_no_file_mixes_z80_procs_with_68k_sections()
    test_attribute_less_z80_procs_are_the_known_set()
    test_no_z80_leaf_under_declares_its_clobbers()
    test_scanner_controls()
    print("OK")
