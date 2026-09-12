#!/usr/bin/env python3
"""song_load_mid_drum_witness — what a `Sound_PlayMusic` landing MID-DRUM does to
the drum and to FM6, measured off the YM2612 write stream.

THE CLAIM UNDER TEST (`docs/lens-findings.jsonl` GAP12-A2-9b, the review seat's
reading of `Snd_LoadSong`, explicitly recorded as UNMEASURED): across a song load
that lands while a DAC drum is in flight,
  (i)  the rest of the drum is SILENT until the new song's first $E2, because
       `Snd_LoadSong` step 1 writes YM $2B = $00 and clears SND_STAT_DAC_ACTIVE
       unconditionally while the streaming loop never reads DAC_ACTIVE and runs
       on to the sample's own `.stop`; and
  (ii) FM6 may be RE-KEYED mid-note, because that `.stop` reads
       SND_FM6_ADAPTIVE / SND_FM6_CHAN_PTR — which the loader has already
       re-derived for the NEW song.

THE INSTRUMENT, and why this one. The 68k never writes the YM here; the Z80 does,
at its own $4000-$4003. oracle's Rust core answers `capabilities.vgm: false` — the
six sound methods (`vgm_start`, `audio_spectrum`, `get_channel_states`, ...) are
catalogued and NOT served — so there is no VGM log and no audio to render. What IS
available: `crates/oracle-core/src/z80/bus.rs` taps every Z80-side $4000-$4003 and
$7F11 write into the same `BusEvent` sink the 68k bus feeds, at the RAW Z80-side
address, and `Watchpoints` is a consumer of that sink. So a v1 `bus`-space write
watch over $4000-$4003 records the driver's YM register traffic with a per-hit
mclk. Measured, not assumed: leg L0 asserts the watch is live, and a `--poison`
run aims it where nothing writes and requires L0 to go loud (a dead instrument and
a silent machine look identical otherwise).

Second instrument, for the state the YM stream cannot show: the config-A profile
places `Sound_DebugMirror` (engine/debug/sound_debug.emp) and calls it every
VBlank, snapshotting Z80 RAM $1F00.. and $18F0.. into `Sound_Dbg_Mirror` in 68k
RAM. `read_memory` REFUSES $A00000-$A0FFFF ("only cartridge space and work RAM are
readable in this slice"), so that mirror is the only way this bus can see
SND_STAT_DAC_ACTIVE / SND_DAC_PHASE / SND_ROM_LEN / SND_FM6_*. Its cost is stated:
it holds the Z80 bus once per frame, so every number here is from a machine
already paying that hold.

WHAT HAS NO INSTRUMENT HERE, said once so it is not mistaken for a result: audio.
Nothing renders a waveform, so "silent" below always means *the DAC enable bit is
off while the streaming loop keeps writing $2A*, which is what silence is made of
on this chip — never a measured absence of sound.

SHAPE. This needs the music-capable off-canonical profile — the canonical ROMs
CANNOT play music by design (`Sound_PlayMusic`'s only call site is
`games/sonic4/debug/game_debug.emp`, bound only under SOUND_DEBUG_HOTKEYS):

    sigil build --aeon . --native --config-a -o cfga.bin --emit-lst cfga.lst
    python3 tools/song_load_mid_drum_witness.py --rom cfga.bin --lst cfga.lst

SEVEN LEGS, count asserted, five drives and two controls:

  L0 THE WATCH IS LIVE  the YM watch's `seen` > 0 and `matched` > 0 over a window
                        in which only the Z80 writes the YM.
  L1 A DRUM IS SOUNDING established from the WRITE STREAM — the $2A data-write
                        RATE over one frame against the DAC rate derived from the
                        sound constants — and not from a frame count.
  L2/L3/L4 THE TRANSITION  mid-drum, request another song — each of the three the
                        ROM ships, because (ii) is a claim about what the dying
                        drum's `.stop` reads out of the NEWLY LOADED song and the
                        three do not agree. Moving Trucks (L2) and HCZ2 (L3) are
                        FM6-DEDICATE; the ONLY FM6-ADAPTIVE song here is the
                        drum-test song itself, so the only way to reach the
                        adaptive branch of `.stop` at all is to load the drum song
                        over its own running drum (L4).
  C1 NO SONG REQUEST    the CONTROL for (i) and (ii): the same drum, same boot,
                        left alone to reach its own `.stop`. Without it, "$2B went
                        to $00 and FM6 got keyed" does not distinguish the song
                        load from what the END OF EVERY DRUM does anyway.
  C2 SONG REQUEST, NO DRUM  the second CONTROL: the same request with
                        DAC_ACTIVE == 0. Isolates what the MID-DRUM landing adds
                        over what any `Snd_LoadSong` does.

This is a MEASUREMENT witness, not a gate. It is wired into no runner: it needs an
off-canonical ROM, so `build.sh` could not run it. It FAILS only when it could not
ask its question (a dead watch, a hole in the captured stream, a drum that never
started, a load that never landed) — never on the engine's behaviour, which is the
thing being reported.
"""
import argparse
import asyncio
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from suite_paths import add_client_path  # noqa: E402
add_client_path()
from aether import BusClient  # noqa: E402
from aether_instance import aether_emulator, read_bytes, unprefix  # noqa: E402
from emp_consts import emp_consts  # noqa: E402

# The sound contract's single authority. The Z80-side constants this file needs are
# consumed only inside the Z80 driver blob and reach NO listing (measured: the
# config-A .lst has 802 EQUs, six of them SND_*, all of them 68k mailbox addresses),
# so the source file is the authority — see tools/emp_consts.py for why.
SOUND_CONSTANTS = Path(__file__).resolve().parent.parent / "engine/sound/sound_constants.emp"

BOOT_FRAMES = 300          # autoplay settles (SoundTest_BootPing plays Moving Trucks)
DRUM_WAIT_FRAMES = 240     # generous: wait for the drum song's first $E2
TAIL_FRAMES = 24           # capture window after the request lands
MCLK_HZ = 53_693_175       # NTSC master clock (oracle-core scheduler)

# YM part-I/part-II port pairs, Z80-side raw addresses (crates/oracle-core/src/z80/bus.rs).
YM_A0, YM_A1, YM_A2, YM_A3 = 0x4000, 0x4001, 0x4002, 0x4003
REG_KEY, REG_DAC_DATA, REG_DAC_ENABLE = 0x28, 0x2A, 0x2B

# Mirror layout — engine/debug/sound_debug.emp IS the layout authority:
#   [0..47]  = Z80 $1F00..$1F2F (SND_REQ_BASE: request slots + status block)
#   [48..63] = Z80 $18F0..$18FF (SND_STATE_BASE: playback state)
# Every field offset below is DERIVED from those two bases and the field's own
# constant, so a constant that moves moves the decode with it. Nothing here is a
# typed-in number.
_C = emp_consts(SOUND_CONSTANTS)
_REQ, _STATE = _C["SND_REQ_BASE"], _C["SND_STATE_BASE"]
MIR_STAT_DAC_ACTIVE = _C["SND_STAT_DAC_ACTIVE"] - _REQ
MIR_STAT_SEQ_ACTIVE = _C["SND_STAT_SEQ_ACTIVE"] - _REQ
MIR_DAC_PHASE = 48 + _C["SND_DAC_PHASE"] - _STATE
MIR_ROM_LEN = 48 + _C["SND_ROM_LEN"] - _STATE   # 2 bytes, Z80 little-endian
MIR_FM6_CHAN_PTR = 48 + _C["SND_FM6_CHAN_PTR"] - _STATE
MIR_FM6_ADAPTIVE = 48 + _C["SND_FM6_ADAPTIVE"] - _STATE
# The DAC output rate. `SND_DAC_RATE_HZ` is a comptime fn call
# (`dac_rate_hz(SND_LOOP_CYC)`) and so is not a foldable const; the fn is
# `Z80_CLOCK_HZ / cyc` with integer division, which is the derivation repeated here
# and nothing else: 3579545 / 195 = 18356, exactly as sound_constants.emp's own
# comment states.
DAC_RATE_HZ = _C["Z80_CLOCK_HZ"] // _C["SND_LOOP_CYC"]

# HOW THE DRUM'S END IS FOUND, and the method that did NOT work. The first version
# of this file bounded the drum by a GAP in the $2A data stream — the first interval
# wider than 10 nominal sample periods (29,251 mclk = 0.54 ms). That is wrong, and
# wrong in the direction that reads as a clean result: the Timer-A tick is *the only
# thing that pauses streaming* (z80_sound_driver.emp's own words), for one
# Sequencer_Frame plus the bulk refill, once per frame — and L1 measures that pause
# at ~15% of a frame, i.e. ~2.5 ms, five times the threshold. So the gap method cut
# every drum off at the first tick and reported ~180 bytes for a 1,406-byte sample
# with a straight face.
#
# The bound used instead is the MIRROR's own SND_STAT_DAC_ACTIVE 1 -> 0 edge, read
# once per frame, which is the driver saying the sample reached its `.stop`. Its
# resolution is one frame and its over-count is bounded: after `.stop` the loop
# jumps to SndDrv_Idle, which writes the address port but never $4001, so no idle
# traffic inflates the count. A second, exact marker is reported beside it — the
# `$2A <- $80` DC-center write that `.stop` performs — so a reader can see the two
# agree rather than trust one.
DC_CENTER = 0x80


class Unmeasurable(RuntimeError):
    """The run could not ask its question — never reported as a pass."""


def parse_syms(lst):
    """-> ({label: addr}, {equ_name: value}) — the .lst's TWO namespaces.

    `lookup_symbol` sees only the first; every SND_* constant this file needs is an
    EQU and is invisible to it.
    """
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


async def rd(b, addr, n):
    """Raw bytes off the 68k bus, address masked to the bus's 24 real lines."""
    return bytes.fromhex(unprefix(await read_bytes(b, addr & 0xFFFFFF, n)))


class Mirror:
    """One frame's snapshot of the Z80 driver state, decoded off Sound_Dbg_Mirror."""

    def __init__(self, raw):
        self.dac_active = raw[MIR_STAT_DAC_ACTIVE]
        self.seq_active = raw[MIR_STAT_SEQ_ACTIVE]
        self.phase = raw[MIR_DAC_PHASE]
        self.rom_len = raw[MIR_ROM_LEN] | (raw[MIR_ROM_LEN + 1] << 8)
        self.fm6_ptr = raw[MIR_FM6_CHAN_PTR] | (raw[MIR_FM6_CHAN_PTR + 1] << 8)
        self.fm6_adaptive = raw[MIR_FM6_ADAPTIVE]

    def __str__(self):
        return (f"DAC_ACTIVE={self.dac_active} PHASE={self.phase} ROM_LEN={self.rom_len} "
                f"SEQ_ACTIVE={self.seq_active} FM6_ADAPTIVE={self.fm6_adaptive} "
                f"FM6_CHAN_PTR=${self.fm6_ptr:04X}")


async def mirror(b, base):
    return Mirror(await rd(b, base, 64))


class YmTap:
    """A live record-mode watch over the Z80's four YM ports, drained by cursor.

    Reconstructs (register, value, mclk) from the raw port stream the way the chip
    does: a $4000/$4002 write LATCHES a register select and a $4001/$4003 write is
    that latched register's data. The DAC stream is exactly the case that makes this
    necessary — the driver PARKS the address port on $2A and then writes bare $4001
    bytes at the sample rate, so a reader that only looked at $4000 writes would see
    none of the drum at all.
    """

    def __init__(self, b, base_addr=YM_A0, span=4):
        self.b = b
        self.base_addr, self.span = base_addr, span
        self.cursor = None        # persistent seq watermark, carried ACROSS polls
        self.events = []          # (seq, mclk, part, reg, value); value None = a select
        self.latch = {0: None, 1: None}
        self.dropped = self.matched = self.seen = 0
        self.seqs = []
        self.handle = None

    async def arm(self, label="ym"):
        r = await self.b.call("emulator/watchpoint_add",
                              {"addr": hex(self.base_addr), "len": self.span,
                               "write": True, "read": False,
                               "mode": "record", "label": label, "space": "bus"})
        self.handle = r["watch"]
        return r

    # The hits ring holds 4096 and a DAC drum writes ~300 bytes PER FRAME, so this
    # must be drained every frame and must resume where it left off. `cursor` is a
    # persistent seq watermark (the server filters `h.seq >= cursor + 1`), so it is
    # carried across polls. 100 per page, not 512: the Aether client reads
    # newline-delimited JSON through asyncio's 64 KiB line limit and a 512-hit page
    # overruns it, killing the connection mid-run (measured 2026-09-12).
    async def poll(self):
        while True:
            p = {"watch": self.handle, "limit": 100}
            if self.cursor is not None:
                p["cursor"] = str(self.cursor)
            r = await self.b.call("emulator/watchpoint_hits", p)
            for h in r.get("hits", []):
                seq = h["seq"]
                self.cursor = seq
                self.seqs.append(seq)
                addr = int(str(h["addr"]).replace("0x", ""), 16)
                val = int(str(h["value"]).replace("0x", ""), 16) & 0xFF
                mclk = h["mclk"]
                part = 0 if addr in (YM_A0, YM_A1) else 1
                if addr in (YM_A0, YM_A2):
                    self.latch[part] = val
                    self.events.append((seq, mclk, part, val, None))
                else:
                    self.events.append((seq, mclk, part, self.latch[part], val))
            self.dropped = r.get("dropped", self.dropped)
            self.seen = r.get("seen", self.seen)
            self.matched = r.get("matched", self.matched)
            if not r.get("truncated"):
                return

    def holes(self):
        """Gaps in the captured `seq` run — the AUTHORITATIVE lost-hit check.

        `dropped` is a whole-instrument counter of drop-oldest EVICTIONS and goes up
        for hits this reader already consumed, and for hits belonging to a different
        watch entirely, so it cannot answer "did I lose anything?". The doc on
        `Watchpoints` says it in as many words: *a gap in `seq` marks dropped hits*.
        """
        return sum(1 for a, c in zip(self.seqs, self.seqs[1:]) if c != a + 1)

    def data(self, reg, part=0, lo=None, hi=None):
        """Every DATA write to one register, mclk-bounded, in stream order."""
        return [(s, m, v) for (s, m, p, r, v) in self.events
                if v is not None and p == part and r == reg
                and (lo is None or m > lo) and (hi is None or m <= hi)]


async def run_until_drum_ends(b, base, tap, frames):
    """Step `frames` frames, draining the tap, sampling the mirror once per frame.

    Returns (samples, t_stop, why) where `samples` is [(frame_end_mclk, Mirror)] and
    `t_stop` is the mclk at the end of the first frame in which THE SAMPLE IN FLIGHT
    AT ENTRY has ended.

    ⚠ THE CRITERION IS SND_DAC_PHASE, NOT SND_STAT_DAC_ACTIVE, and getting that
    wrong is how this file first produced a confidently wrong number. An earlier
    version bounded the drum at the first frame reading DAC_ACTIVE = 0 — which is
    the EXACT FLAG `Snd_LoadSong` step 1 clears at the load. So the bound fired on
    the loader's own clear, the drum's remainder came out ~133 bytes in every
    target, and the suspiciously identical constant across three genuinely different
    songs was the confound telling on itself. SND_DAC_PHASE is written 0 only by
    `.stop` (and by the init sweep), so it is the driver saying the SAMPLE is over
    rather than saying the status mirror was zeroed.

    Second criterion, kept as a fallback: SND_ROM_LEN RISING. It only counts down
    inside one sample, so a rise means a new $E2 armed another — which is what
    happens when the new song has DAC drums of its own and the one-frame sampling
    never catches PHASE at 0 in between.
    """
    samples, t_stop, why, prev = [], None, None, None
    for _ in range(frames):
        r = await b.call("emulator/run_frames", {"frames": 1})
        await tap.poll()
        m = await mirror(b, base)
        samples.append((r["mclk"], m))
        if t_stop is None:
            if m.phase == 0:
                t_stop, why = r["mclk"], "SND_DAC_PHASE returned to 0 (`.stop` ran)"
            elif prev is not None and m.rom_len > prev:
                t_stop, why = r["mclk"], f"SND_ROM_LEN rose {prev} -> {m.rom_len} (a new $E2)"
        prev = m.rom_len
    return samples, t_stop, why


def frame_trace(samples, tap, t0, rate):
    """A compact per-frame table: the mirror's view beside the YM stream's view."""
    rows, prev = [], t0
    for t, m in samples:
        n = len(tap.data(REG_DAC_DATA, lo=prev, hi=t))
        rows.append(f"    DAC_ACTIVE={m.dac_active} PHASE={m.phase} "
                    f"ROM_LEN={m.rom_len:5d} | {n:4d} $2A bytes this frame")
        prev = t
        if m.phase == 0 and m.rom_len == 0 and n < 5:
            break
    return rows


async def clean_boot(b, lst_path):
    """Reset and settle with NO watch armed, so nothing records during the settle.

    Arming before this would put ~300 frames of unread FM traffic through the 4096
    ring and lap it, which is how the first version of this file reported thousands
    of 'dropped' events that had nothing to do with the measurement.
    """
    await b.call("emulator/watchpoint_clear", {"all": True})
    await b.call("emulator/reset", {})
    await b.call("emulator/load_symbols", {"path": lst_path})
    await b.call("emulator/run_frames", {"frames": BOOT_FRAMES})


async def start_drum(b, base, tap, out, tag):
    """Press C (the DAC drum-test song) and wait for a sample to really be in flight."""
    await b.call("emulator/press", {"buttons": ["c"], "frames": 2})
    for i in range(DRUM_WAIT_FRAMES):
        await b.call("emulator/run_frames", {"frames": 1})
        if tap is not None:
            await tap.poll()
        m = await mirror(b, base)
        if m.dac_active and m.rom_len > 0:
            out.append(f"  {tag}: drum in flight after {i + 1} frame(s): {m}")
            return m
    raise Unmeasurable(
        f"{tag}: no DAC sample was ever in flight within {DRUM_WAIT_FRAMES} frames of "
        f"pressing C — the drum-test song never reached an $E2, so there is no "
        f"mid-drum landing to measure")


async def frame_mclk(b):
    """One frame's master-clock span, measured rather than assumed."""
    a = (await b.call("emulator/status", {}))["mclk"]
    r = await b.call("emulator/run_frames", {"frames": 1})
    return r["mclk"] - a


# `.stop`'s epilogue runs in a few hundred Z80 T-states: Snd_ParkDac, $2A <- $80,
# and then (adaptive only) $2B <- $00 and the $28 FM6 re-key. So anything it writes
# lands within a fraction of a millisecond of the sample's LAST $2A byte, and that
# window is what separates `.stop`'s own key write from the new song's sequencer
# keying its channels later in the same frame. Without this split, L2's report of
# twelve $28 writes "between the load and the `.stop`" cannot say whether ANY of them
# came from `.stop` — and the whole of claim (ii) is about exactly that.
STOP_EPILOGUE_MCLK = MCLK_HZ // 10_000          # 0.1 ms


def stop_epilogue(tap, t_stop_exact):
    """The $2B and $28 writes inside `.stop`'s own epilogue window."""
    if t_stop_exact is None:
        return [], []
    hi = t_stop_exact + STOP_EPILOGUE_MCLK
    return (tap.data(REG_DAC_ENABLE, lo=t_stop_exact - 1, hi=hi),
            tap.data(REG_KEY, lo=t_stop_exact - 1, hi=hi))


def dc_center_at(tap, lo, hi):
    """`.stop`'s DC-center write, if the LAST $2A data byte in the window is $80.

    `.stop` ends the sample with `$2A <- $80`, so the last byte of a completed run
    should be exactly that. Checking only the LAST byte matters: `$80` is also a
    legitimate mid-sample silence byte, so "is there a $80 anywhere in the window"
    finds one early in almost any drum and dates the stop far too soon — which the
    first version of this file did, reporting a `.stop` at +9 ms that was a sample
    byte 1,000 bytes before the real one.
    """
    run = tap.data(REG_DAC_DATA, lo=lo, hi=hi)
    if run and run[-1][2] == DC_CENTER:
        return run[-1][1]
    return None


async def mid_drum_load(b, base, lst_path, button, rate, out, tag):
    """One mid-drum song load, start to finish, on a clean boot.

    Returns (tap, result-or-None, error-or-None, post-mirror).
    """
    await clean_boot(b, lst_path)
    tap = YmTap(b)
    await tap.arm(f"ym-{tag}")
    await start_drum(b, base, tap, out, tag)
    pre = await mirror(b, base)
    if pre.rom_len == 0 or not pre.dac_active:
        raise Unmeasurable(f"{tag}: the drum ended before the request could be posted")
    out.append(f"{tag}: '{button}' pressed mid-drum "
               f"(SND_ROM_LEN={pre.rom_len} bytes still to stream = "
               f"{pre.rom_len / rate * 1000:.1f} ms of drum left)")
    mark = tap.events[-1][1] if tap.events else 0
    await b.call("emulator/press", {"buttons": [button], "frames": 1})
    samples, t_stop, why = await run_until_drum_ends(b, base, tap, TAIL_FRAMES)
    post = samples[-1][1]

    ena = tap.data(REG_DAC_ENABLE, lo=mark)
    off = [x for x in ena if x[2] == 0x00]
    if not off:
        out.append(f"  {tag}: NO $2B <- $00 write followed the request")
        return tap, None, (f"{tag}: no $2B <- $00 write followed the request — "
                           f"Snd_LoadSong's step 1 did not land in this window, so this "
                           f"run is not the transition it claims to be"), post
    t_off = off[0][1]
    if t_stop is None:
        out.append(f"  {tag}: neither criterion fired inside {TAIL_FRAMES} frames")
        return tap, None, (f"{tag}: the drum never reached its `.stop` inside the capture "
                           f"window, so the remainder below would be a floor, not a "
                           f"measurement"), post
    # How late in the sample the load actually landed. The request is posted by
    # Sound_PlayMusic (which spins on MUSIC_SLOT == 0) and consumed by the Z80 at its
    # next mailbox poll, so "mid-drum" is NOT "the frame of the press" and the delay
    # is part of the result, not an aside.
    at_off = [m for t, m in samples if t >= t_off]
    rom_at_off = at_off[0].rom_len if at_off else None
    press_to_off_ms = (t_off - mark) / MCLK_HZ * 1000

    rest = tap.data(REG_DAC_DATA, lo=t_off, hi=t_stop)
    keys = tap.data(REG_KEY, lo=t_off, hi=t_stop)
    reen = [x for x in ena if x[1] > t_off and x[2] != 0x00]
    dc = dc_center_at(tap, t_off, t_stop)
    out.append(f"  {tag}: the load landed {press_to_off_ms:.1f} ms after the press "
               f"(SND_ROM_LEN was {rom_at_off} at that frame); the drum's end was "
               f"detected because {why}")
    out.append(f"  {tag} (i): $2B <- $00 at mclk {t_off}. From there to the drum's own "
               f"`.stop` the streaming loop emitted {len(rest)} more $2A DAC bytes "
               f"= {len(rest) / rate * 1000:.1f} ms of sample INTO A DISABLED DAC, over "
               f"{(t_stop - t_off) / MCLK_HZ * 1000:.1f} ms of wall time")
    out.append(f"  {tag} (i): the last $2A byte of that run is "
               f"{'$80 — `.stop`'"'"'s own DC-center write, so the run ended exactly where the driver ended it' if dc else 'NOT $80, so the frame-resolution bound caught the run slightly short or long of `.stop`'}")
    out.extend(frame_trace(samples, tap, mark, rate))
    out.append(f"  {tag} (i): next $2B RE-ENABLE (the new song's first $E2): "
               f"{[f'${v:02X} at +{(m - t_off) / MCLK_HZ * 1000:.1f} ms' for _, m, v in reen[:4]] or 'none within the capture window'}")
    t_last = rest[-1][1] if rest else None
    ep_ena, ep_key = stop_epilogue(tap, t_last)
    out.append(f"  {tag} (ii): `.stop`'s OWN epilogue (the 0.1 ms after the sample's last "
               f"$2A byte) wrote $2B {[f'${v:02X}' for _, _, v in ep_ena] or '(nothing)'} "
               f"and $28 {[f'${v:02X}' for _, _, v in ep_key] or '(nothing)'}")
    out.append(f"  {tag} (ii): all $28 key writes between the load and that `.stop`, most of "
               f"them the NEW song's own sequencer: "
               f"{[f'${v:02X}@+{(m - t_off) / MCLK_HZ * 1000:.2f}ms' for _, m, v in keys] or 'none'}")
    out.append(f"  {tag} (ii): the NEW song's FM6 state, which the dying drum's `.stop` "
               f"reads: FM6_ADAPTIVE={post.fm6_adaptive} FM6_CHAN_PTR=${post.fm6_ptr:04X}")
    out.append(f"  {tag}: mirror at +{TAIL_FRAMES} frames: {post}")
    return tap, {"t_off": t_off, "t_stop": t_stop, "rest": len(rest), "keys": keys,
                 "reen": reen, "dc": dc, "silent": len(rest), "why": why,
                 "rom_at_off": rom_at_off, "ep_key": ep_key, "ep_ena": ep_ena}, None, post


async def main_async(sock, rom, lst_path, poison, out):
    b = BusClient(socket_path=sock, client_id="songload", client_name="song_load_mid_drum")
    await b.connect()
    syms, equs = parse_syms(lst_path)
    # NOTE: `Snd_LoadSong` is deliberately NOT required. The Z80 driver is assembled
    # into its own blob (SIGIL_EMIT / emit_sound_blob) and NONE of its labels reach
    # this 68k listing — measured 2026-09-12: `grep Snd_LoadSong cfga.lst` is empty
    # while `Sound_PlayMusic` is at $B740. The Z80 half of this measurement is
    # reachable only through the YM write stream and the mirror, never by symbol.
    for need in ("Sound_PlayMusic", "Sound_DebugMirror", "Sound_Dbg_Mirror"):
        if need not in syms:
            raise Unmeasurable(
                f"{need} is not a label in {lst_path} — this is not the config-A "
                f"(music-capable, mirror-bearing) listing, and without the Z80-RAM "
                f"mirror this bus cannot read SND_STAT_DAC_ACTIVE at all "
                f"(read_memory refuses $A0xxxx)")
    base = syms["Sound_Dbg_Mirror"] & 0xFFFFFF
    rate = DAC_RATE_HZ
    out.append(f"  Sound_Dbg_Mirror ${base:06X} (68k RAM; the only readable view of Z80 RAM here)")
    out.append(f"  DAC rate = Z80_CLOCK_HZ {_C['Z80_CLOCK_HZ']} / SND_LOOP_CYC "
               f"{_C['SND_LOOP_CYC']} = {rate} Hz (derived from "
               f"engine/sound/sound_constants.emp, not from the listing — it carries "
               f"no SND_DAC_RATE_HZ EQU), master {MCLK_HZ} Hz")
    out.append(f"  mirror decode: DAC_ACTIVE@+{MIR_STAT_DAC_ACTIVE} PHASE@+{MIR_DAC_PHASE} "
               f"ROM_LEN@+{MIR_ROM_LEN} FM6_ADAPTIVE@+{MIR_FM6_ADAPTIVE} "
               f"FM6_CHAN_PTR@+{MIR_FM6_CHAN_PTR} (all derived from the bases)")

    fails, legs = [], []

    # ---------------- L0: the watch is live ---------------------------------------
    await clean_boot(b, lst_path)
    tap0 = YmTap(b, base_addr=(0x00A00000 if poison else YM_A0))
    if poison:
        out.append("  --poison: the YM watch is aimed at $A00000, which the Z80 never "
                   "writes and which carries no FM traffic — L0 MUST go loud")
    await tap0.arm("ym-L0")
    await b.call("emulator/run_frames", {"frames": 30})
    await tap0.poll()
    span = await frame_mclk(b)
    out.append(f"L0 THE WATCH IS LIVE: seen={tap0.seen} matched={tap0.matched} "
               f"dropped={tap0.dropped} holes={tap0.holes()} over 30 idle frames")
    if tap0.seen == 0:
        fails.append("L0: seen == 0 — the watch was never attached to the run; every "
                     "number below would be about an instrument, not about the driver")
    elif tap0.matched == 0:
        fails.append("L0: the YM watch matched NOTHING — live, but aimed where no FM "
                     "traffic goes, so every 'no writes' result below would be an "
                     "artefact of the aim")
    else:
        out.append(f"  L0: live — {tap0.matched} YM writes captured, {tap0.holes()} holes")
    legs.append("L0 the watch is live")
    if poison:
        out.append("LEGS RUN: 1 — L0 only (poison mode stops here by design)")
        return fails, 1, 1
    out.append(f"  one frame = {span} mclk = {span / MCLK_HZ * 1000:.3f} ms -> a running "
               f"sample should emit ~{span * rate // MCLK_HZ} $2A data bytes per frame")

    # ---------------- L1: a drum is sounding, from the STREAM ----------------------
    await clean_boot(b, lst_path)
    tap1 = YmTap(b)
    await tap1.arm("ym-L1")
    await start_drum(b, base, tap1, out, "L1")
    t0 = tap1.events[-1][1] if tap1.events else 0
    await b.call("emulator/run_frames", {"frames": 1})
    await tap1.poll()
    t1 = tap1.events[-1][1] if tap1.events else t0
    got = len(tap1.data(REG_DAC_DATA, lo=t0, hi=t1))
    want = (t1 - t0) * rate // MCLK_HZ
    out.append(f"L1 A DRUM IS SOUNDING: over the {(t1 - t0) / MCLK_HZ * 1000:.2f} ms after the "
               f"mirror first read DAC_ACTIVE=1, the stream carries {got} $2A DAC data "
               f"writes against {want} derived from SND_DAC_RATE_HZ "
               f"({got * 100 // max(want, 1)}% of nominal)")
    if got < want // 2:
        fails.append(f"L1: only {got} $2A data writes against {want} nominal — the mirror "
                     f"says a drum is streaming and the YM stream does not agree, so one "
                     f"of the two instruments is wrong and neither can carry L2/L3")
    legs.append("L1 a drum is sounding")

    # ---------------- L2 / L3 / L4: the transition, to every FM6 posture ------------
    # THREE targets, not one, because (ii) is a claim about what the dying drum's
    # `.stop` reads out of the NEWLY LOADED song, and the three songs this ROM ships
    # do not agree: Moving Trucks and HCZ2 are FM6-DEDICATE (SND_FM6_ADAPTIVE = 0),
    # and the ONLY adaptive song is the drum-test song itself — so the only way to
    # reach the adaptive branch of `.stop` at all is to load the drum song OVER its
    # own running drum, which is L4.
    tapA, resA, errA, postA = await mid_drum_load(
        b, base, lst_path, "a", rate, out, "L2 LOAD -> Moving Trucks")
    if errA:
        fails.append(errA)
    legs.append("L2 load -> Moving Trucks")

    tapU, resU, errU, postU = await mid_drum_load(
        b, base, lst_path, "up", rate, out, "L3 LOAD -> HCZ2")
    if errU:
        fails.append(errU)
    legs.append("L3 load -> HCZ2")

    tapC, resC, errC, postC = await mid_drum_load(
        b, base, lst_path, "c", rate, out, "L4 LOAD -> the drum song itself")
    if errC:
        fails.append(errC)
    legs.append("L4 load -> the drum song itself (the only adaptive target)")

    # ---------------- C1: the control — same drum, NO song request ------------------
    await clean_boot(b, lst_path)
    tapC1 = YmTap(b)
    await tapC1.arm("ym-C1")
    await start_drum(b, base, tapC1, out, "C1")
    c1_pre = await mirror(b, base)
    mark1 = tapC1.events[-1][1] if tapC1.events else 0
    out.append(f"C1 NO SONG REQUEST: the same drum, left alone "
               f"(SND_ROM_LEN={c1_pre.rom_len}); nothing is pressed")
    samples1, t_stop1, why1 = await run_until_drum_ends(b, base, tapC1, TAIL_FRAMES)
    if t_stop1 is None:
        fails.append("C1: the control's drum never reached its `.stop` inside the window, "
                     "so it cannot be compared with L2-L4")
        run1, ena1, key1, dc1 = [], [], [], None
    else:
        run1 = tapC1.data(REG_DAC_DATA, lo=mark1, hi=t_stop1)
        ena1 = tapC1.data(REG_DAC_ENABLE, lo=mark1, hi=t_stop1)
        key1 = tapC1.data(REG_KEY, lo=mark1, hi=t_stop1)
        dc1 = dc_center_at(tapC1, mark1, t_stop1)
        out.append(f"  C1: the drum ran {len(run1)} more $2A bytes = "
                   f"{len(run1) / rate * 1000:.1f} ms to its own `.stop` ({why1}), over "
                   f"{(t_stop1 - mark1) / MCLK_HZ * 1000:.1f} ms of wall time, with the DAC "
                   f"ENABLED throughout; last byte "
                   f"{'$80 — `.stop`'"'"'s DC-center write' if dc1 else 'not $80'}")
        out.extend(frame_trace(samples1, tapC1, mark1, rate))
        ep_ena1, ep_key1 = stop_epilogue(tapC1, run1[-1][1] if run1 else None)
        out.append(f"  C1: `.stop`'s OWN epilogue wrote $2B "
                   f"{[f'${v:02X}' for _, _, v in ep_ena1] or '(nothing)'} and $28 "
                   f"{[f'${v:02X}' for _, _, v in ep_key1] or '(nothing)'}")
        out.append(f"  C1: every $2B across the run: {[f'${v:02X}' for _, _, v in ena1] or 'none'}; "
                   f"every $28: {[f'${v:02X}' for _, _, v in key1] or 'none'}")
    out.append(f"  C1: mirror at +{TAIL_FRAMES} frames: {samples1[-1][1]}")
    legs.append("C1 no song request")

    # ---------------- C2: the control — song request with NO drum -------------------
    await clean_boot(b, lst_path)
    tapC2 = YmTap(b)
    await tapC2.arm("ym-C2")
    await b.call("emulator/run_frames", {"frames": 30})
    await tapC2.poll()
    mark2 = tapC2.events[-1][1] if tapC2.events else 0
    c2_pre = await mirror(b, base)
    out.append(f"C2 SONG REQUEST, NO DRUM: {c2_pre}")
    if c2_pre.dac_active:
        fails.append("C2: a DAC sample WAS in flight — this control is not the no-drum "
                     "case it claims to be")
    await b.call("emulator/press", {"buttons": ["a"], "frames": 1})
    for _ in range(TAIL_FRAMES):
        await b.call("emulator/run_frames", {"frames": 1})
        await tapC2.poll()
    ena2 = tapC2.data(REG_DAC_ENABLE, lo=mark2)
    dac2 = tapC2.data(REG_DAC_DATA, lo=mark2)
    out.append(f"  C2: $2A DAC data writes across the same {TAIL_FRAMES}-frame window: "
               f"{len(dac2)}; $2B writes {[f'${v:02X}' for _, _, v in ena2] or 'none'}")
    out.append(f"  C2: mirror at +{TAIL_FRAMES} frames: {await mirror(b, base)}")
    legs.append("C2 song request, no drum")

    # ---------------- holes: the authoritative capture check ------------------------
    for name, t in (("L0", tap0), ("L1", tap1), ("L2", tapA), ("L3", tapU), ("L4", tapC),
                    ("C1", tapC1), ("C2", tapC2)):
        if t.holes():
            fails.append(f"{name}: {t.holes()} gap(s) in the captured seq run — hits were "
                         f"lost before this reader saw them, so its counts are floors, "
                         f"not measurements")

    def keyset(res):
        return [f"${v:02X}" for _, _, v in res["keys"]] if res else "n/a"

    out.append("")
    out.append("WHAT THE CONTROLS RULE OUT")
    out.append(f"  the part of the drum streamed into a DISABLED DAC, in $2A bytes: "
               f"L2 {resA['silent'] if resA else 'n/a'} · L3 {resU['silent'] if resU else 'n/a'} · "
               f"L4 {resC['silent'] if resC else 'n/a'} · C1 0 — with NO load the drum's "
               f"{len(run1)} remaining bytes all go out with the DAC ENABLED")
    def epset(res):
        return [f"${v:02X}" for _, _, v in res["ep_key"]] if res else "n/a"
    out.append(f"  what the drum's OWN `.stop` epilogue keyed: L2 {epset(resA)} · "
               f"L3 {epset(resU)} · L4 {epset(resC)} · "
               f"C1 {[f'${v:02X}' for _, _, v in ep_key1] if t_stop1 else 'n/a'} (no load)")
    out.append(f"  FM6 posture the dying drum's `.stop` read: "
               f"L2 ADAPTIVE={postA.fm6_adaptive} PTR=${postA.fm6_ptr:04X} · "
               f"L3 ADAPTIVE={postU.fm6_adaptive} PTR=${postU.fm6_ptr:04X} · "
               f"L4 ADAPTIVE={postC.fm6_adaptive} PTR=${postC.fm6_ptr:04X} · "
               f"C1 ADAPTIVE={c1_pre.fm6_adaptive} PTR=${c1_pre.fm6_ptr:04X} (unreloaded)")
    out.append(f"  a load with NO drum (C2) moved {len(dac2)} DAC bytes and wrote "
               f"$2B {[f'${v:02X}' for _, _, v in ena2]}")

    out.append(f"LEGS RUN: {len(legs)} — " + ", ".join(legs))
    if len(legs) != 7:
        fails.append(f"only {len(legs)} of 7 legs ran — an unrun leg is not a pass")
    return fails, len(legs), 7


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", required=True, help="the config-A ROM (music-capable)")
    ap.add_argument("--lst", required=True, help="its listing")
    ap.add_argument("--poison", action="store_true",
                    help="aim the YM watch where nothing writes; L0 must go loud")
    a = ap.parse_args()
    out = []
    try:
        with aether_emulator(a.rom, symbols=a.lst) as sock:
            fails, ran, want = asyncio.run(main_async(sock, a.rom, a.lst, a.poison, out))
    except Unmeasurable as e:
        print("\n".join(out))
        print(f"\nUNMEASURABLE: {e}")
        return 2
    print("\n".join(out))
    if a.poison:
        if fails:
            print("\nPOISON OK — L0 went loud, as it must:")
            for f in fails:
                print(f"  * {f}")
            return 0
        print("\nPOISON FAILED: L0 PASSED on a watch aimed where nothing writes. The "
              "liveness leg is vacuous and every 'no writes' result is worthless.")
        return 1
    if fails:
        print("\nRESULT: COULD NOT MEASURE CLEANLY")
        for f in fails:
            print(f"  * {f}")
        return 1
    print(f"\nRESULT: MEASURED — {ran} of {want} legs (5 drives + 2 controls). The numbers "
          f"above are the finding; this witness asserts only that it could ask its "
          f"question, never what the answer should have been.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
