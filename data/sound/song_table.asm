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
; SONG_TRILLTEST (Sound Phase 3 Task 4): a SCRATCH one-FM-channel verification song
; emitting MULTI-POINT MEV_PITCHENV notes (a count=2 whole-step trill [$30,$32] and
; a count=3 major-triad arp [$24,$28,$2B]) so the controller can confirm ModUpdate's
; .multipoint per-frame cursor cycling. Copy-path, pitchtable_ptr=0 (engine default).
; Kept ALONGSIDE SONG_TEST/SONG_PITCHTEST so DEBUG boot can switch back after verifying.
SONG_TRILLTEST     = 3
; SONG_PANTEST (Sound Phase 3 Task 6): a SCRATCH one-FM-channel verification song
; exercising MEV_PAN ($E4, write-on-change $B4) and MEV_OPBIAS ($E9, per-operator
; TL bias latched in Fm_PatchLoad). A note hard-LEFT ($B4=$80, ~1s), the same note
; hard-RIGHT ($B4=$40, ~1s), then a recentered ($B4=$C0) note with a +$30 bias on
; modulator op0 (reg $40 = $68 vs $38), looping. Copy-path (FM6=DAC, RAM-buffered),
; pitchtable_ptr=0 -> engine default. Kept ALONGSIDE the other scratch songs so DEBUG
; boot can switch back. See data/sound/song_pantest.py for the expected $B4/$40 bytes.
SONG_PANTEST       = 4
SONG_COUNT         = 4

SongTable:
        dc.l    Song_Test           ; id 1 (SongTable[id-1])
        dc.l    Song_PitchTest      ; id 2 — Phase 3 Task 3 scratch pitch verification
        dc.l    Song_TrillTest      ; id 3 — Phase 3 Task 4 scratch trill/arp verification
        dc.l    Song_PanTest        ; id 4 — Phase 3 Task 6 scratch pan/op-bias verification
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
        dc.l    FmPatchTable        ; id 3 Song_TrillTest (copy path — entry unused)
        dc.l    FmPatchTable        ; id 4 Song_PanTest (copy path — entry unused)
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
        if (Song_TrillTest_End-Song_TrillTest) > SND_SONG_BUF_SIZE
          fatal "Song_TrillTest (\{Song_TrillTest_End-Song_TrillTest} bytes) exceeds SND_SONG_BUF_SIZE (\{SND_SONG_BUF_SIZE})"
        endif
        if (Song_PanTest_End-Song_PanTest) > SND_SONG_BUF_SIZE
          fatal "Song_PanTest (\{Song_PanTest_End-Song_PanTest} bytes) exceeds SND_SONG_BUF_SIZE (\{SND_SONG_BUF_SIZE})"
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
        if (Song_TrillTest & $7FFF) > ($8000 - SND_SONG_BUF_SIZE)
          fatal "Song_TrillTest window region crosses the $8000-window top: the \{SND_SONG_BUF_SIZE}-byte load ldir would wrap past $FFFF into Z80 RAM. Move Song_TrillTest so (addr & $7FFF) <= \{$8000 - SND_SONG_BUF_SIZE}."
        endif
        if (Song_PanTest & $7FFF) > ($8000 - SND_SONG_BUF_SIZE)
          fatal "Song_PanTest window region crosses the $8000-window top: the \{SND_SONG_BUF_SIZE}-byte load ldir would wrap past $FFFF into Z80 RAM. Move Song_PanTest so (addr & $7FFF) <= \{$8000 - SND_SONG_BUF_SIZE}."
        endif

        align 2
