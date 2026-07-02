# Screens / HUD / Aurora Screen Authoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The complete non-gameplay surface — font/text pipeline, palette fades, `VInt_Menu`, the gameplay HUD, and the full classic screen set as Aurora-editable compiled documents played by an engine interpreter.

**Architecture:** E (Tasks 1-4): engine primitives — font pipeline, text module, fade engine, `VInt_Menu`+pause. H (Task 5): HUD (unblocks design #4 execution fully). P (Tasks 6-7): `screens_gen.py` + the screen-player interpreter, proven end-to-end with a hand-authored title document. S (Tasks 8-10): full screen set + game widgets (tally, title card). A (Task 11): Aurora screen mode + MCP tools. Task 12: soak + ARCH reconciliation + merge. Spec: `docs/superpowers/specs/2026-07-02-screens-hud-design.md` (APPROVED) — widget/action/binding semantics live there; the plan repeats the load-bearing formats inline.

**Dependencies:** none hard. Executable on current master (screens wire in where the OJZ test is wired, boot.asm:224); slots into design #5's `Game_Entry` unchanged when that executes. Design #4's lives/game-over stub is a consumer, not a prerequisite — until #4 lands, GS_GAMEOVER is reached via a debug menu action. Aurora tasks touch the sibling repo `/home/volence/sonic_hacks/aurora/` (its own git tree — commit there separately).

**Tech Stack:** 68000 (AS), Python 3 generators + pytest, oracle MCP (foreground only — never from subagents), Aurora = Electron/React/TS/Zod/Zustand. Standing rules: research step first per task; DEBUG=1 builds; runtime-boot after any ram.asm change (AS does not auto-align — pad odd ds.b); exact-path commits; branch `feat/screens-hud`; daemon-watched paths (`tools/ojz_strip_gen.py`, `data/editor/ojz/**`) untouched; new `data/editor/screens/**` JSON is written by us during P/S (hand-authored era) and by Aurora-as-user after Task 11.

---

### Task 1: Branch + research + font asset pipeline

**Files:**
- Create: `tools/font_gen.py`, `tools/tests/test_font_gen.py`, `games/sonic4/data/fonts/font_8x8.png` (TEMP glyphs), `games/sonic4/data/generated/fonts/font_main.bin`
- Modify: `build.sh` (generate step), `games/sonic4/main.asm` (BINCLUDE in `__BUDGET_DATA`)

- [ ] **Step 1: Research.** Read the spec end to end. Read `engine/system/vblank.asm` (both handlers, the Ptr-gate comment :126), `engine/system/game_loop.asm`, `test/ojz_scroll_test.asm` (the init/update state template), `engine/system/buffers.asm` (Palette_Buffer/dirty + queueStaticDMA), `engine/objects/sprites.asm:46-80` (Draw_Sprite coord-mode path) + `:627` (InsertSpriteMasks), `engine/level/plane_buffer.asm` entry format, `tools/ojz_entity_gen.py` (the generator pattern to mirror), `engine/sound/sound_api.asm` public API. Note the debugger console symbols (`MDDBG__*`, error_handler.asm:206-250) — the game font is separate from it by design.
- [ ] **Step 2: Failing test.** `test_font_gen.py`: feed a 2-glyph PNG fixture → expect 64-byte 4bpp planar output, glyph order = ASCII from $20, color index 15 for set pixels, 0 for clear. Run: `pytest tools/tests/test_font_gen.py -v` → FAIL (module missing).
- [ ] **Step 3: Implement.** `font_gen.py`: PNG (16×6 grid of 8×8 cells, chars $20-$7F) → 96 tiles × 32 B 4bpp planar, `generate` CLI writing `data/generated/fonts/font_main.bin`; hard-fail on wrong image dimensions. Draw a TEMP blocky font PNG programmatically (script emits it if missing, marked TEMP in a sibling `.txt` provenance note). Wire into `build.sh` after `ojz_block_gen.py`. `pytest` PASS; `./build.sh` green with the BINCLUDE (`Art_FontMain: BINCLUDE "games/sonic4/data/generated/fonts/font_main.bin"`).
- [ ] **Step 4: Commit.** `git checkout -b feat/screens-hud`; exact paths; `feat(tools): font pipeline — PNG→4bpp tiles + TEMP font (E)`

### Task 2: Engine text module

**Files:**
- Create: `engine/screens/text.asm` (the spec's text module — engine/screens/ is the new machinery dir)
- Modify: `games/sonic4/main.asm` (include in engine block), `constants.asm` (control codes, `TEXT_*`)

- [ ] **Step 1: Research.** S.C.E. `Engine/Core/Draw Text.asm` (`Draw_PlaneText` control codes — reference for semantics, code written fresh per no-ported-code rule); our VDP write macros (`vdpComm`, data-port patterns in ojz_scroll_test init); plane-buffer entry format (addr.w, flags_cnt.w bit15=column, data…, 0-terminator).
- [ ] **Step 2: Implement.**

```asm
; a0=ASCII string, d0.l=vdpComm(dest,VRAM,WRITE), d1.w=attr template (pal/pri|font_base)
; Control: $FF end, $FE newline (d2.w=line stride words), $F0..$F3 switch pal line
Text_DrawString:        ; direct-VDP sink (menu states own the display)
Text_DrawString_Plane:  ; same interpreter, emits ONE complete plane-buffer entry (row mode)
; d0.l=BCD value, d1.w=field width (digits), d2.w=attr, a1=plane-buffer/VDP dest
Text_DrawBCD:           ; nibble unpack hi→lo, leading zeros → blank tile ($20 slot), fixed width
```

  Char→tile = `char − $20 + d1-embedded base`. Centering ($FE arg) computed from remaining string length to the next control byte. The plane sink writes header+words+terminator in one pass (Ptr-gate safe: entry complete before VSync).
- [ ] **Step 3: Verify + commit.** Temporary smoke lines in the OJZ state init: font DMA'd to a free slot (tiles 992-1007 region), `Text_DrawString` "HELLO AEON 0123456789" to Plane A + a BCD field; oracle screenshot both; remove the smoke lines before commit (keep as a documented snippet in the file header comment). `feat(engine): text module — DrawString/DrawBCD, control codes, dual sinks (E)`

### Task 3: Palette fade engine

**Files:**
- Create: `engine/screens/fade.asm`
- Modify: `ram.asm` (`Fade_Target: ds.b 128`, `Fade_Timer/Fade_Step/Fade_Mode: ds.b` — pad even), `constants.asm` (`FADE_*` modes), `games/sonic4/main.asm`

- [ ] **Step 1: Research.** `Enqueue_Dirty_Buffers` (buffers.asm:122-148) — the fade only ever touches `Palette_Buffer`+`Palette_Dirty`, DMA machinery untouched. S3K fade pacing (skdisasm `Pal_FadeToBlack` family) for the classic feel constants (reference only).
- [ ] **Step 2: Implement.** `Fade_Start(d0=mode FADE_TO_BLACK/FROM_BLACK/TO_WHITE/FROM_WHITE/CROSS, d1=frames-per-step)`; CROSS reads `Fade_Target` (caller memcpys the destination palette there first). `Fade_Update` (called by state update loops while `Fade_Mode` nonzero): every `d1` frames, step each of 64 colors one unit per channel toward target (B/G/R independently, 9-bit CRAM ⇒ ≤8 steps), set `Palette_Dirty=$0F`; done → clear mode. No mulu/divu: channel step = compare + `addq/subq #2` per 3-bit field, masked.
- [ ] **Step 3: Verify + commit.** OJZ state: fade-out then fade-in on a debug key; oracle `emulator_read_cram` mid-fade shows monotonic stepping, 0 lag frames. `feat(engine): palette fade engine — black/white/cross, N-frame paced (E)`

### Task 4: VInt_Menu + pause mechanism

**Files:**
- Modify: `engine/system/vblank.asm` (`VInt_Menu`), `engine/screens/` new `pause.asm`, `ram.asm` (`Pause_Flag`, `Pause_Saved_VInt: ds.l 1`), `test/ojz_scroll_test.asm` (Start-button hook)

- [ ] **Step 1: Research.** `VInt_Level` step order (vblank.asm:37-108) and which steps are level-only (plane drain `VInt_DrawLevel`, VSRAM/parallax); S.C.E. `Pause Game.asm` push/swap/restore semantics; our controller read site; `Sound_*` pause policy hooks (none yet — music keeps playing, classic).
- [ ] **Step 2: Implement.** `VInt_Menu`: shadow flush → `Enqueue_Dirty_Buffers` → Critical DMA → Important/Deferrable DMA → controllers → done (no plane drain, no VSRAM). ARCH's separate `VInt_Load` is NOT built (folded — reconciliation in Task 12). `Pause_Check` (engine, called by the level state): Start pressed → save `VInt_Ptr`→`Pause_Saved_VInt`, swap to `VInt_Menu`, `Fade` half-darken via CROSS toward a darkened copy (built by halving each channel — shift+mask, no tables), draw "PAUSED" via `Text_DrawString_Plane`, spin loop polling Start (VSync each frame, `Fade_Update` + sound alive); unpause → restore palette (saved copy), erase overlay row, restore `VInt_Ptr`.
- [ ] **Step 3: Verify + commit.** Pause mid-scroll: screen freezes coherently (no torn plane), music continues, PAUSED visible, unpause resumes exactly (camera/RAM hash unchanged across pause — `emulator_state_hash` before/after). `feat(engine): VInt_Menu + pause push/swap/restore (E complete)`

### Task 5: HUD

**Files:**
- Create: `engine/screens/hud.asm` (machinery), `games/sonic4/screens/hud_def.asm` (field defs, layout, art refs), HUD art assets under `games/sonic4/data/` (digits/labels — migrate from sonic_hack data per donor rule)
- Modify: `ram.asm` (game-side: `HUD_Dirty: ds.b 1` + BCD `Player_Score: ds.l 1`, `Ring_Count: ds.w 1`, `Level_Timer: ds.l 1`, `Lives_Count: ds.w 1` — pad even), `constants.asm` (VRAM slots), `test/ojz_scroll_test.asm` (wire update+draw)

- [ ] **Step 1: Research.** skdisasm HUD (`DrawSixDigitNumber`, dirty flags, `ArtUnc_HUDDigits`) + S.C.E.'s refinements — semantics reference. Our DMA queue API (`queueStaticDMA` vs dynamic enqueue — which fits an 12-tile burst), `Draw_Sprite` coord-mode registration + mappings format (VDP-order), sprite mask interaction (`InsertSpriteMasks`) — HUD draws in the highest priority band. sonic_hack HUD art location (donor: digits + SCORE/TIME/RINGS labels).
- [ ] **Step 2: Implement.** `hud_def.asm`: field table {BCD RAM addr, digit count, VRAM tile base, sprite piece defs, dirty bit#}. `hud.asm`: `HUD_Init` (DMA static label art + zero fields), `HUD_Update` (main-loop: for each dirty bit — unpack BCD nibbles → compose digit tile art pointers → enqueue art rewrite to the field's fixed VRAM tiles via the DMA queue → clear bit), `HUD_Draw` (register the fixed sprite pieces via coord-mode `Draw_Sprite` every frame). Score add helper (game-side): `abcd` chain with $99999999 carry cap. Timer tick (game-side, level loop): BCD minutes:seconds:frames. Ring award/loss sets bit HUD_DIRTY_RINGS — the damage spec's seam.
- [ ] **Step 3: Verify + commit.** Oracle: HUD visible over parallax at rest AND during max scroll (verify-during-motion rule); poke `Ring_Count` via `emulator_write_memory` → display updates that frame; watch VRAM writes (watchpoint on a digit tile) → writes occur ONLY when a value changes; per-line sprite count on HUD rows within budget during a busy scene. `feat(engine,game): HUD — BCD fields, dirty flags, art-rewrite digits, coord-mode sprites (H; unblocks #4)`

### Task 6: screens_gen.py — the document compiler

**Files:**
- Create: `tools/screens_gen.py`, `tools/tests/test_screens_gen.py` (+ fixtures incl. one golden document), `games/sonic4/data/editor/screens/title.screen.json` (hand-authored), `games/sonic4/data/editor/screens/binding_manifest.json`, `widget_manifest.json`
- Modify: `build.sh`

- [ ] **Step 1: Research.** `ojz_entity_gen.py` end to end (validate→emit, caps, exit codes); the mappings/nametable word format (attr bits); how palettes are stored (`data/levels/**` palette bins) for the palette-ref convention.
- [ ] **Step 2: Failing tests.** Fixture documents exercising every gate: over-wide string in a field, dangling `goto_screen`, unknown binding id, unknown widget name, VRAM overflow (art refs exceeding the plan), palette-line conflict — each expects nonzero exit + message; plus the golden: `title.screen.json` → byte-exact expected tables. `pytest tools/tests/test_screens_gen.py -v` → FAIL.
- [ ] **Step 3: Implement.** Document schema per spec §8.1 (strings inline; generator assigns `STR_*`). Emits into `data/generated/screens/`: `screens.asm` (screen index + headers: palette ptr, VRAM plan records {dest tile, source blob, count}, strip ptrs, music id, fades, timeout/input action words, widget records), `strings.asm`, `strips.bin` (pre-rendered nametables for labels/images/menu rows — ASCII→tile mapping done HERE at build time), per-screen palette bins. Widget record: `{type.b, flags.b, x.b, y.b, param.w, data_ptr.l}`; menu items: `{str_id.w, action.b, arg.b, arg2.w}`. Actions/widget names ≥ $80 validated against the two manifests. VRAM plan: font base + sequential allocation, overflow = gate. `title.screen.json`: bg image ref (TEMP art ok), "PRESS START" label, input map {Start → goto_screen(menu)}, music cue, fades. All tests PASS; `build.sh` wired; build green.
- [ ] **Step 4: Commit.** `feat(tools): screens_gen — document compiler with build gates + golden test (P)`

### Task 7: Screen player (engine interpreter) + title boots

**Files:**
- Create: `engine/screens/screen_player.asm`, `games/sonic4/screens/screens.asm` (game states table, binding table, widget/action handler tables — mostly empty), `games/sonic4/screens/gs_ids.asm` (`GS_TITLE` etc.)
- Modify: `engine/system/boot.asm` (initial state → `GameState_Title_Init` — the future `Game_Entry` line), `games/sonic4/main.asm`

- [ ] **Step 1: Research.** Re-read the compiled formats emitted in Task 6 (they are the contract); `Sound_PlayMusic`/`Sound_FadeIn` call pattern (game_loop.asm:40-121 example); display-disable/enable reg writes (boot.asm VDP init + ojz state).
- [ ] **Step 2: Implement.** `ScreenPlayer_Init(a0=compiled screen)`: display off → font+art blobs per VRAM plan (DMA) → strips → palette memcpy+dirty → `VInt_Menu` → music cue (0=stop) → `Fade_Start` fade-in → display on → swap `Game_State` to update. `ScreenPlayer_Update`: `Fade_Update`; controllers → input-action map + timeout counter; per-widget dispatch: `value-label` (binding table lookup → dirty? → `Text_DrawBCD` direct-VDP), `menu-list` (up/down with 16-initial/4-repeat delay, row highlight = rewrite the row's nametable words with the alt palette line, A/C/Start → action), types ≥ $80 → game handler table. Action dispatch: `goto_screen` (fade-out → resolve id via screen index → re-init), `start_game` (fade-out → set the level state — today `GameState_OJZScroll_Init`), `set_option`, `back` (one-level screen stack), `play_sound`; ≥ $80 → game table. Game side: states table for all GS ids each pointing at ScreenPlayer with its document.
- [ ] **Step 3: Verify + commit.** Boot → title screen: art + PRESS START visible, music playing, fade-in stepped (CRAM), Start → fade-out into OJZ level (start_game wired for now). Full circuit title↔level. `feat(engine,game): screen player — interpreter, actions, title boots (P complete)`

### Task 8: Menu + level select + options

**Files:**
- Create: `games/sonic4/data/editor/screens/menu.screen.json`, `levelselect.screen.json`
- Modify: `binding_manifest.json` (sound-test id, option vars), `games/sonic4/screens/screens.asm` (option RAM + set_option targets)

- [ ] **Step 1: Research.** S.C.E. level select (buffer/MarkFields/control_timer semantics — ours is generator-prebaked rows + the Task-7 highlight, so only the repeat-delay constants carry over); current act/level identifiers (act descriptor) for `start_game` args.
- [ ] **Step 2: Implement.** `menu.screen.json`: menu-list {1P START → start_game(ojz1), LEVEL SELECT → goto_screen, SOUND TEST rows}. `levelselect.screen.json`: menu rows per act (one today) + sound-test `value-label` bound to a game RAM var with `set_option` inc/dec actions + `play_sound($80 game action: play the selected id)`. Wire GS_MENU/GS_LEVELSELECT.
- [ ] **Step 3: Verify + commit.** Oracle input scripts: navigate title→menu→level select, repeat-delay feel (hold-down scroll at 16/4), highlight tracks, sound test plays SFX/music ids, start_game enters the act. `feat(game): menu + level select documents (S)`

### Task 9: Sega / game over / continue / credits + circuit

**Files:**
- Create: `sega.screen.json`, `gameover.screen.json`, `continue.screen.json`, `credits.screen.json` (+ ending alias doc), all under `games/sonic4/data/editor/screens/`
- Modify: `games/sonic4/screens/screens.asm` (GS wiring, credits scroll = game widget), boot initial state → `GameState_Sega_Init`

- [ ] **Step 1: Research.** Continue-screen classic behavior (countdown timeout → game over; Start → restart with lives reset) from s2disasm — semantics only. Credits: vertical scroll of a tall prebaked strip (generator already emits strips; scrolling = VScroll stepping, a small game widget).
- [ ] **Step 2: Implement.** Sega: image + timeout(180)→goto_screen(title) + the SEGA cue. Game over: text + timeout→title, input Start→continue screen. Continue: countdown value-label (binding: RAM byte ticked by a game widget) + Start→start_game + timeout→gameover→title. Credits: game widget `credits_scroll` (VScroll += ¼px/frame over a tall strip, end→title). Register the two game widgets in `widget_manifest.json` + handler table. Boot → Sega first.
- [ ] **Step 3: Verify + commit.** Full circuit run on oracle: Sega→(timeout)→title→menu→level select→level→(debug action)→game over→continue→(timeout)→game over→title; credits reachable from menu debug row; every transition fade-clean, 0 unexpected lag frames. `feat(game): full classic screen set + circuit (S)`

### Task 10: Title card + results tally (game widgets)

**Files:**
- Create: `games/sonic4/screens/title_card.asm`, `games/sonic4/screens/results.asm`, `titlecard.screen.json`, `results.screen.json`
- Modify: level state (hooks: entry → title card overlay; act-clear debug trigger → results), `widget_manifest.json`, handler tables

- [ ] **Step 1: Research.** How the level state init sequences art loading (where the card must already be resident — its art loads BEFORE the act load kicks off, spec §11 risk); signpost/act-clear trigger points (none yet — debug key stands in until badniks/goal exist); S3K tally cadence (100/frame drain, ring bonus ×10, sounds) — semantics.
- [ ] **Step 2: Implement.** Title card = overlay widget set played by a **sub-player call** from the level state (not a GS switch): zone-name label strip + act number, slide-in via per-frame HScroll offset on its rows (plane-buffer writes), holds until level fill complete flag, slide-out. Results: screen doc over frozen level (VInt_Menu), tally widget drains ring/time bonuses into `Player_Score` via the BCD add helper at 100/frame with tick sound, end → next-act `start_game` arg / title. Both handlers game-side; engine interpreter untouched (grep gate).
- [ ] **Step 3: Verify + commit.** Card animates over the load with zero visible pop-in before fill-complete; tally drains with correct BCD math (probe RAM), sounds tick, score HUD dirty-updates live. `feat(game): title card + results tally on the widget seams (S complete)`

### Task 11: Aurora screen mode + MCP tools

**Files (aurora repo — separate git):**
- Create: `src/core/formats/screen.ts` (Zod schema — mirror of the generator's), `src/renderer/state/screenStore.ts`, `src/renderer/components/screen/ScreenViewport.tsx` + tool dock, screen entries in `src/main/editor-methods.ts`, cases in `src/renderer/agent/agent-handler.ts`
- Modify: `src/renderer/state/editorStore.ts:66` (`AppMode` + `'screen'`), `src/renderer/App.tsx` (mode branch + CommandPalette), `src/renderer/hooks/useProject.ts` (save `*.screen.json`)

- [ ] **Step 1: Research.** Read the listed files + how `artStore`/sprite mode wire their viewport/dock/status bar (the pattern to mirror); the atomic `WRITE_BINARY_FILE` IPC; design #6 spec §2.6 (tool descriptor conventions).
- [ ] **Step 2: Failing tests.** Zod schema round-trip vitest: parse `title.screen.json` fixture → serialize → deep-equal; reject fixtures (bad widget type, missing screen id). Run aurora test suite → FAIL.
- [ ] **Step 3: Implement.** Schema (single source of document truth on the TS side — field-for-field the generator's). `screenStore` on shared undo history (commands: set-text, set-menu-items, add/remove-widget, set-meta). `ScreenViewport`: 40×28 cell grid; renders font tiles from the project font PNG, label/menu/image widgets WYSIWYG, cursor preview, palette-accurate. Dock: text/menu/image/properties (palette, music id, fades, input map). Save: emit each screen doc via `writeBinaryFile`. MCP/Aether: `list_screens`, `get_screen`, `set_screen_text`, `set_menu_items`, `set_screen_meta`, `add_widget`, `remove_widget` — descriptors in `EDITOR_METHODS`, handler cases route through the store commands (one undo step each). Tests PASS.
- [ ] **Step 4: Verify + commit (aurora repo).** Open the project → screen mode → edit title's PRESS START text → save → aeon `./build.sh` → oracle shows the new text. MCP round-trip: `set_screen_text` → `get_screen` reflects it → undo reverts in one step. `feat(screens): screen document mode + viewport + MCP tools`

### Task 12: Soak + ARCH reconciliation + merge

**Files:**
- Modify: `docs/ENGINE_ARCHITECTURE.md` (§9.13/§9.14/§9.15 rewritten as-built: VInt_Load folded into VInt_Menu, compiled-document system, HUD §1.4 slot filled), `docs/DEFERRED_WORK.md` (close §1.4 HUD dirty flags; add VWF/localization/window-letterbox as deferred entries), `docs/superpowers/2026-07-02-design-week-queue.md` (log)

- [ ] **Step 1: Soak.** 10-minute oracle circuit soak (scripted inputs cycling all screens + pause + level entry/exit ×10): `Lag_Frame_Count` stable, no VRAM corruption (state-hash spot checks), sound driver alive throughout (Sound_Ping), crash-handler intact (force a DEBUG assert inside GS_MENU — the risk item: debugger console renders correctly from a menu state).
- [ ] **Step 2: Docs.** Rewrite the three ARCH sections as the design (clean-not-bolted-on rule: the doc reads as if always designed this way); DEFERRED_WORK + queue log updates.
- [ ] **Step 3: Merge.** `git checkout master && git merge --ff-only feat/screens-hud` (rebase first if needed); build green on master; `docs+feat` history intact.

---

## Self-review (done at write time)

- **Spec coverage:** §3 states/VInt→T4/T7/T9; §4 font/text→T1/T2; §5 HUD→T5; §6 interpreter/format→T6/T7 (extension seams exercised in T9/T10); §7 fade→T3; §8 documents/generator/Aurora→T6/T11; §9 tagging enforced at T7/T10 (grep gate), §10 testing distributed per task + T12 soak; §11 order followed (E→H→P→S→A). Gap check: pause overlay content (§3) lands T4+polish T10 — covered.
- **Placeholders:** none; TEMP font/art flagged as intentional content seams with provenance notes.
- **Type consistency:** widget record `{type,flags,x,y,param,data_ptr}` and menu item `{str_id,action,arg,arg2}` used identically in T6 (emit) and T7 (interpret); `HUD_Dirty` bit names shared T5→T10; GS ids defined once in T7's `gs_ids.asm`.
