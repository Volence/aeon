# Parcel R1 — Palette Bands (Mid-Screen Restore) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.
>
> **HARD RULE — CONTROLLER-ONLY tasks:** Tasks 6, 10, 11, 12, 13 use oracle emulator MCP
> tools. **Never dispatch these to a subagent** — oracle MCP from background agents
> deadlocks. The controller session executes them inline. All other tasks are
> subagent-safe (build + file edits only).

**Goal:** Implement `OP_PAL_RESTORE` — a raster op that streams this frame's base-DMA
palette payload back into CRAM mid-screen, giving the effects vocabulary its OFF edge
(bands: fog slabs, tinted strips, top-half glows over ≤3 CRAM entries).

**Architecture:** A 128-byte engine-RAM snapshot (`Palette_Ship_Snap`) spliced per-line at
the `bclr` in `Enqueue_Dirty_Buffers`; a fifth raster opcode appended to the dispatch chain
(body emitted LAST, no blanking spin initially); comptime guards (one band/program,
equal-span-partner composition, both-fires-static, single-op restore fire, tree-wide `$8F`
refusal); a `band()` constructor owning the whole shape; gates (breakpoint-form poison gate,
handler source gate arm, F5 wiring, an expect-fail lane — the tree's first negative-build
coverage).

**Tech Stack:** sigil `.emp` (comptime + 68000 asm), Python gate tools driving oracle MCP,
`cargo`-built sigil binaries via `SIGIL_BUILD`/`SIGIL_EMIT`.

**Spec (single source of truth):** `docs/superpowers/specs/2026-08-16-parcel-r1-palette-bands-v6.md`
@ `ce8350a4`. Where this plan and the spec disagree, the spec wins — stop and reconcile.

**Standing project rules that bind every task:**
- Build: `DEBUG=1 ./build.sh` AND plain `./build.sh` (both shapes must stay green; sound is
  ON by default). `SIGIL_BUILD`/`SIGIL_EMIT` must be exported (build.sh hard-errors).
- Suite baseline at plan start: **3721/0** (sigil repo: `cargo test --release` with
  `--no-fail-fast`; full green = every binary, not binary 1).
- ROM bytes will move (new RAM + new code): after each byte-moving task, run the frozen-table
  repin and `refreeze` ritual (sigil repo: `cargo run --release -p sigil-harness --bin
  refreeze -- --freeze <name> --ab <ref>`) — **`refreeze --check` is NOT golden evidence**;
  a `--freeze --ab` needs the prose emulator note. Byte-moving is routine: do not ask
  permission, do record what moved.
- Commit after every task (exact paths, never `git add -A`; verify branch first —
  `git branch --show-current` must say the feature branch).
- `.emp` gotchas (spec §11): no multi-line ensure conditions; comptime free names resolve at
  the CALL SITE (inline literals in helper bodies); `{}` interpolates in ensure messages;
  tuples destructure only; no `break`/`continue`; `ensure` is non-aborting (Poison).
- If a step's premise turns out false at the file (a register is live, a line moved, a
  helper is missing), **STOP and report BLOCKED for that task** — do not silently adapt the
  design.

**Branch:** create `feature/parcel-r1-palette-bands` from master before Task 1.

---

## File Map

| File | Role in this parcel |
|---|---|
| `engine/ram.emp` | +`Palette_Ship_Snap: [u8; 128]` at the engine tail (Task 1) |
| `engine/system/buffers.emp` | 4 snapshot splices in `Enqueue_Dirty_Buffers` (Task 2) |
| `engine/effects/raster.emp` | `OP_PAL_RESTORE` const, 5th rung, restore body emitted last (Task 3) |
| `engine/effects/raster_dsl.emp` | enum variant, 14 match arms, 2 new helpers, pins, constructors, all guards (Tasks 4, 5, 8, 9) |
| `tools/emp_expect_fail.py` | NEW — the expect-fail lane runner (Task 7) |
| `games/sonic4/test/poison/*.emp` | NEW — poison modules, one per guard (Tasks 7, 8) |
| `tools/raster_cost_probe.py` | +F6 fixture (single restore fire) (Task 6) |
| `tools/effects_gates.py` | +F5 wiring, +E-B poison gate (Tasks 6b, 11) |
| `tools/raster_source_gate.py` | +restore arm (Task 10) |
| `build.sh` | wire `emp_expect_fail.py` into the tool-suite test block (Task 7) |
| `docs/benchmarks/effects-r1/GATE-EVIDENCE.md` | NEW — all measurements (Tasks 6, 12, 13) |
| `docs/ENGINE_ARCHITECTURE.md`, `docs/DEFERRED_WORK.md` | sync (Task 15) |

---

### Task 1: `Palette_Ship_Snap` RAM + repin

**Files:**
- Modify: `engine/ram.emp` (the tail region, immediately BEFORE the
  `if DEBUG == 1 @shape_divergent` replay block, AFTER `Ctrl_2_Ext_Held_Raw` — spec §7.1:
  before the shape-divergent block so both shapes keep equal offsets)

- [ ] **Step 1: Add the buffer.** Locate the comment `// --- Replay recorder` in the tail
  `vars` block of `engine/ram.emp` and insert immediately before it:

```
    // --- Parcel R1: the band restore's source (engine/effects/raster.emp OP_PAL_RESTORE) ---
    // Per-line copy of Palette_Buffer taken at each line's frame-top DMA enqueue
    // (engine/system/buffers.emp, spliced at the bclr — copy iff dirty AND accepted).
    // INVARIANT: Palette_Ship_Snap[line] == THIS FRAME'S base-DMA payload for that line
    // (specs/2026-08-16-parcel-r1-palette-bands-v6.md §2.2 — stated at full strength there:
    // a band's own line is dirty, enqueued, snapshotted and DELIVERED every frame).
    // Placed at the RAM TAIL, before the @shape_divergent block: ripples ZERO engine-RAM
    // addresses; Engine_RAM_End + all game RAM shift — a full game-side repin, routine.
    Palette_Ship_Snap:      [u8; 128],
```

- [ ] **Step 2: Build both shapes.**
  Run: `DEBUG=1 ./build.sh && ./build.sh`
  Expected: both green. If a region-overflow ensure fires, STOP (BLOCKED — RAM budget).

- [ ] **Step 3: Repin + refreeze.** Game-side pins moved (128 B). Fix every failing pin the
  build/gates name (derive each new expectation from the placer's own output — NEVER copy a
  neighbouring pin's number). Then in the sigil repo:
  `cargo run --release -p sigil-harness --bin refreeze -- --freeze parcel-r1-ram --ab master`
  and record one prose line of emulator evidence (boot `s4.debug.bin` in oracle, title
  reachable) in the commit message.

- [ ] **Step 4: Commit.**
```bash
git add engine/ram.emp <every repinned file the build named>
git commit -m "feat(effects): Palette_Ship_Snap — the band restore's 128-byte source (R1 Task 1)"
```

---

### Task 2: The four snapshot splices

**Files:**
- Modify: `engine/system/buffers.emp` (`Enqueue_Dirty_Buffers`, the four palette blocks at
  ~`:236-263` — re-locate by the `queue_static_dma(Static_Pal_Line0)` calls, line numbers
  will have drifted)

- [ ] **Step 1: Verify the register premise.** Read the proc header and the four palette
  blocks. Confirm: (a) the proc declares `clobbers(d0/a1-a2)` (was `:37-38`); (b) no live
  a1/a2 value crosses the palette blocks (each `queue_static_dma` macro establishes its own
  pointers). **If either is false, STOP — BLOCKED** (the splice shape below assumes a1/a2
  are per-splice scratch).

- [ ] **Step 2: Splice line 0.** Immediately AFTER `bclr #0, Palette_Dirty` (and before
  `.skip_pal0:`), insert:

```
        // R1 splice: snapshot line 0 iff dirty AND accepted (both guard branches are
        // upstream). Eight unrolled move.l on COST grounds (160 vs 244 cyc for a dbf
        // loop) — not register pressure; buffers.emp's own :278 note frees d0 by the
        // line-3 block. Spec §2.1.
        lea     Palette_Buffer, a1
        lea     Palette_Ship_Snap, a2
        move.l  (a1)+, (a2)+
        move.l  (a1)+, (a2)+
        move.l  (a1)+, (a2)+
        move.l  (a1)+, (a2)+
        move.l  (a1)+, (a2)+
        move.l  (a1)+, (a2)+
        move.l  (a1)+, (a2)+
        move.l  (a1)+, (a2)+
```

- [ ] **Step 3: Splice lines 1-3.** Identical blocks after each line's `bclr #N`, with the
  `lea` pairs `Palette_Buffer+$20`/`Palette_Ship_Snap+$20`, `+$40`/`+$40`, `+$60`/`+$60`
  respectively (and the comment line reduced to `// R1 splice, line N — see line 0`).

- [ ] **Step 4: Build both shapes.** `DEBUG=1 ./build.sh && ./build.sh` — green.

- [ ] **Step 5: Repin/refreeze** (bytes moved) as in Task 1 Step 3
  (`--freeze parcel-r1-splice --ab <task-1 commit>`).

- [ ] **Step 6: Commit.**
```bash
git add engine/system/buffers.emp <repins>
git commit -m "feat(effects): snapshot splices at the four palette bclrs (R1 Task 2)"
```

*(The behavioural test for this task is Task 11's poison gate — it cannot exist until the
opcode and gates land. Interim safety is the green build + Task 1's boot evidence.)*

---

### Task 3: The opcode — const, rung, body (emitted LAST)

**Files:**
- Modify: `engine/effects/raster.emp` (the opcode consts at ~`:94-173`; the compare chain at
  ~`:694-701`; the body AFTER `.op_run_ramp`'s body)

- [ ] **Step 1: Add the const** after `pub const OP_RUN_RAMP = 8` (locate by name):

```
// OP_PAL_RESTORE (Parcel R1) — the band's OFF edge: stream `count` base colours from
// Palette_Ship_Snap (this frame's base-DMA payload) back to CRAM. Appended LAST so the
// shared .op_region body and its oracle-calibrated EFX_BLANK_DELAY stay byte-identical;
// the SetReg fall-through pays the +16 rung tax (F1 396->412, F5 612->628, re-pinned in
// raster_dsl.emp). specs/2026-08-16-parcel-r1-palette-bands-v6.md §3.
pub const OP_PAL_RESTORE = 10
```

- [ ] **Step 2: Add the rung.** In the compare chain, after the `cmpi.w #OP_RUN_RAMP`/`beq`
  pair and BEFORE the `// OP_SET_REG` fall-through comment:

```
        cmpi.w  #OP_PAL_RESTORE, d1
        beq     .op_pal_restore
```

- [ ] **Step 3: Add the body — AFTER `.op_run_ramp`'s body ends** (the last emission of the
  op bodies; spec §3.1 — mid-chain insertion risks a silent branch word-relaxation):

```
    .op_pal_restore:
        // Band OFF edge: stream base colours from the ship snapshot. .op_region's shape
        // with TWO deliberate differences: the source is Palette_Ship_Snap (whose offset
        // IS the CRAM byte address — BuildStaticDMA maps Palette_Buffer+$00/20/40/60 to
        // CRAM $00/20/40/60 1:1), and there is NO blanking spin — dispatch at depth 4
        // already burned the region path's margin (+48 cyc). The spin site starts EMPTY;
        // EFX_RESTORE_DELAY is introduced here at the first nonzero calibration
        // (spec §3.2 ladder: leading dots -> add moveq #0 + dbf; straddle -> narrow the
        // stream count, no delay value exists).
        move.l  (a1)+, (a2)             // CRAM write command longword (a2 = VDP_CTRL)
        move.w  (a1)+, d1               // count-1
        lea     Palette_Ship_Snap, a2   // snapshot base (was VDP_CTRL)
        adda.w  (a1)+, a2               // + offset == CRAM byte address (payload D-F)
    .restore_loop:
        move.w  (a2)+, VDP_DATA
        dbf     d1, .restore_loop
        lea     VDP_CTRL, a2            // restore the control-port cursor
        dbf     d0, .op_loop
        jbra    .advance
```

  (`adda.w` sign-extension is safe: snapshot offsets ≤ 126. Do NOT spell `add.w` — the
  sigil add-to-An mis-encoding trap.)

- [ ] **Step 4: Build fails at the exhaustive matches — that is the expected failure.**
  Run: `DEBUG=1 ./build.sh`
  Expected at THIS point: **green** (the enum hasn't changed yet; the handler additions are
  self-contained asm). If it errors, fix the asm before proceeding.

- [ ] **Step 5: Read the listing.** In the emitted `.lst`, verify (a) every `cmpi/beq` rung
  in the chain still assembles with BYTE displacements (a word-relaxed rung is 20 cyc and
  falsifies the F1/F5 pins before they're even updated), and (b) the
  `lea Palette_Ship_Snap` form (record short/long — feeds Task 6's model check). If any
  rung relaxed to word: STOP — BLOCKED (the emission order needs rework, spec §3.1).

- [ ] **Step 6: Commit.**
```bash
git add engine/effects/raster.emp
git commit -m "feat(effects): OP_PAL_RESTORE — const, fifth rung, body emitted last (R1 Task 3)"
```

---

### Task 4: Enum variant + all 14 match arms + the four-literal pin

**Files:**
- Modify: `engine/effects/raster_dsl.emp` (enum at ~`:82-87`; the 12 match sites at
  ~`:590, 621, 635, 663, 676, 684, 693, 701, 710, 728, 847, 858` — re-locate by name; the
  depth-pin ensure at ~`:843-844`)

- [ ] **Step 1: Add the variant** to `RasterOp`:

```
    PalRestore(int, int),                 // (CRAM byte address, count) — the snapshot
                                          // offset IS the address (BuildStaticDMA's 1:1
                                          // mapping); one fact, one field (claim D-F)
```

- [ ] **Step 2: Build to enumerate the holes.**
  Run: `DEBUG=1 ./build.sh 2>&1 | grep -i "match\|PalRestore" | head -20`
  Expected: FAIL, sigil naming `PalRestore` as the missing arm at every match site. This
  failure list IS the test — every site in Step 3 must appear in it.

- [ ] **Step 3: Add the arms.** In each named match (locate by enclosing `comptime fn`
  name), add the `PalRestore(a, cnt)` arm:

| fn | arm |
|---|---|
| `op_words` | `PalRestore(a, cnt) => [10, comptime_vdp_cram_cmd_hi(a), comptime_vdp_cram_cmd_lo(a), cnt - 1, a],` — spell the cmd halves exactly as the `Cram` arm does (`vdp_comm(a, VdpTarget.Cram, VdpOp.Write) >> 16` / `& $FFFF`); the opcode literal is `10` per the module's inlined-literals note |
| `op_size` | `PalRestore(a, cnt) => 5,` |
| `op_stream_words` | `PalRestore(a, cnt) => cnt,` |
| `count_stream_pal_region_ops` | `PalRestore(a, cnt) => 0,` |
| `op_ship_cram_addr` | `PalRestore(a, cnt) => -1,` |
| `op_ship_stage_off` | `PalRestore(a, cnt) => -1,` |
| `op_reg_word` | `PalRestore(a, cnt) => 0,` |
| `op_ship_count` | `PalRestore(a, cnt) => 0,` |
| `op_mask` | `PalRestore(a, cnt) => 1 << (a >> 5),` |
| `op_is_reg` | `PalRestore(a, cnt) => 0,` |
| `op_dispatch_cyc` | `PalRestore(a, cnt) => RASTER_DISPATCH_RUNG_CYC * RASTER_DEPTH_RESTORE + RASTER_DISPATCH_HIT_CYC,` — mirror the `PalRegion` arm's spelling exactly |
| `op_work_cyc` | `PalRestore(a, cnt) => 64,` with comment: `// = RASTER_WORK_REGION_CYC(122) - the delay site(58: spin 54 + its moveq 4). DERIVED — Task 6 measures it (CLAIM 9); the minima in band() freeze only after that measurement.` |

- [ ] **Step 4: The depth pin.** Add beside the existing three depth consts:

```
const RASTER_DEPTH_RESTORE = 4
```

  and re-spell the pin ensure so it (a) names `OP_PAL_RESTORE` as the chain's LAST opcode
  and (b) carries the FOURTH term:

```
ensure(RASTER_DEPTH_CRAM == (OP_CRAM - OP_CRAM) / 2
    && RASTER_DEPTH_REGION == (OP_PAL_REGION - OP_CRAM) / 2
    && RASTER_DEPTH_RESTORE == (OP_PAL_RESTORE - OP_CRAM) / 2
    && RASTER_DISPATCH_RUNGS == (OP_PAL_RESTORE - OP_CRAM) / 2 + 1,
    "dispatch depth pins drifted from the opcode chain — update these FOUR literals together (and re-measure F1/F5: the SetReg fall-through pays every rung)")
```

  Update `RASTER_DISPATCH_RUNGS` itself from 4 to `5`.

- [ ] **Step 5: Add the two new total helpers** beside `op_mask` (each arm on one line, all
  five variants — sigil's exhaustiveness is the safety):

```
// op_cram_span — (CRAM byte address, byte length) of the entries an op WRITES; (-1, 0)
// for ops with no CRAM span. ADDRESS-keyed, never class-keyed: Vsram dispatches at the
// CRAM rung but its address is scroll space, not palette space (the op_mask precedent).
// The composition guard (raster_program) is the only consumer. Claim C-A.
comptime fn op_cram_span(o: RasterOp) -> (int, int) {
    return match o {
        SetReg(w)                      => (-1, 0),
        Cram(a, cols)                  => (a, 2 * cols.len),
        PalRegion(a, slot, pl, e, cnt) => (a, 2 * cnt),
        Vsram(a, vals)                 => (-1, 0),
        PalRestore(a, cnt)             => (a, 2 * cnt),
    }
}
// op_is_restore — 1 for the restore op only. §4.1's one-band count.
comptime fn op_is_restore(o: RasterOp) -> int {
    return match o {
        SetReg(w)                      => 0,
        Cram(a, cols)                  => 0,
        PalRegion(a, slot, pl, e, cnt) => 0,
        Vsram(a, vals)                 => 0,
        PalRestore(a, cnt)             => 1,
    }
}
```

- [ ] **Step 6: Build both shapes — green.** The F1/F5 fixture expectations in
  `effects_gates.py` are COMPUTED from `RASTER_DISPATCH_RUNGS`, so they move with the pin
  automatically; the two measured-equality ensures at ~`:925-934` (F1 396, F5 612) must be
  updated to **412** and **628** — but ONLY after Step 7 confirms them on hardware.
  Temporarily update the literals now to keep the build green, marked
  `// re-measured Task 6b`.

- [ ] **Step 7: Commit.**
```bash
git add engine/effects/raster_dsl.emp
git commit -m "feat(effects): PalRestore variant, 14 arms, op_cram_span/op_is_restore, four-literal depth pin (R1 Task 4)"
```

---

### Task 5: `pal_restore()` constructor (C-D: the wrap guard)

**Files:**
- Modify: `engine/effects/raster_dsl.emp` (the op-constructors section, after
  `stream_vsram`)

- [ ] **Step 1: Write the constructor** (mirror `stream_cram`'s ensure idiom exactly —
  inlined literals, one-line conditions):

```
// pal_restore — the band's OFF edge: stream `count` words of Palette_Ship_Snap (this
// frame's base-DMA payload) back to CRAM at `addr`. The snapshot offset IS the CRAM
// address (BuildStaticDMA's 1:1 mapping — claim D-F), so one field carries both.
// Authors do not call this directly in normal content — band() derives it from the ON
// op so the composition guard's partner spans are equal by construction.
pub comptime fn pal_restore(addr: int, count: int) -> RasterOp {
    ensure(addr >= 0 && addr <= 126, "pal_restore: CRAM byte address {addr} outside 0..126")
    ensure((addr & 1) == 0, "pal_restore: CRAM byte address {addr} is odd — colours are words")
    ensure((addr >> 5) != 0,
           "pal_restore: address {addr} is on CRAM line 0, the character's line — a restore there repaints the active character AND forces a per-frame line-0 re-assert via op_mask")
    ensure(count >= 1 && count <= 3,
           "pal_restore: {count} colours exceeds RASTER_CRAM_MAX (3) — the per-fire cycle budget; a band restores at most 3 entries (spec §1)")
    ensure(((addr >> 1) & 15) + count <= 16,
           "pal_restore: {count} colours from entry {(addr >> 1) & 15} runs past the end of CRAM line {addr >> 5} — the span would WRAP into the next line (at $7C+3, into line 0, the character's) and op_mask marks only the START line")
    return RasterOp.PalRestore(addr, count)
}
```

- [ ] **Step 2: Build both shapes — green.**
- [ ] **Step 3: Commit.**
```bash
git add engine/effects/raster_dsl.emp
git commit -m "feat(effects): pal_restore constructor — the CRAM wrap guard + line-0 refusal (R1 Task 5)"
```

---

### Task 6: **CONTROLLER-ONLY** — CLAIM 9 measurement (before ANY minima freeze)

**Files:**
- Modify: `tools/raster_cost_probe.py` (fixture list — F5 is at ~`:188-192`, pattern to
  copy), `engine/effects/raster_dsl.emp` (`op_work_cyc` restore arm if the measurement
  disagrees with 64)
- Create: `docs/benchmarks/effects-r1/GATE-EVIDENCE.md`

- [ ] **Step 1: Read the probe's fixture and injection mechanism** (`raster_cost_probe.py`
  top-to-bottom once). Add fixture **F6**: six identical fires, each a single
  `pal_restore`-shaped op (`{"k": "restore", "a": 0x48, "n": 3}`), with an `op_words`
  branch in the probe's transcribed encoder:

```python
def pal_restore(addr: int, count: int) -> dict:
    return {"k": "restore", "a": addr, "n": count}

# in op_words():
    if k == "restore":
        c = CRAM_WRITE | _delta(o["a"])
        return [10, (c >> 16) & 0xFFFF, c & 0xFFFF, o["n"] - 1, o["a"]]
```

  (The probe is deliberately a second encoder — a mis-encoding shows as the wrong fire
  count before any cycle figure is read.)

- [ ] **Step 2: Run the probe** (oracle foreground; ONE instance, `pgrep -a oracle_gui`
  first):
  `python3 tools/raster_cost_probe.py --rom s4.debug.bin --lst <listing> --only F6 --out /tmp/f6.json`
  Expected: a per-fire cycle figure. Derive measured `op_work_cyc` =
  measured_fire − (302 + 8 + 82 + 3×30 + 10).

- [ ] **Step 3: Reconcile.** If measured work == 64 (±0 — the probe is cycle-exact, spread
  0 over five boots), the model stands. If it differs: update the `op_work_cyc` arm to the
  MEASURED value, recompute the §6.2 minima rows that involve the restore fire
  (496/556 = 302+8+82+work+30/90+10), and note the delta in the evidence file. Either way,
  record the run (command, figure, derivation) in
  `docs/benchmarks/effects-r1/GATE-EVIDENCE.md` under `## CLAIM 9 — op_work_cyc`.

- [ ] **Step 4 (6b): Wire F5 + F6 into `effects_gates.py`.** Change `--only F0,F1,F3` to
  `--only F0,F1,F3,F5,F6` and add computed expectations beside `expect_f1`/`expect_f3`
  (the two-op F5 form — both ops' bundles over ONE fire base; F6 mirrors `fire3` with the
  restore's dispatch 82 and measured work):

```python
        wcram = emp_int("engine/effects/raster_dsl.emp", "RASTER_WORK_CRAM_CYC")
        # F5: reg_set + stream_cram(3) in ONE fire — base once, per-op bundles summed.
        fire_mixed = base + (fetch + rung * rungs + wreg + tail) \
                          + (fetch + hit + wcram + 3 * word + tail)
        expect_f5 = f0 + 6 * fire_mixed
        # F6: one single-op restore fire ×6 — dispatch pays 4 failed rungs + hit.
        wrest = emp_int("engine/effects/raster_dsl.emp", "RASTER_WORK_RESTORE_CYC")
        fire_rest = base + fetch + (rung * 4 + hit) + wrest + 3 * word + tail
        expect_f6 = f0 + 6 * fire_rest
```

  (If `op_work_cyc`'s restore arm is a bare literal rather than a named const, hoist it to
  `pub const RASTER_WORK_RESTORE_CYC` first so the gate computes from the shipped constant,
  never a typed-in copy — the derive-expectations rule.)

- [ ] **Step 5: Run the full gate suite** (controller):
  `python3 tools/effects_gates.py`
  Expected: all gates green, including F1 at its new 412 and F5 at 628. If F1 reads
  416/420: a rung relaxed to word — go back to Task 3 Step 5.

- [ ] **Step 6: Commit.**
```bash
git add tools/raster_cost_probe.py tools/effects_gates.py engine/effects/raster_dsl.emp docs/benchmarks/effects-r1/GATE-EVIDENCE.md
git commit -m "test(effects): F6 restore-cost fixture, F5 wired, CLAIM 9 measured (R1 Task 6)"
```

---

### Task 7: The expect-fail lane (the guards' test harness — BEFORE the guards)

**Files:**
- Create: `tools/emp_expect_fail.py`, `games/sonic4/test/poison/README.md`
- Modify: `build.sh` (the tool-suite test block added in `990dc4a5`)

- [ ] **Step 1: Write the runner.**

```python
#!/usr/bin/env python3
"""emp_expect_fail — the tree's negative-build lane (Parcel R1, spec §10.4).

Each case is a poison .emp module that MUST fail to build, with the expected guard
message. A case passes iff sigil exits nonzero AND stderr/stdout contains the expected
fragment. Known properties (spec [S5-10]): the manifest scan parses the WHOLE --root tree
per invocation (CI cost, not soundness), and the message match is fragile against wording
edits — a wrong/missing message still FAILS here, so drift is caught, but attribute
failures to wording first.
"""
import os, subprocess, sys, pathlib

AEON = pathlib.Path(__file__).resolve().parent.parent
SIGIL = os.environ.get("SIGIL_BUILD")
if not SIGIL:
    sys.exit("SIGIL_BUILD not set (same contract as build.sh)")

# (module path, entry id, expected message fragment)
CASES = [
    # populated by Task 8, one line per guard poison
]

def run_case(path: str, entry: str, expect: str) -> tuple[bool, str]:
    p = subprocess.run([SIGIL, "emp", "--root", str(AEON), "--entry", entry],
                       capture_output=True, text=True)
    out = p.stdout + p.stderr
    if p.returncode == 0:
        return False, f"BUILT CLEAN — the guard did not fire ({path})"
    if expect not in out:
        return False, f"failed but WITHOUT the expected message {expect!r} — wording drift or wrong guard ({path})"
    return True, "ok"

def main() -> int:
    if not CASES:
        print("emp_expect_fail: no cases registered (Task 8 adds them)"); return 0
    bad = 0
    for path, entry, expect in CASES:
        ok, why = run_case(path, entry, expect)
        print(f"  {'PASS' if ok else 'FAIL'}  {entry}: {why}")
        bad += 0 if ok else 1
    return 1 if bad else 0

if __name__ == "__main__":
    sys.exit(main())
```

  **Adapt the sigil invocation** to the real CLI (read `sigil --help` / how build.sh
  invokes it — the `emp --root/--entry` form above is the shape from the sweep-5 seat's
  read of `sigil-cli/src/main.rs:579`; verify flag names before committing). If the CLI
  cannot build a bare module as an entry, STOP — BLOCKED (the lane's premise needs a sigil
  change, which is a cross-repo decision).

- [ ] **Step 2: Poison modules parse-clean.** Create `games/sonic4/test/poison/README.md`
  stating: modules here are syntactically valid (the whole-tree manifest scan parses them
  on EVERY build), never imported by any real entry, and evaluated only by the expect-fail
  lane. Verify: `DEBUG=1 ./build.sh` stays green with the (empty) directory present.

- [ ] **Step 3: Wire into build.sh** beside the existing tool-suite test invocations:

```bash
run_tool_test "expect-fail lane" python3 tools/emp_expect_fail.py
```

  (Match the exact idiom of the block `990dc4a5` added — read it first.)

- [ ] **Step 4: Run it** — `python3 tools/emp_expect_fail.py` → "no cases registered", exit 0.
- [ ] **Step 5: Commit.**
```bash
git add tools/emp_expect_fail.py games/sonic4/test/poison/README.md build.sh
git commit -m "test(tools): emp_expect_fail — the negative-build lane, empty (R1 Task 7)"
```

---

### Task 8: The guards — each lands with its poison already red

For EACH sub-task: (a) write the poison module + register its CASE line → run the lane →
**expect FAIL ("BUILT CLEAN")**; (b) write the guard; (c) run the lane → PASS; (d) build
both shapes green; (e) commit. That is the TDD loop for comptime guards.

**Files:** `engine/effects/raster_dsl.emp` (`raster_program` at ~`:1124-1200`, `reg_set` at
~`:113-141`), `games/sonic4/test/poison/*.emp`, `tools/emp_expect_fail.py` (CASES).

- [ ] **8a — One band per program (§4.1).**
  Poison `poison_two_restores.emp`: a program of two fires each carrying
  `pal_restore($48, 3)` / `pal_restore($68, 2)` on lines 100/140, passed through
  `raster_program`, with a `data` declaration that reads the result (an unreferenced const
  is inert). Expected fragment: `"one band per program"`.
  Guard, in `raster_program` after the existing per-fire walk begins:

```
    comptime var restore_n = 0
    for f in fires { for o in fire_ops(f) { restore_n = restore_n + op_is_restore(o) } }
    ensure(restore_n <= 1,
           "raster_program: {restore_n} restore ops — one band per program (spec §4.1). The FIRST restore (authored order) is the one every later diagnostic describes; ensure is non-aborting, so fix this count first.")
```

- [ ] **8b — The composition guard C-A + rule 6 (§4.2).**
  TWO poisons:
  `poison_band_buried_tint.emp` — `compose([band(...E...), <tint over E at an earlier
  line>])`; expected `"would bury"`.
  `poison_patchable_band_fire.emp` — the sweep-5 K1 witness: `[B[0]] ++
  patchable([B[1]], ch: 0, lo: 100, hi: 150)`; expected `"must be static"`.
  Guard (after 8a's count, only when `restore_n == 1`; comment block carries the
  `check_intervals` grounding + falsifier verbatim from spec §4.2):

```
    if restore_n == 1 {
        // ---- C-A: the equal-span-partner composition guard (spec §4.2). ----
        // GROUNDING, load-bearing: patchable fire lines MOVE at runtime; this guard's
        // earlier/later comparison is sound ONLY because check_intervals forces strictly
        // ascending disjoint band intervals, so every reachable line of a patchable
        // record stays on one side of the restore. FALSIFIER: any relaxation of
        // check_intervals silently voids this guard.
        comptime var r_line = -1
        comptime var r_a = -1
        comptime var r_b = 0
        comptime var r_patch = 0
        for f in fires {
            for o in fire_ops(f) {
                if op_is_restore(o) == 1 && r_line == -1 {
                    r_line = fire_screen_line(f)
                    let (sa, sb) = op_cram_span(o)
                    r_a = sa
                    r_b = sb
                    r_patch = fire_is_patch(f)
                }
            }
        }
        // Rule 6 half 1 (claim E-A): the restore's OWN fire is static — a patchable
        // restore record hits .suppress above band_hi and the tint runs to the bottom
        // of the screen, silently (sweep 5 K1, raster.emp .suppress).
        ensure(r_patch == 0,
               "raster_program: the restore's carrying fire must be static — a patchable restore is the split spelling of a moving-bottom band, whose suppressed restore leaves the tint running to screen bottom (spec §4.2 rule 6)")
        comptime var partners = 0
        comptime var partner_patch = 0
        for f in fires {
            for o in fire_ops(f) {
                if op_is_restore(o) == 0 {
                    let (sa, sb) = op_cram_span(o)
                    if sa >= 0 && sa < r_a + r_b && r_a < sa + sb {
                        // Same-line intersection: order-decided winner. Dead once D-B
                        // ships (nothing else can share the restore's fire/line) — kept
                        // per the module's "a guard that cannot fire is not free" note,
                        // with D-B named as what deadens it.
                        ensure(fire_screen_line(f) != r_line,
                               "raster_program: a CRAM op on the restore's own line {r_line} — the merge order would decide which write wins (spec §4.2)")
                        if fire_screen_line(f) < r_line {
                            ensure(sa == r_a && sb == r_b,
                                   "raster_program: the op at line {fire_screen_line(f)} intersects the restore's span but is not its equal-span partner — the restore writes BASE and would bury it from line {r_line} down (spec §4.2)")
                            // Rule 6 half 2: the partner is static too (moving-top).
                            ensure(fire_is_patch(f) == 0,
                                   "raster_program: the restore's partner at line {fire_screen_line(f)} must be static — a patchable partner is the split spelling of a moving-top band (spec §4.2 rule 6)")
                            partners = partners + 1
                        }
                        // later lines: legitimate layering, unconstrained.
                    }
                }
            }
        }
        ensure(partners == 1,
               "raster_program: {partners} equal-span partners for the restore at line {r_line} — a band needs exactly ONE (its own ON op; zero = base-over-base authoring nonsense, two+ = one of them gets buried) (spec §4.2)")
    }
```

  (Comparison chaining does not exist — the two-sided interval test above is spelled as
  two `&&`-joined comparisons on ONE line each. If a line grows past the file's width
  idiom, factor a local helper with inlined literals.)

- [ ] **8c — Single-op restore fire, D-B (§4.2a).**
  Poison `poison_setreg_on_restore.emp`: a fire `[reg_set($8C81), pal_restore($48, 3)]`;
  expected `"carries the restore ONLY"`.
  Guard (inside the `restore_n == 1` block, using the op count `raster_program` already
  walks per fire):

```
        for f in fires {
            comptime var has_r = 0
            comptime var n_ops = 0
            for o in fire_ops(f) { has_r = has_r + op_is_restore(o) n_ops = n_ops + 1 }
            ensure(has_r == 0 || n_ops == 1,
                   "raster_program: the fire at line {fire_screen_line(f)} carries the restore plus {n_ops - 1} other op(s) — the restore's fire carries the restore ONLY: a SetReg ahead of it costs 110 cyc no delay can recover, and a second stream op races it for the one measured HBlank slot (spec §4.2a, claim D-B). S/H bands end with the static de-mix pair: reg_set a line above, restore alone on the bottom line.")
        }
```

  (Two statements on one line separated by a space is the file's `for` body idiom — check
  a neighbouring loop and match it exactly; if the file uses newlines, use newlines.)

- [ ] **8d — The `$8F` refusal, D-C + E-D (§4.2b).**
  TWO poisons: `poison_regset_8f.emp` (`reg_set($8F04)` in any program; expected
  `"autoincrement"`) and `poison_direct_8f.emp` (`RasterOp.SetReg($8F04)` constructed
  directly, bypassing the constructor; SAME expected fragment — this one proves the SCAN,
  not the constructor).
  Constructor ensure, in `reg_set` beside the `$8A` ban:

```
    ensure((word >> 8) != $8F,
           "reg_set: {word} writes reg $0F (autoincrement) — every span/mask computation in this module assumes stride 2 (op_cram_span, op_mask, the ship destination), so a mid-frame stride change silently voids them all. Revocable behind a stride-aware span model (spec §4.2b).")
```

  Program-level scan, in `raster_program` (unconditional — tree-wide, not band-scoped):

```
    for f in fires {
        for o in fire_ops(f) {
            ensure((op_reg_word(o) >> 8) != $8F,
                   "raster_program: an op writes reg $0F (autoincrement) — refused tree-wide; direct RasterOp.SetReg construction bypasses reg_set's ensure, this scan is the layer that cannot be dodged (spec §4.2b, claim E-D)")
        }
    }
```

- [ ] **8e — The ship refusal, CLAIM 6 (§4.3).**
  Poison `poison_ship_plus_restore.emp`: a program with a restore AND a
  `patchable(..., offscreen_ship: 1)` fire; expected `"offscreen_ship"`.
  Guard (inside the `restore_n == 1` block):

```
        for f in fires {
            ensure(fire_offscreen_ship(f) == 0,
                   "raster_program: a band cannot share a program with an offscreen_ship fire — on a shipping frame CRAM holds VARIANT colours while the snapshot holds BASE, so the restore would paint the dry palette over a submerged screen (spec §4.3). Note: this permanently excludes Sec0 (OJZ_TwoChannel) from bands — doubly so; its [3,220] channel band leaves no legal interval either.")
        }
```

- [ ] **8f: Full lane + both shapes green; run `python3 tools/effects_gates.py`
  (CONTROLLER if it needs oracle; it does — defer the run to Task 11 if executing 8 as a
  subagent, and say so in the report).**
- [ ] **8g: Commit** (one commit per sub-task, at each green):
```bash
git add engine/effects/raster_dsl.emp games/sonic4/test/poison/<module>.emp tools/emp_expect_fail.py
git commit -m "feat(effects): <guard name> + its red-first poison (R1 Task 8<x>)"
```

---

### Task 9: `band()`, `reg_sh_off()`, the minima, the hand-twin

**Files:**
- Modify: `engine/effects/raster_dsl.emp` (the preset-library section, after
  `fx_tint_band`; the hand-twin block at ~`:1442-1464` for the pattern)

- [ ] **Step 1: `reg_sh_off()`** beside `reg_sh_on()` (~`:150`), deriving from the same
  boot base so the pair cannot drift (mirror `reg_sh_on`'s derivation exactly, clearing the
  S/H bit instead of setting it; keep its comment style).

- [ ] **Step 2: `band()`** — the constructor owns the whole shape (claim E-C):

```
// band — the first multi-fire helper: an effect that turns ON at `top` and OFF at `bot`.
// The restore's (addr, count) is DERIVED from the ON op's span, so the composition
// guard's partner spans are equal by construction. sh: 1 emits the full three-fire S/H
// shape — the constructor must see the whole shape to compute the true minimum height
// (claim E-C; the merged [reg, tint] ON fire is measured against the gap to bot-1, so
// S/H needs height >= 3 where the bare shape needs 2).
// "Band height" = bot - top in SCREEN lines = the fire-line gap. NOT an inclusive count.
// Bands restore at most 3 CRAM entries (the stream ceiling x one restore op — spec §1).
// Cannot be handed to patchable (multi-fire refusal) — bands are static, both fires.
pub comptime fn band(top: int, bot: int, on: RasterOp, sh: int) -> array {
    ensure(sh == 0 || sh == 1, "band: sh must be 0 or 1")
    ensure(top < bot, "band: top {top} must be above bot {bot}")
    let (sa, sb) = op_cram_span(on)
    ensure(sa >= 0, "band: the ON op has no CRAM span (a reg-only or VSRAM band needs no restore — a register band is already two plain fires)")
    if sh == 0 {
        ensure(op_cost_cycles(on) <= (bot - top) * 488 - 302 - 10,
               "band: height {bot - top} is below this ON op's minimum — see the minima table (spec §6.2); a 1-word pal_region tint needs height 2")
        return [fire(top, [on]), fire(bot, [pal_restore(sa, sb / 2)])]
    }
    ensure(bot - top >= 3,
           "band: an S/H band needs height >= 3 — the merged [reg, tint] ON fire is charged against the gap to the S/H-off fire at bot-1 (spec §6.2)")
    return [fire(top, [reg_sh_on(), on]),
            fire(bot - 1, [reg_sh_off()]),
            fire(bot, [pal_restore(sa, sb / 2)])]
}
```

  **The `sh: 0` minimum-height ensure above is a SKETCH of the intent — spell it against
  the model the way `check_density` does** (via `fire_cost_cycles` of the actual emitted
  fire, not a hand expansion; read `check_density` at ~`:1014-1036` and reuse its charging
  form with inlined literals). If `op_cost_cycles`/`fire_cost_cycles` are not callable at
  this point in the file (definition order), STOP — BLOCKED, report the ordering.
  Freeze the numbers ONLY as measured by Task 6 (the restore-side gap is `check_density`'s
  job at composition; `band()`'s own ensure covers the ON→next-fire gap).

- [ ] **Step 3: Poisons for the constructor** (lane): `poison_band_h1_region.emp` (1-word
  `pal_region` band at height 1 — expected the minima message) and `poison_band_h2_sh.emp`
  (S/H band at height 2 — expected the S/H message).

- [ ] **Step 4: The comptime hand-twin (Gate 5).** Beside the existing `OJZ_TEST_HAND`
  pattern (~`:1442-1464`): hand-encode `band(100, 140, stream_cram($48, [$0E42, $0A20,
  $0640]), 0)` word-by-word into a `data` twin, then `first_mismatch` PLUS the separate
  `.len` ensure (blind in both directions without the pair). Follow the existing twin's
  exact spelling.

- [ ] **Step 5: Lane + both shapes green. Commit.**
```bash
git add engine/effects/raster_dsl.emp games/sonic4/test/poison/poison_band_h1_region.emp games/sonic4/test/poison/poison_band_h2_sh.emp tools/emp_expect_fail.py
git commit -m "feat(effects): band(sh:) + reg_sh_off + minima + hand-twin (R1 Task 9)"
```

---

### Task 10: **CONTROLLER-ONLY** — `raster_source_gate` restore arm

**Files:**
- Modify: `tools/raster_source_gate.py`; a test program install site (a `band()` program on
  an OJZ test section — follow how the existing gate's fixture program is installed, read
  the gate top-to-bottom first)

- [ ] **Step 1: Add the restore arm** following the existing region arm EXACTLY: resolve
  the restore loop's mangled local label (the body's `.restore_loop` — read the emitted
  symbol from the listing), set the breakpoint **at the instruction AFTER the `adda.w`**
  (the finished source pointer exists only there — the gate's own `:152-157` discipline),
  assert the exact stop PC, `deterministic=False`, and compare `a2` against
  `Palette_Ship_Snap + <addr>` — the restore's offset arithmetic is the bare CRAM address,
  NO `slot*128` term.
- [ ] **Step 2: Run it** (oracle foreground): expected — the gate reports the handler's
  computed source pointer equals the snapshot address. Poison the subject once (point the
  breakpoint at the region loop instead) to prove the gate can fail; restore.
- [ ] **Step 3: Commit.**
```bash
git add tools/raster_source_gate.py <fixture files>
git commit -m "test(effects): source gate observes the restore's computed pointer (R1 Task 10)"
```

---

### Task 11: **CONTROLLER-ONLY** — the E-B poison gate

**Files:**
- Modify: `tools/effects_gates.py` (new gate function, registered with the others)

- [ ] **Step 1: Implement** per spec §10.3, exactly:
  - breakpoint at **`buffers.emp`'s `beq .no_pal`** — the instruction AFTER
    `move.b Palette_Dirty, d0` (resolve via the deb2 symbols + listing, not a hardcoded
    address; oracle checks breakpoints BEFORE execution, so at this stop `d0` IS the
    pre-enqueue mask);
  - before resuming into the frame: write poison `$F1F1` over all 128 bytes of
    `Palette_Ship_Snap` (a word outside the CRAM `$0EEE` format), after asserting no
    fixture-palette word equals it;
  - at the SAME stop (post-splice — run to the proc's return breakpoint within the same
    VBlank), read the captured `d0` mask, `Palette_Ship_Snap`, and `Palette_Buffer`
    (frozen for the whole IRQ — CLAIM 1);
  - assert per line: line in mask → snapshot == `Palette_Buffer + line*32` (32 bytes);
    line not in mask → snapshot still `$F1F1` poison;
  - the fixture must include a **non-program line** for the retain half (the band's own
    line is dirty every frame by construction and can never exercise it);
  - claim scope in the gate's docstring: dirty-gating and copy extent; the `bcs` drop arm
    is untestable (spec §2.4) — say so.
- [ ] **Step 2: Prove both directions.** Run once against master's ROM (no splices → FAIL:
  poison retained on dirty lines); run against the branch ROM (PASS); temporarily break the
  line-2 splice's `lea` offset (+4) and confirm FAIL; restore.
- [ ] **Step 3: Record all three runs** in `docs/benchmarks/effects-r1/GATE-EVIDENCE.md`.
- [ ] **Step 4: Commit.**
```bash
git add tools/effects_gates.py docs/benchmarks/effects-r1/GATE-EVIDENCE.md
git commit -m "test(effects): breakpoint-form poison gate — mask from d0 at the stop, both directions proven (R1 Task 11)"
```

---

### Task 12: **CONTROLLER-ONLY** — snapshot cost measurement (CLAIM 8)

- [ ] **Step 1:** Oracle profiler **per-routine rows** (`VInt_Level`; confirm
  `Enqueue_Dirty_Buffers` exists as a row via `raster_cost_probe.py --dump` first — NEVER
  `interrupts.hint`): before/after on the same OJZ scene (master ROM vs branch ROM), steady
  state; expected delta ≈ +176 cyc (one dirty line).
- [ ] **Step 2:** One synthetic worst-case frame: dirty all four lines
  (`emulator_write_memory` `Palette_Dirty` = `$0F` while paused pre-VBlank), measure the
  same row; expected ≈ +704, and end-of-window position still inside blanking.
- [ ] **Step 3:** Record both in `GATE-EVIDENCE.md` under `## CLAIM 8`. Commit
  (`docs/benchmarks/effects-r1/GATE-EVIDENCE.md`).

---

### Task 13: **CONTROLLER-ONLY** — the two landing captures (§7.3)

- [ ] **Step 1: The restore's landing — the FIRST datum at this shape.** Install a
  `band()` test program on an OJZ section whose art shows the banded entries at the bottom
  row (pick the column against the pinned camera — `Debug_Scene_Freeze`, reset before
  capture). Column-bucket brightness at **8 px buckets** across the band's bottom row.
  Readings per the spec ladder: leading-edge dots → add `moveq #0`+`dbf` to the body
  (introduce `EFX_RESTORE_DELAY`), rebuild, re-measure; clean → record the constant and
  the capture as the calibration datum; **straddle** (leading at N, trailing at N+1) → no
  delay value exists — narrow the test band's stream count and re-measure; if even 1 word
  straddles, STOP and report (spec §3.2's escalation is exhausted — owner decision).
- [ ] **Step 2: The +16 mixed-fire measurement** on `OJZ_TC_PROG` ch 0's water row,
  S/H-seam method, 8 px buckets, branch ROM vs the recorded P2 baseline. Expected-harmless:
  seam drift ~14-15 px. **Failure = colour words spilling into the visible row** → STOP:
  **the vacant fallback slot is the OWNER'S re-ruling** (spec §3.3 candidates: per-fire
  delay word / stream-count narrowing / accept-if-sub-pixel). Do NOT retune
  `EFX_BLANK_DELAY`. No prognosis either way.
- [ ] **Step 3:** Record both captures (bucket tables, ROM CRCs, camera position) in
  `GATE-EVIDENCE.md`. Commit.

---

### Task 14: The committer registry (CLAIM 7 — attempt enforcing, ship advisory)

**Files:**
- Modify: `engine/system/buffers.emp` (comment block at the splices) and
  `engine/effects/raster_dsl.emp` or a new small `engine/effects/committers.emp`

- [ ] **Step 1: Attempt the enforcing form** (time-boxed: one honest attempt): a comptime
  registry such that an unregistered CRAM-reaching writer is a build error. Expected
  outcome per the spec: **no grounded mechanism exists** — if you find one, it is a NEW
  CLAIM: write it up, do NOT ship it unswept; report it.
- [ ] **Step 2: Ship the advisory floor:** a census list of frame-top committers as a
  comptime array + `ensure(<list>.len == N, "<message naming the census and its date>")`,
  with the residual risk stated in the invariant's own comment at the splice site
  (spec §8: "any future frame-top writer silently invalidates the snapshot — this census
  is advisory; declare yourself here").
- [ ] **Step 3: Build green; commit.**

---

### Task 15: Docs sync + the two stale comments + merge prep

- [ ] **Step 1:** Fix `raster_dsl.emp`'s cost-table comment (`adda.w (a1)+,aN` is **12**,
  not 8 — the pinned 122 is right, the attribution was off by 4) and
  `ojz_effects.emp:617-618`'s stale "526 against a 489-cycle line" (the current model's
  figures).
- [ ] **Step 2:** `docs/ENGINE_ARCHITECTURE.md`: add the band restore to the effects
  section (mechanism, invariant, the ≤3-entry limit, the guard set, the vacant fallback).
  `docs/DEFERRED_WORK.md`: book N-bands (behind entry-ownership) and moving bands (behind
  the representation question, rule 6 the seam, the `.suppress` trace the hazard record).
- [ ] **Step 3:** Full verification sweep before merge (the verification-before-completion
  gate): both shapes build; sigil suite still 3721/0 (or the new correct total if the lane
  added counted tests — state which); `python3 tools/effects_gates.py` all green;
  `python3 tools/emp_expect_fail.py` all cases pass; the three GATE-EVIDENCE sections
  populated. **Aggregate totals + failing-target lines — never tail a test run.**
- [ ] **Step 4:** Commit docs; then merge per superpowers:finishing-a-development-branch
  (merge to master only with everything green; if the +16 capture escalated to the owner,
  the merge WAITS on that ruling).

---

## Task order & dependencies

```
1 (RAM) → 2 (splices) → 3 (opcode) → 4 (arms+pins) → 5 (pal_restore)
                                             ↓
                       6 (CLAIM 9 + F5/F6 wiring — CONTROLLER)
                                             ↓
7 (lane) → 8a..8e (guards, poison-first) → 9 (band/minima/twin — needs 6's measurement)
                                             ↓
        10 (source gate — CONTROLLER) → 11 (poison gate — CONTROLLER)
                                             ↓
        12 (cost — CONTROLLER) → 13 (landings — CONTROLLER, may escalate to OWNER)
                                             ↓
                          14 (registry) → 15 (docs + merge)
```

Tasks 7 and 8a-8e are subagent-safe and independent of 6 — they may run while the
controller does Task 6. Task 9 MUST wait for Task 6 (minima freeze after measurement —
the spec's ordering rule).
