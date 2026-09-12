#!/usr/bin/env python3
"""fade_busy_stale_witness — can a caller observe a stale SND_STAT_FADE_BUSY = 1
after a `Sound_StopMusic` lands mid-fade?

THE CLAIM UNDER TEST (`docs/lens-findings.jsonl` GAP12-A2-11b, booked severity LOW
with the note "No callers today"). `SND_STAT_FADE_BUSY` is written only by
`Fade_Ramp`, and `Fade_Ramp` is reached only from `Sequencer_Frame`'s preamble,
past three gates: SND_SEQ_ACTIVE != 0, SND_PAUSED == 0, SND_SEQ_CHCOUNT != 0.
`Sound_StopMusic` -> `Sequencer_StopAll` clears SND_SEQ_ACTIVE. So on the source
reading nothing can ever write that byte again, and `Sound_IsFading` returns 1
forever. This file asks whether the machine agrees, and for how long.

WHY THIS ONE NEEDS A PURPOSE-BUILT ROM, and what was tried first. The observation
half is free: the config-A profile mirrors Z80 RAM $1F00.. into `Sound_Dbg_Mirror`
in 68k RAM every VBlank, and SND_STAT_FADE_BUSY lands at a derived offset in it —
the SAME byte `Sound_IsFading` reads, one VBlank fresh. The TRIGGER half has no
path at all:

  * `read_memory`/`emulator/read` REFUSE $A00000-$A0FFFF ("only cartridge space
    ... and work RAM ... are readable in this slice"), and `write_memory` refuses
    it too ("only the work-RAM window is writable"), so the fade mailbox slot
    FADE_SLOT $A01F05 cannot be poked from the bus.
  * Nothing in the ROM starts a fade. `Sound_FadeOut`, `Sound_FadeIn`,
    `Sound_FadeCmd`, `Sound_FadeOutStop`, `Sound_FadeOutPause` and
    `Sound_IsFading` have ZERO call sites across `engine/` and `games/` — which is
    the booking's own "No callers today", confirmed rather than assumed.
  * There is no register-write method on this bus, so the 68k cannot be steered
    into `Sound_FadeOut` either.

So the only way to ask the question is a ROM that makes the call. This file builds
one, and builds it the way the brief requires — a purpose-built OFF-CANONICAL probe
rather than a bent canonical ROM:

  1. `games/sonic4/debug/game_debug.emp` is verified byte-identical to its COMMITTED
     baseline (`git show HEAD:...`). A dirty file is a refusal, never a silent
     overwrite.
  2. The patch below adds exactly two hotkeys to the existing debug chain — DOWN
     calls `Sound_FadeOut`, LEFT calls `Sound_StopMusic` — and nothing else. THE
     SUBJECT IS UNCHANGED: not one byte of the Z80 driver, `sound_api.emp` or the
     sequencer moves. The probe supplies only the CALL the game does not yet make,
     which is the exact condition the booking describes.
  3. `sigil build --native --config-a` writes the probe ROM to a scratch dir. The
     canonical ROMs are never touched; their CRCs are landing pins.
  4. The file is restored from the committed baseline and the restore is VERIFIED,
     in a `finally`, so a crash mid-run cannot leave the tree patched.

L0 then requires the probe ROM's CRC to DIFFER from the unpatched config-A ROM's,
built in the same run. Without that, a patch that silently failed to apply would
produce "the fade never started" and read as a finding about the driver.

SIX LEGS, count asserted, four drives and two controls:

  L0 THE PROBE IS A PROBE  patched and unpatched config-A CRCs differ.
  L1 A FADE REALLY STARTS  after DOWN, the mirrored SND_STAT_FADE_BUSY reads 1.
  L2 STOP MID-FADE         with it still 1, LEFT (`Sound_StopMusic`); then watch
                           the byte for the rest of the run.
  L3 DOES A NEW SONG CLEAR IT  a later `Sound_PlayMusic` (A) — "forever" and "until
                           the next song" are very different hazards.
  C1 FADE TO COMPLETION    the CONTROL: the same fade with NO stop must return the
                           byte to 0 by itself. Without it, "it stayed 1" does not
                           distinguish the stop from a byte that is simply latched.
  C2 NO FADE AT ALL        the second CONTROL: from the same boot the byte reads 0
                           throughout, so a 1 is a fade and not a mirror decoding
                           the wrong offset.
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
from suite_paths import add_client_path  # noqa: E402
add_client_path()
from aether import BusClient  # noqa: E402
from aether_instance import aether_emulator, read_bytes, unprefix  # noqa: E402
from emp_consts import emp_consts  # noqa: E402

AEON = Path(__file__).resolve().parent.parent
TARGET = "games/sonic4/debug/game_debug.emp"
SOUND_CONSTANTS = AEON / "engine/sound/sound_constants.emp"

BOOT_FRAMES = 300
FADE_WAIT_FRAMES = 240     # the default rate is the FASTEST (~2 s full fade)
HOLD_FRAMES = 300          # ~5 s of watching the byte after the stop

# --- the probe patch -------------------------------------------------------------
# Two anchors, both unique in the baseline file. The first re-points the C-hotkey's
# fallthrough at the probe chain; the second inserts the chain itself. Widths stay
# explicit (`beq.s`, `bsr.w`) because that file's own STRUCTURAL WIDTH PIN requires
# every instruction size ahead of its trailing `align 2` to be fixed.
PATCH = [
    ("use engine.constants.{BUTTON_UP, BUTTON_C, BUTTON_A, BUTTON_B, BUTTON_START}",
     "use engine.constants.{BUTTON_UP, BUTTON_C, BUTTON_A, BUTTON_B, BUTTON_START,\n"
     "                      BUTTON_DOWN, BUTTON_LEFT}"),
    ("""        andi.b  #BUTTON_C, d0
        beq.s   .check_start""",
     """        andi.b  #BUTTON_C, d0
        beq.s   .probe_fade"""),
    ("""    .check_start:
        move.b  (Ctrl_1_Press).w, d0
        andi.b  #BUTTON_START, d0""",
     """    .probe_fade:
        // PROBE ONLY — added by tools/fade_busy_stale_witness.py, never committed.
        // DOWN = Sound_FadeOut, LEFT = Sound_StopMusic. Nothing else in the tree
        // changes; the driver being measured is untouched.
        move.b  (Ctrl_1_Press).w, d0
        andi.b  #BUTTON_DOWN, d0
        beq.s   .probe_stop
        bsr.w   Sound_FadeOut
        rts
    .probe_stop:
        move.b  (Ctrl_1_Press).w, d0
        andi.b  #BUTTON_LEFT, d0
        beq.s   .check_start
        bsr.w   Sound_StopMusic
        rts
    .check_start:
        move.b  (Ctrl_1_Press).w, d0
        andi.b  #BUTTON_START, d0"""),
]


class Unmeasurable(RuntimeError):
    """The run could not ask its question — never reported as a pass."""


class Blocked(RuntimeError):
    """A precondition (env, a dirty tree) stopped the run before it started."""


def parse_syms(lst):
    syms = {}
    for line in open(lst, errors="replace"):
        m = re.match(r"^\(\d+\)\s+\d+/([0-9A-Fa-f]+)\s+:\s+(\w+):", line)
        if m:
            syms.setdefault(m.group(2), int(m.group(1), 16))
    return syms


def git_baseline(rel):
    r = subprocess.run(["git", "show", f"HEAD:{rel}"], cwd=AEON,
                       capture_output=True)
    if r.returncode != 0:
        raise Blocked(f"cannot read the committed baseline of {rel}: "
                      f"{r.stderr.decode(errors='replace').strip()}")
    return r.stdout


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


def apply_patch(text):
    for old, new in PATCH:
        if text.count(old) != 1:
            raise Unmeasurable(
                f"the probe patch anchor is not unique in {TARGET} "
                f"({text.count(old)} matches) — the file moved under this witness and "
                f"patching it blind would produce a ROM that is not the probe:\n{old}")
        text = text.replace(old, new, 1)
    return text


async def rd(b, addr, n):
    return bytes.fromhex(unprefix(await read_bytes(b, addr & 0xFFFFFF, n)))


async def busy(b, base, off):
    return (await rd(b, base + off, 1))[0]


async def seq_active(b, base, off):
    return (await rd(b, base + off, 1))[0]


async def boot(b, lst):
    await b.call("emulator/watchpoint_clear", {"all": True})
    await b.call("emulator/reset", {})
    await b.call("emulator/load_symbols", {"path": lst})
    await b.call("emulator/run_frames", {"frames": BOOT_FRAMES})


async def wait_busy(b, base, off, want, frames):
    """Run up to `frames` frames; return (frames_taken or None, trace)."""
    trace = []
    for i in range(frames):
        await b.call("emulator/run_frames", {"frames": 1})
        v = await busy(b, base, off)
        trace.append(v)
        if v == want:
            return i + 1, trace
    return None, trace


async def main_async(sock, lst, probe_crc, plain_crc, out):
    c = emp_consts(SOUND_CONSTANTS)
    for n in ("SND_STAT_FADE_BUSY", "SND_REQ_BASE", "SND_STAT_SEQ_ACTIVE"):
        if n not in c:
            raise Unmeasurable(f"{n} could not be folded out of {SOUND_CONSTANTS}")
    # Mirror layout authority: engine/debug/sound_debug.emp copies Z80 $1F00..$1F2F to
    # Sound_Dbg_Mirror[0..47], so the offset is the field's own address minus the base.
    off_busy = c["SND_STAT_FADE_BUSY"] - c["SND_REQ_BASE"]
    off_seq = c["SND_STAT_SEQ_ACTIVE"] - c["SND_REQ_BASE"]

    b = BusClient(socket_path=sock, client_id="fadebusy", client_name="fade_busy_stale")
    await b.connect()
    syms = parse_syms(lst)
    if "Sound_Dbg_Mirror" not in syms:
        raise Unmeasurable("Sound_Dbg_Mirror is not in the probe listing — without the "
                           "mirror there is no way to read a Z80 RAM byte from this bus")
    base = syms["Sound_Dbg_Mirror"] & 0xFFFFFF
    out.append(f"  Sound_Dbg_Mirror ${base:06X}; SND_STAT_FADE_BUSY at mirror byte "
               f"{off_busy} (= ${c['SND_STAT_FADE_BUSY']:04X} - ${c['SND_REQ_BASE']:04X}), "
               f"SND_STAT_SEQ_ACTIVE at {off_seq} — both derived, not typed in")

    fails, legs = [], []

    # ---------------- L0: the probe really is a probe --------------------------------
    out.append(f"L0 THE PROBE IS A PROBE: patched crc={probe_crc:08x} vs unpatched "
               f"config-A crc={plain_crc:08x}")
    if probe_crc == plain_crc:
        fails.append("L0: the patched and unpatched config-A ROMs are byte-identical — "
                     "the probe patch did not reach the build, so 'the fade never "
                     "started' below would be a fact about the patch, not the driver")
    else:
        out.append("  L0: they differ — the probe's two hotkeys are in this ROM")
    legs.append("L0 the probe is a probe")

    # ---------------- C2: no fade at all (run first: it is the baseline) -------------
    await boot(b, lst)
    v0 = await busy(b, base, off_busy)
    out.append(f"C2 NO FADE AT ALL: at +{BOOT_FRAMES} frames with the autoplay song "
               f"running and nothing pressed, FADE_BUSY = {v0}")
    got, trace = await wait_busy(b, base, off_busy, 1, 120)
    out.append(f"  C2: over a further 120 frames it read "
               f"{sorted(set(trace))} — {'NEVER 1' if got is None else f'1 after {got} frames'}")
    if got is not None:
        fails.append("C2: FADE_BUSY went to 1 with no fade requested — either something "
                     "else starts a fade or the mirror offset is decoding the wrong "
                     "byte; either way L1/L2 below cannot mean what they say")
    if v0 != 0:
        fails.append(f"C2: FADE_BUSY is already {v0} at boot with no fade — same problem")
    legs.append("C2 no fade at all")

    # ---------------- L1: a fade really starts ---------------------------------------
    await boot(b, lst)
    await b.call("emulator/press", {"buttons": ["down"], "frames": 1})
    got, trace = await wait_busy(b, base, off_busy, 1, FADE_WAIT_FRAMES)
    out.append(f"L1 A FADE REALLY STARTS: after DOWN (`Sound_FadeOut`), FADE_BUSY reached "
               f"1 after {got} frame(s)" if got else
               f"L1 A FADE REALLY STARTS: FADE_BUSY never reached 1 in "
               f"{FADE_WAIT_FRAMES} frames after DOWN")
    if got is None:
        raise Unmeasurable(
            "L1: no fade ever started, so there is no mid-fade state for L2 to stop "
            "into. Either Sound_FadeOut is not reached or the driver refused the "
            "command; with C2 green the mirror decode is not the suspect")
    legs.append("L1 a fade really starts")

    # ---------------- L2: stop mid-fade ----------------------------------------------
    sa = await seq_active(b, base, off_seq)
    out.append(f"L2 STOP MID-FADE: FADE_BUSY = 1 and SND_STAT_SEQ_ACTIVE = {sa}; "
               f"pressing LEFT (`Sound_StopMusic`)")
    await b.call("emulator/press", {"buttons": ["left"], "frames": 1})
    got0, trace = await wait_busy(b, base, off_busy, 0, HOLD_FRAMES)
    sa2 = await seq_active(b, base, off_seq)
    if got0 is None:
        out.append(f"  L2: FADE_BUSY stayed 1 for all {HOLD_FRAMES} frames "
                   f"({HOLD_FRAMES / 59.92:.1f} s) after the stop. "
                   f"SND_STAT_SEQ_ACTIVE is now {sa2}, so the song really did stop and "
                   f"`Fade_Ramp` — the byte's only writer — is behind a gate that is now "
                   f"closed.")
    else:
        out.append(f"  L2: FADE_BUSY returned to 0 after {got0} frame(s) "
                   f"({got0 / 59.92 * 1000:.0f} ms) despite the stop; "
                   f"SND_STAT_SEQ_ACTIVE = {sa2}")
    legs.append("L2 stop mid-fade")

    # ---------------- L3: does a later song clear it? --------------------------------
    out.append("L3 DOES A NEW SONG CLEAR IT: pressing A (`Sound_PlayMusic`) with "
               f"FADE_BUSY = {await busy(b, base, off_busy)}")
    await b.call("emulator/press", {"buttons": ["a"], "frames": 1})
    got1, trace = await wait_busy(b, base, off_busy, 0, HOLD_FRAMES)
    out.append(f"  L3: FADE_BUSY "
               f"{f'returned to 0 after {got1} frame(s) ({got1 / 59.92 * 1000:.0f} ms)' if got1 else f'was STILL 1 after {HOLD_FRAMES} more frames'}"
               f"; SND_STAT_SEQ_ACTIVE = {await seq_active(b, base, off_seq)}")
    legs.append("L3 does a new song clear it")

    # ---------------- C1: the control — fade to completion, no stop -------------------
    await boot(b, lst)
    await b.call("emulator/press", {"buttons": ["down"], "frames": 1})
    got, _ = await wait_busy(b, base, off_busy, 1, FADE_WAIT_FRAMES)
    if got is None:
        fails.append("C1: the control's fade never started, so it cannot control anything")
    else:
        out.append(f"C1 FADE TO COMPLETION (control): the same fade, NO stop; FADE_BUSY "
                   f"reached 1 after {got} frame(s)")
        got0c, _ = await wait_busy(b, base, off_busy, 0, HOLD_FRAMES)
        if got0c is None:
            fails.append(f"C1: the control's FADE_BUSY never returned to 0 either, in "
                         f"{HOLD_FRAMES} frames — so L2's 'it stayed 1' says nothing "
                         f"about the stop; the byte is latched regardless")
        else:
            out.append(f"  C1: it returned to 0 by itself after {got0c} frame(s) "
                       f"({got0c / 59.92:.2f} s) when the ramp reached target — so the "
                       f"byte DOES clear on its own, and L2's result is about the stop")
    legs.append("C1 fade to completion")

    out.append(f"LEGS RUN: {len(legs)} — " + ", ".join(legs))
    if len(legs) != 6:
        fails.append(f"only {len(legs)} of 6 legs ran — an unrun leg is not a pass")
    return fails, len(legs), 6


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep", action="store_true", help="keep the scratch build dir")
    a = ap.parse_args()
    out = []
    tgt = AEON / TARGET
    baseline = None
    tmp = tempfile.mkdtemp(prefix="fade-probe-")
    try:
        baseline = git_baseline(TARGET)
        if tgt.read_bytes() != baseline:
            raise Blocked(
                f"{TARGET} differs from its committed baseline. This witness patches "
                f"that file and restores it from HEAD, and restoring over someone "
                f"else's uncommitted work is exactly the failure the house rule about "
                f"restoring from a COMMITTED baseline exists to prevent. Commit or "
                f"stash first.")
        plain_bin, plain_lst, plain_crc = build_config_a(tmp, "unpatched", out)
        tgt.write_bytes(apply_patch(baseline.decode()).encode())
        probe_bin, probe_lst, probe_crc = build_config_a(tmp, "probe", out)
        tgt.write_bytes(baseline)
        if tgt.read_bytes() != baseline:
            raise Unmeasurable(f"the restore of {TARGET} did not verify")
        out.append(f"  {TARGET} restored from HEAD and verified byte-identical")
        with aether_emulator(probe_bin, symbols=probe_lst) as sock:
            fails, ran, want = asyncio.run(
                main_async(sock, probe_lst, probe_crc, plain_crc, out))
    except Blocked as e:
        print("\n".join(out))
        print(f"\nBLOCKED: {e}")
        return 3
    except Unmeasurable as e:
        print("\n".join(out))
        print(f"\nUNMEASURABLE: {e}")
        return 2
    finally:
        # A crash must never leave the tree patched.
        if baseline is not None and tgt.read_bytes() != baseline:
            tgt.write_bytes(baseline)
            print(f"(restored {TARGET} from HEAD on the way out)")
        if a.keep:
            print(f"(scratch build dir kept at {tmp})")
    print("\n".join(out))
    if fails:
        print("\nRESULT: COULD NOT MEASURE CLEANLY")
        for f in fails:
            print(f"  * {f}")
        return 1
    print(f"\nRESULT: MEASURED — {ran} of {want} legs (4 drives + 2 controls).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
