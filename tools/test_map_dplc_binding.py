"""Every mappings/DPLC pair must bind its two frame counts. No asset opts out silently.

WHY THIS FILE EXISTS (LS-9, 2026-09-06 sweep, closed 2026-09-07).

A sprite asset's mappings table and its DPLC table are indexed by the SAME
`mapping_frame` byte -- Render_Sprites walks one with it, Perform_DPLC walks the other.
If the two declare different frame counts, the shorter is read PAST ITS END: the word
it yields is not an offset but two bytes of whatever blob the linker placed next, and
that is followed as a frame pointer. The helpers that check this existed for a month
and worked, but they were PRIVATE to games/sonic4/player/player_instashield.emp, so
exactly one of the tree's six pairs had them. Sonic -- the default character, 224
frames, the largest pair in the ROM -- had none. They now live in engine/objects/dplc.emp
and every pair carries them.

**Promoting the helpers is not the closure.** Nothing stops the NEXT asset arriving
with a mappings blob, a DPLC blob and no guard at all, which is precisely how the
insta-shield came to be alone. THIS FILE is what refuses that: it enumerates the
mappings and DPLC blobs actually embedded in the tree, requires each to be REGISTERED
either as half of a guarded pair or as an explicit no-DPLC exemption with a reason, and
requires each registered pair's two guards to be present and to name that pair's own
two blobs.

Four layers:

1. THE POPULATION. Every `embed(...)` of a mappings or DPLC blob under games/, derived
   from the sources -- not from a list typed here. An unregistered blob is a failure.
2. THE REGISTRY. Every registered pair carries BOTH guards, and each guard's arguments
   are that pair's own two blob constants. A guard whose arguments drifted to another
   asset's blobs fails here even though it would build green.
3. THE HELPERS. The guards must be spelled with the shared `engine.objects.dplc`
   functions, imported -- not re-privatised into a local copy, which is the state this
   parcel removed.
4. THE MESSAGE. Every guard must say what it does NOT cover. Binding the two tables to
   each other does not bound the frame BYTE (LS-9a), and a message that does not say so
   invites a green build being read as closing that too.

WHAT THIS FILE DOES NOT COVER. It cannot tell you a REGISTRY ROW is right: that two
blobs really are one asset's pair is a fact about the load site, and nothing here reads
one. It does not read the blobs -- whether today's counts agree is the `.emp` ensure's
job, in every shape, without pytest. It says nothing about whether corresponding frames
describe the same art, about DPLC tile or queue-slot cost (tools/test_vram_window_guards.py
and the peak guards own that), and nothing at all about the unbounded frame byte, which
no guard in the tree closes.
"""

import pathlib
import re
import sys

import pytest

TOOLS = pathlib.Path(__file__).resolve().parent
ROOT = TOOLS.parent

# ------------------------------------------------------------------------------
# THE REGISTRY: (module, mappings blob const, DPLC blob const).
#
# A row is a claim that these two tables are indexed by one `mapping_frame` byte. This
# file cannot check that claim -- see the docstring. What it enforces is that the claim
# exists, that both guards are present, and that they name these two blobs and no
# others.
# ------------------------------------------------------------------------------
PAIRS = {
    ("games/sonic4/data/collision/collision_data.emp", "_map_sonic", "_dplc_sonic"),
    ("games/sonic4/data/characters/tails_data.emp", "_map_tails", "_dplc_tails"),
    ("games/sonic4/data/characters/tails_data.emp", "_map_tail", "_dplc_tail"),
    ("games/sonic4/data/characters/knuckles_data.emp", "_map_knux", "_dplc_knux"),
    ("games/sonic4/data/dust_data.emp", "_map_spindash", "_dplc_dust"),
    ("games/sonic4/player/player_instashield.emp", "_map_insta", "_dplc_insta"),
}

# Mappings blobs with NO DPLC, each with the reason. An asset drawn from art DMA'd
# resident once has no per-frame loading to disagree with, so pairing it with some
# other asset's DPLC would be a guard that passes or fails for reasons connected to
# neither table. Exempting one is a deliberate act of stating why.
NO_DPLC = {
    ("games/sonic4/data/dust_data.emp", "_map_puff"):
        "the puff block is DMA'd RESIDENT once (games/sonic4/objects/dust_puff.emp "
        "calls no Perform_DPLC); its length is guarded by DUST_PUFF_ART_LEN instead",
}

# A blob path is a mappings/DPLC table if it lives under one of these directories or
# carries one of these basename prefixes. Both spellings exist in the tree (hand-placed
# blobs under data/mappings + data/dplc, generated ones under data/generated/dust with
# map_/dplc_ prefixes), and a new asset could reasonably use either.
MAP_PAT = re.compile(r"(?:/mappings/|/map_[^/]*\.bin$)")
DPLC_PAT = re.compile(r"(?:/dplc/|/dplc_[^/]*\.bin$)")

EMBED_RE = re.compile(r"^\s*(?:pub\s+)?const\s+(\w+)\s*=\s*embed\(\"([^\"]+)\"\)", re.M)

# `ensure(` bodies span lines; flatten before matching. Arguments are captured as whole
# tokens so a drifted blob name is distinguishable from the right one.
COUNT_RE = re.compile(
    r"ensure\(\s*offset_table_frames\(\s*(\w+)\s*\)\s*==\s*offset_table_frames\(\s*(\w+)\s*\)\s*,"
    r"\s*\"(.*?)\"\s*\)")
EMPTY_RE = re.compile(
    r"ensure\(\s*empty_frame_mismatches\(\s*(\w+)\s*,\s*(\w+)\s*,[^\"]*?\)\s*==\s*0\s*,"
    r"\s*\"(.*?)\"\s*\)")

SHARED_HELPERS = ("offset_table_frames", "map_frame_pieces", "dplc_frame_entries",
                  "empty_frame_mismatches")


def emp_sources() -> list[pathlib.Path]:
    """Every .emp under engine/ and games/ EXCEPT the poison directory, whose modules
    are unreachable fixtures modelling broken inputs on purpose."""
    out = []
    for d in ("engine", "games"):
        for p in sorted((ROOT / d).rglob("*.emp")):
            if "/test/poison/" not in p.relative_to(ROOT).as_posix():
                out.append(p)
    return out


def flat(p: pathlib.Path) -> str:
    """Source with FULL-LINE `//` comments dropped, then whitespace-flattened.

    Dropping them is load-bearing, not tidying. Without it the usage example in
    engine/objects/dplc.emp's own header block matched as a seventh guard -- and the
    same leniency would let a guard that had been COMMENTED OUT still count as present,
    which is the exact vacuity this file exists to refuse. Only whole-line comments are
    stripped: a trailing `//` cannot be removed without a real lexer (an ensure message
    may contain one), and no guard in this tree has an interior comment line.
    """
    keep = [ln for ln in p.read_text().splitlines() if not ln.lstrip().startswith("//")]
    return " ".join(" ".join(keep).split())


def embedded_tables() -> tuple[set, set]:
    """({(module, const)} mappings, {(module, const)} DPLC) straight out of the sources."""
    maps, dplcs = set(), set()
    for p in emp_sources():
        rel = p.relative_to(ROOT).as_posix()
        for const, path in EMBED_RE.findall(p.read_text()):
            if MAP_PAT.search(path):
                maps.add((rel, const))
            elif DPLC_PAT.search(path):
                dplcs.add((rel, const))
    return maps, dplcs


def found(pattern: re.Pattern) -> dict:
    """{(module, map const, dplc const): message} for every guard of that shape."""
    out = {}
    for p in emp_sources():
        rel = p.relative_to(ROOT).as_posix()
        for a, b, msg in pattern.findall(flat(p)):
            out[(rel, a, b)] = msg
    return out


# ------------------------------------------------------------------------------
# 1. THE POPULATION
# ------------------------------------------------------------------------------
def test_every_embedded_mappings_blob_is_paired_or_explicitly_exempt():
    """A new asset cannot arrive with a mappings table nothing binds.

    This is the check that would have caught the state this parcel found: five blobs
    embedded, one guarded, and nothing anywhere that noticed.
    """
    maps, _ = embedded_tables()
    registered = {(m, mc) for m, mc, _ in PAIRS}
    orphans = sorted(maps - registered - set(NO_DPLC))
    assert not orphans, (
        "mappings blob(s) neither registered as half of a pair in PAIRS nor exempted in "
        "NO_DPLC:\n  " + "\n  ".join(f"{m}: {c}" for m, c in orphans)
        + "\n(register it with the DPLC blob its mapping_frame byte also indexes, or "
          "exempt it with the reason it has no DPLC -- resident art, say)")


def test_every_embedded_dplc_blob_is_registered():
    """The other direction. A DPLC blob outside every pair is a table whose frame count
    is bound to nothing, which is the same defect seen from the loading side."""
    _, dplcs = embedded_tables()
    registered = {(m, dc) for m, _, dc in PAIRS}
    orphans = sorted(dplcs - registered)
    assert not orphans, (
        "DPLC blob(s) with no row in PAIRS:\n  "
        + "\n  ".join(f"{m}: {c}" for m, c in orphans)
        + "\n(register it with the mappings blob its mapping_frame byte also indexes)")


def test_the_registry_names_only_blobs_that_are_actually_embedded():
    """A row naming a deleted or renamed const would make the gates below fail for the
    wrong reason, or -- worse -- pass because both halves went away together."""
    maps, dplcs = embedded_tables()
    bad = []
    for mod, mc, dc in sorted(PAIRS):
        if (mod, mc) not in maps:
            bad.append(f"{mod}: `{mc}` is not an embedded mappings blob there")
        if (mod, dc) not in dplcs:
            bad.append(f"{mod}: `{dc}` is not an embedded DPLC blob there")
    for (mod, mc), reason in sorted(NO_DPLC.items()):
        if (mod, mc) not in maps:
            bad.append(f"{mod}: exempt `{mc}` is not an embedded mappings blob there")
        if not reason.strip():
            bad.append(f"{mod}: exempt `{mc}` carries no reason")
    assert not bad, "\n  ".join(bad)


# ------------------------------------------------------------------------------
# 2. THE REGISTRY
# ------------------------------------------------------------------------------
def test_every_pair_carries_the_frame_count_binding():
    """THE GATE. This is the guard that stops the out-of-bounds read.

    Both directions: a pair with no guard is unprotected, and a guard with no row is
    one whose arguments nobody deliberately chose.
    """
    got = set(found(COUNT_RE))
    assert got == PAIRS, (
        "pairs with no `offset_table_frames(map) == offset_table_frames(dplc)` guard: "
        + str(sorted(PAIRS - got))
        + "\n(the shorter table is read past its end without it)"
        + "\nguards whose (module, map, dplc) triple is not a registered pair: "
        + str(sorted(got - PAIRS))
        + "\n(a guard comparing two blobs that are not one asset's pair passes or fails "
          "for a reason connected to neither)")


def test_every_pair_carries_the_empty_frame_agreement():
    """The weaker, per-frame guard -- stated for every pair for the same reason: a
    check that pins one member of a family and not its siblings is the defect."""
    got = set(found(EMPTY_RE))
    assert got == PAIRS, (
        "pairs with no `empty_frame_mismatches(map, dplc, ...) == 0` guard: "
        + str(sorted(PAIRS - got))
        + "\nguards whose triple is not a registered pair: " + str(sorted(got - PAIRS)))


# ------------------------------------------------------------------------------
# 3. THE HELPERS
# ------------------------------------------------------------------------------
def test_the_parsers_are_the_shared_ones_and_are_not_re_privatised():
    """The state this parcel removed was a working set of parsers usable by one file.

    A module defining its own copy would build green and drift; and a module NAMING one
    without importing it is the EMP_PITFALLS §2 trap in its silent form -- a comptime
    fn's free names resolve at the call site, so a half-imported helper does not error,
    it computes the wrong number (measured 2026-09-07: `empty_frame_mismatches` with one
    of its two sibling parsers in scope counted every drawn frame as a mismatch).
    """
    owner = "engine/objects/dplc.emp"
    bad = []
    for p in emp_sources():
        rel = p.relative_to(ROOT).as_posix()
        if rel == owner:
            continue
        txt = p.read_text()
        for name in SHARED_HELPERS:
            if not re.search(rf"(?<![\w]){re.escape(name)}(?![\w])", txt):
                continue
            if re.search(rf"^\s*(?:pub\s+)?comptime\s+fn\s+{re.escape(name)}\b", txt, re.M):
                bad.append(f"{rel} defines its own `{name}` beside the shared one in "
                           f"{owner} -- that is the state LS-9 removed")
            if not re.search(rf"use\s+engine\.objects\.dplc\.\{{[^}}]*{re.escape(name)}",
                             txt, re.S):
                bad.append(f"{rel} names `{name}` without importing it from "
                           f"engine.objects.dplc")
    assert not bad, "\n  ".join(bad)


def test_the_owner_module_exports_every_shared_helper():
    """A helper that stopped being `pub` would re-create the original defect exactly:
    the checks still work, for one file."""
    txt = (ROOT / "engine/objects/dplc.emp").read_text()
    missing = [n for n in SHARED_HELPERS
               if not re.search(rf"^pub\s+comptime\s+fn\s+{re.escape(n)}\b", txt, re.M)]
    assert not missing, (
        f"engine/objects/dplc.emp no longer exports {missing} as `pub comptime fn` -- "
        "a private parser is usable by its own module only, which is the LS-9 defect")


# ------------------------------------------------------------------------------
# 4. THE MESSAGE
# ------------------------------------------------------------------------------
@pytest.mark.parametrize("pattern,label", [(COUNT_RE, "frame-count"),
                                           (EMPTY_RE, "empty-frame")])
def test_every_guard_states_what_it_does_not_cover(pattern, label):
    """The 2026-09-06 sweep's dominant finding: a guard message read as broader than the
    guard. These two bind two tables TO EACH OTHER; neither bounds the frame byte the
    animator writes, and a reader must not have to work that out."""
    silent = [f"{mod}: {mc}/{dc}" for (mod, mc, dc), msg in sorted(found(pattern).items())
              if "does not cover" not in msg.lower()]
    assert not silent, (
        f"{label} guard message(s) that do not state their limits:\n  "
        + "\n  ".join(silent)
        + "\n(say what the guard does NOT measure -- above all that AnimateSprite bounds "
          "no frame byte, so two tables agreeing with each other are still both overrun "
          "by a script byte >= their common count. LS-9a)")


# ------------------------------------------------------------------------------
# THE ANTI-VACUITY WITNESS
# ------------------------------------------------------------------------------
def test_the_sweep_actually_found_something():
    """Guard the guards: a regex that stopped matching would empty every enumeration
    above and turn the registry checks into comparisons of empty-ish sets. State the
    counts as machine facts so that failure is loud rather than green."""
    assert len(emp_sources()) > 100, (
        f"only {len(emp_sources())} .emp sources swept -- the enumeration is broken")
    maps, dplcs = embedded_tables()
    assert len(maps) == 7, (
        f"found {len(maps)} embedded mappings blobs; this tree has 7 (Sonic, Tails, the "
        "Tails appendage, Knuckles, the dust charge half, the dust puff, the "
        f"insta-shield): {sorted(maps)}")
    assert len(dplcs) == 6, (
        f"found {len(dplcs)} embedded DPLC blobs; this tree has 6 -- one per mappings "
        f"blob except the resident puff: {sorted(dplcs)}")
    assert len(PAIRS) == 6 and len(NO_DPLC) == 1
    assert len(found(COUNT_RE)) == 6 and len(found(EMPTY_RE)) == 6, (
        f"found {len(found(COUNT_RE))} frame-count and {len(found(EMPTY_RE))} "
        "empty-frame guards; both must be 6")


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
