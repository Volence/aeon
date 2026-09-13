# Aeon overseer handoff, 2026-09-13 eleventh session (booted 2026-09-13T05:30:20Z after the suite relaunch)

**Read this, then `docs/lane-status.json` (local disk), then `docs/DEFERRED_WORK.md` AT `origin/master`.**
Supersedes "Next, in order" of `docs/superpowers/2026-09-12-aeon-overseer-handoff-10.md`. Every SHA below was
emitted by `git` when this file was committed, not typed. Stopped by the owner's clear rule; see "Why it stopped".

## ⚠ FIRST: YOUR BOOT READ OF `docs/OVERSEER.md` IS PROBABLY STALE — THIS SESSION'S WAS

The owner's main checkout (`/home/volence/sonic_hacks/aeon`) is **189 commits behind `origin/master`**
(WORKING-COPY-CATCHUP, his card, unanswered). The `/overseer` skill says "read `docs/OVERSEER.md`", and reading
it through that working tree served a copy **missing 60 lines of standing ruling** (the owner's
2026-09-12T22:16:45Z "last cleanup before regions / video-memory recut inside regions" section). This session
read the shared protocol correctly at a committed revision and **its own repo's boot file from stale disk**, and
also read handoff-(unnumbered) instead of handoff-10. **Read all three at `origin/master`:**

```sh
git -C /home/volence/sonic_hacks/aeon fetch -q origin
git -C /home/volence/sonic_hacks/aeon rev-list --left-right --count HEAD...origin/master
git -C /home/volence/sonic_hacks/aeon show origin/master:docs/OVERSEER.md
git -C /home/volence/sonic_hacks/aeon log -3 --format='%h %ci %s' origin/master -- 'docs/superpowers/*handoff*'
```

`docs/lane-status.json` is the exception: local disk IS authoritative for it (LANE_STATUS rule 5).

## Landed this session

| what | merge / land | evidence |
|---|---|---|
| **CARRY-CONVENTION** — the five `carry:` labels that read backwards now name what carry SET means (`found`→`unknown` ×3 VolEnv resolvers, `found`→`none` `Sfx_MusicChanPtr`, `ok`→`invalid` `Snd_DacLookup`) | merge `6325f431`, land `acfb4a44` | `landing_build` finished=0, four shapes 2585 passed / 0 failed each, needs_build 14 ran / 0 deferred; ROM CRC32s s4 `1b350bab` / s4.debug `e36d98ba` / demo `3170d31e` / demo.debug `3cf4f104` = the branch's parent baseline (zero bytes), freshly built; sigil `z80_clobbers_incomplete` 5 passed against a git-archive export of the merge, 0 `skip:`, shared sigil md5 unchanged. Reviewed: each rename checked against its body. |

**Found at landing:** `9f7051a3` (session 10's successor) closed lens row `GAP12-A2-U1` about 20 minutes BEFORE
the code reached master. Corrected in DEFERRED_WORK beside the branch's own "still open" sentence. Branch and both
carry worktrees reaped after a controlled `/proc` scan (a planted process was caught; no foreign holder).

## IN FLIGHT at the moment of writing — verify, do not assume

**`BLOCKER2-REWRITE`, branch `parcel/blocker2-rewrite`, one background agent** (dispatched ~05:36Z from this
session; it will NOT survive a clear, but its commits live in the shared `.git`). Comment-only rewrite of
`engine/sound/sound_fm.emp`'s "NOT CHECKED — data->next-address" block, item 2 (OP COVERAGE): three ops released
(`pop af`, `bit n,r`, `add a,n`), two refused by name (`call`/`rst` `[cycles.opaque-call]`, `ret`
`[cycles.path-end]`; `ret cc`/`call cc` also `[cycles.ambiguous-branch]`). Brief required: verify at sigil's
committed source AND with the running binary (throwaway probe branch, never on the parcel branch), echo sweep,
DEFERRED_WORK closure, zero bytes proven on four shapes against its own parent.

**If this session was cleared before landing it:** `git log origin/master..parcel/blocker2-rewrite` shows its
commits and the findings are in the commit bodies. Land from `.aeon-ls8-land` exactly as CARRY-CONVENTION was:
`git checkout --detach origin/master`, merge, assert the new comment text is present, `tools/landing_build.sh`
detached with a `finished=` stamp (SIGIL_BUILD/SIGIL_EMIT exported), **and the sigil Z80 gate** (`sound_fm.emp` is
one of its seven inputs): from `.sigil-pin-af35fa56` (clean), `CARGO_TARGET_DIR=/home/volence/sonic_hacks/.aeon-landing-sigil-target
SIGIL_STRICT_GATE=1 AEON_DIR=<git archive export of the merge> cargo test --release --locked -p sigil-cli --test
z80_clobbers_incomplete -- --nocapture`, require `5 passed`, a `reference-tree:` line naming the export, 0 `skip:`.
**Expected ROMs: identical to master's current four** (the CRC32s in the table above; the land commit after them is
docs-only). **Expect a DEFERRED_WORK conflict** on the blocker-2 clause: the land commit appended a "DISPATCHED
2026-09-13" note to the same sentence the agent closes. Compose, do not pick: the agent's CLOSED text supersedes
the DISPATCHED note. If the agent's comment or probe contradicts the brief, the source and the running binary win.

## Next, in order (after BLOCKER2 lands) — re-derive before starting, never from this list alone

1. **F3 RUNTIME-TAG (controller, emulator, foreground).** handoff-10 item 4: boot `s4.debug.bin`, fire the 16 SFX
   ids listed in the F3 row; a green build cannot observe reachability of the 932 deleted bytes. SFX need no
   off-canonical shape. Oracle: one instance only (`pgrep -x oracle_gui`), verify `romBytes` against the file on disk.
2. **F3 riders (S, byte-neutral):** `sfx_transcode.py` still writes 16 `sfx_NN_patches` files nothing reads and
   keeps an `emit_sfx_table_asm` path into a file that exists nowhere, graded by `TestSfxTableComplete` — a gate
   that outlived its subject (DEFERRED_WORK at origin, search `emit_sfx_table_asm`).
3. **`GAP12-A2-9d`** — Moving Trucks' FM6 with `SND_FM6_ADAPTIVE = 0`: song flag or gate width, an open call.
4. **`PER-GAME-BAND-DEFINES` — the scope is NOT dead code.** It is record-width sizing: the row-remap feature
   widens a record for both games, including the demo game, which can never remap. Fix is per-game `-D` defines
   (sigil shipped them 2026-08-22, zero adoption). Byte-mover (demo shrinks). Read
   `docs/superpowers/notes/2026-09-10-scanline-caps-derivation.md` and `lane-log.jsonl` 2026-09-10T08:55:11Z first.
5. **Worktree hygiene:** 158 of 180 agent worktrees under `aeon/.claude/worktrees/` hold a branch
   already on `origin/master`. Reap only after the controlled `/proc` scan (glob `/proc/[0-9]*`, exclude processes
   descending from your own shell, plant a positive control first; compare COUNTS, zsh does not word-split).
   **DO NOT SWEEP** the sigil-side trees handoff-10 names.

Regions waits only on the owner's go; the owner's order is "the cleanup, then regions — do not grow the cleanup".
VRAM-NEIGHBOURHOOD is an output of regions, not a gate ahead of it.

## Owner cards open (docs/decisions.jsonl; lane-status blockedOnOwner)
WORKING-COPY-CATCHUP (now 189 behind), SECTION-EFFECTS-VISUAL (only section 5's borrowed background is left),
CTRL-3, EFX-2, CHAR-10, SP6-MODULATION-DIVERGENCE, EFX-832. Nothing new filed this session.

## Why it stopped
Owner rule 2026-09-11T23:19:31Z / 23:20:23Z (clear past ~200k at the next landing boundary). **MEASURED from the
transcript usage record: 254,422 tokens at 2026-09-13T05:52:26Z** (input 32 + cache_read 243,384 +
cache_creation 11,006). The blocker-2 agent had been dispatched at roughly 215-230k, before this measurement was
taken; no work was started after it.
