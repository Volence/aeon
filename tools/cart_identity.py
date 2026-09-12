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

Cost, RE-MEASURED 2026-09-12 rather than inherited. What this module shipped with was
"847,885 bytes ... well under a second" — a BOUND, not a figure, and the measurement
below is inside it, so nothing here corrects it. Two things did need re-deriving: the
byte count (the ROM has changed size since) and how far inside that bound the answer
actually is, because "under a second" is the kind of headroom that decides whether a
check can be unconditional. Method: spawn twice and subtract —
`cart_check="length"` pays everything except the readback, so full-minus-length IS the
readback (`python3 tools/aether_instance.py --smoke` prints both operands, because a
difference without them is not a measurement).

  s4.debug.bin, 846,601 bytes, 207 chunks of 4 KiB, 4 runs, load average 6.4-6.6 (a
  four-shape build was running alongside):

    spawn + handshake + LENGTH check   0.061 - 0.062 s
    spawn + handshake + FULL   check   0.097 - 0.100 s
    -> THE READBACK COSTS  +0.035 to +0.038 s

Against witness runs of tens of seconds to minutes, and paid once per spawn. There is
no reason to prefer the weaker check, and the weaker one is the one that cannot see a
stale cart of the right size.

    from cart_identity import assert_cart_matches_disk
    await assert_cart_matches_disk(bus, rom_path, out)     # appends one line to `out`

Raises `CartMismatch`. A caller must let that propagate, or convert it to its own
"could not ask the question" exit — never to a zero or a green.

SINCE 2026-09-12 MOST CALLERS DO NOT CALL THIS AT ALL: `aether_instance.AetherInstance`
runs it on every spawn, so any tool that goes through `aether_emulator(...)` /
`AetherInstance(...)` inherits it. Call it by hand only when you reach a bus another
way, or after something that can CHANGE the cart under a live server — which is what
`reload_rom_verified` below is for.
"""
from __future__ import annotations

import zlib
from pathlib import Path

# Imported from the LEAF, not from `aether_instance`. `aether_instance` imports THIS
# module now, so taking the primitives from it would be a cycle; see aether_bytes.py's
# docstring for the three ways out and why the primitives moved down.
from aether_bytes import read_bytes, unprefix

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
        # The readback can differ in two ways, and the SHORT case has to be handled
        # explicitly: `next(...)` over the differing positions raises StopIteration
        # when `back` is merely a PREFIX of the file, and a bare StopIteration inside
        # a coroutine surfaces as an unrelated `RuntimeError: generator raised
        # StopIteration` — a confusing crash in the one code path whose whole job is
        # to say clearly what went wrong. Found by this file's own red-first run
        # (tools/test_cart_identity.py), which neuters the length branch and so
        # reaches here with a short readback.
        if len(back) != n:
            raise CartMismatch(
                f"the bus returned {len(back)} of the {n} cart bytes requested for "
                f"{rom_path} — a SHORT readback, so the cart cannot be compared at all")
        bad = next((i for i, (x, y) in enumerate(zip(back, raw)) if x != y), None)
        if bad is None:
            raise CartMismatch(
                f"the cart read back from the bus is not equal to {rom_path} yet no "
                f"byte in the first {n} differs — the comparison itself is broken and "
                f"no number from this run is attributable")
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


async def reload_rom_verified(b, rom_path, out=None, full=True):
    """`emulator/reload_rom` AND then prove the machine actually holds that file.

    THE SECOND HOLE, and it is a different one from the stale preload. Sigil's framing,
    which applies here unchanged: **`reload_rom` says *load this*; nothing confirms the
    emulator now holds it.** A spawn-time check defends the cart the server booted with
    and says nothing about the cart after a reload — so a load that silently did not
    take is undefended even in a tool that reloads BECAUSE it reloads. The reply is not
    the evidence: a method that returned a dict and changed nothing produces exactly the
    same log as one that worked.

    There is a measured near-miss in this tree already. `tools/evict_witness.py` reloads
    and then hashes the cart — good — but `emulator/reload_rom` re-binds the symbol table
    it already holds rather than re-reading the `.lst`, and REPORTS `symbolsDropped:
    false`, which reads as reassurance (oracle's own finding, 2026-09-04). A reply field
    that says nothing while looking like it says something is the whole hazard class.

    Uses the same comparison as the spawn-time check, so a reload is defended exactly as
    well as a boot, and raises the same `CartMismatch`.
    """
    await b.call("emulator/reload_rom", {"path": str(Path(rom_path).resolve())})
    return await assert_cart_matches_disk(b, rom_path, out, full=full)
