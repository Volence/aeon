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

**Roster C — user-facing surfaces** (ruled by the owner 2026-09-07; the ritual's first
seats that judge what a person meets rather than what the code is). Runs on every tool
with a surface a person uses: oracle and aurora as windows, sigil as diagnostics, seraph
when its hold lifts. Aeon has none and does NOT run it: a seat pointed at nothing returns
"nothing found", which is indistinguishable from clean.

| Seat | Hunts |
|---|---|
| UXa | Task walk. The controller's charter names three to five jobs a newcomer would want done, with no instructions on how. The seat may read the tool's README and nothing else, then tries each job. It logs every stall, guess, and moment it had to read code to proceed. Findings are "got lost here", ranked by time burned. For sigil: the seat writes wrong code on purpose, three to five classes, and judges whether each message gets a newcomer out. |
| UXb | Heuristic audit. Every panel, control and message walked against a fixed checklist: can it be found, does it answer back, is it consistent with its neighbours, can a mistake be undone, does an error say what to do next. Findings are checklist misses with the panel or message named. For sigil: the message catalog walked against the same list. |

UXa and UXb are a ×2 pair with opposed walks; convergence between them is the top
finding class, as elsewhere. Roster C is a **late panel** on a corpus that already has a
packet: it runs at a NEW pin, and the packet is amended naming the pair as late and the
pin it ran at, never re-dated.

Seat rules for Roster C, on top of the brief below:

- The seat launches its OWN instance of the tool on a PRIVATE virtual display (Xvfb,
  X11 forced, screen size verified from inside the display) with a PRIVATE socket or
  port. It never attaches to the shared server, never touches the owner's display, and
  never uses the emulator MCP; the "no emulator MCP ever" line stands unchanged.
- Every finding ships a screenshot, or the diagnostic text verbatim. No evidence, no
  finding.
- A clean task still reports its step count with a screenshot per step, so a clean
  verdict is examinable rather than "nothing found".
- Look and taste findings (this colour, this placement, this wording preference) are
  captures for the owner, parked under the standing look/taste rule, not packet findings.
  Usability findings (lost, stalled, undone by the tool, misled by a message) go into the
  packet's normal bins.
- The seat closes with what it could not drive (gamepad, audio, a device it lacks) and
  what would.
- **The charter names the surface, and a tool with more than one surface names each.**
  Oracle today is two windows (the game window in `oracle-frontend`, the debug tabs in
  `oracle-player`); a task walked in one and judged against the other is a conflation this
  lane has already paid for once. Say which window each job is walked in, or say both.
- **Not being able to get a ROM, a file, or a project in is a FINDING, never BLOCKED.** UXa's
  jobs are no-ops on an empty tool, and the seat may read only the README; if the README does
  not get a newcomer from launch to a loaded ROM, that is the first and most valuable finding
  the seat can return, not a reason to stop.
- **Pacing, smoothness and responsiveness are OUT OF SCOPE for Roster C.** A virtual display
  has no vsync, so a "feels sluggish" reading taken there answers a different question while
  looking like an answer (oracle's F-VSYNC-NEVER-MEASURED). Those findings need the owner's
  real display and are his captures.
- **"Private socket" binds the CLIENT, not only the instance.** Launching the server on a
  private socket is one flag; a seat that then reaches for the suite's reference client can
  be resolved to the shared socket regardless. The seat's client is pointed at the private
  socket explicitly, and the seat says which client it used.
- **No resolver in the rig may fall through to a shared last resort.** The shape to hunt
  for, in oracle's words: *a default that fills in silently when the specific thing is
  absent.* Any first-set-wins chain (an env var, then a runtime dir, then a fixed path;
  a binary, then the main checkout's build) terminates at a seat-private value the seat set
  explicitly, and the seat proves once WHICH VALUE WAS IN EFFECT, read back from what the
  run prints or writes; on a green run that is usually WHERE its artifacts landed (present
  under the seat's own location, absent from the shared default), and a demonstrated
  refusal of the unforced case is one such proof, not the only one. Three instances were
  found before the first run: a raw launch attaching to the
  owner's compositor, a binary name silently measuring the main checkout, and an app-side
  socket resolver arriving at the owner's live game window when the variable was unset,
  reachable because the audit seat is REQUIRED to press every control and the status badge
  is one.

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
- **Perf seats: every timing figure ships with a wall-clock reading beside it, STAMPED IN UTC
  (`TZ=UTC uptime`, or `date -u` alongside it).** A seat once measured the panel's own
  contention and reported 12.7s for a 2.85s build — that is why the reading is required.
  **NAME THE FRAME, NOT THE COMMAND (amended 2026-09-06):** bare `uptime` prints LOCAL time,
  and this lane spent a session putting a local clock beside UTC stamps in every report
  because this line said `uptime` and the bar that distrusts a local stamp lives in a
  different document. **A rule that MANDATES a field and a rule that DISTRUSTS that field
  cannot see each other**, so the mandate has to carry the frame.

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
