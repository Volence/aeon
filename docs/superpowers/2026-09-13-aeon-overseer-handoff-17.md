# Aeon overseer handoff, 2026-09-13 seventeenth session (booted 22:49Z, after a clear)

**Read this, then `docs/lane-status.json` (local disk), then `docs/OVERSEER.md` and `docs/DEFERRED_WORK.md`
at `origin/master`.** Supersedes "Next, in order" of `docs/superpowers/2026-09-13-aeon-overseer-handoff-16.md`.
Written at 2026-09-13T23:18:51Z from the clock; every figure is copied from this session's tool output.

## Landed this session

- **CHAR-6** (Knuckles' glide-release lift): merge `92b28703`, land `1b414115`, pushed. Merged-tree
  `landing_build` finished=0, 2613 passed / 0 failed x4, needs_build 14/0/0. s4 `0de120e3`, s4.debug
  `45ddcada`, demo pair unchanged. EndOfRom unchanged x4. Glide witness on the merged ROM: PASS, exit 0.
  Branch and worktree `.aeon-char6-lift` removed after an ancestor check and a PID enumeration.
- **Bookings** (`6a6b0baa`): what CHAR-6 left open (the spring ability-box lift, kept and ratified; the
  CHAR-5 interaction; the stale STATE_BOX row), and the test walk that counted a nested checkout.
- **Correction** (`d71af34c`): the SP6 timing A/B he chose to hear on 21:53:38Z was BUILT ON 09-09 and
  never written down. It is at `/home/volence/sonic_hacks/spring-timing-ab/` (before `e62c43ee`, after
  `d9112c35`, README for the ear). Checked: the after ROM equals its tip's build. It needs his ear, not a
  build. The hub is told.
- **Main folder** fast-forwarded and rebuilt: `landing_build` finished=0 at 23:12:14Z, ROMs identical to the
  landing tree's. Its 22:22Z rebuild (finished=1) was the nested-worktree test walk, not a game defect.

## In flight (agents do NOT survive a clear; their commit messages and record files are the record)

| item | branch / worktree | base | owes |
|---|---|---|---|
| REGIONS-P2 (design §4 step 5, with EFX-2's fade) | `parcel/regions-p2`, `/home/volence/sonic_hacks/.aeon-regions-p2` | `1b414115` | one off-grid edge, a new preset with its own palette and `transition` on, a headless fade witness, answers to Q3/T6, the sentinel, the lab rows, T7; note `docs/superpowers/notes/2026-09-13-regions-p2.md` |
| CTRL-3 (his `gate` answer + "drop some builds") | `parcel/ctrl3-land-gate`, `/home/volence/sonic_hacks/.aeon-ctrl3` | `6a6b0baa` | a pre-push/land gate with a docs-only classifier (NOT installed by the agent: the controller installs at landing), and `docs/superpowers/notes/2026-09-13-ctrl3-shapes-proposal.md`, which goes to the HUB |
| TEST-WALK | `parcel/test-walk`, `/home/volence/sonic_hacks/.aeon-test-walk` | `d71af34c` | every checkout-walking site classified; the fooled ones fixed; ROMs md5-identical to control |

If the session was cleared before they reported: read each branch's commits, then land, re-dispatch or
finish from there.

## Landing each one

- **REGIONS-P2** is a byte-mover. Merge in `.aeon-land-0913` (or a fresh landing tree), assert the content
  is present, run `landing_build`, then:
  - **`effects_gates.py`** on the merged tree: the preset install takes a new path;
  - **the agent's fade witness** by hand;
  - **T5 on screen**, which is the controller's job: launch ONE Oracle (`pgrep -x oracle_gui` was 0 at
    23:00Z), cross the edge at speed, and watch the palette change at the edge and not at the section line;
  - **park the palette's look for him**, and answer EFX-2's two questions from the measured fade.
- **CTRL-3** moves no ROM bytes. Land it, then install the hook with the agent's command, and send the
  shapes proposal to the hub (the hub picks unless it is a real tradeoff for him). Ledger rows CTRL-3/V-8
  follow the agent's report.
- **TEST-WALK** moves no ROM bytes. Land it after `landing_build`.
- After every aeon landing, fast-forward the main folder if it is clean and rebuild it.

## Next, after these

Nothing startable is left in the queue. Everything else waits on the owner, sigil or sequencing:
`lane-status.json`'s `queue` says which. Candidates to propose: handoff-15's "to check, not booked" item
(the demo now carries the regions engine code; measure its code and RAM cost before proposing anything),
and the glide witness's missing runner (DEFERRED_WORK, "CHAR-4 LEFT TWO THINGS OPEN", item 1).
