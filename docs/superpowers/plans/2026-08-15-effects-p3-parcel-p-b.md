# Effects P3 Parcel P-b — the runtime — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A runtime patcher walks P-a's table and moves N independent raster boundaries per frame, each anchored to its own world Y — deleting the magic offset, the single-channel RAM, and the one-moving-boundary-per-section limit.

**Architecture:** One VBlank-time loop (`Raster_PatchAll`) walks the ROM patch table at `template + 128`, clamps each patchable channel's line into its band, and stores the arm gap as the **low byte** of an `$8Axx` word. Seven symbols are deleted, not wrapped. `EffectsPreset` carries its world anchors **inline**.

**Tech Stack:** `.emp` (68000), sigil toolchain. No `.emp` test runner — a guard is proved by a **failing build**; runtime behaviour is proved on oracle.

**Spec:** `docs/superpowers/specs/2026-08-15-effects-p3-parcel-p-design.md` §6, §7 — read them, they contain the reasoning this plan only summarises.
**P-a evidence (what you inherit):** `docs/benchmarks/effects-p3-p-a/GATE-EVIDENCE.md`

---

## Before you start

```bash
export SIGIL_BUILD=/home/volence/sonic_hacks/sigil/target/release/sigil
export SIGIL_EMIT=/home/volence/sonic_hacks/sigil/target/release/emit_sound_blob
git checkout -b parcel/effects-p3-p-b
```

Baseline: aeon `9c9d7c75` / sigil `f00408e1`, chain 119. CRCs `416be247` / `9ef00c29` / `6af0112d` / `fdc82cc0`. This parcel **moves bytes in both sonic4 shapes** and must not move either demo shape.

**Six rulings are already made. Do not re-litigate them** — each was reached from a measured failure, recorded in the spec:

1. **`Raster_PatchAll` runs at VBlank.** Main-loop patching tears the arm chain: every arm is a *relative* gap, so a half-updated set desynchronises the whole tail, every frame the camera moves.
2. **Liveness is `Raster_Patch_Tab != 0`**, never `Active_Buf == Buf_B` — `Raster_VBlank`'s explicit-clear path never touches `Active_Buf`.
3. **Anchors are INLINE in `EffectsPreset`** (`[u16; RASTER_MAX_PATCH]`), never a pointer: a `Label` carries no length, and an `ensure` comparing one to an integer is unevaluable and passes silently.
4. **RAM is `Effects_World_Y[]`, owner-neutral**, plus a public `Effects_SetWorldY`. It stays in RAM — reading the preset's ROM array in place would make anchors immutable and foreclose rising lava.
5. **`clr.w Raster_Dense_Lines` at patched install.**
6. **`(absolute, Dn.w)` is not a 68000 addressing mode** — indexed access needs `lea` + `(An, Dn.w)`.

**Inversion ritual** (from P-a, use it for every new guard): flip the predicate false → build MUST fail with your message → restore → build green. Also show the guard **accepts** the adjacent legal case. A guard that refuses everything is as useless as one that refuses nothing.

---

## File Structure

| File | Change |
|---|---|
| `engine/ram.emp` | `Effects_World_Y[4]`, `Raster_Patch_Tab`; delete `Raster_Water_Line`, `Raster_Water_World_Y` |
| `engine/effects/raster.emp` | `Raster_PatchAll`, `Effects_SetWorldY`, `Raster_InstallPatched`; delete five procs/consts; VBlank call + teardown clears |
| `engine/effects/preset.emp` | `EffectsPreset` 32→38, inline anchors, `preset()` signature, install arm |
| `games/sonic4/data/effects/ojz_effects.emp` | convert a section preset to `patched:` (EFX-8) |
| `games/sonic4/test/ojz_scroll_test.emp` | drop the hand install + per-frame patch call |
| `docs/BUGS.md` | EFX-4 close + successor, EFX-8 close |
| `tools/effects_budget_model.toml` | `raster_state_bytes` |

---

### Task 1: RAM — add the new state, delete nothing yet

**Files:** Modify `engine/ram.emp` (the `Raster_State` region, ~line 277-318)

- [ ] **Step 1: Add both cells**

Inside `Raster_State`, after `Raster_Ramp_Step`:

```
    // The patch channel bank. NAMED FOR EFFECTS, NOT RASTER, deliberately: parcel W gives the
    // world anchor an owner, and the parallax deformation system is expected to become a second
    // READER of these same values. Naming them Raster_* would force W to relocate storage rather
    // than add a reader.
    Effects_World_Y:    [u16; RASTER_MAX_PATCH],  // authored world Y per patch channel
    // -> the ROM patch table (patched template + RASTER_BUF_SIZE). ZERO means "no patched
    // program is live", and it is the ONLY liveness test Raster_PatchAll may use: Raster_VBlank's
    // explicit-clear path zeroes Raster_Program but never touches Raster_Active_Buf, so an
    // Active_Buf-gated patcher would keep writing a dead buffer forever after a clear.
    Raster_Patch_Tab:   u32,
```

`RASTER_MAX_PATCH` is defined in `engine/effects/raster_dsl.emp`, a COMPTIME_HELPERS member, so it is glob-injected here — no import needed. Verify that assumption by building; if it fails, report it, do not add an import chain.

- [ ] **Step 2: Build all four shapes**

RAM grows 12 bytes; ROM should be unchanged or nearly so (RAM is not ROM). Record all four CRCs.

- [ ] **Step 3: Commit**

```bash
git add engine/ram.emp
git commit -m "feat(raster): Effects_World_Y bank + Raster_Patch_Tab"
```

---

### Task 2: `Raster_PatchAll` and `Effects_SetWorldY`

**Files:** Modify `engine/effects/raster.emp` (add after `Raster_PatchWaterWorldY`, which still exists at this point)

- [ ] **Step 1: Write the patcher**

```
// -----------------------------------------------
// Raster_PatchAll — move every patchable boundary to its world-anchored line. Walks the ROM
// patch table P-a's patched_program emitted at template+RASTER_BUF_SIZE.
//
// CALLED FROM Raster_VBlank, NOT THE MAIN LOOP, and that is load-bearing. Every arm word is a
// RELATIVE gap to the next fire, and this routine writes one byte per record scattered across
// the buffer. From the main loop it would run while Raster_HInt is walking that same buffer
// during active display: records already passed keep this frame's gaps, records ahead get next
// frame's, and because the gaps are relative the entire tail of the chain desynchronises — every
// frame the camera moves. The single-word water patch this replaces got away with main-loop
// timing only because its one arm is consumed at the frame-top rewind, making it structurally a
// next-frame write.
//
// THE S3K STEAL: every arm word is $8Axx INCLUDING the park word $8AFF, so the counter is the
// LOW BYTE and re-arming is one move.b with no ori and no masking. Park needs no special case.
//
// Table entry: [arm_off][line_src][band_lo_fl][band_hi_fl], all in FIRE-LINE space.
// -----------------------------------------------
proc Raster_PatchAll () clobbers(d0-d5/a0-a2) {
        move.l  Raster_Patch_Tab, d0
        beq     .none                       // liveness: the TABLE, never Active_Buf
        movea.l d0, a0
        lea     Raster_Buf_B, a1
        lea     Effects_World_Y, a2         // indexed access needs its own An
        move.w  (a0)+, d4                   // count (a WORD)
        subq.w  #1, d4
        moveq   #1, d0                      // prev fire line = L[1] = 1, priming record 1
        move.w  Camera_Y, d3                // 16.16 -> the integer word
    .entry:
        move.w  (a0)+, d1                   // arm_off
        move.w  (a0)+, d2                   // line_src
        bpl     .static                     // high bit clear -> a literal fire line
        andi.w  #RASTER_MAX_PATCH-1, d2     // channel index
        add.w   d2, d2                      // -> word offset
        move.w  (a2, d2.w), d2              // authored world Y
        sub.w   d3, d2                      // screen line; may go negative, meaningfully
        subq.w  #1, d2                      // -> fire line. ONE conversion, here.
        cmp.w   (a0), d2
        bge     .lo_ok
        move.w  (a0), d2                    // clamp up to band_lo_fl
    .lo_ok:
        cmp.w   2(a0), d2
        ble     .static
        move.w  2(a0), d2                   // clamp down to band_hi_fl
    .static:
        addq.l  #4, a0                      // step past the two band words
        move.w  d2, d5
        sub.w   d0, d5
        subq.w  #1, d5                      // gap = L[k] - L[k-1] - 1
        move.b  d5, 1(a1, d1.w)             // the low byte IS the counter
        move.w  d2, d0                      // prev = this record's fire line
        dbf     d4, .entry
    .none:
        rts
}

// -----------------------------------------------
// Effects_SetWorldY — move a patch channel's world anchor. THE named handle for every
// runtime-varying effect: rising lava, a flood line, a beat-driven pulse. Without it the only
// way to move a boundary is poking RAM at an index the author has to guess.
//   d0.w = channel   d1.w = world Y
// -----------------------------------------------
pub proc Effects_SetWorldY (d0: u16, d1: u16) clobbers(d0/a0) {
        andi.w  #RASTER_MAX_PATCH-1, d0
        add.w   d0, d0
        lea     Effects_World_Y, a0
        move.w  d1, (a0, d0.w)
        rts
}
```

- [ ] **Step 2: Assemble-check it**

Build. `Raster_PatchAll` has no caller yet — if sigil warns or errors on an uncalled non-`pub` proc, make it `pub` for now and note it; Task 4 gives it a caller.

**Verify the addressing modes actually assembled as intended.** This codebase has a recorded case of `add.w dN,aM` silently encoding as ADDX garbage. Disassemble or check the `.lst` for `move.w (a2,d2.w),d2` and `move.b d5,1(a1,d1.w)` and confirm they are the indexed forms.

- [ ] **Step 3: Commit**

```bash
git add engine/effects/raster.emp
git commit -m "feat(raster): Raster_PatchAll — N world-anchored boundaries, one byte store each"
```

---

### Task 3: `Raster_InstallPatched`

**Files:** Modify `engine/effects/raster.emp`

- [ ] **Step 1: Write it**

```
// -----------------------------------------------
// Raster_InstallPatched — install a patched template and seed its world anchors.
//   a0 = patched template   a2 = *u16 authored world Ys (RASTER_MAX_PATCH of them)
//
// a2 NOT a1: Raster_CopyPatchedTemplate declares clobbers(d1/a0-a1) and uses a1 as its Buf_B
// write pointer, so an anchor pointer in a1 is destroyed before it can be read.
//
// ORDER IS LOAD-BEARING. Raster_Patch_Tab is set BEFORE the copy points Active_Buf at Buf_B:
// the copy makes the buffer look live, and a Patch_Tab still holding the PREVIOUS template
// (or 0 at first install, which would read the vector table as a record count) inside that
// window is exactly the race Raster_PatchAll's VBlank timing would otherwise expose.
// -----------------------------------------------
pub proc Raster_InstallPatched (a0: u32, a2: u32) clobbers(d0-d1/a0-a2) {
        lea     RASTER_BUF_SIZE(a0), a1
        move.l  a1, Raster_Patch_Tab            // table first
        // Seed the anchors from the preset's inline array.
        lea     Effects_World_Y, a1
        moveq   #RASTER_MAX_PATCH-1, d0
    .seed:
        move.w  (a2)+, (a1)+
        dbf     d0, .seed
        // A dense run in flight belongs to the OUTGOING program. Nothing else clears it, so
        // crossing from the gradient section into a patched one mid-run leaves the handler in
        // .dense_body streaming a stale cursor while this program's records are never walked.
        clr.w   Raster_Dense_Lines
        jbsr    Raster_CopyPatchedTemplate      // sets Active_Buf = Buf_B
        jbra    Raster_PatchAll
}
```

- [ ] **Step 2: Clear `Raster_Patch_Tab` in BOTH teardown paths**

In `Raster_VBlank`: add `clr.l Raster_Patch_Tab` to the explicit-clear path (before `HBlank_Uninstall`) **and** to `.copy_program` (which re-points `Active_Buf` at `Buf_A`). Missing either leaves a stale table walked every VBlank against a buffer holding a different program.

- [ ] **Step 3: Build, commit**

```bash
git add engine/effects/raster.emp
git commit -m "feat(raster): Raster_InstallPatched + Patch_Tab teardown in both VBlank paths"
```

---

### Task 4: Call `Raster_PatchAll` from `Raster_VBlank`

**Files:** Modify `engine/effects/raster.emp`

- [ ] **Step 1: Add the call**

In `Raster_VBlank`, after `.no_install` and before `HBlank_Install`. It early-outs on `Raster_Patch_Tab == 0`, so a section with no patched effect pays one `move.l`/`beq`.

- [ ] **Step 2: Check the cross-seam pin question**

`Raster_PatchAll` stays inside the raster module, so no new cross-seam reference is created. **Confirm this** — if any part lands in `engine/system/game_loop.emp` instead, a `[[symbol]] name = "Raster_PatchAll" tests = ["game_loop_port"]` row is needed in sigil's `repin.toml`, per the `Palette_Compose` precedent. Report which case holds.

- [ ] **Step 3: Build all four shapes, commit**

---

### Task 5: `EffectsPreset` — inline anchors, 32 → 38

**Files:** Modify `engine/effects/preset.emp`; every `preset(...)` call site

- [ ] **Step 1: Rewrite the struct, spelling the FULL field table**

Do not write a delta — this struct's declared size has already gone stale once (see its own comment).

```
pub struct EffectsPreset (size: 38) {
    ep_pal:            *u8      @ $00,
    ep_parallax:       *u8      @ $04,
    ep_raster:         *u8      @ $08,
    ep_patched:        *u8      @ $0C,
    ep_cycle:          *u8      @ $10,
    ep_variants:       [*u8; 2] @ $14,
    ep_patch_world_ys: [u16; RASTER_MAX_PATCH] @ $1C,   // inline: a Label carries no length
    ep_transition:     u16      @ $24,
}
```

- [ ] **Step 2: Update `preset()`**

`patch_world_y: int = 0` becomes `patch_world_ys: array = [0, 0, 0, 0]`. Replace the old `patched != 0 || patch_world_y == 0` ensure — it dies under the rename, because comparing a Label to an integer is unevaluable — with a length check that IS evaluable:

```
    ensure(patch_world_ys.len == RASTER_MAX_PATCH,
           "preset(): patch_world_ys must name one world Y per patch channel")
```

**Prove it fires** by passing a 3-element array.

- [ ] **Step 3: Verify the sibling ensure is not already vacuous**

`preset()`'s existing `raster == 0 || patched == 0` exclusivity ensure compares two `Label`s to 0. Prove by inversion with **real Labels on both** (not literal-0 defaults) that it still fires. If it does not, that is a finding: book it in `docs/BUGS.md` rather than silently relying on it.

- [ ] **Step 4: Update the install arm**

In `Effects_InstallPreset`, the patched branch passes `lea EffectsPreset.ep_patch_world_ys(a3), a2` and calls `Raster_InstallPatched`. Mind that `a3` holds the preset pointer and must survive.

- [ ] **Step 5: Update all five OJZ preset call sites; build; commit**

---

### Task 6: Delete the seven symbols

**Files:** `engine/effects/raster.emp`, `engine/ram.emp`, `games/sonic4/data/effects/ojz_effects.emp`, `games/sonic4/test/ojz_scroll_test.emp`

- [ ] **Step 1: Delete**

`WATER_TEMPLATE_ARM0_OFF`, `Raster_PatchWaterLine`, `Raster_PatchWaterWorldY`, `Raster_InstallWater`, `Raster_InstallPatchedWorldY`, `Raster_Water_Line`, `Raster_Water_World_Y`, and the co-located arm0 `ensure` in `ojz_effects.emp` (superseded by P-a's guard 6).

**`ojz_effects.emp` line ~22 has a `use` importing two of them — that is a hard compile break if missed.** Two more are named inside `ensure` MESSAGE TEXT (`raster_dsl.emp`'s `RASTER_BUF_SIZE` ensure and `preset.emp`'s exclusivity ensure); those do not break the build, so grep for them deliberately and reword.

- [ ] **Step 2: Rewrite the scroll test**

`ojz_scroll_test.emp` loses its hand install (~line 286-288) and its per-frame `Raster_PatchWaterWorldY` call (~line 384). The install is now the preset's job (Task 7).

- [ ] **Step 3: Confirm zero sigil-side impact**

P-a's review established there are **zero** sites in the sigil repo for all seven. Re-verify with `rg` in `/home/volence/sonic_hacks/sigil` — if that has changed, stop and report.

- [ ] **Step 4: Build all four shapes; commit**

---

### Task 7: EFX-8 — make the patched path live again

**Files:** `games/sonic4/data/effects/ojz_effects.emp`

This is the task that makes every later gate mean something. Until now, **no patched program has rendered since Parcel C2** (`docs/BUGS.md` EFX-8): total binding drove the channel past "off" into unreachable.

- [ ] **Step 1: Convert a section preset to `patched:`**

Pick the section the scroll test spawns into. By `preset()`'s exclusivity ensure, that section **surrenders its static raster program** — that is expected and is a declared delta, not a regression. Bind `OJZ_TwoChannel` with world Ys placing channel 0 near the spawn view and channel 1 below it.

Choose the world Ys from the section's actual geometry — read `Camera_Y` at spawn on oracle, do not guess.

- [ ] **Step 2: Build, boot, and confirm the path is LIVE**

On oracle: break after install and confirm `Raster_Patch_Tab != 0` and `Raster_Active_Buf == Raster_Buf_B` **after** the first section crossing (frame 2+), which is exactly where EFX-8 killed it before.

- [ ] **Step 3: Commit**

---

### Task 8: The gate — absolute predicted rows on oracle

**This is foreground work for the controlling session. Subagents must NEVER touch oracle MCP — it deadlocks.**

- [ ] **Step 1: Pin the camera at three positions**

For each, compute the predicted screen row per channel as `wy_i - Camera_Y` and record it BEFORE looking. Include one position where a channel clamps to `lo` and one where it clamps to `hi`.

- [ ] **Step 2: Measure the FRAMEBUFFER, not CRAM**

`emulator_read_cram` cannot see a mid-scanline CRAM write during active display — it returns the re-asserted base palette and reads as "the effect did nothing". Screenshot and find the row transitions.

- [ ] **Step 3: The claim, stated so it can fail**

Each boundary lands on its predicted absolute row, at all three camera positions, with the two channels distinguishable by colour. **Do NOT phrase this as "their separation changes"** — two world-anchored channels hold a CONSTANT separation, so that predicate passes broken single-anchor implementations and fails correct ones.

- [ ] **Step 4: Two negative controls**

(a) An overlapping band pair must fail the BUILD (P-a's guard 2). (b) Replacing one channel's anchor with a fixed screen row must make the separation drift by exactly the camera delta.

- [ ] **Step 5: Write `docs/benchmarks/effects-p3-p-b/GATE-EVIDENCE.md`**

Predicted rows beside measured rows, all three positions, both controls, and an explicit statement of what is NOT proved.

---

### Task 9: Ledger surgery and docs

- [ ] **EFX-4 CLOSES** — it is scoped entirely to the patched template, which is now padded. Open a **successor** entry against the site it never named: `Raster_VBlank .copy_program`'s fixed 128-byte read of short static ROM programs into Buf_A. Its existing citations are stale and its named subject `Raster_InstallWater` no longer exists.
- [ ] **EFX-8 CLOSES**, citing Task 8's evidence.
- [ ] `tools/effects_budget_model.toml`: `raster_state_bytes` 288 → its new value; verify against `RASTER_STATE_SIZE` (the `[symbols]` gate should catch a mismatch — confirm it does by inverting).
- [ ] `docs/ENGINE_ARCHITECTURE.md` §7.13: add the runtime half.
- [ ] `docs/EFFECTS_AUTHORING.md`: `Effects_SetWorldY` and the world-anchor authoring model. Remove the "ENCODER ONLY" caveats P-a added.

---

### Task 10: Ritual

Order matters — **freeze first, then the suite**. Golden ROM images are regenerated by the freeze, so running the suite first reports them red for a byte-moving parcel.

- [ ] Four shapes build; **both demo CRCs unchanged**.
- [ ] Four shapes **boot**.
- [ ] `SIGIL_WARNINGS=full` unreachable diff vs master: empty.
- [ ] `python3 tools/emp_helper_closure.py`: clean.
- [ ] `cargo build --release -p sigil-cli -p sigil-harness` (BOTH binaries).
- [ ] `refreeze --freeze parcel-p-b --ab docs/benchmarks/effects-p3-p-b/GATE-EVIDENCE.md`.
- [ ] Re-verify all four CRCs **after** the freeze; if the ROM moved, re-capture and re-freeze.
- [ ] `cargo test --release --no-fail-fast` — read aggregate totals and every failing-target line, never a tail. Baseline 3716/0, a **lower bound**.
- [ ] `refreeze --check` + `repin --check`.
- [ ] Merge aeon and sigil **as a pair**.

---

## Self-review

**Spec coverage:** §6.1 VBlank → Task 4. §6.2 routine → Task 2. §6.3 liveness/teardown → Tasks 2, 3. §6.4 install/RAM/setter → Tasks 1, 2, 3. §6.5 preset → Task 5. §6.6 deletions → Task 6. §7 gate → Task 8. §0.1 EFX-8 → Task 7. §9 ledger → Task 9.

**Known soft spots, stated rather than hidden:**
- Task 2's register assignment is written but unverified against a real assembly; Step 2 exists to check the indexed forms encode correctly, given this project's recorded silent mis-encoding of `add.w dN,aM`.
- Task 7's world Ys cannot be chosen from a document — they need a live `Camera_Y` reading.
- The clamp's below-viewport behaviour (a boundary rendering at `hi` instead of vanishing) is a **declared delta** from today's park semantics, not a defect. Record it in the gate evidence.
