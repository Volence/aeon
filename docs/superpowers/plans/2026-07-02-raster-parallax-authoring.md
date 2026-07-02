# Raster Engine / Effect Sequencer / Parallax & Raster Authoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Data-driven HInt raster effects (water line, gradients, letterbox), a Batman-derived frame-level effect sequencer, parallax configs migrated to Aurora-editable JSON, and Aurora live preview pushing edits into the running oracle over Aether.

**Architecture:** R (Tasks 1-2): trampoline + raster script walker + two-split self-test, then the water line end-to-end (the proving effect). S (Tasks 3-4): effect sequencer, then gradient + letterbox riding ops + sequencer. G (Tasks 5-6): `parallax_gen.py` with byte-equal migration golden (asm data retires), `raster_gen.py` + the four v1 documents. A (Tasks 7-8): Aurora fifth mode + MCP tools, then the Aether client + DEBUG override live preview. Task 9: soak + ARCH reconciliation + merge. Spec: `docs/superpowers/specs/2026-07-02-raster-parallax-authoring-design.md` (APPROVED) — op semantics, hardware numbers, and research citations live there.

**Dependencies:** none hard on unexecuted designs. Design #7's fade engine is the sequencer's fade primitive — if #7 hasn't landed, Task 3 stubs `Fade_Start` behind a tagged direct palette write and the seam is re-pointed when #7 lands. Aurora tasks are in the sibling repo (separate git). Water *physics* stays out (damage-spec hooks stand).

**Tech Stack:** 68000 (AS), Python 3 + pytest, oracle MCP (foreground only), Aurora Electron/React/TS. Standing rules: research step first per task; `DEBUG=1` builds; runtime-boot after ram.asm changes (pad even); exact-path commits; branch `feat/raster-authoring`; daemon-watched paths untouched; verify raster effects DURING MOTION.

---

### Task 1: Trampoline + raster script walker + two-split self-test

**Files:**
- Create: `engine/raster/raster.asm` (walker, ops CRAM_BURST + REG_WRITE first, install/arm)
- Modify: `engine/system/hblank.asm` (RAM inline-jmp trampoline replaces the ROM stub), `ram.asm` (`HBlank_Jmp_Slot: ds.b 6` + raster walk state — pad even), `games/sonic4/main.asm` (vector already points at $70 handler — repoint to the RAM slot), `engine/system/boot.asm` (seed trampoline → null handler), `engine/debug/` self-test hook
- Read first: `docs/superpowers/specs/2026-04-27-hblank-inline-jmp-design.md` (this task ships it)

- [ ] **Step 1: Research.** Read the spec §4 in full; the inline-jmp spec; `engine/system/hblank.asm` + vector at `games/sonic4/main.asm:60`; boot VDP regs `$00`/`$0A` writes (`boot.asm:249,259`); how the DEBUG compression golden self-test is wired at boot (pattern for the two-split test); `VBlank` prologue site for per-frame arming.
- [ ] **Step 2: Implement.**

```asm
; ram.asm (DEBUG-agnostic)
HBlank_Jmp_Slot:    ds.b 6      ; 4EF9 + target.l — IRQ4 vector points here
Raster_Script_Ptr:  ds.l 1      ; 0 = none
Raster_Walk_Ptr:    ds.l 1      ; next record during frame
; script record: line_delta.b, op.b, args... ; delta $FF = end
; ops: ROP_CRAM_BURST=0 (addr.w,count.w,src.l), ROP_REG=2 (regval.w)
```

  `Raster_Install(a0)`: write target into `HBlank_Jmp_Slot+2`, save script ptr. VBlank prologue (`VInt_Level`/`VInt_Menu`, before startZ80): if script — reset walk ptr, write reg `$0A` = first delta, set reg `$00` IE1; else IE1 clear. Handler: **first instruction re-arms `$0A` with next delta** (or clears IE1 at `$FF`), then executes its op (CRAM_BURST = `sr=$2700` + unrolled `move.l` block; REG_WRITE = one control-port word). No shadow/dirty touches.
- [ ] **Step 3: Self-test.** DEBUG boot: install a 2-record script (REG_WRITE at lines 80 and 160 toggling a scratch reg — use `$8A` echo into a RAM capture via HV counter read `move.w (VDP_hv),(capture)+`), run one frame, assert two captures with HV lines in [79,82] and [159,162]; log PASS/FAIL like the compression golden.
- [ ] **Step 4: Verify + commit.** `git checkout -b feat/raster-authoring`; oracle DEBUG boot shows self-test PASS; OJZ gameplay unaffected (HInt disabled with no script), `Lag_Frame_Count` baseline unchanged. `feat(engine): raster script engine — RAM trampoline, walker, $0A re-arm, two-split self-test`

### Task 2: Water line end-to-end

**Files:**
- Create: `engine/raster/tracks.asm` (track table walker + water easing)
- Modify: `engine/raster/raster.asm` (TRACK records), `ram.asm` (`Water_Level`, `Mean_Water_Level`, `Target_Water_Level`, `Water_Speed`, `Water_Fullscreen_Flag`, `Water_Palette_Buffer: ds.b 128`), `engine/system/buffers.asm`/VBlank (top-of-frame palette select), `test/ojz_scroll_test.asm` (debug water level + underwater palette fixture)

- [ ] **Step 1: Research.** Spec §4.4 + the S3K citations (`sonic3k.asm:944-1257` HInt2 + `Handle_Onscreen_Water_Height:8473` semantics); our `Enqueue_Dirty_Buffers` palette DMA path (which buffer the Critical queue sources — the fullscreen flag must swap the DMA *source*); sonic_hack `code/engines/water.asm` for the S1-lineage contract (reference only).
- [ ] **Step 2: Implement.** Track table: `{track_id → handler}`; water handler each VBlank: ease `Mean→Target` by `Water_Speed`, `Water_Level = Mean + osc` (osc = 0 until an oscillator exists — tagged), `d0 = Water_Level − Camera_Y_screen`; `d0 ≤ 0` → fullscreen flag set + record delta `$FF`-parked; `d0 ≥ 224` → HInt not armed; else delta = d0, apply the S3K truncation guard (burst record suppressed when line > 200-equivalent for the burst variant). Fullscreen flag selects `Water_Palette_Buffer` vs `Palette_Buffer` as the top-of-frame CRAM DMA source. Water script = 1 TRACK record: `CRAM_BURST(addr=0, count=64, src=Water_Palette_Buffer or Palette_Buffer per flag — the *other* one)`. Fixture: OJZ debug key sets `Target_Water_Level`; underwater palette = darkened copy built at init (channel halve).
- [ ] **Step 3: Verify + commit (DURING MOTION).** Oracle: split visible and glitch-free while scrolling both axes; camera crossing the line up/down (surface enters from top/bottom); fullscreen enter/exit swaps top-of-frame palette with no flash frame; the S3K overrun regression (line low + camera moving down fast) shows no VInt overrun (`Lag_Frame_Count` clean); CRAM dots confined to left overscan in frame captures. `feat(engine): water line — camera-tracked split, palette double-buffer, fullscreen semantics`

### Task 3: Effect sequencer

**Files:**
- Create: `engine/raster/sequencer.asm`
- Modify: `ram.asm` (4 controller slots × {pc.l, delay.b, loop.b, stack 4×.l, sp.b} — pad even), `constants.asm` (SEQ_OP_*), `games/sonic4/main.asm`

- [ ] **Step 1: Research.** Spec §5 + the Batman citations (byte-pair fetch/dispatch, yield-with-delay op 1, random branch op 7); our RNG routine (engine math — find the existing PRNG or the convention for one); design #7's `Fade_Start`/`Fade_Target` API if landed (else stub seam per plan header); `Palette_Buffer`/`Palette_Dirty` write conventions.
- [ ] **Step 2: Implement.**

```asm
; Stream: {cmd.b, param.b} pairs. cmd low nibble = op, high nibble = sub-mode.
; 0 reset · 1 wait param frames (yield: save pc) · 2 rel-branch (12-bit disp:
;   (sext(cmd)<<4)|param, lea -2(a0,d4.w)) · 3 call (push, 4 deep) · 4 return
; 5 set-loop=param · 6 dec-loop (branch back while >0) · 7 random-branch
;   (RNG-indexed word-offset table follows) · 8-F palette programs:
;   8 load palette set[param] → Palette_Buffer+dirty · 9 load → Fade_Target
;   A start fade (param = mode<<4|frames-per-step, calls Fade_Start)
;   B set gradient phase · C set letterbox targets (param = lines/8 pair)
;   D set shake envelope value · E set water target (param → Target_Water_Level lookup)
;   F reserved (build-time assert: generator rejects)
Seq_Tick:            ; once/frame from main loop: per active slot, decrement
                     ; delay, bpl done; interpret until next yield
Seq_Start(d0=slot, a0=program) / Seq_Stop(d0=slot)
```

  Palette sets = game-side table of palette pointers. All sinks are engine buffers/state — assert no VDP port symbols in this file (comment the grep gate).
- [ ] **Step 3: Verify + commit.** Fixture program on a debug key: wait 60 → load set 1 → fade → loop 3× {set 0, wait 30, set 1, wait 30} → reset. Oracle: timing exact (frame-step), CRAM only changes via the normal DMA path, random-branch fixture picks varying targets across runs. `feat(engine): effect sequencer — byte-pair coroutine interpreter, palette programs`

### Task 4: Gradient + letterbox (CRAM_PACED, VSRAM, DISPLAY ops)

**Files:**
- Modify: `engine/raster/raster.asm` (ROP_CRAM_PACED=1, ROP_VSRAM=3, ROP_DISPLAY=4), `engine/raster/tracks.asm` (letterbox top/bottom tracks fed by sequencer op C), `test/ojz_scroll_test.asm` (fixtures)

- [ ] **Step 1: Research.** Spec §4.2 paced-variant requirements (HB-status-flag sync, NOT cycle constants — `btst #2,(VDP_ctrl+1)` polling pattern; the truncation guard); SpritesMind t=3201 ≤6 VSRAM words basis (spec §2); how VInt re-asserts display reg after a DISPLAY off/on frame (shadow untouched by handlers — VBlank `Flush_VDP_Shadow` restores).
- [ ] **Step 2: Implement.** `ROP_CRAM_PACED(addr,count,src)`: per HInt fire write 3 colors, sync each packet on the HB flag, self-re-arm delta 0 until count exhausted then next record. Gradient = paced records over N stops (data from a stop table: `{line, color_index, rgb}` compiled later by raster_gen — hand table now). `ROP_VSRAM(offset,count≤6,src)`, `ROP_DISPLAY(on/off)`. Letterbox: two tracked lines (targets set by sequencer op C, eased ±2 lines/frame in the track handler) with DISPLAY off at bottom-bar line + on at top-bar line next frame start — bars are true black regardless of palette. Fixtures: sunset gradient over OJZ sky; letterbox in/out on debug key.
- [ ] **Step 3: Verify + commit (DURING MOTION).** Gradient artifact-free at rest AND scrolling (paced writes land in HBlank — zero mid-line dots in captures); letterbox eases smoothly, gameplay continues; combined water+gradient script frame verifies multi-record chains (the self-test's promise in anger). `feat(engine): paced CRAM, VSRAM, display ops — gradient + letterbox effects`

### Task 5: parallax_gen.py + migration golden

**Files:**
- Create: `tools/parallax_gen.py`, `tools/tests/test_parallax_gen.py` (+ fixtures), `games/sonic4/data/editor/parallax/ojz_default.parallax.json` (+ one per live config)
- Modify: `build.sh`; Delete (end of task): the migrated `games/sonic4/data/parallax/*.asm` game data (engine `parallax_macros.inc` STAYS)

- [ ] **Step 1: Research.** `engine/parallax_macros.inc` full semantics (factor encodings: 24-bit packed shift-add, `FACTOR_*` constants; `deform_table_sine` params; `v_column_floor`); `structs.asm:176-196` (`parallax_config` 28-byte layout + `band_entry` 10-byte); which configs are LIVE (grep `ParallaxConfig_` refs in `act_descriptor.asm` + main.asm includes); how the current asm assembles (a reference build's bytes are the golden source — extract via a listing or a small AS fixture assembling just the configs).
- [ ] **Step 2: Failing tests.** Gate fixtures: unrepresentable fraction ("1/3"), unsorted bands, >8 bands, curve length ≠256, dangling curve ref — each exits nonzero. **Migration golden:** `ojz_default.parallax.json` → generator output bytes == the assembled `ParallaxConfig_OJZ_Default` + its deform tables (byte-for-byte). `pytest tools/tests/test_parallax_gen.py -v` → FAIL.
- [ ] **Step 3: Implement.** JSON schema per spec §6.1 (fractions as strings "1/8","5/8" → packed shift-add; curves `{type:sine,...}` or `{type:points,data:[...]}`) → emit `data/generated/parallax/parallax_data.asm` (structs + tables + labels preserving current `ParallaxConfig_*` names). Author JSON for every live config; goldens pass; wire into `build.sh`; build green with generated data replacing the asm includes; delete migrated game asm files (exact paths). `pytest` PASS.
- [ ] **Step 4: Verify + commit.** Full build + oracle OJZ circuit — parallax pixel-identical (screenshot diff at fixed camera positions vs pre-migration build). `feat(tools): parallax_gen — JSON configs, byte-equal migration, asm data retired`

### Task 6: raster_gen.py + v1 documents

**Files:**
- Create: `tools/raster_gen.py`, `tools/tests/test_raster_gen.py`, `games/sonic4/data/editor/raster/{ojz_water,ojz_sunset,letterbox,haze_scene}.{raster,parallax}.json` (haze = a parallax doc using the sine curve)
- Modify: `build.sh`, `structs.asm` (`sec_raster_script`/`act_raster_script` fields), `games/sonic4/data/levels/ojz/act1/act_descriptor.asm` (wire scripts), the Task-2/4 hand tables replaced by generated output

- [ ] **Step 1: Research.** The record/op formats as landed in Tasks 1-4 (they are the contract); `Sec`/`Act` struct field addition rules (structs are asserted — check `structs.asm` size asserts); slot-cost model: run the calibration ONE-TIME on oracle first — measure per-variant writes/HBlank via a DEBUG script that counts completed writes per fire; bake constants into the generator with a comment citing the measurement.
- [ ] **Step 2: Failing tests + implement.** Gates: unsorted/duplicate lines, slot cost > variant budget, unknown track/op, dangling palette-stop refs, sequencer program op F. Emit `data/generated/raster/raster_data.asm` (scripts, stop tables, sequencer programs, palette sets). Author the four v1 documents; replace Task-2/4 hand tables with generated equivalents (byte-compare); wire `sec_raster_script` resolution (mirror `sec_parallax_config` fallback in `Parallax_CheckBoundary`'s pattern — new `Raster_CheckBoundary` or fold into the same boundary walk). All tests PASS; build green.
- [ ] **Step 3: Verify + commit.** Oracle: water + gradient + letterbox + haze all playing from generated data across section boundaries (script switches on crossing). `feat(tools,engine): raster_gen + v1 documents; per-section script attachment`

### Task 7: Aurora parallax/raster mode + MCP tools

**Files (aurora repo — separate git):**
- Create: `src/core/formats/parallax.ts`, `src/core/formats/raster.ts` (Zod schemas mirroring the generators), `src/renderer/state/rasterStore.ts`, `src/renderer/components/raster/{BandEditor,CurveEditor,RasterTimeline,SequencerSteps}.tsx`, shared packer `src/core/formats/parallax-pack.ts` (struct-byte codec)
- Modify: `src/renderer/state/editorStore.ts` (`AppMode` + `'raster'`), `src/renderer/App.tsx` (branch + palette entry), `src/renderer/hooks/useProject.ts` (save both doc types), `src/main/editor-methods.ts` + `src/renderer/agent/agent-handler.ts` (tools: `get_parallax`, `set_parallax_bands`, `set_deform_curve`, `set_raster_splits`, `set_sequencer_program`, `push_preview` — push_preview stubs until Task 8)

- [ ] **Step 1: Research.** Design #7's Task-11 screen-mode wiring (the fourth-mode precedent — mirror it); `sprite/Timeline.tsx` rAF transport; how the map viewport renders the BG canvas (band guides overlay it); the generator JSON schemas as landed (Tasks 5-6 are the contract).
- [ ] **Step 2: Failing tests.** Vitest: schema round-trips for both doc types (parse fixture → serialize → deep-equal; reject bad fraction/curve); **codec golden**: `parallax-pack.ts` output bytes deep-equal a fixture generated by `parallax_gen.py` (checked-in binary fixture). FAIL first.
- [ ] **Step 3: Implement.** Band editor: horizontal band strips over the rendered BG, draggable boundaries (snap to cell), factor dropdowns limited to representable fractions. Curve editor: sine params or freehand 256-point draw, live curve overlay. Raster timeline: 224-line vertical strip, split markers (fixed line or track chip), palette-stop swatches. Sequencer steps: ordered op list editor. Save via atomic path; MCP handlers route through store commands (one undo step). Tests PASS.
- [ ] **Step 4: Verify + commit (aurora).** Edit a band boundary → save → aeon rebuild → visible change in oracle; MCP `set_raster_splits` round-trip + single-step undo. `feat(raster): parallax/raster authoring mode + MCP tools`

### Task 8: Aether client + DEBUG override live preview

**Files:**
- aeon: Modify `ram.asm` (DEBUG-gated `Parallax_Override_Flag.b` + pad + `Parallax_Override_Cfg` (28+8×10) + `Parallax_Override_Curves: ds.b 512`; `Raster_Override_Flag` + `Raster_Override_Buf: ds.b 128`), `engine/level/parallax.asm` (`Parallax_CheckBoundary` resolution: flag set → `lea Parallax_Override_Cfg` copy-then-use), `engine/raster/raster.asm` (prologue override check)
- aurora: Create `src/main/aether/oracle-client.ts` (net socket, NDJSON, initialize handshake, `write_memory`/`read_memory`/`screenshot`/`reload_rom` only), preview UI (connect toggle, push-on-change, reset-to-ROM)

- [ ] **Step 1: Research.** `empyrean/contract/protocol.md` §2.1 handshake + §7 transports; `empyrean/clients/python/aether.py` as the reference client (socket path resolution, framing); where the engine learns the override symbols' addresses for Aurora (export via `s4.lst` parse or a small generated `symbols.json` from the build — pick: generator emits `data/generated/preview_symbols.json` with the two block addresses).
- [ ] **Step 2: Implement.** aeon: override checks (copy whole struct into working state when flag set — never point at the override directly; flag semantics: Aurora writes payload first, flag last; engine clears nothing). Build emits `preview_symbols.json`. aurora: client with reconnect + graceful degrade; push pipeline: edit → debounce 50ms → pack via `parallax-pack.ts` → `write_memory(payload)` → `write_memory(flag=1)`; reset button writes flag=0.
- [ ] **Step 3: Verify + commit (both repos).** Oracle running OJZ: drag a band factor in Aurora → BG speed changes live same-second; drag a deform curve point → visible ripple change; rapid drag soak 30s → no tear/crash, `Lag_Frame_Count` stable; kill oracle → Aurora shows disconnected, editing unaffected; relaunch + reconnect works. `feat(engine): DEBUG override blocks` / `feat(aether): oracle client + live parallax preview`

### Task 9: Soak + docs + merge

**Files:**
- Modify: `docs/ENGINE_ARCHITECTURE.md` (§7.2 rewritten as-built raster script engine, §7.1 gradient shipped, §4.6 cross-ref, sequencer section added; the hblank-inline-jmp spec marked shipped), `docs/DEFERRED_WORK.md` (close raster_perspective's "needs HInt" blocker note, water_surface entry updated, dense-op + sprite-multiplex entries remain), `docs/superpowers/2026-07-02-design-week-queue.md` (log)

- [ ] **Step 1: Soak.** 10-minute oracle circuit: max diagonal scroll with water+gradient+haze active, letterbox in/out ×20, section-boundary script switches ×20, sequencer programs looping — `Lag_Frame_Count` within baseline+0, self-test PASS on 5 consecutive DEBUG boots, VRAM/CRAM state-hash spot checks.
- [ ] **Step 2: Docs.** ARCH sections rewritten as the design (clean-not-bolted-on); DEFERRED_WORK + queue log.
- [ ] **Step 3: Merge.** `git checkout master && git merge --ff-only feat/raster-authoring`; build green on master. Aurora repo merged separately.

---

## Self-review (done at write time)

- **Spec coverage:** §4 engine→T1/T2/T4 (+T6 attachment); §4.6 self-test→T1; §4.4 tracks/water→T2; §5 sequencer→T3 (letterbox/gradient hooks T4); §6 generators/migration→T5/T6; §7 Aurora mode→T7; §8 Aether+override→T8; §9 tagging enforced T1-T6 (grep gates); §10 testing distributed + calibration in T6 Step 1 + soak T9; §11 order followed. Gap check: haze v1 = parallax doc authored in T6 + edited in T7 — covered.
- **Placeholders:** none; the oscillator in T2 is a tagged identity (spec defers oscillators), #7-fade stub seam is explicit in the header.
- **Type consistency:** op ids (ROP_CRAM_BURST=0, PACED=1, REG=2, VSRAM=3, DISPLAY=4) uniform T1/T4/T6; record `{line_delta.b, op.b, args}` uniform; sequencer op table identical in T3 and T6's generator; `Parallax_Override_*` names match T8 aeon/aurora sides; `parallax-pack.ts` referenced in T7 (created) and T8 (used).
