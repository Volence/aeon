# Sonic 3 & Knuckles and Sonic 2: mid-level art swaps

> **Research slice for MEGAACT-BG-STREAMING (2026-09-16).** This is the research agent's final report,
> extracted programmatically from its transcript and committed VERBATIM, never retyped: a report
> whose value is its `file:line` citations cannot be summarised without becoming the
> summary-of-a-summary this project was bitten by twice today. It is a LEAD for the design, not a
> finding the design may assume: every MEASURED claim is re-checkable at its citation.

---

S3K has a real precedent for swapping art in the middle of a level, but it doesn't solve your problem as posed. It never changes tiles while the camera is scrolling. Every one of these swaps happens with the camera pinned in a boss arena, and while it happens neither plane shows any tile being replaced. Zone to zone, S3K does a full reload with a fade to black, and so does Sonic 2.

I read everything below myself in `skdisasm/sonic3k.asm` (plus `Lockon S3/Screen Events.asm`) and `s2disasm/s2.asm`. I decompressed the AIZ and HCZ art with my own Kosinski decoder in the scratchpad; `sonic_hack/tools/kosdec` crashes on these files. The decoder is checked against the game's own load addresses: AIZ2's first tile set is $1FC tiles, which is exactly where the code loads the second set, and the same holds for HCZ at $11B tiles, $558 bytes of blocks and $A00 bytes of chunks. I didn't touch any repo.

## 1. Verdict

Mid-level art swaps exist in S3K, but only between two acts of the same zone, never between zones. They all follow one rule: **freeze the camera, keep the visible nametables pointing only at tiles outside the range being replaced, overwrite that range in place, then redraw.** Neither S3K nor S2 keeps two zones' art in VRAM at once.

- **AIZ1→AIZ2:** the fire enforces the rule. It is fully opaque at the moment the swap starts, it sits on high-priority Plane B tiles stored above the replaced range, and Plane A is wiped to tile 0 behind it.
- **HCZ1→2 and MGZ1→2:** level design enforces it. The swap waits for the post-boss results tally in a locked arena. For HCZ1 I measured that the arena's foreground uses only the art shared by both acts and covers the whole screen, so the background tiles that do change can't be seen.

So is the fire a corridor in disguise? Partly. The actual corridor is a **stopped camera**: a pause in time, not a stretch of level. The fire hides the Plane A wipe, the palette change and the layout change. For a showcase that scrolls continuously, S3K offers the ordering and the rule, not the "no pause" part.

## 2. Techniques

**T1. Idle-time decompression with a VBlank bookmark** (MEASURED)
- **Where:** `Process_Kos_Queue` is called before `Wait_VSync` in `LevelLoop` (7886–7887). `Set_Kos_Bookmark` (2818) redirects the interrupt's return address so the decode resumes later; `Restore_Kos_Bookmark` is at 2959.
- **Cost:** CPU that would otherwise be idle.
- **For aeon:** this is the same mechanism as your §9.7 decoder, so it's a confirmation, not something new.

**T2. Kosinski-moduled art queue, one module per DMA** (MEASURED)
- **Where:** `Queue_Kos_Module` (2667); `Process_Kos_Module_Queue_Init` (2693) splits the art into modules of $800 words ($1000 bytes, 128 tiles); `Process_Kos_Module_Queue` (2725–2790).
- **How:** the DMA only fires once the whole Kosinski queue is empty (`$$decompressionStarted`, 2744), then queues one `Add_To_DMA_Queue` (2769). Because chunks and blocks queue first, the order is always chunks → blocks → tile module 1 → DMA → module 2, and so on.
- **Cost:** at most 4 KB of tile art per frame, and only on frames where a module finishes.

**T3. AIZ fire transition** (MEASURED from code and data; timing INFERRED)
- **Where:** `AIZ1_AIZ2_Transition` / `AIZ1BGE_FireTransition` / `FireRefresh` / `Finish` (≈104628–104780), then `AIZ2BGE_FireRedraw` / `WaitFire` (≈105030–105100).
- **Cost:** 121 extra resident fire tiles at $500 for the whole act, a full plane redraw in each direction, and a camera lock.
- **For aeon:** needs a full-screen high-priority mask whose tiles live outside the pool being swapped, plus Plane A cleared to a transparent tile. Your separate BG pool actually makes "outside the replaced range" easier.
- The full step order is in answer Q2.

**T4. Same-zone swap of only the per-act set** (MEASURED)
- **Where:**
  - `HCZ1BGE_Normal` (≈105717–105740) replaces tiles from $11B, blocks from $558 and chunks from $A00. The code comment says "so as to not compromise current position".
  - `MGZ1BGE_Normal` (106283–106300) replaces from $252.
  - ICZ (110269) at $122 and LBZ (111217) at $19D: I only read the load line for those two.
- **Trigger:** `Events_fg_5`, set by `Obj_LevelResultsCreate` for every act 1 except AIZ and ICZ (62619).
- **The switch:** `HCZ1BGE_DoTransition` waits for `Kos_modules_left==0`, then `Load_Level`, `LoadSolids`, `LoadPalette_Immediate` (105771), subtracts $3600 from every X position, and runs `Reset_TileOffsetPositionActual`. **It does not redraw either plane.**
- **HCZ1 measurements:**
  - The arena lock is X=$3680, Y=$638 (`Obj_HCZMiniboss`, 139227–139260).
  - The visible foreground chunks go no higher than block $9D (below 171) and tile $109 (below $11B), so they use only the shared set.
  - On a 4-pixel sampling grid, **0 of 4,480** foreground pixels are transparent. My sanity spots elsewhere in HCZ1 gave 826–2,616 transparent.
  - The background tiles on screen do change: all 28 tiles of BG row 3 get new content when the HCZ2 set loads, but they are hidden.
  - HCZ2's first columns roughly copy HCZ1's arena (row 13 identical, chunk A0 matches 9A tile for tile), but not exactly: chunks A9/A4 and B4/AF differ in a few blocks.
- **For aeon:** the zone designs a spot where nothing that changes is visible. It depends on content, not on the engine.

**T5. Sonic 2 HTZ repaints tile pixels, not nametables** (MEASURED)
- **Where:** `Dynamic_HTZ` (s2.asm 85503–85640).
- **How:** 24 fixed tiles at $500 (`ArtTile_ArtUnc_HTZMountains`, s2.constants.asm 2401) are rewritten through 6 DMAs of 4 tiles each whenever the parallax step changes. 8 cloud tiles are rewritten every frame.
- **Cost:** 768 + 256 bytes per frame at most.
- **For aeon:** it's parallax, not a zone swap. It's only relevant as a precedent for fixed slots whose contents change.

## 3. Answers

**Q1. What art loads mid-level, when, and how is garbage avoided?**
- **AIZ1, earlier in the act** (MEASURED):
  - At camera X $1400, `loc_1C4D0` (38917–38923) swaps the intro art for the main-level art at tile $0BE and blocks +$268.
  - At X $2E00, `loc_1C5C6` (38989–38995) loads the fire art to $500 only once `Kos_modules_left==0`, well before the fire starts.
- **Other mid-level loads** (MEASURED): AIZ2 bombership art (39108–39116), LBZ2 Death Egg art (39513), SOZ/LRZ/DEZ second-set loads (113763, 115285, 118668). The rest of the ~120 `Queue_Kos_Module` calls are objects, cutscenes and title cards.
- **How garbage is avoided:** see T3 and T4.

**Q2. Order of operations**
- **AIZ** (MEASURED):
  1. Camera locked at X=$2F10 by the miniboss cutscene (`loc_68556`, ~136766–136770).
  2. The miniboss flees and sets `Events_fg_5` (136883).
  3. **Palette:** fire colours are written into line 4, entries 1–6. Per-column VScroll is switched on (`Special_V_int_routine=4`).
  4. The fire rises on Plane B. It is drawn from the AIZ1 background layout at X $1000 (`Draw_TileRow`, d1=$1000), and `AIZ1_FireRise` accelerates it to at most 10 px per frame.
  5. At background Y ≥ $190, AIZ2's chunks, both block sets, tile set 1 at $000 and tile set 2 at $1FC are all queued, plus the spikes/springs art list. A floor object is spawned to hold the player up.
  6. **Plane A is redrawn** from layout X $180, Y 0. That spot is chunk 0 (MEASURED in the layout), and chunk 0 resolves to tile 0 in both acts, so the plane is wiped. It goes 16 block rows at 2 per frame, 8 frames in total.
  7. Wait for `Kos_modules_left==0`, then `Load_Level`, `LoadSolids`, `LoadPalette_Immediate $B` (104743), **re-apply the fire colours**, shift all positions by −$2F00/−$80, lock the camera at X=$10, and set up a delayed redraw.
  8. `AIZ2BGE_FireRedraw` draws Plane A from AIZ2's layout while the fire keeps going.
  9. When background Y reaches $310: object art lists, enemy art, the final line-4 colours, `Camera_max_X=$6000` (105093, which releases the camera), then a **Plane B redraw** from AIZ2's background.
  10. Parallax: `PlainDeformation` runs throughout; `AIZ2_Deform` comes last.
- **HCZ/MGZ:** load art → wait → layout + solids + full palette (lines 2–4) and the position shift in a single frame → no redraw at all.

**Q3. VRAM during the handoff** (MEASURED)
- **Not both zones.** AIZ2 overwrites tiles $000–$2E8 in place. Only the 121 fire tiles at $500 (plus shared object and player art) span both acts. HCZ and MGZ keep their shared set and overwrite the per-act set.
- **The fire is a genuine mask:**
  - All 702 fire tile references are high priority; the arena's foreground is all low priority (2,816 references).
  - Scanning every pixel at X $1000–$1060, the fire is fully opaque for background Y from **$140 to $1E8**. The swap starts at **$190**.
  - The fire chunks use only tile 0 and tiles $500–$578.
  - Chunk BF is identical tile for tile in both acts; BD and BE are not.
- **INFERRED:** at up to 10 px per frame, the opaque window after the trigger is about 9 frames. I can't tell whether the tile uploads finish inside it. I also can't tell what gets drawn while the chunk table is AIZ2's but the block table is still AIZ1's (AIZ2's chunk BF points past the end of AIZ1's block table).
- **Camera:** locked in every case.

**Q4. Resident vs per-zone** (MEASURED, `sonic3k.constants.asm` 1086–1097, PLC lists at 176284 and 176630)
- **Resident:** Monitors $4C4, Explosion $5A0, StarPost $5E4, player 1 $680, player 2 $6A0, player 2 tails $6B0, rings $6BC, shields $79C, dash dust $7E0/$7F0. I didn't find the HUD slot.
- **Per zone:** level art starting at $000 (shared set, then per-act set), and $500–$59F, which is reused for zone objects (fire, HCZ geysers, CNZ teleporter) and title cards and results.
- S3K's plane size is 64×32 cells (line 1361).

**Q5. DMA bandwidth** (MEASURED)
- **Level VBlank** (`VInt_8`, 700–790), every frame: full CRAM ($80), H-scroll ($380), sprite table ($280), the DMA queue (763, 18 slots), `SpecialVInt_Function` (for AIZ, 80 bytes of VScroll), and the nametable buffer `VInt_DrawLevel` (766, buffer $480 bytes).
- **Nemesis art lists:** `Process_Nem_Queue_2` does 3 patterns per frame (2177), about 96 bytes, called from `Do_Updates`.
- **Kosinski modules:** at most $1000 bytes on frames where a module completes.
- **Plane redraws:** 2 block rows per frame is about 512 bytes of nametable, so a full plane takes 8 frames.
- Big loads are spread by modules plus idle-time decoding. There is no fixed per-frame budget beyond that.

**Q6. Palettes** (MEASURED)
- `LoadPalette_Immediate` writes straight into `Normal_palette`. The pointers for $B, $D and $F all target lines 2–4, $60 bytes (`Levels/Misc/Palette pointers.asm`), and VBlank uploads CRAM every frame, so the change shows up on the next frame.
- The player's line 1 is never touched.
- AIZ re-applies the fire colours right after the full load, then sets its final colours when the fire subsides.
- Zone to zone, `Level` fades to black (7523).

**Q7. One pattern set for foreground and background, or two?** One address space in both games, but little actual sharing. Counts below are flip-deduplicated, exclude blank tiles, and count only tiles the layout references (MEASURED):

| Area | Foreground | Background | Shared | BG-only |
|---|---|---|---|---|
| AIZ1 (jungle BG, cols 0–3 × rows 0–6) | 594 | 141 | 4 | 137 |
| AIZ2 (BG without fire) | 622 | 119 | 15 | 104 |
| AIZ2 fire (in its BG layout) | — | +70 | — | — |
| HCZ1 | 650 | 159 | 0 | 159 |
| HCZ2 | 587 | 215 | 47 | 168 |

- AIZ2's background indices ($53–$103) sit inside its first tile set, interleaved with foreground tiles, so the index space really is shared.
- Keeping foreground and background separate, as aeon does, would duplicate 0–47 tiles per act. Every one of these backgrounds fits in 376 on its own.
- Pairs: AIZ1 BG + AIZ2 BG share 4 tiles by content, so together they need 256. HCZ1 BG + HCZ2 BG share 1, so they need 373, which fits 376 with 3 to spare.
- Combined totals: AIZ2 726, or 796 with fire; HCZ1 809; HCZ2 755. Your parallel slice's S3K range of 698–2536 includes these, so I don't see a disagreement. My numbers are per act and layout-referenced only.

**Q8. Sonic 2** (MEASURED)
- No in-level zone or act art swap.
- Changing act or zone sets `Current_ZoneAndAct` and `Level_Inactive_flag` (27778–27781). The main loop then branches to `Level` (5092), which fades the music, clears the art lists and calls `Pal_FadeToBlack` (4753–4761).
- The only mid-level loads are boss and Tornado object art lists (20409, 20517, 20656, 20668) and the HTZ pixel repaint (T5).
- S3K's zone to zone path is the same shape: `StartNewLevel` (180640) sets `Restart_level_flag`, and `LevelLoop` branches to `Level`, which fades.

**Q9. Unique tiles per zone:** done; the numbers are in the Q7 table. They include never-visible layout areas and exclude animated-tile frames.

## 4. What I could not determine
- How many frames each decode stage takes, so whether AIZ's uploads finish inside the ~9-frame opaque window, and whether the partly-swapped chunk/block tables ever reach the screen. That needs an emulator, which is out of scope.
- The exact camera Y when HCZ's swap fires. I used the arena lock Y; the player can still move vertically.
- AIZ1 background rows 7–10 contain what look like foreground chunk IDs. I excluded them; I didn't verify they are never shown.
- I didn't measure MGZ, ICZ, LBZ or the S&K-half transitions (SOZ/LRZ/DEZ), nor where the HUD sits in VRAM.
- Search scope for "mid-level art loads": every `Queue_Kos_Module)` call site, every `Events_fg_5` reference, and every write to `Current_zone_and_act` in `sonic3k.asm`; in S2, `LoadPLC`/`KosDec`/`NemDec` after line 19000 and every write to `Current_ZoneAndAct`.

## 5. Corrections to the brief
- **The corridor hypothesis is half right.** S3K does keep new art out of view until it's safe. But it never needs "old tiles evicted once off screen" or two zones resident at once: it overwrites in place while the camera is locked, with the nametables pinned elsewhere. Its corridor is a moment in time, not a strip of level.
- **"S3K is famous for seamless act transitions"** is true only within a zone. Zone to zone it fades to black.
- **"Plane B is 64×32 blocks"** should be **64×32 cells** (16 block rows × 32 block columns; line 1361).
- **Aeon's own doc disagrees with its code.** `ENGINE_ARCHITECTURE.md` ~1738 says the BG region holds "448 tiles … OJZ Act 1 uses ~340", but `engine/system/constants.emp:648` has `BG_TILE_CAPACITY = 376`. 376 and base $8000 are confirmed in code, and the wipe really is `PLANE_V_CELLS`=64 rows at 4 per frame.
- **Master has moved:** it's `6bed58fd` now, not `60a94111`. I verified against the current tree.
- **Your mid-task corrections** (backdrop sharing, the 320-tile shipped blob, the existing BG-streaming design) don't change any of these findings.

Scratch scripts and decoded data are in `/tmp/claude-1000/-home-volence-sonic-hacks-aeon/24471b62-cac3-45bf-af06-17ff8b6994b6/scratchpad/` (`kos.py`, `uniq.py`, `regions.py`, `hcz.py`, `dec/`); ignore `firechk.py` there, it's a broken leftover.
