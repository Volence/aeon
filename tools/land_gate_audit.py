"""land_gate_audit: a pytest plugin that watches which docs/ files the tests open, and
fails the session when one is read without being declared to the landing gate.

WHY THIS EXISTS. tools/land_gate.py lets a push that changes docs files skip the build
and run, instead, the tests its RULES name as reading them. That is sound only while the
table covers every docs file every test reads. A table is exactly the artifact that
drifts, so this checks it on every build, in both pytest lanes, from what the tests DO
rather than from what their source says: a Python audit hook sees every open(),
os.listdir() and os.scandir() the test process makes, however the path was built.

WHAT IT REQUIRES, for each (test file, docs path) it observes (a directory listing is
spelled with a trailing /, so only a PREFIX rule can cover it, and a file added there
later is covered too):
  * the path's class is `code` (a stamp covers it: landing_build.sh runs every test); or
  * it is `checked`, the test file is among the readers of the rules that match it, and
    the test is not marked needs_build (a push validates without building a ROM).
Anything else is a violation: the session's exit status becomes 1 and the summary names
the rule to add. A read it cannot attribute to a tools/test_*.py frame is
"<unattributed>", which no rule names, so it must be `code`.

WHAT IT CANNOT SEE: a read by a CHILD process (a test that shells out to a tool, or a
build.sh stage). tools/test_land_gate_classifier.py statically scans tracked code for
docs paths; the CTRL-3 record's inotify trace watched every process of a full landing run
and found none (docs/superpowers/notes/2026-09-13-ctrl3-land-gate.md).

Registered by tools/conftest.py. AEON_LAND_GATE_AUDIT_RECORD=<file> also writes every
observation as JSON (how RULES were derived).
"""
from __future__ import annotations

import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
import land_gate  # noqa: E402

_ROOT = land_gate.AEON
_TOOLS = land_gate.TOOLS
_DOCS = os.path.join(_ROOT, "docs")
_DOCS_SEP = _DOCS + os.sep
_EVENTS = {"open": "open", "os.listdir": "list", "os.scandir": "list"}

#: (rel path, kind, test file, nodeid)
_seen: set = set()
_needs_build: dict = {}
_active = [False]


def _who():
    f = sys._getframe(3)
    while f is not None:
        fn = f.f_code.co_filename
        if os.path.dirname(fn) == _TOOLS:
            b = os.path.basename(fn)
            if (b.startswith("test_") and b.endswith(".py")) or b == "conftest.py":
                return "tools/" + b
        f = f.f_back
    return "<unattributed>"


def _hook(event, args):
    kind = _EVENTS.get(event)
    if kind is None or not _active[0]:
        return
    try:
        _observe(kind, args)
    except Exception as e:     # an audit hook that raises breaks the operation it audits
        _seen.add(("<audit error: %s>" % type(e).__name__, "error", "<unattributed>", ""))


def _observe(kind, args):
    p = args[0] if args else None
    if p is None or isinstance(p, int):
        return
    p = os.fsdecode(os.fspath(p))
    if os.path.isabs(p):
        if "docs" not in p:
            return
        ap = os.path.normpath(p)
    elif kind == "open" and (len(args) < 2 or not isinstance(args[1], str)):
        # os.open() of a RELATIVE name. Its audit event carries no dir_fd, and the stdlib's
        # own tree walkers (shutil.rmtree / copytree) open every child by bare name relative
        # to a directory fd: resolving that against the cwd attributed a "docs" directory
        # inside a test's TEMP tree to this repository's docs/ (measured: 19 false rows
        # from tools/test_land_gate.py's rmtree, 2026-09-13). The base is unknowable, so
        # the event is not evidence either way. A test reading docs through a relative
        # os.open() is the one shape this cannot see; builtins.open() is what the suite uses.
        return
    else:
        ap = os.path.normpath(os.path.join(os.getcwd(), p))
    if ap != _DOCS and not ap.startswith(_DOCS_SEP):
        return
    if kind == "open":
        mode = args[1] if len(args) > 1 else None
        if isinstance(mode, str) and "r" not in mode and "+" not in mode:
            return                       # a write is not a read
    rel = os.path.relpath(ap, _ROOT).replace(os.sep, "/")
    if kind == "list" or os.path.isdir(ap):
        rel = rel.rstrip("/") + "/"
    cur = os.environ.get("PYTEST_CURRENT_TEST", "")
    _seen.add((rel, "list" if rel.endswith("/") else "open", _who(),
               cur.rsplit(" (", 1)[0] if cur else ""))


def violations(seen=None, needs_build=None):
    """[(path, test file, why)] for every observation the RULES do not cover."""
    seen = _seen if seen is None else seen
    needs_build = _needs_build if needs_build is None else needs_build
    out = []
    for rel, kind, who, nodeid in sorted(seen):
        if kind == "error":
            out.append((rel, who, "the audit could not read an observation: unmeasurable"))
            continue
        cls = land_gate.classify(rel)
        if cls == land_gate.CODE:
            continue
        if kind == "list" and land_gate.lister_covered(who):
            continue                     # a declared lister whose kept kind is all CODE
        if cls == land_gate.DOCS:
            out.append((rel, who, "%s a docs path no rule names, so a push changing it would "
                        "skip this test. Add a rule to tools/land_gate.py RULES: CHECKED with "
                        "%s as a reader if the test is source-only, else CODE"
                        % ("lists" if kind == "list" else "reads", who)))
            continue
        readers = land_gate.readers_for([rel])
        if who not in readers:
            out.append((rel, who, "reads a `checked` path but is not among its readers %s; "
                        "add it to a rule matching %r" % (readers, rel)))
        if needs_build.get(nodeid):
            out.append((rel, who, "the needs_build test %s reads a `checked` path; a push "
                        "cannot build a ROM to run it, so a rule must make %r CODE"
                        % (nodeid, rel)))
    return out


def pytest_configure(config):
    if not getattr(sys, "_aeon_land_gate_audit", False):
        sys.addaudithook(_hook)
        sys._aeon_land_gate_audit = True
    _seen.clear()
    _needs_build.clear()
    _active[0] = True


def pytest_collection_modifyitems(config, items):
    for it in items:
        _needs_build[it.nodeid] = it.get_closest_marker("needs_build") is not None


def pytest_sessionfinish(session, exitstatus):
    if not _active[0]:
        return
    _active[0] = False
    rec = os.environ.get("AEON_LAND_GATE_AUDIT_RECORD")
    if rec:
        with open(rec, "w") as f:
            json.dump([{"path": r, "kind": k, "test": w, "nodeid": n,
                        "needs_build": _needs_build.get(n, False)}
                       for r, k, w, n in sorted(_seen)], f, indent=1)
    v = violations()
    session.config._aeon_land_gate_violations = v
    if v and session.exitstatus in (0, 5):
        session.exitstatus = 1


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    v = getattr(config, "_aeon_land_gate_violations", None)
    if not v:
        return
    tr = terminalreporter
    tr.section("LAND GATE: docs reads tools/land_gate.py RULES do not cover (%d)" % len(v),
               red=True)
    for rel, who, why in v:
        tr.line("%s  %s: %s" % (rel, who, why), red=True)
    tr.line("A push changing one of these paths would not run the test that reads it. "
            "See tools/land_gate_audit.py.")
