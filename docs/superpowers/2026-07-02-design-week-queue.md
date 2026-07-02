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
- 2026-07-02 — design #1 spec written + approved in dialogue
  (`specs/2026-07-02-art-streaming-phase2-design.md`): supervisor-bookmark
  resumable decode (ARCH §9.7 user-mode variant rejected), ZX0+raw hybrid pages
  (audit amendment #1 superseded by measurement), page-frame residency
  (refcount-pin + LRU), B&R/Vectorman budgets, camera-gate degradation, per-act
  ROM budget gate. Next: user spec review → implementation plan.
- 2026-07-02 — design #1 implementation plan committed
  (`plans/2026-07-02-art-streaming-phase2.md`, 12 tasks). Design #1 BANKED.
- 2026-07-02 — design #2 spec written + approved in dialogue
  (`specs/2026-07-02-floating-origin-design.md`): atomic rebase ratified (modulo
  rejected), per-act parallax-aligned delta (fixes §9's false alignment claim),
  complete audited shift-list, single-owner routine + DEBUG audit, section_id
  byte→word widening included. Next: user spec review → implementation plan.
- 2026-07-02 — design #2 spec user-reviewed (TL;DR walkthrough) + implementation
  plan committed (`plans/2026-07-02-floating-origin.md`, 9 tasks). Design #2 BANKED.
  Design #3 (character dispatch + Tails/Knuckles) research started.
- 2026-07-02 — design #3 spec approved + committed (da7e699: CharacterDef + ability
  hook, CPU-as-input-filter w/ AIR fixes, assets = stock S3K from skdisasm — S.C.E.
  has none) + implementation plan (12 tasks, C1-C4). Design #3 BANKED. Next: #4
  damage/shields/loss-rings.
- 2026-07-02 — design #4 spec + plan committed (full S3K shield kit, dedicated
  32-ring loss pool, death→respawn + star posts w/ explicit reset contract,
  monitors w/ ghost-bug rules, 4 adopted fixes). Design #4 BANKED. Next: #5
  engine/game split.
