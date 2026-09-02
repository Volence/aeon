#!/usr/bin/env python3
"""`emulator/wait_for_break`'s timeout key is right or wrong RELATIVE TO A SERVER.

This repo drives TWO emulators, and they spell the same parameter differently:

  * legacy C++ `oracle_gui`  — `timeout_ms`  (`oracle-old/linux-port/gui/ControlSocket.cpp`,
    `req.getInt("timeout_ms", 30000)`)
  * Rust `oracle-aether`     — `timeoutMs`   (`crates/oracle-aether/src/engine.rs`, and the
    contract schema declares `unevaluatedProperties: false`)

**The asymmetry is the whole reason this file exists.** The Rust core REFUSES an unknown key
with `-32602`, so sending it the snake_case spelling fails loudly and gets fixed in a minute.
The legacy server reads its parameter with a *tolerant* `getInt(key, 30000)`: an unrecognised
key is not an error there, it silently takes the 30 s DEFAULT. So a well-meaning "rename it to
match the convention" against a legacy-seam probe does not go red — it quietly replaces every
hand-chosen budget with 30 s:

    tools/evict_witness.py             60000 -> 30000   (Phase-1 anchor budget halved)
    tools/raster_frame_epoch_probe.py   6000 -> 30000   (a hang gets 5x longer to hide in)
    tools/parallax_hscroll_probe.py   120000 -> 30000   (the wedge detector its own docstring
                                                         says was raised from 20 s AFTER four
                                                         load-induced false failures)

Owner ruling 2026-08-26 (`docs/DEFERRED_WORK.md`, "Rider 3"): convert a probe's spelling **in
the same commit as its migration to the Rust core, never before**. This test is that ruling
made mechanical — it pins each send site's spelling to the seam the file actually dials, so
the flip can only land together with the migration that earns it.

Two tests, deliberately split:

  1. `test_wait_for_break_key_matches_seam` — self-contained, always runs. The regression net.
  2. `test_expected_spellings_are_derived_from_the_real_servers` — reads the two peer sources
     and re-derives the constants below, so they cannot rot into folklore. It FAILS when a
     peer source is absent; see the note under the peer paths for why it no longer skips.
"""
import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))  # tools/, for suite_paths
from suite_paths import SUITE_ROOT_ENV, suite_path  # noqa: E402

TOOLS = Path(__file__).resolve().parent

# Spelling required by each server. Re-derived from both servers' own sources by the second
# test in this file; do not edit one without running it.
KEY_LEGACY = "timeout_ms"
KEY_RUST = "timeoutMs"

# The two peer sources the derivation test reads, spelled RELATIVE TO THE SUITE ROOT
# (SUITE-HOME-PATHS, 2026-08-30 — they used to be absolute literals under one $HOME).
RUST_SCHEMA_PARTS = ("oracle", "crates", "oracle-aether", "tests", "contract",
                     "bus-protocol.schema.json")
LEGACY_CPP_PARTS = ("oracle-old", "linux-port", "gui", "ControlSocket.cpp")
RUST_SCHEMA = suite_path(*RUST_SCHEMA_PARTS)
LEGACY_CPP = suite_path(*LEGACY_CPP_PARTS)

# WHY THE DERIVATION ROW FAILS RATHER THAN SKIPS WHEN A PEER IS ABSENT.
#
# It used to `pytest.skip("a peer emulator checkout is absent")`, reasoning that a missing
# peer must not fail this repo's build. The 2026-08-30 classification
# (`docs/2026-08-30-suite-home-paths-classification.md`) found that this was the ONE row in
# the whole suite that a missing donor turned into a skip, and a skip is indistinguishable
# from a deliberate one: a reader seeing `1 failed, 1 passed, 1 skipped` learns nothing about
# whether the skip was chosen or caused.
#
# The stated rationale was also already false in practice. Six suite files gate 188 rows on
# donor trees outside this repo, and FIVE of them — test_smps_import (skdisasm),
# test_zyrinx_port (the B&R tree), test_effects_gates_segments, test_aether_instance and
# palette_variant_gate — already error or die at collection when their donor is absent. This
# tree's actual policy is "the donors are part of the checkout"; this row was the anomaly, not
# the policy. Failing here makes the row agree with its five siblings.
#
# The escape hatch is `EMPYREAN_SUITE_ROOT` (`suite_paths.SUITE_ROOT_ENV`), which relocates the
# whole suite for every tool at once. There is deliberately no per-row opt-out: an opt-out would restore exactly the silent
# skip this replaced.

# A line that actually SENDS the method, as opposed to naming it in a comment, a docstring or a
# capability list. Both call shapes in this tree: `b.call("emulator/wait_for_break", {...})` and
# the retry wrapper `_c(b, "emulator/wait_for_break", {...}, 20.0)`.
SEND_RE = re.compile(r'(?:\.call|\b_c)\([^)]*?"emulator/wait_for_break"')
KEY_RE = re.compile(r'"(timeout_ms|timeoutMs)"\s*:')


def _seam(text: str) -> str:
    """Which emulator does this file dial? Read off the file's own spawn/connect seam.

    `rust`    — routes through `tools/aether_instance.py`, the one sanctioned oracle-aether seam.
    `legacy`  — spawns the C++ `oracle_gui` via `launcher.headless_emulator` from
                `oracle-old/linux-port/harness` (that module's `GUI` constant is the binary).
    `ambient` — connects to a pre-existing socket rather than spawning. Treated as `legacy`
                below: BOTH servers default to `$XDG_RUNTIME_DIR/oracle.sock`, so the path
                cannot discriminate, and the standing owner ruling pins the one such tool
                (`evict_witness.py`) to the legacy server it documents in its own docstring.
    """
    if "aether_instance" in text:
        return "rust"
    if "linux-port/harness" in text or re.search(r"from\s+launcher\s+import", text):
        return "legacy"
    return "ambient"


REQUIRED_KEY = {"rust": KEY_RUST, "legacy": KEY_LEGACY, "ambient": KEY_LEGACY}


def _send_sites():
    """Every wait_for_break send site in `tools/`, as (path, lineno, seam, key_or_None)."""
    for path in sorted(TOOLS.glob("*.py")):
        text = path.read_text()
        if "emulator/wait_for_break" not in text:
            continue
        seam = _seam(text)
        for n, line in enumerate(text.splitlines(), 1):
            if line.lstrip().startswith("#") or not SEND_RE.search(line):
                continue
            m = KEY_RE.search(line)
            yield path, n, seam, (m.group(1) if m else None)


def test_send_sites_are_found_at_all():
    """Guards the guard: a regex that silently matches nothing would make this file vacuous."""
    sites = list(_send_sites())
    assert sites, ("no `emulator/wait_for_break` send site found in tools/ — the detector is "
                   "broken, not the tree")


def test_wait_for_break_key_matches_seam():
    """Each send site must spell the timeout key the way ITS OWN server spells it."""
    wrong = []
    for path, n, seam, key in _send_sites():
        if key is None:
            continue  # omitting the timeout is legal on both servers; each takes its default
        if key != REQUIRED_KEY[seam]:
            wrong.append(f"{path.name}:{n} dials the {seam} server and must send "
                         f"`{REQUIRED_KEY[seam]}`, but sends `{key}`")
    assert not wrong, (
        f"{len(wrong)} wait_for_break send site(s) spelled for the wrong server:\n  "
        + "\n  ".join(wrong)
        + "\n\nA key name is only right or wrong relative to the server on the other end. "
          "Flip a spelling ONLY in the same commit that migrates the probe's seam.")


def test_expected_spellings_are_derived_from_the_real_servers():
    """Re-derive KEY_RUST and KEY_LEGACY from the two servers' own sources.

    Absent peer source => FAIL, never skip. See the block comment above the peer paths.
    """
    absent = [p for p in (RUST_SCHEMA, LEGACY_CPP) if not p.exists()]
    if absent:
        pytest.fail(
            "cannot re-derive the wait_for_break timeout spelling: "
            + ", ".join(str(p) for p in absent)
            + " is absent.\n\nThis row FAILS rather than skipping, deliberately: while the "
              "peer source is unreadable, KEY_RUST/KEY_LEGACY above are unchecked folklore "
              "and this file's regression net is pinning constants nothing re-derives. "
              "A skip here would report that as a deliberate choice.\n"
              f"Fix by restoring the peer checkout beside this one, or point {SUITE_ROOT_ENV} "
              "at the directory that holds them.")

    schema = json.loads(RUST_SCHEMA.read_text())
    params = schema["methods"]["emulator/wait_for_break"]["params"]
    assert list(params["properties"]) == [KEY_RUST], (
        f"oracle-aether's contract now declares {list(params['properties'])} for "
        f"wait_for_break, not [{KEY_RUST!r}]")
    assert params.get("unevaluatedProperties") is False, (
        "the Rust contract no longer refuses undeclared keys — the loud half of this "
        "asymmetry is gone and this file's reasoning needs re-checking")

    cpp = LEGACY_CPP.read_text()
    body = cpp.split("OpWaitForBreak", 1)
    assert len(body) > 1, "OpWaitForBreak not found in the legacy server"
    m = re.search(r'getInt\("([A-Za-z_]+)"\s*,\s*(\d+)\)', body[1])
    assert m, "the legacy wait_for_break no longer reads its timeout via getInt"
    assert m.group(1) == KEY_LEGACY, (
        f"the legacy server now spells its timeout key {m.group(1)!r}, not {KEY_LEGACY!r}")
    # The tolerant default is the reason a wrong key is SILENT here rather than an error.
    assert int(m.group(2)) == 30000


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
