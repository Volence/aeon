---
kind: template
status: reference
description: "v2 (2026-11-16): the fixed shape of every system audit, revised after the frame-architecture pilot and its process review."
---
# Audit template (v2)

Every system audit follows this file. Why audits exist: [[2026-11-16-engine-quality-process-changes]].
What changed from v1 and why: [[Audit process review]]. **The bar: S3K is the floor.** Judge against the
best known technique anywhere and against the hardware's limit.

## Who runs an audit

| Stage | Agent | Writes | Notes |
|---|---|---|---|
| 0. Inventory | Opus | `<system>/0-inventory.md`: section 2 | **Mechanical, by script where possible**: call order, caller counts per routine in scope, readers/writers of every shared variable, footprint, build shapes, the list of doc claims, the idiom counts (section 7). No judgment |
| 1. Research | Opus | `<system>/1-research.md`: sections 3 and 4 | Rules below. Hardware limits go to the shared page [[Hardware limits]] once and are cited after |
| 2. Measurement | Opus | `<system>/2-measurements.md`: section 5 | Headless harness only (never `mcp__oracle__*`). Pinned fresh emulator build; aeon commit recorded; release AND DEBUG labelled on every number |
| 3. Reviewer A | Opus or Fable | `<system>/3-reviewer-a.md`: sections 1, 6, 7, 8 + coverage table + challenges | Mandatory walk A (below) |
| 4. Reviewer B | the other model | `<system>/4-reviewer-b.md`: same | Mandatory walk B. Never reads A |
| 5. Checker | Opus | `<system>/5-checker.md` | One bounded round: re-opens every cited `path:line`, checks every number's label and build shape against the raw files, reads both coverage tables for unread files, and holds the **known-defect list** from earlier reviews. Gaps go back to the reviewers once |
| 6. Lead | Fable | `<System>.md`: the merged audit | Lead rules below |
| 7. Controller | main session | — | Verifies contested claims in code, runs live-emulator items, reports to the owner |

Big-picture systems get Fable as reviewer A; cycle-heavy systems get Opus as A. B is always the other model.
Reviewers stay blind to earlier reviews; the **checker** carries the known defects, so independence is kept
and nothing known is lost.

**Lighter shapes.** A system that does not exist yet gets a **design review**: inventory of what it touches,
research, one reviewer, lead; sections 1, 3, 4, 8. A system already marked for replacement skips section 5,
and section 7 shrinks to the scripted idiom counts. A **fitness check** (e.g. the emulator: "is it accurate
enough for what we need to judge?") is inventory + research + measurement + one reviewer + checker.

**Fix between waves.** Land the cheap fixes from wave N before wave N+1 audits the tree.

## Labels

Every number is **MEASURED** (ran it, or cite the file that did), **PUBLISHED** (cite), or **ESTIMATED** (show
the derivation), and states **release or DEBUG** where that applies. A killed or capped run is DID NOT RUN.

## The eight sections

### 1. Requirements (reviewers)
- What the system must do for: the Sonic 4 vertical slice; mega-acts and infinite levels; and a **named
  non-Sonic game** chosen for this system.
- Budget targets: share of frame cycles, RAM, VRAM, ROM.
- The worst case it must survive. Interfaces with other systems; non-goals.

### 2. Inventory from source (stage 0)
- Entry points and call order from boot, the main loop and every interrupt handler.
- Every feature classed SHIPPED / DEBUG-ONLY / INERT (no caller) / TEST-ONLY / ABSENT, with `file:line`.
  **Caller counts come from a script over the source and listing, never from comments.**
- Readers and writers of each shared variable and flag in scope.
- Data formats and the tools that produce them; real RAM / VRAM / ROM footprint from the listing.
- Build shapes and flags that change behaviour.
- Every claim the docs and comments make about the system, listed for section 7.

### 3. Best known approach (research)
- At minimum: S3K / S.C.E. (the floor); the two best commercial games for this system (named); the best
  homebrew or SGDK approach; the demoscene; one modern technique from outside the Genesis.
- For each: how it works, what it costs, where it breaks, with a source.
- **No "not documented" where a verdict depends on it: read the disassembly.** A "nobody ships this" claim
  needs a primary-source check.

### 4. Hardware ceiling (research)
- Cite [[Hardware limits]]; add to it only what is new for this system.
- What binds this system, and where the current design sits as a percentage of the ceiling.

### 5. Measured cost (measurement)
- **Fixed scenario legs, the same every audit**: idle, run, top speed, diagonal fall, spindash, object-heavy
  stress, sidekick, streaming act, PAL boot. Release and DEBUG.
- Average and worst cycles per routine; lag frames; the scanline where VBlank work ends; byte footprint.
- How cost grows with objects, rings or layers.

### 6. Correctness (reviewers)
- Edges: wraparound, coordinates near 32K, slot exhaustion, queue overflow, lag frames, PAL, DEBUG vs release.
- Interactions: frame order, interrupt races, Z80 bus contention.
- What happens when a budget is exceeded: graceful degradation or corruption?
- Each finding proven in code or by reproduction, with a proposed test that fails first.

### 7. Code quality (inventory counts + reviewers)
- Comments and docs that contradict the code (against section 2's claim list).
- Dead code, duplication, convention breaks.
- Complexity against value; do the existing gates test what they claim to?
- Which doc facts should be generated from code. Could another game's developer follow it?
- **Idiom / port-residue check** (counted by script, `file:line` per hit):

| Check | What counts |
|---|---|
| Build-time work done at run time | loops or sums over static tables; literals whose derivation sits in a comment |
| Layout literals | raw `n(aN)` offsets or plane/stride numbers where a struct field or constant exists |
| Hand-spelled pins | `ensure` lines guarding a literal that could be derived |
| Hand-kept protocols | flags or orderings whose rules live only in comments |
| Assembler residue | AS operand echoes like `// (Name).w`, references to deleted `.asm` twins, `widths pinned` notes |
| History in comments | dated change notes; comment share of the file |

### 8. Verdict and plan (reviewers, merged by the lead)
- Verdict on one scale: **below S3K / S3K level / best known / beyond**.
- **Disposition: keep / patch / rewrite beside / replace**, with the reason.
- Ranked improvements: gain, cost, risk, dependencies, byte-changing or not.
- Beyond-state-of-the-art candidates and how plausible each is.
- Dropped ideas and why.

## Reviewer mandatory walks

- **Walk A:** follow time. Where can an interrupt land, what is half-done at each point, what does the
  hardware see? (For a tool: follow one input from file to output, step by step.)
- **Walk B:** follow logic and reuse. The order of work within a tick, and **port the named non-Sonic game
  onto the system on paper**: what breaks, what is Sonic-specific? (For a tool: write the same small
  real feature both ways the tool allows, and compare.)

Each reviewer ends with:
- a **coverage table**: every file in scope, lines read, "finding N" or "read, nothing";
- a short **Challenges** box: anything in stages 0 to 2 they believe is wrong, with evidence.

## Lead rules

- State release or DEBUG on every number. Never restate a reviewer's verdict in softer words.
- Carry every needs-runtime item, or say why it was cut.
- **At most five owner decisions**, ranked, each with a recommended answer.
- Show the reviewer agreement table and the checker's corrections.

## Rules for every agent

- Read-only in every repo except your own output file under the audit folder.
- Never `mcp__oracle__*`. Headless harness scripts are sanctioned.
- Faithful reporting: aggregate totals, never a tail excerpt. Do not pad; "read, nothing" is a valid row.
- Your output is read in Obsidian: keep the frontmatter, set `status: in-progress` first and `status: done`
  last, update `description:` to a one-line result. Conclusion first, then detail; tables, callouts, mermaid.
