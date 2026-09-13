# Aeon overseer handoff, 2026-09-13 thirteenth session (booted ~08:12Z, stopped at the clear rule)

**Read this, then `docs/lane-status.json` (local disk), then `docs/OVERSEER.md` and `docs/DEFERRED_WORK.md` AT
`origin/master`.** Supersedes "Next, in order" of `docs/superpowers/2026-09-13-aeon-overseer-handoff-12.md`. The
hashes at the bottom were appended by `git log` in the call that committed this file; none is typed.

## ⚠ STILL TRUE: the main folder is the owner's and ~197 commits behind

Read the boot file with `git show origin/master:docs/OVERSEER.md`, never from disk (WORKING-COPY-CATCHUP, his
card). Do all merging, building and committing from a dedicated worktree.

## Landed this session (both byte-neutral, both on `origin/master`)

1. **GAP12-A2-9d, answered as NEITHER** (merge `44d56948`, land `cb4805b5`). Moving Trucks'
   `SND_FM6_ADAPTIVE = 0` is the designed value and `.stop`'s gate is right for every song-internal sample; the
   unguarded class (a song header flag contradicting its channel set) is now refused by
   `song_packer.check_fm6_mode` at pack time and over the committed song `.bin`s. The runtime witness
   `tools/fm6_foreign_sample_witness.py` was run by the controller: 6/6 legs, both controls. The foreign-sample
   POLICY is deliberately not carded; DEFERRED_WORK carries the grep that makes it a card the day a caller
   appears. Superseding `lens-findings.jsonl` row and lane-log entry are in `cb4805b5`.
2. **F3-RIDERS** (merge `04b970b8`, land `21747f03`), paired with sigil's `sfx_port` probe edit (their merge
   `2d45fa39`, verified on their `origin/master` by content before landing). The 16 `sfx_NN_patches.bin`,
   `emit_sfx_patches_asm`, `emit_sfx_table_asm`, `--emit-table` and `TestSfxTableComplete` are gone; `generate`
   refuses unknown flags (a ratified deviation: the old membership test silently accepted `--emit-table`).
   Verified twice on merged trees, `landing_build.sh finished=0`, ROMs md5-identical to master (`s4` d83e2780,
   `s4.debug` 6211829d, `demo` a8a84b6f, `demo.debug` b4443af7), the second time on the tip it was pushed onto.

All builds this session ran under the shared sigil `0.1.0 (6884bfba)`, md5 `2e7c25920b95cec2c462ea51b4f078b5`.

## ⚠ THE SHARED ASSEMBLER IS ABOUT TO CHANGE UNDER YOU

This session gave sigil and the hub the relink clear at the end of the F3 landing, after a `/proc` scan showed
no aeon process on `sigil/target/release/sigil`. The hub opens the window and announces the swap instant and
the new md5 afterwards. **Before quoting any build as evidence, `md5sum $SIGIL_BUILD` and compare it with the
md5 above; if it differs, the binary was refreshed and your control build must be rebuilt under the new one.**

What the new binary adds: sigil's flag-result gate (their merge `eb0b3915`) makes a build REFUSE a call that
drops a declared flag result (`[call.flag-result-unused]`, `[call.result-invalid-path]`). Sigil measured 0
firings at our `dbb67085` in all seven shapes. The remedy for a firing is to consume the result or mark the call
`@discards(name)`. `CONTRACTS=0` bypasses it. **The first aeon parcel built after the refresh is the first to
meet it**; a firing there is a real finding about the parcel's code, not a toolchain fault.

The standing promise, both directions: sigil asks before a relink, and this lane answers when no aeon build
is on the path.

**THE SWAP IS CONDITIONAL, and checking it is your first job** (the hub's condition, relayed to this lane
at ~09:33Z; the hub banks it in empyrean `docs/OVERSEER-LOG.md` and sends the anchor with its swap announce):
the swap stands only if aeon's four-shape build under the NEW pair produces the same ROM bytes as the four
md5s above. If they move, the aside pair goes back in. The hub's figures for the pair, relayed not measured
here: outgoing sigil `2e7c2592` / emit_sound_blob `d2583416`, incoming sigil `73901664` / emit_sound_blob
`1f936ebb`. So once the hub announces the swap: `md5sum` both binaries, run `./tools/landing_build.sh` on a
clean detached `origin/master`, compare the four ROM md5s, and tell the hub the result either way.

## Next, in order (re-derive before starting)

0. **The swap check above**, the moment the hub announces the swap.
1. **`PER-GAME-BAND-DEFINES`** (M, byte-mover): handoff-11 item 4 says what to read first. The byte-mover
   slot is free. Check the sigil md5 first (above).
2. **Worktree hygiene**, handoff-11 item 5, unchanged. This session's own trees are already tidied (below).

Regions stays the owner's call.

## Owner cards open

WORKING-COPY-CATCHUP, CTRL-3, EFX-2, CHAR-10, SP6-MODULATION-DIVERGENCE. Nothing new filed.

## Why it stopped

The owner's ~200k clear rule. **Measured from this session's transcript usage record: 269,598 tokens at
2026-09-13T09:15:36Z** (input 32 + cache_read 268,326 + cache_creation 1,240). Stopped at a landing boundary
with nothing dispatched and nothing held.

## Tidy done at the stop

Removed, each checked first (both branches `--is-ancestor origin/master`; a `/proc` cmdline and cwd scan
found no process in them): worktrees `.aeon-a2-9d`, `.aeon-land-0913b`, `.aeon-f3-riders` (forced: its only
untracked files were the agent's control/after md5 and timestamp files, whose figures are in the lane-log
entry); branches `parcel/f3-riders` (local and on origin) and `parcel/a2-9d-fm6-handback`. Left:
`.aeon-land-0913`, detached at this handoff's commit and clean, removable by anyone.

## Hashes, appended by git log in the committing call
- `44d56948` merge(GAP12-A2-9d): the song packer refuses an FM6 mode flag that contradicts the song's channels, and the row's two suspects are both cleared
- `cb4805b5` land(GAP12-A2-9d): verified on the merged tree and published
- `04b970b8` merge(F3-RIDERS): the SFX transcoder stops writing patch-bank side files and the dead sfx_table generator, and the gate that outlived it goes
- `21747f03` land(F3-RIDERS): verified on the merged tree and published
