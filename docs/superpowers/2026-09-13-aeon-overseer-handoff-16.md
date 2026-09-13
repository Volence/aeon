# Aeon overseer handoff, 2026-09-13 sixteenth session (booted 21:57Z)

**Read this, then `docs/lane-status.json` (local disk), then `docs/OVERSEER.md` and `docs/DEFERRED_WORK.md` at
`origin/master`.** Supersedes "Next, in order" of `docs/superpowers/2026-09-13-aeon-overseer-handoff-15.md`.
Figures below were copied from this session's own tool output, not typed from memory.

## The owner's answers that set this list (2026-09-13T22:06:54Z)

Read them at the artifact, not here:
`git -C ../empyrean show e33a5e3:docs/OVERSEER.md | grep -n -A4 'OWNER, VERBATIM, 2026-09-13T22:06:54Z'`
(reachable from empyrean `origin/main`; the hub relayed it after this session booted).

- **WORKING-COPY-CATCHUP:** catch up. His edits were video experimentation and could be removed. **DONE, below.**
- **EFX-2:** try the colour fade, and it should be region-based. The hub folded it into REGIONS step 5.
- **CTRL-3:** the recommended `gate`, "as long as it doesn't hamper too much". He also wants fewer than four builds:
  a priced proposal of which to drop goes to the hub, which picks unless it is a real tradeoff for him.
- **CHAR-10:** leave.

All four are closed as DECISIONS rule-8c appends in aeon `8300e0af` (pushed; checked with `ls-remote`).
SP6-MODULATION-DIVERGENCE is his only open card. He chose to hear the A/B first (21:53:38Z, same file), so
the next thing it needs from him is his ear, once we have built the A/B.

## The main folder is CAUGHT UP, which ends the stale-copy regime

- The whole state was committed onto the **local, unpushed** branch `backup/owner-wc-2026-09-13` first: 69
  paths, 36 tracked edits and 33 untracked files, through a separate index. Each path was checked
  byte-identical with `git hash-object` before anything moved.
- Then the edits were discarded, the untracked leftovers removed, and the copy fast-forwarded from
  `a38ce7c9` to `be50631a`, 0 behind.
- `.aeon-land-cv/` is a registered worktree nested inside the main folder and was left untouched. Its owner is
  unknown to this session: do not sweep it.
- **The copy drifts again with every landing.** Practice adopted, and told to the hub: after each aeon landing,
  fast-forward the main folder if it is clean, and rebuild it. Every session's emulator shim preloads
  `aeon/s4.debug.bin` from it at session start, and keeps serving that ROM until the lane reloads it.
- **A rebuild of the main folder** (`tools/landing_build.sh`, four shapes and their checks) was started at
  22:22:29Z. It logs to `.runlogs/catchup-landing.log` in the main folder, and its result goes in the addendum
  below. When its `finished=` stamp lands, tell the hub, so lanes that measure through their emulator reload the
  ROM.

## In flight at the time of writing (agents do NOT survive a clear; their commit messages are the record)

**CHAR-6, the glide-release lift.**
- Where: branch `parcel/char6-lift`, worktree `/home/volence/sonic_hacks/.aeon-char6-lift`, based on `be50631a`.
  The branch has no upstream, on purpose.
- The design the brief asked for: S3K-faithful. At the mid-air GLIDEFALL entries, restore the standing box
  about the centre instead of lifting 9 px. The four sites are `PState_Glide.release`,
  `Slide_Terrain.ledge_drop`, `Knuckles_Gliding_WallCatch.fall` and `Climb_LetGo`. **Keep every grounded
  lift.** The note's §6 (iii) grounded divergence (the glide slope landing and `Climb_ReachFloor`) is a
  separate row and must stay untouched.
- The agent may deviate if it can show the change is measurably better (for example, no frame ending
  embedded). A deviation must come back flagged, for you to ratify or reject.
- What it owes:
  - a per-call-site enumeration of `PHook_EnsureStanding`;
  - the next-frame corrections, named from source;
  - the witness's leg B made to ASSERT the CHAR-6 guarantee: red on base with the mutation shown, green on the
    fix;
  - `landing_build.sh`, with a control on the base first, and the demo pair md5-identical to it;
  - the `EndOfRom` deltas and the cycle cost;
  - a names answer. Any `pub`, RAM or struct change is a STOP, so you can arrange the sigil `*_port`
    measurement yourself.
- Its record file: `docs/superpowers/notes/2026-09-13-char6-lift.md`.
- **Landing it:** it is a byte-mover.
  1. Merge in `.aeon-land-0913` and re-verify on the merged tree.
  2. Run `python3 tools/glide_ceiling_witness.py --rom <tree>/s4.debug.bin --lst <tree>/s4.debug.lst` by hand
     (it has no runner).
  3. Append a CHAR-6 ledger row with state `fixed` and `fixedAt` = the merge SHA (append-only, same id).
  4. Write a lane-log entry.
  5. Push, then fast-forward the main folder and rebuild it.
- If the session was cleared before it reported: read the branch's commits, then re-dispatch or finish from
  there.

## Next, in order (the hub's application of his answers, each overturnable by his one word)

1. **REGIONS step 5, with the colour fade.** One authored rectangle edge off the section grid (design §4
   step 5).
   - The new region gets its own colours, and its preset turns the fade on, so crossing the edge fades.
   - This is the fade's FIRST RUN ever, so its correctness is unestablished. The mechanism and sizes are in
     EFX-2's card detail (`docs/decisions.jsonl`).
   - A second palette is content: ship a legible default and park the look for him.
   - T5 needs the controller's screen.
   - handoff-15's open questions ride with it: the sentinel on an act reload or on a DEBUG warp inside the
     cached region; the lab's PRESET rows still using section words; T6/Q3; T7.
2. **SP6: build the A/B he asked to hear** (the timing difference corrected on one side). Listening builds need
   music, and no canonical shape has it: see the memory "No music in canonical shapes" (`--config-a`).
3. **CTRL-3:**
   - make the landing command the only way to merge, within "doesn't hamper too much";
   - send the hub a priced proposal of which of the four builds to drop. The builds are Sonic 4 normal and
     debug, and the demo normal and debug.
4. Everything else in the queue waits on the owner, sigil or sequencing (lane-status `queue` says which).

## Why it will stop

The owner's ~200k clear line: **220,619 tokens measured from this session's transcript usage record at
2026-09-13T22:23:03Z** (input 32 + cache_read 217,105 + cache_creation 3,482). Nothing new is dispatched.
The session stops once CHAR-6 is landed or handed on, with this file updated at that point.
