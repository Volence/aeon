# Leg survey summary

ran 48 of 48  |  OK: 18  STUCK: 12  DID NOT COVER: 3  DID NOT RUN: 0  FAILED: 15

## Provenance (one aeon + oracle tuple for the whole survey; every cell must match)

- survey: aeon.commit=d11a6661d69c4a297802c2102ce942f258ee66b9, aeon.dirty=False, oracle.server_build_id=dd09acb96ad5d0c2b1ee603f919942dd819f80c6+profile=release+target=x86_64-unknown-linux-gnu+features=, oracle.source=vcs, oracle.dirty=False, oracle.sha256=162a0e976364aecaab5e14c969a03b26bdda62cd943308e56a512b36acec1ae8
- rom crc32 idle/release: 193507d9
- rom crc32 idle/debug: ce326232
- rom crc32 run/release: 193507d9
- rom crc32 run/debug: ce326232
- rom crc32 topspeed/release: 193507d9
- rom crc32 topspeed/debug: ce326232
- rom crc32 diagfall/release: 193507d9
- rom crc32 diagfall/debug: ce326232
- rom crc32 spindash/release: 193507d9
- rom crc32 spindash/debug: ce326232
- rom crc32 objheavy/release: a63f6716
- rom crc32 objheavy/debug: a7c8bc33
- rom crc32 sidekick/release: 0901a38e
- rom crc32 sidekick/debug: 9350730d
- rom crc32 stream/release: 3be528b0
- rom crc32 stream/debug: 0e086143
- rom crc32 stream_companion/release: 4326287f
- rom crc32 stream_companion/debug: 74dbaf25

| leg | shape | cells (p0 p1 p2) | lag frames min-max, MEASURED (Oracle) | worst last-DMA end, MEASURED (Oracle) | rule-4 verdict, ESTIMATED: classify, sound_playing=True (upper-bound Z80 stall), no witness |
|---|---|---|---|---|---|
| idle | release | OK OK OK | 0-0 | line 242 + 1261 mclk | FITS |
| idle | debug | OK OK OK | 0-0 | line 247 + 2359 mclk | FITS |
| run | release | OK OK OK | 1-1 | line 254 + 390 mclk | FITS |
| run | debug | FAILED FAILED FAILED | 15-18 | line 261 + 1729 mclk | OVER |
| topspeed | release | OK OK OK | 1-1 | line 254 + 390 mclk | FITS |
| topspeed | debug | FAILED FAILED FAILED | 15-18 | line 261 + 1729 mclk | OVER |
| diagfall | release | STUCK STUCK STUCK | 0-0 | line 247 + 490 mclk | FITS |
| diagfall | debug | FAILED FAILED FAILED | 11-18 | line 260 + 2031 mclk | OVER |
| spindash | release | STUCK STUCK STUCK | 0-0 | line 247 + 532 mclk | FITS |
| spindash | debug | DID NOT COVER DID NOT COVER DID NOT COVER | 11-18 | line 260 + 2045 mclk | OVER |
| objheavy | release | OK OK OK | 59-60 | line 254 + 3089 mclk | FITS |
| objheavy | debug | FAILED FAILED FAILED | 208-212 | line 260 + 2800 mclk | OVER |
| sidekick | release | OK OK OK | 5-5 | line 254 + 425 mclk | FITS |
| sidekick | debug | FAILED FAILED FAILED | 34-40 | line 264 + 1385 mclk | OVER |
| stream | release | STUCK STUCK STUCK | 10-12 | line 247 + 3268 mclk | FITS |
| stream | debug | STUCK STUCK STUCK | 19-22 | line 248 + 1587 mclk | FITS |

## Stream leg: streaming counts (MEASURED, Oracle: breakpoint entries and RAM reads over the drive window)

`stream` is clip `s2_woven` (one of the 48). The companion is clip `s2_ehz_cpz`, recorded **outside the 48**: its cells are not counted above and its FINISHED never makes the stream cell OK.

| run | shape | p | cell | drive | decode calls | landings | evictions | Direct_Map end | lag frames | worst last-DMA end |
|---|---|---|---|---|---|---|---|---|---|---|
| stream (s2_woven) | release | 0 | STUCK | STUCK | 3 | 3 | 3 | 0 | 10 | line 247 + 3268 |
| stream (s2_woven) | release | 1 | STUCK | STUCK | 3 | 3 | 3 | 0 | 10 | line 247 + 3226 |
| stream (s2_woven) | release | 2 | STUCK | STUCK | 3 | 3 | 3 | 0 | 12 | line 247 + 3243 |
| stream (s2_woven) | debug | 0 | STUCK | STUCK | 3 | 3 | 3 | 0 | 22 | line 248 + 1507 |
| stream (s2_woven) | debug | 1 | STUCK | STUCK | 3 | 3 | 3 | 0 | 22 | line 248 + 1535 |
| stream (s2_woven) | debug | 2 | STUCK | STUCK | 3 | 3 | 3 | 0 | 19 | line 248 + 1587 |
| companion (s2_ehz_cpz), outside the 48 | release | 0 | DID NOT COVER | FINISHED | 0 | 0 | 0 | 1 | 3 | line 250 + 1222 |
| companion (s2_ehz_cpz), outside the 48 | release | 1 | DID NOT COVER | FINISHED | 0 | 0 | 0 | 1 | 3 | line 250 + 1194 |
| companion (s2_ehz_cpz), outside the 48 | release | 2 | DID NOT COVER | FINISHED | 0 | 0 | 0 | 1 | 3 | line 250 + 1218 |
| companion (s2_ehz_cpz), outside the 48 | debug | 0 | DID NOT COVER | FINISHED | 0 | 0 | 0 | 1 | 9 | line 250 + 3111 |
| companion (s2_ehz_cpz), outside the 48 | debug | 1 | DID NOT COVER | FINISHED | 0 | 0 | 0 | 1 | 7 | line 250 + 3135 |
| companion (s2_ehz_cpz), outside the 48 | debug | 2 | DID NOT COVER | FINISHED | 0 | 0 | 0 | 1 | 9 | line 250 + 3128 |

- streaming sustained to the end of an act: **DID NOT COVER** (NO single run both evicts and finishes: evicting runs: stream (s2_woven); finishing runs: companion (s2_ehz_cpz))
- companion cells (outside the 48): OK: 0  STUCK: 0  DID NOT COVER: 6  DID NOT RUN: 0  FAILED: 0

## Cells not OK

- run/debug/p0: **FAILED** DMA overrun: 1 DMA(s) end past line 260 + 0
- run/debug/p1: **FAILED** DMA overrun: 1 DMA(s) end past line 260 + 0
- run/debug/p2: **FAILED** DMA overrun: 1 DMA(s) end past line 260 + 0
- topspeed/debug/p0: **FAILED** DMA overrun: 1 DMA(s) end past line 260 + 0
- topspeed/debug/p1: **FAILED** DMA overrun: 1 DMA(s) end past line 260 + 0
- topspeed/debug/p2: **FAILED** DMA overrun: 1 DMA(s) end past line 260 + 0
- diagfall/release/p0: **STUCK** progress: max px 1143 has not grown by 32 px in 300 ticks; at (px, py) = (1143, 301), cam (983, 157)
- diagfall/release/p1: **STUCK** progress: max px 1143 has not grown by 32 px in 300 ticks; at (px, py) = (1143, 301), cam (983, 157)
- diagfall/release/p2: **STUCK** progress: max px 1143 has not grown by 32 px in 300 ticks; at (px, py) = (1143, 301), cam (983, 157)
- diagfall/debug/p0: **FAILED** DMA overrun: 1 DMA(s) end past line 260 + 0
- diagfall/debug/p1: **FAILED** DMA overrun: 1 DMA(s) end past line 260 + 0
- diagfall/debug/p2: **FAILED** DMA overrun: 1 DMA(s) end past line 260 + 0
- spindash/release/p0: **STUCK** progress: max px 1143 has not grown by 32 px in 300 ticks; at (px, py) = (1143, 301), cam (983, 157)
- spindash/release/p1: **STUCK** progress: max px 1143 has not grown by 32 px in 300 ticks; at (px, py) = (1143, 301), cam (983, 157)
- spindash/release/p2: **STUCK** progress: max px 1143 has not grown by 32 px in 300 ticks; at (px, py) = (1143, 301), cam (983, 157)
- spindash/debug/p0: **DID NOT COVER** status FINISHED, coverage met=False (got={'status': 'FINISHED', 'releases': 0} need={'status': 'FINISHED', 'releases': 1})
- spindash/debug/p1: **DID NOT COVER** status FINISHED, coverage met=False (got={'status': 'FINISHED', 'releases': 0} need={'status': 'FINISHED', 'releases': 1})
- spindash/debug/p2: **DID NOT COVER** status FINISHED, coverage met=False (got={'status': 'FINISHED', 'releases': 0} need={'status': 'FINISHED', 'releases': 1})
- objheavy/debug/p0: **FAILED** DMA overrun: 1 DMA(s) end past line 260 + 0
- objheavy/debug/p1: **FAILED** DMA overrun: 1 DMA(s) end past line 260 + 0
- objheavy/debug/p2: **FAILED** DMA overrun: 1 DMA(s) end past line 260 + 0
- sidekick/debug/p0: **FAILED** DMA overrun: 2 DMA(s) end past line 260 + 0
- sidekick/debug/p1: **FAILED** DMA overrun: 2 DMA(s) end past line 260 + 0
- sidekick/debug/p2: **FAILED** DMA overrun: 1 DMA(s) end past line 260 + 0
- stream/release/p0: **STUCK** progress: max px 2551 has not grown by 32 px in 300 ticks; at (px, py) = (2550, 2790), cam (2391, 2705); streaming (MEASURED, Oracle): decode calls 3, landings 3, evictions 3 (PickVictim 3, no-victim 0), Direct_Map end 0, streamed=True
- stream/release/p1: **STUCK** progress: max px 2551 has not grown by 32 px in 300 ticks; at (px, py) = (2550, 2790), cam (2391, 2705); streaming (MEASURED, Oracle): decode calls 3, landings 3, evictions 3 (PickVictim 3, no-victim 0), Direct_Map end 0, streamed=True
- stream/release/p2: **STUCK** progress: max px 2551 has not grown by 32 px in 300 ticks; at (px, py) = (2550, 2790), cam (2391, 2705); streaming (MEASURED, Oracle): decode calls 3, landings 3, evictions 3 (PickVictim 3, no-victim 0), Direct_Map end 0, streamed=True
- stream/debug/p0: **STUCK** progress: max px 2551 has not grown by 32 px in 300 ticks; at (px, py) = (2550, 2790), cam (2391, 2705); streaming (MEASURED, Oracle): decode calls 3, landings 3, evictions 3 (PickVictim 3, no-victim 0), Direct_Map end 0, streamed=True
- stream/debug/p1: **STUCK** progress: max px 2551 has not grown by 32 px in 300 ticks; at (px, py) = (2550, 2790), cam (2391, 2705); streaming (MEASURED, Oracle): decode calls 3, landings 3, evictions 3 (PickVictim 3, no-victim 0), Direct_Map end 0, streamed=True
- stream/debug/p2: **STUCK** progress: max px 2551 has not grown by 32 px in 300 ticks; at (px, py) = (2550, 2790), cam (2391, 2705); streaming (MEASURED, Oracle): decode calls 3, landings 3, evictions 3 (PickVictim 3, no-victim 0), Direct_Map end 0, streamed=True

## Companion cells (outside the 48)

- stream_companion/release/p0: **DID NOT COVER** status FINISHED, coverage not met (status == FINISHED and decode calls (ZX0R_Decompress entries) >= 1 and evictions (delta Page_Evict_Gen over the drive window) >= 1; the counts half alone is got.streamed); streaming (MEASURED, Oracle): decode calls 0, landings 0, evictions 0 (PickVictim 0, no-victim 0), Direct_Map end 1, streamed=False
- stream_companion/release/p1: **DID NOT COVER** status FINISHED, coverage not met (status == FINISHED and decode calls (ZX0R_Decompress entries) >= 1 and evictions (delta Page_Evict_Gen over the drive window) >= 1; the counts half alone is got.streamed); streaming (MEASURED, Oracle): decode calls 0, landings 0, evictions 0 (PickVictim 0, no-victim 0), Direct_Map end 1, streamed=False
- stream_companion/release/p2: **DID NOT COVER** status FINISHED, coverage not met (status == FINISHED and decode calls (ZX0R_Decompress entries) >= 1 and evictions (delta Page_Evict_Gen over the drive window) >= 1; the counts half alone is got.streamed); streaming (MEASURED, Oracle): decode calls 0, landings 0, evictions 0 (PickVictim 0, no-victim 0), Direct_Map end 1, streamed=False
- stream_companion/debug/p0: **DID NOT COVER** status FINISHED, coverage not met (status == FINISHED and decode calls (ZX0R_Decompress entries) >= 1 and evictions (delta Page_Evict_Gen over the drive window) >= 1; the counts half alone is got.streamed); streaming (MEASURED, Oracle): decode calls 0, landings 0, evictions 0 (PickVictim 0, no-victim 0), Direct_Map end 1, streamed=False
- stream_companion/debug/p1: **DID NOT COVER** status FINISHED, coverage not met (status == FINISHED and decode calls (ZX0R_Decompress entries) >= 1 and evictions (delta Page_Evict_Gen over the drive window) >= 1; the counts half alone is got.streamed); streaming (MEASURED, Oracle): decode calls 0, landings 0, evictions 0 (PickVictim 0, no-victim 0), Direct_Map end 1, streamed=False
- stream_companion/debug/p2: **DID NOT COVER** status FINISHED, coverage not met (status == FINISHED and decode calls (ZX0R_Decompress entries) >= 1 and evictions (delta Page_Evict_Gen over the drive window) >= 1; the counts half alone is got.streamed); streaming (MEASURED, Oracle): decode calls 0, landings 0, evictions 0 (PickVictim 0, no-victim 0), Direct_Map end 1, streamed=False

ran 48 of 48
