# aeon overseer handoff 26 (2026-09-25, session aeon-68)

NOTE: after this file was written the owner asked "real sonic 2 level should switch to short tunnel"; check lane-status and lane-log for whether S2CLIP-ADOPT-SHORT-TUNNEL landed before starting.

CLEAN boundary (as first written): nothing in flight, no agent holding a branch, and master is pushed. The owner asked for a /clear
with this as the next job, so START WITH THE PERFORMANCE SURVEY BELOW. He said go ("If so let me /clear and you can
get going yeah?"), so do not boot into a stop.

## The owner's next ask (verbatim, 2026-09-25)
*"Next up can you fly through things and see if you can detect any lag and see if we want to do anything for
performance?"*

Dispatch it as a RESEARCH parcel (headless only; no MCP in agents), and deliver a ranked shortlist he can pick from.
Suggested scope, to test rather than trust:
- **Shapes:** canonical `s4.debug.bin` / `s4.bin` (OJZ act 1), the Sonic 2 clip `s4.s2clip[.debug].bin`
  (`S2CLIP=s2_ehz_cpz`), and (only if S2CLIP-ADOPT-SHORT-TUNNEL has NOT landed) the short-tunnel clip (`S2CLIP=s2_ehz_cpz_short`).
- **Legs:** the S2CLIP-LAG harness `docs/research/2026-09-25-s4-lag/run_legs.sh` (fly right/down/diagonal, physics run,
  release physics), `tools/tunnel_run_witness.py`, `docs/research/2026-09-25-cpz-traversal/cpz_traverse.py`, and
  the oracle profiler for per-function cost (`reference_oracle_profiler_instrument`: interrupts.hint is HBlank PLUS
  VBlank).
- **Known residue to fold in** (DEFERRED_WORK S2CLIP-LAG "Still open"): (1) after the bounded regime ends the act runs
  the general patch loop, about 3.9k per row run against 1.6k (levers: an idle-time mark-sweep liveness pass, or a
  per-section translated map); (2) the diagonal EHZ band is 26/82 against the resident control's 21/77; (3) no lane
  runs the streaming path on a built shape (no regression net).
- **Deliverable:** lag frames per leg and shape, the top hotspots by cycles with their call sites, and for each fix
  candidate: cost, expected gain, engine or content, and risk. Recommend an order. A **number** with its referent
  (CRC + leg + unit) is the bar, never an impression.

## Landed this session (origin/master; lane-log.jsonl has an entry for each)
- `8939377f` S2CLIP-LAG engine fix (bounded prefetch, direct patch regime) + CLIP-BAKE-JSON for aurora + a
  system-pool scanner fix (it was decoding the deb2 symbol appendix past EndOfRom).
- `0d782e70` S2CLIP-TUNNEL: an enclosed 832-px connector in CPZ art, with the 4-px seam step fixed.
- `06adbfbe` Z80-TAP-ADDR-MOVE, with oracle `87805bf3` (drum L0 z80=662 foreign=0).
- Shared sigil pair swapped to `1d19e60b` (hub window, 17:16:49Z). Canonical was byte-identical across the swap.
  STRESS-CLAMP-EQU-WRONG closed.
- `8886d1cc` clip anchor overlay (the clip's own sound-bank positions), paired with sigil 1d19e60b.
- `96dcfc8f` CPZ +480 (fills the void). `ed48f9a9` B-2 Sonic 2 background scrolling.
- `9acc5120` rule B counts only pinholes a player can stand beside, and CPZ extended to the traversal limit (act 8
  sections; he reaches act x 15399, where a plane-A wall stops him; Sonic 2's route is plane B).
- `005accdc` the short-connector test clip `s2_ehz_cpz_short` (384 px) + an ENGINE change in `engine/level/bg.emp`:
  a one-plane-tall BG is repainted by DMA from ROM, 14 rows/frame, 0 B RAM. **Canonical CRCs moved:** s4
  950f7d28, s4.debug a0e248e7, demo.debug 0d9b88fd.

## Owner calls this session
- Card S2CLIP-CPZ-FURTHER answered: fix-check-and-extend (decisions.jsonl).
- He flew the 384 short clip: *"the short one seems like it's fast enough honestly."* Then RULED, verbatim: *"real sonic 2
  level should switch to short tunnel"*. Dispatched as S2CLIP-ADOPT-SHORT-TUNNEL (branch
  `parcel/s2clip-adopt-short-tunnel`). `s2_ehz_cpz` takes the 384 px connector and `s2_ehz_cpz_short` is DELETED, so
  the survey's short-clip shape below no longer exists once it lands.

## Open items worth knowing (all booked in DEFERRED_WORK)
- **SHORT-TUNNEL-VSCROLL-RATCHET:** since B-2, 384 px shows a 3-4 frame vertical BG slide at the camera cap. 480 px is
  glitch-free today. The fix (skip the 16-px/frame vscroll clamp for one-plane BG maps, a few lines in `parallax.emp`)
  changes canonical behaviour on every one-plane crossing/warp and is graded by `bg_vscroll_rate`, so it is PARKED.
  Ask him if he wants it.
- **BG-SWITCH-POISON-MARGIN:** that gate leg has one tick of margin after the faster repaint. The redesign is to starve
  the DMA queue, as ORDER_STARVED does.
- **CLIP-ANCHORS-MISSING-FILE:** a clip whose anchors.toml goes missing falls back silently in FAST.
- **Going further into CPZ** needs plane switching (crossover marks are one-way; `path_swap.emp` is parked for
  deletion), then the spin tubes, boosters and pipe springs.

## Coordination state
- aurora: sent one landing notice per landing (their currency gates read our master live; memory
  `feedback_aurora_landing_notice`). Their re-vendor is queued as their ROADMAP row 218.
- sigil: clip overlay contract at `1d19e60b:docs/superpowers/notes/2026-09-25-clip-overlay-contract.md` now names the
  PHASE row and the DIGEST-READ row as aeon dependencies. Nothing owed.
- oracle: §11.52 closed on both sides.

## Process note for the next session
Three agents ended their turns "waiting for the landing build" and did not wake by themselves. The controller watched
the log with an `until grep finished=` loop and resumed them. Keep "poll your own log, never end your turn waiting"
in every brief. It helped but did not fully cure it.
