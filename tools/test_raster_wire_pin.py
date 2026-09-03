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
    ("DISPATCH_ZERO_HIT_CYC",  "RASTER_DISPATCH_ZERO_HIT_CYC"),
    ("DISPATCH_ZERO_MISS_CYC", "RASTER_DISPATCH_ZERO_MISS_CYC"),
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
        # OP_SET_REG is opcode 0 and the op fetch's `move.w (a1)+, d1` sets Z, so
        # `.op_loop` decides it with one taken beq.s ahead of the chain (Tier-3 item 2).
        # Every other op pays that same branch NOT taken, then its own rung depth.
        if o["k"] == "reg":
            return k["RASTER_DISPATCH_ZERO_HIT_CYC"]
        return (k["RASTER_DISPATCH_ZERO_MISS_CYC"]
                + k["RASTER_DISPATCH_RUNG_CYC"] * depth[o["k"]]
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
        f"{after} — the second one must be SMALLER; it arrives a whole reg_set later")
    # A register write's dispatch is the zero pre-test's TAKEN branch and nothing more
    # (Tier-3 item 2); it used to be the five-rung fall-through, which is why the gap this
    # asserts is 4 iterations where it was 11.
    reg_cost = (emp_const(DSL, "RASTER_OP_FETCH_CYC")
                + emp_const(DSL, "RASTER_DISPATCH_ZERO_HIT_CYC")
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


# ---- 5. the DENSE program's wire form ----------------------------------------
#
# Added with the dense fixtures (Tier-3 item 3, 2026-08-19). The probe grew a SECOND
# encoder — `dense_program_words` — for a shape the sparse one cannot express, and an
# unpinned second encoder is exactly what this file exists to prevent. The .emp authority
# is raster.emp's `RasterGradientProgram` struct plus `raster_gradient_program`, so both
# the LAYOUT (field order and widths) and the SCHEDULE (the three arm words) are pinned,
# each against the source rather than against a captured image.

STRUCT_WIDTH = {"u16": 1, "u32": 2}          # words; `*u8` is a 32-bit label, handled below


def _gradient_struct_fields() -> list[tuple[str, int]]:
    """(field name, width in words) for RasterGradientProgram, in declaration order."""
    body = re.search(r"pub struct RasterGradientProgram\s*\{(.*?)\n\}", RASTER.read_text(), re.S)
    assert body, "cannot find `pub struct RasterGradientProgram` in raster.emp"
    out: list[tuple[str, int]] = []
    for name, ty in re.findall(r"(\w+)\s*:\s*(\*?\w+)\s*,", body.group(1)):
        out.append((name, 2 if ty.startswith("*") else STRUCT_WIDTH[ty]))
    return out


def test_dense_probe_layout_matches_the_struct():
    """The probe's word image must have the struct's shape, field for field."""
    import raster_cost_probe as probe
    fields = _gradient_struct_fields()
    assert [n for n, _ in fields] == [
        "rgp_mask", "rgp_arm0", "rgp_ops0", "rgp_arm1", "rgp_ops1",
        "rgp_arm2", "rgp_ops2", "rgp_op", "rgp_cmd", "rgp_lines", "rgp_stream",
        "rgp_end_arm", "rgp_end_ops"], (
        "RasterGradientProgram's fields moved — the probe's dense encoder emits a fixed "
        f"order and no longer matches: {[n for n, _ in fields]}")
    w = probe.dense_program_words(top=96, lines=40, cram_addr=0x48, stream=0x00123456)
    assert len(w) == sum(n for _, n in fields), (
        f"probe emits {len(w)} words, the struct is {sum(n for _, n in fields)}")
    # Field -> starting word index, derived from the widths above.
    at, idx = {}, 0
    for name, n in fields:
        at[name], idx = idx, idx + n
    assert w[at["rgp_op"]] == emp_const(RASTER, "OP_RUN_GRADIENT")
    assert w[at["rgp_lines"]] == 40
    assert (w[at["rgp_stream"]] << 16 | w[at["rgp_stream"] + 1]) == 0x00123456
    assert w[at["rgp_end_arm"]] == emp_const(RASTER, "RASTER_ARM_PARK")
    assert w[at["rgp_end_ops"]] == emp_const(RASTER, "RASTER_OPS_END")
    assert w[at["rgp_ops0"]] == 0 and w[at["rgp_ops1"]] == 0 and w[at["rgp_ops2"]] == 1


def test_dense_probe_schedule_matches_raster_arm():
    """The three arm words, derived from raster_arm's own formula, not from an image.

    raster_arm(next, after) = $8A00 | (after - next - 1). raster_gradient_program passes
    (1, top-1) then (top-1, top) then RASTER_ARM_EVERY_LINE — so arm1 must come out equal
    to the every-line constant, and that identity is itself part of the schedule.
    """
    import raster_cost_probe as probe
    every = emp_const(RASTER, "RASTER_ARM_EVERY_LINE")
    for top in (3, 96, 112, 200):
        w = probe.dense_program_words(top=top, lines=8, cram_addr=0x48, stream=0x1000)
        assert w[1] == 0x8A00 | ((top - 1) - 1 - 1), f"arm0 wrong at top {top}"
        assert w[3] == 0x8A00 | (top - (top - 1) - 1) == every, f"arm1 wrong at top {top}"
        assert w[5] == every, f"arm2 must be the every-line word at top {top}"
    # The mask is DERIVED from the CRAM address (raster_gradient_program's rgp_mask), the
    # field with a shipped history of being hand-authored wrong.
    for addr, line in ((0x20, 1), (0x48, 2), (0x60, 3)):
        w = probe.dense_program_words(top=96, lines=8, cram_addr=addr, stream=0x1000)
        assert w[0] == 1 << line, f"mask for CRAM ${addr:02X} must be line {line}'s bit"


def test_dense_fire_count_is_derived_not_measured():
    """lines + 4: two priming, the setup record, the run, and ONE trailing fire.

    THE `1` IS THE PART WORTH PINNING and it is not a constant to be taken on trust — it
    is a claim about `Raster_HInt`'s LEAVE edge, so this reads that edge. Ruling 1b leaves
    the last TWO dense fires' every-line arms in flight, i.e. two trailing fires, unless
    the last one is overwritten; `.dense_end` falling THROUGH into `.park` is what
    overwrites it. Put a transfer back between those two labels and the count is 5 again,
    silently, and every dense `calls` check starts failing for a reason no one would look
    for here — the same class of surprise that cost a whole fixture run when the count was
    first derived as 4 with only one trailing fire assumed and hardware answered 5.
    """
    import raster_cost_probe as probe
    assert probe.dense_fire_count(8) == 8 + 2 + 1 + 1
    assert probe.dense_fire_count(40) == 40 + 2 + 1 + 1
    assert probe.dense_fire_count(96) - probe.dense_fire_count(95) == 1

    assert _leave_edge_body(RASTER.read_text()) == ["clr.w   Raster_Dense_Mode"], (
        "`.dense_end` no longer falls straight into `.park` — the last dense fire's "
        "every-line arm is live again and the fire count is lines + 5")


def _leave_edge_body(text: str) -> list[str]:
    """The instructions between `.dense_end:` and `.park:` in Raster_HInt, comments out."""
    body = [ln.split("//")[0].rstrip() for ln in text.splitlines()]
    ends = [i for i, ln in enumerate(body) if ln.strip() == ".dense_end:"]
    parks = [i for i, ln in enumerate(body) if ln.strip() == ".park:"]
    assert len(ends) == 1 and len(parks) == 1, "raster.emp's LEAVE labels moved or multiplied"
    assert ends[0] < parks[0], "`.park:` no longer follows `.dense_end:`"
    return [ln.strip() for ln in body[ends[0] + 1:parks[0]] if ln.strip()]


def test_leave_edge_pin_is_not_vacuous():
    """Poison it: put the `jbra .out` back and the fall-through pin must bite."""
    poisoned = RASTER.read_text().replace(
        "        clr.w   Raster_Dense_Mode\n        // fall through\n    .park:",
        "        clr.w   Raster_Dense_Mode\n        jbra    .out\n    .park:")
    assert poisoned != RASTER.read_text(), "the poison did not apply — the LEAVE edge moved"
    assert _leave_edge_body(poisoned) == ["clr.w   Raster_Dense_Mode", "jbra    .out"]


def test_dense_pin_is_not_vacuous():
    """Poison each half: a moved field and a naive (T-2) setup line must both bite."""
    import raster_cost_probe as probe
    w = list(probe.dense_program_words(top=96, lines=40, cram_addr=0x48, stream=0x1000))
    # (a) transpose rgp_lines (word 10) and the stream's high word (11) — LENGTH unchanged.
    p = list(w)
    p[10], p[11] = p[11], p[10]
    assert len(p) == len(w)
    assert p != w, "pick a fixture whose two swapped words differ, or this proves nothing"
    with pytest.raises(AssertionError):
        assert p[10] == 40, "rgp_lines"
    # (b) the naive T-2 setup line, the derivation hardware rejected (raster.emp's T-1
    # note). It changes arm0 by exactly one and nothing else.
    with pytest.raises(AssertionError):
        assert (0x8A00 | (96 - 2 - 1 - 1)) == w[1], "arm0 is T-1, not T-2"


def test_dense_encoder_refuses_the_barred_line():
    """`top + lines <= 223` — the constructor's ensure, mirrored (raster.emp's derivation)."""
    import raster_cost_probe as probe
    probe.dense_program_words(top=96, lines=127, cram_addr=0x48, stream=0x1000)   # 223: ok
    with pytest.raises(ValueError):
        probe.dense_program_words(top=96, lines=128, cram_addr=0x48, stream=0x1000)
    with pytest.raises(ValueError):
        probe.dense_program_words(top=96, lines=8, cram_addr=0x00, stream=0x1000)  # CRAM line 0


# ---- 6. the RAMP program's wire form (EFFECTS-W1 item 6) --------------------
#
# `raster_ramp_program` / RasterRampProgram is the dense tier's OTHER body — a second
# encoder the probe grew for the FR1/FR2 pair, and the same rule applies: an unpinned
# second encoder is exactly what this file exists to prevent. Pinned against the .emp
# source, not a captured image, same as the gradient section above.

def _ramp_struct_fields() -> list[tuple[str, int]]:
    """(field name, width in words) for RasterRampProgram, in declaration order."""
    body = re.search(r"pub struct RasterRampProgram\s*\{(.*?)\n\}", RASTER.read_text(), re.S)
    assert body, "cannot find `pub struct RasterRampProgram` in raster.emp"
    out: list[tuple[str, int]] = []
    for name, ty in re.findall(r"(\w+)\s*:\s*(\*?\w+)\s*,", body.group(1)):
        out.append((name, 2 if ty.startswith("*") else STRUCT_WIDTH[ty]))
    return out


def test_ramp_probe_layout_matches_the_struct():
    """The probe's word image must have the struct's shape, field for field."""
    import raster_cost_probe as probe
    fields = _ramp_struct_fields()
    assert [n for n, _ in fields] == [
        "rrp_mask", "rrp_arm0", "rrp_ops0", "rrp_arm1", "rrp_ops1",
        "rrp_arm2", "rrp_ops2", "rrp_op", "rrp_cmd", "rrp_lines", "rrp_start", "rrp_step",
        "rrp_end_arm", "rrp_end_ops"], (
        "RasterRampProgram's fields moved — the probe's ramp encoder emits a fixed "
        f"order and no longer matches: {[n for n, _ in fields]}")
    w = probe.ramp_program_words(top=96, lines=40, cmd=0x40000010, start=0x00010000, step=0x8000)
    assert len(w) == sum(n for _, n in fields), (
        f"probe emits {len(w)} words, the struct is {sum(n for _, n in fields)}")
    at, idx = {}, 0
    for name, n in fields:
        at[name], idx = idx, idx + n
    assert w[at["rrp_op"]] == emp_const(RASTER, "OP_RUN_RAMP") == probe.OP_RUN_RAMP
    assert w[at["rrp_lines"]] == 40
    assert (w[at["rrp_cmd"]] << 16 | w[at["rrp_cmd"] + 1]) == 0x40000010
    assert (w[at["rrp_start"]] << 16 | w[at["rrp_start"] + 1]) == 0x00010000
    assert (w[at["rrp_step"]] << 16 | w[at["rrp_step"] + 1]) == 0x8000
    assert w[at["rrp_end_arm"]] == emp_const(RASTER, "RASTER_ARM_PARK")
    assert w[at["rrp_end_ops"]] == emp_const(RASTER, "RASTER_OPS_END")
    assert w[at["rrp_ops0"]] == 0 and w[at["rrp_ops1"]] == 0 and w[at["rrp_ops2"]] == 1
    assert w[at["rrp_mask"]] == 0, "default mask must be 0 (no arg passed)"


def test_ramp_probe_schedule_matches_raster_arm():
    """Same schedule as the gradient program (raster_ramp_program's own comment: 'Same
    shape as the gradient ENTER'), so the same three-arm-word identity applies."""
    import raster_cost_probe as probe
    every = emp_const(RASTER, "RASTER_ARM_EVERY_LINE")
    for top in (3, 96, 112, 200):
        w = probe.ramp_program_words(top=top, lines=8, cmd=0x40000010, start=0, step=0x8000)
        assert w[1] == 0x8A00 | ((top - 1) - 1 - 1), f"arm0 wrong at top {top}"
        assert w[3] == 0x8A00 | (top - (top - 1) - 1) == every, f"arm1 wrong at top {top}"
        assert w[5] == every, f"arm2 must be the every-line word at top {top}"


def test_ramp_fire_count_shares_the_dense_pipeline():
    """The ramp program walks the SAME arm pipeline as the gradient one — two priming, the
    setup record, `lines` fires, one trailing fire — so `dense_fire_count` applies
    unchanged; there is no separate `ramp_fire_count` to drift out of sync with it."""
    import raster_cost_probe as probe
    assert probe.dense_fire_count(8) == 8 + 2 + 1 + 1
    assert probe.dense_fire_count(40) == 40 + 2 + 1 + 1


def test_ramp_pin_is_not_vacuous():
    """Poison it: transpose rrp_lines and rrp_start's high word — LENGTH unchanged."""
    import raster_cost_probe as probe
    w = list(probe.ramp_program_words(top=96, lines=40, cmd=0x40000010, start=0x00010000, step=0x8000))
    p = list(w)
    p[10], p[11] = p[11], p[10]        # rrp_lines <-> rrp_start's high word
    assert len(p) == len(w)
    assert p != w, "pick a fixture whose two swapped words differ, or this proves nothing"
    with pytest.raises(AssertionError):
        assert p[10] == 40, "rrp_lines"


def test_ramp_encoder_refuses_the_barred_line():
    """`top + lines <= 223` — the constructor's ensure, mirrored (raster.emp's derivation)."""
    import raster_cost_probe as probe
    probe.ramp_program_words(top=96, lines=127, cmd=0x40000010, start=0, step=0x8000)  # 223: ok
    with pytest.raises(ValueError):
        probe.ramp_program_words(top=96, lines=128, cmd=0x40000010, start=0, step=0x8000)
