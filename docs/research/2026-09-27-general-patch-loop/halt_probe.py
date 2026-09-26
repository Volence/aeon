#!/usr/bin/env python3
"""halt_probe — fly a leg until the game halts, then name the raise_error that halted it.

General-patch-loop parcel, 2026-09-27. A DEBUG leg that "stalls" in leg_probe is either a
camera at the level edge or a raise_error halt. This tells them apart and, for a halt,
recovers the message: RaiseError is `jsr <MDDBG error handler>` followed by the message
bytes, so the handler's stacked return address points AT the message. It scans upper RAM
for longs pointing into ROM whose preceding six bytes are `4EB9 <any>` (jsr abs.l) and
whose target starts with printable text, and prints each candidate. Evidence, not a gate.

  halt_probe.py --rom R --lst L [--dirs right] [--then-dirs down --then-at-x 14400] [--frames 3000]
Prints finished=1.
"""
import argparse
import asyncio
import os
import sys
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "2026-09-25-s4-lag"))
import lag_flythrough_probe as LFP  # noqa: E402
from lag_flythrough_probe import syms, snap  # noqa: E402

SOCKDIR = os.environ.get("TMPDIR") or str(Path.home() / ".cache" / "aeon-tmp")
if SOCKDIR.startswith("/tmp"):
    raise SystemExit("halt_probe: REFUSED, socket dir is under /tmp")
_orig_init = LFP.Server.__init__


def _init(self, rom, lst, tag):
    _orig_init(self, rom, lst, tag)
    self.sock = os.path.join(SOCKDIR, f"halt_{os.getpid()}_{tag}.sock")


LFP.Server.__init__ = _init


async def read_ram(c, addr, n):
    out = b""
    while len(out) < n:
        k = min(1024, n - len(out))
        r = await c.call("emulator/read_memory", {"addr": hex((addr + len(out)) & 0xFFFFFF), "len": k})
        raw = r["bytes"]
        raw = raw[2:] if raw[:2].lower() == "0x" else raw
        out += bytes.fromhex(raw)[:k]
    return out


async def main_async(a):
    rom_bytes = open(a.rom, "rb").read()
    print(f"{os.path.basename(a.rom)} crc={zlib.crc32(rom_bytes):08x}")
    async with LFP.Server(str(Path(a.rom).resolve()), str(Path(a.lst).resolve()), f"h{os.getpid()}") as c:
        s = await syms(c, ["Frame_Counter", "Logic_Tick", "Camera_X", "Camera_Y", "Camera_Target",
                           "Lag_Frame_Count"])
        await c.call("emulator/reset", {})
        await c.call("emulator/run_frames", {"frames": 300})
        dirs = a.dirs.split(",")
        await c.call("emulator/hold", {"buttons": dirs, "down": True})
        still, prev, switched = 0, await snap(c, s), False
        for i in range(a.frames):
            await c.call("emulator/run_frames", {"frames": 1})
            cur = await snap(c, s)
            if a.then_dirs and not switched and cur["cx"] >= a.then_at_x:
                await c.call("emulator/hold", {"buttons": dirs, "down": False})
                dirs = a.then_dirs.split(",")
                await c.call("emulator/hold", {"buttons": dirs, "down": True})
                switched = True
            still = still + 1 if cur["lt"] == prev["lt"] else 0
            prev = cur
            if still >= 60:
                break
        print(f"frame {i}: cam ({cur['cx']},{cur['cy']}) Logic_Tick {'STOPPED (halt)' if still >= 60 else 'running'}")
        if still < 60:
            print("finished=1")
            return
        try:
            regs = await c.call("emulator/registers", {})
            print(f"  registers: {regs}")
        except Exception as e:  # the method may not exist on this server
            print(f"  registers: unavailable ({e})")
        ram = await read_ram(c, 0xFF0000, 0x10000)
        seen = set()
        for off in range(0, len(ram) - 3, 2):
            v = int.from_bytes(ram[off:off + 4], "big")
            if 6 <= v < len(rom_bytes) - 4 and v not in seen and rom_bytes[v - 6:v - 4] == b"\x4e\xb9":
                txt = rom_bytes[v:v + 100].split(b"\0")[0]
                if len(txt) >= 8 and all(32 <= ch < 127 or ch in (0xE0, 0xE1, 0xE2, 0xE3, 0xE8) for ch in txt[:8]):
                    seen.add(v)
                    print(f"  RAM ${0xFF0000 + off:06X} -> ROM ${v:06X}: {txt.decode('latin1')!r}")
    print("finished=1")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", required=True)
    ap.add_argument("--lst", required=True)
    ap.add_argument("--dirs", default="right")
    ap.add_argument("--then-dirs", default="")
    ap.add_argument("--then-at-x", type=int, default=0)
    ap.add_argument("--frames", type=int, default=3000)
    asyncio.run(main_async(ap.parse_args()))


if __name__ == "__main__":
    main()
