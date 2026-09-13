"""The per-game band-record tail counts and sizes, read the way the build derives them.

WHY THIS EXISTS (2026-09-13). engine/level/parallax.emp's BAND_EXT_N / BAND_CURVE_N /
BAND_DRIFT_N / BAND_REMAP_N and engine/ram.emp's BAND_*_BYTES used to be pinned LITERALS, one
engine-wide value each, and five tools regex-read those literals. They are now PER GAME: each
one folds the build define GAME_SCANLINE_CAPS, which each game declares in its own
games/<game>/map.toml [defines] table (and which parallax.emp pins to Game.SCANLINE_CAPS).
So "the value of BAND_REMAP_N" no longer exists without naming a game, and a reader that kept
its old regex would either refuse (the derivation is not a literal) or, worse, read the wrong
game's number. This module is the ONE reader, so the tools cannot drift apart again.

WHAT IT READS, AND WHAT IT REFUSES. It follows exactly one spelling:

    const NAME = if (GAME_SCANLINE_CAPS & $MASK) != 0 { VALUE } else { 0 }

in parallax.emp (VALUE 1, the count) and ram.emp (VALUE the tail's byte size), takes the
define from the game's map.toml, and applies the mask. It refuses, loudly, rather than guess:
a missing map.toml or [defines] row, any other spelling (a literal included, which is exactly
the regression the build's own guards also refuse), a parallax.emp mask that disagrees with
ram.emp's for the same tail or with scene_dsl.emp's CAP_* bit, and a ram.emp size that is not
the tail struct's declared `(size: N)`. Every refusal is `Unreadable`; callers map it onto
their own vocabulary (UNMEASURABLE, SystemExit).

WHY map.toml AND NOT THE BUILT LISTING. The listing carries the define too (an `EQU
GAME_SCANLINE_CAPS` row), but several readers are probes and unit tests with no listing in
hand, and the build refuses a map.toml row that disagrees with the game's contract, so for a
tree that builds the two cannot differ.
"""

import os
import re

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - python < 3.11
    tomllib = None

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DEFINE = "GAME_SCANLINE_CAPS"

# (count in parallax.emp, byte size in ram.emp, tail struct in parallax.emp, CAP_* bit in
# scene_dsl.emp), in RECORD ORDER: band_record lays the tails out in exactly this order after
# the legacy band_entry prefix, which is what makes `record_offsets` below a sum.
TAILS = (
    ("BAND_EXT_N",   "BAND_EXT_BYTES",   "band_ext",   "CAP_MULTI_DEFORM_TABLE"),
    ("BAND_CURVE_N", "BAND_CURVE_BYTES", "band_curve", "CAP_FACTOR_CURVE"),
    ("BAND_DRIFT_N", "BAND_DRIFT_BYTES", "band_drift", "CAP_BAND_DRIFT"),
    ("BAND_REMAP_N", "BAND_REMAP_BYTES", "band_remap", "CAP_ROW_REMAP"),
)

PARALLAX = os.path.join("engine", "level", "parallax.emp")
RAM = os.path.join("engine", "ram.emp")
SCENE_DSL = os.path.join("engine", "level", "scene_dsl.emp")


class Unreadable(Exception):
    """The tail geometry could not be read for this game. Never a default."""


def _read(repo, rel):
    p = os.path.join(repo, rel)
    try:
        with open(p, encoding="utf-8") as f:
            return f.read()
    except OSError as e:
        raise Unreadable(f"cannot read {rel}: {e}") from e


def game_caps_define(game, repo=REPO):
    """GAME_SCANLINE_CAPS from games/<game>/map.toml's [defines] table."""
    if tomllib is None:
        raise Unreadable("tomllib is unavailable (python < 3.11); cannot read map.toml")
    rel = os.path.join("games", game, "map.toml")
    try:
        doc = tomllib.loads(_read(repo, rel))
    except tomllib.TOMLDecodeError as e:
        raise Unreadable(f"{rel} does not parse: {e}") from e
    defines = doc.get("defines")
    if not isinstance(defines, dict) or DEFINE not in defines:
        raise Unreadable(
            f"{rel} declares no [defines] {DEFINE} row. The engine sizes its band records "
            f"from it, so a game without one does not build; reading 'no capabilities' out "
            f"of its absence would be a guess")
    v = defines[DEFINE]
    if isinstance(v, bool) or not isinstance(v, int):
        raise Unreadable(f"{rel} [defines] {DEFINE} is {v!r}, not an integer")
    return v


def _derivation(text, rel, name):
    """(mask, value) out of `const NAME = if (GAME_SCANLINE_CAPS & $MASK) != 0 { V } else { 0 }`."""
    m = re.search(
        r"^\s*(?:pub\s+)?const\s+" + re.escape(name)
        + r"\s*=\s*if \(" + DEFINE + r" & \$([0-9A-Fa-f]+)\) != 0 \{ (\d+) \} else \{ 0 \}",
        text, re.M)
    if not m:
        raise Unreadable(
            f"`{name}` in {rel} is not the per-game fold "
            f"`if ({DEFINE} & $MASK) != 0 {{ V }} else {{ 0 }}`. A literal there is the "
            f"engine-wide shape this tree retired on 2026-09-13; any other spelling this reader "
            f"cannot evaluate, and it refuses rather than guess")
    return int(m.group(1), 16), int(m.group(2))


def _struct_size(text, struct):
    m = re.search(r"pub struct " + re.escape(struct) + r" \(size: (\d+)\)", text)
    if not m:
        raise Unreadable(f"cannot size `{struct}` in {PARALLAX}")
    return int(m.group(1))


def _cap_bit(text, cap):
    m = re.search(r"^pub const " + re.escape(cap) + r"\s*=\s*\$([0-9A-Fa-f]+)", text, re.M)
    if not m:
        raise Unreadable(f"`{cap}` is not declared in {SCENE_DSL}")
    return int(m.group(1), 16)


def geometry(game, repo=REPO):
    """Everything the readers need, checked for internal agreement.

    Returns {"caps": int, "counts": {BAND_*_N: 0|1}, "bytes": {BAND_*_BYTES: int},
    "sizes": {band_ext: int, ...}, "entry": BAND_ENTRY_LEN}."""
    caps = game_caps_define(game, repo)
    ptext = _read(repo, PARALLAX)
    rtext = _read(repo, RAM)
    stext = _read(repo, SCENE_DSL)
    m = re.search(r"^\s*const\s+BAND_ENTRY_LEN\s*=\s*(\d+)", rtext, re.M)
    if not m:
        raise Unreadable(f"cannot read BAND_ENTRY_LEN from {RAM}")
    out = {"caps": caps, "counts": {}, "bytes": {}, "sizes": {}, "entry": int(m.group(1))}
    for count, nbytes, struct, cap in TAILS:
        pmask, pval = _derivation(ptext, PARALLAX, count)
        rmask, rval = _derivation(rtext, RAM, nbytes)
        size = _struct_size(ptext, struct)
        bit = _cap_bit(stext, cap)
        if pval != 1:
            raise Unreadable(f"{PARALLAX}'s {count} folds to {pval}, not 1, when its bit is set")
        if not (pmask == rmask == bit):
            raise Unreadable(
                f"the {struct} tail's masks disagree: {PARALLAX} {count} reads ${pmask:04X}, "
                f"{RAM} {nbytes} reads ${rmask:04X}, {SCENE_DSL} {cap} is ${bit:04X}")
        if rval != size:
            raise Unreadable(
                f"{RAM}'s {nbytes} is {rval} when set, but {struct} is (size: {size})")
        on = 1 if caps & bit else 0
        out["counts"][count] = on
        out["bytes"][nbytes] = size * on
        out["sizes"][struct] = size
    return out


def tail_counts(game, repo=REPO):
    """{BAND_EXT_N: 0|1, BAND_CURVE_N: ..., BAND_DRIFT_N: ..., BAND_REMAP_N: ...} for `game`."""
    return geometry(game, repo)["counts"]


def tail_bytes(game, repo=REPO):
    """{BAND_EXT_BYTES: n, ...} for `game`: engine/ram.emp's four tail sizes as it folds them."""
    return geometry(game, repo)["bytes"]


def record_stride(game, repo=REPO):
    """sizeof(band_record) for `game` = BAND_ENTRY_LEN + every tail this game carries."""
    g = geometry(game, repo)
    return g["entry"] + sum(g["bytes"].values())


def tail_offset(game, struct, repo=REPO):
    """The record offset of `struct`'s tail for `game`: the legacy prefix plus every tail
    BEFORE it in record order. Defined whether or not this game carries the tail (a
    zero-length array still has a position), exactly as offsetof is."""
    g = geometry(game, repo)
    off = g["entry"]
    for _count, nbytes, s, _cap in TAILS:
        if s == struct:
            return off
        off += g["bytes"][nbytes]
    raise Unreadable(f"no capability tail named `{struct}`")


if __name__ == "__main__":  # pragma: no cover - a convenience readout
    import sys
    for game in (sys.argv[1:] or ["sonic4", "demo"]):
        g = geometry(game)
        print(f"{game}: {DEFINE}=${g['caps']:04X} counts={g['counts']} bytes={g['bytes']} "
              f"stride={g['entry'] + sum(g['bytes'].values())}")
