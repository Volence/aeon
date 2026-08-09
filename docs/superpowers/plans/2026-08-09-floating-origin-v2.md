# Floating Origin (Continuous-Scroll Phase 4) Implementation Plan — v2

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **v2 provenance (2026-08-09).** This re-anchors the banked 9-task plan (`2026-07-02-floating-origin.md`, now SUPERSEDED) against live master `2f047e3`. The original predates THREE landmarks: the Sigil flip (all `.asm` → `.emp`, `main.asm` includes → `map.toml`), the engine/game split (RAM chains from `Engine_RAM_End`, game state lives in `games/sonic4/`), AND **art-streaming Phase 2 (merged to master `2f047e3` TODAY)** — which added a whole layer of world-derived streaming state the rebase must shift or prove position-independent. Every `.asm` path, `struct`/`ram.asm` reference, file:line, and build command has been translated to the `.emp`/Sigil/`map.toml` world and re-verified against master. Where a cited mechanism has since changed, the drift is corrected inline and flagged **DRIFT:**; where a spec claim no longer holds, it is flagged **SPEC-STALE:** for controller attention (collected in the self-review). A cold session needs ONLY this file plus the spec `docs/superpowers/specs/2026-07-02-floating-origin-design.md` (APPROVED) — reading the spec with the SPEC-STALE list in hand.

**Goal:** Remove the ~16-section-per-axis coordinate ceiling via an atomic floating-origin rebase — level size bounded by ROM only — so the mega-act tech demo (the other half of which is art-streaming Phase 2's ROM-capped art) can traverse arbitrarily far. Plus the (now much narrower — see SPEC-STALE #1) `section_id` byte→word finish.

**Architecture:** Three phases on one branch. **F1 (Tasks 2-5): the rebase machinery** — base counters + parallax-aligned delta derivation with build asserts, the single-owner `Rebase_Execute` with the Phase-2-folded shift-list + DEBUG audit walk, the trigger at the atomic frame point, `+World_Section_Base` at the **eight** lookup clusters (the original seven + the Phase-2 `PageCache_Prefetch` site), base-aware camera clamp, wrap-safe compares, and a force-rebase soak proving shift-list completeness. **F2 (Tasks 6-7): the `section_id` storage-carrier widening** — narrowed by the discovery that `SectionId` is *already* `u16` and `Section_FlatIDXY` *already* returns a word (SPEC-STALE #1); this phase only widens the byte STORAGE carriers, and is **decoupled + gated on a user ruling** (F1 alone unblocks up to 256 sections). **F3 (Task 8): 24-wide fixture grid + acceptance.** Task 9: docs + merge. Spec: `docs/superpowers/specs/2026-07-02-floating-origin-design.md`.

**Tech Stack:** 68000 assembly in the `.emp` tree (Sigil — `DEBUG=1 ./build.sh` drives the Sigil build; there are no `.asm` twins). oracle emulator MCP (controller-only). No generator changes except the F3 fixture descriptor (hand-written data, NOT under the daemon-watched editor tree).

---

## Standing rules for every task

**The `.emp` world (this is not the pre-Sigil tree the original plan assumed):**
- All engine sources are `.emp`. Every AS code block below is a *reference shape* — translate to `.emp`: `module` header, `proc` with `clobbers/preserves/out/requires/grants/in`, typed register params (`d0: u16`, `a0: *Sst`), `if DEBUG == 1 { }` not `ifdef __DEBUG__`, `ensure(cond, "msg")` not `if/fatal`, bare-symbol operands width-select automatically (two-symbolic mem-to-mem needs both widths spelled — see the `move.w (Block_Stage_Gen).w, (Pfx_Memo_Gen).w` idiom at tile_cache.emp:1246). Immediate shifts >8 split (`lsl.l #8` + `lsl.l #SECTION_SIZE_SHIFT-8`, the camera.emp:16-20 guard).
- **There is NO `games/sonic4/main.asm`.** ROM placement is `games/sonic4/map.toml` (`order` list + anchors/holes/budgets). **Every new byte-emitting section (each `proc`/`data` head-label in a new `.emp` module — `rebase.emp`) must be added to `map.toml`'s `order` list** in its correct union position (near the level-engine entries). The registry/pins/golden side is sigil-owned — coordinate with the sigil session.
- **RAM:** `engine/ram.emp` — `region lower_ram @ $FFFF0000..$FFFF8000` (`.l`-addressed buffers) / `region upper_ram @ $FFFF8000..SYSTEM_STACK, w_addressable` (hot `.w` data) with typed `vars` + `pad()`. Alignment/overlap are compiler checks now (the old AS even-alignment caveat is obsolete). `World_Section_Base_X/_Y` are engine-owned steady-state state → `engine/ram.emp` upper_ram (place near the camera block, or at the RAM tail to ripple only `Engine_RAM_End` — prefer the tail per the ram.emp tail-placement convention). DEBUG-only counters go inside the existing `if DEBUG == 1 @shape_divergent { }` block at ram.emp:281 (beside `Dbg_PageIn_Preempts`).
- **Structs / constants:** `engine/structs.emp` (`sizeof` is compiler truth, no manual `_len`); `engine/system/constants.emp` (`pub const`, `SECTION_SIZE=$0800`/`SECTION_SIZE_SHIFT=11` at :204-205 confirmed).

**The byte-changing-parcel ritual (rides EVERY aeon byte-emitting change):**
- `SIGIL_BLOB_LEN_DRIFT=warn`, rebuild BOTH sigil binaries, repin → refreeze `--ab`. `pins.rs` is a gate, not an input. **THREE test gates on every byte-changing task:** (1) hand-type the `repin`/`pins.rs` baseline (historically the missed step), (2) `native_full_rom` + any touched port-test anchors green, (3) `pins_rs_is_current` + `refreeze --check`. Sigil commits land on sigil master. Coordinate the registry/golden side with the sigil session. Do NOT invent waiver hacks — if a gate cannot be made green, pause for controller coordination.

**Build shapes:**
- Plain `./build.sh` → `s4.bin` with **sound ON** (default since the engine/game split). `DEBUG=1 ./build.sh` → **suffixed** `s4.debug.bin` / `s4.debug.lst`. DEBUG carries the asserts/self-tests/audit walk; a plain build proves nothing about them. Oracle symbol cross-checks use `s4.debug.lst`. Never plain-`./build.sh` in a shared hot tree mid-session without byte-verifying the loaded ROM afterward (the daemon plain-rebuilds `tools/ojz_strip_gen.py` edits).

**Verification & emulator:**
- **Every oracle/emulator step is CONTROLLER-ONLY (⚠ controller).** The emulator MCP from a subagent deadlocks the arbiter; the foreground controller session does ALL oracle work. Subagents build, edit, and reason — they never touch oracle.
- Verification is oracle-observed behavior, never build-success alone. **Verify during MOTION, not at rest** (at-rest screenshots hide scroll/parallax artifacts — the whole point of the pixel-identity gate is what happens ACROSS a rebase frame while scrolling). Oracle gotchas current 2026-08-05: absolute-path `reload_rom` + crc-verify (a relative path silently loads no cart), `press` not `hold`, screenshots via the input-replay net, `pgrep -a`. Oracle symbols go stale after `reload_rom` — cross-check against fresh `s4.debug.lst`.
- **The input-replay net is available** for deterministic circuits: `Input_Source=INPUT_PLAYBACK` over `Replay_OJZ_Fixture` / `Replay_OJZ_Slide_Fixture` (engine/system/replay.emp; poke recipe in the fixture header). The soak/acceptance runs benefit from replayed circuits + `emulator_state_hash` / memory reads at checkpoints, which is stronger than a hand-driven press circuit for the pixel-identity checks.

**Daemon-watched files — NOT touched by this plan:**
- The auto-commit daemon watches `tools/ojz_strip_gen.py` and `games/sonic4/data/editor/ojz/`. **No task here edits either** (the F3 fixture is a hand-written act descriptor OUTSIDE the editor tree). If any task turns out to need an edit under those paths, STOP and ask the user; never `--amend` near them.

**Git:**
- `git add` exact paths only (never `-A`/globs). Commit per green task. Branch `feat/floating-origin` off a clean master; merge to master ONLY at Task 9 (merge commit, repo habit). **Verify `git branch --show-current` before EVERY commit** (parallel sessions share the tree).

**Law:** `CODING_CONVENTIONS.md` is the law — read it before writing any `.emp`. `.s`/`.w`/`.l` on every branch/jump; `function`/comptime for all build-time math; typed struct literals; PascalCase routines/globals, ALL_CAPS constants, `.lowercase` locals; no `mulu`/`divu`.

**Precedent — the teleport-rebase ancestor:** the shipped continuous-scroll engine ALREADY performed pure coordinate rebases for section teleports (`docs/research/teleport-rebase.md`; the mod-64/mod-512 invariant note at bg.emp:173-179; the shipped teleport used `$1000` px). Continuous-scroll shipping then removed the per-frame teleport check (the "no section rebases" comment at ojz_scroll_test.emp:249-251). **Task 3 Step 1 must grep for any surviving teleport-rebase shift code** (`grep -rn "rebase\|Rebase\|teleport" engine/level/`) — if a shift routine or its shift-list survives in git history or dormant code, `Rebase_Execute` should be its lineal descendant, not a from-scratch reinvention. The shift discipline in that ancestor is the design floor.

---

### Task 1: Branch + baseline

**Files:** none created (scratchpad numbers only).

- [ ] **Step 1: Research.** Read the spec end-to-end WITH the self-review SPEC-STALE list open. Read the live surfaces fresh (current anchors on master `2f047e3`):
  - **RAM state** `engine/ram.emp` — the streaming-state block the shift-list touches: `Camera_X`/`Camera_Y` (:388-389, 16.16 long), `Camera_X_Biased`/`_Y_Biased` (:394-395), `Camera_X_Max`/`_Y_Max` (:414-415), `Camera_Art_Hold` (:419), tile-cache cursors `Cache_Left_Col`/`Head_Col`/`Top_Row`/`Bottom_Row` (:427-430), `Cache_Origin_Col`/`Row` (:431-432, NOT shifted), resume cells `Cache_Fill_Resume_Col`/`_Row` (:434-435) + `Cache_Fill_RowResume_Row`/`_Col` (:450-451), `Cache_Art_Stall` (:441), `Cache_Prev_Cam_Row` (:453), `Cache_Prev_Cam_X` (:455, **Phase-2, world-derived**), `Cache_H_Pfx_Dir`/`Accum` (:456-457), `Cache_Pfx_Row_Target`/`Col_Target` (:458-459, **Phase-2, world tile targets**), `Cache_Pfx_Skip_Armed`/`Lag_Flag` (:460-461, flags), `Block_Stage_Keys` (:467, fine-sec-keyed), `Section_Top/Bottom_Row_Written` (:471-472), `Section_Right/Left_Col_Written` (:479-480), `Section_Fwd/Bwd_Neighbor_Data` (:484-485), `Ring_Buffer` (:495) + `Ring_Count` (:498), `Entity_Scan_State` (:504), `Entity_Window_Center_ID` (:513), `Entity_Window_Anchor` (:514), `Entity_Window_OriginX/Y` (:515-516), `Camera_Y_Coarse_Prev` (:519), `Pfx_Memo_*`/`Cs_Memo_*` (:606-614, **Phase-2 memoize, gen-invalidated**), the **PageIn bookmark record** `PageIn_Saved_*` (:648-658), `PageIn_Queue`/`Pool_Table` (:669/:679), the **PageCache tables** `Page_Table`/`Page_Frames`/`Page_Queued_Bits` (lower_ram :114-116). Mark each field's category (SHIFT / QUIESCE / RE-DERIVE / INVARIANT) as you read — this IS the Task-3 shift-list.
  - **SST layout** `engine/objects/sst.emp` — `Sst (size: $50)`; the metadata block `slot_tag @ $2A`, `entity_section_id @ $2B` (**u8**), `entity_list_index @ $2C`, `layer @ $2D`, `frame_off @ $2E` (u16), `sst_custom @ $30` (32 B, tail word `$4E` = SST_interact). Note this is POST-sst-fold (SPEC-STALE #3).
  - **Section grid helpers** `engine/level/section.emp` — `Section_FlatIDXY` :102 (`(d2: u8, d3: GridY, a2: *Act) out(d0: SectionId)` — **`SectionId = u16` already**, types.emp:120), `Section_GetSecPtrXY` :128. The `sizeof(Sec)==66` / `flat×66 < $7FFF` ensures (:27, act_descriptor.emp:84).
  - **Frame order** `games/sonic4/test/ojz_scroll_test.emp` — `GameState_OJZScroll_Update` :228: RunObjects :233 → Camera_Update :241 → **[rebase point]** → Tile_Cache_Fill :247 → EntityWindow_Scan :260 → Section_UpdateColumns :266 → TouchResponse :269 → Render_Sprites :275 → Section_FlatIDXY diag :293 → Parallax_CheckBoundary :299 → Parallax_Update :317. And `GameState_OJZScroll_Init` :69 (Camera_Init :119).
  - **Camera** `engine/level/camera.emp` — `Camera_Update` :206, the clamp template `clamp_camera_axis_reg` :102-118 spliced at :305 (X) / :412 (Y), the MEGA-ACT ceiling header :96-100 ("Floating-origin Phase 4 removes the word truncation"), `Camera_Art_Hold` reads :210-212/:244-245/:312-313, `Camera_Init` :136 (Camera_X seed :147, Camera_Y :158, Camera_X_Max :180, Camera_Y_Max :186), `CAM_MAX_X_STEP=16` :22 (`CAM_MAX_Y_STEP=16` constants.emp:636).
  - **Parallax** `engine/level/parallax_dsl.emp` :16-40 (factor encodings), `games/sonic4/data/parallax/configs.emp` :91-98 (`ParallaxConfig_OJZ_Default`), `engine/level/parallax.emp` `Parallax_CheckBoundary` :153 (derive :155-161, Prev_Sec commit :175-176), `Parallax_Update` band loop, `Parallax_Snap_Pending` consume :527, `Parallax_Init` reseed :121-122.
  - **PageIn flush rules** `engine/level/page_in.emp` :529-568 (`PageIn_Flush` — READ the caller-rule comment :538-540 verbatim; it is quoted in Task 3).
- [ ] **Step 2: Branch.** `git checkout -b feat/floating-origin` from a clean master (verify `git branch --show-current` = master first; you branch FROM it).
- [ ] **Step 3: Baseline. ⚠ controller.** Build `DEBUG=1 ./build.sh`; load `s4.debug.bin` (absolute path + crc-verify); free-fly / replay a full OJZ circuit at max scroll both axes. Record to scratchpad: `Lag_Frame_Count` over a 600-frame run, mid-scroll screenshots, and an `emulator_state_hash` at a fixed parked position (the post-rebase pixel-identity reference for Tasks 5/8). Stock OJZ is 3×1 sections — thresholds are unreachable, so this baseline is what F1's base-0 build must reproduce byte-for-byte.

### Task 2: F1 — Base counters, delta derivation, build asserts

**Files:**
- Modify: `engine/system/constants.emp` (`REBASE_*`), `engine/ram.emp` (`World_Section_Base_X/_Y`), `engine/level/parallax_dsl.emp` (the `rebaseAssertBand` comptime helper), `games/sonic4/data/parallax/configs.emp` (per-config alignment asserts).
- Parcel ritual on all byte-emitting changes (constants/asserts emit no bytes; the RAM add ripples `Engine_RAM_End`).

- [ ] **Step 1: Research.** Read `parallax_dsl.emp:16-40` — the packed factor encoding (bits 0-3 = shift1, bits 4-7 = shift2, bit 8 = op; 15 = term-absent). Single-term factors map to a pure `camX >> shift`: `FACTOR_1`=0, `FACTOR_1_2`=1, `FACTOR_1_4`=2, `FACTOR_1_8`=3, `FACTOR_1_16`=4, `FACTOR_1_32`=5. Two-term composites (`FACTOR_5_8`, `FACTOR_3_8`, `FACTOR_7_8`, …) carry TWO shifts — each term must independently satisfy the mod-512 rule. **Audit `configs.emp` for every parallax config an OJZ act's sections can select** and record the slowest (largest-shift) single-term band and both shifts of any two-term band. Confirmed today: `ParallaxConfig_OJZ_Default` = Plane A `FACTOR_1` (shift 0) / Plane B `FACTOR_1_2` (shift 1), `v_factor_bg=3`; `ParallaxConfig_OJZ_Caves` reaches Plane B `FACTOR_1_16` (shift 4).

  > **SPEC-STALE #2 — the `REBASE_DELTA_X = $2000` *rationale* is wrong; the number is coincidentally right.** Spec §3 says the delta is forced by "OJZ's 1/16 band (`FACTOR_1_16`, `ojz_default.asm`)". The shipped `ParallaxConfig_OJZ_Default` has **no** 1/16 band — its slowest is `FACTOR_1_2` (shift 1), which needs only `512<<1 = $400`, so `max(SECTION_SIZE=$800, $400) = $800` = **one section**. `FACTOR_1_16` lives in `ParallaxConfig_OJZ_Caves`. `$2000` (= `512<<4`, 4 sections) is the correct minimum **only if act 1's sections can select the Caves config**. Derive the delta from the ACTUAL slowest band across the act's selectable configs — do not copy `$2000` blindly; if act 1 never selects Caves, `$800` is correct and cheaper (rebases fire 4× more often but each is a few hundred cycles). Document the chosen value's derivation in a comment.

- [ ] **Step 2: Constants + RAM.** In `constants.emp` (reference shape — translate to `.emp` `pub const` + `ensure`):

```asm
; floating origin (spec §3-4). DELTA per-axis, derived from the act's parallax bands (Step 1).
REBASE_THRESHOLD = $6000                 ; fine camera >= this -> down-shift
REBASE_DELTA_X   = $2000                 ; = max(SECTION_SIZE, 512 << slowest_H_band_shift). $800 if act 1 never selects Caves.
REBASE_DELTA_Y   = $1000                 ; = 512 << v_factor_bg (=3); 2 sections
; trigger sanity (spec §4): no chatter, threshold + max frame displacement below the signed ceiling.
        ensure((REBASE_THRESHOLD - REBASE_DELTA_X) > REBASE_DELTA_X, "REBASE X triggers can chatter")
        ensure((REBASE_THRESHOLD - REBASE_DELTA_Y) > REBASE_DELTA_Y, "REBASE Y triggers can chatter")
        ensure((REBASE_THRESHOLD + CAM_MAX_X_STEP) < $8000, "REBASE X threshold + max frame step overshoots the signed ceiling")
        ensure((REBASE_THRESHOLD + CAM_MAX_Y_STEP) < $8000, "REBASE Y threshold + max frame step overshoots the signed ceiling")
; whole-section invariant (base counter increments by whole sections)
        ensure((REBASE_DELTA_X & (SECTION_SIZE-1)) == 0, "REBASE_DELTA_X must be a whole number of sections")
        ensure((REBASE_DELTA_Y & (SECTION_SIZE-1)) == 0, "REBASE_DELTA_Y must be a whole number of sections")
```

  In `ram.emp` upper_ram (prefer the RAM tail — ripples only `Engine_RAM_End` + game RAM):
```asm
World_Section_Base_X: u16               ; sections renormalized past (X); zeroed at Camera_Init
World_Section_Base_Y: u16
```
  (`CAM_MAX_X_STEP` is camera-file-local at camera.emp:22 — either promote it to `constants.emp` beside `CAM_MAX_Y_STEP`:636 so the assert can see it, or duplicate the value with a drift `ensure`. Promoting is cleaner; note the byte-gate note at camera.emp:22-29 says that file-pair is the truth, so add a `use`/drift-guard rather than moving ownership.)

- [ ] **Step 3: Parallax-alignment assert, co-located with each config.** Add a comptime helper `rebaseAssertBand(factor, delta)` to `parallax_dsl.emp` that, given a packed factor, asserts `(delta >> shift1) & 511 == 0` and (if two-term) `(delta >> shift2) & 511 == 0`. In `configs.emp`, emit one `rebaseAssertBand(fa_or_fb, REBASE_DELTA_X)` per band per plane of each config (and `(REBASE_DELTA_Y >> v_factor_bg) & 511 == 0` for the BG vertical). Future configs get the guard by adding one line per band. **Deliberately break it** (temporarily set `REBASE_DELTA_X = $400`) to confirm the build FAILS with a clear message on the `FACTOR_1_16` band, then restore.
- [ ] **Step 4: Zero the base counters at level init.** In `Camera_Init` (camera.emp:136), beside the `Camera_X`/`Camera_Y` seeds (:147/:158), `clr.w World_Section_Base_X` / `clr.w World_Section_Base_Y`. This is the single site both bases zero.
- [ ] **Step 5: Build green + boot + commit. ⚠ controller.** `DEBUG=1 ./build.sh` green (parcel ritual done); boot reaches gameplay; OJZ renders as baseline. Verify branch. `feat(level): floating-origin base counters + parallax-aligned rebase deltas w/ build asserts (F1)`.

### Task 3: F1 — `Rebase_Execute` + DEBUG audit walk

**Files:**
- Create: `engine/level/rebase.emp` (+ its head-labels `Rebase_Execute`, `Rebase_DebugAudit` into `games/sonic4/map.toml` `order`).
- Modify: `engine/ram.emp` (DEBUG counter `Dbg_Rebase_Count` in the `@shape_divergent` block :281).
- Parcel ritual.

- [ ] **Step 1: Research.** Re-verify every shift-list field name against the Task-1 categorized read. `grep -rn "rebase\|Rebase\|teleport" engine/level/` for any surviving teleport-rebase shift code to descend from (the precedent note in Standing Rules). Confirm `TileCache_InvalidateStaging` (tile_cache.emp:190) exists and **bumps `Block_Stage_Gen`** (:197) — this is what auto-invalidates the `Pfx_Memo_*`/`Cs_Memo_*` prefetch memos, making them position-independent-by-invalidation (they need NO hand-shift). Confirm `EntityWindow_BuildEntries` (entity_window.emp:722). Confirm the ring entry layout (x@+0, y@+2, section_id@+4.b — `RING_BUFFER_ENTRY_SIZE=6`, constants.emp:187) and `Ring_Count` semantics (entries in use).

  **The complete Phase-2-folded shift-list (each field's disposition — the header CONTRACT):**

  | Field(s) | Disposition |
  |---|---|
  | `Cache_Fill_Resume_Col/_Row`, `Cache_Fill_RowResume_Row/_Col` | **QUIESCE to $FFFF** (nothing mid-flight to shift) |
  | `Block_Stage_Keys` (fine-sec-keyed) | **INVALIDATE** via `TileCache_InvalidateStaging` (also bumps `Block_Stage_Gen` → kills the memos) |
  | `Camera_X`, `Camera_Y` (16.16) | **SHIFT** high word by `∓DELTA` |
  | `Camera_X_Max`, `Camera_Y_Max` (fine-space extent ceilings) | **SHIFT** by `∓DELTA` — the forward extent shrinks/grows in fine space as the origin moves (NEW vs original; found in the camera-clamp audit) |
  | every SST `x_pos`/`y_pos` across `Object_RAM..Object_RAM_End` (Player_1/2 + Dynamic/System/Effect), stride `sizeof(Sst)`, skip `code_addr==0` | **SHIFT** |
  | `Ring_Buffer` X **and** Y per entry (count `Ring_Count`) | **SHIFT** |
  | world tile cursors `Cache_Left_Col`, `Cache_Head_Col`, `Cache_Top_Row`, `Cache_Bottom_Row`, `Cache_Prev_Cam_Row`, `Section_Right/Left_Col_Written`, `Section_Top/Bottom_Row_Written` | **SHIFT by DELTA/8** (tile units) |
  | `Cache_Prev_Cam_X` (Phase-2, last-frame camera px low word) | **SHIFT by DELTA** (px) — else the H-prefetch delta/hysteresis reads a phantom jump the rebase frame |
  | `Camera_Y_Coarse_Prev` (`camY & $FF80`) | **RE-DERIVE** (masked reseed from the rebased `Camera_Y`) |
  | `Cache_Pfx_Row_Target`, `Cache_Pfx_Col_Target` (Phase-2, this-frame prefetch targets) | **QUIESCE to $FFFF** — they are recomputed by the next `Tile_Cache_Fill`; a stale world-tile target pre-rebase is wrong. (Verify their lifetime at execution: if genuinely rebuilt-before-read every frame, quiesce is belt-and-suspenders; if read before rebuild, quiesce is mandatory.) |
  | `Pfx_Memo_Row/L/H/Gen`, `Cs_Memo_Col/T/B/Gen` (Phase-2 memoize) | **INVARIANT** — `Block_Stage_Gen` bump (from step-1 InvalidateStaging) makes the gen-key mismatch, so the memo self-invalidates. Cite the auto-invalidation; do NOT hand-shift. |
  | `Parallax_Prev_Sec_X/_Y` | **RESEED to $FF** (force a clean config re-select through the base-aware lookup) |
  | `Parallax_Snap_Pending` (Phase-2 lerp state) | **SET =1** — drops any in-flight Plane-B transition lerp (whose intermediate is a pre-rebase `-camX·factor` absolute). NEW vs original spec. |
  | `World_Section_Base_X/_Y` | `± DELTA/SECTION_SIZE` |
  | `Entity_Window_Anchor`, `Entity_Window_Center_ID`, `Entity_Window_OriginX/Y`, `Entity_Scan_State` (`ess_*`) | **RE-DERIVE** via `EntityWindow_BuildEntries` (rebuild, never hand-shift) |
  | `Camera_X_Biased/_Y_Biased` | **INVARIANT** — recomputed in `Render_Sprites` (frame order :275) after the rebase (:241-247), from the rebased `Camera_X/Y` |
  | `Camera_Art_Hold` (bit flags) | **INVARIANT** — position-independent bits; `Camera_Update` already consumed last frame's value before the rebase; `Tile_Cache_Fill` clears+resets it after. Verify no read between rebase and the next `Tile_Cache_Fill` observes a coordinate through it. |
  | `Page_Table`, `Page_Frames`, `Page_Queued_Bits`, `PageIn_Queue`, `PageIn_Pool_Table`, `PageIn_Saved_*` bookmark | **INVARIANT** — see the §9.7 + page-cache lemma below |
  | `Cache_Origin_Col/_Row` (physical ring indices), sub-pixel fractions, velocities, respawn/collected memory (section-id-keyed), static ROM data, `Section_Fwd/Bwd_Neighbor_Data` (ROM ptrs, position-independent) | **NOT shifted** |

  **The page-cache / §9.7 position-independence lemma (verify + state in the header):**
  - `PageIn_Flush` is **NOT called** by the rebase. Quote the shipped caller rule verbatim (page_in.emp:538-540): *"A pure section rebase does NOT flush — page identity is position-independent (spec §5), so the in-flight page is still the right page."* Page ids key off cache content, not coordinates.
  - **A rebase during a suspended decode is safe.** The bookmark banks the ZX0R decoder's live registers `PageIn_Saved_A0/A1/A2` = source (ROM compressed stream), destination (`Art_Staging_Buffer`), and back-reference cursor (within staging) — **none is a world coordinate** (ram.emp:637-658 comment). The corrected §9.7 lemma: vblank straddles are safe on either path because the banked registers hold STAGING/SOURCE pointers, not world coordinates, so a rebase that runs while a decode is suspended cannot corrupt the banked decoder state. State this explicitly in the `Rebase_Execute` header.

- [ ] **Step 2: Write `Rebase_Execute`** as an `.emp` proc, `in(d0: signed X pixel delta, d1: signed Y pixel delta)` (one may be 0; caller passes `±REBASE_DELTA_*`). The header comment carries the CONTRACT: *"every RAM field holding a live world coordinate MUST be shifted here; new world-coordinate fields register here or the DEBUG audit + soak catches you. Page-cache/bookmark state is position-independent by design (page ids key off content; banked decoder regs are staging/ROM pointers) — see the lemma above."* Reference shape (translate; complete the Y-side loops symmetrically where only X is shown):

```asm
; Rebase_Execute — atomic floating-origin shift (spec §5). Runs between
; Camera_Update and Tile_Cache_Fill (ojz_scroll_test.emp:241-247) where no
; world-derived consumer is mid-flight and VBlank only reads LAST frame's coords.
; In: d0.w = X pixel delta (signed, ±REBASE_DELTA_X or 0), d1.w = Y likewise.
Rebase_Execute:
        ; 1) quiesce partial fills + this-frame prefetch targets
        moveq   #-1, d2
        move.w  d2, Cache_Fill_Resume_Col
        move.w  d2, Cache_Fill_Resume_Row
        move.w  d2, Cache_Fill_RowResume_Row
        move.w  d2, Cache_Fill_RowResume_Col
        move.w  d2, Cache_Pfx_Row_Target
        move.w  d2, Cache_Pfx_Col_Target
        ; 2) staged blocks are fine-sec-keyed -> stale (also bumps Block_Stage_Gen -> kills memos)
        jbsr    TileCache_InvalidateStaging
        ; 3) camera 16.16 (shift the pixel high word) + fine-space extent ceilings
        sub.w   d0, Camera_X            ; high word is at the low address of the .l on 68k big-endian — VERIFY the 16.16 layout and subtract from the INTEGER word
        sub.w   d1, Camera_Y
        sub.w   d0, Camera_X_Max        ; ceiling moves with the origin
        sub.w   d1, Camera_Y_Max
        ; 4) every SST across all pools + players
        lea     Object_RAM, a0
        move.w  #(Object_RAM_End-Object_RAM)/sizeof(Sst)-1, d3
.obj:   tst.w   Sst.code_addr(a0)
        beq.s   .obj_next
        sub.w   d0, Sst.x_pos(a0)
        sub.w   d1, Sst.y_pos(a0)
.obj_next: lea   sizeof(Sst)(a0), a0
        dbf     d3, .obj
        ; 5) ring buffer: X AND Y per entry
        ; (lea Ring_Buffer; loop Ring_Count; sub d0 (a0), sub d1 2(a0); addq RING_BUFFER_ENTRY_SIZE)
        ; 6) world tile cursors: delta/8
        move.w  d0, d2
        asr.w   #3, d2                  ; X tile delta
        sub.w   d2, Cache_Left_Col
        sub.w   d2, Cache_Head_Col
        sub.w   d2, Section_Right_Col_Written
        sub.w   d2, Section_Left_Col_Written
        sub.w   d0, Cache_Prev_Cam_X    ; Phase-2: last-frame camera px (whole px, not /8)
        ; ... symmetric Y block: asr d1 #3 -> Cache_Top_Row, Cache_Bottom_Row,
        ;     Cache_Prev_Cam_Row, Section_Top_Row_Written, Section_Bottom_Row_Written
        ; 7) coarse Y baseline: masked reseed from the rebased Camera_Y
        ; 8) parallax: force clean re-select + drop in-flight lerp
        st.b    Parallax_Prev_Sec_X
        st.b    Parallax_Prev_Sec_Y
        st.b    Parallax_Snap_Pending
        ; 9) base counters: delta / SECTION_SIZE
        move.w  d0, d2
        asr.w   #SECTION_SIZE_SHIFT, d2  ; asr max is 8 — split (swap/asr#3) or note SECTION_SIZE_SHIFT=11 needs asr#8+asr#3; delta magnitude fits
        add.w   d2, World_Section_Base_X
        ; ... symmetric Y
        ; 10) derived state: rebuild, never hand-shift
        jbsr    EntityWindow_BuildEntries
    if DEBUG == 1 {
        addq.w  #1, Dbg_Rebase_Count
        jbsr    Rebase_DebugAudit
    }
        rts
```

  Notes to resolve while writing (research, don't guess): the exact 16.16 layout of `Camera_X` (68k big-endian: integer word at the lower address — subtract `d0` from the integer word, i.e. `sub.w d0, Camera_X` hits the high word; VERIFY against how Camera_Update writes it at :116 `move.l d0,{cam}` after `swap`); `asr.w #SECTION_SIZE_SHIFT` exceeds the max shift-8 — split it; player slots ARE inside `Object_RAM` (Player_1/Player_2 are the first two SSTs, ram.emp:346-347), so the single walk covers them; sub-pixel words untouched by construction (whole-pixel delta).
- [ ] **Step 3: `Rebase_DebugAudit`** (DEBUG only): walk the same live-coordinate fields; `raise_error` if any live world coordinate ≥ `REBASE_THRESHOLD` or < `-$1000` (allow despawn margin — objects may sit slightly outside the window; bound `[-$1000, REBASE_THRESHOLD+$1000]`), any resume/prefetch-target key ≠ `$FFFF` immediately post-rebase, or `Entity_Window_OriginX/Y` inconsistent with the rebased `Camera_X/Y` (recompute + compare).
- [ ] **Step 4: Build green (routine assembled, not yet called) + commit. ⚠ controller.** Green; boot unaffected (nothing calls it yet). Verify branch. `feat(level): Rebase_Execute — single-owner atomic shift + DEBUG audit, Phase-2 streaming state folded (F1)`.

### Task 4: F1 — Trigger + the eight lookup clusters + base-aware clamp + wrap-safe compares

**Files:**
- Modify: `games/sonic4/test/ojz_scroll_test.emp` (trigger at :249-251; diagnostic derive :288/:291), `engine/level/camera.emp` (base-aware clamp :102-118, :305/:412), `engine/level/parallax.emp` (:158/:161), `engine/level/section.emp` (:383/:385), `engine/objects/entity_window.emp` (:691/:697, :837/:840, :1693/:1696), `engine/level/tile_cache.emp` (decompose_block :55/:57 + FillAll :642/:645), `engine/level/page_cache.emp` (**8th cluster** :557/:569/:588/:600), `engine/objects/collision.emp` + `engine/objects/aabb.emp` + `engine/objects/entity_window.emp` (wrap-safe compares), `games/sonic4/data/levels/ojz/act1/act_descriptor.emp` (ceiling ensure).
- Parcel ritual.

- [ ] **Step 1: Research.** Re-map the frame order (Task 1). Confirm the eight derive→lookup clusters and that each adds `+World_Section_Base_axis` (in SECTION units) to `sec_x`/`sec_y` **after** the shift/decompose, **before** the flat-id/grid-pointer use. The px-shift clusters (`>> SECTION_SIZE_SHIFT`) and the tile-decompose clusters (`>> 8`) both yield section units, so the base add is uniform. Read the MEGA-ACT ceiling header (camera.emp:96-100) and the act_descriptor ensures (`(GRID_* << SECTION_SIZE_SHIFT) <= $8000` grid≤16; `MAX_ACT_SECTIONS × sizeof(Sec) < $7FFF`, :84) — Task 4 replaces the grid≤16 clamp assert with a "grid fits `SectionId` word + `flat×66 < $7FFF`" assert (the latter already exists).
- [ ] **Step 2: Trigger.** Replace the "no section rebases" comment at ojz_scroll_test.emp:249-251 with a `jbsr Rebase_Check` (immediately after `Camera_Update` at :241, before `Tile_Cache_Fill` at :247). Reference shape:

```asm
Rebase_Check:
        moveq   #0, d0                  ; X delta
        move.w  Camera_X, d2            ; fine integer word (16.16 high word)
        cmpi.w  #REBASE_THRESHOLD, d2
        blt.s   .x_lo
        move.w  #REBASE_DELTA_X, d0     ; down-shift
        bra.s   .x_done
.x_lo:  tst.w   World_Section_Base_X
        beq.s   .x_done
        cmpi.w  #REBASE_DELTA_X, d2
        bge.s   .x_done
        move.w  #-REBASE_DELTA_X, d0    ; up-shift (backward travel)
.x_done: ; ...same for Y into d1...
        move.w  d0, d3
        or.w    d1, d3
        beq.s   .none
        jbsr    Rebase_Execute
.none:  rts
```

  (Both axes may rebase the same frame; the audit runs after both — a single `Rebase_Execute` call with both deltas handles it.)
- [ ] **Step 3: The eight `+World_Section_Base` sites.** At each cluster, after the section coord is derived, add the base (X or Y) before the flat-id/grid use. Helpers (`Section_FlatIDXY`/`Section_GetSecPtrXY`) stay base-AGNOSTIC — callers add the base. Sites (file:line of the derive; add the base there):
  1. `parallax.emp:158,161` (Parallax_CheckBoundary, camera-center px-shift) → GetSecPtrXY :171
  2. `section.emp:383,385` (Section_RedrawPlanes, camera-origin px-shift) → GetSecPtrXY :386
  3. `entity_window.emp:691,697` (DeriveWindow — mind the clamp-to-0 at :692-700: clamp in FINE space, add base after)
  4. `entity_window.emp:837,840` (init recenter) → FlatIDXY :842; and BuildEntries :728-732/:742-749 → GetSecPtrXY :751 + FlatIDXY :754
  5. `entity_window.emp:1693,1696` (slide recenter) → FlatIDXY :1700
  6. `tile_cache.emp:55,57` (`decompose_block` macro, tile `>>8`) **and** :642,645 (FillAll, `BLOCKS_PER_SECTION_SHIFT`) → DecompressBlock sec_id :254-262
  7. `ojz_scroll_test.emp:288,291` (diagnostic) → FlatIDXY :293
  8. **`page_cache.emp:557,569,588,600`** (PageCache_Prefetch, tile `>>8`) → FindStagedBlock :575/:606 — **NEW Phase-2 cluster the original 7-site list did not have.**

  Grep for any OTHER section-derive that appeared since: `grep -rn "SECTION_SIZE_SHIFT\|BLOCKS_PER_SECTION_SHIFT\|decompose_block\|>> 8" engine/ games/`.
- [ ] **Step 4: Base-aware camera clamp.** The clamp template `clamp_camera_axis_reg` (camera.emp:102-118) compares the fine camera against `Camera_X_Max`/`Camera_Y_Max`. Since Task 3 now SHIFTS `Camera_X_Max/_Y_Max` on every rebase (they track the moving origin), the clamp stays a fine-space compare and needs **no change** — but VERIFY: the ceiling must represent the remaining forward extent in fine space (`grid_extent − base×SECTION_SIZE − SCREEN`). Confirm the Task-3 shift keeps it consistent; if the audit or soak shows the camera clamping early/late near a rebase, the ceiling shift is the bug. Update the MEGA-ACT header comment (:96-100) to "shipped" and relax the act_descriptor grid≤16 ensure to the word-`SectionId`/`flat×66<$7FFF` bound.
- [ ] **Step 5: Wrap-safe compares.** The hot live-vs-live position compares that could wrap at `$8000`: the AABB axis test (`aabb.emp:53-54`, template; instantiated `collision.emp:44,54`; compared `collision.emp:257`) and the entity despawn bands (`entity_window.emp:1445/1447` X, :1466/1469 Y for rings; the symmetric object-side in `EntityWindow_DespawnObjects` :1521). **These are ALREADY bounded** — the aabb template carries the wrap note at :58-60 ("cull windows bound |delta| << $4000; a new caller with unbounded delta must guard") and the despawn bands compare within a `±ENTITY_DESPAWN_BUFFER` window. Given floating origin keeps live separation ≤2 screens by construction, wrap is unreachable. So this step is **belt-and-suspenders**: where the idiom is `move.w a; cmp.w b; b<cond>` on two live world positions, prefer `sub.w` + sign-branch on the difference and comment `; wrap-safe: signed difference`. Convert only clear live-vs-live sites; leave the base-aware clamps alone. (If time-boxed, the existing bounds make this deferrable — record it in the commit if skipped.)
- [ ] **Step 6: Build + oracle. ⚠ controller.** Green; boot; full baseline circuit — base 0, thresholds unreachable on stock OJZ (3 sections) → behavior pixel-identical to Task 1 baseline (screenshot + state-hash compare). Verify branch. `feat(level): rebase trigger at the atomic point + base-aware section lookups (8 clusters incl. PageCache_Prefetch) + wrap-safe compares (F1)`.

### Task 5: F1 — Force-rebase soak (F1 acceptance)

**Files:**
- Modify: `engine/system/constants.emp` (DEBUG soak values), `build.sh` (`REBASE_SOAK=1` flag).
- Parcel ritual.

- [ ] **Step 1: Research.** Confirm stock OJZ extent (3×1 sections = `$1800` px). Soak thresholds must trigger INSIDE it. Note `REBASE_DELTA_X=$2000 > $1800` — so an X soak on stock OJZ must use a smaller delta.
- [ ] **Step 2: Soak build.** Under `REBASE_SOAK=1`+DEBUG: `REBASE_THRESHOLD = 2*SECTION_SIZE` ($1000). For X, use `REBASE_DELTA_X = $800` (1 section) with the parallax assert satisfied by the DEFAULT config alone (Plane B `FACTOR_1_2` needs only `$400`) — so on stock OJZ (default config, no Caves) `$800` is parallax-clean AND fits inside `$1800`. Document this in the flag's comment: the soak's job is shift-list completeness, not the Caves-delta. (If act 1 CAN select Caves at runtime, the soak circuit must avoid those sections or accept a documented 64px canopy jump on the Caves band under soak only.)
- [ ] **Step 3: The soak. ⚠ controller.** Oracle, soak build: **(a)** scroll a full circuit right→left→right — `Dbg_Rebase_Count` climbs both directions; **(b) pixel-identity:** park; note `emulator_state_hash`; scroll right until exactly one rebase fires; scroll back to the identical parked position; screenshot + compare against the pre-rebase screenshot (identical), and confirm player/object/ring positions in RAM differ from pre-rebase by exactly `base×SECTION_SIZE` (fine coords rebased, absolute unchanged); **(c)** collect rings, cross several rebases, return — collected rings STAY collected (respawn/collected memory is section-id-keyed and invariant); **(d)** `Rebase_DebugAudit` clean throughout (no `raise_error`); **(e)** diagonal + vertical variants (Y deltas fire); **(f)** `Lag_Frame_Count` for the run ≈ baseline (the rebase event itself — a few hundred cycles — must not register as lag).
- [ ] **Step 4: Commit.** Verify branch. `feat(level): force-rebase soak passes — Phase-2-folded shift-list complete (F1 accepted)`.

### Task 6: F2 — `section_id` storage-carrier widening (⚠ decoupled + user-ruling-gated)

> **SPEC-STALE #1 — the widening is HALF DONE; F2 is now narrow AND decoupled.** Spec §7 frames "`section_id` byte→word" as widening carriers AND the flat-id computation AND `Section_FlatIDXY`'s return. **The computation side already shipped:** `SectionId = u16` (types.emp:120), `Section_FlatIDXY` already `out(d0: SectionId)` = word (section.emp:102), the `flat×66 < $7FFF` bound already guards `Section_GetSecPtrXY` (act_descriptor.emp:84). What remains is ONLY the byte STORAGE carriers, and they cap a level at **256 sections total** — which **F1 alone does NOT require** (F1 unblocks arbitrary *coordinate range*; the 256-section cap is a separate, independent ceiling). **So F2 is decoupled from F1 and only matters for acts with >256 sections.** The 24-wide F3 fixture (24 sections) does NOT need it.
>
> **OPEN QUESTION FOR THE USER (gates this task):** Does the mega-act target exceed 256 sections? If not, F2 can be DEFERRED (register it in DEFERRED_WORK, ship F1 + F3, done). If yes, F2 proceeds — AND its SST relayout needs a ruling (below). Do not execute Task 6-7 without this ruling.

**Files (if the ruling is "proceed"):**
- Modify: `engine/system/constants.emp` (`SEC_VOID $FF→$FFFF`, `RING_BUFFER_ENTRY_SIZE 6→8`), `engine/objects/sst.emp` (`entity_section_id` byte→word — see the relayout ruling), `engine/structs.emp` (`EntityScanState.ess_section_id` byte→word + re-pad), `engine/ram.emp` (`Ring_Buffer` sizing, `Entity_Window_Center_ID` byte→word), `engine/objects/entity_window.emp` (all `d0.b = section_id` params → `d0.w`, ~9 sites), `engine/objects/rings.emp` + `engine/level/section.emp` (ring producers/consumers, `SEC_VOID` compares), the collected/killed park id byte, object spawn/despawn sites reading `entity_section_id`.
- Parcel ritual.

> **SPEC-STALE #3 — the SST relayout recipe is obsolete.** Spec §7 says "SST `$2A-$2D` metadata block relayout, `sst_custom` base moves to `$30`." The **sst-fold (2026-08-05) already did that** — `sst_custom` is ALREADY at `$30`, and `frame_off` now owns `$2E-$2F`. The metadata block `$2A-$2D` is fully packed (`slot_tag @ $2A` niche TagRef, `entity_section_id @ $2B`, `entity_list_index @ $2C`, `layer @ $2D`); there is **no free byte** to widen `entity_section_id` into. Widening it to a word requires stealing 2 bytes from `sst_custom` (32→30 usable; `PlayerV` uses 18 of 30, so 12→10 free — assert headroom) and re-laying the `$2B-$2F` region. **This is a layout change to the engine's most load-bearing struct — get a user ruling on the exact new layout before touching it.**

- [ ] **Step 1: Research + USER RULING.** Confirm the >256-section question and the SST-relayout ruling above. Grep EVERY carrier: `grep -rn "entity_section_id\|SEC_VOID\|RING_BUFFER_ENTRY_SIZE\|Entity_Window_Center_ID\|Entity_Window_Anchor\|ess_section_id\|section_id" engine/ games/ tools/`. Check whether any GENERATOR bakes byte section ids into ROM data (entity export) — if so this gains a daemon-coordination step (ASK THE USER). Verify `Entity_Window_Anchor [u8;2]` stays 2 bytes (it holds grid coords sec_x0/sec_y0, NOT flat ids — verify, don't assume).
- [ ] **Step 2: The format change, one pass.** `SEC_VOID = $FFFF`; ring entry `{x.w, y.w, section_id.w, list_index.b, pad.b}` (`RING_BUFFER_ENTRY_SIZE = 8`; resize `Ring_Buffer`; re-verify RAM overflow guards); `entity_section_id` byte→word per the SST ruling; `EntityScanState.ess_section_id` byte→word (re-pad `(size:$1A)` even); `Entity_Window_Center_ID` byte→word; every `d0.b`/`cmp.b` section-id site widened to word. `Section_FlatIDXY` already returns word — its callers stop truncating to byte on store. The collected/killed park id byte widens if its keys can exceed 256 (verify the park id semantics first).
- [ ] **Step 3: Build + BOOT (mandatory — struct/RAM change) + verify. ⚠ controller.** Full circuit; ring collect/respawn matrix: collect in 3 sections, leave window, return — collected stay collected, uncollected respawn; object despawn/respawn across sections; `SEC_VOID` paths (grid edge) exercised at the level boundary. Verify branch. `feat(level): section_id storage carriers widened to word — 256-section cap removed (F2)`.

### Task 7: F2 regression — soak re-run

- [ ] **Step 1: ⚠ controller.** Re-run the entire Task 5 soak matrix on the widened build (the widening touched the exact fields the rebase shifts and the window rebuilds). All gates identical. Commit only if something needed fixing. `test(level): F2 regression — force-rebase soak clean on widened section_id`.

### Task 8: F3 — wide-grid fixture + acceptance

**Files:**
- Create: `games/sonic4/data/levels/ojz/act1_wide/act_descriptor.emp` (fixture — hand-written, NOT under the daemon-watched editor tree) + its head-label into `map.toml` `order`.
- Modify: `build.sh` (`WIDE_GRID=1` selects the fixture descriptor), `games/sonic4/test/ojz_scroll_test.emp` (conditional descriptor select at the `OJZ_Act1_Descriptor` lea sites — :166/:171/:194).

- [ ] **Step 1: Research.** Read the Act descriptor + `Sec` grid format (`act_descriptor.emp` + the `Sec` struct). Confirm grid entries are section POINTERS (reusable) and that per-section fields are position-INDEPENDENT (sections are position-independent by §4.9 design — verify `sec_objects`/`sec_rings`/`sec_block_dict` are section-local). **Cross-reference DEFERRED_WORK #7 (the pre-DAC ROM hole):** floating origin is the mega-act's *coordinate* half; #7 is its *ROM-layout* half — a 24-wide fixture that REUSES OJZ's 3 section pointers adds ~0 ROM (pure descriptor data), so it fits the pre-DAC hole; but note in the commit that a REAL mega-act's distinct section data will hit the ~21KB pre-DAC slack ceiling (#7), which floating origin does not solve.
- [ ] **Step 2: Fixture.** `act1_wide`: grid 24×1 repeating OJZ's three section pointers cyclically; same art pool, same parallax config. Update the descriptor grid-extent ensure to width 24 (24 sections is fine as byte section_id if F2 was deferred; ≤65535 with F2). With F2 DEFERRED, 24 ≤ 256 so byte ids are fine — this is the proof F1 alone unblocks the mega-act's coordinate range up to the byte-id cap. Build variant via `WIDE_GRID=1`.
- [ ] **Step 3: Acceptance matrix (normal thresholds — real rebases at $6000). ⚠ controller.** Oracle, `WIDE_GRID` build: **(a)** traverse all 24 sections right at max scroll — 5+ down-rebases fire (`$2000` delta over 24×`$800`=`$C000` extent → ~5 rebases); terrain/rings/objects correct in every repeated section; **(b)** traverse back — up-rebases mirror; **(c)** collect rings in sections 1, 12, 23 — memory correct across the whole run and after returning; **(d)** pixel-identity spot-checks straddling rebases (Task 5 method); **(e)** `Lag_Frame_Count` for the full run ≈ baseline per-section rate (the rebase event must not register); **(f)** `Rebase_DebugAudit` clean; **(g) cross the OLD ceiling:** park at absolute x > `$8000` (section 17+), verify collision, touch response, spawning, parallax all correct — the signed-op failure class is dead.
- [ ] **Step 4: Commit.** Verify branch. `feat(level): 24-wide fixture grid — >16-section traversal accepted (F3)`.

### Task 9: Docs + merge

**Files:**
- Modify: `docs/ENGINE_ARCHITECTURE.md`, `docs/superpowers/specs/2026-06-22-continuous-scroll-traversal-design.md` (§9 pointer note), `docs/DEFERRED_WORK.md`, `docs/superpowers/2026-07-02-design-week-queue.md`.

- [ ] **Step 1: ARCH.** Write the floating-origin section as the design (coordinate model, delta rule + the corrected per-act-config derivation, the Phase-2-folded shift contract, the eight lookup sites, the page-cache/§9.7 position-independence lemma); mark continuous-scroll Phase 4 SHIPPED; update the §4.2/§4.9 mentions of the 16-section ceiling; **fix the `SectionId`-already-word reality** wherever docs imply section_id is a byte. Add a one-line banner to continuous-scroll §9: "superseded by the 2026-07-02 spec, as-built per this section". Update the MEGA-ACT ceiling note (camera.emp:96-100 references) to "shipped".
- [ ] **Step 2: DEFERRED_WORK.** Close the Phase-4 line. Register follow-ups: `EDGE_WRAP_V` now unblocked (same `Rebase_Execute` machinery, applied modulo at the level edge); the Tails position-history ring (design #3) must join the shift-list when built (the character-dispatch v2 Task 8 Step 1 already flags this — cross-link it); **if F2 was deferred, record the 256-section cap explicitly** with the SST-relayout ruling need; cross-link #7 (pre-DAC hole) as the mega-act's remaining ROM-layout blocker (floating origin solved coordinates, not ROM placement).
- [ ] **Step 3: Final gates + merge. ⚠ controller.** Full `DEBUG=1 ./build.sh` + plain `./build.sh` both green; baseline (non-soak, non-wide) circuit pixel-identical to Task 1; the `WIDE_GRID` acceptance re-run once more; merge `feat/floating-origin` → master (merge commit per repo habit — verify branch at each commit); update the design-week queue log (design #2 EXECUTED).

---

## Self-review (done at write time, v2)

- **Spec coverage:** §2 (coordinate model)→T2; §3 (delta + asserts)→T2 (+ SPEC-STALE #2 correction); §4 (trigger)→T4 (+ T2 asserts); §5 (shift event, one owner, audited)→T3 (Phase-2-folded shift-list) + T4 (placement); §6 (absolute lookups + tactical adoptions)→T4 (8 clusters + wrap-safe compares); §7 (section_id widening)→T6-7 (narrowed per SPEC-STALE #1/#3, user-gated); §8 (what it doesn't touch)→T3 lemma; §9 F1/F2/F3→T2-5/T6-7/T8; §10 risks→T3 contract header, T5 soak, T8(g); §11 provenance→carried.
- **Sigil-flip translation:** every `.asm` path → `.emp`; `main.asm` include → `map.toml` `order` entry for `rebase.emp`; `struct`/`ram.asm` → `engine/structs.emp`/`engine/ram.emp`; `ifdef __DEBUG__` → `if DEBUG == 1 {}`; `if/fatal` asserts → `ensure(...)`; build = `DEBUG=1 ./build.sh` → suffixed `s4.debug.bin/.lst`; the parcel ritual (SIGIL_BLOB_LEN_DRIFT=warn, rebuild both sigil binaries, repin→refreeze --ab, THREE test gates) rides every byte-changing task.
- **Standing-rules markers:** ⚠ controller on every oracle step; parcel ritual on every byte-emitting change; verify-branch-before-commit throughout; merge only at Task 9; daemon-watched paths confirmed NOT touched (the F3 fixture is a hand-written descriptor OUTSIDE `data/editor/ojz/`).
- **Phase-2 streaming state folded into the shift-list (the core v2 work):** `Cache_Prev_Cam_X` (SHIFT px), `Cache_Pfx_Row/Col_Target` (QUIESCE), `Pfx_Memo_*`/`Cs_Memo_*` (INVARIANT via `Block_Stage_Gen` bump), `Parallax_Snap_Pending` (SET — drop in-flight lerp), `Camera_X_Max/_Y_Max` (SHIFT — moving extent ceiling, found in the camera-clamp audit), `Camera_Art_Hold` (INVARIANT bits), `Page_Table/Frames/Queued_Bits`/`PageIn_Queue`/`PageIn_Saved_*` bookmark (INVARIANT — position-independent by design), the 8th `PageCache_Prefetch` lookup cluster. `PageIn_Flush` is NOT called by the rebase (shipped caller rule at page_in.emp:538-540, quoted in T3). §9.7 lemma: banked decoder regs are staging/ROM pointers, not world coords — a rebase during a suspended decode is safe.
- **Anchors re-verified against master `2f047e3` (drift fixed inline):** frame order → ojz_scroll_test.emp:228-317 (rebase point :249-251); `Camera_Update` → camera.emp:206, clamp :102-118/:305/:412, `Camera_Init` :136, `CAM_MAX_X_STEP` :22; `Section_FlatIDXY` → section.emp:102 (`SectionId=u16`), `Section_GetSecPtrXY` :128; the eight clusters listed in T4 Step 3; `PageIn_Flush` → page_in.emp:529-568; SST metadata → sst.emp:65-84 (post-fold); parallax factors → parallax_dsl.emp:16-40, OJZ default → configs.emp:91-98.
- **SPEC-STALE claims flagged for controller attention (do NOT trust the spec verbatim on these):**
  1. **The `section_id` widening is half-done.** `SectionId` is already `u16` and `Section_FlatIDXY` already returns a word; only the byte STORAGE carriers remain, they cap at 256 sections, and that cap is INDEPENDENT of F1. F2 is decoupled + user-ruling-gated (>256 sections? + SST relayout). (spec §7)
  2. **`REBASE_DELTA_X = $2000`'s rationale is wrong.** The shipped `ParallaxConfig_OJZ_Default` has no `FACTOR_1_16` band (its slowest is `FACTOR_1_2`, needing only `$800` = 1 section); `FACTOR_1_16` is in `ParallaxConfig_OJZ_Caves`. `$2000` is right only if act 1 can select Caves — derive from the actual slowest selectable band. (spec §3, and its `ojz_default.asm` file reference is stale — the config lives in `configs.emp`)
  3. **The SST `$2A-$2D` relayout recipe is obsolete.** The sst-fold (2026-08-05) already moved `sst_custom` to `$30` and put `frame_off` at `$2E-$2F`; `$2A-$2D` is fully packed. Widening `entity_section_id` to a word must steal 2 bytes from `sst_custom` — a layout change to the most load-bearing struct, needing a user ruling. (spec §7)
  4. **`Parallax_Snap_Pending` did not exist when the spec was written.** The Phase-2 parallax transition lerp means the rebase must SET it (drop the in-flight intermediate), beyond the spec's reseed-`Prev_Sec` step. (spec §5, pre-Phase-2)
- **OPEN QUESTIONS needing user rulings (these GATE execution):**
  - **[gates T6-T7] Does the mega-act exceed 256 sections?** If no → defer F2. If yes → F2 proceeds AND needs the SST-relayout ruling (which 2 bytes of `sst_custom` does `entity_section_id` take, and the exact `$2B-$2F` layout).
  - **[gates T2 delta choice] Can OJZ act 1's sections select the Caves parallax config at runtime?** Yes → `REBASE_DELTA_X = $2000`. No → `$800` (cheaper, 1 section). Affects the soak (T5) too.
  - **[informs T5 soak] Accept a documented 64px canopy jump on the Caves band under `REBASE_SOAK` only, or route the soak circuit around Caves sections?**
- **Placeholders:** none — the two deliberately-open implementation choices (`Camera_X` 16.16 subtract form; the `asr #SECTION_SIZE_SHIFT` split) are flagged decisions with the deciding criterion stated. The three open questions above are user rulings, not placeholders.
- **Consistency:** `World_Section_Base_X/_Y`, `REBASE_DELTA_X/_Y`, `REBASE_THRESHOLD`, `Rebase_Execute`/`Rebase_Check`/`Rebase_DebugAudit`, `Dbg_Rebase_Count`, `SEC_VOID`, `RING_BUFFER_ENTRY_SIZE` used uniformly across tasks.
