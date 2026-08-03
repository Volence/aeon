# BUG-005 Net + Sprites H1-H3 + Player/Camera Cluster Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land the BUG-005 chain-walk assert (DEBUG net for the one-frame sprite ghost), the three sprite render-path optimizations (H1 cached frame offset, H2 emit-loop stream order + size/link merge, H3 partial sprite-table DMA), and the player/camera cluster (sensors H3, G10 move_lock fix, A7 landing guard per ruling, G1 jump headroom carry, M3 bounds precompute, camera H2 + init clamp).

**Architecture:** One feature branch, ordered so the BUG-005 assert is live in DEBUG builds while the sprite path changes underneath it. All changes are 68k-side `.emp` (sigil dialect). Behavior-neutral perf items must keep the OJZ replay fixture green; behavior-changing items (G10, A7, camera init clamp) change state only in situations the fixture likely never enters — replay is run after each to confirm. One strict-suite pass + one provenance refreeze (chain-31) at the end.

**Tech Stack:** sigil `.emp` (Spec-2), build via `SIGIL_BUILD=... SIGIL_EMIT=... [DEBUG=1] ./build.sh`, oracle emulator (FOREGROUND ONLY — never from subagents), sigil-harness strict suite + refreeze.

---

## Rulings already made (Volence, 2026-08-02)

- **A7: GUARD IT** — on curled landing, if head clearance < standing rise, stay in ROLL instead of uncurling.
- **Wave-4 Z80 sound reclaim: OUT of this parcel** (separate follow-up).
- Sprites **H4** (dirty-skip vs B2 flicker fairness) is NOT in this parcel — B2 was signed; do not touch.

## Stale-review corrections (verified against master @ 8a1b71b — do NOT re-plan these)

- Camera **H1 already shipped** (`d35b531`): `Camera_X_Max`/`Camera_Y_Max` exist at `engine/ram.emp:326-327`, precomputed in `Camera_Init`. Only H2 (RAM round-trip) remains.
- **PB1** (Sprites_Rendered init clear), **PB2** (band-index bias), **PB3** (sprSize swap), **G9** (d7 width) — all fixed.
- SST has **zero free engine bytes** at $26-$2D (entity-window fields). H1 requires growing `Sst` from `$50` to `$52`.
- H3's DMA length register counts **words**: patch value is `Sprites_Rendered * 4`, via `movep.w` (length bytes interleave at entry offsets +1/+3).
- M3's word-truncation trap is already comment-guarded + `ensure`d; M3 is now pure perf.

## Global constraints

- **No emulator MCP from subagents** — all oracle work is done by the controller, foreground.
- Build (from `/home/volence/sonic_hacks/aeon`):
  ```bash
  SIGIL_BUILD=/home/volence/sonic_hacks/sigil/target/release/sigil \
  SIGIL_EMIT=/home/volence/sonic_hacks/sigil/target/release/emit_sound_blob \
  DEBUG=1 ./build.sh
  ```
  Artifacts: `s4.debug.bin` + `s4.debug.lst` (plain build → `s4.bin`/`s4.lst`). Game arg is POSITIONAL (`./build.sh demo`), never `GAME=demo`.
- **Stale-artifact trap:** delete the target ROM before building, assert fresh mtime after. Rebuild sigil binaries after any sigil-side merge.
- `git add` exact paths only. Commit per task. Feature branch: `parcel/bug005-sprites-player` off master.
- Replay-fixture regression (FOREGROUND, controller only): persistent bp `GameState_OJZScroll_Init` BEFORE `reload_rom` → break at `Logic_Tick`=1 → poke `Input_Source`=1, `Replay_Ptr`=`Replay_OJZ_Fixture`+20 → clear bps → resume → ~75 s → `Replay_Done`=$FF, no REPLAY DESYNC = PASS. Addresses from the fresh `.lst` (oracle symbols go stale after reload).
- The auto-commit daemon may plain-rebuild mid-session — byte-verify ROM vs `.lst` before debugging.
- `.emp` dialect: `jbsr`/`jbra` + bare conditional branches (no `.s`/`.w` — that is the AS-era rule); `assert.<size> <reg>, <cond>, <comparand>` self-gates on DEBUG but wrap `if DEBUG == 1 { }` when setup loads need gating; assert src must be a REGISTER; `pad(1)` after odd `u8` runs in RAM blocks.

---

### Task 1: Branch + baseline

**Files:** none (git only)

- [ ] **Step 1:** `git checkout master && git pull && git checkout -b parcel/bug005-sprites-player`
- [ ] **Step 2:** Baseline build all four canonical shapes; record CRCs:
  ```bash
  rm -f s4.bin s4.debug.bin demo.bin demo.debug.bin
  SIGIL_BUILD=... SIGIL_EMIT=... ./build.sh
  SIGIL_BUILD=... SIGIL_EMIT=... DEBUG=1 ./build.sh
  SIGIL_BUILD=... ./build.sh demo
  SIGIL_BUILD=... DEBUG=1 ./build.sh demo
  crc32 s4.bin s4.debug.bin demo.bin demo.debug.bin
  ```
  Expected: all four build clean; CRCs match the chain-30 goldens in `sigil/crates/sigil-harness/golden/provenance.toml` (tip `i4-terminus-flush`). STOP if they don't — the tree is already dirty.

### Task 2: BUG-005 chain-walk assert (DEBUG net)

**Files:**
- Modify: `engine/objects/sprites.emp` (`.done`, ~:431-438)
- Modify: `docs/BUGS.md` (BUG-005 entry: note the net is live)

The finished SAT link chain must have exactly `Sprites_Rendered` links before the terminator. Walk it at `.done` (both exit paths converge here, incl. `.band_limit_pop`; all registers free; d5 = final count, a4 = one-past-last).

- [ ] **Step 1:** Insert after the terminator fix-up `move.b #0, -5(a4)` and before `move.w d5, Sprites_Rendered`:

```
        // BUG-005 net: walk the finished link chain from entry 0; the link-path
        // length must equal the emitted count. Traps in-frame with the builder's
        // registers live (d5 = count, a4 = write ptr). Bounded at MAX_VDP_SPRITES
        // so a cyclic chain traps on the mismatch instead of hanging.
        if DEBUG == 1 {
        lea     Sprite_Table_Buffer, a0
        moveq   #0, d0                  // d0 = current entry index
        moveq   #0, d1                  // d1 = links walked
        move.w  #MAX_VDP_SPRITES-1, d2  // loop bound
    .chain_walk:
        addq.w  #1, d1
        move.w  d0, d3
        lsl.w   #3, d3                  // entry * 8
        moveq   #0, d0
        move.b  3(a0,d3.w), d0          // link byte -> next index
        dbeq    d2, .chain_walk         // stop on link 0 (terminator)
        assert.w d1, eq, d5             // link-path length == Sprites_Rendered
        }
```

  Note: `dbeq` exits when the just-loaded link is 0 (Z set by `move.b`) — verify the Z-flag timing against the `move` before `dbcc` (move sets Z; dbeq checks it). The `.empty_table` path needs no walk (Sprites_Rendered = 0 and entry 0 is the hidden terminator).
- [ ] **Step 2:** Build DEBUG + plain (both games). Expected: DEBUG ROMs change bytes; **plain ROMs byte-identical to baseline** (the net is DEBUG-only). Verify plain CRCs unchanged.
- [ ] **Step 3 (controller, FOREGROUND):** Load `s4.debug.bin` in oracle (one instance; relaunch must rebuild oracle from its `main` first — the running binary's worktree is deleted). Run the OJZ state, spindash-stress ~2 minutes with ring emission + transitions. Expected: no assert trap (the net arms; a trap here is a BUG-005 CATCH — if it fires, freeze, dump registers + `Sprite_Table_Buffer`, and STOP the parcel to file findings).
- [ ] **Step 4:** Update `docs/BUGS.md` BUG-005: status → OPEN-INSTRUMENTED, describe the live net.
- [ ] **Step 5:** Commit: `git add engine/objects/sprites.emp docs/BUGS.md && git commit -m "sprites: BUG-005 chain-walk assert at Render_Sprites.done (DEBUG net, plain-ROM byte-identical)"`

### Task 3: Sprites H1 — cached frame-data offset in the SST

**Files:**
- Modify: `engine/objects/sst.emp` (grow `Sst` $50 → $52, new field)
- Modify: `engine/objects/frames.emp` (extend `refresh_piece_count` template)
- Modify: `engine/objects/load_object.emp` (seed at spawn, ~:76-81)
- Modify: `engine/objects/children.emp` (`PopulateSpawnedPieceCount` seeds child too)
- Modify: `engine/objects/sprites.emp` (consume in Draw_Sprite ~:79-84 and Render_Sprites ~:275-280; sibling walk UNCHANGED)
- Modify: `games/sonic4/objects/test_solid.emp:16`, `games/sonic4/objects/test_helpers.emp:28`, `games/sonic4/objects/test_player.emp:90,:99`, `games/sonic4/player/player_common.emp` (DebugEnter :764-765 / DebugExit :778) — refresh coverage
- Modify: `engine/ram.emp` / wherever `Object_RAM` sizing derives (follows `sizeof(Sst)` automatically — verify region assert passes)

- [ ] **Step 1:** In `sst.emp`: add `frame_off: u16 @ $50` (comment: "cached word offset from mappings base to current frame data — MUST be refreshed on every mapping_frame/mappings write; sibling walk does NOT use it (child frame is a function of the PARENT's mapping_frame)"). Change `(size: $50)` → `(size: $52)`. Update the `ensure(sizeof(...))` pins at sst.emp:124-138.
- [ ] **Step 2:** Build. Expected: either clean, or a RAM-region overflow error from Object_RAM growth. If overflow: STOP and report — do not shrink anything unilaterally.
- [ ] **Step 3:** In `frames.emp` `refresh_piece_count(sst, ptr, scratch)`: after resolving the frame-data offset (the template already computes it en route to the piece count), store it: `move.w {scratch}, Sst.frame_off({sst})` at the point where `{scratch}` holds the resolved word offset (before it's turned into the piece-count load). Null-mappings path must write 0 to `frame_off` too. Both splices (`RefreshSpritePieceCount`, `PopulateSpawnedPieceCount`) inherit this.
- [ ] **Step 4:** In `load_object.emp` frame-0 cache (~:76-81): seed `frame_off` from the table's entry 0 word alongside the existing `frame_piece_count` cache.
- [ ] **Step 5:** Add `jbsr RefreshSpritePieceCount` (contract: `a0: *Sst`, clobbers d2/a1 — verify locals at each site) after every non-refreshing `mapping_frame` write: `test_solid.emp:16`, `test_helpers.emp:28` (inside `test_obj_prolog`), `test_player.emp:90` and `:99`, `player_common.emp` DebugEnter (:764-765 — replaces the manual `sprite_piece_count=1`) and DebugExit (:778).
- [ ] **Step 6:** Consume the cache. Draw_Sprite (~:79-84), replace the 5-instruction resolve with:
```
        adda.w  Sst.frame_off(a0), a1   // a1 = frame data (bbox at +0) — H1 cache
```
  Render_Sprites main loop (~:275-280), replace the resolve with:
```
        if DEBUG == 1 {
        moveq   #0, d0                  // H1 staleness net: live-resolve and
        move.b  Sst.mapping_frame(a0), d0   // compare against the cache
        add.w   d0, d0
        move.w  (a3,d0.w), d0
        move.w  Sst.frame_off(a0), d1
        assert.w d1, eq, d0
        }
        adda.w  Sst.frame_off(a0), a3   // a3 = frame data — H1 cache
        move.w  FRAME_PIECE_COUNT(a3), d4
        beq   .next_object
        lea     FRAME_PIECES(a3), a3
```
  (Verify d0/d1 are dead at that point in the loop — d6 holds art_tile, d5 the count; adjust scratch choice if not.) **Sibling walk (~:361-372) stays on the live resolve** — add a comment stating why (semantic C: child mappings × PARENT frame; the cache would go stale when the parent animates).
- [ ] **Step 7:** Build DEBUG + plain, both games. Expected: clean; region asserts pass.
- [ ] **Step 8 (controller, FOREGROUND):** Replay fixture run (runbook above). Expected: `Replay_Done`=$FF, 21/21, no desync, and no H1 staleness assert. Then a short live OJZ run with the test objects on screen (test_solid/test_player paths exercise the refresh-coverage fixes).
- [ ] **Step 9:** Commit exact paths, message: `"sprites H1: cached frame-data offset in SST ($50->$52), total refresh coverage, DEBUG staleness net; sibling walk stays live-resolve (parent-frame semantic)"`

### Task 4: Sprites H2 — emit loop stream order + size/link word merge

**Files:**
- Modify: `engine/objects/sprites.emp` (`emit_piece_loop` :594-611, term fns :489-585)

Mapping piece format is already SAT order (`+0 Y w, +2 size b, +3 pad b, +4 tile w, +6 X w`; pad = link position). Restructure so each term does its own `(a3)+` reads — no more parking tile in a6 / X in a1. Per the review: the merge applies to unflipped and xflip; **yflip keeps byte-wise size handling** (it must mangle the size for the Y computation).

- [ ] **Step 1:** New skeleton:
```
comptime fn emit_piece_loop(xflip: int, yflip: int) -> Code {
    return asm {
        subq.w  #1, d4
    .piece_loop:
        {y_term(yflip)}
        {size_link(yflip)}
        {tile_term(xflip, yflip)}
        {x_term(xflip)}
        cmpi.b  #MAX_VDP_SPRITES, d5
        dbeq    d4, .piece_loop
        rts
    }
}
```
- [ ] **Step 2:** Terms (stream-order bodies):
```
// y_term(0):
        move.w  (a3)+, d0
        add.w   d3, d0
        move.w  d0, (a4)+
// y_term(1) — yflip needs height before the write; size byte is at (a3) now:
        move.w  (a3)+, d0
        neg.w   d0
        moveq   #0, d1
        move.b  (a3), d1                // size code (a3 not advanced)
        andi.w  #3, d1
        addq.w  #1, d1
        lsl.w   #3, d1
        sub.w   d1, d0
        add.w   d3, d0
        move.w  d0, (a4)+
// size_link(0) — merged word (pad byte is the link position):
        move.w  (a3)+, d1               // size<<8 | pad
        addq.b  #1, d5
        move.b  d5, d1                  // pad -> link
        move.w  d1, (a4)+
// size_link(1) — yflip keeps byte form:
        move.b  (a3)+, (a4)+            // size
        addq.w  #1, a3                  // skip pad
        addq.b  #1, d5
        move.b  d5, (a4)+               // link
// tile_term(xflip, yflip) — direct read, a6 parking gone:
        move.w  (a3)+, d0
        [eori.w #$0800/$1000/$1800, d0]  // per flip combo, as today
        add.w   d6, d0
        move.w  d0, (a4)+
// x_term(0):
        move.w  (a3)+, d0
        add.w   d2, d0
        bne     .x_ok
        moveq   #1, d0
    .x_ok:
        move.w  d0, (a4)+
// x_term(1) — xflip; a3 is at +8 here so the size byte is still -6(a3):
        move.w  (a3)+, d0
        neg.w   d0
        moveq   #0, d1
        move.b  -6(a3), d1
        move.b  (a0,d1.w), d1           // CellOffsets_XFlip width
        sub.w   d1, d0
        add.w   d2, d0
        bne     .x_ok
        moveq   #1, d0
    .x_ok:
        move.w  d0, (a4)+
```
- [ ] **Step 3:** Update `Emit_ObjectPieces`' header contract: a1/a6 no longer touched by the loop bodies — narrow `clobbers` accordingly (verify the dispatcher :636-643 still uses a0 for the flip table; keep it). The old header said a1/a6 clobbered; callers already assume clobbered, so narrowing is safe.
- [ ] **Step 4:** Build DEBUG + plain. Expected: clean.
- [ ] **Step 5 (controller, FOREGROUND):** SAT byte-equivalence check in oracle: load DEBUG build, run the OJZ replay fixture; at 3-4 paused points mid-run, dump `Sprite_Table_Buffer` (640 B) and compare against the same ticks on the pre-H2 build (the fixture makes the ticks reproducible). Expected: byte-identical SAT at every sampled tick, all flip variants exercised (Sonic xflips when running left; verify at least one xflip sample). Replay completes 21/21. The Task-2 chain-walk assert is the standing net.
- [ ] **Step 6:** Commit: `"sprites H2: emit loop stream-order restructure + size/link word merge (unflipped/xflip); a1/a6 freed; SAT byte-identical vs pre-H2 at replay-fixed ticks"`

### Task 5: Sprites H3 — partial sprite-table DMA

**Files:**
- Modify: `engine/objects/sprites.emp` (`.done` + `.empty_table`)

`Static_Sprite_DMA` is RAM (`engine/ram.emp:229`); length bytes at entry offsets +1/+3 (movep-interleaved with $94/$93 markers); `queue_static_dma` copies the whole 14-byte entry at IRQ6-enqueue time, so a main-loop patch is race-free. Length register counts **words** → patch `d5 * 4`.

- [ ] **Step 1:** At `.done`, after the chain-walk block, before `rts`:
```
        // H3: ship only the live entries — the link chain terminates at the last
        // written entry, so a partial SAT DMA is safe. Length reg is in WORDS.
        move.w  d5, d0
        lsl.w   #2, d0                  // entries * 8 bytes = entries * 4 words
        lea     Static_Sprite_DMA, a0
        movep.w d0, DMAEntry.SizeH(a0)
```
- [ ] **Step 2:** At `.empty_table` (the had-sprites→none transition writes the 8-byte hidden terminator): patch length to 4 words:
```
        move.w  #4, d0                  // one 8-byte hidden terminator entry
        lea     Static_Sprite_DMA, a0
        movep.w d0, DMAEntry.SizeH(a0)
```
- [ ] **Step 3:** Build DEBUG + plain. Expected: clean.
- [ ] **Step 4 (controller, FOREGROUND):** In oracle: (a) replay fixture green; (b) VRAM check — pre-fill VRAM `$B800..$B880` beyond the live count with a sentinel via `emulator_write_vram`, run one frame, confirm only `Sprites_Rendered*8` bytes were overwritten (sentinel survives past the live region — proves the partial length took); (c) trigger a had-sprites→none transition if reachable (debug scene freeze / state with no objects) and confirm no ghost persists. The BUG-005 forensics note applies: stale VRAM entries past the terminator are now *expected* to persist — they are unreferenced by the chain.
- [ ] **Step 5:** Commit: `"sprites H3: sprite-table DMA length patched to live count (words, movep) — up to ~480 B Critical VBlank budget back; empty-transition ships the 8-byte terminator"`

### Task 6: Camera H2 (register single-pass) + Camera_Init seed clamp

**Files:**
- Modify: `engine/level/camera.emp` (clamp macro ~:92-109, `.apply_x`/`.x_done` ~:242-251, `.apply_y`/`.clamp_y` ~:336-345, `Camera_Init` ~:117-169)

Constraints: `.x_done`/`.clamp_y` stay valid entry points for freeze/hold paths that arrive WITHOUT the apply having run; d4 is the reserved freeze flag (macro must stay d0/d1-only); **the fraction-zeroing store shape (`swap; clr.w; move.l`) is load-bearing behavior — preserve it exactly** (the replay fixture will catch any deviation, correctly).

- [ ] **Step 1:** Split the macro:
```
comptime fn clamp_camera_axis_reg(cam: Label, max_cell: Label) -> Code {
    return asm {
        swap    d0
        tst.w   d0
        bge     .min_ok
        moveq   #0, d0
    .min_ok:
        move.w  {max_cell}, d1
        cmp.w   d1, d0
        ble     .clamp
        move.w  d1, d0
    .clamp:
        swap    d0
        clr.w   d0                      // fraction discarded every frame — load-bearing
        move.l  d0, {cam}
    }
}
comptime fn clamp_camera_axis(cam: Label, max_cell: Label) -> Code {
    return asm {
        move.l  {cam}, d0
        clamp_camera_axis_reg(cam, max_cell)
    }
}
```
  (If the dialect rejects a template splice inside `asm`, duplicate the body — verify by building.)
- [ ] **Step 2:** X axis single-pass: `.apply_x` becomes load → add in d0 → `jbra .x_clamp`; `.x_done:` (the freeze/hold/deadzone entry) becomes `move.l Camera_X, d0` falling into `.x_clamp:` which splices `clamp_camera_axis_reg(Camera_X, Camera_X_Max)`. Same restructure for Y with `.clamp_y` keeping its label and trailing `rts` (external entries: the freeze path, `.land_lock`'s `jbra`, `.down_ok`'s `ble`).
- [ ] **Step 3:** `Camera_Init`: after the `Camera_X_Max`/`Y_Max` computes, splice `clamp_camera_axis(Camera_X, Camera_X_Max)` and `clamp_camera_axis(Camera_Y, Camera_Y_Max)`; widen the contract to `clobbers(d0-d1)` (sole caller is the OJZ init ladder — sigil's contract check verifies).
- [ ] **Step 4:** Build DEBUG + plain. Expected: clean; contract checker passes.
- [ ] **Step 5 (controller, FOREGROUND):** Replay fixture — MUST be green (the fixture hashes `Camera_X/Y` every checkpoint; this is the strongest possible A/B for H2's behavior-neutrality). The init clamp changes state only for edge-adjacent starts; the OJZ start is interior, so the fixture stays green — if it desyncs at tick 0-64, the init clamp regressed the seed: STOP.
- [ ] **Step 6:** Commit: `"camera H2: single-pass in-register apply->clamp per axis (fraction-zeroing store preserved; freeze/hold entries intact) + Camera_Init now clamps its seed (closes the edge-start negative-camera init glitch)"`

### Task 7: Sensors H3 — Player_AtLedgeEdge direct probe

**Files:**
- Modify: `games/sonic4/player/player_sensors.emp` (`.single` :534-545)

- [ ] **Step 1:** Replace the B=A pair call:
```
.single:
        // Single-point balance probe: call the core directly — the pair wrapper
        // would run the identical probe twice and compare it with itself.
        jbsr    Collision_ProbeDown     // d0/d1 point, d3 layer, d6 SOLID_TOP already set
        cmpi.w  #LEDGE_NO_GROUND, d0
        bgt     .at_edge
        moveq   #0, d0
        rts
.at_edge:
        moveq   #1, d0
        rts
```
  (d0/d1/d3/d6 are exactly Collision_ProbeDown's inputs, already loaded at :519-520; the d4/d5 copies and `lea …,a2` die. Contract: clobbers d3-d5/a1, preserves a0 — matches AtLedgeEdge's declared clobbers; verify the header still covers d6.)
- [ ] **Step 2:** Build; replay fixture (controller). Expected: green — same probe, same result, half the cost (~500-1,000 cycles/idle frame back).
- [ ] **Step 3:** Commit: `"sensors H3: AtLedgeEdge single-point path calls Collision_ProbeDown directly (was: identical probe twice via the pair wrapper)"`

### Task 8: G10 — move_lock ticks on the on-object grounded exit

**Files:**
- Modify: `games/sonic4/player/player_ground.emp` (Ground_PostMove on-object exit ~:186-190; spindash trigger comment ~:72-79)

**Do NOT hoist to Player_Main** — that would tick the lock on airborne frames and break the documented "frozen while airborne" rule (:250-252). The behavior-minimal, fixture-safe shape is the on-object exit.

- [ ] **Step 1:**
```
        btst    #ST_ON_OBJECT, status(a0)
        beq   .terrain
        clr.b   angle(a0)
        // G10: Player_SlopeRepel (the sole lock decrementer) is bypassed on this
        // exit — without a tick here, a slip-locked player landing on a solid
        // object keeps frozen input forever (only jump escapes).
        move.w  PlayerV.move_lock(a0), d0
        beq   .lock_done
        subq.w  #1, d0
        move.w  d0, PlayerV.move_lock(a0)
.lock_done:
        rts
```
- [ ] **Step 2:** Per the review's S4 note, comment the spindash trigger (~:72-79): `// NOTE: deliberately not move_lock-gated — the trigger needs a down-hold + jump press; lock freezes directional response, not this (review S4, self-resolving).`
- [ ] **Step 3:** Build; replay fixture (controller). Expected green (state changes only when move_lock≠0 while on-object — needs a slip immediately before mounting a solid; if it DOES desync, the fixture found a real recorded instance: inspect the tick, confirm the new behavior is the intended fix, and re-record the fixture per the I4 runbook as a separate follow-up commit).
- [ ] **Step 4 (controller, FOREGROUND):** Manual repro of the fixed bug: in OJZ, force a slip (`move_lock` set) then land on a `ObjDef_Solid` (sections 0-2 have them); confirm input unfreezes after 30 frames instead of never.
- [ ] **Step 5:** Commit: `"player G10: move_lock ticks on the on-object grounded exit (slip-locked landing on a solid no longer freezes input forever)"`

### Task 9: A7 — landing uncurl clearance guard (ruled: guard it)

**Files:**
- Modify: `games/sonic4/player/player_air.emp` (`Air_LandState` :424-438)

Model: PState_Roll's unroll guard (`player_ground.emp:459-461`) — same threshold `(PLAYER_Y_RADIUS-BALL_Y_RADIUS)+CURL_Y_SHIFT` (= 10 px). At Air_LandState time the player is already floor-snapped with `Player_Quadrant`=0 forced, so `Player_SensorCeiling` probes the ball box upward at the landed position — identical geometry to the unroll guard.

- [ ] **Step 1:** Verify with a grep/read that curled air states (JUMP/ROLLJUMP/AIRBALL) hold `ST_ROLLING` in `status` at landing time (the classic invariant). If not, key the guard on the incoming player_state instead — report which.
- [ ] **Step 2:** Rework `Air_LandState`:
```
proc Air_LandState (a0: *Sst) clobbers(d0-d7/a1-a2) out(d0) {
        move.b  Ctrl_1_Held, d1
        btst    #BUTTON_DOWN_BIT, d1
        beq     .check_headroom
        andi.b  #BUTTON_LEFT|BUTTON_RIGHT, d1
        bne     .check_headroom
        move.w  PlayerV.ground_speed(a0), d1
        abs_w(d1)
        cmpi.w  #PHYS_ROLL_START_MIN, d1
        blt     .check_headroom
        moveq   #PSTATE_ROLL, d0                // player chose to keep rolling
        rts
.check_headroom:
        // A7 guard (ruling 2026-08-02): a curled landing may only uncurl if the
        // standing head rise fits — same hazard class as PState_Roll's unroll
        // guard. Blocked -> stay in ROLL (KEEP_ROLL logic owns the low-speed case).
        btst    #ST_ROLLING, status(a0)
        beq     .stand                          // landed uncurled: nothing to guard
        jbsr    Player_SensorCeiling            // d0 = head clearance (ball box)
        cmpi.w  #(PLAYER_Y_RADIUS-BALL_Y_RADIUS)+CURL_Y_SHIFT, d0
        blt     .stay_rolling
.stand:
        moveq   #PSTATE_GROUND, d0
        rts
.stay_rolling:
        moveq   #PSTATE_ROLL, d0
        rts
}
```
  Contract widens from `clobbers(d1)` to `clobbers(d0-d7/a1-a2)` (SensorCeiling's set) — all three callers `jbsr` then immediately `jbra Player_SetState`, relying on nothing but a0/d0; sigil's checker confirms. Curled→ROLL via PHook_EnsureBall is an idempotent no-op. A blocked landing at |gsp| < $80 gets PState_Roll's KEEP_ROLL kick next frame — that IS the intended blocked-unroll behavior.
- [ ] **Step 3:** Build; replay fixture (controller). Expected green: every fixture jump landing is curled so the probe RUNS, but open terrain returns the ≥16 sentinel and the outcome is unchanged. A desync = the fixture lands curled under something low — inspect before touching anything.
- [ ] **Step 4 (controller, FOREGROUND):** Manual verify: roll/jump into a low-clearance spot in OJZ (or temporarily poke a solid tile above a landing point), land curled, confirm the player STAYS rolling instead of clipping; confirm normal landings still uncurl.
- [ ] **Step 5:** Commit: `"player A7 (ruled): curled landing keeps ROLL when standing headroom < 10px — mirrors the unroll guard; open landings unchanged"`

### Task 10: G1 — jump-press headroom carried into the air body

**Files:**
- Modify: `games/sonic4/player/player_common.emp` (PlayerV overlay ~:75-85 — new field; fix the stale "12 of 34" comment at :65)
- Modify: `games/sonic4/player/player_ground.emp` (both jump checks :101-107 and :352-356; Player_Jump entry)
- Modify: `games/sonic4/player/player_air.emp` (class heads ~:206-271)
- Modify: `games/sonic4/config/constants.emp` or the phys constants home — `PHYS_JUMP_SKIP_CLEARANCE`

Scope discipline: **sentinel-only skip.** The air re-probe runs after ObjectMove (player already rose up to ~7 px), so only a carried clearance that still covers the rise is safely skippable; the probe's snap/reattach side effects only fire when dist < 0, which a sufficient carried clearance precludes — behavior-identical. Replay-hash discipline: the carry byte is set and consumed **within the same tick** (Player_Jump tail-runs the air body), so checkpoints never see it nonzero.

- [ ] **Step 1:** Add to the PlayerV overlay: `jump_headroom: u8` (+ keep the overlay even — pair with an existing/added pad byte per the ram conventions). Comment: "press-frame ceiling clearance carried into the same tick's air body; MUST be zero at tick end (replay-hash discipline)." Fix the ":65 — 12 of 34" comment to the real count.
- [ ] **Step 2:** Define `PHYS_JUMP_SKIP_CLEARANCE = 8` next to the phys constants with:
```
// Max first-frame rise = jump_force >> 8 (Sonic: $680 -> 6.5px) + 1 margin.
ensure(PHYS_JUMP_SKIP_CLEARANCE * 256 > PHYS_JUMP_FORCE, "skip clearance must cover the first-frame rise")
```
  (Locate the actual jump-force constant name; if it only exists as per-character table data, derive the ensure from the table's Sonic entry or fall back to the comment + literal 8 — report which.)
- [ ] **Step 3:** At BOTH jump checks (ground :101-107, roll twin :352-356), d0 = clearance survives the `cmpi`/`bge` — store it at Player_Jump's entry (verify Player_Jump has no other callers; if it does, store at the two check sites before the branch instead):
```
        move.b  d0, PlayerV.jump_headroom(a0)   // G1: carry press-frame clearance
```
  (Clearance at this point is 0..32 — fits a byte; it is ≥ PHYS_JUMP_HEADROOM or we wouldn't be jumping.)
- [ ] **Step 4:** In `PState_AirShared`: `.mostly_up` — after the two wall probes, before `Player_SensorCeiling`:
```
        move.b  PlayerV.jump_headroom(a0), d0
        clr.b   PlayerV.jump_headroom(a0)       // consume — never survives the tick
        cmpi.b  #PHYS_JUMP_SKIP_CLEARANCE, d0
        bge     .up_done                        // carried clearance covers the rise:
                                                // probe would return dist >= 1 -> no-op
        jbsr    Player_SensorCeiling
        ...existing...
```
  The other three class heads (`.mostly_down`/left/right) get a bare `clr.b PlayerV.jump_headroom(a0)` so a sideways-dominant jump can't latch the byte. Verify both `PState_Jump` and `PState_RollJump` route through `PState_AirShared` (Player_Jump exits to both, :817-819).
- [ ] **Step 5:** Build; replay fixture (controller). Expected green: skipped probes only occur where the probe was a guaranteed no-op, and the byte is always 0 at checkpoint ticks. A desync here means the skip condition is wrong — STOP and re-derive.
- [ ] **Step 6 (controller, FOREGROUND):** Manual edge test: jump under a 6-7 px ceiling (clearance < 8 → carry doesn't qualify → re-probe runs → head bump still works); jump in the open (probe skipped; ~900-1,600 cycles back per press).
- [ ] **Step 7:** Commit: `"player G1: press-frame ceiling clearance carried into the same-tick air body; mostly-up re-probe skipped only in the guaranteed-no-op case (sentinel discipline, replay-hash clean)"`

### Task 11: M3 — Player_LevelBound act extents precomputed at init

**Files:**
- Modify: `games/sonic4/config/ram.emp` (two new words)
- Modify: `games/sonic4/player/player_common.emp` (new `Player_BoundsInit`; `Player_LevelBound` :684-749 consumes)
- Modify: `games/sonic4/test/ojz_scroll_test.emp` (call after `Section_Init`, ~:143-144)

Venue ruling: game-side (the engine never writes game RAM — keep the wall clean).

- [ ] **Step 1:** In `games/sonic4/config/ram.emp`, near `Player_Death_Pending`:
```
        Player_Bound_Right: u16,        // act right clamp edge (px) - PBOUND_RIGHT_MARGIN
        Player_Bound_Bottom: u16,       // act bottom edge (px) - SCREEN_HEIGHT
```
  (Word fields — keep the block even-aligned; hash-invisible to the replay fixture, it lives outside Player_1's SST.)
- [ ] **Step 2:** New proc in `player_common.emp` (next to Player_LevelBound):
```
// --- Compute the act-invariant player clamp edges. Call once per act init,
//     after Current_Act_Ptr is live. The MEGA-ACT word-wrap trap (grid_w > 31)
//     now lives HERE only, still guarded by act_descriptor's <= $8000 ensure.
pub proc Player_BoundsInit (a0: *Act) clobbers(d1) {
        moveq   #0, d1
        move.w  Act.grid_w(a0), d1
        lsl.l   #8, d1
        lsl.l   #3, d1                  // grid_w << SECTION_SIZE_SHIFT (split shift)
        subi.w  #PBOUND_RIGHT_MARGIN, d1
        move.w  d1, Player_Bound_Right
        moveq   #0, d1
        move.w  Act.grid_h(a0), d1
        lsl.l   #8, d1
        lsl.l   #3, d1
        subi.w  #SCREEN_HEIGHT, d1
        move.w  d1, Player_Bound_Bottom
        rts
}
```
- [ ] **Step 3:** In `ojz_scroll_test.emp` after `Section_Init` (:143-144): `lea OJZ_Act1_Descriptor, a0` (reload — Section_Init clobbers a0) + `jbsr Player_BoundsInit`.
- [ ] **Step 4:** In `Player_LevelBound`, replace both per-frame derivation chains (:693-700, :712-717) with `move.w Player_Bound_Right, d1` / `move.w Player_Bound_Bottom, d1`; move the MEGA-ACT comments to point at Player_BoundsInit; the edge_mode dispatch and X-writeback stay untouched.
- [ ] **Step 5:** Build; replay fixture (controller). Expected green (identical clamp values, cheaper derivation).
- [ ] **Step 6:** Commit: `"player M3: act clamp edges precomputed at init (game-side Player_BoundsInit) — ~180-200 cyc/frame back; per-frame word-wrap derivation deleted"`

### Task 12: Gate — strict suite, refreeze chain-31, docs, merge

- [ ] **Step 1:** Full soak (controller, FOREGROUND): DEBUG build, ~5 minutes live OJZ play — spindash bursts, jumps under terrain, riding solids, transitions with ring emission. Expected: zero asserts (chain-walk + H1 staleness both armed). Then one final replay-fixture run: 21/21.
- [ ] **Step 2:** Strict suite own-run (from `/home/volence/sonic_hacks/sigil`):
```bash
SIGIL_STRICT_GATE=1 AEON_DIR=/home/volence/sonic_hacks/aeon \
SIGIL_EMIT=/home/volence/sonic_hacks/sigil/target/release/emit_sound_blob \
cargo test --workspace --release --no-fail-fast
```
  Expected: pin/golden failures ONLY for addresses this parcel shifted — every changed number must trace to the parcel; anything unexplained is a STOP. Hand-update `crates/sigil-harness/tests/repin_pins.rs` (and `src/pins.rs` if a literal pin moved) from the fresh `.lst`; re-run to 2990+/0/4.
- [ ] **Step 3:** Merge `parcel/bug005-sprites-player` → master (sequential, exact paths verified via `git show --stat`).
- [ ] **Step 4:** Sanctioned refreeze (from sigil):
```bash
cargo run -p sigil-harness --bin refreeze -- --check
SIGIL_EMIT=... SIGIL_BUILD=... AEON_DIR=/home/volence/sonic_hacks/aeon \
cargo run -p sigil-harness --bin refreeze -- --freeze bug005-sprites-player \
  --ab "replay-fixture 21/21 x4 + SAT byte-identical at fixed ticks + soak clean" \
  --note "BUG-005 net + sprites H1-H3 + player/camera cluster"
```
  Appends chain-31. Then **re-run the strict suite AFTER the refreeze** (the P3 countersign lesson: stale literals of this shift class can surface only post-refreeze; use `--no-fail-fast`).
- [ ] **Step 5:** Doc sync: mark the items DONE in `docs/reviews/2026-07-16-emp-port-optimization-review.md`'s queue (H1/H2/H3 sprites, camera H2, sensors H3, G1, G10, A7, M3 + note camera-H1 was pre-done); update `docs/BUGS.md` (BUG-005 instrumented; G10 fixed); `docs/DEFERRED_WORK.md` if any item lands there; `docs/ENGINE_ARCHITECTURE.md` sprite-render + camera sections if their described shapes changed (SST size $52!). Commit docs, push both masters.

---

## Self-review notes

- Spec coverage: BUG-005 net (T2), H1 (T3), H2 (T4), H3 (T5), camera H2+init clamp (T6), sensors H3 (T7), G10 (T8), A7 (T9), G1 (T10), M3 (T11), gate (T12). Camera H1 / PB1 / PB2 / G9 excluded as already-shipped. H4, M2, G4 explicitly out of scope.
- Type consistency: `Sst.frame_off` (T3) is the only new SST field; `PlayerV.jump_headroom` (T10) the only new overlay field; `Player_Bound_Right/Bottom` (T11) the only new game RAM. Names used consistently above.
- Known risk points, each with a STOP condition: SST grow overflow (T3 S2), fixture desync on G10/A7 (T8/T9 — inspect before re-recording), G1 skip-condition desync (T10 S5), post-refreeze stale literals (T12 S4).
