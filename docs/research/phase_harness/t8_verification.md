# T8 capture verification — envelope write-on-change (2026-07-02)

Code: `125ed3e` (byte-neutral, budget $310 free, pytest 811+2). Captures on the
park-FIXED oracle (`04ac467`) — see the new capture procedure note below.

## HCZ2 rendered A/B vs the T7 capture (the "inaudible" gate)

Full-mix bed delta +0.1 dB, median frame +0.1 dB, silent frames -0.3 pp.
Per-channel isolated RMS within 0.1-0.6 dB, inter-note tail silence at parity
(note-count differences are capture length only: 96s vs 67s). Write-on-change
is rendered-inaudible. PASS.

## DAC stalls (context for T9)

Hold excess 24.3% -> 24.1% (T7 -> T8); gap-bucket counts scale with capture
length. The envelope-write savings are real cycles but the drum-hold histogram
is dominated by the tick/seam structure that Task 9's Timer-B drain bursts
attack — as the spec's D.1/D.2 split anticipated. The plan's "drum-hold %
already improves" expectation lands as ~0.2 pp, within noise. Not a blocker;
T9 owns the headline numbers.

## MT regression

No envelopes in MT; spectral vs `mt_ref.vgm` identical to the T6/T7 captures
(overall +0.4 dB, same band pattern). PASS.

## Known residual (implementer-flagged, carried to T12 by-ear)

FM key-on resets the `sc_env_out` shadow to 0 without a TL emit; an FM env body
with leading zeros rides the PREVIOUS note's latched TL until its first nonzero
byte (1-2 frames; both shipped FM envs start `00h`). After a rest-silenced note
the next attack could open TL-silenced for those frames. Not visible in the
rendered A/B at capture scale; flag for the T12 H.2 by-ear pass. Candidate
0-2 byte fix if audible: key-on primes the shadow with a never-matches sentinel.

## Capture-procedure changes (post oracle 04ac467 — drain era over)

- Reload leaves the system RUNNING and the pump now runs FASTER than realtime
  (~1.4x): a capture of N wall seconds yields ~1.4N emulated seconds. Fine for
  all metrics (timebase is emulated time).
- **Press hotkeys from a PAUSED machine.** The game AUTO-PLAYS a song at boot
  (always did — pre-fix workflows pressed from pause so UP switched songs at
  capture start). A press against the free-running machine can miss the hotkey
  window entirely and the capture records the auto-played song instead
  (six-FM/no-DAC content = you captured the wrong song; purity-check catches it).
  Procedure: reload -> pause -> run_frames 300 -> vgm_start -> press -> resume.
