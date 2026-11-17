#!/usr/bin/env python3
"""leg_survey — the 48-cell leg survey runner (Empyrean v2 step 0, B2/C-series, Task 6).

    python3 tools/leg_survey.py run  --out DIR [--only idle,run] [--rom-dir DIR]
    python3 tools/leg_survey.py summarise --out DIR

Every leg x shape x phase cell (8 x 2 x 3 = 48) goes through `leg_run --dma-probe`, one
subprocess per cell, with `rc` appended to DIR/manifest.jsonl. `summarise` judges the result files on disk
(never "the run finished"): a cell with no result file is DID NOT RUN, with the cell named. A
file is only believed when manifest.jsonl confirms this run wrote it (no manifest, no record,
or an rc that disagrees with the file -> FAILED), it matches its cell, and its provenance is one
aeon + oracle tuple across the whole survey with one ROM crc per leg x shape. Cell status:
    OK             `coverage.met` per `leg_drive.coverage` (idle and topspeed may be CAP+met;
                   the others need FINISHED), the DMA probe measured, and no DMA overrun
    STUCK          the leg's progress stalled
    DID NOT COVER  ran, but hit the cap or never met its coverage condition
    DID NOT RUN    no result file (a missing ROM/listing, a refused or crashed run, not yet run)
    FAILED         a result that is unreadable, lacks provenance, mismatches its cell or the
                   survey's provenance, disagrees with the manifest, overran, or whose DMA probe
                   could not measure
The rule-4 verdict per leg x shape is `leg_correction.classify` on the WORST last-DMA end over
the 3 phases against the VBlank window (VInt line -> DMA_END_LIMIT_LINE); anything not derivable
is `n/a (unmeasurable)`, never FITS.

Exit: 0 all 48 OK and every leg x shape rule-4 verdict FITS; 2 any DID NOT RUN; 1 otherwise
(any cell not OK, or a verdict that is OVER / NEEDS-WITNESS / WITNESS-DISAGREES / n/a).
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
AEON = TOOLS.parent
sys.path.insert(0, str(TOOLS))
import leg_correction as lc  # noqa: E402
import leg_drive as ld  # noqa: E402
import leg_provenance as lp  # noqa: E402

LEGS = ("idle", "run", "topspeed", "diagfall", "spindash", "objheavy", "sidekick", "stream")
SHAPES = ("release", "debug")
PHASES = (0, 1, 2)
STATUSES = ("OK", "STUCK", "DID NOT COVER", "DID NOT RUN", "FAILED")

_STEM = {"idle": "s4", "run": "s4", "topspeed": "s4", "diagfall": "s4", "spindash": "s4",
         "objheavy": "s4.stressobj", "sidekick": "s4.sidekick", "stream": "s4.s2clip"}

#: (leg, shape) -> ROM file name. The listing is the same stem with `.lst`.
LEG_ROM = {(leg, shape): _STEM[leg] + (".debug" if shape == "debug" else "") + ".bin"
           for leg in LEGS for shape in SHAPES}

#: The leg_run policy each survey leg drives with. The stress legs drive `run`.
LEG_POLICY = {leg: (leg if leg in ("idle", "run", "topspeed", "diagfall", "spindash") else "run")
              for leg in LEGS}

#: The `leg_run --leg` each survey leg is run as (and the `leg` its result carries). A stress
#: leg leg_run knows by name (objheavy, Task 8; sidekick, Task 9) drives LEG_POLICY's policy
#: under its OWN coverage rule; one it does not know yet (stream) still runs as its policy.
LEG_RUN_LEG = {leg: (leg if leg in ld.POLICIES else LEG_POLICY[leg]) for leg in LEGS}

#: The stream leg's act (v2 C4, owner-proxy ruling Q2 2026-11-17): the S2CLIP clip that EVICTS
#: (C1 note §3.1: 3 evictions, then STUCK at x 2230). It stays the `stream` cell of the 48 and
#: is graded on leg_drive.stream_coverage; its STUCK is reported, never tuned away.
STREAM_CLIP = "s2_woven"
#: The finishing companion: the S2CLIP clip that FINISHES but never evicts (C1 note §3.1). It
#: is recorded alongside, OUTSIDE the 48 (its own cells, directory and manifest), so its
#: FINISHED can never make the stream cell read OK.
STREAM_COMPANION_CLIP = "s2_ehz_cpz"
COMPANION = "stream_companion"
#: The clip each clip-built cell must come from (provenance.rom.rebake.clip).
LEG_CLIP = {"stream": STREAM_CLIP}


def companion_cells() -> list[tuple[str, str, int]]:
    return [(COMPANION, shape, ph) for shape in SHAPES for ph in PHASES]


def companion_dir(out_dir: Path) -> Path:
    return Path(out_dir) / "companion"


def companion_path(out_dir: Path, shape: str, phase: int) -> Path:
    """The companion runs `leg_run --leg stream` on the same ROM name as the stream cell (one
    s4.s2clip[.debug].bin per shape can exist: check_pair pins a ROM to the aeon root), so its
    results live in their own directory."""
    stem = Path(LEG_ROM[("stream", shape)]).stem
    return companion_dir(out_dir) / f"{stem}_stream_p{phase}.json"


def rom_clip(rom: Path) -> str | None:
    """The clip an S2CLIP ROM was built from, as its build's measurement record names it
    (`<rom stem>.clip_anchors.json`, tools/clip_anchors.py). A HINT for refusing a run early;
    the proof is the provenance re-bake (leg_provenance, SHAPE_REBAKES `s4.s2clip`)."""
    try:
        return json.loads(Path(rom).with_suffix(".clip_anchors.json").read_text()).get("clip")
    except (OSError, ValueError, AttributeError):
        return None


def expected_matrix() -> list[tuple[str, str, int]]:
    return [(leg, shape, ph) for leg in LEGS for shape in SHAPES for ph in PHASES]


def result_path(out_dir: Path, leg: str, shape: str, phase: int) -> Path:
    """Where leg_run writes this cell: `<rom-stem>_<leg_run leg>_p<phase>.json`."""
    stem = Path(LEG_ROM[(leg, shape)]).stem
    return Path(out_dir) / f"{stem}_{LEG_RUN_LEG[leg]}_p{phase}.json"


# ---- run ---------------------------------------------------------------------------------

def _manifest(out_dir: Path) -> dict | None:
    """Latest manifest record per (leg, shape, phase); None when there is no manifest."""
    mp = Path(out_dir) / "manifest.jsonl"
    if not mp.is_file():
        return None
    recs = {}
    for ln in mp.read_text().splitlines():
        if ln.strip():
            try:
                x = json.loads(ln)
                recs[(x["leg"], x["shape"], x["phase"])] = x
            except (ValueError, KeyError):
                continue
    return recs


def _run_cell(cmd, timeout) -> tuple[int | None, str | None]:
    """One cell in its own session; on timeout the WHOLE group (leg_run + its private
    oracle-aether) is killed, so no orphan emulator outlives the cell."""
    try:
        p = subprocess.Popen(cmd, start_new_session=True)
    except OSError as e:
        return None, f"could not start leg_run: {type(e).__name__}: {e}"
    try:
        return p.wait(timeout=timeout), None
    except subprocess.TimeoutExpired:
        try:
            os.killpg(p.pid, signal.SIGKILL)
        except OSError:
            pass
        p.wait()
        return None, f"timeout after {timeout}s (process group killed; not a result)"


def run(out_dir, only=None, rom_dir=None, timeout=600, resume=False,
        companion=False) -> list[dict]:
    """One `leg_run --dma-probe` subprocess per cell; a manifest line per cell. A missing ROM or
    listing is recorded loudly and the cell is left without a result (DID NOT RUN). A non-empty
    out_dir is refused (stale results must not pass as this run's) unless `resume`, which
    re-runs only the cells without a good (rc 0) manifest record; summarise() still applies
    every consistency check to the resumed directory.

    `companion` runs the 6 stream-companion cells instead (STREAM_COMPANION_CLIP's ROM must be
    the s4.s2clip pair on disk; results and manifest under companion_dir). A clip-built cell
    whose ROM names another clip is DID NOT RUN, naming both, before anything is spawned."""
    out_dir, rom_dir = Path(out_dir), Path(rom_dir or AEON)
    if companion:
        return _run_cells(companion_dir(out_dir), companion_cells(), rom_dir, timeout, resume,
                          check_empty=out_dir.exists() and companion_dir(out_dir).exists())
    unknown = [o for o in (only or []) if o not in LEGS]
    if unknown:
        raise SystemExit(f"leg_survey: unknown leg(s) {unknown}; legs are {list(LEGS)}")
    if out_dir.exists() and any(p for p in out_dir.iterdir() if p != companion_dir(out_dir)) \
            and not resume:
        raise SystemExit(f"leg_survey: {out_dir} is not empty; stale results would pass as this "
                         f"run's. Use a fresh --out, or --resume to continue it.")
    cells = [c for c in expected_matrix() if not only or c[0] in only]
    return _run_cells(out_dir, cells, rom_dir, timeout, resume)


def _cell_rom(leg: str, shape: str) -> str:
    return LEG_ROM[("stream" if leg == COMPANION else leg, shape)]


def _cell_clip(leg: str) -> str | None:
    return STREAM_COMPANION_CLIP if leg == COMPANION else LEG_CLIP.get(leg)


def _cell_path(out_dir: Path, leg: str, shape: str, ph: int) -> Path:
    """`out_dir` is the companion directory itself for a companion cell."""
    if leg == COMPANION:
        stem = Path(LEG_ROM[("stream", shape)]).stem
        return Path(out_dir) / f"{stem}_stream_p{ph}.json"
    return result_path(out_dir, leg, shape, ph)


def _run_cells(out_dir, cells, rom_dir, timeout, resume, check_empty=False) -> list[dict]:
    if check_empty and any(out_dir.iterdir()) and not resume:
        raise SystemExit(f"leg_survey: {out_dir} is not empty; stale results would pass as this "
                         f"run's. Use --resume to continue it.")
    out_dir.mkdir(parents=True, exist_ok=True)
    prior = (_manifest(out_dir) or {}) if resume else {}
    done = []
    for leg, shape, ph in cells:
        old = prior.get((leg, shape, ph))
        if old and old.get("rc") == 0 and _cell_path(out_dir, leg, shape, ph).is_file():
            continue
        rom = rom_dir / _cell_rom(leg, shape)
        lst = rom.with_suffix(".lst")
        rec = {"leg": leg, "shape": shape, "phase": ph, "rom": rom.name}
        miss = [p.name for p in (rom, lst) if not p.is_file()]
        want, got = _cell_clip(leg), rom_clip(rom)
        if miss:
            rec.update(rc=None, note=f"DID NOT RUN: {', '.join(miss)} missing in {rom_dir}")
        elif want is not None and got != want:
            rec.update(rc=None, note=(
                f"DID NOT RUN: {rom.name} was built from clip {got!r} (its "
                f"{rom.with_suffix('.clip_anchors.json').name}), this cell needs {want!r}: "
                f"rebuild with `{'DEBUG=1 ' if shape == 'debug' else ''}S2CLIP={want} "
                f"./build.sh`"))
        if "note" in rec:
            print(f"leg_survey: {leg}/{shape}/p{ph}: {rec['note']}", file=sys.stderr)
        else:
            cmd = [sys.executable, str(TOOLS / "leg_run.py"), "--rom", str(rom), "--lst",
                   str(lst), "--leg", "stream" if leg == COMPANION else LEG_RUN_LEG[leg],
                   "--phase", str(ph), "--out", str(out_dir), "--dma-probe"]
            rec["rc"], note = _run_cell(cmd, timeout)
            if note:
                rec["note"] = note
                print(f"leg_survey: {leg}/{shape}/p{ph}: {note}", file=sys.stderr)
        with open(out_dir / "manifest.jsonl", "a") as f:
            f.write(json.dumps(rec) + "\n")
        done.append(rec)
    return done


# ---- summarise ---------------------------------------------------------------------------

@dataclass
class Row:
    leg: str
    shape: str
    phase: int
    status: str
    detail: str
    lag_frames: int | None = None
    dma: dict | None = None
    drive_status: str | None = None   # the result file's own `status` (FINISHED / STUCK / ...)
    stream: dict | None = None        # a stream result's coverage.got (the streaming counts)


@dataclass
class Summary:
    rows: list
    counts: dict
    prov: dict | None = None          # {shape: tuple-dict, (leg, shape): crc} as printed in the header
    groups: dict | None = None        # {(leg, shape): (end_text, verdict, all_ok)}
    companion: list = field(default_factory=list)   # the 6 cells OUTSIDE the 48 (STREAM_COMPANION_CLIP)

    @property
    def ran(self) -> int:
        return len(self.rows) - self.counts["DID NOT RUN"]


def _judge(path: Path, cell=None, clip=None) -> tuple[str, str, dict | None, int | None]:
    if not path.is_file():
        return "DID NOT RUN", f"no result file {path.name}", None, None
    try:
        r = json.loads(path.read_text())
    except (OSError, ValueError) as e:
        return "FAILED", f"unreadable result {path.name}: {e}", None, None
    return _judge_loaded(r, path, cell, clip)


def stream_note(cov: dict) -> str:
    """The streaming counts of a stream result, as the annotation a STUCK or uncovered cell
    carries (MEASURED by leg_run's breakpoints and RAM reads)."""
    g = (cov or {}).get("got")
    if not isinstance(g, dict) or "decode_calls" not in g:
        return ""
    return (f"streaming (MEASURED, Oracle): decode calls {g['decode_calls']}, landings "
            f"{g['landings']}, evictions {g['evictions']} (PickVictim {g['pick_victim_calls']}, "
            f"no-victim {g['no_victim']}), Direct_Map end {g['direct_map_end']}, streamed="
            f"{g['streamed']}")


def _judge_loaded(r, path, cell=None, clip=None):
    if not isinstance(r, dict):
        return "FAILED", f"{path.name} is not a result object", None, None
    try:
        lp.require_provenance(r["provenance"])
    except Exception as e:  # MissingProvenance, KeyError, TypeError: all the same finding
        return "FAILED", f"no provenance: {type(e).__name__}: {e}", None, None
    if cell is not None:
        leg, shape, ph = cell
        got = {"leg": r.get("leg"), "phase": r.get("phase"),
               "provenance.rom.rom": r["provenance"]["rom"].get("rom")}
        want = {"leg": LEG_RUN_LEG[leg], "phase": ph, "provenance.rom.rom": LEG_ROM[(leg, shape)]}
        for k in want:
            if got[k] != want[k]:
                return ("FAILED", f"result does not match its cell: {k} is {got[k]!r}, "
                        f"expected {want[k]!r}", None, None)
        clip = clip or LEG_CLIP.get(leg)
    if clip is not None:
        rb = r["provenance"]["rom"].get("rebake")
        had = rb.get("clip") if isinstance(rb, dict) else None
        if had != clip:
            return ("FAILED", f"result's ROM is clip {had!r} (provenance.rom.rebake.clip), this "
                    f"cell needs clip {clip!r}", None, None)
    lag = (r.get("lag") or {}).get("frames")
    dma = r.get("dma")
    st = r.get("status")
    cov = r.get("coverage") or {}
    note = stream_note(cov) if r.get("leg") == "stream" else ""
    if note == "" and r.get("leg") == "stream" and isinstance(cov.get("got"), dict) \
            and cov["got"].get("unmeasurable"):
        return "FAILED", f"coverage {cov['got']['unmeasurable']}", dma, lag
    if st == "STUCK":
        return "STUCK", str(r.get("reason") or "progress stalled") + (
            f"; {note}" if note else ""), dma, lag
    if st == "FAILED":
        return "FAILED", str(r.get("reason") or "leg driver FAILED"), dma, lag
    # coverage.met is the leg's own rule (idle is a fixed-tick leg: CAP + met is its OK)
    if cov.get("met") is not True:
        if note:
            return "DID NOT COVER", f"status {st}, coverage not met ({cov.get('rule')}); {note}", \
                dma, lag
        return ("DID NOT COVER", f"status {st}, coverage met={cov.get('met')} "
                f"(got={cov.get('got')} need={cov.get('need')})", dma, lag)
    if not isinstance(dma, dict) or dma.get("status") not in ("MEASURED",) or dma.get(
            "unmeasurable"):
        why = dma.get("unmeasurable") if isinstance(dma, dict) else None
        return "FAILED", f"DMA probe did not measure: {why or dma}", dma, lag
    ov = dma.get("overruns")
    if not isinstance(ov, list):
        return "FAILED", "DMA probe result has no `overruns` list", dma, lag
    if ov:
        lim = (dma.get("limit") or {}).get("line")
        return "FAILED", f"DMA overrun: {len(ov)} DMA(s) end past line {lim} + 0", dma, lag
    return "OK", "", dma, lag


def _tuple_of(r: dict, shape: str) -> dict:
    pv = r["provenance"]
    return {"aeon.commit": pv["aeon"]["commit"], "aeon.dirty": pv["aeon"]["dirty"],
            "oracle.server_build_id": pv["oracle"]["server_build_id"],
            "oracle.source": pv["oracle"]["source"], "oracle.dirty": pv["oracle"]["dirty"],
            "oracle.sha256": pv["oracle"]["sha256"]}


def _judge_cells(cells, man, path_of, judge_of):
    """Rows for `cells`, each believed only when the manifest confirms this run wrote it."""
    rows, loaded = [], {}
    for leg, shape, ph in cells:
        path = path_of(leg, shape, ph)
        s, d, dma, lag = judge_of(path, leg, shape, ph)
        j = None
        if s != "DID NOT RUN":
            try:
                j = loaded[(leg, shape, ph)] = json.loads(path.read_text())
            except (OSError, ValueError):
                pass
            if man is None:
                s, d = "FAILED", ("no manifest: cannot confirm this run wrote it (result file "
                                  f"was {s})")
            elif s != "FAILED":
                rec = man.get((leg, shape, ph))
                rc = None if rec is None else rec.get("rc")
                if rec is None or rc not in (0, 1) or (rc == 0 and s != "OK") or (
                        rc == 1 and s == "OK"):
                    s, d = "FAILED", (f"rc disagrees with file: manifest "
                                      f"{'has no record' if rec is None else 'rc=' + repr(rc)}, "
                                      f"result file is {s}" + (f" ({d})" if d else ""))
        g = ((j or {}).get("coverage") or {}).get("got") if isinstance(j, dict) else None
        rows.append(Row(leg, shape, ph, s, d, lag, dma,
                        drive_status=j.get("status") if isinstance(j, dict) else None,
                        stream=g if isinstance(g, dict) and "decode_calls" in g else None))
    return rows, loaded


def summarise(out_dir) -> Summary:
    out_dir = Path(out_dir)
    man = _manifest(out_dir)
    rows, loaded = _judge_cells(
        expected_matrix(), man, lambda l, sh, ph: result_path(out_dir, l, sh, ph),
        lambda p, l, sh, ph: _judge(p, (l, sh, ph)))
    # The companion: the same rule and checks, its own clip, directory and manifest.
    cdir = companion_dir(out_dir)
    comp, comp_loaded = _judge_cells(
        companion_cells(), _manifest(cdir) if cdir.is_dir() else None,
        lambda l, sh, ph: companion_path(out_dir, sh, ph),
        lambda p, l, sh, ph: _judge(p, ("stream", sh, ph), clip=STREAM_COMPANION_CLIP))
    # ONE aeon + oracle tuple across the whole survey (both shapes come from one checkout and
    # one pinned oracle; G0 is judged on the survey as a whole), one ROM crc32 per leg x shape.
    # The first readable cell sets the reference; every deviant is FAILED naming the field and
    # both values.
    ref, crc = {}, {}
    every = [(r, loaded) for r in rows] + [(r, comp_loaded) for r in comp]
    for r, src in every:
        j = src.get((r.leg, r.shape, r.phase))
        if j is None or r.status == "DID NOT RUN" or "no provenance" in r.detail:
            continue
        try:
            t = _tuple_of(j, r.shape)
            c = j["provenance"]["rom"]["crc32"]
        except (KeyError, TypeError):
            continue
        bad = None
        if ref:
            for k, v in t.items():
                if ref["t"][k] != v:
                    bad = (f"provenance mismatch: {k} is {v!r} here but {ref['t'][k]!r} in "
                           f"{ref['cell']} (one tuple across the survey)")
                    break
        else:
            ref = {"t": t, "cell": f"{r.leg}/{r.shape}/p{r.phase}"}
        if bad is None:
            if (r.leg, r.shape) in crc and crc[(r.leg, r.shape)] != c:
                bad = (f"provenance mismatch: rom.crc32 is {c!r}, {r.leg}/{r.shape} "
                       f"reference {crc[(r.leg, r.shape)]!r}")
            else:
                crc.setdefault((r.leg, r.shape), c)
        if bad:
            r.status, r.detail = "FAILED", bad
    prov = {"survey": ref.get("t", {}), "crc": {f"{l}/{sh}": c for (l, sh), c in crc.items()}}
    counts = {s: 0 for s in STATUSES}
    counts.update(Counter(r.status for r in rows))
    ccounts = Counter(r.status for r in comp)
    groups = {}
    for leg in LEGS:
        for shape in SHAPES:
            rs = [r for r in rows if r.leg == leg and r.shape == shape]
            end, ver = dma_verdict(rs)
            groups[(leg, shape)] = (end, ver, all(r.status == "OK" for r in rs))
    for shape in SHAPES:
        rs = [r for r in comp if r.shape == shape]
        end, ver = dma_verdict(rs)
        groups[(COMPANION, shape)] = (end, ver, all(r.status == "OK" for r in rs))
    summ = Summary(rows, counts, prov, groups, comp)
    summ.companion_counts = {s: ccounts.get(s, 0) for s in STATUSES}
    return summ


def sustained(summ: Summary) -> tuple[str, str]:
    """Did any ONE run stream (decode >= 1 and evictions >= 1) and FINISH? Over the stream
    cells and the companion. (verdict, why)."""
    runs = [r for r in summ.rows if r.leg == "stream"] + list(summ.companion)
    seen = [r for r in runs if r.stream is not None]
    if not seen:
        return "DID NOT RUN", "no stream or companion result carries streaming counts"
    both = [r for r in seen if r.stream["streamed"] and r.drive_status == "FINISHED"
            and r.status == "OK"]
    if both:
        return "COVERED", f"{both[0].leg}/{both[0].shape}/p{both[0].phase} streamed and finished"
    ev = sorted({f"{'stream (' + STREAM_CLIP + ')' if r.leg == 'stream' else 'companion (' + STREAM_COMPANION_CLIP + ')'}"
                 for r in seen if r.stream["streamed"]})
    fin = sorted({f"{'stream (' + STREAM_CLIP + ')' if r.leg == 'stream' else 'companion (' + STREAM_COMPANION_CLIP + ')'}"
                  for r in seen if r.drive_status == "FINISHED"})
    return "DID NOT COVER", (f"NO single run both evicts and finishes: evicting runs: "
                             f"{', '.join(ev) or 'none'}; finishing runs: {', '.join(fin) or 'none'}")


def dma_verdict(rows: list) -> tuple[str, str]:
    """(worst last-DMA end, rule-4 verdict) over one leg x shape's phase rows. Anything we cannot
    derive from all 3 phases' probe results is `n/a (unmeasurable)`."""
    na = ("n/a", "n/a (unmeasurable)")
    worst, nodma_all = None, True
    for r in rows:
        d = r.dma
        if not isinstance(d, dict) or d.get("status") != "MEASURED" or d.get("unmeasurable"):
            return na
        w, entry = d.get("worst_end"), d.get("entry_line_expected")
        if not isinstance(w, dict) or not isinstance(entry, int) or entry <= 0:
            return na
        if w.get("status") == "NO DMA":
            end = (entry, 0)
        elif w.get("status") == "MEASURED" and isinstance(w.get("line"), int) \
                and isinstance(w.get("off"), int):
            end = (w["line"], w["off"])
            nodma_all = False
        else:
            return na
        worst = max(worst or (entry, 0, entry), (*end, entry))
    if worst is None:
        return na
    line, off, entry = worst
    mclk = (line - entry) * lc.MCLK_PER_LINE + off          # since the VBlank_Handler entry
    budget = (lc.DMA_END_LIMIT_LINE - entry) * lc.MCLK_PER_LINE // 7
    if budget <= 0:
        return na
    elapsed = mclk // 7
    # sound_playing=True: the upper-bound Z80 stall, the conservative choice (never FITS by omission)
    v = lc.classify(budget - elapsed, budget, elapsed, True)
    if nodma_all:
        return "NO DMA in any phase (no end measured)", v
    return f"line {line} + {off} mclk", v


def render(out_dir, summ: Summary) -> str:
    L = ["# Leg survey summary", "",
         f"ran {summ.ran} of {len(summ.rows)}  |  " +
         "  ".join(f"{k}: {summ.counts[k]}" for k in STATUSES), "",
         "## Provenance (one aeon + oracle tuple for the whole survey; every cell must match)", ""]
    t = (summ.prov or {}).get("survey", {})
    if t:
        L.append("- survey: " + ", ".join(f"{k}={v}" for k, v in t.items()))
    for k, c in (summ.prov or {}).get("crc", {}).items():
        L.append(f"- rom crc32 {k}: {c}")
    if not t:
        L.append("- none (no readable result)")
    L += ["", "| leg | shape | cells (p0 p1 p2) | lag frames min-max, MEASURED (Oracle) | "
          "worst last-DMA end, MEASURED (Oracle) | rule-4 verdict, ESTIMATED: classify, "
          "sound_playing=True (upper-bound Z80 stall), no witness |", "|---|---|---|---|---|---|"]
    for leg in LEGS:
        for shape in SHAPES:
            rs = [r for r in summ.rows if r.leg == leg and r.shape == shape]
            lags = [r.lag_frames for r in rs if isinstance(r.lag_frames, int)]
            lagtxt = f"{min(lags)}-{max(lags)}" if lags and len(lags) == len(rs) else (
                f"{min(lags)}-{max(lags)} (partial)" if lags else "n/a")
            end, ver, _ = summ.groups[(leg, shape)]
            if end.startswith("NO DMA"):
                ver = f"{ver} (vacuous: no DMA seen)"
            L.append(f"| {leg} | {shape} | {' '.join(r.status for r in rs)} | {lagtxt} | {end} "
                     f"| {ver} |")
    L += ["", "## Stream leg: streaming counts (MEASURED, Oracle: breakpoint entries and RAM "
          "reads over the drive window)", "",
          f"`stream` is clip `{STREAM_CLIP}` (one of the 48). The companion is clip "
          f"`{STREAM_COMPANION_CLIP}`, recorded **outside the 48**: its cells are not counted "
          f"above and its FINISHED never makes the stream cell OK.", "",
          "| run | shape | p | cell | drive | decode calls | landings | evictions | "
          "Direct_Map end | lag frames | worst last-DMA end |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in [r for r in summ.rows if r.leg == "stream"] + list(summ.companion):
        g = r.stream or {}
        w = (r.dma or {}).get("worst_end") if isinstance(r.dma, dict) else None
        wt = (f"line {w['line']} + {w['off']}" if isinstance(w, dict) and w.get("status") ==
              "MEASURED" else (w or {}).get("status", "n/a") if isinstance(w, dict) else "n/a")
        name = (f"stream ({STREAM_CLIP})" if r.leg == "stream"
                else f"companion ({STREAM_COMPANION_CLIP}), outside the 48")
        L.append(f"| {name} | {r.shape} | {r.phase} | {r.status} | {r.drive_status or 'n/a'} | "
                 f"{g.get('decode_calls', 'n/a')} | {g.get('landings', 'n/a')} | "
                 f"{g.get('evictions', 'n/a')} | {g.get('direct_map_end', 'n/a')} | "
                 f"{r.lag_frames if r.lag_frames is not None else 'n/a'} | {wt} |")
    v, why = sustained(summ)
    L += ["", f"- streaming sustained to the end of an act: **{v}** ({why})"]
    cc = getattr(summ, "companion_counts", {})
    L.append("- companion cells (outside the 48): " +
             "  ".join(f"{k}: {cc.get(k, 0)}" for k in STATUSES))
    bad = [r for r in summ.rows if r.status != "OK"]
    L += ["", "## Cells not OK", ""]
    L += [f"- {r.leg}/{r.shape}/p{r.phase}: **{r.status}** {r.detail}" for r in bad] or ["- none"]
    L += ["", "## Companion cells (outside the 48)", ""]
    L += [f"- {r.leg}/{r.shape}/p{r.phase}: **{r.status}** {r.detail}" for r in summ.companion]
    L += ["", f"ran {summ.ran} of {len(summ.rows)}", ""]
    return "\n".join(L)


def exit_code(summ: Summary) -> int:
    """2 any DID NOT RUN; 1 any cell not OK, or any leg x shape whose rule-4 verdict is not FITS
    (OVER, NEEDS-WITNESS, WITNESS-DISAGREES, or n/a on a row whose cells are all OK); else 0."""
    cc = getattr(summ, "companion_counts", {})
    if summ.counts["DID NOT RUN"] or cc.get("DID NOT RUN"):
        return 2
    if cc.get("FAILED"):
        return 1
    if summ.counts["OK"] != len(summ.rows):
        return 1
    if any(ver != "FITS" for _end, ver, ok in (summ.groups or {}).values() if ok):
        return 1
    return 0


def write_summary(out_dir) -> tuple[Summary, int]:
    summ = summarise(out_dir)
    text = render(out_dir, summ)
    (Path(out_dir) / "summary.md").write_text(text)
    for r in list(summ.rows) + list(summ.companion):
        if r.status == "DID NOT RUN":
            print(f"DID NOT RUN: {r.leg}/{r.shape}/p{r.phase} ({r.detail})", file=sys.stderr)
    print(text)
    return summ, exit_code(summ)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("cmd", choices=("run", "summarise"))
    ap.add_argument("--out", required=True)
    ap.add_argument("--only", default=None, help="comma-separated legs")
    ap.add_argument("--rom-dir", default=None)
    ap.add_argument("--companion", action="store_true",
                    help=f"run the 6 stream-companion cells (clip {STREAM_COMPANION_CLIP}, "
                         f"outside the 48) into <out>/companion")
    ap.add_argument("--resume", action="store_true",
                    help="continue a non-empty --out (re-runs cells without an rc 0 record)")
    a = ap.parse_args(argv)
    if a.cmd == "run":
        run(a.out, a.only.split(",") if a.only else None, a.rom_dir, resume=a.resume,
            companion=a.companion)
    return write_summary(a.out)[1]


if __name__ == "__main__":
    sys.exit(main())
