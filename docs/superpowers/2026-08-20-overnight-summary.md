# Overnight summary — 2026-08-19 → 08-20 (aeon overseer)

## Merged to master (all pushed, all paired where bytes moved)

| what | aeon | sigil pair | chain |
|---|---|---|---|
| F5 audit-off fill (instrument de-noise) | merged pre-midnight | `2a70a296` | 150 |
| F1 resident identity (verify-then-latch; Col 183→103, Seq 136→88 cyc/word) | merged | `6802b6e9` | 151 |
| Boot-at-cursor mailbox (owner edit loop: 38s → ~2.0s with FAST + memo re-bake) | merged | `5b3b7745` | 152 |
| F4 staging side index (evict probe 402-440 → ~200 cyc) | `0cf5a053` | `02ad2e61` | 153 |
| F2 prefetch lands (Schmitt guard + memo re-key; 2.067 → 1.240 f/t; latent cross-tier aiming bug fixed) | `e6a0e104` | `1dbbcbc1` | 154 |
| P3 plan (16 tasks, 8 spec corrections) + T2 hscroll probe + T1 anchor regimes | `08e87cbc`, `da69f178`, `767834bb` | docs/probe only | — |
| Parallax unroll — the arc coda (1.240 → **1.192 f/t**, mean 4,984 cyc UNDER the 60fps line) | `ee310483` | `af2a4429` | 155 |
| Streaming arc CLOSE-OUT doc | `aab012a7` | — | — |

Suite green throughout: sigil `3752 passed / 0 failed`, aeon pytest 1177/3 skips, effects gates 24/24, all four build shapes, clean-checkout CRC reproduction on every byte-moving parcel.

## The headline: the streaming choke arc is CLOSED

Opened on your ruling last evening; closed this morning, six measured parcels later.
**2.067 → 1.192 frames/tick at sustained max-diagonal; work/tick 190,931 → 123,016 (−35.6%), now under the 128,000 line on the mean.** Full story with corrected bookings: `docs/benchmarks/streaming/ARC-CLOSEOUT.md`. The honest residual: the last 0.192 is **tick-to-tick variance** (5 of 31 frames still spike past the line) — nothing has measured which ticks and why. That's the named successor, and oracle's per-frame profiler rows are the purpose-built instrument for it once the corpus A/B lands on their side.

## P3 Phase 0 (instruments-first)

- **T1 done** — the anchor's "two regimes" never existed: both were instrument defects (per-frame rows at 30/31 truth + a missing shift term). Anchor = 982.2 + 59.27×overlay_trips, model residual 195.9 → 13.3.
- **T2 done** — hscroll ramp probe, proven red before any curve exists.
- **T3 + T4 dispatched** (in flight as of this writing): the re-glue/transition-frame instrument and the axis-5 SAT reservation. They finish Phase 0; the checkpoint then gates Tasks 10/12.

## Waiting on you (unchanged, no action taken)

- F6 margins — you deferred; with the mean under the line its urgency dropped further. Only worth revisiting if the variance work wants headroom.
- Seraph S0 execution go; wiki stable-sections go; the P3 plan's 7 PARKs.

## Incidents (all resolved, all banked to memory)

- My unscoped `pkill` killed an agent's live emulators once — rule now: kill only PIDs whose cmdline matches the worktree's ROM path.
- F2's memo rename broke refreeze mid-run (partial goldens) — reset + carrier ripple pattern applied; suite fully green after.
