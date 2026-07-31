; demo game constants
GS_DEMO                 = 2             ; entry state id (0/1 = engine GS_BOOT/GS_IDLE)
VRAM_DEMO_OBJ           = $03E0        ; demo box art (4 tiles) — free tile region
VRAM_RING_PLACEHOLDER   = VRAM_DEMO_OBJ+4 ; engine contract (DrawRings) — blank tile here

; Engine-consumed capacity contracts (every game must define these; the engine
; sizes its ring/entity RAM and loops from them):
MAX_RING_BUFFER         = 16            ; minimal — demo has no rings
RING_BUFFER_ENTRY_SIZE  = 6             ; dc.w x, y; dc.b section_id, list_index — engine layout (matches sonic4 config/constants.asm)
RING_WIDTH              = 16
COLLECTED_WINDOW_SLOTS  = 4
COLLECTED_SLOT_SIZE     = 34            ; 1 tag + 1 pad + 16 ring bitmask + 16 killed bitmask — engine layout (matches sonic4 config/constants.asm)
COLLECTED_PARK_SLOTS    = 4
COLLECTED_PARK_ENTRY_SIZE = 1+2*COLLECTED_MASK_BYTES ; 33 — id byte + collected + killed masks (COLLECTED_MASK_BYTES is an engine constant from engine.constants, injected as a guarded define)
