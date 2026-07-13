# OJZ scene-pin debug hook (`Debug_Scene_Freeze`) — design

**Date:** 2026-07-12
**Repo:** aeon (pure game/engine change; no suite-level surface)
**Status:** approved, pre-implementation

## Problem

Live verification of the **R-A1 ring-cull boundary** needs a controlled static
scene: a ring pinned at a screen edge with the camera held at a known position,
so a tester can `run_frames(N)` and read the SAT to observe whether the ring's
sprite is culled at the boundary.

The OJZScroll streaming test (`games/sonic4/test/ojz_scroll_test.asm`,
`GameState_OJZScroll_Update`) re-drives the scene every frame, so an
`emulator_write_memory` setup is clobbered within one frame:

- `Camera_Update` (line 157) moves the camera to follow `Player_1` → a pinned
  `Camera_X/Y` is overwritten.
- `EntityWindow_Scan` (line 167) loads/despawns rings + objects from the
  camera-window each frame (the despawn chain is inside its body, ~lines
  814–815) → a hand-placed ring is despawned or reloaded from level data.

This blocked the R-A1 ring-cull live confirmation (it was instead proven by
cull-math derivation + byte gate + a SAT-emit read). Ledger row:
`[oracle harness, 2026-07-11]` in
`sigil/docs/superpowers/notes/campaign-gap-ledger.md`.

## Scope

**In scope:** a minimal debug freeze var that pins the OJZScroll scene so a
`write_memory` camera+ring survives N frames, unblocking R-A1.

**Out of scope (recorded, not built):** Bug-2 grounded-wall-push. The OJZ test
has no terrain/wall (the player boots in debug-fly over open space), so a freeze
flag cannot manufacture a wall to push against. Bug-2 stays on the ledger's
"OR a normal playable level" path — a separate, larger piece of work.

## Design

### The variable

One RAM byte, `Debug_Scene_Freeze`, allocated in `engine/ram.asm` inside the
existing `ifdef __DEBUG__` block (the `Prof_*` region). Default 0 = normal
behavior. Harness-owned, so the `Debug_` prefix is correct
(the debug-harness family: `Debug_AssertObjLoop`, `Debug_MusicToggle`); the
`_Dbg_` infix is the subsystem-owned-mirror convention (`Sound_Dbg_Mirror`) and
does not apply here.

**Pad-byte double-booking — check current state, don't trust this spec's
snapshot.** As of master (post the `retro-fix-audit-1` merge, `5e946ca`) this
`__DEBUG__` block is entirely `ds.w`/`ds.l` — there is **no spare `ds.b` pad to
reuse** (the A2 walk-live-flag work in that batch is the kind of change that
consumes such pads, `Engine_RAM_End` shape-invariant). So adding a lone
`Debug_Scene_Freeze: ds.b 1` would make the block **odd** and shift every
`__DEBUG__` address after it. The implementation MUST inspect the block's
**current** layout at implementation time (not this spec's line numbers) and
re-establish word-evenness itself — concretely, add the byte **and** a
`ds.b 1 ; pad to even` immediately after (net 2 bytes, block stays even), unless
it finds a genuine odd/pad slot to land in. This is a symbol-table concern only
(RAM emits no bytes), but it still moves DEBUG-shape addresses — see the re-pin
check in Verification.

The entire hook is `__DEBUG__`-gated: the variable and the two guards compile
only into the debug build. Release `s4.bin` therefore takes no code change.
Verification loads `s4.debug.bin` with its `.lst`, so oracle resolves
`Debug_Scene_Freeze` by symbol for `write_memory` (the tester may also hardcode
the address).

### The hook

In `GameState_OJZScroll_Update` (`games/sonic4/test/ojz_scroll_test.asm`), gate
exactly the two re-drive calls that clobber a pinned scene, under
`ifdef __DEBUG__`:

```
    ifdef __DEBUG__
        tst.b   (Debug_Scene_Freeze).w
        bne.s   .skip_camera_update
    endif
        jsr     Camera_Update
    ifdef __DEBUG__
.skip_camera_update:
    endif
        ...
    ifdef __DEBUG__
        tst.b   (Debug_Scene_Freeze).w
        bne.s   .skip_entity_scan
    endif
        jsr     EntityWindow_Scan
    ifdef __DEBUG__
.skip_entity_scan:
    endif
```

(The two guards cover both load AND despawn, since the despawn chain lives
inside `EntityWindow_Scan`'s body.) The test state is not perf-critical, so
re-reading the flag per guard is fine and clearest — no register threaded across
the `jsr`s.

**What stays live by design:**

- `RunObjects`, `RingCollision`, `Render_Sprites`/`DrawRings` keep running, so
  the pinned ring's SAT emission and its screen-edge cull are live and
  observable — the entire point of R-A1. Freezing `EntityWindow_Scan` preserves
  the ring in the buffer; drawing/cull is a separate path and still executes.
- `Camera_X_Biased` re-derives from `Camera_X` every frame
  (`engine/objects/sprites.asm:181`), so pinning `Camera_X` via `write_memory`
  propagates into the SAT screen-X math with no extra work in the hook.
- **`RingCollision` stays live** — a ring parked *on the player* will be
  collected. Testers must place the pin **away from the player spawn point**.
- Forced debug-fly (from `Player_Init`) is left untouched. With no controller
  input the player is inert, and with `Camera_Update` frozen it cannot move the
  view.

### Tester flow (oracle, existing tooling)

1. Enter OJZScroll; let it settle.
2. `pause` — and **stay paused across steps 3–5**. All the writes plus the
   freeze must land while the emulator is stopped so no frame runs between the
   camera write and the freeze taking effect (otherwise one `Camera_Update` /
   `EntityWindow_Scan` fires against the half-set scene). Step frames only at
   step 6.
3. `write_memory` `Camera_X`/`Camera_Y` to the target position.
4. Hand-place the ring: `write_memory` the **6-byte ring-buffer entry** at a
   world position that lands at the screen-edge boundary, **and bump
   `Ring_Count`** to include it. The count bump is not optional — `DrawRings`
   iterates `Ring_Count` entries, so a ring written without incrementing the
   count **draws nothing** and the tester chases a phantom failure. The entry's
   `section_id` / `list_index` fields may be sentinel garbage (`$FF`): the
   despawn/window bookkeeping that would read them is frozen (`EntityWindow_Scan`
   skipped), so nothing cross-checks them.
5. `write_memory` `Debug_Scene_Freeze = 1`.
6. `run_frames(N)`.
7. Read the SAT (VRAM sprite table) → observe the ring's boundary cull.

**Why "away from the player spawn" carries more weight than it looks:**
`RingCollision` stays live (by design). If the pin overlaps the player it gets
collected — and because the entry's `section_id` is deliberately bogus (`$FF`),
`Collected_MarkRing` would then stamp a **garbage section** into the
collected-ring window, claiming a real collected-window slot for a nonexistent
ring and corrupting the streaming bookkeeping. So the placement rule is two
constraints, not one: (a) at the screen-edge boundary under test, and (b) far
enough from the spawn/player that `RingCollision` never touches it.

## Verification

- **Debug build assembles + boots.** Build `s4.debug.bin`; oracle boot-check
  green.
- **Re-pin check (claim, not assumed).** "No re-pin needed" is the *expectation*
  (only the DEBUG shape grows, and it grows in the `__DEBUG__` RAM block +
  debug-only code), but game-side code growth has moved `ASSEMBLED_LEN`-class
  pins before (the ring-art precedent). After the debug build, run
  `cargo run -p sigil-harness --bin repin -- --check` and **record the result**
  in the implementation notes. If it flags a drift, re-pin as part of this work.
- **Provenance.** The debug ROM hash **will** change. Note the `s4.debug.bin`
  provenance update in the merge commit.
- **Freeze-off neutrality.** With `Debug_Scene_Freeze = 0` (default), OJZScroll
  behaves exactly as before — the guards are inert. Confirm via a short
  behavior check (camera still follows, entity scan still runs).
- **Freeze-on pin survives.** With the tester flow above and
  `Debug_Scene_Freeze = 1`, read back `Camera_X` and the ring-buffer entry after
  `run_frames(N)` and confirm neither was clobbered.

## Coordination

A concurrent churn-scene agent is building an object-test-state variant. File
boundaries, no overlap:

- **This work** touches: `games/sonic4/test/ojz_scroll_test.asm`,
  `engine/ram.asm`. It stays **out of**
  `games/sonic4/test/object_test_state.asm`.
- **The churn-scene agent** stays out of the OJZ files.

## Ledger

Closes/advances the `[oracle harness, 2026-07-11]` row (R-A1 half). Bug-2
remains OPEN on the playable-level path. Update the row on merge.
