# tools/test_smps_import.py
from smps_import import tokenize_line, NOTE_BYTES, PAN_BYTES, DAC_IDS, FLAG_BYTES, resolve_const, HCZ2_DAC_REMAP
from suite_paths import suite_path

# The S3K donor these tests read. Resolved from the suite root, never baked: a wrong
# literal here would make every row below open nothing.
_HCZ2 = str(suite_path("skdisasm", "Sound", "Music", "HCZ2.asm"))

def test_tokenize_macro_with_args():
    assert tokenize_line("\tsmpsHeaderFM\tSnd_HCZ2_FM1, $18, $0F  ; comment") == \
        ("smpsHeaderFM", ["Snd_HCZ2_FM1", "$18", "$0F"], None)

def test_tokenize_label():
    assert tokenize_line("Snd_HCZ2_FM1:") == (None, [], "Snd_HCZ2_FM1")

def test_tokenize_dc_b():
    assert tokenize_line("\tdc.b\tdKickS3, $06") == ("dc.b", ["dKickS3", "$06"], None)

def test_tokenize_blank_and_comment():
    assert tokenize_line("   ; only a comment") == (None, [], None)
    assert tokenize_line("") == (None, [], None)

def test_note_name_to_byte():
    assert NOTE_BYTES["nC0"] == 0x81
    assert NOTE_BYTES["nCs0"] == 0x82
    assert NOTE_BYTES["nC1"] == 0x8D     # +12

def test_pan_consts():
    assert PAN_BYTES["panLeft"] == 0x80
    assert PAN_BYTES["panRight"] == 0x40
    assert PAN_BYTES["panCenter"] == 0xC0

def test_dac_ids():           # driver-v3 enum, _smps2asm_inc.asm:96-113
    assert DAC_IDS["dSnareS3"] == 0x81
    assert DAC_IDS["dKickS3"] == 0x86
    assert DAC_IDS["dHighTom"] == 0x82

def test_resolve_const_numeric():
    assert resolve_const("$18") == 0x18
    assert resolve_const("6") == 6
    assert resolve_const("dKickS3") == 0x86

# ── Task 1.1 ─────────────────────────────────────────────────────────────────

from smps_import import parse_header, SongConfig

HCZ2_HEADER = """
Snd_HCZ2_Header:
\tsmpsHeaderStartSong 3
\tsmpsHeaderVoiceUVB
\tsmpsHeaderChan      $06, $03
\tsmpsHeaderTempo     $01, $25
\tsmpsHeaderDAC       Snd_HCZ2_DAC
\tsmpsHeaderFM        Snd_HCZ2_FM1, $18, $0F
\tsmpsHeaderFM        Snd_HCZ2_FM2, $18, $0A
\tsmpsHeaderFM        Snd_HCZ2_FM3, $18, $13
\tsmpsHeaderFM        Snd_HCZ2_FM4, $0C, $0F
\tsmpsHeaderFM        Snd_HCZ2_FM5, $0C, $0C
\tsmpsHeaderPSG       Snd_HCZ2_PSG1, $F4, $04, $00, sTone_0C
\tsmpsHeaderPSG       Snd_HCZ2_PSG2, $F4, $04, $00, sTone_0C
\tsmpsHeaderPSG       Snd_HCZ2_PSG3, $00, $03, $00, sTone_0C
""".strip().splitlines()

def test_parse_header():
    cfg = parse_header(HCZ2_HEADER)
    assert cfg.divider == 0x01
    assert cfg.tempo_mod == 0x25      # raw S3K TempoWait addend (pass-through)
    assert [c.label for c in cfg.channels] == [
        "Snd_HCZ2_DAC","Snd_HCZ2_FM1","Snd_HCZ2_FM2","Snd_HCZ2_FM3",
        "Snd_HCZ2_FM4","Snd_HCZ2_FM5","Snd_HCZ2_PSG1","Snd_HCZ2_PSG2","Snd_HCZ2_PSG3"]
    fm1 = next(c for c in cfg.channels if c.label == "Snd_HCZ2_FM1")
    # FIX 2: the 3rd smpsHeaderFM arg is the channel VOLUME, not a voice
    # (smpsHeaderFM loc,pitch,vol — _smps2asm_inc.asm:332).
    assert fm1.kind == "FM" and fm1.volume == 0x0F and fm1.transpose == 0x18
    psg1 = next(c for c in cfg.channels if c.label == "Snd_HCZ2_PSG1")
    # smpsHeaderPSG loc,pitch,vol,mod,voice: volume=$04, psg_voice=sTone_0C=$0C.
    assert psg1.kind == "PSG" and psg1.volume == 0x04 and psg1.psg_voice == 0x0C
    dac = cfg.channels[0]
    assert dac.kind == "DAC"

# ── Tempo pass-through correctness (H.4) ─────────────────────────────────────
# The engine now runs S3K's EXACT TempoWait model (accum += mod/frame; a carry
# frame skips the event-tick -> rate = (256 - mod)/256), so the SMPS header mod
# byte is a RAW pass-through — no conversion, no quantization. The old
# `cfg.tempo_base` property (round(4096/(256-mod)) for the retired 16/N reload
# model) is gone: it could only approximate SMPS rates (HCZ2 -1.42%).

def test_tempo_mod_is_raw_passthrough():
    cfg = SongConfig(); cfg.tempo_mod = 0x25
    assert cfg.tempo_mod == 0x25
    assert not hasattr(SongConfig(), "tempo_base")  # conversion property deleted

def test_tempo_mod_hcz2_header_byte_is_25():
    # HCZ2's smpsHeaderTempo $01, $25 must land in the packed header at +2
    # UNCHANGED ($25 -> event-tick rate 219/256 = 0.85547/frame, S3K-exact).
    from song_packer import SongDesc, ChannelDesc, CHROUTE_FM1, pack_song
    from song_packer import Patch, Vol, SetDur, Note, End
    cfg = parse_header(HCZ2_HEADER)
    song = SongDesc(tempo=0x80, tempo_mod=cfg.tempo_mod, channels=[
        ChannelDesc(CHROUTE_FM1, [Patch(0), Vol(100), SetDur(8), Note(10), End()])])
    blob = pack_song(song)
    assert blob[2] == 0x25

# ── Task 1.2 ─────────────────────────────────────────────────────────────────

from smps_import import split_blocks

def test_split_blocks():
    src = ["Snd_HCZ2_FM1:", "\tsmpsSetvoice $0F", "\tdc.b nC4, $0C",
           "Snd_HCZ2_FM2:", "\tdc.b nG3"]
    blocks = split_blocks(src)
    assert list(blocks.keys()) == ["Snd_HCZ2_FM1", "Snd_HCZ2_FM2"]
    assert blocks["Snd_HCZ2_FM1"] == ["\tsmpsSetvoice $0F", "\tdc.b nC4, $0C"]

# ── Finding #1: enharmonic note names ────────────────────────────────────────
# All flat/enharmonic aliases from _smps2asm_inc.asm lines 32-47:
#   Db=Cs, Eb=Ds, Fb=E, F=Es (Es is next after E so nF=nEs), Gb=Fs, Ab=Gs, Bb=As
#   Cb(N)=B(N-1), Bs(N)=C(N+1)
# nMaxPSG1=nBb6=nAs6=$D3, nMaxPSG2=nB6=$D4 (SonicDriverVer>=3, lines 58-59)
# nRst=$80 (line 31)

def test_enharmonic_flat_aliases():
    # Eb = Ds (one semitone above D)
    assert NOTE_BYTES["nEb3"] == NOTE_BYTES["nDs3"]
    assert NOTE_BYTES["nEb4"] == NOTE_BYTES["nDs4"]
    assert NOTE_BYTES["nBb3"] == NOTE_BYTES["nAs3"]
    assert NOTE_BYTES["nBb4"] == NOTE_BYTES["nAs4"]
    assert NOTE_BYTES["nBb5"] == NOTE_BYTES["nAs5"]
    assert NOTE_BYTES["nDb4"] == NOTE_BYTES["nCs4"]
    assert NOTE_BYTES["nGb5"] == NOTE_BYTES["nFs5"]
    assert NOTE_BYTES["nAb4"] == NOTE_BYTES["nGs4"]
    # Check full octave coverage for a few flats
    for oct in range(8):
        assert NOTE_BYTES["nEb%d" % oct] == NOTE_BYTES["nDs%d" % oct]
        assert NOTE_BYTES["nBb%d" % oct] == NOTE_BYTES["nAs%d" % oct]
        assert NOTE_BYTES["nGb%d" % oct] == NOTE_BYTES["nFs%d" % oct]
        assert NOTE_BYTES["nAb%d" % oct] == NOTE_BYTES["nGs%d" % oct]
        assert NOTE_BYTES["nDb%d" % oct] == NOTE_BYTES["nCs%d" % oct]
        assert NOTE_BYTES["nFb%d" % oct] == NOTE_BYTES["nE%d" % oct]

def test_enharmonic_sharp_aliases():
    # Es=F, Bs(N)=C(N+1), Cb(N)=B(N-1)
    for oct in range(8):
        assert NOTE_BYTES["nEs%d" % oct] == NOTE_BYTES["nF%d" % oct]
    for oct in range(7):          # Bs0=C1 ... Bs6=C7
        assert NOTE_BYTES["nBs%d" % oct] == NOTE_BYTES["nC%d" % (oct+1)]
    for oct in range(1, 8):       # Cb1=B0 ... Cb7=B6
        assert NOTE_BYTES["nCb%d" % oct] == NOTE_BYTES["nB%d" % (oct-1)]

def test_nRst():
    # nRst=$80 — _smps2asm_inc.asm line 31
    assert resolve_const("nRst") == 0x80

def test_nMaxPSG():
    # SonicDriverVer>=3: nMaxPSG1=nBb6=$D3, nMaxPSG2=nB6=$D4
    # _smps2asm_inc.asm lines 58-59
    assert resolve_const("nMaxPSG1") == 0xD3
    assert resolve_const("nMaxPSG2") == 0xD4

# ── Finding #2: coordination-flag mnemonics inline in dc.b ───────────────────
# Exact values from _smps2asm_inc.asm:
#   smpsNoAttack EQU $E7  (line 457)

def test_flag_bytes_smpsNoAttack():
    # _smps2asm_inc.asm line 457: smpsNoAttack EQU $E7
    assert FLAG_BYTES["smpsNoAttack"] == 0xE7

def test_resolve_const_flag():
    assert resolve_const("smpsNoAttack") == FLAG_BYTES["smpsNoAttack"]
    assert resolve_const("smpsNoAttack") == 0xE7

# ── Finding #3: split_blocks / tokenize_line style note ──────────────────────
# (No code assertion — comment added in source. Verified by convention check in docstring.)

# ── Finding #4: parse_header bounds guard ────────────────────────────────────

import pytest

def test_parse_header_fm_too_few_args():
    lines = ["\tsmpsHeaderFM\tSnd_HCZ2_FM1, $18"]  # missing vol arg
    with pytest.raises(ValueError, match="smpsHeaderFM"):
        parse_header(lines)

def test_parse_header_psg_too_few_args():
    lines = ["\tsmpsHeaderPSG\tSnd_HCZ2_PSG1, $F4"]  # missing vol arg
    with pytest.raises(ValueError, match="smpsHeaderPSG"):
        parse_header(lines)

def test_parse_header_tempo_too_few_args():
    lines = ["\tsmpsHeaderTempo\t$01"]  # missing mod arg
    with pytest.raises(ValueError, match="smpsHeaderTempo"):
        parse_header(lines)

# ── Integration: resolve_const covers ALL real HCZ2 n*/smps* dc.b tokens ─────

import re as _re

def test_hcz2_dcb_symbol_coverage():
    """
    Read the real HCZ2.asm, extract every dc.b/dc.w arg that looks like a
    note (n...) or flag (smps...) token, and assert resolve_const does NOT
    raise for any of them.
    Skips: raw numbers ($xx / decimal), labels (Snd_*), sTone_* voice names.
    """
    hcz2_path = _HCZ2
    with open(hcz2_path) as f:
        lines = f.readlines()

    failures = []
    for lineno, line in enumerate(lines, 1):
        code = line.split(";", 1)[0]
        mnem_match = _re.match(r"^\s+(\S+)\s", code)
        if not mnem_match:
            continue
        mnem = mnem_match.group(1)
        if mnem not in ("dc.b", "dc.w"):
            continue
        args_str = code[mnem_match.end():]
        for arg in args_str.split(","):
            tok = arg.strip()
            # Only resolve n* and smps* tokens — skip hex, decimal, labels, sTone_*
            if not (_re.match(r"^n[A-Za-z]", tok) or tok.startswith("smps")):
                continue
            try:
                resolve_const(tok)
            except KeyError:
                failures.append("line %d: %r" % (lineno, tok))

    assert not failures, "resolve_const failed on: " + ", ".join(failures)

# ── Task 2.1 ─ notes / rests / durations (CORRECTED note-first model) ─────────

from smps_import import convert_channel, ConvState
from song_packer import Note, Rest, SetDur, NoteDur

def _cfg(divider=1):
    c = SongConfig(); c.divider = divider; return c

def test_note_with_trailing_duration():
    ev = convert_channel("FM", ["\tdc.b nC4, $0C", "\tdc.b $80"], {}, _cfg(), ConvState())
    # nC4 = $B1 -> index 0x30; dur 0x0C
    assert isinstance(ev[0], SetDur) and ev[0].ticks == 0x0C
    assert isinstance(ev[1], Note) and ev[1].pitch == 0x30
    assert isinstance(ev[-1], Rest)

def test_bare_note_reuses_saved_dur():
    ev = convert_channel("FM", ["\tdc.b nC4, $0C, nE4"], {}, _cfg(), ConvState())
    notes = [e for e in ev if isinstance(e, (Note, NoteDur))]
    assert len(notes) == 2 and notes[1].pitch == 0x34   # nE4=$B5 -> 0x34, reuses dur 0x0C (no new SetDur)

def test_transpose_folds():
    ev = convert_channel("FM", ["\tdc.b nC4, $0C"], {}, _cfg(), ConvState(transpose=2))
    assert any(isinstance(e, Note) and e.pitch == 0x32 for e in ev)

def test_duration_times_divider_overflow_uses_notedur():
    ev = convert_channel("FM", ["\tdc.b nC4, $40"], {}, _cfg(divider=2), ConvState())  # 0x40*2=0x80>0x7F
    assert any(isinstance(e, NoteDur) and e.dur == 0x80 for e in ev)

def test_leading_bare_duration_sets_saved_dur():
    # FIX 1: a standalone bare-duration byte ($0C, not consumed as a trailing
    # dur) must set the SMPS SavedDuration so following bare notes reuse it.
    # Before the fix, _saved_dur stayed 0 and the notes got dur 0.
    ev = convert_channel("FM", ["\tdc.b $0C, nC4, nE4"], {}, _cfg(), ConvState())
    notes = [e for e in ev if isinstance(e, (Note, NoteDur))]
    assert len(notes) == 2
    # The first note must carry a SetDur of 0x0C (not 0), and both notes reuse it.
    set_durs = [e for e in ev if isinstance(e, SetDur)]
    assert len(set_durs) == 1 and set_durs[0].ticks == 0x0C
    # nC4=$B1 -> 0x30, nE4=$B5 -> 0x34, both plain Notes at the 0x0C default.
    assert all(isinstance(n, Note) for n in notes)
    assert [n.pitch for n in notes] == [0x30, 0x34]

# ── Task 2.2 ─ coordination-flag -> MEV mapping + DAC route ──────────────────

from song_packer import Pan, Patch, ModSet, End, Dac, Detune

def test_detune_emits_event():
    # smpsDetune/smpsAlterNote (cfDetune) now emit a Detune event (was dropped in v1).
    ev = convert_channel("FM", ["\tsmpsDetune $08", "\tsmpsStop"], {}, _cfg(), ConvState())
    assert isinstance(ev[0], Detune) and ev[0].detune == 8
    # a large operand clamps to +-0x3F (keeps the FM single-step block correction valid)
    ev2 = convert_channel("PSG", ["\tsmpsAlterNote $7F", "\tsmpsStop"], {}, _cfg(), ConvState())
    assert isinstance(ev2[0], Detune) and ev2[0].detune == 0x3F

def test_detune_clamp_warns(capfd):
    # An out-of-range detune must both clamp AND warn (silent truncation hid an
    # audible pitch change).
    ev = convert_channel("FM", ["\tsmpsDetune $70", "\tsmpsStop"], {}, _cfg(), ConvState())
    assert isinstance(ev[0], Detune) and ev[0].detune == 0x3F
    assert "clamped" in capfd.readouterr().err
    # In-range detune must NOT warn.
    convert_channel("FM", ["\tsmpsDetune $08", "\tsmpsStop"], {}, _cfg(), ConvState())
    assert "clamped" not in capfd.readouterr().err

def test_unknown_smpsvc_macro_raises():
    # Unknown smpsVc* sub-macros raise (coord-flag policy) — a silent skip
    # would zero part of the voice.
    from smps_import import smps_voice_to_fmpatch
    bogus = list(_UVB_VOICE_03) + [("smpsVcBogus", ["01h"])]
    with pytest.raises(Exception, match="smpsVcBogus"):
        smps_voice_to_fmpatch(bogus)

def test_flags_map():
    ev = convert_channel("FM", ["\tsmpsPan panLeft, $00","\tsmpsSetvoice $0F","\tsmpsModSet $01,$02,$03,$04","\tsmpsStop"], {}, _cfg(), ConvState())
    assert isinstance(ev[0],Pan) and ev[0].b4==0x80
    assert isinstance(ev[1],Patch) and ev[1].patch==0x0F
    assert isinstance(ev[2],ModSet) and (ev[2].wait,ev[2].speed,ev[2].change,ev[2].step)==(1,2,3,4)
    assert isinstance(ev[3],End)

def test_pan_folds_amsfms_arg():
    # smpsPan macro is `dc.b $E0, direction+amsfms` — the 2nd arg (AMS/FMS bits
    # 5-4/2-0) rides the SAME $B4 operand byte and must be folded in.
    ev = convert_channel("FM", ["\tsmpsPan panLeft, $37", "\tsmpsStop"],
                         {}, _cfg(), ConvState())
    assert isinstance(ev[0], Pan) and ev[0].b4 == (0x80 | 0x37)

def test_dac_samples_and_pan_dropped():
    ev = convert_channel("DAC", ["\tdc.b dKickS3, $06","\tsmpsPan panLeft, $00","\tdc.b dSnareS3, $06"], {}, _cfg(), ConvState())
    ids = [e.sample_id for e in ev if isinstance(e,Dac)]
    assert ids == [0x86 & 0x7F, 0x81 & 0x7F]
    assert not any(isinstance(e,Pan) for e in ev)

def test_inline_smpsnoattack_does_not_break_walk():
    # nMaxPSG1 $06, then smpsNoAttack + a standalone $06 (a TIE: sustain the held
    # note +6 ticks, no re-attack), then nC4. The inline $E7 must not be a note,
    # and the $06 after it must ADVANCE TIME by extending the held note.
    ev = convert_channel("PSG", ["\tdc.b nMaxPSG1, $06, smpsNoAttack, $06, nC4"], {}, _cfg(), ConvState())
    notes = [e for e in ev if isinstance(e, (Note, NoteDur))]
    assert len(notes) == 2
    # held note extended to 6+6=12 (the tie); nC4 then re-attacks at the reused dur
    assert isinstance(notes[0], NoteDur) and notes[0].dur == 0x0C
    assert isinstance(notes[1], Note)

# ── Task 2.3 ─ structural control flow + per-channel state ───────────────────

from song_packer import LoopPoint, Jump, Vol, PsgEnv

def test_call_inlines_body():
    # smpsCall recursively converts the target block's tokens (stopping at
    # smpsReturn) with the SAME ConvState, splices them inline.
    blocks = {"Sub0": ["\tsmpsSetvoice $05", "\tsmpsReturn"]}
    ev = convert_channel("FM", ["\tsmpsCall Sub0", "\tdc.b nC4, $0C"],
                         blocks, _cfg(), ConvState())
    assert isinstance(ev[0], Patch) and ev[0].patch == 0x05
    assert any(isinstance(e, Note) for e in ev)

def test_loop_unrolls():
    # smpsLoop replays its body (target label .. loop flag) `count` times.
    blocks = {"LoopA": ["\tdc.b nC4, $0C", "\tsmpsLoop $00, $03, LoopA"]}
    ev = convert_channel("FM", [], blocks, _cfg(), ConvState(),
                         start_label="LoopA")
    notes = [e for e in ev if isinstance(e, Note)]
    assert len(notes) == 3        # body (1 note) unrolled x3

def test_loop_nested_unrolls():
    # Nested loops, structured the way split_blocks actually emits them (one
    # block per label). The OUTER loop targets the block that contains the INNER
    # loop, so the outer body = [Outer .. outer smpsLoop), which spans Outer ->
    # Inner via fall-through and includes the inner loop.
    #   Outer: 1 note, then fall through to Inner.
    #   Inner: 1 note + smpsLoop x2 (inner body = that 1 note, replayed once).
    #   After Inner's loop: smpsLoop x3 back to Outer (outer body replayed twice).
    # Per outer pass: Outer note (1) + Inner note unrolled x2 (2) = 3 notes.
    # Outer x3 -> 9 notes.
    blocks = {
        "Outer": ["\tdc.b nC4, $0C"],
        "Inner": ["\tdc.b nC4, $0C", "\tsmpsLoop $01, $02, Inner",
                  "\tsmpsLoop $00, $03, Outer"],
    }
    ev = convert_channel("FM", [], blocks, _cfg(), ConvState(),
                         start_label="Outer")
    notes = [e for e in ev if isinstance(e, Note)]
    assert len(notes) == 9

def test_psg_voice_maps_to_imported_env():
    # sTone_0C is an imported engine envelope -> PsgEnv(0x0C), not the old PsgEnv(0).
    ev = convert_channel("PSG", ["\tsmpsPSGvoice sTone_0C", "\tdc.b nC4, $0C"],
                         {}, _cfg(), ConvState())
    assert any(isinstance(e, PsgEnv) and e.env_id == 0x0C for e in ev)

def test_psg_voice_emits_envelope_id():
    # sTone_08 (HCZ2 hi-hat) -> PsgEnv(8).
    ev = convert_channel("PSG", ["\tsmpsPSGvoice sTone_08", "\tdc.b nC4, $0C"],
                         {}, _cfg(), ConvState())
    envs = [e for e in ev if isinstance(e, PsgEnv)]
    assert len(envs) == 1 and envs[0].env_id == 0x08

def test_psg_voice_unknown_env_falls_back_to_zero():
    # An sTone with no imported engine envelope warns + emits PsgEnv(0) (safe).
    ev = convert_channel("PSG", ["\tsmpsPSGvoice sTone_19", "\tdc.b nC4, $0C"],
                         {}, _cfg(), ConvState())
    envs = [e for e in ev if isinstance(e, PsgEnv)]
    assert len(envs) == 1 and envs[0].env_id == 0

def test_jump_loopback_terminates():
    # A channel that jumps back to an earlier label in its own data emits a
    # LoopPoint (at the target) + a Jump (at the smpsJump) and stops.
    blocks = {"Main": ["Lp:", "\tdc.b nC4, $0C", "\tsmpsJump Lp"],
              "Lp":   ["\tdc.b nC4, $0C", "\tsmpsJump Lp"]}
    ev = convert_channel("FM", [], blocks, _cfg(), ConvState(),
                         start_label="Main")
    assert any(isinstance(e, LoopPoint) for e in ev)
    assert isinstance(ev[-1], Jump)
    # nothing emitted after the Jump (terminal)
    assert sum(isinstance(e, Jump) for e in ev) == 1

def test_setnote_sets_transpose():
    # smpsSetNote val -> transpose = val - $40 ; note pitch reflects it.
    ev = convert_channel("FM", ["\tsmpsSetNote $42", "\tdc.b nC4, $0C"],
                         {}, _cfg(), ConvState())
    # nC4=$B1 -> base index 0x30; transpose = 0x42-0x40 = +2 -> 0x32
    assert any(isinstance(e, Note) and e.pitch == 0x32 for e in ev)

def test_change_transposition_adds():
    ev = convert_channel("FM", ["\tsmpsChangeTransposition $02", "\tdc.b nC4, $0C"],
                         {}, _cfg(), ConvState(transpose=1))
    # base 0x30 + (1 + 2) = 0x33
    assert any(isinstance(e, Note) and e.pitch == 0x33 for e in ev)

def test_alter_vol_folds_fm():
    # smpsAlterVol on FM: running volume +/- delta in S3K attenuation space,
    # mapped to v0 loudness via LogVolumeLutZ inverse.
    # Use smpsSetVol $7F (operand=0x7F -> atten=0 -> loudest, v0=127) followed
    # by smpsAlterVol $10 (delta=+16 in atten space -> atten=16 -> v0=70).
    # These produce two distinct Vol events (127 and 70).
    ev = convert_channel("FM",
                         ["\tsmpsSetVol $7F", "\tsmpsAlterVol $10"],
                         {}, _cfg(), ConvState())
    vols = [e for e in ev if isinstance(e, Vol)]
    assert len(vols) == 2 and vols[-1].vol != vols[0].vol
    # First Vol: operand $7F -> atten=0 -> v0=127 (loudest)
    assert vols[0].vol == 127
    # Second Vol: atten=16 -> v0=_fm_atten_to_v0(16)
    from smps_import import _fm_atten_to_v0
    assert vols[1].vol == _fm_atten_to_v0(16)

def test_call_depth_guard():
    # Self-recursive call must error rather than blow the stack.
    blocks = {"R": ["\tsmpsCall R"]}
    raised = False
    try:
        convert_channel("FM", [], blocks, _cfg(), ConvState(), start_label="R")
    except Exception:
        raised = True
    assert raised

# PRINTED-NOT-GATED (2026-09-25): a jump/call/loop to a label the block map does not
# hold used to warn and return "fell_off", which no caller read, so the channel was
# silently truncated at that point and the song still packed. It is now REFUSED,
# naming the label, the flag that referenced it, the block it sits in and its line.
# Instrumented against every converted song at 633b5936 (HCZ2, and S2 EHZ/CPZ with
# probe tables): none reached this branch, so the refusal changes no shipped byte.
@pytest.mark.parametrize("flag_line,mnem", [
    ("\tsmpsCall Nowhere_Sub", "smpsCall"),
    ("\tsmpsJump Nowhere_Sub", "smpsJump"),
    ("\tsmpsLoop $00, $02, Nowhere_Sub", "smpsLoop"),
])
def test_unknown_label_is_refused_not_truncated(flag_line, mnem):
    blocks = {"Main": ["\tdc.b nC4, $0C", flag_line, "\tdc.b nD4, $0C", "\tsmpsStop"]}
    with pytest.raises(ValueError) as ei:
        convert_channel("FM", [], blocks, _cfg(), ConvState(), start_label="Main")
    msg = str(ei.value)
    assert "Nowhere_Sub" in msg and mnem in msg and "'Main'" in msg
    assert flag_line.strip() in msg          # the source line, verbatim


# PRINTED-NOT-GATED residue (2026-09-26): a raw coordination-flag byte written
# inline as dc.b (anything >= $E0 but smpsNoAttack) used to be warned and dropped,
# and its parameter bytes then walked as notes. It is now REFUSED by name. HCZ2,
# S2 EHZ and S2 CPZ were instrumented first and reach this branch zero times.
@pytest.mark.parametrize("raw", ["$E0", "$F2", "$FB"])
def test_inline_raw_flag_byte_is_refused(raw):
    line = "\tdc.b nC4, $0C, %s, $01, nD4, $0C" % raw
    with pytest.raises(ValueError) as ei:
        convert_channel("FM", [], {"Main": [line, "\tsmpsStop"]}, _cfg(),
                        ConvState(), start_label="Main")
    msg = str(ei.value)
    assert ("$%s" % raw[1:]) in msg and "'Main'" in msg and line.strip() in msg


def test_inline_noattack_byte_still_ties():
    ev = convert_channel("FM", ["\tdc.b nC4, $0C, $E7, nC4, $0C"], {}, _cfg(),
                         ConvState())
    notes = [e for e in ev if isinstance(e, (Note, NoteDur))]
    assert len(notes) == 1 and isinstance(notes[0], NoteDur)


def test_unknown_start_label_is_refused():
    with pytest.raises(ValueError, match="Missing_Hdr"):
        convert_channel("FM", [], {"Main": ["\tsmpsStop"]}, _cfg(), ConvState(),
                        start_label="Missing_Hdr")

# ── Task 2.3 end-to-end: real HCZ2 FM + DAC convert without raising ──────────

def _hcz2_blocks_and_cfg():
    path = _HCZ2
    with open(path) as f:
        lines = f.read().splitlines()
    cfg = parse_header(lines)
    blocks = split_blocks(lines)
    return blocks, cfg

def test_e2e_hcz2_dac_converts():
    blocks, cfg = _hcz2_blocks_and_cfg()
    ev = convert_channel("DAC", [], blocks, cfg, ConvState(),
                         start_label="Snd_HCZ2_DAC")
    assert ev, "DAC channel produced no events"
    assert isinstance(ev[-1], (Jump, End))
    assert any(isinstance(e, Dac) for e in ev)

def test_e2e_hcz2_fm1_converts():
    blocks, cfg = _hcz2_blocks_and_cfg()
    fm1 = next(c for c in cfg.channels if c.label == "Snd_HCZ2_FM1")
    ev = convert_channel("FM", [], blocks, cfg,
                         ConvState(transpose=fm1.transpose),
                         start_label="Snd_HCZ2_FM1")
    assert ev, "FM1 channel produced no events"
    assert isinstance(ev[-1], (Jump, End))
    assert any(isinstance(e, Note) for e in ev)

def test_e2e_hcz2_psg3_converts():
    # PSG3 has the densest control flow: nested smpsLoop + many smpsPSGvoice +
    # inline smpsNoAttack + a final smpsJump.
    blocks, cfg = _hcz2_blocks_and_cfg()
    ev = convert_channel("PSG", [], blocks, cfg, ConvState(),
                         start_label="Snd_HCZ2_PSG3")
    assert ev
    assert isinstance(ev[-1], (Jump, End))
    assert any(isinstance(e, PsgEnv) for e in ev)

# ── Task 2.4 ─ smpsNoAttack tie merge ────────────────────────────────────────

def test_same_pitch_tie_merges():
    # nC4 dur $0C, then smpsNoAttack (tie), then same nC4 dur $0C.
    # Same pitch -> merge into one NoteDur(pitch, $18).
    ev = convert_channel("FM", ["\tdc.b nC4, $0C", "\tsmpsNoAttack", "\tdc.b nC4, $0C"], {}, _cfg(), ConvState())
    notes = [e for e in ev if isinstance(e, (Note, NoteDur))]
    assert len(notes) == 1                               # merged into one
    assert isinstance(notes[0], NoteDur) and notes[0].dur == 0x18   # 0x0C + 0x0C

def test_pitch_change_slur_reattacks():
    # nC4 then smpsNoAttack then nE4 — different pitch, accepted v1 gap: re-attacks.
    ev = convert_channel("FM", ["\tdc.b nC4, $0C", "\tsmpsNoAttack", "\tdc.b nE4, $0C"], {}, _cfg(), ConvState())
    notes = [e for e in ev if isinstance(e, (Note, NoteDur))]
    assert len(notes) == 2                               # slur re-attacks (v1 gap)

def test_inline_noattack_merges():
    # smpsNoAttack inline in a dc.b arg list ($E7) also triggers the tie.
    # "nC4, $06, smpsNoAttack, nC4, $06" -> 1 merged note dur=$0C.
    ev = convert_channel("PSG", ["\tdc.b nC4, $06, smpsNoAttack, nC4, $06"], {}, _cfg(), ConvState())
    notes = [e for e in ev if isinstance(e, (Note, NoteDur))]
    assert len(notes) == 1 and notes[0].dur == 0x0C

def test_tie_merge_does_not_update_default_dur():
    # After a merge, the running default-dur (SetDur) must not change.
    # Sequence: nC4 $0C (sets default=12), smpsNoAttack, nC4 $0C (merges, no new SetDur),
    # then nE4 (no dur arg -> reuses saved dur $0C, no extra SetDur needed).
    ev = convert_channel("FM",
                         ["\tdc.b nC4, $0C", "\tsmpsNoAttack", "\tdc.b nC4, $0C, nE4"],
                         {}, _cfg(), ConvState())
    # nE4 should be a plain Note (not NoteDur) with SetDur already matching 0x0C.
    notes = [e for e in ev if isinstance(e, (Note, NoteDur))]
    # notes[0] = merged NoteDur(nC4, 0x18); notes[1] = Note(nE4)
    assert len(notes) == 2
    assert isinstance(notes[1], Note)     # plain Note, not NoteDur
    # Only one SetDur should appear (the initial one from nC4 $0C).
    set_durs = [e for e in ev if isinstance(e, SetDur)]
    assert len(set_durs) == 1 and set_durs[0].ticks == 0x0C

def test_tie_cleared_on_rest():
    # A Rest between tie-flag and next note must clear the tie (no merge).
    ev = convert_channel("FM",
                         ["\tdc.b nC4, $0C", "\tsmpsNoAttack", "\tdc.b $80, $06, nC4, $0C"],
                         {}, _cfg(), ConvState())
    notes = [e for e in ev if isinstance(e, (Note, NoteDur))]
    # tie is cleared by the rest, so two separate notes
    assert len(notes) == 2

def test_e2e_psg3_tie_merge_reduces_note_count():
    # PSG3 has many smpsNoAttack inline ties on the same pitch.
    # Converting WITH merge should produce fewer note events than without.
    blocks, cfg = _hcz2_blocks_and_cfg()
    ev_with = convert_channel("PSG", [], blocks, cfg, ConvState(),
                              start_label="Snd_HCZ2_PSG3")
    note_count_with = sum(1 for e in ev_with if isinstance(e, (Note, NoteDur)))
    # No errors and terminator present.
    assert ev_with
    assert isinstance(ev_with[-1], (Jump, End))
    # Without merge: count notes before this feature was added would be higher.
    # We verify by checking that at least some NoteDur events exist (proof merge fired).
    merged = [e for e in ev_with if isinstance(e, NoteDur)]
    assert len(merged) > 0, "Expected at least one tie-merged NoteDur in PSG3"

# ── Task 3.1 ─ convert_song -> packable SongDesc ─────────────────────────────

from smps_import import convert_song
from song_packer import (SongDesc, ChannelDesc, pack_song, CHROUTE_FM1,
                         CHROUTE_FM2, CHROUTE_FM3, CHROUTE_FM4, CHROUTE_FM5,
                         CHROUTE_PSG1, CHROUTE_PSG2, CHROUTE_PSG3, CHROUTE_DAC,
                         SH_F_STREAM)

def test_convert_song_packs():
    src = HCZ2_HEADER + [
        "Snd_HCZ2_DAC:", "\tdc.b dKickS3, $06", "\tsmpsStop",
        "Snd_HCZ2_FM1:", "\tsmpsSetvoice $0F", "\tdc.b nC4, $0C", "\tsmpsStop",
        "Snd_HCZ2_FM2:", "\tsmpsStop", "Snd_HCZ2_FM3:", "\tsmpsStop",
        "Snd_HCZ2_FM4:", "\tsmpsStop", "Snd_HCZ2_FM5:", "\tsmpsStop",
        "Snd_HCZ2_PSG1:", "\tsmpsStop", "Snd_HCZ2_PSG2:", "\tsmpsStop", "Snd_HCZ2_PSG3:", "\tsmpsStop",
    ]
    song = convert_song(src, dac_remap={6:2,1:3,2:4,3:5,4:6,5:7}, patch_remap={0x0F:0})
    assert isinstance(song, SongDesc) and (song.flags & SH_F_STREAM)
    routes = [c.route for c in song.channels]
    assert CHROUTE_FM1 in routes and CHROUTE_DAC in routes
    pack_song(song)   # MUST NOT raise

def test_convert_song_route_assignment_and_tempo():
    # DAC -> CHROUTE_DAC; FM in order -> FM1..FM5; PSG in order -> PSG1..3.
    src = HCZ2_HEADER + [
        "Snd_HCZ2_DAC:", "\tsmpsStop",
        "Snd_HCZ2_FM1:", "\tsmpsSetvoice $0F", "\tdc.b nC4, $0C", "\tsmpsStop",
        "Snd_HCZ2_FM2:", "\tsmpsStop", "Snd_HCZ2_FM3:", "\tsmpsStop",
        "Snd_HCZ2_FM4:", "\tsmpsStop", "Snd_HCZ2_FM5:", "\tsmpsStop",
        "Snd_HCZ2_PSG1:", "\tsmpsStop", "Snd_HCZ2_PSG2:", "\tsmpsStop", "Snd_HCZ2_PSG3:", "\tsmpsStop",
    ]
    song = convert_song(src, dac_remap={6:2,1:3,2:4,3:5,4:6,5:7}, patch_remap={0x0F:0})
    routes = [c.route for c in song.channels]
    assert routes == [CHROUTE_DAC, CHROUTE_FM1, CHROUTE_FM2, CHROUTE_FM3,
                      CHROUTE_FM4, CHROUTE_FM5, CHROUTE_PSG1, CHROUTE_PSG2, CHROUTE_PSG3]
    assert song.tempo == 0x80
    assert song.tempo_mod == 0x25     # raw SMPS mod pass-through (S3K-exact model)

def test_convert_song_prepends_vol_and_patch():
    from song_packer import Vol, Patch, Note
    src = HCZ2_HEADER + [
        "Snd_HCZ2_DAC:", "\tsmpsStop",
        "Snd_HCZ2_FM1:", "\tsmpsSetvoice $0F", "\tdc.b nC4, $0C", "\tsmpsStop",
        "Snd_HCZ2_FM2:", "\tsmpsStop", "Snd_HCZ2_FM3:", "\tsmpsStop",
        "Snd_HCZ2_FM4:", "\tsmpsStop", "Snd_HCZ2_FM5:", "\tsmpsStop",
        "Snd_HCZ2_PSG1:", "\tsmpsStop", "Snd_HCZ2_PSG2:", "\tsmpsStop", "Snd_HCZ2_PSG3:", "\tsmpsStop",
    ]
    song = convert_song(src, dac_remap={6:2,1:3,2:4,3:5,4:6,5:7}, patch_remap={0x0F:0})
    fm1 = next(c for c in song.channels if c.route == CHROUTE_FM1)
    # A Vol must precede the first Note; a Patch (remapped 0x0F->0) must too.
    first_note = next(i for i, e in enumerate(fm1.events) if isinstance(e, Note))
    assert any(isinstance(e, Vol) for e in fm1.events[:first_note])
    patches = [e for e in fm1.events[:first_note] if isinstance(e, Patch)]
    assert patches and patches[0].patch == 0   # remapped 0x0F -> 0

def test_convert_song_unmapped_patch_raises():
    src = HCZ2_HEADER + [
        "Snd_HCZ2_DAC:", "\tsmpsStop",
        "Snd_HCZ2_FM1:", "\tsmpsSetvoice $0F", "\tdc.b nC4, $0C", "\tsmpsStop",
        "Snd_HCZ2_FM2:", "\tsmpsStop", "Snd_HCZ2_FM3:", "\tsmpsStop",
        "Snd_HCZ2_FM4:", "\tsmpsStop", "Snd_HCZ2_FM5:", "\tsmpsStop",
        "Snd_HCZ2_PSG1:", "\tsmpsStop", "Snd_HCZ2_PSG2:", "\tsmpsStop", "Snd_HCZ2_PSG3:", "\tsmpsStop",
    ]
    with pytest.raises(Exception, match=r"\$0F|patch_remap"):
        convert_song(src, dac_remap={6:2,1:3,2:4,3:5,4:6,5:7}, patch_remap={})

def test_convert_song_unmapped_dac_raises():
    src = HCZ2_HEADER + [
        "Snd_HCZ2_DAC:", "\tdc.b dKickS3, $06", "\tsmpsStop",
        "Snd_HCZ2_FM1:", "\tsmpsSetvoice $0F", "\tdc.b nC4, $0C", "\tsmpsStop",
        "Snd_HCZ2_FM2:", "\tsmpsStop", "Snd_HCZ2_FM3:", "\tsmpsStop",
        "Snd_HCZ2_FM4:", "\tsmpsStop", "Snd_HCZ2_FM5:", "\tsmpsStop",
        "Snd_HCZ2_PSG1:", "\tsmpsStop", "Snd_HCZ2_PSG2:", "\tsmpsStop", "Snd_HCZ2_PSG3:", "\tsmpsStop",
    ]
    with pytest.raises(Exception, match="6|unmapped"):
        convert_song(src, dac_remap={}, patch_remap={0x0F:0})

def test_convert_song_real_hcz2_packs():
    # END-TO-END: read REAL HCZ2.asm, build remaps covering every drum + voice,
    # convert, and prove the whole song packs.
    path = _HCZ2
    with open(path) as f:
        src = f.read().splitlines()
    # The 6 S3K drum ids HCZ2 uses (raw, 1-based): dSnareS3=1, dHighTom=2,
    # dMidTomS3=3, dLowTomS3=4, dFloorTomS3=5, dKickS3=6 (DAC_IDS & 0x7F).
    dac_remap = {1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6}
    # Scan the source for every distinct in-body smpsSetvoice id, map each to a
    # 0-based index.
    voice_ids = sorted({int(m.group(1), 16) for m in
        (_re.match(r"\s*smpsSetvoice\s+\$([0-9A-Fa-f]+)", ln) for ln in src) if m})
    patch_remap = {vid: i for i, vid in enumerate(voice_ids)}
    song = convert_song(src, dac_remap=dac_remap, patch_remap=patch_remap)
    assert isinstance(song, SongDesc)
    assert len(song.channels) == 9     # DAC + 5 FM + 3 PSG
    pack_song(song)                    # MUST NOT raise — whole song converts + packs

# ── Phase 4 ─ UVB voice import (S3K Universal Voice Bank -> FmPatch) ──────────

from smps_import import (smps_voice_to_fmpatch, parse_uvb_voices,
                         build_patch_remap, emit_patch_table,
                         HCZ2_USED_VOICE_IDS)
from zyrinx_port import FMPATCH_LEN

# Voice $03 (Synth Bass 1) from the S3K UVB, in (macro, [args]) form. The driver
# writes suffix-hex (`04h`); smps_voice_to_fmpatch normalizes it.
_UVB_VOICE_03 = [
    ("smpsVcAlgorithm",   ["04h"]),
    ("smpsVcFeedback",    ["06h"]),
    ("smpsVcUnusedBits",  ["00h"]),
    ("smpsVcDetune",      ["03h", "03h", "07h", "07h"]),
    ("smpsVcCoarseFreq",  ["01h", "01h", "02h", "00h"]),
    ("smpsVcRateScale",   ["00h", "00h", "00h", "00h"]),
    ("smpsVcAttackRate",  ["1Fh", "1Fh", "1Fh", "1Fh"]),
    ("smpsVcAmpMod",      ["00h", "00h", "00h", "00h"]),
    ("smpsVcDecayRate1",  ["06h", "06h", "06h", "10h"]),
    ("smpsVcDecayRate2",  ["06h", "06h", "06h", "01h"]),
    ("smpsVcDecayLevel",  ["01h", "01h", "01h", "03h"]),
    ("smpsVcReleaseRate", ["0Ah", "05h", "0Ah", "05h"]),
    ("smpsVcTotalLevel",  ["83h", "18h", "83h", "10h"]),
]

# ── Task 4.1 ─ smps_voice_to_fmpatch ─────────────────────────────────────────

def test_smps_voice_to_fmpatch_len():
    assert len(smps_voice_to_fmpatch(_UVB_VOICE_03)) == FMPATCH_LEN

def test_smps_voice_to_fmpatch_alg_fb():
    # fp_alg_fb = algo | (fb << 3); voice $03 is algo 4, fb 6 -> $34
    # (matches the driver's own "; 34h" $B0-write comment for Voice 03h).
    p = smps_voice_to_fmpatch(_UVB_VOICE_03)
    assert p[0] == (0x04 | (0x06 << 3)) == 0x34

def test_smps_voice_to_fmpatch_op_reorder():
    # _s3k_op_reorder: [op1,op2,op3,op4] -> [op4,op2,op3,op1]. The dt_mul macro
    # args combine detune<<4|coarse: [$31,$31,$72,$70] -> reordered [$70,$31,$72,$31].
    p = smps_voice_to_fmpatch(_UVB_VOICE_03)
    assert list(p[2:6]) == [0x70, 0x31, 0x72, 0x31]   # fp_dt_mul ($30) group

def test_smps_voice_to_fmpatch_tl_verbatim():
    # smpsVcTotalLevel is already YM attenuation -> stored verbatim (tl_is_level
    # False), op-reordered. TL args [$83,$18,$83,$10] -> [$10,$18,$83,$83] masked $7F.
    p = smps_voice_to_fmpatch(_UVB_VOICE_03)
    assert list(p[6:10]) == [0x10, 0x18, 0x03, 0x03]   # fp_tl ($40), 0x83&0x7F=0x03

def test_smps_voice_to_fmpatch_default_pan():
    # fp_lr_ams_fms defaults to $C0 (both L/R on) — _SmpsVoiceBuilder seeds it.
    p = smps_voice_to_fmpatch(_UVB_VOICE_03)
    assert p[1] == 0xC0

def test_smps_voice_to_fmpatch_deterministic():
    assert smps_voice_to_fmpatch(_UVB_VOICE_03) == smps_voice_to_fmpatch(_UVB_VOICE_03)

def test_smps_voice_to_fmpatch_missing_tl_raises():
    with pytest.raises(Exception):
        smps_voice_to_fmpatch(_UVB_VOICE_03[:-1])   # drop smpsVcTotalLevel

# ── Task 4.2 ─ parse_uvb_voices + emit_patch_table ───────────────────────────

def test_build_patch_remap():
    # HCZ2 ids $03,$06,$0E,$15 -> dense {3:0, 6:1, 14:2, 21:3}.
    assert build_patch_remap() == {0x03: 0, 0x06: 1, 0x0E: 2, 0x15: 3}

def test_parse_uvb_voices_returns_four_patches():
    voices = parse_uvb_voices()
    assert set(voices.keys()) == set(HCZ2_USED_VOICE_IDS)
    for vid, p in voices.items():
        assert len(p) == FMPATCH_LEN, "voice $%02X must be %d bytes" % (vid, FMPATCH_LEN)

def test_parse_uvb_voice_03_matches_known():
    # Voice $03 parsed from the real driver must equal the hand-built block.
    voices = parse_uvb_voices()
    assert voices[0x03] == smps_voice_to_fmpatch(_UVB_VOICE_03)

def test_parse_uvb_voices_algo_feedback_real_instruments():
    # Sanity: the 4 voices' algo/feedback look like real instruments.
    # Voice $03 Synth Bass 1 (alg4,fb6=$34); $06 Synth Brass 1 (alg2,fb7=$3A);
    # $0E Elec Piano (alg2,fb7=$3A); $15 Picked Bass (alg0,fb5=$28).
    voices = parse_uvb_voices()
    assert voices[0x03][0] == (4 | (6 << 3))   # $34
    assert voices[0x06][0] == (2 | (7 << 3))   # $3A
    assert voices[0x0E][0] == (2 | (7 << 3))   # $3A
    assert voices[0x15][0] == (0 | (5 << 3))   # $28

def test_emit_patch_table_remap():
    asm, remap = emit_patch_table()
    assert remap == {0x03: 0, 0x06: 1, 0x0E: 2, 0x15: 3}

def test_emit_patch_table_four_rows():
    asm, _ = emit_patch_table()
    assert "HCZ2_Patches:" in asm
    assert "HCZ2_Patches_End:" in asm
    rows = [ln for ln in asm.splitlines() if ln.strip().startswith("dc.b")]
    assert len(rows) == 4
    # Each row must encode exactly FMPATCH_LEN bytes.
    for row in rows:
        body = row.split(";", 1)[0]
        nbytes = body.count("$")
        assert nbytes == FMPATCH_LEN, "row has %d bytes, expected %d: %r" % (nbytes, FMPATCH_LEN, row)

def test_emit_patch_table_size_assert_present():
    asm, _ = emit_patch_table()
    assert "FmPatch_len" in asm and "4*FmPatch_len" in asm

def test_emit_patch_table_deterministic():
    a1, r1 = emit_patch_table()
    a2, r2 = emit_patch_table()
    assert a1 == a2 and r1 == r2

def test_emit_patch_table_rows_in_remap_order():
    # Row i must comment the S3K id whose remap index is i.
    asm, remap = emit_patch_table()
    idx_to_id = {i: vid for vid, i in remap.items()}
    rows = [ln for ln in asm.splitlines() if ln.strip().startswith("dc.b")]
    for i, row in enumerate(rows):
        assert ("S3K voice $%02X" % idx_to_id[i]) in row

def test_hcz2_dac_remap_covers_exactly_the_six_drums():
    # HCZ2 uses exactly 6 DAC ids ($81..$86 = 1-based 1..6). Dac() carries the
    # 1-based id (b & 0x7F), so the remap keys must be exactly {1,2,3,4,5,6}.
    hcz2_one_based = {raw & 0x7F for raw in DAC_IDS.values()}
    assert hcz2_one_based == {1, 2, 3, 4, 5, 6}
    assert set(HCZ2_DAC_REMAP.keys()) == hcz2_one_based
    # Maps to the 6 distinct v0 DacSampleTable ids assigned in Phase 5.
    assert set(HCZ2_DAC_REMAP.values()) == {5, 6, 7, 8, 9, 10}
    # Spot-check the documented assignment.
    assert HCZ2_DAC_REMAP[6] == 5   # dKickS3   -> s3k_kick
    assert HCZ2_DAC_REMAP[1] == 6   # dSnareS3  -> s3k_snare
    assert HCZ2_DAC_REMAP[2] == 7   # dHighTom  -> s3k_hitom
    assert HCZ2_DAC_REMAP[5] == 10  # dFloorTomS3 -> s3k_floortom

# ── BUG 1 ─ header initial volume is a TL ATTENUATION (invert), not loudness ──
# The S3K song-header `vol` byte (smpsHeaderFM/PSG 3rd arg) is copied DIRECTLY
# into zTrack.Volume at track init (Z80 Sound Driver.asm:1876-1878 ldir), and
# zTrack.Volume is the carrier-TL ATTENUATION (0=loudest, 127=silent). v0 Vol is
# LOUDNESS (127=loud), so the header vol must be INVERTED. This is distinct from
# the mid-song smpsSetVol OPERAND, which cfSetVolume xor $7F's into loudness
# (driver:3128) and stays _smps_vol_to_v0.

from smps_import import _smps_header_vol_to_v0, _fm_atten_to_v0, _LOG_VOLUME_LUT

# ── LogVolumeLutZ inverse sanity ─────────────────────────────────────────────

def test_log_volume_lut_parsed():
    # The table is parsed from engine/sound/sound_tables_z80.emp; verify invariants.
    assert len(_LOG_VOLUME_LUT) >= 128, "LUT must have at least 128 entries"
    # First 128 entries must be non-increasing (monotone decreasing for loudness index).
    for i in range(127):
        assert _LOG_VOLUME_LUT[i] >= _LOG_VOLUME_LUT[i + 1], \
            "LUT not monotone at index %d: LUT[%d]=%d > LUT[%d]=%d" % (
                i, i, _LOG_VOLUME_LUT[i], i+1, _LOG_VOLUME_LUT[i+1])
    # Boundary invariants: LUT[0] = 0x7F (max TL delta = near-silent at v0=0);
    # last nonzero should be near index 124.
    assert _LOG_VOLUME_LUT[0] == 0x7F

def test_fm_atten_to_v0_loudest():
    # atten=0 (no carrier-TL delta) -> loudest v0 index = 127
    assert _fm_atten_to_v0(0) == 127

def test_fm_atten_to_v0_silent():
    # atten=0x7F -> v0 near 0 (max-atten; LUT[0]=LUT[1]=0x7F, tie -> larger V=1)
    assert _fm_atten_to_v0(0x7F) in (0, 1)   # both produce max-atten TL delta

def test_fm_atten_to_v0_known_value():
    # atten=15 (0x0F) -> compute from LUT: find V minimising |LUT[V]-15|.
    # The exact value is determined by the parsed table (not hardcoded).
    v = _fm_atten_to_v0(15)
    assert abs(_LOG_VOLUME_LUT[v] - 15) <= 1, \
        "_fm_atten_to_v0(15)=%d -> LUT[%d]=%d not near 15" % (v, v, _LOG_VOLUME_LUT[v])
    # Sanity: must be in the usable loudness range
    assert 60 <= v <= 85, "_fm_atten_to_v0(15) out of expected range: %d" % v

def test_header_vol_fm_uses_lut_inverse():
    # FM header vol is a 7-bit TL attenuation; mapped to v0 via LogVolumeLutZ inverse.
    # Values are computed from the actual parsed table, NOT linear 127-x.
    assert _smps_header_vol_to_v0("FM", 0x00) == 127   # 0 attn -> loudest v0 index
    assert _smps_header_vol_to_v0("FM", 0x0F) == _fm_atten_to_v0(0x0F)   # FM1 HCZ2
    assert _smps_header_vol_to_v0("FM", 0x0A) == _fm_atten_to_v0(0x0A)   # FM2 HCZ2
    assert _smps_header_vol_to_v0("FM", 0x13) == _fm_atten_to_v0(0x13)   # FM3 HCZ2
    assert _smps_header_vol_to_v0("FM", 0x0C) == _fm_atten_to_v0(0x0C)   # FM5 HCZ2
    # All HCZ2 FM header vols fall in the ~62-88 range (moderate attenuation -> loud)
    for atten in (0x0F, 0x0A, 0x13, 0x0C):
        v = _smps_header_vol_to_v0("FM", atten)
        assert 55 <= v <= 95, \
            "_smps_header_vol_to_v0(FM, 0x%02X)=%d not in expected range 55-95" % (atten, v)

def test_header_vol_psg_is_raw_attenuation():
    # PSG header vol is the 4-bit SN76489 attenuation copied DIRECTLY into
    # zTrack.Volume at track init (no operand decode) -> invert to loudness.
    # DISTINCT from the mid-song smpsSetVol OPERAND, which cfSetVolume decodes
    # as inverted bits 3-6 (see test_smps_vol_to_v0_psg_bits36_inverted).
    assert _smps_header_vol_to_v0("PSG", 0x04) == 93   # round((15-4)/15*127)
    assert _smps_header_vol_to_v0("PSG", 0x00) == 127  # atten 0 = loudest
    assert _smps_header_vol_to_v0("PSG", 0x0F) == 0    # atten 15 = silent

def test_smps_vol_to_v0_psg_bits36_inverted():
    # S3K cfSetVolume PSG path (driver ~:3113-3126): `srl a` x3, `xor 0Fh`,
    # `and 0Fh` — attenuation = INVERTED bits 3-6 of the operand ($78 = max
    # volume, $08 = min). The low nibble is DISCARDED, not the attenuation.
    from smps_import import _smps_vol_to_v0
    assert _smps_vol_to_v0("PSG", 0x78) == 127         # $78 -> atten 0 -> max vol
    assert _smps_vol_to_v0("PSG", 0x08) == 8           # $08 -> atten 14 -> quietest audible
    assert _smps_vol_to_v0("PSG", 0x00) == 0           # $00 -> atten 15 -> silent
    # Mid value: $40 -> (0x40>>3)=8, ^0xF=7 -> atten 7 -> round(8/15*127)=68
    assert _smps_vol_to_v0("PSG", 0x40) == 68
    # Low 3 bits are discarded: $78 and $7F decode identically.
    assert _smps_vol_to_v0("PSG", 0x7F) == _smps_vol_to_v0("PSG", 0x78)

def test_psg_alter_vol_composes_with_decoded_setvol():
    # smpsSetVol $78 seeds the DECODED attenuation (0); smpsPSGAlterVol +4 then
    # composes in zTrack.Volume space (cfChangePSGVolume adds the delta to the
    # decoded value): atten 0+4=4 -> v0 93.
    ev = convert_channel("PSG",
        ["\tsmpsSetVol $78", "\tsmpsPSGAlterVol $04", "\tsmpsStop"],
        {}, _cfg(), ConvState())
    vols = [e.vol for e in ev if isinstance(e, Vol)]
    assert vols == [127, 93]

def test_smps_vol_to_v0_fm_path_uses_lut_inverse():
    # Mid-song smpsSetVol FM path: cfSetVolume xors the operand with $7F before
    # storing as TL attenuation, so effective atten = operand ^ 0x7F.
    # _smps_vol_to_v0("FM", operand) must equal _fm_atten_to_v0(operand ^ 0x7F).
    from smps_import import _smps_vol_to_v0
    assert _smps_vol_to_v0("FM", 0x0F) == _fm_atten_to_v0(0x0F ^ 0x7F)
    assert _smps_vol_to_v0("FM", 0x40) == _fm_atten_to_v0(0x40 ^ 0x7F)
    # operand=0 -> atten=0x7F (max-atten/silent); operand=0x7F -> atten=0 (loudest)
    assert _smps_vol_to_v0("FM", 0x7F) == 127   # max-loud operand -> loudest

def test_convert_song_fm_header_vol_in_correct_range():
    # END-TO-END: real HCZ2 FM channels must get header Vols in the ~62-88 range
    # (LogVolumeLutZ inverse of S3K TL attenuations 0x0A..0x13), which places FM
    # volume correctly in the log domain so drums are not buried.
    from song_packer import Vol, Note, NoteDur
    path = _HCZ2
    with open(path) as f:
        src = f.read().splitlines()
    dac_remap = {1: 6, 2: 7, 3: 8, 4: 9, 5: 10, 6: 5}
    patch_remap = {0x03: 0, 0x06: 1, 0x0E: 2, 0x15: 3}
    song = convert_song(src, dac_remap=dac_remap, patch_remap=patch_remap)
    fm_routes = {CHROUTE_FM1, CHROUTE_FM2, CHROUTE_FM3, CHROUTE_FM4, CHROUTE_FM5}
    # Expected header vols from HCZ2 header attenuation values, via LUT inverse:
    #   FM1 atten=$0F -> v0=_fm_atten_to_v0(0x0F); FM2 $0A; FM3 $13; FM4 $0F; FM5 $0C
    expected_vols = {
        CHROUTE_FM1: _fm_atten_to_v0(0x0F),   # $0F = 15
        CHROUTE_FM2: _fm_atten_to_v0(0x0A),   # $0A = 10
        CHROUTE_FM3: _fm_atten_to_v0(0x13),   # $13 = 19
        CHROUTE_FM4: _fm_atten_to_v0(0x0F),   # $0F = 15
        CHROUTE_FM5: _fm_atten_to_v0(0x0C),   # $0C = 12
    }
    for ch in song.channels:
        if ch.route not in fm_routes:
            continue
        fti = next((i for i, e in enumerate(ch.events)
                    if isinstance(e, (Note, NoteDur))), len(ch.events))
        head_vols = [e.vol for e in ch.events[:fti] if isinstance(e, Vol)]
        assert head_vols, "FM route %d has no header Vol" % ch.route
        exp = expected_vols[ch.route]
        assert head_vols[0] == exp, \
            "FM route %d header Vol %d != expected %d (LUT inverse of S3K atten)" % (
                ch.route, head_vols[0], exp)
        # All expected values are in the 55-95 range (moderate TL attenuation -> loud)
        assert 55 <= head_vols[0] <= 95, \
            "FM route %d header Vol %d outside expected 55-95 range" % (ch.route, head_vols[0])

# ── BUG 2 ─ the PSG noise channel routes to CHROUTE_PSGN as noise hits ────────
# HCZ2's PSG3 is the noise/hi-hat channel: smpsPSGform $E7 (white-noise control)
# then nMaxPSG1 "notes" as the rhythm. It must route to CHROUTE_PSGN and emit
# noise hits whose engine control reproduces $E7 (pitch & 7 == 7 = white noise),
# NOT a tone PSG playing a single fixed high pitch. PSG1/PSG2 stay tone routes.

from song_packer import CHROUTE_PSGN

def test_convert_song_psg_noise_channel_routed_to_psgn():
    from song_packer import Note, NoteDur
    path = _HCZ2
    with open(path) as f:
        src = f.read().splitlines()
    dac_remap = {1: 6, 2: 7, 3: 8, 4: 9, 5: 10, 6: 5}
    patch_remap = {0x03: 0, 0x06: 1, 0x0E: 2, 0x15: 3}
    song = convert_song(src, dac_remap=dac_remap, patch_remap=patch_remap)
    routes = [c.route for c in song.channels]
    # Exactly one PSGN route (the noise channel).
    assert routes.count(CHROUTE_PSGN) == 1, "expected exactly one PSGN route"
    # PSG1 and PSG2 remain tone routes (in order), PSG3 is gone (-> PSGN).
    assert CHROUTE_PSG1 in routes and CHROUTE_PSG2 in routes
    assert CHROUTE_PSG3 not in routes
    from song_packer import PsgNoise
    noise = next(c for c in song.channels if c.route == CHROUTE_PSGN)
    # The noise channel sets its mode via MEV_PSGNOISE ($E7 = white, rate-3) ...
    pn = [e for e in noise.events if isinstance(e, PsgNoise)]
    assert pn and pn[0].ctrl == 0xE7, "noise channel must emit PsgNoise($E7)"
    # ... and its hits carry the REAL pitch (nMaxPSG1 = index 82) so the engine clocks
    # tone-ch2 from it (rate-3), NOT the old mode bits.
    notes = [e for e in noise.events if isinstance(e, (Note, NoteDur))]
    assert len(notes) > 1, "noise channel must have >1 hit"
    assert any(n.pitch == (0xD3 - 0x81) for n in notes), "noise hits must carry real pitch"

def test_convert_song_psg_tone_channels_keep_melody():
    from song_packer import Note, NoteDur
    path = _HCZ2
    with open(path) as f:
        src = f.read().splitlines()
    dac_remap = {1: 6, 2: 7, 3: 8, 4: 9, 5: 10, 6: 5}
    patch_remap = {0x03: 0, 0x06: 1, 0x0E: 2, 0x15: 3}
    song = convert_song(src, dac_remap=dac_remap, patch_remap=patch_remap)
    for route in (CHROUTE_PSG1, CHROUTE_PSG2):
        ch = next(c for c in song.channels if c.route == route)
        notes = [e for e in ch.events if isinstance(e, (Note, NoteDur))]
        pitches = {n.pitch for n in notes}
        # Tone PSGs carry the melody: many distinct pitches, NOT a single stuck note.
        assert len(pitches) > 5, \
            "tone PSG route %d should be melodic (got %d distinct pitches)" % (route, len(pitches))

def test_smpspsgform_emits_psgnoise():
    # smpsPSGform $E7 -> PsgNoise($E7) (the SN76489 control byte), NOT a noise_pitch fold.
    from song_packer import PsgNoise
    ev = convert_channel("PSG",
        ["\tsmpsPSGform $E7", "\tdc.b nMaxPSG1, $06"],
        {}, _cfg(), ConvState(), noise=True)
    pn = [e for e in ev if isinstance(e, PsgNoise)]
    assert len(pn) == 1 and pn[0].ctrl == 0xE7

def test_noise_note_carries_real_pitch():
    # The noise note keeps its REAL pitch (nMaxPSG1 -> index 82) so the engine can clock
    # tone-2 (rate-3), NOT the old mode bits ($E7 & 7 = 7).
    from song_packer import Note, NoteDur
    ev = convert_channel("PSG",
        ["\tsmpsPSGform $E7", "\tdc.b nMaxPSG1, $06, nMaxPSG1, $06"],
        {}, _cfg(), ConvState(), noise=True)
    notes = [e for e in ev if isinstance(e, (Note, NoteDur))]
    assert notes, "noise channel produced no hits"
    for n in notes:
        assert n.pitch == (0xD3 - 0x81)   # nMaxPSG1 = $D3 -> index 82 (real pitch)

def test_convert_song_real_hcz2_packs_with_psgn():
    # The whole HCZ2 song still packs end-to-end with the noise channel on PSGN.
    path = _HCZ2
    with open(path) as f:
        src = f.read().splitlines()
    dac_remap = {1: 6, 2: 7, 3: 8, 4: 9, 5: 10, 6: 5}
    patch_remap = {0x03: 0, 0x06: 1, 0x0E: 2, 0x15: 3}
    song = convert_song(src, dac_remap=dac_remap, patch_remap=patch_remap)
    assert len(song.channels) == 9
    pack_song(song)   # MUST NOT raise

# ── Standalone duration is TIME-ADVANCING (drums-off-beat root-cause fix) ─────
# A SMPS duration byte read in NOTE POSITION (not a note's trailing dur) is
# time-advancing in the S3K driver (zStoreDuration->zFinishTrackUpdate sets
# DurationTimeout, holding/sustaining the current note). The converter used to
# drop it (zero-tick "set default"), shortening the DAC + PSG-noise loops so the
# percussion drifted off-beat. These pin the corrected semantics.

def _loop_body_ticks(events):
    """Sum the v0 tick duration of a channel's looped body (LoopPoint..Jump),
    mirroring the engine: SetDur sets the running default (0 tick); Note/Rest
    advance the default; NoteDur advances its explicit dur; Dac/coord = 0 tick."""
    from song_packer import (Note, Rest, SetDur, NoteDur, LoopPoint, Jump, End)
    cur = 0; body = 0; in_loop = False
    for ev in events:
        if isinstance(ev, LoopPoint): in_loop = True; continue
        if isinstance(ev, (Jump, End)): continue
        if isinstance(ev, SetDur): cur = ev.ticks; continue
        if isinstance(ev, NoteDur): t = ev.dur
        elif isinstance(ev, (Note, Rest)): t = cur
        else: t = 0
        if in_loop: body += t
    return body

def test_hcz2_all_channels_equal_loop_period():
    # The decisive regression: every HCZ2 channel must loop at the SAME tick
    # period (2688). Before the standalone-dur fix the DAC (2546) and PSG-noise
    # (2100) channels looped short and drifted ahead of the melody.
    path = _HCZ2
    with open(path) as f:
        src = f.read().splitlines()
    dac_remap = {1: 6, 2: 7, 3: 8, 4: 9, 5: 10, 6: 5}
    patch_remap = {0x03: 0, 0x06: 1, 0x0E: 2, 0x15: 3}
    song = convert_song(src, dac_remap=dac_remap, patch_remap=patch_remap)
    periods = [_loop_body_ticks(c.events) for c in song.channels]
    assert len(set(periods)) == 1, \
        "channels drift: per-channel loop periods differ: %r" % periods
    assert periods[0] == 2688, "expected 2688-tick loop, got %d" % periods[0]

def test_standalone_dur_after_note_extends_it_fm():
    # nC4 $0C then a standalone $18 (e.g. after smpsNoAttack): the note SUSTAINS
    # for 0x0C + 0x18 = 0x24 ticks (no re-attack), not a dropped zero-tick byte.
    ev = convert_channel("FM",
        ["\tdc.b nC4, $0C, smpsNoAttack, $18"], {}, _cfg(), ConvState())
    notes = [e for e in ev if isinstance(e, (Note, NoteDur))]
    assert len(notes) == 1
    assert isinstance(notes[0], NoteDur) and notes[0].dur == 0x24

def test_standalone_dur_in_dac_advances_time():
    # DAC: dKick $0C then standalone $06, $0C -> each bare byte RE-TRIGGERS the
    # saved kick (zUpdateDACTrack_cont) AND advances time. Total DAC ticks must
    # be 0x0C + 0x06 + 0x0C = 0x1E.
    from song_packer import Dac, Rest, SetDur, NoteDur, Note
    ev = convert_channel("DAC",
        ["\tdc.b dKickS3, $0C, $06, $0C"], {}, _cfg(), ConvState())
    cur = 0; total = 0
    for e in ev:
        if isinstance(e, SetDur): cur = e.ticks
        elif isinstance(e, NoteDur): total += e.dur
        elif isinstance(e, (Note, Rest)): total += cur
    assert total == 0x1E, "DAC standalone durs dropped: total=%d" % total
    # 1 initial trigger + 2 bare-duration re-triggers.
    assert sum(1 for e in ev if isinstance(e, Dac)) == 3

# ── DAC bare duration = drum RE-TRIGGER (S3K zUpdateDACTrack_cont) ────────────
# A $00-$7F byte in NOTE position on the DAC track makes the driver back up,
# re-read zTrack.SavedDAC and QUEUE IT AGAIN (a fresh drum hit) with that byte
# as the new duration — unless SavedDAC is the $80 rest. HCZ2's accelerating
# snare rolls and its 9-hit tom fill are written this way.

def _dac_total_ticks(ev):
    from song_packer import Rest, SetDur, NoteDur, Note
    cur = 0; total = 0
    for e in ev:
        if isinstance(e, SetDur): cur = e.ticks
        elif isinstance(e, NoteDur): total += e.dur
        elif isinstance(e, (Note, Rest)): total += cur
    return total

def test_dac_bare_duration_retriggers_saved_sample():
    # HCZ2 snare-roll idiom: dSnareS3 $18, then a bare $0C, then a bare
    # $02, $04, $06 run — every bare byte re-fires the snare at that pacing.
    ev = convert_channel("DAC",
        ["\tdc.b dSnareS3, $18, $0C", "\tdc.b $02, $04, $06"],
        {}, _cfg(), ConvState())
    dacs = [e for e in ev if isinstance(e, Dac)]
    assert len(dacs) == 5, "expected 1 trigger + 4 re-triggers, got %d" % len(dacs)
    assert all(d.sample_id == (0x81 & 0x7F) for d in dacs)   # all snare
    # Pacing preserved exactly: $18+$0C+$02+$04+$06 = $30 ticks.
    assert _dac_total_ticks(ev) == 0x30

# ── Duration overflow: split exactly, never clamp/drop time ──────────────────

def test_long_rest_splits_exact_total():
    # divider=2 forces a rest > $7F: $80 rest with trailing $7F -> 254 ticks.
    # Must split into SetDur/Rest chunks summing EXACTLY (old code clamped to
    # one $7F rest, dropping 127 ticks and drifting the channel).
    ev = convert_channel("FM", ["\tdc.b $80, $7F"], {}, _cfg(divider=2), ConvState())
    assert _dac_total_ticks(ev) == 0x7F * 2
    assert all(isinstance(e, (SetDur, Rest)) for e in ev)

def test_long_rest_split_uneven_remainder():
    # $41 * divider 2 = 130 = 127 + 3: two Rest chunks with distinct SetDurs.
    ev = convert_channel("FM", ["\tdc.b $80, $41"], {}, _cfg(divider=2), ConvState())
    assert _dac_total_ticks(ev) == 130
    assert sum(1 for e in ev if isinstance(e, Rest)) == 2

def test_tie_merge_overflow_continues_instead_of_dropping():
    # Tie chain exceeding the NoteDur byte: nC4 $7F + smpsNoAttack nC4 $7F at
    # divider 2 = 254+254 = 508 ticks. The merge can't fit $FF, so the tie
    # continues as a second keyed segment — total time EXACT (old code clamped
    # at $FF, silently dropping 253 ticks).
    ev = convert_channel("FM",
        ["\tdc.b nC4, $7F", "\tsmpsNoAttack", "\tdc.b nC4, $7F"],
        {}, _cfg(divider=2), ConvState())
    notes = [e for e in ev if isinstance(e, (Note, NoteDur))]
    assert len(notes) == 2                      # continuation segment
    assert all(n.pitch == 0x30 for n in notes)
    assert _dac_total_ticks(ev) == 508

# ── FM/PSG bare standalone duration = RE-ATTACK unless smpsNoAttack ──────────
# S3K zGetNextNote clears the no-attack bit at entry and calls zKeyOffIfActive
# on EVERY non-flag byte; the caller then re-keys the held FreqLow/High via
# zFMSendFreq+zFMNoteOn. So a bare $00-$7F byte re-articulates the previous
# note; ONLY smpsNoAttack+dur is a tie. (sfx_transcode already did this.)

def test_standalone_dur_without_noattack_reattacks_fm():
    # nC4 $0C then a bare $18 with NO smpsNoAttack: two attacks, not a tie.
    ev = convert_channel("FM", ["\tdc.b nC4, $0C, $18"], {}, _cfg(), ConvState())
    notes = [e for e in ev if isinstance(e, (Note, NoteDur))]
    assert len(notes) == 2, "bare duration must re-attack (got %d notes)" % len(notes)
    assert all(n.pitch == 0x30 for n in notes)     # same pitch, re-keyed
    # Second articulation carries the bare byte's duration ($18).
    durs = [e.ticks for e in ev if isinstance(e, SetDur)]
    assert durs == [0x0C, 0x18]

def test_standalone_dur_with_noattack_still_ties():
    # The smpsNoAttack+dur pair remains a tie (single merged NoteDur) — the
    # companion path to the re-attack test above.
    ev = convert_channel("FM", ["\tdc.b nC4, $0C, smpsNoAttack, $18"],
                         {}, _cfg(), ConvState())
    notes = [e for e in ev if isinstance(e, (Note, NoteDur))]
    assert len(notes) == 1
    assert isinstance(notes[0], NoteDur) and notes[0].dur == 0x0C + 0x18

def test_standalone_dur_after_rest_replays_previous_note():
    # zRestTrack does NOT clear FreqLow/High, and zGetNextNote clears the rest
    # bit at entry — a bare duration after a rest re-keys the pre-rest pitch.
    ev = convert_channel("FM", ["\tdc.b nC4, $0C, $80, $0C, $18"],
                         {}, _cfg(), ConvState())
    notes = [e for e in ev if isinstance(e, (Note, NoteDur))]
    assert len(notes) == 2
    assert all(n.pitch == 0x30 for n in notes)
    rests = [e for e in ev if isinstance(e, Rest)]
    assert len(rests) == 1                          # the $80 rest

def test_noattack_then_dur_after_rest_stays_silent():
    # smpsNoAttack suppresses BOTH key-off and key-on; with nothing held (right
    # after a rest) the bare duration paces silence, not a ghost re-key.
    ev = convert_channel("FM",
        ["\tdc.b nC4, $0C, $80, $0C, smpsNoAttack, $18"], {}, _cfg(), ConvState())
    notes = [e for e in ev if isinstance(e, (Note, NoteDur))]
    assert len(notes) == 1                          # only the original nC4
    rests = [e for e in ev if isinstance(e, Rest)]
    assert len(rests) == 2                          # the $80 rest + the $18 pace


def test_dac_rest_clears_saved_sample_no_retrigger():
    # A DAC rest stores $80 into SavedDAC (zUpdateDACTrack_cont .got_sample), so
    # a bare duration AFTER a rest paces silence — no ghost re-trigger.
    ev = convert_channel("DAC",
        ["\tdc.b dKickS3, $0C, $80, $06, $0C"], {}, _cfg(), ConvState())
    dacs = [e for e in ev if isinstance(e, Dac)]
    assert len(dacs) == 1, "rest must clear SavedDAC (got %d triggers)" % len(dacs)
    assert _dac_total_ticks(ev) == 0x0C + 0x06 + 0x0C


def test_dac_pan_emits_b6_regwrite():
    """S3K DAC-track smpsPan (HCZ2 tom fills L/C/R) -> raw FM6 $B6 write."""
    from song_packer import RegWrite, PackError, CHROUTE_DAC
    import smps_import
    out = []
    smps_import._dispatch_flag("DAC", "smpsPan", ["panLeft", "$00"], None, out, None)
    assert len(out) == 1 and isinstance(out[0], RegWrite)
    assert (out[0].part, out[0].reg) == (1, 0xB6)
    assert out[0].val == 0x80  # panLeft
    out[0].validate(CHROUTE_DAC)  # packer accepts the narrow DAC-route door


def test_dac_route_regwrite_limited_to_b6():
    from song_packer import RegWrite, PackError, CHROUTE_DAC
    RegWrite(1, 0xB6, 0xC0).validate(CHROUTE_DAC)
    try:
        RegWrite(0, 0x28, 0xF0).validate(CHROUTE_DAC)
        assert False, "expected PackError"
    except PackError:
        pass


# ── S2CLIP-REGION-MUSIC step 1 ─ Sonic 2 SMPS source (SourceDriver 2) ──────────
#
# The rows below pin the S2 -> S3K conversions that s2disasm/sound/_smps2asm_inc.asm
# itself defines (the design pass, docs/research/2026-09-25-region-music-design.md
# Q1 rows a-h, found them by running the converter behind a throwaway pre-pass).
# The converter reads the source driver from the song's own `smpsHeaderStartSong`.
# New names are reached through the module (`_si.X`) rather than imported at the
# top, so a converter without the S2 mode fails each row on its own instead of the
# whole file failing at collection.

import os
import smps_import as _si
from song_packer import NoteFill

_S2_MUSIC = suite_path("s2disasm", "sound", "music")
_S2_EHZ = str(_S2_MUSIC / "82 - EHZ.asm")
_S2_CPZ = str(_S2_MUSIC / "8E - CPZ.asm")


def _s2_song(body_by_label, psg_voice="$00", start="2", tempo="$9E"):
    """A minimal, complete S2 song: header + the 9 channel blocks + one voice."""
    out = [
        "Tst_Header:",
        "\tsmpsHeaderStartSong %s" % start,
        "\tsmpsHeaderVoice     Tst_Voices",
        "\tsmpsHeaderChan      $06, $03",
        "\tsmpsHeaderTempo     $01, %s" % tempo,
        "\tsmpsHeaderDAC       Tst_DAC",
        "\tsmpsHeaderFM        Tst_FM1, $00, $0E",
        "\tsmpsHeaderFM        Tst_FM2, $00, $16",
        "\tsmpsHeaderFM        Tst_FM3, $00, $16",
        "\tsmpsHeaderFM        Tst_FM4, $00, $20",
        "\tsmpsHeaderFM        Tst_FM5, $00, $25",
        "\tsmpsHeaderPSG       Tst_PSG1, $DC, $04, $00, %s" % psg_voice,
        "\tsmpsHeaderPSG       Tst_PSG2, $DC, $04, $00, $00",
        "\tsmpsHeaderPSG       Tst_PSG3, $00, $02, $00, $00",
    ]
    for lbl in ("Tst_DAC", "Tst_FM1", "Tst_FM2", "Tst_FM3", "Tst_FM4", "Tst_FM5",
                "Tst_PSG1", "Tst_PSG2", "Tst_PSG3"):
        out.append(lbl + ":")
        out.extend(body_by_label.get(lbl, []))
        out.append("\tsmpsStop")
    out += [
        "Tst_Voices:",
        ";\tVoice $00",
        "\tsmpsVcAlgorithm     $07",
        "\tsmpsVcFeedback      $00",
        "\tsmpsVcUnusedBits    $00",
        "\tsmpsVcDetune        $00, $00, $00, $00",
        "\tsmpsVcCoarseFreq    $02, $01, $00, $05",
        "\tsmpsVcRateScale     $00, $00, $00, $00",
        "\tsmpsVcAttackRate    $1F, $1F, $1F, $1F",
        "\tsmpsVcAmpMod        $00, $00, $00, $00",
        "\tsmpsVcDecayRate1    $0E, $0E, $0E, $0E",
        "\tsmpsVcDecayRate2    $02, $02, $02, $02",
        "\tsmpsVcDecayLevel    $05, $05, $05, $05",
        "\tsmpsVcReleaseRate   $04, $05, $05, $05",
        "\tsmpsVcTotalLevel    $00, $00, $00, $00",
    ]
    return out


def _s2_cfg(divider=1, ftone_map=None):
    c = SongConfig(); c.divider = divider; c.source_driver = _si.SOURCE_S2
    c.ftone_map = {} if ftone_map is None else ftone_map
    return c


def _signed(v):
    v &= 0xFF
    return v - 256 if v >= 128 else v


# ---- (a) tempo: the S2 TempoWait model is inverted (silent tempo error) --------

def test_s2_tempo_is_inverted_to_s3k():
    # _smps2asm_inc.asm:184 s2TempotoS3(n) = ($100 - n) & $FF. EHZ $9E -> $62,
    # CPZ $EE -> $12. The S3K source path stays a raw pass-through ($25).
    assert parse_header(_s2_song({}, tempo="$9E")).tempo_mod == 0x62
    assert parse_header(_s2_song({}, tempo="$EE")).tempo_mod == 0x12
    assert parse_header(HCZ2_HEADER).tempo_mod == 0x25


def test_s2_tempo_zero_is_refused():
    # The include `fatal`s on an S2 main tempo of 0; so do we, by name.
    with pytest.raises(_si.S2Refusal, match="tempo"):
        parse_header(_s2_song({}, tempo="$00"))


# ---- (b) PSG header pitch is 12 semitones apart (silent octave error) -----------

def test_s2_psg_header_pitch_gets_psgdelta():
    # PSGPitchConvert (:224-231): PSG header pitch + psgdelta (12). FM untouched.
    cfg = parse_header(_s2_song({}))
    psg = [c for c in cfg.channels if c.kind == "PSG"]
    fm = [c for c in cfg.channels if c.kind == "FM"]
    assert [c.transpose for c in psg] == [_signed(0xDC + 12), _signed(0xDC + 12), 12]
    assert all(c.transpose == 0 for c in fm)
    # S3K source: no delta (HCZ2's PSG header pitch $F4 stays -12).
    hcz = [c for c in parse_header(HCZ2_HEADER).channels if c.kind == "PSG"]
    assert hcz[0].transpose == -12


# ---- (c) nMaxPSG (the probe's second crash) -------------------------------------

def test_s2_nmaxpsg_resolves():
    # :57 for an S3K target: nMaxPSG = nBb6 - psgdelta.
    assert _si.resolve_const("nMaxPSG", _si.SOURCE_S2) == NOTE_BYTES["nBb6"] - 12
    ev = convert_channel("PSG", ["\tdc.b nMaxPSG, $06"], {}, _s2_cfg(), ConvState())
    assert [e.pitch for e in ev if isinstance(e, Note)] == [NOTE_BYTES["nBb6"] - 12 - 0x81]
    # Not an S3K name: the S3K path still refuses it.
    with pytest.raises(KeyError):
        resolve_const("nMaxPSG")


# ---- (d) ModSet units ------------------------------------------------------------

def test_s2_modset_units_converted():
    # smpsModSet w,s,c,st -> w+1, s, c, ((st+1)*s)&$FF (the include's smpsModSet).
    ev = convert_channel("FM", ["\tsmpsModSet $30, $01, $04, $04"], {}, _s2_cfg(), ConvState())
    m = [(e.wait, e.speed, e.change, e.step) for e in ev if isinstance(e, ModSet)]
    assert m == [(0x31, 0x01, 0x04, 0x05)]
    ev = convert_channel("FM", ["\tsmpsModSet $30, $01, $04, $04"], {}, _cfg(), ConvState())
    m = [(e.wait, e.speed, e.change, e.step) for e in ev if isinstance(e, ModSet)]
    assert m == [(0x30, 0x01, 0x04, 0x04)]


# ---- (e)+(f) fTone: the probe's first crash, and the SILENT wrong envelope -------



def test_s2_ftone_with_declared_mapping_converts():
    ev = convert_channel("PSG", ["\tsmpsPSGvoice fTone_02", "\tdc.b nC4, $0C"],
                         {}, _s2_cfg(ftone_map={0x02: 0x02}), ConvState())
    assert [e.env_id for e in ev if isinstance(e, PsgEnv)] == [0x02]


def test_s2_ftone_without_mapping_is_refused_by_name():
    # The hazard: S2 fTone_01 is not S3K envelope 1, and renaming fTone -> sTone
    # made the converter take it with no warning. An undeclared fTone is REFUSED.
    with pytest.raises(_si.S2Refusal, match="fTone_01"):
        convert_channel("PSG", ["\tsmpsPSGvoice fTone_01", "\tdc.b nC4, $0C"],
                        {}, _s2_cfg(), ConvState())


def test_s2_ftone_in_psg_header_is_refused_by_name():
    with pytest.raises(_si.S2Refusal, match="fTone_03"):
        parse_header(_s2_song({}, psg_voice="fTone_03"), ftone_map={})
    cfg = parse_header(_s2_song({}, psg_voice="fTone_03"), ftone_map={0x03: 0x0C})
    assert [c.psg_voice for c in cfg.channels if c.kind == "PSG"][0] == 0x0C


def test_s2_ftone_mapped_to_absent_engine_envelope_is_refused():
    # A declared mapping must name an envelope the engine HAS (or 0 = none); the
    # S3K path's warn-and-emit-0 fallback does not apply to a declaration.
    assert 0x19 not in _si._PSG_ENV_IDS
    with pytest.raises(_si.S2Refusal, match="fTone_03"):
        convert_channel("PSG", ["\tsmpsPSGvoice fTone_03", "\tdc.b nC4, $0C"],
                        {}, _s2_cfg(ftone_map={0x03: 0x19}), ConvState())


def test_s2_psg_header_envelope_is_applied_at_channel_start():
    # S2's smpsHeaderPSG 5th arg is the track's initial envelope (zTrack.VoiceIndex
    # at song init), in force until an in-body smpsPSGvoice replaces it. CPZ's only
    # envelope reference is one of these (CPZ_PSG3 ... fTone_02), and EHZ's three PSG
    # channels all start on one, so dropping it silently plays their first notes
    # with no envelope. It must reach the stream ahead of the first note, and ahead
    # of any loop point (S2 applies it once, at init, not on each loop).
    src = _s2_song({"Tst_PSG1": ["Tst_Loop:", "\tdc.b nC4, $0C", "\tsmpsJump Tst_Loop"]},
                   psg_voice="fTone_03")
    song = convert_song(src, None, {0: 0}, dac_map={}, ftone_map={0x03: 0x0C})
    psg1 = next(c for c in song.channels if c.route == CHROUTE_PSG1)
    kinds = [type(e).__name__ for e in psg1.events]
    first_env = next(i for i, e in enumerate(psg1.events) if isinstance(e, PsgEnv))
    assert psg1.events[first_env].env_id == 0x0C
    assert first_env < kinds.index("Note") and first_env < kinds.index("LoopPoint")
    # A header voice of 0 (none) adds nothing.
    psg2 = next(c for c in song.channels if c.route == CHROUTE_PSG2)
    assert not any(isinstance(e, PsgEnv) for e in psg2.events)


def test_s2_psgvoice_zero_is_no_envelope():
    # S2 zPSGUpdateVolFX: envelope 0 = none (`or a / ret z`); the engine's 0 = none.
    ev = convert_channel("PSG", ["\tsmpsPSGvoice $00", "\tdc.b nC4, $0C"],
                         {}, _s2_cfg(), ConvState())
    assert [e.env_id for e in ev if isinstance(e, PsgEnv)] == [0]


def test_s2_stone_name_in_s2_source_is_refused():
    with pytest.raises(_si.S2Refusal, match="sTone_08"):
        _si.resolve_const("sTone_08", _si.SOURCE_S2)


# ---- (g) S2 DAC enum through a name-keyed mapping --------------------------------

def test_s2_dac_enum_values():
    # _smps2asm_inc.asm:92-95 (case 2).
    e = _si.S2_DAC_ENUM
    assert (e["dKick"], e["dSnare"], e["dMidTom"], e["dFloorTom"], e["dLowClap"]) == \
        (0x81, 0x82, 0x8C, 0x8E, 0x91)


def test_s2_dac_mapped_by_name():
    src = _s2_song({"Tst_DAC": ["\tdc.b dKick, $0C, dSnare"]})
    song = convert_song(src, None, {}, dac_map={"dKick": 2, "dSnare": 3}, ftone_map={})
    dac = next(c for c in song.channels if c.route == CHROUTE_DAC)
    assert [e.sample_id for e in dac.events if isinstance(e, Dac)] == [2, 3]
    pack_song(song)


def test_s2_dac_unmapped_is_refused_by_name():
    src = _s2_song({"Tst_DAC": ["\tdc.b dKick, $0C, dMidTom"]})
    with pytest.raises(_si.S2Refusal, match="dMidTom"):
        convert_song(src, None, {}, dac_map={"dKick": 2}, ftone_map={})


def test_s2_raw_id_dac_remap_is_refused():
    # The S3K raw-id remap is ambiguous across the two enums ($81 is dSnareS3 in
    # one and dKick in the other): an S2 song takes the name-keyed map only.
    src = _s2_song({"Tst_DAC": ["\tdc.b dKick, $0C"]})
    with pytest.raises(_si.S2Refusal, match="dac_map"):
        convert_song(src, {1: 2}, {}, ftone_map={})


# ---- the header declares the source; S1 is not supported -----------------------

def test_s1_source_is_refused():
    with pytest.raises(_si.S2Refusal, match="SourceDriver 1"):
        parse_header(_s2_song({}, start="1"))


# ---- note fill: S3K multiplies by the divider, S2 does not ----------------------

def test_s2_notefill_not_multiplied_by_divider():
    # S3K cfNoteFill calls zComputeNoteDuration ("Multiply note fill by tempo
    # divider", skdisasm Z80 Sound Driver.asm:3231); S2 cfNoteFill stores the
    # operand raw (s2disasm s2.sounddriver.asm:3189-3191).
    ev = convert_channel("FM", ["\tsmpsNoteFill $05"], {}, _s2_cfg(divider=2), ConvState())
    assert [e.master for e in ev if isinstance(e, NoteFill)] == [5]
    ev = convert_channel("FM", ["\tsmpsNoteFill $05"], {}, _cfg(divider=2), ConvState())
    assert [e.master for e in ev if isinstance(e, NoteFill)] == [10]


# ---- (h) song-local voice bank ---------------------------------------------------

def test_s2_song_local_voice_bank():
    src = open(_S2_EHZ).readlines()
    assert _si.song_used_voice_ids(src) == list(range(9))
    blob = _si.pack_song_patch_table(src, _si.song_used_voice_ids(src))
    assert len(blob) == 9 * FMPATCH_LEN
    src = open(_S2_CPZ).readlines()
    assert _si.song_used_voice_ids(src) == list(range(6))
    assert len(_si.pack_song_patch_table(src, _si.song_used_voice_ids(src))) == 6 * FMPATCH_LEN


def test_s2_voice_tl_masked_to_7_bits():
    # smpsVcTotalLevel, (SonicDriverVer>=3)&&(SourceDriver<3): vcTLn &= 127.
    voice = [("smpsVcAlgorithm", ["$07"]), ("smpsVcFeedback", ["$00"]),
             ("smpsVcTotalLevel", ["$80", "$81", "$82", "$83"])]
    s2 = _si.smps_voice_to_fmpatch(voice, _si.SOURCE_S2)
    s2_ref = _si.smps_voice_to_fmpatch(
        voice[:2] + [("smpsVcTotalLevel", ["$00", "$01", "$02", "$03"])])
    assert s2 == s2_ref


# ---- the two real songs ----------------------------------------------------------

def test_s2_real_songs_refuse_with_empty_tables():
    # With nothing declared both songs refuse, and the refusal NAMES every missing
    # fTone and DAC note (the tables passed explicitly: the module defaults are
    # filled since steps 2 and 3).
    with pytest.raises(_si.S2Refusal) as ei:
        convert_song(open(_S2_EHZ).readlines(), None, {v: v for v in range(9)},
                     dac_map={}, ftone_map={})
    msg = str(ei.value)
    for name in ("fTone_01", "fTone_02", "fTone_03", "fTone_08", "fTone_0B",
                 "dKick", "dSnare", "dMidTom", "dFloorTom"):
        assert name in msg, name
    with pytest.raises(_si.S2Refusal) as ei:
        convert_song(open(_S2_CPZ).readlines(), None, {v: v for v in range(6)},
                     dac_map={}, ftone_map={})
    msg = str(ei.value)
    for name in ("fTone_02", "dKick", "dSnare"):
        assert name in msg, name
    assert "dMidTom" not in msg


def _probe_prepass(lines):
    """The design pass's throwaway pre-pass (docs/research/2026-09-25-region-music/
    s2_probe.py `fix`), re-spelled so the S3K path accepts it WITHOUT mutating the
    converter's tables: the S2 DAC names and nMaxPSG become hex literals."""
    out = []
    for ln in lines:
        code = ln.split(";", 1)[0]
        code = _re.sub(r"fTone_", "sTone_", code)
        code = _re.sub(r"\bnMaxPSG\b", "$%02X" % (NOTE_BYTES["nBb6"] - 12), code)
        for name, val in _si.S2_DAC_ENUM.items():
            code = _re.sub(r"\b%s\b" % name, "$%02X" % val, code)
        m = _re.match(r"(\s*)smpsHeaderStartSong\s+2", code)
        if m:
            out.append("%ssmpsHeaderStartSong 3\n" % m.group(1)); continue
        m = _re.match(r"(\s*)smpsHeaderTempo\s+(\S+),\s*(\S+)", code)
        if m:
            mod = resolve_const(m.group(3))
            out.append("%ssmpsHeaderTempo %s, $%02X\n" % (m.group(1), m.group(2), (0x100 - mod) & 0xFF))
            continue
        m = _re.match(r"(\s*)smpsHeaderPSG\s+(.*)", code)
        if m:
            a = [x.strip() for x in m.group(2).split(",")]
            a[1] = "$%02X" % ((resolve_const(a[1]) + 12) & 0xFF)
            out.append("%ssmpsHeaderPSG %s\n" % (m.group(1), ", ".join(a)))
            continue
        m = _re.match(r"(\s*)smpsModSet\s+(.*)", code)
        if m:
            w, s, c, st = [resolve_const(x.strip()) for x in m.group(2).split(",")]
            out.append("%ssmpsModSet $%02X, $%02X, $%02X, $%02X\n"
                       % (m.group(1), (w + 1) & 0xFF, s, c, ((st + 1) * s) & 0xFF))
            continue
        out.append(code + "\n")
    return out


# The design probe's placeholder mapping, as a TEST FIXTURE, not a ruling: these are
# exactly what fTone -> sTone renaming resolved to on the S3K path ($0B -> 0 because
# that path fell back to PsgEnv(0) for it), and its raw-id DAC remap onto S3K drums.
_PROBE_FTONE = {1: 1, 2: 2, 3: 3, 8: 8, 0x0B: 0}
_PROBE_DAC_RAW = {1: 2, 2: 3, 0x0C: 8, 0x0E: 10}
_PROBE_DAC_BY_NAME = {"dKick": 2, "dSnare": 3, "dMidTom": 8, "dFloorTom": 10}


@pytest.mark.parametrize("path,nvoices", [(_S2_EHZ, 9), (_S2_CPZ, 6)])
def test_s2_real_song_matches_the_design_probe(path, nvoices):
    """Differential: the native S2 mode, given the probe's mapping as an explicit
    declaration, packs byte-identical to the S3K path run behind the probe's pre-pass
    (the pre-pass the design measured assembling and sequencing on the real Z80)."""
    src = open(path).readlines()
    patch_remap = {v: v for v in range(nvoices)}
    s3k = pack_song(convert_song(_probe_prepass(src), _PROBE_DAC_RAW, patch_remap))
    song = convert_song(src, None, patch_remap, dac_map=_PROBE_DAC_BY_NAME,
                        ftone_map=_PROBE_FTONE)
    # Since step 2 the native mode also emits each PSG header envelope at stream
    # start (test_s2_psg_header_envelope_is_applied_at_channel_start), which the
    # probe's S3K path drops. Remove exactly those, checking each is there, and
    # the rest must still be byte-identical to the probe.
    hdr = [c.psg_voice for c in parse_header(src, ftone_map=_PROBE_FTONE).channels
           if c.kind == "PSG"]
    psg = [c for c in song.channels if c.route in (CHROUTE_PSG1, CHROUTE_PSG2,
                                                   CHROUTE_PSG3, CHROUTE_PSGN)]
    assert len(psg) == len(hdr) == 3
    for c, want in zip(psg, hdr):
        if want:
            i = next(k for k, e in enumerate(c.events) if isinstance(e, PsgEnv))
            assert c.events[i].env_id == want and i <= 1   # after the Vol prologue
            del c.events[i]
    s2 = pack_song(song)
    assert len(s2) > 0
    assert s2 == s3k
    # The voice bank, as the probe's `voices()` built it (S3K voice path, label
    # found by hand) against the song-local S2 entry point.
    label = next(l.split()[1] for l in src if l.strip().startswith("smpsHeaderVoice"))
    i = next(k for k, l in enumerate(src) if l.strip() == label + ":")
    blocks = _si._parse_vc_blocks([l.split(";")[0] if "smpsVc" in l else l for l in src], i + 1)
    probe = b"".join(bytes(_si.smps_voice_to_fmpatch(blocks[v])).ljust(FMPATCH_LEN, b"\0")
                     for v in range(nvoices))
    assert _si.pack_song_patch_table(src, list(range(nvoices))) == probe


def _load_s2_generator():
    import importlib.util
    here = os.path.dirname(os.path.abspath(__file__))
    p = os.path.join(here, "..", "games", "sonic4", "data", "sound", "song_s2_ehz_cpz.py")
    spec = importlib.util.spec_from_file_location("song_s2_ehz_cpz", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_s2_generator_refuses_and_writes_nothing_with_empty_tables(tmp_path):
    gen = _load_s2_generator()
    with pytest.raises(_si.S2Refusal):
        gen.generate(out_dir=str(tmp_path), ftone_map={}, dac_map={})
    assert list(tmp_path.iterdir()) == []


def test_s2_generator_writes_both_songs_given_declared_maps(tmp_path):
    gen = _load_s2_generator()
    written = gen.generate(out_dir=str(tmp_path), dac_map=_PROBE_DAC_BY_NAME,
                           ftone_map=_PROBE_FTONE)
    names = sorted(p.name for p in tmp_path.iterdir())
    assert names == ["s2_cpz_patches.bin", "s2_ehz_patches.bin",
                     "song_s2_cpz.bin", "song_s2_ehz.bin"]
    sizes = {os.path.basename(p): n for p, n in written}
    assert sizes["s2_ehz_patches.bin"] == 9 * FMPATCH_LEN
    assert sizes["s2_cpz_patches.bin"] == 6 * FMPATCH_LEN


def test_s2_generator_default_output_is_the_embedded_sound_dir():
    # Step 4 (S2CLIP-REGION-MUSIC): the songs joined the bank, so the default output is
    # the directory mt_bank.emp embeds from (the HCZ2 convention), not tools/generated/.
    gen = _load_s2_generator()
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    assert (os.path.relpath(gen.OUT_DIR, root).replace(os.sep, "/")
            == "games/sonic4/data/sound")
    mt_bank = open(os.path.join(root, "games/sonic4/data/sound/mt_bank.emp")).read()
    for name in ("song_s2_ehz.bin", "s2_ehz_patches.bin",
                 "song_s2_cpz.bin", "s2_cpz_patches.bin"):
        assert f'embed("{name}")' in mt_bank, f"mt_bank.emp does not embed {name}"


def test_s2_committed_songs_are_the_generators_output(tmp_path):
    # The build embeds the COMMITTED files and never re-runs the generator, so a converter
    # or table change that alters either song must fail here until the files are
    # regenerated and committed (a regeneration moves ROM bytes).
    gen = _load_s2_generator()
    written = gen.generate(out_dir=str(tmp_path))
    assert len(written) == 4
    for p, n in written:
        committed = os.path.join(gen.OUT_DIR, os.path.basename(p))
        assert os.path.isfile(committed), f"{committed} is not committed"
        assert open(committed, "rb").read() == open(p, "rb").read(), (
            f"{os.path.basename(p)}: the committed file is not the generator's output; "
            f"run python3 games/sonic4/data/sound/song_s2_ehz_cpz.py and commit")


# ---- steps 2 and 3: the declared tables, filled, exercised on the real songs ----
#
# Step 2 imported Sonic 2's own PSG envelopes as NEW engine envelope ids (disjoint
# from the S3K sTone ids $01..$27) and S2_FTONE_MAP points each fTone the two songs
# use at its imported S2 body. Step 3 filled S2_DAC_MAP per the owner's ruling
# S2CLIP-MUSIC-DRUMS = s3k-drums (docs/decisions.jsonl): Sonic 2's drum notes play
# the S3K drums the engine already carries. Every expectation below is derived from
# a source (s2disasm's driver, the song files, HCZ2_DAC_REMAP), not restated.

_S2_DRIVER = str(suite_path("s2disasm", "s2.sounddriver.asm"))
_S3K_STONE_MAX = 0x27    # skdisasm _smps2asm_inc.asm:72-78: sTone_01..sTone_27


def _s2_env_bodies():
    """{N: bytes} for S2's zPSG_EnvN, read verbatim out of s2disasm's Z80 driver
    (the label, then its `db` lines up to the first line that is not one)."""
    out, cur = {}, None
    for ln in open(_S2_DRIVER, encoding="utf-8", errors="replace"):
        code = ln.split(";", 1)[0].rstrip()
        m = _re.match(r"^zPSG_Env(\d+):\s*$", code)
        if m:
            cur = int(m.group(1)); out[cur] = []; continue
        m = _re.match(r"^\s+db\s+(.*)$", code)
        if m and cur is not None:
            for t in m.group(1).split(","):
                t = t.strip()
                out[cur].append(int(t[:-1], 16) if t.lower().endswith("h") else int(t))
            continue
        if code.strip():
            cur = None
    return out


def _shipped_psg_envs():
    import gen_sound_tables
    return {eid: body for eid, _lbl, body in gen_sound_tables._PSG_VOL_ENVS}


def test_s2_env_body_parser_reads_the_driver():
    # Control for the parser the rows below lean on: 13 envelopes, each ending in
    # S2's one terminator $80 (and no other byte >= $80), zPSG_Env1 as the design
    # doc quotes it (s2.sounddriver.asm:3736).
    b = _s2_env_bodies()
    assert sorted(b) == list(range(1, 14))
    assert all(v[-1] == 0x80 and all(x < 0x80 for x in v[:-1]) for v in b.values())
    assert b[1] == [0, 0, 0, 1, 1, 1, 2, 2, 2, 3, 3, 3, 4, 4, 4, 5, 5, 5, 6, 6, 6, 7, 0x80]


def test_s2_ftone_map_covers_exactly_what_ehz_and_cpz_use():
    used = set()
    for p in (_S2_EHZ, _S2_CPZ):
        ftones, _ = _si.s2_mapping_requirements(open(p).readlines())
        used |= set(ftones)
    assert set(_si.S2_FTONE_MAP) == used


def test_s2_ftone_map_points_at_imported_s2_bodies_never_s3k_ones():
    # The silent trap the design found (Q1 row f): S2 fTone_NN is not the engine's
    # S3K envelope NN. Each mapped id must (1) be shipped, (2) lie OUTSIDE the S3K
    # sTone range so no S3K song can ever resolve to it, and (3) carry S2's
    # zPSG_EnvNN body with S2's terminator $80 (hold the last level: zVolEnvHold)
    # re-spelled as the engine's sustain-hold $81, because the engine's $80 LOOPS.
    shipped = _shipped_psg_envs()
    s2 = _s2_env_bodies()
    assert _si.S2_FTONE_MAP
    for sid, eid in _si.S2_FTONE_MAP.items():
        assert eid in shipped, "fTone_%02X -> $%02X is not shipped" % (sid, eid)
        assert eid in _si._PSG_ENV_IDS
        assert eid > _S3K_STONE_MAX, "fTone_%02X maps into the S3K id range" % sid
        assert shipped[eid] == s2[sid][:-1] + [0x81], "fTone_%02X body" % sid


def test_s2_ftone_02_is_not_the_s3k_body_of_the_same_number():
    # The design said fTone_02 "happens to match" S3K's; it matches only up to the
    # terminator: S3K VolEnv_01 ends in $83 (rest, key off), S2 zPSG_Env2 in $80
    # (hold). Pinning that the map does not take the S3K id for it.
    shipped = _shipped_psg_envs()
    assert shipped[0x02][:-1] == _s2_env_bodies()[2][:-1]
    assert shipped[0x02][-1] == 0x83
    assert _si.S2_FTONE_MAP[0x02] != 0x02


def test_s2_dac_map_is_the_s3k_drums_ruling():
    # s3k-drums: each S2 drum the songs play goes to the S3K sample of the same
    # role, named through HCZ2_DAC_REMAP (the S3K-source ids: 1-based dSnareS3=1,
    # dMidTomS3=3, dFloorTomS3=5, dKickS3=6), so the ids are not restated here.
    s3k = {"dKick": HCZ2_DAC_REMAP[6], "dSnare": HCZ2_DAC_REMAP[1],
           "dMidTom": HCZ2_DAC_REMAP[3], "dFloorTom": HCZ2_DAC_REMAP[5]}
    assert _si.S2_DAC_MAP == s3k
    used = set()
    for p in (_S2_EHZ, _S2_CPZ):
        used |= set(_si.s2_mapping_requirements(open(p).readlines())[1])
    assert set(_si.S2_DAC_MAP) == used


@pytest.mark.parametrize("path,nvoices", [(_S2_EHZ, 9), (_S2_CPZ, 6)])
def test_s2_real_song_converts_through_the_declared_tables(path, nvoices):
    # The module defaults, no fixture: every PsgEnv the song emits is 0 or an
    # imported S2 id, every Dac event an S3K drum, and the ids follow the source's
    # own references.
    src = open(path).readlines()
    song = convert_song(src, None, {v: v for v in range(nvoices)})
    envs = [e.env_id for c in song.channels for e in c.events if isinstance(e, PsgEnv)]
    s2_ids = set(_si.S2_FTONE_MAP.values())
    assert envs and set(envs) <= s2_ids | {0}
    ftones, dacs = _si.s2_mapping_requirements(src)
    assert {_si.S2_FTONE_MAP[s] for s in ftones} <= set(envs)
    dac_ids = {e.sample_id for c in song.channels for e in c.events if isinstance(e, Dac)}
    assert dac_ids == {_si.S2_DAC_MAP[n] for n in dacs}
    assert len(pack_song(song)) > 0


def test_s2_generator_writes_both_songs_with_the_declared_tables(tmp_path):
    gen = _load_s2_generator()
    written = gen.generate(out_dir=str(tmp_path))
    sizes = {os.path.basename(p): n for p, n in written}
    assert sorted(sizes) == ["s2_cpz_patches.bin", "s2_ehz_patches.bin",
                             "song_s2_cpz.bin", "song_s2_ehz.bin"]
    assert sizes["s2_ehz_patches.bin"] == 9 * FMPATCH_LEN
    assert sizes["s2_cpz_patches.bin"] == 6 * FMPATCH_LEN


# ---- header volume seeds the running volume (S2CLIP volume parcel, 2026-09-26) ------
# Both drivers copy the smpsHeaderFM/PSG volume byte into zTrack.Volume at song init and
# every smpsAlterVol / smpsPSGAlterVol ADDS to it (S2 cfChangeFMVolume / cfChangePSGVolume:
# `add a,(ix+zTrack.Volume)`). The converter used to start the running volume at 0 (loudest),
# so a channel's first AlterVol discarded the header: rendered against real Sonic 2, EHZ's
# FM2..FM5 played 11 to 19 dB too loud and PSG1/2 8 dB (docs/research/2026-09-26-s2-music-volume.md).

def _first_vol_before_note(events):
    last = None
    for e in events:
        if isinstance(e, Vol):
            last = e.vol
        elif isinstance(e, (Note, NoteDur)):
            return last
    return last


def test_s2_alter_vol_composes_with_the_header_volume():
    # FM4 header $20, then AlterVol $F8 (-8): zTrack.Volume = $18 at the first note.
    # PSG1 header $04, then PSGAlterVol $02: $06.
    src = _s2_song({"Tst_FM4": ["\tsmpsSetvoice $00", "\tsmpsAlterVol $F8", "\tdc.b nC4, $0C"],
                    "Tst_PSG1": ["\tsmpsPSGAlterVol $02", "\tdc.b nC4, $0C"]})
    song = convert_song(src, None, {0: 0}, dac_map={}, ftone_map={})
    fm4 = next(c for c in song.channels if c.route == CHROUTE_FM4)
    psg1 = next(c for c in song.channels if c.route == CHROUTE_PSG1)
    assert _first_vol_before_note(fm4.events) == _si._fm_atten_to_v0(0x20 - 8)
    assert _first_vol_before_note(psg1.events) == _si._psg_atten_to_v0(0x04 + 2)


def _source_first_note_volume(src, label, kind, header_vol):
    """Independent of the converter's state machine: walk the channel's own lines from its
    label, summing (PSG)AlterVol deltas until the first note, entering an smpsCall's
    target inline. None if other control flow (loop/jump/stop/return/setvol) comes first,
    so the channel is not checked."""
    lines = [ln.split(";")[0].strip() for ln in src]
    notes = (set(NOTE_BYTES) | set(_si._S2_NOTE_EXTRAS)) - {"nRst"}
    op = "smpsAlterVol" if kind == "FM" else "smpsPSGAlterVol"

    def walk(lbl, vol, depth):
        # -> ("note", vol) | ("ret", vol) | ("stop", None)
        if depth > 4:
            return "stop", None
        for ln in lines[lines.index(lbl + ":") + 1:]:
            if not ln or ln.endswith(":"):
                continue
            mnem = ln.split()[0]
            if mnem == op:
                vol += _signed(resolve_const(ln.split()[1]))
            elif mnem == "smpsCall":
                how, vol = walk(ln.split()[1], vol, depth + 1)
                if how != "ret":
                    return how, vol
            elif mnem == "smpsReturn" and depth:
                return "ret", vol
            elif mnem in ("smpsReturn", "smpsLoop", "smpsJump", "smpsStop", "smpsSetVol"):
                return "stop", None
            elif mnem == "dc.b" and any(t.strip() in notes for t in ln[4:].split(",")):
                return "note", vol
        return "stop", None

    how, vol = walk(label, header_vol, 0)
    return vol if how == "note" else None


def test_s2_real_songs_first_note_volume_is_header_plus_deltas():
    checked = altered = 0
    for path in (_S2_EHZ, _S2_CPZ):
        c, a = _check_first_note_volumes(path)
        checked += c
        altered += a
    # The population must be real and must contain the guarded case, a channel whose first
    # note follows an AlterVol (in the source: EHZ FM4, FM5, PSG1, PSG2; CPZ has none, its
    # AlterVols all come after a first note, which the committed-bins test covers).
    assert checked >= 8 and altered >= 4, (checked, altered)


def _check_first_note_volumes(path):
    src = open(path).readlines()
    cfg = parse_header(src, ftone_map=_si.S2_FTONE_MAP)
    song = convert_song(src, None, {v: v for v in range(16)})
    blocks = _si.split_blocks(src)
    noise = frozenset(c.label for c in cfg.channels if c.kind == "PSG" and
                      _si._channel_reaches_noise_form(c.label, blocks, _si.SOURCE_S2))
    routes = dict(_si._assign_routes(cfg.channels, noise))
    checked = altered = 0
    for ch in cfg.channels:
        if ch.kind not in ("FM", "PSG"):
            continue
        want = _source_first_note_volume(src, ch.label, ch.kind, ch.volume)
        if want is None:
            continue
        conv = next(c for c in song.channels if c.route == routes[ch])
        got = _first_vol_before_note(conv.events)
        exp = (_si._fm_atten_to_v0(want) if ch.kind == "FM"
               else _si._psg_atten_to_v0(want))
        assert got == exp, "%s: first-note Vol %s, want %s (header $%02X -> $%02X)" % (
            ch.label, got, exp, ch.volume, want)
        checked += 1
        altered += want != ch.volume
    return checked, altered
