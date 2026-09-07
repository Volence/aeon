"""VRAM residency guards: the ceiling must be the region's OWN declared extent.

WHY THIS FILE EXISTS (LS-4 / C2a-H1, 2026-09-06 sweep, closed 2026-09-07).

tools/gen_vram_map.py used to publish only a region's BASE. A module asking "does my
art fit my window?" therefore had no name for its own extent, and reached for whatever
bound happened to be in its `use` line -- the NEXT region's base. Two ceilings were
measured three tiles too permissive that way (the Tails appendage against
VRAM_HSCROLL_TABLE / TILE_SIZE, the insta-shield against VRAM_TEST_SONIC), each having
gone wrong SILENTLY when gen_vram_map.py later allocated a region into the gap. The
generator now emits `<CONST>_TILES` beside every `<CONST>`, so the correct ceiling
arrives in the same import as the base.

**Emitting the name is not the closure.** The defect was that a wrong-but-in-scope
symbol was the convenient one, and after the fix a future author can still write
`peak <= SOME_OTHER_REGION_TILES` and build green. THIS FILE is what refuses that: it
enumerates every residency guard in the tree, requires each to be REGISTERED against
the region it actually writes, and requires its ceiling to be that region's `_TILES`.
A new guard cannot arrive unregistered, and registering one is a deliberate act of
naming a region rather than picking a bound off the import list.

Five layers:

1. THE EMISSION. Every `const`-declaring region in every game's vram.toml publishes
   BOTH names, and `_TILES` equals the TOML's `tiles`. Read from the TOML and from the
   committed generated block -- neither number is typed here.
2. THE REGISTRY. Every `ensure(... dplc_peak_tiles(X) <= C ...)` in the tree, matched
   against a pinned (module, blob, region) table. Unregistered guard, missing guard, or
   a ceiling that is not the registered region's `_TILES`: all failures.
3. THE IMPORT. A module naming a `_TILES` constant must import it from that game's
   constants module -- never restate the number beside the name.
4. THE RESIDENT DMAs. A `*_ART_LEN` that feeds a whole-region DMA must equal that
   region's span x TILE_SIZE, computed from vram.toml. Two of them legitimately span
   TWO regions; the registry records the span, which is the part no `.emp` ensure can
   state (the second region in both cases has no `const`, so it has no `_TILES`).
5. THE MESSAGE. Every registered guard's ensure message must say what it does NOT
   cover -- the sweep's dominant finding was guards read as broader than they are.

WHAT THIS FILE DOES NOT COVER. It cannot tell you a REGISTRY ROW is right: that the
region a guard is pinned to is the region its DMA actually targets is a fact about the
load site, not about this text, and nothing here reads a load site. What it makes
impossible is a guard drifting off its registered region, or arriving with no row at
all. It also says nothing about DMA queue-slot cost, run-time residency overlap
between two regions with different lifetimes, or whether a region is correctly PLACED
(gen_vram_map.py's own coverage/overlap checks own that).
"""

import pathlib
import re
import sys
import tomllib

import pytest

TOOLS = pathlib.Path(__file__).resolve().parent
ROOT = TOOLS.parent
GAMES = ("sonic4", "demo")

MARK_BEGIN = "// >>> GENERATED: vram map (tools/gen_vram_map.py) — DO NOT HAND-EDIT <<<"
MARK_END = "// <<< GENERATED: vram map END >>>"


def emp_const(rel: str, name: str) -> int:
    """A `const NAME = <int>` read out of an .emp source. A miss is a LOUD failure.

    Same contract as tools/test_dplc_tile_start.py's reader: a value this cannot find
    must never fall back to a default, because a bound computed from a default passes
    or fails for a reason unrelated to the source it claims to track.
    """
    txt = (ROOT / rel).read_text()
    m = re.search(rf"^\s*(?:pub\s+)?const\s+{re.escape(name)}\s*=\s*(\$[0-9A-Fa-f]+|\d+)",
                  txt, re.M)
    assert m, (f"cannot find `const {name}` in {rel} -- every bound in this file is "
               "folded from it, and a guessed value would make all of them vacuous")
    v = m.group(1)
    return int(v[1:], 16) if v.startswith("$") else int(v)


TILE_SIZE = emp_const("engine/system/constants.emp", "TILE_SIZE")


def regions(game: str) -> dict[str, dict]:
    """{region name: row} straight out of the game's declared placement contract."""
    with open(ROOT / "games" / game / "vram.toml", "rb") as f:
        return {r["name"]: r for r in tomllib.load(f)["region"]}


def generated_block(game: str) -> str:
    txt = (ROOT / "games" / game / "config" / "constants.emp").read_text()
    b, e = txt.find(MARK_BEGIN), txt.find(MARK_END)
    assert 0 <= b < e, (f"games/{game}/config/constants.emp has no well-formed "
                        "GENERATED vram-map marker pair")
    return txt[b:e]


def emitted_consts(game: str) -> dict[str, int]:
    """{name: value} for every `pub const` inside the generated vram-map block."""
    out = {}
    for m in re.finditer(r"^pub const\s+(\w+)\s*(?::\s*\w+\s*)?=\s*(\$[0-9A-Fa-f]+|\d+)",
                         generated_block(game), re.M):
        v = m.group(2)
        out[m.group(1)] = int(v[1:], 16) if v.startswith("$") else int(v)
    return out


# ------------------------------------------------------------------------------
# 1. THE EMISSION
# ------------------------------------------------------------------------------
@pytest.mark.parametrize("game", GAMES)
def test_every_const_region_publishes_its_declared_extent(game):
    """Base and extent are two halves of one declaration; publishing one is the bug.

    The set is exactly the regions that declare a `const` -- i.e. the ones a game
    module can name at all, which is the same set that can carry this defect. An
    engine-owned region cross-checked by an `authority` form is deliberately NOT in it:
    its extent already has an engine-side constant (POOL_TILE_CEILING,
    BG_TILE_CAPACITY), and a second name for one number is the drift this generator
    exists to prevent.
    """
    consts = emitted_consts(game)
    missing = []
    for name, r in regions(game).items():
        c = r.get("const")
        if not c:
            continue
        if c not in consts:
            missing.append(f"{name}: base const {c} is not emitted")
        elif consts[c] != r["base"]:
            missing.append(f"{name}: {c} = {consts[c]}, vram.toml base is {r['base']}")
        t = c + "_TILES"
        if t not in consts:
            missing.append(f"{name}: extent const {t} is not emitted -- a residency "
                           "guard has no name for this region's own size and will "
                           "reach for a neighbour's base (LS-4)")
        elif consts[t] != r["tiles"]:
            missing.append(f"{name}: {t} = {consts[t]}, vram.toml tiles is {r['tiles']}")
    assert not missing, (
        f"games/{game}/config/constants.emp's generated block disagrees with "
        f"games/{game}/vram.toml:\n  " + "\n  ".join(missing) +
        "\nRegenerate with tools/gen_vram_map.py (the command is in the block header).")


@pytest.mark.parametrize("game", GAMES)
def test_no_extent_is_emitted_for_a_region_that_declares_no_const(game):
    """The emission set is EXACTLY the declared one -- no orphan `_TILES` names.

    An extent published for a region no module can name is dead weight, and a dead
    generated name is one a future guard can reach for by accident.
    """
    declared = {r["const"] + "_TILES" for r in regions(game).values() if r.get("const")}
    emitted = {n for n in emitted_consts(game) if n.endswith("_TILES")}
    assert emitted == declared, (
        f"games/{game}: extents emitted for regions that declare no const: "
        f"{sorted(emitted - declared)}; declared regions with no extent: "
        f"{sorted(declared - emitted)}")


# ------------------------------------------------------------------------------
# 2. THE REGISTRY
# ------------------------------------------------------------------------------
# (module, DPLC blob const, sonic4 region the guarded art is DMA'd into).
#
# A ROW IS A CLAIM ABOUT A LOAD SITE, and this file cannot check that claim -- see the
# module docstring. What it enforces is that the claim exists and that the guard agrees
# with it, so a guard cannot silently move to a different region's ceiling and a new
# character cannot arrive with a ceiling picked off its import list.
DPLC_GUARDS = {
    ("games/sonic4/data/collision/collision_data.emp", "_dplc_sonic"): "character_window",
    ("games/sonic4/data/characters/tails_data.emp", "_dplc_tails"): "character_window",
    ("games/sonic4/data/characters/knuckles_data.emp", "_dplc_knux"): "character_window",
    ("games/sonic4/data/characters/tails_data.emp", "_dplc_tail"): "tails_appendage",
    ("games/sonic4/player/player_instashield.emp", "_dplc_insta"): "insta_shield",
    ("games/sonic4/data/dust_data.emp", "_dplc_dust"): "dust_spindash",
}

# `ensure(` bodies span lines; flatten before matching. The ceiling is captured as a
# whole token so a literal, an expression or a foreign name are all distinguishable
# from the one accepted form.
PEAK_RE = re.compile(
    r"ensure\(\s*dplc_peak_tiles\(\s*(\w+)\s*\)\s*<=\s*([^,]+?)\s*,\s*\"(.*?)\"\s*\)")


def emp_sources() -> list[pathlib.Path]:
    """Every .emp under engine/ and games/ EXCEPT the poison directory, whose modules
    are unreachable fixtures modelling broken inputs on purpose."""
    out = []
    for d in ("engine", "games"):
        for p in sorted((ROOT / d).rglob("*.emp")):
            if "/test/poison/" not in p.relative_to(ROOT).as_posix():
                out.append(p)
    return out


def found_guards() -> dict[tuple[str, str], tuple[str, str]]:
    """{(module, blob): (ceiling token, message)} for every residency guard found."""
    out = {}
    for p in emp_sources():
        flat = " ".join(p.read_text().split())
        for blob, ceiling, msg in PEAK_RE.findall(flat):
            out[(p.relative_to(ROOT).as_posix(), blob)] = (ceiling, msg)
    return out


def test_every_residency_guard_is_registered_and_none_went_missing():
    """Both directions. An unregistered guard picked its ceiling off an import list;
    a registered guard that vanished means a window stopped being checked at all."""
    found = set(found_guards())
    assert found == set(DPLC_GUARDS), (
        "residency guards with no row in DPLC_GUARDS: " + str(sorted(found - set(DPLC_GUARDS)))
        + "\n(add a row naming the vram.toml region this art is DMA'd into -- the point "
          "is that choosing the region is deliberate, not whatever bound was in scope)"
        + "\nregistered guards no longer present: " + str(sorted(set(DPLC_GUARDS) - found))
        + "\n(if a guard really moved, move its row; a silent drop means that window "
          "is unchecked)")


def test_every_residency_guard_binds_its_OWN_regions_declared_extent():
    """THE GATE. The ceiling must be `<the region's const>_TILES` and nothing else.

    A neighbour's base, an engine table address divided by TILE_SIZE, and a bare
    integer are the three spellings this tree actually shipped; all three fail here.
    """
    rs = regions("sonic4")
    wrong = []
    for (mod, blob), region in sorted(DPLC_GUARDS.items()):
        got = found_guards().get((mod, blob))
        if got is None:
            continue                       # the test above reports this
        want = rs[region]["const"] + "_TILES"
        if got[0] != want:
            wrong.append(f"{mod}: dplc_peak_tiles({blob}) is bounded by `{got[0]}`, "
                         f"but it is registered against region `{region}`, whose "
                         f"declared extent is `{want}`")
    assert not wrong, (
        "residency guard(s) not bound to their own region's declared extent -- this is "
        "the LS-4 defect exactly:\n  " + "\n  ".join(wrong))


def test_the_registry_names_only_regions_that_exist_and_publish_an_extent():
    """A row pointing at a deleted or const-less region would make the gate above
    fail for the wrong reason, or crash instead of reporting."""
    rs = regions("sonic4")
    bad = [f"{mod}: region `{region}` " +
           ("is not in games/sonic4/vram.toml" if region not in rs
            else "declares no `const`, so it publishes no extent to bind against")
           for (mod, _), region in sorted(DPLC_GUARDS.items())
           if region not in rs or not rs[region].get("const")]
    assert not bad, "\n  ".join(bad)


# ------------------------------------------------------------------------------
# 3. THE IMPORT
# ------------------------------------------------------------------------------
def test_every_extent_a_module_names_is_imported_not_restated():
    """A `_TILES` name must come from the game's constants module.

    Its whole value is being the ONE spelling of the region's size; a local `const
    VRAM_X_TILES = 9` beside the imported name is the copy that keeps building green
    after vram.toml moves.
    """
    all_extents = {n for g in GAMES for n in emitted_consts(g) if n.endswith("_TILES")}
    bad = []
    for p in emp_sources():
        rel = p.relative_to(ROOT).as_posix()
        if rel.startswith("games/") and rel.endswith("config/constants.emp"):
            continue                        # the emitting module itself
        txt = p.read_text()
        for name in sorted(all_extents):
            if not re.search(rf"(?<![\w]){re.escape(name)}(?![\w])", txt):
                continue
            if re.search(rf"^\s*(?:pub\s+)?const\s+{re.escape(name)}\s*=", txt, re.M):
                bad.append(f"{rel} defines its own `{name}` beside the generated one")
            if not re.search(rf"use\s+games\.\w+\.constants\.\{{[^}}]*{re.escape(name)}",
                             txt, re.S):
                bad.append(f"{rel} names `{name}` without importing it from "
                           "games.<game>.constants")
    assert not bad, "\n  ".join(bad)


# ------------------------------------------------------------------------------
# 4. THE RESIDENT DMAs
# ------------------------------------------------------------------------------
# (game, module, byte-length const) -> the regions the DMA covers, IN ORDER.
#
# A one-region entry is also stated as an `.emp` ensure in its own module (that is what
# refuses the C2a-H1c repair at build time, in every shape, without pytest). The
# TWO-region entries can only live here: their second region declares no `const`, so it
# publishes no `_TILES` for an ensure to name. Both are deliberate multi-region blobs
# and both say so at their definition.
RESIDENT_DMAS = {
    ("sonic4", "games/sonic4/objects/ring_sparkle.emp", "RING_SPARKLE_ART_LEN"):
        ["ring_sparkle"],
    ("sonic4", "games/sonic4/data/dust_data.emp", "DUST_PUFF_ART_LEN"):
        ["dust_puff"],
    ("sonic4", "games/sonic4/test/ojz_scroll_test.emp", "TEST_ART_LEN"):
        ["test_obj", "ring_placeholder"],
    ("demo", "games/demo/demo_state.emp", "DEMO_ART_LEN"):
        ["demo_obj", "ring_placeholder"],
}


# `*_ART_LEN` constants that are NOT a whole-region DMA length, each with the reason.
# The registry above only checks what is in it, so without this an art-length constant
# could arrive unregistered and be measured by nothing -- the same "a new one can skip
# the guard" hole DPLC_GUARDS closes for residency guards.
NOT_A_DMA_LENGTH = {
    # a COMPONENT of TEST_ART_LEN (the ring blob tailing the two colour squares), not
    # a DMA of its own; the DMA that consumes it is registered as TEST_ART_LEN.
    ("games/sonic4/test/ojz_scroll_test.emp", "RING_ART_LEN"),
}

ART_LEN_RE = re.compile(r"^\s*(?:pub\s+)?const\s+(\w+_ART_LEN)\s*=", re.M)


def test_every_art_length_constant_is_registered_or_explicitly_exempt():
    """A new resident-art DMA cannot arrive with its length measured by nothing."""
    registered = {(rel, name) for _, rel, name in RESIDENT_DMAS}
    orphans = []
    for p in emp_sources():
        rel = p.relative_to(ROOT).as_posix()
        if not rel.startswith("games/"):
            continue
        for name in ART_LEN_RE.findall(p.read_text()):
            if (rel, name) not in registered and (rel, name) not in NOT_A_DMA_LENGTH:
                orphans.append(f"{rel}: {name}")
    assert not orphans, (
        "art-length constant(s) neither registered in RESIDENT_DMAS nor listed in "
        "NOT_A_DMA_LENGTH:\n  " + "\n  ".join(orphans)
        + "\n(register it with the vram.toml region(s) its DMA covers, or exempt it "
          "with the reason it is not a DMA length)")


def _const_expr(rel: str, name: str) -> str:
    m = re.search(rf"^\s*(?:pub\s+)?const\s+{re.escape(name)}\s*=\s*([^/\n]+)",
                  (ROOT / rel).read_text(), re.M)
    assert m, f"{rel} no longer defines `{name}` -- its DMA length is unmeasured"
    return m.group(1).strip()


def test_resident_dma_lengths_match_the_span_they_are_written_into():
    """The byte length of a whole-region DMA against the map's own arithmetic.

    A DMA longer than its destination span writes into the next region and the symptom
    lands in an unrelated object's art (C2a-H1c). A DMA SHORTER than its span is not an
    error here -- a region may legitimately hold more than one blob -- so this asserts
    equality only where the registry says the blob fills the span, which is all four
    of today's entries.
    """
    bad = []
    for (game, rel, name), span in sorted(RESIDENT_DMAS.items()):
        rs = regions(game)
        missing = [r for r in span if r not in rs]
        assert not missing, f"{rel}: registry names region(s) {missing} not in {game}'s map"
        # contiguity: a "span" that is not contiguous cannot be one DMA
        for a, b in zip(span, span[1:]):
            assert rs[a]["base"] + rs[a]["tiles"] == rs[b]["base"], (
                f"{rel}: `{name}` is registered as spanning {a} then {b}, but they are "
                f"not adjacent in games/{game}/vram.toml -- one DMA cannot cover both")
        tiles = sum(rs[r]["tiles"] for r in span)
        expr = _const_expr(rel, name)
        env = {"TILE_SIZE": TILE_SIZE}
        # the constants are pure integer arithmetic over TILE_SIZE and named siblings
        for sib in re.findall(r"[A-Z_][A-Z0-9_]*", expr):
            if sib not in env:
                env[sib] = int(_const_expr(rel, sib))
        got = eval(expr, {"__builtins__": {}}, env)   # noqa: S307 - our own source
        if got != tiles * TILE_SIZE:
            bad.append(f"{rel}: {name} = {got} B, but {'+'.join(span)} is {tiles} tiles "
                       f"= {tiles * TILE_SIZE} B in games/{game}/vram.toml")
    assert not bad, (
        "resident DMA length(s) that do not match their destination span -- the DMA "
        "would run past the last region into its neighbour:\n  " + "\n  ".join(bad))


# ------------------------------------------------------------------------------
# 5. THE MESSAGE
# ------------------------------------------------------------------------------
def test_every_residency_guard_states_what_it_does_not_cover():
    """The 2026-09-06 sweep's dominant finding: a guard message read as broader than
    the guard. A residency guard measures TILES; it does not measure queue slots, the
    straddle split, the sibling characters sharing one window, or placement."""
    silent = [f"{mod}: dplc_peak_tiles({blob})"
              for (mod, blob), (_, msg) in sorted(found_guards().items())
              if "does not cover" not in msg.lower()]
    assert not silent, (
        "residency guard message(s) that do not state their limits:\n  "
        + "\n  ".join(silent)
        + "\n(say what the guard does NOT measure -- queue slots, the straddle split, "
          "the siblings sharing the window, placement -- so a reader cannot over-read "
          "a green build)")


# ------------------------------------------------------------------------------
# THE ANTI-VACUITY WITNESS
# ------------------------------------------------------------------------------
def test_the_sweep_actually_found_something():
    """Guard the guards: every test above passes trivially over an empty enumeration.

    A regex that stopped matching (an `ensure` reformatted, `dplc_peak_tiles` renamed)
    would empty `found_guards()` and turn the registry check into a comparison of two
    empty-ish sets -- which the registry's own both-directions assert catches, but only
    because DPLC_GUARDS is non-empty. State both counts as machine facts.
    """
    assert len(emp_sources()) > 100, (
        f"only {len(emp_sources())} .emp sources swept -- the enumeration is broken")
    assert len(found_guards()) == len(DPLC_GUARDS) == 6, (
        f"found {len(found_guards())} residency guards against {len(DPLC_GUARDS)} "
        "registered; both must be the 6 this tree carries")
    total = sum(len(emitted_consts(g)) for g in GAMES)
    assert total == 26, (
        f"the generated vram-map blocks emit {total} constants across {GAMES}; "
        "12 base + 12 extent for sonic4 and 1 + 1 for demo is 26")


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
