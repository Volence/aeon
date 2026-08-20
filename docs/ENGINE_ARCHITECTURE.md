# Sonic 4 Engine Architecture

Target design document for the Sonic 4 engine. Describes the final-state architecture as a coherent system — what each subsystem does, how it works, why this approach was chosen, and how it interacts with other subsystems.

This is the **design bible**. This document describes the engine we're building from scratch in `aeon/`.

**Sources:** S.C.E. (Sonic Clean Engine), Batman & Robin (Clockwork Tortoise), Vectorman (BlueSky), Gunstar Heroes (Treasure), Alien Soldier (Treasure), Thunder Force IV (Technosoft), Flamewing's community tools, SGDK (Stephane-D), Amiga demoscene, modern homebrew (Xeno Crisis, Tanglewood, Demons of Asteborg), Titan Overdrive tech demos, Kabuto hardware research, plutiedev, modern engine design principles.

---

## System Index

| # | System | Key Decisions |
|---|--------|---------------|
| 0 | Hardware Init & Boot | SSP at $FFFFFF00 (Treasure/Vectorman — stack isolated from game data), RAM-patched HBlank+VBlank vectors (interrupt dispatch table — modern event system), VDP shadow table with dirty tracking (NOVEL Aeon design — only changed registers written during VBlank; the "Batman" credit was wrong, corrected 2026-08-14, see §0.4), DMA-parallel init (VRAM fill runs while CPU clears RAM/inits Z80 — modern async I/O), compile-time VDP register table with AS validation, soft-reset detection + DMA-safe warm path (warm boot falls through to full init; nothing is preserved by design — §0.11), region detection with region-adaptive DMA budget (NTSC-only), 6-button controller port init, Z80 init with YM2612-safe timing, build-time sine table generation |
| 1 | Core VDP Pipeline | 3 priority sub-queue DMA, hybrid unrolled/looped drain, static DMA for fixed transfers, variable hscroll dirty tracking, adaptive byte budget, DPLC lookahead, deferred plane buffer, HUD dirty flags |
| 2 | Art & Compression Pipeline | Two-tier compression (measured 2026-06-11): S4LZ v3 (word-aligned LZ + per-section block dictionaries, ~510-640 KB/s) for the runtime block path; ZX0 (~76 KB/s, zlib-class ratio) for load-time tile art. The FG act art pool ships as ZX0 pages; S4LZ remains the runtime block-stream format. Uncompressed sprite art + improved DPLC/DMA (zero CPU, proven by every commercial Genesis game — UFTC dropped after 0.82-0.86 ratio on real data, see `docs/research/tile-format-survey.md`). Raw tilemaps (menu/level select). **Unified VRAM art pool $000-$5BF (1,472 tiles)**, **64×64 scroll planes** ($9011 — validated by Vectorman, enables ±288px vertical buffer + VSRAM deformation), **build-time tile deduplication + spatial pool ordering + paging** (globally-deduped, spatially-ordered, paged act art pool — no per-section allocation), **character DPLC art in the pool ($3C0) + SAT/HScroll in a sub-Plane-A region ($5C0-$5FF) — off-screen-row embedding retired so both 64-row planes stream freely**. Whole-act paged art pool as a **VRAM residency cache** (§9.7): small 64-tile ZX0/raw pages streamed in on demand + prefetch via the supervisor-bookmark idle-time decoder, capped by ROM not VRAM — degenerates to fully-resident for acts whose window fits the pool (e.g. OJZ). Per-section BG support. DPLC improvements: lookahead (NOVEL — predictive pre-load), priority integration, generic Perform_DPLC, build-time contiguous art layout. Nemesis/Kosinski/Comper/Enigma/UFTC not used |
| 3 | Object System | $50 SST with hot/cold reorder (novel), free slot stack O(1) allocation (beats all references), data-driven child creation (4 strategies from S.C.E.), collision_response type dispatch with width/height from SST (novel — more modular than any reference), animation events as behavior sequencer (novel), per-frame delays, multi-sprite animation, per-frame art via DPLC/DMA from uncompressed ROM, **sprite link-order cycling (overflow fairness)**, **sprite X=0 masking (hardware clipping)**, **scanline-aware sprite budgeting** |
| 4 | Level / World | 2D section grid with signed Y (novel), **continuous world-space camera over a 64×64 wrapping VDP plane (classic S2/S3K — no slots, no teleport, no rebase)**, full-height vertical streaming with a grid-derived camera clamp, **per-act vertical `edge_mode` (CLAMP shipped / WRAP_V + KILL deferred hooks)**, edge streaming into the wrapping plane (always-on "see into the next section"), block-based 2D tile cache (Batman — eliminates chunks/blocks from RAM), deferred plane buffer (S.C.E.+overflow fix), 8-layer computed parallax with dual FG/BG deformation + per-block linear interpolation (TF4+S.C.E.), per-section everything (snapped on section-boundary crossing), **camera-driven entity window with 3×3 rolling collected bitmask (novel)**, **section-local entity ROM data (positions relative to section, respawn/kill memory keyed by section_id — coordinate-invariant)**, per-section type tables, flat X-sorted ring lists, unified ring buffer with 3×3 rolling collected bitmask, player position history buffer, state-dependent camera speed caps, dynamic terrain override, scroll table pre-computation over HInt where possible, **collision embedded in block data (S.C.E.-style per-placement, zero separate maps)**, **per-section full palette copies (128 bytes, instant load)**, floating-origin rebase as the future unbounded-level path (coarse/invisible/atomic — replaces the deleted leapfrog) |
| 5 | Player / Character | **SHIPPED (§5, branch player-system):** flat explicit PSTATE_* state machine + Player_SetState enter/exit hooks (hierarchical was evaluated and REJECTED), classic motion-quadrant + angle-band landing axis-select (the "vector projection on landing" claim was a verified S3K myth — NOT used), effective-physics-table-in-RAM (a4 convention; per-section *plumbing* shipped with an identity modifier — the modifier/Lerp system itself is deferred), air drag apex-only (classic-wide, not an S3K fix), roll-jump lockout kept classic, 2-frame jump buffer + jump-delay fix (the two modern concessions), −$FC0 up-cap REMOVED (feel deviation, PHYS_GSP_CAP coupling), angle continuity for loop stability, level bounds, spindash charge curve (table-based), slope factor muls→shift, landing camera lock + spindash freeze, 3-character shared-code structure via Player_Common (Sonic-only shipped), **SWAP-based 16.16 fixed point (Treasure)**. **SHIPPED (feat/sonic-animations):** shared ANIM_* id contract (11 ids, build-time assert), Player_Animate read-only classifier (priority-ordered, display-conditions not new state bits), DUR_DYNAMIC speed-scaled timing in AnimateSprite, shared spindash in player_spindash.emp, Player_AtLedgeEdge balance probe, _pl_look_offset zero-seam, DEBUG anim viewer. **DEFERRED:** 6-button mappings, the per-section physics modifier system, multi-character dispatch, shields, dropdash, instashield, get-up trigger, duck/look-up camera pan. See the §5 body + DEFERRED_WORK.md §5. |
| 6 | Audio | **From-scratch custom Z80-autonomous driver** (NOT Flamedriver — the import plan was superseded by the 2026-06-16 master sound spec). **SHIPPED (Plans 1A/1B/1C/1D + Phase 3a):** Z80 shell + mailbox + Timer-A scheduler primitives (1A), DMA-survival single-channel DAC (1B, MegaPCM-2 free-running every-path-equal-cost streaming loop), FM/PSG music sequencer (1C — event-list song format v0, per-channel stream interpreters, FM voice writer with log-volume LUT + per-algorithm carrier mask, PSG tone/noise + pause silence, Timer-A one-overflow-per-tick scheduler, DAC drums via the 1B path, PlayMusic/StopMusic). **Phase 3a FM depth + 1D Moving Trucks (merged `c89bea3`, 2026-06-19):** per-frame modulation engine (write-on-change ModUpdate at ~59.06 Hz, per-channel tempo accumulator over a fixed Timer-A clock), per-song pitch table + pitch envelopes (trills/arps), pan, signed per-op TL bias, voice-stepping via build-time register deltas, hardware LFO ($22=$08), note-fill gate articulation, and a faithful native-sequencer port of B&R 'Moving Trucks'. **ALSO SHIPPED (DAC-drum revision + SFX engine + music-expression spine, through 2026-06-27):** one-shot PCM drums with adaptive FM6 time-share; the **SFX engine** (steal/priority/ducking, `Sound_PlaySFX`); and the **music-expression spine** — software vibrato/`MEV_MODSET` for music, per-frame FM-TL volume envelope (`MEV_FMENV`), inline raw-register write (`MEV_REGWRITE`, $2A/$2B-guarded), SSG-EG load-time per-op patch (`FmPatch` $90 group), dual-stream macro automation (`MEV_MACRO`/`MacroTick` on `sc_mod_ptr` slot[1]), PSG volume envelopes. **ALSO SHIPPED (music-expression Phase 2 + sound-perf phase, through 2026-07-02):** per-note portamento (`MEV_PORTA`, resident) + detune/fine-pitch, global fade (`SND_REQ_FADE`) + S3K-exact tempo (`MEV_TEMPO` accumulator+skip) + hardware-LFO opcode (`MEV_LFO`), measured 59.9227 Hz frame-clock pin, envelope write-on-change. **DEFERRED:** ~~N-channel DAC mixer~~ (REJECTED — single-voice + pre-mixed composites RATIFIED by user 2026-07-03, see §6.2); ~~runtime SSG-EG 7th-RegDelta-group~~ (**SHIPPED 2026-08-10, package 4** — `RegDeltaGroupBase` group 6 = `$90`, `REGDELTA_GROUP_COUNT` 7; E5 now closed at both load time and runtime), Ch3 special/CSM, detune-unison (Ph3b residuals); Phase-4 richer content-adaptive FM6/DAC modes (basic dedicate/adaptive Echo toggle already SHIPPED); ~~game-feel moments~~ (**SHIPPED 2026-08-09, package 1** — pause/unpause scopes with freeze-in-place resume, jingle push/pop, song-finished/comm status contract, composed fade terminals + 8 spread-bit fade rates, 68k API v2; see §6.1's game-feel paragraph); section-aware banking (§6.4); continuous SFX (→ SFX Stage C, §6.7); distance attenuation DEMOTED (§6.5); procedural ambient CUT (§6.6); MegaDAW compiler/export (Ph6, blocked on content sourcing). See §6 body + the 2026-06-16 master sound spec. |
| 7 | Visual Effects | **Unified raster command table (NOVEL Aeon design — stackable per-scanline VDP register changes; the "Batman" credit was wrong, corrected 2026-08-14, see §7.2)**, Shadow/Highlight hardware lighting (novel for platformers — zero CPU cost), per-scanline palette gradients (Sonic 3 technique, **CRAM/VSRAM 2x active-display DMA speed**), computed water palette (novel), palette cross-fading, white/negative flash effects, window plane HUD + dynamic letterboxing, 16-oscillator system (S.C.E.), screen shake, 512-entry sine table, compound rotation (Batman), effect sequencer, line+column pseudo-rotation, display-disable burst DMA (advanced), mid-frame nametable register swapping (Batman — multi-layer Plane B), mid-frame VSRAM manipulation (Batman — per-scanline column deformation), **FIFO slot-precise mid-scanline writes (Titan Overdrive)**, hit-stop/freeze frames, SNES-style S/H transparency (2024), **sprite cache table-switching (Bloodlines — free water reflections)**, **vertical border opening (Kabuto — 19 extra NTSC scanlines)**, **sprite mapping format — VDP-order reorder (8 bytes/piece)**, **palette cycling animation (Jon Burton — 4x frames from CRAM cycling)**, **Project MD reflection floor**, **interlace Mode 2 (320x448, available for high-res overlays)** |
| 8 | Tooling & Build | **Authoring pipeline (tile/block/chunk editor stamps → build tool: flatten, deduplicate, spatially-order and page the global act art pool, generate block data with embedded collision + S4LZ art)**, **level editor tile budget UI (per-section shared/unique counts, per-corner budget view, warning system)**, pre-computed nametable build tool, **debug system architecture (S.C.E. two-phase gating + 10 per-subsystem toggles)**, **MD Debugger v2.6 error handler (backtrace, symbol resolution, console programs)**, **per-module debug assertions (S.C.E. + Vectorman pointer bounds/breadcrumbs/corruption detection + CHK instruction)**, **frame profiler (raster bars + VDP window lagometer + KDebug + lag detection + stack guard + watchdog)**, RAM layout documentation, build system improvements (jump sizing 10-50x speedup, dual build targets, convsym pipeline, assembly pass checking, compile-time validation), Exodus MCP integration, level editor integration |
| 9 | Cross-Cutting Systems | Level database (unified descriptors, S.C.E. levartptrs evolution), object communication (Treasure parent-child links + S.C.E. trigger array + boss event buffer), error handler with stack guard (Batman high-byte vector IDs + watchdog), 6-button controller (rapid TH cycling protocol + detection), **soft-reset detection + DMA-safe warm path (persistence RULED OUT 2026-08-05 — SRAM is the mechanism, §9.5/§9.6)**, SRAM save system (Sonic 3 dual-copy checksums), **idle-time deferred work (§9.7 — pre-chunked pages + VBlank supervisor bookmark, resumable ZX0 art-page decode; SHIPPED)**, **ROM banking awareness (SSF2 mapper, conditional on ROM >4MB)**, **128KB VRAM mode (investigated, Kabuto byte-wide DMA)**, **PC-relative addressing audit (Batman leads with 986 refs)**, **clearRAM performance variants (3 S.C.E. macros + MOVEM bulk clear)**, **game state machine (function pointer dispatch, 11 states)**, **text/font rendering (96-char ASCII, DrawString/DrawHex/DrawDecimal)**, **screen/menu system (lifecycle init/update, title cards, credits)** |

---

## Engine/game contract

Aeon draws a hard **engine/game wall**. `engine/` is the reusable, Sonic-agnostic
engine; `games/<game>/` is one game built on it. The two meet at a single typed seam
so the engine can be compiled against any game that satisfies the contract, and a new
game starts from a handful of small files (see `games/demo/`). This section is the game
author's reference: what the engine consumes from a game, and what a game must provide.

The build is `sigil build` end to end (Spec-5 Stage 2 flip). There is no separate
assembler/linker/checksum stage: every ROM byte is a natively-placed `.emp` `section`,
the ROM layout is a per-game declaration (`map.toml`), and the header checksum is folded
into sigil's `emit_rom`. Each `.emp` file is a `module`; the engine and the game modules
are resolved together at whole-ROM link.

### The typed interface (`engine/system/game_contract.emp`)

The seam is a typed interface the engine *declares* and a game *implements*:

```
pub interface Game {
    const CAMERA_JUMP_LOCK: bool     // comptime feature gate
    const ENTRY_ID: u8               // initial game-state id
    proc  entry: GameState           // first game-state routine
    hook  boot_hook () clobbers(d0-d4/a0-a1) = empty
    hook  debug_tick () clobbers(d0-d7/a0-a6) = empty
}
```

The module `engine.game_contract` emits no bytes — it is pure declaration. The engine
names members qualified (`Game.CAMERA_JUMP_LOCK`, `#Game.entry`, `#Game.ENTRY_ID`) and
calls the hooks with `invoke Game.hook`. An `invoke` lowers to an absolute `jsr` when a
game binds the hook and to **zero bytes** when the hook stays `= empty` — the
canonical-shape invariant (an unbound hook costs nothing). `GameState` (the state-dispatch
proc type `entry` is typed by) is `pub type`-declared in `engine.game_loop`; the bind pass
resolves member types across the whole reachable module set, so the interface consumes it
without a cross-module type import.

Each member drives a specific engine consumer:

- `CAMERA_JUMP_LOCK` — comptime-selected by `engine/level/camera.emp`: `true` arms the
  jump-state landing-lock block (which reads the game-defined `_pl_state` / `PSTATE_JUMP`
  / `PSTATE_ROLLJUMP`), `false` compiles to the plain deadzone follow with the lock code
  absent entirely.
- `ENTRY_ID` / `entry` — the boot handoff: `engine/system/boot.emp` ends with
  `move.l #Game.entry, (Game_State).w` / `move.b #Game.ENTRY_ID, (Game_State_ID).w`.
- `boot_hook` — `engine/system/boot.emp` invokes it after `Sound_Init`, just before the
  game-state handoff.
- `debug_tick` — `engine/system/game_loop.emp` invokes it once per frame after the
  VSync/SFX drain.

### The manifest (`implement Game`)

A game satisfies the contract with exactly one `implement Game` block in
`games/<game>/config/game.emp`. This module also emits nothing — it binds each interface
member to a symbol or value, and the bind pass resolves it against the interface before
the engine's `Game.MEMBER` / `invoke Game.hook` sites fold and lower.

Comparing the two shipped games shows the whole contract surface. Sonic 4
(`games/sonic4/config/game.emp`):

```
pub implement Game {
    const CAMERA_JUMP_LOCK = true
    const ENTRY_ID = GS_OJZ_SCROLL_TEST
    proc  entry = GameState_OJZScroll_Init
    if SOUND_DEBUG_HOTKEYS == 1 && SOUND_DRIVER_ENABLED == 1 {
        hook boot_hook  = SoundTest_BootPing
        hook debug_tick = Debug_MusicToggle
    }
}
```

The demo (`games/demo/config/game.emp`) is the minimal case — three value bindings, no
hook binds, so the `= empty` defaults carry both hooks and the demo installs nothing at
boot or per frame:

```
pub implement Game {
    const CAMERA_JUMP_LOCK = false      // no player/camera jump-lock system
    const ENTRY_ID = GS_DEMO
    proc  entry = GameState_Demo_Init
}
```

The two differences are the whole point of the wall: Sonic 4 turns the camera jump-lock
on and (in the hotkeys shape only) binds the two sound test-harness hooks; the demo turns
the jump-lock off and binds nothing. Everything the engine needs from a game to *boot* is
these three-to-five bindings.

### Beyond the interface: linked game symbols

The typed interface is the formal contract, but the engine also resolves a set of
game-supplied constants and data tables at whole-ROM link. Game-varying constants are
declared engine-side with a matching value and cross-checked against the game's define
with an `ensure(extern("NAME") == NAME, ...)` wall, so a game that supplies the wrong
value fails the build loudly on both sides; data tables are named with a typed
`extern NAME: Type`. The main ones a game provides:

| Symbol(s) | Engine consumer | Notes |
|---|---|---|
| `VRAM_RING_PLACEHOLDER` | `engine/objects/rings.emp` | Ring art VRAM slot |
| `MAX_RING_BUFFER`, `RING_BUFFER_ENTRY_SIZE`, `RING_WIDTH` | `engine/objects/rings.emp` | Ring buffer capacity/sizing (`ensure`-checked) |
| `COLLECTED_WINDOW_SLOTS`, `COLLECTED_SLOT_SIZE`, `COLLECTED_PARK_SLOTS`, `COLLECTED_PARK_ENTRY_SIZE` | `engine/objects/entity_window.emp` | Collected-entity bookkeeping capacity |
| `BgAnim_Table` | `engine/level/bg_anim.emp` | BG tile-band animation table (a `dc.w 0` band count disables the system) |
| With `SOUND_DRIVER_ENABLED`, additionally: | | |
| `SFXID_REV_LOOP`, `SFXID_RING_LEFT`, `SFXID_RING_RIGHT` | `engine/sound/sound_sfx.emp`, `sound_api.emp` | Typed `extern … : SfxId`; `SFXID_REV_LOOP = -1` disables the rev-loop special case |
| `SndDefaultPitchTable`, `SfxBlobWinTab` | `engine/sound/sound_fm.emp`, `sound_sfx.emp` | Live in the game's sound-bank head (see `soundbankhead` below) |
| `SongTable`, `SfxTable`, `SND_ENGINE_TABLE_BANK` + song/SFX data | `engine/sound/sound_api.emp`, `z80_sound_driver.emp` | Game-supplied song/SFX tables and bank placement |

### ROM layout (`map.toml`)

ROM placement is a per-game declaration in `games/<game>/map.toml`, consumed by the sigil
chainer. It owns the reviewed placement facts (the frozen provisional-base measurement
caches under `golden/` are the per-label measurement cache the order derivation sorts). It
has five kinds of entry:

- **`order`** — the byte-emitting section head-labels in canonical union order. Each build
  shape's derived byte-emitting order must be a *subsequence* of this list; a derivation
  change that reorders anything fails loud (the sonic4 map spans four shapes — s4, s4_debug,
  config_a, config_b — and each is a subsequence of the union). Zero-byte markers are
  excluded, since their tie position is byte-neutral.
- **`[[region]]`** — an address window with a base and size: `rom` (the whole 4 MB image),
  `object_bank` (the 64 KB `org $10000` object-code bank), and, sound-on, the
  `z80_moving_trucks_bank` phase bank (`vma_base = 0x8000`). Regions are the sole owner of
  the ROM geometry.
- **`[[anchor]]`** — a hard LMA for an island whose address is latched by hardware or a
  frozen boundary: `boot_head` at `0x0`, `object_bank` at `0x10000`, and (sound-on) the
  `dac_banks` DAC-sample banks at `0x48000` and the `sound_bank` engine-table head at
  `0x58000` (`vma = 0x8000`). An anchored section never repacks.
- **`[[hole]]`** — a declared gap: the sound-off Z80 idle program occupies `$3d8..$3fe`,
  so the map declares a hole `after = "Z80_IdleProgram"` at `0x3FE` filled by
  `engine.z80_init`, gated `when = "sound_off"`.
- **`[[budget]]`** — a pack-time ceiling (the old assembler `if * > $20000 / error` guard):
  the `object_bank` region has `ceiling = 0x20000` with `cursor` set to the head-label of
  the first section past the bank (the data-region head), whose resolved LMA is the used
  cursor. Overflowing the bank is a build error.

The demo's `map.toml` is the minimal template — two anchors (boot head + object bank), the
sound-off Z80-idle hole, the object-bank budget, and the order list — and declares no Z80
sound bank because it is sound-off.

### The ROM header (`header.emp`)

The $100-$1FF Mega Drive header is a game-side module, `games/sonic4/config/header.emp`
(`module games.sonic4.header in header`) — placed by the map's `header` section directly
after the vector table, not emitted by the engine and not a macro. It is a plain
`data GameHeader: HeaderTop` struct of literal string fields whose **`[u8; N]` field types
are the width guards**: a wrong-length string fails to lower at comptime, so the type *is*
the assertion (this replaced the old per-field `strlen … fatal` walls). The struct splits
at the checksum so `Checksum` ($18E) stays a real boundary label: `HeaderTop` ($100-$18D),
the checksum word, then `HeaderTail` ($190-$1FF). `Checksum` and `rom_end` ($1A4, declared
`extern("EndOfRom") - 1`) are patched post-pipeline by sigil from the final image size;
`ram_start`/`ram_end` are literal.

### The build entry (`build.sh`)

`build.sh [game]` takes the game as a positional argument (`GAME="${1:-sonic4}"`, default
`sonic4` → `s4.bin`; `demo` → `demo.bin`). It is a thin wrapper around the sigil binaries,
selected by environment variable:

- `SIGIL_BUILD` — the `sigil build` binary, the whole assembler/linker/checksum pipeline.
  It is a **hard requirement**: a missing or non-executable `SIGIL_BUILD` aborts the build
  (there is no asl fallback).
- `SIGIL_EMIT` — the seam-1 `emit_sound_blob` binary, run as a preflight for sound-on games
  to regenerate `engine/sound/generated/` (the `.bin` blobs the sound-bank `.emp` files
  embed).

The core invocation is `"${SIGIL_BUILD}" build --aeon . --native --game ${GAME} [--debug]
-o "${ROM_NAME}.bin" --emit-lst "${ROM_NAME}.lst"`. `DEBUG=1` adds `--debug`. The
off-canonical sonic4 sound shapes map to sigil's `--config-a` (sound + debug hotkeys/mirror)
and `--config-b` (sound off) profiles.

### Engine_RAM_End — the RAM seam

Engine RAM and game RAM are declared as chained `region`s. `engine/ram.emp`
(`module engine.ram`) owns the engine layout: `upper_ram @ $FFFF8000 .. SYSTEM_STACK`
(`.w`-addressed hot data) ends with a `mark Engine_RAM_End,`. A game continues from there:
`games/<game>/config/ram.emp` declares `pub region game_ram @ after(upper_ram) .. SYSTEM_STACK`
and phases its own variables in — exactly where the AS-era `phase Engine_RAM_End` did.
Player state, debug harness variables, and all other game-owned RAM live game-side, after
this seam; the `game_ram` region's `limit` (`SYSTEM_STACK`) is the overflow guard. The demo's
`game_ram` is empty (just `mark Game_RAM_End,`) — the template a new game grows from.

### soundBankHead — engine tables at the bank head

The engine's per-frame sequencer reads its lookup tables (pitch, SFX window, opcode dispatch,
DAC sample descriptors) from fixed $8000-window VMAs. A sound-on game places them with a
`section soundbankhead (cpu: m68000, vma: $8000)` in `games/sonic4/data/sound/soundbankhead.emp`
(`module games.sonic4.soundbankhead`), which the map anchors at LMA `0x58000`. The section
`embed`s the seam-1-generated `.bin` artifacts (`SoundTablesZ80_Head` @ $8000,
`SndDefaultPitchTable` @ $8357, `SfxBlobWinTab` @ $845F, `SeqOpcodeTable` @ $856D,
`DacSampleTable` @ $85AD) at the exact VMAs the resident Z80 driver's banked carriers expect,
and guards each span's size with a comptime `ensure` — a size drift would slide a downstream
head off its fixed carrier VMA and desync the Z80 blob, so it fails the build loudly. **Hard
rule: no code is authored in a banked $8000-window section — data tables only.** Z80 opcode
fetches from a banked window traverse the 68k bus, and 68k bus contention (VRAM DMA-from-ROM /
BUSREQ) corrupts fetched opcodes, not just data.

### build.conf + prebuild.sh

Per-game build hooks, both optional and sourced/invoked by `build.sh` before assembly:

- `games/<game>/build.conf` — sourced early; sets build-flag defaults (e.g.
  `games/demo/build.conf` defaults `SOUND_DRIVER_ENABLED=0` since the demo ships no sound
  bank yet).
- `games/<game>/prebuild.sh` — invoked if executable; runs the game's content generators
  (art-pool compression, collision baking, SFX transcoding, etc.) before the assembler runs.
  `games/sonic4/prebuild.sh` holds everything sonic4-specific; the engine core (salvador
  bootstrap, compression self-test vector generation, lint) stays in `build.sh` itself.

### games/demo — the permanent agnosticism regression

`games/demo/` is a minimal game: the `implement Game` manifest above, its `map.toml` and
`header.emp`, a 16×16 white box object, and a one-shot init state. `DEBUG=1 ./build.sh demo`
produces `demo.bin` and boots to a dark-blue backdrop with the white box centered on screen —
zero Sonic code anywhere in the ROM. It exists both as the "start here" template for a new
game and as a standing proof that the engine really is game-agnostic; keep it building green
as a regression check whenever `engine/` changes. (v1 limitation: builds with sound off — see
`docs/DEFERRED_WORK.md`, "Engine substrate gaps".)

### The residual AS root

One `.asm` file survives per game: `games/<game>/game_root.asm`. It emits **no bytes** and
declares no orgs — it exists only to pull in the one named survivor, the vendored MD Debugger
blob (`engine/debug/debugger.asm`), so its defines/macros/link-externs enter the residual
symbol environment the sigil frontend harvests. The game contract itself is fully `.emp`-native;
no game-authored `.asm` carries semantics.

---

## 0. Hardware Initialization & Boot Sequence

The foundation everything else sits on. This section covers the first moments of execution (the 64KB RAM clear alone is ~180,000 cycles): ROM header, exception vectors, TMSS handshake, VDP/Z80/PSG init, RAM clearing, region detection, and the transition into the game state machine. Every design here is informed by what Vectorman, Batman & Robin, Treasure (Gunstar/Alien Soldier), Thunder Force IV, and S.C.E. actually do on real hardware, cross-referenced with plutiedev, Kabuto, md.railgun.works, and modern engine initialization patterns.

### 0.1 ROM Header & Vector Table

**Vector Table** ($000000-$0000FF, 64 longwords):

The first 256 bytes of ROM are the 68000 exception vector table. Two entries matter most:

| Vector | Offset | Our Value | Purpose |
|--------|--------|-----------|---------|
| Initial SSP | $000000 | `$FFFFFF00` | Stack pointer — high RAM, away from game data |
| Reset PC | $000004 | `EntryPoint` | First instruction after power-on or reset |
| Bus Error | $000008 | `BusError` | Invalid bus cycle |
| Address Error | $00000C | `AddressError` | Odd-address word/long access |
| Illegal Instruction | $000010 | `IllegalInstr` | Invalid opcode |
| Division by Zero | $000014 | `ZeroDivide` | `divu`/`divs` with divisor 0 |
| CHK Exception | $000018 | `ChkInstr` | CHK instruction out of bounds |
| TRAPV | $00001C | `TrapvInstr` | Overflow trap |
| Privilege Violation | $000020 | `PrivilegeViol` | User-mode restricted instruction |
| Trace | $000024 | `Trace` | Single-step debugging |
| Line 1010 | $000028 | `Line1010Emu` | Unimplemented A-line trap |
| Line 1111 | $00002C | `Line1111Emu` | Unimplemented F-line trap |
| Reserved | $000030-$00005C | `ErrorExcept` | 12 reserved vectors |
| Spurious Interrupt | $000060 | `ErrorExcept` | Uninitialized interrupt |
| IRQ1 (External) | $000064 | `ErrorExcept` | Unmodelled level — halts loudly |
| IRQ2 (External) | $000068 | `ErrorExcept` | External (controller TH) — unmodelled, halts loudly |
| IRQ3 | $00006C | `ErrorExcept` | Unmodelled level — halts loudly |
| IRQ4 (HBlank) | $000070 | `HBlank_Vector_Slot` | **RAM trampoline** — vector points into a 6-byte executable RAM slot (idle `rte`, or armed `jmp handler.l`) |
| IRQ5 | $000074 | `ErrorExcept` | Unmodelled level — halts loudly |
| IRQ6 (VBlank) | $000078 | `VBlank_Handler` | Vertical blanking interrupt |
| IRQ7 (NMI) | $00007C | `ErrorExcept` | Non-maskable — unmodelled, halts loudly |
| TRAP #0-15 | $000080-$0000BC | `ErrorTrap` | 16 TRAP vectors — reserved for the debug system |
| Reserved | $0000C0-$0000FC | `ErrorTrap` | Remaining reserved vectors |

The "Our Value" column above is the **DEBUG and RELEASE** shape (`DEBUG == 1 || CRASH_REPORT == 1`). In the opt-in **lean** shape (`DEBUG=0, CRASH_REPORT=0`) the error-handler island is absent and every fault, reserved, TRAP and unmodelled-interrupt cell instead holds `ReleaseFault` (`engine/system/release_fault.emp` — mask IRQs, red backdrop, freeze). Four cells are shape-invariant: $00 `SYSTEM_STACK`, $04 `EntryPoint`, $70 `HBlank_Vector_Slot`, $78 `VBlank_Handler`. The region's 256-byte size is shape-invariant either way, so the header boundary at $100 stays byte-neutral. See §8.4 for the three-shape table.

**Design decisions:**

- **SSP = $FFFFFF00** (not $00000000): Vectorman, Gunstar Heroes, and Alien Soldier all use high RAM. Stack grows downward from near-top of 64KB RAM, staying far from game data at low RAM addresses. $00000000 (used by S.C.E., Batman, Thunder Force IV) makes the stack grow down from the very bottom of the address space — wrapping bugs are silent and catastrophic. $FFFFFF00 gives 256 bytes of headroom below the RAM ceiling ($FFFFFFFF), which is sufficient since our deepest call chain is audited.
- **RAM-slot HBlank trampoline**: The vector table entry at $70 points *directly into RAM* — at `HBlank_Vector_Slot`, a 6-byte executable slot that holds an idle `rte` ($4E73) when no raster effect is active, or `jmp handler.l` ($4EF9 + 4-byte target) when a handler is armed (`HBlank_Install`, §0.10). There is no ROM dispatch stub and no pointer indirection: IRQ4 reaches the handler through a single `jmp`, and the handler owns its own register save/restore and terminates with `rte`. This allows swapping raster effect handlers per-section without modifying ROM. Vectorman ($FFFF9D2E), Batman ($FFFFE560), Gunstar/Alien Soldier ($FFFFEE00) all do a variant of this (theirs read a pointer from RAM; ours executes an instruction from RAM, saving the pointer-load and indirect-jsr). Thunder Force IV is the only holdout (ROM-based), and it can't change HBlank behavior between levels.
- **VBlank in ROM**: Unlike HBlank (which changes per-section), VBlank always does the same core work: drain DMA queue, update sprites, read controllers, process sound, set VBlank flag. A single ROM handler with conditional dispatch is sufficient.
- **Exception routing**: Each exception has its own labeled entry point (`BusError`, `AddressError`, `IllegalInstr`, `ZeroDivide`, `ChkInstr`, `TrapvInstr`, `PrivilegeViol`, `Trace`, `Line1010Emu`, `Line1111Emu`), with `ErrorExcept` covering the reserved $30-$60 vectors — all integrating with the MD Debugger v2.6 error handler (§8.3). Per-exception labels let the error screen name the exact fault, out of the deb2 symbol appendix that both canonical shapes ship. In the lean shape the island is absent and every one of these cells holds `ReleaseFault` instead; repointing lean at a tolerant `rte` would be actively wrong for the fault classes, since an `rte` from a bus or address error re-executes the faulting instruction and hard-loops.
- **Unmodelled interrupts halt loudly** (owner ruling, 2026-08-04): the spurious vector ($60) and IRQ1/2/3/5/7 route to `ErrorExcept` (`ReleaseFault` in lean), never to a tolerant `rte`. A spurious IRQ means a state the engine does not model, so it is surfaced during development rather than allowed to corrupt silently. The earlier `NullInterrupt` primitive that gave these five levels a bare `rte` is **deleted** — the table used to be internally inconsistent, crashing or vanishing depending on which line the glitch landed on. Do not reintroduce a tolerant vector without an owner ruling.
- **TRAP vectors**: All 16 TRAP vectors (and the reserved $C0-$FC block) currently route to `ErrorTrap` (`ReleaseFault` in lean). Reserved for the debug system — TRAP #0 can later be wired to `RaiseError` for debug assertions; other TRAPs available for future use.

**ROM Header** ($000100-$0001FF):

Standard Sega header format — emitted by the **game-side** module `games/sonic4/config/header.emp` (`module games.sonic4.header`), not the engine and not a macro. It is a plain `data GameHeader: HeaderTop` / `HeaderTail` struct with literal string values, placed by the game's `map.toml` at the `header` section directly after the vector table:

| Offset | `header.emp` field | Width | Sonic 4 value |
|--------|--------------------|-------|---------------|
| $100 | `console` | 16 | `"SEGA GENESIS    "` (TMSS requires "SEGA" at $100) |
| $110 | `copyright` | 16 | `"(C)     2026.APR"` |
| $120 | `title_dom` | 48 | Domestic name |
| $150 | `title_ovs` | 48 | Overseas name |
| $180 | `serial` | 14 | `"GM S4-0001-00 "` |
| $18E | `Checksum` | word | Emitted 0, folded by `sigil build`'s `emit_rom` (from the final image) |
| $190 | `io` | 16 | I/O support (`"J"` = 3/6-button joypad) |
| $1A0 | `rom_start` | long | ROM start = $00000000 |
| $1A4 | `rom_end` | long | `extern("EndOfRom") - 1` — patched by `emit_rom` to the final image size |
| $1A8/$1AC | `ram_start`/`ram_end` | 2 longs | RAM range $00FF0000-$00FFFFFF |
| $1B0 | `sram` | 12 | No SRAM/modem (SRAM handled in software §9.6) |
| $1BC | `memo` | 52 | Memo field |
| $1F0 | `region` | 16 | `"JUE"` — Japan + US + Europe |

**Build-time validation** (sigil catches errors before we ever run):

The `[u8; N]` field *types* ARE the exact-width guards — a wrong-length string fails to lower at comptime (this replaces the old per-field `strlen … fatal` walls; the type is the assertion). The ROM-size checks live at the engine epilogue (`engine/system/epilogue.emp`):

```
    ensure((EndOfRom & 1) == 0, "ROM size is odd")
    ensure(EndOfRom <= $3FFFFF, "ROM exceeds 4MB without banking")
```

### 0.2 TMSS Handshake

The Trademark Security System exists on Model 1 VA7+ and all Model 2/3 units. If TMSS is present but not satisfied, the next VDP data port access hangs the CPU permanently.

```asm
EntryPoint:
        lea.l   (SYSTEM_STACK).w, sp        ; reload sp — see below
        tst.l   (HW_PORT_A_CTRL_FULL).l     ; Port A control — non-zero on soft reset
        bne.s   Warm_Boot
        tst.w   (HW_EXPANSION_CTRL_FULL).l  ; Expansion control — second soft-reset check
        beq.s   Cold_Boot

Warm_Boot:
.wait_dma:                          ; Soft reset: wait for any in-progress DMA...
        move.w  (VDP_CTRL).l, d0
        btst    #1, d0
        bne.s   .wait_dma
        ; ...then fall through to Cold_Boot — full hardware init runs on soft reset too.

Cold_Boot:
        move.b  (HW_VERSION).l, d0  ; Read version register
        andi.b  #$F, d0             ; Isolate hardware revision nibble
        beq.s   .no_tmss            ; Revision 0 = original Model 1 (no TMSS)
        move.l  #$53454741, (TMSS_REGISTER).l  ; Write "SEGA" to TMSS register
.no_tmss:
```

**Why this order:** The soft-reset detection (port A control + expansion control) must come before TMSS because on soft reset, VDP state is already initialized — a DMA may still be in progress. The warm path exists solely to wait out that in-flight DMA safely; it then performs the same full cold-boot initialization (there is no separate warm-reset path — see §0.11). S.C.E. does exactly this check. On cold boot (power-on), both port registers read zero.

**Why the stack reload first:** on a hardware reset the 68000 has already loaded sp from vector $000, so `lea (SYSTEM_STACK).w, sp` is redundant — but a software `jmp EntryPoint` soft-reset does not, and without it the 64KB RAM clear runs on whatever sp the game was using, after which `jbsr VDP_Shadow_Init` pushes a return address into just-cleared (or live) RAM and returns through garbage. One instruction closes that. It does *not* make software re-entry safe on its own: everything up to the interrupt unmask relies on the 68000 reset forcing SR=$2700, so a `jmp EntryPoint` with interrupts live still races the RAM clear (which zeroes `VInt_Ptr`) against a pending VInt. The reset vector is the sole referencer in practice.

### 0.3 VDP Register Initialization

24 VDP registers ($00-$17) configured from a compile-time validated table. During init, display is OFF and DMA is enabled — this allows DMA fill of VRAM while the CPU continues working.

**Register table** (values chosen for our 64×64 plane, unified-pool VRAM layout from §2.3):

| Reg | Value | Setting | Why |
|-----|-------|---------|-----|
| $00 | `$04` | Mode 5 enabled, HInt OFF, HV counter readable | HInt enabled later per-section |
| $01 | `$14` | Display OFF, VInt OFF, DMA ON, V28 (224px), M5 | Display enabled after init completes |
| $02 | `$30` | Plane A nametable at $C000 | §2.3 — tile $600 × 32 = byte $C000, reg bits 5-3 = 6 → $30 |
| $03 | `$3C` | Window nametable at $F000 | Inert placeholder — $F000 lies INSIDE Plane B (see below) |
| $04 | `$07` | Plane B nametable at $E000 | §2.3 — tile $700 × 32 = byte $E000, reg bits 2-0 = 7 → $07 |
| $05 | `$5C` | Sprite attribute table at $B800 | 80 sprites × 8 bytes = 640 bytes |
| $06 | `$00` | Sprite generator base (normal mode) | Not used in standard 64KB VRAM |
| $07 | `$00` | Background color = palette 0, entry 0 | Black background default |
| $08 | `$00` | Unused (Master System compat) | Must be zero |
| $09 | `$00` | Unused (Master System compat) | Must be zero |
| $0A | `$FF` | HInt counter = every 256 lines | Effectively disabled until gameplay |
| $0B | `$00` | Full-screen VScroll, full-screen HScroll | Changed per-section for effects (§7.2) |
| $0C | `$81` | H40 (320px), no interlace, no S/H | S/H enabled per-section (§7.3) |
| $0D | `$2F` | HScroll table at $BC00 | 224 entries × 4 bytes for per-line scroll — below Plane A, outside both nametables (§2.3) |
| $0E | `$00` | Nametable generator base (normal mode) | Not used in standard 64KB VRAM |
| $0F | `$02` | Auto-increment = 2 bytes | Normal word access. Boot temporarily writes `$8F01` just before the VRAM DMA fill (byte-by-byte), then restores `$8F02` after the fill completes |
| $10 | `$11` | **64×64 cell scroll planes** | §2.3 — validated by Vectorman, enables vertical streaming |
| $11 | `$00` | Window H pos = disabled | Enabled dynamically for HUD (§7) |
| $12 | `$00` | Window V pos = disabled | Enabled dynamically for letterbox (§7) |
| $13 | `$FF` | DMA length low = $FF | Set per-transfer, init value doesn't matter |
| $14 | `$FF` | DMA length high = $FF | Set per-transfer |
| $15 | `$00` | DMA source low | Set per-transfer |
| $16 | `$00` | DMA source mid | Set per-transfer |
| $17 | `$80` | DMA source high = fill mode | Primes VRAM fill for clearing |

**Reg $03 is a constraint, not a free choice.** With 64×64 planes (reg $10 = $11), Plane B at $E000 spans $E000-$FFFF, so the window nametable at $F000 sits *inside* Plane B's map. This is harmless today only because the window is disabled — regs $11/$12 are both `$00`, so the VDP never fetches from it — but there is **no free window space anywhere in this VRAM map** (§2.3 fills VRAM exactly). Enabling the window for a HUD overlay or letterbox (§7) means re-planning the VRAM layout first, not just writing regs $11/$12.

**Reg $02/$04 calculation for our VRAM layout:**

```asm
; §2.3 VRAM map:
;   $000-$5BF  = art pool (1,472 tiles)
;   $600-$6FF  = Plane A nametable (64×64 = 8KB)
;   $700-$7FF  = Plane B nametable (64×64 = 8KB)
;
; Tile-to-byte conversion: tile_index × 32 bytes/tile
;   Tile $600 × 32 = byte $C000 (Plane A)
;   Tile $700 × 32 = byte $E000 (Plane B)
;
; VDP nametable register encoding:
;   Reg $02 bits 5-3 = address / $2000.  $C000/$2000 = 6 → bits %110 → reg = $30
;   Reg $04 bits 2-0 = address / $2000.  $E000/$2000 = 7 → bits %111 → reg = $07
;
; With 64×64 planes, each nametable is 64×64×2 = 8,192 bytes = $2000.
; Plane A: $C000-$DFFF. Plane B: $E000-$FFFF. They fill VRAM exactly.
; Sprite attr table ($B800) + HScroll table ($BC00) sit in tiles $5C0-$5FF,
; BELOW Plane A — relocated from the old $D800/$DC00 (which were INSIDE Plane A's
; $C000-$DFFF nametable). With them moved out, all 64 Plane A rows (incl. rows
; 48-63) are normal nametable rows the vertical streaming uses — no SAT overlap.
```

**Compile-time validation of register table:**

The register command word is built by a comptime function whose parameter ranges are
themselves the guard (`engine/vdp.emp`):

```emp
pub comptime fn vdp_reg(reg: int where 0..$17, val: int where 0..$FF) -> int {
    return $8000 | (reg << 8) | val
}
```

An out-of-range register number or value fails to lower — there is no runtime check and
no separate assertion to keep in sync. The plane-geometry wall lives at the engine
epilogue (`engine/system/epilogue.emp`), where it folds against pure constants:

```emp
ensure(PLANE_H_CELLS * PLANE_V_CELLS <= 4096, "Plane exceeds 8KB")
```

**Init method — preloaded register approach** (from S.C.E., used by every commercial game):

```asm
; Pack hardware addresses into registers with movem (S.C.E. pattern)
        lea.l   BootData(pc), a5
        movem.w (a5)+, d5-d7        ; d5=$8000 (VDP reg base), d6=$3FFF (RAM loop), d7=$0100 (Z80 bus)
        movem.l (a5)+, a0-a4        ; a0=Z80_RAM, a1=Z80_Bus, a2=Z80_Reset, a3=VDP_Data, a4=VDP_Ctrl

; Write 24 VDP registers from table
        moveq   #23, d1
.vdp_loop:
        move.b  (a5)+, d5           ; Load register value into low byte of d5
        move.w  d5, (a4)            ; Write $80xx to VDP control port
        add.w   d7, d5              ; d7 = $0100 → advance to next register number
        dbf     d1, .vdp_loop

; Byte-wise VRAM DMA fill needs increment=1 — written separately, NOT the table value
        move.w  #vdpReg($0F, $01), (a4)
        move.l  (a5)+, (a4)         ; vdpComm(0, VRAM, DMA)
        moveq   #0, d0
        move.w  d0, (a3)            ; trigger fill (fill byte = 0)
```

### 0.4 VDP Shadow Table — RAM-Resident Register Mirror (NOVEL Aeon design)

> **PROVENANCE CORRECTED 2026-08-14.** This section previously read "(from Batman & Robin)" and
> sourced the design to `main_loop.asm:4579-4584`. **Both were wrong, and the error was already
> visible inside this document** — §1.7 below has always said "vs Batman's bulk-write-all
> approach", and the dirty-tracking paragraph further down has always been marked
> "(NOVEL — no reference game does this)". Re-verified against the disassembly at
> `/home/volence/sonic_hacks/The Adventures of Batman and Robin/disasm/`:
>
> - **The cited lines are not a VDP routine at all.** `code/engine/main_loop.asm:4570-4595` is a
>   nibble-expansion / bitplane loop (`lsr.l #$4` + table lookups), no VDP access anywhere in it.
> - **What Batman actually does** is `sub_00AE2C` (`code/engine/main_loop.asm:5400-5409`):
>   `moveq #$12, d7` (19 iterations), `move.w #$8000, d0`, then per iteration
>   `move.b (a0)+, d0` / `move.w d0, $c00004.l` / `addi.w #$100, d0` / `dbra`. That is an
>   **unconditional bulk write of 19 registers from a byte table** — no readback, no compare,
>   no dirty bit, and no per-register skip. Its two callers
>   (`code/engine/main_loop.asm:3601`, `:3864`) are scene/level setup, not the VBlank handler;
>   the second passes `lea $155bc.l, a0`, a **ROM** table, not a RAM one.
> - **There is no register shadow in Batman.** `grep -rin f81e` over every Batman `.asm` source
>   and companion doc returns **zero** hits (the only hits anywhere are four incidental ones in
>   the generated listing `disasm/batman.lst` — a branch displacement and three address-column
>   values, none of them a RAM reference). `shadow` / `dirty` / `mirror` likewise return zero
>   hits across its companion documents. The VDP register mirror at `$FFFFF81E` that this credit
>   describes belongs to a **different ROM** that happens to live in a sibling directory:
>   *The Chaos Layer*, which reads it (`the_chaos_layer/code/disasm.asm:490-515`:
>   `move.w ($fffff81e).w,d0` / `ori.b #$10,d0` / write back) and bulk re-pushes it
>   (`the_chaos_layer/code/disasm.asm:327-334`); see also
>   `the_chaos_layer/notes/BOOT_AND_FRAME.md:468-492` and `notes/GRAPHICS.md:765`.
>   Note TCL's mirror is **19 words** — the same $00-$12 span Aeon shadows, a coincidence of
>   scope, not a shared design — and TCL has **no dirty tracking either**: its `$000534` loop
>   unconditionally re-pushes all 19.
>
> **The shadow itself is therefore ours**, in the sense above: the RAM mirror is a convergent,
> common technique (the VDP control port is write-only, so anything that needs to read a register
> back must keep a copy). The *dirty-tracked flush* this note originally went on to defend —
> `SetVDPReg` sets a bit, `Flush_VDP_Shadow` writes only the changed registers — was itself retired
> later the same day: see
> `docs/superpowers/plans/2026-08-14-blanket-register-restore.md`. `Flush_VDP_Shadow` now re-blits
> all 19 shadowed registers unconditionally, every VBlank — the Batman/TCL bulk-write shape this
> note is busy explaining Aeon did NOT copy from them. The convergence is real now, but it was
> chosen for composability, not sourced from either reference — see the blanket-restore
> description below and `engine/system/vdp_init.emp` for the current code.

**What the pattern is:** a GPU state object, from modern 3D engines, adapted for the VDP.

**Design:**

```asm
    struct VDP_Shadow
vdp_mode1           ds.b 1      ; reg $00
vdp_mode2           ds.b 1      ; reg $01
vdp_plane_a         ds.b 1      ; reg $02
vdp_window          ds.b 1      ; reg $03
vdp_plane_b         ds.b 1      ; reg $04
vdp_sprite          ds.b 1      ; reg $05
vdp_sprite_gen      ds.b 1      ; reg $06
vdp_bgcolor         ds.b 1      ; reg $07
vdp_unused08        ds.b 1      ; reg $08
vdp_unused09        ds.b 1      ; reg $09
vdp_hint_rate       ds.b 1      ; reg $0A
vdp_mode3           ds.b 1      ; reg $0B
vdp_mode4           ds.b 1      ; reg $0C
vdp_hscroll         ds.b 1      ; reg $0D
vdp_nametable_gen   ds.b 1      ; reg $0E
vdp_increment       ds.b 1      ; reg $0F
vdp_plane_size      ds.b 1      ; reg $10
vdp_window_h        ds.b 1      ; reg $11
vdp_window_v        ds.b 1      ; reg $12
    endstruct VDP_Shadow
; Registers $13-$17 (DMA) are NOT shadowed — they are set per-transfer by the DMA queue.
```

**Why shadow only $00-$12** (19 registers, not 24): Registers $13-$17 control DMA source/length/mode and are set immediately before each DMA transfer by the queue system (§1.1). Shadowing them would be wrong — they change per-transfer, not per-frame.

**Frame-top blanket restore** (as of 2026-08-14 — supersedes the dirty-tracked design this section
described until then):

Every VBlank, `Flush_VDP_Shadow` re-blits all 19 shadowed registers from `VDP_Shadow_Table` to the
VDP control port, unconditionally — no dirty bitmask, no per-register skip. This is the same shape
Batman & Robin and The Chaos Layer use (see the provenance note above), and it is how Gunstar
Heroes and Alien Soldier restore VDP state after raster effects: the flush is what makes a
mid-frame register write self-undoing. An effect that pokes reg `$0B` or `$0A` during active scan
needs no paired "frame-top reset" word of its own — the next flush restores the settled shadow
value for free, so two independently-authored effects can touch the same register without
agreeing on anything. That reset-word coupling was exactly the ceiling the old dirty-tracked
design imposed (the raster DSL's `prog_init` had to `ensure` disagreeing resets were a build
error, the water template depended on `init_count == 1`, `region_boundary`'s `sh: 1` existed only
to manufacture an init word) — removing it was the entire point of the change. See
`docs/superpowers/plans/2026-08-14-blanket-register-restore.md` for the full rationale.

There is no `VDP_Dirty_Mask` field anymore. It had zero readers once the flush stopped checking
it and was deleted along with all 11 `ori.l #(1 << …), VDP_Dirty_Mask` writer sites, across
`parallax.emp`, `hblank.emp`, `boot.emp`, `demo_state.emp`, `object_test_state.emp` and
`ojz_scroll_test.emp`.

**Write-through idiom** (game code uses this, never writes VDP directly). `Set_VDP_Reg`
(`engine/system/vdp_init.emp`) is the one sanctioned way to change a register outside VBlank and
have the change survive to the next frame — `d0.w` = register-slot offset, `d1.b` = value; it
writes only the shadow byte:

```asm
        move.w  #VDP_MODE2_OFF, d0
        move.b  #$34, d1
        jbsr    Set_VDP_Reg                 ; VDP_Shadow_Table + VDP_MODE2_OFF <- $34
```

There is no dirty bit to set — the unconditional flush at the next VBlank is what reaches
hardware, for every shadowed register, every frame. The register-slot offsets
(`VDP_MODE1_OFF`, `VDP_MODE2_OFF`, `VDP_HINT_OFF`, …) come from `engine/vdp.emp`, drift-locked
against the `VdpShadow` struct in `engine/structs.emp`. Read-modify-write sites (setting a single
bit such as IE1 without disturbing the rest of reg $00) load the shadow byte directly, mask it,
and store it straight back — `Set_VDP_Reg` only writes, it does not read, so a masked bit-set
reads/writes `VDP_Shadow_Table` inline rather than round-tripping through it. See
`HBlank_Install` / `HBlank_Uninstall` (`engine/system/hblank.emp`).

**`Set_VDP_Reg` currently has zero callers.** It is the mandated idiom and it ships unadopted: every
whole-register settled-state write in the tree still stores to `VDP_Shadow_Table + VDP_*_OFF` inline
— `engine/level/parallax.emp` (2), `engine/system/boot.emp`, `games/demo/demo_state.emp`,
`games/sonic4/test/object_test_state.emp` (2), `games/sonic4/test/ojz_scroll_test.emp` (2). Those
sites predate the helper and converting them moves bytes, so it is booked as its own parcel rather
than smuggled into the one that introduced it. The two `hblank.emp` sites are read-modify-write and
are *not* adoption debt — see the paragraph above. New code should call `Set_VDP_Reg`; the inline
sites are the backlog, not the pattern. In the DEBUG shape it asserts `d0 <= $12` (unsigned, so
negatives are caught too) — the shadow table sits immediately before the interrupt-dispatch block in
`engine/ram.emp`, so an out-of-range index would otherwise corrupt RAM silently.

```asm
; VBlank flush — re-blits every shadowed register, unconditionally, ascending
; from reg 0. No dirty check: the whole point is that a mid-frame register
; write needs no matching reset word — this restores each register's settled
; value every frame, whether or not anything touched it since the last flush.
Flush_VDP_Shadow:
        lea.l   (VDP_Shadow_Table).w, a0
        lea.l   (VDP_CTRL).l, a1
        move.w  #$8000, d0                  ; VDP command base (reg 0)
        moveq   #VDP_Shadow_len-1, d1       ; 19 registers
.loop:
        move.b  (a0)+, d0                   ; shadow value into the command's low byte
        move.w  d0, (a1)                    ; write $8X00+val to VDP
        addi.w  #$0100, d0                  ; next register command
        dbf     d1, .loop
        rts
```

**Why blanket, not dirty-tracked:** The retired design was a deliberate cycles-vs-composability
tradeoff — skip unchanged registers, at the cost of every raster effect owning a matching
frame-top reset word so two effects touching the same register would not fight. In practice that
coupling was the ceiling on composability (the cases above). The blanket restore costs a fixed,
small, predictable 19-register write every frame — the same shape Batman & Robin, The Chaos
Layer, Gunstar Heroes and Alien Soldier all already ship — in exchange for effects never needing
to agree on anything. **Do not state a specific cycle delta between the two designs as fact**:
the implementing plan record explicitly flags its "~200 cycles cheaper" estimate as unmeasured.

**Direct VDP register-write conventions** (audited 2026-04-27, see `docs/superpowers/specs/2026-04-27-vdp-shadow-dma-audit-design.md`):

The shadow idiom is the only sanctioned write path for **persistent** frame state on registers `$00-$12`. Direct writes to those registers (e.g., `move.w #$8Fxx, (VDP_CTRL).l`) are permitted **only** for transient setup that the caller fully controls and that does not represent shared frame state:

1. **Pre-DMA autoincrement (`$0F`) configuration.** Caller sets `$8Fxx` immediately before a VRAM/CRAM/VSRAM transfer; subsequent transfers either tolerate the value or restore it. Examples: `engine/level/bg.emp`, `engine/level/section.emp`, `engine/level/plane_buffer.emp`. **This is no longer harmless by default.** `Flush_VDP_Shadow` re-blits reg `$0F` from the shadow (settled value `$02`) unconditionally, every VBlank — so a VBlank landing mid-excursion flushes `$02` back over the caller's `$80` out from under it, and the rest of the excursion's column-mode writes silently stride by 2 instead of `$80`. All three sites MUST keep interrupts masked (`IPL >= 6`) across the whole excursion for exactly this reason; each carries a DEBUG-shape assert checking it. An unmasked `$8F80` excursion is a silent VRAM-stride bug the flush no longer has any dirty gate to prevent.

   **The census is four sites, not three.** `engine/system/boot.emp:109` makes the same excursion — `move.w #vdp_reg($0F, $01), (a4)`, autoincrement 1 for the byte-by-byte VRAM DMA fill, restored via `AUTO_INC_2_CMD` (`engine/system/boot_data.emp:184`). It carries **no assert, deliberately**: it is safe by *context* rather than by masking discipline. Boot runs masked at `$2700` from the first instruction, VInt is not enabled in the VDP until `boot.emp:300` (`move.b #$34, VDP_Shadow_Table + VDP_MODE2_OFF` followed by the flush at `:303`) and the SR is not lowered to `$2300` until `:307` — so there is no VBlank handler in existence, and therefore no flush, while the excursion is open. An IPL assert there would measure the boot mask a few lines above it and be vacuous. It is listed here because a census that omits it invites the next reader to "discover" an unguarded site and add a vacuous assert, or worse, to conclude the invariant is unenforced.
2. **HInt-handler-internal raster effects (future §7.2).** HInt handlers may freely write VDP registers during the active line — that's the entire point of raster effects. They MUST NOT update the shadow. The shadow represents settled frame state, not transient mid-frame VDP changes. When the section's HInt program exits, hardware register state is whatever the last write left; the next VBlank's `Flush_VDP_Shadow` re-asserts the settled value for every shadowed register unconditionally, and HInt handlers re-establish their own per-line program from scratch.
3. **DMA register writes (`$13-$17`)** are not shadowed and are set per-transfer by the DMA queue. This is by design — the shadow only covers `$00-$12`.

**Hard rule:** any direct VDP write to `$00-$12` that represents settled state (display enable, scroll mode, plane base, etc.) MUST use the shadow idiom above. Bypassing the shadow for settled state risks the next flush overwriting a hardware-only change with a stale shadow value — more certain now than under the old design, since the flush no longer needs a dirty bit to trigger the overwrite; it happens every frame regardless. Audit grep, run periodically; classify each new hit as transient (OK) or settled (use the shadow):

```
grep -rEn 'move\.w\s+#\$8[0-9A-Fa-f]|#\$9[0-2][0-9A-Fa-f]|vdp_reg\(|Set_VDP_Reg' engine/
```

The `vdp_reg\(` and `Set_VDP_Reg` alternatives are not decoration — **the literal-word pattern alone has a structural blind spot.** A register write spelled through the comptime constructor (`move.w #vdp_reg($0F, $01), (a4)` — `engine/system/boot.emp:109`, and `AUTO_INC_2_CMD` at `engine/system/boot_data.emp:94`) folds to `$8F01` only at assembly time; no source line ever contains `#$8F`, so the old grep could never find it and the census above was silently short by one site. `Set_VDP_Reg` is matched so the audit also enumerates the sanctioned *shadow* path in the same pass.

The sanctioned transient hits today are the `$8F02`/`$8F80` autoincrement excursions in `engine/level/bg.emp`, `engine/level/plane_buffer.emp` and `engine/level/section.emp` (masked, asserted), plus boot's `vdp_reg($0F, $01)` fill excursion (safe by context, no assert — see above). `engine/system/release_fault.emp`'s two direct writes are the lean-shape fault path, which by design runs after the engine has stopped.

### 0.5 Z80 Initialization & Sound System Bootstrap

**Z80 bus control registers:**

| Register | Address | Write |
|----------|---------|-------|
| Bus Request | `$A11100` | `$0100` = request, `$0000` = release |
| Reset | `$A11200` | `$0100` = run, `$0000` = assert reset |
| Z80 RAM | `$A00000-$A01FFF` | 8KB, **byte writes only** |

**Init sequence** (with YM2612-safe timing):

```asm
; Phase 1: Assert reset, request bus
        move.w  d0, (a2)                ; Assert Z80 reset (d0 = 0, active low)
        move.w  d7, (a1)                ; Request Z80 bus (d7 = $0100)
        move.w  d7, (a2)                ; Release Z80 reset

; Phase 2: Wait for bus grant
.wait_z80:
        btst    d0, (a1)                ; Poll bus grant (bit 0)
        bne.s   .wait_z80              ; Loop until Z80 stops

; Phase 3: Load Z80 program (byte writes!) — the full sound driver when
; SOUND_DRIVER_ENABLED (the default build), the idle program otherwise.
; a5 already points at the included blob in BootData.
    ifdef SOUND_DRIVER_ENABLED
        move.w  #Z80_SOUND_SIZE-1, d1   ; word count — blob may exceed moveq range
    else
        moveq   #Z80_IDLE_SIZE-1, d1
    endif
.load_z80:
        move.b  (a5)+, (a0)+            ; Copy to Z80 RAM
        dbf     d1, .load_z80

; Phase 4: Reset with YM2612-safe delay
        move.w  d0, (a2)                ; Assert reset (d0 = 0)
        moveq   #25, d2                 ; ~264 cycles delay (YM2612 needs ≥192)
.ym_delay:
        dbf     d2, .ym_delay
        move.w  d7, (a2)                ; Release reset — Z80 starts running
        move.w  d0, (a1)                ; Release bus — Z80 has control
```

**Z80 idle program** (`engine/system/z80_init.emp` — used only in sound-OFF builds):

Clears Z80 RAM *after its own code* via LDIR (BC/DE/HL computed from the assembled program size, stack parked at the program end for the pops), pops IX/IY/both register banks clean from the zeroed RAM, clears I and R, re-seeds SP to $1FFE (the top of the Z80's own 8KB RAM, matching the sound driver's `SND_STACK_TOP`), sets `di`/`im 1`, then self-patches a `jp (hl)` opcode ($E9) at Z80 address 0 and jumps to it — the idle loop is a single 1-byte instruction spinning at address 0, not a two-address `jp` loop:

```z80
        ...
        ld      sp, 1FFEh           ; real stack top — NOT `ld sp, hl` (hl == 0 here)
        di
        im      1
        ld      (hl), 0E9h          ; patch: jp (hl) opcode at address 0
        jp      (hl)                ; idle loop — jp (hl) at 0 jumps to itself
```

**Sound-driver loading:** the driver (`engine/sound/z80_sound_driver.emp`, a `(cpu: z80)` module) is pre-assembled into a `phase 0` blob that boot embeds in the `BootData` table (`engine/system/boot_data.emp` embeds **two** — `z80_sound_blob.bin` and `z80_sound_blob_debug.bin` — and `ShapeBlob` selects on `DEBUG`); in the default build (`SOUND_DRIVER_ENABLED`) it is what boot copies into Z80 RAM — the idle program is included and loaded *only* in sound-OFF builds. Nothing is streamed over the bus at title-screen init.

**Critical hardware rule** (from plutiedev): the Z80 must never fetch from the 68K bus (e.g., reading ROM for music data) while a DMA transfer runs — DMA loads garbage. This is not optional — it corrupts art on real hardware, especially early board revisions. How we enforce it depends on the build:
- **Sound-OFF build:** classic full fence — `stopZ80` before the VBlank DMA pipeline, `startZ80` after.
- **Sound build (default):** the `SND_CTRL_DMA_ACTIVE` flag bracket (MegaPCM-2 drain model, §6) supersedes the blanket fence. VBlank raises the flag before any VDP work and clears it after the last DMA; the Z80 driver checks it every sample and takes its RAM-only DRAIN path while set, so no ROM fetch can land inside a DMA burst. The DMA pipeline itself runs with the Z80 *free* — only the two flag-byte writes briefly bus-hold. See `engine/system/vblank.emp`.

### 0.6 PSG Silence & YM2612 Reset

**PSG** ($C00011, SN76489 — 3 tone + 1 noise channel):

Volume attenuation of $F = silent. Each channel has a latch byte format: `1 CC 1 AAAA` where CC = channel, AAAA = attenuation.

```asm
; Silence bytes — 4, in the BootData table (engine/system/boot_data.emp,
; BootData_PostBlob); boot reads them with the same sequential (a5)+ cursor.
        dc.b    $9F, $BF, $DF, $FF      ; channels 0-3 at max attenuation

; Init code — runs AFTER the VRAM fill completes (see below)
        moveq   #3, d2
.silence_psg:
        move.b  (a5)+, PSG_DATA_OFF(a3) ; a3 = $C00000 (VDP data); PSG_DATA_OFF = $11
        dbf     d2, .silence_psg
```

**Placement is load-bearing.** These four writes sit *below* the DMA-fill wait, not inside
the parallel window (§0.7). The PSG is decoded inside the VDP, so a write to $C00011 while
the VRAM fill is in flight is a real-hardware hazard (plutiedev). Their old placement
inside the window was safe only *temporally* — the 64KB RAM clear (~360k cycles ≈ 47 ms)
strictly dominates the display-off fill (~21 ms) — never topologically: a future shrink of
the clear would have re-opened the race with no gate to catch it. Corrected 2026-08-04
(review item 27, finding 2). The window invariant is now absolute: **nothing VDP-decoded,
data port or PSG, may be touched between the fill trigger and the fill wait.**

**YM2612 reset** (FM synth at $A04000-$A04003):

The Z80 idle program handles this implicitly by clearing Z80 RAM (which includes the YM2612 register cache). But on soft reset, leftover FM voices may still be sounding. Explicit silence:

```asm
; Key-off all 6 FM channels (register $28) — runs after the CRAM/VSRAM clears
        stopZ80
        lea.l   (YM2612_A0).l, a6
        move.b  #$28, (a6)             ; Select Key On/Off register
        moveq   #2, d2                 ; Channels 0-2 (Part I)
.keyoff_part1:
        move.b  d2, 1(a6)              ; Key off (all operators off, channel = d2)
        dbf     d2, .keyoff_part1
        moveq   #6, d2                 ; Channels 3-5 (Part II: $04, $05, $06)
        moveq   #2, d1
.keyoff_part2:
        move.b  d2, 1(a6)
        subq.w  #1, d2
        dbf     d1, .keyoff_part2
        startZ80
```

### 0.7 Memory Clearing — DMA-Parallel Pattern (NOVEL)

**Key insight from modern async I/O:** DMA fill runs on the VDP's own clock, independent of the 68000. While VRAM fills, the CPU can clear Work RAM, init the Z80, and silence PSG simultaneously. No reference game exploits this during boot — they all wait serially.

**Sequence:**

```
1. Prime DMA fill (set regs $13-$17 during VDP init — already done in §0.3)
2. Start VRAM fill: set increment=1, write destination + trigger word → DMA runs in background
3. While DMA runs: init Z80 (bus dance, program copy, YM-safe reset)
4. While DMA runs: clear 68K RAM (64KB = ~180,000 cycles)
5. After CPU work: poll DMA busy bit, wait for fill to complete
6. Silence PSG (4 bytes — VDP-decoded, so strictly after the fill, §0.6)
7. Restore increment=2
8. Clear CRAM (128 bytes — fast CPU loop)
9. Clear VSRAM (80 bytes — fast CPU loop)
```

Only steps 3 and 4 ride the fill window, and both are entirely off-VDP. Nothing between
the trigger (step 2) and the wait (step 5) may touch the VDP data port — a data write
mid-fill both lands in VRAM *and* replaces the fill byte — nor the VDP-decoded PSG port.

**Work RAM clear** (64KB, ~180,000 cycles):

```asm
        moveq   #0, d0
        movea.l d0, a6                  ; a6 = $00000000
        move.w  #$3FFF, d6             ; 16384 longwords = 65536 bytes
.clear_ram:
        move.l  d0, -(a6)              ; Write zero, decrement address
        dbf     d6, .clear_ram         ; a6 wraps: $00000000 → $FFFFFFFC → ... → $FFFF0000
```

**CRAM clear** (128 bytes = 64 colors):

```asm
        move.l  #$C0000000, (a4)       ; vdpComm($0000, CRAM, WRITE)
        moveq   #$1F, d0              ; 32 longwords
.clear_cram:
        move.l  d1, (a3)               ; d1 = 0, a3 = VDP data port
        dbf     d0, .clear_cram
```

**VSRAM clear** (80 bytes = 40 scroll values):

```asm
        move.l  #$40000010, (a4)       ; vdpComm($0000, VSRAM, WRITE)
        moveq   #$13, d0              ; 20 longwords
.clear_vsram:
        move.l  d1, (a3)
        dbf     d0, .clear_vsram
```

**DMA Fill cannot clear CRAM or VSRAM** — it only works on VRAM. CPU loops are required for those, but they're small (128 + 80 bytes = ~210 cycles total).

### 0.8 Region Detection & Timing Constants

**Version register** ($A10001):

```
Bit 7: MODE  — 0 = Domestic (Japan), 1 = Overseas (US/Europe)
Bit 6: VMOD  — 0 = NTSC (60Hz), 1 = PAL (50Hz)
Bit 5: DISK  — 0 = FDD connected, 1 = no FDD
Bit 4: Reserved
Bits 3-0: VER — Hardware revision
```

**Timing constants** derived from region:

| Parameter | NTSC | PAL |
|-----------|------|-----|
| Frame rate | 60 Hz | 50 Hz |
| Scanlines/frame | 262 | 312 |
| Active display | 224 lines (V28) | 224 or 240 lines (V30) |
| VBlank lines | ~38 | ~72 (PAL has nearly **double** VBlank time) |
| CPU clock | 7,670,454 Hz | 7,600,489 Hz |
| Cycles/scanline | ~488 | ~488 |
| VBlank cycles | ~18,500 | ~35,100 |
| DMA bandwidth/VBlank | ~7.5 KB (NTSC) | ~14 KB (PAL) |

**Design — detect once, bake into RAM:**

The region branch happens exactly once, at boot — the chosen value (`DMA_Budget_Default`) is stored in RAM and consumed from there, so no runtime code re-tests the region flag on hot paths:

```asm
; Detection (runs once at boot)
        move.b  (HW_VERSION).l, d0
        move.b  d0, (Hardware_Region).w ; Store full byte for later queries
        andi.b  #$C0, d0
        move.b  d0, (Region_Flags).w    ; Bit 7 = overseas, bit 6 = PAL
        btst    #6, d0
        bne.s   .pal
        move.w  #DMA_BUDGET_NTSC, (DMA_Budget_Default).w
        bra.s   .region_done
.pal:
        move.w  #DMA_BUDGET_PAL, (DMA_Budget_Default).w
.region_done:

; Compile-time constants (engine/system/constants.emp — these two are the ones that exist)
DMA_BUDGET_NTSC         = 6144      ; per-VBlank blanking-window capacity, DMA-byte-equiv
DMA_BUDGET_PAL          = 11648     ; PAL window capacity (nearly double the blank lines)
```

These are the **window-charged** budget model (m1-budget-fix): `DMA_Budget_Default` is seeded into `DMA_Budget_Remaining` at the *top* of `VInt_Level`, and the frame's big window riders (the plane-buffer drain and the mandatory Critical DMA) then **charge** it as they run, so the Important/Deferrable drain sees the true blanking-window headroom left — not a flat "usable bytes" allowance. Derivation (oracle cycle model): blanking window ≈ 488.6 68k cyc/line × 38 blank lines (NTSC) / 72 (PAL) → ~6876 / ~13029 raw bytes at ~2.7 cyc/byte, × ~0.89 safety margin for the uncharged non-DMA VInt tail ≈ 6144 / 11648. See §1.1 and `engine/system/constants.emp`.

The scanline/cycle table above is hardware background, not engine constants — no `VBLANK_LINES`/`CYCLES_PER_VBLANK` symbols exist in code.

**PAL timing compensation: none — NTSC-only product (ruling B, 2026-08-02).** The engine
commits to NTSC-only. `GameLoop` dispatches exactly one game-state tick per VSync
unconditionally (`engine/system/game_loop.emp`), so on PAL hardware the whole game runs
at 50 Hz uncompensated (~5/6 speed) — accepted, matching classic frame-based PAL slow.
The half-built fixed-timestep accumulator (`Timing_Step`/`Frame_Accumulator` +
`NTSC_TIMING_STEP`/`PAL_TIMING_STEP`) that would have driven PAL compensation was deleted
rather than left as dead scaffolding — it had zero readers. Only the region-adaptive DMA
budget survives the region branch (the drain reads `DMA_Budget_Default`). The three
compensation approaches once considered (Sonic 3 speed multiplier, Treasure frame-skip,
the accumulator) are recorded in the DEFERRED_WORK PAL entry as historical design context.

### 0.9 Controller Port Initialization

**I/O control registers:**

| Port | Data | Control |
|------|------|---------|
| Port 1 (player 1) | `$A10003` | `$A10009` |
| Port 2 (player 2) | `$A10005` | `$A1000B` |
| Expansion | `$A10007` | `$A1000D` |

**Init** (TH pin as output for joypad protocol, driven high as the initial state):

```asm
        move.b  #$40, (HW_PORT_1_CTRL).l    ; Port 1: TH = output
        move.b  #$40, (HW_PORT_2_CTRL).l    ; Port 2: TH = output
        move.b  #$40, (HW_EXPANSION_CTRL).l ; Expansion: TH = output
        move.b  #$40, (HW_PORT_1_DATA).l    ; Port 1: TH high (initial state)
        move.b  #$40, (HW_PORT_2_DATA).l    ; Port 2: TH high
        move.b  #$40, (HW_PORT_EXP_DATA).l  ; Expansion: TH high
```

6-button detection and full controller reading protocol are in §9.4. Boot only sets pin direction and the initial TH level — actual polling happens in VBlank.

### 0.10 Interrupt System — Dispatch Architecture

**VBlank (IRQ6) — function pointer dispatch with lag detection (implemented in §1):**

```asm
VBlank_Handler:
        movem.l d0-a6, -(sp)
        tst.b   (VBlank_Ready).w        ; Main loop signals readiness each frame
        beq.s   .lag
        movea.l (VInt_Ptr).w, a0        ; Dispatch through RAM pointer (VInt_Level, etc.)
        jsr     (a0)
        bra.s   .done
.lag:
        bsr.w   VInt_Lag                ; Reduced handler — skips the plane-buffer drain
.done:
;       DEBUG && SOUND_DRIVER_ENABLED && SOUND_DBG_MIRROR only:
;       bsr.w   Sound_DebugMirror       ; Z80-state snapshot (stops the Z80 ~190us)
        clr.b   (VBlank_Ready).w
        movem.l (sp)+, d0-a6
        rte
```

`VInt_Level` (normal frames) runs: DMA-window open (sound build: raise `SND_CTRL_DMA_ACTIVE` flag bracket; sound-OFF build: stopZ80 — see §0.5) → **seed window budget** (`DMA_Budget_Default` → `DMA_Budget_Remaining`, before any VDP work, §0.8) → Flush_VDP_Shadow → Enqueue_Dirty_Buffers → *charge plane drain* (subtract `Plane_Buffer_Ptr`) → VInt_DrawLevel (Plane_Buffer drain, §4.1) → *charge Critical DMA* (subtract the queued entry bytes, floor budget at 0) → Process_DMA_Critical → Vscroll_Write (VSRAM write must come **after** the HScroll DMA, §4.6) → Process_DMA_Important → Process_DMA_Deferrable → DMA-window close (clear flag / startZ80) → Read_Controllers → press-edge latch (main `SACBRLDU` + 6-button `MXYZ` ext) → frame counter → VBlank_Flag. The budget is seeded once at the top and drawn down by the two big riders, so Important/Deferrable see the true leftover window, not a flat allowance.

`VInt_Lag` (lag frames) runs the same pipeline **minus** VInt_DrawLevel and the Important/Deferrable drains: shadow flush, dirty-buffer enqueue, Critical DMA, VSRAM write, controllers, frame counter, VBlank_Flag (plus `Lag_Frame_Count` in DEBUG). The plane-buffer drain is deliberately skipped — on a lag frame the main loop is still mid-fill and the buffer may be torn. See §1.4 for details.

**HBlank (IRQ4) — RAM jmp-slot trampoline** (`engine/system/hblank.emp`; §1.8). The IRQ4 vector points *directly* at `HBlank_Vector_Slot`, a 6-byte executable RAM slot. No ROM dispatch stub, no pointer read, no wrapper `jsr` — the interrupt reaches the handler through one `jmp`, and the handler owns its own save/restore and terminates with `rte`. The slot holds one of two forms:

```asm
; In RAM — the IRQ4 vector ($70) points here
HBlank_Vector_Slot:     ds.b 6          ; executable instruction slot
; idle:  $4E73                          → rte           (no raster handler)
; armed: $4EF9, handler.l               → jmp handler.l (HBlank_Install target, §7.2)
```

`HBlank_Install(a0=handler, d0=line counter)` patches the slot to `jmp a0`, programs the HInt line counter (reg $0A) and sets IE1 (reg $00 bit 4) — all register writes through the VDP shadow (§0.4) so `Flush_VDP_Shadow` never reverts the enable. `HBlank_Uninstall` restores the idle `rte` *first* (a direct, instant RAM store, so any in-flight HInt hits a bare `rte`) then clears IE1. Boot seeds the slot with an `rte` pair (`move.l #$4E734E73, HBlank_Vector_Slot`) before interrupts unmask.

**Default HBlank behavior** (no raster effects active): the slot decodes to a bare `rte` — immediate return, no register save/restore, no pointer load.

**Why a RAM instruction slot for HBlank but a pointer for VBlank:** HBlank fires up to 224 times per frame and must be as fast as possible — executing an instruction straight out of RAM saves the pointer-load and indirect-`jsr` a dispatched design would pay on every line, so the null case is a single `rte`. VBlank fires once per frame but needs mode-specific behavior (VInt_Level, VInt_Lag, future VInt_Menu/VInt_Load). The `VInt_Ptr` RAM pointer selects the mode; the lag detection is handled in the ROM dispatcher itself via the `VBlank_Ready` flag.

### 0.11 Soft Reset Detection

**Problem:** When the user presses RESET, only the 68000 resets. VDP, Z80, VRAM, CRAM, all retain their state. A running DMA may still be in progress.

**What is implemented (and ruled final 2026-08-05):** soft-reset *detection* and DMA safety only. `Warm_Boot` waits for any in-flight DMA to finish and then falls through to `Cold_Boot` — the full hardware init runs on every boot, warm or cold:

```asm
EntryPoint:
        tst.l   (HW_PORT_A_CTRL_FULL).l     ; Port A control — zero on cold boot, non-zero on soft reset
        bne.s   Warm_Boot
        tst.w   (HW_EXPANSION_CTRL_FULL).l  ; Expansion control — second check
        beq.s   Cold_Boot

Warm_Boot:
.wait_dma:
        move.w  (VDP_CTRL).l, d0
        btst    #1, d0                  ; DMA busy flag
        bne.s   .wait_dma
        ; Fall through to Cold_Boot — nothing is preserved.

Cold_Boot:
; Full hardware init (§0.2-§0.9)
```

There is **no reserved persistence region and no magic marker** in code today. `$FFFFFF00` is the initial stack pointer (`SYSTEM_STACK`, `engine/system/constants.emp`), not a reserved cross-reset block — no `CROSS_RESET_RAM` or `CROSS_RESET_MAGIC` symbol exists (`grep engine/ games/` returns only `SYSTEM_STACK`), and boot writes no marker at the end of init. Every boot, warm or cold, runs the full RAM clear and full hardware init; nothing survives a soft reset.

> **CrossResetRAM persistence was RULED OUT (Volence, 2026-08-05) and its design is
> deleted, not deferred.** Two reasons. (1) It straddles the engine/game wall badly:
> warm/cold *detection* is engine (it lives in boot), but the *policy* — what is worth
> preserving — is pure game (the demo has no score to keep), so the engine would have to
> reserve a region it cannot give meaning to. (2) **SRAM (§9.6) is the persistence
> mechanism for this project.** It survives power-off, not just reset, and it is the
> right home for saves, best times and unlocks. The one thing SRAM cannot replicate is
> live-at-the-instant-of-reset state — cross-reset RAM works precisely because you write
> nothing at reset time (reset raises no interrupt), whereas SRAM only holds what was
> deliberately written earlier. That narrow gap ("keep the exact live score through a
> RESET press") is not a feature worth an engine/game contract.
>
> Soft-reset detection + the DMA-safe warm path above STAY — they are real, they ship,
> and they are what stops an in-flight DMA from scribbling over fresh init code.

### 0.12 Boot Sequence — Complete Execution Order

The real order from `engine/system/boot.emp`:

```
Power On
  ├── 68000 reads SSP from $000000 ($FFFFFF00)
  ├── 68000 reads Reset PC from $000004 (EntryPoint)
  │
  EntryPoint:
  ├── Reload sp from SYSTEM_STACK (lea (SYSTEM_STACK).w, sp — redundant after a
  │   hardware reset, load-bearing after a software jmp EntryPoint; §0.2)
  ├── Soft reset check ($A10008 tst.l / $A1000C tst.w)
  │     ├── Warm_Boot: poll VDP status bit 1 until DMA idle, FALL THROUGH to Cold_Boot
  │     └── Cold: continue below
  │
  Cold_Boot:
  ├── TMSS handshake ($A10001 revision-nibble test, "SEGA" → $A14000 if non-zero)
  ├── Read VDP control port (reset command word state machine)
  ├── movem preload d5-d7/a0-a4 from BootData
  │
  ├── VDP register init ($00-$17, 24 registers from table)
  │     └── Register $17 = $80 primes DMA fill
  ├── Set auto-increment to 1 ($8F01 — explicit write, not the table value)
  ├── Start VRAM DMA fill (write dest+trigger → VDP fills 64KB in background)
  │
  ├── WHILE DMA RUNS (parallel work — strictly off-VDP, §0.7):
  │     ├── Init Z80 (reset/bus dance, load sound driver — or idle blob when
  │     │   sound is off — reset with YM2612-safe delay, release bus)
  │     └── Clear Work RAM (64KB via wrapping predecrement, ~180,000 cycles)
  │
  ├── Wait for DMA fill completion (poll VDP status bit 1)
  ├── Silence PSG (4 bytes to $C00011 — VDP-decoded, so only after the fill, §0.6)
  ├── Restore auto-increment to 2 ($8F02)
  ├── Clear CRAM (32 longs via CPU loop)
  ├── Clear VSRAM (20 longs via CPU loop)
  ├── YM2612 key-off all 6 FM channels (stopZ80/startZ80 bracket)
  │
  ├── Clear all 68K registers (movem.l (RAM_Start).w, d0-a6)
  ├── disableInts (SR = $2700 while the subsystem inits run)
  │
  ├── VDP_Shadow_Init (copy boot register values into shadow, §0.4)
  ├── Init_DMA_Queue (§1.1)
  ├── Init_SpriteTable (link chain, §1.3)
  ├── BuildStaticDMA (§1.5)
  ├── Set VInt_Ptr = VInt_Level (§1.2)
  │
  ├── Region detection ($A10001 → Hardware_Region/Region_Flags,
  │   bake DMA_Budget_Default; NTSC-only, no timestep — §0.8)
  ├── Controller port init ($40 → 3 control regs AND 3 data ports, §0.9)
  ├── Init HBlank_Vector_Slot to idle rte (move.l #$4E734E73 → HBlank_Vector_Slot, §0.10)
  │
  ├── Shadow write mode2 = $34 (VInt enable in VDP — display still OFF)
  ├── Flush_VDP_Shadow (VInt enabled in hardware before unmasking)
  ├── enableInts — interrupts are LIVE from here on (SR = $2300)
  │
  ├── DEBUG builds: CompressionSelfTest (golden decompressor self-test)
  ├── Sound builds: Sound_Init (Z80 mailbox idle handshake)
  ├── gameBootHook (game-supplied, may be empty)
  │
  ├── Set Game_State = Game.entry, Game_State_ID = Game.ENTRY_ID,
  │   clear Game_State_Init (the game manifest's entry contract — Sonic 4 binds
  │   these to GameState_OJZScroll_Init / GS_OJZ_SCROLL_TEST)
  └── bra.w GameLoop (never returns)
        └── The game's entry state runs first
            (sound driver already loaded over the Z80 at boot)
```

Note the final interrupt state: boot **enables** interrupts (`enableInts`, SR = $2300) before entering `GameLoop` — VBlank is live during the self-test, Sound_Init, and the game's first state. There is no masked $2700 handoff.

### 0.13 Boot-Time Data Tables

**Sine/Cosine table** (`engine/system/math.emp`, S.C.E./Sonic 2 format): 320 word entries embedded from `engine/data/sine.bin` — one full cycle over 256 angle units plus a quarter-cycle overlap so `cos(angle) = Sine_Table[angle + $40]` with no wrap logic. Output amplitude is $100 (sin(90°) = $100), matching the classic Sonic physics scale. One angle unit = 360°/256 ≈ 1.41°.

```asm
GetSineCosine:                              ; d0.b = angle → d0.w = sin×$100, d1.w = cos×$100
        andi.w  #$FF, d0
        add.w   d0, d0
        addi.w  #$40*2, d0                  ; +90° for cosine
        move.w  Sine_Table(pc,d0.w), d1     ; cos
        subi.w  #$40*2, d0
        move.w  Sine_Table(pc,d0.w), d0     ; sin
        rts

Sine_Table:
        BINCLUDE "engine/data/sine.bin"     ; 320 words, amplitude $100
```

**RNG** — **Status: design, not implemented (verified 2026-08-02).** The `RNG_Seed: u32` RAM slot exists (`engine/ram.emp`), but no `Random_Number` routine has been written yet. When needed, the plan is a linear congruential generator (same as S.C.E.): multiply-by-41 via shift/add on the 32-bit seed, swap-and-add to mix the halves, returning a random word in d0 — with a rescue constant for the zero-seed degenerate case.

**Fixed-point convention** (documented here, used everywhere):

| Type | Format | Range | Use |
|------|--------|-------|-----|
| Position | 16.16 | ±32767.9999 pixels | Object/camera X/Y |
| Velocity | 8.8 | ±127.996 px/frame | Object speeds |
| Subpixel | 0.8 (low byte of word) | 0.004-0.996 | Fractional accumulation |
| Angle | 0-255 (byte) | 360° in 256 steps | Slope angles, rotation |
| Sine result | 8.8 (signed word, amplitude $100) | -1.0 to +1.0 | Trig results (`GetSineCosine`) |

### 0.14 Cascade Effects

Changes in this section that ripple to other sections:

| Decision | Affects | How |
|----------|---------|-----|
| SSP = $FFFFFF00 | §8.3 Error Handler | Stack guard checks adjusted for high-RAM stack |
| VDP shadow table | §1 DMA Pipeline | DMA queue writes to shadow, not direct VDP |
| VDP shadow table | §7 Visual Effects | HInt/section transitions use shadow writes, flush in VBlank |
| RAM-slot HBlank trampoline | §7.2 HBlank System | Section transitions rewrite the RAM slot instruction (`jmp handler` / idle `rte`) via HBlank_Install/Uninstall, not the vector |
| 64×64 plane init | §2.3 VRAM Layout | Plane size register confirmed, nametable addresses validated |
| Region detection | §5 Player Physics | NTSC-only (ruling B, 2026-08-02); PAL runs uncompensated ~5/6 speed, no timing accumulator — §0.8 |
| Region detection | §1.1 DMA Queue | PAL gets nearly double DMA budget — adaptive byte count |
| Controller port init | §9.4 6-Button | Boot sets TH output; VBlank reads using rapid TH cycling |
| Z80 idle program | §6 Audio | Boot loads the sound driver directly when SOUND_DRIVER_ENABLED (default); the idle program ships only in sound-OFF builds |
| Soft-reset handling | §9.5 Soft-Reset | Boot detects warm/cold (DMA-safe fall-through to full init); nothing preserved BY DESIGN — CrossResetRAM persistence ruled out 2026-08-05, SRAM (§9.6) is the mechanism |
| DMA-parallel init | §1.1 DMA Queue | Validates that DMA fill + CPU work can overlap safely |

---

## 1. Core VDP Pipeline

The VDP pipeline governs everything that reaches the screen: DMA transfers, sprite rendering, scroll plane drawing, and interrupt handling. Every system in the engine ultimately feeds data into this pipeline.

### 1.1 DMA Queue System

**Purpose:** Centralize all VDP memory transfers through a single, priority-ordered queue system. The main game loop never stalls on DMA — it enqueues transfers, and VBlank drains them.

**Architecture: Three Priority Sub-Queues**

```
┌─────────────────────────────────────────────────┐
│                  DMA Queue RAM                  │
├──────────────┬───────────────┬───────────────────┤
│  Critical    │  Important    │  Deferrable       │
│  8 slots     │  12 slots     │  12 slots         │
│  112 bytes   │  168 bytes    │  168 bytes        │
├──────────────┼───────────────┼───────────────────┤
│ Palette      │ Char DPLCs    │ S4LZ art stream   │
│ Sprite table │ Animated tiles│ Section preload    │
│ Hscroll buf  │               │ Background art     │
├──────────────┼───────────────┼───────────────────┤
│ ALWAYS drain │ Budget-gated  │ Budget-gated,      │
│ Unrolled     │ addr-compare  │ addr-compare loop  │
│ jump table   │ loop          │ (shared routine)   │
│ ~514 cycles  │               │                    │
└──────────────┴───────────────┴───────────────────┘
Total: 32 slots × 14 bytes = 448 bytes RAM
```

**Entry format:** Flamewing Ultra DMA Queue 14-byte entries (`DMAEntry` struct, `engine/structs.emp`). VDP register-marker bytes sit at the EVEN offsets (0, 2, 4, 6, 8), written once at boot by `Init_DMA_Queue`/`BuildStaticDMA` via `movep`; size/source data bytes are interleaved at the ODD offsets (1, 3, 5, 7, 9). The drain loop never touches the marker bytes — it writes pre-computed VDP commands directly, zero computation during VBlank.

```
Offset  Field    Contents
0       Reg94    VDP reg $14 marker (movep target)
1       SizeH    DMA length high byte
2       Reg93    VDP reg $13 marker
3       SizeL    DMA length low byte
4       Reg97    VDP reg $17 marker
5       SrcH     source address bits 22-16
6       Reg96    VDP reg $16 marker
7       SrcM     source address bits 15-8
8       Reg95    VDP reg $15 marker
9       SrcL     source address bits 7-0
10-13   Command  VDP command longword (destination + DMA trigger)
```

**Drain strategy — hybrid unrolled/address-compare loop:**

- **Critical queue (8 slots), `Process_DMA_Critical`:** Jump-table unrolled drain. The slot pointer is converted to a queue offset (`suba.w #DMA_Critical, a1`) then used as a jump index (`jmp .jump_table(a1)`) into fully unrolled `move.l/move.l/move.l/move.w` sequences, one block per possible fill level. Zero comparisons, zero branches per entry. ~514 cycles to drain all 8 entries. Always drains fully — never budget-gated. Note: S.C.E. uses `jmp table-queue(a1)` directly, but our RAM layout puts the queue too far from ROM for a 16-bit displacement — the two-instruction split is functionally equivalent. Ported from S.C.E.'s `Process_DMA_Queue`.
- **Important + Deferrable queues (12 slots each), `Process_DMA_Important`/`Process_DMA_Deferrable`:** Both tail-call into a single shared routine, `Drain_Budgeted_Queue`. This is **not** a `dbf`-counted loop — each iteration checks `DMA_Budget_Remaining` (`ble .out_of_budget`) and terminates by comparing the current queue pointer against the slot's first-free address (`cmpa.l a0,a1 / bhi .loop`). When the budget runs out mid-queue, the routine **compacts** the undrained entries down to the queue base (`.compact`) so they persist to the next frame rather than being dropped — see "Overflow handling" below.

**Why hybrid, not fully unrolled:** Unrolling all 32 slots costs 704 bytes ROM. The hybrid approach costs ~280 bytes — 60% smaller with 60% of the performance benefit. The critical queue (where every cycle matters for visual stability) gets the fast path. The budget-gated queues (where one extra frame of latency is acceptable) share one compact loop.

**Static DMA for fixed transfers:** Sprite table (640 bytes = $280 → VRAM `VRAM_SPRITE_TABLE`) always transfers from the same RAM address to the same VRAM address with the same size. Its 14-byte DMA entry is pre-computed once at boot (`BuildStaticDMA`, called once after `Init_DMA_Queue` — not at level init) and conditionally re-copied into the Critical queue by `Enqueue_Dirty_Buffers` each frame the dirty flag is set, bypassing the `QueueDMATransfer` enqueue logic (boundary check, SR masking, source-shift) entirely via the `queueStaticDMA` macro.

**Per-palette-line dirty DMA:** Palette uses a 4-bit dirty bitmask (`Palette_Dirty`, one bit per palette line = 32 bytes). Each frame, only dirty lines are enqueued as Critical DMA via `Enqueue_Dirty_Buffers`. On a typical gameplay frame, only the lines that actually changed are re-sent; on section transitions, all 4 bits set. The palette-line-to-content mapping (e.g. "Line 0 = BG/environment") is a game-side content convention, not something the engine enforces — the engine only knows about 4 independent dirty bits.

**Hscroll DMA — two fixed-size static entries, not variable-range:** `Hscroll_Dirty_Start`/`Hscroll_Dirty_End` fields exist in RAM (`engine/ram.emp`) but are dead — nothing reads them. The shipped mechanism (`Enqueue_Dirty_Buffers`, §4.6) enqueues one of exactly two build-time-fixed static entries depending on parallax mode: `Static_Hscroll_Cell` (112 bytes, per-cell mode) or `Static_Hscroll_Line` (896 bytes, per-line mode, used when an H-deform table is active on either plane). There is no computed dirty-range transfer.

**VBlank DMA budget — window-charged model (m1-budget-fix, chain-21):**

`DMA_BUDGET_NTSC` = **6144** and `DMA_BUDGET_PAL` = **11648** (`engine/system/constants.emp`) are the per-VBlank **blanking-window capacity** (DMA-byte-equiv), wired into `DMA_Budget_Default` at boot by region (`engine/system/boot.emp`). They are **not** a flat "usable bytes" allowance: `VInt_Level` seeds `DMA_Budget_Remaining` from `DMA_Budget_Default` at the top of the frame, then the two big window riders **charge** it as they run — the plane-buffer drain subtracts `Plane_Buffer_Ptr` (pending buffer bytes) and the mandatory Critical DMA subtracts its queued entry bytes (walked from the queue), with the result floored at 0. Only then do `Process_DMA_Important` / `Process_DMA_Deferrable` run, so they see the *true* headroom left in the window, not the whole window as if nothing had run. Derivation (oracle cycle model): ~488.6 68k cyc/line × 38 blank lines NTSC / 72 PAL → ~6876 / ~13029 raw bytes at ~2.7 cyc/byte, × ~0.89 margin ≈ 6144 / 11648 (§0.8).

| System | VBlank Lines | Window capacity (`DMA_BUDGET_*`) |
|--------|-------------|-----------------------------------|
| NTSC H40 | ~38 | 6144 |
| PAL H40 | ~72 | 11648 |

**Lag-history feedback budget — design, not implemented.** A further adaptation — shrinking the Important/Deferrable budget for a frame or two after a lag event then gradually restoring it, plus a temporary 1.5× Deferrable boost to flush backlog — does **not** exist. The shipped budget is window-charged per frame (above) but carries no lag *history*: each frame reseeds from `DMA_Budget_Default` independent of prior frames' overruns. Left as a design note for a future self-tuning pass; inspired by Vectorman's `cmpi.w #$B40` budget check, extended with feedback that was never built.

**128KB boundary safety — implemented.** The VDP increments only the low 17 bits of the 23-bit DMA source address; transfers crossing a 128KB boundary wrap within the same block and produce garbage. `QueueDMATransfer` (`engine/system/dma_queue.emp`) detects this via a sub+sub carry check (`sub.w d3,d0 / sub.w d1,d0 / blo .split`, comparing source+length words against the boundary) and, on a crossing, splits the transfer into two queue entries in the `.split` path: the first part finishes at the boundary, the second continues from the wrapped source with the correct destination offset. The split requires a second free slot in the same sub-queue (checked via `subi.w #DMAEntry_len,d4 / cmpa.w d4,a1`); if only one slot is free, only the first part is enqueued and the routine still returns carry-clear (documented in the routine's header comment as a known, vanishingly-rare edge case for small DPLC transfers that straddle a boundary).

**RAM source address safety:** When a RAM source address ($FF0000+) is right-shifted by 1 for the VDP, bit 23 can become set, which the VDP interprets as a VRAM copy flag instead of 68K→VDP DMA. `QueueDMATransfer` clears bit 23 after the shift (`bclr.l #23,d1`).

**VInt safety:** SR masking (disable interrupts) during `QueueDMATransfer`. Prevents queue corruption if VBlank fires mid-enqueue. Enabled for all three queues. `QueueDMATransfer` returns a documented carry contract: carry SET = request dropped (queue full), carry CLEAR = enqueued OK (including a fully-enqueued 128KB split) — callers such as `Perform_DPLC` check this and retry the following frame rather than losing the update.

**Three entry points:** `QueueDMA_Critical`, `QueueDMA_Important`, `QueueDMA_Deferrable` — each sets up the target sub-queue (slot pointer address + end address), then falls through to the shared `QueueDMATransfer` core. Callers provide: d1.l = source address, d2.w = VRAM destination, d3.w = transfer length (bytes).

**No double buffering.** Vectorman uses double-buffered queues (write to A, drain B, swap). With SR masking preventing mid-enqueue interrupts, double buffering solves a problem we don't have. Saves 448 bytes RAM.

**QueueStaticDMA macro:** For transfers with build-time-known source, destination, and length (sprite table, individual palette lines, hscroll), the `queueStaticDMA` macro bypasses `QueueDMATransfer` entirely. `BuildStaticDMA` pre-computes **7** static entries at boot: 4 palette lines, 1 sprite table, and 2 HScroll variants (per-cell/per-line, §4.6) — not the 5 (4 palette + sprite table) an earlier draft of this doc claimed, from before the HScroll static-DMA addition. Each entry is block-copied into the next queue slot by the macro. Used by `Enqueue_Dirty_Buffers` to populate the Critical queue from dirty flags. Adapted from Flamewing's `QueueStaticDMA`.

**Overflow handling:** In debug builds, `QueueDMATransfer`'s `.full` path increments `DMA_Overflow_Count` and returns carry-set; there is no queue-specific `trap` assertion on Critical-queue-full as an earlier draft of this doc claimed — overflow on all three queues is tracked through the same shared debug counter, not a hard trap. In release builds it silently returns without enqueueing (graceful degradation) either way. Important/Deferrable queues never "overflow" in the drop sense — when the budget runs out, `Drain_Budgeted_Queue`'s `.compact` path shifts the undrained entries to the queue base and updates the slot pointer so they persist to next frame; this is expected, budget-gated deferral, not an error condition.

**Dirty-flag retry — fixed.** `Enqueue_Dirty_Buffers` (`engine/system/buffers.emp`) clears each `Palette_Dirty` line bit / `Sprite_Table_Dirty` flag **only when its enqueue succeeded** (`queue_static_dma(...) / bcs .skip / bclr`). On a drop (Critical queue full — reachable during a fade + heavy art staging) the bit is left set so the next VBlank retries it, instead of clearing it and stranding stale palette/SAT data in VRAM. (This closes the unconditional-clear bug an earlier draft of this doc flagged as live in the 2026-07-16 review.)

**Debug profiling counters (§8 integration):** Behind `ifdef __DEBUG__` guards, the DMA system tracks: `DMA_Bytes_ThisFrame` (total bytes enqueued), `DMA_Peak_Critical` / `DMA_Peak_Important` / `DMA_Peak_Deferrable` (one high-water mark per sub-queue — not a single combined counter), `DMA_Overflow_Count` (enqueue rejections), `Lag_Frame_Count` (VBlank overruns). Readable via Oracle MCP or KDebug console. Zero cost in release builds.

**Why not S.C.E.'s hybrid (immediate + queued):** S.C.E. DMAs palette, sprites, and hscroll immediately during VBlank, using the queue only for art streaming (7 slots). We route everything through the queue because: (a) one code path to maintain, (b) the priority system gives us the same "critical transfers always complete" guarantee, (c) the queue provides byte budget enforcement and lag-frame behavior that immediate DMA can't.

**Cross-references:**
- Flamewing Ultra DMA Queue: entry format, boundary safety, VInt protection, QueueStaticDMA
- S.C.E. `DMA Queue.asm`: jump-table drain mechanism
- Vectorman: byte budget concept ($B40), pre-computed VDP command words, atomic batch enqueue
- Alien Soldier: dirty-region DMA concept (motivated the hscroll dirty-range design, though the shipped hscroll path ended up as two fixed-size static entries — see above), dirty flags for palette/sprites
- Batman: pre-staged VDP command buffer at fixed RAM addresses (applied to static DMA)
- Gunstar Heroes: conditional sprite DMA via dirty flags
- Thunder Force IV: round-robin sprite flicker for overflow (deferred to §1.2)
- plutiedev.com, Kabuto hardware notes: VBlank timing, DMA transfer rates, 128KB boundary, sprite cache write-through

---

### 1.2 Sprite System

**Purpose:** Convert object state into the VDP sprite attribute table efficiently, with priority sorting, overflow protection, and conditional DMA.

**Architecture: Two-Phase Render**

```
Phase 1 — During Object Loop          Phase 2 — Render_Sprites
┌─────────────────────────┐           ┌──────────────────────────┐
│ Object calls Draw_Sprite│           │ Walk priority-band lists │
│ → stores RAM addr into  │           │ → convert to VDP format  │
│   priority-band list    │           │ → write to Sprite_Table  │
│ (one pointer store,     │    then   │ → set Sprite_Table_Dirty │
│  no conversion yet)     │  ──────►  │ → clear unused entries   │
└─────────────────────────┘           └──────────────────────────┘
```

**Phase 1 — Draw_Sprite (during object loop):** Each visible object calls `Draw_Sprite`, which resolves the object's current mapping frame, culls exactly against the frame's precomputed bounding box (the 4-byte flip-invariant extent header at the front of each frame — 7.8), and on pass adds the object's RAM address to a priority-band list at `Sprite_Table_Input + priority`. No sprite data conversion happens here — pieces are emitted in Phase 2. Objects are automatically sorted by priority when they register.

**Phase 2 — Render_Sprites (after all objects processed):** Single pass through the priority-sorted lists. For each registered object, reads mappings, applies position offsets and flip flags, writes 8-byte VDP sprite entries to `Sprite_Table`. Sets `Sprite_Table_Dirty` flag when any entries are written.

**Why two-phase:** A naive approach iterates all objects N times (once per priority level), scanning the full object list each pass. With 40+ objects and 8 priority levels, that's 320+ iterations. The two-phase approach does one pass during the object loop (piggybacks on existing iteration) and one pass during Render_Sprites (only processes registered objects). Eliminates redundant full-table scans.

**Link chain pre-initialization:** `Init_SpriteTable` runs at level load and fills the 80-entry sprite link chain: entry 0 links to 1, 1 to 2, ..., 79 to 0. During gameplay, `Render_Sprites` writes the link byte for each emitted piece (sequential 0,1,2,...) and patches the last rendered piece's link to 0 as the chain terminator. The pre-init covers the unused tail of the SAT; per-frame writes are the source of truth for active entries. ("Never rebuilt" was investigated as a 68000 cycle optimization but is genuinely a wash — `move.b Dn,(An)+` and `addq.l #1,An` both cost 8 cycles, so skipping the write doesn't save anything once you account for advancing the pointer. S.C.E./Batman use the advance-past style, sonic_hack rewrites; both end up at the same per-piece cost.) Unused entries keep Y=0 (off-screen) from Init_SpriteTable; Render_Sprites writes link=0 to the last emitted entry to halt the VDP's chain walk early.

**Empty-table terminator (fixed 2026-07-16, a3eef59):** `Sprites_Rendered` is deliberately **not** cleared in `InitSpriteSystem` — it must persist across frames so `Render_Sprites`' had-sprites→none edge test (`.empty_table`) fires the hidden SAT terminator exactly once, on the transition to zero visible sprites. An earlier version of this code cleared `Sprites_Rendered` every frame, which defeated that edge test and could leave the previous frame's full link chain live in VRAM with its sprites frozen on screen ("ghost sprites"). Fixed by no longer resetting the counter in `InitSpriteSystem`; `Render_Sprites` owns clearing/writing it on every exit path instead.

**Sprite overflow handling — two layers:**

1. **Band overflow (from S.C.E.):** When a priority band is full ($80 bytes = 16 entries), `Draw_Sprite` overflows to the next band via `lea $80(a1),a1`. Prevents crashes but can cause priority inversion.
2. **Round-robin flicker (from TF4, optional):** If sprite overflow becomes visible in gameplay, add a frame counter that rotates which sprites get the first 80 slots. Over a 4-frame window, every sprite gets at least one frame of visibility. No sprite permanently hidden.

**Multi-sprite batching:** Composite objects (multi-part bosses, Tails' tails) set `render_flags.multi_sprite`. `Render_Sprites` gives the parent a single bounds check, then renders all child sprite pieces without redundant per-piece culling. Ported from S.C.E.'s `Render_Sprites_MultiDraw`.

**Sprite count per object:** Each object's SST includes a `sprite_piece_count` field, set at init from mapping data. This enables overflow prediction — before calling Draw_Sprite, the system can check if adding this object would exceed the 80-sprite limit. Inspired by Batman's `sprite_link_count` at object offset $18.

**Sprite table dirty flag:** `Sprite_Table_Dirty` byte, set by `Render_Sprites` after writing entries, cleared after DMA. Before enqueueing the sprite table DMA in the Critical queue, check this flag. If clear (no objects moved or animated since last frame), skip the $280-byte DMA entirely. This saves a Priority 0 queue slot and VBlank transfer time on static frames (pauses, cutscenes, menus, any calm moment). Confirmed by Gunstar Heroes' conditional sprite DMA pattern.

**VDP sprite cache is write-through:** The VDP maintains an internal cache of Y-position and size/link fields. This cache updates only via VRAM writes to the sprite table address — changing the sprite table base address register does NOT update the cache. Therefore the full sprite table must always be DMA'd to VRAM; you cannot swap tables by changing the VDP register alone.

**Cross-references:**
- S.C.E. `Draw Sprite.asm`, `Render Sprites.asm`: two-phase system, Init_SpriteTable, MultiDraw, band overflow
- TF4: round-robin sprite flicker for overflow
- Batman: sprite_link_count per object for overflow prediction
- Gunstar: conditional sprite DMA via dirty flags

---

### 1.3 Scroll / Plane Drawing

**Purpose:** Update VDP nametable planes (scroll layers) without touching the VDP during the game loop. All tile writes are deferred to VBlank via a RAM buffer.

**Architecture: Deferred Plane Buffer**

```
Game Loop                              VBlank
┌──────────────────────┐              ┌─────────────────────────┐
│ Camera scrolls       │              │ VInt_DrawLevel:          │
│ → Draw_TileColumn    │              │   for each buffer entry: │
│   queues tile updates│   deferred   │     set VDP increment    │
│   to Plane_buffer    │  ─────────►  │     set VRAM address     │
│ → Draw_TileRow       │              │     move.l tiles to VDP  │
│   queues tile updates│              │   clear buffer           │
│ → Never writes to VDP│              └─────────────────────────┘
└──────────────────────┘
```

**Buffer structure:** One shared `Plane_Buffer`, 768 words (1536 bytes, `PLANE_BUFFER_SIZE`) in RAM — **not** separate per-plane buffers (see below). Each entry consists of:
- Word 0: VRAM destination address
- Word 1: Tile count - 1. Bit 15 set (`PLANE_ENTRY_COL_FLAG = $8000`) = column mode, clear = row mode.
- Data: row-mode entries drain as **longwords** (`move.l (a0)+,(a6)`, i.e. 2 nametable words packed per unit, autoincrement $02); column-mode entries drain as **words** (`move.w (a0)+,(a6)`, autoincrement $80). This asymmetry (row = longword-packed, column = word-at-a-time) isn't just a documentation nuance — it's why the two modes use different VDP auto-increment registers.
- Terminated by a zero address word.

Plane A and Plane B tile updates are interleaved as different entries in this **same** buffer, distinguished only by their VRAM destination address (`VRAM_PLANE_A` vs `VRAM_PLANE_B_BYTES`), not by separate buffers.

**Why 768 words (vs S.C.E.'s 576):** Worst-case diagonal fast-scroll can reach ~400 words per plane. S.C.E.'s 576-word buffer can overflow in extreme cases (no bounds checking). Our 768 words provides headroom for section transitions and fast diagonal scrolling. (Design rationale carried over from the original S.C.E. comparison; not independently re-derived here.)

**Overflow protection:** Each producer (`Draw_TileColumn`, `Draw_TileRow_FromCache`, `Draw_BG_TileColumn`) checks remaining buffer capacity before writing (`cmpi.w #PLANE_BUFFER_SIZE-2,d2 / bhi .done`). On overflow, the update is **silently dropped for that frame** — there is no re-queue/defer-to-next-frame mechanism, contrary to an earlier draft of this doc. Each producer's own header comment states this plainly: `Out: none (silently drops if buffer full)`. In practice a dropped update means a momentary visual pop at the screen edge rather than memory corruption, but it is not retried automatically.

**Dual plane support — no independent dirty flags, one shared pointer.** `Plane_A_Dirty`/`Plane_B_Dirty` flags do **not** exist in code. `VInt_DrawLevel` gates on a single check: `tst.w Plane_Buffer_Ptr / beq .reset` — one shared buffer, one shared fill pointer, drained as a single pass regardless of which plane(s) contributed entries. This is the largest divergence between the original design and the shipped system: the plan called for two independently-dirty buffers, but the buffer and its dirty/fill state are unified.

**No double-update mechanism.** `Plane_Double_Update_Flag` and camera-delta-driven double-queueing do not exist in code — this was a design idea (queue two sequential updates when the camera moves >16px in one frame) that was never implemented. `Draw_TileColumn`/`Draw_TileRow_FromCache` always queue exactly one update per call.

**How tile data reaches the buffer:** During the game loop, the producer routines detect that the camera has crossed a 16-pixel block boundary and do the addressing, cache lookup, and buffer write directly — there is no separate `Setup_TileColumnDraw`/`Setup_TileRowDraw` split (an earlier draft of this doc invented that split; it doesn't exist). The real routines:
- `Draw_TileColumn` (`engine/level/plane_buffer.emp`) — Plane A, column mode
- `Draw_TileRow_FromCache` — Plane A, row mode
- `Draw_BG_TileColumn` (§4.2) — Plane B (background), always column-mode, fixed 32-word strip from `Sec.sec_bg_layout`/`Act.act_bg_layout`

Each of these does cache lookup + VRAM-address computation + buffer write in one routine:
1. Calculates the VRAM nametable address for the new column/row
2. Looks up pre-computed nametable words from the 2D tile cache (build-time generated, zero runtime tile conversion)
3. Writes the complete VDP nametable words into `Plane_Buffer`
4. Writes a zero terminator after the last entry

**VBlank processing:** `VInt_DrawLevel` runs **before** Critical DMA drain in the VBlank pipeline (not after, as an earlier draft of this doc stated — see §1.4 for the full order) and iterates through the buffer:
1. Reads VRAM address (0 = end, stop)
2. Reads the flags/count word; branches on bit 15 to row or column drain
3. Row entries: sets auto-increment to `$8F02`, drains as longwords, `dbf`-counted
4. Column entries: sets auto-increment to `$8F80`, drains as words, `dbf`-counted
5. Resets VDP auto-increment to `$8F02` after the terminator and clears `Plane_Buffer_Ptr`

Tile writes use direct CPU writes to the VDP data port (not DMA). This is correct — the updates are small sequential writes, where DMA setup overhead would exceed the transfer itself.

**Why deferred, not direct VDP writes:** Writing to the VDP data port during the game loop means the 68K is touching $C00000 during active display, competing with the VDP's rendering engine. The deferred approach eliminates all game-loop VDP access, giving the VDP uncontested bus during active display and consolidating all writes to VBlank where bus arbitration is clean.

**Cross-references:**
- S.C.E. `Draw Level.asm`: Plane_buffer, VInt_DrawLevel, Draw_TileColumn/Row, double-update mechanism
- Batman: VDP-ready nametable format in ROM (validates the pre-computed nametable direction)
- All 5 commercial games + S.C.E.: producer-consumer pattern (main loop writes RAM, VBlank writes VDP)

---

### 1.4 VBlank Structure

**Purpose:** Process all time-critical VDP operations within the vertical blanking interval. Prioritize visual stability over throughput.

**Handler dispatch:** Function pointer `VInt_Ptr` selects the mode-specific handler. `VBlank_Handler` (ROM) checks `VBlank_Ready` to detect lag frames — if the main loop hasn't finished, `VInt_Lag` runs instead of the selected handler.

| Mode | When | What it does | Status |
|------|------|-------------|--------|
| `VInt_Level` | Gameplay | Full pipeline: budget seed + shadow flush + dirty buffers + plane-buffer drain + Critical DMA + VSRAM + Important/Deferrable DMA + controllers | Implemented |
| `VInt_Menu` | Menus/title | DMA queue + sound (no plane buffer, no HUD) | Planned |
| `VInt_Load` | Loading screens | DMA queue + S4LZ processing (no gameplay state) | Planned |
| `VInt_Lag` | Lag frame detected | Shadow flush, dirty-buffer enqueue, Critical DMA, VSRAM write, controllers, frame counter, VBlank_Flag — **omits the plane-buffer drain and the Important/Deferrable drains** (not "Critical DMA only": VSRAM and the shadow flush also run) | Implemented |

Only these two levels exist today — no `VInt_Menu`/`VInt_Load` code exists yet (correctly marked "Planned" above).

**VInt_Level execution order (as implemented, `engine/system/vblank.emp`):**

```
Step  System                              Priority     Notes
──────────────────────────────────────────────────────────────────────────
  1   DMA-window open                     Bus safety   Sound build: brief stopZ80 /
                                                         raise SND_CTRL_DMA_ACTIVE / startZ80
                                                         (Z80 runs free through steps 3-9).
                                                         Sound-OFF build: stopZ80 held across
                                                         the whole window instead.
  2   Seed DMA_Budget_Remaining ← _Default Setup       6144 NTSC / 11648 PAL — the window
                                                         capacity, before any VDP work (§1.1)
  3   Flush_VDP_Shadow                    Critical     Writes only dirty VDP registers
  4   Enqueue_Dirty_Buffers               Critical     Palette/sprite/hscroll static DMA
  5   VInt_DrawLevel (plane buffer drain) Critical     §1.3 — direct VDP writes, not DMA;
                                                         CHARGES budget by Plane_Buffer_Ptr first
  6   Process_DMA_Critical                Critical     Jump-table unrolled, ~514 cycles;
                                                         CHARGES budget by queued bytes, floor 0
  7   Vscroll_Write (VSRAM, direct)       Critical     Must run AFTER HScroll DMA (§4.6)
  8   Process_DMA_Important               Budget-gated Drain_Budgeted_Queue (sees residual)
  9   Process_DMA_Deferrable              Budget-gated Drain_Budgeted_Queue (shared routine)
 10   DMA-window close                    Bus release  Sound build: lower flag; sound-OFF: startZ80
 11   Read_Controllers + press-edge latch I/O          Ctrl_x_Press_Accum → Ctrl_x_Press
                                                         (+ Ctrl_x_Ext_Press_Accum → _Ext_Press)
 12   Frame_Counter increment             Tracking
 13   VBlank_Flag signal                  Sync
```

Note the ordering relative to earlier drafts of this doc: the window budget is **seeded at the top** (step 2, before any VDP work) and then **charged** by the plane-buffer drain (step 5) and Critical DMA (step 6) — it is *not* a flat reset placed after VSRAM. The plane-buffer drain (step 5) sits **before** Critical DMA, not after any DMA drain, and VSRAM (step 7) runs **after** Critical DMA — the code carries an explicit comment citing CODING_CONVENTIONS §3.4 for why HScroll DMA must precede the VSRAM write. This matches §0.10's order for the file.

**Z80 bus ownership is sound-build-conditional, not a blanket "steps 1-9 stopped" rule.** In `SOUND_DRIVER_ENABLED` builds the Z80 is stopped only very briefly at the top (to raise the `SND_CTRL_DMA_ACTIVE` flag) and briefly at the bottom (to lower it) — it runs **free** through the entire DMA/plane-buffer pipeline in between (steps 3-9), so the Z80 sound driver keeps ticking during VBlank. Only the sound-OFF build holds `stopZ80` across the whole window as a simpler, blanket "bus-stopped" model would suggest.

**Step 4 — Enqueue_Dirty_Buffers:** Checks the palette dirty bitmask (4 bits) and the sprite-table dirty flag, enqueueing pre-computed static DMA entries to the Critical queue via `queueStaticDMA`; also enqueues one of the two static HScroll entries (§1.1, §4.6) based on the active parallax config. Each dirty bit/flag is cleared **only** when its enqueue succeeds (§1.1) — a dropped enqueue leaves the bit set for next frame's retry.

**Step 7 — VSRAM:** Direct VDP write, not queued. Vertical scroll data is 4 bytes (FG + BG) written to VSRAM via control port command + data port write, RAM-shadowed at `Vscroll_Factor`. Too small to justify queue overhead. Runs after Critical DMA, not as an early step (see ordering note above).

**Steps 6, 8, 9 — DMA queue drain:** Critical queue always drains fully via jump-table dispatch (zero branches per entry) and charges the budget by its queued bytes. Important and Deferrable queues are budget-gated through the shared `Drain_Budgeted_Queue`: check `DMA_Budget_Remaining` before each entry, terminate on an address compare against the slot's first-free pointer (not a `dbf` counter — see §1.1). The budget was seeded from `DMA_Budget_Default` (6144 NTSC / 11648 PAL) at step 2 and charged down by the plane drain (step 5) and Critical DMA (step 6), so Important/Deferrable see the true residual window (§1.1). On lag frames (`VInt_Lag`), only Critical drains — Important and Deferrable entries persist (compacted) in the queue for the next frame.

**Step 11 — controllers:** Also latches the previous frame's press-edge accumulator (`Ctrl_1_Press_Accum` → `Ctrl_1_Press`) — an interesting side effect of this being VBlank-driven: press-edge state survives a lag frame into the next tick rather than being lost.

**Lag frame handling:** `VBlank_Handler` checks `VBlank_Ready` (set by `VSync_Wait` in the main loop). If clear, `VInt_Lag` runs instead of the handler selected by `VInt_Ptr`. On a lag frame:
- Shadow flush, dirty-buffer enqueue, and Critical DMA all still run (palette, sprites — player never sees visual glitches)
- VSRAM write still runs
- The plane-buffer drain is **deliberately skipped** — on a lag frame the main loop is still mid-fill and `Plane_Buffer` may be torn (see the `VSync_Wait` hazard note below)
- Important/Deferrable entries remain in queue (drained next normal frame)
- Controllers still read, frame counter still advances
- `Lag_Frame_Count` increments for debugging (debug builds only, `ifdef __DEBUG__`)
- `VBlank_Ready` is cleared by `VBlank_Handler` after dispatch, on either path

**`VSync_Wait` torn-drain hazard (fixed, b96c861):** `VSync_Wait`'s clear-flag/set-`VBlank_Ready` pair is IRQ-masked (`engine/system/vblank.emp`). Without the mask, an IRQ6 landing between the flag-clear and the `Ready`-set could run `VInt_Lag` (which itself sets `VBlank_Flag`) while leaving `Ready=1` armed for the *next* VBlank — causing that next VBlank to fully dispatch `VInt_Level` and drain a `Plane_Buffer` still mid-fill by the main loop. This is a genuine Genesis-timing gotcha specific to a lag-detection scheme built on a main-loop-set-flag; the fix masks interrupts across the flag/Ready update pair.

**Why this order:** Visual stability first (shadow flush, dirty buffers, plane drain, Critical DMA, VSRAM all ensure correct display), then throughput (Important/Deferrable DMA for art streaming), then housekeeping (controllers, frame counter, flag). Each step is independently skippable without corrupting state — this is what lets `VInt_Lag` cleanly omit steps 5, 8, and 9 (the plane drain and the Important/Deferrable drains).

**Cross-references:**
- S.C.E. `Interrupt Handler.asm`: VInt function pointer dispatch, VInt_Lag, Do_ControllerPal ordering
- Batman: early DMA burst before other VBlank processing
- Gunstar: conditional VBlank steps based on dirty flags

---

### 1.5 Background Work During Idle Time

**See §9.7 (Idle-Time Deferred Work — Pre-Chunked Pages + Supervisor Bookmark).** Deferred CPU work (mid-game art-page decode, oversized decompression) runs in the `VSync_Wait` idle spin, pre-chunked at build time into small units and sliced across frames by a VBlank supervisor bookmark that banks a resumable decoder's registers when VBlank fires mid-decode and resumes it next frame. See §9.7 for the full design as shipped.

---

### 1.6 DPLC Lookahead — Predictive Art Loading

**Status: design, not implemented (2026-07-17).** Verified against the actual DPLC and animation code (`engine/objects/dplc.emp`, `engine/objects/animate.emp`) — no lookahead/peek mechanism exists. `AnimateSprite` decrements `SST_anim_timer` and, on expiry, immediately advances `SST_anim_frame`/`SST_mapping_frame` in the same pass — there is no "one frame before the animation changes" pre-check of the next script byte. `Perform_DPLC` / `Perform_DPLC_Deferrable` are purely reactive: they compare `SST_mapping_frame` against `SST_prev_frame` and, only when they already differ (i.e. the frame has already changed), resolve and enqueue the DPLC entries for the *current* frame via `QueueDMA_Important`/`QueueDMA_Deferrable`. `SST_prev_frame` is committed only after every entry for the frame enqueues successfully (dropped/queue-full entries leave `prev_frame` stale so the load retries next frame) — a real, useful design detail, but still strictly reactive, not predictive. `anim_timer`/DUR_DYNAMIC exist as animation-duration fields, not as a lookahead trigger.

The design below is preserved as an unimplemented proposal:

**Purpose (proposed):** Eliminate single-frame art latency during character animation transitions by pre-loading the next animation frame's art before the animation advances.

**Mechanism (proposed):** During `AnimateSprite`, when `anim_timer <= 1` (one frame before the animation changes), peek at the next frame in the animation script. If it requires different DPLC tiles than the current frame, queue the DPLC load as an Important-priority DMA entry. When the animation actually advances next frame, the art is already in VRAM.

**Trigger guard (proposed):** Only activates when `anim_timer <= 1`, not every frame. This prevents doubling DPLC traffic during steady-state animation. The pre-load fires once per animation transition, not once per frame.

**Waste case (proposed):** Player changes state (e.g., jumps while running) and the pre-loaded art is never used. Cost: one wasted Important-priority DMA entry that gets budget-gated. Minimal impact.

**No Genesis game does predictive DPLC loading.** All load reactively: frame changes → trigger DPLC → art appears next frame. With lookahead, art would appear on the same frame as the animation change — this remains the motivating idea for a future pass, but the shipped engine loads reactively like everything else, one frame behind the animation change, exactly as commercial games do.

---

### 1.7 VDP Register & VSRAM Management

**VDP register shadow:** Full 19-register shadow table, re-blitted unconditionally every VBlank (§0.4, `VDP_Shadow` struct, `engine/structs.emp`). Game code is *supposed* to never write VDP registers directly — persistent changes go through `Set_VDP_Reg` (`engine/system/vdp_init.emp`), which updates the RAM shadow only. `Flush_VDP_Shadow` in VBlank writes all 19 registers in ascending order every frame, no dirty check — the same shape Batman & Robin's `sub_00AE2C` and The Chaos Layer's bulk re-push use (verified 2026-08-14: `The Adventures of Batman and Robin/disasm/code/engine/main_loop.asm:5400-5409` — 19 unconditional register writes from a byte table, no readback; see the §0.4 provenance note). Aeon adopted the same shape 2026-08-14, for composability rather than performance — see §0.4 and `docs/superpowers/plans/2026-08-14-blanket-register-restore.md`.

**Known exception (2026-07-16 review):** OJZ test/game-shell code has a direct `$8B` VDP write for HScroll mode that bypasses the shadow (`Set_VDP_Reg`), violating the invariant above. This is tracked as a bug, not a supported pattern — the engine-level convention still holds; the violation is game-side content, not engine code.

**Key register change points:**
- `vdp_mode2` (reg $01): Display enable/disable — toggled during loading screens and display-disable burst DMA (§7.2)
- `vdp_hint_rate` (reg $0A): H-Int line counter — set per-section for water line, raster effects
- `vdp_mode3` (reg $0B): Scroll mode — changed per-section for different parallax configurations
- `vdp_mode4` (reg $0C): S/H mode — toggled per-section (§7.3)
- `vdp_window_h`/`vdp_window_v` (regs $11/$12): Window plane — toggled for HUD overlay, letterboxing

**VSRAM:** Direct write during VBlank — actual position is step 6 of the real VInt_Level order (§1.4), after Critical DMA has drained, not an early step. RAM shadow at `Vscroll_Factor` (foreground + background, 4 bytes total). If per-column V-scroll is needed for parallax, extend to a RAM buffer (40 columns × 4 bytes = 160 bytes) and write via a direct loop during VBlank (like hscroll, but smaller).

---

### 1.8 H-Blank Dispatch Mechanism

**Purpose:** Execute per-scanline raster effects via a section-installable interrupt handler. The dispatch mechanism is simple — the raster command table system (§7.2) defines what actually runs.

**RAM jmp-slot trampoline (§0.10) — mechanism and walker both SHIPPED.** The HBlank vector in the exception table points *directly* at `HBlank_Vector_Slot` (`engine/system/hblank.emp`), a 6-byte executable RAM slot. There is no ROM dispatch stub and no pointer read: the slot holds an idle `rte` ($4E73) when nothing is armed, or `jmp handler.l` ($4EF9 + 4-byte target) once `HBlank_Install` arms a handler — the interrupt reaches the handler through a single `jmp`, and the handler owns its own save/restore and terminates with `rte`. `HBlank_Install(a0=handler, d0=line counter)` / `HBlank_Uninstall` are shipped and exported, and both program IE1 (reg $00 bit 4) and the HInt counter (reg $0A) through the VDP shadow. The walker SHIPPED with effects P1/P2 (corrected 2026-08-14; this sentence previously read "zero handlers exist today"). `Raster_VBlank` (`engine/effects/raster.emp`) calls `HBlank_Install` every frame it has a program armed, pointing the slot at `Raster_HInt` — which walks the compiled raster program, fires per-line CRAM/VSRAM/register writes, and re-arms reg $0A. The slot sits at the idle `rte` only when no program is installed.

**Idle HBlank cost.** With no handler armed the slot decodes to a bare `rte` — a single ~20-cycle return, with no register save/restore, no pointer load, and no indirect `jsr`. (The RAM-trampoline design that earlier drafts flagged as "not yet applied" is now the shipped mechanism; the old ~180-cycle pointer-dispatch stub it replaced is gone.)

**H-Int counter:** Set via VDP shadow table (§0.4, §1.7) to control which scanline triggers the interrupt. For single-event effects (water line): set to the trigger scanline. For continuous effects (deformation, gradient): set to 0 (fire every scanline) or the effect start line. The raster command table handles multiple effects at different scanlines automatically.

**Production-proven:** 4 out of 5 analyzed commercial games (Vectorman, TF4, Gunstar Heroes, Alien Soldier) RAM-patch HBlank. Vectorman ($FFFF9D2E), Batman ($FFFFE560), and Treasure ($FFFFEE00) all use pointer dispatch.

---

### 1.9 Cascade Effects

The systems in this cluster create a chain of enablements:

```
Plane Buffer (no game-loop VDP access)
  → VDP has uncontested bus during active display
    → Cleaner rendering, no bus contention artifacts
  → More VBlank time available (no game-loop VDP cleanup)
    → More aggressive art streaming via Deferrable DMA
      → Smoother section transitions
        → Smaller sections viable (faster art swap)

Priority DMA + Adaptive Budget + Lag Recovery
  → Visual stability under heavy load
    → More objects/effects affordable per scene
      → Richer gameplay without frame drops
  → Self-tuning throughput
    → No manual per-zone DMA budget tuning needed

Sprite Dirty Flag + Static DMA + Variable Hscroll
  → 1-3 fewer DMA entries on calm frames
    → More budget available for art streaming
      → Faster S4LZ decompression throughput

Idle-time work (§9.7) + DPLC Lookahead
  → Free S4LZ decompression in leftover CPU time
    → Art pre-loaded before section boundary reached
      → Zero visible loading artifacts
  → Character art pre-loaded before animation changes
    → Zero-frame animation transition latency

Raster Command Table (§7.2) + Section Streaming
  → Per-section stackable raster effects via pre-built command tables
    → Visual variety between sections, multiple effects per frame
```

---

## 2. Art & Compression Pipeline

The art pipeline handles getting graphical data from ROM into VRAM — compressed art decompression, VRAM address assignment, section-aware streaming, and background plane support. Every visual element in the game flows through this pipeline.

### 2.1 Compression & Art Formats: Two-Tier (S4LZ v3 + ZX0) + Uncompressed/DPLC

**Purpose:** Formats chosen by DECODE-SPEED TIER, with all ratios MEASURED on the real
(post-dedup) corpus — the original projections assumed pre-dedup redundancy and did not
survive contact with shipped data (see `docs/research/compression-audit-2026-06-11.md`,
the audit that produced this design, and `compression-audit-landscape.md` for the
external survey). All compressed art carries a 4-byte wrapper: [u16 BE uncompressed
size][u8 flags][u8 version: 1 = S4LZ v3, 2 = ZX0]; the manifest's `pm_form` drives the
runtime dispatch (the blocking `Art_Decompress` version dispatcher is DEBUG selftest
equipment now — F-6); the wrapper version byte remains the baked on-disk truth,
DEBUG-asserted against the manifest at dispatch.

| Tier | Format | Measured speed | Measured ratio | Use Case |
|------|--------|-------|-------|----------|
| Runtime hot path | **S4LZ v3 + per-section block dictionary** | ~510-640 KB/s | blocks 0.49 (streams), ~0.29 effective with dict | 16×16 block decompression, 6/frame budget |
| Load-time bulk | **ZX0** (salvador / unzx0_68000) | ~76 KB/s (measured: 5 frames / 6.3 KB) | tile art 0.605 | Act FG art pool pages at init; any init-time bulk |
| Sprite art | **Uncompressed + DPLC** | Bus speed (DMA) | 1.0 | Per-frame character/object art via DMA from ROM |
| Tilemaps | **Raw** | instant | 1.0 | Menu/level select nametables — direct DMA to VDP |

**S4LZ v3 (runtime word-aligned LZ):**
- **Header:** the 4-byte wrapper above (flags bit 0 = tile-delta XOR, currently unused — it MEASURED 9 points WORSE on post-dedup tile data and was dropped from the pipeline)
- **Token word:** [token.b][offmark.b]. Token nibbles: hi = literal words, lo = match words; $00 = EOS (full word consumed). offmark = match_offset/2 for even offsets 2-510 (the byte that v1 wasted as alignment padding); offmark 0 = long form, u16 BE offset word follows the literals. Nibble 15 → u16 count extension (after token word for literals; after the offset position for matches)
- All copies word-aligned `move.w (a0)+,(a1)+`; matches may overlap (offset ≥ 2), copies ascend
- **Offsets ≤ 32766** (decoder uses `suba.w`; encoder enforces). Minimum match 2 words
- **Per-section block dictionary:** the compressor pre-seeds the LZ window with K raw blocks from the same section (K = 0..3 swept per section at build, min total size; OJZ optimum K=1). Dict blocks are stored RAW in the blob and serve double duty as their own storage (index entry bit 31 = raw-direct copy). `S4LZ_DecompressDict` rebases below-buffer match sources into the ROM dict with one compare-branch per match (~16 cycles, both entries pay it; the plain entry's branch never fires on valid streams). Measured: per-block compression recovers whole-stream-class ratios while keeping random access (0.524 → 0.486 streams; ~0.29 effective with dict accounting)
- Compressor: `tools/s4lz.py` — optimal parse (forward DP, dual match candidates per position: best-overall + best-short-offset). The parse is provably optimal for the cost model; known gap: literal-extension words are uncharged (measured < 0.5% ceiling, DEFERRED_WORK)
- Decompressor: `engine/compression/s4lz.emp`, ~300 B, measured ~510-640 KB/s realistic mix. Micro-optimizations (move.l copy tables, extended-loop unroll, 256-entry token jump table → ~770+ KB/s) are documented in the audit and DEFERRED — current block budgets fit (6 blocks/frame ≈ half a frame; vertical scroll protocol unchanged at +4/512px with dicts on)

**ZX0 (load-time bulk):**
- Einar Saukas' ZX0 v2 format; compressed by vendored salvador (`tools/salvador/`, zlib/CC0/MIT licenses), decoded by the vendored unzx0_68000 derivatives (streaming: `engine/compression/zx0_resume.emp`; blocking twin with its DEBUG selftest consumer: `engine/debug/compression_selftest.emp` — both zlib-licensed, attribution in each file)
- Measured 0.605 on section tile art vs 0.85 for the best word-aligned S4LZ — bitstream rep-offset + elias-gamma + byte-granular matching, ~zlib-class ratio without entropy tables
- **~76 KB/s (blocking ZX0) — init/preload tier.** The blocking `ZX0_Decompress` runs at level init and now survives only as the DEBUG self-test oracle. Mid-gameplay art pages instead ride the resumable `ZX0R_Decompress` sliced by the §9.7 pages+bookmark idle-time path — never a synchronous blocking decode. Small (64-tile) pages, demand/prefetch FIFO, VRAM residency cache
- Clobbers d0-d1/a0-a2 only (narrower than S4LZ)

**Pipeline guarantees:**
- **Golden self-test:** every DEBUG boot decompresses build-time vectors (all v3 token paths, dict rebase, ZX0 via dispatch) on the 68000 and verifies checksum + byte-exact payload against the encoder's output — the asm decoders are continuously proven against the Python/salvador encoders
- **Content dedup:** identical section blobs (tiles AND blocks) collapse to one ROM copy via generated `equ` aliases (−37.8 KB on OJZ today)
- **Build guards:** blob size vs wrapper field (64 KB) and vs `Decomp_Buffer` capacity (9,600 B) fail the build, not the console
- See `docs/research/lz-compression-survey.md` for the original (partially superseded) LZ survey and the audit docs for what replaced it and why

**Uncompressed sprite art + DPLC/DMA (per-frame character/object art):**

UFTC was originally planned for random-access sprite decompression, but measured only 0.82-0.86 ratio on real Sonic sprite art (not the projected ~0.50). Every commercial Genesis game stores sprite art uncompressed and uses DMA from ROM. We follow suit with several improvements. See `docs/research/tile-format-survey.md` for full measurements and `docs/research/dplc-improvements.md` for the improvement design.

- Sprite art stored as uncompressed tiles in ROM (`ArtUnc_*` labels)
- **DPLC tables** map each animation frame to tile ranges in the art data (S2/S3K format: word entry count + word entries with 4-bit tile_count/12-bit tile_start)
- On animation frame change, `Perform_DPLC` queues DMA transfers from ROM directly to VRAM — zero CPU decompression cost
- Per-object `ros_prev_frame` field prevents redundant DMA when frame unchanged (S.C.E. pattern)
- **Build-time contiguous art layout:** Build tool rearranges tiles so each animation frame's tiles are contiguous in ROM, guaranteeing 1 DMA entry per frame change (12% ROM overhead from tile duplication — acceptable in 4MB ROM)
- **Build-time entry merging:** Merge adjacent DPLC entries at build time, reducing average DMA entries from 3.1 to 1.2 per frame change for pre-existing DPLC tables
- **Priority integration:** Character DPLCs → Important priority (guaranteed delivery). Object DPLCs → Deferrable priority (budget-gated, can slip one frame). Prevents VBlank overflow when many objects change frame simultaneously
- **DPLC Lookahead (§1.6):** When `anim_timer <= 1`, pre-load next frame's art as Important-priority DMA. Zero-latency animation transitions. No Genesis game does this
- **128KB DMA boundary safety:** `QueueDMATransfer` splits any transfer crossing a 128KB ROM boundary ($20000, $40000, etc.) into two entries. DMA source address wraps within 128KB banks on the Genesis — without splitting, art loads from wrong ROM addresses

**DMA bandwidth analysis (from `docs/research/dplc-improvements.md`):**
- Average tiles per frame change: 17.1 (547 bytes)
- VBlank DMA budget: ~7,000 bytes (NTSC)
- Single frame change = 7.8% of budget
- Worst case (3 characters + 8 objects simultaneous change): 4,202 bytes (60%)
- Amortized (frame changes every ~7 frames on average): 1.1% of budget
- **DPLC is not a DMA bandwidth bottleneck**

**ROM budget for uncompressed sprites (~463 KB):**
- Character sprites: ~308 KB (Sonic, Tails, Knuckles + shields/effects)
- Object/enemy sprites: ~155 KB
- Total: 11.3% of 4 MB ROM — fits comfortably with 2,783 KB free

**Raw tilemaps (menu/level select):**
- Menu tilemaps are small and infrequent — compression overhead isn't justified
- Stored as uncompressed VDP nametable data. Load via direct DMA from ROM — zero CPU cost, instant
- Even a dozen full-screen tilemaps at ~2-5 KB each is under 0.5% of a 4 MB cart

**Why S4LZ over existing LZ formats:**
- **vs KosPM:** S4LZ projects 700-1,100 KB/s vs KosPM's 190-310 KB/s. 3-4x faster. Comparable or better compression ratio with tile-delta preprocessing
- **vs Comper:** S4LZ is faster (word-aligned with unrolled tables vs Comper's simpler loop) AND compresses better (64KB dictionary + tile-delta vs Comper's 512-byte window at ~0.65-0.75 ratio)
- **vs LZ4W (SGDK):** S4LZ improves on LZ4W's design — big-endian offsets (14 cycles/match saved vs LZ4's little-endian), much larger dictionary (64KB vs 512 bytes), tile-delta preprocessing for better ratio
- **vs Nemesis:** S4LZ is ~8-14x faster than Nemesis for sequential loads, with comparable or better ratio via tile-delta
- **vs Raw/uncompressed (Batman):** Sonic needs 10+ zones — uncompressed level art would exceed 4MB ROM. The compressed paged act art pool (ZX0 at load time, S4LZ for the runtime block stream) keeps ROM manageable while decompressing fast

**Why uncompressed + DPLC over UFTC:**
- Zero CPU overhead for per-frame sprite loading (DMA runs on VDP clock)
- UFTC achieves only 0.82-0.86 ratio on real Sonic sprite art — saves ~55 KB (1.3% of ROM) at cost of added complexity and per-frame CPU work
- Every commercial Genesis game (and all 7 reference disassemblies) stores sprite art uncompressed
- DPLC tables from sonic_hack can be migrated directly
- Simpler codebase (no UFTC encoder/decompressor/format handling)

**Cross-references:** See `docs/research/lz-compression-survey.md` for LZ format survey. See `docs/research/tile-format-survey.md` for UFTC evaluation. See `docs/research/dplc-improvements.md` for DPLC improvement design.

### 2.2 VRAM Tile Assignment — Static, Build-Time

**Purpose:** Assign VRAM tile addresses with no runtime bookkeeping. Tile addresses are fixed at build time, so the engine never tracks "what's in VRAM" at runtime.

**How it works:**
- **THE PLACEMENT AUTHORITY IS THE VRAM REGISTRY (2026-08-11, "the VRAM
  linker" T0 — spec `docs/superpowers/specs/2026-08-11-vram-linker-design.md`):**
  every region is DECLARED in `games/<game>/vram.toml` (name, owner, size,
  lifetime, typed engine-constant authority) and `tools/gen_vram_map.py`
  verifies full coverage of all 2048 tiles / non-overlap / quantum fit, then
  emits the game's `VRAM_*` constants (a generated marker block in
  `config/constants.emp`), the Python mirror the build tools import
  (`tools/vram_map.py`), and the LIVING MAP —
  `docs/generated/vram-map-<game>.md`, which supersedes any hand-drawn layout
  table in this document as the per-game truth. Engine-owned bases (planes,
  SAT, HScroll, the pool ceiling) keep their authority in
  `engine/system/constants.emp`; the generated block cross-checks them by
  name, so engine/contract drift fails the build. T1 (planned) moves solving
  into the sigil chainer; T2 adds state overlays, per-act solving, and
  register emission.
- **Act FG art** occupies a single globally-deduped, spatially-ordered, paged pool run as a VRAM residency cache (§9.7): bulk-loaded at level init (§2.3, §2.5), pages living in allocated frames, degenerating to fully resident when the pool fits the frame budget. Section nametables reference per-section LOCAL indices translated to global at block decode (§2.3) — there is no per-section VRAM allocation and no per-section art swap. The pool's ceiling is 896 tiles (14 pages) since the dust carve; the surrendered page holds the dust windows (896/912) + 36 spare.
- **Object/permanent art** (HUD, rings, monitors, characters) uses VRAM addresses baked into archetype templates via the `vram_art()` macro at build time — the addresses now COME FROM the registry rather than hand-picked literals. The address is a static immediate; objects spawn with it directly (§3.9). No allocation step runs when an object spawns.

Because every object/permanent tile address is decided at build time and act FG art rides the §9.7 residency cache, there is no fragmentation, no compaction, and no allocator beyond the cache's own frame/refcount machinery. The act pool is capped by ROM budget, not VRAM: `tools/art_rom_report.py` gates the per-act ROM footprint at build time, and the cache degenerates to fully resident for acts whose pool fits the frame budget.

**Future enhancement (DEFERRED_WORK):** A dynamic per-object VRAM allocator with refcount-based caching and lazy reclaim — for on-demand boss/effect art. This would add `AllocVRAM`/`FreeVRAM`-style lifecycle on top of the same residency cache. It is not part of the shipped engine; today's model is static assignment plus the streamed act-pool residency cache (§9.7). The "levels whose art exceeds the resident pool" case is already handled — that is exactly what the residency cache streams (level art is capped by ROM, not VRAM); this future item is only about per-object/effect art on top.

**Cross-references:** §2.1 (S4LZ + ZX0 + uncompressed/DPLC formats), §2.3 (VRAM layout), §2.5 (art loading flow), §3.9 (static object art).

### 2.3 VRAM Layout — Unified Pool + 64×64 Scroll Planes

**THE PER-GAME OCCUPANCY TRUTH IS GENERATED, NOT THIS DIAGRAM:** see
`docs/generated/vram-map-sonic4.md` / `vram-map-demo.md`, emitted from each
game's `vram.toml` on every regeneration (§2.2). The diagram below keeps the
DESIGN — the unified-pool shape and the plane/table placement rationale — and
its numbers are correct for the layout's original 960-tile pool; the current
pool ceiling is 896 with the dust windows in the surrendered page.

**Purpose:** Maximize available art tiles through a single unified pool, with 64×64 scroll planes for vertical buffering and visual effects. Character DPLC art lives in the pool (tile `$3C0`, DMA'd per frame); the sprite attr + HScroll tables sit in their own region (`$5C0-$5FF`, below Plane A) — so both scroll planes keep all 64 rows free for vertical streaming (no off-screen-row embedding, no "Region 2").

```
VRAM (64KB = 2048 tiles)
┌───────────────┬─────────────────────────────────────────────────────┐
│ $000-$5BF     │ UNIFIED ART POOL (1,472 tiles)                      │
│ (1472 tiles)  │   Act FG tiles — paged residency cache (§9.7)       │
│               │   Object tiles — static vram_art() addresses (2.2)  │
│               │   Permanent tiles — HUD, rings, monitors            │
│               │   Character DPLC art — DMA'd per frame (tile $3C0)   │
├───────────────┼─────────────────────────────────────────────────────┤
│ $5C0-$5FF     │ SPRITE ATTR TABLE ($B800) + HSCROLL ($BC00)         │
│ (64 tiles)    │   Relocated below Plane A (was $D800/$DC00, inside   │
│               │   Plane A) to free its full 64 rows for streaming   │
├───────────────┼─────────────────────────────────────────────────────┤
│ $600-$6FF     │ PLANE A NAMETABLE (256 tiles = 8KB, 64×64)          │
│ (256 tiles)   │   All 64 rows are normal nametable — the vertical    │
│               │   tile-cache fills every row (rows 48-63 included)   │
├───────────────┼─────────────────────────────────────────────────────┤
│ $700-$7FF     │ PLANE B NAMETABLE (256 tiles = 8KB, 64×64)          │
│ (256 tiles)   │   All 64 rows — BG parallax (no "Region 2")          │
└───────────────┴─────────────────────────────────────────────────────┘

VDP byte addresses: $000×32=$0000 ... $600×32=$C000 ... $700×32=$E000
VDP register $90 = $11 (64×64 scroll planes)
Plane A nametable base: VDP reg $02 → $C000
Plane B nametable base: VDP reg $04 → $E000
```

**Why unified pool:** Fragmented VRAM layouts (separate regions for level art, permanent objects, zone pools) waste tiles at region boundaries — a region with 5 free tiles and a neighbor with 0 free tiles can't share. The unified pool makes all 1,472 tiles available to the build tool. Act FG art streams through the §9.7 residency cache, so pool size is capped by ROM budget (`tools/art_rom_report.py`), not by the FG VRAM region; permanent allocations are still asserted to fit at build time.

**Why 64×64 scroll planes ($9011):**

Our 4×3 section grid has true vertical transitions — vertical scrolling is a first-class concern, not an occasional exception.

| Property | 64×32 ($9001) | 64×64 ($9011) |
|---|---|---|
| Vertical buffer | ~32px beyond 224px display | ~288px beyond display |
| VSRAM deformation range | ±32px per column | ±288px per column |
| Nametable size per plane | 128 tiles (4KB) | 256 tiles (8KB) |
| Visual effects enabled | Basic horizontal | Perspective floors, dramatic water reflections, earthquake shake, vertical parallax |

With 64×32, fast vertical scrolling constantly hammers nametable updates with only 4 rows of buffer. With 64×64, 36 rows of buffer absorbs even the fastest vertical movement. The extended VSRAM range enables per-column vertical deformation effects that make levels look dramatically more alive.

**Validated by:** Vectorman (BlueSky) commercially ships with dynamic 64×32 ↔ 64×64 switching — the only known commercial Genesis game to use 64×64 scroll planes. Batman & Robin and S3K use 64×32 because their levels are primarily horizontal — our vertical section grid justifies the larger planes.

**Why character art + VDP tables are NOT embedded in off-screen rows (superseded design):** an earlier plan parked the SAT/HScroll tables and character art in Plane A's "off-screen" nametable rows — a trick that only holds when scrolling is horizontal-only. Vertical streaming makes *every* row reachable on-screen (the camera spans the full act height), so there are no permanently-off-screen rows to hide data in. Instead: the sprite attr table ($B800) + HScroll table ($BC00) were relocated to their own region below Plane A (tiles $5C0-$5FF, was $D800/$DC00 *inside* Plane A's $C000-$DFFF), and character DPLC art lives in the unified pool (tile $3C0). Both planes keep all 64 rows free for streaming.

**Character sprite budget:** Up to 128 tiles for the current animation frame, DMA'd every frame into the pool's character DPLC window (tile $3C0). If strictly one character at a time (no AI follower), this can shrink to 64 tiles.

**Build-time tile deduplication + spatial ordering + paging:** The build tool deduplicates tiles globally across all sections of the act using canonical forms (so a tile and its H/V flips collapse to one entry), then orders the unique tiles spatially — by first occurrence in grid-traversal order, so tiles that are spatially near each other land at nearby pool indices for cache locality (`tools/tile_dedupe.py`: `dedupe_tiles` + `order_pool_spatially`). The deduped, spatially-ordered pool is split into fixed-size pages (`ART_POOL_PAGE_TILES` = 64 tiles each, `split_pool_into_pages`), and each tile receives a permanent global pool index. Section nametables reference **per-section LOCAL indices** (bits 0-10, ≤2047 distinct tiles per section) translated to global via a per-section local→global table at block-decode time (art-streaming Phase 2 cutover, 2026-08-08) — the extra indirection is what lets a page live in any VRAM frame rather than at a fixed slot, which is the precondition for the residency cache (§9.7). Palette/priority/flip bits are untouched by the translation.

Result: section transitions perform no per-section art swap — a global index names one deduped tile for the whole act, and the §9.7 residency cache keeps referenced pages resident (fully resident when the pool fits the frame budget; streamed on demand + prefetch past it). There is no graph coloring and no per-section index reuse: every unique tile in the act has one permanent global index, and the cache maps that index's page to a VRAM frame at runtime.

**Section VRAM lifecycle:**
1. **Build time:** Global deduplication (canonical form) + spatial ordering assign each unique tile a permanent global pool index; the pool is split into 64-tile pages with a stride-8 manifest v2 entry each.
2. **Level load:** `Level_LoadArt` bulk-loads every page through the page-in path (ZX0R resumable decode via the 2048 B `Art_Staging_Buffer`, or raw direct from ROM) into cache-allocated frames; permanent tiles (HUD, rings) load alongside.
3. **Resident model (degenerate case):** When the deduped pool fits the frame budget, every page stays resident after the bulk load — continuous scrolling and teleports never swap section art. The footprint fits because global deduplication ensures each unique tile appears once in the pool regardless of how many sections use it.
4. **>frame-budget acts:** the §9.7 residency cache streams pages on demand + prefetch at the leading edge (idle-time decode, Important-queue landings), evicting the oldest-released unpinned pages (stamp eviction) as the camera moves — capped by ROM budget, not VRAM. Short backtracks reuse still-resident pages; no slots or teleports are reintroduced.

**Auto-calculated addresses:** Permanent-category objects (HUD, rings, monitors, springs, etc.) are defined sequentially in `VRAM_Layout.asm` with tile counts. The assembler computes addresses automatically — adding/removing an object shifts everything after it. Compile-time overflow check ensures permanent allocations don't exceed the pool budget.

**Cross-references:** §2.2 (static VRAM assignment), §2.5 (art loading flow). Vectorman: 64×64 plane validation. Batman: raw nametable data in ROM.

### 2.4 Per-Section Background Support

**Purpose:** Enable per-section visual variety on Plane B (background) independently from Plane A (foreground).

The Genesis VDP has completely separate planes — Plane A and Plane B have independent nametables, scroll positions, and can reference different tiles. This means per-section BG data is architecturally straightforward.

**Three tiers:**

| Tier | Layout | Art | VRAM Cost | Use Case |
|------|--------|-----|-----------|----------|
| 1. Zone-wide shared | One BG layout for zone | Shared BG tile region (zone-wide, fixed) | 256 slots reserved | Simple parallax, most sections |
| 2. Per-section layout | Different BG arrangement | Shared BG tile region (zone-wide, fixed) | 256 slots reserved | Visual variety with existing BG art |
| 3. Per-section art+layout | Different BG tiles+layout | Section's A.3 art group | Pool tiles | Unique BG (mountain skyline, etc.) |

**Shared BG tile region (T1/T2):** A fixed VRAM range — base slot 1024, byte address $8000 (`BG_TILE_BASE_VRAM`) — is reserved for BG-only tile art. The relocated SAT at $B800 is the hard ceiling, so usable BG space is $8000-$B7FF = **448 tiles** (14 KB), `BG_TILE_CAPACITY` in constants.asm; OJZ Act 1 uses ~340. The engine doesn't read this constant; only the build tools gate on it (`tools/ojz_strip_gen.py`, `tools/inject_editor_bg.py`). Loaded **once** at level init and **never** overwritten by section transitions. BG tiles must remain at consistent VRAM slots across all section transitions for the BG nametable's tile-index references to stay valid — the same residency guarantee the FG act pool relies on.

T1 ships with the shared region populated from `act_bg_tiles` (zone-wide pointer). T2 reuses the same region — only the per-section nametable changes. T3 folds its unique BG tile art into the section's contribution to the global act art pool, so each T3 section gets unique BG tile art at the cost of additional pool budget pressure.

**Section entry integration (post-§2 A.5):**
- `act_bg_layout` (Act struct, longword at $16) — zone-wide BG nametable pointer; drawn once at level load by `BG_Init`.
- `act_bg_tiles` (Act struct, longword at $1A) — zone-wide BG tile blob pointer; loaded once at level load into the shared BG region at `BG_TILE_BASE_VRAM` ($8000) by `BG_Init`.
- `sec_bg_layout` (Sec struct, longword at $1C) — per-section BG nametable pointer (NULL = use Act default). Drawn once by `Section_RedrawPlanes` at level init. Continuous scrolling never rebases or redraws Plane B during play (§4.1/§4.4); a per-section BG *swap* on a boundary crossing needs a future deferred mechanism (stream the new 64×32 BG nametable into the wrapping plane at the leading edge) if a zone ever authors differing per-section BG layouts.

**Storage shape:** Each layout is a **raw 64×64 nametable** (8192 bytes uncompressed), stored **column-major** (`blob[col*128 + row*2]` — each column's 64 rows contiguous, column stride 128 bytes; `tools/inject_editor_bg.py` transposes the row-major editor layout into this order). Column-major lets every consumer gather a plane column with sequential `move.l` reads and blit it with autoinc $80 (one `move.l` = two vertically-adjacent cells). All 64 rows are live in every writer — `BG_Init`, `Section_RedrawPlanes`, and `Draw_BG_TileColumn` all cover the full plane (the maintainers' old 32-row limit was closed by NEW-5, 2026-08-05; shipped OJZ art occupies rows 32-63 and the full-plane vscroll wrap exposes them on screen). BG tile blob is raw uncompressed tiles (32 B per tile, ≤ 448 tiles per zone) — `BG_Init` copies it with a Tier-1 `move.l` loop (4-byte-granular by contract). No `sec_bg_plc_off` field — T3 BG tile art folds into the section's contribution to the global act art pool. T3 BG tiles are therefore part of the same paged pool that `Level_LoadArt` loads once at level init — there is no separate per-section BG load path, and the whole pool (FG + any T3 BG tiles) is already resident before play begins.

**Tier detection (build-time):** `sec_bg_layout=NULL` → T1; `sec_bg_layout≠NULL` and BG tile refs ⊆ shared BG region → T2; `sec_bg_layout≠NULL` with section-specific BG-only tiles → T3.

**Engine cost:** T1 = one 4 KB nametable blit + one BG-tile-blob DMA at level init, zero per-frame. T2 = same load cost; a differing per-section BG layout would cost one 4 KB nametable blit when the camera crosses into that section (~0.6 ms blocking via VDP DATA port) — the deferred per-section BG swap above. T3 = nametable blit at init; its BG tiles ride the resident act art pool, so there is no per-section tile load. Deferrable-DMA optimisation tracked in DEFERRED_WORK.

**Pool integration:** T3 BG tiles are part of the section's contribution to the global act art pool, so the build tool dedupes and pages them identically to FG tiles, and they ride the §9.7 residency cache with the FG pool — the combined pool is capped by ROM budget (`tools/art_rom_report.py`), not the FG VRAM region. The shared BG tile region (T1/T2) is a single permanent allocation at $8000 — loaded once, never freed.

**VRAM map summary (post-§2 A.5):**
```
$0000-$B7FF  UNIFIED ART POOL (tiles $000-$5BF, 1,472 tiles). Globally-deduped,
             paged act pool run as the §9.7 residency cache — fully resident when
             the pool fits the frame budget, streamed on demand past it; continuous
             scroll performs no per-section art swap (§2.3).
               · FG act tile art (paged residency cache, frame-allocated)
               · shared BG tile region (base $8000 / tile $400; T1/T2, loaded once)
               · character DPLC window ($7800 / tile $3C0, DMA'd per frame)
               · permanent tiles — HUD, rings, monitors
$B800-$BFFF  SAT ($B800) + HScroll ($BC00) — tiles $5C0-$5FF, below Plane A
$C000-$DFFF  Plane A nametable (64×64; all 64 rows stream)
$E000-$FFFF  Plane B nametable (64×64; all 64 rows — no "Region 2" spill)
```

### 2.5 Art Loading Flow

**Level load (blocking):**
```
Level_LoadArt(act descriptor)              ; engine/level/load_art.emp
  → For each page of the act's paged art pool (one page = ART_POOL_PAGE_TILES = 64 tiles):
      → PageIn_Enqueue(page, PGRQ_BULK) — the page-in path resolves the manifest
        entry and decodes it: ZX0R resumable decoder → Art_Staging_Buffer
        (dedicated 2048 B, one page), or raw direct from ROM
      → QueueDMA_Important: staging buffer (or ROM) → allocated frame << 11
      → VSync_Wait spins until the page lands (display off — Important DMA
        drains at the full blanked rate)
  → BG_Init: blit the zone-wide BG to Plane B (T1; §2.4)
When the pool fits the frame budget the whole act art pool is then resident for
the life of the act (the degenerate regime); a larger pool keeps streaming
through the §9.7 residency cache during play. Section streaming and teleport
never perform a per-section art swap.
```

**Section transition (continuous scroll — current, resident art):**
```
Camera scrolls toward a section boundary
  → Edge streamer (4.7) fills the leading section's nametable + collision
    into the wrapping plane — every moving frame, no boundary burst
  → Object art is already resident (whole-act VRAM pool, paged at init);
    objects spawn at the camera edge (4.9) with their static art_tile
  → Camera crosses (Camera >> SECTION_SIZE_SHIFT) changes:
      → parallax config snap/lerp (shipped); palette cross-fade + music
        swap are descriptor-driven design-stage (sec_pal/sec_music have no
        transition consumer yet — §4.2, §7.1)
  → No art swap, no preload window, no Section_Enter event — the camera
    just keeps moving; the section is "entered" purely by world position
```

**Section transition (>frame-budget acts — SHIPPED as the §9.7 residency cache):**
```
As the camera approaches blocks referencing non-resident pages
  → page prefetch collects the ahead-strip's referenced pages and requests them
  → idle-time decode (ZX0R / raw direct) + Important-queue landing into an
    ALLOCATED frame — pages are frame-relocatable, not fixed-address
  → departed pages are evicted oldest-released-first when unpinned and refcount-free
```
See §9.7 for the full design (frame allocator, refcounts, prefetch, eviction).

**Emergency spawn (mid-gameplay — DEFERRED, needs the §2.2 allocator):**
```
Boss spawns new enemy type not in section layout
  → reserve a pool address for the new type
  → S4LZ-blocking decompress 12 tiles to that address (<0.5 ms)
  → Object spawns with valid art_tile same frame
  (S4LZ at ~510-640 KB/s: 12 tiles = 384 bytes decompressed in well under a frame)
```
Today, all object art is resident from level init (§2.2), so on-demand art
loading is not needed; this is the path a future >VRAM level would use.

**Sprite art via DPLC/DMA (per-frame):**
```
AnimateSprite
  → Animation frame changes (ros_prev_frame != current frame)
  → Perform_DPLC: read DPLC table for this animation frame
    → DPLC entry: tile_count + tile_start → ROM source address
    → Build-time contiguous layout: 1 DMA entry per frame change
  → Queue DMA from ROM directly to the object's static VRAM address
    (Important priority for characters, Deferrable for objects)
  → DPLC Lookahead (§1.6): if anim_timer <= 1, peek next frame's DPLC
    → Pre-queue as Important DMA → art ready before animation advances
  → Zero CPU decompression cost — DMA runs on VDP clock
```

**Art-pool load — RAM footprint:**
```
Art_Staging_Buffer: $800 (2,048 bytes) — one decompressed pool page
  (64 tiles × 32 bytes). Dedicated (engine/ram.emp): the steady-state
  page-in path stages every ZX0 page decode here, during init bulk-load
  and during play alike.

No chunk tables, block tables, level layout arrays, or UFTC tile buffers in RAM.
ZX0 pages decode through the staging buffer; raw pages DMA straight from ROM.
Sprite art DMA'd directly from ROM — no RAM buffer needed.
```

### 2.6 Data Format Summary

The engine uses two compression formats (ZX0 for load-time bulk, S4LZ for the runtime block stream — runtime-dispatched by the manifest's `pm_form`; the wrapper version byte is the baked truth), one random-access format (uncompressed + DPLC), and raw tilemaps. No other decompressors exist in the codebase.

| Data Class | Format | Build Tool | ROM Label Convention |
|---|---|---|---|
| Act FG art pool | ZX0 pages (wrapped) | `tools/tile_dedupe.py` (dedupe + spatial order + page) → ZX0 (`salvador`) | `<Zone>_Act_Pool_Page*` (`act_pool_page*.zx0`) |
| Runtime block stream | S4LZ v3 (+ per-section block dictionary) | `tools/s4lz.py` (optimal parse) | `<Zone>_Sec*_Blocks` (`sec*_blocks.bin`) |
| Sprite art | Uncompressed + DPLC tables | `dplc_layout` (build-time contiguous rearrangement + entry merging) | `ArtUnc_*` / `DPLC_*` |
| Tilemaps | Raw (uncompressed VDP nametable words) | Direct export from editor | `Tilemap_*` |

**Art source pipeline:** Original art assets (extracted from Sonic 2/3K or created new) are stored as raw uncompressed tiles. The act FG tiles are globally deduped, spatially ordered, paged, and ZX0-compressed at build time; block data is S4LZ-compressed. Sprite art stays uncompressed — the build tool rearranges tiles for contiguous per-frame layout and generates optimized DPLC tables.

**ROM footprint:** S4LZ decompressor is ~300 B; the ZX0 decompressor (unzx0_68000) is small as well. DPLC routine (`Perform_DPLC`) is ~0.2 KB. Raw tilemaps need no decompressor.

### 2.7 Cascade Effects

```
Two-Tier Compression (2.1)
  → ZX0 pages handle the load-time act FG art pool
    → ZX0R resumable decode (init bulk-load + idle-time streaming), Important DMA per page
    → ~zlib-class ratio (0.605 on tile art)
  → S4LZ v3 handles the runtime block stream
    → Per-section block dictionary, ~510-640 KB/s, 6 blocks/frame budget
  → runtime dispatch is manifest-form-driven; the DEBUG selftest's Art_Decompress exercises the wrapper-byte path
  → Uncompressed sprite art + DPLC/DMA — zero CPU decode cost
    → Build-time contiguous layout: 1 DMA per animation frame change
    → DMA from ROM on VDP clock — CPU free for game logic
    → DPLC Lookahead (§1.6) pre-loads next frame's art
  → Raw tilemaps for menus — direct DMA from ROM, zero decode cost

Static VRAM Assignment (2.2)
  → Act FG tiles get fixed global pool indices at build time
  → Object/permanent art gets static vram_art() addresses at build time
    → No runtime allocator, no refcount, no compaction
  → Act pool capped by ROM budget (tools/art_rom_report.py), not VRAM
    → §9.7 residency cache streams pools past the frame budget
  → (DEFERRED: dynamic per-object allocator for on-demand boss/effect art — DEFERRED_WORK)

Paged Act Art Pool (2.5)
  → Whole-act FG art is globally deduped, spatially ordered, and paged
    → ZX0R resumable decode via Art_Staging_Buffer (2048 B); raw pages DMA
      straight from ROM
    → Important-queue DMA to the ALLOCATED frame (frame << 11)
    → §9.7 residency cache — fully resident when the pool fits the frame
      budget; no per-section swap, no preload window
  → No chunk/block tables in RAM
    → Pre-computed block data from build tool, zero runtime conversion
      → Zero per-frame cost for level rendering (tile cache → plane buffer → VDP)
  → Pool budget gated at build time
    → Pool deduped; ROM budget gate (tools/art_rom_report.py) caps the act pool

Object Art Integration (3.7)
  → Archetype templates carry static vram_art() addresses
    → No allocation step at spawn, no hardcoded magic in layout data
      → Adding new objects = add to layout + assign pool/permanent tiles, done

Edge-Driven Spawning (4.8)
  → Act art paged in the §9.7 residency cache → no per-section art swap
    → Objects spawn at the camera edge with their static art_tile
      → Zero visible loading: section is "entered" by world position, not an event
        → (>frame-budget acts: §9.7 streams pages at the leading edge)

Build Pipeline (8.1)
  → tile_dedupe: global dedupe + spatial order + page the act art pool → ZX0
  → s4lz compressor for the runtime block stream (optimal parse)
  → DPLC layout tool (contiguous art rearrangement + entry merging)
    → Raw tilemap export (no encoder needed — direct nametable data)
```

---

## 3. Object System

The object system is the backbone — every gameplay entity (players, badniks, rings, monitors, bosses, effects, HUD elements) is an object with a fixed-size slot in RAM, running a state machine each frame. The design targets: O(1) allocation, data-driven spawning and child creation, a modular collision system, and an animation system that doubles as a lightweight behavior sequencer.

### 3.1 SST Layout — $50 Bytes, Logical Field Grouping

Every object occupies an 80-byte ($50) Sprite Status Table entry. The H1 render cache `frame_off` (caches the resolved mapping frame-data offset; refreshed on every `mapping_frame`/`mappings` write via `RefreshSpritePieceCount`, or animator-owned via the prev_anim=$FF idiom) lives at $2E inside the engine block since the sst-fold (2026-08-05) — its 2026-08-03 bolt-on position at $50 briefly grew the record to $52; the fold closed the engine fields at $00-$2F, put the 32-byte custom window at the record tail ($30-$4F, `SST_interact` in its last word), and restored the long-divisible $50 size (the whole-record clear is an exact 20-longword loop again). Fields are grouped by logical function — dispatch, physics, render/collision, animation, links, engine, and custom data. The 68000 has no data cache, so there is no hardware benefit to field ordering. The grouping is a code-maintenance and `movem` optimization: related fields at contiguous offsets means routines that access multiple fields can batch them, and the layout is self-documenting.

The one field that IS performance-critical at $00: `move.w (a0), d0` (zero offset) saves 2 bytes + 4 cycles per dispatch versus any non-zero `d(a0)` offset. All `d(An)` displacements within a $50 SST are 16-bit and cost the same — $00 is the only special case.

```
; === Dispatch ===
$00  code_addr              ; (word) — object code offset from ObjCodeBase
                            ;          zero = empty slot

; === Physics ===
$02  x_pos                  ; (long) — 16.16 subpixel position [patched at spawn]
$06  y_pos                  ; (long) — 16.16 subpixel position [patched at spawn]

; === Template block $0A-$1F — burst-copied verbatim from ObjDef at spawn ===
$0A  x_vel                  ; (word) — horizontal velocity (8.8 fixed-point)
$0C  y_vel                  ; (word) — vertical velocity (8.8 fixed-point)
$0E  render_flags           ; (byte) — bit 0 on-screen, 1 x-flip, 2 y-flip,
                            ;          3 coord mode, 4 multi-sprite,
                            ;          bits 5-7 priority band (absorbs old $16 word)
$0F  collision_resp         ; (byte) — collision type dispatch (0 = none)
$10  mappings               ; (long) — sprite mapping pointer (ROM)
$14  art_tile               ; (word) — VRAM tile index + palette + priority
$16  width_pixels           ; (byte) — collision width (FULL, not half)
$17  height_pixels          ; (byte) — collision height (FULL, not half)
$18  anim                   ; (byte) — desired animation ID
$19  subtype                ; (byte) — object subtype
$1A  anim_table             ; (long) — animation table pointer (ROM)
$1E  status                 ; (byte) — player/object status bits (ST_*)
$1F  angle                  ; (byte) — terrain angle

; === Runtime block $20+ — initialized individually at spawn ===
$20  prev_anim              ; (byte) — previous anim ID ($FF at spawn)
$21  anim_frame             ; (byte) — byte offset within animation script
$22  anim_timer             ; (byte) — frame duration countdown
$23  mapping_frame          ; (byte) — current mapping frame index
$24  prev_frame             ; (byte) — previous mapping_frame ($FF at spawn)
$25  sprite_piece_count     ; (byte) — current frame's piece count (overflow prediction)
$26  parent_ptr             ; (word) — parent object RAM address
$28  sibling_ptr            ; (word) — sibling link (multi-part objects)
$2A  slot_tag               ; (byte) — entity window slot tag (SLOT_TAG_*; $FF = untagged)
$2B  entity_section_id      ; (byte) — spawning section's flat id (despawn bookkeeping)
$2C  entity_list_index      ; (byte) — index in section's ROM object list (killed bitmask)
$2D  layer                  ; (byte) — collision layer select (0 = path A, 1 = path B)

; === Custom data — per-object overlays ===
$2E-$2F  frame_off             ; engine-owned cached frame offset (sst-fold)
$30-$4F  sst_custom (32 bytes) ; Player overlay, boss overlay, or custom
                               ; tail word $4E-$4F = engine-owned SST_interact,
                               ; so 30 bytes are game-usable
                               ; (the overlay window check asserts it fits)
```

**Dispatch:** Word code_addr at $00 stores an offset from `ObjCodeBase` (a $10000-aligned label). Dispatch reconstructs the full address: `moveq #BANK, d0; swap d0; move.w (a0), d0; movea.l d0, a1; jsr (a1)`. The `objroutine` AS function computes offsets at build time: `objroutine function x, (x)-ObjCodeBase`. `tst.w (a0); beq.s .skip` tests for empty slots. This is the sonic_hack pattern — validated across the full game.

**Template block:** The 26-byte ObjDef archetype image (3.7) is a verbatim ROM copy of SST $00 (code_addr) plus $0A-$21 — spawning burst-copies $0A-$21 (24 bytes) with `movem.l`, zero field reordering ($20-$21 land as pad and are immediately re-initialized by the runtime init). Sprite priority lives in render_flags bits 5-7 (`RF_PRIORITY_SHIFT`/`RF_PRIORITY_MASK`) — the old separate priority word at $16 is gone.

**Links:** `sibling_ptr` replaces `child_ptr` — Alien Soldier's research shows dual link fields (parent + sibling) are more useful than parent + child for multi-part boss communication.

**SST size: $50.** It was $50 through 2026-08-02, briefly $52 when the sprites-H1 cached frame offset landed at $50 (2026-08-03), and back to **$50 since the sst-fold (2026-08-05)**, which moved `frame_off` down into `$2E-$2F` and set the custom window at **`$30-$4F`** — 32 bytes, of which the tail word `$4E-$4F` is the engine-owned `SST_interact` (the solid that claimed a player slot this pass), leaving **30 game-usable bytes**. The objects-v2 field audit before it removed the dead fields (`respawn_index`, `wait_timer`, the separate priority word) and packed the entity-window metadata (`slot_tag`/`entity_section_id`/`entity_list_index`/`layer`) into the freed space. **The "does the player overlay need more room" question is CLOSED:** the fully-populated three-character overlay (Sonic + Tails' flight + Knuckles' glide/climb) uses 26 of the 30, so no variable-size pools and no per-pool stride are needed — see §5.4.

**Slot ranges:**
- Slots 0-1: Players (Sonic, Tails)
- Slots 2-41: Dynamic level objects (40 slots)
- Slots 42-57: Effects/particles (16 slots — ring scatter, explosions, dust, score popups)
- Slots 58-65: System objects (HUD, shields, title cards)

Each range has its own free stack for targeted allocation. Effect objects can never fill gameplay slots. Spawn guard (from Thunder Force IV): `cmp.w #MAX, spawn_count; bhi .skip` prevents cascade pool exhaustion.

### 3.2 Free Slot Stack — O(1) Allocation (NOVEL)

All reference engines use linear scan for object allocation. S.C.E.'s `Create_New_Object` scans with `tst.l code_addr(a1); dbeq d0,.find`. Batman uses a doubly-linked free list (heavier). Our approach is simpler and faster than both:

```
Free_Slot_Stack:    ds.w  MAX_DYNAMIC_SLOTS   ; word array of free slot addresses
Free_Slot_SP:       ds.w  1                    ; stack pointer

; Allocate: one instruction
AllocSlot:
    movea.w -(Free_Slot_SP), a1     ; pop free slot address

; Free: one instruction  
FreeSlot:
    move.w  a0, (Free_Slot_SP)+     ; push slot back

; Init at level start: push all dynamic slot addresses
```

O(1) allocate, O(1) free, zero overhead, no linked-list pointers consuming SST space. All five `SingleObjLoad` variants collapse into one stack pop. `DeleteObject` becomes a stack push + slot clear (via `movem.l` — two instructions clear all 80 bytes). No commercial Genesis game uses this approach — all use linear scan. This is the single biggest algorithmic win in the object system.

**Deletion strategy: immediate.** Research across 7 references overwhelmingly favors immediate deletion (5/7 use it). `DeleteObject` pushes the slot address back to the free stack, then zeros the entire SST. No mark bits, no sweep pass, no deferred phase. `RunObjects` skips empty slots via `tst.w (a0); beq.s .skip`. Parent-child cascades are safe: children check `tst.w (parent_ptr)` — if parent's code_addr is zero, child self-deletes. Alien Soldier's mark-and-sweep exists to solve mid-iteration mutation of a pointer list, which our stride-based iteration avoids by design.

**Spawn guard (from Thunder Force IV):** `cmp.w #MAX_SPAWNS_PER_FRAME, spawn_count; bhi .skip` prevents pathological pool exhaustion from spawn cascades (e.g., ring scatter triggering multiple explosion spawns).

### 3.3 Data-Driven Child Creation (from S.C.E.)

S.C.E. has 12 child creation routines, all driven by descriptor tables. Distilled to 4 core strategies that cover all use cases:

| Strategy | Descriptor Fields | Use Case |
|---|---|---|
| **CreateChild_Normal** | code_addr, XY offsets | Badnik projectiles, debris |
| **CreateChild_Complex** | code_addr, setup_addr, animations, wait_addr, XY offsets, velocity | Boss sub-objects with full init |
| **CreateChild_Linked** | code_addr (repeated, doubly-linked chain) | Snake segments, train cars |
| **CreateChild_FlipAware** | Same as Complex, negates X when parent flipped | Directional boss weapons |

All use the free slot stack for allocation. All auto-set `parent_ptr`/`sibling_ptr`. Children inherit `mappings` and `art_tile` from parent (no separate VRAM allocation for shared art), plus the render flags in `CHILD_INHERITED_FLAGS` — coordinate mode and, since the C1c ruling (2026-08-05), the parent's 3-bit priority band via the clear-then-set `set_priority_band` idiom (`engine/objects/sst.emp`; a plain `or` of band *values* could yield a third band, so the band bits are masked out before the parent's are OR'd in).

**Cleanup chain:** On parent death, walk sibling_ptr chain and delete all children. Children also check parent — if parent's code_addr is zero, self-delete. S.C.E.'s `Child_Draw_Sprite` auto-delete behavior is ported into the render path.

**Descriptor table example:**
```
BossChildren:
    dc.w  3-1                ; 3 children (dbf format)
    dc.l  BossArm            ; child 1 code
    dc.b  -24, -16           ; child 1 XY offset
    dc.l  BossArm            ; child 2 code
    dc.b  24, -16            ; child 2 XY offset
    dc.l  BossHead           ; child 3 code
    dc.b  0, -32             ; child 3 XY offset
```

### 3.3.1 Effect Pool Spawning (fire-and-forget)

`CreateEffect_Normal` and `CreateEffect_Simple` mirror the child creation API but allocate from the **effect pool** (16 dedicated slots) instead of the dynamic pool. Effects are fire-and-forget: no sibling chain linking, no parent lifecycle management. They auto-despawn via `AF_DELETE` when their animation ends.

| Routine | Inputs | Behavior |
|---|---|---|
| **CreateEffect_Normal** | a0=parent, a1=descriptor (same 4-byte format as CreateChild_Normal) | Allocate from effect pool, inherit mappings/art_tile, set parent_ptr, position from parent + offsets |
| **CreateEffect_Simple** | a0=parent, d0.w=code_addr, d1.w=count | Spawn N identical effects at parent position from effect pool |

Both fail silently on pool exhaustion. Effects use `AllocEffect`/`DeleteObject` which manages the effect free stack independently from dynamic slots — effect objects can never consume gameplay object slots.

**Render_Sprites mid-frame guard:** Objects added to a sprite band via `Draw_Sprite` can be deleted later in the same `RunObjects` pass (e.g., `DeleteChildren` cascade). `Render_Sprites` guards against this by checking for null mappings before processing each band entry, skipping zeroed slots.

### 3.4 Collision System — Type Dispatch with Direct Dimensions (NOVEL)

The collision system is a custom design that's more modular than any reference engine. Traditional approaches pack collision type + size into one byte and look up dimensions from a table. S.C.E. uses a registration list. Our approach:

- `collision_response` is a **pure type byte** — determines *how* the object reacts to contact (solid, enemy, spring, hurt, etc.)
- `width_pixels` / `height_pixels` in the SST provide collision dimensions directly — no lookup table needed
- `TouchResponse` iterates all dynamic slots, checks `collision_response` for non-zero, and dispatches to the appropriate handler

**Collision types:**
```
COLLISION_NONE          = 0
COLLISION_ENEMY         = 1     ; killable by spin/roll
COLLISION_BOSS          = 2     ; killable, HP-based
COLLISION_HURT          = 3     ; hurts on any contact
COLLISION_MONITOR       = 4     ; breakable from below/spin
COLLISION_RING          = 5     ; collectible
COLLISION_BUBBLE        = 6     ; air bubble
COLLISION_PROJECTILE    = 7     ; fire-and-forget damage
COLLISION_SOLID         = 8     ; full AABB solid
COLLISION_SOLID_BREAK   = 9     ; solid, breaks when spinning
COLLISION_SPRING        = 10    ; solid + bounce (5 directions)
COLLISION_SOLID_HURT    = 11    ; solid + hurts on specific face
COLLISION_TOUCH         = 12    ; generic touch (object handles via ckhit)
```

Each handler uses doubled-delta AABB math with the full `width_pixels`/`height_pixels` values. Touch_Solid does axis detection (which side was contacted) for proper standing/push/slide behavior. Touch_Spring reads orientation from subtype bits. Touch_SolidHurt checks contact face against `objoff_3A` (SPIKE_FACE_TOP/BOTTOM/SIDES).

**Why this beats every reference:** Objects set collision_response to a type and width/height to their actual dimensions — done. No size table, no registration, no bit packing. Any object can become solid, or an enemy, or a spring, just by changing one byte. New collision behaviors are new handler routines + a new type constant.

### 3.5 Sprite Rendering Pipeline (from S.C.E.)

S.C.E.'s two-phase approach:

**Phase 1 (during object loop):** Each object calls `Draw_Sprite`, which resolves the current mapping frame, culls exactly against its precomputed bbox header (7.8), and adds the object's RAM address to a priority-band list. No sprite data conversion.

**Phase 2 (`Render_Sprites`):** Single pass through priority-sorted lists, converting object data to VDP sprite table entries. Handles:
- **Standard sprites:** `BuildSprites_Classic` — dynamic frame indexing from mapping table
- **Static sprites:** `BuildSprites_Static` — fixed mapping, no animation
- **Compound sprites:** `BuildSprites_Compound` — walks sibling_ptr chain (3.3), one bounds check for parent, all children render under it

**Multi-sprite batching:** `render_flags.multi_sprite` routes to `Render_Sprites_MultiDraw`. Combined with parent-driven animation (3.7), a multi-part boss is: one AnimateSprite call on parent → one bounds check → all children render. Three systems converge.

**Additional features:**
- Pre-initialized link chain (80 entries, set at level init); per-frame Render_Sprites rewrites links for emitted pieces and patches the terminator after the last one (the "never rebuilt" optimization is a wash on 68000 — see §1.2)
- Overflow protection: full priority band overflows to next band (S.C.E.), with TF4-style round-robin rotation if overflow is visible
- Sprite count per object in SST for overflow prediction (from Batman's `sprite_link_count`)
- Sprite table dirty flag — skip $280-byte DMA on static frames (confirmed by Gunstar's conditional sprite DMA pattern)
- VDP-order mapping format eliminates field reordering (pre-formatted SAT already achieved)

**Sprite link-order cycling for overflow fairness (IMPLEMENTED):** When >20 sprites land on one scanline, the VDP drops everything past the 20th in link-chain order. `Render_Sprites` reverses intra-band object processing direction on odd frames via `Sprite_Cycle_Counter`, distributing dropout as flicker rather than permanent disappearance. Step direction (+2/-2) stored on stack to avoid register pressure. Cost: +3 scanlines on Render_Sprites. Only Thunder Force IV among commercial games implements this.

**Sprite X=0 masking (IMPLEMENTED):** `InsertSpriteMasks` writes 8×32px sprites at X=0 between priority bands during SAT construction. Configured via `SpriteMask_Y` (VDP Y position), `SpriteMask_Height` (scanlines to cover), `SpriteMask_After_Band` (insertion point). The VDP stops rendering subsequent sprites on covered scanlines. Zero cost when disabled (`SpriteMask_Y = 0`). Used for HUD/status bar clipping without the Window plane.

**Scanline-aware sprite budgeting (IMPLEMENTED):** Screen divided into 7 bands of 32 scanlines. `Scanline_Band_Sprites` array tracks accumulated sprite pieces per band. At `.have_pos` in `Render_Sprites`, objects are skipped when their band exceeds `SCANLINE_SPRITE_LIMIT` (24 pieces). Threshold optimization: budget check skipped entirely when total rendered pieces < 24 (no band can overflow yet). Cost: +6 scanlines on Render_Sprites. No commercial Genesis game implements per-band sprite budgeting.

**VDP sprite cache behavior (from Kabuto hardware notes):** The VDP processes sprites in 4 phases per scanline: (1) scan Y/size/link from write-through cache, (2) fetch X/tile fresh from VRAM, (3) render tiles to line buffer, (4) display. Y/size/link are cached via write-through — CPU writes to SAT VRAM update the cache immediately. X/tile is re-read from VRAM each frame. Both per-scanline limits (20 sprites AND 320 sprite pixels) are enforced simultaneously — whichever is hit first causes dropout.

### 3.6 Animation System — Behavior Sequencer (NOVEL)

The animation system is a **lightweight behavior sequencer** — bytecode-driven animation with frame-triggered callbacks. No Genesis game has this.

**Bytecode animation script format:**
```
Ani_Walk:
    dc.b  4              ; frame duration (ticks)
    dc.b  0, 1, 2, 3     ; mapping frame indices
    dc.b  $FF             ; loop
; Control codes: $FF=loop, $FE=jump back, $FD=branch, $FC=routine-inc, $FB=delete
```

**Animation events (NOVEL):**
All events consume an even number of bytes (for PerFrame alignment). Events execute inline when encountered and continue reading the next byte — multiple events can chain before a frame.
```
$FA = AF_CALLBACK   (dc.b $FA, target_hi, target_lo, 0) — call objroutine offset (big-endian byte pair; scripts are unaligned)
$F9 = AF_SOUND      (dc.b $F9, sound_id)             — play sound effect (stub until driver)
$F8 = AF_COLLISION  (dc.b $F8, collision_type)        — set SST_collision_resp
$F7 = AF_SET_FIELD  (dc.b $F7, sst_offset, value, 0) — set arbitrary SST byte
```

Speed-linked animation and per-frame delays are handled by calling conventions (`AnimateSprite` vs `AnimateSprite_PerFrame`), not by event codes. Speed formula: `duration = max(0, ($800 - abs_speed)) >> 8`.

**Example — boss attack with events (PerFrame mode):**
```
Ani_BossAttack:
    dc.b  0, 8             ; frame 0: 8 ticks (slow wind-up)
    dc.b  1, 6             ; frame 1: 6 ticks
    dc.b  AF_COLLISION, COLLISION_HURT  ; EVENT: become dangerous
    dc.b  2, 2             ; frame 2: 2 ticks (strike)
    dc.b  AF_SOUND, sfx_Impact         ; EVENT: play impact sound
    dc.b  AF_CALLBACK, (objroutine(BossFireHook))>>8, (objroutine(BossFireHook))&$FF, 0 ; EVENT: call routine
    dc.b  AF_COLLISION, COLLISION_SOLID ; EVENT: safe again
    dc.b  3, 4             ; frame 3: follow-through
    dc.b  AF_END            ; loop
    even
```

Objects that currently do "check timer → spawn thing" delete that logic entirely. Animation scripts handle all timing. New attack patterns = new data, not new code.

**Animation table in SST:** Stored at `anim_table` ($1A), set by `Load_Object` from the archetype template. `AnimateSprite` reads it internally — no more `lea (Ani_Table).l,a1` before every call. Saves ~60 `lea` instructions per frame across all active objects.

**Multi-sprite animation (from S.C.E.):** `Animate_MultiSprite` drives all children from the parent's animation script. Each child reads the parent's `mapping_frame` and applies its own mapping offset. Multi-part objects animate in sync with one call.

### 3.7 Object Loading — Archetype Templates (objects-v2)

Each object type is a 26-byte ObjDef archetype: a verbatim ROM image of SST $00 (code_addr) plus the $0A-$21 template block, emitted by the `objdef` comptime fn (`engine/objects/objdef.emp`):

```
; ObjDef layout (26 bytes — exact SST image, zero field reordering):
;   +0:  dc.w  objroutine(Code)              ; code_addr
;   +2:  dc.w  x_vel, y_vel                  ; $0A-$0D image
;   +6:  dc.b  render_flags, collision_resp  ; $0E-$0F image (priority in RF bits 5-7)
;   +8:  dc.l  mappings                      ; $10-$13 image
;   +12: dc.w  art_tile                      ; $14-$15 image
;   +14: dc.b  width, height                 ; $16-$17 image
;   +16: dc.b  anim, subtype                 ; $18-$19 image
;   +18: dc.l  anim_table                    ; $1A-$1D image
;   +22: dc.b  status, angle                 ; $1E-$1F image
;   +24: dc.w  0                             ; $20-$21 pad (re-inited at spawn)

objdef code=TestEnemy_Init, map=Map_TestObj, art=vram_art(VRAM_TEST_OBJ,0,0), \
       zpri=4, xvel=ENEMY_PATROL_SPEED, wdth=16, hght=16, col=COLLISION_HURT
```

`Load_Object` spawns in three steps:

1. **Allocate:** `AllocDynamic` pops a free SST address (3.2) and tags the slot `SLOT_TAG_UNTAGGED` ($FF) — the entity window (4.9) re-tags slots it owns.
2. **Burst copy:** code_addr word, then the 24-byte $0A-$21 block via three `movem.l` pairs — no per-field parsing, no format byte, no conditional paths. The ObjDef layout IS the SST layout.
3. **Per-placement patch:** X/Y converted to 16.16 and stored; placement subtype overwrites the template default; placement flip bits (OEF bits 13-14) rotate into position with a single `rol.w #4` and OR into both render_flags (RF_XFLIP/RF_YFLIP) and status; runtime block re-initialized (prev_anim/prev_frame = $FF for change detection); `sprite_piece_count` seeded from mapping frame 0's piece count (at +4, after the bbox header — 7.8).

Art is referenced by `art_tile` directly (build-time VRAM layout); per-frame character art goes through the DPLC pipeline (3.9). Every object type's full spawn state lives in its objdef line — single source of truth, and the macro build-fails on overflow (priority > 7, image size ≠ 26).

**Object-authoring rule: store re-derivable positional state, not raw absolute coordinates in `sst_custom`.**
In continuous-scroll there is no per-frame coordinate shift — `SST_x_pos`/`SST_y_pos`
are plain world coordinates that never move under an object. The one event that *does*
shift the whole live set is the future floating-origin rebase (§4.11): a coarse,
invisible, atomic subtraction of `REBASE_DELTA` from every live world coordinate. The
rebase walker shifts `SST_x_pos`/`SST_y_pos` for every active object, but it cannot see
absolute world coordinates buried in `sst_custom` (patrol anchors, waypoint targets,
"return home" positions) — those would go stale by `REBASE_DELTA` and the object would
lurch. Keep positional state relative (offsets, counters, velocities) or re-derivable
from the ROM placement (which is section-local and rebase-invariant). An object that
genuinely needs a stored absolute coordinate must register it for the rebase walk
(design the mechanism when the need first arises — likely a per-ObjDef shift mask of
custom longwords). See `CODING_CONVENTIONS.md` §7.8.

### 3.8 Per-Frame Systems — Design Rationale

Comparative analysis across S.C.E. and 5 commercial Genesis engines informed which per-frame system patterns to adopt vs. redesign:

| System | Approach | Architecture |
|--------|----------|--------------|
| **Render_Sprites** | S.C.E. two-phase | 8-priority-level iteration with pre-computed link numbers at init, render callbacks for level-specific sprite injection. |
| **RunObjects** | Tiered execution | 4-tier execution (Reserved/Dynamic/LevelOnly/Deferred). Slot-based entity management (4.9) handles spawn/despawn lifecycle. |
| **Entity Management** | Camera-driven window (novel) | Camera-driven entity window (4.9) with per-section X-sorted ROM lists, unified ring buffer, 3×3 rolling collected bitmask. Free slot stack (3.2) for runtime-spawned objects. |
| **AnimateSprite** | Bytecode sequencer | Bytecode system ($FF/$FE/$FD/$FC/$FB) with animation events (3.6) and pause flag. |
| **TouchResponse** | Type dispatch | Two-pass gather→respond with per-type handlers (3.4). Collision masks for early-exit. Modular file structure per collision type. |
| **Ring System** | Camera-driven (novel) | Unified 128-entry ring buffer, flat X-sorted ROM lists per section, swap-with-last O(1) removal, 3×3 rolling collected bitmask (4.9). |

**Dynamic allocator integration with free slot stack (3.2):** The free slot stack provides the allocation primitive for both paths. Level objects spawn via the camera-driven entity window (4.9) — as objects scroll into camera range, their compact 6-byte ROM entries are read, the section's ROM type table is consulted for the ObjDef pointer, and `Load_Object` calls `AllocDynamic` to pop a free SST address. Dynamic objects (boss parts, projectiles, cutscene actors) call `AllocDynamic` directly. Both paths produce objects in the same SST — the execution loop doesn't distinguish them.

**Parent-child links (from Treasure — Gunstar Heroes / Alien Soldier):** The `parent_ptr` ($26) and `sibling_ptr` ($28) fields in the SST (3.1) enable multi-part boss coordination: child auto-delete when parent dies, sibling chain iteration, inherited art/palette. Validated by 380+ references in Alien Soldier.

### 3.9 Per-Frame Art Loading (DPLC Pipeline)

Two tiers of per-frame art management:

- **Static object art:** VRAM address pre-assigned in the archetype template via the `vram_art()` macro at build time. Resident for the level lifetime (no per-section unloading, no dynamic allocation). No per-frame processing needed.
- **Animated sprite art:** Per-frame — animation frame changes need different tiles. Generic `Perform_DPLC` routine (works for all objects, not per-character) detects frame changes via per-object `ros_prev_frame` field, reads DPLC table for the new frame, and queues DMA from uncompressed ROM art directly to the object's allocated VRAM address. Build-time contiguous art layout guarantees 1 DMA entry per frame change. Character DPLCs → Important priority (guaranteed delivery). Object DPLCs → Deferrable priority (budget-gated).
- **DPLC Lookahead (NOVEL — §1.6):** When `anim_timer <= 1`, peek at the next animation frame's DPLC requirements and pre-load as an Important-priority DMA entry. Art arrives before the frame changes — zero-latency animation transitions. No Genesis game does this.
- **128KB DMA boundary safety:** All DPLC DMA transfers are checked for 128KB ROM boundary crossings. Transfers that would cross a boundary are split into two entries. See §2.1 for details.

### 3.10 Cascade Effects

```
Object System Cascades:

Free Slot Stack (3.2)
  → All child creation strategies use stack pop, not linear scan
    → DeleteObject pushes back to stack
      → Ring scatter pool uses dedicated stack range (slot ranges from 3.1)

Data-Driven Child Creation (3.3)
  → parent_ptr / sibling_ptr in SST link objects
    → BuildSprites_Compound walks child chain (3.5)
      → Animate_MultiSprite drives children from parent (3.6)
        → Child_Draw_Sprite auto-deletes orphans
          → Boss death = one walk + delete, zero orphaned sprites

Collision Type Dispatch (3.4)
  → collision_response set by Load_Object data block
    → width/height from SST, no lookup table
      → New collision behaviors = new handler routine + type constant
        → No registration, no bit packing, no size table

Animation Events (3.6)
  → Frame-triggered callbacks replace manual timer logic
    → Object code shrinks (delete "check timer → do thing" patterns)
      → New attack patterns = new animation data, not new code
        → Animation speed scaling links to velocity (one anim, continuous speed)

Load_Object + Allocator (3.7)
  → The archetype template includes art requirements
    → AllocVRAM checks loaded table → refcount bump or new load
      → S4LZ (streamed or blocking) or uncompressed (DPLC) based on format flag
        → art_tile written to SST from allocator return value
          → Child objects inherit parent art_tile (no separate alloc)

Per-Frame Art Loading (3.9)
  → Static object art: allocator handles at spawn (no per-frame processing)
  → Animated sprite art: Perform_DPLC queues DMA from ROM on frame change
    → Build-time contiguous layout: 1 DMA per frame change
    → Character DPLCs → Important priority, Object DPLCs → Deferrable
    → DPLC Lookahead (§1.6) pre-loads next frame's tiles
      → Zero-latency animation transitions

Camera-Driven Entity Integration (4.9 → 3.2 + 3.7)
  → Level objects spawn via camera-driven entity window
    → AllocSlot (3.2) provides SST address, Load_Object (3.7) initializes fields
      → Per-section type table resolves 5-bit index to routine pointer
        → Edge spawning: objects spawn as the camera scrolls their section into the despawn envelope (no preview zone, no teleport)
```

---

## 4. Level / World System

The level system is the engine's most unique feature. A 2D section grid gives levels true vertical depth — jungle canopy → floor → lake → cave. Each section is a 16×16 chunk cell with its own art, palette, parallax, objects, and music. The camera scrolls **continuously** across the whole act in world space; sections are simply fixed world ranges whose data streams into the wrapping VDP plane at the leading edge as the camera approaches. No Genesis game has achieved this level of per-area independence.

> **Design source of truth:** the continuous-scroll traversal model is specified in full in `docs/superpowers/specs/2026-06-22-continuous-scroll-traversal-design.md` (§9 of that spec = the floating-origin rebase; mirrored here as §4.11). The sections below are the architecture-level description; the spec carries the per-file migration detail.

### 4.1 2D Section Grid — Continuous World-Space Scrolling

The engine uses a single continuous world-space camera over a hardware-wrapping VDP plane — the classic Sonic 2 / Sonic 3 & Knuckles / S.C.E. model. There is **no slot system, no teleport, and no per-section coordinate rebase** in normal play. (The 2-slot "leapfrog" that an earlier draft documented was an assistant-authored bet the resident art pool made unnecessary; it has been deleted. The only invisible-rebase mechanism the engine reserves is the coarse floating-origin renumber in §4.11, used only when a level exceeds the 16-bit coordinate ceiling.)

**Continuous world camera.** `Camera_X/Y` and player positions are 16.16 **world** coordinates running `0 … level extent`. There is no bounded engine space, no `$200`/`SLOT_ORIGIN` bias, and nothing shifts under the player as it scrolls. Sections live at fixed world ranges:

```
level_width  = grid_w × SECTION_SIZE      (SECTION_SIZE = $800 = 2048 px)
level_height = grid_h × SECTION_SIZE

sec 0 : world px    0 .. 2047
sec 1 : world px 2048 .. 4095
sec 2 : world px 4096 .. 6143   ...
```

`Camera_X/Y` clamp to `[0, level_width − SCREEN_W]` / `[0, level_height − SCREEN_H]`, computed live from the grid dimensions — no hardcoded boundaries, and `Player_LevelBound` clamps the player to `[0, level)` in the same world units.

**VDP plane wrap (the key mechanism).** Plane A and Plane B are 64×64 cells = 512×512 px. The VDP masks the HScroll/VScroll registers to the plane dimension, so a continuously-growing world scroll position wraps the 64 nametable cells **in hardware** — the same cells are reused as the camera advances, with no coordinate rebase. Nametable cell writes are simply `world_col & 63`; HScroll/VScroll are the world camera position fed straight to the VDP. This is exactly how S2/S3K scroll an arbitrarily long level over a fixed 64-cell plane.

**Streaming at the leading edge.** The tile cache (§4.7) is a world-space window larger than the screen. As the camera approaches a section boundary, the cache streams the next section's nametable + collision into the wrapping plane at the leading edge, so "seeing into the next section" is always-on and automatic — this is what the old preview zone did by hand, now intrinsic to continuous scrolling. The streaming cursor writes columns/rows just as they rotate onto the leading edge of the visible window; nothing is special about a section boundary. Tile-cache internals (block staging, decompression, the per-frame budget) are unchanged from §4.7.

**Section → data lookup (the only place sections enter the hot path).** A section index is a pair of shifts off the world position:

```
sec_x   = world_px_x >> SECTION_SIZE_SHIFT      ; SECTION_SIZE_SHIFT = 11
sec_y   = world_px_y >> SECTION_SIZE_SHIFT
flat_id = sec_y × grid_w + sec_x                ; Section_FlatIDXY
sec_ptr = base + flat_id × Sec_len              ; Section_GetSecPtrXY
```

`Section_FlatIDXY` / `Section_GetSecPtrXY` are grid-agnostic and unchanged — only the *source* of `sec_x/sec_y` changed (from the deleted slot map to a 2-shift derive off the world camera).

**Section addressing:** `section(X, Y)` where X is always ≥ 0 (0 = level start) and Y indexes grid rows downward (0 = starting band; the grid can extend above the start row for sky/canopy and below for caves/lakes). The vertical Y=0 ceiling of classic Sonic is removed.

**Section size: 16×16 chunks (2048×2048 pixels per cell).** Sized for granular diversity — each cell gets its own palette, parallax, art, music. The continuous camera crosses a 2048-px section at max scroll in ~170 frames; the edge streamer keeps the leading section's nametable/collision filled the whole way (its frame budget is sized for sustained scroll, not a boundary burst — see §4.7).

**Boundary clamping is data-driven:** When `section(X, Y)` has no neighbor (null in table / outside the grid), the camera clamp at the act edge stops there. No hardcoded boundaries. Levels can be irregularly shaped:
```
Example: Oracle Jungle Zone Act 1
              X=0      X=1      X=2      X=3
  Y=-1 (sky): [sky]    [sky]    [canopy]  [canopy]
  Y=0 (main): [intro]  [jungle] [ruins]   [temple]
  Y=1 (below):         [lake]   [cave]
  Y=2 (deep):                   [deep]
```

### 4.2 Section Definition — Per-Cell Configuration

Each section in the 2D grid is fully self-describing — almost its own level:

```
; Section definition — 66 bytes per (X, Y) cell (Sec struct in structs.emp):
    dc.l    sec_block_index      ; +$00: 256-entry block index (ROM pointer, see §4.3/§4.7)
    dc.l    sec_objects          ; +$04: object layout (6-byte objentry entries, X-sorted, see 4.9)
    dc.l    sec_rings            ; +$08: ring layout (flat X-sorted dc.w pairs, section-local coords, see 4.9)
    dc.l    sec_plc              ; +$0C: art PLC list (S4LZ format)
    dc.l    sec_pal              ; +$10: palette pointer — full 128-byte copy (0 = no change)
    dc.l    sec_parallax_config  ; +$14: parallax_config pointer (0 = inherit act default; §4.6)
    dc.l    sec_raster_table     ; +$18: raster command table pointer (0 = keep current, see §7.2)
    dc.l    sec_bg_layout        ; +$1C: per-section Plane B layout pointer (NULL = use Act default; §2 A.5)
    dc.l    sec_type_table       ; +$20: type table (ROM): dc.b count,pad; dc.l ObjDef×N (§4.9)
    dc.l    sec_pal_cycle        ; +$24: palette cycling script (0 = keep current)
    dc.l    sec_sound_bank       ; +$28: DAC sample bank pointer (0 = keep current)
    dc.l    sec_block_dict       ; +$2C: raw block-dictionary ptr (block blob + index size; LZ window pre-seed)
    dc.l    sec_anim_blocks      ; +$30: animated tile script (0 = none)
    dc.l    sec_collision_s4lz   ; +$34: reserved (collision embedded in block data; §4.7)
    dc.w    sec_flags            ; +$38: SF_* bitmask (see below)
    dc.w    sec_music            ; +$3A: music change (0 = keep current)
    dc.b    sec_pcfg_pad_3C      ; +$3C: reserved (parallax config moved to sec_parallax_config)
    dc.b    sec_camera_lookahead ; +$3D: camera look-ahead pixels (0 = zone default)
    dc.b    sec_pcfg_pad_3E      ; +$3E: reserved
    dc.b    sec_pcfg_pad_3F      ; +$3F: reserved
    dc.w    sec_block_dict_len   ; +$40: block-dict bytes (768×K, K≤3, word-even; 0 = no dict)
; Sec_len = $42 (66 bytes). Per-section tile art removed — art is the act-wide
; paged pool on the Act descriptor (act_art_pool_table / act_art_pool_pages).

; sec_flags: SF_HAS_WATER | SF_UNDERGROUND | SF_NO_Y_WRAP | SF_PRESERVE_STATE | SF_HAS_ANIMATED_BLOCKS
```

Fields default to 0 (keep current state). Each section is effectively its own world — unique terrain art, unique background motion, unique palette cycling, unique physics, unique music, unique parallax, all from data alone. No Genesis game has this level of per-area control within a single level.

**Audit note (2026-08-02):** the layout table above matches `engine/structs.emp` field-for-field — all 21 members from `$00` to `$40`, `sizeof(Sec) = 66` (`$42`), which is `ensure`-guarded in `engine/level/section.emp` and `engine/level/tile_cache.emp`. Two names sometimes mistaken for `Sec` members are not fields of it: `sec_grid_ptr` is an **`Act`** field (`Act` +$00, the section-definition-array pointer), and `sec_id` is a **computed** flat index (`sec_y × grid_w + sec_x`, `engine/level/tile_cache.emp`) never stored in the struct. The `SF_*` bit names listed above are still descriptor surface ahead of code: the `sec_flags` field ($38) exists, but the individual `SF_*` constants are not yet defined anywhere in `engine/`/`games/` (the `sec_pal` precedent — a field/name documented ahead of a consumer).

**Palette format:** `sec_pal` points to a full 128-byte palette copy (all 4 palette lines × 16 colors × 2 bytes) — raw CRAM data, no delta format, no compression. **Descriptor field only — no shipped consumer.** No section-transition code reads `sec_pal` today (engine level code reads `sec_bg_layout`/`sec_parallax_config`/`sec_block_dict`/`sec_block_index`/`sec_camera_lookahead`, not `sec_pal`); the descriptor-driven palette *load* on section transition — instant or cross-faded — is **design-stage** (§7.1, whose §7 banner marks the whole palette-transition/cross-fade/cycling cluster as PLANNED, not implemented). What ships today is the game-poked path: game code writes `Palette_Buffer` (128 B RAM) and sets `Palette_Dirty` bits, and `Enqueue_Dirty_Buffers` DMAs the dirty lines to CRAM (§7.1 "Per-palette-line dirty DMA").

### 4.3 Pre-Computed Nametable Data (Block-Based) (confirmed by Batman & Robin)

**Batman proof:** Batman stores raw VDP nametable words at $100000-$1DDFFF (909 KB of ROM). Zero CPU cost at scroll time — pure DMA from ROM to VRAM. This directly validates our approach.

**Our implementation — block-based format:**
- Level editor continues using chunks/blocks for design (unchanged workflow)
- Build pipeline converts chunk layouts into 16×16 tile blocks per section
- Each block contains a 2×2 grid of nametable words (8 bytes) plus embedded collision data
- Blocks are independently S4LZ-compressed in ROM with a 256-entry block index per section
- At level load, block data is decompressed into the 2D tile cache (§4.7) — an 80×60 array in RAM
- Scrolling reads nametable words from the tile cache and writes them to the plane buffer
- `Section_BuildRAMLayout` decompresses block data into the tile cache instead of chunk→block→tile conversion

**ROM cost:** 2-4 KB per section, 16-48 KB per act, ~128-384 KB for 8 acts = 3-10% of a 4 MB ROM.

**Dynamic terrain (breakable floors, moving platforms):** A small per-section runtime override table in RAM. When the scroll engine writes a new column to VRAM, it checks the override table and patches any modified tiles. Override table resets on section transition. Pre-computed nametables handle 99% of tiles; the override table handles the 1% that change.

**Prerequisite:** Deferred plane buffer (4.4) must be in place first — block-based cache data feeds into the buffer infrastructure.

### 4.4 Deferred Plane Buffer (from S.C.E., enhanced)

Producer-consumer pattern: all tile writes are buffered in RAM during the game loop, then flushed to VDP during VBlank. All 5 analyzed commercial games + S.C.E. use this approach — the game loop never touches the VDP data port.

- **Plane_buffer:** 768 words (1536 bytes) in RAM — 40% headroom beyond worst-case diagonal fast-scroll
- **Game loop:** `Draw_TileColumn` / `Draw_TileRow` queue updates into the buffer. Never touch VDP.
- **VBlank:** `VInt_DrawLevel` processes the buffer after DMA queue drain
- **Overflow protection:** Bounds check before each entry. If buffer full, defer to next frame (one frame of missing edge tiles is preferable to memory corruption)
- **Double-update:** When camera moves >16px/frame, auto-queue two column/row updates
- **Dual plane:** Separate pointer for Plane A + Plane B simultaneous updates

**No seam, no redraw during play.** Continuous scrolling never rebases coordinates, so there is no per-section teleport frame and no synchronous full-screen redraw to hide. The VDP plane wrap (§4.1) reuses the 64 nametable cells in hardware as the world camera advances; the edge streamer (§4.7) keeps the leading cells filled. This matches S3K/S.C.E. level wrap, which redraws nothing at a section boundary (`docs/research/teleport-rebase.md`). Per-frame plane work during scroll is just the edge column/row updates the deferred buffer flushes in VBlank — bounded to ≤64 distinct columns by the fill-window clamp (sourced from `Camera_X>>3`).

**`Section_RedrawPlanes` is the level-init draw only** (triggered by `Section_Plane_Dirty`, set once at level init). It writes rows 0-31 of all 64 Plane B columns + 64-column Plane A synchronously via direct VDP pokes with interrupts masked. Both planes are now written column-major (autoinc $80, per-column VDP address, one `move.l` = two vertically-adjacent cells); the mask (`move.w #$2700, sr`) is required because VBlank's `VInt_DrawLevel` repoints the VDP address and resets the autoincrement register to $02, which would corrupt remaining column writes mid-loop. After init, the camera scrolls freely with only edge streaming; there is no recovery redraw on the normal path.

**Per-section parallax snap on boundary crossing.** Sections retain distinct parallax configs (§4.6). The snap that an earlier draft fired on teleport now fires on **section-boundary crossing**: the camera detects a change in `(Camera_X >> SECTION_SIZE_SHIFT)` (or Y) frame-to-frame, looks up the entered section's `sec_parallax_config`, and snaps (vs lerps) the parallax bands. `Parallax_Snap_Pending` is sourced from that boundary-crossing check rather than from a teleport handler.

### 4.5 Camera System (from S.C.E. ExtendedCamera, enhanced)

Port S.C.E.'s `ExtendedCamera` with lookahead panning, then extend with novel features:

**Per-section camera lookahead (NOVEL):** S.C.E. hardcodes ±64px. Our `sec_camera_lookahead` byte makes this per-section: wide-open jungle = 96px, tight cave = 32px, vertical shaft = 0px (vertical-only tracking). The camera reads the current section's value rather than a constant.

**Velocity-adaptive deadzone (NOVEL):** `deadzone_width = base_deadzone + (abs(x_vel) >> shift_factor)`. At high speed, the deadzone widens to show more of what's ahead. At walking speed, tight tracking. No Genesis game adapts the camera deadzone to speed.

**Player-state-dependent speed caps (from S.C.E.):** Different Y-scroll behavior based on player state: ±$20 pixel deadzone at $18 pixels/frame when airborne (prevents jitter during jumps), strict following at $06 pixels/frame on ground (tight tracking), forced positions for cutscene moments.

**Position history buffer (from S.C.E.):** `Pos_table` stores last N frames of player X/Y position. Camera can lag N frames behind via `H_scroll_frame_offset`. Enables whip-effect camera follow at high speed and smooth camera recovery after a forced position move (cutscene, respawn).

**Additional enhancements:**
- Velocity-proportional vertical tracking (faster player = faster vertical camera)
- Dead zone persists for smooth centering

**World-space clamp (continuous scroll).** The camera clamps to the act extent in world coordinates, computed live from the grid dimensions — no preview-zone widening, no slot-map reads, no act-edge special case beyond the extent itself:
```
camera_min_x = 0
camera_max_x = level_width  − SCREEN_W        ; level_width  = grid_w × SECTION_SIZE
camera_min_y = 0
camera_max_y = level_height − SCREEN_H        ; level_height = grid_h × SECTION_SIZE
```
"Seeing into the next section" needs no extended clamp — the edge streamer (§4.7) already fills the leading section's cells into the wrapping plane before the camera reaches them, so the next section is visible the moment it enters the screen without the camera leaving the act. The vertical clamp derives `(Camera_Y >> SECTION_SIZE_SHIFT)` against `0`/`grid_h` rather than reading any slot map.

**Per-act vertical edge behavior (`Act_edge_mode`).** The bottom/top vertical edge is configurable per act, not a fixed clamp (Phase 2 §10):
- **`EDGE_CLAMP`** (default, OJZ ships this) — camera + player stop at the world floor `level_height − SCREEN_H`, exactly the clamp above.
- **`EDGE_WRAP_V`** (fall-forever) — crossing the bottom wraps `Y` by `level_height` (plane-aligned → seamless). **Deferred hook** (dispatch + design in place, stubbed to clamp); the real wrap needs the camera clamp to become edge-mode-aware and a camera-triggered atomic live-set shift — full design in the spec §10.
- **`EDGE_KILL`** (death pit) — sets `Player_Death_Pending` and clamps meanwhile; wired to the death system when it exists. **Deferred hook.**

The dispatch lives in `Player_LevelBound` (bottom guard); `EDGE_CLAMP` is byte-for-byte the original clamp.

### 4.6 Multi-Band Computed Parallax — As Shipped

> **AUTHORING CHANGED 2026-08-18 (Scanline Services P1). The RUNTIME below did not.**
> Everything in this section still describes exactly what executes — P1 made no runtime
> change, and its gate was that all four ROM images stayed byte-for-byte identical. What
> changed is where the records come from.
>
> - **`engine/level/scene_dsl.emp`** holds the authored vocabulary: `layer()` / `scene()`
>   constructors, payload-carrying attachment enums (`SceneDeform`, `SceneVDeform`,
>   `SceneAnchor`), the capability fold, and the comptime lowering to the SAME
>   `parallax_config` / `band_entry` records described below. Pure comptime; emits nothing.
> - **`games/sonic4/data/effects/ojz_scenes.emp`** authors the 20 scenes and **emits zero
>   bytes**.
> - **`games/sonic4/data/effects/scene_registry.emp`** is the SOLE emission path — a scene
>   not listed in its `SCENES` emits nothing and its section reference fails at link. It
>   also holds the capability fold and the ensure verifying it against
>   `Game.SCANLINE_CAPS` (subset form: folded ⊆ declared).
> - **`games/sonic4/data/parallax/` is DELETED.** Its `hdr()` / `cfg_band()` constructors
>   survive ONLY as the test-only oracle in `games/sonic4/test/scene_equiv_proof.emp`, the
>   permanent witness proving all 20 headers, 67 bands and 6 tables lower to the shipped
>   values.
> - **A parallax config is now a LOWERED ARTIFACT, not an authored one.** Do not hand-write
>   one; author a scene. The record layout documented below is the lowering TARGET and stays
>   authoritative for the runtime.
> - **Emission ORDER is load-bearing and non-obvious:** the shipped block INTERLEAVES deform
>   tables with the records that attach them, and an `.emp` section is contiguous per module,
>   so the tables live in the registry beside the records. Grouping them elsewhere moves every
>   table address and rewrites `pcfg_deform_table_*` inside all 20 records.
> - Two `_raw` fields on `Scene` (`layer_mask_raw`, `v_deform_shift_raw`) are **byte-identity
>   bridges**, not features — see DEFERRED_WORK before normalizing either.
>
> Spec: `docs/superpowers/specs/2026-08-17-scanline-services-design.md` (§2, §3).
> Evidence: `docs/benchmarks/scanline-p1/GATE-EVIDENCE.md`.

**Foundation:** S.C.E.'s `HScroll_Deform` deformation script extended with TF4's per-band model. Replaces per-zone hardcoded scroll routines with a data-driven system that auto-selects mode per section, supports per-band gradients, and lerps smoothly across section boundaries.

**Multiply-free shift-add factor encoding.** Each band has a `factor_a` (FG) and `factor_b` (BG) packed into 24 bits: `s1` (4 bits, 0..14 = shift; 15 = "term zero"), `s2` (4 bits, same semantics), `op` (1 bit: 0 = ADD second term, 1 = SUB). Scroll = `(camX >> s1) op (camX >> s2)` per term — pure shift+add, no `muls`. Pre-defined factors: `FACTOR_0` (locked), `FACTOR_1`, `FACTOR_1_2`, `FACTOR_1_4`, `FACTOR_1_8`, `FACTOR_1_16`, `FACTOR_3_4`, `FACTOR_3_8`, `FACTOR_3_16`, `FACTOR_5_8`, `FACTOR_5_16`, `FACTOR_7_8`, `FACTOR_7_16`, `FACTOR_15_16`. New factors added by composing two shifts.

**Per-band Plane A + Plane B factor split.** Each band carries independent FG and BG factors. Plane A's "ground" band typically uses `FACTOR_1` (1:1 with camera); Plane B layers progressively slower (`FACTOR_1_4` mountains, `FACTOR_1_8` clouds). Gives each Y-region its own scroll rate.

**Per-band amplitude shift + phase offset.** `BAND_DSA` / `BAND_DSB` (per-band shift on FG/BG deform sample, set before each `band` macro call) downscale the deform amplitude per band — clouds full-amplitude, hills faint, ground none. Sentinel value `15` skips the sample entirely. `BAND_PHASE` desyncs each band's wave from neighbours so they don't pulse in lockstep.

**FG / BG H-deformation tables (256-byte signed sine/triangle/custom, sampled per line).** When `pcfg_deform_table_fg` and/or `pcfg_deform_table_bg` are non-NULL, the pipeline auto-selects per-line HScroll mode and samples the table at `(phase + band_phase + line) & $FF` per scanline, downscaled by the band's shift, added to the band's base scroll. Phase advances by `pcfg_deform_speed_fg/bg` per frame. Generators in `engine/parallax_macros.inc`: `deform_table_sine`, `deform_table_triangle`, `v_column_perspective`.

**Vertical parallax (whole-plane and per-column).** Whole-plane: `pcfg_v_factor_bg` shift + `pcfg_v_center_y` + `pcfg_v_offset` produce `target_b = ((camY - vCenter) >> v_factor_bg) + vOffset`, lerped each frame. Sentinel `v_factor_bg = 15` locks BG vscroll to `vOffset` (camera-Y-independent). Per-column: when `pcfg_v_deform_table_bg` is non-NULL, mode bit 2 enables per-column VSRAM; the pipeline samples 20 column-pairs from the table each frame, shift-scaled by `pcfg_v_deform_shift_bg`, animated by `pcfg_v_deform_speed_bg`.

**Section transition smoothing (16-frame lerp) — plane B only.** `Parallax_StartTransition` stages `Parallax_Target_Config` and sets `Parallax_Transition_Frames = 16` when entering a new section's config. `Parallax_Update` uses Target_Config to compute band targets; the per-band scroll lerp (`>>4`) eases the **plane B** values toward them only while `Transition_Frames > 0` — outside transitions every band locks exactly to its decoded target. **Plane A is never lerped under any circumstance** (fixed 2026-06-10): the FG streaming engine draws columns in a camera-anchored 64-col wrap window, so any FG scroll offset from the camera drags the plane-wrap seam into view at the screen edge. The original always-on lerp trailed the camera by ~15 × velocity (≈240 px at 16 px/frame), painting "content from 512 px ahead" over the visible left edge during rightward scroll. `pcfg_transition = 1` overrides smooth → instant snap (additionally sets `Parallax_Snap_Pending` so plane B values jump to targets without lerp). `Parallax_Snap_Pending` is also set automatically when the camera crosses a section boundary (a change in `Camera_X/Y >> SECTION_SIZE_SHIFT`) into a section whose config demands an immediate change — the 16-frame lerp still applies for ordinary continuous crossings.

**Per-cell vs per-line auto-mode.** `Parallax_Update` checks both H-deform tables. Both NULL → per-cell HScroll (28 entries × 4 bytes = 112-byte DMA), no per-line wave possible. Either non-NULL → per-line HScroll (224 entries × 4 bytes = 896-byte DMA). **A world-anchored overlay (below) also forces per-line**, because an anchored boundary lands on an arbitrary scanline and per-cell can only place a cell edge. That key has a TWIN in `engine/buffers` choosing the DMA length off the same fields; the two must change together or a mode-differing config ships a cell-length DMA for a line-mode buffer. VDP register `$0B` mode bit set accordingly via shadow + dirty flag during `Parallax_StartTransition`.

**World-anchored deform overlay (Parcel W, 2026-08-15).** A palette boundary and a shimmer boundary can be driven by ONE act-space anchor and land on the same scanline. `pcfg_anchor_ch` names a patch channel (`PARALLAX_ANCHOR_NONE` = `$FF` for none) and `pcfg_anchor_dsa/dsb` the deform shifts to apply below it; all three come from the config's former pad bytes, so the feature costs **zero bytes** and `sizeof(parallax_config)` stays 28 (required — `copy_band_entry` ensures it stays even).

Each frame, after Step 4a's rotation, `L = Effects_World_Y[ch] − Camera_Y` is clamped to the channel's own raster band and to `[0,224]`; the shadow band containing `L` is **split** there, and every band from the split down has its deform shifts overridden. It is an **additive overlay, not a terminal band**: bands keep their own scroll factors, so multi-strata background structure below a water surface survives instead of collapsing onto one factor. `L ≤ 0` splits at line 0 and overrides every band — S3K's `Water_full_screen_flag` state reached structurally rather than as a special case; `L ≥ 224` leaves the view untouched.

- **The clamp is one fact.** `Raster_GetChannelBand(ch)` reads the band words out of the patch table P-a emits, so changing `patchable`'s band moves both boundaries' clamp with no second author action. `Raster_Patch_Tab == 0` (an anchored section with no patched program) means there is no palette boundary to diverge from, so no clamp is applied — `[0,224]` is correct there.
- **Wave PHASE is untouched.** Band top and phase are separate quantities in separate registers (`d5` vs `d2`/`d6`), which is why anchoring a boundary to the camera cannot re-open the layer-anchoring fix below.
- **Shadow band tops measure in SCREEN LINES**, not cells (ROM entries keep cell rows; Step 4a's rebase converts). This is what makes the boundary scanline-exact, and it is why the flat band fill carries a remainder tail — its 8× unroll previously assumed every span was a multiple of 8, which an arbitrary split line breaks.

**Layer enable mask.** `pcfg_layer_mask` disables individual bands; a disabled band's **BG** scroll inherits the previous band's value (or zero if first band, = locked). The **FG** word of a disabled band stays hard-locked to -Camera_X — the inheritance seed is -camX, never zero — because the FG streaming engine draws a camera-anchored 64-col window and any FG scroll offset drags the plane-wrap seam into view (bug found 2026-06-11: zero-seeded FG froze Plane A's top 32 lines under LockedClouds). `LAYER_MASK = $1E` locks the cloud band while mountains/hills/ground continue scrolling.

**RAM footprint:** `Parallax_State` ≈ 126 B in `$FF000000`-range RAM:
- `Parallax_Deform_Phase_FG/BG/V_BG` (3 × ds.w 1 = 6 B)
- `Parallax_Current_Scroll_A/B[8 bands]` (2 × 16 = 32 B)
- `Parallax_Current_Vscroll_BG` (2 B)
- `Parallax_Current_Config / Target_Config` (8 B pointers)
- `Parallax_Transition_Frames / Snap_Pending` (2 B)
- `Parallax_Vscroll_Column_Buf` (80 B for 20 VSRAM column-pairs)

**ROM cost per section:** 28-byte `parallax_config` header + 10-byte `band_entry` per band (the world-anchored overlay added no bytes — it claimed the header's three spare pad bytes). 5-band default = 78 B per section. Deform tables (256 B each) are shared across sections that use the same wave shape.

**Effects library (`games/sonic4/data/parallax/configs.emp` — the single file that replaced the old `effects/` + `scenes/` dirs):** reusable single-effect building blocks as parameterised comptime constructors — `shimmer_bg` (subtle H-wobble), `haze_fg` (graduated H-wobble — heaviest at bottom, with optional uniform mode), `rocking` (per-column V-scroll rocking), `perspective` — each with pre-named `_Slow / default / _Fast` (etc.) `ParallaxConfig_*` variants. The generic constructors (`band`, deform-table generators) live engine-side in `engine/level/parallax_dsl.emp`.

**Composite scenes (same file):** hand-authored configs that mix multiple effects with custom per-band gradients. `ParallaxConfig_WindyHaze` (windy gradient BG + uniform FG haze), `ParallaxConfig_SkyHaze` (split-screen — windy top, haze bottom), `ParallaxConfig_OJZ_Caves` (slow BG factor gradient), `ParallaxConfig_OJZ_LockedClouds` (layer-mask demo).

**Composition macros in `parallax_macros.inc`:**
- `parallax_section` — workhorse, emits a complete config record from named keyword params.
- `parallax_combine` — sugar for stacking up to three deform tables (FG H, BG H, BG per-column V) in one single-band config.
- `parallax_combine_split` — 2-band variant with `PARALLAX_TOP / PARALLAX_BOTTOM / PARALLAX_ALL` bitmask `*Where` params for regional effect placement.

**Performance:** ~410 NTSC cycles per frame for 5-band per-cell pure shift-add (no deform sampling). Per-line mode adds ~2× (~800 cycles for 224-line fill with deform sampling). Cheaper than processing two objects.

**Foundation:** S.C.E.'s `HScroll_Deform` deformation script, extended with shift-add factor encoding (novel), per-band amplitude/phase split (novel), and section-boundary lerp transitions (novel).

### 4.7 Level Collision — Block-Embedded Collision + 2D Tile Cache

**Collision is embedded in block data.** Each 16×16 block in the tile cache carries its collision type alongside its 2×2 nametable words. The 2D tile cache stores nametable and collision data in separate parallel arrays (80 cols × 60 rows), enabling direct indexed access to either layer.

**2D Tile Cache:** The tile cache is an 80-column × 60-row linear array in RAM, covering the viewport plus margins (20 columns each side, 16 rows above/below). Two parallel arrays:
- **Nametable array** (80 × 60 × 2 bytes = 9,600 bytes): VDP nametable words, one per 8×8 tile
- **Collision array** (2 planes × 80 × 30 × 1 byte = 4,800 bytes): collision type bytes, one per 8px-wide × 16px-tall cell per layer — 80 tile columns × 30 collision rows; the two 8px columns of a 16×16 block carry the same byte (loop path A at +0, path B at +TILE_CACHE_COLL_SIZE; objects select via `SST_layer`)

The linear layout enables direct 2D indexing: `cache[col + row * 80]` with both axes circular. Columns slide via `Cache_Origin_Col`, rows via `Cache_Origin_Row` (added 2026-06-10 — replaced the `TileCache_VSlide`/`VSlideUp` memmoves, which cost ~87k cycles per 2-row evict and lagged hard under sustained vertical scroll). Eviction in both axes is O(1) origin arithmetic; the recycled physical rows are overwritten by `TileCache_FillRow` before they can become visible, same validity contract the memmove had. Physical position = `(logical + origin) mod size`. Consumers that walk rows down a column (`TileCache_CopyBlockColumn`, `Draw_TileColumn`, `Section_RedrawPlanes`) carry an end-of-buffer sentinel in an address register and subtract the buffer size on crossing (~16 cycles per row walked); single-row consumers (`Tile_Cache_GetTile`/`GetCollision`, `TileCache_FillRow`, `Draw_TileRow_FromCache`) just remap the row index. **`Cache_Top_Row` and `Cache_Origin_Row` are always even**: init/reinit round down, vertical eviction and upward extension step by 2 tile rows. This keeps 16px collision cells aligned with world block data — and makes `physical_row / 2` exactly the physical collision row, so the collision array shares the same origin. An odd top row would skew every collision lookup by half a cell.

**Cache fill (as shipped, 2026-06-10):**
- **Block staging cache:** decompressed 16×16-tile blocks land in a 12-slot staging cache (`Block_Stage_Buffers`, 768 bytes/slot — 512 nametable + 2×128 collision planes (path A/B, added 2026-06-10), keyed by packed sec_x|sec_y|block_index, round-robin evict). Column fills cross 4–5 blocks vertically and row fills cross 6 horizontally; without staging, each block would be re-decompressed up to 16 times as the cache slides across it (~94% redundant work). 12 slots let a column fill and a row fill coexist on diagonal scroll.
- **Per-frame decompress budget:** `TileCache_FillColumn` AND `TileCache_FillRow` draw from a shared frame allowance (`BLOCK_DECOMP_BUDGET` = 6 blocks, reset in `Tile_Cache_Fill`). Steady-state horizontal scroll costs ~0.3 decompresses per column (staging absorbs the rest); a cold block-column burst (≤5) fits in one frame's budget. Rows additionally cap at `VFILL_ROWS_PER_FRAME` = 2 per frame with their own partial-resume (`Cache_Fill_RowResume_Row/Col`). **Leftover budget drives a unified direction-aware prefetch** (2026-07-16), ordered row → col → corner: the vertical scan stages the next block-row's first unstaged block (k=1, direction from `Cache_Prev_Cam_Row`); a mirrored 90° column scan stages the next block-column (direction latched with `H_PFX_HYST` = 16 px hysteresis against seam-dither, `Cache_H_Pfx_Dir`); and when both axes are crossing, the (next-row × next-col) corner block is staged last. Staging is 16 slots (`BLOCK_STAGE_SLOTS`, raised from 12 by the lap-rate model so the row+col+corner live set survives a diagonal double-crossing). The prefetch tail is gated by a **trailing-lag indicator** — `Tile_Cache_Fill` runs in VBlank (V≈240) where the beam can't gauge load, so it skips speculation on the frame after a lag (`Frame_Counter` delta > 1), bounded to ≤1 consecutive skip; demand fill is never gated. A/B: this cut sustained-max-horizontal lag ~40% (44→27 frames) and sustained-max-diagonal ~76%→~42%; the residual is copy/draw-bound (the "horizontal Wave-1", ledgered). **The vertical contract is structural:** `Camera_Update` clamps Y movement to `CAM_MAX_Y_STEP` = 16 px/frame (S2's number — S3K uses 24) so the fill can never fall behind; the binding constraint is the VBLANK window, not CPU: each filled row adds a 64-word plane-buffer entry to the VBlank drain, and >2 rows/frame overflows VBlank into FIFO-throttled active display (measured 2026-06-10: 4 rows/frame cost +15 lag frames per 512px descent; 2 rows/frame costs +4).
- **Keyed partial resume:** a budget-out stores `Cache_Fill_Resume_Col/Row`; the next frame finishes that exact column before extending either edge. Both edges commit their bound *before* filling, so at most one partial is ever outstanding and a budget-out simply ends column work for the frame.
- **FillRow copies collision too:** the odd row of each 16px cell (cell-completing row, well-defined because Top is even) writes the cell's collision byte alongside the nametable words. **Collision-row-base addressing convention** (`tile_cache.asm`, the `collSrcRowBase`/`collDstRowOfs` macros): the collision row base within a staged block is `slot + BLOCK_NT_SIZE + (intra_row/2)*BLOCK_COLL_COLS` — the `/2` (parity-safe) is mandatory. The even-only `intra_row*8` shortcut is a TRAP: it lands 64px off on odd intra-rows. This bit a real loop-arc bug (the §5 FillRow fix, d1637c8; macro-hardened in c17132d so future cache/cache-prefetch work can't reintroduce it). The even-row shortcut precondition is exactly that `Cache_Top_Row`/`Cache_Origin_Row` stay even.

**Runtime collision lookup** reads directly from the tile cache in world coordinates — no separate collision maps, no per-section decompression, no coordinate translation. The tile cache already has the data:
```asm
; Collision lookup from tile cache
; d0.w = engine X pixels, d1.w = Y pixels
    lsr.w   #3, d0                      ; X pixels → tile col (8px columns)
    lsr.w   #3, d1                      ; Y pixels → tile row (GetCollision halves to 16px collision rows)
    bsr.w   Tile_Cache_GetCollision     ; d0.b = collision type byte
```

**Collision type byte:** Indexes into height maps and angle arrays. The byte IS the collision ID — no further indirection. Embedded in the block data by the build tool (S.C.E./S3K-style: collision is a property of placement, not a separate data structure).

**Floor distance formula** (S.C.E. convention): `distance = 16 - height - sub_cell_Y`, where `sub_cell_Y = Y_pixels & $F` and `height` is the height map value (0-16) at `(collision_type × 16) + (X_pixels & $F)`. Negative distance = embedded in solid (snap up), zero = on surface, positive = gap below foot.

**Dual-sensor system** (unchanged from S.C.E./S3K):
- **Two floor sensors** (left/right foot) positioned at `x_pos ± width_pixels/2, y_pos + height_pixels/2`
- **Height maps** in ROM: `HeightMaps` (vertical collision) + `HeightMapsRot` (wall sensors)
- **Angle arrays:** Pre-computed terrain angles indexed by collision ID
- **Height map indexing:** `(collision_type × 16) + (x_pixel & 0xF)` — single-cycle lookup

**Build tool embeds collision in blocks — fresh-start, editor-authoritative (current, since the 2026-07-02 editor-collision-authoring design):** Level collision starts from an **all-air baseline** and is **overlaid entirely by the editor**, not derived from sonic_hack's donor layout. `tools/ojz_strip_gen.py`'s `generate()` seeds every section's collision grids to air (`air_col`), then `apply_editor_collision_overlay` reads Aurora's `games/sonic4/data/editor/ojz/act1/section_N.collattr.bin` (path A) / `.collattrb.bin` (path B) — 16-bit big-endian cell words, one per 8px tile column × 16px collision row, WYSIWYG with what the editor shows — and bakes each painted cell via `collision_pipeline.bake_plane_cell` against the imported **S&K shape/height/angle vocabulary** (`data/collision/base/`, written by `tools/import_sk_collision.py`) into a shared **sparse interned attr-set** (one byte per unique shape+flip+solidity combo actually painted — 13/255 slots used today, ~242 headroom). The matching ROM tables (`HeightMaps`/`HeightMapsRot`/`AngleTable`/`SolidityTable`, BINCLUDEd from `games/sonic4/data/collision/`) are emitted from that same attr-set, so only combos the level author actually placed reach the ROM. A section with no `.collattr.bin` keeps its air baseline; there is no silent fallback to legacy donor data — `require_donor()`/`editor_data_available()` fail the build loudly instead (the "row-178 hole" postmortem). The older sonic_hack-donor bake (`ojz_strip_gen.build_section_collision` / `collision_pipeline.bake_cell`, driven by `PATH_A_SOL_SHIFT`/`PATH_B_SOL_SHIFT` chunk-entry bits and the VDP-priority-bit placeholder) still exists in the tree but only as a test/fallback path (`test_section_collision_sec0`), not the live production pipeline. Aurora's chunks/stamps/map-clipboard (design #6, 2026-08-08) author both collision planes directly and travel with reused content atomically — editor FG art and editor collision are both first-class, editor-authored inputs now (see `docs/DEFERRED_WORK.md` "Path-B collision content" for the full history).

**Why embedded over separate maps:** S.C.E./S3K embed collision indices directly in their block mapping words. Our block format adapts this by storing collision bytes alongside nametable words in the tile cache. Benefits: no separate per-section collision files, no collision map RAM, no separate collision decompression step (collision streams alongside nametable data at the edge), collision is inherently tied to position (same visual tile can have different collision in different placements). The collision array adds ~4.8 KB RAM but eliminates all runtime collision map management.

### 4.8 Section Streaming Integration

Continuous scrolling makes "streaming" a steady per-frame edge process rather than a per-section event. The section system still touches nearly every other engine system; these are the integration points, all keyed off the world camera:

**Section + tile cache + DMA Queue (the edge streamer):**
- The tile cache (§4.7) streams the leading section's nametable + collision into the wrapping plane as the camera advances — every moving frame, not in bursts at a boundary
- Edge column/row writes accumulate in the deferred plane buffer (§4.4) and flush via the DMA queue in VBlank
- **Two-tier priority:** object art → Priority 1 (important, immediate); the per-frame edge nametable/collision fill is bounded by the tile cache's own 6-block / 2-row budget (§4.7), so it never needs to be queued ahead — there is no "preload phase" to schedule
- The block staging cache absorbs cold blocks as the camera crosses block boundaries; on direction reversal the cache simply streams the now-leading edge — no bookmark to reset, no preload to abort

**Section + VRAM Allocator (2.2):**
- The whole act's tile art is resident in the VRAM art pool (loaded once at `Level_LoadArt`; §2 A.3 — build-time global deduplication + spatial ordering + paging), so there is no per-section art swap and no nametable preload window. Section transitions move only the camera; the tiles the leading section references are already in VRAM
- Object art: `AllocVRAM` allocates as objects spawn at the camera edge (§4.9); `FreeVRAM` decrements refcounts as they despawn — art stays cached for short backtracks. (When a future level exceeds the resident art budget, §4.11's continuous model is the foundation a windowed art-residency streamer builds on — see DEFERRED_WORK; it does not reintroduce slots.)

**Camera-Driven Entity Window (4.9):**
- The window tracks exactly the 2×2 sections overlapped by the camera's despawn envelope — visibility-derived, anchored on `(Camera >> SECTION_SIZE_SHIFT)`
- Slides (the envelope crossing a section boundary) migrate surviving masks by section identity; newly entered sections populate from their section-local ROM lists
- "Seeing ahead" is intrinsic: the envelope reaches into the section ahead of the camera as it scrolls, so entities spawn before they reach the screen — no teleport, no separate preview pass
- Section-local ROM entity data (positions relative to the section, §4.9.1/4.9.2) and section_id-keyed respawn/kill memory (§4.9.5) are coordinate-invariant — large levels and the future floating-origin rebase never touch the static section data

**Section + Parallax (4.6):**
- Each section's `sec_parallax_config` loads a new config when the camera crosses into the section (a change in `Camera >> SECTION_SIZE_SHIFT`); the 16-frame lerp eases ordinary crossings, `pcfg_transition`/`Parallax_Snap_Pending` forces an instant snap when the config demands it
- Different sections in the same zone can have different parallax (outdoor → cave → underwater)
- Layer enable mask disables unused layers per section (saves cycles + DMA)

**Animated Terrain Per-Section (NOVEL — PLANNED, not implemented):**
Each section could define its own animated tile set via `sec_anim_blocks` — conveyor belts, pulsing lava, swaying grass, shimmering ice — cycled and DMA'd via the DMA queue (Priority 1), with the entered section's set starting and the exited one's stopping at each boundary crossing. **Status:** `sec_anim_blocks` is a reserved descriptor field with no runtime consumer (see the §7 banner). What ships today is *act-level* BG tile-band animation — `BgAnim` (`engine/level/bg_anim.emp`), driven by the act-wide `BgAnim_Table`, not per-section scripts. See DEFERRED_WORK.md "Animated Tile DMA Scripts" for the design backlog entry.

**Section State Preservation via Visibility Window:**
The visibility-derived window preserves entity state for sections inside the 2×2 tracked window naturally — mask bits carry over by section identity at every slide. Collected rings stay collected, destroyed objects stay gone, as long as the section remains tracked. Once a section leaves the window, revisiting loads from ROM defaults — matching classic Sonic behavior where distant areas respawn. The 3×3 rolling collected bitmask (4.9.5), keyed by section_id, extends this to ±1 section of backtrack regardless of where the camera is in world space.

**Transition / Blend Sections (NOVEL — PLANNED, not implemented):**
Transition cells in the grid would interpolate between adjacent sections' palettes, parallax, and physics across the cell's width. Jungle gradually darkens into cave, water tint deepens as you descend, wind picks up as you climb. Creates seamless geographic flow instead of hard boundaries — the continuous camera makes the blend a function of world position within the cell rather than a discrete event. **Status:** only the parallax leg exists (per-section `sec_parallax_config` with the 16-frame lerp, above). No palette-transition code ships — `sec_pal` has no runtime consumer and palette cross-fade is design-stage (§7.1 and the §7 banner; see also DEFERRED_WORK.md "Palette transition on section crossing"); the physics leg is the deferred modifier half of §5.2 (DEFERRED_WORK.md §5).

**Streaming During Cutscenes:**
During boss deaths, story sequences, or triggered animations the camera is usually still, so the edge streamer is idle and the DMA queue has spare capacity. There is no per-section art preload to run (art is resident); cutscene time is instead free budget for effects and audio work.

### 4.9 Camera-Driven Entity Management

Entities (rings and objects) load when they scroll into camera range and despawn when they leave — a continuous, camera-driven process with no bulk load step. Per-section X-sorted ROM lists with per-section scan pointers enable early-exit scanning — only entities near the camera edge are checked each frame.

**Why separate rings from objects:** Rings are high-volume (40-50 per section), stateless (no behavior code), and need only collision + rendering. Objects are lower-volume (10-20), stateful (SST slots with behavior routines), and diverse. Segregated pools with type-specific fast paths outperform unified processing.

#### 4.9.1 Ring Layout — Flat X-Sorted, Section-Local

Ring data in ROM per-section, flat `dc.w X, dc.w Y` pairs in section-local coordinates, X-sorted ascending, terminated by `dc.l 0`:

```
OJZ_Sec0_Rings:
    dc.w    $080, $060      ; ring 0
    dc.w    $090, $060      ; ring 1
    dc.w    $0A0, $060      ; ring 2
    dc.l    0               ; terminator
```

No pattern encoding — rings are pre-expanded at build time. Flat lists eliminate per-frame decode overhead and enable binary/linear scanning with early exit. The X-sorted order means once a ring's world-space X (section origin + section-local X) exceeds the camera's load edge, all subsequent entries are also out of range.

#### 4.9.2 Object Layout — 6-Byte v2 Entries with Per-Section Type Table

Object entries in ROM use full-resolution section-local coordinates with a local type index, X-sorted ascending, terminated by `dc.w -1`:

```
; 6-byte entry: dc.w x, y, flags|type|subtype
;   x.w, y.w:  section-local ($000-$7FF; X bit 15 reserved as terminator)
;   word 3:    bit 15 = OEF_ANY_Y (spawn regardless of camera Y — phase 2)
;              bit 14 = OEF_YFLIP, bit 13 = OEF_XFLIP (rol.w #4 → RF bits in Load_Object)
;              bits 12-8 = type (0-31, OEF_TYPE_SHIFT/OEF_TYPE_MASK)
;              bits 7-0  = subtype (OEF_SUBTYPE_MASK)
```

Hand-authored lists use the `objentry`/`objend` helpers (`engine/structs.emp`), which build-fail on non-monotonic X, out-of-range coordinates, type/subtype overflow, and lists exceeding `MAX_LIST_ENTRIES` (128 — the killed-bitmask capacity):

```
OJZ_Sec2_Objects:
    objentry $100, $0B0, 1      ; x, y, type [, subtype] [, oflags]
    objentry $300, $060, 0
    objend                      ; emits dc.w -1 terminator, resets guards
```

Each section defines a count-prefixed type table in ROM:

```
OJZ_Sec0_TypeTable:
    dc.b    2, 0                ; count, pad byte
    dc.l    ObjDef_Static       ; type 0
    dc.l    ObjDef_Solid        ; type 1
```

Object spawning reads the 6-byte entry, indexes the ROM type table for the ObjDef pointer (one indexed `move.l`), and passes the flags/type/subtype word to `Load_Object`, which patches subtype and rotates the flip bits into render_flags/status. The 5-bit type index means each section independently uses up to 32 object types with no global ID space.

**`OEF_ANY_Y` semantics (shipped with the vertical window):** an ANY_Y object spawns whenever the camera's X window reaches it, regardless of camera Y, and is exempt from Y despawn (X despawn and section-tracking despawn still apply — when its section leaves the 2×2 window the object goes with it, and respawns when the section is re-tracked). The flag persists past spawn time as **bit 7 of `SST_slot_tag`** (low bits = entry index 0-3): the per-frame Y despawner tests that bit instead of re-reading ROM. Use it for vertical-corridor hazards, elevators, and anything whose behavior spans a section's full height.

#### 4.9.3 Entity Window — Visibility-Derived 2×2 Lifecycle

The entity window tracks the **2×2 sections overlapped by the camera's despawn envelope** in world space. The despawn envelope spans 320+2×$200=1344px (X) and 224+2×$180=976px (Y), both less than `SECTION_SIZE` ($800), so the envelope always overlaps exactly 2 columns × 2 rows regardless of camera position.

**Envelope anchor derivation (`EntityWindow_DeriveWindow`).** Everything is world-space — the anchor section is a direct shift of the world camera, with no slot map and no origin bias:

```
sec_x0 = (camX − ENTITY_DESPAWN_BUFFER)   asr SECTION_SIZE_SHIFT
sec_y0 = (camY − ENTITY_DESPAWN_BUFFER_Y) asr SECTION_SIZE_SHIFT
window  : sections (sec_x0+{0,1}, sec_y0+{0,1})    entries 0=UL 1=UR 2=LL 3=LR
origins : x = (sec_x0+{0,1}) · SECTION_SIZE       ; section's world X origin
          y = (sec_y0+{0,1}) · SECTION_SIZE       ; section's world Y origin
```

`Entity_Window_Anchor` (2 bytes RAM) stores `(sec_x0, sec_y0)` — the slide trigger reads it. A section's world origin (`sec · SECTION_SIZE`) is fixed for the whole act, so an entity's world position = `section_origin + section_local_coord` is computed once at spawn and never re-expressed during play (positions only ever shift in the future floating-origin rebase, §4.11, which moves the whole live set uniformly).

Continuous scrolling has no teleport, so the anchor simply tracks the camera: when the camera scrolls one `SECTION_SIZE` forward, `sec_x0` increments by 1 and the window slides one column — a single slide event (§below), not an instantaneous swap of a section pair.

`EntityWindow_BuildEntries` calls `DeriveWindow`, stores the anchor, and fills each entry's `EntityScanState` ($1A bytes):

```
EntityScanState struct ($1A bytes):
    ess_ring_right_idx   ds.w 1      ; next unloaded ring index (right scan)
    ess_ring_left_idx    ds.w 1      ; next unloaded ring index (left scan)
    ess_obj_right_idx    ds.w 1      ; next unloaded object index (right scan)
    ess_obj_left_idx     ds.w 1      ; next unloaded object index (left scan)
    ess_rom_ring_ptr     ds.l 1      ; pointer to section's ROM ring list
    ess_rom_obj_ptr      ds.l 1      ; pointer to section's ROM object list
    ess_rom_type_tbl_ptr ds.l 1      ; pointer to section's ROM type table
    ess_origin_x         ds.w 1      ; section's world-space X origin (sec_x · SECTION_SIZE)
    ess_section_id       ds.b 1      ; section flat grid id, or SEC_VOID
    ess_entry_idx        ds.b 1      ; entry index 0-3 (loaded-mask base derives from it)
    ess_origin_y         ds.w 1      ; section's world-space Y origin (per-entry — rows differ)
```

**Validity mask + SEC_VOID:** entries whose section falls outside the act grid (right edge on odd-width grids, bottom rows when `sec_y+1 ≥ grid_h`) are stamped `ess_section_id = SEC_VOID` ($FF) and their bit cleared in `Entity_Window_Active` (bit n = entry n valid). The void stamp is load-bearing: despawn paths read entry ids unconditionally, and a stale id would keep dead-section survivors alive forever. All scan/populate loops skip inactive entries.

**Per-frame scan (`EntityWindow_Scan`):**

```
For each ACTIVE entry (Entity_Window_Active bit set):
  1. ScanRingsRight: advance the ring index through the X-sorted ROM list
     (a right-edge RATCHET — there is no left scan: tracked sections never
     X-despawn their entities, so leftward camera motion needs no re-load)
     - Convert section-local X/Y to world space (add ess_origin_x/y)
     - If world X > camera right load edge: stop (X-sorted early exit)
     - Skip if outside the camera Y band (below)
     - Check Collected_CheckRing bitmask: skip if already collected
     - Check + set the entry's loaded-ring bit: skip if already loaded
     - Add to unified Ring_Buffer via RingBuffer_Add
  2. ScanObjectsRight: same shape for 6-byte object entries
     - OEF_ANY_Y entries bypass the Y band test
     - Check + set loaded-object bit; Load_Object; tag SST_slot_tag with
       entry index (bit 7 = ANY_Y mirror)

Vertical re-scan (EntityWindow_RescanY): when camY & ENTITY_RESCAN_COARSE_MASK
  changes (one 128px coarse row crossed), re-walk each active entry's ROM lists
  from index 0 up to the X ratchet (right_idx), spawning entries that the new
  Y band now covers. Loaded bits make this idempotent — already-loaded
  entities are one btst+skip.

After all entries:
  3. DespawnRings: backward iterate Ring_Buffer, remove entries outside the
     X keep range OR the Y despawn band; clear the loaded-ring bit
     (clearLoadedRing) before swap-with-last removal
  4. DespawnObjects: scan Dynamic_Slots, delete tagged objects outside range
     (ANY_Y objects exempt from the Y test); clear loaded-object bit
     (clearLoadedObj) before DeleteObject
```

**Y band + hysteresis:** entities load inside `[camY − ENTITY_LOAD_BUFFER_Y, camY + SCREEN_HEIGHT + ENTITY_LOAD_BUFFER_Y]` ($100) and despawn outside `[camY − ENTITY_DESPAWN_BUFFER_Y, camY + SCREEN_HEIGHT + ENTITY_DESPAWN_BUFFER_Y]` ($180). This mirrors the X hysteresis (load $180 / despawn $200 past the screen edge): the gap prevents load/despawn oscillation at band edges. Two build-time `ensure()` guards in `engine/objects/entity_window.emp` enforce the band invariants (the constants themselves live in `engine/system/constants.emp`):

```
(ENTITY_DESPAWN_BUFFER_Y - ENTITY_LOAD_BUFFER_Y) >= coarse row size (128)
    ; else hysteresis < re-scan granularity -> edge oscillation returns
ENTITY_LOAD_BUFFER_Y >= coarse row size (128)
    ; else a re-scan fired up to 127px ago can leave a gap inside the
    ;   nominal band -> vertical re-scan can skip entities
```

(Consequence of the coarse trigger: the *guaranteed* load margin is `ENTITY_LOAD_BUFFER_Y − 128` past the screen edge, since the last re-scan may have fired up to one coarse row away. Verified on hardware: a ring 240px above the camera stays unloaded until the next crossing — by design.)

**Loaded bitmasks (idempotent spawns):** `Entity_Loaded_Masks` holds 4 entries × 32 bytes (16B ring bits + 16B object bits, indexed by ROM list position). A bit is set at spawn and cleared at despawn. This is what makes every overlapping spawn path safe to re-run: the vertical re-scan, slide rebuilds, and the X-ratchet scans can all visit the same ROM entry without double-spawning. `EntityWindow_InitSection` compare-clears an entry's mask slot only when its `section_id` changes, so an unchanged section keeps its bits across rebuilds. The `Entity_Mask_Scratch` buffer (4+128 bytes RAM) holds a snapshot of the old ids+masks before any rebuild so `EntityWindow_MigrateMasks` can copy surviving sections' 32-byte slots to their new entries by section identity. A DEBUG no-dup assert inside `EntityWindow_TrySpawnRing` (the single `RingBuffer_Add` site) detects any double-spawn that would indicate a broken invariant.

**Slides — `EntityWindow_Slide`:** fires when `EntityWindow_DeriveWindow` returns an anchor that differs from `Entity_Window_Anchor`. Called from the per-frame slide check in `EntityWindow_Scan` and also from `EntityWindow_SyncSlide`. Sequence: snapshot old ids+masks into `Entity_Mask_Scratch` → `Collected_UpdateCenter` (evict first — evict-before-claim avoids silent failure at 9/9 occupancy) → `BuildEntries` (compare-clear voids genuinely-new sections' masks) → `MigrateMasks` (section-identity copy) → populate only sections whose id was NOT in the snapshot. A DEBUG assert inside `Slide` verifies at most one anchor byte changes per call (the 16px/f camera clamp prevents diagonal slides on the hot path).

**Slides are camera-paced, never racy.** Continuous scrolling moves the camera by ≤16px/frame (the vertical clamp; X is similarly bounded), so the anchor advances at most one section per slide and `EntityWindow_DeriveWindow`'s per-frame compare always sees the slide before the camera has moved a full section past it. There is no teleport that can outrun the window, so there is no pre-rebase/post-rebase sync to guard — the per-frame slide check in `EntityWindow_Scan` is the only trigger.

**Edge entries void cleanly at the act boundary.** When the anchor sits at the right (or bottom) edge of the grid, the trailing entry's section index falls outside the grid; `Section_GetSecPtrXY` uses unsigned compares, so an out-of-range index voids the entry to `SEC_VOID` at `BuildEntries` time and it never spawns. There are no negative origins to reason about — every tracked section's world origin (`sec · SECTION_SIZE`) is non-negative, and the camera world clamp (§4.5) keeps the camera inside `[0, level)`.

**`OEF_ANY_Y` lifetime rule:** an ANY_Y object spawns on X coverage regardless of camera Y and is exempt from Y despawn. Section-lifetime still governs: when its section leaves the 2×2 window the object despawns with it and respawns when the section is re-tracked. The ANY_Y flag persists past spawn time as **bit 7 of `SST_slot_tag`**; the per-frame Y despawner tests that bit instead of re-reading ROM. Cross-reference: §3.7 object-state convention — keep positional state relative or derivable from ROM placement so the future floating-origin rebase (§4.11, which shifts `SST_x_pos`/`SST_y_pos`) stays correct.

**Vertical re-scan cost shape:** O(entities already passed by the X ratchet) per 128px camY crossing, across the ≤4 active entries — each candidate is a band compare + btst when already loaded. Trivial on test fixtures; unbudgeted on dense production levels (see DEFERRED_WORK "RescanY burst is unbudgeted").

#### 4.9.4 Unified Ring Buffer

A single 128-entry ring buffer replaces the old dual per-slot buffers. Each entry is 6 bytes:

```
Ring_Buffer entry (6 bytes):
    dc.w    world_X         ; +0: world-space X (collision/draw read it directly)
    dc.w    world_Y         ; +2: world-space Y
    dc.b    section_id      ; +4: which section owns this ring (respawn key)
    dc.b    list_index      ; +5: index into section's ROM ring list
```

**Operations:**
- `RingBuffer_Add`: append to end of buffer, increment Ring_Count. Carry set if full.
- `RingBuffer_Remove`: swap target entry with last entry, decrement Ring_Count. O(1).
- `DrawRings`: single-pass iteration over Ring_Count entries, 6-byte stride.
- `RingCollision`: backward iteration (safe with swap-with-last removal). On collect, calls `Collected_MarkRing` then `RingBuffer_Remove`.

**Diagnostics:** `Ring_HighWater` records the max Ring_Count ever observed (capacity headroom check per level); `Ring_Add_Dropped` counts `RingBuffer_Add` failures and is **DEBUG-fatal** — a dropped ring means the 128-entry buffer is undersized for the level's band density, which must be caught in testing, not shipped. Both reset with `RingBuffer_Clear` at level init.

#### 4.9.5 Rolling Collected Bitmask (3×3 Window)

A 9-slot rolling window tracks ring collection + badnik kill state across section revisits. Each slot is 34 bytes: `[tag.b][pad.b][ring bitmask × 16][killed bitmask × 16]`. Tag = section_id ($00-$FE) or $FF (empty).

```
Ring_Collected_Window: 9 slots × 34 bytes = 306 bytes

Collected_ClaimSlot(section_id): claim empty slot, clear bitmask
Collected_MarkRing(section_id, list_index): set bit in section's bitmask
Collected_CheckRing(section_id, list_index): test bit (Z set = uncollected)
Collected_UpdateCenter(center_id, grid_w): evict slots outside 3×3 grid range
```

The 3×3 window centered on the player's current section means collection state persists for all adjacent sections. Backtracking within ±1 section preserves collected rings. Moving beyond the 3×3 range evicts distant slots, and revisiting those sections later loads them fresh. The 128-bit bitmask per slot supports up to 128 rings per section (build-enforced by `objentry`'s MAX_LIST_ENTRIES cap for object lists).

**Gameplay consequence:** persistence depth is exactly one section of backtrack. A round trip of 2+ sections re-claims evicted slots with fresh bitmasks — collected rings respawn and killed badniks revive. This is the accepted cost of capping the window at 9 slots (162 bytes); classic Sonic behaves the same way for off-screen respawning objects.

#### 4.9.6 Entity Coordinates Are World-Native and Stable

Because the camera is a continuous world camera, an entity's stored position never has to move under it. A ring's `world_X/Y` is computed once at spawn (`section_origin + section_local`) and is valid for the entire time it is buffered — collision and draw read it directly with no translation. An object's `SST_x_pos/y_pos` is likewise a plain world coordinate. There is no seam, no per-section coordinate re-expression, and nothing spawns or dies because of a coordinate event.

The **only** event that shifts entity coordinates is the future floating-origin rebase (§4.11) — a coarse, invisible, atomic subtraction of `REBASE_DELTA` applied uniformly to every live world coordinate (camera, player, every buffered ring's `world_X`, every active object's `x_pos`) plus a re-run of `BuildEntries` so the window recomputes from the shifted camera. Because everything moves by the same delta in one frame, every relative relationship is unchanged and the screen is pixel-for-pixel identical — a pure coordinate renumber, not a content transition. (Section-local ROM data and section_id-keyed respawn/kill memory are coordinate-invariant and are never touched by a rebase — see §4.11.)

#### 4.9.7 RAM Budget

| Component | Size |
|---|---|
| Ring_Buffer (128 entries × 6 bytes) | 768 B |
| Ring_Count + Ring_HighWater + Ring_Add_Dropped + pad | 4 B |
| Entity_Window_Active + Entity_Window_Center_ID | 2 B |
| Entity_Window_Anchor (sec_x0, sec_y0 — slide trigger) | 2 B |
| Entity_Scan_State (4 × $1A bytes) | 104 B |
| Entity_Loaded_Masks (4 × 32 bytes) | 128 B |
| Entity_Mask_Scratch (4 + 128 bytes — slide snapshot buffer) | 132 B |
| Camera_Y_Coarse_Prev (re-scan trigger baseline) | 2 B |
| Ring_Collected_Window (9 × 34 bytes) | 306 B |
| **Total** | **~1,448 B** |

Comparable to the old dual-buffer system (1,187 B) while supporting far more: visibility-derived window with always-on look-ahead, camera-driven loading on both axes, 2×2 quadrant tracking, idempotent spawns, slide mask migration, kill persistence, unified buffer, and buffer diagnostics.

### 4.10 Cascade Effects

```
Level / World System Cascades:

Continuous World Camera over Wrapping Plane (4.1)
  → World coords 0..level extent; no slots, no teleport, no rebase
    → VDP masks HScroll/VScroll to plane size → 64 cells reused in hardware
      → Camera Y is a full grid coordinate, Y=0 ceiling removed
        → sec = world_px >> SECTION_SIZE_SHIFT (the only place sections enter the hot path)

Edge Streaming (4.7 tile cache)
  → Leading section's nametable + collision stream into the wrapping plane each moving frame
    → "See into the next section" is always-on, no preview pass
      → Bounded by the 6-block / 2-row tile-cache budget (no boundary burst)
        → Diagonal motion shares the budget across column + row fills

Pre-Computed Nametable Blocks (4.3)
  → Build pipeline converts chunks at build time (Batman-proven)
    → Scroll = read block from tile cache, queue plane-buffer entry (zero re-conversion)
      → Section_BuildRAMLayout decompresses blocks into the world-space cache
        → Override table patches dynamic terrain (breakable floors)

Deferred Plane Buffer (4.4)
  → Game loop never touches VDP during active display
    → VDP has uncontested bus → more VBlank time for DMA
      → Edge-fill columns/rows flush in VBlank; ≤64 distinct cols/frame clamp
        → Section_RedrawPlanes runs once at level init only — no in-play redraw

8-Layer Parallax (4.6)
  → Per-section parallax_config snapped/lerped on section-boundary crossing
    → Deformation tables create animated wave motion from ROM data
      → Layer enable mask disables unused layers per section
        → Per-section raster command tables enable raster-level visual variety

Section + Allocator Integration (4.8)
  → Whole-act tile art resident in VRAM pool (globally-deduplicated) → no per-section art swap
    → Object art: AllocVRAM at edge spawn, FreeVRAM at edge despawn (refcount cache)
      → Load_Object finds resident art in VRAM (refcount bump, no decompress)
        → Future >VRAM levels: windowed art-residency streamer builds on this model (not slots)

Section-Local Entity Management (4.9)
  → Visibility-derived window: despawn-envelope anchor = (camera − buffer) >> SECTION_SIZE_SHIFT
    → Slides when the envelope crosses a section boundary; mask migration by section identity
      → Look-ahead intrinsic: envelope reaches the ahead section as the camera scrolls
  → Section-local ROM data: positions relative to section; respawn/kill keyed by section_id (coordinate-invariant)
  → Rings: flat X-sorted ROM lists per section; X-ratchet with Y-band gate
    → Ring collision iterates the world-space ring buffer against player position
  → Objects: compact 6-byte v2 entries; per-section type table; ANY_Y spawns X-only
    → SST_slot_tag: entry index | ANY_Y mirror (bit 7) — lifetime = section in window
  → State: rolling 3×3 collected bitmask for revisit persistence (4.9.5)

Section as Independent World (4.2 + 4.8 + 4.9)
  → Each section defines: layout, art, palette, music, physics, parallax, raster table, deformation, animated tiles, rings, objects, type table
    → Transition sections blend between adjacent worlds as a function of world position
      → Rolling state preservation deferred — fresh load on revisit for now
        → Camera-still cutscenes leave the edge streamer idle (free budget)
          → Result: interconnected worlds, not level chunks

Floating-Origin Rebase (4.11 — future, unbounded levels)
  → Triggers only when the camera approaches the 16-bit coordinate ceiling (~16 sec/axis)
    → Coarse (every ~8 sections), uniform (one shift of the live set), invisible (atomic, plane-aligned)
      → Static section data + section_id respawn memory untouched
        → Replaces the deleted leapfrog: same idea (bounded working coord), done coarsely + seamlessly
```

### 4.11 Floating-Origin Rebase — The Unbounded-Level Path (FUTURE, Phase 4)

This is the engine's only invisible-rebase mechanism, and it is **deferred** — built only when a level actually exceeds the coordinate ceiling. It is the principled replacement for the deleted leapfrog: same goal (keep the working coordinate bounded), done coarsely, uniformly, and seamlessly. Full design in `docs/superpowers/specs/2026-06-22-continuous-scroll-traversal-design.md` §9.

**The ceiling it removes.** World positions are 16.16 (pixel value in the 16-bit upper word). Several coordinate ops are signed (deadzone follow, the `asr` section-derive, the despawn/load compares), so the practical ceiling is the sign bit at `$8000` = **~16 sections per axis** (`16 × SECTION_SIZE`). Past that, the signed despawn/load comparisons wrap and produce false despawn / missed load *before* any visual glitch — so the rebase trigger fires on the camera approaching `$8000`, not on a render symptom. (A separate, independent limit: `section_id` is one byte → max 256 sections total, above today's `MAX_ACT_SECTIONS = 48`; widen it to a word when a level nears 256 sections, and fold a rebase epoch into the respawn key if section_ids are ever allowed to repeat across epochs.)

**The model — floating point for world space.** Split the absolute position into a coarse base plus the fine live coordinate, renormalizing periodically so the fine part never overflows:
```
absolute position = World_Section_Base × SECTION_SIZE  +  Camera_X (live 16-bit)
```
The whole engine keeps running in the fine coordinate exactly as today. `World_Section_Base` (one new RAM counter — the only state this adds) records how many sections we have renormalized past.

**The rebase (atomic, one frame, rendering quiesced).** Trigger when `Camera_X` crosses a threshold below the ceiling (e.g. `REBASE_THRESHOLD = $6000`). Choose `REBASE_DELTA` as a whole number of sections (e.g. `8 × SECTION_SIZE = $4000`); because a multiple of `SECTION_SIZE` is automatically a multiple of the 512px plane width, the wrapped nametable lines up and **no plane redraw is needed**. Then, in one step, subtract `REBASE_DELTA` from every piece of live world-space state and add `REBASE_DELTA / SECTION_SIZE` to `World_Section_Base`:
- `Camera_X`, `Player_1.x_pos`
- every active object `x_pos` (walk Object_RAM / Dynamic_Slots)
- every buffered ring `world_X` (walk Ring_Buffer)
- the tile-cache world cursors (`Cache_Left_Col`/`Cache_Head_Col`/streaming cursors), shifted by `REBASE_DELTA/8` tiles — `REBASE_DELTA` is a section multiple, so the cache even-row/circular invariants are preserved
- the entity-window state: easiest to **re-run `BuildEntries`** after shifting the camera, so it recomputes from the shifted camera rather than being bumped by hand

It is invisible because everything moves by the same delta in one frame — every relative relationship (camera↔player↔entities↔plane) is unchanged and the screen is pixel-for-pixel identical. It is a pure coordinate renumber, not a content transition, so there is **no preview zone and no per-section object/ring handoff** — those leapfrog mechanisms stay deleted; continuous streaming + the entity window already cover "see ahead" and "spawn ahead".

**What it does NOT touch (verified by the section-local entity audit, 2026-06-22).** The static per-section `sec_objects`/`sec_rings` ROM data is section-local (positions relative to the section, `0..SECTION_SIZE-1`, build-enforced) — never shifted, never overflows at any level size. Respawn/collected/killed memory is keyed by absolute `section_id` (`sec_y × grid_w + sec_x`) + list-index — coordinate-invariant, so it survives a rebase untouched. The **only** data-lookup change is adding `World_Section_Base` where a (local) coordinate maps to an absolute section for ROM lookup: `absolute_section = World_Section_Base + (Camera_X >> SECTION_SIZE_SHIFT)`.

**vs. the leapfrog.** Same good idea (keep the working coordinate bounded), done coarsely (every ~8 sections, not every boundary), uniformly (one shift of the live set — no slots, no per-section art swap), and invisibly (atomic, plane-aligned — no seam). Bookkeeping is one counter plus `+World_Section_Base` at the handful of section-lookup sites, versus the leapfrog's slot map + thresholds + edge flags + preview zone. **Cost:** one RAM counter, a per-frame threshold compare, and a rare entity-walk (tens of entities, a few hundred cycles, once per ~8 sections of travel).

### 4.12 External Warp Mailbox — the supported "play from cursor" interface (DEBUG shapes)

The editor (Aurora) needs to drop the running game at an arbitrary world position. This is the **one supported way to do that**, and the reason it is an engine feature rather than a client trick is that a bare camera/player poke *tears*.

**Why a poke tears.** Everything downstream of the camera latches **per-frame deltas** off it. `Tile_Cache_Fill` reads `Cache_Prev_Cam_X` / `Cache_Prev_Cam_Row` and, on a teleport-sized delta, blows through the 16 px hysteresis and latches a prefetch *direction* from the jump rather than from the player's motion; the cache **window** (`Cache_Left_Col`/`Head_Col`/`Top_Row`/`Bottom_Row`) still describes the old locality and only crawls at 1 column / 2 rows per frame, while every plane write outside it is silently dropped by `Draw_TileColumn`'s bounds gate. The nametable therefore keeps showing pre-jump content until the crawl arrives. Measured from both sides: Aurora's client harness (aurora `64aee42`) sees **0 differing plane-A nametable words at 64/128/256 px, 73 at 512, 94 at 1024, 699 at 2048**, and `tools/warp_mailbox_gate.py` sees the same mechanism engine-side (`Cache_Prev_Cam_X = 96` while `Camera_X = 2144`). The tearing **self-heals in ~150 frames**, which is why it is easy to miss and why any test for it must sample early.

**The protocol.** Three RAM cells, DEBUG shapes only, at the tail of `games/sonic4/config/ram.emp`:

| symbol | type | meaning |
|---|---|---|
| `Warp_Req_X` | `u16` | destination **player** world X, in flat world pixels (`section.emp` coordinates) |
| `Warp_Req_Y` | `u16` | destination **player** world Y |
| `Warp_Req_Flag` | `u8` | `0` = idle/consumed; nonzero = request pending |

- **The client writes X, then Y, then the FLAG — the flag last.** That ordering *is* the concurrency control: the consumer only reads X/Y on a frame where the flag is already nonzero, so a write interrupted between the three stores is read on a later frame, never half-applied. No lock, and none is needed.
- **The cleared flag is the ack.** Poll `Warp_Req_Flag` until it reads 0. The whole warp is complete at that point.
- **The engine writes the CLAMPED destination back into `Warp_Req_X`/`Warp_Req_Y` before clearing the flag**, so a client that reads the pair after the ack learns where the player actually landed. Clamping is against the game's own act edges (`Player_Bound_Right` / `Player_Bound_Bottom`, the same ones `Player_LevelBound` uses every frame) — defence in depth, so no client value can reach `SEC_VOID`.
- **Cost:** the consumer refills the whole 80×60 tile cache and forces a full plane redraw, so the ack arrives ~21 frames after the request (measured). It is a visible hitch, not a seamless transition — appropriate for an editor jump, and deliberately not on any gameplay path.

**The consumer** is `Debug_Warp_Consume` (`games/sonic4/test/ojz_scroll_test.emp`), called as the first instruction of the level state's per-frame update — before objects, camera follow and every streaming step, so a consumed warp is whole before anything can read the state it moved. It is a ladder of calls to the **same `pub proc`s the level init ladder calls, in the same order**, which is what keeps it in sync with the streaming rules by construction:

1. clamp the request through the game's act edges, publish the clamp back;
2. place the leader through `Camera_Target` (both velocities zeroed, status/angle/ground-speed/move-lock/spindash cleared, `Player_SetState(PSTATE_AIR)` so it lands on arrival, **then** the position written with its subpixel fraction cleared — see *Placement semantics* below for why the position write comes last) — a **narrow** refresh, not `Player_Init`, which would tail-call `Player_DebugEnter` under the DEBUG shape's armed cheat;
3. centre the camera on the leader and clamp it against `Camera_X_Max`/`Camera_Y_Max` (the ceilings `Camera_Init` precomputed for the act); clear `Camera_Hold_Frames` / `Camera_Art_Hold`;
4. `Section_Init` — re-stamps `Current_Act_Ptr`, reseeds the four `Section_*_Written` trackers via `Section_FillInitial`, recentres the entity window via `EntityWindow_Init`;
5. `PageCache_ResetRefcounts` then `Tile_Cache_Init` — the latter reseeds *every* streaming latch (window bounds, circular origins, resume sentinels, `Cache_Prev_Cam_Row`/`Cache_Prev_Cam_X`, the H-prefetch direction and accumulator, the `$FFFF` ahead-target sentinels), invalidates block staging and refills;
6. `Plane_Buffer_Reset`, `Section_Plane_Dirty`, `Section_UpdateColumns` — drop any stale pre-warp plane entry, then the synchronous full redraw;
7. force a section crossing (`Parallax_Prev_Sec_X/Y = $FF`, `Parallax_Snap_Pending`, then `Parallax_CheckBoundary`) so the destination's palette / cycle / variants / raster install through the **one path a walked crossing takes** (`Effects_InstallPreset`), rather than a second copy of that logic; then `BgAnim_Init` + `Parallax_Update`;
8. clear the flag.

**Placement semantics — what a client actually gets.** Two behaviours were measured from outside and misread; both are settled here, and one of them was a defect that is now fixed.

- **The destination is placed VERBATIM, in every regime.** `Warp_Req_X`/`Warp_Req_Y` are the leader's `Sst.x_pos`/`Sst.y_pos` in world pixels, clamped to the act edges, published back, and written with the subpixel fraction cleared. No collision probe, snap, or push-out runs inside the ack window — the warp does not resolve the destination against terrain, and a request that lands inside a wall stays inside the wall until the player is actually simulated. A client can treat the post-ack `Warp_Req_X`/`Warp_Req_Y` readback as the exact origin.
- **The one adjustment that used to break that, and why it is gone.** Step 2's `Player_SetState(PSTATE_AIR)` runs `PHook_AirEnter` → `PHook_EnsureStanding` (`games/sonic4/player/player_common.emp`), which normalises the collision box to the character's standing box and applies the feet-planted lift that belongs with it: `y_pos -= (cd_stand_h - current_h) >> 1`. That lift is correct for a state change *in place* — the feet must not move when the box grows — and wrong for a teleport, where there is no "in place" to preserve. While the position was written *before* the transition, the lift survived into the result: a warp taken out of debug-fly (whose marker box is 16×16, `Player_DebugEnter`) landed Sonic **11 px** above the request, `(39 − 16) >> 1` with `cd_stand_h = 2·PLAYER_Y_RADIUS + 1 = 39`; a warp taken while curled landed **5 px** high, `(39 − 29) >> 1`; a warp from any already-standing state landed verbatim. The same request therefore produced different heights depending on what the player happened to be doing — and because the first warp of a DEBUG boot normalises the box for every later one, a two-warp probe in one session read as *destination*-dependent (`ask y=128 → 117`, then `ask y=320 → 320`) when it was really *first-warp*-dependent. **Fixed** by writing the placement after the state transition (`d3`/`d4` carry the clamped pair across `Player_SetState`, whose contract clobbers only `d1-d2`/`a1-a2`), so the hook's lift lands on the pre-warp position and is overwritten. Measured after the fix: a fresh boot's single warp to `y=320` rests at 320, and two successive warps to `y=128` both rest at 128. The change is byte-count neutral and wholly inside `if DEBUG == 1` — `s4.bin` stays `e111dff7`.
- **The leader is ticked every frame; in a no-input DEBUG boot it simply does not move.** `RunObjects` calls `Player_Main` unconditionally, but the DEBUG shape arms `CHEAT_DEBUG_FLY` and `Player_Init` tail-calls `Player_DebugEnter`, so the level state boots into free flight — and `Player_Main`'s escape hatch (`tst.b PlayerV.debug_flag(a0); bne Player_DebugMove`) routes past the physics, the state dispatch and the rings into `Player_DebugMove`, which reads the D-pad and nothing else. With no input that is a ticked no-op, which from outside is indistinguishable from a leader that is never run. **There is no separate "simulation" mode flag to set.** To enter the simulated-player regime a harness sends one **B press** (`Player_Main`'s cheat-gated toggle → `Player_DebugExit` → standing box, `debug_flag` cleared, `PSTATE_AIR`); gravity and terrain engage on the next tick. Measured from a no-input boot at `x=256`: `y` holds 256 for 60 idle frames, then after one B press runs 256 → 260 → 332 → 573 and `player_state` goes `PSTATE_AIR` → `PSTATE_GROUND` with `ST_IN_AIR` clearing on touchdown. Poking `PlayerV.debug_flag` directly is *not* the equivalent — it skips `Player_DebugExit`'s box, art and animation-latch restore. Note that the pad cells are rewritten every VBlank, so the press must come from the emulator's controller surface (`emulator/press`), not from a memory write.
- **What Aurora and headless harnesses should expect.** Warp, poll the flag to 0, read `Warp_Req_X`/`Warp_Req_Y` for the clamped origin, and expect the leader to sit there indefinitely — the ~19-frame ack is the whole warp, and nothing moves afterwards until input arrives. A harness that wants to watch the player fall, land and settle must engage the regime above first; one that wants a static placement (screenshots, plane comparisons, the `warp_mailbox` gate) deliberately should not.

**`PageCache_ResetRefcounts`** (`engine/level/page_cache.emp`) is the piece the engine was missing. `TileCache_FillAll` has documented since P2b that a **warm-cache** refill must first reset refcounts, because its bulk nametable zero bypasses the patch runs' per-word unref; `PageCache_Init` could only provide that by also dropping *residency*, which is rebuildable only by `Level_LoadArt` with the display off. The new proc resets exactly the half `FillAll` invalidates — every `pf_refcount` to 0, every assigned unpinned frame stamped and flagged `PF_EVICTABLE`, free/pinned frames left unflagged — which is precisely the post-state `PageCache_Audit` checks. `Tile_Cache_Init`'s DEBUG tail runs that audit, so the warp verifies its own residency bookkeeping on every warp.

**Shape rules.** Both new procs' bodies are wholly inside `if DEBUG == 1`, so they emit zero bytes in release, and both are **parked immediately against an existing zero-byte label** so their release deb2 symbol entries dedupe away: `s4.bin` and `demo.bin` stay byte-identical (`cdabf8a3` / `f7806241`). The consumer lives in the game state rather than `engine/system/game_loop.emp` because `demo` links every `engine.*` module — an ungated frame-top consumer would compile into a game with no act, and gating it would need a new required `Game` contract const, which both games must bind and which breaks the sigil port harness. The other frame-top seam, `Game.debug_tick`, is already claimed by the off-canonical Config-A profile.

**The gate** is `tools/warp_mailbox_gate.py` (registered in `tools/effects_gates.py` as `warp_mailbox`). It builds its reference by *walking* to the destination in sub-threshold camera hops, proves that reference with a second walk at a different step size, then asserts the mailbox warp reproduces it exactly (0 differing visible-window nametable words) while a bare poke to the same place does not. See the module docstring for the full argument, including why the whole 64×64 plane is not a valid metric (three quarters of it is legitimately path-dependent) and why the negative control asserts bounded wrongness at a fixed early sample rather than permanence.

---

## 5. Player / Character System

Three playable characters (Sonic, Tails, Knuckles) with shared physics via `games/sonic4/player/player_common.emp`, per-character abilities, and a unified shield system. The key innovations: per-section terrain physics (novel — generalizes underwater physics to any terrain type), configurable physics tables that separate character identity from terrain modifiers, and preserving Sonic's classic flat-acceleration feel while enabling per-character tuning.

### 5.1 6-Button Controller Support

**6-button pad support (SHIPPED, §9.4):** The full 6-button read is live (`engine/system/controllers.emp`) — X/Y/Z/Mode are detected via the rapid TH-cycling protocol and exposed to game code through the `Ctrl_x_Ext_Held`/`_Ext_Press` RAM cells (0 on a 3-button pad). Extra buttons can drive debug shortcuts in debug builds (frame advance, profiler toggle) without conflicting with gameplay controls; in release builds, X/Y/Z can map to character-specific actions. Button mapping is game-side — the engine only reads and exposes the raw ext state.

### 5.2 Per-Section Terrain Physics (NOVEL)

**Status (§5 shipped 2026-06-14): plumbing SHIPPED, modifier system deferred.** Movement code never reads `PHYS_*` constants directly — it reads an *effective physics row in RAM* (accel, decel, friction, top speed, gravity, jump force, air accel, release cap) through the a4-register convention; handlers use `PBLK_*` offsets. **Since C1 (2026-08-10) that row is PER-SLOT**: it is the head of a per-player `PlayerBlock` (`games/sonic4/config/ram.emp`) that also carries the frame's derived quadrant and jump-buffer bytes, and `Player_Main` resolves the calling slot's block into a4 once per frame via the `player_block` splice (`player_common.emp`) rather than `lea`-ing a single global table. `Player_RefreshPhysics` recomputes ONE slot's row — it takes that slot's block pointer in a2 — and is called on section change / status events, NEVER per-frame. **Day one the modifier is identity** — `Player_RefreshPhysics` is a straight 16-byte copy of `PhysTable_Sonic` (the character base row) into the slot's row, so behavior is pure classic. The modifier/Lerp system itself (per-section terrain multipliers, boundary interpolation) is the deferred half: it slots into `Player_RefreshPhysics` later as one `dc.w` table + a section reference, with zero changes to movement code. See `DEFERRED_WORK.md` §5.

The intended modifier design (deferred):

With the 2D section grid (Section 4.1), different sections can have different physics properties via composable modifier tables:

**Per-character base table:**
```
PhysicsTable_Sonic:
    dc.w  $000C   ; acceleration
    dc.w  $0080   ; deceleration
    dc.w  $0680   ; top_speed
    dc.w  $0038   ; gravity
    dc.w  $0400   ; jump_force
    dc.w  $0020   ; air_drag_rate
```

**Per-section modifier table (applied as multipliers):**
```
SectionPhysics_Lake:
    dc.w  $0080   ; gravity_mult ($100 = 1.0, $80 = half)
    dc.w  $0040   ; friction_mult (low = underwater drift)
    dc.w  $0040   ; air_density (high = strong drag)
```

Section transitions smoothly interpolate modifiers via Lerp so physics don't snap at boundaries. No Genesis game has per-region physics modifiers — Sonic games hardcode underwater as a special case. This generalizes it to any terrain type.

**Used for:** underwater (high drag, low gravity), ice caves (low friction), sandy areas (high friction), sky/space (low gravity, floaty jumps), industrial zones (conveyor effects).

### 5.3 Physics Improvements

**Air drag — apex-only (shipped):** Air drag (`x_vel -= x_vel asr 5`) applies only during the apex window (`y_vel` between `-$400` and `0`), before gravity, not during descent. Preserves horizontal momentum through fall arcs. (Research correction 2026-06-12: this band exists in S1/S2 as well — it is THE classic behavior, not an S3K fix. See `docs/research/player-physics-classics.md`.) Lives in the shared air body, `games/sonic4/player/player_air.emp`.

**Removed up-velocity cap (FEEL DEVIATION, shipped):** The classic non-jump airborne up-cap (`y_vel` clamped to `-$FC0` on ramp/slope launches) is **deliberately REMOVED**. Under the `PHYS_GSP_CAP` ground-speed cap of `$1000` (the SPG-placement tunneling guard), the fastest launch already converts to ≤ `$1000` upward, so the `-$FC0` clamp would shave only the top ~1.6% of a max launch while truncating earned ramp launches. The knob if launches ever feel truncated is `PHYS_GSP_CAP` — raising it is a coupled change (`CAM_MAX_Y_STEP`, `VFILL_ROWS_PER_FRAME`, and the 32px sensor reach must rise together). A `; FEEL DEVIATION` comment marks the clamp site in `player_air.emp` (`PState_AirShared`, where the `-$FC0` clamp would have lived); also recorded in `DEFERRED_WORK.md` §5. (The separate `$FC0` cap in the steep-landing conversion is a different, retained mechanism — not this cap.)

**Roll-jump air control (shipped):** classic S2/S3K lockout KEPT (user decision 2026-06-12, overriding this doc's earlier lean) — jumping from a roll commits you to your trajectory (`PSTATE_ROLLJUMP` skips air accel; air drag still runs). The full §5 feel contract is classic-faithful with exactly two modern concessions: a 2-frame jump input buffer (`PHYS_JUMP_BUFFER`, press edges OR-accumulated across lag frames) and the jump-delay fix (the player completes movement on the press frame — `Player_Jump` falls through into the air body instead of S2's abort). Coyote time and extended camera rejected. See `docs/superpowers/specs/2026-06-12-player-system-design.md` §2.

**Per-character acceleration tuning:** Flat acceleration model — same increment every frame regardless of current speed. Core to Sonic's tight, predictable feel. Per-character values via configurable physics tables: Sonic accelerates fastest, Knuckles has most friction. Terrain friction applied from per-section physics data (5.2).

**SWAP-based 16.16 fixed point (from Treasure):** Position uses 32-bit longwords: high word = integer pixels, low word = subpixel fraction. `SWAP d0` moves between integer and fraction halves in 4 cycles, enabling single-register position+subpixel with no separate hi/lo register pairs. Velocity addition is a single `add.l`; pixel position extraction is `swap d0; ext.l d0` or `move.w d0, d1; swap d1` depending on context. Gunstar Heroes and Alien Soldier use this throughout.

**Slope physics refinement:** With dual collision sensors from S.C.E. (Section 4.7):
- Angle continuity checking: reject angle jumps > $20 between frames (prevents loop fallthrough)
- Landing speed conversion (shipped): **classic motion-quadrant + angle-band axis-select** (NOT vector projection — the oft-cited "S3K vector projection" is a myth; S3K uses the same banding as S2, verified against both disassemblies, see `docs/research/player-physics-classics.md`). Implemented in `games/sonic4/player/player_air.emp`: compute the motion quadrant (`CalcAngle(x_vel,y_vel)`), then band by surface angle — flat ⇒ `gsp = x_vel`; mid band (±$10–$1F) ⇒ `y_vel asr 1`, `gsp = ±y_vel`; steep (±$20–$3F) ⇒ `x_vel = 0`, `gsp = ±y_vel`; horizontal-motion floor hits ⇒ `gsp = x_vel`; wall-quadrant hits while moving horizontally ⇒ `gsp = y_vel` (wall-run engage). Landing eligibility `dist ≥ -(y_vel>>8 + 8)`.
- Unroll wall clip fix: check clearance before height adjustment when exiting rolling
- Steep slope slide: small gravity push when standing still on slopes > ~67°
- Slope factor `muls.w` → `lsl` optimization: saves ~54 cycles/ground frame
- Fix dead spots, ceiling-sticking bug, smooth angle transitions via interpolation

**Spindash charge curve:** closed-form — gsp = SPINDASH_BASE ($800) + (charge>>8)·$80, yielding $800–$C00. A single formula instead of S.C.E.'s 8-entry table, for code compactness.

**Landing camera lock:** Don't scroll camera down during jumps until player lands or exits bottom dead zone. Prevents camera bounce on every jump.

### 5.4 Character Architecture

**Files as shipped (§5, Sonic only):**
- `games/sonic4/player/player_common.emp` — owns the player frame: the `PlayerV` SST overlay (**26 of the 30 game-usable `sst_custom` bytes: $30-$49 used, $4A-$4D free** — the window is $30-$4F but its tail word $4E-$4F is the engine-owned `SST_interact`. Measured post-SST-fold and post-C4, i.e. with Tails' flight pair *and* Knuckles' glide/climb scratch resident; the "18 of 34"/"18 of 30" figures this doc and `player_common.emp` carried predated both the fold that moved the window to $30 and the character work that filled it), `Player_Init` (which also does the ONE roster resolve — see "Character dispatch" below), the character-agnostic loaders `Player_InitAssets` / `Player_RefreshPhysics` / `Player_LoadArt`, the `CharacterDefs` roster table, `Ability_None`, `Player_Main` (frame skeleton + state dispatch), `Player_SetState` + the enter/exit hook tables, `Player_Display` tail (now just `bsr Player_Animate` / `jsr AnimateSprite` / `jmp Player_LoadArt`), `Player_LevelBound`, debug-fly suspend, and shared helpers (`Player_SnapToSurface`, sizing macros, `PSTATE_COUNT` lockstep asserts). Also owns `Player_Animate` (see §5.6).
- `games/sonic4/player/player_ground.emp` — grounded state bodies: `PState_Ground`, `PState_Roll`, the shared `Ground_Move` tail (cap → projection → wall probe → integrate → floor pair → `Player_SlopeRepel`), and `Player_Jump`.
- `games/sonic4/player/player_spindash.emp` — `PState_Spindash` (relocated from `sonic.emp` into shared player code — pure move, logic identical). Resolves ANIM_SPINDASH per-character via the shared `ANIM_*` contract.
- `games/sonic4/player/player_air.emp` — the one shared air body (`PState_Air`/`PState_Jump`/`PState_RollJump`/`PState_AirBall`, flagged per state via d6), landing banding, `Air_LandState`.
- `games/sonic4/player/player_sensors.emp` — the four macro-stamped directional cores (`Collision_ProbeDown/Up/Right/Left`), the floor/ceiling pair wrappers and wall single-probe (`Player_SensorWallDir`), `Player_AtLedgeEdge` (balance probe — see §5.6), and a DEBUG boot self-check (`PlayerSensors_SelfCheck` column path + `PlayerSensors_SelfCheck_RowFill` exercising the row-fill collision path) that asserts the asm sensors agree with `collision_pipeline.py`.
- `games/sonic4/player/sonic.emp` — Sonic's character RECORD and nothing else: `CharDef_Sonic` (a `CharacterDef`) plus the physics base row it points at (`PhysTable_Sonic`). No Sonic code survives — spindash moved to `player_spindash.emp`, and the asset/art/physics loaders became the character-agnostic `Player_*` procs in `player_common.emp`. Tails/Knuckles add sibling records with zero changes to common.

**Character dispatch (C1, shipped).** The player frame names no character. `CharacterDef` (`engine/structs.emp`, 32 bytes) is the ROM record: `cd_phys` (the 8-word physics base row), `cd_mappings`, `cd_dplc`, `cd_artbase`, `cd_animtable`, `cd_ability` (the airborne `AbilityHook` — flight/glide/double-jump; Sonic's is `Ability_None`), `cd_vrambase` (the character DPLC region's base TILE index — the art word is `vram_art(tile,0,0) == tile`, the DPLC destination is `tile<<5`), `cd_stand_wh` / `cd_roll_wh` (the standing/rolling collision boxes as `W<<8|H`), and `cd_flags` (reserved).

The box packing is not cosmetic: `Sst.width_pixels`/`height_pixels` are adjacent and word-aligned (`size_wh_off()`, `engine/objects/sst.emp`), so `set_standing_size` / `set_ball_size` store a whole box from the record in ONE aligned word — and the enter hooks' "am I curled" test is a word compare of that box against the active record's `cd_roll_wh`, so the curled key moves with the boxes it keys on. Sonic stands 19x39 and balls 15x29 (the classic 9/19 and 7/14 radii); Tails stands 19x31 (S3K `default_y_radius` `$F`) and shares the ball box, which S3K's single `Player_DoRoll` also does.

The **curl geometry** is derived from those same two words rather than stored or constant, because it is a function of them: `curl_head_rise` (`player_common.emp`) is `cd_stand_wh.H - cd_roll_wh.H` — the distance the head travels on uncurl — and `curl_shift_px` / `curl_y_shift` are half of it, the centre move that keeps the feet planted. Sonic 10/5, Tails 2/1. S3K computes the identical pair per character as `y_radius - default_y_radius`. Four sites consume it, all of them formerly hardcoded to Sonic's numbers: the two curl hooks' y-shift, the unroll head-rise ceiling probes in `player_ground` and `player_air`, and the rolling wall probe's standing-height correction (which had the `5` as a bare literal, not even behind the constant). Both records carry an `ensure` that the ball is never taller than the standing box, since the derivation's `sub.b` must not borrow.

The fifth consumer is `Camera_Update`'s roll-tracking lift, and it is the interesting one because it is ENGINE code that needs a per-character runtime value — every source of which is game state `games/demo` does not define. It is served by **`Camera_Curl_Offset` (`engine/ram.emp`): the engine owns the cell, the game fills it.** That is the `Camera_Target` pattern rather than the landing lock's: reaching into a game symbol behind a `Game.*` comptime gate also works, but each such hole has to be gated again for `demo`, while a cell needs no gate at all — `demo` links clean, and 0 means "the tracked object does not curl", which is correct there rather than merely harmless. `Player_RefreshPhysics` is the game's single write, chosen because it is the chokepoint every `Player_Chardef` write passes through, so the cell cannot go stale behind a character swap.

Rejected alternative, recorded so it is not re-proposed: tracking the **feet** needs no character knowledge at all (feet are curl-invariant by construction — that is what the half-difference shift buys), but it moves the tracked point by a per-character standing half-height, so it is the same problem wearing a different hat.

`CURL_Y_SHIFT` is deleted. There is no engine-wide curl constant, because any such constant could only ever have been one character's.

`CharacterDefs` (player_common.emp) is the roster: one record pointer per `CHAR_*` id (`games/sonic4/config/constants.emp`), longword-strided so the index scales by `lsl.w #2` — the 68000 has no scaled indexing. `Player_Init` performs the ONE lookup (`Character_ID` → `CharacterDefs[id]`) and caches the record pointer in `Player_Chardef`; `Player_InitAssets`, `Player_RefreshPhysics`, `Player_LoadArt` and `Player_DebugExit` all read that cache.

Both `Character_ID` and `Player_Chardef` live in GAME RAM, deliberately NOT in the `PlayerV` SST overlay: `engine/system/replay.emp` hashes the whole custom window as part of the recorded-input regression net, and every field inside a hashed span must be address-free or a behaviour-identical tick would hash differently between two builds whose layouts differ. The overlay is **26 of the window's 30 usable bytes** with all three characters resident — flight claimed two for ability scratch (`fly_fuel`/`fly_thrust`) and Knuckles' glide/climb four more plus a word (`glide_angle`, `knux_step`, `knux_timer`, `climb_pad`, `knux_latch_x`), leaving $4A-$4D free.

**Tails' flight (C2, shipped).** `games/sonic4/player/player_fly.emp` holds `PSTATE_FLY`'s body and `Ability_TailsFlight`, the `AbilityHook` `CharDef_Tails.cd_ability` points at — and that single pointer is the whole of what makes flight Tails-only. Numbers and call order are stock S3K (`skdisasm/sonic3k.asm`, `Tails_Test_For_Flight` / `Tails_Move_FlySwim` / `Tails_FlyingSwimming`): 240 fuel ticks spent on alternate frames (480 frames = 8 s), thrust `y_vel -= $20` while `y_vel >= -$100` capped at a 32-frame ramp, coast gravity `+8` against the normal `$38`, top clamp at camera-minimum `+ $10`, and "tired" being nothing but the re-flap gate closing when the fuel is out. It shares the air state's terrain and horizontal control outright — `Air_XInput`, `Air_XDrag`, `Air_Collide` and `Air_LandOnObject` were factored out of `PState_AirShared` for it — because S3K shares the identical routines between flight and jumping.

Three deliberate departures, each commented at the code that makes it: the **SPG-documented S3K ceiling bug is fixed, not reproduced** (S3K zeroes `y_vel` on ceiling contact and leaves the gravity flip stranded, sticking Tails to the ceiling with no gravity until the ramp counter saturates — both stranding sites, terrain ceiling and top clamp, reset the flap here); the coast fall speed is clamped at the shared `PHYS_FALL_CAP` where S3K leaves it unbounded (a sensor-reach safety no real fall observes); and the flight SFX are unwired because S3K's `$BA`/`$BB` are outside the `$33..$B9` id range our SFX bank imports.

The **frame semantics of the ability seam** are settled by this consumer, and the seam needed no change. The hook sits mid-body in `PState_AirShared`, so the press frame finishes under the AIR state's rules and the new state's body first runs the frame after. S3K does exactly that: its flight-entry check hangs off the *jumping* mode handler while the flight physics hang off a different branch of the same status dispatch, so the entry frame gets normal `$38` gravity and flight begins, coasting, the next frame. Entry seeds the **coast** state, not a thrust — the ability arrests a fall before it lifts, and it takes a second press to buy the first flap.

**Knuckles' climb tolerates a 1..3 px wall recess (deliberate S3K divergence, user-ruled 2026-08-12).** S3K freezes the climb on any non-flush, non-ledge wall reading — safe there because S3K's climbable walls have FLAT tops, so the wall distance jumps 0 → ≥4 in one step. **Our terrain has sloped grass tops**, so the face recedes gradually and the probe walks 0 → 1 → 2 → 3 before reaching the ledge threshold; S3K's rule then wedges the ascent permanently a few px below the top (reproduced live: left face x464, frozen at y=561, top tile shape 29 = a slope). Here a 1..3 distance means "still on the wall" and the climb continues; freeze is reserved for EMBEDDED (dist < 0). The ledge threshold is unchanged, so the ledge still fires by S3K's own test one pixel later. Mirrored in the climb-DOWN path (where S3K's rule ejected into a spurious fall on the same geometry); a real wall end and EMBEDDED still detach. Full rationale: `games/sonic4/player/player_climb.emp` header + `DEFERRED_WORK.md`.

**Knuckles' glide family (C4, shipped).** `player_glide.emp` + `player_climb.emp` add five states — `PSTATE_GLIDE`, `GLIDEFALL`, `SLIDE`, `CLIMB`, `LEDGE` — behind exactly one new pointer, `CharDef_Knuckles.cd_ability` → `Ability_KnuxGlide`. **No dispatch, no `Character_ID` test and no engine change was needed to add them**, which is the property the seam was built for: the third character cost one record field and two modules. Structure follows S3K's, including that the fall-from-glide is a *separate state* (own gravity after the move, normal air control, and a dead-stop landing rather than the `gsp = x_vel` conversion), and that the flat-top glide landing enters the belly SLIDE while an angled one lands normally. The climb and ledge move by direct `x_pos`/`y_pos` writes (1 px/frame, and a 4-step clamber script) rather than velocity, exactly as S3K does.

Two **deliberate, user-ruled divergences** are recorded rather than accidental, each documented at the code and in `DEFERRED_WORK.md`: the climb tolerates a **1..3 px wall recess** instead of freezing (S3K's freeze is safe only on its flat-topped walls; our sloped grass tops made it a permanent wedge a few px below the ledge), and **solid-object tops are floors for every player state** — a glide landing on a platform slides exactly as it does on terrain, where stock S3K drops Knuckles out of the glide family entirely via `RideObject_SetRide`.

Shared movement (accel/decel/friction, jumping, rolling, slope factor/repel, projection, sensing, display) lives in `player_common`/`player_ground`/`player_air`; characters contribute only data + ability states — inverting sonic_hack's failed split that shared helpers while duplicating control flow 3×. **All three characters now ship**; what remains deferred is per-character *extras* (instashield/dropdash/Super for Sonic, flight AI for Tails) and the ability-agency parcel, tracked in `DEFERRED_WORK.md` §5.

**The S2-era standing-bit hardcode the spec anticipated is structurally absent here.** sonic_hack (and the S2 lineage generally) keeps player condition in global bitfields with per-character hardcodes, which is what forced its duplicated control flow. Aeon's status bits are **per-SST bytes** written `a0`-relative (`status`, plus `PlayerV.status_secondary`), so there are no `ST_P1_*`/`ST_P2_*` globals to get wrong and nothing to special-case per character — the same code operating on a different SST *is* the second player. The one place the engine needs a per-character runtime value from a state it cannot name (`Camera_Update`'s roll-tracking lift) is served by an engine-owned cell the game fills (`Camera_Curl_Offset`), not by reaching into a character.

### 5.6 Animation Classifier and Speed-Scaled Timing (Shipped — feat/sonic-animations)

**Shared `ANIM_*` id contract** (`games/sonic4/config/constants.emp`): thirteen named ids form the cross-character animation contract:

| Id | Constant | Notes |
|---|---|---|
| 0 | `ANIM_WALK` | |
| 1 | `ANIM_RUN` | |
| 2 | `ANIM_ROLL` / `ANIM_BALL` | alias |
| 3 | `ANIM_SPINDASH` | |
| 4 | `ANIM_PUSH` | |
| 5 | `ANIM_IDLE` | |
| 6 | `ANIM_BALANCE` | ledge teeter |
| 7 | `ANIM_LOOKUP` | |
| 8 | `ANIM_DUCK` | |
| 9 | `ANIM_SKID` | |
| 10 | `ANIM_GETUP` | |
| 11 | `ANIM_FLY` | Tails' flight, fuel remaining |
| 12 | `ANIM_FLY_TIRED` | Tails' flight, fuel spent |
| — | `ANIM_COUNT = 13` | build-time assert: `Ani_Sonic` entry count must equal this |

Each character's `Ani_<char>` table is ordered by these ids, and the contract is "every table has a row for every id", NOT "every character can reach every id". The two flight ids are the worked example: `Player_Animate` writes them only from its `PSTATE_FLY` branch, which only Tails' ability can enter, so `Ani_Sonic`'s rows for them exist purely to keep the table total and carry his walk cycle as a deliberately-indistinguishable-from-correct fallback. A build-time `ensure` keeps every table's entry count == `ANIM_COUNT` (`Ani_Sonic`, `Ani_Tails`, `Ani_TailsAppendage`) plus one per ordinal, so adding an id without updating all three tables is a build error.

**`Player_Animate` — character-agnostic read-only classifier** (`games/sonic4/player/player_common.emp`): called from `Player_Display`; classifies the current frame's animation id into `SST_anim` and computes a speed-scaled hold into `d3` without touching any PSTATE or persistent status bits. Priority order (highest to lowest):

1. spindash (`PState_Spindash` active)
1b. flight (`PState_Fly` active) — `ANIM_FLY` or, once the fuel byte reaches zero, `ANIM_FLY_TIRED`. It needs its own branch because flight is airborne AND uncurled, so without one it would fall through to the walk/run tail
2. ball / roll / jump-ball / airball
3. skid (see below)
4. push (wall contact + opposing input)
5. at rest: getup > duck > lookup > balance > idle
6. run (|gsp| ≥ `ANIM_RUN_THRESHOLD` = $600)
7. walk

**Display conditions (not new state bits):** Skid, duck, and look-up are evaluated read-only each frame. Skid uses a one-byte latch (`_pl_skid_latch`) that holds the pose through the brake while opposing input is held and clears on stop or input release — no new `PSTATE`, no new persistent `ST_*` bit. Duck and look-up are computed purely from input + ground-state; their camera-pan effect (`_pl_look_offset`) is a reserved zero-field hook for a future pass (see below).

**Generalized speed-scaled timing** (`engine/objects/animate.emp`): `AnimateSprite` recognizes duration byte `DUR_DYNAMIC` ($FF) as a sentinel. When present, the per-anim hold is taken from register `d3` (via the `reloadAnimTimer` macro) instead of the script byte. The player computes `d3 = max(0, ($800 − |gsp|) >> 8)`; walk/run/roll scripts use `DUR_DYNAMIC`; the walk↔run split is the separate `ANIM_RUN_THRESHOLD` threshold. Generic objects never use the sentinel, so they are unaffected.

**Balance sensor** (`player_sensors.emp`): `Player_AtLedgeEdge` — a single downward floor probe one foot-width toward the facing direction (via `Player_SensorPair` + `Collision_ProbeDown`). Returns no-ground flag used by `Player_Animate` to select `ANIM_BALANCE`. Threshold constant `LEDGE_NO_GROUND` is marked as tunable.

**`_pl_look_offset` seam:** Duck/look-up camera-pan is NOT implemented this pass. A zero-valued field `_pl_look_offset` is reserved in the `PlayerV` SST overlay as a deliberate hook for the future pass that implements it.

**DEBUG anim viewer** (`games/sonic4/player/player_common.emp`, DEBUG shape only): START toggles a frozen viewer sub-mode; Up/Down step through every `ANIM_*` id with a fixed injected gsp so speed-scaled animations animate visibly. Release builds exclude it entirely.

**State entry/exit hooks (shipped):** Every state has an enter and exit hook; ALL transitions route through a single `Player_SetState` (old exit → write state byte → new enter). Hooks are the only writers of height/width (= ball/standing radii), the ±5px curl/uncurl y-shift, `ST_ROLLING`, and anim selects — so the roll-jump 5px size bug (#5) is structurally impossible (radii change only in hooks; JUMP/ROLLJUMP/AIRBALL all use ball radii).

**Flat explicit state machine (RESOLVED — shipped):** The doc's earlier "hierarchical state machine (evaluate)" idea is **REJECTED** in favor of a flat explicit state index + jump table. `player_state` is a single byte holding a `PSTATE_*` jump-table offset (×2); dispatch is `move.w Player_States(pc,d0.w),d1 / jsr Player_States(pc,d1.w)`. The seven mutually-exclusive movement modes get states (`PSTATE_GROUND`, `ROLL`, `SPINDASH`, `AIR`, `JUMP`, `ROLLJUMP`, `AIRBALL`); concurrent conditions stay `ST_*` status bits (facing, pushing, rolling — the line S2 never drew). The classic `status3` pseudo-states dissolve into the index. Survey verdict: explicit index beats flag-derived dispatch and a hierarchy is unneeded at seven states; new states (wall-run, grinding) are one table row each.

**Shield system:** Unified per-shield objects (fire, lightning, bubble, wind) with consistent DPLC loading across all characters. Shields integrate with the VRAM allocator — shield art allocated on pickup, freed on loss.

### 5.5 Cascade Effects

```
Player / Character Cascades:

6-Button Controller (5.1)
  → Extra buttons for debug shortcuts (frame advance, profiler toggle)
    → Character-specific actions available via X/Y/Z in release builds

Per-Section Physics (5.2)  [plumbing SHIPPED, modifier system deferred]
  → Effective physics table in RAM (a4 convention), identity modifier day one
    → Player_RefreshPhysics is the future modifier/Lerp landing site (deferred)
      → Section definition will include physics modifier table
        → Water becomes just another section modifier (not hardcoded special case)
          → New terrain types = new modifier table, zero code

Character Architecture (5.4)  [Sonic SHIPPED]
  → State entry/exit hooks centralize state setup (Player_SetState, one writer)
    → Flat explicit PSTATE_* index + jump table enables clean new states
      → player_common/_ground/_air handle all shared movement/collision
        → Physics tables separate character identity from movement code
          → Per-section modifiers compose on top of character tables (deferred)
            → New character = new ability code + new physics table + new ability states

Physics Polish (5.3)  [SHIPPED]
  → Air drag fix (apex-only) preserves jump momentum
    → Roll-jump lockout kept classic (user decision — see §5.3)
      → Classic motion-quadrant + angle-band axis-select landing (NOT vector projection)
        → Up-velocity cap (-$FC0) removed; PHYS_GSP_CAP bounds launches (§5.3 FEEL DEVIATION)
          → Angle continuity prevents loop fallthrough
            → Landing camera lock + spindash freeze eliminate camera bounce

Animation Classifier + Speed-Scaled Timing (5.6)  [SHIPPED — feat/sonic-animations]
  → Shared ANIM_* contract (ANIM_COUNT=11) with build-time assert per character table
    → Player_Animate classifies once per frame, read-only (no new PSTATE / ST_* bits)
      → Skid uses _pl_skid_latch; duck/lookup are pure display conditions
        → DUR_DYNAMIC sentinel in AnimateSprite routes hold to d3 (generic objects unaffected)
          → Player_AtLedgeEdge probes one foot-width toward facing → ANIM_BALANCE
            → _pl_look_offset zero-seam reserved for future duck/look-up camera pan
              → DEBUG anim viewer (ifdef __DEBUG__): cycle all ANIM_* ids with fixed gsp
```

---

## 6. Audio System

> **SUPERSEDED PLAN — read this first.** This engine does **NOT** import Flamedriver.
> Audio was the one subsystem the early architecture planned to bring in from outside
> (Flamedriver + SMPS2ASM); the **2026-06-16 master sound spec**
> (`docs/superpowers/specs/2026-06-16-sound-driver-design.md`) replaced that with a
> **from-scratch, fully-owned Z80-autonomous driver** targeting best-on-platform quality
> (a full DAC powerhouse + deep FM synthesis + a game-feel layer no commercial Genesis game
> shipped). Plans **1A** (foundations), **1B** (DMA-survival DAC), **1C**
> (`docs/superpowers/specs/2026-06-17-sound-1c-design.md` — FM+PSG music sequencer), and
> **Phase 3a** (FM depth + native Moving Trucks port, merged `c89bea3` 2026-06-19) have
> **built** the foundation. The authoring tool is **MegaDAW**, not SMPS2ASM. The technique
> subsections below (6.2–6.8) carry per-subsection status banners — several are DEFERRED to
> Phases 2–6, not yet built. References to "Flamedriver," "SMPS," "S3K SMPS
> format," and "SMPS2ASM" in the subsections below are **historical/aspirational** and are
> retained only as the technique provenance; the shipped driver is our own code, our own data
> format. The master sound spec + the 1C design are the authorities — but the master spec now
> carries a **2026-07-01 amendment header** listing its superseded sections (BRR/N-channel
> mixer, busy-poll policy, division portamento, polyphonic-samples criterion). The current
> sound state-of-truth is the pair of 2026-07-01 review docs
> (`docs/superpowers/2026-07-01-sound-engine-review-findings.md` +
> `docs/superpowers/2026-07-01-sound-specs-review.md`).

The 68K has zero sound processing overhead beyond a byte write per command (the
68k↔Z80 mailbox). Audio quality borrows techniques from Batman's Zyrinx driver and
MegaPCM 2.x, integrated with the section streaming system for dynamic per-section
soundscapes (the latter is deferred to Phase 5).

### 6.1 Custom Z80-Autonomous Driver — Full Z80 Autonomy

**SHIPPED (Plans 1A / 1B / 1C / 1D + Phase 3a — merged to `master`):**
- **1A Foundations** — Z80 shell (`phase 0` blob, even-padded), the 68k↔Z80 per-type
  mailbox + status/ack region (`$1F00..$1F3F`), and the Timer-A scheduler primitives.
  Z80 RAM map: `docs/superpowers/specs/2026-06-16-sound-z80-ram-map.md` — **rewritten in
  full 2026-07-02** by the budget phase's A.3 repack: code ceiling `$16F0`→`$18F0` (+512),
  ring page `$19` (`$1900`), sequencer state `$1A00`, derived page-aligned `SND_SFX_BASE`,
  `$1F00+` mailbox/status FROZEN as the external contract. The spec carries the full map,
  invariants, and assert inventory; `engine/sound/sound_constants.emp` stays the authoritative values.
- **1B DMA-survival single-channel DAC** — a free-running, every-path-equal-cost streaming
  loop (MegaPCM-2 model): a 256-byte page-aligned read-ahead ring (page `$19`/`$1900` since
  the 2026-07-02 RAM repack; originally `$1700`), FILL/SKIP/DRAIN
  paths balanced to a constant per-pass cycle cost so DAC pitch never warbles, and a 68k DMA
  flag that switches the producer to a no-ROM-read DRAIN path for the duration of a DMA burst
  (no bus-stall sag). DAC owns the `$6000` bank latch and reg `$2A`.
- **1C FM + PSG music sequencer** — a runtime **event-list song format (v0)**: per-channel
  SMPS-family byte streams + a `SongHeader` (tempo selector, channel routing, stream pointers,
  patch-table ptr). A Z80 **sequencer core** (`Sequencer_Tick`) walks per-channel
  `SeqChannel` state via a jump-table opcode dispatch, advanced once per tempo tick. An **FM
  voice writer** (note→F-number/key-on, patch load, log-volume LUT × per-algorithm carrier
  mask). A **PSG voice writer** (3 tone + 1 noise, attenuation, pause-silence). **Scheduler
  integration:** YM **Timer-A** is programmed so one overflow = one sequencer tick
  (sub-frame, NTSC/PAL-independent — since revised: Timer-A is now the FIXED NTSC-rate frame
  clock, N=137 → measured 59.9227 Hz effective under load, and musical tempo lives in the
  per-channel S3K-exact tempo accumulator, see §6.8); the free-running 1B DAC loop polls the
  Timer-A overflow
  flag once per pass (equal cost on all three paths) and calls `Sequencer_Tick` on overflow,
  bounded so the DAC ring outlasts it (tick-holds are inherent to the class — see §6.8's
  measured 2026-07-02 tick/DAC disposition). **DAC drums** route the song's `$E2` triggers
  to the 1B sample path; FM6 stays the DAC channel in 1C. 68k API: `Sound_PlayMusic`
  /`Sound_StopMusic` over the 1A mailbox. Build-time Python tools generate the F-number/PSG
  divisor tables, the 256-byte log-volume LUT, and the 8-byte carrier-mask table, and pack the
  hand-authored test song; AS asserts validate every table/struct size.
- **1D adaptive FM6 slot + faithful song port (B&R "Moving Trucks")** — a song's `SongHeader`
  flags now declare **FM6's role**: `SH_F_FM6_FM` routes FM6 to the sequencer as a 6th FM voice
  (DAC mode off) and `SH_F_STREAM` streams the packed song + its per-song `FmPatch` bank directly
  from a single 32 KB ROM bank (no RAM copy) — the loader holds that bank for the whole DAC-off
  song. *(Since 2026-07-02 streaming is the ONLY load path: the legacy COPY path — the `$1B00`
  RAM song buffer + `FmPatchInlineTable` — was deleted whole by the budget phase; the packer
  still sets the `SH_F_STREAM` header bit and asserts it on every packed song.)* A new opcode **`MEV_NOTE_RAW` ($E7) + a4 a0 dur** keys an FM note at the **exact**
  `$A4/$A0` frequency word, bypassing `FmPitchTable` (engine: `Fm_NoteOnFreq`, the shared tail of
  `Fm_NoteOn` entered with the fnum word preset; `Seq_Op_NoteRaw`) — needed to reach pitches the
  note-index table can't (sub-C0 bass, microtuning). The Moving Trucks demo is **VGM-derived**:
  `tools/vgm_to_song.py` replays the original game's captured chip-register stream
  (`song_05.vgm`) through our sequencer — per FM channel, a `MEV_NOTE_RAW` at each key-on (60 Hz
  quantized durations) with the voice registers snapshotted at key-on into a deduped patch bank.
  Each note keys **OFF→ON** so the YM2612 hardware envelope re-attacks per note,
  as the original driver does (without it the channel decays to silence after the first note — the
  "blips" bug). *(Since 2026-07-02 the off-before-on lives at the `Fm_NoteOnFreq` chokepoint for
  EVERY note — see the perf-phase bullet below; `Seq_Op_NoteRaw`'s explicit off/on pair was folded
  into it 1:1.)* The reference's per-frame fnum/TL rewrites are **redundant constants** (no vibrato,
  no manual envelope), so the retrigger is the whole story. Verified by **rendered-audio** diff vs
  `song_05.vgm` (`vgm2wav`): time-sounding 98% (ref 99%), log-spectrum r=0.997 (identical peaks),
  dynamic-envelope r=0.868, note sequences 100%. Genuinely faithful. (Lesson: verify rendered audio
  energy/spectrum, not just the key-on register stream.) See
  `docs/superpowers/specs/2026-06-18-sound-1d-moving-trucks.md`.
- **DAC drum playback path (DAC-format revision, 2026-06-25)** — `$E2`-triggered one-shot PCM
  drums that play once and cleanly stop to DC-center, replacing the looping 1B blip. **Payload =
  raw 8-bit PCM.** (A noise-shaped 4-bit DPCM codec was built first, then **reversed to raw 8-bit**:
  the shared DAC bank stores each drum *once*, so compression bought ~nothing for short drums, and
  the decode was the loop's rate cap. DPCM stays a future option via a reserved `ds_codec` byte —
  see the 2026-06-25 amendment in the format-revision spec.) **State machine:** IDLE → PLAYING →
  DRAINING_TAIL → STOPPING (two-stage exhaust so the ring tail plays out, then DC-centers — the
  clean stop and FM6 return are one mechanism). **Banking:** a shared `$8000`-aligned DAC bank holds
  the drums; the window swaps per frame via four cached `SetBank` brackets (B1 `Run_SeqFrame_OnSongBank`
  on both tick paths, B2 `Snd_StartSample` stash-only, B3 ISR bank-transparent, B4 idle→stream
  latch) — song bank for every sequencer frame + ISR blob read, sample bank for every FILL. **Loop:**
  a **register-resident 1:1 streaming loop** (state in `de/h/bc/ix` + the shadow set, `di` for the
  whole sample since the VBlank ISR does not fire during streaming) that emits one ring byte and
  fills one ROM byte per pass (no SKIP pad) — **195 cyc/pass = ~18.4 kHz** (the streaming/pitch
  rate; was 6 kHz with the DPCM 2:1 loop). DMA-stall catch-up is the Timer-A tick's bulk-refill
  (off the hot path); the ring lead (~200 samples ≈ 11 ms) outlasts any real 68k DMA. **FM6 — two modes (per-song `SH_FLAGS`):** (1) *dedicate* (Layer 4, the default for FM6=DAC songs) —
  `$B6=$C0` force-DAC-stereo at sample start, the ch6 `$28` key-on gated at the `Fm_NoteOnFreq`
  chokepoint while a sample plays, FM6 stays DAC-owned for the whole song; (2) *adaptive Echo-style
  time-share* (Layer 7, `SH_F_FM6_ADAPTIVE`, requires `SH_F_FM6_FM`+`SH_F_STREAM`) — FM6 plays music
  *between* hits: each `$E2` keys FM6 off + flips ch6 to the DAC (`$2B=$80`), and at exhaust `.stop`
  flips back (`$2A=$80` then `$2B=$00`) + re-keys FM6's held note (a real EG-retrigger edge) iff it
  holds one. The drum inherits FM6's music pan (the `$B6` force is *skipped* in adaptive, so the
  patch's pan/LFO survive the time-share). Both modes branch on a cached `SND_FM6_ADAPTIVE` + a
  scan-free cached FM6 channel ptr; the Layer-4 gate is unchanged (suppress-FM6-while-DAC-active
  serves both). **Verification
  (no real hardware — Exodus/`oracle` only):** byte-exact de-wrapped ring vs the raw sample (r=1.0),
  the `$2A` cadence at the target rate, the music-channel correctness after a `$E2` (bank-swap gate),
  the FM6 key-on gate, an SFX fired mid-drum, and MT regression — all green. A DEBUG STREAM drum-test
  song (id 2, `C` button) drives the integrated proof. See the format-revision spec + plan.
- **SFX engine (merged to master)** — a 68k-side `Sound_PlaySFX` API + an 8-deep request ring drained
  post-VSync, feeding the Z80 SFX dispatcher with channel **steal / priority / ducking** and `Sfx_Restore`
  (re-keys the displaced music voice off its saved KEYED state — no silence gap). Closes the old "no SFX
  path" gap; the 2026-06-21 73-agent audit's gameplay-reachable bugs are fixed. (Continuous/looping SFX —
  spindash buzz, shield hum — is the only SFX piece still deferred, with the Phase-5 game-feel layer.)
- **SFX fidelity Stage A (feat/sfx-fidelity, 2026-07-03)** — S3K-faithful SFX pitch + arbitration:
  - **PSG pitch**: the transcoder's stale `+24` octave fixup removed — PSG SFX notes map 1:1 to the
    S3K-numbered `PsgDivisorTableZ` (register-verified: jump programs `$140/$0EF`, skid `$078`, all
    S3K-exact). A convention-tie test (`TestPsgPitchMatchesS3KDivisors`) fails the build if the fixup
    or the table numbering ever changes alone.
  - **Retrigger = replace-in-place, instance cap 1** (S3K-faithful): `Sfx_BeginSound` kills any ACTIVE
    slot already running the incoming id via the normal `Sfx_Restore` end-path, then allocates —
    the freed voice is the preferred route again. Per-slot ids live in `SND_SFX_ID_TAB` (parallel
    RAM table; the struct's `sx_pad` +58 aliases SeqChannel `sc_detune` and must stay 0). Spindash
    rev escalation (+1 semitone/press) survives retriggers; register-verified under 5-press spam.
  - **Guards**: PSG mod-sweep divisor floor clamp (underflow → divisor 1, never a wrapped low note);
    TL-overflow saturation audited at every volume→carrier-TL add (engine already clamped; transcoder
    bake pinned by test). `Sfx_Restore` gates on `SND_SEQ_ACTIVE` — an SFX ending over STOPPED music
    silences its voice instead of re-keying the dead song's stale-KEYED note (was: unkillable PSG drone).
  - **`SfxHeader` = 8 bytes** — `sfh_gain` / `sfh_duck` / `sfh_cap` reserved (inert in Stage A;
    transcoder writes 0/0/1) + bit 7 of `sfh_priority` reserved for the non-latching priority flag,
    so Stage B (per-SFX gain, per-SFX duck depth, authored instance caps, continuous-SFX class) is
    pure engine work with no format change. Stage B/C backlog: DEFERRED_WORK "SFX Fidelity Stage B/C".
- **Music-expression spine (Phase 1 + Phase 3, merged 2026-06-27)** — the format-defining lift that
  promotes the per-frame modulation engine onto MUSIC channels and adds a macro/automation layer:
  - **Phase 1** — un-gated software vibrato / pitch-mod / `MEV_MODSET` for music; grew the music
    `SeqChannel` to its 58-byte end-state; FM block-boundary octave correction in `Mod_Advance`.
  - **Phase 3 (the spine)** — `MEV_FMENV` ($F7) + `FmEnvUpdate` per-frame FM-TL carrier volume envelope;
    `MEV_REGWRITE` ($F8) inline raw-register write ($2A/$2B-guarded); **SSG-EG** via a load-time per-op
    patch field (`FmPatch` 26→32 B, `fp_ssg_eg`, the `$90` group in `Fm_PatchLoad`); and the **dual-stream
    macro layer** — `sc_mod_ptr` slot[1] drives a `MacroTick` register-automation stream via `MEV_MACRO`
    ($F9, tag grammar `TAG_MAC_*` = $E0–$E3, 2-byte BE loop, `Snd_SongBase` rebase) over the free `sc_env`
    contour slot. PSG volume envelopes (`Seq_Op_PsgEnv` / `MEV_PSGENV`) are music-legal. The packer authors
    all of it (FmEnv/RegWrite/Macro events, macro-body emitter, header `mod_ptr` back-patch, D8 music-illegal
    opcode gate, `TAG_MAC_*` cross-file sync guard). The whole layer is **inert** when `sc_env`=0 /
    `sc_mod_ptr`=NULL (every shipped song), so HCZ2 / Moving Trucks / SFX render byte-identically.

- **Music-expression Phase 2 — SHIPPED (portamento landed 2026-07-02 on `feat/sound-perf-budget`,
  Task 10; the rest merged to master, 2026-07-01 fix pass verified):** fine detune (`MEV_DETUNE` $F6),
  sequencer-driven hardware LFO (`MEV_LFO` $F4), the global tempo scalar (`MEV_TEMPO` $F3, per-channel
  tempo accumulator), master fade-in/out (`Sound_FadeOut`/`Sound_FadeIn` over `SND_REQ_FADE`), and
  **per-note portamento** (`MEV_PORTA` $F5 → persistent `sc_porta_incr` glide rate; `Porta_Apply`
  RESIDENT in `engine/sound/sound_sequencer.emp`, FM glides block-correct via the shared `Fm_FnumApplyDelta`,
  PSG linear-in-divisor; glide owns the pitch, vibrato resumes at target; oracle soak/glide capture
  per the phase verification process).

- **Sound Performance & Budget phase — SHIPPED (2026-07-02, `feat/sound-perf-budget`):** the
  measurement-driven fidelity pass that closed the last audible HCZ2 gap vs real S3K (spec
  `docs/superpowers/specs/2026-07-01-sound-performance-budget-design.md`; per-task numbers in
  `docs/research/phase_harness/t*_verification.md` + the final `t12_matrix.md`). What changed:
  - **One stream load path** — the COPY path deleted whole (T2, see the 1D note above);
    **DacSampleTable + SeqOpcodeTable banked as co-located window DATA** at their bank heads,
    the `FmPitchTableZ` pattern (T3); **RAM repack** — ceiling `$18F0`, ring page `$19`, seq
    `$1A00` (T4, see the rewritten RAM-map spec under 1A above).
  - **Key-off-before-key-on at the single FM chokepoint** (`Fm_NoteOnFreq.do_keyon`, T5): every
    producer (bare note, NOTE_DUR, NOTE_RAW, PITCHENV rekey, SFX restore) gets a true 0→1 EG
    edge; retrigger went 0-2% → 100% on all melody channels, at ref parity. Tie/no-attack notes
    never reach the chokepoint (unchanged by construction).
  - **Per-note modulation re-arm** (T6): `sc_mod_wait_raw`/`sc_mod_delta_raw` latched at MODSET,
    reloaded every note-on — vibrato delay honored on EVERY note (was: first note ever), contour
    unipolar-up with no inverted starts, at exact ref counts.
  - **Canonical S3K fnum band table** (T7): the generator normalizes `FmPitchTableZ` into
    [644, 1288) — fnum-denominated deltas (vibrato, detune, porta) are worth the same cents at
    every note; the doubled-encoding half-depth gap closed to exact ref parity.
  - **Envelope write-on-change** (T8): sustained FM-TL/PSG envelopes stop rewriting the chip
    every frame; rendered-inaudible (bed ±0.1 dB).
  - **Frame clock measured-and-pinned** (T11): N=137, **59.9227 Hz effective under HCZ2 load**
    (10,800/10,800 ticks over 3 min — the pin compensates ~3 long-tick overruns/min at N=136).
  - **S3K-exact tempo model** (`b342889`): accumulator+skip in mod units replaced the old
    quantizing 16/N reload — see §6.8.
  - **Budget:** phase start 6 bytes free; final `$175A/$18F0` = **$196 (406) bytes free**
    (DEBUG=1 figures; plain builds are 126 B leaner).

**Banked-window physics rule (hard constraint, learned 2026-06-28 — data-only banking invariant):**
only DATA may live in the Z80 `$8000` bank window. CODE fetched through the window corrupts under
68k bus contention (DMA/BUSREQ; `di` does not help) → wild PC → Z80 self-reinit. ALL in-frame code
must be RESIDENT. `engine/sound/sound_banked_z80.asm` was deleted (2026-07-01) when its last banked
routine, `Fm_FnumApplyDelta`, moved resident into `sound_fm.asm` (today `engine/sound/sound_fm.emp`) — the portamento history is the
cautionary tale (the original banked `Porta_Apply` caused Z80 self-reinits and porta only shipped
once fully resident). The 2026-07-02 budget phase reaffirmed the invariant: its banking work (T3)
moved DATA tables only, portamento landed resident (T10), and T10's 3000+-frame soak sampled the
Z80 PC never fetching from `$8xxx`/`$Cxxx` with the `$0000` reset-vector trap never firing.

**DEFERRED (each its own plan):** The old "Phase 2 N-channel DAC mixer"
roadmap item is **superseded by the approved DAC-format spec**
(`docs/superpowers/specs/2026-06-24-dac-drum-format-revision-design.md` + its 2026-06-25 raw-8-bit
amendment): single voice, raw 8-bit PCM, pre-mixed composites; `ds_codec`/`ds_rate` reserved bytes
keep the codec/rate doors open — the mixer *rejection* was the one irreversible format bet and
was **RATIFIED by the user 2026-07-03** (sound design-banking session; see §6.2).
Phase 3b residual FM extras (~~runtime SSG-EG
7th-RegDelta-group~~ SHIPPED 2026-08-10 as RegDelta group 6, Ch3 special/CSM, detune-unison — note the dual-stream macro layer, load-time SSG-EG,
the raw-register escape, the per-frame FM-TL envelope, and PSG envelopes have all SHIPPED, see §6.1 body).
Phase 4's richer *content-adaptive* FM6/DAC modes (the basic dedicate/adaptive Echo toggle already SHIPPED
in the DAC-drum phase — see §6 body). Phase 5 engine integration & game-feel (section-aware banking, music
fade state machine, distance attenuation + priority mixing, procedural ambient, **continuous/looping** SFX
— the base SFX engine itself has SHIPPED). Phase 6 MegaDAW compiler (event-list format finalization,
MegaDAW export retarget, sample/DC-offset encoders).

**Game-feel tier (SHIPPED 2026-08-09 — banking package 1,
`2026-07-03-sound-game-feel-moments-design.md`):** the layer no commercial Genesis driver carried.
**Pause scopes** — `SND_REQ_CTRL` (1 pause-music / 2 unpause / 3 pause-all / 4 unpause-all):
freeze-in-place (no SeqChannel state touched; streams resume exactly where they froze), pop-free
hard mute (the shared `Seq_SilenceMusicVoices` sweep: `$28` key-offs + all six `$B4` pan gates
closed + PSG max attenuation — StopMusic now shares it), resume re-uploads every FM music voice
(`Sfx_UnpauseRestore`; held notes stay silent until their next musical event — the honest-resume
contract). **Jingle push/pop** — `SND_REQ_JINGLE` (SFX id): pause the music, play the jingle
through the normal SFX steal path, auto-pop once its last instance ends (a once-per-frame scan at
`Sfx_Frame`'s tail), resume under a short fade-in. **Status contract** — `SND_STAT_SEQ_ACTIVE`
(a true song-finished floor: a natural all-channels-ended song now drops `SND_SEQ_ACTIVE`),
`SND_STAT_COMM` (the score-authored cue byte, written by `MEV_EXT` sub-op 0 — the extension
prefix's first tenant), `SND_STAT_JINGLE`, `SND_STAT_FADE_BUSY`. **Composed fade terminals +
rates** — the fade command byte is `(rate<<4)|cmd`: cmds 3/4 fade out then StopMusic/pause by
themselves; the rate nibble picks one of 8 MDSDRV-style spread-bit patterns (rotate-right +
carry-gated branchless ±1 step; ~2.1 s to ~17 s full fade). **68k API v2** — `Sound_Pause/
Unpause/PauseAll/UnpauseAll`, `Sound_PlayJingle`, `Sound_FadeOutStop/Pause`, `Sound_FadeCmd`,
and the bus-held status readers `Sound_IsMusicPlaying`/`Sound_IsFading`/`Sound_GetComm`
(`engine/sound/sound_api.emp`). The §7 game flows (act clear, drowning, 1-up) are an API
cookbook for game features — engine-complete, game-side pending (screens/HUD package).

**Why a from-scratch driver over importing one:** the central research finding (master spec §2)
is that no single existing driver — hobbyist (MegaPCM, Flamedriver, XGM2, Echo, MDSDRV) or
commercial legend (Thunder Force IV, Gunstar Heroes, Batman & Robin) — ships the *union* of a
DMA-proof DAC powerhouse + deep FM + a game-feel layer. Each nails one slice. Building our own is
the only way to get the union, keep full Z80 autonomy (the 68k sends a command and never thinks
about sound again — every freed cycle goes to DMA/objects/streaming), and use MegaDAW as the
authoring tool without bending the design to SMPS/VGM.

### 6.2 DAC — Shipped Shape (single voice, raw 8-bit + composites)

> **REVISED 2026-07-01.** The Phase-2 "DAC powerhouse" roadmap that used to live here (DPCM,
> multi-channel mixing, pitch-shifted PCM SFX, half-rate voices) is **superseded by the approved
> DAC-format spec** (`docs/superpowers/specs/2026-06-24-dac-drum-format-revision-design.md` +
> its 2026-06-25 raw-8-bit amendment). Implemented in our own driver, not a port of Flamedriver.

The shipped shape (all Z80-side, zero 68K cost):
- **Single voice, raw 8-bit PCM at ~18.4 kHz** (register-resident 1:1 loop — see §6.1) — beats
  S3K (~10-13 kHz, scratches under DMA), Echo (10.6 kHz), and XGM2 per-voice (13.3 kHz).
- **Pre-mixed composites** cover music-internal drum overlap. Runtime N-voice mixing was
  **REJECTED** by the DAC spec §2.2 — the casualty is sampled-SFX/voice-over-drums only.
- **Reserved doors at zero cost:** the 9-byte sample descriptor carries `ds_codec` (raw 8-bit = 0;
  a future compressed codec, e.g. DPCM/BRR, slots in without a format break) and `ds_rate`
  (per-sample rate, v1 ignores it).
- **Per-sample panning door:** DAC tracks pan via raw FM6 `$B6` writes (`MEV_REGWRITE`); the
  dedicate-mode `$B6` default is seeded at song load, not forced per sample-start, so authored
  pan survives (S3K-style tom fills L/C/R work).
- **DMA protection buffering — SHIPPED (1B):** the page-aligned read-ahead ring + the Timer-A
  tick's bulk refill; the ~200-sample lead (≈11 ms at 18.4 kHz) outlasts any real 68k DMA burst.
- **Clean stop:** the drum state machine (IDLE → PLAYING → DRAINING_TAIL → STOPPING) DC-centers
  the output at exhaust — no boundary pops (the DC-offset concern is handled here, not by a
  per-sample bias subtraction).

> **RATIFIED (user, 2026-07-03 — sound design-banking session).** The single-voice/no-runtime-mixer
> decision is confirmed: classic-faithful Sonic needs no sampled SFX over drums, and the 18.4 kHz
> DMA-survival drum quality is the prize. The cheap insurance rides with the ratification: add
> `ds_vol` + reserved mix-cursor bytes to the descriptor (~3 B/descriptor, zero code) — build item
> in the DAC drum-library-readiness package. See the 2026-07-01 spec review §4.1.

Dropped from the roadmap as children of the rejected mixer (per the 2026-07-01 spec review):
BRR codec, >8-bit mix + dither, pitch-shifted PCM SFX, half-rate voices, independent per-voice
DAC volume (revisit via `ds_vol` at ratification time).

### 6.3 Zyrinx Techniques (technique provenance: Batman & Robin)

> **PARTLY SHIPPED.** The **log volume curve** and **per-algorithm carrier mask** are
> **SHIPPED (1C)** — both are build-generated tables (256-byte LUT, 8-byte mask) applied by the FM
> voice writer to carrier-operator TL only. The rest (verified Z80 bus writes, pseudo-stereo DAC,
> frequency-based FM panning) are DEFERRED to later phases.

**Logarithmic volume curve:** 256-byte lookup table mapping linear volume to perceptually correct attenuation. Human hearing is logarithmic — linear volume steps sound wrong. Zero runtime cost (pure lookup). Single easiest audio quality win. **SHIPPED (1C):** `LogVolumeLut`, generated by `tools/gen_sound_tables.py`.

**Per-algorithm carrier mask:** Volume adjustments via TL must only modify carrier operators (not modulators, which would change timbre). Carrier set varies by algorithm: algo 0-3 = op4 only, algo 4 = ops 2+4, algo 5-6 = ops 2+3+4, algo 7 = all 4. 8-byte lookup table indexed by algorithm gives the carrier bitmask. Essential for the log volume curve to work correctly without distorting instrument patches. **SHIPPED (1C):** `CarrierMaskTable`. Note the **FM register writer deliberately uses fixed `nop` + operator-loop spacing, NOT a YM busy-flag poll** (the busy flag is unreliable, and fixed spacing keeps the DAC's `$4000`/`$2A` parking invariant intact for DAC coexistence — see §6.1 / the 1C design §6). **This is the canonical decision (2026-07-01):** the master spec's §5 "DO busy-poll" advice is superseded by its amendment header. Caveat: Exodus does not model the busy flag, so this is a real-hardware-only risk — if hardware testing ever shows dropped/garbled FM writes, the missing busy-wait is the **first suspect**.

**Verified Z80 bus writes:** Read-back verification on 68K→Z80 command writes: `move.b d0,(a1); cmp.b (a1),d0; bne.b retry`. Prevents silent data loss during bus contention. ~8 extra cycles per verified write.

**Pseudo-stereo DAC:** Alternate YM2612 panning between left/right per DAC tick. Creates wider sound from mono output. One register write per tick on Z80.

**Frequency-based FM panning (NOVEL):** A zero-cost composition convention — pan FM channels by frequency range: FM1 (high melody) → right, FM2 (mid) → center, FM3 (bass) → left, PSG distributed. Creates wider perceived stereo image from FM synthesis alone. No CPU cost, no Z80 cost — purely how music is composed in the S3K SMPS format.

### 6.4 Section-Aware Sound Banking (NOVEL) — DEFERRED (Phase 5)

Batman uses static per-level sound banks. We make them per-section and dynamic:
- `sec_music` and `sec_sound_bank` in section definitions trigger music changes or sample set swaps
- Different sections use different DAC samples (outdoor → nature, cave → echo/drip, boss → heavy percussion)
- **Music anticipation:** as the camera nears a section boundary, the next section's sample bank is pre-loaded into the Z80 DAC buffer so the swap is gap-free when the camera crosses.
- **Music transition types:** Per-section `sec_music_fade_type` controls how music changes:
  - `FADE_CUT` — instant switch (for dramatic moments)
  - `FADE_CROSSFADE` — 30-60 frame crossfade via Z80 volume envelopes (seamless environmental flow)
  - `FADE_STINGER` — transition SFX, then new music (boss entrance style)
- **Conditional bank swaps:** Game state triggers can override section banks — boss spawns → heavy percussion, water entry → echo/reverb samples, speed shoes → higher-energy samples. 68K checks state flags at preload time, selects bank.

No commercial game ties sound banking to level streaming.

### 6.5 Distance-Based Sound Attenuation (NOVEL) — DEFERRED, DEMOTED (2026-07-03)

> **DEMOTED below the game-feel layer** (2026-07-01 spec review CUT list, recorded 2026-07-03):
> nice-to-have, no Sonic game needs it. Keep cheap and late — do not schedule before the
> game-feel-moments work (pause/jingles/resume) is built.

`PlaySoundLocal` currently plays or doesn't play based on on-screen check. Add distance-based volume:
```
volume = max_volume - (distance_to_player × falloff_rate)
```
Objects far from the player are quieter. Log volume table makes attenuation perceptually correct. Cost: one subtraction + one table lookup per `PlaySoundLocal` call.

Enables: distant enemies audible before visible (audio foreshadowing), explosions fading with distance, environmental sounds building as you approach. Gives the game world audio depth that no 2D Genesis game has.

**Priority-based SFX mixing:** When multiple SFX trigger simultaneously, rank by priority (explosion > enemy > pickup > UI). Higher-priority SFX get louder; lower-priority quieter. Combined with distance, creates natural "selective hearing" — a close explosion dominates a distant ring pickup. Cost: ~20 cycles on 68K for ranking, volume adjustment on Z80.

### 6.6 Procedural Ambient Soundscape (NOVEL) — CUT (2026-07-03)

> **CUT** (2026-07-01 spec review CUT list, ratified with the 2026-07-03 DAC single-voice
> ratification): a random ambient PCM trigger is near-incompatible with the single-voice DAC —
> it would interrupt the music's drums. If ambient ever returns it must be re-scoped PSG-only.
> The section below is retained as the historical design record; do not build it as written.

No Genesis game does this. Define an ambient sample pool per section via `sec_ambient_pool`:
- Forest: bird chirps, leaf rustles, distant water
- Cave: water drips, echoes, distant rumbles
- Factory: machinery clanks, steam hisses, electric hums

Z80 firmware includes a LFSR-based random trigger — every 0.5-3 seconds (randomized interval), pick a random sample from the pool, play at low volume. Completely decoupled from main music. ~50 bytes of Z80 code. Each pool entry: `(sample_id, min_interval, max_interval, volume)`.

The game world sounds alive without dedicated ambient tracks. Combined with section-aware banking (6.4) and distance attenuation (6.5), each section becomes a distinct auditory environment.

### 6.7 Continuous SFX — DEFERRED (Phase 5)

S.C.E. supports continuous SFX — sounds that loop while a condition is held (spindash charge, shield buzz, speed shoes whoosh). Separate from the normal SFX queue, allowing seamless looping without re-triggering every frame. **The base SFX engine has SHIPPED** (`Sound_PlaySFX` + channel steal/priority/ducking — see §6.1); what remains deferred is the *continuous/looping* variant: a `PlaySoundContinuous` / `StopSoundContinuous` 68K-side API managing a dedicated auto-looping SFX slot. **Unbundled from Phase 5 (2026-07-03):** this now lands with **SFX fidelity Stage C** (spec `2026-07-02-sfx-fidelity-and-mixing-design.md` §5, `SHF_CONTINUOUS`) — it is a near-term core-feel need (spindash charge, drowning warning), not far-future polish.

### 6.8 Tempo & Timing

**YM Timer A = the fixed NTSC-rate frame clock — SHIPPED (1C, revised 2026-07-01, measured + re-pinned 2026-07-02).** YM2612 Timer A (10-bit, registers $24-$25) is the driver's frame clock, programmed once to a FIXED build-time reload: `SND_TIMERA_N` = 137, computed by `timerAReload()` from `SND_FRAME_MILLIHZ` = 60053 — a **compensated pin**: the nominal target is the NTSC field rate 59.9227 Hz, and N=137 delivers **exactly 59.9227 Hz effective under HCZ2 load, measured** (10,800/10,800 ticks over 3 minutes; N=136's nominal ~59.99 Hz measured 59.873 Hz under load because ~3 long ticks/min each eat one overflow — the pin absorbs that; see `docs/research/phase_harness/t11_verification.md`). **One overflow = one engine frame.** Because Timer-A derives from the YM clock, not VBlank, **PAL drifts only ~0.9% by construction** (vs ~17% for a VBlank-locked driver), and lag frames are irrelevant to music tempo. Musical tempo is NOT the Timer-A reload: since 2026-07-02 (`b342889`) it is the **S3K-exact per-channel accumulator+skip** — `sc_tempo_accum += sc_tempo_mod` every frame; a CARRY marks a tempo-delay frame (no event-tick), no carry = exactly one event-tick, so a channel runs at (256−mod)/256 event-ticks per frame and any authored S3K mod byte is EXACT (the previous accum−=16/reload model could only quantize to 16/N — HCZ2 rendered −1.42% slow). `MEV_TEMPO`/`SND_REQ_TEMPO`/`Tempo_Ramp` are redefined in the same mod units (0 = full speed, bigger = slower). The free-running DAC loop polls the Timer-A overflow flag once per pass; polled, not interrupt-driven (Genesis hardware limitation). **Timer A is never disabled:** `StopMusic` leaves the frame clock armed — the old `Snd_TimerA_Disable` path killed the entire driver (sequencer, SFX, DAC refill) and was deleted in the 2026-07-01 fix pass. (History: the reload was tempo-derived, then a fixed ~59.06 Hz — which played all music ~1.4% slow vs its S3K/B&R sources; caught by ear + review 2026-07-01; then N=136 ≈ 59.92 nominal, replaced by the measured N=137 pin 2026-07-02.)

**Tick/DAC relationship (settled by measurement, 2026-07-02):** in-tick DAC ring draining (Timer-B-paced seam bursts, spec D.2) was implemented, measured net-negative twice (a pitch-correct burst repays real time 1:1 and stretches ticks past the Timer-A period), and REVERTED — **ring-lead for DMA stalls + keeping ticks short is the architecture** (`docs/research/phase_harness/t9_verification.md`).

**PSG silence on pause — SHIPPED (1C).** `Psg_SilenceAll` writes $9F,$BF,$DF,$FF to the PSG port on `StopMusic` to immediately silence all 4 PSG channels. Without this, tones sustain.

**Bank switch optimization — SHIPPED (DAC-drum phase).** The Z80 bank register costs 100+ Z80 cycles per switch (nine `$6000` writes). `SndDrv_SetBank` caches the last selected bank in `SND_CUR_BANK` and **no-ops when the requested bank is already current** — all four per-frame SetBank brackets (sequencer-frame song bank, sample stash, ISR, idle→stream latch) go through the cached path, so a DAC-off song pays zero switches and a drum song pays only the real transitions. Samples share one `$8000`-aligned DAC bank (contiguous packing). The DAC owns the `$6000` latch.

**Channel 3 special mode — DEFERRED (Phase 3).** Per-operator frequencies for detuned unison, bell/metallic sounds, inharmonic timbres. Part of the Phase-3 FM-depth work, authored via MegaDAW (not SMPS2ASM).

**LFO awareness:** Hardware LFO has only 8 fixed global rates (3.82-72.2 Hz) affecting all enabled channels uniformly. For per-channel vibrato, software modulation (direct F-Number manipulation) is required and already handled by SMPS modulation envelopes. Reserve hardware LFO for global tremolo/vibrato where uniform rate is acceptable.

**SSG-EG envelope modes (YM2612 registers $90-$9F):** Vestigial SSG envelope generator modes that loop the ADSR envelope in configurable shapes — sawtooth, triangle, inverted sawtooth, and combinations. Creates evolving, pulsing FM tones impossible with standard one-shot ADSR envelopes. Almost no commercial game used these (Olympic Gold is a rare exception). Furnace tracker exposes all SSG-EG modes. Useful for: alarm tones, energy fields, textural pads, pulsing ambient sound design. Zero Z80 cost — entirely YM2612 hardware. **SHIPPED (music-expr Phase 3, load-time):** SSG-EG is now a per-operator `FmPatch` field (`fp_ssg_eg`, the `$90` group, written in `Fm_PatchLoad`) — MegaDAW / the packer set it per voice. **ALSO SHIPPED (package 4, 2026-08-10, runtime):** per-frame *sweeping* of SSG-EG mode — `MEV_REGDELTA` group 6 maps to the `$90` block (`RegDeltaGroupBase`, `REGDELTA_GROUP_COUNT` = 7; packer `RD_GROUP_SSG_EG`), so a stream can walk the mode mid-note through the existing voice-stepping machinery. E5 is closed.

### 6.9 Music Fade State Machine (implementation for 6.4)

The transition types (FADE_CUT, CROSSFADE, STINGER) require an explicit state machine:
- `Music_Fade_State`: IDLE → FADING_OUT → SWITCHING → FADING_IN (or STINGER_PLAY for stingers)
- `Music_Fade_Counter`: frames remaining in current phase
- `Music_Fade_Volume`: current fade level ($00-$7F)
- `Music_Next_ID`: track queued after fade completes

The boundary-crossing check reads the entered section's `sec_transition_type` and initiates the state machine (or arms it as the camera approaches the boundary). Runs in the main loop alongside palette cross-fading, so music and visual transitions stay matched across the crossing.

### 6.10 Cascade Effects

```
Audio System Cascades (updated with web research):

Custom Z80-autonomous driver (6.1) + Tempo/Timing (6.8)
  → Zero 68K cost — all sound processing on Z80
    → YM Timer A frame clock decouples music from VBlank — lag frames irrelevant, PAL ~0.9%
      → Z80 bus stops minimized to controller reads only
        → PSG silence on pause prevents sustained tones

Section-Aware Banking (6.4) + Bank Optimization (6.8)
  → Camera-boundary crossing triggers sample bank swap on Z80 (armed as the camera nears the boundary)
    → Music transition type controls fade/cut/stinger
      → Bank switch optimization packs samples per-section (minimize 100+ cycle switches)
        → Conditional bank swaps respond to game state (boss, water, speed shoes)
          → Ambient soundscape pool creates per-section sonic identity

Distance Attenuation (6.5) + Priority Mixing
  → PlaySoundLocal computes volume from distance + log table
    → Per-algorithm carrier mask ensures correct TL modification per FM algorithm
      → Multiple SFX ranked by priority for natural mixing
        → Audio foreshadowing: enemies audible before visible

DAC (6.2, shipped shape)
  → DMA-survival ring buffering: drums play clean through real 68k DMA bursts
    → Single voice raw 8-bit PCM @ ~18.4 kHz; pre-mixed composites cover overlap
      → ds_codec/ds_rate reserved bytes keep codec/rate doors open at zero cost
        → State-machine DC-center stop eliminates boundary clicks
          → $B6 pan door + frequency panning creates wide stereo image
```

---

## 7. Visual Effects System

> **Status: SHIPPED through effects suite Phase 2 (2026-08-12) — code-complete; the
> visual gates are oracle-owned (see below).**
>
> **Shipped (P1):** the SPARSE tier of the raster engine (§7.2) and the per-section
> palette load. `sec_raster_table` and `sec_pal` have live consumers wired at the
> section-boundary crossing in `Parallax_CheckBoundary`. The dispatcher lives in
> `engine/effects/raster.emp` and the palette module in `engine/effects/palette.emp`
> (split out of `engine/system/hblank.emp` / `buffers.emp`; `hblank` is the RAM
> jmp-slot trampoline — dispatch mechanism only — and `buffers` keeps the CRAM upload
> machinery). Verified on oracle mid-scroll — `docs/benchmarks/effects-p1/GATE-EVIDENCE.md`.
>
> **Shipped (P2):** the **palette engine** — one owner (`Palette_Compose`, from
> GameLoop) composing base → cycling → cross-fade → global operators → variants into
> `Palette_Buffer` lines 1-3 each frame (line 0 stays the character's). **Variants**
> (`pal_variant`, cheap per-channel shift+bias transforms of the live composed palette,
> derived to a RAM staging buffer) and **scanline regions** (`OP_PAL_REGION`, a scoped
> ≤3-colour swap streamed from that staging — a full-line region spreads across
> ceil(16/3) fires, S3K-style). The **dense raster tier** (`OP_RUN_GRADIENT`, a per-line
> mode firing every line). **Cross-fade** (16-frame per-channel lerp) and **global
> operators** (fade-to-black/white, white/negative flash). **`sec_pal_cycle`** finally
> has a consumer (per-section palette cycling). The **water cluster** is a preset, not
> an engine concept: a variant boundary + S/H + the `Water_Level` patch slot
> (`Raster_Buf_B` rebuild + runtime arm recompute). Budget model: `tools/effects_budget_model.toml`.
>
> **Oracle-owned (code-complete, not yet visually gated):** the row-119 pixel-clean
> boundary (both fixes behind `EFX_ROW119_FIX` — the controller measures and picks);
> the `OP_RUN_GRADIENT` enter/leave line-alignment calibration; and the water-cluster
> gate itself (variant boundary + moving line). **S/H remains visually UNPROVEN** and
> is blocked on CONTENT: it dims only low-priority pixels and OJZ art is high-priority,
> baked into generated block data no engine hook can clear — proving it needs
> low-priority water content (out of the parcel's scope).
>
> **Still planned (Phase 3+):** `raster_dsl`/`palette_dsl` general constructors + the
> preset format (Phase 3); sprite-table-switch reflections (§7.6 — needs a second SAT);
> the frame-level effects engine — sequencer, oscillators, shake, hit-stop (§7.4/7.5,
> Phase 6); Aurora Effects Lab (Phases 4-5); `sec_anim_blocks` (separate). A reserved-
> global stream register for the dense tier is a FLAGGED decision awaiting user sign-off.
>
> Design: `docs/superpowers/2026-08-11-effects-suite-design.md` (six phases).
> The timing rules the dispatcher is built on: `docs/research/2026-08-12-raster-hint-survey.md`.

Palette management, raster effects, hardware-driven lighting, and a lightweight effects engine. The palette system is fully section-aware with computed water palettes (novel). Raster effects are driven by a unified per-scanline command table (§7.2) — Batman & Robin's core raster architecture, enabling stackable VDP register changes per frame. Shadow/Highlight mode provides hardware transparency and lighting at zero CPU cost. Boss and special stage effects use Batman-inspired compound rotation math.

### 7.1 Palette System

**Shipped vs planned.** *(Reconciled 2026-08-14 against the tree, Parcel C2. The
paragraph this replaces described a superseded design and is corrected on four
counts: the owning file, the `sec_pal` contract, what ships, and how a section binds
it.)*

The **per-section palette load** ships: `Palette_LoadSection`
(`engine/effects/palette.emp` — split out of `buffers.emp`, which keeps only the CRAM
upload machinery) consumes `Sec.sec_pal` on a boundary crossing and copies it into
`Pal_Base` for the compose to pick up.

**The contract is 96 bytes = CRAM lines 1-3, and NEVER line 0.** This inverted at
some point after the paragraph above was written: line 0 is the CHARACTER's
(`CharacterDef.cd_palette`), and a level palette that wrote it would revert the active
character's colours on every crossing — Knuckles turning into Sonic mid-act. The old
"full 4-line 128-byte image" contract, and the `OJZ_FullPalette` concatenated blob it
required, are both GONE (that symbol no longer exists in the tree). The engine writes
lines 1-3 only, and the compose ORs at most `%1110` into `Palette_Dirty`.

**Shipped as of effects P2/P3:** per-section cycling (`sec_pal_cycle` →
`Palette_InstallCycleSection` → `Palette_DoCycle`), palette VARIANTS (per-channel
transforms derived into a staging image the raster tier streams), global operators
(fade-to-black/white, white/negative flash), and per-scanline gradients (the dense
raster tier, §7.2). The composition order is fixed: base → cycling → cross-fade →
operators → variants, run once per frame by `Palette_Compose` from the game loop.

**Still genuinely planned:** the **cross-fade** layer alone. `Palette_ArmFade` and
`Palette_DoFade` exist and are correct, but have no caller — `Pal_Target` and
`PAL_FADE_FRAMES` are dead in the shipped ROM (booked as EFX-2). `EffectsPreset`
reserves `ep_transition` to claim it, deliberately unused by any Parcel-C2 fixture so
that parcel's gate stays clean. So the load is still an instant snap in practice.

**How a section binds all of this changed in Parcel C2.** `sec_pal` and `sec_pal_cycle`
are no longer read directly on a crossing: a section names ONE `EffectsPreset` through
`Sec.sec_effects`, and `Effects_InstallPreset` writes every channel — palette,
parallax, raster, patched template, cycling, variants. See §7.12.

**Shared effect-dust slots — the per-character line-0 convention (game-side).** CRAM line 0 is the **per-character** line: `Player_RefreshPhysics` swaps the active `Player_Chardef`'s `cd_palette` (Pal_SonicTails or Pal_Knuckles) into `Palette_Buffer` line 0 on a character change. The shared effect-dust art (skid / spindash / belly-slide — the `DustPuff`/`DustSpindash` children) draws on line 0 at **indices 4, 6, 7** (index 0 = transparent), authored as grays. Because line 0 changes with the character, those three slots must hold the **same grays in every character palette** or the dust inherits whatever that character carries there — Knuckles' reds gave red dust (user-reported, fixed 2026-08-12). The convention: **all character palettes agree with the dust's authoring reference (Pal_SonicTails) at idx 4/6/7.** Sonic/Tails carry the grays natively; Knuckles could not be re-indexed onto SonicTails' line (he uses an S3K colour it lacks) so he keeps his own line but is **permuted within it** (`KNUCKLES_LINE_PERMUTE` in `gen_characters.py` swaps his grays from 12/1/13 into 4/6/7, applied identically to his art and palette — a lossless relabel). HUD/rings live on line 1 and are unaffected; the Tails appendage rides line 0 only while Tails is active. Enforcement is build-time on both ends: `gen_characters.py` asserts the permuted Knuckles palette matches SonicTails at those slots, and `games/sonic4/data/characters/knuckles_data.emp` re-checks the invariant against the shipped blobs. A future 4th character whose palette stomps idx 4/6/7 fails the build rather than silently recolouring the dust. **Variant interaction:** a palette *variant* that tints line 0 (e.g. an underwater `Variant_Water_Deep`) tints these dust slots too, so the dust would darken/blue underwater along with the character — expected, since the dust is a line-0 citizen; a variant wanting neutral dust must preserve idx 4/6/7.

**Palette cross-fading (planned):** Section transitions smoothly cross-fade between palettes over ~16 frames using per-component RGB Lerp. Armed as the camera nears a section boundary and completed across the crossing, so there is no jarring palette snap at the boundary. ~3840 cycles during the transition window, run in idle time.

**Computed water palette (NOVEL):** Instead of maintaining separate water palette data per zone, compute at runtime: `water_color = (base_color >> 1) + blue_bias`. Automatically adapts to palette cycling AND cross-fading — water palette is always derived from current palette, never stale. No Genesis game computes water palettes at runtime.

**Per-section palette cycling (NOVEL):** Palette cycling scripts are per-section via `sec_pal_cycle` in the section definition. Different sections within a zone have different cycling effects (forest shimmer → ice sparkle → sunset glow). Combined with computed water palette, section transitions smoothly cross-fade both base and water palettes with cycling effects changing seamlessly.

**Palette DMA via queue:** All palette uploads route through Priority 0 (critical) DMA queue. Prevents CRAM dots, synchronizes with other VRAM updates.

**Fade-to-white:** Both black and white fades (from S.C.E.). Same 22-frame component-stepping algorithm targeting $EEE. Used for dramatic exits, bright entries.

**Screen flash effects :** Two flash types from S.C.E.:
- White flash: fill CRAM with $EEE for N frames (boss explosions, lightning)
- Negative flash: XOR palette with $EEE mask, flicker every 4 frames (damage feedback, power-up activation)

**Per-scanline palette gradient :** Cycle-exact CRAM writes during HInt — 3 colors per scanline pushed into overscan (Sonic 3 technique). Enables smooth 224-step sky/water gradients. Pre-computed gradient table: 224 × 6 bytes = 1,344 bytes RAM. **Key timing detail:** DMA to CRAM and VSRAM during active display runs at 2x the speed of VRAM DMA (36 bytes/scanline in H40 vs 18 bytes/scanline). This doubled bandwidth makes mid-frame palette gradient writes and VSRAM column-scroll updates significantly more practical than VRAM transfers during active display.

### 7.2 Unified Raster Command Table (NOVEL Aeon design)

> **PROVENANCE CORRECTED 2026-08-14.** This section and the §7 index row previously read
> "(from Batman & Robin — stackable per-scanline VDP register changes)". Batman & Robin has no
> such thing. Re-verified against
> `/home/volence/sonic_hacks/The Adventures of Batman and Robin/disasm/`:
>
> - **Its HBlank handler lives in RAM and is a copied, self-modifying routine — not a table
>   walker.** The IRQ4 vector points at `$FFFFE560`
>   (`code/init/vectors.asm:33`), and the game *copies a whole routine* into that slot:
>   `lea $b15e.l, a0` / `lea $ffffe560.l, a1` / `moveq #$45, d7` / `move.w (a0)+, (a1)+` / `dbra`
>   (`code/engine/misc.asm:71-77`, a 70-word body), with a shorter 38-word variant at
>   `code/engine/misc.asm:136-142`. It then patches words *inside* the copied code — the source
>   pointer at `code/engine/misc.asm:83`, `:91`, `:101`, and the routine's own `bcs` displacement
>   at `:104`, `:117`, `:120`, `:123`, `:159`, which is how it chains page-carry stages and
>   eventually shuts HInt off. Textbook self-modifying code, running from RAM.
>   Elsewhere the slot is armed the same way Aeon's is, by writing a `jmp`:
>   `move.w #$4ef9, $ffffe560.l` + `move.l #$24526, $ffffe562.l`
>   (`code/objects/objects_1.asm:550`, again at `:598`).
> - **What the handler consumes is a value table, not a command table.** The handler at
>   `$0245E0` issues a VSRAM write command and then streams longwords straight from a RAM array
>   (`code/objects/objects_1.asm:613`, `:616-620`; the array at `$FFFFF576` is built by a
>   20-iteration copy loop at `:585-592` — 20 entries, i.e. per-column VSRAM). There is **no
>   opcode field, no register selector and no scanline compare** anywhere in that stream. The
>   two other handler variants stream a 4-byte-per-scanline and a 2-byte-per-scanline value
>   table respectively (`code/engine/misc.asm:78-79`, `:143-144` name the double-buffered
>   table pairs) — values only, in both cases.
> - **The thing that *is* a command table in Batman is a frame-level effect bytecode**, not a
>   raster one: a 16-opcode interpreter with a 4-deep call stack at `$FFFFF4FC`, whose opcodes
>   are reset / start / continue / push / pop / set-repeat / loop / computed-jump and eight
>   palette-set loads (`disasm/EFFECTS_ENGINE.md:213-270`). Loops and palette swaps — no
>   scanlines, no VDP register selection.
> - **What Batman has where we have a program is a 16-mode dispatcher.** A RAM word
>   (`$FFE55A`, pre-multiplied by 4) indexes a 16-entry `jmp (pc,d0.w)` table
>   (`code/engine/main_loop.asm:5423-5441`, with a parallel table for the lag path at
>   `:5443-5461`), called from VBlank (`code/engine/interrupts.asm:708`). Each mode sets up a
>   whole frame's raster shape — mode 11 for instance arms per-line HSCROLL DMA plus
>   per-column VSRAM DMA (`code/engine/main_loop.asm:5520-5524`). **Mode 1 is an
>   arbitrary-routine hook**: `movea.l $ffe55c.w, a4` / `jmp (a4)`
>   (`code/engine/main_loop.asm:5467-5469`). That is a mode selector plus an escape hatch —
>   a coarser and different thing from a schedule of typed per-scanline ops.
>
> **So the format described below — a header, fire records in fire order carrying a precomputed
> reg-$0A arm word plus an op count, and typed ops (`OP_SET_REG` / `OP_CRAM` / `OP_PAL_REGION` /
> `OP_RUN_GRADIENT`) that stack arbitrarily on one scanline — is a novel Aeon design.** Nothing
> in the surveyed corpus schedules per-scanline VDP work as a stackable typed-op program.
> What Batman genuinely does contribute is credited accurately elsewhere in §7: mid-frame
> nametable-register swapping and mid-frame VSRAM manipulation, both of which its RAM HBlank
> handler really does (`code/objects/objects_1.asm:611` writes `$8406`, i.e. reg $04 = Plane B base, from inside
> the handler; `:613` issues the VSRAM write command).
>
> The RAM `jmp`-slot trampoline (§0.10, §1.8) is a separate matter and Batman *is* a genuine
> precedent for it — it patches `$4EF9` + target into its HBlank slot exactly as we do
> (`code/objects/objects_1.asm:549-550`). That precedent is worth recording; it is not the
> command table.

> **Sparse tier SHIPPED 2026-08-12** (`engine/effects/raster.emp` — corrected
> 2026-08-14; this line named `engine/system/hblank.emp`, which holds only the RAM
> jmp-slot trampoline, not the tier). The as-built
> format and its timing model are below; the rest of this subsection is the
> remaining design.
>
> **The reload lag is the whole design constraint.** The VDP reloads its internal
> line counter from reg `$0A` *at the instant of underflow*, before the 68000
> executes one handler instruction. A write to `$8Axx` from inside handler `i` is
> therefore consumed at fire `i+1` and schedules **gap(i+1 -> i+2)** — the naive
> "write next_line - cur_line - 1" is off by a whole event. Two consequences:
> deltas are precomputed at BUILD time into each fire record, and the program opens
> with two priming records (reg `$0A` = 0 in VBlank gives cheap no-op fires on lines
> 0 and 1) so every later fire lands exactly. The runtime does no delta arithmetic
> and no line comparison — the schedule IS the program order.
>
> **As-built program format** (what the Phase-3 `raster_dsl` and Aurora compile to):
> a header (`pal_dirty_mask`, `init_count`, `init[]` frame-top `$8xxx` words),
> then fire records in FIRE ORDER (`arm_word`, `op_count`, ops), then a terminator
> (`RASTER_ARM_PARK`, `RASTER_OPS_END`). Ops: `OP_SET_REG` (one `$8xxx` word) and
> `OP_CRAM` (a full command longword in ONE `move.l`, then `count-1` and up to
> `RASTER_BURST_MAX_CRAM` = 3 colours; region and restore ops cap at
> `RASTER_BURST_MAX_DEEP` = 3).
>
> **Fire lines are one line early by construction:** a register write in the handler
> for fire-line L takes effect from L+1, so an effect authored to begin at screen
> line M is scheduled at fire line M-1. The comptime helpers own that -1.
>
> **`pal_dirty_mask` must name the palette lines the ops write.** It is re-asserted
> into `Palette_Dirty` every frame, which is what makes a mid-frame CRAM write
> transient. A mask naming a different line leaves the write latched forever
> (verified failure mode, GATE-EVIDENCE.md).
>
> **The handler raises to IPL 7 on entry.** The 68000 enters IRQ4 at IPL 4, so IRQ6
> can nest; a VBlank between an `OP_CRAM` command and its colour words would
> retarget the VDP address latch. `rte` restores SR, so the guard is ~4 cycles.
>
> **Cycle budget:** the H40 blanking window, **measured at 122.9 cycles** by
> `tools/hblank_window_sweep.py` (2026-08-19), is what a fire's whole burst has to
> fit inside — that, not the 4-entry FIFO, is what sets the per-fire word ceilings.
> They are per class, because a burst word is 26 cycles for cram/vsram and 30 for
> region/restore. Both read 3 today: `RASTER_BURST_MAX_DEEP` because a 4-word deep
> burst would leave 2.9 cycles for margins that want 30, and
> `RASTER_BURST_MAX_CRAM` because 4 cram words *fit* the arithmetic (14.9 cycles to
> spare) yet the solver's rounding lands the first write 0.9 cycles inside the early
> margin — measured, not assumed. The cram class is the one with headroom. The retired pre-measurement estimate — "~105 cycles less
> ~44 for exception entry, about 60 usable" — is what set the old single ceiling of
> 3 and understates the real budget by half. A CRAM write landing inside active
> display tints the pixels drawn after it on that line (single-ported CRAM), which
> is the observed partial row 119 in the gate evidence.
>
> **Sparse, not fire-every-line:** cost is `2 + events` interrupts per frame rather
> than ~224. Fire-every-line was costed at ~11% of an NTSC frame as a constant tax
> and rejected for this tier. Reprogramming the counter from inside the handler is
> shipped Treasure practice (Alien Soldier parks `$8AFF` for a once-per-frame split;
> Gunstar runs a mid-frame state machine), not a novel risk.


Rather than separate per-effect HBlank handlers, the engine uses a **unified per-scanline command table** — a pre-computed list of VDP register changes that the HBlank handler walks sequentially. This is Batman & Robin's core raster architecture, and the reason it achieves visual effects no other Genesis game matches.

**Architecture:**
```
Raster_Command_Table:   ; pre-built per section, sorted by scanline
    dc.w  SCANLINE       ; trigger line
    dc.w  REGISTER        ; VDP register to write
    dc.w  VALUE           ; value to write
    ; ... repeat for all raster events this frame
    dc.w  $FFFF           ; terminator

; HBlank handler walks the table:
HBlank_Handler:
    ; compare current scanline to next command's trigger line
    ; if match: execute command, advance pointer
    ; multiple commands can fire on the same scanline
    rte
```

**What this enables (stackable per frame):**
- Palette swap at water line (line 140)
- Nametable register swap for multi-layer Plane B (line 96, line 160)
- VSRAM column deformation per scanline range (lines 80-160)
- S/H mode toggle at section boundary (line 112)
- Window plane resize for letterboxing (lines 0-32, 192-224)
- Per-scanline palette gradient (every line, via CRAM writes)

All from ONE handler walking ONE table. No per-effect handler swapping, no priority conflicts between effects.

**Corrected 2026-08-14 — there IS a limit, and it binds.** This paragraph used to claim "no limit on how many effects stack in a single frame". `RASTER_BUF_SIZE` is 128 bytes = 64 words, and `raster_program` refuses anything longer (the VBlank walker and the water installer both copy a fixed 128 bytes, so a longer program would be truncated live). Header + two priming records + terminator is ~9 words and a CRAM-class event is ~7-9, so **a program caps at roughly 6-8 events depending on op mix** — one full-line palette boundary alone is 51 of the 64. Raising the buffer is a RAM change (two arrays in `engine/ram.emp` plus the pins) and is not currently planned; see `docs/EFFECTS_AUTHORING.md`'s size-ceiling section for the arithmetic.

**Section installs its raster table:** `sec_raster_table` pointer in the section definition. Section preload copies or points to the section's command table. Default is an empty table (just the terminator) — zero cost when no raster effects are needed.

**Build-time generation:** The build tool compiles high-level raster effect descriptions (water line, parallax bands, nametable splits) into sorted command tables. The 68K never sorts or builds tables at runtime.

**PAL compensation:** S.C.E. uses a `$700`-cycle delay loop on PAL to hide CRAM dots during HBlank palette swaps.

**Mid-frame nametable register swapping (from Batman & Robin):** VDP registers #2/#4 (Plane A/B nametable base) are NOT latched at line start. Writing register #4 during HBlank changes Plane B's nametable address for the next scanline, giving **multiple Plane B nametables per frame**. Each section specifies nametable split scanlines and VRAM addresses as raster commands. VRAM cost: 2KB (H32) or 4KB (H40) per extra nametable. With ~20KB VRAM free after tiles, room for 2-3 extra nametables.

**Mid-frame VSRAM manipulation (from Batman & Robin):** VSRAM column scroll values are read per-column, not latched. Writing VSRAM during HBlank gives per-scanline column offsets. Practical limit: 2-4 columns per HInt (full 20-column update is too many VDP writes for HBlank). Used for boss deformation, shearing effects, pseudo-3D perspective. **Key timing:** VSRAM DMA during active display runs at 2x speed (36 bytes/scanline in H40), making bulk VSRAM updates more feasible than VRAM transfers.

**FIFO slot-precise mid-scanline writes (from Titan Overdrive):** 18 external access slots per H40 scanline at known pixel positions. H-counter polling can target specific slots for VSRAM/CRAM writes between HBlanks, enabling finer-grained raster effects than HBlank-only dispatch. Available for specialized effects but increases CPU cost significantly.

**Scroll table vs H-interrupt efficiency:** Most parallax does NOT need HInt — the VDP hardware scroll table handles per-line H-scroll and per-column V-scroll natively. Reserve HInt for operations requiring mid-frame VDP register changes: palette swaps, nametable register swaps, VSRAM manipulation, S/H mode toggling. Per-line HInt processing consumes 30-50% CPU; pre-computing scroll tables during main loop is far cheaper.

**Interlace Mode 2 (320x448, available):** Register $0C LSM=11 gives double vertical resolution with odd/even field alternation. Not useful for gameplay (flicker at 30fps effective), but available for high-resolution text overlays in menus, cutscene stills, or special stage effects at half framerate.

### 7.3 Shadow/Highlight Mode — Hardware-Driven Lighting (NOVEL for platformers)

VDP Register $0C enables per-pixel brightness manipulation at **zero CPU cost**:
- Low-priority plane pixels auto-shadow (RGB halved)
- High-priority tiles render at normal brightness
- Palette line 4 sprite pixels 14/15 become transparent highlight/shadow operators

**Section-aware S/H (planned):** a planned per-section S/H-enable flag (no such field exists in the `Sec` struct today — it would be added with this feature, e.g. as an `SF_*` bit in `sec_flags`). Sections would independently enable/disable S/H, with HInt toggling at the water line for zoned lighting.

**Applications:**
- Semi-transparent water (Mega Turrican pattern — S/H enabled below water line)
- Cave darkness with player spotlight (highlight-operator sprites around player)
- Day/night per section (toggle tile priorities)
- Translucent boss barriers (shadow-operator sprites)

**Trade-off:** Palette line 4 colors 14-15 become operators (not visible as sprite colors). Art pipeline must account for this. Fully compatible across all Genesis hardware revisions.

**SNES-style transparency via S/H (2024 discovery):** Shannon Birt demonstrated genuine translucent sprites by pre-computing palette entries so shadow/highlight math of `sprite_color + underlying_color` produces the desired blended result. Shadow math: `(color >> 1) & %011011011`. Processes 5,120 pixels/frame at 60fps. Requires knowing underlying plane colors — best for fixed backgrounds (water surface overlays, glass/crystal effects, shield effects), not arbitrary overlap. Niche but available for specific per-section effects.

### 7.4 Effects Engine (from Batman & Robin, simplified)

**512-entry sine table :** Upgrade from 256 entries. Batman quarter-wave trick: `cos(θ) = SineTable[θ + 128]` — one table, both trig functions. 512 extra bytes ROM.

**Compound rotation :** Batman's two-sine formula: `x = A1×cos(θ1) + A2×cos(θ2)`, `y = A1×sin(θ1) + A2×sin(θ2)`. Creates circles, figure-8s, spirals, Lissajous curves from varying angle ratios. ~50 cycles per point (4 muls + 8 adds). Used for boss projectile spirals.

**Pre-rotated frame selection :** Map angle to pre-rendered frame: `lsr.w #5, d0` (512 angles ÷ 32 = 16 frames). Zero CPU cost beyond lookup. Used for directional sprites (projectiles, rotating objects).

**Effect sequencer :** Simplified Batman command interpreter with opcodes: wait, set_palette, loop, branch, call, set_scroll, fade, end. Drives boss intros, special stage sequences, section transition effects. Data-driven — new effects are new scripts, not new code.

**Combined line+column scroll pseudo-rotation :** Per-scanline H-scroll offsets + per-column V-scroll offsets create pseudo-plane-rotation. `H_offset[y] = y × sin(θ)`, `V_offset[x] = x × cos(θ)`. Approximates rotation ±15°. Used for special stage backgrounds, dramatic camera tilts. CPU cost: just writing scroll tables once per frame.

### 7.5 Utility Systems

**Screen shake (from S.C.E.):** Two pre-computed offset tables applied as camera Y displacement. Timed shake (20 entries, escalating amplitude) for impacts. Infinite shake (64-entry pseudo-random pattern) for earthquakes. Data-driven — new patterns are new tables.

**Oscillator system (from S.C.E.):** 16 simultaneous oscillators in a single per-frame loop. Each has frequency, amplitude, direction, velocity. 64 bytes RAM. Used for platform bobbing, ring animation timing, water surface oscillation, boss breathing. Objects read oscillator values instead of maintaining individual timers.

**Window plane HUD :** HUD renders to the VDP window plane (non-scrolling, overlays Plane A where active). Frees 8-12 sprite slots for gameplay. HInt-driven resize for dynamic letterboxing during boss intros and cutscenes.

**Hit-stop / freeze frame system :** Skip the object update loop for N frames (3-6 = 50-100ms) while keeping display, DMA, and input processing active. Combined with 1-2 frame white palette flash, creates ~30% stronger perceived impact. 1 byte RAM (`Hit_Stop_Counter`), ~12 cycles/frame when inactive (tst+beq). Trigger points: boss damage (3-4 frames), player hit (2-3 frames), enemy kill (1-2 frames), boss death (8-12 frames + camera shake).

### 7.6 Sprite Cache Table-Switching — Free Water Reflections (from Castlevania: Bloodlines)

The VDP caches sprite Y-positions, sizes, and link data internally — but NOT X-positions or tile IDs. Switching the sprite attribute table address register (VDP reg #5) mid-frame causes the VDP to use cached Y/size/link from the first table but read X/tile from the second table.

**Application:** Two sprite attribute tables in VRAM. At the water surface (via HBlank), write VDP reg #5 to point to table 2. Sprites above water render from table 1 normally. Below the water line, the VDP reads table 2's X/tile (allowing Y-flip, darker palette, position offset for reflections) while using table 1's cached Y and link chain. **Zero CPU cost** for the reflection — just one VDP register write in HBlank.

**VRAM cost:** $280 bytes for the second sprite table. The reflection table can be pre-built during the object loop: copy each sprite entry with flipped Y and palette swap. Or use a simpler approach — same entries but with a different base tile offset pointing to pre-darkened palette variants.

**Why this beats software reflections:** Software sprite doubling (writing each sprite twice) costs 80+ entries in the sprite table and doubles DMA bandwidth. This hardware trick uses the same 80 entries, adds one HBlank register write, and produces free reflections with zero CPU overhead.

Source: Castlevania: Bloodlines, rasterscroll.com sprite raster effects

### 7.7 Vertical Border Opening — 19 Extra Scanlines (from Kabuto)

Switching from V28 (224 lines) to V30 (240 lines) during active scan, then back to V28 before line 240, causes the VDP to "forget" to start the vertical border. Result: 243 displayable lines on NTSC instead of 224.

**Technique:** At the end of line 224, briefly set V30 mode then immediately revert to V28. The VDP border state machine misses its trigger. Sprites and HScroll work normally in the opened border area.

**Uses:** Bottom HUD in the border region (saves 2+ tile rows of play area). Taller play area for specific zones. Cinematic letterbox removal for dramatic reveals.

**Caveats:** 256x1024 plane size fails (9-bit counter overflow). HIRQ runs continuously without frame reset in the border region. Must be coordinated with the HBlank system (7.2) if raster effects span the border area.

Source: Kabuto hardware notes

### 7.8 Sprite Mapping Format — VDP-Order Reorder

Reorder sprite mapping fields to match VDP sprite table entry layout for sequential word copies in `build_sprites`. The traditional Sonic format (`{Y, size, tile, X}` with different bit packing) requires field extraction and rearrangement per piece. The new format matches VDP order directly.

**Format:** 6-byte frame header (bounding box + piece count) + 8 bytes per piece:
```
; frame header (6 bytes):
dc.b  bbox_x_min               ; +0: signed — leftmost piece pixel
dc.b  bbox_x_max               ; +1: signed — rightmost piece pixel (right EDGE: x_off + width)
dc.b  bbox_y_min               ; +2: signed — topmost piece pixel
dc.b  bbox_y_max               ; +3: signed — bottommost piece pixel (bottom EDGE: y_off + height)
dc.w  piece_count              ; +4: number of sprite pieces in this frame
; per piece (8 bytes at +6, VDP sprite table order):
dc.w  y_offset                 ; signed, relative to object origin
dc.w  size_template            ; VDP size in high byte, low byte = 0 (link merged at runtime)
dc.w  tile_offset              ; relative tile index + palette/priority/flip bits
dc.w  x_offset                 ; signed, relative to object origin
```

**Bounding box:** The 4 signed extent bytes are precomputed at build time as the union of all piece rectangles, made flip-invariant (union of the unflipped and flipped extents) so one box is valid for all four flip states. `Draw_Sprite` culls exactly against this box — no fixed ±32 margins, no per-piece checks, asymmetric frames never pop at screen edges.

**Why VDP-order:** Each VDP sprite table entry is 8 bytes: `{Y, size+link, tile+attr, X}`. When the mapping format matches this layout, `build_sprites` can process each piece with sequential word reads from the mapping data and sequential word writes to the sprite table — no field shuffling, no bit extraction. The link byte is the only field merged at runtime (low byte of word 1).

**Termination:** The `piece_count` header (at +4, after the bbox) eliminates per-piece terminator checks entirely. A sentinel-based approach ($8000 terminator) saves one word of data but costs a `cmpi` per piece — with 60-100 sprite pieces per frame, the count header is faster.

**Savings:** Eliminates field reordering and bit manipulation per sprite piece per frame. With 20+ objects rendering 3-5 pieces each at 60fps, this saves hundreds of instructions per frame — effectively free performance from a data format change.

**Build pipeline:** The build tool generates all sprite mapping data in VDP-order format directly. `Render_Sprites` consumes it with sequential word copies.

Source: plutiedev.com/blog/20241013 (original reorder concept), extended with VDP-order alignment and count header.

### 7.9 Palette Cycling Animation Trick (from Jon Burton / Sonic 3D Blast)

Each tile uses only 4 of 16 palette entries per "sub-frame." By cycling which 4 entries are active each frame, one stored tile frame becomes 4 displayed frames. 15fps tile animation appears as 60fps to the eye.

**Application:** Waterfalls, energy fields, fire effects, animated crystals — store 1/4 the animation frames, get 4x the visual frames via CRAM writes. Zero DMA cost for the animation (just palette changes, which are Priority 0 and always transfer). Zero additional VRAM for animation frames.

**Trade-off:** Each sub-frame uses only 4 colors, so the combined effect has limited color depth. Best for effects where motion matters more than color variety.

### 7.10 Project MD Reflection Floor (safe, no undocumented features)

Render objects twice: normal sprites at high priority, reflection sprites at low priority with Y-flip and dark palette. High-priority Plane B acts as the floor surface. Reflections show through transparent pixels in the floor tiles. Per-line H-scroll on the floor creates perspective distortion.

**Why this is notable:** Creates convincing 3D reflective floors using only standard VDP features. No undocumented registers, no hardware tricks. Works on all Genesis hardware revisions. Barely costs CPU — just duplicate sprite entries with modified attributes.

**Combines with:** Shadow/Highlight mode (7.3) for automatic darkening of the reflection. Sprite cache table-switching (7.6) for zero-cost reflection generation if the floor is at a fixed Y position.

### 7.11 Cascade Effects

```
Visual Effects Cascades:

Palette Cross-Fading (7.1)
  → Boundary-approach arms the fade, the section crossing completes it
    → Computed water palette auto-derives from current fade state
      → Per-section cycling scripts install alongside cross-fade
        → Per-scanline gradient updates from cross-faded palette
          → Base + water + cycling + gradient all transition seamlessly

Shadow/Highlight Mode (7.3)
  → planned per-section S/H-enable flag (no Sec field today; future SF_* bit)
    → HInt toggles S/H at water line for zoned lighting
      → Highlight-operator sprites around player = spotlight in dark sections
        → Combines with computed water palette (shadow below water = auto-darker)

Unified Raster Command Table (7.2)
  → Section definition specifies sec_raster_table
    → Camera-boundary crossing installs the entered section's command table
      → Water palette swap + S/H toggle + gradient + nametable split + VSRAM deform stack in ONE table
        → Build tool compiles high-level effect descriptions into sorted commands
          → Window plane resize, letterboxing, multi-layer Plane B — all just table entries
            → Scroll table pre-computation handles parallax WITHOUT HInt overhead
              → HInt reserved only for register changes that require mid-frame VDP writes

Effects Engine (7.4)
  → Sine table shared by: rotation math, parallax deformation, oscillation, pseudo-rotation
    → Compound rotation creates boss patterns from data
      → Effect sequencer drives cutscene/transition visual sequences
        → Pseudo-rotation creates special stage backgrounds

Hit-Stop System (7.5)
  → Boss damage triggers freeze + white flash + camera shake
    → Object loop skipped but display/DMA/input remain active
      → Combined with palette flash (7.1) for compound impact feel
        → Per-trigger-point frame counts tuned for game feel

Oscillator System (7.5)
  → 16 oscillators drive: platform motion, water surface, ring timing, shake amplitude
    → Objects read oscillator values (no per-object timer state)
      → Screen shake reads oscillator for natural amplitude variation
```

### 7.12 Effect binding: one preset per section (TOTAL BINDING)

> **SHIPPED — effects P3 Parcel C2, 2026-08-14.**

A section binds every visual effect through ONE pointer: `Sec.sec_effects`
(offset `$34`) names an `EffectsPreset` (`engine/effects/preset.emp`, 32 bytes),
and `Effects_InstallPreset` writes **every channel** on the crossing.

```
EffectsPreset      $00 ep_pal            required — the preset CARRIES the palette
                   $04 ep_parallax        0 = act default (the one legal 0)
                   $08 ep_raster          static program; 0 illegal, use Raster_Program_None
                   $0C ep_patched         patched template (water / world-anchored gradient)
                   $10 ep_cycle           0 illegal, use Pal_Cycle_None
                   $14 ep_variants[2]     unused slots 0 = clear
                   $1C ep_patch_world_y   meaningful only with ep_patched
                   $1E ep_transition      cross-fade arm (reserved; see §7.1)
```

**Why total binding, and what it fixed.** The three predecessors
(`Palette_LoadSection`, `Palette_InstallCycleSection`, `Raster_InstallSection`) each
read one descriptor field and treated NULL as *"keep whatever the previous section
had"*. That is not a neutral default — it means an effect installed in one section
persists into every later section that does not happen to overwrite it. The concrete
failure: water installed in the spawn area survived the crossing and rendered at a
stale screen line indefinitely, in sections that never asked for it. Writing every
channel makes "off" expressible, which is why the `_None` sentinels exist:
`Raster_Program_None` (a parked 3-word program) and `Pal_Cycle_None` (a non-NULL
zero-channel script). A NULL cannot mean "off" while it also means "keep".

**The field costs no bytes.** `sec_effects` is the RENAMED `sec_collision_s4lz` — a
reserved `$34` slot with zero consumers. `sizeof(Sec)` stays 66, which matters because
66 is pinned by three `ensure`s and spelled as a literal `#66` in two runtime
multiplies (`section.emp`, `tile_cache.emp`).

**One patched channel, generically named.** `ep_raster` and `ep_patched` are mutually
exclusive, enforced at comptime by `preset()`, because they route through DIFFERENT
buffers: a static program is staged into `Raster_Buf_A` via `Raster_Pending`, while a
patched template is copied into `Raster_Buf_B` and has one arm word rewritten each
frame to track the camera. Populating both means whichever installs last destroys the
other's state. Water and a world-anchored gradient share the one channel because
`RasterGradientProgram`'s `rgp_arm0` sits at the same byte offset with the same
formula as the water template's — so "at most one patched effect per section" is
structurally unrepresentable rather than merely checked.

**Install ordering** has exactly one hard constraint: `ep_transition` must arm before
the palette load, because `Pal_Fade_Request` is a one-shot the load consumes.
`Effects_InstallPreset` returns the resolved parallax config in `a0` and does NOT call
`Parallax_StartTransition` itself — that would make `engine/effects` depend on
`engine/level`, cycling against the dependency the crossing site already creates.

**Variant rebinds are guarded.** `Palette_SetVariant` sets `PAL_ACT_VARIANT_STALE` on
every call, even re-binding an identical pointer, and a stale variant forces a
~19,332-cycle (15.1%-of-frame) re-derive. The installer skips the write when the slot
already holds the same pointer — matching the "already live?" guards its predecessors
used.

---

### 7.13 Patchable raster fires — the patch table and the schedule builder

> **SHIPPED — effects P3 Parcel P-a (encoder, 2026-08-15) + P-b (runtime patcher, 2026-08-15) +
> HInt schedule local-removal (2026-08-16).** A raster program is a schedule of mid-frame VDP
> writes fired by HInt (§7.2). Before P-a/P-b every fire had a fixed screen line; an author can
> now declare a fire **patchable** — its line is re-derived at runtime within a declared band,
> driven by one of `RASTER_MAX_PATCH` (4) world-anchor channels. P-a emits the bytes
> (`engine/effects/raster_dsl.emp`: `patchable`, `compose`, `patch_table`, `patched_program`).
> P-b shipped the first runtime consumer, `Raster_PatchAll`, an in-place patcher that rewrote one
> arm BYTE per record each VBlank inside the live raster buffer — it could MOVE a boundary but
> could never REMOVE one, because arm words are relative gaps and a record is left behind only by
> having been walked. The local-removal parcel replaced it with `Raster_BuildSchedule`, which
> RE-RECORDS the whole schedule each VBlank from the ROM template into the INACTIVE buffer,
> emitting only the records that are live, then swaps `Raster_Active_Buf` — so a suppressed record
> is simply one that was never copied. `Raster_HInt` is byte-for-byte unchanged by this, which is
> the reason this shape was chosen over porting Ristar's per-record linked-list schedule (below).
> Gate evidence: `docs/benchmarks/effects-p3-p-b/GATE-EVIDENCE.md` (P-a/P-b);
> `docs/superpowers/plans/2026-08-16-hint-schedule-local-removal.md` and
> `docs/benchmarks/effects-p3-removal/GATE-EVIDENCE.md` (local removal).

**`patched_program(fires)` emits the ordinary sparse program (§7.2's wire format),
padded to exactly 64 words (128 bytes), then the patch table:**

```
byte 128    count                              WORD — number of authored fires
byte 130+   entry x count, 5 words:    [line_src][band_lo_fl][band_hi_fl][rec_off][rec_len]
```

Field meanings, one entry per authored record (`patch_table`, `raster_dsl.emp:1062-1093`):

- **`line_src`** — a literal fire line (high bit clear) for a static record, or
  `$8000 | channel` for a patchable one. The builder reads the high bit to decide whether
  to treat the low bits as a fire line or a channel index into the world-anchor table, and
  it is FIRST in the entry because the builder decides emit-or-suppress from it before it
  needs anything else; `Raster_GetChannelBand` also matches on it directly.
- **`band_lo_fl` / `band_hi_fl`** — the record's band, in **fire lines** (screen line - 1),
  matching every other field in the table. A static record writes its own fire line into
  both, so every field of every table entry lives in the one coordinate system — a
  consumer never has to branch on whether an entry is patchable to know which space a
  number is in.
- **`rec_off`** — the byte offset of THIS record's own arm word inside the emitted program
  body (not the buffer the runtime builds into — the offset is relative to the template,
  and the builder re-derives the live buffer's copy of the same offset from
  `Raster_Patch_Tab` each VBlank).
- **`rec_len`** — the record's byte length, arm word through its last op word. The builder
  copies exactly this many bytes per record; there is no fixed-size per-record copy.

**There is no `arm_off` any more.** P-b's table carried a fourth field, `arm_off`, naming the
byte offset of the arm word an entry REWRITES — the arm of record `k-2`, pre-resolved into ROM
because the in-place patcher kept no offset history of its own (the reload-lag constraint that
made this necessary is unchanged and still documented in §7.2: "the reload lag is the whole
design constraint"; a write from handler `i` schedules `gap(i+1 -> i+2)`). `Raster_BuildSchedule`
emits every record itself and therefore always knows where it just wrote each arm word, so no
pre-resolved offset needs to travel in ROM at all — it is replaced by an 8-byte SCRATCH region on
the stack, two 4-byte pointers to the arm words of the two most-recently-emitted records (a
2-deep slot history the builder shifts forward one record at a time). The word written at record
`i` is consumed at the next HInt reload and schedules the gap that lands record `i+2` (Ruling 1b)
— so the builder pairs each record's
computed gap with the arm slot **two records back**, and the fire-line delta with the line **one
record back**. Park is by construction: a record's arm slot is written only when a record two
positions later is emitted, so the two youngest slots are never touched by the per-record walk and
the builder parks them explicitly afterward — which is also why an all-suppressed schedule parks
correctly (both youngest slots are the priming records) with no special-case emitter.

**The table sits at a CONSTANT `+128` from the template start.** Nothing needs a second
symbol, a length-prefixed descriptor, or a pointer field to find it — a patched template's
address is enough. This constant offset is what the padding buys: `Raster_BuildSchedule` copies
the template's two priming records verbatim (a fixed 5-word prologue: the header word plus two
`[arm][op_count]` pairs) and then walks the table, so nothing about the body's *actual* length is
assumed past the priming records — every subsequent byte the builder reads comes from `rec_off`/
`rec_len`, not from a fixed-size sweep. The 64-word pad still exists and still matters: it is what
makes the table's `+128` address defined regardless of how short the authored program is, and it
is what the static-program path (§8's "runtime half" below, EFX-4b) still copies a fixed
`RASTER_BUF_SIZE` bytes from.

**After the table sits the OFF-SCREEN SHIP TRAILER** (2026-08-15, unaffected by the local-removal
parcel), at `128 + 2 + 10*records` — ten bytes per entry now that entries are five words, not
four; an offset the runtime computes from the record-count word the table already begins with:

```
[n (word)][n x (channel, stage offset, colour count, CRAM addr, reg count, reg words...)]
```

`n` is emitted **always**, zero included, so a reader takes one fixed shape and never branches
on whether a program has a trailer. `n <= 1` is a comptime `ensure`, not a wire fact: the count
word already lets a reader loop, so a second shipping channel needs the guard relaxed and
`Enqueue_Dirty_Buffers`' single test turned into a walk, with no format change.

**It re-issues the WHOLE fire, not just its colours.** A fire is an op LIST, and the ship's job
is "apply this fire from line 0", so every `SetReg` the fire carries travels in the trailer too
and is replayed at frame top — a direct VDP write from `Enqueue_Dirty_Buffers`, which runs AFTER
`Flush_VDP_Shadow`, so it survives the frame and next frame's unconditional flush restores the
shadow value. Transient by construction, exactly like the palette half, with no restore path.
Shipping only the `pal_region` was the first version's defect: OJZ's water fire also carries
`sh_on()`, so the rows above the clamped fire line came out tinted but with Shadow/Highlight
still OFF — measurably lighter (row brightness 46/65/49 against 22/32/35 once fixed), found in
play rather than by a gate.

**It carries PARAMETERS, not a built `DMAEntry`, and that is forced rather than chosen.** The
first design emitted the finished 14-byte entry, folding `Pal_Variant_Stage`'s absolute address
in through `extern()`. It cannot work: an address is a **link-time** value, and putting one
inside the emitted image makes the whole image non-comptime — which breaks
`first_mismatch(patched_program(...), hand_twin)`, the whole-image pin every patched fixture
rests on. Measured three spellings (a `const`, an `equ`, and a `const` bound to
`patched_program`'s result); all three produced `here.provisional` errors.
`Raster_BuildShipEntry` adds the base at install instead, through `Build_DMA_Entry` — the one
builder — so no second site knows the interleaved `DMAEntry` byte layout.

**The trailer is read through the ROM template, never the RAM working copy.** Nothing in it is
ever patched, and the runtime's copy is a fixed 128 bytes that stops before the table.

**What it is FOR:** a patch channel's fire is bounded by its authored band, so when the anchor
leaves the top of the screen the boundary pins at the band floor (`lo`) and the rows above it
keep the base palette — fully submerged with a permanently dry stripe at the screen top. The
trailer's entry re-ships that fire's own colours as a frame-top DMA on the frames the channel's
latched line is `<= 0`, which covers that direction. **The DRY direction (anchor below the
screen) is now covered too** (HInt schedule local-removal parcel, 2026-08-16): past `band_hi`
`Raster_BuildSchedule` does not emit the record at all this frame, rather than clamping it to
`hi` and painting rows the world says are dry. This is what the schedule-recording shape buys
over the in-place patcher it replaced: suppressing a record needs the ability to leave it out of
the walk entirely, which an in-place byte patch on a live buffer could never do (a negative gap
stores as the park word and kills every later fire), and which a from-scratch re-record can,
because "not copied" needs no encoding at all. There is still a residual — for
`band_hi < L < 224` the boundary renders nowhere rather than where the world says it should be —
narrowed, not eliminated; see `docs/DEFERRED_WORK.md`'s closed entry for the accounting. The
parallax overlay (`engine/level/parallax.emp`, Parcel W's boundary-split code) applies the
identical `L > band_hi` suppression, reading the same two band words via `Raster_GetChannelBand`,
so the palette boundary and the scroll boundary still agree at every anchor state rather than
merely erring the same way.

**Why re-recording instead of a per-record link.** The obvious alternative — give each record its
own successor pointer, Ristar's spelling (`ristar_disasm/code/disasm.asm:14556-14595`, each node
writing its own gap AND its own successor so removing a node is a local edit) — was rejected on
HBlank cycle budget, not on capability. `Raster_HInt` runs inside the ~60-cycle-per-line HBlank
window every fire shares; a disarmed Ristar node still costs interrupt entry plus `tst`/`beq`/
`rte` (~40 cycles) even when it contributes nothing, and that tax lands on *every* fire, every
frame, forever — not only the ones a section happens to suppress. Re-recording the schedule from
a ROM template moves that cost to VBlank, which already has slack, and leaves `Raster_HInt`
byte-for-byte unchanged: zero added HBlank cycles for the whole feature. The tradeoff is doing
the record walk twice as much work (build once per VBlank, walk once per HBlank) rather than
once; VBlank has the room for it and HBlank does not.

**What is checked at build time.** `check_arm_layout` (GUARD 6, `raster_dsl.emp:1178-1193`)
recomputes `arm_word_index` and `arm_at` independently for every record and checks the emitted
program's own arm words against that derivation — an authoring-time guard on `raster_program`
itself, unrelated to the patch table's fields and unaffected by the table format change.
`check_rec_layout` (GUARD 10, `raster_dsl.emp:1211-1239`) is the table-specific guard the local-removal
parcel added: for every record it reads `rec_off`/`rec_len` back out of the *emitted* image and
checks that span both starts on a `$8Axx`-class arm word and ends exactly where the next record's
arm word begins — closing table -> derivation -> image, so a wrong `rec_off`/`rec_len` (which
would make the builder copy a misaligned slice, feeding `Raster_HInt` an op payload word as an
opcode) is caught rather than reaching hardware. `patched_words(fires)` (`raster_dsl.emp:1249-1251`)
is the length-annotation counterpart to `raster_words` (§7.2): `64 + 1 + 5 * fires.len +
ship_trailer_words(fires)` — five words per record now that the table carries `rec_off`/`rec_len`
instead of `arm_off` — checked against the emitter's own output on every build.

Authoring rules for `patchable` — the band-interval disjointness requirement, the
worst-case density measurement across a band, `compose` merge semantics, and the band
budget that actually bounds channel count — are documented for authors in
`docs/EFFECTS_AUTHORING.md` (search `patchable`), not repeated here: this section owns the
wire format, that document owns what a call site can violate.

---

### 7.14 Palette bands (mid-screen restore) — Parcel R1, SHIPPED 2026-08-17

> An effect that turns ON at a scanline and turns back OFF at a lower one — a fog slab, a
> top-half glow, a tinted band — over up to 3 CRAM entries (structural: the restore is one
> stream op under the `stream_words <= 3` ceiling; wider bands are booked, see
> `docs/DEFERRED_WORK.md`). Spec: `docs/superpowers/specs/2026-08-16-parcel-r1-palette-bands-v6.md`.
> Evidence: `docs/benchmarks/effects-r1/GATE-EVIDENCE.md`.

**The mechanism.** `Palette_Ship_Snap` (`engine/ram.emp`, 128 bytes, engine-owned) is a
per-line copy of `Palette_Buffer`, one 32-byte slice per palette line. The copy is spliced
into `Enqueue_Dirty_Buffers` (`engine/system/buffers.emp:236-263`) at the point downstream
of BOTH guards for that line — the line was dirty AND its DMA was accepted (the `bclr` that
clears the dirty bit) — so a dropped/skipped line's snapshot is never touched, and the
restore op always streams from what was actually shipped. The invariant, at full strength:
**`Palette_Ship_Snap[line]` equals this frame's base-DMA payload for that line — and for a
band's own line, that payload is DELIVERED every frame**, because `Raster_VBlank` ORs the
program's `pal_dirty_mask` into `Palette_Dirty` before `Enqueue_Dirty_Buffers` runs, so the
band's line is always dirty and always snapshotted. Nothing in VBlank writes
`Palette_Buffer` (an exhaustive writer census lives at the splice site, `buffers.emp:236-`
region, with a pinned entry count guarding drift).

**`OP_PAL_RESTORE`** is an appended `RasterOp` opcode (value 10, dispatch depth 4 —
`RASTER_DEPTH_RESTORE`, `engine/effects/raster_dsl.emp:1033`). Its payload is
`(CRAM byte address, count)`; the snapshot offset IS the CRAM address (`Palette_Buffer+
$00/$20/$40/$60 -> CRAM $0000/$20/$40/$60`), so no separate translation exists between "which
line" and "where in CRAM." Its blanking spin is **solved, not knobbed** (substrate item 1c,
2026-08-19): the lowering centres each op's burst in a blanking window measured on hardware,
reading the op's position in its fire and its dispatch depth. The restore's depth of 4 and
its deeper pre-burst arm are inputs to that, which is what the retired `EFX_RESTORE_DELAY`
was a hand-fitted stand-in for. The 2026-08-17 calibration behind that 13 is preserved as
evidence rather than as a constant: it found that **every single-op raster fire lands
mid-previous-row** (the restore's zero-delay bracket start and a bare single-op CRAM fire
spilled identically), and the solver now reproduces 13 as the *latest* spin whose 3-word
restore burst still beats the line-start sampling instant. What ships is 10 — centred, and
30 cycles cheaper.

**The guard set** (`raster_dsl.emp`, `raster_program`):
- **One band per program** — at most one restore op per program (a non-aborting `ensure`;
  the first-authored restore is the deterministic representative under a violation).
- **The equal-span-partner composition guard** — every earlier-or-same-line CRAM-span op
  intersecting the restore's span is refused unless it is the unique strictly-earlier op
  with an EXACTLY EQUAL span (the ON op `band()` paired it with). Grounded on
  `check_intervals`, which forces every program's fire-line intervals strictly ascending and
  disjoint — the guard that makes a patchable record's moving line provably stay on one side
  of the restore.
- **Both of a band's fires must be static** — neither the restore's own carrying fire nor
  its partner's carrying fire may be `patchable`. A moving fire on either side can reach
  `.suppress` in `raster.emp` (the schedule-recording path that drops a record outside its
  authored band) and silently un-pair the restore from its partner — closing both directions
  is what makes a band's ON/OFF pairing hold in every anchor state.
- **Single-op restore fire** — the fire carrying `OP_PAL_RESTORE` carries nothing else; no
  `SetReg` or other stream op may compose onto the band's bottom line.
- **Tree-wide `$8F` (autoincrement) and `$8A` (the schedule's own arm register) refusal** —
  a program-level scan over every op's register word (`raster_dsl.emp:1374-1381`) refuses
  both, closing the gap a direct `RasterOp.SetReg($8F04)`/`RasterOp.SetReg($8A05)`
  construction leaves open past the constructor-level (`reg_set`) refusal — a constructor
  refusal alone is not a refusal, since `RasterOp` is `pub`.
- **Program-keyed ship refusal** — a band cannot coexist with an off-screen-ship trailer
  (§7.13) on the same program; verified against both encoder output and runtime install
  state. Section 0 is excluded from bands twice over — by its ship AND because its `[3,220]`
  channel band leaves no legal disjoint interval for a restore.

**The authoring surface.** `band(top, bot, on: RasterOp, sh: 0|1)` owns the whole shape
(`raster_dsl.emp:612`): `sh: 0` emits `[fire(top,[on]), fire(bot,[restore])]`; `sh: 1` emits
the Shadow/Highlight three-fire form (`reg_sh_on()+on` at `top`, `reg_sh_off()` at `bot-1`,
`restore` at `bot`), with the restore's `(addr, count)` derived from the ON op's span so the
equal-span pairing is guaranteed by construction rather than authored twice. Minimum band
height (screen lines from `top` to `bot`, the fire-line gap) is cost-keyed from the real
merged fire cost of the shape `band()` emits: a `pal_region` (or 1-2 word `cram`) ON fire
needs height >= 2; the S/H shape's merged `[reg, tint]` ON fire is measured against the gap
to `bot-1`, so it needs height >= 3. A band is structurally capped at <= 3 CRAM entries (the
`stream_words <= 3` ceiling both the ON op and the restore share).

**Costs (measured, `docs/benchmarks/effects-r1/GATE-EVIDENCE.md`):**
- The restore fire itself: 704 cyc (calibrated body, `RASTER_WORK_RESTORE_CYC = 212` work
  plus dispatch/fetch/tail) — hardware-confirmed via `raster_cost_probe` (F8 fixture, 556 cyc
  pre-calibration / 3 boots, spread 0) and the pixel-landing capture. A fire below a band
  needs a downstream gap of >= 2 fire-lines.
- The snapshot splices: **+347 cyc/frame steady state** (2 dirty lines), **+704 cyc worst
  case** (all 4 lines dirty, e.g. a section transition) — **3.8% of the ~18,565-cyc NTSC
  VBlank window**, confirmed differentially against a splice-free baseline ROM (same scene,
  frozen camera). `VInt_Level`'s own row is unchanged; the cost lives entirely in
  `Enqueue_Dirty_Buffers`.
- **The +16 mixed-fire dispatch tax** (a patchable fire composing `SetReg` + `cram`, e.g.
  OJZ's water channel, going from 4 to 5 dispatch rungs) is hardware-confirmed exactly
  (F5 = 628.0 cyc/fire, 3 boots, spread 0) — but its PIXEL-LANDING consequence is
  **unmeasured**: four independent capture protocols failed their own controls (camera/
  `Logic_Tick` phase drift dominated the boundary-region signal). The `docs/superpowers/
  2026-08-16-parcel-r1-palette-bands-v6.md` §3.3 fallback slot stays **VACANT** (owner
  ruling: measure first, rule only on a measured failure — none is evidenced) and the
  precision re-measure is booked against the render-anchoring parcel (`docs/DEFERRED_WORK.md`).

---

## 8. Tooling & Build System

Build-time tools that convert human-friendly level data into optimized runtime formats, plus runtime debug/profiling systems for data-driven optimization. Commercial Genesis games shipped with zero debug infrastructure; the community (Vladikcomper, Flamewing, S.C.E.) has since built what 90s studios lacked.

**Cross-reference (5 games + S.C.E.):** No commercial game has runtime profiling or assertions. Vectorman is the only game with runtime bounds checking (`illegal` on out-of-range pointers). Batman & Robin is the only game with lag frame detection (dual frame counter comparison). S.C.E. has the most comprehensive debug system: two-phase gating (`if DEBUG_xxx` + `ifdebug`), 10 per-subsystem debug toggles, Vladikcomper MD Debugger v2.6 with crash screen/backtrace/symbol resolution, and a VDP window plane lagometer.


#### The runtime half (Parcel P-b's `Raster_PatchAll`, replaced by `Raster_BuildSchedule` — 2026-08-16)

> **P-b shipped `Raster_PatchAll`, an in-place patcher.** It ran at VBlank and rewrote one arm
> BYTE per patchable record inside the *live* raster buffer — it could move a boundary but never
> remove one, because arm words are relative gaps and a record is left behind only by having been
> walked, and the in-place patcher never controlled which records got walked. The HInt schedule
> local-removal parcel deleted it and put `Raster_BuildSchedule` in its place. The paragraphs below
> describe the current mechanism; where behaviour changed from P-b it says so explicitly.

`Raster_BuildSchedule` runs **at VBlank**, from `Raster_VBlank`, for the same reason `Raster_PatchAll`
had to: every arm word is a **relative** gap to the next fire, and `Raster_HInt` walks the schedule
during active display. Running from the main loop would race that walk — records already passed
would keep stale data, records ahead would get a half-built frame, and because the gaps are
relative the desync propagates down the **entire tail of the chain**. What changed is *what* runs at
VBlank: instead of patching bytes into the buffer `Raster_HInt` is currently reading,
`Raster_BuildSchedule` writes a complete fresh copy into whichever buffer is NOT currently active
(`Raster_Buf_A`/`Raster_Buf_B` swap), then atomically repoints `Raster_Active_Buf` at it. `Raster_HInt`
never observes a partially-built schedule, by construction rather than by timing discipline.

Per record the builder derives `screen_line = Effects_World_Y[ch] - Camera_Y` (via the
`Effects_Screen_L` latch — see `Effects_LatchWorldLines` below), converts once to a fire line
(`-1`), and tests it against the record's authored band: past `band_hi` the record is **not
copied into the new schedule at all**; below `band_lo` it clamps UP to `band_lo` (the frame-top
ship covers what is above); inside the band it follows the anchor. For every record it DOES emit,
it stores the resulting gap as the **low byte** of the `$8Axx` arm word belonging to the record
**two positions back** (Ruling 1b — the word written at record `i` is consumed at the next HInt
reload and schedules the gap landing record `i+2`), tracked through an 8-byte stack-resident
2-deep slot history rather than registers or RAM (this proc runs under `Raster_VBlank`, whose
callers `VInt_Level`/`VInt_Lag` only declare clobbers reaching `d4`/`a2`). The park word `$8AFF`
is an `$8Axx` word too, so re-arming (and parking) is one `move.b`/`move.w` with no `ori` and no
masking — the same low-byte-doubles-as-park-value idea S3K's water HInt counter uses (clamping
`H_int_counter` to `$FF` at `loc_6C8E`, `sonic3k.asm:8509-8515`, rather than special-casing the
disarm), adapted here to a per-record arm word instead of one shared counter variable. The two
youngest slots have no record two positions later, so the builder parks them explicitly after the
walk — which is also what makes the all-suppressed schedule (every record past the two priming
ones dropped) park correctly with no special-case emitter.

- **Liveness is `Raster_Patch_Tab != 0`, never `Active_Buf == Buf_B`.** Unchanged from P-b.
  `Raster_VBlank`'s explicit-clear path zeroes `Raster_Program` but never touches
  `Raster_Active_Buf`, so an Active_Buf-gated builder would keep writing a dead buffer forever
  after a clear. Both teardown paths clear the table.
- **Anchors live in RAM** (`Effects_World_Y[RASTER_MAX_PATCH]`), seeded on section entry from the
  preset's **inline** `ep_patch_world_ys` array. In RAM because that is what makes them movable —
  rising lava, a flood line, a beat-driven pulse all rewrite an anchor through `Effects_SetWorldY`.
  Inline in the preset because a `Label` carries no length, so an `ensure` comparing one to an
  integer is unevaluable and passes silently. Unchanged from P-b/Parcel W.
- **The bank is named `Effects_*`, not `Raster_*`, deliberately.** The world anchor has two readers
  today: `Raster_BuildSchedule` (VBlank) and the parallax overlay (main loop, Parcel W) — a
  complete underwater section is a palette boundary *and* a shimmer at the same line, both driven
  off one anchor via `Effects_LatchWorldLines`'s single per-frame derivation.
- **Off-screen is now TWO different answers, not one clamp.** The deleted `Raster_PatchWaterLine`
  (pre-P-a) had two off-screen branches (above the viewport = fully submerged, fire as early as
  possible; below = park, not visible) that P-b flattened into a single symmetric clamp — a
  **declared, measured delta** at the time, and the DEFERRED_WORK entry this section used to point
  at. The local-removal parcel restored the asymmetry, but not by resurrecting
  `Raster_PatchWaterLine`'s exact branches: **above** the band the record still **clamps** to
  `band_lo` (covered by the separate frame-top-ship trailer mechanism, §7.13, which repaints the
  whole screen above when the latched line reads `<= 0`); **past** the band it is **suppressed** —
  not emitted into the schedule at all, which is closer to "park" than "clamp" but is a property of
  a single VBlank's re-recorded schedule rather than a persistent per-record park flag.

### 8.1 Authoring Pipeline — Editor to ROM

The authoring pipeline decouples the level editor's creative tools from the runtime data formats. The editor works with human-friendly concepts (tiles, blocks, chunks); the build tool converts everything into optimized runtime formats (nametable strips, collision maps, compressed tile art).

**Editor workflow — paint at any granularity:**
- **Tile creation:** Artist draws 8×8 tiles in the art editor. These are the atomic art units.
- **Block creation:** Artist groups tiles into 16×16 blocks (2×2 tiles each) — reusable stamps with per-tile flip/palette attributes.
- **Chunk creation (optional):** Artist groups blocks into 128×128 chunks (8×8 blocks) — larger reusable patterns for terrain structures.
- **Level painting:** Artist paints the level layout using any combination:
  - Place individual 16×16 blocks for fine detail
  - Stamp 128×128 chunks for repeated structures (platforms, terrain patterns)
  - Mix freely — chunks and individual blocks in the same section
- Chunks, blocks, and tiles are **editor-only concepts** — they exist for creative reuse and workflow speed. The runtime never sees them.

**Build tool pipeline (runs as part of `build.sh`):**

1. **Flatten:** Convert each section's layout from chunks/blocks into a flat grid of 8×8 tile references.
2. **Deduplicate tiles:** Identify identical tiles across all sections of the act (including flip variants, via canonical form). Build one master tile set per act (`tools/tile_dedupe.py: dedupe_tiles`).
3. **Spatially order and page the global pool (2.3):** Order the deduped tiles by first occurrence in grid-traversal order (`order_pool_spatially`) so spatially-near tiles land at nearby pool indices, then split the pool into fixed-size pages (64 tiles each, `split_pool_into_pages`) plus a manifest v2 record per page (`{source, tiles, form, flags}`). Each tile gets a permanent global pool index; section nametables carry per-section LOCAL indices translated to global at block-decode time (so a page can reside in any VRAM frame — the §9.7 residency cache precondition). No adjacency graph or per-section index reuse.
4. **Generate nametable strips:** Output raw VDP nametable words (tile index + palette + priority + flip bits) per column per section. Stored in ROM, ready for direct DMA to VDP scroll planes.
5. **Embed collision in strips:** Append 24 collision bytes + 8 padding to each 96-byte nametable column, producing 128-byte wide strips. Collision derived from tile→collision assignments (one type per 16×16 cell).
6. **Compress art and blocks:** ZX0-compress each act art pool page (load-time tier); S4LZ-compress the per-section block stream with its block dictionary (runtime tier). Both carry the 4-byte version wrapper (verified at bake + by the DEBUG selftest).
7. **Report:** Total ROM size per section and per zone. Act art pool page count vs the residency page table (`PAGE_TABLE_MAX`) and the per-act ROM budget (`tools/art_rom_report.py`). Build error if either is exceeded.

**Cross-reference:** Batman & Robin stores level nametable data at `$100000+` in raw VDP format — 16-bit nametable words encoding tile index + palette + flip bits, ready for DMA straight from ROM to VRAM scroll planes. Zero runtime conversion. Our tool does the same thing, but for the section streaming system's per-column strips rather than full-screen pages.

**Build integration:** Tool runs after level data export, before assembly. Outputs `.bin` files that get `BINCLUDE`'d per-section. Reports total ROM size contribution — if nametable strips push past 1.5MB, escalate ROM banking awareness (Section 9.8).

### 8.1b Level Editor Tile Budget UI

The build tool generates tile budget data that the level editor displays in real time, giving artists immediate feedback on VRAM constraints while painting.

**Per-section tile panel:**
- Shared tile count (used by this section AND at least one adjacent neighbor)
- Unique tile count (only this section uses them)
- Color-coded tile palette: shared tiles in one color, unique tiles in another
- Total tile count vs pool budget (1,536 tiles minus permanent allocations)

**Per-corner budget view:**
- For each 2×2 intersection in the section grid, show: total tiles needed by all 4 sections vs budget remaining
- Green / yellow / red indicator (green = comfortable, yellow = within 10% of limit, red = over budget)
- Click a corner to see exactly which tiles are shared vs unique to each of the 4 sections

**Warning system:**
- **Build-time error** if any corner exceeds the tile budget — ROM will not build
- **Build-time warning** when any corner is within 10% of the limit
- **Smart suggestions:** "Sections A and C have 12 tiles that differ by only flip — merging saves 12 slots"
- **Flip-variant detection:** Identify tiles that are horizontal/vertical flips of existing tiles (VDP handles flipping for free via nametable bits)

**Why this matters:** Without budget visualization, artists would paint sections in isolation and discover at build time that a 4-way corner exceeds the 1,536-tile pool. The budget UI makes VRAM constraints visible during the creative process, not after it.

### 8.2 Debug System Architecture (from S.C.E. + Vladikcomper + Vectorman)

**Two shape flags, four idioms.** The S.C.E.-style per-subsystem flag layer (`DEBUG_ALL` / `DEBUG_DMA` / …) was evaluated and never built: a check either belongs in the DEBUG shape or it does not, and a second dimension bought nothing but a matrix of untested shapes. `DEBUG` (`-D DEBUG=0|1`; `__DEBUG__` on the AS side) is that one flag and still means exactly "the debug shape". The second flag is not a subsystem layer but a *category* split, owner-ruled 2026-08-04: `CRASH_REPORT` (`__MDDBG__` on the AS side) separates **diagnostics, which ship**, from **debug equipment, which does not**. The idioms both drive — self-gating `assert`, hand-wrapped `if DEBUG == 1 { raise_error … }`, comptime `ensure(...)`, and registry-level whole-file exclusion — are specified in `CODING_CONVENTIONS.md` §1.7, which is the canonical statement. There is no `ifdebug`/`debugend` layer in `.emp` (the AS `ifdebug` macro survives in `engine/debug/debugger.asm` with zero users) and no profiler overlay.

**Build shapes (three):**

| shape | asserts / hotkeys / selftest / boot autoplay | MD Debugger + deb2 symbols | fault vectors point at |
|---|---|---|---|
| **debug** (`DEBUG=1`) | yes | yes | `error_handler` per-class stubs |
| **release** (default) | no | yes | `error_handler` per-class stubs |
| **lean** (`sigil build --native --lean`) | no | no | `ReleaseFault` |

`DEBUG=1` adds the assertion expansions, the debug-only raise sites, and the debug-only modules (`compression_selftest`; `game_debug` at the hotkeys shape), and emits suffixed artifacts (`s4.debug.bin`). Release assembles none of that. Both canonical shapes carry the error-handler island and the deb2 symbol appendix consumed by MD-Debugger, so a player's crash is reportable — the ruling is that the release ROM is ~9% of a 4 MB cart and space does not decide this. Only the opt-in `lean` profile drops the island, and it routes every fault at `ReleaseFault` (mask, red backdrop, freeze) so the loud-failure ruling still holds there.

### 8.3 Error Handler (Vladikcomper MD Debugger v2.6)

**Cross-reference:** Commercial Genesis games had minimal exception handling. Vectorman points all exception vectors to `$000000` (relies on dev hardware catching null jumps). Gunstar Heroes and Alien Soldier use unique 4-byte stubs per exception type for identification in stack traces. Batman & Robin packs error type IDs into the high byte of exception vector addresses (`$0240800C` = error ID `$02`, handler at `$800C`) — the 68000's 24-bit address bus ignores the high byte, but it's readable on the exception stack frame. Thunder Force IV gives each exception 12 bytes of handler space for in-place diagnostic code.

**Our approach:** Vladikcomper's MD Debugger v2.6 surpasses all of these. Integrated as a pre-compiled ~3.8KB blob with:

- **All 68000 exception types handled:** Bus error, address error, illegal instruction, divide by zero, CHK, TRAPV, privilege violation, trace, Line-A/F emulators. Each displays a human-readable error message.
- **Register dump:** All d0-d7 and a0-a7 with symbol resolution for address values.
- **Backtrace:** Walks the stack looking for return addresses and resolves them to symbol names. Available via button press on crash screen (A = address register details, B = backtrace, C = configurable).
- **Symbol resolution:** `convsym` extracts symbols from the AS assembler listing file and appends them to the ROM. The error handler reads this table at runtime to resolve any address to its nearest symbol name. Must be the very last thing in ROM.
- **Bus/address error details:** The 68000's exception stack frame includes the faulting access address, a read/write flag, and function code (code vs data space). The error handler decodes these for immediate diagnosis.
- **`RaiseError` macro:** Manual error raising with formatted strings and register value interpolation. Used at system boundaries (see 8.4).
- **`assert` macro:** Conditional check with automatic error message generation. Saves and restores CCR so it can be inserted between any two instructions without side effects: `assert.l mappings(a0),ne` crashes if an object has null mappings.
- **Console programs:** `RaiseError` can specify a console program that runs after the crash screen for extended diagnostics — formatted table dumps, human-readable descriptions of error codes.
- **Works on real hardware and all emulators.** No emulator-specific features required.

### 8.4 Per-Module Debug Assertions (from S.C.E., enhanced with Vectorman patterns)

Proactive `RaiseError` checks at every system boundary. Each gated behind its `DEBUG_xxx` flag. Catches bugs at the source, not at the crash.

**S.C.E. assertion sites (ported to our systems):**
- DMA queue overflow — `cmpa.w #DMA_queue_end,a1` before enqueue
- Plane buffer overflow — `cmpa.w #Plane_buffer_end,a0` before write
- S4LZ decompression buffer overflow — bounds check on queue pointer
- Object slot bitmask overflow — bounds check against 64-object-per-section limit
- Ring slot buffer overflow — bounds check against expanded ring count vs buffer size
- Ring pattern expansion — validate count + spacing don't exceed section bounds
- Object type table index — bounds check 5-bit type index against section's table size
- Render sprites invalid object — `assert.l code_addr(a0),ne` and `assert.l mappings(a0),ne`
- MegaPCM/Flamedriver sample table errors — error code + human-readable description via console program

**Vectorman-inspired additions (NOVEL):**
- **Pointer bounds checking before indirect calls:** `cmpa.l #ROM_End,a0` before any `jsr (a0)` through a function pointer. Catches corrupted pointers before they cause an address error in a completely unrelated location.
- **Debug breadcrumbs:** Save function pointer, object pointer, and parameter to fixed RAM addresses before indirect calls. These survive a crash and can be inspected in the emulator memory viewer for post-mortem diagnosis. Zero cost in release (compiled out).
- **Parameter corruption detection:** After returning from an indirect call, verify that caller-saved registers weren't corrupted. `cmp.w saved_value,dn; bne RaiseError`. Catches register clobbering bugs that would otherwise manifest as mysterious later failures.

**CHK instruction bounds checking:** The 68000's `chk #MAX,Dn` auto-triggers a CHK exception (vector 6) if Dn < 0 or Dn > MAX. 10 cycles when in-bounds — comparable to a CMP+BCC pair but in one instruction. Use for: jump table dispatch indices, object slot indices, animation frame range, VRAM tile indices. Compiled out in release via conditional assembly. No commercial Genesis game uses CHK for bounds checking — it was designed for Pascal compilers, but it's a perfect fit for our debug system.

### 8.5 Frame Profiler (NOVEL — no Genesis game has this)

Two complementary profiling approaches, both debug-only:

**Raster bar profiler (backdrop color technique):** Change CRAM entry 0 (backdrop color) at key code boundaries to visualize timing as colored horizontal bands. The band height directly corresponds to CPU time consumed. If colors extend past the active display area, you're overrunning the frame budget. Creates "CRAM dot" artifacts (single rogue pixels) during active display — acceptable for debug. Implementation: write to VDP data port with CRAM write command pre-loaded.

**VDP window plane lagometer (from S.C.E.):** Before the VSync wait loop, set window plane H position to default (hidden). After VSync completes, shift the window plane right. The visible bar width shows how much frame budget was consumed. No RAM variables needed — just two VDP register writes per frame. Cleaner than raster bars (no CRAM dots) but less granular (shows total frame time, not per-system breakdown).

**KDebug timer interface (from S.C.E.):** Writes to VDP register `$9F` are intercepted by Gens KMod and compatible emulators as debugger commands. `KDebug.StartTimer` / `KDebug.EndTimer` measure exact cycle counts between two points. `KDebug.BreakPoint` pauses emulation. Only works in KMod-compatible emulators, but provides the most precise timing data. The `KDebug` macros self-gate on `__DEBUG__` (see `engine/debug/debugger.asm`).

**Lag frame detection (from Batman & Robin):** Dual frame counters — VBlank increments one, main loop samples it with a threshold comparison. If VBlank has fired multiple times before the main loop finished, lag is detected. Batman uses `addq.l #2; cmp.l` to allow up to 1 frame of slack. Our implementation: `Lag_frame_count` incremented in VBlank, reset in main loop. Value > 1 = lag frame. The profiler overlay displays a lag indicator.

**Stack depth tracking:** Place sentinel word `$DEAD` below the stack base. VBlank checks it once per frame — if overwritten, the stack has overflowed. Zero cost on the happy path (one `cmpi.w`). No commercial Genesis game has stack overflow detection.

**Watchdog timer:** VBlank increments a counter, main loop resets to zero. Counter reaching 3 means the main loop hung for 3 frames. Error handler fires with context showing where the main loop was stuck (PC from the VBlank stack frame). Zero cost on the happy path.

### 8.6 RAM Layout Documentation (NOVEL)

Build-time script that parses the RAM region declarations (`engine/ram.emp` + `games/<game>/config/ram.emp`) and outputs a visual RAM map showing all regions, sizes, and remaining free space. Flags overlapping regions, warns if any region exceeds its budget. (The hard-overflow half is already covered: `.emp` region declarations are compiler-checked by sigil.) Prevents the silent RAM collisions that plague Genesis development.

**Cross-reference:** S.C.E.'s `Variables.asm` uses `phase`/`dsset` directives with a compile-time overflow check: `if * > 0; fatal "RAM declarations too large by $\{*} bytes."; endif`. Our script goes further — it generates a visual map and warns about near-misses, not just hard overflows.

**Integration with sprite table safety:** Any RAM layout change that shifts `Sprite_Table` triggers a warning, preventing silent misalignment bugs.

### 8.7 Build System Improvements

**Jump size specification (from AS assembler analysis):** AS is a multi-pass assembler — forward references cause instruction length changes between passes, triggering additional passes. Some programs require up to 12 passes. Explicitly specifying `.s`/`.w`/`.l` on all branch/jump instructions eliminates this iteration entirely. Single-pass assembly is **10-50× faster** than multi-pass resolution. The `-r` flag issues warnings about pass-forcing situations, useful for finding branches that need explicit sizing.

**Dual build targets (from S.C.E.):** `build.sh` (release) and `build_debug.sh` (debug) with identical pipelines except for `-D __DEBUG__`. Both generate listing files and symbol tables.

**Symbol generation pipeline (from S.C.E.):**
1. `convsym S4.lst s4.bin -input as_lst -range 0 FFFFFF -exclude -filter "z[A-Z].+" -a` — append ROM symbol table (excludes Z80 symbols)
2. `convsym S4.lst S4_RAM.lst -in as_lst -out asm -range FF0000 FFFFFF` — generate RAM-only symbol file for emulator memory watches

The ROM symbol table must be appended after all other ROM data. The error handler reads it at runtime for address-to-symbol resolution.

**Assembly pass checking (from S.C.E.):** At end of assembly, check `MOMPASS` against a maximum allowed pass count. Warn if the assembler needed more passes than expected — indicates new forward references or unsized branches were introduced.

**Compile-time validation macros:**
- `clearRAM`/`copyRAM`: Fatal error if start > end, warning if clearing zero bytes
- `org` macro: Fatal error if org address would overwrite previously assembled bytes
- `QueueStaticDMA`: Fatal errors for odd source, odd length, zero length, 128KB boundary crossing
- `zonewarning` (from S.C.E.): Fatal if any zone-indexed table doesn't match `ZoneCount` — catches mismatched table sizes when adding levels

**Level editor integration:** SonLVL via `./run_sonlvl.sh`, exports to formats compatible with the nametable build tool.

### 8.8 Exodus MCP Integration (NOVEL)

Live emulator debugging via the Exodus MCP server, configured in `.mcp.json`. Direct inspection of hardware state without theorizing:

- **VRAM inspection:** Verify art loaded to correct tile addresses (tile index × 32 = byte address)
- **CRAM inspection:** Verify palette data (64 entries, 2 bytes each)
- **VDP registers:** Scroll positions, display settings, interrupt state
- **68k registers and RAM:** Object state, variable values, execution state
- **Breakpoints and watchpoints:** Set on specific addresses or conditions
- **Symbol loading:** Load `S4.lst` symbols for address resolution in all debug views

Direct observation beats guesswork. When a visual bug occurs, look at VRAM/CRAM/RAM directly rather than theorizing from code.

### 8.9 Cascade Effects

**Profiler → DMA budget:** Profiler data directly informs the adaptive DMA byte budget (§1.1). Measured VBlank usage determines safe DMA thresholds rather than guessing.

**Debug assertions → stability:** Every `RaiseError` site is a potential crash point caught during development. The assertion list grows as new systems are implemented — each new subsystem adds its own `DEBUG_xxx` flag and boundary checks.

**Symbol table → error handler → crash diagnosis:** The `convsym` → ROM append → `RaiseError` pipeline means every crash shows human-readable function names, not hex addresses. This turns multi-hour debugging sessions into minutes.

**Build validation → correctness:** Compile-time checks (`zonewarning`, `clearRAM` validation, org overlap detection, assembly pass counting) catch entire categories of bugs before the ROM is even built. These are effectively unit tests for the build system.

**RAM layout tool → sprite table safety:** The RAM documentation tool visualizes exactly what's adjacent to `Sprite_Table` and flags address-dependent regions, preventing silent misalignment bugs.

---

## 9. Cross-Cutting Systems

Systems that span multiple clusters or coordinate between them. These are the connective tissue that makes the engine work as a coherent whole rather than a collection of independent subsystems.

**Cross-reference (5 games + S.C.E.):** Every commercial Genesis game has cross-cutting coordination, but none have formalized it. Batman & Robin's bytecode yield system is the most sophisticated coordination mechanism (script pointer IS the state). Treasure's link fields ($58/$5C) coordinate multi-part bosses across 380+ references. S.C.E. has the cleanest level database (per-zone directories with `levartptrs` macro packing). No commercial game has SRAM save functionality among the 5 analyzed.

### 9.1 Level Database — Unified Level Descriptors (replacing Zone ID system)

A unified level database that consolidates all per-level configuration into a single self-contained descriptor per level. Eliminates the scattered-table pattern (common in Genesis engines) where adding a new level requires touching 12+ files with synchronized table entries.

**Evolution of level data organization across engines:**

| Engine | Approach | Tables to touch for new level |
|--------|----------|-------------------------------|
| Sonic 2 | Scattered fixed-size tables, zone ID indexing | 12+ files, 17 entries each |
| Sonic 3K | Level Load Block (semi-unified, high-byte packing) | 6+ files, still scattered |
| S.C.E. | Per-zone directories with `Pointer.asm` files | 4-5 files, mostly in zone dir |
| Batman & Robin | Binary level tables at `$021400` (11KB block) | 1 binary file |
| **Sonic 4 (target)** | Single descriptor per level, one file per level | **1 file** |

**S.C.E.'s approach (current best-in-class community):** Each zone has its own directory under `Levels/` containing `Blocks/`, `Chunks/`, `Collision/`, `Layout/`, `Palettes/`, `Pointers/`, etc. The `Pointer.asm` file per act uses the `levartptrs` macro to pack 23 parameters (art, blocks, chunks, layouts, collision, objects, rings, palette, music, water flag) into a flat RAM structure. Palette ID, water palette, music ID, and water flag are packed into the high bytes of longword art/layout pointers — eliminating separate lookup tables.

Loading: `LoadLevelPointer` calculates zone×act offset, then bulk-copies the entire pointer block ($A2 bytes) via unrolled `movem.l` into `Level_data_addr_RAM`. One copy operation instead of dozens of individual table lookups.

**Compile-time safety:** S.C.E.'s `zonewarning` macro fatals if any zone-indexed table doesn't match `ZoneCount`. Catches mismatched table sizes at build time.

**Our target architecture:** Go beyond S.C.E.'s approach. One self-contained level descriptor file per level containing ALL data pointers, configuration values, and section definitions:

```
LevelDescriptor_OJZ1:
    ; Art pointers (high byte = palette ID)
    dc.l (Pal_OJZ)<<24|ArtS4LZ_OJZ_FG
    dc.l ArtS4LZ_OJZ_BG
    ; Layout, collision, objects, rings
    dc.l Layout_OJZ1, Collision_OJZ
    dc.l ObjLayout_OJZ1, RingLayout_OJZ1
    ; Section table pointer
    dc.l SectionTable_OJZ1
    ; Music, water, physics
    dc.w Music_OJZ, 0  ; music ID, water flag
    dc.l PhysicsTable_OJZ  ; per-section terrain physics (5.2)
    ; Scroll/parallax definition
    dc.l DeformScript_OJZ  ; 8-layer parallax definition (4.6)
    ; Event hooks (function pointers, 0 = none)
    dc.l ScreenEvent_OJZ, BackgroundEvent_OJZ
    dc.l AnimatePalette_OJZ, AnimateTiles_OJZ
```

Adding a new level = write one descriptor file + add one `include` line to the level index. No scattered tables, no fixed slot counts, no dead entries.

### 9.2 Object Communication — Hierarchical Links + Flag Array

Objects communicate through three mechanisms, chosen by coupling tightness:

**Parent-child link fields (from Treasure, validated at scale):** Two dedicated SST offsets store object pointers for hierarchical coordination. Gunstar Heroes uses one link field ($58) with 71 references; Alien Soldier evolved to two ($58 + $5C) with 484 total references. Boss sub-objects read parent state (`btst #status.defeated,status(a1)`) and position themselves relative to parents every frame.

Our implementation uses `parent_ptr` and `sibling_ptr` fields in the SST. S.C.E.'s 12 child creation routines (`CreateChild1_Normal` through `CreateChild12_Simple`) demonstrate the full range of parent-child patterns: simple children, linked lists, tree lists, repeated spawns. `DeleteFamily` cascades to all children when a parent is destroyed.

**Level trigger array (from S.C.E.):** A 16-byte shared flag array indexed by trigger ID. Button objects set bits; door/platform objects read them. Simple, fast (one byte read per frame), and decoupled — the button doesn't know what it opens, the door doesn't know what opens it. The trigger ID in the object subtype byte is the only connection.

**Boss event buffer:** 32 bytes of boss-specific shared state for complex multi-phase boss coordination. Phase transitions, attack patterns, and defeat conditions communicate through this buffer rather than direct SST reads.

**Why not a general event/message system:** No 16-bit commercial game uses event dispatch or message queuing. The overhead of dispatch tables and message queues is not justified at 7.67 MHz with 64KB RAM. Direct flag reads and parent-child links are cheaper and sufficient for all known use cases. The three mechanisms above cover: tight coupling (parent-child links), loose coupling (trigger array), and domain-specific coordination (boss events).

### 9.3 Error Handler with Stack Guard

**Exception vector engineering (from Batman & Robin + Thunder Force IV):** Pack error type IDs into the high byte of exception vector addresses. The 68000's 24-bit address bus ignores the high byte, but it's preserved on the exception stack frame. One shared handler can identify the exception type without needing separate handlers. Batman uses `$02-$07` for Bus/Address/Illegal/Zero/CHK/TRAPV. Thunder Force IV gives each exception 12 bytes of handler space — enough for in-place diagnostic code.

**Our approach combines both:** Exception vectors use high-byte IDs (Batman technique) pointing to the Vladikcomper MD Debugger (Section 8.3). The error handler decodes the ID and displays the appropriate error message with full register dump, backtrace, and symbol resolution.

**Stack guard word:** Place `$DEAD` below the stack base during init. VBlank checks once per frame — `cmpi.w #$DEAD,(Stack_guard).w; bne RaiseError`. If overwritten, the stack overflowed. Zero cost on the happy path. No commercial Genesis game has stack overflow detection.

**Watchdog timer:** VBlank increments counter, main loop resets to zero. Counter reaching 3 = main loop hung for 3 frames → error handler fires with the VBlank's saved PC showing where the main loop was stuck. Zero cost on the happy path.

### 9.4 6-Button Controller Support

**Status: SHIPPED (input parcel 2026-08-02, `engine/system/controllers.emp`).** `Read_Controllers` runs a full 6-button burst on **both** pads once per VBlank (from `VInt_Level` / `VInt_Lag`), with per-frame pad-type detection. The whole two-port burst runs under one `with z80_stopped { … }` bracket — Z80 access to the 68k bus during `$A100xx` I/O reads corrupts them (hardware bug; plutiedev / SGDK `HALT_Z80_ON_IO` / Vectorman's bus-request lock).

**Read burst (per port).** LOW-first cadence (SGDK/plutiedev standard, verified against oracle's `MDControl6` model — the internal counter advances on TH *rising* edges, so a HIGH-first burst samples the extended phases a half-cycle early and always degrades to 3-button). Eight alternating TH writes starting `$00`, read after the first seven, 2-nop settle each:
- `r2` (TH=1) → `1CBRLDU` main buttons; `r1` (TH=0) → `0SA00DU` (Start/A)
- `r5` (TH=0) → D-pad nibble all-zero = **signature #1**
- `r6` (TH=1) → `1CB MXYZ` extra buttons
- `r7` (TH=0) → bits 3-2 read `%11` = **signature #2**

**Detection = BOTH signatures required** (SGDK's rule: the all-zero nibble alone is faked by a 3-button pad holding U+D, which signature #2 then rejects). Re-confirmed **every frame** — hot-plug just works, and a glitched frame degrades to 3-button data for one frame instead of latching a wrong type. 3-button/SMS/empty ports resolve to `PAD_3BTN` with ext bytes 0. The existing SOCD guard (L+R / U+D cancel) still applies to the fused main byte.

**Outputs (RAM, engine-owned, `engine/ram.emp`).** Per pad `x` = 1,2:
- `Ctrl_x_Held` / `Ctrl_x_Press` / `Ctrl_x_Press_Accum` — main `SACBRLDU` (existing cells, unchanged for every existing consumer)
- `Ctrl_x_Ext_Held` / `Ctrl_x_Ext_Press` / `Ctrl_x_Ext_Press_Accum` — `0000MXYZ` (0 on a 3-button pad; oracle mapping D0=Z, D1=Y, D2=X, D3=Mode)
- `Pad_x_Type` — `PAD_3BTN` / `PAD_6BTN`, refreshed per frame

**Edge detection + lag-safe latch:** `Read_Controllers` ORs press edges into `*_Press_Accum` on **every** VBlank (including lag frames), via the EOR+AND trick (`eor` finds changed bits, `and` isolates newly-pressed). `VInt_Level` then latches `*_Press_Accum → *_Press` and clears the accumulator once per completed tick — so a press landing in any lag frame survives into the next logic tick (consume-once, no race). The 6-button ext bytes latch the same way.

**Deterministic timebase + record/replay (§0.10, `Logic_Tick`).** `GameLoop` increments `Logic_Tick` (u32) once per game tick after `VSync_Wait` — lag-immune, unlike `Frame_Counter` (a raw VBlank count) — then calls `Input_Tick` (`engine/system/replay.emp`), the single replay seam, before the state dispatch. `Input_Tick` reads `Input_Source`: **LIVE** (0) passes the pads through untouched; **PLAYBACK** (1) overwrites `Ctrl_1_Held`/`Ctrl_1_Press` from an ARP0 RLE stream (presses derived from the stream's previous byte, never the live pad — the S1/S2 input-bleed desync class killed structurally; a live Start sets `Replay_Exit_Request` without polluting the stream); **RECORD** (2, DEBUG-only) taps the latched pad into an 8 KB ring and emits a curated-state checkpoint every 64 ticks. `Replay_Hash` (longword sum+rol over `Logic_Tick` + Player 1 SST + camera + section-streaming cells + pool counts) is the desync net, with a DEBUG desync trap. `tools/replay_pack.py` packs/dumps streams. **Shipped** (parcel I3, DEBUG record + LIVE/PLAYBACK): the mechanism and one committed fixture. **Deferred:** title/attract-mode menu integration (game-side wiring), player-facing replay saving, and CI/strict-suite integration (needs headless oracle) — see the spec `docs/superpowers/specs/2026-08-02-input-replay-design.md`.

**Uses for extra buttons (game-side):** X/Y/Z/Mode are exposed to game code via the `_Ext_*` cells for debug shortcuts (frame advance, profiler toggle) or gameplay features. The engine only reads/exposes them; mapping is the game's.

### 9.5 Soft-Reset Handling

**What ships:** soft-reset *detection* + DMA safety, and nothing else. `EntryPoint`
distinguishes warm from cold boot, `Warm_Boot` waits out any in-flight DMA, then falls
through to the full `Cold_Boot` init. Every boot clears all 64 KB and re-inits all
hardware; **nothing survives a soft reset by design.** See §0.11.

**CrossResetRAM persistence: RULED OUT 2026-08-05 — design deleted.** The S.C.E.-derived
scheme (a magic-gated RAM region preserving zone/act, music state, checkpoint, HUD across
a RESET press) is not on the roadmap and its description has been removed from this doc
rather than left standing as a design nobody is building. It had survived two review
passes with zero code and no scheduled work, and it repeatedly produced FALSE review
findings — reviewers kept "discovering" that boot wipes a region that never existed.
Persistence in this engine is **SRAM (§9.6)**, which survives power-off and is the right
home for saves, best times and unlocks. See §0.11 for the full reasoning.

### 9.6 SRAM Save System

> **Status: PLANNED design — not one line implemented (verified 2026-08-04).** No SRAM code exists in the tree, and neither shipped header declares SRAM (`sram` reads 12 spaces at `$1B0` in both `games/sonic4/config/header.emp` and `games/demo/config/header.emp`). This matters more than it used to: §0.11 and §9.5 rule out cross-reset RAM persistence *on the grounds that SRAM is this engine's persistence mechanism*, so until the design below is built the engine has no persistence at all. Everything below is the intended design.

**Hardware (from web research + plutiedev):** SRAM mapped at `$200001+` (odd bytes only due to 8-bit SRAM chip on D0-D7 via /LWR). Controlled by register `$A130F1`: write `$01` to enable SRAM, `$00` to disable. Standard capacity: up to 32KB usable (64KB address range / 2 for odd-byte access). Battery-backed with CR2032.

**ROM header declaration:** Offset `$1B0` must declare SRAM: `dc.b "RA", $F8, $20` with start/end addresses. Some emulators (BizHawk) won't enable SRAM without correct header.

**Implementation (from Sonic 3's proven approach):**
- Store save data twice (primary + backup) for redundancy
- Each copy has its own byte-sum checksum
- On load: verify primary checksum. If corrupt, try backup. If both corrupt, initialize fresh.
- Include a version byte for forward-compatible save data
- First-run detection: magic signature at start of SRAM. If absent, initialize all SRAM.
- Lock/unlock discipline: disable SRAM writes when not actively saving to prevent accidental corruption.

**Save data contents:** Section coordinates, collected items, unlocked zones, total play time, star post state. Compact — under 256 bytes per save slot, allowing 4+ slots in the smallest SRAM.

**ROM banking interaction:** For ROMs >2MB that also need SRAM, a mapper switches the `$200000-$3FFFFF` range between upper ROM banks and SRAM. Sound data and frequently-accessed code should live in bank 0 (`$000000-$07FFFF`, fixed) to avoid switching conflicts.

### 9.7 Idle-Time Deferred Work — Pre-Chunked Pages + Supervisor Bookmark

> **Status: SHIPPED (art-streaming Phase 2, `feat/art-streaming-p2`, 2026-08-09).** The
> driving consumer — mid-game act art-page decode — is live: a resumable stack-flat ZX0
> decoder (`ZX0R_Decompress`) sliced across idle time by a VBlank supervisor bookmark,
> feeding a VRAM page residency cache. This section is the design AS BUILT; the earlier
> user-mode/supervisor cooperative-multitasking proposal it replaced is recorded as
> **rejected** at the end.

Deferred CPU work (mid-game art-page decode, any future oversized decompression) runs
in main-loop idle time — the `VSync_Wait` spin — structured in two layers. This is the
mechanism three shipped Genesis codebases independently converged on (S3K
`Set_Kos_Bookmark`, Ristar's `$FFE5BC` yield protocol, S.C.E. KosPlusM), hardened with
contract enforcement they didn't have.

**Layer 1 — granularity (pre-chunking).** Work arrives pre-cut at build time into units
sized for the common idle window: act art pools are split into pages (64 tiles = 2048 B
raw, KosM's $1000-granule precedent; page size is a build knob, swept on the stress
fixture). Small units mean the *scheduler* needs no time model — most units simply fit.
Pre-chunking alone is not sufficient at the measured worst windows (a 2 KB page ≈ 45 K
cycles vs ~42.5 K average idle in a diagonal-fall window, 2026-08-05 measurement), which
is why Layer 2 exists.

**Layer 2 — preemption (the supervisor bookmark).** The unit decoder runs as a
straight-line supervisor-mode loop in the idle spin. If VBlank fires mid-decode,
`VBlank_Handler` — immediately after its register save, before the `VBlank_Ready` test —
checks the interrupted PC (read from the known stacked-frame offset behind exported
symbols) against the resumable range `[ZX0R_Decompress, ZX0R_Decompress.__end)`; on a hit it
records the PC and redirects the handler's `rte` into `PageIn_BankRegs`, which banks the
decoder's registers + SR to RAM and returns to the main loop. Next frame, the dispatcher
manufactures the frame back (push SR, push PC, `rte`) and the decode continues
mid-instruction-stream. Spawn, resume, and preempt-resume are one code path (Ristar's
manufactured-bookmark trick). Cost: ~300-400 cycles per preempted frame (~0.3%) — decode
consumes ALL idle with near-zero overshoot, and unit size becomes a density/manifest
tradeoff, not a latency constraint.

**The resumable-region contract** (compiler-enforced by the Sigil `@resumable`
attribute; the three invariants every shipped bookmark traces to):
1. **Stack-neutral:** no push/call anywhere in the range — abort is "don't resume", and
   resume works from any stack depth. The resumable ZX0 variant inlines its elias reads
   and takes caller-owned registers.
2. **Register-resident state:** all decoder state in d0-d2/a0-a2 + CCR at every
   instruction (the banked SR word carries the live carry/X flags); the bookmark record
   is 34 bytes (d0-d2/a0-a3 + PC long + SR word).
3. **One contiguous PC range, symbol-exported**, checked only in the VBlank handler. The
   bookmark is the V-int's **final act** — the check runs at handler entry but the
   redirect fires at `rte`, after `VInt_Level`'s whole pipeline. The correct lag lemma
   (**corrected in execution — the drafts overstated it**): the bank is SAFE on
   *whichever* path dispatches, NOT "the lag path can never bank." Because the hook runs
   before the Ready/dispatch split, it banks the decode on either path. Counterexample
   (reviewer-proven): after `VBlank_Ready := 1`, a VBlank landing during the ~150-cycle
   pre-decoder setup window (the resume restore/push) correctly does NOT bank (PC outside
   the range), runs `VInt_Level`, and clears `Ready`; the decode then runs to the NEXT
   VBlank with `Ready = 0`, which dispatches `VInt_Lag` and banks there. Safe either way
   (the main loop is parked in the decoder, so `Plane_Buffer` is already drained and
   `VInt_Lag`'s skipped drain is a no-op; the banked context survives via the movem
   round-trip), but it costs **one benign lag frame at roughly per-resume probability** —
   a known, characterized residual, not a defect.

Additionally: no VDP, no Z80, no shared-RAM writes from inside the range — decode targets
a private staging buffer; publication is the dispatcher's single aligned write + DMA
enqueue after completion (atomic wrt interrupts, no critical sections).

**Admission & gating (per-tier priority disciplines).** Requests queue in a small
two-priority FIFO: demand (a fill is stalled) ahead of prefetch (leading-edge
speculation). Demand decodes and resumes are **never gated** — a stalled fill is the
highest-priority deferred work, and a suspended decode holds the single staging slot, so
finishing it is always better than freezing it. The disciplines layered on top, learned
in the soak:
- **Demand-first prefetch yield:** speculative prefetch returns immediately while a
  demand stall is pending (`Cache_Art_Stall` set), so it never competes for the scarce
  dynamic frames the demand needs.
- **Bulk-first drain:** the init bulk-load path drains queued page-ins before enqueuing
  new prefetch, or a many-page fixture livelocks its own init queue (prefetch refilling
  it perpetually).
- **Trailing-lag speculative gate (the shipped block-prefetch H4 pattern, verbatim):**
  a speculative *start* is skipped if the previous frame lagged, via a `page_in`-owned
  `Frame_Counter`-delta latch (NOT the fill-owned `Cache_Pfx_Lag_Flag`), bounded to ≤1
  consecutive skip so sustained lag can't cascade into cold pages. A completing
  speculative page still adds DMA-window pressure and occupies the staging slot during
  exactly the frames already tight; a demand page never is gated.
Gates use trailing indicators only, never VDP beam position: deferred work runs at fixed
points in the frame, so the beam cannot gauge load (measured lesson, 2026-07-16). There
is **no unified cost arbiter** (D2 = C): under the bookmark, deferred CPU is structurally
free (it can only consume idle), and the truly contended resources — DMA bytes, the
single staging slot — are governed by the per-act art budget word, the dual-cap DMA
admission (entries + bytes, Vectorman), and single-flight staging, each its own governor.
The block tier's budget seam in `Tile_Cache_Fill` remains the named adoption point if a
future consumer ever needs cost-denominated arbitration — a comment + this prose, built
nowhere.

**Correctness invariants (DEBUG-audited).** The residency cache is small, concurrent, and
publishes from an interrupt-sliced decoder, so its bookkeeping is guarded by named
invariants rather than trusted:
- **Claim continuity (enqueue-to-publish):** `PageIn_Enqueue` is the SOLE claim site —
  every enqueue path (bulk / demand / prefetch / retry) sets the page's queued bit; the
  claim holds until `PageCache_Publish` clears it (or eviction / flush). This closes the
  page double-load gap (a bulk/in-flight page re-requested and published twice, orphaning
  the first frame). `PageCache_Publish` DEBUG-asserts the page's table entry is
  `NOT_RESIDENT` before stamping — the duplicate-publish catcher, kept permanently.
- **Instantaneous bijectivity:** `AllocFrame`'s `.detach` stamps `pf_page := $FFFF`
  (UNASSIGNED) so a detached, not-yet-published frame belongs to no page; the audit's
  `pf_page == $FFFF` skip then makes `frame → pf_page → Page_Table` round-trip true at
  *every* instant, including the mid-decode in-flight window.
- **Orphan / refcount audit:** a DEBUG routine walks the whole `Tile_Cache_Nametable`,
  recomputes per-frame refcounts from scratch, and `raise_error`s on any mismatch or
  orphaned frame; run after init and periodically during play.

**Operating regime.** Streaming's regime is **windows ≪ pool** — an act whose multi-screen
cache window references only a fraction of the pool at once, so the resident set churns as
the camera moves. Below that threshold the cache **correctly degenerates to fully
resident**: on a small deduped act (OJZ, 10 pages) the 80×60 cache window references ~every
page, so the working set == the pool — 4 of the 10 pages are build-pinned (`pm_flags`
`ART_PAGE_FLAG_PINNED`), and the rest are held resident by refcounts. This is not a limitation to fix —
`AllocFrame` correctly refuses to evict displayed art (loud thrash assert, zero silent
corruption), and the design simply reduces to Phase 1's fully-resident pool for acts that
fit. The stress fixture (`--stress-uniquify`, 2600 tiles / 41 pages vs 15 frames) is the
regime where streaming actually earns its keep and where the acceptance matrix was proven.
Staged nametable words stay section-LOCAL, and the local→global map is applied per word
inside the `PageCache_PatchRun_Seq`/`_Col` copy runs and the prefetch scan (F-3
merge-translation): the full-width
global exists only in a register, the 11-bit nametable field only ever carries the
physical index (≤ 959), and the pool is bounded by `PAGE_TABLE_MAX` pages + the ROM
budget — there is no 2048-tile ceiling. Every section map's entry 0 is the blank tile
(generator-guaranteed, verify-gated), so the shared zero staged block reads as blank
through any map. Eviction order is a per-frame release stamp (`pf_stamp`) scanned at
eviction — oldest evictable frame wins, by construction (F-1).

**Cancel/flush.** Speculative state needs an explicit invalidation path: `PageIn_Flush`
empties the FIFO and drops any suspended decode (main-loop context only). Called at
cache-invalidating transitions (act/zone change); NOT at pure teleport rebases — page
identity is position-independent, so in-flight work stays valid. A published page's DMA
is always allowed to land.

**Consumers:** ZX0 art-page decode (art-streaming Phase 2 — the driving consumer, shipped);
S4LZ streaming for any larger-than-block payloads (§2.1); palette blend during transitions
(~3.8 K cyc/frame — a fixed idle-slot call, no preemption machinery needed). Ring/object
pre-scan was satisfied by the §4.9 entity window and is a non-consumer.

**Rejected: user-mode cooperative multitasking** (this section's previous design, from
plutiedev — a supervisor/user two-task split with SR bit-13 context switches). Zero
shipped adopters in ~15 years across every examined commercial engine (six disassemblies
grepped exhaustively — no SR write ever clears bit 13; B&R uses USP as a 16th scratch
register); TAS is broken as a lock primitive on MD1/MD2; critical sections would need
`trap` syscalls; and it installs a permanent debugging tax — two register contexts,
preemption at any instruction — in an engine whose worst historical bugs were
preemption-window bugs. The bookmark delivers user-mode's two real advantages
(straight-line decoder, all idle consumed) with none of this. Its previously claimed
"~80-120 cycles" switch cost was unsupported; real 68000 timings give ~300-400 cycles for
a full two-way switch in either design — negligible either way, and not why the decision
goes the way it goes.

### 9.8 ROM Banking Awareness

**When needed:** If pre-computed nametable strips, expanded art, or additional music push ROM past 4MB, the SSF2 mapper provides bank switching via 7 registers at `$A130F3-$A130FF`. Bank 0 (`$000000-$07FFFF`) is fixed; banks 1-7 are switchable to any 512KB page.

**Design constraints:**
- Sound data and Z80 driver must live in bank 0 (Z80 accesses ROM through the 68000 bus — bank switches during Z80 ROM access would read wrong data)
- Code must live in bank 0 or handle bank switching transparently
- Decompression from banked ROM requires the correct bank to be mapped before *starting or resuming* a unit — the §9.7 idle-time decoder must map the bank at each start/resume, and a preempted decode's mapped bank must be part of the bookmark record IF banked art ever ships. Today the act art pool lives in a fixed (unbanked) region, so no action is needed; this is the constraint to honor when art moves to a higher bank (see the mega-act ROM-layout note in DEFERRED_WORK)
- DMA from banked ROM works correctly as long as the source bank is mapped when DMA is enqueued (not when it executes — the DMA source address in the queue entry is already physical)

**Implementation:** Only add banking if ROM exceeds 4MB. Track via build-time ROM size checkpoint. If banking is needed, add a `SetROMBank` helper that writes the page number and records the current mapping for restoration.

### 9.9 128KB VRAM Mode (investigated, available for specialized effects)

**From Kabuto hardware notes:** The VDP's 128KB mode (normally for unreleased 128KB VRAM chips) can be enabled on standard 64KB hardware. In this mode, the VDP does byte-wide DMA (writing only the low byte of each word) with a different address mapping: `(((a & 2) >> 1) ^ 1) | ((a & $400) >> 9) | a & $3FC | ((a & $1F800) >> 1)`.

Setting DMA auto-increment to 4 updates every 4th byte, enabling targeted byte-level VRAM modifications without touching adjacent bytes. Page boundaries (1KB increments) require separate writes.

**Potential uses:** Partial tile updates (modifying individual pixel rows within tiles), targeted palette bit manipulation in tile data, byte-granularity VRAM clearing. Titan Overdrive 2 uses this mode for its border rendering effects.

Available as an advanced technique for specialized visual effects if needed. The address remapping is deterministic but complex — any code using it needs thorough testing on multiple hardware revisions.

### 9.10 PC-Relative Addressing Optimization

**Savings:** `lea label(pc),a0` saves 2 bytes and 4 cycles vs `lea label.l,a0` for every reference within ±32KB range. At scale, this adds up significantly.

**Cross-reference (5 engines):** Batman & Robin leads with 986 `(pc)` references. Alien Soldier has 414, Vectorman 325, Gunstar 197. Thunder Force IV has 0 — entirely absolute addressing. S.C.E. has 196, concentrated in objects (130) and engine (44). The pattern is opportunistic but consistent: used whenever a data table is within PC-relative range of its consumer (typically right below the referencing code).

**Our approach:** Systematic conversion during each code area we touch (opportunistic, per genesis-dev skill guidelines). Focus on hot paths first — object dispatch, collision routines, scroll calculations. The most impactful pattern: jump tables with `lea Table(pc,d0.w),a0; jmp (a0)` — saves 2 bytes AND 4 cycles on every dispatch. `moveq #n,dn` (2 bytes) replacing `move.l #n,dn` (6 bytes) for values -128 to +127 is the complementary optimization.

No automated conversion tool exists. Manual conversion guided by the assembler's `-r` flag, which warns about references that could be PC-relative but aren't.

### 9.11 Memory Clearing Optimization

**Three macro variants (from S.C.E.), each for a different size/speed tradeoff:**

1. **`clearRAM` (loop-based):** `moveq #0,d0` + `move.l d0,(a1)+` in a `dbf` loop. Standard clear, compact code. Used for most RAM regions.
2. **`clearRAM2` (fully unrolled):** `REPT` emits inline `move.l` instructions. Zero loop overhead. Used for small regions (<64 bytes) where code expansion is acceptable.
3. **`clearRAM3` (hybrid):** Unrolled inner loop of 16 `move.l`s inside a `dbf` outer loop. Best of both worlds for large regions — maximum throughput without massive code bloat.

**MOVEM-based bulk clear (from web research, fastest known approach):** Zero d0-d7/a0-a6 (15 registers = 60 bytes), then `movem.l d0-d7/a0-a6,(a0)` repeatedly. Each MOVEM writes 60 bytes with one instruction fetch overhead. ~2.4× faster than simple MOVE loops for large clears. Best for level-load clears where code size doesn't matter and speed does.

All macros handle odd start addresses (emit a `move.b` first) and leftover bytes after the main loop. Auto-select `.w` vs `.l` addressing based on whether the address is in the upper 32KB RAM range (sign-extended word addressing).

### 9.12 Cascade Effects

**Level database → every level-indexed system:** Unified descriptors eliminate scattered zone-indexed tables. Every system that needs level-specific data (art loading, collision, music, water, parallax, events) reads from the loaded level descriptor in RAM. One copy at level load, zero per-frame lookups.

**Idle-time decode → decompression throughput:** The §9.7 pages+bookmark path slices a resumable decoder across spare CPU time. Combined with the priority DMA queue (§1.1), this creates a pipeline: the bookmarked decode fills a private staging buffer → the dispatcher enqueues the completed page's DMA → VBlank transfers to VRAM. Each stage runs independently at its own pace, and under the bookmark the decode consumes ALL idle with near-zero overshoot, so a page decodes across as many frames as the idle window needs without stalling the foreground. The same pipeline extends to S4LZ for any larger-than-block payload (§2.1).

**SRAM → player experience:** SRAM (§9.6) provides permanent saves across power cycles, and is the SOLE persistence mechanism — soft-reset persistence was ruled out (§9.5), so a RESET press is a clean restart and progress granularity is whatever SRAM was last written at (checkpoint/star-post granularity).

**Error handler → debug assertions → stability:** The Vladikcomper error handler (8.3) is the foundation. Per-module assertions (8.4) are the sensors. Together, they catch bugs at their source — buffer overflows, null pointers, corrupted indices — before they cascade into mysterious crashes elsewhere.

**6-button controller → debug workflow:** Extra buttons (X/Y/Z) provide debug shortcuts without conflicting with gameplay controls. Frame advance, profiler toggle, and debug overlay cycling are available during normal gameplay in debug builds.

**PC-relative + clearRAM optimization → ROM size + speed:** These are cumulative micro-optimizations. Each individual instance saves 2-4 bytes or a few cycles. Across thousands of references and dozens of RAM clears, the total impact is measurable — tighter ROM, faster level loads, more headroom for content.

### 9.13 Game State Machine

**Purpose:** Drive top-level program flow — which screen is active, how transitions between screens work, and how each screen's main loop is structured. §0.12 ends with "Branch to Game_StateInit" — this section defines what that means.

**Architecture — function pointer dispatch:**

```asm
Game_State:         ds.l 1      ; pointer to current state's main loop routine
Game_State_ID:      ds.b 1      ; numeric state for save/restore and debug display

GameLoop:
        bsr.w   VSync_Wait              ; wait for VBlank flag
        movea.l (Game_State).w, a0
        jsr     (a0)                    ; run current state's frame logic
        bra.s   GameLoop
```

**States:**

| ID | State | Routine | VBlank Mode | Description |
|----|-------|---------|-------------|-------------|
| 0 | `GS_SEGA` | `GameState_Sega` | `VInt_Menu` | Sega logo (TMSS tie-in) |
| 1 | `GS_TITLE` | `GameState_Title` | `VInt_Menu` | Title screen + press start |
| 2 | `GS_MENU` | `GameState_Menu` | `VInt_Menu` | Main menu (1P, options, etc.) |
| 3 | `GS_LEVELSELECT` | `GameState_LevelSelect` | `VInt_Menu` | Debug level select |
| 4 | `GS_LEVEL_LOAD` | `GameState_LevelLoad` | `VInt_Load` | Level loading (art, layout, objects) |
| 5 | `GS_LEVEL` | `GameState_Level` | `VInt_Level` | Gameplay |
| 6 | `GS_SPECIAL` | `GameState_Special` | `VInt_Level` | Special stage |
| 7 | `GS_CONTINUE` | `GameState_Continue` | `VInt_Menu` | Continue screen |
| 8 | `GS_GAMEOVER` | `GameState_GameOver` | `VInt_Menu` | Game over |
| 9 | `GS_ENDING` | `GameState_Ending` | `VInt_Menu` | Ending sequence |
| 10 | `GS_CREDITS` | `GameState_Credits` | `VInt_Menu` | Credits roll |

**State transitions:** Each state routine sets `Game_State` and `Game_State_ID` to transition. The transition itself happens on the next `GameLoop` iteration — no mid-frame jumps, no stack unwinding. Each state is responsible for its own initialization on first entry (detected via a per-state init flag or `objroutine`-style dispatch within the state).

**VBlank mode selection:** Each state sets `VInt_ptr` to the appropriate VBlank handler during its init phase. `VInt_Level` runs the full gameplay pipeline (DMA queue, plane buffer, HUD, sound). `VInt_Menu` runs DMA queue and sound only. `VInt_Load` runs DMA queue and S4LZ processing.

**Init/teardown:** Each state has an init routine (load art, set palette, configure VDP, install VBlank mode) and implicit teardown (next state's init overwrites everything). No explicit teardown needed — the init fully owns the hardware state.

**Pause sub-state:** During `GS_LEVEL`, Start button triggers a pause overlay (darken palette, show "PAUSED" text, stop object updates, keep sound driver running). Unpausing restores palette and resumes. This is a sub-state within `GS_LEVEL`, not a top-level game state — the level state is preserved.

**Cross-references:**
- §0.12 Boot Sequence: cold boot ends at `Game_StateInit` → `GS_SEGA`
- §1.4 VBlank Structure: `VInt_ptr` selects handler per game state
- §9.5 Soft-reset handling: warm boot waits out in-flight DMA then runs the full cold init — it does NOT resume with preserved state (persistence ruled out 2026-08-05)

### 9.14 Text & Font Rendering

**Purpose:** Render text strings to VDP nametable planes for HUD, menus, debug console, title cards, and any screen that displays text. Every Genesis game needs this; no architecture doc should omit it.

**Font storage:** A single 96-character ASCII font (characters $20-$7F) stored as uncompressed 8×8 tiles in ROM. Loaded to a fixed VRAM region within the unified art pool (§2.3) during any state that needs text. ~3 KB ROM (96 tiles × 32 bytes). A second bold/outlined font variant for title cards costs another 3 KB.

**Tile mapping:** Character code → VRAM tile index: `tile = VRAM_Font + (char - $20)`. Palette and priority bits added per-context (HUD uses palette 0, menus use palette 1, debug uses palette 3).

**String rendering API:**

```asm
; Draw null-terminated string to plane
; a0 = string pointer, d0 = VDP nametable command (position), d1 = base art_tile word
DrawString:
        move.l  d0, (VDP_ctrl_port).l   ; set VRAM write position
.loop:
        moveq   #0, d2
        move.b  (a0)+, d2               ; read character
        beq.s   .done                   ; null terminator
        subi.b  #$20, d2                ; ASCII to tile offset
        add.w   d1, d2                  ; add base tile + palette bits
        move.w  d2, (VDP_data_port).l   ; write to nametable
        bra.s   .loop
.done:
        rts
```

**Number rendering:** `DrawHex` (register value → hex string) and `DrawDecimal` (BCD score → decimal string) for HUD and debug. BCD is the natural format for score display — no division needed, just nibble extraction.

**Deferred text:** For gameplay screens, text writes go through the Plane_buffer (§1.3, §4.4) like any other nametable update. For menu/loading screens where VDP access is less constrained, direct writes are acceptable.

**Debug text:** The MD Debugger error handler (§8.3) has its own text rendering for crash screens. The game's `DrawString` is separate — simpler, used for gameplay text. Both share the same font tiles.

### 9.15 Screen & Menu System

**Purpose:** Manage non-gameplay screens (title, menus, level select, game over, credits). Each screen is a game state (§9.13) with its own art, palette, input handling, and VBlank mode.

**Screen lifecycle:**

```
ScreenInit:
  1. Disable display (VDP reg $01)
  2. Load screen art via S4LZ blocking → VRAM
  3. Load palette → CRAM (via Priority 0 DMA)
  4. Load tilemap → nametable (raw DMA from ROM, §2.1)
  5. Load font if needed → VRAM
  6. Set VBlank mode to VInt_Menu
  7. Enable display
  8. Set Game_State to this screen's update routine

ScreenUpdate (runs each frame via GameLoop):
  1. Read controller input
  2. Update cursor/selection state
  3. Update animations (palette cycling, sprite movement)
  4. Check for state transition (Start pressed → next state)
```

**Menu cursor:** A sprite object (allocated via the standard object system) that moves between menu options. Input moves cursor position, A/C/Start confirms selection. Menu options are a ROM table of `{y_position, target_state_id}` pairs.

**Title card system:** Transition overlay between level select/continue and gameplay. Draws zone name + act number using the outlined font variant, animates in/out via horizontal scroll position. Runs as a brief sub-state within `GS_LEVEL_LOAD` — art loads behind the title card, card animates out when loading is complete.

**Credits roll:** Vertical scroll of text strings rendered to Plane A. Scroll speed controlled by a timer. Background animation (palette cycling, parallax) runs simultaneously via the standard VBlank pipeline.
