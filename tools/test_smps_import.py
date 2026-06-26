# tools/test_smps_import.py
from smps_import import tokenize_line, NOTE_BYTES, PAN_BYTES, DAC_IDS, resolve_const

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
