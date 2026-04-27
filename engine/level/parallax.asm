; engine/level/parallax.asm — §4.6 parallax pipeline
;
; Public:
;   Parallax_Init(a0=parallax_config*) — initialize Parallax_State at level load
;   Parallax_Update                    — main-loop per-frame builder (T5+)
;   Parallax_StartTransition(a0=new)   — section boundary handler (T8+)
;   Vscroll_Write                      — VBlank VSRAM emitter (T6+)

; ----------------------------------------------------------------------
; Parallax_Init — wipe Parallax_State and seed current_config
; In:  a0 = parallax_config* (NULL = inert; pipeline will skip)
; Out: none
; Clobbers: d0, d1, a1
; ----------------------------------------------------------------------
Parallax_Init:
        lea     (Parallax_State).w, a1
        moveq   #(Parallax_State_End-Parallax_State)/4-1, d0
        moveq   #0, d1
.zero:
        move.l  d1, (a1)+
        dbf     d0, .zero

        move.l  a0, (Parallax_Current_Config).w
        ; Target_Config and Transition_Frames stay 0 (no transition active).
        rts
