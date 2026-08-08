# Art Streaming Phase 2 Implementation Plan — v2

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **v2 provenance (2026-08-08).** This file folds three sources into one cold-executable plan: the banked 12-task structure (`2026-07-02-art-streaming-phase2.md`, now SUPERSEDED), the re-anchor addendum (`2026-08-06-art-streaming-phase2-reanchor-addendum.md`, now SUPERSEDED), and the mechanism survey (`2026-08-06-bookmark-implementation-sketch.md`). It also lands the four §9.7 rulings D1–D4 recorded 2026-08-08 (`2026-08-06-97-decision-memo.md`, RULED block). A cold session needs ONLY this file plus the spec `docs/superpowers/specs/2026-07-02-art-streaming-phase2-design.md`. Anchors were re-verified against master `824b69f` (see per-task "current anchor" call-outs); where a line is fluid, the instruction is "re-read at execution."

**Goal:** Turn the fully-resident act art pool into a VRAM residency cache streaming small ZX0/raw pages in main-loop idle time via a supervisor-bookmark resumable decoder — level art capped by ROM, not VRAM.

**Architecture:** Three phases on one branch. P2a (Tasks 2-4): stack-flat resumable ZX0 decoder + VBlank bookmark preemption + page-in dispatcher with cancel/flush, proven on the existing 256-tile pages. P2b (Tasks 5-7): format cutover (64-tile ZX0/raw pages, manifest v2, logical indices + local→global tables) then the residency cache (page frames, refcount-pin + LRU, patch-at-cache-entry, demand stall, eviction, trailing-lag prefetch gate). P2c (Tasks 8-12): Vectorman dual-cap DMA, B&R per-act art budget word, camera-gate degradation, stress + acceptance, ROM budget gate, docs + merge. Spec: `docs/superpowers/specs/2026-07-02-art-streaming-phase2-design.md` (APPROVED).

**§9.7 rulings folded in (2026-08-08):**
- **D1 = A — bookmark-first.** Keep this plan's task order. The page-size sweep is NOT a task of its own; it is a P2c tuning knob mentioned in Task 11 (the stress fixture makes it a 10-minute experiment).
- **D2 = C — no unified arbiter.** NO task builds an arbiter or a shared cost ledger. Each tier keeps its own governor. The §7.2 adoption seam is *documented only*: a named comment in the `Tile_Cache_Fill` budget area (Task 6) + ARCH prose (Task 12). It is never built.
- **D3 — trailing-lag gate on speculative page-in starts only.** Task 7 implements the shipped H4 trailing-lag pattern *verbatim*: an OWN `Frame_Counter`-delta latch inside `page_in` (NOT a reuse of `Cache_Pfx_Lag_Flag`, which is fill-owned), skip-if-last-frame-lagged, bounded to ≤1 consecutive skip. Demand decodes and resumes are NEVER gated.
- **D4 = A — ARCH §9.7 rewrite.** Task 12 lands the already-ratified draft `docs/superpowers/2026-08-06-arch-97-rewrite-proposal.md` verbatim (title "§9.7 Idle-Time Deferred Work — Pre-Chunked Pages + Supervisor Bookmark") plus its cross-reference sweep table.

**Tech Stack:** 68000 assembly in the `.emp` tree (Sigil — `sigil build` IS the build; the `.asm` twins are deleted), Python toolchain (`tools/ojz_strip_gen.py` — **daemon-watched**), oracle emulator MCP (controller-only), salvador ZX0 packer.

---

## Standing rules for every task

**The `.emp` world (this is not the pre-Sigil tree):**
- All engine sources are `.emp`, not `.asm`. Every code block below written in AS syntax must be translated to `.emp`: module header, `proc` with `clobbers/preserves/out/requires/grants`, `if DEBUG == 1 {}` instead of `ifdef __DEBUG__`, bare-symbol operands width-select automatically (two-symbolic mem-to-mem needs both widths spelled — see vblank.emp:97). There is NO `games/sonic4/main.asm` — it is deleted. ROM placement is `games/sonic4/map.toml` (`order` list + anchors/holes/budgets, `order` at map.toml:43) plus the sigil-harness native driver. **Every new byte-emitting section (each `proc`/`data` head-label in `zx0_resume.emp`, `page_in.emp`, `page_cache.emp`) must be added to map.toml's `order` list** in its correct union position; the registry/pins/golden side is sigil-owned — coordinate with the sigil session.
- **RAM:** `engine/ram.emp` — `region lower_ram @ $FFFF0000 .. $FFFF8000` (`.l`-addressed buffers) / `region upper_ram @ $FFFF8000 .. SYSTEM_STACK, w_addressable` (hot `.w` data) with typed `vars` + `pad()`. Alignment/overlap are compiler checks now (the old AS even-alignment caveat is obsolete). PageIn/PageCache state is engine-owned → `engine/ram.emp`. Game RAM chains from `Engine_RAM_End` (mark at ram.emp:580). **DEBUG-only counters go inside the existing `if DEBUG == 1 @shape_divergent {}` block at ram.emp:260** (beside `DMA_Bytes_ThisFrame` / `Lag_Frame_Count`) — adding there ripples only `Engine_RAM_End` and the game RAM tail, no existing engine address (commentary ram.emp:485-578).
- **Structs:** `engine/structs.emp`. No manual `_len` constants — `sizeof` is compiler truth; the typed literal + struct harvest catch drift.

**The byte-changing-parcel ritual (rides EVERY aeon byte-emitting change):**
- `SIGIL_BLOB_LEN_DRIFT=warn`, rebuild BOTH sigil binaries, repin → refreeze `--ab`. `pins.rs` is a gate, not an input. Coordinate the registry/golden side with the sigil session. Do NOT invent waiver hacks.

**Sigil gating (hard dependency — a separate sigil session in `/home/volence/sonic_hacks/sigil` is implementing the asks; do NOT plan that work here):**
- **Task 2 is gated on sigil asks 1–2.** Ask 1 = `@resumable` (stackless) proc attribute — build-fatal on any sp-touching instruction inside the proc, declares the register state set; this turns the decoder's "NO stack, ALL state in registers" comment into a checked property. Ask 2 = exported extent symbols — a generated linkable end-of-range symbol (e.g. `ZX0R_Decompress__end`) so the VBlank range check compiles from symbols, not a hand-maintained sentinel label.
- **Task 3 is gated on sigil asks 3–5.** Ask 3 = a sanctioned stacked-frame accessor (`irq_frame.pc`) valid inside a `grants(vblank)` proc after a declared full-save movem, plus the contract nuance that a handler which rewrites the return PC still satisfies `preserves(d0-a6)` but no longer returns-to-interrupted-instruction. Ask 4 = manufactured-frame resume license (a `@continuation` proc form, entered by rte/jmp only, or `bank_frame`/`resume_frame` intrinsics). Ask 5 = typed computed `jmp` — `jmp (a3) as Type` (the `jsr (a0) as Type` spelling exists at game_loop.emp:42; the `jmp` spelling has no precedent).
- **Fallback if an ask slips:** the affected STEP pauses for controller coordination. Do NOT ship a waiver hack to "unblock." Report the slip and hold.

**Build shapes:**
- Plain `./build.sh` → `s4.bin` with **sound ON** (default since the engine/game split). `DEBUG=1 ./build.sh` → **suffixed** `s4.debug.bin` / `s4.debug.lst` (the two shapes never collide; DEBUG suffix logic build.sh:35-37). DEBUG carries asserts/self-tests; a plain build proves nothing about them. Oracle symbol cross-checks use `s4.debug.lst` for debug ROMs. Never plain-`./build.sh` in a shared hot tree mid-session without byte-verifying the loaded ROM afterward (the daemon plain-rebuilds).

**Verification & emulator:**
- **Every oracle/emulator step is CONTROLLER-ONLY (⚠ controller).** The emulator MCP from a subagent deadlocks the arbiter; the foreground controller session does ALL oracle work. Subagents build, edit, and reason — they never touch oracle.
- Verification is oracle-observed behavior (screenshots during MOTION, `Lag_Frame_Count`, VRAM reads), never build-success alone. Oracle gotchas current 2026-08-05: absolute-path `reload_rom` + crc-verify (a relative path silently loads no cart), `press` not `hold`, screenshots via the input-replay net, `pgrep -a`. Oracle symbols go stale after `reload_rom` — cross-check addresses against fresh `s4.debug.lst`.

**Daemon-watched files (Tasks 5 and 11):**
- `tools/ojz_strip_gen.py` and `games/sonic4/data/editor/ojz/` are auto-committed by the daemon ~60s after edit. **⚠ ASK THE USER before starting Task 5 and Task 11** (they edit these); never edit autonomously; never `--amend` near them.

**Git:**
- `git add` exact paths only (never `-A`/globs). Commit per green task. Branch `feat/art-streaming-p2` off a clean master; merge to master ONLY at Task 12 (merge commit, repo habit). **Verify `git branch --show-current` before EVERY commit** (parallel sessions share the tree).

**Two new standing rules the mechanism survey forces (absorbed here):**
- **Sigil coordination is a first-class dependency, not friction** (see the gating block above): map.toml `order` is part of every "Files:" list; the parcel ritual rides every byte change.
- **Contract surgery is work, not incidental fallout.** The `VSync_Wait` license widening and `Level_LoadArt` re-fold (Task 3) are EXPLICIT steps with their own verification.

**Baseline numbers rule:**
- Idle baseline = the **2026-08-05** table: **74.3% rest / 67.8% max-H / 33.2% diagonal window**. Do NOT use the 2026-06-22 figures. Lower-RAM slack ("9,150 B" in the spec, "6,078 B post-H5" later — both stale) **must be re-measured from the fresh `s4.debug.lst` at Task 1.**

---

### Task 1: Branch + baseline

**Files:** none created (scratchpad numbers only).

- [ ] **Step 1: Research.** Read the spec end-to-end. Read the P2a surfaces fresh (current anchors on master `824b69f`):
  - `engine/level/load_art.emp` — `Art_Decompress` :50, `Level_LoadArt` :108-165, `QueueDMA_Critical` call :133, `VSync_Wait` call :135, out-of-line `.drop_page` retry idiom :157-165.
  - `engine/system/vblank.emp` — `VBlank_Handler` :40-58 (movem :41, `VBlank_Ready` test :42, `VInt_Lag` dispatch :48), `VInt_Level` :71 (`DMA_Budget_Remaining` reset :97), `VInt_Lag` :192, `VSync_Wait` :274-302 (`with ints_off` bracket :290-293, spin :295-302).
  - `engine/system/game_loop.emp` — `GameLoop` :28-43 (`VSync_Wait` :29, `Input_Tick` replay seam :31, `Game.debug_tick` :40, computed `jsr (a0) as GameState` :42).
  - `engine/compression/zx0.emp` — `ZX0_Decompress` :58, elias `jbsr` sites :65/:75/:90/:100, `movem` prologue/epilogue :59/:120.
  - `engine/system/constants.emp` — `ART_POOL_PAGE_TILES` :227, `ART_HDR_*`/`ART_VER_*` :228-231, `ART_STAGING_BUFFER_SIZE` :382, `POOL_TILE_CEILING` :419.
  - `engine/ram.emp` — regions :69-70, `Art_Staging_Buffer` alias :102, `Tile_Cache_Nametable` :79, DEBUG `@shape_divergent` block :260, `Engine_RAM_End` :580.
- [ ] **Step 2: Branch.** `git checkout -b feat/art-streaming-p2` from a clean master (verify `git branch --show-current` = master first; you branch FROM it).
- [ ] **Step 3: Baseline. ⚠ controller.** Build `DEBUG=1 ./build.sh`; load `s4.debug.bin` in oracle (absolute path + crc-verify); free-fly a full OJZ circuit at max scroll; record to scratchpad: `Lag_Frame_Count` over a 600-frame max-horizontal run, a mid-scroll screenshot, and the profiler idle % (`emulator_get_profiler`). These are the no-regression references for Tasks 4/7/11. **Also record: the lower-RAM slack measured from the fresh `s4.debug.lst`** (region tail vs `$FFFF8000`) — this replaces the stale "9,150 B / 6,078 B" figures and is the budget for all new engine RAM below.

### Task 2: P2a — Resumable stack-flat ZX0 decoder + equivalence self-test

**⚠ Gated on sigil asks 1–2** (`@resumable` attribute + exported extent symbols). If either slips, this task pauses for controller coordination — no waiver hacks.

**Files:**
- Create: `engine/compression/zx0_resume.emp` (+ its `ZX0R_Decompress` head-label into `games/sonic4/map.toml` `order`, near the existing `ZX0_Decompress` entry).
- Modify: `engine/debug/compression_selftest.emp` (the DEBUG-boot golden self-test; `CompressionSelfTest` :43 — placed only in debug shapes per map.toml). ⚠ read its tail comment :117-126 first: it documents a measured island-span/pad interaction — appending code to this module can move the pad.
- Modify: `engine/ram.emp` (DEBUG counters, in the `@shape_divergent` block :260).
- Modify: `games/sonic4/map.toml` (`order` entry).
- Parcel ritual on all byte-emitting changes.

- [ ] **Step 1: Research.** Re-read `zx0.emp` instruction-by-instruction; the shipped blocking decoder violates the resumable contract in exactly two ways (mechanism survey §1, confirmed live): (a) three `jbsr` sites into the internal `.get_elias`/`.elias_loop`/`.elias_bt` subroutine (zx0.emp:65/:75/:90/:100) plus the `movem.l a2/d2,-(sp)` prologue/epilogue (:59/:120); (b) `rts` exit. Read the S3K resumable-decoder precedent in spec §3. Read how `CompressionSelfTest` runs at DEBUG boot and mirror its structure. Read `CODING_CONVENTIONS.md`.
- [ ] **Step 2: Write the decoder** as a `.emp` `@resumable` proc. Register-resident state (survey §1, verified against the algorithm): a0 (src), a1 (dst), d0 (elias accumulator), d1 (bit queue), d2 (rep-offset), a2 (backref cursor), plus CCR carry/X live *between* instructions (`add.b d1,d1` → `addx`); a3 (continuation) is never touched by the body. The contract every clause of the VBlank bookmark depends on: NO stack access between `ZX0R_Start` and `ZX0R_End` (no bsr/jsr/jbsr/push, no `with` bracket that lowers to stack); ALL state in d0-d2/a0-a2 + CCR at every instruction; NO VDP/Z80/shared-RAM access (writes go to the staging buffer only); continuation in a3, jumped to on completion (NOT a return address). The reference control flow (translate to `.emp`; the elias inlining is a *restructure* of the original's `.get_elias`/`.elias_loop`/`.elias_bt`, not a transcription — the `.len_elias` tail is the `.elias_bt` case: one data-bit read THEN the loop):

```asm
; ZX0R — resumable stack-flat ZX0 decompressor (art-streaming Phase 2).
; In:  a0 = compressed stream (past the 4-byte wrapper)
;      a1 = destination (staging buffer)
;      a3 = continuation — jumped to on completion (NOT a return address)
; Out: a0/a1 past ends; d0-d2/a2 trashed; jmp (a3)
ZX0R_Start:
ZX0R_Decompress:
        moveq   #-128, d1               ; empty bit queue + roll-in bit
        moveq   #-1, d2                 ; rep-offset = -1
.literals:
        moveq   #1, d0                  ; --- inlined elias: literal count ---
.lit_elias:
        add.b   d1, d1
        bne.s   .lit_got
        move.b  (a0)+, d1
        addx.b  d1, d1
.lit_got:
        bcs.s   .lit_done
        add.b   d1, d1
        addx.l  d0, d0
        bra.s   .lit_elias
.lit_done:
        subq.l  #1, d0
.copy_lits:
        move.b  (a0)+, (a1)+
        dbf     d0, .copy_lits
        add.b   d1, d1                  ; match or rep-match?
        bcs.s   .get_offset
.rep_match:
        moveq   #1, d0                  ; --- inlined elias: rep-match length ---
.rep_elias:
        add.b   d1, d1
        bne.s   .rep_got
        move.b  (a0)+, d1
        addx.b  d1, d1
.rep_got:
        bcs.s   .do_copy
        add.b   d1, d1
        addx.l  d0, d0
        bra.s   .rep_elias
.do_copy:
        subq.l  #1, d0
.do_copy_offs:
        movea.l a1, a2
        adda.l  d2, a2
.copy_match:
        move.b  (a2)+, (a1)+
        dbf     d0, .copy_match
        add.b   d1, d1                  ; literal or match?
        bcc.s   .literals
.get_offset:
        moveq   #-2, d0                 ; --- inlined elias: offset high (pre-seeded) ---
.off_elias:
        add.b   d1, d1
        bne.s   .off_got
        move.b  (a0)+, d1
        addx.b  d1, d1
.off_got:
        bcs.s   .off_done
        add.b   d1, d1
        addx.l  d0, d0
        bra.s   .off_elias
.off_done:
        addq.b  #1, d0
        beq.s   .done                   ; EOD
        move.w  d0, d2
        lsl.w   #8, d2
        moveq   #1, d0
        move.b  (a0)+, d2
        asr.l   #1, d2
        bcs.s   .do_copy_offs
.len_elias:                             ; --- inlined elias tail: rest of match length ---
        add.b   d1, d1
        addx.l  d0, d0
.len_loop:
        add.b   d1, d1
        bne.s   .len_got
        move.b  (a0)+, d1
        addx.b  d1, d1
.len_got:
        bcc.s   .len_elias
        bra.s   .do_copy_offs
.done:
        jmp     (a3)                    ; continuation — never rts
ZX0R_End:
```

  Per ask 2, the range check in Task 3 should compile against the exported `ZX0R_Decompress__end` symbol rather than a hand-maintained `ZX0R_End` label — confirm the sigil-generated extent symbol exists before Task 3 depends on it.
- [ ] **Step 3: DEBUG instrumentation (survey §5).** Add to the `@shape_divergent` block: `Dbg_PageIn_Preempts` (word), `Dbg_PageIn_Flushes` (word), `Dbg_PageIn_Resumes` (word). This task only defines them; Task 3 increments `Preempts`, Task 4 the others.
- [ ] **Step 4: Equivalence self-test (DEBUG boot).** Alongside `CompressionSelfTest`: for each act pool page (walk the Act descriptor's `act_art_pool_table` / `act_art_pool_pages`, structs.emp:39-40; pages `OJZ_Act_Pool_Page0…`, manifest module `ojz_act_pool_manifest.emp`), decode with `ZX0_Decompress` into buffer A and `ZX0R_Decompress` into buffer B (reuse `Art_Staging_Buffer` + the tile-cache RAM the way the init loader does — this runs before the cache goes live), `raise_error` on any byte or length mismatch. This is blocking use (interrupts off at self-test time) — preemption is Task 3's test.
- [ ] **Step 5: Build + boot. ⚠ controller.** `DEBUG=1 ./build.sh` green (parcel ritual done); oracle boot reaches gameplay (self-test passed = no error screen); OJZ renders as baseline.
- [ ] **Step 6: Commit.** Verify branch = `feat/art-streaming-p2`. `feat(compression): resumable stack-flat ZX0 decoder + boot equivalence self-test (P2a)`.

### Task 3: P2a — VBlank bookmark: preempt, bank, resume

**⚠ Gated on sigil asks 3–5** (irq_frame accessor, manufactured-resume/continuation form, typed computed `jmp`). If any slips, the affected step pauses for controller coordination — no waiver hacks.

**Files:**
- Create: `engine/level/page_in.emp` (dispatcher skeleton: suspend/resume + a single-request path this task) + its head-labels (`PageIn_Process`, `PageIn_BankRegs`) into `games/sonic4/map.toml` `order`.
- Modify: `engine/system/vblank.emp` — `VBlank_Handler` :40-58 (hook after movem :41), `VSync_Wait` :274-302 (slice call after the `with ints_off` bracket :293).
- Modify: `engine/ram.emp` (PageIn state block, upper_ram), `engine/system/constants.emp` (offsets if not covered by the `irq_frame` accessor).
- Modify: `engine/level/load_art.emp` (`Level_LoadArt` :108 contract re-verify — Step 6).
- Parcel ritual on all byte-emitting changes.

- [ ] **Step 1: Research.** Re-read `VBlank_Handler` — entry is exactly `movem.l d0-a6,-(sp)` (vblank.emp:41), so the stacked exception frame sits at SR word `60(sp)`, return PC `62(sp)` (`VBH_STACKED_PC = 15*4+2`). **Prefer the Sigil `irq_frame.pc` accessor (ask 3) over the hand constant** so the offset can't silently rot if the handler's save set changes. Confirm the `VBlank_Ready` set (vblank.emp:42/:55) and the `VSync_Wait` `with ints_off { flag-clear; Ready:=1 }` pair (:290-293). Read spec §3's nested-interrupt caveat. **HInt is resolved:** `engine/system/hblank.emp` is RAM-slot dispatch, contract-bound interrupt-transparent + rte-terminated — nested-HInt is safe by contract; note it and move on (survey §2).
- [ ] **Step 2: RAM + constants.** Bookmark record (upper_ram, engine-owned): 7 longs (d0-d2/a0-a3) + PC long + SR word = 34 bytes, plus two byte flags:

```asm
; engine/ram.emp (upper_ram; typed vars — compiler checks alignment)
PageIn_Saved_Regs:      ds.l 7          ; d0-d2/a0-a3 banked at preemption
PageIn_Saved_PC:        ds.l 1
PageIn_Saved_SR:        ds.w 1
PageIn_InFlight:        ds.b 1          ; nonzero while ZX0R may be on the resumable path
PageIn_Suspended:       ds.b 1          ; nonzero = banked context awaits resume
```

  If ask 3 does not fully abstract the offset, define `VBH_STACKED_PC = 15*4+2` in `engine/system/constants.emp` as the interim.
- [ ] **Step 3: The hook in `VBlank_Handler`** — insert immediately after `movem.l d0-a6,-(sp)` (vblank.emp:41), before the `VBlank_Ready` test. Read/write the interrupted PC via `irq_frame.pc` (ask 3); range-check against `[ZX0R_Start, ZX0R_Decompress__end)` (ask 2 symbol):

```asm
        tst.b   PageIn_InFlight         ; art decode possibly interrupted?
        beq.s   .no_decode
        ; d0 := irq_frame.pc  (the PC the rte will return to)
        cmpi.l  #ZX0R_Start, d0
        blo.s   .no_decode
        cmpi.l  #ZX0R_Decompress__end, d0
        bhs.s   .no_decode
        move.l  d0, PageIn_Saved_PC
        ; irq_frame.pc := PageIn_BankRegs
    if DEBUG == 1 { addq.w #1, Dbg_PageIn_Preempts }
.no_decode:
```

  The *effect* fires at the handler's `rte` — after VInt_Level's whole pipeline and the movem restore — so "bookmark is the V-int's final act" holds even though the *check* runs at entry (survey §2).
- [ ] **Step 4: Bank + resume in `page_in.emp`.** `PageIn_BankRegs` is entered BY the hijacked `rte` with the decoder's live registers (movem-restored) and the decoder's SR/CCR; its first instruction must touch nothing before `move.w sr,…`. This needs ask 4's continuation form (entered by rte, exits bare `rts`) and ask 5's typed `jmp`:

```asm
PageIn_BankRegs:                         ; @continuation — entered by rte, register state declared
        move.w  sr, PageIn_Saved_SR
        movem.l d0-d2/a0-a3, PageIn_Saved_Regs
        st.b    PageIn_Suspended
        rts                              ; SP at PageIn_Process depth -> returns to VSync_Wait

PageIn_Process:                          ; bsr'd from VSync_Wait each frame
        tst.b   PageIn_Suspended
        beq.s   .fresh
        clr.b   PageIn_Suspended
        movem.l PageIn_Saved_Regs, d0-d2/a0-a3
        move.l  PageIn_Saved_PC, -(sp)   ; manufactured resume frame (ask 4)
        move.w  PageIn_Saved_SR, -(sp)
        rte                              ; straight back into the decoder loop
.fresh:
        ; Task 3: single hardwired test request — set a0/a1, lea .after(pc),a3,
        ; st PageIn_InFlight, and FALL THROUGH (jmp) into ZX0R_Decompress.
        ; MUST NOT push anything here: PageIn_BankRegs's rts would pop it as a
        ; return address (survey §3 rts-corruption trap).
        rts
.after:
        clr.b   PageIn_InFlight
        ; Task 3: set a done flag the test reads. Task 4: mark request complete + DMA.
        rts
```

  In DEBUG, `.fresh`'s resume path bumps `Dbg_PageIn_Resumes`.
- [ ] **Step 5: Wire `PageIn_Process` into `VSync_Wait`** — called AFTER the `with ints_off` bracket (vblank.emp:293), before `.wait` (survey §3 constraint 1: the atomic pair must not be split; decode before Ready-set would break the lag-path proof):

```asm
VSync_Wait:
        ...                              ; existing: clear stale flag
        with ints_off { move.b d0, VBlank_Flag ; move.b #1, VBlank_Ready }   ; :290-293 (unchanged)
        jbsr    PageIn_Process           ; NEW: idle-time decode slice
.wait:  ...                              ; existing spin on VBlank_Flag :295-302
```

- [ ] **Step 6: Contract-surgery ripple (survey §3, an EXPLICIT step, not incidental).** `VSync_Wait`'s license widens: today `clobbers(d0) preserves(sr.mask)`; with the decode slice inside, its clobber set becomes the PageIn/decoder union (d0-d2/a0-a3 at minimum, and `PageIn_Process` must add nothing beyond it and push nothing before falling into the decoder). Update `VSync_Wait`'s contract. Then **re-verify every caller** — Sigil turns this ripple into build errors until reconciled (that is the feature): known affected caller `Level_LoadArt` (load_art.emp:108) folds "VSync_Wait d0" into its license and keeps a6/a4/d4 live across the retry loop; a4-a6 stay outside the decoder set so it survives, but its contract text must be redone. `GameLoop` (game_loop.emp:28) already clobbers everything — no ripple. Fix each build error the widened license surfaces; do not suppress.
- [ ] **Step 7: Preemption test (DEBUG, temporary scaffold — removed in Task 4). ⚠ controller.** After boot with display ON: queue the largest act pool page as the test request, decode it via the dispatcher across frames into a spare buffer, then compare against a blocking `ZX0_Decompress` of the same page. Assert: outputs byte-identical AND `Dbg_PageIn_Preempts > 0` (an 8KB page ≈ 620K cycles cannot fit one frame's idle — a zero means the hook never fired: investigate before proceeding, and see the review-gate appendix's kosplus failure #2). Run 3 consecutive cycles to prove suspend/resume re-entry.
- [ ] **Step 8: Build + oracle. ⚠ controller.** Green; boot; test passes (no error screen); gameplay unaffected; `Lag_Frame_Count` at rest = 0.
- [ ] **Step 9: Commit.** Verify branch. `feat(level): VBlank bookmark preemption for the resumable art decoder (P2a)` — note in the message that nested-HInt is safe by contract (hblank.emp) and record the observed `Dbg_PageIn_Preempts` count.

### Task 4: P2a — Page-in request queue + cancel/flush + init-path routing

**Files:**
- Modify: `engine/level/page_in.emp` (real FIFO queue + `PageIn_Flush`), `engine/level/load_art.emp` (`Level_LoadArt` :108 drives the queue), `engine/ram.emp`.
- Delete: the Task-3 test scaffold.
- Parcel ritual.

- [ ] **Step 1: Research.** Read `Level_LoadArt` (load_art.emp:108-165) and `Art_Decompress` (:50) as they stand; read the DMA queue enqueue API — `QueueDMA_Critical`/`Important`/`Deferrable` (dma_queue.emp:94/:100/:106, each `out(carry: dropped) preserves(sr.mask)` — the carry contract the FIFO mirrors) and the `QueueDMA_Critical` call + `.drop_page` retry idiom in `Level_LoadArt` (load_art.emp:133, :157-165). Read S3K's queue shape for calibration (spec §11: ~4-deep FIFO, head-first, retry-when-full).
- [ ] **Step 2: Request queue.** 8-entry FIFO in RAM, entry = `{page_id.w, flags.b (PGRQ_DEMAND bit), pad.b}`; enqueue returns carry when full (caller retries next frame — the B&R rollback idiom). `PageIn_Process .fresh` pops the head, resolves page→source ptr + dest VRAM via the manifest table, and either falls into `ZX0R_Decompress` (ZX0 form) or enqueues a direct ROM→VRAM DMA (raw form — no staging, no decode). On `.after`: enqueue staging→VRAM DMA at Important priority, set `PageIn_Staging_Busy`; a new decode does not start while `PageIn_Staging_Busy` is set; clear it in `VInt_Level` right after the Important drain when the Important queue emptied. Demand-priority entries dequeue before prefetch entries (two head pointers or a two-pass scan — pick and comment).
- [ ] **Step 3: `PageIn_Flush` (cancel/flush — survey §4, main-loop context only).** Clears `PageIn_Suspended` + `PageIn_InFlight`, empties the request FIFO (both priorities), leaves `PageIn_Staging_Busy` alone (an already-*published* page's staging→VRAM DMA is allowed to land — its destination is a page frame; every flush caller either resets the page cache or keeps the landing valid). NO mid-DMA-queue surgery, ever. In DEBUG bump `Dbg_PageIn_Flushes`. **Caller rules (wire the hooks now; the cache-reset callers finalize in Task 6):** call `PageIn_Flush` at act/level transition (before the future `PageCache_Init`); call it on the section teleport path *only if* it invalidates the tile cache — **pure rebases do NOT flush** (page identity is position-independent, spec §5, so the in-flight page is still the right page). Block-tier analog for review symmetry: `TileCache_InvalidateStaging` (tile_cache.emp:161). **NEVER call `PageIn_Flush` from interrupt context.**
- [ ] **Step 4: Route init through it.** `Level_LoadArt` becomes: for each page, enqueue request + `jbsr VSync_Wait` in a loop until all pages resident (display off — Critical/Important drains run in the extended blanking as today). Delete the direct `Art_Decompress`-loop body. Keep `Art_Decompress` only if other callers remain (grep — the block tier uses `S4LZ_DecompressDict`, not this); if none remain, delete it and keep `ZX0_Decompress` only as the self-test oracle for ZX0R (comment it as such). Remove the Task-3 test scaffold.
- [ ] **Step 5: Build + oracle. ⚠ controller.** Green; boot; OJZ renders identical to Task 1 baseline (screenshot compare); full max-scroll circuit clean; `Dbg_PageIn_Preempts` reads 0 during normal play (nothing streams mid-game yet). Init self-tests still pass.
- [ ] **Step 6: Commit.** Verify branch. `feat(level): page-in request queue + cancel/flush; level init rides the streaming path (P2a complete)`.

### Task 5: P2b — Format cutover: 64-tile ZX0/raw pages, manifest v2, logical indices

**⚠ ASK THE USER before starting — this task edits `tools/ojz_strip_gen.py` (daemon-watched). Never `--amend` near it.**

**Files:**
- Modify: `tools/ojz_strip_gen.py` (Pass 5 remap :1313, Pass 6 page emission :1352, **Pass 6b BG blob :1360 sits between**, manifest **Pass 7** :1396-1406 — emits an `.emp` module; `remap_nametable_word` def at `tools/tile_dedupe.py:148`, called at `ojz_strip_gen.py:1325` and :371-389), `build.sh` (per-page compression + form election — build.sh is 186 lines now; salvador vendored-build + page-blob handling + the one-invocation sigil build — **re-read at execution** and place raw-election beside the salvador step).
- Modify: `engine/level/load_art.emp`, `engine/level/page_in.emp`, `engine/system/constants.emp` (`ART_POOL_PAGE_TILES` :227).
- Modify: `engine/level/tile_cache.emp` (translation at block decode — Step 4).
- Test: inline pytest in `ojz_strip_gen.py` (`def test_*` :641-901; runner `python3 -m pytest tools/ -q`).
- Parcel ritual.

**⚠ Three T4-review tripwires — correct today at 256-tile/3-page OJZ, BUGS at this cutover (fix all three as part of Step 3's engine consumption):**
1. `Level_LoadArt` enqueues ALL pages up-front with `@discards(dropped)` — at ~10+ pages > `PAGEIN_QUEUE_SLOTS`(8) it silently drops pages. Switch to incremental enqueue-and-drain (retry dropped enqueues in the spin) or grow the queue; either way delete the discard.
2. `PageIn_Process`'s DMA dest is a hardcoded `lsl #8 + lsl #5` (= `page_id<<13`, 8192 B pages) — derive from `ART_POOL_PAGE_BYTES` (becomes `<<11` at 64-tile/2048 B) or assert the shift against the constant at build time.
3. `PageIn_Process` doesn't skip size-0 wrappers (`Art_Decompress`'s header says callers must) — unreachable today (manifest lists only real pages) but a stub/partial page would feed ZX0R a 0-length stream. Add the guard when the manifest goes v2.

**Task-5 execution amendments (2026-08-08).** Three anchors in the text above were verified wrong against the actual pipeline; the controller ruled (rulings recorded here — plan stays source of truth):
- **R1 — raw election is NOT in `build.sh`.** `build.sh` never compresses pages; it only builds the salvador binary + verifies the committed tree + runs `sigil build`. Per-page `.bin`→`.zx0` compression, the 4-byte wrapper, and `ojz_act_pool.emp` emission live in `tools/regenerate-level.sh:46-107` (a MANUAL donor-fed re-bake). Raw/zx0 form election goes there, beside the salvador step; `tools/verify_level_bin.py` becomes v2-aware (page size, wrapper form/version, per-page form byte). Both scripts are IN SCOPE (not daemon-watched — only `ojz_strip_gen.py` + `data/editor/ojz/` are). `build.sh` untouched.
- **R2 — manifest v2 shape.** The byte-emitting `{source.l, tiles.w, form.b, flags.b}` stride-8 table REPLACES `OJZ_Act_Pool_PageTable` as what `Act.act_art_pool_table` points at. Emission splits by knowledge: `ojz_strip_gen.py` Pass 7 additionally emits a deterministic JSON sidecar with per-page `{tiles, pinned}` (pinned = ≥75%-of-sections rule + page 0 always). `regenerate-level.sh` consumes the sidecar, adds `{source, form}` (form = its ratio election), and emits the final v2 table in `ojz_act_pool.emp`. The zero-ROM const manifest module keeps the comptime counts (updated to v2 reality) for the descriptor guard. `PageIn_Process` strides the v2 table; form dispatch is manifest-driven (replaces wrapper-version dispatch) with a DEBUG assert that the ZX0 wrapper version agrees with the manifest form.
- **R3 — local→global home + re-bake.** `ojz_strip_gen.py` Pass 5 (the site that today writes GLOBAL slots into the strips) instead writes per-section LOCAL indices and emits per-section local→global tables as deterministic binary artifacts, packaged as generated `.emp` data placed on the engine's existing per-section resolution path. Full `regenerate-level.sh` re-bake AUTHORIZED (donors present). Constraint: after the re-bake, every non-art-pool output (collision tables, entity data — anything the page cutover doesn't touch) must be BYTE-IDENTICAL to the committed tree; any unexpected diff = STOP (donor/toolchain drift). Art-pool + strips + block blobs + manifests are expected to change.

- [ ] **Step 1: Research.** Confirm with the user (daemon coordination). Read Pass 5/6/6b/7 + manifest emission in the generator AND the consuming engine sites; read `remap_nametable_word` (tile_dedupe.py) to see which bits carry tile index vs palette/priority/flip; read the S4LZ block-dict emission to choose where the per-section local→global table rides.
- [ ] **Step 2: Generator v2.** (a) Page size 256→`ART_POOL_PAGE_TILES = 64` (spatial order preserved — pages are consecutive 64-index runs). (b) Per-section **local→global tables**: collect each section's referenced global pool indices into a ≤2047-entry local palette; rewrite block nametable words to local indices (bits 0-10; palette/priority/flip untouched); emit the table with the section's dict data. Build-fails if a section references >2047 distinct tiles. (c) Manifest v2 per page: `dc.l source`, `dc.w tiles`, `dc.b form (0=zx0,1=raw), flags (bit0=pinned)`; pinned marking: pages whose tiles are referenced by ≥ `PIN_SECTION_FRACTION` of sections (start 75%, tunable) — page 0 always pinned (blank tile 0). (d) Raw election in `build.sh`: compress each page; keep `.zx0` only if it saves ≥ `RAW_ELECT_MIN` (10%) else emit `.raw` and mark the form. (e) All `POOL_TILE_CEILING`-style asserts become page-count + residency asserts (`pages ≤ PAGE_TABLE_MAX = 256`).
- [ ] **Step 3: Engine consumption — identity residency.** Page frames exist in name only this task: page N loads to VRAM slot `N*64` exactly as today (OJZ's 10 pages ≤ 15 frames). `page_in.emp` reads manifest v2. Staging shrinks: `ART_STAGING_BUFFER_SIZE = 64*32 = 2048` (constants.emp:382); keep it a named buffer in `lower_ram`. **The init-only `Art_Staging_Buffer = alias(Tile_Cache_Nametable)` at ram.emp:102 is DELETED** — steady-state streaming can't overlay live cache RAM; give the staging buffer its own allocation (charge it against the Task-1 lower-RAM slack).
- [ ] **Step 4: Translation at block decode.** In `TileCache_CopyBlockColumn`'s consumers (proc head tile_cache.emp:303) and `TileCache_FillRow` (jbsr sites :725/:738/:916 — locate the proc + its staged-word write loops at execution; bodies were re-shaped by the H6 hoist): each staged word's local index (bits 0-10) is translated to global via the section's local→global table before it lands in `Tile_Cache_Nametable`. This task the "patch" is identity (global == VRAM slot), so translate-then-write reproduces today's output exactly. Keep flip/pal/pri bits intact (mask, or, write).
- [ ] **Step 5: pytest.** Extend the inline tests (:641-901): local tables round-trip (word→local→global == original global); page split covers the pool exactly; a fabricated >2048-tile pool passes generation with >32 pages (unbounded-index proof); a fabricated section referencing >2047 distinct tiles FAILS loudly.
- [ ] **Step 6: Build + oracle. ⚠ controller.** Green; boot; OJZ pixel-identical to baseline (screenshot at rest + during a max-scroll circuit — translate bugs show as wrong tiles instantly); collision unaffected (drive a terrain circuit). `python3 -m pytest tools/ -q` green.
- [ ] **Step 7: Commit.** Verify branch. `feat(art): 64-tile ZX0/raw pool pages, manifest v2, logical indices + per-section translation (P2b cutover)`.

### Task 6: P2b — Residency cache: page table, frames, refcount, LRU, patch

**Files:**
- Create: `engine/level/page_cache.emp` + its head-labels (`PageCache_*`) into `games/sonic4/map.toml` `order`.
- Modify: `engine/level/tile_cache.emp` (the Task-5 translate sites gain patch + refcount; the §7.2 adoption-seam comment — Step 4), `engine/level/page_in.emp` (dest = allocated frame), `engine/ram.emp`, `engine/system/constants.emp`, `engine/structs.emp`.
- Parcel ritual.

- [ ] **Step 1: Research.** Re-read the Task-5 translate sites as landed; read the LRU-list shape in spec §5 and van Waveren's free/LRU/locked tri-list (spec §11); read `TileCache_FillColumn`/`FillRow`'s overwrite behavior — where OLD cache words get replaced (the decrement sites).
- [ ] **Step 2: Structures** (`.emp` struct/const syntax):

```asm
; engine/system/constants.emp
PAGE_FRAMES        = 15                 ; 960-tile FG region / 64
PAGE_TABLE_MAX     = 256                ; max pages per act (assert in generator)
PAGE_NOT_RESIDENT  = $FF
; engine/structs.emp
        struct PageFrame
pf_page         ds.w 1                  ; resident page id, or -1
pf_refcount     ds.w 1                  ; cache words referencing this page
pf_lru_prev     ds.b 1
pf_lru_next     ds.b 1
pf_flags        ds.b 1                  ; bit0 = pinned
pf_pad          ds.b 1
        endstruct
; engine/ram.emp (lower_ram — sizeof is compiler truth, no manual _len)
Page_Table:     ds.b PAGE_TABLE_MAX     ; page id -> frame idx / PAGE_NOT_RESIDENT
Page_Frames:    ds.b PAGE_FRAMES*sizeof(PageFrame)
```

- [ ] **Step 3: `page_cache.emp` API** (each a documented proc): `PageCache_Init` (frames free, pinned pages loaded, table built — calls `PageIn_Flush` first per Task 4's caller rule), `PageCache_Lookup` (page→frame or NOT_RESIDENT, ~10 cyc), `PageCache_Request` (enqueue demand/prefetch page-in if not resident + not queued), `PageCache_AllocFrame` (free list, else LRU tail with refcount 0 and !pinned; NO victim with refcount>0 — `raise_error` in DEBUG if none available: that is a thrash bug, not a policy), `PageCache_Ref`/`PageCache_Unref` (word-granular inc/dec + LRU touch on 0→1 / move-to-tail on 1→0).
- [ ] **Step 4: Patch + refcount at cache entry.** The Task-5 translate sites become: local→global→`Page_Table` lookup→physical slot = `frame*64 + (global & 63)`; write patched word; `PageCache_Ref(page)`. Every overwritten cache word first passes its old physical word back through frame→page (`slot>>6` → `Page_Frames[..].pf_page`) for `PageCache_Unref`. Blank/zero words skip both. If the needed page is NOT resident: `PageCache_Request(demand)`, store a resume key, and return "partial" through the existing keyed-resume fill contract (the pattern is the column commit at tile_cache.emp:813 "resume is keyed by column" and the row commit at :912 "resume is keyed by row"; do NOT confuse it with the H4 trailing-lag gate at :974-984). **D2 seam (documented, NOT built):** add a named comment in the `Tile_Cache_Fill` budget area marking the §7.2 unified-arbiter adoption point — the place a future third consumer with real non-preemptible cost would plug in a cost-denominated arbiter. Build nothing; the comment + Task-12 ARCH text ARE the seam.
- [ ] **Step 5: Page-in destination = frame.** `page_in.emp` asks `PageCache_AllocFrame` at dequeue time; DMA dest = `frame*64*32`. On completion, update `Page_Table` + frame fields.
- [ ] **Step 6: DEBUG audit assert.** A DEBUG-boot + on-demand routine: walk the whole `Tile_Cache_Nametable`, recompute per-frame refcounts from scratch, compare to `pf_refcount` — `raise_error` on mismatch. Run after init and (hotkey or every N frames in DEBUG) during play.
- [ ] **Step 7: Build + oracle. ⚠ controller.** OJZ still fully resident (10 pages ≤ 15 frames → no eviction yet): pixel-identical baseline, audit assert clean over a full circuit, `Lag_Frame_Count` regression ≤ baseline + 0 (refcount cost is the watch item — if lag appears, profile before optimizing).
- [ ] **Step 8: Commit.** Verify branch. `feat(level): page-frame residency cache — table, refcount, LRU, patch-at-entry (P2b)`.

### Task 7: P2b — Eviction live + trailing-lag prefetch gate + forced-eviction soak

**Files:**
- Modify: `engine/level/page_cache.emp`, `engine/system/constants.emp` (DEBUG clamp), `engine/level/page_in.emp` (prefetch + the D3 gate), `engine/ram.emp` (own lag latch).
- Parcel ritual.

- [ ] **Step 1: Research.** Read the shipped unified prefetch (H1-H5, 2026-07-16) in `tile_cache.emp`: row scan ~:1000-1046 (`Cache_Pfx_Row_Target` :997/:1039), col scan ~:1092+ (`Cache_Pfx_Col_Target` :998, H3 direction hysteresis), the H4 deadline gate at :974-984, and the fill-owned trailing-lag latch `Cache_Pfx_Lag_Flag` (baseline-cleared :465, set :699, cleared :702). 16 staging slots (H5) are already live. The page prefetch consumes these richer direction signals.
- [ ] **Step 2: Prefetch.** When the fill's leading edge advances, look one block-column/row further ahead: collect that strip's referenced pages (via the same local→global path) and `PageCache_Request(prefetch)` any non-resident ones. Bounded: ≤2 requests enqueued per frame.
- [ ] **Step 3: D3 trailing-lag admission gate (the shipped H4 pattern, VERBATIM).** Gate **speculative (prefetch) decode STARTS only**. Implement an OWN `Frame_Counter`-delta latch INSIDE `page_in` (a new byte in `engine/ram.emp`) — **NOT** a reuse of `Cache_Pfx_Lag_Flag`, which is fill-owned and only as fresh as the last `Tile_Cache_Fill` call. Skip a speculative start if the previous frame lagged; **bound to ≤1 consecutive skip** (a second lagged frame does NOT skip, so sustained lag can't starve prefetch into a cold-page cascade). **Demand decodes and RESUMES are NEVER gated** — a stalled fill is the highest-priority deferred work; a suspended decode holds the single staging slot and finishing it is always better than freezing it. Rationale: decode CPU is structurally free under the bookmark, but a completing speculative page still adds DMA-window pressure and occupies the staging slot during exactly the frames already tight. Explicitly rejected: per-chunk deadlines, VDP beam reads, gating resumes.
- [ ] **Step 4: Forced eviction.** `if DEBUG == 1: PAGE_FRAMES_CLAMP = 6` (OJZ's 10 pages can no longer all be resident) behind a build flag `STRESS_EVICT=1` in build.sh. With it on: full OJZ circuits force continuous evict/reload traffic through every path.
- [ ] **Step 5: Soak. ⚠ controller.** STRESS_EVICT build, oracle: 3+ full max-scroll circuits both directions + vertical + diagonal. Gates: zero wrong-tile frames (screenshot spot checks DURING motion), audit assert clean throughout, no deadlock in the demand-stall path (fill always completes once its page lands), `Dbg_PageIn_Preempts` climbing (decodes are being sliced), lag bounded (this is a synthetic overload — clamp-frame counts recorded, not gated, until Task 10 adds the camera gate).
- [ ] **Step 6: Commit.** Verify branch. `feat(level): LRU eviction + trailing-lag-gated page prefetch live; forced-eviction soak clean (P2b complete)`.

### Task 8: P2c — Vectorman dual cap on the DMA queue

**Files:**
- Modify: `engine/system/dma_queue.emp` (the three `QueueDMA_*` procs + shared internals, :94-133 region), `engine/ram.emp`, `engine/system/constants.emp`, `engine/system/vblank.emp` (`VInt_Level` per-frame reset beside `DMA_Budget_Remaining` :97).
- Parcel ritual.

- [ ] **Step 1: Research.** Read the `QueueDMA_*` carry-on-full contract (`out(carry: dropped)`, dma_queue.emp:94/:100/:106) and callers' failure handling; read the Vectorman mechanism (spec §11: enqueue-side running byte total + entry cap, atomic per-request rollback, retry next frame). Note there is NO single `QueueDMATransfer` symbol — the unified enqueue is the three procs + shared internals.
- [ ] **Step 2: Implement.** `DMA_Enq_Bytes_Frame` word, reset in `VInt_Level` beside the existing `DMA_Budget_Default → DMA_Budget_Remaining` reset (vblank.emp:97); the shared enqueue path adds the transfer's byte size; over `DMA_ENQ_BYTE_CAP` (start 12288 — above the drain budget so it only catches runaway enqueue storms) → roll back the size add, return carry exactly like queue-full. The 128KB-split path must roll back BOTH halves or neither (split entries commit atomically). **This is NOT an arbiter (D2) — it is a per-tier admission cap on one resource (DMA bytes); it builds no shared ledger.**
- [ ] **Step 3: Verify + commit. ⚠ controller.** Green build, baseline circuit unaffected (cap never hits in normal play — DEBUG counter proves it stayed 0), STRESS_EVICT soak unaffected. Verify branch. Commit: `feat(system): enqueue-side dual cap (entries+bytes) on the DMA queue (P2c)`.

### Task 9: P2c — B&R per-act art budget word

**Files:**
- Modify: `engine/structs.emp` (Act struct :28), `games/sonic4/data/levels/ojz/act1/act_descriptor.emp` (`OJZ_Act1_Descriptor` typed literal :81), `engine/level/page_in.emp`, `engine/ram.emp`, `engine/system/vblank.emp` (`VInt_Level`).
- Parcel ritual.

- [ ] **Step 1: Research.** Read the Act struct (`engine/structs.emp:28` — existing `act_art_pool_table` :39, `act_art_pool_pages` :40; `sizeof` is compiler truth, no manual `Act_len`) and the descriptor consumer in level init. **Editor-exporter drift warning:** re-verify whether a stale descriptor exporter still exists at all under `games/sonic4/data/editor/ojz/act1/export/` (it now holds `section_*.{art,coll,tiles}.bin` streams; the old stale `act_descriptor.asm` exporter may be gone) — do NOT touch that directory (daemon-watched); only the hand-maintained `data/levels/.../act_descriptor.emp` + the struct change here.
- [ ] **Step 2: Implement.** Append `act_art_budget: u16` to the Act struct (the typed literal `OJZ_Act1_Descriptor` :81 is compiler-checked, so the new field is caught if unset — no `Act_len` bookkeeping); OJZ value 4096 (two pages/frame ceiling). Level init copies it to `Act_Art_Budget` RAM; `VInt_Level` reloads `Art_Budget_Remaining` from it each frame; `page_in.emp` charges each page's DMA bytes against it and defers further page-ins to the next frame when exhausted (the request stays queued — nothing dropped). **This is a per-tier budget, not a unified arbiter (D2).**
- [ ] **Step 3: Verify + commit. ⚠ controller.** Baseline + STRESS_EVICT circuits clean; DEBUG counter shows deferrals only under stress. Verify branch. Commit: `feat(level): per-act art streaming budget word (B&R pattern) (P2c)`.

### Task 10: P2c — Camera soft-clamp degradation

**Files:**
- Modify: `engine/level/camera.emp`, `engine/level/tile_cache.emp` (demand-stall depth signal), `engine/ram.emp`.
- Parcel ritual.

- [ ] **Step 1: Research.** Read `Camera_Update` (camera.emp:205) and its per-axis clamp — `CAM_MAX_X_STEP` is now a **file-local const at camera.emp:21** (`CAM_MAX_Y_STEP` comes from `engine.constants`, `use`d :10); splice points are `.x_clamp` (:286) / `.y_clamp` (:387) with the `clamp_camera_axis_reg` comptime helper (:101). Read where the fill's stall state lives (Task 6's resume key).
- [ ] **Step 2: Implement.** Signal: a demand-stalled fill whose stalled edge is within `CLAMP_MARGIN_TILES = 4` block-columns/rows of the visible screen edge sets `Camera_Art_Hold` (axis-tagged). `Camera_Update` treats a held axis' max step as 0 (full classic S3K-gate feel: the camera waits; player logic untouched). Cleared the frame the stall resolves. DEBUG: `Dbg_Cam_Clamp_Frames` counter.
- [ ] **Step 3: Verify + commit. ⚠ controller.** Normal build: counter stays 0 through all circuits (prefetch does its job). STRESS_EVICT: clamps engage at worst-case seams instead of showing unfetched art — screenshot-verify during motion that no wrong/blank FG tile is ever visible. Verify branch. Commit: `feat(level): camera soft-clamp on art demand-miss (honorable degradation) (P2c)`.

### Task 11: P2c — Stress fixture + acceptance matrix

**⚠ ASK THE USER before starting — this task edits `tools/ojz_strip_gen.py` (daemon-watched). Never `--amend` near it.**

**Files:**
- Modify: `tools/ojz_strip_gen.py` (`--stress-uniquify N` flag; inline pytest :641-901), `build.sh` (`STRESS_ART=1` plumbs it).
- Parcel ritual (on any engine byte change; the generator/build changes ride the daemon).

- [ ] **Step 1: Research.** Confirm with the user; read the pool-emission pass (Pass 6 :1352) once more.
- [ ] **Step 2: `--stress-uniquify N`.** Post-dedup, clone existing pool tiles with a per-clone pixel perturbation (e.g. XOR a counter into one row) and re-point a spread of block references at the clones until the pool reaches N distinct tiles (default 2600 — crosses the 2048 index line and exceeds 15 frames ≈ 4×). Deterministic (seeded by index, no RNG). Inline pytest: N=2600 generation succeeds, >40 pages, local tables valid.
- [ ] **Step 3: Acceptance matrix (the spec's P2c gate), STRESS_ART=1 build, oracle. ⚠ controller.**
  - sustained max scroll H, V, and DIAGONAL, 600+ frames each, both directions;
  - zero visible pop-in / wrong tiles (screenshots during motion at fixed intervals);
  - `Lag_Frame_Count` per run recorded; diagonal target: no worse than the Task 1 baseline (the 2026-08-05 **33.2% diagonal window**) — art streaming must not measurably deepen it (compare, record numbers);
  - `Dbg_Cam_Clamp_Frames` bounded (record; expect brief engagements at worst seams only);
  - **idle-minima floor (survey §5): log the `VSync_Wait`-entry-to-VBlank per-frame cycle FLOOR over each stress window via DEBUG state counters (NOT the per-frame profiler — averages hide minima). Record the floor alongside `Lag_Frame_Count`;**
  - refcount audit assert clean after every run.
- [ ] **Step 4: Page-size sweep (D1 — a P2c TUNING KNOB, not a task).** Because the fixture + ROM report exist, sweeping `ART_POOL_PAGE_TILES` (32/64/128) is now a ~10-minute experiment: rebuild at each size, re-run the diagonal acceptance run, record lag + ROM ratio. This is optional tuning to pick the final page size; the bookmark already closed the latency question (D1 rationale), so there is no gate here — just record the numbers and pick the density/manifest sweet spot.
- [ ] **Step 5: Commit.** Verify branch. `feat(tools): stress-uniquify fixture; Phase 2 acceptance matrix passed (P2c)` — include the numbers table (+ any page-size sweep results) in the commit message.

### Task 12: ROM budget gate, docs, merge

**Files:**
- Modify: `build.sh` (report + gate), `docs/ENGINE_ARCHITECTURE.md` (§9.7 rewrite + §2 residency section + cross-ref sweep), `docs/DEFERRED_WORK.md`, `CLAUDE.md` (compression line), `docs/superpowers/2026-07-02-design-week-queue.md` (log).
- Parcel ritual on any residual engine byte change.

- [ ] **Step 1: ROM report + gate.** `build.sh` prints per-act: raw pool bytes, stored bytes per form, page count, ratio; warns above `ART_ROM_SOFT_KB` and fails above `ART_ROM_HARD_KB` (per-act overridable vars; OJZ defaults 24/64 KB — generous now, tightened when real acts exist).
- [ ] **Step 2: ARCH §9.7 rewrite (D4 — land the ratified draft).** Drop in the replacement text from `docs/superpowers/2026-08-06-arch-97-rewrite-proposal.md` VERBATIM (title "§9.7 Idle-Time Deferred Work — Pre-Chunked Pages + Supervisor Bookmark", the two-layer structure 9.7.1–9.7.4, the trailing-lag gating text, the D2 "no unified arbiter" paragraph with the named `Tile_Cache_Fill` adoption seam, the cancel/flush path, the consumers table, and the "user-mode multitasking REJECTED" record). It drops in at ENGINE_ARCHITECTURE.md:3800-3835. Then apply the proposal's **cross-reference sweep table** (ARCH :1312/:1390/:1437/:3802-3835/:3844/:3885; DEFERRED_WORK :55-64/:714-733/:746/:866-875; CLAUDE.md engine-summary line; spec §4/§5 stale-figure notes). Sweep for stale claims everywhere: "fully resident", "loaded once at init", `ART_POOL_PAGE_TILES = 256`.
- [ ] **Step 3: DEFERRED_WORK closeout.** Mark the Phase-2 amendments entry RESOLVED (pointing here); delete/close the `Decomp_Buffer`/`Art_Staging_Buffer` alias entries this work retired; rescope the "§9.7 is the sole gate on three consumers" rows to point at this plan and close them when P2a merged; add follow-ups discovered en route.
- [ ] **Step 4: Scaffold sweep.** Confirm deleted: Task-3 test scaffold, `Art_Staging_Buffer` alias (ram.emp:102), `Art_Decompress` (if Task 4 orphaned it), old 256-tile constants, any `if old else new` remnants. `grep -rn "ART_POOL_PAGE_TILES\|Decomp_Buffer\|Art_Staging_Buffer\|Art_Decompress" engine/ games/ tools/` returns only current-design hits.
- [ ] **Step 5: Final gates + merge. ⚠ controller.** Full `DEBUG=1 ./build.sh` + plain `./build.sh` both green; `python3 -m pytest tools/ -q` green; one last baseline circuit + STRESS_EVICT soak + acceptance spot-check; run the review-gate appendix checklist; then merge `feat/art-streaming-p2` → master (merge commit per repo habit — verify branch at each commit), and update the design-week queue log.

---

## Review gate appendix (run before Task 12 merge — from the in-tree negative example)

Legacy `sonic_hack/code/engines/kosplus.asm` ported the S3K bookmark and broke all three invariants. Review the shipped mechanism against its failure modes (mechanism survey §7):

- [ ] decode body physically inside `[ZX0R_Start, ZX0R_Decompress__end)` — no `jsr`/`jbsr` from the guarded range to an unguarded body (kosplus failure #3);
- [ ] the processor/dispatcher runs from the main loop's idle site (`VSync_Wait`), never from inside the V-int (kosplus failure #1);
- [ ] the bookmark hook actually has call sites in the shipped shape — grep proves the hook is live, `Dbg_PageIn_Preempts > 0` proves it fires (kosplus failure #2: zero call sites);
- [ ] the lag-path proof re-verified after any `VSync_Wait`/`VBlank_Handler` edit (the survey §2 structural argument is protocol-dependent — decode is only ever live after `VBlank_Ready = 1`, so a mid-decode VBlank always dispatches `VInt_Level`);
- [ ] no stack push anywhere between dispatcher entry and decoder fall-through (the survey §3 rts-corruption trap — `PageIn_BankRegs`'s `rts` would pop a stray push as a return address);
- [ ] `PageIn_Flush` called at every cache-invalidating transition, and NOT at pure rebases (survey §4);
- [ ] no task built an arbiter or shared cost ledger (D2); the §7.2 seam is comment + ARCH prose only;
- [ ] no gate touches demand decodes or resumes (D3); the trailing-lag latch is page_in-owned, ≤1 consecutive skip.

---

## Self-review (done at write time, v2)

- **Rulings folded:** D1 (bookmark-first) → task order unchanged, page-size sweep is Task 11 Step 4 not a task; D2 (no arbiter) → Tasks 6/8/9 explicitly per-tier, §7.2 seam is comment + ARCH text only, no task builds a ledger; D3 (trailing-lag gate) → Task 7 Step 3 owns a page_in latch, ≤1 skip, demand + resumes never gated; D4 (ARCH rewrite) → Task 12 Step 2 lands the ratified draft verbatim + its cross-ref sweep.
- **Addendum absorbed:** every global + per-task re-anchor is inline (`.emp` paths, map.toml `order` in each Files list, no `main.asm`, DEBUG-suffixed builds, RAM regions/compiler checks, structs `sizeof`); the three new standing rules (Sigil first-class dependency, contract-surgery-is-work, oracle gotchas) are in the standing-rules block. The addendum no longer needs side-by-side reading.
- **Sketch folded:** §3 contract ripple → Task 3 Steps 5-6 (VSync_Wait clobber widening + Level_LoadArt re-verify, explicit); §4 cancel/flush → Task 4 Step 3 (`PageIn_Flush` + caller rules); §5 instrumentation → Task 2 Step 3 + Task 3 Steps 3/7 (`Dbg_PageIn_Preempts/Flushes/Resumes`); §7 review checklist → review-gate appendix; §6 asks → the Sigil-gating standing-rules block + per-task gate markers.
- **Anchors re-verified against master `824b69f`** (drift fixed inline): load_art `Art_Decompress` :46→:50, `Level_LoadArt` :103→:108, `QueueDMA_Critical` :128→:133, retry idiom now `.drop_page` :157-165; constants `ART_POOL_PAGE_TILES` :228→:227, `ART_STAGING_BUFFER_SIZE` :383→:382; act_descriptor `OJZ_Act1_Descriptor` :77→:81; compression_selftest tail :117-124→:117-126; tile_cache `CopyBlockColumn` :302→:303, `InvalidateStaging` :159→:161, keyed-resume commits :807/:906/:947→:813/:912, H4 gate :973-1037→:974-984 + scans :1000-1046/:1092+, lag latch :693/:696→:699/:702; ram `@shape_divergent` DEBUG block :260, `Engine_RAM_End` :580, `Art_Staging_Buffer` alias :102; build.sh 168→186 lines (raw-election "re-read at execution" kept); ojz passes 5/6/6b/7 confirmed :1313/:1352/:1360/:1396, pytest :641-901; map.toml `order` :43.
- **Baseline-numbers rule carried:** 2026-08-05 idle table (74.3 / 67.8 / 33.2); lower-RAM slack re-measured from fresh `s4.debug.lst` at Task 1.
- **Standing-rule markers:** ⚠ controller on every oracle step; ⚠ ask-user on Tasks 5 and 11; parcel ritual on every byte-emitting change; verify-branch-before-commit throughout; merge only at Task 12.
- **Placeholder scan:** none; every code step has code or an exact anchor + expected observable.
- **Consistency:** names match across tasks (`ZX0R_Start`/`ZX0R_Decompress__end`, `PageIn_*`/`PageIn_Flush`, `PageCache_*`, `Page_Table`/`Page_Frames`, `Dbg_PageIn_Preempts/Flushes/Resumes`, `ART_STAGING_BUFFER_SIZE`, `STRESS_EVICT`/`STRESS_ART`).
</content>
</invoke>
