#!/usr/bin/env python3
"""keepalive_surface -- what the keepalive lane's ONE declared invocation per tool reaches,
and what it does not.

WHY THIS EXISTS. `tools/keepalive_lane.py` runs ~35 bus instruments nightly, each on
exactly one invocation from `tools/keepalive_manifest.toml`. That establishes each tool
can still reach a verdict. It does NOT establish that the tool's other arms can. The
population contains a worked example of the difference: `ramp_authored_witness.run_arm5`
was dead for weeks behind four healthy-looking arms, and the only reason the lane caught
it is that the dead arm happened to be on the DEFAULT path.

The same tree also contains the inverse. `floor_hscroll_dump` and `floor_capture` were
sampling mid-transition ONLY on their `--extra-right-frames` arm; their default path was
clean and measured clean. A default-only lane cannot see that one at all.

So "defaults are a blind spot" is too coarse to act on. This module measures, per tool,
WHICH option values the declared invocation leaves untouched and whether those options
gate CODE THAT THEN NEVER EXECUTES -- as opposed to merely resizing code that runs every
night anyway. Only the first kind can rot silently.

=============================================================================
HOW THE CLASSIFICATION IS DERIVED -- FROM THE PARSER AND THE CODE, NOT THE PROSE
=============================================================================
Docstrings in this tree have repeatedly been wrong about their own tools' subjects, so
nothing here reads one. For each tool the lane wires:

  1. Parse the file. Collect every `add_argument(...)` -- its option strings, `dest`,
     `default`, `choices`, `action`.
  2. Mark the options the manifest's declared argv actually sets.
  3. For each option it does NOT set, TAINT the value from `args.<dest>` forward:
     through assignments, through operators, and through call arguments into the callee's
     parameter by position or keyword. This hop matters and is not optional --
     `--extra-right-frames` is read as `a.extra_right_frames`, passed positionally into
     `run(rom, lst, extra)`, and gated there as `if extra:`. An `if args.X` scan sees
     NOTHING for the one flag in this tree with a known defect on it.
  4. Measure the `if` / `while` / `for` bodies those tainted names gate.

Then classify by WHETHER THE DEFAULT VALUE MAKES THE BLOCK RUN:

  UNREACHED BODY        the option gates a block and its default is falsy (None, 0, "",
                        or an absent store_true). The block does not execute on the
                        nightly, ever. This is the surface that can rot silently.
  SUBJECT SELECTOR      the option carries `choices`; the default picks one and the lane
                        reaches only that one. Rotting surface, counted in SUBJECTS.
  REACHED, resized only the option gates a block but its default is truthy, so the block
                        runs nightly at one size. A wrong size is a measurement question,
                        not a dead-code question.
  PURE PARAMETER        the value never reaches a branch test at all. It flows into
                        arithmetic or into a bus call. Nothing here can be dead.

⚠ THREE THINGS THIS DOES NOT SEE, and they are named rather than rounded away:
  * ENVIRONMENT VARIABLES. Three wired tools take input from `os.environ`, which no
    argparse scan can reach. `--env` reports them.
  * SUBJECT TOOLS. `transition_window_probe` takes another tool's PATH and runs it under
    a shim. Its subject surface is the whole population, not an enumerable flag domain.
  * COMPUTED DEFAULTS. A `default=` that is not a literal is reported as `<expr>` and
    classified on its syntactic shape; five of them are paths or module constants derived
    at import, all non-empty, and each was read by hand on 2026-09-19.

⚠ AND THIS FILE IS NOT A GATE. It reports; it does not fail. The one thing about it that
  IS checked is in `tools/test_keepalive_surface.py`, which pins the control case: the
  flag with a KNOWN defect on it must land in the rotting class. A classifier that cannot
  classify the one case whose answer is known is not evidence about the other 89.
"""
import argparse
import ast
import json
import os
import re
import sys
import tomllib

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(TOOLS_DIR)
sys.path.insert(0, TOOLS_DIR)
import keepalive_lane as lane  # noqa: E402  -- for `tool_of`, the row-key grammar's one reader

DEFAULT_MANIFEST = os.path.join(TOOLS_DIR, "keepalive_manifest.toml")

NO_DEFAULT = "<none>"          # add_argument had no `default=` kwarg at all
UNREACHED = "UNREACHED BODY"
SELECTOR = "SUBJECT SELECTOR"
RESIZED = "REACHED, resized only"
PARAM = "PURE PARAMETER"

ENV_RE = re.compile(
    r'(?:os\.environ(?:\.get)?\s*[\(\[]\s*|os\.getenv\s*\(\s*)["\']([A-Za-z_][A-Za-z0-9_]*)["\']'
)


def _lit(node):
    try:
        return ast.literal_eval(node)
    except Exception:
        return "<expr>"


# A `choices=` domain is the one `add_argument` kwarg whose VALUE a reader needs, and it
# is also the one most often built rather than written: `choices=WITNESSES + ("c4a2t",
# "all") + tuple(AB)` is not a literal, so `_lit` returns the string "<expr>" -- which is
# ITERABLE, and reporting an unreached domain of ['<','e','x','p','r','>'] is worse than
# reporting nothing, because it looks like an answer. Measured 2026-09-19: 6 options in
# tools/ build their choices this way. So the domain gets a small bounded evaluator over
# the module's own top-level literal constants, and anything it cannot resolve is marked
# UNRESOLVED rather than rendered.
_CHOICE_CALLS = {"tuple": tuple, "list": list, "sorted": sorted, "frozenset": frozenset,
                 "set": set}
CHOICES_UNRESOLVED = "<unresolved>"


def _module_consts(tree):
    """Top-level NAME = <literal> bindings, the only namespace the evaluator may use."""
    out = {}
    for n in tree.body:
        if isinstance(n, ast.Assign) and len(n.targets) == 1 \
                and isinstance(n.targets[0], ast.Name):
            try:
                out[n.targets[0].id] = ast.literal_eval(n.value)
            except Exception:
                pass
    return out


def _eval_choices(node, consts):
    """Resolve a `choices=` expression, or return CHOICES_UNRESOLVED.

    Deliberately tiny: literals, names bound to literals at module level, `+` between
    sequences, and the five sequence constructors above. Nothing is imported and nothing
    is executed from the file -- a scanner that ran a tool's module to read its parser
    would be booting emulators to answer a static question.
    """
    def ev(n):
        if isinstance(n, ast.Name):
            if n.id in consts:
                return consts[n.id]
            raise ValueError(n.id)
        if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Add):
            a, b = ev(n.left), ev(n.right)
            return list(a) + list(b)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) \
                and n.func.id in _CHOICE_CALLS and len(n.args) == 1 and not n.keywords:
            return list(_CHOICE_CALLS[n.func.id](ev(n.args[0])))
        return ast.literal_eval(n)
    try:
        v = ev(node)
    except Exception:
        return CHOICES_UNRESOLVED
    return list(v) if isinstance(v, (list, tuple, set, frozenset)) else CHOICES_UNRESOLVED


def parse_options(tree):
    """Every add_argument in the file, as {names, dest, default, choices, action}."""
    out = []
    consts = _module_consts(tree)
    for n in ast.walk(tree):
        if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr == "add_argument"):
            continue
        names = [a.value for a in n.args if isinstance(a, ast.Constant)
                 and isinstance(a.value, str)]
        kw = {k.arg: _lit(k.value) for k in n.keywords if k.arg}
        if not names:
            continue
        for k in n.keywords:
            if k.arg == "choices":
                kw["choices"] = _eval_choices(k.value, consts)
        dest = kw.get("dest")
        if dest is None:
            longs = [x for x in names if x.startswith("--")]
            head = longs[0] if longs else names[0]
            dest = head.lstrip("-").replace("-", "_")
        out.append({
            "names": names, "dest": dest,
            "default": kw["default"] if "default" in kw else NO_DEFAULT,
            "choices": kw.get("choices"), "action": kw.get("action"),
            "positional": not names[0].startswith("-"),
        })
    return out


def _funcs(tree):
    out = {}
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out.setdefault(n.name, []).append(n)
    return out


def _owner_map(tree):
    """node -> name of the nearest enclosing function ('<module>' at top level)."""
    infn = {tree: "<module>"}

    def rec(node, cur):
        for ch in ast.iter_child_nodes(node):
            infn[ch] = cur
            rec(ch, ch.name if isinstance(ch, (ast.FunctionDef, ast.AsyncFunctionDef)) else cur)
    rec(tree, "<module>")
    return infn


def _parents(tree):
    p = {}
    for n in ast.walk(tree):
        for ch in ast.iter_child_nodes(n):
            p[ch] = n
    return p


def argv_namespace_names(tree):
    """The local names bound to a `parse_args()` result."""
    names = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign) and isinstance(n.value, ast.Call):
            f = n.value.func
            if isinstance(f, ast.Attribute) and f.attr == "parse_args":
                for t in n.targets:
                    if isinstance(t, ast.Name):
                        names.add(t.id)
    return names or {"a", "args", "opts", "ns"}


def taint(tree, dest, ns_names):
    """(function, local) pairs carrying the value of args.<dest>.

    The call-argument hop is the load-bearing part: see the module docstring.
    """
    fns, par, infn = _funcs(tree), _parents(tree), _owner_map(tree)
    tainted, seen = set(), set()
    queue = [n for n in ast.walk(tree)
             if isinstance(n, ast.Attribute) and n.attr == dest
             and isinstance(n.value, ast.Name) and n.value.id in ns_names]

    def step(node):
        p = par.get(node)
        if p is None:
            return []
        here = infn.get(node, "<module>")
        if isinstance(p, ast.Assign):
            got = []
            for tgt in p.targets:
                for e in (tgt.elts if isinstance(tgt, ast.Tuple) else [tgt]):
                    if isinstance(e, ast.Name):
                        got.append(("local", here, e.id))
            return got
        if isinstance(p, (ast.BinOp, ast.UnaryOp, ast.BoolOp, ast.Compare, ast.IfExp,
                          ast.keyword)):
            return [("expr", p, None)]
        if isinstance(p, ast.Call):
            callee = p.func.id if isinstance(p.func, ast.Name) else \
                (p.func.attr if isinstance(p.func, ast.Attribute) else None)
            got = []
            for fd in fns.get(callee, []):
                params = [a.arg for a in fd.args.posonlyargs] + [a.arg for a in fd.args.args]
                for i, a in enumerate(p.args):
                    if a is node and i < len(params):
                        got.append(("local", fd.name, params[i]))
                for kw in p.keywords:
                    if kw.value is node and kw.arg:
                        got.append(("local", fd.name, kw.arg))
            return got or [("expr", p, None)]
        return []

    while queue:
        node = queue.pop()
        if id(node) in seen:
            continue
        seen.add(id(node))
        for kind, a, b in step(node):
            if kind == "expr":
                queue.append(a)
                continue
            key = (a, b)
            if key in tainted:
                continue
            tainted.add(key)
            scopes = fns.get(a, []) if a != "<module>" else [tree]
            for fd in scopes:
                for n2 in ast.walk(fd):
                    if (isinstance(n2, ast.Name) and n2.id == b
                            and isinstance(n2.ctx, ast.Load)
                            and infn.get(n2, "<module>") == a):
                        queue.append(n2)
    return tainted, infn


def gated(tree, tainted, infn, dest, ns_names):
    """Lines and count of the branch bodies those tainted names control."""
    lines, blocks = set(), 0

    def hot(test, fn):
        for n in ast.walk(test):
            if isinstance(n, ast.Name) and (fn, n.id) in tainted:
                return True
            if (isinstance(n, ast.Attribute) and n.attr == dest
                    and isinstance(n.value, ast.Name) and n.value.id in ns_names):
                return True
        return False

    for n in ast.walk(tree):
        fn = infn.get(n, "<module>")
        body = None
        if isinstance(n, ast.If) and hot(n.test, fn):
            body = list(n.body) + list(n.orelse)
        elif isinstance(n, ast.While) and hot(n.test, fn):
            body = list(n.body)
        elif isinstance(n, (ast.For, ast.AsyncFor)) and hot(n.iter, fn):
            body = list(n.body)
        if body:
            blocks += 1
            for s in body:
                lines.update(range(s.lineno, getattr(s, "end_lineno", s.lineno) + 1))
    return len(lines), blocks


def default_disables(opt):
    """Does this option's DEFAULT value leave the block it gates unexecuted?

    store_true with an explicit `default=True` is the case that makes this a function
    rather than a truthiness test: pcc_identity_probe's `--press-b` is store_true AND
    default True, so its block runs nightly and the flag can only ever be a no-op.
    """
    d, a = opt["default"], opt["action"]
    if a == "store_true":
        return d is not True
    if a == "store_false":
        return False                      # dest defaults True; the block runs
    if d == NO_DEFAULT:
        return True                       # argparse fills None
    return d is None or d == 0 or d == "" or d is False


def classify(opt, blocks):
    if opt["choices"]:
        return SELECTOR
    if blocks == 0:
        return PARAM
    return UNREACHED if default_disables(opt) else RESIZED


def measure(repo=REPO, manifest=DEFAULT_MANIFEST):
    wired = tomllib.load(open(manifest, "rb"))["wired"]
    # A manifest row is an INVOCATION and a tool may have several (`tool.py#arm-label`).
    # The question this file asks -- "what surface does the lane never reach" -- is a
    # question about the TOOL, so the rows of one tool are folded here and the flags any
    # of them sets count as set. Measuring per row instead would report a flag as
    # unreached on the arm that does not set it while another arm sets it every night.
    by_tool = {}
    for row in sorted(wired):
        by_tool.setdefault(lane.tool_of(row), []).append(
            [str(x) for x in wired[row].get("args", [])])
    rows = []
    for name in sorted(by_tool):
        rows.extend(_scan_tool(repo, name, by_tool[name]))
    return rows


def _scan_tool(repo, name, argvs, extra=None):
    """The per-tool option scan, shared by the wired and unwired halves.

    `argvs` is every declared invocation of this tool; `[[]]` means "nothing is set",
    which is the unwired case. `extra` is merged into every row this tool produces, so
    the unwired half can carry its per-TOOL facts (required set, runnability) on rows
    that are otherwise per-OPTION.
    """
    rows = []
    # A single-iteration loop, not an `if`: the body below uses `continue` to mean "this
    # option needs no row", which was a skip to the next TOOL when this was the body of
    # measure()'s loop and must stay a skip here.
    for _once in (None,):
        declared = argvs[0] if len(argvs) == 1 else [a for argv in argvs for a in argv]
        set_flags = {x for argv in argvs for x in argv if x.startswith("-")}
        path = os.path.join(repo, "tools", name)
        src = open(path, encoding="utf-8", errors="replace").read()
        tree = ast.parse(src)
        ns = argv_namespace_names(tree)
        opts = parse_options(tree)
        env = sorted(set(ENV_RE.findall(src)))
        if not opts:
            rows.append({"tool": name, "declared": declared, "env": env,
                         "flag": "(no argparse)", "dest": None, "class": None,
                         "default": None, "choices": None,
                         "gated_lines": 0, "gated_blocks": 0})
            continue
        for o in opts:
            is_set = any(n in set_flags for n in o["names"]) or \
                (o["positional"] and declared and not declared[0].startswith("-"))
            if is_set and not o["choices"]:
                continue                  # the manifest sets it; nothing left unreached
            if is_set and o["choices"]:
                # SET, but a choices domain is only ever one-reached-at-a-time. The
                # unreached choices are the surface, and they are counted in SUBJECTS.
                chosen = [d for d in declared if d in o["choices"]]
                rows.append({
                    "tool": name, "declared": declared, "env": env,
                    "flag": "/".join(o["names"]), "dest": o["dest"],
                    "default": o["default"], "choices": o["choices"],
                    "action": o["action"], "reached_choices": chosen,
                    "unreached_choices": [c for c in o["choices"] if c not in chosen],
                    "gated_lines": 0, "gated_blocks": 0, "class": SELECTOR,
                })
                continue
            t, infn = taint(tree, o["dest"], ns)
            gl, gb = gated(tree, t, infn, o["dest"], ns)
            row = {
                "tool": name, "declared": declared, "env": env,
                "flag": "/".join(o["names"]), "dest": o["dest"],
                "default": o["default"], "choices": o["choices"],
                "action": o["action"],
                "gated_lines": gl, "gated_blocks": gb,
                "class": classify(o, gb),
            }
            if o["choices"]:
                # UNSET selector. `classify` already calls it SUBJECT SELECTOR, but the
                # domain is the whole point of that class and a row that omits it forces
                # every reader back to the source. Reached is empty BY CONSTRUCTION here
                # -- that is what "the manifest sets nothing" means -- so the pair is
                # carried in the same shape the set-selector branch above uses, and not
                # in a second one a consumer would have to learn.
                row["reached_choices"] = [d for d in declared if d in o["choices"]]
                row["unreached_choices"] = [c for c in o["choices"]
                                            if c not in row["reached_choices"]]
            rows.append(row)
    if extra:
        for r in rows:
            r.update(extra)
    return rows


# =====================================================================================
#  THE UNWIRED HALF -- the 50 tools the lane does NOT run
# =====================================================================================
#  WHY THIS IS NOT JUST `measure()` OVER THE OTHER TABLE, and the distinction is the
#  whole point. For a WIRED tool the question is "which options does the one declared
#  invocation leave untouched", and the answer is a proper subset. For an UNWIRED tool
#  nothing is set, so every option is untouched -- a true statement that carries no
#  information and would let this module report a big number about nothing.
#
#  What a reader actually needs from an unwired row is the price and the shape of a
#  wiring, so that is what is derived:
#
#    required            what argparse REFUSES without. This is the `args = [...]` a
#                        manifest row would have to spell, and it turns the manifest's
#                        A/B prose ("requires --before-rom/--after-rom from two different
#                        builds") into a fact read off the parser. It is validated in
#                        tools/test_keepalive_surface.py against an argparse exit-2
#                        message measured off this tree, not against itself.
#    needs_args          argparse would exit 2 on an empty argv.
#    bare_exit_is_free   the trap the manifest names for display_ab_gate, generalised: a
#                        parser that demands nothing can exit 0 having measured nothing,
#                        and from the outside that is indistinguishable from a pass.
#                        ⚠ IT IS A FLAG, NOT A VERDICT. It says an exit status alone is
#                        not evidence for this row; it does NOT say the tool is vacuous.
#    runnable            has a `__main__` block, i.e. is a program at all. Two manifest
#                        rows are excluded as "not an instrument"; this is that claim,
#                        derived, and it separates them (aether_bytes is not runnable,
#                        aether_instance is).
#
#  ⚠ AND THE OPTION CLASSES BELOW MEAN SOMETHING WEAKER HERE. On a wired tool UNREACHED
#  BODY means "the nightly never executes this block". On an unwired tool the nightly
#  executes NO block of the file, so the classes describe only what a bare wiring would
#  STILL leave dead after it went green. Do not add the two halves' UNREACHED totals
#  together: they are counts of different things.
# =====================================================================================

def required_args(tree):
    """Option strings argparse would refuse an empty argv for.

    Positionals count only when they demand at least one value: `nargs='*'` and
    `nargs='?'` are satisfied by nothing, and `sfx_audition`'s `sounds` is the case that
    makes that distinction load-bearing -- it takes `nargs='*'`, so a bare run parses
    cleanly and returns 0 without ever reaching the bus.
    """
    out = []
    for n in ast.walk(tree):
        if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr == "add_argument"):
            continue
        names = [a.value for a in n.args
                 if isinstance(a, ast.Constant) and isinstance(a.value, str)]
        if not names:
            continue
        kw = {k.arg: _lit(k.value) for k in n.keywords if k.arg}
        positional = not names[0].startswith("-")
        if positional:
            if kw.get("nargs") in ("*", "?") or kw.get("nargs") == 0:
                continue
            out.append(names[0])
        elif kw.get("required") is True:
            out.append(names[0])
    return out


def measure_unwired(repo=REPO, manifest=DEFAULT_MANIFEST):
    """One or more rows per `[not_wired]` entry, carrying the reason beside the derivation."""
    not_wired = tomllib.load(open(manifest, "rb"))["not_wired"]
    rows = []
    for name in sorted(not_wired):
        path = os.path.join(repo, "tools", name)
        src = open(path, encoding="utf-8", errors="replace").read()
        tree = ast.parse(src)
        req = required_args(tree)
        runnable = bool(re.search(r'^if __name__\s*==', src, re.M))
        has_parser = bool(parse_options(tree))
        # ⚠ UNDETERMINED IS A THIRD ANSWER, NOT A FALSY SECOND ONE. `required_args` reads
        # argparse; a tool that parses `sys.argv` by hand has no argparse to read, so
        # "does a bare argv parse" is a question this module did not ask, not a question
        # it answered no to. Both no-argparse PROGRAMS in the [not_wired] table dispatch
        # by hand (`cache_hold_probe` off a MODES table, `reels_witness` off `sys.argv[1:]`)
        # and tools/test_cli_dispatch_refuses.py already records the first of them giving
        # usage + exit 1 on a missing mode -- the exact opposite of the free green a
        # truthiness answer would have asserted here. `runnable` stays determinable either
        # way, which is what separates aether_bytes (no parser AND no __main__: False)
        # from these two (None).
        determinable = has_parser or not runnable
        extra = {
            "wired": False,
            "reason": not_wired[name],
            "required": req,
            "needs_args": bool(req) if determinable else None,
            "bare_exit_is_free": ((not req) and runnable) if determinable else None,
            "runnable": runnable,
        }
        rows.extend(_scan_tool(repo, name, [[]], extra=extra))
    return rows


def _report_unwired(args):
    """The unwired half of the report. See the block comment above `required_args`.

    ⚠ READ THE TOTALS NARROWLY, and this is a prohibition rather than a caveat: NOTHING
    here is a coverage claim. Every one of these tools is run by this lane ZERO times.
    The counts say what a wiring would COST and what a bare wiring would STILL leave
    unexecuted; they do not say any line of any of these files has been executed by
    anything. A reader who adds an `UNREACHED BODY` total from this report to the one
    from the wired report has added two counts of different things.
    """
    rows = measure_unwired(args.repo, args.manifest)
    if args.json:
        with open(args.json, "w") as fh:
            json.dump(rows, fh, indent=1, default=str)
    by = {}
    for r in rows:
        by.setdefault(r["tool"], []).append(r)
    print(f"KEEPALIVE UNWIRED SURFACE -- {len(by)} tool(s) the lane runs ZERO times.")
    print("  Nothing below is coverage. The lane executes no line of any of these files.")
    und = sum(1 for t in by if by[t][0].get("bare_exit_is_free") is None
              and by[t][0].get("runnable"))
    print(f"  {sum(1 for t in by if by[t][0].get('needs_args'))} need arguments "
          f"(a manifest row must spell them); "
          f"{sum(1 for t in by if by[t][0].get('bare_exit_is_free'))} would accept an "
          f"empty argv, where an exit status alone is not evidence; "
          f"{sum(1 for t in by if not by[t][0].get('runnable'))} are not programs at all; "
          f"{und} UNDETERMINED -- they parse sys.argv by hand and argparse says nothing "
          f"about them.")
    print()
    hdr = (f"  {'tool':34s} {'opts':>4s} {'UNR':>4s} {'SEL':>4s} {'RSZ':>4s} {'PAR':>4s}"
           f"  required / notes")
    print(hdr)
    print("  " + "-" * (len(hdr) - 2))
    for name in sorted(by):
        rs = by[name]
        head = rs[0]
        n = {k: sum(1 for r in rs if r["class"] == k)
             for k in (UNREACHED, SELECTOR, RESIZED, PARAM)}
        opts = sum(1 for r in rs if r["dest"])
        notes = []
        if not head.get("runnable"):
            notes.append("NOT A PROGRAM (no __main__)")
        elif head.get("bare_exit_is_free") is None:
            notes.append("UNDETERMINED: hand-rolled sys.argv, no parser to read")
        if head.get("required"):
            notes.append(" ".join(head["required"]))
        elif head.get("bare_exit_is_free"):
            notes.append("bare argv parses -- exit status alone is not evidence")
        if head.get("env"):
            notes.append("env=" + ",".join(head["env"]))
        print(f"  {name[:34]:34s} {opts:4d} {n[UNREACHED]:4d} {n[SELECTOR]:4d} "
              f"{n[RESIZED]:4d} {n[PARAM]:4d}  {'; '.join(notes)}")
    sel = [r for r in rows if r["class"] == SELECTOR]
    if sel:
        print("\n### SUBJECT SELECTORS -- whole domains, none of them reached")
        for r in sorted(sel, key=lambda r: r["tool"]):
            print(f"   {r['tool'][:32]:33s} {r['flag'][:22]:23s} "
                  f"UNREACHED={r.get('unreached_choices')}")
    print("\n### THE REASON EACH ROW CARRIES, beside what was derived above")
    print("   (the reason is the CLAIM; the columns are the measurement)")
    for name in sorted(by):
        print(f"   {name}\n      {by[name][0]['reason']}")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", default=REPO)
    ap.add_argument("--manifest", default=DEFAULT_MANIFEST)
    ap.add_argument("--json", default=None, help="write the rows here")
    ap.add_argument("--env", action="store_true", help="only the env-var surface")
    ap.add_argument("--unwired", action="store_true",
                    help="the 50 tools the lane does NOT run: reason beside derivation")
    args = ap.parse_args(argv)

    if args.unwired:
        return _report_unwired(args)

    rows = measure(args.repo, args.manifest)
    if args.json:
        with open(args.json, "w") as fh:
            json.dump(rows, fh, indent=1, default=str)

    if args.env:
        print("WIRED TOOLS TAKING INPUT FROM THE ENVIRONMENT (no argparse scan sees these)")
        for name in sorted({r["tool"] for r in rows if r["env"]}):
            env = next(r["env"] for r in rows if r["tool"] == name)
            print(f"  {name:38s} {env}")
        return 0

    tools = sorted({r["tool"] for r in rows})
    noargs = sorted({r["tool"] for r in rows if r["flag"] == "(no argparse)"})
    _w = tomllib.load(open(args.manifest, "rb"))["wired"]
    wired_n = len({lane.tool_of(r) for r in _w})
    print(f"KEEPALIVE SURFACE -- {wired_n} wired tool(s) over {len(_w)} declared "
          f"invocation(s); {len(tools)} of them have surface "
          f"the declared invocation does not set, over "
          f"{sum(1 for r in rows if r['dest'])} option(s)")
    print(f"  tools with no argparse at all: {len(noargs)}  ({', '.join(noargs)})")
    for k in (UNREACHED, SELECTOR, RESIZED, PARAM):
        sel = sorted([r for r in rows if r["class"] == k],
                     key=lambda r: (-r["gated_lines"], r["tool"]))
        print(f"\n### {k}  -- {len(sel)} option(s), {sum(r['gated_lines'] for r in sel)} gated line(s)")
        for r in sel:
            d = str(r["default"])[:14]
            if k == SELECTOR:
                print(f"   {r['tool'][:32]:33s} {r['flag'][:22]:23s} "
                      f"reached={r.get('reached_choices')} "
                      f"UNREACHED={r.get('unreached_choices')}")
            else:
                print(f"   {r['tool'][:32]:33s} {r['flag'][:22]:23s} default={d:15s} "
                      f"lines={r['gated_lines']:3d}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
