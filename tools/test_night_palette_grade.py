#!/usr/bin/env python3
"""The OJZ night grade, checked from outside the compiler that built it.

WHAT THIS FILE IS FOR, and what it deliberately is NOT.

`games/sonic4/data/effects/ojz_effects.emp` derives `OJZ_Palette_Night` from
`OJZ_Palette` by a per-channel multiplicative scale, and asserts fourteen properties
about the result as comptime `ensure`s. Those ensures are the primary guard: they are
zero bytes, they run inside every build of every shape, and each one was proven to fire
by mutating the transform on disk (the sweep is in
`docs/superpowers/notes/2026-09-16-night-palette-tone.md`, M1..M11).

This file adds the two things a comptime ensure structurally CANNOT do:

  1. **Check the EMITTED bytes.** An `ensure` reasons about the value sigil computed. It
     cannot see whether that value reached the ROM at the address the symbol names. The
     old night palette was a literal table; this one is a fold, and a fold that is right
     in the compiler and wrong in the image is a new failure class this tree has never
     had a check for. `test_rom_words_are_the_derived_grade` re-derives all 48 words in
     Python, from the same `.bin` and the same two constants read out of the `.emp`
     SOURCE, and compares against `s4.bin` at the address `s4.lst` gives.

  2. **Say that each property is FALSIFIABLE at all.** A guard reading `== 0` over a
     counter that can only ever be 0 passes forever and proves nothing. The mutation
     sweep shows the shipped ensures fire; these rows show the SPECIFICATION has teeth,
     by feeding each mirrored predicate a palette built to violate it and requiring a
     non-zero answer. A row here going green on a poisoned input is the vacuity this
     tree keeps finding, arriving early.

WHAT IT DOES NOT DO, said plainly: it does not judge the look. Nothing here can. It also
does not prove the `.emp` ensures run — only the mutation sweep does that, and only for
the revision it was run at. If the ensures were deleted, every row in this file would
still pass, because this file reads the day palette and the ROM and never the guards.

THE MIRROR IS PINNED TO THE SOURCE, not typed in. `NIGHT_LIGHT_8` and `NIGHT_BLUE_8` are
read out of the `.emp` by regex, and `night_channel` below is a transcription of the
`.emp` fn beside it. A transcription can still drift; row 1 is what catches that, because
a drifted mirror disagrees with the ROM sigil actually built.
"""
import re
import struct
from pathlib import Path

import pytest

AEON = Path(__file__).resolve().parent.parent
EFFECTS = AEON / "games/sonic4/data/effects/ojz_effects.emp"
DAY_BIN = AEON / "games/sonic4/data/generated/ojz/act1/ojz_palette.bin"

ENTRIES = 48  # CRAM lines 1-3; line 0 is the character's and the grade must not touch it


# ---- the mirror --------------------------------------------------------------


def emp_const(name: str) -> int:
    """A `const NAME = <int>` out of ojz_effects.emp."""
    m = re.search(rf"^\s*(?:pub\s+)?const\s+{re.escape(name)}\s*=\s*(\$[0-9A-Fa-f]+|-?\d+)",
                  EFFECTS.read_text(), re.M)
    assert m, f"cannot find `const {name}` in {EFFECTS.name}"
    v = m.group(1)
    return int(v[1:], 16) if v.startswith("$") else int(v)


def day_words() -> list[int]:
    raw = DAY_BIN.read_bytes()
    assert len(raw) == 2 * ENTRIES, f"{DAY_BIN.name} is {len(raw)} bytes, expected {2 * ENTRIES}"
    return list(struct.unpack(f">{ENTRIES}H", raw))


def night_channel(v: int, s8: int) -> int:
    """Transcribed from `comptime fn night_channel` in ojz_effects.emp."""
    n = (v * s8 + 4) // 8
    if v > 0 and n < 1:
        n = 1
    if n > 7:
        n = 7
    return n


def chans(w: int) -> tuple[int, int, int]:
    """CRAM word 0000 BBB0 GGG0 RRR0 -> (r, g, b), each 0..7."""
    return ((w >> 1) & 7, (w >> 5) & 7, (w >> 9) & 7)


def night_word(w: int, light8: int, blue8: int) -> int:
    r, g, b = chans(w)
    return ((night_channel(r, light8) << 1)
            | (night_channel(g, light8) << 5)
            | (night_channel(b, blue8) << 9))


def night_words(light8: int | None = None, blue8: int | None = None) -> list[int]:
    light8 = emp_const("NIGHT_LIGHT_8") if light8 is None else light8
    blue8 = emp_const("NIGHT_BLUE_8") if blue8 is None else blue8
    return [night_word(w, light8, blue8) for w in day_words()]


def lum3(w: int) -> int:
    """Rec.601 luma over the 3-bit values. The CRAM ramp is linear in the channel
    value (v * 255 / 7), so the weights apply to the 3-bit number directly."""
    r, g, b = chans(w)
    return 77 * r + 151 * g + 28 * b


# ---- the mirrored predicates, one per shipped `ensure` -----------------------
# Each returns a FAULT COUNT (or a measured figure). The poison rows below require
# each one to be capable of a non-zero / off-pin answer.


def new_blacks(day: list[int], night: list[int]) -> int:
    return sum(1 for d, n in zip(day, night) if (d == 0) != (n == 0))


def dead_channels(day: list[int], night: list[int]) -> int:
    n = 0
    for d, w in zip(day, night):
        for dc, nc in zip(chans(d), chans(w)):
            if dc > 0 and nc == 0:
                n += 1
    return n


def brighter_channels(day: list[int], night: list[int]) -> int:
    n = 0
    for d, w in zip(day, night):
        for dc, nc in zip(chans(d), chans(w)):
            if nc > dc:
                n += 1
    return n


def retention_pcts(day: list[int], night: list[int], lit_floor: int) -> list[int]:
    out = []
    for d, w in zip(day, night):
        if d == 0 or max(chans(d)) < lit_floor:
            continue
        out.append(lum3(w) * 100 // lum3(d))
    return out


def blue_permille(words: list[int]) -> int:
    blue = sum(chans(w)[2] for w in words)
    allc = sum(sum(chans(w)) for w in words)
    return blue * 1000 // allc


def distinct(words: list[int]) -> int:
    return len(set(words))


# =============================================================================
# 1. THE EMITTED BYTES
# =============================================================================

class TestRomCarriesTheGrade:
    """The one check no comptime `ensure` can make: that the fold reached the image."""

    @pytest.mark.needs_build("s4.bin", "s4.lst")
    def test_rom_words_are_the_derived_grade(self):
        rom = (AEON / "s4.bin").read_bytes()
        lst = (AEON / "s4.lst").read_text()
        m = re.search(r"^\s*OJZ_Palette_Night\s*:\s*([0-9A-Fa-f]+)\s", lst, re.M)
        assert m, "OJZ_Palette_Night is not in s4.lst's symbol table"
        addr = int(m.group(1), 16)
        got = list(struct.unpack_from(f">{ENTRIES}H", rom, addr))
        want = night_words()
        bad = [(i, hex(a), hex(b)) for i, (a, b) in enumerate(zip(got, want)) if a != b]
        assert not bad, (
            f"{len(bad)} of {ENTRIES} emitted night-palette words disagree with the "
            f"transform re-derived here from {DAY_BIN.name} and the two constants in "
            f"{EFFECTS.name}: {bad[:6]}. Either the fold did not reach the ROM at the "
            f"address s4.lst names, or this file's transcription of night_channel drifted "
            f"from the .emp beside it.")

    @pytest.mark.needs_build("s4.bin", "s4.lst")
    def test_rom_words_are_not_the_day_palette(self):
        """Anti-vacuity for the row above: a transform that did nothing would also match
        a mirror that did nothing. The two palettes must actually differ."""
        rom = (AEON / "s4.bin").read_bytes()
        lst = (AEON / "s4.lst").read_text()
        addr = int(re.search(r"^\s*OJZ_Palette_Night\s*:\s*([0-9A-Fa-f]+)\s", lst, re.M).group(1), 16)
        got = list(struct.unpack_from(f">{ENTRIES}H", rom, addr))
        day = day_words()
        moved = sum(1 for a, b in zip(got, day) if a != b)
        assert moved >= 30, (
            f"only {moved} of {ENTRIES} night words differ from the day palette — the "
            f"night region would be indistinguishable from its neighbours")


# =============================================================================
# 2. THE PROPERTIES HOLD (a second implementation agreeing with the .emp)
# =============================================================================

class TestPropertiesHoldOnTheShippedGrade:

    @classmethod
    def setup_class(cls):
        cls.day = day_words()
        cls.night = night_words()
        cls.light8 = emp_const("NIGHT_LIGHT_8")
        cls.blue8 = emp_const("NIGHT_BLUE_8")

    def test_blue_lean_is_structural_and_beats_its_own_control(self):
        """THE CONTROL IS THE NO-LEAN SCALE, NOT THE DAY PALETTE. Scale blue by exactly
        the light factor — no lean whatever — and the palette's blue share STILL rises
        above day, because rounding half up and the non-zero floor bite hardest on the
        smallest channel and blue is usually the smallest here. Comparing the grade
        against the day palette would credit that rounding to the design."""
        assert self.blue8 > self.light8, (
            f"NIGHT_BLUE_8 ({self.blue8}) must exceed NIGHT_LIGHT_8 ({self.light8})")
        control = night_words(light8=self.light8, blue8=self.light8)
        assert blue_permille(control) > blue_permille(self.day), (
            "the control is expected to rise a little on rounding alone; if it stopped "
            "rising, this comparison is no longer the confound it was built to hold")
        assert blue_permille(self.night) > blue_permille(control) + 20, (
            f"the lean is only {blue_permille(self.night) - blue_permille(control)} permille "
            f"over the NO-LEAN control ({blue_permille(control)}), not a real blue cast. "
            f"Day is {blue_permille(self.day)}.")

    def test_black_set_is_invariant(self):
        assert new_blacks(self.day, self.night) == 0

    def test_no_lit_channel_dies(self):
        assert dead_channels(self.day, self.night) == 0

    def test_nothing_brightens(self):
        assert brighter_channels(self.day, self.night) == 0

    def test_retention_band(self):
        band = retention_pcts(self.day, self.night, lit_floor=2)
        assert band, "no darkenable colours found — the band check would be vacuous"
        assert min(band) >= 50, f"retention floor {min(band)}% is under the derived 50%"
        assert max(band) <= 100, f"retention ceiling {max(band)}% is over 100% — something brightened"

    def test_the_hundred_percent_class_is_exactly_the_already_minimal_entries(self):
        """A 3-bit channel at its dimmest non-black step has nowhere to go. Those entries
        keep 100% by arithmetic necessity; NOTHING ELSE may."""
        full = [i for i, (d, n) in enumerate(zip(self.day, self.night))
                if d != 0 and lum3(n) * 100 // lum3(d) >= 100]
        for i in full:
            r, g, b = chans(self.day[i])
            assert night_channel(r, self.light8) == r
            assert night_channel(g, self.light8) == g
            assert night_channel(b, self.blue8) == b, (
                f"entry {i} (${self.day[i]:04X}) keeps 100% of its luminance without being "
                f"at the bottom rung — it will read as full daylight beside neighbours at "
                f"half brightness, which is the straggler the hub's ruling named")

    def test_merge_budget_does_not_grow_silently(self):
        lost = distinct(self.day) - distinct(self.night)
        assert lost == 3, (
            f"{lost} distinct day colours collapse at night, not the authored 3. Each "
            f"collapse is an art edge that stops being an edge.")


# =============================================================================
# 3. EVERY PREDICATE IS FALSIFIABLE
# =============================================================================

class TestEachPredicateBites:
    """Feed each mirrored predicate a palette built to violate it. A green row here means
    the predicate cannot distinguish anything and the matching `ensure` is decoration."""

    @classmethod
    def setup_class(cls):
        cls.day = day_words()

    def _subtraction(self) -> list[int]:
        """The recipe that actually shipped until 2026-09-16: r-3, g-2, b-0, clamped."""
        out = []
        for w in self.day:
            r, g, b = chans(w)
            out.append((max(0, r - 3) << 1) | (max(0, g - 2) << 5) | (b << 9))
        return out

    def test_black_set_predicate_refuses_the_recipe_that_shipped(self):
        assert new_blacks(self.day, self._subtraction()) == 4, (
            "the subtraction crushed exactly four act colours to $0000; a predicate that "
            "cannot see them is not guarding the property the hub ruled")

    def test_dead_channel_predicate_refuses_the_recipe_that_shipped(self):
        assert dead_channels(self.day, self._subtraction()) > 0

    def test_retention_band_predicate_refuses_the_recipe_that_shipped(self):
        band = retention_pcts(self.day, self._subtraction(), lit_floor=2)
        assert min(band) == 0, "the subtraction kept 0% on at least one darkenable colour"
        assert max(band) == 100, "and 100% on another — a 100-point spread is not a cast"

    def test_brighter_predicate_refuses_a_lean_added_as_an_offset(self):
        """The shadow-lift variant the parcel considered and did not take: every non-black
        colour gets a blue floor of 1. It reads as moonlight and it brightens."""
        lifted = []
        for w in self.day:
            n = night_word(w, emp_const("NIGHT_LIGHT_8"), emp_const("NIGHT_BLUE_8"))
            if w != 0:
                r, g, b = chans(n)
                n = (r << 1) | (g << 5) | (max(1, b) << 9)
            lifted.append(n)
        assert brighter_channels(self.day, lifted) > 0

    def test_blue_lean_predicate_refuses_an_even_scale(self):
        """The predicate must call the no-lean scale what it is. Written first as
        `even <= day` — which FAILED, 341 against 337, and that failure is the reason the
        control above exists at all."""
        light8 = emp_const("NIGHT_LIGHT_8")
        even = night_words(light8=light8, blue8=light8)
        real = night_words()
        assert blue_permille(even) < blue_permille(real) - 20, (
            "an even scale must not read as a blue cast beside the shipped grade")

    def test_merge_predicate_refuses_a_scale_that_flattens_the_art(self):
        flat = night_words(light8=1, blue8=2)
        assert distinct(self.day) - distinct(flat) > 3

    def test_the_mirror_is_reading_a_real_palette(self):
        """Anti-vacuity for this whole class: every predicate above counts faults, so a
        palette that read as 48 zeros would satisfy several of them for free."""
        assert sum(1 for w in self.day if w != 0) == 42, (
            f"OJZ_Palette has {sum(1 for w in self.day if w != 0)} lit entries, not 42 — "
            f"re-derive every pin in this file and in ojz_effects.emp")
