# Sound Perf & Budget Phase — Task 1 Baselines (2026-07-01)

All artifacts in `<scratchpad>/s3k_ref/`. Captures via oracle VGM logger, rendered via
`/usr/bin/vgm2wav` (Nuked-class core, verified accurate on key-on-while-keyed = NO-OP,
delta −9.8 dB on the synthetic two-note test `eg_a/eg_b.vgm`).

## Captures (both purity-checked via clean_purity.py)

| Capture | File | Duration | Verdict |
|---|---|---|---|
| S3K HCZ2 reference | `s3k_hcz2_ref.vgm` | 65.2 s | PURE: steady key-on rate all 66 s, 5 dense FM channels, FM5 keyed off per drum hit (S3K signature), 491 k $2A writes, PSG noise mode 7 (tone2-clocked). Captured from NOP-muted skdisasm ROM (`sonic3k_muted.bin`, 3 sites patched), music id $04 via Z80 `0x1C0A=0x04`. |
| Ours baseline | `ours_baseline.vgm` | 66.1 s | PURE but **song stops at t=44.2 s** (see anomalies). First 43 s = identical HCZ2 content (1027 key-ons vs ref 1039 in same window), no contamination. |
| Matched A/B windows | `ref_43.vgm`, `ours_43.vgm` | 43.5 s | Trimmed pair used for all rendered A/B. |

## Numbers table (ours vs S3K ref)

### Key-off / EG retrigger (melody_regs.py) — REPRODUCES (register level)
| ch | ref on/off | ref off-then-on retrigger | ours on/off | ours retrigger |
|---|---|---|---|---|
| FM0 | 333/439 | 100% | 237/69 | 0% |
| FM1 | 252/492 | 100% | 172/163 | 1% |
| FM2 | 332/439 | 100% | 236/69 | 1% |
| FM3 | 289/570 | 100% | 198/190 | 2% |
| FM4 | 269/537 | 100% | 184/183 | 1% |

Ref keys off before EVERY key-on; ours essentially never does. (Evidence's "3 vs 67
key-offs" magnitude was a 64-note window on one channel; whole-capture ratios above.)

### DAC starvation (dac_stall.py / dac_perburst.py, value-aware hit segmentation)
| Metric | ref (43.5 s) | ours (43.5 s) |
|---|---|---|
| drum hits | 87 | 84 |
| in-hit cadence (median gap) | 45.4 µs (quantization floor) | 45.4 µs |
| airtime in hold gaps (>1.5× own-hit median) | 21.8–23.5% | 28.6–31.2% |
| hold split: intro / melody section | 25.6% / 22.9% | 31.0% / 31.3% |
| stall gaps 2–5 ms | 1263 | 1150 |
| stall gaps 5–10 ms | 45 | 328 |
| stall gaps 10–17 ms | 1 | 40 |
| mid-sample full-frame (≥16.7 ms) freezes | 2 intro + 3 melody* | 1 intro + 7 melody |
| snare class: writes / duration | 1437 / 93.6 ms | 1404 / 108.9 ms (+16%) |
| mid class: writes / duration | 3198 / 217.2 ms | 2970 / 246.1 ms (+13%) |
| tom class: writes / duration | 4954 / 333.7 ms | 4511 / 349.2 ms (+5%) |

*ref "freezes" are adjacent-hit joins under the 30 ms merge; its in-hit stalls top out ~5-7 ms.
Ours has a 7× excess of 5–10 ms stalls and 40× of 10–17 ms stalls = the sequencer-tick
starvation, plus per-frame idle $2A writes (always-armed FM6; ref keys FM6 per hit).

### Drum loudness (drum_loud.py, $2A-waveform attack RMS) — REPRODUCES (parity)
ref median −5.1 dBFS; ours median −5.0 dBFS (evidence: −0.6 dB parity ✓).

### Vibrato / mod delay (gate_vib.py, vib_series.py) — REPRODUCES
| Metric | ref | ours |
|---|---|---|
| flat frames before first fnum move (median, per ch) | 7.0–14.0 | 0.8–1.0 |
| contour | unipolar (med −pk = 0 on FM1/3/4) | bipolar symmetric (±pk equal) |
| FM3 depth | 18.0 c unipolar (pp 18) | ±18.1 c bipolar (pp ~36 = 2.0×) |
| FM4 depth | 13.6 c unipolar | ±13.6 c bipolar (pp 2×) |
| FM1 depth | 36.6 c unipolar | ±19.2 c bipolar (pp ~34, ≈parity) |

Mod-delay-only-on-first-note ✓, bipolar-vs-unipolar ✓, 2× peak-to-peak on matched
encodings ✓ (evidence's 96.7 vs 47.6 c was the same 2× ratio, different note/units).

### Tempo — REPRODUCES
Ours +1.16% slower over the matched 1027-key-on span (evidence ~1.5% ✓).

### Rendered mix/bed (melody_cmp.py, spectral.py) — DOES NOT REPRODUCE the evidence
| Metric | ref | ours | evidence claimed |
|---|---|---|---|
| full-mix bed RMS | −13.5 dB | −13.5 dB (−0.0) | ours +2.1 dB |
| median frame RMS | −14.8 dB | −15.0 dB (−0.2) | ours +4.5 dB |
| digitally-silent frames (≤−60 dB) | 1.0% | 0.8% | ref ~25%, ours ~0 |
| FM-only bed (FM0-4 isolated) | −15.6 dB, 3.8% silent | −15.9 dB, 3.6% silent | — |
| note-matched attack step FM0/FM2 | +0.3 dB (28% notes >6 dB) | −0.0 dB (27%) | ref staccato vs ours pad |
| note-matched attack FM1/3/4 | −200 dB pre / full attacks 95-99% | identical | — |
| inter-note tail silence per ch | 35.5/54.8/37.5/77.8/81.3% | 35.5/54.7/34.1/78.3/82.2% | — |
| band RMS 800 Hz–10 kHz | — | −0.6..−0.8 dB vs ref | −2.1 dB at 6-10 kHz (residue) |
| spectral centroid | 619 Hz | 580 Hz (−39) | — |

Note-matched, per-channel, ours renders essentially IDENTICAL to ref: FM1/3/4 key off in
our data too (gated notes) and get full attacks; FM0/FM2 are legato pads with no attack
step in the REF either. The audible "duller" gap is NOT visible in these rendered
baselines at the claimed magnitudes.

## Anomalies found (STOP-worthy, reported to parent)

1. **Our HCZ2 stops dead at t=44.2 s** (song end / StopMusic path), where real S3K
   continues to its 54.1 s loop. Content up to the stop is note-identical to ref.
   Loop is broken or import truncated on this branch's master base.
2. **Re-trigger after the stop is loaded-but-silent** — the documented pre-existing
   Timer-A disable bug (StopMusic kills Timer A; $24/$25/$2B/$B6 written on reload,
   zero key-ons after). Confirms the stop went through StopMusic.
3. **Phase-evidence divergence**: DAC hold magnitude (ours 31% vs claimed 45-63%; tom
   smear +5..16% vs claimed 2.3×) and ALL rendered bed/retrigger-consequence numbers
   diverge from the handoff's evidence. Register-level findings all reproduce
   directionally. Possible causes: evidence captured pre-2026-07-01-fix merges, with
   SOUND_DBG_MIRROR=1, under game load, or with different metric definitions.

## Gates
- `python3 -m pytest tools/ -q`: **808 passed, 2 skipped** (0.55 s)
- Nothing committed (scratchpad only).

## Scripts (all headless, labeled output)
`vgmlib.py` (parser/isolation/trim/render/hit-segmentation), `clean_purity.py`,
`dac_stall.py`, `dac_perburst.py`, `drum_loud.py`, `melody_regs.py`, `melody_cmp.py`,
`gate_vib.py`, `vib_series.py`, `spectral.py`. Muted ROM: `s3k_ref/sonic3k_muted.bin`.
