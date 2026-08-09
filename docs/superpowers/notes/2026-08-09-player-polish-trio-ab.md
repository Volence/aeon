# Player-polish trio (Harmony debts) — A/B + gate evidence

**Parcel:** `fix/player-polish-trio` (aeon + sigil), 2026-08-09. Three
S3K-parity fixes, each grounded against skdisasm before touching code:

1. **Roll animation rate** (`player_common.emp` `.ball`): recomputes the
   DUR_DYNAMIC hold as `max(0,($400-|gsp|))>>8` — S3K `Animate_Sonic`
   loc_12A2A rolls at 4−|gsp|, twice the walk flip rate; our shared $800
   walk hold had the ball at HALF the classic rate (Harmony defect #1).
   Verified: `anim_timer` pinned 0-1 through a decaying |gsp|≈$300-370 roll
   (old formula reads 4-5).
2. **Camera curl compensation** (`engine/level/camera.emp`): S3K
   `MoveCameraY` does `subq #5` on Status_Roll — ours now subtracts
   CURL_Y_SHIFT from the Y target when ST_ROLLING is set, tracking the
   STANDING center (no 5px camera step on curl/uncurl). Engine-generic
   (both constants engine-owned; non-rolling games pay one btst) — no new
   Game-contract knob. Instruction-verified: d0 $0242→$023D across the
   subq while rolled.
3. **Deform phase layer-anchoring** (`engine/level/parallax.emp`): the
   per-line H-deform sample base now folds in the plane's vscroll (FG camY,
   BG lerped current) at the per-band hoist — the wave rides the art, not
   the screen (Harmony defect #2, verified in-code: index was
   `phase + screen_line`). Mod-256 index math keeps the fold phase-safe.
   Behavior-neutral on OJZ (zero deform table); visual verify owed to the
   first act with a live deform table.

## Fixture re-record (items 1+2 change hashed trajectories — expected)

Recording build: trio+sound-pkg1 merged, debug crc `0x49781788`. Standing
fixture 1,721 ticks / 27 checks (272 B); slide 2,350 ticks / 37 checks
(336 B), Camera_Y excursion 2941→157 (both vertical row crossings).
`core_hash` stamp `0x2320340D` (recording-build gameplay core).

**Transient found and controlled:** the FIRST slide recording of the session
desynced its own replay deterministically at checkpoint tick 1474 (hash
1DCABB9C expected / 34572C5B actual) — a record/playback consistency
transient of that recording session, NOT structural: fixture 1 replayed
clean on the same build, and a SECOND slide recording (same timeline)
replays clean ×2. Practical rule: verify record-consistency by replaying
before embedding (the runbook already does); on a desync, re-record before
suspecting the engine. Also: a desync trap reads as `running=true` with a
frozen Logic_Tick from the MCP side (the handler's display loop) — check
`status.symbol_at_pc` for ErrorHandlerBlob BEFORE diagnosing an oracle
wedge (one healthy instance was killed on that misread this session).

## Verification (embedded, final shapes: debug `0x001B07EE`, release `0x52A4807D`)

- Standing fixture DEBUG ×2: net silent, done at tick 1723 both runs,
  full-WRAM `0xFEEB0607`/fnv `55D5B3837F2E413A` identical.
- Slide fixture DEBUG ×2: net silent, done at tick 2352 both runs,
  full-WRAM `0x425C1B0C`/fnv `2FB9639A27996479` identical.
- Release: standing fixture `Replay_Done=$FF`, live gameplay, no error
  screen.
