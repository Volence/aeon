"""The 12-bit DPLC tile_start ceiling: the generic half of the guard.

engine/objects/dplc.emp names the field width ONCE (DPLC_TILE_START_BITS) and six art
modules state `art tiles <= DPLC_ADDRESSABLE_TILES` against it. Those six `ensure`s are
build-fatal and they are the part that stops a bad tree from assembling -- but they are
six sites, and a seventh character can arrive without one. This file is the site that
cannot be skipped: it ENUMERATES the modules that embed a DPLC table, finds the art
sheets they embed, and asks the question itself.

WHY THE CHECK IS ON THE ART SHEET AND NOT ON THE TABLE, which is the first thing anyone
reading this will want to change. A stored tile_start is the low 12 bits of a 16-bit
entry word, so `word & 0xFFF` is <= 4095 for every possible input -- there is no blob,
valid or corrupt, that can drive "max tile_start <= DPLC_TILE_START_MAX" red. It is a
gate that cannot fail. The overflow happens in the PRODUCER: a tile index >= 4096 is
packed into 12 bits and what reaches the file is the wrapped, legal-looking low index,
which is exactly how the Knuckles `_opt` defect shipped (25 entries across frames
234-250 loading early-frame art, found by reconstructing frames from the ART).
test_the_blob_side_check_is_vacuous below states that as a machine fact rather than as
a paragraph, so the vacuous version cannot be re-added as an improvement.

Four layers:

1. THE DERIVATION. DPLC_TILE_START_BITS is read out of the .emp source and everything
   else is folded from it. 4095 and 4096 are not typed anywhere in this file.
2. THE ENUMERATION. Every .emp embedding a DPLC blob, every art sheet it embeds,
   measured from the shipped bytes against the folded ceiling.
3. THE COVERAGE. Each enumerated art sheet must ALSO carry the build-fatal `ensure` in
   its own module. This is what a new character cannot skip: the module is found by its
   DPLC embed, not by a list maintained here.
4. THE SPELLING. The runtime mask in perform_dplc and both Python producers' asserts
   must agree with the one name, so the five restatements the parcel collapsed cannot
   quietly reappear.
"""

import pathlib
import re
import sys

import pytest

TOOLS = pathlib.Path(__file__).resolve().parent
ROOT = TOOLS.parent

DPLC_EMP = ROOT / "engine" / "objects" / "dplc.emp"
TILE_SIZE = 32          # engine/system/constants.emp; pinned by test_tile_size_matches_source


# --------------------------------------------------------------------------------
# 1. THE DERIVATION
# --------------------------------------------------------------------------------
def emp_const(rel: str, name: str) -> int:
    """A `const NAME = <int>` read out of an .emp source. A miss is a LOUD failure.

    Same contract as tools/emp_expect_fail.py's reader and for the same reason: a value
    this cannot find must never fall back to a default, because a gate computed from a
    default passes or fails for a reason unrelated to the source it claims to track.
    """
    txt = (ROOT / rel).read_text()
    m = re.search(rf"^\s*(?:pub\s+)?const\s+{re.escape(name)}\s*=\s*(\$[0-9A-Fa-f]+|\d+)",
                  txt, re.M)
    assert m, (f"cannot find `const {name}` in {rel} -- every bound in this file is "
               "folded from it, and a guessed value would make all of them vacuous")
    v = m.group(1)
    return int(v[1:], 16) if v.startswith("$") else int(v)


TILE_START_BITS = emp_const("engine/objects/dplc.emp", "DPLC_TILE_START_BITS")
TILE_COUNT_BITS = emp_const("engine/objects/dplc.emp", "DPLC_TILE_COUNT_BITS")
TILE_START_MAX = (1 << TILE_START_BITS) - 1
ADDRESSABLE_TILES = TILE_START_MAX + 1
MAX_TILES_PER_ENTRY = 1 << TILE_COUNT_BITS


def test_tile_size_matches_source():
    assert TILE_SIZE == emp_const("engine/system/constants.emp", "TILE_SIZE")


def test_the_two_fields_are_the_whole_entry_word():
    """The .emp guard's twin. A widened tile_start has to come out of the count."""
    assert TILE_COUNT_BITS + TILE_START_BITS == 16, (
        f"{TILE_COUNT_BITS} count bits + {TILE_START_BITS} tile_start bits is not a "
        "16-bit entry word")


def test_the_emp_constants_fold_from_the_one_name():
    """DPLC_TILE_START_MAX / DPLC_ADDRESSABLE_TILES must be EXPRESSIONS, not literals.

    A guard whose ceiling is typed as 4095 beside a width named as 12 is two facts that
    can drift; the whole point of the parcel is that there is one.
    """
    txt = DPLC_EMP.read_text()
    for name, expected in (
        ("DPLC_TILE_START_MAX", "(1 << DPLC_TILE_START_BITS) - 1"),
        ("DPLC_ADDRESSABLE_TILES", "DPLC_TILE_START_MAX + 1"),
        ("DPLC_MAX_TILES_PER_ENTRY", "1 << DPLC_TILE_COUNT_BITS"),
    ):
        m = re.search(rf"^\s*pub\s+const\s+{name}\s*=\s*([^/\n]+)", txt, re.M)
        assert m, f"{name} is gone from {DPLC_EMP.name}"
        assert m.group(1).strip() == expected, (
            f"{name} is `{m.group(1).strip()}`, expected `{expected}` -- it must FOLD "
            "from DPLC_TILE_START_BITS, never restate the number")


# --------------------------------------------------------------------------------
# 2. THE ENUMERATION
# --------------------------------------------------------------------------------
EMBED_RE = re.compile(r'^\s*const\s+(\w+)\s*=\s*embed\("([^"]+)"', re.M)

# The five modules that own a DPLC table today. Named so that a module LOSING its table
# is as loud as one arriving without a guard; modules beyond this set are still swept.
KNOWN_DPLC_MODULES = {
    "games/sonic4/data/collision/collision_data.emp",
    "games/sonic4/data/characters/tails_data.emp",
    "games/sonic4/data/characters/knuckles_data.emp",
    "games/sonic4/player/player_instashield.emp",
    "games/sonic4/data/dust_data.emp",
}


def _is_dplc(path: str) -> bool:
    return "/dplc" in path or pathlib.PurePath(path).name.startswith("dplc_")


def _is_art_sheet(path: str) -> bool:
    """An art sheet a DPLC could index -- NOT a palette, mapping or collision blob.

    Stated as a rule over the path rather than as a list of blob names, so a new
    character's sheet is swept the day it is embedded.
    """
    p = pathlib.PurePath(path)
    if p.parts[:2] == ("art", "palettes"):
        return False
    return p.parts[0] == "art" or p.name.startswith("art_")


def dplc_modules() -> dict[str, dict[str, list[tuple[str, str]]]]:
    """{module rel path: {"dplc": [(const, path)], "art": [(const, path)]}}.

    Every `.emp` under engine/ and games/ that embeds a DPLC blob -- EXCEPT the poison
    directory, whose modules are unreachable fixtures that deliberately model broken
    inputs (games/sonic4/test/poison/README.md).
    """
    out: dict[str, dict[str, list[tuple[str, str]]]] = {}
    for emp in sorted(list((ROOT / "engine").rglob("*.emp")) + list((ROOT / "games").rglob("*.emp"))):
        rel = emp.relative_to(ROOT).as_posix()
        if "/test/poison/" in rel:
            continue
        embeds = EMBED_RE.findall(emp.read_text())
        dplcs = [(c, p) for c, p in embeds if _is_dplc(p)]
        if not dplcs:
            continue
        out[rel] = {"dplc": dplcs, "art": [(c, p) for c, p in embeds if _is_art_sheet(p)]}
    return out


def test_the_known_dplc_modules_are_all_still_here():
    found = set(dplc_modules())
    missing = KNOWN_DPLC_MODULES - found
    assert not missing, (
        f"module(s) that owned a DPLC table no longer embed one: {sorted(missing)}. If a "
        "table really moved, move the name; a silent drop means these sheets stopped "
        "being swept.")


def test_every_dplc_module_embeds_at_least_one_art_sheet():
    """A DPLC with no sheet beside it means _is_art_sheet stopped recognising one."""
    for mod, e in dplc_modules().items():
        assert e["art"], (
            f"{mod} embeds {[p for _, p in e['dplc']]} but no art sheet was recognised -- "
            "the sweep below would silently measure nothing for this module")


def test_every_dplc_fed_art_sheet_fits_the_tile_start_ceiling():
    """THE GATE. Measured from the shipped bytes, against the folded ceiling.

    This is the same question the six `ensure`s ask, asked here where a new character
    cannot arrive without being asked it.
    """
    over = []
    for mod, e in dplc_modules().items():
        for const, path in e["art"]:
            tiles = (ROOT / path).stat().st_size // TILE_SIZE
            if tiles > ADDRESSABLE_TILES:
                over.append(f"{mod}: {const} ({path}) is {tiles} tiles, "
                            f"{tiles - ADDRESSABLE_TILES} past the {ADDRESSABLE_TILES}-tile "
                            f"ceiling a {TILE_START_BITS}-bit tile_start can name")
    assert not over, (
        "art sheet(s) a DPLC entry cannot fully address -- the producer will WRAP into "
        "the low tile indices and those frames will load early-frame art:\n  "
        + "\n  ".join(over))


def test_every_art_sheet_is_a_whole_number_of_tiles():
    """A truncated sheet makes the tile count above a lie in the safe-looking direction."""
    for mod, e in dplc_modules().items():
        for const, path in e["art"]:
            size = (ROOT / path).stat().st_size
            assert size % TILE_SIZE == 0, f"{mod}: {const} ({path}) is {size} B, not whole tiles"


def test_headroom_report(capsys):
    """Not an assertion -- the number the DEFERRED_WORK rider asked for, per sheet.

    Run `pytest tools/test_dplc_tile_start.py -s -k headroom` to read it.
    """
    with capsys.disabled():
        print(f"\n  tile_start is {TILE_START_BITS} bits -> ceiling {ADDRESSABLE_TILES} tiles")
        rows = []
        for mod, e in dplc_modules().items():
            for const, path in e["art"]:
                tiles = (ROOT / path).stat().st_size // TILE_SIZE
                rows.append((ADDRESSABLE_TILES - tiles, const, tiles, path))
        for spare, const, tiles, path in sorted(rows):
            print(f"  {const:<16} {tiles:>5} tiles  headroom {spare:>5} "
                  f"({spare * TILE_SIZE} B)  {path}")


# --------------------------------------------------------------------------------
# 3. THE COVERAGE
# --------------------------------------------------------------------------------
def test_every_dplc_fed_art_sheet_also_carries_the_build_fatal_ensure():
    """A new character cannot ship a sheet without the guard in its own module.

    The sweep above runs in the pytest lane; the `ensure` runs in EVERY sigil build,
    including one nobody ran pytest before. Both halves, or the guard is only as strong
    as whoever remembered to run the tests.
    """
    missing = []
    for mod, e in dplc_modules().items():
        txt = (ROOT / mod).read_text()
        # `ensure(...)` bodies span lines; flatten before looking for the pair.
        flat = " ".join(txt.split())
        for const, path in e["art"]:
            guarded = any(
                const in body and "DPLC_ADDRESSABLE_TILES" in body
                for body in re.findall(r"ensure\((.*?)\)\s*(?=ensure\(|pub |const |use |//|$)",
                                       flat)
            ) or bool(re.search(
                rf"{re.escape(const)}\.len\s*/\s*TILE_SIZE\s*<=\s*DPLC_ADDRESSABLE_TILES", flat))
            if not guarded:
                missing.append(f"{mod}: {const} ({path})")
    assert not missing, (
        "art sheet(s) fed by a DPLC with no `ensure(<const>.len / TILE_SIZE <= "
        "DPLC_ADDRESSABLE_TILES, ...)` in their own module:\n  " + "\n  ".join(missing)
        + "\n(engine/objects/dplc.emp explains the ceiling; copy the guard from "
          "games/sonic4/data/characters/knuckles_data.emp, which is the tightest.)")


def test_the_ensures_import_the_ceiling_rather_than_restating_it():
    for mod in dplc_modules():
        txt = (ROOT / mod).read_text()
        if "DPLC_ADDRESSABLE_TILES" not in txt:
            continue
        assert re.search(r"use\s+engine\.objects\.dplc\.\{[^}]*DPLC_ADDRESSABLE_TILES", txt,
                         re.S), (f"{mod} names DPLC_ADDRESSABLE_TILES without importing it "
                                 "from engine.objects.dplc")
        # CODE only. A prose paragraph may narrate the number (knuckles_data.emp's
        # header records what the `_opt` layout measured); what must not exist is a
        # second SPELLING of the ceiling that the compiler reads, because that is the
        # copy that keeps building green after DPLC_TILE_START_BITS moves.
        code = "\n".join(re.sub(r"//.*$", "", ln) for ln in txt.splitlines())
        # WHOLE literals only. A bare substring search matches `$7FF` inside the
        # `<= $7FFF` signed-word-offset walls two of these modules already carry --
        # measured, by flipping DPLC_TILE_START_BITS to 11 and watching this fire on an
        # innocent line. A gate that reports the wrong site is worse than none.
        for lit in (str(ADDRESSABLE_TILES), str(TILE_START_MAX), f"${TILE_START_MAX:X}",
                    f"${ADDRESSABLE_TILES:X}"):
            assert not re.search(rf"(?<![\w${{}}]){re.escape(lit)}(?![\w])", code), (
                f"{mod} spells the ceiling as the literal `{lit}` in CODE beside the "
                "imported name -- that is the drift the parcel removed")


# --------------------------------------------------------------------------------
# 4. THE SPELLING
# --------------------------------------------------------------------------------
def test_the_runtime_mask_names_the_constant():
    """perform_dplc's `andi.l` IS the field width at run time; it must not re-type it."""
    txt = DPLC_EMP.read_text()
    assert re.search(r"andi\.l\s+#DPLC_TILE_START_MAX,\s*d0", txt), (
        "perform_dplc's tile_start mask no longer names DPLC_TILE_START_MAX -- a literal "
        "there is a sixth restatement of the field width")
    assert "$0FFF" not in txt and "$FFF," not in txt, (
        "a raw 12-bit mask literal is back in dplc.emp")


def test_both_python_producers_still_refuse_an_out_of_range_tile_start():
    """The generators are the ONLY place an over-range tile_start can be caught before
    it wraps -- they are offline staging tools, not part of build.sh, so nothing else
    re-checks them. Both must still assert, against the width this file folded."""
    for rel, pattern in (
        ("tools/dplc_layout.py", rf"assert\s+0\s*<=\s*tile_start\s*<\s*0x{ADDRESSABLE_TILES:X}\b"),
        ("games/sonic4/data/characters_staging/gen_characters.py",
         rf"assert\s+0\s*<=\s*tstart\s*<=\s*0x{TILE_START_MAX:X}\b"),
    ):
        txt = (ROOT / rel).read_text()
        assert re.search(pattern, txt, re.I), (
            f"{rel} no longer refuses a tile_start outside 0..{TILE_START_MAX}. Without it "
            "an over-large sheet WRAPS silently at generation time and the emitted file "
            "carries no evidence of it.")


# --------------------------------------------------------------------------------
# THE FINDING THAT SHAPED THE DESIGN
# --------------------------------------------------------------------------------
def test_the_blob_side_check_is_vacuous():
    """"max tile_start in the shipped table <= DPLC_TILE_START_MAX" CANNOT FAIL.

    Stated as a machine fact so the vacuous guard is not re-added as an improvement:
    over every 16-bit value an entry word can hold, the extracted tile_start is under
    the ceiling. Nothing about the shipped data is being observed here -- that is the
    point. The real tables are then walked to show the SAME thing empirically, so the
    contrast with the art-sheet gate above is on the record.
    """
    mask = (1 << TILE_START_BITS) - 1
    assert max(w & mask for w in range(1 << 16)) == TILE_START_MAX

    for mod, e in dplc_modules().items():
        for const, path in e["dplc"]:
            d = (ROOT / path).read_bytes()
            be16 = lambda o: (d[o] << 8) | d[o + 1]
            for f in range(be16(0) >> 1):
                fo = be16(f * 2)
                for i in range(be16(fo)):
                    w = be16(fo + 2 + i * 2)
                    assert w & mask <= TILE_START_MAX
                    assert 1 <= ((w >> TILE_START_BITS) & (MAX_TILES_PER_ENTRY - 1)) + 1 \
                        <= MAX_TILES_PER_ENTRY


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v", "-s"]))
