# HCZ2 SMPS Import — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Play Sonic 3&K's Hydrocity Zone Act 2 in the aeon sound driver via a reusable SMPS(S3K)→music-format-v0 converter, with the real S3K drum kit.

**Architecture:** A Python converter (`tools/smps_import.py`) parses skdisasm SMPS2ASM macro source, runs a stateful per-channel pass (inline calls, flatten loops, fold transpose/volume, map coordination flags), and emits a `SongDesc` consumed by the existing `tools/song_packer.py`. HCZ2 uses the existing STREAM + FM6=DAC dedicate path (FM1–5 melody + DAC drums on ch6 + 3 PSG) — no engine code changes. The 6 S3K drums are encoded from their `.wav` sources through `tools/dac_encode.py`.

**Tech Stack:** Python 3 + numpy (converter, encoder), AS macro assembler (engine build), oracle (Exodus) MCP for verification.

**Spec:** `docs/superpowers/specs/2026-06-25-hcz2-smps-import-design.md`

**Reference paths:**
- Source song: `/home/volence/sonic_hacks/skdisasm/Sound/Music/HCZ2.asm`
- SMPS2ASM macros/constants: `/home/volence/sonic_hacks/skdisasm/Sound/_smps2asm_inc.asm`
- S3K voice bank + driver: `/home/volence/sonic_hacks/skdisasm/Sound/Z80 Sound Driver.asm`
- S3K DAC wavs: `/home/volence/sonic_hacks/skdisasm/Sound/DAC/*.wav`
- Packer API: `tools/song_packer.py` (event classes `Note/Rest/SetDur/Vol/Patch/Pan/ModSet/PsgEnv/NoteFill/Dac/NoteDur/NoteRaw/RepeatStart/RepeatEnd/LoopPoint/Jump/End`; `ChannelDesc(route, events)`; `SongDesc(tempo, channels, flags=0, tempo_base=..., patch_count=..., pitchtable=None)`; `write_asm(song, label, out_path)`; routes `CHROUTE_FM1..FM6/PSG1..3/PSGN/DAC`; `SH_F_STREAM`)
- Raw-8 encoder: `tools/dac_encode.py` (`encode_raw8(samples)`, CLI `--codec raw`)
- Patch format: `sound_constants.asm` `FmPatch` (26 bytes: `fp_alg_fb, fp_lr_ams_fms, fp_dt_mul[4], fp_tl[4], fp_rs_ar[4], fp_am_d1r[4], fp_d2r[4], fp_d1l_rr[4]`; op order S1,S3,S2,S4)
- DAC table: `engine/z80_sound_driver.asm` `DacSampleTable` + `data/sound/dac_samples.asm`

**Build/verify:** `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh` (timeout-wrapped — asl can hang). Verify in oracle only (no real hardware). Build needs the gitignored OJZ exports OR tolerates the fallback level (HCZ2 is sound-only, fallback level is fine). Set `tools/bin` as an ABSOLUTE symlink to the main checkout's `tools/bin` before the first build (DAC-phase gotcha).

---

## Phase 0 — Converter scaffold + SMPS constant tables

### Task 0.1: Macro-line tokenizer

**Files:**
- Create: `tools/smps_import.py`
- Test: `tools/test_smps_import.py`

- [ ] **Step 1: Write the failing test**

```python
# tools/test_smps_import.py
from smps_import import tokenize_line

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
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd tools && python3 -m pytest test_smps_import.py -v`
Expected: FAIL (`ImportError`/`AttributeError: tokenize_line`).

- [ ] **Step 3: Implement `tokenize_line`**

```python
# tools/smps_import.py  — SMPS (S3K) -> music-format-v0 converter.
import os, sys, re
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

def tokenize_line(line):
    """Return (mnemonic_or_None, [args], label_or_None) for one SMPS2ASM source line.
    Strips ';' comments. A line like 'Foo:' yields a label; '\tmacro a, b' yields
    (macro, [a, b], None)."""
    code = line.split(";", 1)[0].rstrip()
    if not code.strip():
        return (None, [], None)
    m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*):", code.strip())
    if m and code.strip().endswith(":"):
        return (None, [], m.group(1))
    parts = code.strip().split(None, 1)
    mnem = parts[0]
    args = [a.strip() for a in parts[1].split(",")] if len(parts) > 1 else []
    return (mnem, args, None)
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd tools && python3 -m pytest test_smps_import.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add tools/smps_import.py tools/test_smps_import.py
git commit -m "feat(tools): smps_import tokenizer (SMPS2ASM macro lines)"
```

### Task 0.2: SMPS2ASM constant tables (note names, pan, DAC samples)

**Files:**
- Modify: `tools/smps_import.py`
- Test: `tools/test_smps_import.py`

- [ ] **Step 1: Write the failing test**

```python
from smps_import import NOTE_BYTES, PAN_BYTES, DAC_IDS, resolve_const

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
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd tools && python3 -m pytest test_smps_import.py::test_note_name_to_byte -v`
Expected: FAIL.

- [ ] **Step 3: Implement the constant tables**

Build `NOTE_BYTES` programmatically (`nC0=$81`, chromatic 12/octave, octaves 0..7), `PAN_BYTES` (`panLeft=$80, panRight=$40, panCenter=$C0, panNone=$00`), and `DAC_IDS` from the driver-v3 enum (`dSnareS3=$81, dHighTom=$82, dMidTomS3=$83, dLowTomS3=$84, dFloorTomS3=$85, dKickS3=$86`, … as needed). `resolve_const` parses `$hex`/decimal or looks up a name across all tables.

```python
_NOTE_NAMES = ["C","Cs","D","Ds","E","F","Fs","G","Gs","A","As","B"]
NOTE_BYTES = {}
for _oct in range(8):
    for _i, _n in enumerate(_NOTE_NAMES):
        NOTE_BYTES["n%s%d" % (_n, _oct)] = 0x81 + _oct*12 + _i

PAN_BYTES = {"panLeft": 0x80, "panRight": 0x40, "panCenter": 0xC0, "panNone": 0x00}

# Driver-v3 DAC enum (_smps2asm_inc.asm). Only the HCZ2 set is required; extend as needed.
DAC_IDS = {
    "dSnareS3": 0x81, "dHighTom": 0x82, "dMidTomS3": 0x83, "dLowTomS3": 0x84,
    "dFloorTomS3": 0x85, "dKickS3": 0x86,
}

def resolve_const(tok):
    tok = tok.strip()
    if tok.startswith("$"):
        return int(tok[1:], 16)
    if re.fullmatch(r"-?\d+", tok):
        return int(tok)
    for table in (NOTE_BYTES, PAN_BYTES, DAC_IDS):
        if tok in table:
            return table[tok]
    raise KeyError("unknown SMPS constant: %r" % tok)
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd tools && python3 -m pytest test_smps_import.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tools/smps_import.py tools/test_smps_import.py
git commit -m "feat(tools): smps_import SMPS2ASM constant tables (notes/pan/DAC)"
```

---

## Phase 1 — Header + channel-block parse

### Task 1.1: Parse the song header → SongConfig

**Files:** Modify `tools/smps_import.py`; Test `tools/test_smps_import.py`

- [ ] **Step 1: Write the failing test**

```python
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
    # DAC + FM1..FM5 + PSG1..PSG3
    assert [c.label for c in cfg.channels] == [
        "Snd_HCZ2_DAC","Snd_HCZ2_FM1","Snd_HCZ2_FM2","Snd_HCZ2_FM3",
        "Snd_HCZ2_FM4","Snd_HCZ2_FM5","Snd_HCZ2_PSG1","Snd_HCZ2_PSG2","Snd_HCZ2_PSG3"]
    fm1 = next(c for c in cfg.channels if c.label == "Snd_HCZ2_FM1")
    assert fm1.kind == "FM" and fm1.voice == 0x0F and fm1.transpose == 0x18
    dac = cfg.channels[0]
    assert dac.kind == "DAC"
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd tools && python3 -m pytest test_smps_import.py::test_parse_header -v`
Expected: FAIL.

- [ ] **Step 3: Implement `SongConfig`/`ChannelHdr`/`parse_header`**

```python
class ChannelHdr:
    def __init__(self, kind, label, transpose=0, voice=None):
        self.kind = kind          # "FM" | "PSG" | "DAC"
        self.label = label        # the channel's data label
        self.transpose = transpose
        self.voice = voice

class SongConfig:
    def __init__(self):
        self.divider = 1; self.tempo_mod = 0; self.channels = []
    @property
    def tempo_base(self):
        return max(16, min(255, 256 - self.tempo_mod))

def _signed8(v):
    return v - 256 if v >= 128 else v

def parse_header(lines):
    cfg = SongConfig()
    for ln in lines:
        mnem, args, _ = tokenize_line(ln)
        if mnem == "smpsHeaderTempo":
            cfg.tempo_mod = resolve_const(args[0]); cfg.divider = resolve_const(args[1])
        elif mnem == "smpsHeaderDAC":
            cfg.channels.append(ChannelHdr("DAC", args[0]))
        elif mnem == "smpsHeaderFM":
            cfg.channels.append(ChannelHdr("FM", args[0],
                transpose=_signed8(resolve_const(args[1])), voice=resolve_const(args[2])))
        elif mnem == "smpsHeaderPSG":
            cfg.channels.append(ChannelHdr("PSG", args[0],
                transpose=_signed8(resolve_const(args[1]))))
    return cfg
```

Note: `smpsHeaderTempo div,mod` order in SMPS is `mod, divider`? Verify against `_smps2asm_inc.asm` `smpsHeaderTempo` macro — adjust the two `args[]` indices so `tempo_mod` is the global-tempo byte (`$25`) and `divider` the per-note multiplier (`$01`). The test pins the expected values.

- [ ] **Step 4: Run to verify it passes**

Run: `cd tools && python3 -m pytest test_smps_import.py::test_parse_header -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tools/smps_import.py tools/test_smps_import.py
git commit -m "feat(tools): smps_import header parser -> SongConfig"
```

### Task 1.2: Split file into label→lines blocks

**Files:** Modify `tools/smps_import.py`; Test `tools/test_smps_import.py`

- [ ] **Step 1: Write the failing test**

```python
from smps_import import split_blocks

def test_split_blocks():
    src = ["Snd_HCZ2_FM1:", "\tsmpsSetvoice $0F", "\tdc.b nC4, $0C",
           "Snd_HCZ2_FM2:", "\tdc.b nG3"]
    blocks = split_blocks(src)
    assert list(blocks.keys()) == ["Snd_HCZ2_FM1", "Snd_HCZ2_FM2"]
    assert blocks["Snd_HCZ2_FM1"] == ["\tsmpsSetvoice $0F", "\tdc.b nC4, $0C"]
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Implement**

```python
def split_blocks(lines):
    """label -> list of source lines until the next label. Lines before the first
    label are ignored (header handled separately)."""
    blocks, cur = {}, None
    for ln in lines:
        _, _, label = tokenize_line(ln)
        if label is not None:
            cur = label; blocks[cur] = []
        elif cur is not None and ln.split(";",1)[0].strip():
            blocks[cur].append(ln)
    return blocks
```

- [ ] **Step 4: Run** → PASS.

- [ ] **Step 5: Commit**

```bash
git add tools/smps_import.py tools/test_smps_import.py
git commit -m "feat(tools): smps_import label-block splitter"
```

---

## Phase 2 — Channel event conversion (the core)

The converter walks a channel's lines, maintaining state (`transpose`, `volume`, `divider`), inlining `smpsCall` bodies and flattening `smpsLoop`, and emits `song_packer` `Event` objects. Implement as `convert_channel(kind, lines, blocks, cfg, state)` returning a `list[Event]`.

### Task 2.1: Notes, rests, durations

**Files:** Modify `tools/smps_import.py`; Test `tools/test_smps_import.py`

- [ ] **Step 1: Write the failing test**

```python
from smps_import import convert_channel, ConvState
from song_packer import Note, Rest, SetDur, NoteDur

def _conv(kind, lines, **cfgkw):
    from smps_import import SongConfig
    cfg = SongConfig(); cfg.divider = cfgkw.get("divider", 1)
    st = ConvState(transpose=cfgkw.get("transpose", 0))
    return convert_channel(kind, lines, {}, cfg, st)

def test_note_and_duration():
    # SMPS: set duration $0C, play nC4 (=$81+ (4*12)= $B1 -> index 48), then a rest
    ev = _conv("FM", ["\tdc.b $0C, nC4", "\tdc.b $80"])
    assert isinstance(ev[0], SetDur) and ev[0].ticks == 0x0C
    assert isinstance(ev[1], Note) and ev[1].pitch == (0xB1 - 0x81)   # 48
    assert isinstance(ev[2], Rest)

def test_transpose_folds_into_pitch():
    ev = _conv("FM", ["\tdc.b nC4"], transpose=2)
    assert isinstance(ev[0], Note) and ev[0].pitch == (0xB1 - 0x81) + 2

def test_duration_times_divider():
    ev = _conv("FM", ["\tdc.b $40, nC4"], divider=2)   # 0x40*2 = 0x80 > 0x7F -> NoteDur
    assert isinstance(ev[0], NoteDur) and ev[0].dur == 0x80
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Implement the note/rest/duration core**

```python
NOTE_REST = 0x80

class ConvState:
    def __init__(self, transpose=0, volume=None):
        self.transpose = transpose
        self.volume = volume
        self.cur_dur = None          # last SetDur ticks (None until set)

def _is_note(b):  return 0x81 <= b <= 0xDF
def _is_dur(b):   return b < 0x80

def _emit_note(out, pitch_index, dur, st):
    from song_packer import Note, NoteDur
    if dur is not None and dur > 0x7F:
        out.append(NoteDur(pitch_index, dur))
    else:
        out.append(Note(pitch_index))

def convert_channel(kind, lines, blocks, cfg, st):
    from song_packer import Rest, SetDur
    out = []
    # flatten the line tokens into a byte/flag stream first (Task 2.3 adds call/loop)
    for ln in lines:
        mnem, args, _ = tokenize_line(ln)
        if mnem not in ("dc.b", "dc.w", None):
            continue  # coordination flags handled in Task 2.2; skip here
        for tok in args:
            b = resolve_const(tok)
            if _is_dur(b):
                ticks = b * cfg.divider
                if ticks <= 0x7F:
                    out.append(SetDur(ticks)); st.cur_dur = ticks
                else:
                    st.cur_dur = ticks   # carried into NoteDur on the next note
            elif b == NOTE_REST:
                out.append(Rest())
            elif _is_note(b):
                _emit_note(out, (b - 0x81) + st.transpose, st.cur_dur, st)
    return out
```

- [ ] **Step 4: Run** → PASS (the three tests).

- [ ] **Step 5: Commit**

```bash
git add tools/smps_import.py tools/test_smps_import.py
git commit -m "feat(tools): smps_import note/rest/duration conversion"
```

### Task 2.2: Coordination-flag → MEV mapping

**Files:** Modify `tools/smps_import.py`; Test `tools/test_smps_import.py`

- [ ] **Step 1: Write the failing test**

```python
from song_packer import Pan, Vol, Patch, ModSet, PsgEnv, NoteFill, Dac, End, LoopPoint, Jump

def test_flags_map():
    ev = _conv("FM", [
        "\tsmpsPan panLeft, $00",
        "\tsmpsSetvoice $0F",
        "\tsmpsModSet $01, $02, $03, $04",
        "\tsmpsStop",
    ])
    assert isinstance(ev[0], Pan)   and ev[0].b4 == 0x80
    assert isinstance(ev[1], Patch) and ev[1].patch == 0x0F
    assert isinstance(ev[2], ModSet) and (ev[2].wait, ev[2].speed, ev[2].change, ev[2].step) == (1,2,3,4)
    assert isinstance(ev[3], End)

def test_dac_channel_sample_and_pan_dropped():
    ev = _conv("DAC", ["\tdc.b dKickS3, $06", "\tsmpsPan panLeft, $00", "\tdc.b dSnareS3"])
    ids = [e for e in ev if isinstance(e, Dac)]
    assert [d.sample_id for d in ids] == [0x86 & 0x7F, 0x81 & 0x7F]   # 6, 1 (remap applied later)
    assert not any(isinstance(e, Pan) for e in ev)  # pan dropped on DAC route
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Implement flag dispatch** inside `convert_channel`

Add a coordination-flag handler before the `dc.b` byte loop. Map per the spec table. Key cases (volume/transpose folding is Task 2.3; here emit the direct ones):

```python
def _handle_flag(kind, mnem, args, out, st, cfg):
    from song_packer import (Pan, Patch, ModSet, PsgEnv, NoteFill, End, Vol)
    if mnem == "smpsPan":
        if kind != "DAC":                       # FM-only; drop on DAC route
            out.append(Pan(resolve_const(args[0])))      # raw $B4 byte
    elif mnem in ("smpsSetvoice", "smpsFMvoice"):
        out.append(Patch(resolve_const(args[0])))        # remapped to v0 index in Task 7.1
    elif mnem == "smpsModSet":
        out.append(ModSet(resolve_const(args[0]), resolve_const(args[1]),
                          resolve_const(args[2]), resolve_const(args[3])))
    elif mnem in ("smpsModOff", "smpsStopSpecial"):
        out.append(ModSet(0, 0, 0, 0))
    elif mnem == "smpsPSGvoice":
        out.append(PsgEnv(resolve_const(args[0])))
    elif mnem == "smpsNoteFill":
        out.append(NoteFill(resolve_const(args[0]) * cfg.divider))
    elif mnem in ("smpsStop",):
        out.append(End())
    elif mnem == "smpsSetVol":
        st.volume = _smps_vol_to_v0(kind, resolve_const(args[0])); out.append(Vol(st.volume))
    # smpsDetune/smpsNoAttack: Task 2.4; smpsCall/Loop/Jump: Task 2.3; others: warn-skip
    else:
        return False
    return True
```

`_smps_vol_to_v0(kind, val)`: FM driver-v3 `smpsSetVol` stores a loud=high parameter → `v0 = min(127, val)`; PSG 4-bit attenuation → `v0 = int((15 - (val & 0x0F)) / 15 * 127)`. Pin both with a test.

Wire `_handle_flag` into `convert_channel`: for a non-`dc.b` mnemonic, call `_handle_flag`; if it returns `False`, `warn("skip flag %s" % mnem)`.

Add the DAC route: in the `dc.b` loop, when `kind == "DAC"`, a byte ≥ `$81` is a sample → `out.append(Dac(b & 0x7F))` (remap to the v0 table id happens in Task 7.1); a byte `< $80` is a duration (reuses prior sample) → `SetDur(b*divider)`; `$80` → `Rest()`.

- [ ] **Step 4: Run** → PASS.

- [ ] **Step 5: Commit**

```bash
git add tools/smps_import.py tools/test_smps_import.py
git commit -m "feat(tools): smps_import coordination-flag -> MEV mapping + DAC route"
```

### Task 2.3: Call-inline + loop-flatten + volume/transpose state

**Files:** Modify `tools/smps_import.py`; Test `tools/test_smps_import.py`

- [ ] **Step 1: Write the failing test**

```python
from song_packer import RepeatStart, RepeatEnd, Note, Patch

def test_call_inlines_body():
    blocks = {"Sub0": ["\tsmpsSetvoice $05", "\tsmpsReturn"]}
    cfg = _mkcfg(); st = ConvState()
    ev = convert_channel("FM", ["\tsmpsCall Sub0", "\tdc.b nC4"], blocks, cfg, st)
    assert isinstance(ev[0], Patch) and ev[0].patch == 0x05    # inlined from Sub0
    assert isinstance(ev[1], Note)

def test_loop_becomes_repeat():
    # smpsLoop index,count,target — body is the lines between target-label and the loop flag
    blocks = {}
    cfg = _mkcfg(); st = ConvState()
    ev = convert_channel("FM",
        ["LoopA:", "\tdc.b nC4", "\tsmpsLoop $00, $03, LoopA"], blocks, cfg, st)
    assert isinstance(ev[0], RepeatStart)
    assert isinstance(ev[1], Note)
    assert isinstance(ev[2], RepeatEnd) and ev[2].count == 3
```

(Add a `_mkcfg()` helper in the test returning a `SongConfig` with divider=1.)

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Implement call-inline + loop-flatten**

Refactor `convert_channel` to walk lines with an index, tracking in-channel labels for loop targets:
- `smpsCall L` → recursively convert `blocks[L]` (stop at `smpsReturn`) and splice the events in (guard against missing label → error; against recursion depth).
- A local `Label:` that is a loop target → emit `RepeatStart()`, remember the position; the matching `smpsLoop idx,count,Label` → emit `RepeatEnd(count)`. (HCZ2's loops are body-then-flag with an earlier target, well-nested — one level. If a loop target isn't immediately the prior block, fall back to unrolling `count` copies of the body and log it.)
- `smpsJump L` where `L` is the channel's own start (loop-back) → `LoopPoint()` at the start + `Jump()` here. Forward jumps → flatten/inline.
- `smpsSetNote v`/`smpsChangeTransposition v` → adjust `st.transpose` (no event).
- `smpsAlterVol v`/`smpsPSGAlterVol v` → `st.volume += signed(v)`; emit absolute `Vol(clamp(st.volume))`.

Keep each sub-behavior covered by the two tests above (extend with a transpose/vol test if helpful).

- [ ] **Step 4: Run** → PASS.

- [ ] **Step 5: Commit**

```bash
git add tools/smps_import.py tools/test_smps_import.py
git commit -m "feat(tools): smps_import call-inline + loop-flatten + transpose/vol state"
```

### Task 2.4: Detune → NOTE_RAW; same-pitch tie merge (legato)

**Files:** Modify `tools/smps_import.py`; Test `tools/test_smps_import.py`

- [ ] **Step 1: Write the failing test**

```python
from song_packer import NoteRaw, Note, NoteDur

def test_detune_emits_noteraw():
    # smpsAlterNote (detune) $04 then nC4 -> NOTE_RAW with detuned fnum, not plain Note
    ev = _conv("FM", ["\tsmpsAlterNote $04", "\tdc.b $0C, nC4"])
    assert any(isinstance(e, NoteRaw) for e in ev)

def test_same_pitch_tie_merges():
    # smpsNoAttack before a SAME-pitch note merges durations (one note), not two
    ev = _conv("FM", ["\tdc.b $0C, nC4", "\tsmpsNoAttack", "\tdc.b $0C, nC4"])
    notes = [e for e in ev if isinstance(e, (Note, NoteDur))]
    assert len(notes) == 1            # merged
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Implement detune + tie-merge**

- `smpsAlterNote v`/`smpsDetune v` → set `st.detune = signed(v)`; on the next note, compute `$A4/$A0` from the chromatic fnum + detune (mirror `zUpdateFreq`), emit `NoteRaw(a4, a0, dur)` instead of `Note`. Provide `_fnum_for(pitch_index, detune)` using the standard YM2612 fnum/block math (octave = index//12, semitone = index%12; base fnum table for one octave; `a4=(block<<3)|fnumHi`, `a0=fnumLo`; add detune to fnum). Pin `_fnum_for` with a unit test against two known indices.
- `smpsNoAttack` (`$E7`) → set `st.tie = True`; when emitting the next note, if `st.tie` and the new pitch == the previous emitted note's pitch, extend the previous note's duration (replace with `NoteDur(pitch, prev_dur+new_dur)`), else emit normally (accepted re-attack on a pitch-changing slur) and `warn` once.

- [ ] **Step 4: Run** → PASS.

- [ ] **Step 5: Commit**

```bash
git add tools/smps_import.py tools/test_smps_import.py
git commit -m "feat(tools): smps_import detune->NOTE_RAW + same-pitch tie merge"
```

---

## Phase 3 — SongDesc emission + end-to-end convert

### Task 3.1: Assemble channels → SongDesc → song_packer

**Files:** Modify `tools/smps_import.py`; Test `tools/test_smps_import.py`

- [ ] **Step 1: Write the failing test**

```python
from smps_import import convert_song
from song_packer import SongDesc, ChannelDesc, pack_song, CHROUTE_FM1, CHROUTE_DAC

def test_convert_song_roundtrips_through_packer():
    src = HCZ2_HEADER + [
        "Snd_HCZ2_DAC:", "\tdc.b dKickS3, $06", "\tsmpsStop",
        "Snd_HCZ2_FM1:", "\tsmpsSetvoice $0F", "\tdc.b $0C, nC4", "\tsmpsStop",
        "Snd_HCZ2_FM2:", "\tsmpsStop", "Snd_HCZ2_FM3:", "\tsmpsStop",
        "Snd_HCZ2_FM4:", "\tsmpsStop", "Snd_HCZ2_FM5:", "\tsmpsStop",
        "Snd_HCZ2_PSG1:", "\tsmpsStop", "Snd_HCZ2_PSG2:", "\tsmpsStop",
        "Snd_HCZ2_PSG3:", "\tsmpsStop",
    ]
    song = convert_song(src, dac_remap={6: 2, 1: 3}, patch_remap={0x0F: 0})
    assert isinstance(song, SongDesc)
    assert song.flags & 0x02                       # SH_F_STREAM
    routes = [c.route for c in song.channels]
    assert CHROUTE_FM1 in routes and CHROUTE_DAC in routes
    pack_song(song)                                # must not raise (packer validation passes)
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Implement `convert_song`**

```python
def convert_song(src_lines, dac_remap, patch_remap, pitchtable=None):
    from song_packer import (SongDesc, ChannelDesc, SH_F_STREAM,
        CHROUTE_FM1, CHROUTE_FM2, CHROUTE_FM3, CHROUTE_FM4, CHROUTE_FM5,
        CHROUTE_PSG1, CHROUTE_PSG2, CHROUTE_PSG3, CHROUTE_DAC, Dac, Patch, End)
    cfg = parse_header(src_lines)
    blocks = split_blocks(src_lines)
    route_for = {"DAC": [CHROUTE_DAC],
                 "FM": [CHROUTE_FM1,CHROUTE_FM2,CHROUTE_FM3,CHROUTE_FM4,CHROUTE_FM5],
                 "PSG":[CHROUTE_PSG1,CHROUTE_PSG2,CHROUTE_PSG3]}
    fm_i = psg_i = 0
    channels = []
    for ch in cfg.channels:
        st = ConvState(transpose=ch.transpose)
        ev = convert_channel(ch.kind, blocks.get(ch.label, []), blocks, cfg, st)
        # apply remaps
        for e in ev:
            if isinstance(e, Dac):  e.sample_id = dac_remap[e.sample_id]
            if isinstance(e, Patch): e.patch = patch_remap[e.patch]
        if not ev or not isinstance(ev[-1], End):
            ev.append(End())
        if ch.kind == "DAC": route = CHROUTE_DAC
        elif ch.kind == "FM": route = route_for["FM"][fm_i]; fm_i += 1
        else: route = route_for["PSG"][psg_i]; psg_i += 1
        # ensure FM emits Patch+Vol before first note; PSG emits Vol first (packer rule)
        channels.append(ChannelDesc(route, ev))
    return SongDesc(tempo=0x80, tempo_base=cfg.tempo_base,
                    flags=SH_F_STREAM, channels=channels, pitchtable=pitchtable)
```

Add the packer setup-order guards: if an FM channel's first event isn't `Patch`, inject the header voice's `Patch` (+ a default `Vol(100)`); for PSG inject a `Vol`. Pin with the packer not raising (the test calls `pack_song`).

- [ ] **Step 4: Run** → PASS.

- [ ] **Step 5: Commit**

```bash
git add tools/smps_import.py tools/test_smps_import.py
git commit -m "feat(tools): smps_import convert_song -> SongDesc (packer-valid)"
```

---

## Phase 4 — Voice (FM patch) conversion

### Task 4.1: S3K UVB voice → FmPatch bytes

**Files:** Modify `tools/smps_import.py`; Test `tools/test_smps_import.py`

- [ ] **Step 1: Write the failing test**

```python
from smps_import import smps_voice_to_fmpatch

def test_voice_byte_order_and_length():
    # one UVB voice in smpsVc* fields -> 26-byte FmPatch (alg/fb, lr_ams_fms, then 6 per-op groups)
    voice = {
        "alg": 0x04, "fb": 0x00, "lr_ams_fms": 0xC0,
        "dt_mul":  [0x71,0x31,0x71,0x31],   # S3K op order S1,S2,S3,S4
        "tl":      [0x1B,0x23,0x80,0x00],
        "rs_ar":   [0x5F,0x5F,0x5F,0x5F],
        "am_d1r":  [0x05,0x05,0x05,0x05],
        "d2r":     [0x02,0x02,0x02,0x02],
        "d1l_rr":  [0x1F,0x1F,0x1F,0x2F],
    }
    p = smps_voice_to_fmpatch(voice)
    assert len(p) == 26
    assert p[0] == 0x04          # fp_alg_fb
    assert p[1] == 0xC0          # fp_lr_ams_fms
    # op order remapped S1,S2,S3,S4 (SMPS) -> S1,S3,S2,S4 (engine)  [OP_REORDER]
    assert p[2:6] == bytes([0x71,0x71,0x31,0x31])   # dt_mul reordered
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Implement `smps_voice_to_fmpatch`**

```python
# SMPS stores per-op arrays in op order S1,S2,S3,S4; the engine FmPatch is S1,S3,S2,S4.
OP_REORDER = [0, 2, 1, 3]      # engine[i] = smps[OP_REORDER[i]]

def _reorder(arr):
    return [arr[OP_REORDER[i]] for i in range(4)]

def smps_voice_to_fmpatch(v):
    out = bytearray()
    out.append(v["alg"] | (v["fb"] << 3) if v.get("fb_shifted") is None else (v["alg"] | (v["fb"]<<3)))
    out.append(v["lr_ams_fms"])
    for key in ("dt_mul","tl","rs_ar","am_d1r","d2r","d1l_rr"):
        out.extend(_reorder(v[key]))
    assert len(out) == 26
    return bytes(out)
```

Note: confirm the `fp_alg_fb` packing (the engine expects `algorithm(0-2) | feedback(3-5)` in one byte). Adjust if the S3K voice already packs alg+fb. The `OP_REORDER=[0,2,1,3]` matches the SFX-transcoder operator swap (memory: SFX op-swap fix). Verify the byte order against an actual rendered voice in oracle (Task 8).

- [ ] **Step 4: Run** → PASS.

- [ ] **Step 5: Commit**

```bash
git add tools/smps_import.py tools/test_smps_import.py
git commit -m "feat(tools): smps_import UVB voice -> FmPatch (op reorder)"
```

### Task 4.2: Extract HCZ2's voices + emit `HCZ2_Patches`

**Files:** Modify `tools/smps_import.py`; Create `data/sound/movingtrucks-style hcz2_patches.asm` (generated by the converter)

- [ ] **Step 1:** Add a `parse_uvb_voices(driver_asm_path)` that reads the `smpsVc*` macro voices from `skdisasm/Sound/Z80 Sound Driver.asm` into `{voice_id: dict}`. Add `emit_patch_table(used_ids) -> asm_text` producing `HCZ2_Patches:` as `dc.b` rows (one `FmPatch` per used voice, in a stable order) + a `patch_remap = {smps_id: index}`. Test: parse the file, assert HCZ2's 5 ids (`$0F,$0A,$13,$0C` + reuse) resolve to 26-byte patches.

- [ ] **Step 2-5:** Run the test (FAIL→implement→PASS), commit:

```bash
git commit -m "feat(tools): smps_import extract UVB voices + emit HCZ2_Patches"
```

---

## Phase 5 — DAC kit import

### Task 5.1: Encode the 6 S3K drum WAVs → raw-8 PCM

**Files:** Create `tools/import_s3k_dac.py`; Test `tools/test_import_s3k_dac.py`

- [ ] **Step 1: Write the failing test**

```python
# tools/test_import_s3k_dac.py
import numpy as np
from import_s3k_dac import wav_to_raw8

def test_wav_to_raw8_centers_and_resamples(tmp_path):
    import wave, struct
    p = tmp_path / "t.wav"
    w = wave.open(str(p), "wb"); w.setnchannels(1); w.setsampwidth(1); w.setframerate(8000)
    w.writeframes(bytes([0x80, 0xFF, 0x00, 0x80] * 50)); w.close()
    out = wav_to_raw8(str(p), target_hz=18356)
    assert isinstance(out, (bytes, bytearray))
    assert all(0 <= b <= 255 for b in out)        # valid unsigned 8-bit
    assert len(out) > 0
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Implement `wav_to_raw8`** (load wav, to mono float, resample to `target_hz`, scale to unsigned 8-bit centered $80, reuse `dac_encode.encode_raw8`):

```python
# tools/import_s3k_dac.py
import os, sys, wave, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dac_encode import encode_raw8

def _read_wav_mono(path):
    w = wave.open(path, "rb"); n = w.getnframes(); sw = w.getsampwidth()
    ch = w.getnchannels(); sr = w.getframerate(); raw = w.readframes(n); w.close()
    dt = {1: np.uint8, 2: np.int16}[sw]
    a = np.frombuffer(raw, dtype=dt).astype(np.float64)
    if sw == 1: a = a - 128.0           # unsigned -> signed-ish, centered 0
    else:       a = a / 256.0           # 16-bit -> ~8-bit range
    if ch > 1: a = a.reshape(-1, ch).mean(axis=1)
    return a, sr

def wav_to_raw8(path, target_hz=18356):
    a, sr = _read_wav_mono(path)
    if sr != target_hz and len(a) > 1:
        idx = np.linspace(0, len(a) - 1, int(round(len(a) * target_hz / sr)))
        a = np.interp(idx, np.arange(len(a)), a)
    s = np.clip(np.round(a) + 0x80, 0, 255).astype(np.int32)
    return encode_raw8(s)
```

- [ ] **Step 4: Run** → PASS.

- [ ] **Step 5: Commit**

```bash
git add tools/import_s3k_dac.py tools/test_import_s3k_dac.py
git commit -m "feat(tools): S3K DAC wav -> raw8 (resample) importer"
```

### Task 5.2: Generate the 6 drum .pcm files + add to the DAC table

**Files:**
- Create: `data/sound/dac/s3k_kick.pcm`, `s3k_snare.pcm`, `s3k_hitom.pcm`, `s3k_midtom.pcm`, `s3k_lowtom.pcm`, `s3k_floortom.pcm` (generated)
- Modify: `data/sound/dac_samples.asm`, `engine/z80_sound_driver.asm` (`DacSampleTable`), `sound_constants.asm` (`DAC_SAMPLE_COUNT`)

- [ ] **Step 1:** Add a CLI to `import_s3k_dac.py` mapping the 6 S3K wav names → the 6 output `.pcm` files. Run it:

```bash
cd tools && python3 import_s3k_dac.py \
  --src "/home/volence/sonic_hacks/skdisasm/Sound/DAC" \
  --out ../data/sound/dac --rate 18356
```
Expected: 6 `.pcm` files written; print each name + byte length.

- [ ] **Step 2:** Add the 6 drums to `data/sound/dac_samples.asm` after `Dac_Hat_End:` (BINCLUDE each `.pcm`, `Dac_*_End:` labels, `SND_*_BANK/PTR/LEN` constants), inside the shared `$8000`-aligned bank. Confirm the bank-boundary `fatal` assert still passes (6 drums ≈ 15–20 KB; if the bank overflows 32 KB, move the S3K kit to its own `align $8000` bank).

- [ ] **Step 3:** Extend `DacSampleTable` in `engine/z80_sound_driver.asm` with descriptor ids 5–10 (the 6 S3K drums: `ds_bank/ds_rate(0)/ds_codec(0)/ds_ptr/ds_length/ds_loop_ofs(0)`), and bump `DAC_SAMPLE_COUNT` in `sound_constants.asm` to match. The `DacSampleTable` size assert pins this.

- [ ] **Step 4:** Define the `dac_remap` for the converter: `{S3K 1-based id → v0 DacSampleTable id}`, e.g. `dKickS3(6)→<kick id>`, `dSnareS3(1)→<snare id>`, `dHighTom(2)→…`, etc. Put it in `tools/smps_import.py` as `HCZ2_DAC_REMAP`.

- [ ] **Step 5: Commit**

```bash
git add data/sound/dac data/sound/dac_samples.asm engine/z80_sound_driver.asm sound_constants.asm tools/smps_import.py
git commit -m "feat(sound): import the 6 S3K HCZ2 drums into the DAC table"
```

---

## Phase 6 — Pitch table (conditional)

Default: use the engine-default chromatic `FmPitchTableZ` (no per-song table). Only if Task 8 reveals audible mistuning vs S3K, add Task 6.1:

### Task 6.1 (conditional): Generate a per-song pitch table from S3K frequencies

- [ ] Add `emit_pitch_table()` to the converter producing the 132-entry A4/A0 pages from S3K's `zFMFrequencies`/`zPSGFrequencies` math; pass it to `SongDesc(pitchtable=...)`. Verify pitch in oracle. Commit `feat(tools): per-song HCZ2 pitch table from S3K frequencies`.

---

## Phase 7 — Generate the song + wire it in

### Task 7.1: Run the converter → `song_hcz2.asm`

**Files:** Create `data/sound/song_hcz2.py` (driver script); Create `data/sound/song_hcz2.asm` + `data/sound/hcz2_patches.asm` (generated)

- [ ] **Step 1:** Write `data/sound/song_hcz2.py` that calls the converter on `skdisasm/.../HCZ2.asm` with `HCZ2_DAC_REMAP` + the patch remap, and `write_asm(song, "Song_HCZ2", "data/sound/song_hcz2.asm")` + writes `hcz2_patches.asm`.

```bash
cd /home/volence/sonic_hacks/aeon-hcz2 && python3 data/sound/song_hcz2.py
```
Expected: `song_hcz2.asm` + `hcz2_patches.asm` written; converter prints any warn-skips.

- [ ] **Step 2:** Eyeball `song_hcz2.asm` — sane channel count, the DAC track present, no obviously-broken `dc.b`. Commit:

```bash
git add data/sound/song_hcz2.py data/sound/song_hcz2.asm data/sound/hcz2_patches.asm
git commit -m "feat(sound): generate Song_HCZ2 from skdisasm SMPS"
```

### Task 7.2: Register the song + bank

**Files:** Modify `data/sound/song_table.asm`, `main.asm`

- [ ] **Step 1:** In `song_table.asm`: add `SONG_HCZ2 = 3`, bump `SONG_COUNT` (DEBUG) to 3, add `dc.l Song_HCZ2` to `SongTable` and `dc.l HCZ2_Patches` to `SongPatchTable`, keep the count asserts. In `main.asm`: include `song_hcz2.asm` + `hcz2_patches.asm` in HCZ2's own bank (mirror the Moving Trucks bank pattern; add a bank-fit assert).

- [ ] **Step 2: Commit**

```bash
git add data/sound/song_table.asm main.asm
git commit -m "feat(sound): register Song_HCZ2 (id 3) + bank"
```

### Task 7.3: DEBUG trigger (B button)

**Files:** Modify `engine/game_loop.asm`

- [ ] **Step 1:** In `Debug_MusicToggle`, add a `BUTTON_B` edge check (alongside C/START) that calls `Sound_PlayMusic` with `SONG_HCZ2` and sets `Dbg_Music_On`. Confirm `BUTTON_B ($10)` doesn't collide with A/C/START already handled.

```asm
        move.b  (Ctrl_1_Press).w, d0
        andi.b  #BUTTON_B, d0
        beq.s   .check_sample
        moveq   #SONG_HCZ2, d0
        bsr.w   Sound_PlayMusic
        move.b  #1, (Dbg_Music_On).w
        rts
```

- [ ] **Step 2: Commit**

```bash
git add engine/game_loop.asm
git commit -m "feat(sound): DEBUG B button plays Song_HCZ2"
```

---

## Phase 8 — Build + oracle verification

### Task 8.1: Build green

- [ ] **Step 1:** Ensure `tools/bin` is an ABSOLUTE symlink to the main checkout's `tools/bin`; copy `tools/salvador/salvador` if needed. Build:

```bash
cd /home/volence/sonic_hacks/aeon-hcz2 && \
  timeout 360 env SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh > /tmp/hcz2_build.log 2>&1; \
  echo EXIT=$?; grep -iE "error|fatal|Build complete" /tmp/hcz2_build.log | head
```
Expected: `EXIT=0`, `Build complete`. Fix any assembler errors (bank fit, DAC table size, song-table count) and re-build. Commit any fixes.

### Task 8.2: Oracle verification

- [ ] **Step 1:** Snapshot the ROM + listing to `/tmp` (watcher-immune), load into oracle, load symbols. Boot, press **B** (HCZ2). Run frames.

- [ ] **Step 2:** Capture a VGM over ~1 loop (`emulator_vgm_start`/`run_frames`/`vgm_stop`). Parse (reuse the DAC-phase VGM parser): confirm FM1–5 + PSG1–3 key-on activity, the DAC `$2A` drum stream with the HCZ2 rhythm, and the channel loop-backs. `audio_spectrum` per isolated channel (`set_channel_enabled`) for pitch spot-checks vs expected HCZ2 notes.

- [ ] **Step 3 (acceptance):** Listen (render the VGM to wav via the vgm2wav tooling, or judge by the spectrum/structure) — it must be **recognizably HCZ2** with the real drum kit. Document any audible fidelity gaps (slur re-attacks, dropped SSG-EG/vol-env, mistuning). If mistuned, do Task 6.1. If a voice sounds wrong, revisit Task 4.1 op-order/TL.

- [ ] **Step 4:** Update `docs/ENGINE_ARCHITECTURE.md` §6 (note the SMPS-import path + HCZ2 as a shipped test song) and the memory. Commit.

```bash
git commit -m "docs(sound): HCZ2 import verified in oracle + ARCH/memory sync"
```

### Task 8.3: Finish the branch

- [ ] Per superpowers:finishing-a-development-branch — verify all tests pass (`cd tools && python3 -m pytest test_smps_import.py test_import_s3k_dac.py -v`), build green, then FF-merge `feat/hcz2-import` → `master` (clean-FF check first; don't disturb the user's WIP).

---

## Self-review notes

- **Spec coverage:** converter (§4)→Phases 0–3; SMPS→MEV map (§5)→Tasks 2.1–2.4; voices (§6)→Phase 4; pitch (§6)→Phase 6; DAC kit (§6)→Phase 5; integration (§7)→Phase 7; testing (§8)→Phase 8. All covered.
- **Fidelity calls** (detune→NOTE_RAW, same-pitch tie merge, accepted slur re-attack, drop cosmetic flags) are in Task 2.4 + 2.2 with `warn` on skips.
- **Conditional Phase 6** is explicit (only if mistuned), not a placeholder.
- **Engine-change guard:** the only `.asm` edits are additive (DAC table, song table, main include, a DEBUG button) — no driver logic changes, matching the spec's "no engine changes."
