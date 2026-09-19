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


def parse_options(tree):
    """Every add_argument in the file, as {names, dest, default, choices, action}."""
    out = []
    for n in ast.walk(tree):
        if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr == "add_argument"):
            continue
        names = [a.value for a in n.args if isinstance(a, ast.Constant)
                 and isinstance(a.value, str)]
        kw = {k.arg: _lit(k.value) for k in n.keywords if k.arg}
        if not names:
            continue
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
    rows = []
    for name in sorted(wired):
        spec = wired[name]
        declared = [str(x) for x in spec.get("args", [])]
        set_flags = {x for x in declared if x.startswith("-")}
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
            rows.append({
                "tool": name, "declared": declared, "env": env,
                "flag": "/".join(o["names"]), "dest": o["dest"],
                "default": o["default"], "choices": o["choices"],
                "action": o["action"],
                "gated_lines": gl, "gated_blocks": gb,
                "class": classify(o, gb),
            })
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", default=REPO)
    ap.add_argument("--manifest", default=DEFAULT_MANIFEST)
    ap.add_argument("--json", default=None, help="write the rows here")
    ap.add_argument("--env", action="store_true", help="only the env-var surface")
    args = ap.parse_args(argv)

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
    wired_n = len(tomllib.load(open(args.manifest, "rb"))["wired"])
    print(f"KEEPALIVE SURFACE -- {wired_n} wired tool(s); {len(tools)} of them have surface "
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
