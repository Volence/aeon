#!/usr/bin/env python3
"""Art-pool ROM budget report + gate (art-streaming Phase 2, Task 12).

For each act that ships a paged art pool, report the pool's ROM footprint:
raw (uncompressed) pool bytes, STORED bytes broken out per election form
(ZX0 vs raw-direct), page count, and the stored/raw ratio. Then gate the
stored footprint against a soft (warn) and hard (fail) per-act ceiling.

The residency cache means level art is capped by ROM, not VRAM (a page not
resident is streamed in on demand), so the ROM footprint of the pool is the
budget that matters now. This report is that budget's watchdog.

Data sources (no ROM parse needed — the pool's ROM cost is exactly the sum of
the embedded page blobs):
  - <act>/ojz_act_pool.emp          -> per-page embed() path + PageManifest form/tiles
  - <act>/ojz_act_pool_manifest.json -> page_tiles / pool_tiles cross-check

Thresholds (KB of STORED pool bytes), per act, overridable by env:
  ART_ROM_SOFT_KB / ART_ROM_HARD_KB          -> all acts
  ART_ROM_SOFT_KB_<ACT> / ART_ROM_HARD_KB_<ACT> -> one act (e.g. _OJZ)
OJZ defaults 24 / 64 KB (generous now, tightened when real acts exist).

Exit: 0 clean/warn, 2 over a hard ceiling (unless --no-fail).
"""

import glob
import json
import os
import re
import sys

DEFAULT_SOFT_KB = 24.0
DEFAULT_HARD_KB = 64.0
FORM_NAMES = {0: "zx0", 1: "raw"}

EMBED_RE = re.compile(r'data\s+(OJZ_Act_Pool_Page\d+)\s*=\s*embed\("([^"]+)"\)')
MANIFEST_RE = re.compile(
    r'pm_source:\s*extern\("(OJZ_Act_Pool_Page\d+)"\)\s*,\s*'
    r'pm_tiles:\s*(\d+)\s*,\s*pm_form:\s*(\d+)'
)


def find_act_pools(root):
    """Yield (act_name, pool_emp_path) for every emitted act pool table."""
    pattern = os.path.join(root, "games", "*", "data", "generated", "*", "act*",
                           "ojz_act_pool.emp")
    for emp in sorted(glob.glob(pattern)):
        act_dir = os.path.dirname(emp)
        act = os.path.basename(act_dir)                       # act1
        zone = os.path.basename(os.path.dirname(act_dir))     # ojz
        yield f"{zone.upper()}_{act.upper()}", act_dir, emp


def parse_pool(act_dir, emp_path):
    """Return list of page dicts: {name, path, form, tiles, stored, raw}."""
    text = open(emp_path).read()
    embeds = {m.group(1): m.group(2) for m in EMBED_RE.finditer(text)}
    pages = []
    for m in MANIFEST_RE.finditer(text):
        name, tiles, form = m.group(1), int(m.group(2)), int(m.group(3))
        path = embeds.get(name)
        if path is None:
            raise SystemExit(f"art_rom_report: {emp_path}: {name} in table "
                             f"but has no embed() — pool emp is malformed")
        # embed() paths are repo-relative; resolve from the repo root.
        abspath = path if os.path.isabs(path) else os.path.join(
            os.path.dirname(emp_path).split("/games/")[0], path)
        stored = os.path.getsize(abspath)
        pages.append({"name": name, "path": path, "form": form,
                      "tiles": tiles, "stored": stored, "raw": tiles * 32})
    return pages


def env_kb(name, act, default):
    for key in (f"{name}_{act}", name):
        if os.environ.get(key):
            try:
                return float(os.environ[key])
            except ValueError:
                pass
    return default


def report_act(act, act_dir, emp_path, no_fail):
    pages = parse_pool(act_dir, emp_path)
    raw = sum(p["raw"] for p in pages)
    stored = sum(p["stored"] for p in pages)
    by_form = {}
    for p in pages:
        f = FORM_NAMES.get(p["form"], f"form{p['form']}")
        d = by_form.setdefault(f, {"pages": 0, "stored": 0, "raw": 0})
        d["pages"] += 1
        d["stored"] += p["stored"]
        d["raw"] += p["raw"]

    soft = env_kb("ART_ROM_SOFT_KB", act, DEFAULT_SOFT_KB)
    hard = env_kb("ART_ROM_HARD_KB", act, DEFAULT_HARD_KB)
    stored_kb = stored / 1024.0
    ratio = (stored / raw * 100.0) if raw else 0.0

    print(f"  {act}: {len(pages)} pages, raw {raw/1024:.1f} KB -> "
          f"stored {stored_kb:.1f} KB ({ratio:.1f}%)")
    for f in sorted(by_form):
        d = by_form[f]
        fr = (d["stored"] / d["raw"] * 100.0) if d["raw"] else 0.0
        print(f"      {f:>3}: {d['pages']:>2} pages, "
              f"{d['stored']/1024:.1f} KB stored ({fr:.1f}%)")
    print(f"      budget: soft {soft:.0f} KB / hard {hard:.0f} KB", end="")

    status = "ok"
    if stored_kb > hard:
        print(f"  -> FAIL (over hard by {stored_kb-hard:.1f} KB)")
        status = "fail"
    elif stored_kb > soft:
        print(f"  -> WARN (over soft by {stored_kb-soft:.1f} KB)")
        status = "warn"
    else:
        print("  -> ok")
    return status


def main(argv):
    no_fail = "--no-fail" in argv
    root = "."
    for a in argv[1:]:
        if not a.startswith("-"):
            root = a
    acts = list(find_act_pools(root))
    if not acts:
        print("art_rom_report: no act art pools found (nothing to report)")
        return 0
    print("Art-pool ROM budget:")
    worst = "ok"
    for act, act_dir, emp in acts:
        st = report_act(act, act_dir, emp, no_fail)
        if st == "fail":
            worst = "fail"
        elif st == "warn" and worst != "fail":
            worst = "warn"
    if worst == "fail" and not no_fail:
        print("art_rom_report: an act art pool exceeds its HARD ROM ceiling.")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
