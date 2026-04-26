; RAM layout via phase/dephase
; Lower 32KB ($FFFF0000+) for large buffers — .l addressing required
; Upper 32KB ($FFFF8000+) for hot data — .w addressing for speed

; -----------------------------------------------
; Lower RAM — large, infrequently-accessed buffers
; -----------------------------------------------
        phase $FFFF0000

Decomp_Buffer:          ds.b DECOMP_BUFFER_SIZE
Decomp_Buffer_End:

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
; Static DMA Entries (§1.5)
; Pre-computed 14-byte entries for fixed transfers
; -----------------------------------------------
Static_Pal_Line0:       ds.b DMAEntry_len
Static_Pal_Line1:       ds.b DMAEntry_len
Static_Pal_Line2:       ds.b DMAEntry_len
Static_Pal_Line3:       ds.b DMAEntry_len
Static_Sprite_DMA:      ds.b DMAEntry_len

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

; Section slot state
; Slot_Origins: 4 slots × 8 bytes = [origin_x.l][origin_y.l] each
Slot_Origins:           ds.b 32
; Slot_Section_Map: 4 slots × 2 bytes = [section_x.b][section_y.b] each
Slot_Section_Map:       ds.b 8

; Section streaming state
Section_Preload_Flags:  ds.b 1          ; bits: fwd/bwd/up/dn preloaded
Section_Teleport_Guard: ds.b 1          ; cooldown after teleport (frames)

; Per-section streaming state (§2 A.4) — one byte per section
; (SS_IDLE / SS_STREAMING / SS_RESIDENT). Indexed by flat section_id
; (sec_y * grid_w + sec_x). Sized to OJZ act 1's 9 sections; pad to 16.
Section_Stream_State:   ds.b 16         ; up to 16 sections; even-aligned
Streaming_Active_Buffer: ds.b 1         ; 0 = next stream uses A; 1 = next uses B
                        ds.b 1          ; pad to even

; Column streaming state — engine tile columns (Camera_X/8 domain)
; Right: last tile col written to nametable on the right side of view
; Left:  last tile col written to nametable on the left side of view
Section_Right_Col_Written: ds.w 1
Section_Left_Col_Written:  ds.w 1

; Dynamic tile override (16 entries × 6 bytes: col.w, row.w, new_tile.w)
Tile_Override_Table:    ds.b 96

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
; CROSS_RESET_RAM (fixed address near top of RAM)
; Survives soft reset, cleared only on cold boot
; -----------------------------------------------
CROSS_RESET_RAM:            = $FFFFFE00
CROSS_RESET_MAGIC_ADDR:     = $FFFFFE00
CROSS_RESET_MAGIC_END:      = $FFFFFE04
CROSS_RESET_RAM_END:        = $FFFFFF00

        dephase
