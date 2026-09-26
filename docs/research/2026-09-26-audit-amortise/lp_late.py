#!/usr/bin/env python3
"""The perf survey's leg_probe.py, unchanged, except that its one-byte --read-at-end
read of the symbol Page_Audit_Late is widened to the whole u16 word (the counter of
nametable slices the TICK call had to audit because the idle slot had no room can pass
255). Every other argument is leg_probe's own; see docs/research/2026-09-25-perf-survey/."""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "2026-09-25-perf-survey"))
import leg_probe as LP  # noqa: E402

lst = sys.argv[sys.argv.index("--lst") + 1]
m = re.search(r"^\(0\) \d+/([0-9A-F]+) :\s+Page_Audit_Late:", Path(lst).read_text(), re.M)
if not m:
    print("COULD NOT RUN: Page_Audit_Late is not in the listing (a pre-amortise ROM?)")
    sys.exit(2)
LATE = int(m.group(1), 16) & 0xFFFFFF
orig = LP.rd


async def rd(c, addr, n):
    return await orig(c, addr, 2 if (addr == LATE and n == 1) else n)


LP.rd = rd
LP.main()
