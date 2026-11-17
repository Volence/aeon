#!/usr/bin/env python3
"""leg_survey — the 48-cell leg survey runner (Empyrean v2 step 0, B2/C-series, Task 6).

    python3 tools/leg_survey.py run  --out DIR [--only idle,run] [--rom-dir DIR]
    python3 tools/leg_survey.py summarise --out DIR

Every leg x shape x phase cell (8 x 2 x 3 = 48) goes through `leg_run --dma-probe`, one
subprocess per cell, with `rc` appended to DIR/manifest.jsonl. `summarise` judges ONLY the
result files on disk (never the manifest, never "the run finished"): a cell with no result
file is DID NOT RUN, with the cell named. Cell status is one of
    OK             the leg's own coverage rule met (idle: CAP at its tick count; others: FINISHED) and the DMA probe measured
    STUCK          the leg's progress stalled
    DID NOT COVER  ran, but hit the cap or never met its coverage condition
    DID NOT RUN    no result file (a missing ROM/listing, a refused or crashed run, not yet run)
    FAILED         a result file that is unreadable, lacks provenance, or whose DMA probe could
                   not measure
The rule-4 verdict per leg x shape is `leg_correction.classify` on the WORST last-DMA end over
the 3 phases against the VBlank window (VInt line -> DMA_END_LIMIT_LINE); anything not derivable
is `n/a (unmeasurable)`, never FITS.

Exit: 0 all 48 OK; 2 any DID NOT RUN; 1 otherwise.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
AEON = TOOLS.parent
sys.path.insert(0, str(TOOLS))
import leg_correction as lc  # noqa: E402
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


def expected_matrix() -> list[tuple[str, str, int]]:
    return [(leg, shape, ph) for leg in LEGS for shape in SHAPES for ph in PHASES]


def result_path(out_dir: Path, leg: str, shape: str, phase: int) -> Path:
    """Where leg_run writes this cell: `<rom-stem>_<policy>_p<phase>.json`."""
    stem = Path(LEG_ROM[(leg, shape)]).stem
    return Path(out_dir) / f"{stem}_{LEG_POLICY[leg]}_p{phase}.json"


# ---- run ---------------------------------------------------------------------------------

def run(out_dir, only=None, rom_dir=None, timeout=600) -> list[dict]:
    """One `leg_run --dma-probe` subprocess per cell; a manifest line per cell. A missing ROM or
    listing is recorded loudly and the cell is left without a result (DID NOT RUN)."""
    out_dir, rom_dir = Path(out_dir), Path(rom_dir or AEON)
    out_dir.mkdir(parents=True, exist_ok=True)
    unknown = [o for o in (only or []) if o not in LEGS]
    if unknown:
        raise SystemExit(f"leg_survey: unknown leg(s) {unknown}; legs are {list(LEGS)}")
    done = []
    for leg, shape, ph in expected_matrix():
        if only and leg not in only:
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
                   str(lst), "--leg", LEG_POLICY[leg], "--phase", str(ph), "--out",
                   str(out_dir), "--dma-probe"]
            try:
                p = subprocess.run(cmd, timeout=timeout)
                rec["rc"] = p.returncode
            except subprocess.TimeoutExpired:
                rec.update(rc=None, note=f"timeout after {timeout}s (killed; not a result)")
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

    @property
    def ran(self) -> int:
        return len(self.rows) - self.counts["DID NOT RUN"]


def _judge(path: Path) -> tuple[str, str, dict | None, int | None]:
    if not path.is_file():
        return "DID NOT RUN", f"no result file {path.name}", None, None
    try:
        r = json.loads(path.read_text())
    except (OSError, ValueError) as e:
        return "FAILED", f"unreadable result {path.name}: {e}", None, None
    return _judge_loaded(r, path)


def _judge_loaded(r, path):
    if not isinstance(r, dict):
        return "FAILED", f"{path.name} is not a result object", None, None
    try:
        lp.require_provenance(r["provenance"])
    except Exception as e:  # MissingProvenance, KeyError, TypeError: all the same finding
        return "FAILED", f"no provenance: {type(e).__name__}: {e}", None, None
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
    return "OK", "", dma, lag


def summarise(out_dir) -> Summary:
    out_dir = Path(out_dir)
    rows = []
    for leg, shape, ph in expected_matrix():
        s, d, dma, lag = _judge(result_path(out_dir, leg, shape, ph))
        rows.append(Row(leg, shape, ph, s, d, lag, dma))
    counts = {s: 0 for s in STATUSES}
    counts.update(Counter(r.status for r in rows))
    return Summary(rows, counts)


def dma_verdict(rows: list) -> tuple[str, str]:
    """(worst last-DMA end, rule-4 verdict) over one leg x shape's phase rows. Anything we cannot
    derive from all 3 phases' probe results is `n/a (unmeasurable)`."""
    na = ("n/a", "n/a (unmeasurable)")
    worst = None
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
    return f"line {line} + {off} mclk", v


def render(out_dir, summ: Summary) -> str:
    L = ["# Leg survey summary", "",
         f"ran {summ.ran} of {len(summ.rows)}  |  " +
         "  ".join(f"{k}: {summ.counts[k]}" for k in STATUSES), "",
         "| leg | shape | cells (p0 p1 p2) | lag frames min-max | worst last-DMA end | rule-4 |",
         "|---|---|---|---|---|---|"]
    for leg in LEGS:
        for shape in SHAPES:
            rs = [r for r in summ.rows if r.leg == leg and r.shape == shape]
            lags = [r.lag_frames for r in rs if isinstance(r.lag_frames, int)]
            lagtxt = f"{min(lags)}-{max(lags)}" if lags and len(lags) == len(rs) else (
                f"{min(lags)}-{max(lags)} (partial)" if lags else "n/a")
            end, ver = dma_verdict(rs)
            L.append(f"| {leg} | {shape} | {' '.join(r.status for r in rs)} | {lagtxt} | {end} "
                     f"| {ver} |")
    bad = [r for r in summ.rows if r.status != "OK"]
    L += ["", "## Cells not OK", ""]
    L += [f"- {r.leg}/{r.shape}/p{r.phase}: **{r.status}** {r.detail}" for r in bad] or ["- none"]
    L += ["", f"ran {summ.ran} of {len(summ.rows)}", ""]
    return "\n".join(L)


def exit_code(summ: Summary) -> int:
    if summ.counts["DID NOT RUN"]:
        return 2
    return 0 if summ.counts["OK"] == len(summ.rows) else 1


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
    a = ap.parse_args(argv)
    if a.cmd == "run":
        run(a.out, a.only.split(",") if a.only else None, a.rom_dir)
    return write_summary(a.out)[1]


if __name__ == "__main__":
    sys.exit(main())
