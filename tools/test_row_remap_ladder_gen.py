#!/usr/bin/env python3
"""The ROW REMAP LADDER GENERATOR's gate (EFFECTS-W1 item 9, parcel 9b).

RUNNER: `python3 -m pytest tools -q --no-header -p no:cacheprovider`, which `build.sh`
invokes BUILD-FATALLY in its verification lane (the `import pytest` arm, "Running the
tool-suite unit tests"). It needs no ROM and no emulator, which is why it can live there.

⚠ THIS FILE WAS WRITTEN AND PROVEN RED BEFORE `tools/row_remap_ladder_gen.py` EXISTED.
That ordering is the parcel's whole point and it is not decoration. A gate written after a
generator gets written against what the generator HAPPENED TO EMIT, which makes it a
transcription of the bug if there is one. Every expectation below is derived from either a
source constant read out of the tree at run time, or from the ladder model's own algebra —
none of it is copied from an output.

WHAT IT IS NOT. It does not pin the emitted image byte for byte. The four fixtures this
repo repaired on 2026-09-04 all pinned absolute addresses and went red on innocent changes;
a byte-pin of GENERATED data is the same trap one level over — it would go red on any H
change, on any model change, and it would never once have told you WHICH property broke.
The properties below name themselves when they fail.

THE DIVISION OF LABOUR WITH THE 9a GATE. `tools/row_remap_gate.py` reads the LINKED IMAGE
and re-checks the ladder's three invariants at the address the band record points at — "the
generator is right" and "the right bytes reached the ROM" are two different claims. This
file asks the first one, across every band height the runtime can express, before a ROM
exists. Neither subsumes the other.

THE PROPERTIES, and where each one comes from:

  (P1) SIZE IDENTITY, against the COMPILED-IN height. `ROW_REMAP_H16` is read out of
       `engine/level/parallax_dsl.emp`, the declared return-array length of
       `row_remap_ladder16()` is read out of the same file, and the two must satisfy
       `len == (H+1) * H`. Neither number is typed here. This is the arm that catches a
       hand-edited `[u8; N]` drifting away from the H beside it — which would link, and
       which the runtime would index straight past the end of.

  (P2) THE GENERATOR SPANS THE RUNTIME'S EXPRESSIBLE HEIGHTS. The band record stores the
       height as a SHIFT (`band_remap.brm_hshift`, consumed as `1 << brm_hshift`), so the
       expressible set is powers of two. The upper end is derived, not chosen: the ladder is
       `[u8]`, the model's largest entry is `2*(H-1)`, so `2*(H-1) <= 255` gives `H <= 128`.
       The generator must produce a correct ladder at every such H and must REFUSE the ones
       above it rather than emit silently-truncated bytes.

  (P3) THE THREE INVARIANTS, at every H in that sweep. `entry[i] >= i` (the permute is in
       place and forward), non-decreasing (rows are reordered/repeated/dropped, never
       swapped), `entry[i] <= 2i` (the read bound the pass caps its run at span/2 on).
       Their wording lives in `engine/level/parallax_dsl.emp`; their consequences are in
       `Parallax_Fill_PerLine`.

  (P4) THE ANCHOR ROWS, which are what makes the ladder a LADDER and not a table. Row H is
       selected when `|p| = 0` and must be exactly the identity — that is the no-op rung and
       a remap that is live with zero separation is a bug that costs cycles and shows
       nothing. Row 0 is the maximal rung and its last entry must SATURATE the read bound at
       exactly `2*(H-1)` — the model is built to reach the bound and not to cross it, so an
       entry short of it means the compression is being thrown away and an entry past it
       means P3 was only ever true by luck.

  (P5) MONOTONE IN THE SELECTOR. For a fixed output line `i`, `ladder[r][i]` must be
       non-increasing in `r`. `r = H - |p|`, so this says: MORE separation compresses MORE.
       A sign flip in the `p` term satisfies P3 and P4 at both ends and inverts the effect
       in between; nothing else here can see that.

  (P6) NOT ALL-IDENTITY. `entry[i] = i` satisfies P3 in full, and a ladder of nothing but
       identity rows spends the pass's cycles writing the buffer back unchanged. This is the
       fourth arm 9a's ROM gate carries, asked one level earlier.

LOUD ON UNMEASURABLE. A missing generator module, an unparseable `ROW_REMAP_H16`, an
unparseable return type — every one of them FAILS. None of them skips. A gate that answered
"nothing to check" would pass hardest exactly when the thing it guards had been deleted.
"""
from __future__ import annotations

import importlib.util
import os
import re

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DSL = os.path.join(REPO, "engine/level/parallax_dsl.emp")
GEN_PATH = os.path.join(REPO, "tools/row_remap_ladder_gen.py")


# --------------------------------------------------------------------------- sources


def _dsl_text() -> str:
    if not os.path.isfile(DSL):
        pytest.fail(f"UNMEASURABLE: {DSL} does not exist — the ladder model's source "
                    f"constants cannot be read, so nothing below is derived from anything.")
    return open(DSL, encoding="utf-8").read()


def shipped_h() -> int:
    """The band height ACTUALLY COMPILED IN, off `ROW_REMAP_H16` in parallax_dsl.emp."""
    m = re.search(r"pub const ROW_REMAP_H16 = (\d+)", _dsl_text())
    if not m:
        pytest.fail("UNMEASURABLE: `pub const ROW_REMAP_H16` is not declared in "
                    "engine/level/parallax_dsl.emp — the gate has no compiled-in height to "
                    "check the emitted table's size against.")
    return int(m.group(1))


def shipped_table_len() -> int:
    """The DECLARED length of `row_remap_ladder16()`'s return array, off its signature."""
    m = re.search(r"pub comptime fn row_remap_ladder16\(\)\s*->\s*\[u8;\s*(\d+)\]", _dsl_text())
    if not m:
        pytest.fail("UNMEASURABLE: could not read the return type of `row_remap_ladder16()` "
                    "from engine/level/parallax_dsl.emp. Its declared `[u8; N]` is the only "
                    "place the emitted table's size is stated, so P1 has no subject.")
    return int(m.group(1))


def load_gen():
    """`tools/row_remap_ladder_gen.py`, imported by path.

    ⚠ A MISSING GENERATOR IS A FAILURE, NEVER A SKIP. On 2026-09-04 this gate was run in
    exactly that state on purpose — it is the red-first proof — and it printed the message
    below and exited non-zero."""
    if not os.path.isfile(GEN_PATH):
        pytest.fail(f"UNMEASURABLE: {GEN_PATH} does not exist. This is the row-remap ladder "
                    f"GENERATOR (EFFECTS-W1 item 9b); without it every property below is "
                    f"unasked. This gate refuses to pass on its absence.")
    spec = importlib.util.spec_from_file_location("row_remap_ladder_gen", GEN_PATH)
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception as exc:                                   # pragma: no cover
        pytest.fail(f"UNMEASURABLE: {GEN_PATH} exists but does not import: {exc!r}")
    for sym in ("ladder", "MAX_H", "expressible_heights"):
        if not hasattr(mod, sym):
            pytest.fail(f"UNMEASURABLE: {GEN_PATH} defines no `{sym}` — the gate's contract "
                        f"with the generator is `ladder(H) -> bytes`, `MAX_H`, and "
                        f"`expressible_heights()`.")
    return mod


# --------------------------------------------------------- derived expectations, no pins


def derived_max_h() -> int:
    """The largest H whose ladder still fits `[u8]`, DERIVED from the read bound.

    The model's largest entry is the saturating one, `2*(H-1)` (P4). A u8 holds 0..255, so
    `2*(H-1) <= 255` and, H being a power of two, `H <= 128`. Typed nowhere; if the runtime
    ever widens the ladder to u16 this derivation is what has to change, and it is one line."""
    h = 2
    while 2 * (2 * h - 1) <= 255:
        h *= 2
    return h


def derived_heights() -> list[int]:
    """Every band height the runtime can EXPRESS: `band_remap.brm_hshift` is consumed as `1 << s`,
    so the set is the powers of two from 2 (the model divides by H-1) up to derived_max_h()."""
    out, h = [], 2
    while h <= derived_max_h():
        out.append(h)
        h *= 2
    return out


def rows_of(tab, H: int):
    return [list(tab[r * H:(r + 1) * H]) for r in range(len(tab) // H)]


# ------------------------------------------------------------------------------ P1


def test_p1_size_identity_against_the_compiled_in_height():
    """The emitted table's DECLARED length is exactly (H+1)*H for the H beside it."""
    H = shipped_h()
    declared = shipped_table_len()
    assert declared == (H + 1) * H, (
        f"P1 SIZE IDENTITY BROKEN. engine/level/parallax_dsl.emp declares "
        f"ROW_REMAP_H16 = {H} and `row_remap_ladder16() -> [u8; {declared}]`, but a ladder "
        f"is (H+1) rows of H bytes = {(H + 1) * H}. One of the two was hand-edited without "
        f"the other. The runtime indexes `row * H + i` into this array, so the short side "
        f"is read past its end and the long side ships dead bytes.")


def test_p1_generator_reproduces_the_shipped_table_size():
    """The generator, asked for the height the ENGINE compiled in, produces exactly the
    table the engine declares. Not a byte pin — a LENGTH agreement between the parameterised
    generator and the fixed-H comptime fn it parameterises."""
    gen = load_gen()
    H = shipped_h()
    assert len(gen.ladder(H)) == shipped_table_len(), (
        f"The generator at H={H} produces {len(gen.ladder(H))} bytes; "
        f"row_remap_ladder16() declares {shipped_table_len()}. The generator is meant to be "
        f"the model's canonical parameterisation — if it disagrees with the one instantiation "
        f"that ships, it is not generating the same ladder.")


# ------------------------------------------------------------------------------ P2


def test_p2_generator_max_h_is_the_derived_u8_ceiling():
    gen = load_gen()
    want = derived_max_h()
    assert gen.MAX_H == want, (
        f"P2: the generator caps H at {gen.MAX_H}; the u8 read bound derives {want} "
        f"(largest entry is 2*(H-1), and 2*(H-1) <= 255). A cap above this emits entries "
        f"that wrap in a byte and a cap below it refuses heights the runtime can express.")


def test_p2_generator_spans_every_expressible_height():
    gen = load_gen()
    assert list(gen.expressible_heights()) == derived_heights(), (
        f"P2: the generator offers {list(gen.expressible_heights())}; `band_remap.brm_hshift` is "
        f"consumed as `1 << s`, so the expressible set is {derived_heights()}.")


def test_p2_generator_refuses_a_height_that_would_not_fit_u8():
    gen = load_gen()
    over = derived_max_h() * 2
    with pytest.raises(Exception):
        gen.ladder(over)


def test_p2_generator_refuses_a_non_power_of_two_height():
    """`brm_hshift` cannot express it, so emitting one would produce a table no band record can
    name — bytes in the ROM that nothing indexes."""
    gen = load_gen()
    with pytest.raises(Exception):
        gen.ladder(24)


# ------------------------------------------------------------------------------ P3


@pytest.mark.parametrize("H", derived_heights())
def test_p3_three_invariants_hold_at_every_expressible_height(H):
    gen = load_gen()
    tab = gen.ladder(H)
    assert len(tab) == (H + 1) * H, (
        f"P3 has no subject at H={H}: the generator returned {len(tab)} bytes, not "
        f"{(H + 1) * H}.")
    for r, row in enumerate(rows_of(tab, H)):
        prev = -1
        for i, v in enumerate(row):
            assert 0 <= v <= 255, (
                f"H={H} row {r} entry {i} = {v} does not fit the u8 the ladder is declared as")
            assert v >= i, (
                f"H={H} row {r} entry {i} = {v} < i. The permute is IN PLACE and FORWARD — "
                f"read base and write cursor are one address — so this line reads a slot the "
                f"pass has already overwritten and the loop feeds on its own output.")
            assert v <= 2 * i, (
                f"H={H} row {r} entry {i} = {v} > 2i. The pass caps its remapped run at "
                f"span/2 on the strength of this bound; break it and the fetch leaves the "
                f"band and pulls the NEXT band's scroll words in, which looks like a "
                f"plausible effect and is not one.")
            assert v >= prev, (
                f"H={H} row {r} entry {i} = {v} descends from {prev}. Rows may be reordered, "
                f"repeated and dropped; never SWAPPED. A descending pair is a scroll word "
                f"travelling backwards down the band — a tear, not compression.")
            prev = v


# ------------------------------------------------------------------------------ P4


@pytest.mark.parametrize("H", derived_heights())
def test_p4_row_h_is_the_identity_rung(H):
    gen = load_gen()
    row = rows_of(gen.ladder(H), H)[H]
    assert row == list(range(H)), (
        f"P4: at H={H} row {H} is not the identity. That row is selected when |p| = 0 — the "
        f"background's image of the surface has not separated from the foreground's — and a "
        f"remap that is live at zero separation costs the pass's cycles and shows nothing.\n"
        f"  got  {row[:8]}...\n  want {list(range(min(8, H)))}...")


@pytest.mark.parametrize("H", derived_heights())
def test_p4_row_zero_saturates_the_read_bound(H):
    """The maximal rung reaches the bound exactly. Short of it, the model is throwing
    compression away; past it, P3 was only ever true by luck."""
    gen = load_gen()
    row = rows_of(gen.ladder(H), H)[0]
    assert row[-1] == 2 * (H - 1), (
        f"P4: at H={H} the maximal row's last entry is {row[-1]}, not the saturating "
        f"{2 * (H - 1)}. Row 0 is |p| = H, the deepest separation the ladder has a rung for; "
        f"it is built to reach `entry[i] <= 2i` at the far end and not to cross it.")


# ------------------------------------------------------------------------------ P5


@pytest.mark.parametrize("H", derived_heights())
def test_p5_monotone_in_the_selector(H):
    """More separation compresses more. `r = H - |p|`, so along decreasing r each output line
    must reach FURTHER down the source."""
    gen = load_gen()
    rows = rows_of(gen.ladder(H), H)
    for i in range(H):
        col = [rows[r][i] for r in range(H + 1)]
        for r in range(H):
            assert col[r] >= col[r + 1], (
                f"P5: at H={H}, output line {i} reads source {col[r]} at row {r} and "
                f"{col[r + 1]} at row {r + 1}. Row index is `H - |p|`, so a LOWER row is MORE "
                f"separation and must compress at least as hard. This is what a sign flip on "
                f"the p term looks like — it satisfies both anchor rows and every invariant "
                f"and inverts the effect between them.")


# ------------------------------------------------------------------------------ P6


@pytest.mark.parametrize("H", derived_heights())
def test_p6_not_all_identity(H):
    gen = load_gen()
    rows = rows_of(gen.ladder(H), H)
    moved = sum(1 for r in range(H) if rows[r] != list(range(H)))
    assert moved > 0, (
        f"P6: at H={H} EVERY row is the identity. All three invariants are satisfied by "
        f"`entry[i] = i` — they cannot see this — but the pass would write the buffer back "
        f"unchanged and NOTHING IS ON SCREEN.")
