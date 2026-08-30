#!/usr/bin/env python3
"""The d-47 `targeted` re-cut, guarded at its PRODUCER rather than at its output.

WHAT THIS GATE IS FOR
---------------------
`games/sonic4/data/collision/collision_data.emp` asserts the budget
(`dplc_peak_entries(_dplc_sonic) + DPLC_ENTRY_RESERVE <= DMA_IMPORTANT_SLOTS`),
and `tools/dplc_straddle.py --gate` asserts the SLOT cost at the linked base. Both
read the SHIPPED blob. Neither can say where that blob came from, so neither would
notice a hand-edit, a stale copy, or a re-export that happened to land under the
wall for the wrong reason.

This file closes that: it re-runs the producer and requires the committed bytes to
be exactly what it emits. The re-cut is then reproducible rather than a one-time
artifact somebody generated once and committed.

PROVENANCE, MEASURED HERE AND NOT INHERITED
-------------------------------------------
`test.sh` carried a note saying optimized-art reproduction was UNVERIFIED and that
`dplc_layout.py` "is not the producer of the committed blobs". That was right about
`dplc_layout.py` and wrong to stop there. Measured 2026-08-30:

  * sonic      — `tools/dedup_art.py` reproduces BOTH blobs byte-identically
                 (with `--entry-cap`, since the re-cut; without it, before).
                 That is what this file tests.
  * tails      — `dplc_layout.py` reproduces the DPLC byte-identically; the ART
                 blob matches NEITHER producer. Still open, deliberately not
                 asserted here rather than asserted loosely.
  * tails_tail — neither producer reproduces it. Also still open.

So the producers are MIXED per character, which is why a single blanket comparison
could never have gone green and why the note read as a total failure.

RED-FIRST, AND WHY THE ANTI-VACUITY TEST IS THE LOAD-BEARING ONE
-----------------------------------------------------------------
"The committed blob equals what the producer emits" passes trivially if the
producer's cap does nothing. `test_the_entry_cap_is_load_bearing` runs the same
producer with the cap OFF and requires the peak to be OVER the wall — so the cap
is proven to be the thing holding the budget, not decoration. If a future
re-export made the deduped sheet fit on its own, that test goes red and says so,
which is the correct signal (the cap became unnecessary) rather than a silent pass.
"""

import importlib.util
import pathlib
import re
import struct
import sys

import pytest

TOOLS = pathlib.Path(__file__).resolve().parent
ROOT = TOOLS.parent

ART_SRC = ROOT / "art/uncompressed/characters/sonic.bin"
DPLC_SRC = ROOT / "games/sonic4/data/dplc/sonic.bin"
ART_OUT = ROOT / "art/optimized/characters/sonic.bin"
DPLC_OUT = ROOT / "games/sonic4/data/dplc/optimized/sonic.bin"

TILE = 32


def _load(name):
    spec = importlib.util.spec_from_file_location(name, str(TOOLS / f"{name}.py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


da = _load("dedup_art")
dl = da.dl


# ------------------------------------------------------------ derived constants

def _const(rel, name):
    """`pub const NAME = <int>` out of an .emp file. Derived, never typed here."""
    text = (ROOT / rel).read_text()
    m = re.search(r'^\s*pub\s+const\s+' + re.escape(name) + r'\s*=\s*(\$?[0-9A-Fa-f]+)\s*(?://.*)?$',
                  text, re.M)
    assert m, f"no `pub const {name} = <int>` in {rel} — the wall this gate uses is gone"
    raw = m.group(1)
    return int(raw[1:], 16) if raw.startswith('$') else int(raw)


def wall():
    """DMA_IMPORTANT_SLOTS - DPLC_ENTRY_RESERVE, each read from its owning file.

    This is the whole expectation of this gate and it is computed, not copied: the
    engine owns the slot count, the DPLC module owns the reserve, and the cap the
    producer is run with below is this number. Move either constant and every
    assertion here moves with it.
    """
    return (_const("engine/system/constants.emp", "DMA_IMPORTANT_SLOTS")
            - _const("engine/objects/dplc.emp", "DPLC_ENTRY_RESERVE"))


def _frames(blob):
    return dl.parse_dplc(blob)


def _peak_entries(blob):
    return max(len(f) for f in _frames(blob))


def _produce(cap):
    """Run the real producer end to end. Returns (art_bytes, dplc_bytes)."""
    art = ART_SRC.read_bytes()
    frames = dl.parse_dplc(DPLC_SRC.read_bytes())
    new_art, new_frames = da.dedup(art, frames)
    if cap is not None:
        new_art, new_frames, _ = da.entry_cap(new_art, new_frames, cap)
    return new_art, dl.write_dplc(new_frames)


# ------------------------------------------------------------------- the tests

def test_the_inputs_this_gate_derives_from_all_exist():
    """Loud on unmeasurable: a missing input is a RED gate, never a skipped one."""
    for p in (ART_SRC, DPLC_SRC, ART_OUT, DPLC_OUT):
        assert p.is_file(), f"{p.relative_to(ROOT)} is missing — this gate cannot run"


def test_the_shipped_sonic_dplc_is_exactly_what_the_producer_emits():
    _, dplc = _produce(wall())
    committed = DPLC_OUT.read_bytes()
    assert dplc == committed, (
        "games/sonic4/data/dplc/optimized/sonic.bin is not what "
        "`dedup_art.py --entry-cap %d` emits from the uncompressed sheet "
        "(produced %d B, committed %d B). Regenerate it rather than editing it."
        % (wall(), len(dplc), len(committed)))


def test_the_shipped_sonic_art_is_exactly_what_the_producer_emits():
    art, _ = _produce(wall())
    committed = ART_OUT.read_bytes()
    assert art == committed, (
        "art/optimized/characters/sonic.bin is not what "
        "`dedup_art.py --entry-cap %d` emits from the uncompressed sheet "
        "(produced %d B, committed %d B). Regenerate it rather than editing it."
        % (wall(), len(art), len(committed)))


def test_the_committed_peak_is_exactly_the_wall():
    """Not `<=`. The re-cut targets the wall, so landing UNDER it means the sheet
    changed and the number should be re-derived before it is adopted."""
    peak = _peak_entries(DPLC_OUT.read_bytes())
    assert peak == wall(), (
        "DPLC_Sonic's peak entry count is %d, not the wall %d "
        "(DMA_IMPORTANT_SLOTS - DPLC_ENTRY_RESERVE) — re-derive it" % (peak, wall()))


def test_the_entry_cap_is_load_bearing():
    """ANTI-VACUITY. Without the cap the deduped sheet must be OVER the wall, or the
    equality above would hold for reasons having nothing to do with this parcel."""
    _, uncapped = _produce(None)
    peak = _peak_entries(uncapped)
    assert peak > wall(), (
        "the deduped sheet peaks at %d entries, already within the wall %d — the "
        "`--entry-cap` pass is doing nothing, so the budget gates above are passing "
        "vacuously. Re-derive whether the re-cut is still needed." % (peak, wall()))


def test_the_recut_frames_load_byte_identical_tiles():
    """The re-cut is only safe because it changes WHERE tiles come from and never
    WHICH tiles, in what order — that is what lets the mappings stay untouched.
    Checked against the RAW sheet, so it proves the whole chain and not just the
    last step."""
    raw_art = ART_SRC.read_bytes()
    raw_frames = dl.parse_dplc(DPLC_SRC.read_bytes())
    opt_art = ART_OUT.read_bytes()
    opt_frames = _frames(DPLC_OUT.read_bytes())
    assert len(raw_frames) == len(opt_frames), (
        "frame count changed: %d raw vs %d shipped" % (len(raw_frames), len(opt_frames)))
    bad = [i for i, (r, o) in enumerate(zip(raw_frames, opt_frames))
           if da.loaded_bytes(raw_art, r) != da.loaded_bytes(opt_art, o)]
    assert bad == [], (
        "%d frame(s) load different tile bytes after the re-cut, starting at $%02X — "
        "the sheet and the table are out of step" % (len(bad), bad[0] if bad else 0))


def test_only_frames_over_the_wall_were_re_cut():
    """The re-cut is TARGETED: it gives back dedup on the frames that need it and on
    no others. If it had touched a frame already under the wall it would be spending
    ROM for nothing, and this is what says so."""
    art = ART_SRC.read_bytes()
    frames = dl.parse_dplc(DPLC_SRC.read_bytes())
    deduped_art, deduped = da.dedup(art, frames)
    _, _, rewritten = da.entry_cap(deduped_art, deduped, wall())
    over = [i for i, f in enumerate(deduped) if len(f) > wall()]
    assert rewritten == over, (
        "the re-cut rewrote %s but the frames over the wall are %s"
        % (["$%02X" % i for i in rewritten], ["$%02X" % i for i in over]))


def test_appending_did_not_move_any_pool_index():
    """The re-cut appends, so every frame it did NOT rewrite must be bit-for-bit the
    entry list dedup produced. This is the property that makes the pass safe to run
    last, and nothing else checks it."""
    art = ART_SRC.read_bytes()
    frames = dl.parse_dplc(DPLC_SRC.read_bytes())
    deduped_art, deduped = da.dedup(art, frames)
    _, after, rewritten = da.entry_cap(deduped_art, deduped, wall())
    for i, (b, a) in enumerate(zip(deduped, after)):
        if i in rewritten:
            continue
        assert list(b) == list(a), (
            "frame $%02X changed although it was not re-cut — an append moved a "
            "pool index, which it must never do" % i)


def test_the_art_sheet_still_fits_the_tile_start_field():
    """The re-cut GROWS the sheet, and tile_start is 12 bits. collision_data.emp
    asserts this at build time; asserted here too because this is the file that
    would have to change the cap if it ever stopped fitting."""
    bits = _const("engine/objects/dplc.emp", "DPLC_TILE_START_BITS")
    tiles = len(ART_OUT.read_bytes()) // TILE
    assert tiles <= (1 << bits), (
        "Art_Sonic is %d tiles, past the %d a %d-bit tile_start can name"
        % (tiles, 1 << bits, bits))


def test_no_dplc_entry_points_past_the_sheet():
    """A DPLC/art pair that drifted out of step would DMA past the sheet. The re-cut
    writes both halves together, so this is the check that they were written from the
    same run."""
    tiles = len(ART_OUT.read_bytes()) // TILE
    worst = max((s + c for f in _frames(DPLC_OUT.read_bytes()) for s, c in f), default=0)
    assert worst <= tiles, (
        "a DPLC entry reaches tile %d but the sheet has %d" % (worst, tiles))


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
