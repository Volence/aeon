# T6 capture verification — per-note modulation re-arm (2026-07-02)

Code: `1ff1c1f` (+18 B, budget $15E0/$18F0 = $310 free). This file records the C.b
verification gates. Captures session-scratchpad only; purity-checked 1x realtime
captures on the T6 build, compared against `s3k_hcz2_ref.vgm`.

**C.b outcome: the planning finding held.** C.a (wait + delta-sign reload per note)
alone produced the reference contour — no Mod_Advance mechanism change was needed.

## HCZ2 66s: gate_vib (flat frames before first fnum move, median)

| ch | ref | T6 | pre-T6 (T5 capture) |
|---|---|---|---|
| FM0 | 7.0 | 6.9 | 1.0 |
| FM1 | 14.0 | 14.0 | 0.9 |
| FM2 | 7.0 | 7.0 | 1.0 |
| FM3 | 9.0 | 9.8 | 0.8 |
| FM4 | 8.9 | 9.8 | 0.8 |

Mod delay honored on EVERY note (was: first note ever).

## HCZ2: vib_series (contour + depth)

| metric | ref | T6 | pre-T6 |
|---|---|---|---|
| vib notes FM0/1/2/3/4 | 28/71/28/71/71 | 28/72/28/72/72 | 242/251/243/289/268 |
| contour down-count | 0 on all ch | 0 on all ch | 86-110 per ch |
| FM3 depth (cents) | 18.0 | 18.0 | 18.2 |
| FM4 depth | 13.6 | 13.5 | 13.6 |
| FM0/FM2 depth | 40.3/40.1 | 36.2/36.3 | 27.4/32.6 |
| FM1 depth | 36.6 | 19.2 | 19.2 |

Short notes never vibrate (exact ref counts); contour unipolar-up, phase-locked, no
inverted starts (sign leak eliminated). FM3/FM4 (matching fnum-encoding class) at
exact depth parity. FM0/1/2 residue is the encoding-class factor — the plan's
expected state: full both-class depth match lands with Task 7's pitch-table
renormalization.

## MT regression (A, 28.7s)

melody_regs identical to the T5 MT capture (100% retrigger all 6 channels, same
off/on ratios ±window noise, same key-on rate ~5.0/s); spectral vs `mt_ref.vgm`
within ±1.1 dB per band, overall +0.4 dB — unchanged. Consistent with the
implementer's emitter-source verification that MT's packed stream contains no
MODSET events (sc_mod_ctrl stays 0; Mod_ReArm is a single-test no-op on MT).
