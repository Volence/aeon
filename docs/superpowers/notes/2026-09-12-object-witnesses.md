# Object and ring runtime witnesses, 2026-09-12 (helper on branch `witness/objects-0912`)

Five still-owed runtime witnesses, run headless against master's debug ROM. Every expected value
below is derived from source or from the build's own constants; the survey
(`survey/physics-scene-0912:docs/superpowers/notes/2026-09-12-physics-scene-survey.md`, sections
3a/3b/3e/3f/3g) and the s7 note were used as recipes and as cross-checks only.

- **ROM:** `/home/volence/sonic_hacks/.aeon-ls8-land/s4.debug.bin`, **crc32 `9ce1c2ff`, 847533 B**,
  verified by the tool on every run before anything else; listing `s4.debug.lst` beside it. That
  tree's HEAD is master `9fe9ee91`. Read only.
- **Instrument:** own `oracle-aether` spawned through `tools/aether_instance.py` (handshake
  `implementation: "oracle-rs"`, `serverBuild` `bd60c3dc…`, release). No emulator MCP, no foreign
  socket. Every run reaps its own pid and checks it is gone.
- **Tool:** `tools/lens_residue_object_witness.py` (one subcommand per witness plus `all`). A
  witness tool, not a gate: wired into nothing.
- **Final run:** `python3 -X pycache_prefix=$(mktemp -d) tools/lens_residue_object_witness.py all`
  from branch tip `87fddb09`, **2026-09-12 14:29:52Z to 14:30:02Z** (`date -u` either side),
  **exit 0**, own pid 2950181, "reaped: gone". An earlier `all` run on the same code (14:28:37Z to
  14:28:44Z) printed the same 48 lines, checked with `diff`. The only lines excluded from the
  diff were the start timestamp, the pid/socket line, the reap line and the per-witness
  wall-clock suffixes.

| witness | verdict | key measured value | control |
|---|---|---|---|
| C2a-6 staleness net (3b) | **WITNESSED** | raise rail `$37F8` hit in pass 1 (frame 400), a0 `$FF8FFE` = Player_1, d1 (cached) `$0008`, d0 (live) `$0006`; `MDDBG__ErrorHandler` `$C06AC` entered | A (count `$FF` only): 2 passes return, Player_1 owns 0 SAT entries (baseline 1). B (mappings 0 in band (4,0), with the same stale pokes): 2 passes return |
| Draw_Sprite multisprite parent (3f) | **WITNESSED** | 3/3 children: `.offscreen` visited, `.no_parent` not, RF_ONSCREEN clear (`$68`); `.multi_sprite` hit with a0 `$FF9AEE` = parent; parent and each child own 1 SAT entry | parent RF_MULTISPRITE cleared: 3/3 children via `.no_parent`, RF_ONSCREEN set; 2 passes with no `.multi_sprite` |
| Draw_Sprite null mappings (3g) | **WITNESSED, NATURAL path** | sparkle slot `$A44E`, frame 427: code_addr `$0000`, mappings `$00000000`, `.no_parent` → `$36B2` = `.offscreen` | the same slot's 24 live visits (derived 24) fell through the null test |
| C4a-2 collected half (3e) | **WITNESSED** | evicted at Camera_X 4616 (derived slide at 4608), park holds id 0 with ring mask `01 00…`; home: section-0 indices [1..6], window slot mask `01 00…`, park entry freed | no collect: park never holds section 0; home: indices [0..6], mask all zero |
| C4a-3 DespawnRings at a full buffer (3a) | **WITNESSED** | keep-all **15224** cycles (106568 mclk), remove-all **65400** cycles (457800 mclk), 0 interrupts in either window | both equal the hand-derived model; loop passes 128/128, `RingBuffer_Remove` 0 / 128, Ring_Count after 128 / 0 |

## Method, and one finding about the scene

**Boot.** Every witness restores one checkpoint taken at boot + 400 frames: frame 400, Player_1
in debug fly at (256,256), camera (96,144), `Player_1.code_addr` = `Player_Main − ObjCodeBase`,
`PlayerV.debug_flag` (`$3C`) set, `Debug_Scene_Freeze` 0. The `debug_flag` offset is packed from
the `PlayerV` overlay in `player_common.emp`, and checked against the three offsets the listing
exports (`_pl_gsp` $30, `_pl_state` $32, `_pl_flip_angle` $38).

**B is held, not tapped.** The frame boundary at boot + 400 falls mid-tick (the PC is inside
`Tile_Cache_Fill`), so an `emulator/press` returns with the B tick half-run. The first version
tapped B, read the ring state straight after, and saw no collect. A second tap straight after
the first gave the game no release edge, so fly never came back. The tool now holds B until the
event it needs (`RingSparkle_Spawn` for a collect, `debug_flag` flipping otherwise), releases it,
and allows two release polls before the next press. The controller's premise holds: one B press
hands the player to physics.

**Finding: once the player is in physics, the scene lags.** One logic tick can span two frames.
In fly, `Render_Sprites` is entered once per frame (frames 400–411, measured). After the collect,
the next `Draw_Sprite` of any object after the collect tick's `Render_Sprites` (frame 401) ran
in frame 403. The first null-mappings run used a 2-frame `run_to` budget and broke out before
its first arrival, a false NOT WITNESSED. So every "must not happen" control now runs over
**counted `Render_Sprites` passes** instead of frame budgets. `render_pass()` brackets one call
by its entry and the return address read off the stack at entry. It arms execution breakpoints
at the thing under test, and a pass that returns to the caller counts as one whole render. The
detector is validated inside each run: every subject trips the same breakpoint its control must
not.

## C2a-6 — the staleness net ahead of the overflow pre-check (survey 3b)

`python3 tools/lens_residue_object_witness.py c2a6`

**Derivation.** `Render_Sprites` (`engine/objects/sprites.emp`) runs its DEBUG net for every
non-null band entry with live mappings: it live-resolves `word[mappings + 2·mapping_frame]` and
asserts it equals the cached `frame_off`. Only after that does the overflow pre-check run, which
skips an object whose `piece_count + d5 > MAX_VDP_SPRITES` (80). So a stale offset must trip the
net even with a count the pre-check would skip (`$FF`). A count-only poke must skip the object
without tripping. A null-mappings slot must skip the net (`beq .stale_net_done`).

**Detector.** The net's raise rail is the one `$diag<n>$engine.objects.sprites$raise` label
between `Render_Sprites$object_loop` ($37C6) and `$stale_net_done` ($3842), which is `$37F8` in
this ROM. The tool locates it by position rather than by diag number, and checks that its bytes
contain `jsr MDDBG__ErrorHandler` (`4EB9 000C06AC`). Disassembly: `$37F0 move.w sr,-(a7)` ·
`$37F2 cmp.w d0,d1` · `$37F4 beq.w $3840` (the pass path, `move.w (a7)+,sr`) · `$37F8` the raise.
Detection is by PC, never by screenshot.

**Raw values.** At boot + 400, Player_1 has mappings `$02B66A`, mapping_frame 0, frame_off `$0006`,
live-resolved `$0006` (consistent), piece count 1, render_flags `$81`. The wrong value is
`$0006 + 2 = $0008` (even, and different).
- Baseline, no poke: 2 passes return (at `$BE646`, the caller), and Player_1 owns 1 SAT entry.
- **Subject** (count `$FF`, frame_off `$0008`, poked at the checkpoint, before this tick's
  render): pass 1 stops at `$37F8`, frame 400. a0 `$FF8FFE` (Player_1), d1 `$0008` (cached),
  d0 `$0006` (live). `run_to MDDBG__ErrorHandler` is then reached.
- **Control A** (count `$FF` only): 2 passes return and neither breakpoint is hit. Player_1 owns
  **0** SAT entries in the poked pass (baseline 1), so the pre-check skipped the marker, as the
  parcel TAG predicted.
- **Control B**, poked at `Render_Sprites` entry after `Draw_Sprite` registered Player_1 (found in
  band 4, index 0): mappings 0, plus the subject's count `$FF` and frame_off `$0008`. 2 passes
  return and neither breakpoint is hit. The subject's two stale pokes were kept here so that B
  differs from the subject only by the null mappings. Without the null guard, the net would read
  `ROM[0 + 2·0]` and compare it against `$0008`.

**Survey.** The recipe is right. It is Player_1 in fly, and nothing refreshes the cache before the
render.

## Draw_Sprite: the multisprite parent (survey 3f)

`python3 tools/lens_residue_object_witness.py multisprite`

**Derivation.** `Draw_Sprite` (`sprites.emp`, disassembled): `$36A2 move.w $26(a0),d0` · `beq
$36BA` (`.no_parent`) · `movea.w d0,a1` · `btst #4,$e(a1)` (the parent's RF_MULTISPRITE) · `beq
$36BA` · then it falls into `$36B2` `.offscreen` (`bclr #0,$e(a0)`, `rts`). So a child of a
batching parent must reach `$36B2` without `$36BA`, and leave RF_ONSCREEN (bit 0) clear.
`Render_Sprites` branches to `.multi_sprite` ($38E0) on the parent's own RF_MULTISPRITE, and its
sibling walk stamps each child's SST word into `Sprite_Owner` (DEBUG). `TestParent`
(`test_parent.emp`) sets RF_COORDMODE and RF_MULTISPRITE and spawns `child_desc`'s 3 rows.

**Raw values.** Spawned through the mailbox: `Obj_Req_Def` = `ObjDef_Parent` ($BE2BA), X 160,
Y 112, Place 0, Op 1, and `Obj_Req_Flag` = 1 written last. The ack came within 1 frame: Status 0,
Slot `$9AEE`, code `$318C` (= TestParent_Main − ObjCodeBase), render_flags `$79`. Children
`$99FE`, `$9A4E`, `$9A9E`, each with parent_ptr `$9AEE` and code TestChildPart_Main.
- Each child's `Draw_Sprite`, stepped from entry to its return: `.offscreen` visited, `.no_parent`
  not; render_flags `$68` (RF_ONSCREEN clear).
- One counted `Render_Sprites` pass: the `.multi_sprite` breakpoint is hit with a0 `$FF9AEE`.
  After the pass, `Sprite_Owner` holds `$9AEE`×1, `$99FE`×1, `$9A4E`×1 and `$9A9E`×1: the
  children were drawn, by the parent's walk.
- The camera stayed at (96,144) throughout, and the parent was still alive (code `$318C`).
- **Control**, restored to the settled post-spawn checkpoint with the parent's RF_MULTISPRITE
  cleared: all 3 children go through `.no_parent` with RF_ONSCREEN set. 2 counted passes return
  with no `.multi_sprite` hit. The children still own 1 SAT entry each, now registered by
  themselves.

**Survey.** Right. The cull note does not bite at the boot camera.

## Draw_Sprite: null mappings, NATURAL path (survey 3g)

`python3 tools/lens_residue_object_witness.py nullmap`

**Derivation.** `RingSparkle_Main` is `jbsr AnimateSprite` / `jbra Draw_Sprite`. The script
`[5, 0, 1, 2, 3, AF_DELETE]` ends in AnimateSprite's `.cc_delete` → `jbra DeleteObject`, whose
`.clear_slot` zeroes all `sizeof(Sst)/4` longs. The survey had not read this; it is read here.
DeleteObject's rts returns into RingSparkle_Main, which then tail-jumps `Draw_Sprite` on the
zeroed slot: parent_ptr 0 → `.no_parent` → `movea.l $10(a0),a1 / move.l a1,d0 / beq $36B2`.
Expected live draws: `ring_sparkle.emp`'s build-time ensure pins the display length at
`S3K_SPARKLE_FRAMES × (S3K_SPARKLE_DURATION + 1)` = 4 × 6 = **24**.

**The collect.** Player_1 was poked, in fly, to (120,96) with ring 0 at (128,96). AABB overlap on
an axis is `2|d| < wa + wb` (`engine/objects/aabb.emp`), so ring 0 (d = 8) overlaps for any
player width from 1 to 31, and ring 1 (d = 24) stays clear for any width up to 32. The standing
box read back 19×39. B was held until `RingSparkle_Spawn` was reached, then released. At that
tick's `Render_Sprites` (frame 401): Ring_Count 7 → 6, Ring_Counter 0 → 1, section-0 indices
[1..6], and the sparkle is in effect slot `$A44E`.

**Raw values.** 24 arrivals at `.no_parent` with a0 = `$FFA44E` and mappings set; all 24 fell
through the null test. This is the control, and the count equals the derived 24. The 25th arrival,
at frame 427: code_addr `$0000`, mappings `$00000000`, and 3 steps later the PC is `$36B2` =
`.offscreen`. After the `bclr`, RF_ONSCREEN is clear.

**Survey.** Right. "prefer this [poke] over poking a spring" was not needed, because the natural
path is practical.

## C4a-2 — the collected half (survey 3e)

`python3 tools/lens_residue_object_witness.py c4a2`

**Derivation of the distance, which the survey could not give.**
- A window slide fires only when `EntityWindow_DeriveWindow`'s anchor changes:
  `sec_x0 = (Camera_X − ENTITY_DESPAWN_BUFFER) >> SECTION_SIZE_SHIFT` = `(Camera_X − 512) >> 11`
  (`EntityWindow_Scan` → `.slide`).
- The collected window is recentred only inside `EntityWindow_Slide`, on the camera centre
  `(Camera_X + SCREEN_WIDTH/2) >> 11`. `Collected_UpdateCenter` evicts a slot when
  `|slot_x − centre_x| > 1`, parking it if any bit is set.
- The 0→1 slide fires at Camera_X = 2560. Its centre is column (2560+160)>>11 = 1, so section 0
  is **kept**.
- The 1→2 slide fires at **Camera_X = 2·2048 + 512 = 4608**. Its centre is (4608+160)>>11 = 2,
  so section 0 is **evicted into the park**.
- Coming back, the 1→0 slide below 2560 has centre column 1 and entries in column 0.
  `BuildEntries` → `Collected_ClaimSlot` → `Collected_UnparkSlot` copies the mask back and frees
  the park entry.
- s7's 200-frame slide reached Camera_X 3232 (`$0CA0`), short of 4608. It exercised the retained
  slot, not the park.

**Raw values, subject.**
- The collect is the one described above.
- B is held again (after two release polls) to re-enter fly. The player is back in fly at
  (120,96), camera (32,80).
- RIGHT, polled every 4 frames: at 300 frames the camera is at (4616,16) and the centre id is 2.
  Window tags [255,1,255,4,2,5,255,255,255]: no section 0. The park holds `(0, 01 00…00)`, i.e.
  ring bit 0.
- LEFT for 300 frames plus 8 settle frames: camera (0,16). The section-0 buffer indices are
  **[1,2,3,4,5,6]**, at the editor list's positions. Section 0's window slot mask is `01 00…00`
  (bit 0 set), and the park no longer holds section 0.

**Raw values, control.** The same route with Player_1 40 px below ring 0 (2·40 = 80 ≥ 39+16, so
no overlap):
- Ring_Counter stays 0.
- At (4632,56) with centre 2 the park is **empty**, because a pristine slot is not parked.
- Home: indices **[0..6]**, mask all zero.

**Survey.** The recipe is right, with the distance above. The survey's "fly the marker onto list
index 0 (left 8 frames, up 10 frames)" was replaced by a position poke while in fly, which is
deterministic.

## C4a-3 — `EntityWindow_DespawnRings` at a full ring buffer (survey 3a)

`python3 tools/lens_residue_object_witness.py c4a3`

**Seed.** The tool stops at the proc's entry (`$4EB4`, frame 400; camera (96,144); tracked ids
[0,1,3,4]; natural Ring_Count 7) and checkpoints there. It writes `Ring_Count` =
`MAX_RING_BUFFER` = 128 (the listing's EQU; the parcel note reads the same `cmpi.b #$80`) and 128
six-byte entries, reads them back, and restores after each variant.
- **Keep-all:** x = Camera_X+160 = 256, y = Camera_Y+112 = 256, section 0.
- **Remove-all:** x = Camera_X + 320 + 512 + 16 = 944, right of the `[Camera_X−$200,
  Camera_X+$340]` window. Section 2 is untracked, so `EntryForSection` misses and
  `EntityLoaded_Clear` is skipped.

**Measurement.**
- Every instruction from the proc's first to the one after its `rts` is single-stepped, recording
  the PC and mclk, so an interrupt inside the window would be seen. Any step outside the proc
  and its three callees counts as foreign, and a window with one is discarded; neither variant
  had one.
- The same window, re-seeded from the same entry checkpoint and run with one `run_to` to the
  return address, gives the identical mclk delta.
- **Divisor 7:** the Mega Drive's 68000 is clocked at MCLK/7. The server's timing basis is
  896040 mclk per NTSC frame, i.e. 262 lines × 3420; 3420/7 = 488.6 cycles per line. Both deltas
  divide exactly.
- **"Entry to its rts" is measured including the rts** (16 cycles); excluding it, the figures are
  15208 and 65384.

| variant | instructions | loop passes | EntryForSection | RingBuffer_Remove | Ring_Count after | mclk | cycles |
|---|---|---|---|---|---|---|---|
| keep-all | 1936 | 128 | 0 | 0 | 128 | 106568 | **15224** |
| remove-all | 7696 | 128 | 128 | 128 | 0 | 457800 | **65400** |

**Hand-derived model**, from the ROM's disassembly and the MC68000 timing tables (no wait states).
It matches both measurements exactly:
- **Prologue, 100 cycles:** `moveq` 4, `move.b Ring_Count.w,d5` 12, `beq.w` not taken 12, `subq`
  4, the ×6 (`move.w` 4, then `move.w`/`add.w`/`add.w`/`add.w` 4 each = the parcel note's
  `mul_const` 16), `lea Ring_Buffer.w` 8, `adda.w` 8, `move.w Camera_X.w,d6` 12, `move.w` 4,
  `subi.w` 8, `addi.w` 8.
- **Keep iteration, 118 cycles:** `move.w (a2),d1` 8, `cmp` 4, `blt.b` not taken 8, `cmp` 4,
  `ble.b` taken 10, `move.w 2(a2),d1` 12, `move.w Camera_Y.w,d2` 12, `subi.w` 8, `cmp` 4,
  `blt.b` not taken 8, `addi.w` 8, `cmp` 4, `ble.b` taken 10, `subq.w #6,a2` 8, `dbf` taken 10.
- **Remove iteration, 510 cycles**, in parts:
  - X tests 32.
  - Four section compares 94: `move.b 4(a2)` 12, then 3 × (`cmp.b abs.w` 12 + `beq.b` not taken
    8), then `cmp.b` 12 + `bne.b` taken 10.
  - Remove setup 46: `moveq` 4, two `move.b d(a2)` 12 each, `bsr.w` 18.
  - `EntryForSection`, untracked, 214: `lea` 8, `moveq` 4, then 4 probes of `cmp.b (a0)` 8 +
    `beq` 8 + `lea` 8 + `addq` 4 + `cmpi` 8 + `bcs`, 10 taken and 8 on the last, then
    `moveq #-1` 4 and `rts` 16.
  - `tst.w` 4 + `bmi.b` taken 10.
  - `move.w` 4 + `bsr.w` 18.
  - `RingBuffer_Remove` removing the last entry, 70: `moveq` 4, `move.b abs.w` 12, `subq.b` 4,
    `bmi` not taken 8, `move.b →abs.w` 12, `cmp.w` 4, `beq.b` taken 10, `rts` 16.
  - `subq` 8 + `dbf` 10.
- **Tail:** the last `dbf` expires at 14 (+4), then `rts` 16.

Keep-all: 100 + 128·118 + 4 + 16 = **15224**. Remove-all: 100 + 128·510 + 4 + 16 = **65400**.
The model is a check on the instrument (no hidden wait states, no interrupt billed to the proc),
not a second measurement.

**Still owed (out of scope here):** the before/after on the ROM built from the parent of merge
`f64f26b3`. The parcel note's prediction (net ≈ 36 − 24N per frame, about −3.0 K at 128) needs
that ROM.

## Booking corrections for the controller

These are the corrections this run supports. I edited neither DEFERRED_WORK nor the s7 note.

1. **`docs/DEFERRED_WORK.md`, the C4a runtime-TAG status line** (the entity-window parcel's
   "Runtime TAGs" paragraph, "Status 2026-09-12 (seventh session …)").
   - "its collected half and the cycle counts NOT, because the boot scene (the OJZ scroll test)
     has no player physics" is wrong about the scene: one B press gives physics.
   - Now: **C4a-2 collected half WITNESSED** on `9ce1c2ff`, this note. **C4a-3 profiled at a full
     buffer, WITNESSED**: keep-all 15224 / remove-all 65400 cycles, equal to the hand model.
   - Still owed: C4a-3 before/after (parent of `f64f26b3`); C4a-2's
     `PopulateSectionRings`/`RescanY` before/after cycle counts (parent of `62fb300f`).
2. **The Draw_Sprite short-entry CLOSED row** (DEFERRED_WORK, "Not yet looked at at runtime"), and
   s7's "Not covered: a multisprite parent … and a null-mappings object". **Both paths are now
   WITNESSED** on the fixed ROM `9ce1c2ff`:
   - the batching child reaches `.offscreen` ($36B2) with RF_ONSCREEN clear;
   - `.multi_sprite` is reached with a0 = the parent;
   - a zeroed sparkle slot goes `.no_parent` → `.offscreen`, by the natural path.
   - The fix's *layout* claim (`.offscreen` between the two entry tests) is confirmed in the
     disassembly.
3. **C2a-6's runtime TAG** (s7's "Not run" list) is **WITNESSED**. The net fires ahead of the
   pre-check for count `$FF` + a stale offset. Count-only skips the marker without raising. Null
   mappings in a band do not raise.
4. **s7 note, "no player physics"** (the header line, the C4a-2 "Collected half" line, the C1b-3
   LIMIT, and the "Not run" list): wrong about the scene, as the survey already said. C1b-3's
   LIMIT is reachable with physics on, but was **not run here**.
5. **Survey 3e**: "Hold RIGHT 200 frames … Slide further (to sec_x 2)". The eviction needs the
   **sec_x0 1→2 slide at Camera_X ≥ 4608** (measured at 4616, after 300 frames of fly from x 120).
   s7's 200-frame trip (Camera_X 3232) kept section 0's slot and never reached the park, so s7's
   C4a-2 spawn half was a retained-slot run, not a respawn-park run.
6. **Recipe caveats for any future runtime witness in this scene**, measured:
   - B must be HELD to a known event, not tapped: the boot + 400 frame boundary falls mid-tick.
   - Two presses need a release poll between them.
   - After leaving fly, one tick can span two frames, so frame-budgeted "not reached" controls
     can be vacuous. Use counted passes.
7. **RUNTIME-TAG items not attempted here** (outside this brief): EFX-4b longer→shorter re-install,
   C3b-2 lag-frame residue, B2a-2 (no caller), C1b-3 at a non-zero cache origin with physics on.

## Nothing BLOCKED

All five ran headless. No build was needed or made; no `.emp` changed.
