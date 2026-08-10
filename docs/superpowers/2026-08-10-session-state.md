# Session state — 2026-08-10 (supersedes the 2026-08-09 work order's status)

The 2026-08-09 handoff (`2026-08-09-next-session-handoff.md`) is still the
reference for standing operational facts (build env, replay-net runbook, oracle
policy, ritual). This file records what that work order's five workstreams
actually produced. BG-graphics streaming remains ON HOLD by user instruction.

## Closed this session

**Workstream 5 — silent music: RESOLVED, not a bug.**
Canonical playback works; the pkg-1 session's raw `SND_REQ_MUSIC` poke was an
unsupported entry (trigger without the 6-byte `SND_MUSIC_PARAM` block).
Real-audio A/B vs config-a: band-energy cosine 0.9999. Pkg 5 unblocked.
→ `notes/2026-08-10-silent-music-adjudication.md`

**Workstream 3 — famine: ROOT-CAUSED, no fix (per ruling).**
Deterministic capacity arithmetic: OJZ act1 build-pins 4 of 10 pages, the dense
window concurrently references 6 transients, `STRESS_EVICT_FRAMES` = 9. Predates
patch-run batching (clean A/B with era-matched chain-80 sigil binaries). The
2026-08-09 "prebatch scene unresponsive" confound was an armed-playback replay
trap, not a build difference. Fix design folds into C4-3; top option = strip-gen
emits per-act `MAX_CONCURRENT_PAGES` and `ensure`s the clamp, turning famine
into a build error. → `notes/2026-08-10-famine-root-cause.md`

**Workstream 1 (pkg 3) — MERGED** (aeon `4a411dc2`, sigil chain 85).
12-byte `DacSample`, Bank-D twin emitter, authoring runbook. **Gate catch worth
remembering:** a build-green parcel silently broke plain-shape SFX — the sigil
chainer 8-aligns bank-section bases while the seam-2 fold packs contiguously, so
the head growth put every `SfxTable` pointer 2 bytes low (debug survived by
parity luck). Caught only by the oracle real-output gate on the *plain* shape.
Fixed with comptime mod-8 pads; sigil ask ledgered (fold==placement must become
a build gate). **Rule going forward: real-output gates on BOTH shapes.**

**R5 rider (flam trace): not reproduced, no fix booked.** 13 steal/restore
cycles, zero flam pairs ≤1.5 frames. Route audit correction: jump `$62` is
PSG-only, so only 3 of those were FM steals. The structural narrowing is the
stronger result — the hazard needs `MEV_PITCHENV` on a stolen channel, which no
shipped song has. → `notes/2026-08-10-r5-rekey-flam-trace.md`

## Needs an owner ruling

**Workstream 4 — diagonal hoist: BUILT, GATED, UNMERGED.**
`perf/fillcol-hoist` (T1-T5, tip `118c184a`). Correctness fully green — both
replay fixtures hold with all checkpoint hashes matching, refcount audit clean,
patch runs unchanged. But **no measurable lag win**: 61 → 63 lag per 270 frames
for +430 B ROM / +138 B RAM. Two attributable wins are real but small
(`Draw_TileColumn` −14%, `FindStagedBlock` 13→11 calls). **Pick one:**
1. cherry-pick T1 only (`903bfde` — the one clean measured win, +42 B, no RAM),
2. merge whole (savings real, below this measurement's noise floor),
3. re-measure with a position-matched harness first (drive to a fixed camera-X,
   count frames — fixed-frame windows drift in content by ~3.1k decompress
   cycles, which swamps the signal).
The DEFERRED_WORK diagonal entry has been corrected: the copy chain is NOT the
top lever; the flat decompress/patch-run/HInt taxes are.
→ `notes/2026-08-10-fillcol-hoist-ab.md` + `-baseline.md`

**Workstream 1 (pkg 4) — MERGED** (aeon `d9582b83`, sigil chain 86). D4 PSG
transpose, D1/D6/D7 producer rules, B3 AM bit, E5 SSG-EG, and the R1 drain
guard — all funded by Task 0's **-98 B item-25 reclaim**, so the blob came out
SMALLER than it went in (plain 6255→6164, debug 6381→6294) and **debug headroom
is 90 B, not 3 B**. The ceiling that shaped packages 1-3 is retired. H1 stays
excluded for the tempo-contract parcel.

D4's gate is worth reusing: shipped content has `sc_transpose` = 0 everywhere,
so the fix is latent and whole-song A/B proves nothing. Poke `sc_transpose`=+12
onto live PSG SeqChannels and compare **VGM divisor values** against the
pre-package build — the control stays overlapping, package 4 moves disjointly
an octave up (214 → exactly 107).

Deferred out of the package with full costing: **B5** (dash noise sweep) needs
an SFX noise-mode carrier that cannot live in the shared channel prefix.
Also found: `pack_sfx` never calls `Event.validate`, so no song_packer rule
reaches SFX streams (ledgered class risk), and F3/F4 are less closed than the
plan claimed.

## In flight

Nothing. All spawned work is merged or explicitly parked.

## Not started

- **S3K drum-kit content pass** — now unblocked (pkg 3 shipped the runbook).
  Survey done: `docs/research/2026-08-10-s3k-dac-kit-survey.md` (51 source WAVs,
  id→multiplier table, ~350-400 KB resampled, spans several Z80 banks, needs
  per-bank packing). Serialize AFTER pkg 4 — it grows `dac_sample_tab.emp` and
  the bank head, i.e. exactly the files pkg 4's ritual touches.
- **Pkgs 5 → 6**, then the R6 format revision + tempo-contract plan-writing.
  Package 5 is unblocked (the silent-music question that gated it is resolved),
  and the 90 B of reclaimed headroom means neither package has to open with a
  reclaim. Package 6 still carries the R2 observability rider.

## Ritual gotcha learned this session (cost two blocked agents)

**Two parallel byte-parcel lanes cannot share one sigil binary pair.** The D1c
contract baseline is a multiset equality, so a row added for branch A's shape
GONE-fires on master and on branch B. Never pre-add baseline rows for an
unmerged branch — land them in that branch's merge-time lockstep. Give each lane
era-matched binaries from a sigil scratch worktree and verify each pair
reproduces its lane's golden crc before handing it to a porter.
