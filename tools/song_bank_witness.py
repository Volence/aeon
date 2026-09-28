#!/usr/bin/env python3
"""song_bank_witness — does a song play the same from its own bank as from the SFX bank,
including across FM SFX that hand a voice back? (S2CLIP-MTZ-SONG-BANK, song bank 2, 2026-09-28.)

THE QUESTION. A song in a second Z80 song bank (SongBank2_Head at 0xC0000) is streamed by the
sequencer through the $8000 window with the SONG's bank latched, and an FM SFX that ends over
it re-uploads the music voice under that bank too (Sfx_Restore -> SndDrv_SongBankIn). If any
read happened under the wrong bank, the Z80 would read other bytes and write other things to
the chip.

WHAT CANNOT BE SEEN, said first. This harness (oracle-aether on the Rust core) records no Z80
bank-register write, no Z80 read through the window and no Z80 fetch (MEASURED here: a bus
watch on $A06000 and a read watch over the song's ROM bytes record no `via: "z80"` hit; oracle
docs/2026-09-25-z80-watch-cr.md §1.1 says the same from the code), and it cannot read or write
Z80 RAM (`emulator/read` / `write_memory` refuse $A0xxxx). So the bank the Z80 latched and the
bytes it fetched are NOT observed. What IS observed is every byte the Z80 writes to the YM2612
and the PSG (`via: "z80"`), which is what the song and the restore produce from those fetches.

THE DIFFERENTIAL. The same deterministic drive runs on two ROMs whose 68k code is identical:
  SUBJECT  the ROM under test, the song where the build put it;
  CONTROL  (default) a copy of the SUBJECT with the song and its patch bank copied over Moving
           Trucks (unplayed in a clip act) in the SFX bank, bank 1, and the song's
           SongTable / SongPatchTable entries repointed: the song as it would play with no
           second bank. Or --control-rom: any ROM with the same song (the pre-change build,
           for a song that did not move banks).
Same bytes fetched => same chip writes. A read under the wrong bank => different writes.
The comparison is the ordered stream of Z80 YM data writes (DAC sample data $2A excluded: its
count depends on Z80 timing, and an extra uncached SetBank per frame is exactly the timing the
two ROMs differ in) and PSG writes.

STATIC CHECKS (on the SUBJECT, from the ROM and its listing, nothing typed): the song's
SongTable entry points at a committed song_*.bin and its SongPatchTable entry at a committed
*_patches.bin; song and patch bank share one bank; that bank begins with the engine-table head
(the bytes from the SFX bank's base up to Song_MovingTrucks), byte for byte.

THE DRIVE: boot BOOT_FRAMES; if Music_Current is not the song, post it through Music_Want (the
region service's own two bytes); play FRAMES frames; queue the FM SFX (SFX_NAME) into the 68k
SFX ring at +SFX_AT[0] and +SFX_AT[1] frames after the request. Three runs: SUBJECT, CONTROL,
and SUBJECT without the SFX (a premise, below).

PREMISES (unmet = COULD NOT RUN, exit 2, never a pass): each run's watches recorded Z80 YM and
PSG writes with no lost hit; each run observed the music request; the SUBJECT keyed at least
MIN_KEYONS notes after it; every queued SFX left the ring; the SFX run's FM stream differs from
the no-SFX run's by at least two patch uploads per SFX (the SFX's own voice, then the music's
re-uploaded by the hand-back), so the restore under test really ran.

Exit 0 SUBJECT == CONTROL · 1 they differ (the first divergence printed) · 2 could not run.
NOTHING HERE SAYS HOW IT SOUNDS: that is the owner's ear.

Usage:
    python3 tools/song_bank_witness.py --rom s4.s2clip.bin --lst s4.s2clip.lst --song SONG_S2_MTZ
    python3 tools/song_bank_witness.py --rom NEW.bin --lst NEW.lst --song SONG_S2_EHZ \\
        --control-rom OLD.bin --control-lst OLD.lst
"""
from __future__ import annotations

import argparse
import asyncio
import difflib
import os
import sys
import tempfile
import zlib
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
import rom_reloc_diff as RRD  # noqa: E402
from psg_env_attack_witness import PSG_PORT_BUS, SOUND_CONSTANTS, VIA_Z80, sfx_id_of  # noqa: E402
from song_load_mid_drum_witness import YmTap, REG_KEY, REG_DAC_DATA  # noqa: E402

BOOT_FRAMES = 240
FRAMES = 900               # 15 s after the request
SFX_AT = (240, 540)        # frames after the request the SFX are queued
SFX_NAME = "SFXID_RING_RIGHT"
LOAD_WAIT = 30
MIN_KEYONS = 20
WINDOW = 0x8000


class CouldNotRun(Exception):
    pass


def crc(data: bytes) -> str:
    return f"{zlib.crc32(data):08x}/{len(data)}"


# --------------------------------------------------------------------------- static
def be32(rom: bytes, a: int) -> int:
    return int.from_bytes(rom[a:a + 4], "big")


def song_entry(rom: bytes, labs: dict, song_id: int) -> tuple[int, int]:
    for n in ("SongTable", "SongPatchTable", "Song_MovingTrucks", "Sfx_33"):
        if n not in labs:
            raise CouldNotRun(f"the listing defines no {n}")
    return (be32(rom, labs["SongTable"] + 4 * (song_id - 1)),
            be32(rom, labs["SongPatchTable"] + 4 * (song_id - 1)))


def blob_at(rom: bytes, addr: int, blobs: dict, kind: str) -> str:
    names = [n for n, b in blobs.items() if n.startswith(kind) and rom[addr:addr + len(b)] == b] \
        if kind == "song_" else \
        [n for n, b in blobs.items() if n.endswith(kind) and rom[addr:addr + len(b)] == b]
    if not names:
        raise CouldNotRun(f"no committed {kind}* blob at {addr:#x}")
    return max(names, key=lambda n: len(blobs[n]))


def static_checks(rom: bytes, labs: dict, song_id: int) -> dict:
    blobs = RRD.committed_blobs()
    song, patch = song_entry(rom, labs, song_id)
    song_name, patch_name = blob_at(rom, song, blobs, "song_"), blob_at(rom, patch, blobs, "_patches.bin")
    sfx_bank_base = labs["Sfx_33"] & ~(WINDOW - 1)
    head_len = labs["Song_MovingTrucks"] - (labs["Song_MovingTrucks"] & ~(WINDOW - 1))
    if (labs["Song_MovingTrucks"] & ~(WINDOW - 1)) != sfx_bank_base:
        raise CouldNotRun("Song_MovingTrucks and Sfx_33 are not in one bank; the SFX bank's "
                          "head cannot be located")
    song_base = song & ~(WINDOW - 1)
    head_ok = rom[song_base:song_base + head_len] == rom[sfx_bank_base:sfx_bank_base + head_len]
    return {"song": song, "patch": patch, "song_name": song_name, "patch_name": patch_name,
            "song_bank": song >> 15, "patch_bank": patch >> 15, "sfx_bank": sfx_bank_base >> 15,
            "head_len": head_len, "head_ok": head_ok,
            "song_len": len(blobs[song_name]), "patch_len": len(blobs[patch_name])}


def control_fixture(rom: bytes, labs: dict, song_id: int, st: dict) -> bytes:
    """The SUBJECT with the song + patch bank copied over Moving Trucks (SFX bank) and the
    two table entries repointed."""
    target = labs["Song_MovingTrucks"]
    room_end = labs.get("MovingTrucks_Patches")
    if room_end is None:
        raise CouldNotRun("the listing defines no MovingTrucks_Patches (the fixture's room)")
    room_end += len(RRD.committed_blobs()["movingtrucks_patches.bin"])
    patch_at = (target + st["song_len"] + 1) & ~1
    if patch_at + st["patch_len"] > room_end or (target >> 15) != st["sfx_bank"]:
        raise CouldNotRun("the song + patch bank do not fit over Moving Trucks in the SFX bank")
    out = bytearray(rom)
    out[target:target + st["song_len"]] = rom[st["song"]:st["song"] + st["song_len"]]
    out[patch_at:patch_at + st["patch_len"]] = rom[st["patch"]:st["patch"] + st["patch_len"]]
    st_cell = labs["SongTable"] + 4 * (song_id - 1)
    spt_cell = labs["SongPatchTable"] + 4 * (song_id - 1)
    out[st_cell:st_cell + 4] = target.to_bytes(4, "big")
    out[spt_cell:spt_cell + 4] = patch_at.to_bytes(4, "big")
    struct_ok = song_entry(bytes(out), labs, song_id) == (target, patch_at)
    if not struct_ok:
        raise CouldNotRun("the fixture's table repoint did not take")
    return bytes(out)


# --------------------------------------------------------------------------- the drive
async def drive(sock, syms, equs, song_id, sfx_id, with_sfx):
    b = BusClient(socket_path=sock, client_id="songbank", client_name="song_bank_witness")
    await b.connect()

    async def rd(addr, n):
        r = await b.call("emulator/read_memory", {"addr": hex(addr & 0xFFFFFF), "len": n})
        s = r["bytes"]
        return bytes.fromhex(s[2:] if s[:2].lower() == "0x" else s)

    async def wr(addr, value, width=1):
        await b.call("emulator/write_memory", {"addr": hex(addr & 0xFFFFFF), "value": value,
                                               "width": width})

    ym = YmTap(b)
    await ym.arm("ym")
    watches, cursors = {}, {}
    for label, addr in (("psg", PSG_PORT_BUS), ("slot", equs["MUSIC_SLOT"])):
        r = await b.call("emulator/watchpoint_add", {"addr": hex(addr), "len": 1, "write": True,
                                                     "read": False, "mode": "record",
                                                     "label": label, "space": "bus"})
        watches[label], cursors[label] = r["watch"], None
    psg, slot, seqs = [], [], []
    frame = 0

    async def poll():
        await ym.poll()
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
                        slot.append((frame, hit.get("via"), v))
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

    await step(BOOT_FRAMES)
    await alive("boot")
    cur = (await rd(syms["Music_Current"], 1))[0]
    if cur != song_id:
        await wr(syms["Music_Want"], song_id)
    req_frame = frame
    mask = emp_consts(SOUND_CONSTANTS)["SFX_RING_MASK"]
    ring, wr_p, rd_p = syms["Sfx_Ring_Buf"], syms["Sfx_Ring_Wr"], syms["Sfx_Ring_Rd"]
    sfx_frames = []
    for at in (SFX_AT if with_sfx else ()):
        await step(req_frame + at - frame)
        w0, r0 = (await rd(wr_p, 1))[0], (await rd(rd_p, 1))[0]
        if w0 != r0:
            raise CouldNotRun(f"the SFX ring is not empty at frame {frame} (Wr={w0} Rd={r0})")
        await wr(ring + w0, sfx_id)
        await wr(wr_p, (w0 + 1) & mask)
        sfx_frames.append(frame)
        for _ in range(LOAD_WAIT):
            await step(1)
            if (await rd(rd_p, 1))[0] == (w0 + 1) & mask:
                break
        else:
            raise CouldNotRun(f"the SFX queued at frame {sfx_frames[-1]} never left the ring")
    await step(req_frame + FRAMES - frame)
    await alive("play")
    await poll()
    await b.close()
    fault = ym.liveness_fault() if hasattr(ym, "liveness_fault") else None
    return {"ym": ym, "psg": psg, "slot": slot, "seqs": seqs + list(ym.seqs),
            "req_frame": req_frame, "sfx_frames": sfx_frames, "boot_song": cur,
            "live_fault": fault}


def stream(r):
    """The comparable stream: YM data writes except DAC sample data, and PSG bytes, in bus
    order (seq). Each item carries its kind and payload, never its time."""
    out = []
    for seq, _mclk, part, reg, val in r["ym"].events:
        if val is None or reg == REG_DAC_DATA:
            continue
        out.append((seq, ("ym", part, reg, val)))
    for seq, _f, v in r["psg"]:
        out.append((seq, ("psg", v)))
    out.sort()
    return [x for _s, x in out]


UPLOAD_MIN_OPS = 16        # a patch upload writes 24 operator registers ($30-$9F)


def patch_uploads(bare, with_sfx):
    """Patch uploads the SFX run has that the no-SFX run does not: runs of at least
    UPLOAD_MIN_OPS operator-register writes ($30-$9F) inside the stretches the SFX run adds
    or replaces. An FM SFX over a music voice makes two per SFX: Sfx_Steal uploads the
    SFX's voice, and the hand-back (Sfx_Restore .fm) re-uploads the music's."""
    n = 0
    sm = difflib.SequenceMatcher(None, bare, with_sfx, autojunk=False)
    for tag, _i1, _i2, j1, j2 in sm.get_opcodes():
        if tag not in ("insert", "replace"):
            continue
        run = 0
        for x in with_sfx[j1:j2] + [("end",)]:
            if x[0] == "ym" and 0x30 <= x[2] <= 0x9F:
                run += 1
                continue
            if x[0] == "ym" and x[2] in (0xB0, 0xB4) and run == 0:
                continue          # the upload's own algorithm/pan writes lead it
            if run >= UPLOAD_MIN_OPS:
                n += 1
            run = 0
    return n


def keyons_after(r):
    return sum(1 for _s, _m, part, reg, val in r["ym"].events
               if reg == REG_KEY and val is not None and val & 0xF0)


def run_one(rom_path, lst, syms, equs, song_id, sfx_id, with_sfx):
    with aether_emulator(rom_path, symbols=lst) as sock:
        r = asyncio.run(drive(sock, syms, equs, song_id, sfx_id, with_sfx))
    if r["live_fault"]:
        raise CouldNotRun(f"{rom_path}: {r['live_fault']}")
    s = sorted(r["seqs"])
    holes = sum(1 for x, y in zip(s, s[1:]) if y != x + 1)
    if holes:
        raise CouldNotRun(f"{rom_path}: {holes} gap(s) in the watch seq run: hits were lost")
    if not r["psg"]:
        raise CouldNotRun(f"{rom_path}: the PSG watch recorded no z80-attributed write")
    posted = [v for _f, via, v in r["slot"] if via != "z80" and v != 0]
    if song_id not in posted and r["boot_song"] != song_id:
        raise CouldNotRun(f"{rom_path}: no request for song {song_id} was observed "
                          f"(posted {posted})")
    return r


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--rom", required=True)
    ap.add_argument("--lst", required=True)
    ap.add_argument("--song", required=True, help="a SONG_* name from sound_ids.emp")
    ap.add_argument("--control-rom")
    ap.add_argument("--control-lst")
    ap.add_argument("--sfx", default=SFX_NAME)
    a = ap.parse_args(argv)
    tmp = None
    try:
        rom = Path(a.rom).read_bytes()
        labs = dict(RRD.listing_labels(Path(a.lst)))
        ids = CRB.song_ids()
        if a.song not in ids:
            raise CouldNotRun(f"{a.song} is not a song id in games/sonic4/config/sound_ids.emp")
        song_id, sfx_id = ids[a.song], sfx_id_of(a.sfx)
        syms, equs = RMW.parse_lst(a.lst)
        for n in ("Music_Want", "Music_Current", "Sfx_Ring_Buf", "Sfx_Ring_Wr", "Sfx_Ring_Rd"):
            if n not in syms:
                raise CouldNotRun(f"{a.lst} carries no {n}")
        st = static_checks(rom, labs, song_id)
        print(f"SUBJECT {a.rom} ({crc(rom)}): {a.song} = id {song_id}")
        print(f"  song  {st['song_name']} ({st['song_len']} B) at {st['song']:#x}: bank "
              f"${st['song_bank']:02X}, window ptr ${0x8000 | (st['song'] & 0x7FFF):04X}")
        print(f"  patch {st['patch_name']} ({st['patch_len']} B) at {st['patch']:#x}: bank "
              f"${st['patch_bank']:02X}")
        print(f"  SFX bank ${st['sfx_bank']:02X}; the song's bank begins with the engine-table "
              f"head ({st['head_len']} B): {'YES' if st['head_ok'] else 'NO'}")
        fails = []
        if st["song_bank"] != st["patch_bank"]:
            fails.append("the song and its patch bank are in different banks")
        if not st["head_ok"]:
            fails.append(f"bank ${st['song_bank']:02X} does not begin with the engine-table head")
        if a.control_rom:
            if not a.control_lst:
                raise CouldNotRun("--control-rom needs --control-lst")
            c_path, c_lst = a.control_rom, a.control_lst
            c_syms, c_equs = RMW.parse_lst(c_lst)
            cst = static_checks(Path(c_path).read_bytes(), dict(RRD.listing_labels(Path(c_lst))),
                                song_id)
            print(f"CONTROL {c_path} ({crc(Path(c_path).read_bytes())}): the same song "
                  f"at {cst['song']:#x} (bank ${cst['song_bank']:02X})")
        else:
            if st["song_bank"] == st["sfx_bank"]:
                raise CouldNotRun(f"{a.song} is in the SFX bank already; the default control "
                                  "would be the subject itself. Pass --control-rom.")
            fixture = control_fixture(rom, labs, song_id, st)
            fd, tmp = tempfile.mkstemp(suffix=".bin", prefix="song_bank_control_")
            os.write(fd, fixture)
            os.close(fd)
            c_path, c_lst, c_syms, c_equs = tmp, a.lst, syms, equs
            print(f"CONTROL fixture ({crc(fixture)}): the song + patch bank copied over "
                  f"Moving Trucks at {labs['Song_MovingTrucks']:#x} (bank ${st['sfx_bank']:02X}), "
                  f"table entries repointed; the ROM on disk is untouched")
        subj = run_one(a.rom, a.lst, syms, equs, song_id, sfx_id, True)
        ctrl = run_one(c_path, c_lst, c_syms, c_equs, song_id, sfx_id, True)
        bare = run_one(a.rom, a.lst, syms, equs, song_id, sfx_id, False)
        ks = keyons_after(subj)
        s_subj, s_ctrl, s_bare = stream(subj), stream(ctrl), stream(bare)
        print(f"runs: request at frame {subj['req_frame']} (boot song {subj['boot_song']}); "
              f"{a.sfx} queued at {subj['sfx_frames']}; {FRAMES} frames")
        print(f"  SUBJECT {len(s_subj)} chip writes ({ks} key-ons), CONTROL {len(s_ctrl)}, "
              f"SUBJECT without SFX {len(s_bare)}")
        if ks < MIN_KEYONS:
            raise CouldNotRun(f"the SUBJECT keyed {ks} notes (< {MIN_KEYONS}): no song played")
        ups = patch_uploads(s_bare, s_subj)
        print(f"  patch uploads only the SFX run makes: {ups} (a steal and a hand-back per "
              f"SFX = {2 * len(SFX_AT)})")
        if ups < 2 * len(SFX_AT):
            raise CouldNotRun(f"{a.sfx} over {a.song} made {ups} patch upload(s), fewer than "
                              f"a steal + a hand-back for each of the {len(SFX_AT)} SFX: no "
                              "music voice was handed back, so the check would test nothing")
        if s_subj != s_ctrl:
            i = next((k for k, (x, y) in enumerate(zip(s_subj, s_ctrl)) if x != y),
                     min(len(s_subj), len(s_ctrl)))
            fails.append(f"SUBJECT and CONTROL chip writes diverge at write #{i} of "
                         f"{len(s_subj)}/{len(s_ctrl)}: {s_subj[i:i + 4]} vs {s_ctrl[i:i + 4]}")
        else:
            print(f"  SUBJECT == CONTROL: all {len(s_subj)} chip writes identical, in order, "
                  "including the two SFX voice hand-backs")
    except CouldNotRun as e:
        print(f"COULD NOT RUN: {e}")
        print("finished=1")
        return 2
    finally:
        if tmp:
            os.unlink(tmp)
    for m in fails:
        print(f"FAIL: {m}")
    print("VERDICT:", "RED" if fails else "GREEN")
    print("finished=1")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
