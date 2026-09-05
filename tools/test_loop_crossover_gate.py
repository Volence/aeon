"""Unit tests for the loop crossover READ side (Player_LoopCrossover).

Three layers, and the split is the point:

1. THE ROUTINE, EXECUTED, over a COMMITTED CUT of a real ROM
   (tools/fixtures/loop_crossover_cut.json) — because build.sh's pytest lane runs
   BEFORE sigil, so a test opening s4.debug.bin here would grade a PREVIOUS build
   (build.sh:61-72 records that happening twice). The same sweeps run against the
   FRESH artifact in build.sh's post-sigil block, which also fails loudly if this cut
   has gone stale. One cut per canonical shape: a green on the debug ROM alone would
   leave the shipped release ROM ungraded.

2. THE CONSUMPTION CLAIM, isolated. Every other sweep here would still pass if the
   routine ignored `CrossoverTable` and hard-coded its answer, so the claim that the
   ROM table DECIDES the layer gets its own test that varies one byte of the ROM image
   and nothing else. `test_the_gate_refuses_a_vacuous_pass` is its converse: the gate
   itself must go red when no execution was moved by that byte.

3. THE MODEL's own shape, asserted rather than transcribed. The mapping under test is
   `layer' = v - XOVER_LAYER_BIAS`, and a test that restated `1 -> 0, 2 -> 1` would
   prove nothing about a mis-typed bias. What is asserted instead is that the model is
   a BIJECTION onto the two legal layers and that it leaves the layer alone on
   XOVER_NONE — properties a wrong bias breaks.

The executor lives in loop_crossover_gate.py and raises on any instruction form it does
not model, so an edit reaching for a new addressing mode stops these tests rather than
being silently skipped.
"""

import pathlib
import sys

import pytest

TOOLS = pathlib.Path(__file__).resolve().parent
ROOT = TOOLS.parent
sys.path.insert(0, str(TOOLS))

import loop_crossover_gate as lxg  # noqa: E402

FIXTURE = TOOLS / "fixtures" / "loop_crossover_cut.json"


def _shapes():
    if not FIXTURE.exists():
        return []
    return lxg.cut_shapes(FIXTURE)


@pytest.fixture(scope="module", params=_shapes() or [None])
def cut(request):
    """One cut per committed BUILD SHAPE."""
    if request.param is None:
        pytest.fail("%s is missing or carries no shapes — regenerate with "
                    "tools/loop_crossover_gate.py --write-fixture" % FIXTURE)
    rom, spans, syms, equs = lxg.load_cut(FIXTURE, request.param)
    prog, _ = lxg.decode(rom, spans)
    return rom, prog, [tuple(s) for s in spans], syms, equs


@pytest.fixture(scope="module")
def K(cut):
    return cut[4]           # the constants the ROM in this cut was built with


# ------------------------------------------------------------------ 1. the routine

def test_every_sweep_agrees_with_the_encoding(cut):
    """The whole gate, over the committed cut. Aggregate: any finding fails."""
    rom, prog, extents, syms, equs = cut
    r = lxg.run_all(rom, prog, extents, syms, equs)
    assert r["fails"] == [], "\n".join("[%s] %s" % f for f in r["fails"])
    assert r["executions"] > 100, \
        "the sweep shrank to %d executions — a gate that stopped asking is not a " \
        "gate that passed" % r["executions"]


def test_both_routines_are_executed_not_stubbed(cut):
    """Collision_GetType must actually run. If it were stubbed, the interesting half —
    that the byte indexed is the attr of the cell the player is IN, on the plane the
    player is ON — would be assumed rather than shown."""
    rom, prog, extents, syms, equs = cut
    w = lxg.World(rom, prog, extents, syms, equs)
    w.fill_plane(0, lxg.ATTR_A)
    w.place(lxg.IN_CELL[0], lxg.IN_CELL[1], equs["LAYER_PATH_A"])
    w.set_x_vel(lxg.RIGHT)
    trace = w.frame()
    assert syms["Collision_GetType"] in trace.called, \
        "the read site did not call Collision_GetType"
    assert trace.steps > 30, "the run executed only %d instructions — the lookup's " \
                             "body cannot have run" % trace.steps


# --------------------------------------------------------------- 2. the consumption

def test_one_rom_byte_decides_the_layer(cut, K):
    """THE experiment. Two runs, identical in every input except the byte at
    CrossoverTable + attr in the ROM image. If the layer does not follow it, the read
    site is decorative and the bake half shipped into nothing."""
    rom, prog, extents, syms, equs = cut

    def run(table_value):
        w = lxg.World(rom, prog, extents, syms, equs)
        w.fill_plane(0, lxg.ATTR_A)
        w.fill_plane(1, lxg.ATTR_A)
        w.set_crossover(lxg.ATTR_A, table_value)
        w.place(lxg.IN_CELL[0], lxg.IN_CELL[1], K["LAYER_PATH_A"])
        w.set_x_vel(lxg.RIGHT)          # XOVER_TO_B leads onto the RIGHT arc
        w.frame()
        return w.layer()

    assert run(K["XOVER_NONE"]) == K["LAYER_PATH_A"], \
        "the CONTROL moved: with XOVER_NONE in the table the layer must not change"
    assert run(K["XOVER_TO_B"]) == K["LAYER_PATH_B"], \
        "changing one ROM byte from XOVER_NONE to XOVER_TO_B did NOT move the player " \
        "to path B — the table is readable but not consumed"


def test_the_shipped_table_is_the_control(cut, K):
    """The unmodified ROM must leave the layer alone.

    THE PREMISE CHANGED ON 2026-09-04 AND THIS IS THE RE-READ IT ASKED FOR. It used to
    assert all 256 slots hold XOVER_NONE, and said in as many words: "when the first
    real crossover is authored this test's premise changes, and the gate's staleness
    check on the table blob is what forces that to be noticed." That happened — the
    section-0 loop is authored and two slots are now marked — and the staleness check
    did force it, exactly as designed.

    WHAT THE TEST IS ACTUALLY FOR is the assertion below it: a shipped ROM, unmodified,
    must not write the layer byte for a player standing on an UNMARKED cell. The
    all-256-empty check was a PROXY for that precondition, sound only while nothing was
    authored. The precondition itself is narrower and survives authored content: the
    ONE attr this test places its player on (ATTR_A) must be unmarked.

    NOT WEAKENED TO A RANGE. Asserting "few slots are marked" or dropping the check
    would pass for any table anyone bakes, including one that marks ATTR_A and makes
    the behavioural assertion below vacuous — the layer would move for a reason the
    test would then read as normal. This names the exact slot the experiment depends
    on, so authoring the wrong cell still fails here."""
    rom, prog, extents, syms, equs = cut
    table = rom[syms["CrossoverTable"]:syms["CrossoverTable"] + 256]
    assert table[lxg.ATTR_A] == K["XOVER_NONE"], \
        f"the shipped CrossoverTable marks ATTR_A ({lxg.ATTR_A:#04x}) with " \
        f"{table[lxg.ATTR_A]:#04x} — this test places its player on that attr, so the " \
        "no-layer-write assertion below would be measuring the mark, not the control"
    marked = sum(1 for b in table if b != K["XOVER_NONE"])
    assert marked <= 8, \
        f"{marked} of 256 CrossoverTable slots are marked. That is not wrong in " \
        "itself, but it is far more than the authored loops in this act account for " \
        "(2 as of 2026-09-04), so re-read this test rather than raising the number"
    w = lxg.World(rom, prog, extents, syms, equs)
    w.fill_plane(0, lxg.ATTR_A)
    w.place(lxg.IN_CELL[0], lxg.IN_CELL[1], K["LAYER_PATH_A"])
    w.set_x_vel(lxg.RIGHT)              # a LIVE direction: a silent pass here must be
                                        # the unmarked cell's doing, not x_vel == 0
    trace = w.frame()
    assert not w.layer_writes(trace), \
        "the shipped, unmarked ROM wrote the layer byte — every act would be a loop"


def test_the_gate_refuses_a_vacuous_pass(cut, K):
    """`run_all` must FAIL when nothing was moved by a table byte. Without this, a read
    site that never fires produces zero mismatches and an all-green report — the exact
    shape of pass this file exists to refuse. Demonstrated by neutering the world (an
    off-cache position for every case) rather than by trusting the counter."""
    rom, prog, extents, syms, equs = cut
    honest = lxg.run_all(rom, prog, extents, syms, equs)
    assert honest["fails"] == [] and honest["moved_by_rom"] > 0, \
        "the honest baseline is not green — the control for this test is broken"

    real = lxg.World

    class Deaf(real):
        """A world where the player is never on a real cell, so the lookup always
        returns CTYPE_AIR and NO ROM byte can reach the layer. Every value the sweep
        writes into CrossoverTable is therefore unread — the exact state a read site
        that never fires would produce."""
        def place(self, x, y, layer):
            real.place(self, 0xF000, 0xF000, layer)

    lxg.World = Deaf
    try:
        deaf = lxg.run_all(rom, prog, extents, syms, equs)
    finally:
        lxg.World = real

    assert deaf["moved_by_rom"] == 0, \
        "the neutered world still moved a layer — the control is wrong, not the gate"
    assert any("NOT ONE execution" in why for _, why in deaf["fails"]), \
        "run_all reported no vacuity finding on a world where no ROM byte could " \
        "possibly have moved a layer: %r" % (deaf["fails"],)


# -------------------------------------------------------------------- 3. the model

def test_the_model_is_a_bijection_onto_the_two_layers(K):
    """A restatement of `1 -> 0, 2 -> 1` would pass with a mis-typed bias. What must
    hold is that the two legal values map onto the two legal layers, one each.

    Asserted on `mark_target`, the ENCODING's half alone. The direction rule gates
    whether that target is taken; it does not change what the target IS, and folding
    the two together here would let a broken bias hide behind a refused fire."""
    out = [lxg.mark_target(v, K) for v in (K["XOVER_TO_A"], K["XOVER_TO_B"])]
    assert sorted(out) == sorted([K["LAYER_PATH_A"], K["LAYER_PATH_B"]]), \
        "the crossover values do not cover the two layers exactly once: %r" % out


def test_xover_none_is_the_identity_on_both_layers(K):
    for layer in (K["LAYER_PATH_A"], K["LAYER_PATH_B"]):
        for vel in (lxg.RIGHT, lxg.LEFT, lxg.STILL):
            assert lxg.model(layer, K["XOVER_NONE"], K, vel) == layer


def test_the_direction_rule_is_the_arc_the_mark_leads_onto(K):
    """The rule, DERIVED from the plane split rather than transcribed as a table.

    Plane B carries a loop's RIGHT arc and plane A its LEFT arc, so a mark fires only
    when the player's screen-space horizontal travel is heading for the arc that mark
    leads onto. Everything below follows from `mark_target` and `travel_plane`; nothing
    here spells 0, 1 or a direction constant, so a flipped LAYER_PATH_* would move the
    expectation with the rule instead of being caught by a stale literal."""
    for value in (K["XOVER_TO_A"], K["XOVER_TO_B"]):
        target = lxg.mark_target(value, K)
        matching = lxg.RIGHT if target == K["LAYER_PATH_B"] else lxg.LEFT
        opposing = lxg.LEFT if matching == lxg.RIGHT else lxg.RIGHT
        for layer in (K["LAYER_PATH_A"], K["LAYER_PATH_B"]):
            assert lxg.model(layer, value, K, matching) == target, \
                "a mark leading onto plane %d did not fire for a player travelling " \
                "onto that arc" % target
            assert lxg.model(layer, value, K, opposing) == layer, \
                "a mark leading onto plane %d fired for a player travelling AWAY " \
                "from that arc — this is the witnessed defect" % target
            assert lxg.model(layer, value, K, lxg.STILL) == layer, \
                "a mark fired for a player with no horizontal travel at all"


def test_the_direction_rule_is_what_the_witness_measured_wrong(K):
    """The witnessed defect, named as its own case so the fix has an address.

    docs/witness/loop-plane-b-exit-2026-09-05.json run A: a player on plane A moving
    LEFT crossed a loop's bottom centre — which carries XOVER_TO_B on plane A, the only
    value R2 permits there — and was moved to plane B, whose LEFT half is not solid. He
    ended 253 px below the ground he should have been standing on."""
    assert lxg.model(K["LAYER_PATH_A"], K["XOVER_TO_B"], K, lxg.LEFT) \
        == K["LAYER_PATH_A"], \
        "a leftward player on plane A is still sent to plane B by a bottom-centre " \
        "XOVER_TO_B — the defect the direction rule exists to close"
    assert lxg.model(K["LAYER_PATH_A"], K["XOVER_TO_B"], K, lxg.RIGHT) \
        == K["LAYER_PATH_B"], \
        "the RIGHTWARD entrant, which was the one case that already worked, stopped " \
        "working — the rule must not close the defect by refusing everything"


def test_the_bias_the_routine_emits_is_the_one_the_model_uses(cut, K):
    """R6 from the other side. The .emp `ensure` block binds XOVER_LAYER_BIAS to
    LAYER_PATH_A/B at build time; this checks the number actually reached the emitted
    instruction, by reading the routine's own bytes for the subq immediate."""
    rom, prog, extents, syms, equs = cut
    start, end = extents[0]
    subqs = [(a, ops) for a, (m, ops, _) in prog.items()
             if start <= a < end and m.startswith("subq")]
    assert len(subqs) == 1, \
        "expected exactly one subq in %s, found %d — the value->layer step is supposed " \
        "to be a single subtraction" % (lxg.READ_SITE, len(subqs))
    imm = subqs[0][1][0]
    assert imm[0] == "imm" and imm[1] == K["XOVER_LAYER_BIAS"], \
        "the emitted subq subtracts %r, but the build's XOVER_LAYER_BIAS is %d" \
        % (imm, K["XOVER_LAYER_BIAS"])


def test_the_cell_mask_matches_the_declared_cell_footprint(cut, K):
    """The edge trigger's quantisation is an `andi.l` immediate. It must be the mask
    COLL_CELL_W/H derive to, or the trigger is on a different grid from the lookup."""
    rom, prog, extents, syms, equs = cut
    start, end = extents[0]
    andis = [ops for a, (m, ops, _) in prog.items()
             if start <= a < end and m == "andi.l"]
    assert len(andis) == 1, "expected one andi.l (the cell quantiser), found %d" % len(andis)
    want = (((0x10000 - K["COLL_CELL_W"]) << 16) | (0x10000 - K["COLL_CELL_H"]))
    assert andis[0][0][1] == want, \
        "the emitted cell mask is $%08X but COLL_CELL_W/H (%d x %d) derive to $%08X" \
        % (andis[0][0][1], K["COLL_CELL_W"], K["COLL_CELL_H"], want)


# ------------------------------------------------------------------- the cut itself

def test_the_fixture_carries_both_canonical_shapes():
    assert FIXTURE.exists(), "%s is missing — regenerate with " \
                             "tools/loop_crossover_gate.py --write-fixture" % FIXTURE
    shapes = set(lxg.cut_shapes(FIXTURE))
    assert {"s4.lst", "s4.debug.lst"} <= shapes, \
        "committed cuts: %s — both canonical sonic4 shapes must be graded here, or " \
        "the release ROM's copy of the routine is never executed. Regenerate with " \
        "tools/loop_crossover_gate.py --write-fixture" % sorted(shapes)
