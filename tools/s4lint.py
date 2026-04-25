#!/usr/bin/env python3
"""
s4lint — Sonic 4 Engine 68000 assembly linter.

Tokenizes AS Macro Assembler source, follows includes, and runs
configurable diagnostic checks. Runs as a pre-build step.

Usage:
    python3 tools/s4lint.py [options] file [file ...]
    python3 tools/s4lint.py [options] main.asm          # follows includes
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from collections import namedtuple
from typing import List, Optional, Set, Dict, Tuple

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# AS assembler directives (lowercased for lookup; some are uppercase in source)
ASM_DIRECTIVES: frozenset = frozenset({
    # Data
    "dc", "ds", "dcb",
    # Alignment / padding
    "even", "align", "odd",
    # Assembly control
    "org", "cpu", "padding", "supmode", "radix",
    "include", "binclude",
    # Conditional assembly
    "if", "elseif", "else", "endif",
    "ifdef", "ifndef", "ifused", "ifnused",
    "switch", "case", "elsecase", "endcase", "endswitch",
    # Repetition
    "rept", "irp", "irpc", "endr",
    # Macro definition
    "macro", "endm",
    # Struct
    "struct", "endstruct",
    # Symbol definition
    "set", "equ", "label", "function",
    # Phase / section
    "phase", "dephase", "section",
    # Listing
    "listing", "page", "title", "error", "warning",
    # Miscellaneous
    "end", "fail",
    # Padding
    "pushv", "popv",
})

# Branch / loop mnemonics
BRANCH_MNEMONICS: frozenset = frozenset({
    "bra", "bsr",
    "beq", "bne", "blt", "bgt", "ble", "bge",
    "blo", "bls", "bhi", "bhs",
    "bcc", "bcs", "bvc", "bvs",
    "bpl", "bmi",
    "dbf", "dbra", "dbt", "dbcc", "dbcs", "dbvc", "dbvs",
    "dbeq", "dbne", "dblt", "dbgt", "dble", "dbge",
    "dblo", "dbls", "dbhi", "dbhs",
    "dbpl", "dbmi",
    "jmp", "jsr",
})

# Full set of 68000 mnemonics (lower-case — used to distinguish instructions
# from macro invocations).
_M68K_MNEMONICS: frozenset = frozenset({
    # Data movement
    "move", "movea", "movem", "movep", "moveq",
    "exg", "swap", "lea", "pea", "link", "unlk",
    "clr", "ext", "extb",
    # Arithmetic
    "add", "adda", "addi", "addq", "addx",
    "sub", "suba", "subi", "subq", "subx",
    "neg", "negx",
    "muls", "mulu", "divs", "divu",
    "abcd", "nbcd", "sbcd",
    # Logical
    "and", "andi", "or", "ori", "eor", "eori", "not",
    # Shift / rotate
    "asl", "asr", "lsl", "lsr", "rol", "ror", "roxl", "roxr",
    # Bit manipulation
    "bchg", "bclr", "bset", "btst",
    # Branches (included for mnemonic lookup)
    *BRANCH_MNEMONICS,
    # Comparison
    "cmp", "cmpa", "cmpi", "cmpm", "tst",
    # Control flow
    "nop", "rts", "rte", "rtd", "rtr",
    "trap", "trapv", "illegal",
    "stop", "reset", "rte",
    # Stack
    "push", "pop",
    # Conditional set
    "st", "sf",
    "seq", "sne", "slt", "sgt", "sle", "sge",
    "slo", "sls", "shi", "shs",
    "scc", "scs", "svc", "svs", "spl", "smi",
    # Miscellaneous
    "chk", "tas", "cas", "cas2",
    # 68020+
    "bfchg", "bfclr", "bfexts", "bfextu", "bfffo", "bfins", "bfset", "bftst",
    "pack", "unpk",
    "cinv", "cpush",
    "moves",
})

# Directives that may appear with label BEFORE them on the same token
# (e.g. "VDP_Shadow struct", "VDP_Shadow endstruct", "stopZ80 macro")
_LABEL_BEFORE_DIRECTIVE: frozenset = frozenset({
    "struct", "endstruct", "macro", "endm", "function",
})

# File-level skips
_SKIP_FILES: frozenset = frozenset({
    "debug/debugger.asm",
    "debug/error_handler.asm",
})

# ---------------------------------------------------------------------------
# Token
# ---------------------------------------------------------------------------

Token = namedtuple("Token", ["label", "instruction", "size", "operands", "comment"])


def _split_comment(text: str) -> Tuple[str, str]:
    """Split *text* into (body, comment) honoring string literals.

    A comment starts at the first `;` that is not inside a double-quoted
    string (single-quoted strings are not used in AS 68K source).
    """
    in_string = False
    escape_next = False
    for i, ch in enumerate(text):
        if escape_next:
            escape_next = False
            continue
        if ch == "\\" and in_string:
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if not in_string and ch == ";":
            return text[:i], text[i:]
    return text, ""


def _split_operands(text: str) -> List[str]:
    """Split an operand string on top-level commas (not inside parentheses or
    double-quoted strings).
    """
    if not text:
        return []

    operands: List[str] = []
    depth = 0           # parenthesis depth
    in_string = False
    start = 0

    for i, ch in enumerate(text):
        if ch == '"':
            in_string = not in_string
        elif not in_string:
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            elif ch == "," and depth == 0:
                part = text[start:i].strip()
                if part:
                    operands.append(part)
                start = i + 1

    tail = text[start:].strip()
    if tail:
        operands.append(tail)

    return operands


# Regex to strip a size suffix from the end of an instruction token.
# Valid suffixes: .b .w .l .s (short branches)
_SIZE_RE = re.compile(r"^(.+?)(\.(?:b|w|l|s|L|W|B|S))$", re.IGNORECASE)


def tokenize_line(line: str) -> Token:
    """Parse one line of 68K AS assembly into a Token namedtuple.

    Handles:
    - Global labels (``Label:``), local labels (``.loop:``), and
      label-before-directive forms (``VDP_Shadow struct``).
    - Assignment lines: ``MY_CONST = $50``
    - Instructions / directives with optional size suffix and operands.
    - Macro invocations (case-preserved).
    - Comment-only and blank lines.
    - Operand splitting that respects parentheses and string literals.
    """
    # 1. Strip trailing whitespace; keep leading (column position matters)
    raw = line.rstrip()

    # 2. Separate body from comment (respects string literals)
    body, comment = _split_comment(raw)
    body = body.rstrip()

    # 3. Blank / comment-only
    if not body.strip():
        return Token("", "", "", [], comment.strip())

    # 4. Assignment line: TOKEN = value
    #    May have whitespace around the '='.
    #    Must check BEFORE generic label parsing to catch "MY_CONST = $50".
    eq_match = re.match(r"^(\S+)\s*=\s*(.+)$", body)
    if eq_match and "struct" not in body and "endstruct" not in body:
        lhs = eq_match.group(1)
        rhs = eq_match.group(2).strip()
        # Disambiguate: if lhs ends with ':' it's a label, not an assignment.
        # Real assignment tokens never end with ':'.
        if not lhs.endswith(":"):
            return Token(lhs, "=", "", [rhs], comment.strip())

    # 5. Determine label and rest of body.
    label = ""
    rest = body

    # Strip column-0 or indented labels (end with ':')
    # Pattern: optional leading whitespace, then identifier ending with ':'
    label_colon_re = re.match(r"^(\s*)((?:[._A-Za-z][._A-Za-z0-9]*):)\s*(.*)", rest)
    if label_colon_re:
        label = label_colon_re.group(2).rstrip(":")
        rest = label_colon_re.group(3)

    if not rest.strip():
        # Label only (possibly with comment stripped already)
        return Token(label, "", "", [], comment.strip())

    # 6. Tokenize what remains: instruction [operands]
    #
    # In AS Macro Assembler, a line starting at column 0 (no leading whitespace)
    # with a non-local identifier FOLLOWED BY a known directive or mnemonic
    # treats that identifier as a label (no colon required).
    #
    # Examples:
    #   "VDP_Shadow struct"    → label=VDP_Shadow, instr=struct
    #   "vdp_mode1 ds.b 1"    → label=vdp_mode1,  instr=ds, size=.b
    #   "stopZ80 macro"        → label=stopZ80,    instr=macro
    #   "vdpComm function ..."  → label=vdpComm,   instr=function
    #
    # Rule: if we have no label yet AND the original line starts at column 0
    # (no leading whitespace) AND the line contains at least two tokens,
    # and the second token (stripped of any size suffix) is a known
    # directive or mnemonic, treat the first token as a label.
    rest_stripped = rest.strip()

    if label == "" and not body[0:1].isspace():
        # Line started at column 0 — potential no-colon label
        space_idx = _first_unquoted_space(rest_stripped)
        if space_idx != -1:
            first_token = rest_stripped[:space_idx]
            after_first = rest_stripped[space_idx:].lstrip()
            # Extract the second token (strip size suffix for lookup)
            second_token_end = _first_unquoted_space(after_first)
            raw_second = (after_first[:second_token_end]
                          if second_token_end != -1 else after_first)
            raw_second = raw_second.split()[0] if raw_second.split() else ""
            # Strip size suffix from second token for lookup
            m2 = _SIZE_RE.match(raw_second)
            second_base = m2.group(1).lower() if m2 else raw_second.lower()
            if (second_base in ASM_DIRECTIVES or second_base in _M68K_MNEMONICS):
                label = first_token
                rest_stripped = after_first

    # 7. Extract instruction and size from the leading token of rest_stripped.
    parts = rest_stripped.split(None, 1)   # split on first whitespace run
    if not parts:
        return Token(label, "", "", [], comment.strip())

    instr_raw = parts[0]
    operand_str = parts[1].strip() if len(parts) > 1 else ""

    # Strip size suffix
    size = ""
    instr = instr_raw
    m = _SIZE_RE.match(instr_raw)
    if m:
        instr = m.group(1)
        size = m.group(2).lower()

    # Normalize instruction case:
    # - Known 68K mnemonics → lowercase
    # - Known directives → lowercase (except BINCLUDE which we keep as-is
    #   since the codebase uses uppercase)
    instr_lower = instr.lower()
    if instr_lower in _M68K_MNEMONICS:
        instr = instr_lower
    elif instr_lower in ASM_DIRECTIVES and instr_lower != "binclude":
        instr = instr_lower
    # else: macro name — preserve original case

    # 8. Split operands (honoring parens and strings)
    operands = _split_operands(operand_str)

    return Token(label, instr, size, operands, comment.strip())


def _first_unquoted_space(text: str) -> int:
    """Return index of first whitespace character not inside a double-quoted
    string, or -1 if none found."""
    in_string = False
    for i, ch in enumerate(text):
        if ch == '"':
            in_string = not in_string
        elif not in_string and ch in " \t":
            return i
    return -1


# ---------------------------------------------------------------------------
# Diagnostic
# ---------------------------------------------------------------------------

class Diagnostic:
    """One linter diagnostic."""
    __slots__ = ("file", "line", "severity", "code", "message")

    def __init__(self, file: str, line: int, severity: str, code: str,
                 message: str) -> None:
        self.file = file
        self.line = line
        self.severity = severity
        self.code = code
        self.message = message

    def __str__(self) -> str:
        return f"{self.file}:{self.line}: {self.severity}: {self.message} [{self.code}]"

    def __repr__(self) -> str:
        return (f"Diagnostic({self.file!r}, {self.line}, {self.severity!r}, "
                f"{self.code!r}, {self.message!r})")


# ---------------------------------------------------------------------------
# LintContext
# ---------------------------------------------------------------------------

class LintContext:
    """Per-file linting state."""

    def __init__(self, filepath: str, options: dict) -> None:
        self.filepath = filepath
        self.options = options
        self.diagnostics: List[Diagnostic] = []

        # Z80 bus state: 'running' | 'stopped'
        self.z80_state: str = "running"
        # Interrupt state: 'enabled' | 'disabled'
        self.ints_state: str = "enabled"
        # Byte count accumulator (for alignment checks)
        self.byte_count: int = 0
        # SR has been saved to stack (for paired save/restore checks)
        self.sr_saved: bool = False
        # Inside a dbf/dbra loop body
        self.in_dbf_loop: bool = False
        # Name of the current routine (global label)
        self.current_routine: str = ""
        # Previous token (for fall-through / pairing checks)
        self.prev_instruction: str = ""
        # Local labels seen in the current routine
        self.local_labels: Set[str] = set()
        # Number of lines in the current routine
        self.routine_lines: int = 0
        # Whether the last routine ended cleanly (rts/rte/jmp/bra)
        self.last_routine_terminated: bool = False

        # Block-level guards (linting is suppressed inside these blocks)
        self.in_struct: bool = False
        self.in_rept: bool = False
        self.in_macro_def: bool = False

    def reset_routine_state(self) -> None:
        """Reset per-routine tracking at each global label boundary."""
        self.z80_state = "running"
        self.ints_state = "enabled"
        self.sr_saved = False
        self.in_dbf_loop = False
        self.local_labels = set()
        self.routine_lines = 0

    def check_routine_end(self, line_num: int) -> None:
        """Run checks at rts/rte — paired-resource validation."""
        if self.z80_state == "stopped":
            self.emit("error", "E007", line_num,
                      f"rts/rte while Z80 is stopped (unpaired stopZ80/startZ80)")
        if self.sr_saved:
            self.emit("error", "E010", line_num,
                      f"rts/rte while SR is on stack (leaked move sr, -(sp))")

    # ------------------------------------------------------------------
    # Emit helpers
    # ------------------------------------------------------------------

    def emit(self, severity: str, code: str, line_num: int, message: str) -> None:
        d = Diagnostic(self.filepath, line_num, severity, code, message)
        self.diagnostics.append(d)

    def error(self, code: str, line_num: int, message: str) -> None:
        self.emit("error", code, line_num, message)

    def warning(self, code: str, line_num: int, message: str) -> None:
        self.emit("warning", code, line_num, message)


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------

def discover_files(entry_path: str, follow_includes: bool = True,
                   base_dir: Optional[str] = None) -> List[str]:
    """Return an ordered list of all .asm files reachable from *entry_path*
    by following ``include`` directives (depth-first, pre-order).

    Files listed in *_SKIP_FILES* are excluded from linting but their
    includes are still followed so we don't miss transitively included files
    (unless the skipped file is the include target itself).

    The returned list contains absolute paths, deduplicated (each file
    appears only once, in first-encounter order).
    """
    if base_dir is None:
        base_dir = os.path.dirname(os.path.abspath(entry_path))

    entry_abs = os.path.abspath(entry_path)
    visited: Set[str] = set()
    ordered: List[str] = []

    def _visit(path: str) -> None:
        if path in visited:
            return
        visited.add(path)
        ordered.append(path)

        if not follow_includes:
            return

        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                lines = fh.readlines()
        except OSError:
            return

        for raw_line in lines:
            tok = tokenize_line(raw_line)
            if tok.instruction.lower() in ("include",) and tok.operands:
                # Operand is a quoted string: `"path/to/file.asm"`
                inc_arg = tok.operands[0].strip().strip('"')
                # AS Macro Assembler resolves includes relative to the
                # current working directory (project root) at assembly time.
                # Try project-root-relative first, then file-dir-relative.
                inc_dir = os.path.dirname(path)
                candidate_from_root = os.path.normpath(
                    os.path.join(base_dir, inc_arg))
                candidate_from_file = os.path.normpath(
                    os.path.join(inc_dir, inc_arg))
                if os.path.isfile(candidate_from_root):
                    _visit(candidate_from_root)
                elif os.path.isfile(candidate_from_file):
                    _visit(candidate_from_file)

    _visit(entry_abs)
    return ordered


# ---------------------------------------------------------------------------
# Run checks (skeleton)
# ---------------------------------------------------------------------------

_SUPPRESS_RE = re.compile(r";\s*lint:\s*disable\s*=\s*([\w,]+)")


def _parse_suppressed(comment: str) -> Set[str]:
    """Extract suppressed code set from a ``; lint: disable=E001,W003`` comment."""
    m = _SUPPRESS_RE.search(comment)
    if not m:
        return set()
    return {code.strip() for code in m.group(1).split(",")}


# ---------------------------------------------------------------------------
# Numeric parsing helpers (E003/E004)
# ---------------------------------------------------------------------------

def parse_numeric(s: str) -> Optional[int]:
    """Parse a bare numeric literal (hex ``$XXXX`` or decimal) from *s*.

    Returns the integer value, or *None* if *s* is not a plain numeric literal
    (e.g. contains operators, is a symbolic label, or is empty).
    """
    s = s.strip()
    if not s:
        return None
    if s.startswith("$"):
        hex_part = s[1:]
        if hex_part and all(c in "0123456789abcdefABCDEF" for c in hex_part):
            return int(hex_part, 16)
        return None
    # Decimal — must be all digits (no operators, no labels)
    if s.isdigit():
        return int(s)
    return None


def _extract_address_value(operand: str) -> Optional[int]:
    """Extract a numeric address from an operand like ``($C00004).l`` or
    ``$FF0000``.

    Returns the integer address, or *None* when the operand is symbolic or
    cannot be resolved at lint time.

    Handles:
    - ``$XXXX``                  plain hex
    - ``$XXXX.w``                hex with address-size suffix (no parens)
    - ``($XXXX)``                hex in parens, no suffix
    - ``($XXXX).l`` / ``.w``     hex in parens with suffix
    - ``#...``                    immediate — NOT an address operand → None
    """
    s = operand.strip()

    # Immediate values (#...) are not address operands
    if s.startswith("#"):
        return None

    # Strip outer paren + optional size suffix: ($C00004).l → $C00004
    paren_suffix_re = re.compile(r"^\(\s*([^)]+)\s*\)(?:\.[bwlBWL])?$")
    m = paren_suffix_re.match(s)
    if m:
        inner = m.group(1).strip()
        return parse_numeric(inner)

    # Plain with optional address-size suffix: $FF0000.w → $FF0000
    dot_suffix_re = re.compile(r"^(.+?)(\.[bwlBWL])$")
    m2 = dot_suffix_re.match(s)
    if m2:
        base = m2.group(1)
        return parse_numeric(base)

    # Plain with no suffix
    return parse_numeric(s)


# ---------------------------------------------------------------------------
# Mnemonics for checks
# ---------------------------------------------------------------------------

_MULDIV_MNEMONICS: frozenset = frozenset({"mulu", "muls", "divu", "divs"})
_ADDRESS_MNEMONICS: frozenset = frozenset({"movea", "lea", "jmp", "jsr"})

# Branch mnemonics that E001 checks (excludes dbf/dbra variants and jmp/jsr)
_E001_BRANCH_MNEMONICS: frozenset = frozenset({
    "bra", "bsr",
    "beq", "bne", "blt", "bgt", "ble", "bge",
    "blo", "bls", "bhi", "bhs",
    "bcc", "bcs", "bvc", "bvs",
    "bpl", "bmi",
})

# AS data-layout directives — skip for E004 (dc.w $0001 is not a memory access)
_DATA_DIRECTIVES: frozenset = frozenset({"dc", "ds", "dcb"})


# ---------------------------------------------------------------------------
# Macro contract registry (E008, E011)
# ---------------------------------------------------------------------------

# Each entry maps a macro name (original case) to a dict with optional keys:
#   requires: {state_key: expected_value} — E008 if condition not met (or unknown)
#   rejects:  {state_key: rejected_value} — E011 if state matches exactly
#   sets:     {state_key: new_value}       — applied after checks
MACRO_CONTRACTS: Dict[str, dict] = {
    "stopZ80":        {"rejects":  {"z80": "stopped"},  "sets": {"z80": "stopped"}},
    "startZ80":       {"requires": {"z80": "stopped"},  "sets": {"z80": "running"}},
    "disableInts":    {"sets": {"ints": "disabled"}},
    "enableInts":     {"requires": {"ints": "disabled"}, "sets": {"ints": "enabled"}},
    # setVDPReg writes to shadow table RAM only — does NOT touch VDP hardware.
    # Flush_VDP_Shadow is what requires Z80 stopped. No requires needed here.
    "setVDPReg":      {},
    "vdpCommReg":     {},
    "queueStaticDMA": {},
}

# VDP port identifiers that E006 watches for writes
_VDP_WRITE_TARGETS: frozenset = frozenset({
    "VDP_CTRL", "VDP_DATA", "$C00004", "$C00000",
})


def _get_hw_state(ctx: LintContext, key: str) -> str:
    """Return the current hardware state for *key* ('z80' or 'ints')."""
    if key == "z80":
        return ctx.z80_state
    if key == "ints":
        return ctx.ints_state
    return "unknown"


def _set_hw_state(ctx: LintContext, key: str, value: str, line_num: int) -> None:
    """Update hardware state for *key* to *value*."""
    if key == "z80":
        ctx.z80_state = value
    elif key == "ints":
        ctx.ints_state = value


# ---------------------------------------------------------------------------
# E005 byte-counting helpers
# ---------------------------------------------------------------------------

def _count_dc_b_items(operands: List[str]) -> int:
    """Count the number of bytes produced by a dc.b operand list.

    Each comma-separated operand is 1 byte, except string literals which
    contribute one byte per character (quotes excluded).

    Example: ["1", "2", '"AB"'] -> 4
    """
    total = 0
    for op in operands:
        s = op.strip()
        if s.startswith('"') and s.endswith('"') and len(s) >= 2:
            # String literal: count characters between the quotes
            total += len(s) - 2
        else:
            total += 1
    return total


def _count_ds_b_items(operands: List[str]) -> int:
    """Return the byte count from a ds.b directive operand list.

    Only supports plain numeric literals ($XX or decimal).  Returns 0 for
    symbolic or expression operands that cannot be resolved at lint time.
    """
    if not operands:
        return 0
    val = parse_numeric(operands[0])
    return val if val is not None else 0


def check_e005_track(ctx: LintContext, token: Token, line_num: int,
                     suppressed: Set[str]) -> None:
    """E005: Missing alignment after byte data.

    Accumulates the running byte count from dc.b / ds.b directives.  When a
    word-or-larger directive (dc.w / dc.l / ds.w / ds.l) or any 68K
    instruction is encountered while the accumulated count is odd, an error
    is emitted and the counter is reset.  ``even`` and ``align`` reset the
    counter unconditionally.
    """
    instr_lower = token.instruction.lower()

    # Alignment / address-reset directives -- reset counter
    if instr_lower in ("even", "align", "phase", "dephase", "org"):
        ctx.byte_count = 0
        return

    # dc.b -- accumulate bytes
    if instr_lower == "dc" and token.size == ".b":
        ctx.byte_count += _count_dc_b_items(token.operands)
        return

    # ds.b -- accumulate bytes if count is a resolvable literal; otherwise
    # the alignment state is unknown so reset the counter to avoid false
    # positives on symbolic counts like "ds.b VDP_Shadow_len".
    if instr_lower == "ds" and token.size == ".b":
        n = _count_ds_b_items(token.operands)
        if token.operands and parse_numeric(token.operands[0]) is None:
            # Symbolic count -- alignment tracking is broken; reset
            ctx.byte_count = 0
        else:
            ctx.byte_count += n
        return

    # Word-or-larger dc/ds -- must check alignment then reset
    is_word_or_larger_data = (
        instr_lower in ("dc", "ds") and token.size in (".w", ".l")
    )

    # 68K instruction -- must check alignment then reset
    is_68k = instr_lower in _M68K_MNEMONICS

    if is_word_or_larger_data or is_68k:
        if ctx.byte_count % 2 != 0:
            if "E005" not in suppressed:
                ctx.error("E005", line_num,
                          f"word-or-larger data/instruction after {ctx.byte_count} "
                          f"unaligned byte(s) -- insert 'even' or 'align 2' first")
        ctx.byte_count = 0
        return

    # Any other dc/ds or non-byte directive: reset byte tracking
    if instr_lower in _DATA_DIRECTIVES:
        ctx.byte_count = 0


# ---------------------------------------------------------------------------
# Check functions
# ---------------------------------------------------------------------------

def check_e001(ctx: LintContext, token: Token, line_num: int,
               suppressed: Set[str]) -> None:
    """E001: Branch without explicit size suffix (.s or .w)."""
    if "E001" in suppressed:
        return
    if token.instruction.lower() not in _E001_BRANCH_MNEMONICS:
        return
    if not token.size:
        ctx.error("E001", line_num,
                  f"unsized branch '{token.instruction}' — use .s or .w suffix")


def check_e002(ctx: LintContext, token: Token, line_num: int,
               suppressed: Set[str]) -> None:
    """E002/W014: mulu/muls/divu/divs — error in engine/ or objects/, warning elsewhere."""
    if token.instruction.lower() not in _MULDIV_MNEMONICS:
        return

    fp = ctx.filepath.replace("\\", "/")
    in_hot_path = (
        fp.startswith("engine/") or "/engine/" in fp or
        fp.startswith("objects/") or "/objects/" in fp
    )

    if in_hot_path:
        if "E002" in suppressed:
            return
        ctx.error("E002", line_num,
                  f"'{token.instruction}' in hot-path file — use shifts/adds/lookup table")
    else:
        if "W014" in suppressed:
            return
        ctx.warning("W014", line_num,
                    f"'{token.instruction}' is slow (75+ cycles) — consider alternative")


def check_e003(ctx: LintContext, token: Token, line_num: int,
               suppressed: Set[str]) -> None:
    """E003: Odd address in movea/lea/jmp/jsr operand."""
    if "E003" in suppressed:
        return
    if token.instruction.lower() not in _ADDRESS_MNEMONICS:
        return

    for operand in token.operands:
        val = _extract_address_value(operand)
        if val is not None and (val & 1):
            ctx.error("E003", line_num,
                      f"odd address {operand!r} in '{token.instruction}' "
                      f"(addresses must be word-aligned)")
            return  # one error per line is enough


def check_e004(ctx: LintContext, token: Token, line_num: int,
               suppressed: Set[str]) -> None:
    """E004: Word or long-sized instruction accesses an odd literal address."""
    if "E004" in suppressed:
        return
    if token.size not in (".w", ".l"):
        return

    # Skip data-layout directives
    instr_lower = token.instruction.lower()
    if instr_lower in _DATA_DIRECTIVES or instr_lower in ASM_DIRECTIVES:
        return

    for operand in token.operands:
        val = _extract_address_value(operand)
        if val is not None and (val & 1):
            ctx.error("E004", line_num,
                      f"word/long access to odd address {operand!r} — bus error on 68000")
            return  # one error per line is enough


def check_macro_contracts(ctx: LintContext, token: Token, line_num: int,
                          suppressed: Set[str]) -> None:
    """E008 / E011: Check and apply macro contracts.

    - E008: a ``requires`` precondition is not met (state != expected, or unknown)
    - E011: a ``rejects`` precondition matches (state == rejected value exactly)
    - After checks, ``sets`` updates are applied to ctx state.
    """
    # Macro names are preserved in original case (see tokenize_line)
    contract = MACRO_CONTRACTS.get(token.instruction)
    if contract is None:
        return

    # Check rejects (E011 — double invocation guard)
    rejects = contract.get("rejects", {})
    for key, rejected_val in rejects.items():
        current = _get_hw_state(ctx, key)
        if current == rejected_val:
            if "E011" not in suppressed:
                ctx.error("E011", line_num,
                          f"'{token.instruction}' invoked when {key}={current!r} "
                          f"(double-stop or similar)")

    # Check requires (E008 — precondition not satisfied)
    requires = contract.get("requires", {})
    for key, expected_val in requires.items():
        current = _get_hw_state(ctx, key)
        if current != expected_val:
            if "E008" not in suppressed:
                ctx.error("E008", line_num,
                          f"'{token.instruction}' requires {key}={expected_val!r} "
                          f"but current state is {key}={current!r}")

    # Apply sets — update state after checking
    for key, new_val in contract.get("sets", {}).items():
        _set_hw_state(ctx, key, new_val, line_num)


# Regex to detect 68000 address registers inside an operand (register-indirect)
_ADDR_REG_RE = re.compile(r'\b(a[0-7]|sp)\b', re.IGNORECASE)


def check_e006(ctx: LintContext, token: Token, line_num: int,
               suppressed: Set[str]) -> None:
    """E006: VDP write (to VDP_CTRL or VDP_DATA) when Z80 is not stopped.

    Only checks move instructions whose DESTINATION operand names a VDP port
    (by symbolic name or literal $C00000/$C00004 address).

    Register-indirect addressing (e.g. ``(a4)``, ``PSG_PORT-VDP_DATA(a3)``)
    is NOT flagged because the linter cannot resolve register contents at lint
    time — boot code intentionally preloads VDP_CTRL / VDP_DATA into address
    registers and accesses them indirectly.

    VDP reads (VDP port as SOURCE operand) are legal without Z80 stopped.
    """
    if "E006" in suppressed:
        return
    if ctx.z80_state == "stopped":
        return

    instr_lower = token.instruction.lower()
    if instr_lower != "move":
        return

    # The destination is the LAST operand of a move instruction.
    if not token.operands:
        return
    dest = token.operands[-1].strip()

    # Skip register-indirect addressing modes — if any address or stack
    # register appears in the destination the linter cannot determine the
    # effective address at lint time.
    if _ADDR_REG_RE.search(dest):
        return

    # Check whether dest references a VDP port (symbolic or literal hex address)
    dest_upper = dest.upper()

    # Symbolic name check (e.g. "(VDP_CTRL).l", "(VDP_DATA).l")
    for name in ("VDP_CTRL", "VDP_DATA"):
        if name in dest_upper:
            ctx.error("E006", line_num,
                      f"VDP write to {name} while Z80 is not stopped "
                      f"(use stopZ80 before VDP access)")
            return

    # Literal hex address check ($C00000 or $C00004)
    val = _extract_address_value(dest)
    if val is not None and val in (0xC00000, 0xC00004):
        ctx.error("E006", line_num,
                  f"VDP write to ${val:X} while Z80 is not stopped "
                  f"(use stopZ80 before VDP access)")


def run_checks(ctx: LintContext, token: Token, line_num: int,
               raw_line: str, suppressed: Set[str]) -> None:
    """Apply all enabled checks to *token*.

    Currently implements:
    - Block-state tracking (struct / macro def / rept)
    - Routine boundary tracking (global label → reset_routine_state)
    - Local label tracking
    - Routine termination detection (rts/rte → check_routine_end)
    - Fall-through detection placeholder
    """
    instr = token.instruction
    instr_lower = instr.lower()

    # ------------------------------------------------------------------
    # Block-level tracking — update state FIRST so checks inside blocks
    # can reference correct state, then skip actual lint checks if blocked.
    # ------------------------------------------------------------------

    # Struct block
    if instr_lower == "struct":
        ctx.in_struct = True
        return
    if instr_lower == "endstruct":
        ctx.in_struct = False
        return

    # Macro definition block
    if instr_lower == "macro":
        ctx.in_macro_def = True
        return
    if instr_lower == "endm":
        ctx.in_macro_def = False
        return

    # Rept block
    if instr_lower == "rept":
        ctx.in_rept = True
        return
    if instr_lower == "endr":
        ctx.in_rept = False
        return

    # Skip linting inside struct / macro def / rept bodies
    if ctx.in_struct or ctx.in_macro_def or ctx.in_rept:
        return

    # ------------------------------------------------------------------
    # Routine boundary tracking
    # ------------------------------------------------------------------
    label = token.label

    if label and not label.startswith("."):
        # Global label — start of a new routine
        ctx.current_routine = label
        ctx.reset_routine_state()
        ctx.last_routine_terminated = False

    if label and label.startswith("."):
        # Local label — record it
        ctx.local_labels.add(label)

    if not instr:
        # Label-only or blank line — nothing more to check
        return

    ctx.routine_lines += 1

    # ------------------------------------------------------------------
    # Routine termination
    # ------------------------------------------------------------------
    if instr_lower in ("rts", "rte"):
        ctx.check_routine_end(line_num)
        ctx.last_routine_terminated = True

    # ------------------------------------------------------------------
    # Stateful checks (must run before stateless checks)
    # ------------------------------------------------------------------
    if token.instruction:
        check_e005_track(ctx, token, line_num, suppressed)

    # ------------------------------------------------------------------
    # Hardware state tracking — macro contracts (E008/E011) then VDP write
    # check (E006).  Order matters: macro_contracts updates state first so
    # that e006 sees the updated z80_state for the current instruction.
    # ------------------------------------------------------------------
    if token.instruction:
        check_macro_contracts(ctx, token, line_num, suppressed)
        check_e006(ctx, token, line_num, suppressed)

    # ------------------------------------------------------------------
    # Stateless per-instruction checks
    # ------------------------------------------------------------------
    if token.instruction:
        check_e001(ctx, token, line_num, suppressed)
        check_e002(ctx, token, line_num, suppressed)
        check_e003(ctx, token, line_num, suppressed)
        check_e004(ctx, token, line_num, suppressed)

    # ------------------------------------------------------------------
    # Track prev_instruction for fall-through detection (future checks)
    # ------------------------------------------------------------------
    ctx.prev_instruction = instr_lower


# ---------------------------------------------------------------------------
# Lint a single file
# ---------------------------------------------------------------------------

def lint_file(filepath: str, options: dict, base_dir: str) -> LintContext:
    """Read *filepath*, tokenize, and run all checks.

    Returns the populated LintContext.
    """
    ctx = LintContext(filepath, options)

    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as fh:
            raw_lines = fh.readlines()
    except OSError as exc:
        ctx.error("E000", 0, f"cannot open file: {exc}")
        return ctx

    for line_num, raw_line in enumerate(raw_lines, start=1):
        token = tokenize_line(raw_line)
        suppressed = _parse_suppressed(token.comment)
        run_checks(ctx, token, line_num, raw_line, suppressed)

    return ctx


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="s4lint",
        description="68000 assembly linter for the Sonic 4 Engine.",
    )
    p.add_argument(
        "files",
        nargs="+",
        metavar="FILE",
        help="Assembly files to lint (use main.asm to follow all includes).",
    )
    p.add_argument(
        "--warnings-as-errors",
        action="store_true",
        help="Treat all warnings as errors.",
    )
    p.add_argument(
        "--no-warnings",
        action="store_true",
        help="Suppress all warnings (only report errors).",
    )
    p.add_argument(
        "--only",
        metavar="CODES",
        default="",
        help="Comma-separated list of codes to report (e.g. E001,W003).",
    )
    p.add_argument(
        "--skip",
        metavar="CODES",
        default="",
        help="Comma-separated list of codes to suppress.",
    )
    p.add_argument(
        "--no-follow-includes",
        action="store_true",
        help="Do not follow include directives — lint only the listed files.",
    )
    return p


def main(argv: Optional[List[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    only_codes: Set[str] = (
        {c.strip() for c in args.only.split(",") if c.strip()}
        if args.only else set()
    )
    skip_codes: Set[str] = (
        {c.strip() for c in args.skip.split(",") if c.strip()}
        if args.skip else set()
    )

    options = {
        "warnings_as_errors": args.warnings_as_errors,
        "no_warnings": args.no_warnings,
        "only": only_codes,
        "skip": skip_codes,
    }

    follow = not args.no_follow_includes

    # Collect files to lint
    all_files: List[str] = []
    seen: Set[str] = set()

    for entry in args.files:
        abs_entry = os.path.abspath(entry)
        base_dir = os.path.dirname(abs_entry)
        files = discover_files(abs_entry, follow_includes=follow, base_dir=base_dir)
        for f in files:
            if f not in seen:
                seen.add(f)
                # Check against skip list (relative path comparison)
                rel = os.path.relpath(f, base_dir)
                if rel not in _SKIP_FILES:
                    all_files.append(f)

    has_errors = False
    has_warnings = False

    for filepath in all_files:
        base_dir = os.path.dirname(filepath)
        ctx = lint_file(filepath, options, base_dir)
        for diag in ctx.diagnostics:
            # Apply --only / --skip / --no-warnings filters
            if only_codes and diag.code not in only_codes:
                continue
            if diag.code in skip_codes:
                continue
            if options["no_warnings"] and diag.severity == "warning":
                continue
            # Promote warnings → errors if requested
            if options["warnings_as_errors"] and diag.severity == "warning":
                diag.severity = "error"

            print(str(diag))

            if diag.severity == "error":
                has_errors = True
            elif diag.severity == "warning":
                has_warnings = True

    if has_errors:
        return 1
    if has_warnings and options["warnings_as_errors"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
