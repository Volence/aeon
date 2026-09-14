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

## Addendum, 2026-09-14T00:12:07Z (from the clock)

- **TEST-WALK LANDED**: merge `684658c7`, land `24a92168`, pushed. Four walks fixed (not one), ROMs
  md5-identical to master, 2634 passed x4. Branch and worktree removed. It is no longer in flight.
- **REGIONS-P2 RETURNED** (`parcel/regions-p2` tip `a3757a59`, worktree `.aeon-regions-p2`, NOT merged).
  The night region is row 9, x 3400..4799, with `OJZ_Palette_Night`/`OJZ_Preset_Night`. **T5 DONE on screen
  by the controller**, evidence committed at `docs/captures/2026-09-13-regions-p2-night/`: the normal crossing is
  correct, and the reversal defect reproduces (turning back within 16 frames settles NIGHT inside the forest
  region).
- **FADE FIX IN FLIGHT**: `parcel/fade-fix`, worktree `/home/volence/sonic_hacks/.aeon-fade-fix`, STACKED on
  `a3757a59`. It owes (A) the reversal fix plus `--strict-reversal` made a default witness leg, (B1) end the
  fade on arrival, (B2) the ~35k-cycle re-derive per step (a fix or a priced STOP), (B3) the lag frame
  attributed, and (C) the parity comments.
- **LANDING ORDER, ruled here:** master must never carry a reachable fade bug, so REGIONS-P2 does NOT publish
  alone. Merge REGIONS-P2 and verify it (`landing_build`, `effects_gates`, the fade witness), then merge the fix
  and verify it separately (two byte-movers, each attributed), and push only once BOTH are green. Then:
  - tell sigil the data moved (`OJZ_Act1_Regions` grew to 10 rows; data after `OJZ_Preset_Sec7` moved by
    $8E): their after-the-fact repin, under the 09-02 ruling;
  - file the owner's look card for the night palette, pointing at the captures;
  - answer EFX-2's two questions from the measured fade.
- **CTRL-3** is still in flight, as listed above.

## Addendum, 2026-09-14T00:46:26Z (from the clock)

- **CTRL-3 LANDED AND THE GATE IS LIVE**: merge `383fb350`, hook installed in `.git/hooks/pre-push`. Every aeon
  master push now needs a `landing_build.sh` stamp for its code (landing_build writes it on `finished=0` over a
  clean, unmoved tree), and docs-only pushes run only the tests that read them. **A stray untracked file at a
  landing tree's root blocks the stamp**: keep landing trees clean. Bypass: `AEON_LAND_GATE=skip` (prints a banner).
- **Shapes proposal** is with the hub: A plus D recommended. Their pick comes back as a small parcel.
- **OWED at the REGIONS-P2 push: a notice to the lane named `aurora`** (their section-binding reader; asked 2026-09-14,
  and my answer is banked at aurora `98989d4b` `docs/reviews/2026-09-14-aeon-answer-sections-0-7.md`). Also owed at
  that push: sigil told that `OJZ_Act1_Regions` grew and data moved `$8E`.

## Addendum, 2026-09-14T00:49:18Z (from the clock): CONTEXT IS PAST THE LINE; STOPPING AFTER WHAT IS IN FLIGHT

- **Measured 447,399 tokens** at 2026-09-14T00:48:28Z (this session's transcript usage record: input 32 +
  cache_read 441,193 + cache_creation 6,174), more than twice the owner's 200k line. **Nothing new is dispatched.**
  The two agents in flight are landed as they return, and then the session stops clearable.
- **In flight (agents do NOT survive a clear; their branch commits are the record):**
  - **FADE FIX:** `parcel/fade-fix`, `/home/volence/sonic_hacks/.aeon-fade-fix`, stacked on REGIONS-P2 `a3757a59`.
    Owes (A) the reversal fix, (B1) ending the fade on arrival, (B2) the re-derive cost or a priced STOP, (B3) the
    lag frame attributed, (C) the comments. Landing order as in the addendum above.
  - **CTRL-3b** (the hub's pick A plus D, empyrean `cf430f7`): `parcel/ctrl3b-trim-check`,
    `/home/volence/sonic_hacks/.aeon-ctrl3b`, base `d4d7977d`. The pre-merge check drops demo-normal and runs
    the shape-independent pytest and expect-fail lanes once. Owes a caller-proven knob that `build.sh` refuses
    outside `landing_build.sh`, an exemption for exactly the unbuilt shape's needs_build rows (derived from one
    shape list, so B is a one-line swap), and a control-vs-tip run. It moves no ROM bytes. B stays the owner's.
- **If cleared before they report:** read each branch's commits and land or re-dispatch from there. REGIONS-P2
  (`a3757a59`) must not publish without the fade fix.
- **The land gate is live**: every master push needs a `landing_build.sh` stamp for its code, and a stray
  untracked file at a landing tree's root blocks the stamp.
