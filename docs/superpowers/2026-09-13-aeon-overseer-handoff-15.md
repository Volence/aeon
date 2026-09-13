# Aeon overseer handoff, 2026-09-13 fifteenth session (booted 15:40Z)

**Read this, then `docs/lane-status.json` (local disk), then `docs/OVERSEER.md` and `docs/DEFERRED_WORK.md` AT
`origin/master`.** Supersedes "Next, in order" of `docs/superpowers/2026-09-13-aeon-overseer-handoff-14.md`.
Figures below were copied from this session's own tool output, not typed from memory.

## ⚠ STILL TRUE: the main folder is the owner's and 221 commits behind (was 212)

Read the boot file with `git show origin/master:docs/OVERSEER.md`, never from disk (WORKING-COPY-CATCHUP, his
card). Do all merging, building and committing from a dedicated worktree. `.aeon-land-0913` is the landing tree,
detached at the last land commit; it is clean apart from build outputs and `.runlogs-control-char46.md5`.

## Landed this session

1. **CHAR-4/6 reproduction write-up** (docs only): merge `bb064477` of `research/char46-repro` (tip `36270961`),
   land commit `a284de00`, on `origin/master` (verified with `ls-remote` and `merge-base --is-ancestor`). It carries
   `docs/superpowers/notes/2026-09-13-char46-repro-recipe.md` and two appended ledger rows (batch `CHAR46-REPRO`).
   Merged-tree `landing_build.sh` gave `finished=0` under sigil `1532b72f`, with all four ROMs md5-identical to the
   pre-merge control (s4 `d83e2780`, s4.debug `6211829d`, demo `1774d78c`, demo.debug `339f50a3`) and all
   rewritten after T0. Test totals: 2606 passed / 0 failed in each of the four shapes, and needs_build 14 ran / 0
   deferred / 0 failed. The lane-log entry is in the land commit.
   - **CHAR-6, measured by the controller:** the glide release under the OJZ act 1 slab (last solid row 511)
     lifts y_pos exactly 9 px (`sub.l d2,6(a0)` at `$1083E`, read from the ROM). The head sensor ends 4 px
     inside the slab and stays embedded for 5 frames (777-781), with no correction.
   - **CHAR-4, measured by the controller:** a glide at integer y 517 embeds the head 4 px at x 888, for 7
     frames (891-897). Every measured frame's y change equals y_vel exactly, and the state stays GLIDE.
   - **Found on the way:** there are four mid-air lift sites, not three (`Climb_LetGo` is the fourth). Our head
     rises 18 px against S3K's 9, and the four S3K restore sites leave y_pos alone (skdisasm :30730, :30893,
     :31031, :31461, read firsthand). Our glide slope landing and `Climb_ReachFloor` lift 9 px on grounded paths
     where S3K does not (note §6(iii)); this is booked in the note and the ledger, not fixed.

## Owner go received this session

**REGIONS parcel 1 STARTS**, owner verbatim 2026-09-13T15:46:57Z, *"also Aeon's v1 above - yyes let's go for
it!"*. Read firsthand at empyrean `ffcaa24`, `docs/OVERSEER.md` lines 74-80, which is an ancestor of
`origin/main`. It selects the v1 design, and Q2 = yes (region edges may sit off the section grid). Parcel 1 is
steps 1-4, then step 5's authored sub-section edge. `lane-status.json` carries it as `REGIONS-P1`, project
`REGIONS`.

## In flight at the time of writing (agents do NOT survive a clear; their commit messages are the record)

**A. REGIONS parcel 1, steps 1-4.**
- Where: branch `parcel/regions-p1`, worktree `/home/volence/sonic_hacks/.aeon-regions-p1`, based on
  `origin/master` at dispatch (`96a98abd`).
- What the brief requires:
  - read the whole design, including §10;
  - one commit per step;
  - four shapes via `landing_build.sh`;
  - the `EndOfRom` delta per step, against the design's figures;
  - the design's inversions, with each mutation shown on disk;
  - the headless gates T1-T4, run on the base tree and on the final tree. T1's detector is repointed at
    `Region_Current` per §10.6;
  - `effects_gates.py` (step 2 touches `engine/effects/preset.emp`);
  - the `ENGINE_ARCHITECTURE.md` §4.2/§7.12 rewrite, in step 4;
  - sigil's suite measured from a fresh sigil worktree (`SIGIL_STRICT_GATE=1 --no-fail-fast`), NOT edited. The
    owner's 09-02 ruling makes drift sigil's after-the-fact finding.
- Expected: about +152 emitted bytes and +12 RAM, and **no pixel changes**.
- If the session was cleared before it reported, read the branch's commits, then re-dispatch or finish from there.
- **Landing A:** it is a byte-mover. It needs the effects-gate ritual. At the push, tell sigil which `*_port`
  tests trip, per the agent's list.

**B. CHAR-4 fix (a ceiling probe for the glide family).**
- Where: branch `parcel/char4-glide-ceiling`, worktree `/home/volence/sonic_hacks/.aeon-char4-fix`, based on
  `origin/master` at dispatch (`96a98abd`).
- What it does: gives the glide, glide-fall and slide a ceiling probe, using the existing `Air_Collide` motion
  classes and `Air_CeilingBump` rather than a second copy.
- Calls to review on return:
  - S3K's left-class $14 cutoff. The brief's default is NOT to reproduce it; ratify or reject the agent's call.
  - What "ceiling" means for the quadrant-rotated slide.
- Proof it owes: `tools/glide_ceiling_witness.py`, red on the base ROM and green on the fix, with a named runner
  or a BLOCKED item. Also `landing_build.sh`, demo unmoved, the cycle cost, and sigil's suite measured.
- It reads the note through the `research/char46-repro` ref, so **do not delete that branch until B has
  returned**. The note is also on `origin/master` at `a284de00`.
- **Landing B:** it is a byte-mover. Append a CHAR-4 row with state `fixed` and `fixedAt` = the merge SHA
  (append-only, same id; see `S0-1`'s pair for the shape).

## Next, in order (re-derive before starting)

0. Review and land A and B as they return, **one at a time**, because byte-movers serialize. Whichever lands
   second re-verifies on the merged tree.
1. **After B lands: dispatch CHAR-6 (the lift). This session deliberately did not dispatch it** (past the clear
   line; see below).
   - Design inputs, from the note §6 (ii): S3K grows the radius about a fixed centre on all four mid-air
     restores and never lifts. Its next frame then corrects the feet (the floor probe) and the head (the ceiling
     probe that B adds).
   - So the likely fix: on the four GLIDEFALL entries (`PState_Glide.release`, `Slide_Terrain.ledge_drop`,
     `Knuckles_Gliding_WallCatch.fall` and `Climb_LetGo`), grow the box about the centre instead of lifting.
     Keep the grounded lifts. Confirm that the one feet-in-floor frame is corrected by `Glide_Collide`'s floor
     snap on the next frame.
   - Its witness is the same script's CHAR-6 leg.
   - The note §6 (iii) grounded-path divergence (the glide slope landing and `Climb_ReachFloor` lift 9 px) is a
     separate row. Do not fold it into CHAR-6.
2. Delete `research/char46-repro` once B has returned (`git -C .aeon-land-0913 branch -d research/char46-repro`).
3. Everything else in the queue waits on the owner, sigil or sequencing (lane-status `queue` says which).

## Driving notes, learned this session (debug build, OJZ)

- Boot lands in debug-fly as the yellow square. **A cycles the character, and needs at least one released frame
  between two A presses** (the press latch is edge-triggered). B leaves fly. Two A presses from Sonic give
  Knuckles (`Character_ID` `$FFFFEC4C` = 2).
- Knuckles' glide: A or C in the air (B is the fly toggle in the debug shape); hold to glide, release to drop.
- `Debug_Warp_Consume` runs its tile-cache reseed inside ONE call that spanned more than 13 frames:
  `Warp_Req_Flag` still read 1 at frame 796 and 0 by frame 856. Wait for 0. The player falls during the wait.
- The emulator has a checkpoint cap of 8. Checkpoint 1 in this session's instance belonged to an earlier
  session's ROM.

## Owner cards open

WORKING-COPY-CATCHUP (221 behind), CTRL-3, EFX-2, CHAR-10, SP6-MODULATION-DIVERGENCE. Nothing new filed.

## Why it will stop

The owner's ~200k clear rule: **371,222 tokens measured from this session's transcript usage record at
2026-09-13T16:35:13Z** (input 32 + cache_read 367,107 + cache_creation 4,083). No new work is dispatched. The
session stops once A and B are landed or handed on, with this file updated at that point.

## Addendum, 2026-09-13 ~17:47Z: B (CHAR-4) LANDED

Merge `6ccf31e6`, land commit `d46e66db`, on `origin/master` (verified with `ls-remote` and `merge-base`).
- **Deviations RATIFIED:**
  - No slide probe. The slide's floor follow owns y and would undo an eject; S3K's `.continueSliding` overwrites
    its own eject the same way (skdisasm :30997-31013, read firsthand).
  - The `dplc_straddle.py` selftest search widened from tile steps to byte steps. That visits strictly more
    placements, and the gate's own verdict is unchanged.
  - S3K's left-class `$14` cutoff NOT reproduced, matching `Air_CeilingBump` for every air state.
- **Merged-tree `landing_build.sh`:** `finished=0`. s4 is `e8ae697a` and s4.debug is `f7dea36d`, both equal to the
  branch build. The demo pair is unchanged. Test totals: 2606 passed / 0 failed x4, and needs_build 14/0/0.
- **The controller ran `tools/glide_ceiling_witness.py` on the merged-tree ROM: PASS, exit 0.**
- The CHAR-4 `fixed` ledger row is appended. `research/char46-repro` and `parcel/char4-glide-ceiling` are deleted,
  with both tips on origin, and sigil has been told (the new `pub` name and the +$24 player shift).

**So "Next, in order" item 0 is now A only, and item 1 (dispatch CHAR-6) is UNBLOCKED for the next session.**
The witness's leg B is its target. After the release, only the release frame itself still ends embedded (-7),
because `PHook_EnsureStanding`'s lift runs after `Glide_Collide`; the first GLIDEFALL update then ejects it. The
witness has no runner (booked), so run it by hand:
`python3 tools/glide_ceiling_witness.py --rom <tree>/s4.debug.bin --lst <tree>/s4.debug.lst`.


## Addendum, 2026-09-13 ~18:40Z: A (REGIONS parcel 1) LANDED — nothing is in flight, and this session is clearable

Merge `a094ddbc`, land commit `aab6ca59`, on `origin/master` (verified with `ls-remote` and `merge-base`), on top of CHAR-4.
- **Merged tree:** `landing_build.sh` `finished=0`, 2613 passed / 0 failed x4, needs_build 14/0/0. ROMs: s4 `78d31f53`,
  s4.debug `0e5c05ee`, demo `e3e7190e`, demo.debug `6bd0ecd3`. `EndOfRom` equals the branch: s4 `$BDA02`, s4.debug
  `$C123A`, demo `$1121A`.
- **Checks on the merged ROM:**
  - effects-gate ritual 16/16 PASS, exit 0 (T1 and T2 among them);
  - `preset_lab_witness` exit 0;
  - `glide_ceiling_witness` PASS.
  - The T3 witnesses fail on base and final alike. That is pre-existing and booked in DEFERRED_WORK.
- **Sigil:** 6 new suite failures (4 name/layout walls, and 2 RAM repins, `controllers_port` and `hblank_port`
  debug). Their list is at `docs/superpowers/notes/2026-09-13-regions-p1-sigil-suite-classified.txt`. Sigil is
  told. Under the owner's 09-02 ruling these are sigil's after-the-fact repin work, not an aeon gate.
- **Tidied:** the worktrees `.aeon-regions-p1` and `.sigil-regions-p1` are removed and branch `parcel/regions-p1`
  is deleted, with the tip published. The agent's gitignored `.runlogs` went with them; its commit messages and
  the committed list are the record.

**Next, in order, replacing the list above:**
1. **CHAR-6 (the lift), `next` in the queue.** Design inputs are in item 1 above. Its target is the glide
   witness's leg B, where the release frame still ends embedded at -7.
2. **REGIONS-P2, `open`: step 5, one authored rectangle edge that is off the section grid**
   (design §4 step 5). It is the first step that changes a pixel, and T5 needs the controller's screen.
   - It can run in parallel with CHAR-6: they touch different files (player code against level data).
   - The agent's open questions ride with it: whether the sentinel matters on an act reload or on a DEBUG warp
     inside the already-cached region; that the lab's PRESET rows still use section words, which is right only
     while region N = section N; T6/Q3 (booting into a region whose preset differs in `ep_pal`); and T7 (the
     crossing cost with sub-section edges).
3. **To check, not booked:** the demo now carries the regions engine code (it lowers the shared engine modules;
   module granularity means unused code in an imported module ships). This morning's per-game capability work is
   the precedent for gating it. Measure the demo's code and RAM cost before proposing anything.
