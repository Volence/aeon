#!/usr/bin/env python3
"""sfx_modulation_span_gate — SP-6e: does our engine reproduce S&K's pitch
trajectory across the spring's FIRST NOTE, from its onset to the voice change?

⚠ THIS FILE DOES NOT CLOSE THE OWNER'S REPORTED ARTEFACT. He described the spring
as "clipping between the first hit and where it changes". Clipping is an AMPLITUDE
character. What is established below is a PITCH-TIMING divergence and a KEY-CODE
divergence inside that span. Neither has been shown to be what he hears, and
nothing in this suite can show it: there is no audio instrument here (measured, not
assumed — the running oracle server's method table has no audio method at all), so
no file in this repo may claim to have heard the spring. The span is now KNOWN to
contain something of ours; whether it is HIS something needs his ear on an A/B.

THE SUBJECT. skdisasm's `B1 - Spring.asm` authors, on FM5:

    smpsModSet  $03, $01, $5D, $0F      ; wait 3, speed 1, delta +93, steps 15
    dc.b        nB3, $0A                ; ...on a 10-frame attacked note
    smpsModOff
    smpsSetvoice $01                    ; <- "where it changes"

so the span is exactly that note: ten frames carrying a deep upward pitch sweep,
ending at the voice change. The question is whether our sweep is S&K's sweep.

WHAT S3K ACTUALLY DOES, read out of the driver rather than out of our comments
(skdisasm `Sound/Z80 Sound Driver.asm`, cited by SYMBOL — the 2026-07-03 line
numbers in sfx_transcode.py's `_apply_s3k_modset_load_points` docstring were
re-checked against the file on 2026-09-09 and still land on their symbols):

  cfModulation           stores the modulation DATA POINTER and sets the on-flag.
  zPrepareModulation     loads wait/speed/delta into track RAM and seeds the step
                         count as `srl a` — HALF the authored count, so the first
                         half-period is half-length. Returns early on the no-attack
                         bit, which is the whole basis of the transcoder's
                         load-point pass. All four checks confirmed.
  zDoModulation          per frame: `dec ModulationWait / ret nz`, then `inc` it
                         back to 1 so it fires every frame thereafter; every
                         `ModulationSpeed` frames sign-extends ModulationDelta and
                         adds it to the 16-bit accumulator; then
                         `pop bc / add hl, bc` — A PLAIN 16-BIT ADD OF THE
                         ACCUMULATOR ONTO THE PACKED $A4$A0 WORD; then decrements
                         ModulationSteps, reloading it from `(iy+3)` (the FULL
                         authored count, NOT halved) and negating the delta.

  The transcoder docstring's model is CORRECT on every point it makes. It simply
  does not mention the two things this file is about, because neither is a
  load-point question: the plain 16-bit add, and the call ORDER.

  For THIS sound the load-point pass is a NO-OP anyway — the modSet is followed by
  an attacked note (`nB3`, bit 7 clear), so `attacked_follows` is true, the event is
  kept verbatim, and L3 below measures that it was.

THE TWO DIVERGENCES, both ours, both inside the span.

  (A) THE SWEEP IS ONE FRAME LATE.  S3K's note-on path is
      `zPrepareModulation / zUpdateFreq / zDoModulation / zFMSendFreq / zFMNoteOn`
      — modulation is stepped on the note-on frame itself, so the authored wait of
      3 elapses on note-on+2. Our per-frame order is the other way round:
      Sfx_Frame calls `ModUpdate` BEFORE `Sequencer_Channel`, so on the frame the
      note keys, ModUpdate has already run and Mod_ReArm's fresh wait=3 is not
      touched until the NEXT frame. Our first step lands on note-on+3.

      Consequence: the whole sweep is shifted 16.7 ms, and at equal frame index the
      rendered pitch differs by up to ~128 cents — more than a semitone, for the
      whole span. At the voice change itself S&K is one step PAST the sweep peak
      and coming down; we are AT the peak.

      This is a PITCH difference, not an amplitude one. L4 pins it at exactly one
      frame so it cannot quietly become two.

  (B) THE BLOCK RENORMALIZATION MOVES THE KEY CODE.  Where zDoModulation adds the
      accumulator to the whole packed word and lets the f-number climb inside its
      11-bit field, our Mod_Advance splits block from fnum, adds only to the fnum,
      and renormalizes: `fnum >= FNUM_HI -> fnum >>= 1, block++`. Halving the fnum
      while raising the block is the same chip PITCH — that is what
      Fm_FnumApplyDelta's comment says and it is true, to within the half-LSB the
      `srl h / rr l` truncates (<= 1.3 cents here).

      It is not the same KEY CODE. The YM2612 derives KC from the block and the top
      f-number bits, and KC drives both KSR (envelope rate scaling) and DT. Across
      this span S&K's KC is CONSTANT at 15; ours steps to 16 at the first
      modulation frame and 17 at the peak. The spring's carrier is KS=2, D1R=6,
      D2R=8, so +1 KC is +1 on the effective EG rate of both decays — a ~2^(1/4)
      faster carrier decay from the first modulation frame onward.

      So the answer to "does anything in that span move amplitude" is: no SEQUENCED
      event does (L2 measures that), but this does, indirectly, through KSR. The
      direction is QUIETER than S&K, which is the opposite character to clipping.
      Recorded because it was asked, not because it explains him.

THE LEGS. Every expectation is derived from the two drivers' own constants and
control flow; none is copied from a measurement of current behaviour.

  C1 THE INSTRUMENT IS LIVE   the SFX channel carrying the spring's own modulation
                              latches is located in Z80 RAM by those latches, is
                              unique, and its accumulator actually MOVES during the
                              window. A dead read, or a second matching block,
                              cannot pass as agreement.

  L1 THE ENGINE IS THE MODEL  the measured per-frame `sc_last_freq` series equals
                              this file's port of Mod_Advance driven at our call
                              order. Everything derived below is a claim about a
                              Python model; this leg is what licenses reading it as
                              a claim about the engine.

  L2 NO SEQUENCED AMPLITUDE   walking the SHIPPED stream from the modSet to the
     EVENT IN THE SPAN        modOff turns up no MEV_VOL / MEV_OPBIAS / MEV_PATCH /
                              MEV_FMENV / MEV_REGWRITE / MEV_REGDELTA. The span's
                              amplitude is the FM envelope alone.

  L3 THE TRANSCODE PRESERVED  the shipped blob's MEV_MODSET operands equal
     THE AUTHORED PROGRAM     skdisasm's four smpsModSet arguments, and the note it
                              precedes is ATTACKED — which is what makes the
                              load-point pass a no-op here.

  L4 THE LOAD LAG IS EXACTLY  measured (first accumulator move - note-on frame)
     ONE FRAME                == authored wait + 1, where the +1 is DERIVED from
                              Sfx_Frame's ModUpdate-before-Sequencer_Channel order,
                              read out of sound_sfx.emp so the pin tracks the
                              source rather than a remembered fact.

LOUD ON UNMEASURABLE. Every ambiguity raises Unmeasurable and exits 2. A run that
could not ask its question is NEVER reported as a pass.

RUN:  python3 tools/sfx_modulation_span_gate.py [--rom s4.debug.bin] [--lst s4.debug.lst]
Exit: 0 = all legs pass, 1 = a leg failed, 2 = could not measure.
"""
import argparse
import asyncio
import math
import os
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))
from suite_paths import add_client_path  # noqa: E402
add_client_path()
from aether import BusClient  # noqa: E402
from aether_instance import aether_emulator, read_bytes, unprefix  # noqa: E402


class Unmeasurable(RuntimeError):
    """The run could not ask its question — never reported as a pass."""


# The spring's drop, shared with tools/spring_sfx_witness.py: a real player meeting
# the real up spring in real level data, so the SFX under measurement is the one the
# game fires rather than one this file poked into a queue.
SPRING_X, SPRING_Y, DROP_HEIGHT = 160, 584, 96
SETTLE_FRAMES = 40
SAMPLE_FRAMES = 24          # comfortably spans the 10-frame note plus its approach


def find_skdisasm():
    """-> the S&K reference checkout, or None. Walks UP from here (a worktree sits
    several levels below the main checkout, so a fixed hop count would be wrong) and
    takes the first ancestor holding a `skdisasm` directory. `SKDISASM_DIR` overrides.
    Not found is Unmeasurable at the call site, never a pass."""
    env = os.environ.get("SKDISASM_DIR")
    if env:
        return Path(env)
    for anc in [REPO, *REPO.parents]:
        cand = anc / "skdisasm"
        if cand.is_dir():
            return cand
    return None


# --------------------------------------------------------------------------
# Derivation 1: the AUTHORED program, out of skdisasm's own source.
# --------------------------------------------------------------------------
def authored_program():
    """-> (wait, speed, delta, steps, note_name, duration) from `B1 - Spring.asm`."""
    sk = find_skdisasm()
    if sk is None:
        raise Unmeasurable(
            "no skdisasm checkout found (set SKDISASM_DIR) — the authored modulation "
            "program is the reference this gate compares against and cannot be guessed")
    src = sk / "Sound" / "SFX" / "B1 - Spring.asm"
    if not src.is_file():
        raise Unmeasurable(f"{src} does not exist")
    txt = src.read_text(errors="replace")
    m = re.search(r"smpsModSet\s+\$([0-9A-Fa-f]+),\s*\$([0-9A-Fa-f]+),"
                  r"\s*\$([0-9A-Fa-f]+),\s*\$([0-9A-Fa-f]+)", txt)
    if not m:
        raise Unmeasurable(f"no smpsModSet in {src.name} — this gate's subject is gone")
    wait, speed, delta, steps = (int(g, 16) for g in m.groups())
    # the note the modSet precedes: the first `dc.b nXX, $dd` AFTER the modSet
    tail = txt[m.end():]
    n = re.search(r"dc\.b\s+(n[A-G][sb]?\d)\s*,\s*\$([0-9A-Fa-f]+)", tail)
    if not n:
        raise Unmeasurable(f"no note follows the smpsModSet in {src.name}")
    return wait, speed, delta, steps, n.group(1), int(n.group(2), 16)


def smps_note_index(name):
    """-> the pitch index (0 = C0) for an SMPS note name, from skdisasm's OWN enum.

    The enum in `_smps2asm_inc.asm` is written with enharmonic aliases (`nDb0=nCs0`)
    that do NOT advance the counter, so it is walked rather than assumed to be
    twelve-per-line."""
    sk = find_skdisasm()
    inc = sk / "Sound" / "_smps2asm_inc.asm"
    if not inc.is_file():
        raise Unmeasurable(f"{inc} does not exist")
    val, table = None, {}
    for line in inc.read_text(errors="replace").splitlines():
        m = re.match(r"\s*enum\s+nRst\s*=\s*\$([0-9A-Fa-f]+)", line)
        if m:
            val = int(m.group(1), 16)
            table["nRst"] = val
            continue
        if re.match(r"\s*enum(conf)?\s", line):
            # a DIFFERENT enum block (the file opens with the smpsPitch ones and
            # closes with the PSG maxima). Only the nRst run is the note scale.
            if val is not None:
                break
            continue
        if not re.match(r"\s*nextenum\s", line):
            continue
        if val is None:
            continue                          # still inside an earlier enum block
        for tok in line.split(None, 1)[1].split(","):
            tok = tok.strip()
            if not tok:
                continue
            if "=" in tok:                    # alias: same value, no advance
                lhs, rhs = (t.strip() for t in tok.split("=", 1))
                if rhs not in table:
                    raise Unmeasurable(f"alias {tok} refers to unknown {rhs}")
                table[lhs] = table[rhs]
            else:
                val += 1
                table[tok] = val
    if name not in table:
        raise Unmeasurable(f"{name} is not in skdisasm's note enum")
    base = table.get("nC0")
    if base is None:
        raise Unmeasurable("_smps2asm_inc.asm has no nC0")
    return table[name] - base


# --------------------------------------------------------------------------
# Derivation 2: OUR side — opcodes, struct offsets, pitch table, shipped blob.
# --------------------------------------------------------------------------
CONSTS = REPO / "engine" / "sound" / "sound_constants.emp"
TABLES = REPO / "engine" / "sound" / "sound_tables_z80.emp"
SFXFRM = REPO / "engine" / "sound" / "sound_sfx.emp"


def emp_consts(names):
    """-> {name: int} for `pub const NAME = $hh` / `= 123` lines."""
    txt = CONSTS.read_text(errors="replace")
    out = {}
    for n in names:
        m = re.search(rf"^pub const {n}\s*=\s*\$?([0-9A-Fa-f]+)\b", txt, re.M)
        if not m:
            raise Unmeasurable(f"{n} is not a literal `pub const` in {CONSTS.name}")
        raw = m.group(1)
        out[n] = int(raw, 16) if "$" in m.group(0) else int(raw, 10)
    return out


def sfxchannel_offsets():
    """-> {field: byte offset} walked out of `pub struct SfxChannel`.

    The OFFSETS are the thing being derived: ModUpdate reaches these through
    (ix+d), so a field that moves must move this table with it. The struct's own
    trailing `// +NN` comments are NOT trusted — the widths are summed."""
    txt = CONSTS.read_text(errors="replace")
    m = re.search(r"pub struct SfxChannel \{(.*?)\n\}", txt, re.S)
    if not m:
        raise Unmeasurable(f"no `pub struct SfxChannel {{ ... }}` in {CONSTS.name}")
    off, out = 0, {}
    for fm in re.finditer(r"\n\s*(\w+):\s*(u8|u16|\[u8;\s*(\d+)\])", m.group(1)):
        out[fm.group(1)] = off
        off += 2 if fm.group(2) == "u16" else (int(fm.group(3)) if fm.group(3) else 1)
    need = ("sc_mod_ctrl", "sc_mod_wait", "sc_mod_speed", "sc_mod_delta",
            "sc_mod_steps", "sc_mod_speed_raw", "sc_mod_step_raw", "sc_mod_wait_raw",
            "sc_mod_delta_raw", "sc_mod_accum", "sc_base_freq", "sc_last_freq")
    missing = [n for n in need if n not in out]
    if missing:
        raise Unmeasurable(f"SfxChannel has no {missing}")
    out["__len__"] = off
    return out


def fm_pitch_word(index):
    """-> FmPitchTableZ[index], parsed from the generated Z80 table."""
    txt = TABLES.read_text(errors="replace")
    m = re.search(r"proc FmPitchTableZ \(\) clobbers\(\) \{(.*?)\n\s*\}", txt, re.S)
    if not m:
        raise Unmeasurable(f"no FmPitchTableZ body in {TABLES.name}")
    words = [int(w, 16) for w in re.findall(r"\$([0-9A-Fa-f]{4})", m.group(1))]
    if not 0 <= index < len(words):
        raise Unmeasurable(f"pitch index {index} outside FmPitchTableZ ({len(words)} entries)")
    return words[index]


def sfx_frame_order():
    """-> True iff Sfx_Frame calls ModUpdate BEFORE Sequencer_Channel.

    L4's `+1` is this fact and nothing else, so it is READ rather than remembered.
    An order this file cannot determine is Unmeasurable, never an assumed +1."""
    txt = SFXFRM.read_text(errors="replace")
    m = re.search(r"pub proc Sfx_Frame \(\).*?\n    \}", txt, re.S)
    if not m:
        raise Unmeasurable(f"no `pub proc Sfx_Frame` body in {SFXFRM.name}")
    body = m.group(0)
    a = body.find("call    ModUpdate")
    c = body.find("call    Sequencer_Channel")
    if a < 0 or c < 0:
        raise Unmeasurable(
            "Sfx_Frame no longer calls both ModUpdate and Sequencer_Channel — the "
            "one-frame lag this gate pins is derived from their ORDER and cannot be "
            "derived from a body that does not contain them")
    return a < c


# Operand byte counts for the opcodes this gate may walk. An opcode NOT in this
# table stops the walk with Unmeasurable rather than being skipped as one byte —
# a mis-walked stream would silently report "no amplitude event in the span".
FIXED_OPERANDS = {
    "MEV_VOL": 1, "MEV_PATCH": 1, "MEV_DAC": 1, "MEV_NOTE_DUR": 2, "MEV_PAN": 1,
    "MEV_REPEAT_START": 0, "MEV_REPEAT_END": 1, "MEV_NOTE_RAW": 3, "MEV_OPBIAS": 2,
    "MEV_PSGENV": 1, "MEV_MODSET": 4, "MEV_NOTEFILL": 1, "MEV_LOOP_POINT": 0,
    "MEV_JUMP": 0, "MEV_SPINREV": 0, "MEV_SPINREV_RESET": 0, "MEV_PSGNOISE": 1,
    "MEV_TEMPO": 1, "MEV_LFO": 1, "MEV_PORTA": 1, "MEV_DETUNE": 1, "MEV_FMENV": 1,
    "MEV_REGWRITE": 3, "MEV_MACRO": 2, "MEV_REST": 0, "MEV_END": 0,
}
# Opcodes that move a channel's AMPLITUDE. MEV_PATCH is here because a patch swap
# reloads every TL. MEV_REGDELTA/MEV_PITCHENV are variable-length and are refused
# outright rather than walked.
AMPLITUDE_OPS = ("MEV_VOL", "MEV_OPBIAS", "MEV_PATCH", "MEV_FMENV", "MEV_REGWRITE")


def load_blob(sfx_id):
    """-> (blob bytes, first FM channel's stream offset). Layout per
    tools/sfx_transcode.py: 8-byte SfxHeader then chcount 6-byte channel records
    {route, kind, cmd_hi, cmd_lo, voice_hi, voice_lo}."""
    p = REPO / "games/sonic4/data/sound/sfx" / f"sfx_{sfx_id:02X}.bin"
    if not p.is_file():
        raise Unmeasurable(f"{p} does not exist")
    blob = p.read_bytes()
    if len(blob) < 8:
        raise Unmeasurable(f"{p.name} is {len(blob)} B, shorter than its 8-byte header")
    chcount = blob[2]
    if chcount != 1:
        raise Unmeasurable(
            f"{p.name} declares {chcount} channels; this gate's subject is the single "
            "FM channel the spring authors and it will not guess which one to read")
    r = 8
    if r + 6 > len(blob):
        raise Unmeasurable(f"{p.name} declares a channel record it is too short to hold")
    return blob, (blob[r + 2] << 8) | blob[r + 3]


def walk_span(blob, start, ops):
    """Walk the stream from `start` to the SECOND MEV_MODSET.

    -> (modset_operands, (raw, index, duration, attacked), ops_in_span)
    `ops_in_span` names every opcode strictly between the two modSets."""
    inv = {v: k for k, v in ops.items() if k.startswith("MEV_")}
    i, first, note, seen = start, None, None, []
    while i < len(blob):
        op = blob[i]
        if op < ops["MEV_REST"]:
            # a BARE byte below MEV_REST is song_packer's SetDur (it encodes as the
            # raw tick count), so it is one byte with no operand and moves no level.
            if first is not None:
                seen.append("SetDur")
            i += 1
            continue
        if ops["MEV_NOTE_BASE"] <= op <= ops["MEV_NOTE_MAX"]:
            # a bare note (default duration): one byte, no operand
            if first is not None and note is None:
                # a bare note opcode carries no no-attack bit — the range itself is
                # the pitch index, so such a note is always an attack.
                note = (op, op - ops["MEV_NOTE_BASE"], None, True)
            i += 1
            continue
        name = inv.get(op)
        if name is None:
            raise Unmeasurable(f"stream byte ${op:02X} at +{i} is not a known opcode")
        if name in ("MEV_REGDELTA", "MEV_PITCHENV", "MEV_EXT"):
            raise Unmeasurable(
                f"{name} at +{i} is variable-length; this gate refuses to walk past an "
                "opcode whose width it cannot derive rather than mis-read the span")
        if name == "MEV_MODSET":
            if first is None:
                first = tuple(blob[i + 1:i + 5])
                if len(first) != 4:
                    raise Unmeasurable("stream ends inside the first MEV_MODSET")
                i += 5
                continue
            return first, note, seen
        if first is not None:
            seen.append(name)
            if name == "MEV_NOTE_DUR" and note is None:
                # MEV_NOTE_DUR's first operand is the PITCH INDEX itself, with bit 7
                # as S3K's no-attack flag (`smpsNoAttack`), not a note OPCODE.
                raw = blob[i + 1]
                note = (raw, raw & 0x7F, blob[i + 2], not (raw & 0x80))
        i += 1 + FIXED_OPERANDS[name]
    raise Unmeasurable("the stream ends without a second MEV_MODSET — the span this "
                       "gate measures (modSet .. modOff) is not in the shipped blob")


# --------------------------------------------------------------------------
# The two drivers' arithmetic, ported.
# --------------------------------------------------------------------------
def s8(v):
    return v - 256 if v & 0x80 else v


def s16(v):
    return v - 0x10000 if v & 0x8000 else v


def key_code(block, fnum):
    """YM2612 KC = block:N. N's two bits are the documented F11..F8 reduction; KC
    feeds KSR (envelope rate scaling) and the detune table."""
    f11 = (fnum >> 10) & 1
    f10 = (fnum >> 9) & 1
    f9 = (fnum >> 8) & 1
    f8 = (fnum >> 7) & 1
    n = (f11 << 1) | ((f11 & (f10 | f9 | f8)) | ((1 - f11) & f10 & f9 & f8))
    return (block << 2) | n


def phase_inc(block, fnum):
    """Relative pitch: the YM2612's phase increment before detune/multiple."""
    return (fnum << block) >> 1


class ModCore:
    """The arithmetic zDoModulation and Mod_Advance share, byte for byte: the
    wait countdown held at 1, the speed-gated sign-extended accumulate, and the
    steps countdown that reloads the FULL authored count and negates the delta."""

    def __init__(self, wait, speed, delta, steps):
        self.w_raw, self.s_raw, self.d_raw, self.t_raw = wait, speed, delta, steps
        self.wait, self.speed, self.delta = wait, speed, delta
        self.steps = steps >> 1            # zPrepareModulation's `srl a`
        self.accum = 0

    def tick(self):
        """One frame. -> True if this frame renders a word."""
        self.wait = (self.wait - 1) & 0xFF
        if self.wait:
            return False
        self.wait = 1
        self.speed = (self.speed - 1) & 0xFF
        if self.speed == 0:
            self.speed = self.s_raw
            self.accum = (self.accum + s8(self.delta)) & 0xFFFF
        return True

    def after_render(self):
        self.steps = (self.steps - 1) & 0xFF
        if self.steps == 0:
            self.steps = self.t_raw
            self.delta = (-self.delta) & 0xFF


def render_s3k(base, accum):
    """zDoModulation: `pop bc / add hl, bc` — a plain 16-bit add of the accumulator
    onto the PACKED word. The f-number climbs inside its own 11-bit field and the
    block is never touched."""
    return (base + s16(accum)) & 0xFFFF


def render_ours(base, accum, fnum_lo, fnum_hi):
    """Mod_Advance's `.fm` branch: split block from fnum, add only to the fnum, then
    a SINGLE-STEP renormalization back into [FNUM_LO, FNUM_HI), skipped at block 7
    (hi) and block 0 (lo) exactly as the engine skips it."""
    block, fnum = (base >> 11) & 7, base & 0x7FF
    fnum = (fnum + s16(accum)) & 0xFFFF
    if block != 7 and fnum >= fnum_hi:
        fnum >>= 1
        block += 1
    elif block != 0 and fnum < fnum_lo:
        fnum = (fnum << 1) & 0xFFFF
        block -= 1
    return ((block << 3) | ((fnum >> 8) & 0xFF)) << 8 | (fnum & 0xFF)


def series(base, prog, render, lag, frames, extra=()):
    """-> [(word, accum)] per frame, `lag` frames of silence first.

    `lag` is 0 for S3K (zDoModulation runs on the note-on frame, right after
    zPrepareModulation) and 1 for us (ModUpdate precedes Sequencer_Channel)."""
    m = ModCore(*prog)
    word, out = base, []
    for f in range(frames):
        if f >= lag and m.tick():
            word = render(base, m.accum, *extra)
            m.after_render()
        out.append((word, m.accum))
    return out


# --------------------------------------------------------------------------
# The live half.
# --------------------------------------------------------------------------
def parse_syms(lst):
    syms, equs = {}, {}
    for line in open(lst, errors="replace"):
        m = re.match(r"^EQU (\w+) = \$?([0-9A-Fa-f]+)", line)
        if m:
            equs[m.group(1)] = int(m.group(2), 16)
            continue
        m = re.match(r"^\(\d+\)\s+\d+/([0-9A-Fa-f]+)\s+:\s+(\w+):", line)
        if m:
            syms.setdefault(m.group(2), int(m.group(1), 16))
    return syms, equs


async def player_y(b, syms, equs):
    raw = bytes.fromhex(unprefix(await read_bytes(
        b, (syms["Player_1"] + equs["SST_y_pos"]) & 0xFFFFFF, 2)))
    v = int.from_bytes(raw, "big")
    return v - 0x10000 if v >= 0x8000 else v


async def z80_ram(b):
    r = await b.call("emulator/z80_read", {"addr": "0x0", "len": 0x2000})
    if "bytes" not in r:
        raise Unmeasurable(f"emulator/z80_read returned no `bytes` field: {r!r}")
    return bytes.fromhex(unprefix(r["bytes"]))


async def measure(sock, rom, lst, prog, off, out):
    """Boot, drop the player onto the spring, and sample the SFX channel's whole
    modulation block once per frame.

    -> [(frame, snapshot|None)], snapshot = dict of the mod fields that frame."""
    b = BusClient(socket_path=sock, client_id="modspan",
                  client_name="sfx_modulation_span_gate")
    await b.connect()
    await b.call("emulator/load_symbols", {"path": lst})
    syms, equs = parse_syms(lst)
    for need in ("Player_1", "Sound_PlaySFX"):
        if need not in syms:
            raise Unmeasurable(f"{need} is not in {lst} — wrong ROM/listing pair?")
    for need in ("SST_x_pos", "SST_y_pos", "SST_x_vel"):
        if need not in equs:
            raise Unmeasurable(f"{need} has no EQU in {lst}")

    await b.call("emulator/reset", {})
    await b.call("emulator/run_frames", {"frames": 240})
    y0 = await player_y(b, syms, equs)
    await b.call("emulator/run_frames", {"frames": 8})
    if await player_y(b, syms, equs) == y0:
        out.append(f"  player not falling at y={y0} — pressing B to leave debug-fly")
        await b.call("emulator/press", {"buttons": ["b"]})
        await b.call("emulator/run_frames", {"frames": 8})
        if await player_y(b, syms, equs) == y0:
            raise Unmeasurable(f"player still frozen at y={y0} after B — no physics here")
    await b.call("emulator/run_frames", {"frames": SETTLE_FRAMES})

    for field, val in (("SST_x_pos", SPRING_X << 16),
                       ("SST_y_pos", (SPRING_Y - DROP_HEIGHT) << 16),
                       ("SST_x_vel", 0)):
        await b.call("emulator/write_memory", {
            "addr": hex((syms["Player_1"] + equs[field]) & 0xFFFFFF),
            "bytes": "0x" + f"{val:08X}"})

    play = syms["Sound_PlaySFX"]
    r = await b.call("emulator/run_to", {"addr": hex(play), "maxFrames": 240})
    if not r.get("reached"):
        raise Unmeasurable(
            "Sound_PlaySFX was never entered during the drop — the spring fired no "
            "sound, so there is no modulation in flight to sample")

    # The channel is found by the spring's OWN four latched modulation parameters,
    # in their struct order. Nothing here computes a channel address: an address
    # would be a guess about a Z80 RAM layout no listing publishes.
    wait, speed, delta, steps = prog
    sig = bytes([speed, steps, wait, delta])
    sig_at = off["sc_mod_speed_raw"]
    if (off["sc_mod_step_raw"], off["sc_mod_wait_raw"], off["sc_mod_delta_raw"]) != \
            (sig_at + 1, sig_at + 2, sig_at + 3):
        raise Unmeasurable(
            "the four latched modSet parameters are no longer four consecutive "
            "SfxChannel bytes — the signature this gate locates the channel by is "
            "gone and it will not fall back to a hardcoded address")

    frames = []
    for fr in range(SAMPLE_FRAMES):
        await b.call("emulator/run_frames", {"frames": 1})
        ram = await z80_ram(b)
        hits = [i for i in range(len(ram) - len(sig)) if ram[i:i + len(sig)] == sig]
        if len(hits) > 1:
            raise Unmeasurable(
                f"frame {fr}: the modulation signature {sig.hex()} matches "
                f"{len(hits)} places in Z80 RAM ({[hex(h) for h in hits]}) — this gate "
                "cannot say which is the spring's channel")
        if not hits:
            frames.append((fr, None))
            continue
        base = hits[0] - sig_at
        if base < 0 or base + off["__len__"] > len(ram):
            raise Unmeasurable(f"frame {fr}: signature at ${hits[0]:04X} puts the "
                               "SfxChannel outside Z80 RAM")

        def u8(name):
            return ram[base + off[name]]

        frames.append((fr, {
            "addr": base,
            "ctrl": u8("sc_mod_ctrl"), "wait": u8("sc_mod_wait"),
            "speed": u8("sc_mod_speed"), "delta": u8("sc_mod_delta"),
            "steps": u8("sc_mod_steps"),
            # sc_mod_accum is written lo-then-hi (`ld (ix+n),l` / `ld (ix+n+1),h`)
            "accum": ram[base + off["sc_mod_accum"]] |
                     (ram[base + off["sc_mod_accum"] + 1] << 8),
            # sc_base_freq / sc_last_freq are written hi-then-lo (d = $A4, e = $A0)
            "base": (ram[base + off["sc_base_freq"]] << 8) |
                    ram[base + off["sc_base_freq"] + 1],
            "last": (ram[base + off["sc_last_freq"]] << 8) |
                    ram[base + off["sc_last_freq"] + 1],
        }))
    return frames


# --------------------------------------------------------------------------
def main_async(rom, lst, out):
    ops = emp_consts(["MEV_NOTE_BASE", "MEV_NOTE_MAX", "MEV_VOL", "MEV_PATCH",
                      "MEV_DAC", "MEV_NOTE_DUR", "MEV_PAN", "MEV_REPEAT_START",
                      "MEV_REPEAT_END", "MEV_NOTE_RAW", "MEV_PITCHENV", "MEV_OPBIAS",
                      "MEV_REGDELTA", "MEV_PSGENV", "MEV_MODSET", "MEV_NOTEFILL",
                      "MEV_LOOP_POINT", "MEV_JUMP", "MEV_SPINREV", "MEV_SPINREV_RESET",
                      "MEV_PSGNOISE", "MEV_TEMPO", "MEV_LFO", "MEV_PORTA", "MEV_DETUNE",
                      "MEV_FMENV", "MEV_REGWRITE", "MEV_MACRO", "MEV_EXT", "MEV_REST",
                      "MEV_END"])
    band = emp_consts(["FNUM_LO", "FNUM_HI"])
    fnum_lo, fnum_hi = band["FNUM_LO"], band["FNUM_HI"]
    off = sfxchannel_offsets()

    a_wait, a_speed, a_delta, a_steps, a_note, a_dur = authored_program()
    a_index = smps_note_index(a_note)
    out.append(f"  authored (skdisasm B1 - Spring.asm): smpsModSet "
               f"${a_wait:02X},${a_speed:02X},${a_delta:02X},${a_steps:02X} on "
               f"{a_note} (index {a_index}) for ${a_dur:02X} frames")

    syms, equs = parse_syms(lst)
    if "SFXID_SPRING" not in equs:
        raise Unmeasurable(f"SFXID_SPRING has no EQU in {lst} — the spring is not wired in")
    blob, stream_off = load_blob(equs["SFXID_SPRING"])
    shipped, note, span_ops = walk_span(blob, stream_off, ops)
    if note is None:
        raise Unmeasurable("no note between the two MEV_MODSETs — the span is empty")
    note_op, note_index, note_dur, note_attacked = note
    base = fm_pitch_word(note_index)
    block, fnum = (base >> 11) & 7, base & 0x7FF
    out.append(f"  shipped (sfx_{equs['SFXID_SPRING']:02X}.bin): MEV_MODSET "
               f"${shipped[0]:02X},${shipped[1]:02X},${shipped[2]:02X},${shipped[3]:02X}"
               f" then note ${note_op:02X} (index {note_index}) dur ${note_dur:02X}")
    out.append(f"  FmPitchTableZ[{note_index}] = ${base:04X} -> block {block}, fnum "
               f"{fnum}; band [FNUM_LO ${fnum_lo:03X}, FNUM_HI ${fnum_hi:03X})")

    prog = (shipped[0], shipped[1], shipped[2], shipped[3])
    dur = note_dur if note_dur is not None else a_dur
    s3k = series(base, prog, render_s3k, 0, dur)
    ours = series(base, prog, render_ours, 1, dur, extra=(fnum_lo, fnum_hi))
    ours_aligned = series(base, prog, render_ours, 0, dur, extra=(fnum_lo, fnum_hi))

    fails, legs = [], []

    # ---- L3 the transcode preserved the authored program ------------------
    if tuple(shipped) != (a_wait, a_speed, a_delta, a_steps):
        fails.append(f"L3: shipped MEV_MODSET {tuple(f'${v:02X}' for v in shipped)} != "
                     f"authored {tuple(f'${v:02X}' for v in (a_wait,a_speed,a_delta,a_steps))}")
    elif not note_attacked:
        fails.append(f"L3: the note after the modSet (operand ${note_op:02X}) carries "
                     f"the no-attack bit, so S3K would never LOAD this modSet and the "
                     f"whole span this gate measures is a different sound")
    elif note_index != a_index:
        fails.append(f"L3: shipped note index {note_index} != authored {a_index} ({a_note})")
    else:
        legs.append("L3 THE TRANSCODE PRESERVED THE AUTHORED PROGRAM: all four operands "
                    f"match and the note is attacked, so _apply_s3k_modset_load_points "
                    f"kept the event verbatim (its `attacked_follows` arm)")

    # ---- L2 no sequenced amplitude event in the span -----------------------
    amp = [n for n in span_ops if n in AMPLITUDE_OPS]
    if amp:
        fails.append(f"L2: the span carries amplitude event(s) {amp} — the note's level "
                     f"is not the FM envelope alone")
    else:
        legs.append(f"L2 NO SEQUENCED AMPLITUDE EVENT IN THE SPAN: the {len(span_ops)} "
                    f"opcode(s) between the two modSets are {span_ops or ['(none)']}; "
                    f"none of {list(AMPLITUDE_OPS)} is among them")

    # ---- the live half ----------------------------------------------------
    with aether_emulator(rom, symbols=lst) as sock:
        frames = asyncio.run(measure(sock, rom, lst, prog, off, out))

    live = [(f, s) for f, s in frames if s is not None]
    if not live:
        raise Unmeasurable(
            "the spring's modulation block was never found in Z80 RAM across "
            f"{SAMPLE_FRAMES} frames — nothing was measured")
    addrs = {s["addr"] for _, s in live}
    if len(addrs) != 1:
        raise Unmeasurable(f"the signature moved between {len(addrs)} addresses "
                           f"{[hex(a) for a in addrs]} during one run")
    accums = {s["accum"] for _, s in live}
    c1_dead = len(accums) < 2
    if c1_dead:
        fails.append(f"C1: sc_mod_accum held {accums} for every sampled frame — the "
                     f"accumulator never moved, so this instrument measured nothing")
    else:
        legs.append(f"C1 THE INSTRUMENT IS LIVE: one SfxChannel at Z80 ${addrs.pop():04X} "
                    f"carries the spring's latches across {len(live)} frames and its "
                    f"accumulator takes {len(accums)} distinct values")

    # note-on = the first sampled frame (Mod_ReArm has just seeded steps = raw>>1
    # and cleared the accumulator; the base word is latched).
    f0 = live[0][0]
    moved = [f for f, s in live if s["accum"] != 0]
    if not moved:
        fails.append("L4: the accumulator never left 0 — no load point to measure")
    else:
        measured_lag = moved[0] - f0
        # DERIVATION. `wait` counts DOWN and fires on the frame it reaches 0.
        #   S3K   zPrepareModulation seeds wait on the note-on frame and zDoModulation
        #         is called two lines later IN THAT SAME FRAME (:778-780), so one
        #         decrement is spent on note-on and the first step lands at
        #         note-on + (wait - 1).
        #   ours  Sfx_Frame runs ModUpdate BEFORE Sequencer_Channel, so on the frame
        #         the note keys ModUpdate has already run and Mod_ReArm's fresh wait
        #         is untouched. The countdown starts the NEXT frame and the first step
        #         lands at note-on + wait.
        # The divergence is the difference of those two, which is exactly 1 frame.
        if not sfx_frame_order():
            raise Unmeasurable(
                "Sfx_Frame no longer calls ModUpdate before Sequencer_Channel — the "
                "load point below is derived from that order and this gate will not "
                "assert a number it can no longer derive")
        ours_first = shipped[0]
        s3k_first = shipped[0] - 1
        if measured_lag != ours_first:
            fails.append(
                f"L4: the first accumulator move lands {measured_lag} frame(s) after "
                f"note-on; with an authored wait of {shipped[0]} and Sfx_Frame running "
                f"ModUpdate before Sequencer_Channel the countdown starts the frame "
                f"AFTER the re-arm, so it should be {ours_first}")
        else:
            legs.append(
                f"L4 THE LOAD LAG IS EXACTLY ONE FRAME: our first step is at note-on+"
                f"{measured_lag} (= the authored wait, because ModUpdate precedes "
                f"Sequencer_Channel in {SFXFRM.name} so the note-on frame spends no "
                f"decrement); S3K's zDoModulation runs in the note-on frame itself, so "
                f"its first step is at note-on+{s3k_first}. The sweep is one frame late")

    # ---- L1 the engine is the model ---------------------------------------
    # Compare the frames the note actually owns: from note-on for `dur` frames.
    meas = [s["last"] for f, s in live if f0 <= f < f0 + dur]
    model = [w for w, _ in ours]
    if len(meas) < dur:
        if c1_dead:
            fails.append(
                f"L1: not evaluated — only {len(meas)} of the note's {dur} frames "
                f"carried the channel, which is the same truncation C1 already failed on")
            meas = []
        else:
            raise Unmeasurable(
                f"only {len(meas)} of the note's {dur} frames were sampled")
    bad = [(i, m, p) for i, (m, p) in enumerate(zip(meas, model)) if m != p]
    if not meas:
        pass                              # already reported above
    elif bad:
        fails.append(
            f"L1: measured sc_last_freq diverges from the Mod_Advance model at "
            f"{len(bad)}/{dur} frames: " +
            ", ".join(f"fr{i}: chip ${m:04X} vs model ${p:04X}" for i, m, p in bad[:6]))
    else:
        legs.append(f"L1 THE ENGINE IS THE MODEL: all {dur} measured sc_last_freq words "
                    f"equal this file's Mod_Advance port driven at our call order")

    # ---- the report the legs exist to license ------------------------------
    out.append("")
    out.append("  S&K vs ours across the span (aligned — the block renormalization alone):")
    out.append(f"    {'idx':>3}  {'S&K blk/fnum':>16} {'KC':>3}   {'ours blk/fnum':>16} "
               f"{'KC':>3}   {'cents':>6}")
    max_cents, kc_delta = 0.0, set()
    for i in range(dur):
        b1, n1 = (s3k[i][0] >> 11) & 7, s3k[i][0] & 0x7FF
        b2, n2 = (ours_aligned[i][0] >> 11) & 7, ours_aligned[i][0] & 0x7FF
        c = 1200 * math.log2(phase_inc(b2, n2) / phase_inc(b1, n1))
        k1, k2 = key_code(b1, n1), key_code(b2, n2)
        max_cents = max(max_cents, abs(c))
        kc_delta.add(k2 - k1)
        out.append(f"    {i:>3}  {b1}/{n1:>4} (${s3k[i][0]:04X}) {k1:>3}   "
                   f"{b2}/{n2:>4} (${ours_aligned[i][0]:04X}) {k2:>3}   {c:>6.2f}")
    out.append(f"    -> pitch agrees to {max_cents:.2f} cents (the `srl h / rr l` "
               f"half-LSB); KEY CODE differs by {sorted(kc_delta)}")
    out.append("")
    out.append("  S&K vs ours AS SHIPPED (our sweep one frame later):")
    worst = 0.0
    for i in range(dur):
        b1, n1 = (s3k[i][0] >> 11) & 7, s3k[i][0] & 0x7FF
        b2, n2 = (ours[i][0] >> 11) & 7, ours[i][0] & 0x7FF
        c = 1200 * math.log2(phase_inc(b2, n2) / phase_inc(b1, n1))
        worst = max(worst, abs(c))
        out.append(f"    fr{i:>2}  S&K {b1}/{n1:>4} KC{key_code(b1,n1):<3}  "
                   f"ours {b2}/{n2:>4} KC{key_code(b2,n2):<3}  {c:>+8.1f} cents")
    out.append(f"    -> the shipped sweep is off by up to {worst:.0f} cents at equal "
               f"frame index, entirely because of the one-frame lag")
    out.append("")
    out.append("  ⚠ NEITHER divergence has been shown to be the artefact the owner "
               "reported. He described an AMPLITUDE character ('clipping'); the lag is "
               "pitch, and the key-code shift moves the carrier's decay in the QUIETER "
               "direction. There is no audio instrument in this suite and this gate did "
               "not hear anything.")
    return fails, legs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", default=str(REPO / "s4.debug.bin"))
    ap.add_argument("--lst", default=str(REPO / "s4.debug.lst"))
    a = ap.parse_args()
    out = [f"sfx_modulation_span_gate [{Path(a.rom).name}]:"]
    try:
        fails, legs = main_async(a.rom, a.lst, out)
    except Unmeasurable as e:
        print("\n".join(out))
        print(f"  UNMEASURABLE: {e}")
        return 2
    for line in legs:
        out.append(f"  {line}")
    print("\n".join(out))
    if fails:
        print(f"  FAIL ({len(fails)} of {len(fails)+len(legs)} legs):")
        for f in fails:
            print(f"    {f}")
        return 1
    print(f"  OK ({len(legs)} legs)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
