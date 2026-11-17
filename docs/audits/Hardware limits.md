---
kind: reference
status: done
description: "Mega Drive ceilings every audit cites: clocks, cycles per frame/line, blank lines (37 DMA-rate lines NTSC V28, not 38), DMA bytes per line, memory sizes, sprite limits, Z80/YM/PSG facts. Each with a source."
---
# Hardware limits

The shared ceiling page for every system audit ([[AUDIT_TEMPLATE]] section 4). Cite a row; add a row
only when an audit needs a fact that is not here, with its source. Written 2026-11-16 by the Oracle-fitness
research stage.

Labels: **PUBLISHED** (a cited source states it), **ESTIMATED** (derived from published figures; the
derivation is shown). Emulator sources are cited as the authors' encoding of their own hardware tests:
Genesis Plus GX (GPGX, Eke-Eke), BlastEm (Mask of Destiny, who measured with a logic analyser), Ares.

> [!verdict] The five numbers most audits need (NTSC, H40, V28)
> - **128,006** 68000 cycles per frame, **488.6** per line (ESTIMATED: 262 × 3,420 / 7). After DRAM refresh the 68000 gets about **126,006** a frame, **481** a line (ESTIMATED: × 126/128; Kabuto measures "roughly 480").
> - **37** lines move DMA at the blank rate, not 38. Line 261 (V = `$1FF`) already fetches for line 0 (Kabuto, GPGX, BlastEm agree).
> - **204–205 B** of 68k→VRAM DMA per blank line, **18 B** per active line. About **7.5 KB** per VBlank (railgun publishes 7,524 B; 37 × 204 = 7,548 B).
> - **~17,800** 68000 cycles from VInt to the end of the blank-rate window (ESTIMATED: (37 × 3,420 − 788) / 7 × 126/128). The pilot used 18,566. That figure counts 38 lines and no refresh.
> - **20 sprites and 320 sprite pixels per line, 80 per frame** (H32: 16, 256 and 64).

## 1. Clocks

| Quantity | NTSC | PAL | Label / source |
|---|---|---|---|
| Master clock | 53,693,175 Hz | 53,203,424 Hz | PUBLISHED: GPGX `core/system.h:62-63` (`MCLOCK_NTSC`, `MCLOCK_PAL`) |
| 68000 clock | 7,670,454 Hz | 7,600,489 Hz | ESTIMATED: master ÷ 7 (BlastEm `MCLKS_PER_68K` 7; GPGX m68k step 7) |
| Z80 clock | 3,579,545 Hz | 3,546,895 Hz | ESTIMATED: master ÷ 15 (BlastEm `genesis.c:31` `MCLKS_PER_Z80 15`) |
| YM2612 clock | = 68000 clock | = 68000 clock | PUBLISHED: BlastEm `genesis.c:30` `MCLKS_PER_YM 7` |
| PSG (SN76489) clock | = Z80 clock | = Z80 clock | PUBLISHED: BlastEm `genesis.c:32` (`MCLKS_PER_PSG = MCLKS_PER_Z80*16`, the ÷16 being the PSG's internal divider) |

## 2. The frame

| Quantity | NTSC | PAL | Label / source |
|---|---|---|---|
| Master clocks per line (H32 and H40 with the normal dot clock) | 3,420 | 3,420 | PUBLISHED: Kabuto hardware notes ([plutiedev mirror](https://plutiedev.com/mirror/kabuto-hardware-notes)); GPGX `MCYCLES_PER_LINE 3420` |
| Lines per frame | 262 | 313 | PUBLISHED: Kabuto ("262 total", "313 total"); GPGX `vdp_ctrl.c:239` |
| Frame rate | 59.923 Hz | 49.701 Hz | ESTIMATED: master / (lines × 3,420) |
| **68000 cycles per frame** | **128,006** | **152,923** | ESTIMATED: lines × 3,420 / 7 |
| 68000 cycles per line | 488.57 | 488.57 | ESTIMATED: 3,420 / 7 |
| **68000 DRAM refresh** | 2 cycles lost per 128 | same | PUBLISHED: Kabuto ("The 68K loses 2 cycles out of every 128"); BlastEm `genesis.c:514-515` (`REFRESH_INTERVAL 128`, `REFRESH_DELAY 2`) |
| Usable 68000 cycles per frame / line | ≈ 126,006 / ≈ 481 | ≈ 150,533 / ≈ 481 | ESTIMATED: × 126/128. Kabuto: "roughly 480 cycles per raster line, after bus stealing" |
| Z80 cycles per frame / per line | 59,736 / 228 | 71,364 / 228 | ESTIMATED: lines × 3,420 / 15 |
| Line structure | 11 border, 224 picture, 8 border, 3+3+3 sync, 10 blank | 38 border, 224 picture, 32 border, 3+3+3 sync, 10 blank | PUBLISHED: Kabuto. V30 adds 8 lines to each border |

### Vertical blank

| Quantity | NTSC V28 | PAL V28 | PAL V30 | Label / source |
|---|---|---|---|---|
| V counter sequence | `$000-$0EA`, `$1E5-$1FF` | `$000-$102`, `$1CA-$1FF` | `$000-$10A`, `$1D2-$1FF` | PUBLISHED: Kabuto; GPGX `vdp_ctrl.c:161-168` (`vc_table`) |
| VBlank flag set / cleared | `$DF→$E0` / `$1FE→$1FF` | same | `$EF→$F0` / `$1FE→$1FF` | PUBLISHED: Kabuto |
| **Lines at the blank DMA rate** | **37** (V `$E0`–`$1FE`) | **88** | **72** | ESTIMATED from the V sequence and the clear point; matches GPGX `vdp_ctrl.c:685` (DMA in VBlank runs to `lines_per_frame − height − 1`) and BlastEm `vdp.c:123` (line `$1FF` is `PREPARING`, an active-fetch line) |
| Non-picture lines in total | 38 | 89 | 73 | ESTIMATED: lines − 224 (or 240) |
| Sega's own table | 36 | 87 | 71 | PUBLISHED: Sega *Genesis Technical Overview* v1.00 DMA table, as cited in the pilot ([[frame-architecture/1-research]] §4.1). It disagrees with the V-counter sources by one line |
| VInt position | line 224 (V `$E0`), 788 mclk into GPGX's line (H40), 770 (H32) | same | line 240 | PUBLISHED: GPGX `vdp_ctrl.c:57-58` (`VINT_H40_MCYCLE`, `VINT_H32_MCYCLE`) |
| **68000 cycles from VInt to end of blank-rate DMA** | **≈ 17,964** (≈ 17,683 after refresh) | ≈ 42,885 | ≈ 35,059 | ESTIMATED: (lines × 3,420 − 788) / 7, then × 126/128 |
| V counter increments | mid-line, at H `$A4→$A5` (H40), `$84→$85` (H32) | same | same | PUBLISHED: Kabuto |
| HBlank flag | H40 set `$B2→$B3`, cleared `$05→$06`; H32 set `$92→$93`, cleared `$04→$05` | same | same | PUBLISHED: Kabuto |

## 3. VDP memory and access

| Quantity | Value | Label / source |
|---|---|---|
| VRAM | 64 KB (2,048 tiles of 32 B) | PUBLISHED: GPGX `vdp_ctrl.c:68`; BlastEm `vdp.h:23` |
| CRAM | 64 entries × 9 bits (4 palettes × 16) | PUBLISHED: GPGX `vdp_ctrl.c:69`; BlastEm `vdp.h:17`; [railgun](https://md.railgun.works/index.php?title=VDP) |
| VSRAM | 40 entries (20 two-cell column pairs); BlastEm allows 64 on later VDPs | PUBLISHED: GPGX `vdp_ctrl.c:70` ("40 x 11-bit"); BlastEm `vdp.h:21-22` (`MIN_VSRAM_SIZE 40`, `MAX_VSRAM_SIZE 64`) |
| Write FIFO | 4 words; a write to a full FIFO freezes the 68000 until a slot frees | PUBLISHED: railgun; BlastEm `vdp.h:164` |
| VDP accesses per line | 210 (H40), 171 (H32), one every 2 VDP cycles | PUBLISHED: Kabuto |
| External (CPU/DMA) slots per **active** line | **18** (H40), **16** (H32), at irregular positions; largest gap 26 accesses | PUBLISHED: Kabuto slot strings; railgun; GPGX `vdp_ctrl.c:179-185` slot table; gap: TascoDLX, cited in Oracle `vdp.rs:874-880` |
| External slots per **blank** line | 204–205 (H40), 166–167 (H32) | PUBLISHED: GPGX `vdp_ctrl.c:188-193` (204/166, one extra refresh with display off, per Mask of Destiny); Sega table 205; Kabuto (210 − 5 refresh) |
| 68k→VRAM DMA, bytes per line | **204–205 blank, 18 active** (H40); 166–167 / 16 (H32) | PUBLISHED: as above (one slot per byte) |
| 68k→CRAM/VSRAM DMA, words per line | 198 blank, 18 active (H40); 161 / 16 (H32) | PUBLISHED: GPGX `vdp_ctrl.c:664-670` (refresh costs one more slot for word targets) |
| VRAM fill, bytes per line | 203 blank, 17 active (H40); 165 / 15 (H32) | PUBLISHED: GPGX `vdp_ctrl.c:642-648` |
| VRAM copy, bytes per line | 102 blank, 9 active (H40); 83 / 8 (H32); the 68000 keeps running | PUBLISHED: GPGX `vdp_ctrl.c:649-652`; railgun |
| **68k→VRAM DMA per VBlank, NTSC H40 V28** | **7,524 B** (railgun) / 7,548 B (37 × 204) | PUBLISHED / ESTIMATED |
| same, PAL H40 V28 / V30 | 17,622 / 14,454 B (railgun); 17,952 / 14,688 B (88 / 72 × 204) | PUBLISHED / ESTIMATED |
| 68k→VRAM DMA in active display, whole frame | 4,032 B (H40), 3,584 B (H32) | PUBLISHED: railgun |
| 68000 cost of a 68k→VDP DMA | the 68000 is frozen for the whole transfer. Kabuto: slow (64 KB-mode VRAM) `max(words×2.4+5.6, words×4.7−6)` cycles, fast (CRAM, VSRAM) `words×2.4+5.6` | PUBLISHED: Kabuto |
| DMA source limits | cannot cross a 128 KB source boundary; length 0 = 65,536 words | PUBLISHED: [plutiedev, hardware issues](https://plutiedev.com/hardware-issues) |
| Display-enable change | takes effect at 16-pixel granularity mid-line; mid-line disable "will always break something" | PUBLISHED: Sik and Kabuto, as cited in `aeon/docs/research/megaact-bg-streaming/05-online-and-tech-demos.md` §2 |

## 4. Sprites

| Quantity | H40 | H32 | Label / source |
|---|---|---|---|
| Sprites per frame (link list) | 80 | 64 | PUBLISHED: [plutiedev, sprites](https://plutiedev.com/sprites); BlastEm `vdp.h:33-34` |
| Sprites per line | 20 | 16 | PUBLISHED: same; BlastEm `vdp.h:31-32`; railgun (SOVR set on the 21st / 17th) |
| Sprite pixels per line | 320 | 256 | PUBLISHED: plutiedev |
| SAT entry | 8 bytes; Y/X in 0–511 (visible X 128 to 447 in H40) | | PUBLISHED: railgun |
| SAT cache | Y, size and link come from the VDP's internal cache, refreshed only on writes to the SAT region | | PUBLISHED: Kabuto (phase 1 reads the cache) |

## 5. Interrupts (68000)

| Quantity | Cycles | Label / source |
|---|---|---|
| Interrupt acknowledge to first handler instruction (autovector) | 44 | PUBLISHED: *M68000 User's Manual* §8.12, "Interrupt 44(5/3)" (`oracle/docs/reference/M68000UM.pdf`) |
| `rte` | 20 | PUBLISHED: same manual, §8 |
| Latency jitter | up to the longest instruction in flight (`divs` ≤ 158) | ESTIMATED from the manual's timing tables; interrupts are taken only at instruction boundaries |
| HInt position | in HBlank; GPGX starts HBlank at 228 mclk (H40) / 280 (H32) into its line | PUBLISHED: GPGX `vdp_ctrl.c:61-64` |

## 6. Memory map and sizes

| Quantity | Value | Label / source |
|---|---|---|
| Cartridge ROM window | `$000000-$3FFFFF`, 4 MB without a mapper | PUBLISHED: [plutiedev, memory map](https://plutiedev.com/memory-map) |
| 68000 work RAM | 64 KB, mirrored `$E00000-$FFFFFF` (used at `$FF0000`) | PUBLISHED: plutiedev memory map; GPGX `genesis.c:50` |
| Z80 RAM | 8 KB at Z80 `$0000`, mirrored to `$3FFF` | PUBLISHED: GPGX `memz80.c:119`; [plutiedev, using the Z80](https://plutiedev.com/using-the-z80) |
| YM2612 (Z80 side) | `$4000-$5FFF` | PUBLISHED: GPGX `memz80.c:125` |
| Z80 bank window | 32 KB at Z80 `$8000`, onto any 32 KB of the 68000 space, set by 9 serial writes to `$6000` | PUBLISHED: GPGX `memz80.c:143-149, 177-183` |

## 7. Z80 and the bus

| Quantity | Value | Label / source |
|---|---|---|
| Z80 read through the bank window: Z80 delay | ≈ 3.3 Z80 cycles average (MD1); a little under 3 on MD3 | PUBLISHED: Kabuto. GPGX `memz80.c:111-112` and BlastEm `genesis.c:1782-1783` charge 3 |
| same: 68000 delay | ≈ 11 68000 cycles average | PUBLISHED: Kabuto. BlastEm charges 8 and calls it an estimate (`genesis.c:1784-1787`) |
| Z80 access during a 68k→VDP DMA | the Z80 waits until the DMA ends | PUBLISHED: GPGX `memz80.c:95-109`; BlastEm `genesis.c:1779-1780` (`bus_busy`); Ares acquires the 68000 bus for DMA (`ares/md/vdp/dma.cpp:2-10`) |
| 68000 access to the Z80 area | +1 68000 cycle | PUBLISHED: GPGX `mem68k.c:143-144` |
| Bus request | write `$100` to `$A11100`, poll until granted; "it may take a bit until the bus is free". Some early boards corrupt DMA if the Z80 runs during it | PUBLISHED: plutiedev, using the Z80 |

## 8. Sound chips

| Quantity | Value | Label / source |
|---|---|---|
| YM2612 output rate | clock / 144 = **53,267 Hz** NTSC, 52,781 Hz PAL | PUBLISHED: BlastEm `ym2612.c:24` (`OP_UPDATE_PERIOD 144`); ESTIMATED arithmetic |
| YM2612 channels | 6 FM; channel 6 can be an 8-bit DAC (`$2A`, enabled by `$2B`) | PUBLISHED: plutiedev / common reference |
| Timer A / B | 10-bit / 8-bit; B counts at 1/16 of A's rate | PUBLISHED: BlastEm `ym2612.c:91-92` (`TIMER_A_MAX 1023`, `TIMER_B_MAX 255`), `:262` (`sub_timer_b += 0x10`) |
| BUSY flag | 32 internal cycles (internal = clock / 6), so 192 68000 cycles or about 90 Z80 cycles | PUBLISHED: BlastEm `ym2612.c:23, 144-145`; Sauraen (die analysis, [SpritesMind p=27161](https://gendev.spritesmind.net/forum/viewtopic.php?p=27161)) |
| Real minimum write spacing | "just over 24 internal cycles (about 70 Z80 cycles)" for channel and operator writes. A second write while one is pending **loses the first** | PUBLISHED: Sauraen, same thread. Stef measured ~25 Z80 cycles for some registers and ~70–80 for others. **The sources do not fully agree.** The Sega wait table (17 68000 cycles after an address write, 83 after a data write) is the conservative manual figure |
| Practical DAC ceiling | about 26 kHz before writes go missing | PUBLISHED (forum-grade): TmEE, same thread |
| PSG | SN76489-compatible, 3 square + 1 noise; clock = Z80 clock, output at clock / 16 | PUBLISHED: BlastEm `genesis.c:32` |

## 9. Correcting Oracle's numbers

Oracle is the pinned measuring emulator, but it is not a cycle-exact console. The [[Oracle fitness]] audit
(`oracle/docs/audits/Oracle fitness.md`, findings 3, 4 and 5, decision 2) found what it leaves out and how far
that moves a figure. This section is the rule every audit applies to an Oracle figure before it calls
something "fits". The rule is also code: `tools/leg_correction.py` holds the constants and `classify()`, and
`tools/test_leg_correction.py::test_constants_match_hardware_limits_doc` reads the table and the rule below,
so the doc and the code cannot drift. Change one and the test fails until the other matches.

**The rule** (values from Oracle fitness):

1. Judge VBlank work by the **last DMA's end**, not by `rte`.
2. The blank-rate window is **37 lines**, not 38; on hardware it ends at about line 261 + 0, give or take a line. Use the threshold "no DMA ends after line 260 + 0". That leaves one line of safety and needs no disputed GPL-only constant (fitness decision 2).
3. Oracle omits the 68000 refresh (2 cycles in 128, 1.56%) and Z80 bank stalls (up to about 2.6% with sound). Correct by **2-4%** of the cycles elapsed since VInt: the low end for a silent leg, the high end with sound.
4. Frame budgets on Oracle are about **2% optimistic** (band 1.5-2.5%, ESTIMATED from one BlastEm lag frame).
5. **A "fits" call with a corrected margin under 3% of its budget (about 3.8k cycles of a frame) is not a verdict on Oracle alone.** It needs BlastEm agreement on lag and path for the same tick-keyed inputs, or it is reported NEEDS-WITNESS.
6. A DMA past the blank is **not measurable** on Oracle (flat cost, finding 4). Report the flag, not a cost.

**What the code subtracts (fix round 1).** The "2-4%" in rule 3 is a rounding. The code takes off
**1.5625%** of elapsed (2/128, the refresh alone) for a silent leg, which is below the stated 2% low end, and
**4.1625%** (1.5625% + 2.6%) with sound, which is above the stated 4% high end. Changing the rule's wording to
match is the owner's call; until then the rule is quoted as the audit wrote it and the code follows the constants.

**Rule 4 is not a second correction.** The "about 2% optimistic" of rule 4 is the empirical gap between Oracle
and BlastEm over whole frames (one BlastEm lag frame where Oracle had 1.46% to spare; Oracle fitness finding 5,
whose likely cause is the same refresh rule 3 corrects for). It is evidence that rule 3's correction is the
right size, not an amount to add to it. Apply rule 3 once (`corrected_margin`) and never subtract rule 4 on top.

| Constant | Value | Meaning | Label / source |
|---|---|---|---|
| `FRAME_CYCLES` | 128,006 | 68000 cycles per NTSC frame | ESTIMATED: 262 × 3,420 / 7 (section 2) |
| `MCLK_PER_LINE` | 3,420 | master clocks per line | PUBLISHED: section 2 |
| `LINES_PER_FRAME` | 262 | NTSC lines per frame | PUBLISHED: section 2 |
| `BLANK_DMA_LINES` | 37 | lines at the blank DMA rate, NTSC V28 | ESTIMATED: section 2, Vertical blank |
| `DMA_END_LIMIT_LINE` | 260 | no VBlank DMA may end after this line + 0 | rule 2; fitness decision 2 |
| `REFRESH_FRACTION` | 2/128 | 68000 cycles lost to DRAM refresh | PUBLISHED: section 2 (Kabuto) |
| `Z80_STALL_MAX_FRACTION` | 2.6% | upper bound of Z80 bank stalls with sound | ESTIMATED: Oracle fitness finding 5 |
| `WITNESS_MARGIN_FRACTION` | 3% | a corrected margin under this share of its budget needs a witness | rule 5 |

**How to apply it.** `corrected_margin(margin, elapsed, sound)` takes off `floor(elapsed × 2/128)` for the
refresh and, when sound plays, `ceil(elapsed × 2.6%)` for the Z80 (an upper bound, so rounded up). `elapsed`
is the cycles since VInt that the margin was measured over. The code takes these exact terms, never rule 3's rounded band (see "What the code subtracts" above). `classify(margin, budget, elapsed, sound, witness)` answers:

- **OVER**: the corrected margin is negative. A witness cannot rescue it, because Oracle errs optimistic.
- **FITS**: the corrected margin is at least 3% of the budget, or under it with a BlastEm witness that agrees.
- **NEEDS-WITNESS**: under 3% and no witness was run. This is a result, not a failure: report it as such.
- **WITNESS-DISAGREES**: under 3% and BlastEm differs on lag or path, or did not cover the whole leg.

**The witness.** `tools/blastem_witness.py --rom R --lst L --result <leg_run json>` replays that result's
`input_log` open-loop on BlastEm 0.6.2, keyed to `Logic_Tick` at the `Input_Tick` seam, over the GDB-RSP stub
(`oracle/tools/blastem-differential/rsp.py`; BlastEm's source is never opened). It writes
`<result>.blastem.json` with `path_agree_ticks`, `first_divergent_tick`, both lag counts and the ticks whose
lag differs. **BlastEm is a second model, not hardware.** Agreement means two independent models give the
same answer; it does not prove the cart fits on a console. The stub has no cycle counter, so the witness is
lag-level and path-level only: it can confirm or refuse a close call, but it cannot supply a cycle figure.
PAL (`blastem -r E`) is not built.

## Source notes

- **Kabuto's hardware notes** transcribe Nemesis's logic-analyser measurements of slot positions. The source for the refresh, Z80 delay and line structure figures is the [plutiedev mirror](https://plutiedev.com/mirror/kabuto-hardware-notes).
- **railgun** ([md.railgun.works VDP](https://md.railgun.works/index.php?title=VDP)) gives the DMA tables but not the lines it counts. Its 7,524 B NTSC figure equals 38 lines × 198 B, which is neither GPGX's rule nor the Sega table's.
- Emulator source read for this page (2026-11-16): GPGX `core/{vdp_ctrl.c, memz80.c, mem68k.c, genesis.c, system.h}` from `ekeeke/Genesis-Plus-GX` master; BlastEm `{vdp.c, vdp.h, genesis.c, ym2612.c}` from `retrodev.com/repos/blastem` tip; Ares `ares/md/vdp/{dma.cpp, main.cpp}` from master. Line numbers refer to those downloads.
- Sega Retro's specification page refused the fetch (bot protection). Clocks are taken from GPGX instead.
