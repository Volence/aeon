#!/usr/bin/env python3
"""Proof that `cart_identity.assert_cart_matches_disk` FIRES — both of its branches.

A precondition check that cannot fail is worse than no check: it prints a reassuring
line and lets every number through. So this boots a REAL headless emulator on a real
ROM and then makes the file on disk disagree with the loaded cart in each of the two
ways it can, requiring `CartMismatch` both times:

  LENGTH   append a byte to the file after the server has loaded it -> the `romBytes`
           branch must raise. This is the truncated / mid-write ROM case.
  CONTENT  flip one byte in the middle, keeping the length -> the readback branch must
           raise, and name the offset. This is the case a length comparison alone
           CANNOT see, and it is the common one here: the four canonical shapes have
           held their sizes across many landings, so a stale cart usually has exactly
           the right length.

  CLEAN    and the negative control: untouched, it must PASS and return the crc.
           Without this leg a check that raised unconditionally would look perfect.

Not a `build.sh` gate: it spawns an emulator, which is the same reason the effects
gates live outside build.sh. Run it by hand, or from a lane that already boots one:

    python3 tools/test_cart_identity.py [--rom s4.debug.bin] [--lst s4.debug.lst]
"""
import argparse
import asyncio
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from suite_paths import add_client_path  # noqa: E402
add_client_path()
from aether import BusClient  # noqa: E402
from aether_instance import aether_emulator  # noqa: E402
from cart_identity import CartMismatch, assert_cart_matches_disk  # noqa: E402


async def run(sock, rom, out):
    b = BusClient(socket_path=sock, client_id="cartpoison", client_name="test_cart_identity")
    await b.connect()
    fails, legs = [], []
    raw = Path(rom).read_bytes()

    # CLEAN — the negative control.
    try:
        crc = await assert_cart_matches_disk(b, rom, out)
        out.append(f"  CLEAN: passed, crc32 {crc:08x}")
    except CartMismatch as e:
        fails.append(f"CLEAN: the check raised on an untouched ROM, so it is not a "
                     f"check, it is a refusal: {e}")
    legs.append("CLEAN (negative control)")

    # LENGTH — the file grows under the loaded cart.
    Path(rom).write_bytes(raw + b"\x00")
    try:
        await assert_cart_matches_disk(b, rom, out)
        fails.append("LENGTH: the check PASSED with the file one byte longer than the "
                     "cart the server holds — the romBytes branch is vacuous")
    except CartMismatch as e:
        out.append(f"  LENGTH: raised, as it must — {str(e)[:110]}...")
    legs.append("LENGTH branch")

    # CONTENT — same length, one byte different, in the middle.
    mid = len(raw) // 2
    poisoned = bytearray(raw)
    poisoned[mid] ^= 0xFF
    Path(rom).write_bytes(bytes(poisoned))
    try:
        await assert_cart_matches_disk(b, rom, out)
        fails.append(f"CONTENT: the check PASSED with byte ${mid:06X} flipped and the "
                     f"length unchanged — the readback branch is vacuous, and a stale "
                     f"cart of the right size would sail through")
    except CartMismatch as e:
        if f"${mid:06X}" not in str(e):
            fails.append(f"CONTENT: raised, but did not name the flipped offset "
                         f"${mid:06X}: {e}")
        else:
            out.append(f"  CONTENT: raised and named offset ${mid:06X}, as it must")
    legs.append("CONTENT branch")

    Path(rom).write_bytes(raw)
    if Path(rom).read_bytes() != raw:
        fails.append("the scratch ROM was not restored")
    await b.close()
    out.append(f"LEGS RUN: {len(legs)} — " + ", ".join(legs))
    if len(legs) != 3:
        fails.append(f"only {len(legs)} of 3 legs ran — an unrun leg is not a pass")
    return fails


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", default="s4.debug.bin")
    ap.add_argument("--lst", default="s4.debug.lst")
    a = ap.parse_args()
    out = []
    tmp = tempfile.mkdtemp(prefix="cart-poison-")
    # The ROM is MUTATED by this test, so it works on a COPY. Poisoning the real
    # s4.debug.bin would leave a corrupt canonical artifact behind if the run died.
    rom = str(Path(tmp) / Path(a.rom).name)
    lst = str(Path(tmp) / Path(a.lst).name)
    shutil.copy(a.rom, rom)
    shutil.copy(a.lst, lst)
    try:
        with aether_emulator(rom, symbols=lst) as sock:
            fails = asyncio.run(run(sock, rom, out))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("\n".join(out))
    if fails:
        print("\nRESULT: FAIL")
        for f in fails:
            print(f"  * {f}")
        return 1
    print("\nRESULT: PASS — 3 legs. The cart check passes an untouched ROM and raises on "
          "BOTH a length change and a same-length content change.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
