#!/usr/bin/env python3
"""effects_scene_assert — assert a raster program's SHAPE from an ab_runner sidecar.

Reads one side's `hashes.json` (written by `oracle/linux-port/harness/ab_runner.py` with a
`memory_read` capture) and checks the LIVE raster buffer against expected words. It never talks to
an emulator and never reads a pixel: the measurement is the harness's job, the verdict is this
script's. That split is deliberate and is the rule every effects gate follows — a gate selects and
asserts on report fields; if it needs a fact the report cannot express, the REPORT format grows,
once, and every later gate inherits it.

WHY IT RESOLVES THE BUFFER RATHER THAN NAMING ONE. `Raster_BuildSchedule` re-records the schedule
into whichever of Raster_Buf_A / Raster_Buf_B is not live and then swaps, so which buffer holds the
frame's program depends on frame parity. A gate that read a fixed buffer would sample the stale one
on half of all frames — and would look perfectly stable while measuring nothing, which is the exact
vacuity this tree keeps rediscovering. The scene captures both plus Raster_Active_Buf; this picks
the live one from the pointer.

Usage:
    python3 tools/effects_scene_assert.py OUT/old/hashes.json \\
        --expect-word 1=0x8ADB --expect-word 3=0x8AFF --expect-absent 0x8C89

Exit codes:
    0  every assertion held
    1  at least one assertion failed (the message names the word, expected and actual)
    2  the sidecar is unusable — missing capture, or no memory_read regions (a scene that did not
       capture what the gate needs is a SCENE bug, and is reported separately from a real failure)
"""
import argparse
import json
import sys

# The regions the scenes capture. Named here rather than passed in: a gate that let the caller
# choose region names would let a typo select nothing and pass.
BUF_REGIONS = ("raster_buf_a", "raster_buf_b")
ACTIVE_REGION = "active_buf"


def words(hexstr: str) -> list[int]:
    """A hex byte-string as big-endian 16-bit words — the unit a raster program is written in."""
    b = bytes.fromhex(hexstr)
    return [int.from_bytes(b[i:i + 2], "big") for i in range(0, len(b) - 1, 2)]


def addr_of(region: dict) -> int:
    """A region's address as an int, masked to 24 bits.

    The harness reports `addr` as a hex string ("0x00FF89A2") while a longword READ of
    Raster_Active_Buf comes back as raw hex ("FFFF89A2"); both denote the same 24-bit address once
    masked, and comparing them in any narrower form is how a gate ends up always taking one branch.
    """
    return int(region["addr"], 16) & 0xFFFFFF


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("sidecar", help="path to a side's hashes.json")
    ap.add_argument("--expect-word", action="append", default=[], metavar="INDEX=VALUE",
                    help="word INDEX must equal VALUE, e.g. 1=0x8ADB (repeatable)")
    ap.add_argument("--expect-absent", action="append", default=[], metavar="VALUE",
                    help="VALUE must not appear anywhere in the live buffer (repeatable)")
    ap.add_argument("--expect-present", action="append", default=[], metavar="VALUE",
                    help="VALUE must appear somewhere in the live buffer (repeatable)")
    a = ap.parse_args()

    try:
        side = json.loads(open(a.sidecar).read())
    except (OSError, ValueError) as e:
        print(f"cannot read sidecar {a.sidecar}: {e}", file=sys.stderr)
        return 2

    reads = side.get("memory_read") or {}
    missing = [r for r in (*BUF_REGIONS, ACTIVE_REGION) if r not in reads]
    if missing:
        print(f"sidecar has no memory_read region(s): {', '.join(missing)} — the SCENE did not "
              f"capture what this gate asserts on, so nothing was concluded", file=sys.stderr)
        return 2

    active = int(reads[ACTIVE_REGION]["bytes"], 16) & 0xFFFFFF
    live = next((r for r in BUF_REGIONS if addr_of(reads[r]) == active), None)
    if live is None:
        known = ", ".join(f"{r}={addr_of(reads[r]):#08x}" for r in BUF_REGIONS)
        print(f"Raster_Active_Buf points at {active:#08x}, which is neither captured buffer "
              f"({known}) — the scene captured the wrong regions, or the buffers moved",
              file=sys.stderr)
        return 2

    w = words(reads[live]["bytes"])
    print(f"live buffer: {live} @ {reads[live]['addr']}  ({len(w)} words)")
    print("  " + " ".join(f"{x:04X}" for x in w))

    failures = []
    for spec in a.expect_word:
        if "=" not in spec:
            print(f"--expect-word needs INDEX=VALUE, got {spec!r}", file=sys.stderr)
            return 2
        idx_s, val_s = spec.split("=", 1)
        idx, val = int(idx_s, 0), int(val_s, 0)
        if idx >= len(w):
            failures.append(f"word {idx} is past the captured region ({len(w)} words captured)")
        elif w[idx] != val:
            failures.append(f"word {idx}: expected {val:#06x}, got {w[idx]:#06x}")
    for spec in a.expect_absent:
        val = int(spec, 0)
        if val in w:
            failures.append(f"{val:#06x} is present at word {w.index(val)} but must be ABSENT")
    for spec in a.expect_present:
        val = int(spec, 0)
        if val not in w:
            failures.append(f"{val:#06x} must be PRESENT but does not appear")

    for f in failures:
        print(f"FAIL: {f}", file=sys.stderr)
    if failures:
        return 1

    n = len(a.expect_word) + len(a.expect_absent) + len(a.expect_present)
    if n == 0:
        print("no assertions requested — this gate asserted NOTHING", file=sys.stderr)
        return 2
    print(f"OK — {n} assertion(s) held")
    return 0


if __name__ == "__main__":
    sys.exit(main())
