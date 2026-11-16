# Engine systems review: two independent opinions, merged (2026-11-13 / 11-16)

Read-only review. Nothing was built for it and nothing ran in an emulator. Labels: MEAS = measured
(by a reviewer, or cited from an aeon doc), EST = hand-estimated from 68000 timings, PUB = published.
Process lessons and the six ratified process changes are in
`empyrean/docs/2026-11-16-engine-quality-process-changes.md`.

**Bar (owner):** S3K is the floor. Judge against the best known technique anywhere and the hardware limit.

**Method:** four subsystem reviewers (compression, tiles/VRAM/DMA, sprites/objects/physics, sound),
then an independent second reviewer that formed its own view from source before reading the first.
The controller spot-checked the key claims in code. The second opinion overturned three first-round
recommendations; they are listed under "Dropped" so nobody re-proposes them.

## Scorecard (merged)

| System | Verdict | Key evidence |
|---|---|---|
| DMA queue | Good to top tier on features | 3 tiers, byte budget, carry-over, 128 KB split. BUT `DMA_IMPORTANT_SLOTS = 12` (`constants.emp:388`) overflows with Sonic (10 DPLC entries) + Tails (2-3); the drain also stops at the first entry that does not fit |
| Resumable ZX0 decode | Parity of mechanism with S3K (`Set_Kos_Bookmark`), better ratio | |
| Paged art pool | Ahead of the field, unused in release | OJZ is 10 pages, fully resident |
| SFX arbitration | Best of drivers compared | 7 voices, priority, steal ladder, instance caps, ducking |
| DPLC | Top tier, except the slot wall above | |
| Object loop | Structure beyond S3K, capacity below | live list (~230-238 cyc/object EST); 40 dynamic slots vs S3K 90; all object code in one 64 KB bank |
| Block compression (S4LZ v3) | Good codec, wrong problem | OJZ act 1: 241 non-blank block positions, **38 unique** (MEAS). Raw deduped = 29,184 B vs 42,582 B of compressed blobs today. Index tables are 21.6% of the blob; collision plane B duplicates A in 2274/2304 columns |
| Art compression (ZX0) | Right codec, wrong policy | 60.9% of raw (MEAS; Kosinski 68.8, Nemesis 66.9, LZ4W 87.2). Decode 140-164K clocks per page, ~74 clk/B (MODELED, matches Oracle's measurement). ARCH §9.7's 45K counts only the copy. Whole act saves 7.7 KB vs raw |
| Sprite drawing | At S3K level | ~112 cyc/piece; ~850-930 cyc/object (EST) |
| Player physics / terrain | S3K parity | faithful S.C.E. port; `Collision_GetType` ~310-330 cyc, multiply-by-80 + wrap (docs say shift-based) |
| Tile streaming | Capability beyond S3K, CPU well below | four copies per tile; ~48K cyc/tick diagonal OJZ (MEAS, 2026-09-27-ojz-feel.md) vs S3K ~8-9K (EST); decode bursts = 62% of lag frames |
| VRAM layout | Not ready for a game | planes 512 + spare NT 128; objects 154 tiles; 64x32 frees 384. `BG_Stream_Update` already streams Plane B rows (`bg.emp:642`) but OJZ rows exit early (`rg_bg_span = 0`) |
| Touch collision & rings | Below S3K | walks all live objects + 16 effect slots per player, no on-screen filter; rings: unsorted scan, ~3x S3K's visits. Box math per test ~equal; aeon's per-object w/h is kept |
| Music | At S3K level, at the ceiling of its architecture | 1 PCM voice; drums held 24-26% of airtime (S3K 21.4%); song data 79-124 B/s vs MDSDRV 15-27; Z80 blob ~6194/6384 B |

## Defects (verified in code)

1. **Lag frames ship sprites and scroll out of step.** `VInt_Lag` calls `Enqueue_Dirty_Buffers`, which ships the sprite table if dirty and HScroll always. `Render_Sprites` (ojz_scroll_test.emp:1263) runs before `Parallax_Update` (:1462). Visibility NEEDS-RUNTIME. S2/S3K ship neither on lag.
2. **Off-cache terrain.** `CULL_DISTANCE_X = $300` (768 px) but the collision cache is 80x60 tiles (640x480 px); outside reads `CTYPE_AIR` (`collision_lookup.emp:83`). Terrain-walking objects will fall off screen. The cull is asymmetric (measured from the camera's left edge).
3. **Important DMA queue overflow with a sidekick** (12 slots; see scorecard).
4. **Plane drain charged 1:1** (`vblank.emp:169-174`) though the CPU copy costs ~7.5 cyc/byte vs DMA's 2.7.
5. **Sprite band order reversed every odd frame unconditionally** (`sprites.emp:298-311`).
6. **Sound mailbox race** (latent): Z80 reads, acts, then clears; 68k posts fade/tempo/pause/jingle unconditionally.
7. **Solids resolve after the camera** (`TouchResponse` :1211 after `Camera_Update` :1117), and there is no horizontal platform carry.
8. Collision stored at 2x needed width: even/odd 8 px columns identical in 1151/1152 pairs (MEAS).

## Ranked plan

1. **Quick fixes:** nothing but palette ships on lag frames; raw-elect streamed art pages (ZX0 only for init-only); DMA the plane buffer (then the 1:1 charge is honest); Important queue 12 -> 24 slots; reverse sprite order only after an overflow frame; mailbox race; doc corrections (45K, shift-based lookup, VDP shadow, Set_VDP_Reg callers, etc.).
2. **Blocks:** level tool dedupes blocks and the index points at raw ROM blocks (no decode, no staging on resident acts). **First count unique blocks on the S2 clip acts**, and re-check the dedupe script (it reports exactly 38 collision positions and 38 unique blocks, a coincidence worth confirming). Then remove the 80x60 cache: draw and collide through the block-pointer grid. S4LZ staging stays as the fallback tier.
3. **Before badniks:** on-screen collision response list (built during draw, walked once per player, player box hoisted; invisible solids need their own registration); ring X-sort + camera window; off-cache terrain policy; solids before camera + platform carry; dynamic slots 40 -> ~96; 64x32 planes + window-plane HUD after re-authoring the OJZ background.
4. **Hybrid sound driver** as its own project: the 68k sequences inside VBlank and posts one YM/PSG register list per frame under the existing bus hold; the Z80 runs a fixed-cost loop mixing 2 PCM voices and applying at most one YM write per sample. Keep the current driver until the new one passes the VGM-diff harness. Expect 13-17 kHz with two voices; PAL needs tempo compensation. Owner decision pending.
5. **Later:** S4LZ index u16/sparse, collision at 16 px cells, power-of-two cache width (moot if the cache goes), multi-bank object code, compiled sprites.

## Dropped (do not re-propose without new evidence)

- **Decoded blocks resident in RAM:** a 768 B block x up to 256 per zone = ~196 KB; release has ~19.6 KB free. Only OJZ (38 blocks) fits.
- **Charge the plane drain at ~3x:** a full buffer (1536 x 3 = 4608) plus Critical (~1664) exceeds the 6144 budget, starving page landings during diagonal scrolls. DMA the buffer instead.
- **Baked plane strips in ROM:** ~2.4 MB for OJZ's two orders, carries no collision, resident acts only.
- **Cache screen X/Y in sprite band entries:** saves under 100 cyc/object, and goes stale because `TouchResponse` moves the player between Draw_Sprite and `Render_Sprites`.
- **upkr / context-Huffman for tiles:** slow on 68000, ~1.9 KB per act; not worth it while ROM is ~10% used.

## Beyond-state-of-the-art candidates (plausible)

- A two-tier pointer window: each window cell points at a ROM block or a RAM stage slot, giving streaming virtual-memory tiles at near-S3K draw cost.
- The hybrid sound driver (no known shipped Genesis driver combines MDSDRV-class sequencing, XGM-class PCM mixing and live FM SFX arbitration).
- ROM-direct plane DMA from raw physical-word blocks (modest gain; last).
