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

        ; Task 6: song ids are 1..$FE in SND_REQ_MUSIC ($FF = stop sentinel), so
        ; the real song count must stay below $FF.
        if SONG_COUNT >= $FF
          error "SONG_COUNT (\{SONG_COUNT}) must be < $FF ($FF is the stop sentinel)"
        endif

        ; Task 6: the loader copies a FIXED SND_SONG_BUF_SIZE bytes of the packed
        ; song into Z80 RAM, so a RAM-BUFFERED song must fit in that buffer.
        ; (Sound 1D Song_MovingTrucks is ~3KB and is NOT buffer-asserted here: it
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

        align 2
