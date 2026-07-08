; Sonic 4 game RAM — phased continuation from Engine_RAM_End (E5 split).
; RULES: AS does NOT auto-align ds.w/ds.l — every block must end even; an odd
; ds.b run address-errors the next word field at RUNTIME with a green build.
; Emulator runtime boot-verify is mandatory after any change here.
        phase Engine_RAM_End

    ifdef __DEBUG__
Dbg_Music_On:           ds.w 1          ; DEBUG: 1 = test song playing (Start toggles; low byte only)
Dbg_Sfx_Sel:            ds.w 1          ; DEBUG: B-button SFX-trigger cycle index (low byte; 0..7 over the test id table)
    endif

; -----------------------------------------------
; Player (§5)
; -----------------------------------------------
; Effective physics table — recomputed by Player_RefreshPhysics on
; section change / status events, NEVER per-frame. a4 points here
; during player movement code (classic register convention).
; field order must match the first eight PHYS_* constants (constants.asm)
Player_Phys:
Phys_accel:             ds.w 1
Phys_decel:             ds.w 1
Phys_friction:          ds.w 1
Phys_top_speed:         ds.w 1
Phys_gravity:           ds.w 1
Phys_jump_force:        ds.w 1
Phys_air_accel:         ds.w 1
Phys_release_cap:       ds.w 1
Player_Phys_End:

Player_Quadrant:        ds.b 1      ; (angle+$20)>>6 — derived once per frame
Player_JumpBuffer:      ds.b 1      ; frames remaining on buffered jump press
Player_Death_Pending:   ds.b 1      ; EDGE_KILL hook: set when the player crosses a
                                    ; kill-edge; the death system (when it exists)
                                    ; consumes it. Boot-cleared with all Work-RAM.
                        ds.b 1      ; pad — keep the following ds.w/ds.l fields
                                    ; even-aligned (AS does not auto-align; an odd
                                    ; count here address-errors Plane_Buffer_Ptr)

; -----------------------------------------------
; Player history rings (§5)
; -----------------------------------------------
; Position/stat history rings (future Tails follow + trails; recorded
; from day one). 256-aligned: index wraps via low-byte increment.
        align 256   ; Player_Pos_Ring low-byte index wrap needs a 256 boundary
                     ; (align, since Engine_RAM_End is arbitrary)
Player_Pos_Ring:        ds.b 256    ; 64 × (x.w, y.w)
Player_Stat_Ring:       ds.b 256    ; 64 × (input.w, status.b, pad.b)
Player_Ring_Index:      ds.w 1      ; byte offset into both rings — word-sized for direct (an,dn.w) index use

    if Player_Pos_Ring&$FF
      error "Player_Pos_Ring not 256-aligned — low-byte index wrap breaks"
    endif

Game_RAM_End:

        if Game_RAM_End >= SYSTEM_STACK
          error "Game RAM overflow into stack by \{Game_RAM_End - SYSTEM_STACK} bytes!"
        endif

        dephase
