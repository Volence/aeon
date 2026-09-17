# Aeon overseer handoff 21 (2026-09-17, overnight)

**The resume anchor for the next aeon session.** Read `docs/lane-status.json` first. **Fetch origin before reading master.** An agent listed in `inFlight` in a file written before a `/clear` is NOT running: check its branch on origin/worktrees, and re-dispatch from this file if it did not land.

## Landed this session (all pushed; lane-log entries carry the evidence)
- **VRAM savings audit** (research): `docs/research/2026-09-17-vram-savings-audit.md`. 62 tiles free without an owner dial, 84 behind dials (BG band reserve 56, waterline cap 16, dust/insta-shield share 12). Spare nametable is NOT free; per-region object art is 0 until badniks exist.
- **FG-CACHE-10 research**: `docs/research/megaact-bg-streaming/10-fg-cache-10-frames.md`. 640 fg tiles fit every stitched S2/S3K window only with 32-tile pages + budget-aimed search + per-zone pages + frame-aware pins + 56x48 window. 64-tile frames never fit S3K (540 windows, all CNZ1 acts).
- **STITCHED-ACT-PAGE-ORDER wiring** (merge `099046fd`): `tools/fg_page_order.py`; ojz_strip_gen Pass 4 keeps the current order when it fits, else searches; strict `build.sh` lane + re-bake refusal, budget read from `constants.emp`. OJZ byte-identical.
- **PAGE-SIZE-CONSTANT-ONLY**: bake/verify read the page size from `constants.emp`; ROMs byte-identical (s4 `f9156c30`, debug `8d3d92a0`). Engine/RAM items a 32-tile switch still needs: `DEFERRED_WORK.md` STITCHED-ACT-PAGE-ORDER item 2.

## Owner card open
- **FG-CACHE-10-HOW** (half-size pages + smaller window after an in-game test [recommended] / cut to 10 at 64 / stay at 12). Two lines share the id on purpose: the second supersedes with the derived 128-tile cost (hub agreed this is not an 8e case).
- SP-6 spring sound A/B still waits on his ear.

## In flight at writing
- **STRESS-UNIQUIFY-REBAKE** on `fix/stress-uniquify-rebake`: `STRESS_UNIQUIFY=2600 tools/regenerate-level.sh` fails verify_level_bin's editor-bake fidelity check (pre-existing; DEFERRED_WORK STITCHED-ACT-PAGE-ORDER item 6). Brief: reproduce, root-cause, find the breaking commit, do not weaken canonical fidelity, prove with a planted wrong tile, canonical bytes identical.

## Then, in order (none waits on the owner)
1. **CACHE-WINDOW-HOLD-MEASURE**: the runtime measurement card FG-CACHE-10-HOW's recommended option is gated on. Count camera holds (art not resident) at 16 px/frame through a stitched act for 80x60 vs 64x48 vs 56x48 windows, and measure 32-tile page decode time (report 10 "Tagged for runtime"). Use the repo's headless subprocess gate harness (ab_runner / effects_gates style), never oracle MCP from an agent. Research only; changed-constant builds live in the agent's worktree and never land. Its result goes on the card as a `detail` supersede only if the numbers change the recommendation.
2. **MEGAACT-BG-STREAMING** remaining aeon-side pieces (cover-length warning, per-region animated bands); authoring is aurora's.
3. LS-13b (boot's hand-written Z80 pause, sigil feature shipped).

## Lessons
- `/clear` kills running agents; the owner asked to clear at bedtime and was steered to sleep-mode rotation instead.
- The land gate accepts an agent's `landing_build.sh` stamp when master moved only by docs since the agent's base.

## Update, later the same night (supersedes "In flight" and "Then" above)
- **Landed:** STRESS-UNIQUIFY-REBAKE (stress clones declared, verified as a stress bake), stress shapes' ceiling rows + STRESS_EVICT DEBUG=1, STRESS-SHAPES-GATE-CUTS (off-canonical shapes derive gate cuts; both stress builds exit 0), CACHE-WINDOW-HOLD-MEASURE (report 11: smaller windows hold the camera; ARCH 9.7 decode figure 3.4x low), check_mode_conflict docstring. Card FG-CACHE-10-HOW superseded: recommend stay-at-12.
- **Nothing in flight.** Aeon told the hub it is clear for the sigil release-binary swap window (sigil d7e6aa15 enforces `(size: N)`). Do not rebuild `sigil/target/release/sigil` yourself: sigil lane only, in a hub-opened window.
- **Next, in order:** (1) SPAWNDESC-SIZE-CLOSE after the swap: re-run the control (SpawnDesc size 41 refused at `engine/objects/children.emp`) then close the DEFERRED_WORK row. (2) STRESS-SHAPES-NIGHTLY: add both stress builds to `tools/nightly_effects_gates.sh` after the canonical legs, own exit codes, failure is FAILED not COULD NOT RUN. (3) MEGAACT-BG-STREAMING aeon pieces. (4) LS-13b.
- **Aurora reads this tree:** at a landing touching a path its suite reads, message aurora (derive the list; command in OVERSEER-REFERENCE landing lane).
