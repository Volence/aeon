; Hardware constants and system definitions

; -----------------------------------------------
; Hardware addresses
; -----------------------------------------------
Z80_RAM                 = $A00000
Z80_RAM_END             = $A02000       ; 8KB
Z80_BUS_REQUEST         = $A11100
Z80_RESET               = $A11200

VDP_DATA                = $C00000
VDP_CTRL                = $C00004
VDP_HV_COUNTER          = $C00008
PSG_PORT                = $C00011

HW_VERSION              = $A10001
HW_PORT_1_DATA          = $A10003
HW_PORT_2_DATA          = $A10005
HW_PORT_EXP_DATA        = $A10007
HW_PORT_1_CTRL          = $A10009
HW_PORT_2_CTRL          = $A1000B
HW_EXPANSION_CTRL       = $A1000D
HW_PORT_A_CTRL_FULL     = $A10008
HW_EXPANSION_CTRL_FULL  = $A1000C

TMSS_REGISTER           = $A14000

YM2612_A0               = $A04000
YM2612_D0               = $A04001
YM2612_A1               = $A04002
YM2612_D1               = $A04003

; -----------------------------------------------
; VDP access type constants (for vdpComm function)
; -----------------------------------------------
VRAM                    = %100001
CRAM                    = %101011
VSRAM                   = %100101
READ                    = %001100
WRITE                   = %000111
DMA                     = %100111

; -----------------------------------------------
; System constants
; -----------------------------------------------
SYSTEM_STACK            = $FFFFFF00

; -----------------------------------------------
; VRAM layout (tile indices)
; -----------------------------------------------
VRAM_PLANE_A            = $C000         ; Byte address (tile $600)
VRAM_PLANE_B            = $E000         ; Byte address (tile $700)
VRAM_SPRITE_TABLE       = $D800
VRAM_HSCROLL_TABLE      = $DC00
VRAM_WINDOW             = $F000

; Shared BG tile region (§2 A.5 T1/T2)
; Reserved permanent VRAM slot range for zone-wide BG tile art.
; Loaded once at level init and never overwritten by section transitions.
; Lives between FG section pools (which may grow up to ~slot 1279) and
; Plane A nametable (slot 1536).
BG_TILE_BASE_VRAM       = $A000         ; Byte address (slot 1280)
BG_TILE_BASE_SLOT       = BG_TILE_BASE_VRAM/32   ; 1280 — for nametable index remap
BG_TILE_CAPACITY        = 256           ; tiles ($A000..$BFFF = 8 KB)

; Plane size
PLANE_H_CELLS           = 64
PLANE_V_CELLS           = 64

; -----------------------------------------------
; Timing constants
; -----------------------------------------------
NTSC_TIMING_STEP        = $0100         ; 1.0 (8.8 fixed)
PAL_TIMING_STEP         = $0133         ; 1.2 (8.8 fixed, 6/5 ratio)

; -----------------------------------------------
; Controller button masks
; -----------------------------------------------
BUTTON_UP               = 1<<0          ; $01
BUTTON_DOWN             = 1<<1          ; $02
BUTTON_LEFT             = 1<<2          ; $04
BUTTON_RIGHT            = 1<<3          ; $08
BUTTON_B                = 1<<4          ; $10
BUTTON_C                = 1<<5          ; $20
BUTTON_A                = 1<<6          ; $40
BUTTON_START            = 1<<7          ; $80

; -----------------------------------------------
; CROSS_RESET_RAM
; -----------------------------------------------
CROSS_RESET_MAGIC       = 'INIT'

; -----------------------------------------------
; Game state IDs
; -----------------------------------------------
GS_BOOT                 = 0
GS_IDLE                 = 1

; -----------------------------------------------
; DMA Queue (§1.1)
; -----------------------------------------------
DMA_CRITICAL_SLOTS      = 8
DMA_IMPORTANT_SLOTS     = 12
DMA_DEFERRABLE_SLOTS    = 12
DMA_TOTAL_SLOTS         = DMA_CRITICAL_SLOTS+DMA_IMPORTANT_SLOTS+DMA_DEFERRABLE_SLOTS

DMA_BUDGET_NTSC         = 7200          ; usable DMA bytes per NTSC VBlank
DMA_BUDGET_PAL          = 15000         ; usable DMA bytes per PAL VBlank

; -----------------------------------------------
; Decompression (§2)
; -----------------------------------------------
TILE_SIZE               = 32            ; bytes per 8x8 4bpp tile
DECOMP_BUFFER_SIZE      = 32768         ; 32KB decompression work buffer

; -----------------------------------------------
; Object System (§3)
; -----------------------------------------------

; Slot counts per pool
NUM_PLAYERS             = 2
NUM_DYNAMIC             = 40
NUM_EFFECTS             = 16
NUM_SYSTEM              = 8
NUM_TOTAL_SLOTS         = NUM_PLAYERS+NUM_DYNAMIC+NUM_SYSTEM+NUM_EFFECTS

; Object code bank (ObjCodeBase aligned to $10000)
OBJ_CODE_BANK           = 1         ; moveq #1,d0; swap d0 → $00010000

; Sprite priority bands
PRIORITY_BANDS          = 8
SPRITES_PER_BAND        = 32

; Scanline-aware sprite budgeting
SCANLINE_BANDS          = 7             ; 224 / 32 = 7 bands of 32 scanlines each
SCANLINE_SPRITE_LIMIT   = 24           ; max sprite pieces per band before skipping

; Collision response types
COLLISION_NONE          = 0
COLLISION_ENEMY         = 1
COLLISION_BOSS          = 2
COLLISION_HURT          = 3
COLLISION_MONITOR       = 4
COLLISION_RING          = 5
COLLISION_BUBBLE        = 6
COLLISION_PROJECTILE    = 7
COLLISION_SOLID         = 8
COLLISION_SOLID_BREAK   = 9
COLLISION_SPRING        = 10
COLLISION_SOLID_HURT    = 11
COLLISION_TOUCH         = 12

; render_flags bits
RF_ONSCREEN             = 0         ; set by Draw_Sprite if visible
RF_XFLIP                = 1         ; horizontal flip
RF_YFLIP                = 2         ; vertical flip
RF_COORDMODE            = 3         ; 0 = world coords, 1 = screen coords

; status byte bits (SST_status)
; Bits 1-2 aligned with RF_XFLIP/RF_YFLIP for direct propagation.
; Player interpretation:
ST_XFLIP                = 1         ; = RF_XFLIP — facing left
ST_YFLIP                = 2         ; = RF_YFLIP — vertical flip
ST_IN_AIR               = 3         ; 1 = airborne (jumped or falling)
ST_ROLLING              = 4         ; 1 = in ball form
ST_ON_OBJECT            = 5         ; 1 = standing on a solid object
ST_PUSHING              = 6         ; 1 = pushing against object
ST_UNDERWATER           = 7         ; 1 = submerged
; Object interpretation (platforms use bits 3-6):
ST_P1_STANDING          = 3         ; 1 = player 1 standing on this object
ST_P2_STANDING          = 4         ; 1 = player 2 standing on this object
ST_P1_PUSHING           = 5         ; 1 = player 1 pushing this object
ST_P2_PUSHING           = 6         ; 1 = player 2 pushing this object

; Object definition format byte bits (Load_Object data blocks)
ODF_VELOCITY            = 0         ; dc.w x_vel, y_vel
ODF_COLLISION           = 1         ; dc.b width, height, collision_type, pad
ODF_ANIMATION           = 2         ; dc.l anim_table
ODF_SUBTYPE             = 3         ; flag only — copy caller's subtype to SST
ODF_RENDER_FLAGS        = 4         ; dc.b render_flags, pad
ODF_PRIORITY            = 5         ; dc.w priority

; Pre-built format byte combinations
OBJ_FMT_MINIMAL         = 0                                ; mappings + art_tile only
OBJ_FMT_STATIC          = (1<<ODF_COLLISION)|(1<<ODF_PRIORITY) ; + collision + priority
OBJ_FMT_MOVING          = OBJ_FMT_STATIC|(1<<ODF_VELOCITY) ; + velocity
OBJ_FMT_ANIMATED        = OBJ_FMT_STATIC|(1<<ODF_ANIMATION) ; + animation

; Execution culling distances (pixels from camera center)
CULL_DISTANCE_X         = $300      ; 768px — skip dynamic objects beyond this
CULL_DISTANCE_Y         = $200      ; 512px

; Spawn guard
MAX_SPAWNS_PER_FRAME    = 8

; Game state IDs (extend existing)
GS_OBJECT_TEST          = 2

; -----------------------------------------------
; §4 Level / World System
; -----------------------------------------------

; Section coordinate space
SECTION_SHIFT           = $1000     ; uniform shift applied on teleport (pixels)
SECTION_SIZE            = $0800     ; slot width/height in engine pixels
SLOT_ORIGIN_L           = $0200     ; left slot engine-space left edge
SLOT_ORIGIN_R           = $0A00     ; right slot engine-space left edge
SLOT_ORIGIN_U           = $0200     ; upper slot engine-space top edge
SLOT_ORIGIN_D           = $0A00     ; lower slot engine-space top edge
SECTION_FWD_THRESHOLD   = $1200     ; camera X → fire forward teleport
SECTION_BWD_THRESHOLD   = $0200     ; camera X → fire backward teleport
SECTION_FWD_PRELOAD     = $0E00     ; camera X → queue forward section art
SECTION_BWD_PRELOAD     = $0400     ; camera X → queue backward section art

; Nametable strips
STRIP_TILE_HEIGHT       = 48        ; rows per strip (0–47; row 48+ = sprite table)
STRIP_BYTE_SIZE         = STRIP_TILE_HEIGHT*2   ; 96 bytes per strip

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

; Plane buffer
PLANE_BUFFER_SIZE       = 1536      ; bytes (~22 column entries per frame)

; Camera
CAM_LOOKAHEAD_THRESHOLD = $0600     ; ground speed for pan enable
CAM_PAN_SPEED           = 2         ; pixels/frame pan rate
CAM_PAN_LIMIT           = 64        ; max pan pixels

; Section flags (sec_flags word bits)
SF_HAS_WATER            = 1<<0
SF_UNDERGROUND          = 1<<1
SF_NO_Y_WRAP            = 1<<2
SF_PRESERVE_STATE       = 1<<3

; Game state IDs (extend existing table)
GS_OJZ_SCROLL_TEST      = 3

; -----------------------------------------------
; Test VRAM allocation
; -----------------------------------------------
VRAM_TEST_OBJ           = $0001         ; tile index 1 (8 tiles for test art)
VRAM_TEST_SONIC         = $0010         ; tile index 16 (up to 25 tiles for Sonic frames)
