# Supervisor VBlank Bookmark — implementation sketch against the current tree (2026-08-06)

**Status:** design-prep note, read-only survey — no code changed. Companion to the
§9.7 decision memo (`2026-08-06-97-decision-memo.md`), the ARCH §9.7 rewrite
proposal (`2026-08-06-arch-97-rewrite-proposal.md`), and the Phase-2 plan
re-anchor addendum (`plans/2026-08-06-art-streaming-phase2-reanchor-addendum.md`).
**Sources:** corpus note `2026-08-05-deferred-work-research.md`; Phase-2 spec §3
(`specs/2026-07-02-art-streaming-phase2-design.md`); live code as of master
`4974bf3` — `engine/system/vblank.emp`, `engine/system/game_loop.emp`,
`engine/compression/zx0.emp`, `engine/system/hblank.emp`, `engine/ram.emp`.

The banked plan (Tasks 2–4) drafted this mechanism against the pre-Sigil tree.
This sketch re-derives it against the `.emp` tree, verifies the three
load-bearing invariants hold structurally in Aeon's actual VInt shape, and specs
what the mechanism needs from the Sigil contract system (§6 — the ask for the
sigil owner; aeon does not implement that side).

---

## 1. The resumable region: what the decoder must satisfy

The shipped blocking decoder (`engine/compression/zx0.emp`, `ZX0_Decompress`,
Marty's unzx0_68000) violates the resumable contract in exactly two ways, both
already identified by the plan and confirmed against the live source:

1. **Stack use:** three `jbsr` sites into the internal `.get_elias` /
   `.elias_loop` / `.elias_bt` subroutine (zx0.emp:65, :75, :90, :100), plus the
   `movem.l a2/d2,-(sp)` prologue/epilogue (:59, :120). The resumable variant
   inlines the elias reader at all sites (the plan's Task-2 listing is a correct
   restructure of this control flow — `.len_elias` is the `.elias_bt` tail: one
   data-bit read, then the loop) and takes caller-owned d0–d2/a0–a2 with no
   prologue.
2. **`rts` exit:** the resumable variant exits `jmp (a3)` to a caller-loaded
   continuation — never touching sp — so an abort/cancel is just "don't resume"
   and resume works from any interrupt depth.

**Register-resident state, verified against the algorithm:** at every
instruction the live state is exactly a0 (src), a1 (dst), d0 (elias
accumulator), d1 (bit queue), d2 (rep-offset), a2 (backref cursor), plus
CCR carry/X — the elias loops carry a live X flag *between* instructions
(`add.b d1,d1` → `addx`). a3 (continuation) is never touched by the body.
The interrupt frame preserves CCR in the stacked SR, and the bookmark
banks/restores that SR word, so the mid-elias X flag survives preemption.
`move sr,<ea>` is unprivileged on the 68000 (S.C.E.'s `rtr` observation from
the corpus); we run supervisor anyway, so even that latitude is unneeded.

**Bookmark record** (upper-RAM, engine-owned): 7 longs (d0–d2/a0–a3) + PC long
+ SR word = **34 bytes**, between S.C.E.'s 26 and S3K's 46. Plus two byte flags
(`PageIn_InFlight`, `PageIn_Suspended`) and DEBUG counters.

**The other two contract clauses** hold by construction and must be stated in
the proc's header (and, once Sigil support lands, enforced — §6):
- no VDP, no Z80, no shared-RAM writes inside the range — the decode target is
  the private staging buffer; publication is the *dispatcher's* act after
  completion (single aligned write + DMA enqueue, atomic wrt interrupts);
- one contiguous PC range `[ZX0R_Start, ZX0R_End)`, exported as link symbols
  the VBlank hook compiles against.

## 2. The VInt hook — placement and the structural safety proofs

**Where:** `VBlank_Handler` (vblank.emp:40–58). Entry is still exactly
`movem.l d0-a6,-(sp)` (:41), so the stacked exception frame sits at a known
offset: SR word at `60(sp)`, return PC at `62(sp)` (`VBH_STACKED_PC = 15*4+2`
— the plan's constant survives verbatim). The hook goes immediately after the
movem, before the `VBlank_Ready` test:

```
tst.b InFlight → beq .no    (~14 cyc on every VBlank when idle)
PC = 62(sp); range-check against [ZX0R_Start, ZX0R_End); outside → .no
save PC to PageIn_Saved_PC; rewrite 62(sp) := PageIn_BankRegs
```

The *effect* fires at the handler's `rte` — after VInt_Level's entire pipeline,
the debug mirror, and the movem restore — so "bookmark is the V-int's final
act" (corpus invariant 3) holds even though the *check* runs at entry. The
movem restore re-materializes the decoder's registers; the hijacked `rte` pops
the decoder's SR (CCR intact) and lands at `PageIn_BankRegs`, which banks
d0–d2/a0–a3 + SR (its first instruction is `move.w sr,…` — nothing may touch
flags before it), sets `PageIn_Suspended`, and `rts`. The stack at that moment
is VSync_Wait's caller frame at `PageIn_Process` depth, so the `rts` returns
into `VSync_Wait`, whose `.wait` spin falls through immediately (VInt_Level
already set `VBlank_Flag`) — the next main-loop tick starts on time.

**Proof: the lag path can never bookmark.** `VInt_Lag` dispatches only when
`VBlank_Ready = 0` (:43). The decoder can only be executing inside
`PageIn_Process`, which is called from `VSync_Wait` *after* the
`with ints_off { flag-clear; Ready := 1 }` pair (:290–293). So "PC in decoder
range" implies `Ready = 1` implies the VInt_Level path — the same structural
impossibility the corpus traced in S3K, falling out of Aeon's existing
Ready/Flag protocol with no added checks. (A *suspended* decode during a lag
frame is fine: `InFlight = 1` but the interrupted PC is main-loop code, outside
the range — no bookmark, banked context untouched.)

**Proof: a mid-decode VInt_Level is safe.** On a decode-live frame the main
loop is parked, so Plane_Buffer is complete and drained normally; the decoder
owns no shared state (clause 3); DMA queues see nothing from the decode until
the dispatcher publishes. The one new consumer-side rule: the staging buffer
must not be re-targeted while `InFlight`/`Suspended` (the dispatcher's
`Staging_Busy` handshake with the Important drain, exactly as the plan's
Task 4 specs).

**Nested interrupts:** HBlank handlers are contract-enforced
interrupt-transparent (`hblank.emp` — full save/restore, `rte`-terminated,
`clobbers()` CPU-state-only), so an HInt landing inside the decoder range or
inside `PageIn_BankRegs` is invisible. Only IRQ6 carries the hook. The
manufactured-resume sequence (push SR, push PC, `rte`) is likewise
interrupt-safe: a VBlank landing between the pushes sees a PC *outside* the
decoder range (it's in `PageIn_Process`), stays transparent, and the sequence
completes after its `rte`.

**Resume = spawn = one code path** (Ristar's manufactured-bookmark trick, kept
by the plan): a fresh decode is started by loading a0/a1/a3 and falling into
`ZX0R_Decompress`; a suspended one is re-entered by manufacturing the frame
from the banked SR/PC and `rte`. Cancel is a third trivial path (§4).

## 3. VSync_Wait integration and the contract ripple

Insertion point (vblank.emp:274–302): after the `with ints_off` bracket,
before `.wait`. Two constraints discovered against the live code:

1. **The atomic pair must not be split.** The flag-clear/Ready-set bracket
   (:290–293) exists to close a torn-drain hazard; `PageIn_Process` goes
   strictly after it. Decode before Ready-set would break the §2 lag proof.
2. **`VSync_Wait`'s license widens — and every caller re-verifies.** Today it
   is `clobbers(d0) preserves(sr.mask)`. With the decode slice inside, its
   clobber set becomes the PageIn/decoder union (d0–d2/a0–a3 at minimum;
   `PageIn_Process` must add nothing beyond it, and **must not push anything
   before falling into the decoder** — a prologue movem would be popped as a
   "return address" by `PageIn_BankRegs`'s rts). Known affected caller:
   `Level_LoadArt` (load_art.emp:103 — folds "VSync_Wait d0" into its license
   and keeps a6/a4/d4 live across the retry loop; a4–a6 stay outside the
   decoder set, so it survives, but the contract text must be redone). Sigil
   turns this ripple into build errors until reconciled — that is a feature;
   budget a contract-surgery step for it in the re-anchored plan (the addendum
   flags it on Task 3).

`GameLoop` (game_loop.emp:28) already clobbers everything; no ripple there.

## 4. Cancel / flush (the gap the corpus flagged in spec §6)

The Unity-incremental-GC lesson: speculative work needs an explicit
invalidation path. Concrete design, engine-side, main-loop context only:

- **`PageIn_Flush`** — clears `PageIn_Suspended` + `PageIn_InFlight`, empties
  the request FIFO (both priorities), leaves `Staging_Busy` alone. An already
  *published* page (staging→VRAM DMA enqueued) is allowed to land: its
  destination is a page frame, and every flush caller either resets the page
  cache (act/zone transition — display off, frames rebuilt) or keeps it valid
  (teleport rebase — page identity is position-independent, spec §5, so a
  landing prefetch is still correct art). No mid-DMA-queue surgery, ever.
- **Callers:** act/level transition (before `PageCache_Init`); the section
  teleport path *only if* it invalidates the tile cache (pure rebases don't
  flush — the in-flight page is still the right page). Block-tier analog for
  review symmetry: `TileCache_InvalidateStaging` (tile_cache.emp:159).
- **Never from interrupt context** — the flush races nothing because both
  producers of `Suspended`/`InFlight` transitions are main-loop-side
  (`PageIn_Process`) or fire only while decode is live (the hook, and decode
  can't be live inside another main-loop routine).

## 5. Instrumentation (DEBUG shape)

- `Dbg_PageIn_Preempts` (word) — incremented in the hook when it redirects; the
  P2a acceptance gate asserts it is >0 when slicing an 8 KB page (a zero means
  the hook never fired — the plan's Task-3 tripwire, kept).
- `Dbg_PageIn_Flushes`, `Dbg_PageIn_Resumes` (words) — cancel-path and re-entry
  coverage for the soak.
- Equivalence self-test rides `CompressionSelfTest`
  (engine/debug/compression_selftest.emp — debug-shape-only placement per
  map.toml): blocking `ZX0_Decompress` vs `ZX0R` byte-compare over the act pool
  pages, plus the forced-preemption variant once the hook exists.
- Per-frame idle minima: the corpus warns averages hide minima — the P2 DEBUG
  self-test should log a `VSync_Wait`-entry-to-VBlank cycle floor over the
  stress window (profiler ring holds 120 frames; state counters, not the
  per-frame profiler, per the standing method note).

## 6. What this needs from Sigil (the ask — sigil side owns implementation)

The mechanism is expressible today only by punching holes in exactly the
contracts Sigil exists to enforce. Six asks, in priority order; the first two
are required before Task 2/3 of the re-anchored plan can land clean:

1. **`@resumable` (stackless) proc attribute.** Build-fatal on any sp-touching
   instruction inside the proc (`bsr/jsr/jbsr/pea/link/movem` with sp,
   `-(sp)`/`(sp)+` operands), and on `with` brackets that lower to stack ops.
   Declares the register state set (here d0–d2/a0–a2 + ccr); anything live
   outside it is an error. This turns the decoder contract's "NO stack access,
   ALL state in registers" comment into a checked property — the whole safety
   argument of §1 rests on it.
2. **Exported extent symbols.** `pub` head symbol exists via placement already;
   the ask is a generated, linkable end-of-range symbol (e.g.
   `ZX0R_Decompress__end`) for `@resumable` procs, so vblank.emp's range check
   compiles from symbols instead of a hand-maintained sentinel label. (S3K used
   a magic stack offset; the spec's improvement is symbolic — make it *toolchain*
   symbolic.)
3. **A sanctioned stacked-frame accessor in handlers.** The hook reads/writes
   the interrupted PC at `62(sp)` — an offset derived by hand from the
   handler's movem set. Ask: an intrinsic (e.g. `irq_frame.pc` valid inside a
   `grants(vblank)` proc after a declared full-save movem) so the offset can't
   silently rot if the handler's save set ever changes. Also a home for the
   contract nuance that a handler which rewrites the return PC still satisfies
   `preserves(d0-a6)` but no longer returns-to-interrupted-instruction — the
   checker must not "optimize" or flag the redirect.
4. **Manufactured-frame resume license.** `PageIn_Process` executes `rte` from
   non-handler context (push saved SR, push saved PC, `rte`), and
   `PageIn_BankRegs` is *entered by* an rte with live decoder registers and
   exits by bare `rts` into its grand-caller's frame. Neither fits any current
   proc form. Ask: either a `@continuation` proc form (no callable contract,
   entered by rte/jmp only, register state declared not proven) or paired
   intrinsics (`bank_frame`/`resume_frame`) the checker understands.
5. **Typed computed `jmp`.** `jsr (a0) as Type` exists (game_loop.emp:42); the
   decoder's continuation exit needs the `jmp (a3) as Type` spelling — no
   precedent in the tree today.
6. **Registration + ritual.** New modules (`engine/compression/zx0_resume.emp`,
   `engine/level/page_in.emp`) mean new byte-emitting sections in map.toml's
   `order` and whatever the native driver's registry needs — plus the standing
   byte-changing-parcel ritual (SIGIL_BLOB_LEN_DRIFT, both binaries, repin →
   refreeze --ab). All sigil-side; aeon-side lands nothing until the asks
   above exist or an interim waiver form is agreed.

## 7. Review checklist (from the in-tree negative example)

Legacy `sonic_hack/code/engines/kosplus.asm` ported the S3K bookmark and broke
all three invariants. Whatever we build gets reviewed against its failure
modes:

- [ ] decode body physically inside `[ZX0R_Start, ZX0R_End)` — no `jsr` from
      the guarded range to an unguarded body (kosplus failure #3);
- [ ] the processor/dispatcher runs from the main loop's idle site, never from
      inside the V-int (kosplus failure #1);
- [ ] the bookmark set/hook actually has call sites in the shipped shape —
      grep proves the hook is live, DEBUG counter proves it fires (kosplus
      failure #2: zero call sites);
- [ ] lag path proof re-verified after any VSync_Wait/VBlank_Handler edit
      (the §2 structural argument is protocol-dependent, not local);
- [ ] no stack push anywhere between dispatcher entry and decoder fall-through
      (§3's rts-corruption trap);
- [ ] flush called at every cache-invalidating transition, and NOT at pure
      rebases (§4).
