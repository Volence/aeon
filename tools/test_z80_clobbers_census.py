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

THE ALLOW-LIST, and why it is not a fix. The census finds the seven `Seq_Op_*` opcode
handlers LS-2a counted, each writing `hl` via `inc hl` while declaring only
`clobbers(af…)`. They are carried in KNOWN_UNDER_DECLARED below, derived by this file's own
scanner, and printed on every run. It is a RATCHET in both directions: a new
under-declaration fails, an allow-listed proc that grows a SECOND undeclared register fails,
and a row that stops firing fails too (so correcting an attribute must delete its row). The
list's safety premise is also checked, not remembered: no `call` instruction names any
allow-listed proc (test_allow_listed_procs_have_no_call_site). Correcting the attributes
instead is the better end state and moves zero bytes by LS-2's measurement; it was not done
in the parcel that wrote this file because engine/sound/ was owned by another parcel that
day. See docs/superpowers/notes/2026-09-11-lens-z3-parcel.md.

WHAT IT DOES NOT COVER, each a real hole:
  * PROCS WITH A `call` OR `rst`. Their callees' effects are not modelled, so they are
    skipped whole, including their own direct writes. The skipped count is derived and
    printed on every run. A DEBUG-only `call` (inside `if DEBUG == 1 { }`) skips the proc
    in every shape, because this file reads source, not a shape.
  * TAIL JUMPS. A `jp`/`jr` into another proc hands the caller that proc's writes too;
    nothing here follows a jump. (Seq_Op_Ext is entered by a `jp z` from
    Sequencer_NextOpcode, whose own declaration already covers `hl`.)
  * IMPLICIT WRITERS. ALU results into `a` (add/sub/and/or/xor/neg/cpl/daa and the
    accumulator rotates), flag-only writes (cp, bit, scf/ccf), `djnz` (b), the block ops
    (ldi/ldir/ldd/lddr/cpi/cpir: bc/de/hl), `exx`, `ex af,af'`, `ex (sp),hl`, `in r,(c)`,
    and shifts, rotates or set/res on a register. Widening to these is deliberately NOT
    done while the allow-list is non-empty: a wider parser would enlarge the list rather
    than the protection, and the seven have to be resolved first.
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

# ---------------------------------------------------------------------------------------
# The allow-list. DERIVED 2026-09-11 by this file's scanner at aeon e4b4f38f, and equal
# to LS-2a's hand count (7 procs, all `hl`). Each value is the exact set of undeclared
# register HALVES the proc writes. The list is printed on every run.
#
# Why each is safe TODAY, and why that is not the same as correct: every one is an opcode
# handler reached through the sequencer's computed trampoline (engine/sound/
# seq_opcode_tab.emp's `dc.w` rows), never `call`ed, and each ends by `jp`-ing back to
# Sequencer_NextOpcode.fetch with `hl` advanced past its operand, which is the handler's
# intended effect. No caller can be broken by the omission. What is missing is only the
# declaration, and the declaration is what a future `call` would trust.
# ---------------------------------------------------------------------------------------
SEQ = "engine/sound/sound_sequencer.emp"
KNOWN_UNDER_DECLARED: dict[tuple[str, str], frozenset[str]] = {
    (SEQ, "Seq_Op_NoteFill"): frozenset({"h", "l"}),
    (SEQ, "Seq_Op_PsgEnv"):   frozenset({"h", "l"}),
    (SEQ, "Seq_Op_Detune"):   frozenset({"h", "l"}),
    (SEQ, "Seq_Op_Ext"):      frozenset({"h", "l"}),
    (SEQ, "Seq_Op_Porta"):    frozenset({"h", "l"}),
    (SEQ, "Seq_Op_ModSet"):   frozenset({"h", "l"}),
    (SEQ, "Seq_Op_OpBias"):   frozenset({"h", "l"}),
}

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
        f"the Z80 sweep of {ROOTS} did not reach {SEQ}, the module this census's allow-list "
        f"lives in. It found {len(files)} file(s): {files}. The `cpu: z80` match is broken."
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
    procs = scan_tree()
    actual = {(p["file"], p["proc"]): frozenset(p["under"]) for p in procs if p["under"]}
    lines = {(p["file"], p["proc"]): p for p in procs}

    print(f"KNOWN_UNDER_DECLARED allow-list ({len(KNOWN_UNDER_DECLARED)} row(s)):")
    for (f, name), regs in sorted(KNOWN_UNDER_DECLARED.items()):
        print(f"  {f} {name}: writes {_fmt(regs)} undeclared")

    problems = []
    for key, regs in sorted(actual.items()):
        rec = lines[key]
        detail = ", ".join(f"{r} (first written at :{ln})" for r, ln in sorted(rec["under"].items()))
        if key not in KNOWN_UNDER_DECLARED:
            problems.append(f"NEW  {key[0]}:{rec['line']} {key[1]} writes {detail}, declared "
                            f"{_fmt(rec['declared']) or 'nothing'}")
        elif regs != KNOWN_UNDER_DECLARED[key]:
            problems.append(f"GREW {key[0]}:{rec['line']} {key[1]} now writes {detail}; the "
                            f"allow-list carries only {_fmt(KNOWN_UNDER_DECLARED[key])}")
    for key in sorted(set(KNOWN_UNDER_DECLARED) - set(actual)):
        problems.append(f"STALE {key[0]} {key[1]} no longer under-declares "
                        f"{_fmt(KNOWN_UNDER_DECLARED[key])} (fixed, renamed, or no longer a "
                        f"leaf): delete its row so the list only shrinks on purpose")

    assert not problems, (
        "Z80 clobbers() under-declaration census (CTRL-1 / LS-2a) is not at its allow-list:\n  "
        + "\n  ".join(problems)
        + "\nA Z80 proc must declare every register it writes in clobbers(), preserves() or "
          "out(). Fix the ATTRIBUTE; do not widen the allow-list for a new proc."
    )


def test_allow_listed_procs_have_no_call_site():
    """The allow-list's safety premise, checked rather than remembered: an under-declared
    proc is harmless only while nothing `call`s it and trusts the contract."""
    names = {name for _, name in KNOWN_UNDER_DECLARED}
    hits = []
    for p in z80_files():
        for n, raw in enumerate(p.read_text(errors="replace").splitlines(), start=1):
            s = _strip(raw).strip()
            m = re.match(r"^(?:call)\s+(?:\w+\s*,\s*)?(\w+)\b", s, re.I)
            if m and m.group(1) in names:
                hits.append(f"{p.relative_to(REPO).as_posix()}:{n} {s}")
    print(f"call sites of allow-listed procs: {len(hits)}")
    assert not hits, (
        "an allow-listed under-declaring proc is now CALLED, so a caller trusts a contract "
        "that omits registers it writes. Correct its clobbers() first:\n  " + "\n  ".join(hits)
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
        "    pub proc Caller () clobbers() {\n"
        "        ld      b, 1\n"
        "        call    Leaf_Ok\n"
        "        ret\n"
        "    }\n"
        "}\n"
    )
    procs = {p["proc"]: p for p in scan_text(src, "fake.emp")}
    assert set(procs) == {"Leaf_Under", "Leaf_Ok", "Caller"}, sorted(procs)
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
    test_allow_listed_procs_have_no_call_site()
    test_scanner_controls()
    print("OK")
