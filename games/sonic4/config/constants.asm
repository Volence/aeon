; Sonic 4 game constants — tuning, test scaffold, game state ids. Split from
; the shared constants.asm (E4).

; Game state IDs (extend existing)
GS_OBJECT_TEST          = 2

ANIM_RUN_THRESHOLD      = $600      ; |gsp| at/above which walk -> run anim (S3K)
SPINDASH_BASE           = $800
SPINDASH_CHARGE_STEP    = $200
SPINDASH_CHARGE_MAX     = $800

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
; Player animation ids — SHARED CONTRACT across all characters.
; Each character's Ani_<char> script table is ordered by these ids
; (sonic_anims.asm asserts its entry count == ANIM_COUNT). Player_Animate
; only ever writes these ids; it never knows which character it animates.
ANIM_WALK               = 0
ANIM_RUN                = 1
ANIM_ROLL               = 2         ; also the air ball (jump/airball)
ANIM_SPINDASH           = 3
ANIM_PUSH               = 4
ANIM_IDLE               = 5         ; wait/idle (neutral hold -> foot-tap tail)
ANIM_BALANCE            = 6
ANIM_LOOKUP             = 7
ANIM_DUCK               = 8
ANIM_SKID               = 9
ANIM_GETUP              = 10
ANIM_COUNT              = 11        ; sonic_anims.asm asserts entry count == this

; Game state IDs (extend existing table)
GS_OJZ_SCROLL_TEST      = 3

; Unified ring buffer
MAX_RING_BUFFER         = 128           ; max rings in unified buffer
RING_BUFFER_ENTRY_SIZE  = 6             ; dc.w x, y; dc.b section_id, list_index
RING_WIDTH              = 16            ; collision AABB pixels

; 3×3 rolling collected bitmask sizing (±1 section in each axis)
; Slot count and eviction radius must agree: 3×3 = 9 slots, radius = ±1.
; Collected_UpdateCenter evicts any slot where |dx|>1 OR |dy|>1.
COLLECTED_WINDOW_SLOTS  = 9             ; max tracked sections (9 slots)
COLLECTED_SLOT_SIZE     = 34            ; 1 tag + 1 pad + 16 ring bitmask + 16 killed bitmask

; Rolling respawn park (§4.9.4) — sections evicted from the 3×3 with any
; collected/killed bit set park here; restored on re-claim. Oldest rolls off.
; 9 (window) + 4 (park) = 13 remembered sections — covers a 3×3 act entirely.
COLLECTED_PARK_SLOTS    = 4             ; park entries (rolling overwrite)
COLLECTED_PARK_ENTRY_SIZE = 1+2*COLLECTED_MASK_BYTES ; 33 — id byte + collected + killed masks (byte-packed, entries NOT word-aligned)

; -----------------------------------------------
; Test VRAM allocation
; -----------------------------------------------
VRAM_TEST_OBJ           = $03E0         ; tile 992 — test object art (8 tiles) in the free
                                        ; gap between the character DPLC region end (985)
                                        ; and the BG shared region base (1024).
VRAM_RING_PLACEHOLDER   = VRAM_TEST_OBJ+8 ; tile 1000 — gold ring art (1 tile). DrawRings
                                        ; emits 2×2 (16×16) sprites, so tiles 1001-1003
                                        ; render too and MUST stay blank — they are the
                                        ; ring's transparent surround.
                                        ; ENGINE CONTRACT — DrawRings (engine/objects/rings.asm)
                                        ; renders every ring with this tile; every game must
                                        ; define it.
VRAM_TEST_MARKER        = VRAM_RING_PLACEHOLDER+4 ; tile 1004 — debug-fly marker (2×2 = 4 tiles)
                                        ; in the free gap below the BG region (1024). Must NOT
                                        ; sit inside the act art pool (every pool slot is
                                        ; referenced FG art — see POOL_TILE_CEILING) nor in
                                        ; the ring sprite's 1000-1003 span.
VRAM_TEST_SONIC         = $03C0        ; tile 960 — character DPLC region (up to 25 tiles).
                                        ; MUST stay clear of: the act art pool (tiles
                                        ; 0..POOL_TILE_CEILING-1), the test-obj/ring/marker
                                        ; span (992-1007), BG region (1024+), SAT/HScroll/planes.
