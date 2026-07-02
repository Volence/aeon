# Design Week Queue — 2026-07-02

**Purpose:** ~1 week of high-capability model access, spent banking approved specs +
implementation plans for the architecturally hardest open items. Execution can happen
later in any session; the design quality is the scarce resource. This doc is the
cross-session coordination point — the parallel sound-driver session should not
collide with any of this (all sound work stays in its own lane).

**Working rules (per design):**
- Full research checklist (all 8 reference disassemblies + online + modern patterns),
  subagent-driven.
- Ends as a committed spec (`docs/superpowers/specs/`) + implementation plan
  (`docs/superpowers/plans/`) executable cold by a later session.
- Every new component is explicitly tagged **engine** or **game** — these tags are
  the concrete inputs for design #5.

## Queue (approved order, 2026-07-02)

| # | Design | Status | Why this order |
|---|---|---|---|
| 1 | **Art-streaming Phase 2 + §9.7 cooperative multitasking** — residency cache / streams-past-VRAM; small ~64-tile S4LZ pages, resumable decode, diagonal-stress degradation gate | IN PROGRESS | Hardest; requirements already bound by the 2026-07-01 loading audit (see DEFERRED_WORK §2 entry) |
| 2 | **Floating origin (continuous-scroll Phase 4)** — unbounded level coordinates | queued | Its rebase contract constrains every later design; check interaction with #1 |
| 3 | **Per-character dispatch + Tails/Knuckles architecture** — dispatch-table indirection, Tails flight/AI, Knuckles glide/climb | queued | #4 must be designed against the post-dispatch shape |
| 4 | **Damage / shields / loss-rings + game-feel** — hit response, invuln, ring scatter, shield objects | queued | Assumes #3's player architecture |
| 5 | **Engine/game agnostic split** — engine.inc + game manifest, def/RAM split, parameterized boot, `games/demo/` | queued | Last on purpose: designs 1–4 supply real engine-vs-game placement data |

**Not in the queue (considered, deferred):** screen/game-state system (§9.13 + HUD)
— conventional enough that design quality is not the bottleneck; water/per-section
physics modifiers; suite work (Sigil, oracle-next, Aurora export drift).

## Log

- 2026-07-02 — queue approved, design #1 started.
