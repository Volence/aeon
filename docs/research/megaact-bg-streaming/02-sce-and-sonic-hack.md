# S.C.E. and sonic_hack: level-art loading and act transitions

> **Research slice for MEGAACT-BG-STREAMING (2026-09-16).** This is the research agent's final report,
> extracted programmatically from its transcript and committed VERBATIM, never retyped: a report
> whose value is its `file:line` citations cannot be summarised without becoming the
> summary-of-a-summary this project was bitten by twice today. It is a LEAD for the design, not a
> finding the design may assume: every MEASURED claim is re-checkable at its citation.

---

I found no precedent for a seamless zone-to-zone transition in S.C.E. or `sonic_hack`. Neither streams level art during play, and neither keeps foreground and background tiles apart.

## 1. Verdict

S.C.E. has none of what you're hoping for. It ships one zone (DEZ, four acts sharing one tileset). It loads level art only inside `LevelScreen`, after fading to black and in a loop that waits for loading to finish. Its S3K-style act-transition hooks are empty: the flag gets set, and DEZ's handler just clears it. The routines that would re-point level data (`Reset_LevelData`, `Load_Level2`, `Load_Solids2`, `Change_ActSizes2`) are never called on either git branch. S.C.E. does stream object art during play, through a Kosinski+ module queue drained every frame. Its one "overwrite a VRAM slot during play" case waits until the object using the art is off-screen first. That matches your "evict only once off screen" rule, but only for sprites.

`sonic_hack` also streams no level art. It keeps one tileset per zone, used by both planes. It varies its sections through palette swaps and per-section background layout rows, never through tiles. Its `VRAM_Layout.asm` budget doesn't hold up against its own data or its own VDP register setup.

Your core hypothesis (background tiles must page in and out, with a neutral corridor) is neither supported nor refuted here. Neither engine ever faced the problem. The real S3K transition code is in `skdisasm`, which was outside my slice.

## 2. Techniques

| Technique | Where | Label | How it works | Cost | Use for aeon |
|---|---|---|---|---|---|
| Level art queued, then a blocking wait | `Engine/Core/Load Level.asm:7-32`, called only at `Screens/Level/Level.asm:111` | MEASURED | Queues the primary 8x8 art at VRAM 0. Optional secondary art goes straight after it (offset = primary size, `:19`). Then loops until the queue is empty (`:25-31`). Blocks and chunks are decompressed in one go, no queue (`:96-118`). | Screen is already black (`Level.asm:25`) | None. It's a load screen. |
| Kosinski+ module queue drained during play | `Kosinski Plus Moduled Decompression.asm:55-116`; per-frame calls at `Level.asm:187` and `:204` | MEASURED | Decompresses one module (up to `$1000` bytes = 128 tiles) into a buffer, then queues it for DMA (`:76-93`). The next module isn't queued until the next call, so each module takes at least 2 frames (INFERRED). | At most 4 KB of DMA per module; roughly 2 KB/frame average or less (INFERRED); 32 queue slots (`Constants.asm:106`) | Aeon's paged foreground cache already does more. |
| Decompression resumable across VBlank | `Set_KosPlus_Bookmark` at `:201-213`, called from VInt at `Interrupt Handler.asm:316,320`; restore at `:225-229` | MEASURED | If VBlank interrupts decompression inside the decoder, the interrupt returns to a routine that saves the registers and resume address; the next call picks up there. | Uses idle time only | Same idea as aeon's §9.7 decoder, which already exists. |
| DMA queue with no byte budget | `DMA Queue.asm:243-300`, `:346-375`; `Variables.asm:57` | MEASURED | 18 fixed slots (`$12*7` words, 14-byte entries). If full, the request is silently dropped (`:255-256`); debug builds raise an error. Splits transfers that cross a 128 KB boundary (`:302-335`). | Capped by slot count, not bytes | Nothing to borrow: aeon's queue already adds priority and budget. |
| Overwrite a VRAM slot only once its user is off-screen | `Objects/Main/Signpost/Signpost.asm:174-196` | MEASURED | After the results screen, the signpost waits until it's out of range, then re-queues `PLC2_Sonic` (springs, spikes, monitors, explosion) over the slots and frees its DPLC tracking slot. | One queue call | Same rule as your "evict when off screen", but for sprite slots. It doesn't check whether *other* on-screen objects use the overwritten tiles (INFERRED gap). |
| Mutually exclusive art sharing one VRAM range | Title card `$500`/`$53D` (`Title Card.asm:32,40`), results `$500`/`$548`/`$566` (`Results.asm:33,37,116`), `PLC2_DEZ1_After` spikebonker at `$500` (`Pattern Load Cues.asm:44`) | MEASURED | Art that is never on screen at the same time shares one range and is reloaded after use. | 0 VRAM, one reload | Just ordinary slot sharing. |
| Foreground and background share tiles, blocks, chunks and layout | `Level Setup.asm:26-38` | MEASURED | Plane A and Plane B are drawn from the same 16x16 table (`a2`) and one layout, with background rows 2 bytes after foreground rows (`addq.w #2,a3`, `:37`). | One pool | The opposite of aeon's split. |
| Animated tiles sent every frame | `Animate Tiles.asm:53-71` | MEASURED | Uncompressed ROM frames are queued for DMA to a fixed VRAM address. | Per script, per frame | Not relevant here. |
| Per-section palettes and background rows on one tileset (`sonic_hack`) | `section_streaming.asm:1335-1373` (apply), `level_load.asm:252` (fade every frame), `:26-29` and `:165-170` (background rows with a global fallback) | MEASURED | Sections look different through palette lines 1-3 and background layout rows, never through tiles. | 96 bytes of palette per swap | Explains why `sonic_hack` never needed background paging. It doesn't carry over to S2/S3 zones, whose tiles really differ. |

## 3. Answers

**1. How S.C.E. loads art.** It uses Kosinski+ module queues (the S3K KosM design with the Kosinski+ format), plus raw PLC lists.
- **Level art:** loaded only at level load (`Level.asm:111-112`), with the screen already black (`:25`).
- **Object art:** loaded during play too. The module queue is processed every frame (`Level.asm:187,204`). Callers include the signpost (`Signpost.asm:188-189`), egg capsule (`Egg Capsule.asm:26`), title card (`Title Card.asm:32-41,134-141`) and results (`Results.asm:33-37`).
- **Restarts and act changes:** `StartNewLevel` (`Engine/Objects/Misc.asm:62-66`) sets `Restart_level_flag`, which re-enters `LevelScreen` with a fade (`Level.asm:196-197`).

**2. Seamless act or zone transitions.** Not implemented, so there's no upload, repaint, palette or parallax order to cite.
- Results sets `Background_event_flag` unless this is the last act (`Results.asm:125-129`).
- DEZ's handler only clears it (`Levels/DEZ/Events/DEZ1 - Events.asm:48-50`).
- The "in-level" title card (`Results.asm:216-220`) skips the PLC reload (`Title Card.asm:125-128`). The signpost controller then only changes camera bounds (`Signpost.asm:51-55`, `Check Range.asm:585-591`).
- No tiles, layout or palette are swapped.
- `Reset_LevelData` (`Load Level.asm:50-64`), `Load_Level2` (`:135`), `Load_Solids2` (`:76`) and `Change_ActSizes2` (`Check Range.asm:599`) have no callers. I checked the working tree (grep) and `git grep` on `Clone-Driver-v2`.

**3. Dedup or sharing.**
- There's no dedup code.
- Sharing is by authoring convention: primary plus optional secondary 8x8 sets appended in VRAM (`Load Level.asm:10-20`), and one tileset used by all four DEZ acts (`Data/Levels Data.asm:21-23`; `DEZ1 - Pointers.asm:33-40`, where secondary is 0).
- Foreground and background use one pattern set, one block table, one chunk table and one layout (`Level Setup.asm:26-38`).
- DEZ primary art is 209 tiles (header `$1A20` = 6688 bytes, MEASURED from `Levels/DEZ/Tiles/Primary.kospm`).

**4. Resident vs per-zone in S.C.E.** Everything is reloaded on each `LevelScreen` entry. Nothing is resident across level loads.
- **Every level:** `PLC1_Sonic` (starpost, rings, HUD; `Pattern Load Cues.asm:10-14`) loads at `Level.asm:72-73`. `PLC2_Sonic` (springs, spikes, monitors, explosion; `:20-24`) loads after the title card (`Title Card.asm:134-135`).
- **Per zone/act:** level art, then PLC1, PLC2 and animals from the pointer file (`Title Card.asm:136-141`).
- **Fixed addresses:** `Constants.asm:776-788` (Sonic `$680`, Ring `$6BC`, HUD `$6C8`, Shield `$79C`, DashDust `$7E0`). Plane A is at `$C000`, Plane B at `$E000`, horizontal scroll at `$F000`, sprite table at `$F800` (`:830-838`).

**5. Spreading big uploads across frames.**
- Module granularity is `$1000` bytes: one module decompressed per queue call, then one DMA (`Kosinski Plus Moduled Decompression.asm:78-92`).
- Decompression resumes across VBlanks via the bookmark.
- The DMA queue has 18 slots and no byte budget (`Variables.asm:57`, `DMA Queue.asm:176`).
- So the per-frame budget is implicit, about one `$1000` module per 2 or more frames (INFERRED from control flow, not measured at runtime).

**6. Departures from S3K.** From code I read:
- Kosinski+ / Kosinski+ Moduled formats and the Ultra DMA Queue (`DMA Queue.asm`, with the 128 KB split option on at `:115`).
- Custom per-object DPLC via DMA, at most 16 tiles per transfer (`Misc.asm:85-119`).
- A tracking-slot mask for those DPLC slots (`Remember State.asm:237-241`).
- The level pointer table copied into RAM (`Load Level.asm:147-216`).
- Two-byte chunk IDs (README only; I didn't trace the code).

That S3K already had the KosM queue and bookmark is INFERRED from general knowledge; I didn't verify it in `skdisasm`. **None of these departures touches seamless loading.**

**7. `sonic_hack` budget.**
- On paper (`VRAM_Layout.asm:9-14,35-122`): level art `$000-$23F` (576), Pool A `$240-$3FF` (448), Pool B `$400-$5FF` (512), Plane A nametable `$600-$67F` (128), UI plus shared `$680-$77F` (256), characters `$780-$7FF` (128). **There's no background region.**
- The loader (`code/engines/demo_continue.asm:263-299`) decompresses one Kosinski file (`zones/ojz.asm:13`, `Tile List.asm:4`) and uploads it in `$1000`-byte chunks, one per VBlank. Both planes' layout rows index that one set.
- **MEASURED:** `art/kosinski/OJZ.bin` decompresses to 919 tiles (`$000-$396`). My decoder consumed exactly 17568 of 17568 input bytes. That is 60% over the 576-tile budget and covers most of Pool A. The file's own comment (`:63`) says "overflows to ~$449", which also disagrees with my measurement.
- The table overlaps the VDP tables it's supposed to sit around:
  - Plane B nametable: `$8407` = `$E000`, 64x32 via `$9001` (`level_init.asm:87,89`) = tiles `$700-$77F`. That's inside "Core UI + Shared", and `VRAM_ResultsText = $72E` (`:121`) lands in it.
  - Sprite table: `$857C` = `$F800` = tiles `$7C0-$7D3`.
  - Horizontal scroll: DMA'd to `$FC00` (`dma_plc.asm:178`) = tiles `$7E0-$7FB`, inside "Characters".
  - Whether this corrupts anything at runtime is INFERRED; I didn't run it. **Treat this table as a sketch, not a prior answer.**

**8. Per-act or per-zone separation in `sonic_hack`.**
- Tiles, blocks and chunks are per zone; acts get only palette, starts, bounds and a section table (`ojz.asm:9-54`).
- The four `OJZ*.bin` "variants" (metallic, snowy, sunset) are **byte-identical** (same md5). Their differences live only in palettes (`ojz.asm:70,79`; `palette.asm:725-727`).
- `Section_PreloadArt` (`section_streaming.asm:1303-1325`) was built for per-section art but has **no callers**. It would also have decompressed synchronously and flushed the DMA at once (`load_art.asm:63-77`).

## 4. What I could not determine

- **The real S3K transition order** (AIZ1 to AIZ2 and the other zones): S.C.E. stripped it. `skdisasm` would answer it.
- **Runtime DMA bytes per frame** for either engine: static reading only; no emulator, per the brief.
- **Sizes of `sonic_hack`'s `.kospm` files:** their header words (e.g. `Signpost.kospm` = `$B000`) don't decode as S.C.E.-style sizes, and `tools/kosdec` crashed with an assertion on `OJZ.bin`. So the size of the art at `$72E` is unknown, though any size overlaps the Plane B range.
- **Search scope:** all `.asm` in S.C.E.'s `flamedriver` working tree (236 files, `comfy-env` excluded), `git grep` of `Clone-Driver-v2` for the transition symbols, `README.md`, and `sonic_hack`'s `VRAM_Layout.asm`, `code/`, and the OJZ Kosinski art. I didn't open `S4.asm`'s includes beyond these. The reference absences are statements about this scope.

## 5. What in the brief is wrong or needs a caveat

- **Commit:** this checkout's `master` is `e8a8a777`, one status-only commit past `60a94111`.
- **Capacity figure:** `BG_TILE_CAPACITY = 376` is correct (`engine/system/constants.emp:648`, enforced in `games/sonic4/config/constants.emp:527`). But the `ENGINE_ARCHITECTURE.md` passage you cited (around line 1738) still says **448 tiles, "OJZ Act 1 uses ~340"**. The doc is stale against the code.
- **"S.C.E. is the most valuable reference for act transitions":** not for this question. It contains hooks only, one zone, and no working transition.
- **"`VRAM_Layout.asm` is a real prior answer to aeon's budget question":** it's weak. The data breaks it (919 tiles against 576) and it overlaps the Plane B nametable, sprite table and horizontal-scroll writes.
- **Context for the split:** separate foreground and background pools are aeon's own design. Neither reference does it. One consequence to weigh: the split is partly why aeon can never share a tile between planes. Keeping one pool would let background tiles use the foreground paging machinery.
