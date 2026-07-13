# OJZ scene-pin debug hook — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `__DEBUG__`-gated `Debug_Scene_Freeze` RAM flag that, when set, makes `GameState_OJZScroll_Update` skip `Camera_Update` and `EntityWindow_Scan`, so an `emulator_write_memory` camera+ring scene survives N frames for the R-A1 ring-cull boundary verification.

**Architecture:** One debug RAM byte + two `tst.b/bne.s` guards around the two per-frame re-drive calls that clobber a pinned scene. Debug-only (release `s4.bin` byte-identical). All work in an isolated git worktree (`aeon/.worktrees/ojz-scene-pin`, branch `feat/ojz-scene-pin` off master) so the shared working tree's `s4.bin` and the concurrent churn agent are untouched.

**Tech Stack:** 68000 assembly (asl via `tools/asl`), `DEBUG=1 ./build.sh`, sigil-harness `repin --check`, oracle headless harness for behavior verification.

**Spec:** `docs/superpowers/specs/2026-07-12-ojz-scene-pin-debug-hook-design.md`

**Coordination:** Files owned here — `engine/ram.asm`, `games/sonic4/test/ojz_scroll_test.asm`. Stay OUT of `games/sonic4/test/object_test_state.asm` (churn agent). Build only inside the worktree — never run `DEBUG=1 ./build.sh` in the shared tree (it overwrites `s4.bin`).

---

### Task 1: Allocate `Debug_Scene_Freeze` in the `__DEBUG__` RAM block

**Files:**
- Modify: `engine/ram.asm` (the `ifdef __DEBUG__` profiling block ending in `Prof_Effect_Used: ds.w 1` / `endif`)

- [ ] **Step 1: Inspect the CURRENT block layout** (do NOT trust the spec's line numbers — the A2 walk-live rail already reshaped this block on master)

Run: `grep -n "ifdef __DEBUG__" engine/ram.asm` then read that block. Confirm whether it ends on a word boundary (all `ds.w`/`ds.l` = even) or has a trailing `ds.b`/pad.

- [ ] **Step 2: Add the flag + restore evenness**

Add immediately before the block's `endif` (after `Prof_Effect_Used: ds.w 1`):

```
Debug_Scene_Freeze:     ds.b 1          ; nonzero = pin OJZScroll scene (skip Camera_Update + EntityWindow_Scan)
                        ds.b 1          ; pad to even (keep the __DEBUG__ block word-aligned)
```

(If Step 1 found the block already ends odd with a reusable pad byte, land `Debug_Scene_Freeze` in it instead and drop the extra pad — the invariant is "block stays word-even", not "always add 2 bytes".)

- [ ] **Step 3: Verify it assembles (debug) and the symbol exists**

Run (in the worktree): `DEBUG=1 ./build.sh 2>&1 | tail -3`
Expected: `Build complete: s4.bin` with no errors.
Run: `grep -c "Debug_Scene_Freeze" s4.lst`
Expected: `>= 1` (symbol present in the listing, so oracle can resolve it).

- [ ] **Step 4: Commit**

```bash
git add engine/ram.asm
git commit -m "feat(debug): add Debug_Scene_Freeze RAM flag (__DEBUG__ only)"
```

---

### Task 2: Gate the two re-drive calls in `GameState_OJZScroll_Update`

**Files:**
- Modify: `games/sonic4/test/ojz_scroll_test.asm` (`GameState_OJZScroll_Update`, the `jsr Camera_Update` at ~line 157 and `jsr EntityWindow_Scan` at ~line 167)

- [ ] **Step 1: Guard `Camera_Update`**

Replace:
```
        ; -- camera follows Player_1 (deadzone + preview-aware clamp) --
        jsr     Camera_Update
```
with:
```
        ; -- camera follows Player_1 (deadzone + preview-aware clamp) --
        ; DEBUG scene-pin: skip so a write_memory Camera_X/Y stays put.
    ifdef __DEBUG__
        tst.b   (Debug_Scene_Freeze).w
        bne.s   .skip_camera_update
    endif
        jsr     Camera_Update
    ifdef __DEBUG__
.skip_camera_update:
    endif
```

- [ ] **Step 2: Guard `EntityWindow_Scan`**

Replace:
```
        ; -- §4.9: camera-driven entity scan (load/despawn rings + objects) --
        jsr     EntityWindow_Scan
```
with:
```
        ; -- §4.9: camera-driven entity scan (load/despawn rings + objects) --
        ; DEBUG scene-pin: skip so a hand-placed ring isn't despawned/reloaded.
        ; (Despawn lives inside EntityWindow_Scan's body, so one gate covers both.)
    ifdef __DEBUG__
        tst.b   (Debug_Scene_Freeze).w
        bne.s   .skip_entity_scan
    endif
        jsr     EntityWindow_Scan
    ifdef __DEBUG__
.skip_entity_scan:
    endif
```

- [ ] **Step 3: Build both shapes — release must be byte-identical, debug must assemble**

Run: `./build.sh 2>&1 | tail -2 && sha256sum s4.bin`
Expected: builds; record the release hash.
Run: `git stash -- games/sonic4/test/ojz_scroll_test.asm engine/ram.asm 2>/dev/null; ./build.sh 2>&1 | tail -1 && sha256sum s4.bin; git stash pop`
— OR simpler: compare release `s4.bin` against the pre-change master build. The `ifdef __DEBUG__` guards emit nothing in the release (`DEBUG` unset) build, so the release ROM MUST be byte-identical to master's `s4.bin`.
Run: `DEBUG=1 ./build.sh 2>&1 | tail -2`
Expected: debug build succeeds.

- [ ] **Step 4: Commit**

```bash
git add games/sonic4/test/ojz_scroll_test.asm
git commit -m "feat(debug): OJZScroll scene-pin — gate Camera_Update + EntityWindow_Scan on Debug_Scene_Freeze"
```

---

### Task 3: Re-pin check + record (claim, not assumption)

**Files:** none (verification only)

- [ ] **Step 1: Run the re-pin check against the freshly built debug shape**

Run: `cd /home/volence/sonic_hacks/sigil && cargo run -p sigil-harness --bin repin -- --check 2>&1 | tail -20`
(The repin harness reads the aeon build outputs; ensure the DEBUG build in the worktree is the most recent aeon build it sees, or point it at the worktree per its `--help`.)

- [ ] **Step 2: Record the result**

If clean: note "repin --check: clean, no pins moved (DEBUG-shape RAM growth absorbed)" in the merge commit / ledger.
If it flags drift: the DEBUG shape grew a pin — apply the re-pin it reports, rebuild, re-run until clean, and record what moved.

---

### Task 4: Oracle behavior verification (freeze off = neutral, on = pin survives)

**Files:**
- Create (scratch, not committed): a Python harness script using the oracle headless launcher pointed at the worktree's `s4.debug.bin` + `s4.lst`.

- [ ] **Step 1: Stage the debug ROM + symbols for oracle**

Copy the worktree build to a stable scratch name: `cp s4.bin /tmp/.../s4.debug.bin && cp s4.lst /tmp/.../s4.debug.lst` (or point the tester directly at the worktree `s4.bin` from the DEBUG build).

- [ ] **Step 2: Freeze-OFF neutrality**

Boot the debug ROM headless, enter OJZScroll, `run_frames(30)` with `Debug_Scene_Freeze=0`, read `Camera_X`. Nudge (or just observe) that the camera tracks / the scene runs exactly as an unmodified debug build. Expected: identical behavior to master debug build (guards inert).

- [ ] **Step 3: Freeze-ON pin survives**

Sequence (stay paused across the writes): `pause` → `write_memory Camera_X/Y` → `write_memory` a ring entry + bump `Ring_Count` (away from spawn) → `write_memory Debug_Scene_Freeze=1` → `run_frames(20)` → read back `Camera_X` and the ring entry.
Expected: `Camera_X` unchanged (not re-driven) and the ring entry intact (not despawned). Optionally read the SAT to see the ring's boundary cull.

- [ ] **Step 3b: Confirm the flag is load-bearing**

Repeat Step 3 with `Debug_Scene_Freeze=0`: `Camera_X` should MOVE / the ring should be despawned within a frame — proving the pin is the reason, not a coincidence.

---

### Task 5: Merge to master + provenance + ledger

- [ ] **Step 1: Fast-forward master to include the implementation**

From the worktree (branch `feat/ojz-scene-pin`), only if master hasn't diverged:
```bash
git -C /home/volence/sonic_hacks/aeon fetch . feat/ojz-scene-pin
git -C /home/volence/sonic_hacks/aeon branch -f master feat/ojz-scene-pin   # FF only
```
If master diverged (churn agent merged something), rebase `feat/ojz-scene-pin` onto master first (files don't overlap → no conflict expected), then FF.

- [ ] **Step 2: Provenance note**

`s4.debug.bin` hash changes (DEBUG shape grew a byte). Record the new debug ROM hash + the repin result in the merge commit body.

- [ ] **Step 3: Update the ledger**

In `sigil/docs/superpowers/notes/campaign-gap-ledger.md`, the `[oracle harness, 2026-07-11]` row: mark the R-A1 half CLOSED (scene-pin hook shipped), Bug-2 still OPEN on the playable-level path.

- [ ] **Step 4: Clean up the worktree**

```bash
git -C /home/volence/sonic_hacks/aeon worktree remove .worktrees/ojz-scene-pin
```
