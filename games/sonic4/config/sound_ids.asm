; Sonic 4 SFX-bank count contract (residual AS stub).
;
; The song ids, symbolic SFX ids, the spindash-rev special case, and the SFX
; priority ladder flipped to games/sonic4/config/sound_ids.emp (module
; games.sonic4.sound_ids) at conversion-tail Parcel F2 — the sole authority now,
; harvested into the residual AS as guarded -D defines + link EquSyms.
;
; --- SFX table shape. Hand-owned mirror of sfx_bank.emp's SfxTable-derived
; counts (const SFX_ID_BASE = SfxTable.min_key, etc.), consumed by the Z80 SFX
; reader as imm8 (ld a, .. / sub SFX_ID_BASE / cp SFX_TABLE_LEN), which never
; defer — so they must resolve at AS-time, which a hand-owned home guarantees.
; sfx_bank.emp's ensure(extern("SFX_ID_BASE") == ...) drift-guards these against
; the table row set; sound_bank.inc reads SFX_TABLE_LEN in the SfxBlobWinTab span
; guard. TRANSITIONAL: the F2 close-packet ruling dissolves these into sfx_bank.emp
; (the module that owns the bank they count, where they are already DERIVED from the
; SfxTable rows) — the pub-const eval is mechanical; this stub is deleted in the same
; parcel once the seam / harvest consumers source them from that authority.
SFX_ID_BASE   = $33
SFX_COUNT     = 9
SFX_TABLE_LEN = 135   ; max_id - min_id + 1 (sparse over the id range $33..$B9)
