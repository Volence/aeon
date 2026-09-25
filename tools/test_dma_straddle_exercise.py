#!/usr/bin/env python3
"""tools/dma_straddle_exercise.py: control B's forced frames must STRADDLE in the ROM it drives.

Control B proves the straddle instrument live by forcing a straddling DPLC frame into the
player and watching Dbg_DMA_Straddle_All move. That only works if the forced frame really
straddles a 128 KB boundary in THIS build, and which frames straddle depends on where the
linker put each character's art. The ladder used to be the literal (0x65, 0x9F, 0x85),
copied from tools/dplc_straddle.py's 2026-09-05 output. The art moved after that. On
s4.debug.bin crc32 62238a15 none of those three frames straddles, and a full campaign
printed "the instrument did NOT fire on any forced mapping frame of $65, $9F, $85"
(DPLC-STRADDLE-REACHABLE, docs/research/2026-09-25-dplc-straddle-reachable.md).

The expectation is DERIVED from the listing and ROM through tools/dplc_straddle.py's own
primitives: the labelled art bases, the DPLC tables, the TILE_SIZE constant and the
boundary it decodes out of dma_queue.emp's split instructions. No frame number is typed
here.
"""

from pathlib import Path

import pytest

import dplc_straddle as D
import dma_straddle_exercise as X

AEON = Path(__file__).resolve().parent.parent
ROM = AEON / "s4.debug.bin"
LST = AEON / "s4.debug.lst"


def _straddling_frames_per_player():
    """{subject name: [straddling frame indices]} for every PLAYER subject (the ones whose
    table Perform_DPLC walks for Player_1), in dplc_straddle's subject order."""
    tile = D.const_from_emp("engine/system/constants.emp", "TILE_SIZE")
    boundary = D.boundary_from_source()
    labels = D.lst_labels(str(LST))
    subs = D.load_subjects(labels)
    D.check_subject_extents(subs, D.rom_bytes(str(ROM)), str(ROM))
    kind = {art: b["kind"] for art, b in D.subject_bindings().items()}
    out = {}
    for s in subs:
        if kind.get(s["art_label"]) != "player":
            continue
        costs = D.frame_costs(s["frames"], s["art_base"], tile, boundary)
        out[s["name"]] = [i for i, c in enumerate(costs) if c[2]]
    return out


@pytest.mark.needs_build("s4.debug.bin", "s4.debug.lst")
def test_every_forced_control_frame_straddles_in_the_built_rom():
    per_player = _straddling_frames_per_player()
    straddlers = {f for frames in per_player.values() for f in frames}
    if not straddlers:
        pytest.fail("no player subject has a straddling DPLC frame in this build, so control B "
                    "has nothing to force. That is a real state of the ROM, but this test "
                    "cannot grade the ladder against it; say so rather than pass")
    ladder = X.default_control_ladder(str(LST), str(ROM))
    assert ladder, "the default control ladder is empty although straddling frames exist"
    dead = [f"${f:02X}" for f in ladder if f not in straddlers]
    assert not dead, (
        f"control B would force {dead}, which straddle for NO player subject in "
        f"{ROM.name}; the straddling frames are "
        + ", ".join(f"{n}: {' '.join(f'${f:02X}' for f in fr) or 'none'}"
                    for n, fr in per_player.items()))
    # One per character that has one: the DPLC walks only the ACTIVE character's table,
    # and the campaign's own presses can cycle the roster (control_body's docstring).
    missing = [n for n, fr in per_player.items() if fr and not set(fr) & set(ladder)]
    assert not missing, f"the ladder has no straddling frame for {missing}"
