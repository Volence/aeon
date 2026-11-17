"""Post-sigil smoke for the leg harness with the per-DMA VBlank-end probe (v2 B3).

Runs `tools/leg_run.py --leg idle --cap 120 --dma-probe` on BOTH canonical shapes against
the pinned oracle and checks the result, not the exit code alone: idle's coverage rule needs
600 ticks, so a 120-tick cap is written-but-not-met (exit 1) by design; exit 2 (COULD NOT
RUN) fails. A missing pinned binary FAILS naming the pin path -- it never skips."""
import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

import leg_drive as ld
import leg_provenance as lp

AEON = Path(__file__).resolve().parent.parent
TOOLS = AEON / "tools"


@pytest.mark.needs_build("s4.bin", "s4.lst", "s4.debug.bin", "s4.debug.lst")
@pytest.mark.parametrize("stem", ["s4", "s4.debug"])
def test_idle_legs_with_dma_probe(stem, tmp_path):
    pin = lp.load_pin()
    if not pin.binary.is_file():
        pytest.fail(f"pinned oracle binary missing: {pin.binary} (from {lp.PIN_FILE})")
    rom, lst = AEON / f"{stem}.bin", AEON / f"{stem}.lst"

    def leg(out, *extra):
        t = time.monotonic()
        p = subprocess.run([sys.executable, str(TOOLS / "leg_run.py"), "--rom", str(rom),
                            "--lst", str(lst), "--leg", "idle", "--phase", "0", "--out",
                            str(out), "--cap", "120", *extra],
                           capture_output=True, text=True, timeout=300)
        print(f"{stem} {extra}: leg_run rc={p.returncode} wall {time.monotonic() - t:.1f}s\n"
              f"{p.stdout}{p.stderr}")
        assert p.returncode in (0, 1), f"COULD NOT RUN:\n{p.stderr}"
        f = out / f"{stem}_idle_p0.json"
        assert f.is_file(), "no result file written"
        return json.loads(f.read_text())

    r = leg(tmp_path / "probe", "--dma-probe")
    # The probe must not perturb what it measures: the same leg without it drives the same
    # rows and the same input, bit for bit.
    bare = leg(tmp_path / "bare")
    assert bare["dma"]["status"] == "DID NOT RUN"
    assert bare["rows"] == r["rows"] and bare["input_log"] == r["input_log"]
    lp.require_provenance(r["provenance"])
    assert r["status"] == "CAP" and len(r["rows"]) == 120
    d = r["dma"]
    assert d.get("status") != "DID NOT RUN", d
    assert d["unmeasurable"] is None, d["unmeasurable"]
    assert d["sites"], "no trigger sites"
    # Every VBlank the probe saw entered at the line the listing's SCREEN_HEIGHT says.
    equ = ld.parse_listing(lst)[1]
    assert d["vblanks"] and all(v["entry_line"] == equ["SCREEN_HEIGHT"] for v in d["vblanks"])
    # One VBlank per frame driven: frames = ticks + lag over the window between the first and
    # last row (the probe is armed at the first row).
    frames = sum(row["dfc"] for row in r["rows"][1:])
    assert len(d["vblanks"]) == frames, (len(d["vblanks"]), frames)
    non_lag = [v for v in d["vblanks"] if not v["lag"]]
    assert non_lag and all(v["events"] >= 1 for v in non_lag), \
        [v for v in non_lag if v["events"] < 1][:3]
    assert d["overruns"] == [], d["overruns"][:3]
    assert d["worst_end"]["status"] == "MEASURED" and d["worst_end"]["line"] is not None
