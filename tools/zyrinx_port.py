#!/usr/bin/env python3
"""zyrinx_port — transcode the decoded "Moving Trucks" (The Adventures of Batman
& Robin, Zyrinx "Advanced Z80 Player", music Jesper Kyd) into our v0 music
format (a song_packer SongDesc).

This is BUILD-PC tooling: it reads the already-decoded song JSON
(`megadaw_export/05_Moving_Trucks.json`) and emits an AS data file the engine
includes. No driver code is ported — only data is translated.

----------------------------------------------------------------------------
Mapping decisions (Sound 1D Task 1; calibrated against the reference VGM in T5)
----------------------------------------------------------------------------

NOTE.  Zyrinx note values are MIDI-style (octave = note//12, semitone =
note%12).  Our pitch index = MIDI - 12 (semitone 0 = C0).  The decoded JSON
already carries raw note values; the candidate calibration is "Zyrinx note 0 =
C0 = MIDI 12 = our index 0", i.e. our index == note value.  OCTAVE_BASE_OFFSET
captures any whole-octave correction T5 finds against the VGM; it is 0 now.
  our_pitch = note + pattern.pitch_transpose + OCTAVE_BASE_OFFSET, clamped 0..0x5E.

TEMPO.  Moving Trucks format code = 56 ($38) -> 60*16/56 ~= 17.14 events/sec.
Our tick clock is YM Timer A: N = tempo<<2, period = 18.773us*(1024-N), rate =
1/period.  At tempo 0 (N=0) the rate is ALREADY ~52 Hz — Timer A CANNOT tick as
slowly as 17 Hz (its floor is ~52 Hz).  So the tempo byte pins to the floor (0)
and wall-clock fidelity comes from the DURATION_SCALE factor below.  (T5 may
re-pin both against the VGM onset timing.)

DURATION.  The decoder resolved each `wait` into `frames` = the number of
original event-slots the note/rest is held.  One original event-slot ~= 1/17.14
sec; our tick ~= 1/52 sec.  So a frame spans DURATION_SCALE = round(52/17.14) =
3 of our ticks.  our_dur = frames * DURATION_SCALE (notes use NoteDur, dur<=255;
the largest wait is 63 frames -> 189 <= 255, fits).

STRUCTURE.  Fully unrolling the repeats is ~50,900 events (~100KB).  Instead each
pattern's sequence body is emitted ONCE wrapped in MEV_REPEAT_START..
MEV_REPEAT_END(repeat) so the song stays ~8KB.  Each channel is wrapped in
LoopPoint()..Jump() (song header loop_point = 0 -> loop the whole pattern list).

CHANNELS.  The JSON's channels[] 16-per-channel split is approximate (the real
per-YM-voice assignment was set by the game's 68K loader, not in the song
binary).  T1 uses channels[] as-is: ch0-5 are the 6 active FM voices, ch6 is a
1-pattern stub (DROPPED + logged).  We have only 5 sequencer FM routes today
(FM1..FM5); the 6th FM voice (ch5) is HELD ASIDE for T3's adaptive FM6 slot.  So
T1 ships ch0-4 -> FM1..FM5; ch5 is logged as deferred.

VOICES / PAN / VOLUME.  T1 stubs voices to Patch(0) (a leading setup patch so the
packer accepts the FM channel) and DROPS pan/volume/fm_op/flag/ch_select events.
Real voice translation is T2; pan + volume dynamics are T4.
"""

import json
import sys


# --- Calibration constants (pinned now; T5 re-calibrates against the VGM) ---
OCTAVE_BASE_OFFSET = 0           # whole-octave correction (note == our index)
DURATION_SCALE = 3               # our ticks per original frame (~52/17.14)
ZYRINX_FORMAT_MOVING_TRUCKS = 56  # header format code ($38)

# Our pitch index range (mirror of song_packer.MAX_PITCH = MEV_NOTE_MAX-BASE).
MAX_PITCH = 0x5E

# Our v0 NoteDur duration field is a single byte.
MAX_DUR = 0xFF

# Timer-A constants for the tempo math (mirror sound_constants.asm).
_TIMERA_PERIOD_NS = 18773         # 18.773 us per Timer-A count tick (NTSC)

# --- Voice translation constants (Sound 1D Task 2) -------------------------
# Our FmPatch is a 26-byte record (sound_constants.asm + data/sound/fm_patches.inc):
#   fp_alg_fb ($B0), fp_lr_ams_fms ($B4), then six 4-byte per-operator arrays for
#   regs $30/$40/$50/$60/$70/$80 (dt_mul, tl, ks_ar, am_d1r, d2r, sl_rr), with
#   array index 0..3 = PHYSICAL register order [S1,S3,S2,S4].
FMPATCH_LEN = 26

# Zyrinx voices store operators in NATURAL order op1,op2,op3,op4 (indices
# 0,1,2,3). Our FmPatch arrays are in PHYSICAL register order S1,S3,S2,S4. The
# reorder maps natural -> physical: our_group = [g[0], g[2], g[1], g[3]] =
# natural indices [0,2,1,3]. CALIBRATED against the original VGM's voice-load
# register writes in T5 — kept as a named constant so T5 can flip it if the VGM
# shows otherwise.
OP_REORDER = [0, 2, 1, 3]

# The six per-operator group keys in our FmPatch emit order (regs $30..$80).
_VOICE_GROUP_KEYS = ("dt_mul", "tl", "ks_ar", "am_d1r", "d2r", "sl_rr")

# YM2612 reg-$B4 L/R (panning) bits. If neither is set the channel is silent, so
# force L/R=11 to make the voice audible.
_LR_MASK = 0xC0


def translate_voice(v: dict) -> bytes:
    """Translate a parsed Zyrinx voice (voices.json["bank1"][i]) into our 26-byte
    FmPatch record.

    - fp_alg_fb     = ((fb & 7) << 3) | (algo & 7).
    - fp_lr_ams_fms = ams_fms_pan, but if its L/R bits (6-7) are NOT both set,
      force L/R=11 (| $C0) so the channel is audible.
    - Each of the six op groups (dt_mul, tl, ks_ar, am_d1r, d2r, sl_rr) is
      reordered from Zyrinx natural [op1,op2,op3,op4] to our physical
      [S1,S3,S2,S4] via OP_REORDER = [0,2,1,3].
    - ext[4] is dropped.
    """
    alg_fb = ((v["fb"] & 7) << 3) | (v["algo"] & 7)

    lr_ams_fms = v["ams_fms_pan"] & 0xFF
    if (lr_ams_fms & _LR_MASK) != _LR_MASK:
        lr_ams_fms |= _LR_MASK

    out = bytearray((alg_fb, lr_ams_fms))
    for key in _VOICE_GROUP_KEYS:
        g = v[key]
        out.extend((g[OP_REORDER[0]] & 0xFF, g[OP_REORDER[1]] & 0xFF,
                    g[OP_REORDER[2]] & 0xFF, g[OP_REORDER[3]] & 0xFF))
    assert len(out) == FMPATCH_LEN
    return bytes(out)


def _load_voice_bank(voices_json_path: str) -> list:
    """Load the Zyrinx bank-1 voice list (Moving Trucks references bank 1)."""
    with open(voices_json_path) as f:
        return json.load(f)["bank1"]


def collect_song_voices(raw: dict) -> list:
    """Return the distinct absolute voice indices the song references, in
    FIRST-SEEN order (channel-then-pattern-then-event scan). Determines the dense
    local bank order + the voice_idx -> local_idx remap."""
    seen = set()
    order = []
    sequences = raw["sequences"]
    for ch in raw["channels"]:
        for pat in ch.get("patterns", []):
            seq = sequences.get(str(pat["seq_idx"]))
            if seq is None:
                continue
            for ev in seq["events"]:
                if ev["type"] == "voice":
                    idx = ev["index"]
                    if idx not in seen:
                        seen.add(idx)
                        order.append(idx)
    return order


def build_patch_bank(raw: dict, voices_json_path: str):
    """Build the per-song dense FmPatch bank + the voice_idx -> local_idx remap.

    Collects the distinct voice indices the song uses (first-seen order),
    translates each Zyrinx bank-1 voice to a 26-byte FmPatch, and packs them into
    a contiguous bank. Returns (bank_bytes, remap, count) where bank_bytes is
    count*26 bytes, remap maps absolute voice index -> dense local index 0..N-1,
    and count == N.
    """
    bank = _load_voice_bank(voices_json_path)
    order = collect_song_voices(raw)
    remap = {}
    out = bytearray()
    for voice_idx in order:
        remap[voice_idx] = len(remap)
        out.extend(translate_voice(bank[voice_idx]))
    return bytes(out), remap, len(remap)


# Per-FmPatch group layout for the emitter: (struct field name, group label).
# Matches the six 4-byte arrays + the two scalar leads (alg_fb, lr_ams_fms).
_PATCH_GROUP_LABELS = (
    "fp_dt_mul  $30", "fp_tl      $40", "fp_rs_ar   $50",
    "fp_am_d1r  $60", "fp_d2r     $70", "fp_d1l_rr  $80",
)


def emit_patch_bank_asm(bank_bytes: bytes, remap: dict, count: int,
                        label: str = "MovingTrucks_Patches") -> str:
    """Emit the per-song FmPatch bank as an AS data file using the `pbyte`
    single-source pattern (decimal literals through a CPU-agnostic macro), so the
    SAME file can be included in BOTH the 68k ROM data area AND inline in the Z80
    blob (no dc.b/db drift). Layout: `label:` + N FmPatch records (26 bytes each,
    one record per voice, groups commented) + `label_End:` + PATCH_COUNT_MT = N +
    a count + size assert (the loader points SND_SEQ_PATCHTAB at `label`)."""
    assert len(bank_bytes) == count * FMPATCH_LEN
    # Invert remap (local_idx -> absolute voice idx) for record comments.
    local_to_voice = {li: vi for vi, li in remap.items()}

    L = []
    L.append("; ======================================================================")
    L.append("; data/sound/%s.asm — GENERATED by tools/zyrinx_port.py — DO NOT EDIT." % label.lower())
    L.append(";")
    L.append("; Per-song FmPatch bank for \"Moving Trucks\" (Zyrinx bank 1 voices,")
    L.append("; translated to our 26-byte FmPatch by translate_voice()). The song's")
    L.append("; VOICE events were remapped to DENSE local indices 0..%d; the FM writer" % (count - 1))
    L.append("; reads a record via Fm_PatchLoad at SND_SEQ_PATCHTAB + local_idx*26.")
    L.append(";")
    L.append("; SINGLE SOURCE / DUAL-INCLUDABLE: emitted through the `pbyte` macro (picks")
    L.append("; dc.b for 68k ROM vs db for the Z80 phase-0 blob), so this one file can be")
    L.append("; included in the ROM data area OR inline in the Z80 blob with no drift.")
    L.append("; The recommended placement (T5) is INLINE in the Z80 blob: the bank is")
    L.append("; %d records * %d bytes = %d bytes, always Z80-addressable (no $8000 banking)." % (count, FMPATCH_LEN, count * FMPATCH_LEN))
    L.append(";")
    L.append("; Record: fp_alg_fb=$B0, fp_lr_ams_fms=$B4, then 6 four-byte per-op arrays")
    L.append("; for regs $30/$40/$50/$60/$70/$80, array index 0..3 = PHYSICAL operators")
    L.append("; S1,S3,S2,S4 (Zyrinx natural op order reordered via OP_REORDER=[0,2,1,3]).")
    L.append("; ======================================================================")
    L.append("")
    # Self-contained pbyte macro (ifndef-guarded; identical to fm_patches.inc so
    # including both files in the same context is safe).
    L.append("        ifndef pbyte_defined")
    L.append("pbyte_defined = 1")
    L.append("pbyte   macro                           ; emit data byte(s); CPU-correct directive")
    L.append("        if MOMCPUNAME=\"Z80\"")
    L.append("        db      ALLARGS                  ; Z80 phase-0 blob context")
    L.append("        else")
    L.append("        dc.b    ALLARGS                  ; 68k ROM context")
    L.append("        endif")
    L.append("        endm")
    L.append("        endif")
    L.append("")
    L.append("PATCH_COUNT_MT = %d" % count)
    L.append("")
    L.append("%s:" % label)
    for li in range(count):
        rec = bank_bytes[li * FMPATCH_LEN:(li + 1) * FMPATCH_LEN]
        vi = local_to_voice[li]
        L.append("; --- local %d (Zyrinx bank1 voice %d) ---" % (li, vi))
        L.append("        pbyte   %-3d                     ; fp_alg_fb     $%02X" % (rec[0], rec[0]))
        L.append("        pbyte   %-3d                     ; fp_lr_ams_fms $%02X" % (rec[1], rec[1]))
        for gi, glabel in enumerate(_PATCH_GROUP_LABELS):
            off = 2 + gi * 4
            g = rec[off:off + 4]
            L.append("        pbyte   %3d, %3d, %3d, %3d   ; %s  [S1,S3,S2,S4]"
                     % (g[0], g[1], g[2], g[3], glabel))
    L.append("%s_End:" % label)
    L.append("")
    L.append("        if (%s_End-%s)/FmPatch_len <> PATCH_COUNT_MT" % (label, label))
    L.append("          error \"Moving Trucks patch bank count mismatch\"")
    L.append("        endif")
    L.append("        if (%s_End-%s) <> PATCH_COUNT_MT*FmPatch_len" % (label, label))
    L.append("          error \"Moving Trucks patch bank size mismatch\"")
    L.append("        endif")
    L.append("")
    return "\n".join(L) + "\n"


def write_patch_bank_asm(raw: dict, voices_json: str, out_path: str,
                         label: str = "MovingTrucks_Patches"):
    """Build + write the per-song FmPatch bank .asm. Returns (remap, count)."""
    bank_bytes, remap, count = build_patch_bank(raw, voices_json)
    with open(out_path, "w") as f:
        f.write(emit_patch_bank_asm(bank_bytes, remap, count, label))
    return remap, count


# Import the packer event helpers. Support both `import zyrinx_port` (tools/ on
# path) and `from tools import zyrinx_port` styles.
try:
    from song_packer import (
        SongDesc, ChannelDesc,
        Note, NoteDur, Rest, SetDur, Patch, Vol, LoopPoint, Jump,
        RepeatStart, RepeatEnd,
        CHROUTE_FM1, CHROUTE_FM5,
    )
except ImportError:  # pragma: no cover - alternate import path
    from tools.song_packer import (  # type: ignore
        SongDesc, ChannelDesc,
        Note, NoteDur, Rest, SetDur, Patch, Vol, LoopPoint, Jump,
        RepeatStart, RepeatEnd,
        CHROUTE_FM1, CHROUTE_FM5,
    )


# --- Pure mapping functions ------------------------------------------------

def zyrinx_note_to_pitch(note: int, transpose: int = 0,
                         offset: int = OCTAVE_BASE_OFFSET) -> int:
    """Zyrinx note value -> our pitch index, clamped to 0..MAX_PITCH.

    our_pitch = note + transpose + offset (offset defaults to the pinned
    OCTAVE_BASE_OFFSET). Identity when transpose/offset are 0.
    """
    p = note + transpose + offset
    if p < 0:
        return 0
    if p > MAX_PITCH:
        return MAX_PITCH
    return p


def _timera_rate_hz(tempo_byte: int) -> float:
    """YM Timer-A overflow rate for a tempo byte (N = tempo<<2)."""
    n = tempo_byte << 2
    period_ns = (1024 - n) * _TIMERA_PERIOD_NS
    return 1e9 / period_ns


def zyrinx_tempo_to_byte(format_code: int, tempo_delta: int = 0) -> int:
    """Zyrinx format code (+ optional pattern tempo_delta) -> our Timer-A tempo
    byte, chosen so our tick rate is as close as Timer A can get to the
    original's events/sec.

    events/sec = 60*16 / (format_code + tempo_delta)  (Zyrinx; +delta = slower).
    Timer-A rate floor is ~52 Hz (tempo 0), so a slow song like Moving Trucks
    (~17 Hz) pins to the floor; DURATION_SCALE makes up the wall-clock timing.
    """
    base = format_code + tempo_delta
    if base <= 0:
        base = 1
    target_hz = (60 * 16) / base
    best_byte, best_err = 0, None
    for tb in range(0, 256):
        err = abs(_timera_rate_hz(tb) - target_hz)
        if best_err is None or err < best_err:
            best_byte, best_err = tb, err
    return best_byte


def wait_to_dur(frames: int) -> int:
    """Zyrinx `wait` frame count -> our duration ticks (frames * DURATION_SCALE,
    clamped to the NoteDur byte range)."""
    d = frames * DURATION_SCALE
    if d > MAX_DUR:
        return MAX_DUR
    if d < 0:
        return 0
    return d


# --- Loading + flattening --------------------------------------------------

def load_song(json_path: str) -> dict:
    """Load the decoded Moving Trucks JSON (the transcoder input)."""
    with open(json_path) as f:
        return json.load(f)


def _channel_first_voice(channel: dict, sequences: dict):
    """Return the FIRST voice index this channel references (channel's leading
    setup uses it as the initial Patch), or None if it has no voice event."""
    for pat in channel.get("patterns", []):
        seq = sequences.get(str(pat["seq_idx"]))
        if seq is None:
            continue
        for ev in seq["events"]:
            if ev["type"] == "voice":
                return ev["index"]
    return None


def _flatten_sequence_body(seq: dict, transpose: int, voice_remap=None) -> list:
    """Translate ONE resolved sequence's events into v0 events (the body that a
    RepeatStart/RepeatEnd wraps).

    Model (validated against the decoded data): events come in
    [pitch, voice?, fm_op*, wait] groups. `pitch` sets the pending note; the
    following `wait frames=N` emits NoteDur(pitch, N) (or Rest if no pitch is
    pending). The `loop` event terminates the body (we stop consuming there).

    voice_remap: None -> T1 behavior (voice events DROPPED). A dict
    (voice_idx -> local patch index) -> T2 behavior: a `voice` event emits
    Patch(local_idx) inline (so a mid-song instrument change re-loads the voice).
    pan/volume/fm_op/flag/ch_select are still dropped (pan/vol -> T4).
    """
    out = []
    pending = None          # pending pitch index awaiting its wait duration
    clamps = 0
    for ev in seq["events"]:
        t = ev["type"]
        if t in ("pitch", "note"):
            # Single-pitch only in Moving Trucks (no chords). Take pitch[0].
            raw = ev["pitches"][0]
            mapped = zyrinx_note_to_pitch(raw, transpose)
            if (raw + transpose + OCTAVE_BASE_OFFSET) != mapped:
                clamps += 1
            pending = mapped
        elif t == "wait":
            dur = wait_to_dur(ev["frames"])
            if pending is not None:
                out.append(NoteDur(pending, dur))
                pending = None
            else:
                # No active note -> a rest for this duration.
                out.append(SetDur(min(dur, 0x7F)))
                out.append(Rest())
        elif t == "voice":
            # T2: re-load the voice as an FmPatch by its dense local index.
            # T1 (voice_remap is None): dropped (voices stubbed).
            if voice_remap is not None:
                out.append(Patch(voice_remap[ev["index"]]))
        elif t == "loop":
            break               # body terminator
        else:
            # pan / volume / fm_op / flag / ch_select / param / reset / ch_off —
            # all dropped here (pan/vol dynamics -> T4).
            continue
    return out, clamps


def flatten_channel(channel: dict, sequences: dict, route: int,
                    voice_remap=None) -> list:
    """Flatten one JSON channel into a v0 event list:
        [Patch(p0), Vol(100),]?  LoopPoint, (RepeatStart, body, RepeatEnd(n))*, Jump

    FM routes get a leading Patch+Vol(100) setup so the packer's "FM keys a note
    before Patch+Vol" guard is satisfied. The setup Patch is:
      - voice_remap is None (T1): Patch(0) placeholder.
      - voice_remap given (T2): Patch(local_idx of the channel's FIRST voice),
        or Patch(0) if the channel references no voice.
    """
    events = []
    is_fm = (CHROUTE_FM1 <= route <= CHROUTE_FM5)
    if is_fm:
        setup_patch = 0
        if voice_remap is not None:
            first = _channel_first_voice(channel, sequences)
            if first is not None:
                setup_patch = voice_remap[first]
        events.append(Patch(setup_patch))   # initial voice (T2) / placeholder (T1)
        events.append(Vol(100))             # placeholder volume (real dynamics in T4)
    events.append(LoopPoint())

    total_clamps = 0
    for pat in channel["patterns"]:
        seq_idx = str(pat["seq_idx"])
        seq = sequences.get(seq_idx)
        if seq is None:
            print(f"  [warn] ch{channel.get('channel_idx')}: missing "
                  f"sequence {seq_idx} — skipped", file=sys.stderr)
            continue
        body, clamps = _flatten_sequence_body(
            seq, pat["pitch_transpose"], voice_remap)
        total_clamps += clamps
        if not body:
            continue                # empty body — nothing to repeat
        repeat = pat["repeat"]
        if not (1 <= repeat <= 255):
            print(f"  [warn] ch{channel.get('channel_idx')}: repeat {repeat} "
                  f"out of range 1..255 — clamped", file=sys.stderr)
            repeat = max(1, min(255, repeat))
        events.append(RepeatStart())
        events.extend(body)
        events.append(RepeatEnd(repeat))

    events.append(Jump())
    if total_clamps:
        print(f"  [info] ch{channel.get('channel_idx')}: {total_clamps} "
              f"pitch value(s) clamped to 0..0x{MAX_PITCH:X}", file=sys.stderr)
    return events


# ch0-4 -> FM1..FM5. ch5 is the 6th FM voice held aside for T3's adaptive FM6.
# ch6 is a 1-pattern stub (dropped). Indices beyond 4 are not routed in T1.
_T1_FM_ROUTES = [CHROUTE_FM1, CHROUTE_FM1 + 1, CHROUTE_FM1 + 2,
                 CHROUTE_FM1 + 3, CHROUTE_FM5]

# The Zyrinx global voice bank (Moving Trucks = bank 1). Default location; the
# CLI / build pass it explicitly so this is only a fallback for in-tree calls.
import os as _os
VOICES_JSON_DEFAULT = (
    "/home/volence/sonic_hacks/The Adventures of Batman and Robin/"
    "disasm/sound/decoded_full/voices.json")


def build_songdesc(raw: dict, voices_json: str = None) -> SongDesc:
    """Turn the loaded JSON into a packer-accepted SongDesc.

    Routes ch0-4 -> FM1..FM5. ch5 (the 6th FM voice) is DEFERRED to T3 (we have
    no FM6 route yet). ch6 (the 1-pattern stub) is DROPPED + logged.

    voices_json: path to the Zyrinx voices.json. T2: voice events become
    Patch(local_idx) into the per-song dense bank (build_patch_bank). If None,
    VOICES_JSON_DEFAULT is used when present; if the bank cannot be loaded the
    transcode degrades to the T1 placeholder (Patch(0), voices dropped).
    """
    if voices_json is None and _os.path.exists(VOICES_JSON_DEFAULT):
        voices_json = VOICES_JSON_DEFAULT
    voice_remap = None
    if voices_json is not None and _os.path.exists(voices_json):
        _, voice_remap, _ = build_patch_bank(raw, voices_json)

    tempo = zyrinx_tempo_to_byte(raw["header"]["format"])
    sequences = raw["sequences"]
    channels = []
    for i, ch in enumerate(raw["channels"]):
        npat = len(ch.get("patterns", []))
        if i >= len(_T1_FM_ROUTES):
            # ch5 = 6th FM voice (FM6, T3); ch6 = trivial stub (drop).
            reason = ("FM6 — deferred to T3 (adaptive FM6 slot)"
                      if i == 5 else "trivial stub — dropped")
            print(f"  [info] ch{i} ({npat} pattern(s)) NOT routed in T1: "
                  f"{reason}", file=sys.stderr)
            continue
        events = flatten_channel(ch, sequences, _T1_FM_ROUTES[i], voice_remap)
        channels.append(ChannelDesc(_T1_FM_ROUTES[i], events))
    return SongDesc(tempo=tempo, channels=channels)


# --- CLI: regenerate the .asm ----------------------------------------------

def main(argv=None):
    import argparse
    try:
        from song_packer import write_asm
    except ImportError:  # pragma: no cover
        from tools.song_packer import write_asm  # type: ignore

    argv = argv if argv is not None else sys.argv[1:]
    ap = argparse.ArgumentParser(description="Transcode Moving Trucks -> v0 song")
    ap.add_argument("json", help="path to 05_Moving_Trucks.json")
    ap.add_argument("out", help="output .asm path (song)")
    ap.add_argument("--label", default="Song_MovingTrucks")
    ap.add_argument("--voices", default=VOICES_JSON_DEFAULT,
                    help="path to voices.json (Zyrinx voice bank)")
    ap.add_argument("--patches-out", default=None,
                    help="output .asm path for the FmPatch bank "
                         "(default: movingtrucks_patches.asm beside the song)")
    ap.add_argument("--patch-label", default="MovingTrucks_Patches")
    args = ap.parse_args(argv)

    raw = load_song(args.json)

    # Emit the per-song FmPatch bank (T2) first so we can report its size.
    patches_out = args.patches_out
    if patches_out is None:
        patches_out = _os.path.join(_os.path.dirname(args.out),
                                    "movingtrucks_patches.asm")
    remap, pcount = write_patch_bank_asm(raw, args.voices, patches_out,
                                         args.patch_label)
    print(f"wrote {patches_out}: {pcount} FmPatch records, "
          f"{pcount * FMPATCH_LEN} bytes", file=sys.stderr)

    song = build_songdesc(raw, voices_json=args.voices)
    write_asm(song, args.label, args.out)
    # Report the emitted size.
    try:
        from song_packer import pack_song
    except ImportError:  # pragma: no cover
        from tools.song_packer import pack_song  # type: ignore
    size = len(pack_song(song))
    print(f"wrote {args.out}: {len(song.channels)} channel(s), {size} bytes "
          f"(tempo ${song.tempo:02X})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
