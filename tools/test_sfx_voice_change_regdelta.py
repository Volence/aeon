#!/usr/bin/env python3
"""Runner for tools/sfx_voice_change_regdelta.py.

WIRED INTO: build.sh's pre-build pytest lane (`python3 -m pytest tools`, build.sh
:627-636), so every canonical build runs it. It is a pure static check — it reads
the shipped SFX blob and skdisasm's own sources and touches no emulator — which is
why it belongs here and not in tools/effects_gates.py.

WHAT IT PROTECTS. SP-6 gave the engine mid-stream `smpsSetvoice`. The owner then
reported an audible click in the re-sourced two-voice spring, and the question was
whether the click is inherent to changing a voice under a sounding note or a bug in
how we perform the switch. The answer was established by showing our YM2612 write
set is value-identical to Sonic & Knuckles' for the same voice bank. This runner
keeps that true: if anyone changes Fm_PatchLoad's field order, the FmPatch struct,
a register base, or the shipped voice bytes such that we stop writing S&K's values,
the build fails and says which register drifted.

RED-FIRST, PROVEN ON DISK (2026-09-09, sfx_B1.bin):
  * byte $BF ($31 -> $32, voice 1 fp_dt_mul[0]) -> exit 1,
    "L1 voice 1 reg $30: ours $32 != S&K $31"
  * byte $BD ($20 -> $24, voice 1 fp_alg_fb algorithm 0 -> 4) -> exit 1,
    "L1 voice 1 reg $B0: ours $24 != S&K $20" AND
    "L2 a non-TL instantaneous-amplitude register changed: $B0"
  * baseline restored with `git checkout --` -> exit 0
Both poisons were applied to the file on disk and both exit codes were read
UNPIPED, because a pipe replaces the exit status.
"""
import subprocess
import sys
from pathlib import Path

import pytest

TOOL = Path(__file__).resolve().parent / "sfx_voice_change_regdelta.py"
SKDISASM = Path("/home/volence/sonic_hacks/skdisasm")


def _run():
    return subprocess.run([sys.executable, str(TOOL), "--verbose"],
                          capture_output=True, text=True)


def test_our_voice_change_writes_sk_values():
    """L1+L2: our mid-stream voice change is register-and-value identical to S&K's.

    Exit 2 (Unmeasurable) is a SKIP, not a pass and not a failure: the S&K
    reference tree is a sibling checkout that a fresh clone need not have, and a
    check that could not ask its question must never read as green. The skip
    reason carries the tool's own stderr so the cause is visible in the run."""
    if not SKDISASM.is_dir():
        pytest.skip(f"S&K reference tree {SKDISASM} is absent — no reference half")
    r = _run()
    if r.returncode == 2:
        pytest.skip(f"UNMEASURABLE (exit 2), not a pass:\n{r.stderr.strip()}")
    assert r.returncode == 0, (
        "sfx_voice_change_regdelta reported a drift between our FM voice write set "
        f"and Sonic & Knuckles' (exit {r.returncode}).\n"
        f"--- stdout ---\n{r.stdout}\n--- stderr ---\n{r.stderr}")
    # The tool must have actually compared something; a run that silently compared
    # zero registers would print PASS while proving nothing.
    assert "shared registers compared" in r.stdout, (
        "the tool produced no per-voice comparison line — it may have found no "
        f"registers to compare:\n{r.stdout}")
    assert "ALL LEGS PASS" in r.stdout, r.stdout
