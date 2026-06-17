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

SONG_TEST   = 1
SONG_COUNT  = 1

SongTable:
        dc.l    Song_Test       ; id 1 (SongTable[id-1])
SongTable_End:

        if (SongTable_End-SongTable)/4 <> SONG_COUNT
          error "song table length \{(SongTable_End-SongTable)/4} != SONG_COUNT"
        endif

        align 2
