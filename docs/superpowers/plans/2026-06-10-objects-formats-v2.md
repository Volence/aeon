# Objects & Formats v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (user prefers inline execution) to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the SST, spawn path, entity placement format, and collision data format so every field earns its bytes, every format covers its full coordinate range, and every capacity ceiling fails at build time instead of corrupting at runtime.

**Architecture:** Six coordinated changes that share one migration: (1) SST v2 — dead fields removed, priority folded into render_flags, entity metadata promoted to named fields, spawn-initialized fields reordered into one contiguous template block; (2) archetype burst-copy spawn — ObjDefs become ROM images of that template block, `Load_Object` becomes a movem copy; (3) entity entry format v2 — 6-byte entries with full-range coordinates, per-placement flip/any-Y flags; (4) capacity fixes for the section/entity-window state; (5) dual-layer collision (loop paths) in the block format; (6) per-frame bounding boxes in mappings for exact render culling. A closing task adds build-time ceilings for everything.

**Tech Stack:** AS Macro Assembler (68000), Python build tools (`tools/`), Exodus MCP for verification.

**Design decisions locked during brainstorm (2026-06-10):**
- NO archetype back-pointer in the SST — identity/teardown/refcount each land on existing fields (`code_addr`+symbols = debug identity; `ENTITY_SECTION_ID`/`LIST_INDEX` = respawn identity; `art_tile` = future VRAM refcount key; `sibling_ptr` = child teardown). Resources are reclaimed through the field that references them.
- SST stays `$50`. Reclaimed bytes go to `sst_custom` (30 → 34 bytes). Per-pool stride (player `$80`, effect `$20`) is deferred to §5 player physics — this plan keeps one stride but the prefix layout is chosen to allow it later.
- `anim_callback` moves from the SST into the animation script (`AF_CALLBACK` carries a word target).
- Verification is build + Exodus MCP per task (no test framework exists for 68000 asm; "test" = boot the OJZ scroll test and inspect state).

---

## SST v2 layout (single source of truth for every task below)

```
                       ; ============ SST v2 — still $50 bytes ============
$00 code_addr    .w    ; objroutine offset (0 = empty)         [template word]
$02 x_pos        .l    ; 16.16                                  [patched at spawn]
$06 y_pos        .l    ; 16.16                                  [patched at spawn]
                       ; ---- template block: $0A-$1F, copied verbatim from ObjDef ----
$0A x_vel        .w    ; 8.8
$0C y_vel        .w    ; 8.8
$0E render_flags .b    ; bit0 ONSCREEN, 1 XFLIP, 2 YFLIP, 3 COORDMODE,
                       ; bit4 MULTISPRITE, bits 5-7 PRIORITY (NEW — was word at $16)
$0F collision_resp.b
$10 mappings     .l
$14 art_tile     .w
$16 width_pixels .b    ; (moved from $18)
$17 height_pixels.b    ; (moved from $19)
$18 anim         .b    ; initial animation id
$19 subtype      .b    ; template default; placement subtype overwrites after copy
$1A anim_table   .l
$1E status       .b    ; template default (usually 0)
$1F angle        .b    ; NEW — terrain angle (player, slope-aligned badniks)
                       ; ---- end template (22 bytes; spawn copies 24, overlap below is re-inited) ----
$20 prev_anim    .b    ; runtime: $FF at spawn
$21 anim_frame   .b    ; runtime: 0
$22 anim_timer   .b    ; runtime: 0
$23 mapping_frame.b    ; runtime: 0
$24 prev_frame   .b    ; runtime: $FF
$25 sprite_piece_count.b ; runtime: from mappings frame 0
$26 parent_ptr   .w
$28 sibling_ptr  .w
$2A slot_tag     .b    ; NEW named field (was sst_custom+$1D squat)
$2B entity_section_id.b; NEW named field (was sst_custom+$1B squat)
$2C entity_list_index.b; NEW named field (was sst_custom+$1C squat)
$2D layer        .b    ; NEW — collision layer select (0 = path A, 1 = path B)
$2E sst_custom   34 bytes ($2E-$4F)
```

Deleted outright: `priority.w` ($16), `respawn_index.b` ($25), `wait_timer.w` ($2A), `anim_callback.l` ($2E) — 9 bytes, all verified dead or relocated 2026-06-10.

Render priority access pattern everywhere: `moveq #0,d0` + `move.b SST_render_flags(a0),d0` + `lsr.b #RF_PRIORITY_SHIFT,d0` — lsr discards bits 0-4 so no mask is needed, and 3 bits can't exceed `PRIORITY_BANDS-1` by construction (T2 review upgraded this from the original rol+andi; 4 cycles and 4 bytes cheaper). Runtime priority CHANGES must clear `RF_PRIORITY_MASK` first — `ori.b` is spawn-only.

## Entity entry format v2 (replaces packed 32-bit entries)

6 bytes per object placement, X-sorted, terminated by `dc.w -1` (X is section-local, always < `$800`, so a negative first word is an unambiguous sentinel and scan loops keep the `bmi` idiom):

```
+0  dc.w x          ; full section-local X (0-$7FF today; format covers any size)
+2  dc.w y          ; full section-local Y
+4  dc.w flags|type|subtype
       bit 15    = OEF_ANY_Y  (spawn regardless of camera Y — §4.9 phase 2)
       bit 14    = OEF_YFLIP  ┐ rol.w #4 lands these on RF_YFLIP(2)/RF_XFLIP(1)
       bit 13    = OEF_XFLIP  ┘ — one rol+andi initializes render_flags AND status
       bits 12-8 = type (5 bits, index into the section's type table)
       bits 7-0  = subtype (widened from 5 bits)
```

Ring entries are unchanged (`dc.w x, y`; `dc.l 0` terminator).

## ObjDef v2 (archetype template, replaces ODF bit-format)

A ROM image of SST `$00` + `$0A-$21` (word + 24 bytes), emitted by a named-parameter macro. No format byte, no conditional fields, no ordering rules:

```asm
; objdef — emit a v2 archetype template (26 bytes, all params except code/map optional)
;   objdef code=TestEnemy_Init, map=Map_TestObj, art=vram_art(VRAM_TEST_OBJ,0,0), \
;          pri=4, xvel=ENEMY_PATROL_SPEED, w=16, h=16, col=COLLISION_HURT, anims=Ani_Enemy
```

`Load_Object` copies it with `move.w` + `movem.l` (zero branches), patches x/y/subtype/flips, then runs the fixed runtime init (`prev_*` = `$FF`, piece count from mappings).

---

### Task 0: Branch

- [ ] **Step 1:** `git checkout -b objects-v2` from a clean `master`. Confirm `./build.sh` is green before any change.

---

### Task 1: AF_CALLBACK takes its target from the script (frees `anim_callback`)

**Research first (per project convention):** skim S.C.E. `Engine/Objects/Animate Sprite.asm` and sonic_hack's `AnimateSprite` for how they encode script commands with word args (both use byte-pair reads, never aligned word reads — scripts are byte streams). No online lookup needed; this is a self-contained script-format change.

**Files:**
- Modify: `engine/objects/animate.asm` (`.evt_callback` in both variants, header comment)
- Modify: `data/animations/sonic_anims.asm`, `data/animations/particle_anims.asm` (only if any script uses `AF_CALLBACK` — grep first; none expected)

- [ ] **Step 1:** Confirm no script uses the event yet: `grep -rn "AF_CALLBACK" data/` → expect no hits (engine-only references).

- [ ] **Step 2:** New script format, documented in the `animate.asm` header (args directly after the event byte, pad LAST — matches AF_SET_FIELD's convention):
```asm
;   $FA (AF_CALLBACK)  — call routine; format: dc.b $FA, target_hi, target_lo, 0
;                        (objroutine offset stored big-endian as two BYTES — scripts are unaligned)
```

- [ ] **Step 3:** Replace `.evt_callback` (per-anim variant). Args live at `2(a1,d1.w)`/`3(a1,d1.w)` (event byte itself is at `1(a1,d1.w)`); event consumes 4 bytes:
```asm
.evt_callback:
        ; dc.b AF_CALLBACK, target_hi, target_lo, 0  (objroutine offset, byte pair)
        moveq   #0, d0
        move.b  2(a1,d1.w), d0
        lsl.w   #8, d0
        move.b  3(a1,d1.w), d0
        beq.s   .evt_cb_done            ; offset 0 = no-op safety
        moveq   #OBJ_CODE_BANK, d2
        swap    d2
        move.w  d0, d2
        move.l  a1, -(sp)
        movea.l d2, a2
        jsr     (a2)
        movea.l (sp)+, a1
.evt_cb_done:
        addq.b  #4, SST_anim_frame(a0)
        bra.s   .after_event
```

- [ ] **Step 4:** Same change in `.pf_evt_callback` (PerFrame variant — args at `1(a1,d1.w)`/`2(a1,d1.w)`, consume 4, advance 4). Both handlers no longer touch `SST_anim_callback`.

- [ ] **Step 5:** `./build.sh` green. Boot in Exodus (reload + reset + screenshot — animations still play on the test player). Commit: `feat(anim): AF_CALLBACK target moves into the script — frees SST anim_callback`.

---

### Task 2: SST v2 layout + all consumers (mechanical, one commit)

**Research first:** re-read S.C.E.'s `Object.asm` SST ordering and TheBlad768's collision-field-packing commits (`d1e24ee`/`05512e4`, already summarized in DEFERRED_WORK §3) to sanity-check the template-block ordering before committing to it. Check Gunstar's object struct (multi-sprite fields adjacency) in the disasm notes.

**Files:**
- Modify: `structs.asm` (SST struct — the v2 layout above, verbatim)
- Modify: `constants.asm` (delete `SLOT_TAG_OFFSET`/`ENTITY_SECTION_ID_OFFSET`/`ENTITY_LIST_INDEX_OFFSET` equates — now real fields; add `RF_PRIORITY_SHIFT = 5`, `SST_CUSTOM_SIZE = 34`, `SST_TEMPLATE_START = $0A`, `SST_TEMPLATE_SIZE = 24`)
- Modify (offset consumers — every `SST_priority`, `SST_width_pixels`, `SST_height_pixels`, squatted-offset, and anim-block-init site):
  - `engine/objects/sprites.asm` (priority read in `Draw_Sprite`)
  - `engine/objects/load_object.asm` (rewritten fully in Task 4; here only field offsets)
  - `engine/objects/entity_window.asm` + `engine/objects/entity_loader.asm` (`SLOT_TAG_OFFSET` → `SST_slot_tag` etc.)
  - `engine/objects/collision.asm`, `engine/objects/rings.asm` (width/height offsets — symbolic, no edit needed beyond rebuild)
  - all 9 `objects/test_*.asm` + `test/ojz_scroll_test.asm` + `test/object_test_state.asm` (priority writes become render_flags bits)

- [ ] **Step 1:** Rewrite the `SST` struct in `structs.asm` exactly per the v2 layout table above, including the field comments. Keep the `SST_len <> $50` assertion. Add:
```asm
    if SST_sst_custom <> $2E
      error "SST template/metadata block moved — sst_custom expected at $2E, got \{SST_sst_custom}"
    endif
```

- [ ] **Step 2:** Priority fold. In `Draw_Sprite` (`engine/objects/sprites.asm`):
```asm
        ; OLD:
        move.w  SST_priority(a0), d0   ; 0-7
        andi.w  #PRIORITY_BANDS-1, d0
        ; NEW:
        moveq   #0, d0
        move.b  SST_render_flags(a0), d0
        rol.b   #3, d0                 ; bits 5-7 → 0-2
        andi.w  #PRIORITY_BANDS-1, d0
```
Every object that wrote `move.w #N, SST_priority(a0)` now sets bits at init: `ori.b #N<<RF_PRIORITY_SHIFT, SST_render_flags(a0)` (test objects: stress_emitter 7, emitter 5, player 4, particle 6, animated 4; `ojz_scroll_test.asm:68` player setup; `ObjDef` data migrates in Task 4).

- [ ] **Step 3:** Replace every `SLOT_TAG_OFFSET(...)` with `SST_slot_tag(...)`, `ENTITY_SECTION_ID_OFFSET` with `SST_entity_section_id`, `ENTITY_LIST_INDEX_OFFSET` with `SST_entity_list_index` (sites: `entity_window.asm` ×6, `entity_loader.asm` ×1, constants deleted). `SLOT_TAG_UNTAGGED` stays `$FF` — but note: `DeleteObject`/`InitObjectRAM` zero slots, and 0 = `SLOT_TAG_LEFT`. Add one line to the spawn-tag path instead of relying on zero: untagged objects (children/effects) must get `move.b #SLOT_TAG_UNTAGGED, SST_slot_tag(a2)` in `CreateChild_*`/`CreateEffect_*` (5 sites in `engine/objects/children.asm`) so despawn never claims them. *(This fixes a latent v1 bug: a zeroed slot reads tag 0 = LEFT, but v1 "worked" because zeroed slots also have code_addr 0 — keep the explicit tag anyway, it costs one instruction per spawn.)*

- [ ] **Step 4:** Anim-block runtime init sites (`Load_Object`, `CreateChild_Complex`/`FlipAware`): the `$FF` pair moved ($1B/$1F → $20/$24). New canonical init (used verbatim in Task 4's Load_Object too):
```asm
        move.l  #$FF000000, SST_prev_anim(a1)   ; prev_anim=$FF, anim_frame/timer/mapping_frame=0
        move.b  #$FF, SST_prev_frame(a1)
```

- [ ] **Step 5:** `./build.sh` — chase every assembler error from removed fields (`SST_priority`, `SST_wait_timer`, `SST_respawn_index`, `SST_anim_callback` must all be gone; the build IS the migration checklist). Then `DEBUG=1 ./build.sh` green too.

- [ ] **Step 6:** Exodus: reload, reset, screenshot — player + rings render in the same bands as before (priority fold proof). Drive the player down past `$A00` (write `0xFF897A` = `0B000000`, sleep, screenshot) — entity despawn/spawn still works (metadata-field proof: rings persist, backdrop goes yellow). Commit: `refactor(sst): SST v2 layout — dead fields out, priority in render_flags, entity metadata promoted, angle+layer added`.

---

### Task 3: `objvars` convention for custom fields

**Files:**
- Modify: `macros.asm` (add check macro), `structs.asm` (nothing — per-object structs live in the object files)
- Modify: all 9 `objects/test_*.asm`

- [ ] **Step 1:** Add to `macros.asm`:
```asm
; objvars_check — assert a per-object custom struct fits sst_custom
; Usage:  MyV struct ... MyV endstruct
;         objvars_check MyV_len
objvars_check macro structlen
    if (structlen) > SST_CUSTOM_SIZE
        fatal "object custom vars overflow sst_custom by \{(structlen)-SST_CUSTOM_SIZE} bytes"
    endif
        endm
```

- [ ] **Step 2:** Migrate each test object. Pattern (TestEnemy shown; same shape for all — the short `_name` equates SURVIVE but are derived from the struct, never raw arithmetic):
```asm
; OLD:
;_enemy_patrol_left      = SST_sst_custom
;_enemy_patrol_right     = SST_sst_custom+2
;_enemy_direction        = SST_sst_custom+4
; NEW:
TEnemyV struct
patrol_left     ds.w 1
patrol_right    ds.w 1
direction       ds.b 1
TEnemyV endstruct
        objvars_check TEnemyV_len
_enemy_patrol_left      = SST_sst_custom+TEnemyV_patrol_left
_enemy_patrol_right     = SST_sst_custom+TEnemyV_patrol_right
_enemy_direction        = SST_sst_custom+TEnemyV_direction
```
Shared layouts (the `_dplc_ptr`/`_art_base` pair in test_player/test_animated) get ONE struct (`DplcV`) defined in `test_animated.asm` (first include) with the existing `ifndef` guard retained around the equates.

- [ ] **Step 3:** Build green, commit: `refactor(objects): objvars structs replace raw sst_custom offset arithmetic`.

---

### Task 4: ObjDef v2 + burst-copy `Load_Object`

**Research first:** S.C.E. `Load Objects.asm` (the commit the user found — flag placement + `rol` trick), Vectorman's object templates (their init blocks are ROM images — closest prior art for burst-copy spawn), and sonic_hack `Object_Load`. Confirm `movem.l` reg-to-mem ordering (d0 first at lowest address) against AS output once during implementation.

**Folded in from the T2 quality review:**
- Centralize the untagged init: move `move.b #SLOT_TAG_UNTAGGED, SST_slot_tag(a1)` into `AllocDynamic` (core.asm) so the invariant is structural; delete the seven per-site inits T2 added (six in children.asm, one in Load_Object). `AllocEffect` keeps none (effect slots are never despawn-scanned) — delete the two CreateEffect_* inits too.
- The `objdef` macro must validate `pri`: `if OD_PRI > 7 / fatal "objdef: priority N exceeds 7"` (lsl.b would silently truncate).

**Files:**
- Modify: `macros.asm` (the `objdef` macro)
- Rewrite: `engine/objects/load_object.asm`
- Rewrite: `data/objdefs/test_objects.asm`
- Modify: `constants.asm` (delete `ODF_*` and `OBJ_FMT_*` — fully superseded)

- [ ] **Step 1:** The `objdef` macro in `macros.asm` — emits exactly SST `$00` + `$0A-$21` (26 bytes), every parameter named-and-optional except `code`/`map`:
```asm
; objdef — v2 archetype template. ROM image of SST $00 + $0A-$21.
objdef macro code,map,art,pri,xvel,yvel,w,h,col,anims,anim,sub,rf,st
    if "code" = ""
        fatal "objdef: code required"
    endif
    if "map" = ""
        fatal "objdef: map required"
    endif
OD_ART set 0
    if "art" <> ""
OD_ART set art
    endif
OD_PRI set 0
    if "pri" <> ""
OD_PRI set pri
    endif
OD_XV set 0
    if "xvel" <> ""
OD_XV set xvel
    endif
OD_YV set 0
    if "yvel" <> ""
OD_YV set yvel
    endif
OD_W set 0
    if "w" <> ""
OD_W set w
    endif
OD_H set 0
    if "h" <> ""
OD_H set h
    endif
OD_COL set 0
    if "col" <> ""
OD_COL set col
    endif
OD_ANIMS set 0
    if "anims" <> ""
OD_ANIMS set anims
    endif
OD_ANIM set 0
    if "anim" <> ""
OD_ANIM set anim
    endif
OD_SUB set 0
    if "sub" <> ""
OD_SUB set sub
    endif
OD_RF set 0
    if "rf" <> ""
OD_RF set rf
    endif
OD_ST set 0
    if "st" <> ""
OD_ST set st
    endif
        dc.w objroutine(code)                       ; $00 code_addr
        dc.w OD_XV, OD_YV                           ; $0A x_vel, $0C y_vel
        dc.b OD_RF|(OD_PRI<<RF_PRIORITY_SHIFT)      ; $0E render_flags (priority folded)
        dc.b OD_COL                                 ; $0F collision_resp
        dc.l map                                    ; $10 mappings
        dc.w OD_ART                                 ; $14 art_tile
        dc.b OD_W, OD_H                             ; $16 width, $17 height
        dc.b OD_ANIM, OD_SUB                        ; $18 anim, $19 subtype default
        dc.l OD_ANIMS                               ; $1A anim_table
        dc.b OD_ST, 0                               ; $1E status, $1F angle
        dc.w 0                                      ; $20-$21 pad (copied, then re-inited)
        endm
```

- [ ] **Step 2:** Rewrite `Load_Object` (`engine/objects/load_object.asm`) — full replacement:
```asm
; -----------------------------------------------
; Load_Object — spawn one object from a v2 archetype template
; In:  a1 = ObjDef template (ROM, 26 bytes: code_addr.w + SST $0A-$21 image)
;      d0.w = X position (integer, engine coords)
;      d1.w = Y position (integer, engine coords)
;      d2.w = placement word: flags|type|subtype (entity format v2);
;             pass subtype in low byte and 0 flags for direct spawns
; Out: Z set = success, a1 = new SST pointer
;      Z clear = allocation failed
; Clobbers: d0-d4, a1-a3
; -----------------------------------------------
Load_Object:
        movem.l d0-d2/a1, -(sp)
        jsr     AllocDynamic
        bne.w   .alloc_fail
        movem.l (sp)+, d0-d2/a2        ; a2 = template, a1 = new SST

        ; --- burst copy: code_addr word + 24-byte template block ---
        move.w  (a2)+, SST_code_addr(a1)
        lea     SST_x_vel(a1), a3
        movem.l (a2)+, d3-d4
        movem.l d3-d4, (a3)            ; $0A-$11
        movem.l (a2)+, d3-d4
        movem.l d3-d4, 8(a3)           ; $12-$19
        movem.l (a2)+, d3-d4
        movem.l d3-d4, 16(a3)          ; $1A-$21 ($20-$21 overlap re-inited below)

        ; --- per-placement patch ---
        swap    d0
        clr.w   d0
        move.l  d0, SST_x_pos(a1)
        swap    d1
        clr.w   d1
        move.l  d1, SST_y_pos(a1)
        move.b  d2, SST_subtype(a1)    ; placement subtype (low byte)
        move.w  d2, d3                 ; placement flips → render_flags + status
        rol.w   #4, d3                 ; bits 13/14 → RF_XFLIP(1)/RF_YFLIP(2)
        andi.b  #(1<<RF_XFLIP)|(1<<RF_YFLIP), d3
        or.b    d3, SST_render_flags(a1)
        or.b    d3, SST_status(a1)

        ; --- runtime init ---
        move.l  #$FF000000, SST_prev_anim(a1)   ; prev_anim $FF, frame/timer/mapframe 0
        move.b  #$FF, SST_prev_frame(a1)
        move.b  #SLOT_TAG_UNTAGGED, SST_slot_tag(a1)

        ; --- initial sprite_piece_count from mappings frame 0 ---
        move.l  SST_mappings(a1), d3
        beq.s   .no_piece_count
        movea.l d3, a3
        move.w  (a3), d3
        move.w  (a3,d3.w), d3
        move.b  d3, SST_sprite_piece_count(a1)
.no_piece_count:
        moveq   #0, d0                 ; Z set = success
        rts

.alloc_fail:
        movem.l (sp)+, d0-d2/a1
        moveq   #1, d0                 ; Z clear = failed
        rts
```
`Load_ObjectList` keeps its shape; its `subtype` word passes through in d2 unchanged (no flags from direct lists).

- [ ] **Step 3:** Rewrite `data/objdefs/test_objects.asm` with the macro:
```asm
ObjDef_Static:
        objdef code=TestStatic_Main, map=Map_TestObj, art=vram_art(VRAM_TEST_OBJ,0,0)
ObjDef_Solid:
        objdef code=TestSolid_Init, map=Map_TestObj, art=vram_art(VRAM_TEST_OBJ,0,0), \
               pri=3, w=16, h=16, col=COLLISION_SOLID
ObjDef_Enemy:
        objdef code=TestEnemy_Init, map=Map_TestObj, art=vram_art(VRAM_TEST_OBJ,0,0), \
               pri=4, xvel=ENEMY_PATROL_SPEED, w=16, h=16, col=COLLISION_HURT
ObjDef_Parent:
        objdef code=TestParent, map=Map_TestObj, art=vram_art(VRAM_TEST_OBJ,0,0), pri=3
```
(`ENEMY_PATROL_SPEED` must move to `constants.asm` or be defined before the include — it currently lives in `test_enemy.asm` which is included earlier in `main.asm`; verify include order, it already works today.)

- [ ] **Step 4:** Delete `ODF_*`/`OBJ_FMT_*` from `constants.asm`. Update the caller in `entity_window.asm` (`EntityWindow_ScanObjectsRight`) minimally — it already passes a1=ObjDef, d0/d1/d2; it now passes the full placement word in d2 (interim: still the v1-extracted subtype until Task 5 rewrites the scan).

- [ ] **Step 5:** Build green (both flavors). Exodus: reload/reset, verify the solid block and enemy in Sec0-2 spawn, patrol, and collide as before (drive player right with `0xFF8976` X writes; screenshot at `$300` and `$900`). Commit: `feat(objects): archetype burst-copy spawn — ObjDef v2 templates replace ODF bit-format`.

---

### Task 5: Entity entry format v2

**Research first:** the S.C.E.-Extended commit `8a8cd4f` (flags-in-ID-word; already analyzed), and `data/editor/ojz/act1/export/entity_data.asm` + whatever generates it (check `tools/` and `data/editor/` for the exporter script — research step MUST identify it before editing data by hand twice).

**Files:**
- Modify: `constants.asm` (replace `OBJ_ENTRY_*` with `OEF_*` bit definitions)
- Modify: `engine/objects/entity_window.asm` (`EntityWindow_ScanObjectsRight` extraction)
- Modify: `data/levels/ojz/act1/entity_data.asm` (+ the editor exporter + `data/editor/.../export/entity_data.asm`)
- Modify: `docs/LEVEL_EDITOR_SPEC.md` §8.1

- [ ] **Step 1:** Constants:
```asm
; Object placement entry (ROM, 6 bytes): dc.w x, y, flags|type|subtype
; X-sorted; terminated by dc.w -1 (X is section-local, always >= 0)
OEF_ANY_Y               = 15            ; spawn regardless of camera Y
OEF_YFLIP               = 14            ; rol.w #4 → RF_YFLIP
OEF_XFLIP               = 13            ; rol.w #4 → RF_XFLIP
OEF_TYPE_SHIFT          = 8             ; bits 12-8: type (0-31)
OEF_TYPE_MASK           = $1F
OEF_SUBTYPE_MASK        = $FF           ; bits 7-0
OBJ_ENTRY_SIZE          = 6
```

- [ ] **Step 2:** Rewrite the scan extraction in `EntityWindow_ScanObjectsRight` — entry stride 4 → 6, bit-harvest → word reads:
```asm
        ; Advance a0 to current index (6 bytes per ROM entry)
        move.w  d4, d0
        add.w   d0, d0
        add.w   d4, d0
        add.w   d0, d0                  ; index × 6
        adda.w  d0, a0

.obj_loop:
        move.w  (a0), d0                ; section-local X (negative = terminator)
        bmi.s   .obj_update_idx
        add.w   d3, d0                  ; engine X
        cmp.w   d7, d0
        bhi.s   .obj_update_idx         ; past right edge — X-sorted, stop
        ; ... killed-check unchanged (uses d4 list index) ...
        move.w  2(a0), d1               ; section-local Y (engine Y for row 0 — §4.9 X-only)
        move.w  4(a0), d2               ; flags|type|subtype
        move.w  d2, d3                  ; (d3 reloaded from scan state after spawn)
        lsr.w   #OEF_TYPE_SHIFT, d3
        andi.w  #OEF_TYPE_MASK, d3
        movea.l EntityScanState_ess_rom_type_tbl_ptr(a1), a2
        lsl.w   #2, d3
        addq.w  #2, d3
        movea.l (a2,d3.w), a1           ; ObjDef
        jsr     Load_Object             ; d2 carries subtype + flip/any-Y flags intact
        ; ... tag fields, restore, advance ...
.obj_skip:
        addq.w  #1, d4
        addq.w  #OBJ_ENTRY_SIZE, a0
        bra.s   .obj_loop
```
(Write the full routine during implementation — the registers around the spawn save/restore keep the existing `movem` shape; `d3` = origin_x must be re-fetched from `EntityScanState_ess_origin_x(a1)` after the spawn block exactly as v1 does.)

- [ ] **Step 3:** Migrate `data/levels/ojz/act1/entity_data.asm` (4 sections with objects, 1-2 entries each) to `dc.w x, y, (type<<OEF_TYPE_SHIFT)|subtype` + `dc.w -1` terminators. Place ONE object deliberately at X=`$600` (right half of section — impossible in v1) as the format's regression proof. Update the editor exporter found in the research step; regenerate `data/editor/ojz/act1/export/entity_data.asm`; exporter gets hard-fails: x/y within section size, type < 32, subtype < 256.

- [ ] **Step 4:** Update `docs/LEVEL_EDITOR_SPEC.md` §8.1 with the v2 entry format (copy the format block from this plan's header).

- [ ] **Step 5:** Build green. Exodus: the X=`$600` object spawns when the camera approaches (drive player right; screenshot). Commit: `feat(entities): 6-byte placement entries — full-range coords, flip + any-Y flags (S.C.E.-Extended pattern)`.

---

### Task 6: Capacity fixes (section state, collected window, list caps)

**Files:**
- Modify: `ram.asm` (`Section_Stream_State` sizing), `constants.asm` (`MAX_ACT_SECTIONS`)
- Modify: `engine/objects/entity_window.asm` (`Collected_UpdateCenter` eviction radius)
- Modify: `data/levels/ojz/act1/act_descriptor.asm` (build assert), exporter (list caps)

- [ ] **Step 1:** `MAX_ACT_SECTIONS = 48` in constants; `Section_Stream_State: ds.b MAX_ACT_SECTIONS` in ram.asm (was 16; +32 bytes, RAM has 20KB headroom). Per-act build assert next to the descriptor:
```asm
    if 3*3 > MAX_ACT_SECTIONS          ; grid_w * grid_h literals per act
      error "OJZ act 1 grid exceeds MAX_ACT_SECTIONS"
    endif
```

- [ ] **Step 2:** Collected window geometry: eviction radius ±2 (5×5=25 neighborhood) contradicts 9 slots. Change both `cmpi.w #2, d1`/`cmpi.w #2, d0` in `Collected_UpdateCenter` to `#1` (3×3 = 9 — matches the slot count and the architecture doc's "3×3 rolling bitmask"). Update the `constants.asm` comment block that says "5×5".

- [ ] **Step 3:** Killed/collected bitmask caps in the exporter: hard-fail any section with > 128 rings or > 128 objects (`bset` past bit 127 corrupts the neighboring window slot). Engine-side belt-and-braces in `DEBUG` builds: `ifdebug assert.w d1, lo, #128` in `Collected_CheckRing`/`Killed_CheckObject` after the index load.

- [ ] **Step 4:** Build green both flavors, boot check, commit: `fix(entities): section-state and bitmask capacity ceilings — sized, asserted, exporter-enforced`.

---

### Task 7: Dual-layer collision (loop paths)

**Research first (this task's design depends on it):** (1) how sonic_hack/S2 OJZ encodes primary vs secondary collision indexes (`Obj_Index`/`ColP`/`ColS` data — check `sonic_hack/collision/`), (2) S.C.E.'s `Collision Response.asm` layer handling (`top_solid_bit`), (3) how `tools/` block generator currently emits the single collision byte per cell (find the script that builds `data/collision` + block blobs), (4) S3K path-swapper object behavior (plane switch on touch). Online: Sonic Physics Guide "Solid Tiles — Layers".

**Format decision (locked):** each block's collision area doubles — layer A plane then layer B plane (`BLOCK_COLL_SIZE` 128 → 256, `BLOCK_RAW_SIZE` 640 → 768). Tile cache collision array doubles (2,400 → 4,800 bytes — lower RAM had ~4.8KB slack at `$FFFF6D12`; verify the phase check still passes). `Collision_GetType` adds `+TILE_CACHE_COLL_SIZE` to the index when the querying object's `SST_layer` is nonzero — one `tst.b` + one `add.w`, no extra lookups for layer-A objects.

**Files:**
- Modify: `constants.asm` (BLOCK_COLL_SIZE, BLOCK_RAW_SIZE, TILE_CACHE_COLL_SIZE ×2)
- Modify: `ram.asm` (cache + staging sizes; check `Lower_RAM_End` guard)
- Modify: `engine/level/tile_cache.asm` (`TileCache_CopyBlockColumn` collision copy ×2 planes, `TileCache_FillRow` collision write ×2, `Tile_Cache_GetCollision` layer offset)
- Modify: `engine/level/collision_lookup.asm` (`Collision_GetType` takes layer from caller; `Collision_FloorSensors` reads `SST_layer(a0)`)
- Modify: block generator tool + regenerate OJZ block data (research step identifies the script)

- [ ] **Step 1:** Research per above; write findings to `docs/research/dual-layer-collision.md` (what S2 data exists for OJZ's two layers, exact tool entry point). **If OJZ's source data has no secondary layer authored, emit layer B = copy of layer A** — format ships now, content later.
- [ ] **Step 2:** Constants + RAM resize; build; fix the `Lower_RAM_End` overflow if the staging growth (12 × 768 = 9,216) busts it — drop `BLOCK_STAGE_SLOTS` to 10 if needed (comment explains the diagonal-coexistence minimum is 11; measure before dropping).
- [ ] **Step 3:** Engine-side: collision copy loops handle two planes (second plane = same loop, source +128/dest +`TILE_CACHE_COLL_SIZE/2`... — plane-relative, mirrors the first); `Collision_GetType` gains layer-select; `Collision_FloorSensors`/`_Wall` pass the object's layer. Sensor routines' register contracts in the headers updated.
- [ ] **Step 4:** Tool-side: regenerate blocks with both planes; build green; Exodus boot — collision behaves identically (everything is layer A). Flip `Player_1+SST_layer` to 1 via MCP (`0xFF8974+$2D`) and confirm the player still lands (layer B = copy proves the plumbing). Commit: `feat(collision): dual-layer collision planes — loop path A/B in block format + SST layer select`.

---

### Task 8: Per-frame bounding boxes — exact render culling

**Research first:** the mapping generator (find the tool that emits `data/mappings/*.bin` / `test_mappings.asm`), S2's `width_pixels`-based cull for comparison, and confirm worst current piece extents (Sonic frames) fit signed bytes (±127); exporter hard-fails beyond.

**Format:** frame data becomes `[x_min.b, x_max.b, y_min.b, y_max.b][count.w][pieces...]` — 4 signed bytes BEFORE the existing count word. `Render_Sprites`/`RefreshSpritePieceCount`/`PopulateSpawnedPieceCount` read count at `+4`; `Draw_Sprite` culls exactly:
```asm
        ; screen-relative d0 (X) already computed; frame ptr in a1
        move.b  fbb_x_min(a1), d2
        ext.w   d2
        add.w   d0, d2                  ; left edge on screen
        cmpi.w  #SCREEN_WIDTH, d2
        bge.s   .offscreen              ; left edge past right side
        move.b  fbb_x_max(a1), d2
        ext.w   d2
        add.w   d0, d2
        bmi.s   .offscreen              ; right edge above zero? gone left
        ; (same pair for Y)
```
*(Exact integration — Draw_Sprite currently doesn't resolve the frame pointer; it will need the same table-offset lookup Render_Sprites does, ~5 instructions. Implementation step works out the final register usage; the win is exact culling for 96px bosses AND tighter culling for 8px particles.)*

**Files:** mapping tool, `data/mappings/test_mappings.asm`, `engine/objects/sprites.asm` (3 count-read sites + Draw_Sprite), `engine/objects/animate.asm` (`RefreshSpritePieceCount`), `engine/objects/children.asm` (`PopulateSpawnedPieceCount`), `engine/objects/load_object.asm`.

- [ ] **Step 1:** Research + regenerate mappings with bbox prefix (hand-edit `test_mappings.asm`'s few frames if no tool generates them — compute the 4 bytes from the piece offsets by hand, they're 1-piece frames).
- [ ] **Step 2:** Bump the count-read offset (+4) at all 4 sites; add the bbox cull to `Draw_Sprite` replacing the fixed ±32 margins.
- [ ] **Step 3:** Build, Exodus: sprites still render; park an object half off-screen via MCP X writes and confirm it draws (margin behavior preserved at worst, exact at best). Commit: `feat(render): per-frame bounding boxes in mappings — exact sprite culling`.

---

### Task 9: Build-time ceilings sweep + docs + merge

**Files:** `main.asm`, `macros.asm`, `constants.asm`, `docs/ENGINE_ARCHITECTURE.md`, `docs/LEVEL_EDITOR_SPEC.md`, `docs/DEFERRED_WORK.md`

- [ ] **Step 1:** Object bank guard in `main.asm` after the last object include:
```asm
    if * > $20000
      error "Object code bank overflows 64KB by \{*-$20000} bytes"
    endif
```
- [ ] **Step 2:** ±32KB word-offset table asserts — after `Map_Sonic`/`DPLC_Sonic` BINCLUDEs and the anim tables:
```asm
    if (*-Map_Sonic) > $7FFF
      error "Map_Sonic exceeds signed-word offset range"
    endif
```
(same pattern for DPLC table and each anim table file's end).
- [ ] **Step 3:** Derive section threshold constants from `SECTION_SIZE` in `constants.asm` (pure refactor, values identical — `SECTION_FWD_THRESHOLD = SLOT_ORIGIN_L+2*SECTION_SIZE` etc.; assert each equals its old literal once, then delete the asserts).
- [ ] **Step 4:** Sync `ENGINE_ARCHITECTURE.md` (§3 SST table → v2 layout, §4.9 entry format, §4.7 collision dual-layer) and close the superseded `DEFERRED_WORK` items (word mappings offset → still open; SST audit → resolved by this plan; pack-collision-fields → superseded; subObjData → superseded by `objdef`).
- [ ] **Step 5:** Full build both flavors + final Exodus sweep (boot, scroll right through a teleport, vertical descent, ring collect). Merge: `git checkout master && git merge objects-v2`, push nothing (local), update memory.

---

## Self-review notes

- **Spec coverage:** SST v2 ✓ (T2), callback-to-script ✓ (T1), objvars ✓ (T3), burst-copy spawn ✓ (T4), entity format v2 ✓ (T5), capacity 1-3 ✓ (T6), dual-layer ✓ (T7), bbox cull ✓ (T8), ceilings ✓ (T9). Dropped by design decision: archetype pointer (user call, justified), per-pool stride (deferred to §5 with layout left compatible).
- **Known soft spots flagged inline:** T5 Step 2 and T8 Step 2 specify the shape but finalize registers during implementation against the live file; T7's data availability question has an explicit fallback (layer B = layer A copy).
- **Ordering rationale:** T1 is independent; T2 must precede T3-T5 (offsets); T4 before T5 (spawn signature change); T6-T8 independent after T5; T9 last.
