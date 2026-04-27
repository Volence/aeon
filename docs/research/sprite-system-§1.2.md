# Sprite System §1.2 — Per-Task Research Findings

Living research doc. One section per task in `docs/superpowers/plans/2026-04-27-sprite-system-multisprite-and-piece-overflow.md`. Per project memory `feedback_research_in_plans`, every implementation step's first sub-task is research — findings accumulate here.

---

## Task 1 — Link-chain reality check (2026-04-27)

**Question:** Does any reference disassembly actually achieve "links never rebuilt during gameplay" in a way that saves cycles vs our current per-piece `move.b d5, (a4)+`?

**Findings across the 7 references:**

- **S.C.E.** (`Sonic-Clean-Engine-S.C.E.-/Engine/Objects/Render Sprites.asm:308,336,375`) — Pre-init chain in `Init_SpriteTable` (line 7), then per piece uses `addq.w #1, a6` to advance the SAT pointer past the link byte without rewriting it. 8 cycles per piece.
- **Batman & Robin** (`The Adventures of Batman and Robin/disasm/code/rendering/rendering.asm`) — Same pattern as S.C.E.: pre-init + `addq.w #1, a6` advance. 8 cycles per piece.
- **sonic_hack** (`sonic_hack/code/engines/build_sprites.asm:184,215,260,297`) — No pre-init relevant to link bytes; rewrites every frame: `addq.b #1, d5; move.b d5, (a2)+`. 4+8 = 12 cycles for the increment + write.
- **Vectorman / Gunstar / Alien Soldier / Thunder Force IV** — disasms are partially decompiled / less-readable; could not extract clean per-piece sequences. Pattern is consistent with S.C.E. or sonic_hack styles based on visible fragments.

**Cycle cost reality on 68000:**

| Approach | Per-piece link area cost |
|---|---|
| Rewrite (sonic_hack, our current code) | `move.b d5, (a4)+` = 8c (the `addq.b #1, d5` is needed independently for the MAX check, so we don't count it as link-area cost) |
| Pre-init + advance (S.C.E. / Batman) | `addq.l #1, a4` = 8c |
| Skip entirely (hypothetical) | Not achievable — must advance the pointer to write subsequent fields without clobbering the link byte |

**Wash confirmed:** The `move.b Dn, (An)+` postincrement and the `addq.l #1, An` pointer-advance both cost 8 cycles. Skipping the byte write doesn't save anything once you account for the advance. Reformulations using displacement (`2(a4)`, `4(a4)`) cost MORE per access (12c vs 8c), so they're net-worse. `movem.l` packing tricks would require byte-shift composition that costs more than it saves.

**Online evidence:**
- Hugues Johnson's "Sega Genesis Programming Part 10: Sprite Link List" — describes the link mechanism, doesn't claim per-frame skip is a win.
- Megacat Studios VDP Graphics Guide — confirms the sprite cache is write-through and the link byte is treated like any other SAT field.

**Conclusion / decision:**

The doc claim "links never rebuilt during gameplay" is **technically achievable** in S.C.E.'s "advance past, don't rewrite" sense, but **not a cycle win**. Our code rewrites every piece (sonic_hack pattern), which is functionally equivalent at identical cost.

**Decision for Task 1:** Stick with the planned doc correction — change wording to match what our code does (rewrites links every piece + terminator at end), explain the wash. Don't refactor code to S.C.E. style; it would be a cycle-neutral architectural change outside this plan's scope.

**Insight to surface in final summary:** A future cleanup task could swap our 4× `move.b d5, (a4)+` for 4× `addq.l #1, a4` plus update Init_SpriteTable as the source of truth — same cycles, cleaner mental model. Out-of-scope for §1.2 deferred-work closure but worth logging.

---

## Task 2 — Piece-count cache patterns (2026-04-27)

**Question:** Do reference engines cache sprite-piece count in their object structure for predictive overflow checks? If so, where, what size, when populated?

**Findings:**

- **Batman & Robin** — confirmed: `sprite_link_count` at object offset **$18, word-sized**. Populated at spawn + animation frame change. Used for predictive overflow ("would emitting this object overflow the SAT?").
- **Gunstar Heroes / Alien Soldier** — no piece-count cache, but extensive parent/child object linking ($58/$5C longwords). Handle overflow via global per-frame budgets rather than per-object caching.
- **S.C.E.** — no dedicated piece-count field in the SST. Reads count from mapping data inline at render time.
- **sonic_hack** — `build_sprites.asm:125` reads child sprite count from mapping data via `move.b (a6)+, d0`. Not cached in SST.
- **Vectorman** — separate dispatch-stub architecture, sprite work queued via `QueueDMA` with global per-frame budget (2880 bytes / 54 entries). No per-object piece count.
- **Thunder Force IV** — 32-byte type-segregated object pools, no piece-count cache. Overflow handled via round-robin priority rotation.

**Online evidence:**
- SpritesMind threads on VDP internals + sprite limit confirm 80-sprite cap is the hard hardware constraint and per-line dropout is independent.
- Hugues Johnson's link-list article describes the chain mechanism but doesn't mention piece-count caches.

**Decision for Task 2:**

- **Byte at $2D is correct** — max value is 80 (hardware cap), comfortably fits in 8 bits. Word would be wasteful for our case (Batman's word reservation may have been for future-proofing or alignment, not necessity).
- **Pattern validated** — Batman is the canonical example; we're following the same design with an SST size optimization.
- **Field placement at $2D pad slot** — keeps SST size at $50, no struct reshuffle needed. Verified by the existing `if SST_len <> $50 ; error` assert at structs.asm:98.
- `RF_MULTISPRITE = 4` is consistent with the existing render_flags bit allocation (bits 0-3 used, bits 4-6 free, bit 7 reserved for delete).

**Insight:** sonic_hack's "read count from mapping data inline" (no SST cache) is also viable — but our piece-count is checked BEFORE we begin walking the frame data, so caching avoids the pointer chase for the overflow check. Worth the byte.
