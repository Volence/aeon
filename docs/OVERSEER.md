# Aeon Overseer

**Boot prompt** (paste into a fresh session started in this repo):

> You're the overseer for this repo. Read `docs/OVERSEER.md` first, then
> `../empyrean/docs/OVERSEER-PROTOCOL.md`. Work the queue. Peers may or may not be
> running — check `ListAgents`; coordinate if present, proceed solo if not.

The role, delegation discipline, review bars, and peer protocol live in the shared
protocol doc. This file is what's aeon-specific.

## The queue

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
  The hand-typed baseline test (`repin_pins.rs`) demands a per-parcel term with its story
  when assembled lengths move.

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
  reading: still do not quote it, but expect it to start telling the truth after the next
  sigil rebuild rather than after a fix landing. So the word `dirty` sits beside every CRC this repo quotes and
  **cannot vary**, which makes it exactly the thing this file has spent the night naming: a
  field that reads as a signal and is a constant. The discriminating half is inside the same
  string (`0 modified` vs `N modified`); the summary word is what over-warns, which is the
  `GOLDEN-DIRTY-BANNER` item already booked to the sigil lane.
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
  *every* fresh checkout of any tree containing it trips the staleness gate on mtime alone;
  **⚠ THE WORD "FRESH" IS WRONG — corrected 2026-08-27 by the sigil lane, who MEASURED it on two
  worktrees where this note predicted a stop and none occurred.** The gate compares
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

**Two capability facts that bite:** breakpoints and `wait_for_break` **do not exist** on the
Rust server (`capabilities.breakpoints: false`) — for an arm→wait→clear flow use
`run_to{symbol}` today; the real parcel is breakpoints + `wait_for_break` shipping together
and has no date. And **we are already driving the Rust server headlessly** — 8 of our tools
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
3. **No breakpoints, no `wait_for_break`** (`capabilities.breakpoints: false`). Use
   `emulator/run_to {"addr"|"symbol", "maxFrames"}` and CHECK `reached` — it parks at an
   instruction boundary with the target instruction not yet executed, which is the same stop
   rule the breakpoint gates were written against (proved: `snapshot_poison` captures the
   same mask %0101 at the same PC on both servers).
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
"0.0.0"` / 41 methods / `capabilities.breakpoints: false`; legacy `serverName "oracle"` /
`"2.1-linux"` / 53 methods / no `breakpoints` key. So: `implementation` when present is the
only thing consulted; when absent, `serverName == "oracle-next"` stands in. **Delete rung 2
the day oracle's release binaries are rebuilt.** Proof it is not vacuous:
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
  **The durable half is their distinction, not the near miss.** Sigil's byte gates build ROMs
  through the library **compiled into the test binaries**, never through `target/release/sigil`.
  So a fully green sigil suite is real evidence that an emitter change is byte-neutral, and is
  **no evidence at all** that the CLI binary `build.sh` invokes is current. Two artifacts, one
  checked, and the unchecked one is the one that produces every CRC we freeze.
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
- Cycle claims near VDP ports: the bus absorbs adjacent OPERAND accesses but not
  instruction-stream fetches — nominal tables mispriced three consecutive parcels.
  Measure with the cost lane; the F-series/dense rows re-derive from shipped constants.
- Raster spins are SOLVED (`raster_dsl.emp`'s solver from the measured window anchor);
  a parcel that hand-adjusts a spin or a cost-gate expectation is wrong by definition.
- `.emp` comptime work: `docs/EMP_PITFALLS.md` first, every time.
- Cross-seam `Game.*`/`CAP_*` references: a FIRST reference in a module sigil's port
  harness compiles standalone breaks its `*_port` tests silently — extend the
  contract-env helpers in sigil's `test_support.rs`, values parsed from aeon source.
