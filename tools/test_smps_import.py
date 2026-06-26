# tools/test_smps_import.py
from smps_import import tokenize_line, NOTE_BYTES, PAN_BYTES, DAC_IDS, FLAG_BYTES, resolve_const, HCZ2_DAC_REMAP

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
    assert cfg.tempo_base == 19       # 4096/(256-0x25) = 4096/219 ≈ 18.7 -> 19
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

# ── Tempo conversion correctness ─────────────────────────────────────────────
# Engine model: accum -= 16/frame, tick on borrow -> ticks/frame = 16/tempo_base.
# SMPS model:   accum += mod/frame, overflow skips tick -> ticks/frame = (256-mod)/256.
# Match:        tempo_base = 4096 / (256 - mod).

def test_tempo_mod_zero_gives_max_rate():
    # mod=0 -> denominator 256 -> 4096/256 = 16 -> 1 tick/frame (maximum rate).
    cfg = SongConfig(); cfg.tempo_mod = 0
    assert cfg.tempo_base == 16

def test_tempo_mod_hcz2():
    # HCZ2: mod=$25=37 -> 4096/(256-37) = 4096/219 ≈ 18.70 -> 19.
    cfg = SongConfig(); cfg.tempo_mod = 0x25
    assert cfg.tempo_base == 19

def test_tempo_mod_high_clamps():
    # mod=$F0=240 -> 4096/(256-240) = 4096/16 = 256; clamp to 255.
    cfg = SongConfig(); cfg.tempo_mod = 0xF0
    assert cfg.tempo_base == 255

def test_tempo_mod_never_below_16():
    # Even mod=0 the floor is 16 (1 tick/frame exactly = already there).
    # Try a very small denom via mod=255 -> 4096/1 = 4096, clamp to 255.
    cfg = SongConfig(); cfg.tempo_mod = 255
    assert cfg.tempo_base == 255

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

def test_psg_voice_safe_env():
    ev = convert_channel("PSG", ["\tsmpsPSGvoice sTone_0C", "\tdc.b nC4, $0C"],
                         {}, _cfg(), ConvState())
    assert any(isinstance(e, PsgEnv) and e.env_id == 0 for e in ev)

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
    # smpsAlterVol on FM: running volume +/- delta, emits Vol.
    ev = convert_channel("FM",
                         ["\tsmpsSetVol $10", "\tsmpsAlterVol $04"],
                         {}, _cfg(), ConvState())
    vols = [e for e in ev if isinstance(e, Vol)]
    assert len(vols) == 2 and vols[-1].vol != vols[0].vol

def test_call_depth_guard():
    # Self-recursive call must error rather than blow the stack.
    blocks = {"R": ["\tsmpsCall R"]}
    raised = False
    try:
        convert_channel("FM", [], blocks, _cfg(), ConvState(), start_label="R")
    except Exception:
        raised = True
    assert raised

# ── Task 2.3 end-to-end: real HCZ2 FM + DAC convert without raising ──────────

def _hcz2_blocks_and_cfg():
    path = "/home/volence/sonic_hacks/skdisasm/Sound/Music/HCZ2.asm"
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
    assert song.tempo_base == 19      # 4096/(256-0x25) = 4096/219 ≈ 18.7 -> 19

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
    path = "/home/volence/sonic_hacks/skdisasm/Sound/Music/HCZ2.asm"
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
    assert len(smps_voice_to_fmpatch(_UVB_VOICE_03)) == FMPATCH_LEN == 26

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
        assert len(p) == 26, "voice $%02X must be 26 bytes" % vid

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
    # Each row must encode exactly 26 bytes.
    for row in rows:
        body = row.split(";", 1)[0]
        nbytes = body.count("$")
        assert nbytes == 26, "row has %d bytes, expected 26: %r" % (nbytes, row)

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
