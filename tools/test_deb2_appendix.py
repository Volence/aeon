"""A `mark` IS NOT ZERO-BYTE — the guard on the claim, not on the count (LS-22a).

THE FINDING THIS PROTECTS (measured 2026-09-07, branch point `0d64f534`).

`mark NAME` in a `region`/`vars` block emits no ROM bytes.  It still changes the
ROM, because it emits a SYMBOL and `build.sh` appends the deb2 symbol table INTO
the image, past `EndOfRom`, in EVERY shape — the two debug ROMs and BOTH SHIPPED
RELEASE ROMS.  Measured appendix sizes at that SHA: s4 `0xa773`, s4.debug
`0xd5cd`, demo `0x6845`, demo.debug `0x80f7`.

HOW BIG THE MOVE IS, AND WHY YOU CANNOT PREDICT IT.  The appendix opens with a
Huffman code table over the CHARACTERS of every symbol name (4-byte records
`<code:2><len:1><char:1>`), followed by the bit-packed names.  A mark lands on the
address of the next var, so its RECORD is dropped as a duplicate address — but its
NAME still feeds the character histogram the code table is built from.  Adding
`mark Sound_Dbg_Mirror_End` took demo.debug's `'b'` from 336 to 337 and broke its
exact tie with `'k'` at 336; the two 7-bit codes `0x004D` and `0x005C` exchanged
owners, every name containing a `b` or a `k` re-encoded, and 953 appendix bytes
changed with the total length UNCHANGED (`0x80f7` both ways).  Plus the header
checksum word at `$18E` = the 955 bytes the real build moved.  The same edit left
s4, s4.debug and demo BYTE-IDENTICAL, because `'b'` was untied in those corpora.

There is no shape-level rule.  Holding the name fixed and moving the mark to four
different anchors changed nothing; holding the address fixed and varying the name
moved every shape.  Over 35 names: s4 moved for 20, s4.debug for 17, demo for 30,
demo.debug for 32, and `AAAAAAAAAAAAAAAAAAAA` moved all four AND changed their
lengths.  So: **a mark can move any of the four ROMs, including the shipped
release ones, and which ones it moves is not predictable — measure all four.**

WHAT THIS FILE ASSERTS, and why it is shaped this way.

Not a pinned COUNT of marks.  A count-pin would fire on every legitimate mark
addition while staying blind to the rest of the same hazard: ANY edit that changes
the set of symbol NAMES without emitting a byte moves the appendix the same way —
renaming a local label, adding one, dropping one.  Singling out `mark` would teach
the wrong rule and tax the right edits.  The prose above is the guidance; this file
guards the two FACTS that prose rests on, both of which have rotted in this tree
before (build.sh's own header claimed the release ROM shipped without the appendix
until 2026-09-04):

  1. the built ROM carries a deb2 appendix past `EndOfRom` — in the shape under
     test, release shapes included;
  2. a `mark` really does become a symbol in that shape's listing, which is what
     `convsym` packs into that appendix.

If someone changes the pipeline so either stops being true, this goes red and the
guidance above has to be rewritten rather than left standing as stale prose.

WHAT IT DOES **NOT** COVER.

  * It does NOT tell you whether your edit moved a ROM.  It cannot: that is a byte
    comparison against a baseline built with the same assembler, and it is the
    repin/refreeze ritual's job.  A green run here says nothing about your CRC.
  * It does NOT cover the non-`mark` half of the hazard (renamed or added labels).
  * It does NOT check the appendix CONTENTS beyond its magic and non-emptiness —
    a corrupt table with a correct header passes.
  * It grades only the shape THIS `./build.sh` produced; the other three are
    DEFERRED by `tools/conftest.py`, never silently skipped.

TO ASK "WOULD THIS NAME MOVE THIS ROM?" WITHOUT BUILDING: `tools/deb2_probe.py`
replays the same convsym pipeline over a listing already on disk (0.1 s a trial)
and `--verify`s itself by reproducing the built ROMs' own appendices byte for
byte.  It is a hand instrument, not a lane; a real answer is still four builds.
"""

import os
import re

import pytest

AEON = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: The `mark NAME,` form as `region`/`vars` blocks spell it.
MARK_RE = re.compile(r"^\s*mark\s+([A-Za-z_][A-Za-z0-9_]*)\s*,")

#: A double-quoted string literal, so its `{...}` interpolations never reach the
#: brace tracker in `mark_inventory`.
STRING_RE = re.compile(r'"(?:[^"\\]|\\.)*"')

#: A ` NAME : HEXADDR C |` row of the listing's `Symbol Table` section.
SYMROW_RE = re.compile(r"^[ *](\S+) : ([0-9A-F]+) C \|$")

#: The FIRST TWO bytes of the deb2 header.  The only literal in this file: the rest
#: of the header is data-dependent (the packing/offset fields differ per shape), so
#: two bytes plus a size floor is the whole presence claim.  Same two bytes
#: `sigil-harness`'s `native::DEB2_MAGIC` asserts on its own side of the pipeline.
DEB2_MAGIC = b"\xde\xb2"

#: (rom, listing, game) for each shape build.sh can produce.
SHAPES = [
    ("s4.bin", "s4.lst", "sonic4"),
    ("s4.debug.bin", "s4.debug.lst", "sonic4"),
    ("demo.bin", "demo.lst", "demo"),
    ("demo.debug.bin", "demo.debug.lst", "demo"),
]


def _emp_sources(game):
    """Every `.emp` file a build of `game` links: the engine plus that game."""
    roots = [os.path.join(AEON, "engine"), os.path.join(AEON, "games", game)]
    out = []
    for root in roots:
        for dirpath, _, files in os.walk(root):
            for f in files:
                if f.endswith(".emp"):
                    out.append(os.path.join(dirpath, f))
    return sorted(out)


def mark_inventory(game):
    """{name: (loc, gate)} for every `mark` declared in `game`'s sources.

    `gate` is None for a mark every shape places, or the text of the innermost
    enclosing `if ... {` condition for one only some shapes place.  It is derived
    by brace-tracking the source, not hardcoded: `engine/ram.emp` places
    `Parallax_Scratch_Config_End` inside `if DEBUG == 1 @shape_divergent { ... }`,
    so the release listings do not carry it and a flat "every mark is in every
    listing" expectation would be simply false.
    """
    inv = {}
    for path in _emp_sources(game):
        stack = []          # (opening keyword, condition text) per open brace
        with open(path, errors="replace") as fh:
            for i, line in enumerate(fh, 1):
                # Comments AND string literals are stripped before brace counting:
                # `.emp` ensure/diagnostic messages carry `{...}` interpolations,
                # and one of those would unbalance the stack for the rest of a file.
                code = STRING_RE.sub('""', line.split("//", 1)[0])
                m = MARK_RE.match(line)
                if m:
                    gates = [c for kw, c in stack if kw == "if"]
                    rel = os.path.relpath(path, AEON)
                    inv[m.group(1)] = ("%s:%d" % (rel, i),
                                       gates[-1] if gates else None)
                opens, closes = code.count("{"), code.count("}")
                for _ in range(opens):
                    kw = (code.strip().split() or [""])[0]
                    cond = code.strip()[len(kw):].split("{", 1)[0].strip()
                    stack.append((kw, cond))
                for _ in range(closes):
                    if stack:
                        stack.pop()
    return inv


def listing_symbols(path):
    """{name: value} from the listing's `Symbol Table` section."""
    syms, in_table = {}, False
    with open(path, errors="replace") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if line.startswith("  Symbol Table"):
                in_table = True
                continue
            if not in_table:
                continue
            if line.strip().endswith("symbols"):
                break
            m = SYMROW_RE.match(line)
            if m:
                syms[m.group(1)] = int(m.group(2), 16)
    return syms


# --------------------------------------------------------------------------
# The hermetic half — runs in build.sh's PRE-build lane, reads no artifact.
# It exists so an inventory that silently became EMPTY (a renamed construct, a
# moved tree, a regex that stopped matching) cannot make the artifact tests below
# pass vacuously by having nothing to look for.
# --------------------------------------------------------------------------

def test_mark_inventory_is_measurable():
    for game in ("sonic4", "demo"):
        sources = _emp_sources(game)
        assert len(sources) > 50, (
            "walked %s and found only %d .emp files — the tree moved and every "
            "mark assertion below would be vacuous" % (game, len(sources)))
        inv = mark_inventory(game)
        assert inv, (
            "no `mark` found in any of %d .emp sources for game %s. Either the "
            "construct was renamed (update MARK_RE) or every mark was deleted — "
            "and a deletion is as byte-changing as an addition, for the reason in "
            "this file's header." % (len(sources), game))
        # engine/ram.emp is where the RAM-region marks live; a game with none of
        # its own is fine, a tree with none at all is the vacuous case above.
        assert any(loc.startswith("engine/ram.emp:")
                   for loc, _gate in inv.values()), (
            "no mark in engine/ram.emp for game %s — the file this finding is "
            "about no longer declares one" % game)


def test_mark_names_are_unique_per_symbol():
    """A duplicated mark name would make the listing assertion below ambiguous.

    `mark_inventory` is a dict keyed by name, so a duplicate would COLLAPSE there
    rather than show up — this scans the raw sources instead, which is the only
    place the second declaration still exists.
    """
    for game in ("sonic4", "demo"):
        seen = {}
        for path in _emp_sources(game):
            with open(path, errors="replace") as fh:
                for i, line in enumerate(fh, 1):
                    m = MARK_RE.match(line)
                    if m:
                        seen.setdefault(m.group(1), []).append(
                            "%s:%d" % (os.path.relpath(path, AEON), i))
        dupes = {n: locs for n, locs in seen.items() if len(locs) > 1}
        assert not dupes, (
            "game %s declares the same mark name twice: %s. Two marks with one "
            "name resolve to one deb2 symbol, so the listing check cannot tell "
            "which of them reached the ROM." % (game, dupes))


# --------------------------------------------------------------------------
# The artifact half — POST-SIGIL lane, one test per shape, deferred by
# tools/conftest.py for every shape this invocation did not build.
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "rom_name,lst_name,game",
    [pytest.param(*s, marks=pytest.mark.needs_build(s[0], s[1])) for s in SHAPES],
    ids=[s[0] for s in SHAPES],
)
def test_deb2_appendix_is_in_the_rom_and_carries_the_marks(rom_name, lst_name, game):
    rom_path = os.path.join(AEON, rom_name)
    lst_path = os.path.join(AEON, lst_name)
    with open(rom_path, "rb") as fh:
        rom = fh.read()
    syms = listing_symbols(lst_path)

    assert syms, (
        "%s has no parseable `Symbol Table` section — the listing format moved "
        "and this test is grading nothing" % lst_name)
    assert "EndOfRom" in syms, (
        "%s declares no EndOfRom symbol, so the assembled/appendix boundary this "
        "test splits at cannot be derived" % lst_name)

    eor = syms["EndOfRom"]

    # (1) the appendix is IN the shipped image, release shapes included.
    assert len(rom) > eor, (
        "%s is %d bytes and EndOfRom is %#x — no deb2 appendix at all. If this "
        "shape is now meant to ship without one, the LS-22a guidance in this "
        "file's header is stale and the CODING_CONVENTIONS.md rule with it."
        % (rom_name, len(rom), eor))
    assert rom[eor:eor + 2] == DEB2_MAGIC, (
        "%s: expected the deb2 magic %s at EndOfRom %#x, found %s"
        % (rom_name, DEB2_MAGIC.hex(), eor, rom[eor:eor + 2].hex()))
    appendix = len(rom) - eor
    # Derived floor, not a copied number: one symbol costs several bytes, so a
    # table for hundreds of symbols cannot be a handful of bytes. This catches a
    # COLLAPSED table (a filter that dropped nearly everything), not a drift.
    assert appendix > len(syms), (
        "%s: the deb2 appendix is %#x bytes for %d listing symbols — fewer bytes "
        "than symbols means the table collapsed" % (rom_name, appendix, len(syms)))

    # (2) a `mark` really is a symbol in this shape's listing, which is what
    #     convsym packs into the appendix asserted above.
    inv = mark_inventory(game)
    debug_shape = ".debug." in rom_name
    # The gate text carries its attributes (`DEBUG == 1 @shape_divergent`); the
    # condition is the part before the first `@`.
    expected = {n: loc for n, (loc, gate) in inv.items()
                if gate is None
                or (gate.split("@", 1)[0].strip() == "DEBUG == 1" and debug_shape)}
    assert len(expected) >= 10, (
        "only %d of %d marks are expected in %s — the gate classification "
        "collapsed and this assertion has almost nothing left to check"
        % (len(expected), len(inv), lst_name))
    missing = sorted(n for n in expected if n not in syms)
    assert not missing, (
        "%s: %d mark(s) declared in source do not appear in %s: %s\n"
        "  If marks have stopped becoming deb2 symbols then a mark IS free now, "
        "and this file's header plus the CODING_CONVENTIONS.md rule it cites are "
        "both wrong and must be rewritten — do not delete this assertion to make "
        "the build green.\n  Declared at: %s"
        % (rom_name, len(missing), lst_name, missing,
           {n: expected[n] for n in missing}))

    # The other direction for the gated ones: a mark this shape is NOT supposed to
    # place must be ABSENT. Without it a gate that silently stopped gating would
    # read as a pass, and the shapes would quietly stop diverging.
    unexpected = sorted(n for n, (loc, gate) in inv.items()
                        if n not in expected and n in syms)
    assert not unexpected, (
        "%s: mark(s) %s are gated OUT of this shape in source but present in %s — "
        "either the gate stopped gating (every shape now pays the symbol, and the "
        "release ROMs moved) or the classification in mark_inventory is wrong"
        % (rom_name, unexpected, lst_name))
