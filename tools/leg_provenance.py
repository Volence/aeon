#!/usr/bin/env python3
"""leg_provenance — the pinned Oracle build and the provenance every harness result carries
(Empyrean v2 step 0, B1).

WHY. Until now an engine number came from whatever `oracle-aether` happened to be at some
path (`aether_instance.SERVER`'s default does not exist on this machine: Oracle fitness
finding 1), measured against whatever .bin/.lst pair was lying around. Both are refused here:

  * The emulator is the binary named in `tools/oracle_pin.toml`: sha256 checked BEFORE spawn
    (a binary rebuilt at the same path is refused), and the live handshake's `serverBuild`
    checked AFTER (id == "<commit>+profile=release", source == "vcs", dirty == false).
  * The ROM is vouched for by its listing through `artifact_provenance.check_pair` (a fresh
    .bin with an old .lst is refused, never measured silently).
  * A dirty aeon tree is RECORDED (`aeon.dirty`), never hidden.
  * `require_provenance` is the writer's gate: a result missing any provenance key refuses
    to be written.

`spawn_pinned` is the only spawn the harness uses.
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import tomllib
import zlib
from dataclasses import dataclass
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
from suite_paths import suite_path  # noqa: E402
import artifact_provenance as ap  # noqa: E402
from artifact_provenance import check_pair, read_digest  # noqa: E402

PIN_FILE = TOOLS / "oracle_pin.toml"
AEON_ROOT = TOOLS.parent


class PinMismatch(RuntimeError):
    """The emulator is not the pinned one. The message names the field that disagrees."""


class MissingProvenance(RuntimeError):
    """A result lacks provenance. A result without it is not written."""


class StalePair(RuntimeError):
    """The .bin/.lst pair is not fresh per artifact_provenance.check_pair."""


@dataclass(frozen=True)
class OraclePin:
    commit: str
    binary: Path
    sha256: str


def load_pin(path: Path = PIN_FILE) -> OraclePin:
    with open(path, "rb") as f:
        t = tomllib.load(f)
    for k in ("commit", "binary", "sha256"):
        if not t.get(k):
            raise PinMismatch(f"{path}: `{k}` is missing or empty")
    b = Path(t["binary"])
    return OraclePin(t["commit"], b if b.is_absolute() else suite_path(*b.parts), t["sha256"])


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_binary(pin: OraclePin) -> str:
    """sha256 of the binary on disk must equal the pin's. Runs BEFORE any spawn."""
    if not pin.binary.is_file():
        raise PinMismatch(f"pinned binary does not exist: {pin.binary}")
    got = sha256_file(pin.binary)
    if got != pin.sha256:
        raise PinMismatch(f"binary sha256 {got} != pinned {pin.sha256} ({pin.binary})")
    return got


def verify_pin(pin: OraclePin, handshake: dict) -> None:
    """The live handshake must be the pinned build, built from vcs, clean."""
    sb = handshake.get("serverBuild")
    if not isinstance(sb, dict):
        raise PinMismatch("handshake has no serverBuild: cannot prove which build answered")
    # The real id is "<commit>+profile=release+target=<triple>+features=" (measured on the
    # pinned binary); the plan's bare "<commit>+profile=release" is its prefix. Compare by
    # parts: commit exact, profile=release, no cargo features, target free.
    want = pin.commit + "+profile=release"
    sid = sb.get("id")
    parts = sid.split("+") if isinstance(sid, str) else []
    kv = dict(p.split("=", 1) for p in parts[1:] if "=" in p)
    if (not parts or parts[0] != pin.commit or kv.get("profile") != "release"
            or kv.get("features", "") != ""):
        raise PinMismatch(f"serverBuild.id {sid!r} != pinned {want!r} "
                          "(commit, profile=release, no features)")
    if sb.get("source") != "vcs":
        raise PinMismatch(f"serverBuild.source {sb.get('source')!r} != 'vcs' "
                          "(a declared/unknown build has no commit proof)")
    if sb.get("dirty") is not False:
        raise PinMismatch(f"serverBuild.dirty {sb.get('dirty')!r} != False")


def rom_provenance(rom: Path, lst: Path, root: Path | None = None) -> dict:
    """`root` is the aeon root the digest is checked against (default: this tree)."""
    rom, lst = Path(rom), Path(lst)
    v = check_pair(str(rom), str(lst), root=None if root is None else str(root))
    if not v.fresh:
        raise StalePair(v.render("leg_provenance"))
    d = read_digest(str(lst))
    shape, asm = d["shape"], d["assembler"]
    data = rom.read_bytes()
    return {"rom": rom.name, "crc32": f"{zlib.crc32(data) & 0xFFFFFFFF:08x}", "size": len(data),
            "game": shape["game"], "debug": int(shape["debug"]), "target": shape["target"],
            "extra_entries": shape["extra-entries"], "sigil_revision": asm["revision"],
            "tree": asm["tree"]}


def _git(root: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True,
                          text=True).stdout


#: How many `git status --porcelain` lines `aeon.dirty_paths` keeps; `dirty_count` is the total.
DIRTY_PATHS_MAX = 50


def aeon_provenance(root: Path = AEON_ROOT) -> dict:
    """`dirty` counts UNTRACKED files too (an untracked .emp can change a build). The porcelain
    lines behind it are recorded (`dirty_paths`, first DIRTY_PATHS_MAX, plus `dirty_count`) so
    a dirty flag can always be audited, never just believed."""
    lines = [ln for ln in _git(root, "status", "--porcelain").splitlines() if ln.strip()]
    return {"commit": _git(root, "rev-parse", "HEAD").strip(),
            "dirty": bool(lines),
            "dirty_count": len(lines),
            "dirty_paths": lines[:DIRTY_PATHS_MAX],
            "branch": _git(root, "branch", "--show-current").strip()}


def provenance(pin: OraclePin, handshake: dict, rom: Path, lst: Path) -> dict:
    verify_pin(pin, handshake)
    sb = handshake["serverBuild"]
    return {
        "oracle": {"commit": pin.commit, "server_build_id": sb["id"], "source": sb["source"],
                   "dirty": sb["dirty"], "sha256": pin.sha256},
        "aeon": aeon_provenance(),
        "rom": rom_provenance(rom, lst),
        "harness": {"tool_sha256": sha256_file(Path(__file__).resolve())},
    }


#: Required leaves per block (the plan's global constraint: aeon commit + dirty flag; oracle
#: serverBuild id/source/dirty; ROM name/crc32/size; DIGEST-SHAPE and DIGEST-ASSEMBLER
#: revision). `False`, `0` and "none" are VALID values; only absent/None/"" is missing.
REQUIRED = {
    "oracle": ("commit", "server_build_id", "source", "dirty", "sha256"),
    "aeon": ("commit", "dirty", "branch"),
    "rom": ("rom", "crc32", "size", "game", "debug", "target", "sigil_revision"),
    "harness": ("tool_sha256",),
}
TOP_KEYS = tuple(REQUIRED)


def _empty(v) -> bool:
    return v is None or v == "" or v == {}


def require_provenance(result: dict) -> None:
    """The writer's gate. Every required leaf of every block must be present and non-empty."""
    for k, leaves in REQUIRED.items():
        blk = result.get(k)
        if not isinstance(blk, dict):
            raise MissingProvenance(f"result has no `{k}` provenance block")
        for leaf in leaves:
            if leaf not in blk or _empty(blk[leaf]):
                raise MissingProvenance(f"provenance `{k}.{leaf}` is missing or empty")


def spawn_pinned(rom, lst):
    """The only spawn the harness uses: sha256 gate, private oracle-aether, handshake gate."""
    from aether_instance import AetherInstance
    pin = load_pin()
    verify_binary(pin)
    inst = AetherInstance(str(rom), str(lst), binary=pin.binary)
    try:
        inst.start()
        verify_pin(pin, inst.handshake)
    except BaseException:
        inst.reap()
        raise
    return inst
