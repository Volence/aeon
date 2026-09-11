"""B2b-4: the YM2612 address->data floor has ONE authority, and its two mirrors are pinned to it.

`YM_ADDR_TO_DATA_MIN_T` is the T-state floor that thirteen build-fatal
`ensure(cycles(...) >= YM_ADDR_TO_DATA_MIN_T)` guards measure the sound driver's YM write
paths against (2 in sound_fm.emp, 8 in z80_sound_driver.emp, 3 in sound_sequencer.emp at
aeon cd075f2d; the count is informational, nothing below depends on it). It is declared in
three Z80 resident modules. The AUTHORITY is the `pub const` in engine/sound/sound_fm.emp,
where the derivation (Sega wait table: 17 68k cycles after an address-port write, converted
to the Z80 clock) and the gap-measurement convention are written down.
engine/sound/z80_sound_driver.emp and engine/sound/sound_sequencer.emp carry private copies.

WHY THIS IS A TEST AND NOT AN `ensure`. Seam-1 lowers the resident modules one file at a time
(sigil `crates/sigil-harness/src/seam1.rs`, `lower_one`). A resident file sees its own names,
the FIXED per-file `-D` list seam-1 injects from sound_constants.emp, and nothing else; its
`use engine.sound_*.{...}` clauses become `extern proc` contract stubs built from the sibling's
`pub proc` definitions only (`import_stub_table` / `use_import_stubs`). Measured 2026-09-11 on
aeon cd075f2d with the sigil release binary this parcel ran against:
  * `use engine.sound_fm.{YM_ADDR_TO_DATA_MIN_T}` in the driver: `unknown name` at all 8
    consumers, emit_sound_blob fails. A const does not cross a `use` here.
  * `const YM_ADDR_TO_DATA_MIN_T = extern("YM_ADDR_TO_DATA_MIN_T")` in the driver: builds
    GREEN. So does `extern("NO_SUCH_SYMBOL_LENS_PIN")`, a name that exists nowhere. With the
    driver on the extern spelling and the authority raised to 100, only sound_fm.emp's own two
    guards fired: the driver's eight passed. extern() in a resident module is VACUOUS, and it
    is the tempting "single authority" respelling, which is why the mirror check below refuses
    anything that is not an integer literal.
The routes that would let the build itself hold the three in step (a const `use` across
resident modules, or a new name on seam-1's injected list) are sigil changes, out of this
repo's reach.

A mirror that drifted LOW would not fail the build: every cycle guard in its module would
accept a write path under the hardware floor. This test reads the authority's value off the
authority's own line (never a copy) and requires every other `.emp` that touches the name in
code to declare it once, as a literal, with the same value. It runs in build.sh's pre-build
pytest lane, which is build-fatal.

WHAT THIS TEST DOES NOT COVER, so nobody reads a green run as more than it is:
  * whether 8 is the RIGHT floor. That is the authority's derivation and nothing checks it;
  * the data->next-address floor (~39 T), which sound_fm.emp deliberately does not declare
    because no build input can measure it (the coverage note above Fm_WriteFreq);
  * whether each consuming `cycles()` span measures the right pair of labels;
  * `FAST=1` and `NO_LINT=1` builds, which skip the pytest lane entirely: a mirror edited in a
    FAST loop builds green there and fails at the next canonical `./build.sh`.
"""
import os
import re

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NAME = "YM_ADDR_TO_DATA_MIN_T"
AUTHORITY = os.path.join("engine", "sound", "sound_fm.emp")
DECL = re.compile(r"^\s*(pub\s+)?const\s+" + NAME + r"\s*=\s*(.*?)\s*(//.*)?$")
LITERAL = re.compile(r"\$[0-9A-Fa-f]+|[0-9]+")
NOT_COVERED = (
    "WHAT THIS DOES NOT COVER: whether the authority's value is the right floor, the "
    "undeclared data->next-address floor, and FAST=1 / NO_LINT=1 builds (they skip this lane)")


def _int(tok):
    return int(tok[1:], 16) if tok.startswith("$") else int(tok, 10)


def _code_lines(path):
    """(lineno, line) for every line that is not a whole-line // comment."""
    with open(os.path.join(REPO, path), encoding="utf-8") as fh:
        for n, line in enumerate(fh, 1):
            if not line.lstrip().startswith("//"):
                yield n, line.rstrip("\n")


def _population():
    """Every .emp under engine/ and games/ that TOUCHES the name in code (not only in a comment)."""
    out = []
    for top in ("engine", "games"):
        for root, _dirs, files in os.walk(os.path.join(REPO, top)):
            for f in files:
                if f.endswith(".emp"):
                    rel = os.path.relpath(os.path.join(root, f), REPO)
                    if any(NAME in line for _n, line in _code_lines(rel)):
                        out.append(rel)
    return sorted(out)


def _decls(path):
    return [(n, m) for n, line in _code_lines(path) for m in [DECL.match(line)] if m]


def _authority():
    decls = _decls(AUTHORITY)
    assert len(decls) == 1, (
        f"{AUTHORITY} must declare {NAME} exactly once; found {len(decls)}. It is the authority "
        "the resident mirrors are held to. " + NOT_COVERED)
    n, m = decls[0]
    assert m.group(1), (
        f"{AUTHORITY}:{n}: the authority must stay `pub const` (it is the declaration every "
        "mirror's comment points a reader at). " + NOT_COVERED)
    assert LITERAL.fullmatch(m.group(2)), (
        f"{AUTHORITY}:{n}: {NAME} = {m.group(2)!r} is not an integer literal. This test reads "
        "only a literal and refuses anything else rather than guess (fail closed). " + NOT_COVERED)
    return n, _int(m.group(2))


def test_the_authority_declares_it_once_as_a_pub_literal():
    _authority()


def test_every_mirror_equals_the_authority():
    an, want = _authority()
    population = _population()
    assert AUTHORITY in population, f"the authority {AUTHORITY} no longer mentions {NAME} in code"
    assert len(population) > 1, (
        f"only the authority mentions {NAME}: either the mirrors were deleted (good, then delete "
        "this test) or the population walk is broken (then this test has gone vacuous)")
    bad = []
    for path in population:
        if path == AUTHORITY:
            continue
        decls = _decls(path)
        if len(decls) != 1:
            bad.append(f"{path}: touches {NAME} in code but declares it {len(decls)} times (expected exactly one private mirror)")
            continue
        n, m = decls[0]
        tok = m.group(2)
        if not LITERAL.fullmatch(tok):
            bad.append(
                f"{path}:{n}: mirror is {tok!r}, not an integer literal. In a seam-1 resident module "
                "`extern(...)` builds green even for a symbol that exists nowhere and every guard "
                "reading it passes unconditionally (measured 2026-09-11), so this test refuses any "
                "spelling it cannot read")
        elif _int(tok) != want:
            bad.append(f"{path}:{n}: mirror says {_int(tok)}, the authority {AUTHORITY}:{an} says {want}")
    assert not bad, (
        f"YM2612 address->data floor ({NAME}) out of step with its authority. Every "
        f"`ensure(cycles(...) >= {NAME})` in a drifted module is now measuring against the wrong "
        "floor, and a LOW mirror makes those guards pass on spacing the chip cannot take. Set "
        "each mirror to the authority's value as a plain literal (the authority carries the "
        "derivation):\n  " + "\n  ".join(bad) + "\n" + NOT_COVERED)
