# Aeon overseer handoff, 2026-09-12 second session (booted 04:20Z after the owner's clear)

**Read this, then `docs/lane-status.json`, then `docs/DEFERRED_WORK.md`.** It supersedes the "READY TO LAND" section of
`docs/superpowers/2026-09-12-aeon-overseer-handoff.md`: everything that section listed is now landed. Every SHA below is on
origin/master unless marked. This session stopped by the owner's clear rule at a landing boundary; its context size is an
ESTIMATE (see "Why it stopped").

## Landed this session (each verified on its merged tree in `.aeon-ls8-land`, then pushed)

| what | merges | land commit | evidence |
|---|---|---|---|
| EFX-4b (fixed, padding) + C3b-2 (refuted, residue accepted) | `97589c56`, `11d35bc9` | `7a938fbe` | landing_build finished=0; effects_gates 17/17 complete, 37 PASS, 0 FAIL, 0 WEDGED; demo ROMs = master, s4 same size + moved; every emitted static program re-measured on the merged ROMs at 128 B, terminator then zeros (8 release, 10 debug; BandDemo/BaseSwap alias OJZ_TestPal in release, 0 B) |
| ew ensure message (zero-byte) + C4a-3 (fixed) | `f64f26b3`, `21a2887a` | `0eaf09a0` | finished=0; all four same size + moved, EndOfRom fixed; expect-fail 55/55 x4, needs_build 14/14 |
| C4a-4 (fixed) | `b4a1e4ba` | `104134ca` | same shape of evidence |
| C4a-2 (fixed) + the stack's side findings booked | `62fb300f` | `ba488cf0` | finished=0; s4 +32, others +34, all appendix (EndOfRom unchanged) |

Each landing used a refuse-unless checker proven able to fail on an unchanged tree first. Scripts and run records:
`/home/volence/sonic_hacks/.aeon-probes/raster-pair-run/` and `.aeon-probes/ew-stack/` (outside any repo; reuse them).

## Rulings taken this session
- **`docs/DEFERRED_WORK.md` conflict at the ew-ensure merge** (`f64f26b3`): both sides struck through a DIFFERENT item of
  the 2026-09-11 lens-tools side findings. Resolved by keeping BOTH: the branch's (a) FIXED and master's (b) CLOSED
  (landing-build-env-stamp). Diffed after resolution: nothing dropped.

## Found this session
- **My own defect, booked in memory (`reference_merge_tree_exit_status.md`):** `git merge-tree --write-tree` prints a tree id
  even on conflict and exits 1; a `| head -1` dry run cannot fail. The first stage-A launch ran a build on a half-merged tree
  because the merge failed and `set -e` did not stop the script; it was killed by process group after ~2 min, and the
  acceptance check (built HEAD pinned to the merge) would have refused it. Every later step checked `$?` explicitly.
- **Aurora's channel-bands report (via the hub, verified here):** `effects_channel_bands.json` `edges.*.engine` still
  publish raster.emp LINE numbers, so aurora's currency row goes red when raster.emp grows. Booked in DEFERRED_WORK and as
  queue row `CHANNEL-BANDS-EDGE-ANCHOR` (S, zero ROM bytes, the `17a6c6d4` pattern). Aurora re-vendors once after the fix.
- **The stack's side findings, booked in DEFERRED_WORK** (block "Side findings of the 2026-09-12 entity-window C4a
  parcel"): `Killed_MarkObject` has NO caller (re-verified here with `git grep -w`), so destroyed badniks may respawn when
  their section slides back in: an emulator look first. Two declared-clobbered registers read after the call
  (`Parallax_CheckBoundary` d2, the ring walkers' a0). A third flat-id product in `tile_cache.emp`.

## ⚠ For the owner: the main checkout is BEHIND master
`/home/volence/sonic_hacks/aeon` is at `a38ce7c9`; `git merge --ff-only origin/master` REFUSES because the owner's
uncommitted edit to `games/sonic4/data/generated/ojz/act1/effects_scenes.emp` collides with EFX-4b's regeneration of it
(the only overlap between the landings and his modified files, computed with `comm`). Not forced, his edits not committed.
Resolution is to REGENERATE the file from his editor sources, never to pick a side; ask him first. Every landing ran in the
clean `.aeon-ls8-land` checkout, so none of them baked his edits in.

## Cross-lane state
- **Sigil:** C4a-2 deleted `Collected_CheckRing` and `Killed_CheckObject`, named in sigil
  `crates/sigil-cli/tests/preserves_corpus.rs`. Per their banked commitment (sigil `c6651e45`, "COMMITMENT TO AEON
  2026-09-12"): do NOT ping them; their nightly source gate goes red naming one of the two procs, and the remedy is
  pre-decided (drop the two rows). EFX-4b will stale their `section:ojz_effects` pins: their drift finding, not a gate.
- **Aurora:** re-vendored the sidecar at our `38c63452` (their `7e8af032`). Nothing owed until CHANNEL-BANDS-EDGE-ANCHOR lands.

## Runtime TAGs outstanding (emulator, controller only)
EFX-4b: `Raster_Buf_A` holds zeros past the terminator after an install. C3b-2: the lag-frame residue, never observed.
C4a-3: profile `EntityWindow_DespawnRings` at a full buffer. C4a-4: section ids unchanged across a slide. C4a-2: same rings
spawn and collected stay collected across a slide and a coarse-row crossing, cycle counts before/after. Plus the previous
session's: C2a-6 (piece count `$FF` + wrong cached offset asserts), B2a-2 (optional), C1b-3 (collision after a vertical
scroll, non-zero origin). And `Killed_MarkObject`: kill a badnik, slide away and back.

## Next, in order (the standing rulings say take it without waiting for a go)
1. `CHANNEL-BANDS-EDGE-ANCHOR` (S, one agent, zero ROM bytes; tell aurora when it lands).
2. LS-2a remainder: 13 `Seq_Op_*` handlers with a call write `hl` undeclared, plus `Seq_Op_RegWrite`'s `e` (zero-byte
   expected, not measured); sigil's z80 gate at landing (method in the previous handoff).
3. Follow-ups: build.sh ignores an exported `NO_LINT=1`; `Draw_Sprite` long branches; `map.toml` placement claim to
   re-derive; `ojz_strip_gen` naming; `ensure(TILE_CACHE_ROWS % 2 == 0)`.
4. The emulator rows above, batched in one controller session.
5. LS-1a: our sigil pin moves first, WITH NOTICE to every lane.

## Housekeeping
- The two agent worktrees that held the landed branches can now be swept: `aeon/.claude/worktrees/agent-a19193e2c65cf1a5d`
  (raster pair) and `agent-a65c5b5c29ba77363` (entity-window stack). Check each for uncommitted or gitignored-unique files
  first, per the shared-machine cautions.
- The previous session's locked probe worktree `agent-a79ab935058db83d7` and its branches (see the previous handoff).
- `.aeon-ls8-land` is left detached at the last pushed tip; `git checkout --detach origin/master` before reuse.

## Why it stopped
Owner rule (2026-09-11T23:19:31Z / 23:20:23Z): near ~200k, reach a landing boundary without dispatching the next wave,
commit a handoff, `atBoundary: true`, `inFlight: []`, tell the hub. This session's context is an ESTIMATE of roughly
170-190k (boot reads: the protocol ~31k tokens, OVERSEER.md, the previous handoff; plus four landings of tool output); the
harness gives no reading. The next items are agent dispatches whose review would cross the line, so it stopped here.
