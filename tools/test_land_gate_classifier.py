"""The landing gate's classifier (tools/land_gate.py RULES) covers every docs/ file the
build and its tests read, and its guard (tools/land_gate_audit.py) is live and can fail.

WHY THIS FILE EXISTS. The gate lets a push that changes only docs files skip the landing
check's builds and run, instead, the tests the RULES name as reading them. If a test or a build
stage reads a docs file the RULES do not name, a docs push can break master with no check
having run. So the classifier is a gate in its own right, and this file holds it:

  * the audit plugin is registered and armed in THIS session (so every build runs it);
  * the plugin's verdict logic, on the real RULES, flags an undeclared reader, a
    needs_build reader of a checked path, and an unnamed docs path, and passes a
    declared one;
  * END TO END, in a sandbox pytest session: a test that opens an undeclared docs file,
    or lists an undeclared docs directory, turns an otherwise green session into exit 1
    with the LAND GATE section; the same session reading only declared files exits 0
    (the control);
  * STATICALLY: every docs/ path named in tracked code (a path literal, or an
    os.path.join / `/` chain starting at "docs") is either code, or named by a rule that
    lists that file as a reader, or recorded in KNOWN below with the evidence for why no
    build stage reads it. This is the net for what the audit hook cannot see: a CHILD
    process (a build.sh stage, a tool a test shells out to);
  * the landing lane's ledger files are never code (constraint 2 of CTRL-3: the ledger
    commit after a verified merge must not force a rebuild);
  * every rule is well-formed: its readers exist and are tools/test_*.py files.

RUNNER: build.sh's pre-build tool-suite lane (source only, no marker).
"""
import ast
import os
import re
import shutil
import subprocess
import sys
import tempfile

TOOLS = os.path.dirname(os.path.abspath(__file__))
AEON = os.path.dirname(TOOLS)
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)
import land_gate  # noqa: E402
import land_gate_audit  # noqa: E402

#: (file, docs path) -> why a docs push changing that path cannot change a build or test
#: result the RULES do not already cover. Evidence: the 2026-09-13 inotify trace of a full
#: tools/landing_build.sh run, in docs/superpowers/notes/2026-09-13-ctrl3-land-gate.md.
KNOWN = {
    ("tools/decisions_conformance.py", "docs/decisions.jsonl"):
        "its default ledger path; imported in-process by tools/test_decisions_ledger.py, a "
        "declared reader of docs/decisions.jsonl, and otherwise run by hand",
    ("tools/lane_status_audit.py", "docs/lane-status.json"):
        "a hand-run audit; no build stage or test runs it (the trace saw the file opened only "
        "by test_citation_form, once per shape)",
    ("tools/lane_status_audit.py", "docs/decisions.jsonl"):
        "the same hand-run audit",
    ("tools/decisions_append.py", "docs/OVERSEER.md"):
        "the hand-run ledger write site; it names the owner's boot files in a message",
    ("tools/decisions_append.py", "docs/OVERSEER-LOG.md"):
        "the same hand-run write site",
    ("tools/fg_working_set.py", "docs/generated/vram-map-sonic4.md"):
        "read in-process by tools/test_fg_working_set.py, a declared reader of docs/generated/",
    ("tools/ramp_boundary_probe.py", "docs/benchmarks/effects-p3"):
        "an emulator probe run by hand; the directory is where it writes its PNG evidence",
    ("tools/tilt_frame_static_audit.py", "docs/witness/f7-tilt-frames.png"):
        "a witness tool run by hand, naming its own evidence image",
    ("tools/tilt_frame_static_audit.py", "docs/witness/f7-frame-09-defect.png"):
        "the same witness tool",
}

#: The gate's own files name docs paths as DATA (the RULES table, scratch-repository
#: fixtures, synthetic audit observations) and open none of this repository's docs: the
#: tests among them are watched by the audit plugin like every other test. Excluded BY
#: NAME, not by pattern. Found by the red-first control run: the scan enumerates with
#: `git ls-files`, so these were invisible to it until the commit that tracked them.
GATE_OWN = ("tools/land_gate.py", "tools/land_gate_audit.py", "tools/test_land_gate.py",
            "tools/test_land_gate_classifier.py", "tools/test_landing_build_stamp.py")

_PATHLIT = re.compile(r"^docs(/[^\s'\"`]*)?$")
_SHTOK = re.compile(r"docs/[A-Za-z0-9_./*-]+")


def _const(n):
    return n.value if isinstance(n, ast.Constant) and isinstance(n.value, str) else None


def _py_refs(src):
    """docs paths a Python file names in executable code (docstrings and prose excluded)."""
    tree = ast.parse(src)
    docstrings = set()
    for node in ast.walk(tree):
        for st in getattr(node, "body", []) if isinstance(getattr(node, "body", None), list) else []:
            if isinstance(st, ast.Expr) and _const(st.value) is not None:
                docstrings.add(id(st.value))
    out, joined = set(), set()
    for node in ast.walk(tree):
        chains = []
        if isinstance(node, ast.Call):
            chains.append(node.args)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            chain, n = [], node
            while isinstance(n, ast.BinOp) and isinstance(n.op, ast.Div):
                chain.insert(0, n.right)
                n = n.left
            chains.append([n] + chain)
        for args in chains:
            for i, a in enumerate(args):
                v = _const(a)
                if v is None or v.rstrip("/") != "docs" or id(a) in joined:
                    continue
                joined.add(id(a))
                parts = ["docs"]
                for b in args[i + 1:]:
                    bv = _const(b)
                    if bv is None:
                        break
                    parts.append(bv.strip("/"))
                out.add("/".join(parts) + ("" if len(parts) > 1 else "/"))
    for node in ast.walk(tree):
        v = _const(node)
        if v is None or id(node) in docstrings or id(node) in joined:
            continue
        v = v.strip()
        if _PATHLIT.match(v) and v.rstrip("/") != "docs":
            out.add(v)
    return out


_STATIC_CACHE = []


def _static_refs():
    if not _STATIC_CACHE:
        _STATIC_CACHE.append(_scan_static_refs())
    return _STATIC_CACHE[0]


def _scan_static_refs():
    files = subprocess.run(["git", "-C", AEON, "ls-files", "-z"], capture_output=True,
                           check=True).stdout.decode().split("\0")
    refs = set()
    for f in files:
        if not f or f.startswith("docs/") or not (f.endswith((".py", ".sh"))) or f in GATE_OWN:
            continue
        try:
            with open(os.path.join(AEON, f), encoding="utf-8") as fh:
                src = fh.read()
        except (OSError, UnicodeDecodeError):
            continue
        if "docs" not in src:
            continue
        if f.endswith(".py"):
            found = _py_refs(src)
        else:
            found = {m.group(0).rstrip(".,;:)")
                     for line in src.splitlines() if not line.lstrip().startswith("#")
                     for m in _SHTOK.finditer(line)}
        refs |= {(f, p) for p in found}
    return refs


def test_the_audit_plugin_is_armed_in_this_session(request):
    assert request.config.pluginmanager.has_plugin("land_gate_audit"), (
        "tools/conftest.py did not register tools/land_gate_audit.py: every build now runs "
        "without the check that keeps land_gate.RULES honest")
    assert getattr(sys, "_aeon_land_gate_audit", False), "the audit hook was never added"
    assert land_gate_audit._active[0], "the audit plugin is registered but not recording"


def test_the_verdicts_on_the_real_rules():
    V = land_gate_audit.violations
    ok = {("docs/OVERSEER.md", "open", "tools/test_overseer_bound.py", "n1"),
          ("docs/superpowers/notes/x.md", "open", "tools/test_citation_form.py", "n2"),
          ("docs/witness/", "list", "tools/test_emp_helper_closure.py", "n3"),
          ("docs/", "list", "tools/conftest.py", "")}
    assert V(ok, {}) == [], V(ok, {})
    undeclared = {("docs/OVERSEER.md", "open", "tools/test_brand_new.py", "n4")}
    assert len(V(undeclared, {})) == 1
    undeclared_lister = {("docs/witness/", "list", "tools/test_brand_new.py", "n6")}
    assert len(V(undeclared_lister, {})) == 1, "an undeclared directory listing must fail"
    nb = {("docs/OVERSEER.md", "open", "tools/test_overseer_bound.py", "n5")}
    assert len(V(nb, {"n5": True})) == 1, "a needs_build reader of a checked path must fail"
    unattributed = {("docs/lane-log.jsonl", "open", "<unattributed>", "")}
    assert len(V(unattributed, {})) == 1
    err = {("<audit error: TypeError>", "error", "<unattributed>", "")}
    assert len(V(err, {})) == 1, "an unreadable observation is unmeasurable, never green"


_SANDBOX_RULES = '''RULES = (
    ("docs/declared.md", CHECKED, ("tools/test_reads.py",), "sandbox"),
)
'''

_SANDBOX_CONFTEST = '''import os, sys
def pytest_configure(config):
    here = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, here)
    import land_gate_audit
    config.pluginmanager.register(land_gate_audit, "land_gate_audit")
'''

_SANDBOX_TEST = '''import os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def test_reads():
    open(os.path.join(ROOT, "docs", "declared.md")).read()
    what = os.environ.get("SANDBOX_EXTRA")
    if what == "file":
        open(os.path.join(ROOT, "docs", "undeclared.md")).read()
    elif what == "dir":
        os.listdir(os.path.join(ROOT, "docs", "sub"))
'''


def _sandbox_session(extra):
    d = tempfile.mkdtemp(prefix="land-gate-audit-")
    try:
        os.makedirs(os.path.join(d, "tools"))
        os.makedirs(os.path.join(d, "docs", "sub"))
        for name in ("declared.md", "undeclared.md", "sub/x.md"):
            with open(os.path.join(d, "docs", name), "w") as f:
                f.write("x\n")
        with open(os.path.join(TOOLS, "land_gate.py")) as f:
            gate, n = re.subn(r"# >>> RULES.*?# <<< RULES",
                              "# >>> RULES\n" + _SANDBOX_RULES + "# <<< RULES", f.read(), flags=re.S)
        assert n == 1
        for rel, text in (("tools/land_gate.py", gate), ("tools/conftest.py", _SANDBOX_CONFTEST),
                          ("tools/test_reads.py", _SANDBOX_TEST)):
            with open(os.path.join(d, rel), "w") as f:
                f.write(text)
        shutil.copy(os.path.join(TOOLS, "land_gate_audit.py"), os.path.join(d, "tools"))
        env = {k: v for k, v in os.environ.items() if not k.startswith(("PYTEST_", "AEON_"))}
        if extra:
            env["SANDBOX_EXTRA"] = extra
        p = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
                            "tools"], cwd=d, env=env, capture_output=True, text=True, timeout=120)
        return p.returncode, p.stdout + p.stderr
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_end_to_end_an_undeclared_read_fails_a_green_session():
    rc, out = _sandbox_session(None)
    assert rc == 0 and "1 passed" in out and "LAND GATE" not in out, out    # the control
    rc, out = _sandbox_session("file")
    assert rc == 1 and "1 passed" in out, out
    assert "LAND GATE" in out and "docs/undeclared.md" in out, out
    rc, out = _sandbox_session("dir")
    assert rc == 1 and "LAND GATE" in out and "docs/sub/" in out, out


def test_every_docs_path_named_in_code_is_covered():
    unknown = []
    for f, p in sorted(_static_refs()):
        if land_gate.classify(p) == land_gate.CODE:
            continue
        if f in land_gate.readers_for([p]):
            continue
        if (f, p) in KNOWN:
            continue
        unknown.append("%s names %s" % (f, p))
    assert not unknown, (
        "tracked code names docs paths the landing gate has no verdict for:\n  %s\n"
        "If this code runs during a build (a build.sh stage, a generator, a gate, or a tool a "
        "test shells out to) and reads the path, make the path CODE in tools/land_gate.py "
        "RULES. If a source-only test reads it, add that test as a reader. If it never runs "
        "in a build, add the pair to KNOWN in this file with the evidence."
        % "\n  ".join(unknown))


def test_the_known_list_has_no_dead_entries():
    live = _static_refs()
    dead = sorted(k for k in KNOWN if k not in live)
    assert not dead, "KNOWN names references the code no longer makes: %s" % dead
    gone = [f for f in GATE_OWN if not os.path.isfile(os.path.join(AEON, f))]
    assert not gone, "GATE_OWN excludes files that no longer exist: %s" % gone


def test_the_landing_ledger_files_never_need_a_rebuild():
    """CTRL-3 constraint 2. The landing lane commits ledger and lane-log rows AFTER the
    verified merge; if one of these became CODE, that commit would change the content key
    and every landing would need a second 10-15 minute build to push its own record."""
    for p in ("docs/lens-findings.jsonl", "docs/lane-log.jsonl", "docs/decisions.jsonl",
              "docs/lane-status.json", "docs/DEFERRED_WORK.md", "docs/OVERSEER-LOG.md"):
        assert land_gate.classify(p) != land_gate.CODE, p


def test_an_emp_file_under_docs_is_code():
    """sigil's module walk takes every *.emp under the root into the build, docs/ included,
    so a docs-only push adding one is a code push. The declared listers depend on it."""
    for p in ("docs/x.emp", "docs/superpowers/notes/probe.emp"):
        assert land_gate.classify(p) == land_gate.CODE, p
    assert land_gate.classify("docs/x.emp.md") != land_gate.CODE
    for who in land_gate.LISTERS:
        assert land_gate.lister_covered(who), who


def test_every_lister_is_declared_with_its_filter():
    for who, (suffix, where) in land_gate.LISTERS.items():
        assert os.path.isfile(os.path.join(AEON, who)), who
        assert suffix.startswith(".") and where.strip(), who


def test_every_rule_is_well_formed():
    for key, cls, readers, why in land_gate.RULES:
        assert key.startswith("docs/") or re.match(r"^\*\.[A-Za-z0-9]+$", key), key
        assert cls in (land_gate.CODE, land_gate.CHECKED, land_gate.DOCS), (key, cls)
        assert why.strip(), key
        if cls == land_gate.CHECKED:
            assert readers, "a CHECKED rule with no reader validates nothing: %s" % key
        for r in readers:
            assert re.match(r"^tools/test_[A-Za-z0-9_]+\.py$", r), (key, r)
            assert os.path.isfile(os.path.join(AEON, r)), (key, r)
