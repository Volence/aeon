#!/usr/bin/env python3
"""keepalive_lane — run the bus instruments nothing else runs, and report which ones
CANNOT run as a different thing from which ones FAIL.

THE DEFECT, IN ONE SENTENCE: a channel that cannot report is indistinguishable from a
channel reporting nothing wrong.

`tools/parallax_hscroll_probe.py` crashed on startup from 2026-08-26 until it was found
on 2026-09-18, and the crash was hiding 35 findings. `tools/parallax_hscroll_identity.py`
had not run since 2026-08-29. Both are bus instruments that nothing executes, so nothing
noticed. This lane executes them.

⚠ ONE INVOCATION PER TOOL, WHICH IS NARROWER THAN "RUNS THEM" AND IS MEASURED, NOT
ESTIMATED. Every wired tool is run on exactly the argv `keepalive_manifest.toml` declares
for it, so what this lane keeps alive is each tool's ability to reach A verdict on ONE
path -- in practice its defaults, plus a required label/out-dir and, for two rows, one
chosen subject. Measured 2026-09-19 by `tools/keepalive_surface.py` over the 35 wired
tools: 28 carry surface this invocation does not set, 38 options gate 241 lines whose
default leaves them unexecuted, one selector reaches 1 of 5 subjects, and
`transition_window_probe` is pointed at 1 of 85 possible subject tools. A 20-arm sample
of that unreached surface ran clean the same night (0 dead), so the gap is a LIMIT OF
REACH rather than a list of known-broken arms -- but it is a real limit and it is stated
here rather than left for the next reader to discover.

=============================================================================
WHY THE CHEAP VERSION DOES NOT WORK, MEASURED BY THE PARCEL BEFORE THIS ONE
=============================================================================
A `--help` startup smoke over all 85 instruments costs 7.9 s and catches NEITHER real
defect: `parallax_hscroll_identity`'s `TypeError` fires inside `main()` at the first
`build()`, AFTER `parse_args`, so `--help` exits 0 on a tool that cannot do anything; and
`parallax_hscroll_probe`'s `NameError` was on the reporting path, deep inside a run. The
smoke also had a 9% false-positive rate (8 of 85 exit non-zero on `--help`, mostly tools
taking positionals). **9% false positives against 0% true positives is worse than
nothing**, and a noisy lane gets ignored, which is this defect again with extra steps.

There is no observation short of EXECUTION that separates "this channel reports nothing
wrong" from "this channel cannot report". So this lane runs the tools.

=============================================================================
THE THREE OUTCOMES, AND WHY COULD-NOT-RUN IS NOT A KIND OF FAILURE
=============================================================================
  PASSED         the tool ran to completion and exited with its DECLARED baseline status.
  FAILED         the tool ran to completion and exited with some OTHER status. It formed
                 a verdict and the verdict is not the declared one.
  COULD NOT RUN  the tool did not reach a verdict at all.

Collapsing the third into the second is the whole defect wearing a lane's clothes: a dead
instrument rendered as one red row among other red rows is a dead instrument nobody digs
out. Collapsing it into the first recreates the original defect INSIDE the fix. So it is
its own outcome, its own count, and its own exit status, and it OUTRANKS failure in the
worst-wins fold at the bottom — the same contract `tools/nightly_effects_gates.sh` draws,
for the same reason.

HOW THE THREE ARE TOLD APART. The discriminator is DERIVED from the two real defects
rather than invented: both were uncaught Python exceptions, one before the run and one
inside it, and an uncaught exception prints `Traceback (most recent call last):` and exits
1 — the same exit status a tool uses to report a measured negative. Exit status ALONE
therefore cannot tell them apart, which is exactly why a naive exit-code lane would have
rendered both of today's dead instruments as ordinary failures.

    timeout ........................................... COULD NOT RUN
    "Traceback (most recent call last):" in output .... COULD NOT RUN
    exit 2 with an argparse usage error ............... COULD NOT RUN  (see below)
    non-zero AND the instrument's own refusal word .... COULD NOT RUN  (see REFUSAL_MARKERS)
    exit status == the declared baseline .............. PASSED
    anything else ..................................... FAILED

The fourth rung was added after the FIRST REAL RUN, which is the only reason it exists:
seven of the ten rows that came back FAILED were instruments saying in their own words
that they could not measure the ROM they were handed ("COULD NOT RUN - ROM crc32 ... is
not the measured 9ce1c2ff", "UNMEASURABLE: Sound_DebugMirror is not a label", "BLOCKED:
the borrowed symbol addresses do not describe this ROM"). Reading those as failures both
loses the distinction this lane exists for AND blames the engine for a stale instrument.

The argparse rung is about THIS FILE being wrong, not the tool: if the manifest's declared
invocation no longer matches the tool's arguments, the lane is not measuring that tool any
more, and that is a lane that cannot run rather than a tool that failed.

  ⚠ A tool declared `expect = 1` that exits 0 is FAILED, deliberately. A known-red going
    green is a change in what the instrument reports and the lane must say so. Otherwise
    the cheapest way to make this lane green is to weaken an instrument until it stops
    complaining, which would make this lane a machine for hiding exactly what it exists to
    surface.

=============================================================================
A BASELINE DESCRIBES AN INVOCATION, NOT A TOOL
=============================================================================
`expect` used to be keyed to the TOOL. It is keyed to the ROW, and a ROW IS AN INVOCATION:
a manifest key is `tool.py` or `tool.py#arm-label`, and the part before the `#` is the only
part that names a file. That is the whole schema change, and it exists because of a measured
trap.

THE TRAP, MEASURED 2026-09-19 by `KEEPALIVE-DEFAULT-ARGS`. Several wired rows declare a
NON-ZERO baseline (four that day; three since `parallax_hscroll_identity` went to 0) -- their normal, understood state is a red, and baselining it is what makes
a known-red GOING GREEN report as FAILED. But `loop_step_over_witness --phase-sweep` enters
its arm, hits the same tool-wide SETUP red the default arm hits, and exits 1; graded against
the TOOL's `expect = 1` it reports PASSED. **A check that can see perfectly and whose output
carries no information.** An extra arm on a tool with a non-zero baseline inherits a baseline
that was measured on a DIFFERENT arm, and is then a green row that cannot fail.

THE RULE, AND IT IS ONE SENTENCE: a NON-ZERO `expect` must be accompanied by `baseline_args`,
spelled out, and EQUAL to that row's own `args`. The redundancy IS the check. A row whose
declared baseline does not describe its own invocation is COULD NOT RUN -- never PASSED,
never FAILED -- because a baseline measured somewhere else cannot grade this run. Three
things it catches, and one it does not, stated so nobody expects more of it:

  * adding an arm to an existing non-zero row's `args` and leaving `expect` alone: CAUGHT,
    `baseline_args` no longer matches `args`.
  * copying a non-zero row to a new `tool.py#arm` key and changing only `args`: CAUGHT, same
    way.
  * writing a new arm and thinking about nothing: CAUGHT by the DEFAULT. `expect` defaults to
    0, so a new arm on a known-red tool reports FAILED, loudly, on its first run.
  * copying the row AND editing `baseline_args` to match: NOT caught, and cannot be. That is
    an author asserting "I measured THIS argv and it exits N", which is a claim, not an
    inheritance. No mechanism short of running it can tell a true claim from a false one.

⚠ THE ZERO BASELINE IS DELIBERATELY EXEMPT. `expect = 0` is not a measurement that can
travel -- it is "this tool is supposed to work" -- so requiring `baseline_args` on 31 rows
would buy nothing and rot on the first `args` edit. The hazard is a RED that travels, and
that is what the rule is keyed to. A row that carries `baseline_args` anyway is still held to
the equality, so a stale one cannot sit there looking like evidence.

=============================================================================
THE POPULATION REFUSES TO SHRINK SILENTLY
=============================================================================
`keepalive_population.py` derives the 85 bus instruments FROM THE TREE on every run. This
lane refuses to grade unless the manifest carries a disposition for every one of them:

    UNDECLARED   a bus instrument exists in the tree and the manifest does not name it.
                 COULD NOT RUN. Somebody added an instrument and the lane silently did
                 not cover it -- a keepalive lane quietly covering 84 of 85 is precisely
                 the artifact it was built to prevent.
    MISSING      the manifest names a tool that is no longer in the tree. COULD NOT RUN.
                 Deleting the instrument is a legitimate act; deleting the manifest line
                 is the other half of it, and until both happen the lane says so.

Neither is a judgement about the instrument. Both say the lane's stated coverage and the
tree have diverged, and the lane will not pretend otherwise by rounding to green.
"""
import argparse
import datetime
import os
import subprocess
import sys
import tempfile
import time
import tomllib

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(TOOLS_DIR)
sys.path.insert(0, TOOLS_DIR)
import keepalive_population as kpop  # noqa: E402

DEFAULT_MANIFEST = os.path.join(TOOLS_DIR, "keepalive_manifest.toml")

PASSED = "PASSED"
FAILED = "FAILED"
CNR = "COULD NOT RUN"

TRACEBACK_MARK = "Traceback (most recent call last):"

# THE INSTRUMENTS ALREADY DRAW THIS DISTINCTION THEMSELVES, and the first real run of this
# lane is what showed it. Seven of the ten rows that came back FAILED were not failures at
# all -- they were instruments saying, in their own words, that they could not measure the
# ROM they were handed:
#
#   blank_priority_probe        "COULD NOT RUN - ROM crc32 62238a15 is not the measured 9ce1c2ff"
#   lens_residue_object_witness "COULD NOT RUN (setup): ... Refusing to report on a different ROM."
#   sec5_band_witness           "REFUSED: ... this instrument measures exactly ONE band; the document has 3"
#   deform_own_cost_probe       "REFUSED: band record is 32 bytes, expected 20"
#   song_load_mid_drum_witness  "UNMEASURABLE: Sound_DebugMirror is not a label in ..."
#   tick_variance_probe         "BLOCKED: the borrowed symbol addresses do not describe this ROM"
#   dma_straddle_reading        "THIS RUN SAYS NOTHING - REFUSING TO REPORT IT AS A PASS"
#
# Flattening those into "exit 1, expected 0" throws away the very distinction this lane
# exists to preserve, and it points the finger at the engine for what is a stale
# instrument. So the lane honours an instrument's own verdict word when it has one.
#
# THE VOCABULARY IS THE TREE'S, NOT MINE. Measured over tools/*.py on 2026-09-18:
# "UNMEASURABLE" appears in 82 files, "REFUSED" in 58, "VACUOUS" in 31, "COULD NOT RUN" in
# 28. These are house conventions with a long history here, not a pattern fitted to one
# bad night.
#
# TWO GUARDS KEEP THIS FROM SWALLOWING REAL FAILURES:
#   * the marker must begin a LINE (after an optional "toolname: " prefix), so a sentence
#     mentioning a refusal in passing cannot trigger it; and
#   * a tool that exited 0 is never reclassified -- it formed a verdict, and its prose is
#     not the lane's business.
# A tool whose legitimate verdict IS a refusal (tools/curve_probe.py refuses every
# canonical image by design) sets `refusal_is_expected = true` in the manifest and opts out.
REFUSAL_MARKERS = (
    "COULD NOT RUN",
    "REFUSED",
    "REFUSING TO REPORT",
    "UNMEASURABLE",
    "BLOCKED:",
    "THIS RUN SAYS NOTHING",
)


def _self_declared_refusal(output):
    """Return the instrument's own refusal line, or None. Line-leading markers only."""
    for line in output.splitlines():
        text = line.strip()
        # Strip a "toolname: " prefix -- several instruments lead their verdict with it.
        head, sep, rest = text.partition(": ")
        if sep and " " not in head and head.endswith(("probe", "witness", "gate", "ab",
                                                      "poison", "capture", "dump",
                                                      "reading", "exercise", "audition")):
            text = rest.strip()
        for mark in REFUSAL_MARKERS:
            if text.startswith(mark):
                return text[:160]
    return None


def classify(rc, output, expect, timed_out, refusal_is_expected=False):
    """The whole claim of this lane lives in this function. See the module docstring."""
    if timed_out:
        return CNR, "timed out"
    if TRACEBACK_MARK in output:
        # Derived from the two real defects: an uncaught exception exits 1, which is also
        # how a tool reports a measured negative. The traceback is what separates them.
        last = [ln for ln in output.strip().splitlines() if ln.strip()]
        why = last[-1].strip()[:160] if last else "uncaught exception"
        return CNR, f"uncaught exception: {why}"
    if rc == 2 and ("usage:" in output or "error: the following arguments are required" in output
                    or "error: unrecognized arguments" in output):
        return CNR, "the manifest's declared invocation no longer matches this tool's arguments"
    if rc != 0 and not refusal_is_expected:
        said = _self_declared_refusal(output)
        if said:
            return CNR, f"the instrument itself refused: {said}"
    if rc == expect:
        return PASSED, f"exit {rc} (declared baseline)"
    return FAILED, f"exit {rc}, declared baseline was {expect}"


def load_manifest(path):
    with open(path, "rb") as fh:
        return tomllib.load(fh)


# A manifest row is keyed by an INVOCATION, not by a tool: `tool.py` names the tool's one
# declared invocation, `tool.py#arm-label` names another one of the same tool's. Only the
# part before the separator is a filename. See the module docstring.
ARM_SEP = "#"


def tool_of(row):
    """The tools/ filename a manifest row names."""
    return row.split(ARM_SEP, 1)[0]


def arm_of(row):
    """The arm label, or "" for a tool's default row."""
    head, sep, label = row.partition(ARM_SEP)
    return label if sep else ""


def baseline_drift(row, spec):
    """None if this row's declared baseline describes THIS row's invocation, else why not.

    THE WHOLE POINT IS THE REDUNDANCY. `baseline_args` restates the argv the baseline was
    measured against, so a baseline that was moved onto a different invocation stops
    matching and the row becomes ungradeable instead of silently grading. See the module
    docstring for the three cases this catches and the one it cannot.
    """
    expect = int(spec.get("expect", 0))
    args = [str(a) for a in spec.get("args", [])]
    declared = spec.get("baseline_args")
    if declared is None:
        if expect == 0:
            return None
        return (f"declares `expect = {expect}` -- a NON-ZERO baseline, i.e. a measured red -- "
                f"and no `baseline_args`. A red baseline is a measurement of ONE invocation "
                f"and this row does not say which. Add `baseline_args` spelling out the argv "
                f"the baseline was measured on; it must equal this row's `args`")
    declared = [str(a) for a in declared]
    if declared != args:
        return (f"`baseline_args` {declared} is not this row's `args` {args}, so the declared "
                f"baseline (`expect = {expect}`) was measured on a DIFFERENT invocation than "
                f"the one this row runs. Re-measure this arm and write its own baseline; do "
                f"not carry another arm's over")
    return None


def account(manifest, pop):
    """Reconcile the manifest against the tree-derived population.

    Rows are per-INVOCATION and the population is per-TOOL, so both sides of every set
    operation below are folded through `tool_of` first. A tool with three arms is one
    declaration, not three, and a tool declared `not_wired` while an arm of it is wired is
    still AMBIGUOUS.
    """
    wired = manifest.get("wired", {})
    not_wired = manifest.get("not_wired", {})
    wired_tools = {tool_of(r) for r in wired}
    nw_tools = {tool_of(r) for r in not_wired}
    declared = wired_tools | nw_tools
    dupes = sorted(wired_tools & nw_tools)
    undeclared = sorted(set(pop) - declared)
    missing = sorted(declared - set(pop))
    return declared, undeclared, missing, dupes


def twin_rows(wired):
    """Rows of ONE tool whose `args` are identical -- two names for one invocation.

    Not a style complaint. Two rows that run the same argv carry two baselines for one
    measurement, so one of them is unfalsifiable bookkeeping and nothing says which. It is
    also the exact residue of copying a row to make an arm and forgetting to change the
    argv, which is the copy this lane's baseline rule is aimed at.
    """
    seen = {}
    out = []
    for row in sorted(wired):
        key = (tool_of(row), tuple(str(a) for a in wired[row].get("args", [])))
        if key in seen:
            out.append((seen[key], row))
        else:
            seen[key] = row
    return out


def run_one(row, spec, rom, lst, repo, verbose):
    name = tool_of(row)
    # THE BASELINE IS CHECKED BEFORE THE TOOL IS RUN, and a drifting one makes the row
    # UNGRADEABLE rather than merely noisy: there is no exit status this invocation could
    # return that the declared baseline is entitled to grade, so PASSED and FAILED are both
    # wrong answers and COULD NOT RUN is the honest one. The tool is not spawned -- a run
    # nothing can grade is a headless boot spent for no verdict.
    drift = baseline_drift(row, spec)
    if drift:
        return {"name": row, "verdict": CNR, "why": f"the baseline does not describe this "
                f"invocation: {drift}", "wall": 0.0, "cmd": "(not run)", "output": "", "rc": None}
    args = []
    outdir = None
    raw = list(spec.get("args", []))
    if any("{outdir}" in a for a in raw):
        outdir = tempfile.mkdtemp(prefix="keepalive-")
    for a in raw:
        args.append(
            a.replace("{rom}", rom).replace("{lst}", lst)
             .replace("{repo}", repo).replace("{outdir}", outdir or "")
        )
    cmd = [sys.executable, os.path.join(repo, "tools", name)] + args
    timeout = int(spec.get("timeout", 600))
    t0 = time.time()
    timed_out = False
    try:
        proc = subprocess.run(
            cmd, cwd=repo, capture_output=True, text=True, timeout=timeout,
        )
        rc, out = proc.returncode, proc.stdout + proc.stderr
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        rc = -1
        out = (exc.stdout or "") + (exc.stderr or "")
        if isinstance(out, bytes):
            out = out.decode("utf-8", "replace")
    wall = time.time() - t0
    verdict, why = classify(rc, out, int(spec.get("expect", 0)), timed_out,
                            refusal_is_expected=bool(spec.get("refusal_is_expected", False)))
    return {
        "name": row, "verdict": verdict, "why": why, "wall": wall,
        "cmd": " ".join(cmd[1:]), "output": out, "rc": rc,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--rom", default=os.path.join(REPO, "s4.debug.bin"))
    ap.add_argument("--lst", default=os.path.join(REPO, "s4.debug.lst"))
    ap.add_argument("--manifest", default=DEFAULT_MANIFEST)
    ap.add_argument("--only", action="append", default=None,
                    help="run just these wired tools (repeatable); accounting still runs")
    ap.add_argument("--list", action="store_true", help="print the accounting and exit")
    ap.add_argument("--logdir", default=None, help="write each tool's full output here")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args(argv)

    started = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    print(f"keepalive lane starting {started}")
    print(f"  uptime:{subprocess.run(['uptime'], capture_output=True, text=True).stdout.strip()}")

    manifest = load_manifest(args.manifest)
    pop, dead = kpop.unreachable(REPO)
    wired = manifest.get("wired", {})
    not_wired = manifest.get("not_wired", {})
    declared, undeclared, missing, dupes = account(manifest, pop)

    print()
    wired_tools = {tool_of(r) for r in wired}
    arms = sorted(r for r in wired if arm_of(r))
    print("POPULATION (derived from the tree, every run)")
    print(f"  bus instruments in tools/          {len(pop)}")
    print(f"  of those, nothing executes         {len(dead)}  (advisory; see keepalive_population.py)")
    print(f"  declared in the manifest           {len(declared)}  "
          f"({len(wired_tools)} wired, {len(not_wired)} not wired)")
    print(f"  wired INVOCATIONS (rows)           {len(wired)}  "
          f"({len(arms)} extra arm(s) past each tool's default row)")
    dead_unwired = sorted(set(dead) - wired_tools)
    print(f"  unexecuted AND not wired here      {len(dead_unwired)}  "
          f"(the honest remaining gap, all named in [not_wired])")

    drift = 0
    for nm in undeclared:
        print(f"  UNDECLARED  {nm}  -- in the tree, absent from the manifest")
        drift += 1
    for nm in missing:
        print(f"  MISSING     {nm}  -- in the manifest, absent from the tree")
        drift += 1
    for nm in dupes:
        print(f"  AMBIGUOUS   {nm}  -- declared BOTH wired and not_wired")
        drift += 1
    for first, second in twin_rows(wired):
        print(f"  AMBIGUOUS   {second}  -- same tool and same `args` as {first}: two "
              f"baselines for ONE invocation, and nothing says which is the measurement")
        drift += 1
    # THE BASELINE ACCOUNTING, printed here so `--list` reaches it without a 5-minute run.
    # `run_one` refuses the same rows independently -- this is the cheap early warning, not
    # the enforcement, because a lane invoked with `--only` must not be able to skip it.
    for row in sorted(wired):
        why = baseline_drift(row, wired[row])
        if why:
            print(f"  BASELINE    {row}  -- {why}")
            drift += 1
    if not drift:
        print("  accounting: every bus instrument in the tree has a disposition.")

    if args.list:
        return 2 if drift else 0

    for path, what in ((args.rom, "ROM"), (args.lst, "listing")):
        if not os.path.isfile(path):
            print(f"\nCOULD NOT RUN: no {what} at {path}")
            return 2

    # `--only` names a TOOL or a ROW: `loop_step_over_witness`, `loop_step_over_witness.py`,
    # or `loop_step_over_witness.py#phase-sweep`. Naming the tool runs every arm of it,
    # because "run that instrument" has to mean all of it once a tool has more than one row.
    def _picked(row):
        tool = tool_of(row)
        return row in args.only or tool in args.only or tool[:-3] in args.only
    todo = sorted(wired) if not args.only else [r for r in sorted(wired) if _picked(r)]
    print(f"\nRUNNING {len(todo)} wired invocation(s) over "
          f"{len({tool_of(r) for r in todo})} instrument(s), serially "
          f"(each boots its own headless emulator)\n")

    if args.logdir:
        os.makedirs(args.logdir, exist_ok=True)

    results = []
    for i, row in enumerate(todo, 1):
        spec = wired[row]
        print(f"[{i:2d}/{len(todo)}] {row:46s} ", end="", flush=True)
        res = run_one(row, spec, args.rom, args.lst, REPO, args.verbose)
        results.append(res)
        print(f"{res['verdict']:14s} {res['wall']:6.1f}s  {res['why']}")
        if args.logdir:
            with open(os.path.join(args.logdir, row.replace(ARM_SEP, "--") + ".log"), "w") as fh:
                fh.write(f"$ {res['cmd']}\nexit {res['rc']}  {res['verdict']}: {res['why']}\n\n")
                fh.write(res["output"])

    counts = {PASSED: 0, FAILED: 0, CNR: 0}
    for r in results:
        counts[r["verdict"]] += 1

    print()
    print("=" * 78)
    print(f"RESULTS  {len(results)} wired invocation(s) run over "
          f"{len({tool_of(r['name']) for r in results})} instrument(s)")
    print(f"  PASSED          {counts[PASSED]}")
    print(f"  FAILED          {counts[FAILED]}")
    print(f"  COULD NOT RUN   {counts[CNR]}")
    for label in (CNR, FAILED):
        named = [r for r in results if r["verdict"] == label]
        if named:
            print(f"\n  {label}:")
            for r in named:
                note = wired[r["name"]].get("note", "")
                print(f"    {r['name']:46s} {r['why']}")
                if note:
                    print(f"      declared: {note}")
    print("=" * 78)
    total = sum(r["wall"] for r in results)
    print(f"wall {total/60:.1f} min over {len(results)} invocation(s); "
          f"uptime:{subprocess.run(['uptime'], capture_output=True, text=True).stdout.strip()}")
    print(f"finished={len(results)} of {len(todo)}")

    # worst-wins, same contract as tools/nightly_effects_gates.sh: a lane that COULD NOT
    # RUN outranks a lane that failed, because a channel that cannot report is the thing
    # this lane exists to catch.
    if drift or counts[CNR]:
        return 2
    return 1 if counts[FAILED] else 0


if __name__ == "__main__":
    sys.exit(main())
