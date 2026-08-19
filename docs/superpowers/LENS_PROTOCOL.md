# Lens Sweep Protocol — the Ratified Ritual

Canonical protocol for "let's run our lenses." This is the single authority; prior
packets under `docs/superpowers/notes/` are worked examples, not the spec. Suite-wide:
applies to aeon, sigil, aurora, oracle-next — the packet lands in the swept repo.

Ratified 2026-08-01 (`sigil/docs/superpowers/notes/2026-08-02-lens-sweep-adjudication.md`),
extended live by the owner; tooling roster validated 2026-08-13. Do not improvise a
smaller panel — the 2026-08-09 improvised A/B/C trio was explicitly corrected: each
ratified seat earned its keep, and seats verify DIFFERENT properties. The union is the
truth.

## Step 0 — check for standing findings first

If this corpus has a prior packet: **landing a packet made its findings discoverable;
nothing in it is fixed.** A new sweep on a previously-swept corpus is two jobs — a cheap
re-verification pass over the standing findings (CONFIRMED-STILL-OPEN / CHANGED / STALE,
one or two seats) and a fresh panel for the delta since the pin. Never blank-slate over
an open packet and let its findings rot twice. Check `docs/DEFERRED_WORK.md` for the
booking, and honor any DO-NOT-RE-LITIGATE (refuted) entries — they exist so refuted
majors don't get re-found every round.

## Setup

- Pin a named review SHA on a clean tree; seats work read-only against it (worktree if
  anything else is in flight).
- Every seat is a **fresh subagent, never a fork** — no shared bias from the
  controller's own read. Launch all seats in one batched message so they run
  concurrently.
- Charter the corpus explicitly — the file list AND what is out of scope and why. An
  out-of-scope subsystem is *unexamined, not cleared*; write that sentence into the
  packet so the sweep is never later read as blessing what it skipped.

## Rosters

**Roster A — assembly / engine corpora** (68000/Z80 `.emp`, engine code):

| Seat | Hunts |
|---|---|
| A | Ceremony/history — comments narrating changes instead of present-tense fact |
| A2 | Comment TRUTH — every factual claim checked against what the code does |
| B1 | Construct/idiom discipline — blessed patterns vs hand-rolled equivalents |
| B2 ×2 | Cross-file duplication — one walk code-first, one data-first |
| C1 ×2 | Instruction-level performance — opposite walk orders |
| C2 ×2 | Gate-blind hazards — what no test/gate would catch — forward + Z80-first |
| C3 ×2 | Hardware timing/atomicity — bus holds, DMA contention — outward + handler-first |
| C4 ×2 | Algorithmic altitude — right structure/algorithm, not just correct code |
| C5 | Space/footprint — dead ROM/RAM, reclaimable bytes |
| V | Vacuity/gate-coverage — chase every claimed guard to a file:line or record its absence |

**Roster B — toolchain / Rust corpora** (validated on the 2026-08-13 sigil sweep; it
substantially outperformed reusing Roster A): CGa/CGb (codegen correctness per target) ·
GATE (golden/pin machinery) · TEST (suite vacuity + skip counts) · FUZZ
(property/mutation) · SAFE (panics/unsafe/robustness) · RELAX (fixed-point algorithms) ·
LINK (placement/layout) · IR (pass contracts) · ARCH (crate structure) · ERR
(diagnostics) · COMPTIME (evaluator semantics) · CACHE (dev-loop I/O) · P1a/P1b/P2
(performance: forward, reverse, algorithmic) · plus A2 / B1 / B2 / V from Roster A.

**Scaling:** full ×2 seat doubling for corpus-scale sweeps; for merge-sized diffs,
collapse each ×2 pair into one seat with encoded walk-order variation. Any tool that
runs on every build deserves perf seats — and perf seats come **doubled deliberately**:
measuring the same thing from two ends is the only reason a bad number gets caught.

## The seat brief (every seat, verbatim rules)

- READ-ONLY. No edits, no commits. **No emulator MCP ever** (deadlocks from
  background agents); findings wanting runtime confirmation are tagged for the
  controller's foreground follow-up.
- Every claim needs a derivation the overseer can redo in seconds — file:line, a grep,
  or short reasoning. "Verified clean, here is what I re-derived" is a welcome result;
  inventing findings is the cardinal sin.
- Report most-severe/most-uncertain first; keep FIXED-verified vs PROPOSED-unapplied
  separate; close with what the seat could NOT check and which instrument would.
- If BLOCKED (missing context, unbuildable pin), STOP and say so — never degrade the
  charter silently.
- **Perf seats: every timing figure ships with a wall-clock uptime beside it.** A seat
  once measured the panel's own contention and reported 12.7s for a 2.85s build.

## Overseer duties (the controller, after seats return)

- Independently re-verify every load-bearing citation against the pinned tree before it
  enters the packet. Nothing ships unverified.
- Resolve seat conflicts explicitly, never by picking a favorite. Precedent: when seat A
  called a registry clean and seat V found its hollow guard, A's verdict was downgraded
  and documented *as evidence for the finding*.
- Convergence — independent seats on opposed walks hitting the same target — is the
  panel's strongest signal; call it out.
- Rank CRITICAL/HIGH/MEDIUM with a LIVE-today vs latent-until-X reachability tag.
- Record refuted majors in a DO-NOT-RE-LITIGATE section with the refutation.

## The packet

- **Committed, never scratchpad-only.** A packet that lives in /tmp does not exist to
  any other session — one sweep was nearly lost this way and another was wrongly ruled
  "never ran" from repo absence.
- Location: `docs/superpowers/notes/<date>-<corpus>-lens-sweep.md` in the swept repo
  (+ optional raw seat output as `…-packet.jsonl`). Docs-only commit on a
  `review/<corpus>-lens-sweep` branch, merged to master promptly.
- Same-day reconciliation into `docs/DEFERRED_WORK.md`: new findings booked; standing
  findings updated in place (never a second disconnected list).

## Aftermath — triage bins (owner-gated, never agent auto-fix)

Seats stay read-only precisely so the report stays honest; fixes are separate work:

- **Byte-changing fixes** — own small parcels, each with before/after evidence, then the
  repin/refreeze ritual. Never batched blind (two byte-moving changes in one branch make
  a crc diff unattributable).
- **Measure-first items** — asserted costs go to the profiler before any retuning.
- **Byte-neutral parcels** (comment truth, dead-guard deletion) — may land immediately.
- **Structural/process findings** — their own arc item, not folded into a code fix.
- **Open questions** (conflicting models, pin-or-derive choices, novel mechanisms) —
  explicit owner ruling, never resolved unilaterally by whichever seat found them.
- Everything not actioned is booked in DEFERRED_WORK the same day.

**Dry criterion:** a track is dry only when a fresh panel, run *after* the prior round's
fixes landed, returns nothing new.
