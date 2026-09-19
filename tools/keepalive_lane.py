#!/usr/bin/env python3
"""keepalive_lane — run the bus instruments nothing else runs, and report which ones
CANNOT run as a different thing from which ones FAIL.

THE DEFECT, IN ONE SENTENCE: a channel that cannot report is indistinguishable from a
channel reporting nothing wrong.

`tools/parallax_hscroll_probe.py` crashed on startup from 2026-08-26 until it was found
on 2026-09-18, and the crash was hiding 35 findings. `tools/parallax_hscroll_identity.py`
had not run since 2026-08-29. Both are bus instruments that nothing executes, so nothing
noticed. This lane executes them.

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
    exit status == the declared baseline .............. PASSED
    anything else ..................................... FAILED

The argparse rung is about THIS FILE being wrong, not the tool: if the manifest's declared
invocation no longer matches the tool's arguments, the lane is not measuring that tool any
more, and that is a lane that cannot run rather than a tool that failed.

  ⚠ A tool declared `expect = 1` that exits 0 is FAILED, deliberately. A known-red going
    green is a change in what the instrument reports and the lane must say so. Otherwise
    the cheapest way to make this lane green is to weaken an instrument until it stops
    complaining, which would make this lane a machine for hiding exactly what it exists to
    surface.

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


def classify(rc, output, expect, timed_out):
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
    if rc == expect:
        return PASSED, f"exit {rc} (declared baseline)"
    return FAILED, f"exit {rc}, declared baseline was {expect}"


def load_manifest(path):
    with open(path, "rb") as fh:
        return tomllib.load(fh)


def account(manifest, pop):
    """Reconcile the manifest against the tree-derived population."""
    wired = manifest.get("wired", {})
    not_wired = manifest.get("not_wired", {})
    declared = set(wired) | set(not_wired)
    dupes = sorted(set(wired) & set(not_wired))
    undeclared = sorted(set(pop) - declared)
    missing = sorted(declared - set(pop))
    return declared, undeclared, missing, dupes


def run_one(name, spec, rom, lst, repo, verbose):
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
    verdict, why = classify(rc, out, int(spec.get("expect", 0)), timed_out)
    return {
        "name": name, "verdict": verdict, "why": why, "wall": wall,
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
    print("POPULATION (derived from the tree, every run)")
    print(f"  bus instruments in tools/          {len(pop)}")
    print(f"  of those, nothing executes         {len(dead)}  (advisory; see keepalive_population.py)")
    print(f"  declared in the manifest           {len(declared)}  "
          f"({len(wired)} wired, {len(not_wired)} not wired)")
    dead_unwired = sorted(set(dead) - set(wired))
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
    if not drift:
        print("  accounting: every bus instrument in the tree has a disposition.")

    if args.list:
        return 2 if drift else 0

    for path, what in ((args.rom, "ROM"), (args.lst, "listing")):
        if not os.path.isfile(path):
            print(f"\nCOULD NOT RUN: no {what} at {path}")
            return 2

    todo = sorted(wired) if not args.only else [t for t in sorted(wired) if
                                                t in args.only or t[:-3] in args.only]
    print(f"\nRUNNING {len(todo)} wired instrument(s), serially "
          f"(each boots its own headless emulator)\n")

    if args.logdir:
        os.makedirs(args.logdir, exist_ok=True)

    results = []
    for i, name in enumerate(todo, 1):
        spec = wired[name]
        print(f"[{i:2d}/{len(todo)}] {name:38s} ", end="", flush=True)
        res = run_one(name, spec, args.rom, args.lst, REPO, args.verbose)
        results.append(res)
        print(f"{res['verdict']:14s} {res['wall']:6.1f}s  {res['why']}")
        if args.logdir:
            with open(os.path.join(args.logdir, name + ".log"), "w") as fh:
                fh.write(f"$ {res['cmd']}\nexit {res['rc']}  {res['verdict']}: {res['why']}\n\n")
                fh.write(res["output"])

    counts = {PASSED: 0, FAILED: 0, CNR: 0}
    for r in results:
        counts[r["verdict"]] += 1

    print()
    print("=" * 78)
    print(f"RESULTS  {len(results)} wired instrument(s) run")
    print(f"  PASSED          {counts[PASSED]}")
    print(f"  FAILED          {counts[FAILED]}")
    print(f"  COULD NOT RUN   {counts[CNR]}")
    for label in (CNR, FAILED):
        named = [r for r in results if r["verdict"] == label]
        if named:
            print(f"\n  {label}:")
            for r in named:
                note = wired[r["name"]].get("note", "")
                print(f"    {r['name']:38s} {r['why']}")
                if note:
                    print(f"      declared: {note}")
    print("=" * 78)
    total = sum(r["wall"] for r in results)
    print(f"wall {total/60:.1f} min over {len(results)} instrument(s); "
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
