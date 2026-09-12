#!/usr/bin/env python3
"""cart_identity — prove the server's loaded cart IS the file on disk, before measuring.

WHY. A witness spells a ROM path, a server reports a plausible `romPath`, and every
number after that is about whatever cart is actually in the machine. The two ways
that goes wrong are both quiet:

  * the ROM was being REWRITTEN when the server loaded it — a lane rebuilding, or a
    broad `pkill` landing on a `sigil` mid-write — so the cart is truncated; and
  * the path is right and the bytes are old, which is the stale-shim failure the
    suite has already paid for: a correct-looking `romPath` serving a previous
    freeze.

Neither raises. Both produce a full run with a clean leg count and wrong numbers.

The house pattern (`tools/fg_left_edge_gate.py:409-412`) compares the server's
`romBytes` against the file's length and raises rather than returning a number. This
module does that AND reads the whole cart back through the bus to compare bytes,
because a length match is not an identity: a rebuild that changes content without
changing size passes the length check, and for this tree that is the common case —
the four canonical shapes have held their sizes across many landings.

Cost, measured 2026-09-12: 847,885 bytes read back in 4 KiB chunks over the Unix
socket is well under a second, against witness runs of minutes. There is no reason
to prefer the weaker check.

    from cart_identity import assert_cart_matches_disk
    await assert_cart_matches_disk(bus, rom_path, out)     # appends one line to `out`

Raises `CartMismatch`. A caller must let that propagate, or convert it to its own
"could not ask the question" exit — never to a zero or a green.
"""
from __future__ import annotations

import zlib
from pathlib import Path

from aether_instance import read_bytes, unprefix

CHUNK = 0x1000
# The 68000 cartridge window. A cart larger than this is banked and the tail is not
# linearly readable, so the readback is capped here and the cap is REPORTED rather
# than silently shrinking what was compared.
CART_WINDOW = 0x400000


class CartMismatch(RuntimeError):
    """The cart in the machine is not the file on disk — never reported as a pass."""


async def assert_cart_matches_disk(b, rom_path, out=None, full=True):
    """Raise unless the loaded cart is the bytes of `rom_path`. Returns its crc32."""
    raw = Path(rom_path).read_bytes()
    crc = zlib.crc32(raw) & 0xFFFFFFFF
    st = await b.call("emulator/status", {})
    n_srv = st.get("romBytes")
    if n_srv is None:
        raise CartMismatch(
            f"`emulator/status` reported no `romBytes`, so this bus cannot say what cart "
            f"it holds and nothing measured against it is attributable to {rom_path}")
    if n_srv != len(raw):
        raise CartMismatch(
            f"the server holds {n_srv} cart bytes and {rom_path} is {len(raw)} on disk. "
            f"Either the ROM was rewritten under this run or the server loaded a "
            f"different file (its romPath says {st.get('romPath')!r})")
    if not full:
        if out is not None:
            out.append(f"  cart: romBytes {n_srv} == disk, crc32 {crc:08x} (length only)")
        return crc
    n = min(len(raw), CART_WINDOW)
    got, chunks = 0, []
    while got < n:
        step = min(CHUNK, n - got)
        chunks.append(bytes.fromhex(unprefix(await read_bytes(b, got, step))))
        got += step
    back = b"".join(chunks)
    if back != raw[:n]:
        bad = next(i for i, (x, y) in enumerate(zip(back, raw)) if x != y)
        raise CartMismatch(
            f"the cart read back from the bus differs from {rom_path} at offset "
            f"${bad:06X} (disk ${raw[bad]:02X}, machine ${back[bad]:02X}); the lengths "
            f"matched, so this is a CONTENT mismatch — a stale or mid-write ROM")
    if out is not None:
        out.append(f"  cart: romBytes {n_srv} == disk, and {n} bytes read back from the "
                   f"bus are byte-identical to the file; crc32 {crc:08x}"
                   + ("" if n == len(raw) else
                      f" (readback capped at the ${CART_WINDOW:06X} cart window; "
                      f"{len(raw) - n} banked bytes not compared)"))
    return crc
