#!/usr/bin/env python3
"""vgm_to_song — transcode a captured VGM register stream into our v0 music
format, played by OUR sequencer across all 6 FM voices.

WHY VGM (not the Zyrinx song binary): the Zyrinx per-channel -> YM-voice
assignment lives in the GAME'S 68K loader, which was never decoded, so the
song-JSON channel split is a guess; its repeat/duration semantics also produce
impossible timings. The captured VGM is the EXACT chip-register output of the
original game playing the song — unambiguous ground truth, and its channel index
IS the real YM channel. We replay that performance through our sequencer:
  - each YM key-on  -> MEV_NOTE_RAW(a4, a0, dur): the exact $A4/$A0 the chip got,
    so the pitch (incl. sub-C0 bass + microtuning) is reproduced bit-exactly.
  - the channel's voice registers ($30-$8E, $B0, $B4), snapshotted at each
    key-on, become a 26-byte FmPatch (deduped into a per-song bank); a Patch
    event reloads it whenever it changes.
  - durations come from quantizing VGM timestamps to our Timer-A tick grid.

This is BUILD-PC tooling. It emits the song + FmPatch-bank .asm the engine
includes (same labels/placement as the old zyrinx_port output, so main.asm and
song_table.asm are unchanged).

Usage:
  python3 tools/vgm_to_song.py <ref.vgm> <song_out.asm> [--patches-out P.asm]
"""

import struct
import sys

try:
    from song_packer import (
        SongDesc, ChannelDesc,
        NoteRaw, Rest, SetDur, Patch, Vol, LoopPoint, Jump,
        CHROUTE_FM1, SH_F_FM6_FM, SH_F_STREAM, pack_song, write_asm,
    )
except ImportError:  # pragma: no cover
    from tools.song_packer import (  # type: ignore
        SongDesc, ChannelDesc,
        NoteRaw, Rest, SetDur, Patch, Vol, LoopPoint, Jump,
        CHROUTE_FM1, SH_F_FM6_FM, SH_F_STREAM, pack_song, write_asm,
    )

# --- Tick clock ------------------------------------------------------------
# Our tick is YM Timer-A: N = tempo<<2, period = 18.773us*(1024-N). tempo 34 ->
# N=136 -> 60.0 Hz (one tick ~= one NTSC video frame). 60 Hz resolves the song's
# ~152 ms median note to ~9 ticks and keeps note/rest durations within the 1-byte
# range (<=255 ticks = 4.25 s) for everything in this song.
TEMPO = 34
_TIMERA_PERIOD_NS = 18773


def tick_hz(tempo: int) -> float:
    return 1e9 / ((1024 - (tempo << 2)) * _TIMERA_PERIOD_NS)


SAMPLE_RATE = 44100
FMPATCH_LEN = 26
MAX_DUR = 0xFF          # NoteRaw / NoteDur duration byte
MAX_SETDUR = 0x7F       # SetDur range
MAX_PATCHES = 256       # Patch operand is one byte (index 0..255)

# YM channel routing: the 6 FM channels in YM order map 1:1 to our FM routes.
# VGM port0 ($52) carries FM1-3 (reg&3 = 0,1,2); port1 ($53) carries FM4-6.
# Global channel index g = 0..5 -> CHROUTE_FM1 + g.
N_FM = 6


def _global_ch(port: int, ch_in_port: int) -> int:
    """(port, ch-in-port 0..2) -> global FM channel 0..5."""
    return ch_in_port + (3 if port else 0)


def snapshot_patch(regs: dict, port: int, ch: int) -> bytes:
    """Build a 26-byte FmPatch from the live register state of (port, ch).

    Layout (mirror of fm_patches.inc / song_packer): fp_alg_fb ($B0), fp_lr_ams_fms
    ($B4), then six 4-byte per-operator arrays for regs $30/$40/$50/$60/$70/$80,
    array index 0..3 = the four operators in PHYSICAL register order S1,S3,S2,S4
    (= reg offsets +0,+4,+8,+C). The VGM already holds registers in that order, so
    NO operator reordering is needed (unlike the JSON path) — this is the exact
    chip voice. $B4 L/R bits forced to 11 if both are clear (else the voice is
    silent)."""
    rp = regs[port]

    def g(base, op):
        return rp.get(base + op * 4 + ch, 0) & 0xFF

    alg_fb = rp.get(0xB0 + ch, 0) & 0xFF        # $B0 byte == (fb<<3)|algo already
    lr_ams_fms = rp.get(0xB4 + ch, 0) & 0xFF
    if (lr_ams_fms & 0xC0) == 0:
        lr_ams_fms |= 0xC0                      # force audible (both L+R)
    out = bytearray((alg_fb, lr_ams_fms))
    for base in (0x30, 0x40, 0x50, 0x60, 0x70, 0x80):
        out.extend((g(base, 0), g(base, 1), g(base, 2), g(base, 3)))
    assert len(out) == FMPATCH_LEN
    return bytes(out)


def parse_vgm(path: str):
    """Parse a VGM. Returns (events, total_samples) where events[g] is the
    per-FM-channel list of (sample_time, kind, a4, a0, patch_bytes); kind is
    'on' or 'off' ('off' has a4/a0/patch = None)."""
    data = open(path, 'rb').read()
    doff = struct.unpack('<I', data[0x34:0x38])[0]
    p = 0x34 + doff if doff else 0x40
    n = len(data)
    t = 0
    regs = {0: {}, 1: {}}        # regs[port][reg] = last value
    events = [[] for _ in range(N_FM)]
    while p < n:
        c = data[p]
        if c in (0x52, 0x53):
            port = 0 if c == 0x52 else 1
            reg, val = data[p + 1], data[p + 2]
            p += 3
            regs[port][reg] = val
            if c == 0x52 and reg == 0x28:        # key on/off (always port0)
                chsel = val & 0x07
                if chsel == 3 or chsel == 7:
                    continue                     # invalid chsel
                kport = 0 if chsel < 4 else 1
                cip = chsel & 3                  # ch-in-port 0..2
                g = _global_ch(kport, cip)
                if val & 0xF0:                   # any operator on -> key-on
                    a4 = regs[kport].get(0xA4 + cip, 0)
                    a0 = regs[kport].get(0xA0 + cip, 0)
                    patch = snapshot_patch(regs, kport, cip)
                    events[g].append((t, 'on', a4, a0, patch))
                else:                            # all ops off -> key-off
                    events[g].append((t, 'off', None, None, None))
        elif c == 0x50:
            p += 2
        elif c == 0x4F:
            p += 2
        elif c == 0x61:
            t += struct.unpack('<H', data[p + 1:p + 3])[0]
            p += 3
        elif c == 0x62:
            t += 735
            p += 1
        elif c == 0x63:
            t += 882
            p += 1
        elif 0x70 <= c <= 0x7F:
            t += (c & 0xF) + 1
            p += 1
        elif 0x80 <= c <= 0x8F:
            t += (c & 0xF)
            p += 1
        elif c == 0x66:
            break
        elif c == 0x67:
            sz = struct.unpack('<I', data[p + 3:p + 7])[0]
            p += 7 + sz
        elif c == 0xE0:
            p += 5
        else:
            p += 1
    return events, t


def _to_ticks(samples: int, hz: float) -> int:
    return int(round(samples / SAMPLE_RATE * hz))


def build_song(ref_vgm: str, verbose=True):
    """Parse the VGM and build (SongDesc, patch_bank_bytes, patch_count)."""
    raw_events, total_samples = parse_vgm(ref_vgm)
    hz = tick_hz(TEMPO)
    total_ticks = _to_ticks(total_samples, hz)

    # --- global patch bank (dedup the 26-byte snapshots) ---
    patch_index = {}          # bytes -> idx
    patch_bank = bytearray()

    def intern(pbytes: bytes) -> int:
        i = patch_index.get(pbytes)
        if i is None:
            i = len(patch_index)
            patch_index[pbytes] = i
            patch_bank.extend(pbytes)
        return i

    # --- quantize each channel's events to ticks, collapse same-tick ---
    channels = []
    max_note_dur = 0
    long_notes = 0
    for g in range(N_FM):
        evs = raw_events[g]
        if not evs:
            continue
        # (tick, kind, a4, a0, patch_idx)
        q = []
        for (smp, kind, a4, a0, patch) in evs:
            tk = _to_ticks(smp, hz)
            pidx = intern(patch) if kind == 'on' else None
            q.append([tk, kind, a4, a0, pidx])
        # collapse consecutive events on the same tick (keep the last state)
        collapsed = []
        for e in q:
            if collapsed and collapsed[-1][0] == e[0]:
                collapsed[-1] = e
            else:
                collapsed.append(e)
        q = collapsed

        events = []
        first_on = next((e for e in q if e[1] == 'on'), None)
        if first_on is None:
            continue
        first_patch = first_on[4]
        events.append(Patch(first_patch))     # one-time setup (packer needs it)
        events.append(Vol(127))               # 127 -> LogVolumeLut[127]=0: patch TL as-is
        events.append(LoopPoint())
        # Leading silence to this channel's FIRST onset, so the song's staggered
        # instrument entrances are preserved (FM4 enters ~1.2s after FM1, etc.) and
        # every channel is exactly total_ticks long -> all 6 loops stay in sync.
        lead = q[0][0]
        while lead > 0:
            step = min(lead, MAX_SETDUR)
            events.append(SetDur(step))
            events.append(Rest())
            lead -= step
        cur_patch = None                       # force a Patch on the first note each loop

        for i, e in enumerate(q):
            tk, kind, a4, a0, pidx = e
            nxt = q[i + 1][0] if i + 1 < len(q) else total_ticks
            dur = nxt - tk
            if dur <= 0:
                continue
            if kind == 'on':
                if pidx != cur_patch:
                    events.append(Patch(pidx))
                    cur_patch = pidx
                # split a >255-tick held note (rare); each chunk re-keys
                d = dur
                while d > MAX_DUR:
                    events.append(NoteRaw(a4, a0, MAX_DUR))
                    d -= MAX_DUR
                    long_notes += 1
                events.append(NoteRaw(a4, a0, d))
                max_note_dur = max(max_note_dur, dur)
            else:  # 'off' -> rest for dur ticks (key-off + silence)
                d = dur
                while d > 0:
                    step = min(d, MAX_SETDUR)
                    events.append(SetDur(step))
                    events.append(Rest())
                    d -= step
        events.append(Jump())
        channels.append(ChannelDesc(CHROUTE_FM1 + g, events))
        if verbose:
            non = sum(1 for e in q if e[1] == 'on')
            print(f"  FM{g+1}: {non} notes, {len([e for e in events])} events",
                  file=sys.stderr)

    if len(patch_index) > MAX_PATCHES:
        raise SystemExit(
            f"ERROR: {len(patch_index)} distinct patches > {MAX_PATCHES} "
            f"(Patch index is one byte). Need TL/voice quantization.")

    if verbose:
        print(f"  tick rate {hz:.2f} Hz (tempo ${TEMPO:02X}), "
              f"song {total_ticks} ticks (~{total_ticks/hz:.1f}s)", file=sys.stderr)
        print(f"  distinct patches: {len(patch_index)} "
              f"({len(patch_bank)} bytes)", file=sys.stderr)
        print(f"  max note dur {max_note_dur} ticks; "
              f"{long_notes} note-splits (>255 ticks)", file=sys.stderr)

    song = SongDesc(tempo=TEMPO, channels=channels,
                    flags=SH_F_FM6_FM | SH_F_STREAM)
    return song, bytes(patch_bank), len(patch_index)


def emit_patch_bank_asm(bank: bytes, count: int,
                        label: str = "MovingTrucks_Patches") -> str:
    """Emit the FmPatch bank as an AS data file via the dual-includable `pbyte`
    macro (same shape as the old zyrinx_port output, so the build/asserts are
    unchanged)."""
    assert len(bank) == count * FMPATCH_LEN
    grp = ("fp_dt_mul  $30", "fp_tl      $40", "fp_rs_ar   $50",
           "fp_am_d1r  $60", "fp_d2r     $70", "fp_d1l_rr  $80")
    L = []
    L.append("; ======================================================================")
    L.append("; data/sound/%s.asm — GENERATED by tools/vgm_to_song.py — DO NOT EDIT." % label.lower())
    L.append(";")
    L.append("; Per-song FmPatch bank for \"Moving Trucks\", snapshotted directly from")
    L.append("; the original game's chip-register stream (the reference VGM) at each")
    L.append("; key-on and deduplicated. Each record is the EXACT YM2612 voice the")
    L.append("; original used. Operators are already in PHYSICAL register order")
    L.append("; S1,S3,S2,S4 (the VGM holds them that way), so no reorder is applied.")
    L.append(";")
    L.append("; Record: fp_alg_fb=$B0, fp_lr_ams_fms=$B4, then 6 four-byte per-op arrays")
    L.append("; for regs $30/$40/$50/$60/$70/$80. The FM writer reads a record via")
    L.append("; Fm_PatchLoad at SND_SEQ_PATCHTAB + local_idx*26.")
    L.append("; ======================================================================")
    L.append("")
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
        rec = bank[li * FMPATCH_LEN:(li + 1) * FMPATCH_LEN]
        L.append("; --- patch %d ---" % li)
        L.append("        pbyte   %-3d                     ; fp_alg_fb     $%02X" % (rec[0], rec[0]))
        L.append("        pbyte   %-3d                     ; fp_lr_ams_fms $%02X" % (rec[1], rec[1]))
        for gi, glabel in enumerate(grp):
            off = 2 + gi * 4
            x = rec[off:off + 4]
            L.append("        pbyte   %3d, %3d, %3d, %3d   ; %s  [S1,S3,S2,S4]"
                     % (x[0], x[1], x[2], x[3], glabel))
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


def main(argv=None):
    import argparse
    import os
    argv = argv if argv is not None else sys.argv[1:]
    ap = argparse.ArgumentParser(description="Transcode a VGM -> v0 song")
    ap.add_argument("vgm", help="reference VGM (chip register stream)")
    ap.add_argument("out", help="output song .asm path")
    ap.add_argument("--label", default="Song_MovingTrucks")
    ap.add_argument("--patches-out", default=None)
    ap.add_argument("--patch-label", default="MovingTrucks_Patches")
    args = ap.parse_args(argv)

    song, bank, pcount = build_song(args.vgm)

    patches_out = args.patches_out or os.path.join(
        os.path.dirname(args.out), "movingtrucks_patches.asm")
    with open(patches_out, "w") as f:
        f.write(emit_patch_bank_asm(bank, pcount, args.patch_label))
    print(f"wrote {patches_out}: {pcount} FmPatch records, "
          f"{pcount * FMPATCH_LEN} bytes", file=sys.stderr)

    write_asm(song, args.label, args.out)
    size = len(pack_song(song))
    print(f"wrote {args.out}: {len(song.channels)} channel(s), {size} bytes "
          f"(tempo ${song.tempo:02X})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
