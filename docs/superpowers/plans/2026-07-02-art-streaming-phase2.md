# Art Streaming Phase 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the fully-resident act art pool into a VRAM residency cache streaming small ZX0/raw pages in main-loop idle time via a supervisor-bookmark resumable decoder — level art capped by ROM, not VRAM.

**Architecture:** Three phases on one branch. P2a (Tasks 2-4): stack-flat resumable ZX0 decoder + VBlank bookmark preemption + page-in dispatcher, proven on the existing 256-tile pages. P2b (Tasks 5-7): format cutover (64-tile ZX0/raw pages, manifest v2, logical indices + local→global tables) then the residency cache (page frames, refcount-pin + LRU, patch-at-cache-entry, demand stall, eviction). P2c (Tasks 8-12): Vectorman dual-cap DMA, B&R per-act art budget word, camera-gate degradation, stress + acceptance, ROM budget gate, docs + merge. Spec: `docs/superpowers/specs/2026-07-02-art-streaming-phase2-design.md` (APPROVED).

**Tech Stack:** 68000 assembly (AS, `engine/`), Python toolchain (`tools/ojz_strip_gen.py` — **daemon-watched**), oracle emulator MCP, salvador ZX0 packer.

**Standing rules for every task:**
- Step 1 of every task is research (per-project convention): read the cited code fresh — line numbers below are anchors as of `2b8c207` and WILL drift.
- Build: `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh` (a plain build proves nothing about DEBUG asserts/self-tests). Runtime-boot in oracle after ANY ram.asm change (AS does not auto-align; an odd `ds.b` crashes the *next* word field at runtime while the build stays green — pad to even).
- **`tools/ojz_strip_gen.py` and `games/sonic4/data/editor/ojz/` are daemon-watched (auto-committed as the user ~60s after edit). ASK THE USER before each task that edits them; never edit autonomously; never `--amend` near them.**
- `git add` exact paths only. Commit per green task. Branch: `feat/art-streaming-p2` off master; merge to master only at Task 12.
- Verification is oracle-observed behavior (screenshots during MOTION, `Lag_Frame_Count`, VRAM reads), never build-success alone. Oracle symbols go stale after `reload_rom` — cross-check addresses against fresh `s4.lst`.

---

### Task 1: Branch + baseline

**Files:** none created (scratchpad numbers only)

- [ ] **Step 1: Research.** Read the spec end-to-end. Read `engine/level/load_art.asm` (all 92 lines), `engine/system/vblank.asm:1-60,167-184`, `engine/system/game_loop.asm:1-20`, `engine/compression/zx0_decompress.asm` (all), `constants.asm:118-140,326-370`, `ram.asm:10-43` — these are the surfaces P2a touches.
- [ ] **Step 2: Branch.** `git checkout -b feat/art-streaming-p2` from a clean master.
- [ ] **Step 3: Baseline.** Build; load in oracle; free-fly a full OJZ circuit at max scroll; record to scratchpad: `Lag_Frame_Count` over a 600-frame max-horizontal run, a mid-scroll screenshot, and the profiler idle % (`emulator_get_profiler`). These are the no-regression references for Tasks 4/7/11.

### Task 2: P2a — Resumable stack-flat ZX0 decoder + equivalence self-test

**Files:**
- Create: `engine/compression/zx0_resume.asm`
- Modify: `games/sonic4/main.asm` (include, next to the existing compression includes)
- Modify: `engine/debug/` self-test bank (find the compression golden-test done at DEBUG boot — grep `golden` / `SelfTest`)

- [ ] **Step 1: Research.** Read `zx0_decompress.asm` again instruction-by-instruction; read the S3K resumable-decoder precedent notes in the spec §3 (registers-only state, RAM/register description field instead of stack — sonic3k.asm:2844-2953 if deeper detail is wanted). Read how the existing DEBUG compression self-test is invoked at boot (grep `SOUND`-free self-test path) and mirror its structure. Read `CODING_CONVENTIONS.md`.
- [ ] **Step 2: Write the decoder.** The blocking decoder with (a) the `bsr` elias reads inlined (three sites), (b) no stack use anywhere between `ZX0R_Start` and `ZX0R_End` (no prologue movem — d0-d2/a0-a3 are caller-owned), (c) continuation in a3. This is the complete routine:

```asm
; ZX0R — resumable stack-flat ZX0 decompressor (art-streaming Phase 2).
; CONTRACT (the VBlank bookmark depends on every clause):
;   - NO stack access between ZX0R_Start and ZX0R_End (no bsr/jsr/push).
;   - ALL state lives in d0-d2/a0-a2 + CCR at every instruction.
;   - NO VDP / Z80 / shared-RAM access; writes go to the staging buffer only.
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

  Note the elias inlining is a *restructure*, not a transcription — verify the control flow against the original's `.get_elias`/`.elias_loop`/`.elias_bt` entry points during review (the `.len_elias` tail is the `bsr.s .elias_bt` case: one data-bit read THEN the loop).
- [ ] **Step 3: Equivalence self-test (DEBUG boot).** Alongside the existing golden self-test: for each act pool page (walk `OJZ_Act_Pool_PageTable`), decode with `ZX0_Decompress` into buffer A and `ZX0R_Decompress` into buffer B (reuse `Art_Staging_Buffer` + the tile-cache RAM the same way the init loader does — this runs before the cache goes live), `RaiseError` on any byte mismatch or length mismatch. This is blocking use (interrupts still off at self-test time) — preemption is Task 3's test.
- [ ] **Step 4: Build + boot.** DEBUG build green; oracle boot reaches gameplay (self-test passed = no error screen). OJZ renders as baseline.
- [ ] **Step 5: Commit.** `feat(compression): resumable stack-flat ZX0 decoder + boot equivalence self-test (P2a)`

### Task 3: P2a — VBlank bookmark: preempt, bank, resume

**Files:**
- Create: `engine/level/page_in.asm` (dispatcher skeleton: suspend/resume + a single-request path this task)
- Modify: `engine/system/vblank.asm:8-29` (`VBlank_Handler`), `engine/system/vblank.asm:167-184` (`VSync_Wait`)
- Modify: `ram.asm` (PageIn state block), `constants.asm` (offsets), `games/sonic4/main.asm` (include)

- [ ] **Step 1: Research.** Re-read `VBlank_Handler` — confirm the entry is still exactly `movem.l d0-a6,-(sp)` then the ready test (the stacked-PC offset below is derived from it). Read `VSync_Wait` and confirm the `VBlank_Ready` set happens before the spin. Read spec §3's nested-interrupt caveat. Check the HInt vector target in `games/sonic4/main.asm` (if HInt is a bare `rte` today, the nested-preempt window is negligible; note what you find in the commit message).
- [ ] **Step 2: RAM + constants.**

```asm
; ram.asm (upper block; keep even)
PageIn_Saved_Regs:      ds.l 7          ; d0-d2/a0-a3 banked at preemption
PageIn_Saved_PC:        ds.l 1
PageIn_Saved_SR:        ds.w 1
PageIn_InFlight:        ds.b 1          ; nonzero while ZX0R may be on the stack frame
PageIn_Suspended:       ds.b 1          ; nonzero = banked context awaits resume
; constants.asm
VBH_STACKED_PC = 15*4+2                 ; VBlank_Handler: movem.l d0-a6 (60) + SR word
```

- [ ] **Step 3: The hook in `VBlank_Handler`** — insert immediately after the `movem.l d0-a6,-(sp)`:

```asm
        tst.b   (PageIn_InFlight).w     ; art decode possibly interrupted?
        beq.s   .no_decode
        move.l  VBH_STACKED_PC(sp), d0  ; PC the rte will return to
        cmpi.l  #ZX0R_Start, d0
        blo.s   .no_decode
        cmpi.l  #ZX0R_End, d0
        bhs.s   .no_decode
        move.l  d0, (PageIn_Saved_PC).w
        move.l  #PageIn_BankRegs, VBH_STACKED_PC(sp)
    ifdef __DEBUG__
        addq.w  #1, (Dbg_PageIn_Preempts).w
    endif
.no_decode:
```

- [ ] **Step 4: Bank + resume in `page_in.asm`:**

```asm
; Landed by the hijacked rte: registers are the decoder's live values
; (restored by VBlank_Handler's movem pop), SR/CCR is the decoder's.
; SP is at PageIn_Process depth -> rts returns to VSync_Wait.
PageIn_BankRegs:
        move.w  sr, (PageIn_Saved_SR).w
        movem.l d0-d2/a0-a3, (PageIn_Saved_Regs).w
        st.b    (PageIn_Suspended).w
        rts

PageIn_Process:                          ; bsr'd from VSync_Wait each frame
        tst.b   (PageIn_Suspended).w
        beq.s   .fresh
        clr.b   (PageIn_Suspended).w
        movem.l (PageIn_Saved_Regs).w, d0-d2/a0-a3
        move.l  (PageIn_Saved_PC).w, -(sp)
        move.w  (PageIn_Saved_SR).w, -(sp)
        rte                              ; straight back into the decoder loop
.fresh:
        ; Task 3: single hardwired test request (Task 4 replaces with the queue):
        ; if a test-page request is pending, set up a0/a1, lea .after(pc),a3,
        ; st PageIn_InFlight, and FALL THROUGH (jmp) into ZX0R_Decompress.
        rts
.after:
        clr.b   (PageIn_InFlight).w
        ; Task 3: set a done flag the test reads. Task 4: mark request complete + DMA.
        rts
```

  `PageIn_Process` is called from `VSync_Wait` after `VBlank_Ready` is set, before the spin (so a mid-decode VBlank dispatches `VInt_Level`, not `VInt_Lag`):

```asm
VSync_Wait:
        ...                              ; existing: clear stale flag
        move.b  #1, (VBlank_Ready).w     ; existing
        bsr.w   PageIn_Process           ; NEW: idle-time decode slice
.wait:  ...                              ; existing spin on VBlank_Flag
```

- [ ] **Step 5: Preemption test (DEBUG, temporary scaffold — removed in Task 4).** After boot with display ON: queue the largest act pool page as the test request, decode it via the dispatcher across frames into a spare buffer, then compare against a blocking `ZX0_Decompress` of the same page. Assert: outputs byte-identical AND `Dbg_PageIn_Preempts > 0` (an 8KB page ≈ 100K+ cycles cannot fit one frame's idle — if the counter is 0 the hook never fired; investigate before proceeding). Run 3 consecutive cycles to prove suspend/resume re-entry.
- [ ] **Step 6: Build + oracle.** Green; boot; the test passes (no RaiseError); gameplay unaffected; `Lag_Frame_Count` at rest = 0.
- [ ] **Step 7: Commit.** `feat(level): VBlank bookmark preemption for the resumable art decoder (P2a)`

### Task 4: P2a — Page-in request queue + init-path routing

**Files:**
- Modify: `engine/level/page_in.asm` (real FIFO queue), `engine/level/load_art.asm:56-92` (`Level_LoadArt` drives the queue), `ram.asm`
- Delete: the Task-3 test scaffold

- [ ] **Step 1: Research.** Read `Level_LoadArt` and `Art_Decompress` (load_art.asm:23-29) as they stand; read the DMA queue enqueue API (`engine/system/dma_queue.asm:38-57`) and `QueueDMA_Critical` usage at load_art.asm:79. Read S3K's queue shape for calibration (spec §11 cites; 4-deep FIFO, head-first, retry-when-full).
- [ ] **Step 2: Request queue.** 8-entry FIFO in RAM, entry = `{page_id.w, flags.b (PGRQ_DEMAND bit), pad.b}`; enqueue routine returns carry when full (caller retries next frame — the B&R rollback idiom); `PageIn_Process .fresh` pops the head, resolves page→source ptr + dest VRAM via the manifest table, and either falls into `ZX0R_Decompress` (ZX0 form) or enqueues a direct ROM→VRAM DMA (raw form — no staging, no decode). On `.after`: enqueue staging→VRAM DMA at Important priority, set `PageIn_Staging_Busy`; a new decode does not start while `PageIn_Staging_Busy` is set; clear it in `VInt_Level` right after `Process_DMA_Important` when the Important queue emptied. Demand-priority entries are dequeued before prefetch entries (two head pointers or a simple two-pass scan — pick and comment).
- [ ] **Step 3: Route init through it.** `Level_LoadArt` becomes: for each page, enqueue request + `bsr VSync_Wait` in a loop until all pages resident (display is off — Critical/Important drains run in the extended blanking, same as today). Delete the direct `Art_Decompress`-loop body. Keep `Art_Decompress` itself only if other callers remain (grep — the block tier uses `S4LZ_DecompressDict`, not this); if none remain, delete it and `ZX0_Decompress` stays only as the self-test oracle for ZX0R (comment it as such).
- [ ] **Step 4: Build + oracle.** Green build; boot; OJZ renders identical to Task 1 baseline (screenshot compare); full max-scroll circuit clean; `Dbg_PageIn_Preempts` reads 0 during normal play (nothing streams mid-game yet). Init self-tests still pass.
- [ ] **Step 5: Commit.** `feat(level): page-in request queue; level init rides the streaming path (P2a complete)`

### Task 5: P2b — Format cutover: 64-tile ZX0/raw pages, manifest v2, logical indices

**⚠ This task edits `tools/ojz_strip_gen.py` — ASK THE USER before starting (daemon-watched).**

**Files:**
- Modify: `tools/ojz_strip_gen.py` (Pass 5 remap :1280-1294, Pass 6 page emission :1320-1324, manifest :1364-1372), `build.sh:75-111` (per-page compression + form election)
- Modify: `engine/level/load_art.asm`, `engine/level/page_in.asm`, `constants.asm:133-134`
- Modify: `engine/level/tile_cache.asm` (translation at block decode — see Step 4)
- Test: `tools/` pytest (extend the generator tests)

- [ ] **Step 1: Research.** Read Pass 5/6 + manifest emission in the generator AND the consuming engine sites; read `remap_nametable_word` to see exactly which bits carry the tile index vs palette/priority/flip; read the S4LZ block-dict emission (`sec_block_dicts.asm`) to choose where the per-section local→global table rides. Confirm with the user the daemon coordination.
- [ ] **Step 2: Generator v2.** (a) Page size 256→`ART_POOL_PAGE_TILES = 64` (spatial order preserved — pages are consecutive 64-index runs). (b) Per-section **local→global tables**: collect each section's referenced global pool indices into a ≤2047-entry local palette; rewrite block nametable words to local indices (bits 0-10; palette/priority/flip untouched); emit the table with the section's dict data. Build-fails if a section references >2047 distinct tiles. (c) Manifest v2 per page: `dc.l source`, `dc.w tiles`, `dc.b form (0=zx0,1=raw), flags (bit0=pinned)`; pinned marking: pages whose tiles are referenced by ≥ PIN_SECTION_FRACTION of sections (start 75%, tunable) — page 0 always pinned (blank tile 0 lives there). (d) Raw election in `build.sh`: compress each page; keep `.zx0` only if it saves ≥ `RAW_ELECT_MIN` (10%) else emit `.raw` and mark the form. (e) All `POOL_TILE_CEILING`-style pool-size asserts become *page-count* + residency asserts (`pages ≤ PAGE_TABLE_MAX = 256`).
- [ ] **Step 3: Engine consumption — identity residency.** Page frames exist in name only this task: page N loads to VRAM slot `N*64` exactly as today (OJZ's 10 pages ≤ 15 frames). `page_in.asm` reads manifest v2. Staging shrinks: `ART_STAGING_BUFFER_SIZE = 64*32 = 2048`; keep it a named buffer in lower RAM (the init-only `Art_Staging_Buffer = Tile_Cache_Nametable` alias at ram.asm:31 is DELETED — steady-state streaming can't overlay live cache RAM).
- [ ] **Step 4: Translation at block decode.** In `TileCache_DecompressBlock`'s consumers (`TileCache_CopyBlockColumn` :293-307 / `TileCache_FillRow` :1130-1131): each staged word's local index (bits 0-10) is translated global via the section's local→global table before it lands in `Tile_Cache_Nametable`. This task the "patch" is identity (global == VRAM slot), so translate-then-write reproduces today's output exactly. Keep flip/pal/pri bits intact (mask, or, write).
- [ ] **Step 5: pytest.** Extend the generator tests: local tables round-trip (word→local→global == original global); page split covers the pool exactly; a fabricated >2048-tile pool passes generation with >32 pages (the unbounded-index unit proof); a fabricated section referencing >2047 distinct tiles FAILS loudly.
- [ ] **Step 6: Build + oracle.** Green; boot; OJZ pixel-identical to baseline (screenshot at rest + during a max-scroll circuit — translate bugs show as wrong tiles instantly); collision unaffected (drive a terrain circuit). `python3 -m pytest tools/ -q` green.
- [ ] **Step 7: Commit.** `feat(art): 64-tile ZX0/raw pool pages, manifest v2, logical indices + per-section translation (P2b cutover)`

### Task 6: P2b — Residency cache: page table, frames, refcount, LRU, patch

**Files:**
- Create: `engine/level/page_cache.asm`
- Modify: `engine/level/tile_cache.asm` (the Task-5 translate sites gain patch + refcount), `engine/level/page_in.asm` (dest = allocated frame), `ram.asm`, `constants.asm`, `structs.asm`

- [ ] **Step 1: Research.** Re-read the Task-5 translate sites as landed; read the LRU-list shape in the spec §5 and van Waveren's free/LRU/locked tri-list (spec §11); read `TileCache_FillColumn/FillRow`'s overwrite behavior — where OLD cache words get replaced (those are the decrement sites).
- [ ] **Step 2: Structures.**

```asm
; constants.asm
PAGE_FRAMES        = 15                 ; 960-tile FG region / 64
PAGE_TABLE_MAX     = 256                ; max pages per act (assert in generator)
PAGE_NOT_RESIDENT  = $FF
; structs.asm
        struct PageFrame
pf_page         ds.w 1                  ; resident page id, or -1
pf_refcount     ds.w 1                  ; cache words referencing this page
pf_lru_prev     ds.b 1
pf_lru_next     ds.b 1
pf_flags        ds.b 1                  ; bit0 = pinned
pf_pad          ds.b 1
        endstruct
; ram.asm
Page_Table:     ds.b PAGE_TABLE_MAX     ; page id -> frame idx / PAGE_NOT_RESIDENT
Page_Frames:    ds.b PAGE_FRAMES*PageFrame_len
```

- [ ] **Step 3: `page_cache.asm` API** (each a documented routine): `PageCache_Init` (frames free, pinned pages loaded, table built), `PageCache_Lookup` (page→frame or NOT_RESIDENT, ~10 cyc), `PageCache_Request` (enqueue demand/prefetch page-in if not resident + not queued), `PageCache_AllocFrame` (free list, else LRU tail with refcount 0 and !pinned; NO victim with refcount>0 — `RaiseError` in DEBUG if none available: that is a thrash bug, not a policy), `PageCache_Ref`/`PageCache_Unref` (word-granular inc/dec + LRU touch on 0→1 / move-to-tail on 1→0).
- [ ] **Step 4: Patch + refcount at cache entry.** The Task-5 translate sites become: local→global→`Page_Table` lookup→physical slot = `frame*64 + (global & 63)`; write patched word; `PageCache_Ref(page)`. Every cache word being *overwritten* first passes its old physical word back through frame→page (`slot>>6` → `Page_Frames[..].pf_page`) for `PageCache_Unref`. Blank/zero words skip both. If the needed page is NOT resident: `PageCache_Request(demand)`, store a resume key, and return "partial" through the existing keyed-resume fill contract (`tile_cache.asm:976-980,1161-1168` is the pattern) — the fill retries next frame until the page lands.
- [ ] **Step 5: Page-in destination = frame.** `page_in.asm` asks `PageCache_AllocFrame` at dequeue time; DMA dest = `frame*64*32`. On completion, update `Page_Table` + frame fields.
- [ ] **Step 6: DEBUG audit assert.** A DEBUG-boot + on-demand routine: walk the whole `Tile_Cache_Nametable`, recompute per-frame refcounts from scratch, compare to `pf_refcount` — `RaiseError` on mismatch. Run it after init and (hotkey or every N frames in DEBUG) during play.
- [ ] **Step 7: Build + oracle.** OJZ still fully resident (10 pages ≤ 15 frames → no eviction yet): pixel-identical baseline, audit assert clean over a full circuit, `Lag_Frame_Count` regression ≤ baseline + 0 (refcount cost is the watch item — if lag appears, profile before optimizing).
- [ ] **Step 8: Commit.** `feat(level): page-frame residency cache — table, refcount, LRU, patch-at-entry (P2b)`

### Task 7: P2b — Eviction live + forced-eviction soak

**Files:**
- Modify: `engine/level/page_cache.asm`, `constants.asm` (DEBUG clamp), `engine/level/page_in.asm` (prefetch)

- [ ] **Step 1: Research.** Read the leading-edge prefetch that exists for blocks (`tile_cache.asm:809-891`, `Cache_Prev_Cam_Row` diffing) — the page prefetch rides the same direction signals.
- [ ] **Step 2: Prefetch.** When the fill's leading edge advances, look one block-column/row further ahead: collect that strip's referenced pages (via the same local→global path) and `PageCache_Request(prefetch)` any non-resident ones. Bounded: ≤2 requests enqueued per frame.
- [ ] **Step 3: Forced eviction.** `ifdef __DEBUG__: PAGE_FRAMES_CLAMP = 6` (OJZ's 10 pages can no longer all be resident) behind a build flag `STRESS_EVICT=1` in build.sh. With it on: full OJZ circuits force continuous evict/reload traffic through every code path.
- [ ] **Step 4: Soak.** STRESS_EVICT build, oracle: 3+ full max-scroll circuits both directions + vertical + diagonal. Gates: zero wrong-tile frames (screenshot spot checks DURING motion), audit assert clean throughout, no deadlock in the demand-stall path (fill always completes once its page lands), `Dbg_PageIn_Preempts` climbing (decodes are being sliced), lag bounded (this is a synthetic overload — clamp-frame counts get recorded, not gated, until Task 10 adds the camera gate).
- [ ] **Step 5: Commit.** `feat(level): LRU eviction + page prefetch live; forced-eviction soak clean (P2b complete)`

### Task 8: P2c — Vectorman dual cap on the DMA queue

**Files:**
- Modify: `engine/system/dma_queue.asm:57-133` (`QueueDMATransfer`), `ram.asm`, `constants.asm`, `engine/system/vblank.asm` (per-frame reset)

- [ ] **Step 1: Research.** Read `QueueDMATransfer`'s carry-on-full contract and existing callers' failure handling; read the Vectorman mechanism (spec §11: enqueue-side running byte total + entry cap, atomic per-request rollback, retry next frame).
- [ ] **Step 2: Implement.** `DMA_Enq_Bytes_Frame` word, reset in `VInt_Level` beside the existing `DMA_Budget_Remaining` reset (vblank.asm:69 area); `QueueDMATransfer` adds the transfer's byte size; over `DMA_ENQ_BYTE_CAP` (start: 12288 — above the drain budget so it only catches runaway enqueue storms) → roll back the size add, return carry exactly like queue-full. The 128KB-split path must roll back BOTH halves or neither (split entries commit atomically).
- [ ] **Step 3: Verify + commit.** Green build, baseline circuit unaffected (cap never hits in normal play — DEBUG counter proves it stayed 0), STRESS_EVICT soak unaffected. Commit: `feat(system): enqueue-side dual cap (entries+bytes) on the DMA queue (P2c)`.

### Task 9: P2c — B&R per-act art budget word

**Files:**
- Modify: `structs.asm` (Act struct), `games/sonic4/data/levels/ojz/act1/act_descriptor.asm`, `engine/level/page_in.asm`, `ram.asm`, `engine/system/vblank.asm`

- [ ] **Step 1: Research.** Read the Act struct (`structs.asm` — `Act_len = $22` per DEFERRED_WORK) and the descriptor consumer in level init; note the **editor-exporter drift warning** (DEFERRED_WORK §8 entry: `data/editor/ojz/act1/export/act_descriptor.asm` emits a STALE format and is daemon-watched — do NOT touch it; only the hand-maintained `data/levels/.../act_descriptor.asm` + struct change here, and add the size assert the DEFERRED entry suggests if absent).
- [ ] **Step 2: Implement.** `act_art_budget ds.w 1` appended to the Act struct (+ pad to keep `Act_len` even; update the length constant + any assert); OJZ value: 4096 (two pages/frame ceiling). Level init copies it to `Act_Art_Budget` RAM; `VInt_Level` reloads `Art_Budget_Remaining` from it each frame; `page_in.asm` charges each page's DMA bytes against it and defers further page-ins to the next frame when exhausted (the request stays queued — nothing is dropped).
- [ ] **Step 3: Verify + commit.** Baseline + STRESS_EVICT circuits clean; DEBUG counter shows deferrals only under stress. Commit: `feat(level): per-act art streaming budget word (B&R pattern) (P2c)`.

### Task 10: P2c — Camera soft-clamp degradation

**Files:**
- Modify: `engine/level/camera.asm`, `engine/level/tile_cache.asm` (demand-stall depth signal), `ram.asm`

- [ ] **Step 1: Research.** Read `Camera_Update`'s per-axis step clamp (`CAM_MAX_X_STEP`/`CAM_MAX_Y_STEP`, constants.asm:402) and where the fill's stall state lives (Task 6's resume key).
- [ ] **Step 2: Implement.** Signal: a demand-stalled fill whose stalled edge is within `CLAMP_MARGIN_TILES = 4` block-columns/rows of the visible screen edge sets `Camera_Art_Hold` (axis-tagged). `Camera_Update` treats a held axis' max step as 0 (full classic S3K-gate feel: the camera waits; the player logic is untouched). Cleared the frame the stall resolves. DEBUG: `Dbg_Cam_Clamp_Frames` counter.
- [ ] **Step 3: Verify + commit.** Normal build: counter stays 0 through all circuits (prefetch does its job). STRESS_EVICT: clamps engage at worst-case seams instead of showing unfetched art — screenshot-verify during motion that no wrong/blank FG tile is ever visible. Commit: `feat(level): camera soft-clamp on art demand-miss (honorable degradation) (P2c)`.

### Task 11: P2c — Stress fixture + acceptance matrix

**⚠ Generator flag work — coordinate with the user (daemon-watched file).**

**Files:**
- Modify: `tools/ojz_strip_gen.py` (`--stress-uniquify N` flag), `build.sh` (`STRESS_ART=1` plumbs it)
- Test: `tools/` pytest

- [ ] **Step 1: Research.** Confirm with the user; read the pool-emission pass once more.
- [ ] **Step 2: `--stress-uniquify N`.** Post-dedup, clone existing pool tiles with a per-clone pixel perturbation (e.g. XOR a counter into one row) and re-point a spread of block references at the clones until the pool reaches N distinct tiles (default 2600 — crosses the 2048 index line and exceeds 15 frames ≈ 4×). Deterministic (seeded by index, no RNG). pytest: N=2600 generation succeeds, >40 pages, local tables valid.
- [ ] **Step 3: Acceptance matrix (the spec's P2c gate), STRESS_ART=1 build, oracle:**
  - sustained max scroll H, V, and DIAGONAL, 600+ frames each, both directions;
  - zero visible pop-in / wrong tiles (screenshots during motion at fixed intervals);
  - `Lag_Frame_Count` per run recorded; diagonal target: no worse than the Task 1 baseline + the audit's known ~76% diagonal condition — art streaming must not measurably deepen it (compare, record numbers);
  - `Dbg_Cam_Clamp_Frames` bounded (record; expect brief engagements at worst seams only);
  - refcount audit assert clean after every run.
- [ ] **Step 4: Commit.** `feat(tools): stress-uniquify fixture; Phase 2 acceptance matrix passed (P2c)` — include the numbers table in the commit message.

### Task 12: ROM budget gate, docs, merge

**Files:**
- Modify: `build.sh` (report + gate), `docs/ENGINE_ARCHITECTURE.md` (§9.7 rewrite + §2 residency section), `docs/DEFERRED_WORK.md`, `CLAUDE.md` (compression line), `docs/superpowers/2026-07-02-design-week-queue.md` (log)

- [ ] **Step 1: ROM report + gate.** `build.sh` prints per-act: raw pool bytes, stored bytes per form, page count, ratio; warns above `ART_ROM_SOFT_KB` and fails above `ART_ROM_HARD_KB` (per-act overridable vars; OJZ defaults 24/64 KB — generous now, tightened when real acts exist).
- [ ] **Step 2: ARCH §9.7 rewrite.** Replace the user-mode design with the supervisor-bookmark mechanism as shipped (contract, PC-range hook, costs), with a short "user-mode variant REJECTED" record (spec §3 rationale). Rewrite the §2 art sections to describe the residency cache as *the* design (clean-not-bolted-on: the doc reads as if designed this way). Sweep for stale claims: "fully resident", "loaded once at init", `ART_POOL_PAGE_TILES=256`.
- [ ] **Step 3: DEFERRED_WORK closeout.** Mark the Phase-2 amendments entry RESOLVED (pointing here); delete/close the `Decomp_Buffer` alias entries this work retired; add follow-ups discovered en route.
- [ ] **Step 4: Scaffold sweep.** Confirm deleted: Task-3 test scaffold, `Art_Staging_Buffer` alias, `Art_Decompress` (if Task 4 orphaned it), old 256-tile constants, any `if old else new` remnants. `grep -rn "ART_POOL_PAGE_TILES\|Decomp_Buffer\|Art_Decompress" engine/ games/ tools/ *.asm` returns only current-design hits.
- [ ] **Step 5: Final gates + merge.** Full DEBUG build + plain build both green; pytest green; one last baseline circuit + STRESS_EVICT soak + acceptance spot-check; then merge `feat/art-streaming-p2` → master (FF or merge commit per repo habit), and update the design-week queue log.

---

## Self-review (done at write time)

- **Spec coverage:** §3 mechanism→T2-3; §4 formats/election/init-unification→T5+T4; §5 model/residency/stall→T5-7; §6 pipeline/budgets/degradation→T4,8,9,10; §7 build+ROM gate→T5,11,12; §8 phasing→task order; §9 verification→T2/3 self-tests, T6 audit, T7 soak, T11 matrix; §10 risks→T7 deadlock soak, T11 page-size numbers (32/128 sweep is a follow-up knob — the fixture + report make it a 10-minute experiment), T3 nested-interrupt note+counter.
- **Placeholder scan:** none; every code step has code or an exact anchor + expected observable.
- **Consistency:** names used across tasks match (`ZX0R_Start/End`, `PageIn_*`, `PageCache_*`, `Page_Table`/`Page_Frames`, `ART_STAGING_BUFFER_SIZE`, `STRESS_EVICT`/`STRESS_ART`).
