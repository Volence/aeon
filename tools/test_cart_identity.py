#!/usr/bin/env python3
"""test_cart_identity — proof that `cart_identity.assert_cart_matches_disk` FIRES.

A precondition check that cannot fail is worse than no check: it prints a reassuring
line and lets every number through. So both of its branches are driven until they
raise, and the clean case is driven too — without that leg an unconditional refusal
would look perfect.

TWO HALVES, and the split is deliberate.

  The PYTEST half (the `test_*` functions below) drives the real
  `assert_cart_matches_disk` against a FAKE bus: a 20-line stand-in that answers
  `emulator/status` and `emulator/read_memory` out of a bytes object. Pure Python,
  no emulator, microseconds — so it joins `build.sh`'s pre-build lane and the check
  has an automated runner. That is the point: a file named `test_*` that pytest
  collects NOTHING from promises coverage it does not deliver, which is how
  `tools/test_tool_selftests.py` came to exist in the first place.

  The EMULATOR half (`--emulator`) boots a real headless `oracle-aether` on a COPY of
  a real ROM and mutates the file under the loaded cart. It is kept OUT of pytest on
  the same ground this directory already states twice: `aether_instance.py
  --poison-legacy` ("Kept out of pytest deliberately: it boots the legacy server")
  and `palette_variant_gate.py` ("it boots a headless emulator and belongs where the
  emulator lanes are"). It is the proof that the fake bus is not a fiction.

WHAT EACH BRANCH CATCHES:

  LENGTH   a file that grew or shrank under the loaded cart — the truncated or
           mid-write ROM.
  CONTENT  one byte different at unchanged length — the case a length comparison
           CANNOT see, and the common one here, because the four canonical shapes
           have held their sizes across many landings. A stale cart usually has
           exactly the right length.

    python3 -m pytest tools/test_cart_identity.py -q       # the fake-bus half
    python3 tools/test_cart_identity.py --emulator         # the real-ROM half
"""
import argparse
import asyncio
import shutil
import sys
import tempfile
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from suite_paths import add_client_path  # noqa: E402
add_client_path()
from cart_identity import CartMismatch, assert_cart_matches_disk  # noqa: E402

CART = bytes((i * 37 + 11) & 0xFF for i in range(0x2000))


class FakeBus:
    """The two calls `assert_cart_matches_disk` makes, answered from `cart`.

    Deliberately NOT a mock of the whole bus: it answers exactly `emulator/status`
    and `emulator/read_memory` and raises on anything else, so a future version of
    the check that reaches for a third method fails here loudly instead of being
    silently satisfied.
    """

    def __init__(self, cart, path="/fake/rom.bin"):
        self.cart, self.path = cart, path

    async def call(self, method, params):
        if method == "emulator/status":
            return {"romBytes": len(self.cart), "romPath": self.path}
        if method == "emulator/read_memory":
            a = int(str(params["addr"]).replace("0x", ""), 16)
            return {"bytes": "0x" + self.cart[a:a + params["len"]].hex()}
        raise AssertionError(f"the check reached for an unexpected method: {method}")


def _rom(tmp_path, data):
    p = tmp_path / "rom.bin"
    p.write_bytes(data)
    return str(p)


def test_clean_cart_passes_and_returns_its_crc(tmp_path):
    """The negative control. Without it, a check that always raised would look ideal."""
    rom = _rom(tmp_path, CART)
    out = []
    crc = asyncio.run(assert_cart_matches_disk(FakeBus(CART), rom, out))
    assert crc == zlib.crc32(CART) & 0xFFFFFFFF
    assert len(out) == 1 and "byte-identical" in out[0]


def test_length_mismatch_raises(tmp_path):
    """The file grew under the loaded cart: the romBytes branch.

    The message is required to name BOTH lengths, because "they differ" without the
    numbers is the hardest kind of refusal to act on. When this row is run against a
    cart_identity with its length branch neutered it still goes red, on the SHORT
    readback instead — which is how that path's StopIteration bug was found.
    """
    rom = _rom(tmp_path, CART + b"\x00")
    try:
        asyncio.run(assert_cart_matches_disk(FakeBus(CART), rom, []))
    except CartMismatch as e:
        assert str(len(CART)) in str(e) and str(len(CART) + 1) in str(e), str(e)
        return
    raise AssertionError("a one-byte length difference PASSED — the romBytes branch "
                         "is vacuous and a truncated ROM would be measured")


def test_a_short_readback_is_named_as_such(tmp_path):
    """The SHORT-readback path, reached when lengths agree but the bus returns less.

    This is the path whose `next(...)` raised StopIteration — surfacing as an
    unrelated `RuntimeError: generator raised StopIteration` from asyncio rather than
    as a message — in the one code path whose whole job is to say what went wrong.
    """
    class Short(FakeBus):
        async def call(self, method, params):
            r = await FakeBus.call(self, method, params)
            if method == "emulator/status":
                r["romBytes"] = len(CART) + 1      # claim one more than it will serve
            return r

    rom = _rom(tmp_path, CART + b"\x00")
    try:
        asyncio.run(assert_cart_matches_disk(Short(CART), rom, []))
    except CartMismatch as e:
        assert "SHORT readback" in str(e), str(e)
        return
    raise AssertionError("a short readback PASSED — the comparison silently compared "
                         "fewer bytes than it claimed to")


def test_same_length_content_mismatch_raises_and_names_the_offset(tmp_path):
    """One byte different at unchanged length: the branch a length check cannot have."""
    bad = bytearray(CART)
    off = len(CART) // 2
    bad[off] ^= 0xFF
    rom = _rom(tmp_path, bytes(bad))
    try:
        asyncio.run(assert_cart_matches_disk(FakeBus(CART), rom, []))
    except CartMismatch as e:
        assert f"${off:06X}" in str(e), f"raised but did not name offset ${off:06X}: {e}"
        assert "CONTENT" in str(e)
        return
    raise AssertionError("a same-length content difference PASSED — the readback branch "
                         "is vacuous, and a stale cart of the right size is exactly what "
                         "that lets through")


def test_absent_rombytes_raises(tmp_path):
    """A server that cannot say what it holds is not a server to measure against."""
    class Mute(FakeBus):
        async def call(self, method, params):
            if method == "emulator/status":
                return {}
            return await FakeBus.call(self, method, params)

    rom = _rom(tmp_path, CART)
    try:
        asyncio.run(assert_cart_matches_disk(Mute(CART), rom, []))
    except CartMismatch as e:
        assert "romBytes" in str(e)
        return
    raise AssertionError("an absent romBytes PASSED — the check cannot tell what cart it "
                         "is looking at and said nothing")


def test_length_only_mode_cannot_see_a_content_change(tmp_path):
    """`full=False` is the weaker house check, and this pins what it MISSES.

    Not a complaint about the flag: it exists for a caller that cannot afford the
    readback. The test is here so nobody reaches for it believing it proves identity.
    """
    bad = bytearray(CART)
    bad[7] ^= 0xFF
    rom = _rom(tmp_path, bytes(bad))
    out = []
    crc = asyncio.run(assert_cart_matches_disk(FakeBus(CART), rom, out, full=False))
    assert crc == zlib.crc32(bytes(bad)) & 0xFFFFFFFF
    assert "length only" in out[0]


# ------------------------------------------------------------------ the emulator half

async def _emulator_legs(sock, rom, out):
    from aether import BusClient
    b = BusClient(socket_path=sock, client_id="cartpoison",
                  client_name="test_cart_identity")
    await b.connect()
    fails, legs = [], []
    raw = Path(rom).read_bytes()

    try:
        crc = await assert_cart_matches_disk(b, rom, out)
        out.append(f"  CLEAN: passed, crc32 {crc:08x}")
    except CartMismatch as e:
        fails.append(f"CLEAN: raised on an untouched ROM — that is a refusal, not a "
                     f"check: {e}")
    legs.append("CLEAN (negative control)")

    Path(rom).write_bytes(raw + b"\x00")
    try:
        await assert_cart_matches_disk(b, rom, out)
        fails.append("LENGTH: PASSED with the file one byte longer than the cart the "
                     "server holds — the romBytes branch is vacuous")
    except CartMismatch as e:
        out.append(f"  LENGTH: raised, as it must — {str(e)[:100]}...")
    legs.append("LENGTH branch")

    mid = len(raw) // 2
    poisoned = bytearray(raw)
    poisoned[mid] ^= 0xFF
    Path(rom).write_bytes(bytes(poisoned))
    try:
        await assert_cart_matches_disk(b, rom, out)
        fails.append(f"CONTENT: PASSED with byte ${mid:06X} flipped at unchanged length "
                     f"— the readback branch is vacuous")
    except CartMismatch as e:
        if f"${mid:06X}" not in str(e):
            fails.append(f"CONTENT: raised but did not name ${mid:06X}: {e}")
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
    ap.add_argument("--emulator", action="store_true",
                    help="boot a real headless oracle-aether and poison a COPY of the ROM")
    ap.add_argument("--rom", default="s4.debug.bin")
    ap.add_argument("--lst", default="s4.debug.lst")
    a = ap.parse_args()
    if not a.emulator:
        ap.error("pass --emulator for the real-ROM half; the fake-bus half runs under "
                 "pytest (python3 -m pytest tools/test_cart_identity.py)")
    from aether_instance import aether_emulator
    out = []
    tmp = tempfile.mkdtemp(prefix="cart-poison-")
    # This MUTATES the ROM, so it works on a COPY. Poisoning the real s4.debug.bin
    # would leave a corrupt canonical artifact behind if the run died.
    rom = str(Path(tmp) / Path(a.rom).name)
    lst = str(Path(tmp) / Path(a.lst).name)
    shutil.copy(a.rom, rom)
    shutil.copy(a.lst, lst)
    try:
        with aether_emulator(rom, symbols=lst) as sock:
            fails = asyncio.run(_emulator_legs(sock, rom, out))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("\n".join(out))
    if fails:
        print("\nRESULT: FAIL")
        for f in fails:
            print(f"  * {f}")
        return 1
    print("\nRESULT: PASS — 3 legs on a REAL cart. The check passes an untouched ROM and "
          "raises on both a length change and a same-length content change.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
