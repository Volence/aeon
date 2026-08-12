# Effects Suite Phase 1 — Raster Engine Core + Per-Section Palettes

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **REPO LAW:** read `CODING_CONVENTIONS.md` before writing any code. `.s`/`.w`/`.l` on every branch. `function`/comptime for all build-time math. No `mulu`/`divu`.
>
> **EMULATOR RULE:** all oracle MCP work is done by the CONTROLLER session in the foreground — never from a subagent (deadlocks; see memory/feedback_no_emulator_in_subagents). Tasks 4 and 8 are controller-only.

**Goal:** Ship the sparse HInt raster dispatcher (delta-programmed line counter, variable-length command walker, VBlank re-arm + double-buffer seam), the `sec_pal` per-section palette consumer, and `sec_raster_table` wiring — gated by an OJZ test section showing a palette region boundary + Shadow/Highlight toggle on oracle **mid-scroll**.

**Architecture:** Two-tier raster engine per `docs/superpowers/2026-08-11-effects-suite-design.md` §4 — this phase builds the sparse tier only (`SET_REG`, `CRAM`, `END`; dense runs are Phase 2). Compiled programs are data: a header (palette re-assert mask + frame-init register words) followed by line-sorted variable-length entries. HInt fires only on event lines (counter = delta to next event). VBlank re-arms every frame (level + lag paths) and re-asserts the base palette so mid-frame CRAM writes stay transient.

**Tech Stack:** `.emp` (sigil), 68000, VDP HInt (IRQ4), oracle MCP for verification.

**Branch:** `feat/effects-p1-raster-core` off clean `master`. The spec commit `3da87fe6` lives on `feat/character-dispatch`; if it hasn't merged yet, cherry-pick it onto this branch first so the spec travels with the work.

**Key facts discovered in exploration (trust these, verify only if a step fails):**
- HBlank infra EXISTS, dormant, zero callers: `engine/system/hblank.emp` — `HBlank_Install` (line 54; `a0`=handler, `d0.b`=counter; patches the RAM jmp slot `HBlank_Vector_Slot`, writes `$0A` shadow + dirty bit, sets IE1 bit `$10` in reg `$00` shadow), `HBlank_Uninstall` (line 74; restores idle `rte`, clears IE1). CPU is at IPL `$2300` (boot.emp:307) so IRQ4 is gated by IE1 alone.
- VDP shadow idiom: `move.b val, VDP_Shadow_Table + OFF` then `ori.l #(1 << OFF), VDP_Dirty_Mask`. Offsets: `VDP_HINT_OFF = $0A`, `VDP_MODE1_OFF = $00` (engine/vdp.emp:31-34). Reg `$0C` (S/H = bit 3, boot value `$81`) has NO named offset const yet.
- Direct CRAM write pattern (release_fault.emp:73-74): `move.l #vdp_comm(0, VdpTarget.Cram, VdpOp.Write), VDP_CTRL` / `move.w #$000E, VDP_DATA`.
- VInt_Level: engine/system/vblank.emp:110-242. Flush_VDP_Shadow at :151, Enqueue_Dirty_Buffers at :153. `VInt_Lag` (:255-325) runs a reduced pipeline and MUST mirror the raster re-arm.
- Section boundary hook: `Parallax_CheckBoundary`, engine/level/parallax.emp:153-188 — at label `.crossed` (after the `Section_GetSecPtrXY` out-of-grid guard), `a0` = fresh `Sec*`.
- `Sec` struct (engine/structs.emp:110-132): `sec_pal` at `$10`, `sec_raster_table` at `$18` — both dead today. Convention: pointer field 0 = "keep current".
- Palette: `Palette_Buffer` (128 B) + `Palette_Dirty` (bits 0-3) at engine/ram.emp:224-227; `Enqueue_Dirty_Buffers` (engine/system/buffers.emp:212) clears bits only on successful enqueue.
- RAM pattern: `mark X, … mark X_End,` inside `pub vars upper_ram` (model: `Parallax_State`, ram.emp:241-269) + comptime `ensure` span guard (parallax.emp:32). New engine RAM ripples only `Engine_RAM_End` + game RAM.
- New module registration: (1) `module engine.effects.raster in raster`; (2) add the module path to the sigil registry in `crates/sigil-harness/src/native.rs` (**sigil repo**, `$SIGIL_BUILD`'s source tree); (3) add the head-label to the `order` array in `games/sonic4/map.toml:55-83` AND `games/demo/map.toml:15-27` (VInt calls the raster hook, so every game links it). Natural slot: adjacent to `"Parallax_Init"`.
- Golden-ROM gates live in the sigil repo (`native_full_rom`, `pins_rs_is_current`), not build.sh — local builds stay green; the paired repin/refreeze ritual happens once at the end (Task 8), per docs/superpowers/notes/2026-08-08-golden-rebaseline-clean-head.md and 2026-08-09-replay-net-rerecord-ab.md. `refreeze --check` is NOT sufficient evidence (memory: reference_refreeze_check_is_not_the_goldens).

**Testing model (TDD adapted for 68k):** comptime `ensure` guards are the unit-test layer (they fail the build); each task ends with a `DEBUG=1 ./build.sh` proving assembly + contract closure; runtime truth is oracle, concentrated in the calibration checkpoint (Task 4) and the gate (Task 8). Never claim green from a partial log — aggregate results (memory: feedback_never_tail_a_test_run).

---

## Task 0: Branch + Research Sweep

**Files:**
- Create: `docs/research/2026-08-12-raster-hint-survey.md`

- [ ] **Step 1: Branch setup**

```bash
cd /home/volence/sonic_hacks/aeon
git checkout master && git pull --ff-only 2>/dev/null; git checkout -b feat/effects-p1-raster-core
# If docs/superpowers/2026-08-11-effects-suite-design.md is absent on master:
git cherry-pick 3da87fe6
```

- [ ] **Step 2: Reference research (project law — all sources, no skipping)**

Answer these questions, each with a file/URL citation, in the survey doc. Sources: the 8 reference disassemblies (paths in `CLAUDE.md` §Reference Projects) + plutiedev.com + md.railgun.works + Kabuto's hardware notes + SpritesMind.

1. **Reg `$0A` counter semantics, exactly** (plutiedev "Raster effects"/"HInt", Kabuto notes): when does the counter reload (every line during VBlank + after firing?), and for "currently at line L, want next fire at line M", is the write value `M-L-1`, `M-L`, or `M-L-2`? Is a mid-HInt write of `$8Axx` effective for the next fire or the one after? Record the rule as `RASTER_DELTA(M, L) = ...` — Task 3 consumes it, Task 4 verifies it empirically.
2. **Batman & Robin HInt dispatch** (`The Adventures of Batman and Robin/` disasm): how does its raster table dispatch — per-entry counter reprogram or fire-every-line? What registers does its handler save?
3. **S.C.E. water line** (`Sonic-Clean-Engine-S.C.E.-/`): find `HScroll_Deform`/water HInt code — where in HBlank does it write CRAM, and the PAL `$700`-cycle delay-loop trick location.
4. **skdisasm S3K water**: how S3K arms the water-line HInt and what it does about CRAM dots.
5. **Ristar HInt scripting** (`ristar_disasm/`, HBlank → `$FFEA70` RAM): the RAM-script dispatch pattern — anything worth stealing for our cursor-in-RAM walker.
6. **TF4 / Gunstar / Alien Soldier / Vectorman**: one paragraph each — do they use HInt at all, and for what.
7. **CRAM dot timing**: per plutiedev/SpritesMind, how many CRAM writes fit in one H40 HBlank without visible dots on the following line; note the FIFO depth (4 words) constraint. This calibrates the Phase-1 "≤3 colors per line" budget.
8. **S/H mid-frame toggle**: any documented hardware quirk toggling reg `$0C` bit 3 mid-frame (Kabuto, SpritesMind)? (Mega Turrican does it for water — confirm nothing special is needed.)

- [ ] **Step 3: Write the survey doc**

Structure: one `##` per question above, each ending in a **Ruling** line (the fact the implementation will use). Final section: **Format deltas** — anything below in Tasks 1-3 contradicted by research (flag; do NOT silently change the plan — STOP and report BLOCKED per memory/feedback_constraints_need_escape_hatch).

- [ ] **Step 4: Commit**

```bash
git add docs/research/2026-08-12-raster-hint-survey.md
git commit -m "docs(research): raster/HInt survey for effects P1 (all refs + online)"
```

---

## Task 1: Raster Program Format + Module Skeleton

**Files:**
- Create: `engine/effects/raster.emp`
- Modify: `games/sonic4/map.toml` (order array, :55-83), `games/demo/map.toml` (order array, :15-27)
- Modify (sigil repo): `crates/sigil-harness/src/native.rs` (module registry)

**The program format (the Phase-1 contract — Aurora and the DSL compile to this in later phases):**

```
; Header
dc.w pal_dirty_mask    ; bits 0-3: palette lines Raster_VBlank ORs into Palette_Dirty
                       ; EVERY frame while installed (re-asserts base palette so
                       ; mid-frame CRAM writes are transient)
dc.w init_count        ; N register words applied during VBlank every frame
dc.w init[N]           ; pre-composed $8xxx words (frame-top state, e.g. S/H off $8C81)
; Entries — sorted ascending by line; same-line entries adjacent; walker executes
; all entries matching the current line in one interrupt.
dc.w line              ; 0..223
dc.w op                ; jump-table byte offset: OP_SET_REG / OP_CRAM / OP_END
...args (op-specific)...
; OP_SET_REG args: dc.w $8xxx              (one pre-composed VDP register word)
; OP_CRAM args:    dc.l vdp_comm(addr, Cram, Write)
;                  dc.w count-1            (count ≤ RASTER_CRAM_MAX = 3)
;                  dc.w color[count]
; OP_END:          no args; its line word is RASTER_LINE_END = $7FFF (sorts last)
```

- [ ] **Step 1: Write the module with constants, comptime constructors for entries, and ensure-based format tests**

Create `engine/effects/raster.emp`:

```
// engine/effects/raster.emp — sparse HInt raster dispatcher (effects suite P1).
// Design: docs/superpowers/2026-08-11-effects-suite-design.md §4.
// Programs are DATA (header + line-sorted variable-length entries, format above
// in the plan / mirrored in ENGINE_ARCHITECTURE §7.2 at merge). HInt fires only
// on event lines: each interrupt executes all entries for the current line, then
// reprograms reg $0A with the delta to the next event line.
module engine.effects.raster in raster

// use-list: start empty; add imports only as the compiler demands them, matching
// the style of engine/level/parallax.emp's header

// ---- command opcodes (byte offsets into the HInt jump table, Task 3) ----
pub const OP_SET_REG      = 0
pub const OP_CRAM         = 4
pub const OP_END          = 8

pub const RASTER_LINE_END = $7FFF     // END sentinel line — never matches a real line
pub const RASTER_CRAM_MAX = 3         // colors per CRAM entry (dot budget, survey Q7)
pub const RASTER_BUF_SIZE = 128       // bytes per RAM working buffer (Task 2)

// ---- comptime entry constructors (P1 minimal — NOT the Phase-3 DSL; these are
// the format's own smoke tests + what Task 7's test program is built from) ----
pub comptime fn raster_set_reg(line: int, regword: int) -> [u16; 3] {
    ensure(line >= 0 && line <= 223, "raster_set_reg: line {line} out of 0..223")
    ensure((regword & $8000) == $8000, "raster_set_reg: {regword} is not an $8xxx register word")
    return [line, OP_SET_REG, regword]
}

pub comptime fn raster_end() -> [u16; 2] {
    return [RASTER_LINE_END, OP_END]
}

// (OP_CRAM entries are wider and irregular — Task 7 lays one out with explicit
// words; the Phase-3 DSL owns the general constructor.)
```

Follow `engine/level/parallax_dsl.emp` for exact comptime array-return syntax; if `[u16; 3]` literals need a `comptime for`, mirror how `deform_sine` builds arrays.

- [ ] **Step 2: Register the module**

1. Sigil repo: add `engine/effects/raster.emp` to the module registry in `crates/sigil-harness/src/native.rs` — copy the registration line-shape of `engine/level/parallax.emp` exactly (fixed registry, not a tree walk). Rebuild BOTH sigil release binaries (memory: stale sigil binaries are a known gate trap): `cargo build --release` in the sigil repo, confirm `$SIGIL_BUILD` mtime moved.
2. `games/sonic4/map.toml`: no order entry yet — the module emits no bytes until Task 3's procs exist. Defer both map edits to Task 3 Step 3.

- [ ] **Step 3: Build**

```bash
DEBUG=1 ./build.sh
```
Expected: builds green (comptime-only module, no bytes). If sigil errors "unknown module": the registry edit or binary rebuild was missed.

- [ ] **Step 4: Commit**

```bash
git add engine/effects/raster.emp
git commit -m "feat(effects): raster program format — opcodes, sentinels, comptime constructors (P1)"
# plus a commit in the sigil repo for the registry line
```

---

## Task 2: Raster RAM Block

**Files:**
- Modify: `engine/ram.emp` (inside `pub vars upper_ram`, after the `Parallax_State`…`Parallax_State_End` block that ends at :269)
- Modify: `engine/effects/raster.emp` (span guard)

- [ ] **Step 1: Add the RAM block** (model: `Parallax_State`, ram.emp:241-269 — `mark`/`_End` pair; adding here ripples only `Engine_RAM_End` + game RAM)

```
    // ---- Raster_State — sparse HInt raster engine (effects P1, raster.emp) ----
    mark Raster_State,
    Raster_Program:      u32,                    // installed compiled program (ROM/RAM), 0 = none
    Raster_Cursor:       u32,                    // HInt walk cursor into active buffer entries
    Raster_Pending:      u32,                    // program staged by Raster_Install, consumed+cleared by Raster_VBlank (0 = none)
    Raster_Line:         u16,                    // line the cursor's next entry group starts at
    Raster_Buf_A:        [u8; RASTER_BUF_SIZE],  // working copy (active)
    Raster_Buf_B:        [u8; RASTER_BUF_SIZE],  // working copy (back — P2 patches write here)
    Raster_Active_Buf:   u32,                    // points at Buf_A or Buf_B
    mark Raster_State_End,
```

(If `RASTER_BUF_SIZE` can't be imported into ram.emp — check how ram.emp handles `MAX_PARALLAX_BANDS` at :241; if it mirrors constants locally with a drift comment, do the same: `128` + comment naming `raster.emp` as the authority, per the bg_anim.emp precedent.)

- [ ] **Step 2: Add the span guard in raster.emp** (model: parallax.emp:32)

```
ensure((extern("Raster_State_End") - extern("Raster_State")) == RASTER_STATE_SIZE,
       "Raster_State RAM block drifted from raster.emp's layout")
```
with `pub const RASTER_STATE_SIZE = 4+4+4+2 + 128+128 + 4 + 2` — count pad bytes if the compiler pads for alignment; set the const to whatever the first build reports and comment the breakdown. (Even-alignment is compiler-checked for .emp regions.)

- [ ] **Step 3: Build + commit**

```bash
DEBUG=1 ./build.sh
git add engine/ram.emp engine/effects/raster.emp
git commit -m "feat(effects): Raster_State RAM block + span guard"
```

---

## Task 3: HInt Dispatcher + Install/Clear + VInt Integration

**Files:**
- Modify: `engine/effects/raster.emp` (the runtime procs)
- Modify: `engine/vdp.emp` (add `pub const VDP_MODE4_OFF = $0C` next to :31-34)
- Modify: `engine/system/vblank.emp` (`VInt_Level` after :151, `VInt_Lag` mirror)
- Modify: `games/sonic4/map.toml`, `games/demo/map.toml` (order arrays)

- [ ] **Step 1: Write the four procs in raster.emp**

The code below is the reference shape — adjust only instruction-level details the survey's **Ruling** lines or build errors force (e.g. the exact `RASTER_DELTA` bias), never the structure. `RASTER_ARM_BIAS` below encodes the survey Q1 ruling: next-fire-at-M from line L → write `M - L - RASTER_ARM_BIAS`; start with bias `1` and let Task 4 calibrate.

```
pub const RASTER_ARM_BIAS = 1        // survey Q1 ruling; Task 4 verifies empirically

// Raster_Install — stage a compiled program. Takes effect at next VBlank (atomic).
// In: a0 = program (0 = clear). Callable from main loop only.
pub proc Raster_Install () clobbers(d0) {
        move.l  a0, Raster_Pending              // (Raster_Pending).w
        rts
}

// Raster_Clear — remove any program. Convenience wrapper.
pub proc Raster_Clear () clobbers(d0/a0) {
        suba.l  a0, a0
        jbsr    Raster_Install
        rts
}

// Raster_VBlank — called from VInt_Level AND VInt_Lag, inside the DMA/Z80 bracket,
// after Flush_VDP_Shadow. Consumes pending installs, re-asserts frame-top state
// (init regwords + pal_dirty_mask), resets the walk cursor, arms the first HInt.
pub proc Raster_VBlank () clobbers(d0-d2/a0-a2) {
        move.l  Raster_Pending, d0              // pending install?
        beq.s   .no_install
        clr.l   Raster_Pending
        move.l  d0, Raster_Program
        bne.s   .installed
        // pending == "clear": tear down. HBlank_Uninstall restores idle rte + IE1 off.
        jbsr    HBlank_Uninstall                // extern, engine/system/hblank.emp:74
        bra.s   .done
.installed:
        // copy program into Buf_A (P1: single buffer active; B is the P2 patch seam)
        movea.l d0, a1
        lea     Raster_Buf_A, a2                // (Raster_Buf_A).w
        move.l  a2, Raster_Active_Buf
        move.w  #(RASTER_BUF_SIZE/2)-1, d1
.copy:  move.w  (a1)+, (a2)+
        dbf     d1, .copy
.no_install:
        move.l  Raster_Program, d0
        beq.s   .done                           // no program: zero cost (one tst)
        movea.l Raster_Active_Buf, a1
        // header: pal_dirty_mask, init_count, init words
        move.w  (a1)+, d1
        or.b    d1, Palette_Dirty               // re-assert base palette lines each frame
        move.w  (a1)+, d1                       // init_count
        beq.s   .init_done
        subq.w  #1, d1
        lea     VDP_CTRL, a2
.init:  move.w  (a1)+, (a2)                     // $8xxx frame-top words (VBlank-safe)
        dbf     d1, .init
.init_done:
        move.l  a1, Raster_Cursor               // first entry
        move.w  (a1), d1                        // first entry's line
        move.w  d1, Raster_Line
        cmpi.w  #RASTER_LINE_END, d1
        beq.s   .done                           // empty program: never arm
        subq.w  #RASTER_ARM_BIAS, d1
        move.w  d1, d0
        // (re)install handler + counter + IE1 every frame — idempotent, and it
        // heals the counter after END disarmed it ($8AFF) last frame.
        lea     Raster_HInt, a0
        jbsr    HBlank_Install                  // extern, hblank.emp:54 (a0=handler, d0.b=counter)
.done:
        rts
}

// Raster_HInt — the IRQ4 handler (reached via HBlank_Vector_Slot jmp).
// Executes every entry whose line == Raster_Line, then re-arms the counter with
// the delta to the next entry's line. Raw interrupt context: touches only what
// it saves. VDP-access invariant: full command longword in ONE move.l (hblank.emp:37-42).
pub proc Raster_HInt () {
        movem.l d0-d1/a1-a2, -(sp)
        movea.l Raster_Cursor, a1
        lea     VDP_CTRL, a2
.next:  move.w  (a1)+, d0                       // entry line
        cmp.w   Raster_Line, d0
        bne.s   .rearm                          // first entry beyond current line
        move.w  (a1)+, d0                       // op
        jmp     .optable(pc, d0.w)
.optable:
        bra.s   .op_set_reg                     // OP_SET_REG = 0
        bra.s   .op_cram                        // OP_CRAM    = 4
        // OP_END = 8 falls through to .op_end below the table
.op_end:
        move.w  #$8AFF, (a2)                    // no more fires this frame
        clr.l   Raster_Cursor                   // parked; VBlank re-arms  [see note]
        bra.s   .out
.op_set_reg:
        move.w  (a1)+, (a2)                     // pre-composed $8xxx word
        bra.s   .next
.op_cram:
        move.l  (a1)+, (a2)                     // vdp_comm CRAM write command (one move.l)
        move.w  (a1)+, d1                       // count-1
.cram:  move.w  (a1)+, VDP_DATA
        dbf     d1, .cram
        bra.s   .next
.rearm:
        subq.l  #2, a1                          // un-consume the peeked line word
        move.l  a1, Raster_Cursor
        move.w  Raster_Line, d1                 // d1 = line we just serviced
        move.w  d0, Raster_Line                 // next event line (current at next fire)
        sub.w   d1, d0                          // d0 = delta in lines
        subq.w  #RASTER_ARM_BIAS, d0
        ori.w   #$8A00, d0                      // counter reprogram word
        move.w  d0, (a2)
.out:
        movem.l (sp)+, d0-d1/a1-a2
        rte
}
```

**Two deliberate notes for the implementer:**
1. `.op_end` clears `Raster_Cursor` but `Raster_VBlank` decides re-arm from `Raster_Program` (not cursor) and resets the cursor unconditionally in `.init_done` — the `clr.l` is redundant defense; keep it (cheap) with a comment saying so.
2. `proc` contract syntax for an `rte` handler: check how existing IRQ code declares clobbers (`engine/irq.emp`, `engine/system/vblank.emp` `VBlank_Handler`) — an rte-terminated proc that saves/restores everything it touches likely wants an empty clobbers or an `@irq`-style marker; copy whatever `VBlank_Handler` does.

- [ ] **Step 2: VInt integration** — in `engine/system/vblank.emp`:
  - `VInt_Level`: insert `jbsr Raster_VBlank` immediately after `jbsr Flush_VDP_Shadow` (:151) and BEFORE `Enqueue_Dirty_Buffers` (:153) — the pal_dirty_mask OR must land before the palette enqueue reads `Palette_Dirty`.
  - `VInt_Lag` (:255-325): insert the same call after its Flush, before its Enqueue. A lag frame that skips re-arm leaves a stale cursor and a dead counter — this mirror is mandatory.

- [ ] **Step 3: map.toml order entries** — head-label is `Raster_Install` (first byte-emitting symbol). Add `"Raster_Install",` adjacent to `"Parallax_Init"` in BOTH `games/sonic4/map.toml` and `games/demo/map.toml` (VInt references the module, all games link it; demo installs nothing → HInt stays dormant there).

- [ ] **Step 4: Main-thread VDP-access audit** — the IRQ4 hazard (hblank.emp:37-42): while a program is armed, IRQ4 can split a main-thread VDP control-port sequence. Audit: `grep -rn "VDP_CTRL\|VDP_DATA" engine/ games/ --include=*.emp | grep -v vblank.emp | grep -v boot` — classify each hit: VBlank-context (safe), boot (safe), or main-loop (needs `ints_off` bracket, engine/irq.emp:48-56, or a comment why it's unreachable while raster is armed). Fix or annotate every main-loop hit. The known OJZ `$8B` direct-write bug (ENGINE_ARCHITECTURE §"Known exception") gets its `ints_off` bracket here.

- [ ] **Step 5: Build + commit**

```bash
DEBUG=1 ./build.sh    # green; also plain ./build.sh once (both canonical shapes assemble)
git add engine/effects/raster.emp engine/vdp.emp engine/system/vblank.emp games/sonic4/map.toml games/demo/map.toml
git commit -m "feat(effects): sparse HInt raster dispatcher — delta dispatch, VBlank re-arm, lag mirror"
```

---

## Task 4: Oracle Calibration Checkpoint (CONTROLLER-ONLY)

No section wiring yet — poke a minimal program by hand and calibrate the counter bias before building on it.

- [ ] **Step 1:** Build `DEBUG=1`, kill any stale `oracle_gui` (`pgrep -a oracle`), launch fresh, load `s4.debug.bin`, CRC-check ROM vs `.lst` (the auto-commit daemon can plain-rebuild mid-session — byte-verify, memory: project_sfx_fidelity_design).
- [ ] **Step 2:** Enter the OJZ scroll test state. Write a 3-word test program into free RAM via `emulator_write_memory` (backdrop-blue CRAM entry at line 120: header `0000 0000`, entry `0078 0004`, `vdp_comm(0,Cram,Write)` longword, `0000`, `0E00`, then `7FFF 0008`), then poke `Raster_Pending` with its address.
- [ ] **Step 3:** `emulator_run_to_scanline` line 118 vs 122 over several frames + screenshot: the backdrop split must sit at line 120 exactly and stay put frame-to-frame. Off-by-N → adjust `RASTER_ARM_BIAS`, rebuild, repeat until exact. Record the final bias + evidence (scanline reads, screenshot names) in the survey doc's Format-deltas section.
- [ ] **Step 4:** Also verify: `Raster_Pending` clear-path (`Raster_Clear` poke → split gone next frame, IE1 off via `emulator_registers`), and a lag-frame doesn't kill the effect (hold a heavy scroll; split persists).
- [ ] **Step 5:** Commit any bias fix: `git commit -am "fix(effects): RASTER_ARM_BIAS calibrated on oracle (evidence in survey doc)"`

---

## Task 5: `sec_pal` Consumer (Per-Section Palettes)

**Files:**
- Create: `engine/effects/palette.emp` (P1-minimal — grows into the full palette engine in P2)
- Modify: `engine/level/parallax.emp` (`.crossed` block, :171-185)
- Modify: sigil registry + both map.toml order arrays (head-label `Palette_LoadSection`)

- [ ] **Step 1: Write the module**

```
// engine/effects/palette.emp — per-section palette load (effects P1).
// P1 = instant snap on section crossing (sec_pal). Cross-fade/cycling/variants
// arrive in P2 and this proc becomes the composition pipeline's base-layer step.
module engine.effects.palette in palette

// Palette_LoadSection — consume Sec.sec_pal.
// In: a0 = Sec*. NULL sec_pal = keep current (the struct's 0-convention).
pub proc Palette_LoadSection () clobbers(d0-d1/a1-a2) {
        move.l  Sec.sec_pal(a0), d0
        beq.s   .keep
        movea.l d0, a1
        lea     Palette_Buffer, a2              // (Palette_Buffer).w
        moveq   #(128/4)-1, d1
.copy:  move.l  (a1)+, (a2)+
        dbf     d1, .copy
        move.b  #$0F, Palette_Dirty             // all 4 lines (test-writer idiom)
.keep:  rts
}
```

- [ ] **Step 2: Hook the boundary crossing** — in `parallax.emp` `.crossed` (after the `Section_GetSecPtrXY` Z-guard at :171, while `a0` = `Sec*`, BEFORE the `movea.l Sec.sec_parallax_config(a0), a0` at :179 destroys it):

```
        movem.l a0, -(sp)
        jbsr    Palette_LoadSection             // a0 = Sec* (sec_pal; NULL = keep)
        jbsr    Raster_InstallSection           // Task 6 adds this; comment out until then
        movem.l (sp)+, a0
```

- [ ] **Step 3: Initial-load seed** — find where `Parallax_Prev_Sec_X/Y` are initialized (`Parallax_Init`, parallax.emp:100 region). Verify a fresh level triggers `.crossed` on frame 1 (prev-sec seeded to an impossible value). If it doesn't, seed `Parallax_Prev_Sec_X = $FF` in `Parallax_Init` so the first `Parallax_CheckBoundary` fires the full descriptor consume — one mechanism, no special-case level-init path.

- [ ] **Step 4: Register + build + commit**

Sigil registry line for `engine/effects/palette.emp`; rebuild sigil binaries; `"Palette_LoadSection",` into both map orders next to `"Raster_Install"`.

```bash
DEBUG=1 ./build.sh
git add engine/effects/palette.emp engine/level/parallax.emp games/sonic4/map.toml games/demo/map.toml
git commit -m "feat(effects): sec_pal per-section palette consumer, hooked at boundary crossing"
```

---

## Task 6: `sec_raster_table` Consumer

**Files:**
- Modify: `engine/effects/raster.emp`
- Modify: `engine/level/parallax.emp` (uncomment the Task 5 call)

- [ ] **Step 1: Add the section consumer to raster.emp**

```
// Raster_InstallSection — consume Sec.sec_raster_table on boundary crossing.
// In: a0 = Sec*. Semantics: NULL = keep current program (0-convention), matching
// sec_parallax_config. Sections that must KILL a neighbour's raster effect point
// at Raster_Program_None (an empty program: no init, END only) rather than NULL.
// Raster programs SNAP — no lerp (design §4; cross-fade smooths perception in P2).
pub proc Raster_InstallSection () clobbers(d0/a1) {
        move.l  Sec.sec_raster_table(a0), d0
        beq.s   .keep
        cmp.l   Raster_Program, d0              // already installed? (re-cross churn)
        beq.s   .keep
        movea.l a0, a1                          // preserve Sec* for the caller
        movea.l d0, a0
        jbsr    Raster_Install
        movea.l a1, a0
.keep:  rts
}

// The canonical empty program — "explicitly no raster effects here".
pub data Raster_Program_None: [u16; 4] = [0, 0, RASTER_LINE_END, OP_END]
```

(Adjust the `pub data` literal syntax to match how `configs.emp` materializes records; the four words are: pal_dirty_mask=0, init_count=0, END entry.)

- [ ] **Step 2:** Uncomment `jbsr Raster_InstallSection` in the parallax.emp hook (Task 5 Step 2).

- [ ] **Step 3: Build + commit**

```bash
DEBUG=1 ./build.sh
git add engine/effects/raster.emp engine/level/parallax.emp
git commit -m "feat(effects): sec_raster_table consumer — snap install on section crossing"
```

---

## Task 7: Test Content — OJZ Gate Section

**Files:**
- Create: `games/sonic4/data/effects/test_effects.emp` (module `games.sonic4.effects_test in effects_test`)
- Modify: `games/sonic4/data/levels/ojz/act1/act_descriptor.emp` (:125-151 — `ojz_sec` constructor + section array)
- Modify: sigil registry + `games/sonic4/map.toml` order (head-label `OJZ_TestRaster`; sonic4 only — demo doesn't reference it)

- [ ] **Step 1: Author the test program + test palette**

`OJZ_TestRaster` — S/H on below line 120 + backdrop turns blue below line 120 (two same-line entries, exercising the multi-entry walk):

```
// 14 words, in format order. $C000,$0000 is vdp_comm(0, VdpTarget.Cram, VdpOp.Write)
// split into its two command words — add next to it:
//   ensure(vdp_comm(0, VdpTarget.Cram, VdpOp.Write) == $C0000000, "CRAM cmd drifted")
pub data OJZ_TestRaster: [u16; 14] = [
    %0001,                    // pal_dirty_mask: re-assert palette line 0 each frame
                              // (undoes the mid-frame backdrop write at frame top)
    1, $8C81,                 // init: S/H OFF at frame top (H40 base value, boot_data.emp:140)
    120, OP_SET_REG, $8C89,   // line 120: S/H ON  ($81 | bit3)
    120, OP_CRAM,             // line 120: backdrop → blue
    $C000, $0000,             //   CRAM write command @ color 0 (ensure-pinned above)
    0, $0E00,                 //   count-1 = 0, one color: full blue
    RASTER_LINE_END, OP_END,
]
```

(If the compiler rejects mixed-provenance words in a `[u16]` literal, emit the module as a `data` block with explicit `dc.w` lines instead — check how sound descriptor tables mix widths; the FORMAT is the contract, the emission idiom is free.)

`OJZ_TestPal` — a 128-byte tinted copy of the OJZ palette for a *different* section, proving `sec_pal` independently: locate the palette the OJZ scroll test state loads (writer at `games/sonic4/test/ojz_scroll_test.emp:112-124` — trace its source symbol), then generate a red-shifted copy: for every color word (Genesis format `0000BBB0GGG0RRR0`), `out = (w & $000E) | ((w >> 1) & $0660)` — keeps R, halves G and B. Apply at comptime if the source is a comptime array, else via a python snippet (input bin → output literal block); either way, write the transform expression in the file's header comment.

- [ ] **Step 2: Wire two sections in `act_descriptor.emp`** — the `ojz_sec` comptime constructor (:125-149) currently hardcodes `sec_parallax_config: default, sec_raster_table: default`. Add two keyword params with `default` defaults (match the constructor's existing param style), then:
  - Section 2 (one screen right of spawn): `raster: OJZ_TestRaster`
  - Section 3: `pal: OJZ_TestPal`
  Import the symbols per the file's existing `use` list for `ParallaxConfig_OJZ_Default`.

- [ ] **Step 3: Build both shapes + commit**

```bash
DEBUG=1 ./build.sh && ./build.sh
git add games/sonic4/data/effects/test_effects.emp games/sonic4/data/levels/ojz/act1/act_descriptor.emp games/sonic4/map.toml
git commit -m "feat(effects): OJZ gate content — raster test program (S/H + backdrop split) + test sec_pal"
```

---

## Task 8: Gate Verification + Docs + Golden Ritual (CONTROLLER-ONLY)

- [ ] **Step 1: The gate, on oracle, MID-SCROLL** (memory: feedback_verify_during_motion — at-rest frames hide raster/scroll bugs):
  1. Fresh oracle, `s4.debug.bin`, CRC-verified.
  2. Hold right through sections 1→2→3 while capturing screenshots DURING motion (use the input-replay/press pattern, not press-frame timing — memory: reference_oracle_screenshot_not_deterministic).
  3. **Assert:** section 2 shows the line-120 split (S/H dimming + blue backdrop below, stable across ≥3 moving frames); crossing into section 3 snaps the palette (CRAM read via `emulator_read_cram` differs from section 1's); crossing BACK restores (sec_pal on re-entry of a NULL-pal section = keep-current — confirm the visual matches that semantic and note it in the survey doc).
  4. Lag-frame robustness: force sustained max diagonal scroll in section 2; the split must not drift or die (VInt_Lag mirror proof).
- [ ] **Step 2: Replay net** — run BOTH replay fixtures per the runbook (`docs/superpowers/notes/2026-08-09-replay-net-rerecord-ab.md:15-25`); all checkpoint hashes must pass. Report aggregate totals, not a tail.
- [ ] **Step 3: Docs** — ENGINE_ARCHITECTURE.md: update the §7 banner (raster command table sparse tier + per-section palette load = SHIPPED, rest still planned), document the program binary format in §7.2, note the `VDP_MODE4_OFF` const; DEFERRED_WORK.md: point the water-level entry (:231) at the now-real host. Commit.
- [ ] **Step 4: Sigil golden ritual (paired repo)** — bytes changed, so: sigil branch → `repin` (updates `repin.toml`/`pins.rs`; the fault-handler island + `EndOfRom` moved) → full suite → `refreeze --freeze <NAME> --ab <REF>` with prose emulator evidence in the commit (NOT just `--check` — memory: reference_refreeze_check_is_not_the_goldens) → confirm the golden ROM tests themselves are green.
- [ ] **Step 5: Merge** — use superpowers:finishing-a-development-branch. Never leave master broken; both canonical shapes must build green at the merge commit.

---

## Explicitly OUT of Phase 1 (do not build, even if adjacent)
- `RUN_GRADIENT` / `RUN_VSRAM` dense handlers, `PAL_REGION` variant swaps → Phase 2
- Patch slots / per-frame back-buffer rebuild (the double-buffer flip stays dormant; Buf_B exists as the seam) → Phase 2
- `raster_dsl.emp` / `palette_dsl.emp` general constructors, presets, starter pack → Phase 3
- Cross-fade on section crossing (P1 snaps), cycling, computed variants → Phase 2
- Aurora anything → Phases 4-5
