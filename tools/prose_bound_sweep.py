#!/usr/bin/env python3
"""prose_bound_sweep — find a BOUND STATED IN PROSE that duplicates a live constant.

THE POPULATION AND WHY IT NEEDS ITS OWN INSTRUMENT. A number written into help text, a
refusal message, a docstring or a comment is reached by NEITHER an identifier grep nor a
quoted-key grep — the two this repo already requires running together on the standing
finding that neither is a superset of the other. Prose is a third population outside both,
and it is the one an author READS at the moment they hit the limit.

Precedent that earned it: `inject_editor_bg`'s refusal said "the limit is 12 KiB" while
enforcing 20,480 for two days after the owner raised it, and two lines further down said
the bank-placement rule keeps >= 16 KiB when the rule demands 49,152. Both found here.

WHY AN AST WALK AND NOT A REGEX OVER LINES. Python concatenates adjacent string literals
at PARSE time, so an AST walk sees a multi-line message as ONE logical string for free.
A line-based sweep sees physical lines, so a sentence whose bound word and number sit on
different lines carries neither half alone — measured: the line form found the 12 KiB and
was structurally blind to the 16 KiB three lines below it, in the same message.

A number inside an f-string `{...}` is DERIVED and is not a defect, so FormattedValue
parts are masked out and only LITERAL text is matched for numbers.

THE COST OF JOINING, measured over tools/ rather than assumed — report it when you borrow
this: joining alone took 21 sites to 158, because a whole module docstring becomes one
string and almost always contains SOME bound word and SOME number. Recall rose and
precision collapsed. The proximity window is what makes it reviewable again (82), and the
date filter takes it to the reviewable set. Recall is not free; the noise arrives with it.

Run:  python3 tools/prose_bound_sweep.py tools
      python3 tools/prose_bound_sweep.py --self-test    # the positive control
"""
import ast, re, sys, pathlib

BOUNDWORD = re.compile(
    r'\b(limit|ceiling|budget|max(?:imum)?|at most|no more than|cap(?:ped)?|'
    r'must be under|fits|allows|reserve|floor)\b', re.I)
WINDOW = 80
NUM = re.compile(
    r'(?<![\w.$])(\d{2,3}(?:,\d{3})+|\d{3,}|0x[0-9A-Fa-f]{2,}|\d+ ?(?:KiB|KB|MiB)\b)')
#: A bare 4-digit year is not a bound. 23 of 82 hits over tools/ were dates like
#: `2026-09-04` sitting near words such as "budget" — the single largest noise class.
ISO_DATE = re.compile(r'\b(19|20)\d\d-\d\d(-\d\d)?\b')


def logical_strings(tree):
    """(lineno, literal_text, full_text_with_placeholders) per string node."""
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            out.append((node.lineno, node.value, node.value))
        elif isinstance(node, ast.JoinedStr):
            lit, full = [], []
            for v in node.values:
                if isinstance(v, ast.Constant) and isinstance(v.value, str):
                    lit.append(v.value)
                    full.append(v.value)
                else:
                    full.append("")      # a derived value: masked out
            out.append((node.lineno, "".join(lit), "".join(full)))
    return out


def sweep(paths):
    hits = []
    for p in paths:
        try:
            tree = ast.parse(pathlib.Path(p).read_text())
        except Exception as e:
            print("  !! %s: %s" % (p, e), file=sys.stderr)
            continue
        seen = set()
        for lineno, lit, full in logical_strings(tree):
            if len(full) < 20:
                continue
            # PROXIMITY. Joining alone swallows whole module docstrings, which almost
            # always contain SOME bound word and SOME number: recall rises and precision
            # collapses (measured: 21 -> 158 sites over tools/). Require the number to sit
            # within WINDOW chars of a bound word, which is what "a sentence states a
            # bound" actually means. The known defect had them 55 chars apart.
            m = None
            for cand in NUM.finditer(lit):
                around = lit[max(0, cand.start() - 6):cand.end() + 6]
                if ISO_DATE.search(around):
                    continue
                lo = max(0, cand.start() - WINDOW)
                if BOUNDWORD.search(lit[lo:cand.end() + WINDOW]):
                    m = cand
                    break
            if not m:
                continue
            key = (str(p), lineno)
            if key in seen:
                continue
            seen.add(key)
            hits.append((str(p), lineno, m.group(0), " ".join(full.split())[:120]))
    return hits


SELF_TEST_SRC = '''
def f(section, ceiling):
    raise SystemExit(
        f"  The limit is the owner\'s ruled authoring budget (decision d-9, 12 KiB).\\n"
        f"  `{section}` grows into the room before the `dac_banks` anchor, which the\\n"
        f"  BANK PLACEMENT RULE in map.toml keeps at >= 16 KiB in every\\n"
        f"  shape; the ceiling is the budget INSIDE that room.\\n")

def g(ceiling):
    raise SystemExit(f"  The limit is {ceiling} B, derived, on 2026-09-04.\\n")
'''


def self_test():
    """POSITIVE CONTROL. An empty sweep and a predicate that could never match are the
    same artifact, so the instrument must be shown finding a defect of the known shape --
    INCLUDING the split-across-lines one a line-based sweep cannot see -- and NOT flagging
    the derived form. Prints its own output; asserting it ran is not the same as showing
    what it found."""
    import tempfile, os
    fd, path = tempfile.mkstemp(suffix=".py")
    os.write(fd, SELF_TEST_SRC.encode()); os.close(fd)
    try:
        hits = sweep([path])
    finally:
        os.unlink(path)
    nums = {n for _, _, n, _ in hits}
    print("self-test hits: %d" % len(hits))
    for f, i, n, s_ in hits:
        print("   [%s]  %s" % (n, s_))
    ok_same_line = "12 KiB" in nums
    ok_split     = "16 KiB" in nums
    ok_derived   = not any(n.startswith("20") and len(n) == 4 for n in nums)
    print("  same-line bound found : %s" % ok_same_line)
    print("  SPLIT-LINE bound found: %s   <- the whole reason for the AST form" % ok_split)
    print("  derived form not flagged: %s" % ok_derived)
    good = ok_same_line and ok_split and ok_derived
    print("VERDICT:", "INSTRUMENT WORKS" if good else "INSTRUMENT IS BLIND - do not trust an empty sweep")
    return 0 if good else 1


if __name__ == "__main__":
    if "--self-test" in sys.argv[1:]:
        sys.exit(self_test())
    files = []
    for a in sys.argv[1:]:
        q = pathlib.Path(a)
        files.extend(sorted(q.rglob("*.py")) if q.is_dir() else [q])
    hits = sweep(files)
    print("sites: %d" % len(hits))
    for f, i, n, s in hits:
        print("%s:%d  [%s]  %s" % (f, i, n, s))
