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
VRAM_SPRITE_TABLE       = $B800         ; Relocated from $D800 to free plane rows 48-63
VRAM_HSCROLL_TABLE      = $BC00         ; Relocated from $DC00 (was inside Plane A 64×64 nametable)
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
RF_PRIORITY_SHIFT       = 5         ; bits 5-7 = sprite priority band (0-7)
RF_PRIORITY_MASK        = $E0       ; runtime priority changes must clear these bits first —
                                    ; ori.b alone accumulates stale bits (spawn-time ori is
                                    ; safe: slots are zeroed by DeleteObject/InitObjectRAM)

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

; SST layout constants (sync with structs.asm)
SST_CUSTOM_SIZE         = 34        ; bytes in sst_custom ($2E-$4F)
SST_TEMPLATE_START      = $0A       ; first byte of the ObjDef-copied template block
SST_TEMPLATE_SIZE       = 24        ; template bytes copied at spawn ($0A-$21; $20-$21 re-inited)

; Execution culling distances (pixels from camera center)
CULL_DISTANCE_X         = $300      ; 768px — skip dynamic objects beyond this
CULL_DISTANCE_Y         = $200      ; 512px

; Spawn guard
MAX_SPAWNS_PER_FRAME    = 8

; Game state IDs (extend existing)
GS_OBJECT_TEST          = 2

; -----------------------------------------------
; Player physics (§5) — 8.8 fixed point. Values are the verified
; S2/S3K contract; see docs/superpowers/specs/2026-06-12-player-system-design.md §6
; and docs/research/player-physics-classics.md (quick-reference card).
; order of these eight must match Player_Phys field order (ram.asm) —
; block-copied by Player_RefreshPhysics
; -----------------------------------------------
PHYS_ACCEL              = $C
PHYS_DECEL              = $80
PHYS_FRICTION           = $C
PHYS_TOP_SPEED          = $600
PHYS_GRAVITY            = $38
PHYS_JUMP_FORCE         = $680
PHYS_AIR_ACCEL          = $18
PHYS_JUMP_RELEASE_CAP   = -$400
PHYS_GSP_CAP            = $1000     ; tunneling guard on GROUND SPEED — FEEL DEVIATION coupling, spec §2.1
PHYS_FALL_CAP           = $1000
PHYS_SLOPE_WALK         = $20
PHYS_SLOPE_ROLL_DOWN    = $50
PHYS_SLOPE_ROLL_UP      = $14
PHYS_SLOPE_STAND_MIN    = $D        ; S3K standing slope-factor gate
PHYS_ROLL_FRICTION      = $6
PHYS_ROLL_DECEL         = $20
PHYS_ROLL_START_MIN     = $100      ; S3K threshold
PHYS_UNROLL_MAX         = $80       ; S3K threshold
PHYS_ROLL_FORCE_MIN     = $200
PHYS_KEEP_ROLL_MIN      = $400
PHYS_SLIP_SPEED         = $280
PHYS_SLIP_ANGLE         = $18       ; S3K slip threshold
PHYS_FALL_ANGLE         = $30       ; S3K detach threshold
PHYS_SLIP_NUDGE         = $80
PHYS_MOVE_LOCK_TIME     = 30
PHYS_SKID_MIN           = $400
PHYS_JUMP_BUFFER        = 2         ; frames — the one modern concession
SPINDASH_BASE           = $800
SPINDASH_CHARGE_STEP    = $200
SPINDASH_CHARGE_MAX     = $800
; Player collision radii (SPG; sizes are 2r+1)
PLAYER_X_RADIUS         = 9
PLAYER_Y_RADIUS         = 19
BALL_X_RADIUS           = 7
BALL_Y_RADIUS           = 14
PUSH_RADIUS             = 10        ; constant, never x_radius
CURL_Y_SHIFT            = 5         ; y_pos += on curl, -= on uncurl
; Player states (jump-table byte offsets: index × 2)
; ORDERING CONSTRAINT: the curled states (JUMP/ROLLJUMP/AIRBALL) must stay
; the LAST entries — Player_Display's ball-anim test is `>= PSTATE_JUMP`.
; Append new states BEFORE PSTATE_JUMP and renumber.
PSTATE_GROUND           = 0
PSTATE_ROLL             = 2
PSTATE_SPINDASH         = 4
PSTATE_AIR              = 6         ; airborne uncurled — no release cap
PSTATE_JUMP             = 8         ; airborne curled from jump — release cap active
PSTATE_ROLLJUMP         = 10        ; as JUMP + air control lockout
PSTATE_AIRBALL          = 12        ; airborne curled, not from jump
PSTATE_COUNT            = 7         ; state/hook tables assert against this
        if PSTATE_AIRBALL <> (PSTATE_COUNT-1)*2
          error "curled states must remain the last PSTATE_* entries (Player_Display ball test)"
        endif
; Player animation ids (Ani_Sonic script-table order — sonic_anims.asm)
ANIM_WALK               = 0
ANIM_IDLE               = 1
ANIM_BALL               = 2         ; roll/jump
; Solidity classes (SolidityTable values — generator contract, collision_pipeline.py)
SOLID_NONE              = 0
SOLID_TOP               = 1
SOLID_LRB               = 2
SOLID_ALL               = 3

; -----------------------------------------------
; §4 Level / World System
; -----------------------------------------------

; Section coordinate space
SECTION_SIZE            = $0800     ; slot width/height in engine pixels
SECTION_SIZE_SHIFT      = 11            ; log2(SECTION_SIZE) — derivation shift
    if SECTION_SIZE <> (1<<SECTION_SIZE_SHIFT)
      error "SECTION_SIZE_SHIFT out of sync with SECTION_SIZE"
    endif
SECTION_SHIFT           = 2*SECTION_SIZE        ; $1000 — teleport shift (pixels); 2-slot pair width (both axes). Anti-oscillation handled by Section_Teleport_Guard (position-based suppression after teleport).
SLOT_ORIGIN_L           = $0200     ; left slot engine-space left edge
SLOT_ORIGIN_R           = SLOT_ORIGIN_L+SECTION_SIZE    ; $0A00 — right slot engine-space left edge
SLOT_ORIGIN_U           = $0200     ; upper slot engine-space top edge
SLOT_ORIGIN_D           = SLOT_ORIGIN_U+SECTION_SIZE    ; $0A00 — lower slot engine-space top edge (no direct code use — documentation mirror of SLOT_ORIGIN_R)
SEC_VOID                = $FF       ; Slot_Section_Map sec_x sentinel: slot holds no section
                                    ; (FWD pair-advance at the edge of an odd-width grid).
                                    ; Consumers must skip the slot; SlotFlatID on it is invalid.

; Section_Edge_Flags bits — THE one "act edge at this side of the window"
; predicate. Written ONLY by Section_UpdateEdgeFlags (section.asm), which
; runs wherever Slot_Section_Map's sec_x changes (Section_Init,
; Section_TeleportFwd/Bwd; vertical teleports change sec_y only). Read by
; Section_Check (teleport gates), Player_LevelBound (playable bounds),
; Camera_Update (preview extension) — keep all three in sync with the
; writer's definitions below.
SEF_BWD_BLOCKED         = 0         ; slot 0 sec_x == 0 → no BWD teleport; left edge is a playable bound
SEF_FWD_BLOCKED         = 1         ; no FWD teleport (slot 1 void OR slot 1 is the last grid column)
SEF_FWD_VOID            = 2         ; slot 1 == SEC_VOID — playable area ends at slot 0's right edge
                                    ; (SEF_FWD_VOID implies SEF_FWD_BLOCKED; the writer sets both)
; -- §4.2 preview-zone (24-col / 24-row edges on plane A + plane B) --
; Preview width covers the edge region visible as camera approaches the
; teleport boundary. 24 cols = 192 px = ~3/5 of screen width. Preview is
; streaming-integrated: Section_UpdateColumns extends its range into
; neighbor section data, so preview cols are written by the normal
; streaming mechanism and only become visible as the camera reaches
; the boundary.
PREVIEW_COLS            = 24        ; nametable cols at FWD/BWD edges
PREVIEW_ROWS            = 24        ; nametable rows at TOP/BOT edges (vertical: stub for now)
PREVIEW_PIXELS          = PREVIEW_COLS*8    ; 192 px — used for camera clamp offset
SECTION_TILE_WIDTH      = SECTION_SIZE/8    ; 256 — tile cols per section
SECTION_FWD_THRESHOLD   = SLOT_ORIGIN_L+SECTION_SHIFT          ; $1200 — camera X → fire forward teleport
SECTION_BWD_THRESHOLD   = SLOT_ORIGIN_L                        ; $0200 — camera X → fire backward teleport
SECTION_FWD_PRELOAD     = SLOT_ORIGIN_L+SECTION_SIZE+SECTION_SIZE/2 ; $0E00 — camera X → queue forward section art (slot 1 midpoint)
SECTION_BWD_PRELOAD     = SLOT_ORIGIN_L+SECTION_SIZE/4         ; $0400 — camera X → queue backward section art (slot 0 quarter)
; -- §4.2 deferred cold-load triggers (keep just-left section's art alive across teleport for preview) --
SECTION_DEFERRED_FWD_LOAD = SLOT_ORIGIN_L+SECTION_SIZE/2       ; $0600 — camera X → fire deferred Sec_R load (slot 0 midpoint, post-FWD-teleport)
SECTION_DEFERRED_BWD_LOAD = SLOT_ORIGIN_L+SECTION_SIZE+SECTION_SIZE/4 ; $0C00 — camera X → fire deferred Sec_L load (slot 1 quarter, post-BWD-teleport)

; Vertical thresholds (2D active — mirrors horizontal pair layout)
SECTION_UP_THRESHOLD    = SLOT_ORIGIN_U                        ; $0200
SECTION_DOWN_THRESHOLD  = SLOT_ORIGIN_U+SECTION_SHIFT          ; $1200
SECTION_UP_PRELOAD      = SLOT_ORIGIN_U+SECTION_SIZE/4         ; $0400
SECTION_DOWN_PRELOAD    = SLOT_ORIGIN_U+SECTION_SIZE+SECTION_SIZE/2 ; $0E00
SECTION_DEFERRED_UP_LOAD  = SLOT_ORIGIN_U+SECTION_SIZE+SECTION_SIZE/4 ; $0C00
SECTION_DEFERRED_DOWN_LOAD = SLOT_ORIGIN_U+SECTION_SIZE/2      ; $0600
SECTION_TILE_HEIGHT     = SECTION_SIZE/8    ; 256 — tile rows per section

; Parallax (§4.6)
MAX_PARALLAX_BANDS         = 8
PARALLAX_TRANS_DEFAULT     = 16     ; default boundary lerp duration (frames)
PARALLAX_LERP_SHIFT        = 4      ; >>4 ≈ 16-frame convergence to ~95% — gentler slide on factor changes

; Multi-region VRAM tile packing (§2 A.2)
; Region 1: primary art pool $0000-$B7FF (1472 tiles).
; SAT at $B800 occupies tiles $5C0-$5FF (64 tiles).
; Region 2 removed — full 64-row plane uses all nametable rows.
REGION1_TILE_CAPACITY   = 1472      ; was 1536; SAT at $B800 takes tiles $5C0-$5FF

; Per-section streaming (§2 A.4)
MAX_ACT_SECTIONS        = 48        ; Section_Stream_State capacity; per-act grids must fit
                                    ; (flat id = sec_y * grid_w + sec_x; build asserts enforce
                                    ; grid_w * grid_h <= MAX_ACT_SECTIONS)

; Per-section streaming state values (single byte per section)
; (value 1 was SS_STREAMING — retired with Section_StreamArtGroup; the
; union-blob model marks neighbor sections RESIDENT directly)
SS_IDLE      = 0    ; not loaded
SS_RESIDENT  = 2    ; in VRAM, valid

; Section_Preload_Flags bit definitions
SPF_FWD_PRELOADED = 0       ; bit 0: forward neighbour streamed
SPF_BWD_PRELOADED = 1       ; bit 1: backward neighbour streamed
SPF_DEFERRED_FWD_LOAD = 2   ; bit 2: deferred slot 1 cold-load pending after FWD teleport (§4.2)
SPF_DEFERRED_BWD_LOAD = 3   ; bit 3: deferred slot 0 cold-load pending after BWD teleport (§4.2)
SPF_UP_PRELOADED      = 4   ; bit 4: upward neighbour streamed
SPF_DOWN_PRELOADED    = 5   ; bit 5: downward neighbour streamed
SPF_DEFERRED_UP_LOAD  = 6   ; bit 6: deferred vertical slot cold-load
SPF_DEFERRED_DOWN_LOAD = 7  ; bit 7: deferred vertical slot cold-load

; Plane buffer
PLANE_BUFFER_SIZE       = 1536      ; bytes (~22 column entries per frame)

; -----------------------------------------------
; 2D Tile Cache (§4.7)
; -----------------------------------------------
TILE_CACHE_COLS         = 80        ; columns in cache (viewport 40 + margin 20×2)
TILE_CACHE_ROWS         = 60        ; rows in cache (viewport 28 + margin 16×2)
TILE_CACHE_STRIDE       = TILE_CACHE_COLS   ; compile-time constant for row stride
TILE_CACHE_NT_SIZE      = TILE_CACHE_COLS * TILE_CACHE_ROWS * 2  ; 9600 bytes
TILE_CACHE_COLL_ROWS    = TILE_CACHE_ROWS / 2  ; 30 collision rows (16px cells)
TILE_CACHE_COLL_SIZE    = TILE_CACHE_COLS * TILE_CACHE_COLL_ROWS  ; 2400 bytes per plane
TILE_CACHE_COLL_PLANES  = 2         ; path A (index 0) + path B (index 1)
TILE_CACHE_MARGIN_H     = 20        ; horizontal margin (columns each side)
TILE_CACHE_MARGIN_V     = 16        ; vertical margin (rows each side)

; Block format (16×16 tile blocks, independently S4LZ-compressed)
; Raw block layout: [512B nametable][128B collision plane A][128B collision plane B]
BLOCK_TILE_SIZE         = 16        ; 16×16 tiles per block
BLOCK_TILE_SHIFT        = 4         ; lsr #4 = ÷ 16
BLOCK_NT_SIZE           = BLOCK_TILE_SIZE * BLOCK_TILE_SIZE * 2  ; 512 bytes
BLOCK_COLL_ROWS         = BLOCK_TILE_SIZE / 2  ; 8 collision rows per block
BLOCK_COLL_PLANE_SIZE   = BLOCK_TILE_SIZE * BLOCK_COLL_ROWS  ; 128 bytes per plane
BLOCK_COLL_SIZE         = BLOCK_COLL_PLANE_SIZE * TILE_CACHE_COLL_PLANES  ; 256 bytes (A+B)
BLOCK_RAW_SIZE          = BLOCK_NT_SIZE + BLOCK_COLL_SIZE  ; 768 bytes
BLOCK_STAGE_SLOTS       = 12        ; staged decompressed blocks (round-robin evict)
                                    ; sized so a column fill (<=5 blocks) + a row fill
                                    ; (<=6 blocks) coexist without thrashing on diagonals
BLOCK_DECOMP_BUDGET     = 6         ; max block decompresses per frame (shared: columns + rows)
VFILL_ROWS_PER_FRAME    = 2         ; rows filled per frame cap. Terminal velocity is
                                    ; 2 rows/frame (16px); 4 = catch-up headroom. The
                                    ; camera Y clamp (CAM_MAX_Y_STEP, Task 2) must stay
                                    ; <= this*8 px or streaming falls behind the view.
BLOCKS_PER_SECTION_AXIS = 16        ; 16 blocks across, 16 blocks down
BLOCK_INDEX_ENTRIES     = BLOCKS_PER_SECTION_AXIS * BLOCKS_PER_SECTION_AXIS  ; 256
BLOCK_INDEX_SIZE        = BLOCK_INDEX_ENTRIES * 4  ; 1024 bytes (ROM)

; Compressed art wrapper — every art blob starts with a 4-byte header:
; [u16 BE uncompressed size][u8 flags][u8 version]. Loaders peek the size
; for DMA (0 = empty stub, skip) and dispatch on the version byte.
ART_HDR_VERSION         = 3         ; byte offset of version within wrapper
ART_HDR_SIZE            = 4         ; wrapper bytes ahead of the stream
ART_VER_S4LZ            = 1         ; S4LZ v3 token stream (runtime tier)
ART_VER_ZX0             = 2         ; ZX0 modern/V2 bitstream (load-time tier)

; Collision (§4.7) — collision bytes embedded in block data, no separate maps
COLLISION_CELL_SHIFT    = 4         ; pixel → cell (/ 16)

; Height maps (§4.7)
NUM_COLLISION_PROFILES  = 256
HEIGHT_PROFILE_SIZE     = 16        ; bytes per profile (one per pixel column in 16px block)
HEIGHT_MAP_SIZE         = NUM_COLLISION_PROFILES * HEIGHT_PROFILE_SIZE  ; 4096 bytes
ANGLE_TABLE_SIZE        = 256       ; one byte per collision type

; Collision types
CTYPE_AIR               = 0
CTYPE_FLAT_SOLID        = 1

; Camera
CAM_LOOKAHEAD_THRESHOLD = $0600     ; ground speed for pan enable
CAM_PAN_SPEED           = 2         ; pixels/frame pan rate
CAM_PAN_LIMIT           = 64        ; max pan pixels
CAM_MAX_Y_STEP          = 16        ; max camera Y movement px/frame. The streaming
                                    ; contract rests on this clamp (every reference
                                    ; engine bounds the CAMERA: S2=16, S3K=24) — must
                                    ; stay <= VFILL_ROWS_PER_FRAME*8 or fills fall
                                    ; behind the view. Teleports bypass via Reinit.

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
MAX_TRACKED_SECTIONS     = 4            ; camera-envelope 2×2 — see EntityWindow_DeriveWindow
ENTITY_LOAD_BUFFER       = $180         ; pixels ahead/behind camera to load entities
ENTITY_DESPAWN_BUFFER    = $200         ; pixels beyond load buffer to despawn (hysteresis)
ENTITY_LOAD_BUFFER_Y     = $100         ; pixels above/below camera to load entities (§4.9 ph2)
ENTITY_DESPAWN_BUFFER_Y  = $180         ; Y despawn distance (> load = hysteresis)
ENTITY_LOADED_SLOT_SIZE  = 32           ; per-entry loaded bitmask: 16B rings + 16B objects
ENTITY_LOADED_OBJ_OFFSET = 16           ; object bits start mid-slot
ENTITY_RESCAN_COARSE_MASK = $FF80       ; camY coarse-row mask (128px rows) — crossing fires the vertical re-scan
ENTITY_RESCAN_ROW_SIZE   = ($10000-ENTITY_RESCAN_COARSE_MASK)  ; 128 — derived from the mask

; Load-bearing Y-band invariants (see entity_window.asm Y despawn / re-scan):
;  - despawn hysteresis must cover a full coarse row, or entities at the band
;    edge churn (despawn then re-load every crossing)
;  - the load buffer must cover a full coarse row, or fast vertical travel can
;    skip a row between re-scans, leaving in-band entities unspawned
    if (ENTITY_DESPAWN_BUFFER_Y-ENTITY_LOAD_BUFFER_Y) < ENTITY_RESCAN_ROW_SIZE
      error "Y despawn hysteresis < coarse row size — band-edge entities will churn"
    endif
    if ENTITY_LOAD_BUFFER_Y < ENTITY_RESCAN_ROW_SIZE
      error "ENTITY_LOAD_BUFFER_Y < coarse row size — vertical re-scan can skip entities"
    endif

SCREEN_WIDTH             = 320          ; visible screen width in pixels
SCREEN_HEIGHT            = 224          ; visible screen height in pixels

; 3×3 rolling collected bitmask (±1 section in each axis)
; Slot count and eviction radius must agree: 3×3 = 9 slots, radius = ±1.
; Collected_UpdateCenter evicts any slot where |dx|>1 OR |dy|>1.
COLLECTED_WINDOW_SLOTS  = 9             ; max tracked sections (9 slots)
COLLECTED_SLOT_SIZE     = 34            ; 1 tag + 1 pad + 16 ring bitmask + 16 killed bitmask
COLLECTED_BITMASK_OFFSET = 2            ; ring collected bitmask starts 2 bytes into slot
KILLED_BITMASK_OFFSET   = 18           ; object killed bitmask starts after ring bitmask
COLLECTED_EMPTY_TAG     = $FF           ; slot not owned by any section
COLLECTED_MASK_BYTES    = KILLED_BITMASK_OFFSET-COLLECTED_BITMASK_OFFSET ; 16 — one bitmask (ring or killed)

; Rolling respawn park (§4.9.4) — sections evicted from the 3×3 with any
; collected/killed bit set park here; restored on re-claim. Oldest rolls off.
; 9 (window) + 4 (park) = 13 remembered sections — covers a 3×3 act entirely.
COLLECTED_PARK_SLOTS    = 4             ; park entries (rolling overwrite)
COLLECTED_PARK_ENTRY_SIZE = 1+2*COLLECTED_MASK_BYTES ; 33 — id byte + collected + killed masks (byte-packed, entries NOT word-aligned)
MAX_LIST_ENTRIES        = 128           ; collected/killed bitmask capacity per section
                                        ; (16-byte bitmask; index >= 128 corrupts the next
                                        ; window slot — enforced by debug asserts + T9 objentry macro)

; Object type tables (read from ROM, no RAM copy)
MAX_OBJECT_TYPES        = 32

; Slot tag — stored in SST_slot_tag; identifies which quadrant entry (0-3) spawned an object
; 0 = upper-left (slot L, row r), 1 = upper-right (slot R, row r)
; 2 = lower-left (slot L, row r+1), 3 = lower-right (slot R, row r+1)
; Bit 7 = OEF_ANY_Y placement (Y-despawn exempt). $80|idx never equals
; SLOT_TAG_UNTAGGED ($FF), so exact-$FF untagged compares stay correct.
SLOT_TAG_UNTAGGED       = $FF
SLOT_TAG_LEFT           = 0
SLOT_TAG_RIGHT          = 1
SLOT_TAG_LOWER_L        = 2             ; lower-left quadrant (was SLOT_TAG_UP)
SLOT_TAG_LOWER_R        = 3             ; lower-right quadrant (was SLOT_TAG_DOWN)

; Object placement entry (ROM, 6 bytes): dc.w x, y, flags|type|subtype
; X-sorted ascending; terminated by dc.w -1 (X is section-local, never negative)
OEF_ANY_Y               = 15            ; spawn regardless of camera Y (§4.9 phase 2)
OEF_YFLIP               = 14            ; rol.w #4 in Load_Object → RF_YFLIP
OEF_XFLIP               = 13            ; rol.w #4 in Load_Object → RF_XFLIP
OEF_TYPE_SHIFT          = 8             ; bits 12-8: type (0-31)
OEF_TYPE_MASK           = $1F
OEF_SUBTYPE_MASK        = $FF           ; bits 7-0
OBJ_ENTRY_SIZE          = 6

; -----------------------------------------------
; Mapping frame header (precomputed by the mapping pipeline)
; -----------------------------------------------
; Frame data layout:
;   +0  dc.b x_min, x_max, y_min, y_max   ; signed pixel extents relative to origin
;   +4  dc.w piece_count
;   +6  pieces (8 bytes each)
;
; x_max/y_max are the far edge (offset + piece size), not the piece origin.
; Extents are FLIP-INVARIANT — see convert_s2_mappings.py _compute_bbox.
FRAME_BBOX_X_MIN        = 0         ; signed byte — leftmost piece pixel
FRAME_BBOX_X_MAX        = 1         ; signed byte — rightmost piece pixel (right EDGE: x_off + width)
FRAME_BBOX_Y_MIN        = 2         ; signed byte — topmost piece pixel
FRAME_BBOX_Y_MAX        = 3         ; signed byte — bottommost piece pixel (bottom EDGE: y_off + height)
FRAME_PIECE_COUNT       = 4         ; word — number of pieces in frame
FRAME_PIECES            = 6         ; byte offset to first piece datum

; -----------------------------------------------
; Test VRAM allocation
; -----------------------------------------------
VRAM_TEST_OBJ           = $03E0         ; tile 992 — test object art (8 tiles) in the free
                                        ; gap between the character DPLC region end (985)
                                        ; and the BG shared region base (1024). The old
                                        ; value $0001 sat inside the FG level pool: blank
                                        ; in some art bases, terrain-aliased in others.
VRAM_RING_PLACEHOLDER   = VRAM_TEST_OBJ+8 ; tile 1000 — 1-tile gold ring (DrawRings)
VRAM_TEST_SONIC         = $03C0        ; tile 960 — character DPLC region (up to 25 tiles).
                                        ; MUST stay clear of: FG section pools (tiles 0-~226,
                                        ; see data/editor vram_bases), marker tile $FA, BG
                                        ; region (1024+), SAT/HScroll/planes. The old value
                                        ; $0010 sat inside FG pool A — Sonic DPLC streaming
                                        ; stomped live level tiles the moment debug mode exited.
