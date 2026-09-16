#!/usr/bin/env python3
"""emp_consts — read a `.emp` module's top-level `const` values out of the SOURCE.

WHY THIS EXISTS rather than reading the listing. A witness that needs a number must
take it from an authority, and the obvious authority is the build's own `.lst`. But
the listing carries only the names the 68k side USES: measured 2026-09-12, the
config-A listing has 802 `EQU` lines and exactly SIX beginning `SND_` — the mailbox
slot addresses and the mirror source pointers. Every Z80-side sound constant
(`SND_DAC_RATE_HZ`, `SND_LOOP_CYC`, `Z80_CLOCK_HZ`, `SND_RING_LEAD_TARGET`, the
`SND_STATE_BASE` field offsets) is consumed only inside the Z80 driver, which is
assembled into its own blob by `emit_sound_blob`, and NONE of its names reach the
68k listing at all. So for those constants the source file IS the authority, and
the alternative — typing the number into the witness — is the thing the house rules
call copying a number from a nearby pin.

This reads only `pub const NAME = <int expr>` / `const NAME = <int expr>` forms with
a literal or a simple arithmetic right-hand side over names already read, which is
what the sound constants are. Anything it cannot fold it reports as absent: a
witness must then say it could not derive its number, never guess one.

    from emp_consts import emp_consts
    c = emp_consts("engine/sound/sound_constants.emp")
    rate = c["Z80_CLOCK_HZ"] // c["SND_LOOP_CYC"]
"""
from __future__ import annotations

import re
from pathlib import Path

_CONST = re.compile(r"^\s*(?:pub\s+)?const\s+(\w+)\s*=\s*([^/\n]+?)\s*(?://.*)?$")


def _to_py(expr: str) -> str:
    """`$FF` -> `0xFF`, `%1010` -> `0b1010`; everything else is already Python-ish."""
    expr = re.sub(r"\$([0-9A-Fa-f]+)", lambda m: str(int(m.group(1), 16)), expr)
    expr = re.sub(r"%([01]+)", lambda m: str(int(m.group(1), 2)), expr)
    return expr


def emp_consts(path: str | Path, seed: dict[str, int] | None = None) -> dict[str, int]:
    """{name: int} for every top-level const whose value folds to an int.

    `seed` PRE-LOADS THE FOLDING SCOPE WITH NAMES FROM ANOTHER MODULE, and it exists
    because the interesting derived constants in this tree are cross-file. A game's act
    descriptor writes `const ACT_W = GRID_W << SECTION_SIZE_SHIFT` and
    `const CENTRE_X_MAX = ACT_W - SCREEN_WIDTH + CAM_SCREEN_HALF_W`: every operand but
    `GRID_W` lives in `engine/system/constants.emp`, so a same-file-only fold drops all
    four camera-band constants and a caller that wants them has to RESTATE the arithmetic
    in Python. That restatement is the failure this module's own header names — the
    number stops coming from the authority the moment its formula does. Seeded, the
    formula still comes from the `.emp` line and only the leaf values are imported.

    The seed is read-only from the caller's point of view: the returned dict carries the
    file's own consts only, so a caller cannot mistake an imported leaf for a declaration
    in the file it asked about.
    """
    vals: dict[str, int] = {}
    scope: dict[str, int] = dict(seed or {})
    for line in Path(path).read_text(errors="replace").splitlines():
        m = _CONST.match(line)
        if not m:
            continue
        name, expr = m.group(1), _to_py(m.group(2))
        if not re.fullmatch(r"[\w\s+\-*/()<>|&]+", expr):
            continue
        try:
            v = eval(expr, {"__builtins__": {}}, dict(scope))  # noqa: S307 - closed env
        except Exception:
            continue
        if isinstance(v, int) and not isinstance(v, bool):
            vals[name] = v
            scope[name] = v
    return vals
