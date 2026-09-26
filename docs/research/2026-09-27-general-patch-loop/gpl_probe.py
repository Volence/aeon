#!/usr/bin/env python3
"""gpl_probe — the perf survey's leg_probe, unchanged, with its emulator socket moved off /tmp.

The general-patch-loop design parcel (2026-09-27) measures with the survey's harness
(docs/research/2026-09-25-perf-survey/leg_probe.py), which inherits the S2CLIP-LAG
study's Server. That Server puts its Unix socket under /tmp, and /tmp was over its disk
quota while this parcel ran (the brief forbids writing there). This wrapper changes ONLY
the socket directory (to $TMPDIR, else ~/.cache/aeon-tmp) and then runs leg_probe.main()
with the same argv. Every counter, drive and summary is leg_probe's own.
"""
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SURVEY = HERE.parent / "2026-09-25-perf-survey"
sys.path.insert(0, str(SURVEY))
import leg_probe  # noqa: E402

SOCKDIR = os.environ.get("TMPDIR") or str(Path.home() / ".cache" / "aeon-tmp")
_orig_init = leg_probe.LFP.Server.__init__


def _init(self, rom, lst, tag):
    _orig_init(self, rom, lst, tag)
    self.sock = os.path.join(SOCKDIR, f"gpl_{os.getpid()}_{tag}.sock")


leg_probe.LFP.Server.__init__ = _init

# --read-at-end reads ONE byte per symbol (leg_probe's rule). A symbol named in the
# GPL_WORDS environment variable (comma list) is read as a big-endian 16-bit word instead,
# so a u16 counter is not reported as its high byte.
WORDS = set(filter(None, os.environ.get("GPL_WORDS", "").split(",")))
_word_addrs = set()
_orig_syms, _orig_rd = leg_probe.syms, leg_probe.rd


async def _syms(c, names):
    got = await _orig_syms(c, names)
    _word_addrs.update(v for k, v in got.items() if k in WORDS)
    return got


async def _rd(c, addr, n):
    return await _orig_rd(c, addr, 2 if (n == 1 and addr in _word_addrs) else n)


leg_probe.syms, leg_probe.rd = _syms, _rd

if __name__ == "__main__":
    if not SOCKDIR.startswith("/tmp"):
        leg_probe.main()
    else:
        raise SystemExit("gpl_probe: REFUSED, socket dir is under /tmp")
