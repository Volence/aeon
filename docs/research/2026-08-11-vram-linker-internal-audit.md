# Internal audit — every VRAM consumer, blast radius, and the full 0..2047 map

**Provenance:** research subagent output, 2026-08-11, dispatched for the
VRAM-linker design (see docs/research/2026-08-11-vram-allocation-brief.md).
Banked verbatim from the agent transcript.

---

# VRAM Occupancy Audit — Aeon Engine (branch `feat/character-dispatch`, commit `8265772e`)

READ-ONLY research pass. All line numbers verified against the working tree at HEAD (`8265772e feat(vram): surrender the top FG pool page to the dust windows`). `.worktrees/*` copies excluded throughout — they are stale mirrors, not distinct consumers.

## 1. Complete occupancy map, tiles 0..2047

### POST-CHANGE map (current HEAD, `POOL_TILE_CEILING=896`)

| Tiles (dec) | VRAM bytes | Size | Owner symbol | Defined at |
|---|---|---|---|---|
| 0–895 | $0000–$6FFF | 896 | FG act art-pool residency cache (`PAGE_FRAMES`×`ART_POOL_PAGE_TILES` frames) | `engine/system/constants.emp:590` (`POOL_TILE_CEILING`), `:252` (`PAGE_FRAMES`) |
| 896–911 | $7000–$71FF | 16 | `VRAM_DUST_PUFF` (resident, 4 anim frames × 4 tiles) | `games/sonic4/config/constants.emp:266` |
| 912–923 | $7200–$73FF | 12 | `VRAM_DUST_SPINDASH` (DPLC window) | `games/sonic4/config/constants.emp:271` |
| 924–959 | $7400–$77FF | 36 | **FREE** (explicit spare — page-quantised carve leftover) | called out in comment, `games/sonic4/config/constants.emp:258` |
| 960–991 | $7800–$7BFF | 32 | `VRAM_TEST_SONIC` — the character DPLC window (shared by whichever character is resident) | `games/sonic4/config/constants.emp:236` |
| 992–999 | $7C00–$7DFF | 8 | `VRAM_TEST_OBJ` — test-object art (2×4-tile squares) | `games/sonic4/config/constants.emp:215` |
| 1000–1015 | $7E00–$7FFF | 16 | `VRAM_RING_PLACEHOLDER` (= `VRAM_TEST_OBJ`+8) — S3K ring art, 4 frames × 4 tiles | `-D` in `sigil/.../native.rs:618` (value `0x3E8`); consumed `engine/objects/rings.emp:36` |
| 1016–1019 | $8000-4… | 4 | `VRAM_TEST_MARKER` (= `VRAM_TEST_OBJ`+$18) — debug-fly 2×2 marker | `games/sonic4/config/constants.emp:224` |
| 1020–1023 | | 4 | **FREE** (confirmed gap) | between `VRAM_TEST_MARKER` end (1020) and `BG_TILE_BASE_VRAM` (1024) |
| 1024–1471 | $8000–$B7FF | 448 | `BG_TILE_BASE_VRAM` shared zone-wide BG tile region (`BG_TILE_CAPACITY`) | `engine/system/constants.emp:452,454` |
| 1472–1491 | $B800–$BA7F | 20 | `VRAM_SPRITE_TABLE` (SAT) — 80 sprites × 8B | `engine/system/constants.emp:346` |
| 1492–1500 | $BA80–$BC5F… | 9 | `VRAM_TAILS_APPENDAGE` — twin-tail DPLC window | `games/sonic4/config/constants.emp:248` |
| 1501–1503 | | 3 | **FREE** (confirmed gap) | remainder of the 12-tile SAT↔HScroll span not used by the 9-tile appendage window |
| 1504–1531 | $BC00–$BD8F… | 28 | `VRAM_HSCROLL_TABLE` — line-scroll table (896 B / 32) | `engine/system/constants.emp:347` |
| 1532–1535 | | 4 | **FREE** (new gap found — not previously documented) | remainder of the $400 (32-tile) slot between `VRAM_HSCROLL_TABLE` ($BC00) and `VRAM_PLANE_A` ($C000); only 28 of 32 tiles are used by the 896-byte HScroll DMA |
| 1536–1791 | $C000–$DFFF | 256 | `VRAM_PLANE_A` — 64×64-cell nametable | `engine/system/constants.emp:444` |
| 1792–2047 | $E000–$FFFF | 256 | `VRAM_PLANE_B_BYTES` / `VRAM_PLANE_B` — 64×64-cell nametable | `engine/system/constants.emp:348,445` |
| — | $F000 | (inside Plane B) | `VRAM_WINDOW` (tile 1920) — disabled, deliberately overlaps Plane B; VDP never fetches it (regs $11/$12=0) | `engine/system/constants.emp:446`; rationale comment `engine/system/boot_data.emp:125-131` |

Free tiles total: 36 (924-959) + 4 (1020-1023) + 3 (1501-1503) + 4 (1532-1535) = **47 tiles genuinely unassigned**, plus whatever slack exists inside the 896-tile pool / 448-tile BG region / DPLC windows when a specific act/character doesn't use its full budget (Sonic's DPLC peak is 29/32 tiles, Tails' is 24/32 — see §2).

### PRE-CHANGE map (before commit `8265772e`, `POOL_TILE_CEILING=960`)

Everything above tile 960 is identical; the difference is entirely in 0–959:

| Tiles | Owner | Note |
|---|---|---|
| 0–959 | FG act art-pool (`PAGE_FRAMES`=15 × 64) | no dust windows existed |
| 960–991 | `VRAM_TEST_SONIC` | unchanged |
| 992+ | unchanged | unchanged |

The dust windows (`VRAM_DUST_PUFF`/`VRAM_DUST_SPINDASH`) and the 924-959 spare did not exist pre-change; the pool simply ran one full page (64 tiles) further, to 959. Diff: `git show 8265772e -- engine/system/constants.emp` (quoted above in my working notes) — `PAGE_FRAMES` 15→14, `POOL_TILE_CEILING` 960→896.

## 2. Per-consumer: how the art gets there

| Consumer | Load site (file:line) | Mechanism | DMA priority | Lifetime |
|---|---|---|---|---|
| FG act art pool (0-895) | `engine/level/load_art.emp:52` (`Level_LoadArt`) init bulk load → `engine/level/page_in.emp:104` (`PageIn_Process`) landing → `engine/level/page_in.emp:519` (`QueueDMA_Important`) | S4LZ/ZX0 page-in, resumable idle-time decoder (§9.7), demand + prefetch during gameplay | **Important** (`PageIn_EnqueueLanding`, `page_in.emp:519`) | Act (paged residency cache; degenerates to fully-resident when the act's pool fits `PAGE_FRAMES_CLAMP`) |
| `VRAM_DUST_PUFF`/`VRAM_DUST_SPINDASH` | **No load site exists yet.** Constants declared (`games/sonic4/config/constants.emp:266,271`) and asset generator shipped (`games/sonic4/data/dust_staging/gen_dust.py`), but no `.emp` object consumes `VRAM_DUST_PUFF`/`VRAM_DUST_SPINDASH` anywhere in the tree (verified: zero hits outside the two constants files) | n/a — reserved, unconsumed | n/a | Reserved-but-dead: the VRAM carve landed ahead of the object wiring |
| `VRAM_TEST_SONIC` (character window) | `games/sonic4/objects/test_animated.emp:52`, `games/sonic4/objects/test_player.emp:308`, `games/sonic4/player/player_common.emp` (via `Perform_DPLC`) | DPLC streamed per-frame, `engine/objects/dplc.emp:137` (`Perform_DPLC`) | **Important** (`dplc.emp:138`) — player uses this tier | Character-state-specific: only the currently-resident character's DPLC targets it; also DOUBLE-USED as the `GS_OBJECT_TEST`/`GS_OJZ_SCROLL_TEST` debug-state art window (see aliasing note below) |
| `VRAM_TEST_OBJ` | `games/sonic4/data/objdefs/test_objects.emp:24,27`, `games/sonic4/objects/path_swap.emp:58`, `games/sonic4/test/object_test_state.emp:403,407` | One-shot DMA at object load (`vram_art`/`vram_bytes` baked into `ObjDef.art_tile`, DMA'd by `Load_Object`) | not traced to a specific queue in this pass — object load path, not DPLC | Game-state-specific (test/debug objects only) |
| `VRAM_RING_PLACEHOLDER` | `engine/objects/rings.emp:36` (`RING_ART_ATTR`); art blob loaded at `games/sonic4/test/ojz_scroll_test.emp:129` (`vram_bytes(VRAM_TEST_OBJ)` region DMA which includes the ring blob immediately after) | One-shot DMA at level/test-state init | traced to test-state init DMA, priority not confirmed in this pass | Act (loaded once, rendered by every ring object for the act's life) |
| `VRAM_TEST_MARKER` | `games/sonic4/player/player_common.emp:1144` | One-shot art write (debug-fly marker) + VDP write at `games/sonic4/test/ojz_scroll_test.emp:190` | direct `vdp_comm`/`VDP_CTRL` write, not queued DMA | DEBUG-cheat-specific (`CHEAT_DEBUG_FLY`) |
| `VRAM_TAILS_APPENDAGE` | `games/sonic4/objects/tails_appendage.emp:175` (art_tile write), DPLC via `Perform_DPLC`/`Perform_DPLC_Deferrable` | DPLC streamed per-frame | Important or Deferrable (appendage is a non-player object — likely Deferrable per `dplc.emp:152` convention "used for non-player objects", not directly confirmed at the appendage's own call site in this pass) | Character-state-specific (Tails only; second simultaneously-resident sprite) |
| Shared BG region (1024-1471) | `engine/level/bg.emp:67` (`BG_Init`), called from `Level_LoadArt` tail-call `engine/level/load_art.emp:154` | Blocking CPU-driven VDP_DATA writes (`with z80_stopped { move.l (a1)+, (a2) }`, `bg.emp:122-129`) — **not** a DMA-queue transfer | n/a (blocking, display-off) | Act (loaded once at level init before display-on) |
| Plane A/B nametables (init blit) | `engine/level/bg.emp:132-166` (Plane B), title/menu path `engine/system/buffers.emp:184` (`PlaneMapToVRAM`, unconsumed today) | Blocking CPU-driven VDP writes, column-major autoinc $80 | n/a | Act (init) |
| Plane A/B nametables (per-frame streaming) | `engine/level/plane_buffer.emp:442` (`VInt_DrawLevel`), drains `Plane_Buffer` ring during VBlank | Direct CPU writes to `VDP_DATA`/`VDP_CTRL` inside the VBlank bracket — **not** the DMA queue | n/a | Per-frame, continuous during play |
| `VRAM_SPRITE_TABLE` (SAT) | Boot pre-init `engine/system/buffers.emp:75` (`Init_SpriteTable`), static entry built `buffers.emp:138-142` (`BuildStaticDMA`), enqueued every VBlank `buffers.emp:212` (`Enqueue_Dirty_Buffers`) | Static pre-built `DMAEntry`, enqueued via `queue_static_dma` | **Critical** (`DMA_Critical_Slot`, `buffers.emp:45-61`) | Boot-permanent structure, content updated every frame |
| `VRAM_HSCROLL_TABLE` | Static entries built `buffers.emp:145-156` (cell mode 112B, line mode 896B), enqueued via `Enqueue_Dirty_Buffers` | Static `DMAEntry` | **Critical** | Boot-permanent structure, updated per-frame (parallax/section) |
| Palette (CRAM, not VRAM but shares the queue) | `buffers.emp:107-131` | Static `DMAEntry` | **Critical** | Boot-permanent / act |
| Demo's `VRAM_DEMO_OBJ` | `games/demo/demo_state.emp:35` (`GameState_Demo_Init`) | One-shot DMA, `jbsr QueueDMA_Critical` line 39 | **Critical** | Boot-permanent for the demo's one game state |

**Aliasing note (important for the redesign):** `VRAM_TEST_SONIC`/`VRAM_TEST_OBJ`/`VRAM_TEST_MARKER`/`VRAM_RING_PLACEHOLDER` are shared between the production player character window and the debug/test game states (`GS_OBJECT_TEST=2`, `games/sonic4/config/constants.emp:34`; `GS_OJZ_SCROLL_TEST=3`, entry state per `games/sonic4/config/game.emp:23`). This works only because those game states are mutually exclusive at runtime — a declared-region packer needs to either model this as an explicit "one of N mutually-exclusive owners" region, or stop sharing it.

## 3. Blast radius per budget constant

### `POOL_TILE_CEILING` (`engine/system/constants.emp:590`)
- `PAGE_FRAMES = POOL_TILE_CEILING / ART_POOL_PAGE_TILES` (`constants.emp:252`), with `ensure` at `:253` that the division is exact.
- `PAGE_FRAMES` sizes **two RAM arrays**: `Page_Frames: [PageFrame; PAGE_FRAMES]` (`engine/ram.emp:115`, `PageFrame` = 8 bytes, `engine/structs.emp:94-102`) and `Page_Audit_Scratch: [u16; PAGE_FRAMES]` (`engine/ram.emp:332`, DEBUG-only).
- `PAGE_FRAMES_CLAMP` (`constants.emp:334`) derives from it for the `STRESS_EVICT` dev fixture.
- Generator copy: `tools/ojz_strip_gen.py:125` (`POOL_TILE_CEILING = 896`, hand-mirrored, "must move with it" per the constant's own comment at `constants.emp:588`). Used only in a printed report string there per the commit message (`8265772e`), so it doesn't gate generated bytes today — but it is a silent-drift risk if that ever changes.
- `games/sonic4/config/constants.emp:266` reads `POOL_TILE_CEILING` directly (`VRAM_DUST_PUFF : VramTile = POOL_TILE_CEILING`) and `ensure`s at `:274` that the dust windows don't overlap it.
- Sigil-side: the commit message for `8265772e` states repin moved 126 RAM pins and the plain/debug ROM CRCs moved (byte-identical lengths) because of the two array-size changes — i.e. **any future edit to `POOL_TILE_CEILING` forces a sigil repin ritual** (`reference_sigil_byte_changing_parcel_ritual` in memory).
- No VDP register or instruction immediate directly bakes this value (it only bounds RAM array sizes and the page-frame math); the register-coupled values are `VRAM_SPRITE_TABLE`/`VRAM_HSCROLL_TABLE`/`VRAM_PLANE_A`/`VRAM_PLANE_B` (§4), which sit far above this ceiling and are unaffected by it directly, EXCEPT that `VRAM_DUST_PUFF`, `VRAM_TEST_SONIC`, etc. are all defined relative to it and must stay below `BG_TILE_BASE_VRAM`.

### `VRAM_TEST_SONIC` (`games/sonic4/config/constants.emp:236`)
- Consumed directly (not via a derived constant) by: `games/sonic4/objects/test_animated.emp:31,52`; `games/sonic4/objects/test_player.emp:61,130,308`; `games/sonic4/player/sonic.emp:42` (`cd_vrambase`); `games/sonic4/player/tails.emp:70` (`cd_vrambase`); `games/sonic4/data/collision/collision_data.emp:31` (`ensure`); `games/sonic4/data/characters/tails_data.emp:76` (`ensure`).
- Two `ensure()` build-time walls key off it as the base for character DPLC-peak checks (Sonic 29 tiles measured, `collision_data.emp:26-32`; Tails 24 tiles, `tails_data.emp:66-77`) — these are the guards that would fire if art grew past the 32-tile window.
- `VRAM_TEST_OBJ = $03E0` (992) is an independent literal, not derived from `VRAM_TEST_SONIC`; the window's upper wall is checked only via the `ensure`s above, not a compile-time subtraction — i.e. moving `VRAM_TEST_SONIC` does NOT automatically resize the window; a packer must re-derive both together.

### `VRAM_TEST_OBJ` (`games/sonic4/config/constants.emp:215`)
- Feeds `VRAM_TEST_MARKER = VRAM_TEST_OBJ + $18` (`:224`), and (via native.rs `-D`) `VRAM_RING_PLACEHOLDER = 0x3E8` (`VRAM_TEST_OBJ + 8`, sigil `native.rs:618` etc. — five separate profile blocks: `sonic4_profile` `:618`, `config_b_profile` `:775`, `config_a_profile` `:834`; demo's own `demo_profile` uses `0x3E4` = `VRAM_DEMO_OBJ+4` at `:706`).
- Consumed by nine `.emp` files as a direct art-tile base: `test_objects.emp:24,27`; `path_swap.emp:58`; `test_churn.emp`, `test_emitter.emp`, `test_helpers.emp:29`, `test_parent.emp`, `test_stress_emitter.emp` (all via `use games.sonic4.constants.{VRAM_TEST_OBJ}`); `object_test_state.emp:69,255,403,407`; `ojz_scroll_test.emp:129`.
- The dust `ensure` chain (`games/sonic4/config/constants.emp:278`) checks `VRAM_DUST_SPINDASH + DUST_SPINDASH_TILES <= VRAM_TEST_SONIC` — so `VRAM_TEST_OBJ` is downstream of the dust carve only transitively (it sits above `VRAM_TEST_SONIC`, which is itself walled from the dust windows).

### `VRAM_RING_PLACEHOLDER` (`-D` only, no `.emp` authority)
- Values: sonic4/config_a/config_b = `0x3E8` (1000); demo = `0x3E4` (996) — five call sites in `sigil/crates/sigil-harness/src/native.rs:618, 706, 775, 834`, plus a fifth line not fully enumerated in this pass (search `emp_defines` blocks near line 885 — same pattern).
- Consumed by `engine/objects/rings.emp:36` (`RING_ART_ATTR = vram_art(VRAM_RING_PLACEHOLDER, 1, 1)`), guarded by `ensure(extern("RING_WIDTH") == RING_WIDTH)` at `rings.emp:41` but **no** `ensure` on the placeholder's numeric value itself against a game authority — its drift net is explicitly "six-target byte-identity" (comment `rings.emp:37-40`), i.e. a wrong `-D` is only caught by full-ROM CRC comparison across the six shipped shapes, not a build-time assert.
- Downstream art: 16-tile S3K ring blob (`games/sonic4/test/ojz_scroll_test.emp:563-573`, `RingArt`/`TestArt_Ring`).

### `VRAM_TEST_MARKER` (`games/sonic4/config/constants.emp:224`)
- Sole consumer: `games/sonic4/player/player_common.emp:1144` (art_tile write) and `games/sonic4/test/ojz_scroll_test.emp:190` (raw VDP write of the CRAM-index-12 marker color).

### `VRAM_DUST_PUFF` / `VRAM_DUST_SPINDASH` (`games/sonic4/config/constants.emp:266,271`)
- Both derive from `POOL_TILE_CEILING` and each other; three `ensure`s at `:274-279` wall them against the pool and `VRAM_TEST_SONIC`.
- `tools/ojz_strip_gen.py:125` carries the matching `POOL_TILE_CEILING=896` Python copy — the commit that moved the engine constant moved this file in the same commit (lockstep, enforced by convention not by a build check).
- **No sink**: as noted in §2, no object code reads either constant yet. Blast radius today is "constants + generator only".

### `BG_TILE_BASE_VRAM` / `BG_TILE_CAPACITY` (`engine/system/constants.emp:452,454`)
- `BG_TILE_CAPACITY` (448) is explicitly **not read by any engine `.emp` code** — its own comment says so (`constants.emp:451`, "gates the build tools; engine code doesn't read it").
- At runtime, `engine/level/bg.emp:51` independently re-derives the same 448 as `BG_TILE_REGION_BYTES = VRAM_SPRITE_TABLE - BG_TILE_BASE_VRAM` (in bytes; 448 tiles) and clamps the copy to it at `bg.emp:88-90`. **This means there are two independent sources for the same 448-tile fact**: the engine's own runtime-derived value (auto-follows `VRAM_SPRITE_TABLE` if that ever moves) and the standalone `BG_TILE_CAPACITY` constant plus its hand-carried Python copies:
  - `tools/inject_editor_bg.py:18,21` (`BG_TILE_BASE_SLOT=1024`, `BG_TILE_CAPACITY=448`)
  - `tools/ojz_strip_gen.py:263-264` (`BG_TILE_BASE_SLOT_PY=1024`, `BG_TILE_CAPACITY_PY=448`), enforced at `:1892-1894`
  - `tools/png_to_bg_override.py:33` (`BG_TILE_CAPACITY=448`), enforced at `:164-165`
  - A packer that relocates `BG_TILE_BASE_VRAM` or `VRAM_SPRITE_TABLE` must update **four** independent copies of "448" by hand (one `.emp` constant + three Python literals); only `bg.emp`'s own derivation would self-correct.

### `VRAM_SPRITE_TABLE` / `VRAM_HSCROLL_TABLE` / `VRAM_PLANE_A` / `VRAM_PLANE_B` / `VRAM_WINDOW`
- Feed `MAX_VDP_SPRITES * 8` SAT-size math in the `VRAM_TAILS_APPENDAGE` guards (`games/sonic4/config/constants.emp:249-252`).
- Feed `BG_TILE_REGION_BYTES` (§ above).
- Feed the static DMA entries (`buffers.emp:141,148,156`).
- Feed the runtime nametable writers (`plane_buffer.emp:96,128,253,411`; `section.emp:292,330,412`; `bg.emp:124,155`).
- **Not** wired to the boot-time VDP register bytes — see §4, this is the key gap for a redesign.

## 4. VDP-register-coupled values

`engine/system/boot_data.emp:121-153` (`BootData_VDPRegs`) is the sole VDP register-init site (24 registers, $00-$17), consumed by `engine/system/boot.emp:100-151` and shadow-mirrored by `engine/system/vdp_init.emp:21` (`VDP_Shadow_Init`). The bytes are **hand-computed literals with explanatory comments**, not derived from the named constants:

| Reg | Byte | Encodes | Matches constant | Derivation is… |
|---|---|---|---|---|
| $02 | `$30` | Plane A base $C000 | `VRAM_PLANE_A` | hand-computed, commented (`boot_data.emp:124`) |
| $03 | `$3C` | Window base $F000 | `VRAM_WINDOW` | hand-computed, commented (`:125-131`) |
| $04 | `$07` | Plane B base $E000 | `VRAM_PLANE_B_BYTES` | hand-computed, commented (`:132`) |
| $05 | `$5C` | SAT base $B800 | `VRAM_SPRITE_TABLE` | hand-computed, commented (`:133`) |
| $0D | `$2F` | HScroll base $BC00 | `VRAM_HSCROLL_TABLE` | hand-computed, commented (`:141`) |
| $10 | `$11` | 64×64 scroll-plane mode | `PLANE_H_CELLS`/`PLANE_V_CELLS`=64 | hand-set, not derived |

**Finding for the redesign:** none of these six bytes is computed by an `.emp` `comptime fn` from the named `VRAM_*` constants — they are independent hex literals whose correctness is asserted only by inline comments. A relocation of any of `VRAM_PLANE_A/B`, `VRAM_WINDOW`, `VRAM_SPRITE_TABLE`, or `VRAM_HSCROLL_TABLE` requires a **human to hand-recompute the VDP register encoding** (bit-shifted base-address-to-register-value math) and edit `boot_data.emp` directly; nothing in the build checks that these six bytes still agree with the constants. A packer that reassigns these bases must either (a) also emit correct register bytes, or (b) gain a `vdp_reg`-style comptime encoder wired to the same constants with an `ensure`. `engine/vdp.emp:36-41` (`vdp_reg`) already exists as a general register-command encoder but is used only for the fill/auto-increment commands in `boot_data.emp`, not for the plane/SAT/HScroll base registers.

## 5. Raw VRAM literals outside the constants files — lint baseline

Searched every `.emp` file (excluding `.worktrees/`) for `vram_bytes(`, `vram_art(`, and bare VRAM-range hex literals (`$8000`, `$B800`, `$BC00`, `$C000`, `$E000`, `$F000`).

**Result: zero violations of "no undeclared VRAM literal in a `vram_bytes()`/`vram_art()` call".** Every one of the 29 call sites across the tree passes a named constant (`VRAM_TEST_SONIC`, `VRAM_TEST_OBJ`, `VRAM_TEST_MARKER`, `VRAM_DEMO_OBJ`, `VRAM_RING_PLACEHOLDER`). The apparent `vram_art(tile` / `vram_bytes(tile` hits are the **function definitions themselves** (`engine/objects/objdef.emp:32,45` — parameter named `tile`), not literal call sites.

The only bare hex literals in the $8000-$FFFF byte range that are **not** VRAM-related are the Z80 sound-driver's own $8000-window banking scheme (dozens of hits across `engine/sound/*.emp`, `games/sonic4/data/sound/*.emp`) — that `$8000` is the Z80's ROM-bank window base, an entirely different address space, not Genesis VRAM. These should be excluded from any future VRAM-literal lint by scoping it to files that `use engine.constants.{VRAM_*}` or touch `VDP_DATA`/`VDP_CTRL`.

The one genuine baseline violation is the **VDP register byte literals** in `boot_data.emp:124,131,132,133,141` (§4) — six bytes that encode VRAM addresses without going through any `vram_*` helper or named constant. A "no undeclared VRAM literal" lint should either special-case this table or force it through a `vdp_plane_reg()`-style comptime encoder.

## 6. Demo game (`games/demo/`)

`games/demo/config/constants.emp` declares exactly one VRAM constant:

- `VRAM_DEMO_OBJ : VramTile = $03E0` (tile 992) — `constants.emp:34`. Identical numeric value to sonic4's `VRAM_TEST_OBJ`, but a **separate declaration** (no shared module) — the engine/game split means each game owns its own copy of "tile 992" independently; there's no structural link forcing them to agree, they just happen to both use the free gap below the BG region.
- `VRAM_RING_PLACEHOLDER` for demo is a per-profile `-D` = `0x3E4` (996) = `VRAM_DEMO_OBJ + 4`, homed in `sigil/.../native.rs:706` (`demo_profile`), not in any `.emp` file (same "-D-not-in-.emp" rule as sonic4).
- Art: `games/demo/data/demo_data.emp:54-64` — 4 solid tiles (indices 0-3) + 1 blank tile (index 4, the ring placeholder slot) = 5 tiles total, DMA'd whole via `QueueDMA_Critical` at `games/demo/demo_state.emp:31-39`. Everything else the demo needs (SAT, HScroll, Plane A/B, BG region) is the **same engine-owned fixed layout** as sonic4 — the demo carries no BG art (`BgAnim_Table` header only, `demo_data.emp:79`, band_count=0) and no character DPLC window at all (no player, no `VRAM_TEST_SONIC` equivalent).
- Demo's VRAM footprint is therefore a strict subset of sonic4's: only `VRAM_DEMO_OBJ`/`VRAM_RING_PLACEHOLDER` in the "free gap below BG" region are game-owned; tiles 0-895 (FG pool) are declared in the engine but the demo ships `HAS_ACT_ART_POOL=0` (`sigil/.../native.rs:700`), so the pool is present as an address range but never populated for demo.
- Two-game confirmation for the redesign: **the "free gap below BG" (960-1023) is allocated per-game, not per-engine**, and the two games' allocations happen to be numerically compatible only by coincidence (both start at tile 992) — a declared-region packer needs a per-game region set, not a single global one, exactly as the engine/game split already implies architecturally.

## Cannot-determine / needs follow-up

- Exact DMA priority tier for `VRAM_RING_PLACEHOLDER`'s art load and `VRAM_TAILS_APPENDAGE`'s DPLC calls at their specific call sites (only the two general `Perform_DPLC`/`Perform_DPLC_Deferrable` entry points were confirmed, not which one each specific object routine calls — would need to read `tails_appendage.emp`'s DPLC call site directly, `games/sonic4/objects/tails_appendage.emp:365` area).
- Whether `sigil`'s `pins.rs`/frozen-table mechanism holds any **VRAM-address** pins (as opposed to RAM/ROM address pins) — the `8265772e` commit message only mentions RAM pins moving; I did not find a VRAM-specific pin table in this pass and did not exhaustively search `sigil/crates/*/pins.rs` beyond the `native.rs` `emp_defines` grep.
- Whether `VRAM_RING_PLACEHOLDER`'s fifth `emp_defines` block (`native.rs` around line 885, `lean_profile` or an off-canonical profile) matches `0x3E8` or diverges — grep showed 5 occurrences total but I only named 4 profiles explicitly (`sonic4_profile`, `demo_profile`, `config_b_profile`, `config_a_profile`); the fifth needs a direct line-number check if it matters to the redesign.
