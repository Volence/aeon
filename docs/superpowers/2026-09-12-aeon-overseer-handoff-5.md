# Aeon overseer handoff, 2026-09-12 fifth session (booted 08:47Z after the owner's clear)

**Read this, then `docs/lane-status.json`, then `docs/DEFERRED_WORK.md`.** Supersedes "Next, in order" of
`docs/superpowers/2026-09-12-aeon-overseer-handoff-4.md`. Every SHA below is on aeon origin/master unless marked.
Stopped by the owner's clear rule at a landing boundary with its context MEASURED (see "Why it stopped").

## Landed this session (all pushed, each `ls-remote` verified)

| what | commits | evidence |
|---|---|---|
| **LS-1a step (1) DONE: the shared assembler pair is sigil `6884bfba`** | DEFERRED entry `4b3f7949` | see below |
| Parcel C, LS-2a (b)+(c) census widening (rulings in its merge message) | merge `c37bb5cf` | landing run below |
| Nightly backstop fetches and tests origin/master | merge `b9e86840` | landing run below |
| Land commit (three lane-log entries) | `02378b92` | |
| Card `SECTION-EFFECTS-VISUAL` filed | `131a8d57` | `decisions_append.py --now`; `test_decisions_ledger.py` 5 passed |
| The card's evidence note merged to master | merge `21cc137b` | ledger + citation tests 8 passed |

**The swap, in order.** Sigil committed its -20 B answer at sigil origin/master `dd6e9f1b`
(`docs/superpowers/notes/2026-09-12-deb2-minus-20-bytes.md`): one deb2 record lost when a 68000 label slid onto
`0x8000` beside the Z80 label `SoundTablesZ80_Head`, in the `ec640bcf` tree only. Verified here against our own
listings: both sonic4 listings carry exactly one symbol at `8000`, old and new pair, so nothing collides at aeon
master. Hub ruled condition (2) discharged and gave OPEN to a fresh sigil session; sigil swapped at 08:57:35Z
(copy then rename, links 1; outgoing pair `49ecc532`/`36ef302c` at `/home/volence/sonic_hacks/.sigil-outgoing-49ecc532/`).
Installed md5s measured here: sigil `2e7c25920b95cec2c462ea51b4f078b5`, emitter `d258341604bbf735a8af8438c2b8d642`.
**Decider** at `57528c22` under the installed pair: `landing_build` finished=0, 2459 passed / 0 failed per shape,
needs_build 14/14; four CRCs equal to the preview. **Landing run** on the merged tree `4b3f7949`: finished=0,
2469 passed / 0 failed per shape, needs_build 14 ran / 0 deferred, four ROMs written during the run.

**Master CRCs from here on (assembler `6884bfba`):** s4 `7a552cde`/821155, s4.debug `b93a889f`/847533,
demo `dd589fe7`/97109, demo.debug `c3eda757`/103501. **The chband refuse-unless base
(`.aeon-probes/chband-land/base/`) is STALE** (old assembler); rebuild it before using it as a baseline.

## Found and fixed on the owner's console (lane-status only; not committed history)
A queue audit against `docs/decisions.jsonl`: four rows claimed "blocked by owner" wrongly or without a reason.
- `REGIONS-PLAN`: his build call IS made (`REGIONS-V1-WORTH-IT`, hub-answered `build` 2026-09-09 under his delegation);
  it waits on his 09-11 ORDER (empyrean `68b9a2e`): review fixes, then the section/effects cleanup, then regions.
- `ENGINE-SEAM-AUDIT`: sequencing, behind that order. (It flipped from next to blocked at `73dbf311` with no reason
  recorded in that diff.)
- `FLOOR-FAN`: parked by his word, "revisit another time".
- `SP-6`: really does wait on his ear, via the open card `SP6-MODULATION-DIVERGENCE` (recommend `ab-first`), which
  was not on `blockedOnOwner`; added.
- `SECTION-EFFECTS-VISUAL` had NO card (the hub had flagged it at empyrean `5afcb7b`); now filed, see above.
- **Still a contract gap:** the id-less `blockedOnOwner` entry about his working copy has no card.

## Reviewed rulings (in the merge messages)
- Parcel C: RATIFIED the DISPATCH RE-ENTRY narrowing and the forward edge `e931501d` + `a4181293`.
- Nightly: RATIFIED `--checkout-only` over the brief's `--print-target` (runs the same resolution and checkout).
- Card: controller cut the question to two sentences and unmarked the recommended label; options, costs and
  recommendation are the drafting agent's. Spot-checked firsthand: Sec1 binds `OJZ_TestRaster`, Sec2
  `OJZ_TestGradient`, and 24.7% of a frame is a MEASURED figure in `tools/effects_budget_model.toml`.

## Watch
- **The nightly's first real fetch under the systemd user unit** (no `SSH_AUTH_SOCK` there; origin is SSH). A
  BatchMode `ls-remote` succeeded from a shell. Read `~/.local/state/aeon-nightly/nightly.log` after the next firing:
  a `target:` line naming origin/master is success; `COULD NOT RUN: git fetch` means suspect that environment.
- The card agent found the handoff-4 claim "Scheme C blocked on item 9c" half stale: 9c's schema landed 2026-09-04;
  C's live blocker is d-53's `open_the_door` contract change. And the inventory's "rename is safe" row is wrong
  (DEFERRED `RENAME IS COUPLED`).

## Next, in order
1. **LS-1a steps (2) and (3)**: the shared provenance primitive, then move the 14 `--built-after` consumers onto it.
   Bookings: DEFERRED row `LS-1a` (search `| LS-1a |`) and `LS-1a NEXT STEP, booked 2026-09-11`.
2. The review-fix residue (handoff-4 "Remaining queue"): `Draw_Sprite` long branches (a byte-mover, now free to go
   since the swap is done; check short reach first); re-derive the `map.toml` placement claim;
   `ensure(TILE_CACHE_ROWS % 2 == 0)` (find the reason or drop it); C4a (a) `Killed_MarkObject` has no caller
   (emulator look first) and (d) the third flat-id product in `tile_cache.emp` (byte-mover); the emulator rows batch.
3. The section/effects cleanup once he answers `SECTION-EFFECTS-VISUAL`; then regions.

## Cross-lane state
- Sigil: nothing owed either way. It keeps `.sigil-outgoing-49ecc532` as its call.
- Hub: told at every stop; knows the card is filed and will point him at it.

## Housekeeping (removable, NOT removed; run the cmdline + cwd check by PID before removing any)
- Merged agent worktrees: `aeon/.claude/worktrees/agent-ac62140ca70e0630e` (parcel C), `agent-ab98d021aa621cc8e`
  (nightly), `agent-a4571d99a599d3b89` (card), plus handoff-4's four (`agent-ad481838a8baa9f77`,
  `agent-a089b2f199f919a29`, `agent-a19193e2c65cf1a5d`, `agent-a65c5b5c29ba77363`).
- `.aeon-ls1a-preview`: the decider is done; removable.
- Merged branches: `parcel/ls2a-census-widen`, `parcel/nightly-origin-master`, `notes/section-effects-visual-card`,
  `parcel/tools-followups-0912`, `parcel/clobber-decls-0912`.
- KEEP: `.aeon-ls8-land` (detached at the tip, clean), `.sigil-pin-6884bfba` (the installed binary reads it),
  `.sigil-pin-af35fa56` while sigil keeps the outgoing pair.
- The main checkout is still at `a38ce7c9` with his uncommitted edits (section 0 background layers moved, world Y
  112/160 to 303/318); regenerate from his editor sources, never pick a side; asked, no answer.

## Why it stopped
Owner rule (2026-09-11T23:19:31Z / 23:20:23Z). MEASURED from this session's transcript usage records
(input + cache_read + cache_creation): 340,205 at 2026-09-12T09:34:09Z, 223 records. The next step (LS-1a steps 2-3)
is a new wave, so it stops at this boundary with nothing running and everything pushed.
