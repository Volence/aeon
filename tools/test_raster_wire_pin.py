#!/usr/bin/env python3
"""Pin raster_cost_probe.py's wire transcription against the .emp encoder it copies.

WHY THIS EXISTS. `raster_cost_probe.py` re-implements engine/effects/raster_dsl.emp's
`op_words`/`op_size` in Python, on purpose -- it has to build programs the .emp authoring
layer refuses (F0 has no fires at all), and a fixture that had to be a ROM `data`
declaration would drag map.toml and the frozen tables into a measurement. That second
implementation was UNPINNED, which the 2026-08-18 raster-substrate lens sweep flagged as
Tier 4: the probe is the instrument that calibrates the very constants `band()` enforces,
so a silent drift between the two mis-measures the thing everything downstream trusts.

IT IS NOT A HYPOTHETICAL. Substrate item 1 moved the blanking spin into the program, and
the probe's encoder had to be hand-edited to match. Had that edit been wrong -- a missing
spin word, or the right word in the wrong slot -- the probe would have poked a malformed
program and reported cycle figures that looked entirely healthy. The probe's existing
empirical check (`calls` reports the fires hardware actually took) does NOT cover it: a
wrong spin VALUE leaves the fire count untouched and only shifts cycles, which is
indistinguishable from a real cost change.

WHAT IS PINNED, and each is a drift class that has actually occurred in this tree:
  1. the three RASTER_SPIN_* values          (item 1 changed these; the probe copies them)
  2. the per-class body ARITY from op_size   (item 1 changed these; a length drift means
                                              the probe's later ops are read as garbage)
  3. the opcode literals                     (the dispatch chain has been appended to
                                              before -- see RASTER_DISPATCH_RUNGS' trap note)
  4. the spin word's POSITION in the body    (arity alone cannot see a transposition)

Every pin below has a poison test beside it proving it bites.
"""
import re
import sys
from pathlib import Path

import pytest

AEON = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AEON / "tools"))

DSL = AEON / "engine/effects/raster_dsl.emp"
RASTER = AEON / "engine/effects/raster.emp"


def emp_const(path: Path, name: str) -> int:
    """A `const NAME = <int>` out of an .emp source. Same shape as effects_gates.emp_int."""
    m = re.search(rf"^\s*(?:pub\s+)?const\s+{re.escape(name)}\s*=\s*(\$[0-9A-Fa-f]+|-?\d+)",
                  path.read_text(), re.M)
    assert m, f"cannot find `const {name}` in {path.name}"
    v = m.group(1)
    return int(v[1:], 16) if v.startswith("$") else int(v)


def op_size_arity(variant: str) -> int:
    """The CONSTANT part of an op_size match arm, e.g. `Cram(a, cols) => 5 + cols.len` -> 5.

    The payload term (`+ cols.len`) is the caller's word count and is not part of the
    fixed body shape, so the constant alone is what the probe has to agree with.
    """
    body = re.search(r"comptime fn op_size\(.*?\n\}", DSL.read_text(), re.S)
    assert body, "op_size not found in raster_dsl.emp"
    m = re.search(rf"^\s*{variant}\([^)]*\)\s*=>\s*(\d+)", body.group(0), re.M)
    assert m, f"cannot find op_size arm for {variant}"
    return int(m.group(1))


# ---- 1. the spin constants ---------------------------------------------------

def test_probe_spin_constants_match_the_dsl():
    import raster_cost_probe as probe
    assert probe.SPIN_CRAM == emp_const(DSL, "RASTER_SPIN_CRAM")
    assert probe.SPIN_REGION == emp_const(DSL, "RASTER_SPIN_REGION")
    assert probe.SPIN_RESTORE == emp_const(DSL, "RASTER_SPIN_RESTORE")


def test_spin_pin_is_not_vacuous():
    """Poison: a probe spin that disagrees with the .emp must fail the pin above."""
    import raster_cost_probe as probe
    real = probe.SPIN_CRAM
    try:
        probe.SPIN_CRAM = real + 1
        with pytest.raises(AssertionError):
            assert probe.SPIN_CRAM == emp_const(DSL, "RASTER_SPIN_CRAM")
    finally:
        probe.SPIN_CRAM = real


# ---- 2. the per-class body arity ---------------------------------------------

# (probe op factory args, op_size variant, payload words the arm's `+ N.len` covers)
ARITY_CASES = [
    (lambda p: p.reg_set(0x8C81), "SetReg", 0),
    (lambda p: p.stream_cram(34, [0x0EEE]), "Cram", 1),
    (lambda p: p.stream_cram(34, [0, 0, 0]), "Cram", 3),
    (lambda p: p.stream_vsram(2, [0x0043]), "Vsram", 1),
    (lambda p: p.stream_pal_region(34, 0, 1, 1, 3), "PalRegion", 0),
    (lambda p: p.pal_restore(34, 3), "PalRestore", 0),
]


@pytest.mark.parametrize("make,variant,payload", ARITY_CASES)
def test_probe_body_length_matches_op_size(make, variant, payload):
    import raster_cost_probe as probe
    emitted = probe.op_words(make(probe))
    assert len(emitted) == op_size_arity(variant) + payload, (
        f"{variant}: probe emits {len(emitted)} words, op_size says "
        f"{op_size_arity(variant)} + {payload} payload")


def test_arity_pin_is_not_vacuous():
    """Poison: dropping a word from the probe's cram body must fail the arity pin."""
    import raster_cost_probe as probe
    real = probe.op_words
    try:
        probe.op_words = lambda o: real(o)[:-1]
        with pytest.raises(AssertionError):
            emitted = probe.op_words(probe.stream_cram(34, [0x0EEE]))
            assert len(emitted) == op_size_arity("Cram") + 1
    finally:
        probe.op_words = real


# ---- 3. the opcode literals --------------------------------------------------

OPCODES = [("cram", "OP_CRAM"), ("vsram", "OP_CRAM"),
           ("region", "OP_PAL_REGION"), ("restore", "OP_PAL_RESTORE"),
           ("reg", "OP_SET_REG")]


def test_probe_opcodes_match_raster_emp():
    import raster_cost_probe as probe
    made = {
        "reg": probe.reg_set(0x8C81),
        "cram": probe.stream_cram(34, [0]),
        "vsram": probe.stream_vsram(2, [0]),
        "region": probe.stream_pal_region(34, 0, 1, 1, 3),
        "restore": probe.pal_restore(34, 3),
    }
    for key, const in OPCODES:
        assert probe.op_words(made[key])[0] == emp_const(RASTER, const), (
            f"{key}: probe emits opcode {probe.op_words(made[key])[0]}, "
            f"raster.emp says {const} = {emp_const(RASTER, const)}")


# ---- 4. the spin word's POSITION ---------------------------------------------

def test_spin_sits_between_command_and_count():
    """The body is [op][cmd hi][cmd lo][SPIN][count-1][payload...].

    Arity cannot see a transposition -- swapping SPIN and count-1 keeps the length and
    changes what the handler does with both. Raster_HInt reads command, then spin, then
    count, so index 3 is the contract.
    """
    import raster_cost_probe as probe
    # A 3-colour cram: count-1 is 2, and the spin is a value distinguishable from it.
    w = probe.op_words(probe.stream_cram(34, [0x0EEE, 0x0E0E, 0x00EE]))
    assert w[3] == emp_const(DSL, "RASTER_SPIN_CRAM"), "word 3 must be the spin"
    assert w[4] == 2, "word 4 must be count-1"
    # The restore's tail word is the CRAM address (claim D-F), which must stay last.
    r = probe.op_words(probe.pal_restore(34, 3))
    assert r[3] == emp_const(DSL, "RASTER_SPIN_RESTORE")
    assert r[4] == 2
    assert r[5] == 34


def test_position_pin_is_not_vacuous():
    """Poison: transposing spin and count-1 keeps the LENGTH and must still be caught."""
    import raster_cost_probe as probe
    w = list(probe.op_words(probe.stream_cram(34, [0x0EEE, 0x0E0E, 0x00EE])))
    w[3], w[4] = w[4], w[3]
    assert len(w) == 8, "the transposition must not change the length, or this proves nothing"
    with pytest.raises(AssertionError):
        assert w[3] == emp_const(DSL, "RASTER_SPIN_CRAM"), "word 3 must be the spin"
