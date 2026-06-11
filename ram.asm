; RAM layout via phase/dephase
; Lower 32KB ($FFFF0000+) for large buffers — .l addressing required
; Upper 32KB ($FFFF8000+) for hot data — .w addressing for speed

; -----------------------------------------------
; Lower RAM — 2D tile cache, block staging, streaming buffers (§4.7)
; Replaces Decomp_Buffer after level init. LoadArt_Compressed still
; writes here during init (display off, before cache is populated).
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

; Keep Decomp_Buffer as alias for LoadArt_Compressed backward compat
Decomp_Buffer = Tile_Cache_Nametable
Decomp_Buffer_End = Tile_Cache_Nametable + TILE_CACHE_NT_SIZE

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
HBlank_Handler_Ptr:     ds.l 1

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
Ctrl_1_Press:           ds.b 1
Ctrl_2_Held:            ds.b 1
Ctrl_2_Press:           ds.b 1

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
Hscroll_Dirty_Start:    ds.b 1          ; first dirty scanline ($FF = clean)
Hscroll_Dirty_End:      ds.b 1          ; last dirty scanline

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
Parallax_Pad:                ds.b 2
Parallax_Vscroll_Column_Buf: ds.b 80    ; 40 VSRAM entries × 2 bytes
Parallax_State_End:

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
    endif

; -----------------------------------------------
; Object System (§3)
; -----------------------------------------------

; Object RAM — all slots contiguous, stride = SST_len ($50)
Object_RAM:
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

; Spawn guard counter (reset each frame)
Spawn_Count:            ds.w 1

; -----------------------------------------------
; Sprite Rendering (§3.5)
; -----------------------------------------------

; Priority band lists — each band holds up to SPRITES_PER_BAND object addresses
Sprite_Bands:           ds.w SPRITES_PER_BAND * PRIORITY_BANDS
Sprite_Band_Counts:     ds.b PRIORITY_BANDS
                                        ; PRIORITY_BANDS=8, already even — no pad needed

; Sprite link counter (next VDP sprite index to assign)
Sprite_Link_Next:       ds.w 1

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

; Game pause / freeze flag
Game_Paused:            ds.b 1
                        ds.b 1          ; pad

; -----------------------------------------------
; Level System (§4 Phase 1)
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
                        ds.w 1          ; pad

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
Cache_Prev_Cam_Row:     ds.w 1          ; last frame's camera world tile row (prefetch direction)

; Block staging metadata — keys parallel to Block_Stage_Buffers slots
; Key format: sec_x.b | sec_y.b | block_index.w ($FFFFFFFF = empty)
Block_Stage_Keys:       ds.l BLOCK_STAGE_SLOTS
Block_Stage_Next:       ds.w 1          ; next round-robin slot to evict

; Row streaming state (vertical)
Section_Top_Row_Written:  ds.w 1
Section_Bottom_Row_Written: ds.w 1

; Section slot state
; Slot_Origins: 4 slots × 8 bytes = [origin_x.l][origin_y.l] each
Slot_Origins:           ds.b 32
; Slot_Section_Map: 4 slots × 2 bytes = [section_x.b][section_y.b] each
Slot_Section_Map:       ds.b 8

; Section streaming state
Section_Preload_Flags:  ds.b 1          ; bits: fwd/bwd/up/dn preloaded
Section_Teleport_Guard: ds.b 1          ; anti-oscillation flag (cleared when player leaves threshold)
Section_Plane_Dirty:    ds.b 1          ; §4.2: full plane redraw pending (level init + cache recovery; teleports are pure rebases and never set it)
                        ds.b 1          ; pad to even

; Per-section streaming state (§2 A.4) — one byte per section
; (SS_IDLE / SS_RESIDENT). Indexed by flat section_id
; (sec_y * grid_w + sec_x). Per-act build asserts enforce grid_w*grid_h <= MAX_ACT_SECTIONS.
Section_Stream_State:   ds.b MAX_ACT_SECTIONS   ; 48 sections max; even-aligned (48 is even)

; Column streaming state — engine tile columns (Camera_X/8 domain)
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

; Ring count (unified)
Ring_Count:             ds.b 1
                        ds.b 1          ; pad

; Entity scan state — 4 tracked sections × EntityScanState_len bytes
Entity_Scan_State:      ds.b MAX_TRACKED_SECTIONS * EntityScanState_len

; Ring state
Ring_Counter:           ds.w 1          ; total collected rings (player HUD)
Ring_Anim_Frame:        ds.b 1          ; global ring animation counter (0-3)
Ring_Anim_Timer:        ds.b 1          ; countdown to next animation tick

; Entity window tracking
Entity_Window_Active:   ds.b 1          ; number of tracked sections (0-4)
Entity_Window_Center_ID: ds.b 1         ; section_id of rolling bitmask center

; Rolling collected/killed bitmask — 9 slots × 34 bytes
Ring_Collected_Window:  ds.b COLLECTED_WINDOW_SLOTS * COLLECTED_SLOT_SIZE  ; 306 bytes
                        ds.b 2          ; pad to even

; Active level pointer
Current_Act_Ptr:        ds.l 1

RAM_End:

        if RAM_End >= SYSTEM_STACK
          error "RAM overflow into stack by \{RAM_End - SYSTEM_STACK} bytes!"
        endif

        if (Object_RAM & $FFFF) < $8000
          error "Object_RAM .w address $\{Object_RAM & $FFFF} has bit 15 clear — will resolve to ROM"
        endif

; -----------------------------------------------
; CROSS_RESET_RAM — top 256 bytes of RAM ($FFFFFF00-$FFFFFFFF)
; Survives soft reset, cleared only on cold boot.
; Lives ABOVE the stack base (SYSTEM_STACK = $FFFFFF00, grows down),
; so stack pushes can never reach it. Previously sat at $FE00-$FEFF —
; directly in the stack's path, 252 bytes of depth from corruption,
; while this top page went unused.
; -----------------------------------------------
CROSS_RESET_RAM:            = $FFFFFF00
CROSS_RESET_MAGIC_ADDR:     = $FFFFFF00
CROSS_RESET_MAGIC_END:      = $FFFFFF04
CROSS_RESET_RAM_END:        = $00000000     ; exclusive end (wraps at top of RAM)

        dephase
