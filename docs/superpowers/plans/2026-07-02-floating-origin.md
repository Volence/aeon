# Floating Origin (Continuous-Scroll Phase 4) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the ~16-section coordinate ceiling via an atomic floating-origin rebase — level size bounded by ROM only — plus the section_id byte→word widening.

**Architecture:** F1 (Tasks 2-5): base counters + parallax-aligned delta derivation with build asserts, the single-owner `Rebase_Execute` with the audited shift-list + DEBUG audit walk, trigger at the atomic frame point, `+World_Section_Base` at the seven lookup sites, signed-difference compares, force-rebase soak. F2 (Tasks 6-7): section_id word widening as one coherent format change. F3 (Task 8): 24×-wide fixture grid crossing the old `$8000` ceiling + acceptance. Task 9: docs + merge. Spec: `docs/superpowers/specs/2026-07-02-floating-origin-design.md` (APPROVED).

**Tech Stack:** 68000 assembly (AS), oracle emulator MCP. No generator changes except the F3 fixture descriptor (hand-written data, NOT the daemon-watched editor tree).

**Standing rules:** Step 1 of every task is research — line numbers below are anchors as of `e3e2446` and WILL drift (re-verify before editing). Build: `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh`. Runtime-boot in oracle after ANY ram.asm/structs.asm change (AS even-alignment lesson). `git add` exact paths; commit per green task. Branch `feat/floating-origin` off master; merge at Task 9. Verify during MOTION, not at rest.

---

### Task 1: Branch + baseline

- [ ] **Step 1: Research.** Read the spec end-to-end. Read `engine/level/camera.asm` (whole file), `engine/level/section.asm:57-121,290-320`, `engine/level/entity_window.asm:560-640,700-760,1460-1475`, `engine/level/parallax.asm:60-95`, `engine/level/tile_cache.asm:380-450,860-890`, `games/sonic4/objects/../rings.asm` (ring buffer producers/consumers), `ram.asm:260-400`, `structs.asm:60-100`, `constants.asm:305-345,395-445`.
- [ ] **Step 2: Branch + baseline.** `git checkout -b feat/floating-origin`. Build; oracle: full OJZ max-scroll circuit both axes; record `Lag_Frame_Count`, screenshots, and a `emulator_state_hash` at a fixed parked position (post-rebase determinism reference for Task 5).

### Task 2: Base counters, delta derivation, build asserts

**Files:**
- Modify: `constants.asm`, `ram.asm`, `games/sonic4/data/parallax/ojz_default.asm` (assert co-location), `engine/parallax_macros.inc` (if the assert macro lives with the factor encodings)

- [ ] **Step 1: Research.** Read `engine/parallax_macros.inc:31-43` (factor encodings — which shift(s) each `FACTOR_*` implies) and `games/sonic4/data/parallax/ojz_default.asm:30-46` (shipped bands: `FACTOR_1`, `FACTOR_1_16`, `FACTOR_1_8`, `FACTOR_1_2`, `FACTOR_5_8`; `vFactorBg=3`). Confirm `SECTION_SIZE=$0800`/`SECTION_SIZE_SHIFT=11` (`constants.asm:309-310`) and the act-descriptor 16-section assert (`games/sonic4/data/levels/ojz/act1/act_descriptor.asm:36-38` — Task 4 relaxes it).
- [ ] **Step 2: Constants + RAM.**

```asm
; constants.asm — floating origin (spec §3-4)
REBASE_THRESHOLD   = $6000              ; fine camera >= this -> down-shift
REBASE_DELTA_X     = $2000              ; OJZ: max(SECTION_SIZE, 512<<4) — slowest H band FACTOR_1_16
REBASE_DELTA_Y     = $1000              ; OJZ: max(SECTION_SIZE, 512<<3) — vFactorBg=3
; trigger sanity (spec §4): no chatter, no overshoot past the signed ceiling
        if (REBASE_THRESHOLD - REBASE_DELTA_X) <= REBASE_DELTA_X
          fatal "REBASE X triggers can chatter"
        endif
        if (REBASE_THRESHOLD - REBASE_DELTA_Y) <= REBASE_DELTA_Y
          fatal "REBASE Y triggers can chatter"
        endif
; ram.asm — upper block, even
World_Section_Base_X:   ds.w 1          ; sections renormalized past (X)
World_Section_Base_Y:   ds.w 1
```

  (Match the codebase's actual assert idiom — grep `fatal`/`error` usage in constants.asm and use the house form.)
- [ ] **Step 3: Parallax-alignment assert, co-located with the config.** Next to each act's parallax config, assert per band: `(REBASE_DELTA_X >> shift) & 511 == 0` for every shift the band's factor encodes (both shifts of a two-term factor like `FACTOR_5_8`), and `(REBASE_DELTA_Y >> vFactorBg) & 511 == 0`. Implement as a macro (e.g. `rebaseAssertBand factor`) in `engine/parallax_macros.inc` so future configs get it by adding one line per band; OJZ's config gets the lines now. Deliberately break one (temporarily set `REBASE_DELTA_X = $800`) to confirm the build FAILS with a clear message, then restore.
- [ ] **Step 4: Zero the counters at level init** (find where `Camera_X/Y` are seeded for level start — same site zeroes both bases).
- [ ] **Step 5: Build green + boot + commit.** `feat(level): floating-origin base counters + parallax-aligned rebase deltas w/ build asserts (F1)`

### Task 3: `Rebase_Execute` + DEBUG audit walk

**Files:**
- Create: `engine/level/rebase.asm`
- Modify: `games/sonic4/main.asm` (include), `ram.asm` (DEBUG counters)

- [ ] **Step 1: Research.** Re-verify every shift-list symbol from spec §5 exists under these exact names (audit anchors: `ram.asm:268-269,328-341,349-360,375-378,399`; `structs.asm:68-69`; `Object_RAM` layout `ram.asm:217-223`; `TileCache_InvalidateStaging` `tile_cache.asm:389`; `EntityWindow_BuildEntries` `entity_window.asm:604`). Confirm `Ring_Count` semantics (entries in use) and the ring entry layout x@+0,y@+2 (`rings.asm:146,154`).
- [ ] **Step 2: Write `Rebase_Execute`.** One routine, `d0.w = signed pixel delta for X` / `d1.w = signed pixel delta for Y` (one of them may be 0; caller passes ±`REBASE_DELTA_*`). Header comment carries the CONTRACT: *"every RAM field holding a live world coordinate MUST be shifted here; new fields register here or the DEBUG audit + soak will catch you."* Core shape (complete the marked loops in the obvious way for Y where only X is shown):

```asm
; Rebase_Execute — atomic floating-origin shift (spec §5). Interrupts NOT masked:
; runs between Camera_Update and Tile_Cache_Fill where no consumer is mid-flight,
; and VBlank only reads Plane_Buffer/SAT built from LAST frame's coords.
; In: d0.w = X pixel delta (signed, ±REBASE_DELTA_X or 0), d1.w = Y likewise
Rebase_Execute:
        ; 1) quiesce partial fills (nothing mid-flight to shift)
        moveq   #-1, d2
        move.w  d2, (Cache_Fill_Resume_Col).w
        move.w  d2, (Cache_Fill_Resume_Row).w
        move.w  d2, (Cache_Fill_RowResume_Row).w
        move.w  d2, (Cache_Fill_RowResume_Col).w
        ; 2) staged blocks are fine-sec-keyed -> stale
        bsr.w   TileCache_InvalidateStaging
        ; 3) camera (16.16: shift the pixel high word)
        sub.w   d0, (Camera_X).w
        sub.w   d1, (Camera_Y).w
        ; 4) every SST across all three slot arrays + player
        lea     (Object_RAM).w, a0
        move.w  #(Object_RAM_End-Object_RAM)/SST_len-1, d3
.obj:   tst.w   (a0)                    ; code_addr==0 -> slot free
        beq.s   .next
        sub.w   d0, SST_x_pos(a0)
        sub.w   d1, SST_y_pos(a0)
.next:  lea     SST_len(a0), a0
        dbf     d3, .obj
        ; 5) ring buffer: X AND Y per entry
        lea     (Ring_Buffer).w, a0
        moveq   #0, d3
        move.b  (Ring_Count).w, d3
        bra.s   .ring_check
.ring:  sub.w   d0, (a0)
        sub.w   d1, 2(a0)
        addq.w  #RING_BUFFER_ENTRY_SIZE, a0
.ring_check:
        dbf     d3, .ring               ; (adjust for count-vs-dbf off-by-one)
        ; 6) world tile cursors: delta/8
        move.w  d0, d2
        asr.w   #3, d2                  ; X tile delta
        sub.w   d2, (Cache_Left_Col).w
        sub.w   d2, (Cache_Head_Col).w
        sub.w   d2, (Section_Right_Col_Written).w
        sub.w   d2, (Section_Left_Col_Written).w
        move.w  d1, d2
        asr.w   #3, d2                  ; Y tile delta
        sub.w   d2, (Cache_Top_Row).w
        sub.w   d2, (Cache_Bottom_Row).w
        sub.w   d2, (Cache_Prev_Cam_Row).w
        sub.w   d2, (Section_Top_Row_Written).w
        sub.w   d2, (Section_Bottom_Row_Written).w
        ; 7) coarse Y baseline: reseed from rebased camera (masked, entity_window.asm:756 idiom)
        ; 8) parallax prev-section: force one clean re-select via the base-aware lookup
        st.b    (Parallax_Prev_Sec_X).w
        st.b    (Parallax_Prev_Sec_Y).w
        ; 9) base counters
        move.w  d0, d2
        asr.w   #SECTION_SIZE_SHIFT-?, d2  ; delta/SECTION_SIZE (see note)
        add.w   d2, (World_Section_Base_X).w
        move.w  d1, d2
        asr.w   #SECTION_SIZE_SHIFT-?, d2
        add.w   d2, (World_Section_Base_Y).w
        ; 10) derived state: rebuild, never hand-shift
        bsr.w   EntityWindow_BuildEntries
    ifdef __DEBUG__
        addq.w  #1, (Dbg_Rebase_Count).w
        bsr.w   Rebase_DebugAudit
    endif
        rts
```

  Notes to resolve while writing (research, don't guess): the exact 16.16 layout of `Camera_X` (subtract from the high word or the long); `asr.w #11` needs two shifts or a swap trick (asr max 8 — use `asr.w #8` + `asr.w #3`, delta is always positive-magnitude with sign applied by caller — pick one clean form); player slot inclusion (is `Player_1` inside the `Object_RAM` walk range or separate); sub-pixel words untouched by construction.
- [ ] **Step 3: `Rebase_DebugAudit`** (DEBUG only): walk the same fields; `RaiseError` if any live coordinate ≥ `REBASE_THRESHOLD` or < 0 (objects may be slightly out-of-window — bound check against `[−$1000, REBASE_THRESHOLD+$1000]` to allow despawn margins), any resume key ≠ `$FFFF` immediately post-rebase, or `Entity_Window_OriginX/Y` inconsistent with `Camera_X/Y` (recompute and compare).
- [ ] **Step 4: Build green (routine assembled, not yet called) + commit.** `feat(level): Rebase_Execute — single-owner atomic shift + DEBUG audit (F1)`

### Task 4: Trigger + the seven lookup sites + signed-difference compares

**Files:**
- Modify: the level game-state loop (`games/sonic4/ojz_scroll_test.asm:149-261` and/or the real level state — research which drives OJZ today), `engine/level/parallax.asm:61-95`, `engine/level/section.asm:290-320`, `engine/level/entity_window.asm:570-586,715-726,1463-1472`, `engine/level/tile_cache.asm:443-446,864-874`, `games/sonic4/data/levels/ojz/act1/act_descriptor.asm:29-38` (ceiling assert)

- [ ] **Step 1: Research.** Map the live frame order (audit: `InitSpriteSystem → RunObjects → Camera_Update → Tile_Cache_Fill → EntityWindow_Scan → Section_UpdateColumns → Touch/RingCollision → Render_Sprites → section diag → Parallax_CheckBoundary → Parallax_Update`). Identify every `asr` section-derive at the seven clusters and how each feeds `Section_GetSecPtrXY`/`Section_FlatIDXY`. Read the camera clamp: with the rebase, `Camera_Update`'s max-X/Y clamp must become base-aware (level extent in ABSOLUTE space: clamp fine camera against `grid_extent − base×SECTION_SIZE`); the act-descriptor's 16-section build assert is REPLACED by a "grid fits section_id width" assert (Task 6 widens that too).
- [ ] **Step 2: Trigger.** `Rebase_Check` called immediately after `Camera_Update`, before `Tile_Cache_Fill`:

```asm
Rebase_Check:
        move.w  (Camera_X).w, d0        ; fine pixel (16.16 high word)
        cmpi.w  #REBASE_THRESHOLD, d0
        blt.s   .x_low
        move.w  #REBASE_DELTA_X, d0     ; down-shift X
        bra.s   .x_go
.x_low: tst.w   (World_Section_Base_X).w
        beq.s   .x_none
        cmpi.w  #REBASE_DELTA_X, d0
        bge.s   .x_none
        move.w  #-REBASE_DELTA_X, d0    ; up-shift X (backward travel)
        bra.s   .x_go
.x_none:
        moveq   #0, d0
.x_go:  ; ...same for Y into d1...
        tst.w   d0
        bne.s   .do
        tst.w   d1
        bne.s   .do
        rts
.do:    bra.w   Rebase_Execute
```

- [ ] **Step 3: The seven `+World_Section_Base` sites.** At each cluster the fine `asr`-derived sec_x/sec_y gains `add.w (World_Section_Base_X).w` (resp. Y) before flat-id/grid-pointer use: parallax boundary (`parallax.asm:63-79`), Plane-B redraw (`section.asm:298-303`), entity window derive/init/slide (`entity_window.asm:570-586,715-726,1463-1472`), tile-cache dict lookups (both: `tile_cache.asm:443-446,864-874`), section diagnostic (`ojz_scroll_test.asm:188-195`). Helpers stay base-agnostic. Grep for any *other* `asr.w #SECTION` derive the audit's seven might have gained since (`grep -n "SECTION_SIZE_SHIFT" engine/ games/ -r`).
- [ ] **Step 4: Signed-difference compares.** At live-vs-live position compares in touch response / entity distance checks (grep `Camera_X`/player-x compares in `Object_Specific`-equivalents and `entity_window.asm` despawn checks): where the idiom is `move.w a; cmp.w b; b<cond>` on two world positions, convert to `sub.w` + sign-branch on the difference. Convert only clear live-vs-live sites; leave clamps (they're base-aware now) alone. Comment each converted site `; wrap-safe: signed difference`.
- [ ] **Step 5: Build + oracle.** Green; boot; full baseline circuit — with base 0 and thresholds unreachable on stock OJZ (3 sections), behavior must be pixel-identical to Task 1 baseline. Commit: `feat(level): rebase trigger at the atomic point + base-aware section lookups + wrap-safe compares (F1)`

### Task 5: Force-rebase soak (F1 acceptance)

**Files:**
- Modify: `constants.asm` (DEBUG soak values), `build.sh` (`REBASE_SOAK=1` flag)

- [ ] **Step 1: Research.** Confirm stock OJZ extent (3×1 sections = $1800 px) — soak thresholds must trigger inside it.
- [ ] **Step 2: Soak build.** Under `REBASE_SOAK=1`+DEBUG: `REBASE_THRESHOLD = 2*SECTION_SIZE` and deltas stay parallax-derived… **note $2000 > stock OJZ extent — so the X soak needs delta $1000 with the canopy band's assert RELAXED under soak only** (accept the documented 64px canopy jump in soak, or better: soak with a parallax config variant whose slowest band is FACTOR_1_2). Decide by trying; the soak's job is shift-list completeness, not parallax aesthetics — document the choice in the flag's comment.
- [ ] **Step 3: The soak.** Oracle, soak build: (a) scroll a full circuit right→left→right — `Dbg_Rebase_Count` climbs both directions; (b) **pixel-identity check**: park; note `emulator_state_hash`; scroll right until exactly one rebase fires; scroll back to the identical parked position; screenshot + compare against pre-rebase screenshot (identical), and player/object/ring positions in RAM differ from pre-rebase values by exactly `base×SECTION_SIZE` deltas; (c) collect rings, cross several rebases, return — collected rings STAY collected (respawn memory invariant); (d) audit walk clean throughout (no RaiseError); (e) diagonal + vertical variants (Y deltas fire).
- [ ] **Step 4: Commit.** `feat(level): force-rebase soak passes — shift-list complete (F1 accepted)`

### Task 6: F2 — section_id byte→word widening

**Files:**
- Modify: `constants.asm` (`SEC_VOID`, `RING_BUFFER_ENTRY_SIZE`), `structs.asm` (SST metadata block + `Entity_Scan_State`), `ram.asm` (`Ring_Buffer` sizing, `Entity_Window_Center_ID`, `Entity_Window_Anchor`), `engine/level/section.asm` (`Section_FlatIDXY` word return), `engine/level/entity_window.asm` (all `d0.b` id params → `d0.w`; `Collected_*`/`Killed_*`), `games/sonic4/.../rings.asm` (entry layout), object spawn/despawn sites reading `entity_section_id`

- [ ] **Step 1: Research.** Grep EVERY consumer: `grep -rn "entity_section_id\|SEC_VOID\|RING_BUFFER_ENTRY_SIZE\|Entity_Window_Center_ID\|Entity_Window_Anchor\|ess_section_id\|Section_FlatIDXY" engine/ games/ tools/`. Check whether any GENERATOR emits section ids into data (entity export format — if `tools/ojz_entity_gen.py` bakes byte ids into ROM lists, this task gains a daemon-coordination step: ASK THE USER first). Check the objdef/archetype spawn template block for baked metadata offsets.
- [ ] **Step 2: The format change, one pass:** `SEC_VOID = $FFFF`; ring entry `{x.w, y.w, section_id.w, list_index.b, pad.b}` (`RING_BUFFER_ENTRY_SIZE = 8`; resize `Ring_Buffer` RAM, re-verify RAM overflow guards); SST metadata relayout `{$2A slot_tag.b, $2B layer.b, $2C entity_section_id.w, $2E entity_list_index.b, $2F pad.b}` with `sst_custom` moving to `$30` (custom area 34→32 bytes — assert `PlayerV_len ≤ 32` still holds); `Entity_Scan_State.ess_section_id` word (+ struct re-pad even); `Entity_Window_Center_ID` word; `Entity_Window_Anchor` stays 2 bytes (sec_x0/sec_y0 grid coords, not flat ids — verify, don't assume); `Section_FlatIDXY` returns `d1.w`; every `d0.b`/`cmp.b` id site widened. The OEF_ANY_Y bit-7 mirror on `slot_tag` is unaffected (slot_tag stays a byte).
- [ ] **Step 3: Build + BOOT (mandatory — struct/RAM change) + verify.** Full circuit; ring collect/respawn matrix: collect rings in 3 sections, leave window, return — collected stay collected, uncollected respawn; object despawn/respawn across sections; SEC_VOID paths (grid edge) exercised at the level boundary. Commit: `feat(level): section_id widened to word — 256-section cap removed (F2)`

### Task 7: F2 regression — soak re-run

- [ ] **Step 1:** Re-run the entire Task 5 soak matrix on the widened build (the widening touched the exact fields the rebase shifts and the window rebuilds). All gates identical. Commit only if something needed fixing.

### Task 8: F3 — wide-grid fixture + acceptance

**Files:**
- Create: `games/sonic4/data/levels/ojz/act1_wide/act_descriptor.asm` (fixture — hand-written, NOT under the daemon-watched editor tree)
- Modify: `build.sh` (`WIDE_GRID=1` selects the fixture descriptor), `games/sonic4/main.asm` (conditional include)

- [ ] **Step 1: Research.** Read the Act descriptor + section grid format (`act_descriptor.asm` + `Section` struct docs) — confirm grid entries are section POINTERS (reusable) and what per-section fields are position-dependent (none should be — sections are position-independent by §4.9 design; verify `sec_objects`/`sec_rings` are section-local).
- [ ] **Step 2: Fixture.** `act1_wide`: grid 24×1 repeating OJZ's three section pointers cyclically; same art pool, same parallax config. Update the descriptor grid-extent assert to the new width (now gated by word section_id: 24 ≤ 65535 ✓). Build variant via `WIDE_GRID=1`.
- [ ] **Step 3: Acceptance matrix (normal thresholds — real rebases at $6000).** Oracle, WIDE_GRID build: (a) traverse all 24 sections right at max scroll — 5+ down-rebases fire; terrain/rings/objects correct in every repeated section; (b) traverse back — up-rebases mirror; (c) collect rings in sections 1, 12, 23 — memory correct across the whole run and after returning; (d) pixel-identity spot-checks straddling rebases (Task 5 method); (e) `Lag_Frame_Count` for the full run ≈ baseline per-section rate (the rebase event itself must not register); (f) audit walk clean; (g) cross the OLD ceiling: park at absolute x > $8000 (section 17+), verify collision, touch response, spawning, parallax all correct — the signed-op failure class is dead.
- [ ] **Step 4: Commit.** `feat(level): 24-wide fixture grid — >16-section traversal accepted (F3)`

### Task 9: Docs + merge

**Files:**
- Modify: `docs/ENGINE_ARCHITECTURE.md`, `docs/superpowers/specs/2026-06-22-continuous-scroll-traversal-design.md` (§9 pointer note), `docs/DEFERRED_WORK.md`, `docs/superpowers/2026-07-02-design-week-queue.md`

- [ ] **Step 1:** ARCH: write the floating-origin section as the design (coordinate model, delta rule, shift contract, lookup sites); mark continuous-scroll Phase 4 SHIPPED; update the §4.2/§4.9 mentions of the 16-section ceiling and byte section_id. Add a one-line banner to the old spec §9: "superseded by the 2026-07-02 spec (as-built)". DEFERRED_WORK: close the Phase-4 line; register follow-ups (e.g. `EDGE_WRAP_V` now unblocked — same machinery; Tails position-ring must join the shift-list when built — design #3 note).
- [ ] **Step 2: Final gates + merge.** Full DEBUG + plain builds green; baseline (non-soak, non-wide) circuit pixel-identical to Task 1; pytest green (if Task 6 touched generators); merge `feat/floating-origin` → master; update the queue-doc log.

---

## Self-review (done at write time)

- **Spec coverage:** §2→T2; §3→T2 (asserts) + T5 note; §4→T4 (trigger) + T2 (asserts); §5→T3+T4 placement; §6→T4 (sites + compares); §7→T6-7; §9 F1/F2/F3→T2-5/T6-7/T8; §10 risks→T3 contract header, T5 soak, T8(g).
- **Placeholders:** none — the two deliberately-open implementation choices (soak delta vs parallax variant in T5; `asr #11` form in T3) are flagged decisions with the deciding criterion stated, not TBDs.
- **Consistency:** `World_Section_Base_X/_Y`, `REBASE_DELTA_X/_Y`, `REBASE_THRESHOLD`, `Rebase_Execute`/`Rebase_Check`/`Rebase_DebugAudit`, `SEC_VOID=$FFFF`, `RING_BUFFER_ENTRY_SIZE=8` used uniformly across tasks.
