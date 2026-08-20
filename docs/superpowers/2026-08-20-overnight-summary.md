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

## P3 Phase 0 — COMPLETE (instruments-first, all four merged)

- **T1** — the anchor's "two regimes" never existed: both were instrument defects (per-frame rows at 30/31 truth + a missing shift term). Anchor = 982.2 + 59.27×overlay_trips, model residual 195.9 → 13.3.
- **T2** — hscroll ramp probe, proven red before any curve exists.
- **T3** — the re-glue instrument: 18-position vertical sweep exact (poison 18/18 red first), and the synthesized transition frame measured — surcharge ~+900-1,100 cyc on `Parallax_Update`, +0 DMA bytes. Closes P2 Task 12's blocker (b); blocker (a) (the Label-typed section→scene join) stays open. Also found: the plan's "differ-in-HScroll-mode" transition pair doesn't exist in shipped content (all 20 scenes attach H-deform), and `[parallax.cost_model]` was stale post-unroll — re-measured rows booked as `postunroll_*` for Task 13.
- **T4** — axis 5's denominator measured (idle: 3/80 SAT slots, worst line 2/20 sprites); ruling: the axis gates on the per-line sprite count. **Design-changing flag: the left-column mask really costs 7 SAT slots full-height, not the 1 the plan priced** — carried onto Task 12's section.
- **Checkpoint passed** → Phase 1 open and moving:
  - **T5 MERGED** (`ee2751dc`) — the two P3 capability bits are gateable; zero-byte proven
    on all four shapes; +2 derived span tests (gapless-bit-run, bare-prefix rule).
  - **T6 MERGED as a pair** (aeon `95538920` / sigil `3dae4bd2`, chain 156, suite 3752/0)
    — ONE comptime fold (`scene_forces_per_line`) + ONE runtime splice
    (`parallax_mode_key`) now feed both mode twins; the P1 precision fence retired.
    **C1 RULED: 896 B / one entry per frame** — the recorded 1792 was queue residue (the
    DMA drain resets cursors, never bytes; the scanner read live+residue
    indistinguishably; three independent tells). Budget re-attributed with the guard sum
    unchanged. sonic4 −74 B = deb2 span-name merge only, 533/533 procs byte-identical.
  - **Landing trap found + banked** (OVERSEER.md): the main tree now carries live
    editor/baked content, and repin, refreeze AND the sigil suite each default to it —
    all three legs must be pointed at a clean checkout explicitly. The dirty-tree suite
    run read 111 false failures; the clean rerun isolated the 4 real ones (the
    mode-key port ripple, fixed with a verbatim AST-extraction shim).

## The profiler corpus A/B PASSED — and revised our own margin

Oracle's evidence doc (`oracle/docs/2026-08-20-profiler-corpus-ab.md`) validated their new
profiler cycle-exact against ours, and found the OLD instrument accounts for only **78.45%**
of a maxdiag frame. Consequences, all booked (aeon `971ef142`): the migration ledger is
flipped; the dense −242 anomaly resolved as our old instrument's defect (measured == model);
the arc's "mean 4,984 under the line" was briefly downgraded to a hypothesis — and then:

## The tick-variance retake RAN — the arc's last question is answered

`docs/benchmarks/streaming/TICK-VARIANCE.md` + `tools/tick_variance_probe.py` (the first
probe living on the new, validated profiler; control row reproduced exactly against the A/B's
pinned reference before any new number). The headline: **the honest mean is 112,897
work/tick — 15,103 UNDER the line, three times the margin the old instrument claimed.** And
the spikes have ONE named cause: 3 of 26 ticks carry 25-49k cycles of `S4LZ_DecompressDict`
on block-COLUMN crossings (one per 128 px of camera travel); row crossings are nearly free
because their blocks are already staged. Stall: 2,216 cyc/frame, all VBlank DMA drain, flat —
not part of the variance. Two honestly-unresolved riders booked: why the row side is covered
(hypothesis + settling experiment), and a cross-emulator tick-count divergence (old oracle
1.192 f/t vs new 1.069 on byte-identical ROM — relayed to the oracle session, engine not
implicated). **F6 stays parked exactly as you left it** — the doc gives the arithmetic, no
recommendation.

## Waiting on you (unchanged, no action taken)

- F6 margins — you deferred; with the mean under the line its urgency dropped further. Only worth revisiting if the variance work wants headroom.
- Seraph S0 execution go; wiki stable-sections go; the P3 plan's 7 PARKs.

## Incidents (all resolved, all banked to memory)

- My unscoped `pkill` killed an agent's live emulators once — rule now: kill only PIDs whose cmdline matches the worktree's ROM path.
- F2's memo rename broke refreeze mid-run (partial goldens) — reset + carrier ripple pattern applied; suite fully green after.
