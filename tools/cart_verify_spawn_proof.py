#!/usr/bin/env python3
"""cart_verify_spawn_proof — prove the SPAWN-TIME cart check fires, on a real server.

THE PROOF THE DEFERRED_WORK ROW ASKED FOR, in its own words: *point a witness at a
DIFFERENT ROM and require `UNMEASURABLE`.* This is that, with the discriminating
detail that makes it worth running — **the different ROM is the SAME SIZE.** A
truncated file is the easy case; every length check in the tree already catches it.
The case that costs you a clean run with wrong numbers is a cart of exactly the right
length and the wrong bytes, which is what a stale preload actually looks like here,
because the four canonical ROM shapes have held their sizes across many landings.

HOW THE POISON IS APPLIED, and why this shape and not a race. A witness names ROM A;
the machine holds ROM B. Reproducing that by rewriting the file while the server boots
is a race, and a proof that sometimes does not poison is a proof that sometimes passes
for the wrong reason. So the poison is deterministic and applied at the one seam where
the two can be separated: `AetherInstance.argv()` builds the server's command line from
`self.rom`, and `self.rom` is also what the check compares against. Patch `argv` to
launch ROM B and `self.rom` still says ROM A — server holds B, tool named A, nothing
racy, exactly the failure in the field. This is the same move
`aether_instance.py --poison-legacy` makes against the SERVER assertion: spawn the
thing the check is supposed to refuse and require the refusal.

FIVE LEGS, and the leg count is checked, because an unrun leg is not a pass:

  1 CONTROL   clean ROM, `full` -> the spawn must SUCCEED. Without this leg a check
              that refused everything would score perfectly.
  2 POISON    same-size different-content cart, `full` -> must raise `CartMismatch`
              and NAME the differing offset.
  3a CONTROL  the SAME witness command, UNPOISONED, must exit ZERO and mention no
              cart at all. Run FIRST. Without it, leg 3's non-zero exit is not
              evidence: a witness that is simply broken reads identically.
  3 WITNESS   a real witness tool (default `tools/raster_off_gate.py`), run as a
              SUBPROCESS under the poison, must exit NON-ZERO and say CartMismatch.
              Legs 1-2 prove the seam; this one proves a tool that never heard of
              `cart_identity` now inherits it.
  4 WEAKNESS  the same poison with `cart_check="length"` -> must PASS, and must have
              printed WEAKER on stderr. This pins what the opt-down cannot see. It is
              not a complaint about the flag; it is the reason the flag is not the
              default and the reason it is loud.

    python3 tools/cart_verify_spawn_proof.py [--rom s4.debug.bin] [--lst s4.debug.lst]
    python3 tools/cart_verify_spawn_proof.py --witness tools/band_witness.py

Exit 0 = all five legs ran and behaved. 1 = a leg misbehaved. 2 = could not run.
NEVER exits 0 on a leg it could not run.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aether_instance import (AetherInstance, CART_CHECK_LENGTH,  # noqa: E402
                             CartMismatch, SERVER)

POISON_ENV = "AEON_CART_PROOF_SERVE"

# The `sitecustomize.py` dropped into a temp dir and put FIRST on PYTHONPATH for leg 3.
# Python's `site` imports it automatically at startup, so the witness is poisoned before
# its first line runs and needs no flag, no import and no edit. It lives ONLY inside this
# run's temp dir and is deleted with it -- there is no committed hook a real run could
# trip over, which is the point: a poison that can be enabled from the environment of a
# NORMAL run is the same hazard class as the stale cart it is testing for.
SITECUSTOMIZE = '''
import os, sys
_serve = os.environ.get({env!r})
if _serve:
    sys.path.insert(0, {tools!r})
    import aether_instance as _ai
    _orig = _ai.AetherInstance.argv
    def _poisoned(self):
        a = _orig(self)
        return [a[0], _serve] + a[2:]      # launch a DIFFERENT cart; self.rom unchanged
    _ai.AetherInstance.argv = _poisoned
'''


def _poison_argv(inst: AetherInstance, serve: str) -> None:
    """Make this instance LAUNCH `serve` while still claiming `self.rom`."""
    orig = inst.argv

    def poisoned():
        a = orig()
        return [a[0], serve] + a[2:]
    inst.argv = poisoned                                   # type: ignore[method-assign]


def main() -> int:
    ap = argparse.ArgumentParser()
    aeon = Path(__file__).resolve().parent.parent
    ap.add_argument("--rom", default=str(aeon / "s4.debug.bin"))
    ap.add_argument("--lst", default=str(aeon / "s4.debug.lst"))
    ap.add_argument("--witness", default=str(aeon / "tools" / "raster_off_gate.py"),
                    help="a real tool that spawns through aether_emulator/AetherInstance")
    ap.add_argument("--witness-timeout", type=float, default=300.0)
    a = ap.parse_args()

    for label, p in (("ROM", a.rom), ("listing", a.lst), ("witness", a.witness),
                     ("oracle-aether", SERVER)):
        if not Path(p).is_file():
            print(f"COULD NOT RUN: {label} does not exist: {p}")
            return 2

    tools = str(Path(__file__).resolve().parent)
    tmp = tempfile.mkdtemp(prefix="cart-spawn-proof-")
    legs: list[str] = []
    fails: list[str] = []
    try:
        good = str(Path(tmp) / "good.bin")
        lst = str(Path(tmp) / "good.lst")
        shutil.copy(a.rom, good)
        shutil.copy(a.lst, lst)
        raw = Path(good).read_bytes()

        # The poisoned cart: SAME LENGTH, one byte different, placed deep in the file so
        # the server still accepts it as a cart and boots.
        off = len(raw) - 0x40
        bad = bytearray(raw)
        bad[off] ^= 0xFF
        evil = str(Path(tmp) / "evil.bin")
        Path(evil).write_bytes(bytes(bad))
        assert Path(evil).stat().st_size == Path(good).stat().st_size
        print(f"poison: {evil} is {len(raw)} bytes — the SAME SIZE as {good} — differing "
              f"only at ${off:06X} (${raw[off]:02X} -> ${bad[off]:02X})")

        # ---- leg 1: CONTROL ------------------------------------------------------
        t0 = time.monotonic()
        inst = AetherInstance(good, symbols=lst)
        try:
            inst.start()
            print(f"  LEG 1 CONTROL  : spawn on a clean cart SUCCEEDED in "
                  f"{time.monotonic() - t0:.3f}s")
            print(f"                   {inst.cart_note}")
        except CartMismatch as e:
            fails.append(f"LEG 1 CONTROL: the check REFUSED an untouched ROM — that is a "
                         f"refusal, not a check: {e}")
        finally:
            inst.reap()
        legs.append("1 CONTROL")

        # ---- leg 2: POISON -------------------------------------------------------
        inst = AetherInstance(good, symbols=lst)
        _poison_argv(inst, evil)
        try:
            inst.start()
            fails.append(f"LEG 2 POISON: the spawn SUCCEEDED with the server holding a "
                         f"different cart of the same size. The inherited check is "
                         f"vacuous and every tool on this seam can measure the wrong ROM.")
        except CartMismatch as e:
            if f"${off:06X}" not in str(e):
                fails.append(f"LEG 2 POISON: raised, but did not name ${off:06X}: {e}")
            else:
                print(f"  LEG 2 POISON   : UNMEASURABLE, as it must be — "
                      f"{str(e)[:150]}")
        finally:
            inst.reap()
        legs.append("2 POISON")

        # ---- leg 3a: THE WITNESS CONTROL, and it runs BEFORE the poisoned one -----
        #
        # "exited non-zero naming the cart" is only evidence if the SAME command exits
        # ZERO without the poison. Otherwise a witness that is simply broken today, or
        # that always fails on this ROM, reads as the check firing. Establishing the
        # control first is what makes the poisoned run mean something; establishing it
        # afterwards is how you find out you have been reading a constant.
        base_cmd = [sys.executable, a.witness, "--rom", good, "--lst", lst]
        t0 = time.monotonic()
        try:
            r0 = subprocess.run(base_cmd, capture_output=True, text=True,
                                timeout=a.witness_timeout, cwd=str(aeon))
        except subprocess.TimeoutExpired:
            r0 = None
        if r0 is None:
            fails.append(f"LEG 3a CONTROL: {Path(a.witness).name} did not finish within "
                         f"{a.witness_timeout:.0f}s UNPOISONED — this leg DID NOT RUN")
        elif r0.returncode != 0:
            fails.append(
                f"LEG 3a CONTROL: {Path(a.witness).name} exited {r0.returncode} on a CLEAN "
                f"cart. A witness that already fails cannot testify about the poison — "
                f"leg 3's non-zero exit would prove nothing. tail:\n"
                + "\n".join(((r0.stdout or "") + (r0.stderr or "")).strip().splitlines()[-6:]))
        elif "CartMismatch" in (r0.stdout or "") + (r0.stderr or ""):
            fails.append(f"LEG 3a CONTROL: {Path(a.witness).name} named a CartMismatch on a "
                         f"CLEAN cart — the discriminator is not a discriminator")
        else:
            print(f"  LEG 3a CONTROL : {Path(a.witness).name} exited 0 in "
                  f"{time.monotonic() - t0:.1f}s unpoisoned, with no cart complaint")
        legs.append("3a WITNESS CONTROL")

        # ---- leg 3: the same command, poisoned -----------------------------------
        sc = Path(tmp) / "sitecustomize.py"
        sc.write_text(SITECUSTOMIZE.format(env=POISON_ENV, tools=tools))
        env = dict(os.environ)
        env["PYTHONPATH"] = tmp + (os.pathsep + env["PYTHONPATH"]
                                   if env.get("PYTHONPATH") else "")
        env[POISON_ENV] = evil
        t0 = time.monotonic()
        try:
            r = subprocess.run(base_cmd, env=env, capture_output=True, text=True,
                               timeout=a.witness_timeout, cwd=str(aeon))
        except subprocess.TimeoutExpired:
            fails.append(f"LEG 3 WITNESS: {Path(a.witness).name} did not finish within "
                         f"{a.witness_timeout:.0f}s — this leg DID NOT RUN and is not a pass")
            r = None
        if r is not None:
            blob = (r.stdout or "") + (r.stderr or "")
            if r.returncode == 0:
                fails.append(
                    f"LEG 3 WITNESS: {Path(a.witness).name} exited 0 while the machine "
                    f"held a different cart — it reported a verdict about the wrong ROM")
            elif "CartMismatch" not in blob and "cart read back" not in blob:
                fails.append(
                    f"LEG 3 WITNESS: {Path(a.witness).name} exited {r.returncode} but "
                    f"nothing in its output names the cart. A non-zero exit for an "
                    f"unrelated reason is not this check firing. tail:\n"
                    + "\n".join(blob.strip().splitlines()[-6:]))
            else:
                print(f"  LEG 3 WITNESS  : {Path(a.witness).name} exited "
                      f"{r.returncode} in {time.monotonic() - t0:.1f}s naming the cart "
                      f"mismatch — a tool that never heard of cart_identity INHERITED it")
        legs.append("3 WITNESS")

        # ---- leg 4: what the opt-down CANNOT see ---------------------------------
        inst = AetherInstance(good, symbols=lst, cart_check=CART_CHECK_LENGTH)
        _poison_argv(inst, evil)
        try:
            inst.start()
            if inst.cart_note and "length only" in inst.cart_note:
                print(f"  LEG 4 WEAKNESS : cart_check='length' PASSED the same poison — "
                      f"this is what the opt-down cannot see, and why it is not the "
                      f"default. Its note says so: {inst.cart_note.strip()}")
            else:
                fails.append(f"LEG 4 WEAKNESS: length mode passed but did not label itself "
                             f"weaker in its note: {inst.cart_note!r}")
        except CartMismatch as e:
            fails.append(f"LEG 4 WEAKNESS: length mode RAISED on a same-length difference "
                         f"it cannot possibly detect — the test is measuring something "
                         f"other than what it claims: {e}")
        finally:
            inst.reap()
        legs.append("4 WEAKNESS")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    print(f"LEGS RUN: {len(legs)} — " + ", ".join(legs))
    if len(legs) != 5:
        fails.append(f"only {len(legs)} of 5 legs ran — an unrun leg is not a pass")
    if fails:
        print("RESULT: FAIL")
        for f in fails:
            print(f"  * {f}")
        return 1
    print("RESULT: PASS — the spawn-time cart check refuses a same-size different-content "
          "cart, on a real oracle-aether, through a real witness, and the weaker opt-down "
          "is pinned as weaker.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
