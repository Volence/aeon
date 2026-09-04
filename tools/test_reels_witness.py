"""Unit cover for `tools/reels_witness.py` — the pure halves of the RESOLUTION.

WHY THIS FILE EXISTS AT ALL. The witness's discriminating assertion is not a delta row;
it is "which rate table did the engine select". That resolution is a walk over the ROM's
association table against a live RAM value, and the walk itself is pure Python — so it
can be exercised here, in build.sh's pytest lane, without an emulator. The EMULATOR half
(a2 at `.bound`, the buffer deltas) cannot live in a unit test and is run by hand; its
evidence, including the mandatory unbound control, is in the parcel report and in
docs/DEFERRED_WORK.md.

WHY THIS FILE NEVER OPENS A ROM, test_reels_gate.py's own reason: build.sh's pytest lane
runs BEFORE the sigil build, so a unit test opening `s4.debug.bin` here would grade a
PREVIOUS build. Every fixture below is a synthetic byte string built in the test.

⚠ THE PROPERTY THESE TESTS EXIST TO PROTECT, and it is easy to lose in a later edit:
`OJZ_Reels_Fill`'s `.bind` loop loads the CANDIDATE rates pointer (into d2) BEFORE it
compares the config, so a bound table's address is in a register on the MISS path too.
Measured in this tree 2026-09-04: with the unbound config $013DD4 active, `a2 = $01476C`
(the fallback) while `d2 = $013FCE` (the authored table). Any future assertion added to
the witness must therefore be checked against the UNBOUND CONTROL
(`tools/reels_witness.py <rom> <lst> --config natural`, which must FAIL) before it is
believed. A signal present in both arms is vacuous however green it goes.

PROVEN RED, on disk, against the built artifacts, 2026-09-04. The witness's own rule was
mutated and restored from the committed baseline, `__pycache__` cleared and
PYTHONPYCACHEPREFIX pointed at a scratch dir between runs:
  * the UNBOUND CONTROL, no mutation at all — `--config natural`, one value different
        -> exit 1 on the new expectation assertion, while all five delta rows, the
           a2-agreement row and the vacuity row stayed green EXACTLY as in the bound arm.
           That contrast is the proof the new assertion is the only discriminating one.
  * `resolve()` returning the selected address + 1
        -> exit 1 naming the a2 disagreement ("the engine selected $013FCE ... Python
           gives $013FCF").
  * the per-band expectation multiplied by SAMPLE_GAP_FRAMES instead of the measured
    execution count
        -> exit 1 on all five bands. This is the 2026-09-03 defect class, re-caught.
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))

import reels_gate as G   # noqa: E402
import reels_witness as W  # noqa: E402


def _table(pairs, base=0x10000):
    """A synthetic association table: (config, rates) longs then a zero terminator,
    laid out at `base` inside a byte image big enough to hold it."""
    img = bytearray(base + (len(pairs) * 2 + 1) * 4 + 16)
    off = base
    for cfg, rates in pairs:
        img[off:off + 4] = cfg.to_bytes(4, "big")
        img[off + 4:off + 8] = rates.to_bytes(4, "big")
        off += 8
    img[off:off + 4] = (0).to_bytes(4, "big")
    return bytes(img)


# ---------------------------------------------------------------------------
# parse_bindings — `.bind`'s loop shape, in Python.
# ---------------------------------------------------------------------------

def test_parse_bindings_reads_pairs_until_the_zero_config():
    img = _table([(0x13E92, 0x13FCE), (0x13F50, 0x13FD8)])
    assert W.parse_bindings(img, 0x10000) == [(0x13E92, 0x13FCE), (0x13F50, 0x13FD8)]


def test_parse_bindings_reads_an_empty_table_as_no_bindings():
    """A tree that authors no reels still emits the table — one terminator long — and the
    witness must read that as 'the fallback path', not as a parse failure."""
    assert W.parse_bindings(_table([]), 0x10000) == []


def test_parse_bindings_refuses_a_table_with_no_terminator():
    img = bytearray(0x10000)
    img += (0x13E92).to_bytes(4, "big") + (0x13FCE).to_bytes(4, "big")
    img += b"\x00\x11\x22\x33" * 4          # nonzero filler, never a terminator
    try:
        W.parse_bindings(bytes(img), 0x10000, limit_longs=8)
    except G.Unmeasurable:
        return
    raise AssertionError("a table with no zero terminator must be UNMEASURABLE — the "
                         "engine's own walk would run off the end of it")


def test_parse_bindings_refuses_running_past_the_image():
    img = (0x13E92).to_bytes(4, "big")      # a config long and nothing after it
    try:
        W.parse_bindings(img, 0)
    except G.Unmeasurable:
        return
    raise AssertionError("a table that runs past the ROM must be UNMEASURABLE")


# ---------------------------------------------------------------------------
# resolve — the selection rule, which is the whole discrimination.
# ---------------------------------------------------------------------------

def test_resolve_hits_the_bound_config():
    got, hit = W.resolve([(0x13E92, 0x13FCE)], 0x13E92, fallback_addr=0x1476C)
    assert (got, hit) == (0x13FCE, True)


def test_resolve_misses_an_unbound_config_and_keeps_the_fallback():
    """The control arm, as a unit. $013DD4 is a REAL scene binding (section 0) that simply
    authors no reels — the miss must be a miss, not a nearest match."""
    got, hit = W.resolve([(0x13E92, 0x13FCE)], 0x13DD4, fallback_addr=0x1476C)
    assert (got, hit) == (0x1476C, False)


def test_resolve_misses_when_no_scene_authors_reels():
    got, hit = W.resolve([], 0x13DD4, fallback_addr=0x1476C)
    assert (got, hit) == (0x1476C, False)


def test_resolve_takes_the_first_match_like_the_assembly_does():
    """`.bind` returns on the first `cmp.l`/`beq`, so a duplicated config resolves to the
    FIRST table. A Python walk that took the last one would disagree with the engine only
    in a case nobody has yet — which is the case a witness is for."""
    got, hit = W.resolve([(0x13E92, 0xAAAA), (0x13E92, 0xBBBB)], 0x13E92,
                         fallback_addr=0x1476C)
    assert (got, hit) == (0xAAAA, True)


def test_resolve_never_matches_a_zero_config():
    """Parallax_Current_Config is 0 before any config is installed (measured: it reads 0
    for the first ~60 frames of the scroll test). A zero must not select anything."""
    got, hit = W.resolve([(0x13E92, 0x13FCE)], 0, fallback_addr=0x1476C)
    assert (got, hit) == (0x1476C, False)


# ---------------------------------------------------------------------------
# signed_rates — the expectation, read from wherever the resolution pointed.
# ---------------------------------------------------------------------------

def test_signed_rates_decodes_twos_complement():
    img = bytearray(0x100)
    img[0x10:0x15] = bytes([0x03, 0xFB, 0x02, 0xFC, 0x06])
    assert W.signed_rates(bytes(img), 0x10, 5) == [3, -5, 2, -4, 6]


def test_signed_rates_round_trips_against_the_gate_encoder():
    """The gate encodes source ints to bytes; the witness decodes ROM bytes to ints. Two
    directions of one convention, pinned against each other rather than each against a
    hand-written table."""
    rates = [127, -128, 0, 1, -1]
    img = bytes(G.to_bytes_i8(rates))
    assert W.signed_rates(img, 0, len(rates)) == rates


def test_signed_rates_refuses_reading_past_the_image():
    try:
        W.signed_rates(b"\x03\xFB", 0, 5)
    except G.Unmeasurable:
        return
    raise AssertionError("a table running past the ROM must be UNMEASURABLE")


# ---------------------------------------------------------------------------
# local_label — the a2 read point. parse_lst drops every `$` name, so this is the only
# way the witness can find `.bound`, and a silent miss would cost the whole a2 arm.
# ---------------------------------------------------------------------------

def test_local_label_finds_a_proc_local_by_suffix(tmp_path):
    p = tmp_path / "x.lst"
    p.write_text("(0) 1/14772 :        OJZ_Reels_Fill:\n"
                 "(0) 2/1478C :        $games.sonic4.ojz_effects$OJZ_Reels_Fill$bound:\n")
    assert W.local_label(str(p), W.BOUND_LABEL_SUFFIX) == 0x1478C


def test_local_label_refuses_a_missing_label(tmp_path):
    p = tmp_path / "x.lst"
    p.write_text("(0) 1/14772 :        OJZ_Reels_Fill:\n")
    try:
        W.local_label(str(p), W.BOUND_LABEL_SUFFIX)
    except G.Unmeasurable:
        return
    raise AssertionError("a missing `.bound` label must be UNMEASURABLE — without a2 "
                         "there is nothing that separates a HIT from a MISS")


def test_local_label_refuses_an_ambiguous_suffix(tmp_path):
    """Two matches must be refused, not resolved by picking: a2 read at the wrong point
    in the routine is a convincing wrong answer rather than an error."""
    p = tmp_path / "x.lst"
    p.write_text("(0) 1/1478C :        $a$OJZ_Reels_Fill$bound:\n"
                 "(0) 2/1479C :        $b$OJZ_Reels_Fill$bound:\n")
    try:
        W.local_label(str(p), W.BOUND_LABEL_SUFFIX)
    except G.Unmeasurable:
        return
    raise AssertionError("an ambiguous label suffix must be UNMEASURABLE")


# ---------------------------------------------------------------------------
# The witness carries NO rates. This is the defect the parcel fixed, pinned so it
# cannot come back by a well-meaning "just cache the expected values" edit.
# ---------------------------------------------------------------------------

def test_the_witness_source_hardcodes_no_rate_array():
    src = (REPO / "tools" / "reels_witness.py").read_text()
    speeds = G.emp_int_array(G.FIXTURE, "OJZ_REEL_SPEEDS")
    literal = "[" + ", ".join(str(v) for v in speeds) + "]"
    body = src.split('"""', 2)[2]      # skip the module docstring, which quotes them
    assert literal not in body, (
        f"tools/reels_witness.py's CODE contains {literal} — the shipped fallback rates "
        f"as a Python literal. That is exactly the defect this parcel removed: pointed at "
        f"a ROM whose ACTIVE table is an authored one with different rates, a hardcoded "
        f"copy goes red because the authoring WORKED. Derive from the resolved table.")


def test_the_witness_derives_its_geometry_from_game_constants():
    """Both constants must be readable by the same `emp_const` the witness calls; a
    rename in constants.emp must break here, in the pytest lane, rather than in an
    emulator run nobody schedules."""
    assert G.emp_const(G.GAME_CONSTANTS, "REEL_BAND_COUNT") > 0
    assert G.emp_const(G.GAME_CONSTANTS, "REEL_COLS_PER_BAND") > 0
