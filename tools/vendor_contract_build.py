#!/usr/bin/env python3
"""Re-vendor the empyrean.build contract into tools/contract/build/ (G0a).

    EMPYREAN_DIR=<checkout> python3 tools/vendor_contract_build.py

Copies the reader, its tests, the build schema and the vectors from an empyrean checkout and writes
`SOURCE` (the empyrean commit and branch, plus a sha256 per file). Never edit the vendored files by
hand: change them in empyrean first, then run this. `tools/test_contract_build_vendor.py` is the
drift gate. The checkout must be clean for the files it copies, or the pinned commit would not
describe the bytes."""
from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
from suite_paths import empyrean_dir  # noqa: E402

DEST = TOOLS / "contract" / "build"
#: vendored path (relative to DEST) -> path in the empyrean checkout
SINGLE = {"empyrean_build.py": "clients/python/empyrean_build.py",
          "test_empyrean_build.py": "clients/python/test_empyrean_build.py",
          "empyrean.build-1.schema.json": "contract/schema/build/empyrean.build-1.schema.json"}
VECTORS_UP = "contract/schema/build/vectors"
HEADER = ("# Vendored copy of the empyrean.build 1.x reader and contract (G0a). Do not edit here: change it in "
          "empyrean, then re-vendor with tools/vendor_contract_build.py.\n"
          "# Lines below `files:` are sha256sum format: <sha256>  <path relative to this directory>.\n")


def upstream_of(rel: str) -> str:
    return SINGLE[rel] if rel in SINGLE else f"{VECTORS_UP}/{rel[len('vectors/'):]}"


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> int:
    up = empyrean_dir()
    git = lambda *a: subprocess.run(["git", "-C", str(up), *a], check=True, capture_output=True, text=True).stdout.strip()
    vec = sorted(p.relative_to(up / VECTORS_UP).as_posix() for p in (up / VECTORS_UP).rglob("*.json"))
    rels = sorted(SINGLE) + [f"vectors/{v}" for v in vec]
    dirty = git("status", "--porcelain", "--", *[upstream_of(r) for r in rels])
    if dirty:
        print(f"vendor_contract_build: uncommitted changes in the files to vendor:\n{dirty}", file=sys.stderr)
        return 1
    if DEST.exists():
        shutil.rmtree(DEST)
    for r in rels:
        (DEST / r).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(up / upstream_of(r), DEST / r)
    lines = [HEADER.rstrip("\n"), "empyrean-repo: empyrean",
             f"empyrean-branch: {git('branch', '--show-current')}", f"empyrean-commit: {git('rev-parse', 'HEAD')}",
             "files:"] + [f"{sha(DEST / r)}  {r}" for r in rels]
    (DEST / "SOURCE").write_text("\n".join(lines) + "\n")
    print(f"vendored {len(rels)} files from {up} @ {git('rev-parse', '--short', 'HEAD')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
