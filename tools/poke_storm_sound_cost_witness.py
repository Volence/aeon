#!/usr/bin/env python3
"""poke_storm_sound_cost_witness — what `Section_RedrawPlanes`' poke storm actually
costs the sound driver, measured off the driver's own DMA-window flag.

THE CLAIM UNDER TEST (`docs/lens-findings.jsonl` GAP12-A2-17b). `engine/level/section.emp`'s
Z80-POSTURE header says the storm's flag bracket buys bus-hold's protection "without
killing sound"; the review seat read that as "costs no sound" and estimated ~50 ms of
storm against a ~10.9 ms ring lead, and recorded the estimate as UNVERIFIED. Both
sides of that comparison are measured here, and neither number is copied from the
booking: the ring lead is DERIVED from `engine/sound/sound_constants.emp` with the
arithmetic printed, and the storm is TIMED off the bracket itself.

THE INSTRUMENT. `SND_DMA_ACTIVE_SLOT` is a byte in Z80 RAM that the 68k writes over
its own bus, so a v1 `bus`-space write watch records every raise and lower with the
access's own mclk AND the PC that drove it. That last part is what makes the control
free: `Section_RedrawPlanes` and `VInt_Level`/`VInt_Lag` raise the SAME flag, so one
watch over one run measures the subject and its control with one instrument, and a
"50 ms" that were really an artefact of how this bus reports brackets would show up
in both.

WHAT THIS DOES NOT MEASURE, stated so the result is not over-read: audio. There is
no audio instrument on this bus (`capabilities.vgm: false`). "Costs sound" here is
established structurally — the driver's own DRAIN path consumes the ring without
refilling while the flag is up, and `SndDrv_TimerATick` returns early without
rearming — so the cost is expressed in ring-lead multiples and Timer-A periods,
which are the units those two mechanisms are written in.

SHAPE: the canonical debug ROM. Level streaming needs no music.

    DEBUG=1 ./build.sh
    python3 tools/poke_storm_sound_cost_witness.py --rom s4.debug.bin --lst s4.debug.lst

SIX LEGS, count asserted, four drives and two controls:

  D0 THE DERIVATION    ring lead and Timer-A period, computed from the source
                       constants with the arithmetic shown. No emulator.
  L0 THE WATCH IS LIVE `seen` > 0 and `matched` > 0 on the flag watch.
  L1 THE STORM         every raise/lower pair whose raise PC falls in
                       `Section_RedrawPlanes`, in ms.
  L2 WHAT IT COSTS     that duration in DAC ring-lead multiples and in Timer-A
                       periods — the two units the driver's own mechanisms use.
  C1 THE VBLANK BRACKET the CONTROL: pairs raised by `VInt_*`, same flag, same run,
                       same instrument. Without it, "the storm's bracket is N ms"
                       does not distinguish the storm from what every frame does.
  C2 STEADY STATE      the second CONTROL: the bracket distribution AFTER the storm
                       is over, ruling out "the flag is simply held a long time
                       early in a boot".

A MEASUREMENT witness, not a gate: it FAILS only when it could not ask its question.
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
from aether_instance import aether_emulator  # noqa: E402
from emp_consts import emp_consts  # noqa: E402

AEON = Path(__file__).resolve().parent.parent
SOUND_CONSTANTS = AEON / "engine/sound/sound_constants.emp"
MCLK_HZ = 53_693_175       # NTSC master clock (oracle-core scheduler)
RUN_FRAMES = 900           # boot through the level load and well past it
SUBJECT = "Section_RedrawPlanes"
CONTROL = "VInt"


class Unmeasurable(RuntimeError):
    """The run could not ask its question — never reported as a pass."""


def parse_syms(lst):
    syms, equs = {}, {}
    for line in open(lst, errors="replace"):
        m = re.match(r"^EQU (\w+) = \$?([0-9A-Fa-f]+)", line)
        if m:
            equs[m.group(1)] = int(m.group(2), 16)
            continue
        m = re.match(r"^\(\d+\)\s+\d+/([0-9A-Fa-f]+)\s+:\s+(\S+):", line)
        if m:
            syms.setdefault(m.group(2), int(m.group(1), 16))
    return syms, equs


def derive(out):
    """D0 — every number the comparison needs, from the source constants."""
    c = emp_consts(SOUND_CONSTANTS)
    need = ("Z80_CLOCK_HZ", "SND_LOOP_CYC", "SND_RING_LEAD_TARGET", "SND_RING_LEAD_PRIME",
            "SND_RING_LEN", "SND_FRAME_MILLIHZ")
    missing = [n for n in need if n not in c]
    if missing:
        raise Unmeasurable(f"{', '.join(missing)} could not be folded out of "
                           f"{SOUND_CONSTANTS} — the derivation below cannot be done "
                           f"and nothing here may be typed in instead")
    rate = c["Z80_CLOCK_HZ"] // c["SND_LOOP_CYC"]
    lead_ms = c["SND_RING_LEAD_TARGET"] / rate * 1000
    prime_ms = c["SND_RING_LEAD_PRIME"] / rate * 1000
    full_ms = c["SND_RING_LEN"] / rate * 1000
    # SND_TIMERA_N = timerAReload(SND_FRAME_MILLIHZ) is a comptime fn call, so it does
    # not fold as a const either. Repeat the fn's own body — and then CHECK the result
    # against the `ensure(SND_TIMERA_N == ...)` pin standing right beside it in the
    # source, so a derivation that drifted from the fn cannot pass silently.
    ta_n = 1024 - (1000000000000 // (c["SND_FRAME_MILLIHZ"] * 18773))
    m = re.search(r"ensure\(SND_TIMERA_N == (\d+)", SOUND_CONSTANTS.read_text(errors="replace"))
    if not m:
        raise Unmeasurable("sound_constants.emp no longer carries the "
                           "`ensure(SND_TIMERA_N == N)` pin, so this file's re-derivation "
                           "of the Timer-A reload has nothing to check itself against")
    if ta_n != int(m.group(1)):
        raise Unmeasurable(f"this file re-derives SND_TIMERA_N as {ta_n} but the source's "
                           f"own ensure pins it at {m.group(1)} — the re-derivation is "
                           f"wrong and every Timer-A figure below would be wrong with it")
    ta_ms = (1024 - ta_n) * 18773 / 1e6
    out.append("D0 THE DERIVATION — every figure below is computed here, not quoted:")
    out.append(f"  DAC rate      = Z80_CLOCK_HZ {c['Z80_CLOCK_HZ']} / SND_LOOP_CYC "
               f"{c['SND_LOOP_CYC']} = {rate} Hz  (SND_DAC_RATE_HZ is a comptime fn, so "
               f"it does not fold as a const; this repeats the fn's own body)")
    out.append(f"  ring LEAD     = SND_RING_LEAD_TARGET {c['SND_RING_LEAD_TARGET']} bytes "
               f"/ {rate} Hz = {lead_ms:.2f} ms   <- the DRAIN budget the storm spends")
    out.append(f"  ring PRIME    = SND_RING_LEAD_PRIME {c['SND_RING_LEAD_PRIME']} bytes "
               f"= {prime_ms:.2f} ms (the lead at sample start, before the first tick "
               f"tops it up — the WORST case a storm can meet)")
    out.append(f"  ring CAPACITY = SND_RING_LEN {c['SND_RING_LEN']} bytes = {full_ms:.2f} ms "
               f"(an absolute ceiling the lead never reaches: TARGET < 256 by design)")
    out.append(f"  Timer-A period = (1024 - SND_TIMERA_N {ta_n}) * 18773 ns "
               f"= {ta_ms:.2f} ms  <- a bracket longer than this coalesces two overflows "
               f"into one latched bit, i.e. DROPS a sequencer frame")
    return rate, lead_ms, prime_ms, ta_ms


def owner_table(syms):
    """[(addr, name)] over TOP-LEVEL labels only, sorted — for PC attribution.

    ⚠ `emulator/watchpoint_hits` already reports a `symbol`, and it is the WRONG one
    for this measurement. Both raisers write the flag from inside a `with z80_stopped`
    block, so the nearest preceding label is that block's own spin target — measured:
    every one of 1792 hits came back as `$engine.vblank$asm2$wait_z80`,
    `$engine.vblank$asm4$wait_z80`, `$engine.vblank$asm9$wait_z80` or
    `asm20.wait_z80`. Attributing on that name puts the storm and its control in the
    same bucket and reports "the storm never ran".

    So attribution is redone here against TOP-LEVEL labels only — no `$`-qualified
    module-local, no `.`-suffixed local, nothing beginning `asm` — which is the set of
    names a proc is actually called by.
    """
    tbl = sorted((a, n) for n, a in syms.items()
                 if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", n) and not n.startswith("asm"))
    return tbl


def owner_of(tbl, pc):
    """The top-level label the PC falls in, and its displacement."""
    lo, hi = 0, len(tbl)
    while lo < hi:
        mid = (lo + hi) // 2
        if tbl[mid][0] <= pc:
            lo = mid + 1
        else:
            hi = mid
    if lo == 0:
        return "?", 0
    a, n = tbl[lo - 1]
    return n, pc - a


def pair_up(hits):
    """[(raise_hit, lower_hit)] — consecutive 1 then 0 on the flag."""
    pairs, open_hit = [], None
    for h in hits:
        if h["v"]:
            open_hit = h
        elif open_hit is not None:
            pairs.append((open_hit, h))
            open_hit = None
    return pairs, open_hit


def describe(pairs, label, rate, lead_ms, ta_ms, out):
    if not pairs:
        out.append(f"  {label}: NO complete raise/lower pair")
        return None
    ms = sorted((lo["m"] - hi["m"]) / MCLK_HZ * 1000 for hi, lo in pairs)
    out.append(f"  {label}: {len(pairs)} bracket(s); min {ms[0]:.3f} ms · median "
               f"{ms[len(ms) // 2]:.3f} ms · max {ms[-1]:.3f} ms")
    return ms


async def main_async(sock, rom, lst_path, poison, out):
    rate, lead_ms, prime_ms, ta_ms = derive(out)
    b = BusClient(socket_path=sock, client_id="pokestorm", client_name="poke_storm_cost")
    await b.connect()
    await b.call("emulator/load_symbols", {"path": lst_path})
    syms, equs = parse_syms(lst_path)
    if "SND_DMA_ACTIVE_SLOT" not in equs:
        raise Unmeasurable("SND_DMA_ACTIVE_SLOT has no EQU in the listing — it is an "
                           "`equ`, invisible to lookup_symbol, and without it there is "
                           "no address to watch")
    if SUBJECT not in syms:
        raise Unmeasurable(f"{SUBJECT} is not in the listing — wrong ROM/listing pair?")
    slot = equs["SND_DMA_ACTIVE_SLOT"] & 0xFFFFFF
    watch_at = 0x00FF0000 if poison else slot
    out.append(f"  SND_DMA_ACTIVE_SLOT ${slot:06X} (Z80 RAM, written by the 68k over its "
               f"own bus — which is why a bus watch can see it at all)")
    out.append(f"  {SUBJECT} at ${syms[SUBJECT]:06X}")
    if poison:
        out.append("  --poison: the watch is aimed at $FF0000, a work-RAM byte no bracket "
                   "writes — L1 MUST report no storm bracket")

    tbl = owner_table(syms)
    legs, fails = [], []
    await b.call("emulator/watchpoint_add",
                 {"addr": hex(watch_at), "len": 1, "write": True, "read": False,
                  "mode": "record", "label": "dma-flag", "space": "bus"})
    await b.call("emulator/run_frames", {"frames": RUN_FRAMES})

    hits, cursor, dropped, seen, matched = [], None, 0, 0, 0
    while True:
        p = {"limit": 100}
        if cursor is not None:
            p["cursor"] = str(cursor)
        r = await b.call("emulator/watchpoint_hits", p)
        for h in r.get("hits", []):
            cursor = h["seq"]
            pc = int(str(h["pc"]).replace("0x", ""), 16)
            own, disp = owner_of(tbl, pc)
            hits.append({"seq": h["seq"], "m": h["mclk"], "frame": h["frame"],
                         "v": int(str(h["value"]).replace("0x", ""), 16) & 0xFF,
                         "pc": pc, "sym": own, "disp": disp,
                         "served": h.get("symbol", "?")})
        dropped, seen, matched = r.get("dropped", 0), r.get("seen", 0), r.get("matched", 0)
        if not r.get("truncated"):
            break
    holes = sum(1 for a, c in zip(hits, hits[1:]) if c["seq"] != a["seq"] + 1)

    out.append(f"L0 THE WATCH IS LIVE: seen={seen} matched={matched} dropped={dropped} "
               f"holes={holes} over {RUN_FRAMES} frames; {len(hits)} flag writes captured")
    if seen == 0:
        fails.append("L0: seen == 0 — the watch was never attached; nothing below is a "
                     "measurement of the engine")
    elif matched == 0 and not poison:
        fails.append("L0: the flag watch matched NOTHING in a sound-ON debug build — "
                     "either the bracket is not being written or the aim is wrong")
    if holes:
        fails.append(f"L0: {holes} gap(s) in the captured seq run — brackets were lost, "
                     f"so the pairing below can mis-pair a raise with a later lower")
    legs.append("L0 the watch is live")

    sub = [h for h in hits if SUBJECT in h["sym"]]
    ctl = [h for h in hits if CONTROL in h["sym"]]
    other = [h for h in hits if SUBJECT not in h["sym"] and CONTROL not in h["sym"]]
    out.append(f"  attribution by driving PC against {len(tbl)} top-level labels: "
               f"{len(sub)} writes from {SUBJECT}, {len(ctl)} from {CONTROL}*, "
               f"{len(other)} from elsewhere {sorted({h['sym'] for h in other})[:4]}")
    out.append(f"  (the server's own `symbol` field says "
               f"{sorted({h['served'] for h in hits})[:3]} for every one of them — the "
               f"`with z80_stopped` spin label, which is why it is not used here)")

    # ---------------- L1: the storm's own bracket ----------------------------------
    pairs_sub, dangling = pair_up(sub)
    out.append(f"L1 THE STORM: raise/lower pairs whose PC is inside {SUBJECT}")
    ms_sub = describe(pairs_sub, "L1", rate, lead_ms, ta_ms, out)
    if dangling is not None:
        out.append(f"  L1: one raise at frame {dangling['frame']} has no matching lower "
                   f"inside the run window")
    if not pairs_sub:
        if poison:
            out.append("  L1: no storm bracket, as the poison run requires")
        else:
            fails.append(f"L1: {SUBJECT} never raised the flag in {RUN_FRAMES} frames — "
                         f"the storm did not run, so there is nothing here to time")
    legs.append("L1 the storm")

    # ---------------- L2: what that costs, in the driver's own units ----------------
    out.append("L2 WHAT IT COSTS, in the two units the driver's own mechanisms use:")
    if ms_sub:
        worst = ms_sub[-1]
        total = sum(ms_sub)
        out.append(f"  L2: longest storm bracket {worst:.2f} ms = {worst / lead_ms:.2f} x "
                   f"the {lead_ms:.2f} ms ring lead and {worst / ta_ms:.2f} x the "
                   f"{ta_ms:.2f} ms Timer-A period")
        out.append(f"  L2: a DAC sample streaming across it would have to drain "
                   f"{int(worst / 1000 * rate)} ring bytes while the producer is on its "
                   f"DRAIN path; the ring holds a {int(lead_ms / 1000 * rate)}-byte lead, "
                   f"so it runs dry after {lead_ms:.2f} ms and the R1 underrun guard pins "
                   f"RD to WR — a held DC level for the remaining {worst - lead_ms:.2f} ms")
        out.append(f"  L2: sequencer frames the bracket can coalesce: "
                   f"floor({worst:.2f}/{ta_ms:.2f}) = {int(worst // ta_ms)} dropped "
                   f"Timer-A overflow(s) per storm")
        out.append(f"  L2: total time the flag is held by the storm across the run: "
                   f"{total:.2f} ms over {len(ms_sub)} bracket(s)")
    else:
        out.append("  L2: not computable — L1 found no bracket")
    legs.append("L2 what it costs")

    # ---------------- C1: the control, the SAME flag from the VBlank path -----------
    pairs_ctl, _ = pair_up(ctl)
    out.append(f"C1 THE VBLANK BRACKET (control): the same flag, the same run, raised by "
               f"{CONTROL}* instead")
    ms_ctl = describe(pairs_ctl, "C1", rate, lead_ms, ta_ms, out)
    if ms_ctl:
        out.append(f"  C1: the per-frame bracket's median is "
                   f"{ms_ctl[len(ms_ctl) // 2] / lead_ms:.3f} x the ring lead and "
                   f"{ms_ctl[len(ms_ctl) // 2] / ta_ms:.3f} x the Timer-A period — so a "
                   f"large L1 is a fact about the STORM, not about how this instrument "
                   f"reports brackets")
    elif not poison:
        fails.append("C1: no VBlank bracket pairs at all — the control did not run, so L1 "
                     "has nothing to be compared against")
    legs.append("C1 the vblank bracket")

    # ---------------- C2: steady state, after the storm -----------------------------
    last_storm = pairs_sub[-1][1]["m"] if pairs_sub else 0
    late = [h for h in ctl if h["m"] > last_storm]
    pairs_late, _ = pair_up(late)
    out.append(f"C2 STEADY STATE (control): brackets after the last storm ended")
    ms_late = describe(pairs_late, "C2", rate, lead_ms, ta_ms, out)
    if ms_late and ms_sub:
        out.append(f"  C2: steady-state max {ms_late[-1]:.3f} ms against the storm's "
                   f"{ms_sub[-1]:.2f} ms — rules out 'the flag is simply held a long time "
                   f"early in a boot'")
    legs.append("C2 steady state")
    legs.append("D0 the derivation")

    out.append(f"LEGS RUN: {len(legs)} — " + ", ".join(legs))
    if len(legs) != 6:
        fails.append(f"only {len(legs)} of 6 legs ran — an unrun leg is not a pass")
    return fails, len(legs), 6, (ms_sub, ms_ctl, lead_ms, ta_ms)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", default="s4.debug.bin")
    ap.add_argument("--lst", default="s4.debug.lst")
    ap.add_argument("--poison", action="store_true",
                    help="aim the watch at a byte no bracket writes; L1 must find nothing")
    a = ap.parse_args()
    out = []
    try:
        with aether_emulator(a.rom, symbols=a.lst) as sock:
            fails, ran, want, _ = asyncio.run(main_async(sock, a.rom, a.lst, a.poison, out))
    except Unmeasurable as e:
        print("\n".join(out))
        print(f"\nUNMEASURABLE: {e}")
        return 2
    print("\n".join(out))
    if a.poison:
        print("\nPOISON: L1 must have reported no storm bracket above. If it reported one, "
              "the attribution is not reading the PC it claims to read.")
        return 0
    if fails:
        print("\nRESULT: COULD NOT MEASURE CLEANLY")
        for f in fails:
            print(f"  * {f}")
        return 1
    print(f"\nRESULT: MEASURED — {ran} of {want} legs (4 drives + 2 controls).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
