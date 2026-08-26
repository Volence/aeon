# The insta-shield is the ONLY behavioural change that disturbs the replay net

**Measured 2026-08-26.** Decision d-14 ruled prove-then-restamp: before the owner's recorded
regression net is re-recorded, buy the proof that the insta-shield is the only thing that moved
it. This note is that proof. **Nothing was re-recorded.**

## Verdict

**PROVEN.** With everything else that is on master today and only the insta-shield removed, both
committed fixtures replay clean to the end and the negative control fires. The paired control
(same environment, same runner, shield still in) reproduces the booked desync exactly.

| tree | `ojz_fixture` | `ojz_slide_fixture` | negative control |
|---|---|---|---|
| master `b87e6e5a` (shield IN) | **DESYNC** tick 1282, actual `$BC3A6AE9` / expected `$BBB93779` | PASS | — |
| master minus shield `3c893cb7` | **PASS** (ran to end, 1723 ≥ 1721 ticks) | **PASS** (2352 ≥ 2350 ticks) | **PASS** (trap fired) |

The 2×2 is what makes the green mean something: a bare pass on the reverted tree only shows the
runner did not complain, whereas the master row shows this same runner, this same build
environment, catching the divergence it is supposed to catch on the very fixture in question.

## What this licenses, and what it does not

**Licenses:** the eighteen commits that landed after the shield merge — an authored background
band, the parallax-resolver/boot-override work, the gate cutover onto `AetherInstance`, docs —
carry **no** player-behaviour divergence. They have had no replay-net coverage since the net went
red, and this is that coverage, retroactively.

**Does not license:** anything about whether the shield's *own* divergence is correct. That was
already established (screenshot at the 1282 halt shows Sonic airborne inside the shield flash).
The re-stamp remains the owner's call, exactly as `docs/DEFERRED_WORK.md` books it.

**Effect on the booking:** the "a re-stamp also silently absorbs any OTHER divergence in the same
run" objection in `docs/DEFERRED_WORK.md` (heading `REPLAY FIXTURE \`Replay_OJZ_Fixture\` DESYNCS
SINCE THE INSTA-SHIELD`) is now **discharged for the tree as of `b87e6e5a`**. There is no other
divergence to absorb. `DEFERRED_WORK.md` is deliberately NOT edited on this throwaway branch (it
would not cherry-pick cleanly alongside this note); narrowing it is a master-side edit.

## Method

Branch `proof/instashield-only-change`, cut from **current master `b87e6e5a`** — not from the
pre-merge tree `3c0ef624`. Reverting on top of master is the whole point: checking out the
pre-merge tree would only re-prove that the fixture matched *before* the shield, which was never
in doubt, and would grade none of the eighteen later commits.

```
git checkout -b proof/instashield-only-change b87e6e5a
git revert --no-edit -m 1 8d289459     # -> 3c893cb7, NO conflicts
```

The revert applied clean: 19 files, 11 insertions, 1902 deletions, including
`games/sonic4/player/player_instashield.emp`, the `player_common.emp`/`sonic.emp` hooks, the
mappings/DPLC/animation blobs, the `map.toml` + `vram.toml` rows, and the tool/test scaffolding.
`docs/DEFERRED_WORK.md` auto-merged. **The reverted tree was never hand-repaired** — a tree you
have to fix up is no longer "master minus the shield" and would not answer the question.

Environment:

```
SIGIL_BUILD=/home/volence/sonic_hacks/sigil/target/release/sigil
SIGIL_EMIT=/home/volence/sonic_hacks/sigil/target/release/emit_sound_blob
AEON_SKDISASM_DIR=/home/volence/sonic_hacks/skdisasm
ORACLE_NEXT=/home/volence/sonic_hacks/oracle          # oracle-next is a symlink to oracle
```

Runner (read-only consumer of the oracle repo at `0d7c5c21`, `main`; nothing changed there):

```
cd /home/volence/sonic_hacks/oracle && cargo build --release -p oracle-replay
   Compiling oracle-replay v0.0.0 (/home/volence/sonic_hacks/oracle/crates/oracle-replay)
    Finished `release` profile [optimized] target(s) in 0.76s
```

Fresh-worktree level staleness cleared first with `tools/regenerate-level.sh`
(`verify_level_bin: OK`, 9 sections rebuilt, blob dedup saved 6040 B).

Build and run, per tree:

```
rm -f s4.debug.bin
DEBUG=1 ./build.sh sonic4
replay_runner --rom s4.debug.bin --lst s4.debug.lst --fixture ojz_fixture
replay_runner --rom s4.debug.bin --lst s4.debug.lst --fixture ojz_slide_fixture
replay_runner --rom s4.debug.bin --lst s4.debug.lst --negative-control
```

These are exactly the four steps `./test.sh` section 8 performs; they were run directly so the
verdict could not be diluted by unrelated sections. Only the DEBUG sonic4 shape was built — the
four-shape rule is relaxed for this throwaway proof artifact per the parcel brief, and the runner
refuses a release ROM by design because `replay.emp` gates the checkpoint compare on `DEBUG == 1`.

## Artifacts

| tree | DEBUG ROM crc32 | length |
|---|---|---|
| master `b87e6e5a` | `8279a3fe` | 715582 |
| reverted `3c893cb7` | `4a6fb3de` | 715356 |

`4a6fb3de` was produced twice from two independent canonical builds and matched, and also matched
the `FAST=1` build of the same tree — the documented FAST/canonical byte-identity contract holds
here. Every graded ROM was deleted before its build, so its existence proves this run made it.

## Full runner output

### Reverted tree `3c893cb7` — `ojz_fixture`

```
replay_runner
  rom      s4.debug.bin (715356 bytes)
  lst      s4.debug.lst
  fixture  ojz_fixture
  rom: contains `REPLAY DESYNC` — the DEBUG checkpoint compare is present
  lst: 2692 symbols, bound to this ROM (deb2 appendix at $0A32A0, 47036 bytes)
  anchors  init=$0A1724 fixture=$0A1F90 blob=$0A234A
           Logic_Tick=$FF8004 Input_Source=$FF8036 Replay_Done=$FF8038 Replay_Ptr=$FF803C
  stream   ARP0 flags=$00 ticks=1721 core_hash=$7054D28B (stale, not a guard) seed=$00000000 body=$0A1FA4
  run      armed at frame 34, 1778 frames after the arm

PASS — the stream ran to its end, corroborated three ways.
  Replay_Done  = $FF
  Logic_Tick   = 1723 >= the 1721 ticks the header declares (an overshoot is normal — the game keeps running on live input after end-of-stream)
  Input_Source = $00 — self-cleared on the completion path
  Replay_Ptr   = $000A2096 — fixture+262, well past the 20-byte header
EXIT=0
```

### Reverted tree `3c893cb7` — `ojz_slide_fixture`

```
replay_runner
  rom      s4.debug.bin (715356 bytes)
  lst      s4.debug.lst
  fixture  ojz_slide_fixture
  rom: contains `REPLAY DESYNC` — the DEBUG checkpoint compare is present
  lst: 2692 symbols, bound to this ROM (deb2 appendix at $0A32A0, 47036 bytes)
  anchors  init=$0A1724 fixture=$0A20A0 blob=$0A234A
           Logic_Tick=$FF8004 Input_Source=$FF8036 Replay_Done=$FF8038 Replay_Ptr=$FF803C
  stream   ARP0 flags=$00 ticks=2350 core_hash=$7054D28B (stale, not a guard) seed=$00000000 body=$0A20B4
  run      armed at frame 34, 2415 frames after the arm

PASS — the stream ran to its end, corroborated three ways.
  Replay_Done  = $FF
  Logic_Tick   = 2352 >= the 2350 ticks the header declares (an overshoot is normal — the game keeps running on live input after end-of-stream)
  Input_Source = $00 — self-cleared on the completion path
  Replay_Ptr   = $000A21EE — fixture+334, well past the 20-byte header
EXIT=0
```

### Reverted tree `3c893cb7` — negative control

```
replay_runner
  rom      s4.debug.bin (715356 bytes)
  lst      s4.debug.lst
  fixture  ojz_fixture
  rom: contains `REPLAY DESYNC` — the DEBUG checkpoint compare is present
  lst: 2692 symbols, bound to this ROM (deb2 appendix at $0A32A0, 47036 bytes)
  NEGATIVE CONTROL: checkpoint payload at $0A1FA6 patched $1D375066 -> $DEADBEEF — the trap MUST fire
  anchors  init=$0A1724 fixture=$0A1F90 blob=$0A234A
           Logic_Tick=$FF8004 Input_Source=$FF8036 Replay_Done=$FF8038 Replay_Ptr=$FF803C
  stream   ARP0 flags=$00 ticks=1721 core_hash=$7054D28B (stale, not a guard) seed=$00000000 body=$0A1FA4
  run      armed at frame 34, 35 frames after the arm

DESYNC — a checkpoint did not match.
  Logic_Tick 2   expected $DEADBEEF   actual $1D375066
  message  "REPLAY DESYNC" at $00277E
  raised at $002778  (Input_Tick.desync+$4)
  (A7).l   $0000277E
  registers (PRE-CLOBBER — stopped at blob+0, before the handler draws its screen):
    d0 = $1D375066    a0 = $FFFFAC82
    d1 = $00000002    a1 = $000028C6
    d2 = $DEADBEEF    a2 = $FFFF8980
    d3 = $0000FFFF    a3 = $FFFF8990
    d4 = $000000E0    a4 = $FFFF889A
    d5 = $000000E0    a5 = $00000000
    d6 = $0000FFFF    a6 = $00000000
    d7 = $00000006    a7 = $FFFFFEF8
    pc = $000A234A    sr = $2300
  work RAM Logic_Tick=2 Replay_Done=$00 Input_Source=$01 stream offset 26

NEGATIVE CONTROL PASSED — the corrupted checkpoint tripped the gate: `REPLAY DESYNC` at Logic_Tick 2, expected $DEADBEEF (the payload we wrote), actual $1D375066
  (the corruption was planted at $0A1FA6; the gate demonstrably fails when it should)
EXIT=0
```

### Control — master `b87e6e5a` (shield IN), `ojz_fixture`

```
replay_runner
  rom      s4.debug.bin (715582 bytes)
  lst      s4.debug.lst
  fixture  ojz_fixture
  rom: contains `REPLAY DESYNC` — the DEBUG checkpoint compare is present
  lst: 2708 symbols, bound to this ROM (deb2 appendix at $0A32A0, 47262 bytes)
  anchors  init=$0A1724 fixture=$0A1F90 blob=$0A234A
           Logic_Tick=$FF8004 Input_Source=$FF8036 Replay_Done=$FF8038 Replay_Ptr=$FF803C
  stream   ARP0 flags=$00 ticks=1721 core_hash=$7054D28B (stale, not a guard) seed=$00000000 body=$0A1FA4
  run      armed at frame 34, 1329 frames after the arm

DESYNC — a checkpoint did not match.
  Logic_Tick 1282   expected $BBB93779   actual $BC3A6AE9
  message  "REPLAY DESYNC" at $00277E
  raised at $002778  (Input_Tick.desync+$4)
  (A7).l   $0000277E
  registers (PRE-CLOBBER — stopped at blob+0, before the handler draws its screen):
    d0 = $BC3A6AE9    a0 = $FFFFAC82
    d1 = $00000502    a1 = $000028C6
    d2 = $BBB93779    a2 = $FFFF8980
    d3 = $0000FFFF    a3 = $FFFF8990
    d4 = $000000E0    a4 = $FFFF889A
    d5 = $000000E0    a5 = $00000000
    d6 = $0000FFFF    a6 = $00000000
    d7 = $0000FFFF    a7 = $FFFFFEF8
    pc = $000A234A    sr = $2300
  work RAM Logic_Tick=1282 Replay_Done=$00 Input_Source=$01 stream offset 202
EXIT=2
```

### Control — master `b87e6e5a` (shield IN), `ojz_slide_fixture`

```
PASS — the stream ran to its end, corroborated three ways.
  Replay_Done  = $FF
  Logic_Tick   = 2352 >= the 2350 ticks the header declares
  Input_Source = $00 — self-cleared on the completion path
  Replay_Ptr   = $000A21EE — fixture+334, well past the 20-byte header
EXIT=0
```

(`ojz_slide_fixture` passes on BOTH trees, as predicted: it has zero A/C press edges, so the
shield cannot reach it. Its identical `Replay_Ptr`/`Logic_Tick` across the two trees is a second,
independent sighting of the address-free hash surviving a 226-byte ROM size change.)

## Timings, each with its wall clock

| step | wall clock (`uptime`) | cost |
|---|---|---|
| `cargo build --release -p oracle-replay` | 09:13, load 1.47 | 0.76 s |
| `tools/regenerate-level.sh` (fresh worktree) | 09:15:17, load 1.14 | ~19 s |
| `FAST=1 DEBUG=1 ./build.sh sonic4` (reverted) | 09:16:16, load 1.83 | 2 s |
| `DEBUG=1 ./build.sh sonic4` (reverted) | 09:16:27 → 09:17:29, load 1.78→2.07 | 62 s |
| three runner invocations (reverted) | 09:17:38 → 09:17:57, load 2.12→1.95 | 4 s + 5 s + <1 s |
| `DEBUG=1 ./build.sh sonic4` (master control) | 09:18:10 → 09:19:14, load 2.18→2.62 | 64 s |
| two runner invocations (master control) | 09:19:20 → 09:19:23, load 3.05 | 3 s + 5 s |
| `DEBUG=1 ./build.sh sonic4` (reverted, reproducibility) | 09:19:50 → 09:20:53, load 3.40→3.09 | 63 s |

## Findings the parcel did not go looking for

1. **`rm -f s4.debug.lst` before a canonical build is a hard failure, not a clean slate.**
   Deleting the listings as part of the "prove the artifact is fresh" step made the *first*
   canonical build fail with exit 1 in the pytest lane — `tools/test_bg_emit.py` has three tests
   (`test_rom_ceiling_fits_the_room_every_present_shape_derives`,
   `test_report_prints_no_placer_room_and_names_the_binding_limit`,
   `test_rom_room_matches_a_hand_computation_from_the_instruments`) that require `s4.lst` or
   `s4.debug.lst` to exist and deliberately `fail` rather than skip when neither is present. That
   lane runs BEFORE any ROM is emitted, so the failure is not a verdict about the tree. Aggregate
   was `3 failed, 1385 passed, 7 skipped, 49 subtests passed in 14.43s`. The workaround used here
   — bootstrap a listing with `FAST=1`, delete only the `.bin`, then run the canonical build —
   keeps the freshness proof for the graded artifact. Worth knowing before the next
   delete-then-build ritual.

2. **The level re-bake is byte-neutral on this tree.** `tools/regenerate-level.sh` in a fresh
   worktree left exactly one file modified, `DONOR_PROVENANCE.json`, and only its `generator.head`
   / `modified_tracked` self-stamp. All level bytes were identical. That file was restored so the
   tree stayed exactly "master minus the shield".

3. **Two brief facts needed correcting (both harmless).** `replay_runner` *was* already built (17
   Aug); it was rebuilt anyway, which took 0.76 s. And `docs/DEFERRED_WORK.md` records master's
   DEBUG crc as `2bc51d79`, measured at `5f4d00ee`; master is `8279a3fe` today — content and gate
   commits have landed since. Everything else in the brief checked out: the merge SHA `8d289459`
   and its parents, the eighteen post-shield commits, the tick, both hashes, and the address-free
   hash coverage documented at `engine/system/replay.emp:8-92`.

## This branch must never merge

`proof/instashield-only-change` exists to produce evidence and nothing else. Its first commit
deletes a shipped feature. Only this note is meant to travel — cherry-pick it onto master on its
own.
