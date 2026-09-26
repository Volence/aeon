#!/usr/bin/env python3
"""psg_env_attack_witness — does a PSG volume envelope's byte 0 sound on the note-on tick?

THE CLAIM UNDER TEST. Both reference drivers apply envelope byte 0 on the tick a note
attacks and byte 1 on the next: Sonic 2's zPSGUpdateTrack runs zPSGDoNoteOn and then
zPSGDoVolFX in the same frame after zFinishTrackUpdate zeroed VolFlutter
(s2disasm/s2.sounddriver.asm), and Sonic 3's zUpdatePSGTrack falls from the new note into
.skip_fill -> zDoVolEnv after zFinishTrackUpdate zeroed VolEnv
(skdisasm/Sound/Z80 Sound Driver.asm). Until 2026-09-26 this engine did not: ModUpdate
(and so PsgEnvUpdate) runs BEFORE Sequencer_Channel within a tick, and the attack zeroed
the contour, so the attack sounded delta 0 and every contour played one tick late and one
tick long. The fix is `PsgEnvAttack` (engine/sound/sound_sequencer.emp), the volume tail of
every PSG attack. Measured consequence before the fix: the Sonic 2 noise hat +1.18 dB
against real Sonic 2 (docs/research/2026-09-26-s2-music-volume.md).

THE INSTRUMENT. The Z80's own PSG writes on the bus watch surface: since oracle's
Z80-WATCH-TAP change a Z80 write to $7F11 reaches a `bus` watch at $A07F11 with
`via: "z80"` and a per-hit mclk (see tools/song_load_mid_drum_witness.py for the contract
citation). Only `via == "z80"` hits are kept. Each hit is a PSG byte; a latch byte with
bit 4 set is a volume write, (b >> 5) & 3 its channel, b & $0F its attenuation.

THE SUBJECTS are SFX, because the canonical ROMs play no music. An SFX is queued the way
Sound_PlaySFX queues one (the id into Sfx_Ring_Buf[Wr], then Wr advanced), from a paused
machine, so Sound_DrainSfxRing posts it on the next frame.

THE EXPECTATION IS DERIVED, NOT TYPED. For each subject the SFX's event list comes from
tools/sfx_transcode.py run on the shipped source, and the envelope body from
tools/gen_sound_tables.py's `_PSG_VOL_ENVS` (the generator the Z80 table is emitted from).
`simulate()` then plays that list through a transcription of the engine's per-tick order
(ModUpdate -> PsgEnvUpdate, then Sequencer_Channel -> the attack) under TWO attack rules:
  REFERENCE  the attack folds byte 0 (cursor 1 afterwards) — S2/S3K, and the fix;
  LATE       the attack writes delta 0 and PsgEnvUpdate reads byte 0 next tick — the
             pre-fix engine.
It predicts, per tick, the LAST volume write to the subject's channel as an attenuation
delta (or SILENT for a key-off). The unknown base attenuation (sc_volume through
Psg_VolToAtten and the SFX gain fold, constant over one SFX) is solved, not typed: a
subject MATCHES a rule if some base 0..15 makes every predicted write equal the observed
one, including the bit-4 clamp to $0F.

Tick numbers come from the write times: T is the Timer-A overflow period derived from
sound_constants.emp (SND_FRAME_MILLIHZ through timerAReload's formula; one Timer-A count
is 144 YM clocks = 1008 mclk). The hardware timer is periodic, but the driver services an
overflow LATE when it lands in a 68k DMA window (the LS-12 DMA guard defers the tick; the
latched overflow is serviced after the window) or behind a 68k bus hold, so each tick's
writes sit at grid + delay, delay >= 0. MEASURED on the first run (s4.debug.bin, fix
applied): the SFX's first tick came 0.10 and 0.27 tick late in L1 and L2, every later gap
within 0.06 of an integer. Each gap between write clusters is therefore rounded to whole
ticks separately (delays cannot accumulate), and a gap more than 0.4 tick from an integer
is UNMEASURABLE rather than rounded: past that, the rounding could pick the wrong tick.
The largest deviation seen is printed on every run.

LEGS (count asserted):
  L0 THE WATCH IS LIVE   z80-attributed PSG hits were recorded at all.
  L1 $42 INSTA-SHIELD    noise route, env $0A = 1,0,0,0,0,1,... — byte 0 differs from
                         byte 1, so the two rules predict different VALUES at the attack.
  L2 $B6 DASH            noise route, a 6-tick rest then env $1D = 0,0,0,0,1,... — the
                         rules predict the same values at different TICKS.
  C1 $62 JUMP (control)  PSG1, env $0D = 0,HOLD — the two rules predict the same writes.
                         It must match; it cannot discriminate, and says so. It is here
                         to show the decode and the tick model are right on a subject
                         the fix does not move.
For L1 and L2 the leg REQUIRES that the two rules' predictions differ (derived per run,
so a subject that stops discriminating is refused loudly) and that the observation
matches REFERENCE and not LATE.

Exit: 0 all legs pass; 1 a leg failed (the engine plays LATE, or matches neither rule);
2 UNMEASURABLE (no emulator, dead watch, wrong listing, off-grid timing).

RUN:  python3 tools/psg_env_attack_witness.py [--rom s4.debug.bin] [--lst s4.debug.lst]
Wired: tools/keepalive_manifest.toml (keepalive lane, s4.debug.bin by default).
"""
from __future__ import annotations

import argparse
import asyncio
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from suite_paths import add_client_path  # noqa: E402
add_client_path()
from aether import BusClient  # noqa: E402
from aether_instance import aether_emulator, read_bytes, unprefix, write_bytes  # noqa: E402
from emp_consts import emp_consts  # noqa: E402
import gen_sound_tables as gst  # noqa: E402
import sfx_transcode as st  # noqa: E402

AEON = HERE.parent
SOUND_CONSTANTS = AEON / "engine/sound/sound_constants.emp"

PSG_PORT_BUS = 0xA07F11     # the Z80's $7F11, as oracle reports a Z80 hit (contract §6)
VIA_Z80 = "z80"
MCLK_PER_TIMERA_COUNT = 7 * 144   # one Timer-A count = 144 YM clocks, YM clock = MCLK/7
BOOT_FRAMES = 240
QUIET_FRAMES = 30          # per-leg pre-window: the subject channel must be silent
TAIL_FRAMES = 30           # past the SFX's last tick
SILENT = "SILENT"

# (leg, sfx id name in sound_ids.emp, must discriminate?)
SUBJECTS = [("L1", "SFXID_INSTASHIELD", True),
            ("L2", "SFXID_DASH", True),
            ("C1", "SFXID_JUMP", False)]

# Engine channel routes (song_packer CHROUTE_*) -> PSG channel number in the latch byte.
ROUTE_TO_PSG_CH = {6: 0, 7: 1, 8: 2, 9: 3}


class Unmeasurable(RuntimeError):
    """The run could not ask its question — never reported as a pass."""


# --------------------------------------------------------------------------- derivations
def timer_a_period_mclk() -> int:
    """The Timer-A overflow period in mclk, from SND_FRAME_MILLIHZ via timerAReload's own
    formula (sound_constants.emp: `1024 - 10^12 / (mhz * 18773)`, integer division). The
    formula is restated because a comptime fn call does not fold in emp_consts; the input
    comes from the source."""
    c = emp_consts(SOUND_CONSTANTS)
    mhz = c["SND_FRAME_MILLIHZ"]
    n = 1024 - (1000000000000 // (mhz * 18773))
    if "SND_TIMERA_N" in c and c["SND_TIMERA_N"] != n:
        raise Unmeasurable(f"restated timerAReload gives N={n}, the source folds "
                           f"{c['SND_TIMERA_N']}: the formula drifted")
    return MCLK_PER_TIMERA_COUNT * (1024 - n)


def env_bodies() -> dict:
    return {eid: list(body) for eid, _name, body in gst._PSG_VOL_ENVS}


def sfx_channel(sfx_id: int) -> dict:
    """The shipped SFX's PSG channel (events + route), from the transcoder on its source."""
    d = st.sfx_source_dir(sfx_id)
    fname = st._CORE_SFX_FILENAMES[sfx_id]
    src = open(os.path.join(d, fname)).read()
    desc = st.transcode_sfx_source(src, sfx_id)
    psg = [ch for ch in desc["channels"] if ch["route"] in ROUTE_TO_PSG_CH]
    if len(psg) != 1:
        raise Unmeasurable(f"sfx ${sfx_id:02X}: expected exactly one PSG channel, found "
                           f"{[ch['route'] for ch in psg]}")
    return psg[0]


# --------------------------------------------------------------------------- the model
def simulate(events, bodies, rule):
    """Per-tick last volume write to the channel: {tick: delta | SILENT}.

    A transcription of the SFX slot's tick: ModUpdate (PSG vol-env: PsgEnvUpdate when an
    env is set and the channel is keyed), then Sequencer_Channel (dur_count counts down;
    at 0, zero-tick events run until a note, rest or end). `rule` is "REFERENCE" or
    "LATE" and differs ONLY in the attack. Also returns the tick count to the end."""
    writes = {}
    st_ = {"keyed": False, "env": 0, "cur": 0, "out": 0, "defdur": 1}

    def write(t, v):
        writes[t] = v

    def note_off(t):
        st_["keyed"] = False
        write(t, SILENT)

    def env_update(t):
        body = bodies[st_["env"]]
        for _ in range(len(body) + 1):
            b = body[st_["cur"]]
            if b == gst._CTL_LOOP:
                st_["cur"] = 0
                continue
            if b == gst._CTL_SUSTAIN:
                return
            if b == gst._CTL_REST:
                note_off(t)
                return
            st_["cur"] += 1
            if b != st_["out"]:
                st_["out"] = b
                write(t, b)
            return
        raise Unmeasurable("an envelope body loops without a level byte")

    def attack(t):
        st_["keyed"] = True
        st_["cur"] = 0
        st_["out"] = 0
        if rule == "REFERENCE" and st_["env"]:
            b = bodies[st_["env"]][0]
            if b == gst._CTL_REST:
                note_off(t)
                return
            if b < 0x80:
                st_["out"] = b
                st_["cur"] = 1
        write(t, st_["out"])

    evs = list(events)
    i, dur, t = 0, 1, 0
    while t < 4096:
        if st_["keyed"] and st_["env"]:
            env_update(t)
        dur -= 1
        if dur == 0:
            while True:
                if i >= len(evs):
                    raise Unmeasurable("the SFX ran off its event list without an End")
                e = evs[i]
                i += 1
                k = type(e).__name__
                if k == "Vol":
                    write(t, st_["out"])
                elif k == "PsgEnv":
                    st_["env"], st_["cur"] = e.env_id, 0
                elif k == "SetDur":
                    st_["defdur"] = e.ticks
                elif k in ("PsgNoise", "ModSet"):
                    pass
                elif k == "Rest":
                    dur = st_["defdur"]
                    note_off(t)
                    break
                elif k == "Note":
                    dur = st_["defdur"]
                    attack(t)
                    break
                elif k == "NoteDur":
                    dur = e.dur
                    if e.pitch & 0x80:
                        st_["keyed"] = True      # held: no hook, contour continues
                    else:
                        attack(t)
                    break
                elif k == "End":
                    note_off(t)                  # Sfx_Restore: no music under it
                    return writes, t
                else:
                    raise Unmeasurable(f"the model has no rule for event {k}; extend "
                                       "simulate() before trusting this subject")
        t += 1
    raise Unmeasurable("the SFX did not end within 4096 ticks")


def predicted_atten(model, base):
    out = {}
    for t, v in model.items():
        if v == SILENT:
            out[t] = 0x0F
        else:
            s = base + v
            out[t] = 0x0F if (s & 0x10) else s
    return out


def matching_bases(model, observed):
    return [b for b in range(16) if predicted_atten(model, b) == observed]


# --------------------------------------------------------------------------- the tap
class PsgTap:
    def __init__(self, b):
        self.b, self.cursor, self.handle = b, None, None
        self.hits = []            # (mclk, byte)
        self.seen = self.matched = self.z80 = self.foreign = 0
        self.seqs = []

    async def arm(self):
        r = await self.b.call("emulator/watchpoint_add",
                              {"addr": hex(PSG_PORT_BUS), "len": 1, "write": True,
                               "read": False, "mode": "record", "label": "psg",
                               "space": "bus"})
        self.handle = r["watch"]

    async def poll(self):
        while True:
            p = {"watch": self.handle, "limit": 100}
            if self.cursor is not None:
                p["cursor"] = str(self.cursor)
            r = await self.b.call("emulator/watchpoint_hits", p)
            for h in r.get("hits", []):
                self.cursor = h["seq"]
                self.seqs.append(h["seq"])
                if h.get("via") != VIA_Z80:
                    self.foreign += 1
                    continue
                self.z80 += 1
                self.hits.append((h["mclk"], int(str(h["value"]).replace("0x", ""), 16) & 0xFF))
            self.seen = r.get("seen", self.seen)
            self.matched = r.get("matched", self.matched)
            if not r.get("truncated"):
                return

    def holes(self):
        return sum(1 for a, c in zip(self.seqs, self.seqs[1:]) if c != a + 1)

    def vol_writes(self, ch, lo):
        return [(m, v & 0x0F) for (m, v) in self.hits
                if m > lo and (v & 0x90) == 0x90 and ((v >> 5) & 3) == ch]


GRID_TOLERANCE = 0.4
CLUSTER_GAP = 0.5          # writes closer than this (in ticks) belong to one tick's burst


def ticks_of(writes, period):
    """[(mclk, atten)] -> ({tick: last atten}, worst deviation from the grid), tick 0 =
    the first write's cluster. Writes within CLUSTER_GAP of the cluster's first write are
    one tick; each later cluster is placed by rounding its gap to the previous one."""
    if not writes:
        return {}, 0.0
    out, tick, prev, worst = {}, 0, writes[0][0], 0.0
    for m, v in writes:
        gap = (m - prev) / period
        if gap > CLUSTER_GAP:
            n = round(gap)
            worst = max(worst, abs(gap - n))
            if abs(gap - n) > GRID_TOLERANCE:
                raise Unmeasurable(f"a write gap of {gap:.3f} ticks is off the Timer-A grid "
                                   f"(T = {period} mclk): the tick model does not hold here")
            tick += n
            prev = m
        out[tick] = v
    return out, worst


# --------------------------------------------------------------------------- driving
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


def sfx_id_of(name):
    txt = (AEON / "games/sonic4/config/sound_ids.emp").read_text()
    m = re.search(r"pub const %s\s*:\s*SfxId\s*=\s*\$([0-9A-Fa-f]+)" % name, txt)
    if not m:
        raise Unmeasurable(f"{name} is not declared in games/sonic4/config/sound_ids.emp")
    return int(m.group(1), 16)


async def rd(b, addr, n):
    return bytes.fromhex(unprefix(await read_bytes(b, addr & 0xFFFFFF, n)))


async def run_leg(b, tap, syms, mask, leg, name, must_disc, bodies, period, out, fails):
    sfx = sfx_id_of(name)
    ch = sfx_channel(sfx)
    psg_ch = ROUTE_TO_PSG_CH[ch["route"]]
    ref, n_ticks = simulate(ch["events"], bodies, "REFERENCE")
    late, _ = simulate(ch["events"], bodies, "LATE")
    out.append(f"{leg} {name} ${sfx:02X}: PSG channel {psg_ch} (route {ch['route']}), "
               f"{n_ticks} ticks to End")
    out.append(f"  model REFERENCE (byte 0 on the attack): {sorted(ref.items())}")
    out.append(f"  model LATE      (byte 0 one tick late): {sorted(late.items())}")
    if must_disc and ref == late:
        fails.append(f"{leg}: the two rules predict the SAME writes for {name}, so this "
                     f"subject cannot discriminate; pick another")
        return
    await tap.poll()
    lo = tap.hits[-1][0] if tap.hits else 0
    await b.call("emulator/run_frames", {"frames": QUIET_FRAMES})
    await tap.poll()
    pre = tap.vol_writes(psg_ch, lo)
    if pre:
        raise Unmeasurable(f"{leg}: PSG channel {psg_ch} took {len(pre)} volume write(s) "
                           f"before the SFX was queued; something else owns it")
    lo = tap.hits[-1][0] if tap.hits else lo
    ring, wr_p, rd_p = syms["Sfx_Ring_Buf"], syms["Sfx_Ring_Wr"], syms["Sfx_Ring_Rd"]
    wr, rdc = (await rd(b, wr_p, 1))[0], (await rd(b, rd_p, 1))[0]
    if wr != rdc:
        raise Unmeasurable(f"{leg}: the SFX ring is not empty (Wr={wr} Rd={rdc})")
    await write_bytes(b, (ring + wr) & 0xFFFFFF, f"{sfx:02X}")
    await write_bytes(b, wr_p & 0xFFFFFF, f"{(wr + 1) & mask:02X}")
    left = n_ticks + TAIL_FRAMES
    while left > 0:
        step = min(10, left)
        await b.call("emulator/run_frames", {"frames": step})
        await tap.poll()
        left -= step
    got = tap.vol_writes(psg_ch, lo)
    if not got:
        raise Unmeasurable(f"{leg}: no volume write reached PSG channel {psg_ch} after "
                           f"{name} was queued — the SFX did not play")
    obs, worst = ticks_of(got, period)
    out.append(f"  observed ({len(got)} writes):              {sorted(obs.items())}")
    out.append(f"  worst gap deviation from the Timer-A grid: {worst:.3f} tick "
               f"(tolerance {GRID_TOLERANCE})")
    rb, lb = matching_bases(ref, obs), matching_bases(late, obs)
    out.append(f"  bases matching REFERENCE: {rb or 'none'}   LATE: {lb or 'none'}")
    if not rb:
        fails.append(f"{leg}: the observed writes match the REFERENCE rule for no base "
                     f"attenuation" + (" — they match LATE: byte 0 lands a tick late"
                                       if lb else " (nor LATE)"))
    elif must_disc and lb:
        fails.append(f"{leg}: the observation matches BOTH rules, so it discriminates "
                     f"nothing")
    else:
        out.append(f"  {leg}: PASS — matches REFERENCE" +
                   ("" if must_disc else " (control: both rules agree on this subject)"))


async def main_async(sock, lst, out):
    b = BusClient(socket_path=sock, client_id="psgenvattack",
                  client_name="psg_env_attack_witness")
    await b.connect()
    await b.call("emulator/load_symbols", {"path": lst})
    syms, _equs = parse_syms(lst)
    for need in ("Sfx_Ring_Buf", "Sfx_Ring_Wr", "Sfx_Ring_Rd"):
        if need not in syms:
            raise Unmeasurable(f"{need} is not in {lst} — wrong ROM/listing pair?")
    mask = emp_consts(SOUND_CONSTANTS)["SFX_RING_MASK"]
    period = timer_a_period_mclk()
    bodies = env_bodies()
    out.append(f"  Timer-A tick = {period} mclk (from SND_FRAME_MILLIHZ); "
               f"SFX_RING_MASK = {mask}")
    tap = PsgTap(b)
    await tap.arm()
    await b.call("emulator/run_frames", {"frames": BOOT_FRAMES})
    fails, legs = [], []
    for leg, name, disc in SUBJECTS:
        await run_leg(b, tap, syms, mask, leg, name, disc, bodies, period, out, fails)
        legs.append(leg)
    await tap.poll()
    out.append(f"L0 THE WATCH IS LIVE: seen={tap.seen} matched={tap.matched} "
               f"z80={tap.z80} foreign={tap.foreign} holes={tap.holes()}")
    if tap.z80 == 0:
        raise Unmeasurable("the PSG watch recorded no z80-attributed write")
    if tap.holes():
        raise Unmeasurable(f"{tap.holes()} gap(s) in the captured seq run: hits were lost")
    legs.insert(0, "L0")
    out.append(f"LEGS RUN: {len(legs)} — {', '.join(legs)}")
    if len(legs) != 1 + len(SUBJECTS):
        fails.append(f"only {len(legs)} of {1 + len(SUBJECTS)} legs ran")
    return fails


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", default="s4.debug.bin")
    ap.add_argument("--lst", default="s4.debug.lst")
    a = ap.parse_args()
    out = []
    try:
        with aether_emulator(a.rom, symbols=a.lst) as sock:
            fails = asyncio.run(main_async(sock, a.lst, out))
    except Unmeasurable as e:
        print("\n".join(out))
        print(f"\nUNMEASURABLE: {e}")
        return 2
    print("\n".join(out))
    if fails:
        print("\nRESULT: FAIL")
        for f in fails:
            print(f"  * {f}")
        return 1
    print("\nRESULT: PASS — L0 + 3 subjects: envelope byte 0 sounds on the attack tick "
          "(L1 by value, L2 by tick), and the control matches the same model.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
