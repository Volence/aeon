; RAM layout via phase/dephase
; Lower 32KB ($FFFF0000+) for large buffers — .l addressing required
; Upper 32KB ($FFFF8000+) for hot data — .w addressing for speed

; -----------------------------------------------
; Lower RAM — 2D tile cache, block staging, streaming buffers (§4.7).
; Art_Staging_Buffer (below) reuses the tile-cache nametable RAM during
; display-off level init to stage decompressed art pages before DMA.
; -----------------------------------------------
        phase $FFFF0000

; 2D tile cache — world-space sliding window (replaces 1D strip cache)
Tile_Cache_Nametable:   ds.b TILE_CACHE_NT_SIZE                      ; 9600 bytes (80×60×2)
; Collision: two planes contiguous in memory.
;   Plane A: Tile_Cache_Collision + 0               (2400 bytes, 80×30)
;   Plane B: Tile_Cache_Collision + TILE_CACHE_COLL_SIZE  (2400 bytes, 80×30)
; Tile_Cache_GetCollision selects the plane via the caller's SST_layer value.
Tile_Cache_Collision:   ds.b TILE_CACHE_COLL_SIZE * TILE_CACHE_COLL_PLANES  ; 4800 bytes
                        ds.b 2                       ; pad to even

; Block staging cache — recently decompressed blocks (§4.7)
; BLOCK_STAGE_SLOTS slots of BLOCK_RAW_SIZE each:
;   nametable (512 B) + collision plane A (128 B) + collision plane B (128 B).
; Keys live in upper RAM (Block_Stage_Keys).
Block_Stage_Buffers:    ds.b BLOCK_RAW_SIZE * BLOCK_STAGE_SLOTS  ; 9216 bytes (12×768)

; Art staging — decompress one art-pool page here at level init (display off),
; then DMA it to VRAM. Reuses the tile-cache nametable RAM, which is NOT yet
; populated during display-off level init. INIT-ONLY; never used after the
; cache goes live.
Art_Staging_Buffer = Tile_Cache_Nametable

        if ART_STAGING_BUFFER_SIZE > TILE_CACHE_NT_SIZE
          error "Art staging buffer (\{ART_STAGING_BUFFER_SIZE}) exceeds tile-cache RAM"
        endif

Lower_RAM_End:

        if Lower_RAM_End > $FFFF8000
          error "Lower RAM overflow by \{Lower_RAM_End - $FFFF8000} bytes!"
        endif

        dephase

; -----------------------------------------------
; Upper RAM — hot data (.w addressing)
; -----------------------------------------------
        phase $FFFF8000

RAM_Start:

; -----------------------------------------------
; System
; -----------------------------------------------
VBlank_Flag:            ds.b 1
                        ds.b 1
Frame_Counter:          ds.w 1
Game_State:             ds.l 1
Game_State_ID:          ds.b 1
Game_State_Init:        ds.b 1

; -----------------------------------------------
; VDP Shadow Table (§0.4)
; -----------------------------------------------
VDP_Shadow_Table:       ds.b VDP_Shadow_len
                        ds.b 1          ; pad to even (VDP_Shadow_len is 19 = odd)
VDP_Dirty_Mask:         ds.l 1          ; bits 0-18 for regs $00-$12

; -----------------------------------------------
; Interrupt dispatch
; -----------------------------------------------
; HBlank dispatch runs through HBlank_Vector_Slot (defined at the RAM tail — see
; below — so its addition ripples zero existing upper-RAM addresses). This
; reserved word holds that layout stable.
                        ds.l 1          ; reserved (interrupt dispatch)

; -----------------------------------------------
; Region detection (§0.8)
; -----------------------------------------------
Hardware_Region:        ds.b 1
Region_Flags:           ds.b 1
Timing_Step:            ds.w 1
Frame_Accumulator:      ds.w 1

; -----------------------------------------------
; Controllers
; -----------------------------------------------
Ctrl_1_Held:            ds.b 1
Ctrl_1_Press:           ds.b 1          ; tick-stable: latched by VInt_Level, consumed by game logic
Ctrl_2_Held:            ds.b 1
Ctrl_2_Press:           ds.b 1
Ctrl_1_Press_Accum:     ds.b 1          ; edges OR'd here by EVERY VBlank (incl. lag)
Ctrl_2_Press_Accum:     ds.b 1          ; latched into Ctrl_*_Press by the non-lag handler

; -----------------------------------------------
; RNG
; -----------------------------------------------
RNG_Seed:               ds.l 1

; -----------------------------------------------
; VBlank dispatch (§1 — VDP Pipeline)
; -----------------------------------------------
VInt_Ptr:               ds.l 1          ; pointer to current VBlank handler
VBlank_Ready:           ds.b 1          ; set by main loop, cleared by VBlank
                        ds.b 1          ; pad

; -----------------------------------------------
; DMA Queue (§1.1)
; Three priority sub-queues, contiguous in memory
; -----------------------------------------------
DMA_Queue:
DMA_Critical:           ds.b DMA_CRITICAL_SLOTS*DMAEntry_len
DMA_Critical_End:
DMA_Important:          ds.b DMA_IMPORTANT_SLOTS*DMAEntry_len
DMA_Important_End:
DMA_Deferrable:         ds.b DMA_DEFERRABLE_SLOTS*DMAEntry_len
DMA_Deferrable_End:
DMA_Queue_End:

DMA_Critical_Slot:      ds.w 1          ; next free Critical slot
DMA_Important_Slot:     ds.w 1          ; next free Important slot
DMA_Deferrable_Slot:    ds.w 1          ; next free Deferrable slot

DMA_Budget_Default:     ds.w 1          ; per-frame byte budget (set at boot)
DMA_Budget_Remaining:   ds.w 1          ; remaining bytes this frame

; -----------------------------------------------
; RAM Buffers and Dirty Flags (§1.3)
; -----------------------------------------------
Palette_Buffer:         ds.b 128        ; 4 lines × 32 bytes
Palette_Dirty:          ds.b 1          ; bits 0-3 = per-line dirty
                        ds.b 1          ; pad

Sprite_Table_Buffer:    ds.b 640        ; 80 entries × 8 bytes
Sprite_Table_Dirty:     ds.b 1
                        ds.b 1          ; pad

Hscroll_Buffer:         ds.b 896        ; 224 lines × 4 bytes (FG + BG)
                        ds.b 2          ; reserved (pad)

Vscroll_Factor:         ds.l 1          ; FG word + BG word

; -----------------------------------------------
; Parallax state (§4.6) — ~126 bytes
; -----------------------------------------------
Parallax_State:
Parallax_Deform_Phase_FG:    ds.w 1     ; (frame_counter * speed_fg) & $FF
Parallax_Deform_Phase_BG:    ds.w 1
Parallax_V_Deform_Phase_BG:  ds.w 1     ; for animated per-column V-scroll
Parallax_Current_Scroll_A:   ds.w MAX_PARALLAX_BANDS  ; lerp accumulators, Plane A
Parallax_Current_Scroll_B:   ds.w MAX_PARALLAX_BANDS  ; Plane B
Parallax_Current_Vscroll_BG: ds.w 1
Parallax_Current_Config:     ds.l 1     ; ptr to active parallax_config
Parallax_Target_Config:      ds.l 1     ; ptr to incoming during transition
Parallax_Transition_Frames:  ds.b 1     ; frames remaining; 0 = stable
Parallax_Snap_Pending:       ds.b 1     ; 1 = next Update writes target_scroll directly to current (skip lerp)
; Per-section parallax: section grid coords under the camera centre on the
; previous frame. A change in either is a section-boundary crossing, which
; re-selects the active config (Sec_sec_parallax_config, Act fallback) via
; Parallax_CheckBoundary. Seeded to $FF in Parallax_Init so the first frame
; always re-selects (a no-op against the config init already chose).
Parallax_Prev_Sec_X:         ds.b 1
Parallax_Prev_Sec_Y:         ds.b 1
Parallax_Vscroll_Column_Buf: ds.b 80    ; 40 VSRAM entries × 2 bytes
; Per-frame screen-space band view (Step 4a): the config's plane-space band
; list rotated by Vscroll_BG, tops rebased to screen cells. Fillers consume
; this (or the config's own arrays when vshift = 0).
Parallax_Shadow_Bands:       ds.b band_entry_len*MAX_PARALLAX_BANDS
Parallax_Shadow_Scroll_A:    ds.w MAX_PARALLAX_BANDS
Parallax_Shadow_Scroll_B:    ds.w MAX_PARALLAX_BANDS
Parallax_State_End:

; Driver-keyed BG tile-band animation (engine/level/bg_anim.asm)
BgAnim_LastStep:        ds.w 4          ; per band: last DMA'd step; -1 = none yet
                                        ; (size must match BGANIM_MAX_BANDS)

; -----------------------------------------------
; Static DMA Entries (§1.5)
; Pre-computed 14-byte entries for fixed transfers
; -----------------------------------------------
Static_Pal_Line0:       ds.b DMAEntry_len
Static_Pal_Line1:       ds.b DMAEntry_len
Static_Pal_Line2:       ds.b DMAEntry_len
Static_Pal_Line3:       ds.b DMAEntry_len
Static_Sprite_DMA:      ds.b DMAEntry_len
Static_Hscroll_Cell:    ds.b DMAEntry_len   ; §4.6 — 112-byte HScroll per-cell mode
Static_Hscroll_Line:    ds.b DMAEntry_len   ; §4.6 — 896-byte HScroll per-line mode

; -----------------------------------------------
; Debug profiling (§1.7) — zero in release builds
; -----------------------------------------------
    ifdef __DEBUG__
DMA_Bytes_ThisFrame:    ds.w 1
DMA_Peak_Critical:      ds.w 1
DMA_Peak_Important:     ds.w 1
DMA_Peak_Deferrable:    ds.w 1
DMA_Overflow_Count:     ds.w 1
Lag_Frame_Count:        ds.l 1

Prof_RunObjects:        ds.w 1          ; V counter lines spent in RunObjects
Prof_TouchResponse:     ds.w 1          ; V counter lines spent in TouchResponse
Prof_RenderSprites:     ds.w 1          ; V counter lines spent in Render_Sprites
Prof_FrameTotal:        ds.w 1          ; V counter lines for full game loop
Prof_Peak_RunObjects:   ds.w 1          ; peak RunObjects across all frames
Prof_Peak_Touch:        ds.w 1          ; peak TouchResponse
Prof_Peak_Render:       ds.w 1          ; peak Render_Sprites
Prof_Peak_Frame:        ds.w 1          ; peak full frame
Prof_Dynamic_Used:      ds.w 1          ; dynamic slots in use this frame
Prof_Effect_Used:       ds.w 1          ; effect slots in use this frame

; Debug harness: scene-pin flag. Nonzero = GameState_OJZScroll_Update skips
; Camera_Update + EntityWindow_Scan so a write_memory camera+ring scene
; survives (R-A1 ring-cull boundary verification). See
; docs/superpowers/specs/2026-07-12-ojz-scene-pin-debug-hook-design.md.
Debug_Scene_Freeze:     ds.b 1          ; 0 = normal, nonzero = pin OJZScroll scene
                        ds.b 1          ; pad to even (keep the __DEBUG__ block word-aligned)
    endif

; -----------------------------------------------
; Object System (§3)
; -----------------------------------------------

; Object RAM — all slots contiguous, stride = SST_len ($50)
Object_RAM:
; Reserved tracked-entity slots — engine camera/rings/collision address slot
; 0/1 directly; the game's player code claims them at spawn.
Player_1:               ds.b SST_len
Player_2:               ds.b SST_len
Dynamic_Slots:          ds.b SST_len * NUM_DYNAMIC
System_Slots:           ds.b SST_len * NUM_SYSTEM
Effect_Slots:           ds.b SST_len * NUM_EFFECTS
Object_RAM_End:

; Free slot stacks — word arrays of SST addresses, one per pool
Dynamic_Free_Stack:     ds.w NUM_DYNAMIC
Dynamic_Free_SP:        ds.w 1

Effect_Free_Stack:      ds.w NUM_EFFECTS
Effect_Free_SP:         ds.w 1

; -----------------------------------------------
; Sprite Rendering (§3.5)
; -----------------------------------------------

; Priority band lists — each band holds up to SPRITES_PER_BAND object addresses
Sprite_Bands:           ds.w SPRITES_PER_BAND * PRIORITY_BANDS
Sprite_Band_Counts:     ds.b PRIORITY_BANDS
                                        ; PRIORITY_BANDS=8, already even — no pad needed

; Total sprites rendered this frame
Sprites_Rendered:       ds.w 1

; Link-order cycling frame counter (incremented each Render_Sprites call)
Sprite_Cycle_Counter:   ds.w 1

; Sprite X=0 masking configuration
; Set SpriteMask_Y to VDP Y position (screen Y + 128) and SpriteMask_Height
; to the number of scanlines to mask. Set SpriteMask_After_Band to the band
; index AFTER which mask sprites are inserted (e.g. 7 = after HUD band).
; SpriteMask_Y = 0 disables masking.
SpriteMask_Y:           ds.w 1          ; VDP Y position of mask top (0 = disabled)
SpriteMask_Height:      ds.w 1          ; scanlines to cover
SpriteMask_After_Band:  ds.b 1          ; insert after this band (0-7)
                        ds.b 1          ; pad

; Scanline band sprite budgeting (§3.5)
; 7 bands of 32 scanlines — tracks accumulated sprite pieces per band
Scanline_Band_Sprites:  ds.b SCANLINE_BANDS
                        ds.b 1          ; pad to even (7+1=8)

; -----------------------------------------------
; Camera (stub for §3, real implementation in §4)
; -----------------------------------------------
Camera_X:               ds.l 1          ; 16.16 camera X position
Camera_Y:               ds.l 1          ; 16.16 camera Y position

; Frame-constant biased camera (Render_Sprites): Camera_{X,Y} integer minus the
; VDP +128 SAT offset, computed once per render frame so the four Emit loops
; drop the per-piece `addi #128`. Integer words only (the fold is on the
; screen-position integer, not the 16.16 world position).
Camera_X_Biased:        ds.w 1          ; Camera_X(int) - VDP_SPRITE_X_OFFSET
Camera_Y_Biased:        ds.w 1          ; Camera_Y(int) - VDP_SPRITE_Y_OFFSET

; Game pause / freeze flag
Game_Paused:            ds.b 1
                        ds.b 1          ; pad

; -----------------------------------------------
; Level System (§4)
; -----------------------------------------------

; Deferred plane write buffer — game loop appends, VBlank drains
Plane_Buffer:           ds.b PLANE_BUFFER_SIZE   ; 1536 bytes
Plane_Buffer_Ptr:       ds.w 1          ; byte offset (0 = empty)

; Camera position history — 64 frames × 4 bytes (X.w, Y.w)
Pos_table:              ds.b 256
H_scroll_frame_offset:  ds.b 1          ; camera lag depth (0 = no lag)
                        ds.b 1          ; pad

; Camera parameters
Camera_Deadzone_Base:   ds.w 1          ; base deadzone width in pixels
Camera_Lookahead:       ds.w 1          ; zone-default lookahead pixels
Camera_Pan_Offset:      ds.w 1          ; current extended lookahead pan
Camera_Hold_Frames:     ds.b 1          ; frames the camera holds position (game code sets it,
                                        ; e.g. spindash charge). Camera_Update tests it each
                                        ; frame to suppress camera movement, then decrements.
                        ds.b 1          ; pad

; -----------------------------------------------
; 2D Tile Cache metadata (§4.7 — .w addressable)
; -----------------------------------------------
Cache_Left_Col:         ds.w 1          ; world tile col of leftmost valid column
Cache_Head_Col:         ds.w 1          ; world tile col of rightmost valid column
Cache_Top_Row:          ds.w 1          ; world tile row of topmost valid row
Cache_Bottom_Row:       ds.w 1          ; world tile row of bottommost valid row
Cache_Origin_Col:       ds.w 1          ; physical col index where Cache_Left_Col maps (circular)
Cache_Origin_Row:       ds.w 1          ; physical row index where Cache_Top_Row maps (circular; kept even)
Cache_Fill_Last_Frame:  ds.w 1          ; Frame_Counter of last fill (cascade prevention)
Cache_Fill_Resume_Col:  ds.w 1          ; partial FillColumn resume column ($FFFF = none pending)
Cache_Fill_Resume_Row:  ds.w 1          ; partial FillColumn resume row (valid when Resume_Col set)
Cache_Fill_Budget:      ds.w 1          ; per-frame block decompress allowance (shared: columns + rows)
Cache_Fill_RowResume_Row: ds.w 1        ; partial FillRow resume world row ($FFFF = none)
Cache_Fill_RowResume_Col: ds.w 1        ; partial FillRow resume col cursor
Cache_Fill_Rows_Left:   ds.w 1          ; rows-this-frame cap countdown (reset to VFILL_ROWS_PER_FRAME)
Cache_Prev_Cam_Row:     ds.w 1          ; last frame's camera world tile row (vertical prefetch direction)
; Horizontal prefetch state (unified direction-aware prefetch, §4.7).
Cache_Prev_Cam_X:       ds.w 1          ; last frame's camera px (low word) — H prefetch delta/hysteresis
Cache_H_Pfx_Dir:        ds.w 1          ; latched H prefetch direction (0=none, +1=right, -1=left)
Cache_H_Pfx_Accum:      ds.w 1          ; net opposite-motion px accumulator (>=0) for the hysteresis flip
Cache_Pfx_Row_Target:   ds.w 1          ; this-frame vertical prefetch target row ($FFFF = none) — corner input
Cache_Pfx_Col_Target:   ds.w 1          ; this-frame horizontal prefetch target col ($FFFF = none) — corner input
Cache_Pfx_Skip_Armed:   ds.w 1          ; 1 = prefetch skipped last frame (bound: never skip two running)
Cache_Pfx_Lag_Flag:     ds.w 1          ; set =1 by the tile-cache frame gate when Frame_Counter
                                        ; advanced by >1 since the last fill (a frame lagged in
                                        ; between — trailing detect, release-safe); the prefetch
                                        ; H4 gate consumes it (skip this frame if the prev frame lagged)

; Block staging metadata — keys parallel to Block_Stage_Buffers slots
; Key format: sec_x.b | sec_y.b | block_index.w ($FFFFFFFF = empty)
Block_Stage_Keys:       ds.l BLOCK_STAGE_SLOTS
Block_Stage_Next:       ds.w 1          ; next round-robin slot to evict

; Row streaming state (vertical)
Section_Top_Row_Written:  ds.w 1
Section_Bottom_Row_Written: ds.w 1

; Section streaming state
Section_Plane_Dirty:    ds.b 1          ; full plane redraw pending (level init + cache recovery)
                        ds.b 1          ; pad to even (Section_Plane_Dirty is 1 odd byte)

; Column streaming state — world tile columns (Camera_X/8 domain)
; Right: last tile col written to nametable on the right side of view
; Left:  last tile col written to nametable on the left side of view
Section_Right_Col_Written: ds.w 1
Section_Left_Col_Written:  ds.w 1

; §4.2 preview: cached neighbor section data pointers.
; Set at teleport/init; NULL if no neighbor exists (act boundary).
Section_Fwd_Neighbor_Data: ds.l 1
Section_Bwd_Neighbor_Data: ds.l 1

; Dynamic tile override (16 entries × 6 bytes: col.w, row.w, new_tile.w)
Tile_Override_Table:    ds.b 96

; -----------------------------------------------
; Entity System (§4.9 — camera-driven sliding window)
; -----------------------------------------------

; Unified ring buffer — 128 entries × 6 bytes (dc.w x, y; dc.b section_id, list_index)
Ring_Buffer:            ds.b MAX_RING_BUFFER * RING_BUFFER_ENTRY_SIZE  ; 768 bytes

; Ring count (unified) + buffer diagnostics (reset by RingBuffer_Clear at level init)
Ring_Count:             ds.b 1
Ring_HighWater:         ds.b 1          ; max Ring_Count observed
Ring_Add_Dropped:       ds.b 1          ; RingBuffer_Add failures (buffer full) — DEBUG-fatal
                        ds.b 1          ; pad

; Entity scan state — 4 tracked sections × EntityScanState_len bytes
Entity_Scan_State:      ds.b MAX_TRACKED_SECTIONS * EntityScanState_len

; Ring state
Ring_Counter:           ds.w 1          ; total collected rings (player HUD)
Ring_Anim_Frame:        ds.b 1          ; global ring animation counter (0-3)
Ring_Anim_Timer:        ds.b 1          ; countdown to next animation tick

; Entity window tracking
Entity_Window_Active:   ds.b 1          ; 4-bit entry validity mask (bit n = entry n valid)
Entity_Window_Center_ID: ds.b 1         ; section_id of rolling bitmask center
Entity_Window_Anchor:   ds.b 2          ; absolute (sec_x0, sec_y0) of entry 0 — slide trigger + teleport invariance
Entity_Window_OriginX:  ds.w 1          ; column-0 origin base, world px (sec_x0 * SECTION_SIZE)
Entity_Window_OriginY:  ds.w 1          ; row-0 origin base, world px (sec_y0 * SECTION_SIZE)
Entity_Loaded_Masks:    ds.b MAX_TRACKED_SECTIONS * ENTITY_LOADED_SLOT_SIZE ; 128B — per-entry ring/obj loaded bits (§4.9 ph2)
Entity_Mask_Scratch:    ds.b 4+MAX_TRACKED_SECTIONS*ENTITY_LOADED_SLOT_SIZE ; 132B (even) — slide snapshot: 4 old section ids + 4×32B old masks (EntityWindow_Slide)
Camera_Y_Coarse_Prev:   ds.w 1          ; camY & $FF80 at last vertical re-scan

; Rolling collected/killed bitmask — 9 slots × 34 bytes
Ring_Collected_Window:  ds.b COLLECTED_WINDOW_SLOTS * COLLECTED_SLOT_SIZE  ; 306 bytes
                        ds.b 2          ; pad to even

; Respawn park (§4.9.4) — 4 entries × 33 bytes (byte-packed, copied bytewise)
Ring_Collected_Park:    ds.b COLLECTED_PARK_SLOTS * COLLECTED_PARK_ENTRY_SIZE ; 132 bytes
                        ds.b (COLLECTED_PARK_SLOTS*COLLECTED_PARK_ENTRY_SIZE)&1 ; pad to even (132 — none needed)
Collected_Park_Next:    ds.b 1          ; rolling write index (0..COLLECTED_PARK_SLOTS-1)
                        ds.b 1          ; pad to even

; Active level pointer
Current_Act_Ptr:        ds.l 1

; -----------------------------------------------
; Sound driver runtime state
Ring_Sfx_Speaker:       ds.b 1          ; toggles 0/1 each ring collect; 0→LEFT, 1→RIGHT
                        ds.b 1          ; pad to even
; A2 fix: 68k-side pending-SFX ring. Sound_PlaySFX enqueues here; Sound_DrainSfxRing
; (game_loop, post-VSync) posts ONE id/frame into the single-byte SND_REQ_SFX mailbox
; once the Z80 has cleared it, so two SFX requested in one 68k frame are delivered over
; two frames (both reach the Z80 priority queue) instead of the 2nd clobbering the 1st.
; Empty == (Rd == Wr); cleared to 0 by boot.asm's 64KB Work-RAM clear (frame-1 = empty).
Sfx_Ring_Buf:           ds.b SFX_RING_DEPTH   ; pending SFX ids (raw, as posted today)
Sfx_Ring_Wr:            ds.b 1                 ; write cursor (0..SFX_RING_MASK)
Sfx_Ring_Rd:            ds.b 1                 ; read cursor  (0..SFX_RING_MASK)
                        ; SFX_RING_DEPTH(8)+2 = 10 bytes, even — no pad needed

; Sound driver debug mirror
; Declared unconditionally (160 bytes, negligible) so the RAM layout is
; identical between DEBUG and release. Only WRITTEN under __DEBUG__ +
; SOUND_DRIVER_ENABLED + SOUND_DBG_MIRROR (debug/sound_debug.asm). Lets the
; Exodus MCP — which can read 68k RAM but not Z80 RAM at $A00000 — observe the
; driver's mailbox+status+sequencer state by reading this symbol.
; Sized for the 5-channel sequencer window + trace ring. SeqChannel is 14 B
; (includes repeat state): 5 channels * 14 = 70, so header+ch window = 78, and
; 64 + 78 + 32 (trace) = 174 <= 176 (kept EVEN with a 2-byte margin).
; -----------------------------------------------
Sound_Dbg_Mirror:       ds.b 176        ; DEBUG: [0..47] Z80 mailbox/status ($1F00..$1F2F), [48..63] playback state ($18F0..$18FF), [64..71] seq header, [72..141] 5 SeqChannel slots (FM1/FM2/PSG1/PSGN/DAC, 14 B each), [142..173] trace ring (see debug/sound_debug.asm)

; -----------------------------------------------
; Object-pool occupancy — the dynamic-pool "run objects list"
; (docs/superpowers/specs/2026-07-11-object-pool-occupancy-design.md)
; Word SST-addresses of the live DYNAMIC slots, in SPAWN order, + count +
; a frame-end-compaction dirty flag. SST code_addr==0 stays the single
; source of truth; this list is a conservative over-approximation (may
; briefly hold dead slots, never misses a live one — walkers keep a tst.w
; guard) that lets RunObjects / TouchResponse / EntityWindow skip the ~37
; typically-empty dynamic slots instead of sweeping all 40.
; Placed at the RAM TAIL (not beside the free stacks): the addition then
; ripples ZERO existing RAM addresses, so no ported module's byte gate moves
; from the layout change — only the code edits do. Genesis RAM has no
; locality cost, so tail placement is free.
; -----------------------------------------------
Dynamic_Live:           ds.w NUM_DYNAMIC ; 80B — live dynamic slot addresses, spawn order
Dynamic_Live_Count:     ds.w 1           ; live entries (0..NUM_DYNAMIC)
Dynamic_Live_Dirty:     ds.b 1           ; a dynamic deletion happened; compact at frame end
    ifdef __DEBUG__
; A2 walk-live rail (retro-fix-audit-1, item 1/12): set while a dynamic
; live-list walk holds a cursor into Dynamic_Live (.run_culled /
; RunObjects_Frozen / TouchResponse / EntityWindow_DespawnObjects), asserted
; CLEAR at CompactDynamicLive entry — a set flag there means a mid-walk
; compaction is about to move entries under a live cursor (the A2 hazard).
; Occupies the release pad slot, so Engine_RAM_End is shape-INVARIANT (no
; downstream RAM address moves in either shape).
Dynamic_Live_Walking:   ds.b 1           ; DEBUG-only: a dynamic live-list walk is in progress
    else
                        ds.b 1           ; pad to even
    endif

; Occupancy amendment A2 (overflow latch, spec §9) — RELEASE (both shapes).
; AllocDynamic at a full live list (count==NUM_DYNAMIC) latches the popped slot
; word here instead of compacting mid-frame under a live walker; RunObjects' tail
; drains it (one CompactDynamicLive, then append the latched entries IN ALLOC
; ORDER, preserving spawn-order dispatch). DeleteObject zeroes a latch entry too
; (the "exactly once" invariant extends to the latch). Placed after the
; DEBUG/pad byte so both shapes carry it at the same offset (Engine_RAM_End moves
; identically in both). Word count for even alignment.
Dynamic_Live_Pending:       ds.w NUM_DYNAMIC_PENDING ; latched slot addresses (alloc order)
Dynamic_Live_Pending_Count: ds.w 1                   ; latch occupancy (0..NUM_DYNAMIC_PENDING)

; -----------------------------------------------
; Prefetch scan memoize — a generation word plus one keyed memo per axis. The
; vertical (.pfx_scan) and horizontal (.cs_scan) prefetch scans skip their
; FindStagedBlock all-hits re-probe walk when the target line, cache bounds, and
; generation still match the last recorded all-staged result. Every staging claim
; (TileCache_DecompressBlock) and every TileCache_InvalidateStaging bumps the
; generation, so a memo survives only across frames in which no block was staged —
; exactly when the walk would re-probe to all hits and skipping is behaviour-
; identical. Placed at the RAM tail: the addition ripples ZERO existing RAM
; addresses (only Engine_RAM_End + game RAM shift), so no ported module's byte gate
; moves from the layout change.
; -----------------------------------------------
Block_Stage_Gen:        ds.w 1 ; bumped on every staging claim + invalidate; the memo generation key
Pfx_Memo_Row:           ds.w 1 ; vertical scan: memoized target row
Pfx_Memo_L:             ds.w 1 ; vertical scan: Cache_Left_Col at record (bounds guard — load-bearing)
Pfx_Memo_H:             ds.w 1 ; vertical scan: Cache_Head_Col at record (bounds guard — load-bearing)
Pfx_Memo_Gen:           ds.w 1 ; vertical scan: Block_Stage_Gen at record ($FFFF sentinel = no memo)
Cs_Memo_Col:            ds.w 1 ; horizontal scan: memoized target col
Cs_Memo_T:              ds.w 1 ; horizontal scan: Cache_Top_Row at record (bounds guard — load-bearing)
Cs_Memo_B:              ds.w 1 ; horizontal scan: Cache_Bottom_Row at record (bounds guard — load-bearing)
Cs_Memo_Gen:            ds.w 1 ; horizontal scan: Block_Stage_Gen at record ($FFFF sentinel = no memo)

; -----------------------------------------------
; HBlank vector slot (§0.10) — the IRQ4 vector points DIRECTLY here. Holds a
; 6-byte executable instruction: idle rte ($4E73) when no raster handler is
; installed, or `jmp handler.l` ($4EF9 + 4-byte target) when HBlank_Install arms
; one. Entered with no wrapper — the handler owns its save/restore + rte.
; Placed at the RAM TAIL (not beside the interrupt-dispatch reserve above): the
; addition then ripples ZERO existing RAM addresses — only Engine_RAM_End + game
; RAM shift. Genesis RAM has no locality cost, so tail placement is free.
; -----------------------------------------------
HBlank_Vector_Slot:     ds.b 6

; -----------------------------------------------
; Block staging data pointers (§4.7) — one per staging slot, parallel to
; Block_Stage_Keys. TileCache_DecompressBlock writes the slot's staged-data
; base here at claim time; TileCache_FindStagedBlock returns it. A compressed
; block points at its RAM slot in Block_Stage_Buffers; a raw block points
; straight at the uncompressed ROM block; an empty block points at the shared
; zero page below. Consumers (CopyBlockColumn / FillRow) only READ through the
; pointer, so ROM / zero-page targets are safe. Placed at the RAM TAIL: the
; addition ripples ZERO existing RAM addresses (only Engine_RAM_End + game RAM).
Block_Stage_Ptrs:       ds.l BLOCK_STAGE_SLOTS   ; 64 bytes — per-slot staged data pointer

; Shared all-zero staged block — every empty (blank / out-of-grid) block points
; here instead of paying a 768-byte zero-fill. BLOCK_RAW_SIZE bytes
; (nametable + collision), word-even, in the boot-cleared 64KB Work RAM; never
; written after boot (the staged-pointer read-only contract keeps it zero).
Block_Stage_ZeroPage:   ds.b BLOCK_RAW_SIZE      ; 768 bytes — read-only zero staged block

; -----------------------------------------------
; Engine RAM ends here — game RAM continues from Engine_RAM_End
; (games/<game>/config/ram.asm phases from this address).
; -----------------------------------------------
Engine_RAM_End:

        if Engine_RAM_End >= SYSTEM_STACK
          error "Engine RAM overflow into stack by \{Engine_RAM_End - SYSTEM_STACK} bytes!"
        endif

        if (Object_RAM & $FFFF) < $8000
          error "Object_RAM .w address $\{Object_RAM & $FFFF} has bit 15 clear — will resolve to ROM"
        endif

        dephase
