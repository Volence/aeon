#!/usr/bin/env python3
"""test_cli_dispatch_refuses — an unrecognised CLI mode must REFUSE, never fall through.

WHY THIS FILE EXISTS (LS-15d, 2026-09-10).

A red-first mutation in an earlier parcel rewrote committed level data. The mutation was
innocent -- `if mode == "test":` -> `if mode == "tset":` in `tools/ojz_strip_gen.py` --
and the damage came entirely from the DISPATCH SHAPE around it:

    if mode not in ("preflight", "test", "generate"):   # <- the validator
        usage; sys.exit(1)
    if mode == "test": ...; return                      # <- the dispatcher
    if mode == "preflight": ...; return
    generate()                                          # <- reached by FALLING OFF THE END

The legal-mode set is written twice, and the destructive mode is the syntactic default.
`test` passed the validator, matched no branch, and ran `generate()`, which rewrote
`bg_tiles.bin` (10242 -> 6978 B), `zone_bg.bin` (8192 -> 4096 B) and
`DONOR_PROVENANCE.json` on a machine where that data is the owner's work.

WHAT THIS FILE ASSERTS, AND WHY IT IS NOT A SUBPROCESS TEST. The obvious net -- run
`python3 tools/<tool>.py <bogus>` and assert a non-zero exit -- IS THE INCIDENT. On a
regression the bogus mode falls through to `generate()`, the generator succeeds, the
process exits 0, and the row goes red only AFTER rewriting the committed tree the row
exists to protect. A gate whose failure mode is the damage it guards against is not a
gate.

So these rows import the module and drive `main()` in-process with EVERY writing handler
monkeypatched to a tripwire that raises. A correct dispatch reaches `sys.exit(1)` before
any handler; a regressed one hits the tripwire and the row names which handler it fell
into. Either way nothing is written. The tripwire is the assertion -- it is not there to
make the test safe as a side effect, it is what turns "did it write?" into a question
this file can ask without finding out the hard way.

THE POPULATION, AND HOW IT WAS BUILT (not "the tools someone remembered"). Every
`tools/*.py` with an `if __name__ == "__main__"` block was parsed with `ast` and searched
for a comparison of an argv-derived expression against a string literal -- 27 files with a
CLI string dispatch, of which 12 hand-roll the ladder and 15 delegate to argparse
`choices=`/`add_subparsers` (which refuse an unknown value themselves, exit 2). Of the 12
hand-rolled ladders, four could not refuse an unrecognised mode:

  * `ojz_strip_gen.py`   -- fell through into `generate()`        [DESTRUCTIVE]
  * `ojz_entity_gen.py`  -- fell through into `generate()`        [DESTRUCTIVE]
  * `ojz_block_gen.py`   -- matched nothing, exited 0 silently
  * `effects_gen.py`     -- demoted to the read-only shapes report, exited 0

`ojz_entity_gen.py` was NOT among the three siblings the LS-15d row checked and cleared;
it carried the destructive shape byte-for-byte. That is the argument for keeping the
census as a test and not as a paragraph: the row's "three siblings" was a fact about one
seat's attention span, not about the tree.

The other eight ladders refuse on their own and are asserted here too, so that a future
edit cannot quietly move one of them into the fall-through class:
`collision_pipeline` (usage + exit 1), `state_ram` (unknown-arg + exit 2, and a bare
`test`-typo becomes a state-file path -> REFUSED exit 1), `sfx_transcode`,
`donor_provenance`, `decisions_conformance`, `dplc_layout` (argparse required
positionals), `s4lz` (`else: print_help; sys.exit(1)` -- the exemplar), `vgm_onsets`
(read-only, tolerant flag loop, writes only a path the caller names).

RUNNER: `build.sh:798`, the pre-build tool-suite pytest lane, build-fatal. This file is
picked up by that lane's directory sweep with no wiring. It is pure Python over committed
source, boots nothing, and costs well under a second.
"""

import ast
import importlib
import os
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
AEON = os.path.normpath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)


class _Tripwire(Exception):
    """Raised instead of running a real handler, so a fall-through cannot write."""


def _trip(name):
    def boom(*a, **kw):
        raise _Tripwire(
            "an unrecognised CLI mode DISPATCHED INTO %s(). The mode ladder fell "
            "through instead of refusing -- this is LS-15d recurring, and on the real "
            "tool it would have rewritten committed data under games/sonic4/data/."
            % name)
    return boom


def _drive(monkeypatch, module_name, argv, handlers, capsys):
    """Import *module_name*, blind every handler in *handlers*, run main(argv).

    Returns the captured stdout. Asserts SystemExit(1) -- i.e. the usage refusal.
    """
    mod = importlib.import_module(module_name)
    for h in handlers:
        assert hasattr(mod, h), (
            "%s has no attribute %r -- this test's tripwire list has drifted from the "
            "module and is no longer blinding the destructive path" % (module_name, h))
        monkeypatch.setattr(mod, h, _trip("%s.%s" % (module_name, h)))
    with pytest.raises(SystemExit) as exc:
        mod.main(argv)
    assert exc.value.code == 1, (
        "%s main(%r) exited %r; an unrecognised mode must exit 1"
        % (module_name, argv, exc.value.code))
    out = capsys.readouterr().out
    assert "Usage" in out or "usage" in out, (
        "%s refused %r without printing usage; stdout was %r"
        % (module_name, argv, out))
    return out


# ---------------------------------------------------------------------------
# The four that could not refuse. These are the rows LS-15d exists for.
# ---------------------------------------------------------------------------

#: (module, tripwired handlers). The handler lists are the WRITING entry points --
#: everything a fall-through could plausibly land in, not just the one that did.
_FIXED = [
    ("ojz_strip_gen", ["generate", "preflight", "run_tests"]),
    ("ojz_entity_gen", ["generate", "run_tests"]),
    ("ojz_block_gen", ["generate_all", "run_tests"]),
    # CTRL-3 (2026-09-13): born in the table form. `finish` writes the landing stamp and
    # `pre-push` can run tests; neither may be reachable from an unknown mode.
    ("land_gate", ["cmd_finish", "cmd_pre_push", "cmd_begin", "cmd_stamps"]),
    # M-B (2026-09-16): `report --json PATH` writes the committed evidence files under
    # docs/research/megaact-bg-streaming/. Its first form was argparse `choices=` with the
    # writing `report` path as the ladder's fall-through default; now a MODES table.
    # build_report is what `report` runs before it writes; control_ojz is `control`'s work.
    ("megaact_window_pageset", ["build_report", "control_ojz"]),
    # STITCHED-ACT-PAGE-ORDER (2026-09-16): born in the table form. `report --json PATH`
    # writes docs/research/megaact-bg-streaming/09-*.json; build_report is what it runs
    # before writing, control_presence is `control`'s work.
    ("megaact_page_order", ["build_report", "control_presence"]),
    # FG-CACHE-10-RESEARCH (2026-09-16): born in the table form. `rederive`/`sweep`/`rom`
    # with --json PATH write docs/research/megaact-bg-streaming/10-*.json; `run` is what
    # rederive and sweep execute, rom_bytes is `rom`'s work, control_ext is `control`'s.
    ("megaact_fg_cache10", ["run", "rom_bytes", "control_ext"]),
    # STITCHED-ACT-PAGE-ORDER wiring (2026-09-17): born in the table form. `check` writes
    # nothing, but it is a BUILD GATE (build.sh + regenerate-level.sh), and a fall-through
    # that reached it on a typo'd mode would print a verdict nobody asked for; `check` is
    # the handler's work.
    ("fg_page_order", ["check"]),
    # CACHE-WINDOW-HOLD-MEASURE (2026-09-17): born in the table form. `run --out PATH` boots
    # an emulator and writes the run JSON; `analyze --out PATH` writes a summary. run_probe
    # and analyze_runs are the two handlers; neither may be reachable from an unknown mode.
    ("cache_hold_probe", ["run_probe", "analyze_runs"]),
    # S2-COMPRESSED-ACT parcel 4 (2026-09-17): born in the table form. `build` OVERWRITES
    # the committed S2 collision bank under games/sonic4/data/collision/base_s2/, so an
    # unknown mode reaching it would silently rewrite tracked build inputs -- the
    # ojz_strip_gen shape of the LS-15d incident. `build` is the writing handler; `check`
    # is read-only but is the parcel's falsifiable check and must not run unasked.
    ("import_s2_collision", ["cmd_build", "cmd_check", "build"]),
    # S2-COMPRESSED-ACT parcel 6 (2026-09-17): born in the table form. `bake` OVERWRITES
    # the committed generated level tree and the ROM collision tables (it is a THROWAWAY
    # re-bake of the shipped act's slot, restored by build.sh's S2CLIP trap), so an
    # unknown mode reaching it would rewrite tracked build inputs with no trap above it
    # to put them back -- the ojz_strip_gen shape of LS-15d again. `ground` is read-only
    # but is the parcel's falsifiable check and must not run unasked.
    # Row 7 (2026-09-25) added `emit-neutral`, which OVERWRITES the committed neutral
    # games/sonic4/data/generated/ojz/act1/clip_act.emp; its handler joins the same row.
    ("clip_rom_bake", ["_mode_bake", "_mode_ground", "_mode_emit_neutral", "bake", "ground"]),
    # S2-COMPRESSED-ACT parcel 7 (2026-09-17): born in the table form. Every mode is
    # READ-ONLY -- it measures a baked tree and writes nothing -- so an unknown mode
    # reaching a handler would not lose data. It is in _FIXED anyway, for the reason the
    # tool exists: it is a `gate strict` build lane, and a lane that runs the wrong thing
    # on a typo'd mode and exits 0 is a lane that has silently stopped asking. The three
    # rows below are cheap and the alternative is a gate nobody can tell from a pass.
    ("clip_reachability", ["_mode_check", "check", "scan"]),
    # S2-COMPRESSED-ACT parcel 9 (2026-09-17): born in the table form. `emit` OVERWRITES
    # games/sonic4/data/generated/ojz/act1/act_grid.emp -- a COMMITTED file the engine
    # compiles its act grid out of -- so an unknown mode reaching it would silently re-shape
    # the act from whatever project.json says. `check` is read-only but must not run unasked.
    ("act_grid", ["_mode_emit", "_mode_check", "emit", "emit_from_project"]),
]


@pytest.mark.parametrize("module_name,handlers", _FIXED,
                         ids=[m for m, _ in _FIXED])
def test_unknown_mode_refuses(monkeypatch, capsys, module_name, handlers):
    """A mode that is not in the table exits 1 with usage and reaches NO handler."""
    _drive(monkeypatch, module_name, ["definitely-not-a-mode"], handlers, capsys)


@pytest.mark.parametrize("module_name,handlers", _FIXED,
                         ids=[m for m, _ in _FIXED])
def test_no_argument_refuses(monkeypatch, capsys, module_name, handlers):
    """The EMPTY argv is the fall-through's other doorway.

    `mode = args[0] if args else None` was already handled by the old validator, but the
    dict lookup has to reject `None` too -- and a `MODES.get(argv[0])` written without
    the emptiness guard would raise IndexError here rather than print usage.
    """
    _drive(monkeypatch, module_name, [], handlers, capsys)


@pytest.mark.parametrize("module_name,handlers", _FIXED,
                         ids=[m for m, _ in _FIXED])
def test_mode_table_is_the_validator(module_name, handlers):
    """There is ONE list of legal modes, and it is the dispatch table.

    The defect LS-15d records is not "a branch was missing" -- it is that the validator
    and the dispatcher were two lists that could disagree. This row holds the shape:
    `MODES` exists, every value is callable, and every key round-trips through the
    lookup that `main` uses. A future edit that reintroduces a separate
    `if mode not in (...)` guard does not fail here, but it has to get past the two
    rows above, which is what actually matters.
    """
    mod = importlib.import_module(module_name)
    assert hasattr(mod, "MODES"), (
        "%s lost its MODES table; the mode set is presumably duplicated again"
        % module_name)
    assert mod.MODES, "%s.MODES is empty" % module_name
    for name, fn in mod.MODES.items():
        assert isinstance(name, str) and name, "%s.MODES has a bad key %r" % (module_name, name)
        assert callable(fn), "%s.MODES[%r] is not callable" % (module_name, name)


def test_effects_gen_refuses_unknown_mode():
    """effects_gen is the one of the four that is SAFE to probe as a subprocess.

    Its fall-through was the read-only `shapes` report -- it writes nothing and exits 0 --
    so a regression here costs a wrong verdict, not a restore. That makes the subprocess
    the better instrument for it: it exercises the shipped `__main__` block, which no
    import can reach.

    WHAT THE OLD BEHAVIOUR COST, since "exit 0" reads as harmless. `build.sh:869` runs
    `effects_gen.py check` as a STRICT gate over two committed generated artifacts. With
    the old `else`, a misspelled mode printed a scene inventory and returned success --
    the gate would have gone vacuous while the build stayed green.
    """
    p = subprocess.run([sys.executable, "tools/effects_gen.py", "chekc"],
                       cwd=AEON, capture_output=True, text=True)
    assert p.returncode == 1, (
        "effects_gen.py chekc exited %d; an unrecognised mode must exit 1.\n"
        "--- stdout ---\n%s\n--- stderr ---\n%s"
        % (p.returncode, p.stdout[-2000:], p.stderr[-2000:]))
    assert "unknown mode" in p.stdout, p.stdout
    # And the modes that DO exist still work: `check` is the build's gate, and a row
    # that only proved the refusal would pass just as well against a tool that refuses
    # everything.
    q = subprocess.run([sys.executable, "tools/effects_gen.py", "check"],
                       cwd=AEON, capture_output=True, text=True)
    assert q.returncode == 0, (
        "effects_gen.py check exited %d -- the refusal guard broke a real mode.\n"
        "--- stdout ---\n%s\n--- stderr ---\n%s"
        % (q.returncode, q.stdout[-2000:], q.stderr[-2000:]))
    assert "OK — generated effects module matches its inputs" in q.stdout, q.stdout


# ---------------------------------------------------------------------------
# The ladders that already refused. Pinned so they cannot drift into the fall-through
# class unnoticed. These are SUBPROCESS rows, which is only safe because each one's
# unrecognised-mode path was MEASURED to write nothing -- that is the property being
# pinned, and it is also the licence to probe it this way.
#
# `ojz_entity_gen` is DELIBERATELY ABSENT from this list even though it now refuses.
# Its fall-through was `generate()`; a subprocess row over it would, on a regression,
# rewrite committed data before reporting. It is covered in-process above, behind the
# tripwire, and it must stay there.
# ---------------------------------------------------------------------------

#: (argv, expected exit codes, a marker that must appear in stdout+stderr).
#: The exit code alone is not the assertion -- that is this row's own lesson from
#: ojz_block_gen, whose silent exit 0 was caught only because its caller happened to
#: check a stdout marker too.
_ALREADY_REFUSING = [
    ("collision_pipeline.py", ["not-a-mode"], (1,), "Usage:"),
    ("sfx_transcode.py", ["not-a-mode"], (1,), "Usage:"),
    ("donor_provenance.py", ["not-a-mode"], (1,), "Usage:"),
    ("dplc_layout.py", ["not-a-mode"], (2,), "required"),
    ("s4lz.py", ["not-a-mode"], (2,), "invalid choice"),
    # state_ram has no mode SET at all: `argv[1]` is either the literal `test` or a
    # save-state PATH, so a typo'd `test` becomes a filename. MEASURED, not assumed --
    # it does not print a tidy REFUSED line, it dies on an unhandled FileNotFoundError
    # with a traceback and exit 1. That is loud and non-destructive, which is all this
    # row claims; it is pinned as what the tool actually does rather than tidied into
    # what it ought to do, because a marker chosen to look nice is a marker that stops
    # matching the day someone adds the try/except.
    ("state_ram.py", ["tset"], (1, 2), "No such file or directory"),
    # S2-COMPRESSED-ACT parcel 3. Both are MODES-table tools born in the fixed form: the
    # dispatch runs BEFORE any handler, so an unrecognised mode reaches no writing branch.
    # MEASURED 2026-09-17, not assumed -- `not-a-mode` on each printed usage, exited 1 and
    # left the working tree byte-identical (git status clean afterwards), which is the
    # property that licenses a subprocess row here.
    ("clip_manifest.py", ["not-a-mode"], (1,), "Usage:"),
    ("clip_act_bake.py", ["not-a-mode"], (1,), "Usage:"),
]


@pytest.mark.parametrize("tool,argv,codes,marker", _ALREADY_REFUSING,
                         ids=[t for t, _, _, _ in _ALREADY_REFUSING])
def test_sibling_ladder_still_refuses(tool, argv, codes, marker):
    p = subprocess.run([sys.executable, os.path.join("tools", tool)] + argv,
                       cwd=AEON, capture_output=True, text=True)
    both = p.stdout + p.stderr
    assert p.returncode in codes, (
        "tools/%s %s exited %d, expected one of %s.\n--- stdout ---\n%s\n"
        "--- stderr ---\n%s" % (tool, " ".join(argv), p.returncode, codes,
                                p.stdout[-2000:], p.stderr[-2000:]))
    assert marker in both, (
        "tools/%s %s exited %d but printed no %r marker; an exit status with no "
        "message is how ojz_block_gen's silent fall-through survived.\n%s"
        % (tool, " ".join(argv), p.returncode, marker, both[-2000:]))


# ---------------------------------------------------------------------------
# THE POPULATION ITSELF, RE-DERIVED ON EVERY RUN.
# ---------------------------------------------------------------------------
#
# The rows above cover the ladders that exist TODAY, and that is exactly the shape of
# hole this row exists to close. LS-15d's own defect was not in any tool -- it was in a
# SENTENCE: "three sibling tools' dispatches were checked and are fine", written by
# someone who had looked at three. A test that only knows the twelve ladders a 2026-09-10
# census found is the same sentence with a shebang. So the census runs here, from source,
# every time, and a hand-rolled CLI ladder that is not in the roster below is a FAILURE
# that names the file and asks for a verdict.

#: The detector's rule, spelled out because a population is only as trustworthy as the
#: rule that built it. A file is in the population iff it has an `if __name__ ==` block
#: AND EITHER
#:   (1) compares an ARGV-DERIVED expression against a string literal somewhere in the
#:       module (`==`, `!=`, `in`, `not in`) -- the hand-rolled ladder, or
#:   (2) defines a module-level string-keyed dict named `MODES`/`*_MODE_TABLE` -- the
#:       table form this parcel converted the destructive tools to.
#: Argparse `choices=`/`add_subparsers` files are NOT excluded -- s4lz has both, and the
#: hand-written half is the half that can fall through.
#:
#: CLAUSE (2) IS NOT DECORATION, and it was added because THIS ROW WENT RED THE FIRST
#: TIME IT RAN. With only clause (1) the detector reported that ojz_strip_gen,
#: ojz_entity_gen and ojz_block_gen had left the population -- true, and exactly wrong:
#: converting them to dict dispatch is what removed their `if mode == "..."` chains, so
#: a ladder-only detector goes BLIND on precisely the three files it most needs to
#: watch, and it does so at the moment they are fixed. A population rule that loses
#: members when they are repaired cannot notice them being un-repaired.
_ARGV_SUBJECTS = ("mode", "cmd")


def _argv_derived(src):
    s = src.strip()
    return (s.startswith("sys.argv") or s.startswith("argv") or s.startswith("args[")
            or s in _ARGV_SUBJECTS
            or s in ("args.command", "args.mode", "args.cmd", "args.subcommand"))


def _is_mode_table(node):
    """Clause (2): a module-level `MODES = {"name": handler, ...}` with string keys."""
    if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Dict):
        return False
    names = [t.id for t in node.targets if isinstance(t, ast.Name)]
    if not any(n == "MODES" or n.endswith("MODE_TABLE") for n in names):
        return False
    keys = node.value.keys
    return bool(keys) and all(
        isinstance(k, ast.Constant) and isinstance(k.value, str) for k in keys)


def _dispatch_files():
    found = set()
    for fn in sorted(os.listdir(HERE)):
        if not fn.endswith(".py"):
            continue
        src = open(os.path.join(HERE, fn), encoding="utf-8").read()
        if "if __name__ ==" not in src:
            continue
        try:
            tree = ast.parse(src)
        except SyntaxError:  # pragma: no cover - a syntax error is another lane's job
            continue
        if any(_is_mode_table(n) for n in tree.body):
            found.add(fn)
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Compare) or len(node.ops) != 1:
                continue
            op, left, right = node.ops[0], node.left, node.comparators[0]
            lits = False
            if isinstance(op, (ast.Eq, ast.NotEq)):
                if isinstance(right, ast.Constant) and isinstance(right.value, str):
                    lits = True
                elif isinstance(left, ast.Constant) and isinstance(left.value, str):
                    lits, left = True, right
            elif isinstance(op, (ast.In, ast.NotIn)) and isinstance(
                    right, (ast.Tuple, ast.List, ast.Set)):
                lits = any(isinstance(e, ast.Constant) and isinstance(e.value, str)
                           for e in right.elts)
            if lits:
                try:
                    subject = ast.unparse(left)
                except Exception:  # pragma: no cover
                    continue
                if _argv_derived(subject):
                    found.add(fn)
                    break
    return found


#: file -> the verdict a human reached, 2026-09-10. Adding a file here is a claim; the
#: rows above are where a claim of "refuses" gets tested. The four that were WRONG are
#: marked with what they used to do, because the next person to read this list should be
#: able to see that the defect was common and not exotic.
_ROSTER = {
    "collision_pipeline.py": "refuses: usage + exit 1",
    "decisions_conformance.py": "refuses: no mode SET -- a typo'd flag becomes a ledger path -> CANNOT MEASURE, exit 2",
    "donor_provenance.py": "refuses: exact-match `args != ['--backfill']` -> usage + exit 1",
    "dplc_layout.py": "refuses: unknown arg falls to argparse, which requires two positionals -> exit 2",
    "effects_gen.py": "FIXED LS-15d (was: silent demote to the read-only shapes report, exit 0)",
    "ojz_block_gen.py": "FIXED LS-15d (was: validated set, if/elif, no else -> silent exit 0)",
    "ojz_entity_gen.py": "FIXED LS-15d (was: DESTRUCTIVE fall-through into generate())",
    "ojz_strip_gen.py": "FIXED LS-15d (was: DESTRUCTIVE fall-through into generate() -- the incident)",
    "megaact_window_pageset.py": "refuses: MODES table, unknown/missing mode -> usage + exit 1 (M-B, 2026-09-16; was: argparse choices= guarding an `if == 'control'` ladder whose default branch was the WRITING `report --json`)",
    "megaact_page_order.py": "refuses: MODES table, unknown/missing mode -> usage + exit 1 (STITCHED-ACT-PAGE-ORDER, 2026-09-16, born in the fixed form; `report --json` writes the 09 evidence file)",
    "megaact_fg_cache10.py": "refuses: MODES table, unknown/missing mode -> usage + exit 1 (FG-CACHE-10-RESEARCH, 2026-09-16, born in the fixed form; `rederive`/`sweep`/`rom --json` write the 10 evidence files)",
    "cache_hold_probe.py": "refuses: MODES table, unknown/missing mode -> usage + exit 1 (CACHE-WINDOW-HOLD-MEASURE, 2026-09-17, born in the fixed form; `run --out` boots an emulator and writes a run JSON, `analyze --out` writes a summary)",
    "clip_manifest.py": "refuses: MODES table, unknown/missing mode -> usage + exit 1 (S2-COMPRESSED-ACT row 3, 2026-09-17, born in the fixed form; the only mode, `validate`, is read-only)",
    "clip_act_bake.py": "refuses: MODES table, unknown/missing mode -> usage + exit 1 (S2-COMPRESSED-ACT row 3, 2026-09-17, born in the fixed form; `bake` WRITES a clip act tree, so the dispatch running before any handler is the property, and the subprocess row above pins it)",
    "fg_page_order.py": "refuses: MODES table, unknown/missing mode -> usage + exit 1 (STITCHED-ACT-PAGE-ORDER wiring, 2026-09-17, born in the fixed form; `check` is read-only, the FG page-budget build gate)",
    "import_s2_collision.py": "refuses: MODES table, unknown/missing mode -> usage + exit 1 (S2-COMPRESSED-ACT row 4, 2026-09-17, born in the fixed form; `build` OVERWRITES the committed S2 collision bank, so the dispatch running before any handler is the property, and the two subprocess rows above pin it for both doorways)",
    "land_gate.py": "refuses: MODES table, unknown/missing mode -> usage + exit 1 (CTRL-3, born in the fixed form; `finish` writes the landing stamp)",
    "clip_rom_bake.py": "refuses: MODES table, unknown/missing mode -> usage + exit 1 (S2-COMPRESSED-ACT row 6, 2026-09-17, born in the fixed form; `bake` OVERWRITES the committed generated tree and the ROM collision tables as a THROWAWAY, so the dispatch running before any handler is the property -- and it deliberately has NO subprocess row, because on a regression that row's failure IS the write)",
    "act_grid.py": "refuses: MODES table, unknown/missing mode -> usage + exit 1 (S2-COMPRESSED-ACT parcel 9, 2026-09-17, born in the fixed form; `emit` WRITES the committed act_grid.emp the engine compiles its GRID_W/GRID_H out of, so the dispatch running before any handler is the property)",
    "clip_reachability.py": "refuses: MODES table, unknown/missing mode -> usage + exit 1 (S2-COMPRESSED-ACT parcel 7, 2026-09-17, born in the fixed form; `check` is READ-ONLY -- the act-wide reachability build gate for the S2CLIP shape. It is in _FIXED despite writing nothing because it runs as `gate strict`: a typo'd mode that reached a handler and exited 0 would be a build lane that had stopped measuring, which is this gate's own subject)",
    "verify_level_bin.py": "refuses: unknown argv token -> usage + exit 2 (it grew --project/--bank on 2026-09-17 so a clip act's tree could be verified by the same ten lanes; it WRITES NOTHING at any mode, and an unparsed flag is refused by name rather than ignored)",
    "s4lz.py": "refuses: `else: parser.print_help(); sys.exit(1)` -- the exemplar",
    "sfx_transcode.py": "refuses: single mode, exact match, else usage + exit 1",
    "state_ram.py": "refuses: no mode SET -- a typo'd `test` becomes a state path -> unhandled FileNotFoundError, exit 1",
    "vgm_onsets.py": "TOLERANT BY DESIGN, not fixed: unknown --flags are skipped (`else: a += 1`). Read-only; writes only a path the caller names on the command line. Recorded, not repaired.",
}


def test_the_ladder_population_is_still_the_roster():
    """A tools/*.py that dispatches on an argv string must have a recorded verdict.

    THIS IS THE ROW THAT OUTLIVES THE OTHERS. The parametrized rows above test twelve
    named files; this one tests that twelve is still the number, by rebuilding the list
    from source. A new generator with a hand-rolled mode ladder -- which is how all four
    of the broken ones got here -- lands red on THIS row with its filename in the
    message, before it can quietly join the population.
    """
    found = _dispatch_files()
    unrostered = sorted(found - set(_ROSTER))
    assert not unrostered, (
        "these tools/*.py dispatch on an argv string and have no recorded verdict: %s\n"
        "Classify each one and add it to _ROSTER in this file. The question to answer "
        "is NOT 'does it work' but: WHAT RUNS when the mode matches nothing? If the "
        "answer is a branch that writes, it belongs in _FIXED with a MODES table and a "
        "tripwire row -- never in a subprocess row, because on a regression that row's "
        "failure IS the data loss (LS-15d)." % ", ".join(unrostered))
    vanished = sorted(set(_ROSTER) - found)
    assert not vanished, (
        "these tools/*.py are in _ROSTER but the detector no longer finds a ladder in "
        "them: %s. Either they were rewritten (drop the entry AND the rows above that "
        "name them) or the detector has gone blind -- a silently-shrinking population "
        "is the failure this row is built to prevent." % ", ".join(vanished))
    # 12 at the 2026-09-10 census; 13 since CTRL-3 (2026-09-13) added land_gate.py;
    # 14 since M-B (2026-09-16) added megaact_window_pageset.py; 15 since
    # STITCHED-ACT-PAGE-ORDER (2026-09-16) added megaact_page_order.py; 16 since
    # FG-CACHE-10-RESEARCH (2026-09-16) added megaact_fg_cache10.py; 17 since the
    # STITCHED-ACT-PAGE-ORDER wiring (2026-09-17) added fg_page_order.py; 18 since
    # CACHE-WINDOW-HOLD-MEASURE (2026-09-17) added cache_hold_probe.py; 20 since
    # S2-COMPRESSED-ACT row 3 (2026-09-17) added clip_manifest.py and clip_act_bake.py;
    # 21 since S2-COMPRESSED-ACT row 4 (2026-09-17) added import_s2_collision.py;
    # 24 since S2-COMPRESSED-ACT parcel 7 (2026-09-17) added clip_reachability.py.
    # OBSERVED WHILE RAISING IT, said rather than tidied: this running commentary stops
    # at 21 but the assertion already read 23 before parcel 7 touched it, so TWO tools
    # (clip_rom_bake.py, verify_level_bin.py) entered the population without a line
    # here. The number is what the rows grade; the commentary is not, and it had drifted.
    assert len(found) == 25, (
        "expected the 2026-09-10 census's 12 CLI string dispatches plus CTRL-3's "
        "land_gate.py, M-B's megaact_window_pageset.py and STITCHED-ACT-PAGE-ORDER's "
        "megaact_page_order.py, FG-CACHE-10-RESEARCH's megaact_fg_cache10.py, the "
        "STITCHED-ACT-PAGE-ORDER wiring's fg_page_order.py, CACHE-WINDOW-HOLD-MEASURE's "
        "cache_hold_probe.py, S2-COMPRESSED-ACT row 3's clip_manifest.py + "
        "clip_act_bake.py, row 4's import_s2_collision.py, parcel 7's clip_reachability.py and "
        "parcel 9's act_grid.py, found %d: %s"
        % (len(found), sorted(found)))
