; ======================================================================
; data/sound/song_table.asm — song id -> SongHeader pointer table.
;
; TASK-1 STUB. Task 6 builds the real song table (and wires each song's
; patch_table_ptr to FmPatchTable). For now it holds the one test song so the
; reference resolves and SONG_COUNT is meaningful.
;
; CONTRACT: SongTable is SONG_COUNT longwords, indexed SongTable[id-1] (id 1 is
; the first entry). Song id 0 is RESERVED for "stop music" (exact stop encoding
; finalized in Task 6). SONG_TEST is the id of the bring-up song authored in
; data/sound/song_test.py.
; ======================================================================

SONG_TEST          = 1
SONG_MOVINGTRUCKS  = 2          ; Sound 1D: B&R "Moving Trucks" (transcoded)
SONG_COUNT         = 2

SongTable:
        dc.l    Song_Test           ; id 1 (SongTable[id-1])
        dc.l    Song_MovingTrucks   ; id 2
SongTable_End:

        if (SongTable_End-SongTable)/4 <> SONG_COUNT
          error "song table length \{(SongTable_End-SongTable)/4} != SONG_COUNT"
        endif

; --- Sound 1D: parallel per-song FM-patch-bank pointer table ---------------
; SongPatchTable[id-1] = the 68k ROM address of the song's FM patch bank. The 68k
; Sound_PlayMusic derives its $8000-window ptr and forwards it; the Z80 loader uses
; it ONLY on the stream path (the patch bank shares the song's bank). The copy path
; (1C songs) IGNORES it — its patches stay inline in Z80 RAM (FmPatchInlineTable),
; so the entry is a harmless placeholder (FmPatchTable, the 68k ROM table) for
; Song_Test. Moving Trucks points at its own translated bank (MovingTrucks_Patches).
SongPatchTable:
        dc.l    FmPatchTable        ; id 1 Song_Test (copy path — entry unused)
        dc.l    MovingTrucks_Patches ; id 2 Song_MovingTrucks (stream path — used)
SongPatchTable_End:

        if (SongPatchTable_End-SongPatchTable)/4 <> SONG_COUNT
          error "song-patch table length \{(SongPatchTable_End-SongPatchTable)/4} != SONG_COUNT"
        endif

        ; Task 6: song ids are 1..$FE in SND_REQ_MUSIC ($FF = stop sentinel), so
        ; the real song count must stay below $FF.
        if SONG_COUNT >= $FF
          error "SONG_COUNT (\{SONG_COUNT}) must be < $FF ($FF is the stop sentinel)"
        endif

        ; Task 6: the loader copies a FIXED SND_SONG_BUF_SIZE bytes of the packed
        ; song into Z80 RAM, so a RAM-BUFFERED song must fit in that buffer.
        ; (Sound 1D Song_MovingTrucks is ~4.4KB and is NOT buffer-asserted here: it
        ; streams from ROM in T3, never through the fixed SND_SONG_BUF.)
        if (Song_Test_End-Song_Test) > SND_SONG_BUF_SIZE
          fatal "Song_Test (\{Song_Test_End-Song_Test} bytes) exceeds SND_SONG_BUF_SIZE (\{SND_SONG_BUF_SIZE})"
        endif

        ; Task 6: the loader's fixed SND_SONG_BUF_SIZE-byte `ldir` reads from the
        ; song's $8000-window ptr ((addr & $7FFF) | $8000). If that window region
        ; sits within SND_SONG_BUF_SIZE bytes of $FFFF, the copy's source ptr wraps
        ; past $FFFF into Z80 RAM ($0000) and copies garbage into the buffer tail.
        ; Forbid it: the window offset must leave room for the full copy below the
        ; $8000-window top, i.e. (addr & $7FFF) <= ($8000 - SND_SONG_BUF_SIZE).
        if (Song_Test & $7FFF) > ($8000 - SND_SONG_BUF_SIZE)
          fatal "Song_Test window region crosses the $8000-window top: the \{SND_SONG_BUF_SIZE}-byte load ldir would wrap past $FFFF into Z80 RAM. Move Song_Test so (addr & $7FFF) <= \{$8000 - SND_SONG_BUF_SIZE}."
        endif

        ; --- Sound 1D: the Moving Trucks STREAMING block (song stream + patch bank)
        ; must fit in ONE 32KB bank so a single SetBank covers every sequencer ROM
        ; read (the loader holds that one bank for the whole DAC-off song). The
        ; block is Song_MovingTrucks .. MovingTrucks_Patches_End, placed contiguously
        ; after one `align $8000` in main.asm. Assert it does NOT cross a bank
        ; boundary (top byte in the same 32KB bank as the start). Combined size is
        ; ~4.4KB song + ~2.7KB patches ~= 7.2KB << 32KB, so the align guarantees it —
        ; this catches any future growth or accidental reordering. The per-channel
        ; stream offsets + the patch-bank window ptr are bank-window-relative
        ; (window_base = (addr & $7FFF) | $8000), which holds iff no boundary cross.
        if (Song_MovingTrucks >> 15) <> ((MovingTrucks_Patches_End-1) >> 15)
          fatal "Moving Trucks streaming block (song+patches, \{MovingTrucks_Patches_End-Song_MovingTrucks} bytes) crosses a 32KB bank boundary — one SetBank can't cover it. Keep Song_MovingTrucks bank-aligned (align $8000) with the patch bank contiguous."
        endif
        ; The streaming song's whole window region must also stay below the $8000-
        ; window top (so window_base + any per-channel offset stays a valid window
        ; address, never wrapping past $FFFF). With bank-alignment (addr & $7FFF)=0
        ; this is automatic, but assert it against future placement changes.
        if ((MovingTrucks_Patches_End-1) & $7FFF) < (MovingTrucks_Patches_End-1 - Song_MovingTrucks)
          fatal "Moving Trucks streaming block extends past the $8000-window top — not bank-aligned? Keep `align $8000` before Song_MovingTrucks."
        endif

        align 2
