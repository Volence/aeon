#!/usr/bin/env python3
"""s2clip_rebake — regenerate an S2CLIP build's throwaway level bake from COMMITTED inputs,
into a directory, WITHOUT touching the working tree (v2 C4, Task 10).

    python3 tools/s2clip_rebake.py rebake --clip s2_woven --out DIR

WHY. build.sh's S2CLIP shape bakes the clip act into the shipped act's slot IN PLACE
(`clip_rom_bake.py bake --keep`) and its EXIT trap restores the committed tree, so the
bytes the build read are not on disk afterwards and `artifact_provenance.check_pair` reads
every S2CLIP pair as NOT FRESH (the C2 report's finding, Task 8). leg_provenance's declared
re-bake (SHAPE_REBAKES `s4.s2clip`) regenerates those bytes and checks the DIGEST-READ rows
against them instead.

HOW. clip_rom_bake writes through fixed module paths (act_grid.ACT_GRID_EMP, the generators'
output globals), so redirecting it piecemeal would half-point. Instead the bake runs, exactly
as build.sh runs it, inside a PRIVATE COPY of the committed tree:

  1. `git archive HEAD` (minus SANDBOX_EXCLUDE) extracted into a sandbox under tools/.cache/
     (gitignored, on disk: /tmp is RAM on this host), plus the converted donor trees
     (gitignored, games/sonic4/data/donors) and tools/bin (gitignored: salvador, the ZX0
     page compressor) copied in -- the build reads both from the working tree too;
  2. `python3 tools/clip_rom_bake.py bake <clips.json> --allow-dirty --keep` with the
     sandbox as its cwd and repo (its REPO is its own file's parent);
  3. the two baked trees (TREES) copied to `<out>/<repo path>`; the sandbox is removed.

The working tree's TREES are checked clean before and after (a bake that escaped the
sandbox is refused loudly). Exit 0 written; 1 refused (the reason on stderr).
"""
from __future__ import annotations

import argparse
import io
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

AEON = Path(__file__).resolve().parent.parent
#: The two trees the S2CLIP bake writes (clip_rom_bake.RESTORE_PATHS) -- what is handed back.
TREES = ("games/sonic4/data/generated/ojz/act1", "games/sonic4/data/collision")
#: The committed tree minus these top-level entries is the sandbox (docs/ is ~95 MB of
#: research the bake never reads; everything else -- tools, games, engine, art (the line-0
#: palette clip_manifest reads), project.json -- is copied, so no read path is guessed).
SANDBOX_EXCLUDE = ("docs",)
DONORS = "games/sonic4/data/donors"
#: Gitignored tool binaries the bake runs (the ZX0 page compressor), copied in as built.
TOOL_BINS = "tools/bin"
CACHE = AEON / "tools" / ".cache"


class Refused(RuntimeError):
    pass


def _git(*args, **kw):
    return subprocess.run(["git", "-C", str(AEON), *args], check=True, capture_output=True,
                          **kw).stdout


def _dirty(paths) -> str:
    return _git("status", "--porcelain", "--", *paths, text=True).strip()


def rebake(clip: str, out: Path) -> list[str]:
    manifest = f"games/sonic4/data/clips/{clip}/clips.json"
    if not (AEON / manifest).is_file():
        raise Refused(f"no clip manifest {manifest}")
    if not (AEON / DONORS).is_dir():
        raise Refused(f"{DONORS} is missing: convert the donors first "
                      f"(python3 tools/s2_zone_convert.py convert --all-six)")
    before = _dirty(TREES)
    if before:
        raise Refused(f"the working tree's {TREES} are not clean; refusing:\n{before}")
    CACHE.mkdir(parents=True, exist_ok=True)
    box = Path(tempfile.mkdtemp(prefix="s2clip_rebake.", dir=CACHE))
    try:
        top = [n for n in _git("ls-tree", "--name-only", "HEAD", text=True).split()
               if n not in SANDBOX_EXCLUDE]
        tar = _git("archive", "HEAD", "--", *top)
        with tarfile.open(fileobj=io.BytesIO(tar)) as t:
            t.extractall(box, filter="data")
        shutil.copytree(AEON / DONORS, box / DONORS)
        if (AEON / TOOL_BINS).is_dir():
            shutil.copytree(AEON / TOOL_BINS, box / TOOL_BINS, dirs_exist_ok=True)
        p = subprocess.run([sys.executable, "tools/clip_rom_bake.py", "bake", manifest,
                            "--allow-dirty", "--keep"], cwd=box, capture_output=True, text=True)
        if p.returncode != 0:
            raise Refused(f"clip_rom_bake bake {clip} -> rc {p.returncode}:\n"
                          f"{(p.stdout + p.stderr)[-1500:]}")
        written = []
        for tree in TREES:
            for f in sorted((box / tree).rglob("*")):
                if f.is_file():
                    rel = f.relative_to(box).as_posix()
                    dst = Path(out) / rel
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(f, dst)
                    written.append(rel)
    finally:
        shutil.rmtree(box, ignore_errors=True)
    after = _dirty(TREES)
    if after:
        raise Refused(f"the bake escaped its sandbox: {TREES} changed in the working tree:\n"
                      f"{after}")
    return written


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("rebake")
    r.add_argument("--clip", required=True)
    r.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    try:
        n = rebake(a.clip, Path(a.out))
    except (Refused, subprocess.CalledProcessError, OSError) as e:
        print(f"s2clip_rebake: REFUSED — {e}", file=sys.stderr)
        return 1
    print(f"s2clip_rebake: {a.clip}: {len(n)} file(s) under {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
