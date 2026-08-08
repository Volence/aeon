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
| 1 | **Art-streaming Phase 2 + §9.7 cooperative multitasking** — residency cache / streams-past-VRAM; small ~64-tile S4LZ pages, resumable decode, diagonal-stress degradation gate | **BANKED** | Hardest; requirements already bound by the 2026-07-01 loading audit (see DEFERRED_WORK §2 entry) |
| 2 | **Floating origin (continuous-scroll Phase 4)** — unbounded level coordinates | **BANKED** | Its rebase contract constrains every later design; check interaction with #1 |
| 3 | **Per-character dispatch + Tails/Knuckles architecture** — dispatch-table indirection, Tails flight/AI, Knuckles glide/climb | **BANKED** | #4 must be designed against the post-dispatch shape |
| 4 | **Damage / shields / loss-rings + game-feel** — hit response, invuln, ring scatter, shield objects | **BANKED** | Assumes #3's player architecture |
| 5 | **Engine/game agnostic split** — engine.inc + game manifest, def/RAM split, parameterized boot, `games/demo/` | **BANKED** | Last on purpose: designs 1–4 supply real engine-vs-game placement data |
| 6 | **Editor collision authoring** — Aurora stamps carry collision (per-block-placement solidity — the classic-chunk role) + a first-class collision layer; fixes art-reuse dragging collision along | **BANKED** (added 2026-07-02, user-raised) | Cross-tool: Aurora + the daemon-watched generator |

| 7 | **Screens/HUD (§9.13) + Aurora screen authoring** — game-state screens (title/menus/results/game-over), font/text pipeline, HUD; screens are data documents Aurora edits visually (text, selectable menus, art, palette, music cue) and the engine plays | **BANKED** | Unlocks #4's lives/game-over; needs the font pipeline |
| 8 | **Raster engine + parallax authoring tools** — HInt raster-effect library (water line etc., §4.6 backlog) + Aurora visual band/deform editor with live preview over Aether | **BANKED** | Engine half exists; authoring is hand-written asm today |
| 9 | **Reusable object behaviors** — composable behavior primitives ("wait until on-screen", patrol, fire-at-player, death-into-explosion) via a lightweight per-object behavior sequencer; Aurora attaches behaviors/params to placed objects | **BANKED** | The force-multiplier for badniks/bosses; architecturally deepest of the three |

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
- 2026-07-02 — designs #5 AND #6 specs + plans committed. #5: gameHeader macro +
  parameterized boot (Game_Entry) + soundBankHead contract + stray inversions +
  def/RAM splits + games/demo (SGDK-validated seams). #6: Aurora chunks carry
  dual-plane 16-bit collision, atomic stamp-carry, paint defaults to just-here,
  legacy encodings retired, paint_collision MCP tool; aeon side ZERO code changes
  (editor collision already consumed authoritatively — stale-doc claim corrected).
  ALL SIX DESIGNS BANKED.
- 2026-07-02 — designs #7-9 queued (screens/HUD + Aurora authoring; raster/parallax
  tools; reusable object behaviors). NEXT SESSION starts here: read this doc + the
  design-week memory, then run the same per-design cycle (research agents →
  decisions → spec → plan). All six prior designs are execution-ready.
- 2026-07-02 — design #7 spec + plan committed (compiled screen documents:
  Aurora JSON → screens_gen.py w/ build gates → widget tables + prebaked strips
  → engine interpreter; VInt_Menu w/ VInt_Load folded in, S3K-style sprite HUD
  w/ BCD + per-field dirty flags, runtime palette fade engine, game seams =
  binding table + widget/action handler tables for tally/title-card; full
  classic screen set; Aurora 4th AppMode + 7 MCP tools last). Design #7 BANKED.
  Next: #8 raster engine + parallax authoring tools.
- 2026-07-02 — design #8 spec + plan committed (three layers: sparse HInt raster
  script engine w/ closed op set + RAM trampoline + in-handler $0A re-arm +
  camera-tracked water line; Batman-derived frame sequencer — deep-dive verified
  B&R is sequencer + hardcoded raster, the general raster table is OUR novel
  layer; parallax→JSON migration w/ byte-equal golden; Aurora 5th mode + FIRST
  Aether client + DEBUG RAM override = real-engine 60fps live preview).
  Design #8 BANKED. Next: #9 reusable object behaviors.
- 2026-07-02 — design #9 spec + plan committed (two-track move‖act byte-opcode
  sequencer, PC-is-the-state w/ depth-1 interrupts + armed events; BulletML
  4-mode aim on new 256-angle atan2/sine module; native escape hatch;
  badnik-side Touch_Enemy kill/chain-score/explosion/killed-bit owned here;
  per-placement params = subtype-as-param-bundle-index, zero entity-format
  break; v1 = skeleton + 3 example badniks [user framing], boss seams designed
  not built; Aurora properties panel in map mode + 4 MCP tools, stale TS
  entity exporter retired). Design #9 BANKED.
- 2026-07-07 — design #5 plan REFRESHED: `plans/2026-07-07-engine-game-split-execution.md`
  supersedes `plans/2026-07-02-engine-game-split.md` (post-07-02 sound merges drifted its
  anchors; GAME_FM_PATCHES seam dead; four new seams: SndDefaultPitchTable, ring SFXID
  contract, camera `_pl_state` gate, root `test/` relocation; engine.inc formation moved
  late as its own byte-identical stage). Spec unchanged; deltas listed in the new plan's
  header. Execution still open.
- **ALL NINE DESIGNS BANKED — design week COMPLETE.** Every design has an
  approved spec + cold-executable plan on master. Execution order note:
  #7 tasks 1-5 unblock #4 fully; #9 depends softly on #4 (Touch_Enemy split)
  and #7 (BCD helpers); #8 depends softly on #7 (fade engine). All soft deps
  have tagged fallback seams in their plans.
- 2026-08-08 — **design #1 EXECUTION OPENED.** D1–D4 ruled (all per the
  2026-08-06 decision memo's recommendations: bookmark-first / no arbiter /
  H4 gate on speculative starts only / two-layer §9.7 title). Plan being
  re-anchored into `plans/2026-08-08-art-streaming-phase2-v2.md` (folds the
  2026-08-06 addendum + rulings); sigil asks 1–2 (`@resumable` + extent
  symbols) started as the gating lane. Branch: `feat/art-streaming-p2`.
- 2026-07-07/08 — **design #5 EXECUTED.** All 9 tasks of
  `plans/2026-07-07-engine-game-split-execution.md` complete: `engine/engine.inc` +
  seven-macro game manifest, `gameHeader`/parameterized boot, `soundBankHead` contract,
  def + RAM splits, `games/demo/` boots (white box, 89830 bytes). `engine/` passes the
  contract grep gate (T9). Field findings (gameStatesIncludes 7th hook,
  `{GLOBALSYMBOLS}` macro-local gotcha, cart-core hash gate, `BgAnim_Table` contract)
  are folded into the plan doc as amendments.
