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
  moved) → sigil `refreeze --freeze NAME --ab <prose evidence>` → full sigil suite
  (`cargo test --release --workspace --no-fail-fast`, aggregate totals; the fully-green
  bar moves — derive it, don't quote this file) → push both. `refreeze --check` is NOT
  the goldens. The hand-typed baseline test (`repin_pins.rs`) demands a per-parcel
  term with its story when assembled lengths move.
- One byte-mover per branch. Serialize refreezes. When any session is live-editing
  content in the main tree, build + freeze from a CLEAN CHECKOUT of the merge SHA.
  **The clean checkout must be threaded through ALL THREE legs explicitly** (lived
  2026-08-20): `repin -- --aeon <clean>`, `refreeze` with `AEON_DIR=<clean>`, AND the
  full suite with `AEON_DIR=<clean>` — each defaults to the sibling main tree on its
  own. The tell for a dirty-tree repin is region pins shifting in lockstep (+0x100-ish)
  with lengths unchanged; the tell for a dirty-tree suite is broad `*_port`
  region-diff failures at embedded addresses. A fresh clean worktree also needs one
  `./build.sh` + `DEBUG=1 ./build.sh` first — repin resolves but does not generate.
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

- **oracle-next / oracle-aether** (bus socket, headless): pixels, scanlines (sub-line
  since 2026-08-19), memory, watchpoints with per-hit mclk, the warp mailbox, and — once
  its profiler ships — cycle attribution (compare `cyclesSelf`, never inclusive).
  Client patterns: `tools/hblank_window_sweep.py`, `tools/sh_probe.py`. Assert
  `source == "raster"` on every scanline capture.
- **old oracle** (headless harness at `oracle-old/linux-port/harness`): the profiler until
  oracle-next's lands. Per-routine rows ONLY (`interrupts.hint` sums both handlers);
  match addresses on the low 24 bits; attribution LOSES ~20% when a tick spans VBlank —
  rest conclusions on preemption-free evidence. Patterns: `tools/raster_cost_probe.py`,
  `tools/engine_baseline_probe.py`, `tools/streaming_choke_probe.py`.
- Subagents NEVER touch emulator MCP tools (deadlock); headless bus scripts are the
  sanctioned instrument everywhere.

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
  PARENT needs a `sigil` symlink. ~~Without both, ~9-13 pytest failures are path
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

## Aeon-specific review bars (beyond the protocol's)

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

- Cycle claims near VDP ports: the bus absorbs adjacent OPERAND accesses but not
  instruction-stream fetches — nominal tables mispriced three consecutive parcels.
  Measure with the cost lane; the F-series/dense rows re-derive from shipped constants.
- Raster spins are SOLVED (`raster_dsl.emp`'s solver from the measured window anchor);
  a parcel that hand-adjusts a spin or a cost-gate expectation is wrong by definition.
- `.emp` comptime work: `docs/EMP_PITFALLS.md` first, every time.
- Cross-seam `Game.*`/`CAP_*` references: a FIRST reference in a module sigil's port
  harness compiles standalone breaks its `*_port` tests silently — extend the
  contract-env helpers in sigil's `test_support.rs`, values parsed from aeon source.
