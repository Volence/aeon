; Sonic 4 sound ids + SFX priority ladder. SONG_* ids live in
; data/sound/song_table.asm; SFX_BLOB_BANK is generator-emitted into
; data/sound/sfx/sfx_table.asm.

; --- Symbolic SFX ids (spec §9; ids posted to SND_REQ_SFX, disjoint from song ids)
; Values are the S3K source filenames so the transcoder's SfxTable index matches
; (id -> SfxTable[id-1] inside the contiguous SFX-id range; the transcoder densely
; renumbers, but these names are what gameplay refers to). See SfxIdRemap below.
SFXID_RING_RIGHT = $33
SFXID_RING_LEFT  = $34
SFXID_DEATH      = $35
SFXID_SKID       = $36
SFXID_ROLL       = $3C
SFXID_JUMP       = $62
SFXID_SPINDASH   = $AB
SFXID_DASH       = $B6
SFXID_RINGLOSS   = $B9

; --- Per-SFX priority tiers (authored; S3K has none — spec §6). Higher = wins.
; Seeded from S2 zSFXPriority for shared sounds: death/hurt > spindash > skid/roll
; > jump > ring/UI. The transcoder bakes a priority byte into each SfxHeader keyed
; by id; these tiers are the source of that map (mirrored in tools/sfx_transcode.py).
; 7-BIT SCALE ($00-$7F): bit 7 of sfh_priority is RESERVED as the non-latching flag
; (spec §5/§7.1, S2's trick — plays but never latches the floor; Sfx_BeginSound masks
; it off for arbitration). Only relative ordering matters (all compares are `cp`), so
; these values carry rank only — keep them spaced and strictly < $80. Build-asserted
; below; a value >= $80 would be misread as the non-latching flag AND is negative
; under any signed Z80 compare.
SFXPRI_RING     = $10    ; ring/UI — lowest; never ducks (authored sfh_duck = 0)
SFXPRI_JUMP     = $20
SFXPRI_ROLL     = $30
SFXPRI_SKID     = $30
SFXPRI_SPINDASH = $40
SFXPRI_DASH     = $40
SFXPRI_DEATH    = $60    ; death/ring-loss — highest
SFXPRI_RINGLOSS = $60

; Guard: every priority tier MUST fit in 7 bits so bit 7 stays free as the
; non-latching flag (and stays non-negative under signed compares). Mirrored by a
; test in tools/sfx_transcode.py.
        if (SFXPRI_RING|SFXPRI_JUMP|SFXPRI_ROLL|SFXPRI_SKID|SFXPRI_SPINDASH|SFXPRI_DASH|SFXPRI_DEATH|SFXPRI_RINGLOSS) & $80
          fatal "an SFXPRI_* tier has bit 7 set — priorities must be 7-bit ($00-$7F); bit 7 is the non-latching flag"
        endif
