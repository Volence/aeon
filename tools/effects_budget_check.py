#!/usr/bin/env python3
"""
effects_budget_check — gate the effects budget model's code-derived rows.

tools/effects_budget_model.toml carries a [symbols] table mapping a dotted row path to
the .emp constant that is its authority. This resolves each constant (following
references to other constants in the same file) and fails on disagreement.

Deliberately NOT a generator. The measured rows are upper bounds including profiler
instrumentation and exception entry, so a generated `ensure` against them would fail
programs that demonstrably run today (design spec 4.3).

WHAT THE REGEX MATCHES, measured against the shipped tree rather than a sample:

  `[pub] const NAME [: TYPE] = <expr>` at any indentation. All four parts are real:
  `pub` is optional (raster.emp's EFX_BLANK_DELAY is private), the name is not always
  ALL_CAPS (games/sonic4 has Act_grid_w_lo and friends), and the type annotation form
  is live in games/sonic4/config/sound_ids.emp (`pub const SONG_HCZ2 : SongId = 3`)
  and games/demo (`pub const VRAM_DEMO_OBJ : VramTile = $03E0`).

  A `const NAME: TYPE` with NO `=` is a contract declaration, not a constant, and is
  correctly skipped. A multi-line array constant matches with its head (`[`) as the
  value, which is not an integer expression and so fails loudly if anything reads it —
  the right outcome, since the caller asked for a number.

  Comments are stripped with emp_helper_closure.strip_comments, which handles `//`,
  the non-nesting `/* */` block form (lexer.rs:117-128) and string bodies. Stripping
  only `//`, as an earlier draft did, would have let a block-commented declaration
  become a live constant.

  KNOWN LIMIT: a type annotation containing `=` would not match. None exists, and the
  failure mode is a loud "unknown constant", not a wrong number.

Usage:
    python3 tools/effects_budget_check.py [AEON_DIR]
"""

from __future__ import annotations

import ast
import glob
import os
import re
import sys
import tomllib
from typing import Any, Callable, Dict, List, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from emp_helper_closure import strip_comments

CONST_RE = re.compile(
    r"^\s*(?:pub\s+)?const\s+([A-Za-z_][A-Za-z0-9_]*)\s*(?::[^=]*)?=\s*(.+?)\s*$"
)

# `$1F` -> 0x1F, `%1010` -> 0b1010, applied before the expression is parsed.
HEX_RE = re.compile(r"\$([0-9A-Fa-f]+)")
BIN_RE = re.compile(r"%([01]+)")
# `.emp` `/` is integer division; Python's `/` is float. Rewrite the single-slash form
# only, so an already-doubled `//` is left alone rather than mangled into `////`.
DIV_RE = re.compile(r"(?<!/)/(?!/)")

# The only AST node types the evaluator walks. Anything else — a call, an attribute,
# a subscript — is a hard error, so this never becomes an arbitrary-code path.
_ALLOWED = (
    ast.Expression, ast.BinOp, ast.UnaryOp, ast.Constant, ast.Name, ast.Load,
    ast.Add, ast.Sub, ast.Mult, ast.LShift, ast.RShift, ast.BitOr, ast.BitAnd,
    ast.BitXor, ast.USub, ast.UAdd, ast.FloorDiv,
)


def emp_constants(path: str) -> Dict[str, str]:
    """Every `const NAME = <expr>` in a module, as unevaluated expression text."""
    with open(path, "r", encoding="utf-8") as fh:
        src = strip_comments(fh.read())
    out: Dict[str, str] = {}
    for line in src.split("\n"):
        m = CONST_RE.match(line)
        if m:
            out[m.group(1)] = m.group(2).strip()
    return out


def eval_int_expr(expr: str, consts: Dict[str, str], _seen: frozenset = frozenset()) -> int:
    """Evaluate an .emp integer expression, resolving names against `consts`."""
    src = DIV_RE.sub("//", BIN_RE.sub(lambda m: str(int(m.group(1), 2)),
                                      HEX_RE.sub(r"0x\1", expr)))
    try:
        tree = ast.parse(src, mode="eval")
    except SyntaxError as exc:
        raise ValueError(f"cannot parse {expr!r}: {exc}") from exc

    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED):
            raise ValueError(f"{expr!r} contains an unsupported construct: {type(node).__name__}")

    def walk(node: ast.AST) -> int:
        if isinstance(node, ast.Expression):
            return walk(node.body)
        if isinstance(node, ast.Constant):
            if not isinstance(node.value, int) or isinstance(node.value, bool):
                raise ValueError(f"{expr!r} is not an integer expression")
            return node.value
        if isinstance(node, ast.Name):
            if node.id in _seen:
                raise ValueError(f"{expr!r}: circular reference through {node.id}")
            if node.id not in consts:
                raise ValueError(f"{expr!r}: unknown constant {node.id}")
            return eval_int_expr(consts[node.id], consts, _seen | {node.id})
        if isinstance(node, ast.UnaryOp):
            v = walk(node.operand)
            return -v if isinstance(node.op, ast.USub) else v
        if isinstance(node, ast.BinOp):
            a, b = walk(node.left), walk(node.right)
            op = node.op
            if isinstance(op, ast.Add):
                return a + b
            if isinstance(op, ast.Sub):
                return a - b
            if isinstance(op, ast.Mult):
                return a * b
            if isinstance(op, ast.FloorDiv):
                return a // b
            if isinstance(op, ast.LShift):
                return a << b
            if isinstance(op, ast.RShift):
                return a >> b
            if isinstance(op, ast.BitOr):
                return a | b
            if isinstance(op, ast.BitAnd):
                return a & b
            if isinstance(op, ast.BitXor):
                return a ^ b
        raise ValueError(f"{expr!r}: unsupported node {type(node).__name__}")

    return walk(tree)


def make_resolver(aeon: str) -> Callable[[str], int]:
    """`path.emp:EXPR` -> the integer value, with the module's constants in scope."""
    cache: Dict[str, Dict[str, str]] = {}

    def resolve(ref: str) -> int:
        rel, sep, expr = ref.partition(":")
        if not sep or not expr.strip():
            raise ValueError(f"[symbols] entry is not `path.emp:EXPR`: {ref!r}")
        path = os.path.join(aeon, rel)
        if path not in cache:
            if not os.path.exists(path):
                raise ValueError(f"[symbols] names a missing file: {rel}")
            # The scope is the named module's own consts PLUS every sibling `*_dsl.emp`
            # in the same directory. That is not a convenience — it mirrors how sigil
            # actually resolves these names: a *_dsl module is a COMPTIME_HELPERS member
            # and is GLOB-INJECTED into code modules, so `raster.emp` legitimately names
            # `RASTER_MAX_PATCH` without a `use`. Reading raster.emp alone made this
            # checker die with `unknown constant RASTER_MAX_PATCH` the moment P-b put a
            # helper constant into RASTER_STATE_SIZE — an unhandled traceback, not a
            # verdict, which is the worst way for a gate to fail.
            # Own-module consts win on a name clash, matching the injection's precedence.
            scope: Dict[str, str] = {}
            for sib in sorted(glob.glob(os.path.join(os.path.dirname(path), "*_dsl.emp"))):
                scope.update(emp_constants(sib))
            scope.update(emp_constants(path))
            cache[path] = scope
        return eval_int_expr(expr, cache[path])

    return resolve


def dig(model: Dict[str, Any], dotted: str) -> Any:
    """The model value at a dotted path. A path the model lacks is a KeyError.

    Explicitly including the "indexed through a scalar" case: relying on dict's own
    KeyError would raise TypeError there and escape an `except KeyError` caller, so a
    [symbols] entry naming a row under a scalar could read as something other than the
    error it is.
    """
    node: Any = model
    walked: List[str] = []
    for part in dotted.split("."):
        walked.append(part)
        if not isinstance(node, dict) or part not in node:
            raise KeyError(
                f"[symbols] names a row the model does not have: {dotted} "
                f"(nothing at {'.'.join(walked)})"
            )
        node = node[part]
    return node


def check(model: Dict[str, Any], symbols: Dict[str, str],
          resolver: Callable[[str], int]) -> List[Tuple[str, Any, int]]:
    """Rows whose TOML value disagrees with its .emp authority."""
    bad: List[Tuple[str, Any, int]] = []
    for row in sorted(symbols):
        declared = dig(model, row)      # KeyError on a symbol naming a missing row
        actual = resolver(symbols[row])
        if declared != actual:
            bad.append((row, declared, actual))
    return bad


def main(argv: List[str]) -> int:
    aeon = argv[0] if argv else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    toml_path = os.path.join(aeon, "tools", "effects_budget_model.toml")
    with open(toml_path, "rb") as fh:
        model = tomllib.load(fh)
    symbols = model.get("symbols")
    if not symbols:
        print(f"{toml_path}: no [symbols] table — nothing is gated, which is not a pass")
        return 2
    bad = check(model, symbols, make_resolver(aeon))
    if bad:
        print(f"{len(bad)} budget row(s) disagree with the shipped code:")
        for row, declared, actual in bad:
            print(f"  {row}: model says {declared}, {symbols[row]} is {actual}")
        return 1
    print(f"effects_budget_check: OK — {len(symbols)} code-derived rows agree")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
