# Vectorman, Gunstar Heroes and Alien Soldier: live tile-art streaming

> **Research slice for MEGAACT-BG-STREAMING (2026-09-16).** This is the research agent's final report,
> extracted programmatically from its transcript and committed VERBATIM, never retyped: a report
> whose value is its `file:line` citations cannot be summarised without becoming the
> summary-of-a-summary this project was bitten by twice today. It is a LEAD for the design, not a
> finding the design may assume: every MEASURED claim is re-checkable at its citation.

---

# Vectorman, Gunstar Heroes and Alien Soldier: do they swap tile art mid-level?

**The short answer:** Alien Soldier and Gunstar Heroes both stream tile art in during live gameplay, at the size of a full zone's art (up to about 710 tiles in one load). Vectorman does it only at stage start, plus a few small uploads mid-stage (72 and 325 tiles).

**How to read the citations.** The repo's `disasm.asm` files have no address column. Vectorman's also skips ROM `$88C2`–`$8C00`, which is where its VBlank handler lives (it jumps straight to `disasm.asm:7806` `loc_008C00`). So I disassembled the three ROM images myself with capstone: `The Adventures of Batman and Robin/{Vectorman (USA, Europe).md, Gunstar Heroes (USA).md, Alien Soldier (Europe).md}`.
- A citation like `AS $294E` means a ROM address I read in my own disassembly.
- `vectorman disasm.asm:N` means a line in the repo file.
- Everything is **MEASURED** unless it says **INFERRED**.
- **Search scope:** the full ROMs (code-shaped regions); every VDP port and DMA register site; every caller of each game's art loaders; every display-disable write.

**Housekeeping.** The repos were not touched. I did write temporary listings and a helper script under `scratchpad/`. That scratchpad is shared with a parallel agent: my first `mv dis.py m68kdis.py` may briefly have overwritten its `m68kdis.py`. That file now holds its content again, but it should check.

## 1. Verdict

**Alien Soldier: a real precedent, and a strong one.** The whole game runs inside the VBlank interrupt. The main loop does only one thing: it runs a deferred art loader in whatever CPU time is left each frame (`AS $055E–$0568`: `move.w #$2300,sr; jsr $294E; bra`).
- Stage scripts start loads of 376–711 tiles in the middle of a scrolling stage. The loader pushes one chunk per frame through the DMA queue.
- Stage code waits for the load to finish before redrawing the plane, one row per frame.
- **Main lesson:** decode during idle CPU, send one chunk per frame through the normal queue, and let gameplay code wait on a "load finished" flag. This is aeon's §9.7 design, shipped in 1995.

**Gunstar Heroes: a real precedent, same engine.** The loader and decompressor are opcode-for-opcode identical to Alien Soldier's.
- Camera position starts loads (421 tiles at camera X ≥ `$1500`). The script waits for completion, then locks the camera.
- Boss and object code starts loads of up to 708 tiles.
- **Main lesson:** the "corridor" is a stage script, not a mechanism. Scrolling continues while the load runs, and progress or a camera lock only happens once the load is done. I could not identify which loads belong to Dice Palace.

**Vectorman: mostly not a precedent.**
- Level art loads once at stage start, inside one routine with interrupts off.
- Mid-stage it streams sprite frames through a budgeted queue.
- There are two small scripted mid-stage uploads: 72 tiles over 2 frames, and 325 tiles over 5 frames. Both use immediate DMA outside the queue.
- **Main lesson:** its queue budget and all-or-nothing enqueue are sound. But at 72–325 tiles its mid-stage swaps are a different scale from a Sonic zone (604–965 tiles).

## 2. Techniques

| # | Technique | Where | How it works | Cost | Fit for aeon |
|---|---|---|---|---|---|
| T1 | Idle-time deferred loader | AS `$28C0` (setup), `$294E` (runner), jump table `$2974`; called from the idle loop at `$0562`. GS: `$2478`, `$2506`, `$0438` | A command list of {flags word, source long, destination word}. Bit 0 = VRAM or RAM destination; bits 1–2 = raw / 4bpp tile codec / LZ. Progress is saved in `$F720`–`$F732`, so each game frame it adds one chunk to the queue at `$2D4A` (sets `$F754`) and spins on `tst.b $F754` until VBlank drains it (cleared at `$0F7E`). | One chunk per frame. Raw or tile codec: 512 bytes (16 tiles) (`$29B6`, `$29FE`). LZ: 1024 bytes (32 tiles) decoded into staging RAM at `$B400` (`$2A74`). CPU cost is idle time only. | Direct precedent for §9.7. Proves full-zone-size loads (up to 711 tiles) stream fine during live play. |
| T2 | "Load finished" gate | AS: `$F720` (bit 15 set while loading, `$28CA`), tested by stage scripts (`$DA24`, `$F65E`, `$F732`) and by many objects (e.g. `$349FA`, `$36CCA`). GS: `$7370`, `$741E` | Gameplay reads the flag. Scroll acceleration only happens once loaded (`AS $DA24–$DA32`). Plane rebuild waits for it (`$F65E`). | Nothing | A gate that any consumer (plane repaint, boss spawn) can wait on. |
| T3 | Load-time tile rebasing | AS `$1193A`, used at `$F66E` | After loading, block definitions in RAM get a tile base added: `d1=$F8` matches the load to VRAM `$1F00` (tile `$F8`). Palette and priority are OR'd in from `d0`; tile 0 is left as 0. | CPU once per load | The same art can live at any VRAM base. That is the tool for putting incoming art in free slots. |
| T4 | Row-at-a-time plane repaint through the queue | AS `$1139E`–`$1149A`, set up at `$F690`–`$F6A4` / `$DAC4`–`$DAD0` | Each call writes 16 blocks → 64 cells (128 bytes, `#$94009340`) into the queue, plus a RAM mirror. `$A944` counts down from `$1F` (32 rows). | 128 bytes per frame | Same shape as aeon's crossing wipe. |
| T5 | Per-frame DMA queue with no budget | AS drain `$0E8C–$0EAC`, GS `$0DDA–$0DFA`: stack at `$F400` growing downward, 16-byte entries | VBlank drains everything that was queued, before game logic runs (`AS $0C08`). No length or entry check. Game logic runs with interrupts on inside VBlank, guarded by `$F704`. | Unbounded. The loader keeps its own share small (T1). | Supports the queue approach. The missing budget is a weakness, not something to copy. |
| T6 | Budgeted, all-or-nothing enqueue | Vectorman `disasm.asm:6288–6339` (`sub_007826`) | Checks entries < `$36` (54) and a running `$AABE` + length ≤ `$B40`. **Units are DMA length words:** destination advances by `d3*2` (`:6320–6321`), so the cap is 5760 bytes ≈ 180 tiles. On overflow the **whole call rolls back** (`loc_00788C`, `:6325–6331`, returns `d0=0`). Budget reset per frame at `$767C` (`:6252`) via `$846A` ← `$8406` ← per-frame stage routine `$2FCAC`. Sprite code keeps the old frame on refusal (`:7437`). | 180 tiles/frame cap | Good pattern for aeon's DMA budget. |
| T7 | Split an immediate upload across calls | Vectorman `$3009A` (state `$9(a6)`); `$10E272` (state `$5(a6)` 1→5) | Each call does one list via `$205A`, calling `$8EB4`: an immediate DMA with interrupts off and the Z80 stopped. 2 × 36 tiles (`$AC20`, `$B0A0`) or 5 × 65 tiles (`$81C0`…`$A260`). | 36–65 tiles per frame, outside the T6 budget. INFERRED: runs during active display, since it is called from the main-loop stage routine `$2FC78`, which sets `$E80A` at the end. | Small scale only. |
| T8 | Whole stage load, atomic | Vectorman `$1BCE` (`sr=$2700`), called from the stage-init script at `$1FC3E`. LZSS straight to the VDP port: `$639C`. RAM cache of decompressed items with a lookup table: `$2386`, `$BE78`, up to 64 entries. | Everything at stage start | n/a | Not a live swap. |

## 3. Answers

**1. Vectorman.** It does not stream level tiles in the way you mean. The stage art bank loads at init (T8).
- **Mid-stage uploads found:** `$2FE96` runs once when the player's Y drops below `$560`. It calls `$30010`, which installs a new plane-B descriptor (`$1F72` with `$199D78`), calls `$230E(#$11)` and `$2326`, then uploads 72 tiles over the next 2 frames (T7). The second one: `$10E0C2` (from object init at `$4FC3E`) queues 32 writes, then uploads 325 tiles over 5 frames.
- **Transfer budgeting:** yes, T6.
- **I did not verify** the "64×64 planes" claim.

**2. Gunstar Heroes.** Yes, art changes mid-stage.
- `$7332–$7436`: at camera ≥ `$1500` it loads list `$942A` (421 tiles to tiles `$150`–`$2F4`, plus a 4800-byte map to RAM). Scrolling continues. At `$7370` it waits for the load; at ≥ `$1780` it locks the camera (`$73AA`); at ≥ `$1800` it loads `$944C` (53 tiles) and waits again (`$741E`).
- Object and boss code starts loads (a5 is pushed): `$335B2` loads 708 tiles; `$595BA` loads 448; `$61E36` loads 250.
- Its lists use the tile codec at 16 tiles per frame, so 708 tiles take about 45 frames.
- **Not determined:** which stage is Dice Palace.

**3. Alien Soldier.** Boss and scene art goes through T1 and T2, not through load screens. In-stage loads I sized by re-implementing the `$2ABC` LZ decoder; every result came out a whole number of tiles, which cross-checks the decoder:

| List | Contents | Minimum frames |
|---|---|---|
| `$D938` | 376 tiles → tile `$300` | 12 |
| `$11FA6` | 406 tiles | 13 |
| `$F62C` | 711 tiles → `$000` and `$0F8`, plus maps and 128-byte blobs to RAM | 23 |
| `$DB04` | 110 tiles → `$400` | 4 |
| `$12C0E` | 242 tiles → `$300` | 8 |
| `$36CB8` | 276 tiles → `$300` (object-triggered) | 9 |

- There are no display-disable writes (`bclr #6,$F7D3`) anywhere between `$9D66`… and `$1CB96` in the sorted list, and the stage scripts sit at `$D000`–`$12FFF`.
- **INFERRED:** these loads happen with the display on. A palette fade is not excluded.

**4. Ordering and how garbage is avoided.**
- **Alien Soldier, `$F5E8` → `$F65E`:**
  1. Set scroll positions.
  2. Start the list. Within the list, the VRAM tiles come first, then the RAM maps and 128-byte blobs (INFERRED to be palettes: 64 words = 4 × 16).
  3. Wait on `$F720`.
  4. Rebase the block tables to the load base (T3).
  5. Repaint 32 rows, one per frame (T4).

  This matches your "tiles first, then repaint" hypothesis.
- **How garbage is avoided (INFERRED):**
  - incoming art goes to VRAM ranges the current nametable does not reference, at a base the blocks are rebased to;
  - the script holds progress until loaded (scroll ramp, camera lock at GS `$73AA`).
- **Not seen:** a display-off at these sites.
- **Vectorman `$30010`:** the plane-descriptor switch comes *before* the tile upload. Whether the plane is actually redrawn before the tiles arrive is not determined.
- **CRAM timing:** not determined in any of the three.

**5. DMA budget.**
- **Alien Soldier / Gunstar:** the loader adds one chunk per game frame (512 bytes raw or tile codec, 1024 bytes LZ). The drain itself is unbounded.
- **Player sprite art** also streams every frame in VBlank.
  - Alien Soldier (`$0EB0–$0EE2`): 4 or 896 bytes (`#$93029400` / `#$93C09401`) from RAM to VRAM `$F000`.
  - Gunstar (`$0E0E–$0F24`): 3 × 80 and 4 × 80 bytes to `$D000`/`$E500`-range slots.
- **Vectorman:** queued uploads are capped at 5760 bytes (180 tiles); immediate uploads bypass the cap.
- **Big loads are spread** by the idle loader's chunking (Alien Soldier / Gunstar) or by per-call state machines (Vectorman).

**6. Resident vs dynamic.**
- **Alien Soldier:** load destinations cover tiles `$000`, `$0F8`, `$15C`, `$2D6`–`$2DF`, `$300`, `$400`, `$500`, `$580`, `$600`, `$680`/`$6F0`, `$700` and `$7B4`. INFERRED: almost all of VRAM is per-scene.
- **Resident slots:** the player-sprite streaming slots (above) and the sprite table.
- **Not determined:** a full resident map.

**7. Foreground and background.** All three use the one hardware pattern space.
- Alien Soldier puts per-plane sets in separate ranges and keeps separate RAM block tables (`$FF4020` vs `$FF2020`; INFERRED to be FG vs BG). T3 rebases them independently.

## 4. What I could not determine

- **Which stage each list belongs to** (including Dice Palace), and what is actually on screen during each load. That needs a running emulator, which was ruled out.
- **Palette application timing.**
- **Whether overwritten VRAM ranges are ever visible mid-load.** All three answers above rest on INFERRED slot separation.
- **Alien Soldier `$12D98`:** an immediate 288-tile DMA via `$1BF62`, called from `$123AC`. Its context is unknown.
- **Gunstar LZ handler `$2616`:** its control flow reads oddly in a linear-sweep disassembly; not verified.
- **Chunk-boundary back-references in the LZ path:** the `$B400` staging buffer resets every 1024 bytes. INFERRED: the encoder must keep chunks independent.

## 5. What in the brief (and its lead sources) was wrong

- **"Old tiles evicted once off screen" and a generic "neutral corridor":** neither Treasure game has eviction. They overwrite whole ranges, and the corridor is scripted per stage (hold progress or lock the camera until loaded). Your hypothesis is right in effect, but it is a stage-design contract, not a runtime mechanism.
- **`vectorman_disasm/ANALYSIS.md`:**
  - **:35:** the "object processing loop at `$2062`" is actually the stage art-list walker `$205A` (entries = VRAM address, length/16, loader function `$2368`/`$2386`/`$2366`, data pointer). The real object lists are `$841A` and `$846A`.
  - **:120, :187, :234:** the budget is 2880 words (5760 bytes), not 2880 bytes.
  - **:181–182:** `$E802`/`$E808` are rollback checkpoints, not swapped double buffers.
  - **:188:** partial lists do not succeed; the whole call rolls back.
  - The "render trampoline `$8EB4`" is an immediate DMA routine.
- **`gunstar_disasm/ANALYSIS.md` (shared with Alien Soldier), :116, :134:**
  - "Direct VBlank DMA (No Queue)" is wrong: both games have a queue at `$F400`.
  - "Art is pre-rendered, not streamed" is wrong: player art streams every frame and level art streams in-stage.
  - The file says nothing at all about art loading.
- **Your correction message:** noted. On the scale question, Alien Soldier (711 tiles) and Gunstar (708 tiles) work at real Sonic 2 zone scale (604–965 tiles). Vectorman's live swaps (72–325 tiles) do not.
