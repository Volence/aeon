#!/usr/bin/env python3
"""aether_bytes — the three byte-shaping primitives of the Aether bus, and NOTHING else.

WHY THIS FILE EXISTS: TO BREAK A CYCLE, DELIBERATELY, AT THE BOTTOM.

`cart_identity` needs `read_bytes`/`unprefix` to read a cart back off the bus. It got
them from `aether_instance`. Once `aether_instance` verifies the cart at spawn — which
is the whole point of the CART-VERIFY-COVERAGE parcel, so that 46 tools inherit the
check instead of 3 hand-rolling it — that import runs the other way too and the two
modules import each other.

Three ways out, and the reasoning for the one taken:

  * a function-local `import cart_identity` inside `AetherInstance.start()`. Works,
    costs nothing, and is what you reach for when you do not want to move anything.
    REJECTED: it hides a real layering fact behind an import that only exists at call
    time, and the next reader has no way to see that the two modules are ordered.
  * inline `unprefix`/`read_bytes` into `cart_identity`. Six lines, no new file.
    REJECTED because of WHAT those six lines are: `unprefix` encodes the measured
    0x-prefix trap of the whole legacy->Rust cutover, the one that makes a positional
    slice read two characters off and return a plausible wrong answer with nothing
    raised. A second copy of that is a second place for it to drift.
  * MOVE THE PRIMITIVES DOWN to a leaf with no suite imports of its own. TAKEN. The
    order becomes aether_bytes <- cart_identity <- aether_instance, acyclic, and each
    arrow points at something more primitive than its source.

`aether_instance` RE-EXPORTS all three, so the ~30 tools that say
`from aether_instance import read_bytes, unprefix, write_bytes` keep working unchanged
and nothing in this parcel has to touch them. `tools/test_aether_instance.py` pins
that the re-export is live, because a re-export that quietly stopped being one would
break those tools at import time in a lane nobody runs first.

NO SUITE IMPORTS ON PURPOSE. There is no `from aether import BusClient` here: the
annotations are strings under `from __future__ import annotations`, so this module
does not need the client on `sys.path` and cannot be the thing that fails to find it.
"""
from __future__ import annotations


def unprefix(hexstr: str) -> str:
    """Strip the `0x` / `$` the Rust core puts on every hex byte string it returns.

    ⚠ THE QUIET TRAP OF THE WHOLE ORACLE CUTOVER. The legacy server answered
    `read_memory` with BARE hex ("0100000700000000"); the Rust core answers
    "0x0100000700000000". Callers that do `int(bytes, 16)` are unaffected — but callers
    that SLICE the string positionally (`raw[i*4:i*4+4]`, and several gates here do)
    read two characters off and get a plausible, entirely wrong answer with nothing
    raised. Measured 2026-08-26.

    In the other direction the core is strict rather than quiet: a `bytes` param
    WITHOUT the prefix is refused with -32602 (`bytes` must start with "0x" or "$"),
    which is how the palette_variant conversion announced itself.
    """
    return hexstr[2:] if hexstr[:2].lower() == "0x" else (
        hexstr[1:] if hexstr[:1] == "$" else hexstr)


async def read_bytes(b, addr: int, length: int) -> str:
    """`read_memory` returning BARE hex — the shape the legacy-era gate bodies expect.

    Use this instead of indexing the raw reply whenever the result is sliced.
    """
    return unprefix((await b.call("emulator/read_memory",
                                  {"addr": hex(addr), "len": length}))["bytes"])


async def write_bytes(b, addr: int, hexstr: str) -> dict:
    """`write_memory` from a bare-or-prefixed hex string; the prefix is added if missing."""
    return await b.call("emulator/write_memory",
                        {"addr": hex(addr), "bytes": "0x" + unprefix(hexstr)})
