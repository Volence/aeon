#!/usr/bin/env python3
"""Read the page-streaming mode bytes after boot. Usage: residency_read.py <rom> <lst>"""
import asyncio
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lag_flythrough_probe import Server, rd, syms  # noqa: E402

NAMES = ["PageIn_Fully_Resident", "PageCache_Direct_Map", "PageIn_Pool_Pages"]


async def go(rom, lst):
    async with Server(str(Path(rom).resolve()), str(Path(lst).resolve()), "res") as c:
        s = await syms(c, NAMES)
        await c.call("emulator/reset", {})
        await c.call("emulator/run_frames", {"frames": 300})
        crc = "%08x" % zlib.crc32(open(rom, "rb").read())
        vals = {n: await rd(c, s[n], 2 if n == "PageIn_Pool_Pages" else 1) for n in NAMES if n in s}
        print(Path(rom).name, crc, vals, "missing:", [n for n in NAMES if n not in s])


asyncio.run(go(sys.argv[1], sys.argv[2]))
