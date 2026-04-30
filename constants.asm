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
; Lives between FG section pools (which may grow up to ~slot 1023) and
; Plane A nametable (slot 1536).
;
; T2/T3 (per-section BG variation) requires holding the union of all
; sections' BG tiles simultaneously, since the region is loaded once at
; level init. 512 slots (16 KB) covers OJZ Act 1's measured worst-case
; (~344 tiles when all four section variants were authored during T2/T3
; verification). T1-only zones use ~218 of the 512 slots; the headroom is
; reserved for future T2/T3 zones.
BG_TILE_BASE_VRAM       = $8000         ; Byte address (slot 1024)
BG_TILE_BASE_SLOT       = BG_TILE_BASE_VRAM/32   ; 1024 — for nametable index remap
BG_TILE_CAPACITY        = 512           ; tiles ($8000..$BFFF = 16 KB)

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
RF_MULTISPRITE          = 4         ; (parent only) batch render via sibling-chain walk

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
SECTION_SHIFT           = $1000     ; teleport shift (pixels); exact slot width. Anti-oscillation handled by Section_Teleport_Guard (position-based suppression after teleport).
SECTION_SIZE            = $0800     ; slot width/height in engine pixels
SLOT_ORIGIN_L           = $0200     ; left slot engine-space left edge
SLOT_ORIGIN_R           = $0A00     ; right slot engine-space left edge
SLOT_ORIGIN_U           = $0200     ; upper slot engine-space top edge
SLOT_ORIGIN_D           = $0A00     ; lower slot engine-space top edge
; -- §4.2 preview-zone (24-col / 24-row edges on plane A + plane B) --
; Preview width covers the edge region visible as camera approaches the
; teleport boundary. 24 cols = 192 px = ~3/5 of screen width. Preview is
; streaming-integrated: Section_UpdateColumns extends its range into
; neighbor section strips (Section_Fwd/Bwd_Neighbor_Strips), so preview
; cols are written by the normal ring-buffer mechanism and only become
; visible as the camera reaches the boundary.
PREVIEW_COLS            = 24        ; nametable cols at FWD/BWD edges
PREVIEW_ROWS            = 24        ; nametable rows at TOP/BOT edges (vertical: stub for now)
PREVIEW_PIXELS          = PREVIEW_COLS*8    ; 192 px — used for camera clamp offset
SECTION_TILE_WIDTH      = SECTION_SIZE/8    ; 256 — tile cols per section
SECTION_FWD_THRESHOLD   = $1200     ; camera X → fire forward teleport
SECTION_BWD_THRESHOLD   = $0200     ; camera X → fire backward teleport
SECTION_FWD_PRELOAD     = $0E00     ; camera X → queue forward section art
SECTION_BWD_PRELOAD     = $0400     ; camera X → queue backward section art
; -- §4.2 deferred cold-load triggers (keep just-left section's art alive across teleport for preview) --
SECTION_DEFERRED_FWD_LOAD = $0600   ; camera X → fire deferred Sec_R load (slot 0 midpoint, post-FWD-teleport)
SECTION_DEFERRED_BWD_LOAD = $0C00   ; camera X → fire deferred Sec_L load (slot 1 quarter, post-BWD-teleport)

; Vertical thresholds (2D-ready, unreachable in 1D)
SECTION_UP_THRESHOLD    = $7FFF
SECTION_DOWN_THRESHOLD  = $7FFF
SECTION_UP_PRELOAD      = $7FFF
SECTION_DOWN_PRELOAD    = $7FFF

; Parallax (§4.6)
MAX_PARALLAX_BANDS         = 8
PARALLAX_TRANS_DEFAULT     = 16     ; default boundary lerp duration (frames)
PARALLAX_LERP_SHIFT        = 4      ; >>4 ≈ 16-frame convergence to ~95% — gentler slide on factor changes

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
STREAMING_BUFFER_SIZE   = 4096

; Per-section streaming state values (single byte per section)
SS_IDLE      = 0    ; not loaded, not streaming
SS_STREAMING = 1    ; decompressed + DMA queued, awaiting drain
SS_RESIDENT  = 2    ; in VRAM, valid

; Section_Preload_Flags bit definitions
SPF_FWD_PRELOADED = 0       ; bit 0: forward neighbour streamed
SPF_BWD_PRELOADED = 1       ; bit 1: backward neighbour streamed
SPF_DEFERRED_FWD_LOAD = 2   ; bit 2: deferred slot 1 cold-load pending after FWD teleport (§4.2)
SPF_DEFERRED_BWD_LOAD = 3   ; bit 3: deferred slot 0 cold-load pending after BWD teleport (§4.2)

; Plane buffer
PLANE_BUFFER_SIZE       = 1536      ; bytes (~22 column entries per frame)

; -----------------------------------------------
; Strip Cache (§4.7) — linear buffer with batched slide
; -----------------------------------------------
STRIP_CACHE_COLS        = 80        ; logical window (viewport 40 + margin 20×2)
STRIP_CACHE_SIZE        = STRIP_CACHE_COLS * STRIP_BYTE_SIZE  ; 80 × 96 = 7680 bytes
STRIP_CACHE_PHYS_COLS   = 120       ; physical buffer capacity (40 extra for slide batching)
STRIP_CACHE_PHYS_SIZE   = STRIP_CACHE_PHYS_COLS * STRIP_BYTE_SIZE  ; 120 × 96 = 11520 bytes
STRIP_CACHE_GUARD_SIZE  = 512       ; absorbs S4LZ streaming decompressor overshoot
STRIP_CACHE_MARGIN      = 20        ; lookahead columns each side
STRIP_CACHE_SLIDE_KEEP  = STRIP_CACHE_MARGIN * 2  ; 40 strips kept left of camera during slide (backward scroll headroom)
STRIP_CACHE_INIT_COLS   = STRIP_CACHE_COLS - STRIP_CACHE_MARGIN  ; 60 strips at init (room for right margin fill)

; Collision maps (§4.7)
COLLISION_MAP_COLS      = 128       ; cells per section (SECTION_SIZE / 16)
COLLISION_MAP_ROWS      = 24        ; cells per section (384 / 16)
COLLISION_MAP_SIZE      = COLLISION_MAP_COLS * COLLISION_MAP_ROWS  ; 3072 bytes
COLLISION_CELL_SHIFT    = 4         ; pixel → cell (/ 16)
COLLISION_ROW_SHIFT     = 7         ; row × 128 via lsl #7

; Height maps (§4.7)
NUM_COLLISION_PROFILES  = 256
HEIGHT_PROFILE_SIZE     = 16        ; bytes per profile (one per pixel column in 16px block)
HEIGHT_MAP_SIZE         = NUM_COLLISION_PROFILES * HEIGHT_PROFILE_SIZE  ; 4096 bytes
ANGLE_TABLE_SIZE        = 256       ; one byte per collision type

; Collision types
CTYPE_AIR               = 0
CTYPE_FLAT_SOLID        = 1

; S4LZ streaming checkpoints
STRIPS_PER_CHECKPOINT   = 64        ; checkpoint every 64 strips
CHECKPOINT_INTERVAL     = STRIPS_PER_CHECKPOINT * STRIP_BYTE_SIZE  ; 6144 bytes

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
; Entity System (§4.9 — camera-driven sliding window)
; -----------------------------------------------

; Unified ring buffer
MAX_RING_BUFFER         = 128           ; max rings in unified buffer
RING_BUFFER_ENTRY_SIZE  = 6             ; dc.w x, y; dc.b section_id, list_index
RING_WIDTH              = 16            ; collision AABB pixels
RING_HEIGHT             = 16
RING_ANIM_FRAMES        = 4
RING_ANIM_SPEED         = 8             ; frames per animation tick

; Entity window scan
MAX_TRACKED_SECTIONS    = 4             ; 2 active + 2 preview neighbors
ENTITY_LOAD_BUFFER      = $180          ; pixels ahead/behind camera to load entities
ENTITY_DESPAWN_BUFFER   = $200          ; pixels beyond load buffer to despawn (hysteresis)
SCREEN_WIDTH            = 320           ; visible screen width in pixels

; 5×5 rolling collected bitmask (±2 sections in each axis)
COLLECTED_WINDOW_SLOTS  = 9             ; max tracked sections (9 slots)
COLLECTED_SLOT_SIZE     = 34            ; 1 tag + 1 pad + 16 ring bitmask + 16 killed bitmask
COLLECTED_BITMASK_OFFSET = 2            ; ring collected bitmask starts 2 bytes into slot
KILLED_BITMASK_OFFSET   = 18           ; object killed bitmask starts after ring bitmask
COLLECTED_EMPTY_TAG     = $FF           ; slot not owned by any section

; Object type tables (read from ROM, no RAM copy)
MAX_OBJECT_TYPES        = 32

; Slot tag — stored at fixed SST offset, identifies which section spawned an object
SLOT_TAG_OFFSET         = SST_sst_custom+$1D
SLOT_TAG_UNTAGGED       = $FF
SLOT_TAG_LEFT           = 0
SLOT_TAG_RIGHT          = 1

; Entity metadata — stored in SST custom region at spawn time
ENTITY_SECTION_ID_OFFSET = SST_sst_custom+$1B
ENTITY_LIST_INDEX_OFFSET = SST_sst_custom+$1C

; Object layout encoding (ROM format, 32-bit entries)
OBJ_ENTRY_X_SHIFT       = 20           ; bits 29-20
OBJ_ENTRY_Y_SHIFT       = 10           ; bits 19-10
OBJ_ENTRY_TYPE_SHIFT    = 5            ; bits 9-5
OBJ_ENTRY_SUBTYPE_MASK  = $1F          ; bits 4-0

; -----------------------------------------------
; Test VRAM allocation
; -----------------------------------------------
VRAM_TEST_OBJ           = $0001         ; tile index 1 (8 tiles for test art)
VRAM_TEST_SONIC         = $0010         ; tile index 16 (up to 25 tiles for Sonic frames)
