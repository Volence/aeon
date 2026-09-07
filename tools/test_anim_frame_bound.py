"""The runner for tools/anim_frame_bound.py — LS-9a's frame-byte bound.

WHY THIS FILE EXISTS. `anim_frame_bound.py --gate` is wired into build.sh and
runs on every sonic4 build, which makes the BOUND enforced. It does not make the
bound PROVABLE: a gate whose red path nobody exercises is indistinguishable in
an exit status from a gate that cannot go red at all, and this sweep found that
exact shape more than once (a printed-and-discarded `out_of_range`, a lane whose
bed was its own runner). `--selftest` is the red path, and this file is what
makes it run instead of sitting behind a flag nobody types.

The selftest's per-table proof is three cases, not one:

  A  the shipped image is green for this pair;
  B  a frame byte set to `frames - 1` — the LAST VALID index — stays green;
  C  the SAME byte set to `frames` goes red and names the table.

B and C differ by one in one byte, so nothing but the direction of the compare
separates them, and B is the case that fails if `<` were ever written `<=`. Six
of the ten tables sit at margin ZERO (their script's last frame IS the table's
last frame), which is why the direction has to be proved and not argued.

WHAT THIS FILE DOES NOT COVER. It does not check that a REGISTRY row is right —
that Ani_Particle really is animated against Map_TestObj is a claim about a spawn
path, and the tool reports it as DECLARED for that reason. It says nothing about
the DPLC table (LS-9's `offset_table_frames(map) == offset_table_frames(dplc)`
ensure owns that), and nothing about whether a frame's art is correct — only that
the index is inside the table.
"""

import pathlib
import subprocess
import sys

import pytest

TOOLS = pathlib.Path(__file__).resolve().parent
AEON = TOOLS.parent
sys.path.insert(0, str(TOOLS))

import anim_frame_bound as afb                                       # noqa: E402


def _run(*args):
    return subprocess.run([sys.executable, str(TOOLS / "anim_frame_bound.py"), *args],
                          cwd=AEON, capture_output=True, text=True)


# ------------------------------------------------------------- source-only

def test_declared_pairs_evidence_is_live():
    """Every DECLARED_PAIRS entry's evidence must still match its file.

    A declared pairing is the tool's own claim rather than something it read, so
    the evidence lines are the only thing keeping the claim honest. This runs
    with no build, so a source change that invalidates one is caught in the
    pre-build lane rather than at the gate.
    """
    import re
    stale = []
    for anim, spec in afb.DECLARED_PAIRS.items():
        assert spec["evidence"], f"{anim} is declared with no evidence at all"
        for rx, why, where in spec["evidence"]:
            if not re.search(rx, afb._read(where), re.M):
                stale.append(f"{anim}: {where} no longer matches `{rx}` ({why})")
    assert not stale, "DECLARED_PAIRS evidence went stale:\n  " + "\n  ".join(stale)


def test_pairing_scan_finds_the_three_binding_shapes():
    """The derivation must reach all three idioms the tree uses, each by name.

    Asserting only a total would pass if one shape stopped matching and another
    grew — which is how a scan goes blind. So each shape is named: a
    CharacterDef literal, a co-located spawn write, and an objdef literal.
    """
    pairs = afb.derived_pairs(afb.equ_aliases())
    by_src = {src: (a, m) for a, m, src in pairs}
    shapes = {
        "CharacterDef": [s for s in by_src if "CharDef_" in s],
        "co-located spawn write": [s for s in by_src if ":" in s and "(" in s],
        "objdef literal": [s for s in by_src if "ObjDef_" in s],
    }
    missing = [k for k, v in shapes.items() if not v]
    assert not missing, (f"the pairing scan reaches none of: {missing}. A shape that stops "
                         f"matching is how a scan goes silently blind; found "
                         f"{ {k: len(v) for k, v in shapes.items()} }")


def test_alias_resolution_reaches_the_equ_bound_objects():
    """Four of the co-located pairs bind through `equ NAME = extern("Sym")`.

    Without alias resolution those four would resolve to names that are not
    listing labels, and the tool would report a population gap on assets that
    are in fact bound — a false red, which is as bad as a false green.
    """
    alias = afb.equ_aliases()
    for name, want in (("ANI_DUST_PUFF", "Ani_DustPuff"),
                       ("ANI_DUST_SPINDASH", "Ani_DustSpindash"),
                       ("ANI_TAILS_APPENDAGE", "Ani_TailsAppendage"),
                       ("MAP_DUST_PUFF", "Map_DustPuff")):
        assert alias.get(name) == want, (
            f"`equ {name} = extern(\"{want}\")` no longer resolves — the object modules "
            f"bind their data by alias and the pairing scan depends on it")


# ---------------------------------------------------------- against the ROM

@pytest.mark.needs_build("s4.debug.lst", "s4.debug.bin")
def test_gate_is_green_on_the_built_rom():
    r = _run("--lst", "s4.debug.lst", "--rom", "s4.debug.bin", "--gate")
    assert r.returncode == 0, f"gate not green:\n{r.stdout}\n{r.stderr}"
    assert "10 animation table(s)" in r.stdout or "animation table(s) in the listing" in r.stdout


@pytest.mark.needs_build("s4.debug.lst", "s4.debug.bin")
def test_every_pair_proved_red_first_in_both_directions():
    """THE red-first proof, run rather than available.

    A `broken` case is a failure: it means a pair could be neither placed on the
    boundary nor pushed over it, so nothing was established for it. A pair the
    tool reports as unable to go red at all (`VACUOUS`) is counted separately and
    printed — Map_Tails and Map_Knuckles declare 251 frames, more than the $F7
    frame/command threshold lets a script byte name, so for those two the bound
    is reachable only through an expansion, and the selftest says so instead of
    quietly counting them as proved.
    """
    r = _run("--lst", "s4.debug.lst", "--rom", "s4.debug.bin", "--selftest")
    assert r.returncode == 0, f"selftest did not pass:\n{r.stdout}\n{r.stderr}"
    tail = [ln for ln in r.stdout.splitlines() if ln.startswith("anim_frame_bound selftest:")]
    assert tail, f"the selftest printed no verdict line:\n{r.stdout}"
    assert " 0 broken" in tail[-1], f"a pair could not be proved:\n{r.stdout}"
    # Every pair must carry an A line, and every pair must carry either the B/C
    # boundary pair or the D expansion case. A pair with only an A line would be
    # a table the proof silently skipped.
    rows, _faults, _pop = afb.build_rows("s4.debug.lst", "s4.debug.bin")
    for row in rows:
        lines = [ln for ln in r.stdout.splitlines() if row["anim"] in ln]
        assert any(" A control:" in ln for ln in lines), f"{row['anim']}: no control case"
        assert any(" C first invalid:" in ln or " D expansion:" in ln for ln in lines), \
            f"{row['anim']}: neither the boundary pair nor the expansion case was placed"
