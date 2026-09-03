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
  4c. vscroll-split landing and precedence — `vsplit_landing_gate`, P3 Task 11. The gate on
     the OTHER two-writer question: Plane B's vertical scroll word is written in VBlank and
     again mid-frame by a raster fire, and the scene model can now author that collision. Two
     fixtures differing only in their split line must produce one contiguous band of disagreement
     between the two lines, starting at the landing row and closing again below the second —
     which is the N+1 landing model and the precedence ruling in one measurement.
  4b. palette variant derive vs its comptime MIRROR — `palette_variant_gate`, the B2 gate.
     `palette_dsl.emp` models the derive and pins that model with `ensure()` vectors, and
     `palette.emp` used to tell the reader the asm was therefore "build-time checked". It was
     not: sigil cannot execute 68000, so the mirror only ever proved itself. This gate parses
     those same vectors out of the .emp and drives them through the real
     `Palette_DeriveVariant` on an emulator, plus a 48-entry sweep and the `v_lines` coverage
     the mirror never modelled. A one-shift change in that proc builds green and fails here.
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
  8. section-streamer promise — `tile_cache_fill_gate`, the third non-effects member (see the
     registry note beside it). The four `Section_*_{Col,Row}_Written` trackers say a cell will
     not be revisited for tens of seconds of travel, so a cell recorded but drawn from cache
     the fill had not populated is a PERMANENT hole on screen. This asserts plane A against the
     tile cache over exactly the recorded window, and asserts that the fill's pending partial
     is never inside it.

Gates 6 and 7 boot no emulator, but they need a listing, so they cannot go in build.sh either
(build.sh runs pytest BEFORE the build — a listing read there is the previous build's).

HOW IT RUNS — SEGMENTED, since 2026-08-19.

A plain invocation does NOT run all 22 gates in one process any more. It partitions them into
segments, re-invokes ITSELF once per segment with `--only`, and aggregates. The reason is a
measured failure, not a preference: the oracle stop-race intermittently wedges ONE
emulator-backed gate forever, and because this lane buffers every result and prints at the
end, one wedge used to destroy all 22 results and print nothing at all. It burned three
sessions on 2026-08-19 (two full-lane timeouts recovered only by hand-segmenting with
`--only`, plus orphaned oracle_gui processes left behind), and DEFERRED_WORK booked the
hand-segmenting as the shape the lane should just have.

So: per segment, a timeout and ONE retry; before the retry, the oracle_gui processes belonging
to THIS invocation's ROM are reaped (by argv token — never a bare pkill, see `oracle_pids_for`).
A segment that wedges twice becomes its OWN named failure row, "WEDGED after retry". The lane
is loud on unmeasurable and the other 21 gates still report.

WHICH EMULATOR, AFTER THE 2026-08-26 CUTOVER. The owner ruled the Rust core the default
instrument (empyrean 3c21183) and most of this lane is now on it, through the one shared seam
`tools/aether_instance.py` — which spawns it, waits for the socket to ACCEPT, ASSERTS the
server really is the Rust core, and reaps it. Seven of the twelve emulator segments spawn
oracle-aether (raster_off, raster_source, palette_variant, snapshot_poison converted here;
vsplit_landing, warp_mailbox, boot_override always did). Those seven CANNOT hit the stop race:
oracle-aether boots PAUSED and `run_frames`/`run_to` are synchronous and bounded, so there is
no resume-then-wait-for-an-event to lose. They also reap their OWN processes, which is why
`oracle_pids_for` — an oracle_gui-only search, deliberately — cannot see them and does not
need to.

Five gates STAY on the legacy oracle_gui, for reasons that are not about this lane:
  * scene:* (4 segments, 8 gates) drive `ab_runner.py`, which lives in `oracle-old`. Porting
    it is oracle's call, not ours. At ~38 s each they are now 80% of the lane's wall clock.
  * cost_model drives `raster_cost_probe.py`, one of the three PROFILER probes held under
    docs/OVERSEER.md's Instruments section. The Rust core's profiler exists and serves
    `interrupts.{hint,vint}.cyclesSelf`, but the `perFrame[]` rows still carry no self field
    for either bucket, which is the specific gap the hold names. Not ours to close.

Measured, same ROM, same machine, 2026-08-26, as whole lane segments: raster_off 9.7 -> 0.5 s,
palette_variant 12.6 -> 1.5 s, snapshot_poison 9.8 -> 0.5 s, raster_source 13.3 -> 1.5 s;
whole lane 233 -> 191 s, same 26-of-27 verdict. The budgets below were NOT lowered to match:
a budget is a wedge detector and wants headroom, and five of the gates it covers still boot
the legacy server.

`--only` is unchanged: it runs in-process exactly as it always did. It is both the escape hatch
and the mechanism the segments themselves use, so it cannot be allowed to grow a second shape.

Usage:
    python3 tools/effects_gates.py [--rom s4.debug.bin] [--lst s4.debug.lst]
                                   [--demo-lst demo.debug.lst] [--only NAME,...]
Exit: 0 all gates pass · 1 a gate failed · 2 a gate could not run (scene/setup problem)
"""
import argparse
import json
import os
import re
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from suite_paths import harness_path  # noqa: E402
from scene_spans import (capability_bits, expected_spans,  # noqa: E402
                         game_caps, lst_spans, lst_unpaired_spans,
                         source_spans_by_cap)

AEON = Path(__file__).resolve().parent.parent
HARNESS = harness_path()
# The SPARSE-tier scenes: three anchor states of one patched two-channel schedule, all
# asserted through derive_arms below.
SCENES = ("mid_band", "suppressed", "above_screen")
# The DENSE-tier scene (Tier-3 item 3, 2026-08-19). Separate because it shares nothing with
# the three above: no patch channels (so no bands and no derive_arms), a different program
# shape, and — the point of it — assertions on RUNTIME state rather than on program words.
# Until this parcel every committed scene was sparse, so the dense tier, which is 27% of a
# frame on the shipped content, had no scene, no gate and no cost row at all.
DENSE_SCENE = "dense"

# ---------------------------------------------------------------------------
# THE GATE REGISTRY — one list, read by everything.
#
# `--only` validates against it, the segment partition is DERIVED from it, and `wanted()`
# records every name the body actually asks about so a full run can prove the two agree
# (see `check_registry_drift`). That last part is the point: a second hand-kept list of gate
# names is the copied-expectation defect this tree keeps re-learning, and the failure mode
# here is the quiet one — a gate added to the body but not to the registry would simply never
# be scheduled by any segment, and a totals line cannot tell "22 gates passed" from "22 gates
# passed and a 23rd never ran".
#
# `emulator` is what the partition keys on and it is a FACT ABOUT THE TOOL, checked by reading
# it: scanline_spans is computed inline from listings, demo_specialization_witness.py imports
# no launcher, and every other entry boots SOMETHING — since 2026-08-26 that is oracle-aether
# via `aether_instance` for all but scene:* (ab_runner) and cost_model (raster_cost_probe),
# which still reach `launcher.headless_emulator`. Note palette_variant IS emulator-backed —
# it drives the palette_dsl vectors through the real 68000 proc, which is the whole of the
# B2 gate.
#
# `budget` is the wedge timeout in seconds, NOT a performance assertion. A wedge hangs FOREVER,
# so the only job of these numbers is to sit above any honest run; a false WEDGED on a loaded
# machine would be worse than the disease. They are ~8-35x the runtimes measured here on
# 2026-08-19, standalone, on a machine simultaneously running two other agents' gate lanes:
#
#     scene:*         38-39 s   -> 300     raster_off        9 s -> 240
#     raster_source   14 s      -> 240     palette_variant  12 s -> 240
#     snapshot_poison 10 s      -> 240     cost_model       25 s -> 900
#     scanline_spans   0 s / demo_witness 1 s (listings only)    -> 120 each
#
# cost_model keeps the widest margin deliberately: it is the one segment that boots SIX
# emulator fixtures in sequence, other sessions have reported it near 3 min, and it is the
# segment whose re-run costs the most to trigger needlessly.
#
# THE MEASUREMENT THAT MATTERS is not in that table. While it was being taken, `snapshot_poison`
# WEDGED live — 642 s and still hanging with its oracle_gui alive, against 10 s when it ran
# clean minutes later. At a 240 s budget that becomes one retried segment; in the old
# single-invocation shape it was 22 lost results and no output at all.
GATE_SCENE_BUDGET = 300
GATE_EMU_BUDGET = 240


def gate_registry() -> list[tuple[str, bool, int]]:
    """(name, is-emulator-backed, wedge-timeout-seconds), in the order the body runs them."""
    reg = [(f"scene:{n}", True, GATE_SCENE_BUDGET) for n in SCENES]
    reg.append((f"scene:{DENSE_SCENE}", True, GATE_SCENE_BUDGET))
    reg += [
        ("raster_off", True, GATE_EMU_BUDGET),
        ("raster_source", True, GATE_EMU_BUDGET),
        # vsplit_landing is raster_source's sibling one layer out: raster_source observes the
        # handler INTERPRETING an op, this observes the RENDERED CONSEQUENCE of one — which
        # row the write governs and which row the VBlank writer still owns. It needs
        # `emulator/scanlines`, the only pixel readback with a `source` field, so it was on
        # oracle-aether before the rest of the lane joined it; it still manages its own
        # processes through its Server context manager, four short runs.
        ("vsplit_landing", True, GATE_EMU_BUDGET),
        ("palette_variant", True, GATE_EMU_BUDGET),
        ("snapshot_poison", True, GATE_EMU_BUDGET),
        # warp_mailbox is not an EFFECTS gate; it rides this lane because this is the
        # tree's ONLY emulator-gate runner, and the machinery it needs — per-gate
        # segmentation, a wedge timeout, one retry, ROM-scoped process reaping — is
        # exactly the machinery an emulator gate needs regardless of subject. It needs
        # `emulator/scanlines`, so like vsplit_landing it was on oracle-aether first; it
        # manages its own processes via the Server context manager, and its own RPC
        # deadlines mean a wedge surfaces as its exit 2 before this lane's budget expires.
        ("warp_mailbox", True, GATE_EMU_BUDGET),
        # boot_override rides here for warp_mailbox's reason, and beside it deliberately:
        # the two are the game's two external placement mailboxes and share their clamp and
        # camera-centring templates, so a change to either is a change to both. Its seven
        # runs each boot their own oracle-aether, hence the larger budget.
        ("boot_override", True, 480),
        # parallax_crossing is boot_override's other half and sits beside it for that reason:
        # the two witness the SAME resolver (Effects_ResolveParallax) at its two callers, and
        # their sampling rules are deliberate opposites — boot_override samples at the level
        # init's exit, BEFORE any Parallax_CheckBoundary, and this one only ever samples
        # AFTER a walked crossing. A change to the resolver should turn both red. One
        # oracle-aether process, two crossings (out and back), measured 0.66 s standalone and
        # 0.4 s as this lane's segment [12/14] on 2026-08-26 — the budget below is the lane's
        # ordinary emulator budget, ~600x that, and is a wedge ceiling and not a performance
        # assertion.
        ("parallax_crossing", True, GATE_EMU_BUDGET),
        # tile_cache_fill rides here for warp_mailbox's stated reason and is the third
        # non-effects member: it is the section streamer's own invariant (a cell RECORDED
        # as written was actually written), and this lane is still the tree's only
        # emulator-gate runner with segmentation, a wedge timeout and ROM-scoped reaping.
        # It sits beside warp_mailbox/boot_override's neighbourhood on purpose — all three
        # read the streaming state after camera motion. It is far too slow for build.sh's
        # inline lane (a headless boot plus 30 settled samples), which is exactly why it is
        # here and in the nightly.
        ("tile_cache_fill", True, GATE_EMU_BUDGET),
        # sec6_baseswap is item 11a's ON-SCREEN half, and the one gate here that boots BOTH
        # canonical shapes in a single invocation — the release arm is not decoration, it is
        # how the instrument separates the generated program from `OJZ_BaseSwap` BY
        # CONSTRUCTION (the hand-written demo emits zero bytes in `s4.bin`). Two servers, a
        # warp, four checkpoint-restored frame captures per shape and a dozen scanline stops
        # each, measured 300-400 s wall on a machine running two other agents' lanes, so the
        # budget below is a wedge ceiling well above that and not a performance assertion.
        ("sec6_baseswap", True, 900),
        ("cost_model", True, 900),
        ("scanline_spans", False, 120),
        ("demo_witness", False, 120),
    ]
    return reg


def segments() -> list[tuple[str, list[str], int]]:
    """(label, gate names, timeout) — the partition, DERIVED from the registry.

    The rule is two lines and it preserves registry order, so the aggregated result rows come
    out in exactly the order a single-process run would have printed them:

      * every emulator-backed gate is its OWN segment — it is the unit that wedges, and
        isolating it is the entire point;
      * a RUN of consecutive listing-only gates collapses into one segment — they boot nothing,
        cannot wedge, and paying a process spawn each would be waste.

    Nothing here names a gate. Add a gate to the registry and it gets scheduled; add one to the
    body only and `check_registry_drift` fails the run rather than letting it go unscheduled.
    """
    segs: list[tuple[str, list[str], int]] = []
    for name, emu, budget in gate_registry():
        if emu:
            segs.append((name, [name], budget))
        elif segs and segs[-1][0] == "listing":
            label, names, t = segs[-1]
            segs[-1] = (label, names + [name], t + budget)
        else:
            segs.append(("listing", [name], budget))
    return segs


def oracle_pids_for(rom: str) -> list[int]:
    """PIDs of legacy oracle_gui processes launched against THIS invocation's ROM.

    SCOPE, since the 2026-08-26 cutover: this searches for `oracle_gui` ONLY, and that is
    correct rather than an oversight. The seven segments now on oracle-aether reap their own
    children from a `finally` (and carry PR_SET_PDEATHSIG as a backstop), so there is nothing
    of theirs left for a retry to clean up. What remains for this function is scene:* and
    cost_model, which still boot the legacy server under xvfb-run.

    NEVER a bare `pkill oracle_gui`. That mistake was made twice on 2026-08-19 and it is not a
    style point: this tree routinely has several worktrees running the lane at once, and a bare
    pkill kills another session's emulator mid-measurement — which looks exactly like the wedge
    it was meant to clean up after.

    `launcher.headless_emulator` spells the legacy emulator as

        <oracle>/linux-port/build/oracle_gui <tmpdir>/settings.xml <rom_path>

    so the ROM path is an argv TOKEN. Ownership is token EQUALITY, not a substring search: two
    worktrees' ROMs differ only by a path prefix (`.../aeon/s4.debug.bin` vs
    `.../aeon/.claude/worktrees/<agent>/s4.debug.bin`), and a substring test on the shorter one
    matches the longer one's process.
    """
    want = os.fsencode(rom)
    pids = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            argv = (entry / "cmdline").read_bytes().split(b"\0")
        except OSError:
            continue                      # exited, or not ours to read
        if owns_rom(argv, want):
            pids.append(int(entry.name))
    return pids


def owns_rom(argv: list[bytes], rom: bytes) -> bool:
    """Is this argv an oracle_gui running THIS rom? Token equality, never substring."""
    return bool(argv) and argv[0].rsplit(b"/", 1)[-1] == b"oracle_gui" and rom in argv


def reap_oracle(rom: str) -> list[int]:
    """SIGKILL this ROM's leftover emulators before a retry. Returns what was killed."""
    killed = []
    for pid in oracle_pids_for(rom):
        try:
            pgid = os.getpgid(pid)
            # The launcher gives each headless instance its own session, so the group is
            # exactly {xvfb-run, Xvfb, oracle_gui} and taking the group is what stops the
            # Xvfb orphans piling up. The guard is what keeps a shared-group accident from
            # making this lane kill itself.
            if pgid != os.getpgid(0):
                os.killpg(pgid, signal.SIGKILL)
            else:
                os.kill(pid, signal.SIGKILL)
            killed.append(pid)
        except OSError:
            pass                          # already gone
    return killed


def run_one_segment(names: list[str], timeout: int, args, poison: bool) -> tuple:
    """One `--only` re-invocation. Returns (rc, rows-or-None, output-tail, wedged)."""
    with tempfile.NamedTemporaryFile(suffix=".json", prefix="effects-seg-", delete=False) as fh:
        jf = Path(fh.name)
    cmd = [sys.executable, str(Path(__file__).resolve()),
           "--rom", args.rom, "--lst", args.lst, "--demo-lst", args.demo_lst,
           "--only", ",".join(names), "--emit-results", str(jf)]
    env = dict(os.environ)
    env.pop("EFFECTS_GATES_POISON_WEDGE", None)     # never inherited by a child
    if poison:
        env["EFFECTS_GATES_POISON_HANG"] = "1"
    # Own session: subprocess's own timeout kill reaches the direct child only, and the thing
    # that actually wedges is a grandchild (the gate tool, its xvfb-run, its oracle_gui).
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         text=True, start_new_session=True, env=env)
    try:
        out = p.communicate(timeout=timeout)[0]
        wedged = False
    except subprocess.TimeoutExpired:
        try:
            os.killpg(os.getpgid(p.pid), signal.SIGKILL)
        except OSError:
            pass
        out = p.communicate()[0] or ""
        wedged = True
    rows = None
    if jf.exists():
        try:
            rows = json.loads(jf.read_text()) or None
        except json.JSONDecodeError:
            rows = None
        jf.unlink(missing_ok=True)
    tail = [ln for ln in (out or "").strip().splitlines() if ln.strip()]
    return (p.returncode, rows, (tail[-1] if tail else "(no output)"), wedged)


def run_segmented(args) -> int:
    """The default shape: one re-invocation per segment, one retry, aggregate identically."""
    segs = segments()
    emu = {n for n, is_emu, _ in gate_registry() if is_emu}
    n_emu = sum(1 for _, names, _ in segs if set(names) <= emu)
    poison_seg = os.environ.get("EFFECTS_GATES_POISON_WEDGE")
    poison_to = int(os.environ.get("EFFECTS_GATES_POISON_TIMEOUT", "0") or 0)
    if poison_seg:
        print(f"  !! TEST POISON ACTIVE: segment {poison_seg!r} will be hung on purpose"
              f"{f' (timeout forced to {poison_to}s)' if poison_to else ''}. "
              f"This run's result is NOT a lane verdict.\n")
        if poison_seg not in {label for label, _, _ in segs}:
            print(f"effects_gates: EFFECTS_GATES_POISON_WEDGE={poison_seg!r} is not a segment "
                  f"label; segments are {[s[0] for s in segs]}", file=sys.stderr)
            return 2
    print(f"  {len(segs)} segment{'s' if len(segs) != 1 else ''} ({n_emu} emulator-backed, "
          f"{len(segs) - n_emu} listing-only), each a `--only` re-invocation with a timeout "
          f"and ONE retry —\n  so an oracle stop-race wedge costs its own segment instead of "
          f"every gate's result.\n")

    rows: list = []
    setup_problem = False
    for i, (label, names, timeout) in enumerate(segs, 1):
        poison = (label == poison_seg)
        eff_to = poison_to if (poison and poison_to) else timeout
        head = f"  [{i:>2}/{len(segs)}] {label:<22}"
        t0 = time.monotonic()
        rc, got, tail, wedged = run_one_segment(names, eff_to, args, poison)
        if wedged:
            killed = reap_oracle(args.rom)
            print(f"{head} WEDGED at {eff_to}s — retrying once"
                  + (f" (reaped oracle_gui {killed} for this ROM)" if killed else
                     " (no oracle_gui of this ROM was left behind)"), flush=True)
            t0 = time.monotonic()
            rc, got, tail, wedged = run_one_segment(names, eff_to, args, poison)
        dt = time.monotonic() - t0
        if wedged:
            reap_oracle(args.rom)
            # ONE ROW PER GATE THE SEGMENT LEFT UNMEASURED, each tagged with that gate. This
            # is what keeps a wedge from reading as a missing gate: the gate DOES produce a
            # row (so R1 is satisfied) and that row FAILS (so R3 is satisfied by the failure),
            # and the reader is told which of the two states they are looking at by the text.
            for n in names:
                rows.append(row(n, f"{label} — WEDGED after retry (no result for `{n}`)", False,
                                f"two {eff_to}s attempts produced no result; this is the oracle "
                                f"stop-race, and this gate is UNMEASURED — not passing"))
            print(f"{head} WEDGED     {dt:6.1f}s  <- reported as a failure, not silence",
                  flush=True)
            continue
        if got is None:
            # Ran, but produced no result rows: a setup problem (exit 2 territory), not a
            # gate verdict. It must not be silent either — and, as above, one row per gate so
            # the row set stays complete and the failure is attributed rather than aggregate.
            setup_problem = setup_problem or rc != 0
            for n in names:
                rows.append(row(n, f"{label} — produced NO results (exit {rc}); `{n}` is "
                                   f"UNMEASURED", False, tail))
            print(f"{head} NO RESULTS {dt:6.1f}s  (exit {rc}) {tail}", flush=True)
            continue
        rows.extend(got)
        bad = sum(1 for r in got if not r[ROW_OK])
        status = "PASS" if not bad else f"FAIL x{bad}"
        # "rows", not "gates": a segment's row count is not its gate count, which is the whole
        # subject of the ROW SET block. The gate accounting is `report`'s closing line.
        print(f"{head} {status:<11}{dt:6.1f}s  {len(got)} row(s) for {len(names)} gate(s)",
              flush=True)
    print()
    # The expectation is the partition this run actually scheduled. In production that IS the
    # registry — `segments()` derives from `gate_registry()` and
    # `test_effects_gates_segments.py::test_segments_cover_the_registry_exactly_and_in_order`
    # pins the two equal, build-fatally — and taking it from `segs` keeps the check coherent
    # when a caller (a test) schedules a subset.
    rc = report(rows, {n for _, names, _ in segs for n in names})
    return 2 if (setup_problem and rc == 1) else rc


# ---------------------------------------------------------------------------
# THE ROW SET — every result row is TAGGED WITH THE GATE THAT PRODUCED IT.
#
# WHY THE OLD WITNESS WAS NOT ONE. This lane used to end with `effects_gates: OK — N gates`,
# where N was `len(results)` — a count of ROWS, not of gates (there are 15 registry entries and
# a green run prints 27 rows), and variable for two independent reasons:
#
#   * OUTCOME. A scene appends its determinism row and then `continue`s past its shape row when
#     that determinism failed, so one scene is 2 rows passing and 1 failing; `cost_model` is 2
#     rows on a good probe and 1 on a bad one; the dense scene the same.
#   * POPULATION. `scanline_spans` emits one row PER DECLARED `CAP_*` BIT, so retiring a
#     capability legitimately removes a row from a fully green lane.
#
# The second one is what actually happened, and it is worth stating because the outcome story
# alone cannot explain it: EVERY row-suppressing path in the body appends a FAILING row before
# it skips, so outcome variability can only ever produce a smaller count WITH RED IN IT. The
# unreconciled 28 -> 27 drop of 2026-08-26/27, all rows PASS, was `309d937a` retiring
# CAP_PER_LINE — 7 declared bits at `6fbcd186` (the 28 run) against 6 at `e4eee42c` (the 27
# run), and `309d937a` is an ancestor of the second and not of the first. So the count was
# never a witness, and it was not lying either; it was answering a different question.
#
# WHAT REPLACES IT. Rows carry `gate`, and the run asserts a SET against an expectation DERIVED
# from `wanted()` — i.e. from `gate_registry()`, filtered by whatever `--only` selected. There
# is no expected row COUNT anywhere in this file, because there is no honest way to derive one:
# a gate's row count is a function of its own outcome and of source-declared populations.
# Three rules, and the second and third are what keep it from being vacuous:
#
#   R1 POPULATION — every gate this run scheduled produced at least one row. This catches the
#      silent shape, and it is the one `check_registry_drift` structurally cannot: that check
#      compares the names the body ASKS ABOUT against the registry, so a gate whose
#      `if wanted(...)` still evaluates but whose body no longer appends passes it cleanly.
#   R2 NO STRAYS — no row is attributed to a gate this run did not schedule. A `--only` run
#      emitting somebody else's row means a `wanted()` guard is not guarding its emit.
#   R3 COMPLETENESS — a gate whose rows are ALL PASS must have reached its `final=True` emit,
#      the last row on its fully-successful path. This is the rule that separates the two
#      states the count conflated. A scene that fails determinism legitimately emits 1 row
#      instead of 2, and R3 is satisfied BY ITS FAILING ROW. A gate that quietly stopped
#      emitting its terminal assertion emits fewer rows with nothing failing — R3 fires. A
#      segment WEDGED twice is the first shape, not the second: `run_segmented` tags its
#      "WEDGED after retry" row with each gate it left unmeasured, so a wedge reads as a named
#      failure and never as a missing gate, and a missing gate reads as R1 and never as a wedge.
#
# WHAT R3 DOES NOT CATCH, said plainly rather than left for someone to discover: a gate that
# drops a MIDDLE row while still reaching its final one. Catching that needs a per-gate
# expected row count, and every honest source for one is a number somebody types — which is
# the defect this replaced. The `final` marker lives AT the emit site, so it travels when the
# code moves; a new gate that forgets one turns the lane red under R3 rather than quiet.
ROW_GATE, ROW_LABEL, ROW_OK, ROW_MSG, ROW_FINAL = range(5)


def row(gate: str, label: str, ok, msg, final: bool = False) -> list:
    """One result row: `[gate, label, ok, msg, final]`.

    `gate` MUST be a `gate_registry()` name — `check_row_coverage` R2 refuses anything else.
    `final` marks the LAST row a gate emits on its fully-successful path (R3). A list, not a
    tuple, because rows cross the parent/child seam as JSON.
    """
    return [gate, label, bool(ok), msg, bool(final)]


def check_row_coverage(scheduled, results: list) -> list[tuple[str, str]]:
    """(gate, why) for every expectation the emitted row SET fails to meet — R1/R2/R3 above.

    `scheduled` is derived, never listed: in-process it is what `wanted()` returned True for,
    and in `run_segmented` it is the union of the segment partition, which `segments()` derives
    from `gate_registry()` (and `test_effects_gates_segments.py` pins to it exactly).
    """
    problems: list[tuple[str, str]] = []
    by_gate: dict[str, list] = {}
    for r in results:
        by_gate.setdefault(r[ROW_GATE], []).append(r)
    for gate in sorted(scheduled):
        rows = by_gate.get(gate, [])
        if not rows:                                                            # R1
            problems.append((gate, f"gate `{gate}` PRODUCED NO ROW. It was scheduled and its "
                                   f"`if wanted(...)` ran, but nothing was appended — so this "
                                   f"lane cannot say whether it passed, and it did not pass. "
                                   f"(A count could not see this: it just got smaller.)"))
            continue
        if not any(r[ROW_FINAL] for r in rows) and all(r[ROW_OK] for r in rows):  # R3
            problems.append((gate, f"gate `{gate}` emitted {len(rows)} row(s), EVERY ONE PASS, "
                                   f"and never reached its terminal (final=True) assertion — "
                                   f"an INCOMPLETE row set. A gate that stops early because it "
                                   f"FAILED carries a failing row; this one carries none, so "
                                   f"something between its first row and its last went silent."))
    for gate in sorted(by_gate):                                                # R2
        if gate not in scheduled:
            problems.append((gate, f"{len(by_gate[gate])} row(s) attributed to `{gate}`, which "
                                   f"this run did not schedule — a `wanted()` guard is not "
                                   f"guarding its emit."))
    return problems


def report(results: list, scheduled) -> int:
    """The output contract — identical for the segmented and the `--only` shapes.

    The final line names the GATE SET and never a row count; the row count is printed beside
    it, labelled as the non-witness it is. `check_row_coverage` runs HERE rather than at the
    call sites so that no path can print a verdict without it.
    """
    scheduled = set(scheduled)
    covered = sorted({r[ROW_GATE] for r in results} & scheduled)
    rows = list(results) + [row(g, f"ROW-SET COVERAGE — {g}", False, why)
                            for g, why in check_row_coverage(scheduled, results)]
    bad = 0
    for r in rows:
        print(f"  {'PASS' if r[ROW_OK] else 'FAIL'}  {r[ROW_LABEL]}\n        {r[ROW_MSG]}")
        bad += 0 if r[ROW_OK] else 1
    print()
    if bad:
        print(f"effects_gates: FAIL — {bad} of {len(rows)} row(s), over {len(covered)} of "
              f"{len(scheduled)} scheduled gate(s)")
        return 1
    print(f"effects_gates: OK — all {len(scheduled)} scheduled gate(s) produced a complete "
          f"row set: {covered}")
    print(f"  ({len(rows)} result rows — a COUNT, and NOT the witness: a gate's row count "
          f"varies with its own outcome and with source-declared populations. The witness is "
          f"the gate set above.)")
    return 0


def check_registry_drift(queried: set) -> str:
    """'' if the body's gates and the registry are the same set, else why not.

    Every run evaluates every `if wanted(...)`, including a `--only` run, so this is checkable
    from any invocation. A gate in the body but not the registry would never be scheduled by a
    segment; one in the registry but not the body would make its segment measure nothing.
    """
    known = {n for n, _, _ in gate_registry()}
    unscheduled, phantom = sorted(queried - known), sorted(known - queried)
    if not unscheduled and not phantom:
        return ""
    parts = []
    if unscheduled:
        parts.append(f"gates the body runs but the registry does not schedule: {unscheduled}")
    if phantom:
        parts.append(f"gates the registry schedules but the body never runs: {phantom}")
    return "; ".join(parts)


def emp_int(rel: str, name: str) -> int:
    """A `const NAME = <int>` out of an .emp source, so no expectation here is hand-copied."""
    txt = (AEON / rel).read_text()
    m = re.search(rf"^\s*(?:pub\s+)?const\s+{re.escape(name)}\s*=\s*(\$[0-9A-Fa-f]+|-?\d+)",
                  txt, re.M)
    if not m:
        raise SystemExit(f"effects_gates: cannot find `const {name}` in {rel}")
    v = m.group(1)
    return int(v[1:], 16) if v.startswith("$") else int(v)


# ---------------------------------------------------------------------------
# SCENE RESOLUTION — the committed scenes name SYMBOLS, never addresses, and never a listing.
#
# ab_runner resolves every `symbol:` poke and capture through the file the scene's top-level
# `symbols` key names (`emulator/load_symbols`). Until 2026-08-26 that key was the MAIN
# tree's `<suite>/aeon/s4.debug.lst`, spelled absolutely in all four
# scenes — so a gate run in a worktree resolved its symbols from whatever listing master
# happened to have. Measured on parcel/showcase-effects-r2: the parcel moves
# `Raster_Buf_A/_B/Raster_Active_Buf` by +84 B (`BAND_CURVE_BYTES x MAX_PARALLAX_BANDS +
# CURVE_CARRY_WORDS x 2` = 80 + 4), the scene captured master's addresses, and every
# `scene:*` shape gate reported "`Raster_Active_Buf points at 0x438aff`, which is neither
# captured buffer" — a wrong-instrument failure, not a wrong-ROM one. The determinism half
# passed throughout, which is exactly the blind spot: two identical runs of a stale capture
# agree perfectly.
#
# The fix keeps the scene files free of any tree-specific path: they carry the placeholder
# `SCENE_SYMBOLS_PLACEHOLDER` and `resolve_scene()` writes a copy with `symbols` set to the
# `--lst` under test, next to the run's own output. A committed scene that names a real
# path is refused here (loud), and so is one with no `symbols` at all — every committed
# scene pokes by symbol, so a scene without a listing would silently poke nothing.
SCENE_SYMBOLS_PLACEHOLDER = "$LST"


def scene_path(name: str) -> Path:
    return AEON / "tools" / "scenes" / f"effects_raster_{name}.json"


def resolve_scene(name: str, lst: str, out_dir: Path) -> Path:
    """Materialise the committed scene `name` against the listing `lst` under test.

    Returns the path of the resolved copy (`<out_dir>/scene.json`). Raises ValueError on
    a committed scene that hardcodes a listing (the defect this exists to remove) or has
    no `symbols` key; raises FileNotFoundError if `lst` is not a file — an ab_runner fed a
    missing listing answers every symbol poke against blank RAM and reports ALL EQUAL.
    """
    src = scene_path(name)
    sc = json.loads(src.read_text())
    sym = sc.get("symbols")
    if sym != SCENE_SYMBOLS_PLACEHOLDER:
        raise ValueError(
            f"{src}: `symbols` is {sym!r}, not the placeholder {SCENE_SYMBOLS_PLACEHOLDER!r}. "
            f"Committed scenes must not name a listing — that is how a worktree's gates "
            f"resolved master's RAM addresses (2026-08-26). The listing under test is "
            f"substituted at run time by resolve_scene().")
    lst_path = Path(lst)
    if not lst_path.is_file():
        raise FileNotFoundError(
            f"scene {name}: listing under test not found: {lst} — build the shape first; "
            f"a scene run without symbols pokes nothing and still reports ALL EQUAL")
    sc["symbols"] = str(lst_path.resolve())
    out_dir.mkdir(parents=True, exist_ok=True)
    dst = out_dir / "scene.json"
    dst.write_text(json.dumps(sc, indent=2) + "\n")
    return dst


def scene_pokes(name: str) -> dict:
    """The scene's own poke values — the inputs every expectation below is derived FROM."""
    sc = json.loads(scene_path(name).read_text())
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
    ap.add_argument("--only", default="", help="comma-separated gate names; runs in-process")
    ap.add_argument("--emit-results", default="",
                    help="internal: where a segment child writes its result rows as JSON")
    ap.add_argument("--resolve-scene", default="", metavar="NAME",
                    help="hand-run helper: write the committed scene NAME resolved against "
                         "--lst into a temp dir, print its path, and exit (no gate runs)")
    args = ap.parse_args()
    rom, lst = str(Path(args.rom).resolve()), str(Path(args.lst).resolve())
    args.rom, args.lst = rom, lst
    args.demo_lst = str(Path(args.demo_lst).resolve())

    if args.resolve_scene:
        known = SCENES + (DENSE_SCENE,)
        if args.resolve_scene not in known:
            print(f"effects_gates: unknown scene {args.resolve_scene!r}; known: {list(known)}",
                  file=sys.stderr)
            return 2
        try:
            print(resolve_scene(args.resolve_scene, lst,
                                Path(tempfile.mkdtemp(prefix="effects-scene-"))))
        except (ValueError, FileNotFoundError) as e:
            print(f"effects_gates: {e}", file=sys.stderr)
            return 2
        return 0

    # TEST-ONLY, and FIRST so it models a wedge faithfully — a real one can strike at any point,
    # including before this process has looked at a file. The parent sets this in exactly one
    # segment child's environment when EFFECTS_GATES_POISON_WEDGE names that segment, and the
    # child then hangs the way an oracle stop-race hangs it. It exists so the retry/WEDGED path
    # has red-first evidence instead of waiting for an intermittent race to oblige.
    if os.environ.get("EFFECTS_GATES_POISON_HANG"):
        print("effects_gates: TEST POISON — hanging this segment on purpose", flush=True)
        while True:
            time.sleep(3600)

    want = set(args.only.split(",")) if args.only else None
    if want is not None:
        unknown = sorted(want - {n for n, _, _ in gate_registry()})
        if unknown:
            print(f"effects_gates: unknown gate name(s) in --only: {unknown}\n"
                  f"  known: {[n for n, _, _ in gate_registry()]}", file=sys.stderr)
            return 2
    if not Path(rom).is_file():
        print(f"effects_gates: ROM not found: {rom} — build it first", file=sys.stderr)
        return 2
    queried: set = set()
    # `queried` is every name the body ASKS about (the registry-drift check); `ran` is the
    # subset `--only` actually selected, and it is the row-set expectation. Two sets because
    # they answer two different questions and one of them was already being asked.
    ran: set = set()

    def wanted(n: str) -> bool:
        queried.add(n)
        if want is None or n in want:
            ran.add(n)
            return True
        return False

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

    # The default shape. Everything above (ROM check, bands, header) is the parent's too, so a
    # segmented run and an `--only` run open identically; below this line the parent only
    # schedules, and the gates themselves run in the children.
    if want is None:
        return run_segmented(args)

    results: list[tuple[str, bool, str]] = []
    tmp = Path(tempfile.mkdtemp(prefix="effects-gates-"))

    for name in SCENES:
        if not wanted(f"scene:{name}"):
            continue
        out = tmp / name
        try:
            resolved = resolve_scene(name, lst, out)
        except (ValueError, FileNotFoundError) as e:
            results.append(row(f"scene:{name}", f"scene:{name} determinism", False,
                               f"scene not resolvable: {e}"))
            continue
        ok, msg = run(["python3", str(HARNESS / "ab_runner.py"), "--old", rom, "--new", rom,
                       "--scene", str(resolved),
                       "--out", str(out), "--selfcheck"], name)
        results.append(row(f"scene:{name}", f"scene:{name} determinism", ok, msg))
        if not ok:
            # The row-suppressing `continue` the old count could not distinguish from a gate
            # going dark. It is safe because the row above FAILS: R3 reads that failure as the
            # reason this gate stops one row short.
            continue
        w1, w3, setreg = derive_arms(name, bands)
        cmd = ["python3", str(AEON / "tools/effects_scene_assert.py"), str(out / "new/hashes.json"),
               "--expect-word", f"1={hex(w1)}", "--expect-word", f"3={hex(w3)}",
               "--expect-present" if setreg else "--expect-absent", "0x8C89"]
        ok2, msg2 = run(cmd, name)
        results.append(row(f"scene:{name}",
                           f"scene:{name} shape (word1={w1:#06x} word3={w3:#06x}, "
                           f"$8C89 {'present' if setreg else 'absent'})", ok2, msg2,
                           final=True))

    # ------------------------------------------------------------------
    # 2b. THE DENSE TIER (Tier-3 item 3). Two halves, and the second is the one that had
    # never existed: the PROGRAM half asserts the words raster_gradient_program emitted,
    # the RUNTIME half asserts what Raster_HInt's dense body did with them.
    #
    # The runtime assertion is `Raster_Dense_Cursor`, and it is chosen because it is the
    # only cell that counts. The dense body advances it three words per line, so at frame
    # end it equals stream + lines * RASTER_DENSE_WORDS_PER_LINE * 2 IF AND ONLY IF the body ran
    # exactly `lines` times. A run that fired one line short, one line long, or streamed
    # from the wrong base lands somewhere else. Nothing else here can see that: CRAM is
    # re-asserted at frame top (ojz_effects.emp's own note on why the pixel instrument was
    # needed), the program words are ROM and identical either way, and `state_hash` would
    # only say "something differs".
    #
    # Every expectation is derived — the run's geometry out of ojz_effects.emp, the opcode
    # and arm constants out of raster.emp, the stream's address out of the listing.
    if wanted(f"scene:{DENSE_SCENE}"):
        top = emp_int("games/sonic4/data/effects/ojz_effects.emp", "OJZ_GRAD_TOP")
        glines = emp_int("games/sonic4/data/effects/ojz_effects.emp", "OJZ_GRAD_LINES")
        gaddr = emp_int("games/sonic4/data/effects/ojz_effects.emp", "OJZ_GRAD_CRAM_ADDR")
        dense_words = emp_int("engine/effects/raster.emp", "RASTER_DENSE_WORDS_PER_LINE")
        op_run = emp_int("engine/effects/raster.emp", "OP_RUN_GRADIENT")
        every = emp_int("engine/effects/raster.emp", "RASTER_ARM_EVERY_LINE")
        # The stream's link-time address. A dense program is the one shape that carries a
        # real pointer (raster.emp's note on why it is a struct and not a [u16]), so the
        # listing is where this comes from — there is no comptime form of it to read.
        stream = None
        for line in Path(lst).read_text(errors="replace").splitlines():
            if line.startswith("(0) ") and line.rstrip().endswith("OJZ_GradientStream:"):
                stream = int(line[4:].split(" :", 1)[0].split("/", 1)[1], 16) & 0xFFFFFF
                break
        if stream is None:
            results.append(row(f"scene:{DENSE_SCENE}", f"scene:{DENSE_SCENE}", False,
                               f"OJZ_GradientStream not in {lst} — every expectation below "
                               f"would be guesswork"))
        else:
            # The VDP CRAM-write command longword: type/rwd 3 in the top two bits, the
            # address split A13-A0 into bits 16-29 and A15-A14 into bits 0-1 (engine.vdp's
            # vdp_comm). ojz_effects.emp pins this same value with its own ensure.
            cmd = 0xC0000000 | ((gaddr & 0x3FFF) << 16) | ((gaddr & 0xC000) >> 14)
            out = tmp / DENSE_SCENE
            try:
                resolved = resolve_scene(DENSE_SCENE, lst, out)
                ok, msg = run(["python3", str(HARNESS / "ab_runner.py"), "--old", rom,
                               "--new", rom, "--scene", str(resolved),
                               "--out", str(out), "--selfcheck"], DENSE_SCENE)
            except (ValueError, FileNotFoundError) as e:
                ok, msg = False, f"scene not resolvable: {e}"
            results.append(row(f"scene:{DENSE_SCENE}", f"scene:{DENSE_SCENE} determinism",
                               ok, msg))
            if ok:
                end = stream + glines * dense_words * 2
                cmd_args = [
                    # --- the program, as raster_gradient_program emitted it ---
                    "--expect-word", f"1={hex(0x8A00 | (top - 3))}",   # raster_arm(1, top-1)
                    "--expect-word", f"3={hex(every)}",                # raster_arm(top-1, top)
                    "--expect-word", f"5={hex(every)}",                # the setup record's arm
                    "--expect-word", f"7={hex(op_run)}",
                    "--expect-word", f"10={glines}",
                    "--expect-word", f"8={hex((cmd >> 16) & 0xFFFF)}",
                    "--expect-word", f"9={hex(cmd & 0xFFFF)}",
                    # --- what the HANDLER did with it ---
                    "--expect-region", f"dense_state+0:2=0",           # rewound at VBlank
                    "--expect-region", f"dense_state+2:4={hex(end)}",  # ran exactly `lines`
                    "--expect-region", f"dense_state+6:4={hex(cmd)}",  # stashed the command
                ]
                ok2, msg2 = run(["python3", str(AEON / "tools/effects_scene_assert.py"),
                                 str(out / "new/hashes.json")] + cmd_args, DENSE_SCENE)
                results.append(row(
                    f"scene:{DENSE_SCENE}",
                    f"scene:{DENSE_SCENE} dense tier (run {top}..{top + glines - 1}; "
                    f"cursor ends at {end:#08x} = stream + {glines} * {dense_words} words, "
                    f"which is true only if the dense body ran exactly {glines} times)",
                    ok2, msg2, final=True))

    if wanted("raster_off"):
        ok, msg = run(["python3", str(AEON / "tools/raster_off_gate.py"),
                       "--rom", rom, "--lst", lst], "raster_off")
        results.append(row("raster_off", "raster_off (EFX-7 teardown)", ok, msg, final=True))

    if wanted("raster_source"):
        ok, msg = run(["python3", str(AEON / "tools/raster_source_gate.py"),
                       "--rom", rom, "--lst", lst], "raster_source")
        results.append(row("raster_source",
                           "raster_source (handler streams from the encoded address)",
                           ok, msg, final=True))

    if wanted("vsplit_landing"):
        ok, msg = run(["python3", str(AEON / "tools/vsplit_landing_gate.py"),
                       "--rom", rom, "--lst", lst], "vsplit_landing")
        results.append(row("vsplit_landing",
                           "vsplit_landing (the two-writer ruling: the mid-frame split governs "
                           "from its landing row down, the VBlank writer keeps the rows above)",
                           ok, msg, final=True))

    if wanted("palette_variant"):
        ok, msg = run(["python3", str(AEON / "tools/palette_variant_gate.py"),
                       "--rom", rom, "--lst", lst], "palette_variant")
        results.append(row("palette_variant",
                           "palette_variant (B2: the palette_dsl mirror actually checks the "
                           "asm)", ok, msg, final=True))

    if wanted("snapshot_poison"):
        ok, msg = run(["python3", str(AEON / "tools/snapshot_poison_gate.py"),
                       "--rom", rom, "--lst", lst], "snapshot_poison")
        results.append(row("snapshot_poison",
                           "snapshot_poison (E-B: splices copy what the captured mask says)",
                           ok, msg, final=True))

    if wanted("warp_mailbox"):
        ok, msg = run(["python3", str(AEON / "tools/warp_mailbox_gate.py"),
                       "--rom", rom, "--lst", lst], "warp_mailbox")
        results.append(row("warp_mailbox",
                           "warp_mailbox (the DEBUG warp lands the walked reference; a bare "
                           "camera poke does not)", ok, msg, final=True))

    if wanted("boot_override"):
        ok, msg = run(["python3", str(AEON / "tools/boot_override_gate.py"),
                       "--rom", rom, "--lst", lst], "boot_override")
        results.append(row("boot_override",
                           "boot_override (the DEBUG boot mailbox puts the FIRST painted "
                           "frame at the cursor, matching a warp to the same place)",
                           ok, msg, final=True))

    if wanted("parallax_crossing"):
        ok, msg = run(["python3", str(AEON / "tools/parallax_crossing_gate.py"),
                       "--rom", rom, "--lst", lst], "parallax_crossing")
        results.append(row("parallax_crossing",
                           "parallax_crossing (a WALKED section crossing installs the config "
                           "Effects_ResolveParallax names for the section entered — section "
                           "beats preset beats act)", ok, msg, final=True))

    if wanted("tile_cache_fill"):
        ok, msg = run(["python3", str(AEON / "tools/tile_cache_fill_gate.py"),
                       "--rom", rom, "--lst", lst,
                       "--samples", "30", "--step", "10", "--post", "30"],
                      "tile_cache_fill")
        results.append(row("tile_cache_fill",
                           "tile_cache_fill (every plane-A cell the section streamer RECORDS "
                           "as written matches the tile cache, and no partially filled column "
                           "or row is ever inside the recorded window)", ok, msg, final=True))

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
        # A no-op record is the fire base less the loop entry/exit a record WITH ops pays,
        # PLUS the frame-rewind interlock, which only a no-op record reaches (raster.emp's
        # `.priming`). Reading `guard` from the .emp rather than folding it into `base` is
        # what keeps this gate able to tell the two apart: a change that moved the interlock
        # into the prologue would leave F0 right and every other fixture 30 cycles light.
        guard = emp_int("engine/effects/raster_dsl.emp", "RASTER_PRIMING_GUARD_CYC")
        f0 = 2 * (base - 16 + guard)
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
        # The DENSE tier's per-line cost (Tier-3 item 3). One constant, one fixture PAIR,
        # and the expectation is a SLOPE: FD1 and FD2 are the same program at two line
        # counts, so everything they share — the fire base, the priming records, the setup
        # fire, the trailing fire — cancels in the subtraction and what is left is one
        # dense gradient line. No absolute figure here is a dense cost, and reading either
        # fixture alone would be reading mostly overhead.
        #
        # THE CONSTANT IS MEASURED, like RASTER_FIRE_BASE_CYC and RASTER_SCANLINE_CYC and
        # unlike every op-class term above (those are modelled from instruction timings and
        # this gate re-derives them longhand). The dense body's cost includes the exception
        # entry and the `ints_off` bracket, neither of which the op model prices at all, so
        # a modelled figure here would be a new model rather than a use of the existing one.
        dense_line = emp_int("engine/effects/raster_dsl.emp", "RASTER_DENSE_LINE_GRAD_CYC")
        jf = tmp / "cost.json"
        p = subprocess.run(["python3", str(AEON / "tools/raster_cost_probe.py"),
                            "--rom", rom, "--lst", lst,
                            "--only", "F0,F1,F3,F4,F5,F8,FD1,FD2,FR1,FR2",
                            "--out", str(jf)],
                           capture_output=True, text=True)
        if p.returncode != 0 or not jf.exists():
            results.append(row("cost_model", "cost_model vs hardware", False,
                               (p.stdout + p.stderr).strip().splitlines()[-1:]
                               or ["probe failed"]))
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
            results.append(row("cost_model",
                            f"cost_model vs hardware (F0 {f0}, F1 {expect_f1}, F3 {expect_f3}, "
                            f"F4 {expect_f4}, F5 {expect_f5}, F8 {expect_f8} — all computed from "
                            f"the shipped constants; F1/F5 carry the register write, the one op "
                            f"dispatched by the zero pre-test rather than by the chain, "
                            f"F4 is the region op at dispatch depth 1, F8 is the restore)", ok,
                            f"measured F0={got_f0} F1={got_f1} F3={got_f3} F4={got_f4} "
                            f"F5={got_f5} F8={got_f8}"))
            # The dense row. The divisor comes out of the fixtures' own published
            # parameters, never restated here — a fixture whose line counts are edited
            # re-derives rather than silently re-scaling the measurement.
            d1, d2 = d["FD1"], d["FD2"]
            dl = d2["dense"]["lines"] - d1["dense"]["lines"]
            slope = (d2["cycles"][0] - d1["cycles"][0]) / dl
            # `calls` is the fixture's own correctness check, derived (two priming, the
            # setup record, the run, and ONE trailing fire: Ruling 1b leaves the last two
            # dense lines' every-line arms in flight, and since the dense rider the LAST
            # one is overwritten by `.dense_end`'s fall into `.park`). A dense fixture
            # whose run did not run as authored must not be read as a cost.
            #
            # IMPORTED, NOT RESTATED. This gate used to spell `+ 5` beside a paragraph
            # explaining why, so the rider had to fix the number in two files that could
            # not fail each other. The probe owns the derivation; a gate that disagreed
            # with it would have reported a fixture as healthy while the probe printed a
            # `!!` about the same run.
            from raster_cost_probe import dense_fire_count  # noqa: E402
            calls_ok = all(f["calls"][0] == dense_fire_count(f["dense"]["lines"])
                           for f in (d1, d2))
            ok_d = calls_ok and slope == dense_line
            shape = f"lines + {dense_fire_count(0)}"
            results.append(row(
                "cost_model",
                f"dense cost row (RASTER_DENSE_LINE_GRAD_CYC = {dense_line}; the slope "
                f"(FD2 - FD1) / {dl} lines, with both fires counts derived as {shape})",
                ok_d,
                f"measured FD1={d1['cycles'][0]}/{d1['calls'][0]} fires, "
                f"FD2={d2['cycles'][0]}/{d2['calls'][0]} fires -> {slope:.1f} cyc/line"
                + ("" if calls_ok else f"  !! a fire count is not {shape}")))

            # The RAMP row (EFFECTS-W1 item 6) — `.ramp_body`'s twin of the dense gradient
            # row directly above, same method: FR1/FR2 are the same OP_RUN_RAMP program at
            # two line counts, so the slope is one ramp line with every shared overhead
            # cancelled. RASTER_DENSE_LINE_RAMP_CYC is the HBlank budget check EFFECTS-W1
            # item 6 asked for — this gate is what re-runs it on every canonical build,
            # the same standing this file already gives the gradient constant.
            ramp_line = emp_int("engine/effects/raster_dsl.emp", "RASTER_DENSE_LINE_RAMP_CYC")
            r1, r2 = d["FR1"], d["FR2"]
            rl = r2["ramp"]["lines"] - r1["ramp"]["lines"]
            rslope = (r2["cycles"][0] - r1["cycles"][0]) / rl
            r_calls_ok = all(f["calls"][0] == dense_fire_count(f["ramp"]["lines"])
                             for f in (r1, r2))
            ok_r = r_calls_ok and rslope == ramp_line
            results.append(row(
                "cost_model",
                f"ramp cost row (RASTER_DENSE_LINE_RAMP_CYC = {ramp_line}; the slope "
                f"(FR2 - FR1) / {rl} lines, with both fires counts derived as {shape})",
                ok_r,
                f"measured FR1={r1['cycles'][0]}/{r1['calls'][0]} fires, "
                f"FR2={r2['cycles'][0]}/{r2['calls'][0]} fires -> {rslope:.1f} cyc/line"
                + ("" if r_calls_ok else f"  !! a fire count is not {shape}"),
                final=True))

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
            results.append(row("scanline_spans", "scanline_spans (two-fixture differential)",
                               False,
                               f"demo listing not found: {args.demo_lst} — run "
                               f"`DEBUG=1 ./build.sh demo`. A one-fixture run is not this "
                               f"gate."))
        else:
            bits = capability_bits()
            caps_s4, caps_demo = game_caps("sonic4"), game_caps("demo")
            got_s4, got_demo = lst_spans(lst), lst_spans(args.demo_lst)
            # A region needs TWO boundaries. A set-level comparison alone cannot tell a
            # span with one boundary from a span with two, and a poison that renamed a
            # single `_begin` walked straight through the first version of this gate.
            for fixture, path in (("sonic4", lst), ("demo", args.demo_lst)):
                unpaired = lst_unpaired_spans(path)
                results.append(row(
                    "scanline_spans",
                    f"scanline_spans {fixture} boundary pairing",
                    not unpaired,
                    "every emitted span carries both _begin and _end" if not unpaired
                    else f"half-bracketed spans (a region with one boundary cannot be "
                         f"measured): {unpaired}"))
            want_s4, want_demo = expected_spans(caps_s4), expected_spans(caps_demo)
            # Depth-scoped: one row per capability, so a failure names the BIT rather
            # than a pile of span names. §8.2's three depths are all carried by spans,
            # so the scoping that matters at this layer is the capability itself.
            src_by_cap = source_spans_by_cap()
            # Which declared bits the loop below actually asked about — the subject of this
            # gate's terminal row, and the thing its old floor could not see.
            covered_caps: set = set()
            for cap in sorted(bits):
                spans = {s for s in (want_s4 | got_s4 | got_demo)
                         if s.startswith(cap[len("CAP_"):].lower())}
                if not spans:
                    # A declared capability with no span in either LISTING is two very
                    # different states, and the row must say which (P3 Task 16 — the
                    # single informational row this replaces conflated them, and its
                    # own comment named the fear: "a capability that quietly stopped
                    # being gated would disappear exactly here"):
                    #
                    #  * SOURCE brackets exist, no fixture raises the bit. The lowering
                    #    is real and comptime-elided from BOTH shipped games — a
                    #    statement about ADOPTION (PARK-1), not about the gating; the
                    #    two-fixture differential has no subject until a game raises
                    #    the bit. Informational. Today: CAP_MULTI_DEFORM_TABLE and
                    #    CAP_FACTOR_CURVE, whose measured elision (instrument builds,
                    #    non-canonical) is recorded in demo_specialization_witness.py's
                    #    re-derivation log.
                    #
                    #  * NO source brackets either — a `pub const` bit with no lowering
                    #    anywhere. Either the brackets were deleted while the bit stayed
                    #    promoted, or the bit was promoted ahead of its subject (the
                    #    vacuous-gate shape Task 5 refuses). Every declared bit had
                    #    source brackets when this check landed (all seven, verified
                    #    2026-08-22), so this state FAILS rather than informs.
                    src = sorted(src_by_cap.get(cap, ()))
                    if src:
                        covered_caps.add(cap)
                        results.append(row(
                            "scanline_spans",
                            f"scanline_spans {cap} — GATED IN SOURCE, RAISED BY "
                            f"NEITHER FIXTURE ({len(src)} span(s) elided from both: "
                            f"{src})",
                            True,
                            "adoption pending (PARK-1); the differential has no "
                            "subject until a game raises the bit"))
                    else:
                        covered_caps.add(cap)
                        results.append(row(
                            "scanline_spans",
                            f"scanline_spans {cap} — NOT GATED ANYWHERE (no bracketed "
                            f"span in the engine sources or either fixture)",
                            False,
                            "a declared `pub const` capability with no lowering: "
                            "either its brackets were deleted while the bit stayed "
                            "promoted, or the bit was promoted ahead of its subject "
                            "(the vacuous-gate shape)"))
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
                covered_caps.add(cap)
                results.append(row(
                    "scanline_spans",
                    f"scanline_spans {cap} (sonic4 {'raised' if raised_s4 else 'clear'}, "
                    f"demo {'raised' if raised_demo else 'clear'}) — differential "
                    f"{want_diff}",
                    ok,
                    f"sonic4 {sorted(have_s4)} vs expected {sorted(exp_s4)}; "
                    f"demo {sorted(have_demo)} vs expected {sorted(exp_demo)}"))
            # THE CAPABILITY COVERAGE ROW — this gate's terminal (final=True) assertion, and
            # the reason its row count is POPULATION-variable at all.
            #
            # IT REPLACES A FLOOR THAT COULD NOT FIRE. The old check was
            # `if not any(r[0].startswith("scanline_spans ") for r in results)`, and the two
            # boundary-pairing rows appended a few lines above both begin with exactly that
            # string — so the condition was False on every reachable path and the anti-vacuity
            # check was itself vacuous. (It also read `r[0]` as a LABEL, which rows no longer
            # are.) This asserts the SET instead: every bit `capability_bits()` declares in
            # scene_dsl.emp must have produced a row from the loop above. Retiring a bit
            # legitimately drops a row — and that is exactly what took the whole lane from 28
            # rows to 27 on 2026-08-26 with everything still green — so the population belongs
            # in a row that SAYS the number, not in a total nobody can diff.
            missing = sorted(set(bits) - covered_caps)
            results.append(row(
                "scanline_spans",
                f"scanline_spans capability coverage — {len(covered_caps)} of {len(bits)} "
                f"`pub const CAP_*` bits declared in scene_dsl.emp produced a row",
                bool(bits) and not missing,
                "every declared capability was asked about" if (bits and not missing)
                else f"declared but never asked about: {missing}" if missing
                else "NO capability bits declared at all — every check above ran over an "
                     "empty set and this gate measured nothing",
                final=True))

    # ------------------------------------------------------------------
    # 6b. EFFECTS-W1 item 11a's on-screen half: a RUNNING machine obeys the base-swap
    # program a preset DOCUMENT asks for. `tools/plane_base_swap_gate.py` (build.sh, every
    # canonical build) proves the HAND-WRITTEN demo's bytes are in the ROM and says in its
    # own docstring that it does not prove the VDP draws anything; this is that half, and
    # its subject is the GENERATED program bound to section 6, never the demo.
    #
    # It derives the release ROM/listing from `--rom`/`--lst` by dropping `.debug`, so the
    # lane's ordinary two arguments reach both shapes. A missing release artifact REFUSES
    # (exit 2) rather than quietly measuring one shape.
    if wanted("sec6_baseswap"):
        rel_rom = rom.replace(".debug.bin", ".bin")
        rel_lst = lst.replace(".debug.lst", ".lst")
        ok, msg = run(["python3", str(AEON / "tools/sec6_baseswap_witness.py"),
                       "--rom", rom, "--lst", lst,
                       "--release-rom", rel_rom, "--release-lst", rel_lst], "sec6_baseswap")
        results.append(row("sec6_baseswap",
                           "sec6_baseswap (the section's own crossing installs the GENERATED "
                           "base-swap program, and the VDP's Plane A base moves at the "
                           "authored line — in both shapes)", ok, msg, final=True))

    # ------------------------------------------------------------------
    # 7. The demo witness (Task 8): span absence + the committed per-proc image pin.
    if wanted("demo_witness"):
        ok, msg = run(["python3", str(AEON / "tools/demo_specialization_witness.py"),
                       "--sonic4-lst", lst, "--demo-lst", args.demo_lst], "demo_witness")
        results.append(row("demo_witness", "demo_witness (span absence + image pin)", ok, msg,
                           final=True))

    # The registry has to describe the body, or the segmentation silently drops a gate. Checked
    # from every invocation, because every invocation evaluates every `if wanted(...)`.
    drift = check_registry_drift(queried)
    if drift:
        print(f"effects_gates: GATE REGISTRY DRIFT — {drift}\n"
              f"  The segment partition is derived from `gate_registry()`, so a gate missing "
              f"from it is a gate no default run would ever schedule.", file=sys.stderr)
        return 2

    if args.emit_results:
        Path(args.emit_results).write_text(json.dumps(results))

    print()
    # `ran`, not the registry: an `--only` run legitimately emits a subset, and the
    # expectation must be exactly what this invocation scheduled. The parent re-checks the
    # aggregate against the whole partition, so a child that dropped a row is caught twice.
    return report(results, ran)


if __name__ == "__main__":
    sys.exit(main())
