#!/usr/bin/env python3
"""Stamp the DONOR REVISIONS a level re-bake actually read.

The committed level tree under `games/sonic4/data/generated/` and the collision
tables under `games/sonic4/data/collision/` are baked from TWO out-of-repo donor
projects — `sonic_hack` (layouts / Kosinski art / chunk+block maps) and
`skdisasm` (the S&K 252-shape collision vocabulary). Until this file existed,
NEITHER donor's revision was recorded anywhere, so nobody — not even the
authoring machine — could prove a re-bake would reproduce the committed bytes.
The bytes were tracked; the inputs that produced them were not.

What this writes is a claim about INPUTS, not a checksum of outputs. It cannot
prove the tree reproduces; it makes the question answerable, by naming the two
revisions to check out before asking. Read `mode` before trusting it:

  mode = "rebake"    the donors named here were read by the generate() run that
                     wrote the tree in the same commit. This is the real claim.
  mode = "backfill"  the SHAs were recorded by pointing this tool at the donors
                     some time AFTER the bake. It says "these were the donor
                     revisions present when someone looked", nothing more. It is
                     NOT evidence that this tree reproduces from them.

`dirty` is the other half of the claim: a donor with uncommitted modifications
is not identified by its SHA, and the stamp says so instead of implying the SHA
is sufficient.

Usage:
    python3 tools/donor_provenance.py --backfill    # record today's donor SHAs

`ojz_strip_gen.generate()` calls `write_provenance(mode="rebake")` itself, so a
real re-bake needs no separate step.
"""

import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ojz_common import SONIC_HACK, skdisasm_root  # noqa: E402

REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

# Lives INSIDE ojz_strip_gen's output directory, not at the root of the generated
# tree, and that is a safety property rather than a filing choice: `generate()`
# derives the destination from its own `out_dir`, so the tempdir redirect that
# `test_full_pipeline_runs` uses reaches it automatically. A module-constant path
# aimed at the committed tree is exactly the shape of tools lens sweep D8, where a
# redirected generator kept writing committed ROM data through the redirect.
#
# It still describes the WHOLE re-bake — including data/collision/, whose donor is
# skdisasm rather than sonic_hack — because regenerate-level.sh bakes both from the
# same pair of checkouts in one pass.
#
# Tracked: `.gitignore` blanket-ignores *.bin, not *.json, so no negation is needed
# here (renaming it to a .bin-ish extension would silently untrack it).
PROVENANCE_PATH = os.path.join(REPO_ROOT, "games", "sonic4", "data", "generated",
                               "ojz", "act1", "DONOR_PROVENANCE.json")

SCHEMA = 1


def _git(repo: str, *args: str) -> str | None:
    """Run a READ-ONLY git query in `repo`; None if it is not a usable git repo.

    `--no-optional-locks` matters: donors are somebody else's repositories and
    this tool must not write to them. Without it, `git status` refreshes (and
    rewrites) the donor's index as a side effect of being asked a question.
    """
    try:
        out = subprocess.run(
            ["git", "--no-optional-locks", "-C", repo, *args],
            capture_output=True, text=True, timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    return out.stdout


def describe_repo(path: str) -> dict:
    """The revision claim for one checkout: sha + whether the sha is sufficient.

    Never raises and never guesses. A path that is absent, or present but not a
    git checkout, yields head=None with a `status` naming which of those it is —
    "unknown" and "clean" must never be confusable, since the whole point of the
    file is to be believed.
    """
    rec: dict = {"path": path}
    if not os.path.isdir(path):
        rec.update(status="absent", head=None, dirty=None,
                   detail="directory does not exist on this machine")
        return rec

    head = _git(path, "rev-parse", "HEAD")
    if head is None:
        rec.update(status="not-a-git-repo", head=None, dirty=None,
                   detail="no git revision available (unpacked copy, or no git)")
        return rec

    porcelain = _git(path, "status", "--porcelain", "--untracked-files=normal")
    if porcelain is None:
        # HEAD resolved but status did not — do NOT report clean by omission.
        rec.update(status="git", head=head.strip(), dirty=None,
                   detail="git status unavailable; dirtiness UNKNOWN")
        return rec

    lines = [ln for ln in porcelain.splitlines() if ln.strip()]
    untracked = sum(1 for ln in lines if ln.startswith("??"))
    modified = len(lines) - untracked
    rec.update(
        status="git",
        head=head.strip(),
        dirty=modified > 0,
        modified_tracked=modified,
        untracked=untracked,
    )
    branch = _git(path, "rev-parse", "--abbrev-ref", "HEAD")
    if branch:
        rec["branch"] = branch.strip()
    return rec


def build_provenance(mode: str, sonic_hack: str | None = None,
                     skdisasm: str | None = None,
                     generator_repo: str | None = None,
                     recorded_at: str | None = None) -> dict:
    """Assemble the provenance record. Pure: no filesystem writes, no clock.

    `recorded_at` is a parameter and not a `now()` call so the record is a
    deterministic function of its inputs — a re-bake that changed nothing must
    not produce a diff here purely because time passed.
    """
    if mode not in ("rebake", "backfill"):
        raise ValueError(f"donor_provenance: mode must be 'rebake' or 'backfill', got {mode!r}")

    rec = {
        "schema": SCHEMA,
        "_note": (
            "Donor revisions read by the level re-bake that produced "
            "games/sonic4/data/generated/ and games/sonic4/data/collision/. "
            "Written by tools/donor_provenance.py. mode=rebake means these donors "
            "were read by the bake committed alongside this file; mode=backfill "
            "means every revision here (donors AND generator) was recorded by "
            "inspection AFTER the bake, and is NOT proof that this tree reproduces "
            "from them. A donor with dirty=true is not identified by its SHA at all."
        ),
        "mode": mode,
        "donors": {
            "sonic_hack": dict(
                role="level layouts, Kosinski art, chunk+block maps, palette",
                env_var="AEON_SONIC_HACK_DIR",
                **describe_repo(sonic_hack if sonic_hack is not None else SONIC_HACK),
            ),
            "skdisasm": dict(
                role="S&K 252-shape collision vocabulary (import_sk_collision.py)",
                env_var="AEON_SKDISASM_DIR",
                **describe_repo(skdisasm if skdisasm is not None else skdisasm_root()),
            ),
        },
        # The generator's own revision is the third reproducibility input: the same
        # donors through different tool code give different bytes. Expect this to
        # differ on every re-bake (and to read dirty, since this very file is
        # unwritten at the moment it is sampled) — that is honest, not noise.
        "generator": dict(
            repo="aeon",
            **describe_repo(generator_repo if generator_repo is not None else REPO_ROOT),
        ),
    }
    # This repo's own checkout LOCATION is not provenance — a re-bake run from a
    # git worktree would otherwise stamp a throwaway agent directory and a branch
    # nobody will ever see again. Its REVISION is the thing that matters. (Donor
    # paths stay: those are out-of-repo, so where they lived is real information.)
    rec["generator"].pop("path", None)
    rec["generator"].pop("branch", None)
    if recorded_at is not None:
        rec["recorded_at"] = recorded_at
    return rec


def render(record: dict) -> str:
    """Canonical serialization — sorted keys, trailing newline, stable diffs."""
    return json.dumps(record, indent=2, sort_keys=True) + "\n"


def write_provenance(mode: str, path: str | None = None, **kwargs) -> dict:
    """Build + write the provenance file; returns the record."""
    record = build_provenance(mode, **kwargs)
    out = path or PROVENANCE_PATH
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        f.write(render(record))

    for name, d in record["donors"].items():
        if d["head"] is None:
            print(f"  WARNING: donor {name} revision UNKNOWN ({d['status']}: {d.get('detail','')}) "
                  f"— the bake is unreproducible by revision.")
        elif d["dirty"]:
            print(f"  WARNING: donor {name} is DIRTY at {d['head'][:12]} "
                  f"({d['modified_tracked']} modified tracked file(s)) — the SHA does "
                  f"not identify what was read.")
        else:
            print(f"  donor {name}: {d['head'][:12]} (clean)")
    print(f"Wrote donor provenance ({mode}) -> {out}")
    return record


def main() -> int:
    args = sys.argv[1:]
    if args != ["--backfill"]:
        print(f"Usage: {sys.argv[0]} --backfill")
        print("  Records the donor SHAs present RIGHT NOW against the already-committed")
        print("  bake. A real re-bake stamps itself (mode=rebake) via ojz_strip_gen.")
        return 1
    from datetime import date
    write_provenance("backfill", recorded_at=date.today().isoformat())
    return 0


if __name__ == "__main__":
    sys.exit(main())
