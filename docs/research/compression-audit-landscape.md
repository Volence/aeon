# Compression Audit — External Landscape (2026-06-11)

Companion to `lz-compression-survey.md` (2026-04-24). This covers what the outside world has shipped/measured
since that survey was written, plus corrections to it. Internal S4LZ code dissection is the other audit track.

## (a) Format Landscape: Ratio on Tile Art vs 68000 Decompression Speed

| Format | Typical ratio (tile art) | 68000 decomp speed | Source |
|---|---|---|---|
| Nemesis | strong on sprite art | ~50-100 KB/s ("a few tiles per frame") | [s3unlocked](https://s3unlocked.blogspot.com/2017/06/mega-drive-compression-formats.html) |
| Kosinski | ~0.45-0.55 | ~120-200 KB/s (bit-stream) | s3unlocked; survey doc |
| Kosinski+ | same as Kosinski ("no cost to ratio") | faster than Kosinski (~190-310 KB/s est.) | [SegaRetro via clownlzss](https://github.com/Clownacy/clownlzss) |
| Comper (vladikcomper/flamewing) | poor — "significant cost to compression ratio" | word-aligned speed king of the *classic* formats; **no published cycles/byte found** (mdcomp asm has no cycle annotations) | [clownlzss README](https://github.com/Clownacy/clownlzss), [mdcomp Comper.asm](https://github.com/flamewing/mdcomp/blob/master/src/asm/Comper.asm) |
| **LZ4W (SGDK)** | **0.532** on Stef's tile file (6,746/12,672) — within **1.9% of LZ4HC** (6,622) on that same file | spec: **550-950 KB/s**; Stef's forum measurement: 600-900, mean ~720 KB/s; decompressor = **2,404 bytes** | [lz4w.txt](https://github.com/Stephane-D/SGDK/blob/master/bin/lz4w.txt), [SpritesMind t=2479](https://gendev.spritesmind.net/forum/viewtopic.php?t=2479) |
| LZ4 (std), Arnaud Carré `lz4_fastest` | LZ4HC ratios (~0.52 on tiles) | fastest known 68k LZ4: 3,722-byte unrolled decoder, 2.36× his 72-byte version, 6.81× ARJ | [lz4-68k](https://github.com/arnaud-carre/lz4-68k) |
| LZSA1 | 57.08% on standard corpora (between LZ4HC 60.59% and ZX7 53.30%) | 90% of LZ4 speed on 8-bit; Jaguar 68k port: "slightly better ratio than LZ4, **6% slower**" | [lzsa](https://github.com/emmanuel-marty/lzsa), [AtariAge Jaguar thread](https://forums.atariage.com/topic/342048-lzsa-format-1-depacker/) |
| SLZ (Sik) | unstated; 4KB window, byte-aligned bit-flag tokens | "not time critical — load-time only" per author | [plutiedev](https://plutiedev.com/format-slz) |
| ZX0 / salvador | Exomizer-class (best pure-LZ ratios) | bit-granular Elias-gamma; two 68k decompressors exist (Marty 88-byte; chrisly42 speed fork) — **no published KB/s**, clearly Kosinski-class or slower | [unzx0_68000](https://github.com/emmanuel-marty/unzx0_68000), [chrisly42 fork](https://git.platon42.de/chrisly42/unzx0_68000), [salvador](https://github.com/emmanuel-marty/salvador) |
| aPLib 68k port | strong (near-PackFire on small files) | 182-byte decompressor, bit-stream, "fast" but unquantified | [SpritesMind t=703](https://gendev.spritesmind.net/forum/viewtopic.php?t=703) |
| UPX/NRV2B (custom 60-byte 68k depacker) | exe-packer class | ~**300 KB/s** reported on ST | [Atari depack benchmark](https://www.atari-forum.com/viewtopic.php?t=31438) |
| Shrinkler (context-model ceiling) | best ratio of anything 68k-practical | **~11.5 KB/s** (265,660 B in 23 s, 7 MHz) — 2× PackFire-large | [EAB fastest-depacker](https://eab.abime.net/showthread.php?t=97734) |

Theoretical ceiling note: on Stef's actual Genesis tile data, PC-side **LZ4HC left only ~2% over LZ4W**.
The big LZ4W losses were text (21,400 vs 16,088) and pathologically redundant tiles (48,202 vs 24,613 — match
*length* caps, not window). For 4bpp tile art the gap between a well-windowed word LZ and zlib-class is small;
real ceiling gains come from modeling (Shrinkler/upkr/Nemesis-style), paid at 10-100× slower decode.

## (b) LZ4W Token Encoding vs S4LZ — the Pad Byte Question

LZ4W token = one 16-bit word `LLLL MMMM OOOOOOOO`: 4-bit literal words, 4-bit match-size-minus-1, 8-bit
offset-minus-1 (words). **LZ4W does not waste a pad byte — the byte that S4LZ spends on PAD is LZ4W's short-match
offset.** Long matches (MMMM=0, O≠0): O becomes length (up to 257 words), and a *separate* word `X OOOOOOO OOOOOOOO`
carries a 15-bit word offset = **64KB window**, with the X bit allowing the match source to be the *compressed
stream in ROM* (a ratio trick S4LZ lacks). End marker is also word-shaped. Per-token cost:

| Case | LZ4W | S4LZ (current, with PAD) |
|---|---|---|
| literals only | 2 B token | 2 B (token+pad) |
| short match (≤512 B back) | 2 B token (offset inside) | 4 B (token+pad+16-bit offset) |
| far match | 4 B (token + offset word) | 4 B |
| min match | 2 words | 2 words |

So S4LZ is never cheaper per token than LZ4W and is 2 bytes worse on every near match — and near matches dominate
tile art (LZ4W's 1.9%-off-LZ4HC tile result is evidence the 512-byte short window covers most matches). The PAD
byte also breaks the survey's §4.7 breakeven math: standalone match overhead is now 4 bytes, so a 2-word (4-byte)
match saves **zero** — minimum *profitable* standalone match is 3 words. S4LZ's remaining differentiators are
tile-delta XOR (format-agnostic — could front LZ4W equally) and 64KB offsets on *all* matches (worth little if
short offsets dominate).

## (c) What Optimal Parsing Typically Gains

Clownacy (clownlzss, graph shortest-path): a perfect Kosinski compressor saves "a dozen bytes or so for small
files, a few hundred bytes for larger ones" over standard greedy compressors — i.e. **~0.5-2%**, and clownlzss
output is only "on-par with mdcomp" (Flamewing's optimal suite). Optimal parsing is table stakes (we have it),
not a ratio lever: it cannot offset a 2-byte-per-match encoding handicap.
Sources: [clownlzss blog](https://clownacy.wordpress.com/2021/10/14/clownlzss-a-perfect-lzss-compressor/),
[clownlzss](https://github.com/Clownacy/clownlzss) (formats: Kosinski, Kosinski+, Saxman, Faxman, Chameleon,
Rocket, Rage, Comper, GBA-BIOS), [mdcomp](https://github.com/flamewing/mdcomp).

## (d) Stale/Wrong Items in `lz-compression-survey.md`

1. **"LZ4W window = 512 bytes, severely limiting" — wrong.** Only short matches are 512 B; long matches have
   15-bit word offsets (64KB) plus the ROM-source X bit. The survey's claimed S4LZ window advantage largely
   doesn't exist.
2. **"LZ4W minimum match: 1 word" — wrong.** Spec: MMMM=1 ⇒ 2 words; minimum match is 2 words, same as S4LZ.
3. **"LZ4W decompressor ~4KB" — stale.** Measured 2,404 bytes (SpritesMind thread).
4. **"Worse than LZ4HC on larger files due to tiny window" — misattributed.** The losses are from match-length
   caps and text data; on tile art LZ4W ≈ LZ4HC (−1.9%).
5. **Comper "800-1200 KB/s" is an unsourced internal estimate** — no external measurement found anywhere;
   treat as unverified.
6. **The survey's §6 format spec has no PAD byte.** The shipped format does. All of §3.3/§4.7's cycle and
   breakeven analysis describes a format we are not shipping — the survey must be re-run against the real
   2-byte token cost.
7. Tile-delta XOR prior art: nothing new found beyond MEGAPACK
   ([repo](https://github.com/lab313ru/megapack-megadrive), color-adjacency modeling, ~30% over plain LZ) and
   the NES/rage1 anecdotes already cited. No independent measurement of XOR-delta on 4bpp planar art exists —
   our own corpus numbers are the only evidence that matters.

## (e) Threats to S4LZ's Justification

1. **LZ4W likely matches or beats S4LZ's ratio as currently encoded.** Same alignment, same min match, zero pad
   waste, 2-byte near matches, 64KB far matches, ROM-source matches — and it's battle-tested at 550-950 KB/s.
   The honest test: run SGDK's `lz4w` over our real tile corpus (with and without our XOR-delta pre-pass) vs the
   S4LZ compressor. If S4LZ doesn't win by a clear margin, the custom format is a maintenance liability.
2. **Tile-delta XOR is not an S4LZ feature.** It's a preprocessing pass any format can use; it cannot justify
   the format choice, only the pipeline.
3. **The PAD byte.** Either repurpose it (LZ4W-style short offset, or extension byte slot) or accept ~1 byte/token
   of pure padding; on match-dense tile art that can be several % of output — more than optimal parsing earns back.
4. **Optimal parsing buys ~0.5-2%** — it is not a moat; clownlzss/mdcomp give every classic format the same.
5. **ROM pressure is low** (~2.7MB free): if that holds, raw+DMA (Batman model) beats any decompressor on speed
   for hot data, and ratio differences of 5% are immaterial — speed and code simplicity should dominate the call.
6. **If ROM pressure ever rises**, ZX0/salvador or aPLib (tiny decompressors, best pure-LZ ratios) are the
   correct cold-data answer, not a stronger S4LZ — accept slow decode for rarely-loaded assets.
7. Comper/LZSA1 are not threats: Comper's ratio is poor, LZSA1 is byte-aligned little-endian (wrong fit for 68k
   word copies, only ~LZ4-class speed).
