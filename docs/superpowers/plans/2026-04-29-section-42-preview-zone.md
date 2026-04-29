# §4.2 Preview-Zone Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate the visible "warp at teleport" by adding preview-zone nametable copies on plane A and unifying plane B with per-frame DMA-queue streaming (deletes `BG_RedrawForSection`).

**Architecture:** Preview is nametable-only edge regions on both planes — 4 cols / 4 rows wide. Preview cells reference existing slot art. Dedicated copy routines (mirroring sonic_hack's `Section_CopyPreview` family) fire on source-section preload completion (FWD) and at teleport (BWD). Plane B replaces `BG_RedrawForSection`'s during-display burst with per-frame column writes through the existing deferred plane buffer + DMA queue.

**Tech Stack:** Motorola 68000 assembly (AS Macro Assembler), Sega Genesis VDP, existing `engine/level/` modules. No new compression or build pipeline; uses on-the-fly column extraction from existing `sec_bg_layout` for plane B.

**Spec:** `docs/superpowers/specs/2026-04-29-section-42-preview-zone-design.md`
**Branch:** `feat/section-42-preview-zone` (from `master` `0b8af3a`, tag `checkpoint/pre-teleport-refresh`)

---

## File Structure

**New file:**
- `engine/level/preview.asm` — preview-copy routines (`Section_CopyFwdPreview`, `Section_CopyBwdPreview`, plus stubs for vertical/diagonal)

**Modified files:**
- `constants.asm` — preview width constants
- `main.asm` — include the new preview.asm
- `engine/level/section.asm` — preload-completion hook + teleport hooks; remove `BG_RedrawForSection` calls
- `engine/level/bg.asm` — delete `BG_RedrawForSection`
- `engine/level/plane_buffer.asm` — add `Draw_BG_TileColumn` (plane B equivalent of `Draw_TileColumn`)
- `engine/level/camera.asm` — clamp toggle rule
- `docs/ENGINE_ARCHITECTURE.md` — update §4.1 / §4.4 / §4.5 per spec

---

## Verification Tooling

For this Genesis ROM project, "test" steps are not unit tests. Verification uses:

- **Build:** `./build.sh -pe` from `/home/volence/sonic_hacks/s4_engine` — must succeed (no errors in `s4.log`)
- **s4lint:** runs as part of build; warnings/errors block the commit gate
- **Exodus MCP** (already running on user's machine): inspect VRAM/CRAM/RAM via `mcp__exodus__emulator_read_vram` / `_read_memory` / `_screenshot`. User reloads ROM via `mcp__exodus__emulator_reload_rom`.
- **Visual frame-step:** scrub across teleport in Exodus, confirm no warp/tear/shuffle visible

After each task: build green + commit. Where Exodus inspection is called for, the step says exactly what to read and what bytes to expect.

---

## Task 1: Add Preview Constants

**Files:**
- Modify: `constants.asm` (around the existing `SECTION_SIZE`/`SLOT_ORIGIN` block, line ~213)

- [ ] **Step 1: Read existing constants context**

Run: `grep -n -E "SECTION_SIZE|SLOT_ORIGIN|STRIP_TILE" constants.asm`

Expected: shows `SECTION_SIZE = $0800`, `SLOT_ORIGIN_L = $0200`, `STRIP_TILE_HEIGHT = 48`. The new constants will sit alongside these.

- [ ] **Step 2: Add preview constants**

Add immediately after the `SLOT_ORIGIN_*` lines (~line 217):

```asm
; -- §4.2 preview-zone (4-col / 4-row edges on plane A + plane B) --
PREVIEW_COLS            = 4         ; nametable cols at FWD/BWD edges
PREVIEW_ROWS            = 4         ; nametable rows at TOP/BOT edges (vertical: stub for now)
PREVIEW_PIXELS          = PREVIEW_COLS*8    ; 32 px — used for camera clamp offset
SECTION_TILE_WIDTH      = SECTION_SIZE/8    ; 256 — tile cols per section
```

- [ ] **Step 3: Build**

Run: `./build.sh -pe`

Expected: builds clean. `s4.bin` produced. No new errors in `s4.log`.

- [ ] **Step 4: Commit**

```bash
git add constants.asm
git commit -m "feat(§4.2): add preview-zone constants"
```

---

## Task 2: Create `engine/level/preview.asm` with `Section_CopyFwdPreview` (plane A only)

**Files:**
- Create: `engine/level/preview.asm`
- Modify: `main.asm` (add include)

- [ ] **Step 1: Read `Draw_TileColumn` API**

Run: `sed -n '13,63p' engine/level/plane_buffer.asm`

Expected: confirms inputs `d0.w = target VDP nametable column (0–63)`, `d1.w = section tile column index (0-based)`, `a0 = section def pointer`. Clobbers d0–d3, a1–a2.

- [ ] **Step 2: Create `engine/level/preview.asm`**

Write to `engine/level/preview.asm`:

```asm
; §4.2 Preview-zone copy routines.
;
; Preview is nametable-only edge regions on plane A and plane B (PREVIEW_COLS
; cols on left + right; PREVIEW_ROWS rows on top + bottom — vertical is stubbed).
; Cells reference resident slot art; no extra VRAM is allocated.
;
; FWD preview = leading PREVIEW_COLS cols of next-section nametable strip,
;               written at plane cols 0..PREVIEW_COLS-1 (= world cols 576-579 mod 64).
; BWD preview = trailing PREVIEW_COLS cols of previous-section nametable strip,
;               written at plane cols 60..63 (= world cols 60-63 mod 64).
;
; Triggers (see section.asm):
;   FWD copy fires when source section's art preload completes (Section_LoadArt).
;   BWD copy fires at every teleport (Section_TeleportFwd / _Bwd).

; -----------------------------------------------
; Section_CopyFwdPreview — write FWD preview region of plane A.
; In:  a0 = Sec ptr (the section whose leading PREVIEW_COLS we copy)
; Out: none
; Clobbers: d0–d3, a1–a2
; -----------------------------------------------
Section_CopyFwdPreview:
        movem.l d4-d5, -(sp)
        moveq   #PREVIEW_COLS-1, d4         ; loop 4 times (d4 = 3..0)
        moveq   #0, d5                      ; d5 = src section tile col (starts at 0)
.loop:
        move.w  d5, d0                      ; dest plane col = 0..PREVIEW_COLS-1
        move.w  d5, d1                      ; src section tile col = 0..PREVIEW_COLS-1
        movem.l d4-d5/a0, -(sp)
        bsr.w   Draw_TileColumn             ; clobbers d0–d3, a1–a2
        movem.l (sp)+, d4-d5/a0
        addq.w  #1, d5
        dbf     d4, .loop
        movem.l (sp)+, d4-d5
        rts
```

- [ ] **Step 3: Add include to `main.asm`**

Find the existing level engine includes in main.asm (e.g., the include for `engine/level/section.asm` or similar). Add the new line nearby:

Run: `grep -n "engine/level/" main.asm`

Then edit `main.asm` to add (in the same group as other `engine/level/` includes):

```asm
    include "engine/level/preview.asm"
```

- [ ] **Step 4: Build**

Run: `./build.sh -pe`

Expected: builds clean. `s4.log` shows no errors.

- [ ] **Step 5: Commit**

```bash
git add engine/level/preview.asm main.asm
git commit -m "feat(§4.2): add Section_CopyFwdPreview (plane A)"
```

---

## Task 3: Hook `Section_CopyFwdPreview` into Section_LoadArt completion

**Files:**
- Modify: `engine/level/load_art.asm` (or `section.asm` if preload completion is signaled there)

- [ ] **Step 1: Find where Section_LoadArt completes**

Run: `grep -n "Section_LoadArt" engine/level/load_art.asm engine/level/section.asm | head -20`

Then read `engine/level/load_art.asm` lines 40-110 to find where `Section_LoadArt` returns and where it's called from for slot 0 (slot L) preloads.

- [ ] **Step 2: Add FWD preview hook**

In `engine/level/section.asm`, inside `Section_TeleportFwd` (around line 250-256, the `.fwd_cold_load` block) and the `.fwd_redraw_bg` block: after `Section_LoadArt` succeeds for the new slot 0, the section now resident in slot 0 is the one we just teleported into — its leading 4 cols become the FWD preview source for the NEXT cycle's preview… but actually the FWD preview source is the section that will land in slot 0 at NEXT teleport.

Stop. Re-read the spec timing. Actual rule: **FWD preview is populated when slot L (slot 0) is overwritten with the next-FWD section's art.** That happens during `Section_LoadArt` for slot 0 in the mid-section preload path (not in teleport itself).

Find the slot 0 preload path. Run:

```bash
grep -n -E "SLOT_LEFT|SS_RESIDENT|Section_LoadArt|slot 0" engine/level/section.asm | head -30
```

The slot 0 (slot L) preload completion needs identifying. Look for the streaming/preload code that fires when camera enters slot R (Sec1 traversal) and queues Sec2 into slot 0.

- [ ] **Step 3: Add Section_CopyFwdPreview call after slot 0 art preload completes**

Once the right line is identified (the moment Sec2's art has finished decompressing into slot 0's VRAM range), add:

```asm
        ; -- §4.2: slot 0 just got new art — that section becomes the FWD
        ;    preview source. Copy its leading PREVIEW_COLS into plane A
        ;    cols 0..PREVIEW_COLS-1.
        moveq   #SLOT_LEFT, d0
        movea.l (Current_Act_Ptr).w, a2
        bsr.w   Section_GetSlotDef          ; a0 = Sec ptr for slot 0
        bsr.w   Section_CopyFwdPreview
```

Place this immediately after the line that marks slot 0 as `SS_RESIDENT` after preload completion. (If the preload path is async, place it where the async completion fires.)

- [ ] **Step 4: Build**

Run: `./build.sh -pe`

Expected: builds clean.

- [ ] **Step 5: Exodus verify**

Reload ROM in Exodus. Position camera in OJZ such that slot 0 has been preloaded with the next section. Use:

```
mcp__exodus__emulator_read_vram(address=0xC000, length=8)
```

Expected: 4 words of plane A nametable at cols 0-3 contain valid tile indices (non-zero, matching the next section's leading column tile pattern). Compare against `Sec_sec_strips_a` ROM data for that section — first word of strip should match first word of read.

- [ ] **Step 6: Commit**

```bash
git add engine/level/section.asm
git commit -m "feat(§4.2): fire Section_CopyFwdPreview on slot 0 preload"
```

---

## Task 4: Add `Section_CopyBwdPreview` (plane A only)

**Files:**
- Modify: `engine/level/preview.asm`

- [ ] **Step 1: Add Section_CopyBwdPreview**

Append to `engine/level/preview.asm`:

```asm
; -----------------------------------------------
; Section_CopyBwdPreview — write BWD preview region of plane A.
; In:  a0 = Sec ptr (the section whose trailing PREVIEW_COLS we copy)
; Out: none
; Clobbers: d0–d3, a1–a2
; -----------------------------------------------
Section_CopyBwdPreview:
        movem.l d4-d5, -(sp)
        moveq   #PREVIEW_COLS-1, d4         ; loop 4 times
        move.w  #SECTION_TILE_WIDTH-PREVIEW_COLS, d5    ; first of last 4 src cols (= 252)
.loop:
        move.w  d5, d1                      ; src section tile col = 252..255
        move.w  d5, d0                      ;
        addi.w  #64-SECTION_TILE_WIDTH, d0  ; dest plane col: 252→60, 253→61, 254→62, 255→63
                                            ;   (since 252-256+64 = 60)
        andi.w  #$3F, d0                    ; safety: clamp to plane col 0..63
        movem.l d4-d5/a0, -(sp)
        bsr.w   Draw_TileColumn
        movem.l (sp)+, d4-d5/a0
        addq.w  #1, d5
        dbf     d4, .loop
        movem.l (sp)+, d4-d5
        rts
```

- [ ] **Step 2: Build**

Run: `./build.sh -pe`

Expected: builds clean.

- [ ] **Step 3: Commit**

```bash
git add engine/level/preview.asm
git commit -m "feat(§4.2): add Section_CopyBwdPreview (plane A)"
```

---

## Task 5: Hook `Section_CopyBwdPreview` into teleport handlers

**Files:**
- Modify: `engine/level/section.asm`

- [ ] **Step 1: Re-read Section_TeleportFwd and Section_TeleportBwd**

Run: `sed -n '205,360p' engine/level/section.asm`

Identify: in `Section_TeleportFwd`, the just-left section is what *was* slot 0 before rotation = `(Slot_Section_Map+0).b` BEFORE the `move.b d0, (a0)` that updates it. In `Section_TeleportBwd`, mirror.

- [ ] **Step 2: Add BWD preview call in Section_TeleportFwd**

In `Section_TeleportFwd`, after the slot section map updates (~line 227, after `move.b d0, 2(a0)`), add:

```asm
        ; -- §4.2: BWD preview = trailing PREVIEW_COLS of the section just
        ;    left behind. After FWD teleport, the just-left section is the
        ;    NEW slot 0 - 1 (= old slot 0). Slot R (slot 1) still holds its
        ;    art for ~85 frames until next preload, so refs resolve correctly.
        movem.l d0-d3/a0-a2, -(sp)
        lea     (Slot_Section_Map).w, a0
        moveq   #0, d2
        move.b  (a0), d2                    ; new slot 0 sec_x
        subq.b  #1, d2                      ; just-left sec_x = slot 0 - 1
        bmi.s   .skip_bwd_preview           ; no prev section (first pair)
        ; Look up the just-left section in act table
        movea.l (Current_Act_Ptr).w, a2
        ; (Section_GetSecPtr by sec_x/sec_y) — see Section_GetSlotDef pattern
        ; for now, build the Sec ptr via the act grid lookup that already exists
        moveq   #0, d3
        move.b  1(a0), d3                   ; sec_y unchanged
        ; <ENGINEER: use the existing Section_LookupByXY routine here, or copy
        ;  the index math from Section_GetSlotDef. The routine should set
        ;  a0 = Sec ptr for the (d2, d3) cell. If no such routine exists yet,
        ;  add a small helper Section_GetSecPtrXY(d2.b, d3.b, a2) → a0.>
        bsr.w   Section_GetSecPtrXY
        bsr.w   Section_CopyBwdPreview
.skip_bwd_preview:
        movem.l (sp)+, d0-d3/a0-a2
```

If `Section_GetSecPtrXY` doesn't exist, factor it out from the existing index math used inside `Section_GetSlotDef`. It's a 1-line helper.

- [ ] **Step 3: Add same call in Section_TeleportBwd**

Mirror in `Section_TeleportBwd` (line ~285): the just-left section is now `slot 1 + 1` (the section we retreated FROM).

```asm
        ; -- §4.2: BWD preview after BWD teleport — just-left section is
        ;    new slot 1 + 1 (= old slot 1). After BWD teleport, slot L
        ;    holds the new prev section, slot R holds (old slot 0)'s art.
        movem.l d0-d3/a0-a2, -(sp)
        lea     (Slot_Section_Map).w, a0
        moveq   #0, d2
        move.b  2(a0), d2                   ; new slot 1 sec_x
        addq.b  #1, d2                      ; just-left sec_x = slot 1 + 1
        ; (no clamp needed — at level end the FWD preview source instead)
        moveq   #0, d3
        move.b  3(a0), d3
        movea.l (Current_Act_Ptr).w, a2
        bsr.w   Section_GetSecPtrXY
        bsr.w   Section_CopyBwdPreview
        movem.l (sp)+, d0-d3/a0-a2
```

- [ ] **Step 4: Initial population in `Section_FillInitial`**

Find `Section_FillInitial` (line 62). After the existing slot setup, add a call to populate the BWD preview from `Sec(-1)` if it exists, or zero-fill (Task 11 will add the zero-fill helper; for now, skip the call if no Sec(-1)):

```asm
        ; -- §4.2: initial BWD preview population. At level start, Sec(-1)
        ;    doesn't exist → leave preview region empty. The camera clamp
        ;    (Task 6) will prevent BWD preview from being visible anyway.
        ;    First populated at first FWD teleport.
```

(No code change required at this step — comment is documentation only. The first BWD copy fires at first teleport.)

- [ ] **Step 5: Build**

Run: `./build.sh -pe`

Expected: builds clean.

- [ ] **Step 6: Exodus verify**

In Exodus: scroll OJZ until first FWD teleport. After teleport, read plane A at BWD preview cols 60-63:

```
mcp__exodus__emulator_read_vram(address=0xC000+60*2, length=8)
```

Expected: 4 words contain valid tile indices matching the trailing 4 cols of the section just left behind.

- [ ] **Step 7: Commit**

```bash
git add engine/level/section.asm
git commit -m "feat(§4.2): fire Section_CopyBwdPreview at every teleport"
```

---

## Task 6: Camera Clamp Toggle Rule

**Files:**
- Modify: `engine/level/camera.asm`

- [ ] **Step 1: Read existing camera_min_x logic**

Run: `sed -n '14,120p' engine/level/camera.asm`

Identify where `Camera_X` is clamped to `SLOT_ORIGIN_L` (= `$200`) on the left edge and to `SLOT_ORIGIN_R + SECTION_SIZE` on the right edge. Note the section_cur_X check pattern.

- [ ] **Step 2: Add clamp toggle**

Find the existing left-clamp logic. Replace the hardcoded `SLOT_ORIGIN_L` clamp with a conditional one based on whether `Sec(-1)` exists for the current pair:

```asm
        ; -- §4.2: camera_min_x toggles based on whether BWD preview is
        ;    accessible. At level start (slot_section_map[0] = 0) Sec(-1)
        ;    doesn't exist; clamp at SLOT_ORIGIN_L (= world col 64).
        ;    Otherwise allow camera to scroll PREVIEW_PIXELS into BWD
        ;    preview region.
        move.b  (Slot_Section_Map).w, d0    ; current slot 0 sec_x
        beq.s   .clamp_at_origin            ; sec_x = 0 → no Sec(-1)
        move.l  #(SLOT_ORIGIN_L - PREVIEW_PIXELS) << 16, d1
        bra.s   .have_min
.clamp_at_origin:
        move.l  #SLOT_ORIGIN_L << 16, d1
.have_min:
        ; <ENGINEER: existing clamp uses d1 to compare against Camera_X.
        ;  Replace the literal #SLOT_ORIGIN_L<<16 with the d1 set above.>
```

Mirror for `camera_max_x`: clamp at `SLOT_ORIGIN_R + SECTION_SIZE` only when at the act's last pair; otherwise allow `+PREVIEW_PIXELS`.

For the right edge, the equivalent check is `slot_section_map[2] == Act_grid_w - 1` (final section in last pair). If `Act_grid_w` isn't yet exposed, hardcode for OJZ (last sec_x = 8 → check `cmpi.b #8, d0`) and add a TODO comment to use the act constant once available.

- [ ] **Step 3: Build**

Run: `./build.sh -pe`

Expected: builds clean.

- [ ] **Step 4: Exodus verify**

Reload ROM. At level start: try to scroll camera left. Camera should clamp at `Camera_X = $200` (read via `mcp__exodus__emulator_read_memory(address=Camera_X)`).

Walk through to first FWD teleport. After teleport: try to scroll left. Camera should clamp at `Camera_X = $1E0` (= `$200 - 32`), allowing 4 cols of BWD preview to be visible.

- [ ] **Step 5: Commit**

```bash
git add engine/level/camera.asm
git commit -m "feat(§4.2): camera clamp toggle for BWD preview accessibility"
```

---

## Task 7: Add `Draw_BG_TileColumn` (plane B equivalent)

**Files:**
- Modify: `engine/level/plane_buffer.asm`

- [ ] **Step 1: Plan the data shape**

Plane B layout source: `Sec_sec_bg_layout(a0)` points to a 64×32 = 4096-byte raw nametable (per `engine/level/bg.asm` comments). For column N, the words are at offsets `row*128 + N*2` for `row=0..31` (since plane B is also 64×64-stride; verify by reading `engine/level/bg.asm` for the BG layout shape).

Actually plane B nametable is 64-wide stride too (the plane is 64×32 in tile rows for BG vs 64×64 for FG due to VDP setting). Confirm via:

Run: `grep -n -E "PLANE_B|VRAM_PLANE_B|\\$E000|BG_LAYOUT_SIZE" engine/level/bg.asm constants.asm`

Expected: `VRAM_PLANE_B = $E000`, `BG_LAYOUT_SIZE = 64*32*2 = 4096`. Confirms 64×32 plane B.

- [ ] **Step 2: Add `Draw_BG_TileColumn`**

Append to `engine/level/plane_buffer.asm`:

```asm
; -----------------------------------------------
; Draw_BG_TileColumn — append one tile column strip to Plane_Buffer for plane B.
; In:  d0.w = target VDP nametable column (0–63)
;      d1.w = section tile column index (0..63)
;      a0   = section def pointer (uses Sec_sec_bg_layout, Act fallback if NULL)
; Out: none (silently drops if buffer full)
; Clobbers: d0–d3, a1–a2
; Note: plane B is 64×32 tiles. Strip = 32 words; header = $8000 | (32/2 - 1) = 15.
;       Source layout is row-major 64×32 — for col N, words are at byte offsets
;       (row*128 + N*2) for row=0..31 (stride = 64 cols * 2 B = 128).
; -----------------------------------------------
Draw_BG_TileColumn:
        ; -- overflow check (entry size = 4 + 32*2 = 68 bytes) --
        move.w  (Plane_Buffer_Ptr).w, d2
        addi.w  #4 + 32*2, d2
        cmpi.w  #PLANE_BUFFER_SIZE - 2, d2
        bhi.s   .done

        ; -- get source: sec_bg_layout. Fall back to act default if NULL. --
        movea.l Sec_sec_bg_layout(a0), a1
        cmpa.w  #0, a1
        bne.s   .have_layout
        movea.l (Current_Act_Ptr).w, a2
        movea.l Act_act_bg_layout(a2), a1
        cmpa.w  #0, a1
        beq.s   .done
.have_layout:
        ; -- a1 = layout base; advance by (col * 2) to point at row 0 of col --
        move.w  d1, d3
        add.w   d3, d3
        adda.w  d3, a1

        ; -- write buffer header --
        lea     (Plane_Buffer).w, a2
        adda.w  (Plane_Buffer_Ptr).w, a2
        add.w   d0, d0
        addi.w  #VRAM_PLANE_B_BYTES & $FFFF, d0
        move.w  d0, (a2)+
        move.w  #$8000 | (32/2 - 1), (a2)+

        ; -- copy 32 words (one per row), reading column-major (stride = 128) --
        moveq   #32-1, d3
.copy:
        move.w  (a1), (a2)+
        adda.w  #128, a1
        dbf     d3, .copy

        ; -- zero terminator + buffer pointer update --
        move.w  #0, (a2)
        move.w  (Plane_Buffer_Ptr).w, d2
        addi.w  #4 + 32*2, d2
        move.w  d2, (Plane_Buffer_Ptr).w

.done:
        rts
```

- [ ] **Step 3: Build**

Run: `./build.sh -pe`

Expected: builds clean.

- [ ] **Step 4: Commit**

```bash
git add engine/level/plane_buffer.asm
git commit -m "feat(§4.2): Draw_BG_TileColumn — plane B column streaming"
```

---

## Task 8: Per-Frame BG Column Streaming

**Files:**
- Modify: `engine/level/section.asm` (`Section_QueueNewSlot1Cols`, `Section_QueueNewSlot0Cols`, or wherever per-frame columns are queued)

- [ ] **Step 1: Find the per-frame column queue path**

Run: `grep -n -E "Draw_TileColumn|Section_QueueNew" engine/level/section.asm | head -20`

Read the routines that call `Draw_TileColumn` once per leading-edge column. There are typically two paths: one for slot 1 (FWD scroll) and one for slot 0 (BWD scroll).

- [ ] **Step 2: Add corresponding `Draw_BG_TileColumn` call**

Wherever `Draw_TileColumn` is called for plane A leading-edge streaming, add a sibling call for plane B with the same `d0` (dest col) and `d1` (src col):

```asm
        bsr.w   Draw_TileColumn             ; plane A — existing
        bsr.w   Draw_BG_TileColumn          ; plane B — §4.2 unification (NEW)
```

Make this edit in both `Section_QueueNewSlot1Cols` and `Section_QueueNewSlot0Cols` (or wherever the actual streaming happens — `Section_UpdateColumns` may also call `Draw_TileColumn`).

- [ ] **Step 3: Build**

Run: `./build.sh -pe`

Expected: builds clean.

- [ ] **Step 4: Exodus verify (plane B updates incrementally)**

Reload ROM. Set Exodus to step 1 frame at a time across a section transition. Read plane B nametable (`$E000+`) at successive frames during the transition — verify a new column lands per frame, no burst rewrite of all 4096 bytes at once. Compare against pre-fix ROM behavior if available.

- [ ] **Step 5: Commit**

```bash
git add engine/level/section.asm
git commit -m "feat(§4.2): per-frame plane B column streaming"
```

---

## Task 9: Extend Preview Routines for Plane B

**Files:**
- Modify: `engine/level/preview.asm`

- [ ] **Step 1: Update `Section_CopyFwdPreview` to also copy plane B**

In `engine/level/preview.asm`, modify the `.loop` body of `Section_CopyFwdPreview`:

```asm
.loop:
        move.w  d5, d0
        move.w  d5, d1
        movem.l d4-d5/a0, -(sp)
        bsr.w   Draw_TileColumn             ; plane A (existing)
        bsr.w   Draw_BG_TileColumn          ; plane B (NEW)
        movem.l (sp)+, d4-d5/a0
        addq.w  #1, d5
        dbf     d4, .loop
```

- [ ] **Step 2: Same for `Section_CopyBwdPreview`**

Update its `.loop` body identically — `Draw_TileColumn` then `Draw_BG_TileColumn`.

- [ ] **Step 3: Build**

Run: `./build.sh -pe`

Expected: builds clean.

- [ ] **Step 4: Exodus verify**

Reload ROM. Drive camera to first FWD teleport. Read plane B BWD preview region:

```
mcp__exodus__emulator_read_vram(address=0xE000+60*2, length=8)
```

Expected: 4 valid tile indices for trailing 4 cols of just-left section's BG.

- [ ] **Step 5: Commit**

```bash
git add engine/level/preview.asm
git commit -m "feat(§4.2): preview routines write both planes"
```

---

## Task 10: Delete `BG_RedrawForSection`

**Files:**
- Modify: `engine/level/bg.asm` (delete the routine)
- Modify: `engine/level/section.asm` (remove call sites at lines 264 and 343)

- [ ] **Step 1: Remove call sites in section.asm**

In `engine/level/section.asm`, find the two `bsr.w BG_RedrawForSection` calls (lines ~264 and ~343 — verify with grep). Remove both lines and the surrounding setup blocks (`moveq #SLOT_LEFT, d0` / `movea.l (Current_Act_Ptr).w, a2` / `bsr.w Section_GetSlotDef` if they're only there for this call).

Run: `grep -n "BG_RedrawForSection" engine/level/section.asm`

Expected after edit: no matches.

- [ ] **Step 2: Delete the routine in bg.asm**

In `engine/level/bg.asm`, delete the `BG_RedrawForSection` routine (lines 67-102) and its block-comment header. Keep `BG_Init` (lines 14-65) — that's still used at level load.

Run: `grep -n "BG_RedrawForSection" engine/level/bg.asm`

Expected: no matches.

- [ ] **Step 3: Build**

Run: `./build.sh -pe`

Expected: builds clean. No undefined-symbol errors.

- [ ] **Step 4: Exodus verify — visual no-tear**

Reload ROM in Exodus. Set camera to scroll across multiple FWD teleports (recommend OJZ test layout). Frame-step through each teleport.

Expected: NO top-down sweep of plane B at teleport (the tear is gone). Plane B updates only at the leading edge per frame; teleport itself produces no plane B burst.

- [ ] **Step 5: Commit**

```bash
git add engine/level/bg.asm engine/level/section.asm
git commit -m "feat(§4.2): delete BG_RedrawForSection — plane B unified with streaming"
```

---

## Task 11: Boundary-Case Zero-Fill

**Files:**
- Modify: `engine/level/preview.asm`

- [ ] **Step 1: Add zero-fill helper**

Append to `engine/level/preview.asm`:

```asm
; -----------------------------------------------
; Section_ClearFwdPreview — zero-fill FWD preview region (no FWD neighbor case).
; Writes blank tile (index 0) to plane A + B cols 0..PREVIEW_COLS-1.
; In:   none
; Out:  none
; Clobbers: d0–d3, a1–a2
; -----------------------------------------------
Section_ClearFwdPreview:
        movem.l d4-d5, -(sp)
        moveq   #PREVIEW_COLS-1, d4
        moveq   #0, d5
.loop:
        move.w  d5, d0                      ; dest plane col
        movem.l d4-d5, -(sp)
        bsr.w   Plane_Buffer_QueueBlank_A   ; helper writes 48 zero words at plane A col d0
        bsr.w   Plane_Buffer_QueueBlank_B   ; helper writes 32 zero words at plane B col d0
        movem.l (sp)+, d4-d5
        addq.w  #1, d5
        dbf     d4, .loop
        movem.l (sp)+, d4-d5
        rts

; Section_ClearBwdPreview — same pattern, dest cols 60..63
Section_ClearBwdPreview:
        movem.l d4-d5, -(sp)
        moveq   #PREVIEW_COLS-1, d4
        move.w  #64-PREVIEW_COLS, d5
.loop_b:
        move.w  d5, d0
        movem.l d4-d5, -(sp)
        bsr.w   Plane_Buffer_QueueBlank_A
        bsr.w   Plane_Buffer_QueueBlank_B
        movem.l (sp)+, d4-d5
        addq.w  #1, d5
        dbf     d4, .loop_b
        movem.l (sp)+, d4-d5
        rts
```

- [ ] **Step 2: Add `Plane_Buffer_QueueBlank_A` and `_B` helpers**

In `engine/level/plane_buffer.asm`, append:

```asm
; -----------------------------------------------
; Plane_Buffer_QueueBlank_A — append a column of zero tiles (blank) for plane A.
; In:  d0.w = target VDP nametable column (0–63)
; Clobbers: d0–d3, a2
; -----------------------------------------------
Plane_Buffer_QueueBlank_A:
        move.w  (Plane_Buffer_Ptr).w, d2
        addi.w  #4 + STRIP_TILE_HEIGHT*2, d2
        cmpi.w  #PLANE_BUFFER_SIZE - 2, d2
        bhi.s   .done
        lea     (Plane_Buffer).w, a2
        adda.w  (Plane_Buffer_Ptr).w, a2
        add.w   d0, d0
        addi.w  #VRAM_PLANE_A & $FFFF, d0
        move.w  d0, (a2)+
        move.w  #$8000 | (STRIP_TILE_HEIGHT/2 - 1), (a2)+
        moveq   #STRIP_TILE_HEIGHT/2 - 1, d3
.fill:
        move.l  #0, (a2)+
        dbf     d3, .fill
        move.w  #0, (a2)
        move.w  (Plane_Buffer_Ptr).w, d2
        addi.w  #4 + STRIP_TILE_HEIGHT*2, d2
        move.w  d2, (Plane_Buffer_Ptr).w
.done:
        rts

; Plane_Buffer_QueueBlank_B — same for plane B (32 rows = 16 longwords)
Plane_Buffer_QueueBlank_B:
        move.w  (Plane_Buffer_Ptr).w, d2
        addi.w  #4 + 32*2, d2
        cmpi.w  #PLANE_BUFFER_SIZE - 2, d2
        bhi.s   .done
        lea     (Plane_Buffer).w, a2
        adda.w  (Plane_Buffer_Ptr).w, a2
        add.w   d0, d0
        addi.w  #VRAM_PLANE_B_BYTES & $FFFF, d0
        move.w  d0, (a2)+
        move.w  #$8000 | (16 - 1), (a2)+
        moveq   #16 - 1, d3
.fill:
        move.l  #0, (a2)+
        dbf     d3, .fill
        move.w  #0, (a2)
        move.w  (Plane_Buffer_Ptr).w, d2
        addi.w  #4 + 32*2, d2
        move.w  d2, (Plane_Buffer_Ptr).w
.done:
        rts
```

- [ ] **Step 3: Wire into Section_TeleportFwd / _Bwd at boundary**

In `Section_TeleportFwd` (and BWD mirror), where `Section_GetSecPtrXY` is called for the just-left section: if it returns null (no such section in act grid), call `Section_ClearBwdPreview` instead of `Section_CopyBwdPreview`. The exact pattern depends on `Section_GetSecPtrXY`'s null-return convention — likely `Z` flag set, or `a0 = 0`.

```asm
        bsr.w   Section_GetSecPtrXY
        cmpa.w  #0, a0
        beq.s   .clear_bwd
        bsr.w   Section_CopyBwdPreview
        bra.s   .bwd_done
.clear_bwd:
        bsr.w   Section_ClearBwdPreview
.bwd_done:
```

Similarly hook `Section_ClearFwdPreview` into the slot-0-preload path (Task 3) for cases where the next-FWD section doesn't exist (last pair).

- [ ] **Step 4: Build**

Run: `./build.sh -pe`

Expected: builds clean.

- [ ] **Step 5: Exodus verify**

Drive camera to act's last pair (OJZ has 9 sections; last pair is sections 7+8). Try to scroll right past the last section. Camera should clamp; FWD preview region should be zero-filled (read VRAM at $C000 cols 0-3 expected to be all zeros).

- [ ] **Step 6: Commit**

```bash
git add engine/level/preview.asm engine/level/plane_buffer.asm engine/level/section.asm
git commit -m "feat(§4.2): zero-fill preview at act boundaries"
```

---

## Task 12: Update Architecture Doc

**Files:**
- Modify: `docs/ENGINE_ARCHITECTURE.md`

- [ ] **Step 1: §4.1 step 2 — add preview specifics**

Find the "Preview columns/rows copied at boundary edges" line (around line 1820) and append:

```markdown
2. Preview columns/rows copied at boundary edges for seamless visual transition.
   Width = 4 cols (`PREVIEW_COLS`) / 4 rows (`PREVIEW_ROWS`). Preview cells reference
   resident slot art; no extra VRAM allocated. Copies fire on source-section preload
   completion (FWD) and at every teleport (BWD). Per-section content via dedicated
   routines `Section_CopyFwdPreview` / `_CopyBwdPreview` in `engine/level/preview.asm`.
   Vertical and diagonal preview routines stubbed for vertical-streaming follow-up.
```

- [ ] **Step 2: §4.4 — add no-BG-burst policy**

In §4.4 Deferred Plane Buffer, append a paragraph:

```markdown
**Plane B never writes during active display.** The legacy `BG_RedrawForSection` burst
(direct VDP pokes for ~25-30k cycles at section transition) is removed. Plane B uses
per-frame streaming (`Draw_BG_TileColumn` paired with `Draw_TileColumn` at every
leading-edge column write) plus preview copies at teleport. All plane B writes go
through the deferred plane buffer + DMA queue — same path as plane A. Eliminates the
top-down tear at teleport by construction.
```

- [ ] **Step 3: §4.5 (or wherever camera clamps live) — add toggle rule**

Find the camera-clamp section in §4.5 and append:

```markdown
**Preview-aware clamp toggle (§4.2):**
- `camera_min_x = $200` (= world col 64) when at level start (`section_cur_X = 0`,
  no Sec(-1) neighbor)
- `camera_min_x = $1E0` (= world col 60) for any post-teleport pair, allowing camera
  to scroll into the BWD preview region
- Mirrored at `camera_max_x` for the level's final pair
- Re-clamps to `$200` if BWD-teleport returns to `section_cur_X = 0`
```

- [ ] **Step 4: Commit**

```bash
git add docs/ENGINE_ARCHITECTURE.md
git commit -m "docs(§4.2): update architecture doc with preview specifics"
```

---

## Task 13: Long-Run Soak + Merge

**Files:** none (verification + merge only)

- [ ] **Step 1: Long-run Exodus soak**

Reload ROM. Drive camera through 20 sections (10 teleports). Use Exodus screen-record or step manually. Confirm:
- No visible warp / shuffle / tear at any teleport
- DMA queue not overflowing (`mcp__exodus__emulator_read_memory` at the queue pointers)
- No frame-time growth (Exodus profiler)

- [ ] **Step 2: BWD travel verification**

Reverse direction near a teleport boundary. Camera should scroll into BWD preview cleanly (no artifacts), then BWD-teleport. After BWD teleport, FWD scroll continues normally with FWD preview repopulated.

- [ ] **Step 3: Boundary-case verification**

Test at level start (try to scroll left, camera clamps at `$200`) and level end (try to scroll right past last section, camera clamps + FWD preview zero-filled).

- [ ] **Step 4: Watchpoint regression — `BG_RedrawForSection`**

Set Exodus watchpoint on the deleted routine's old address (or simply confirm the symbol no longer exists in the binary):

```bash
strings s4.bin | grep -i "BG_RedrawForSection" || echo "OK: symbol removed"
```

Expected: "OK: symbol removed".

- [ ] **Step 5: Merge to master**

```bash
git checkout master
git merge --no-ff feat/section-42-preview-zone -m "Merge §4.2 preview-zone — fixes teleport warp on both planes"
```

- [ ] **Step 6: Tag merge for rollback safety**

```bash
git tag -a checkpoint/post-section-42-preview-zone -m "§4.2 preview-zone merged: plane A + plane B unified streaming, BG_RedrawForSection deleted"
```

- [ ] **Step 7: Update memory**

Update `MEMORY.md` entry `project_section_42_preview_zone_brainstorm.md` (or supersede with a new "section 42 complete" entry):

```bash
# (Inline edit via Claude — replace the in-progress entry with a "complete" one
#  noting which deferred items remain.)
```

---

## Self-Review Notes

- **Spec coverage:**
  - Plane A FWD preview → Tasks 2, 3
  - Plane A BWD preview → Tasks 4, 5
  - Plane B unification → Tasks 7, 8, 9, 10
  - Camera clamp toggle → Task 6
  - Boundary cases → Task 11
  - Doc updates → Task 12
  - Testing & verification → Tasks 3, 5, 6, 8, 9, 10, 11, 13
- **Deferred items match spec:** vertical/diagonal preview stubs (not in plan); landing-flag (out of scope); SECTION_SHIFT reconcile (out of scope) — all flagged in spec, not in this plan.
- **Type/name consistency check:** `Section_CopyFwdPreview` / `Section_CopyBwdPreview` / `Section_ClearFwdPreview` / `Section_ClearBwdPreview` / `Draw_BG_TileColumn` / `Plane_Buffer_QueueBlank_A` / `_B` — used consistently across tasks.
- **Helper required:** `Section_GetSecPtrXY` (Task 5) — factored from existing `Section_GetSlotDef` index math during implementation. If it's missing, add it as a small helper in `section.asm` rather than blocking on a separate refactor.
