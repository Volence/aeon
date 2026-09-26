#!/usr/bin/env python3
"""tools/transition_window_probe.py passes its SUBJECT's exit status through unchanged.

KEEPALIVE-IS-BLIND-TO-LOSSY (docs/research/2026-09-25-keepalive-lossy.md). The probe runs a
subject tool under a shim and exits with the subject's status. It mapped every non-int
SystemExit code to 0, so a subject that refused with `sys.exit("message")` -- which Python
itself exits 1 for -- came out of the shim as a success. These rows run the SHIPPED probe as
a subprocess over tiny subject scripts; the subjects never touch the bus, so no emulator.
"""

import subprocess
import sys
from pathlib import Path

import pytest

PROBE = Path(__file__).resolve().parent / "transition_window_probe.py"


@pytest.mark.parametrize("body, want", [
    ("import sys; sys.exit('REFUSED: this subject could not measure')", 1),
    ("raise SystemExit('BLOCKED: a message, not an int')", 1),
    ("import sys; sys.exit(2)", 2),
    # The three exit-0 rows that stood here (sys.exit(0), sys.exit(), running off the end)
    # moved to test_a_subject_that_never_reads_is_could_not_run below: those subjects never
    # read the machine, so the probe measured nothing, and that is now COULD NOT RUN (2).
])
def test_subject_exit_status_is_what_python_would_have_exited(tmp_path, body, want):
    subject = tmp_path / "subject.py"
    subject.write_text(body + "\n")
    direct = subprocess.run([sys.executable, str(subject)], capture_output=True)
    assert direct.returncode == want, "the expectation is Python's own, measured directly"
    shimmed = subprocess.run([sys.executable, str(PROBE), str(subject)], capture_output=True,
                             text=True, timeout=60)
    assert shimmed.returncode == want, (
        f"subject exits {want} on its own and {shimmed.returncode} under the shim\n"
        f"stderr: {shimmed.stderr}")


def test_a_message_exit_keeps_its_message(tmp_path):
    subject = tmp_path / "subject.py"
    subject.write_text("import sys; sys.exit('REFUSED: the message the subject gave')\n")
    shimmed = subprocess.run([sys.executable, str(PROBE), str(subject)], capture_output=True,
                             text=True, timeout=60)
    assert "REFUSED: the message the subject gave" in shimmed.stderr


# ---- PRINTED-NOT-GATED residue (2026-09-26): the shim's OWN verdict ------------------
# A subject that exits 0 used to make the probe exit 0 whatever the shim measured: a run
# whose every peek raised printed "IN-WINDOW=0" (the clean reading) and passed, and so did
# a subject that never read the machine at all. Both are now COULD NOT RUN (exit 2). The
# subjects below drive a FAKE BusClient (its _request answers from a dict), so the shim's
# real peek path runs and still nothing touches an emulator.

FAKE_BUS = """
import asyncio, sys
sys.path.insert(0, {tools!r})
import suite_paths; suite_paths.add_client_path()
import aether

MEM = {mem!r}

class Fake(aether.BusClient):
    async def _request(self, method, params):
        if method == "emulator/read_memory":
            a = int(params["addr"], 16)
            if a not in MEM:
                raise RuntimeError("fake bus: no answer for %#x" % a)
            return {{"bytes": "0x" + MEM[a]}}
        return {{}}

async def main():
    c = object.__new__(Fake)
    for _ in range(3):
        await c.call("emulator/read_vram", {{"addr": "0xC000", "len": 2}})

asyncio.run(main())
"""
TOOLS_DIR = str(Path(__file__).resolve().parent)
LIVE = {0xFF88F4: "00", 0xFF88EC: "00012340", 0xFFA74C: "01000000"}   # level running
PREBOOT = {0xFF88F4: "9E", 0xFF88EC: "FFFFFFFF", 0xFFA74C: "00000000"}
NO_FRAMES = {0xFF88EC: "00012340", 0xFFA74C: "01000000"}             # that peek raises


def _shim(tmp_path, body):
    subject = tmp_path / "subject.py"
    subject.write_text(body)
    return subprocess.run([sys.executable, str(PROBE), str(subject)], capture_output=True,
                          text=True, timeout=60)


@pytest.mark.parametrize("mem, want, says", [
    (LIVE, 0, None),                           # measured: the green control
    (NO_FRAMES, 2, "peeks failed"),            # the shim's own read raised
    (PREBOOT, 2, "nothing was measured"),      # read, but never while the level ran
])
def test_shim_verdict(tmp_path, mem, want, says):
    r = _shim(tmp_path, FAKE_BUS.format(tools=TOOLS_DIR, mem=mem))
    assert r.returncode == want, r.stderr
    if says:
        assert "COULD NOT RUN" in r.stderr and says in r.stderr, r.stderr
    else:
        assert "COULD NOT RUN" not in r.stderr, r.stderr
        assert "live=3" in r.stderr, r.stderr


@pytest.mark.parametrize("body", ["import sys; sys.exit(0)", "import sys; sys.exit()",
                                  "print('ran to the end')"])
def test_a_subject_that_never_reads_is_could_not_run(tmp_path, body):
    r = _shim(tmp_path, body + "\n")
    assert r.returncode == 2 and "COULD NOT RUN" in r.stderr, r.stderr


def test_a_failing_subject_keeps_its_status_beside_the_refusal(tmp_path):
    r = _shim(tmp_path, "import sys; sys.exit(3)\n")
    assert r.returncode == 3 and "COULD NOT RUN" in r.stderr, r.stderr
