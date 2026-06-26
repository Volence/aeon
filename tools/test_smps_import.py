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
    # FIX 2: the 3rd smpsHeaderFM arg is the channel VOLUME, not a voice
    # (smpsHeaderFM loc,pitch,vol — _smps2asm_inc.asm:332).
    assert fm1.kind == "FM" and fm1.volume == 0x0F and fm1.transpose == 0x18
    psg1 = next(c for c in cfg.channels if c.label == "Snd_HCZ2_PSG1")
    # smpsHeaderPSG loc,pitch,vol,mod,voice: volume=$04, psg_voice=sTone_0C=$0C.
    assert psg1.kind == "PSG" and psg1.volume == 0x04 and psg1.psg_voice == 0x0C
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
