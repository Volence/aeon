"""Shared VGM parsing/rendering helpers for the sound-perf-budget harness.

Handles: 0x50 PSG, 0x52/0x53 YM2612 port0/1, 0x61/0x62/0x63/0x7n waits,
0x67 data blocks, 0x8n DAC-write-with-wait, 0xE0 seek, 0x66 end.
All timestamps are in VGM samples (44100 Hz).
"""
import struct
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np

RATE = 44100
FRAME = 735  # samples per NTSC frame


class Event:
    __slots__ = ("t", "kind", "a", "b")

    def __init__(self, t, kind, a=0, b=0):
        self.t = t
        self.kind = kind  # 'ym0','ym1','psg','dacblk'
        self.a = a        # register (ym) / value (psg) / data byte (dacblk)
        self.b = b        # value (ym)

    def __repr__(self):
        return f"Event(t={self.t},{self.kind},a={self.a:#x},b={self.b:#x})"


def parse(path):
    """Parse a VGM file -> (header_dict, list[Event])."""
    data = Path(path).read_bytes()
    assert data[:4] == b"Vgm ", "not a VGM file"
    version = struct.unpack_from("<I", data, 0x08)[0]
    total_samples = struct.unpack_from("<I", data, 0x18)[0]
    if version >= 0x150:
        off = struct.unpack_from("<I", data, 0x34)[0]
        start = 0x34 + off if off else 0x40
    else:
        start = 0x40
    hdr = {"version": version, "total_samples": total_samples, "start": start}

    events = []
    t = 0
    i = start
    datablock = bytearray()
    dac_pos = 0
    n = len(data)
    while i < n:
        c = data[i]
        if c == 0x52:
            events.append(Event(t, "ym0", data[i + 1], data[i + 2])); i += 3
        elif c == 0x53:
            events.append(Event(t, "ym1", data[i + 1], data[i + 2])); i += 3
        elif c == 0x50:
            events.append(Event(t, "psg", data[i + 1])); i += 2
        elif c == 0x61:
            t += struct.unpack_from("<H", data, i + 1)[0]; i += 3
        elif c == 0x62:
            t += 735; i += 1
        elif c == 0x63:
            t += 882; i += 1
        elif 0x70 <= c <= 0x7F:
            t += (c & 0x0F) + 1; i += 1
        elif 0x80 <= c <= 0x8F:
            # YM2612 port0 $2A write from data block, then wait n
            if dac_pos < len(datablock):
                events.append(Event(t, "ym0", 0x2A, datablock[dac_pos]))
                dac_pos += 1
            t += c & 0x0F; i += 1
        elif c == 0x67:
            size = struct.unpack_from("<I", data, i + 3)[0] & 0x7FFFFFFF
            datablock += data[i + 7:i + 7 + size]
            i += 7 + size
        elif c == 0xE0:
            dac_pos = struct.unpack_from("<I", data, i + 1)[0]; i += 5
        elif c == 0x66:
            break
        elif c == 0x4F:
            i += 2  # GG stereo
        elif 0x90 <= c <= 0x95:
            # DAC stream control — sizes per spec
            i += {0x90: 5, 0x91: 5, 0x92: 6, 0x93: 11, 0x94: 2, 0x95: 5}[c]
        else:
            raise ValueError(f"unhandled VGM cmd {c:#04x} at {i:#x}")
    hdr["end_t"] = t
    return hdr, events


# ---------- derived streams ----------

def keyons(events):
    """Yield (t, ch, on_bool, opmask) from $28 writes. ch in 0..5."""
    out = []
    for e in events:
        if e.kind == "ym0" and e.a == 0x28:
            v = e.b
            ch = (v & 0x07)
            if ch in (0, 1, 2):
                chn = ch
            elif ch in (4, 5, 6):
                chn = ch - 1
            else:
                continue
            ops = v >> 4
            out.append((e.t, chn, ops != 0, ops))
    return out


def dac_writes(events):
    """(t, value) for every $2A write."""
    return [(e.t, e.b) for e in events if e.kind == "ym0" and e.a == 0x2A]


def fnum_stream(events, ch):
    """Yield (t, block, fnum) each time the channel's operating fnum changes.
    ch 0-2 = port0 regs A4+ch/A0+ch, ch 3-5 = port1 regs A4+(ch-3)/A0+(ch-3).
    YM latches: write A4 (block+fnum hi) THEN A0 (fnum lo) applies."""
    port = "ym0" if ch < 3 else "ym1"
    sub = ch if ch < 3 else ch - 3
    hi_reg, lo_reg = 0xA4 + sub, 0xA0 + sub
    hi = 0
    out = []
    for e in events:
        if e.kind != port:
            continue
        if e.a == hi_reg:
            hi = e.b
        elif e.a == lo_reg:
            block = (hi >> 3) & 7
            fnum = ((hi & 7) << 8) | e.b
            out.append((e.t, block, fnum))
    return out


def cents(block, fnum, base_block, base_fnum):
    f = fnum * (1 << block)
    fb = base_fnum * (1 << base_block)
    if f <= 0 or fb <= 0:
        return 0.0
    return 1200.0 * np.log2(f / fb)


# ---------- burst segmentation (DAC) ----------

def dac_bursts(dw, boundary_samples=int(0.030 * RATE)):
    """Split $2A write timestamps into bursts (drum hits).
    A gap > boundary (default 30 ms) starts a new burst.
    Returns list of lists of (t, value)."""
    bursts = []
    cur = []
    last = None
    for t, v in dw:
        if last is not None and t - last > boundary_samples:
            if cur:
                bursts.append(cur)
            cur = []
        cur.append((t, v))
        last = t
    if cur:
        bursts.append(cur)
    return bursts


def dac_hits(dw, idle_val=0x80):
    """Value-aware drum-hit segmentation, valid for BOTH driver styles:
    - S3K ref: stops writing between hits -> gap > 30 ms separates.
    - ours: writes idle_val once per frame between hits -> a run of >=3
      frame-paced (8-30 ms gap) idle-valued writes separates; mid-hit
      full-frame freezes (gap ~16.7 ms but sample mid-flight) do NOT.
    Returns list of hits, each a list of (t, v) with idle writes stripped
    from the edges."""
    hits = []
    cur = []
    idle_run = 0
    last_t = None
    for t, v in dw:
        gap = (t - last_t) if last_t is not None else 0
        frame_paced = 8e-3 * RATE <= gap <= 30e-3 * RATE
        if v == idle_val and frame_paced:
            idle_run += 1
        elif v == idle_val and gap > 30e-3 * RATE:
            idle_run = 3  # lone idle after long silence
        elif gap > 30e-3 * RATE:
            # long gap into a real sample: hit boundary (ref style)
            if cur:
                hits.append(cur)
            cur = []
            idle_run = 0
        else:
            idle_run = 0
        if idle_run >= 3:
            # we are in silence; close any open hit (strip trailing idles)
            if cur:
                while cur and cur[-1][1] == idle_val:
                    cur.pop()
                if cur:
                    hits.append(cur)
                cur = []
        else:
            if not cur and v == idle_val:
                pass  # don't open a hit on an idle write
            else:
                cur.append((t, v))
        last_t = t
    if cur:
        while cur and cur[-1][1] == idle_val:
            cur.pop()
        if cur:
            hits.append(cur)
    return [h for h in hits if len(h) >= 32]


# ---------- channel isolation + rendering ----------

def write_isolated(src, dst, keep_fm=None, keep_dac=False, keep_psg=False):
    """Rewrite a VGM keeping only one voice.
    keep_fm: FM channel 0-5 (keeps its regs + its $28 key-ons + globals),
    keep_dac: keep $2A/$2B and FM6 key-ons, keep_psg: keep PSG writes.
    Globals ($22 LFO, $27 ch3 mode, timers) are always kept."""
    data = bytearray(Path(src).read_bytes())
    version = struct.unpack_from("<I", data, 0x08)[0]
    if version >= 0x150:
        off = struct.unpack_from("<I", data, 0x34)[0]
        start = 0x34 + off if off else 0x40
    else:
        start = 0x40

    if keep_fm is None:
        keep_set = set()
    elif isinstance(keep_fm, int):
        keep_set = {keep_fm}
    else:
        keep_set = set(keep_fm)

    def fm_reg_belongs(port, reg, chans):
        for ch in chans:
            sub = ch if ch < 3 else ch - 3
            p = 0 if ch < 3 else 1
            if port != p:
                continue
            if 0x30 <= reg <= 0x9F and (reg & 3) == sub:
                return True
            if 0xA0 <= reg <= 0xAE and ((reg & 3) == sub or 0xA8 <= reg <= 0xAE):
                return True
            if 0xB0 <= reg <= 0xB6 and (reg & 3) == sub:
                return True
        return False

    out = bytearray(data[:start])
    i = start
    n = len(data)
    NOP = b""
    while i < n:
        c = data[i]
        if c == 0x52 or c == 0x53:
            port = c - 0x52
            reg, val = data[i + 1], data[i + 2]
            keep = False
            if port == 0 and reg in (0x22, 0x27, 0x24, 0x25, 0x26, 0x2B):
                keep = True
                if reg == 0x2B and not keep_dac:
                    keep = False
            elif port == 0 and reg == 0x2A:
                keep = keep_dac
            elif port == 0 and reg == 0x28:
                v = val & 7
                ch = v if v < 3 else (v - 1 if v > 3 else None)
                keep = (ch is not None) and ((ch in keep_set)
                                             or (keep_dac and ch == 5))
            else:
                keep = fm_reg_belongs(port, reg, keep_set) or \
                    (keep_dac and fm_reg_belongs(port, reg, {5}))
            out += data[i:i + 3] if keep else NOP
            i += 3
        elif c == 0x50:
            if keep_psg:
                out += data[i:i + 2]
            i += 2
        elif c == 0x61:
            out += data[i:i + 3]; i += 3
        elif c in (0x62, 0x63):
            out += data[i:i + 1]; i += 1
        elif 0x70 <= c <= 0x7F:
            out += data[i:i + 1]; i += 1
        elif 0x80 <= c <= 0x8F:
            if keep_dac:
                out += data[i:i + 1]
            else:
                out += bytes([0x70 | (c & 0x0F)]) if (c & 0x0F) else b""
            i += 1
        elif c == 0x67:
            size = struct.unpack_from("<I", data, i + 3)[0] & 0x7FFFFFFF
            out += data[i:i + 7 + size]; i += 7 + size
        elif c == 0xE0:
            out += data[i:i + 5]; i += 5
        elif c == 0x66:
            out += data[i:i + 1]; break
        elif c == 0x4F:
            i += 2
        elif 0x90 <= c <= 0x95:
            sz = {0x90: 5, 0x91: 5, 0x92: 6, 0x93: 11, 0x94: 2, 0x95: 5}[c]
            out += data[i:i + sz]; i += sz
        else:
            raise ValueError(f"unhandled cmd {c:#04x}")
    # patch EOF offset
    struct.pack_into("<I", out, 0x04, len(out) - 4)
    # kill loop so vgm2wav renders once
    struct.pack_into("<I", out, 0x1C, 0)
    struct.pack_into("<I", out, 0x20, 0)
    Path(dst).write_bytes(bytes(out))


def write_trimmed(src, dst, t_end_sec):
    """Copy a VGM keeping only commands before t_end_sec (data blocks kept)."""
    data = bytearray(Path(src).read_bytes())
    version = struct.unpack_from("<I", data, 0x08)[0]
    if version >= 0x150:
        off = struct.unpack_from("<I", data, 0x34)[0]
        start = 0x34 + off if off else 0x40
    else:
        start = 0x40
    t_end = int(t_end_sec * RATE)
    out = bytearray(data[:start])
    i = start
    t = 0
    n = len(data)
    while i < n and t < t_end:
        c = data[i]
        if c in (0x52, 0x53):
            out += data[i:i + 3]; i += 3
        elif c == 0x50:
            out += data[i:i + 2]; i += 2
        elif c == 0x61:
            t += struct.unpack_from("<H", data, i + 1)[0]
            out += data[i:i + 3]; i += 3
        elif c == 0x62:
            t += 735; out += data[i:i + 1]; i += 1
        elif c == 0x63:
            t += 882; out += data[i:i + 1]; i += 1
        elif 0x70 <= c <= 0x7F:
            t += (c & 0x0F) + 1; out += data[i:i + 1]; i += 1
        elif 0x80 <= c <= 0x8F:
            t += c & 0x0F; out += data[i:i + 1]; i += 1
        elif c == 0x67:
            size = struct.unpack_from("<I", data, i + 3)[0] & 0x7FFFFFFF
            out += data[i:i + 7 + size]; i += 7 + size
        elif c == 0xE0:
            out += data[i:i + 5]; i += 5
        elif c == 0x66:
            break
        elif c == 0x4F:
            i += 2
        elif 0x90 <= c <= 0x95:
            sz = {0x90: 5, 0x91: 5, 0x92: 6, 0x93: 11, 0x94: 2, 0x95: 5}[c]
            out += data[i:i + sz]; i += sz
        else:
            raise ValueError(f"unhandled cmd {c:#04x}")
    out += b"\x66"
    struct.pack_into("<I", out, 0x04, len(out) - 4)
    struct.pack_into("<I", out, 0x18, min(t, t_end))
    struct.pack_into("<I", out, 0x1C, 0)
    struct.pack_into("<I", out, 0x20, 0)
    Path(dst).write_bytes(bytes(out))


def render(vgm_path, wav_path=None, loops=1, fade=0.0):
    """Render a VGM to mono float array via vgm2wav."""
    vgm_path = Path(vgm_path)
    if wav_path is None:
        wav_path = vgm_path.with_suffix(".wav")
    subprocess.run(["vgm2wav", "--loops", str(loops), "--fade", str(fade),
                    str(vgm_path), str(wav_path)],
                   check=True, capture_output=True)
    with wave.open(str(wav_path), "rb") as w:
        nch, sw, sr = w.getnchannels(), w.getsampwidth(), w.getframerate()
        raw = w.readframes(w.getnframes())
    assert sw == 2
    x = np.frombuffer(raw, dtype=np.int16).astype(np.float64) / 32768.0
    if nch == 2:
        x = x.reshape(-1, 2).mean(axis=1)
    return x, sr


def frame_rms_db(x, sr, frame_ms=16.7):
    """Per-frame RMS in dBFS."""
    flen = int(sr * frame_ms / 1000.0)
    nf = len(x) // flen
    fr = x[:nf * flen].reshape(nf, flen)
    rms = np.sqrt((fr ** 2).mean(axis=1))
    return 20 * np.log10(np.maximum(rms, 1e-10))


def db(v):
    return 20 * np.log10(max(v, 1e-10))
