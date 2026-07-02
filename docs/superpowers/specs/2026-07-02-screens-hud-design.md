# Screens, HUD & Aurora Screen Authoring — design spec

**Date:** 2026-07-02
**Status:** Approved by user (design dialogue 2026-07-02)
**Extends:** §9.13 game state machine, §9.14 text & font, §9.15 screen & menu
(ENGINE_ARCHITECTURE baseline — this spec supersedes those sections where it
differs; ARCH gets reconciled at implementation), the Palette_Buffer/dirty DMA
machinery (buffers.asm), the sprite system (coord-mode `Draw_Sprite`,
sprites.asm:63), and the plane buffer (§4.4).
**Depends on:** design #4 (consumes its lives-counter + game-over stub + HUD
ring dirty flag), design #5 contract (Game_Entry/GAME_ENTRY_ID; this design is
executable on current master and slots into #5 unchanged), design #6 pattern
(Aurora document + MCP tool + generator conventions).
**Design-week queue:** #7

---

## 1. Goal & user-ratified scope

The complete non-gameplay surface of the game: game-state screens, the font/text
pipeline, the gameplay HUD, palette fades — and **screens as data documents that
Aurora edits visually and the engine plays** (the queue item's stated goal; also
an explicitly named Aurora charter item in `empyrean/docs/ROADMAP.md:93-94`
"single home for everything visual: … menus").

**Screen set (user decision: full classic set):** Sega logo, title, main menu,
level select (debug), title card, results tally, game over, continue,
credits/ending — plus pause overlay, HUD, and the font pipeline.

**Architecture (user decision: approach B):** compiled screen documents.
Aurora edits `*.screen.json` → `tools/screens_gen.py` validates and compiles to
ROM tables (widget records, string tables, pre-rendered nametable strips,
palettes, VRAM plan) → a small engine interpreter plays them inside the existing
game state machine. Hand-written-per-screen asm (approach A) was rejected as
un-authorable; full bytecode scripting (approach C) was rejected as overlapping
design #9's behavior sequencer — its useful residue survives as the symbolic
action enum (§6.4).

**Non-goals:** special-stage screens, save/competition menus (S3K-unique modes,
future documents on the same system), VWF dialogue rendering (kept *possible* —
§4 string rules — not built), localization tables beyond the string-ID seam,
cutscene scripting (design #9 territory), Aurora live-preview-on-emulator
(the WYSIWYG viewport is the preview; Aether live preview is design #8's
raster-tool concern), window-plane letterboxing (§7 backlog; window stays
reserved).

## 2. Research grounding (checklist discharged)

All 8 reference disassemblies + online + modern patterns, 5 subagents, 2026-07-02:

- **S.C.E./S3K** are the machinery template: pointer-based per-mode VBlank
  (`V_int_ptr` — we already have `VInt_Ptr`), `Draw_PlaneText` control-code text
  interpreter, per-field HUD dirty flags + repeated-subtraction digit draw
  (ours: BCD, §5), pause = push/swap/restore of the VInt pointer, menu-row
  highlight via palette-bit rewrite (`LevelSelect_MarkFields`), 16/4-frame
  cursor repeat-delay. S.C.E.'s `codepage` compile-time ASCII→tile trick is
  matched on our side by the *generator* doing the mapping at build time.
- **Avoid** (s2disasm): Enigma-baked menu plane maps (text uneditable in
  source — the exact anti-pattern for Aurora authoring), `bra.w` mode tables,
  byte-indexed VInt tables.
- **Non-Sonic refs legitimize data-driven screens on MD:** Vectorman draws
  Plane A/B *and the Window* from "map type ID" tables and dynamically
  allocates menu-text objects; TF4's scene list is a data enumeration with
  32-char text-grid menus; Batman runs screens/cutscenes as bytecode through
  two interpreters; Ristar's title cards/tally run off a per-stage script
  interpreter. Treasure (Gunstar/Alien Soldier) ships zero ASCII — all text is
  pre-drawn tiles — i.e. our "prebaked static labels" idea shipped in 1993;
  we add the generator so it stays authorable.
- **Hardware facts (plutiedev / md.railgun.works / SpritesMind):** Window plane
  costs zero sprite budget but *replaces* Plane A where active, never scrolls,
  and has a documented left-edge bug (RGHT=0 + hscroll%16 ≠ 0 fetches wrong
  tiles) — fine for menus, wrong for a floating gameplay HUD. H40 window
  nametable must be $1000-aligned ($F000 ✓). Sprite limits (80/frame,
  20/line, 320 px/line) are unaffected by the window.
- **Modern:** Bedrock JSON-UI / UMG retained-widget-tree + data-binding +
  symbolic actions is the converged industry pattern; nobody in the retro
  space has compiled it to ROM tables — that is this design's best-in-class
  claim. SGDK has no screen framework at all (every SGDK game hand-rolls
  menus); its text API shape (context + explicit-attr + draw-with-fill) and
  pinned-VRAM sprite-HUD idiom inform §4/§5. BCD end-to-end per plutiedev.

## 3. Game states & VInt modes (engine)

- **Keep** the `Game_State` function-pointer dispatch + `Game_State_Init`
  two-part init/update pattern (game_loop.asm:7, ojz_scroll_test.asm as
  template). No mode table — a state IS a pointer; ids (`GS_*`) exist for
  debug/save only and are **game-side** constants per the split spec.
- **New engine VInt mode `VInt_Menu`:** shadow flush → `Enqueue_Dirty_Buffers`
  → Critical DMA → Important/Deferrable DMA → controllers. No level plane
  drain, no VSRAM/parallax. ARCH's planned `VInt_Load` is **folded into
  `VInt_Menu`** (S4LZ decompression is main-loop work; the DMA queue drains
  either way) — ARCH §9.13/§1.4 updated at implementation.
- **Pause (engine mechanism, game content):** push `VInt_Ptr` → swap to
  `VInt_Menu` → darken palette (fade engine, §7) + draw PAUSED overlay via
  plane buffer → spin on unpause → restore pointer + palette. Sound driver
  keeps running; `Sound_SetTempo`/pause hooks are game policy.
- **Boot/entry:** screens wire in where the OJZ test is wired today
  (boot.asm:224); when design #5 executes, the game's `Game_Entry` becomes
  `GameState_Sega_Init` with zero changes to this design's states.
- **State inventory (all game-side):** `GS_SEGA, GS_TITLE, GS_MENU,
  GS_LEVELSELECT, GS_LEVEL_LOAD, GS_LEVEL, GS_CONTINUE, GS_GAMEOVER,
  GS_ENDING, GS_CREDITS` (ids for ARCH §9.13's table, minus special stage —
  reserved). All non-gameplay states are hosted by the **screen player**
  (§6); they differ only in which compiled screen document they load and
  which bindings/widgets are live.

## 4. Font & text pipeline

- **Font:** 96-char 8×8 ASCII ($20–$7F), uncompressed, ~3 KB ROM, loaded by
  the screen loader / level loader to a generator-allocated VRAM slot. A bold
  title-card variant is a second font asset on the same pipeline. Font source:
  PNG sheet under `games/sonic4/data/fonts/` converted by the toolchain —
  **TEMP placeholder glyphs** until the user sources real art (content is the
  user's; the pipeline is not blocked on it).
- **Strings are ASCII bytes in ID-indexed string tables — never tile indices,
  never inline in code.** The generator emits the tables; widgets reference
  `STR_*` ids. This is the whole localization seam (add a table + font glyphs
  later, zero screen rework) and keeps a future VWF renderer additive
  (Comix Zone proves VWF feasible on MD; explicitly out of scope).
- **Engine text module (`engine/text.asm`):** `Text_DrawString` — ASCII→tile
  (`char − $20 + font_base`, palette/priority from an attr-word template
  argument), control codes S.C.E.-style: `$FF` terminate, newline, center-on-
  width, palette-line switch. Two sinks: **direct VDP** (menu states — display
  owned by the screen player) and **plane-buffer entries** (gameplay text,
  inheriting the complete-before-VBlank contract, vblank.asm:126). Plus
  `Text_DrawBCD` (nibble unpack, leading-zero blank-fill to fixed field width
  — the SGDK `drawTextFill` no-flicker trick for free).
- **Static text costs nothing at runtime:** every static label/menu row is
  pre-rendered by the generator into nametable strips DMA'd at screen init.
  Only dynamic fields (`value-label`, menu highlight) draw at runtime.

## 5. HUD (engine machinery + game data)

- **Display:** classic layout (SCORE/TIME/RINGS top-left, lives bottom-left),
  **sprite-displayed** via the coord-mode `Draw_Sprite` path (RF_COORDMODE,
  sprites.asm:63) registered each frame by an engine HUD module — not an SST
  object (no slot pressure, deterministic). Window plane rejected for the
  gameplay HUD: it would replace Plane A under its band (hiding level FG) and
  cannot float; it remains reserved for future letterboxing/status bars.
- **Digits: S3K-style art-rewrite.** Few large fixed sprite pieces referencing
  fixed VRAM tiles; on change, digit tile art is rewritten through the DMA
  queue. Chosen over attribute-only digit sprites on measured grounds: art-
  rewrite minimizes per-scanline sprite pressure (20 sprites/320 px per line is
  the scarce resource on HUD rows) at the cost of rare, dirty-gated DMA
  (worst case ~384 B on a score change).
- **Per-field dirty flags** (`HUD_Dirty`: score/rings/timer/lives bits) — this
  IS the DEFERRED_WORK §1.4 item and the landing spot for the damage spec's
  ring dirty flag. No field writes when nothing changed.
- **Packed BCD end-to-end:** score/rings/time stored BCD from the moment they
  increment (`abcd` chains with carry-cap), display is nibble unpack — zero
  division anywhere (convention-compliant). RAM: game-side (`Player_Score`,
  `Ring_Count`, `Level_Timer`, `Lives_Count` — the damage spec's lives word).
- **Update site:** HUD module runs in the main loop (game state), VDP writes
  ride the DMA queue in VBlank — satisfying ARCH §1.4's "HUD update" slot.
- Timer policy (10:00 Time Over etc.) is game logic on the binding, not
  engine.

## 6. The screen player (engine interpreter) & compiled format

### 6.1 Compiled screen (generator output, ROM)
Header: palette ref, art blobs + **VRAM plan** (generator-allocated: font,
screen art, strips), prebuilt nametable strips, music cue id (0 = silence),
fade-in/out spec, timeout → action, input → action map. Then a widget record
list (count-prefixed, fixed-stride records + variable data pool).

### 6.2 Built-in widgets (engine)
- `label` — compiled away into strips (record exists only for Aurora's
  round-trip; engine skips it).
- `value-label` — binding id + x/y + BCD field width; redrawn when the
  binding's dirty bit is set.
- `image` — prebaked strip reference (position baked).
- `menu-list` — item records {string id, action, action arg}; cursor with
  16/4-frame repeat-delay; row highlight = palette-line rewrite of the row's
  nametable words (MarkFields pattern); confirm executes the action.
- `cursor` — sprite art ref + per-item positions (emitted by generator from
  menu geometry).

### 6.3 Game extension points (the grep-gate seams)
- **Binding table (game):** binding id → {RAM address, format (BCD width,
  raw hex, etc.), dirty-bit location}. Engine reads values through it only.
- **Widget-handler table (game):** widget type ≥ $80 dispatches to a
  game-registered handler with the record pointer. The **results tally**
  (ring-bonus countdown transferring into score with sounds) and the **title
  card** (overlays GS_LEVEL_LOAD, animates in/out while art loads behind it)
  are game widgets/screens on these seams — their logic never enters the
  engine interpreter.

### 6.4 Actions (symbolic enum)
`goto_screen(id)` (with exit-fade), `start_game(level id)`, `set_option(var,
val)`, `back`, `play_sound(id)`. Extensible opcode space; game may register
action handlers ≥ $80 through the same table mechanism as widgets.

### 6.5 Screen lifecycle (one generic game state hosts all screens)
Init: display off → load font+art per VRAM plan → strips → palette via
Palette_Buffer → set `VInt_Menu` → music cue (`Sound_PlayMusic`/fade) →
fade-in → display on. Update: controllers → cursor/widgets → bindings-dirty
redraw → action dispatch (transition = fade-out → next screen/state).
Teardown is the next state's init (established convention).

## 7. Palette fade engine (engine)

Runtime per-channel step fade operating on `Palette_Buffer` + `Palette_Dirty`:
fade to/from black, to/from white, and **crossfade toward a target buffer**,
N-frame paced (9-bit CRAM ⇒ 8 steps/channel; classic pacing ≈ 8 steps × 3-4
frames). Chosen over build-time fade tables because it handles dynamic
palettes (act palettes, future underwater) and transitions run when the CPU
is idle. Fades are declared as data in screen documents; the same module
serves pause-darken, title cards, and future damage-spec flashes. Sits in
`engine/` beside buffers.asm; ARCH §7's "palette cross-fading — planned"
becomes real here.

## 8. Documents, generator, Aurora

### 8.1 Screen documents
`games/sonic4/data/editor/screens/<name>.screen.json` — Aurora writes at
save-time as the user (identical daemon posture to level docs; agents do not
hand-edit autonomously). Schema (Zod in Aurora, mirrored in the generator):
screen id, palette ref, art refs, music cue, fades, timeout action, input→
action map, widgets (built-ins + game widgets by name), strings inline as
authored text (the generator assigns `STR_*` ids and builds the tables).

### 8.2 `tools/screens_gen.py`
Mirrors `ojz_entity_gen.py`: validate → emit into
`games/sonic4/data/generated/screens/` → nonzero exit on violation. **Build
gates:** string width vs field width, dangling `goto_screen`/art/palette refs,
binding ids vs the game's binding manifest, widget names vs the handler
manifest, **VRAM fit** (it owns the per-screen VRAM allocation), palette-line
conflicts. Emits widget records, string tables, nametable strips, palettes,
screen index. Wired into build.sh as a `generate` step. Generated output is
never hand-edited.

### 8.3 Aurora screen mode
Fourth `AppMode` (`'screen'`) on the established pattern (editorStore.ts:66,
App.tsx mode branch): `core/formats/screen.ts` (Zod), `screenStore.ts` on the
shared undo history, WYSIWYG `ScreenViewport` (40×28 cell grid rendering real
font tiles, menu rows + cursor preview, images, live palette), tool dock
(text / menu editor / image placement / screen properties: palette, music,
fades, actions), save via the atomic `writeBinaryFile` path. **MCP/Aether
tools** per the design-#6 template (descriptor in `EDITOR_METHODS` + agent-
handler case, one undo step per call): `list_screens`, `get_screen`,
`set_screen_text`, `set_menu_items`, `set_screen_meta`, `add_widget`,
`remove_widget`.

## 9. Engine/game tagging (design-#5 inputs)

**Engine:** `VInt_Menu`, text module, `Text_DrawBCD`, fade engine, HUD
machinery (dirty-flag/digit/sprite-registration), screen interpreter + widget/
action dispatch, pause mechanism. Zero game symbols (grep gate: no `GS_`,
`STR_`, `SONG_`, screen names in `engine/`).
**Game:** GS ids, screen documents + compiled data, string tables, fonts,
binding table, widget/action handler tables (tally, title card), HUD field
definitions + BCD RAM, screen states (→ `Game_Entry` material), music cue ids.

## 10. Testing

- **Build-time:** generator gates (each violation class has a failing-fixture
  test) + golden round-trip (JSON → compile → assert emitted tables byte-
  exact); pytest beside the existing tool tests.
- **Runtime (foreground oracle, per no-emulator-in-subagents rule):** full
  circuit Sega → title → menu → level select → level (HUD live) → pause →
  death → game over → continue → title. HUD dirty behavior verified by
  watching VRAM writes occur only on value change; fade correctness via CRAM
  reads mid-fade; menu input incl. repeat-delay via `emulator_press` scripts.
- **Aurora:** edit a menu item → save → rebuild → change visible in-emulator;
  MCP tool round-trip (`set_screen_text` → `get_screen`).

## 11. Sequencing & risks

**Plan order:** (1) engine primitives — font/text, fade engine, `VInt_Menu`;
(2) HUD (fully unblocks design #4 execution); (3) interpreter + generator
with one hand-authored JSON (title screen) proving the whole pipeline;
(4) full screen set + game widgets (tally, title card, pause); (5) Aurora
mode + MCP tools last — JSON is hand-editable in the interim, so authoring
is never blocked on the editor.

**Risks:** VRAM plans for screens must respect the debugger console's
assumptions (it owns its own VDP setup — verify no collision when a crash
occurs inside a menu state); title card over `GS_LEVEL_LOAD` competes with
load-time DMA pressure (title card art must be resident before load kicks
off — sequenced in its game widget); results tally owns score-transfer game
logic that must not leak into the engine interpreter (enforced by the
handler-table seam + grep gate); `VInt_Menu` must not drain the plane buffer
mid-write (inherits the Ptr-gate rule — menu states only submit complete
entries before VSync).
