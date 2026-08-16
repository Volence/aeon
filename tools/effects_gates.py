#!/usr/bin/env python3
"""effects_gates — run every emulator-backed effects gate, aggregated, in one command.

WHY THIS EXISTS. This tree has a documented, repeated failure: gates that were built carefully and
then run by nothing. `effects_budget_check` sat unwired long enough for a row to drift 10 bytes;
`s4lint` lints one no-op file; 147 pytest functions are invoked by no runner. The effects suite had
three more of them — the committed `ab_runner` scenes, `effects_scene_assert`, and (as of this
parcel) `raster_off_gate` and the cost-model fixtures — each with its own hand ritual and no single
thing that ran them. A gate nobody runs is documentation with a shebang.

These CANNOT go in `build.sh`: every one boots a headless emulator and takes tens of seconds. This
is the pre-merge / post-effects-change command instead, and the point is that it is ONE command.

WHAT IT RUNS

  1. scene determinism — `ab_runner --selfcheck` on each committed scene. Runs the SAME ROM twice
     and aborts if the two disagree. This is the gate on the gates: a nondeterministic scene makes
     every assertion downstream of it meaningless, and exit 2 from ab_runner says so specifically.
  2. raster program shape — `effects_scene_assert` on each scene's sidecar, against arm words
     DERIVED here from the scene's own pokes and the bands read out of the game source. Never
     copied from a table: two gates in this tree were written against copied numbers and would have
     passed on incorrect code.
  3. handler teardown — `raster_off_gate`, which is the EFX-7 gate.
  4. cost model vs reality — two fixtures from `raster_cost_probe`, asserted against the constants
     `raster_dsl.emp` actually ships. This is what keeps the measured model MEASURED: the values in
     the .emp are pinned to each other at build time, but only this checks them against hardware.

Usage:
    python3 tools/effects_gates.py [--rom s4.debug.bin] [--lst s4.debug.lst] [--only NAME,...]
Exit: 0 all gates pass · 1 a gate failed · 2 a gate could not run (scene/setup problem)
"""
import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

AEON = Path(__file__).resolve().parent.parent
HARNESS = Path("/home/volence/sonic_hacks/oracle/linux-port/harness")
SCENES = ("mid_band", "suppressed", "above_screen")


def emp_int(rel: str, name: str) -> int:
    """A `const NAME = <int>` out of an .emp source, so no expectation here is hand-copied."""
    txt = (AEON / rel).read_text()
    m = re.search(rf"^\s*(?:pub\s+)?const\s+{re.escape(name)}\s*=\s*(\$[0-9A-Fa-f]+|-?\d+)",
                  txt, re.M)
    if not m:
        raise SystemExit(f"effects_gates: cannot find `const {name}` in {rel}")
    v = m.group(1)
    return int(v[1:], 16) if v.startswith("$") else int(v)


def scene_pokes(name: str) -> dict:
    """The scene's own poke values — the inputs every expectation below is derived FROM."""
    sc = json.loads((AEON / "tools" / "scenes" / f"effects_raster_{name}.json").read_text())
    out = {}
    for step in sc.get("steps", []):
        if "poke" in step and "symbol" in step["poke"]:
            out[step["poke"]["symbol"]] = step["poke"].get("value")
    return out


def derive_arms(name: str, bands: dict) -> tuple[int, int, bool]:
    """(word 1, word 3, is the SetReg word present) for a scene, derived from its pokes.

    The schedule is two priming records at fire lines 0 and 1, then one record per LIVE channel.
    `Raster_BuildSchedule` writes the gap `L[k] - L[k-1] - 1` into the arm slot TWO records back,
    so word 1 (priming 0's arm) carries the gap that lands the FIRST authored record and word 3
    (priming 1's arm) the gap that lands the second. A record whose latched line is past its band
    ceiling is not emitted at all; one below its floor clamps UP to the floor.
    """
    pokes = scene_pokes(name)
    cam = pokes["Camera_Y"]
    lo0, hi0 = bands["ch0"]
    lo1, hi1 = bands["ch1"]
    # Channel 0's latched screen line is anchor - camera; channel 1 is never poked (see the
    # scenes README), so it sits at its preset anchor and clamps up to its band floor.
    l0 = pokes["Effects_World_Y"] - cam
    fires = []
    if l0 <= hi0:                                  # past the ceiling -> record suppressed
        fires.append(max(l0, lo0) - 1)             # below the floor -> clamps UP
    fires.append(lo1 - 1)                          # channel 1, clamped to its floor
    L = [0, 1] + fires

    def arm(i: int) -> int:
        return 0x8AFF if i + 2 >= len(L) else 0x8A00 | (L[i + 2] - L[i + 1] - 1)

    # The SetReg word belongs to channel 0's fire; it is on screen iff that record is emitted.
    return arm(0), arm(1), l0 <= hi0


def run(cmd: list[str], label: str) -> tuple[bool, str]:
    p = subprocess.run(cmd, capture_output=True, text=True)
    ok = p.returncode == 0
    tail = (p.stdout + p.stderr).strip().splitlines()
    return ok, (tail[-1] if tail else f"(no output, rc={p.returncode})")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", default=str(AEON / "s4.debug.bin"))
    ap.add_argument("--lst", default=str(AEON / "s4.debug.lst"))
    ap.add_argument("--only", default="", help="comma-separated gate names")
    args = ap.parse_args()
    rom, lst = str(Path(args.rom).resolve()), str(Path(args.lst).resolve())
    if not Path(rom).is_file():
        print(f"effects_gates: ROM not found: {rom} — build it first", file=sys.stderr)
        return 2
    want = set(args.only.split(",")) if args.only else None

    def wanted(n: str) -> bool:
        return want is None or n in want

    # The bands, read from the game source rather than restated. patchable(..., lo, hi) in SCREEN
    # lines; the first two calls in ojz_effects.emp are channels 0 and 1 of OJZ_TwoChannel.
    src = (AEON / "games/sonic4/data/effects/ojz_effects.emp").read_text()
    # The `ch:/lo:/hi:` triple, not the whole `patchable(...)` call: the first argument is itself
    # a preset call with its own parentheses, so any pattern trying to span from `patchable(` to
    # the band arguments has to cross a nested `)` and will not match.
    pat = re.findall(r"\bch:\s*(\d+)\s*,\s*lo:\s*(\d+)\s*,\s*hi:\s*(\d+)", src, re.S)
    bands = {f"ch{c}": (int(lo), int(hi)) for c, lo, hi in pat}
    if "ch0" not in bands or "ch1" not in bands:
        print("effects_gates: could not read both patchable bands out of ojz_effects.emp — the "
              "call spelling changed, so every derived expectation below would be guesswork",
              file=sys.stderr)
        return 2
    print(f"effects_gates  ROM {rom}")
    print(f"  bands (screen lines), read from ojz_effects.emp: "
          f"ch0 {bands['ch0'][0]}..{bands['ch0'][1]}  ch1 {bands['ch1'][0]}..{bands['ch1'][1]}\n")

    results: list[tuple[str, bool, str]] = []
    tmp = Path(tempfile.mkdtemp(prefix="effects-gates-"))

    for name in SCENES:
        if not wanted(f"scene:{name}"):
            continue
        out = tmp / name
        ok, msg = run(["python3", str(HARNESS / "ab_runner.py"), "--old", rom, "--new", rom,
                       "--scene", str(AEON / "tools/scenes" / f"effects_raster_{name}.json"),
                       "--out", str(out), "--selfcheck"], name)
        results.append((f"scene:{name} determinism", ok, msg))
        if not ok:
            continue
        w1, w3, setreg = derive_arms(name, bands)
        cmd = ["python3", str(AEON / "tools/effects_scene_assert.py"), str(out / "new/hashes.json"),
               "--expect-word", f"1={hex(w1)}", "--expect-word", f"3={hex(w3)}",
               "--expect-present" if setreg else "--expect-absent", "0x8C89"]
        ok2, msg2 = run(cmd, name)
        results.append((f"scene:{name} shape (word1={w1:#06x} word3={w3:#06x}, "
                        f"$8C89 {'present' if setreg else 'absent'})", ok2, msg2))

    if wanted("raster_off"):
        ok, msg = run(["python3", str(AEON / "tools/raster_off_gate.py"),
                       "--rom", rom, "--lst", lst], "raster_off")
        results.append(("raster_off (EFX-7 teardown)", ok, msg))

    if wanted("cost_model"):
        base = emp_int("engine/effects/raster_dsl.emp", "RASTER_FIRE_BASE_CYC")
        fetch = emp_int("engine/effects/raster_dsl.emp", "RASTER_OP_FETCH_CYC")
        hit = emp_int("engine/effects/raster_dsl.emp", "RASTER_DISPATCH_HIT_CYC")
        tail = emp_int("engine/effects/raster_dsl.emp", "RASTER_OP_TAIL_CYC")
        word = emp_int("engine/effects/raster_dsl.emp", "RASTER_STREAM_WORD_CYC")
        cram = emp_int("engine/effects/raster_dsl.emp", "RASTER_WORK_CRAM_CYC")
        # F0 is two priming records; F3 adds six 3-word stream_cram fires. Both figures are
        # COMPUTED from the shipped constants, never typed in.
        f0 = 2 * (base - 16)                       # a no-op record is the fire base less the
                                                   # loop entry/exit a record WITH ops pays
        fire3 = base + fetch + hit + cram + 3 * word + tail
        expect_f3 = f0 + 6 * fire3
        jf = tmp / "cost.json"
        p = subprocess.run(["python3", str(AEON / "tools/raster_cost_probe.py"),
                            "--rom", rom, "--lst", lst, "--only", "F0,F3", "--out", str(jf)],
                           capture_output=True, text=True)
        if p.returncode != 0 or not jf.exists():
            results.append(("cost_model vs hardware", False,
                            (p.stdout + p.stderr).strip().splitlines()[-1:] or ["probe failed"]))
        else:
            d = json.loads(jf.read_text())
            got_f0, got_f3 = d["F0"]["cycles"][0], d["F3"]["cycles"][0]
            ok = got_f0 == f0 and got_f3 == expect_f3
            results.append((f"cost_model vs hardware (F0 {f0}, F3 {expect_f3} — both computed "
                            f"from the shipped constants)", ok,
                            f"measured F0={got_f0} F3={got_f3}"))

    print()
    bad = 0
    for label, ok, msg in results:
        print(f"  {'PASS' if ok else 'FAIL'}  {label}\n        {msg}")
        bad += 0 if ok else 1
    print()
    if bad:
        print(f"effects_gates: FAIL — {bad} of {len(results)} gate(s)")
        return 1
    print(f"effects_gates: OK — {len(results)} gates")
    return 0


if __name__ == "__main__":
    sys.exit(main())
