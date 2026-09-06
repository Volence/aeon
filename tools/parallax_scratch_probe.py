#!/usr/bin/env python3
"""parallax_scratch_probe — does the LIVE-EFFECTS parallax scratch actually work?

A hook nobody has driven is a hook that compiles. This drives it end to end on a headless
emulator: arm the scratch, confirm the selector moved into RAM, poke ONE field of the RAM
copy, and show the engine's own per-frame output change because of it.

WHAT IT PROVES, and the shape of the proof is the point:

  * CONTROL FIRST, and it is an ABSENT control rather than a sampled one. Every run starts
    from `emulator/reset` and replays the SAME scripted approach (settle, walk right, arm,
    one frame), then records Hscroll_Buffer for N frames. Run 1 and run 2 touch nothing and
    are REQUIRED to be byte-identical. Without that determinism rung a "the buffer changed"
    result says nothing — a per-line deform buffer changes every frame on its own. Only
    after the machine has been shown to repeat itself does a poked run mean anything.
  * THEN the subject: the same approach again, poke one byte of the scratch, run the same N
    frames. The difference between run 3 and runs 1/2 is attributable to that byte and to
    nothing else, because every other input is identical by construction.

WHAT WOULD HAVE MADE IT FAIL (asked of the fixture before it was run, not after):
  * the arm never being read       -> Parallax_Current_Config still points at ROM after the
                                      arm frame; the probe refuses at that step
  * the copy being wrong           -> the scratch's first 30 bytes would not equal the ROM
                                      config's; compared byte for byte
  * the four cells being incomplete-> Target_Config / Transition_Frames non-zero, or
                                      Snap_Pending not set, after the install; all checked
  * the poke being ignored         -> run 3 identical to run 1, which is exactly the
                                      determinism rung's PASS condition and this run's FAIL

LOUD ON UNMEASURABLE. Served ROM not matching the file on disk; a symbol that will not
resolve; a scratch that is not where the listing says; a camera that never moved (with
Camera_X at 0 every scroll factor produces 0 and the experiment cannot discriminate). Each
is a refusal with its text, never a green.

USAGE
    python3 tools/parallax_scratch_probe.py --rom s4.debug.bin --lst s4.debug.lst

RUN IT FOREGROUND. It boots its own headless emulator via tools/aether_instance.py — never
the owner's socket.
"""
import argparse
import asyncio
import os
import sys
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from aether_instance import AetherInstance                      # noqa: E402
from aether import BusClient                                    # noqa: E402

HSCROLL_BYTES = 896            # 224 lines x {FG word, BG word}
CFG_HDR = 30                   # sizeof(parallax_config)
BAND_REC = 32                  # sizeof(band_record) for sonic4's capability set

# Header field offsets a panel writes (docs/2026-09-06-live-effects-ram-surface.md §6.3)
OFF_BAND_COUNT = 0x00
OFF_LAYER_MASK = 0x02
OFF_TRANSITION = 0x08
OFF_V_OFFSET = 0x06
# Band-record field offsets (§6.4), relative to the record
OFF_FACTOR_B_S1 = 0x04

SYMBOLS = [
    "Parallax_Scratch_Config", "Parallax_Scratch_Config_End", "Parallax_Scratch_Arm",
    "Parallax_Current_Config", "Parallax_Target_Config", "Parallax_Transition_Frames",
    "Parallax_Snap_Pending", "Hscroll_Buffer", "Camera_X",
]


def _int(v):
    s = str(v)
    return int(s.removeprefix("0x"), 16) if s.lower().startswith("0x") else int(s, 16)


async def lookup(c, name):
    """Resolve a symbol to its 24-BIT BUS address — what emulator/read wants."""
    try:
        r = await c.call("emulator/lookup_symbol", {"name": name})
    except Exception as exc:  # noqa: BLE001
        raise SystemExit(f"UNMEASURABLE: symbol {name!r} did not resolve ({exc}) — the probe "
                         f"cannot locate its subject; refusing to report a verdict") from exc
    return _int(r["addr"])


def bus24(v):
    """A 68000 `move.l` STORES $FFFFEA26 where the listing says $FFEA26. Comparing a
    stored pointer against a raw listing address is a false mismatch — which is exactly
    what this probe reported the first time it was run. Normalise both to the bus."""
    return v & 0xFFFFFF


async def rd(c, addr, length):
    r = await c.call("emulator/read", {"addr": hex(addr), "len": length})
    return bytes.fromhex(str(r["bytes"]).removeprefix("0x"))


async def wr(c, addr, value, width):
    await c.call("emulator/write_memory", {"addr": hex(addr), "value": value, "width": width})


async def frames(c, n):
    await c.call("emulator/run_frames", {"frames": n})


async def capture(c, hs, n):
    """Run n frames, recording Hscroll_Buffer after each."""
    out = []
    for _ in range(n):
        await frames(c, 1)
        out.append(await rd(c, hs, HSCROLL_BYTES))
    return out


def diff_lines(a, b):
    """Which of the 224 lines differ, and on which plane."""
    fg, bg = [], []
    for line in range(224):
        o = line * 4
        if a[o:o + 2] != b[o:o + 2]:
            fg.append(line)
        if a[o + 2:o + 4] != b[o + 2:o + 4]:
            bg.append(line)
    return fg, bg


async def reach_armed(c, s, a, *, first=False):
    """From RESET, replay the identical approach and leave the scratch installed.

    Every run goes through this and only this, so two runs differ in exactly what the
    caller pokes afterwards. Returns (camera_x, config_before_arming).
    """
    await c.call("emulator/reset", {})
    await frames(c, a.settle)
    await c.call("emulator/play_input", {"rows": [{"start": 0, "end": a.walk,
                                                   "buttons": ["right"]}],
                                         "maxFrames": a.walk + 2})
    await c.call("emulator/release_all", {})
    await frames(c, 8)
    camx = int.from_bytes(await rd(c, s["Camera_X"], 4), "big")
    cfg = bus24(int.from_bytes(await rd(c, s["Parallax_Current_Config"], 4), "big"))
    if first:
        print(f"\n      Camera_X = ${camx:08X} (pixel half ${camx >> 16:04X})")
        print(f"      Parallax_Current_Config before arming = ${cfg:08X}")
        if (camx >> 16) == 0:
            raise SystemExit("UNMEASURABLE: Camera_X's pixel half is 0. Every band scroll is "
                             "`camX >> shift`, so at camX 0 EVERY factor produces 0 and a "
                             "factor poke cannot discriminate. The walk did not move the "
                             "camera")
        if cfg == 0:
            raise SystemExit("UNMEASURABLE: no parallax config is active, so there is nothing "
                             "to copy and Parallax_InstallScratch is expected to refuse")
        if cfg >= 0xFF0000:
            raise SystemExit(f"UNMEASURABLE: the active config is already in RAM "
                             f"(${cfg:08X}); the probe expects a ROM config so the install "
                             f"is observable")
    await wr(c, s["Parallax_Scratch_Arm"], 1, 1)
    await frames(c, 1)
    return camx, cfg


async def body(c, rom_bytes, a):
    st = await c.call("emulator/status", {})
    if st["romBytes"] != rom_bytes:
        raise SystemExit(f"UNMEASURABLE: server serves {st['romBytes']} bytes, the ROM on disk "
                         f"is {rom_bytes} — a stale shim would answer every question about a "
                         f"different build")
    print(f"      server romPath={st['romPath']} romBytes={st['romBytes']} (matches)")

    s = {n: await lookup(c, n) for n in SYMBOLS}
    for k, v in s.items():
        print(f"      {k:<28} ${v:06X}")
    scratch = s["Parallax_Scratch_Config"]
    span = s["Parallax_Scratch_Config_End"] - scratch
    print(f"\n      scratch span = {span} bytes "
          f"(expected {CFG_HDR} + {BAND_REC} x 16 = {CFG_HDR + BAND_REC * 16})")
    if span != CFG_HDR + BAND_REC * 16:
        raise SystemExit(f"UNMEASURABLE: the scratch reserves {span} bytes, not the derived "
                         f"{CFG_HDR + BAND_REC * 16} — the probe's field offsets would be wrong")

    # ---- the NEGATIVE control: a fixture with no parallax config at all -----------------
    # An install that always fires would pass every check below and be wrong, so the other
    # half of the claim is that arming does NOT install when there is nothing to copy.
    #
    # ⚠ WHAT THIS MODE MEASURED ON demo.debug, and it is NOT what it was written to measure.
    # The arm was still set after a frame. That is not a dirty refusal: `Parallax_Update` is
    # never called in games/demo at all (grep-verified — its only callers are in
    # games/sonic4/test/ojz_scroll_test.emp), so the poll that would service and clear the arm
    # does not run. THE HOOK IS LINKED INTO demo.debug AND UNREACHABLE THERE. This mode
    # therefore reports three distinguishable outcomes and only calls one of them a failure —
    # a run that cannot reach the subject must say so instead of returning a verdict.
    if a.expect_refusal:
        await c.call("emulator/reset", {})
        await frames(c, a.settle)
        before = await rd(c, scratch, span)
        cfg = bus24(int.from_bytes(await rd(c, s["Parallax_Current_Config"], 4), "big"))
        print(f"\n  REFUSAL CONTROL — Parallax_Current_Config = ${cfg:08X} before arming")
        if cfg != 0:
            raise SystemExit(f"UNMEASURABLE: this fixture HAS an active config (${cfg:06X}), "
                             f"so it cannot exercise the refusal path — run it without "
                             f"--expect-refusal")
        await wr(c, s["Parallax_Scratch_Arm"], 1, 1)
        await frames(c, 1)
        cur = bus24(int.from_bytes(await rd(c, s["Parallax_Current_Config"], 4), "big"))
        arm = (await rd(c, s["Parallax_Scratch_Arm"], 1))[0]
        after = await rd(c, scratch, span)
        print(f"      after arming: Current_Config = ${cur:08X} (want $00000000), "
              f"arm = {arm} (want 0, engine-cleared)")
        print(f"      scratch bytes changed by the refused install: "
              f"{sum(1 for i in range(span) if before[i] != after[i])} of {span} (want 0)")
        bad = []
        if cur != 0:
            bad.append(f"the selector moved to ${cur:08X}; a refusal must write nothing")
        if before != after:
            bad.append("the scratch was written by a refused install")
        if bad:
            print("\n  FAIL — the refusal path is not clean:")
            for x in bad:
                print(f"      - {x}")
            return 1
        if arm != 0:
            print("\n  UNREACHABLE, NOT PASS — the arm is still set, which means the poll at "
                  "the head of Parallax_Update never ran. `Parallax_Update` has no caller in "
                  "games/demo, so this fixture cannot exercise the refusal arm at all. What "
                  "IS established here: arming wrote nothing — the selector is still 0 and "
                  "all 542 scratch bytes are untouched — because no code ran. That is a fact "
                  "about REACHABILITY, and it must not be read as the refusal being tested.")
            return 2
        print("\n  PASS — with no active config the hook refuses, writes nothing, and clears "
              "the arm.")
        return 0

    # ---- RUN 1: the scripted approach, then arm ---------------------------------------
    camx, cfg_rom = await reach_armed(c, s, a, first=True)
    rom_image = await rd(c, cfg_rom, span)

    # ---- STEP 1: check every cell the install is contracted to write -------------------
    cur = bus24(int.from_bytes(await rd(c, s["Parallax_Current_Config"], 4), "big"))
    tgt = int.from_bytes(await rd(c, s["Parallax_Target_Config"], 4), "big")
    tfr = (await rd(c, s["Parallax_Transition_Frames"], 1))[0]
    snp = (await rd(c, s["Parallax_Snap_Pending"], 1))[0]
    arm = (await rd(c, s["Parallax_Scratch_Arm"], 1))[0]
    print(f"\n  STEP 1 — one frame after arming:")
    print(f"      Parallax_Current_Config    = ${cur:08X}   (want ${scratch:08X})")
    print(f"      Parallax_Target_Config     = ${tgt:08X}   (want $00000000)")
    print(f"      Parallax_Transition_Frames = {tfr}          (want 0)")
    print(f"      Parallax_Scratch_Arm       = {arm}          (want 0, engine-cleared)")
    # Snap_Pending is DELIBERATELY not asserted to 1 here, and the reason is a real property
    # of where the arm is serviced rather than a softened check: the poll runs at the HEAD of
    # Parallax_Update, so the same frame's pass consumes the flag it was just handed. A 1 read
    # back after that frame would mean the snap was NOT consumed. It is reported, not judged.
    print(f"      Parallax_Snap_Pending      = {snp}          (0 = consumed by the same "
          f"frame's pass, which is the arm's whole point)")
    fails = []
    if cur != scratch:
        fails.append(f"Current_Config is ${cur:08X}, not the scratch ${scratch:08X}")
    if tgt != 0:
        fails.append(f"Target_Config is ${tgt:08X}, not 0")
    if tfr != 0:
        fails.append(f"Transition_Frames is {tfr}, not 0")
    if arm != 0:
        fails.append(f"the arm cell is {arm}, not cleared")

    # the copy itself: the scratch must equal the config that was ACTIVE, except
    # pcfg_transition, which the install deliberately forces to 1 (see the proc's banner).
    #
    # The source is NOT necessarily the pointer read before arming: the arm frame's own
    # boundary check can install a different section's preset before Parallax_Update runs,
    # and Parallax_Active_Config returns the TARGET during a transition. So the probe reads
    # the scratch and asks the ROM where it came from, rather than assuming.
    scr = await rd(c, scratch, span)
    n_bands = scr[OFF_BAND_COUNT]
    copied = CFG_HDR + BAND_REC * n_bands
    # The search MASKS pcfg_transition: the install deliberately forces it to 1, so a source
    # that authored 0 (the shipped default) is not findable byte-for-byte. Everything else
    # must match exactly, which is what makes the match evidence rather than a fit.
    body_after = bytes(scr[OFF_TRANSITION + 1:copied])
    head = bytes(scr[:OFF_TRANSITION])
    rom = open(a.rom, "rb").read()
    matched, src_transition = None, None
    at = -1
    while True:
        at = rom.find(head, at + 1)
        if at < 0:
            break
        if rom[at + OFF_TRANSITION + 1:at + copied] == body_after:
            matched, src_transition = at, rom[at + OFF_TRANSITION]
            break
    if matched is None:
        fails.append(f"the scratch's {copied} bytes do not match the pre-arm config "
                     f"(${cfg_rom:06X}) and do not appear anywhere in the ROM image — the "
                     f"copy is not a faithful copy of any config")
        print(f"      scratch[0:32] = {bytes(scr[:32]).hex()}")
        print(f"      rom    [0:32] = {bytes(rom_image[:32]).hex()}")
    else:
        same = ("the pre-arm pointer" if matched == cfg_rom else
                f"a DIFFERENT config from the pre-arm ${cfg_rom:06X} — the arm frame's own "
                f"boundary check installed this one first, which is the engine behaving "
                f"normally, not the copy going wrong")
        print(f"      copy: {copied} bytes ({n_bands} bands), byte-identical to the ROM "
              f"config at ${matched:06X} ({same}); pcfg_transition forced "
              f"{src_transition} -> {scr[OFF_TRANSITION]} by the install")
        if scr[OFF_TRANSITION] != 1:
            fails.append(f"pcfg_transition in the scratch is {scr[OFF_TRANSITION]}, not the "
                         f"1 the install forces — a later re-arm would be staged, not "
                         f"installed")
    if fails:
        print("\n  FAIL — the install did not honour its contract:")
        for f in fails:
            print(f"      - {f}")
        return 1

    # ---- STEP 2: the determinism rung. The control is ABSENT, not sampled. -------------
    run1 = await capture(c, s["Hscroll_Buffer"], a.frames)
    await reach_armed(c, s, a)
    run2 = await capture(c, s["Hscroll_Buffer"], a.frames)
    print(f"\n  STEP 2 — determinism rung ({a.frames} frames, re-approached, nothing touched):")
    if run1 != run2:
        first = next(i for i in range(a.frames) if run1[i] != run2[i])
        print(f"      FAIL — two identical runs diverge at frame {first}. Without a machine "
              f"that repeats itself, a 'the buffer changed' result is unattributable")
        return 1
    selfmove = sum(1 for i in range(1, a.frames) if run1[i] != run1[i - 1])
    print(f"      the two runs are byte-identical over all {a.frames} frames")
    print(f"      (and the buffer moves on its own on {selfmove}/{a.frames - 1} frame steps — "
          f"which is exactly why the control had to be absent rather than sampled)")

    # ---- STEP 3: the subject. One byte. ------------------------------------------------
    band0 = scratch + CFG_HDR
    old = (await rd(c, band0 + OFF_FACTOR_B_S1, 1))[0]
    new = 3 if old != 3 else 5
    await reach_armed(c, s, a)
    await wr(c, band0 + OFF_FACTOR_B_S1, new, 1)
    run3 = await capture(c, s["Hscroll_Buffer"], a.frames)
    print(f"\n  STEP 3 — band 0's band_factor_b_s1 (${band0 + OFF_FACTOR_B_S1:06X}) "
          f"{old} -> {new}, same approach, same {a.frames} frames:")
    changed = [i for i in range(a.frames) if run3[i] != run1[i]]
    if not changed:
        print("      FAIL — the poked run is byte-identical to the control. The engine did "
              "not read the edited field")
        return 1
    fg, bg = diff_lines(run1[0], run3[0])
    print(f"      frames whose Hscroll_Buffer differs from the control: "
          f"{changed} of {list(range(a.frames))}")
    print(f"      on frame 0: {len(fg)} FG lines and {len(bg)} BG lines differ "
          f"(BG lines {bg[:4]}..{bg[-4:] if len(bg) > 4 else ''})")
    o = (bg[0] * 4 + 2) if bg else 2
    print(f"      first differing BG word, line {bg[0] if bg else '-'}: "
          f"${int.from_bytes(run1[0][o:o + 2], 'big'):04X} -> "
          f"${int.from_bytes(run3[0][o:o + 2], 'big'):04X}")
    if not bg:
        print("      NOTE: the difference is on plane A only, which a Plane-B factor poke "
              "should not produce — report this rather than reading it as a pass")
        return 1

    # ---- STEP 4: a second, camera-independent field, so the result is not one field's ---
    await reach_armed(c, s, a)
    mask_old = int.from_bytes(await rd(c, scratch + OFF_LAYER_MASK, 2), "big")
    await wr(c, scratch + OFF_LAYER_MASK, 0, 2)
    run4 = await capture(c, s["Hscroll_Buffer"], a.frames)
    mchanged = [i for i in range(a.frames) if run4[i] != run1[i]]
    print(f"\n  STEP 4 — pcfg_layer_mask (${scratch + OFF_LAYER_MASK:06X}) "
          f"${mask_old:04X} -> $0000, same approach:")
    print(f"      frames differing from the control: {mchanged}")
    if not mchanged:
        print("      NOTE: disabling every band changed nothing. Reported, not excused")

    print("\n  PASS — the scratch is installed by the arm, the install honours all four "
          "selector cells, and an edit to the RAM copy reaches the engine's per-frame output.")
    return 0


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--rom", default="s4.debug.bin")
    p.add_argument("--lst", default="s4.debug.lst")
    p.add_argument("--settle", type=int, default=180, help="frames to boot into the act")
    p.add_argument("--walk", type=int, default=120, help="frames of RIGHT to move the camera")
    p.add_argument("--frames", type=int, default=6, help="frames per captured run")
    p.add_argument("--expect-refusal", action="store_true",
                   help="fixture with NO parallax config (demo): assert the hook refuses cleanly")
    a = p.parse_args()

    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    rom = a.rom if os.path.isabs(a.rom) else os.path.join(repo, a.rom)
    lst = a.lst if os.path.isabs(a.lst) else os.path.join(repo, a.lst)
    for f in (rom, lst):
        if not os.path.isfile(f):
            raise SystemExit(f"UNMEASURABLE: {f} does not exist")
    blob = open(rom, "rb").read()
    print(f"ROM   {rom}\n      {len(blob)} bytes, crc32 {zlib.crc32(blob) & 0xFFFFFFFF:08x}")

    inst = AetherInstance(rom, symbols=lst)
    sock = inst.start()

    async def go():
        c = BusClient(sock)
        await c.connect()
        return await body(c, len(blob), a)

    try:
        return asyncio.run(go())
    finally:
        inst.reap()


if __name__ == "__main__":
    sys.exit(main())
