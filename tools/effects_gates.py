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
  4. handler SOURCE — `raster_source_gate`. Everything above asserts the program's WORDS; this is
     the only gate that observes the handler interpreting them, by breaking inside the region op
     and reading the source pointer it computed. A build that encodes an offset correctly and
     streams from the wrong base passes every other gate here.
  5. cost model vs reality — three fixtures from `raster_cost_probe`, asserted against the
     constants `raster_dsl.emp` actually ships. This is what keeps the measured model MEASURED:
     the values in the .emp are pinned to each other at build time, but only this checks them
     against hardware. F1 earns its place separately — it is the register write, the op whose
     dispatch Tier-3 item 2 cut from 80 cycles to 10, so it is the fixture that says the
     parcel reached the ROM (every other fixture moves by 8 cycles or less).
  6. scanline capability spans (P2 §8.2) — the TWO-FIXTURE differential: sonic4 (SCANLINE_CAPS
     $001F) against demo ($0000), asserting the DIFFERENCE matches the mask rather than an
     absolute span in either. Region spans include placer fill, so nothing here reads a byte
     count that fill can move; and the expectations are computed from each game's own declared
     mask plus the gated blocks in the engine sources, never from a list kept here.
  7. demo specialisation witness (P2 Task 8) — span absence PLUS the committed per-proc image
     pin. Lives in its own tool because its two halves fail on different things; run from here
     because this is the post-build command and the pytest lane runs before sigil.

Gates 6 and 7 boot no emulator, but they need a listing, so they cannot go in build.sh either
(build.sh runs pytest BEFORE the build — a listing read there is the previous build's).

Usage:
    python3 tools/effects_gates.py [--rom s4.debug.bin] [--lst s4.debug.lst]
                                   [--demo-lst demo.debug.lst] [--only NAME,...]
Exit: 0 all gates pass · 1 a gate failed · 2 a gate could not run (scene/setup problem)
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scene_spans import (capability_bits, expected_spans,  # noqa: E402
                         game_caps, lst_spans, lst_unpaired_spans)

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
    ap.add_argument("--demo-lst", default=str(AEON / "demo.debug.lst"),
                    help="the ZERO-capability fixture; the span gates are a two-fixture "
                         "differential and cannot run against one build")
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

    if wanted("raster_source"):
        ok, msg = run(["python3", str(AEON / "tools/raster_source_gate.py"),
                       "--rom", rom, "--lst", lst], "raster_source")
        results.append(("raster_source (handler streams from the encoded address)", ok, msg))

    if wanted("snapshot_poison"):
        ok, msg = run(["python3", str(AEON / "tools/snapshot_poison_gate.py"),
                       "--rom", rom, "--lst", lst], "snapshot_poison")
        results.append(("snapshot_poison (E-B: splices copy what the captured mask says)",
                        ok, msg))

    if wanted("cost_model"):
        base = emp_int("engine/effects/raster_dsl.emp", "RASTER_FIRE_BASE_CYC")
        fetch = emp_int("engine/effects/raster_dsl.emp", "RASTER_OP_FETCH_CYC")
        hit = emp_int("engine/effects/raster_dsl.emp", "RASTER_DISPATCH_HIT_CYC")
        tail = emp_int("engine/effects/raster_dsl.emp", "RASTER_OP_TAIL_CYC")
        # One burst word costs what the op's DESTINATION SPELLING costs (Tier-3 item 1):
        # `.cram_loop` still holds VDP_CTRL in a2 and writes `-4(a2)` (16 + dbf 10 = 26);
        # `.region_loop` / `.restore_loop` have spent a2 on their source cursor and write
        # the absolute VDP_DATA (20 + dbf 10 = 30). Two constants, read separately, so a
        # gate that priced every fixture with one of them cannot go quiet on the other.
        word_cram = emp_int("engine/effects/raster_dsl.emp", "RASTER_STREAM_WORD_CRAM_CYC")
        word_deep = emp_int("engine/effects/raster_dsl.emp", "RASTER_STREAM_WORD_DEEP_CYC")
        rung = emp_int("engine/effects/raster_dsl.emp", "RASTER_DISPATCH_RUNG_CYC")
        rungs = emp_int("engine/effects/raster_dsl.emp", "RASTER_DISPATCH_RUNGS")
        # The zero pre-test (Tier-3 item 2). OP_SET_REG is opcode 0 and the op fetch's own
        # `move.w (a1)+, d1` sets Z, so `.op_loop` decides it with one `beq.s` and no test
        # instruction ahead of the chain: `zhit` is a register write's WHOLE dispatch,
        # `zmiss` is what every other op pays to walk past it on top of its rung depth.
        # `rungs` survives as a structural fact (the chain's length) and is deliberately no
        # longer multiplied into anything here — that it stopped being a cost term is the
        # parcel.
        zhit = emp_int("engine/effects/raster_dsl.emp", "RASTER_DISPATCH_ZERO_HIT_CYC")
        zmiss = emp_int("engine/effects/raster_dsl.emp", "RASTER_DISPATCH_ZERO_MISS_CYC")
        wreg = emp_int("engine/effects/raster_dsl.emp", "RASTER_WORK_REG_CYC")
        # The blanking spin is per-op PROGRAM DATA since substrate item 1, so a work term is
        # a spinless base plus the spin the op actually carries. spin_cyc(n) = n*10 + 14: n
        # taken dbf iterations at 10 plus the expired one at 14.
        #
        # SINCE ITEM 1c THE SPIN IS SOLVED, NOT LOOKED UP: raster_dsl.emp centres each
        # burst in the MEASURED blanking window, so the value depends on where the op sits
        # in its fire. This gate re-derives it the same way it re-derives everything else —
        # from the .emp constants, longhand — rather than importing the probe's answer.
        # That is deliberate: the probe BUILDS the fixture, so a gate reading the probe's
        # spin could not tell a mis-built fixture from a mis-modelled one.
        cram_base = emp_int("engine/effects/raster_dsl.emp", "RASTER_WORK_CRAM_BASE_CYC")
        region_base = emp_int("engine/effects/raster_dsl.emp", "RASTER_WORK_REGION_BASE_CYC")
        hb_end = emp_int("engine/effects/raster_dsl.emp", "RASTER_HBLANK_END_CYC")
        hb_w10 = emp_int("engine/effects/raster_dsl.emp", "RASTER_HBLANK_WIDTH_X10")
        pre_cram = emp_int("engine/effects/raster_dsl.emp", "RASTER_PRE_CRAM_CYC")
        pre_region = emp_int("engine/effects/raster_dsl.emp", "RASTER_PRE_REGION_CYC")
        pre_restore = emp_int("engine/effects/raster_dsl.emp", "RASTER_PRE_RESTORE_CYC")
        depth_region = emp_int("engine/effects/raster_dsl.emp", "RASTER_DEPTH_REGION")
        depth_restore = emp_int("engine/effects/raster_dsl.emp", "RASTER_DEPTH_RESTORE")
        def spin_cyc(n): return n * 10 + 14
        def solve_spin(p, span):
            """n = round((END - p - 14 - (width + span)/2) / 10), in twentieths."""
            num = 20 * (hb_end - p - 14) - (hb_w10 + 10 * span)
            return (num + 100) // 200 if num > 0 else 0
        # Each fixture's LEADING-or-not position, spelled out. `p` is the modelled cycles
        # from the record's op-walk origin to this op's burst with a spin of zero.
        reg_op = fetch + zhit + wreg + tail                   # one whole OP_SET_REG
        spin_f3 = solve_spin(fetch + zmiss + hit + pre_cram, 2 * word_cram)  # leading cram 3w
        spin_f4 = solve_spin(fetch + zmiss + rung * depth_region + hit + pre_region, 2 * word_deep)
        spin_f5 = solve_spin(reg_op + fetch + zmiss + hit + pre_cram, 2 * word_cram)  # cram 3w, SECOND
        spin_f8 = solve_spin(fetch + zmiss + rung * depth_restore + hit + pre_restore, 2 * word_deep)
        # SAME OP, TWO WORK TERMS — this is the whole of item 1c in one line pair: F3's and
        # F5's cram ops are identical `stream_cram(34, 3 words)` and cost DIFFERENT amounts,
        # because F5's sits second and needs 11 fewer iterations to reach the same window.
        cram_f3 = cram_base + spin_cyc(spin_f3)
        cram_f5 = cram_base + spin_cyc(spin_f5)
        region = region_base + spin_cyc(spin_f4)
        # F0 is two priming records; F3 adds FIVE 3-word stream_cram fires. Both figures are
        # COMPUTED from the shipped constants, never typed in.
        #
        # F3 dropped 6 -> 5 fires and F5 5 -> 4 with substrate item 1: every stream op gained
        # a spin word, so a 3-word cram fire is 10 words where it was 9 and the old counts no
        # longer fit RASTER_BUF_SIZE. The probe REFUSES an over-cap program rather than
        # truncating it, which is what surfaced this; the counts here must track that file.
        f0 = 2 * (base - 16)                       # a no-op record is the fire base less the
                                                   # loop entry/exit a record WITH ops pays
        fire3 = base + fetch + zmiss + hit + cram_f3 + 3 * word_cram + tail
        expect_f3 = f0 + 5 * fire3
        # F4 (stream_pal_region, 3 words) — WIRED 2026-08-18 by the raster-substrate sweep, which
        # found it was the one fixture the --only list never named, leaving RASTER_WORK_REGION_CYC
        # the only work constant with NO path to hardware. It is not a spare: it is the sole
        # fixture covering the op the shipped OJZ water band fires.
        #
        # OP_PAL_REGION dispatches at DEPTH 1, so this pays ONE failed rung on top of the hit,
        # plus the not-taken zero pre-test every non-zero op now pays — raster.emp's `.op_loop`
        # tests opcode 0 on the fetch's own Z flag, then orders the chain OP_CRAM first, then
        # OP_PAL_REGION. That rung is the whole reason a naive reading looks broken: the model
        # puts region 32 cycles over cram (122 vs 90) while hardware measures a 48-cycle gap, and
        # the missing 16 is the rung, not an error in the constant.
        #
        # First measurement (2026-08-18, s4.debug.bin ab1055d4): F4 = 3968 cyc/frame, 566/fire,
        # against this expectation exactly. So the constant was right for the whole time nothing
        # was checking it — the gap was real, the drift never happened.
        fire_region = base + fetch + zmiss + rung + hit + region + 3 * word_deep + tail
        expect_f4 = f0 + 6 * fire_region
        # F1 (six one-reg_set fires) is here for a reason F0 and F3 cannot cover: it is the only
        # fixture whose op is a REGISTER WRITE, and since Tier-3 item 2 that op's dispatch is a
        # different mechanism from every other op's — the zero pre-test's taken branch, on the Z
        # flag the op fetch already set, rather than a walk down the compare chain. So F1 is the
        # only fixture here that can see the pre-test mis-modelled in the TAKEN direction; every
        # other fixture sees only the not-taken 8. It also used to be the dispatch-tax sentinel
        # (OP_SET_REG was the chain's fall-through, so appending an opcode made it dearer); that
        # job is gone because appending an opcode now moves no existing op's cost at all, and the
        # append is caught structurally by RASTER_DISPATCH_RUNGS' pin in the .emp.
        fire_reg = base + fetch + zhit + wreg + tail
        expect_f1 = f0 + 6 * fire_reg
        # F5 (reg_set + stream_cram 3 in ONE fire, R1 [S4-8]): the base is paid once, the
        # per-op bundles sum. It carries the same fall-through SetReg as F1, so it is the
        # SECOND fixture that can see a dispatch-chain change — and the only one that sees
        # it displace a CRAM burst (the mixed-fire landing question, spec §3.3).
        fire_mixed = base + (fetch + zhit + wreg + tail) \
                          + (fetch + zmiss + hit + cram_f5 + 3 * word_cram + tail)
        expect_f5 = f0 + 4 * fire_mixed            # F5 authors 4 fires (buffer cap; was 5)
        # F8 (pal_restore, 3 words, R1 claim 9): the restore dispatches at depth 4 (four
        # failed rungs + hit) with its own measured work constant.
        wrest = emp_int("engine/effects/raster_dsl.emp", "RASTER_WORK_RESTORE_BASE_CYC") \
                + spin_cyc(spin_f8)
        fire_rest = base + fetch + (zmiss + rung * 4 + hit) + wrest + 3 * word_deep + tail
        expect_f8 = f0 + 6 * fire_rest
        jf = tmp / "cost.json"
        p = subprocess.run(["python3", str(AEON / "tools/raster_cost_probe.py"),
                            "--rom", rom, "--lst", lst, "--only", "F0,F1,F3,F4,F5,F8",
                            "--out", str(jf)],
                           capture_output=True, text=True)
        if p.returncode != 0 or not jf.exists():
            results.append(("cost_model vs hardware", False,
                            (p.stdout + p.stderr).strip().splitlines()[-1:] or ["probe failed"]))
        else:
            d = json.loads(jf.read_text())
            got_f0 = d["F0"]["cycles"][0]
            got_f1 = d["F1"]["cycles"][0]
            got_f3 = d["F3"]["cycles"][0]
            got_f4 = d["F4"]["cycles"][0]
            got_f5 = d["F5"]["cycles"][0]
            got_f8 = d["F8"]["cycles"][0]
            ok = (got_f0 == f0 and got_f1 == expect_f1 and got_f3 == expect_f3
                  and got_f4 == expect_f4 and got_f5 == expect_f5 and got_f8 == expect_f8)
            results.append((f"cost_model vs hardware (F0 {f0}, F1 {expect_f1}, F3 {expect_f3}, "
                            f"F4 {expect_f4}, F5 {expect_f5}, F8 {expect_f8} — all computed from "
                            f"the shipped constants; F1/F5 carry the register write, the one op "
                            f"dispatched by the zero pre-test rather than by the chain, "
                            f"F4 is the region op at dispatch depth 1, F8 is the restore)", ok,
                            f"measured F0={got_f0} F1={got_f1} F3={got_f3} F4={got_f4} "
                            f"F5={got_f5} F8={got_f8}"))

    # ------------------------------------------------------------------
    # 6. Scanline capability spans — the §8.2 two-fixture differential.
    #
    # THE DIFFERENCE IS THE ASSERTION, never an absolute span in either fixture.
    # §8.2 requires the two-fixture form because a single poison can pass on a layout
    # accident, and because region spans include PLACER FILL: this parcel measured
    # every one of its elisions being absorbed by fill (demo's EndOfRom did not move
    # at all), so a gate reading a byte count would have been measuring the placer.
    # Presence/absence of the boundary symbols is fill-immune.
    #
    # Expectations come from each game's own `const SCANLINE_CAPS` binding and the
    # gated blocks in the engine sources — derived through the SAME enclosure rule the
    # lowering uses (a span survives only if every gate around it is raised), so a
    # nested span cannot be expected in a build that elides its parent. Nothing here
    # is a list of span names; a hand list is the copied-expectation defect.
    if wanted("scanline_spans"):
        if not Path(args.demo_lst).is_file():
            results.append(("scanline_spans (two-fixture differential)", False,
                            f"demo listing not found: {args.demo_lst} — run "
                            f"`DEBUG=1 ./build.sh demo`. A one-fixture run is not this gate."))
        else:
            bits = capability_bits()
            caps_s4, caps_demo = game_caps("sonic4"), game_caps("demo")
            got_s4, got_demo = lst_spans(lst), lst_spans(args.demo_lst)
            # A region needs TWO boundaries. A set-level comparison alone cannot tell a
            # span with one boundary from a span with two, and a poison that renamed a
            # single `_begin` walked straight through the first version of this gate.
            for fixture, path in (("sonic4", lst), ("demo", args.demo_lst)):
                unpaired = lst_unpaired_spans(path)
                results.append((
                    f"scanline_spans {fixture} boundary pairing",
                    not unpaired,
                    "every emitted span carries both _begin and _end" if not unpaired
                    else f"half-bracketed spans (a region with one boundary cannot be "
                         f"measured): {unpaired}"))
            want_s4, want_demo = expected_spans(caps_s4), expected_spans(caps_demo)
            # Depth-scoped: one row per capability, so a failure names the BIT rather
            # than a pile of span names. §8.2's three depths are all carried by spans,
            # so the scoping that matters at this layer is the capability itself.
            for cap in sorted(bits):
                spans = {s for s in (want_s4 | got_s4 | got_demo)
                         if s.startswith(cap[len("CAP_"):].lower())}
                if not spans:
                    # A declared capability nobody gates is REPORTED, not skipped in
                    # silence: "no row" and "row passed" look identical in a totals
                    # line, and a capability that quietly stopped being gated would
                    # disappear exactly here. Today CAP_TRANSITIONS is legitimately in
                    # this state (blocked on a sigil-side refreeze — see the note at
                    # parallax.emp's capability import), so this is informational
                    # rather than a failure; what it must never do is hide.
                    results.append((
                        f"scanline_spans {cap} — NOT GATED ANYWHERE (no bracketed span "
                        f"in either fixture; nothing specialises on this bit yet)",
                        True, "informational"))
                    continue
                raised_s4 = bool(caps_s4 & bits[cap])
                raised_demo = bool(caps_demo & bits[cap])
                exp_s4 = {s for s in spans if s in want_s4}
                exp_demo = {s for s in spans if s in want_demo}
                have_s4 = {s for s in spans if s in got_s4}
                have_demo = {s for s in spans if s in got_demo}
                ok = (have_s4 == exp_s4 and have_demo == exp_demo)
                # The differential itself: what the mask says should DIFFER between the
                # two fixtures, against what does.
                want_diff = sorted(exp_s4 ^ exp_demo)
                got_diff = sorted(have_s4 ^ have_demo)
                ok = ok and want_diff == got_diff
                results.append((
                    f"scanline_spans {cap} (sonic4 {'raised' if raised_s4 else 'clear'}, "
                    f"demo {'raised' if raised_demo else 'clear'}) — differential "
                    f"{want_diff}",
                    ok,
                    f"sonic4 {sorted(have_s4)} vs expected {sorted(exp_s4)}; "
                    f"demo {sorted(have_demo)} vs expected {sorted(exp_demo)}"))
            # The anti-vacuity floor: if no capability produced a row, every check above
            # was over an empty set and the gate would report success having asked nothing.
            if not any(r[0].startswith("scanline_spans ") for r in results):
                results.append(("scanline_spans (two-fixture differential)", False,
                                "no capability has a bracketed span in either fixture — "
                                "this gate measured nothing"))

    # ------------------------------------------------------------------
    # 7. The demo witness (Task 8): span absence + the committed per-proc image pin.
    if wanted("demo_witness"):
        ok, msg = run(["python3", str(AEON / "tools/demo_specialization_witness.py"),
                       "--sonic4-lst", lst, "--demo-lst", args.demo_lst], "demo_witness")
        results.append(("demo_witness (span absence + image pin)", ok, msg))

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
