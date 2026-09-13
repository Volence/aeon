# Aeon overseer handoff, 2026-09-13 fourteenth session (booted ~09:35Z, past the clear line at boot+20min)

**Read this, then `docs/lane-status.json` (local disk), then `docs/OVERSEER.md` and `docs/DEFERRED_WORK.md` AT
`origin/master`.** Supersedes "Next, in order" of `docs/superpowers/2026-09-13-aeon-overseer-handoff-13.md`.
Figures below were copied from this session's own tool output, not typed from memory; the commit carrying this
file is named by `git log` in the call that pushed it.

## ⚠ STILL TRUE: the main folder is the owner's and 212 commits behind (was 197)

Read the boot file with `git show origin/master:docs/OVERSEER.md`, never from disk (WORKING-COPY-CATCHUP, his
card). Do all merging, building and committing from a dedicated worktree. `.aeon-land-0913` is detached at the
tip this file was committed on and is the docs/landing tree; it is clean apart from build outputs.

## Done this session

1. **SWAP-CHECK: the shared sigil swap STANDS.** Sigil swapped at 09:36:09Z (hub record: empyrean `b0b61de`).
   Installed pair: sigil md5 `739016647ad1ab92f4d072e3013b8818`, emit_sound_blob md5
   `1f936ebb805d39eae23844ee66fb458a`, `--version` revision `1532b72f`, unchanged across the run. Control first:
   `.aeon-land-0913`'s old-pair ROMs md5'd `d83e2780` / `6211829d` / `a8a84b6f` / `b4443af7`. Then
   `./tools/landing_build.sh .runlogs/swapcheck.log` at `62fe88f7`: T0 09:38:21Z, `finished=0` at 09:51:32Z, all
   four ROMs rewritten after T0 and byte-identical to the control; 2595 passed / 0 failed in each shape lane, final
   needs_build lane 14 passed; log line 1 `Assembler: sigil 1532b72fca01`; the new flag-result gate fired 0 times.
   Reported to the hub and to sigil. **Every build from now on runs under this pair.**
2. **WORKTREE-HYGIENE: done.** 187 trees under `aeon/.claude/worktrees/`; 159 were HEAD-ancestor of
   `origin/master` AND clean. A `/proc` scan (cwd + argv, own-shell descendants excluded) saw BOTH planted
   controls (a cwd `sleep` and a python whose argv named a candidate path) and nothing else; controls killed by
   PID after an argv+cwd check. Reap re-checked each tree at removal: **159 removed, 0 refused, 156 local branches
   deleted** (3 were detached), no remote branch touched. **28 remain on purpose**: 21 whose tip is NOT on
   `origin/master` (unpublished work, e.g. `parcel/sp6-ab-timing`, `design/fg-left-edge-planea`,
   `parcel/sp6-modulation`) and 9 with local changes (2 trees are in both sets). Do not reap those without
   reading each. Sigil-side trees (`.aeon-sigil-ref`, `.aeon-sigil-gates`, `.sigil-ref-197-mine`) were never in
   scope. (The first scan's argv control was void: `sleep <path>` exits at once. Re-planted, re-scanned.)

## In flight at the time of writing

**PER-GAME-BAND-DEFINES** (M, byte-mover), one background agent. Worktree `/home/volence/sonic_hacks/.aeon-band-defines`,
branch `parcel/per-game-band-defines`, created at `62fe88f7`, **upstream deliberately unset**. The agent does not
push. If this session was cleared before it reported, the agent is gone: read the branch's commits (the brief
required findings in commit messages), then re-dispatch or finish from there.

What the brief established, so the next reader does not re-derive it:
- **The mechanism exists and has zero adoption.** Sigil merges each game's own `map.toml [defines]` rows
  (integers) into the shape's define set: sigil-cli `crates/sigil-cli/src/main.rs`, `shape_defines_or_exit` ->
  `sigil_harness::native::shape_defines`, read at sigil `origin/master`. A game row shadowing a built-in is
  refused. Neither `games/sonic4/map.toml` nor `games/demo/map.toml` has a `[defines]` table. **So this parcel is
  aeon-only**, unless a harvest context turns out not to see game-side rows (then it is a named sigil ask).
- Scope: the four `BAND_*_N` literals in `engine/level/parallax.emp` and the `engine/ram.emp` `*_BYTES`
  mirrors, per game; the capability stays the authority, guarded both directions in both games; the
  `const SCANLINE_CAPS = <literal>` declarations stay literal (tool readers regex them). Not in scope: the cap-mask
  derivation (refuted, `docs/superpowers/notes/2026-09-10-scanline-caps-derivation.md`), the `band_entry`
  STRUCT_OFFSET_TWINS retirement.
- It also closes DEFERRED_WORK "Obligation 1" (the three T8 contexts with a game-side define).
- **Unverified premises the agent was told to test**: that demo pays anything today; that sonic4 stays
  byte-identical.

**Landing it:** review against the brief's report shape, then the landing lane in `docs/OVERSEER-REFERENCE.md`.
The effects-gate ritual applies only if it touched `engine/effects/*`, `bg_anim.emp` or `buffers.emp`; the Z80
clobbers gate only if a sound input moved. Byte-mover: md5 the four ROMs, explain demo's delta byte for byte.

## Next, in order (re-derive before starting)

0. The band parcel above: review, land, lane-log entry (fold this session's swap check and reap into its
   `detail` or a second entry; neither was a landing so neither has one yet).
1. **CHAR-4 + CHAR-6** (Knuckles glide head clearance; ledger rows in `docs/lens-findings.jsonl`). The
   controller's own emulator rows: REPRODUCE first. The 09-12 handoff said "the oracle driver cannot press C".
   **This session loaded `mcp__oracle__emulator_press`'s schema and it now lists `c`.** That is a schema, not a
   press: verify by pressing it before relying on it. There is no character select (`games/sonic4/player/characters.emp`
   indexes by id; `CHAR_KNUCKLES = 2`), so getting Knuckles into a level is part of the repro. Two byte-movers:
   never one branch. CHAR-6's fix must not touch the grounded path.
2. Everything else in the queue waits on the owner, sigil, or sequencing (lane-status `queue` says which).

Regions stays the owner's call; VRAM-NEIGHBOURHOOD is an output of regions.

## Owner cards open

WORKING-COPY-CATCHUP (212 behind), CTRL-3, EFX-2, CHAR-10, SP6-MODULATION-DIVERGENCE. Nothing new filed.

## Why it will stop

The owner's ~200k clear rule: **233,811 tokens measured from this session's transcript usage record at
2026-09-13T09:57:35Z** (input 32 + cache_read 231,962 + cache_creation 1,817), most of it the boot reads. Nothing
new is dispatched; the session stops once the band agent's work is landed or handed on.
