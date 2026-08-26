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
  26 of 27 gates passing — the one failure is `boot_override`'s pre-existing SETUP ERROR,
  identical text in both. Per segment: raster_off 9.7 -> 0.5 s, palette_variant 12.6 -> 1.5 s,
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
  So the named ask is HALF discharged, at the aggregate and not per-frame. Spawn through
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
- Cycle claims near VDP ports: the bus absorbs adjacent OPERAND accesses but not
  instruction-stream fetches — nominal tables mispriced three consecutive parcels.
  Measure with the cost lane; the F-series/dense rows re-derive from shipped constants.
- Raster spins are SOLVED (`raster_dsl.emp`'s solver from the measured window anchor);
  a parcel that hand-adjusts a spin or a cost-gate expectation is wrong by definition.
- `.emp` comptime work: `docs/EMP_PITFALLS.md` first, every time.
- Cross-seam `Game.*`/`CAP_*` references: a FIRST reference in a module sigil's port
  harness compiles standalone breaks its `*_port` tests silently — extend the
  contract-env helpers in sigil's `test_support.rs`, values parsed from aeon source.
