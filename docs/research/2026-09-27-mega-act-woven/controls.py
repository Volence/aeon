#!/usr/bin/env python3
"""Can `woven.py check` fail? Each control breaks layout.json one way and must turn it red.

Mutations are made on a COPY under --scratch (default ~/.cache/aeon-tmp/woven/ctl), never on
layout.json. Prints each control's red rows and exits 1 if any control stays green.

    python3 controls.py
"""
import argparse
import copy
import json
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent


def clip(d, cid):
    return next(c for c in d["clips"] if c["id"] == cid)


def c_cpz_closer(d):
    """Chemical Plant and the east half of Metropolis 16 px left: the C6 tunnel is 368."""
    clip(d, "cpz_loop_cluster")["dst"][0] -= 16
    clip(d, "mtz_east")["dst"][0] -= 16


def c_mtz_own_blob(d):
    """Metropolis out of Chemical Plant's BG blob: C6/C7 now need an overwrite."""
    d["blobs"] = {"A": ["EHZ", "HPZ", "WFZ"], "M": ["CPZ"], "M2": ["MTZ"], "O": ["OOZ"]}


def c_hpz_up(d):
    """Hidden Palace 64 px up: the C4 shaft is 224, screen height with no BG time."""
    clip(d, "hpz_west")["dst"][1] -= 64


def c_hpz_touch(d):
    """Hidden Palace directly under Emerald Hill, no band at all."""
    c = clip(d, "hpz_west")
    e = clip(d, "ehz_double_loop")
    c["dst"][1] = e["dst"][1] + e["src"][3]


def c_hpz_east_up(d):
    """r2: Hidden Palace's east piece 16 px up: the C10 shaft to Metropolis is 512."""
    c = clip(d, "hpz_east")
    c["dst"][1] -= 16
    c["src"][1] -= 16
    c["src"][3] += 16


def c_hpz_east_wider(d):
    """r2: Hidden Palace's east piece 16 px wider: the C11 tunnel to Oil Ocean is 560."""
    clip(d, "hpz_east")["src"][2] += 16


CONTROLS = [c_cpz_closer, c_mtz_own_blob, c_hpz_up, c_hpz_touch, c_hpz_east_up,
            c_hpz_east_wider]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scratch", default=str(pathlib.Path.home() / ".cache/aeon-tmp/woven/ctl"))
    a = ap.parse_args()
    out_dir = pathlib.Path(a.scratch)
    out_dir.mkdir(parents=True, exist_ok=True)
    base = json.loads((HERE / "layout.json").read_text())
    green = 0
    for fn in CONTROLS:
        d = copy.deepcopy(base)
        fn(d)
        p = out_dir / f"{fn.__name__}.json"
        p.write_text(json.dumps(d))
        r = subprocess.run([sys.executable, str(HERE / "woven.py"), "check", str(p)],
                           capture_output=True, text=True)
        rows = [ln for ln in r.stdout.splitlines()
                if "SHORT" in ln or ln.startswith(("MIXED", "WRONG", "VERDICT"))]
        print(f"== {fn.__name__}: {fn.__doc__.strip()}  (exit {r.returncode})")
        print("\n".join("   " + ln for ln in rows))
        green += r.returncode == 0
    print(f"{len(CONTROLS) - green} of {len(CONTROLS)} controls red")
    return 1 if green else 0


if __name__ == "__main__":
    sys.exit(main())
