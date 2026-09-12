"""A2-6 follow-up: the MEV_EXT extension prefix has ONE authority, and its mirror is pinned to it.

`MEV_EXT` ($FA) is the music/SFX event-list EXTENSION PREFIX: the sequencer intercepts it in
`Sequencer_NextOpcode.coord` (`cp MEV_EXT` / `jp z, Seq_Op_Ext`) BEFORE the banked
SeqOpcodeTable dispatch, and `song_packer.py` emits it for every `Comm` event. The AUTHORITY is
the `pub const` in engine/sound/sound_constants.emp, where the sub-op registry is written down.
engine/sound/sound_sequencer.emp carries a private mirror because seam-1 injects only a FIXED
per-file `-D` list of authority constants into a resident Z80 module, and MEV_EXT is not on it.

WHY THIS IS A TEST AND NOT AN `ensure`, and what the ensures already do.
Since 2026-09-12 both sides carry value pins: sound_constants.emp has the A2-6 trio (range,
`== $FA`, and a 27-way collision wall), and sound_sequencer.emp has this parcel's pair (a
DERIVED `>= MEV_VOL` reachability clause plus its own `== $FA`). Those catch a one-sided edit
in the two sonic4 shapes. What no `ensure` in either file can catch is a CONSISTENT move: edit
the authority to $FB and its own value pin to match, and the mirror stays stale at $FA with
every guard green. A value pin cannot see another file, and the two routes that would let the
build hold them in step (a const crossing a `use` between resident modules, or a new name on
seam-1's injected list) are sigil changes, out of this repo's reach — the same reasoning, and
the same measurements, as tools/test_ym_floor_single_authority.py, which this file follows.

It also runs where the ensures cannot. games/demo/build.conf sets `SOUND_DRIVER_ENABLED=0`, so
build.sh never invokes emit_sound_blob for demo and engine/sound/sound_sequencer.emp is not
elaborated in either demo shape — its ensures are dead there. This lane is shape-independent.

WHAT THIS TEST DOES NOT COVER, so nobody reads a green run as more than it is:
  * whether $FA is the RIGHT slot. That is the authority's own collision wall and range pin;
  * the sub-op REGISTRY (0 = COMM, 1/2 reserved, 3-255 free) — nothing checks that at all;
  * tools/song_packer.py's own `MEV_EXT = 0xFA`, which tools/test_song_packer.py pins
    separately (`self.assertEqual(MEV_EXT, 0xFA)`);
  * `FAST=1` and `NO_LINT=1` builds, which skip the pytest lane entirely: a mirror edited in a
    FAST loop builds green there and fails at the next canonical `./build.sh`.
"""
import os
import re

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NAME = "MEV_EXT"
AUTHORITY = os.path.join("engine", "sound", "sound_constants.emp")
# `MEV_EXT` must not match `MEV_EXT_COMM`, which sound_constants.emp declares two lines later.
DECL = re.compile(r"^\s*(pub\s+)?const\s+" + NAME + r"\s*=\s*(.*?)\s*(//.*)?$")
LITERAL = re.compile(r"\$[0-9A-Fa-f]+|[0-9]+")
NOT_COVERED = (
    "WHAT THIS DOES NOT COVER: whether $FA is the right slot, the MEV_EXT sub-op registry, "
    "song_packer.py's own copy (tools/test_song_packer.py pins that one), and FAST=1 / "
    "NO_LINT=1 builds (they skip this lane)")


def _int(tok):
    return int(tok[1:], 16) if tok.startswith("$") else int(tok, 10)


def _code_lines(path):
    """(lineno, line) for every line that is not a whole-line // comment."""
    with open(os.path.join(REPO, path), encoding="utf-8") as fh:
        for n, line in enumerate(fh, 1):
            if not line.lstrip().startswith("//"):
                yield n, line.rstrip("\n")


def _population():
    """Every .emp under engine/ and games/ that DECLARES the name (a `const MEV_EXT = ...` line).

    Deliberately narrower than the YM-floor test's "touches the name in code" walk: MEV_EXT is
    named in code by seq_opcode_tab.emp's comments and by sound_api.emp prose, and a
    declaration is the only thing that can drift out of step with a value.
    """
    out = []
    for top in ("engine", "games"):
        for root, _dirs, files in os.walk(os.path.join(REPO, top)):
            for f in files:
                if f.endswith(".emp"):
                    rel = os.path.relpath(os.path.join(root, f), REPO)
                    if _decls(rel):
                        out.append(rel)
    return sorted(out)


def _decls(path):
    return [(n, m) for n, line in _code_lines(path) for m in [DECL.match(line)] if m]


def _authority():
    decls = _decls(AUTHORITY)
    assert len(decls) == 1, (
        f"{AUTHORITY} must declare {NAME} exactly once; found {len(decls)}. It is the authority "
        "the resident mirror is held to. " + NOT_COVERED)
    n, m = decls[0]
    assert m.group(1), (
        f"{AUTHORITY}:{n}: the authority must stay `pub const` (it is the declaration the "
        "mirror's comment points a reader at). " + NOT_COVERED)
    assert LITERAL.fullmatch(m.group(2)), (
        f"{AUTHORITY}:{n}: {NAME} = {m.group(2)!r} is not an integer literal. This test reads "
        "only a literal and refuses anything else rather than guess (fail closed). " + NOT_COVERED)
    return n, _int(m.group(2))


def test_the_authority_declares_it_once_as_a_pub_literal():
    _authority()


def test_the_sequencer_mirror_equals_the_authority():
    an, want = _authority()
    population = _population()
    assert AUTHORITY in population, f"the authority {AUTHORITY} no longer declares {NAME}"
    mirrors = [p for p in population if p != AUTHORITY]
    assert mirrors, (
        f"only the authority declares {NAME}: either the sequencer mirror was deleted (good — "
        "then delete this test and the two ensures beside that mirror) or the declaration walk "
        "is broken (then this test has gone vacuous). " + NOT_COVERED)
    bad = []
    for path in mirrors:
        decls = _decls(path)
        if len(decls) != 1:
            bad.append(
                f"{path}: declares {NAME} {len(decls)} times (expected exactly one private mirror)")
            continue
        n, m = decls[0]
        tok = m.group(2)
        if not LITERAL.fullmatch(tok):
            bad.append(
                f"{path}:{n}: mirror is {tok!r}, not an integer literal. In a seam-1 resident "
                "module `extern(...)` builds green even for a symbol that exists nowhere and "
                "every guard reading it passes unconditionally (measured 2026-09-11, see "
                "tools/test_ym_floor_single_authority.py), so this test refuses any spelling it "
                "cannot read")
        elif _int(tok) != want:
            bad.append(
                f"{path}:{n}: mirror says {_int(tok)} (${_int(tok):02X}), the authority "
                f"{AUTHORITY}:{an} says {want} (${want:02X})")
    assert not bad, (
        f"the music/SFX extension prefix ({NAME}) is out of step with its authority. The "
        "sequencer's `cp MEV_EXT` intercept would test a byte the packer never emits, so a "
        "score's MEV_EXT would fall through to the banked SeqOpcodeTable and be dispatched as "
        "whatever handler sits at that slot, mid-stream. Set the mirror to the authority's value "
        "as a plain literal (and update the `== $FA` ensure beside each):\n  "
        + "\n  ".join(bad) + "\n" + NOT_COVERED)
