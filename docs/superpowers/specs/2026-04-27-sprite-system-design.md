# Sprite System — Closing §1.2 Deferred Work

**Date:** 2026-04-27
**Scope:** Engine §1.2 / §3.5 — finish the deferred bits of the sprite rendering pipeline. Multi-sprite batching, piece-count overflow prediction, and a documentation correction. All other §1.2 / §3.5 features are already implemented (`engine/objects/sprites.asm`, `engine/buffers.asm`).

## Background

The §1.2 deferred-work entry covers: two-phase render, priority-band sorting, overflow handling, multi-sprite batching, sprite count per object. Most of it shipped during §3 Object System work. Auditing what's actually in the codebase, only two bullets remain:

1. **Multi-sprite batching** — no `Render_Sprites_MultiDraw`-equivalent path. Multi-part objects today have every child call `Draw_Sprite` independently and pay full per-piece bounds + budget cost.
2. **Piece-count overflow prediction** — no `sprite_piece_count` field in SST. The engine cannot predict whether emitting an object will exceed the 80-piece SAT cap; it only enforces the cap reactively per-piece via `cmpi.b #MAX_VDP_SPRITES, d5`.

A third item came up during research: ENGINE_ARCHITECTURE.md claims "links never rebuilt during gameplay," but `Render_Sprites` writes the link byte every piece. Research across all 7 reference disassemblies + 68000 timing analysis confirmed this is genuinely a wash on hardware (postincrement-write costs the same as pointer-advance), so the doc statement is aspirational and will be corrected to match reality.

## Goals

- Add the multi-sprite rendering path so a parent with N children pays one bounds check + one band slot.
- Add overflow prediction that skips whole objects intact, never half-rendered.
- Correct ENGINE_ARCHITECTURE.md to match the actual link-chain behavior.
- Maintain backward compatibility with existing single-object Draw_Sprite/Render_Sprites flow.

## Non-Goals

- Link-chain optimization (researched, wash on 68000).
- Per-band scanline budget changes — already implemented and working.
- DPLC lookahead, sprite cache table-switching, animation-event-driven render — separate deferred items.
- Animation-side `Animate_MultiSprite` driving children's full scripts — punted to §3.6 / step-level research.

## Architecture

### Multi-sprite batching — Approach 1 (Parent-only registration)

- A multi-sprite parent has `RF_MULTISPRITE` (render_flags bit 4) set.
- Children of the parent have `parent_ptr` populated (already happens via `CreateChild_*` routines).
- **`Draw_Sprite` child-skip guard:** at the very top of `Draw_Sprite`, before any other work, check `parent_ptr`. If non-zero, fetch parent's `render_flags`, `btst RF_MULTISPRITE`. If set → `rts` immediately. Children of multisprite parents never enter a priority band.
- **Render-time sibling walk:** in `Render_Sprites`, when the object being processed has `RF_MULTISPRITE` set, after emitting its own pieces, walk `sibling_ptr` chain and emit each child's pieces using the same factored emission code, with the following per-child semantics:
  - Screen position: from child's own `x_pos`/`y_pos` (with `RF_COORDMODE` honored). Children may move independently of parent (e.g., trailing tail segments).
  - Mappings table: from child's `mappings`.
  - Frame index: from **parent's** `mapping_frame` (semantic C — shared frame index, per-child mapping data).
  - Art tile: from child's `art_tile`.
  - Flip: from child's `render_flags` (RF_XFLIP / RF_YFLIP).

### Piece-count overflow prediction — total-only

- New SST field `sprite_piece_count` (1 byte at offset `$2D`, reusing the existing pad slot).
- Populated at `Load_Object` (initial mapping_frame's piece count) and refreshed at `AnimateSprite` whenever `mapping_frame` changes (one indirect read + store after the existing frame advance).
- In `Render_Sprites`, before entering the per-piece emission loop for an object, pre-check: if running `d5` (total pieces emitted) + object's `sprite_piece_count` > `MAX_VDP_SPRITES` (80), skip the whole object (`bra .next_object`). The existing `cmpi.b #MAX_VDP_SPRITES, d5 ; dbeq d4, ...` per-piece check stays as a defensive fail-safe.
- For multi-sprite children, the pre-check uses the just-in-time piece count read from `(a3)` after indexing into the child's frame data, since we have to read it for the `dbf` loop anyway. Children's `sprite_piece_count` SST field is unused on the multisprite path. Mid-chain overflow skips only the offending child and continues the sibling walk.

### Doc correction

- ENGINE_ARCHITECTURE.md §1.2 and §3.5: replace "Pre-initialized link chain (80 entries, set at level init, never rebuilt)" with "Link chain pre-initialized at boot; per-frame writes overwrite link bytes, with terminator patched after the last rendered piece." Brief note explaining the 68000 timing parity that makes "never rebuilt" not actually faster.

## Components

| Area | File | Change |
|---|---|---|
| SST layout | `structs.asm` | Add `sprite_piece_count ds.b 1` at `$2D` (replacing the existing pad). Verify `SST_len` still equals `$50`. |
| Render flags | `constants.asm` | Add `RF_MULTISPRITE = 4`. |
| Sprite registration | `engine/objects/sprites.asm` `Draw_Sprite` | Add child-skip guard at top: read parent_ptr, if non-zero btst parent's RF_MULTISPRITE, rts on set. |
| Sprite render | `engine/objects/sprites.asm` `Render_Sprites` | Factor the four-flip-variant inner piece-emission body into a reusable subroutine. Add total-piece overflow pre-check before invoking it. Add sibling-walk path triggered by parent's `RF_MULTISPRITE`. |
| Object init | `engine/objects/load_object.asm` | Populate `sprite_piece_count` from initial frame data when mappings is set. |
| Animation | `engine/objects/animate.asm` | After `mapping_frame` advances and differs from `prev_frame`, refresh `sprite_piece_count` from new frame's data (one indirect read + store). |
| Doc | `docs/ENGINE_ARCHITECTURE.md` | §1.2 + §3.5 link-chain truth correction. |
| Test fixture | `objects/test_multipart.asm` (new) | Parent + 3-4 siblings, parent has `RF_MULTISPRITE`, distinct mappings + art_tile per child, parent-driven mapping_frame animation. |
| Stress test | existing `test_stress_emitter.asm` integration | Pressure 80-piece SAT cap to verify overflow prediction skips whole objects without tearing. |

## Data Flow

**Spawn (multi-sprite parent + children):**
1. Parent object's data block has `RF_MULTISPRITE` set in render_flags initial value.
2. Parent's per-frame routine calls `CreateChild_Complex` (or similar) — children inherit `parent_ptr → parent` and chain via `sibling_ptr`.
3. `Load_Object` for each (parent and children) reads initial mapping frame's piece count into `sprite_piece_count`.

**Per-frame (multi-sprite group):**
1. Parent's per-frame routine runs `AnimateSprite` (advances parent's `mapping_frame`, refreshes parent's `sprite_piece_count` if frame changed).
2. Parent calls `Draw_Sprite` — registered in priority band normally.
3. Each child's per-frame routine runs (movement etc.) and calls `Draw_Sprite` — early-return guard sees parent has `RF_MULTISPRITE`, returns immediately. Children never register.
4. After object loop completes, `Render_Sprites` runs:
   - Walks priority bands.
   - For each registered object, pre-checks `d5 + sprite_piece_count > 80`. Skip whole object on overflow.
   - Emits parent's own pieces via factored subroutine.
   - If parent has `RF_MULTISPRITE`, walks `sibling_ptr` chain. For each child: index parent's `mapping_frame` into child's `mappings`, read piece count from frame data, pre-check overflow (skip just this child if it would fail), emit pieces via the same subroutine using child's screen position, art_tile, flip flags.

**Per-frame (regular single-sprite object):**
1. Object's per-frame routine runs `AnimateSprite` (refreshes `sprite_piece_count` on frame change).
2. Object calls `Draw_Sprite` — early-return guard reads parent_ptr=0, skips guard, registers normally.
3. `Render_Sprites` pre-check `d5 + sprite_piece_count > 80`, emits or skips. No sibling walk (RF_MULTISPRITE clear).

## Error Handling

- **Mid-chain child overflow:** skip just that child, continue chain. Other children still get a chance to fit. Documented in code comment.
- **Parent on-screen but children off-screen:** parent's bounds check is the only on-screen test for the whole group. Children's screen-relative positions can land off-screen, but their pieces will be emitted with off-screen Y values, which the VDP discards naturally. No tearing risk; just a few wasted SAT entries on edge cases. Acceptable cost — adding per-child culling defeats the batching purpose.
- **Parent missing children but RF_MULTISPRITE set:** sibling walk reads `sibling_ptr=0` immediately, exits cleanly. No-op path, just one extra `tst.w` per parent.
- **Overflow pre-check on stale `sprite_piece_count`:** the per-piece `cmpi.b #MAX_VDP_SPRITES, d5 ; dbeq d4` defensive check inside the existing inner loop catches any miscount. Never tears the SAT layout.
- **`SST_len` invariant:** the assert in `structs.asm` (`if SST_len <> $50 ; error`) catches any regression from the pad-slot reuse.

## Testing

- **Functional:** `test_multipart.asm` parent + 3-4 siblings rendering correctly under animation. Visual verification via Exodus SAT viewer + Plane A screenshot capture comparison.
- **Sibling-walk correctness:** instrument a one-time profiling counter to confirm child Draw_Sprite calls early-return (count of guard hits should equal sum of children spawned).
- **Overflow prediction:** stress test pushes total pieces past 80 with multi-sprite + regular sprites mixed. Verify `Sprites_Rendered` matches actual non-zero SAT entries (no torn objects). Compare against current behavior (per-piece cap) to confirm predicted skips look cleaner.
- **Performance:** existing `Prof_RenderSprites` V-counter measurement before/after, with single-sprite-only and multi-sprite-heavy scenes, to confirm the factored subroutine doesn't regress baseline cost and the multi-sprite path is bounded.
- **Regression:** existing single-sprite tests (test_player, test_animated, etc.) still render identically — proven by Plane A snapshot diff.

## Open Questions Punted to Step-Level Research

Each implementation step's first sub-task is a research pass across all 7 reference disassemblies + online + modern-technique sources, targeted to that step's concern:

- Whether multi-sprite children call `AnimateSprite` at all (§3.6 territory). Affects independent vs. parent-driven animation timing.
- Exact register layout for the factored piece-emission subroutine (pass via stack vs. registers, JSR vs. inline).
- Whether the `parent_ptr`/`RF_MULTISPRITE` check at the top of `Draw_Sprite` should be conditionalized to only run for objects that ever participate in multi-sprite groups (cycle vs. simplicity tradeoff).
- Whether mid-chain child overflow should always skip-just-this-child or sometimes break the chain entirely.
- Whether S.C.E.'s `Animate_MultiSprite` (parent drives all children's animation script positions) should be implemented now or deferred to a §3.6 follow-up.
- Whether children's `RF_ONSCREEN` state needs to be propagated (currently never set since children skip Draw_Sprite).

## Closes

- DEFERRED_WORK.md "Sprite Rendering Pipeline (§1.2)" entry.
