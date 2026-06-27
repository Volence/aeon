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
    _LOG_VOLUME_LUT, _vol_for_atten, _validate_sfx_repeat,
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
        self.assertEqual(len(self.desc['voices'][0]), 32,
                         "FmPatch must be exactly 32 bytes (incl. SSG-EG group + pad)")

    def test_no_patch_event_emitted(self):
        # SFX must NOT emit MEV_PATCH: the engine's Sfx_Steal pre-loads the SFX's own
        # voice (sx_patch_base); a stream MEV_PATCH re-resolves via the MUSIC patch
        # table and OVERWRITES it with garbage, corrupting the SFX timbre. smpsSetvoice
        # $00 is dropped (the steal already loaded voice 0). Regression guard for the
        # ring/FM-SFX "wrong timbre" bug found via VGM register capture.
        events = self.desc['channels'][0]['events']
        patch_events = [e for e in events if isinstance(e, Patch)]
        self.assertEqual(len(patch_events), 0,
                         "FM SFX must NOT emit MEV_PATCH (the steal pre-loads the voice)")

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

    def test_no_cross_channel_contamination(self):
        # Skid source lists PSG2 first in the header but lays Sound_36_PSG1
        # BEFORE Sound_36_PSG2 in the file; PSG1's block is only `dc.b nRst, $01`
        # with no smpsStop.  The parser must stop PSG1 at the Sound_36_PSG2 label
        # (channel boundary) and NOT consume PSG2's smpsPSGvoice / nBb3 loop.
        psg1_ch = next(ch for ch in self.desc['channels']
                       if ch['route'] == CHROUTE_PSG1)
        psg2_ch = next(ch for ch in self.desc['channels']
                       if ch['route'] == CHROUTE_PSG2)

        # PSG1 must NOT contain PSG2's PsgEnv (sTone_0D) — that is PSG2's pattern.
        psg1_has_psgenv = any(isinstance(e, PsgEnv) for e in psg1_ch['events'])
        self.assertFalse(psg1_has_psgenv,
                         "PSG1 wrongly contains a PSG volume envelope (PSG2's data leaked in)")

        # PSG1 must NOT contain the nBb3 note (pitch index of nBb3) — PSG2's note.
        psg2_pitches = {e.pitch for e in psg2_ch['events']
                        if isinstance(e, (Note, NoteDur))}
        psg1_pitches = {e.pitch for e in psg1_ch['events']
                        if isinstance(e, (Note, NoteDur))}
        self.assertTrue(psg2_pitches, "PSG2 should have at least one played note")
        self.assertEqual(psg1_pitches & psg2_pitches, set(),
                         "PSG1 shares PSG2's note pattern — cross-channel contamination")

        # PSG1's only musical content is a single rest (nRst); it must have NO
        # played notes at all.
        self.assertEqual(len(psg1_pitches), 0,
                         "PSG1 should only contain a rest, no played notes")

        # PSG1's stream must NOT loop (only PSG2 has the smpsLoop).
        psg1_has_repeat = any(isinstance(e, (RepeatStart, RepeatEnd))
                              for e in psg1_ch['events'])
        self.assertFalse(psg1_has_repeat,
                         "PSG1 wrongly contains a repeat (PSG2's smpsLoop leaked in)")

        # Both channels must still terminate with End (PSG1 via the injected
        # implicit channel-boundary end).
        self.assertIsInstance(psg1_ch['events'][-1], End)
        self.assertIsInstance(psg2_ch['events'][-1], End)


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

    def test_octave_shift_in_taste_range(self):
        # FM_SFX_OCTAVE_SHIFT is a by-ear taste knob (S3K-faithful = 0 is verified high).
        # Assert a sane range (<=0, within 3 octaves) rather than an exact value so tuning
        # passes don't churn the test.
        self.assertTrue(-36 <= FM_SFX_OCTAVE_SHIFT <= 0,
                        "taste shift must be 0..-36 semitones (a whole-number-ish lowering)")


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

    def test_smpsmodset_emits_modset(self):
        """SFX Expressive Fidelity Task 4: smpsModSet now EMITS MEV_MODSET (the
        faithful pitch-modulation latch), it is no longer dropped. Roll's FM4 carries
        smpsModSet $03,$01,$09,$FF then $00,$01,$00,$00 (mod-off)."""
        from song_packer import ModSet
        desc = transcode_sfx_source(ROLL_SRC, 0x3C)
        ch = next(c for c in desc['channels'] if c['route'] == CHROUTE_FM4)
        mods = [e for e in ch['events'] if isinstance(e, ModSet)]
        self.assertEqual(len(mods), 2, "Roll FM4 has two smpsModSet ops")
        self.assertEqual((mods[0].wait, mods[0].speed, mods[0].change, mods[0].step),
                         (0x03, 0x01, 0x09, 0xFF))
        # the second is the mod-off cancel
        self.assertEqual((mods[1].wait, mods[1].speed, mods[1].change, mods[1].step),
                         (0x00, 0x01, 0x00, 0x00))


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


class TestModSet(unittest.TestCase):
    """SFX Expressive Fidelity Task 4 — FM pitch modulation (smpsModSet -> MEV_MODSET)."""

    def test_modset_encodes(self):
        from song_packer import ModSet, MEV_MODSET
        # change $F8 = -8 must encode back to the byte $F8 (two's complement).
        self.assertEqual(ModSet(0x02, 0x01, -8, 0x65).encode(),
                         bytes([0xEC, 0x02, 0x01, 0xF8, 0x65]))
        self.assertEqual(ModSet(0x01, 0x01, 0x1A, 0x01).encode(),
                         bytes([MEV_MODSET, 0x01, 0x01, 0x1A, 0x01]))

    def test_modset_off_encodes(self):
        from song_packer import ModSet
        # the smpsModSet 0,0,0,0 mod-off idiom.
        self.assertEqual(ModSet(0, 0, 0, 0).encode(), bytes([0xEC, 0, 0, 0, 0]))

    def test_modset_validate_byte_range(self):
        from song_packer import ModSet
        ModSet(0xFF, 0xFF, -128, 0xFF).validate(CHROUTE_FM5)   # extremes OK
        ModSet(0x00, 0x00, 127, 0x00).validate(CHROUTE_FM5)
        with self.assertRaises(PackError):
            ModSet(0x100, 0, 0, 0).validate(CHROUTE_FM5)       # wait out of range
        with self.assertRaises(PackError):
            ModSet(0, 0, -200, 0).validate(CHROUTE_FM5)        # change out of signed range

    def test_spindash_emits_modset(self):
        # Spin Dash (AB) FM5: smpsModSet $01,$01,$1A,$01 then a mod-off $00,$00,$00,$00.
        from song_packer import ModSet
        src = """\
Sound_AB_Header:
\tsmpsHeaderStartSong 3
\tsmpsHeaderVoice     Sound_AB_Voices
\tsmpsHeaderTempoSFX  $01
\tsmpsHeaderChanSFX   $01
\tsmpsHeaderSFXChannel cFM5, Sound_AB_FM5,\t$00, $00
Sound_AB_FM5:
\tsmpsSpindashRev
\tsmpsSetvoice        $00
\tsmpsModSet          $01, $01, $1A, $01
\tdc.b\tnC5, $18, smpsNoAttack
\tsmpsModSet          $00, $00, $00, $00
\tdc.b\t$02
\tsmpsStop
Sound_AB_Voices:
\tsmpsVcAlgorithm     $04
\tsmpsVcFeedback      $06
\tsmpsVcUnusedBits    $00
\tsmpsVcDetune        $00, $00, $00, $00
\tsmpsVcCoarseFreq    $09, $03, $0C, $00
\tsmpsVcRateScale     $03, $02, $02, $02
\tsmpsVcAttackRate    $15, $0C, $0F, $1F
\tsmpsVcAmpMod        $00, $00, $00, $00
\tsmpsVcDecayRate1    $00, $00, $00, $00
\tsmpsVcDecayRate2    $00, $00, $00, $00
\tsmpsVcDecayLevel    $00, $00, $00, $00
\tsmpsVcReleaseRate   $0F, $0F, $0F, $0F
\tsmpsVcTotalLevel    $00, $1C, $00, $00
"""
        from sfx_transcode import _SPINDASH_MOD_SCALE
        desc = transcode_sfx_source(src, 0xAB)
        ch = next(c for c in desc['channels'] if c['route'] == CHROUTE_FM5)
        mods = [e for e in ch['events'] if isinstance(e, ModSet)]
        self.assertEqual(len(mods), 2)
        # The spindash per-step delta is taste-tamed (sweep too aggressive); the wait/speed/
        # step stay byte-exact. Expected change = round($1A * scale).
        tamed = int(round(0x1A * _SPINDASH_MOD_SCALE)) or 1
        self.assertEqual((mods[0].wait, mods[0].speed, mods[0].change, mods[0].step),
                         (0x01, 0x01, tamed, 0x01))
        self.assertEqual((mods[1].wait, mods[1].speed, mods[1].change, mods[1].step),
                         (0x00, 0x00, 0x00, 0x00))

    def test_modset_precedes_note(self):
        # The active ModSet must be latched BEFORE the note it modulates (Roll FM4).
        from song_packer import ModSet
        desc = transcode_sfx_source(ROLL_SRC, 0x3C)
        ch = next(c for c in desc['channels'] if c['route'] == CHROUTE_FM4)
        evs = ch['events']
        first_mod = next(i for i, e in enumerate(evs) if isinstance(e, ModSet))
        first_note = next(i for i, e in enumerate(evs) if isinstance(e, (Note, NoteDur)))
        self.assertLess(first_mod, first_note,
                        "the first ModSet must precede the first note it modulates")


# Spin Dash (AB) FM5 fixture (verbatim from skdisasm SFX/AB - Spin Dash.asm):
# smpsSpindashRev at the start, bare nC5 note (the rev escalation is RUNTIME, applied
# by the engine via the global Snd_SpindashRev -> sc_transpose), smpsResetSpindashRev
# at the end (which the engine handles by the dispatch-fold reset, so no opcode).
SPINDASH_SRC = """\
Sound_AB_Header:
\tsmpsHeaderStartSong 3
\tsmpsHeaderVoice     Sound_AB_Voices
\tsmpsHeaderTempoSFX  $01
\tsmpsHeaderChanSFX   $01
\tsmpsHeaderSFXChannel cFM5, Sound_AB_FM5,\t$00, $00
Sound_AB_FM5:
\tsmpsSpindashRev
\tsmpsSetvoice        $00
\tsmpsModSet          $01, $01, $1A, $01
\tdc.b\tnC5, $18, smpsNoAttack
\tsmpsModSet          $00, $00, $00, $00
\tdc.b\t$02
\tsmpsResetSpindashRev
\tsmpsStop
Sound_AB_Voices:
\tsmpsVcAlgorithm     $04
\tsmpsVcFeedback      $06
\tsmpsVcUnusedBits    $00
\tsmpsVcDetune        $00, $00, $00, $00
\tsmpsVcCoarseFreq    $09, $03, $0C, $00
\tsmpsVcRateScale     $03, $02, $02, $02
\tsmpsVcAttackRate    $15, $0C, $0F, $1F
\tsmpsVcAmpMod        $00, $00, $00, $00
\tsmpsVcDecayRate1    $00, $00, $00, $00
\tsmpsVcDecayRate2    $00, $00, $00, $00
\tsmpsVcDecayLevel    $00, $00, $00, $00
\tsmpsVcReleaseRate   $0F, $0F, $0F, $0F
\tsmpsVcTotalLevel    $00, $1C, $00, $00
"""


class TestSpindashRev(unittest.TestCase):
    """SFX Expressive Fidelity Task 6 — runtime spindash rev escalation."""

    def test_spindash_emits_rev_op(self):
        # FM5 must emit a SpinRev (first event) and keep the bare nC5 note (NOT a
        # flat-baked-up pitch). The RESET is dispatch-folded -> no SpinRev/Reset opcode.
        from song_packer import SpinRev
        desc = transcode_sfx_source(SPINDASH_SRC, 0xAB)
        ch = next(c for c in desc['channels'] if c['route'] == CHROUTE_FM5)
        evs = ch['events']
        spin = next(i for i, e in enumerate(evs) if isinstance(e, SpinRev))
        first_note = next(i for i, e in enumerate(evs)
                          if isinstance(e, (Note, NoteDur)))
        self.assertLess(spin, first_note, "SpinRev must precede the note")

    def test_spindash_note_is_bare_nc5(self):
        # The note stays the byte-exact nC5 (the rev transpose is applied at RUNTIME by
        # the engine, not baked into the transcoded pitch). nC5 = $BD -> FM index $3C.
        desc = transcode_sfx_source(SPINDASH_SRC, 0xAB)
        ch = next(c for c in desc['channels'] if c['route'] == CHROUTE_FM5)
        from sfx_transcode import _fm_octave_for
        note = next(e for e in ch['events'] if isinstance(e, (Note, NoteDur)))
        expected = 0xBD - S3K_NOTE_BASE + _fm_octave_for(0xAB)   # bare nC5 + per-SFX octave
        self.assertEqual(note.pitch, expected,
                         "the spindash note must stay the bare nC5 (no flat rev bake)")

    def test_spinrev_encodes(self):
        from song_packer import SpinRev, MEV_SPINREV
        self.assertEqual(SpinRev().encode(), bytes([0xF0]))
        self.assertEqual(SpinRev().encode(), bytes([MEV_SPINREV]))

    def test_reset_is_dispatch_folded_no_opcode(self):
        # smpsResetSpindashRev emits NO stream opcode (the engine resets the global rev
        # via the Sfx_BeginSound dispatch fold on any non-spindash SFX).
        from song_packer import SpinRev
        desc = transcode_sfx_source(SPINDASH_SRC, 0xAB)
        ch = next(c for c in desc['channels'] if c['route'] == CHROUTE_FM5)
        # exactly one SpinRev, and no encoded $F1 (SPINREV_RESET) anywhere.
        spinrevs = [e for e in ch['events'] if isinstance(e, SpinRev)]
        self.assertEqual(len(spinrevs), 1)
        for e in ch['events']:
            self.assertNotIn(0xF1, e.encode(),
                             "no MEV_SPINREV_RESET ($F1) opcode should be emitted")

    def test_no_spindash_step_constant(self):
        # The old flat-bake machinery is gone (the rev is now runtime, not a transcode
        # accumulator).
        self.assertFalse(hasattr(sfx_transcode, '_SPINDASH_STEP'),
                         "_SPINDASH_STEP (the flat spindash bake) must be removed")


class TestFmVoiceOperatorOrder(unittest.TestCase):
    """Regression guard for audit B1/#6: an S3K SMPS FM voice must land each operator
    value on the SAME physical YM2612 register that S3K's own driver targets.

    S3K uploads via zFMInstrumentOperatorTable = [$30,$38,$34,$3C]; our engine's
    Fm_PatchOpGroup writes array index k -> base+k*4 = [$30,$34,$38,$3C]. The two
    register sequences differ in the middle pair, so the macro-arg order
    [op1,op2,op3,op4] must map to FmPatch order [op4,op2,op3,op1] (_s3k_op_reorder),
    UNIFORMLY across all six op groups. (The pre-fix code applied a plain reverse to
    four groups and left d2r/sl_rr unreordered — both wrong.)
    """

    def test_s3k_op_reorder_permutation(self):
        from sfx_transcode import _s3k_op_reorder
        self.assertEqual(_s3k_op_reorder([1, 2, 3, 4]), [4, 2, 3, 1])
        # explicitly NOT the old plain-reverse and NOT identity (the two prior bugs)
        self.assertNotEqual(_s3k_op_reorder([1, 2, 3, 4]), [4, 3, 2, 1])
        self.assertNotEqual(_s3k_op_reorder([1, 2, 3, 4]), [1, 2, 3, 4])

    def test_all_groups_reordered_uniformly(self):
        # Build a voice whose four operators carry DISTINCT marker values per group, so
        # the output byte order is an unambiguous witness of the permutation.
        from sfx_transcode import _SmpsVoiceBuilder
        b = _SmpsVoiceBuilder()
        b.apply('smpsVcAlgorithm',  ['4'])
        b.apply('smpsVcFeedback',   ['0'])
        b.apply('smpsVcDetune',     ['1', '2', '3', '4'])   # op1..op4
        b.apply('smpsVcCoarseFreq', ['0', '0', '0', '0'])
        b.apply('smpsVcRateScale',  ['0', '0', '0', '0'])
        b.apply('smpsVcAttackRate', ['1', '2', '3', '4'])
        b.apply('smpsVcAmpMod',     ['0', '0', '0', '0'])
        b.apply('smpsVcDecayRate1', ['1', '2', '3', '4'])
        b.apply('smpsVcDecayRate2', ['1', '2', '3', '4'])
        b.apply('smpsVcDecayLevel', ['0', '0', '0', '0'])
        b.apply('smpsVcReleaseRate',['1', '2', '3', '4'])
        b.apply('smpsVcTotalLevel', ['1', '2', '3', '4'])   # must be applied LAST
        out = b.build()
        self.assertEqual(len(out), 32)
        # header
        self.assertEqual(out[0], (0 << 3) | 4, "alg_fb = (fb<<3)|algo")
        self.assertEqual(out[1], 0xC0, "lr_ams_fms defaults to L/R both set")
        # group order in the blob: dt_mul, tl, ks_ar, am_d1r, d2r, sl_rr
        # each group's macro-arg [op1,op2,op3,op4] -> FmPatch [op4,op2,op3,op1]
        self.assertEqual(list(out[2:6]),  [0x40, 0x20, 0x30, 0x10], "dt_mul = (det<<4) reordered")
        self.assertEqual(list(out[6:10]), [4, 2, 3, 1], "tl reordered (op4,op2,op3,op1)")
        self.assertEqual(list(out[10:14]),[4, 2, 3, 1], "ks_ar reordered")
        self.assertEqual(list(out[14:18]),[4, 2, 3, 1], "am_d1r reordered")
        self.assertEqual(list(out[18:22]),[4, 2, 3, 1], "d2r reordered (was the unreordered bug)")
        self.assertEqual(list(out[22:26]),[4, 2, 3, 1], "sl_rr reordered (was the unreordered bug)")
        self.assertEqual(list(out[26:30]), [0, 0, 0, 0], "fp_ssg_eg default off")
        self.assertEqual(list(out[30:32]), [0, 0], "fp_reserved pad")


class TestFmDecayEnvelopeParsed(unittest.TestCase):
    """Regression guard: the voice-block parser must capture smpsVcDecayRate1/2.

    The dispatch regex was `(smpsVc[A-Za-z]+)` — `[A-Za-z]+` dropped the trailing
    digit, so `smpsVcDecayRate1`/`smpsVcDecayRate2` were captured as `smpsVcDecayRate`,
    missed apply()'s exact-name match, fell through to `else: pass`, and D1R/D2R (the
    FM decay envelope) were silently ZEROED on every FM SFX -> wrong no-decay timbre
    (verified against the real S&K ROM via VGM register capture). This exercises the
    regex/parse path that the builder-only operator-order test bypasses.
    """

    def test_ring_decay_rates_not_zeroed(self):
        desc = transcode_sfx_source(RING_RIGHT_SRC, 0x33)
        self.assertEqual(len(desc['voices']), 1)
        v = desc['voices'][0]
        # 26-byte FmPatch: [0]alg_fb [1]lr [2:6]dt_mul [6:10]tl [10:14]ks_ar
        #                  [14:18]am_d1r [18:22]d2r [22:26]sl_rr
        am_d1r = list(v[14:18])
        d2r = list(v[18:22])
        # source D1R [op1..op4]=[$0D,$07,$0A,$07] -> _s3k_op_reorder [op4,op2,op3,op1];
        # D2R [$0B,$00,$0B,$00] -> reorder. These match the real S&K ROM register dump.
        self.assertEqual(am_d1r, [0x07, 0x07, 0x0A, 0x0D],
                         "smpsVcDecayRate1 must be parsed (D1R was zeroed by the [A-Za-z]+ regex)")
        self.assertEqual(d2r, [0x00, 0x00, 0x0B, 0x0B],
                         "smpsVcDecayRate2 must be parsed (D2R was zeroed by the [A-Za-z]+ regex)")

    def test_ring_channel_volume_baked_into_carriers(self):
        # The SFX channel-volume (RING_RIGHT_SRC header vol = $05) is baked LINEARLY
        # into the CARRIER TLs (alg 4 carriers = TL bytes [2],[3] per CarrierMaskTableZ
        # $0C), matching S&K's key-on volume. Our engine's log-volume curve would
        # otherwise flatten it to ~0 (carriers ~4 dB too bright). Verified vs the real
        # S&K ROM: ring TL = 23 23 05 05. NO Vol event is emitted for FM (it's in the patch).
        desc = transcode_sfx_source(RING_RIGHT_SRC, 0x33)
        tl = list(desc['voices'][0][6:10])   # [S1,S3,S2,S4]
        self.assertEqual(tl, [0x23, 0x23, 0x05, 0x05],
                         "ring carriers (bytes 2,3) must carry the baked $05 channel-volume")
        fm_ch = next(c for c in desc['channels'] if c['route'] in (CHROUTE_FM3, CHROUTE_FM4, CHROUTE_FM5))
        self.assertEqual([e for e in fm_ch['events'] if isinstance(e, Vol)], [],
                         "FM SFX must not emit a Vol event (channel-volume is baked into the patch)")


# Spindash-rev ($AB): the loop body is the SMPS bare-duration "replay previous note"
# idiom (dc.b smpsNoAttack, $02) + a per-pass smpsFMAlterVol fade.
SPINDASH_SRC = """\
Sound_AB_Header:
\tsmpsHeaderStartSong 3
\tsmpsHeaderVoice     Sound_AB_Voices
\tsmpsHeaderTempoSFX  $01
\tsmpsHeaderChanSFX   $01

\tsmpsHeaderSFXChannel cFM5, Sound_AB_FM5,\t$00, $00

Sound_AB_FM5:
\tsmpsSpindashRev
\tsmpsSetvoice        $00
\tsmpsModSet          $01, $01, $1A, $01
\tdc.b\tnC5, $18
\tsmpsNoAttack
\tsmpsModSet          $00, $00, $00, $00
\tdc.b\t$02

Sound_AB_Loop00:
\tdc.b\tsmpsNoAttack, $02
\tsmpsFMAlterVol      $02
\tsmpsLoop            $00, $18, Sound_AB_Loop00
\tsmpsResetSpindashRev
\tsmpsStop

Sound_AB_Voices:
\tsmpsVcAlgorithm     $04
\tsmpsVcFeedback      $07
\tsmpsVcUnusedBits    $00
\tsmpsVcDetune        $00, $00, $00, $00
\tsmpsVcCoarseFreq    $03, $0C, $09, $00
\tsmpsVcRateScale     $00, $00, $00, $00
\tsmpsVcAttackRate    $1F, $1F, $1F, $1F
\tsmpsVcAmpMod        $00, $00, $00, $00
\tsmpsVcDecayRate1    $00, $00, $00, $00
\tsmpsVcDecayRate2    $00, $00, $00, $00
\tsmpsVcDecayLevel    $00, $00, $00, $00
\tsmpsVcReleaseRate   $0F, $0F, $0F, $0F
\tsmpsVcTotalLevel    $00, $1C, $00, $00
"""


class TestLogVolumeLut(unittest.TestCase):
    """The transcoder's LogVolumeLutZ mirror must match the engine table, and the
    inverse must round-trip — the faithful AlterVol fade depends on both."""

    def test_lut_length_and_bounds(self):
        self.assertEqual(len(_LOG_VOLUME_LUT), 128)
        self.assertEqual(_LOG_VOLUME_LUT[0], 0x7F)   # index 0 = silent
        self.assertEqual(_LOG_VOLUME_LUT[127], 0x00)  # index 127 = loudest
        # monotonic non-increasing (louder index -> lower attenuation)
        self.assertTrue(all(_LOG_VOLUME_LUT[i] >= _LOG_VOLUME_LUT[i + 1]
                            for i in range(127)))

    def test_lut_matches_engine_table(self):
        """Parse engine/sound_tables_z80.asm LogVolumeLutZ and assert byte-equality —
        catches any future drift between the engine table and the transcoder mirror."""
        eng = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           'engine', 'sound_tables_z80.asm')
        with open(eng) as f:
            text = f.read()
        start = text.index('LogVolumeLutZ:')
        end = text.index('LogVolumeLutZ_End:')
        body = text[start:end]
        vals = []
        for line in body.splitlines():
            line = line.strip()
            if not line.startswith('db'):
                continue
            for tok in line[2:].split(','):
                tok = tok.strip()
                if tok.endswith('h'):
                    vals.append(int(tok[:-1], 16))
        self.assertEqual(vals[:128], _LOG_VOLUME_LUT,
                         "transcoder _LOG_VOLUME_LUT drifted from engine LogVolumeLutZ")

    def test_vol_for_atten_inverse(self):
        self.assertEqual(_vol_for_atten(0x00), 127)   # zero attenuation -> loudest
        self.assertEqual(_vol_for_atten(0x07), 99)    # ties resolve to loudest index
        # round-trip: inverting an exact LUT attenuation lands on an index with that value
        for k in (20, 50, 80, 99, 110):
            self.assertEqual(_LOG_VOLUME_LUT[_vol_for_atten(_LOG_VOLUME_LUT[k])],
                             _LOG_VOLUME_LUT[k])


class TestRollFadeTail(unittest.TestCase):
    """Roll ($3C): the 42-pass smpsFMAlterVol fade must be UNROLLED into per-pass
    decreasing Vol events (not a frozen Vol in a RepeatStart/End), so the tail decays
    to quiet instead of holding flat and hard-cutting (bug #1)."""

    def setUp(self):
        self.ch = transcode_sfx_source(ROLL_SRC, 0x3C)['channels'][0]
        self.ev = self.ch['events']

    def test_no_repeat_block(self):
        # fully unrolled — no back-patched repeat survives for an AlterVol loop
        self.assertEqual([e for e in self.ev if isinstance(e, (RepeatStart, RepeatEnd))], [],
                         "AlterVol loop must be unrolled, not left as RepeatStart/End")

    def test_tail_has_42_passes(self):
        # 1 main note + 42 unrolled loop notes
        notes = [e for e in self.ev if isinstance(e, NoteDur)]
        self.assertEqual(len(notes), 43)

    def test_tail_volume_fades_monotonically(self):
        vols = [e.vol for e in self.ev if isinstance(e, Vol)]
        self.assertEqual(len(vols), 42, "one Vol per unrolled pass")
        self.assertTrue(all(vols[i] >= vols[i + 1] for i in range(len(vols) - 1)),
                        "fade must be monotonically non-increasing")
        self.assertGreater(vols[0], vols[-1] + 40,
                           "fade must span a wide range (loud -> quiet)")

    def test_fade_is_db_faithful(self):
        # S&K smpsFMAlterVol $01 == +1 TL attenuation per pass. Our per-pass Vol must
        # render +1 attenuation each step (via LogVolumeLut), i.e. consecutive passes
        # differ by exactly 1 attenuation unit.
        vols = [e.vol for e in self.ev if isinstance(e, Vol)]
        attens = [_LOG_VOLUME_LUT[v] for v in vols]
        steps = [attens[i + 1] - attens[i] for i in range(len(attens) - 1)]
        self.assertTrue(all(s == 1 for s in steps),
                        f"each pass must add +1 TL attenuation (S&K $01); got {steps}")


class TestSpindashTailNotCollapsed(unittest.TestCase):
    """Spindash-rev ($AB): the bare-duration 'replay previous note' idiom must emit a
    real note so the loop body advances time (not a zero-tick collapse, bug #3), AND
    the per-pass fade must be unrolled."""

    def setUp(self):
        self.ev = transcode_sfx_source(SPINDASH_SRC, 0xAB)['channels'][0]['events']

    def test_loop_body_has_time_advancing_notes(self):
        notes = [e for e in self.ev if isinstance(e, NoteDur)]
        # main(24t) + dc.b $02 replay + 24 loop-pass replays
        self.assertGreaterEqual(len(notes), 25,
                                "the bare-duration replay must re-articulate the note "
                                "each pass (no zero-tick loop-body collapse)")

    def test_no_repeat_block(self):
        self.assertEqual([e for e in self.ev if isinstance(e, (RepeatStart, RepeatEnd))], [])

    def test_tail_fades(self):
        vols = [e.vol for e in self.ev if isinstance(e, Vol)]
        self.assertEqual(len(vols), 24)
        self.assertTrue(all(vols[i] >= vols[i + 1] for i in range(len(vols) - 1)))

    def test_bare_duration_replays_last_pitch(self):
        # every loop-body note is the same pitch as the main note (nC5 replay).
        # Mask bit 7 (the smpsNoAttack/held flag) before comparing pitches.
        notes = [e for e in self.ev if isinstance(e, NoteDur)]
        main_pitch = notes[0].pitch & 0x7F
        self.assertTrue(all((n.pitch & 0x7F) == main_pitch for n in notes),
                        "bare-duration replay must re-use the previous note's pitch")


class TestNoAttackHeldTail(unittest.TestCase):
    """smpsNoAttack -> bit 7 of the NoteDur pitch tells the engine to HOLD the note
    (skip the $28 re-attack). The whole looped fade tail holds — ONLY the main note
    attacks (one key-on total). Seq_Op_ModSet re-writes the base freq (no key-on) when
    a sweep modSet turns off, so the tail no longer needs a re-key to reset the swept
    pitch (which removes the faint 'second attack' at the main->tail seam)."""

    def test_roll_tail_all_held_after_main(self):
        ev = transcode_sfx_source(ROLL_SRC, 0x3C)['channels'][0]['events']
        nd = [e for e in ev if isinstance(e, NoteDur)]
        attacked = [i for i, e in enumerate(nd) if not (e.pitch & 0x80)]
        # exactly ONE attack: the main note (0); the entire 42-pass tail holds.
        self.assertEqual(attacked, [0],
                         f"roll should attack only the main note; got {attacked}")
        self.assertTrue(all(e.pitch & 0x80 for e in nd[1:]),
                        "all roll tail passes must be held")

    def test_spindash_tail_all_held_after_main(self):
        ev = transcode_sfx_source(SPINDASH_SRC, 0xAB)['channels'][0]['events']
        nd = [e for e in ev if isinstance(e, NoteDur)]
        attacked = [i for i, e in enumerate(nd) if not (e.pitch & 0x80)]
        # ONE attack: the main note (0); the dc.b $02 replay + 24 loop passes all hold.
        self.assertEqual(attacked, [0],
                         f"spindash should attack only the main note; got {attacked}")

    def test_skid_notes_all_attack(self):
        # Skid ($36) has no smpsNoAttack -> no held notes (bit 7 never set).
        for ch in transcode_sfx_source(SKID_SRC, 0x36)['channels']:
            for e in ch['events']:
                if isinstance(e, NoteDur):
                    self.assertFalse(e.pitch & 0x80, "skid notes must all attack")


# A PSG tone channel that switches to noise via smpsPSGform must be played on the
# NOISE channel (not as an audible tone) — the dash $B6's release "pshhh".
PSGFORM_SRC = """\
Sound_FF_Header:
\tsmpsHeaderStartSong 3
\tsmpsHeaderVoice     Sound_FF_Voices
\tsmpsHeaderTempoSFX  $01
\tsmpsHeaderChanSFX   $01

\tsmpsHeaderSFXChannel cPSG3, Sound_FF_PSG3,\t$00, $00

Sound_FF_PSG3:
\tsmpsPSGvoice        sTone_1D
\tdc.b\tnRst, $06
\tsmpsModSet          $01, $02, $05, $FF
\tsmpsPSGform         $E7
\tdc.b\tnE6, $4F
\tsmpsStop

Sound_FF_Voices:
"""


class TestPsgFormNoise(unittest.TestCase):
    """A cPSG3 channel with smpsPSGform (noise mode) must be rerouted to the NOISE
    channel so it plays as noise, not an audible descending tone (the dash "duh")."""

    def setUp(self):
        from song_packer import CHROUTE_PSGN
        self.CHROUTE_PSGN = CHROUTE_PSGN
        self.ch = transcode_sfx_source(PSGFORM_SRC, 0xFF)['channels'][0]

    def test_rerouted_to_noise(self):
        self.assertEqual(self.ch['route'], self.CHROUTE_PSGN,
                         "smpsPSGform channel must route to PSGN (noise), not PSG3 (tone)")
        self.assertEqual(self.ch['kind'], SFXEL_NOISE)

    def test_note_is_noise_mode_not_tone(self):
        # the engine reads NoteDur pitch low-3 as the SN76489 noise mode; bit 2 set =
        # white noise. Tone modulation must be dropped (no ModSet on a noise channel).
        from song_packer import ModSet
        nd = [e for e in self.ch['events'] if isinstance(e, NoteDur)]
        self.assertEqual(len(nd), 1)
        self.assertEqual(nd[0].pitch & 0x04, 0x04, "noise note must select WHITE noise")
        self.assertEqual([e for e in self.ch['events'] if isinstance(e, ModSet)], [],
                         "noise channel has no tone freq -> modSet must be dropped")


class TestRepeatBodyBackstop(unittest.TestCase):
    """A REPEAT_START..REPEAT_END span with no time-advancing event would collapse in
    one Z80 frame; the SFX packer must reject it."""

    def test_empty_repeat_body_rejected(self):
        events = [Vol(80), RepeatStart(), Vol(60), RepeatEnd(8), End()]
        with self.assertRaises(TranscodeError):
            _validate_sfx_repeat(events, 0x99)

    def test_repeat_body_with_note_accepted(self):
        events = [Vol(80), RepeatStart(), NoteDur(0x46, 1), RepeatEnd(8), End()]
        _validate_sfx_repeat(events, 0x99)   # must not raise

    def test_skid_keeps_compact_repeat(self):
        # Skid ($36) has no AlterVol, so its PSG loop must STAY a compact
        # RepeatStart/End (a real note inside) — NOT unrolled.
        chans = transcode_sfx_source(SKID_SRC, 0x36)['channels']
        psg2 = chans[0]['events']
        self.assertTrue(any(isinstance(e, RepeatStart) for e in psg2),
                        "skid's note-bearing loop should stay a compact repeat")


if __name__ == '__main__':
    unittest.main()
