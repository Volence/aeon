; ======================================================================
; data/sound/song_table.asm — song id -> SongHeader pointer table.
;
; Holds the native "Moving Trucks" (B&R) port — the only song, id 1. The
; SongPatchTable + the stream-path loader infra below feed its bank-aligned
; 32KB streaming block.
;
; CONTRACT: SongTable is SONG_COUNT longwords, indexed SongTable[id-1] (id 1 is
; the first entry). Song id 0 is RESERVED for "stop music".
; ======================================================================

; SONG_MOVINGTRUCKS / SONG_DRUMTEST / SONG_HCZ2 id equates now live in
; config/sound_ids.asm (sound-migration T2 ruling R2 — moveq bakes the id
; immediate into the opcode word, so a hand-written contract file holds them
; instead of a cross-seam deferral). SONG_COUNT moved there too (retro-fix
; batch 2): it must resolve UNGATED for sound_api's cross-seam DEBUG bounds
; assert, since the mixed build gates this file out. The self-check below still
; validates the actual table length against it.

SongTable:
        dc.l    Song_MovingTrucks   ; id 1 — Phase 3 Task 8 native Moving Trucks (streamed)
    ifdef __DEBUG__
        dc.l    Song_DrumTest       ; id 2 — DEBUG STREAM DAC-on drum-test (Task 5.3)
        dc.l    Song_HCZ2           ; id 3 — S3K Hydrocity Zone Act 2 import (Phase 7)
    endif
SongTable_End:

        if (SongTable_End-SongTable)/4 <> SONG_COUNT
          error "song table length \{(SongTable_End-SongTable)/4} != SONG_COUNT"
        endif

; --- parallel per-song FM-patch-bank pointer table -------------------------
; SongPatchTable[id-1] = the 68k ROM address of the song's FM patch bank. The 68k
; Sound_PlayMusic derives its $8000-window ptr and forwards it; the Z80 loader uses
; it on the stream path (the patch bank shares the song's bank).
SongPatchTable:
        dc.l    MovingTrucks_Patches ; id 1 Song_MovingTrucks (stream path — USED)
    ifdef __DEBUG__
        dc.l    MovingTrucks_Patches ; id 2 Song_DrumTest reuses MT's patch bank (same bank)
        dc.l    HCZ2_Patches         ; id 3 Song_HCZ2 (stream path — MT's bank, contiguous w/ song)
    endif
SongPatchTable_End:

        if (SongPatchTable_End-SongPatchTable)/4 <> SONG_COUNT
          error "song-patch table length \{(SongPatchTable_End-SongPatchTable)/4} != SONG_COUNT"
        endif

        ; song ids are 1..$FE in SND_REQ_MUSIC ($FF = stop sentinel), so the real
        ; song count must stay below $FF.
        if SONG_COUNT >= $FF
          error "SONG_COUNT (\{SONG_COUNT}) must be < $FF ($FF is the stop sentinel)"
        endif

        ; Every song STREAMS from ROM through the banked $8000 window (the copy
        ; path and its fixed Z80-RAM song buffer were deleted — budget A.1), so
        ; no per-song buffer-fit asserts exist; only the bank-straddle guards
        ; below matter.

        ; --- Sound Phase 3 Task 8 + F5 co-location: the Moving Trucks STREAMING block
        ; must fit in ONE 32KB bank so a single SetBank covers every sequencer ROM read
        ; (the loader holds that one bank for the whole DAC-off song). The F5 redo puts
        ; the engine lookup tables at the START of this same bank, so the block now runs
        ; MovingTrucks_Bank_Start (tables) .. MovingTrucks_Patches_End (song stream +
        ; per-song pitch table + FmPatch bank), placed contiguously after one
        ; `align $8000` in main.asm. MT reads tables AND its own stream through the SAME
        ; banked $8000 window — no swap. Assert it does NOT cross a 32KB bank boundary
        ; (top byte in the same 32KB bank as the bank start). Combined size is ~1KB
        ; tables + ~14.9KB song + 264B pitch table + 858B patches ~= 17KB << 32KB, so
        ; the align guarantees it — this catches any future growth or reordering. The
        ; table labels, the per-channel stream offsets, the header pitchtable_ptr
        ; offset, and the patch-bank window ptr are all bank-window-relative
        ; (window_base = (addr & $7FFF) | $8000), which holds iff no boundary cross.
        if (MovingTrucks_Bank_Start >> 15) <> ((MovingTrucks_Patches_End-1) >> 15)
          fatal "Moving Trucks streaming block (tables+song+pitchtable+patches, \{MovingTrucks_Patches_End-MovingTrucks_Bank_Start} bytes) crosses a 32KB bank boundary — one SetBank can't cover it. Keep MovingTrucks_Bank_Start bank-aligned (align $8000) with tables + song + pitch table + patch bank contiguous."
        endif
        ; The streaming block's whole window region must also stay below the $8000-
        ; window top (so window_base + any per-channel offset / the pitchtable offset
        ; stays a valid window address, never wrapping past $FFFF). With bank-
        ; alignment (addr & $7FFF)=0 this is automatic, but assert it against future
        ; placement changes.
        if ((MovingTrucks_Patches_End-1) & $7FFF) < (MovingTrucks_Patches_End-1 - MovingTrucks_Bank_Start)
          fatal "Moving Trucks streaming block extends past the $8000-window top — not bank-aligned? Keep `align $8000` before MovingTrucks_Bank_Start."
        endif

    ifdef __DEBUG__
        ; Song_DrumTest (Task 5.3) is co-located in Moving Trucks' bank, right after
        ; the MT patches (see main.asm). It must stay in the SAME 32KB bank so the
        ; one SetBank(SND_SONG_BANK) that covers MT's reads also covers DrumTest's
        ; stream reads + its window-relative engine-table/patch reads. (It reuses the
        ; engine-default pitch table + MovingTrucks_Patches, both already asserted in
        ; this bank above, so no separate pitch/patch fit check is needed.)
        if (MovingTrucks_Bank_Start >> 15) <> ((Song_DrumTest_End-1) >> 15)
          fatal "Song_DrumTest (DEBUG) pushed Moving Trucks' bank past a 32KB boundary (\{Song_DrumTest_End-MovingTrucks_Bank_Start} bytes from the bank start). Shrink the test song or give it its own bank+tables."
        endif

        ; Song_HCZ2 (Phase 7) STREAMS from ROM (SH_F_STREAM): the Z80 sequencer reads
        ; its command streams AND its FM patch bank DIRECTLY through the banked $8000
        ; window with ONE SetBank. It is CO-LOCATED in Moving Trucks' bank (main.asm —
        ; no own `align $8000`), because its frame ALSO reads the engine-table head
        ; (FmPitchTableZ/LogVolumeLutZ/SeqOpcodeTable/DacSampleTable/...) as fixed
        ; window labels that physically live only at THAT bank's start (the
        ; replicate-per-bank rule in main.asm). So assert the whole block against
        ; MovingTrucks_Bank_Start — not merely self-consistency — which catches BOTH
        ; a bank-boundary straddle AND HCZ2 being pushed whole into the next bank
        ; (where its own no-straddle check would still pass but every engine-table
        ; read would see garbage). Combined bank content is ~24KB << 32KB today. The
        ; per-channel stream offsets and the patch-bank window ptr are all bank-
        ; window-relative (window_base = (addr & $7FFF) | $8000), which holds iff
        ; the block stays inside the bank.
        if (MovingTrucks_Bank_Start >> 15) <> ((HCZ2_Patches_End-1) >> 15)
          fatal "Song_HCZ2 block (song+patches, ending \{HCZ2_Patches_End-MovingTrucks_Bank_Start} bytes from the bank start) leaves Moving Trucks' 32KB bank — one SetBank can't cover its stream + the engine-table head. Shrink the bank contents or give HCZ2 its own bank WITH an engine-table head twin."
        endif
        ; (Window-top wrap is covered by the bank-anchored assert above: the whole
        ; block staying inside MovingTrucks' bank bounds every window offset below
        ; $8000. The old self-anchored duplicate — which could no longer fire once
        ; HCZ2 lost its own `align $8000` — was removed 2026-07-02.)
    endif

        align 2
