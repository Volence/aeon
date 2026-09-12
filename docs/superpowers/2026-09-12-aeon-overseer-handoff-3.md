# Aeon overseer handoff, 2026-09-12 third session (booted 05:26Z after the owner's clear)

**Read this, then `docs/lane-status.json`, then `docs/DEFERRED_WORK.md`.** Supersedes the "Next, in order" of
`docs/superpowers/2026-09-12-aeon-overseer-handoff-2.md`: its items 1 and 2 are now landed. Every SHA below is on
origin/master unless marked. This session stopped by the owner's clear rule at a landing boundary, with its context
MEASURED (see "Why it stopped").

## Landed this session (each verified on its merged tree in `.aeon-ls8-land`, then pushed)

| what | merge | land commit | evidence |
|---|---|---|---|
| CHANNEL-BANDS-EDGE-ANCHOR: the sidecar's `edges.*.engine` publish `raster.emp#Raster_BuildSchedule`, not line numbers | `4bb8d5d0` | `4aa9a114` | landing_build finished=0; four ROMs byte-identical to master's by a refuse-unless check first shown refusing a one-byte flip and accepting an untouched copy; 4 x 2449 passed, needs_build 14/14 |
| DEFERRED: the split sound-emitter pair (sigil's SHARED-PAIR-SPLIT-EMITTER) + our build.sh banner follow-up | (docs) | `808141f7` | docs only |
| LS-2a remainder: 13 call-containing `Seq_Op_*` handlers declare what they and their callees write; the Z80 census checks procs with a call | `133b713c` | `b3d89695` | landing_build finished=0; four ROMs byte-identical to master's; sigil `z80_clobbers_incomplete` 5 passed on a `git archive` export of the merged tree, 0 skip lines, pin tree clean |

Scripts and run records, reusable: `/home/volence/sonic_hacks/.aeon-probes/chband-land/` (`check.py` zero-byte
refuse-unless, `push.sh`, `recheck.sh`, `base/` = master's ROMs, valid while no parcel moves bytes) and
`/home/volence/sonic_hacks/.aeon-probes/ls2a-land/` (`run-3/run.sh` adds the sigil z80 gate on a `git archive` export of
the merged tree; `push.sh` refuses unless 5 passed, `reference-tree:` names the export, 0 `skip:` lines, pin tree clean).

## Rulings taken this session (ratified on returned work)
- **CHANNEL-BANDS: option A, one proc anchor shared by both edges**, over a per-edge label. Both edge checks sit in
  `Raster_BuildSchedule` under one `.entry`; the lo clamp has no label, and the agent MEASURED that adding `.clamp_up:`
  moves `s4.bin` (locals reach the deb2 appendix). A ROM-moving label whose only reader is a generated file was rejected.
  The anchor is a location, not an identifier; key + `behaviour` identify the edge, and the instruction markers still
  refuse unless exactly one line matches. Proven: control 40-line insert exit 1 before the fix, exit 0 after; proc rename
  exit 1; broken lo marker REFUSED.
- **LS-2a: `bc` added to `Seq_Op_NoteDur` and `Seq_Op_NoteRaw`** beyond the booking, from their callees
  (`Seq_HookNoteOn`, `Fm_NoteOnFreq`, both `clobbers(af, bc, de, hl)`, checked at source). The census now charges each call
  and `falls_into` edge the callee's DECLARED clobbers, no allow-list; its two exclusion rules (restore-pop of a matching
  push; `sp` in an `@noreturn` proc) were each shown doing work by switching it off. Sigil's `z80_clobbers_incomplete`
  excludes every `Seq_Op_*` by design, so for these handlers the census is the only guard.
- **The emitter swap: emitter only, rebuilt at `af35fa56` in `.sigil-pin-af35fa56`**, `sigil` kept at `49ecc532`
  (sigil's proposal; a same-revision sigil rebuild is a new artifact that buys nothing). Swapped 06:25:12Z in a
  hub-opened window; aeon's re-check under the new pair was byte-identical on all four shapes, so it stays. New emitter
  md5 `36ef302cbf5eeca693ecbf981ce8a53a`. Sigil keeps the old `8d80a578` at `~/sonic_hacks/.sigil-outgoing-8d80a578/`.

## Found this session
- **Sigil's top-level `ensure` hazard (relayed, NOT verified on our `af35fa56`)**: an `ensure` after a file's last
  `section {}` can make sigil measure a call 2 bytes short. Booked in DEFERRED with the rule: such ensures go ABOVE the
  last section. Fixed on a sigil branch, not landed; when our pin moves past it all four shapes move (+2 to +22 B per
  section, EndOfRom unchanged, per sigil). **This lands on LS-1a**: moving our pin will bring that byte movement with it.
- **zsh eats `$T:e`**: `git show $T:engine/...` in this shell expands `$T:e` as a modifier. Use `${T}:path`. It silently
  produced a bogus "0 procs" once this session.
- Six queue rows carry `blockedBy: "owner"` with no card under their own id; cards on the same topics exist under other
  ids (SP6-*, REGIONS-V1-WORTH-IT, d-39, ...). Not resolved: a boundary-audit item for the next session.

## Cross-lane state
- **Aurora:** told to re-vendor `effects_channel_bands.json` once, with a content test (blob `0473935b…` at `4aa9a114`).
  Nothing owed back.
- **Sigil:** the swap is closed. The ensure-hazard fix and their LS-1a-relevant pin work are theirs; they will send a
  one-line shape report when the fix lands. C4a-2's deleted procs in their `preserves_corpus.rs` are still theirs to drop
  (no ping, per their commitment).
- **Hub:** told at every stop; the shared-binary window protocol (09-06) was followed.

## Next, in order (the standing rulings say take it without waiting for a go)
1. **LS-1a** (provenance digest): our sigil pin moves first, WITH NOTICE to every lane, and it will now also carry sigil's
   ensure-hazard fix's byte movement. Ask sigil which revision to pin before planning.
2. Follow-ups: record `md5(SIGIL_EMIT)` in build.sh's banner; build.sh ignores an exported `NO_LINT=1`; `Draw_Sprite`
   long branches; `map.toml` placement claim to re-derive; `ojz_strip_gen` naming; `ensure(TILE_CACHE_ROWS % 2 == 0)`
   (place it ABOVE the file's last section); the `Raster_GetChannelBand` banner's two stale cross-file cites; the
   effects_gen DRIFT message should name a moved anchor as a cause.
3. The emulator rows (handoff-2's list, unchanged), batched in one controller session.
4. LS-2a (b) implicit writers and (c) tail `jp`/`jr`, both booked in the LS-2a row.

## For the owner (unchanged)
The main checkout `/home/volence/sonic_hacks/aeon` is BEHIND master (at `a38ce7c9`); `merge --ff-only` refuses only
because of his uncommitted edit to `games/sonic4/data/generated/ojz/act1/effects_scenes.emp`. Resolution: regenerate from
his editor sources, never pick a side; ask him first. Four cards remain on his console (VRAM-FOR-OBJECTS, CTRL-3, EFX-2,
CHAR-10).

## Housekeeping
- Both parcel worktrees of this session are removed with their branches.
- `.aeon-ls8-land` is left detached at the last pushed tip; `git checkout --detach origin/master` before reuse.
- Previous handoffs' housekeeping (agent worktrees, the locked probe worktree) is unchanged.

## Why it stopped
Owner rule (2026-09-11T23:19:31Z / 23:20:23Z): near ~200k, reach a landing boundary without dispatching the next wave.
MEASURED this time, per the hub's 09-09 pointer: this session's transcript usage records (input + cache_read +
cache_creation) read 56,307 at 05:25:58Z and 331,225 at 07:16:51Z, 212 records, no drop (no compaction). The next item
(LS-1a) is a cross-lane pin move whose planning and review would run far past the line, so it stops here.
