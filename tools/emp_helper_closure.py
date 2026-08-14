#!/usr/bin/env python3
"""
emp_helper_closure — the COMPTIME_HELPERS name-collision gate.

sigil force-publicizes every PRIVATE comptime item of a COMPTIME_HELPERS module
(native.rs publicize_helper_comptime) and then injects one `use <helper>.*` glob per
helper into EVERY module, in list order (normalize_helper_imports). Between two
helpers the later silently wins. A name that is currently unresolved in some module —
degrading to a label reference — would start resolving to an injected const, which is
the one way helper membership changes emitted bytes.

So the exported closures must be pairwise disjoint. This checks that.

WHAT COUNTS AS EXPORTED, and why (read against sigil, which is the authority):

  publicize_helper_comptime (sigil-harness/src/native.rs) sets `public = true` on
  Const / Struct / Enum / Bitfield / Newtype / ComptimeFn / Vars(name.is_some()),
  recursing into `Item::Section` bodies. It deliberately leaves Equ, Data, Proc and
  Context alone.

  collect_pub_comptime (sigil-frontend-emp/src/resolve/mod.rs) then decides what a
  `use x.*` glob actually injects: pub_comptime_name covers the seven kinds above
  PLUS `pub context`, and pub_struct_data_name additionally injects a TYPE-ONLY stub
  for a `pub data NAME: T` whose `T` is a single bare named type.

  Exported(helper) = {const, struct, enum, bitfield, newtype, comptime fn,
                      named vars overlay}          (visibility irrelevant — forced)
                   | {pub context}
                   | {pub data with a single-segment named type annotation}

  `equ`, `proc`, `data` without a bare named type, private `context`, and the
  `vars <region> { }` REGION form (name is None) are all invisible to a consumer.

Coverage note, so the load-bearing parts stay legible: on the CURRENT twelve
helpers only the `pub context` rule and the module-id lookup change the answer —
without them irq/z80_bus read as exporting nothing, and two helpers resolve to no
file at all. The `vars`/`data` rules and the block-comment stripping match sigil's
semantics but are inert here (no helper contains either form). Item-position
gating is NOT inert: `implement` blocks bind contract values with depth-1 `const`
lines, and helper modules gain comptime-fn bodies as the set grows.

Usage:
    python3 tools/emp_helper_closure.py [AEON_DIR] [NATIVE_RS]
"""

from __future__ import annotations

import os
import re
import sys
from typing import Dict, List, Optional, Set, Tuple

# One declaration in ITEM position: optional `pub`, optional `comptime`, the kind
# keyword, the name. `fn` only ever appears as `comptime fn` (the parser reaches
# comptime_fn_decl solely through `at_kw("comptime")`), so the qualifier is optional
# here purely for tolerance — a bare `fn` item does not parse in `.emp`.
ITEM_RE = re.compile(
    r"^\s*(pub\s+)?(?:comptime\s+)?"
    r"(const|fn|struct|enum|bitfield|newtype|vars|context|data)\s+"
    r"([A-Za-z_][A-Za-z0-9_]*)"
    r"(.*)$"
)

SECTION_RE = re.compile(r"^\s*section\s+[A-Za-z_]")

# `vars Name: region { .. }` is the OVERLAY form (AST name = Some) and is injected;
# `vars region_name { .. }` is the REGION form (name = None) and is not. The colon
# after the identifier is the only thing that tells them apart.
VARS_OVERLAY_RE = re.compile(r"^\s*:")

# `pub data NAME: T = ..` qualifies only when `T` is Type::Named with ONE segment —
# so a plain identifier, and never `[u16; 4]`, `*Sst`, `(a, b)`, `fixed<..>`,
# `T where LO..HI`, or a dotted `engine.structs.Sec`.
DATA_NAMED_TY_RE = re.compile(r"^\s*:\s*([A-Za-z_][A-Za-z0-9_]*)\s*(=|$)")

# Kinds publicize_helper_comptime force-publicizes: visibility in the source is
# irrelevant, they are all exported.
FORCED_KINDS = frozenset({"const", "fn", "struct", "enum", "bitfield", "newtype"})

HELPERS_RE = re.compile(
    r"const\s+COMPTIME_HELPERS\s*:\s*&\[&str\]\s*=\s*&\[(.*?)\];", re.DOTALL
)

NATIVE_RS_TAIL = os.path.join("crates", "sigil-harness", "src", "native.rs")

MODULE_DECL_RE = re.compile(r"^\s*module\s+([A-Za-z_][A-Za-z0-9_.]*)\s*$")


def strip_comments(src: str) -> str:
    """Blank out `//` line comments, `/* */` block comments and string bodies.

    Line count and column count are preserved so the caller can still scan
    line-by-line, and blanking string BODIES (rather than deleting them) keeps a
    brace inside a message literal from desyncing the depth scan. `.emp` block
    comments do not nest (lexer.rs scans to the first `*/`).
    """
    out = []
    i, n = 0, len(src)
    while i < n:
        c = src[i]
        if c == "/" and i + 1 < n and src[i + 1] == "/":
            while i < n and src[i] != "\n":
                out.append(" ")
                i += 1
        elif c == "/" and i + 1 < n and src[i + 1] == "*":
            out.append("  ")
            i += 2
            while i + 1 < n and not (src[i] == "*" and src[i + 1] == "/"):
                out.append("\n" if src[i] == "\n" else " ")
                i += 1
            if i + 1 < n:
                out.append("  ")
                i += 2
            else:  # unterminated — consume the rest
                out.extend(" " for _ in range(n - i))
                i = n
        elif c == '"':
            out.append('"')
            i += 1
            while i < n and src[i] != '"':
                if src[i] == "\\" and i + 1 < n:
                    out.append("  ")
                    i += 2
                    continue
                out.append("\n" if src[i] == "\n" else " ")
                i += 1
            if i < n:
                out.append('"')
                i += 1
        else:
            out.append(c)
            i += 1
    return "".join(out)


def _exported_name(line: str) -> Optional[str]:
    """The name this item-position line exports to a `use <module>.*` consumer."""
    m = ITEM_RE.match(line)
    if not m:
        return None
    is_pub, kind, name, rest = bool(m.group(1)), m.group(2), m.group(3), m.group(4)
    if kind in FORCED_KINDS:
        return name
    if kind == "vars":
        return name if VARS_OVERLAY_RE.match(rest) else None
    if kind == "context":
        return name if is_pub else None
    if kind == "data":
        return name if is_pub and DATA_NAMED_TY_RE.match(rest) else None
    return None


def comptime_items(path: str) -> Set[str]:
    """Every name `use <this module>.*` injects, after force-publicization.

    Item position is brace depth 0, plus depth 1 inside a `section` body (sigil
    recurses exactly one level; nested sections are a parse error). Anything deeper
    is a fn body, a struct body or an enum body and exports nothing.
    """
    with open(path, "r", encoding="utf-8") as fh:
        src = strip_comments(fh.read())

    names: Set[str] = set()
    depth = 0
    section_depth: Optional[int] = None

    for line in src.split("\n"):
        at_item = depth == 0 or depth == section_depth
        if at_item:
            name = _exported_name(line)
            if name is not None:
                names.add(name)
            elif SECTION_RE.match(line):
                section_depth = depth + 1
        depth += line.count("{") - line.count("}")
        if depth < 0:
            raise ValueError(f"{path}: unbalanced `}}` — brace scan desynced")
        if section_depth is not None and depth < section_depth:
            section_depth = None

    if depth != 0:
        raise ValueError(f"{path}: {depth} unclosed `{{` — brace scan desynced")
    return names


def helper_ids_from_native(native_rs: str) -> List[str]:
    """The COMPTIME_HELPERS list, read from sigil rather than duplicated here."""
    with open(native_rs, "r", encoding="utf-8") as fh:
        src = fh.read()
    m = HELPERS_RE.search(src)
    if not m:
        raise SystemExit(f"{native_rs}: could not find `const COMPTIME_HELPERS`")
    body = re.sub(r"//[^\n]*", "", m.group(1))
    return re.findall(r'"([a-z0-9_.]+)"', body)


def default_native_rs(aeon: str) -> str:
    """Locate the sigil checkout PAIRED with this aeon checkout.

    A parcel edits aeon and sigil together in matching worktrees, so
    `<root>/aeon/.worktrees/NAME` must read `<root>/sigil/.worktrees/NAME` rather
    than sigil master, which may be a merge behind on the helper list.
    """
    aeon = os.path.abspath(aeon)
    candidates: List[str] = []
    parts = aeon.split(os.sep)
    if len(parts) >= 3 and parts[-2] == ".worktrees":
        root = os.sep.join(parts[:-3])
        candidates.append(os.path.join(root, "sigil", ".worktrees", parts[-1]))
        candidates.append(os.path.join(root, "sigil"))
    candidates.append(os.path.join(os.path.dirname(aeon), "sigil"))
    for base in candidates:
        path = os.path.join(base, NATIVE_RS_TAIL)
        if os.path.exists(path):
            return path
    return os.path.join(candidates[-1], NATIVE_RS_TAIL)


def module_index(aeon: str) -> Dict[str, str]:
    """Map every `.emp` module id to its file, read from the `module` declaration.

    The id is NOT the path: `engine.types` lives at `engine/system/types.emp`, so a
    dots-to-slashes mapping would report two of the twelve helpers as missing.
    """
    index: Dict[str, str] = {}
    for dirpath, dirnames, filenames in os.walk(aeon):
        dirnames[:] = [d for d in dirnames if d not in (".git", ".worktrees")]
        for fn in filenames:
            if not fn.endswith(".emp"):
                continue
            path = os.path.join(dirpath, fn)
            with open(path, "r", encoding="utf-8") as fh:
                # Comment-stripped, so a `module x.y` line inside the file's header
                # block comment cannot claim the id ahead of the real declaration.
                src = strip_comments(fh.read())
            for line in src.split("\n"):
                m = MODULE_DECL_RE.match(line)
                if m:
                    prior = index.get(m.group(1))
                    if prior and prior != path:
                        raise SystemExit(
                            f"module id {m.group(1)} declared twice: {prior}, {path}"
                        )
                    index[m.group(1)] = path
                    break
    return index


def find_collisions(closures: Dict[str, Set[str]]) -> List[Tuple[str, List[str]]]:
    """Names exported by more than one helper, sorted for a stable report."""
    owners: Dict[str, List[str]] = {}
    for mod in sorted(closures):
        for name in closures[mod]:
            owners.setdefault(name, []).append(mod)
    return sorted((n, m) for n, m in owners.items() if len(m) > 1)


def main(argv: List[str]) -> int:
    aeon = argv[0] if argv else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    native_rs = argv[1] if len(argv) > 1 else default_native_rs(aeon)
    helpers = helper_ids_from_native(native_rs)
    index = module_index(aeon)
    closures: Dict[str, Set[str]] = {}
    missing: List[str] = []
    for mod in helpers:
        path = index.get(mod)
        if path is None:
            missing.append(mod)
            continue
        closures[mod] = comptime_items(path)
    if missing:
        print("COMPTIME_HELPERS names a module no .emp file declares:")
        for mod in missing:
            print(f"  {mod}")
        return 2
    collisions = find_collisions(closures)
    if collisions:
        print(f"{len(collisions)} name collision(s) across {len(helpers)} helpers:")
        for name, mods in collisions:
            print(f"  {name}: {', '.join(mods)}")
        print("The LAST helper in COMPTIME_HELPERS order wins; a module that was")
        print("degrading one of these names to a label reference changes bytes.")
        return 1
    total = sum(len(v) for v in closures.values())
    print(f"emp_helper_closure: OK — {total} names across {len(helpers)} helpers, no collisions")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
