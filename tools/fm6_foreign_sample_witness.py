#!/usr/bin/env python3
"""fm6_foreign_sample_witness — what a DAC sample that does NOT come from the song
does to a song whose FM6 is a music voice but is not SH_F_FM6_ADAPTIVE.

THE CLAIM UNDER TEST (`docs/lens-findings.jsonl` GAP12-A2-9d, read off source and
never measured). Moving Trucks loads with SND_FM6_CHAN_PTR != 0 (a real FM6 music
channel) and SND_FM6_ADAPTIVE = 0. Then, for a sample started by anything other than
the song itself:

  * `Snd_StartSample` writes $2B <- $80 unconditionally and, with ADAPTIVE = 0,
    SKIPS its FM6 key-off ($28 <- $06);
  * while the sample plays, `Fm_NoteOnFreq`'s Layer-4 gate suppresses every FM6
    key-on (route CHROUTE_FM6 and SND_STAT_DAC_ACTIVE != 0);
  * `.stop` DC-centers ($2A <- $80) and then, with ADAPTIVE = 0, SKIPS the whole
    hand-back: no $2B <- $00 and no $28 <- $F6;
  * so after the sample the song's FM6 key-ons reach the chip again (DAC_ACTIVE is
    0) but ch6 is still in DAC mode ($2B = $80) and outputs the parked $80. FM6 is
    keyed and inaudible until the next song load writes $2B <- $00.

"Inaudible" here means exactly that last clause — the DAC enable bit is ON while
FM6 is keyed — because nothing on this bus renders audio (`capabilities.vgm:
false`). It is never a measured absence of sound.

WHY A PROBE ROM. No shipped shape can start a sample under Moving Trucks: the
canonical ROMs never call `Sound_PlayMusic` at all, `Sound_PlaySample` has ZERO call
sites in `engine/` and `games/`, and SFX cannot carry `$E2` (the transcoder never
builds a `Dac` event and refuses the DAC route). That absence is the row's verdict,
LATENT; this file measures what the latent path WOULD do, so the owner decision it
feeds rests on a measurement rather than a reading. The bus cannot poke the Z80
mailbox (`write_memory` refuses $A0xxxx), so the call has to be in the ROM. As in
`tools/fade_busy_stale_witness.py`:

  1. `games/sonic4/debug/game_debug.emp` must be byte-identical to its COMMITTED
     baseline (`git show HEAD:...`); a dirty file is a refusal.
  2. The patch adds ONE hotkey — RIGHT calls `Sound_PlaySample` with the kick's
     sample id — and nothing else. The Z80 driver, `sound_api.emp`, the sequencer
     and every song are untouched: the probe supplies only the caller the game
     does not have.
  3. `sigil build --native --config-a` writes both ROMs to a scratch dir.
  4. The file is restored from the committed baseline and the restore VERIFIED, in
     a `finally`.

`--build-only` stops after step 4 (no emulator): it proves the probe compiles, that
it DIFFERS from the unpatched config-A ROM, and that the tree comes back clean.

SIX LEGS, count asserted, three drives and three controls:

  L0 THE PROBE IS A PROBE   patched and unpatched config-A CRCs differ.
  L1 THE WATCH IS LIVE      the YM watch sees and matches Z80 YM traffic.
  L2 THE SUBJECT SONG       Moving Trucks is playing with FM6_CHAN_PTR != 0 and
                            FM6_ADAPTIVE == 0, and keys FM6 ($28 <- $F6) BEFORE any
                            sample — FM6 is a sounding voice to lose.
  L3 THE FOREIGN SAMPLE     RIGHT (`Sound_PlaySample`) under Moving Trucks; follow
                            the sample to its `.stop`, then hold HOLD_FRAMES.
  C1 THE HAND-BACK IS VISIBLE  the POSITIVE control, and it can fail: the drum-test
                            song (the one ADAPTIVE song) plays a drum of its own and
                            that drum's `.stop` epilogue must show $2B <- $00. If this
                            instrument cannot see a hand-back that the source says
                            happens, L3's "no hand-back" means nothing.
  C2 NO SAMPLE              the NEGATIVE control: the same Moving Trucks, reloaded
                            with the watch armed (A) and no sample. The load writes
                            $2B <- $00 and FM6 keys — the "ch6 is FM" baseline L3's
                            end state is compared against.

A MEASUREMENT witness, not a gate: it needs an off-canonical ROM, so it lives in no
runner. It FAILS only when it could not ask its question (the probe did not land, a
dead watch, a hole in the capture, a sample that never started, a control that
could not see what it controls for) — never on the engine's behaviour.

    export SIGIL_BUILD=<the sigil repo's release `sigil` binary>
    python3 tools/fm6_foreign_sample_witness.py --build-only   # no emulator
    python3 tools/fm6_foreign_sample_witness.py                # headless oracle-aether
    python3 tools/fm6_foreign_sample_witness.py --poison       # L1 must go loud
"""
import argparse
import asyncio
import os
import re
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
# The YM tap, the mirror decode, the boot and the drum-end criterion are the SAME
# instruments GAP12-A2-9b's witness measured with, imported rather than re-typed so
# the four instrument errors that file records (DAC_ACTIVE as the drum bound, any
# $80 as the stop, `dropped` as lost hits, the watch's own symbol attribution) stay
# fixed here too.
from song_load_mid_drum_witness import (  # noqa: E402
    _C, BOOT_FRAMES, DAC_RATE_HZ, MCLK_HZ, REG_DAC_DATA, REG_DAC_ENABLE, REG_KEY,
    YM_A0, Unmeasurable, YmTap, clean_boot, dc_center_at, mirror, parse_syms,
    run_until_drum_ends, start_drum, stop_epilogue,
)
from aether import BusClient  # noqa: E402  (client path added by the import above)
from aether_instance import aether_emulator  # noqa: E402
from cart_identity import CartMismatch, assert_cart_matches_disk  # noqa: E402

AEON = Path(__file__).resolve().parent.parent
TARGET = "games/sonic4/debug/game_debug.emp"
SOUND_CONSTANTS = AEON / "engine/sound/sound_constants.emp"


def seqchannel_len():
    """SeqChannel's size, read off the struct's OWN pin in sound_constants.emp.

    `SeqChannel_len` is a struct-derived size, which emp_consts does not fold, so the
    authority is the file's own `ensure(SeqChannel_len == N, ...)`. Reading the pin
    rather than typing N keeps a struct change from leaving this witness behind.
    """
    m = re.search(r"ensure\(\s*SeqChannel_len\s*==\s*(\d+)", SOUND_CONSTANTS.read_text())
    if not m:
        raise Unmeasurable("no `ensure(SeqChannel_len == N)` pin in sound_constants.emp — "
                           "the FM6 channel pointer cannot be derived")
    return int(m.group(1))

# The kick. Sample ids are 1-based DacSampleTable rows (sound_constants.emp: "the $E2
# operand (and SND_REQ_SAMPLE) is a 1-based sample id"); row 2 is the kick in
# games/sonic4/data/sound/dac_samples.emp, the same id song_drumtest.py fires as
# KICK. Its length is the blob's own size, read off disk, not typed in.
SAMPLE_ID = 2
KICK_PCM = AEON / "games/sonic4/data/sound/dac/kick.pcm"

# FM6's key bytes, derived: $28's data is (op-mask | chsel) and FM6 is part II
# channel-in-part 2, chsel (1 << 2) | 2 = 6 (sound_constants.emp's own
# `ensure((CHROUTE_FM6 - 3) == 2, ...)`).
FM6_CHSEL = (1 << 2) | 2
FM6_KEY_ON = _C["SND_FM_KEYON_OPMASK"] | FM6_CHSEL
FM6_KEY_OFF = FM6_CHSEL

START_WAIT_FRAMES = 30     # a posted sample is consumed at the next mailbox poll
DRUM_FRAMES = 30           # the kick is ~4.6 frames; generous
HOLD_FRAMES = 300          # ~5 s after the sample's `.stop`
PRE_FRAMES = 120           # L2: FM6 must key inside ~2 s of Moving Trucks

PATCH = [
    ("use engine.constants.{BUTTON_UP, BUTTON_C, BUTTON_A, BUTTON_B, BUTTON_START}",
     "use engine.constants.{BUTTON_UP, BUTTON_C, BUTTON_A, BUTTON_B, BUTTON_START,\n"
     "                      BUTTON_RIGHT}"),
    ("""        andi.b  #BUTTON_C, d0
        beq.s   .check_start""",
     """        andi.b  #BUTTON_C, d0
        beq.s   .probe_sample"""),
    ("""    .check_start:
        move.b  (Ctrl_1_Press).w, d0
        andi.b  #BUTTON_START, d0""",
     f"""    .probe_sample:
        // PROBE ONLY — added by tools/fm6_foreign_sample_witness.py, never committed.
        // RIGHT = Sound_PlaySample(kick). Nothing else in the tree changes; the
        // driver being measured is untouched.
        move.b  (Ctrl_1_Press).w, d0
        andi.b  #BUTTON_RIGHT, d0
        beq.s   .check_start
        moveq   #{SAMPLE_ID}, d0
        bsr.w   Sound_PlaySample
        rts
    .check_start:
        move.b  (Ctrl_1_Press).w, d0
        andi.b  #BUTTON_START, d0"""),
]


class Blocked(RuntimeError):
    """A precondition (env, a dirty tree) stopped the run before it started."""


def git_baseline(rel):
    r = subprocess.run(["git", "show", f"HEAD:{rel}"], cwd=AEON, capture_output=True)
    if r.returncode != 0:
        raise Blocked(f"cannot read the committed baseline of {rel}: "
                      f"{r.stderr.decode(errors='replace').strip()}")
    return r.stdout


def apply_patch(text):
    for old, new in PATCH:
        if text.count(old) != 1:
            raise Unmeasurable(
                f"the probe patch anchor is not unique in {TARGET} "
                f"({text.count(old)} matches) — the file moved under this witness and "
                f"patching it blind would produce a ROM that is not the probe:\n{old}")
        text = text.replace(old, new, 1)
    return text


def build_config_a(out_dir, tag, out):
    sigil = os.environ.get("SIGIL_BUILD")
    if not sigil or not Path(sigil).is_file():
        raise Blocked("SIGIL_BUILD is unset or does not name a file. It is set by NO "
                      "dotfile; export it before running this witness.")
    binp = Path(out_dir) / f"{tag}.bin"
    lstp = Path(out_dir) / f"{tag}.lst"
    r = subprocess.run([sigil, "build", "--aeon", str(AEON), "--native", "--config-a",
                        "-o", str(binp), "--emit-lst", str(lstp)],
                       cwd=AEON, capture_output=True, text=True)
    if r.returncode != 0:
        raise Unmeasurable(f"the {tag} config-A build FAILED (rc={r.returncode}):\n"
                           f"{r.stdout[-1500:]}\n{r.stderr[-1500:]}")
    crc = zlib.crc32(binp.read_bytes()) & 0xFFFFFFFF
    out.append(f"  built {tag}: crc={crc:08x} len={binp.stat().st_size}")
    return str(binp), str(lstp), crc


def hexes(rows):
    return [f"${v:02X}" for _, _, v in rows]


def ms(mclk):
    return mclk / MCLK_HZ * 1000


async def settle(b, tap, frames):
    for _ in range(frames):
        await b.call("emulator/run_frames", {"frames": 1})
        await tap.poll()


async def main_async(sock, rom, lst, probe_crc, plain_crc, poison, out):
    b = BusClient(socket_path=sock, client_id="fm6foreign", client_name="fm6_foreign_sample")
    await b.connect()
    loaded = await assert_cart_matches_disk(b, rom, out)
    if loaded != probe_crc:
        raise CartMismatch(f"the loaded cart's crc is {loaded:08x} but this run BUILT "
                           f"{probe_crc:08x} — the machine is not holding the probe ROM")
    syms, _ = parse_syms(lst)
    for need in ("Sound_PlaySample", "Sound_Dbg_Mirror", "Debug_MusicToggle"):
        if need not in syms:
            raise Unmeasurable(f"{need} is not a label in the probe listing — this is not "
                               f"the config-A probe this witness needs")
    base = syms["Sound_Dbg_Mirror"] & 0xFFFFFF
    kick_len = KICK_PCM.stat().st_size
    # Moving Trucks declares FM1..FM6 in order, and the loader caches the SeqChannel
    # of the CHROUTE_FM6 record (channels in DECLARATION order), so FM6 is slot 5.
    fm6_ptr_want = _C["SND_SEQ_CHANNELS"] + 5 * seqchannel_len()
    out.append(f"  Sound_Dbg_Mirror ${base:06X}; sample id {SAMPLE_ID} = kick, "
               f"{kick_len} bytes = {kick_len / DAC_RATE_HZ * 1000:.1f} ms at {DAC_RATE_HZ} Hz; "
               f"FM6 key on/off = ${FM6_KEY_ON:02X}/${FM6_KEY_OFF:02X} (derived)")

    fails, legs = [], []

    # ---------------- L0 ---------------------------------------------------------------
    out.append(f"L0 THE PROBE IS A PROBE: patched crc={probe_crc:08x} vs unpatched "
               f"crc={plain_crc:08x}")
    if probe_crc == plain_crc:
        fails.append("L0: patched and unpatched config-A ROMs are identical — the probe "
                     "hotkey never reached the build, so 'no sample started' would be a "
                     "fact about the patch")
    legs.append("L0 the probe is a probe")

    # ---------------- L1 ---------------------------------------------------------------
    await clean_boot(b, lst)
    tap1 = YmTap(b, base_addr=(0x00A00000 if poison else YM_A0))
    await tap1.arm("ym-L1")
    await settle(b, tap1, 30)
    out.append(f"L1 THE WATCH IS LIVE: seen={tap1.seen} matched={tap1.matched} "
               f"z80={tap1.z80} foreign={tap1.foreign} "
               f"holes={tap1.holes()} over 30 frames of Moving Trucks")
    fault = tap1.liveness_fault()   # the song_load witness's verdict: gates on via == "z80"
    if fault:
        fails.append(f"L1: {fault}")
    legs.append("L1 the watch is live")
    if poison:
        out.append("LEGS RUN: 2 — L0 and L1 only (poison mode stops here by design)")
        return fails, 2, 2

    # ---------------- L2: the subject song ------------------------------------------------
    await clean_boot(b, lst)
    tap = YmTap(b)
    await tap.arm("ym-L2L3")
    m0 = await mirror(b, base)
    await settle(b, tap, PRE_FRAMES)
    pre_keys = [x for x in tap.data(REG_KEY) if x[2] == FM6_KEY_ON]
    out.append(f"L2 THE SUBJECT SONG: {m0}")
    out.append(f"  L2: FM6 key-ons ${FM6_KEY_ON:02X} in {PRE_FRAMES} frames before any "
               f"sample: {len(pre_keys)}"
               + (f"; FM6_CHAN_PTR derived = ${fm6_ptr_want:04X} (6th channel, "
                  f"SND_SEQ_CHANNELS + 5 * SeqChannel_len)" if fm6_ptr_want else ""))
    if not m0.seq_active:
        raise Unmeasurable("L2: no song is playing at boot — the config-A autoplay did not "
                           "start Moving Trucks, so there is no subject")
    if m0.fm6_ptr == 0 or m0.fm6_adaptive != 0:
        raise Unmeasurable(f"L2: the booted song is not the row's posture (FM6_CHAN_PTR="
                           f"${m0.fm6_ptr:04X}, FM6_ADAPTIVE={m0.fm6_adaptive}); the "
                           f"question needs PTR != 0 and ADAPTIVE == 0")
    if not pre_keys:
        fails.append("L2: FM6 never keyed before the sample — there is no sounding FM6 "
                     "voice for L3 to lose, so L3 cannot show a loss")
    legs.append("L2 the subject song")

    # ---------------- L3: the foreign sample --------------------------------------------
    mark = tap.events[-1][1] if tap.events else 0
    await b.call("emulator/press", {"buttons": ["right"], "frames": 1})
    started = None
    for i in range(START_WAIT_FRAMES):
        await b.call("emulator/run_frames", {"frames": 1})
        await tap.poll()
        m = await mirror(b, base)
        if m.dac_active and m.rom_len > 0:
            started = (i + 1, m)
            break
    if started is None:
        raise Unmeasurable(f"L3: no sample was in flight within {START_WAIT_FRAMES} frames "
                           f"of RIGHT — Sound_PlaySample never reached Snd_StartSample")
    out.append(f"L3 THE FOREIGN SAMPLE: in flight after {started[0]} frame(s): {started[1]}")
    if started[1].rom_len > kick_len:
        fails.append(f"L3: ROM_LEN {started[1].rom_len} exceeds the kick's {kick_len} bytes — "
                     f"the sample in flight is not the one the probe asked for")
    samples, t_stop, why = await run_until_drum_ends(b, base, tap, DRUM_FRAMES)
    if t_stop is None:
        raise Unmeasurable("L3: the sample never reached its `.stop` inside the window")
    ena_start = tap.data(REG_DAC_ENABLE, lo=mark, hi=t_stop)
    run = tap.data(REG_DAC_DATA, lo=mark, hi=t_stop)
    keyoff_start = [x for x in tap.data(REG_KEY, lo=mark, hi=(run[0][1] if run else t_stop))
                    if x[2] == FM6_KEY_OFF]
    t_first, t_last = (run[0][1], run[-1][1]) if run else (None, None)
    fm6_on_during = [x for x in tap.data(REG_KEY, lo=t_first, hi=t_last)
                     if x[2] == FM6_KEY_ON] if run else []
    ep_ena, ep_key = stop_epilogue(tap, t_last)
    dc = dc_center_at(tap, mark, t_stop)
    out.append(f"  L3: $2B writes from the press to `.stop`: {hexes(ena_start) or 'none'}; "
               f"FM6 key-off ${FM6_KEY_OFF:02X} before the first $2A byte: "
               f"{len(keyoff_start)}")
    out.append(f"  L3: {len(run)} $2A bytes to `.stop` ({why}); last byte "
               f"{'$80 — `.stop`s own DC-center' if dc else 'NOT $80'}; FM6 key-ons "
               f"${FM6_KEY_ON:02X} while the sample streamed: {len(fm6_on_during)}")
    out.append(f"  L3: `.stop`'s OWN epilogue wrote $2B {hexes(ep_ena) or '(nothing)'} and "
               f"$28 {hexes(ep_key) or '(nothing)'}")
    await settle(b, tap, HOLD_FRAMES)
    after_ena = tap.data(REG_DAC_ENABLE, lo=t_stop)
    after_on = [x for x in tap.data(REG_KEY, lo=t_stop) if x[2] == FM6_KEY_ON]
    all_ena = tap.data(REG_DAC_ENABLE, lo=mark)
    last_ena = all_ena[-1][2] if all_ena else None
    out.append(f"  L3: over {HOLD_FRAMES} frames after `.stop`: $2B writes "
               f"{hexes(after_ena) or 'none'}; FM6 key-ons ${FM6_KEY_ON:02X}: {len(after_on)}"
               f"{f' (first at +{ms(after_on[0][1] - t_stop):.1f} ms)' if after_on else ''}")
    out.append(f"  L3: LAST $2B value written since the press: "
               f"{f'${last_ena:02X}' if last_ena is not None else 'none'} "
               f"-> ch6 is {'the DAC' if last_ena == 0x80 else 'FM' if last_ena == 0 else '?'} "
               f"while FM6 keys; mirror: {await mirror(b, base)}")
    if not ena_start:
        fails.append("L3: no $2B write at all between the press and `.stop` — "
                     "Snd_StartSample's DAC-enable was not captured, so the end state "
                     "below has no start to be compared with")
    legs.append("L3 the foreign sample")

    # ---------------- C1: the hand-back is visible (positive control) -------------------
    await clean_boot(b, lst)
    tapc1 = YmTap(b)
    await tapc1.arm("ym-C1")
    await start_drum(b, base, tapc1, out, "C1")
    c1 = await mirror(b, base)
    mark1 = tapc1.events[-1][1] if tapc1.events else 0
    s1, t_stop1, why1 = await run_until_drum_ends(b, base, tapc1, DRUM_FRAMES * 4)
    if t_stop1 is None:
        fails.append("C1: the drum-test song's drum never reached `.stop` — the positive "
                     "control could not run")
    else:
        run1 = tapc1.data(REG_DAC_DATA, lo=mark1, hi=t_stop1)
        ep_ena1, ep_key1 = stop_epilogue(tapc1, run1[-1][1] if run1 else None)
        out.append(f"C1 THE HAND-BACK IS VISIBLE (drum-test song, FM6_ADAPTIVE="
                   f"{c1.fm6_adaptive}): its own drum's `.stop` epilogue wrote $2B "
                   f"{hexes(ep_ena1) or '(nothing)'} and $28 {hexes(ep_key1) or '(nothing)'}")
        if c1.fm6_adaptive == 0:
            fails.append("C1: the drum-test song loaded with FM6_ADAPTIVE = 0 — the control "
                         "is not the adaptive case it claims to be")
        if not any(v == 0x00 for _, _, v in ep_ena1):
            fails.append("C1: the ADAPTIVE song's `.stop` epilogue showed no $2B <- $00 — "
                         "the source says it must, so this instrument cannot see a "
                         "hand-back and L3's 'no hand-back' says nothing")
    legs.append("C1 the hand-back is visible")

    # ---------------- C2: no sample (negative control) ----------------------------------
    await clean_boot(b, lst)
    tapc2 = YmTap(b)
    await tapc2.arm("ym-C2")
    await settle(b, tapc2, 10)
    mark2 = tapc2.events[-1][1] if tapc2.events else 0
    await b.call("emulator/press", {"buttons": ["a"], "frames": 1})
    await settle(b, tapc2, HOLD_FRAMES)
    ena2 = tapc2.data(REG_DAC_ENABLE, lo=mark2)
    on2 = [x for x in tapc2.data(REG_KEY, lo=mark2) if x[2] == FM6_KEY_ON]
    dac2 = tapc2.data(REG_DAC_DATA, lo=mark2)
    out.append(f"C2 NO SAMPLE: Moving Trucks reloaded (A), no sample; $2B writes "
               f"{hexes(ena2) or 'none'}; FM6 key-ons {len(on2)}; $2A data bytes "
               f"{len(dac2)} over {HOLD_FRAMES} frames")
    if not ena2:
        fails.append("C2: the reload wrote no $2B at all — Snd_LoadSong's step 1 was not "
                     "captured, so there is no 'ch6 is FM' baseline")
    legs.append("C2 no sample")

    for name, t in (("L1", tap1), ("L2/L3", tap), ("C1", tapc1), ("C2", tapc2)):
        if t.holes():
            fails.append(f"{name}: {t.holes()} gap(s) in the captured seq run — counts "
                         f"are floors, not measurements")

    out.append(f"LEGS RUN: {len(legs)} — " + ", ".join(legs))
    if len(legs) != 6:
        fails.append(f"only {len(legs)} of 6 legs ran — an unrun leg is not a pass")
    return fails, len(legs), 6


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--build-only", action="store_true",
                    help="build both ROMs, check L0, restore, exit — no emulator")
    ap.add_argument("--poison", action="store_true",
                    help="aim the YM watch where nothing writes; L1 must go loud")
    ap.add_argument("--keep", action="store_true", help="keep the scratch build dir")
    a = ap.parse_args()
    out = []
    tgt = AEON / TARGET
    baseline = None
    tmp = tempfile.mkdtemp(prefix="fm6-foreign-probe-")
    try:
        baseline = git_baseline(TARGET)
        if tgt.read_bytes() != baseline:
            raise Blocked(f"{TARGET} differs from its committed baseline; this witness "
                          f"patches it and restores it from HEAD, and will not restore "
                          f"over uncommitted work. Commit or stash first.")
        plain_bin, plain_lst, plain_crc = build_config_a(tmp, "unpatched", out)
        tgt.write_bytes(apply_patch(baseline.decode()).encode())
        probe_bin, probe_lst, probe_crc = build_config_a(tmp, "probe", out)
        tgt.write_bytes(baseline)
        if tgt.read_bytes() != baseline:
            raise Unmeasurable(f"the restore of {TARGET} did not verify")
        out.append(f"  {TARGET} restored from HEAD and verified byte-identical")
        if a.build_only:
            print("\n".join(out))
            if probe_crc == plain_crc:
                print("\nBUILD-ONLY: FAILED — the probe ROM is identical to the unpatched one")
                return 1
            print(f"\nBUILD-ONLY: OK — probe {probe_crc:08x} differs from unpatched "
                  f"{plain_crc:08x}; no emulator was started")
            return 0
        with aether_emulator(probe_bin, symbols=probe_lst) as sock:
            fails, ran, want = asyncio.run(main_async(
                sock, probe_bin, probe_lst, probe_crc, plain_crc, a.poison, out))
    except Blocked as e:
        print("\n".join(out))
        print(f"\nBLOCKED: {e}")
        return 3
    except (Unmeasurable, CartMismatch) as e:
        print("\n".join(out))
        print(f"\nUNMEASURABLE: {e}")
        return 2
    finally:
        if baseline is not None and tgt.read_bytes() != baseline:
            tgt.write_bytes(baseline)
            print(f"(restored {TARGET} from HEAD on the way out)")
        if a.keep:
            print(f"(scratch build dir kept at {tmp})")
    print("\n".join(out))
    if a.poison:
        if fails:
            print("\nPOISON OK — L1 went loud, as it must:")
            for f in fails:
                print(f"  * {f}")
            return 0
        print("\nPOISON FAILED: L1 passed on a watch aimed where nothing writes.")
        return 1
    if fails:
        print("\nRESULT: COULD NOT MEASURE CLEANLY")
        for f in fails:
            print(f"  * {f}")
        return 1
    print(f"\nRESULT: MEASURED — {ran} of {want} legs (3 drives + 3 controls). The numbers "
          f"above are the finding; this witness asserts only that it could ask its "
          f"question.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
