# T11 verification — frame clock measured + retuned (2026-07-02)

## Measurement method (controller, deterministic)

SND_STAT_TICK (per-Timer-A-overflow counter) vs exact emulated frame count via
`run_frames`, from song start (deterministic emulator = identical tick-load
sequence across builds). Windows mid-song are NOISY (section-dependent tick load
and, in one poisoned run, a leftover debug porta poke) — from-start long windows
are the protocol.

## Result

- N=136 (pre-retune): 3597/3600 ticks = **59.873 Hz** under HCZ2 load
  (~3 long-tick overruns per minute — the T9 monster-tick story's residue).
- N=137 (SND_FRAME_MILLIHZ 59920 → 60053, the compensated pin): 10800/10800
  ticks over 3 minutes = **59.9227 Hz exactly**. Gate 59.92 ± 0.02: DEAD CENTER.

## Drift gate (Step 3) — honest disposition

Clock-domain drift is 0 by construction (the tick rate IS the NTSC field rate,
measured). Song-domain check vs the S3K ref surfaced a ~1.4% loop-period
discrepancy (ours 53.80s vs ref 54.58s) with WEAK confidence (1.2-loop capture,
93 autocorrelation matches; T1's index-matched method said +1.16% SLOWER — the
methods disagree and both have known artifacts). Since the clock is exact, any
real residual lives in the TRANSCODER's tempo mapping (note: 1.42% ≈ the
historical 59.06→59.92 retune delta — the import may have been calibrated
against the old clock). Escalated to the T12 H.4 matrix with a required
longer-capture (2.5+ loop) protocol; do NOT chase it by de-tuning the clock.

## MT re-verify (Step 4)

The clock feel change from this retune is +0.08% (59.873 → 59.9227) —
inaudible. MT spectral vs mt_ref: identical to every capture this session
(overall +0.4 dB, same band pattern). The plan's warned "~1.4% faster" feel
change happened in the PREVIOUS retune (2026-07-01, 59.06→59.92) and was
already user-endorsed ("caught by ear"); this retune is a trim on top.

## Process note

A broken `grep`-masked build exit briefly hid a failing pin assert (the pin/target
edits landed in two steps). Caught by re-running with explicit exit-code checks;
the pin assert did its job. Always check `./build.sh` exit, not just the budget line.
