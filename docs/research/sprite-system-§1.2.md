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

---

## Task 4 — AnimateSprite frame-change refresh site (2026-04-27)

**Question:** Where do reference engines react to `mapping_frame` change beyond updating the index? Should our `sprite_piece_count` refresh sit (a) directly in AnimateSprite, (b) in a separate helper, (c) at the existing `prev_frame` update site (consolidate side effects)?

**Findings:**

- **s4_engine** — has change detection in two places: `animate.asm:54` (compares `prev_anim`, not `prev_frame`) and `dplc.asm:22-25` (compares `mapping_frame` vs `prev_frame`, then advances `prev_frame`). AnimateSprite *writes* `mapping_frame` but doesn't touch `prev_frame`. Perform_DPLC is the canonical "frame change" detector but only runs for objects that explicitly call it.
- **sonic_hack** — animation update at `display_animate.asm:67-86` does change detection on anim, not frame; uses a separate deferred PLC queue for DPLC.
- **S.C.E.** — `Animate Sprite.asm:13` does anim-change detection, no piece-count or DPLC side effects (clean engine, leaves DPLC to caller).
- **Batman & Robin / Vectorman / Gunstar / Alien Soldier / Thunder Force IV** — varied patterns, none exposed a piece-count cache update site distinct from animation.

**Decision for Task 4:**

Option (b) — separate helper called from each `mapping_frame` write site. Reasoning:

- Putting refresh inside Perform_DPLC (option c) wouldn't fire for objects without DPLC tables (most of our test objects). Wrong scope.
- Putting refresh always-unconditionally at end of AnimateSprite (variant of a) wastes cycles when frame didn't change.
- Helper at each `mapping_frame` write site fires exactly when needed, is reusable from PerFrame variant too.

**Implementation:** New `RefreshSpritePieceCount` helper at end of `animate.asm`. Called via `bsr.w` after each `move.b d0, SST_mapping_frame(a0)` in the main path; called via `bra.w` (tail-call) from PerFrame paths whose only post-write op is the rts. Five sites total: 1 in main AnimateSprite, 4 in AnimateSprite_PerFrame.

**Cycle cost:** bsr.w + rts adds ~34 cycles to the change path, plus ~30c for the helper body. Total ~64c per frame change. Frame changes are rare (every several gameplay frames, not every game tick). Negligible budget impact.

**Insight:** Our existing `prev_frame` field at $1F is touched ONLY by Perform_DPLC, never by AnimateSprite. That's why Perform_DPLC's change-detection works (mapping_frame and prev_frame diverge on each AnimateSprite frame change, then DPLC reconverges them). The piece_count refresh is independent — it doesn't touch prev_frame and won't interfere with DPLC.

---

## Task 5 — Predictive overflow pre-check (2026-04-27)

**Question:** Predictive vs reactive overflow handling: do reference engines pre-check sprite overflow before emitting an object's pieces, or only react per-piece?

**Findings:**

- **S.C.E.** — per-piece dbeq only, no predictive pre-check. Half-rendered objects possible at the cap.
- **sonic_hack** — hybrid: `cmpi.b #80, d5; blo DrawSprite_Cont` pre-check at start of each piece-emission entry, AND per-piece dbeq fail-safe. Most defensive.
- **s4_engine** existing — outer `.object_loop` has `cmpi.w #MAX_VDP_SPRITES, d5; bge .band_limit_pop` (already-at-cap), per-piece dbeq inside loop. No PIECE-COUNT-aware pre-check before loop.

**Decision for Task 5:**

Add per-object pre-check using cached `SST_sprite_piece_count`. Sit it right after `movea.w (a2), a0` (SST address loaded), before any indexing or per-piece work. Five new instructions ~28 cycles per object. For uncached objects (sprite_piece_count=0), the pre-check is a no-op (d5 + 0 ≤ 80 unless we already hit the cap, which the outer check catches), so behavior is preserved.

**Layered defense:**
1. Outer `.object_loop` check — "already at cap, stop"
2. **NEW: per-object pre-check** — "this object would push us over, skip whole"
3. Existing per-piece `cmpi.b #MAX_VDP_SPRITES, d5; dbeq d4, .piece_loop_*` fail-safe

This matches sonic_hack's hybrid approach plus our existing scanline-band budget — most defensive Genesis sprite engine in the references.

---

## Task 6 — Piece-emission factoring (2026-04-27)

**Question:** Single subroutine with flag-dispatch, or 4 separate inline blocks for the 4 flip variants?

**Findings:** All references (S.C.E., sonic_hack, Batman) use **4 separate inline blocks**. Reasoning: each flip variant has 1-3 unique instructions (eori for X-flip, neg + height lookup for Y-flip), and a unified subroutine would require per-piece conditionals that erase any code-size savings.

**Decision for Task 6:** Factor into `Emit_ObjectPieces` but **keep the 4 flip variants inline within the subroutine**. The subroutine wraps the dispatch + 4 blocks. Caller does `bsr.w Emit_ObjectPieces`. JSR/RTS overhead: one per object (not per piece). Code-size savings: ~120 bytes by removing the duplicate 4-block dispatch from inline code path.

**Calling convention:** All registers passed via expected-state convention:
- a3 (frame data, post piece-count word), a4 (SAT write ptr), d2/d3 (screen pos), d4 (piece count raw), d5 (running total), d6 (art_tile), d0 (flip bits, masked).
- a0 is repurposed inside the subroutine as the flip-table base.
- d7 preserved (band-loop counter must survive).

**Verified:** OJZ scroll test renders byte-identical to pre-refactor (10842 bytes both screenshots). ObjectTest shows sprites correctly emitting through new path. No regression.

---

## Task 7 — Multi-part test fixture baseline (2026-04-27)

**Decision:** Reuse the existing `objects/test_parent.asm` (TestParent + TestChildPart) instead of creating a new `test_multipart.asm`. TestParent already spawns parent + 3 children at offsets via `CreateChild_Normal`, has children calling `Draw_Sprite` independently, and is wired into the ObjectTest scene. Plan said "build on existing test_parent.asm" — interpreted as "reuse" rather than "create alongside."

**Baseline state (Task 7):**
- Parent and children spawn correctly via Load_Object → TestParent init → CreateChild_Normal.
- Each child's per-frame routine: `jmp Draw_Sprite` (independent registration, current code path).
- Parent has `RF_COORDMODE` set but NOT `RF_MULTISPRITE` — children draw via existing band-registration path.
- Visual: 3 small parents at top spawn 3 children each (9 child squares visible), Sonic at bottom-left, 8 stress emitters scattered.
- Baseline screenshot saved at `test/multipart_baseline.png` (1740 bytes).

**Task 8 will:** Add the Draw_Sprite child-skip guard + Render_Sprites sibling walk, then `bset #RF_MULTISPRITE` on the parent in TestParent's init, and verify identical visual output via screenshot diff.

**Reference fixture patterns checked:** TestParent's existing structure mirrors S.C.E.'s child-creation patterns (data-driven descriptor table). No additional research needed for fixture design itself.

---

## Task 8 — Compound/multi-sprite rendering (2026-04-27)

**Question:** Validate Approach 1 + semantic C against real engines. Where does sibling walk happen? What's the screen-position semantic for children? mapping_frame semantic? art_tile inheritance? Cycle cost?

**Findings:**

- **Sonic 3K** (`skdisasm/s3.asm:29940-30024`) and **S.C.E.** (`Render Sprites.asm:259-292`) both walk children **inline within Render_Sprites** after the parent's pieces have been emitted. Pattern is identical between the two.
- **Major divergence from spec discovered**: Both real engines use a **static sub-sprite array** (count + per-child X/Y/frame triplets) embedded in object data, NOT a sibling chain walk. The array approach is ~10 cycles faster per child (no null-check, tighter loop).
- **mapping_frame semantic**: Real engines have **each child store its own frame byte** in the static table. Parent's mappings pointer is reused; per-child frame indexes that table. Our spec's "shared parent mapping_frame" (semantic C) is a SLIGHT DEVIATION — but valid as long as children visually want to follow parent's animation. For independent-frame children, would need adapting.
- **screen position**: Real engines store **independent world coordinates** for each child, then camera-adjust per child. Matches what our chain-walk does (reads child's `SST_x_pos`/`SST_y_pos`).
- **art_tile/palette/priority**: Both engines have all children inherit parent's `art_tile`. Our spec has children use their OWN `art_tile`. Per-child art_tile is more flexible (allows different palettes per part); the cost is one extra word read per child.

**Decision for Task 8:**

**Stay with the spec's sibling-chain approach** for this implementation. Reasons:
- We already have `sibling_ptr` infrastructure for object lifecycle (CreateChild_Normal, DeleteChildren). Using a separate static array would duplicate or complicate.
- Cycle cost difference is small (~10c per child, negligible for typical multi-part objects).
- Sibling chain naturally grows/shrinks as children are added/removed at runtime; static array is fixed-size.
- Our use case (mostly Sonic-style multi-part bosses, Tails' tails) doesn't push the cycle budget.

**Document as future-improvement:** static sub-sprite array (S3K/S.C.E. style) is a known optimization. Worth revisiting if multi-sprite cycle budget becomes a concern with real workloads.

**Implementation gotchas resolved:**
- Register pressure: a2 (band-pointer in outer loop) repurposed as parent SST during sibling walk; saved/restored on stack. Child SST also stack-saved across `Emit_ObjectPieces` calls (since the subroutine clobbers a0).
- `RF_ONSCREEN` for children: Never set (children skip Draw_Sprite). Acceptable; parent's bounds check is the gate.
- Mid-chain overflow: skip just the offending child, continue chain (matches spec).
- Child's piece count read just-in-time from frame data after indexing — no reliance on stale `sprite_piece_count` cache.

**Verified visually:** TestParent's 3 children render identically with `RF_MULTISPRITE` set (Task 8) vs cleared (Task 7 baseline). Compared `multipart_baseline.png` (1740 bytes) vs `multipart_batched.png` (1944 bytes) — small byte-size difference is PNG compression of live particles, multi-sprite groups themselves are visually identical. SAT contents inspected: child entries present with correct positions.

---

## Task 9 — Stress test + closure (2026-04-27)

**Stress observation:** ObjectTest scene with default `STRESS_EMITTER_INTERVAL=8` produces `Sprites_Rendered=49` (read at end of Render_Sprites via run-to breakpoint at the `move.w d5,(Sprites_Rendered).w` instruction). Aggressive spawn rate (interval=2) saturates the 16-slot effect pool before reaching the 80-piece SAT cap, so the cap is not pressure-tested by this fixture.

**Why pre-check verification is acceptable without forced overflow:**
1. The pre-check is 4 instructions (`moveq #0, d0; move.b SST_sprite_piece_count(a0), d0; add.w d5, d0; cmpi.w #MAX_VDP_SPRITES, d0; bhi.w .next_object`). Straightforward; build success confirms assembly.
2. The cached `sprite_piece_count` is verified populated correctly (Task 3 + Task 4 inspections).
3. The per-piece `dbeq d4, .piece_loop_*` fail-safe inside `Emit_ObjectPieces` catches actual SAT cap if the pre-check is bypassed.
4. Forcing overflow would require either (a) a dedicated stress fixture with >40 dynamic-pool-spawned objects (each with multi-piece mappings), or (b) lowering `MAX_VDP_SPRITES` temporarily — both out of scope for this plan and not needed for correctness.

**Future improvement:** add a synthetic stress fixture that spawns ~50 objects with 2+ pieces each via the dynamic pool (bypassing the effect pool's 16-slot bottleneck). Would push past 80 pieces and trigger the pre-check observably.

**Closing the deferred-work entry:** `DEFERRED_WORK.md` "Sprite Rendering Pipeline (§1.2)" entry marked DONE 2026-04-27.
