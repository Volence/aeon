# Re-anchor addendum — `2026-07-02-art-streaming-phase2.md` (2026-08-06)

**Status: addendum only — the plan file is deliberately untouched** (rewrite
happens after the morning §9.7 rulings, so it re-anchors once, not twice). The
plan predates the Sigil flip and the engine/game split; every path and most
anchors are stale. Read this table beside the plan; anchors verified against
master `4974bf3`.

## Global re-anchors (apply to every task)

| Plan says | Current reality |
|---|---|
| `.asm` engine sources, AS syntax | The `.emp` tree: `sigil build` IS the build; the `.asm` code twins are deleted. Every code block in Tasks 2/3/6 must be translated to `.emp` (module header, `proc` with `clobbers/preserves/out/requires`, `if DEBUG == 1 {}` instead of `ifdef __DEBUG__`, bare-symbol operands width-select automatically). |
| `games/sonic4/main.asm` (add `include` lines) | **Deleted.** ROM placement = `games/sonic4/map.toml` (`order` list + anchors/holes/budgets) + the sigil-harness native driver. Every new byte-emitting section (`zx0_resume.emp`, `page_in.emp`, `page_cache.emp` procs/data) must enter map.toml `order`; registry/pins/golden side is **sigil-owned — coordinate with the sigil session** and follow the byte-changing-parcel ritual (SIGIL_BLOB_LEN_DRIFT=warn, rebuild both sigil binaries, repin → refreeze --ab). |
| `ram.asm` edits (`ds.b/ds.w`, "keep even", runtime-boot after change) | `engine/ram.emp` — declared `region lower_ram @ $FFFF0000..$FFFF8000` / `region upper_ram @ $FFFF8000..SYSTEM_STACK` with typed `vars` + `pad()`; alignment/overlap are **compiler checks** now (the AS even-alignment caveat is obsolete). Game RAM chains from `Engine_RAM_End` (`games/sonic4/config/ram.emp`). PageIn/PageCache state is engine-owned → `engine/ram.emp`. DEBUG-only counters go in the existing `if DEBUG == 1 @shape_divergent` blocks (see ram.emp:471–557 commentary on Engine_RAM_End rippling). |
| `constants.asm:118-140,326-370` | `engine/system/constants.emp` — `ART_POOL_PAGE_TILES`/`ART_HDR_*`/`ART_VER_*` at :228–232, `ART_STAGING_BUFFER_SIZE` at :383. |
| `structs.asm` | `engine/structs.emp` (Act at :28, field names verbatim `act_*`; no manual `Act_len` — `sizeof` is compiler truth, so the plan's "+ pad + update length constant" step shrinks to "append field; the typed literal + struct harvest catch drift"). |
| Build: `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh` | Stale. Sound is ON in the plain build since the engine/game split; `DEBUG=1 ./build.sh` emits **suffixed** artifacts `s4.debug.bin`/`s4.debug.lst` (the two shapes never collide). Shapes: plain release / DEBUG / config-a (hotkeys+mirror) / config-b (silent) / `--lean`. Oracle symbol cross-checks use `s4.debug.lst` for debug ROMs. |
| Branch/commit rules | Unchanged and load-bearing; ADD: verify branch before commit (parallel sessions share the tree) and never plain-`./build.sh` in a shared hot tree mid-session without byte-verifying the loaded ROM afterward. |
| Baseline numbers (Task 1 + spec §5) | Lower-RAM slack "9,150 B" is stale → 6,078 B post-H5, itself unverified since the hardening chains — **re-measure from the fresh `.lst` at Task 1**. Idle baseline: use the 2026-08-05 table (74.3% rest / 67.8% max-H / 33.2% diagonal window), not the 2026-06-22 figures. |

## Per-task anchors

| Task | Stale anchor | Current anchor |
|---|---|---|
| 1 | `engine/system/vblank.asm:1-60,167-184` | `engine/system/vblank.emp` — `VBlank_Handler` :40–58, `VInt_Level` :71, `VInt_Lag` :192, `VSync_Wait` :274–302 (**new since the plan:** the flag-clear/Ready-set pair is `with ints_off`-atomic; the decode-slice call must go after the bracket — see sketch §3) |
| 1 | `engine/system/game_loop.asm:1-20` | `engine/system/game_loop.emp` (GameLoop :28–44; note `invoke Game.debug_tick` + `Input_Tick` replay seam now sit between VSync and state dispatch) |
| 1 | `engine/compression/zx0_decompress.asm` | `engine/compression/zx0.emp` (`ZX0_Decompress` :58; elias `jbsr` sites :65/:75/:90/:100 — the inline targets) |
| 1 | `constants.asm:118-140,326-370`, `ram.asm:10-43` | see global table |
| 2 | Create `engine/compression/zx0_resume.asm` | `engine/compression/zx0_resume.emp` + map.toml `order` entry (+ sigil registry — coordinate). The Task-2 listing itself is verified against live `zx0.emp` control flow (sketch §1) but needs `.emp` translation; the "no stack / registers only" contract is the `@resumable` Sigil ask — **Task 2 is gated on sketch §6 asks 1–2 (or an agreed interim waiver)**. |
| 2 | "self-test bank — grep `golden`/`SelfTest`" | `engine/debug/compression_selftest.emp` (`CompressionSelfTest` :43). Placed only in debug shapes (map.toml: s4_debug/config_a). ⚠ its tail comment (:117–124) documents a measured island-span/pad interaction — read before appending code to this module. |
| 2 | `OJZ_Act_Pool_PageTable` | Page table rides the Act descriptor: `act_art_pool_table`/`act_art_pool_pages` (structs.emp :39–40), generated manifest module `games.sonic4.ojz_act_pool_manifest_act1` (`ojz_act_pool_manifest.emp`), page sections `OJZ_Act_Pool_Page0…`. |
| 3 | `vblank.asm:8-29` hook site; `VBH_STACKED_PC = 15*4+2` | `vblank.emp:41` (`movem.l d0-a6,-(sp)` unchanged — offset 62 survives). Prefer the Sigil `irq_frame` accessor ask over the hand constant (sketch §6.3). Hook + BankRegs/resume need Sigil asks 3–5. |
| 3 | `VSync_Wait` "after `VBlank_Ready` is set, before the spin" | Still correct, but **after the `with ints_off` bracket** (vblank.emp:290–293). NEW: `VSync_Wait`'s `clobbers(d0)` widens to the PageIn union — contract-surgery ripple through `Level_LoadArt` (and any future caller); budget an explicit step (sketch §3). |
| 3 | "check HInt vector in main.asm; if bare rte, negligible" | Resolved: `engine/system/hblank.emp` — RAM-slot dispatch, handlers contract-bound interrupt-transparent + rte-terminated. Nested-HInt is safe by contract; note it and move on. |
| 4 | `load_art.asm:56-92`, `:23-29`, `:79` | `engine/level/load_art.emp` — `Art_Decompress` :46, `Level_LoadArt` :103–155, `QueueDMA_Critical` call :128 (drop-retry loop :150–153 is the retry idiom the queue-route step replaces). |
| 4 | `dma_queue.asm:38-57` enqueue API | `engine/system/dma_queue.emp` — `QueueDMA_Critical/Important/Deferrable` :94–106 (`out(carry: dropped) preserves(sr.mask)` — the carry contract the FIFO mirrors), drains :271–371. |
| 5 | `ojz_strip_gen.py` Pass 5 `:1280-1294`, Pass 6 `:1320-1324`, manifest `:1364-1372` | Pass 5 :1313, Pass 6 :1352, **Pass 6b (BG blob) :1360 now sits between**, manifest is **Pass 7** :1396–1406 and emits an `.emp` module (not `.asm`). `remap_nametable_word` lives in `tools/tile_dedupe.py` (used at :371–389). Daemon-watch + ask-user rule unchanged. |
| 5 | `build.sh:75-111` per-page compression | build.sh is 168 lines now: salvador vendored-build :112–117, page-blob handling near :138; the one-invocation sigil build at :146–151. Raw-election logic likely belongs beside the salvador step — re-read at execution. |
| 5 | `tile_cache.asm:293-307` / `:1130-1131` translate sites | `tile_cache.emp` — `TileCache_CopyBlockColumn` :302 (proc head), `TileCache_FillRow` :1334; find the staged-word write loops inside each at execution time (bodies re-shaped by the H6 hoist). |
| 6 | keyed-resume pattern `:976-980,1161-1168` | Resume-keyed commits now at :807 (`Cache_Head_Col`, column), :906/:947 (rows); **:973–1037 is the H4 trailing-lag gate + row prefetch scan** — do not confuse the two when borrowing the pattern. |
| 6 | `PAGE_FRAMES = 15` etc. in constants/structs | Same homes as global table; PageFrame struct in `.emp` struct syntax; DEBUG audit walk gated `if DEBUG == 1`. |
| 7 | prefetch `tile_cache.asm:809-891` (`Cache_Prev_Cam_Row` diffing) | Superseded by the shipped unified prefetch (H1–H5, 2026-07-16): row scan ~:998–1037, column scan ~:1155, corner ~:1215, direction hysteresis latch, `Cache_Pfx_Row_Target`/`Col_Target` (:1033/:1155) — the page prefetch should consume these richer signals, and 16 staging slots (H5) are already live. Trailing-lag latch precedent: :693/:696 set, :979–986 consume. |
| 8 | `dma_queue.asm:57-133` `QueueDMATransfer` | No such symbol — the unified enqueue is the three `QueueDMA_*` procs + shared internals (dma_queue.emp:94–133 region); per-frame budget reset is `VInt_Level` vblank.emp:97 (`DMA_Budget_Default → DMA_Budget_Remaining`) — the dual-cap reset goes beside it. 128KB-split atomic-rollback requirement unchanged. |
| 9 | Act struct + `act_descriptor.asm` + `Act_len = $22` | `engine/structs.emp:28` + `games/sonic4/data/levels/ojz/act1/act_descriptor.emp` (:77 `pub data OJZ_Act1_Descriptor: Act = Act{…}` — a **typed literal**, so the new field is compiler-checked; no `Act_len` bookkeeping). Editor-exporter drift warning: `data/editor/ojz/act1/export/` now holds `section_*.{art,coll,tiles}.bin` streams — **re-verify whether a stale descriptor exporter still exists at all** before carrying the plan's warning forward. Daemon-watch on `data/editor/ojz/` unchanged. |
| 10 | `camera.asm`, `CAM_MAX_X_STEP` at `constants.asm:402` | `engine/level/camera.emp` — **`CAM_MAX_X_STEP` is now a file-local const at camera.emp:21**; `CAM_MAX_Y_STEP` comes from engine.constants. Clamp splice points documented at camera.emp:80–120. |
| 11 | generator flag + pytest `tools/` | pytest = inline `def test_*` functions in `ojz_strip_gen.py` itself (:641–770) — extend there; `python3 -m pytest tools/ -q` still the runner. Fixture design unchanged. |
| 12 | ARCH §9.7 rewrite + doc sweep | Replacement text + full cross-ref table already drafted: `../2026-08-06-arch-97-rewrite-proposal.md` (covers ARCH :1312/:1390/:1437/:3802-3835/:3844/:3885, DEFERRED_WORK :55-64/:714-733/:746/:866-875, CLAUDE.md line). |
| 12 | "FF or merge commit per repo habit" | Habit is merge commits on `master` (see recent chain); keep. |

## New standing rules the rewrite should absorb

1. **Sigil coordination is a first-class dependency**: Tasks 2–3 are gated on
   the contract asks (sketch §6); every byte-emitting change rides the parcel
   ritual; map.toml `order` is part of every "Files:" list.
2. **Contract surgery is work, not friction**: the VSync_Wait license widening
   (Task 3) and Level_LoadArt's re-fold are explicit steps with their own
   verification, not incidental fallout.
3. Oracle gotchas current as of 2026-08-05: absolute-path `reload_rom` +
   crc-verify (relative path silently loads no cart), `press` not `hold`,
   screenshots via the input-replay net, `pgrep -a`.
