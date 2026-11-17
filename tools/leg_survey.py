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
from dataclasses import dataclass
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
#: leg leg_run knows by name (objheavy, Task 8) drives LEG_POLICY's policy under its OWN
#: coverage rule; one it does not know yet (sidekick, stream) still runs as its policy.
LEG_RUN_LEG = {leg: (leg if leg in ld.POLICIES else LEG_POLICY[leg]) for leg in LEGS}


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


def run(out_dir, only=None, rom_dir=None, timeout=600, resume=False) -> list[dict]:
    """One `leg_run --dma-probe` subprocess per cell; a manifest line per cell. A missing ROM or
    listing is recorded loudly and the cell is left without a result (DID NOT RUN). A non-empty
    out_dir is refused (stale results must not pass as this run's) unless `resume`, which
    re-runs only the cells without a good (rc 0) manifest record; summarise() still applies
    every consistency check to the resumed directory."""
    out_dir, rom_dir = Path(out_dir), Path(rom_dir or AEON)
    unknown = [o for o in (only or []) if o not in LEGS]
    if unknown:
        raise SystemExit(f"leg_survey: unknown leg(s) {unknown}; legs are {list(LEGS)}")
    if out_dir.exists() and any(out_dir.iterdir()) and not resume:
        raise SystemExit(f"leg_survey: {out_dir} is not empty; stale results would pass as this "
                         f"run's. Use a fresh --out, or --resume to continue it.")
    out_dir.mkdir(parents=True, exist_ok=True)
    prior = (_manifest(out_dir) or {}) if resume else {}
    done = []
    for leg, shape, ph in expected_matrix():
        if only and leg not in only:
            continue
        old = prior.get((leg, shape, ph))
        if old and old.get("rc") == 0 and result_path(out_dir, leg, shape, ph).is_file():
            continue
        rom = rom_dir / LEG_ROM[(leg, shape)]
        lst = rom.with_suffix(".lst")
        rec = {"leg": leg, "shape": shape, "phase": ph, "rom": rom.name}
        miss = [p.name for p in (rom, lst) if not p.is_file()]
        if miss:
            rec.update(rc=None, note=f"DID NOT RUN: {', '.join(miss)} missing in {rom_dir}")
            print(f"leg_survey: {leg}/{shape}/p{ph}: {rec['note']}", file=sys.stderr)
        else:
            cmd = [sys.executable, str(TOOLS / "leg_run.py"), "--rom", str(rom), "--lst",
                   str(lst), "--leg", LEG_RUN_LEG[leg], "--phase", str(ph), "--out",
                   str(out_dir), "--dma-probe"]
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


@dataclass
class Summary:
    rows: list
    counts: dict
    prov: dict | None = None          # {shape: tuple-dict, (leg, shape): crc} as printed in the header
    groups: dict | None = None        # {(leg, shape): (end_text, verdict, all_ok)}

    @property
    def ran(self) -> int:
        return len(self.rows) - self.counts["DID NOT RUN"]


def _judge(path: Path, cell=None) -> tuple[str, str, dict | None, int | None]:
    if not path.is_file():
        return "DID NOT RUN", f"no result file {path.name}", None, None
    try:
        r = json.loads(path.read_text())
    except (OSError, ValueError) as e:
        return "FAILED", f"unreadable result {path.name}: {e}", None, None
    return _judge_loaded(r, path, cell)


def _judge_loaded(r, path, cell=None):
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
    lag = (r.get("lag") or {}).get("frames")
    dma = r.get("dma")
    st = r.get("status")
    cov = r.get("coverage") or {}
    if st == "STUCK":
        return "STUCK", str(r.get("reason") or "progress stalled"), dma, lag
    if st == "FAILED":
        return "FAILED", str(r.get("reason") or "leg driver FAILED"), dma, lag
    # coverage.met is the leg's own rule (idle is a fixed-tick leg: CAP + met is its OK)
    if cov.get("met") is not True:
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


def summarise(out_dir) -> Summary:
    out_dir = Path(out_dir)
    man = _manifest(out_dir)
    rows, loaded = [], {}
    for leg, shape, ph in expected_matrix():
        path = result_path(out_dir, leg, shape, ph)
        s, d, dma, lag = _judge(path, (leg, shape, ph))
        if s != "DID NOT RUN":
            try:
                loaded[(leg, shape, ph)] = json.loads(path.read_text())
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
        rows.append(Row(leg, shape, ph, s, d, lag, dma))
    # ONE aeon + oracle tuple across the whole survey (both shapes come from one checkout and
    # one pinned oracle; G0 is judged on the survey as a whole), one ROM crc32 per leg x shape.
    # The first readable cell sets the reference; every deviant is FAILED naming the field and
    # both values.
    ref, crc = {}, {}
    for r in rows:
        j = loaded.get((r.leg, r.shape, r.phase))
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
    groups = {}
    for leg in LEGS:
        for shape in SHAPES:
            rs = [r for r in rows if r.leg == leg and r.shape == shape]
            end, ver = dma_verdict(rs)
            groups[(leg, shape)] = (end, ver, all(r.status == "OK" for r in rs))
    return Summary(rows, counts, prov, groups)


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
    bad = [r for r in summ.rows if r.status != "OK"]
    L += ["", "## Cells not OK", ""]
    L += [f"- {r.leg}/{r.shape}/p{r.phase}: **{r.status}** {r.detail}" for r in bad] or ["- none"]
    L += ["", f"ran {summ.ran} of {len(summ.rows)}", ""]
    return "\n".join(L)


def exit_code(summ: Summary) -> int:
    """2 any DID NOT RUN; 1 any cell not OK, or any leg x shape whose rule-4 verdict is not FITS
    (OVER, NEEDS-WITNESS, WITNESS-DISAGREES, or n/a on a row whose cells are all OK); else 0."""
    if summ.counts["DID NOT RUN"]:
        return 2
    if summ.counts["OK"] != len(summ.rows):
        return 1
    if any(ver != "FITS" for _end, ver, ok in (summ.groups or {}).values() if ok):
        return 1
    return 0


def write_summary(out_dir) -> tuple[Summary, int]:
    summ = summarise(out_dir)
    text = render(out_dir, summ)
    (Path(out_dir) / "summary.md").write_text(text)
    for r in summ.rows:
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
    ap.add_argument("--resume", action="store_true",
                    help="continue a non-empty --out (re-runs cells without an rc 0 record)")
    a = ap.parse_args(argv)
    if a.cmd == "run":
        run(a.out, a.only.split(",") if a.only else None, a.rom_dir, resume=a.resume)
    return write_summary(a.out)[1]


if __name__ == "__main__":
    sys.exit(main())
