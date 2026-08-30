# Aeon Overseer

**Boot prompt** (paste into a fresh session started in this repo):

> You're the overseer for this repo. Read `docs/OVERSEER.md` first, then
> `../empyrean/docs/OVERSEER-PROTOCOL.md`. Work the queue. Peers may or may not be
> running — check `ListAgents`; coordinate if present, proceed solo if not.

The role, delegation discipline, review bars, and peer protocol live in the shared
protocol doc. This file is what's aeon-specific.

## The queue

> ### RESUME BRIEF FOR THE NEXT AEON SESSION (first written 2026-08-30T00:38Z; **partly superseded, revised 2026-08-30T09:07Z** — read the strikes, they are the point)
> **DO NOT BOOT INTO A STOP AND WAIT FOR A PICK.** The owner's go is recorded — empyrean
> `origin/main` `7149b39`, verified reachable here, and his standing instruction in it reads
> *"Do not boot into a stop and wait for a pick: his pick is this paragraph."* The hub pushes
> lanes continuously through the ratified plan and rules in his place where a lane is blocked.
> **This overrides the `/overseer` skill's boot stop, which is exactly the exception that skill
> names.**
>
> **⚠ THE PREVIOUS `START WITH` IS SPENT — DO NOT EXECUTE IT.** It said *"run
> `tools/band_witness.py` and find out whether a colour band can be shown at all"*. That was
> answered: the tool landed at `235ef669` (*"the first evidence a palette band reaches the
> screen"*), a band **does** reach the screen, and the finding turned into a different row —
> `BAND-PALETTE-ENTRY-CHOICE`: the bands work and are near-invisible, because they recolour ONE
> palette entry that only **1.64%** of the scene is drawn with. That is a content/authoring call
> (which entry, or several), not a mechanism defect, and it is the owner's. Left here as a struck
> instruction rather than deleted, because this file's own first review bar is that **a stale
> sentence in a planning document is executed as a work order** — and this one survived 8.5 hours
> of being exactly that.
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
> re-verified here at 10:03Z after the hub pushed on this lane's catch.** The interval is recorded
> because it was real: at 10:00Z the commit was present in the hub's clone and NOT an ancestor of
> `origin/main` — sigil's `AHEAD OF REMOTE`, structurally the same sentence as an orphan to
> anyone reading later, and actionable here only because the blob was readable in their tree. The
> bar it instances is **push before you ask anyone to cite it**, the same one this lane took for
> `--attest`. Re-check reachability anyway: this line ages, the check does not.
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
> That is this file's own diagnosis of the class: **the artifact that supersedes a booking is a
> commit in a different tree, so there is no edge for anything to walk.** Nothing will notice for
> you. `lane-status.json` carries the current answer and is rewritten from the clock at every
> dispatch, ruling and landing; this block is rewritten only when someone remembers to.

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
  Chain 190 moved assembled lengths (+38 in `ojz_effects`, 204/207 symbols sliding +32) and
  **owed no per-parcel term**; `repin_pins` ran 2 passed / 0 failed / 1 ignored. Left struck
  rather than deleted because this file's own first bar is that a stale sentence in a planning
  document is executed as a work order — and a lander following this one would have hand-written
  a term into a test that cannot read it.

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

  **Why the tool sets the flag rather than the rule asking you to — this is the durable
  lesson and it is about rules, not about sigil's tool.** Chains 169 and 170 landed following
  a rule that was **complete in its steps and inert in its spelling**: one missing token,
  `SIGIL_STRICT_GATE=1`, and the suite structurally could not execute the gates the refreeze
  exists to move. `SFX_BODY_LEN` was stale from chain 169 (2046 against a region that grew to
  0x8DA) and rode through both, surfacing only when chain 171 ran strict. **The staleness was
  never hidden; it was never asked.** Both lanes' first hypothesis was a silent skip — the
  more comfortable reading, because it means the check existed — and sigil refuted it from
  source: there was no run at all. **A rule cannot be trusted to carry a token nobody audits**,
  which is why the remedy is a tool that cannot omit it and not a more emphatic sentence.

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

  **Anchors, and one citation correction made in passing.** The feature merge is sigil
  `74793994` (`Merge branch 'feat/refreeze-attest'`), `--stat`-verified here as the commit that
  carries the code — it touches the harness plus every `*_port.rs`. The code-carrying commit
  under it is `e435333f`. Docs are `9040dc36` (their `origin/master` tip at the time of
  writing). **Sigil's message cited `729cd642` for "REFREEZE-NEEDS-STRICT is in"; that SHA is
  reachable and does touch `refreeze.rs`, but it is a `clippy -D warnings` fixup (2 files,
  8+/8-)** — a lint cleanup standing in for a feature merge. Exactly the SHA-class bar, caught
  by `--stat`-ing a citation from a lane that has been rigorous all night, which is the whole
  argument for checking every citation rather than suspecting particular peers.

  **Standing commitment to the sigil lane (`REFREEZE-NEEDS-STRICT`, agreed 2026-08-27, landed
  their `74793994`): every paired refreeze clears the full strict suite before push, whoever
  lands it.** It is one command on top of a landing this lane is already doing, and it is not
  a courtesy — it is the run that should have happened at 169 and 170.
  **Their declared bar moves to 3990 / 0 / 4 (3994 declared).** Derive it at the time rather
  than quoting this line; it has moved twice in two days. *(Recorded because it is the shape
  this file keeps meeting: their agent claimed a delta of 53 new tests; the measured delta was
  40. The tree was self-consistent, the claimed delta was not.)*

- **NEVER LEAVE A SHARED CHECKOUT ON A PRIVATE BRANCH — a repoint silently invalidates
  every other session's already-correct branch check** (added 2026-08-27; this lane's defect,
  disclosed by the sigil lane who bore the cost). Landing chain 172, this overseer committed the
  paired freeze in sigil's **shared main checkout**, switching it from `master` to
  `parcel/band-ceiling-16-pair` and leaving it there. Four minutes later the sigil lane committed
  a lane-log entry onto that branch. They repaired it (cherry-picked to master, `reset --hard`
  back), disclosed it unprompted, and asked to be verified rather than trusted — verified here,
  content and not just SHAs, since `reset --hard` on someone else's branch is precisely what
  could destroy a freeze while leaving the SHA looking right.
  **Their branch check did not fail — it was INVALIDATED RETROACTIVELY.** They had verified the
  branch at boot and no event on their side could have told them it moved, because this lane
  moved it. That is the shape worth keeping: **repointing a shared checkout changes what
  `git commit` means for every session using it, silently and after the fact.** Framing it as
  the committer's carelessness lets the real defect escape, and the party who can prevent it
  most cheaply is the one repointing, not the one committing.
  **Two correctives at opposite ends, both live:** the committer verifies the branch **in the
  same command that commits**, never at boot (sigil's, and it is the one that protects you
  against a peer doing this to you); and **this lane does freeze work in a dedicated worktree,
  leaving the shared checkout on `master`** — done, `/home/volence/sonic_hacks/.sigil-pair-172`.
  This repo's own protocol already says worktrees are why a shared main tree never matters;
  committing in the shared tree is the one act that makes it matter again.
  *Blast radius was bounded by the exact-path staging rule even with the branch check defeated —
  their commit touched only their own lane-log — which is evidence that rule earns its keep
  beyond the reason it was written for.*
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
  **This supersedes the "seven" figure this file carried for one hour.** Seven was the output of
  *this lane's board audit* — entries both unsuperseded AND unsurfaced — reported as though it were
  the population that fails the READER. It is a strictly narrower set, and the difference is 24
  lines. *The correction came from the hub refusing a recalled number and asking for a measurement;
  the first measurement I ran off my own paraphrase of the predicate gave 23, and only transcribing
  the reader's actual predicate gave the true figure.*
  **MEASURED: 86 lines · 55 parse · 31 REJECTED**, counted per LINE. Predicate transcribed from
  dominion `796bc1e` `server/src/decisions.ts`. Reasons (collected, so one line carries several):
   22  options must list two or more
   19  option missing key
   19  option missing name
    4  recommend must be an object
    3  options missing
    3  recommend missing
    2  recommend.key names no option
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
  *Worth keeping, because it argues for the fix rather than against the authors: the malformed shape
  is MORE readable to a human — "RESOLVED, not a question any more" in the question field tells a
  person the answer at a glance, where 8c's identical-question reproduction reads as an open card
  until you notice `supersedes`. Whoever wrote these was solving a real legibility problem. That is
  the case for the `answered` field, not for tolerating drift.*
- **A PARCEL THAT MOVES AN IMAGE PIN CANNOT BE VERIFIED BY A CANONICAL BUILD FROM A CLEAN
  STATE — THE GATE READS ON-DISK LISTINGS AND THE BUILD REFUSES BEFORE REGENERATING THEM**
  (added 2026-08-30, hit landing the clamps parcel; the escape is `FAST=1`).
  `build.sh` runs the tool-suite pytest **before** it builds ("*the build tooling is broken, not
  just the ROM*"). `tools/demo_specialization_witness.py` — reached through
  `test_effects_gates_segments.py` — reads `s4.debug.lst` and `demo.debug.lst` **from disk**. So on
  a merge that both moves code and updates that pin: the listings on disk are still PRE-change, the
  pin in source is POST-change, the witness fails, the build refuses, and **the listings are never
  regenerated.** A deadlock, and it looks exactly like the parcel being wrong.
  **THE ESCAPE, and it is the documented one:** `FAST=1 DEBUG=1 ./build.sh` (and the `demo` shape)
  skips the verification lanes, regenerates both listings, and then a canonical build passes.
  `FAST=1` prints its own banner saying it is not a ship artifact, which is exactly right — it is
  being used here to BOOTSTRAP the instrument, not to skip the check. **Re-run canonically
  afterwards; that is the run whose totals you quote.** Measured: 1660 passed / 0 failed on all
  four shapes after the refresh, against `1 failed` before it.
  **THIS IS THE SAME GATE'S FALSE-GREEN, SEEN FROM THE OTHER SIDE, AND THAT IS THE DURABLE HALF.**
  The building agent independently found that a build order leaving either listing stale lets all
  four shapes go green *before* the pin is updated. So stale listings make this gate **false-green
  when the pin is old and false-RED when the pin is new**, and **neither state is distinguishable
  from a real result by reading the gate's output.** A gate whose subject is a file on disk rather
  than the tree is reporting on whatever the last build left behind.
  *Generalisation worth carrying beyond this gate: when a check reads a GENERATED ARTIFACT rather
  than regenerating it, its verdict is about the artifact's freshness as much as about the code, and
  it cannot tell you which. `bganim_room`'s provenance line — which prints how many seconds after
  the build started its inputs were written — is the shape that solves this, and this witness has no
  equivalent.* Booked: give the witness a freshness assertion of its own.

- **A RECOMMENDATION SHOULD CARRY ITS IMPLEMENTATION CONSTRAINTS WHEN THE RECOMMENDER IS THE
  BENEFICIARY** (added 2026-08-30; the sigil lane's self-correction, and this lane is the party it
  protects).
  They recommended freezing the `.lst` beside each golden ROM. They priced the benefit precisely —
  their own failure class, their own two wasted builds — declared the interest unprompted, argued it
  hard enough to move a ruling, and **did not look at how it would be implemented until after the
  ruling existed.** The implementation had a trap in it that would have frozen an off-canonical
  listing under a canonical name, deterministically, on the first run. **The cost of that would have
  landed in THIS lane's ritual, on their argument.**
  **The bar: when you recommend a change whose cost lands on someone else, the implementation
  constraints are part of the recommendation, not a follow-up.** Declaring the interest — which they
  did, and which is why the recommendation was trustworthy — covers the *motive* and says nothing
  about the *feasibility*. A beneficiary who has not costed the implementation is asking the payer to
  discover it.
  **This lane's own corrective, since it is the receiving side: measure the cost yourself (done —
  65 KB compressed against 6.7 MB) AND ask what the implementation touches, before ruling.** I did
  the first and not the second; the trap was found by the recommender, not by me.
  **⚠ AND A CREDIT CORRECTION THAT IS THE ACTUAL LESSON, theirs, refusing praise for the wrong
  mechanism.** I wrote that their build-order sweep "ran against the change they had just
  recommended", i.e. that they audited their own win. **False: the sweep had finished hours earlier.**
  What happened is smaller and reproducible — they were *holding a named class* (**correctness that
  depends on invocation order, with no failing mode to observe**) and the new proposal walked into
  it. **The transferable form is "keep the class list where you will meet it", NOT "audit your own
  wins".** Stating it as vigilance would teach a habit nobody can perform on demand; stating it as
  a live class list is a thing this file can actually be.

- **AN UNATTESTED COMMIT'S CROSS-SEAM DEBT IS PAID BY WHOEVER FREEZES NEXT — AND GETS ATTRIBUTED
  TO THEM** (established 2026-08-30 after chain 187's red was blamed on the wrong parcel TWICE, once
  by this lane and once by sigil).
  **The measured facts**, from valid readings only (see the zsh trap below):
  `Cache_Fill_Resume_Col` occurrences in `section.emp` + `plane_buffer.emp` — at `def98ee5`, the last
  GREEN attest: **0**. At `2718cf0a`, the clamps merge: **7** (4 + 3). **`839d600d` — the d-45 canopy
  fix, merged to master at `42cb5781` — added all seven** (`git show 839d600d -- <both files>` counts
  7 added lines; pickaxe over `def98ee5..2718cf0a` names it and only it). **The clamps parcel's own
  two commits, `d3b3ab5a` and `9ba11115`, added ZERO.**
  **Forty-nine commits sat on master between the d-45 merge and the clamps merge, with no attest
  among them.** So the cross-seam reference was introduced by one parcel, went unattested because no
  freeze ran, and went red under the *next* parcel to freeze — which was mine, and which had nothing
  to do with it.
  **THREE STORIES WERE TOLD ABOUT THIS AND THE FIRST TWO WERE BOTH WRONG.** Mine: *"the reference
  pre-existed, my byte movement pulled it into a compiled span"* — wrong, it did not pre-exist the
  last green attest. Sigil's correction: *"your parcel introduced it"* — also wrong, my commits add
  none. **The truth is neither: a third parcel introduced it and mine merely arrived at the till.**
  **The structural lesson, and it is about the ritual rather than about anyone's care: attest debt
  accrues silently and is charged to a stranger.** A freeze attributes every strict failure to the
  parcel being frozen, because that is the only parcel it knows about. The longer the gap between
  attests, the more of someone else's debt the next freezer inherits — and the natural reading of the
  red, by everyone including the person who caused it, is that the current parcel did it.
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
  *Same class as everything else this night: absent rendered as a number.*

- **`emulator/screen_text` READS THE DEBUGGER'S CHROME, NOT THE GAME'S PICTURE — and its `F`
  COUNTER MUST NEVER BE JOINED TO A BUS FIELD** (added 2026-08-30; served at oracle build
  `52815f2`, contract Aether §11.29, vectors `cb1201b`).
  It returns `surfaces[]` — `statusLine | toast | palette | lens | titleBar` — each with `text`
  (what the player composed), `rendered` (what fits on the glass), `truncated`, and
  `unrenderable[]`. **Both `text` and `rendered` are served deliberately:** reading only `rendered`
  loses the reason inside a truncated message; reading only `text` reports strings that are **not on
  screen**. *Did the window tell the user X* wants `rendered`; *what did the player mean to say*
  wants `text`.
  **⚠ THE TRAP, and it is exactly the shape this file keeps recording: the status line's `F` is a UI
  COUNTER, NOT THE MACHINE'S FRAME.** It is bumped after every run iteration whether or not a frame
  completed, so a mid-frame breakpoint stop leaves a **permanent +1** and a state load diverges it
  **without bound**. **Joining it to any bus field produces a plausible number that is about
  something else.** Use `emulator/status`'s `frame`. *A value that is real, adjacent, and answering a
  different question — the same family as `pgrep -f` matching its own watcher and `$?` reporting the
  last pipe stage.*
  **⚠ AND WHAT IT DOES NOT DO, stated because the offer was framed as ending eyeball requests:
  it reads the emulator's own overlay, not the rendered game.** Everything this lane has asked the
  owner to LOOK at — the right-edge price, the background wrap, the colour bands — is game pixels,
  and `screen_text` cannot see them. Where it does help is anything drawn as debugger chrome, and
  the booked SCENE-READOUT item is the first candidate **if** that readout is chrome rather than
  game graphics — which is unmeasured and must be checked before the item is planned around it.
  `unrenderable[]` exists because the player has no glyph for a backtick or an em dash and draws a
  hollow box; an assertion against a literal containing either finds out through that field rather
  than by eye.
  **Open and named by oracle rather than skipped: it has never run against a real window.** Every
  path is unit-tested and the headless refusal is a genuine end-to-end capture, but the windowed
  case is unobserved — they will not put a window on the owner's desktop while he is logged in. **On
  the windowed path, suspect it before suspecting your own code.**

- **THE EXIT CODE YOU READ IS OFTEN NOT THE ONE YOU WANT — echo the REAL one INSIDE the log**
  (added 2026-08-30; five instances across two lanes in one night, none of them subtle in hindsight
  and all of them silent).
  Measured here: `cmd | tail -3; echo "EXIT=${PIPESTATUS[0]}"` printed **`EXIT=`** (empty) more than
  once, and `cmd | head -2; echo $?` reported **head's** status, not the command's — which turned a
  real `exit 1` into a green-looking `0` while I was verifying a red-first proof. Sigil's three:
  a backgrounded run reported *"completed (exit code 0)"* while cargo was still executing (the `&`
  shell had exited, not the suite); a clean run reported *"failed with exit code 1"* because of a
  trailing `grep -c` finding no matches; and the same `grep -c` class again.
  **Operational form: have the process write its own exit code INTO its own log**, and read that.
  `{ cmd; echo "REAL_EXIT=$?"; } > log 2>&1` — then the number you read is the one the command
  produced, not the one the last stage of your pipeline produced. Sigil's note is the sharp version:
  *the only reason any of the three was caught is that the real exit code was echoed inside the log.*
  **And when the process is backgrounded, an exit code says nothing about the WORK.** The tell that
  saved them was the log's mtime still advancing — which is this file's own *check the artifact, not
  the process* rule doing the work under a different name.
  *Same family as the four instrument faults above: a value that is real, adjacent, and about
  something other than what you asked.*

- **`pgrep -f "<cmd>"` MATCHES YOUR OWN WATCHER, so an until-loop waiting on a process can never
  exit — and it reports the process as ALIVE long after you killed it** (added 2026-08-30; cost 35
  minutes of a landing believing a strict attest was still running when it had been dead the whole
  time).
  `until ! pgrep -f "refreeze --attest"; do sleep 15; done` run through the shell puts that exact
  string on the WATCHER's own command line, so `pgrep -f` finds the watcher, the condition never
  goes false, and every later `pgrep -f` check from the session **also** matches it. Two independent
  symptoms, both confidently wrong: the loop never fires, and every manual "is it still running?"
  answers yes.
  **What made it survive scrutiny is that the kill had ALREADY WORKED.** A `kill -TERM`/`pkill -9`
  earlier in the chain did land on the real binary; the process was gone; and the checks kept saying
  running. So the evidence read as *"the kill failed and the tool is stubborn"* — a coherent story
  that explains the same observation and is entirely false. The attest had died mid-run, its suite
  log was complete and GREEN (357 suites, 4156 passed, 0 failed, 0 `skip:`), and `provenance.toml`
  was never written because the process was killed before the write.
  **Use `pgrep -x <name>`** — it matches the executable name, so a `zsh` running your loop cannot
  match a binary called `refreeze`. Where `-x` will not do (a script run under an interpreter),
  match on something the watcher cannot contain, or check for the ARTIFACT rather than the process:
  *did `provenance.toml` change* is a question about the world, and *is the process alive* is a
  question your own command line can answer wrongly.
  *The family: an instrument that includes itself in its own population. Same night as a `grep -c`
  counting a spelling, a `grep -c` printing 0 for a failed read, and a `git show $rev:path` eaten by
  a zsh history modifier — all four rendered ABSENCE or SELF as a confident value.*

- **THE SHA BAR HAS ONLY EVER BEEN WRITTEN FOR THE RECEIVING SIDE, AND THE FAILURE LIVES ON THE
  EMITTING SIDE** (added 2026-08-30; this lane's own defect, caught by the hub within minutes).
  This file's existing SHA rules all say the same thing: `--stat` a citation you RECEIVE. That is
  the half with a rule. Landing the band-spike capture, this overseer reported the commit as
  `8b23f0f` — **a hash typed from memory of a commit it had made itself four minutes earlier**,
  resolving in no object store anywhere. The hub could not open it and said so.
  **Why this is not the same bar arriving again.** Every prior instance was a citation to somebody
  else's work, checked or not. This one was never checked because it was never DOUBTED: it was my
  own commit, made by me, minutes old, and the feeling attached to it was memory rather than
  inference. **The receiving-side rule is structurally incapable of catching it — there is no
  incoming artifact to `--stat`.**
  **Operational form: EMIT every SHA from the command that proves it, in the same invocation as the
  thing it anchors.** `git branch --show-current && git rev-parse HEAD && git show --stat HEAD` —
  then quote what came back, never what you remember. Costs one command; the alternative is a
  plausible-looking hash that sends a reader hunting for a clone that does not exist.
  *And the second defect underneath it, which the hub's diagnosis found and mine had missed: the
  commit was also UNPUSHED, so even a correct hash would have failed for them. A mistyped-but-pushed
  SHA fails loudly; a fabricated one on an unpushed commit fails as a mystery. Push before you cite,
  and verify the push with `merge-base --is-ancestor` rather than the push command's own output.*
- **MEASURED 2026-08-30: A 41-COMMIT ASSEMBLER CHANGE MOVED ZERO ROM BYTES — and the stuck banner
  field is FIXED.** The sigil lane relinked `target/release/sigil` from `85a5726c` to `ec4c368d`
  while this lane sat at a boundary. Rebuilt to see whether the night's quoted CRCs still reproduce:
  at the same `aeon_rev ec6a4791`, **both assemblers produce `s4.debug.bin crc=6516fc68
  len=736315`** — byte-identical, matching the chain-188 golden.
  **This is a CASE 2 row in the drift record's own terms — same `aeon_rev`, new `sigil_rev`,
  expectation from a genuinely earlier build — QUIET AND EVIDENCE-BEARING**, and it arrived by
  accident. Worth keeping because it is the population sigil correctly observed that ordinary
  activity almost never produces, which is why their nightly job will MANUFACTURE it by holding
  `aeon_rev` pinned.
  **The cheap discriminator agreed and was still not sufficient on its own:**
  `git diff --stat <old>..<new> -- crates/sigil-frontend-emp/src crates/sigil-link/src
  crates/sigil-cli/src crates/sigil-frontend-as/src` is EMPTY — the byte-producing code did not
  move; the 27 changed files are harness and *test* code. So the source-level prediction was "no
  byte change" and the build confirmed it. **"The code did not change" and "the bytes did not
  change" are different claims, and only the second is the one a record stores.** Predict from the
  diff if you like; store the build.
  **AND: `build.sh` now prints `Assembler: sigil ec4c368d6a37 (clean at capture — no uncommitted
  changes)`.** The stuck/stale `-dirty` field this file has warned about twice is gone. Note the
  test that was banked for it — *a `revision:` that is not `fbf60abd`*, not the flag clearing — and
  both halves now hold, so the warning above is **discharged** rather than merely quiet.

- **`sigil --version` DIFFERING FROM SIGIL'S `HEAD` IS THIS REPO'S NORMAL STEADY STATE, NOT A
  SIGNAL** (added 2026-08-30; the sigil lane's sharpening of a diagnostic this lane ran correctly).
  The binary self-reports the revision it was linked at. After any docs-only commit over there —
  and their lane-log, decisions and OVERSEER writes are constant — that revision trails `HEAD`
  while the binary is byte-for-byte what `HEAD` would produce. **A reader who compares `--version`
  against `HEAD` gets STALE on a current binary, every time, and the natural response is a
  needless rebuild or, worse, distrust of a measurement that was fine.**
  **The witness that actually discriminates is a diff scoped to the code:**
  `git -C ../sigil diff --stat <binary-rev>..HEAD -- crates/` — empty means behaviourally current.
  A rebuild landing on the identical md5 is the other one.
  **The composition, which is the durable half:** `--version` is a positive witness that the binary
  carries A revision and is **silent on behavioural equivalence to tip**; the crates-diff witnesses
  equivalence and is **silent on which binary you actually invoked**. Neither is sufficient and they
  fail in opposite directions — the same shape as the off-canonical table witnessing that a build
  ran while saying nothing about its source. Run both, or state which question you did not ask.
- **A PAIRED LANDING CITES TWO AEON SHAs AND THEY ANSWER DIFFERENT QUESTIONS — LABEL WHICH IS
  WHICH, OR THE TREE-STATE PIN GETS READ AS THE CODE ANCHOR** (added 2026-08-27; caught by the
  oracle lane, turning this repo's own SHA-class bar back on it, and they were right about the
  defect while wrong about the substitute — which is why you check rather than swap).
  A freeze records `aeon_rev`: **the tree state the ROM was built from**. That is the correct
  anchor for *reproducibility* and it is frequently a **docs-only commit**, because the tip at
  freeze time is whatever landed last. It is NOT the commit carrying the feature. Chain 173's
  lane-log wrote the pairing as *"aeon `33d905b8` / sigil `4648c579`"* with no label, and
  `33d905b8` is `DEFERRED_WORK.md` + `OVERSEER.md`, two files. A reader chasing it for the
  sprite-owner byte guarantee lands in a docs diff — the exact failure this repo booked when a
  lint fixup stood in for a feature merge.
  **The code anchor for that chain is `cbd04ba8`** (`engine/objects/sprites.emp` +121,
  `engine/ram.emp` +20, `tools/test_sprite_owner.py` +281; 532 insertions), `--stat`-verified.
  *(Note for anyone re-deriving: `212b2a06` is NOT it either — it is a 509-line measurement
  write-up, also docs. Two of the three plausible-looking SHAs in that chain are docs commits,
  which is precisely why the label is needed and why guessing from a subject line fails.)*
  **Operational form: write a paired landing as `code <SHA> · frozen at aeon_rev <SHA> / sigil
  <SHA>`.** Both SHAs are correct for their own question; the prose is what has to say which
  question each answers. This is not the SHA-class bar repeating — that one is about citing the
  *wrong* SHA. This is about citing the *right* one for an unstated question, which no
  `--stat` check catches, because the commit you land in is genuinely the one named.
- **A REBASE ORPHANS THE SHAs A GENERATED LEDGER HAS ALREADY CAPTURED — AND THE CONSUMER YOU
  MISS IS THE ARTIFACT, NOT THE PEER** (added 2026-08-29, chain 181; **the sigil lane's finding
  against this lane's rebase**, and every particular of it verified firsthand here before being
  written down).
  **The record item first, because it is a permanent fact about chain 181 and nothing will
  surface it later.** Chain 181's attest entry records
  `sigil_rev = bfbedc11fb52183c08631034a0108be9df01f8bf`. **That commit is not reachable from
  sigil `origin/master`.** Landing the chain, this lane rebased the sigil lane's six doc commits
  underneath its own, which moved the freeze to `16b83c63`; the pre-rebase commit survives only
  in local object stores and will eventually be gc-ed. Measured here in the shared sigil checkout
  after `git fetch -q origin`, not taken from their message: `merge-base --is-ancestor bfbedc11
  origin/master` exits 1, `cat-file -t` says `commit` (so it resolves locally and only locally),
  `16b83c63` IS an ancestor, and the two trees genuinely differ —
  `bfbedc11^{tree}` is `ed5a25acf48a9d7adc23b4fa6b5f79ca2f34cdf7` against `16b83c63^{tree}`
  `7ccd5d3fe44414eadcb5324bf5bab12e43773903`. **So there is no reachable commit whose tree is the
  one that attest run actually happened on.**
  **THE MAPPING, which is the operative half of this bullet: `bfbedc11` → `16b83c63`, same work,
  rebased.** A verifier who cannot resolve entry 181's `sigil_rev` should meet that sentence
  rather than a mystery.
  **RULED — document the mapping, do NOT re-attest** (this lane's call, reached independently by
  the sigil lane, and ruled by the hub under the owner's overnight grant; banked for his review).
  Re-attesting 181 would record a run that happened on tree `ed5a25ac` under an entry naming a
  commit whose tree is `7ccd5d3f` — **trading a dangling anchor for a resolvable one that points
  at the wrong tree.** That is strictly worse for the only question `sigil_rev` exists to answer
  (`provenance.rs:125`: *tree identity, so an attestation cannot silently travel to a different
  pair of trees*), and unlike a dangling anchor nothing downstream could ever detect it. **A
  dangling anchor with a written reason beats a resolvable anchor that lies.** Neither lane
  hand-edits a generated ledger, so the mapping lives here and in the lane log, never in
  `provenance.toml`.
  **THE REUSABLE HALF, and it is bar 8 arriving somewhere nobody points it:** before rebasing,
  this lane enumerated the consumer set correctly for the question it asked — *had this SHA been
  handed to any peer?* — and the answer was genuinely no. **The consumer was not a peer. It was
  the ledger being written in the same operation, which had already captured the value.**
  Enumerate by **what TOUCHES the value**, never by **whom you told**. A generated artifact is
  the worst consumer to miss, because it is the one that cannot be sent a correction message and
  the one that hardens into the permanent record.
  **And nothing validates it.** The field's check is `is_full_sha` — forty hex characters — so a
  **well-formed orphan passes forever**, and `--check` re-validates the chain without ever asking
  whether a recorded revision resolves. This is the absence family on a POSITIVE artifact: the
  entry is present, well-formed, inert, and indistinguishable from a good anchor. *(Sigil has
  queued the systemic fix on their side — reachability rather than well-formedness. It is their
  crate and their work; this lane's ask as its first consumer is that the red name the entry and
  the unreachable rev, and distinguish `unreachable from origin` (permanent, this case) from
  `not in this clone yet` (a missing fetch, transient), because those want different responses
  from whoever meets it.)*
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
  **⚠ THE FLIP CONDITION AS THIS LANE FIRST STATED IT WAS REMEMBERED, NOT MEASURED — and the
  correction is the durable half.** It was written as *"three consecutive chains attested with
  the freeze already pushed and no warning fired"*, with the claim that this made the flip
  checkable rather than remembered. **It did not.** Warnings go to stderr and nothing durable
  records that one did or did not appear, so verifying the condition means counting three chains
  **and recalling** whether a warning fired in any of them — evidence that lives only in session
  context. **This lane's session was rotated tonight while holding exactly that class of state**,
  which is how the mapping write nearly got done twice and how the reasoning for *not*
  re-attesting nearly died with it.
  **The condition is therefore not armed until the ledger can answer it.** Sigil has queued
  `ATTEST-RECORDS-REACHABILITY` — `--attest` records the reachability state it observed into the
  entry it writes — after which "three consecutive clean chains" is **computed from the ledger by
  the walk that already reports orphans**, in one command, surviving every rotation on both sides
  and auditable after the fact rather than asserted. **Do not flip the refusal on a count anyone
  had to remember.**
  *The general form, and it is the same preference that killed the opt-out flag and the exception
  list: prefer the assertion that needs nothing maintained. A remembered condition is a
  population of one, kept in a place that gets cleared.*
  *Recorded here rather than left in mail because it is a cross-lane COMMITMENT, and protocol bar
  20's sending-side half says state that lives only in correspondence does not survive a `/clear`.
  This lane made the ruling in a message and had to be reminded by its own file to bank it.*
- **⚠ AND THE PRE-FLIGHT ABOVE HAS A FALSE-POSITIVE CLASS I DID NOT SEE WHEN I WROTE IT: ON A
  BYTE-MOVING PARCEL THE PORT TESTS FAIL FOR A REASON THE FREEZE ITSELF FIXES** (added
  2026-08-29, within two hours of banking the bar it corrects; found by a diagnosis agent I
  dispatched *because I had misread the evidence*).
  **`refreeze --freeze` runs `repin` as its third step.** So a parcel that moves code makes every
  address pin stale, the port tests read those pins, and pre-flighting them BEFORE the freeze
  shows red **by construction** — then the freeze regenerates the pins and the attest is green.
  Pre-flighting without knowing that turns a correct gate into a phantom defect at exactly the
  moment you are trying to be careful.
  **The two classes are distinguishable and the discriminator is one command:**
  `cargo test -p sigil-harness --test repin_pins` — its `pins_rs_is_current` arm regenerates the
  table in memory and diffs it; it is a READ-ONLY guard, not a repin. If it says
  *"pins.rs is STALE against the live listings (N changed pin(s))"*, the port failures are
  **stale-instrument** and the freeze will clear them. If pins are current and a port test still
  fails, it is the **cross-seam symbol** class — a name the standalone scope cannot resolve — and
  that one is real, needs a hand edit, and is what chains 182 and 184 hit.
  **So the corrected pre-flight is: run `repin_pins` FIRST, and only read the port tests as a
  finding once pins are current.**
  *Lived: d-41 added a 4-byte write to `Parallax_Step5_Vscroll` and slid everything after parallax
  by +4 — 29 stale pins, 26 of them outside parallax entirely. `parallax_port` was simply the
  first gate to notice, and it was working perfectly.*
  **AND THE TELL I WALKED PAST, which is the durable half: the plain ROM changed CRC at an
  IDENTICAL LENGTH.** `Level_LoadArt` sits at the same address in both trees because the +4 was
  absorbed inside the preset region. **A CRC change at an unchanged length is positive evidence
  that bytes moved without the image growing — which is precisely the repin trigger — and I read
  it as unremarkable.** Same length is the reassuring half of that pair and it is the half that
  means nothing.
  **A SECOND LESSON, ABOUT MY OWN EVIDENCE.** I identified the differing byte as a CMP register
  field (`b2` vs `b6` = D1 vs D3) and handed that to the agent as a hypothesis. **It is a
  coincidence and the agent refuted it from the listing:** the byte is the low half of a `bsr.w`
  DISPLACEMENT (`0x10B6` → `Effects_InstallPreset` at `0x7406`, against the standalone's
  `0x10B2` → `0x7402`). The `cmp.b`s whose encoding I matched are real and sit **0x20 bytes
  earlier**. **A byte pattern that decodes plausibly is not an instruction** — opcode space is
  dense enough that almost any byte reads as something. Decode from a known instruction boundary
  or from the listing, never by matching a byte against an encoding table. *Flagging it as a
  hypothesis is what stopped it becoming the brief's premise; had I asserted it, the agent would
  have spent its run inside the wrong routine.*

- **RUN THE STRICT SUITE BEFORE THE FREEZE, NOT AFTER — A NEW CROSS-SEAM SYMBOL GOES RED AT
  ATTEST EVERY TIME, AND NOTHING UPSTREAM WARNS** (added 2026-08-29, after chains 182 and 184
  both did it).
  **Two for two, same night, same mechanism, different symbols.** 182 added
  `EditorRaster_OJZ_Act1_authored_probe` and `act_descriptor_port` went red on *"link assertion
  condition references symbol(s) … not defined in this link"*. 184 added `Parallax_Drift_Acc` and
  both `parallax_port` tests went red on the identical diagnostic. **`build.sh` does not warn
  about cross-seam refs** — it links the whole map, so the standalone-module case it never
  exercises is exactly the case the port tests exist for.
  **The cost is not the fix; the fix is a table row. The cost is WHERE it lands.** Discovering it
  at `--attest` means the freeze has already run (a full seven-ROM capture), already been
  committed, and already been pushed — so the entry is FROZEN with a red record and can only be
  abandoned via `--supersede-tip`, which requires **a second full capture**. Two chains × two
  captures ≈ 40 minutes of wall clock spent on a defect a two-minute check would have caught
  before the first one.
  **⚠ SUPERSEDED BY A COMMAND, 2026-08-30 — RUN `tools/freeze_preflight.sh`.** The prose form
  below was complete, correct, and truncated on chain 187: this lane ran step 1 (`repin_pins`),
  found exactly what step 1 exists to find, and went straight to the freeze. **The sigil lane's
  diagnosis is why this is now a script and not a better sentence: step 1 is genuinely useful on
  its own, so COMPLETING IT FELT LIKE COMPLETING THE PRE-FLIGHT.** A two-step ritual whose first
  step is independently satisfying will keep being truncated there, and no amount of emphasis in
  prose fixes that — it is the same lesson as spelling an invocation inside the command span
  rather than beside it, arriving on a ritual instead of on a flag.
  Proven red-first against the very failure it was written for: run on the chain-187 tree it
  names `Cache_Fill_Resume_Col`, verdicts *"pins were current, so these are REAL. Supply the
  composition BEFORE freezing"*, and exits 1 — in about two minutes, against the twenty that
  discovering it at `--attest` cost.
  *The script also carries the discriminator's meaning so a reader cannot invert it: pins STALE
  means the port reds are stale-instrument and the freeze clears them; pins CURRENT with a port
  still red is the cross-seam class and is real. It refuses on a `repin_pins` failure that is not
  staleness, rather than reading that as either.*

  **Operational form (what the script does): after the merge and the four-shape verify, and
  BEFORE `--freeze`, run the strict suite against the merged tree.** `AEON_DIR=<clean merge> cargo test --release
  --workspace --no-fail-fast` with `SIGIL_STRICT_GATE=1` — or simply expect `--attest`'s failures
  early by running the port targets alone, which is faster: the two that have bitten are
  `-p sigil-cli --test act_descriptor_port` and `--test parallax_port`.
  **A cheaper pre-flight that catches the whole class:** any parcel that adds a `pub` symbol which
  a *different* module references — a `dc.l`, an `extern`, a link `ensure` — has added a
  cross-seam ref. **Grep your own diff for new cross-module names before freezing**; that is the
  population, and it is enumerable from the parcel rather than discovered by the suite.
  *Note what this does NOT change: the port tests are right, the diagnostic is excellent (it names
  the symbol and tells you to supply the composition), and the fix is documented and mechanical.
  This is purely about ORDER — the same information arriving before the expensive step instead of
  after it.*
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
  `build.sh` takes `SIGIL_BUILD` (`:558`) and `SIGIL_EMIT` (`:317`) **from the environment**.
  Nothing in a checkout pins either, and `SIGIL_EMIT` *writes* `engine/sound/generated/` — one
  of the directories whose drift was being investigated. So a pinned tracked tree, `git status`
  clean throughout, can build a different ROM tomorrow with **no cause visible in the tree at
  all**. Lived: a `git clone` fixture built `4b4f1b5b` at 00:58 and `f33b157e` at 03:35, and the
  only thing that changed was that `emit_sound_blob` and `sigil` were rebuilt underneath it.
  **`build.sh:266` already prints `Assembler: sigil <rev>` for exactly this class** (the
  three-days-behind incident in its own header). The gap is that nobody records the banner
  beside the CRC they cite.
  **OPERATIONAL FORM, adopted: quote the assembler REVISION beside every CRC you hand to
  anyone, and treat a cross-session CRC comparison as MEANINGLESS unless both sides carry the
  same revision.** Costs nothing; `build.sh:266` already computes it.
  **⚠ QUOTE THE REVISION, NOT THE WHOLE BANNER — one half of it is a stuck constant** (caught
  by the sigil lane within the hour of this rule being written; verified firsthand here).
  `build.sh` prints `Assembler: sigil <rev> (<tree>)`, and that parenthesised `tree` field
  reads **`dirty at capture — 0 modified, 1 untracked`** on every invocation. The one untracked
  file was `docs/lane-status.json` — read by no build, incapable of moving a byte.
  **⚠ STATUS AS OF 2026-08-27: the CAUSE is fixed and the SYMPTOM is not, and the difference
  matters to a reader.** sigil gitignored that file at their `e5bd4a4f` (verified reachable at
  their `origin/master` here, and `.gitignore:13` confirmed in the blob), so their tree is
  genuinely clean now. But `tree:` is a **build-time snapshot** — cargo has no trigger for
  uncommitted state — so **the banner keeps reporting `-dirty` until the binary is relinked.**
  It has therefore moved from *stuck* to *stale*, which is a different defect with the same
  reading: still do not quote it.
  **THE TEST THAT THE FIX HAS REACHED THE BANNER IS A `revision:` THAT IS NOT `fbf60abd` — NOT
  THE DIRTY FLAG CLEARING** (aurora's, their `8e2056a6`, amending their own bar which had
  written the test as *"until sigil fixes it"*). Any wording of that shape inherits the defect:
  a future session reads the stale value, sees `-dirty`, and concludes the fix never landed.
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
  **THE BOUNDARY, drawn 2026-08-27 and narrower than the contract above reads on its own —
  read this before blocking any banner work.** The contract binds the banner's SHAPE, not the
  judgement made from it. **A change that only decides differently about data the banner ALREADY
  prints needs no agreement from this lane**; a new field, a rename, or a change to when `tree:`
  starts with `dirty` does. The distinction matters because the contract read alone would have
  this lane gate a sigil-internal classifier it has no stake in, which is a cost with no reader
  (shared-protocol bar 18) and the failure mode a broadly-worded contract produces by default.
  *Concretely: the banner already emits `0 modified, 1 untracked`, so the discriminating data was
  never missing — only the decision about what it means. That reframes `GOLDEN-DIRTY-BANNER` from
  "measure more" to "decide correctly about what is already measured", which is both a smaller
  change and one that stays entirely on sigil's side of this contract.*
  **⚠ RETRACTED 2026-08-27, AND THE RETRACTION IS WORTH MORE THAN THE CLAIM WAS — READ THIS
  BEFORE THE PARAGRAPH BELOW.** This was banked as a bar-19 positive control. **The conclusion
  it certified is FALSE**, refuted by the sigil lane's classifier agent (their `2b26419c`), which
  measured what neither derivation had: the banner's `N modified, M untracked` discriminates
  **tracked-vs-untracked**, which is a different axis from **material-vs-immaterial**. The very
  case that motivated the item — the noise in sigil's own `OVERSEER.md` — is a *modified tracked*
  file, i.e. the bucket any "decide better from the counts" rule must call material; and
  `1 modified` is equally consistent with a docs edit. The `where` was never in the string. The
  revision half fails the same way: one SHA cannot say which of 19 commits reach the binary.
  **What survives, and it SHARPENS bar 19 rather than weakening it: the bar's test PASSED and the
  answer was still wrong.** The enumeration parameters genuinely differed (quoting discipline
  here, classifier design there), neither lane raised it before writing it down, and the
  convergence was real. **So independent derivation raises CONFIDENCE and does not establish
  TRUTH.** Two sound methods applied to the same *unmeasured* question converge on the same
  plausible answer and supply no new evidence, while feeling exactly like corroboration. The
  shared defect was not a shared frame in bar 8's sense — it was a **shared untested premise**
  (that the discriminating information was in the string), and **neither derivation had performed
  the one cheap refuting act**: compare the string against the failing case.
  **Operational form, adopted here as well as there:** corroboration moves a claim from *guess*
  to *worth measuring*, never from *guess* to *established*. On any convergence, ask **what
  measurement would refute this, and did either derivation perform it** — and if the answer is
  no, the agreement is a hypothesis with two authors.
  *Kept in full rather than deleted, so the wrong reasoning stays legible beside what refuted it.
  Note also the cost the sigil lane booked against their own item: the mid-build relink incident
  was caught ONLY by the banner shifting `(dirty)` → `(revision+dirty)`, so a quieter banner must
  never later be read as that hazard being closed.*

  ~~**Recorded as this lane's half of a bar-19 POSITIVE CONTROL, which is the rarer artifact.**~~
  Both lanes reached that reframe independently and by different enumeration parameters — this
  lane from **quoting discipline** (which components of a provenance line can move, and on whose
  clock), sigil from **classifier design** (what data the fix actually needs) — with neither
  raising it before writing it down. That is corroboration rather than echo. Sigil banked their
  half at `d279a912` (verified reachable at their `origin/master` here, and `--stat`-checked as a
  notes commit — cite it for the *reasoning*, never as a code anchor). Most instances in both
  repos are one lane's synthesis with a second's endorsement, discussed first; **this one is
  not, and the difference is worth preserving, because otherwise the weak instances borrow
  credibility from the strong one.**
  *Note the shape, because it happened to a rule ONE HOUR OLD: adopting a provenance field
  wholesale, without asking which of its components can move, is how a constant gets quoted as
  evidence. The rule was right and its first operational form was already carrying a
  non-signal.*
  *Reached independently by the aurora lane within minutes (their `c45f3313`), from the
  instrument rather than from sigil's report — two derivations over different parameters, so
  corroboration rather than echo. They add the sharpest argument for making this MECHANICAL
  rather than a habit, and it is worth more than the incident:* **a vigilance rule protects the
  people who least need it.** *Of tonight's three assembler-moved-under-a-measurement instances,
  the two that were caught were caught by parties who already suspected the assembler; the one
  that escaped escaped because its author had no reason to think about it at all. Vigilance is
  distributed exactly opposite to exposure.*
  *Their cross-lane datum, useful and not visible from inside sigil: `docs/lane-status.json` is
  TRACKED in aeon, oracle, seraph and empyrean, untracked-but-ignored in aurora, and
  untracked-and-not-ignored in **sigil alone** — so the stuck flag is sigil-only and either
  arrangement the other five use would clear it. **Do not build this bar on it clearing.***
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
  *Three instances of the assembler moving under a measurement in one night: this lane's own
  sprite-owner A/B (re-derived after asking sigil to rebuild), the gates parcel's agent
  (caught it mid-run and re-derived its baseline unprompted), and aurora's fixture (not caught,
  and it produced a wrong CRC plus two wrong explanations). Two of three were caught by
  vigilance rather than by any gate, which is the argument for the banner rule.*
- Zero-byte parcels (tools/docs) are aeon-only; verify CRC identity anyway —
  byte-count-neutral is not byte-identical, and DEBUG-only procs can still move the
  release deb2 appendix.
- **A citation has TWO SHAs — the one you cite and the one you VERIFIED AT — and the
  second needs the same `ls-remote`** (lived 2026-08-22, this overseer's error, caught by
  aurora-86). The shared protocol's push-before-you-cite rule polices the SHA you hand
  over. It says nothing about the revision your *claim* rests on, and that one gets checked
  far less because it reads as provenance rather than payload. Lived twice in one message:
  having just audited all four of MY anchors as reachable from `origin` after empyrean's
  local-only discovery, this overseer pinned a claim about a sibling repo to aurora
  `2fe39ea` — **local-only, 30 commits ahead of `origin/master`** — so the receiver could
  not check the verification at all. **Also: never certify a LINE NUMBER with a SHA.** The
  same message cited `s4-types.ts:227` for `Act.parallaxRef`; at that very pin `:227` is
  `export interface Palette` (Act begins at `:235`, the field at `:243`), and `:227` had
  already been *two different types in one day*. **A correction that carries a line number
  inherits the defect it was correcting** — aurora's ROADMAP had "fixed" this number once
  already and gone stale again. **Anchor to the SYMBOL; let the SHA date the CLAIM, never
  the coordinate.** Practical convention, agreed with aurora-86: state explicitly whether a
  SHA is at `origin` or local-only — "verified reachable at origin" and "verified in my
  object store" are indistinguishable in a message and only one is an anchor. Treat every
  Aurora SHA as local-only unless they say otherwise.
- **On a byte-neutral parcel, byte identity stops being evidence about the BUILD and is
  only evidence about the SOURCE — freshness needs a separate witness** (lived 2026-08-22,
  caught by one exit code). Advancing a landing worktree to a new SHA, the four CRCs came
  back matching the pins exactly — from a build that **never ran**. `git checkout` gives
  `project.json` a fresh mtime, `level staleness` hard-fails *before* a ROM is emitted, and
  the ROMs on disk were **leftovers from the previous build at the previous SHA**. Because
  the parcel was zero-byte, leftover and correct are byte-identical: **a CRC check cannot
  distinguish "built at the new SHA" from "never rebuilt at all."** The only tell was the
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
  What trips it is an **in-place `git checkout` into an existing tree**, which rewrites only the
  changed files and leaves `project.json` newer than an untouched generated tree. Read "checkout
  into an existing tree", never "fresh checkout" — and running `regenerate-level.sh`
  prophylactically on a fresh worktree is **pure cost plus `DONOR_PROVENANCE.json` churn**. (This
  lane paid exactly that cost on the chain-172 landing, before the correction arrived.) *Note the
  direction of the error: the old wording caused unnecessary work rather than missed work, so
  nothing was ever going to surface it — a hazard note that OVER-predicts a stop is
  self-confirming, because the prophylactic runs and the stop duly never comes. It took a lane
  that skipped the prophylactic and measured what happened.* The rest of this stanza stands;
  only the population it bites is narrower than written:
  `tools/regenerate-level.sh` clears it (level bytes unchanged — revert the
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
  Lived: P3 T11-T16 were six consecutive zero-byte parcels (CRCs held at `060401e4` /
  `0dbaa80f` / `c708b114` / `dec88cc1` throughout — the identity we verified and cited at
  every landing), and `layout.odd-field` began firing on the sonic4 corpus somewhere in
  them with no adjudication and no baseline update. The last baseline freeze is sigil
  `40f862e2` (2026-08-21T14:23, pairing aeon T10 `3c68ee11` at 14:06); aeon T11
  `b0b85f47` merged at **14:57**, *after* it — so **T11 is outside both the baseline and
  any diff range that starts at T11's own merge commit**, which is the natural range to
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

Lived 2026-08-22: recovering the profiler-corpus ROM (`d22dda85`), this overseer checked
`sigil master:crates/sigil-harness/golden/s4.debug.bin`, truthfully found `0dbaa80f` (correct for
master), reported "no committed blob shortcuts it", and was one step from a rebuild parcel. **The
blob was sitting at `7b46f075`** — the `refreeze: raster-cram-anchor-366` commit whose own message
named the paired golden move. A golden path is a MOVING POINTER: for a vintage artifact, the tip is
the one revision guaranteed not to have it.

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

Live interaction in THIS file, so read it deliberately: the landing lane's clean-checkout rule
pins `AEON_DIR` at a committed SHA. That is correct for **reproducibility** (freeze the artifact
you actually measured) and would be WRONG for a currency question — a sigil port gate asked "does
aeon still satisfy this contract *today*" must not be pointed at a pin.

## Instruments (which oracle for what)

**✅ HOLD LIFTED 2026-08-24 — read this before the block below, which is kept for its
mechanism and its scope note only.** Oracle fixed the straddle defect (red-first tests
`68461a7`, fix `4111c88`, merged `51143a5` — verified reachable at their `origin/main` here,
and the cited `7bdb75f` in their message is the DOCS commit, not the code). The three probes
may migrate whenever a parcel wants them to; **nothing on this queue waits on it, and it was
never "aeon's profiler migration".** The paired outcome: **our `PROF-RING-SELF` ask is
WITHDRAWN** — a bucket's `self_cycles` is the exception entry alone, so the field we asked for
would have been exact and useless, and the fix delivers the quantity on the fields we already
read. Full derivation and our error class in `docs/DEFERRED_WORK.md`.

~~**⚠ HOLD — do NOT migrate the three cost probes to oracle-next's profiler (oracle lane,
2026-08-22).**~~ `tools/raster_cost_probe.py`, `tools/engine_baseline_probe.py`,
`tools/streaming_choke_probe.py` stay on the legacy harness until oracle says otherwise.
Their attribution across VBlank preemption is **sound by design** (returns matched by
`entry_sp` + privilege, never positionally) — the ~20% legacy loss is genuinely not shared.
**But `perFrame[].vintCycles` may displace a boundary-straddling handler's ENTIRE cost into
the frame it returns in**, and **no test in either suite puts an interrupt bucket across a
mid-sample boundary**, so it is latent at every state anyone has measured.
**Status: LOCATED, NOT CONFIRMED** — reasoned from source, no cargo run, no emulator; their
overseer read the code and calls it plausible and specifically sited. Tier 1 there, and it
gets a test before we migrate.
**Why this one is ours specifically, and it inverts the usual latent-bug story:** our
workloads are *sustained streaming*, where a tick costs 190,931 cycles against a
128,000-cycle frame — so **boundary-straddling handlers are our NORMAL case, not an edge
case.** A defect latent everywhere else would be load-bearing here.
*Costs us nothing today: verified 2026-08-22 that none of the three references
`oracle-aether` or `--no-pace` — they are all still on the legacy profiler, so this is a
hold on a future migration, not a retraction of anything in use.*
**RE-MEASURED AND UPGRADED 2026-08-23 — read this before acting on the block above.**
- **Still current**: all three assign `HARNESS = .../oracle-old/linux-port/harness` (the
  assignment, not a grep hit). Nothing migrated underneath the hold.
- **"CONFIRMED" now, not "LOCATED"** — but by *our* measurement, not their source read.
  It is one kind-agnostic mechanism in `Profiler::checkpoint`, and our own booked 149,104
  lump is its signature. Full derivation, verified firsthand at oracle `origin/main`
  `4f0bedd5`, in `docs/DEFERRED_WORK.md`'s "Two instrument findings" booking — **including
  the part that changes the port: `cyclesSelf` is the right remedy and the `perFrame[]` wire
  row has no self field for either interrupt bucket**, so the remedy is unreachable on the
  ring until oracle ships one. That is a named ask, not a workaround.
- **SCOPE — do not repeat the over-read this hold caused.** It held *three named probes*,
  and was relayed to the hub as "aeon's profiler migration is HELD". It is not: the
  migration is booked with its condition **discharged**, and `tools/tick_variance_probe.py`
  already runs `oracle-aether --no-pace`. Its two `oracle-old` mentions are comments, one
  saying the legacy harness is deliberately not importable — **presence, not invocation**
  (protocol bar 16). Oracle has reworded their side. **Nothing on this lane's queue waits on
  it**; never let a peer rank it as unblocking us.
- **Discharge condition, sharpened**: the witness must open the bucket, then have the handler
  **call a routine** that is still open when the boundary lands. A handler whose calls all
  return first shows no displacement, so the obvious test passes for the wrong reason.

**✅ Pixel capture is COMPOSABLE TODAY — and the "capture is impossible here" belief is a
LEGACY-SERVER result that must not be carried forward.** `play_input` + `scanlines{}` +
`state_hash{includeFramebuffer}` are all served by the Rust core, and determinism is a
property it already gates: `a1_determinism_three_boots_byte_identical` compares three
servers, three sockets, full 224-line frames, byte-identical, with a poison beside it.
Their determinism sweep was run as an enumeration, not a conclusion (zero
`Instant::now`/`SystemTime`/`sleep` in core; no `HashMap`/`HashSet` iteration; no `rand` —
`rng.rs` is a hand-rolled SplitMix64 seeded from a constant; `forbid(unsafe_code)`; floats
confined to `src/synth/`; wall-clock pacing at exactly one site, disabled by `--no-pace`).
**So the three failed capture protocols and the non-deterministic screenshots are facts
about the OLD server.** Poison-test anything before adopting it as a gate — that sequencing
still stands — but stop repeating that raster work cannot be gated on pixels.

**DMA-enqueue union (axis-2 unlock) is also composable today**: a watchpoint record sweep
cross-checked with `run_to{symbol}` + `read_memory`. **`run_to` takes a `symbol`** — that is
the piece nobody had noticed, and it is what makes this composable rather than new work.

**⚠ THE BREAKPOINT GAP IS CLOSED — corrected in place 2026-08-27, and the sentence it replaces
said the opposite.** The Rust server **serves breakpoints**: `"breakpoints": true` at
`crates/oracle-aether/src/engine.rs:1694`, read at oracle `origin/main` (`227b0c8`), with their
hosted-halt merge `3fb9f4a` verified reachable there. Their local `target/release/oracle-aether`
was relinked **2026-08-27 05:59**, so the served binary is current with that source — checked
separately, because a source claim and the binary a tool actually dials are two artifacts.
Oracle's own run against the rebuilt binary reports **52 methods** and all five breakpoint
methods present. **CONFIRMED INDEPENDENTLY HERE 2026-08-27** by spawning
`target/release/oracle-aether` through `tools/aether_instance.py` against our own
`s4.debug.bin` and reading the handshake: `implementation` `'oracle-rs'`, `serverName`
`'oracle-next'`, `serverBuild` `{dirty: False, source: 'vcs', id: '614736b6…+profile=release'}`,
`capabilities.breakpoints` `True`, **52** methods, all five of `breakpoint_{add,clear,list,
set_enabled}` + `wait_for_break`.
  **⚠ WHY THAT CONFIRMATION IS RECORDED WITH ITS PROVENANCE, AND THE LESSON IS ABOUT THIS FILE
  RATHER THAN ABOUT ORACLE** (2026-08-27; the amendment is oracle's, against this lane's own
  remedy, and it is the sharper rule). The 52 originated with **oracle**, was relayed here,
  was written into an earlier revision of this file **without attribution**, and oracle then
  **read it back firsthand out of this committed blob** and let it outrank their own
  five-instrument static measurement of their own binary. **Their claim completed a circuit and
  returned to them wearing this lane's confidence.** It happened to point at the truth — their
  binary is current — while their correctly-executed measurement pointed at a falsehood, so two
  defective inputs cancelled. That is luck, not method.
  **The remedy this lane first proposed — "say whose measurement it is when you repeat it in a
  message" — WOULD NOT HAVE CAUGHT IT, because no message was involved.** Oracle read the
  durable record, which is this suite's primary defence. **Verify-firsthand confirms the
  TRANSCRIPTION, never the CLAIM**: a faithfully-copied number is indistinguishable from an
  independently-measured one, and a reader cannot recover what the writer did not record.
  **So the attribution has to survive into the DURABLE RECORD, not merely into correspondence.**
  *Sharpened by this lane's own audit of the two sites: the figure at the "Two capability facts"
  block DID carry "Oracle's own run"; the one ~200 lines below did NOT, and sat beside a
  41-method figure explicitly labelled "Measured, both binaries as shipped". **Attributed in one
  place and bare in another is worse than uniformly bare**, because a reader who spot-checks the
  attributed site is reassured about the one they actually quote.* Both sites now carry it. *Historical note kept deliberately: this bullet previously read "do not exist …
`capabilities.breakpoints: false`", which was true when written and would have sent a future
session to `run_to{symbol}` as the only option. `run_to{symbol}` still works and is still the
right tool where a symbol is what you have.*
**What this unblocks here, stated so it is not re-derived:** the `arm → wait → clear` flow this
lane could not express is now expressible, which is what takes `WAITFORBREAK-SPELLING-HOLD` from
a hold to a scheduled parcel, and it makes the widened `Sprite_Owner` witness reachable — arm on
a gameplay address, resume into it, and the SAT is populated at the stop, including the `$0002`
mask sentinel that has never been exercised. **Oracle's caveat, carried because it is theirs and
it is load-bearing:** the *windowed* halt rests on an in-process fixture, not on a windowed run —
they could not drive a window without touching the owner's or aurora's. Treat the first windowed
use as the confirmation, not as a regression test. And **we are already driving the Rust server headlessly** — 8 of our tools
reference `oracle-aether`/`--no-pace` (verified: `boot_override_gate`, `effects_gates`,
`hblank_window_sweep`, `sh_probe`, `staging_lifetime_timeline`, `tick_variance_probe`,
`vsplit_landing_gate`, `warp_mailbox_gate`). **The cutover is partial and IN PROGRESS, not
pending** — do not write as though it has yet to begin.
*(Count superseded 2026-08-26: the effects gate lane went over wholesale — see the block
below. Four more gates converted and everything routes through one seam,
`tools/aether_instance.py`, so grep for that name rather than re-counting `--no-pace`.)*

**✅ THE EFFECTS GATES ARE ON THE RUST CORE NOW (2026-08-26) — the line above that said
they spawn `oracle_gui` is retired.** Owner ruling (empyrean 3c21183): oracle-aether is the
default, `oracle_gui` is FALLBACK ONLY. There is ONE spawn seam, `tools/aether_instance.py`:
short mkdtemp socket, readiness by socket ACCEPT (~0.06 s measured), a handshake, an identity
ASSERTION, and a reap in a `finally` with PR_SET_PDEATHSIG behind it.

- **Converted this parcel** (were legacy, verified same verdict AND same asserted values —
  each gate's full output is byte-identical before/after): `raster_off_gate`,
  `palette_variant_gate`, `snapshot_poison_gate`, `raster_source_gate`.
- **Already aether, and now carrying the same assertion**: `vsplit_landing_gate`,
  `warp_mailbox_gate`, `boot_override_gate`. They keep their own PID-scoped Server class.
- **STILL LEGACY, and it is not this lane's call**: `scene:*` (4 segments, 8 gates) drive
  `ab_runner.py`, which lives in `oracle-old` — porting it is oracle's; and `cost_model`
  drives `raster_cost_probe.py`, held below. At ~38 s each the scene segments are now 80% of
  the lane's wall clock, so ab_runner is the next real lever and it is a PROPOSAL FOR ORACLE.
- **Wall clock, both full lanes aggregated, same ROM, same machine, uptime beside each**:
  legacy 233 s (02:42 up 18:31, load 3.07), aether 191 s (02:38 up 18:27, load 3.33), both
  26 of 27 gates passing — the one failure was `boot_override`'s SETUP ERROR, identical text
  in both. **⚠ THAT FAILURE IS GONE — do not carry it forward (measured 2026-08-26).** The
  `parcel/boot-override-witness` parcel rewrote that gate hours after this row was written,
  and this line was never re-derived. On merged master at `s4.debug.bin` crc `f8d06cae`,
  `--only boot_override` is **PASS, exit 0**, and a full lane was **28 gates OK, exit 0**.
  **⚠ THAT COUNT NO LONGER REPRODUCES — measured 27 on 2026-08-27. RECONCILED EXACTLY: the
  missing row is `scanline_spans`' `CAP_PER_LINE` row, retired by `309d937a`. Nothing stopped
  running. See the SHIPPED note below; the count itself no longer exists.**
  On merged master `e4eee42c` at `s4.debug.bin` crc `9732c56a`, a full lane is **`effects_gates: OK
  — 27 gates`, exit 0**, all 27 PASS. Enumerated so the next run can diff rather than re-count:
  `scene`×8, `scanline_spans`×8, and eleven singletons — `boot_override`, `cost_model`,
  `demo_witness`, `dense`, `palette_variant`, `parallax_crossing`, `raster_off`, `raster_source`,
  `snapshot_poison`, `vsplit_landing`, `warp_mailbox`.
  **What is ESTABLISHED, so nobody re-derives it:** the newest gate (`parallax_crossing`,
  `6164d7d5`, 10:55) already existed when the 28 was written (`6fbcd186`, 11:26), so 28 was the
  count *with* it; **no gate registration was removed** between that commit and `0da00a33`
  (diffed, empty); the only intervening lane commit is `e82807e0` (scene symbol resolution); and
  the band-ceiling parcel **never touched `effects_gates.py`**. So the missing gate is
  PRE-EXISTING and is not the parcel's. The count is `len(results)`, i.e. derived from gates that
  actually produced a row — which is exactly why one going missing shows up as a smaller green
  rather than as a failure.
  **⚠ RECONCILED 2026-08-27 — THE COUNT RECONCILES EXACTLY: 28 − 27 IS ONE RETIRED CAPABILITY
  BIT, AND NO GATE EVER WENT DARK.** Two findings.
  **⚠⚠ THIS HEADLINE PREVIOUSLY READ *"the answer is that the count cannot be reconciled, by
  construction"*, WHICH WAS FALSE.** It stood about ninety minutes, was relayed to the sigil
  lane, and they built a doctrine note on it before the retraction reached them. **The full
  retraction is the ⚠ block after (b) — read it before quoting anything in this stanza**, and
  note that (b) below is left standing as written on purpose, so the wrong reasoning stays
  legible next to what refuted it rather than being quietly edited into looking correct.
  **(a) The "diffed, empty" evidence above was MANUFACTURABLE and has been re-derived.** This
  stanza cited an empty diff between `6fbcd186` and `0da00a33` as proof no gate registration was
  removed. Running that same diff today returned empty **at exit 0 while the two blobs differed
  by 87 insertions** — because `git diff … -- <path>` takes a **CWD-relative pathspec** while
  `git show <rev>:<path>` takes a **root-relative** one, and this session had `cd`-ed into
  `tools/` earlier in the same investigation. Mixing the two forms in one investigation yields a
  clean empty diff and a zero exit with nothing to be suspicious of. Re-derived from the repo
  root: the real diff adds **exactly one** `results.append` (the scene-not-resolvable error path)
  and removes no registration, so **the original conclusion holds and its evidence did not** —
  bar 10 on one's own evidence, and bar 16(d) with `cd` as the manufacturing mechanism.
  **THE REMEDY IS `:(top)` AND IT BELONGS IN ANYTHING SCRIPTED** (sigil's, reproduced in their
  repo, verified firsthand here from both cwds): `git diff --stat A B -- ':(top)tools/x.py'`
  returns the same correct answer from the repo root and from `tools/`, where the bare pathspec
  returns 0 from `tools/`. **Prefer it in every script**, because a script cannot know where it
  will be invoked from — the interactive case at least has a human who might notice.
  **Why this is nastier than the suppression cases, stated so nobody files it as a git
  footnote:** with `2>/dev/null` or the `eza` alias something is destroyed or something errors,
  so there is a missing artifact to be suspicious of. Here **nothing is suppressed, nothing
  errors, the command is correct, the shell is correct, the revisions are correct**, and only
  the composition of two path conventions is wrong. And the tell that was nearly missed
  generalises past git entirely: **the conclusion being checked happened to be TRUE, so the
  empty diff confirmed a prior.** An empty result that agrees with what you already believe is
  the hardest case there is — there is no dissonance to trigger a second look. It was caught
  only because blob hashes from an unrelated command sat on screen contradicting it, i.e. bar
  19's changed-parameter mechanism firing **by accident rather than by intent**, which is
  precisely what bar 21 says will keep happening until someone invokes it deliberately.
  **(b) `len(results)` is RUNTIME-VARIABLE BY DESIGN, so `OK — N gates` was never capable of
  being a witness.** Read the scene loop: each scene appends a determinism row, and
  `if not ok: continue` **skips the shape row**. So a scene emits **2 rows when it passes and 1
  when it fails**, and `scanline_spans` emits a data-dependent number. The count is therefore a
  function of outcomes, not of population — 28 and 27 can both be correct for the same registry.
  Chasing the missing 28th was chasing a number that does not denote what the stanza assumed.
  **The corrective is the third leg of the absent-and-silent family** (aeon's, contributed to
  sigil's note `ffa76f7d`): evidence can discriminate perfectly and still witness nothing when
  **no expectation stands beside it**. `gate_registry()` already exists (15 entries) and
  `check_registry_drift` already proves registry and body agree — *(so this file's earlier claim
  that "the lane has no registry enumeration" is WRONG; `--help` not exposing it is not the same
  as it not existing, which is bar 16's name-versus-presence one layer down)*. **The fix is to
  assert the emitted ROW SET against a registry-derived expected set, and never to report a
  count**: a set can be diffed, which is an assertion; a count can only be read. Booked as
  `GATES-EXPECTED-ROWSET` — and note the sibling instance in sigil's `refreeze --attest`,
  which refuses on `strict_bodies == 0`, a **floor rather than an expectation**, so a deleted
  strict gate takes the witness 29 → 28 and still attests (their `ATTEST-EXPECTED-BODIES`).

  **⚠ (b) IS RIGHT ABOUT THE REMEDY AND WRONG ABOUT THIS INSTANCE — and the count DID reconcile,
  exactly, on 2026-08-27** (`parcel/gates-expected-rowset`). Two corrections, both measured:
  * **Outcome variability cannot produce an all-PASS shrink, so it cannot be what was seen.**
    Every row-suppressing path in the body — all three scene `continue`s, the dense-scene
    stream miss, the cost probe failure, the missing demo listing — **appends a FAILING row
    before it skips**. Outcome variability therefore only ever yields a smaller count *with red
    in it*. A 27-rows-all-PASS run was never reachable that way, and (b) asserted a mechanism
    without checking it could produce the observed shape. *(Bar 10 again, one level up: the
    right general conclusion resting on the wrong particular.)*
  * **The real variable was POPULATION, and it is `scanline_spans`, which emits one row PER
    DECLARED `CAP_*` BIT.** `309d937a` ("scene DSL: retire CAP_PER_LINE", 2026-08-26 13:22)
    took the declaration count 7 → 6. Measured, not inferred: `git show <rev>:engine/level/
    scene_dsl.emp | grep -c '^pub const CAP_…'` is **7 at `6fbcd186`** (the 28 run) and **6 at
    `e4eee42c`** (the 27 run), and `309d937a` is an ancestor of the second and not of the
    first. The stanza's own enumeration already carried the answer — it lists `scanline_spans`
    ×8 in the 27 run — nobody diffed it against the 28 run's ×9. **28 − 27 = one retired
    capability bit.** The missing gate was never missing.
  So `OK — N gates` was not lying; it was **answering a different question**, and one whose
  answer changes when the *source* changes as well as when an outcome does. That is the sharper
  form of the lesson: a witness that moves for two independent reasons cannot be read for
  either.

  **SHIPPED — the count is gone.** Rows now carry the gate that produced them and the lane
  asserts a SET (`row()` / `check_row_coverage()` in `tools/effects_gates.py`): **R1** every
  scheduled gate produced ≥1 row, **R2** no row from a gate the run did not schedule, **R3** a
  gate whose rows are ALL PASS must have reached its `final=True` terminal emit. R3 is what
  separates the two states the count conflated — a scene that fails determinism emits 1 row
  instead of 2 and is complete *by its failing row*, while a gate that goes dark mid-body emits
  fewer rows with nothing failing and is caught. The expectation is derived from `wanted()`, so
  it shrinks correctly under `--only`; a segment WEDGED twice now emits **one attributed
  failing row per gate it left unmeasured**, so a wedge reads as a named failure and never as a
  missing gate. There is **no expected row count anywhere in the file** — none is derivable
  honestly, and the residual blind spot is stated in the source: R3 cannot see a gate that
  drops a *middle* row while still reaching its final one. The closing line names the gate set;
  the row count is still printed, labelled as the non-witness it is. Runner:
  `tools/test_effects_gates_segments.py` (10 new tests, in build.sh's build-fatal pytest lane).
  Red-first, on the real tool via its two listing-only gates (no emulator): deleting
  `demo_witness`'s emit while leaving its `if wanted(...)` running gives **`FAIL — ROW-SET
  COVERAGE — demo_witness … PRODUCED NO ROW`, exit 1**, where the old code printed `OK — 9
  gates`, exit 0 — and `check_registry_drift` stays silent throughout, which is precisely the
  gap it structurally cannot cover (it compares names *asked about*, not rows *emitted*).
  **Also fixed, found on the way**: `scanline_spans`' anti-vacuity floor was itself vacuous —
  `if not any(r[0].startswith("scanline_spans ") …)` sat *after* two rows whose labels begin
  with exactly that string, so it was False on every reachable path. It is now a real
  capability-coverage row (`6 of 6 declared CAP_* bits produced a row`), which is also the
  gate's terminal assertion and puts the population *on the page* instead of inside a total.
  **This lane's overseer put the stale claim into two agent briefs before measuring it**, and
  it fails in the PERMISSIVE direction: it licences an agent to see a real `boot_override`
  failure and write it off as somebody else's. A "known pre-existing failure" note is the most
  dangerous kind of stale fact a brief can carry, because its whole function is to tell the
  reader to ignore red. Re-measure one before repeating it; it costs a single `--only` run. Per segment: raster_off 9.7 -> 0.5 s, palette_variant 12.6 -> 1.5 s,
  snapshot_poison 9.8 -> 0.5 s, raster_source 13.3 -> 1.5 s. **The headline is not the 42 s.**
  It is that `raster_source` WEDGED TWICE at 240 s each on 2026-08-25 and needed a hand
  `--only` retry: the legacy stop race is arm-breakpoint / resume / wait-for-an-event, and
  the event can be lost. oracle-aether boots PAUSED and `run_to`/`run_frames` RETURN when the
  condition is met, so those four gates cannot wedge that way at all.

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

**The identity assertion, and why it has two rungs.** `assert_rust_server()` runs on every
spawn so a gate can never silently end up on the legacy server. The parcel's recipe said to
assert `implementation == "oracle-rs"` from the handshake — **that field is not on the wire
yet.** Oracle committed it (`bc2cddd`, 2026-08-26) but both release binaries here were built
2026-08-25 21:03, so a single-rung assertion would refuse the CORRECT server and block the
lane. Measured, both binaries as shipped: Rust `serverName "oracle-next"` / `serverVersion
"0.0.0"` / 41 methods / `capabilities.breakpoints: false` **(a MEASUREMENT DATED 2026-08-26 —
kept as the record of why the assertion has two rungs, NOT as current fact: the same server
reports 52 methods and `breakpoints: true` after the 08-27 05:59 relink — **that 52 was
ORACLE'S measurement, relayed; independently confirmed HERE 2026-08-27 by this lane's own live
spawn**, see the identity block below)**; legacy `serverName "oracle"` /
`"2.1-linux"` / 53 methods / no `breakpoints` key. So: `implementation` when present is the
only thing consulted; when absent, `serverName == "oracle-next"` stands in. **Delete rung 2
the day oracle's release binaries are rebuilt.** **⚠ THAT DAY HAS ARRIVED —
`target/release/oracle-aether` was relinked 2026-08-27 05:59, past oracle's `bc2cddd` which put
`implementation` on the wire. Rung 2 is now deletable, and leaving it is not free: a fallback
that can never fire is a branch nobody will ever watch fail, so it rots silently while its
presence argues the field is still absent.** Do NOT delete it blind — assert `implementation` is
actually present on a live handshake first, because the rung exists precisely on the principle
that a committed field and a shipped binary are two artifacts. Booked with the
`WAITFORBREAK-SPELLING-HOLD` flip parcel, which touches this same client seam. Proof it is not vacuous:
`tools/test_aether_instance.py` (stubbing the assertion to `return` turns 3 of 7 red) plus
`python3 tools/aether_instance.py --poison-legacy`, which boots a REAL `oracle_gui` and
fails if its handshake is accepted — run 2026-08-26, assertion fired.

- **oracle-next / oracle-aether** (bus socket, headless): pixels, scanlines (sub-line
  since 2026-08-19), memory, watchpoints with per-hit mclk, the warp mailbox, and the whole
  effects gate lane bar the five above. Its profiler EXISTS (`capabilities.profiler: true`,
  measured 2026-08-26) and serves `interrupts.{hint,vint}.cyclesSelf` and
  `cyclesSelfTotal` — but `set_profiler` must be armed with `{perFrame: true}` and the
  `perFrame[]` ROWS still carry only `cycles`/`hintCycles`/`vintCycles`/`stallCycles`, **no
  self field for either interrupt bucket**, which is exactly the gap the hold above names.
  ~~So the named ask is HALF discharged, at the aggregate and not per-frame.~~ **STRUCK 2026-08-26, on oracle's live
  measurement against our own ROM (oracle `4915ed9` docs, code `4111c88` under `51143a5`): a bucket's
  `cyclesSelf` is the exception entry alone — `cyclesSelfTotal / callsTotal` is EXACTLY 44.00 for both
  `vint` (9,830 cyc/call) and `hint` (514 cyc/call) — so a per-frame self field would print 44 every
  frame and discriminate nothing. `sum(perFrame[].vintCycles) == interrupts.vint.cyclesTotal` to the cycle
  (119/119 frames), so the column we already read IS the per-frame quantity. The 'half that matters' was
  a field that could not carry information; nothing remains of the ask. Migration of the three probes is
  unblocked on this count.** Spawn through
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
  **Measured here, so the next session does not re-derive it: this lane's tools are structurally
  unexposed.** Zero hits for `content[0]` / `"content"` anywhere in `tools/` (positive control:
  12 files match `aether_instance|jsonrpc`, so the grep was live), and the seam
  `tools/aether_instance.py` reaches the emulator through `from aether import BusClient` — a
  direct bus client, **not the MCP shim**. The exposure is to an INTERACTIVE session calling
  `mcp__oracle__emulator_status` by hand, which reads the blocks as text anyway.
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

**What it cost, so nobody re-derives the caution from the surviving prose:** 38 files of
the owner's own Aurora work — two saves (2026-08-19, 2026-08-20) plus the re-bake they
triggered — sat uncommitted for days. The heuristic also over-reached: the re-bake rewrites
`data/collision/` and `data/generated/`, which were **never** daemon territory, so an
"editor churn, not ours" reading applied to the whole `data/` blob orphaned the derived
half as well. `.gitignore` lines 103-115 explicitly **negate** those paths and say why (the
generators read out-of-repo donors and cannot run in the build), so "generated, therefore
ignorable" is wrong and the repo already argues against it.

**The failure mode is the durable part: an ownership claim fails SILENTLY AND
PERMISSIVELY.** Nothing errors, no gate trips — the work simply never lands, and every
session that reads the note reproduces the omission. Fourth of the day's stale-hazard
family and the most expensive, because the others cost effort and this one cost data
sitting unversioned. **An ownership claim needs a liveness check, not a citation:** before
deferring to "something else owns this", confirm the something else exists.

## Worktree quirks (agents hit all of these)

- **A TIME WINDOW IS A CLAIM ABOUT THE CLOCK; A BLOB COMPARISON IS A CLAIM ABOUT THE ARTIFACT —
  AND ONLY ONE OF THEM CAN BE CHECKED AFTER THE FACT** (added 2026-08-29; the aurora lane's
  formulation, against the remedy THIS lane handed them).
  Disclosing that the band parcel had briefly been reverted off master, this lane told aurora
  *"if you fetched aeon master between roughly 11:48Z and 12:20Z you got a tree without the
  parcel — refetch."* **That is the wrong instrument and they declined it.** One of their two
  reads fell inside the window; rather than doing arithmetic on my estimate they compared the
  **blob at `origin/master` against the frozen `e99a2ca7`**, found them byte-identical, and
  established their read was post-repair from the artifact itself.
  **Why the window form is bad even when the numbers are right:** my boundaries were estimates,
  from a lane that had already demonstrated a four-hour timezone error the same night, and
  **nothing about them is verifiable by the receiver** — they can only trust or refetch. The
  content check needs no trust, no clock, and no cooperation from the discloser, and it stays
  answerable indefinitely.
  **Operational form: when disclosing that a tree was briefly wrong, give the receiver a CONTENT
  test, not a time window.** "Compare `<path>` at `origin/master` against `<frozen-rev>`; equal
  means you have the repaired tree" beats any interval. Offer the window only as colour, never as
  the check.
  *Generalises past this incident: every remediation notice this lane sends should hand over
  something the receiver can EVALUATE rather than something they must BELIEVE. Same family as
  quoting the assembler revision beside a CRC, and as never typing a hash into a message.*

- **✅ DISCHARGED 2026-08-29T21:06:34Z — THE MAIN CHECKOUT IS LEVEL WITH `origin/master` AGAIN, and
  the stanza below is kept only for the rule its last two sentences carry.** `d-44` was ruled by the
  owner (*"I'm just testing things idc really about my edits you can discard"*, `decisions.jsonl`
  `d-44-answered`, 2026-08-29T14:03:10Z), the edit was discarded, and the tree could take the merge.
  Fast-forwarded `f901d988 → 95752842` with `git merge --ff-only origin/master` — **which updates the
  working tree AND the index**, and is therefore the correct instrument where `update-ref` was the
  defect. Verified after: `git rev-parse HEAD` equals `git rev-parse origin/master`, and the only
  working-tree residue is `docs/lane-status.json` (this lane's own, edited every session) plus the
  2-byte `object-bindings.json` already triaged on 2026-08-22.
  **Why this correction is made in place rather than left standing with a note underneath:** this
  file's own bar says *a stale sentence in a planning document is executed as a work order*, and the
  paragraph below is written as a standing prohibition with its condition buried in a subordinate
  clause. A session skimming it would keep a checkout stale for a reason that expired six hours
  before this was written. **The cost-accounting in the `update-ref` stanza above is the whole
  argument: the unanswered question was upstream of the outage** — so discharging the question is
  what actually closes the hazard, and letting the workaround outlive it re-creates the condition.
  ~~**THE MAIN CHECKOUT IS DELIBERATELY BEHIND `origin/master` AND MUST STAY THAT WAY UNTIL `d-44`
  IS RULED.**~~ Its working tree held the owner's unruled `d-44` edit on
  `games/sonic4/data/generated/ojz/act1/effects_scenes.emp`, which the band parcel regenerates, so
  it could not take that merge. **The two rules that survive and are NOT conditional on `d-44`:**
  **do not sync a checked-out branch with `git update-ref`** — that is the defect above, and it is
  absolute — and **do all landing, freezing and committing from a dedicated worktree**, which this
  lane's rules already require for freezes and which extends to ordinary doc commits. A stale branch
  ref in that tree is visible and harmless; the shortcut that removes it is neither.
  **⚠ AND I BROKE THE RESTATED RULE WITHIN TWO MINUTES OF RESTATING IT — recorded because this file
  says these instances are always produced by a session actively rehearsing the rule.** Having just
  written *"do all landing, freezing and committing from a dedicated worktree"*, this overseer
  committed that very correction from the **main checkout**. Not caught by a gate; caught by reading
  back what had just been written.
  **The honest resolution is a SCOPE correction, not a mea culpa, and the two must be separated.**
  The worktree extension was reasoned from the stale-index hazard, and that hazard had exactly one
  cause: a tree that could not take merges accumulating index drift under `update-ref`. **A tree
  whose index is current cannot exhibit it.** So the extension's premise is discharged by the same
  ruling as the rest of the stanza, and the surviving scope is the one that was never conditional:
  **freezes and paired landings run from a dedicated worktree** (their reason is artifact
  cleanliness, not index drift, and it stands on its own); **ordinary doc commits from the main
  checkout are fine while it is level with `origin/master`** — verified with `git show --stat` and
  its deletion count read, every time, which is the check that would actually have caught the 988.
  **What I am NOT claiming: that I reasoned this out before committing.** I did not; I wrote a
  broader rule than its reason supported and then acted on the narrower one by reflex. The scope
  correction is right on the merits and it is also post-hoc, and saying only the first half would be
  this file's own most-pleasing-part tell.

- **⚠⚠ `git update-ref` ON A CHECKED-OUT BRANCH DOES NOT REFRESH THAT TREE'S INDEX, AND THE NEXT
  EXACT-PATH COMMIT THERE SILENTLY DELETES EVERYTHING THE INDEX HAS NOT SEEN** (added 2026-08-29,
  chain 182; **this lane's defect, and the worst of the session** — it reverted a whole landed
  parcel off master and nothing announced it).
  **The mechanism.** Chain 182 was landed from a detached worktree and pushed. To bring the main
  checkout's `master` level with it, this lane ran `git update-ref refs/heads/master <sha>` —
  because the main tree could not take the merge, its working copy holding the owner's unruled
  `d-44` edit on a file the parcel regenerates. **`update-ref` moves the ref and touches neither
  the working tree nor the INDEX.** The next commit in that tree — `git add` on two enumerated
  doc paths, then `git commit` — wrote a tree from the **stale index plus those two files**. Every
  path added between the index's state and the new ref was recorded as **deleted**.
  **Damage: 988 deletions.** The entire `editor-raster-preset` parcel — the preset document, the
  generated program, `ram.emp`'s cursor, the hotkey cycle, both new test files, the Aurora
  deliverable page, the contract corrections, the `DEFERRED_WORK` entry — all reverted off master
  by a commit whose message said it was booking a lane-log entry.
  **Why it is worse than losing work: the goldens are frozen at an `aeon_rev` that HAS the parcel,
  and master did not.** So the frozen artifacts and master disagreed while every CRC in the ledger
  stayed correct — and sigil's port gates read aeon master through `AEON_DIR`. A byte-perfect
  freeze pointing at a tree that no longer matches it.
  **EXACT-PATH STAGING DID NOT SAVE IT, AND THAT IS THE PART TO INTERNALISE.** This repo's staging
  rule is written to bound blast radius, and it did bound it — for the paths NAMED. It says
  nothing about paths the index believes are gone, because those are not staged, they are
  *inherited from the index*. **A rule about what you add cannot protect what you do not add.**
  **How it escaped every check that was running:** `git status` was clean-looking (the tree still
  had the files on disk — only the INDEX disagreed), the push succeeded, the CRCs in the ledger
  were correct, and the suite still passed on the *frozen worktree*, which was never affected.
  **It surfaced only because the hub asked whether a peer had received a specific deliverable
  file, and the file was not on master.** A question about a document, not about a build.
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
  *Cost accounting, because it argues for rule 1 rather than for vigilance: the main checkout was
  in this state only because the owner's `d-44` edit sits unruled on a file the parcel
  regenerates. An unanswered decision created a tree that could not merge, which invited the
  shortcut, which destroyed the parcel. **The unanswered question was upstream of the outage.***

- **A KILLED FREEZE LEAVES A HALF-STATE THAT `git status` CANNOT SEE, BECAUSE THE MISSING
  ARTIFACT IS GITIGNORED — the tool everyone checks is the one that cannot report it** (added
  2026-08-29, chain 182; this lane's instance, and the sigil lane rates it above their own
  motivating case for the freeze-journal parcel).
  `refreeze --freeze` runs `capture_goldens.sh --write`, which **deletes and rebuilds the
  canonical aeon ROMs and restores them at the END**. Chain 182's first attempt was killed during
  the very first capture. Result: **`s4.bin` was gone from the aeon landing worktree, and
  `git status` reported the tree CLEAN throughout** — ROMs are gitignored, so version control is
  structurally incapable of mentioning it. The sigil worktree was also clean, because the kill
  landed before any golden was written.
  **So the state looked recoverable-by-inspection in the one place anybody inspects.** Had this
  lane trusted the clean tree and simply re-run, the freeze would have captured all seven goldens
  against a tree with a ROM missing, and the resulting entry would have been well-formed.
  **It was caught only by going to look for the specific half-state the chain-180 write-up
  documents**, which is the entire value of that write-up existing — and note that chain 180's
  own instance was DIFFERENT (five half-captured goldens, i.e. artifacts PRESENT and wrong). The
  note generalised to a case it had not seen.
  **Procedure after ANY killed freeze, in this order:** (1) check the sigil worktree for
  half-written goldens; (2) **check the aeon `AEON_DIR` tree for MISSING ROMs — by hashing all
  four, never by `git status`**; (3) rebuild whatever is absent and verify its CRC against the
  pin before re-running anything. `git checkout -- .` in the sigil worktree covers (1) and is
  silent about (2).
  *Why the sigil lane rates it: their motivating case was fresh goldens beside stale size tables —
  bad, but every artifact is PRESENT and a reader can compare them. Here the artifact is absent
  and the absence is unreportable by the usual instrument, which is bar 16(d)'s family arriving on
  a build tree instead of on a command's output.*
  *This is also the argument this lane used to CLEAR their freeze-journal parcel to land ahead of
  chain 184's freeze rather than holding it: the hazard is real, measured, and hit once already —
  and the parcel's `--freeze` deliberately announces-and-replaces instead of refusing, so the
  recovery detector cannot brick the recovery.*

- **A SHARED DIRECTORY IS NOT A SHARED NAMESPACE — "it is in my repo's worktree list" is a fact
  about BOOKKEEPING, not about who it belongs to** (added 2026-08-27; this lane's error, disclosed
  unprompted). Pruning leftover worktrees on the owner's directive, this lane swept aeon's
  worktree list for **merged + detached + no-branch** trees under `~/sonic_hacks/` and removed
  eleven. **One was the sigil lane's standing reference tree**, `.aeon-ref-a6a7c23d`, declared in
  **their** `docs/OVERSEER.md:1028` and kept deliberately because four built shapes matching a tip
  is the expensive half of any artifact-dependent run.
  **It matched every mechanical criterion, and it had to**: a reference tree holding aeon shapes is
  an *aeon* worktree by construction, and it lives at the shared root. **The only thing that
  distinguished it was a declaration in another lane's file, which was not consulted.**
  **The tell that it was a heuristic rather than a rule: `/tmp` scratchpads WERE carved out** as
  "another session's, not mine to remove". So the concept was present and applied **by path
  prefix** — protecting the two obvious cases and missing the one that was actually documented.
  **A heuristic that happens to cover the visible instances reads as a rule until it meets the
  invisible one.**
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
  `diag/warp-parallax-reresolve` holds a diagnosis with **zero hits in `DEFERRED_WORK.md`** plus
  `tools/warp_arrival_stability_probe.py`, and `diag/showcase-invisible` holds
  `tools/showcase_diag_*.py` whose findings are banked while the tools are not. **Deleting either
  would have lost work with nothing to announce it.** The owner's directive was explicitly to
  report a verdict per tree rather than delete on a guess, and that is why.

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
  1. It sent a freeze into sigil's **shared checkout**. `refreeze.rs` bakes
     `env!("CARGO_MANIFEST_DIR")`, so the tool writes where the binary you ran was **compiled**,
     not where you invoke it — voiding the dedicated-worktree remedy entirely. Presented as *the
     worktree remedy does not work*.
  2. It **refused `--attest`** — *"unknown argument"* — because that binary was linked at 01:41
     and the feature landed later. Source had it; the binary did not. Presented as *a usage
     error*.
  **Neither presented as what it was: the binary is older than the question you are asking it.**
  A prebuilt binary snapshots its paths, its features, its flags and its defaults together, and
  a stale one answers confidently in all four.
  **Note WHY the mitigation was adopted, because this is the durable half:** it was correct
  practice, taken to honour a peer's hold on relinking. **A precaution whose cost is paid in a
  dimension nobody is watching looks free.** Same shape as the baked-path finding it caused.
  **Operational rule: when a tool's BEHAVIOUR is what you are reasoning about, run it from source
  or check what it was built from — a version banner or an mtime, never an assumption.**
  *Which is precisely what the assembler's version banner exists to answer, and both lanes spent
  the same night arguing about that banner while neither applied it to the harness tools.*
- **A GRANTED PERMISSION GOES STALE LIKE A STATUS FILE, AND HAS NO TIMESTAMP AT ALL** (added
  2026-08-27; the sigil lane's formulation, against their own lapse). This lane said *"safe to
  relink"* at a boundary with nothing measuring — true when said. **Then it dispatched a parcel**,
  and from that moment a running build depended on the binary again. The grant never expired in
  words; **the conditions under it changed**, and neither lane re-read it. The relink was then
  found in an `mtime` rather than in a message.
  **This is the snapshot problem (shared-protocol bar 22) arriving on PERMISSIONS.** Both lanes
  had spent the night being careful that a peer's *status file* goes stale in minutes. A granted
  permission is the same class and is worse in one respect: a status file at least carries an
  `updatedAt`, so a reader can weigh it. **A permission reads as a standing state because it was
  phrased as one, and carries nothing to date it.**
  **Rule adopted, both directions and symmetric: announce a relink of the shared
  `target/release/sigil` at the time, every time, regardless of standing permission — and treat
  "safe to relink" as EXPIRING the moment the grantor dispatches anything.** Cheap, and it removes
  the need for either party to reason about whether an old grant still holds. Proposed to the hub
  for the shared protocol, since it is a cross-lane rule and not aeon's to fork.
  **⚠ AMENDED WITHIN THE HOUR, AND THE AMENDMENT IS THE MORE IMPORTANT HALF (aurora's finding,
  relayed and endorsed by sigil, correcting a rule THIS LANE had just banked and proposed).**
  Three defects in the version above, all of which made it look complete from inside:
  **(a) IT WAS BILATERAL, SO IT SILENTLY EXCLUDED EVERYONE UNNAMED.** This lane asked for the
  hold, so sigil agreed the announcement rule *with this lane*. **The aurora lane was building
  against that same binary and was in none of the conversation** — they were mid-build when the
  relink landed, and found out by watching a pid. **The holder of a shared artifact cannot
  enumerate who depends on it**, so a two-party agreement covers the two parties and reads as
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
  They built the check around it faithfully — and **a revision pin cannot detect a relink**,
  because it names a property of the **source** while the thing that ran is a **file**. Two
  revisions can produce one binary; one revision can produce two; the pin is silent on both, and
  it reads *correct* while the artifact changes underneath. **An md5 of the binary changes exactly
  when the file changes and needs no cooperation from whoever relinks it.**
  **Operational form: quote `md5(SIGIL_BUILD)` AND the revision — the revision is what a human
  can look up in a history, the md5 is what identifies the artifact that actually ran.** Take the
  md5 before and after any build whose evidence you intend to cite; aurora's agent adopted one
  mid-parcel on its own initiative and it is the only reason anyone could say the binary was
  stable *within* each build, which no revision pin could have established.
- **Sigil's banner is GAINING FIELDS (announced 2026-08-27, landing behind chain 174).** `tree:`
  will report **`clean-sources`** when the only uncommitted changes are outside the assembler's
  compiled sources, and the banner gains `closure:`, `closure-revision:` and `closure-paths:`.
  **`build.sh`'s guard is safe by construction** — since `4b43bdda` it matches *positively*
  against clean and reads every unrecognised state word as dirty, which is exactly the case
  `clean-sources` would otherwise have silenced. Expect the new fields rather than meeting them.
  **⚠ CONFIRMED IN THE WILD 2026-08-27, AND RECORD IT AS A NEAR-MISS RATHER THAN A SUCCESS.** The
  banner now reads `clean-sources at capture — 1 uncommitted change(s), none of them in the
  sources this binary is compiled from`, the guard takes its unrecognised arm, and `build.sh`
  prints `(revision+dirty)` — over-warning, the direction chosen. **But the SEQUENCING was luck.**
  The guard fix landed hours before the word that would have silenced the old `dirty*` prefix
  test. **Had the order been reversed the warning would simply have gone quiet, and nothing would
  have announced it** — a fail-open created by a peer's ordinary, well-intentioned field addition,
  invisible to both lanes. *(The sigil lane insisted on this framing against this lane's first
  wording, which had called it a success. A fix that arrives before its trigger by accident is a
  near-miss; treating it as a win teaches the wrong lesson about why it held.)*
  **The ledger tooling is also changing:** `--freeze`/`--attest` will validate prose BEFORE the
  write, escape quotes rather than refuse them, and use temp-and-rename. **Retire this lane's
  temporary pre-parse of the `ab = "…"` line only after a freeze has actually RUN through the new
  path — not when it merges** (a fix existing and a fix having fired are different facts).
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
  shells sat sleeping from 03:55/03:59/04:01 until reaped at 09:44 — 1h45m each — and their
  three background tasks then died together with the exact titles that named them, which is the
  clean confirmation that the population was three.
  **Two corrections to how this was first reported, and both are the reusable half.**
  (a) **It was THREE, not two, and the third waits on a DIFFERENT pattern** (`refreeze
  --freeze`), so an enumeration run as `pgrep -f "refreeze --attest"` structurally cannot see
  it — a sweep whose own search term is one of the values being swept for. Enumerate the loop
  CONDITION out of `/proc/<pid>/cmdline` (`grep -o "until ![^;]*;"`), never the pattern you
  happen to have in hand. (b) **"The spawning session is gone" was wrong**: all three were
  children of PID 286960, which is **this lane's own live `claude` process** — a `/clear`
  retires the SESSION and keeps the PROCESS, so orphans from earlier sessions are still your
  own children and are yours to reap. A peer reasonably read a dead session id as a dead
  process; the check is `/proc/<ppid>` and your own shell's ancestry, not the session id in a
  scratchpad path.
  **Why it earns a bullet rather than a shrug: the failure is silent and inverted.** The shells
  report nothing, block nothing and consume nothing, so there is no artifact to be suspicious
  of — and a handover that says *"they will fire against your run and report on the wrong
  worktree"* and one that says *"they can never fire at all"* call for different responses,
  while producing the identical empty evidence (bar 16(d)).
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
  **The four, and they are one statement rather than a list:** a **CRC without its freeze**
  (sigil's — true against the baseline standing when measured, false the moment aeon froze);
  a **self-observation without its clock** (this lane's — "this session has zero Skill calls",
  present tense, falsified by **this lane's own next action eight seconds later**); an **address
  without its shape** (this lane's — `0xA6CDC…` quoted with no `s4.debug.bin` named, while sigil
  measured the plain shape and got a constant `0x22B0` difference); and a **term without its
  definition** (this lane's, and the worst — "movers" used for the raw candidate set one sentence
  before the candidate-minus-control differential, in the entry whose falsifier turns on that word).
  **WHY CARE CANNOT FIX IT.** In the address case this lane had the shape in hand, read that blob
  deliberately, and did not carry it into the sentence. So it is not an attention failure — it is a
  **completion-signal failure** (sigil's reframe): **the number arriving IS the signal that the work
  is done, and the referent is not part of what that signal measures.** Diligence already fired and
  returned satisfied. The remedy must therefore be a mechanical clause attached to the figure and
  can never be a standard of care. Generalised: **a referent is the part of a claim its author has
  already resolved, which is exactly why it is the part they cannot see is missing.**
  **WHY PROSE IS THE WORSE CASE, and it is mechanical rather than cultural (sigil's):** a number
  must be **RE-TYPED** at every use, so each use re-opens the slot where its baseline goes; a term
  is **RE-USED BY REFERENCE** and re-opens nothing. *This lane's refinement: the axis is **restated
  vs referenced**, not number vs term — a figure pointed at as "the CRC above" or "the same hash" is
  a pointer too and decays identically. The trigger is not "is this prose?" but "is this use a
  restatement or a pointer?"*
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
  **The instances.** (1) This lane's SIGIL-DECOUPLE booking said *"the FROZEN TABLES are the
  placement authority, not `map.toml`"* — true when written, superseded by sigil's K5 parcel, and
  **two lanes spent an hour scoping step 2 against it** before anyone opened sigil's source.
  (2) Sigil's own `SizeSource::Frozen` doc comment carried the same superseded premise
  independently. (3) The same booking's R1 audit still names `$48000`/`$50000` for the DAC banks,
  which the 2026-08-26 re-layout moved — `map.toml` now DERIVES them
  (`align_up(packed_data_end + DATA_GROWTH_RESERVE, 0x8000)`, `dac_banks = 0x90000`), and
  `$48000` survives only as commentary about an anchor that is no longer there.
  **Why this is worse than the code-comment class the prose sweep was scoped for.** A stale code
  comment misinforms a reader who is already looking at the code. **A stale booking is read as an
  instruction**: it names work, it sits in the queue, and a session picks it up and starts. The
  morning's prose-bounds sweep covered comments and help text; **planning and booking documents
  are the population it missed**, and they are the population with the highest blast radius.
  **The mechanism, and this is the part neither lane has a fix for (sigil's diagnosis, kept in
  their words): the artifact that supersedes a booking is a commit in a DIFFERENT REPO, so there
  is no edge for anything to walk.** Both documents were correct when written; nothing in either
  tree notices when a landing elsewhere invalidates a sentence in a plan. **Named rather than
  patched — neither of us would maintain a checker for it, and proposing one would be the
  announce-but-do-not-run shape this file is full of.**
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
  Twice this session a peer refuted a claim of this lane's that **every check either lane was
  running had passed**: a flip condition whose safety property was supplied only by asserting it,
  and a reachability green called "the instrument doing its job" when the ritual guaranteed that
  green. Neither was a measurement error. Both were errors in the reasoning *about* an
  instrument, made while the measurements were being handled carefully.
  **The catches were possible only because the reasoning was WRITTEN DOWN in a form that could be
  shown false.** *"Attest passed, reachability green"* would have been exactly as wrong, and
  **unfalsifiable — and it would have read as more competent, not less**, because a bare verdict
  carries no visible surface to attack.
  **So the transferable habit is not "have a peer check you" — a peer cannot check a conclusion.
  It is: state the argument, and state it in the form that can be refuted.** That is what a peer
  review is *for*; the second pair of eyes is worthless against a report that only carries
  outcomes. A checklist cannot carry this habit, which is why it is written as a bar and not as a
  step.
  **Corollary for anything this lane sends or banks: prefer the sentence that could be wrong.**
  "Both revisions were ancestors before the suite ran" invites the question that killed it (could
  it have been otherwise?); "reachability green" does not.
  *~~And the three proposals this session produced turn out to be one finding at three sites…~~*
  **⚠ THAT UNIFICATION IS WITHDRAWN — the sigil lane refuted it within the hour, and the refutation
  is the more useful half.** The claim was that the over-refusal bar, the volatile-pointer class
  and the vacuous-green bar reduce to *"the artifact that reports success is not the artifact that
  establishes it."* **It fits two of the three and not the third.** The over-refusal bar is not an
  uninformative success at all — it is a **RED on correct work**, whose harm is a false alarm that
  trains a permanent route-around. Restating it to fit the unification turns it into *"the verdict
  does not establish the fault"*, which **is shared-protocol bar 10** — so the merge either loses
  the mechanism or duplicates a bar that already exists.
  **And it would cost the property this file insists on elsewhere: state a rule as a bound, not a
  slogan.** Each of the three is actionable BECAUSE each names its own check — *could this green
  have come back dirty?*, *where does the pointer to the durable thing live?*, *can this refusal
  fire on a correct run?* The unified sentence is memorable and answers none of them. **Three bars
  that reduce to one lesson is a stronger result only if the lesson keeps the operations; this one
  dropped them.**
  **Recorded rather than deleted because of what it was: the most PLEASING thing this lane wrote
  tonight, and the third of its claims the same peer had to withdraw.** All three were syntheses
  rather than measurements, all three were reached while handling the measurements carefully, and
  the tell each time was that the invented part was the part its author most liked. *Cross-
  reference the three, never merge them — and note that three instances in one night between two
  lanes in constant contact is a coincidence of attention, not a discovered unity.*

- **A REFUSAL THAT CAN FIRE ON THE CORRECT CASE IS WORSE THAN THE SILENCE IT REPLACES — three
  declined in one night, which makes it a rule rather than three judgement calls** (added
  2026-08-29; instances split between this lane and the sigil lane, the pattern named here after
  the third).
  The three, all real and all declined deliberately:
  1. **`SIGIL_HARNESS_ROOT`** — a fix that would have made `refreeze` refuse when the variable is
     unset. The normal invocation does not set it, so the refusal would have fired **in the middle
     of an unattended overnight freeze**, guarding a hazard that did not exist. Stopped only
     because the implementing lane measured before building what it had been told.
  2. **`AHEAD OF REMOTE` at attest time** — refusing an unpushed freeze would refuse the honest
     mid-ritual state. Kept as a warning; the flip to refusal is gated on the state ceasing to be
     normal, and that has to be **computed from the ledger**, not remembered (see the
     push-before-attest ritual above).
     **⚠ THIS INSTANCE IS NOT A CLEAN DECLINE AND AN EARLIER WORDING HERE IMPLIED IT WAS**
     (corrected 2026-08-29 on the sigil lane's reading of this lane's own account, against this
     lane's credit). What actually happened: **this lane proposed the flip as a remembered
     three-chain count AND asserted that this made it "checkable rather than remembered" — the
     assertion being the only thing supplying the property — and withdrew it after the sigil lane
     objected.** So the instance is not *aeon declined an over-refusal*; it is *aeon talked itself
     into one, a peer showed the safety property was self-asserted, aeon withdrew.*
     **Kept in the corrected form because it is a BETTER instance that way**: a clean decline shows
     the rule being followed, while this shows it catching something a lane had already convinced
     itself of — which is the only evidence that matters for a bar about checks that look stronger
     than they are. *A correction that reduces the corrector's credit is the one worth trusting;
     note that the peer offered to take this lane's version instead, and this lane's version was
     the flattering one and the wrong one.*
  3. **A completed freeze journal surviving a kill** — reported as a NOTE rather than a fault,
     because the alternative fires on a run that actually succeeded.
  **Why it earns a bar: the cost is not the false stop, it is what the operator does next.** A
  refusal that fires on correct work trains a route-around — an env var someone always sets, a
  flag someone always passes, a step someone always skips — and **the route-around is permanent
  while the memory of why is not.** The next session inherits the workaround as ritual and cannot
  reconstruct which cases it was suppressing. So a gate that over-refuses does not merely annoy;
  it **converts itself into a disabled gate** by a path nobody records.
  **Test before building any refusal: name a correct run that would trip it.** If you can, it is a
  warning until the state it refuses has demonstrably stopped occurring — and *demonstrably* means
  a query someone can run, not a count someone remembers.
  *Composes with the opposite failure this file already carries in quantity — the gate that passes
  for the wrong reason. Both are the same defect at different signs: a check whose firing is
  uncorrelated with the thing it names. The vacuous-pass family is better represented here only
  because a false green leaves no one arguing with it, while a false red gets routed around within
  the hour and looks like it was fixed.*

- **`stat` PRINTS LOCAL TIME AND YOUR EVIDENCE IS TIMESTAMPED IN UTC — THE OFFSET IS RIGHT
  THERE IN THE OUTPUT AND IS READ AS DECORATION** (added 2026-08-29; this lane's error, caught
  by the aurora lane after it had already reached three lanes).
  Investigating an unattributed dirty tree, this overseer read `stat -c '%y'` output —
  `2026-08-29 04:25:04.693043247 **-0400**` — and transcribed the wall-clock half as Z in
  messages to aurora, sigil and the hub. This box is EDT, so every one of those times was **four
  hours early**. The true times were 08:25:04Z and 09:11:10Z.
  **Why it mattered rather than being a pedantic slip: the error moved the event across a
  decision boundary.** The owner's goodnight is 07:56:52Z. At the fabricated 04:25Z the edit sits
  comfortably *before he went to sleep*, which makes "this is his authored work" the natural
  reading; at the true 08:25Z he was already asleep and that reading is dead on timing alone. The
  wrong number did not merely mislabel the event, it **supported a specific wrong conclusion about
  whose work it was**, on a question that was about to become a card asking him to rule.
  **The general shape: a timestamp is the one field where the units travel WITH the value and
  still get dropped.** A byte count carries no unit and nobody assumes one; `%y` prints its offset
  in the same string and the offset reads as trailing punctuation. It sits in the same
  provenance-feeling class as a verified-at SHA — transcription rather than argument, so it gets
  copied by a session applying real scrutiny two inches away.
  **Operational form: use `TZ=UTC stat` or `date -u -r <file>` whenever a file time is going into
  a message, a card or a doc**, and when quoting one, write the `Z`. Never hand a bare wall-clock
  across a lane boundary — the receiver cannot tell which zone it was read in, and the failure is
  silent in both directions.
  *Note the asymmetry with the tooling this lane already has: `updatedAt` in `lane-status.json` is
  protected by a rule that says take it from `date -u`, precisely because a hand-written time is
  untrustworthy. That rule guards the field nobody reasons from and left unguarded the times this
  lane actually builds arguments on.*

- **A GATE WHOSE PASS AND FAIL EMIT THE SAME ARTIFACT IN YOUR ENVIRONMENT HAS NOT PASSED — IT
  HAS NOT RUN** (added 2026-08-29; the aurora lane's formulation of an observation this lane made
  about its own staleness gate, and their wording is the one to keep).
  `tools/level_staleness.py` compares `newest mtime(editor sources) > newest mtime(generated
  tree)`. In a fresh `git worktree add`, git writes **every** file within the same second, so `>`
  is false **by construction** — the gate cannot fail there whatever the tree contains. That is
  precisely why it could not see the floor fix missing from the ROM: a green sat beside the defect
  the whole time.
  **The reusable procedure, in their words: name the property, then ask what a GREEN would have
  ruled out.** In a fresh worktree, nothing. So "staleness passed" is **unquotable as evidence
  from a clean checkout** — not because the gate is wrong (it is correct in the tree it was
  designed for) but because in that environment it is not an instrument at all.
  **This is bar 25 (a green log and an absent run are the same artifact) with the absence created
  by the ENVIRONMENT rather than by a missing flag** — and it is worse in one respect: a missing
  flag is a fact about a command someone can inspect, while this is a fact about the *filesystem
  state* the command met, which appears nowhere in its output. Ask it of any gate before quoting
  a pass, and especially of one you are running somewhere other than where it was written for.

- **A "KNOWN PRE-EXISTING FAILURE" NOTE ROTS INTO A LICENCE TO IGNORE RED — SECOND INSTANCE, AND
  THIS ONE WAS IN A COMMIT MESSAGE** (added 2026-08-29, the repaint landing). This file already
  carries the `boot_override` instance, which said a brief must never repeat one unmeasured. Same
  class, new surface: `fix/repaint-preserve-crossover`'s own commit message declared its single
  failure *"pre-existing, red on master since `fde35b2f`, out of scope"*. **Measured on clean
  master at landing: `tools/test_collision_consistency.py` is 25 passed / 0 failed.** The floor
  re-bake fixed it *after* the commit being blamed, so the note was true when written and false
  when read, one day later.
  **Why the commit-message surface is the worse one (protocol bar 23's family):** a brief is read
  once by one agent and dies; a commit message is permanent, is what `git log` shows, and is the
  first thing the next reader of that branch meets. **Nothing re-checks it, and its whole function
  is to tell the reader that red is acceptable.** A stale-but-once-true note is more dangerous
  than a wrong one, because it survives every check that looks for fabrication.
  **Cost of the corrective: one `pytest` invocation on a clean checkout.** Pay it every time — and
  note that the measurement is what MADE the landing safe, since a genuine new failure introduced
  by that parcel would have been invisible behind the same sentence.

- **A RULING RELAYED ON THE OWNER'S BEHALF CAN CARRY CONSTRAINTS HE NEVER STATED, AND THEY ARRIVE
  WEARING HIS AUTHORITY** (added 2026-08-29; the hub's error, withdrawn by them unprompted and
  banked there as a hub error; this lane caught it by measuring the tool rather than by suspecting
  the message).
  Relaying the owner's d-37 ruling, the hub added *"keep the script's refusal (exactly the expected
  cells carrying `$1472`, nothing else) as is"*. **That constraint was the relayer's invention.**
  The tool does the opposite by design — its docstring says *nothing here is a literal cell word*
  and it matches on **resolved geometry** — and the invented constraint was also WRONG: measured
  here, 300 cells carry the literal word, the tool targets 150 pinholes, and only 146 of those are
  tops of `$1472` columns, so **four repaired cells are not that word at all**. A refusal narrowed
  to the literal would have left four holes in the owner's floor and reported success.
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
  Landing chain 180 this lane wrote *"sigil `6b3ef068` (freeze ball-seating chain 180 + attest)"*
  — **one SHA carrying two claims**, and the wrong one for the evidence. The goldens and the
  `pins.rs` evidence are in `fa0e6540` (11 files, both ROM goldens, `provenance.toml` +54);
  `6b3ef068` touches `provenance.toml` alone (+21), the attest block. The sigil lane **went to the
  right commit, verified it, and said nothing** — so the correction surfaced only because this lane
  audited its own message afterwards.
  **Their framing, and it is the durable half: the omission IS the defect, not a small thing
  attached to otherwise-good diligence.** A silent route-around costs the router nothing and leaves
  the bad form standing for every later reader — including one without the instinct to go looking,
  who `--stat`s the attest, finds no goldens, and concludes the freeze is empty.
  **This is the SHA-class bar's blind spot from the receiving side.** That bar polices what you
  cite; it says nothing about what you do when a peer's citation is wrong and you can see past it.
  Both lanes were applying it correctly all night and neither noticed the gap.
  **Operational form:** `freeze <SHA> · attested <SHA>` for a paired landing, and when a peer hands
  you a SHA you have to correct silently to use, correct it out loud in the same message.
- **A HABIT THAT HAPPENS TO COVER A DEFECT IS INDISTINGUISHABLE FROM A DESIGN THAT PREVENTS IT,
  RIGHT UP UNTIL THE DAY IT IS NOT** (added 2026-08-29, chain 180; this lane's formulation, adopted
  by the sigil lane for two of their own instances the same hour). The general case of the
  rehearsal-is-not-protection clause, pointed at things that WORKED.
  Three instances in one chain, all of which came out green: `cmd | tail; echo $?` reports **tail's**
  status, and the sigil lane's pushes were safe all night only because their reflex is to verify
  against `git ls-remote` — a positive artifact — rather than an exit code; this lane's freeze
  survived a mid-capture kill only because it happened to be in a dedicated worktree; and the
  miscitation above cost nothing only because the reader's instinct covered it.
  **Why it earns a bar rather than a shrug: a covering habit produces exactly the evidence a
  designed check produces, so nothing distinguishes them while both hold.** The green run is not
  evidence the mechanism exists. **Test: name what would have happened if the habit had not fired,
  and if the answer is a wrong result reported confidently, write the habit down as a rule or build
  the check.**

- **FINDING THE MACHINERY IS NOT FINDING IT RUN — shared-protocol bar 16 (name / presence /
  behaviour) arriving on a CODE PATH** (added 2026-08-27; this lane's over-claim, named by the
  sigil lane). Tracing why one `embed()` in `engine/system/math.emp` resolves when the resolver's
  boundary check says it should not, this lane found a **per-module `embed_base` override** in
  sigil's `resolve/mod.rs` — real code, with a comment naming the exact puzzle — and reported it
  as *the mechanism you could not locate*. **It is a mechanism. Nothing established that it is
  the one that fires**: `embed_base_for` is a caller-supplied closure, and every caller either
  lane could find is **module-INDEPENDENT** (`&|_| opts.embed_base.clone()`, `move |_id|
  Some(aeon_root.clone())`), so on the ROM path the override may be present and never exercised.
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
  **Their timeline, which is the finding rather than the incident.** A claim about
  `evict_witness.py` landed in their doc at 03:11 and was **true at that moment**. This lane fixed
  the underlying code at **03:51**. Their doc re-cited it at 04:45, 04:48 and 06:39, and exported
  it to this lane at ~13:00 **as a live exposure**. **Nobody re-read the source at any point in
  that chain** — every re-citation was a faithful copy of a sentence that had been true. The
  coordinate rotted with it: the cited `:97` is now a comment line and the code sits at `:109`.
  **Why every existing bar missed it.** *Verify firsthand* was satisfied — the author really did
  read the file. SHA class was fine. **Bar 22 (re-read at SEND time) is closest and does not
  reach it, because bar 22 is written for peer STATUS files, which carry a timestamp that
  announces their own staleness.** Committed prose carries none, **and it reads as settled fact
  precisely because it is yours and you wrote it.**
  **Remedy, and it is the protocol's verified-at anchor pointed INWARD: when a doc here asserts
  anything about a sibling repo's code, record the peer revision inline** — `(sigil 8dc62906,
  read 2026-08-27)`. That converts an unfalsifiable sentence into a one-command currency check.
  And re-read the peer's **tip** before exporting a claim, never the doc that quotes it.
  **⚠ THIS FILE'S OWN EXPOSURE, MEASURED: 176 lines mention `sigil`/`oracle`/`aurora`; 11 carry a
  peer revision.** *(That 176 is mentions, not claims — an upper bound, and the sweep is one
  spelling axis. The ratio is the signal, not the number.)* **Retrofitting all of them is not
  proposed; the rule binds NEW assertions**, and an old one gets its anchor the next time anyone
  relies on it.
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
  Lived: hunting for step 2's remaining gap, this lane grepped `bganim_room`, read the hit at
  `build.sh:224` — *"bganim_room (the BG-anim ceiling is NOT checked)"* — and reported the gate
  as unarmed to two lanes. **That line is inside the `FAST=1` SKIP BANNER**, an accurate statement
  about what fast mode omits. The gate runs unconditionally at `build.sh:664` with `--rom`,
  `--built-after` and `--fixture`, and its own comment calls it *the only enforcement of
  `BGANIM_SECTION_CEILINGS` against a real listing*. **Four lines of context, unread.**
  **And note WHY it caught a session running that exact theme all day: the theme made a vacuous
  gate the expected find, and the search obligingly produced one.** A day spent removing
  announce-but-do-not-run gates is a day primed to see one. **The prior did not make the reader
  more careful; it made the confirming hit more convincing.**
  **Corrective: when a hit confirms what you were looking for, read its enclosing block BEFORE
  reporting it** — and if the hit is a printed string, find out what prints it.
- **HOLDING A RULE AND APPLYING IT TO YOUR OWN OUTPUT ARE SEPARATE ACTS — and the gap between
  them is measured in MINUTES, not days** (added 2026-08-27; the formulation is the sigil lane's,
  the instance count is mostly this lane's). This is the frame that explains why almost every
  corrective in this file is a MECHANISM rather than a reminder, and it should be read before
  the bars below, because it is the reason they are shaped the way they are.
  **Measured, one night, all under maximum priming:**
  - This lane banked the self-matching-`pgrep` hazard, wrote it into this file, corrected a peer
    about it — and **then wrote a wait loop that greps for a string its own command line
    contains**, roughly twenty minutes later.
  - This lane banked the commit-message bar (*a commit message is a claim about a diff and
    nothing checks it*) in the morning and **pushed a commit whose message described a change it
    did not contain** the same hour.
  - The sigil lane spent the night enforcing the absence surface on others (*an absence and a
    failure produce the same artifact*) and **offered a check whose negative direction was a bare
    absence**, in a message where everything else was careful.
  - The sigil lane praised this lane for announcing a relink before doing it, then **relinked the
    shared binary without announcing it**, hours later.
  **None of these were careless.** Every one was produced by a session actively rehearsing the
  rule it broke, usually in the same conversation. **Rehearsal is not protection** — that clause
  already exists in the shared protocol about SHAs, and this is the general case.
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
  **Measured, one command:** `python3 -m pytest tools/test_gen_vram_map.py -q --no-header
  -p no:cacheprovider` on a fully passing file prints `..................` and `34 passed`;
  grepping that output for the file's own name returns **0**. `build.sh:432` runs the tool
  suite with exactly `-q`, so **a fully green aeon pytest lane contains no gate names at all**
  — there is nothing in it to confirm.
  **The saving grace, and it is structural rather than lucky: `build.sh` gates on the EXIT
  CODE** (`if ! python3 -m pytest …`), which is capture-independent. So the *did the suite
  run* question is soundly answered here and the sigil-side defect (a flag present whose
  output is discarded) does not reach it. What is NOT answered is *did THIS gate run* — a
  test silently dropped from the suite leaves the exit code green and the log a row of
  identical dots. That is the effects-lane `OK — 27 gates` shape exactly: a count derived from
  rows that actually appeared, shrinking silently while every printed row says PASS.
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
  caveat that had been false since a commit that was an ANCESTOR of the assessment's own
  survey pin, plus a ruling aimed at a field the sibling's save path never writes. A
  quoted survey, roadmap, or plan caveat can be stale before its pin; only reading the
  described tree catches it. Peer verification found both — reciprocate it.
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
  list a SUBSET of labels, so content between two listed labels is **invisible in them by
  construction**. This lane, the aurora lane, and this repo's own booking all read the
  `[HeightMapsRot+0x2000, Dac_Temp_Blip)` gap as ~119,072 B of slack; `s4.debug.lst:2225-2229`
  shows `AngleTable`/`SolidityTable`/`Map_Sonic`/`DPLC_Sonic`/`Art_Sonic` filling it, and the
  ROM image is only **43.8% zero** across that span. Real free tail: **11,427 B** at
  `0x4535D`, by constant-byte run scan — and even that is padding inside `Art_Sonic`'s
  allotment (offset 97,469, `mod 32 == 29`, so not whole blank tiles), i.e. growing room for
  the most growth-prone object in the region rather than unowned space.
  **What makes this a bar and not a repeat of the existing allotment rule:** the booking
  ALREADY said *"a gap is an ALLOTMENT, never proven free space"* — and then committed the
  error two paragraphs later on a different label pair, and two more lanes inherited it. A
  rule that says "do not conclude X" without saying **what does conclude X** leaves the
  reader holding the only tool they have. **The instrument for occupancy is the `.lst` symbol
  listing or a scan of the ROM image itself; the frozen table structurally cannot answer it.**
  Corollary, from the same episode: an arithmetic step built ON TOP of somebody's number
  looks like corroboration and is propagation — aurora re-derived a margin from this lane's
  bad figure and the agreement read as two sources.

- **A completeness claim about a TRUNCATED view — `head -N` on a definition — and the
  truncation leaves no mark** (lived 2026-08-24, this overseer's error, caught by the sigil
  lane). Establishing whether a section qualified for a sigil mechanism, this lane read
  `Fragment`'s variants with `sed -n '/pub enum Fragment/,/^}/p' … | head -40` and asserted
  *"exactly two length-variable variants"*. The enum is **94 lines** and that window holds
  exactly **5 of 7**: `RelaxLadder` (`:74`) and **`Org` (`:93`)** were below the cut.
  **`Org` is the one that matters, and the stated reduction could not reach it:** the argument
  offered was *"both length-variable variants are instructions, and this section contains no
  instruction"* — and `Org` is **not** an instruction, so a section carrying one fails
  `is_position_independent` with no opcode anywhere in it.
  **This is the absence family (shared-protocol bar 16d) with truncation in place of
  suppression, and truncation is the worse face.** `2>/dev/null` at least hides a message that
  *would* have existed; `head -N` output is **indistinguishable from a complete listing** — no
  ellipsis, no exit code, nothing to be suspicious of. The conclusion survived only on the
  *source* leg (one module, all `data`, no `org`/`align`), which had been offered almost
  apologetically as mere inspection, while the type-level leg presented as the rigorous half
  was the wrong one. **Bar 17 with the sign flipped: the completeness claim was the cheap half
  of the message and the cheap half is what failed.**
  **Correctives, both cheap:** count the thing before characterising it (`grep -c` the variant
  pattern over the *whole* definition, never a window), and when a reduction rests on a
  category (*"all X are instructions"*), enumerate the category from the type and check each
  member against the predicate rather than against the category's typical member.

- **A COMPILED-IN library and the INVOKED binary are two artifacts, and a suite green only
  witnesses the one it links** (added 2026-08-26; drawn by the sigil lane against this lane's
  own assertion, mid-parcel). Landing the replay re-stamp, this overseer checked sigil's stale
  `target/release/sigil` against its source, correctly found that only tests, pins and goldens
  had moved since the binary was built, and told the sigil lane the staleness was harmless.
  **Their next merge falsified it**: that parcel moved emitter source (`sigil-frontend-emp`'s
  `eval/emit.rs`, `eval/mod.rs`), so the on-disk CLI went stale against changed emitting code —
  the exact case where it bites.
  **⚠ THE MECHANISM AS FIRST WRITTEN HERE WAS FALSE — corrected in place 2026-08-27 by the sigil
  lane, who grepped their own tree when this lane cited the sentence back at them.** It used to
  read *"sigil's byte gates build ROMs through the library compiled into the test binaries, never
  through `target/release/sigil`"*. **They do shell it, extensively**: `env!("CARGO_BIN_EXE_sigil")`
  appears across at least nine test files (`subcommands.rs`, `sigil_test_runner.rs`,
  `deny_todo.rs`, `extra_entry.rs`, `warn_tier_corpus.rs`, `placement_fix.rs`,
  `tranche0_acceptance.rs` among them, several with multiple call sites), and under
  `cargo test --release` that macro resolves to exactly `target/release/sigil`.
  **The CONCLUSION survives and its reason changes completely, which is the point.** A suite run
  is still not evidence that the CLI binary `build.sh` invokes is current — but **not** because
  the suite avoids that binary. It is because `CARGO_BIN_EXE_*` is a **build-time** dependency:
  cargo builds the bin target *before* any test that references it, so the suite spawns a
  freshly-built binary and then leaves the on-disk one exactly as it found it for everyone else.
  Two artifacts, one checked; the unchecked one is still the one that produces every CRC we freeze.
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
  *Recorded because of how it surfaced: this lane quoted its own doc to a peer as the reason a
  relink would be safe, and asked them to check the one step it was least sure of. The verdict
  was right, the stated reason was wrong, and the wrong reason was load-bearing for the NEXT
  decision rather than this one — shared-protocol bar 10, on one's own document, where the cheap
  move was simply naming which step to attack.*
  **Why no gate here can catch it:** a stale assembler emits byte-identical output for as long
  as its source has not changed, so every downstream CRC agrees right up until the moment it
  matters, and then agrees with the wrong thing. This is our own byte-neutral CRC trap (a
  matching CRC cannot witness that the build RAN) arriving in the compiled-in-versus-invoked
  direction.
  **Operational form: `cargo build --release` in sigil is a precondition of any refreeze, and
  it is a SEPARATE ACT that nobody's green can stand in for.** When the pairing is live,
  require the sigil lane to say "rebuilt" explicitly rather than inferring it from their suite.
  Re-derive the staleness at the moment of freezing, never from an earlier check: this instance
  went from harmless to load-bearing inside one merge.
- **An instrument that reports an ABSENCE can manufacture that absence, and the check is
  whether the instrument could have produced the empty result** (added 2026-08-26; contributed
  by the sigil lane against their own near miss, and **framed at their insistence as the
  absence class rather than as a fact about one tool** — that framing correction is the
  valuable half, see below). Verifying that their rebuilt release binary carried a string
  literal existing only in the just-merged parcel, that lane ran `strings` and got **absent**.
  The literal is there. Its format string opens with an em dash; `strings` emits only runs of
  printable ASCII, so it split the literal at the first non-ASCII byte and reported nothing.
  `grep -a` on the binary answers the question; `strings` cannot.
  **Why it is booked here and not as a tooling footnote: the false alarm was one command from
  being SENT.** This lane had just told them not to refreeze against a stale binary, so an
  "it is still stale" message would have been received as confirmation of a hazard both lanes
  were already primed for, and would have stalled a landing on a fact that was not true. The
  absence surface (shared-protocol bar 16d) usually costs the lane that runs the command; here
  it was about to cost the lane that did not.
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
  claim and then refuted the reason given for it). Landing the paired re-stamp, the
  stale-assembler banner fired naming 11 modified files. This lane said they were all artifacts
  and offered the refreeze commit as proof, reasoning: *"if any source file had been dirty it
  would be in that commit, because I staged by enumerated path."*
  **That runs backwards. Staging by enumerated path is precisely the operation that OMITS an
  unenumerated dirty file** — this repo's own invariant 3, doing exactly its job. `git add -u`
  would have swept a stray source edit in and made it visible; exact-path staging guarantees it
  stays out. So under that mechanism the commit looks **identical** whether or not source was
  dirty, and the check **cannot fail** — a wrong-reason pass, this repo's oldest gate failure
  mode, arriving in a hand-offered piece of evidence rather than in a gate.
  **What actually closes it:** the banner said **11**, the commit carries **11** paths, all
  under `golden/`. There is no room for a twelfth. A source file dirty-and-unstaged would have
  made the banner say 12 while the commit still said 11, and **that discrepancy is the
  observable**. The evidence is an agreement between two independent numbers, **one of which
  the committer does not control**, which is the property the staging story lacked entirely.
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
  over-long fixture of length 9 against a max of 8. It went red when the ceiling moved UP to 16
  — correctly, and that is the trap, because the red **looks like the test working**. Had the
  ceiling moved DOWN, 9 would have sat under the new bound and the test would have kept
  **passing**, green about a bound that no longer existed. A fixed count is not a test of the
  ceiling; it is a test of one number that happens to sit above it today.
  **Why it is booked here specifically: this lane wrote the defect into a dispatch brief.** The
  brief for the band-ceiling raise told the agent to re-author `poison_scene_capacity.emp` from
  8 layers to 16 and to move `emp_expect_fail.py`'s literal fragment `"count+1 entries — 8+1"`
  to `16+1` — i.e. to **reproduce the fixed count one ceiling higher**, having already noticed
  and flagged that the poison was hardcoded with no pin. Noticing that a number is unpinned and
  then re-typing it at a new value is not a fix; it is the same defect with a fresher date.
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
  Their sweep for stale off-canonical lengths reported three; it was **four**. The miss was
  spelled `assembled_len: pins::ASSEMBLED_LEN` — a wrong value wearing a symbol — and the
  original sweep could not see it because that sweep enumerated large hex **literals**. A second
  drifted for 28 days after being *correct when typed*, with nothing able to say so.
  **The transferable half is NOT "also grep for symbols", and this lane proposed exactly that
  wrong generalisation before being corrected.** Spelling was irrelevant to how it was actually
  found: every value was **recomputed from its own generator and diffed against the checked-in
  artifact**, so the symbol-spelled one got recomputed like the literals and could not hide. A
  sweep for "constants that look pinned rather than computed" has to guess what that looks
  like, and the point of the finding is that **it does not look like anything.**
  **Operational form:** enumerate the population from the TOOLS that write it — every value some
  generator emits into a checked-in artifact — recompute each, and diff. The blind spot becomes
  "a value no generator produces", which is small and nameable, instead of "a value spelled in a
  way I did not anticipate", which is neither. In sigil that population was three tools writing
  the same ROM address into three artifacts; **this repo's equivalent is any address or length a
  generator writes and a human also transcribes**, and finding that set is the sweep.
  **Price the result honestly, per row** (their own caveat, volunteered against their own gate
  after their agent overstated it and corrected itself): recomputation makes every value
  checked, but the COMPARISONS differ in kind. Where two tools independently produce the value,
  it is a second witness; where one artifact holds a **copy** of another taken at freeze time,
  the comparison is **temporal, not independent** — it catches a half-done landing, which is
  worth catching, and is not corroboration. Do not report such a gate as "N independent
  witnesses"; say which rows are independent and which are temporal.
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
  blip bank at `$48000` (bank `$9`) and the shared drum bank at `$50000` (bank `$A`). The
  2026-08-26 re-layout moved them — `map.toml` records `dac_banks = 0x90000` (bank `$12`, shared
  `0x98000` = `$13`) and the `.lst` puts `Dac_Temp_Blip` at `0x90000`. **Four sites, wrong in both
  address and bank id, and no gate could contradict them because nothing executes a header.**
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
  **Why it is worse than a stale code constant rather than more benign:** a stale bound in code
  eventually fails a gate; a stale bound in prose **teaches the next reader something false and
  is never executed**, so nothing can ever contradict it. It is the perishable-claim-in-a-comment
  hazard (shared protocol's bar preamble) arriving in the one place a completeness sweep is
  structurally not looking. An interpolated message carrying `{MAX_PARALLAX_BANDS}` is fine; the
  target is the hardcoded kind.
  **Operational form:** when a constant moves, grep the prose — help/usage strings, descriptions,
  docstrings, refusal text, comments — as a named third pass, and say you ran it.
  **⚠ NO LONGER RELAYED — THIS LANE NOW HAS TWO FIRSTHAND INSTANCES, BOTH FROM ONE PARCEL**
  (2026-08-27, the sprite-owner landing). The bar above was banked from sigil's mail and explicitly
  marked *not verified firsthand*. It is verified now, and the instances arrived from opposite
  directions, which is worth more than either alone.
  **(a) Found by the sigil lane, in THEIR tree, caused by OUR parcel.** `sprites_port.rs`'s header
  asserted the sprites region is *"same-LENGTH ($420 both)"*. The parcel grew the DEBUG shape and
  made it false. Nothing could have caught it: a bound stated in a doc comment is executed by
  nothing, so no gate can contradict it and the next reader simply learns something untrue.
  **They fixed it the right way and that half is the one people skip: they DELETED the number and
  pointed at where numbers live** (`pins::SPRITES.{plain,debug}_len`) rather than re-typing a fresh
  `$420`-shaped literal that would go stale on the identical clock. **Re-authoring a hardcoded bound
  one value later is the same defect with a newer date** — the fixture-vs-ceiling bar above, arriving
  in prose.
  **(b) Found HERE, in our tree, BEFORE it went stale.** `games/sonic4/player/player_common.emp`'s
  bound comment says `(PHYS_FALL_CAP = 16px)`. The owner's ruling takes that constant to 15. The
  `ensure` on the line below is DERIVED (`PBOUND_BOTTOM_MARGIN > (PHYS_FALL_CAP >> 8)`) and would
  keep passing correctly at 15 — **so the executable check survives and only the sentence goes
  wrong.** That is the class in its purest form: the gate stays green precisely while the prose
  starts lying. Booked into the `FALL-CAP-15` queue row so the comment is fixed in the same change.
  **The technique that found (a), contributed by the sigil lane and cheap enough to be a habit:
  when you touch a file, re-read the claims ADJACENT to your edit, not just the lines you changed.**
  They only looked at that header because they were checking whether their own edit had made a
  neighbouring claim staler. Name it as method rather than luck.
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
  **⚠ THIS SENTENCE REPLACES ONE THAT SAID THE OPPOSITE AND STOOD FOR TWENTY MINUTES — the wrong
  version was pushed, and the retraction is the most useful thing in this stanza.** It read *"the two
  fields scale differently and only one tracks the lowering population; `repin.toml`'s `tests` stays
  SINGLE-test"*, offering `DMA_Overflow_Count`'s one-test row at `repin.toml:1888` as a verified
  working precedent against three label rows (`dma_queue_port:139`, `dplc_port:471`,
  `bg_anim_port:404`).
  **Every measurement in it was right and the conclusion was wrong, because the precedent is
  UNFALSIFIABLE** (the sigil lane's, from reading what consumes the field — `repin.rs:167-186`).
  `tests` is read in exactly one place, only after a pin has already drifted, and only to print a
  *"rerun hint (affected binaries first…)"*. It does not gate, does not select what runs, does not
  affect `pins.rs` generation, **and nothing fails if it is incomplete.** So that row is not correct
  by design — it is **under-listed by two, in a field with no mechanism that could ever say so.**
  **The lesson is this file's own vacuity bar arriving on a PRECEDENT rather than on a gate.** My
  control fired correctly and I misread what it ruled out: I concluded *the field answers a different
  question* when the truth was *the field has no teeth*. **A row that cannot be wrong is not a
  validated example — and copying it propagates the defect**, which is what my four fresh rows were
  about to do. The cost is deferred and lands on a person: when one of those pins drifts a year from
  now, repin names one binary while three are affected, someone reruns the one, sees green, and two
  stale port tests go unexamined.
  **Test before adopting any precedent: name the mechanism that would have caught this row being
  wrong. If there is none, it is a habit with a good track record, not evidence.**
  *Scale, theirs and honestly bounded: their sweep finds 190 of 412 rows with a `tests` list omitting
  at least one test binary carrying the label — an UPPER bound, since it matches a quoted name
  anywhere in a test file, so some hits are comments. The mechanism and the `DMA_Overflow_Count`
  instance are source-confirmed; the 190 is not. Booked on their board, not fixed under our parcel.*
  `Dbg_PageIn_Preempts` is the same lowering shape on the vblank side (`vblank_port:139`,
  `game_loop_port:593`, `load_art_port`) — cite it for the label population, never for its `tests`
  row, which is in the same unfalsifiable population.
  **ENUMERATE BY WHAT LOWERS THE MODULE, NOT BY WHAT NAMES IT** — and read the enclosing block,
  because a path in a test file may be a mention. Measured populations: `engine/system/dma_queue.emp`
  is lowered by **three** (`dma_queue_port`, `dplc_port:437`, `bg_anim_port:362`);
  `engine/system/vblank.emp` by **three** (`vblank_port`, `game_loop_port:487`, `load_art_port:420`).
  The sigil lane found `dplc_port` as a trap beyond the obvious one; `bg_anim_port` sat under it, so
  the class had a third instance neither lane had named.
  **THE CONTROL FIRED CORRECTLY AND I DREW THE WRONG CONCLUSION FROM IT — that sequence is the
  durable half, and it is worth more than either version of the answer.** Having enumerated three
  lowerers, this overseer was about to ask for the full `tests` lists — which was RIGHT — then ran
  `DMA_Overflow_Count`'s row as a positive control, found it single-test and green, and **withdrew a
  correct proposal in favour of the precedent.** The retraction above is the sigil lane restoring the
  original answer by reading `repin.rs` rather than reading another row.
  **So the control was necessary and not sufficient, and the failure was in the inference, not the
  measurement.** A control tells you your model disagrees with the world; it does not tell you which
  of the two is wrong. **I assumed the artifact was right because it was committed, shipped and
  green** — the three properties an unfalsifiable field has for free.
  **Operational form: when a control refutes your model, the next question is what ENFORCES the
  control's subject.** If nothing does, the control has told you about a habit, not about a rule, and
  your model may be the correct half of the disagreement. One `grep` for where a config field is
  consumed distinguishes them, and it is the step neither this lane nor the precedent's author ever
  ran. *(Note also the direction the near-miss ran: the pleasing-invention tell this file carries
  twice did NOT apply here — the satisfying answer was the true one, and deference to a committed
  artifact is what nearly lost it. Suspicion of your own cleverness is not a general-purpose
  instrument.)*
  **Sequencing, agreed with the sigil lane:** `repin.toml` rows can be written ahead; `pins.rs`
  values **cannot**, because repin resolves addresses out of aeon's listings — so the aeon parcel
  must build and emit listings first, and a paired landing of this shape is one ordered chain with
  aeon as its back half.
  **Region gates move too, not just symbol resolution:** a parcel growing a routine a port test
  lowers will shift that test's region diff independently of any unresolved name. Lived: a ~71-line
  addition inside `VInt_Level`, which `game_loop_port` and `load_art_port` both lower and both
  annotate.
  *Supersedes the original wording of this bullet, which said to extend the contract-env helpers
  in sigil's `test_support.rs`. That is not where these symbols resolve; kept as a pointer
  because a reader who met the old sentence needs to know it was replaced, not merely absent.*
  **⚠ THE WORD "SILENTLY" IS NOW WRONG AND I HAVE DELETED IT (measured 2026-08-27).** The
  sprite-owner parcel put the first cross-seam reference to `Sprite_Owner` (`engine/ram.emp`)
  into `engine/objects/sprites.emp` and tripped exactly this, and the diagnostic was:
  *"unresolved symbolic absolute operand in section sprites references symbol `Sprite_Owner`
  not defined in this link — **expected when compiling a cross-seam module standalone; supply
  the map/harness composition that defines it**"*. It names the condition, the cause AND the
  remedy. Whatever changed on sigil's side since this note was written earned its keep; a
  warning that still said "silently" would have sent the next reader hunting for an invisible
  failure while a self-describing one sat in the log.
  **The class is worth keeping even though the symptom improved:** a `*_port` test compiles ONE
  module standalone, so a reference that is fine in the linked ROM is a hard failure there.
  Any parcel adding a first cross-seam name to a ported module owes the harness a composition,
  and this is a *paired* cost — the aeon change is correct and the sigil side still has to move.

- **TWO PARCELS INSIDE ONE A/B RANGE CANNOT BE SEPARATED BY DIFFERENCING ITS ENDS — AND BOTH
  LANES WILL REACH FOR THE ENDS** (added 2026-08-29, chain 179; the shared error, found by the
  sigil lane auditing this lane's pin description and resolved here with a third revision).
  Chain 179 froze aeon `4ba7cb92` against chain 178's pin at `b12c0141`, and **two byte-movers
  sat inside that range** — the sprite tilt and the insta-shield jump gate. Both lanes
  differenced 178 against 179, independently, and neither could attribute a single byte to
  either parcel, because attribution by differencing endpoints is *structurally* unavailable
  when more than one mover is inside. Each of us then reasoned about which parcel produced
  which delta, and both readings were wrong in different ways.
  **The resolution is one more revision, not one more argument.** `e1f412ed` is tilt-landed and
  shield-not, and reading `CharacterDefs` at all three settles it in one table:
  plain `0x11EA0 → 0x11F10 (+0x70 tilt) → 0x11F20 (+0x10 shield)`;
  debug `0x11FC0 → 0x12030 (+0x70 tilt) → 0x12030 (+0x00)`.
  **Operational form: before attributing bytes to a parcel, count the movers in the range. If
  it is more than one, the intermediate merge SHA IS the instrument** — it exists, it is free,
  and it is the only thing that can answer. The landing lane's own "serialize byte-movers,
  never batch two in one branch" rule exists for exactly this and says nothing about a FREEZE
  that spans two already-serialized branches, which is how the gap opened.
  *Note the shape: this was not carelessness on either side. Two lanes ran a sound method on a
  range that could not support it, and the method's failure is silent — differencing two
  endpoints always yields a number.*

- **A PIN FIELD MEASURES WHERE PINS ARE, NOT WHERE CODE IS — and its silence is an absence in
  the INSTRUMENT** (added 2026-08-29, same chain; the sigil lane's instance, against
  themselves, banked here because this lane's own instruments have the same property).
  Auditing chain 179, that lane measured that the debug shape's pin field never shows the
  insta-shield's bytes — max debug delta `+0x72` where plain reaches `+0x80` — and wrote it as
  *"the debug shape never receives the insta-shield's bytes."* **The bytes are there.** What was
  measured is that the *pin field* does not show them; slack before the next pinned symbol
  absorbs local growth, so the field is structurally blind to a change that does not push a pin.
  **This is bar 16(d) — absence-and-failure produce the same artifact — arriving on a POSITIVE,
  QUANTITATIVE instrument rather than an empty grep**, which is why it did not present as an
  inference needing a check. A field of real hex deltas reads as a measurement of the ROM; it is
  a measurement of the pin set.
  **What settled it was three witnesses of different kinds**, and the behavioural one is the only
  one that is not an inference: the new label present in BOTH listings at `+$10`; the routine's
  immediate neighbours moving `+14` in debug (`InstaShield_Spawn $1175C → $1176A`); and
  `tools/instashield_gate.py` decoding the DEBUG ROM's own bytes over 6,912 executions and
  reporting only `PSTATE_JUMP`/`PSTATE_ROLLJUMP` firing. **When an instrument reports an absence,
  ask what it is a census OF before reporting what is missing from the subject.**
  **Sub-finding, and it is the one most likely to recur: TWO CORRECT NUMBERS FOR TWO DIFFERENT
  QUANTITIES, WITH NOTHING SAYING WHICH.** This lane wrote 14 in a message and 16 in a commit and
  the discrepancy looked like an error in one of them. Both were right: **16** is the gate block
  (`.from_jump`'s offset, and what plain's tier delta `0x80−0x70` measures), **14** is the
  routine's NET growth (48 → 62 bytes), because the fix also lets `d1` carry the state byte into
  the roll-jump cancel that previously re-read it. The defect was never a wrong number — it was
  shipping two quantities under one name.

- **⚠ CHAIN 179's FREEZE COMMIT CARRIES A WRONG DESCRIPTION OF ITS OWN PIN MOVEMENT — DO NOT
  QUOTE IT; THE CORRECTION IS HERE AND OWES A LINE IN THE NEXT ENTRY'S PROSE.** `13a6d3c8`'s
  message says the field is *"uniform +0x80 plain / +0x70 debug"* with `PLAYER_SNAP_TO_SURFACE`
  as the single straddler. Measured over all 134 changed entries it is **three-tiered**: 21
  entries at `+0x70` in both shapes (the 13 `P_STATE_*` pins, 6 `PLAYER_*` regions, 2 bare
  u32s — plus `PLAYER_COMMON`, whose base does not move while its LENGTH grows `+0x70`, which is
  the tilt landing inside it); **2** straddlers at `+0x72` in both shapes — `PLAYER_SNAP_TO_SURFACE`
  **and `PLAYER_SET_STATE`**, and only the first was named; and 112 entries at `+0x80` plain /
  `+0x70` debug. The ROMs, the suite and the pins are all correct; only the prose is wrong.
  **The cause is worth more than the correction: that sentence was written from the TAIL of
  refreeze's output**, which shows the largest tier and the exception, and the visible sample was
  described as the field. That is this file's `head -N` bar with a scrolled terminal as the
  truncating instrument, and it is bar 23 (a commit message is a claim about a diff and nothing
  checks it) landing on a message written while thinking carefully about that exact diff.
  Repair by a note in the next chain entry's prose naming `13a6d3c8` — **never by rewriting a
  pushed freeze.**

- **DECLARED TREE — `/home/volence/sonic_hacks/.aeon-land-182`, do not sweep it.** A clean
  detached checkout of aeon `e99a2ca7`, the `aeon_rev` chain 182/183 is frozen at, carrying all
  four built shapes. `AEON_DIR` points here for anything asking what chain 182 actually froze.
  **`.aeon-land-180` and `.aeon-land-181` are RETIRED by this line** — say so here rather than
  deleting the line. The sigil-side `.sigil-pair-182` was transient and is removed: it held
  nothing that is not now at `origin/master`.

- **PUSH-BEFORE-ATTEST HAS A COST NOBODY PRICED, AND IT SHOWED UP ON ITS FIRST USE: A RED STRICT
  SUITE NOW LANDS ON MASTER BEFORE YOU KNOW IT IS RED** (added 2026-08-29, chain 182).
  The ritual adopted this session — push the freeze commit before `--attest`, because a revision
  already in `origin/master` cannot be orphaned by a later rebase — worked exactly as designed:
  the reachability check confirmed both revisions were ancestors before the suite ran, which is
  the property chain 181 lacked.
  **⚠ AND THIS LANE THEN CALLED THAT GREEN A SUCCESS FOR THE INSTRUMENT, WHICH IT IS NOT —
  corrected 2026-08-29 by the sigil lane, against their own tool.** Push-before-attest **puts
  both revisions on the remote first**, so REACHABLE was the only outcome available: the check
  could not have come back dirty. **That is the identical vacuity this lane caught in its own
  three-clean-chains flip condition an hour earlier, arriving on a peer's instrument and being
  read as a win.** Second instance in one session of a by-construction green mistaken for
  evidence, and the one this lane did NOT catch — the first was its own, this one needed the
  tool's author.
  **What the check still IS, stated so it is not now under-rated: a DEVIATION detector.** Green
  means the ritual was followed. It can no longer catch an orphan prospectively, because the
  ritual prevents the state rather than the check detecting it. **The discriminating half of that
  same run was the HISTORICAL walk** — 181 entries, 33 revisions, one `DIVERGENT` — which ran
  over a population nothing guaranteed clean. **Two different powers in one tool, and the
  by-construction half is the one that looked like the win.**
  *General form, and it is the sharpest thing in this file about gates: when a ritual is changed
  to PREVENT a state, every check for that state goes vacuous at the same moment — and it goes
  vacuous while continuing to print green, which reads as the fix being confirmed. Ask of any
  green beside a new ritual: could this have come back dirty, given what the ritual now
  guarantees? If not, it is witnessing compliance, not correctness.* **Then the suite went red, and sigil's `master` sat red between
  the freeze commit and the fix.**
  **The two hazards are traded against each other and the trade is not obviously correct.** An
  orphaned `sigil_rev` is permanent, invisible and passes every check forever; a red master is
  loud, temporary, and — because a freeze commit carries only goldens, size tables and pins —
  blocks nobody's build. That argues for the trade. What argues against it is that it fired on
  the FIRST use rather than eventually, so it is not a tail risk. **Flagged to the sigil lane as
  something to weigh when they enumerate the flows; it may argue for pushing the freeze to a ref
  that is not `master`.** Do not treat the ritual as settled until that is answered.
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
  **⚠ THE MECHANISM I WROTE HERE WAS WRONG, AND IT PROPAGATED FURTHER THAN THE MEASUREMENT DID —
  corrected 2026-08-29 by the sigil lane (sigil `1c595038`, verified reachable at their
  `origin/master` here, and `resolve_harness_root(&cwd, ROOT_OVERRIDE)` read firsthand at
  `src/bin/refreeze.rs:1037` at that tip).** This stanza said `refreeze` "has no `--harness-root`
  flag of its own and otherwise operates on the tree it was COMPILED in". **The first clause is
  true and the second is FALSE.** `refreeze` resolves its root from the **CURRENT WORKING
  DIRECTORY** (`git rev-parse --show-toplevel`), with `SIGIL_HARNESS_ROOT` as an *override*, not
  as the only steering. `--harness-root` is absent from the parent because it is the parent→child
  protocol *to* `repin`: refreeze derives the root and passes it down so the child cannot resolve
  a different one. Its absence is the design, not a gap.
  **What actually works is simpler than what I wrote: stand in the tree you mean to freeze.**
  Setting `SIGIL_HARNESS_ROOT` as well is harmless and still fine. **`SIGIL_BUILD` is the one that
  genuinely must be set** when aiming a prebuilt refreeze at a fresh worktree — it defaults to
  `<root>/target/release/sigil`, which a new worktree does not have, and `capture_goldens.sh`
  exits naming the path, so that one is friction rather than silence.
  **HOW I GOT IT WRONG, which is the reusable half.** Chain 180's freeze ran with the cwd **and**
  `SIGIL_HARNESS_ROOT` pointing at the same worktree. Both candidate causes were held equal **by
  construction**, so the run could not discriminate between them, and I credited the variable I
  had deliberately set. That is bar 5 — a clean result across inputs that only *looked* varied —
  arriving on a causal story rather than on a number. The sigil lane discriminated it in one
  command I never ran: the same binary, `--check`, from two directories, reading two different
  provenance chains (`ball-seating`/180 from the shared checkout, `migmask`/51 from
  `.worktrees/lane-c`).
  **AND THE COST WAS NEARLY REAL, WHICH IS WHY THIS IS A BAR AND NOT A FOOTNOTE.** My counts were
  exact and reproduced (`harness-root`: zero hits in `refreeze.rs`, two in `repin.rs`). **The
  explanation attached to them reached the sigil lane's own `OVERSEER.md`, a hub ruling, and an
  authorized fix inside one day** — a fix that would have made `refreeze` *refuse when
  `SIGIL_HARNESS_ROOT` is unset*, turning the normal invocation into a refusal in the middle of an
  unattended overnight freeze, guarding a hazard that does not exist. It was stopped only because
  that lane measured before implementing what it had been told.
  **The general form, theirs and kept in their words: an explanation propagates in a way a number
  does not.** A count travels as a count; a mechanism travels as a fact, gets built on, and turns
  into rulings and dispatch orders. **So report the measurement and flag the cause as the softer
  half of the message**, explicitly, every time — the asymmetry is not in how carefully each is
  checked, but in how far each travels once unchecked.
  **AND THE BINARY ANNOUNCES THE MISMATCH LOUDLY, WHICH IS A FEATURE TO USE RATHER THAN A WARNING
  TO WAVE PAST** — it prints *built from X, operating on Y … if it predates what you are about to
  ask it, rebuild it*. The check that discharges it is two commands, not a rebuild: `git log
  --since=<binary mtime> -- crates/` and `--stat` on whatever it returns. For chain 180 both
  intervening commits touched `golden/` data only, no Rust source, so the binary was current with
  its source and the rebuild was correctly skipped. **Run that check every time rather than
  remembering this result** — it is a fact about one night, not about the binary.
  **⚠ `refreeze` OUTLIVES A 10-MINUTE FOREGROUND TIMEOUT.** Chain 180's first attempt was killed
  at exactly 10m by the harness tool cap (a `timeout 1800` argument is clamped and does not help),
  leaving the worktree holding five half-captured goldens — recoverable with `git checkout -- .`
  in a *dedicated* worktree, which is one more reason not to do this in the shared checkout. Run
  `--freeze` and `--attest` as BACKGROUND commands. Also: `cmd | tail; echo $?` reports **tail's**
  exit status, not the tool's — redirect to a file and echo `$?` on the next line, or the one
  number the whole ritual turns on is the one you did not measure.
- **RETIRED — `/home/volence/sonic_hacks/.aeon-freeze-179`.** A clean
  detached checkout of aeon `4ba7cb92`, the `aeon_rev` chain 179 is frozen at, carrying all four
  built shapes and both `.lst` listings. It is the tree `AEON_DIR` should point at for anything
  asking what chain 179 actually froze, and rebuilding four shapes to recreate it is the
  expensive half of any artifact-dependent run.
  **Declared here BECAUSE OF THIS LANE'S OWN DEFECT (2026-08-27):** sweeping merged+detached
  worktrees under `~/sonic_hacks/`, this lane removed the sigil lane's standing reference tree,
  which was declared in *their* `OVERSEER.md` and invisible to every mechanical criterion. The
  remedy adopted then was "grep the other lanes' `OVERSEER.md` before removing anything under
  the shared root" — which only works if trees worth keeping are actually declared. **This is
  the other half of that remedy, and it is the half this lane had not yet done for itself.**
  Retire it when a later chain supersedes it, and say so here rather than deleting the line.
