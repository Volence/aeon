# Aeon overseer handoff, 2026-09-15/16 eighteenth session (booted 23:46Z, after a clear)

**Read this, then `docs/lane-status.json` (local disk), then `docs/OVERSEER.md` and
`docs/DEFERRED_WORK.md` at `origin/master`.** Supersedes handoff-17.
Written 2026-09-16T01:17:09Z from the clock; every figure is copied from this session's tool output.
Master at writing: `a2756196`, pushed. Nothing in flight. Nothing half-applied.

## The one-line state

**Step 0 of Regions part 2 is CLOSED. The hub has given a GO on STEPS 1 TO 5 (its ruling under his
2026-09-15T23:48:50Z go, overturnable by one word from him). STEP 6 IS HELD for the owner's E2
verdict, because that verdict SELECTS step 6's palette behaviour and writing it first means picking
one of two branches and hoping.** Start at step 1.

## Landed and published this session

| what | merge | note |
|---|---|---|
| E3 — can a second BG picture fit | `27f29d20` | `docs/superpowers/notes/2026-09-15-regions-p2-e3.md` |
| E2 — the palette-snap fixture | `5de779b2` + land `c53dfa38` | `…-e2.md`; effects_gates 18/18 `GATE_EXIT=0` |
| E1 — plane-buffer headroom | `ec513055` | `…-e1.md` |
| four doc/comment figures booked | in `55651631` | DEFERRED_WORK, three checked firsthand |
| E1's falsifier run | `a2756196` | DEFERRED_WORK, with the rest control |
| E2's captures | `a2756196` | `docs/captures/2026-09-15-regions-p2-e2/` + README |

**The three numbers that matter.** E3: forest 320, cave 448, union 768 tiles against
`BG_TILE_CAPACITY = 376` — decision row 3, 2.04x the arena, not near the boundary, and the cave does
not fit alone either. E1: peak **536 B of 1536**, decision row 1, `BG_WIPE_ROWS_PER_FRAME = 4`, now
FINAL (the falsifier ran). E2: fixture built, colour proven the only variable by bytes, verdict is
the owner's.

## ⚠ THE FINDING THAT CHANGES STEP 6's ARITHMETIC — read before sizing the wipe

`Draw_BG_TileColumn` has **zero call sites**, so no frame in this ROM emits a BG entry today and the
wipe would be the buffer's **first BG producer**. **Step 6 plans against 536 + 528 = 1064 B, NOT
536**, and the wipe must append AFTER the FG streamer with its own reservation guard or
`Draw_TileColumn` drops columns **silently**. "Peak 536, headroom 1000" invites the exact opposite
inference: the headroom is what the wipe SPENDS.

## ⚠ WHAT THE OWNER'S E2 VERDICT CAN AND CANNOT SETTLE

There is **no "new palette over half-redrawn art" transient today** — the row wipe IS step 6 and does
not exist, and both regions share one tile set. So his answer selects the **snap-versus-fade default
and nothing more**. The spec's risk-2 framing describes a condition step 6 CREATES. **Expect to go
back to him once more after step 6 lands; that is the experiment that could not exist yet, not scope
creep.** Failure this prevents: someone looks for a transient that is not there and reports its
absence as a pass.

## Four things sit with the owner (none blocks steps 1 to 5)

1. **E2's look** — does an instant whole-screen colour change read as a transition or a fault?
   Captures banked; the real judgement wants the ROM moving. **The line-0 sentence is in the README
   ABOVE the frames on purpose**: Sonic keeps day colours because palette line 0 is the shared
   character line, which is his own PALETTE-LINE0 ruling, so "the character looks wrong" is a finding
   about THAT card, not about the snap.
2. **`REGIONS-P2-FIRST-SHOWCASE`** (decisions.jsonl) — taller backdrop (free, structural) vs a second
   layout from the forest's own tiles (art pass, cost unmeasured). A different PICTURE is ruled out.
3. **SP-6's spring A/B** — built 09-09, needs his ear.
4. **`NIGHT-REGION-LOOK`** — the night palette.

## Peer state at writing

- **sigil:** binary pair swapped to `700177b1` (md5 `324d85d6…` / `8c874ce1…`); **my rebuild closed it
  — all three ROMs byte-identical** to the pre-swap controls, preserved at
  `/home/volence/sonic_hacks/.aeon-control-roms-0dc0ff11/`. Outgoing pair aside at
  `.sigil-outgoing-1532b72f/`; keep `.sigil-pin-1532b72f` (the aside pair reads its size tables from it).
  **I OWE THEM ONE RUN:** commit `82838687`, link-assert failure renders located and never panics.
  Fixture must be an ensure over **two link-time symbol addresses** (`extern()` poisons comptime-ness;
  model at `engine/debug/sound_debug.emp:98`) built with `--check` — **a plain false ensure lands in
  the comptime bucket and proves the wrong path.** Throwaway worktree, throwaway branch. If it panics
  it is theirs.
- **hub:** carrying the spec; all my corrections applied there. Taking BOOT-REMEASURE.

## Method rulings banked this session (all in DEFERRED_WORK or the notes)

- **A predicted result is the weakest evidence available.** E1's falsifier returned *exactly* the
  predicted 264 B. A latch stuck at a constant, or one accumulating from any motion, produces the same
  agreement. **The rest control (0 B over the same 240 frames) is what made it a measurement.** Before
  accepting a measurement that matches your prediction, name the two ways the apparatus could produce
  that number without measuring anything, then run the case that separates them.
- **Harness defect worth remembering:** the DEBUG shape boots into free flight at 16 px/frame, which
  IS `CAM_MAX_Y_STEP`. The environment's resting condition MIMICS the condition under test — press B
  and let gravity do it, or you measure the capped case and call it physics.
- **A procedure written from outside a tree is a hypothesis about that tree.** Three of three
  experiments corrected the spec's procedure (E3's capacity constant, E2's field AND edge, E1's gate
  AND worst case). A procedure encodes an unwritten assumption about what is safe to disturb.
- **An unmeetable bar in a brief produces an invented measurement, not a refusal** — unless the agent
  has somewhere to put one. "s4.bin byte-identical" cannot be met (symbol names land in the deb2
  appendix, `build.sh:1086`). The available standard: image `[0, EndOfRom)` identical except `$18E/$18F`
  and `$1A7`, `EndOfRom` unmoved, zero code/data bytes moved.
- **Tracked-ness is a property the MERGE creates**, so `test_land_gate_classifier` is structurally
  unreachable from a branch. E2 was green on its branch and failed on the merged tree. Not carelessness.

## Housekeeping left undone, deliberately

- **The main folder was fast-forwarded but NOT rebuilt** after E1/E2 landed. Its `s4.debug.bin` is
  `76ea409b` (pre-fixture). `./tools/landing_build.sh` in the main folder refreshes it. **The emulator
  work above used the landing tree's ROM (`9250a9af`, `ec513055`) and its freshness was verified
  against disk before measuring** — do not repeat that measurement against the stale main-folder ROM.
- Worktrees `.aeon-e1`, `.aeon-e2`, `.aeon-e3` and branch `land-e2` are NOT tidied. All three tips are
  ancestors of master; check with `git merge-base --is-ancestor <tip> master` before removing.
- The stale-figure DOCFIX (`ART_PIPELINE_CONTRACT.md` capacity at lines 225/233/432/1544, reserve 80 →
  56) is booked, not done. **Do not "fix" `BG_STATIC_TILE_BUDGET = 320` on that line — it is still
  correct**, because capacity and reserve each shrank by 24.

## Context

**306,119 tokens measured at 2026-09-16T01:17:09Z** (input 2 + cache_read 304,790 + cache_creation
1,327), past the owner's 200k line. This handoff is the resume anchor; the session stopped clearable
rather than opening steps 1 to 5 on a large context.
