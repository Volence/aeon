# Batman & Robin, Thunder Force IV and Ristar: stage scenery changes

> **Research slice for MEGAACT-BG-STREAMING (2026-09-16).** This is the research agent's final report,
> extracted programmatically from its transcript and committed VERBATIM, never retyped: a report
> whose value is its `file:line` citations cannot be summarised without becoming the
> summary-of-a-summary this project was bitten by twice today. It is a LEAD for the design, not a
> finding the design may assume: every MEASURED claim is re-checkable at its citation.

---

Short answer: none of the three games is a precedent for swapping a whole zone's background seamlessly. Batman & Robin comes closest. During live play it swaps a backdrop of about 78 tiles, and the steps are strictly ordered and spread over frames. Thunder Force IV changes scenery almost entirely with palette fades, and its biggest tile upload is 256 tiles for an object. In the code I read, Ristar only loads bulk art during loads or behind a palette fade. Your correction is noted and doesn't change any of this; I use the 604–965-tile zone size below.

**Scope.** For Thunder Force IV and Ristar the repo disassemblies have no addresses, so I disassembled both ROMs myself with capstone. Addresses for those two are ROM offsets you can re-derive; my scratch listings are temporary. For Batman & Robin, the first 2 MB of the rebuilt `disasm/bin/batman.bin` is byte-identical to the original ROM (0 differing bytes), so I cite its `.asm` files by line. Batman & Robin paths are relative to `.../The Adventures of Batman and Robin/disasm/code/engine/`. Each game's search is scoped at the end of its verdict.

## 1. Verdict

**Batman & Robin: a real but small precedent, and the only one here.** A camera trigger runs a script mid-stage (`objects_2.asm:5857-5862`: when `$ffed9c` ≥ `$680`, start the script at `$330FC`). That script:
1. Decompresses new background art during idle time, and the script waits for it to finish.
2. Uploads it under a per-frame budget.
3. Only then repaints plane B's nametable, row by row inside VBlank, under the same budget.

Each step waits for the previous one to finish. MEASURED from the script bytes and handlers. I ran the game's decompressor in Python: the upload is **78 tiles** (2,496 bytes) and the new map is 128×32. The sizes are self-consistent, which checks the decoder. That is a backdrop, not a zone.

The most important lesson: **new tiles are fully in VRAM before the first nametable word points at them, and a plane is blanked before its own tile range is reused.**

Two caveats:
- **Old art may not stay resident.** The new tiles go to tiles `$55A-$5A7`. An earlier section script loaded 434 tiles starting at `$42E` (up to `$5DF`), so the new block lands inside that range. Whether those old tiles were still on screen I could not determine without an emulator.
- **The larger loads are unresolved.** Two other section scripts use the same budgeted upload for 276 and 522 tiles. I could not tell whether those run on a visible screen.

Batman & Robin search scope: the VBlank handler, the DMA queue, the budget code, the script interpreter handlers (`interrupts.asm:1-735`), the async decompressor, and the scripts for section ids 21–24 (ROM `$32E0E-$33240`). I also counted script handler addresses across the whole ROM (the budgeted upload handler `$7682` occurs 17 times). I did not decode the scripts for stages 1x, 3x or 4x.

**Thunder Force IV: not a precedent for bulk tile swaps.**
- **Stage start:** all stage art loads at once, in 16-tile chunks (one 512-byte transfer per frame), while the main code busy-waits.
- **Scenery changes:** these are events keyed to distance travelled. Five palette-fade events in stage index 0, one each in stages 4 and 7 (as the table dump reads).
- **Tile changes:** one event burst in stage index 3 rewrites the same 32 animated-tile slots 16 times. Separately, two object routines upload 256 tiles over 16 frames and 96 tiles over 6 frames.

The lesson: **the planes' tile set is resident for the whole stage and only nametable columns stream.** "Scenery change" is mostly a palette fade plus per-row palette-attribute changes.

Search scope: I disassembled the whole 1 MB ROM. I read the gameplay loop, the per-frame VDP routine, the stage loader and the event dispatcher. I found every writer of the two transfer mailboxes and all 12 callers of the decompressor; all are in load or title paths.

**Ristar: no precedent found.** Gameplay art loads clear the display-enable bit first (MEASURED at `$14076-$14084`, `$61ECA-$61ED2` and level load `$7BC0-$7BCE`). The one loader that spreads work over frames (object `$5D3BE`, 100 tiles per frame) runs in a cutscene or menu mode, behind a 15-step palette fade to black. The transferable idea is **idle-time decompression that VBlank interrupts and the next frame resumes**, the same design as Batman & Robin.

Search scope: I disassembled 2 MB. I read the VBlank handler, the wait-for-VBlank routine, the async decompress setup, the loader object and its spawner, and the three callers of the async decompressor. I sampled 8 of the 42 callers of the synchronous decompressor `$4BBE`. I did not read the Nemesis or pattern-load-queue paths.

## 2. Techniques

**Budgeted DMA command queue** (Batman & Robin) — `main_loop.asm:22-29` and `sub_00784A`; checked by `sub_00799C` (`:194`) and `loc_007F5E` (`:822-850`). MEASURED.
- **How it works:** each entry is 14 bytes (length, source and command register writes). There are at most 40 entries per frame. VBlank jumps into an unrolled loop at the right offset, so unused slots cost nothing.
- **Budget:** `$ff9914` is set per stage from the stage-init stream (`:3604`). Values found: 130–220, measured at 37 stage-init call sites. Tile uploads charge 1 unit per tile plus 5 per transfer (`interrupts.asm:641`). VBlank nametable painting spends what is left at 1 unit per word written (`:555`).
- **Deferral:** a request that doesn't fit this frame's budget or slots is refused and retried next frame (`:893`).
- **Unit (INFERRED):** probably "VBlank time". I can't give a byte value.
- **For aeon:** a direct model for pacing background pages and repaint rows against one shared VBlank budget.

**Script handlers for uploads and paints** (Batman & Robin) — `interrupts.asm`. MEASURED.
- **`$7604`, immediate transfer** (`:585-622`): turns the display off (`$8134`) unless mode ≥ `$E`, then transfers, then turns it on (`$8164`). Used when a checkpoint restart reloads a section.
- **`$7682`, budgeted upload** (`:624-678`): queues as many tiles per frame as the budget allows, and continues next frame until done.
- **`$7468`/`$747C`, immediate nametable paint** (`:500-528`).
- **`$7488`/`$749C`, deferred paint** (`:530-620`): adds a VBlank task that writes rows directly to the data port with what's left of the budget.
- **`$723A`/`$724A`, deferred fill with a blank tile** (`:231-340`, tile `$5FC`).
- **Waiting (MEASURED):** each deferred handler parks the script until it finishes (`$ffe03a` continuation).
- **Cost (INFERRED):** a 128-wide row costs 129 units against a 160–220 budget, so at most one row per frame. The 32-row repaint takes at least 32 frames.
- **Two variants of the same section (MEASURED):** the checkpoint version (`$33184`) uses the immediate handlers with the same addresses. The live version uses the budgeted ones.

**VBlank task list** (Batman & Robin) — `main_loop.asm:1978` (`sub_008ADA`), with add and remove at `:2055` and `:2076`. MEASURED: a linked list of callbacks VBlank runs after flushing the queue. For aeon it maps onto a background-repaint task.

**Idle-time interruptible decompression** (Batman & Robin) — `main_loop.asm:4185` (setup), `:4197` (resume), `:4220` (decoder), `:4425` (done). The VBlank side is `interrupts.asm:724`. MEASURED.
- **Main loop order:** scripts, then resume the decompressor, then wait for VBlank (`:3651-3661`).
- **Suspend:** VBlank saves the decoder's registers and return PC. Its return from the interrupt lands back in the main loop.
- **Format:** an LZ variant with separate streams for control bits and literal bytes. Offsets use 5, 7, 9 or 10 bits.
- **For aeon:** this looks like the same design as aeon's §9.7 idle decoder.

**Blank before reusing a plane's tiles** (Batman & Robin) — script at `$330D0`. MEASURED. The order is:
1. Deferred fill of plane A with blank tile `$5FC`, waited on.
2. Decompress.
3. Budgeted upload into plane A's tile range (`$AAC0`).
4. Deferred repaint.

**For aeon:** the ordering your hypothesis asks for, done without a corridor.

**Display off for the whole VDP update** — Batman & Robin: `interrupts.asm:693` (`$8134`) until `main_loop.asm:5423` re-enables (`$8164`). Thunder Force IV: `$1BB0` calls `$1752` (display bit off) and ends at `$173E` (on). MEASURED writes. INFERRED purpose: if a transfer overruns into the visible frame, the top lines show black rather than garbage.

**Event table keyed to distance travelled** (Thunder Force IV) — dispatcher at `$55F2-$5646`; counter `$f27a` accumulates |scroll speed| (`$4660`, `$469E`); tables at ROM `$63400 + $C00×(stage+1)`. MEASURED.
- **Event types:** 5 sets the animated-tile rate (`$574C`). 6 fades to a new palette set (`$5754`, 128 bytes). 7 uploads up to 16 ROM tiles but acts only in stage index 3 (`$579E`). 11 changes mode (boss). 12 and up are object spawns.
- **For aeon:** a data-driven trigger shape, but the events carry palette changes, not art.

**Fixed per-frame transfer slots** (Thunder Force IV) — gameplay VDP routine `$1BB0-$1D5C`, run from the main loop after `stop #$2500` at `$2F94`. MEASURED slots:
- a one-shot mailbox (`$f28c`), last writer wins;
- 512 bytes of animated tiles per frame (`$f282`, skipped when disabled);
- the sprite table (flagged), 640 bytes of horizontal scroll, and CRAM;
- 4×64-byte column transfers (`$f25e`, `$f260`) plus two 512-byte blocks (`$f262`, `$f264`).
- **Budget:** fixed by construction, roughly 3.5 KB per frame at most (INFERRED sum).

**Stage load and nametable streaming** (Thunder Force IV) — `$3E64-$424C`, `$428C`, `$429A-$43E0`. MEASURED.
- **Load:** three decompressed sets per stage. VRAM `$0000-$7FFF` (1,024 tiles) is filled in 512-byte chunks per frame, with a busy-wait handshake. Both plane nametables are built into RAM as a 64×64 image.
- **Live:** columns stream to VRAM `$C000`, with palette attributes per row group from a per-stage table at ROM `$6CC00`.
- **Shared pool (INFERRED):** both planes' nametables index the same uploaded tile range.

**Object uploads spread over frames** (Thunder Force IV) — `$3DCD2`: ROM `$6E000+n×$200` → VRAM `$2000+n×$200`, 16 frames × 512 bytes = 256 tiles. `$47ABA`: ROM `$63200` → VRAM `$8800`, 6 frames = 96 tiles. MEASURED. The first overwrites part of the stage's own tile range with no coordination with the nametable. Why that is safe is NOT DETERMINED.

**Loader object** (Ristar) — `$5D3BE-$5D512`, spawned by `$5D1B0-$5D24A`. MEASURED order:
1. Async decompress.
2. Wait until done.
3. Up to 100 tiles per frame into a RAM transfer slot at `$E900` (cap at `$5D446`).
4. Decompress the map.
5. Immediate rectangle paint (`$5561E`).

The spawner first fades the palette out over 15 steps and afterwards fades it in. This is a cutscene or menu mode, not gameplay.

**Interruptible decompression** (Ristar) — setup at `$4C24` (resume PC `$4C3E`), VBlank at `$4284-$4310` (rewrites the return PC to `$6C6C`), resume inside wait-for-VBlank at `$6C60-$6C8E`, done at `$4CA2`. MEASURED; the same design as Batman & Robin.

## 3. Answers

1. **Batman & Robin.**
   - **Mid-stage changes:** yes. Plane B is swapped mid-section and plane A is blanked and reused for section 24 01.
   - **VDP shadow table:** I did not find one tied to uploads in what I read. It writes literal register values; I didn't search the whole ROM for one.
   - **Batching:** all VBlank work is batched (register command queue, then the task list), and every script handler that spreads work waits for it to finish.
   - **Budget:** a per-stage abstract budget of 130–220 units and 40 transfer slots per frame.
2. **Thunder Force IV.** Plane tile art is not swapped within a stage in any code I found. The exceptions are the 32 animated-tile slots in stage index 3 and object uploads of up to 256 tiles. Scenery transitions are distance-triggered palette fades and palette-attribute or scroll changes. The event's own order is: copy 4 palette lines into a target, then start a fade.
3. **Ristar.** In what I read, no gameplay code changes art mid-stage while the display is live. Art loads either clear the display bit or run behind a palette fade.
4. **Order.**
   - Batman & Robin: optional plane blank-fill (spread, waited on) → decompress (idle time, waited on) → tile upload (budgeted, waited on) → nametable repaint (budgeted, in VBlank). Raster mode changes before the script starts (`objects_2.asm:5859`). The palette is not touched in the `$330FC` swap.
   - Ristar's cutscene loader: palette out → tiles → map → palette in.
   - Garbage avoidance is by ordering, plus display-off during VBlank work. Whether a visible wipe is hidden is NOT DETERMINED.
5. **Transfer budget during play.**
   - Batman & Robin: abstract units as above.
   - Thunder Force IV: fixed slots, 512 bytes (16 tiles) for any one art slot per frame.
   - Ristar's loader: 100 tiles (3,200 bytes) per frame.
   - All three spread big loads across frames with an "until done" state.
6. **Resident vs dynamic VRAM.**
   - Batman & Robin: tile addresses are authored into each script per section, with no allocator for backgrounds. Sprite art does have a reference-counted, budget-deferred allocator (`main_loop.asm:822-930`), which I did not decode fully.
   - Thunder Force IV: a resident stage tile set, 32 dynamic animated slots, and object overwrites.
   - Ristar: four RAM transfer slots at `$E900-$E960`.
7. **Foreground and background patterns.** One shared pattern space in all three. In Batman & Robin, planes A and B take tile bases from the same space (`$A556`→`$556`, `$455A`→`$55A`). INFERRED for Thunder Force IV.

## 4. What I could not determine

- **Batman & Robin:**
  - whether the 32-frame plane-B repaint is visible on screen;
  - whether the overwritten tiles at `$55A-$5A7` were still referenced;
  - whether the 276- and 522-tile section uploads happen on a visible screen;
  - which data record starts those section scripts (a `$7092` start-script call exists at `$21D8C`/`$21D98`; the record layout is not decoded);
  - the byte value of a budget unit.

  All of this needs an emulator trace; my brief forbade using one.
- **Thunder Force IV:**
  - which stage the 256-tile object runs in;
  - what the `$8F02`/`$8F04`/`$8F80` register writes do;
  - the exact end of the event tables for stages 2–6 and 9 (my parser read into padding).
- **Ristar:** the consumer of the `$E900` slots, and 34 unchecked callers of the synchronous decompressor.

## 5. Wrong in the brief or the existing notes

- **Brief, "Batman = VDP shadow table":** not borne out by what I read. What matters for bulk uploads is the command queue plus the VBlank task list.
- **Your corridor hypothesis:** the one precedent does not use a corridor. It uses camera triggers and "wait for each step to finish" ordering. A stated neutral step exists only as the blank-tile fill before a plane's tile range is reused. And "old tiles evicted only once off screen" is not shown: Batman & Robin's destination overlaps the previous block.
- **`disasm/ART_AND_COMPRESSION.md`:**
  - "No compression" is wrong: there is an LZ decoder at `$A23E`.
  - The "280-iteration loop writing about 3,920 bytes during the active frame" is wrong. `$784A` is a 40-entry register-command queue flushed in VBlank.
  - The "active-display writes double bandwidth" claim is not supported by the VBlank code I read.
- **`disasm/MEMORY_MAP.md`:** "interrupts.asm = VBlank/HBlank handlers" is misleading. Most of that file is the script interpreter.
- **`thunderforce4_disasm/ANALYSIS.md`:**
  - The "10-mode VBlank dispatch" is used with a constant index and only when `$f304`≠0.
  - Gameplay VDP work happens in the main thread after `stop` (`$2F94`, then `$1BB0`), not in VBlank.
  - The ROM file's header says `GM T-18063 -00J`, and its exception vectors point to `$B00Dxx`, beyond the 1 MB ROM. This may be a modified dump.
- **`ristar_disasm/ANALYSIS.md`:** `$C01E` is not a "stage script interpreter". It is demo playback: it injects recorded input into `$ea3a/$ea3b` when mode = `$4C` (demo), with a recorder at `$C028`. The "cinematic engine at the level-script layer" claim built on it falls with it.
- **`aeon/docs/research/ristar-techniques.md`:**
  - It says nothing about art swapping.
  - "VBlank exit code points the IRQ vector at it" is loose: the vector is fixed at `$FFEA70` and only the RAM jump target changes.
  - I did not verify its raster, grab or animation claims; they stay INFERRED.
