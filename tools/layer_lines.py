#!/usr/bin/env python3
"""layer_lines.py — the ONE bake path for an act's layer-line table, and its authored source.

WHAT A LAYER LINE IS (docs/ENGINE_ARCHITECTURE.md §4.7 "Collision layers"). The engine's only
layer-switch mechanism since LINES-EVERYWHERE (owner ruling 2026-09-26, docs/decisions.jsonl
S2CLIP-PLANE-SWITCH): a vertical or horizontal line in the level, with an extent along itself,
that moves a player between collision plane A and plane B, and sets his sprite priority, when
he crosses it. `Player_LayerLines` (games/sonic4/player/player_common.emp) runs every act's
table every frame with Sonic 2's Obj03 rule. Painted crossover marks, the mechanism lines
replaced, are gone (docs/LOOP_CROSSOVER_ENCODING.md is SUPERSEDED).

ONE TABLE FORMAT, ONE BAKE PATH, TWO SOURCES. A line reaches the ROM from either:
  * a Sonic 2 donor's Obj03 objects (tools/s2_layer_lines.py `lines()`, a clip act), or
  * an AUTHORED FILE, `games/<game>/data/editor/<zone>/act<N>/layer_lines.json` (this file's
    `authored_lines()`), which aurora will later write with a line tool.
Both produce the same LINE records, and everything after that is here: `rows()` cuts and
sorts them into `LayerLine` rows, `rows_text()` spells the rows as `.emp` literals, and
`module_text()` writes a canonical act's generated module. The clip bake
(tools/clip_rom_bake.py) calls `rows_text()` for its own two emissions.

THE AUTHORED FILE (format "aeon-layer-lines", version 1). A closed JSON document: any key not
named below is refused, so a misspelled field cannot be silently ignored.

    {
      "format": "aeon-layer-lines",
      "version": 1,
      "notes": "free text (optional)",
      "lines": [
        {
          "id": "loop0_floor_west",          unique within the file; names the line in errors
          "orientation": "vertical",         "vertical" | "horizontal"
          "x": 1144, "y": 544,               act pixels: a vertical line's X and the TOP of
                                             its extent; a horizontal line's Y and the LEFT
          "length": 32,                      the extent, px, half-open: [y, y + length) for a
                                             vertical line, [x, x + length) for a horizontal
          "forward":  {"path": "B", "priority": "high"},   crossing RIGHT (vertical) or DOWN
          "backward": {"path": "A", "priority": "low"},    crossing LEFT (vertical) or UP
          "grounded_only": false,            true: does nothing while the player is airborne
          "notes": "free text (optional)"
        }
      ]
    }

`path` is "A", "B" or "keep" (leave the plane, set the priority only). A line keeps the path
in both directions or in neither, because the row format has one keep bit
(`LL_KEEP_PATH`, Obj03's x-flip): a line with "keep" on one side only is refused. `priority`
is "high" or "low" and is ALWAYS written on a crossing (Obj03 clears the bit and sets it again
only for "high"). Lines with equal keys run in FILE ORDER, and the last write of a frame
stands.

THE REFUSALS (every message leads with its tag and names the line):
  A1  the document is not a JSON object of format "aeon-layer-lines" version 1, or carries a
      key this format does not define (closed, like aurora's regions document)
  A2  a line field is missing, of the wrong type, or out of its value set
  A3  a line keeps the path on one side only
  A4  two lines share an id
  L4  (rows()) a row outside the act, or a coordinate the runtime's signed word compares or
      the sentinels could not order
"""
import json
import os
import re

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONSTANTS_EMP = os.path.join(REPO, "engine", "system", "constants.emp")

FORMAT = "aeon-layer-lines"
VERSION = 1

#: The engine's names for the row format. Read, never restated: the table is data the engine
#: consumes, so the consumer's constants are the authority.
LL_NAMES = ("LL_KEEP_PATH", "LL_GROUNDED", "LL_HORIZONTAL", "LL_FWD_B", "LL_BACK_B",
            "LL_FWD_HI", "LL_BACK_HI", "LL_SEG_W", "LL_KEY_BEFORE", "LL_KEY_AFTER")

_DOC_KEYS = {"format", "version", "notes", "lines"}
_LINE_KEYS = {"id", "orientation", "x", "y", "length", "forward", "backward",
              "grounded_only", "notes"}
_SIDE_KEYS = {"path", "priority"}


class LayerLineError(Exception):
    """An act's layer lines cannot be baked; the message leads with its rule tag."""


def engine_constants(path=CONSTANTS_EMP):
    """{name: int} for every LL_* the row format uses, parsed from engine/system/constants.emp."""
    with open(path) as fh:
        text = fh.read()
    out = {}
    for name in LL_NAMES:
        m = re.search(rf"^pub const {name}\s*=\s*(\$[0-9A-Fa-f]+|\d+)\b", text, re.M)
        if not m:
            raise LayerLineError(f"L5 engine/system/constants.emp no longer defines {name}")
        v = m.group(1)
        out[name] = int(v[1:], 16) if v.startswith("$") else int(v)
    return out


# ---------------------------------------------------------------------------
# The authored source
# ---------------------------------------------------------------------------

def _is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def authored_lines(path, consts=None):
    """The LINE records of an authored layer_lines.json, in file order (see the module
    header for the format and the refusals). The record shape is the one
    tools/s2_layer_lines.lines() produces, so rows() takes either."""
    c = consts or engine_constants()
    rel = os.path.relpath(path, REPO)
    try:
        with open(path) as fh:
            doc = json.load(fh)
    except json.JSONDecodeError as exc:
        raise LayerLineError(f"A1 {rel} is not JSON: {exc}") from None
    if not isinstance(doc, dict):
        raise LayerLineError(f"A1 {rel} is not a JSON object")
    extra = sorted(set(doc) - _DOC_KEYS)
    if extra:
        raise LayerLineError(f"A1 {rel} carries key(s) this format does not define: {extra}")
    if doc.get("format") != FORMAT or doc.get("version") != VERSION:
        raise LayerLineError(f"A1 {rel} is format {doc.get('format')!r} version "
                             f"{doc.get('version')!r}, not {FORMAT!r} version {VERSION}")
    lines = doc.get("lines")
    if not isinstance(lines, list):
        raise LayerLineError(f"A1 {rel}: `lines` is not a list")
    out, seen = [], set()
    for n, ln in enumerate(lines):
        where = f"{rel} line {n}"
        if not isinstance(ln, dict):
            raise LayerLineError(f"A2 {where} is not an object")
        if isinstance(ln.get("id"), str):
            where = f"{rel} line {ln['id']!r}"
        extra = sorted(set(ln) - _LINE_KEYS)
        if extra:
            raise LayerLineError(f"A1 {where} carries key(s) this format does not define: {extra}")
        missing = sorted({"id", "orientation", "x", "y", "length", "forward", "backward"}
                         - set(ln))
        if missing:
            raise LayerLineError(f"A2 {where} is missing {missing}")
        if not isinstance(ln["id"], str) or not ln["id"]:
            raise LayerLineError(f"A2 {where}: `id` is not a non-empty string")
        if ln["id"] in seen:
            raise LayerLineError(f"A4 {where}: two lines share this id")
        seen.add(ln["id"])
        if ln["orientation"] not in ("vertical", "horizontal"):
            raise LayerLineError(f"A2 {where}: `orientation` is {ln['orientation']!r}, not "
                                 f"'vertical' or 'horizontal'")
        for k in ("x", "y", "length"):
            if not _is_int(ln[k]):
                raise LayerLineError(f"A2 {where}: `{k}` is not an integer")
        if ln["length"] <= 0:
            raise LayerLineError(f"A2 {where}: `length` is {ln['length']}, not positive")
        grounded = ln.get("grounded_only", False)
        if not isinstance(grounded, bool):
            raise LayerLineError(f"A2 {where}: `grounded_only` is not true or false")
        sides = {}
        for side in ("forward", "backward"):
            s = ln[side]
            if not isinstance(s, dict) or set(s) != _SIDE_KEYS:
                raise LayerLineError(f"A2 {where}: `{side}` is not exactly "
                                     f"{{\"path\": ..., \"priority\": ...}}")
            if s["path"] not in ("A", "B", "keep"):
                raise LayerLineError(f"A2 {where}: `{side}.path` is {s['path']!r}, not "
                                     f"'A', 'B' or 'keep'")
            if s["priority"] not in ("high", "low"):
                raise LayerLineError(f"A2 {where}: `{side}.priority` is {s['priority']!r}, "
                                     f"not 'high' or 'low'")
            sides[side] = s
        keep = [sides[s]["path"] == "keep" for s in ("forward", "backward")]
        if keep[0] != keep[1]:
            raise LayerLineError(
                f"A3 {where} keeps the path on one side only; the row format has one keep bit "
                f"(LL_KEEP_PATH) for both directions. Use 'keep' on both sides or on neither.")
        horiz = ln["orientation"] == "horizontal"
        f = 0
        if keep[0]:
            f |= 1 << c["LL_KEEP_PATH"]
        if grounded:
            f |= 1 << c["LL_GROUNDED"]
        if horiz:
            f |= 1 << c["LL_HORIZONTAL"]
        if sides["forward"]["path"] == "B":
            f |= 1 << c["LL_FWD_B"]
        if sides["backward"]["path"] == "B":
            f |= 1 << c["LL_BACK_B"]
        if sides["forward"]["priority"] == "high":
            f |= 1 << c["LL_FWD_HI"]
        if sides["backward"]["priority"] == "high":
            f |= 1 << c["LL_BACK_HI"]
        lo = ln["x"] if horiz else ln["y"]
        out.append({"order": len(out), "horizontal": horiz, "x": ln["x"], "y": ln["y"],
                    "lo": lo, "hi": lo + ln["length"], "flags": f,
                    "where": f"{os.path.basename(path)} {ln['id']}"})
    return out


# ---------------------------------------------------------------------------
# Lines -> rows (both sources)
# ---------------------------------------------------------------------------

def rows(line_list, act_w, act_h, consts=None):
    """The ROM rows, sorted by (key, source order), WITHOUT the sentinels. Each row is a dict:
    key / a / b / flags as the `LayerLine` fields, plus `why` and `order`.

    A vertical line is one row keyed by its X, extent [lo, hi) in Y. A horizontal line is cut
    into segments no wider than LL_SEG_W, each keyed by its left X, with ll_a its Y and ll_b the
    segment's right X: every row's X interest then starts within LL_SEG_W of where it can
    matter, which is what lets the runtime window stay LL_SEG_W plus one frame's step wide. The
    segments partition the line, so a crossing fires exactly one of them."""
    c = consts or engine_constants()
    seg = c["LL_SEG_W"]
    out = []
    for ln in line_list:
        x_lo, x_hi = (ln["lo"], ln["hi"]) if ln["horizontal"] else (ln["x"], ln["x"] + 1)
        y_lo, y_hi = (ln["y"], ln["y"] + 1) if ln["horizontal"] else (ln["lo"], ln["hi"])
        if x_lo < 0 or y_lo < 0 or x_hi > act_w or y_hi > act_h:
            raise LayerLineError(
                f"L4 {ln['where']} lands at act x {x_lo}..{x_hi - 1}, y {y_lo}..{y_hi - 1}, "
                f"outside the {act_w} x {act_h} act")
        why = (f"{ln['where']}{' x-flipped' if ln.get('xflip') else ''} -> act "
               f"({ln['x']}, {ln['y']})")
        base = {"flags": ln["flags"], "order": ln["order"]}
        if not ln["horizontal"]:
            out.append(dict(base, key=ln["x"], a=ln["lo"], b=ln["hi"], why=why))
            continue
        x = ln["lo"]
        while x < ln["hi"]:
            x1 = min(x + seg, ln["hi"])
            out.append(dict(base, key=x, a=ln["y"], b=x1, why=f"{why}, x {x}..{x1 - 1}"))
            x = x1
    out.sort(key=lambda r: (r["key"], r["order"]))
    before, after = c["LL_KEY_BEFORE"] - 0x10000, c["LL_KEY_AFTER"]
    for r in out:
        if not (before < r["key"] < after and 0 <= r["a"] < after and 0 <= r["b"] < after):
            raise LayerLineError(
                f"L4 row {r['why']} (key {r['key']}, {r['a']}, {r['b']}) cannot be ordered "
                f"between the sentinels ({before}, {after}) by signed word compares")
    return out


def rows_text(p):
    """The table's `LayerLine` literals, sentinels included (for a generated .emp). `p` is a
    plan: {"rows": [...], "consts": {...}}."""
    c = p["consts"]
    body = [f"LayerLine{{ ll_key: ${c['LL_KEY_BEFORE']:04X}, ll_a: 0, ll_b: 0, ll_flags: 0, "
            f"ll_pad: 0 }},  // sentinel: every key is above it"]
    for r in p["rows"]:
        body.append(f"LayerLine{{ ll_key: {r['key']}, ll_a: {r['a']}, ll_b: {r['b']}, "
                    f"ll_flags: ${r['flags']:02X}, ll_pad: 0 }},  // {r['why']}")
    body.append(f"LayerLine{{ ll_key: ${c['LL_KEY_AFTER']:04X}, ll_a: 0, ll_b: 0, ll_flags: 0, "
                f"ll_pad: 0 }},  // sentinel: every key is below it")
    return "\n    ".join(body)


def plan_authored(path, act_w, act_h, consts=None):
    """{"lines", "rows", "consts"} for an authored file (rows sorted, no sentinels)."""
    c = consts or engine_constants()
    ls = authored_lines(path, c)
    return {"lines": ls, "rows": rows(ls, act_w, act_h, c), "consts": c}


# ---------------------------------------------------------------------------
# A canonical act's generated module
# ---------------------------------------------------------------------------

def module_text(p, module, const_name, source_rel):
    """The generated const-only module a canonical act's descriptor imports: the rows as
    `const_name` (sentinels included), which the descriptor both CHECKS
    (`layer_line_table_check`) and EMITS as its `pub data` table. Zero bytes of its own, like
    games/sonic4/data/generated/ojz/act1/regions.emp. An act with no lines gets an empty array,
    and the descriptor binds no table."""
    head = ("// AUTO-GENERATED by tools/layer_lines.py — DO NOT EDIT.\n"
            "//\n"
            f"// The act's layer-line rows, baked from {source_rel} (format\n"
            f"// {FORMAT} v{VERSION}; tools/layer_lines.py documents it). The descriptor checks\n"
            "// them with layer_line_table_check and emits them as the table Act.act_layer_lines\n"
            "// names; Player_LayerLines (games/sonic4/player/player_common.emp) runs it.\n"
            "// ZERO BYTES: this module declares a `const` only and is placed in no section.\n\n"
            f"module {module}\n\n")
    if not p["rows"]:
        return head + (f"// No lines are authored: the descriptor binds no table.\n"
                       f"pub const {const_name}: array = []\n")
    n = len(p["rows"]) + 2
    return head + (f"use engine.structs.{{LayerLine}}\n\n"
                   f"// {len(p['lines'])} authored line(s) -> {len(p['rows'])} row(s), between two "
                   f"sentinels.\n"
                   f"pub const {const_name}: [LayerLine; {n}] = [\n    {rows_text(p)}\n]\n")


#: The canonical acts whose descriptor imports a generated layer-line module:
#: (editor act dir, generated module path, module name, const name), all repo-relative.
CANONICAL_ACTS = (
    ("games/sonic4/data/editor/ojz/act1/layer_lines.json",
     "games/sonic4/data/generated/ojz/act1/layer_lines.emp",
     "games.sonic4.ojz_layer_lines_act1", "OJZ_ACT1_LAYER_LINE_ROWS"),
)


def act_size(game_root=os.path.join(REPO, "games", "sonic4")):
    """(act_w, act_h) px of OJZ act 1, from the generated act grid the descriptor also reads."""
    text = open(os.path.join(game_root, "data", "generated", "ojz", "act1", "act_grid.emp")).read()
    vals = {}
    for name in ("OJZ_ACT_GRID_W", "OJZ_ACT_GRID_H"):
        m = re.search(rf"^pub const {name}\s*=\s*(\d+)", text, re.M)
        if not m:
            raise LayerLineError(f"L5 act_grid.emp no longer defines {name}")
        vals[name] = int(m.group(1))
    sec = 1 << int(re.search(r"^pub const SECTION_SIZE_SHIFT\s*=\s*(\d+)",
                             open(CONSTANTS_EMP).read(), re.M).group(1))
    return vals["OJZ_ACT_GRID_W"] * sec, vals["OJZ_ACT_GRID_H"] * sec


def emit(check=False):
    """Write (or, with check, compare) every canonical act's generated module. Returns the
    list of (generated path, row count) or raises LayerLineError."""
    done = []
    w, h = act_size()
    for src, gen, module, const in CANONICAL_ACTS:
        src_abs, gen_abs = os.path.join(REPO, src), os.path.join(REPO, gen)
        if os.path.exists(src_abs):
            p = plan_authored(src_abs, w, h)
        else:
            p = {"lines": [], "rows": [], "consts": engine_constants()}
        text = module_text(p, module, const, src)
        if check:
            have = open(gen_abs).read() if os.path.exists(gen_abs) else None
            if have != text:
                raise LayerLineError(f"L6 {gen} is not what {src} bakes to; run "
                                     f"tools/regenerate-level.sh")
        else:
            with open(gen_abs, "w") as fh:
                fh.write(text)
        done.append((gen, len(p["rows"])))
    return done


USAGE = """Usage:
    python3 tools/layer_lines.py emit    # bake every canonical act's layer_lines.json into its
                                         # generated module (tools/regenerate-level.sh runs it)
    python3 tools/layer_lines.py check   # refuse a generated module its source no longer bakes to"""


def _mode(check):
    def run(rest):
        if rest:
            print(f"ERROR: unknown argument {rest[0]!r}")
            print(USAGE)
            return 1
        try:
            for gen, n in emit(check=check):
                print(f"layer_lines: {gen}: {n} row(s) {'match' if check else 'written'}")
        except LayerLineError as exc:
            print(f"layer_lines: REFUSED: {exc}")
            return 1
        return 0
    return run


_mode_emit = _mode(False)
_mode_check = _mode(True)

# ONE list of legal modes, and it is the dispatch table (LS-15d shape,
# tools/test_cli_dispatch_refuses.py). `emit` WRITES tracked generated modules the engine
# compiles, so an unknown mode must never reach it; `check` writes nothing but must not run
# unasked either.
MODES = {
    "emit": _mode_emit,
    "check": _mode_check,
}


def main(argv=None):
    import sys
    args = list(sys.argv[1:] if argv is None else argv)
    handler = MODES.get(args[0] if args else None)
    if handler is None:
        print(USAGE)
        sys.exit(1)
    return handler(args[1:])


if __name__ == "__main__":
    import sys
    sys.exit(main())
