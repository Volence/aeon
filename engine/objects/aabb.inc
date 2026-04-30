; aabb_axis_test — single-axis AABB overlap test (assembler macro)
; Single source of truth for the overlap math — used by TouchResponse
; and RingCollision. Call twice (X then Y) for full 2D overlap.
;
; Tests: abs(apos - bpos) * 2 < (adim + bdim)
; Falls through if overlap on this axis; branches to mlab if not.
;
; Register contract:
;   apos       — position A (read-only, e.g. cached player X/Y)
;   bpos       — position B (read-only, register or memory operand)
;   adim,bdim  — widths/heights (consumed — aliasing with cdim/delt allowed)
;   cdim       — receives adim + bdim (may alias adim for zero-copy)
;   delt       — receives apos - bpos, signed (may alias bdim)
;   stmp       — scratch, clobbered (MUST NOT alias cdim or delt)
;   mlab       — label to branch to on no overlap
;   utag       — unique suffix for internal branch label (e.g. x or y)
;
; Typical aliasing for TouchResponse:
;   X: aabb_axis_test d4,SST_x_pos(a3),d0,d1,d0,d1,d2,.next_object,x
;   Y: aabb_axis_test d5,SST_y_pos(a3),d2,d3,d2,d3,d0,.next_object,y

    ifndef __AABB_INC__
__AABB_INC__ equ 1

aabb_axis_test macro apos,bpos,adim,bdim,cdim,delt,stmp,mlab,utag
        move.w  adim, cdim
        add.w   bdim, cdim

        move.w  apos, delt
        sub.w   bpos, delt

        move.w  delt, stmp
        bpl.s   .aovutag
        neg.w   stmp
.aovutag:
        add.w   stmp, stmp
        cmp.w   cdim, stmp
        bhs.s   mlab
        endm

    endif
