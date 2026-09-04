# Aeon Overseer — log

Dated precedent narratives, incident write-ups and measurement transcripts split out of
`docs/OVERSEER.md` on 2026-09-02, when that file was 2,840 lines / 241,367 bytes against the
suite's boot-read bound of about 900 lines / 100 KB (empyrean `docs/OVERSEER-PROTOCOL.md`,
"The boot read is bounded", read at `f4d6d4b253ce8f3ef3ad7fffe1df5949c1f36c69`).

**This file is not read at boot.** Read it with `tail`/`grep`. Append new dated entries at
the end.

Every body below is VERBATIM — nothing was reworded, condensed or re-flowed on the way out.
Each entry is preceded by an anchor comment `<!-- @L<first>-<last> -->` giving the line span
the body occupied in `docs/OVERSEER.md` at commit 69104c87490b26a95dc7b9c4bf593e4f29d5f40b,
so head and log can be reassembled and diffed against that revision. Entries appear in that
file's order, earliest position first.

<!-- BODIES BELOW -->
<!-- @L22-31 -->
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
<!-- @L49-54 -->
> re-verified here at 10:03Z after the hub pushed on this lane's catch.** The interval is recorded
> because it was real: at 10:00Z the commit was present in the hub's clone and NOT an ancestor of
> `origin/main` — sigil's `AHEAD OF REMOTE`, structurally the same sentence as an orphan to
> anyone reading later, and actionable here only because the blob was readable in their tree. The
> bar it instances is **push before you ask anyone to cite it**, the same one this lane took for
> `--attest`. Re-check reachability anyway: this line ages, the check does not.
<!-- @L87-90 -->
> That is this file's own diagnosis of the class: **the artifact that supersedes a booking is a
> commit in a different tree, so there is no edge for anything to walk.** Nothing will notice for
> you. `lane-status.json` carries the current answer and is rewritten from the clock at every
> dispatch, ruling and landing; this block is rewritten only when someone remembers to.
<!-- @L112-116 -->
  Chain 190 moved assembled lengths (+38 in `ojz_effects`, 204/207 symbols sliding +32) and
  **owed no per-parcel term**; `repin_pins` ran 2 passed / 0 failed / 1 ignored. Left struck
  rather than deleted because this file's own first bar is that a stale sentence in a planning
  document is executed as a work order — and a lander following this one would have hand-written
  a term into a test that cannot read it.
<!-- @L143-152 -->
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
<!-- @L169-177 -->
  **Anchors, and one citation correction made in passing.** The feature merge is sigil
  `74793994` (`Merge branch 'feat/refreeze-attest'`), `--stat`-verified here as the commit that
  carries the code — it touches the harness plus every `*_port.rs`. The code-carrying commit
  under it is `e435333f`. Docs are `9040dc36` (their `origin/master` tip at the time of
  writing). **Sigil's message cited `729cd642` for "REFREEZE-NEEDS-STRICT is in"; that SHA is
  reachable and does touch `refreeze.rs`, but it is a `clippy -D warnings` fixup (2 files,
  8+/8-)** — a lint cleanup standing in for a feature merge. Exactly the SHA-class bar, caught
  by `--stat`-ing a citation from a lane that has been rigorous all night, which is the whole
  argument for checking every citation rather than suspecting particular peers.
<!-- @L192-196 -->
  This lane lost two freezes to `[killed]` with no exit status and no error anywhere, and spent a
  session on a correlation story (each kill coincided with an abnormal foreground call). **That
  story is DEMOTED.** Sigil got a controlled comparison by accident: the same work launched **as**
  a harness background task was reported killed — no OOM in `journalctl -k`, no orphan, swap fine
  — while the same work launched **detached** with `nohup … &`, watched by a separate background
<!-- @L199-201 -->
  It explains both properties that made this confusing: **no exit status** because the process
  never returned one, and **no error** because nothing went wrong. It also explains why the
  journal recovery worked perfectly — nothing was corrupt because nothing had failed.
<!-- @L221-223 -->
  *Free control that arrived unplanned: the thing that died carried NO stamp, and its log is
  indistinguishable by inspection from a completed run — which is the argument for the stamp,
  landing on the one process in the experiment that lacked it.*
<!-- @L237-242 -->
  *Recorded because of HOW it got here, which is the transferable part: the claim arrived from a
  peer, was persuasive, was banked in this file and in session memory in those words without
  being worked through, and would have been quoted AFTER a clean run as though the result proved
  something stronger than it did. Chain 197's freeze DID complete clean (`finished=0`) — the
  convenient direction, which is exactly when an unchecked claim gets promoted. The peer's own
  later message had it right and the two never met, because nothing re-reads a banked sentence.*
<!-- @L249-251 -->
  *And the miss worth keeping: this lane's own notes already recorded aurora's observation that
  `[killed]` is what the task harness writes when IT stops a task. The mechanism was sitting in
  the record, and a coincidence story got built on top of it instead of followed.*
<!-- @L255-267 -->
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
<!-- @L274-276 -->
  *Blast radius was bounded by the exact-path staging rule even with the branch check defeated —
  their commit touched only their own lane-log — which is evidence that rule earns its keep
  beyond the reason it was written for.*
<!-- @L290-295 -->
  **This supersedes the "seven" figure this file carried for one hour.** Seven was the output of
  *this lane's board audit* — entries both unsuperseded AND unsurfaced — reported as though it were
  the population that fails the READER. It is a strictly narrower set, and the difference is 24
  lines. *The correction came from the hub refusing a recalled number and asking for a measurement;
  the first measurement I ran off my own paraphrase of the predicate gave 23, and only transcribing
  the reader's actual predicate gave the true figure.*
<!-- @L298-304 -->
   22  options must list two or more
   19  option missing key
   19  option missing name
    4  recommend must be an object
    3  options missing
    3  recommend missing
    2  recommend.key names no option
<!-- @L371-375 -->
  *Worth keeping, because it argues for the fix rather than against the authors: the malformed shape
  is MORE readable to a human — "RESOLVED, not a question any more" in the question field tells a
  person the answer at a glance, where 8c's identical-question reproduction reads as an open card
  until you notice `supersedes`. Whoever wrote these was solving a real legibility problem. That is
  the case for the `answered` field, not for tolerating drift.*
<!-- @L402-407 -->
  `build.sh` runs the tool-suite pytest **before** it builds ("*the build tooling is broken, not
  just the ROM*"). `tools/demo_specialization_witness.py` — reached through
  `test_effects_gates_segments.py` — reads `s4.debug.lst` and `demo.debug.lst` **from disk**. So on
  a merge that both moves code and updates that pin: the listings on disk are still PRE-change, the
  pin in source is POST-change, the witness fails, the build refuses, and **the listings are never
  regenerated.** A deadlock, and it looks exactly like the parcel being wrong.
<!-- @L414-424 -->
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
<!-- @L429-434 -->
  They recommended freezing the `.lst` beside each golden ROM. They priced the benefit precisely —
  their own failure class, their own two wasted builds — declared the interest unprompted, argued it
  hard enough to move a ruling, and **did not look at how it would be implemented until after the
  ruling existed.** The implementation had a trap in it that would have frozen an off-canonical
  listing under a canonical name, deterministically, on the first run. **The cost of that would have
  landed in THIS lane's ritual, on their argument.**
<!-- @L443-450 -->
  **⚠ AND A CREDIT CORRECTION THAT IS THE ACTUAL LESSON, theirs, refusing praise for the wrong
  mechanism.** I wrote that their build-order sweep "ran against the change they had just
  recommended", i.e. that they audited their own win. **False: the sweep had finished hours earlier.**
  What happened is smaller and reproducible — they were *holding a named class* (**correctness that
  depends on invocation order, with no failing mode to observe**) and the new proposal walked into
  it. **The transferable form is "keep the class list where you will meet it", NOT "audit your own
  wins".** Stating it as vigilance would teach a habit nobody can perform on demand; stating it as
  a live class list is a thing this file can actually be.
<!-- @L455-473 -->
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
<!-- @L485-485 -->
  *Same class as everything else this night: absent rendered as a number.*
<!-- @L490-495 -->
  It returns `surfaces[]` — `statusLine | toast | palette | lens | titleBar` — each with `text`
  (what the player composed), `rendered` (what fits on the glass), `truncated`, and
  `unrenderable[]`. **Both `text` and `rendered` are served deliberately:** reading only `rendered`
  loses the reason inside a truncated message; reading only `text` reports strings that are **not on
  screen**. *Did the window tell the user X* wants `rendered`; *what did the player mean to say*
  wants `text`.
<!-- @L503-511 -->
  **⚠ AND WHAT IT DOES NOT DO, stated because the offer was framed as ending eyeball requests:
  it reads the emulator's own overlay, not the rendered game.** Everything this lane has asked the
  owner to LOOK at — the right-edge price, the background wrap, the colour bands — is game pixels,
  and `screen_text` cannot see them. Where it does help is anything drawn as debugger chrome, and
  the booked SCENE-READOUT item is the first candidate **if** that readout is chrome rather than
  game graphics — which is unmeasured and must be checked before the item is planned around it.
  `unrenderable[]` exists because the player has no glyph for a backtick or an em dash and draws a
  hollow box; an assertion against a literal containing either finds out through that field rather
  than by eye.
<!-- @L520-525 -->
  Measured here: `cmd | tail -3; echo "EXIT=${PIPESTATUS[0]}"` printed **`EXIT=`** (empty) more than
  once, and `cmd | head -2; echo $?` reported **head's** status, not the command's — which turned a
  real `exit 1` into a green-looking `0` while I was verifying a red-first proof. Sigil's three:
  a backgrounded run reported *"completed (exit code 0)"* while cargo was still executing (the `&`
  shell had exited, not the suite); a clean run reported *"failed with exit code 1"* because of a
  trailing `grep -c` finding no matches; and the same `grep -c` class again.
<!-- @L533-534 -->
  *Same family as the four instrument faults above: a value that is real, adjacent, and about
  something other than what you asked.*
<!-- @L540-550 -->
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
<!-- @L556-558 -->
  *The family: an instrument that includes itself in its own population. Same night as a `grep -c`
  counting a spelling, a `grep -c` printing 0 for a failed read, and a `git show $rev:path` eaten by
  a zsh history modifier — all four rendered ABSENCE or SELF as a confident value.*
<!-- @L562-570 -->
  This file's existing SHA rules all say the same thing: `--stat` a citation you RECEIVE. That is
  the half with a rule. Landing the band-spike capture, this overseer reported the commit as
  `8b23f0f` — **a hash typed from memory of a commit it had made itself four minutes earlier**,
  resolving in no object store anywhere. The hub could not open it and said so.
  **Why this is not the same bar arriving again.** Every prior instance was a citation to somebody
  else's work, checked or not. This one was never checked because it was never DOUBTED: it was my
  own commit, made by me, minutes old, and the feeling attached to it was memory rather than
  inference. **The receiving-side rule is structurally incapable of catching it — there is no
  incoming artifact to `--stat`.**
<!-- @L579-599 -->
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
<!-- @L603-607 -->
  The binary self-reports the revision it was linked at. After any docs-only commit over there —
  and their lane-log, decisions and OVERSEER writes are constant — that revision trails `HEAD`
  while the binary is byte-for-byte what `HEAD` would produce. **A reader who compares `--version`
  against `HEAD` gets STALE on a current binary, every time, and the natural response is a
  needless rebuild or, worse, distrust of a measurement that was fine.**
<!-- @L610-615 -->
  A rebuild landing on the identical md5 is the other one.
  **The composition, which is the durable half:** `--version` is a positive witness that the binary
  carries A revision and is **silent on behavioural equivalence to tip**; the crates-diff witnesses
  equivalence and is **silent on which binary you actually invoked**. Neither is sufficient and they
  fail in opposite directions — the same shape as the off-canonical table witnessing that a build
  ran while saying nothing about its source. Run both, or state which question you did not ask.
<!-- @L620-631 -->
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
<!-- @L641-652 -->
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
<!-- @L661-665 -->
  (`provenance.rs:125`: *tree identity, so an attestation cannot silently travel to a different
  pair of trees*), and unlike a dangling anchor nothing downstream could ever detect it. **A
  dangling anchor with a written reason beats a resolvable anchor that lies.** Neither lane
  hand-edits a generated ledger, so the mapping lives here and in the lane log, never in
  `provenance.toml`.
<!-- @L673-681 -->
  **And nothing validates it.** The field's check is `is_full_sha` — forty hex characters — so a
  **well-formed orphan passes forever**, and `--check` re-validates the chain without ever asking
  whether a recorded revision resolves. This is the absence family on a POSITIVE artifact: the
  entry is present, well-formed, inert, and indistinguishable from a good anchor. *(Sigil has
  queued the systemic fix on their side — reachability rather than well-formedness. It is their
  crate and their work; this lane's ask as its first consumer is that the red name the entry and
  the unreachable rev, and distinguish `unreachable from origin` (permanent, this case) from
  `not in this clone yet` (a missing fetch, transient), because those want different responses
  from whoever meets it.)*
<!-- @L698-706 -->
  **⚠ THE FLIP CONDITION AS THIS LANE FIRST STATED IT WAS REMEMBERED, NOT MEASURED — and the
  correction is the durable half.** It was written as *"three consecutive chains attested with
  the freeze already pushed and no warning fired"*, with the claim that this made the flip
  checkable rather than remembered. **It did not.** Warnings go to stderr and nothing durable
  records that one did or did not appear, so verifying the condition means counting three chains
  **and recalling** whether a warning fired in any of them — evidence that lives only in session
  context. **This lane's session was rotated tonight while holding exactly that class of state**,
  which is how the mapping write nearly got done twice and how the reasoning for *not*
  re-attesting nearly died with it.
<!-- @L713-718 -->
  *The general form, and it is the same preference that killed the opt-out flag and the exception
  list: prefer the assertion that needs nothing maintained. A remembered condition is a
  population of one, kept in a place that gets cleared.*
  *Recorded here rather than left in mail because it is a cross-lane COMMITMENT, and protocol bar
  20's sending-side half says state that lives only in correspondence does not survive a `/clear`.
  This lane made the ruling in a message and had to be reminded by its own file to bank it.*
<!-- @L723-727 -->
  **`refreeze --freeze` runs `repin` as its third step.** So a parcel that moves code makes every
  address pin stale, the port tests read those pins, and pre-flighting them BEFORE the freeze
  shows red **by construction** — then the freeze regenerates the pins and the attest is green.
  Pre-flighting without knowing that turns a correct gate into a phantom defect at exactly the
  moment you are trying to be careful.
<!-- @L737-739 -->
  *Lived: d-41 added a 4-byte write to `Parallax_Step5_Vscroll` and slid everything after parallax
  by +4 — 29 stale pins, 26 of them outside parallax entirely. `parallax_port` was simply the
  first gate to notice, and it was working perfectly.*
<!-- @L746-755 -->
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
<!-- @L760-771 -->
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
<!-- @L780-788 -->
  Proven red-first against the very failure it was written for: run on the chain-187 tree it
  names `Cache_Fill_Resume_Col`, verdicts *"pins were current, so these are REAL. Supply the
  composition BEFORE freezing"*, and exits 1 — in about two minutes, against the twenty that
  discovering it at `--attest` cost.
  *The script also carries the discriminator's meaning so a reader cannot invert it: pins STALE
  means the port reds are stale-instrument and the freeze clears them; pins CURRENT with a port
  still red is the cross-seam class and is real. It refuses on a `repin_pins` failure that is not
  staleness, rather than reading that as either.*

<!-- @L798-801 -->
  *Note what this does NOT change: the port tests are right, the diagnostic is excellent (it names
  the symbol and tells you to supply the composition), and the fix is documented and mechanical.
  This is purely about ORDER — the same information arriving before the expensive step instead of
  after it.*
<!-- @L815-823 -->
  `build.sh` takes `SIGIL_BUILD` (`:558`) and `SIGIL_EMIT` (`:317`) **from the environment**.
  Nothing in a checkout pins either, and `SIGIL_EMIT` *writes* `engine/sound/generated/` — one
  of the directories whose drift was being investigated. So a pinned tracked tree, `git status`
  clean throughout, can build a different ROM tomorrow with **no cause visible in the tree at
  all**. Lived: a `git clone` fixture built `4b4f1b5b` at 00:58 and `f33b157e` at 03:35, and the
  only thing that changed was that `emit_sound_blob` and `sigil` were rebuilt underneath it.
  **`build.sh:266` already prints `Assembler: sigil <rev>` for exactly this class** (the
  three-days-behind incident in its own header). The gap is that nobody records the banner
  beside the CRC they cite.
<!-- @L832-842 -->
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
<!-- @L864-892 -->
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
<!-- @L897-927 -->
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
<!-- @L941-945 -->
  *Three instances of the assembler moving under a measurement in one night: this lane's own
  sprite-owner A/B (re-derived after asking sigil to rebuild), the gates parcel's agent
  (caught it mid-run and re-derived its baseline unprompted), and aurora's fixture (not caught,
  and it produced a wrong CRC plus two wrong explanations). Two of three were caught by
  vigilance rather than by any gate, which is the argument for the banner rule.*
<!-- @L951-961 -->
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
<!-- @L969-974 -->
  caught by one exit code). Advancing a landing worktree to a new SHA, the four CRCs came
  back matching the pins exactly — from a build that **never ran**. `git checkout` gives
  `project.json` a fresh mtime, `level staleness` hard-fails *before* a ROM is emitted, and
  the ROMs on disk were **leftovers from the previous build at the previous SHA**. Because
  the parcel was zero-byte, leftover and correct are byte-identical: **a CRC check cannot
  distinguish "built at the new SHA" from "never rebuilt at all."** The only tell was the
<!-- @L989-999 -->
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
<!-- @L1022-1028 -->
  Lived: P3 T11-T16 were six consecutive zero-byte parcels (CRCs held at `060401e4` /
  `0dbaa80f` / `c708b114` / `dec88cc1` throughout — the identity we verified and cited at
  every landing), and `layout.odd-field` began firing on the sonic4 corpus somewhere in
  them with no adjudication and no baseline update. The last baseline freeze is sigil
  `40f862e2` (2026-08-21T14:23, pairing aeon T10 `3c68ee11` at 14:06); aeon T11
  `b0b85f47` merged at **14:57**, *after* it — so **T11 is outside both the baseline and
  any diff range that starts at T11's own merge commit**, which is the natural range to
<!-- @L1047-1052 -->
Lived 2026-08-22: recovering the profiler-corpus ROM (`d22dda85`), this overseer checked
`sigil master:crates/sigil-harness/golden/s4.debug.bin`, truthfully found `0dbaa80f` (correct for
master), reported "no committed blob shortcuts it", and was one step from a rebuild parcel. **The
blob was sitting at `7b46f075`** — the `refreeze: raster-cram-anchor-366` commit whose own message
named the paired golden move. A golden path is a MOVING POINTER: for a vintage artifact, the tip is
the one revision guaranteed not to have it.
<!-- @L1073-1077 -->

Live interaction in THIS file, so read it deliberately: the landing lane's clean-checkout rule
pins `AEON_DIR` at a committed SHA. That is correct for **reproducibility** (freeze the artifact
you actually measured) and would be WRONG for a currency question — a sigil port gate asked "does
aeon still satisfy this contract *today*" must not be pointed at a pin.
<!-- @L1084-1089 -->
and the cited `7bdb75f` in their message is the DOCS commit, not the code). The three probes
may migrate whenever a parcel wants them to; **nothing on this queue waits on it, and it was
never "aeon's profiler migration".** The paired outcome: **our `PROF-RING-SELF` ask is
WITHDRAWN** — a bucket's `self_cycles` is the exception entry alone, so the field we asked for
would have been exact and useless, and the fix delivers the quantity on the fields we already
read. Full derivation and our error class in `docs/DEFERRED_WORK.md`.
<!-- @L1091-1128 -->
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
<!-- @L1135-1138 -->
Their determinism sweep was run as an enumeration, not a conclusion (zero
`Instant::now`/`SystemTime`/`sleep` in core; no `HashMap`/`HashSet` iteration; no `rand` —
`rng.rs` is a hand-rolled SplitMix64 seeded from a constant; `forbid(unsafe_code)`; floats
confined to `src/synth/`; wall-clock pacing at exactly one site, disabled by `--no-pace`).
<!-- @L1147-1168 -->
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
<!-- @L1175-1209 -->
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
<!-- @L1214-1344 -->
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
<!-- @L1366-1389 -->
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
<!-- @L1398-1405 -->
  ~~So the named ask is HALF discharged, at the aggregate and not per-frame.~~ **STRUCK 2026-08-26, on oracle's live
  measurement against our own ROM (oracle `4915ed9` docs, code `4111c88` under `51143a5`): a bucket's
  `cyclesSelf` is the exception entry alone — `cyclesSelfTotal / callsTotal` is EXACTLY 44.00 for both
  `vint` (9,830 cyc/call) and `hint` (514 cyc/call) — so a per-frame self field would print 44 every
  frame and discriminate nothing. `sum(perFrame[].vintCycles) == interrupts.vint.cyclesTotal` to the cycle
  (119/119 frames), so the column we already read IS the per-frame quantity. The 'half that matters' was
  a field that could not carry information; nothing remains of the ask. Migration of the three probes is
  unblocked on this count.** Spawn through
<!-- @L1421-1426 -->
  **Measured here, so the next session does not re-derive it: this lane's tools are structurally
  unexposed.** Zero hits for `content[0]` / `"content"` anywhere in `tools/` (positive control:
  12 files match `aether_instance|jsonrpc`, so the grep was live), and the seam
  `tools/aether_instance.py` reaches the emulator through `from aether import BusClient` — a
  direct bus client, **not the MCP shim**. The exposure is to an INTERACTIVE session calling
  `mcp__oracle__emulator_status` by hand, which reads the blocks as text anyway.
<!-- @L1441-1449 -->

**What it cost, so nobody re-derives the caution from the surviving prose:** 38 files of
the owner's own Aurora work — two saves (2026-08-19, 2026-08-20) plus the re-bake they
triggered — sat uncommitted for days. The heuristic also over-reached: the re-bake rewrites
`data/collision/` and `data/generated/`, which were **never** daemon territory, so an
"editor churn, not ours" reading applied to the whole `data/` blob orphaned the derived
half as well. `.gitignore` lines 103-115 explicitly **negate** those paths and say why (the
generators read out-of-repo donors and cannot run in the build), so "generated, therefore
ignorable" is wrong and the repo already argues against it.
<!-- @L1451-1454 -->
**The failure mode is the durable part: an ownership claim fails SILENTLY AND
PERMISSIVELY.** Nothing errors, no gate trips — the work simply never lands, and every
session that reads the note reproduces the omission. Fourth of the day's stale-hazard
family and the most expensive, because the others cost effort and this one cost data
<!-- @L1463-1473 -->
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
<!-- @L1482-1497 -->
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
<!-- @L1506-1523 -->
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
<!-- @L1529-1552 -->
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
<!-- @L1565-1568 -->
  *Cost accounting, because it argues for rule 1 rather than for vigilance: the main checkout was
  in this state only because the owner's `d-44` edit sits unruled on a file the parcel
  regenerates. An unanswered decision created a tree that could not merge, which invited the
  shortcut, which destroyed the parcel. **The unanswered question was upstream of the outage.***
<!-- @L1574-1586 -->
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
<!-- @L1592-1599 -->
  *Why the sigil lane rates it: their motivating case was fresh goldens beside stale size tables —
  bad, but every artifact is PRESENT and a reader can compare them. Here the artifact is absent
  and the absence is unreportable by the usual instrument, which is bar 16(d)'s family arriving on
  a build tree instead of on a command's output.*
  *This is also the argument this lane used to CLEAR their freeze-journal parcel to land ahead of
  chain 184's freeze rather than holding it: the hazard is real, measured, and hit once already —
  and the parcel's `--freeze` deliberately announces-and-replaces instead of refusing, so the
  recovery detector cannot brick the recovery.*
<!-- @L1604-1615 -->
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
<!-- @L1628-1632 -->
  `diag/warp-parallax-reresolve` holds a diagnosis with **zero hits in `DEFERRED_WORK.md`** plus
  `tools/warp_arrival_stability_probe.py`, and `diag/showcase-invisible` holds
  `tools/showcase_diag_*.py` whose findings are banked while the tools are not. **Deleting either
  would have lost work with nothing to announce it.** The owner's directive was explicitly to
  report a verdict per tree rather than delete on a guess, and that is why.
<!-- @L1663-1675 -->
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
<!-- @L1683-1690 -->
  and from that moment a running build depended on the binary again. The grant never expired in
  words; **the conditions under it changed**, and neither lane re-read it. The relink was then
  found in an `mtime` rather than in a message.
  **This is the snapshot problem (shared-protocol bar 22) arriving on PERMISSIONS.** Both lanes
  had spent the night being careful that a peer's *status file* goes stale in minutes. A granted
  permission is the same class and is worse in one respect: a status file at least carries an
  `updatedAt`, so a reader can weigh it. **A permission reads as a standing state because it was
  phrased as one, and carries nothing to date it.**
<!-- @L1699-1703 -->
  **(a) IT WAS BILATERAL, SO IT SILENTLY EXCLUDED EVERYONE UNNAMED.** This lane asked for the
  hold, so sigil agreed the announcement rule *with this lane*. **The aurora lane was building
  against that same binary and was in none of the conversation** — they were mid-build when the
  relink landed, and found out by watching a pid. **The holder of a shared artifact cannot
  enumerate who depends on it**, so a two-party agreement covers the two parties and reads as
<!-- @L1718-1720 -->
  They built the check around it faithfully — and **a revision pin cannot detect a relink**,
  because it names a property of the **source** while the thing that ran is a **file**. Two
  revisions can produce one binary; one revision can produce two; the pin is silent on both, and
<!-- @L1728-1747 -->
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
<!-- @L1763-1781 -->
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
<!-- @L1809-1829 -->
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
<!-- @L1853-1871 -->
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
<!-- @L1886-1894 -->
  Twice this session a peer refuted a claim of this lane's that **every check either lane was
  running had passed**: a flip condition whose safety property was supplied only by asserting it,
  and a reachability green called "the instrument doing its job" when the ritual guaranteed that
  green. Neither was a measurement error. Both were errors in the reasoning *about* an
  instrument, made while the measurements were being handled carefully.
  **The catches were possible only because the reasoning was WRITTEN DOWN in a form that could be
  shown false.** *"Attest passed, reachability green"* would have been exactly as wrong, and
  **unfalsifiable — and it would have read as more competent, not less**, because a bare verdict
  carries no visible surface to attack.
<!-- @L1903-1923 -->
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
<!-- @L1929-1958 -->
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
<!-- @L1962-1966 -->
  *Composes with the opposite failure this file already carries in quantity — the gate that passes
  for the wrong reason. Both are the same defect at different signs: a check whose firing is
  uncorrelated with the thing it names. The vacuous-pass family is better represented here only
  because a false green leaves no one arguing with it, while a false red gets routed around within
  the hour and looks like it was fixed.*
<!-- @L1971-1985 -->
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
<!-- @L1990-1993 -->
  *Note the asymmetry with the tooling this lane already has: `updatedAt` in `lane-status.json` is
  protected by a rule that says take it from `date -u`, precisely because a hand-written time is
  untrustworthy. That rule guards the field nobody reasons from and left unguarded the times this
  lane actually builds arguments on.*
<!-- @L1998-2002 -->
  `tools/level_staleness.py` compares `newest mtime(editor sources) > newest mtime(generated
  tree)`. In a fresh `git worktree add`, git writes **every** file within the same second, so `>`
  is false **by construction** — the gate cannot fail there whatever the tree contains. That is
  precisely why it could not see the floor fix missing from the ROM: a green sat beside the defect
  the whole time.
<!-- @L2007-2011 -->
  **This is bar 25 (a green log and an absent run are the same artifact) with the absence created
  by the ENVIRONMENT rather than by a missing flag** — and it is worse in one respect: a missing
  flag is a fact about a command someone can inspect, while this is a fact about the *filesystem
  state* the command met, which appears nowhere in its output. Ask it of any gate before quoting
  a pass, and especially of one you are running somewhere other than where it was written for.
<!-- @L2015-2025 -->
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
<!-- @L2034-2040 -->
  Relaying the owner's d-37 ruling, the hub added *"keep the script's refusal (exactly the expected
  cells carrying `$1472`, nothing else) as is"*. **That constraint was the relayer's invention.**
  The tool does the opposite by design — its docstring says *nothing here is a literal cell word*
  and it matches on **resolved geometry** — and the invented constraint was also WRONG: measured
  here, 300 cells carry the literal word, the tool targets 150 pinholes, and only 146 of those are
  tops of `$1472` columns, so **four repaired cells are not that word at all**. A refusal narrowed
  to the literal would have left four holes in the owner's floor and reported success.
<!-- @L2057-2069 -->
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
<!-- @L2076-2080 -->
  Three instances in one chain, all of which came out green: `cmd | tail; echo $?` reports **tail's**
  status, and the sigil lane's pushes were safe all night only because their reflex is to verify
  against `git ls-remote` — a positive artifact — rather than an exit code; this lane's freeze
  survived a mid-capture kill only because it happened to be in a dedicated worktree; and the
  miscitation above cost nothing only because the reader's instinct covered it.
<!-- @L2089-2095 -->
  sigil lane). Tracing why one `embed()` in `engine/system/math.emp` resolves when the resolver's
  boundary check says it should not, this lane found a **per-module `embed_base` override** in
  sigil's `resolve/mod.rs` — real code, with a comment naming the exact puzzle — and reported it
  as *the mechanism you could not locate*. **It is a mechanism. Nothing established that it is
  the one that fires**: `embed_base_for` is a caller-supplied closure, and every caller either
  lane could find is **module-INDEPENDENT** (`&|_| opts.embed_base.clone()`, `move |_id|
  Some(aeon_root.clone())`), so on the ROM path the override may be present and never exercised.
<!-- @L2109-2119 -->
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
<!-- @L2124-2128 -->
  **⚠ THIS FILE'S OWN EXPOSURE, MEASURED: 176 lines mention `sigil`/`oracle`/`aurora`; 11 carry a
  peer revision.** *(That 176 is mentions, not claims — an upper bound, and the sweep is one
  spelling axis. The ratio is the signal, not the number.)* **Retrofitting all of them is not
  proposed; the rule binds NEW assertions**, and an old one gets its anchor the next time anyone
  relies on it.
<!-- @L2141-2150 -->
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
<!-- @L2158-2172 -->
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
<!-- @L2198-2209 -->
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
<!-- @L2233-2236 -->
  caveat that had been false since a commit that was an ANCESTOR of the assessment's own
  survey pin, plus a ruling aimed at a field the sibling's save path never writes. A
  quoted survey, roadmap, or plan caveat can be stale before its pin; only reading the
  described tree catches it. Peer verification found both — reciprocate it.
<!-- @L2283-2290 -->
  list a SUBSET of labels, so content between two listed labels is **invisible in them by
  construction**. This lane, the aurora lane, and this repo's own booking all read the
  `[HeightMapsRot+0x2000, Dac_Temp_Blip)` gap as ~119,072 B of slack; `s4.debug.lst:2225-2229`
  shows `AngleTable`/`SolidityTable`/`Map_Sonic`/`DPLC_Sonic`/`Art_Sonic` filling it, and the
  ROM image is only **43.8% zero** across that span. Real free tail: **11,427 B** at
  `0x4535D`, by constant-byte run scan — and even that is padding inside `Art_Sonic`'s
  allotment (offset 97,469, `mod 32 == 29`, so not whole blank tiles), i.e. growing room for
  the most growth-prone object in the region rather than unowned space.
<!-- @L2297-2299 -->
  Corollary, from the same episode: an arithmetic step built ON TOP of somebody's number
  looks like corroboration and is propagation — aurora re-derived a margin from this lane's
  bad figure and the agreement read as two sources.
<!-- @L2304-2318 -->
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
<!-- @L2327-2345 -->
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
<!-- @L2356-2365 -->
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
<!-- @L2375-2385 -->
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
<!-- @L2398-2412 -->
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
<!-- @L2423-2433 -->
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
<!-- @L2444-2453 -->
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
<!-- @L2460-2466 -->
  **Price the result honestly, per row** (their own caveat, volunteered against their own gate
  after their agent overstated it and corrected itself): recomputation makes every value
  checked, but the COMPARISONS differ in kind. Where two tools independently produce the value,
  it is a second witness; where one artifact holds a **copy** of another taken at freeze time,
  the comparison is **temporal, not independent** — it catches a half-done landing, which is
  worth catching, and is not corroboration. Do not report such a gate as "N independent
  witnesses"; say which rows are independent and which are temporal.
<!-- @L2478-2481 -->
  blip bank at `$48000` (bank `$9`) and the shared drum bank at `$50000` (bank `$A`). The
  2026-08-26 re-layout moved them — `map.toml` records `dac_banks = 0x90000` (bank `$12`, shared
  `0x98000` = `$13`) and the `.lst` puts `Dac_Temp_Blip` at `0x90000`. **Four sites, wrong in both
  address and bank id, and no gate could contradict them because nothing executes a header.**
<!-- @L2512-2517 -->
  **Why it is worse than a stale code constant rather than more benign:** a stale bound in code
  eventually fails a gate; a stale bound in prose **teaches the next reader something false and
  is never executed**, so nothing can ever contradict it. It is the perishable-claim-in-a-comment
  hazard (shared protocol's bar preamble) arriving in the one place a completeness sweep is
  structurally not looking. An interpolated message carrying `{MAX_PARALLAX_BANDS}` is fine; the
  target is the hardcoded kind.
<!-- @L2520-2542 -->
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
<!-- @L2566-2617 -->
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
<!-- @L2626-2637 -->
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
<!-- @L2646-2655 -->
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
<!-- @L2661-2663 -->
  *Note the shape: this was not carelessness on either side. Two lanes ran a sound method on a
  range that could not support it, and the method's failure is silent — differencing two
  endpoints always yields a number.*
<!-- @L2668-2680 -->
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
<!-- @L2683-2689 -->
  **Sub-finding, and it is the one most likely to recur: TWO CORRECT NUMBERS FOR TWO DIFFERENT
  QUANTITIES, WITH NOTHING SAYING WHICH.** This lane wrote 14 in a message and 16 in a commit and
  the discrepancy looked like an error in one of them. Both were right: **16** is the gate block
  (`.from_jump`'s offset, and what plain's tier delta `0x80−0x70` measures), **14** is the
  routine's NET growth (48 → 62 bytes), because the fix also lets `d1` carry the state byte into
  the roll-jump cancel that previously re-read it. The defect was never a wrong number — it was
  shipping two quantities under one name.
<!-- @L2693-2706 -->
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
<!-- @L2717-2734 -->
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
<!-- @L2741-2747 -->
  **The two hazards are traded against each other and the trade is not obviously correct.** An
  orphaned `sigil_rev` is permanent, invisible and passes every check forever; a red master is
  loud, temporary, and — because a freeze commit carries only goldens, size tables and pins —
  blocks nobody's build. That argues for the trade. What argues against it is that it fired on
  the FIRST use rather than eventually, so it is not a tail risk. **Flagged to the sigil lane as
  something to weigh when they enumerate the flows; it may argue for pushing the freeze to a ref
  that is not `master`.** Do not treat the ritual as settled until that is answered.
<!-- @L2767-2776 -->
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
<!-- @L2782-2801 -->
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
<!-- @L2809-2815 -->
  **⚠ `refreeze` OUTLIVES A 10-MINUTE FOREGROUND TIMEOUT.** Chain 180's first attempt was killed
  at exactly 10m by the harness tool cap (a `timeout 1800` argument is clamped and does not help),
  leaving the worktree holding five half-captured goldens — recoverable with `git checkout -- .`
  in a *dedicated* worktree, which is one more reason not to do this in the shared checkout. Run
  `--freeze` and `--attest` as BACKGROUND commands. Also: `cmd | tail; echo $?` reports **tail's**
  exit status, not the tool's — redirect to a file and echo `$?` on the next line, or the one
  number the whole ritual turns on is the one you did not measure.
<!-- @L2821-2827 -->
  **Declared here BECAUSE OF THIS LANE'S OWN DEFECT (2026-08-27):** sweeping merged+detached
  worktrees under `~/sonic_hacks/`, this lane removed the sigil lane's standing reference tree,
  which was declared in *their* `OVERSEER.md` and invisible to every mechanical criterion. The
  remedy adopted then was "grep the other lanes' `OVERSEER.md` before removing anything under
  the shared root" — which only works if trees worth keeping are actually declared. **This is
  the other half of that remedy, and it is the half this lane had not yet done for itself.**
  Retire it when a later chain supersedes it, and say so here rather than deleting the line.


<!-- @MOVED 2026-09-02: the 31-row ruled-not-to-repair set, moved out of the head under the
     boot-read bound. VERBATIM, 32 lines. The RULING and the 8c trap stay in OVERSEER.md;
     the generated fixture tools/fixtures/decisions_ruled_unrepaired.json is the authority. -->
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


## Second pass — 2026-09-04, boot-read bound

Closed history moved out of `docs/OVERSEER.md` on 2026-09-04 under the same suite ruling as the
2026-09-02 split (empyrean `docs/OVERSEER-PROTOCOL.md`, "The boot read is bounded", read at
`origin/main`). Every body below is VERBATIM. Anchors `<!-- @L<first>-<last> -->` give the line
span the body occupied in `docs/OVERSEER.md` at commit 7accc2ef13a95ffa261f4868e422d1f20d3885d6 — NOT at the
commit the 2026-09-02 anchors above refer to. Entries are in that file's order.

<!-- @L137-140 -->
*(landing lane: the hand-typed baseline test, STRUCK 2026-08-30 and RETIRED in sigil)*

  ~~The hand-typed baseline test (`repin_pins.rs`) demands a per-parcel term with its story
  when assembled lengths move.~~ **STRUCK 2026-08-30, measured, not assumed.** That test is
  RETIRED: `secondary_pin_classes_match_the_hand_typed_baseline` reports
  `ignored, RETIRED by Wave-B B-0 (packed placement): this test asserts literal pin VALUES`.

<!-- @L224-230 -->
*(landing lane: the detached-freeze bullet's correction of its own earlier wording)*

  **⚠ CORRECTED 2026-09-02, AND THE CORRECTION MATTERS MORE THAN THE RULE. This bullet first
  read: "a clean completion REFUTES the harness story rather than merely failing to confirm it."
  THAT IS BACKWARDS.** The hypothesis predicts that a detached run survives, so a clean
  completion **CONFIRMS** it — weakly, at n=1. **A detached DEATH is what would refute it**, which
  is why the death is the more valuable outcome. What a clean run refutes is the *competing*
  story — the freeze is fragile, memory pressure kills it — and that is probably what the
  sentence was reaching for, but it is not what it said.

<!-- @L259-260 -->
*(landing lane: the 86/55/31 ledger measurement (the reasons list it introduces was moved 2026-09-02))*

  **MEASURED: 86 lines · 55 parse · 31 REJECTED**, counted per LINE. Predicate transcribed from
  dominion `796bc1e` `server/src/decisions.ts`. Reasons (collected, so one line carries several):

<!-- @L289-295 -->
*(landing lane: which four closures were out of shape, under a ruling that forbids repairing them)*

  `docs/decisions.jsonl` closes a decision per `contract/DECISIONS.md` rule 8c: append an entry with
  `supersedes` set to the settled id and the question/options/recommend reproduced identically.
  **These four closures did not do that.** Each was filed as a NEW id with `supersedes: null` and the
  resolution written into the `question` field as a statement: `d-45-answered`, `d-46-downgraded`,
  `d-47-revised-answered`, `vram-replan-deferred` — leaving their originals `d-45`, `d-46`,
  `d-47-revised`, `vram-replan` unsuperseded too. **So each closure leaves TWO open-looking cards
  instead of zero**, seven entries in total.

<!-- @L653-656 -->
*(instruments: the 2026-08-24 straddle hold, lifted)*

**✅ HOLD LIFTED 2026-08-24 — read this before the block below, which is kept for its
mechanism and its scope note only.** Oracle fixed the straddle defect (red-first tests
`68461a7`, fix `4111c88`, merged `51143a5` — verified reachable at their `origin/main` here,


<!-- @L920-924 -->
*(bars: the byte-decomposition instance under the re-derive-the-arithmetic bar)*

  Lived: told that the causal story behind a byte decomposition was backwards, this lane replied
  *"the arithmetic was right and the word 'leaving' was the whole defect"*. The arithmetic was the
  part that was wrong. Chain 198's frozen prose says *"release +93 = 62 content + 31 appendix"*;
  measured, it is +0 assembled / +93 appendix, because the content is absorbed at the org anchor
  and never reaches the file end — and the entry's own held `anchor_end` refutes it.

<!-- @L950-953 -->
*(bars: the overwritten-binary cost under the same bar)*

  **A second cost, and it is permanent: the binary that produced entry 198's goldens was
  overwritten IN PLACE at the same path.** It no longer exists to compare against and is
  recoverable only by rebuilding at 079cec97. A shared artifact pinned by md5 tells you it moved;
  it does not give you back the thing that moved.

<!-- @L1294-1306 -->
*(bars: the stale DAC/sound-bank anchor prose sweep, CLOSED 2026-08-29)*

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

<!-- @L1448-1460 -->
*(the dated tail: 2026-08-30T16:25Z d-41 correction)*


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
