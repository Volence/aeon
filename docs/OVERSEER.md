# Aeon Overseer

**Boot prompt** (paste into a fresh session started in this repo):

> You're the overseer for this repo. Read `docs/OVERSEER.md` first, then
> `../empyrean/docs/OVERSEER-PROTOCOL.md`. Work the queue. Peers may or may not be
> running — check `ListAgents`; coordinate if present, proceed solo if not.

The role, delegation discipline, review bars, and peer protocol live in the shared
protocol doc. This file is what's aeon-specific.
<!-- SPLIT-NOTE -->
**Dated precedent narratives have moved to `docs/OVERSEER-LOG.md`** (append-only, newest
last, read by `tail`/`grep`, not at boot). Rules, rulings, bars, the landing lane and the
quirks stay here. Each log entry carries an anchor `<!-- @L<first>-<last> -->` naming the
line span it occupied in this file before the 2026-09-02 split, and entries are in this
file's own order.
<!-- /SPLIT-NOTE -->

## The queue

> ### RESUME BRIEF FOR THE NEXT AEON SESSION (first written 2026-08-30T00:38Z; **partly superseded, revised 2026-08-30T09:07Z** — read the strikes, they are the point)
> **DO NOT BOOT INTO A STOP AND WAIT FOR A PICK.** The owner's go is recorded — empyrean
> `origin/main` `7149b39`, verified reachable here, and his standing instruction in it reads
> *"Do not boot into a stop and wait for a pick: his pick is this paragraph."* The hub pushes
> lanes continuously through the ratified plan and rules in his place where a lane is blocked.
> **This overrides the `/overseer` skill's boot stop, which is exactly the exception that skill
> names.**
>
>
> **START WITH:** whatever `docs/lane-status.json` `resume` says — it is written from the clock
> and this block is not. **The 09:07Z sentence that stood here is SPENT: the arm is MERGED**
> (`4aa2abc0`, steps 0-4, re-verified on the merged tree), so `parcel/effects-ref-arm` is no
> longer in flight and a reader who executes that line will re-do landed work. As of
> 2026-08-30T10:01Z the live piece is **item 1 STEP 5** on `parcel/preset-sec5-split`. Its
> contract question is **ADJUDICATED**: the sidecar key is **`rasterRef`**, not `effectsRef`
> (empyrean `da91abce`, option B — verified reachable from `origin/main` here, and §3.1 read
> firsthand rather than relayed).
>
> **AND ITS SECOND BLOCKER IS RULED — BLOCKED-2, the owner's call, taken in his place by the hub
> under the standing instruction: the band goes on SECTION 5** (the 38-byte split that evicts
> nothing; section 4 was rejected because it evicts the d-15 showcase he asked to see). What the
> band LOOKS like stays his: a legible default ships with a parked capture naming the section,
> and he moves or recolours it in aurora once `assign_section_preset` lands. Carrying commit
> empyrean `e874427decc99c3717892a68a583f5a9bafc6dcc`, `docs/OVERSEER.md`, found with
> `git log -1 -S 'SECTION 5, look parked' -- docs/OVERSEER.md`. **Reachable from `origin/main`,
>
> **The falsifier travels with the ruling**, because the ruling rests on a number: if section 5's
> split is not 38 bytes, or evicts anything when built, the ground under the choice is gone —
> report the true cost and stop rather than proceeding on a different one. The design branch `design/effects-ref-binding` (`2cf29126`, unmerged)
> **predates the ruling and says `effectsRef` throughout** — that is a stale planning document
> too, and the same bar applies to it. Then items 3 and 5 — but note **item 5 is NOT unblocked by
> item 1's ruling**: option C, the one that would have carried item 5's keys, was refused
> precisely because it would have inverted the ratified order. Item 5 needs its own, unwritten CR.
>
> **THE PLAN:** `docs/DEFERRED_WORK.md` → *"EFFECTS-W1 — the owner-ratified definition of done,
> priced and sequenced"*. All eleven aeon items priced S/M/L with byte status, the sequence, and
> **item 0** — the spare-nametable prerequisite that items 10 and 11 both need and that is on
> nobody's list. Card `vram-replan` is filed; his answer is not needed until 10/11 are reached.
>
> **⚠ THE PROJECT GREW A SECOND HALF (owner, 2026-08-30).** EFFECTS-W1 is not done until the
> side-effect bugs are fixed too — his words and the enumeration are at empyrean `origin/main`
> (`contract/projects.json` → EFFECTS-W1 `completionRequires`; DoD items 14-17). **The canopy gap
> is no longer backgroundable** (item 17: *"a found cause and a fix, not a backgrounded card"*).
> **Its plan is to INSTRUMENT for the next sighting, not to derive a third explanation** — two
> code-read explanations are already refuted, so derivation is the approach with a demonstrated
> failure rate here. `d-47-revised` is RULED `targeted`; **measure the append-disturbs-nothing risk
> before any art ships — a measurement, not the argument.**
>
> **RE-MEASURE, DO NOT INHERIT:** the sigil binary's staleness (rebuilt at their `85a5726c` as of
> 2026-08-30T00:33Z — but re-derive at the moment you need it, never from this line); and the
> lost `+$60` derivation described under *"AN OPEN MEASUREMENT THREAD WITH SIGIL"* in
> `DEFERRED_WORK.md`, which must be re-derived and never reconstructed from a peer's paraphrase.
>
> **SHELF LIFE — treat every coordinate in this block as expired and every SHAPE as sound.**
> The shapes above (there is a ratified plan; the project grew a second half; re-measure rather
> than inherit) age well. The specific rows, SHAs and next-actions do not, and the two that went
> stale here both went stale because work landed *elsewhere* — one in this repo, one in empyrean.

**`docs/DEFERRED_WORK.md` is the living queue** — check it at the start of every
planning phase; it books everything with provenance. The current arc and any owner
rulings live in the session memory and the most recent `docs/superpowers/*handoff*` /
`*summary*` docs. Do not duplicate queue content here; this file only says where it is.

## Landing lane (aeon owns the aeon↔sigil pair)

- Byte-moving parcels land as aeon+sigil PAIRS through THIS repo's overseer: merge →
  rebuild all four shapes → re-verify on the merged tree → effects-gate ritual (if
  `engine/effects/*`, `engine/level/bg_anim.emp`, or `engine/system/buffers.emp`
  moved) → sigil `refreeze --freeze NAME --ab <prose evidence>` → **commit the freeze** →
  `refreeze --attest` on the committed tree (see the block below — this REPLACES the
  hand-run strict suite, and the tool sets the flag so the rule no longer has to carry a
  token nobody audits) → commit `provenance.toml` → push both. Aggregate totals only, never
  a tail; the fully-green bar moves, so derive it and do not quote this file.
  `refreeze --check` is NOT the goldens.
  ~~The hand-typed baseline test (`repin_pins.rs`) demands a per-parcel term with its story
  when assembled lengths move.~~ **STRUCK 2026-08-30, measured, not assumed.** That test is
  RETIRED: `secondary_pin_classes_match_the_hand_typed_baseline` reports
  `ignored, RETIRED by Wave-B B-0 (packed placement): this test asserts literal pin VALUES`.

  **⚠ THE MANUAL STRICT SUITE IS SUPERSEDED — RUN THE TOOL (2026-08-27).** Where this file
  previously told you to run `SIGIL_STRICT_GATE=1 AEON_DIR=<clean> cargo test --release
  --workspace --no-fail-fast` by hand, **do this instead**, after the freeze is committed:

  ```sh
  AEON_DIR=<clean checkout of the frozen aeon SHA> \
    cargo run --release -p sigil-harness --bin refreeze -- --attest \
      [--expect-test <a-test-this-parcel-added>]
  ```

  Transcribed from sigil's own source header (`crates/sigil-harness/src/bin/refreeze.rs`,
  read at their `origin/master`), not from their message. *Note: the source header spells the
  attest form without `--release`; their landing note spells it with. `--release` is what this
  lane runs everywhere else and is the safer default — if the distinction ever matters, ask
  them rather than guessing.*

  The tool **sets `SIGIL_STRICT_GATE=1` itself**, adds `--nocapture`, runs the same suite, and
  appends `[entry.strict]` to `provenance.toml` on success (commit `provenance.toml` only). A
  red run records `outcome = "failed"`, names the failing tests, and exits 1.
  **`--expect-test <name>` refuses if a test your parcel added did not execute** — use it for
  every parcel that adds one, because it is the only step that closes bar 25 at the level of
  *this* gate rather than *the suite*.
  It REFUSES on: a dirty sigil tree (commit the freeze first), `AEON_DIR` unset/dirty/not the
  tip's `aeon_rev`, zero strict bodies reached, or HEAD moving mid-run.


  **A `ratchet:` line you will see and must NOT misread.** Until this lane's first `--attest`,
  a strict run emits exactly one: *"no entry in this chain records a strict run yet … the rule
  is not yet in force."* The zero-`skip:` bar is unaffected (it prints `ratchet:`, never
  `skip:`). **Do not read it as the old `aeon_rev` pairing ratchet returning** — that one
  disarmed at chain 167 and its reappearance WOULD be a defect. Two self-disarming ratchets
  now exist saying different things: **read the sentence, not the word.** Ours disarms
  permanently at our first attest.

  **If a strict run legitimately goes RED and the fix moves bytes**, that entry can never be
  attested — expected, not a bug. The next freeze passes `--supersede-tip "<why>"` naming its
  successor. **Abandonment also requires a recorded red run**: "must name a successor" alone is
  defeated by serial supersession (freeze, abandon, freeze, abandon, and the suite never runs),
  so you cannot abandon an entry you never tested. That guard is sigil's addition to this
  lane's own scenario.


  **Standing commitment to the sigil lane (`REFREEZE-NEEDS-STRICT`, agreed 2026-08-27, landed
  their `74793994`): every paired refreeze clears the full strict suite before push, whoever
  lands it.** It is one command on top of a landing this lane is already doing, and it is not
  a courtesy — it is the run that should have happened at 169 and 170.
  **Their declared bar moves to 3990 / 0 / 4 (3994 declared).** Derive it at the time rather
  than quoting this line; it has moved twice in two days. *(Recorded because it is the shape
  this file keeps meeting: their agent claimed a delta of 53 new tests; the measured delta was
  40. The tree was self-consistent, the claimed delta was not.)*

- **RUN THE FREEZE DETACHED, NOT AS A HARNESS BACKGROUND TASK — the `[killed], no exit status`
  class is the harness reclaiming its own task, and NOTHING ABOUT THE FREEZE FAILED** (added
  2026-09-02; the sigil lane's mechanism, offered explicitly as a hypothesis, n=2, one data point
  accidental, harness lifecycle rules unread by either lane).
  task, survived and the *watcher* was killed instead. **The variable is whether the work is a
  CHILD of the harness's background task.**
  **Operational form, and the second half is the one that matters:**
  ```sh
  nohup bash the-freeze-script.sh > run.log 2>&1 &
  ```
  and have the script append its own `finished=<exit code>` line at the end. **In a log a vanished
  run and a completed one trail IDENTICALLY**, so the stamp is the only thing that distinguishes
  them — the same corrective as `REAL_EXIT=$?` inside the log, one level out. Do not poll with
  `pgrep -f`, which matches your own watcher; ask whether the artifact changed.
  **⚠ AND DO NOT WATCH THE DETACHED RUN WITH A HARNESS BACKGROUND TASK — THE WATCHER IS EXACTLY
  WHAT GETS RECLAIMED** *(measured here 2026-09-02, and it is a correction to the advice above,
  which was two thirds right)*. Landing chain 197 this lane detached the four-shape build
  correctly and then armed a `run_in_background` `until`-loop to wait for its `finished=` line.
  **The harness killed the WAITER; the detached build survived** — `pgrep -x sigil` found the
  assembler alive and the log still growing. So the watch step reintroduces the exact failure the
  detach was routing around. Poll by hand, or better, ask the question that survives:
  **"did the log get its `finished=` line" is answerable later by anyone; "is the process alive"
  asks about something the harness may reclaim out from under both the asker and the answer.
  Prefer the artifact.** *(Stated this way rather than as "no background waiters" because the
  rule generalises past this harness.)*
  **AND KEEP THE NUMBER, not just the fact of it** *(sigil's sharpening, 2026-09-02, and it is
  what turns this from a hypothesis into a measurement)*: the recorded exit code separates
  *killed by something* from *died on its own*, and **137 vs 143 separates SIGKILL from SIGTERM**,
  i.e. a hard reclaim from a polite one. Without the stamp both outcomes and a completed run
  produce the same truncated artifact, which is the absence family rather than a mystery.
  Report the number either way.
  **⚠ CORRECTED 2026-09-02, AND THE CORRECTION MATTERS MORE THAN THE RULE. This bullet first
  read: "a clean completion REFUTES the harness story rather than merely failing to confirm it."
  THAT IS BACKWARDS.** The hypothesis predicts that a detached run survives, so a clean
  completion **CONFIRMS** it — weakly, at n=1. **A detached DEATH is what would refute it**, which
  is why the death is the more valuable outcome. What a clean run refutes is the *competing*
  story — the freeze is fragile, memory pressure kills it — and that is probably what the
  sentence was reaching for, but it is not what it said.
  **THE HONEST STATE AS OF CHAIN 197: three observations, all consistent, none decisive.** Two
  freezes died as harness background tasks; a waiter died while its detached build lived (run-2
  shape, reproduced by the lane that did not form the hypothesis); a detached freeze ran to
  completion. Consistent with child-lifecycle — and equally consistent with an intermittent death
  that happened not to fire. **The discriminating run is a detached death, and we have not had
  one.** Keep detaching and keep stamping; do not write the mechanism down as settled.

- **NEVER LEAVE A SHARED CHECKOUT ON A PRIVATE BRANCH — a repoint silently invalidates
  every other session's already-correct branch check** (added 2026-08-27; this lane's defect,
  **Two correctives at opposite ends, both live:** the committer verifies the branch **in the
  same command that commits**, never at boot (sigil's, and it is the one that protects you
  against a peer doing this to you); and **this lane does freeze work in a dedicated worktree,
  leaving the shared checkout on `master`** — done, `/home/volence/sonic_hacks/.sigil-pair-172`.
  This repo's own protocol already says worktrees are why a shared main tree never matters;
  committing in the shared tree is the one act that makes it matter again.
  **Two mechanical traps in the fix itself, contributed by the sigil lane who hit both while
  applying it — and they land on THIS lane now that freezes run from a dedicated worktree:**
  (1) `git worktree add <path> master` **fails outright** when the shared checkout is itself on
  `master` (*"'master' is already used by worktree at …"*) — which is the NORMAL state under the
  rule above, so the fix creates the trap. Use `--detach` and push with
  `git push origin HEAD:master`. (2) `git worktree remove` run from **inside** that worktree
  deletes your cwd, and every later command in the chain dies with *"Unable to read current
  working directory"* — which in their case made a chain report a push that had never happened,
  i.e. it fails in the direction of a FALSE SUCCESS. `cd` out first, and never trust a push
  reported by a chain whose cwd may have been removed mid-run.
  *Cross-check: sigil's own write-up of both correctives is at their `1d1e3dc0`.*
- **THIRTY-ONE LEDGER LINES DO NOT PARSE FOR THE OWNER'S READER — DO NOT REPAIR THEM** (measured
  2026-08-30 by running Dominion's own predicate over the file; hub-ruled not to repair).
  **MEASURED: 86 lines · 55 parse · 31 REJECTED**, counted per LINE. Predicate transcribed from
  dominion `796bc1e` `server/src/decisions.ts`. Reasons (collected, so one line carries several):
  **⚠ COUNT BY LINE, NOT BY ID.** My first run keyed results by `id` and reported 28, because
  `d-42-answered`, `d-43-answered` and `instashield-riders` each appear TWICE and a dict silently
  collapsed them. Three lines vanished into a container that deduplicates without saying so — the
  same class as every other miss of that night. Rule 8c makes repeated ids NORMAL, so any tooling
  over this file must be line-addressed.
  **THE RULED-NOT-TO-REPAIR SET, by line:**
  line   3  `d-4` — option missing key; option missing name; recommend must be an object
  line   4  `d-5` — option missing key; option missing name; recommend must be an object
  line  35  `d-19-answered` — options must list two or more
  line  36  `d-20-answered` — options must list two or more
  line  38  `d-21-answered` — options must list two or more
  line  39  `d-22-answered` — options must list two or more
  line  40  `d-24-answered` — options must list two or more
  line  41  `d-25-answered` — options must list two or more
  line  42  `d-26-answered` — options must list two or more
  line  43  `d-27-answered` — options must list two or more
  line  45  `d-18-answered` — options must list two or more
  line  48  `d-32` — option missing key; option missing name; recommend must be an object
  line  49  `d-30-answered` — options must list two or more
  line  59  `d-36-answered` — options must list two or more
  line  60  `d-38-answered` — options must list two or more
  line  63  `d-40-answered` — options must list two or more
  line  64  `d-36-correction` — options must list two or more
  line  68  `d-42-answered` — options must list two or more
  line  69  `d-43-answered` — options must list two or more
  line  72  `d-42-answered` — options must list two or more
  line  73  `d-43-answered` — options must list two or more
  line  74  `d-44-answered` — options must list two or more
  line  75  `d-45-answered` — options must list two or more
  line  76  `d-35-closed` — options must list two or more
  line  77  `d-32-closed` — options must list two or more
  line  81  `vram-replan` — option missing key; option missing name; recommend must be an object
  line  82  `instashield-riders` — option missing key; option missing name; recommend.key names no option
  line  83  `d-47-revised-answered` — options missing; recommend missing
  line  84  `vram-replan-deferred` — options missing; recommend missing
  line  85  `d-46-downgraded` — options missing; recommend missing
  line  86  `instashield-riders` — option missing key; option missing name; recommend.key names no option
  **RULED: no repair appends** (hub, 2026-08-30; rule 8 forbids rewriting, and 8d says explicitly
  that nothing is rewritten). Dominion builds owner-facing cards ONLY from `blockedOnOwner` joined
  by id, so a rejected line no live blocker claims reaches him nowhere; the harm is to future ledger
  readers and the history view. **Rule 8d's `answered` field is the forward fix** — every closure
  from here carries it.
  **⚠ AND A TRAP IN 8c ITSELF, worth more than the list: `instashield-riders` is rejected — INCLUDING
  the conforming closure I appended for it on 2026-08-30.** 8c requires reproducing the settled
  card's question, options and recommend IDENTICALLY. When the settled card does not parse (this one
  has options lacking `key` and `name`), **a faithful 8c closure reproduces the defect and creates a
  second rejected line.** Closing a malformed card correctly makes the file worse by exactly one
  line. Flagged to the hub; do not "fix" it by editing either line.

- **SEVEN LEDGER ENTRIES ARE CLOSED OUT OF SHAPE — DO NOT REPAIR THEM** (added 2026-08-30; hub-ruled
  after this lane's boundary audit surfaced them).
  `docs/decisions.jsonl` closes a decision per `contract/DECISIONS.md` rule 8c: append an entry with
  `supersedes` set to the settled id and the question/options/recommend reproduced identically.
  **These four closures did not do that.** Each was filed as a NEW id with `supersedes: null` and the
  resolution written into the `question` field as a statement: `d-45-answered`, `d-46-downgraded`,
  `d-47-revised-answered`, `vram-replan-deferred` — leaving their originals `d-45`, `d-46`,
  `d-47-revised`, `vram-replan` unsuperseded too. **So each closure leaves TWO open-looking cards
  instead of zero**, seven entries in total.
  **RULED: no repair appends.** Rule 8 forbids rewriting; Dominion builds owner-facing cards ONLY
  from `blockedOnOwner` joined by id (`decisionQueue.ts` at dominion `796bc1e`, read by the hub in
  their own tree), so every entry no live blocker claims goes to `settled` and **these reach him
  nowhere**. The harm is confined to future ledger readers and to the history view. Eight lanes
  repairing eight ways is precisely what 8c exists to prevent, and the first-class `answered` field
  is now the front of the hub's queue and supersedes the whole question.
  **Rule 8c stands unchanged for every closure from here.** The instashield-riders close (`39b400bc`)
  is the conforming example to copy.
- **LEDGER APPENDS GO THROUGH `tools/decisions_append.py`, AND THE BUILD HOLDS THE FILE TO THE
  RULED SET** (2026-08-30T18:14:34Z, LEDGER-WRITE-SITE-CHECK; `parcel/ledger-write-site-check`).
  `decisions_conformance.py` found the 31 above and could not stop the 32nd, because it runs after
  the fact and only when someone remembers to (the `refreeze` argument, DEFERRED_WORK "LEDGER
  CONFORMANCE IS CHECKED OVER THE HISTORY..."). So the check now sits at the write:
  `printf '%s' "$ENTRY" | python3 tools/decisions_append.py --now` (or `FILE.json`; `--check-only`
  validates without writing). It IMPORTS the transcribed reader predicate (never a copy), stamps
  `at` from the clock, and REFUSES with every reason printed if the reader would reject the line,
  if `supersedes` names an id no parseable line carries, if an existing id is reused without
  superseding it, if a closure (an entry carrying `answered`, or `--closure`) does not reproduce
  the settled card's question/options/recommend in 8c's amended substance (additions allowed,
  drops and edits named by first differing field; an out-of-shape settled card requires `detail`
  to say so), or if `answered` is in a shape the reader would silently DROP. Rule 8's recipe is
  built in: heal a missing final newline, one line, re-measure, exit 1 on a post-write mismatch.
  Control: every line appended since the ruled set (87-98) replays through it accepted.
  **The backstop is `tools/test_decisions_ledger.py`**, in build.sh's pytest lane (all four
  shapes, build-fatal), against `tools/fixtures/decisions_ruled_unrepaired.json`, GENERATED by
  `decisions_conformance.py --emit-ruled-fixture` at aeon `525d8eba` (31 lines, 98-line id
  sequence): a NEW rejected line fails by line number; a ruled line rewritten, deleted or
  "repaired" fails by line number and reason; a shorter file or a moved id fails as a rule-8
  violation; a missing fixture FAILS, never skips. Red-first, all four, restored after each.
  Regenerate the fixture ONLY on a hub ruling that changes the ruled set, in the same commit
  that names the ruling; regenerating to turn a red gate green is the repair by another route.
- **A PARCEL THAT MOVES AN IMAGE PIN CANNOT BE VERIFIED BY A CANONICAL BUILD FROM A CLEAN
  STATE — THE GATE READS ON-DISK LISTINGS AND THE BUILD REFUSES BEFORE REGENERATING THEM**
  (added 2026-08-30, hit landing the clamps parcel; the escape is `FAST=1`).
  **THE ESCAPE, and it is the documented one:** `FAST=1 DEBUG=1 ./build.sh` (and the `demo` shape)
  skips the verification lanes, regenerates both listings, and then a canonical build passes.
  `FAST=1` prints its own banner saying it is not a ship artifact, which is exactly right — it is
  being used here to BOOTSTRAP the instrument, not to skip the check. **Re-run canonically
  afterwards; that is the run whose totals you quote.** Measured: 1660 passed / 0 failed on all
  four shapes after the refresh, against `1 failed` before it.

- **A RECOMMENDATION SHOULD CARRY ITS IMPLEMENTATION CONSTRAINTS WHEN THE RECOMMENDER IS THE
  BENEFICIARY** (added 2026-08-30; the sigil lane's self-correction, and this lane is the party it
  protects).
  **The bar: when you recommend a change whose cost lands on someone else, the implementation
  constraints are part of the recommendation, not a follow-up.** Declaring the interest — which they
  did, and which is why the recommendation was trustworthy — covers the *motive* and says nothing
  about the *feasibility*. A beneficiary who has not costed the implementation is asking the payer to
  discover it.
  **This lane's own corrective, since it is the receiving side: measure the cost yourself (done —
  65 KB compressed against 6.7 MB) AND ask what the implementation touches, before ruling.** I did
  the first and not the second; the trap was found by the recommender, not by me.

- **AN UNATTESTED COMMIT'S CROSS-SEAM DEBT IS PAID BY WHOEVER FREEZES NEXT — AND GETS ATTRIBUTED
  TO THEM** (established 2026-08-30 after chain 187's red was blamed on the wrong parcel TWICE, once
  by this lane and once by sigil).
  **Operational form: `freeze_preflight.sh` run at the START of a parcel, not only before its
  freeze, tells you whether you are inheriting a red.** If it is already red before you touch
  anything, the debt is not yours and the diagnosis starts elsewhere. That is one cheap run and it
  partitions the population that this whole episode failed to partition.
  **⚠ AND THE INSTRUMENT THAT PRODUCED BOTH WRONG STORIES: `git show $rev:path` IS BROKEN IN ZSH.**
  `$rev:engine/level/section.emp` parses as the history modifier `${rev:e}` followed by
  `ngine/level/section.emp`, so git fails with *"ambiguous argument"* — and a piped `grep -c` then
  prints **`0`**, which is a plausible count rather than an error. Three separate loops tonight
  returned confident zeros this way, and one of them is what produced this lane's "4 before and 4
  after" reading. **Use `git show "$rev:$path"` with BOTH sides as variables (no modifier applies), or
  `git cat-file -e` first, and never let `grep -c` stand in for a read that may not have happened.**

- **`emulator/screen_text` READS THE DEBUGGER'S CHROME, NOT THE GAME'S PICTURE — and its `F`
  COUNTER MUST NEVER BE JOINED TO A BUS FIELD** (added 2026-08-30; served at oracle build
  `52815f2`, contract Aether §11.29, vectors `cb1201b`).
  **⚠ THE TRAP, and it is exactly the shape this file keeps recording: the status line's `F` is a UI
  COUNTER, NOT THE MACHINE'S FRAME.** It is bumped after every run iteration whether or not a frame
  completed, so a mid-frame breakpoint stop leaves a **permanent +1** and a state load diverges it
  **without bound**. **Joining it to any bus field produces a plausible number that is about
  something else.** Use `emulator/status`'s `frame`. *A value that is real, adjacent, and answering a
  different question — the same family as `pgrep -f` matching its own watcher and `$?` reporting the
  last pipe stage.*
  **Open and named by oracle rather than skipped: it has never run against a real window.** Every
  path is unit-tested and the headless refusal is a genuine end-to-end capture, but the windowed
  case is unobserved — they will not put a window on the owner's desktop while he is logged in. **On
  the windowed path, suspect it before suspecting your own code.**

- **THE EXIT CODE YOU READ IS OFTEN NOT THE ONE YOU WANT — echo the REAL one INSIDE the log**
  (added 2026-08-30; five instances across two lanes in one night, none of them subtle in hindsight
  and all of them silent).
  **Operational form: have the process write its own exit code INTO its own log**, and read that.
  `{ cmd; echo "REAL_EXIT=$?"; } > log 2>&1` — then the number you read is the one the command
  produced, not the one the last stage of your pipeline produced. Sigil's note is the sharp version:
  *the only reason any of the three was caught is that the real exit code was echoed inside the log.*
  **And when the process is backgrounded, an exit code says nothing about the WORK.** The tell that
  saved them was the log's mtime still advancing — which is this file's own *check the artifact, not
  the process* rule doing the work under a different name.

- **`pgrep -f "<cmd>"` MATCHES YOUR OWN WATCHER, so an until-loop waiting on a process can never
  exit — and it reports the process as ALIVE long after you killed it** (added 2026-08-30; cost 35
  minutes of a landing believing a strict attest was still running when it had been dead the whole
  time).
  **Use `pgrep -x <name>`** — it matches the executable name, so a `zsh` running your loop cannot
  match a binary called `refreeze`. Where `-x` will not do (a script run under an interpreter),
  match on something the watcher cannot contain, or check for the ARTIFACT rather than the process:
  *did `provenance.toml` change* is a question about the world, and *is the process alive* is a
  question your own command line can answer wrongly.

- **THE SHA BAR HAS ONLY EVER BEEN WRITTEN FOR THE RECEIVING SIDE, AND THE FAILURE LIVES ON THE
  EMITTING SIDE** (added 2026-08-30; this lane's own defect, caught by the hub within minutes).
  **Operational form: EMIT every SHA from the command that proves it, in the same invocation as the
  thing it anchors.** `git branch --show-current && git rev-parse HEAD && git show --stat HEAD` —
  then quote what came back, never what you remember. Costs one command; the alternative is a
  plausible-looking hash that sends a reader hunting for a clone that does not exist.
  *And the second defect underneath it, which the hub's diagnosis found and mine had missed: the
  commit was also UNPUSHED, so even a correct hash would have failed for them. A mistyped-but-pushed
  SHA fails loudly; a fabricated one on an unpushed commit fails as a mystery. Push before you cite,
  and verify the push with `merge-base --is-ancestor` rather than the push command's own output.*

- **`sigil --version` DIFFERING FROM SIGIL'S `HEAD` IS THIS REPO'S NORMAL STEADY STATE, NOT A
  SIGNAL** (added 2026-08-30; the sigil lane's sharpening of a diagnostic this lane ran correctly).
  **The witness that actually discriminates is a diff scoped to the code:**
  `git -C ../sigil diff --stat <binary-rev>..HEAD -- crates/` — empty means behaviourally current.
- **A PAIRED LANDING CITES TWO AEON SHAs AND THEY ANSWER DIFFERENT QUESTIONS — LABEL WHICH IS
  WHICH, OR THE TREE-STATE PIN GETS READ AS THE CODE ANCHOR** (added 2026-08-27; caught by the
  oracle lane, turning this repo's own SHA-class bar back on it, and they were right about the
  defect while wrong about the substitute — which is why you check rather than swap).
  **Operational form: write a paired landing as `code <SHA> · frozen at aeon_rev <SHA> / sigil
  <SHA>`.** Both SHAs are correct for their own question; the prose is what has to say which
  question each answers. This is not the SHA-class bar repeating — that one is about citing the
  *wrong* SHA. This is about citing the *right* one for an unstated question, which no
  `--stat` check catches, because the commit you land in is genuinely the one named.
- **A REBASE ORPHANS THE SHAs A GENERATED LEDGER HAS ALREADY CAPTURED — AND THE CONSUMER YOU
  MISS IS THE ARTIFACT, NOT THE PEER** (added 2026-08-29, chain 181; **the sigil lane's finding
  against this lane's rebase**, and every particular of it verified firsthand here before being
  written down).
  **THE MAPPING, which is the operative half of this bullet: `bfbedc11` → `16b83c63`, same work,
  rebased.** A verifier who cannot resolve entry 181's `sigil_rev` should meet that sentence
  rather than a mystery.
  **RULED — document the mapping, do NOT re-attest** (this lane's call, reached independently by
  the sigil lane, and ruled by the hub under the owner's overnight grant; banked for his review).
  Re-attesting 181 would record a run that happened on tree `ed5a25ac` under an entry naming a
  commit whose tree is `7ccd5d3f` — **trading a dangling anchor for a resolvable one that points
  at the wrong tree.** That is strictly worse for the only question `sigil_rev` exists to answer
  **THE REUSABLE HALF, and it is bar 8 arriving somewhere nobody points it:** before rebasing,
  this lane enumerated the consumer set correctly for the question it asked — *had this SHA been
  handed to any peer?* — and the answer was genuinely no. **The consumer was not a peer. It was
  the ledger being written in the same operation, which had already captured the value.**
  Enumerate by **what TOUCHES the value**, never by **whom you told**. A generated artifact is
  the worst consumer to miss, because it is the one that cannot be sent a correction message and
  the one that hardens into the permanent record.
  **Operational rule taken from it: before rebasing anything whose SHAs a freeze or attest has
  already recorded, either do not rebase or record the mapping in the same commit.** The window
  is narrow and it is exactly the moment a landing feels finished.
- **RITUAL, IN FORCE FROM CHAIN 182: PUSH THE FREEZE COMMIT BEFORE `--attest`** (ruled here
  2026-08-29 on the sigil lane's finding; banked by them at sigil `1253036e` as this lane's
  ruling, and amended within the hour by them against the half of it that was weak).
  **A revision already in `origin/master` cannot be orphaned by a later rebase.** That is exactly
  what chain 181 lacked, and it is the structural fix rather than a detection: it costs one
  `git push` in an order this lane was performing anyway. Pushing the freeze before attesting is
  now part of the landing sequence, not a nicety.
  **`AHEAD OF REMOTE` at attest time stays a WARNING and does not refuse**, because that is the
  honest mid-ritual state today and refusing it would refuse the correct case — the same shape as
  the `SIGIL_HARNESS_ROOT` fix that would have refused when the variable was unset, guarding a
  hazard that did not exist, stopped only because the implementing lane measured before building
  what it had been told. **A refusal is safe exactly when the state it refuses has stopped being
  normal, and that is measurable rather than a judgement.**
  **The condition is therefore not armed until the ledger can answer it.** Sigil has queued
  `ATTEST-RECORDS-REACHABILITY` — `--attest` records the reachability state it observed into the
  entry it writes — after which "three consecutive clean chains" is **computed from the ledger by
  the walk that already reports orphans**, in one command, surviving every rotation on both sides
  and auditable after the fact rather than asserted. **Do not flip the refusal on a count anyone
  had to remember.**
- **⚠ AND THE PRE-FLIGHT ABOVE HAS A FALSE-POSITIVE CLASS I DID NOT SEE WHEN I WROTE IT: ON A
  BYTE-MOVING PARCEL THE PORT TESTS FAIL FOR A REASON THE FREEZE ITSELF FIXES** (added
  2026-08-29, within two hours of banking the bar it corrects; found by a diagnosis agent I
  dispatched *because I had misread the evidence*).
  **The two classes are distinguishable and the discriminator is one command:**
  `cargo test -p sigil-harness --test repin_pins` — its `pins_rs_is_current` arm regenerates the
  table in memory and diffs it; it is a READ-ONLY guard, not a repin. If it says
  *"pins.rs is STALE against the live listings (N changed pin(s))"*, the port failures are
  **stale-instrument** and the freeze will clear them. If pins are current and a port test still
  fails, it is the **cross-seam symbol** class — a name the standalone scope cannot resolve — and
  that one is real, needs a hand edit, and is what chains 182 and 184 hit.
  **So the corrected pre-flight is: run `repin_pins` FIRST, and only read the port tests as a
  finding once pins are current.**
  **AND THE TELL I WALKED PAST, which is the durable half: the plain ROM changed CRC at an
  IDENTICAL LENGTH.** `Level_LoadArt` sits at the same address in both trees because the +4 was
  absorbed inside the preset region. **A CRC change at an unchanged length is positive evidence
  that bytes moved without the image growing — which is precisely the repin trigger — and I read
  it as unremarkable.** Same length is the reassuring half of that pair and it is the half that
  means nothing.

- **RUN THE STRICT SUITE BEFORE THE FREEZE, NOT AFTER — A NEW CROSS-SEAM SYMBOL GOES RED AT
  ATTEST EVERY TIME, AND NOTHING UPSTREAM WARNS** (added 2026-08-29, after chains 182 and 184
  both did it).
  **⚠ SUPERSEDED BY A COMMAND, 2026-08-30 — RUN `tools/freeze_preflight.sh`.** The prose form
  below was complete, correct, and truncated on chain 187: this lane ran step 1 (`repin_pins`),
  found exactly what step 1 exists to find, and went straight to the freeze. **The sigil lane's
  diagnosis is why this is now a script and not a better sentence: step 1 is genuinely useful on
  its own, so COMPLETING IT FELT LIKE COMPLETING THE PRE-FLIGHT.** A two-step ritual whose first
  step is independently satisfying will keep being truncated there, and no amount of emphasis in
  prose fixes that — it is the same lesson as spelling an invocation inside the command span
  rather than beside it, arriving on a ritual instead of on a flag.
  **Operational form (what the script does): after the merge and the four-shape verify, and
  BEFORE `--freeze`, run the strict suite against the merged tree.** `AEON_DIR=<clean merge> cargo test --release
  --workspace --no-fail-fast` with `SIGIL_STRICT_GATE=1` — or simply expect `--attest`'s failures
  early by running the port targets alone, which is faster: the two that have bitten are
  `-p sigil-cli --test act_descriptor_port` and `--test parallax_port`.
  **A cheaper pre-flight that catches the whole class:** any parcel that adds a `pub` symbol which
  a *different* module references — a `dc.l`, an `extern`, a link `ensure` — has added a
  cross-seam ref. **Grep your own diff for new cross-module names before freezing**; that is the
  population, and it is enumerable from the parcel rather than discovered by the suite.
- One byte-mover per branch. Serialize refreezes. When any session is live-editing
  content in the main tree, build + freeze from a CLEAN CHECKOUT of the merge SHA.
  **The clean checkout must be threaded through ALL THREE legs explicitly** (lived
  2026-08-20): `repin -- --aeon <clean>`, `refreeze` with `AEON_DIR=<clean>`, AND the
  full suite with `AEON_DIR=<clean>` — each defaults to the sibling main tree on its
  own. The tell for a dirty-tree repin is region pins shifting in lockstep (+0x100-ish)
  with lengths unchanged; the tell for a dirty-tree suite is broad `*_port`
  region-diff failures at embedded addresses. A fresh clean worktree also needs one
  `./build.sh` + `DEBUG=1 ./build.sh` first — repin resolves but does not generate.
- **A CRC IS MEANINGLESS ACROSS SESSIONS WITHOUT THE ASSEMBLER REVISION BESIDE IT — and the
  toolchain is the one build input this repo does NOT pin** (added 2026-08-27; found by the
  aurora lane, whose first explanation AND this lane's confident refutation of it were BOTH
  wrong; their corrected packet is aurora `b1c15d0`).
  **OPERATIONAL FORM, adopted: quote the assembler REVISION beside every CRC you hand to
  anyone, and treat a cross-session CRC comparison as MEANINGLESS unless both sides carry the
  same revision.** Costs nothing; `build.sh:266` already computes it.
  **⚠ QUOTE THE REVISION, NOT THE WHOLE BANNER — one half of it is a stuck constant** (caught
  by the sigil lane within the hour of this rule being written; verified firsthand here).
  `build.sh` prints `Assembler: sigil <rev> (<tree>)`, and that parenthesised `tree` field
  reads **`dirty at capture — 0 modified, 1 untracked`** on every invocation. The one untracked
  file was `docs/lane-status.json` — read by no build, incapable of moving a byte.
  **The general form, and it is the durable output — a provenance record is not ONE claim, it
  is several, and they do not share a clock.** `revision:` follows git refs; `tree:` follows a
  build. Same line of output, two different freshnesses, and **nothing in the formatting says
  so.** Before quoting any provenance line as evidence, ask which of its components can move
  and on whose schedule — quoting it wholesale is how a constant, or a value frozen at an
  unrelated moment, gets cited as a signal. So the word `dirty` sits beside every CRC this repo quotes and
  **cannot vary**, which makes it exactly the thing this file has spent the night naming: a
  field that reads as a signal and is a constant. The discriminating half is inside the same
  string (`0 modified` vs `N modified`); the summary word is what over-warns, which is the
  `GOLDEN-DIRTY-BANNER` item already booked to the sigil lane.
  **⚠ STANDING TWO-WAY CONTRACT WITH THE SIGIL LANE ON THIS BANNER — agreed 2026-08-27, banked
  here because it was agreed in MAIL and would not have survived a `/clear`.** Neither lane
  changes the banner unilaterally: **sigil does not move `revision:`, `source:`, `tree:` or the
  `dirty` prefix without agreeing it here first, and this lane tells sigil before anything of
  ours that PARSES the banner moves.** Reaffirmed by the sigil lane unprompted at the chain-173
  handover, with the explicit reason that *"if it lives only in this thread it does not survive
  your next `/clear`"* — which is shared-protocol bar 20's sending-side half, correctly applied
  by the receiving lane rather than the sending one. **The obligation binds THIS repo across
  session boundaries, so it is a fact about the file and not about whoever is running the lane
  today.** Nothing else is owed between the lanes on the banner: as of that handover neither
  `ISLAND-PIECE-2` nor `VERSION-DIRT-CLASSIFY` has an aeon dependency.
  **Operational form, adopted here as well as there:** corroboration moves a claim from *guess*
  to *worth measuring*, never from *guess* to *established*. On any convergence, ask **what
  measurement would refute this, and did either derivation perform it** — and if the answer is
  no, the agreement is a hypothesis with two authors.
  *Local consequence worth knowing: because aeon TRACKS that file and this lane edits it all
  session without committing, the aeon main tree is effectively always dirty — which is why
  every freeze here needs a clean worktree rather than the main checkout. That is a property of
  our own status discipline, not of the freeze tooling.*
  **⚠ AND THE TRAP THIS LANE FELL INTO, which is the durable half.** Asked whether the drift
  was in aeon's tree, this lane compared 23 regenerated artifacts in a fresh worktree against
  the live tree, got **23/23 MATCH**, and reported the exposure closed as "fixture
  construction". The measurement was sound and answered **a different question**: both trees
  were built *at the same moment with the same binaries*, so the comparison **held the varying
  quantity fixed by construction** and could not detect an input that varies over TIME. A clean
  constant across varied inputs is evidence of a confound (bar 5) — here the inputs only looked
  varied. **Before reporting a green comparison as closing an exposure, name the quantity the
  exposure is about and check your design actually varied it.**
- Zero-byte parcels (tools/docs) are aeon-only; verify CRC identity anyway —
  byte-count-neutral is not byte-identical, and DEBUG-only procs can still move the
  release deb2 appendix.
- **A citation has TWO SHAs — the one you cite and the one you VERIFIED AT — and the
  second needs the same `ls-remote`** (lived 2026-08-22, this overseer's error, caught by
  already and gone stale again. **Anchor to the SYMBOL; let the SHA date the CLAIM, never
  the coordinate.** Practical convention, agreed with aurora-86: state explicitly whether a
  SHA is at `origin` or local-only — "verified reachable at origin" and "verified in my
  object store" are indistinguishable in a message and only one is an anchor. Treat every
  Aurora SHA as local-only unless they say otherwise.
- **On a byte-neutral parcel, byte identity stops being evidence about the BUILD and is
  only evidence about the SOURCE — freshness needs a separate witness** (lived 2026-08-22,
  exit code disagreeing with the artifacts. **Remedy: `rm -f` all four ROMs before the
  rebuild, so existence proves freshness**, and check mtimes. Note the asymmetry with the
  ordinary failure — a missing ROM is loud, a stale one is silent and ships four perfect
  CRCs as proof. **Standing hazard as of `98100905`:** that parcel edited `project.json`, so
  **an in-place `git checkout` into an EXISTING tree** containing it trips the staleness gate on
  mtime alone. **A fresh `git worktree add` does NOT** — measured three times by the sigil lane,
  who each time got `ok (generated >= editor)` where an earlier wording of this bullet predicted
  a stop. *(That earlier wording said "every fresh checkout" and was left standing here with a
  retraction underneath it; it is corrected in place now, because a claim asserted first and
  withdrawn second is still the claim a skimming reader carries away. Third report from the same
  lane is what it took, which is itself the argument for fixing the sentence rather than
  appending to it.)* The gate compares
  `newest mtime(editor sources) > newest mtime(generated tree)`, and `git worktree add` writes
  **every** file within the same second, so `>` is false and a fresh worktree does NOT trip it.
  `DONOR_PROVENANCE.json` churn, since unchanged level bytes mean the existing stamp still
  describes them).
  **The gate's input set is WIDER than `project.json`, and for some lanes the stop is
  CERTAIN rather than incidental** (sharpened 2026-08-22 by aurora-86, correcting this
  lane's narrower framing — which had made it contingent on a save path *incidentally*
  touching `project.json`). `tools/level_staleness.py`'s `editor_sources()` returns exactly
  three paths: the `games/<game>/data/editor` tree, **`games/<game>/data/editor_bg_override.json`**,
  and `project.json` — compared as `newest mtime(editor sources) > newest mtime(generated
  tree)`. So a lane whose *deliverable is writing one of those files* (an Aurora BG-override
  save, an editor-tree bake) is writing a gate input **by construction**, and hard-fails
  staleness **before a ROM is emitted**. Two consequences, separately: run
  `tools/regenerate-level.sh` between the write and the build; and **attribute a failure by
  stage and exit code before reading it as a verdict**, because a pre-emission staleness stop
  looks exactly like a downstream refusal gate rejecting the bytes you just wrote. Composes
  with the `rm -f` rule above — a build that never ran, plus leftover artifacts, greets you
  with four perfect CRCs.
- **CRC identity is blind to SOURCE-derived gates, and the pairing ritual cannot see
  what it does not trigger on** (found 2026-08-22 by sigil-83's warn-tier corpus, not by
  anything in this lane). sigil's warn-tier lint baseline lives in
  `crates/sigil-cli/tests/` and is only ever updated by a **refreeze**; a refreeze only
  happens when **bytes move**. So a parcel that changes `.emp` source while holding all
  four CRCs moves a source-derived lint set with **nothing in the ritual able to notice**.
  reach for and the one place nobody looks. **A zero-byte parcel that touches `.emp` owes
  a source-drift check, not just a CRC check** — the two ask different questions, and the
  CRC is the one that cannot answer this. Corollary for reading a lint verdict: the
  failure named is not "the odd field", it is "the *undecided* odd field" — a deliberate
  layout discharges it with a recorded adjudication plus a baseline update in the same
  commit, never with silence.
- **Sigil sessions/agents are read-only consumers of this tree** (their port gates read
  it via `AEON_DIR` at test runtime). Mid-brushstroke uncommitted aeon edits can flip
  sigil port-gate results — a sigil strict-gate run that matters points `AEON_DIR` at a
  clean checkout of a committed SHA, the same clean-checkout rule freezes use. Mirrored
  from sigil's `docs/OVERSEER.md` (024c7caa).

## Recovering a vintage artifact (before ANY toolchain-archaeology parcel)

**Prefer the committed artifact to the recipe that recreates it — and look for it at the revision
that PINNED it, not at the tip.** Shared protocol (`9b604f0` + companion clause `e650b96`); this
lane supplied the miss that earned the clause. **A SHA has a class; a path has a TIME.**


The procedure, since this repo's landing lane generates exactly these pairings on every refreeze:
1. Find the refreeze/pairing commit that moved the golden (its message names the pairing).
2. `git -C sigil cat-file blob <rev>:<path> > out.bin`, then **hash the extracted bytes yourself**
   — never trust the claim, including a peer's.
3. `git merge-base --is-ancestor <rev> master` before depending on it (reachable, not gc-able).
4. Only if the artifact genuinely isn't there, consider the rebuild — and price it first: the
   `bc048e2a` attempt failed on a PRE-rename `HARNESS` path
   (`oracle/linux-port/harness`, now `oracle-old/...`) and would then have hit
   `[map.undeclared-island] at 0x99F0` from current sigil having moved past that tree's map.
   Both halves were one pinned sigil revision — the same `7b46f075`.

**SCOPE — this procedure is RECOVERY ONLY, and the opposite operation runs at TIP** (protocol
`aadf63f`, caught by aurora-86 the same day). A **currency check** — "has the contract moved?",
"is our vendored copy stale?", "did sigil's golden change?" — must read the **tip**, the only
revision that can answer it. **Re-pointing a drift check at the pinning revision makes it vacuous:
a pinned blob equals itself by construction, so the gate passes forever and never detects the thing
it exists for** — a wrong-reason pass wearing protocol-compliance clothes, which is this repo's
oldest gate failure mode. The two operations look identical at the call site (both are "compare our
copy against the other repo"); **name which question you are asking before choosing the revision.**

## Instruments (which oracle for what)

**✅ HOLD LIFTED 2026-08-24 — read this before the block below, which is kept for its
mechanism and its scope note only.** Oracle fixed the straddle defect (red-first tests
`68461a7`, fix `4111c88`, merged `51143a5` — verified reachable at their `origin/main` here,


**✅ Pixel capture is COMPOSABLE TODAY — and the "capture is impossible here" belief is a
LEGACY-SERVER result that must not be carried forward.** `play_input` + `scanlines{}` +
`state_hash{includeFramebuffer}` are all served by the Rust core, and determinism is a
property it already gates: `a1_determinism_three_boots_byte_identical` compares three
servers, three sockets, full 224-line frames, byte-identical, with a poison beside it.
**So the three failed capture protocols and the non-deterministic screenshots are facts
about the OLD server.** Poison-test anything before adopting it as a gate — that sequencing
still stands — but stop repeating that raster work cannot be gated on pixels.

**DMA-enqueue union (axis-2 unlock) is also composable today**: a watchpoint record sweep
cross-checked with `run_to{symbol}` + `read_memory`. **`run_to` takes a `symbol`** — that is
the piece nobody had noticed, and it is what makes this composable rather than new work.

  **The remedy this lane first proposed — "say whose measurement it is when you repeat it in a
  message" — WOULD NOT HAVE CAUGHT IT, because no message was involved.** Oracle read the
  durable record, which is this suite's primary defence. **Verify-firsthand confirms the
  TRANSCRIPTION, never the CLAIM**: a faithfully-copied number is indistinguishable from an
  independently-measured one, and a reader cannot recover what the writer did not record.
  **So the attribution has to survive into the DURABLE RECORD, not merely into correspondence.**
- **STILL LEGACY, and it is not this lane's call**: `scene:*` (4 segments, 8 gates) drive
  `ab_runner.py`, which lives in `oracle-old` — porting it is oracle's; and `cost_model`
  drives `raster_cost_probe.py`, held below. At ~38 s each the scene segments are now 80% of
  the lane's wall clock, so ab_runner is the next real lever and it is a PROPOSAL FOR ORACLE.

**Four wire differences that bite, all measured, all handled inside the seam:**
1. `emulator/reset` takes **NO params** — the legacy `{"wait": true, "run": false}` is
   refused with -32602 (protocol §2.5 rejects undeclared keys), and is unnecessary anyway
   because the Rust core resets to a stopped machine.
2. The bus is **24 bits**: `0xFFFF0000` is -32004. `parse_lst` already yields 24-bit
   addresses, so nothing here needed masking — but a hand-written probe will.
3. **Breakpoints ARE served as of 2026-08-27** (`capabilities.breakpoints: true`; this line
   read "no breakpoints, no `wait_for_break`" until then, and that is why the four converted
   gates are written against `run_to`). `emulator/run_to {"addr"|"symbol", "maxFrames"}` remains
   correct and is still preferable where a **symbol** is what you have: CHECK `reached`, and it
   parks at an instruction boundary with the target instruction not yet executed — the same stop
   rule the breakpoint gates were written against (proved: `snapshot_poison` captures the same
   mask %0101 at the same PC on both servers). Reach for a breakpoint when you need
   arm→run→**halt on a hit you did not schedule**, which `run_to` structurally cannot express.
4. **THE QUIET ONE.** `read_memory` returns hex WITH a `0x` prefix; the legacy server
   returned it bare. `int(x, 16)` survives; anything that SLICES positionally
   (`raw[i*4:i*4+4]`) reads two characters off and reports a confident wrong answer with
   nothing raised. Route reads through `aether_instance.read_bytes`. In the write direction
   the core is loud instead: an unprefixed `bytes` param is -32602.


- **oracle-next / oracle-aether** (bus socket, headless): pixels, scanlines (sub-line
  since 2026-08-19), memory, watchpoints with per-hit mclk, the warp mailbox, and the whole
  effects gate lane bar the five above. Its profiler EXISTS (`capabilities.profiler: true`,
  measured 2026-08-26) and serves `interrupts.{hint,vint}.cyclesSelf` and
  `cyclesSelfTotal` — but `set_profiler` must be armed with `{perFrame: true}` and the
  `perFrame[]` ROWS still carry only `cycles`/`hintCycles`/`vintCycles`/`stallCycles`, **no
  self field for either interrupt bucket**, which is exactly the gap the hold above names.
  `tools/aether_instance.py`; other client patterns: `tools/hblank_window_sweep.py`,
  `tools/sh_probe.py`. Assert `source == "raster"` on every scanline capture.
- **old oracle** (headless harness at `oracle-old/linux-port/harness`): FALLBACK ONLY, and
  what still uses it is now a short list — `ab_runner.py` (the `scene:*` gates) and the three
  profiler probes. Per-routine rows ONLY (`interrupts.hint` sums both handlers); match
  addresses on the low 24 bits; attribution LOSES ~20% when a tick spans VBlank — rest
  conclusions on preemption-free evidence. Patterns: `tools/raster_cost_probe.py`,
  `tools/engine_baseline_probe.py`, `tools/streaming_choke_probe.py`.
- Subagents NEVER touch emulator MCP tools (deadlock); headless bus scripts are the
  sanctioned instrument everywhere.
- **The MCP shim's `emulator_status` now prefixes a BANNER text block before the JSON when the
  served ROM does not verify against `romPath` (stale, missing, or cannot-tell)** — oracle-old
  `58b6f81`, relayed by the hub 2026-08-27 from oracle-03, picked up at the next tool start. A
  reader that takes `content[0]` and parses it as JSON breaks **exactly when the ROM is stale**,
  i.e. in the one state the banner exists to announce.
  **Re-check this if a tool is ever written against the MCP shim rather than the bus** — the
  hub flagged us as the lane most likely to trip it because we rebuild `s4.bin` many times a
  night, and that reasoning is sound about our REBUILD RATE while being wrong about our
  TRANSPORT. Read the last block, never the first, if it ever applies.

## ⚠ THE AUTO-COMMIT DAEMON IS DEAD — stage the editor tree normally (2026-08-22)

**There is no auto-commit daemon.** Verified: no process, no user systemd unit (the only
one is `aeon-effects-gates.timer`), and the last commit touching
`games/sonic4/data/editor/ojz` is `a447e0fd`, **2026-08-12**.

Around **fifteen** handoff docs still tell every session that tree is daemon territory —
*"never stage, revert or touch it"*, *"Not ours"*. **Ignore that instruction wherever you
meet it.** `games/sonic4/data/editor/**` is ordinary work and is staged like any other.

sitting unversioned. **An ownership claim needs a liveness check, not a citation:** before
deferring to "something else owns this", confirm the something else exists.

## Worktree quirks (agents hit all of these)

- **A TIME WINDOW IS A CLAIM ABOUT THE CLOCK; A BLOB COMPARISON IS A CLAIM ABOUT THE ARTIFACT —
  AND ONLY ONE OF THEM CAN BE CHECKED AFTER THE FACT** (added 2026-08-29; the aurora lane's
  formulation, against the remedy THIS lane handed them).
  **Operational form: when disclosing that a tree was briefly wrong, give the receiver a CONTENT
  test, not a time window.** "Compare `<path>` at `origin/master` against `<frozen-rev>`; equal
  means you have the repaired tree" beats any interval. Offer the window only as colour, never as
  the check.
  *Generalises past this incident: every remediation notice this lane sends should hand over
  something the receiver can EVALUATE rather than something they must BELIEVE. Same family as
  quoting the assembler revision beside a CRC, and as never typing a hash into a message.*

  ~~**THE MAIN CHECKOUT IS DELIBERATELY BEHIND `origin/master` AND MUST STAY THAT WAY UNTIL `d-44`
  IS RULED.**~~ Its working tree held the owner's unruled `d-44` edit on
  `games/sonic4/data/generated/ojz/act1/effects_scenes.emp`, which the band parcel regenerates, so
  it could not take that merge. **The two rules that survive and are NOT conditional on `d-44`:**
  **do not sync a checked-out branch with `git update-ref`** — that is the defect above, and it is
  absolute — and **do all landing, freezing and committing from a dedicated worktree**, which this
  lane's rules already require for freezes and which extends to ordinary doc commits. A stale branch
  ref in that tree is visible and harmless; the shortcut that removes it is neither.

- **⚠⚠ `git update-ref` ON A CHECKED-OUT BRANCH DOES NOT REFRESH THAT TREE'S INDEX, AND THE NEXT
  EXACT-PATH COMMIT THERE SILENTLY DELETES EVERYTHING THE INDEX HAS NOT SEEN** (added 2026-08-29,
  chain 182; **this lane's defect, and the worst of the session** — it reverted a whole landed
  parcel off master and nothing announced it).
  **RULES, and the first is absolute:**
  1. **NEVER move a branch that is checked out somewhere with `update-ref`.** If the tree cannot
     take the change, leave it behind and say so — a stale ref is visible and harmless; a stale
     index is invisible and destructive. Prefer `git -C <tree> reset --keep <sha>` or simply do
     not sync that tree.
  2. **`git show --stat` YOUR OWN COMMIT, every time, and read the deletion count.** This is
     shared-protocol bar 23 — a commit message is a claim about a diff and nothing checks it —
     arriving with a 988-line disproof available in one command that was not run, on a commit
     whose message described adding one line.
  3. **After any repair of this shape, verify BOTH directions**: every restored path hash-equal to
     the source revision, AND every path with legitimate later work hash-equal to the pre-repair
     tip. One direction alone silently reverts the other half.

- **A KILLED FREEZE LEAVES A HALF-STATE THAT `git status` CANNOT SEE, BECAUSE THE MISSING
  ARTIFACT IS GITIGNORED — the tool everyone checks is the one that cannot report it** (added
  2026-08-29, chain 182; this lane's instance, and the sigil lane rates it above their own
  motivating case for the freeze-journal parcel).
  **Procedure after ANY killed freeze, in this order:** (1) check the sigil worktree for
  half-written goldens; (2) **check the aeon `AEON_DIR` tree for MISSING ROMs — by hashing all
  four, never by `git status`**; (3) rebuild whatever is absent and verify its CRC against the
  pin before re-running anything. `git checkout -- .` in the sigil worktree covers (1) and is
  silent about (2).

- **A SHARED DIRECTORY IS NOT A SHARED NAMESPACE — "it is in my repo's worktree list" is a fact
  about BOOKKEEPING, not about who it belongs to** (added 2026-08-27; this lane's error, disclosed
  unprompted). Pruning leftover worktrees on the owner's directive, this lane swept aeon's
  **Operational form: before removing ANYTHING under `~/sonic_hacks/`, grep the other lanes'
  `OVERSEER.md` for the path.** Cheap, and it is the only instrument that can see a declaration.
- **AND CHECK WHETHER SOMETHING IS RUNNING IN IT** (aurora's, relayed by the hub the same hour,
  after they removed a fixture directory the owner's live Aurora window had open — his next build
  died with `spawn ./build.sh ENOENT`). **A running tool does not appear in `git worktree list`.**
  Check `/proc/<pid>/cwd` or `lsof` before removing a directory. *(Checked here after the fact —
  no process held any removed path — which is the wrong order and is the reason this line exists.)*
  Their two companion rules, both adopted: test merged-ness by **HEAD with
  `merge-base --is-ancestor`**, never by branch name; and **look at uncommitted files** before
  removing a worktree that has them.
- **A WORKTREE CAN HOLD THE ONLY COPY OF SOMETHING — check before deleting, not after.** Two of
  the four unmerged trees in this sweep carried content that exists nowhere else:

- Export `AEON_SKDISASM_DIR=/home/volence/sonic_hacks/skdisasm`; the worktree root's
  PARENT DIRECTORY may carry a `sigil` symlink — **never the checkout itself, and this
  matters** (lived 2026-08-26 by the sigil lane, against this very line). They read "the
  worktree root's PARENT" as licence to add `sigil`/`skdisasm` links INSIDE their reference
  checkout; `section_row_fixture`'s tree mirror then died on them with *"the source path is
  neither a regular file nor a symlink to a regular file"* and three gates went red for a
  reason unrelated to anything under test. A reference checkout that only has to BUILD needs
  no links at all — `./build.sh` produced all four shapes there without them. So: links in
  the parent for an agent worktree, no links in a clean reference checkout, and if a gate
  dies on a path that is not a regular file, look for a link somebody seeded. ~~Without both, ~9-13 pytest failures are path
  artifacts, not signal.~~ **THE "~9-13 PATH ARTIFACTS" CLAIM IS STALE — corrected
  2026-08-22.** A full parcel ran in a worktree with **no** paired `sigil/.worktrees/<name>`
  and saw a **fully green suite before and after** (1262 → 1290 passed, 0 failed, across all
  four build shapes). Either the emp-helper-closure locator changed or the hazard was always
  narrower than written.
  **Reverse the default: treat pytest failures in a worktree as REAL until proven
  otherwise.** This correction matters more than the usual stale-fact fix because of its
  *direction* — the old wording licensed writing off up to thirteen genuine failures as
  noise, and a hazard that tells you to ignore red is far worse than one that tells you to
  expect it. Same family as the day's other three stale hazards (sigil-SHAs-are-local-only,
  every-checkout-trips-staleness, 147-pytest-fns-run-by-nothing), and the fourth in a row to
  fail in the *permissive* direction. **Prove the artifact, don't assume it:** name the
  failing test and show the path it could not resolve.
- `SIGIL_BUILD`/`SIGIL_EMIT` point at the sigil repo's release binaries; missing =
  BLOCKED report, never a workaround.
- **A PREBUILT BINARY IS A SNAPSHOT OF ITS SOURCE AT LINK TIME, AND IT CARRIES THAT SNAPSHOT
  SILENTLY IN EVERY DIMENSION AT ONCE** (added 2026-08-27; both instances this lane's, on one
  night, generalised by the sigil lane from them). Twice, *"invoke the prebuilt binary rather
  than `cargo run`"* was **individually correct and wrong in composition**:
  **Operational rule: when a tool's BEHAVIOUR is what you are reasoning about, run it from source
  or check what it was built from — a version banner or an mtime, never an assumption.**
  *Which is precisely what the assembler's version banner exists to answer, and both lanes spent
  the same night arguing about that banner while neither applied it to the harness tools.*
- **A GRANTED PERMISSION GOES STALE LIKE A STATUS FILE, AND HAS NO TIMESTAMP AT ALL** (added
  2026-08-27; the sigil lane's formulation, against their own lapse). This lane said *"safe to
  relink"* at a boundary with nothing measuring — true when said. **Then it dispatched a parcel**,
  **Rule adopted, both directions and symmetric: announce a relink of the shared
  `target/release/sigil` at the time, every time, regardless of standing permission — and treat
  "safe to relink" as EXPIRING the moment the grantor dispatches anything.** Cheap, and it removes
  the need for either party to reason about whether an old grant still holds. Proposed to the hub
  for the shared protocol, since it is a cross-lane rule and not aeon's to fork.
  **⚠ AMENDED WITHIN THE HOUR, AND THE AMENDMENT IS THE MORE IMPORTANT HALF (aurora's finding,
  relayed and endorsed by sigil, correcting a rule THIS LANE had just banked and proposed).**
  Three defects in the version above, all of which made it look complete from inside:
  closed. **Announce to EVERY lane, not to the party who granted the hold.**
  **(b) THE PROHIBITION WAS WRITTEN AT THE WRONG LEVEL — the subcommand, not the artifact.** The
  standing rule said *do not run `cargo build --release` in sigil*. The relink came from
  `cargo test --release --workspace`, which is not `cargo build` and relinks the identical file.
  **Anyone honouring that rule exactly would have done the same thing.** Guard the ARTIFACT, not
  the verb. *(This lane's own message to aurora happened to say "do not run ANY cargo command in
  sigil", which is the correct level — by luck of phrasing, not by design.)*
  **(c) AN ANNOUNCEMENT RULE DEPENDS ON SOMEBODY REMEMBERING, WHICH IS THE WEAKER FIX.** Sigil's
  own framing, against their own remedy. **The structural version is that no lane shares
  `target/` at all — a run that cannot reach the artifact cannot relink it, and then none of the
  announcement discipline is load-bearing.** Their agents already run that way; a landing run
  legitimately happens in the main checkout, so the residual is open and is not closed.
- **PIN A SHARED BINARY BY ITS md5, NOT BY ITS REVISION** (aurora's, 2026-08-27, correcting a pin
  THIS LANE handed them). We told aurora to quote the assembler `revision:` beside their CRCs.
  it reads *correct* while the artifact changes underneath. **An md5 of the binary changes exactly
  when the file changes and needs no cooperation from whoever relinks it.**
  **Operational form: quote `md5(SIGIL_BUILD)` AND the revision — the revision is what a human
  can look up in a history, the md5 is what identifies the artifact that actually ran.** Take the
  md5 before and after any build whose evidence you intend to cite; aurora's agent adopted one
  mid-parcel on its own initiative and it is the only reason anyone could say the binary was
  stable *within* each build, which no revision pin could have established.
- The committed ab_runner scenes hardcode the MAIN tree's `s4.debug.lst` — run against
  repointed copies in a worktree. `ab_runner --new` needs ABSOLUTE paths (relative
  resolves against the emulator's cwd and reports a convincing false verdict on
  uninitialised RAM).
- `FAST=1 ./build.sh` is the content-iteration loop (~1.3 s, lanes skipped, loud
  banner) — never the basis for landing evidence. Both build paths gate on level-data
  staleness.
- The effects gate lane self-segments with per-segment timeouts and scoped reaping;
  if a lane wedges anyway, kill only PIDs whose `/proc/<pid>/cmdline` carries YOUR
  worktree's ROM path.
- **A BACKGROUND WAITER THAT `pgrep`s FOR THE PROCESS IT IS WAITING ON SELF-MATCHES AND CAN
  NEVER EXIT** (measured 2026-08-27; the mechanism is the sigil lane's, the population and the
  ownership are this lane's correction of it). `until ! pgrep -f "refreeze --attest"; do sleep
  20; done` **never terminates**, because the waiting shell's own command line contains the
  literal `refreeze --attest`, so `pgrep -f` matches at least itself on every pass. Three such
  **And the shared-machine half, which is why the kill is by PID and never by pattern:** at the
  moment of reaping, a real `cargo test --workspace --no-fail-fast` was running — **oracle's**,
  in `oracle/.claude/worktrees/agent-a6f38c56c54c36360`, verified by `/proc/<pid>/cwd`. Any
  pattern-shaped kill aimed at the waiters would have been one careless regex away from taking
  another lane's verification with it. Check ownership in the same command that kills
  (`ppid` + a cmdline token), and re-assert the innocent process is still up afterwards.

## Changed-parameter moves — POINTER, not a copy

When you need to vary the enumeration parameter (bar 19) and have no move to hand — which
bar 21 says is the actual failure, not ignorance of the principle — the list lives in
**sigil**, deliberately in one place so it cannot fork:

```sh
git -C ../sigil fetch -q origin && git -C ../sigil show \
  origin/master:docs/superpowers/notes/2026-08-27-changed-parameter-moves.md
```

Ten moves, four of them from this lane's instances. **Do not copy rows into this file** — ask
the sigil lane to edit theirs. Read it at the committed revision, never through the sibling
path, for the same reason the protocol is read that way.

## Aeon-specific review bars (beyond the protocol's)

- **A MEASUREMENT RECORDED WITHOUT THE THING IT WAS TAKEN AGAINST DECAYS INTO A FALSE CLAIM —
  SILENTLY, BECAUSE THE NUMBER ITSELF NEVER CHANGES** (added 2026-08-30T09:35Z; developed jointly
  with the sigil lane, four instances in one evening, three of them this lane's).
  **THE OPERATIONS.** (1) Every figure carries its referent in the same sentence: CRC + baseline
  SHA, self-observation + clock, address + shape, count + unit (**sites vs files** — both right,
  different things). (2) **Date** a decayed figure, never overwrite it: it was true, it lacked a
  bound. (3) **Where a claim TURNS on a term — a falsifier, a gate, a count stated over it —
  restate the definition INLINE AT THAT USE**, not in a glossary and not at first use. "Define your
  terms" is advice nobody can act on; this is narrow enough to do. (4) When two lanes' numbers
  differ by a **constant**, test the offset hypothesis before reporting a conflict — a systematic
  delta is a shape difference, and testing it turns a disagreement into a doubled measurement.
  (5) Prefer an **expected-immobile witness** to "constant across every address": **uniformity is
  what a systematic error and a real shift have in common; immobility is what only the real shift
  has.** (6) A structure whose **total** is right can still be wrong — `2+36+2 = 40` summed
  correctly while describing one mover where there are two, in two different fixtures; a structure
  that cannot account for a downstream observation is wrong even when its arithmetic checks out.
  **AND THE ATTRIBUTION RULE THAT GOES WITH IT, which matters more than the bar:** when a defective
  record misleads a careful reader, **the reader behaved correctly and the defect is the record's.**
  Reading it the other way is how a defective record survives — **it recruits its own victims as
  the explanation.** *The flattering reading was available to this lane all evening and it would
  have had no reason to notice it had taken it.*

- **A STALE SENTENCE IN A PLANNING DOCUMENT IS EXECUTED AS A WORK ORDER — and nothing can
  contradict it, because the thing that superseded it is a commit in ANOTHER REPO** (added
  2026-08-29; three instances in one exchange, framing jointly with the sigil lane, the
  no-edge-to-walk diagnosis theirs).
  **What IS cheap and is adopted: when a booking asserts a fact about a sibling repo, cite the
  peer revision inline** — the same rule this file already carries for claims, now pointed at
  PLANS. That converts *"the frozen tables are the authority"* into *"…(sigil `<rev>`, read
  `<date>`)"*, which a reader can check in one command instead of inheriting.
  **And the operational form for the reader, which needs no tooling: take a booking's SHAPE and
  re-derive its NUMBERS.** The R1 audit's eight requirements are still exactly right as a shape —
  object bank, hard-org'd sound banks, DAC banks, `error_handler` last, OJZ islands contiguous,
  vectors and header — and two of its addresses are wrong. **Shape ages well; coordinates do
  not.** That is the same split as *anchor to the SYMBOL, let the SHA date the CLAIM*, arriving
  on plans instead of on citations.

- **REPORT THE REASONING, NOT THE VERDICT — A CONCLUSION IS NOT REFUTABLE AND READS AS MORE
  COMPETENT THAN AN ARGUMENT** (added 2026-08-29; the sigil lane's formulation, offered against
  this lane's own attempt to credit them for two catches).
  **So the transferable habit is not "have a peer check you" — a peer cannot check a conclusion.
  It is: state the argument, and state it in the form that can be refuted.** That is what a peer
  review is *for*; the second pair of eyes is worthless against a report that only carries
  outcomes. A checklist cannot carry this habit, which is why it is written as a bar and not as a
  step.
  **Corollary for anything this lane sends or banks: prefer the sentence that could be wrong.**
  "Both revisions were ancestors before the suite ran" invites the question that killed it (could
  it have been otherwise?); "reachability green" does not.

- **A REFUSAL THAT CAN FIRE ON THE CORRECT CASE IS WORSE THAN THE SILENCE IT REPLACES — three
  declined in one night, which makes it a rule rather than three judgement calls** (added
  2026-08-29; instances split between this lane and the sigil lane, the pattern named here after
  the third).
  **Test before building any refusal: name a correct run that would trip it.** If you can, it is a
  warning until the state it refuses has demonstrably stopped occurring — and *demonstrably* means
  a query someone can run, not a count someone remembers.

- **`stat` PRINTS LOCAL TIME AND YOUR EVIDENCE IS TIMESTAMPED IN UTC — THE OFFSET IS RIGHT
  THERE IN THE OUTPUT AND IS READ AS DECORATION** (added 2026-08-29; this lane's error, caught
  by the aurora lane after it had already reached three lanes).
  **Operational form: use `TZ=UTC stat` or `date -u -r <file>` whenever a file time is going into
  a message, a card or a doc**, and when quoting one, write the `Z`. Never hand a bare wall-clock
  across a lane boundary — the receiver cannot tell which zone it was read in, and the failure is
  silent in both directions.

- **A GATE WHOSE PASS AND FAIL EMIT THE SAME ARTIFACT IN YOUR ENVIRONMENT HAS NOT PASSED — IT
  HAS NOT RUN** (added 2026-08-29; the aurora lane's formulation of an observation this lane made
  about its own staleness gate, and their wording is the one to keep).
  **The reusable procedure, in their words: name the property, then ask what a GREEN would have
  ruled out.** In a fresh worktree, nothing. So "staleness passed" is **unquotable as evidence
  from a clean checkout** — not because the gate is wrong (it is correct in the tree it was
  designed for) but because in that environment it is not an instrument at all.

- **A "KNOWN PRE-EXISTING FAILURE" NOTE ROTS INTO A LICENCE TO IGNORE RED — SECOND INSTANCE, AND
  THIS ONE WAS IN A COMMIT MESSAGE** (added 2026-08-29, the repaint landing). This file already
  **Cost of the corrective: one `pytest` invocation on a clean checkout.** Pay it every time — and
  note that the measurement is what MADE the landing safe, since a genuine new failure introduced
  by that parcel would have been invisible behind the same sentence.

- **A RULING RELAYED ON THE OWNER'S BEHALF CAN CARRY CONSTRAINTS HE NEVER STATED, AND THEY ARRIVE
  WEARING HIS AUTHORITY** (added 2026-08-29; the hub's error, withdrawn by them unprompted and
  banked there as a hub error; this lane caught it by measuring the tool rather than by suspecting
  the message).
  **This lane receives most owner rulings through that relay** (d-36, d-38, d-40, d-37 all arrived
  that way), so the exposure is structural rather than one bad message.
  **The remedy already exists and is the hub's own practice: they quote his words VERBATIM** —
  *"theyy should all be flush"*, *"1"*. **Read a relay as two separable things: the quoted ruling,
  which is his, and the operational scaffolding around it, which is the relayer's and is
  checkable like any other peer claim.** An operational constraint arriving without quoted words
  behind it has an author, and it is not him.
  **What actually caught it was not suspicion — it was doing the measurement anyway.** The
  discrepancy surfaced from a read-only check run against the live tree before touching anything,
  which is the general lesson: **a gate you run before you have any reason to distrust the
  instruction is the only one that can catch an instruction you had no reason to distrust.**

- **A SILENT ROUTE-AROUND LEAVES THE BROKEN FORM FULLY INTACT — WHEN YOU ROUTE AROUND A BAD
  CITATION, SAY THAT YOU DID** (added 2026-08-29, chain 180; **the sigil lane's finding against
  themselves**, banked at sigil `326fe095`, verified reachable at their `origin/master` here and
  the sentence read firsthand out of that blob rather than out of their message).
  **Operational form:** `freeze <SHA> · attested <SHA>` for a paired landing, and when a peer hands
  you a SHA you have to correct silently to use, correct it out loud in the same message.
- **A HABIT THAT HAPPENS TO COVER A DEFECT IS INDISTINGUISHABLE FROM A DESIGN THAT PREVENTS IT,
  RIGHT UP UNTIL THE DAY IT IS NOT** (added 2026-08-29, chain 180; this lane's formulation, adopted
  by the sigil lane for two of their own instances the same hour). The general case of the
  rehearsal-is-not-protection clause, pointed at things that WORKED.
  **Why it earns a bar rather than a shrug: a covering habit produces exactly the evidence a
  designed check produces, so nothing distinguishes them while both hold.** The green run is not
  evidence the mechanism exists. **Test: name what would have happened if the habit had not fired,
  and if the answer is a wrong result reported confidently, write the habit down as a rule or build
  the check.**

- **FINDING THE MACHINERY IS NOT FINDING IT RUN — shared-protocol bar 16 (name / presence /
  behaviour) arriving on a CODE PATH** (added 2026-08-27; this lane's over-claim, named by the
  **The presence of a code path that WOULD explain a behaviour is not evidence that it DID.**
  It reads as an explanation because it is specific, it is real, and it is exactly the shape the
  question was looking for — which is precisely the trap: a plausible mechanism found while
  hunting for one is the hardest kind to hold at arm's length.
  **The corrective is the same as bar 16's everywhere else — convert it to behaviour**: find the
  invocation, not the definition; check the closure that is actually passed, not the parameter it
  is passed to. *(Recorded with its useful half intact: the find still moved the question from
  "I cannot locate the mechanism" to "does any caller on this path supply a non-constant closure",
  which is a sharper and differently-shaped question. Narrowing is worth reporting. Reporting it
  as closure is not.)*
- **A CLAIM ABOUT ANOTHER LANE'S TREE, LIVING IN YOURS, CAN NEVER MEET ITS CONTRADICTION — AND A
  DOC HAS NO `updatedAt`** (added 2026-08-27; the oracle lane's, banked from their third instance
  in one day, and it lands on this file harder than on theirs).
  **Remedy, and it is the protocol's verified-at anchor pointed INWARD: when a doc here asserts
  anything about a sibling repo's code, record the peer revision inline** — `(sigil 8dc62906,
  read 2026-08-27)`. That converts an unfalsifiable sentence into a one-command currency check.
  And re-read the peer's **tip** before exporting a claim, never the doc that quotes it.
  **And the second half is this lane's, banked by oracle in these words: a peer's warning about
  YOUR OWN tree is the class you must verify before acting on, and it is the one that feels least
  like it needs checking** — it arrives as help, about your own code, from someone with no motive
  to be wrong. **Their confident claim nearly became this lane's agent brief**, and it was caught
  by opening the file to locate line numbers rather than by suspecting anything. **That is luck,
  and it is not a method.**
- **A GREP HIT THAT CONFIRMS WHAT YOU SET OUT TO FIND IS THE ONE YOU ARE LEAST LIKELY TO READ THE
  CONTEXT OF — THE SEARCH ITSELF SELECTED FOR AGREEMENT** (added 2026-08-27; this lane's error,
  and the sigil lane asked for it as a bar rather than an apology). Shared-protocol bar 11 says
  read the lines AROUND a cited line before accepting what it proves. **This is the sharper
  form: when the hit CONFIRMS your hypothesis, the confirmation is the reason you stop reading —
  so the danger is highest exactly where the evidence looks best.**
  **Corrective: when a hit confirms what you were looking for, read its enclosing block BEFORE
  reporting it** — and if the hit is a printed string, find out what prints it.
- **HOLDING A RULE AND APPLYING IT TO YOUR OWN OUTPUT ARE SEPARATE ACTS — and the gap between
  them is measured in MINUTES, not days** (added 2026-08-27; the formulation is the sigil lane's,
  the instance count is mostly this lane's). This is the frame that explains why almost every
  corrective in this file is a MECHANISM rather than a reminder, and it should be read before
  the bars below, because it is the reason they are shaped the way they are.
  **What follows operationally, and it is the whole value:**
  1. **Prefer a check that cannot be omitted to a rule that must be remembered.** Wait on a PID,
     not on a name. Parse the line the file will parse, do not scan it for bad characters. Let
     the tool set the flag rather than asking the rule to carry it.
  2. **Point the rule at your OWN output at the moment you write it**, not only at work you are
     reviewing. Every instance above was caught by the *other* lane, because scrutiny naturally
     flows outward.
  3. **A rule you have just written down is at its most dangerous, not its safest** — it feels
     handled, which is exactly when it stops being checked.

- **A green log and an absent run are the same artifact** — **SHARED PROTOCOL bar 25**
  (empyrean `dc0ebe7`, verified reachable at `origin/main` here and `--stat`-checked as a
  protocol-doc commit; read it there, do not restate it here). This lane's instance earned
  it. Summary only, so a brief author knows whether they need it: *"the check was weaker
  than we thought"* and *"the check never ran"* produce identical evidence — a green log
  with nothing in it about the subject — which is the absence surface arriving on a
  POSITIVE artifact. The instance, both correctives, and the two-chain cost are in the
  landing-lane stanza above.


- **THE "CONFIRM THE GATE'S NAME APPEARS IN ITS OWN LOG" CORRECTIVE IS UNRUNNABLE AGAINST
  THIS REPO'S PYTEST LANE, AND I MEASURED IT** (added 2026-08-27; the class is the sigil
  lane's, found against their own `zero skip:` bar; **this instance is aeon's and measured
  firsthand here**). Bar 25's corrective (1) says confirm the gate's NAME appears in the run's
  own log rather than merely that the run was green. Good rule. It cannot be run here.
  **The remedy is an ENUMERATION, not a better grep** — and it is bar-cheap:
  `python3 -m pytest tools/ --collect-only -q --no-header -p no:cacheprovider` lists every
  test id and **cost 0.19 s for 1451 ids** when measured. Diff the collected id set across the
  revisions in question; that answers "which gates exist to be run" from a source that cannot
  quietly shrink, where a log grep answers it from a source that can. Same shape as the
  generator-enumeration bar above: enumerate the population from something that emits it, not
  from an artifact that merely mentions it.
  *(Do not read 1451 as a pass count — it is what COLLECTS. The older `1262 → 1290 passed`
  figure elsewhere in this file was measured differently and the two are not reconciled.)*
  **Reciprocal finding from the sigil lane, worth knowing before you trust any Rust-side
  skip claim** (their measurement, relayed, not verified here): libtest **captures a passing
  test's output**, so `cargo test … | grep skip` sees nothing from passing tests — their
  documented hand-run "zero `skip:` lines" bar has never been able to observe the thing it
  asserts. Their automated `scripts/nightly_source_gates.sh` passes `-- --nocapture` and is
  fine; the hand bar is the blind one. **If a rule here ever spells a `cargo test` whose
  OUTPUT you then grep, it needs `--nocapture`.** This lane's landing-lane `cargo test` is
  safe on that count because its bar is aggregate totals from the summary line, which prints
  under capture — but check it again if that bar ever grows a grep.

- **Cross-repo claims verify against the described repo AT AUTHORING TIME, citing the SHA
  verified at** — now the shared protocol's rule too (empyrean `00334b6`, 2026-08-22), with
  this repo's effects-schema arc as its precedent, so put it in agent briefs that survey a
  sibling tree. Lived here: an assessment quoted aurora's ROADMAP faithfully and shipped a
- **Check the CLASS of a SHA before citing it** — SHARED PROTOCOL, read it there, do not
  restate it here (empyrean `43fbfc9` + `6d38fbc`, both from this arc; the both-outcomes
  nuance this repo proposed is now upstream too). Summary only, so a brief author knows
  whether they need it: a code guarantee anchors to the merge that carries the code,
  `--stat`-ed before the citation hardens. Paired with the claim rule above — that one
  governs what a doc asserts, this one governs what it cites.
- **Enumerate by what TOUCHES the data, not what defines it** — SHARED PROTOCOL review bar 8
  (empyrean `dc629a5`), precedent again from this arc: two overseers cross-verified each
  other's sidecar-ref enumerations firsthand and both got 8; the real count was 13, the misses
  being copiers OUTSIDE the codec frame — one of them (`cloneSection`) unguarded under a
  3,909-test suite. Every named site was real and both verifications passed; the failure was the
  shared FRAME. **Mutual verification cannot catch a shared frame — only a changed frame can.**
  When counting where a field lives, grep the TYPE and every constructor/copier of the record,
  never just the field name in its owning module. Aeon's own ERRATUM 1 enumeration is the
  corrected example.
- **Never change the subject to suit the instrument** — SHARED PROTOCOL bar 9 (empyrean
  `c2c81e2`). **This one has teeth in THIS repo specifically:** almost every instrument here
  reaches the engine through a differently-configured build — `DEBUG=1` shapes, the MD Debugger
  island, the effects-gate lane's `s4.debug.bin`, profiler builds that alter what they profile.
  A number measured on a debug/instrumented shape and reported as RELEASE behaviour is exactly
  this failure, and it announces itself no more loudly than the timer-clamp case did. Say which
  shape produced a number, and if the instrument cannot reach the release shape, report the reach
  limit rather than quietly measuring the reachable thing. (`FAST=1` builds are the same trap in
  a different coat — see the build header.)
- **A confidently-offered weak point is a misdirection, even in good faith** — SHARED PROTOCOL
  bar 11 (empyrean `20a8e81`), from THIS repo's own error. A volunteered caveat reads as a
  certificate that the rest was checked as carefully, and it steers scrutiny toward the part the
  author already doubted and away from the part they didn't. Not a rule against caveats — keep
  flagging weak points — a rule about what the flag does NOT certify. **The cheap check: read the
  lines AROUND a cited line before accepting what it proves; a citation is a pointer into code
  that keeps executing past the line you were shown.** Lived: this overseer cited
  `ControlSocket.cpp:2042`'s integer division as proving an invocation excess, invited the peer to
  attack the one dependency it named — and `:2043`, the very next line, was a clamp that killed
  the inference outright. Reproduced arithmetic, a verified call site, and a well-placed caveat
  all held; the line below the cited one did not.
- **A gate's VERDICT and its STATED REASON are separately checkable** — SHARED PROTOCOL bar 10
  (same commit). Check the reason against the data before quoting it onward: a tripwire can fire
  correctly while its message fabricates the justification (precedent: a spread formula falling
  through a zero branch announced "medians agree to within 0.00%" about a set spanning
  0.000→0.800 ms). The reason is what a reader carries forward, so a sound verdict with a
  fabricated reason is worse than a failing gate. Relevant to every gate in `tools/` that prints
  its own explanation.

- **A gap between BOUNDARY labels is never evidence of free space — and the rule must NAME
  the instrument that can answer, or everyone reaches the wrong answer politely** (lived
  2026-08-24; three parties, one shared instrument). The frozen `offcanonical_sizes` tables
  **What makes this a bar and not a repeat of the existing allotment rule:** the booking
  ALREADY said *"a gap is an ALLOTMENT, never proven free space"* — and then committed the
  error two paragraphs later on a different label pair, and two more lanes inherited it. A
  rule that says "do not conclude X" without saying **what does conclude X** leaves the
  reader holding the only tool they have. **The instrument for occupancy is the `.lst` symbol
  listing or a scan of the ROM image itself; the frozen table structurally cannot answer it.**

- **A completeness claim about a TRUNCATED view — `head -N` on a definition — and the
  truncation leaves no mark** (lived 2026-08-24, this overseer's error, caught by the sigil
  lane). Establishing whether a section qualified for a sigil mechanism, this lane read
  **Correctives, both cheap:** count the thing before characterising it (`grep -c` the variant
  pattern over the *whole* definition, never a window), and when a reduction rests on a
  category (*"all X are instructions"*), enumerate the category from the type and check each
  member against the predicate rather than against the category's typical member.

- **A COMPILED-IN library and the INVOKED binary are two artifacts, and a suite green only
  witnesses the one it links** (added 2026-08-26; drawn by the sigil lane against this lane's
  own assertion, mid-parcel). Landing the replay re-stamp, this overseer checked sigil's stale
  **⚠ AND THE FALSE MECHANISM WAS THE DANGEROUS HALF, WHICH IS WHY THIS IS CORRECTED RATHER THAN
  ANNOTATED.** *"The suite does not touch the CLI binary"* licenses the inference *"so relinking
  it mid-run is harmless"* — and that is **genuinely unsafe**. A concurrent build swapping
  `target/release/sigil` **while the suite runs** hands spawned tests a partially-written or
  wrong-revision binary, producing failures scattered across unrelated tests with no diagnostic
  pointing at the cause (sigil's shared-`CARGO_TARGET_DIR` trap produces 284 such failures, which
  read exactly like golden divergence).
  **So the operational constraint is CONCURRENCY, not usage: for the length of any strict/attest
  run, nothing may build into the main checkout's `target/`.** That is a rule the false version
  of this stanza would have told you to ignore.
  **Operational form: `cargo build --release` in sigil is a precondition of any refreeze, and
  it is a SEPARATE ACT that nobody's green can stand in for.** When the pairing is live,
  require the sigil lane to say "rebuilt" explicitly rather than inferring it from their suite.
  Re-derive the staleness at the moment of freezing, never from an earlier check: this instance
  went from harmless to load-bearing inside one merge.
- **An instrument that reports an ABSENCE can manufacture that absence, and the check is
  whether the instrument could have produced the empty result** (added 2026-08-26; contributed
  by the sigil lane against their own near miss, and **framed at their insistence as the
  absence class rather than as a fact about one tool** — that framing correction is the
  **The framing the finder insisted on, and it is the durable part:** the transferable lesson
  is NOT "`strings` is unreliable". It is that **an absence was read as a finding without
  asking whether the instrument could have produced it**. Booked as a tool fact, the next
  reader reaches for `grep -a` and repeats the class with a different tool on a different day.
  Same family as `ls` aliased to `eza` failing and being read as an empty directory, and as
  `2>/dev/null` deleting the only correcting signal.
  **Operational form:** before treating an empty result as evidence, name what the instrument
  would print if it had FAILED, and confirm that is not what you are looking at — a positive
  control (ask the same question a second way, on something you know is present) is cheaper
  than the retraction.
- **EXACT-PATH STAGING CANNOT WITNESS WHAT WAS DIRTY — the count can, and only the count**
  (added 2026-08-26; this lane's wrong mechanism, corrected by the sigil lane, who verified the
  **The general form, and why it is booked as a bar:** the verdict was right and the reason was
  wrong, and **the reason is what gets written down and reused** (shared-protocol bar 10,
  turned on one's own evidence instead of a gate's message). As stated it licensed *"my commit
  shows no source, therefore no source was dirty"* on every future paired landing. When
  offering a commit as evidence about a TREE STATE, ask what the commit would look like if the
  claim were false; if the answer is "the same", the artifact is not the witness. Reach for a
  count, a timestamp, or any figure produced by something other than the hand making the claim.
- **A BOUND TEST THAT FIXES ITS INPUT IS ONE-DIRECTIONAL, and the direction it cannot see
  is the one that leaves it GREEN** (added 2026-08-27; found by the aurora lane during the
  matching half of the 16-layer raise, relayed by the hub). Their instance: a test asserted an
  **The corrective is bar 1 (derived, never copied) pointed at FIXTURES rather than at
  expectations** — the over-long case is `MAX+1`, not `9` and not `17` — plus a test the
  one-directional version cannot pass: **prove it red at a ceiling moved DOWN as well as up.**
  A derived fixture tracks the constant in both directions; a re-authored one tracks it in
  neither.
- **ENUMERATE A CONSTANT POPULATION BY ITS GENERATOR, NEVER BY ITS SPELLING — AND A VALUE
  SPELLED AS A SYMBOL LOOKS MORE DERIVED THAN A LITERAL, NOT LESS** (added 2026-08-27; the
  finding and the whole method are the sigil lane's, from their OFFCANON-ROT parcel; **relayed
  here from mail and NOT verified firsthand in their tree** — treat the mechanism as theirs to
  certify and re-ground it before citing it onward).
  **Operational form:** enumerate the population from the TOOLS that write it — every value some
  generator emits into a checked-in artifact — recompute each, and diff. The blind spot becomes
  "a value no generator produces", which is small and nameable, instead of "a value spelled in a
  way I did not anticipate", which is neither. In sigil that population was three tools writing
  the same ROM address into three artifacts; **this repo's equivalent is any address or length a
  generator writes and a human also transcribes**, and finding that set is the sweep.
  **The complementary parameter, if you want corroboration rather than a copy of their sweep**
  (bar 19: the parameter must differ, and a second sweep that is a worse version of the first
  varies nothing): they enumerated by **generator** — what WRITES the value. Enumerate by
  **consumer** — what READS it and would notice it being wrong. Their fourth value had **no
  reader at all**, its only consumer an `unwrap_or` fallback made unreachable by a loud error
  elsewhere, which is precisely why it drifted silently. A consumer-side sweep finds the class
  *values nothing would notice being wrong*; the two sets are not supersets of each other.

- **⚠ AND THE PROSE SWEEP HAS ITS OWN BLIND SPOT: A PARCEL MOVES ADDRESSES IT NEVER TOUCHES**
  (added 2026-08-27; found by the sigil lane in THIS tree, a day after this lane swept its own
  prose and reported it clean). `games/sonic4/data/sound/dac_banks.emp`'s header described the
  **THE SWEEP'S RULE IS "GREP THE VALUES THIS PARCEL MOVED" AND THAT IS THE HOLE.** A prose sweep
  naturally enumerates from the diff — the values you changed. **This file was never edited. It
  started lying when something else moved underneath it.** Addresses a parcel **MOVES** are a
  different population from addresses a parcel **TOUCHES**, and only the second is reachable by
  grepping your own change.
  **Operational form: after a parcel that RELOCATES anything, sweep the OLD values too** — grep
  the addresses as they were *before*, across the whole tree, not the addresses as they are now.
  The stale prose says the old number by definition, so the new number cannot find it.
  *And fix it by DELETING the number, not by re-typing today's: a fresh literal goes stale on the
  identical clock, which is exactly how these got there.*
  **✅ CLOSED 2026-08-29** by `fix/stale-dac-anchor-prose` — full write-up in `docs/DEFERRED_WORK.md`
  ("THE STALE DAC/SOUND-BANK ANCHOR PROSE, SWEPT BY THE *OLD* VALUES"). Note for anyone reading this
  bullet as the record: **the header fix it describes (`28c9ee02`, 2026-08-27) was not the sweep.**
  It fixed the four sites in `dac_banks.emp`'s header and nothing else, and this bullet went on
  reading as fully open, so the operational rule it states had never been run. Running it found **20
  more live sites across 10 files** (enumerated in the DEFERRED_WORK entry so the count is
  checkable) — one of them eight lines below `28c9ee02`'s own ⚠ warning. Two
  classes the rule as written would still miss: (a) prose whose **mechanism** was deleted rather than
  moved (`dac_samples.emp` described map regions removed 25 days *earlier*; the wrong-looking address
  was the *less* wrong half), and (b) a **generator diverged from its own `DO NOT EDIT BY HAND`
  output**, so regenerating would have reintroduced stale text. Add both to the sweep: after
  relocating anything, also grep for mechanisms recently *deleted*, and re-run every generator to
  confirm it round-trips against its checked-in output.
- **PROSE BOUNDS ARE A POPULATION THE "IS IT DERIVED?" SWEEP DOES NOT REACH** (added
  2026-08-27; same source). After a sweep across every code consumer, one literal `8` survived
  in an agent-facing tool **description string**. Help text, `argparse` descriptions, docstrings,
  refusal and error messages that state a bound in words, and comments asserting a number are
  reached by **neither** an identifier grep nor a quoted-key grep — the two this repo already
  requires running together, on the standing finding that neither is a superset of the other.
  Prose is a third population outside both.
  **Operational form:** when a constant moves, grep the prose — help/usage strings, descriptions,
  docstrings, refusal text, comments — as a named third pass, and say you ran it.
  **And the discipline that makes an empty prose sweep reportable at all:** grep each moved value in
  THREE forms — bare hex (`0x4DA`), the `$`-prefixed assembler spelling (`$4DA`), and decimal — and
  **report the patterns, not just the verdict.** An empty sweep and a pattern that never could have
  matched are the same artifact (bar 16(d) turned on the sweep itself).
- Cycle claims near VDP ports: the bus absorbs adjacent OPERAND accesses but not
  instruction-stream fetches — nominal tables mispriced three consecutive parcels.
  Measure with the cost lane; the F-series/dense rows re-derive from shipped constants.
- Raster spins are SOLVED (`raster_dsl.emp`'s solver from the measured window anchor);
  a parcel that hand-adjusts a spin or a cost-gate expectation is wrong by definition.
- `.emp` comptime work: `docs/EMP_PITFALLS.md` first, every time.
- Cross-seam references: **a FIRST reference, in a module sigil's port harness compiles
  standalone, breaks that module's `*_port` test.**
  **⚠ THE MECHANISM, MEASURED 2026-08-29 — AND THE TWO SIGIL-SIDE FIELDS ANSWER DIFFERENT
  QUESTIONS, WHICH IS WHERE THIS LANE GOT IT WRONG.** The harness does **not** resolve ram symbols
  by region: every cross-seam address symbol is **hand-listed by name**, and each row becomes a
  synthetic one-byte carrier pinned at a per-shape VMA. A name absent from that table is an
  unresolved external, so **new names in an existing region get nothing for free** (the sigil lane's,
  read out of `addr_labels()` in three port tests rather than reasoned from `test_support`).
  Three sites per new symbol: a `[[symbol]]` block in `crates/sigil-harness/repin.toml`; a `pins.rs`
  constant (`debug_only` symbols emit a bare `pub const`, pushed inside the `if debug { }` branch,
  not wrapped in `pick()`); and **the label row in each consuming port test**.
  **BOTH FIELDS TAKE THE FULL LOWERING POPULATION. Write `repin.toml`'s `tests = [...]` with every
  test that lowers the module, exactly like the `addr_labels()` rows.**
  **Sequencing, agreed with the sigil lane:** `repin.toml` rows can be written ahead; `pins.rs`
  values **cannot**, because repin resolves addresses out of aeon's listings — so the aeon parcel
  must build and emit listings first, and a paired landing of this shape is one ordered chain with
  aeon as its back half.
  **Region gates move too, not just symbol resolution:** a parcel growing a routine a port test
  lowers will shift that test's region diff independently of any unresolved name. Lived: a ~71-line
  addition inside `VInt_Level`, which `game_loop_port` and `load_art_port` both lower and both
  annotate.
  **The class is worth keeping even though the symptom improved:** a `*_port` test compiles ONE
  module standalone, so a reference that is fine in the linked ROM is a hard failure there.
  Any parcel adding a first cross-seam name to a ported module owes the harness a composition,
  and this is a *paired* cost — the aeon change is correct and the sigil side still has to move.

- **TWO PARCELS INSIDE ONE A/B RANGE CANNOT BE SEPARATED BY DIFFERENCING ITS ENDS — AND BOTH
  LANES WILL REACH FOR THE ENDS** (added 2026-08-29, chain 179; the shared error, found by the
  sigil lane auditing this lane's pin description and resolved here with a third revision).
  **Operational form: before attributing bytes to a parcel, count the movers in the range. If
  it is more than one, the intermediate merge SHA IS the instrument** — it exists, it is free,
  and it is the only thing that can answer. The landing lane's own "serialize byte-movers,
  never batch two in one branch" rule exists for exactly this and says nothing about a FREEZE
  that spans two already-serialized branches, which is how the gap opened.

- **A PIN FIELD MEASURES WHERE PINS ARE, NOT WHERE CODE IS — and its silence is an absence in
  the INSTRUMENT** (added 2026-08-29, same chain; the sigil lane's instance, against
  themselves, banked here because this lane's own instruments have the same property).
  reporting only `PSTATE_JUMP`/`PSTATE_ROLLJUMP` firing. **When an instrument reports an absence,
  ask what it is a census OF before reporting what is missing from the subject.**

- **⚠ CHAIN 179's FREEZE COMMIT CARRIES A WRONG DESCRIPTION OF ITS OWN PIN MOVEMENT — DO NOT
  QUOTE IT; THE CORRECTION IS HERE AND OWES A LINE IN THE NEXT ENTRY'S PROSE.** `13a6d3c8`'s

- **DECLARED TREE — `/home/volence/sonic_hacks/.aeon-land-182`, do not sweep it.** A clean
  detached checkout of aeon `e99a2ca7`, the `aeon_rev` chain 182/183 is frozen at, carrying all
  four built shapes. `AEON_DIR` points here for anything asking what chain 182 actually froze.
  **`.aeon-land-180` and `.aeon-land-181` are RETIRED by this line** — say so here rather than
  deleting the line. The sigil-side `.sigil-pair-182` was transient and is removed: it held
  nothing that is not now at `origin/master`.

- **PUSH-BEFORE-ATTEST HAS A COST NOBODY PRICED, AND IT SHOWED UP ON ITS FIRST USE: A RED STRICT
  SUITE NOW LANDS ON MASTER BEFORE YOU KNOW IT IS RED** (added 2026-08-29, chain 182).
  *General form, and it is the sharpest thing in this file about gates: when a ritual is changed
  to PREVENT a state, every check for that state goes vacuous at the same moment — and it goes
  vacuous while continuing to print green, which reads as the fix being confirmed. Ask of any
  green beside a new ritual: could this have come back dirty, given what the ritual now
  guarantees? If not, it is witnessing compliance, not correctness.* **Then the suite went red, and sigil's `master` sat red between
  the freeze commit and the fix.**
  *Related and load-bearing for anyone who meets a red attest: an entry is FROZEN once it records
  a strict run, so a red one is abandoned via `--supersede-tip`, never amended. **Abandonment
  legally requires the recorded red run**, so COMMIT the failed `[entry.strict]` rather than
  tidying it away — reverting that file to keep history clean locks you out of the only legal
  path forward. Lived at 182: three red tests, all of them the ritual working (two
  `act_descriptor_port` cross-seam link asserts wanting the parcel's new symbol supplied to the
  standalone scope, and `repin_pins` wanting its per-parcel term), none moving a ROM byte —
  proven independently by `FIXPOINT PASSED` on the supersede.*

- **DECLARED TREE — `/home/volence/sonic_hacks/.aeon-land-180`, do not sweep it.** A clean
  detached checkout of aeon `03ed1f1c`, the `aeon_rev` chain 180 is frozen at, carrying all four
  built shapes. It is the tree `AEON_DIR` should point at for anything asking what chain 180
  actually froze, and rebuilding four shapes to recreate it is the expensive half of any
  artifact-dependent run. **`.aeon-freeze-179` is RETIRED by this line** (chain 180 supersedes it)
  — say so here rather than deleting the line, per the rule below.
  **Freeze worktrees on the SIGIL side are transient and are NOT declared**: `.sigil-pair-180` was
  created for chain 180's freeze and removed once both halves were pushed, because it held nothing
  that is not now at `origin/master`. Declare a tree for what it would COST to recreate, not for
  having existed.
  **What actually works is simpler than what I wrote: stand in the tree you mean to freeze.**
  Setting `SIGIL_HARNESS_ROOT` as well is harmless and still fine. **`SIGIL_BUILD` is the one that
  genuinely must be set** when aiming a prebuilt refreeze at a fresh worktree — it defaults to
  `<root>/target/release/sigil`, which a new worktree does not have, and `capture_goldens.sh`
  exits naming the path, so that one is friction rather than silence.
  **AND THE BINARY ANNOUNCES THE MISMATCH LOUDLY, WHICH IS A FEATURE TO USE RATHER THAN A WARNING
  TO WAVE PAST** — it prints *built from X, operating on Y … if it predates what you are about to
  ask it, rebuild it*. The check that discharges it is two commands, not a rebuild: `git log
  --since=<binary mtime> -- crates/` and `--stat` on whatever it returns. For chain 180 both
  intervening commits touched `golden/` data only, no Rust source, so the binary was current with
  its source and the rebuild was correctly skipped. **Run that check every time rather than
  remembering this result** — it is a fact about one night, not about the binary.
- **RETIRED — `/home/volence/sonic_hacks/.aeon-freeze-179`.** A clean
  detached checkout of aeon `4ba7cb92`, the `aeon_rev` chain 179 is frozen at, carrying all four
  built shapes and both `.lst` listings. It is the tree `AEON_DIR` should point at for anything
  asking what chain 179 actually froze, and rebuilding four shapes to recreate it is the
  expensive half of any artifact-dependent run.

### 2026-08-30T16:25Z — CORRECTION: the d-41 left-edge fix has been ON MASTER since 2026-08-29 11:20 (def98ee5), not on a branch

Three records in this lane and one in the hub said the fix was "reverted on master" and needed restoring: the d-32 retraction
(`043cf485`), the two d-41 `answered` entries of 2026-08-30 02:05Z/02:10Z, the resume brief this session handed its look-build
agent, and empyrean's 16:09Z check. All wrong the same way: the revert `48eded35` (08-29 10:30) was followed by the RE-LAND
`def98ee5` (08-29 11:20, chain 186, attested) and everyone downstream copied the first half of the day. Verified firsthand:
`git merge-base --is-ancestor 48eded35 def98ee5` = yes; `VSCROLL_COL19_BG_OFF` in master `engine/level/parallax.emp:717`; the
store at `s4.debug.lst` `cap_per_col_vsram_fill_begin` 7C6C..7CB2. The agent sent to "restore" it produced an EMPTY revert-of-revert
and reported that instead of committing nothing, which is the behaviour the escape hatch exists for. **Bar:** a claim about what is
on master is checked with `git log -S <the fix's own symbol> -- <file>` before it goes in a brief; a revert's existence says
nothing about what happened after it. The owner's window (master build) therefore already carried band + fix; it was stepped to
scene 13 and left running at 16:25Z (this heading and this time are from the commit clock; the first version of this note wrote 16:27Z from memory).
