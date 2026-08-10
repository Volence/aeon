# Next-session handoff — 2026-08-09 (post pkg-1 / trio / net-restore session)

User-scoped work order for the next session(s). BG-graphics streaming is ON
HOLD by user instruction (its two design rulings stay queued — do not start
it). Everything below is user-approved to execute.

## Standing operational facts (read first)

- Build env (build.sh hard-errors without these):
  `SIGIL_BUILD=/home/volence/sonic_hacks/sigil/target/release/sigil`
  `SIGIL_EMIT=/home/volence/sonic_hacks/sigil/target/release/emit_sound_blob`
  Shapes: `./build.sh` (release) / `DEBUG=1 ./build.sh` (debug) /
  `./build.sh demo` / `DEBUG=1 ./build.sh demo`. Delete-first before gates.
- Both repos' masters are LOCAL-ONLY (nothing pushed): aeon at the
  roadmap-sync commit after trio merge `7afc553f`; sigil master at chain 83.
- Byte-changing parcels take the sigil ritual: repin (`cargo run -p
  sigil-harness --bin repin --release`, AEON_DIR + SIGIL_EMIT + SIGIL_BUILD
  set) → hand-ledger narration (`crates/sigil-harness/tests/repin_pins.rs` +
  any test-local mirrors that fail) → `refreeze --freeze <name> --ab <evidence>`
  → full workspace suite green → merge BOTH repos. Precedent commits: sigil
  `473969fb` (blob-changing, pkg 1) and `7559a6e8` (code-shift, trio).
- Replay regression net (the merge gate for anything gameplay-visible):
  runbook in `docs/superpowers/notes/2026-08-09-replay-net-rerecord-ab.md` —
  anchor bp `GameState_OJZScroll_Init` BEFORE `reload_rom`, poke
  `Input_Source` (=1 playback / =2 record) + `Replay_Ptr` = fixture+20.
  Dump/inject via the aether bus (socket `/run/user/1000/oracle.sock`,
  `sys.path.insert(0, "/home/volence/sonic_hacks/empyrean/clients/python")`,
  `from aether import BusClient`) — NEVER hand-transcribe hex dumps.
  Behavior-changing parcels desync the fixtures BY DESIGN → re-record is part
  of their gate. A fresh recording can transiently desync its own replay —
  re-record before suspecting the engine.
- Oracle: ONE instance (`pgrep -a oracle_gui`); binary
  `/home/volence/sonic_hacks/oracle/linux-port/build/oracle_gui <rom>`.
  A DEBUG trap looks like a hang from MCP (`running=true`, frozen
  `Logic_Tick`) — check `status.symbol_at_pc` for ErrorHandlerBlob before
  killing anything. The DEBUG OJZ scene boots with debug-fly ACTIVE (a B tap
  toggles to normal play); the OJZ init swallows ~2,700 frames (~12 s wall)
  before logic ticks flow. NO emulator work from subagents — controller only.
- ~~HARD CONSTRAINT: the debug Z80 sound blob is 6381/6384 bytes — **3 bytes of
  headroom**.~~ **RETIRED 2026-08-10** — package 4's Task-0 item-25 reclaim returned
  98 B against 11 spent, so the blob is now plain 6164 / debug 6294 of 6384 =
  **90 B of headroom**. The reclaim-before-adding discipline below still applies,
  but the ceiling is no longer the binding constraint. Still true regardless of
  the number: any resident Z80 addition wants a reclaim identified first
  (candidates ledgered in DEFERRED_WORK), and blob-size changes need
  `SIGIL_BLOB_LEN_DRIFT=warn` to build, then the BLOB_LEN_PLAIN/DEBUG +
  Z80_SOUND_SIZE (boot_port) + SOUND_API-literal repins (precedent: sigil
  `473969fb`).

## Workstream 1 — Sound packages, order 3 → 4 → 5 → 6

Queue doc: `docs/superpowers/2026-07-03-sound-banking-queue.md` (pkg 1+2 rows
marked EXECUTED; path-migration note at the bottom applies to every plan).
Execution pattern = package 1's (porter subagent in an isolated worktree; the
porter re-anchors stale paths/line numbers by grepping, builds all four
shapes delete-first per commit, never merges/refreezes/runs emulators;
controller gates + rituals + merges). Package-1 gate precedent:
`project_sound_pkg1_done` memory + aeon merge `3d6b92a8`.

- **Pkg 3 — DAC drum-library readiness**:
  `plans/2026-07-03-dac-drum-library-readiness.md`. Mostly mechanical
  (descriptor `ds_vol` + reserved mix-cursor bytes, Bank-D co-location hook in
  the tools, authoring runbook). Descriptors are banked DATA — should not
  touch the resident blob; if any resident byte is needed, reclaim first.
- **Pkg 4 — correctness batch**: `plans/2026-07-03-sound-correctness-batch.md`.
  TRIAGE RIDERS (docs/research/2026-08-08-sound-study-triage.md): **R1**
  (DAC drain underrun guard) + **R5-trace** ride this session.
- **Pkg 5 — production suite**: `plans/2026-07-03-sound-production-suite.md`
  (+ user-approved spec). MEV_EXT sub-ops 1/2 (PUMPSET/GHOSTSET) are reserved
  for it in the registry.
- **Pkg 6 — closeout sweep**: `plans/2026-07-03-sound-closeout-sweep.md`.
  Rider: **R2** (observability cluster).
- After pkg 4: **R6 format revision v1** and the **tempo-contract parcel**
  (user-ruled 2026-08-09: multi-tick tempo as a STRICT SUPERSET — S3K-range
  bit-exact, bounded loop — landing TOGETHER with DEFERRED_WORK item-25 H1;
  one parcel, profiler gate vs the DAC ring lead). Both need plans written
  (writing-plans pass) before execution.

## Workstream 2 — Drum samples: USER RULED 2026-08-09 = Sonic 3 & Knuckles

Content ruling closed: the drum kit sources from **S3K**
(`/home/volence/sonic_hacks/skdisasm` carries the DAC samples). Sequence:
pkg 3 ships the mechanism → then a content pass imports the S3K kit through
the tools pipeline per pkg 3's authoring runbook. Verification per the house
rule: render real audio (vgm capture → wav) and A/B energy+spectrum against
the S3K originals — not register streams. Note the R9 ruling: DAC playback
RATE stays as-is (headroom banked for polyphonic PCM); the S3K samples get
resampled/re-rendered to OUR rate in the tools, not the other way round.

## Workstream 3 — Stress-crash (famine) investigation

Evidence: `notes/2026-08-09-art-streaming-p2-lens-adjudication.md` (open-debts
item 1's "NEW FAMINE INTEL" block) + `project_evict_witness_famine_intel`
memory. State: on current master's STRESS_EVICT shape (9 frames vs 10 pages;
`STRESS_EVICT=1 ./build.sh` → `s4.stress.bin`), sustained right scroll raises
`PageCache_AllocFrame` "no free/evictable frame" — reproduced with right×900,
burst×5, and a single first right×90 (knife-edge race). Counters at raise:
2 demands / 8 prefetches / stall-watchdog 6 (EARLY famine, not runaway
thrash). The camera in this scene is INPUT-DRIVEN at ~8 px/frame under
debug-fly. An A/B vs pre-batching `517bf4` was CONFOUNDED (that build's scene
does not respond to input — camera parked at 96px, zero streaming counters) —
so whether patch-run batching worsened famine is OPEN, not answered.
FIRST STEP: understand the stress scene's drive semantics on both builds
(why prebatch doesn't move), THEN a clean A/B, THEN root-cause. The fix
design folds into the C4-3 famine-handling question (frames-vs-max-
simultaneously-referenced-pages bound, or famine handling beyond the camera
hold). Only the DEV stress shape raises; release degrades to camera-hold —
but the mega-act goal needs this solved. `tools/evict_witness.py` is the
regression check (its Phase 2 currently reports the famine as a known open
debt without failing).

## Workstream 4 — Diagonal-scroll speedup (FillColumn/Draw_TileColumn hoist)

Measured 2026-08-09, banked in DEFERRED_WORK's diagonal-budget entry
("Measured 2026-08-09" block): max diagonal = 127,962/128,000 cycles —
zero headroom. Targets: `Tile_Cache_Fill` 56.9% incl (`FillRow` 35.9k /
`FillColumn` 28.9k / `CopyBlockColumn` 20.9k at ~2.6k/call /
`FindStagedBlock` 24 calls/frame w/ repeat hits / PatchRuns 32.3k combined —
already-batched, M-1-endorsed). Fix shape = the patch-run precedent
(aeon `eb37f5a`): bank once per column/run, hoist the stage-slot resolve out
of the per-cell path, fold the draw's nametable recompute. The 2026-08-05
owner ruling's revisit condition (P2 merged) is met — cleared to build as its
own parcel. A/B with the lag counter on the dense-region diagonal
(position-matched traverse, currently 29 lag/90f) + the replay net + full
ritual. Semantics must hold: capture-old-before-write, ref-new-then-unref-old,
blank early-outs, miss = demand+stall+skip+continue (DEBUG refcount audit is
the checker).

## Workstream 5 — Silent-music question — RESOLVED 2026-08-10

ADJUDICATED (notes/2026-08-10-silent-music-adjudication.md): canonical playback
is NOT broken — the raw mailbox poke was an unsupported entry (trigger without
the 6-byte SND_MUSIC_PARAM block). Real-audio A/B vs config-a: band-energy
cosine similarity 0.9999. No P1 bug; pkg 5 unblocked. Original question below
for the record.

Evidence in `project_sound_pkg1_done` memory: poking the Z80 mailbox
(`SND_REQ_MUSIC` $1F02 = 1, via z80_write) on canonical DEBUG shapes produces
NO FM audio — request consumed, pkg-1 `SND_STAT_SEQ_ACTIVE` mirror reads 1,
DMA flag toggles normally (~75% duty at OJZ load). IDENTICAL on pre-pkg-1
master → pre-existing, not a pkg-1 regression. Open question: is
canonical-shape music playback actually broken, or is the raw mailbox poke an
unsupported entry (e.g. needs the 68k `Sound_PlayMusic` path's bracket
handshake)? Adjudicate with REAL OUTPUT: drive playback through the 68k API
(oracle-call or a tiny DEBUG hook), capture VGM (`emulator_vgm_start`) or use
the established vgm→wav render pipeline, and compare against the known-good
off-canonical (hotkeys profile, `sigil build --native --config-a`) route that
past fidelity sessions verified. If canonical playback IS broken, that's a
P1 driver bug; fix before pkg 5 (production suite assumes audible output).

## Recommended order

1. Silent-music adjudication (short oracle session; informs everything sound).
2. Pkg 3 porter (+ gate/ritual) → pkg 4 porter (+R1/R5 riders, gate/ritual).
3. S3K drum-kit content pass (needs pkg 3's runbook).
4. Diagonal hoist parcel (level lane, independent of sound lane).
5. Famine investigation (own session, oracle-heavy).
6. Pkgs 5 → 6, then R6 + tempo-contract plan-writing.
