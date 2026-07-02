# T5 capture verification — key-off-before-key-on (2026-07-02)

Code: `3d8d037` + `1355424` (both reviews passed 2026-07-02). This file records the
capture gates that completed the task. Captures were session-scratchpad only (not
committed); all numbers below are from purity-checked 1x-timebase realtime captures
on the T5 build (`s4.bin` @ `31da591` tree, oracle @ `7f88ce7`).

## HCZ2 60s (UP, no stop) vs `s3k_hcz2_ref.vgm`

**Retrigger (melody_regs): 100% on all five melody channels** — every key-on preceded
by a same-channel key-off (baseline: 0-2%; ref: 100%). off/on ratios at ref parity:

| ch | ours on/off (ratio) | ref on/off (ratio) |
|---|---|---|
| FM0 | 341/448 (1.31) | 333/439 (1.32) |
| FM1 | 260/501 (1.93) | 252/492 (1.95) |
| FM2 | 339/448 (1.32) | 332/439 (1.32) |
| FM3 | 303/587 (1.94) | 289/570 (1.97) |
| FM4 | 278/549 (1.97) | 269/537 (2.00) |

**Rendered (melody_cmp):** full-mix bed RMS delta +0.1 dB, median frame +0.1 dB,
digitally-silent frames -0.3 pp vs ref. Per-channel isolated RMS within 0.5 dB;
inter-note tail silence now matches/slightly exceeds ref on every channel
(e.g. FM0 53.7% vs ref 46.3% — the retrigger creates the proper note gaps).

**Bonus observation:** the song now plays PAST the baseline's t=44.2s dead stop and
loops (67/67 active seconds). Baseline anomaly #1 (broken loop) is not reproducible
on this branch build — re-check at T12 whether a T2-T5 change or the master base fixed it.

## MT regression (A, 45s) — UNCHANGED semantics

melody_regs: 100% retrigger on all six channels (NOTE_RAW keyed off before the fix
too; the chokepoint's bit test replaced the explicit off/on pair 1:1 as designed).
Spectral vs `mt_ref.vgm`: every band within ±0.9 dB, overall RMS +0.4 dB. The
centroid delta (-230 Hz) is a capture-window proportion artifact (different section
mix in a 45s window); band-level parity is the gate.

## SFX over music (B x4 during HCZ2, 30s)

Capture clean (no contamination bursts, peak/mean 1.81). Retrigger stays 100% on all
melody channels through the steal/restore cycles; off/on ratios normal — no
double-attack signature. User by-ear confirmation deferred to T12 H.2 as planned.

## Harness gotchas discovered (also in phase_notes.md)

- **VGM capture under `run_frames` logs 2x wait timestamps** (content correct, time
  stretched exactly 2x). Realtime free-run captures (resume/sleep/pause) are 1x.
  Capture ONLY via realtime until the logger interaction is fixed.
- **Every ROM reload seeds a ~70.9e9 ns far-future park** on the 68k (absolute time
  stamped into the arbiter handshake at reload; grows with emulated uptime). With
  oracle `7f88ce7` it self-heals at one slice per pumped slice: drain with
  `run_frames {"frames":500}` loops until m68k `timeslice_progress` < 2e7, THEN
  press/capture. ~8 rounds after a fresh GUI launch.
