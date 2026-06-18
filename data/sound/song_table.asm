; ======================================================================
; data/sound/song_table.asm — song id -> SongHeader pointer table.
;
; Holds the bring-up test song (SONG_TEST). The Sound 1D FM-depth work
; (Phase 3) re-adds the real "Moving Trucks" port as a streaming song; the
; SongPatchTable + the stream-path loader infra below are kept ready for it.
;
; CONTRACT: SongTable is SONG_COUNT longwords, indexed SongTable[id-1] (id 1 is
; the first entry). Song id 0 is RESERVED for "stop music". SONG_TEST is the id
; of the bring-up song authored in data/sound/song_test.py.
; ======================================================================

SONG_TEST          = 1
; SONG_PITCHTEST (Sound Phase 3 Task 3): a SCRATCH one-FM-channel verification
; song emitting MEV_PITCHENV count=1 notes at known fnum-table indices so the
; controller can confirm the per-song pitch table + the ModUpdate single-note
; render. Copy-path (FM6=DAC, RAM-buffered), pitchtable_ptr=0 -> engine-default
; table. Kept ALONGSIDE SONG_TEST so DEBUG boot can switch back after verifying.
SONG_PITCHTEST     = 2
SONG_COUNT         = 2

SongTable:
        dc.l    Song_Test           ; id 1 (SongTable[id-1])
        dc.l    Song_PitchTest      ; id 2 — Phase 3 scratch pitch verification
SongTable_End:

        if (SongTable_End-SongTable)/4 <> SONG_COUNT
          error "song table length \{(SongTable_End-SongTable)/4} != SONG_COUNT"
        endif

; --- parallel per-song FM-patch-bank pointer table -------------------------
; SongPatchTable[id-1] = the 68k ROM address of the song's FM patch bank. The 68k
; Sound_PlayMusic derives its $8000-window ptr and forwards it; the Z80 loader uses
; it ONLY on the stream path (the patch bank shares the song's bank). The copy path
; (1C songs) IGNORES it — its patches stay inline in Z80 RAM (FmPatchInlineTable),
; so the entry is a harmless placeholder (FmPatchTable, the 68k ROM table) for
; Song_Test. (Phase 3's streaming Moving Trucks will add its own bank here.)
SongPatchTable:
        dc.l    FmPatchTable        ; id 1 Song_Test (copy path — entry unused)
        dc.l    FmPatchTable        ; id 2 Song_PitchTest (copy path — entry unused)
SongPatchTable_End:

        if (SongPatchTable_End-SongPatchTable)/4 <> SONG_COUNT
          error "song-patch table length \{(SongPatchTable_End-SongPatchTable)/4} != SONG_COUNT"
        endif

        ; song ids are 1..$FE in SND_REQ_MUSIC ($FF = stop sentinel), so the real
        ; song count must stay below $FF.
        if SONG_COUNT >= $FF
          error "SONG_COUNT (\{SONG_COUNT}) must be < $FF ($FF is the stop sentinel)"
        endif

        ; The loader copies a FIXED SND_SONG_BUF_SIZE bytes of the packed song into
        ; Z80 RAM, so a RAM-BUFFERED (copy-path) song must fit in that buffer.
        if (Song_Test_End-Song_Test) > SND_SONG_BUF_SIZE
          fatal "Song_Test (\{Song_Test_End-Song_Test} bytes) exceeds SND_SONG_BUF_SIZE (\{SND_SONG_BUF_SIZE})"
        endif
        if (Song_PitchTest_End-Song_PitchTest) > SND_SONG_BUF_SIZE
          fatal "Song_PitchTest (\{Song_PitchTest_End-Song_PitchTest} bytes) exceeds SND_SONG_BUF_SIZE (\{SND_SONG_BUF_SIZE})"
        endif

        ; The loader's fixed SND_SONG_BUF_SIZE-byte `ldir` reads from the song's
        ; $8000-window ptr ((addr & $7FFF) | $8000). If that window region sits within
        ; SND_SONG_BUF_SIZE bytes of $FFFF, the copy's source ptr wraps past $FFFF into
        ; Z80 RAM ($0000) and copies garbage into the buffer tail. Forbid it: the window
        ; offset must leave room for the full copy below the $8000-window top.
        if (Song_Test & $7FFF) > ($8000 - SND_SONG_BUF_SIZE)
          fatal "Song_Test window region crosses the $8000-window top: the \{SND_SONG_BUF_SIZE}-byte load ldir would wrap past $FFFF into Z80 RAM. Move Song_Test so (addr & $7FFF) <= \{$8000 - SND_SONG_BUF_SIZE}."
        endif
        if (Song_PitchTest & $7FFF) > ($8000 - SND_SONG_BUF_SIZE)
          fatal "Song_PitchTest window region crosses the $8000-window top: the \{SND_SONG_BUF_SIZE}-byte load ldir would wrap past $FFFF into Z80 RAM. Move Song_PitchTest so (addr & $7FFF) <= \{$8000 - SND_SONG_BUF_SIZE}."
        endif

        align 2
