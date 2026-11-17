#!/usr/bin/env python3
"""stress_sidekick — the STRESS_SIDEKICK=1 build shape's one mechanism (Empyrean v2 step 0, C3).

WHAT THE SHAPE IS (C1 note docs/superpowers/notes/2026-11-16-stress-content-sizing.md §2).
A second player, Player_2, spawned on Player_1 and run every tick on Player_1's input word
from 16 ticks ago (Player_Stat_Ring), with its own CharacterDef copy whose `cd_vrambase` is
VRAM_STRESS_SIDEKICK: a 29-tile window borrowed from the register-less `spare_nametable`
(768..796). While Player_1 is in debug free flight (which writes no ring entry) Player_2 is
pinned to it. The survey's `sidekick` leg measures what a sidekick costs v1.

WHY A PATCH (the note's ruling, §2.5). Nothing sidekick-related is on canonical master: the
code and the VRAM region live in ONE committed patch, `tools/stress/sidekick.patch`, data
that nothing compiles. `build.sh` applies it in place under an EXIT trap that restores the
touched files from git (`apply` below), regenerates the VRAM map from the patched
vram.toml, and builds `s4.sidekick[.debug].bin`. Canonical bytes are identical by
construction.

Subcommands:
  guard            refuse (exit 1) a tree that carries the applied patch or its regenerated
                   VRAM map: a SIGKILLed shape build runs no trap, and the next canonical
                   build would ship the sidekick in s4.bin. build.sh runs it in every shape.
  apply            `git apply --check` (a refusal names the patch: it has rotted), apply,
                   regenerate the VRAM map. build.sh's STRESS_SIDEKICK block runs it.
  paths            print RESTORE_PATHS, one per line (build.sh's EXIT-trap list; one source).
  rebake --out D   write the patched + regenerated files under D/<repo path>, from the
                   COMMITTED inputs, without touching the tree: the throwaway re-bake the
                   harness checks a sidekick listing's DIGEST-READ rows against
                   (leg_provenance.SHAPE_REBAKES).
Exit: 0 ok, 1 refused, 2 could not run.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
AEON_ROOT = TOOLS.parent

PATCH = "tools/stress/sidekick.patch"
#: The files the patch edits.
PATCHED = ("games/sonic4/test/ojz_scroll_test.emp", "games/sonic4/vram.toml")
#: The files `gen_vram_map.py` rewrites from the patched vram.toml.
REGENERATED = ("games/sonic4/config/constants.emp", "tools/vram_map.py",
               "docs/generated/vram-map-sonic4.md")
#: Every file the shape changes in place, i.e. what the EXIT trap restores.
RESTORE_PATHS = PATCHED + REGENERATED
#: The two the sigil build reads (DIGEST-READ rows); the other three are build-time only.
BUILD_READS = ("games/sonic4/test/ojz_scroll_test.emp", "games/sonic4/config/constants.emp")
#: The map doc is gen_vram_map's OUTPUT only: written by `apply`, checked out by the trap,
#: never read here (the guard skips it; a leftover doc changes no ROM byte). Everything else
#: in RESTORE_PATHS the guard scans.
GUARDED = tuple(p for p in RESTORE_PATHS if not p.endswith(".md"))
#: What only the patch introduces. The region name and the constant are the patch's own; a
#: canonical tree carrying either is a leftover.
MARKERS = ("stress_sidekick_body", "VRAM_STRESS_SIDEKICK")


class Refused(RuntimeError):
    pass


def _regen_argv(root: Path) -> list[str]:
    r = Path(root)
    return [sys.executable, str(r / "tools" / "gen_vram_map.py"), "--game", "sonic4",
            "--toml", str(r / "games/sonic4/vram.toml"),
            "--emp", str(r / "games/sonic4/config/constants.emp"),
            "--py", str(r / "tools/vram_map.py"),
            "--map-doc", str(r / "docs/generated/vram-map-sonic4.md")]


def _run(argv, cwd) -> subprocess.CompletedProcess:
    return subprocess.run(argv, cwd=cwd, capture_output=True, text=True)


def leftovers(root: Path = AEON_ROOT) -> list[str]:
    """Every RESTORE_PATHS file that carries a MARKER (`path: marker`)."""
    out = []
    for rel in GUARDED:
        p = Path(root) / rel
        try:
            text = p.read_text(errors="replace")
        except OSError:
            continue
        out += [f"{rel}: {m}" for m in MARKERS if m in text]
    return out


def guard(root: Path = AEON_ROOT) -> int:
    hits = leftovers(root)
    if not hits:
        print("stress_sidekick guard: OK (no applied sidekick patch in the tree)")
        return 0
    print("ERROR: the tree carries the STRESS_SIDEKICK patch (a stress build that ran no EXIT")
    print("  trap, e.g. SIGKILL). A canonical build from it would ship the sidekick in s4.bin:")
    for h in hits:
        print(f"    {h}")
    print("  Restore by hand:  git checkout -- " + " ".join(RESTORE_PATHS))
    return 1


def apply(root: Path = AEON_ROOT) -> None:
    """Apply the patch in place and regenerate the VRAM map. Raises Refused."""
    root = Path(root)
    chk = _run(["git", "apply", "--check", PATCH], root)
    if chk.returncode != 0:
        raise Refused(f"{PATCH} no longer applies to this tree (it has rotted against "
                      f"{' / '.join(PATCHED)}): re-diff its hunks.\n{chk.stderr.strip()}")
    ap = _run(["git", "apply", PATCH], root)
    if ap.returncode != 0:
        raise Refused(f"git apply {PATCH} failed after --check passed: {ap.stderr.strip()}")
    g = _run(_regen_argv(root), root)
    if g.returncode != 0:
        raise Refused(f"gen_vram_map.py refused the patched vram.toml:\n{g.stdout}{g.stderr}")
    print(f"stress_sidekick: applied {PATCH}; {g.stdout.strip()}")


def rebake(out_dir: Path, root: Path = AEON_ROOT) -> dict:
    """Write every RESTORE_PATHS file, patched and regenerated, under out_dir/<repo path>,
    built from the files as they are in `root` (which must not carry the patch). Returns
    {repo path: written file}. The tree is not touched."""
    root, out_dir = Path(root), Path(out_dir)
    if leftovers(root):
        raise Refused(f"rebake: {root} already carries the patch ({leftovers(root)}); a re-bake "
                      "must start from the committed files")
    with tempfile.TemporaryDirectory(prefix="sidekick_rebake.") as td:
        work = Path(td)
        for rel in GUARDED + ("tools/gen_vram_map.py", PATCH):
            (work / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(root / rel, work / rel)
        for rel in REGENERATED:                       # outputs only (the map doc)
            (work / rel).parent.mkdir(parents=True, exist_ok=True)
        # Outside any repository `git apply` is a plain patch tool on the copies.
        ap = _run(["git", "apply", PATCH], work)
        if ap.returncode != 0:
            raise Refused(f"rebake: {PATCH} does not apply to the committed files: "
                          f"{ap.stderr.strip()}")
        g = _run(_regen_argv(work), work)
        if g.returncode != 0:
            raise Refused(f"rebake: gen_vram_map.py refused: {g.stdout}{g.stderr}")
        out = {}
        for rel in RESTORE_PATHS:
            dst = out_dir / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(work / rel, dst)
            out[rel] = dst
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("guard")
    g.add_argument("--root", default=str(AEON_ROOT))
    a = sub.add_parser("apply")
    a.add_argument("--root", default=str(AEON_ROOT))
    sub.add_parser("paths")
    r = sub.add_parser("rebake")
    r.add_argument("--out", required=True)
    r.add_argument("--root", default=str(AEON_ROOT))
    args = ap.parse_args(argv)
    try:
        if args.cmd == "guard":
            return guard(Path(args.root))
        if args.cmd == "paths":
            print("\n".join(RESTORE_PATHS))
            return 0
        if args.cmd == "apply":
            apply(Path(args.root))
            return 0
        if args.cmd == "rebake":
            for rel, p in rebake(Path(args.out), Path(args.root)).items():
                print(f"{rel} -> {p}")
            return 0
        print(f"stress_sidekick: unknown mode {args.cmd!r}", file=sys.stderr)
        return 2
    except Refused as e:
        print(f"ERROR: stress_sidekick {args.cmd}: {e}", file=sys.stderr)
        return 1
    except OSError as e:
        print(f"stress_sidekick {args.cmd}: COULD NOT RUN — {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
