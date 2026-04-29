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

## Task 5: Defer cold-loads to mid-traversal + hook `Section_CopyBwdPreview` at teleport

This task replaces the original Task 5 plan. The original assumed slot 1's art persists across teleport, which it doesn't — the cold-load at `Section_TeleportFwd` (line 262) and `Section_TeleportBwd` (line 341) overwrite it immediately. Verified empirically: `data/generated/ojz/act1/sec_vram_bases.asm` shows Sec1 and Sec3 share `OJZ_SEC*_VRAM = 0 * 32` (color 1).

**Fix: defer the cold-loads to mid-traversal of the new pair's first section.** This keeps the just-left section's art in slot VRAM for ~85 frames post-teleport — long enough for BWD preview (FWD teleport) and FWD preview (BWD teleport) to be valid and visible. The architecture doc §4.1 already specifies "Camera crosses midpoint of current section → preload next section into the behind slot" — this aligns the code with that.

**New thresholds added to `constants.asm`:**
- `SECTION_DEFERRED_FWD_LOAD = $0600` (slot 0 midpoint going RIGHT post-FWD-teleport)
- `SECTION_DEFERRED_BWD_LOAD = $0C00` (slot 1 quarter-point going LEFT post-BWD-teleport)

**Files:**
- Modify: `constants.asm` (add 2 thresholds + 2 preload-flag bits)
- Modify: `engine/level/section.asm` (remove cold-loads, add deferred triggers, add BWD preview hooks)
- Modify: `ram.asm` (verify `Section_Preload_Flags` has room for 2 new bits — likely already a byte)

- [ ] **Step 1: Add new threshold constants and flag bits**

In `constants.asm`, near the existing `SECTION_FWD_PRELOAD` / `SECTION_BWD_PRELOAD` definitions (lines ~225-226), add:

```asm
SECTION_DEFERRED_FWD_LOAD = $0600   ; camera X → fire deferred Sec_R load (slot 0 midpoint, post-FWD-teleport)
SECTION_DEFERRED_BWD_LOAD = $0C00   ; camera X → fire deferred Sec_L load (slot 1 quarter, post-BWD-teleport)
```

Then locate the `SPF_FWD_PRELOADED` / `SPF_BWD_PRELOADED` bit definitions (search `grep -n "SPF_" constants.asm`) and add two new bits adjacent:

```asm
SPF_DEFERRED_FWD_LOAD = 2   ; deferred slot 1 cold-load pending after FWD teleport
SPF_DEFERRED_BWD_LOAD = 3   ; deferred slot 0 cold-load pending after BWD teleport
```

(Choose the next free bit indices — read existing SPF_* bits to confirm 2 and 3 are unused.)

- [ ] **Step 2: Add `Section_GetSecPtrXY` helper**

In `engine/level/section.asm`, after `Section_GetSlotDef` (line 74), add a helper that takes (sec_x in d2.b, sec_y in d3.b, act ptr in a2) and returns Sec ptr in a0. This is the same index math `Section_GetSlotDef` uses, factored out:

```asm
; -----------------------------------------------
; Section_GetSecPtrXY — Sec ptr lookup by grid coordinates.
; In:  d2.b = sec_x, d3.b = sec_y, a2 = Act ptr
; Out: a0 = Sec ptr; Z flag clear if found, Z set if out of range (a0 = 0)
; Clobbers: d0, d1
; -----------------------------------------------
Section_GetSecPtrXY:
        moveq   #0, d0
        cmp.b   Act_grid_w+1(a2), d2
        bge.s   .out_of_range
        cmp.b   Act_grid_h+1(a2), d3
        bge.s   .out_of_range
        ; flat section_id = sec_y * grid_w + sec_x
        move.b  d3, d0
        moveq   #0, d1
        move.b  Act_grid_w+1(a2), d1
        ; OJZ is single-row: grid_h = 1, so section_id = sec_x. We assume
        ; OJZ-style 1-row layout for now; multi-row Y math handled by build tool.
        ; (For 1-row: section_id = sec_x; the multiply is a placeholder for future.)
        moveq   #0, d0
        move.b  d2, d0
        ; compute Sec ptr = sec_grid_ptr + section_id * Sec_len ($48 = 72)
        movea.l Act_sec_grid_ptr(a2), a0
        move.w  d0, d1
        lsl.w   #6, d0          ; sec * 64
        lsl.w   #3, d1          ; sec * 8
        add.w   d1, d0          ; sec * 72
        adda.w  d0, a0
        moveq   #1, d0          ; Z flag clear (success)
        rts
.out_of_range:
        suba.l  a0, a0          ; a0 = 0
        moveq   #0, d0          ; Z flag set
        rts
```

(Note: this assumes 1-row act layout per the comment. If `Act_grid_h` > 1, the multiply for `sec_y * grid_w` needs to be added — the existing engine doesn't have multi-row sections yet, so we defer that.)

- [ ] **Step 3: Remove the cold-load fallbacks at teleport**

In `Section_TeleportFwd` (line ~253-256), remove the `.fwd_cold_load` block:

```asm
        ; DELETE THESE LINES:
.fwd_cold_load:
        move.l  a0, -(sp)
        bsr.w   Section_LoadArt
        movea.l (sp)+, a0
```

Replace the `cmpi.b #SS_IDLE, d0 / beq.s .fwd_cold_load` block (lines ~248-250) with: if SS_IDLE, set the deferred-load flag and skip the load:

```asm
        cmpi.b  #SS_IDLE, d0
        bne.s   .mark_resident
        ; -- §4.2: deferred cold-load — slot 1 stays stale (just-left
        ;    section's art) until camera passes Sec_L midpoint, keeping
        ;    BWD preview valid. Fire bset and let .deferred_fwd_load
        ;    handle it later.
        bset    #SPF_DEFERRED_FWD_LOAD, (Section_Preload_Flags).w
        bra.s   .fwd_redraw_bg
.mark_resident:
        move.b  #SS_RESIDENT, (a1, d6.w)
        bra.s   .fwd_redraw_bg
```

Mirror the same change in `Section_TeleportBwd` (line ~330-345): remove `.bwd_cold_load`, set `SPF_DEFERRED_BWD_LOAD` if SS_IDLE.

- [ ] **Step 4: Add deferred-load triggers in Section_Check**

In `Section_Check` (line ~109), after the existing preload checks at `.fwd_preload_check` and `.bwd_preload_check` blocks (lines ~120-131), add new threshold checks for the deferred loads.

Replace the threshold-check block (lines 113-118) with:

```asm
        ; -- preload triggers (§2 A.4) — fire BEFORE teleport thresholds --
        cmpi.w  #SECTION_FWD_PRELOAD, d0
        bge.s   .fwd_preload_check
        cmpi.w  #SECTION_BWD_PRELOAD, d0
        ble.s   .bwd_preload_check
        ; -- §4.2 deferred load triggers --
        cmpi.w  #SECTION_DEFERRED_FWD_LOAD, d0
        bge.s   .deferred_fwd_check
        cmpi.w  #SECTION_DEFERRED_BWD_LOAD, d0
        ble.s   .deferred_bwd_check
        bra.s   .threshold_check
```

Then add the new check blocks after the existing preload checks (around line 131):

```asm
.deferred_fwd_check:
        btst    #SPF_DEFERRED_FWD_LOAD, (Section_Preload_Flags).w
        beq.s   .threshold_check
        bsr.w   .deferred_fwd_load
        bclr    #SPF_DEFERRED_FWD_LOAD, (Section_Preload_Flags).w
        bra.s   .threshold_check

.deferred_bwd_check:
        btst    #SPF_DEFERRED_BWD_LOAD, (Section_Preload_Flags).w
        beq.s   .threshold_check
        bsr.w   .deferred_bwd_load
        bclr    #SPF_DEFERRED_BWD_LOAD, (Section_Preload_Flags).w
```

And add the implementation routines below `.preload_bwd` (line ~186):

```asm
.deferred_fwd_load:
        ; Stream slot 1's section into VRAM via async DMA. By Sec_L midpoint
        ; ($0600), camera is past BWD-preview-visible window, so overwriting
        ; the just-left section's art is safe.
        moveq   #SLOT_RIGHT, d0
        movea.l (Current_Act_Ptr).w, a2
        bsr.w   Section_GetSlotDef          ; a0 = Sec ptr for slot 1
        moveq   #0, d6
        move.b  (Slot_Section_Map+2).w, d6  ; slot 1 flat section_id
        ; copy a0 to a4 for Section_StreamArtGroup convention
        movea.l a0, a4
        bra.w   Section_StreamArtGroup

.deferred_bwd_load:
        ; Mirror for BWD: stream slot 0's section. By slot 1 quarter-point
        ; ($0C00), FWD preview no longer visible.
        moveq   #SLOT_LEFT, d0
        movea.l (Current_Act_Ptr).w, a2
        bsr.w   Section_GetSlotDef          ; a0 = Sec ptr for slot 0
        moveq   #0, d6
        move.b  (Slot_Section_Map).w, d6    ; slot 0 flat section_id
        movea.l a0, a4
        bra.w   Section_StreamArtGroup
```

- [ ] **Step 5: Add BWD preview call in Section_TeleportFwd**

After the slot section map updates in `Section_TeleportFwd` (~line 227, after `move.b d0, 2(a0)`), add:

```asm
        ; -- §4.2: BWD preview = trailing PREVIEW_COLS of the just-left section.
        ;    With deferred Sec_R load (Step 3), slot 1's old art persists past
        ;    teleport — refs resolve correctly until SECTION_DEFERRED_FWD_LOAD
        ;    fires at $0600. Skip if at level start (no prev section).
        movem.l d0-d3/a0-a2, -(sp)
        lea     (Slot_Section_Map).w, a0
        moveq   #0, d2
        move.b  (a0), d2                    ; new slot 0 sec_x
        subq.b  #1, d2                      ; just-left sec_x = new slot 0 - 1
        bmi.s   .skip_bwd_preview
        moveq   #0, d3
        move.b  1(a0), d3                   ; sec_y unchanged
        movea.l (Current_Act_Ptr).w, a2
        bsr.w   Section_GetSecPtrXY
        beq.s   .skip_bwd_preview
        bsr.w   Section_CopyBwdPreview
.skip_bwd_preview:
        movem.l (sp)+, d0-d3/a0-a2
```

- [ ] **Step 6: Add FWD preview call in Section_TeleportBwd**

Mirror in `Section_TeleportBwd` (~line 308, after slot map updates): the just-left section is the section we retreated from. After BWD teleport, FWD preview cells (currently containing post-rewrite or stale data) need to be rewritten with the just-left section's leading 4 cols, since plane wraparound now maps those cells to "world cols beyond the new pair's right edge."

Wait — re-derive: after BWD teleport, plane cols 576-579 in NEW world coords correspond to "right of new slot 1" = "section AFTER new slot 1" = the just-left section. So FWD preview should reference just-left section's leading cols.

```asm
        ; -- §4.2: FWD preview after BWD teleport = leading PREVIEW_COLS of
        ;    the just-left section (now to the right in world coords). Slot 0's
        ;    art is preserved (deferred load) so refs resolve correctly.
        movem.l d0-d3/a0-a2, -(sp)
        lea     (Slot_Section_Map).w, a0
        moveq   #0, d2
        move.b  2(a0), d2                   ; new slot 1 sec_x
        addq.b  #1, d2                      ; just-left sec_x = new slot 1 + 1
        moveq   #0, d3
        move.b  3(a0), d3
        movea.l (Current_Act_Ptr).w, a2
        bsr.w   Section_GetSecPtrXY
        beq.s   .skip_fwd_preview
        bsr.w   Section_CopyFwdPreview
.skip_fwd_preview:
        movem.l (sp)+, d0-d3/a0-a2
```

- [ ] **Step 7: Build**

Run: `cd /home/volence/sonic_hacks/s4_engine && ./build.sh -pe`

Expected: builds clean.

- [ ] **Step 8: Exodus verify**

Reload ROM. Drive camera through first FWD teleport in OJZ.

After teleport, **before** camera reaches `$0600`:
- Read plane A at BWD preview cols 60-63: `mcp__exodus__emulator_read_vram(address=0xC000+60*2, length=8)`. Expect: tile indices matching Sec0's last 4 cols (the just-left section). Reference: read `Sec_sec_strips_a[0]` for Sec0, take last 4 cols' first words.
- Verify slot 1 VRAM still holds Sec1's art (read tile bytes at color-1 region: `mcp__exodus__emulator_read_vram(address=0, length=64)`). Should be Sec1's first tile pattern, not Sec3's.

After camera passes `$0600`:
- Read slot 1 VRAM again. Should now be Sec3's art (deferred load fired and DMA drained).
- BWD preview cells unchanged (still Sec0 trailing refs), but offscreen now.

- [ ] **Step 9: Commit**

```bash
cd /home/volence/sonic_hacks/s4_engine
git add constants.asm engine/level/section.asm
git commit -m "feat(§4.2): defer cold-loads to mid-traversal + BWD preview hooks"
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
