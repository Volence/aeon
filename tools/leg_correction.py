"""leg_correction — hardware-correction constants for harness figures (Empyrean v2 step 0).

STUB written by Task 3 (B3) so the per-DMA VBlank-end probe can consume the two names it
needs; Task 4 (B4) OWNS this file and replaces the stub (same names, same values).
"""

#: Master clocks per scanline (NTSC/PAL alike: 3,420 mclk = 342 pixel clocks x 10).
MCLK_PER_LINE = 3420

#: The last line a VBlank DMA may END on, + 0 mclk. Hardware's blank-rate window ends at about
#: line 261 + 0, give or take a line (Oracle fitness finding 3,
#: oracle/docs/audits/Oracle fitness.md:77); 260 keeps one line of that uncertainty as margin.
DMA_END_LIMIT_LINE = 260
