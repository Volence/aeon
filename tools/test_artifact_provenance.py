"""The shared provenance primitive, tools/artifact_provenance.py (LS-1a step 2).

RUNNER: build.sh's PRE-build tool-suite lane (`pytest tools -m "not needs_build"`),
build-fatal, every shape. Nothing here reads a build artifact out of the working tree:
every pair is BUILT by the installed assembler into a directory this file owns
(tools/provenance_fixtures.py, plain demo, ~0.75 s each), so no DIGEST line is hand-typed
and the fixtures move with the emitter.

WHAT IS ASSERTED, each arm with a control that the same fixture is fresh unmutated:
  * a real pair is FRESH against the tree it was built from, and against a mirror of its
    read set (the control every content arm below stands on);
  * THE LS-1a CASE: content stale, mtime fresh -> NOT FRESH, naming the file;
  * a `touch` of everything moves nothing (the digest is content, not time);
  * a truncated section, a mispaired ROM (identical CRC, other file), a ROM rewritten
    after the build, a listing with NO section, a doctored READ row, an older assembler,
    no assembler, a wrong shape under a canonical name, a module that appeared, an
    unknown `tree=` word -> NOT FRESH, each naming its row;
  * `tree=` is reported and never gated: a known word other than the build's is fresh;
  * `built_after` survives as an additional condition (decision (b));
  * the CLI's exit codes are 0 and 2 and nothing else.
"""

import os
import subprocess
import sys
import time

import pytest

TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS)

import artifact_provenance as ap  # noqa: E402
import provenance_fixtures as pf  # noqa: E402


def _build(out_dir, **kw):
    try:
        return pf.build_demo(str(out_dir), **kw)
    except pf.NoAssembler as e:
        pytest.fail(str(e))


@pytest.fixture(scope="module")
def real(tmp_path_factory):
    """One real plain-demo pair, built after `t0`."""
    d = tmp_path_factory.mktemp("provenance_real")
    t0 = int(time.time())
    rom, lst = _build(d)
    return {"t0": t0, "rom": rom, "lst": lst}


def _verdict_text(v):
    return v.render("t") + "\n" + "\n".join(v.problems)


def _source_emp_row(lst):
    rows = [r for r in pf.aeon_rows(lst) if r.endswith(".emp")]
    assert rows, "the demo build read no .emp source; the fixture cannot test a source edit"
    return rows[len(rows) // 2]


# ---- the controls ------------------------------------------------------------------

def test_a_real_pair_is_fresh_against_the_tree_it_was_built_from(real):
    v = ap.check_pair(real["rom"], real["lst"], built_after=real["t0"])
    assert v.fresh and v.code == ap.FRESH, _verdict_text(v)
    assert "provenance FRESH" in v.render("t")


def test_a_mirror_of_the_read_set_is_fresh(real, tmp_path):
    """The control every content arm stands on: a copy of exactly the files the build
    read is an aeon root the listing is fresh against."""
    root = tmp_path / "root"
    n = len(pf.mirror(real["lst"], str(root)))
    assert n > 100, n
    v = ap.check_pair(real["rom"], real["lst"], built_after=real["t0"], root=str(root))
    assert v.fresh, _verdict_text(v)


# ---- LS-1a itself ------------------------------------------------------------------

def test_content_stale_with_a_fresh_mtime_is_not_fresh_and_names_the_file(real, tmp_path):
    """The case the old rule could not see. Every mtime is AFTER the build began, so
    `mtime >= built_after` alone passes; one file the build read has changed since."""
    root = tmp_path / "root"
    pf.mirror(real["lst"], str(root))
    victim = _source_emp_row(real["lst"])
    with open(root / victim, "ab") as f:
        f.write(b"\n// edited after the build\n")
    now = time.time()
    for p in (real["rom"], real["lst"]):
        os.utime(p, (now, now))
    assert all(os.stat(p).st_mtime >= real["t0"] for p in (real["rom"], real["lst"])), \
        "the arm needs mtimes the old rule would call fresh"
    v = ap.check_pair(real["rom"], real["lst"], built_after=real["t0"], root=str(root))
    assert v.code == ap.UNMEASURABLE, _verdict_text(v)
    named = [p for p in v.problems if victim in p]
    assert named and "DIGEST-READ" in named[0], _verdict_text(v)
    assert victim in v.render("some_gate"), "the printed verdict must name the file"


def test_a_touch_of_everything_moves_nothing(real, tmp_path):
    root = tmp_path / "root"
    rows = pf.mirror(real["lst"], str(root))
    later = time.time() + 3600
    for rel in rows:
        os.utime(root / rel, (later, later))
    v = ap.check_pair(real["rom"], real["lst"], built_after=real["t0"], root=str(root))
    assert v.fresh, _verdict_text(v)


# ---- the section's integrity -------------------------------------------------------

def test_a_truncated_section_is_not_fresh(real, tmp_path):
    with open(real["lst"], "rb") as f:
        raw = f.read()
    start = raw.index(b"\nDIGEST-READ ")
    end = raw.index(b"\nDIGEST-END\n")
    cut = tmp_path / "cut.lst"
    cut.write_bytes(raw[:start + (end - start) // 2])      # mid-row, mid-section
    v = ap.check_pair(real["rom"], str(cut))
    assert v.code == ap.UNMEASURABLE and "TRUNCATED" in _verdict_text(v), _verdict_text(v)

    no_end = tmp_path / "no_end.lst"
    pf.rewrite(real["lst"], str(no_end), lambda t: t.replace("DIGEST-END\n", "", 1))
    v = ap.check_pair(real["rom"], str(no_end))
    assert v.code == ap.UNMEASURABLE and "DIGEST-END" in _verdict_text(v), _verdict_text(v)


def test_a_listing_with_no_digest_section_is_never_fresh(real, tmp_path):
    """Decision (c): no section is loud whatever the mtime, with or without a threshold."""
    bare = tmp_path / "bare.lst"
    pf.rewrite(real["lst"], str(bare), lambda t: "".join(
        ln for ln in t.splitlines(keepends=True) if not ln.startswith("DIGEST-")))
    for built_after in (None, real["t0"]):
        v = ap.check_pair(real["rom"], str(bare), built_after=built_after)
        assert v.code == ap.UNMEASURABLE, _verdict_text(v)
        assert "NO `DIGEST-` section" in _verdict_text(v), _verdict_text(v)


def test_a_doctored_read_row_breaks_the_aggregate(real, tmp_path):
    doc = tmp_path / "doc.lst"

    def edit(t):
        i = t.index("DIGEST-READ crc=") + len("DIGEST-READ crc=")
        flip = "0" if t[i] != "0" else "1"
        return t[:i] + flip + t[i + 1:]
    pf.rewrite(real["lst"], str(doc), edit)
    v = ap.check_pair(real["rom"], str(doc))
    assert v.code == ap.UNMEASURABLE and "does not match its own READ rows" in _verdict_text(v)


# ---- the ROM row ---------------------------------------------------------------------

def test_a_mispaired_rom_is_caught_by_its_path_even_with_an_identical_crc(real, tmp_path):
    """Two builds of one shape write byte-identical ROMs, so the CRC cannot tell them
    apart: the path is what says the listing belongs to the OTHER file."""
    other_rom, _ = _build(tmp_path / "other")
    with open(other_rom, "rb") as a, open(real["rom"], "rb") as b:
        assert a.read() == b.read(), "the control needs two identical ROMs"
    v = ap.check_pair(other_rom, real["lst"])
    assert v.code == ap.UNMEASURABLE, _verdict_text(v)
    assert any(p.startswith("DIGEST-ROM names ") and "another ROM file" in p
               for p in v.problems), _verdict_text(v)


def test_a_rom_rewritten_after_the_build_is_not_fresh(tmp_path):
    rom, lst = _build(tmp_path / "own")
    with open(rom, "r+b") as f:
        f.seek(0x200)
        b = f.read(1)
        f.seek(0x200)
        f.write(bytes([b[0] ^ 0xFF]))
    v = ap.check_pair(rom, lst)
    assert v.code == ap.UNMEASURABLE, _verdict_text(v)
    assert any(p.startswith("DIGEST-ROM says crc=") for p in v.problems), _verdict_text(v)


def test_an_absent_file_is_not_fresh(real, tmp_path):
    v = ap.check_pair(str(tmp_path / "nothing.bin"), real["lst"])
    assert v.code == ap.UNMEASURABLE and "does not exist" in _verdict_text(v)


# ---- the assembler and the shape (decision (a)) ------------------------------------

def _stub_assembler(tmp_path, revision):
    source = ap.assembler_identity(pf.sigil())[2]
    stub = tmp_path / "sigil-stub"
    stub.write_text("#!/bin/sh\necho 'sigil 0.1.0 (stub)'\n"
                    f"echo '  revision:  {revision}'\n"
                    "echo '  tree:      clean at capture'\n"
                    f"echo '  source:    {source}'\n")
    stub.chmod(0o755)
    return str(stub)


def test_a_listing_from_another_assembler_is_not_fresh(real, tmp_path):
    stub = _stub_assembler(tmp_path, "0" * 40)
    v = ap.check_pair(real["rom"], real["lst"], assembler=stub)
    assert v.code == ap.UNMEASURABLE, _verdict_text(v)
    assert any(p.startswith("DIGEST-ASSEMBLER revision=") for p in v.problems), _verdict_text(v)
    # control: the same stub reporting the listing's own revision is fresh
    rev = ap.read_digest(real["lst"])["assembler"]["revision"]
    assert ap.check_pair(real["rom"], real["lst"], assembler=_stub_assembler(tmp_path, rev)).fresh


def test_no_assembler_to_ask_is_not_fresh(real, monkeypatch):
    monkeypatch.delenv("SIGIL_BUILD", raising=False)
    v = ap.check_pair(real["rom"], real["lst"])
    assert v.code == ap.UNMEASURABLE and "SIGIL_BUILD is unset" in _verdict_text(v)


def test_a_wrong_shape_under_a_canonical_name_is_not_fresh(real, tmp_path):
    """The plain shape, built for real under the DEBUG artifact's name."""
    rom, lst = _build(tmp_path / "mis", rom_name="demo.debug.bin")
    v = ap.check_pair(rom, lst)
    assert v.code == ap.UNMEASURABLE, _verdict_text(v)
    assert any("DIGEST-SHAPE debug=0" in p for p in v.problems), _verdict_text(v)
    # an explicit expectation wins over the name, and a matching one is fresh
    assert ap.check_pair(rom, lst, expect_debug=False).fresh
    assert not ap.check_pair(real["rom"], real["lst"], expect_debug=True).fresh
    assert not ap.check_pair(real["rom"], real["lst"], expect_game="sonic4").fresh


def test_a_non_canonical_name_is_reported_unchecked_not_guessed(tmp_path):
    rom, lst = _build(tmp_path / "odd", rom_name="whatever.bin")
    v = ap.check_pair(rom, lst)
    assert v.fresh, _verdict_text(v)
    assert any("shape not checked" in n for n in v.notes), v.notes


# ---- tree= (reported, fail-closed on an unknown word, never gated) -----------------

def test_tree_is_reported_never_gated_and_an_unknown_word_fails_closed(real, tmp_path):
    word = ap.read_digest(real["lst"])["assembler"]["tree"]
    other = "dirty" if word != "dirty" else "clean"
    known = tmp_path / "known.lst"
    pf.rewrite(real["lst"], str(known), lambda t: t.replace(f" tree={word}\n", f" tree={other}\n", 1))
    v = ap.check_pair(real["rom"], str(known))
    assert v.fresh, _verdict_text(v)
    assert any(f"tree={other}" in n for n in v.notes), v.notes

    unknown = tmp_path / "unknown.lst"
    pf.rewrite(real["lst"], str(unknown), lambda t: t.replace(f" tree={word}\n", " tree=pristine\n", 1))
    v = ap.check_pair(real["rom"], str(unknown))
    assert v.code == ap.UNMEASURABLE and "tree=pristine" in _verdict_text(v), _verdict_text(v)


# ---- the scan --------------------------------------------------------------------------

def test_a_module_that_appeared_after_the_build_moves_the_scan(real, tmp_path):
    root = tmp_path / "root"
    pf.mirror(real["lst"], str(root))
    new = root / "engine" / "zz_appeared_after_the_build.emp"
    new.write_text("module engine.zz_appeared_after_the_build in x\n")
    v = ap.check_pair(real["rom"], real["lst"], root=str(root))
    assert v.code == ap.UNMEASURABLE, _verdict_text(v)
    scan = [p for p in v.problems if p.startswith("DIGEST-SCAN")]
    assert scan and "engine/zz_appeared_after_the_build.emp" in scan[0], _verdict_text(v)


def test_the_scan_follows_the_walk_rule(tmp_path):
    """sigil's `collect_emp`: a directory symlink is not followed, a `.worktrees` child and
    a child holding a `.git` entry are not entered (the root is, whatever it holds), and a
    name counts when its Rust `extension()` is exactly `emp`."""
    r = tmp_path / "r"
    (r / "a").mkdir(parents=True)
    (r / "a" / "m.emp").write_text("")
    (r / "a" / ".emp").write_text("")            # extension() is None
    (r / "a" / "x.emp.bak").write_text("")
    (r / ".worktrees" / "w").mkdir(parents=True)
    (r / ".worktrees" / "w" / "n.emp").write_text("")
    (r / "nested").mkdir()
    (r / "nested" / ".git").write_text("gitdir: elsewhere\n")
    (r / "nested" / "n.emp").write_text("")
    (r / ".git").write_text("gitdir: elsewhere\n")   # the root is still walked
    (r / "top.emp").write_text("")
    (tmp_path / "outside").mkdir()
    (tmp_path / "outside" / "o.emp").write_text("")
    os.symlink(tmp_path / "outside", r / "linkdir")  # not followed
    os.symlink(r / "a" / "m.emp", r / "alias.emp")   # a non-directory entry: counted
    assert ap.scan_members(str(r)) == ["a/m.emp", "alias.emp", "top.emp"]


# ---- built_after survives (decision (b)) -------------------------------------------

def test_built_after_still_gates_a_fresh_digest(real):
    v = ap.check_pair(real["rom"], real["lst"], built_after=time.time() + 3600)
    assert v.code == ap.UNMEASURABLE, _verdict_text(v)
    assert sum("before this build began" in p for p in v.problems) == 2, _verdict_text(v)


# ---- the CLI ---------------------------------------------------------------------------

def test_the_cli_exits_0_fresh_and_2_otherwise(real, tmp_path):
    cli = [sys.executable, os.path.join(TOOLS, "artifact_provenance.py")]
    p = subprocess.run(cli + ["--rom", real["rom"], "--lst", real["lst"]],
                       capture_output=True, text=True)
    assert p.returncode == 0, p.stdout + p.stderr
    bare = tmp_path / "bare.lst"
    pf.rewrite(real["lst"], str(bare), lambda t: "".join(
        ln for ln in t.splitlines(keepends=True) if not ln.startswith("DIGEST-")))
    p = subprocess.run(cli + ["--rom", real["rom"], "--lst", str(bare)],
                       capture_output=True, text=True)
    assert p.returncode == 2, p.stdout + p.stderr
    assert "provenance NOT FRESH" in p.stdout
