#!/usr/bin/env python3
"""psg_song_switch_witness — after a song switch, does any PSG channel sound a tone the
PREVIOUS song latched? (S2CLIP CPZ drone, 2026-09-27.)

THE DEFECT THIS EXISTS FOR. The owner, on the Sonic 2 clip build: "CPZ has like a louder
droning psg channel ... a straight noise in it that sounds like a sine wave". Measured: after
the region switch from Emerald Hill to Chemical Plant, PSG1 held 1398 Hz (divisor 80) and PSG2
589 Hz (divisor 190) at attenuation 7 for as long as CPZ played. The switch HAD silenced the
chip (Snd_LoadSong -> Sequencer_StopAll). CPZ's PSG1/PSG2 are `smpsStop` in the source,
converted to `Vol, End`, and the sequencer's volume hook wrote that volume to the chip on a
channel that never keyed a note. The SN76489 has no key-off: an attenuation write sounds
whatever divisor the tone latch still holds, and the latch still held EHZ's last notes.
s2_music_balance never saw it, because it requested CPZ before EHZ had latched any PSG note.

THE RULE (derived from the write stream alone, no song model). At each song LOAD (the Z80's
own write of 0 to MUSIC_SLOT, which Snd_LoadSong makes after silencing the chip), every PSG
latch is the previous song's. So after a load, the first NON-SILENT attenuation write to a
tone channel must come after a divisor write to that channel since the load, and the first
non-silent write to the noise channel after a noise-control write since the load. Any other
non-silent write sounds the previous song's latch: that is a STALE SOUND and fails.
Sonic 2 and S3K obey this by construction (a PSG volume command only stores; the chip is
written by the note/track update: S2 cfChangePSGVolume / zPSGUpdateVol, S3K cfSetVolume /
zStoreTrackVolume), and every engine note-on latches its divisor before its volume
(Psg_NoteOn -> Psg_EmitDivisor -> PsgEnvAttack).

THE ROUTE, one boot of s4.debug.bin (the canonical DEBUG ROM carries both Sonic 2 songs,
SONG_S2_EHZ and SONG_S2_CPZ, games/sonic4/config/sound_ids.emp; its regions name song 0, so
the region service never competes with the pokes):
  boot    BOOT_FRAMES.
  ehz     Music_Want = SONG_S2_EHZ; PLAY_FRAMES (EHZ latches notes on PSG1/PSG2/noise).
  cpz     Music_Want = SONG_S2_CPZ; PLAY_FRAMES (CPZ keys no PSG1/PSG2 note).
  back    Music_Want = SONG_S2_EHZ (CPZ -> EHZ); PLAY_FRAMES.
  sfx     a PSG SFX (SFXID_INSTASHIELD) queued, and once the driver has taken it off the ring,
          Music_Want = SONG_S2_CPZ: a switch mid-SFX; PLAY_FRAMES.
The songs are switched through the region service's own two bytes (Music_Want vs
Music_Current), the path the clip's region crossing takes.

PREMISES (unmet = COULD NOT RUN, exit 2, never a pass): each leg's request is consumed by a
load; before each switch AWAY from EHZ, PSG1 and PSG2 hold a non-zero divisor and have
sounded (otherwise the latch is 0, ultrasonic, and the switch tests nothing: exactly the
blind spot that hid this); the SFX leg's SFX left the ring before the switch; the PSG watch
lost no hit.

Also printed, per leg: every PSG channel's longest audible run at one attenuation and one
divisor after the load (the drone, as a number: frames, divisor, Hz, attenuation).

Exit 0 all held · 1 a stale sound · 2 could not run. Headless oracle-aether subprocess, never
MCP. Wired: tools/keepalive_manifest.toml.

Usage:
    python3 tools/psg_song_switch_witness.py --rom s4.debug.bin --lst s4.debug.lst
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
from suite_paths import add_client_path  # noqa: E402
add_client_path()
from aether import BusClient  # noqa: E402
from aether_instance import aether_emulator  # noqa: E402
import clip_rom_bake as CRB  # noqa: E402
from emp_consts import emp_consts  # noqa: E402
import region_music_witness as RMW  # noqa: E402
from psg_env_attack_witness import PSG_PORT_BUS, SOUND_CONSTANTS, VIA_Z80, sfx_id_of  # noqa: E402

BOOT_FRAMES = 240
PLAY_FRAMES = 600          # > EHZ's first PSG1/PSG2 note (~230 frames after its load, measured)
LOAD_WAIT = 30             # frames a posted request may take to be consumed
PSG_CLOCK_HZ = 3579545     # NTSC PSG clock (MCLK / 15)
SFX_NAME = "SFXID_INSTASHIELD"
SILENCE_BURST = [0x9F, 0xBF, 0xDF, 0xFF]   # Psg_SilenceAll: what a load writes first


class CouldNotRun(Exception):
    pass


# --------------------------------------------------------------------------- the rule
def stale_sounds(writes, loads):
    """writes: [(seq, byte)] PSG port writes in bus order; loads: [seq] of each song load.
    Returns [(load_index, seq, channel, attenuation)] for every non-silent attenuation write
    that sounds a latch the previous song left: a tone channel with no divisor write since
    the load, the noise channel with no noise-control write since the load."""
    out = []
    loads = sorted(loads)
    fresh = None                # per-channel "latched since the current load"
    li = -1
    latch = None
    for seq, v in sorted(writes):
        while li + 1 < len(loads) and loads[li + 1] < seq:
            li += 1
            fresh = [False] * 4
        if v & 0x80:
            latch = (v >> 5) & 3
            if v & 0x10:
                att = v & 0x0F
                if fresh is not None and att != 0x0F and not fresh[latch]:
                    out.append((li, seq, latch, att))
            elif fresh is not None:
                fresh[latch] = True        # tone low nibble, or the noise control byte
        elif fresh is not None and latch is not None and latch < 3:
            fresh[latch] = True            # tone high bits (data byte)
    return out


def replay(writes):
    """[(seq, byte)] -> [(seq, attens[4], divisors[3], noise_ctrl)] the chip state after
    each write."""
    att, div, noise, latch, out = [15] * 4, [0] * 3, None, None, []
    for seq, v in sorted(writes):
        if v & 0x80:
            latch = (v >> 5) & 3
            if v & 0x10:
                att[latch] = v & 0x0F
            elif latch < 3:
                div[latch] = (div[latch] & 0x3F0) | (v & 0x0F)
            else:
                noise = v & 7
        elif latch is not None and latch < 3:
            div[latch] = (div[latch] & 0x0F) | ((v & 0x3F) << 4)
        out.append((seq, list(att), list(div), noise))
    return out


def locate_loads(psg, req_frames, wait=None):
    """psg: [(frame, byte)] Z80 PSG writes in write order; req_frames: the frame each music
    request was observed on the bus, in order. -> per request, the index into psg of the first
    silence burst (SILENCE_BURST, back to back) at or after the request and within `wait`
    frames of it, after the previous request's load; None where there is none.
    The Z80's own consume of MUSIC_SLOT is not a bus event and Z80 RAM is not readable in the
    aether slice (both measured), so a load is located by the first thing Snd_LoadSong
    writes: the chip silence (Sequencer_StopAll -> Psg_SilenceAll)."""
    wait = LOAD_WAIT if wait is None else wait
    bursts = [i for i in range(len(psg) - 3)
              if [psg[i + j][1] for j in range(4)] == SILENCE_BURST]
    out, floor = [], -1
    for rf in req_frames:
        hit = next((i for i in bursts if i > floor and rf <= psg[i][0] <= rf + wait), None)
        out.append(hit)
        if hit is not None:
            floor = hit
    return out


def framed_states(psg, n_frames):
    """psg: [(frame, byte)] in write order -> per frame 0..n_frames, the chip state
    (attens, divisors, noise_ctrl) after that frame's last write."""
    states = replay([(i, v) for i, (_f, v) in enumerate(psg)])
    framed, cur, k = [], ([15] * 4, [0] * 3, None), 0
    for f in range(n_frames + 1):
        while k < len(states) and psg[states[k][0]][0] <= f:
            cur = tuple(states[k][1:])
            k += 1
        framed.append(cur)
    return framed


def describe_runs(framed, lo, hi):
    """One line: each channel's longest audible unchanged run over frames lo..hi."""
    names = ["PSG1", "PSG2", "PSG3", "NOISE"]
    runs, parts = longest_runs(framed, lo, hi), []
    for ch in range(4):
        n, att, d = runs[ch]
        if not n:
            parts.append(f"{names[ch]} silent")
        elif ch < 3:
            hz = PSG_CLOCK_HZ / (32 * d) if d else 0.0
            parts.append(f"{names[ch]} {n} f at atten {att} div {d} ({hz:.1f} Hz)")
        else:
            parts.append(f"{names[ch]} {n} f at atten {att} noise ctrl {d}")
    return "; ".join(parts)


def judge(psg, reqs, loads, framed, leg_names, n_frames):
    """The verdict shared by this witness and clip_music_witness. psg [(frame, byte)] in
    write order; reqs [(frame, song)]; loads = locate_loads(psg, request frames); framed =
    framed_states(psg, n_frames). -> (report lines, failure lines)."""
    names = ["PSG1", "PSG2", "PSG3", "NOISE"]
    lines, fails = [], []
    located = [(i, ld) for i, ld in enumerate(loads) if ld is not None]
    for i, ld in enumerate(loads):
        if ld is None:
            fails.append(f"leg {leg_names[i]}: no PSG silence within {LOAD_WAIT} frames of the "
                         f"request at frame {reqs[i][0]}: the switch did not silence the chip, "
                         f"or the song never loaded")
    for k, (i, ld) in enumerate(located):
        lo = psg[ld][0]
        hi = psg[located[k + 1][1]][0] - 1 if k + 1 < len(located) else n_frames
        lines.append(f"leg {leg_names[i]} (song {reqs[i][1]}, loaded frame {lo}): longest "
                     f"audible unchanged run per channel, frames {lo}..{hi}: "
                     + describe_runs(framed, lo, hi))
    bad = stale_sounds([(j, v) for j, (_f, v) in enumerate(psg)], [ld for _i, ld in located])
    for li, j, ch, att in bad:
        i, ld = located[li]
        fails.append(f"leg {leg_names[i]} (song {reqs[i][1]}): {names[ch]} set to attenuation "
                     f"{att} at frame {psg[j][0]} with no "
                     f"{'divisor' if ch < 3 else 'noise-control'} write since the load at "
                     f"frame {psg[ld][0]}: it sounds the previous song's latch")
    lines.append(f"RULE: {len(bad)} stale sound(s) over {len(located)} load(s), "
                 f"{len(psg)} PSG writes")
    return lines, fails


def longest_runs(framed, lo, hi):
    """framed: [(frame, attens, divs, noise)] state per frame (last write of the frame);
    frames lo..hi inclusive. -> {ch: (frames, atten, divisor_or_noise)} longest audible run
    of one unchanged (atten, divisor) per channel."""
    best = {}
    for ch in range(4):
        run_key, run_len, top = None, 0, (0, None, None)
        for f in range(lo, hi + 1):
            att, div, noise = framed[f]
            key = (att[ch], div[ch] if ch < 3 else noise)
            if key == run_key:
                run_len += 1
            else:
                run_key, run_len = key, 1
            if key[0] != 15 and run_len > top[0]:
                top = (run_len, key[0], key[1])
        best[ch] = top
    return best


# --------------------------------------------------------------------------- the drive
async def drive(sock, syms, equs):
    b = BusClient(socket_path=sock, client_id="psgswitch", client_name="psg_song_switch_witness")
    await b.connect()

    async def rd(addr, n):
        r = await b.call("emulator/read_memory", {"addr": hex(addr & 0xFFFFFF), "len": n})
        s = r["bytes"]
        return bytes.fromhex(s[2:] if s[:2].lower() == "0x" else s)

    async def wr(addr, value, width=1):
        await b.call("emulator/write_memory", {"addr": hex(addr & 0xFFFFFF), "value": value,
                                               "width": width})

    watches = {}
    for label, addr in (("psg", PSG_PORT_BUS), ("slot", equs["MUSIC_SLOT"])):
        r = await b.call("emulator/watchpoint_add", {"addr": hex(addr), "len": 1, "write": True,
                                                     "read": False, "mode": "record",
                                                     "label": label, "space": "bus"})
        watches[label] = r["watch"]
    cursors = {k: None for k in watches}
    psg, slot, seqs = [], [], []          # (seq, frame, byte) / (seq, frame, via, byte)
    frame = 0

    async def poll():
        for label, h in watches.items():
            while True:
                p = {"watch": h, "limit": 100}
                if cursors[label] is not None:
                    p["cursor"] = str(cursors[label])
                r = await b.call("emulator/watchpoint_hits", p)
                hits = r.get("hits", [])
                for hit in hits:
                    cursors[label] = hit["seq"]
                    seqs.append(hit["seq"])
                    v = int(str(hit["value"]).replace("0x", ""), 16) & 0xFF
                    if label == "psg":
                        if hit.get("via") == VIA_Z80:
                            psg.append((hit["seq"], frame, v))
                    else:
                        slot.append((hit["seq"], frame, hit.get("via"), v))
                if not r.get("truncated") and len(hits) < 100:
                    break

    async def step(n):
        nonlocal frame
        for _ in range(n):
            await b.call("emulator/run_frames", {"frames": 1})
            frame += 1
            await poll()

    async def alive(where):
        st = await b.call("emulator/status", {})
        if "ErrorHandler" in (st.get("symbolAtPc") or ""):
            raise CouldNotRun(f"the ROM FAULTED during {where}: {st.get('symbolAtPc')!r}")

    ids = CRB.song_ids()
    ehz, cpz = ids["SONG_S2_EHZ"], ids["SONG_S2_CPZ"]
    legs = []                              # (name, request frame, song)

    async def request(name, song):
        legs.append((name, frame, song))
        await wr(syms["Music_Want"], song)
        await step(PLAY_FRAMES)
        await alive(name)

    await step(BOOT_FRAMES)
    await alive("boot")
    await request("ehz", ehz)
    await request("cpz", cpz)
    await request("back", ehz)
    # mid-SFX: queue the SFX, wait for the driver to take it, then switch
    mask = emp_consts(SOUND_CONSTANTS)["SFX_RING_MASK"]
    ring, wr_p, rd_p = syms["Sfx_Ring_Buf"], syms["Sfx_Ring_Wr"], syms["Sfx_Ring_Rd"]
    w0, r0 = (await rd(wr_p, 1))[0], (await rd(rd_p, 1))[0]
    if w0 != r0:
        raise CouldNotRun(f"the SFX ring is not empty before the SFX leg (Wr={w0} Rd={r0})")
    await wr(ring + w0, sfx_id_of(SFX_NAME))
    await wr(wr_p, (w0 + 1) & mask)
    sfx_frame = frame
    for _ in range(LOAD_WAIT):
        await step(1)
        if (await rd(rd_p, 1))[0] == (w0 + 1) & mask:
            break
    else:
        raise CouldNotRun(f"{SFX_NAME} never left the SFX ring")
    await step(2)                          # the SFX's first tick has written the chip
    await request("sfx", cpz)
    await poll()
    await b.close()
    return {"psg": psg, "slot": slot, "seqs": seqs, "legs": legs, "frames": frame,
            "sfx_frame": sfx_frame}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--rom", default="s4.debug.bin")
    ap.add_argument("--lst", default="s4.debug.lst")
    a = ap.parse_args()
    try:
        syms, equs = RMW.parse_lst(a.lst)
        for n in ("Music_Want", "Music_Current", "Sfx_Ring_Buf", "Sfx_Ring_Wr", "Sfx_Ring_Rd"):
            if n not in syms:
                raise CouldNotRun(f"{a.lst} carries no {n}")
        with aether_emulator(a.rom, symbols=a.lst) as sock:
            r = asyncio.run(drive(sock, syms, equs))
        seqs = sorted(r["seqs"])
        holes = sum(1 for x, y in zip(seqs, seqs[1:]) if y != x + 1)
        if holes:
            raise CouldNotRun(f"{holes} gap(s) in the watch's seq run: hits were lost")
        if not r["psg"]:
            raise CouldNotRun("the PSG watch recorded no z80-attributed write")
        reqs = [(f, v) for _s, f, via, v in r["slot"] if via != "z80" and v != 0]
        print(f"ROM {a.rom}: legs " + ", ".join(f"{n} song {s} at frame {f}"
                                                 for n, f, s in r["legs"]))
        print(f"music requests on the bus (frame, song): {reqs}")
        if [v for _f, v in reqs] != [s for _n, _f, s in r["legs"]]:
            raise CouldNotRun(f"the legs posted {[v for _f, v in reqs]}, not "
                              f"{[s for _n, _f, s in r['legs']]}")
        psg = [(f, v) for _s, f, v in r["psg"]]
        loads = locate_loads(psg, [f for f, _v in reqs])
        framed = framed_states(psg, r["frames"])
        # premise: every switch AWAY from EHZ happens with PSG1/PSG2 latched and sounded
        ehz = CRB.song_ids()["SONG_S2_EHZ"]
        for i in range(1, len(reqs)):
            if reqs[i - 1][1] != ehz or loads[i] is None or loads[i - 1] is None:
                continue
            lf, pf = psg[loads[i]][0], psg[loads[i - 1]][0]
            div = framed[lf - 1][1]
            seen = [any(framed[g][0][c] != 15 for g in range(pf, lf)) for c in range(2)]
            print(f"premise {r['legs'][i][0]}: at the switch PSG1/PSG2 divisors {div[:2]}, "
                  f"sounded since EHZ loaded {seen}")
            if not all(d > 1 for d in div[:2]) or not all(seen):
                raise CouldNotRun(f"leg {r['legs'][i][0]}: EHZ had not latched and sounded "
                                  f"PSG1 and PSG2 before the switch, so a stale latch is 0 "
                                  f"and the switch tests nothing")
        sfx_writes = [f for f, _v in psg
                      if r["sfx_frame"] <= f < (psg[loads[-1]][0] if loads[-1] is not None
                                               else reqs[-1][0])]
        print(f"premise sfx: {len(sfx_writes)} PSG write(s) between queueing {SFX_NAME} and "
              f"the switch")
        if not sfx_writes:
            raise CouldNotRun(f"{SFX_NAME} wrote no PSG byte before the switch")
    except CouldNotRun as e:
        print(f"COULD NOT RUN: {e}")
        print("finished=1")
        return 2

    lines, fails = judge(psg, reqs, loads, framed, [n for n, _f, _s in r["legs"]],
                         r["frames"])
    for m in lines:
        print(m)
    for m in fails:
        print(f"FAIL: {m}")
    print("VERDICT:", "RED" if fails else "GREEN")
    print("finished=1")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
