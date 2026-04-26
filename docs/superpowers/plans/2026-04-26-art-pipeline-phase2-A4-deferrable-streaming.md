# §2 Phase 2 — Layer A.4: Per-Section S4LZ Deferrable Streaming Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace A.3's blocking `Section_LoadArt` calls in `Section_TeleportFwd`/`Bwd` with budget-gated Deferrable DMA streaming triggered ahead of section transitions. The player should never see a stutter when crossing section boundaries — the camera's preload threshold fires earlier than the teleport threshold, kicking off streaming so tiles are already in VRAM by the time the leapfrog teleport runs.

**Architecture:** `Section_Check` gains preload-trigger hooks. When the camera crosses `SECTION_FWD_PRELOAD` (or `SECTION_BWD_PRELOAD`), `Section_StreamArtGroup(section_id)` runs: it checks per-section state (IDLE/STREAMING/RESIDENT), picks a free streaming buffer (double-buffered for fast direction reversals), decompresses the section's S4LZ blob into that buffer, and queues a Deferrable DMA to VRAM. By the time the camera reaches the teleport threshold, the DMA has drained. `Section_TeleportFwd`/`Bwd` keep `Section_LoadArt` as a fallback for sections that weren't preloaded (debug jumps, hard camera writes); in normal play, the streamed data is already resident and the fallback is a no-op (RESIDENT state → skip).

**Tech Stack:** 68000 assembly with the AS Macro Assembler, existing S4LZ decompressor, existing DMA queue (`QueueDMA_Deferrable`).

**Spec:** `docs/superpowers/specs/2026-04-26-art-pipeline-phase2-design.md` (Phase A.4 section)

**Out of scope:**
- Mid-decompress preemption (§9.7 cooperative multitasking)
- Velocity-adaptive thresholds (needs §3 player physics ground_speed)
- Vertical-axis section streaming (vertical level data deferred)
- Runtime VRAM allocator (milestone B)

---

## File map

**New files:**
- `docs/research/section-streaming.md` — Task 1 research output

**Modified files:**
- `tools/tile_dedupe.py`, `tools/test_tile_dedupe.py` — no changes (A.4 is engine-only)
- `tools/ojz_strip_gen.py` — no changes
- `build.sh` — no changes
- `constants.asm` — `STREAMING_BUFFER_SIZE`, `STREAMING_BUFFER_A`/`STREAMING_BUFFER_B` addresses; per-section state-byte values
- `ram.asm` — new `Section_Stream_State` byte array (per OJZ section), `Streaming_Active_Buffer` byte (round-robin tracker)
- `engine/level/load_art.asm` — `Section_StreamArtGroup` routine + state-machine logic
- `engine/level/section.asm` — `Section_Check` extended with preload-trigger hooks; `Section_TeleportFwd`/`Bwd` retain `Section_LoadArt` as RESIDENT-state fallback
- `data/levels/ojz/act1/act_descriptor.asm` — no changes
- `docs/research/tile-pipeline-measurements.md` — append A.4 row
- `docs/DEFERRED_WORK.md` — A.4 done entry
- `docs/ENGINE_ARCHITECTURE.md` — only if research surfaces something

---

## Task 0: Create feature branch

**Files:** none (git only)

- [ ] **Step 1: Create and check out the A.4 feature branch from master**

```bash
git checkout master
git status
git checkout -b feat/s2-a4-deferrable-streaming
git status
```

Expected: clean working tree, branch `feat/s2-a4-deferrable-streaming` checked out.

---

## Task 1: Research — full CLAUDE.md sweep, Genesis streaming prior art

**Files:**
- Create: `docs/research/section-streaming.md`

**Per `CLAUDE.md`'s research checklist + the user's stored "research breadth" feedback, this task does the FULL sweep. No shortcuts.** Same enforcement structure as A.2 and A.3 plans.

### Required source coverage (CLAUDE.md mandate)

- [ ] **Step 1: All 7 reference disassemblies — runtime art-streaming patterns**

Each disasm potentially streams art mid-gameplay differently. Look for: (a) deferrable DMA scheduling, (b) ahead-of-camera art preload, (c) state machines for in-flight loads, (d) buffer reuse / double-buffering.

```bash
ls /home/volence/sonic_hacks/Sonic-Clean-Engine-S.C.E.-/Engine/Core/
grep -ln 'PLC\|art.*stream\|DMA.*queue\|deferrable\|art_load\|Process_DMA' /home/volence/sonic_hacks/Sonic-Clean-Engine-S.C.E.-/Engine/Core/*.asm 2>/dev/null
ls /home/volence/sonic_hacks/sonic_hack/code/engines/
ls /home/volence/sonic_hacks/sonic_hack/plcs/
ls "/home/volence/sonic_hacks/The Adventures of Batman and Robin/disasm/code/engine/"
```

For sonic_hack specifically: read `code/engines/dma_plc.asm` (the PLC system) — that's S2/S3K's mechanism for queued art loading. Document `Process_PLC` / `Add_PLC` patterns:
- How does it deferred-load art across multiple VBlanks?
- How does it know when an art transfer completes?
- Per-PLC state machine?
- Preload-vs-blocking distinction?

For S.C.E.: search `Engine/Core/Load Level.asm` and `Engine/Variables.asm` for `KosPlus_module_queue` (mentioned in the A.3 research). That's S.C.E.'s queue for art transfers — it's per-module, deferrable.

For the 5 sibling disasms (B&R, Vectorman, TF4, Gunstar, Alien Soldier): look for runtime art-DMA scheduling — most of them use static loads, but document any deferrable patterns.

- [ ] **Step 2: SGDK's MAP system (modern Genesis homebrew streaming reference)**

Use WebFetch on:
- `https://github.com/Stephane-D/SGDK/tree/master/inc` — look for MAP_*.h or similar
- `https://github.com/Stephane-D/SGDK/blob/master/inc/map.h` — quote MAP_scrollTo, MAP_update, async-load patterns
- `https://github.com/Stephane-D/SGDK/blob/master/src/map.c` — quote actual streaming logic

Document:
- How does SGDK schedule per-frame load tasks?
- Buffer management — how many, where?
- Preload distance — does it look ahead based on camera direction?

- [ ] **Step 3: Online sources — full sweep**

WebFetch on each (catch failures, summarize):
- `https://plutiedev.com/dma-transfer` (or similar URL — try variants if 404)
- `https://md.railgun.works/index.php?title=DMA` — DMA scheduling patterns
- `https://md.railgun.works/index.php?title=Pattern_Load_Cue` — if exists
- `https://gendev.spritesmind.net/forum/` — search "art streaming", "deferred DMA", "Mode 7"-style reload patterns
- `https://segaretro.org/Sega_Mega_Drive/Memory_map` — DMA timing
- Search "Castlevania Bloodlines DMA" / "Thunder Force IV streaming" for any community write-ups

- [ ] **Step 4: GitHub homebrew check**

For projects known to have ambitious streaming:
- Xeno Crisis (SGDK-based; uses MAP)
- Tanglewood (SGDK-based)
- Demons of Asteborg (SGDK-based)
- Project MD (different engine)

WebFetch any visible source / write-ups about their streaming approach. Most will use SGDK's MAP — verify and note differences.

- [ ] **Step 5: Modern engine streaming literature**

Brief look at:
- **Asset streaming in Unity/Unreal** — `Resources.LoadAsync`, async asset bundles, distance-based prefetch
- **Texture streaming in 3D engines** — mipmap residency, LOD streaming, in-flight buffer pools
- **Look-ahead distance heuristics** — how do open-world engines pick how far ahead to preload?

Document concepts that map to our 68000 problem (most modern patterns are dynamic-allocation-driven; ours is static).

- [ ] **Step 6: Resolve A.4's open implementation questions**

Based on research:

**a. Preload threshold value.** Existing constants: `SECTION_FWD_PRELOAD = $0E00`, `SECTION_BWD_PRELOAD = $0400`. Teleport thresholds are `$1200` and `$0200`. So preload fires `$0400` = 1024 px before forward teleport, and `$0200` = 512 px before backward teleport. At normal Sonic camera speeds (~6 px/frame), forward preload gives ~170 frames of streaming time; backward gives ~85. Plenty for Deferrable DMA to drain ~270-byte blobs.

Default: keep existing thresholds. If research surfaces a specific recommendation (e.g., SGDK's MAP uses some specific lookahead distance), document and adjust.

**b. Decompressor invocation pattern.**

Two options:
- **Run-to-completion**: at preload-trigger frame, fully decompress S4LZ to buffer + queue DMA. CPU cost per trigger = decompress time. For ~270-byte blobs, decompress is ~1-2 ms (very fast).
- **Per-frame budget**: each frame, decompress N bytes from a checkpointed in-flight stream. Smoother but more complex; needs decompressor state save/restore.

Recommendation: **run-to-completion**. OJZ-scale data makes per-frame budgeting unnecessary. Future bigger sections might need budgeting; defer until they exist. Document this decision explicitly to prevent a future maintainer from adding unnecessary complexity.

**c. Single buffer vs double buffer.**

Spec settled this — **double-buffered**. Two ~4 KB buffers for fast direction reversals (preload N+1, then preload N-1 before N+1's DMA drains).

- [ ] **Step 7: Write the research notes**

Write `docs/research/section-streaming.md` with these exact sections:

1. **Sources reviewed** — every source actually opened, including unlisted breadth-search material
2. **Genesis prior art** — sonic_hack PLC system, S.C.E. KosPlus module queue, anything else found. Compare to A.4's design.
3. **SGDK MAP reference** — what does it do, how does it differ from A.4
4. **Preload threshold decision** — chosen value with one paragraph of justification
5. **Decompressor invocation pattern** — run-to-completion with one paragraph of justification
6. **Anything that changes ENGINE_ARCHITECTURE.md** — explicit list (state "none" if so)

- [ ] **Step 8: Commit research notes**

```bash
git add docs/research/section-streaming.md
git commit -m "$(cat <<'EOF'
docs(research): per-section streaming for §2 A.4

Full CLAUDE.md sweep — all 7 disasms, plutiedev/md.railgun/segaretro/
SpritesMind/GitHub homebrew/SGDK MAP system, modern engine streaming
literature.

Settles A.4's open questions:
- Preload threshold values (existing FWD/BWD constants are fine)
- Run-to-completion decompression (per-frame budgeting unneeded for
  current data scale)
- Double-buffered streaming (one buffer per pending preload, max 2
  in-flight via leapfrog adjacency invariant)

Genesis prior art: sonic_hack's PLC system is the closest analog —
deferrable per-tile-set queue with priority. SGDK's MAP system is
modern equivalent. Both differ from A.4 in granularity (per-zone /
per-screen, not per-section adjacency-aware).
EOF
)"
```

---

## Task 2: Apply research findings to ENGINE_ARCHITECTURE.md (conditional)

**Files:**
- Modify (conditional): `docs/ENGINE_ARCHITECTURE.md`

- [ ] **Step 1: Check the research notes**

Open `docs/research/section-streaming.md` section 6 ("Anything that changes ENGINE_ARCHITECTURE.md").

- [ ] **Step 2a: If list is empty, skip Task 2**

- [ ] **Step 2b: If list is non-empty**

Apply the listed changes surgically to `docs/ENGINE_ARCHITECTURE.md`. Commit:
```bash
git add docs/ENGINE_ARCHITECTURE.md
git commit -m "docs(arch): apply A.4 research findings"
```

---

## Task 3: Add streaming buffer + state constants

**Files:**
- Modify: `constants.asm`

Define the streaming buffer addresses and per-section state values. Buffers carve out the first 8 KB of the existing `Decomp_Buffer` region (which is 32 KB at $FFFF0000 and only used during level init blocking loads — safe to share with streaming during gameplay).

- [ ] **Step 1: Add A.4 streaming constants**

In `constants.asm`, find the A.2 multi-region block:

```asm
; Multi-region VRAM tile packing (§2 A.2)
; Region 1: primary art pool $0000-$BFFF (1536 tiles).
; Region 2: Plane B off-screen rows, $F800-$FFFF (64 tiles).
;   Safe because OJZ act_descriptor's cam_max_y=128 caps the visible
;   bottom row at nametable row 44; rows 45+ of Plane B never render.
;   Row 48 chosen for a 3-row safety margin against future cam_max_y bumps.
; tools/ojz_strip_gen.py REGION* constants must match.
REGION1_TILE_CAPACITY   = 1536
REGION2_VRAM_BASE       = $F800
REGION2_TILE_CAPACITY   = 64        ; ($10000 - $F800) / 32
```

Add immediately after that block:

```asm
; Per-section streaming (§2 A.4)
; Two double-buffered ~4 KB regions inside Decomp_Buffer ($FFFF0000-$FFFF7FFF).
; Decomp_Buffer is only used during Level_LoadArt at level init (display off);
; after init it's free, so streaming buffers carve out the first 8 KB.
STREAMING_BUFFER_SIZE   = 4096
STREAMING_BUFFER_A      = $FFFF0000     ; first 4 KB of Decomp_Buffer
STREAMING_BUFFER_B      = $FFFF1000     ; next 4 KB

; Per-section streaming state values (single byte per section)
SS_IDLE      = 0    ; not loaded, not streaming
SS_STREAMING = 1    ; decompressed + DMA queued, awaiting drain
SS_RESIDENT  = 2    ; in VRAM, valid

; Section_Preload_Flags bit definitions
SPF_FWD_PRELOADED = 0       ; bit 0: forward neighbour streamed
SPF_BWD_PRELOADED = 1       ; bit 1: backward neighbour streamed
```

- [ ] **Step 2: Build to confirm**

```bash
./build.sh -nl 2>&1 | tail -3
```
Expected: clean build (no callers reference these new symbols yet).

- [ ] **Step 3: Commit**

```bash
git add constants.asm
git commit -m "feat(§2): A.4 streaming buffer + state constants"
```

---

## Task 4: Add per-section streaming state RAM

**Files:**
- Modify: `ram.asm`

- [ ] **Step 1: Add Section_Stream_State + Streaming_Active_Buffer**

In `ram.asm`, find the existing section streaming state block:

```asm
; Section streaming state
Section_Preload_Flags:  ds.b 1          ; bits: fwd/bwd/up/dn preloaded
Section_Teleport_Guard: ds.b 1          ; cooldown after teleport (frames)
```

Add immediately after it:

```asm
; Per-section streaming state (§2 A.4)
; One byte per section (SS_IDLE / SS_STREAMING / SS_RESIDENT).
; Indexed by flat section_id (sec_y * grid_w + sec_x).
; Sized to OJZ act 1's 9 sections; future acts with larger grids need a bigger array.
Section_Stream_State:   ds.b 16         ; up to 16 sections; pad to even
Streaming_Active_Buffer: ds.b 1         ; 0 = next stream uses buffer A; 1 = buffer B
                        ds.b 1          ; pad to even
```

- [ ] **Step 2: Build to confirm**

```bash
./build.sh -nl 2>&1 | tail -3
```
Expected: clean build; RAM still under 64 KB.

- [ ] **Step 3: Commit**

```bash
git add ram.asm
git commit -m "feat(§2): A.4 per-section stream state + active-buffer tracker"
```

---

## Task 5: Implement `Section_StreamArtGroup`

**Files:**
- Modify: `engine/level/load_art.asm`

The new `Section_StreamArtGroup` is the heart of A.4: takes a Sec struct ptr, checks the section's stream state, picks a free buffer if needed, decompresses + queues Deferrable DMA. Idempotent — re-calling on a RESIDENT or STREAMING section is a no-op.

- [ ] **Step 1: Append `Section_StreamArtGroup` to load_art.asm**

Open `engine/level/load_art.asm`. Append (after the existing `Level_LoadArt`):

```asm
; -----------------------------------------------
; Section_StreamArtGroup — preload one section's tile art via Deferrable DMA.
;
; In:  a0 = Sec struct pointer
;      d6.w = flat section_id (sec_y * grid_w + sec_x), used to index
;             Section_Stream_State
; Out: none
; Clobbers: d0–d4, a0–a4
;
; State machine:
;   SS_IDLE      → decompress to active buffer, queue Deferrable DMA, mark
;                  SS_STREAMING. Round-robin active buffer (A/B).
;   SS_STREAMING → no-op (already in-flight; DMA will drain on its own)
;   SS_RESIDENT  → no-op (already in VRAM)
;
; A.4 model: run-to-completion S4LZ decompress + queued Deferrable DMA.
; The queue drains across upcoming VBlanks at Deferrable priority. By the
; time camera reaches the teleport threshold (~85-170 frames after the
; preload threshold), tiles are in VRAM.
; -----------------------------------------------
Section_StreamArtGroup:
        ; -- check current state --
        lea     (Section_Stream_State).w, a1
        move.b  (a1, d6.w), d0                      ; d0.b = current state
        cmpi.b  #SS_IDLE, d0
        bne.s   .skip                               ; already STREAMING or RESIDENT

        ; -- check that the section actually has art (null s4lz ptr → skip) --
        movea.l Sec_sec_tile_art_s4lz(a0), a2
        cmpa.w  #0, a2
        beq.s   .skip                               ; null ptr — nothing to stream

        ; -- pick active buffer (round-robin) --
        moveq   #0, d0
        move.b  (Streaming_Active_Buffer).w, d0
        beq.s   .use_buffer_a
        ; buffer B was active last; use B again? No — round-robin: switch.
        ; (We arrived here only because state was IDLE, so the OTHER buffer
        ; is whichever STREAMING section is using. Use the inactive one.)
        lea     (STREAMING_BUFFER_A).l, a3
        move.b  #0, (Streaming_Active_Buffer).w
        bra.s   .have_buffer
.use_buffer_a:
        lea     (STREAMING_BUFFER_B).l, a3
        move.b  #1, (Streaming_Active_Buffer).w
.have_buffer:
        ; -- check the s4lz uncompressed-size header (skip placeholder blobs) --
        move.w  (a2), d4                            ; d4.w = uncompressed size
        beq.s   .skip                               ; size 0 → placeholder, no streaming

        ; -- decompress run-to-completion into the chosen buffer --
        movea.l a2, a0                              ; a0 = source S4LZ
        movea.l a3, a1                              ; a1 = dest buffer
        bsr.w   S4LZ_Decompress                     ; clobbers d0-d3, a2

        ; -- queue Deferrable DMA: buffer → VRAM --
        moveq   #0, d0
        ; Reload Sec ptr — original a0 was clobbered by S4LZ_Decompress.
        ; Streaming buffer in a3 is preserved (not in clobber list).
        ; We still need the section's VRAM dest from the Sec struct, so the
        ; caller must guarantee that the Sec struct ptr survives this call.
        ; Simplest: caller passes Sec ptr in a4, we copy it locally.
        ; (See state-machine notes — Section_Check passes a4 = Sec ptr.)
        move.l  a3, d1                              ; d1 = source (RAM addr)
        moveq   #0, d2
        move.w  Sec_sec_tile_art_vram(a4), d2       ; d2.w = VRAM dest
        move.w  d4, d3                              ; d3.w = byte length
        bsr.w   QueueDMA_Deferrable

        ; -- mark section STREAMING --
        lea     (Section_Stream_State).w, a1
        move.b  #SS_STREAMING, (a1, d6.w)
        rts

.skip:
        rts
```

**Note for the implementer:** the "caller must pass Sec ptr in a4" convention is documented inline. Section_Check (Task 6) will set `a4 = Sec ptr` before calling `Section_StreamArtGroup`. If this convention turns out awkward in implementation, the alternative is to make `Section_StreamArtGroup` save/restore a0 around the `S4LZ_Decompress` call via the stack.

- [ ] **Step 2: Build to confirm linkage**

```bash
./build.sh -nl 2>&1 | tail -3
```
Expected: clean build (no callers yet).

- [ ] **Step 3: Commit**

```bash
git add engine/level/load_art.asm
git commit -m "feat(§2): Section_StreamArtGroup — Deferrable streaming primitive"
```

---

## Task 6: Wire preload-trigger hooks into `Section_Check`

**Files:**
- Modify: `engine/level/section.asm`

`Section_Check` currently checks the teleport thresholds. Extend it to ALSO check the preload thresholds (which are 1024 px earlier for FWD, 512 px earlier for BWD). When a preload threshold is crossed and the corresponding `Section_Preload_Flags` bit is clear, call `Section_StreamArtGroup` for the upcoming section and set the flag.

- [ ] **Step 1: Locate `Section_Check`**

In `engine/level/section.asm`, find:

```asm
Section_Check:
        tst.b   (Section_Teleport_Guard).w
        beq.s   .check
        subq.b  #1, (Section_Teleport_Guard).w
        rts

.check:
        move.l  (Camera_X).w, d0
        swap    d0                                 ; d0.w = camera X in pixels

        cmpi.w  #SECTION_FWD_THRESHOLD, d0
        bge.s   .fwd_check
        cmpi.w  #SECTION_BWD_THRESHOLD, d0
        ble.s   .bwd_check
        rts
```

Replace with:

```asm
Section_Check:
        tst.b   (Section_Teleport_Guard).w
        beq.s   .check
        subq.b  #1, (Section_Teleport_Guard).w
        rts

.check:
        move.l  (Camera_X).w, d0
        swap    d0                                 ; d0.w = camera X in pixels

        ; -- preload triggers (§2 A.4) — fire BEFORE teleport thresholds --
        cmpi.w  #SECTION_FWD_PRELOAD, d0
        bge.s   .fwd_preload_check
        cmpi.w  #SECTION_BWD_PRELOAD, d0
        ble.s   .bwd_preload_check
        bra.s   .threshold_check

.fwd_preload_check:
        btst    #SPF_FWD_PRELOADED, (Section_Preload_Flags).w
        bne.s   .threshold_check
        bsr.w   .preload_fwd
        bset    #SPF_FWD_PRELOADED, (Section_Preload_Flags).w
        bra.s   .threshold_check

.bwd_preload_check:
        btst    #SPF_BWD_PRELOADED, (Section_Preload_Flags).w
        bne.s   .threshold_check
        bsr.w   .preload_bwd
        bset    #SPF_BWD_PRELOADED, (Section_Preload_Flags).w

.threshold_check:
        cmpi.w  #SECTION_FWD_THRESHOLD, d0
        bge.s   .fwd_check
        cmpi.w  #SECTION_BWD_THRESHOLD, d0
        ble.s   .bwd_check
        rts

.preload_fwd:
        ; Section to forward = current slot 1's sec_x + 1 (clamped to grid_w).
        movea.l (Current_Act_Ptr).w, a2
        move.b  (Slot_Section_Map+2).w, d6         ; slot 1 sec_x
        addq.b  #1, d6
        cmp.b   Act_grid_w+1(a2), d6
        bge.s   .preload_skip
        ; Compute Sec ptr for section_id d6.w
        movea.l Act_sec_grid_ptr(a2), a4
        moveq   #0, d0
        move.b  d6, d0
        move.w  d0, d1
        lsl.w   #6, d0                             ; sec × 64
        lsl.w   #3, d1                             ; sec × 8
        add.w   d1, d0                             ; sec × 72 = Sec_len
        adda.w  d0, a4                             ; a4 = Sec ptr
        movea.l a4, a0                             ; a0 = Sec ptr (Section_StreamArtGroup convention)
        bra.w   Section_StreamArtGroup             ; tail call
.preload_skip:
        rts

.preload_bwd:
        ; Section to backward = current slot 0's sec_x - 1 (clamped to 0).
        movea.l (Current_Act_Ptr).w, a2
        move.b  (Slot_Section_Map).w, d6           ; slot 0 sec_x
        tst.b   d6
        beq.s   .preload_skip                       ; already at section 0
        subq.b  #1, d6
        ; Compute Sec ptr for section_id d6.w
        movea.l Act_sec_grid_ptr(a2), a4
        moveq   #0, d0
        move.b  d6, d0
        move.w  d0, d1
        lsl.w   #6, d0
        lsl.w   #3, d1
        add.w   d1, d0
        adda.w  d0, a4
        movea.l a4, a0
        bra.w   Section_StreamArtGroup
```

(The duplicate "compute Sec ptr" code is intentional per the no-placeholder rule — a future helper extraction is valid scope-creep but not in this task.)

- [ ] **Step 2: Build to confirm**

```bash
./build.sh 2>&1 | tail -3
```
Expected: clean build. (W005/W018/W020 baseline warnings unchanged.)

- [ ] **Step 3: Commit**

```bash
git add engine/level/section.asm
git commit -m "feat(§2): Section_Check fires Section_StreamArtGroup at preload thresholds"
```

---

## Task 7: Update teleport paths to use streaming + RESIDENT fallback

**Files:**
- Modify: `engine/level/section.asm`

After A.4 preloading, the teleport-time `Section_LoadArt` call is usually redundant (section is already RESIDENT). But it's cheap to keep as a safety net for: (a) cold camera jumps that bypass preload, (b) initial level boot (where Section_Init already calls Level_LoadArt for both initial slots).

The right behavior on teleport:
1. After slot map update, mark the new section RESIDENT (in case it was STREAMING → DMA must have finished by now since teleport threshold is reached LATER than preload threshold)
2. As a defensive fallback: call `Section_LoadArt` if state is still IDLE (preload didn't fire — e.g., cold camera write)

Also: clear the relevant `Section_Preload_Flags` bit on teleport (so the next preload past the threshold can fire again).

- [ ] **Step 1: Update `Section_TeleportFwd`**

In `engine/level/section.asm`, find the current `Section_TeleportFwd`. Replace the trailing block:

```asm
        move.b  #4, (Section_Teleport_Guard).w

        ; -- A.3: load new slot 1 section's tile art (blocking) --
        moveq   #SLOT_RIGHT, d0
        movea.l (Current_Act_Ptr).w, a2
        bsr.w   Section_GetSlotDef                  ; a0 = Sec ptr for new slot 1
        bra.w   Section_LoadArt                     ; tail call
```

with:

```asm
        move.b  #4, (Section_Teleport_Guard).w

        ; -- A.4: clear FWD-preload flag so next forward preload can fire --
        bclr    #SPF_FWD_PRELOADED, (Section_Preload_Flags).w

        ; -- promote new slot 1 section's state to RESIDENT (DMA assumed drained) --
        ; If state is still IDLE, fall back to blocking Section_LoadArt.
        moveq   #SLOT_RIGHT, d0
        movea.l (Current_Act_Ptr).w, a2
        bsr.w   Section_GetSlotDef                  ; a0 = Sec ptr for new slot 1
        move.b  (Slot_Section_Map+2).w, d6         ; slot 1 flat sec_id (sec_y=0 for OJZ)
        lea     (Section_Stream_State).w, a1
        move.b  (a1, d6.w), d0
        cmpi.b  #SS_IDLE, d0
        beq.s   .fwd_blocking                       ; preload didn't fire → fall back
        ; STREAMING or RESIDENT → just mark RESIDENT (in case it was STREAMING)
        move.b  #SS_RESIDENT, (a1, d6.w)
        rts
.fwd_blocking:
        bra.w   Section_LoadArt                     ; blocking fallback
```

- [ ] **Step 2: Update `Section_TeleportBwd`**

Same pattern. Find the trailing block:

```asm
        move.b  #4, (Section_Teleport_Guard).w

        ; -- A.3: load new slot 0 section's tile art (blocking) --
        moveq   #SLOT_LEFT, d0
        movea.l (Current_Act_Ptr).w, a2
        bsr.w   Section_GetSlotDef                  ; a0 = Sec ptr for new slot 0
        bra.w   Section_LoadArt                     ; tail call
```

Replace with:

```asm
        move.b  #4, (Section_Teleport_Guard).w

        ; -- A.4: clear BWD-preload flag --
        bclr    #SPF_BWD_PRELOADED, (Section_Preload_Flags).w

        moveq   #SLOT_LEFT, d0
        movea.l (Current_Act_Ptr).w, a2
        bsr.w   Section_GetSlotDef                  ; a0 = Sec ptr for new slot 0
        move.b  (Slot_Section_Map).w, d6           ; slot 0 flat sec_id
        lea     (Section_Stream_State).w, a1
        move.b  (a1, d6.w), d0
        cmpi.b  #SS_IDLE, d0
        beq.s   .bwd_blocking
        move.b  #SS_RESIDENT, (a1, d6.w)
        rts
.bwd_blocking:
        bra.w   Section_LoadArt                     ; blocking fallback
```

- [ ] **Step 3: Build**

```bash
./build.sh 2>&1 | tail -5
```
Expected: clean build.

- [ ] **Step 4: Commit**

```bash
git add engine/level/section.asm
git commit -m "feat(§2): teleport paths use streamed art with blocking fallback (A.4)"
```

---

## Task 8: Mark initial slot sections RESIDENT after `Level_LoadArt`

**Files:**
- Modify: `engine/level/load_art.asm`

`Level_LoadArt` already loads slot 0 + slot 1 sections at level init via blocking `Section_LoadArt`. After A.4, those sections are now in VRAM and should be marked RESIDENT in `Section_Stream_State` so subsequent preload triggers don't re-stream them.

- [ ] **Step 1: Update `Level_LoadArt` to mark RESIDENT**

In `engine/level/load_art.asm`, find:

```asm
Level_LoadArt:
        movem.l a0/a4, -(sp)
        movea.l a0, a4                              ; a4 = act ptr (saved across calls)

        ; -- slot 0 --
        moveq   #SLOT_LEFT, d0
        movea.l a4, a2                              ; a2 = act ptr for Section_GetSlotDef
        bsr.w   Section_GetSlotDef                  ; a0 = Sec ptr for slot 0
        bsr.w   Section_LoadArt

        ; -- slot 1 --
        moveq   #SLOT_RIGHT, d0
        movea.l a4, a2
        bsr.w   Section_GetSlotDef                  ; a0 = Sec ptr for slot 1
        bsr.w   Section_LoadArt

        movem.l (sp)+, a0/a4
        rts
```

Replace with:

```asm
Level_LoadArt:
        movem.l a0/a4, -(sp)
        movea.l a0, a4                              ; a4 = act ptr (saved across calls)

        ; -- slot 0 --
        moveq   #SLOT_LEFT, d0
        movea.l a4, a2
        bsr.w   Section_GetSlotDef                  ; a0 = Sec ptr for slot 0
        bsr.w   Section_LoadArt
        ; mark RESIDENT
        moveq   #0, d6
        move.b  (Slot_Section_Map).w, d6
        lea     (Section_Stream_State).w, a1
        move.b  #SS_RESIDENT, (a1, d6.w)

        ; -- slot 1 --
        moveq   #SLOT_RIGHT, d0
        movea.l a4, a2
        bsr.w   Section_GetSlotDef                  ; a0 = Sec ptr for slot 1
        bsr.w   Section_LoadArt
        ; mark RESIDENT
        moveq   #0, d6
        move.b  (Slot_Section_Map+2).w, d6
        lea     (Section_Stream_State).w, a1
        move.b  #SS_RESIDENT, (a1, d6.w)

        movem.l (sp)+, a0/a4
        rts
```

- [ ] **Step 2: Build**

```bash
./build.sh 2>&1 | tail -3
```
Expected: clean build.

- [ ] **Step 3: Commit**

```bash
git add engine/level/load_art.asm
git commit -m "feat(§2): Level_LoadArt marks initial slot sections RESIDENT (A.4)"
```

---

## Task 9: Exodus verification — slow scroll triggers preload, no stutter

**Files:** none (Exodus interaction)

A.4's payoff is "no stutter on section transition." Verification: smoothly scroll the camera across a section boundary (gradually, not via direct write) and confirm the rendering stays smooth.

- [ ] **Step 1: User reloads s4.bin in Exodus**

Tell the user: "Please reload `s4.bin` in Exodus."

- [ ] **Step 2: Sanity-check Exodus state**

`mcp__exodus__emulator_status` — verify running, PC at `VSync_Wait`.

- [ ] **Step 3: Verify initial state — slot 0+1 sections RESIDENT**

Run:
```python
mcp__exodus__emulator_read_memory(symbol="Section_Stream_State", len=16)
```

Expected: bytes [02, 02, 00, 00, 00, 00, 00, 00, 00, ...]. First two bytes = SS_RESIDENT (slot 0 = section 0, slot 1 = section 1, both loaded by Level_LoadArt). Remaining sections IDLE.

- [ ] **Step 4: Hold RIGHT to scroll the camera**

The OJZ scroll test reads `Ctrl_1_Held` and adds 6 px/frame to Camera_X when bit 3 (RIGHT) is set. To simulate held-right via Exodus MCP, write `Ctrl_1_Held` repeatedly OR directly advance Camera_X gradually.

Simplest: ramp Camera_X manually in 64-px increments and verify state transitions:

```python
# Move from start (0x02600000) to just past FWD_PRELOAD ($0E00) = 0x0E000000
mcp__exodus__emulator_write_memory(symbol="Camera_X", value=0x0E100000, width=4)
# Sleep 1 second to let the engine run a frame
import time; time.sleep(1)
# Verify Section_Stream_State[2] (section 2, the upcoming one) is now SS_STREAMING or SS_RESIDENT
mcp__exodus__emulator_read_memory(symbol="Section_Stream_State", len=16)
```

Expected: byte 2 = SS_STREAMING (1) or SS_RESIDENT (2) — preload fired. Byte 0 still SS_RESIDENT (2). Byte 1 SS_RESIDENT.

- [ ] **Step 5: Continue past teleport threshold**

```python
# Move past FWD_THRESHOLD ($1200)
mcp__exodus__emulator_write_memory(symbol="Camera_X", value=0x12100000, width=4)
import time; time.sleep(1)
# Verify slot map advanced and new section is RESIDENT
mcp__exodus__emulator_read_memory(symbol="Slot_Section_Map", len=4)
mcp__exodus__emulator_read_memory(symbol="Section_Stream_State", len=16)
mcp__exodus__emulator_screenshot()
```

Expected:
- Slot_Section_Map = 01 00 02 00 (slot 0 = sec 1, slot 1 = sec 2)
- Section_Stream_State[1] = SS_RESIDENT, [2] = SS_RESIDENT (was preloaded), other bytes SS_RESIDENT or SS_IDLE
- Screenshot: clean rendering, no glitches

- [ ] **Step 6: Reset and try a fast direction reversal**

```python
# Back to start
mcp__exodus__emulator_write_memory(symbol="Camera_X", value=0x02600000, width=4)
# Reset preload flags + stream state via a fresh ROM reload (or live-write)
import time; time.sleep(1)
```

Then: smoothly scroll right, then immediately reverse left. Both directions should complete without artifacts. The double-buffer should hold both pending streams.

- [ ] **Step 7: No commit — verification only**

---

## Task 10: Update measurements log with A.4 numbers

**Files:**
- Modify: `docs/research/tile-pipeline-measurements.md`

A.4 doesn't change tile counts or VRAM bytes — it changes *when* loads happen. Update the row to reflect the new behaviour.

- [ ] **Step 1: Find the A.4 row in the measurements table**

Open `docs/research/tile-pipeline-measurements.md`. Find:

```
| A.4 | tbd | tbd | tbd | tbd | tbd | tbd | tbd | tbd | tbd | tbd |
```

Replace with:

```
| **A.4** | 48 | 14 | 1856 | 2 | 10 (28.6%) | 19 | yes (2 colors) | per-section: 9 blobs ≤320 each (unchanged from A.3) | per-section: ~270 each (unchanged) | $0000-$013F + $0140-$027F (unchanged) |
```

- [ ] **Step 2: Add an A.4 explainer paragraph**

Below the existing A.3 paragraph in the doc, add:

```markdown
## A.4 makes section transitions seamless

A.4 adds a preload trigger to `Section_Check`: when the camera crosses `SECTION_FWD_PRELOAD` (1024 px before the teleport threshold) or `SECTION_BWD_PRELOAD` (512 px before), `Section_StreamArtGroup` decompresses the upcoming section's S4LZ blob into one of two streaming buffers (double-buffered for fast direction reversals) and queues a Deferrable DMA. By the time the camera reaches the teleport threshold, the DMA has drained — the teleport itself does no work beyond clearing a flag.

**Per-section state machine:** each section is in one of three states: `SS_IDLE`, `SS_STREAMING`, `SS_RESIDENT`. State is tracked in 16 bytes of RAM (`Section_Stream_State`). Initial slots 0+1 are RESIDENT after `Level_LoadArt`. Crossing a preload threshold transitions the upcoming section IDLE → STREAMING; crossing the teleport threshold promotes it to RESIDENT.

**Robustness:** if a hard camera write (debug, scripted) bypasses the preload threshold and triggers the teleport directly, the new section is still IDLE. `Section_TeleportFwd`/`Bwd` checks state and falls back to blocking `Section_LoadArt` for IDLE sections. The streaming path is the optimization; blocking remains the safety net.

**No measurement change:** A.4 doesn't alter tile counts, deduped pool size, or S4LZ ratios. It changes *when* loads happen, not how much. The empirical win is "no stutter on section transition" — a qualitative improvement visible only in profiling or live play.
```

- [ ] **Step 3: Commit**

```bash
git add docs/research/tile-pipeline-measurements.md
git commit -m "docs(research): A.4 streaming — same numbers, seamless transitions"
```

---

## Task 11: Update DEFERRED_WORK.md

**Files:**
- Modify: `docs/DEFERRED_WORK.md`

- [ ] **Step 1: Add A.4 to the Done section above A.3's entry**

Open `docs/DEFERRED_WORK.md`. Find:

```
### §2 Phase 2 Layer A.3 — Build-time Graph Coloring — 2026-04-26
```

Insert immediately above:

```markdown
### §2 Phase 2 Layer A.4 — Per-Section Deferrable Streaming — <today's date>
**Completed in:** §2 Phase 2 Layer A.4
**What:** `Section_StreamArtGroup` (engine/level/load_art.asm) decompresses + queues Deferrable DMA for an upcoming section. `Section_Check` extended to fire the preload trigger ~1024 px before the FWD teleport threshold (and ~512 px before BWD). Per-section state machine in `Section_Stream_State` (16 bytes RAM): `SS_IDLE` → `SS_STREAMING` → `SS_RESIDENT`. Two streaming buffers (`STREAMING_BUFFER_A`/`B`, 4 KB each, carved from existing `Decomp_Buffer`) handle fast direction reversals. `Section_TeleportFwd`/`Bwd` retain blocking `Section_LoadArt` as a fallback for IDLE-state sections (cold camera writes / debug jumps).
**Verified in Exodus:** Smooth horizontal scroll triggers preload at ~$0E00, advances state to SS_STREAMING; teleport at $1200 finds section RESIDENT and skips blocking load. No visible stutter on section transitions in normal play. Hard camera writes that bypass preload fall back to blocking — still correct, just stutters.
**Closes the §4 Phase 1 deferred item:** "Section Preload with S4LZ Deferrable DMA".
**See:** `docs/research/section-streaming.md`, `docs/research/tile-pipeline-measurements.md`.

```

(Replace `<today's date>` with the actual date.)

- [ ] **Step 2: Also close the §4 deferred item**

Find the still-open `§4 Phase 1 — Level/World System` entry "Section Preload with S4LZ Deferrable DMA" and convert it to strikethrough format pointing at the Done entry, like the existing closed §1 entries (e.g., `~~Scroll / Plane Drawing — Core (§1.3)~~ — DONE`).

- [ ] **Step 3: Commit**

```bash
git add docs/DEFERRED_WORK.md
git commit -m "docs: §2 A.4 — Deferrable streaming complete; closes §4 preload item"
```

---

## Task 12: s4budget + final lint check

**Files:** Read-only

- [ ] **Step 1: Run the budget tool**

```bash
python3 tools/s4budget.py s4.lst s4.bin --summary
```
Expected: ROM ~641-642 KB; RAM ~41 KB. A.4 adds ~150 bytes of new asm code (Section_StreamArtGroup + Section_Check hooks) plus 18 bytes RAM (Section_Stream_State[16] + Streaming_Active_Buffer + pad).

- [ ] **Step 2: Run full lint**

```bash
./build.sh
```
Expected: clean build; warning count should match A.3's baseline (2 W020 in core.asm and section.asm:40, both pre-existing).

- [ ] **Step 3: No commit — verification only**

---

## Task 13: Merge to master

**Files:** none (git only)

- [ ] **Step 1: Verify clean working tree**

```bash
git status
git log --oneline master..HEAD
```
Expected: clean tree; commit list shows the work from Tasks 0-11.

- [ ] **Step 2: Merge with --no-ff**

```bash
git checkout master
git merge --no-ff feat/s2-a4-deferrable-streaming -m "$(cat <<'EOF'
Merge §2 Phase 2 Layer A.4: per-section Deferrable streaming

Replaces A.3's blocking Section_LoadArt at section transitions with
budget-gated Deferrable DMA streaming triggered ahead of the boundary.
Section_Check fires the preload at SECTION_FWD_PRELOAD/BWD_PRELOAD
(~1024/512 px before the teleport thresholds); Section_StreamArtGroup
decompresses + queues Deferrable DMA via one of two double-buffered
streaming regions. By the time the camera reaches the teleport
threshold, the DMA has drained.

Per-section state (SS_IDLE/SS_STREAMING/SS_RESIDENT) tracked in 16
bytes of RAM. Section_TeleportFwd/Bwd now check state — STREAMING or
RESIDENT means tiles are in VRAM and the teleport just clears a flag;
IDLE falls back to blocking Section_LoadArt for safety (cold camera
writes, debug jumps).

Closes the §4 Phase 1 deferred item "Section Preload with S4LZ
Deferrable DMA".

A.5 (per-section background art) is the final layer.
EOF
)"
```

- [ ] **Step 3: Verify post-merge build**

```bash
./build.sh
```
Expected: clean build on master.

- [ ] **Step 4: Delete the feature branch**

```bash
git branch -d feat/s2-a4-deferrable-streaming
git status
git log --oneline -3
```

---

## Self-review checklist (run before claiming done)

- [ ] All 27 unit tests in `tools/test_tile_dedupe.py` still pass (no test changes in A.4)
- [ ] `python3 tools/ojz_strip_gen.py test` still passes
- [ ] `./build.sh` produces `s4.bin` with no errors and warning count matching A.3's baseline
- [ ] In Exodus: smooth scroll across a section boundary triggers preload (`Section_Stream_State` byte transitions IDLE → STREAMING → RESIDENT), no visible stutter on transition
- [ ] In Exodus: hard camera write that skips preload still produces correct rendering (blocking fallback fires)
- [ ] `docs/DEFERRED_WORK.md` has the A.4 entry in the Done section AND the §4 "Section Preload with S4LZ Deferrable DMA" item is closed
- [ ] `docs/research/tile-pipeline-measurements.md` has the A.4 row populated with same numbers as A.3 (A.4 changes timing, not amount)
