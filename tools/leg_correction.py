"""leg_correction — the rule for correcting Oracle's cycle figures (Empyrean v2 step 0, B4).

WHY. Oracle omits two hardware costs (oracle/docs/audits/Oracle fitness.md, findings 3-5):
the 68000's DRAM refresh (2 cycles lost in every 128) and the Z80's bank-window stalls of the
68000 bus (up to about 2.6 % with sound playing). So a margin Oracle reports is optimistic, by
about 2 % of a frame (band 1.5-2.5 %, ESTIMATED from one BlastEm lag frame). This module is that
rule as code; `docs/audits/Hardware limits.md`, section "Correcting Oracle's numbers", is the
same rule as prose, and `tools/test_leg_correction.py::test_constants_match_hardware_limits_doc`
reads that section's numbers so the two cannot drift.

  * `corrected_margin` subtracts the refresh (always) and the Z80 stall bound (with sound) from
    a margin, in proportion to the cycles elapsed since VInt.
  * `classify` turns a corrected margin into FITS / OVER / NEEDS-WITNESS / WITNESS-DISAGREES.
    A "fits" whose corrected margin is under WITNESS_MARGIN_FRACTION of its budget is not a
    verdict on Oracle alone: it needs BlastEm (tools/blastem_witness.py) to agree on lag and
    path for the same tick-keyed inputs. BlastEm is a second MODEL, not hardware.

Task 3 (B3) created this file as a stub holding MCLK_PER_LINE and DMA_END_LIMIT_LINE for
tools/vblank_dma_probe.py; the names and values are unchanged.
"""
from __future__ import annotations

import math

#: 68000 cycles per NTSC frame: 262 lines x 3,420 mclk / 7 = 128,005.7 (measured mean
#: 127,983-128,033). The retired FRAME_CYC = 127840 must not be copied forward.
FRAME_CYCLES = 128006

#: Master clocks per scanline (NTSC/PAL alike: 3,420 mclk = 342 pixel clocks x 10).
MCLK_PER_LINE = 3420

#: NTSC lines per frame.
LINES_PER_FRAME = 262

#: Lines that move DMA at the blank rate, NTSC V28: 37 (V $E0-$1FE), not 38 -- line 261
#: (V $1FF) already fetches for line 0 (Hardware limits section 2; Oracle fitness finding 3).
BLANK_DMA_LINES = 37

#: The last line a VBlank DMA may END on, + 0 mclk. Hardware's blank-rate window ends at about
#: line 261 + 0, give or take a line (Oracle fitness finding 3,
#: oracle/docs/audits/Oracle fitness.md:77); 260 keeps one line of that uncertainty as margin
#: and needs no disputed GPL-only constant (fitness decision 2).
DMA_END_LIMIT_LINE = 260

#: The 68000 loses 2 cycles in every 128 to DRAM refresh (Kabuto; Oracle does not model it).
REFRESH_FRACTION = 2 / 128

#: Upper bound of the Z80 bank-window stalls of the 68000 with sound playing (Oracle fitness).
Z80_STALL_MAX_FRACTION = 0.026

#: A "fits" whose corrected margin is under this fraction of its budget needs a second witness.
WITNESS_MARGIN_FRACTION = 0.03

VERDICTS = ("FITS", "OVER", "NEEDS-WITNESS", "WITNESS-DISAGREES")


def correction(elapsed_cycles: int, sound_playing: bool) -> int:
    """Cycles Oracle did not charge over `elapsed_cycles` since VInt.

    Refresh: one 2-cycle stall per WHOLE 128-cycle period (floor: a partial period has not
    refreshed yet). Z80: the stall fraction is an upper bound, so it is rounded UP."""
    if elapsed_cycles < 0:
        raise ValueError(f"elapsed_cycles {elapsed_cycles} < 0")
    refresh = math.floor(elapsed_cycles * REFRESH_FRACTION)
    z80 = math.ceil(elapsed_cycles * Z80_STALL_MAX_FRACTION) if sound_playing else 0
    return refresh + z80


def corrected_margin(margin_cycles: int, elapsed_cycles: int, sound_playing: bool) -> int:
    """`margin_cycles` (budget - Oracle's measured cost) less the cycles Oracle omitted."""
    return int(margin_cycles) - correction(elapsed_cycles, sound_playing)


def classify(margin_cycles: int, budget_cycles: int, elapsed_cycles: int, sound_playing: bool,
             witness=None) -> str:
    """One of VERDICTS.

    OVER               the corrected margin is negative (Oracle is optimistic, so a witness
                       cannot rescue it).
    FITS               corrected margin >= WITNESS_MARGIN_FRACTION x budget, or under it with
                       a BlastEm witness (`blastem_witness.WitnessResult`) that agrees.
    NEEDS-WITNESS      under the threshold and no witness was run.
    WITNESS-DISAGREES  under the threshold and the witness disagrees on lag or path, or did
                       not cover the whole leg."""
    if budget_cycles <= 0:
        raise ValueError(f"budget_cycles {budget_cycles} <= 0: no budget to judge against")
    m = corrected_margin(margin_cycles, elapsed_cycles, sound_playing)
    if m < 0:
        return "OVER"
    if m >= WITNESS_MARGIN_FRACTION * budget_cycles:
        return "FITS"
    if witness is None:
        return "NEEDS-WITNESS"
    return "FITS" if witness.agrees() else "WITNESS-DISAGREES"
