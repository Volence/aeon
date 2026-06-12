# Visibility-Derived Entity Window (§4.9.5) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The entity window tracks the sections the camera's despawn envelope actually overlaps, making entity preview at seams and teleport continuity correct by construction in all directions.

**Architecture:** Replace `EntityWindow_BuildEntries`' slot-pair derivation with a camera-envelope derivation anchored on **absolute section coordinates**; window changes become *slides* (camera crossing a margin boundary, with generic mask migration by section identity) and teleports become *coordinate re-expressions* (shift all entities + forced re-init with same-section mask preservation — the keep-window code is deleted). Spec: `docs/superpowers/specs/2026-06-11-visibility-window-preview-entities-design.md`.

**Tech Stack:** AS Macro Assembler (68000), Exodus MCP verification. Build `./build.sh`. Branch: continue on `vertical-entity-window`.

---

## Current-state facts (verified 2026-06-11, HEAD 443e0e2)

- `engine/objects/entity_window.asm` (~1280 lines): `EntityWindow_BuildEntries` derives 4 entries from `Slot_Section_Map` (entry = slot&1 × row r + entry>>1); `EntityWindow_Scan` has the coarse-Y re-scan trigger; `EntityWindow_TeleportShift`/`TeleportShiftY` have keep-window shift/despawn loops + `clearLoadedRing`/`clearLoadedObj` macro sites + no-op migration comment tables; `EntityWindow_RebuildScanState` = UpdateCenter → BuildEntries → Camera_Y_Coarse_Prev rebase → populate loop.
- `EntityWindow_InitSection` compare-clears an entry's 32-byte `Entity_Loaded_Masks` slot iff `ess_section_id` changes; writes both origins; clears all four scan indices unconditionally.
- `Section_GetSecPtrXY` (engine/level/section.asm): d2.b=sec_x, d3.b=sec_y, a2=Act ptr → a0 (Z set + a0=0 when out of range, **unsigned** compares — a "negative" byte like $FF fails the range check, which voids derived out-of-grid cells for free).
- `Section_FlatIDXY`: d2/d3/a2 → d0.w flat id (clobbers d1).
- Teleport handlers (`Section_TeleportFwd/Bwd/Down/Up`, section.asm ~350-610) rebase Camera/Player FIRST, update `Slot_Section_Map` (pair columns ±2 / `sec_y ±= 2`), then call `EntityWindow_TeleportShift(Y)` with d0 = ±SECTION_SHIFT. Signs: FWD/DOWN pass −SECTION_SHIFT, BWD/UP pass +SECTION_SHIFT (verified Task 6).
- Constants: `SECTION_SIZE = $800`, `SLOT_ORIGIN_L/U = $200`, `ENTITY_DESPAWN_BUFFER = $200`, `ENTITY_DESPAWN_BUFFER_Y = $180`, `ENTITY_LOADED_SLOT_SIZE = 32`, `MAX_TRACKED_SECTIONS = 4`, `SEC_VOID = $FF`, `ENTITY_RESCAN_COARSE_MASK = $FF80`.
- Test fixtures + editor pipeline: entity data generates from `data/editor/ojz/act1/section_N.{rings,objects}.json` via `tools/ojz_entity_gen.py` (runs inside `ojz_strip_gen.py generate`). Edit JSONs, rebuild, data regenerates.
- **Concurrent-session caution still applies:** `build.sh`, `data/levels/ojz/act1/act_descriptor.asm`, `project.json`, parallax/bg files are dirty from another session — never modify or `git add` them. Explicit-path `git add` only.

## The key derivation (worked out in design — implementers: trust but verify the worked examples)

```
col0 = (camX − SLOT_ORIGIN_L − ENTITY_DESPAWN_BUFFER)   asr SECTION_SIZE_SHIFT   ; arithmetic shift = floor, negative-safe
row0 = (camY − SLOT_ORIGIN_U − ENTITY_DESPAWN_BUFFER_Y) asr SECTION_SIZE_SHIFT
anchor (absolute) : sec_x0 = slot0_sec_x + col0 ;  sec_y0 = slot0_sec_y + row0
window            : sections (sec_x0+{0,1}, sec_y0+{0,1})    ; entries 0=UL 1=UR 2=LL 3=LR
entry origins     : x = SLOT_ORIGIN_L + (col0+{0,1})·SECTION_SIZE   (signed word; may be −$600, $200, $A00, $1200)
                    y = SLOT_ORIGIN_U + (row0+{0,1})·SECTION_SIZE
```

Why the anchor makes teleports trivial: a FWD rebase changes camX by −$1000 (col0 −2) and advances slot0_sec_x by +2 — **sec_x0 is invariant**. Same sections, same entry assignments, only origins re-express. Worked example: camX $11FF, slot0=n → col0 = ($11FF−$400)>>11 = 1 → window cols (n+1, n+2), origins ($A00, $1200). Post-teleport camX $1FF, slot0=n+2 → col0 = (−$201)>>11 = −1 → window cols (n+1, n+2), origins (−$600, $200). Identical sections. Slides are the ONLY time entry↔section assignments change.

Envelope spans: X = 320+2×$200 = 1344 < 2048; Y = 224+2×$180 = 976 < 2048 → always ≤2×2. The despawn envelope (not the load band) is used so every live windowed entity's section is always tracked.

---

### Task 1: Research, object-state audit, convention documentation

**Files:**
- Modify: `CODING_CONVENTIONS.md` (object-authoring rules section — find the appropriate section by reading the file's structure)
- Modify: `docs/ENGINE_ARCHITECTURE.md` (§3 object system — object authoring rules)

- [ ] **Step 1: Audit all object code for unshifted absolute coordinates.** Read every file in `objects/` (test_static, test_animated, test_player, test_enemy, test_solid, test_particle, test_emitter, test_parent, test_stress_emitter) and `engine/objects/children.asm`. For each: does it store an absolute world coordinate anywhere other than `SST_x_pos`/`SST_y_pos` (in `sst_custom` fields, or computed targets)? Patrol anchors, spawn-position stashes, emitter targets are the suspects. Record findings per object. (Prediction from design: test_enemy patrols by counter — safe; verify. Children store parent-relative offsets — safe; verify.) If a violation EXISTS, flag it in your report and fix it by converting to relative/derived state — with the fix as its own commit.

- [ ] **Step 2: Document the convention.** Add to `CODING_CONVENTIONS.md` (matching its rule style) and the object-authoring part of `docs/ENGINE_ARCHITECTURE.md` §3:

```markdown
**No unshifted absolute coordinates in object state.** Teleport rebases shift
`SST_x_pos`/`SST_y_pos` for every slot-tagged object but cannot see absolute
world coordinates stored in `sst_custom` (patrol anchors, waypoint targets,
"return home" positions) — those go stale by ±SECTION_SHIFT at a seam and the
object lurches. Keep positional state relative (offsets, counters, velocities)
or re-derivable from the ROM placement. An object that genuinely needs a stored
absolute coordinate must register it for teleport shifting (design the mechanism
when the need first arises — likely a per-ObjDef shift mask of custom longwords).
```

- [ ] **Step 3: Re-verify the worked derivation examples** against current constants (SECTION_SIZE really $800, despawn buffers really $200/$180, teleport rebase really $1000, slot map advance really ±2 — all in constants.asm + section.asm). If ANY differs, STOP and report — the whole plan's math rests on these.

- [ ] **Step 4: Commit**

```bash
git add CODING_CONVENTIONS.md docs/ENGINE_ARCHITECTURE.md
git commit -m "docs: no-unshifted-absolute-coordinates object convention + audit results"
```
(Plus the separate fix commit from Step 1 if a violation was found.)

---

### Task 2: Derivation core — DeriveWindow + BuildEntries rework + anchor RAM

**Files:**
- Modify: `constants.asm` (SECTION_SIZE_SHIFT + guard, near SECTION_SIZE)
- Modify: `ram.asm` (anchor word, near Entity_Window_Active)
- Modify: `engine/objects/entity_window.asm` (`EntityWindow_BuildEntries`, new `EntityWindow_DeriveWindow`, `EntityWindow_Init`)

- [ ] **Step 1: Constants + RAM.**

constants.asm, directly under SECTION_SIZE:
```asm
SECTION_SIZE_SHIFT      = 11            ; log2(SECTION_SIZE) — derivation shift
    if SECTION_SIZE <> (1<<SECTION_SIZE_SHIFT)
      error "SECTION_SIZE_SHIFT out of sync with SECTION_SIZE"
    endif
```

ram.asm, after `Entity_Window_Active`/`Entity_Window_Center_ID`:
```asm
Entity_Window_Anchor:   ds.b 2          ; absolute (sec_x0, sec_y0) of entry 0 — slide trigger + teleport invariance
```

- [ ] **Step 2: New `EntityWindow_DeriveWindow`** (before BuildEntries):

```asm
; -----------------------------------------------
; EntityWindow_DeriveWindow — absolute window anchor from the camera envelope
;
; The tracked 2×2 = the sections overlapped by the camera's DESPAWN envelope
; (the widest band), so any live windowed entity's section is always tracked.
; Envelope spans < SECTION_SIZE on both axes → always exactly 2 cols × 2 rows.
;
; Out: d2.b = sec_x0 (slot0 sec_x + col0 — may be "negative"/past-grid; the
;             grid range check voids such cells downstream)
;      d3.b = sec_y0
;      d4.w = col0 (signed — entry origin derivation needs it)
;      d5.w = row0 (signed)
; Clobbers: d0
; -----------------------------------------------
EntityWindow_DeriveWindow:
        move.w  (Camera_X).w, d4
        subi.w  #SLOT_ORIGIN_L+ENTITY_DESPAWN_BUFFER, d4
        moveq   #SECTION_SIZE_SHIFT, d0
        asr.w   d0, d4                  ; d4 = col0 (floor — asr is negative-safe)
        move.w  (Camera_Y).w, d5
        subi.w  #SLOT_ORIGIN_U+ENTITY_DESPAWN_BUFFER_Y, d5
        asr.w   d0, d5                  ; d5 = row0
        move.b  (Slot_Section_Map).w, d2        ; slot0 sec_x
        add.b   d4, d2                  ; d2 = sec_x0 (byte wrap OK — range check voids)
        move.b  (Slot_Section_Map+1).w, d3      ; slot0 sec_y
        add.b   d5, d3                  ; d3 = sec_y0
        rts
```

- [ ] **Step 3: Rework `EntityWindow_BuildEntries`** to consume the derived window. Replace the slot/row-offset geometry block with anchor-based geometry; keep the existing void-stamp, InitSection call, ClaimSlot, and validity-mask structure intact (read the current routine first — only the section/origin computation changes):

```asm
; -----------------------------------------------
; EntityWindow_BuildEntries — (re)configure the 4 entries from the camera
; envelope (visibility-derived window — see spec 2026-06-11).
;
; Quadrants: entry 0 = (sec_x0, sec_y0) … entry 3 = (sec_x0+1, sec_y0+1).
; Stores the absolute anchor in Entity_Window_Anchor (slide trigger +
; teleport-invariance checks read it).
;
; In:  none (reads Camera_X/Y, Slot_Section_Map, Current_Act_Ptr)
; Out: Entity_Window_Active = validity mask; Entity_Window_Anchor updated
; Clobbers: d0-d7, a0-a5
; -----------------------------------------------
EntityWindow_BuildEntries:
        bsr.w   EntityWindow_DeriveWindow       ; d2/d3 = anchor, d4/d5 = col0/row0
        move.b  d2, (Entity_Window_Anchor).w
        move.b  d3, (Entity_Window_Anchor+1).w
        ; precompute origin bases: d4 = SLOT_ORIGIN_L + col0*SECTION_SIZE (signed)
        moveq   #SECTION_SIZE_SHIFT, d0
        asl.w   d0, d4
        addi.w  #SLOT_ORIGIN_L, d4              ; d4 = origin_x of column 0
        asl.w   d0, d5
        addi.w  #SLOT_ORIGIN_U, d5              ; d5 = origin_y of row 0
        movem.w d2-d5, -(sp)                    ; anchor + origin bases (8 bytes)

        lea     (Entity_Scan_State).w, a3
        moveq   #0, d7                  ; validity mask
        moveq   #0, d6                  ; entry index

.entry_loop:
        ; entry geometry from the saved anchor/bases
        move.w  (sp), d2                ; sec_x0 (movem.w sign-extends — take low byte)
        move.w  2(sp), d3               ; sec_y0
        move.w  d6, d0
        andi.w  #1, d0
        add.b   d0, d2                  ; sec_x = sec_x0 + (entry & 1)
        move.w  d6, d1
        lsr.w   #1, d1
        add.b   d1, d3                  ; sec_y = sec_y0 + (entry >> 1)
        movea.l (Current_Act_Ptr).w, a2
        bsr.w   Section_GetSecPtrXY     ; Z set = out of grid (handles "negative" bytes too)
        beq.s   .void_entry

        bsr.w   Section_FlatIDXY        ; d0.w = flat id
        move.w  d0, d1                  ; d1.b = section_id

        ; origins: base + (entry bit)·SECTION_SIZE
        move.w  (sp)+, d0               ; (sp adjust trick NOT used — see note) 
        ; --- implementer note: read origins from the stack frame WITHOUT popping:
        move.w  4+0(sp), d0             ; ADJUST: with the movem.w frame, origin_x base is at +4
        ; The exact stack offsets depend on the movem order — compute them from
        ; YOUR movem.w register list and document them in a comment, or use two
        ; scratch RAM words instead of the stack if that reads cleaner. The
        ; REQUIRED semantics: origin_x = base_x + (entry&1 ? SECTION_SIZE : 0),
        ; origin_y = base_y + (entry>>1 ? SECTION_SIZE : 0), passed to
        ; InitSection in d0/d2 exactly as today, d1 = section_id, d6 = entry.
        ; (Code shape continues as in the current routine: InitSection call,
        ;  ClaimSlot under movem protection, bset d6,d7, loop, store mask.)
```

**Implementer latitude:** the stack-frame juggling above is the one place the plan doesn't dictate exact instructions — derive clean register/stack usage from the current routine's shape (it already movem-protects around ClaimSlot). Semantics are fully specified; keep the existing `.void_entry` stamp (SEC_VOID + entry_idx) and `Entity_Window_Active` mask write verbatim. If you prefer two scratch words in RAM (`Entity_Window_OriginX/Y` next to the anchor) over stack offsets, that's acceptable — document the choice.

- [ ] **Step 4: `EntityWindow_Init`** — remove the now-redundant slot-pair-specific anything (it already just calls BuildEntries; verify) and ensure the anchor is initialized before the first Scan (BuildEntries stores it). The cold-clear block must also clear `Entity_Window_Anchor` (add 2 bytes to the cleared range or clear explicitly — the first BuildEntries overwrites it anyway; explicit clear documents intent).

- [ ] **Step 5: Build + boot regression.** `./build.sh` clean. Exodus: reload + symbols. At boot (camX ~$260, camY ~$290): col0 = ($260−$400)>>11 = −1?? **Compute the real expectation:** $260−$400 = −$1A0 → asr 11 → −1 → window cols (slot0−1, slot0) = (−1=void, 0) — *different from the old window* (old: sections 0,1 tracked; new: void,0 columns!). Verify: `Entity_Window_Active` reflects it (entries 0/2 void → mask $0A), section ids = (VOID, 0, VOID, 3), `Ring_Count` = 7 still (sec0's rings — sec1's were never in the envelope... old behavior loaded sec1 rings into the buffer ratchet! Boot Ring_Count may drop vs the old window if sec1 rings were previously in-window. Compute from data: sec1 rings at engine $B00-$C00 — old window tracked sec1 and its ratchet covered... camX $260 + screen + LOAD buffer = $260+320+$180 = $660 < $B00 → ratchet never reached them → Ring_Count 7 both ways ✓). Expect mask **$0A** (entries 1/3 valid: column slot0 at cols offset +1), entry1 = section 0 at origin $200, entry3 = section 3 at origin Y $A00. **The window is correct but SHIFTED in entry numbering vs the old build — update any stale expectations.**
- Drive right to camX $500: col0 = ($100)>>11 = 0 → slide fires → entries = sections (0,1,3,4) mask $0F. Drive to camX $E00 (preview zone): col0 = ($A00)>>11 = 1 → entries = (1,2,4,5): **section 2 tracked at origin $1200 = the FWD preview, live** (its rings spawn when the ratchet/band reach them).
- NOTE: slides don't exist until Task 3 — for THIS task's verification, force re-derivation by reloading ROM with Player_1 start positions written immediately after reset, or temporarily verify via `EntityWindow_Init`-time positions only (boot-position checks). Full slide verification is Task 3's job. Verify at boot position only, then commit.

- [ ] **Step 6: Commit**

```bash
git add constants.asm ram.asm engine/objects/entity_window.asm
git commit -m "feat(entity-window): visibility-derived window core — envelope anchor derivation in BuildEntries"
```

---

### Task 3: Slide trigger + mask migration + recenter move + slide populate

**Files:**
- Modify: `engine/objects/entity_window.asm` (`EntityWindow_Scan`, new `EntityWindow_CheckSlide` + `EntityWindow_MigrateMasks`, `EntityWindow_RebuildScanState`)

- [ ] **Step 1: New `EntityWindow_MigrateMasks`** — generic identity-match migration. Called with a snapshot of the OLD entry section ids; after BuildEntries reassigns entries, copy each surviving section's 32-byte mask from its old entry slot to its new one:

```asm
; -----------------------------------------------
; EntityWindow_MigrateMasks — move loaded masks to sections' new entries
;
; In:  a4 = snapshot: 4 bytes old section ids + 4×32 bytes old masks
;      (stack or scratch buffer — caller builds it BEFORE BuildEntries)
; Generic identity match: for each NEW entry, find its section in the old
; snapshot; copy the 32-byte mask. New sections keep the compare-clear's
; zeroed mask. Handles any slide direction including (asserted-impossible)
; diagonal slides.
; Clobbers: d0-d3, a0-a2
; -----------------------------------------------
EntityWindow_MigrateMasks:
        moveq   #0, d3                  ; new entry index
.new_loop:
        lea     (Entity_Scan_State).w, a0
        move.w  d3, d0
        ; a0 = entry d3's scan state (d0 × EntityScanState_len via add chain — len $1A: ×26 = ×16+×8+×2)
        move.w  d3, d1
        lsl.w   #4, d0                  ; ×16
        lsl.w   #3, d1                  ; ×8
        add.w   d1, d0
        add.w   d3, d1                  ; (d1 was ×8; +×1... implementer: just compute ×26
        ; with a clean shift/add chain or a dbf loop — cold path, clarity wins)
        ; --- semantics: d2.b = new entry d3's ess_section_id; skip if SEC_VOID;
        ;     scan snapshot ids 0-3 for match; on match copy 32 bytes from
        ;     snapshot mask[i] to Entity_Loaded_Masks + d3*32.
        ; (full loop shape left to implementer; keep it dbf-simple, cold path)
        addq.w  #1, d3
        cmpi.w  #MAX_TRACKED_SECTIONS, d3
        blo.s   .new_loop
        rts
```

**Implementer latitude:** exact loop code is yours (cold path — clarity over cycles); the semantics block is the contract. The snapshot buffer: use a 132-byte scratch — add `Entity_Mask_Scratch: ds.b 4+MAX_TRACKED_SECTIONS*ENTITY_LOADED_SLOT_SIZE` to ram.asm (RAM is fine: ~20KB free) rather than stack gymnastics.

- [ ] **Step 2: New `EntityWindow_CheckSlide`** + wire into `EntityWindow_Scan` directly after the existing coarse-Y re-scan trigger:

```asm
        ; window slide: fires when the camera envelope crosses a section
        ; boundary (≤ once per ~2048px of travel; one axis per frame at the
        ; 16px/f camera clamp)
        bsr.w   EntityWindow_DeriveWindow       ; d2/d3 = anchor candidate
        cmp.b   (Entity_Window_Anchor).w, d2
        bne.s   .slide
        cmp.b   (Entity_Window_Anchor+1).w, d3
        beq.s   .no_slide
.slide:
        movem.l d5-d7/a3, -(sp)                 ; preserve the Scan loop's registers
        bsr.w   EntityWindow_Slide
        movem.l (sp)+, d5-d7/a3
.no_slide:
```

(Mind register pressure: the Scan prologue uses d5/d6/d7/a3 — DeriveWindow clobbers d0/d2-d5; place this check BEFORE d5 is loaded with the validity mask, or re-load the mask after. Read the current Scan prologue and order accordingly — the coarse-Y trigger already navigates the same constraint.)

`EntityWindow_Slide` (new):
```asm
; snapshot old ids + masks → BuildEntries → MigrateMasks → UpdateCenter →
; populate sections that are NEW (id not in the snapshot)
EntityWindow_Slide:
        ; 1. snapshot: copy 4 ess_section_id bytes + the 128-byte mask block
        ;    into Entity_Mask_Scratch
        ; 2. bsr.w EntityWindow_BuildEntries
        ; 3. lea (Entity_Mask_Scratch).w, a4 ; bsr.w EntityWindow_MigrateMasks
        ; 4. Collected_UpdateCenter centered on the section containing the
        ;    camera center: derive via Section_FlatIDXY on (anchor + the
        ;    quadrant the camera center falls in) — simplest correct choice:
        ;    the entry whose origin box contains (camX+160, camY+112);
        ;    d1 = Act_grid_w+1(a2) as in the current rebuild code
        ; 5. populate loop (validity-gated, as in current RebuildScanState):
        ;    for each valid entry whose section_id is NOT in the snapshot ids,
        ;    bsr.w EntityWindow_PopulateSectionRings
        rts
```
(Each numbered line becomes real code — the existing `RebuildScanState` body is the template for 4/5; write it, don't sketch it. The DEBUG single-axis assert: compare new anchor to snapshot anchor — exactly one byte may differ; `ifdebug` both-differ → assert fail.)

- [ ] **Step 3: Shrink `EntityWindow_RebuildScanState`.** Its body becomes: snapshot → BuildEntries → MigrateMasks → UpdateCenter → Camera_Y_Coarse_Prev rebase → populate-new-only — i.e., identical to Slide plus the Camera_Y_Coarse_Prev rebase. Implement `RebuildScanState` as: rebase `Camera_Y_Coarse_Prev`, then `bra.w EntityWindow_Slide` (or share the body via a common entry point). Same-section entries (the teleport case) migrate masks slot-to-same-slot (no-op copies) and skip populate (their ids are in the snapshot) — **this is what makes teleports populate-free.**

- [ ] **Step 4: Build + slide verification in Exodus.**
1. Boot (mask $0A per Task 2), drive right slowly to camX $500 → slide fires once: mask $0F, ids (0,1,3,4), `Entity_Loaded_Masks` for section 0/3 SURVIVED the slide (bits intact — compare before/after), sections 1/4 populated fresh (band-gated).
2. Drive to camX $E00 → slide: ids (1,2,4,5) — **section 2 at origin $1200 tracked = FWD preview live.** Ring_Count gains sec2's in-band rings whose X ≤ the ratchet edge. Park; verify sec2 ring bits set.
3. Reverse to camX $500 → slide back: ids (0,1,3,4) — sections 1/4 masks survived (they never left), 0/3 repopulated (band+collected gated), Ring_Count consistent with cycle-start (collect nothing during this test).
4. Vertical: descend camY to $B00 → row slide (row0 0→... compute: ($B00−$380)>>11 = 0 → no row slide until camY ≥ $380+$800=$B80; drive to $C00) → ids advance one row; ladder behavior regression intact.
5. Ten slide oscillations across one boundary: Ring_Count identical at endpoints every cycle; `Ring_Add_Dropped` = 0.

- [ ] **Step 5: Commit**

```bash
git add engine/objects/entity_window.asm ram.asm
git commit -m "feat(entity-window): envelope slides — generic mask migration, recenter + populate move to slide path"
```

---

### Task 4: Teleports become re-expressions — delete the keep-window

**Files:**
- Modify: `engine/objects/entity_window.asm` (`EntityWindow_TeleportShift`, `EntityWindow_TeleportShiftY`, `EntityWindow_PopulateSectionRings`)

- [ ] **Step 1: Rewrite `EntityWindow_TeleportShift`** — delete the keep-window despawn/shift loops AND the Task-6 no-op comment table (superseded — the new invariant is stronger; say so in the replacement comment):

```asm
; -----------------------------------------------
; EntityWindow_TeleportShift — re-express entities after an X teleport rebase
;
; A teleport rebase does not change what is visible, and the window is
; visibility-derived, so the tracked SECTIONS are invariant across the rebase
; (slot-map advance ±2 cancels the camera-delta's col0 ∓2 — DEBUG-asserted).
; Entity work reduces to: shift every slot-tagged entity's X by the rebase
; delta, then re-init entries (same sections, re-expressed origins; masks
; survive via InitSection's same-section path + slot-to-slot migration).
; No keep-window, no despawn, no populate — nothing spawns or dies at a seam.
;
; In:  d0.w = shift amount (±SECTION_SHIFT)
; Out: none
; Clobbers: d0-d7, a0-a5
; -----------------------------------------------
EntityWindow_TeleportShift:
        move.w  d0, d4

        ; --- shift all buffered rings ---
        moveq   #0, d5
        move.b  (Ring_Count).w, d5
        beq.s   .rings_done
        subq.w  #1, d5
        lea     (Ring_Buffer).w, a0
.ring_loop:
        add.w   d4, (a0)                ; engine_X += delta
        addq.w  #RING_BUFFER_ENTRY_SIZE, a0
        dbf     d5, .ring_loop
.rings_done:

        ; --- shift all slot-tagged objects ---
        lea     (Dynamic_Slots).w, a0
        move.w  #NUM_DYNAMIC-1, d5
.obj_loop:
        tst.w   SST_code_addr(a0)
        beq.s   .obj_next
        cmpi.b  #SLOT_TAG_UNTAGGED, SST_slot_tag(a0)
        beq.s   .obj_next
        add.w   d4, SST_x_pos(a0)
.obj_next:
        lea     SST_len(a0), a0
        dbf     d5, .obj_loop

    ifdebug
        ; teleport invariance: anchor must be unchanged by the rebase
        move.b  (Entity_Window_Anchor).w, d6
        move.b  (Entity_Window_Anchor+1).w, d7
    endif
        bsr.w   EntityWindow_RebuildScanState
    ifdebug
        assert.b (Entity_Window_Anchor).w, eq, d6
        assert.b (Entity_Window_Anchor+1).w, eq, d7
    endif
        rts
```

(Verify the `assert` macro accepts a register comparand — read its definition in `debug/debugger.asm`; if it only takes immediates/memory, stash d6/d7 to scratch RAM words and compare those. Also verify `movem`-free d6/d7 survival through RebuildScanState — they do NOT (it clobbers d0-d7), so the scratch-RAM form is required; the code above shows intent, implement with `Entity_Mask_Scratch` bytes.)

- [ ] **Step 2: Same rewrite for `EntityWindow_TeleportShiftY`** (shift `2(a0)` ring Y / `SST_y_pos`, same structure, same asserts). Note `RebuildScanState` already rebases `Camera_Y_Coarse_Prev` (Task 3 Step 3) — exactly what Y teleports need.

- [ ] **Step 3: DEBUG populate no-dup assert.** In `EntityWindow_PopulateSectionRings`, inside the spawn path under `ifdebug`: before `RingBuffer_Add`, scan the live ring buffer for an entry with the same (section_id, list_index); assert none exists. (Cold path, DEBUG-only — a dbf scan over Ring_Count entries is fine.) This guards the "teleports never populate, slides only populate genuinely-new sections" invariant.

- [ ] **Step 4: Negative-origin DEBUG assert + comment.** At the end of `EntityWindow_ScanRingsRight`'s and `ScanObjectsRight`'s ratchet update, under `ifdebug`: if `ess_origin_x(a1)` is negative (`tst.w` + `bmi`), assert the ratchet being written is 0 (a negative-origin entry's first list entry already exceeds the unsigned right-edge compare — it must never scan anything; see spec §6). One shared comment at ScanRingsRight explains the unsigned-compare inertness.

- [ ] **Step 5: Build + teleport verification.**
1. FWD: park at camX $1100 (sec2 previewed, note Ring_Count + which sec2 entities are live); drive across $1200. **Ring_Count identical on the frames before/after the teleport** (read it repeatedly during the crossing; the rebase frame must not change it). Sec2's live entities: same buffer entries, X shifted by −$1000 exactly.
2. BWD back: same continuity check.
3. DOWN/UP: same, with a row-1→row-2... (grid is 3 rows; DOWN from rows (1,2)... set up by descending first). Ring continuity across both.
4. A live test-object (sec4 enemy patrolling): cross a seam with it on screen — it keeps patrolling, no reset (read its SST address before/after: same slot, x_pos shifted, anim state untouched).
5. DEBUG asserts silent throughout; quick FWD/BWD/FWD oscillation ×3 — counts stable.

- [ ] **Step 6: Commit**

```bash
git add engine/objects/entity_window.asm
git commit -m "feat(entity-window): teleports are entity re-expressions — keep-window deleted, invariance asserted"
```

---

### Task 5: Seam-region test data

**Files:**
- Modify: `data/editor/ojz/act1/section_2.rings.json`, `section_5.rings.json`, `section_5.objects.json` (+ library if needed)

- [ ] **Step 1: Author seam fixtures** (these regenerate into the ROM via the entity exporter at build time):
- `section_2.rings.json` (sec2 = column 2, row 0): ADD rings hugging its LEFT edge — `{"x":16,"y":1200},{"x":40,"y":1200},{"x":64,"y":1200}` (local $010-$040, Y $4B0 — visible heights when approaching the sec1/sec2 seam at mid-level camY).
- `section_5.rings.json` (sec5 = column 2, row 1 — the FWD+DOWN corner from sec1/row0): ADD `{"x":16,"y":16},{"x":40,"y":16}` (corner-hugging, exercises the diagonal).
- `section_5.objects.json`: ADD `{"x":96,"y":160,"typeId":"solid","subtype":0}` near its top-left corner.
(Existing user-authored entries in these files: leave untouched; append.)

- [ ] **Step 2: Build (regenerates entity data), reload, verify preview.** Approach the sec1→sec2 seam slowly at camY mid-row: the sec2 left-edge rings APPEAR while you're still left of camX $1200 (the envelope tracks sec2 from camX ≥ $D80: col0 = ($1200−... compute: col0=1 needs camX ≥ $C00; the rings at engine $1210-$1240 enter the X load ratchet at camX ≥ $1210−320−$180 = $D10 — expect them visible-when-reachable, spawned before the seam). Screenshot the rings sitting across the unseen boundary. Repeat for the corner (approach diagonally toward (camX $11xx, camY $Bxx... rows: sec5 needs row0 = 1 — camY ≥ $B80): sec5's corner rings + solid appear before either teleport fires.

- [ ] **Step 3: Commit**

```bash
git add data/editor/ojz/act1/section_2.rings.json data/editor/ojz/act1/section_5.rings.json data/editor/ojz/act1/section_5.objects.json
git commit -m "test(entity-window): seam + corner preview fixtures in sections 2 and 5"
```

---

### Task 6: Full verification matrix + §4.9-phase-2 regression

**Files:** none (verification only; fixes as needed)

- [ ] **Step 1: Run the spec §8 matrix end to end on a fresh build:**
1. Seam preview in all three directions (FWD column / DOWN row / corner) — entities appear before seams at correct world positions (Task 5 fixtures + sec4 circle).
2. Teleport continuity all four directions — Ring_Count + object identity across the rebase frame.
3. Quick reversals across slides AND teleports — counts stable, DEBUG asserts silent.
4. Grid edges — envelope clipped at world edges (camX low at boot, X void state (2,VOID) via double-FWD, bottom row), voids correct, no asserts.
5. §4.9-ph2 regression: band culling at boot, ladder progressive spawn on descent, 10× vertical oscillation idempotency, ANY_Y marker alive + tag, `Ring_Add_Dropped` = 0, `Ring_HighWater` recorded.
6. The user's authored formations (sec1 triangle, sec4 circle, sec2 square) all reachable and visible in normal play.

- [ ] **Step 2:** Any failure → systematic-debugging (root cause, fix, re-run matrix). Record all observed values.

---

### Task 7: Docs closeout

**Files:**
- Modify: `docs/ENGINE_ARCHITECTURE.md` (§4.9), `docs/DEFERRED_WORK.md`

- [ ] **Step 1: ENGINE_ARCHITECTURE §4.9:** rewrite the window-derivation paragraphs for the visibility model (envelope derivation, anchor invariance worked example, slides + generic migration, teleports as re-expressions, negative-origin inertness, the object-state convention pointer). Replace the now-obsolete "teleport disjointness table" framing: the table remains true but the stronger statement is "sections are invariant across rebases; assignments change only at slides."

- [ ] **Step 2: DEFERRED_WORK:** strike all three entries — "§4.9.5 Warp-Based Teleport Preview" (shipped — visibility window), "Teleport keep-range tests pre-shift coords" + "No survivor continuity across teleports" (dissolved by design — the keep-window no longer exists; explain in the strike note). Add follow-ups discovered during implementation. Check whether the "§4.9 entity window" architecture-doc statements elsewhere (e.g. §4 index line) need the same update.

- [ ] **Step 3: Commit; report final state** (this plan ends ON the branch — §4.9.4 respawn memory is the next plan; merge to master remains gated on the user's forest-BG coordination).

```bash
git add docs/ENGINE_ARCHITECTURE.md docs/DEFERRED_WORK.md
git commit -m "docs(§4.9): visibility-derived window — architecture + deferred closeouts"
```

---

## Self-review notes (applied)

- **Spec coverage:** §1 derivation → Task 2; §2 slides/migration/recenter/populate → Task 3; §3 teleports + all four DEBUG asserts → Task 4 (invariance, no-dup, single-axis [Task 3 Step 2], negative-origin); §4 behavior + §8 matrix → Tasks 5/6; §5b convention + audit → Task 1; §6 edge cases → Tasks 2 (voids/negative origins) & 6 (grid edges); §7 perf shapes stated inline.
- **Known judgment points, deliberately delegated with stated semantics:** BuildEntries stack-vs-scratch origin plumbing (Task 2 Step 3), MigrateMasks loop body (Task 3 Step 1), assert-macro register-comparand handling (Task 4 Step 1). Each has its contract spelled out; everything else is exact.
- **Type consistency:** `EntityWindow_DeriveWindow` out-regs (d2/d3/d4/d5) consistent across Tasks 2/3; `Entity_Window_Anchor` layout (x byte, y byte) consistent; `Entity_Mask_Scratch` defined Task 3, reused Task 4.
- **Boot-window change is intentional and flagged** (Task 2 Step 5): entry numbering shifts at boot because the envelope sees the void column left of the world — expectations recomputed, not assumed.
