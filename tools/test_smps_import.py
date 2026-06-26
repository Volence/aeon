# tools/test_smps_import.py
from smps_import import tokenize_line, NOTE_BYTES, PAN_BYTES, DAC_IDS, FLAG_BYTES, resolve_const

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
    assert cfg.tempo_mod == 0x25
    assert cfg.tempo_base == 256 - 0x25          # 0xDB
    assert [c.label for c in cfg.channels] == [
        "Snd_HCZ2_DAC","Snd_HCZ2_FM1","Snd_HCZ2_FM2","Snd_HCZ2_FM3",
        "Snd_HCZ2_FM4","Snd_HCZ2_FM5","Snd_HCZ2_PSG1","Snd_HCZ2_PSG2","Snd_HCZ2_PSG3"]
    fm1 = next(c for c in cfg.channels if c.label == "Snd_HCZ2_FM1")
    assert fm1.kind == "FM" and fm1.voice == 0x0F and fm1.transpose == 0x18
    dac = cfg.channels[0]
    assert dac.kind == "DAC"

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
    hcz2_path = "/home/volence/sonic_hacks/skdisasm/Sound/Music/HCZ2.asm"
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

# ── Task 2.2 ─ coordination-flag -> MEV mapping + DAC route ──────────────────

from song_packer import Pan, Patch, ModSet, End, Dac

def test_flags_map():
    ev = convert_channel("FM", ["\tsmpsPan panLeft, $00","\tsmpsSetvoice $0F","\tsmpsModSet $01,$02,$03,$04","\tsmpsStop"], {}, _cfg(), ConvState())
    assert isinstance(ev[0],Pan) and ev[0].b4==0x80
    assert isinstance(ev[1],Patch) and ev[1].patch==0x0F
    assert isinstance(ev[2],ModSet) and (ev[2].wait,ev[2].speed,ev[2].change,ev[2].step)==(1,2,3,4)
    assert isinstance(ev[3],End)

def test_dac_samples_and_pan_dropped():
    ev = convert_channel("DAC", ["\tdc.b dKickS3, $06","\tsmpsPan panLeft, $00","\tdc.b dSnareS3, $06"], {}, _cfg(), ConvState())
    ids = [e.sample_id for e in ev if isinstance(e,Dac)]
    assert ids == [0x86 & 0x7F, 0x81 & 0x7F]
    assert not any(isinstance(e,Pan) for e in ev)

def test_inline_smpsnoattack_does_not_break_walk():
    ev = convert_channel("PSG", ["\tdc.b nMaxPSG1, $06, smpsNoAttack, $06, nC4"], {}, _cfg(), ConvState())
    # the inline $E7 must not be treated as a note; nMaxPSG1 and nC4 are notes
    notes = [e for e in ev if isinstance(e, Note)]
    assert len(notes) == 2
