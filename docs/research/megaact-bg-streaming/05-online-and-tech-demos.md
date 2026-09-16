# Online sources, homebrew and tech demos: DMA bounds and streaming techniques

> **Research slice for MEGAACT-BG-STREAMING (2026-09-16).** This is the research agent's final report,
> extracted programmatically from its transcript and committed VERBATIM, never retyped: a report
> whose value is its `file:line` citations cannot be summarised without becoming the
> summary-of-a-summary this project was bitten by twice today. It is a LEAD for the design, not a
> finding the design may assume: every MEASURED claim is re-checkable at its citation.

---

I wrote no files outside the scratchpad and changed nothing in any repo. After your correction I read three aeon files (not changed): `engine/system/constants.emp`, `engine/system/boot.emp` and `engine/vdp.emp`, to see where your 6144 B and 11648 B figures come from.

## 1. Verdict

DMA bandwidth is not what stops a seamless zone swap. Even at aeon's own 4096 B/frame, a full Sonic 2 zone (604-965 tiles) moves in 5-8 frames; at the published raw NTSC limit it is 3-4 frames. What actually limits it is how fast the CPU can decompress, and how many tiles two zones need in VRAM at the same moment. The one shipped precedent shows this. Sonic 3 & Knuckles' Icecap Zone does its act change inside a corridor, with no screen lock, and "if you're going fast enough, the tunnel is unfortunately not long enough to cover up the load time, and you can catch the act 2 background while it's still decompressing". The slow part there was Kosinski decompression, not DMA.

So your corridor hypothesis has real precedent, and that same precedent shows how it fails. The corridor has to be as long as top speed × (decompression frames + upload frames). The rest of the scene has no hidden way to beat the per-line hardware rate. The tricks available are: more blanked lines (letterbox, or PAL), less CPU per byte (raw tiles DMA'd straight from ROM), and needing fewer tiles in VRAM at once (a shared primary set, or covering the background).

**Two errors in aeon's DMA budget comment** (`engine/system/constants.emp:690-706`), both MEASURED against the sources below:
- **The PAL figure counts too few lines.** It uses "PAL 72 blank lines". But `boot.emp:334` writes `$34` to register 1, so bit 3 (V30) is clear and aeon runs 224-line V28 on PAL. V28 PAL has 313 − 224 = **89** non-picture lines (Kabuto), or 87 per Sega's own table. 72 is roughly the **V30** count (Sega: 71). Recomputed with aeon's own model: 89 × 488.6 / 2.7 × 0.89 ≈ **14,330 B**, not 11,648. That is about 84 tiles a frame left unused on PAL.
- **The per-byte cost is a bit pessimistic.** Aeon assumes 2.7 cycles/byte. Kabuto measures slow (64k VRAM) DMA at `words*4.7-6` cycles, about 2.35/byte, and Mask of Destiny says "Every ~2.3 68K cycles, you lose one byte". Kabuto also measures the 68k at about 480 cycles/line, not 488.6. Those numbers give 480 / 2.35 ≈ 204 B/line, which matches every hardware source. Aeon's raw NTSC 6876 B is about 11% under 38 × 204 = 7752 B. This one is a disagreement to check, not a proven bug: aeon says its figure is from its own emulator's cycle model, "hardware-verified".

## 2. Hardware bounds (H40)

| Quantity | Figure | Source | Label |
|---|---|---|---|
| 68k→VRAM bytes/line, blanking or display off | **205** | Sega Technical Overview v1.00 DMA capacity table ([archive.org](https://archive.org/stream/Genesis_Technical_Overview_v1.00_1991_Sega_US/Genesis_Technical_Overview_v1.00_1991_Sega_US_djvu.txt)) | MEASURED |
| same | **204**: "there is an extra refresh cycle when the display is off (or you're in VBlank)", from logic-analyser captures | Mask of Destiny, [SpritesMind t=1968](https://gendev.spritesmind.net/forum/viewtopic.php?t=1968) | MEASURED (his own capture) |
| same | **198** (implied: 7524/38, 17622/89) | [md.railgun.works VDP, DMA Bandwidth](https://md.railgun.works/index.php?title=VDP) | MEASURED table, derivation not stated |
| Bytes/line during active display | **18** (H32: 16) | Sega table; Kabuto's slot map `((A~aaBSbb)*3 AraaBSbb)*5 ~~ s*23 ~ s*11` gives 18 access slots ([plutiedev mirror](https://plutiedev.com/mirror/kabuto-hardware-notes)) | MEASURED |
| Non-picture lines, V28 NTSC / V28 PAL / V30 PAL | **38 / 89 / –** (Kabuto: "11 border, 224 picture, 8 border, 3+3+3 sync, 10 blank … 262 total"; PAL 313) vs **36 / 87 / 71** (Sega table) | both above | MEASURED; **the sources disagree by 2 lines** |
| VBlank total, 60 Hz 320×224 | **7524** VBlank + **4032** active = 11556 | railgun | MEASURED |
| VBlank total, 50 Hz 320×224 | **17622** + 4032 = 21654 | railgun | MEASURED |
| "About 7 KB … about 230 tiles … just 18 bytes each scanline" | 7 KB | [rasterscroll](https://rasterscroll.com/mdgraphics/vdp-inner-workings/) | MEASURED, but secondhand: 230 = 205×36/32, the Sega table |
| Engine caps | `DMA_TRANSFER_CAPACITY_NTSC 7200`, `PAL_LOW 8000`, `PAL_MAX 15000` | [SGDK inc/dma.h](https://raw.githubusercontent.com/Stephane-D/SGDK/master/inc/dma.h) | MEASURED (a chosen cap, not a hardware figure) |
| CRAM/VSRAM rate | one word per slot, so double | Sik, [SpritesMind t=2268](https://gendev.spritesmind.net/forum/viewtopic.php?t=2268); railgun | MEASURED |
| VRAM copy DMA | about half the 68k→VRAM rate (3876 B NTSC VBlank); **the 68k is not frozen** | railgun | MEASURED |
| Measured practical ceiling in a real engine | 8 × 256 words ≈ 4 KB/VBlank before lag; CPU overhead is the cause | KanedaFr, t=1968 | MEASURED (one C engine, 2015) |

**Writing mid-frame (MEASURED):**
- During active display, writes queue in a 4-word FIFO. When it is full, "the 68k is halted until the FIFO clears" (railgun).
- A 68k→VRAM DMA freezes the 68k for the whole transfer (railgun, plutiedev).
- Turning the display off mid-line "will always break something". "Only in-border display disable seems to be useful, at the cost of losing sprites during phase 1 and sprite tiles during phase 3" (Kabuto).
- Register 1 display-bit changes take effect at 16-pixel granularity (Sik, [SpritesMind t=2429](https://gendev.spritesmind.net/forum/viewtopic.php?t=2429)).
- DMA cannot cross a 128 KB source boundary. Length 0 means 65536 ([plutiedev hardware issues](https://plutiedev.com/hardware-issues)).

## 3. Techniques

**Extended blanking / letterbox via HInt**
- Source: gasega68k, t=1968 ("using the h-int on line 192 … disable the display and make the DMA in the hint"); Sega table ("when on-screen display is not made, the TRANSFER quantity is the same as … BLANKING"); Kabuto on the sprite cost.
- Label: MEASURED for the mechanism. The claim that Mickey Mania uses it came from a search snippet I could not verify.
- How it works: turn the display off at the bottom of the frame, so those lines carry DMA at the blanking rate.
- Cost: each blanked line is border colour and adds about 204 B. 16 lines ≈ +3.3 KB/frame (about 100 tiles). Sprites on the line after re-enable may break.
- Aeon: the only per-frame bandwidth multiplier on stock hardware that I found. It suits a cinematic letterbox during a crossing, or a permanent status bar. It will be seen; nothing about it is invisible.

**Sacrifice a gameplay frame**
- Label: INFERRED from the railgun totals.
- How it works: a DMA during active display freezes the 68k, but railgun counts 4032 B available there. One frame could carry about 11.5 KB (≈ 361 tiles) if game logic skips that frame.
- Cost: one dropped frame, which reads as a hitch.
- Aeon: a single hitch at the crossing, not a visible load. Worth weighing against a longer corridor.

**Raw tiles DMA'd straight from ROM (no decompression)**
- Source: Sik on Sonic 3D Blast, [SpritesMind t=2122](http://gendev.spritesmind.net/forum/viewtopic.php?t=2122): streams up to 4096 tiles, "they had to leave all those graphics uncompressed". Stef on the same scheme, [SpritesMind t=3244](https://gendev.spritesmind.net/forum/viewtopic.php?t=3244).
- Label: INFERRED. These are forum claims about a game I did not disassemble.
- Cost: ROM size.
- Aeon: removes the CPU bottleneck that sank Icecap Zone. Aeon's per-page raw-direct form already exists; forcing it for crossing pages is the lever.

**VRAM slot equals screen position** (Sonic 3D Blast)
- Source: Sik, t=2122: "there's no 'VDP index' because that's really just calculated off its position on screen"; 41×29 = 1189 slots, plane A only, and a palette bit given up to address 4096 tiles.
- Label: INFERRED.
- How it works: no allocator and no eviction, because every newly revealed cell is uploaded.
- Aeon: 1189 slots is too many for a background plane. It does show that "tiles addressed by position" can become a streaming design instead of a blocker.

**Primary/secondary tileset split plus covering the background** (Sonic 3 & Knuckles)
- Source: [S3 Unlocked, act transitions part 1](https://s3unlocked.blogspot.com/2017/08/act-transitions-part-1.html), which quotes disassembly.
- Label: MEASURED from the blog's quoted code.
- How it works: only primary-set tiles are visible while the secondary set is swapped. "Covering up the background plane with foreground tiles … frees up act 1's background tiles to be overwritten". The act change waits on `Kos_modules_left`, then loads layout and collision in one frame (both are uncompressed).
- Aeon: this is exactly the co-residency reducer. Design the crossing so the background is hidden and not co-resident.

**Corridor transition** (Icecap Zone)
- Source: [S3 Unlocked part 3](https://s3unlocked.blogspot.com/2017/08/act-transitions-part-3-icecap-zone.html).
- Label: MEASURED (the author's observation plus quoted code).
- How it works: the only Sonic 3 & Knuckles transition with no screen lock. It waits only for chunks and blocks, not tiles, and the art visibly lags at speed.
- Aeon: this is your neutral corridor. Size it as top speed × frames to finish.

**Contiguous shadow pattern area and one DMA; solid tiles as nametable-only**
- Source: [jix, Pushing Polygons on the Mega Drive](https://jix.one/pushing-polygons-on-the-mega-drive/) (Overdrive 2).
- Label: MEASURED.
- How it works: "a compact consecutive memory area containing all patterns saves a lot more cycles". Solid-colour tiles point at 16 shared patterns.
- Aeon: lowers per-transfer overhead (Mask of Destiny: CPU time costs about 1 byte per 2.3 cycles). Solid-colour background tiles cost no upload at all.

**VRAM-to-VRAM copy DMA**
- Source: railgun.
- Label: MEASURED rate; the use for aeon is INFERRED.
- How it works: the VDP moves data internally at about half rate without freezing the 68k.
- Aeon: lets you compact or defragment background slots without CPU or 68k-bus bandwidth. You must not touch the VDP except status, HV counter and PSG during the copy.

**128k "byte-wide DMA"**
- Source: Kabuto.
- Label: MEASURED rates, INFERRED conclusion.
- How it works: the fast rate (2.4 cycles/word), but only the low byte is stored.
- Aeon: no gain for whole tiles: about 2.4 cycles per stored byte vs about 2.35 for the normal path. It only helps partial-byte updates. It is not a way past the naive limit.

**Stage, then flip, in one VBlank**
- Label: INFERRED from the fact that all VBlank writes land before the next active line.
- How it works: upload new tiles into free slots over N frames; switch the nametable rows only once every tile they reference is present. Refcount slots by visible rows, not by layout region: tiles referenced only by off-screen rows of the 64-row plane can be evicted at once.
- Aeon: this may make the corridor shorter than a whole-zone swap would need. Whether it does depends on per-row tile overlap in aeon's data, which I could not measure.

## 4. Projects surveyed

- **SGDK** (MEASURED from [map.h](https://raw.githubusercontent.com/Stephane-D/SGDK/master/inc/map.h) and dma.h): streams the metatile map; the tileset is loaded separately and stays fixed. Stef, the author: "The MAP resource doesn't support 'tile streaming'". A negative.
- **Tanglewood** (MEASURED from source): `GAMELIB/STREAM.ASM` streams map data only. `FRAMEWK/VRAMPOOL.ASM` is a bump allocator cleared per level (`VRAM_ClearPools`), with no free. Levels load whole. A negative.
- **Overdrive 2**: the polygon renderer above. Kabuto says the demo's bottleneck was often "the DMA capacity" ([megabites](https://megabitesblog.wordpress.com/2019/01/16/overdrive-2-a-voyage-to-the-boundaries-of-16-bit-part-1/)). I found no bulk tile-streaming trick in it.
- **Overdrive 1** (Sik, t=2268): a 512-colour screen pushes CRAM through HBlank display-disable, "the limit is 23 before you run into the visible area". This is about colours, not tile throughput.
- **Paprium** ([MiSTer doc](https://github.com/MisterPezz82/Paprium_MegaDrive_MiSTer/blob/paprium-mdplus-port/docs/PAPRIUM.md)): "The MCU decompresses graphics into the workspace". It uses an on-cart coprocessor, so it does not apply to stock hardware. A negative.
- **Xeno Crisis, Demons of Asteborg, Pier Solar, Project MD**: I found no technical documentation of tile handling. Xeno Crisis is single-arena rooms and Demons of Asteborg is SGDK plus Tiled rooms (INFERRED); neither is a precedent.
- **Sonic 3D Blast**: the per-position streaming described above (INFERRED from forum posts).
- **Hidden Palace, Sonic 3 prototypes**: only content-difference notes, nothing on the transition engine.
- **Amiga/demoscene**: tiles are blitted into chip-RAM bitmaps, so there is no tile-slot residency problem. The parallel does not carry over. A negative.
- **nesdev t=17172** turned out to be about the **SNES**. I discarded it.

## 5. What I could NOT determine

- The true V28 NTSC blanking line count (36 vs 38) and bytes/line (198 / 204 / 205). No source reconciles them; only a logic-analyser capture or aeon's own hardware-verified model can.
- Any first-hand writeup of the Sonic 3D Blast engine. Jon Burton's GameHut material is video, which I cannot read.
- The Mickey Mania letterbox claim, and a "fast 8-bit DMA in Overdrive 2" claim. Both appeared only in search-engine summaries.
- `wiki.megadrive.org` did not resolve (DNS failure).
- Search scope: plutiedev (DMA, hardware issues, Kabuto mirror), md.railgun.works VDP, the Sega Technical Overview OCR, rasterscroll, SpritesMind t=1968/2122/2268/2429/3244, SGDK GitHub, the Tanglewood GitHub source, jix.one, megabites, S3 Unlocked, nesdev, and web searches for each named project.
- A warning about the evidence bar: one WebFetch summary put words in Kabuto's mouth ("writing … during vertical blanking can cause corruption"). The raw page says nothing like that. Every quote above comes from raw page text I read myself.

## 6. What in the brief was wrong

- **Aeon's PAL DMA window (11648 B) is derived from 72 blanking lines, but aeon runs V28 (`$34`/`$74`, no V30 bit), which has 87-89 blanking lines.** This is the most important error I found.
- "DMA transfers happen in VBlank" is incomplete. Active display allows about 4 KB/frame at the cost of freezing the 68k, and a blanked display gives the full rate on any line.
- The hypothesis puts the whole weight on "new tiles in before repaint". The precedent says the binding costs are decompression time and co-residency. Also, "evict once off screen" should be tracked per visible nametable row, not per zone region.
- Your correction about sharing lines up with Sonic 3 & Knuckles' design. Zones share almost nothing, which is why it relies on a primary set plus hiding the background, not on tiles overlapping between zones.
