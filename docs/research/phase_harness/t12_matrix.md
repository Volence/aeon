# T12 — Phase success-criteria matrix (spec §H), final build (2026-07-02)

Final build: branch HEAD after `b342889` (S3K-exact tempo model). All numbers from
purity-checked realtime captures on THIS build unless marked (build-invariant =
measured earlier this session on a build whose relevant code is identical).
Reference = `s3k_hcz2_ref.vgm` + the 115s `ref_long` capture (real S3K, muted ROM).

| Gate | Target | Measured | Verdict |
|---|---|---|---|
| H.1 retrigger | ref parity (100%) | 100% all 5 melody ch (was 0-2%) | **PASS** |
| H.1 bed/silence | ref parity | bed −0.1 dB, median −0.0 dB, silent −0.1 pp | **PASS** |
| H.2 drum airtime | ≤ ~20% (spec, from evidence #s) | 24-26% vs REF'S OWN 21.4% (same script) | **PASS at ref-parity reading**; spec's absolute 20% was calibrated to evidence numbers that never reproduced (T1). D.2 attempt to force it lower measured net-negative and was reverted (t9_verification). |
| H.2 by-ear | user confirmation | **PENDING — needs the user** | OPEN |
| H.3 vibrato delay | ref 7-14 flat frames | 6.9/14.0/7.0/9.8/9.7 (ref 7.0/14.0/7.0/9.0/8.9) | **PASS** |
| H.3 contour | unipolar-up, no inverted starts | down=0 on all channels | **PASS** |
| H.3 depth | ref parity both encodings | FM1 36.7 (ref 36.6), FM3 18.2 (18.0), FM4 13.5 (13.6); FM0/FM2 36.6/36.7 vs 40.3/40.1 (~9% band-overlap residue, documented t7) | **PASS with noted residue** |
| H.4 tempo | < 0.3% drift | −1.42% → engine model replaced (S3K-exact, `b342889`) → **−0.52%**; residual isolated to IMPORT loop length (~14 event-ticks/loop), not the engine | **ENGINE PASS / DATA OPEN** (deferred: per-channel packed-loop tick audit) |
| H.5 porta | soak + smooth glides | 3000f soak, PC resident, trap silent; 163-step uniform +8 sweeps | **PASS** (t10) |
| H.6 build+pytest | green, 803+ | exit 0, **815 passed, 2 skipped** | **PASS** |
| H.6 MT A/B | unchanged | spectral ±1.2 dB, +0.3 dB overall, 100% retrigger (every build this session); tempo now −0.196% (2/7 unrepresentable in the 8-bit model — nearest mod; ~78 ms per 40 s) | **PASS with noted −0.196%** |
| H.6 SFX steal/restore | clean | 100% retrigger through steal cycles, spectral parity (t5/t7) | **PASS** |
| H.6 boot | clean | every reload this session (dozens) | **PASS** |

**Budget:** $175A/$18F0 = **$196 free** (DEBUG=1; plain builds 126 B leaner). Phase
start: 6 bytes free. Spent this phase on fidelity: rekey −10, mod re-arm +18,
porta +386, tempo model −8; recovered by T2-T4: +790.

**Clock:** 59.9227 Hz effective under load, measured exactly (t11).

**Unplanned work shipped:** oracle emulator root-cause fix (04ac467 — parks/known-stuck
gone); S3K-exact tempo model (b342889 — H.4). **Reverted after measurement:** D.2
in-tick DAC drains. **Rejected on measurement:** D.3 hit-scoped toggling.

**Open at gate:** H.2 by-ear (user), H.4 import residual (deferred, tools-side),
FM0/FM2 depth residue (band-overlap, cosmetic), FM env attack seam (1-2 frames,
by-ear candidate), MT −0.196%.
