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

## In flight

**Workstream 1 (pkg 4) — porter running** on `sound-pkg4` (worktree
`.claude/worktrees/agent-a9f1ee9b108186e74`). Task 0 landed: `d69847cd`
reclaimed **98 resident Z80 bytes** (debug blob 6381→6283), so the old 3-byte
ceiling is no longer the binding constraint — ~101 B of headroom funds D4, R1,
B5 and E5. Remaining: D4 PSG transpose, D1/D6/D7 packer rules, B3 AM bit, the
R1 drain-underrun guard, B5, E5, tracking closure.
Controller owes at its gate: oracle D4 check (spindash-rev PSG pitch tracking),
R1 before/after, rendered-audio A/B on **both** shapes, blob-length repin
(BLOB_LEN_* + `Z80_SOUND_SIZE` mirrors — the reclaim shrinks the blob), merge.

## Not started

- **S3K drum-kit content pass** — now unblocked (pkg 3 shipped the runbook).
  Survey done: `docs/research/2026-08-10-s3k-dac-kit-survey.md` (51 source WAVs,
  id→multiplier table, ~350-400 KB resampled, spans several Z80 banks, needs
  per-bank packing). Serialize AFTER pkg 4 — it grows `dac_sample_tab.emp` and
  the bank head, i.e. exactly the files pkg 4's ritual touches.
- **Pkgs 5 → 6**, then the R6 format revision + tempo-contract plan-writing.

## Ritual gotcha learned this session (cost two blocked agents)

**Two parallel byte-parcel lanes cannot share one sigil binary pair.** The D1c
contract baseline is a multiset equality, so a row added for branch A's shape
GONE-fires on master and on branch B. Never pre-add baseline rows for an
unmerged branch — land them in that branch's merge-time lockstep. Give each lane
era-matched binaries from a sigil scratch worktree and verify each pair
reproduces its lane's golden crc before handing it to a porter.
