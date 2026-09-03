# The canopy gap (item 17): a found cause, proven invisible, and a clean search beyond it

Taken 2026-09-03 on branch `diag/canopy-gap-cause`, based on `origin/master` at `c7ee7075`.
`s4.debug.bin` built with `SIGIL_BUILD`/`SIGIL_EMIT` pointed at the sigil repo's release
binaries, `AEON_SKDISASM_DIR` set per the standing env recipe. All measurements below are
against a headless `oracle-aether` spawned by `tools/aether_instance.py` — never the owner's
window, never `mcp__oracle__*`.

## The method, and why it is the whole point

Item 17 required "a found cause and a fix, not a backgrounded card." Two derived (code-read)
explanations for the canopy gap had already been proposed and refuted by measurement before
this parcel started (`docs/DEFERRED_WORK.md`, "the 64-vs-80 head-column suspect is REFUTED";
"THE d-45 CANOPY-GAP MEASUREMENT WAS WRONG, THE DEFECT IT NAMED IS REAL"). A third derivation
was explicitly out of scope. The instrument built for this
(`Canopy_Probe`/`Canopy_Fire`/`Canopy_Persist` in `engine/level/section.emp`, the shadow writes
in `engine/level/plane_buffer.emp`, `tools/canopy_record.py`) had never actually been run
against a live machine before this session — see "The reader was broken" below.

## The reader was broken before any of this could start

`tools/canopy_record.py`'s `read_live()` read:

```python
async with AetherInstance(rom=rom) as inst:
    b = inst.bus
```

`AetherInstance` has neither `__aenter__`/`__aexit__` nor a `.bus` attribute — it exposes a
synchronous `start()`/`reap()` pair (`tools/aether_instance.py`), and `start()` itself calls
`asyncio.run()` internally for its handshake, so it cannot even be invoked from inside an
already-running event loop. **Every call to this function raised before reading a single byte
from a live machine.** Fixed to match the spawn-then-async-body shape every other gate in this
tree uses (`tools/tile_cache_fill_gate.py`'s `main()`): spawn `AetherInstance` synchronously in
the caller, hand its socket path into a plain `async def`. Confirmed working:

```
$ python3 tools/canopy_record.py --rom s4.debug.bin --lst s4.debug.lst
canopy_record:
  fires: C1 31006  C4 46056 ...
```

(That first successful run above was against an UN-SETTLED machine — `canopy_record.py` run
standalone spawns its own fresh emulator and reads immediately with zero frames executed, so its
"first" reading was RAM garbage from before boot code ran. This is a separate, real gap in the
standalone tool — it can only ever observe a machine it also drove — which is why the actual
reproduction below uses a purpose-built driver that settles, plays, and reads off the SAME
connection.)

**This fix is reader-only.** The runtime instrument in the DEBUG ROM (`Canopy_Fire`,
`Canopy_Persist`, `Canopy_Probe`, the shadow writes) is byte-for-byte unchanged — only the tool
that reads its RAM was touched.

## The driver

`tools/canopy_gap_exercise.py` (new, committed) is a single headless session that:

1. Settles 180 frames (the tree-wide boot-to-gameplay constant), verifies `Logic_Tick` advances.
2. **P1/P2** — long real RIGHT then LEFT runs with real jumps (button A — the DEBUG shape arms
   `CHEAT_DEBUG_FLY` at boot per `GameState_OJZScroll_Init`, which excludes B from the jump mask,
   so A/C are the buttons that reliably jump for the whole session).
3. **P3** — rapid direction reversals straddling both of OJZ act 1's internal section seams
   (world X 2048 and 4096).
4. **P4** — a debug-fly sweep of BOTH axes across the whole 3×3 grid (fly avoids an unrelated
   defect — see "A defect not chased" below — where real physics has no wall at the act's right
   edge).
5. **P5** — five warp-mailbox hops to distant sections (both far corners, the centre, back to
   spawn), each followed by real MOVING play rather than a static settle, since the untested
   combination flagged in `Debug_Warp_Consume`'s own comments is a moving camera meeting a
   post-warp redraw.
6. **P6** — a final long right run.

`Canopy_Rec_Code` is polled every ~150-frame slice throughout (fine enough that a fire cannot
sit unexamined across a whole phase's frame budget). **Total: 21,439 frames (357 s of game time)
in 56 s of wall clock, covering all 9 of OJZ act 1's sections** (`world sections (col,row)
visited` in the run log; a 10th, targeted follow-up run confirmed the one section the main
campaign happened to skip, (0,1), is clean too).

## It fired — on the very first attempt

C1 (a visible plane column holding the wrong world column) latched at **frame 554** of a fresh
boot, the very first time the campaign reached the act's right edge. Over the full campaign, C1
fired 2,080 times and C4 (a row anchor missing the visible columns) fired 63 times. Every single
one of them is the same cause, confirmed by direct inspection of the decoded record
(`docs/measurements/2026-09-03-canopy-gap-right-edge-record.json`, produced by a clean,
warp-free, fly-free run that holds RIGHT from spawn and does nothing else):

```
LATCHED: C1  a visible plane COLUMN holds the wrong world column
  at frame 552, camera (5824, 144) px = world cell (728, 18)
  visible world columns 728..768, rows 18..46
  plane column 0: wanted world column 768, holds 704
    difference +64 = +1 wrap twins of 64 columns (512 px)
```

## The cause

`Camera_X_Max` (the right-edge clamp `Camera_Init` computes as
`grid_w << SECTION_SIZE_SHIFT - SCREEN_WIDTH`) is **5824** for OJZ act 1
(`3 << 11 - 320`). Once the camera rests there, `cam_col = 5824 >> 3 = 728`, and the last
column the engine TRACKS as potentially visible is `cam_col + SCREEN_LAST_COL_MAX` =
`728 + 40` = **768**. But the act's last VALID tile column is `grid_w * 2048 / 8 - 1` = **767**
— column 768 is one tile past the edge of the map, inside no section, and never gets a
legitimate write. Its plane-A shadow slot (`768 mod 64 = 0`) keeps whatever the ring wrote there
64 columns earlier (world column 704), forever, for as long as the camera sits at the wall. C4's
63 fires are the same fact seen from the row-fill side: a row write's anchor correctly stops at
767 (the last valid column) instead of reaching for 768, and C4's own derived requirement reads
that as "short by 1."

`SCREEN_LAST_COL_MAX` = `(7 + SCREEN_WIDTH - 1) >> 3` = 40, not 39, **by design** — it exists so
a screen scrolled to a non-tile-aligned position (any `camX` not a multiple of 8) has a 41st,
partially-visible tile column correctly tracked. That is correct everywhere except at this one
spot: the exact clamp.

## Proven invisible — this is not the reported symptom

Both `SECTION_SIZE_SHIFT` (2048, i.e. `1 << 11`) and `SCREEN_WIDTH` (320) are engine constants
and both are multiples of 8, so `Camera_X_Max` is **always** exactly tile-aligned — the clamp
never leaves any fine-scroll remainder. At zero fine-scroll the VDP only needs 40 whole tile
columns (`cam_col..cam_col+39`), and all 40 of those are valid (`728..767`). The 41st tracked
column is real in the RAM shadow but **never reaches the CRT** at this exact camera position.

Confirmed two ways, both with the camera pinned exactly at `Camera_X_Max` (verified live:
`camX=5824`, `remainder camX&7=0`):

1. **Screenshot** (`docs/measurements/2026-09-03-canopy-gap-right-edge.png`, taken via
   `emulator/screenshot` on the same live session that had just fired C1 237 sweeps in a row):
   continuous canopy/foliage art across the full 320 px width, no seam, no blank strip, no
   wrong-colour column at the right edge.
2. **Pixel-column dump** of `x=304..319` (the physical rightmost 16 px): normal, varying colour
   content column by column, no anomaly.

The instrument's own reader (`tools/canopy_record.py`) even hints at this directly: "a single
run at the LEADING edge is a streamer that fell behind; a run in the MIDDLE of the screen is not,
and is the interesting shape." Every fire in this campaign was the single-column leading-edge
run, never a middle-of-screen run.

## Beyond that one cause: clean, including at maximum predicate sensitivity

`tools/canopy_gap_exercise.py` classifies this exact shape live (generically, off
`Camera_X`/`Camera_X_Max`/`SCREEN_LAST_COL_MAX` — never pinned to OJZ's numbers) and clears it so
the campaign can keep searching. It fired and was cleared 22 times across the full 21,439-frame
run. **Nothing else ever latched** — no other C1, no C4 anywhere but the same edge case, across
every section, both directions, both internal seams, the full vertical range, five warp
destinations each followed by real moving play.

**The persistence-threshold caveat was tested directly, per the brief.** `docs/DEFERRED_WORK.md`
states plainly: "if C1 or C4 fires during ordinary play with no visible gap, the predicate is too
tight and `CANOPY_PERSIST_FRAMES` is the first thing to suspect" — and the converse matters too:
an EMPTY record does not distinguish "no defect occurred" from "the latch is too strict to see
it." `CANOPY_PERSIST_FRAMES` was lowered from 8 to 1 (maximum sensitivity — fires on a single
disagreeing sweep instead of requiring 8 consecutive), `s4.debug.bin` rebuilt, and the identical
deterministic campaign re-run. **Result: byte-for-byte identical fires** — same frames, same
positions, same edge cause, nothing new. This is the sharper of the two possible outcomes: it is
not that a short-lived, self-healing disagreement was being hidden by an over-strict latch — at
1-frame sensitivity there is nothing left to hide. The constant was reverted to 8 immediately
after (`git diff engine/system/constants.emp` clean) and `s4.debug.bin` rebuilt canonical before
this document was written.

## What this means for the owner's sighting

**Still unaccounted for — and now more tightly bounded.** The found cause is real and
reproducible on demand, but it is structurally invisible (proven, not argued), so it cannot be
what the owner saw. Per this parcel's brief: a found-but-not-matching engine cause does not need
a fix, and the instrument's own "what it misses" list says where a real sighting would have to
live instead — art faults (page eviction, ZX0 decode, block dictionaries) that leave plane-A
addressing perfect, plane B, sub-cell artifacts (VSRAM/HSCROLL, parallax, sprite masking), or
anything lasting under one frame at the sweep point. None of those are plane-A cell addressing,
which is everything C1/C4 can see. This campaign says plane-A cell addressing is clean on OJZ act
1 to the limit of an exhaustive, maximally-sensitive automated drive.

**Worth flagging even though it doesn't need a fix: the generic shape is a latent hardening
opportunity.** `SCREEN_LAST_COL_MAX` over-tracks by exactly one column past whichever axis a
camera clamp pins to an act's last valid tile. It is invisible today only because
`SECTION_SIZE_SHIFT` and `SCREEN_WIDTH` both happen to be multiples of 8. If a future act ever
computed its edge clamp differently, or either constant changed, this would stop being invisible.
Not fixed here (nothing observable changes, and the brief's scope for an engine cause that never
fires the visible symptom is "found and named," not "fixed") — recorded so nobody re-derives it.

## A defect not chased

While reaching the right edge under real physics (not fly), Sonic runs straight off the map —
there is no wall there. Measured: player X reached 11,120 world px against a 6,144 px act width,
`x_vel` reading 0 the entire time, `status` 0x08 (airborne), before a slow multi-thousand-frame
drift back toward the map. This has nothing to do with canopy/plane-A addressing (the CAMERA
clamps at `Camera_X_Max` regardless of where the player physically is) and was not investigated
further — it cost real exploration budget (the first full-campaign attempt, before
`classify_and_maybe_clear` learned to warp the player back, spent its entire P1+P2 budget stuck
recovering from one fall) but is out of this item's scope. Left for whoever picks up player
physics at act edges.

## Coverage this campaign does not claim

- **One level.** OJZ act 1 only, and it is a short test level — full horizontal traversal at
  speed takes well under 10 seconds, which is also why the right-edge clamp dominates any long
  straight-line run. No other zone/act, no other tileset, no other block-dictionary shape.
- **No long unbroken session.** The longest single stretch without a clear-and-warp intervention
  here was roughly 2,600 frames (P2 in the very first, unfixed campaign attempt, entirely spent
  in the fall-off-the-edge drift, not new exploration). The actual novel-territory legs are all
  a few hundred frames each.
- **Nothing outside plane-A cell addressing.** Art faults, plane B, sub-cell/VSRAM effects and
  anything under one frame are outside what C1/C4 can see by design (`docs/DEFERRED_WORK.md`,
  "WHAT IT MISSES").

## What to try next

1. Point the exercise driver at a full Sonic-4-shaped act once one exists (not the OJZ test
   level) — a real act's greater length would let a long RIGHT run explore far more territory
   before ever meeting an edge clamp.
2. If the owner can describe roughly where or under what action he saw the gap (which zone,
   moving which direction, jumping/rolling/idle), aim the driver there specifically rather than
   broad coverage.
3. Since plane-A addressing is now clean at this sensitivity, the next instrument to build (if a
   sighting still needs chasing) should watch one of the causes outside this one's reach: art
   pool page residency/eviction during a page-in, or a plane-B-specific shadow.

## Artifacts

- `docs/measurements/2026-09-03-canopy-gap-right-edge.png` — screenshot, camera pinned exactly
  at `Camera_X_Max`, C1 latched and firing every sweep. No visible defect.
- `docs/measurements/2026-09-03-canopy-gap-right-edge-record.json` — the full decoded canopy
  record (all four shadow snapshots) from the clean, warp-free right-edge repro.
- `docs/measurements/2026-09-03-canopy-gap-exercise-capture.json` — the record at the end of the
  full 21,439-frame campaign (cleared/empty, since every fire encountered was the known edge
  cause and none survived uncleared to the end — the counters `Canopy_Hits` inside it are the
  campaign's real totals: C1 2080, C4 63, both attributable to the one cause above).
- `tools/canopy_gap_exercise.py` — the driver itself, kept for the next attempt.
