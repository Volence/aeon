# Region Background Switch: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Phase 2 does not start until the controller says go.

**Goal:** when the camera centre enters a region whose background TILES differ from the ones in VRAM, overwrite the background tile block from that region's own blob, spread over frames, and only then repaint Plane B through the existing step-6 crossing wipe, with the ordering enforced by the sequence and a gate that goes red if the repaint can start early.

**Architecture:** one more level-triggered arm in `BG_Stream_Update`, placed ABOVE the existing wipe arm and structurally gating it: compare the region's effective tile blob with `BG_Tiles_Current` (what VRAM holds). On a difference, upload the blob as ROM-to-VRAM DMA chunks through the Deferrable queue, one outstanding chunk at a time, and suspend the wipe and the streamer until the last chunk has been observed SENT. The synchronous writer (`Section_RedrawPlanes`, boot and DEBUG warp) uploads the resolved region's tiles in its own masked storm before it blits the nametable, and cancels any asynchronous overwrite in flight. BgAnim bands pause while VRAM does not hold the act-default tiles.

**Tech Stack:** `.emp` (68000) assembled by sigil; Python gate on the headless Aether emulator (`tools/aether_instance`, the `bg_wipe_gate.py` rig); `tools/effects_gates.py` as the runner; `tools/landing_build.sh` for landing.

**Spec:** `docs/superpowers/specs/2026-09-16-megaact-bg-streaming-design.md` (the CORRECTION BANNER overrides its body; §3.1's blank step, §3.6 and §5 are superseded) and `docs/research/megaact-bg-streaming/07-fable-design-review.md`.

## Global Constraints

- Owner rulings R1-R7 (spec §2) and the banner's owner ruling: **no blank step**; full overwrite, then repaint, behind authored cover (R3). Palette machinery unchanged (R6).
- **The repaint must not start until the overwrite completes, enforced by the sequence, not by timing.** A gate must be able to go red.
- Not in scope: hysteresis (M-C), the position-driven palette blend, FG stress/budget work (`tools/` M-B files and `docs/research/megaact-bg-streaming/08-*` belong to another agent; do not touch), REGIONS-P2-STEP7/8.
- Read `CODING_CONVENTIONS.md` and `docs/EMP_PITFALLS.md` before writing any `.emp`. Transfers `jbsr`/`jbra`/unsized `bcc`; no `mulu`/`divu`; comptime for derivable math; `ensure` for every derived bound.
- Never `mcp__oracle__*`. Headless gate lanes only. A human look is TAGGED for the controller.
- Branch `parcel/region-bg-switch`, base `ae861d1a` or later. Exact-path `git add`, `git show --stat` after each commit, finding in the body. Keep `docs/ENGINE_ARCHITECTURE.md` (§2.4) and `docs/DEFERRED_WORK.md` in sync in the same commit.
- Build shell: `export SIGIL_BUILD=/home/volence/sonic_hacks/sigil/target/release/sigil` and `export SIGIL_EMIT=/home/volence/sonic_hacks/sigil/target/release/emit_sound_blob`. Landing evidence is `./tools/landing_build.sh` (read `finished=<n>`). Any step touching `engine/level/bg_anim.emp`, `engine/effects/*` or `engine/system/buffers.emp` also runs `python3 tools/effects_gates.py --rom s4.debug.bin --lst s4.debug.lst` and reports totals and exit code. Never pipe a gating command. Clear `tools/__pycache__` before trusting pytest.
- Every new gate leg is proven red first: mutation applied on disk and quoted back, red run shown, restore from the COMMITTED baseline (never `git checkout --` on a dirty tree).

---

## What I checked, and where the brief or the review was wrong or incomplete

Each of these was re-read at `ae861d1a`. They change the design, so they come first.

1. **Band slots are the FRONT of the BG blob, not the 56-tile reserve.** `games/sonic4/vram.toml:223-262` and `tools/inject_editor_bg.py` `validate_band_coherence`: "A band's tiles ARE the front of `tiles` (its phase-0 IS the static art there)". The 56-tile `band_reserve` is headroom withheld from the static importer, not where bands live. So a region overwrite ALWAYS rewrites band slots, and a live band's DMA would scribble over the new region's front tiles. The review's "320 static + 56 reserve" is right as a capacity statement and misleading as a location statement. Consequence: Task 6.
2. **In release, OJZ act 1's band table is empty** (`games/sonic4/data/generated/ojz/act1/bg_anim.emp:7`, `BgAnim_Table: u16 = 0`, `default_off`). Bands run only when the DEBUG lab points `BgAnim_Table_Ptr` at a live table. Review finding 7 (no release selector) is confirmed at `engine/level/bg_anim.emp` `BgAnim_Update`.
3. **⚠ THIS ITEM WAS WRONG IN THE FIRST DRAFT (`44ae3101`) AND IS CORRECTED HERE; do not copy the old sentence.** The draft said the Deferrable queue had exactly two producers, both in `bg_anim.emp`, that "no FG art uses it", and that this made "queue observed empty" a sound completion test. The controller found a third producer, and re-deriving the set (grep over `engine games tools` for `QueueDMA_Deferrable`, `Perform_DPLC_Deferrable`, `perform_dplc`, `DMA_Deferrable_Slot`, `.asm` included; the only writers of the slot cell are `dma_queue.emp` itself) gives **four producer paths**:
   - `BgAnim_Update` bands (`bg_anim.emp:320`, `:330`), destination inside the BG arena;
   - `Waterline_Art_Update` (`bg_anim.emp:478`), destination `VRAM_WATERLINE_STRIPS`, just above the arena;
   - `Perform_DPLC_Deferrable` (`engine/objects/dplc.emp:387-388`, the `perform_dplc(QueueDMA_Deferrable)` template), called by `games/sonic4/player/player_instashield.emp:605` and `games/sonic4/objects/dust_spindash.emp:262`: OBJECT SPRITE art for Sonic's own effects, destinations in the object regions below `$8000`. `perform_dplc` enqueues only when `mapping_frame != prev_frame`, and commits `prev_frame` only after every entry of the frame was accepted, so a dropped frame retries next frame, but an ACCEPTED frame whose entries are later removed from the queue is not re-sent until the animation changes frame again.
   "No FG art uses it" is true of foreground TILES and false of the queue. **Consequence:** a global "queue empty" test can stay false on consecutive frames while the player spindashes or insta-shields, so the overwrite could never complete and the wipe and streamer would stay suspended indefinitely: the soft-lock class, on the background. Completion is therefore keyed to the overwrite's OWN writes (C2, as amended), and the synchronous cancel removes only arena-destined entries (C9, as amended).
4. **"Enqueued" is not "landed before the repaint", and that is the Icecap bug waiting in this engine.** `engine/system/vblank.emp` drains in this order: `VInt_DrawLevel` (the plane buffer, so wipe rows) at ~:176, then `Process_DMA_Critical`, then `Process_DMA_Important`, then `Process_DMA_Deferrable` (:282). A wipe armed on the same main-loop frame as the final chunk's enqueue would put new-layout rows on the VDP BEFORE the final tiles in the SAME VBlank, and a chunk refused by the drain budget (`Drain_Budgeted_Queue` compacts and keeps it) could sit for several frames. So completion must be observed on a later frame, after the queue is seen to hold no entry writing the BG arena (C2). A frame-boundary sampler cannot see the same-VBlank inversion; the gate needs a starvation leg (Task 4).
5. **The Deferrable queue persists across frames.** A band DMA refused on frame N-1 can land after an overwrite chunk queued on frame N if they sit in different queues. Keeping the overwrite in the SAME FIFO as bands makes their relative order the enqueue order (Task 3, call C1).
6. **A regions DOCUMENT cannot express a per-region background today, and cannot express tiles at all.** `tools/effects_gen.py` `_check_region_bg` refuses every non-`@act` `layoutRef` (the library `ojz_bglib.json` has only `id`/`name`, so no height and no symbol), and `empyrean/contract/schema/aurora-regions.schema.json` `bg` is closed with only `layoutRef` and `span`. `empyrean/docs/AURORA_REGIONS_SCHEMA.md:413` records the `layoutRef` lowering as explicitly open and unowned. So the test content must be a DEBUG-shape build-time delta row, the same mechanism as `OJZ_E2_SNAP_ROWS` and `OJZ_TALL_BG_ROWS` (`games/sonic4/data/levels/ojz/act1/act_descriptor.emp:612-719`). Making it authorable is cross-repo and is booked (call C11).
7. **The existing BG gates assume exactly one region names a layout.** `tools/bg_wipe_gate.py` `pick_fixture` raises `GateError` (exit 2) if the ROM has more than one row with `rg_bg_layout`; `tools/bg_window_gate.py` reads the same tall-row premise. Adding test content breaks both unless they name their fixture (Task 2).
8. **BG-BOOT-REGION-BLIT has an overseer ruling** (`docs/DEFERRED_WORK.md:35302`, "ROUTE 2 IS REFUSED, ROUTE 1 STANDS"): `BG_Init` keeps its act-default blit; `Section_RedrawPlanes` is the region-aware writer. This plan keeps that ruling: the region tile upload goes in `Section_RedrawPlanes`, `BG_Init` still loads the act default (Task 2).
9. **There is no respawn path to fix.** No death/respawn system exists (`games/sonic4/player/player_common.emp:2843`, `:2901`). The only `Section_Plane_Dirty` setters are the boot ladder (`games/sonic4/test/ojz_scroll_test.emp:911`) and `Debug_Warp_Consume` (`:1807`). Respawn is booked as a contract, not built (Task 2).
10. **Review citations re-read and holding:** `bg.emp:614-622` (the level-triggered arm), `:700-713` (plane-row cursor), `:748-777` (streamer loop), `bg.emp:144` (`BG_Init` loads only `Act.act_bg_tiles`), `structs.emp` `Region` (size 22, `rg_bg_layout` $10, `rg_bg_span` $14, no tiles field), `bg_anim.emp` release `lea BgAnim_Table`, `constants.emp:648` (`BG_TILE_CAPACITY = 376`), `:708` (`DMA_BUDGET_NTSC = 6144`), `act_descriptor.emp:172` (`ACT_ART_BUDGET = 4096`).
11. **Measured sizes of the candidate art** (`games/sonic4/data/editor/*_tiles.bin`, 2-byte header + raw): the shipped act default is 320 tiles (`generated/ojz/act1/bg_tiles.bin`, 10242 B). Of the 17 library entries only three fit the 320-tile static budget: `deep-forest-v15-marching-colonnade` (216), `deep-forest-v16-trunks-over-wall` (216) and `ojz_act1_bg` (218). The other fourteen are 364-512 tiles.

---

## Design calls the ruled design did not settle

Each carries my recommendation. The ones marked **OWNER** change something the player or the designer sees.

| # | Call | Recommendation and reason |
|---|---|---|
| **C1** | Which DMA queue carries the overwrite? | **Deferrable.** It drains after Important in the same VBlank, so FG page landings (the camera-hold path) keep priority and the BG overwrite takes what is left. It is the queue bands use, so band and overwrite writes to the same slots are FIFO-ordered (the queue compacts in order, `Drain_Budgeted_Queue`). (The draft's extra justification, "its only other producer is BgAnim", was false; see item 3. It was never needed for the FIFO argument.) Starvation behind object DPLC traffic is bounded because every other producer is either sprite art enqueued only on an animation frame change (at most one frame's entries per object per frame, the insta-shield's peak `ensure`d at `player_instashield.emp:430-438`) or held (bands, C10), and C3's static check reserves their peak in the same window. Proven by leg TRAFFIC (Task 3). |
| **C2** | What does "overwrite complete" mean? | **AMENDED after controller review (the draft keyed it to the queue being globally empty, which never completes under object DPLC traffic; item 3).** Complete = **the final chunk has been enqueued AND a later main-loop frame finds NO queued Deferrable entry whose destination lies in the BG arena** `[BG_TILE_BASE_VRAM, BG_TILE_BASE_VRAM + BG_TILE_CAPACITY_BYTES)`. The same test gates "one outstanding chunk at a time". Why destination rather than remembering our own entry: `Drain_Budgeted_Queue` moves entries when it compacts, a chunk that straddles the 128 KB source boundary becomes TWO entries, and a band DMA queued before the arm (bands are held from the arm on, C10) must also land before the repaint, and all three are covered by "no arena-destined entry" and missed by "my entry is gone". The destination is decoded from the entry's `Command` longword by the runtime inverse of `vdp_comm_reg` (`engine/vdp.emp` already has the comptime inverse, `vdp_comm_addr`), pinned by a comptime `ensure` that the two agree at the arena's first and last byte. It is BOUNDED under any other traffic: from the arm on, nothing but the overwrite enqueues into the arena (bands held; DPLC and waterline destinations are outside it, `ensure`d in the game against `vram.toml` regions), so the arena-destined set only shrinks between our own enqueues, and every entry drains on the first frame whose window residual covers it (C3). Sent means landed, because DMA completes inside VBlank. |
| **C3** | Chunk size and budget. | **`BG_OVERWRITE_CHUNK_BYTES` = 2048 (64 tiles), comptime, with an `ensure` that it fits `DMA_BUDGET_NTSC` minus the plane-drain peak (`FG_PEAK_BYTES + BG_PEAK_BYTES` in `bg.emp`, 1328 B) minus the Critical peak (derived in Task 3 from the static entries: HScroll 896 + SAT + palette lines + ship; roughly 1760 B, to be re-derived, not carried) minus the peak of every OTHER producer that can sit ahead of it in the window (AMENDED: Important-queue player DPLC, and the Deferrable queue's own other producers: insta-shield and spindash-dust DPLC peaks from `dplc_peak_tiles`, and the waterline DMA's `WATERLINE_DST_BYTES`).** Because those peaks are game data, the engine declares the chunk and the engine-side terms, and the game states the full `ensure` where both are visible (`games/sonic4/config/`), following the insta-shield entries guard at `player_instashield.emp:430-438`. Act art page landings are NOT in the sum: they are the priority C1 chose, and OJZ act 1 lands none in play (fully resident). It does NOT charge `Art_Budget_Remaining`: that is an Important-queue enqueue governor and this is not Important. Under sustained FG page-in the overwrite waits; that is the priority C1 chose. A 320-tile blob is 5 chunks, so about 6 frames on calm frames, plus the 16-frame sweep. |
| **C4** | Does "full overwrite" mean all 376 slots? | **No: the region blob's own length**, clamped to `BG_TILE_CAPACITY` like `BG_Init`. Slots past it keep old art that no nametable word of the new layout references. Padding would cost DMA frames and change nothing on screen. |
| **C5** | Tile identity. | **By blob pointer**, `Region.rg_bg_tiles` 0 = `Act.act_bg_tiles`, the same convention and ladder as `rg_bg_layout`. Two regions naming one blob never re-upload. Appended at $16, so `Region` goes 22 to 26 B and no existing offset moves. |
| **C6** | If only tiles differ (same layout pointer), repaint or not? | **Always repaint: arming an overwrite zeroes `BG_Plane_Layout`.** The streamer is suspended during the overwrite (C7), so the window can go stale on a fall, and an in-flight sweep for the previous region is cancelled. Forcing the wipe re-primes the window (the wipe arm already snaps `BG_Plane_Top` to `want_top`) and repaints every row. Cost: 16 frames of sweep on a tiles-only switch, which is a rare authoring case. One rule with no exceptions beats a correct-but-conditional one here. |
| **C7** | What do the streamer and an in-flight wipe do during the overwrite? | **Both suspended** (the overwrite arm returns before the wipe and the streamer). The arm clears `BG_Wipe_Cursor`. On a vertical move during the overwrite the visible rows can show the wrong map row of the OLD picture over half-new tiles: that is garbage, and it is the garbage R3 makes the designer cover. The alternative (keep streaming from the old layout) needs the old region pointer retained and still paints over tiles that are changing. |
| **C8** | Re-entrancy: the target changes mid-overwrite. | **Restart.** Each frame the effective blob is compared with `BG_Tiles_Target`; on a difference the target is replaced and the offset resets to 0. Chunks already queued for the old target land first (FIFO) and are overwritten; completion (C2) waits for the queue to empty after the new target's last chunk, so nothing stale can land after it. It cannot lock up: every frame either enqueues, waits on a draining queue, or completes. What it can do is never finish while a player oscillates across a boundary faster than an overwrite, and that is M-C's hysteresis, out of scope. Walking back to the original region mid-overwrite also restarts (its tiles are already partly gone; `BG_Tiles_Current` was zeroed at arm). |
| **C9** | The synchronous path (boot, DEBUG warp, any future recovery/respawn). | **`Section_RedrawPlanes` uploads the resolved region's tile blob in its existing masked storm, before the nametable blit, whenever it differs from `BG_Tiles_Current`, and cancels the async overwrite**. AMENDED after controller review: the draft reset `DMA_Deferrable_Slot` to base, which would also drop accepted insta-shield and dust DPLC entries, and `perform_dplc` does not re-send an accepted frame until `mapping_frame` changes again, so those sprites would show stale tiles for up to one animation frame. The cancel now REMOVES ONLY ARENA-DESTINED ENTRIES (a compacting walk over at most `DMA_DEFERRABLE_SLOTS` entries, inside the existing SR mask, reusing C2's destination decode), so object and waterline entries survive in order. It then zeroes the target and offset, recomputes the band hold, and invalidates `BgAnim_LastStep` (the dropped arena entries include any band DMA; bands re-send their phase). `BG_Init` is unchanged except for seeding the trackers (the overseer's route-1 ruling). Boot into a non-default region then costs one extra tile upload with the display off. |
| **C9b** | Display during the synchronous upload on a warp (display ON). | **Leave it on.** The warp is DEBUG-only and already a ~3-frame masked storm; the tile upload shows as a transient during that storm. Batman & Robin's immediate-transfer handler turns the display off (`interrupts.asm:585-622`); doing the same here touches the VDP shadow-register contract and is booked, not built, unless a real (non-DEBUG) caller of the synchronous path appears. |
| **C10** | BgAnim bands with per-region tiles. | **Make the switch safe with bands present; book per-region bands.** A byte `BG_Bands_Hold` is set whenever VRAM does not hold the act-default tiles or an overwrite is in flight, and `BgAnim_Update` returns early while it is set. When an overwrite back to the act default completes, the hold clears and `BgAnim_LastStep` is reset to -1 so every band re-sends its current phase over the freshly uploaded phase-0 art. A region with its own art therefore shows no band animation. Per-region band tables need a release table selector plus importer emission, and the owner has shipped no bands in release, so there is no content to justify that RAM and code yet. |
| **C11** | Test content: where does the second background come from? | **A DEBUG-shape delta row**, like the E2 snap row and the tall row, generated by a new tool from an existing library entry. Default choice **`deep-forest-v15-marching-colonnade`** (216 tiles, fits). The look is the owner's; this is an instrument. **OWNER/HUB:** making it authorable in a regions document needs the `layoutRef` lowering (open at empyrean `AURORA_REGIONS_SCHEMA.md:413`) plus a new contract key for tiles. That is cross-repo and booked. |
| **C11b** | Which rectangle? | **Decided in Task 2's research, not here, by three constraints:** (1) no existing gate route crosses it (enumerate every `Boot_At`/warp coordinate and held-button route in `tools/*gate*.py` and `tools/*witness*.py`); (2) it has an act-default neighbour on a horizontal AND a vertical edge, with the interior edges inside the `CENTRE_X/Y` bands and wider than `REGION_MIN_SPAN`; (3) the carve is expressible. `ojz_cut_row` only cuts rows that reach the act's right edge, and all three such rows (2, 5, 8) are already cut, so the likely answer is a sibling that cuts a named row at a stated expected `x1`, with the same `ensure`s. |
| **C12** | Size ceiling for a region blob. | **Build: the static budget** (`tiles - band_reserve` = 320), `ensure`d in the row constructor and the table walk, so region art obeys the same importer contract as the act's. **Runtime: clamp to `BG_TILE_CAPACITY`**, like `BG_Init`, as the last line of defence. |
| **C13** | How does the gate starve the transport? | **Poke `DMA_Budget_Default`** (a RAM word, `engine/ram.emp:406`, reseeded into `DMA_Budget_Remaining` every VBlank) below one chunk for N ticks, then restore it. This holds the chunk in the queue so the ordering has room to fail visibly at a frame-boundary sample. |
| **C14** | OC-3: hold the camera when authored cover is shorter than the sequence. | **Book as an owner option** (review "wrongly superseded"). The mechanism would be `Camera_Art_Hold`; nothing in this parcel needs it and R3 puts cover on the designer. |

---

## Review findings: where each one lands

| Review finding | Disposition |
|---|---|
| 1. Over-budget FG soft-locks; budget is the 80x60 window | **Booked, not mine.** Another agent owns M-B and M-E in `tools/` and `08-*`. |
| 2. Blank step has no transport; overwrite transport missing | Blank: **dropped by the owner** (banner). Overwrite transport: **handled in Task 3.** |
| 3. Cover ~2 screens at speed; D4 check should return as a warning; blank fill word | Cover warning: **booked** (needs the opaque-FG extent per crossing, which is Aurora-side and build-side work, and M-A's measured duration from Task 7 as its input). Blank fill word: **moot** with no blank. |
| 4. Hysteresis at the crossing; reversal; re-entrancy | Hysteresis: **out of scope** (M-C). Re-entrancy and reversal: **handled in Task 4** (C8). |
| 5. Streamer and `Section_RedrawPlanes` paint garbage mid-sequence | Streamer: **Task 4.** `Section_RedrawPlanes`: **Task 2** (loads tiles first) and **Task 5** (cancels an async overwrite in flight). |
| 6. Boot, respawn, warp into a non-default region | Boot and warp: **Task 2.** Respawn: **booked as a contract**: no respawn system exists; whoever builds one must reach `Section_Plane_Dirty`, which now carries tiles. |
| 7. BgAnim has no release selector; 320 + 56 | **Task 6** (C10) makes the switch safe with bands present; per-region bands **booked**. The 320/56 location correction is item 1 above; C12 sets the ceiling. |
| 8. Palette at a horizontal junction | **Booked** under R6 and the position-driven blend. Nothing in this parcel changes palette. |
| 9. Icecap overclaim | **No code.** The banner already corrects the spec. Item 4 above records the mechanism in THIS engine. |
| 10. The 4096 B figure is the act art budget, not the window | **Task 3** derives the chunk from the window (C3). **Task 7** measures real frames. The FG-contention worst case needs a streaming act; OJZ act 1 is fully resident, so Task 7 **books** that half unless the stress fixture can run it. |
| 11. Per-zone object art; Sonic 4 vs stress test | **Booked.** The VRAM levers are out of scope. |
| Measurements section (M-A after the transport) | **Task 7** measures M-A as overwrite + repaint (no blank) on two routes. |

---

## File structure

| File | Responsibility | Tasks |
|---|---|---|
| `engine/structs.emp` | `Region.rg_bg_tiles` appended ($16), size 26 | 1 |
| `engine/ram.emp` | `BG_Tiles_Current`, `BG_Tiles_Target` (u32), `BG_Tiles_Offset` (u16), `BG_Bands_Hold` (u8 + pad) | 1 |
| `engine/level/bg.emp` | `BG_UploadTiles` (synchronous blob copy, factored out of `BG_Init`); tracker seeding; the overwrite arm and spend in `BG_Stream_Update`; `BG_OVERWRITE_CHUNK_BYTES` and its `ensure` | 2, 3, 4, 6 |
| `engine/level/section.emp` | `Section_RedrawPlanes`: resolve tiles, synchronous upload, async cancel | 2, 5 |
| `engine/system/dma_queue.emp` | `DMA_Deferrable_DestPending`, `DMA_Deferrable_DropDest`, the runtime destination decode (AMENDED) | 3, 5 |
| `games/sonic4/config/` | the full chunk-fit `ensure` over the game's DPLC and waterline peaks; other producers' regions outside the arena (AMENDED) | 3 |
| `engine/level/bg_anim.emp` | `BG_Bands_Hold` early exit in `BgAnim_Update` | 6 |
| `tools/effects_gen.py` | emit `rg_bg_tiles: 0` on every generated row | 1 |
| `games/sonic4/data/generated/ojz/act1/regions.emp` | regenerated | 1 |
| `games/sonic4/data/levels/ojz/act1/act_descriptor.emp` | `ojz_region(bg_tiles:)`, `ojz_cut_row` field copy, table-walk rule for tiles, the DEBUG showcase row | 1, 2 |
| `games/sonic4/data/levels/ojz/act1/act_assets.emp` | DEBUG-only showcase layout + tiles embeds | 2 |
| `tools/gen_region_bg_showcase.py` (new) | editor library entry to engine layout (row-major, rebased) + tile blob; `--check` | 2 |
| `tools/inject_editor_bg.py` | factor the nametable rebase + tile blob packing into importable functions (no output change) | 2 |
| `tools/region_table.py`, `tools/test_region_table.py` | stride 26, `$HH` comment gate, `bg_tiles` field | 1 |
| `tools/bg_wipe_gate.py`, `tools/bg_window_gate.py` | name the tall fixture (`rg_bg_span != 0`) instead of "the only row with a layout" | 2 |
| `tools/bg_switch_gate.py` (new) | GATE BG-SWITCH legs | 2-6 |
| `tools/effects_gates.py` | `bg_switch` row | 2 |
| `tools/test_gen_region_bg_showcase.py` (new) | pytest for the generator | 2 |
| `docs/ENGINE_ARCHITECTURE.md` §2.4 | the switch sequence, the trackers, bands, the sync path | every task |
| `docs/DEFERRED_WORK.md` | BG-BOOT-REGION-BLIT update; new bookings | every task |
| `docs/research/megaact-bg-streaming/region-bg-switch-cost.md` (new) | M-A result | 7 |

---

### Task 1: The data model (`Region.rg_bg_tiles` and the RAM trackers)

**Files:**
- Modify: `engine/structs.emp` (the `Region` struct and its `ensure(sizeof(Region) == 22 ...)`)
- Modify: `engine/ram.emp` (beside `BG_Plane_Layout`, ~:600-645)
- Modify: `tools/effects_gen.py` (the region-row emitter), regenerate `games/sonic4/data/generated/ojz/act1/regions.emp`
- Modify: `games/sonic4/data/levels/ojz/act1/act_descriptor.emp` (`ojz_region`, `ojz_cut_row`, `ojz_region_table_check`)
- Modify: `tools/region_table.py`, `tools/test_region_table.py`, and every other reader found by the research step

**Interfaces:**
- Produces: `Region.rg_bg_tiles: *u8 = 0` at $16; `sizeof(Region) == 26`; RAM `BG_Tiles_Current: u32`, `BG_Tiles_Target: u32`, `BG_Tiles_Offset: u16`, `BG_Bands_Hold: u8`; `ojz_region(..., bg_tiles: Label = 0)`; rule code 9 in `ojz_region_table_check` (tiles blob longer than the static budget is checked in Task 2 where the first blob exists, since a comptime length of an `embed` label must be verified reachable first).

- [ ] **Step 1: Research.** Enumerate every reader of the Region stride or field list BY WHAT TOUCHES THE VALUE, not by name: `command grep -rn "sizeof(Region)\|Region{\|rg_bg_span\|22" engine games tools --include='*.emp' --include='*.py'`, then read each hit. Known so far: `engine/level/parallax.emp` `lea sizeof(Region)(a0)`, two `mul_const.w ... #sizeof(Region)` in `games/sonic4/test/ojz_scroll_test.emp`, `tools/region_table.py` (the `// $HH` comment gate and the ROM row reader used by `bg_wipe_gate.py`), `tools/effects_gen.py`'s literal emitter, `ojz_cut_row`'s field-by-field copy, `tools/test_s4budget.py`, and the shared golden `tools/fixtures/regions/ojz_act1.rows.json` (engine rows in document vocabulary; confirm whether it enumerates engine fields, and if it does, whether adding one is a cross-repo change to raise with the controller rather than make). S3K/S.C.E./B&R have no equivalent record, so no reference check applies to this task.
- [ ] **Step 2: Write the failing test.** In `tools/test_region_table.py`, add `test_region_record_carries_bg_tiles_at_offset_22` asserting the parsed `engine/structs.emp` `Region` has a `rg_bg_tiles` field at `$16`, pointer width, and the declared size is 26. Clear `tools/__pycache__`, run `python3 -m pytest tools/test_region_table.py -q`: expect FAIL naming the missing field.
- [ ] **Step 3: Implement.** Append to `Region`:
  ```
      rg_bg_tiles:         *u8 = 0,       // $16 — BG tile blob (2-byte length + raw tiles);
                                          //       0 = Act.act_bg_tiles. READ by
                                          //       engine/level/bg.emp (the overwrite arm) and
                                          //       engine/level/section.emp (Section_RedrawPlanes).
  ```
  Change `(size: 22)` to 26 and the `ensure` to 26, with its message updated. Add the four RAM cells after `BG_Wipe_Row` WITHOUT splitting the `BG_Wipe_Cursor`/`BG_Wipe_Row` pair (the adjacency `ensure` at the foot of `bg.emp`), padding to even. Add `bg_tiles: Label = 0` to `ojz_region()` and `rg_bg_tiles: bg_tiles` to its literal; copy the field in `ojz_cut_row`; make `effects_gen.py` emit `rg_bg_tiles: 0` on every row and regenerate. Update `tools/region_table.py` for stride 26 and the new field. Nothing reads the RAM cells yet; they are declared here so later tasks only add behaviour.
- [ ] **Step 4: Verify.** Clear `tools/__pycache__`; `python3 -m pytest tools/test_region_table.py tools/test_regions_doc.py -q` PASS. `./build.sh` and `DEBUG=1 ./build.sh` green. The release ROM moves (the region table grew 40 B plus RAM layout); that is routine. `python3 tools/effects_gates.py --rom s4.debug.bin --lst s4.debug.lst --only bg_wipe,bg_window` (or the runner's equivalent selector) still green, because `region_table.py`'s stride moved under them.
- [ ] **Step 5: Docs + commit.** ENGINE_ARCHITECTURE §2.4 gains the `rg_bg_tiles` bullet. `git add engine/structs.emp engine/ram.emp tools/effects_gen.py games/sonic4/data/generated/ojz/act1/regions.emp games/sonic4/data/levels/ojz/act1/act_descriptor.emp tools/region_table.py tools/test_region_table.py docs/ENGINE_ARCHITECTURE.md` (plus any reader Step 1 found); commit `regions: Region.rg_bg_tiles (22 -> 26 B) and the BG tile trackers` with the reader enumeration in the body.

### Task 2: Test content, and the synchronous path (boot and DEBUG warp load the region's tiles)

**Files:**
- Create: `tools/gen_region_bg_showcase.py`, `tools/test_gen_region_bg_showcase.py`, `tools/bg_switch_gate.py`
- Modify: `tools/inject_editor_bg.py` (extract `rebase_layout(words) -> bytes` and `pack_tile_blob(tiles) -> bytes`; output byte-identical)
- Modify: `games/sonic4/data/levels/ojz/act1/act_assets.emp`, `act_descriptor.emp`
- Modify: `engine/level/bg.emp` (`BG_UploadTiles`, `BG_Init` seeds trackers), `engine/level/section.emp` (`Section_RedrawPlanes`)
- Modify: `tools/bg_wipe_gate.py`, `tools/bg_window_gate.py` (fixture naming), `tools/effects_gates.py` (`bg_switch` row), `tools/regenerate-level.sh` or `build.sh` (wire the generator's `--check`, following how `gen_tall_bg_test.py` is wired)

**Interfaces:**
- Consumes: Task 1's field and RAM cells.
- Produces: `pub proc BG_UploadTiles (a1: *u8) clobbers(d1/a1-a2)`, a blocking copy of a length-prefixed blob to `BG_TILE_BASE_VRAM` with `BG_Init`'s guards (capacity clamp, longword count first, skip on zero), CALLER owns interrupt mask and Z80 posture; DEBUG data `OJZ_Act1_BG_Showcase_Layout: [u8; BG_LAYOUT_SIZE]`, `OJZ_Act1_BG_Showcase_Tiles`; DEBUG row `OJZ_SHOWCASE_BG_ROWS`; gate legs BOOT and WARP.

- [ ] **Step 1: Research.**
  - Engine: re-read `Section_RedrawPlanes`'s Plane B half (`section.emp` ~:520-690) for the exact span inside the SR mask and the sound flag bracket (the upload must sit inside both, before `.plb_have_layout`'s blit), and `BG_Init` (`bg.emp:133-287`) for the guards to factor.
  - Rectangle (C11b): enumerate every route and boot/warp coordinate in `tools/*gate*.py`, `tools/*witness*.py` and `tools/effects_gates.py` so the showcase rectangle crosses none; check `REGION_MIN_SPAN`, `CENTRE_X_MIN/MAX`, `CENTRE_Y_MIN/MAX` in `act_descriptor.emp:459-475`; decide the carve and whether `ojz_cut_row` needs a sibling.
  - Art: confirm `ojz_bg_deep-forest-v15-marching-colonnade-*.bin` is a 64x32 row-major editor layout with local indices (measured: 4096 B, indices 0..215, palette line 2) and its `_tiles.bin` is a 2-byte length plus 216 x 32 B.
  - References: S3K's synchronous act reload path (`HCZ1BGE_DoTransition` ~:105771 `Load_Level` with tiles already landed via `Kos_modules_left`; slice 01 T4) and Batman & Robin's immediate handlers `$7604`/`$7468` used on checkpoint restart (slice 04). Both do tiles, then nametable, in one blocking unit: the ordering this task copies.
- [ ] **Step 2: Generator test first.** `tools/test_gen_region_bg_showcase.py::test_showcase_layout_is_row_major_rebased_and_references_only_its_own_tiles`: run the generator into a tmpdir; assert layout is 8192 B, every nonzero word's index lies in `[BG_TILE_BASE_SLOT, BG_TILE_BASE_SLOT + tile_count)`, rows 32..63 are zero padding, the tile blob is `2 + 216*32` with a matching header, `tile_count <= BG_TILE_CAPACITY - band_reserve` (read from `games/sonic4/vram.toml`), and the tile blob is NOT byte-identical to `generated/ojz/act1/bg_tiles.bin` (the whole point is visibly different art). And `test_inject_editor_bg_output_is_unchanged_by_the_refactor` (run the injector into a tmpdir, compare with the committed `zone_bg.bin`/`bg_tiles.bin`). Clear pycache, run: FAIL (module missing).
- [ ] **Step 3: Generator.** Extract `rebase_layout` and `pack_tile_blob` from `inject_editor_bg.py` (the loop at ~:1325-1367). Write `gen_region_bg_showcase.py` taking `--entry <library id>` (default the v15 id), reading `games/sonic4/data/editor/ojz_bg_<id>.bin` and `_tiles.bin`, refusing an id absent from `ojz_bglib.json`, writing `games/sonic4/data/generated/ojz/act1/zone_bg_showcase_debug.bin` and `bg_tiles_showcase_debug.bin`, with `--check` like `gen_tall_bg_test.py`. Note: the editor `_tiles.bin` format must be read by the same decoder the injector uses (confirm in Step 1; if the editor file is already the engine's packed form, `pack_tile_blob` is a pass-through and the test says so). Run tests: PASS.
- [ ] **Step 4: Content.** In `act_assets.emp`, DEBUG-only embeds shaped like `OJZ_Act1_BG_Layout_Tall` (typed, `[]` in release), with an `ensure` on the tile blob length against `(BG_TILE_CAPACITY - BG_BAND_RESERVE)*32 + 2` (derive the reserve from wherever the game already mirrors `vram.toml`; if nothing mirrors it, add the mirror constant with the existing `vram.toml` drift-`ensure` pattern in `games/sonic4/config/constants.emp:527`). In `act_descriptor.emp`, the `OJZ_SHOWCASE_BG_ROWS` delta (`bg_layout:` and `bg_tiles:` both set, preset reused from the carved row so only the BG differs), composed after `OJZ_TALL_BG_ROWS`, with the carve from Step 1. Add rule 9 to `ojz_region_table_check`/`_fault_count`: none needed for layout/tiles pairing (both combinations are legal, see C5), so rule 9 is only the static-budget length check if a comptime length of the label is readable; if not, the `act_assets.emp` `ensure` is the check and the table walk says so.
- [ ] **Step 5: Fix the two gates that assumed one layout row.** `pick_fixture` in `bg_wipe_gate.py` and the equivalent in `bg_window_gate.py`: select the row with `bg_span != 0` (the tall row) and refuse loudly if that count is not 1. Build DEBUG; run `python3 tools/effects_gates.py --rom s4.debug.bin --lst s4.debug.lst` and confirm `bg_wipe` and `bg_window` still PASS (they must not have become vacuous: the leg counts printed must match the pre-change run, recorded before the edit).
- [ ] **Step 6: Gate legs BOOT and WARP, written before the engine change.** `tools/bg_switch_gate.py`, on the `bg_wipe_gate.py` rig (`Rig.boot(at)`, `tick`, `read_vram`, `read_memory`, `write_memory`), with every expectation derived: the showcase row read out of the ROM by `region_table.py` (the row whose `bg_tiles != 0`, refuse if not exactly one), the blob's length and bytes read out of the ROM at `bg_tiles`, `BG_TILE_BASE_VRAM` parsed from `constants.emp`.
  - **BOOT** (`test name: boot_inside_a_region_with_its_own_tiles_shows_those_tiles`): boot with `Boot_At` at the showcase row's centre-reachable point; at the first `GameState_OJZScroll_Update` read VRAM `[BG_TILE_BASE_VRAM, +len)` and assert it equals the blob; assert `BG_Tiles_Current` equals the row's `bg_tiles`; assert the Plane B nametable equals the showcase layout's window.
  - **WARP** (`warp_into_a_region_with_its_own_tiles_uploads_them_before_the_first_update`): boot in an act-default row, write the warp mailbox to the showcase row, tick until `Debug_Warp_Consume` has run, same three assertions.
  - Wire `bg_switch` into `tools/effects_gates.py` beside `bg_wipe`.
  - Run: both legs RED on the current tree (the sync path does not load region tiles yet). Show the output. This red is structural, not a mutation; the mutation red comes in Step 8.
- [ ] **Step 7: Engine.** Factor `BG_UploadTiles` out of `BG_Init`'s `.tile_copy` block (guards verbatim; the `with z80_stopped` stays at the `BG_Init` call site). `BG_Init` then seeds: `BG_Tiles_Current = Act.act_bg_tiles`, `BG_Tiles_Target = 0`, `BG_Tiles_Offset = 0`, `BG_Bands_Hold = 0`. In `Section_RedrawPlanes`, after `Region_Resolve` gives `a0`, resolve the effective tiles (`rg_bg_tiles`, else `Act.act_bg_tiles`) and, inside the mask and the posture span, BEFORE the nametable blit:
  ```
          movea.l Region.rg_bg_tiles(a0), a1      // (after the a0 == 0 test)
          cmpa.w  #0, a1
          bne     .plb_tiles_eff
          movea.l Current_Act_Ptr, a2
          movea.l Act.act_bg_tiles(a2), a1
      .plb_tiles_eff:
          cmpa.l  BG_Tiles_Current, a1            // (BG_Tiles_Current).w
          beq     .plb_tiles_ok                   // VRAM already holds this blob
          move.l  a1, BG_Tiles_Current            // written before the copy consumes a1
          jbsr    BG_UploadTiles                  // tiles FIRST: the nametable below references them
      .plb_tiles_ok:
  ```
  (Registers to be re-checked against the routine's live usage at that point; `a0` must survive for the layout half.) The async-cancel half of the sync path is Task 5, because the async path does not exist yet.
- [ ] **Step 8: Verify, then prove the legs can fail by mutation.** Build DEBUG; run `python3 tools/bg_switch_gate.py --rom s4.debug.bin --lst s4.debug.lst`: BOOT and WARP PASS. Commit. Mutation: replace `jbsr BG_UploadTiles` in `Section_RedrawPlanes` with nothing (quote the edited lines back from disk), rebuild, run: both legs RED. Restore with `git show HEAD:engine/level/section.emp > engine/level/section.emp`, rebuild, confirm green. Run the full `effects_gates.py`; report totals and exit code.
- [ ] **Step 9: Docs + commit.** ENGINE_ARCHITECTURE §2.4: tiles are resolved per region; the synchronous path loads tiles then layout. DEFERRED_WORK: BG-BOOT-REGION-BLIT gets an update (route 1 stands; boot into a region with its own tiles is correct via `Section_RedrawPlanes`, at the cost of a second tile upload with the display off); book **REGION-BG-RESPAWN-CONTRACT** (any respawn must set `Section_Plane_Dirty`) and **REGION-BG-TILES-AUTHORING** (the `layoutRef` lowering plus a contract tiles key, cross-repo, C11). Note in the commit body that the DEBUG ROM's walked crossing into the showcase is KNOWN WRONG until Task 4 (the wipe repaints its layout over act tiles); the parcel lands whole.

### Task 3: The overwrite transport (chunked ROM-to-VRAM through the Deferrable queue)

**Files:**
- Modify: `engine/level/bg.emp` (`BG_Stream_Update`, new constants)
- Modify: `engine/system/dma_queue.emp` (AMENDED: `DMA_Deferrable_DestPending` and, for Task 5, `DMA_Deferrable_DropDest`, plus the runtime destination decode and its comptime pin against `vdp_comm_addr`)
- Modify: `games/sonic4/config/constants.emp` or the nearest game-side home of the DPLC peaks (AMENDED: the full chunk-fit `ensure`, C3)
- Modify: `tools/bg_switch_gate.py` (legs TRANSPORT and TRAFFIC)

**Interfaces:**
- Consumes: Task 1 RAM cells; `QueueDMA_Deferrable (d1: u32 src, d2: u16 dest, d3: u16 len) clobbers(d0-d4/a1-a2) out(carry: dropped)`; `DMA_Deferrable`, `DMA_Deferrable_Slot`.
- Produces: `pub const BG_OVERWRITE_CHUNK_BYTES`; `pub proc DMA_Deferrable_DestPending (d1: u16 lo, d2: u16 hi_exclusive) clobbers(d0/a0-a1) out(zero: none_pending)` (Z SET = no queued Deferrable entry has a destination in `[lo, hi)`); the invariant "`BG_Tiles_Current` becomes the target only on a main-loop frame that finds no arena-destined Deferrable entry after the final chunk was enqueued" (AMENDED from "queue empty", item 3); `BG_Tiles_Current == 0` means VRAM holds a partial blob.

- [ ] **Step 1: Research.**
  - Producers (AMENDED): re-run the producer enumeration of item 3 at the implementation revision (the controller asked for it to be re-derived, not trusted); include macros and templates that splice a `QueueDMA_*` call, and any `jsr (aN)` whose target table could hold a queue entry point. For each Deferrable producer record its destination range (from `vram.toml` regions) and its per-frame peak bytes and entries.
  - Destination decode: `engine/vdp.emp` `vdp_comm_reg` (the in-place encoder the queue core uses at `.finish_entry`, `clr=false`) and `vdp_comm_addr` (the comptime inverse). The runtime decode reads `DMAEntry.Command` and must invert exactly what `.finish_entry` and the `.split` tail wrote; pin it with `ensure(vdp_comm_addr(vdp_comm(A, VdpTarget.Vram, VdpOp.Dma)) == A)` for A at the arena's first byte, its last tile, and one address on each side.
  - Engine: `engine/system/dma_queue.emp` (`.transfer` core: 128 KB split needs two slots, `DMA_ENQ_BYTE_CAP` per frame, source must be even), `engine/system/vblank.emp` (drain order, the plane-drain and Critical charges, and whether `VInt_Lag` drains the Deferrable queue at all, which changes C2's frame count but not its soundness), `engine/system/buffers.emp` (each static Critical entry's length, to derive the Critical peak as a named constant rather than a remembered 1760).
  - References: S3K `Process_Kos_Module_Queue` (sonic3k.asm:2725-2790; one $1000-byte module DMA per completed module, the next module queued only on a later call) is the one-outstanding-chunk shape C2 adopts. Batman & Robin's budgeted upload handler `$7682` (`interrupts.asm:624-678`) queues as many tiles as the per-frame budget allows and parks the script until done: the "wait for completion" half. S.C.E. module queue (`Kosinski Plus Moduled Decompression.asm:55-116`) is the same S3K shape and confirms nothing new.
- [ ] **Step 2a: Leg TRAFFIC first** (AMENDED; `the_overwrite_completes_while_another_producer_enqueues_a_deferrable_entry_every_frame`). A deterministic synthetic producer, chosen over a real spindash because DEBUG free flight is the gate's only reliable way across an edge and a spindash needs grounded physics: at the top of every tick (`GameState_OJZScroll_Update`, main loop, so no VBlank is mid-drain) the gate appends ONE well-formed `DMAEntry` at `DMA_Deferrable_Slot` and advances the slot by `sizeof(DMAEntry)`: 32 B from a fixed even ROM address to the map's free tile (`vram.toml`: "THE MAP HAS ONE FREE TILE LEFT (959)"; the gate reads the generated VRAM map and is COULD NOT RUN if 959 is no longer free). The entry bytes are built from the `DMAEntry` layout and `engine/vdp.emp`'s encoding, parsed, not typed. Positive control first: with no crossing, the appended entry drains (slot back at base on the next tick) and VRAM tile 959 equals the source bytes. Then cross into the showcase with the producer running every tick and assert completion (`BG_Tiles_Current` == showcase blob, VRAM equals the blob) within `ceil(len / CHUNK) + 2` ticks plus the derived slack of one 32 B entry per frame. A timeout is FAIL. **This leg must be RED against the draft's C2** (global queue-empty), proven in Step 5.
- [ ] **Step 2: Leg TRANSPORT first** (`crossing_into_a_region_with_its_own_tiles_uploads_its_whole_blob_in_bounded_frames`). Boot in the act-default neighbour, hold the button across the edge; every tick record `BG_Tiles_Target`, `BG_Tiles_Offset`, `BG_Tiles_Current`, the Deferrable queue's entries (decoded destinations), and VRAM `[BG_TILE_BASE_VRAM, +len)`. Assert: target armed on the crossing tick; offset advances by exactly `BG_OVERWRITE_CHUNK_BYTES` (last chunk the remainder) on each tick that enqueues; no tick enqueues while an arena-destined entry is still queued (one outstanding chunk); `BG_Tiles_Current` becomes the blob pointer; at that tick VRAM equals the blob; completion within `ceil(len / CHUNK) + 2` ticks with no starvation (bound derived from the parsed constant). Run on the Task 2 tree: RED (nothing arms). Show it.
- [ ] **Step 3: Implement** at the top of `BG_Stream_Update`, after the `Region_Current` null test and BEFORE the `max_top` arithmetic (so `d3/d6/d7` below are unaffected), preserving `a0`:
  ```
          // ================= THE TILE OVERWRITE (region bg switch) =================
          movea.l Region.rg_bg_tiles(a0), a1
          cmpa.w  #0, a1
          bne     .ow_eff
          movea.l Current_Act_Ptr, a2
          movea.l Act.act_bg_tiles(a2), a1
      .ow_eff:
          cmpa.l  BG_Tiles_Current, a1
          beq     .tiles_settled                  // VRAM holds this blob: the common case
          cmpa.l  BG_Tiles_Target, a1
          beq     .ow_spend
          // ---- ARM or RETARGET (C8) ----
          move.l  a1, BG_Tiles_Target
          clr.l   BG_Tiles_Current                // VRAM is now a partial blob
          clr.w   BG_Tiles_Offset
      .ow_spend:
          move.w  (a1), d3                        // blob length in bytes
          cmpi.w  #BG_TILE_CAPACITY_BYTES, d3
          bls     .ow_len_ok
          move.w  #BG_TILE_CAPACITY_BYTES, d3     // runtime clamp (C12)
      .ow_len_ok:
          andi.w  #$FFFC, d3                      // longword-granular, as BG_Init
          movem.l d3/a0-a1, -(sp)                 // movem leaves CCR alone on the restore
          move.w  #BG_TILE_BASE_VRAM, d1
          move.w  #BG_TILE_BASE_VRAM + BG_TILE_CAPACITY_BYTES, d2
          jbsr    DMA_Deferrable_DestPending      // Z SET = nothing queued writes the arena (C2, AMENDED)
          movem.l (sp)+, d3/a0-a1
          bne     .ow_wait                        // one outstanding chunk; band DMAs and split halves drained too
          move.w  BG_Tiles_Offset, d0
          cmp.w   d3, d0
          bhs     .ow_complete                    // all enqueued AND none of the arena's writes remain queued
          sub.w   d0, d3                          // bytes left
          cmpi.w  #BG_OVERWRITE_CHUNK_BYTES, d3
          bls     .ow_len_chunk
          move.w  #BG_OVERWRITE_CHUNK_BYTES, d3
      .ow_len_chunk:
          moveq   #0, d1
          move.w  d0, d1
          addq.l  #2, d1
          add.l   a1, d1                          // src = blob + 2 + offset
          move.w  d0, d2
          addi.w  #BG_TILE_BASE_VRAM, d2          // dest
          move.w  d3, -(sp)
          movem.l a0, -(sp)                       // QueueDMA clobbers a1-a2 only; keep a0 explicit anyway
          jbsr    QueueDMA_Deferrable
          movem.l (sp)+, a0
          move.w  (sp)+, d3
          bcs     .ow_wait                        // queue full or byte cap: retry next frame
          add.w   d3, BG_Tiles_Offset
      .ow_wait:
          rts                                     // Task 4 turns this into the gating point
      .ow_complete:
          move.l  BG_Tiles_Target, BG_Tiles_Current
          clr.l   BG_Tiles_Target
      .tiles_settled:
          // ... the existing max_top / wipe / stream code, unchanged in this task
  ```
  (The `movem`/stack shape is a sketch: re-derive against `QueueDMA_Deferrable`'s declared clobbers and the proc's own `clobbers(d0-d7/a0-a2)`; the sigil contract checker is the authority.) Add, beside the wipe budget block:
  ```
  pub const BG_OVERWRITE_CHUNK_BYTES = 64 * 32      // one 64-tile run
  ensure(BG_OVERWRITE_CHUNK_BYTES % 4 == 0 && BG_OVERWRITE_CHUNK_BYTES >= 32, "...")
  ensure(BG_OVERWRITE_CHUNK_BYTES <= DMA_BUDGET_NTSC - (FG_PEAK_BYTES + BG_PEAK_BYTES) - DMA_CRITICAL_PEAK_BYTES, "...")
  ensure(BG_TILE_BASE_VRAM + BG_TILE_CAPACITY_BYTES <= $FFFF, "dest is a word ...")
  ```
  `DMA_CRITICAL_PEAK_BYTES` is derived in Step 1 from the static entries' sizes and declared where those sizes live, with its own `ensure` against them. AMENDED (C3): the engine-side `ensure` above is the necessary half only. The game adds the sufficient half where the DPLC data is visible: `BG_OVERWRITE_CHUNK_BYTES <= DMA_BUDGET_NTSC - (engine plane peak) - DMA_CRITICAL_PEAK_BYTES - (player Important DPLC peak) - (insta-shield + spindash-dust Deferrable DPLC peaks, dplc_peak_tiles x TILE_SIZE) - WATERLINE_DST_BYTES`, plus `ensure`s that every other Deferrable producer's `vram.toml` region lies outside `[BG_TILE_BASE_VRAM, BG_TILE_BASE_VRAM + BG_TILE_CAPACITY*32)`, which is what C2's boundedness argument rests on. If the sum cannot hold 2048, lower the chunk (a derived consequence of the accepted C3, reported, not a re-opened call), or STOP and report if it cannot hold even 32.
  `DMA_Deferrable_DestPending` walks `[DMA_Deferrable, DMA_Deferrable_Slot)` at `sizeof(DMAEntry)`, decodes each `Command`, and returns on the first destination in range: at most `DMA_DEFERRABLE_SLOTS` = 12 iterations a frame, only while an overwrite is in flight. Walking from the main loop without masking is safe because `Drain_Budgeted_Queue` runs only in VBlank and only REMOVES entries (compacting toward the base): a VBlank mid-walk can turn a "pending" answer into a one-frame-late "not pending", never the reverse. Derive that at the proc rather than trusting this sentence (a compaction that moves an unread entry below the walk cursor must not be able to hide an arena entry that is still queued; if it can, mask the walk). Under DEBUG, `raise_error` if `d1` is odd (the queue drops bit 0; `page_in.emp`'s raw-page precedent).
  In THIS task `.ow_wait` returns before the wipe and the streamer, which already gives the gating; Task 4 adds the arm-time state (C6, C7), the band hold, and the legs that prove the ordering.
- [ ] **Step 4: Verify.** Build both shapes. TRANSPORT PASS; BOOT, WARP PASS; `effects_gates.py` full run, totals and exit code. Commit.
- [ ] **Step 5: Mutation reds.** (a) Delete the `bne .ow_wait` after `DMA_Deferrable_DestPending` (quote it back), rebuild: TRANSPORT must go RED on its "one outstanding chunk" assertion. (b) The DRAFT's C2: replace the `DMA_Deferrable_DestPending` test with `cmpi.w #DMA_Deferrable, DMA_Deferrable_Slot` (global queue-empty), rebuild: TRAFFIC must go RED (timeout, the overwrite never completes) while TRANSPORT stays green, which is the soft-lock the controller named. (c) Make `DMA_Deferrable_DestPending`'s range test always "not in range": TRANSPORT RED. If any stays green, the leg is not observing what it claims: fix the leg first. Restore each from `git show HEAD:<path>`, rebuild, green.
- [ ] **Step 6: Docs + commit.** ENGINE_ARCHITECTURE §2.4 "The tile overwrite": queue, chunk, completion rule, budget derivation. Commit body: the VBlank drain order finding (item 4), the corrected producer set (item 3) and C1-C4.

### Task 4: The ordering (repaint waits for the overwrite; streamer gated; re-entrancy)

**Files:**
- Modify: `engine/level/bg.emp`
- Modify: `tools/bg_switch_gate.py` (legs ORDER, ORDER-STARVED, STREAMER, REENTRANT, CONTROL)

**Interfaces:**
- Consumes: Task 3's trackers and completion invariant; C13's `DMA_Budget_Default` poke.
- Produces: at arm, `BG_Plane_Layout = 0` and `BG_Wipe_Cursor = 0`; the invariant "no Plane B row holds a word of the new layout on any tick where VRAM does not hold the new blob".

- [ ] **Step 1: Research.** Re-read the wipe arm (`bg.emp:614-692`) to confirm a zero `BG_Plane_Layout` re-arms a full 64-row sweep with the window snapped to `want_top`, and that nothing else reads `BG_Plane_Layout` (the `Replay_Hash` note in `engine/ram.emp:618`). References: S3K `HCZ1BGE_DoTransition` waits on `Kos_modules_left` (the tile counter) before the layout switch, and ICZ waits on `Kos_decomp_queue_count` only (reconciliation R1): the first is the rule this task enforces, the second is the bug the ORDER-STARVED leg reproduces by mutation. S3K background events stop `DrawBGAsYouMove`-style streaming while a redraw state machine owns Plane B (slice 01 Q2 step 9 and bg.emp's own SSZ1/FBZ notes); that is the precedent for C7.
- [ ] **Step 2: Legs first**, on the Task 3 tree:
  - **ORDER** (`no_plane_b_row_shows_the_new_layout_before_vram_holds_the_new_tiles`): horizontal crossing; every tick read Plane B and the tile block; for each plane row whose 64 words equal a row of the showcase layout's current window (and differ from the act layout's same row, so a row identical in both pictures is not counted), assert the tile block equals the showcase blob. Also assert `BG_Wipe_Cursor` first becomes nonzero strictly after the tick where `BG_Tiles_Current` became the blob, never on it.
  - **ORDER-STARVED** (same assertion, `...even_when_the_last_chunk_is_held_in_the_queue`): at the tick `BG_Tiles_Offset` reaches the blob length, write `DMA_Budget_Default` to `BG_OVERWRITE_CHUNK_BYTES - 2` for `WIPE_FRAMES` ticks (C13), then restore. During the hold assert `BG_Tiles_Current == 0`, `BG_Wipe_Cursor == 0`, and the Plane B nametable is byte-identical to the tick before the hold began.
  - **STREAMER** (`a_vertical_move_during_the_overwrite_paints_no_new_layout_row`): vertical crossing (fly down into the showcase row from its act-default neighbour above or below) with the ORDER-STARVED hold, so the window wants to move while tiles are pending; same per-tick assertion as ORDER.
  - **REENTRANT** (`reversing_across_the_edge_mid_overwrite_retargets_and_settles_on_the_act_tiles`): cross in, hold the budget starved, cross back out before completion; release the budget; assert `BG_Tiles_Target` became `Act.act_bg_tiles` within one tick of the reverse crossing, the run settles (`BG_Tiles_Current == act tiles`, `BG_Wipe_Cursor == 0`) within `ceil(len/CHUNK) + 2 + WIPE_FRAMES + 2` ticks of the release, VRAM tile block equals the act blob, and Plane B equals the act layout. A timeout is FAIL (lock-up), not COULD NOT RUN.
  - **CONTROL** (`a_crossing_between_two_act_default_rows_arms_no_overwrite`): `BG_Tiles_Target` stays 0 and `BG_Tiles_Offset` stays 0 across the crossing.
  Run on the Task 3 tree. Expected: ORDER and ORDER-STARVED may already PASS (Task 3's `.ow_wait` returns early), and STREAMER/REENTRANT's final state may FAIL because the arm does not force the repaint (C6). Record exactly which, with output. Whatever is green here must be proven able to fail in Step 5.
- [ ] **Step 3: Implement** at the ARM label from Task 3, after `clr.w BG_Tiles_Offset`:
  ```
          clr.l   BG_Plane_Layout                 // C6: the repaint MUST follow, whatever the layout pointer
          clr.w   BG_Wipe_Cursor                  // C7: cancel an in-flight sweep (cursor + row, one word)
  ```
  and a comment block at `.ow_wait` stating that returning here is what suspends the wipe AND the streamer, and that moving this `rts` below the wipe is exactly the Icecap failure.
- [ ] **Step 4: Verify.** Build both shapes; all `bg_switch` legs PASS; `bg_wipe`, `bg_window` PASS; full `effects_gates.py` totals and exit code. Commit.
- [ ] **Step 5: Mutation reds, one at a time, each quoted from disk, each restored from `git show HEAD:engine/level/bg.emp`:**
  - M1 (the Icecap mutation): at `.ow_spend`, when `d0 >= d3` complete WITHOUT the arena-pending test (move the `DMA_Deferrable_DestPending` / `bne .ow_wait` pair below the `bhs .ow_complete`). Expected RED: ORDER-STARVED (wipe arms while the last chunk is held).
  - M2: replace `rts` at `.ow_wait` with `jbra .tiles_settled` (wipe and streamer run during the overwrite). Expected RED: ORDER and STREAMER.
  - M3: delete `clr.l BG_Plane_Layout` at arm. Expected RED: STREAMER's settled-state assertion (the window went stale while the streamer was suspended, and without the forced sweep nothing re-primes it), or REENTRANT's (a reverse crossing while the forward sweep was in flight leaves `BG_Plane_Layout` naming the act layout although part of the plane still holds showcase rows, so the reverse arm never fires). If M3 stays green on every leg, the legs cannot see C6's reason to exist: add a leg that arms the overwrite while a sweep is in flight (starve the budget immediately after the forward sweep arms, then cross back) and assert the settled plane equals the act layout row for row. Region rows are ROM, so a tiles-only switch cannot be made by poking; do not add a third DEBUG row just for this.
  - M4: delete the retarget compare (`cmpa.l BG_Tiles_Target, a1 / beq .ow_spend`) so every frame re-arms. Expected RED: TRANSPORT (never completes).
  If any mutation stays green, stop and fix the leg before continuing.
- [ ] **Step 6: Docs + commit.** ENGINE_ARCHITECTURE §2.4: the sequence (overwrite, completion observed, forced sweep), C6-C8, and the explicit statement "the wipe cannot arm while `BG_Tiles_Current` differs from the region's effective blob". DEFERRED_WORK: book **REGION-BG-COVER-WARNING** (finding 3 / v1 D4's check, input from Task 7) and **REGION-BG-CAMERA-HOLD** (C14, owner option). Commit body lists the four mutations and their reds.

### Task 5: The synchronous path cancels an asynchronous overwrite in flight

**Files:**
- Modify: `engine/level/section.emp` (`Section_RedrawPlanes`)
- Modify: `engine/system/dma_queue.emp` (`DMA_Deferrable_DropDest`, AMENDED C9)
- Modify: `tools/bg_switch_gate.py` (leg WARP-MID)

**Interfaces:**
- Consumes: Tasks 2-4.
- Produces: `pub proc DMA_Deferrable_DropDest (d1: u16 lo, d2: u16 hi_exclusive) clobbers(d0/a0-a2)` (removes every queued Deferrable entry whose destination is in range and keeps the rest in order; the caller holds the SR mask); after any `Section_RedrawPlanes`, `BG_Tiles_Target == 0`, `BG_Tiles_Offset == 0`, no arena-destined Deferrable entry queued, every non-arena entry that was queued still queued in order, `BgAnim_LastStep` all $FFFF.

- [ ] **Step 1: Research.** AMENDED (C9): the draft reset the whole queue. Confirm the compacting drop is safe inside the SR mask (no VBlank can drain mid-walk), and record what the selective drop keeps and why: insta-shield and spindash-dust DPLC entries (item 3) are kept because `perform_dplc` commits `prev_frame` on acceptance and does not re-send an accepted frame until `mapping_frame` changes, so dropping them would show stale sprite tiles for up to one animation frame; waterline entries are kept because `Waterline_Art_LastRow` is committed on acceptance too. Only arena-destined entries (overwrite chunks, band DMAs) are dropped, and bands re-send via the `BgAnim_LastStep` reset. S3K's act reload clears `Kos` queues implicitly by running only after they drain; Batman & Robin's checkpoint variant uses the immediate handlers instead of the budgeted ones (slice 04), which is the same "synchronous path replaces the asynchronous one" shape.
- [ ] **Step 2: Leg WARP-MID first** (`a_warp_during_an_overwrite_leaves_vram_holding_the_warp_targets_tiles`): cross into the showcase with the budget starved so a chunk is held; warp to an act-default row; release the budget; tick `ceil(len/CHUNK) + 4`; assert tile block equals the ACT blob (a stale showcase chunk landing after the synchronous upload would break it), `BG_Tiles_Current == act tiles`, `BG_Tiles_Target == 0`. AMENDED: run TRAFFIC's synthetic producer during the hold, so at the warp tick at least one NON-arena entry is queued; assert it is still queued, in order, immediately after the warp, and that VRAM tile 959 receives its bytes once the budget is released (the cancel must not drop it). Run on the Task 4 tree: expected RED on the tile-block assertion. The mechanism: Task 2's compare sees `BG_Tiles_Current == 0`, uploads the act blob synchronously and sets `Current` to it; the next `BG_Stream_Update` finds the effective blob equal to `Current` and never touches the queue; the held showcase chunk is still in the Deferrable queue and lands over the act tiles when the budget is released, while every tracker says VRAM holds the act blob. Show it.
- [ ] **Step 3: Implement** in `Section_RedrawPlanes`, inside the mask, unconditionally after the tiles block from Task 2:
  ```
          clr.l   BG_Tiles_Target
          clr.w   BG_Tiles_Offset
          move.w  #BG_TILE_BASE_VRAM, d1
          move.w  #BG_TILE_BASE_VRAM + BG_TILE_CAPACITY_BYTES, d2
          jbsr    DMA_Deferrable_DropDest         // drop ONLY arena writes: chunks and band DMAs (C9, AMENDED)
          moveq   #-1, d0
          move.l  d0, BgAnim_LastStep
          move.l  d0, BgAnim_LastStep + 4
  ```
  (the band hold recompute joins in Task 6).
- [ ] **Step 4: Verify.** WARP-MID PASS, all other legs PASS; full `effects_gates.py`. Commit.
- [ ] **Step 5: Mutation reds.** (a) Delete the `jbsr DMA_Deferrable_DropDest` (quote it): WARP-MID RED on the tile block. (b) Replace it with the draft's whole-queue reset `move.w #DMA_Deferrable, DMA_Deferrable_Slot`: WARP-MID RED on the "non-arena entry still queued" assertion. Restore each from HEAD, green.
- [ ] **Step 6: Docs + commit.** ENGINE_ARCHITECTURE §2.4 sync-path paragraph; commit body with the waterline finding from Step 1 either way.

### Task 6: BgAnim bands are safe across a region switch

**Files:**
- Modify: `engine/level/bg_anim.emp` (`BgAnim_Update`), `engine/level/bg.emp` (hold set/clear), `engine/level/section.emp` (hold recompute)
- Modify: `tools/bg_switch_gate.py` (leg BANDS)

**Interfaces:**
- Consumes: `BgAnim_SetTable (a0)` (DEBUG) to point the system at a live band table; `BgAnim_LastStep`.
- Produces: `BG_Bands_Hold != 0` whenever `BG_Tiles_Current != Act.act_bg_tiles`.

- [ ] **Step 1: Research.** Find a live DEBUG band table the lab already selects (`games/sonic4/test/ojz_scroll_test.emp` ~:2497-2740 and `ojz_bg_anim_act1` views) and its slot range. Check the `bg_anim_port` standalone lowering: a new RAM symbol read in `bg_anim.emp` is a new cross-seam NAME, and the memory "Zero-byte says nothing about NAMES" says `*_port` tests can break while all shapes build green; find where that port test runs from aeon's side (if it lives only in sigil, the step records that it was not run and why). S3K `AnimateTiles_*` routines are gated per zone and act by the `Animated_tiles` pointer being swapped at act transitions (`AIZ` fire refresh, slice 01 T3): the precedent for tying band activity to which art is resident.
- [ ] **Step 2: Leg BANDS first** (`no_band_write_lands_in_the_tile_block_while_a_region_with_its_own_tiles_is_resident`): boot in the act-default neighbour, point the lab at the live band table, confirm a band write happens (positive control: the band slots change between two ticks with the camera moving; if they never change, COULD NOT RUN), cross into the showcase and let it settle, keep the camera moving for `WIPE_FRAMES` ticks, assert the tile block stays equal to the showcase blob every tick; cross back out, settle, assert band slots change again (resync). Run on the Task 5 tree: RED (bands scribble over the front slots).
- [ ] **Step 3: Implement.** `BgAnim_Update`, after the `movem` push: `tst.b BG_Bands_Hold / bne .exit`. In `bg.emp`: at ARM `st BG_Bands_Hold`; at `.ow_complete`, if `BG_Tiles_Current == Act.act_bg_tiles` then `clr.b BG_Bands_Hold` and set both `BgAnim_LastStep` longs to -1. In `Section_RedrawPlanes` (Task 5's block): `sne`-style recompute of the hold from `BG_Tiles_Current != Act.act_bg_tiles`.
- [ ] **Step 4: Verify.** BANDS PASS, all legs PASS. **Required by the effects ritual:** `python3 tools/effects_gates.py --rom s4.debug.bin --lst s4.debug.lst`, totals and exit code pasted. Commit.
- [ ] **Step 5: Mutation reds.** M5: delete the `BgAnim_Update` early exit: BANDS RED (scribble). M6: delete the `BgAnim_LastStep` reset at completion: BANDS RED on resync (bands resume only when their step next changes; if the leg's camera motion always changes the step, it stays green, so the resync assertion must hold the camera still after settling and require the band slots to hold the CURRENT phase's art, derived from the table's bank pointers and step). Restore each from HEAD.
- [ ] **Step 6: Docs + commit.** ENGINE_ARCHITECTURE §2.4 bands paragraph (C10). DEFERRED_WORK: book **REGION-BG-PER-REGION-BANDS** (release table selector + importer emission + band table on `Region`), with the reason it is not built: no release content, and it needs the release RAM word the review named.

### Task 7: M-A, the measured cost of a switch

**Files:**
- Create: `docs/research/megaact-bg-streaming/region-bg-switch-cost.md` (NOT an `08-*` name)
- Modify: `tools/bg_switch_gate.py` (a `--measure` mode printing per-tick timelines; no new assertions)

- [ ] **Step 1: Research.** Reuse the gate's routes. Decide whether the STRESS eviction fixture can run a crossing with FG streaming active; `build.sh` refuses `STRESS_*` shapes on the canonical path, so check whether a named sigil profile or the existing stress lane can build it. If it cannot, record COULD NOT RUN for the contention half and book it.
- [ ] **Step 2: Measure** on `s4.debug.bin` (and on the release-equivalent timing only if a release ROM can reach the showcase, which it cannot: the row is DEBUG-only, so say so): for the horizontal route and the vertical route at `PLAYER_DEBUG_FLY_SPEED`, report ticks from crossing to `BG_Tiles_Current` set, to the visible rows repainted (`ceil(BG_SCREEN_ROWS / BG_WIPE_ROWS_PER_FRAME)` after arm, measured, not assumed), and to the sweep retiring. Every figure with its unit (logic ticks; state whether lag frames occurred by reading `Frame_Counter` against ticks). Derive the cover length each implies at `CAM_MAX_X_STEP` and `CAM_MAX_Y_STEP` plus one screen, as the input REGION-BG-COVER-WARNING needs.
- [ ] **Step 3: TAG for the controller (human eye):** a boot/route recipe (`Boot_At` coordinates and held button) that shows the switch on the DEBUG ROM, to judge the look of the uncovered transient. Per the controller's C7/C8 ruling the recipe must say WHERE the accepted garbage shows: during the overwrite ticks measured in Step 2 (crossing to `BG_Tiles_Current` set), the visible Plane B rows show the old layout's words over partly overwritten tiles on both routes, and on the VERTICAL route the paused streamer also leaves rows entering at the top or bottom edge showing the wrong map row. Give the tick range and the screen band (top or bottom rows, from the measured window movement), so the owner knows how much foreground cover that crossing needs. The look of the colonnade art in this region is the owner's call.
- [ ] **Step 4: Commit** the doc and the `--measure` mode, figures in the body.

### Task 8: Landing evidence

- [ ] **Step 1:** Clear `tools/__pycache__`. With both SIGIL exports, run `./tools/landing_build.sh` in the foreground if it fits the timeout; otherwise copy it to a run-unique scratchpad path, `nohup` it with a `finished=` marker and poll the log. Report the exit code and the `finished=<n>` stamp, and the pytest totals it prints (aggregate, not a tail).
- [ ] **Step 2:** `python3 tools/effects_gates.py --rom s4.debug.bin --lst s4.debug.lst`: totals and exit code.
- [ ] **Step 3:** Confirm the release ROM's Plane B behaviour is unchanged where it must be: every release row has `rg_bg_tiles = 0`, so the overwrite arm compares equal on every frame. State it as the reason, and note the release ROM bytes DID move (struct size, RAM cells, new code).
- [ ] **Step 4:** Final DEFERRED_WORK/ENGINE_ARCHITECTURE read-through for sentences this parcel made stale (grep for "never overwritten by section transitions" in §2.4 and "448 tiles" beside it, both already stale), commit, report tip SHA.

---

## Self-review

- **Spec coverage.** Full overwrite then repaint (Tasks 3-4); ordering structural with a red-capable gate (Task 4 ORDER-STARVED + M1); repaint reuses the step-6 wipe (Task 4 zeroes `BG_Plane_Layout`, the existing arm does the rest); palette untouched; per-region tiles in the data model (Task 1); transport (Task 3); both other Plane B writers gated (Task 4 streamer, Tasks 2 and 5 redraw); boot, warp (Task 2), respawn booked; re-entrancy (Task 4, C8); bands (Task 6, C10); test content (Task 2, C11); every review finding mapped above.
- **Placeholders.** `DMA_CRITICAL_PEAK_BYTES` and the showcase rectangle are deliberately derived in their tasks' research steps, with the derivation named; they are not left open.
- **Name consistency.** `BG_Tiles_Current`, `BG_Tiles_Target`, `BG_Tiles_Offset`, `BG_Bands_Hold`, `BG_UploadTiles`, `BG_OVERWRITE_CHUNK_BYTES`, `rg_bg_tiles`, `DMA_Deferrable_DestPending`, `DMA_Deferrable_DropDest`, `tools/bg_switch_gate.py` are used identically in every task.
- **Amendment after controller review (item 3 was false).** C1's justification, C2, C3 and C9 re-decided; leg TRAFFIC (Task 3) and WARP-MID's survival assertion (Task 5) added so the corrected premise is graded rather than asserted. Controller rulings recorded: C3 accepted (2048 B, not charged to the act art budget), C7/C8 accepted under R3 with the Task 7 recipe naming where the garbage shows, OC-3/C14 stays booked.

---

## Execution record (phase 2)

Deviations from the plan text, each with its reason, and the red-first evidence per task. Mutations were applied on disk by a helper that quotes the edited lines, built `FAST=1 DEBUG=1` (exit 0 each; a first T3-a spelling that deleted the branch outright failed the build with `[call.flag-result-unused]`, left a stale ROM that read green, and was discarded), run against `tools/bg_switch_gate.py`, and restored with `git show HEAD:<path> > <path>`.

- **Task 2.** The showcase rectangle (C11b): x 1024..2047, y 2048..4095, carved from `sec3`; `ojz_cut_row` gained `was_x1`. Only `rebase_layout` was factored out of the injector: the library `_tiles.bin` is already the engine blob shape, so `pack_tile_blob` had nothing to do. `BG_UploadTiles` sits AFTER `BG_Init`: first in the file it renamed the `bg` section head and failed `[layout.undeclared-alignment]` (a sigil-side table keyed on head labels). Red first: BOOT + WARP, 6 failing assertions on the tree without the upload; mutation (upload removed): 2 failing.
- **Task 3.** CHUNK derived at **256 B**, not the accepted 2048 (see C3 as amended; `tools/test_bg_overwrite_chunk_budget.py`, residual 264 B). The chunk-fit check is that pytest rather than a game-side `ensure`: the inputs are module-local DPLC embeds in four game modules, and the pytest reuses `tools/dma_defer_headroom.py`'s own reader of `BuildStaticDMA`. Leg TRANSPORT_STARVED added because calm TRANSPORT cannot see the one-outstanding rule. Reds: T3-a (branch neutralised) TRANSPORT_STARVED 10 failing; T3-b (the draft's global queue-empty C2) TRAFFIC red, never completes, TRANSPORT green; T3-c (DestPending never "in range") TRANSPORT_STARVED 10 failing.
- **Task 4.** Legs ORDER, ORDER_STARVED, ORDER_VERTICAL, REENTRANT, CONTROL, POISON; all green on the task-3 engine (its `rts` already gated the wipe). Reds: **M1** (Icecap: complete on "all enqueued") ORDER_STARVED 2 failing: `BG_Tiles_Current` named while the last chunk was queued, cursor 60, 4 new-layout rows shown over the old tiles; ORDER green (calm). **M2** (`rts` -> `jbra .tiles_settled`) ORDER and ORDER_VERTICAL 4 failing (rows shown at the crossing tick; cursor armed 27 ticks before the tiles settled). **M3** (plane tracker not zeroed) POISON 1 failing: 40 of 64 rows never repainted. **M4** (no retarget compare) TRANSPORT never completes (offset stuck at 256). The streamer's suspension is ungraded (REGION-BG-STREAMER-SUSPENSION-UNGRADED).
