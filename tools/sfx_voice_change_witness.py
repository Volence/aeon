#!/usr/bin/env python3
"""sfx_voice_change_witness — SP-6: does a mid-stream `smpsSetvoice` actually
select the SECOND voice out of the SFX's own FmPatch bank?

THE CLAIM UNDER TEST is not "sfx $B1 carries two voices in the ROM" and not
"a MEV_PATCH byte is in the stream". Both of those are static and are already
covered by tools/test_sfx_transcode.py. The claim is that at RUNTIME, after the
voice-change opcode, the driver resolves its FM patch pointer to voice N's 32
bytes and not to voice 0's — i.e. that Fm_PatchPtr's

    hl = sx_patch_base + sc_patch*FmPatch_len

term is real and reaches the code that consumes it.

WHAT THIS CANNOT SAY, STATED PLAINLY. It does not claim the spring SOUNDS right,
and it does not observe the YM2612 at all. There is no audio instrument in this
suite, and that is measured rather than assumed: the running oracle server's
method table (`name: "emulator/..."` in oracle-aether/src/engine.rs) has no
vgm_start/vgm_stop/vgm_status, no audio_spectrum, no get_channel_states, no Z80
registers and no Z80 breakpoints. Those names appear in the bus SCHEMA and in the
contract vectors but are NOT served — probing them on a live instance returns
`[-32601] no such method`. So the chip-side write is out of reach, and the honest
subject is the pointer resolution that determines it.

THE INSTRUMENT, AND WHY IT IS NOT THE WITNESS GRADING ITS OWN HOMEWORK.
Fm_SetVolume writes Fm_ScratchMask = CarrierMaskTableZ[resolved_patch.fp_alg_fb & 7],
where `resolved_patch` is whatever Fm_PatchPtr just returned. That byte is in Z80
RAM and readable over the bus. Critically, this file never computes a patch
address: it changes ONE BYTE IN THE ROM IMAGE and watches which resolved voice the
driver's own output follows.

THREE LEGS. The two voices of the real spring have the SAME algorithm ($00), so
their masks are naturally identical and no leg could tell them apart by observation
alone — which is exactly why the discrimination has to be INTRODUCED, one poisoned
byte at a time, and why C1 exists to show the baseline really is flat:

  C1 BASELINE            the unpoisoned ROM. Records the mask series, finds the
                         first frame the cell is written at all, and asserts the
                         two voices are NOT already distinguishable. Without this,
                         L1 and L2 could be reading a pre-existing difference
                         rather than one they caused, and a dead instrument
                         (nothing ever writes the cell) would read as agreement.

  L1 VOICE 0 IS NOT READ poison voice 0's algorithm only. NOTHING in the observed
                         window may move. Under the pre-SP-6 engine — Fm_PatchPtr
                         returning sx_patch_base raw and discarding the index —
                         voice 0 is what gets resolved no matter what the stream
                         said, so this leg goes red there.

  L2 VOICE N IS READ     poison voice N's algorithm only, where N is decoded from
                         the shipped stream's own MEV_PATCH operand. The observed
                         window must move to the poisoned mask. Also red pre-SP-6,
                         for the mirror-image reason: voice N was never read.

  and the pair must DISAGREE. Two poisons of two voices in one bank producing the
  same observation would mean the instrument is not reading the resolved voice.

WHAT THE LEGS DELIBERATELY DO NOT CLAIM, AND WHY THEY WERE NARROWED. An earlier
draft of L1 asserted the opposite — that poisoning voice 0 WOULD move an early
stretch of the series, proving voice 0 feeds the driver BEFORE the change, with a
further assertion that the voice-0 window lies entirely before the voice-N window.
It was run and it FAILED, for a reason that is a property of the subject rather
than of the engine: the spring emits no MEV_VOL before its voice change (the
transcoder bakes the channel volume into the patch TLs, and the only Vol events
come from the smpsFMAlterVol unroll, which is AFTER the change), so Fm_SetVolume
never runs while voice 0 is selected and voice 0 is never observable through this
cell at all. The measured baseline shows it: Fm_ScratchMask is $00 until frame 13.
So the ordering claim is NOT established here, and this file does not make it. What
is established is the discrimination AFTER the change, which is the SP-6 claim.

EVERY EXPECTATION IS DERIVED. The subject id comes from the listing's own
SFXID_SPRING equ; the Z80 address from its Fm_ScratchMask_Addr equ; the patch bank
location from the shipped blob's own header record; FmPatch_len from
zyrinx_port.FMPATCH_LEN; the voice index from the stream's MEV_PATCH operand; and
the expected mask values from tools/gen_sound_tables.py::carrier_mask_table(), the
generator that emits CarrierMaskTableZ. No value below is copied from a nearby pin
or from a single earlier measurement.

RUN:  python3 tools/sfx_voice_change_witness.py [--rom s4.debug.bin] [--lst s4.debug.lst]
"""
import argparse
import asyncio
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from suite_paths import add_client_path  # noqa: E402
add_client_path()
from aether import BusClient  # noqa: E402
from aether_instance import aether_emulator, read_bytes, unprefix  # noqa: E402
from gen_sound_tables import carrier_mask_table  # noqa: E402
from zyrinx_port import FMPATCH_LEN  # noqa: E402
from song_packer import MEV_PATCH  # noqa: E402

SETTLE_FRAMES = 40
SAMPLE_FRAMES = 120        # covers the whole spring: wind-up + the unrolled tail
DROP_HEIGHT = 120
SPRING_X, SPRING_Y = 160, 584


class Unmeasurable(RuntimeError):
    """The run could not ask its question — never reported as a pass."""


def parse_syms(lst):
    """-> ({label: addr}, {equ_name: value}) — the .lst's two namespaces.

    They ARE two namespaces: `emulator/lookup_symbol` cannot see an EQU row, which
    is why this reads the listing directly rather than asking the emulator."""
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


# --------------------------------------------------------------------------
# Static half: find the subject's patch bank IN THE ROM IMAGE, and decode which
# voice its stream switches to. Both come out of the shipped artifacts, so a
# regenerated blob moves them automatically.
# --------------------------------------------------------------------------
def locate_subject(rom_path, blob_path):
    """-> (bank_rom_off, voice_count, change_idx) for the SFX blob at blob_path.

    Raises Unmeasurable rather than guessing on every ambiguity: the ROM must
    contain the blob exactly once, the blob must carry an FM channel with a voice
    pointer, the bank must hold >= 2 whole FmPatch records, and the stream must
    contain exactly one MEV_PATCH."""
    rom = Path(rom_path).read_bytes()
    blob = Path(blob_path).read_bytes()
    hits = [m.start() for m in re.finditer(re.escape(blob), rom)]
    if len(hits) != 1:
        raise Unmeasurable(
            f"{os.path.basename(blob_path)} ({len(blob)} B) occurs {len(hits)} times in "
            f"{os.path.basename(rom_path)}; a poison needs exactly one unambiguous site")
    base = hits[0]

    # SfxHeader: priority, flags, chcount, gain, duck, cap, rsvd*2 == 8 bytes;
    # then chcount 6-byte records {route, kind, cmd_hi, cmd_lo, voice_hi, voice_lo}.
    chcount = blob[2]
    if chcount < 1:
        raise Unmeasurable(f"blob declares chcount={chcount}")
    voice_ptr = None
    cmd_ptr = None
    for i in range(chcount):
        r = 8 + i * 6
        vp = (blob[r + 4] << 8) | blob[r + 5]
        if vp:                                   # 0 == PSG/noise, no FM bank
            voice_ptr, cmd_ptr = vp, (blob[r + 2] << 8) | blob[r + 3]
            break
    if voice_ptr is None:
        raise Unmeasurable(
            "no channel in this blob carries an FmPatch bank pointer — the subject "
            "is PSG-only and has no FM voice to change")

    bank = blob[voice_ptr:]
    voice_count, rem = divmod(len(bank), FMPATCH_LEN)
    if rem:
        raise Unmeasurable(
            f"the patch bank is {len(bank)} B, not a whole number of "
            f"{FMPATCH_LEN}-byte FmPatch records")
    if voice_count < 2:
        raise Unmeasurable(
            f"sfx blob {os.path.basename(blob_path)} carries {voice_count} voice(s). "
            "SP-6's subject must be a MULTI-VOICE SFX; if the spring's donor was "
            "reverted to Sonic 2's single-voice source this witness has no subject "
            "and REFUSES rather than reporting a pass")

    # Decode the stream far enough to read the MEV_PATCH operand. Only the operand
    # is wanted, so a full decoder is not needed: MEV_PATCH is a 2-byte event and
    # scanning the stream span for it is unambiguous here because the assertion
    # below requires exactly one.
    stream = blob[cmd_ptr:voice_ptr]
    idxs = [i for i in range(len(stream) - 1) if stream[i] == MEV_PATCH]
    if len(idxs) != 1:
        raise Unmeasurable(
            f"expected exactly one MEV_PATCH (${MEV_PATCH:02X}) in the subject's "
            f"stream, found {len(idxs)} — cannot name a single voice under test")
    change_idx = stream[idxs[0] + 1]
    if not 0 < change_idx < voice_count:
        raise Unmeasurable(
            f"the stream selects voice {change_idx}, which is not a non-zero voice "
            f"inside a {voice_count}-voice bank")
    return base + voice_ptr, voice_count, change_idx


def poisoned_rom(src, out_path, bank_off, voice, new_alg):
    """Copy `src` to `out_path` with ONE byte changed: voice's fp_alg_fb algorithm.

    fp_alg_fb is byte 0 of an FmPatch (algorithm bits 0-2, feedback bits 3-5); only
    the algorithm nibble moves, so the feedback the voice was authored with is
    preserved and the single changed byte is the only variable across legs."""
    data = bytearray(Path(src).read_bytes())
    off = bank_off + voice * FMPATCH_LEN
    old = data[off]
    data[off] = (old & ~0x07) | (new_alg & 0x07)
    Path(out_path).write_bytes(bytes(data))
    return off, old, data[off]


# --------------------------------------------------------------------------
# Dynamic half
# --------------------------------------------------------------------------
async def rd(b, addr, n):
    """Raw bytes from the 68k bus, masked to the 24 real address lines."""
    return bytes.fromhex(unprefix(await read_bytes(b, addr & 0xFFFFFF, n)))


async def z80_byte(b, addr):
    """One byte of Z80 RAM.

    Routed through the reply's own hex string with unprefix(): `emulator/z80_read`
    answers "0x.." and slicing it positionally reads two characters off and reports
    a confident wrong answer."""
    # `addr` must be a HEX STRING ("0x....") — the bus refuses a bare number (D9).
    r = await b.call("emulator/z80_read", {"addr": hex(addr), "len": 1})
    # The reply is {"addr","len","bytes"} and `bytes` carries the "0x" PREFIX.
    # unprefix() strips it: slicing positionally would read two characters off and
    # report a confident wrong byte.
    if not isinstance(r, dict) or "bytes" not in r:
        raise Unmeasurable(f"emulator/z80_read returned no `bytes` field: {r!r}")
    return bytes.fromhex(unprefix(r["bytes"]))[0]


def s16(v):
    return v - 0x10000 if v >= 0x8000 else v


async def player_y(b, syms, equs):
    return s16(int.from_bytes(await rd(b, syms["Player_1"] + equs["SST_y_pos"], 2), "big"))


async def boot_to_act(b, syms, equs, out):
    """Reach a running act with physics live. Mirrors spring_sfx_witness."""
    await b.call("emulator/run_frames", {"frames": 240})
    y0 = await player_y(b, syms, equs)
    await b.call("emulator/run_frames", {"frames": 8})
    if await player_y(b, syms, equs) == y0:
        await b.call("emulator/press", {"buttons": ["b"]})
        await b.call("emulator/run_frames", {"frames": 8})
        if await player_y(b, syms, equs) == y0:
            raise Unmeasurable(
                f"the player is still frozen at y={y0} after a B press — nothing in "
                "this run would be physics")
    await b.call("emulator/run_frames", {"frames": SETTLE_FRAMES})


async def run_leg(sock, lst, mask_addr, syms, equs):
    """Boot, drop the player onto the spring, and sample Fm_ScratchMask per frame.

    -> the list of SAMPLE_FRAMES mask bytes, one per frame after contact."""
    b = BusClient(socket_path=sock, client_id="sfxvoice",
                  client_name="sfx_voice_change_witness")
    await b.connect()
    await b.call("emulator/load_symbols", {"path": lst})
    await b.call("emulator/reset", {})
    await boot_to_act(b, syms, equs, None)

    for field, val in (("SST_x_pos", SPRING_X << 16),
                       ("SST_y_pos", (SPRING_Y - DROP_HEIGHT) << 16),
                       ("SST_x_vel", 0)):
        await b.call("emulator/write_memory", {
            "addr": hex((syms["Player_1"] + equs[field]) & 0xFFFFFF),
            "bytes": "0x" + f"{val:08X}"})

    # Stop the instant the sound API is entered with the spring's id, so every leg
    # starts sampling from the SAME event rather than from a frame count.
    play = syms["Sound_PlaySFX"]
    r = await b.call("emulator/run_to", {"addr": hex(play), "maxFrames": 240})
    hit = (r.get("stopped") or r.get("hit") or
           (r.get("pc") is not None and int(str(r["pc"]).replace("0x", ""), 16) == play))
    if not hit:
        raise Unmeasurable(
            "Sound_PlaySFX was never entered during the drop — the spring fired no "
            "sound, so there is no SFX whose voice could be observed")

    series = []
    for _ in range(SAMPLE_FRAMES):
        await b.call("emulator/run_frames", {"frames": 1})
        series.append(await z80_byte(b, mask_addr))
    return series


def window(series, baseline, value):
    """Indices where `series` shows `value` and the baseline did not."""
    return [i for i, v in enumerate(series)
            if v == value and baseline[i] != value]


def sample(rom, lst, mask_addr, syms, equs):
    """Boot ONE emulator instance on `rom` and return its mask series.

    The instance is spawned OUTSIDE the event loop and torn down before the next
    leg starts: aether_emulator is a synchronous context manager that calls
    asyncio.run() internally, so nesting it inside a running loop raises. One
    process per leg is also what makes the legs independent — nothing carries over
    from a poisoned run into the next."""
    with aether_emulator(rom, symbols=lst) as sock:
        return asyncio.run(run_leg(sock, lst, mask_addr, syms, equs))


def main_async(rom, lst, out):
    syms, equs = parse_syms(lst)
    for need in ("Player_1", "Sound_PlaySFX"):
        if need not in syms:
            raise Unmeasurable(f"{need} is not in {lst} — wrong ROM/listing pair?")
    for need in ("SST_x_pos", "SST_y_pos", "SST_x_vel"):
        if need not in equs:
            raise Unmeasurable(f"{need} has no EQU in {lst}")
    if "SND_FM_SCRATCH_MASK" not in equs:
        raise Unmeasurable(
            "SND_FM_SCRATCH_MASK has no EQU in the listing — sound_api.emp must "
            "publish the FM carrier-mask scratch cell 68k-side. Nothing in the Z80 "
            "modules reaches the .lst, so that mirror is the only way to resolve this "
            "address; without it the witness would hardcode a Z80 address that moves "
            "whenever the sequencer RAM block changes size")
    if "SND_Z80_BASE" not in equs and "Z80_RAM" not in equs:
        # Not fatal: the mirror is SND_Z80_BASE + offset and SND_Z80_BASE is $A00000
        # on every Mega Drive, which is a BUS FACT rather than a build value. The
        # bounds check below is what makes the conversion safe.
        pass
    if "SFXID_SPRING" not in equs:
        raise Unmeasurable("SFXID_SPRING has no EQU — the spring is not wired in")

    # The listing carries the 68k BUS address ($A0xxxx); emulator/z80_read wants the
    # Z80's own 16-bit address. Convert, and bound-check the result rather than
    # trusting the subtraction: a mirror that stopped being an $A0-window address
    # would otherwise silently become a plausible-looking small number.
    bus_mask = equs["SND_FM_SCRATCH_MASK"]
    mask_addr = bus_mask - 0xA00000
    if not 0 <= mask_addr <= 0x1FFF:
        raise Unmeasurable(
            f"SND_FM_SCRATCH_MASK = ${bus_mask:08X} is not inside the Z80's 8 KB RAM "
            f"window at $A00000 (derived offset ${mask_addr:X}) — refusing to read a "
            f"byte this witness cannot show is the driver's scratch cell")
    sfx_id = equs["SFXID_SPRING"]
    blob = Path(__file__).resolve().parent.parent / "games" / "sonic4" / "data" / \
        "sound" / "sfx" / f"sfx_{sfx_id:02X}.bin"
    if not blob.is_file():
        raise Unmeasurable(f"{blob} does not exist")

    bank_off, nvoices, vN = locate_subject(rom, str(blob))
    masks = carrier_mask_table()
    if len(masks) != 8:
        raise Unmeasurable(f"carrier_mask_table() returned {len(masks)} entries, not 8")

    rom_bytes = Path(rom).read_bytes()
    alg0 = rom_bytes[bank_off + 0 * FMPATCH_LEN] & 7
    algN = rom_bytes[bank_off + vN * FMPATCH_LEN] & 7

    # The poison algorithm is chosen so its mask differs from BOTH natural masks;
    # picked from the table rather than written as a literal.
    natural = {masks[alg0], masks[algN]}
    cand = [a for a in range(8) if masks[a] not in natural]
    if not cand:
        raise Unmeasurable(
            "no YM algorithm has a carrier mask distinct from both of the subject's "
            "voices — this instrument cannot discriminate them")
    poison_alg = cand[0]
    pmask = masks[poison_alg]

    out.append(f"SUBJECT: sfx ${sfx_id:02X} (SFXID_SPRING, from the listing's EQU), "
               f"{nvoices} voices, stream switches to voice {vN} (decoded from its own "
               f"MEV_PATCH operand)")
    out.append(f"  patch bank at ROM ${bank_off:06X}; FmPatch_len = {FMPATCH_LEN} "
               f"(zyrinx_port.FMPATCH_LEN)")
    out.append(f"  natural algorithms: voice 0 = {alg0} -> mask ${masks[alg0]:02X}, "
               f"voice {vN} = {algN} -> mask ${masks[algN]:02X}")
    out.append(f"  poison algorithm {poison_alg} -> mask ${pmask:02X} "
               f"(chosen from carrier_mask_table(), distinct from both)")
    out.append(f"  Fm_ScratchMask at Z80 ${mask_addr:04X}")

    fails, legs = [], []
    tmp = tempfile.mkdtemp(prefix="sp6witness-")
    try:
        # ---- C1: the unpoisoned baseline -------------------------------
        base = sample(rom, lst, mask_addr, syms, equs)
        live = [i for i, v in enumerate(base) if v != 0]
        out.append(f"C1 BASELINE: {len(base)} samples, distinct values "
                   f"{sorted({f'${v:02X}' for v in set(base)})}")
        if not live:
            raise Unmeasurable(
                "Fm_ScratchMask stayed $00 for the whole window — nothing wrote the "
                "carrier-mask cell, so this instrument saw no FM volume write at all "
                "and the poison legs would compare two dead series")
        first = live[0]
        out.append(f"  C1: first write at frame {first}, value ${base[first]:02X}; "
                   f"the observed window is frames {first}..{len(base) - 1}")
        if masks[alg0] == masks[algN]:
            out.append(f"  C1: both voices mask to ${masks[alg0]:02X} — the baseline is "
                       f"flat BY CONSTRUCTION, so any difference L1/L2 show is one they "
                       f"caused and not one that was already there")
        if pmask in base:
            fails.append(f"C1: the poison mask ${pmask:02X} already appears in the "
                         f"unpoisoned baseline — the discriminator is not exclusive")
        legs.append("C1 baseline")

        obs = slice(first, len(base))

        # ---- L1: voice 0 is NOT what the driver resolves after the change ----
        p1 = os.path.join(tmp, "poison_v0.bin")
        off, old, new = poisoned_rom(rom, p1, bank_off, 0, poison_alg)
        out.append(f"L1 VOICE 0 IS NOT READ: ROM ${off:06X} ${old:02X} -> ${new:02X} "
                   f"(voice 0 fp_alg_fb; one byte, feedback preserved)")
        s1 = sample(p1, lst, mask_addr, syms, equs)
        changed1 = [i for i in range(first, len(base)) if s1[i] != base[i]]
        out.append(f"  L1: {len(changed1)} of {len(base) - first} observed samples moved"
                   + (f" (frames {changed1[0]}..{changed1[-1]})" if changed1 else ""))
        if changed1:
            fails.append(
                f"L1: poisoning voice 0 changed frames {changed1[0]}..{changed1[-1]} — "
                f"the driver is still resolving VOICE 0 after the stream selected voice "
                f"{vN}. That is the pre-SP-6 behaviour: Fm_PatchPtr returning "
                f"sx_patch_base raw and discarding sc_patch.")
        else:
            out.append("  L1: voice 0's bytes have NO effect on what the driver resolved "
                       "— the index moved the pointer off voice 0")
        legs.append("L1 voice 0 is not read")

        # ---- L2: voice N IS what it resolves (the SP-6 claim) ----------
        p2 = os.path.join(tmp, f"poison_v{vN}.bin")
        off, old, new = poisoned_rom(rom, p2, bank_off, vN, poison_alg)
        out.append(f"L2 VOICE {vN} IS READ: ROM ${off:06X} ${old:02X} -> ${new:02X} "
                   f"(voice {vN} fp_alg_fb; one byte)")
        s2 = sample(p2, lst, mask_addr, syms, equs)
        moved = [i for i in range(first, len(base)) if s2[i] == pmask and base[i] != pmask]
        stale = [i for i in range(first, len(base))
                 if s2[i] != pmask and s2[i] != 0 and base[i] != 0]
        out.append(f"  L2: {len(moved)} of {len(base) - first} observed samples moved to "
                   f"the poison mask ${pmask:02X}"
                   + (f" (frames {moved[0]}..{moved[-1]})" if moved else ""))
        if not moved:
            fails.append(
                f"L2: poisoning voice {vN} changed NOTHING — the driver never resolved "
                f"voice {vN}, so the mid-stream voice change did not take effect. This "
                f"is exactly the pre-SP-6 behaviour (Fm_PatchPtr returning "
                f"sx_patch_base raw and discarding the index).")
        elif stale:
            fails.append(
                f"L2: frames {stale[0]}..{stale[-1]} kept a non-poison, non-zero mask "
                f"inside the observed window — the driver resolved voice {vN} for only "
                f"part of it, which is not a clean mid-stream selection")
        legs.append(f"L2 voice {vN} is read")

        # ---- the discrimination: L1 and L2 must DISAGREE ---------------
        # This is the whole point. Poisoning two different voices of the same bank
        # must produce two different observations; if both legs looked the same the
        # instrument would be measuring something other than the resolved voice.
        if s1[obs] == s2[obs]:
            fails.append(
                "L1 and L2 produced IDENTICAL series over the observed window — "
                "poisoning voice 0 and voice {} had the same effect, so this "
                "instrument is not reading the resolved voice at all".format(vN))
        else:
            out.append(f"  DISCRIMINATION: L1 and L2 differ over frames "
                       f"{first}..{len(base) - 1}. Voice {vN}'s bytes decide what the "
                       f"driver resolved and voice 0's do not — which is the SP-6 claim, "
                       f"and is false of the engine this parcel replaced.")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    out.append(f"LEGS RUN: {len(legs)} — " + ", ".join(legs))
    if len(legs) != 3:
        fails.append(f"only {len(legs)} of 3 legs ran — an unrun leg is not a pass")
    return fails


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", default="s4.debug.bin")
    ap.add_argument("--lst", default="s4.debug.lst")
    a = ap.parse_args()
    out = []
    try:
        fails = main_async(a.rom, a.lst, out)
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
    print("\nRESULT: PASS — 3 legs (1 baseline + 2 poisons). After the stream's "
          "mid-stream voice change the driver resolves the SECOND voice out of the "
          "SFX's own FmPatch bank: poisoning that voice's bytes moves what the driver "
          "computed, and poisoning voice 0's does not. No claim is made about what "
          "reached the YM2612, and none about what it sounds like.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
