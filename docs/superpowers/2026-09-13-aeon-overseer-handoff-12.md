# Aeon overseer handoff, 2026-09-13 twelfth session (booted after the 07:12Z Clear+Reboot)

**Read this, then `docs/lane-status.json` (local disk), then `docs/OVERSEER.md` and `docs/DEFERRED_WORK.md` AT
`origin/master`.** Supersedes "Next, in order" of `docs/superpowers/2026-09-13-aeon-overseer-handoff-11.md`. The
hashes at the bottom were appended by `git log` in the call that committed this file; none is typed.

## ⚠ FIRST, STILL TRUE: READ THE BOOT FILE AT `origin/master`, NOT FROM THE MAIN FOLDER

The owner's main checkout is ~195 commits behind `origin/master` (WORKING-COPY-CATCHUP, his card, unanswered).
This session also read `docs/OVERSEER.md` from that stale disk copy first, exactly as handoff-11 warned, and
caught it only because handoff-11 said so. The published copy carries the 2026-09-12T22:16:45Z standing ruling
the disk copy lacks. `git show origin/master:docs/OVERSEER.md`.

Also: the oracle MCP's private instance boots the MAIN folder's `s4.debug.bin`, which is that stale build. Load a
ROM built from `origin/master` before measuring anything (`emulator_reload_rom` + `emulator_load_symbols`).

## Landed this session

1. **Two owner cards closed by the hub's rulings** under the owner's 2026-09-13 delegation (empyrean `cdb8035`,
   search `goodnigbht`): EFX-832 = leave_it; SECTION-EFFECTS-VISUAL's section 5 keeps the borrowed background until
   regions (sections 1 and 2 were the owner's own 2026-09-12 answer, landed earlier and never closed in the ledger
   until now). Both appended to `docs/decisions.jsonl` per contract 8c/8d with `answered.by = "hub"`, both dropped
   from `blockedOnOwner`.
2. **F3 RUNTIME-TAG closed.** Nothing read the 932 deleted SFX bytes, in the stated scope:
   `docs/superpowers/notes/2026-09-13-f3-runtime-tag.md` (runners beside it), DEFERRED_WORK's F3 row, lane-log.
3. **Oracle booked an instrument gap this session found:** a bus watch never sees any Z80 access
   (`F-Z80-ACCESSES-UNWATCHED`, oracle `ea1dcb8`). Consequence for this lane: **a watchpoint zero on sound-driver
   data means nothing** until they land a fix; they will message when either half lands.

## Next, in order (re-derive before starting)

1. **F3 riders (S, byte-neutral):** `tools/sfx_transcode.py` still writes the 16 `sfx_NN_patches` files nothing
   reads, and keeps `emit_sfx_table_asm` emitting into a `sfx_table.asm` that exists nowhere, graded by
   `TestSfxTableComplete` (a gate outliving its subject). DEFERRED_WORK at origin, search `emit_sfx_table_asm`. The
   hub named this as next.
2. **`GAP12-A2-9d`** — Moving Trucks' FM6 with `SND_FM6_ADAPTIVE = 0`: song flag or gate width, an open call.
3. **`PER-GAME-BAND-DEFINES`** — record-width sizing, not dead code (handoff-11 item 4 says what to read first).
4. **Worktree hygiene** — handoff-11 item 5, unchanged. This session removed only its own two build trees.

Regions stays the owner's call (his "only when it's at a good spot"; "which design doc" unanswered).

## Owner cards open
WORKING-COPY-CATCHUP, CTRL-3, EFX-2, CHAR-10, SP6-MODULATION-DIVERGENCE. Nothing new filed.

## Why it stopped
The owner's ~200k clear rule. **Measured from the transcript usage record: 284,025 tokens at
2026-09-13T07:30:20Z** (input 32 + cache_read 282,238 + cache_creation 1,755). Stopped at a landing boundary with
nothing dispatched; F3 riders not started.

## Hashes, appended by git log in the committing call

- decisions closures (EFX-832, SECTION-EFFECTS-VISUAL): `5d0111ad` decisions: EFX-832 and SECTION-EFFECTS-VISUAL closed by the hub's rulings under the owner's 2026-09-13 delegation
- F3 RUNTIME-TAG closure: `de502e59` close(F3 RUNTIME-TAG): nothing read the 932 deleted SFX bytes, measured on a running game
