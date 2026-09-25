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
    ("import sys; sys.exit(0)", 0),
    ("import sys; sys.exit()", 0),
    ("print('ran to the end')", 0),
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
