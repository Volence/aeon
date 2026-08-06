# ARCH §9.7 rewrite — standalone proposal (2026-08-06)

**Status: PROPOSAL. ENGINE_ARCHITECTURE.md is deliberately untouched** — the
reconciliation lands with the Phase-2 implementation (plan Task 12), per the
standing rule and to avoid colliding with the parallel sigil session's tree.
This file holds the full replacement text so the morning ruling on decision
point 4 (naming/structure — see `2026-08-06-97-decision-memo.md`) can be made
against concrete prose, and so Task 12 becomes a paste + cross-ref sweep.

Drafted to the memo's recommended shape (title A, two layers, D2-C/D3
gating). If the rulings differ, §9.7.3 and the title line are the only parts
that move.

---

## Replacement text for §9.7 (drops in at ENGINE_ARCHITECTURE.md:3800–3835)

> ### 9.7 Idle-Time Deferred Work — Pre-Chunked Pages + Supervisor Bookmark
>
> Deferred CPU work (mid-game art-page decode, any future oversized decompression)
> runs in main-loop idle time — the `VSync_Wait` spin — structured in two layers.
> This is the mechanism three shipped Genesis codebases independently converged on
> (S3K `Set_Kos_Bookmark`, Ristar's `$FFE5BC` yield protocol, S.C.E. KosPlusM),
> hardened with contract enforcement they didn't have.
>
> **Layer 1 — granularity (pre-chunking).** Work arrives pre-cut at build time
> into units sized for the common idle window: act art pools are split into
> pages (KosM's $1000-granule precedent; page size is a build knob, swept on the
> stress fixture). Small units mean the *scheduler* needs no time model — most
> units simply fit. Pre-chunking alone is not sufficient at the measured worst
> windows (a 2 KB page ≈ 45 K cycles vs ~42.5 K average idle in a diagonal-fall
> window, 2026-08-05 measurement), which is why Layer 2 exists.
>
> **Layer 2 — preemption (the supervisor bookmark).** The unit decoder runs as a
> straight-line supervisor-mode loop in the idle spin. If VBlank fires mid-decode,
> `VBlank_Handler` checks the interrupted PC (read from the known stack-frame
> offset behind exported symbols) against the resumable range
> `[ZX0R_Start, ZX0R_End)`; on a hit it banks the decoder's registers + SR + PC
> to RAM at handler exit and redirects the `rte` into the main loop. Next frame,
> the dispatcher manufactures the frame back (push SR, push PC, `rte`) and the
> decode continues mid-instruction-stream. Spawn, resume, and preempt-resume are
> one code path (Ristar's manufactured-bookmark trick). Cost: ~300–400 cycles
> per preempted frame (~0.3%) — decode consumes ALL idle with zero overshoot,
> and unit size becomes a density/manifest tradeoff, not a latency constraint.
>
> **The resumable-region contract** (compiler-enforced once the Sigil
> `@resumable` attribute lands; the three invariants every shipped bookmark
> traces to):
> 1. **Stack-neutral:** no push/call anywhere in the range — abort is "don't
>    resume", and resume works from any stack depth. The resumable ZX0 variant
>    inlines its elias reads and takes caller-owned registers.
> 2. **Register-resident state:** all decoder state in d0–d2/a0–a2 + CCR at
>    every instruction (the banked SR word carries the live carry/X flags);
>    the bookmark record is 34 bytes.
> 3. **One contiguous PC range, symbol-exported**, checked only in the VBlank
>    handler; the bookmark is the handler's **final act** (it fires at `rte`,
>    after all frame-critical work), and the **lag path can never bookmark** —
>    decode is only ever live after `VBlank_Ready` is set, so a mid-decode
>    VBlank always dispatches `VInt_Level`, structurally.
> Additionally: no VDP, no Z80, no shared-RAM writes from inside the range —
> decode targets a private staging buffer; publication is the dispatcher's
> single aligned write + DMA enqueue after completion (atomic wrt interrupts,
> no critical sections).
>
> **Admission & gating.** Requests queue in a small two-priority FIFO: demand
> (a fill is stalled) ahead of prefetch (leading-edge speculation). Demand is
> never gated. Speculative *starts* pass a trailing-lag gate — skip if the
> previous frame lagged, bounded to one consecutive skip so sustained lag can't
> cascade into cold pages (the same gate shape shipped for block prefetch).
> Gates use trailing indicators only, never VDP beam position: deferred work
> runs at fixed points in the frame, so the beam cannot gauge load (measured
> lesson, 2026-07-16). There is no unified cost arbiter: under the bookmark,
> deferred CPU is structurally free (it can only consume idle), and the truly
> contended resources — DMA bytes, the single staging slot — are governed by
> the per-act art budget word, the dual-cap DMA admission, and single-flight
> staging. The block tier's budget seam in `Tile_Cache_Fill` remains the named
> adoption point if a future consumer ever needs cost-denominated arbitration.
>
> **Cancel/flush.** Speculative state needs an explicit invalidation path:
> `PageIn_Flush` empties the FIFO and drops any suspended decode (main-loop
> context only). Called at cache-invalidating transitions (act/zone change);
> NOT at pure teleport rebases — page identity is position-independent, so
> in-flight work stays valid. A published page's DMA is always allowed to land.
>
> **Consumers:** ZX0 art-page decode (art-streaming Phase 2 — the driving
> consumer); S4LZ streaming for any larger-than-block payloads (§2.1); palette
> blend during transitions (~3.8 K cyc/frame — a fixed idle-slot call, no
> preemption machinery needed). Ring/object pre-scan was satisfied by the §4.9
> entity window and is a non-consumer.
>
> **Rejected: user-mode cooperative multitasking** (this section's previous
> design, from plutiedev). Zero shipped adopters in ~15 years across every
> examined commercial engine (six disassemblies grepped exhaustively — no SR
> write ever clears bit 13; B&R uses USP as a 16th scratch register); TAS is
> broken as a lock primitive on MD1/MD2; critical sections would need `trap`
> syscalls; and it installs a permanent debugging tax — two register contexts,
> preemption at any instruction — in an engine whose worst historical bugs were
> preemption-window bugs. The bookmark delivers user-mode's two real advantages
> (straight-line decoder, all idle consumed) with none of this. Its previously
> claimed "~80–120 cycles" switch cost was unsupported; real 68000 timings give
> ~300–400 cycles for a full two-way switch in either design — negligible
> either way, and not why the decision goes the way it goes.

---

## Cross-reference sweep (lands with the rewrite, Task 12)

| Site | Today | Change |
|---|---|---|
| ARCH:1312 (§1.5 stub) | "Superseded by §9.7 (Cooperative Multitasking)… No manual chunking, no bookmark systems" | Point at the new §9.7; delete the "no bookmark systems" claim (the bookmark IS the design) |
| ARCH:1390 | "Background Task (§9.7) + DPLC Lookahead" label | Rename to "Idle-time work (§9.7)…" |
| ARCH:1437 | "…that's the §9.7 cooperative-multitasking budgeted-decode design" | "…that's the §9.7 pages+bookmark idle-time path" |
| ARCH:3844 (§9.8) | "the background task (9.7) must coordinate with the bank register" | Reword: banked-source decode must map the bank before *starting or resuming* a unit; add that a preempted decode's bank must be part of the bookmark record IF banked art ever ships (today: art in fixed bank, no action) |
| ARCH:3885 (§9.12) | "The multitasking system (9.7) enables S4LZ to run continuously…" | Reword to the bookmark pipeline; keep the pipeline framing (decode → enqueue → VBlank DMA), it survives |
| ARCH:3802/3804 | PLANNED-status + drift-flag blockquotes | Delete both (the rewrite discharges them) |
| DEFERRED_WORK:55–64, 714–733 | "§9.7 is the sole gate on three consumers… highest-leverage unlock" | Rescope to point at the Phase-2 plan as the vehicle; close when P2a merges |
| DEFERRED_WORK:746 | Amendment #1 row still calls rejected §9.7 "the designed vehicle" | Update pointer to the new §9.7 |
| DEFERRED_WORK:866–875 (§2.1 streaming row) | "gated ONLY on §9.7" | Same rescope |
| Spec §5 | "lower-RAM slack is 9,150 B" | Stale (6,078 B post-H5, itself to be re-verified against current `s4.debug.lst` at Task 1) |
| Spec §4 | idle figures "~62% max scroll / ~24% diagonal" | Superseded by the 2026-08-05 table (74.3 / 67.8 / 33.2) and regime (e) ~42% |

Also sweep, per plan Task 12 step 2: "fully resident", "loaded once at init",
`ART_POOL_PAGE_TILES = 256` claims in ARCH §2 and CLAUDE.md's engine summary
("fully resident, loaded once at init" line) once streaming actually ships.
