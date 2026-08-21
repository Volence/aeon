# Aeon overseer handoff — 2026-08-21 (post-/clear rotation)

You are the aeon overseer. Boot: `docs/OVERSEER.md` (role, landing ritual, instrument
table). This file is the STATE — what the previous incarnation left you, verified and
pushed. Read `docs/DEFERRED_WORK.md`'s top block after this.

## Where things stand

**P3 (scanline walker mechanisms, `docs/superpowers/plans/2026-08-20-scanline-p3-walker-mechanisms.md`):
T1-T11 LANDED.** Phase 0 complete (four instruments), Phase 1 complete except T12.
Chains 156-158 as aeon+sigil pairs (T6 forcer / T7 world-Y re-glue / T10 curves);
T8/T9/T11 were byte-identical aeon-only landings. Suite bar: **3752 passed / 0 failed**,
held green across every landing. Current CRCs: s4 `060401e4`, s4.debug `0dbaa80f`,
demo `c708b114`, demo.debug `dec88cc1`.

**The streaming arc is CLOSED and its variance question ANSWERED**
(`docs/benchmarks/streaming/ARC-CLOSEOUT.md` + `TICK-VARIANCE.md`): honest mean 112,897
work/tick (15,103 UNDER the line); the spikes are `S4LZ_DecompressDict` bursts on
block-COLUMN crossings. **The owner FELT this lag in play** ("big lag jumping and
holding diagonal as we cross some sections").

## The two approved lanes (owner: "sounds fine to me to have them both", 2026-08-21)

1. **P3 tail**: dispatch **T12** (left-column mask — read the plan section INCLUDING the
   blockquote flag: the mask really costs **7 SAT slots full-height, not 1**; the
   executor must accept-7 / bound-height / taller-primitive with justification, and the
   first-sprite-on-line exemption needs verifying). Then Phase 2: T13 re-fit (model
   baseline = the `postunroll_*`/`reglue_*` rows + T9/T10's new columns), T14 axis-5
   gate, T15 poisons (arm-5 + curve reachability are on its list), T16 witness+spans.
2. **Burst-smoothing lane** (runs alongside; disjoint files): settling experiment FIRST —
   why are ROW crossings ~free (blocks already staged) while COLUMNS pay 25-49k in one
   tick — then give columns the same early staging. F6 margins only if that isn't
   enough. Instrument: `tools/tick_variance_probe.py` (new-oracle profiler, the only
   migrated probe); CR-28's caller breakdown ships soon and is purpose-built for this.

## Cross-suite state (live contracts)

- **sigil-83**: their `feat/game-defines` parcel (map.toml `[defines]` per-game rows —
  our T8 ask) is DONE, HOLDING for our go per the sequencing contract (no sigil-binary
  merge while an aeon parcel is mid-flight; ping → idle-or-busy → hold). The previous
  incarnation owes them the go signal post-T11 (may already be sent — check the
  transcript tail). **We owe the adoption check when it merges**: re-run T8's three
  contexts with a capability-derived define (recipe: `EXTENDED-RECORD.md`), exercise
  the struct-offset harvest (context 2) explicitly. Cross-ledger: their d3a8c91d ↔ our
  DEFERRED_WORK entry.
- **oracle-next-f3**: CR-28 (in-row `callers[]`, entryKind hint/vint/root/depthCap)
  adjudicated + accepted (`docs/benchmarks/streaming/CR28-DEMAND.md` is our anchor);
  implementation in flight, ship notice will arrive with SHAs. Also open on their
  ledger: F-TICK-BOUNDARY-DIVERGENCE (cross-emulator tick counts; settling experiment
  named in TICK-VARIANCE §1.2, whoever reaches it first pings).
- **aurora-86**: sprite-export consumer BOOKED (DEFERRED_WORK; format ruling = neutral
  json+bin in, aeon bake generates code). Not scheduled; they have no blocking pressure.
- **aeon-05**: a second aeon session exists, conversational-only, will ping before
  touching files.

## Standing rules that bit someone this session (beyond OVERSEER.md)

- The main tree carries the OWNER's live editor content (~43 files) that will not clear:
  every landing leg — `repin --aeon`, refreeze `AEON_DIR`, suite `AEON_DIR` — points at a
  clean worktree of the merge SHA, and a fresh clean worktree needs one build first.
- Suite runs: detach with setsid + done-marker + Monitor (the 10-min Bash cap kills
  foreground runs); aggregate `test result:` lines with awk, never tails.
- Emulator lanes run ALONE (concurrent probe lanes wedge); kill only PIDs whose
  /proc/cmdline names your worktree's ROM.
- Byte-moving is routine — repin/refreeze/suite without asking; byte-IDENTICAL parcels
  still get the clean-checkout CRC check and (if any cross-seam name moved) the suite.
- `emulator/scanlines` at count 56 closes the bus (32 is safe) — recorded in
  `tools/vsplit_landing_gate.py`.

## Owner-pending (do NOT act without them)

PARK-1 deform/curve/vsplit content adoption (visible showcase = Parcel D, Aurora-authored;
the owner was told adoption is cheap and a proof-of-vocabulary scene was OFFERED — no
answer yet); the P3 plan's 7 PARKs; F6 proper; wiki stable-sections; seraph S0.

## Booked findings worth remembering

Axis 4b's hint-total ensure is VACUOUS against any accepted program (check_density and
RASTER_BUF_SIZE bind first — T11's finding, booked in DEFERRED_WORK). The T10 curve
carry aliases Shadow_Bands at CURVE_CARRY_WORDS=0 (the port carrier row documents it).
