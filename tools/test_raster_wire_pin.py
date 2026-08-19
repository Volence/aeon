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
  1. the SPIN SOLVER                         (item 1 moved the spin into the program, item
                                              1c made its value a function of the op's
                                              position; the probe re-implements the solver)
  2. the per-class body ARITY from op_size   (item 1 changed these; a length drift means
                                              the probe's later ops are read as garbage)
  3. the opcode literals                     (the dispatch chain has been appended to
                                              before -- see RASTER_DISPATCH_RUNGS' trap note)
  4. the spin word's POSITION in the body    (arity alone cannot see a transposition)

HOW PIN 1 IS WRITTEN, and it is deliberate: the expected spins are DERIVED HERE, from the
constants read out of raster_dsl.emp, by an arithmetic spelled out in this file. They are
never copied from a build's output and never imported from the probe -- a pin that read the
probe's own answer would be pinning the probe to itself, and a pin holding a typed-in `18`
would go stale silently the day a cost term moves. What this file asserts is that TWO
independent implementations of one published formula agree on every shipped op shape.

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


# ---- 1. the spin solver ------------------------------------------------------

# The names the probe mirrors, and the .emp const each one copies. Every solved spin below
# is computed FROM THESE, never typed in.
SOLVER_CONSTS = [
    ("HBLANK_END_CYC",        "RASTER_HBLANK_END_CYC"),
    ("HBLANK_WIDTH_X10",      "RASTER_HBLANK_WIDTH_X10"),
    ("OP_FETCH_CYC",          "RASTER_OP_FETCH_CYC"),
    ("DISPATCH_RUNG_CYC",     "RASTER_DISPATCH_RUNG_CYC"),
    ("DISPATCH_HIT_CYC",      "RASTER_DISPATCH_HIT_CYC"),
    ("DISPATCH_RUNGS",        "RASTER_DISPATCH_RUNGS"),
    ("OP_TAIL_CYC",           "RASTER_OP_TAIL_CYC"),
    ("STREAM_WORD_CRAM_CYC",  "RASTER_STREAM_WORD_CRAM_CYC"),
    ("STREAM_WORD_DEEP_CYC",  "RASTER_STREAM_WORD_DEEP_CYC"),
    ("WORK_REG_CYC",          "RASTER_WORK_REG_CYC"),
    ("WORK_CRAM_BASE_CYC",    "RASTER_WORK_CRAM_BASE_CYC"),
    ("WORK_REGION_BASE_CYC",  "RASTER_WORK_REGION_BASE_CYC"),
    ("WORK_RESTORE_BASE_CYC", "RASTER_WORK_RESTORE_BASE_CYC"),
    ("PRE_CRAM_CYC",          "RASTER_PRE_CRAM_CYC"),
    ("PRE_REGION_CYC",        "RASTER_PRE_REGION_CYC"),
    ("PRE_RESTORE_CYC",       "RASTER_PRE_RESTORE_CYC"),
    ("DEPTH_CRAM",            "RASTER_DEPTH_CRAM"),
    ("DEPTH_REGION",          "RASTER_DEPTH_REGION"),
    ("DEPTH_RESTORE",         "RASTER_DEPTH_RESTORE"),
]


@pytest.mark.parametrize("probe_name,emp_name", SOLVER_CONSTS)
def test_probe_solver_constants_match_the_dsl(probe_name, emp_name):
    import raster_cost_probe as probe
    assert getattr(probe, probe_name) == emp_const(DSL, emp_name), (
        f"probe.{probe_name} = {getattr(probe, probe_name)} but raster_dsl.emp's "
        f"{emp_name} = {emp_const(DSL, emp_name)}")


def _expected_spins(ops):
    """raster_dsl.emp's fire_spins, re-derived here from the .emp constants alone.

    A third implementation of the published formula, written out longhand so a reader can
    check it against the comment block in raster_dsl.emp:

        n = round( (END - p - 14 - (width + span)/2) / 10 )

    where `p` is the modelled cycles from the record's op-walk origin to where this op
    would start its burst with a spin of zero, and `span` is the combined burst span.
    """
    k = {e: emp_const(DSL, e) for _, e in SOLVER_CONSTS}
    pre = {"cram": k["RASTER_PRE_CRAM_CYC"], "vsram": k["RASTER_PRE_CRAM_CYC"],
           "region": k["RASTER_PRE_REGION_CYC"], "restore": k["RASTER_PRE_RESTORE_CYC"],
           "reg": 0}
    base = {"cram": k["RASTER_WORK_CRAM_BASE_CYC"], "vsram": k["RASTER_WORK_CRAM_BASE_CYC"],
            "region": k["RASTER_WORK_REGION_BASE_CYC"],
            "restore": k["RASTER_WORK_RESTORE_BASE_CYC"], "reg": k["RASTER_WORK_REG_CYC"]}
    depth = {"cram": k["RASTER_DEPTH_CRAM"], "vsram": k["RASTER_DEPTH_CRAM"],
             "region": k["RASTER_DEPTH_REGION"], "restore": k["RASTER_DEPTH_RESTORE"]}
    # One burst word costs what its op's DESTINATION SPELLING costs (Tier-3 item 1): the
    # cram arm still holds VDP_CTRL in a2 and writes `-4(a2)`; region and restore have spent
    # a2 on their source cursor and write the absolute VDP_DATA.
    word = {"cram": k["RASTER_STREAM_WORD_CRAM_CYC"], "vsram": k["RASTER_STREAM_WORD_CRAM_CYC"],
            "region": k["RASTER_STREAM_WORD_DEEP_CYC"],
            "restore": k["RASTER_STREAM_WORD_DEEP_CYC"], "reg": 0}

    def words(o):
        if o["k"] == "reg":
            return 0
        return len(o["v"]) if o["k"] in ("cram", "vsram") else o["n"]

    def dispatch(o):
        if o["k"] == "reg":
            return k["RASTER_DISPATCH_RUNG_CYC"] * k["RASTER_DISPATCH_RUNGS"]
        return (k["RASTER_DISPATCH_RUNG_CYC"] * depth[o["k"]]
                + k["RASTER_DISPATCH_HIT_CYC"])

    def cost(o, spin):
        w = base[o["k"]] + (0 if o["k"] == "reg" else spin * 10 + 14)
        return (k["RASTER_OP_FETCH_CYC"] + dispatch(o) + w
                + word[o["k"]] * words(o) + k["RASTER_OP_TAIL_CYC"])

    idx = [i for i, o in enumerate(ops) if o["k"] != "reg"]
    if not idx:
        return [0] * len(ops)
    a, b = idx[0], idx[-1]
    if a == b:
        span = word[ops[a]["k"]] * (words(ops[a]) - 1)
    else:
        span = ((base[ops[a]["k"]] - pre[ops[a]["k"]])
                + word[ops[a]["k"]] * words(ops[a]) + k["RASTER_OP_TAIL_CYC"])
        for o in ops[a + 1:b]:
            span += cost(o, 0)
        span += (k["RASTER_OP_FETCH_CYC"] + dispatch(ops[b]) + pre[ops[b]["k"]] + 14
                 + word[ops[b]["k"]] * (words(ops[b]) - 1))

    out, acc = [], 0
    for i, o in enumerate(ops):
        n = 0
        if i == a:
            p = acc + k["RASTER_OP_FETCH_CYC"] + dispatch(o) + pre[o["k"]]
            num = 20 * (k["RASTER_HBLANK_END_CYC"] - p - 14) - (
                k["RASTER_HBLANK_WIDTH_X10"] + 10 * span)
            n = (num + 100) // 200 if num > 0 else 0
        out.append(n)
        acc += cost(o, n)
    return out


def _shapes(p):
    """Every op shape this tree emits, plus the two-stream-op shape only F6 exercises."""
    return {
        "leading cram 1w":      [p.stream_cram(34, [0x0EEE])],
        "leading cram 3w":      [p.stream_cram(34, [0, 0, 0])],
        "leading region 3w":    [p.stream_pal_region(34, 0, 1, 1, 3)],
        "leading vsram 1w":     [p.stream_vsram(2, [0x0043])],
        "leading restore 3w":   [p.pal_restore(34, 3)],
        "reg + cram 1w":        [p.reg_set(0x8C89), p.stream_cram(34, [0x000E])],
        "reg + cram 3w":        [p.reg_set(0x8C89), p.stream_cram(34, [0, 0, 0])],
        "reg + region 3w":      [p.reg_set(0x8C89), p.stream_pal_region(34, 0, 1, 1, 3)],
        "cram 1w + cram 1w":    [p.stream_cram(34, [0]), p.stream_cram(38, [0])],
        "reg only":             [p.reg_set(0x8C81)],
    }


def test_probe_solver_matches_the_dsl_on_every_shipped_shape():
    import raster_cost_probe as probe
    for name, ops in _shapes(probe).items():
        assert probe.fire_spins(ops) == _expected_spins(ops), (
            f"{name}: probe solves {probe.fire_spins(ops)}, the .emp constants derive "
            f"{_expected_spins(ops)}")


def test_the_solver_is_position_dependent_at_all():
    """The defect item 1c closed: the identical op must NOT get the identical spin when it
    sits after a register write. A solver that lost its accumulator would pass every pin
    above (both implementations would be equally wrong), so this asserts the property
    directly, on the two shapes whose difference is exactly one leading reg_set."""
    import raster_cost_probe as probe
    lead = probe.fire_spins([probe.stream_cram(34, [0, 0, 0])])[0]
    after = probe.fire_spins([probe.reg_set(0x8C89), probe.stream_cram(34, [0, 0, 0])])[1]
    assert lead > after, (
        f"a leading 3-word cram solves to {lead} and the same op after a reg_set to "
        f"{after} — the second one must be SMALLER; it arrives 110 cycles later")
    reg_cost = (emp_const(DSL, "RASTER_OP_FETCH_CYC")
                + emp_const(DSL, "RASTER_DISPATCH_RUNG_CYC")
                * emp_const(DSL, "RASTER_DISPATCH_RUNGS")
                + emp_const(DSL, "RASTER_WORK_REG_CYC")
                + emp_const(DSL, "RASTER_OP_TAIL_CYC"))
    assert lead - after == reg_cost // 10, (
        f"the gap is {lead - after} iterations but the reg_set ahead of it costs "
        f"{reg_cost} cycles = {reg_cost // 10} iterations")


def test_spin_pin_is_not_vacuous():
    """Poison: a probe solver constant that disagrees with the .emp must fail the pins.

    The subject perturbed is the WINDOW ANCHOR — the one measured constant — so this shows
    both the constant pin and the derived-spin pin biting, not merely "something raised".
    """
    import raster_cost_probe as probe
    real = probe.HBLANK_END_CYC
    ops = [probe.stream_cram(34, [0, 0, 0])]
    try:
        probe.HBLANK_END_CYC = real + 10        # one whole iteration later
        with pytest.raises(AssertionError):
            assert probe.HBLANK_END_CYC == emp_const(DSL, "RASTER_HBLANK_END_CYC")
        assert probe.fire_spins(ops) != _expected_spins(ops), (
            "moving the window anchor by a whole iteration did not change a solved spin — "
            "the solver is not reading the constant this test claims to pin")
    finally:
        probe.HBLANK_END_CYC = real
    assert probe.fire_spins(ops) == _expected_spins(ops)


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
    # A 3-colour cram, as the LEADING op of its fire: count-1 is 2, and the solved spin is
    # a value distinguishable from it. Both expectations are derived, never typed in.
    ops = [probe.stream_cram(34, [0x0EEE, 0x0E0E, 0x00EE])]
    w = probe.fire_words(ops)
    assert w[3] == _expected_spins(ops)[0], "word 3 must be the spin"
    assert w[4] == 2, "word 4 must be count-1"
    assert w[3] != w[4], "pick a fixture whose spin and count-1 differ, or this proves nothing"
    # The restore's tail word is the CRAM address (claim D-F), which must stay last.
    rops = [probe.pal_restore(34, 3)]
    r = probe.fire_words(rops)
    assert r[3] == _expected_spins(rops)[0]
    assert r[4] == 2
    assert r[5] == 34


def test_position_pin_is_not_vacuous():
    """Poison: transposing spin and count-1 keeps the LENGTH and must still be caught."""
    import raster_cost_probe as probe
    ops = [probe.stream_cram(34, [0x0EEE, 0x0E0E, 0x00EE])]
    w = list(probe.fire_words(ops))
    w[3], w[4] = w[4], w[3]
    assert len(w) == 8, "the transposition must not change the length, or this proves nothing"
    with pytest.raises(AssertionError):
        assert w[3] == _expected_spins(ops)[0], "word 3 must be the spin"
