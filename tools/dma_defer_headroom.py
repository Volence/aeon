#!/usr/bin/env python3
"""dma_defer_headroom -- the frame's Important-queue headroom, and what wants it.

WHAT THIS MEASURES, AND WHY IT IS NOT THE STRADDLE QUESTION
===========================================================

`tools/dplc_straddle.py` asks whether the Important queue has enough SLOTS.
This asks whether the frame has enough BYTES, which is a different wall with a
different failure mode, and until 2026-09-05 nothing computed it.

The two walls behave differently on being hit:

  SLOTS   -- `QueueDMA_Important` returns carry SET. `perform_dplc` sees the
             carry, takes `bcs .done`, and leaves `prev_frame` STALE so the
             next frame retries. Counted by DMA_Overflow_Count /
             Dbg_DMA_Enq_Capped. LOUD.

  BYTES   -- `Drain_Budgeted_Queue` (engine/system/dma_queue.emp) reaches
             `.out_of_budget`, COMPACTS the survivors to the queue base and
             leaves them for next frame's fresh budget. The enqueue already
             returned carry CLEAR, so `perform_dplc` has ALREADY committed
             `prev_frame`. No counter moves. SILENT.

The silent one is the interesting one, because of what happens on the OTHER
queue in the same VBlank. Order in `VInt_Level` (engine/system/vblank.emp):

    seed DMA_Budget_Remaining = DMA_Budget_Default      :136
    Enqueue_Dirty_Buffers   -- palette + SAT + HScroll -> CRITICAL   :161
    charge Plane_Buffer_Ptr against the budget                       :169
    charge the whole Critical queue against the budget               :190
    Process_DMA_Critical    -- UNBUDGETED, always fully drains       :200
    Process_DMA_Important   -- BUDGETED, may defer                   :264
    Process_DMA_Deferrable  -- BUDGETED, may defer                   :276

The sprite attribute table ships on Critical. The art its mappings index ships
on Important. Nothing interlocks them. So on a frame where the residual budget
runs out mid-Important-drain, the VDP is handed the NEW frame's mappings over
the OLD frame's tiles -- and because the drain stops at the FIRST entry that
does not fit rather than skipping it, a player whose DPLC was cut in half shows
some pieces from the new frame and some from the old. That is a jumble, it
lasts exactly one frame, and every existing drop instrument reads zero through
it.

Queue ORDER decides who loses. One `GameLoop` iteration
(engine/system/game_loop.emp:29) runs `VSync_Wait` -- where `PageIn_Process`
enqueues a 2048-byte page landing on Important -- BEFORE the state dispatch,
where `perform_dplc` enqueues the player's art on Important. The queue is FIFO
and `Drain_Budgeted_Queue` walks from the base, so the page landing is ahead of
the player and spends the budget first. The player's art is what gets deferred.

WHAT THIS TOOL PRINTS
=====================

  residual  = DMA_BUDGET_* - (plane drain charge + Critical charge)
  demand    = page landing + the resident cast's peak per-frame DPLC bytes
  deficit   = demand - residual        (positive means the drain WILL defer)

Every input is derived from source, never typed in:

  DMA_BUDGET_NTSC / _PAL, PLANE_BUFFER_SIZE, MAX_VDP_SPRITES,
  ART_STAGING_BUFFER_SIZE, TILE_SIZE   <- engine/system/constants.emp
  the four static Critical entry lengths <- engine/system/buffers.emp, read
      out of `move.w #dma_length(N), d3` in Init_Static_DMA_Entries
  per-frame DPLC byte totals             <- the shipped DPLC blobs, via
      tools/dplc_straddle.py's parser and subject table

A deficit today is NOT a build failure -- the engine ships with one and the
frames it needs to bite are rare. `--gate` pins the arithmetic instead: it
fails when any derived input MOVES without the baseline being re-cut, so the
next person to change a budget, a buffer size or the cast's art volume is told
what it did to this margin.

USAGE
    python3 tools/dma_defer_headroom.py                     # report
    python3 tools/dma_defer_headroom.py --gate              # pin check
    python3 tools/dma_defer_headroom.py --write-baseline    # re-cut the pin
    python3 tools/dma_defer_headroom.py --selftest          # red-first proof

EXIT CODES
    0  measured (and, under --gate, matched the baseline)
    1  --gate mismatch: an input moved
    3  UNMEASURABLE -- an input could not be read at all. Never silent, never 0.
"""

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(HERE))

import dplc_straddle as DS  # noqa: E402  -- parser + subject table, single-sourced

BASELINE = HERE / "dma_defer_headroom_baseline.json"

CONSTANTS_EMP = REPO / "engine" / "system" / "constants.emp"
BUFFERS_EMP = REPO / "engine" / "system" / "buffers.emp"
VBLANK_EMP = REPO / "engine" / "system" / "vblank.emp"
DMA_QUEUE_EMP = REPO / "engine" / "system" / "dma_queue.emp"


class Unmeasurable(Exception):
    """An input could not be read. Exit 3, never a zero and never a number."""


# --------------------------------------------------------------- source reads

#: `pub const NAME = <expr>`, where expr is integers, other constant names, and
#: `* + - ( )`. Several of the sizes this tool needs are DERIVED in
#: constants.emp (`ART_STAGING_BUFFER_SIZE = ART_POOL_PAGE_BYTES`, itself
#: `ART_POOL_PAGE_TILES * TILE_SIZE`), and resolving the chain is the whole
#: point -- retyping the leaf value here would put a second, rottable copy of
#: the number in the tree, which is the failure this tool exists to catch.
_CONST_RE = re.compile(
    r"^\s*pub\s+const\s+([A-Za-z_]\w*)\s*=\s*([^/\n]+?)\s*(?://.*)?$", re.M)
_TOKEN_OK = re.compile(r"^[\w\s$*+\-()]+$")


def _const(name, _seen=None):
    text = CONSTANTS_EMP.read_text()
    hits = [m for m in _CONST_RE.finditer(text) if m.group(1) == name]
    if len(hits) != 1:
        raise Unmeasurable(
            f"`pub const {name}` appears {len(hits)} times in "
            f"{CONSTANTS_EMP.relative_to(REPO)}, expected exactly 1")
    expr = hits[0].group(2).strip()
    _seen = (_seen or set()) | {name}
    if not _TOKEN_OK.match(expr):
        raise Unmeasurable(f"{name} = {expr!r} uses syntax this reader does not model")
    # $hex -> 0xhex, then substitute any bare names recursively.
    py = re.sub(r"\$([0-9A-Fa-f]+)", r"0x\1", expr)
    for ident in sorted(set(re.findall(r"[A-Za-z_]\w*", py)), key=len, reverse=True):
        if ident in _seen:
            raise Unmeasurable(f"constant cycle resolving {name} at {ident}")
        py = re.sub(rf"\b{ident}\b", str(_const(ident, _seen)), py)
    try:
        v = eval(py, {"__builtins__": {}}, {})       # noqa: S307 -- token-gated above
    except Exception as exc:                          # noqa: BLE001
        raise Unmeasurable(f"{name} = {expr!r} did not evaluate: {exc}") from exc
    if not isinstance(v, int):
        raise Unmeasurable(f"{name} evaluated to {v!r}, not an integer")
    return v


def static_critical_lengths():
    """The Critical queue's per-frame byte cost, out of Init_Static_DMA_Entries.

    Read from the `move.w #dma_length(N), d3` lines rather than retyped, so a
    length change lands here instead of rotting a comment. The SAT entry's 640
    is the boot default -- Render_Sprites re-patches it every frame to
    Sprites_Rendered*8 -- so 640 IS the worst case (MAX_VDP_SPRITES*8) and is
    checked against that below.
    """
    text = BUFFERS_EMP.read_text()
    lens = [int(m) for m in re.findall(r"move\.w\s+#dma_length\((\d+)\),\s*d3", text)]
    if len(lens) != 6:
        raise Unmeasurable(
            f"expected 6 `move.w #dma_length(N), d3` lines in "
            f"{BUFFERS_EMP.relative_to(REPO)}, found {len(lens)}: {lens}. "
            "Init_Static_DMA_Entries changed shape -- re-derive this reader "
            "before trusting any number below it."
        )
    pal = lens[0:4]
    if len(set(pal)) != 1:
        raise Unmeasurable(f"the four palette-line entries differ: {pal}")
    sat, hscroll = lens[4], lens[5]
    sprites_max = _const("MAX_VDP_SPRITES")
    if sat != sprites_max * 8:
        raise Unmeasurable(
            f"the SAT static entry is {sat} B but MAX_VDP_SPRITES*8 is "
            f"{sprites_max * 8} -- one of the two moved; the worst-case SAT "
            "charge below is derived from the pair agreeing."
        )
    return {"palette_line": pal[0], "palette_lines": 4, "sat": sat, "hscroll": hscroll}


def assert_ship_asymmetry():
    """The claim the whole report rests on: Critical is unbudgeted, Important is not.

    Spelling-pinned rather than assumed. If either side ever grows or loses a
    budget test this raises, because the arithmetic below would then be about a
    machine that no longer exists.
    """
    vb = VBLANK_EMP.read_text()
    dq = DMA_QUEUE_EMP.read_text()
    checks = [
        (vb, r"jbsr\s+Process_DMA_Critical",
         "VInt_Level no longer calls Process_DMA_Critical"),
        (vb, r"jbsr\s+Process_DMA_Important",
         "VInt_Level no longer calls Process_DMA_Important"),
        (vb, r"move\.w\s+\(DMA_Budget_Default\)\.w,\s*\(DMA_Budget_Remaining\)\.w",
         "VInt_Level no longer seeds the frame budget from DMA_Budget_Default"),
        (dq, r"jbra\s+Drain_Budgeted_Queue",
         "Process_DMA_Important no longer tail-calls Drain_Budgeted_Queue"),
        (dq, r"bmi\s+\.out_of_budget",
         "Drain_Budgeted_Queue no longer has the out-of-budget branch"),
    ]
    for text, pat, why in checks:
        if not re.search(pat, text):
            raise Unmeasurable(f"{why} (pattern {pat!r} not found)")
    # Process_DMA_Critical must NOT consult the budget -- that asymmetry is the defect.
    crit = re.search(
        r"pub proc Process_DMA_Critical.*?\n\}", dq, re.S)
    if crit is None:
        raise Unmeasurable("Process_DMA_Critical's body could not be delimited")
    if "DMA_Budget_Remaining" in crit.group(0):
        raise Unmeasurable(
            "Process_DMA_Critical now reads DMA_Budget_Remaining -- the "
            "unbudgeted-Critical premise of this report is DEAD; re-derive it."
        )
    return True


# ------------------------------------------------------------------- the model

def measure(lst_path):
    assert_ship_asymmetry()

    budget_ntsc = _const("DMA_BUDGET_NTSC")
    budget_pal = _const("DMA_BUDGET_PAL")
    plane = _const("PLANE_BUFFER_SIZE")
    staging = _const("ART_STAGING_BUFFER_SIZE")
    tile = _const("TILE_SIZE")

    crit = static_critical_lengths()
    critical_bytes = crit["palette_line"] * crit["palette_lines"] + crit["sat"] + crit["hscroll"]

    labels = DS.lst_labels(lst_path)
    subs = DS.load_subjects(labels)
    peaks = {}
    peak_frames = {}
    for s in subs:
        by_frame = [sum(c for _, c in ents) * tile for ents in s["frames"]]
        if not by_frame:
            raise Unmeasurable(f"{s['name']}: DPLC parsed to zero frames")
        peaks[s["name"]] = max(by_frame)
        peak_frames[s["name"]] = [i for i, b in enumerate(by_frame) if b == max(by_frame)]

    # The resident cast in the shipped game is ONE player. The two-player and
    # Tails-appendage rows are reported because dplc_straddle's own reserve model
    # counts them, and because they are the direction this margin gets worse in.
    solo = max(peaks["sonic"], peaks["knuckles"])
    duo = peaks["sonic"] + peaks["tails"] + peaks["tails_tail"]

    out = {}
    for region, budget in (("NTSC", budget_ntsc), ("PAL", budget_pal)):
        residual = budget - plane - critical_bytes
        out[region] = {
            "budget": budget,
            "charge_plane_max": plane,
            "charge_critical_max": critical_bytes,
            "residual": residual,
            "demand_solo": staging + solo,
            "demand_duo": staging + duo,
            "deficit_solo": staging + solo - residual,
            "deficit_duo": staging + duo - residual,
        }
    return {
        "constants": {
            "DMA_BUDGET_NTSC": budget_ntsc, "DMA_BUDGET_PAL": budget_pal,
            "PLANE_BUFFER_SIZE": plane, "ART_STAGING_BUFFER_SIZE": staging,
            "TILE_SIZE": tile, "MAX_VDP_SPRITES": _const("MAX_VDP_SPRITES"),
        },
        "critical_entry_bytes": crit,
        "critical_bytes_total": critical_bytes,
        "dplc_peak_bytes": peaks,
        "dplc_peak_frames": {k: [hex(i) for i in v] for k, v in peak_frames.items()},
        "regions": out,
    }


# -------------------------------------------------------------------- printing

def report(m, out=sys.stdout):
    p = lambda *a: print(*a, file=out)                                  # noqa: E731
    p("dma_defer_headroom -- Important-queue BYTE headroom per frame")
    p("")
    p("  charged before the Important drain (worst case):")
    p(f"    plane drain (Plane_Buffer_Ptr max)   {m['constants']['PLANE_BUFFER_SIZE']:6d} B")
    c = m["critical_entry_bytes"]
    p(f"    palette {c['palette_lines']} x {c['palette_line']} B"
      f"{'':<21}{c['palette_line'] * c['palette_lines']:6d} B")
    p(f"    SAT (MAX_VDP_SPRITES x 8){'':<12}{c['sat']:6d} B")
    p(f"    HScroll (always, parallax active){'':<4}{c['hscroll']:6d} B")
    p(f"    {'':<36}------")
    p(f"    Critical total{'':<23}{m['critical_bytes_total']:6d} B  (UNBUDGETED -- always ships)")
    p("")
    p("  wants the residual (Important, FIFO, page landing FIRST):")
    p(f"    PageIn staging landing{'':<15}{m['constants']['ART_STAGING_BUFFER_SIZE']:6d} B")
    for name, v in sorted(m["dplc_peak_bytes"].items()):
        frames = ",".join(m["dplc_peak_frames"][name][:4])
        p(f"    {name + ' peak DPLC frame':<37}{v:6d} B  (frames {frames})")
    p("")
    for region, r in m["regions"].items():
        p(f"  {region}: budget {r['budget']} - plane {r['charge_plane_max']} "
          f"- critical {r['charge_critical_max']} = residual {r['residual']} B")
        for tag in ("solo", "duo"):
            d = r[f"deficit_{tag}"]
            verdict = "DEFERS" if d > 0 else "fits"
            p(f"      {tag:4s}: demand {r['demand_' + tag]:6d} B  "
              f"deficit {d:+6d} B  -> {verdict}")
    p("")
    p("  A positive deficit means Drain_Budgeted_Queue reaches .out_of_budget")
    p("  while the SAT for the same frame has ALREADY shipped on Critical:")
    p("  one frame of new mappings over partly-old art, with every drop")
    p("  counter reading zero. See this file's header for the full chain.")
    p("")
    p("  WHAT THIS IS NOT. Every charge above is that rider's MAXIMUM, so the")
    p("  numbers describe an ENVELOPE, not a frame anybody observed. A frame")
    p("  reaches the deficit only when several riders peak together: the plane")
    p("  drain full, a page landing queued, the player on a peak DPLC frame.")
    p("  Whether that conjunction occurs in play is a RUNTIME question and this")
    p("  tool cannot answer it -- it can only say the window is open, and how")
    p("  wide. A negative deficit, by contrast, IS conclusive: the drain cannot")
    p("  defer, and this mechanism is ruled out for that region.")


# ----------------------------------------------------------------------- gate

def gate(m, out=sys.stdout):
    if not BASELINE.exists():
        raise Unmeasurable(
            f"no baseline at {BASELINE.relative_to(REPO)} -- run --write-baseline")
    want = json.loads(BASELINE.read_text())
    got = {"constants": m["constants"],
           "critical_entry_bytes": m["critical_entry_bytes"],
           "dplc_peak_bytes": m["dplc_peak_bytes"],
           "regions": m["regions"]}
    if got == want:
        print("dma_defer_headroom --gate: OK, every derived input matches the pin",
              file=out)
        return 0
    print("dma_defer_headroom --gate: FAILED -- a derived input moved.", file=out)
    _diff(want, got, out)
    print("", file=out)
    print("  If the move is intended, re-read this file's header (the deficit is "
          "the F7 mechanism), then re-cut with --write-baseline.", file=out)
    return 1


def _diff(want, got, out, path=""):
    for k in sorted(set(want) | set(got)):
        w, g = want.get(k, "<absent>"), got.get(k, "<absent>")
        here = f"{path}.{k}" if path else k
        if isinstance(w, dict) and isinstance(g, dict):
            _diff(w, g, out, here)
        elif w != g:
            print(f"    {here}: baseline {w} -> now {g}", file=out)


# ------------------------------------------------------------------- selftest

def selftest(lst_path, out=sys.stdout):
    """Red-first proof, run against THIS tree, restoring what it mutated.

    Three arms, each mutating a DIFFERENT class of input, because a gate that
    only notices one of its readers is a gate that is mostly asleep:
      A  a constant           (DMA_BUDGET_NTSC in constants.emp)
      B  a static DMA length  (the HScroll entry in buffers.emp)
      C  the premise pin      (Process_DMA_Critical gaining a budget read)
    Arm C must raise Unmeasurable, NOT merely fail the diff -- a dead premise
    is not a moved number.
    """
    arms = [
        ("A constant", CONSTANTS_EMP,
         "pub const DMA_BUDGET_NTSC = 6144",
         "pub const DMA_BUDGET_NTSC = 6145", "gate"),
        ("B static DMA length", BUFFERS_EMP,
         "move.w  #dma_length(896), d3",
         "move.w  #dma_length(892), d3", "gate"),
        ("C premise pin", DMA_QUEUE_EMP,
         "        movea.w DMA_Critical_Slot, a1           // (DMA_Critical_Slot).w",
         "        move.w  DMA_Budget_Remaining, d0        // premise-pin mutation\n"
         "        movea.w DMA_Critical_Slot, a1           // (DMA_Critical_Slot).w",
         "unmeasurable"),
    ]
    ok = True
    for name, path, old, new, expect in arms:
        text = path.read_text()
        if text.count(old) != 1:
            print(f"  {name}: UNMEASURABLE -- anchor appears "
                  f"{text.count(old)} times in {path.name}, not once", file=out)
            ok = False
            continue
        path.write_text(text.replace(old, new, 1))
        try:
            if expect == "unmeasurable":
                try:
                    measure(lst_path)
                except Unmeasurable as exc:
                    print(f"  {name}: RED as required -- {exc}", file=out)
                else:
                    print(f"  {name}: GREEN when it must be RED "
                          "-- the premise pin does not fire", file=out)
                    ok = False
            else:
                import io
                rc = gate(measure(lst_path), io.StringIO())
                if rc == 1:
                    print(f"  {name}: RED as required (gate rc=1)", file=out)
                else:
                    print(f"  {name}: GREEN when it must be RED (gate rc={rc})", file=out)
                    ok = False
        finally:
            path.write_text(text)
    # And green again on the restored tree -- a selftest that leaves the tree
    # red is indistinguishable from one that never restored it.
    import io
    rc = gate(measure(lst_path), io.StringIO())
    if rc != 0:
        print(f"  restore check: tree did NOT come back green (rc={rc})", file=out)
        ok = False
    else:
        print("  restore check: tree green again", file=out)
    return 0 if ok else 1


# --------------------------------------------------------------------- main

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--lst", default=str(REPO / "s4.debug.lst"))
    ap.add_argument("--gate", action="store_true")
    ap.add_argument("--write-baseline", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    try:
        if a.selftest:
            return selftest(a.lst)
        m = measure(a.lst)
        if a.write_baseline:
            BASELINE.write_text(json.dumps(
                {"constants": m["constants"],
                 "critical_entry_bytes": m["critical_entry_bytes"],
                 "dplc_peak_bytes": m["dplc_peak_bytes"],
                 "regions": m["regions"]}, indent=2, sort_keys=True) + "\n")
            print(f"baseline written to {BASELINE.relative_to(REPO)}")
            return 0
        report(m)
        if a.gate:
            return gate(m)
        return 0
    except (Unmeasurable, DS.Unmeasurable) as exc:
        print(f"dma_defer_headroom: UNMEASURABLE -- {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())
