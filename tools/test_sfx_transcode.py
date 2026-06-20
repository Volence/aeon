#!/usr/bin/env python3
"""Tests for sfx_transcode — S3K SMPS SFX source -> our engine SFX blob.

Run via:
    python3 -m pytest tools/test_sfx_transcode.py -q

Test coverage per Task 4 spec:
  - test_roundtrip_roll / test_roundtrip_skid: parse Roll + Skid from fixture
    strings; assert route, events, voice bytes, priority.
  - test_no_reserved_target: for Roll + Skid assert no channel targets
    FM1/FM2/FM6/DAC.
  - test_sfxtable_complete: SfxTable has SFX_COUNT entries + every SFXID_*
    maps to a label.
  - test_unknown_flag_errors: unknown $E0-$FF coord flag raises build error.
"""

import unittest
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sfx_transcode
from sfx_transcode import (
    transcode_sfx_source,
    pack_sfx, emit_sfx_table_asm,
    TranscodeError,
    SFXEL_FM, SFXEL_PSG, SFXEL_NOISE, SFXEL_NONE,
    SFXPRI_ROLL, SFXPRI_SKID, SFXPRI_RING, SFXPRI_JUMP,
    SFXPRI_DEATH, SFXPRI_RINGLOSS, SFXPRI_SPINDASH, SFXPRI_DASH,
    SHF_LOOP,
    _SFX_PRIORITY, _CORE_SFX_IDS, _sfx_label,
    _smps_note_to_pitch, FM_SFX_OCTAVE_SHIFT, PSG_OCTAVE_FIXUP,
    S3K_NOTE_BASE,
    CHROUTE_FM3, CHROUTE_FM4, CHROUTE_FM5,
    CHROUTE_PSG1, CHROUTE_PSG2, CHROUTE_PSG3, CHROUTE_PSGN,
)
from song_packer import (
    End, Vol, Patch, Pan, PsgEnv, Note, NoteDur, Rest, SetDur, RepeatStart, RepeatEnd,
    CHROUTE_FM1, CHROUTE_FM2, CHROUTE_FM6, CHROUTE_DAC,
    MEV_END, MEV_VOL, MEV_PATCH, MEV_PAN, MEV_PSGENV,
    PackError,
)

# ---------------------------------------------------------------------------
# Fixture strings (verbatim from skdisasm; trimmed to essentials for pytest)
# ---------------------------------------------------------------------------

ROLL_SRC = """\
Sound_3C_Header:
\tsmpsHeaderStartSong 3
\tsmpsHeaderVoice     Sound_3C_Voices
\tsmpsHeaderTempoSFX  $01
\tsmpsHeaderChanSFX   $01

\tsmpsHeaderSFXChannel cFM4, Sound_3C_FM4,\t$0C, $05

; FM4 Data
Sound_3C_FM4:
\tsmpsSetvoice        $00
\tdc.b\tnRst, $01
\tsmpsModSet          $03, $01, $09, $FF
\tdc.b\tnCs6, $25
\tsmpsModSet          $00, $01, $00, $00

Sound_3C_Loop00:
\tdc.b\tsmpsNoAttack
\tsmpsFMAlterVol      $01
\tdc.b\tnCs6, $02
\tsmpsLoop            $00, $2A, Sound_3C_Loop00
\tsmpsStop

Sound_3C_Voices:
;\tVoice $00
\tsmpsVcAlgorithm     $04
\tsmpsVcFeedback      $07
\tsmpsVcUnusedBits    $00
\tsmpsVcDetune        $00, $00, $04, $00
\tsmpsVcCoarseFreq    $02, $02, $04, $00
\tsmpsVcRateScale     $00, $00, $00, $00
\tsmpsVcAttackRate    $15, $1F, $1F, $1F
\tsmpsVcAmpMod        $00, $00, $00, $00
\tsmpsVcDecayRate1    $00, $00, $1F, $00
\tsmpsVcDecayRate2    $00, $00, $00, $00
\tsmpsVcDecayLevel    $00, $00, $00, $00
\tsmpsVcReleaseRate   $0F, $0F, $0F, $0F
\tsmpsVcTotalLevel    $00, $28, $00, $0D
"""

SKID_SRC = """\
Sound_36_Header:
\tsmpsHeaderStartSong 3
\tsmpsHeaderVoice     Sound_36_Voices
\tsmpsHeaderTempoSFX  $01
\tsmpsHeaderChanSFX   $02

\tsmpsHeaderSFXChannel cPSG2, Sound_36_PSG2,\t$00, $00
\tsmpsHeaderSFXChannel cPSG1, Sound_36_PSG1,\t$FE, $00

; PSG1 Data
Sound_36_PSG1:
\tdc.b\tnRst, $01

; PSG2 Data
Sound_36_PSG2:
\tsmpsPSGvoice        sTone_0D
\tdc.b\tnBb3, $01, nRst, nBb3, nRst, $03

Sound_36_Loop00:
\tdc.b\tnBb3, $01, nRst, $01
\tsmpsLoop            $00, $0B, Sound_36_Loop00
\tsmpsStop

; Song seems to not use any FM voices
Sound_36_Voices:
"""

RING_RIGHT_SRC = """\
Sound_33_Header:
\tsmpsHeaderStartSong 3
\tsmpsHeaderVoice     Sound_33_34_B9_Voices
\tsmpsHeaderTempoSFX  $01
\tsmpsHeaderChanSFX   $01

\tsmpsHeaderSFXChannel cFM4, Sound_33_FM4,\t$00, $05

; FM4 Data
Sound_33_FM4:
\tsmpsSetvoice        $00
\tsmpsPan             panRight, $00

Sound_34_Jump00:
\tdc.b\tnE5, $05, nG5, $05, nC6, $1B
\tsmpsStop

Sound_33_34_B9_Voices:
\tsmpsVcAlgorithm     $04
\tsmpsVcFeedback      $00
\tsmpsVcUnusedBits    $00
\tsmpsVcDetune        $04, $07, $07, $03
\tsmpsVcCoarseFreq    $09, $07, $02, $07
\tsmpsVcRateScale     $00, $00, $00, $00
\tsmpsVcAttackRate    $1F, $1F, $1F, $1F
\tsmpsVcAmpMod        $00, $00, $00, $00
\tsmpsVcDecayRate1    $0D, $07, $0A, $07
\tsmpsVcDecayRate2    $0B, $00, $0B, $00
\tsmpsVcDecayLevel    $00, $01, $00, $01
\tsmpsVcReleaseRate   $0F, $0F, $0F, $0F
\tsmpsVcTotalLevel    $00, $23, $00, $23
"""

# A fixture with an unknown coord flag — must raise TranscodeError.
UNKNOWN_FLAG_SRC = """\
Sound_XX_Header:
\tsmpsHeaderStartSong 3
\tsmpsHeaderVoice     Sound_XX_Voices
\tsmpsHeaderTempoSFX  $01
\tsmpsHeaderChanSFX   $01

\tsmpsHeaderSFXChannel cPSG1, Sound_XX_PSG1, $00, $00

; PSG1 Data
Sound_XX_PSG1:
\tsmpsAlterVol        $10
\tdc.b\tnC4, $10
\tsmpsStop

Sound_XX_Voices:
"""

# smpsAlterVol = $E6 in S2 / generic, which is NOT in our v1 coverage list.
# For S3K driver, smpsAlterVol expands to $E6,val. That's an unknown flag for us.


class TestRoundtripRoll(unittest.TestCase):
    """transcode_sfx_source on Roll fixture: check route, event shape, voice, priority."""

    def setUp(self):
        self.desc = transcode_sfx_source(ROLL_SRC, 0x3C)

    def test_channel_count(self):
        self.assertEqual(len(self.desc['channels']), 1)

    def test_route(self):
        ch = self.desc['channels'][0]
        self.assertEqual(ch['route'], CHROUTE_FM4)

    def test_kind(self):
        ch = self.desc['channels'][0]
        self.assertEqual(ch['kind'], SFXEL_FM)

    def test_has_voice(self):
        # Roll has one FM4 voice
        self.assertEqual(len(self.desc['voices']), 1)
        self.assertEqual(len(self.desc['voices'][0]), 26,
                         "FmPatch must be exactly 26 bytes")

    def test_events_contain_patch(self):
        events = self.desc['channels'][0]['events']
        patch_events = [e for e in events if isinstance(e, Patch)]
        self.assertGreaterEqual(len(patch_events), 1,
                                "FM channel must have a Patch (smpsSetvoice) event")

    def test_events_contain_notes(self):
        events = self.desc['channels'][0]['events']
        note_events = [e for e in events if isinstance(e, (Note, NoteDur))]
        self.assertGreaterEqual(len(note_events), 1,
                                "Roll must have at least one note event")

    def test_events_end_with_end(self):
        events = self.desc['channels'][0]['events']
        self.assertIsInstance(events[-1], End,
                              "Channel stream must end with End()")

    def test_priority(self):
        priority = _SFX_PRIORITY[0x3C]
        self.assertEqual(priority, SFXPRI_ROLL)

    def test_has_loop_flag(self):
        # Roll uses smpsLoop -> SHF_LOOP set
        self.assertTrue(self.desc['flags'] & SHF_LOOP,
                        "Roll smpsLoop should set SHF_LOOP flag")

    def test_pack_produces_bytes(self):
        blob = pack_sfx(self.desc, SFXPRI_ROLL)
        self.assertIsInstance(blob, bytes)
        self.assertGreater(len(blob), 4 + 6,
                           "Blob must be larger than the header alone")

    def test_blob_header_layout(self):
        blob = pack_sfx(self.desc, SFXPRI_ROLL)
        # [0] = priority
        self.assertEqual(blob[0], SFXPRI_ROLL)
        # [1] = flags
        self.assertEqual(blob[1], self.desc['flags'])
        # [2] = chcount
        self.assertEqual(blob[2], 1)
        # [3] = pad
        self.assertEqual(blob[3], 0x00)
        # per-channel record [4..9]: route, kind, cmd_ptr_hi, cmd_ptr_lo, voice_hi, voice_lo
        self.assertEqual(blob[4], CHROUTE_FM4)     # route
        self.assertEqual(blob[5], SFXEL_FM)         # kind
        # cmd_ptr must point past the header (4 + 1*6 = 10)
        cmd_ptr = (blob[6] << 8) | blob[7]
        self.assertEqual(cmd_ptr, 10, "cmd_ptr should be 10 (header + 1 channel record)")

    def test_not_reserved_route(self):
        ch = self.desc['channels'][0]
        self.assertNotIn(ch['route'], {CHROUTE_FM1, CHROUTE_FM2, CHROUTE_FM6, CHROUTE_DAC})


class TestRoundtripSkid(unittest.TestCase):
    """transcode_sfx_source on Skid fixture: PSG-only, 2 channels."""

    def setUp(self):
        self.desc = transcode_sfx_source(SKID_SRC, 0x36)

    def test_channel_count(self):
        self.assertEqual(len(self.desc['channels']), 2)

    def test_routes(self):
        routes = {ch['route'] for ch in self.desc['channels']}
        self.assertEqual(routes, {CHROUTE_PSG2, CHROUTE_PSG1})

    def test_kinds(self):
        for ch in self.desc['channels']:
            self.assertEqual(ch['kind'], SFXEL_PSG)

    def test_no_voices(self):
        # Skid is PSG-only — no FM voices
        self.assertEqual(len(self.desc['voices']), 0)

    def test_psg2_events_have_notes(self):
        # PSG2 (cPSG2) is the one with actual note data + smpsLoop
        psg2_ch = next(ch for ch in self.desc['channels']
                       if ch['route'] == CHROUTE_PSG2)
        events = psg2_ch['events']
        note_events = [e for e in events if isinstance(e, (Note, NoteDur))]
        self.assertGreaterEqual(len(note_events), 1)

    def test_events_end_with_end(self):
        for ch in self.desc['channels']:
            self.assertIsInstance(ch['events'][-1], End)

    def test_priority(self):
        self.assertEqual(_SFX_PRIORITY[0x36], SFXPRI_SKID)

    def test_has_loop_flag(self):
        self.assertTrue(self.desc['flags'] & SHF_LOOP)

    def test_psg_blob_has_no_voice_ptr(self):
        blob = pack_sfx(self.desc, SFXPRI_SKID)
        # header = 4 bytes; 2 channels * 6 bytes each
        for ch_idx in range(2):
            off = 4 + ch_idx * 6
            voice_hi = blob[off + 4]
            voice_lo = blob[off + 5]
            self.assertEqual((voice_hi << 8) | voice_lo, 0,
                             "PSG channel must have voice_ptr=0")

    def test_not_reserved_routes(self):
        for ch in self.desc['channels']:
            self.assertNotIn(ch['route'], {CHROUTE_FM1, CHROUTE_FM2, CHROUTE_FM6, CHROUTE_DAC})


class TestNoReservedTarget(unittest.TestCase):
    """For every transcoded SFX (Roll, Skid, Ring), assert no channel route is reserved."""

    def _assert_no_reserved(self, src: str, sfx_id: int):
        desc = transcode_sfx_source(src, sfx_id)
        for ch in desc['channels']:
            self.assertNotIn(
                ch['route'],
                {CHROUTE_FM1, CHROUTE_FM2, CHROUTE_FM6, CHROUTE_DAC},
                f"SFX ${sfx_id:02X} channel ${ch['chanid']:02X} maps to reserved route "
                f"{ch['route']} (FM1/FM2/FM6/DAC not stealable)")

    def test_no_reserved_roll(self):
        self._assert_no_reserved(ROLL_SRC, 0x3C)

    def test_no_reserved_skid(self):
        self._assert_no_reserved(SKID_SRC, 0x36)

    def test_no_reserved_ring_right(self):
        self._assert_no_reserved(RING_RIGHT_SRC, 0x33)

    def test_reserved_fm6_raises(self):
        """An SFX targeting cFM6 must raise TranscodeError (cFM6 = reserved in v1)."""
        src = """\
Sound_XX_Header:
\tsmpsHeaderStartSong 3
\tsmpsHeaderVoice     Sound_XX_Voices
\tsmpsHeaderTempoSFX  $01
\tsmpsHeaderChanSFX   $01
\tsmpsHeaderSFXChannel cFM6, Sound_XX_FM6, $00, $00
; FM6 Data
Sound_XX_FM6:
\tsmpsSetvoice        $00
\tdc.b\tnC5, $10
\tsmpsStop
Sound_XX_Voices:
\tsmpsVcAlgorithm     $04
\tsmpsVcFeedback      $00
\tsmpsVcUnusedBits    $00
\tsmpsVcDetune        $00, $00, $00, $00
\tsmpsVcCoarseFreq    $00, $00, $00, $00
\tsmpsVcRateScale     $00, $00, $00, $00
\tsmpsVcAttackRate    $1F, $1F, $1F, $1F
\tsmpsVcAmpMod        $00, $00, $00, $00
\tsmpsVcDecayRate1    $00, $00, $00, $00
\tsmpsVcDecayRate2    $00, $00, $00, $00
\tsmpsVcDecayLevel    $00, $00, $00, $00
\tsmpsVcReleaseRate   $0F, $0F, $0F, $0F
\tsmpsVcTotalLevel    $00, $00, $00, $00
"""
        with self.assertRaises(TranscodeError) as ctx:
            transcode_sfx_source(src, 0x99)
        self.assertIn('reserved', str(ctx.exception).lower())


class TestFmSfxOctaveKnob(unittest.TestCase):
    """FM_SFX_OCTAVE_SHIFT is a taste knob applied to FM notes only.

    It must lower FM SFX pitch indices by exactly FM_SFX_OCTAVE_SHIFT semitones
    (default -12 = one octave down) relative to the byte-exact-S3K pitch, and
    must NOT touch PSG notes (which carry their own PSG_OCTAVE_FIXUP).
    """

    def test_fm_note_shifted_by_knob(self):
        # nC5 = $BD; faithful FM index = 0xBD - 0x81 = 0x3C (60).
        raw = 0xBD
        faithful = raw - S3K_NOTE_BASE          # 0x3C
        got = _smps_note_to_pitch(raw, is_psg=False, transpose=0)
        self.assertEqual(got, faithful + FM_SFX_OCTAVE_SHIFT,
                         "FM note must be lowered by exactly FM_SFX_OCTAVE_SHIFT")

    def test_fm_note_with_transpose_shifted(self):
        # Roll: nCs6 = $CA, header transpose +$0C; faithful = 0xCA-0x81+0x0C = 0x55.
        raw, tr = 0xCA, 0x0C
        faithful = raw - S3K_NOTE_BASE + tr      # 0x55 (85)
        got = _smps_note_to_pitch(raw, is_psg=False, transpose=tr)
        self.assertEqual(got, faithful + FM_SFX_OCTAVE_SHIFT)

    def test_psg_note_not_shifted_by_fm_knob(self):
        # PSG keeps its scientific +24 fixup and is NOT affected by the FM knob.
        raw = 0xBD
        got = _smps_note_to_pitch(raw, is_psg=True, transpose=0)
        self.assertEqual(got, raw - S3K_NOTE_BASE + PSG_OCTAVE_FIXUP)

    def test_default_is_faithful(self):
        self.assertEqual(FM_SFX_OCTAVE_SHIFT, 0,
                         "default taste shift is 0 (S3K-faithful); -1 octave broke the ring")


class TestSfxTableComplete(unittest.TestCase):
    """SfxTable must have SFX_COUNT entries and every SFXID_* maps to a label."""

    def setUp(self):
        # Build a synthetic id_to_label map for the core set
        self.all_ids = _CORE_SFX_IDS
        self.id_to_label = {sfx_id: _sfx_label(sfx_id) for sfx_id in self.all_ids}

    def test_sfx_count(self):
        self.assertEqual(len(self.id_to_label), len(self.all_ids))

    def test_all_sfxid_present(self):
        # These are the symbolic SFXID_* from sound_constants.asm
        required_ids = [0x33, 0x34, 0x35, 0x36, 0x3C, 0x62, 0xAB, 0xB6, 0xB9]
        for sid in required_ids:
            self.assertIn(sid, self.id_to_label,
                          f"SFXID ${sid:02X} must be in the SfxTable")

    def test_table_asm_contains_all_labels(self):
        table_asm = emit_sfx_table_asm(self.all_ids, self.id_to_label)
        for sfx_id, label in self.id_to_label.items():
            self.assertIn(label, table_asm,
                          f"SfxTable asm must reference label {label!r} for id ${sfx_id:02X}")

    def test_table_asm_has_sfx_count_define(self):
        table_asm = emit_sfx_table_asm(self.all_ids, self.id_to_label)
        self.assertIn('SFX_COUNT', table_asm)

    def test_table_asm_has_completeness_assert(self):
        table_asm = emit_sfx_table_asm(self.all_ids, self.id_to_label)
        # The asm must have a `SfxTable_End - SfxTable` check
        self.assertIn('SfxTable_End', table_asm)
        self.assertIn('SfxTable_End-SfxTable', table_asm)

    def test_sfxtable_end_label_present(self):
        table_asm = emit_sfx_table_asm(self.all_ids, self.id_to_label)
        self.assertIn('SfxTable:', table_asm)
        self.assertIn('SfxTable_End:', table_asm)


class TestUnknownFlagErrors(unittest.TestCase):
    """Unknown $E0-$FF coord flag must raise TranscodeError, never silently drop."""

    def test_unknown_smps_macro_raises(self):
        """smpsAlterVol ($E6 in S2/generic) is NOT in v1 coverage -> must raise."""
        with self.assertRaises(TranscodeError) as ctx:
            transcode_sfx_source(UNKNOWN_FLAG_SRC, 0xFF)
        self.assertIn('unknown', str(ctx.exception).lower())

    def test_smpsnop_raises(self):
        """smpsNop ($E2) is NOT in our v1 coverage list -> must raise."""
        src = """\
Sound_XX_Header:
\tsmpsHeaderStartSong 3
\tsmpsHeaderVoice     Sound_XX_Voices
\tsmpsHeaderTempoSFX  $01
\tsmpsHeaderChanSFX   $01
\tsmpsHeaderSFXChannel cPSG1, Sound_XX_PSG1, $00, $00
Sound_XX_PSG1:
\tsmpsNop        $01
\tdc.b\tnC4, $10
\tsmpsStop
Sound_XX_Voices:
"""
        with self.assertRaises(TranscodeError):
            transcode_sfx_source(src, 0xFF)

    def test_known_flags_do_not_raise(self):
        """Known flags (smpsSetvoice, smpsPan, smpsModSet, smpsStop, smpsLoop,
        smpsFMAlterVol, smpsNoAttack, smpsSpindashRev, smpsResetSpindashRev,
        smpsPSGvoice, smpsPSGform) must NOT raise."""
        # Roll and Skid use these and must parse without error
        desc = transcode_sfx_source(ROLL_SRC, 0x3C)
        self.assertIsNotNone(desc)
        desc2 = transcode_sfx_source(SKID_SRC, 0x36)
        self.assertIsNotNone(desc2)

    def test_smpsmodset_logged_not_raised(self):
        """smpsModSet is intentionally lossy (dropped with log) not a build error."""
        # Roll contains smpsModSet — must succeed
        import io
        old_err = sys.stderr
        sys.stderr = io.StringIO()
        try:
            desc = transcode_sfx_source(ROLL_SRC, 0x3C)
            log = sys.stderr.getvalue()
        finally:
            sys.stderr = old_err
        self.assertIsNotNone(desc)
        self.assertIn('smpsModSet', log,
                      "smpsModSet must log a message (not silently drop)")


class TestBlobLayoutMatchesSfxHeader(unittest.TestCase):
    """Verify the packed blob exactly matches the SfxHeader field layout from
    sound_constants.asm Task 2:
      [0] sfh_priority, [1] sfh_flags, [2] sfh_chcount, [3] sfh_pad=0
      per channel record (6 bytes): route, kind, cmd_ptr(BE), voice_ptr(BE)
    """

    def test_roll_blob_header(self):
        desc = transcode_sfx_source(ROLL_SRC, 0x3C)
        blob = pack_sfx(desc, SFXPRI_ROLL)
        # 4-byte prefix
        self.assertEqual(blob[0], SFXPRI_ROLL)          # sfh_priority
        self.assertEqual(blob[1], desc['flags'])          # sfh_flags
        self.assertEqual(blob[2], 1)                      # sfh_chcount
        self.assertEqual(blob[3], 0)                      # sfh_pad
        # 6-byte per-channel record
        self.assertEqual(blob[4], CHROUTE_FM4)           # route
        self.assertEqual(blob[5], SFXEL_FM)               # kind
        cmd_ptr = (blob[6] << 8) | blob[7]
        # header=4, 1 channel*6=6, so stream starts at offset 10
        self.assertEqual(cmd_ptr, 10)
        # FM channel has a voice_ptr (points to patch bank after stream)
        voice_ptr = (blob[8] << 8) | blob[9]
        self.assertGreater(voice_ptr, 10,
                           "FM channel voice_ptr must point past the stream data")

    def test_skid_blob_header(self):
        desc = transcode_sfx_source(SKID_SRC, 0x36)
        blob = pack_sfx(desc, SFXPRI_SKID)
        # 4-byte prefix
        self.assertEqual(blob[0], SFXPRI_SKID)
        self.assertEqual(blob[2], 2)           # 2 channels
        self.assertEqual(blob[3], 0)           # pad
        # Channel 0 record starts at offset 4
        # PSG channels have voice_ptr=0
        voice_ptr_0 = (blob[8] << 8) | blob[9]
        self.assertEqual(voice_ptr_0, 0)
        # Channel 1 record starts at offset 10
        voice_ptr_1 = (blob[14] << 8) | blob[15]
        self.assertEqual(voice_ptr_1, 0)

    def test_blob_stream_ends_with_mev_end(self):
        """The packed stream for each channel must end with MEV_END ($FF)."""
        desc = transcode_sfx_source(ROLL_SRC, 0x3C)
        blob = pack_sfx(desc, SFXPRI_ROLL)
        # Find the stream for channel 0
        cmd_ptr = (blob[6] << 8) | blob[7]
        voice_ptr = (blob[8] << 8) | blob[9]
        # Stream spans cmd_ptr..voice_ptr (for FM with patch bank)
        stream = blob[cmd_ptr:voice_ptr]
        self.assertEqual(stream[-1], MEV_END,
                         f"Stream must end with MEV_END ($FF); got ${stream[-1]:02X}")

    def test_priority_map_covers_all_core_ids(self):
        """Every SFXID_* must have an entry in the priority map."""
        from sfx_transcode import _SFX_PRIORITY, _CORE_SFX_IDS
        for sid in _CORE_SFX_IDS:
            self.assertIn(sid, _SFX_PRIORITY,
                          f"SFXID ${sid:02X} missing from priority map")


class TestPriorityValues(unittest.TestCase):
    """Verify priority bytes match sound_constants.asm SFXPRI_* values."""

    def _p(self, sfx_id):
        return _SFX_PRIORITY[sfx_id]

    def test_ring_priority(self):
        self.assertEqual(self._p(0x33), 0x20)
        self.assertEqual(self._p(0x34), 0x20)

    def test_death_priority(self):
        self.assertEqual(self._p(0x35), 0xC0)

    def test_skid_priority(self):
        self.assertEqual(self._p(0x36), 0x60)

    def test_roll_priority(self):
        self.assertEqual(self._p(0x3C), 0x60)

    def test_jump_priority(self):
        self.assertEqual(self._p(0x62), 0x40)

    def test_spindash_priority(self):
        self.assertEqual(self._p(0xAB), 0x80)

    def test_dash_priority(self):
        self.assertEqual(self._p(0xB6), 0x80)

    def test_ringloss_priority(self):
        self.assertEqual(self._p(0xB9), 0xC0)


# PSG vol-env fixtures (SFX Expressive Fidelity Task 3).
# Jump (62) uses smpsPSGvoice sTone_0D on PSG1 before its first note.
JUMP_PSG_SRC = """\
Sound_62_Header:
\tsmpsHeaderStartSong 3
\tsmpsHeaderVoice     Sound_62_Voices
\tsmpsHeaderTempoSFX  $01
\tsmpsHeaderChanSFX   $01

\tsmpsHeaderSFXChannel cPSG1, Sound_62_PSG1,\t$00, $00

; PSG1 Data
Sound_62_PSG1:
\tsmpsPSGvoice        sTone_0D
\tdc.b\tnC5, $08, nRst, $08
\tsmpsStop

Sound_62_Voices:
"""

# An unmapped sTone (sTone_07 has no body in PsgVolEnv_Table) must raise.
UNMAPPED_STONE_SRC = """\
Sound_XY_Header:
\tsmpsHeaderStartSong 3
\tsmpsHeaderVoice     Sound_XY_Voices
\tsmpsHeaderTempoSFX  $01
\tsmpsHeaderChanSFX   $01

\tsmpsHeaderSFXChannel cPSG1, Sound_XY_PSG1, $00, $00

; PSG1 Data
Sound_XY_PSG1:
\tsmpsPSGvoice        sTone_07
\tdc.b\tnC5, $08
\tsmpsStop

Sound_XY_Voices:
"""


class TestPsgEnv(unittest.TestCase):
    """SFX Expressive Fidelity Task 3 — PSG volume envelopes."""

    def test_jump_emits_psgenv(self):
        # The Jump PSG1 channel must emit a PsgEnv(0x0D) BEFORE its first note.
        desc = transcode_sfx_source(JUMP_PSG_SRC, 0x62)
        ch = next(c for c in desc['channels'] if c['route'] == CHROUTE_PSG1)
        evs = ch['events']
        psgenv_idx = next(i for i, e in enumerate(evs) if isinstance(e, PsgEnv))
        self.assertEqual(evs[psgenv_idx].env_id, 0x0D)
        first_note = next(i for i, e in enumerate(evs)
                          if isinstance(e, (Note, NoteDur)))
        self.assertLess(psgenv_idx, first_note,
                        "PsgEnv must precede the first note")

    def test_skid_emits_psgenv(self):
        # Skid (36) PSG2 also carries smpsPSGvoice sTone_0D (existing fixture).
        desc = transcode_sfx_source(SKID_SRC, 0x36)
        ch = next(c for c in desc['channels'] if c['route'] == CHROUTE_PSG2)
        self.assertTrue(any(isinstance(e, PsgEnv) and e.env_id == 0x0D
                            for e in ch['events']))

    def test_psgenv_encodes(self):
        self.assertEqual(PsgEnv(0x0D).encode(), bytes([0xEB, 0x0D]))
        self.assertEqual(PsgEnv(0x1D).encode(), bytes([MEV_PSGENV, 0x1D]))

    def test_psgenv_rejects_fm(self):
        from song_packer import CHROUTE_FM3
        with self.assertRaises(PackError):
            PsgEnv(0x0D).validate(CHROUTE_FM3)

    def test_psgenv_accepts_psg_and_noise(self):
        # Must NOT raise on PSG / noise routes.
        PsgEnv(0x0D).validate(CHROUTE_PSG1)
        PsgEnv(0x0D).validate(CHROUTE_PSGN)

    def test_unmapped_stone_errors(self):
        with self.assertRaises(TranscodeError):
            transcode_sfx_source(UNMAPPED_STONE_SRC, 0x99)


if __name__ == '__main__':
    unittest.main()
